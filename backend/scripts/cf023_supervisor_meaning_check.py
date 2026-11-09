"""Closed policy2 source loader and focused owned-PG verification. No live factory by default."""
import hashlib
import importlib.util
from pathlib import Path
import sys

MEANING_MODULES = ('domain.meaning_proposals', 'application.meaning_policy', 'infrastructure.openai_meaning_gateway')


def load_meaning(*, gateway=None):
    from scripts.cf022_supervisor_core_check import load_core
    from scripts.check_safe import CF023_INPUTS
    root = Path(__file__).resolve().parents[2]
    for relative, digest in CF023_INPUTS.items():
        if hashlib.sha256((root / relative).read_bytes()).hexdigest() != digest:
            raise RuntimeError('Meaning source pin mismatch')
    load_core()
    for suffix in MEANING_MODULES:
        name = 'src.supervisor.' + suffix
        path = root / ('ai/src/supervisor/' + suffix.replace('.', '/') + '.py')
        if name not in sys.modules:
            spec = importlib.util.spec_from_file_location(name, path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            parent, _, leaf = name.rpartition('.')
            setattr(sys.modules[parent], leaf, module)
        if Path(sys.modules[name].__spec__.origin).resolve() != path.resolve():
            raise RuntimeError('Meaning module origin mismatch')
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(sys.modules['src.supervisor.api.routes'].make_router(gateway=gateway))
    return app


async def verify_meaning(proof):
    from scripts.cf003_admission_check import isolated_application, check
    with isolated_application(proof) as observed:
        try:
            result = await _verify_meaning(proof)
        except BaseException as error:
            from scripts.cf002_interactive_login import safe_print
            frames=[];tb=error.__traceback__
            while tb:
                if tb.tb_frame.f_code.co_filename==__file__:
                    frames.append({'source':'meaning_checker','function':tb.tb_frame.f_code.co_name,'line':tb.tb_lineno})
                tb=tb.tb_next
            safe_print({'phase':'cf023_checker_failure','frames':frames[-8:],'observed_denials':dict(observed)})
            raise
        check(not any(observed.values()), 'CF023 forbidden access')
        return result | {'observed_denials': dict(observed)}


async def verify_live(*, counter_agreement=None, key_supplier=None):
    """No implicit keys, outbound network, epoch reset or unpriced counting request."""
    # A separate approved verifier must provide the full-input mapping and a documented counting fee bound.
    # The current published evidence does not establish that bound; no credential callback is invoked.
    from src.supervisor.infrastructure.meaning_gateway import CounterUnavailable
    raise CounterUnavailable()


async def _verify_meaning(proof):
    import asyncio
    import copy
    from contextlib import ExitStack
    from datetime import timedelta
    from types import SimpleNamespace
    from unittest.mock import patch
    from uuid import uuid4, UUID
    import httpx
    from sqlalchemy import select, text
    from db.models.auth.models import AuthUser
    from db.models.common.stock import Stock
    from db.models.supervisor.preparation import SupervisorMeaningPreparation as Preparation, SupervisorMeaningEpoch as Epoch
    from db.models.supervisor.request_binding import SupervisorRequestBinding as Binding
    from db.session import get_session
    from src.api.main import app
    from src.shared.config import settings
    from src.shared.infrastructure.clients.ai_client import AIClient
    from src.modules.auth.api import router as auth
    from src.modules.auth.application.session_service import issue_session, csrf_token
    from src.modules.supervisor.api import router as routes
    from src.modules.supervisor.application.preparation_service import PreparationService
    from src.modules.supervisor.infrastructure import preparation_repository as repo
    from src.modules.supervisor.infrastructure import repository as bindings
    from src.modules.supervisor.domain.contracts import canonical, sha, MEANING_SPEC, MEANING_SPEC_SHA256
    from src.modules.stocks.application.resolver_service import StockResolverService
    from src.modules.stocks.api.schemas import StockResolveResponse
    from src.modules.flow.api import analysis_router
    from scripts.cf002_interactive_login import owned_session, safe_print, migrate_owned
    from scripts.cf003_admission_check import check, migration
    from scripts.cf012_analysis_check import flow_app, engine_result

    groups, phases, models, dispatch = [], [], [], []
    mode = 'normal'
    ack_seen = False
    target_key = None
    held, release = asyncio.Event(), asyncio.Event()
    tasks = []

    def mark(label):
        groups.append(label)
        safe_print({'phase':'cf023_check','label':label,'status':'passed'})

    async def sql(query, params=None):
        async with owned_session(proof) as session:
            return await session.scalar(text(query), params or {})

    async def user():
        async with owned_session(proof) as session:
            value=AuthUser(id=uuid4());session.add(value);await session.flush()
            cookie, principal=await issue_session(session,value)
            await session.commit()
            return cookie,principal

    primary, other = await user(), await user()
    async with owned_session(proof) as session:
        session.add_all([Stock(stock_code='005930',stock_name='삼성전자',market='KOSPI'),Stock(stock_code='000660',stock_name='SK하이닉스',market='KOSPI'),Stock(stock_code='000720',stock_name='현대건설',market='KOSPI')])
        await session.commit()
    preserved=await sql('SELECT count(*) FROM auth_users')
    await migration(proof,'c22001a7e0001',downgrade=True)
    check(await sql("SELECT to_regclass('supervisor_meaning_preparations')") is None,'CF023 empty downgrade')
    await migrate_owned(proof)
    check(await sql('SELECT count(*) FROM auth_users')==preserved,'CF023 original rows preserved')
    mark('additive_migration_empty_roundtrip_old_rows_preserved')

    class Gateway:
        async def propose(self,draft,*,attempt_id=None):
            models.append(attempt_id)
            q=draft.original_query
            start=q.find('현대건설')
            return dict(schema_version='supervisor.meaning.v1',mentions=[dict(evidence=dict(source_kind='original_query',answer_id=None,start=start,end=start+4,text='현대건설'),negation=None)] if start>=0 else [],views=[],conditions=[])
    planner=load_meaning(gateway=Gateway())
    token='cf023-synthetic-service-token-at-least32'
    flow=flow_app(lambda request,context:engine_result(request,context))

    def client(*args,**kwargs):
        value=AIClient(*args,**kwargs)
        core=AIClient(*args,**kwargs,transport=httpx.ASGITransport(app=planner))
        execution=AIClient(*args,**kwargs,transport=httpx.ASGITransport(app=flow))
        async def plan(payload):
            phases.append(payload['data']['phase'])
            if mode in {'claim_race','late_delete'} and payload['data']['phase']=='start':
                held.set();await release.wait()
            return await core.plan_supervisor_core(payload)
        async def analyze(payload):
            dispatch.append(payload['analysis_id'])
            return await execution.analyze_flow(payload)
        value.plan_supervisor_core=plan;value.analyze_flow=analyze
        return value

    async def sessions():
        async with owned_session(proof) as session:
            original=session.commit
            async def commit():
                nonlocal ack_seen
                if mode in {'root_ack','binding_ack'} and not ack_seen:
                    cls=Preparation if mode=='root_ack' else Binding
                    column=cls.prepare_key_digest if mode=='root_ack' else cls.client_key_digest
                    exists=await session.scalar(select(cls.id).where(column==target_key))
                    if exists is not None:
                        await original();ack_seen=True
                        raise OSError('Fixed synthetic commit ACK loss')
                await original()
            session.commit=commit
            yield session

    async def call(method,path,body=None,identity=None):
        cookie,principal=identity or primary
        headers={'origin':'http://localhost:3200','cookie':auth.SESSION_COOKIE+'='+cookie,'x-csrf-token':csrf_token(principal)}
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://localhost:8200') as c:
            return await c.request(method,path,json=body,headers=headers)

    def data(response,status=200):
        check(response.status_code==status,'CF023 HTTP status')
        check(response.headers.get('cache-control')=='private, no-store','CF023 private')
        value=response.json();check(value['error'] is None and value['schema_version']=='supervisor.core.v1','CF023 success envelope')
        return value['data']

    def error(response,status,code=None):
        check(response.status_code==status,'CF023 fixed failure status')
        value=response.json();check(value['data'] is None and value['error']['message']=='Supervisor request unavailable','CF023 safe error')
        check(code is None or value['error']['code']==code,'CF023 fixed error code')

    def body(query='삼성전자 수급'):
        return dict(prepare_key=str(uuid4()),draft=dict(original_query=query,answers=[],revision=0,selected_ticker=None,candidate_ref=None),parent_preparation_id=None)

    async def prepare(value=None):
        return data(await call('POST','/api/supervisor/core/preparations',value or body()))

    def confirm(prepared,request):
        plan=prepared['plan']
        return dict(client_key=str(uuid4()),preparation_id=prepared['preparation_id'],draft=request['draft'],expected_plan_hash=plan['plan_hash'],consent=dict(allow_flow=True,allow_partial=plan['partial'],waived_conditions=plan['required_waivers']))

    original_resolve=StockResolverService.resolve
    async def resolve(self,query):
        if mode in {'ambiguous','lineage_race'} and query=='삼성전자':
            return StockResolveResponse(status='ambiguous',reason='multiple_stocks',candidates=[dict(stock_code=code,stock_name=name,market='KOSPI',match_type='ambiguous_group',matched_text='삼성전자') for code,name in [('005930','삼성전자'),('000660','SK하이닉스')]])
        return await original_resolve(self,query)

    previous=dict(app.dependency_overrides);app.dependency_overrides[get_session]=sessions
    try:
      with ExitStack() as stack:
        for name,value in dict(AI_SERVICE_URL='http://synthetic.invalid',FLOW_ANALYSIS_ENABLED=True,FLOW_SERVICE_TOKEN=token,FLOW_USAGE_LIMITS_ENABLED='true',FLOW_SUPPORTED_TICKERS='005930,000660,000720',FLOW_USER_DAILY_REQUEST_LIMIT='100',FLOW_SERVICE_DAILY_REQUEST_LIMIT='200',FLOW_SERVICE_DAILY_BUDGET_USD='200').items():
            stack.enter_context(patch.object(settings,name,value))
        stack.enter_context(patch.dict('os.environ',{'FLOW_ANALYSIS_ENABLED':'true','FLOW_SERVICE_TOKEN':token}))
        stack.enter_context(patch.object(routes,'AIClient',client))
        stack.enter_context(patch.object(analysis_router,'AIClient',client))
        stack.enter_context(patch.object(StockResolverService,'resolve',resolve))

        request=body();held.clear();release.clear();mode='claim_race'
        winner=asyncio.create_task(call('POST','/api/supervisor/core/preparations',request));tasks.append(winner)
        await asyncio.wait_for(held.wait(),5)
        loser=data(await call('POST','/api/supervisor/core/preparations',request),202)
        check(loser['state']=='pending' and len(phases)==1,'CF023 pending loser extraction0')
        release.set();first=data(await winner);mode='normal'
        check(first['preparation_id']==loser['preparation_id'] and first['state']=='ready','CF023 same preparation winner')
        n=(len(phases),len(models));check(await prepare(request)==first and (len(phases),len(models))==n,'CF023 same-key replay no model')
        error(await call('POST','/api/supervisor/core/preparations',request|{'draft':body('SK하이닉스 수급')['draft']}),409,'IDEMPOTENCY_CONFLICT')
        error(await call('GET','/api/supervisor/core/preparations/'+first['preparation_id'],identity=other),404)
        mark('prepare_claim_race_same_key_owner_and_input_fence')

        mode='root_ack';ack_seen=False;uncertain=body();target_key=hashlib.sha256(uncertain['prepare_key'].encode()).digest();n=len(phases)
        error(await call('POST','/api/supervisor/core/preparations',uncertain),503)
        check(ack_seen and len(phases)==n,'CF023 unknown admission ACK AI0')
        mode='normal';pending=data(await call('POST','/api/supervisor/core/preparations',uncertain),202)
        check(pending['state']=='pending' and len(phases)==n,'CF023 pending never reclaimed')
        mark('preparation_ACK_unknown_primary_replay_no_regeneration')

        fixed_body=confirm(first,request);mode='binding_ack';ack_seen=False;target_key=hashlib.sha256(fixed_body['client_key'].encode()).digest();n=len(dispatch)
        error(await call('POST','/api/supervisor/core/requests',fixed_body),503)
        check(ack_seen and len(dispatch)==n,'CF023 unknown binding ACK Flow0')
        mode='normal';nplan=len(phases)
        stored=data(await call('POST','/api/supervisor/core/requests',fixed_body))
        check(stored['flow']['state']=='stored' and len(phases)==nplan and len(dispatch)==n+1,'CF023 replay uses fixed binding only')
        consumed=data(await call('GET','/api/supervisor/core/preparations/'+first['preparation_id']))
        check(consumed['state']=='consumed' and consumed['plan'] is None and consumed['consumed_binding_id']==stored['supervisor_id'],'CF023 consumed winner reference')
        check(data(await call('GET','/api/supervisor/core/requests/'+stored['supervisor_id']))==stored,'CF023 GET scope preserved')
        mark('fixed_plan_adoption_ACK_recovery_and_original_Flow_storage')

        mode='ambiguous';parent_body=body();parent=await prepare(parent_body)
        check(parent['plan']['status']=='needs_stock_selection','CF023 ambiguity preserved')
        def child_body(parent_view,selected):
            return dict(prepare_key=str(uuid4()),parent_preparation_id=parent_view['preparation_id'],draft=parent_body['draft']|{'selected_ticker':selected,'candidate_ref':parent['plan']['candidate_ref']})
        nmodel=len(models)
        left_body=child_body(parent,'005930');left=await prepare(left_body)
        right_body=child_body(parent,'000660');right=await prepare(right_body)
        grand_body=child_body(left,'000660');grand=await prepare(grand_body)
        check(len(models)==nmodel and left['plan']['status']=='ready' and grand['plan']['status']=='ready','CF023 candidate children model0')
        check(await sql('SELECT count(*) FROM supervisor_meaning_preparations WHERE parent_id IS NOT NULL AND (draft_json IS NOT NULL OR frame_json IS NOT NULL OR plan_json IS NOT NULL)')==0,'CF023 child has no sensitive copies')
        mode='lineage_race'
        a=asyncio.create_task(call('POST','/api/supervisor/core/requests',confirm(left,left_body)))
        b=asyncio.create_task(call('POST','/api/supervisor/core/requests',confirm(right,right_body)))
        tasks.extend([a,b]);responses=await asyncio.gather(a,b)
        check(sorted(r.status_code for r in responses)==[200,409],'CF023 sibling single consumer')
        win=data(next(r for r in responses if r.status_code==200))['supervisor_id']
        for view in (parent,left,right,grand):
            closed=data(await call('GET','/api/supervisor/core/preparations/'+view['preparation_id']))
            check(closed['state']=='consumed' and closed['plan'] is None and closed['consumed_binding_id']==win,'CF023 all closed ancestors share winner')
        error(await call('POST','/api/supervisor/core/preparations',child_body(left,'005930')),409,'PREPARATION_CONSUMED')
        mode='normal';mark('sibling_lineage_consumption_root_only_and_model0_children')

        mode='ambiguous';pbody=body();pview=await prepare(pbody)
        cbody=dict(prepare_key=str(uuid4()),parent_preparation_id=pview['preparation_id'],draft=pbody['draft']|{'selected_ticker':'005930','candidate_ref':pview['plan']['candidate_ref']})
        cview=await prepare(cbody)
        gbody=dict(prepare_key=str(uuid4()),parent_preparation_id=cview['preparation_id'],draft=cbody['draft']|{'selected_ticker':'000660'})
        gview=await prepare(gbody)
        mode='lineage_race';responses=await asyncio.gather(call('POST','/api/supervisor/core/requests',confirm(cview,cbody)),call('POST','/api/supervisor/core/requests',confirm(gview,gbody)))
        check(sorted(r.status_code for r in responses)==[200,409],'CF023 parent-child winner once')
        mode='normal';mark('parent_child_confirm_shared_ancestor_single_winner')

        held.clear();release.clear();mode='late_delete';late_body=body();late=asyncio.create_task(call('POST','/api/supervisor/core/preparations',late_body));tasks.append(late)
        await asyncio.wait_for(held.wait(),5)
        late_id=await sql('SELECT id FROM supervisor_meaning_preparations WHERE prepare_key_digest=:key',{'key':hashlib.sha256(late_body['prepare_key'].encode()).digest()})
        gone=data(await call('DELETE','/api/supervisor/core/preparations/'+str(late_id)))
        release.set();closed=data(await late)
        check(gone['state']=='deleted' and closed['state']=='deleted' and closed['plan'] is None,'CF023 late result cannot resurrect deleted root')
        mode='normal';mark('delete_during_preparation_late_result_fence')

        # A child ID deletes the one actual sensitive root, not only its local row.
        mode='ambiguous';dbody=body();dparent=await prepare(dbody)
        dcbody=dict(prepare_key=str(uuid4()),parent_preparation_id=dparent['preparation_id'],draft=dbody['draft']|{'selected_ticker':'005930','candidate_ref':dparent['plan']['candidate_ref']})
        dchild=await prepare(dcbody)
        gone=data(await call('DELETE','/api/supervisor/core/preparations/'+dchild['preparation_id']))
        check(gone['state']=='deleted' and data(await call('GET','/api/supervisor/core/preparations/'+dparent['preparation_id']))['plan'] is None,'CF023 child DELETE redacts root')
        mode='normal'
        report=stored['flow']['report_id'];n=len(dispatch)
        check((await call('DELETE','/api/flow/reports/'+report)).status_code==204,'CF023 owned report delete')
        check(data(await call('GET','/api/supervisor/core/requests/'+stored['supervisor_id']))['coverage']=='deleted','CF023 binding redaction retained')
        check(await sql('SELECT count(*) FROM supervisor_meaning_preparations WHERE state=\'consumed\' AND (draft_json IS NOT NULL OR frame_json IS NOT NULL OR plan_json IS NOT NULL OR continuation_json IS NOT NULL)')==0 and len(dispatch)==n,'CF023 consumed source remains redacted')
        mark('child_root_redaction_and_existing_report_delete_transaction')

        # Private unit epoch: count/generation share one reservation; malformed finish cannot release it.
        async with owned_session(proof) as session:
            epoch=await repo.verifier_epoch(session);epoch_id=epoch.id;await session.commit()
        attempts=[]
        for index in range(3):
            async with owned_session(proof) as session:
                stamp=await repo.clock(session);id=uuid4();attempt=uuid4();attempts.append(str(attempt))
                await repo.admit(session,dict(id=id,owner_user_id=primary[1].user_id,prepare_key_digest=hashlib.sha256(str(id).encode()).digest(),request_digest=sha(index),draft_digest=sha(index),semantic_json=canonical(MEANING_SPEC),semantic_sha256=MEANING_SPEC_SHA256,root_id=id,parent_id=None,depth=0,attempt_id=attempt,epoch_id=epoch_id,state='pending',meaning_status='pending',draft_json=canonical(body()['draft']),created_at=stamp,expires_at=stamp+timedelta(minutes=10)))
                await session.commit()
        budget=repo.DurableMeaningBudget(lambda:owned_session(proof),epoch_id=epoch_id,owner=primary[1].user_id)
        results=await asyncio.gather(*(budget.authorize(attempts[0],'count','a'*64,'b'*64,None) for _ in range(2)))
        check(sorted(results)==[False,True],'CF023 atomic same attempt count once')
        evidence=SimpleNamespace(request_sha256='a'*64,projection_sha256='b'*64,model=MEANING_SPEC['model'],price_sha256=sha(MEANING_SPEC['price']),input_tokens=100,count_fee_bound_nano=1)
        check(await budget.authorize(attempts[0],'generation','a'*64,'b'*64,evidence),'CF023 same attempt generation')
        await budget.finish(attempts[0],dict(state='observed',reason='USAGE_OBSERVED',estimated_nano=1),blocked=False)
        check(await budget.authorize(attempts[1],'count','c'*64,'d'*64,None),'CF023 second attempt reserved')
        await budget.finish(attempts[1],dict(state='unknown',reason='USAGE_UNAVAILABLE',estimated_nano=None),blocked=False)
        restart=repo.DurableMeaningBudget(lambda:owned_session(proof),epoch_id=epoch_id,owner=primary[1].user_id)
        check(not await restart.authorize(attempts[2],'count','e'*64,'f'*64,None),'CF023 restart cannot clear hold or budget')
        check(await sql('SELECT blocked AND reserved_nano=100000000 AND count_requests=2 AND generation_requests=1 AND active_attempt_id IS NOT NULL FROM supervisor_meaning_test_epochs WHERE id=:id',{'id':epoch_id}),'CF023 epoch unknown hold totals')
        try:
            async with owned_session(proof) as session:
                await session.execute(text('UPDATE supervisor_meaning_test_epochs SET blocked=false,active_attempt_id=NULL WHERE id=:id'),{'id':epoch_id});await session.commit()
        except Exception:pass
        else:check(False,'CF023 database rejects hold reset')
        mark('durable_two_attempt_epoch_concurrency_unknown_hold_restart')

        try:await migration(proof,'c22001a7e0001',downgrade=True)
        except Exception:pass
        else:check(False,'CF023 populated downgrade forbidden')
        check(await sql('SELECT count(*) FROM auth_users')==preserved,'CF023 old rows survive failed downgrade')
        mark('populated_downgrade_refused_preserves_existing_rows')
    finally:
        release.set()
        for task in tasks:
            if not task.done():task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
        app.dependency_overrides.clear();app.dependency_overrides.update(previous)
    return dict(groups=groups,preparations=await sql('SELECT count(*) FROM supervisor_meaning_preparations'),bindings=await sql('SELECT count(*) FROM supervisor_request_bindings'),planning_HTTP_calls=len(phases),model_calls=len(models),Flow_dispatches=len(dispatch))


async def verify_meaning_impact(proof):
    """Narrow post-review TTL/DB hold regressions; does not repeat the main ten groups."""
    import asyncio
    import hashlib
    from datetime import timedelta
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, patch
    from uuid import uuid4
    from sqlalchemy import select, text
    from db.models.auth.models import AuthUser
    from db.models.supervisor.preparation import SupervisorMeaningPreparation as Preparation
    from db.models.supervisor.request_binding import SupervisorRequestBinding as Binding
    from src.modules.supervisor.application.preparation_service import PreparationService
    from src.modules.supervisor.infrastructure import preparation_repository as repo
    from src.modules.supervisor.infrastructure import repository as bindings
    from src.modules.supervisor.domain import contracts as C
    from src.modules.supervisor.domain.flow_projection import confirmed_plan,flow_body
    from scripts.cf002_interactive_login import owned_session,safe_print
    from scripts.cf003_admission_check import isolated_application,check

    with isolated_application(proof) as observed:
        load_meaning()
        planner=sys.modules['src.supervisor.application.planning.core_planner']
        models=sys.modules['src.supervisor.domain.meaning']
        draft=models.Draft(original_query='삼성전자 수급',answers=[],revision=0)
        frame=(await planner.start_v2(draft)).frame
        resolution=sys.modules['src.supervisor.domain.core_contracts'].Resolution(status='resolved',reason='exact_match',stock=dict(stock_code='005930',stock_name='삼성전자',market='KOSPI'),candidates=[])
        plan=C.Plan.model_validate(planner.continuation_v2(draft,frame,resolution).plan.model_dump(mode='json'))
        async with owned_session(proof) as session:
            owner=uuid4();session.add(AuthUser(id=owner));await session.commit()
        async def root(ttl=600,epoch=None,complete=True):
            async with owned_session(proof) as session:
                now=await repo.clock(session);id=uuid4()
                raw=C.canonical(plan.model_dump(mode='json'));raw_frame=C.canonical(frame.model_dump(mode='json'))
                stamp=now-timedelta(seconds=600-ttl)
                value=dict(id=id,owner_user_id=owner,prepare_key_digest=hashlib.sha256(str(id).encode()).digest(),request_digest='a'*64,draft_digest=C.sha(draft.model_dump(mode='json',exclude={'selected_ticker','candidate_ref'})),semantic_json=C.canonical(C.MEANING_SPEC),semantic_sha256=C.MEANING_SPEC_SHA256,root_id=id,parent_id=None,depth=0,attempt_id=uuid4(),epoch_id=epoch,state='ready' if complete else 'pending',meaning_status='deterministic' if complete else 'pending',draft_json=C.canonical(draft.model_dump(mode='json')),frame_json=raw_frame if complete else None,frame_sha256=hashlib.sha256(raw_frame.encode()).hexdigest() if complete else None,plan_json=raw if complete else None,plan_sha256=hashlib.sha256(raw.encode()).hexdigest() if complete else None,created_at=stamp,expires_at=stamp+timedelta(minutes=10))
                await repo.admit(session,value);await session.commit()
                return id,value['attempt_id']
        id,_=await root(1.5)
        slow_calls=[]
        async def slow(query):
            slow_calls.append(True)
            await asyncio.sleep(1.8)
            return resolution
        async with owned_session(proof) as session:
            service=PreparationService(session,principal=SimpleNamespace(user_id=owner),client=None,resolver_factory=lambda session:SimpleNamespace(resolve=slow))
            service.auth=AsyncMock()  # Auth is tested through HTTP in the main owned run; only the delayed resolver boundary is replaced here.
            confirm=C.Confirm(client_key=str(uuid4()),draft=C.Draft.model_validate(draft.model_dump(mode='json')),expected_plan_hash=plan.plan_hash,consent=C.Consent(allow_flow=True,allow_partial=False,waived_conditions=[]),preparation_id=str(id))
            try:await service.adopt(confirm,'a'*64,b'k'*32)
            except repo.PreparationConflict as error:check(error.code=='PREPARATION_EXPIRED','CF023 delayed resolver expiration')
            else:check(False,'CF023 expired resolver must refuse adoption')
            await session.rollback()
        check(slow_calls==[True],'CF023 delayed resolver actually entered before expiry')
        safe_print({'phase':'cf023_impact','label':'delayed_resolver_DB_clock_recheck','status':'passed'})

        id,_=await root(1.5)
        binding_id=uuid4()
        async with owned_session(proof) as session:
            rows=await repo.lineage(session,owner,id)
            stamp=await repo.clock(session)
            check(stamp<rows[-1].expires_at,'CF023 binding insert begins before expiry')
            raw_plan=C.canonical(confirmed_plan(plan,C.Consent(allow_flow=True,allow_partial=False,waived_conditions=[])))
            raw_flow=C.canonical(flow_body(plan,binding_id,stamp))
            await bindings.admit(session,dict(id=binding_id,owner_user_id=owner,client_key_digest=b'z'*32,confirm_digest='b'*64,preparation_id=id,plan_json=raw_plan,plan_sha256=hashlib.sha256(raw_plan.encode()).hexdigest(),flow_input_json=raw_flow,flow_sha256=hashlib.sha256(raw_flow.encode()).hexdigest(),flow_key_digest=hashlib.sha256(str(binding_id).encode()).digest(),confirmed_at=stamp,handoff_before=stamp+timedelta(seconds=120)))
            await asyncio.sleep(1.8)
            try:
                # Direct SQL bypasses the service recheck: the DB itself must reject late consumption.
                await session.execute(text("UPDATE supervisor_meaning_preparations SET state='consumed',meaning_status='consumed',consumed_binding_id=:binding,draft_json=NULL,frame_json=NULL,plan_json=NULL,continuation_json=NULL,redacted_at=clock_timestamp() WHERE id=:id"),{'binding':binding_id,'id':id})
                await session.commit()
            except Exception as error:
                check(getattr(getattr(error,'orig',None),'sqlstate',None)=='23514','CF023 exact late consumption constraint')
                await session.rollback()
            else:check(False,'CF023 DB consumption deadline cannot be bypassed')
        async with owned_session(proof) as session:
            check(await session.scalar(select(Binding.id).where(Binding.id==binding_id)) is None,'CF023 late binding rolled back atomically')
        safe_print({'phase':'cf023_impact','label':'late_consumption_DB_guard_rolls_back_new_binding','status':'passed'})

        async with owned_session(proof) as session:
            epoch=await repo.verifier_epoch(session);epoch_id=epoch.id;await session.commit()
        _,attempt=await root(epoch=epoch_id,complete=False)
        budget=repo.DurableMeaningBudget(lambda:owned_session(proof),epoch_id=epoch_id,owner=owner)
        check(await budget.authorize(str(attempt),'count','a'*64,'b'*64,None),'CF023 impact reservation')
        async with owned_session(proof) as session:
            try:
                await session.execute(text("UPDATE supervisor_meaning_test_epochs SET active_attempt_id=NULL,attempts_json=jsonb_set(attempts_json,ARRAY[:attempt,'observation'],CAST(:observation AS jsonb)) WHERE id=:id"),{'attempt':str(attempt),'observation':'{"state":"unknown","reason":"FIXED","estimated_nano":null}','id':epoch_id})
                await session.commit()
            except Exception as error:
                check(getattr(getattr(error,'orig',None),'sqlstate',None)=='23514','CF023 exact unknown hold constraint')
                await session.rollback()
            else:check(False,'CF023 unknown false block tuple rejected in DB')
        await budget.finish(str(attempt),dict(state='unknown',reason='FIXED',estimated_nano=None),blocked=False)
        async with owned_session(proof) as session:
            row=await session.scalar(text('SELECT blocked AND active_attempt_id=:attempt AND reserved_nano=50000000 FROM supervisor_meaning_test_epochs WHERE id=:id'),{'attempt':attempt,'id':epoch_id})
            check(row,'CF023 service forces uncertain hold')
        check(not any(observed.values()),'CF023 impact forbidden access')
        safe_print({'phase':'cf023_impact','label':'unknown_finish_DB_and_service_hold','status':'passed'})
        return dict(groups=['delayed_resolver_DB_clock_recheck','late_consumption_DB_guard_rolls_back_new_binding','unknown_finish_DB_and_service_hold'],observed_denials=dict(observed))
