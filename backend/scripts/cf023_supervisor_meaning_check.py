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


async def verify_live(*, proof=None, binding=None, principal=None, prepare_body=None,
                      authority=None, counter_agreement=None, key_supplier=None):
    """Private trusted orchestration only; no default approval, key loader or epoch creation."""
    if any(value is None for value in (proof, binding, principal, prepare_body, authority, counter_agreement, key_supplier)):
        load_meaning()
        from src.supervisor.infrastructure.meaning_gateway import CounterUnavailable
        raise CounterUnavailable()
    return await run_meaning_assembly(mode='live', proof=proof, binding=binding,
        principal=principal, prepare_body=prepare_body, authority=authority,
        counter_agreement=counter_agreement, key_supplier=key_supplier)


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


# CF024 private assembly. No production router, configuration or public budget API is modified.
from dataclasses import dataclass, field
from datetime import datetime, timezone
from contextlib import asynccontextmanager, contextmanager

SYNTHETIC_MAPPING_SHA = 'f' * 64


def assembly_error():
    from src.supervisor.infrastructure.meaning_gateway import CounterUnavailable
    return CounterUnavailable()


@dataclass(frozen=True, repr=False)
class OwnedEpochBinding:
    """External live caller supplies original object identities, not a receipt JSON/URL."""
    proof: object = field(repr=False)
    receipt: object = field(repr=False)
    epoch_id: object
    epoch_created_at: object
    epoch_state_sha256: str
    mode: str

    def __repr__(self):
        return '<OwnedEpochBinding private identity>'


def epoch_state(row):
    return dict(id=str(row.id), created_at=row.created_at.isoformat(), unit=row.unit_id,
        semantic=row.semantic_sha256, price=row.price_sha256, max_nano=row.max_nano,
        attempt_reserve=row.attempt_reserve_nano, max_attempts=row.max_attempts,
        reserved=row.reserved_nano, count=row.count_requests, generation=row.generation_requests,
        blocked=row.blocked, active=str(row.active_attempt_id) if row.active_attempt_id else None,
        attempts=row.attempts_json)


def proof_identity(proof, binding, mode):
    from scripts.runner_owned_database import RunnerOwnedDatabase, CreationReceipt
    if type(proof) is not RunnerOwnedDatabase or type(binding) is not OwnedEpochBinding or binding.mode != mode or binding.proof is not proof:
        raise assembly_error()
    if type(binding.receipt) is not CreationReceipt or proof._owner.receipt is not binding.receipt:
        raise assembly_error()
    proof.verify_ownership()


@contextmanager
def bounded_owned_calls(proof, deadline):
    """Only tighten the same verified Docker driver's existing per-call timeout."""
    import asyncio
    driver=proof._owner.docker
    original=driver.call
    def bounded(*args, **kwargs):
        remaining=deadline()-asyncio.get_running_loop().time()
        if remaining<=0:
            raise TimeoutError('Meaning verification deadline exceeded')
        kwargs['timeout']=min(kwargs.get('timeout',15),remaining)
        return original(*args,**kwargs)
    driver.call=bounded
    try:
        yield
    finally:
        driver.call=original


async def existing_epoch(session, binding, *, initial=False, phase=None):
    from sqlalchemy import select
    from db.models.supervisor.preparation import SupervisorMeaningEpoch as Epoch
    from src.modules.supervisor.domain.contracts import MEANING_SPEC, MEANING_SPEC_SHA256, sha
    row=await session.scalar(select(Epoch).where(Epoch.id==binding.epoch_id).execution_options(populate_existing=True))
    if row is None or row.created_at!=binding.epoch_created_at or row.unit_id!='CF023' or row.currency!='USD' or row.semantic_sha256!=MEANING_SPEC_SHA256 or row.price_sha256!=sha(MEANING_SPEC['price']) or (row.max_nano,row.attempt_reserve_nano,row.max_attempts)!=(100000000,50000000,2):
        raise assembly_error()
    if initial and binding.mode=='live' and sha(epoch_state(row))!=binding.epoch_state_sha256:
        raise assembly_error()
    if row.blocked or row.count_requests>=2 and phase!='generation' or row.reserved_nano>100000000 or row.reserved_nano!=row.count_requests*50000000 or not 0<=row.generation_requests<=row.count_requests<=2:
        raise assembly_error()
    return row


async def capture_synthetic_epoch(proof, principal):
    """Only a new disposable synthetic DB may call the inserting CF023 helper."""
    from scripts.cf002_interactive_login import owned_session
    from src.modules.auth.application.session_service import validate_principal
    from src.modules.supervisor.infrastructure.preparation_repository import verifier_epoch
    from src.modules.supervisor.domain.contracts import sha
    async with owned_session(proof) as session:
        await validate_principal(session, principal, lock=True)
        row=await verifier_epoch(session)
        binding=OwnedEpochBinding(proof,proof._owner.receipt,row.id,row.created_at,sha(epoch_state(row)),'synthetic')
        await session.commit()
        return binding


@dataclass(frozen=True, repr=False)
class DeferredKeySource:
    """Private identity capability, never a source loader or a serialized approval."""
    supplier: object = field(repr=False)
    source_capability: object = field(repr=False)

    async def __call__(self):
        return await self.supplier()

    def __repr__(self):
        return '<DeferredKeySource private identity>'


class SyntheticAuthority:
    """Explicit simulation, rejected by the live factory. Never an approval issuer."""
    def __init__(self, expires_at, key_source):
        self.expires_at=expires_at
        self.key_source=key_source

    async def verify(self, **scope):
        if scope['mode']!='synthetic' or scope['agreement'].documentation_sha256!=SYNTHETIC_MAPPING_SHA or scope['key_supplier'] is not self.key_source or scope['key_source_capability'] is not self.key_source.source_capability:
            raise assembly_error()
        return self.expires_at


class PhaseBudget:
    """Fresh proof + principal + exact preparation scope in the durable delegate's session."""
    def __init__(self, *, proof, binding, principal, body, authority, agreement, key_source, deadline, stages):
        self.proof,self.binding,self.principal=proof,binding,principal
        self.body,self.authority,self.agreement=body,authority,agreement
        self.key_source=key_source
        self.deadline,self.stages=deadline,stages
        self.settlement_deadline=deadline
        self.attempt=None
        self.preparation=None
        self.request_hash=self.projection_hash=None
        self.phases=[]
        self.busy=False
        self.uncertain=False

    async def lease(self, phase):
        import asyncio
        from src.modules.supervisor.domain.contracts import sha, MEANING_SPEC_SHA256
        if asyncio.get_running_loop().time()>=self.deadline:
            raise assembly_error()
        expires=await self.authority.verify(mode=self.binding.mode, phase=phase,
            proof_binding=self.binding, principal=self.principal,
            draft_sha256=sha(self.body.draft.model_dump(mode='json')),
            semantic_sha256=MEANING_SPEC_SHA256, request_sha256=self.request_hash,
            projection_sha256=self.projection_hash, agreement=self.agreement,
            key_supplier=self.key_source, key_source_capability=self.key_source.source_capability)
        if type(expires) is not datetime or expires.tzinfo is None:
            raise assembly_error()
        remaining=(expires-datetime.now(timezone.utc)).total_seconds()
        approved_until=asyncio.get_running_loop().time()+remaining
        self.deadline=min(self.deadline,approved_until)
        self.settlement_deadline=min(self.settlement_deadline,approved_until)
        if remaining<=0:
            raise assembly_error()
        return self.deadline

    async def validate_preparation(self, session, attempt, *, lock=False):
        import hashlib
        from uuid import UUID
        from sqlalchemy import select
        from db.models.supervisor.preparation import SupervisorMeaningPreparation as Preparation
        from src.modules.auth.application.session_service import validate_principal
        from src.modules.supervisor.domain.contracts import canonical,sha,MEANING_SPEC,MEANING_SPEC_SHA256
        from src.modules.supervisor.application.preparation_service import draft_identity
        from src.modules.supervisor.infrastructure.preparation_repository import clock
        await validate_principal(session,self.principal,lock=True)
        statement=select(Preparation).where(Preparation.attempt_id==UUID(attempt),Preparation.owner_user_id==self.principal.user_id).execution_options(populate_existing=True)
        if lock:statement=statement.with_for_update()
        row=await session.scalar(statement)
        now=await clock(session)
        if row is None or row.owner_user_id!=self.principal.user_id or row.attempt_id!=UUID(attempt) or row.epoch_id!=self.binding.epoch_id or row.parent_id is not None or row.root_id!=row.id or row.state!='pending' or row.redacted_at is not None or row.expires_at<=now or row.semantic_sha256!=MEANING_SPEC_SHA256 or row.semantic_json!=canonical(MEANING_SPEC) or row.prepare_key_digest!=hashlib.sha256(self.body.prepare_key.encode()).digest() or row.request_digest!=sha(self.body.model_dump(mode='json')) or row.draft_digest!=sha(draft_identity(self.body.draft)) or row.draft_json!=canonical(self.body.draft.model_dump(mode='json')):
            raise assembly_error()
        if self.preparation is not None and self.preparation!=row.id or self.attempt is not None and self.attempt!=attempt:
            raise assembly_error()
        self.preparation,self.attempt=row.id,attempt
        return row

    async def preflight(self, draft, attempt, request_hash, projection_hash, *, deadline):
        from scripts.cf002_interactive_login import owned_session
        from src.modules.supervisor.domain.contracts import canonical
        if canonical(draft.model_dump(mode='json'))!=canonical(self.body.draft.model_dump(mode='json')):
            raise assembly_error()
        from src.supervisor.infrastructure.openai_meaning_gateway import rendered_request,INPUT_FIELDS
        from src.modules.supervisor.domain.contracts import sha
        rendered=rendered_request(draft)
        if (request_hash,projection_hash)!=(sha(rendered),sha({key:rendered[key] for key in INPUT_FIELDS})):
            raise assembly_error()
        self.request_hash,self.projection_hash=request_hash,projection_hash
        self.deadline=min(self.deadline,deadline)
        await self.lease('preflight')
        with bounded_owned_calls(self.proof,lambda:self.deadline):
            proof_identity(self.proof,self.binding,self.binding.mode)
            async with owned_session(self.proof) as session:
                await self.validate_preparation(session,attempt)
                await existing_epoch(session,self.binding)
                await session.commit()
        self.stages.append('claim_ACK_identity_verified')
        return self.deadline

    @asynccontextmanager
    async def phase_session(self, attempt, phase):
        from scripts.cf002_interactive_login import owned_session
        import asyncio
        with bounded_owned_calls(self.proof,lambda:self.deadline):
            async with asyncio.timeout_at(self.deadline):
                proof_identity(self.proof,self.binding,self.binding.mode)
                async with owned_session(self.proof) as session:
                    await self.validate_preparation(session,attempt,lock=True)
                    # These reads and durable authorize share this same actual session/connection.
                    await existing_epoch(session,self.binding,phase=phase)
                    yield session

    async def authorize(self, attempt, phase, request_hash, projection_hash, evidence):
        from src.modules.supervisor.infrastructure.preparation_repository import DurableMeaningBudget
        if self.uncertain or self.busy or self.attempt!=attempt or (request_hash,projection_hash)!=(self.request_hash,self.projection_hash) or phase not in {'count','generation'} or self.phases!=([] if phase=='count' else ['count']):
            return False
        self.busy=True
        try:
            await self.lease(phase)
            delegate=DurableMeaningBudget(lambda:self.phase_session(attempt,phase),epoch_id=self.binding.epoch_id,owner=self.principal.user_id)
            accepted=await delegate.authorize(attempt,phase,request_hash,projection_hash,evidence)
            if accepted is True:
                self.phases.append(phase)
                self.stages.append(phase+'_reservation_ACK')
            return accepted
        except BaseException:
            self.uncertain=True
            raise
        finally:
            self.busy=False

    async def finish(self, attempt, observation, *, blocked):
        import asyncio
        from scripts.cf002_interactive_login import owned_session
        from src.modules.supervisor.infrastructure.preparation_repository import DurableMeaningBudget
        task=asyncio.current_task()
        if task is not None and task.cancelling():
            self.uncertain=True
            raise asyncio.CancelledError()
        deadline=min(self.settlement_deadline,asyncio.get_running_loop().time()+5)
        if attempt!=self.attempt or asyncio.get_running_loop().time()>=deadline:
            self.uncertain=True
            raise assembly_error()
        delegate=DurableMeaningBudget(lambda:owned_session(self.proof),epoch_id=self.binding.epoch_id,owner=self.principal.user_id)
        try:
            with bounded_owned_calls(self.proof,lambda:deadline):
                proof_identity(self.proof,self.binding,self.binding.mode)
                async with asyncio.timeout_at(deadline):
                    await delegate.finish(attempt,observation,blocked=blocked)
        except BaseException:
            self.uncertain=True
            raise
        self.stages.append('hold_ACK' if blocked else 'settlement_ACK')


def synthetic_provider(scenario, stages):
    """Exactly the reviewed transport/credential, no caller supplied network transport."""
    import httpx
    from src.supervisor.infrastructure.openai_meaning_gateway import COUNT_PATH,GENERATE_PATH,ORIGIN
    from src.supervisor.domain.meaning import decode,canonical
    from src.supervisor.domain.meaning_proposals import MODEL
    async def send(request):
        if str(request.url) not in {ORIGIN+COUNT_PATH,ORIGIN+GENERATE_PATH} or request.method!='POST' or request.headers.get('authorization')!='Bearer cf024-synthetic-key-only':
            raise assembly_error()
        value=decode(request.content)
        if request.url.path==COUNT_PATH:
            stages.append('mock_count')
            if {'max_output_tokens','store','stream','service_tier'}&value.keys():raise assembly_error()
            return httpx.Response(200,json={'object':'response.input_tokens','input_tokens':100})
        stages.append('mock_generation')
        candidate={'schema_version':'supervisor.meaning.v1','mentions':[{'evidence':{'source_kind':'original_query','answer_id':None,'start':0,'end':4,'text':'현대건설'},'negation':None}],'views':[],'conditions':[]}
        usage={'input_tokens':100,'output_tokens':10,'total_tokens':110,'input_tokens_details':{'cached_tokens':0}} if scenario=='success' else None
        return httpx.Response(200,json={'model':MODEL,'service_tier':'default','status':'completed','error':None,'usage':usage,'output':[{'type':'message','role':'assistant','status':'completed','content':[{'type':'output_text','text':canonical(candidate)}]}]})
    return httpx.MockTransport(send)


async def _run_meaning_assembly(*, mode, proof, binding, principal, prepare_body, deadline,
                               authority=None, counter_agreement=None, key_supplier=None,
                               transport=None, scenario='success'):
    """Private verifier only. Actual preparation/service/HTTP/gateway and durable accounting."""
    import asyncio
    import httpx
    import os
    from datetime import timedelta
    from unittest.mock import patch
    from uuid import uuid4
    from scripts.cf002_interactive_login import owned_session
    from src.modules.auth.application.session_service import Principal,validate_principal
    from src.modules.supervisor.domain.contracts import PreparationRequest,MEANING_SPEC_SHA256
    from src.modules.supervisor.application.preparation_service import PreparationService
    from src.shared.infrastructure.clients.ai_client import AIClient
    load_meaning()
    from src.supervisor.infrastructure.openai_meaning_gateway import OpenAIMeaningGateway,CounterAgreement,COUNT_DOCUMENTATION,INPUT_FIELDS
    if mode not in {'synthetic','live'} or type(principal) is not Principal:
        raise assembly_error()
    body=PreparationRequest.model_validate(prepare_body)
    if body.parent_preparation_id is not None:
        raise assembly_error()
    proof_identity(proof,binding,mode)
    stages=[]
    if mode=='synthetic':
        if any(value is not None for value in (authority,counter_agreement,key_supplier,transport)) or scenario not in {'success','missing_usage'} or body.draft.original_query!='현대건설 수급' or body.draft.answers:
            raise assembly_error()
        counter_agreement=CounterAgreement(COUNT_DOCUMENTATION,SYNTHETIC_MAPPING_SHA,INPUT_FIELDS,1)
        transport=synthetic_provider(scenario,stages)
        async def synthetic_key():
            stages.append('synthetic_key_supplied')
            return 'cf024-synthetic-key-only'
        key_supplier=DeferredKeySource(synthetic_key,object())
        authority=SyntheticAuthority(datetime.now(timezone.utc)+timedelta(seconds=60),key_supplier)
    else:
        # A syntactic CounterAgreement is not authorization. A trusted external authority must
        # audit exact mapping/fee/key/data scope at action time; no implementation is supplied here.
        if authority is None or isinstance(authority,SyntheticAuthority) or not callable(getattr(authority,'verify',None)) or type(counter_agreement) is not CounterAgreement or counter_agreement.documentation_sha256==SYNTHETIC_MAPPING_SHA or type(key_supplier) is not DeferredKeySource or not callable(key_supplier.supplier) or key_supplier.source_capability is None or transport is not None:
            raise assembly_error()
    counter_agreement.validate()
    budget=PhaseBudget(proof=proof,binding=binding,principal=principal,body=body,authority=authority,agreement=counter_agreement,key_source=key_supplier,deadline=deadline,stages=stages)
    async with asyncio.timeout_at(deadline):
        deadline=await budget.lease('initial')
        async with asyncio.timeout_at(deadline):
            # SELECT-only live initialization. No verifier_epoch or replacement resource fallback.
            async with owned_session(proof) as session:
                await validate_principal(session,principal,lock=True)
                await existing_epoch(session,binding,initial=True)
                await session.commit()
            stages.append('preflight_verified')
            gateway=OpenAIMeaningGateway(key_supplier=key_supplier,budget=budget,counter_agreement=counter_agreement,transport=transport,preflight=budget.preflight,deadline=deadline)
            app=load_meaning(gateway=gateway)
            token='cf024-asgi-synthetic-service-token-at-least32'
            client=AIClient('http://synthetic.invalid',8,transport=httpx.ASGITransport(app=app),service_token=token)
            with patch.dict(os.environ,{'FLOW_ANALYSIS_ENABLED':'true','FLOW_SERVICE_TOKEN':token}):
                async with owned_session(proof) as session:
                    result=await PreparationService(session,principal=principal,client=client,epoch_id=binding.epoch_id).post(body,uuid4())
            if gateway.settlement_uncertain or budget.uncertain:
                return {'state':'unknown','meaning_status':'unavailable','stages':stages,'settlement':'unconfirmed','gateway_diagnostic':gateway.diagnostic(),'real_provider_requests':0 if mode=='synthetic' else None}
            # Read back through the real owner-aware service; no model/key on observation.
            before=len(stages)
            async with owned_session(proof) as session:
                stored=await PreparationService(session,principal=principal,client=client,epoch_id=binding.epoch_id).get(__import__('uuid').UUID(result['preparation_id']))
            if result!=stored or len(stages)!=before:
                raise assembly_error()
            stages.append('preparation_owner_readback')
            return {'state':result['state'],'meaning_status':result['meaning_status'],'plan_hash':result['plan']['plan_hash'] if result['plan'] else None,'stages':stages,'settlement':'hold' if gateway.block_confirmed else 'observed' if 'settlement_ACK' in stages else 'not_called','gateway_diagnostic':gateway.diagnostic(),'semantic_sha256':MEANING_SPEC_SHA256,'real_provider_requests':0 if mode=='synthetic' else None}


import weakref
_ASSEMBLY_LOCKS=weakref.WeakKeyDictionary()


async def run_meaning_assembly(**scope):
    """One bounded verifier per actual owned Docker driver; shared proofs cannot race timeout restoration."""
    import asyncio
    from scripts.runner_owned_database import RunnerOwnedDatabase
    deadline=asyncio.get_running_loop().time()+60
    proof=scope.get('proof')
    if type(proof) is not RunnerOwnedDatabase:
        raise assembly_error()
    lock=_ASSEMBLY_LOCKS.setdefault(proof._owner.docker,asyncio.Lock())
    async with asyncio.timeout_at(deadline):
        async with lock:
            with bounded_owned_calls(proof,lambda:deadline):
                return await _run_meaning_assembly(**scope,deadline=deadline)


async def _verify_meaning_assembly(proof):
    """One owned epoch: one success, one unknown, then replay/restart blocked. No Flow."""
    import asyncio
    from uuid import uuid4
    from sqlalchemy import select
    from db.models.auth.models import AuthUser
    from db.models.common.stock import Stock
    from db.models.supervisor.preparation import SupervisorMeaningEpoch as Epoch
    from src.modules.auth.application.session_service import issue_session
    from scripts.cf002_interactive_login import owned_session,safe_print
    from scripts.cf003_admission_check import isolated_application,check
    with isolated_application(proof) as observed:
        load_meaning()
        async with owned_session(proof) as session:
            user=AuthUser(id=uuid4());session.add(user)
            session.add(Stock(stock_code='000720',stock_name='현대건설',market='KOSPI'))
            await session.flush()
            _,principal=await issue_session(session,user)
            await session.commit()
        binding=await capture_synthetic_epoch(proof,principal)
        def request():
            return {'prepare_key':str(uuid4()),'parent_preparation_id':None,'draft':{'original_query':'현대건설 수급','answers':[],'revision':0,'selected_ticker':None,'candidate_ref':None}}
        first_body=request()
        first=await run_meaning_assembly(mode='synthetic',proof=proof,binding=binding,principal=principal,prepare_body=first_body)
        check(first['state']=='ready' and first['meaning_status']=='supplemented' and first['settlement']=='observed','CF024 actual successful assembly')
        check(first['stages']==['preflight_verified','claim_ACK_identity_verified','count_reservation_ACK','synthetic_key_supplied','mock_count','generation_reservation_ACK','mock_generation','settlement_ACK','preparation_owner_readback'],'CF024 exact assembly stage order')
        safe_print({'phase':'cf024_assembly','label':'owner_claim_budget_supplier_ASGI_candidate_readback','status':'passed','stages':first['stages']})
        replay=await run_meaning_assembly(mode='synthetic',proof=proof,binding=binding,principal=principal,prepare_body=first_body)
        check(replay['plan_hash']==first['plan_hash'] and replay['stages']==['preflight_verified','preparation_owner_readback'],'CF024 same-key model/key/send0 replay')
        safe_print({'phase':'cf024_assembly','label':'same_preparation_replay_no_supplier_or_provider','status':'passed'})
        last=await run_meaning_assembly(mode='synthetic',proof=proof,binding=binding,principal=principal,prepare_body=request(),scenario='missing_usage')
        check(last['state']=='clarification' and last['settlement']=='hold' and last['stages'].count('synthetic_key_supplied')==1 and 'hold_ACK' in last['stages'],'CF024 last unknown holds')
        async with owned_session(proof) as session:
            epoch=await session.scalar(select(Epoch).where(Epoch.id==binding.epoch_id))
            check(epoch.count_requests==2 and epoch.generation_requests==2 and epoch.reserved_nano==100000000 and epoch.blocked and epoch.active_attempt_id is not None and len(epoch.attempts_json)==2,'CF024 one epoch two maximum reservations')
            states=sorted(value['observation']['state'] for value in epoch.attempts_json.values())
            check(states==['observed','unknown'],'CF024 success then unknown only')
            estimate=next(value['observation']['estimated_nano'] for value in epoch.attempts_json.values() if value['observation']['state']=='observed')
            check(estimate==120000,'CF024 synthetic observation estimate')
        safe_print({'phase':'cf024_assembly','label':'same_epoch_last_unknown_durable_hold','status':'passed'})
        for value in (first_body,request()):
            try:
                await run_meaning_assembly(mode='synthetic',proof=proof,binding=binding,principal=principal,prepare_body=value)
            except sys.modules['src.supervisor.infrastructure.meaning_gateway'].CounterUnavailable:
                pass
            else:check(False,'CF024 blocked epoch cannot restart verifier sends')
        async with owned_session(proof) as session:
            epoch=await session.scalar(select(Epoch).where(Epoch.id==binding.epoch_id))
            check(epoch.count_requests==2 and epoch.generation_requests==2 and epoch.reserved_nano==100000000 and len(epoch.attempts_json)==2,'CF024 no reset on restart')
        check(not any(observed.values()),'CF024 forbidden accesses')
        safe_print({'phase':'cf024_assembly','label':'blocked_replay_restart_preserves_original_epoch','status':'passed'})
        return {'groups':4,'count_requests':2,'generation_requests':2,'reservations':2,'reserved_nano':100000000,'synthetic_estimated_nano':estimate,'real_provider_requests':0,'observed_denials':dict(observed),'note':'Other ACK/cancellation combinations are callback simulations, not additional PG epochs.'}


async def verify_meaning_assembly(proof):
    try:
        return await _verify_meaning_assembly(proof)
    except BaseException as error:
        from scripts.cf002_interactive_login import safe_print
        frames=[];tb=error.__traceback__
        while tb:
            if tb.tb_frame.f_code.co_filename==__file__:
                frames.append({'source':'meaning_assembly_checker','function':tb.tb_frame.f_code.co_name,'line':tb.tb_lineno})
            tb=tb.tb_next
        safe_print({'phase':'cf024_assembly_failure','frames':frames[-8:]})
        raise


async def verify_meaning_flow_crosspath(proof):
    """Fixed synthetic-only owned-PG preparation -> authenticated adoption -> fake Flow.

    This separate entry leaves CF024's No Flow result and live factory unchanged.
    No caller-selected mode, key, transport, approval or ledger is accepted.
    """
    from scripts.runner_owned_database import RunnerOwnedDatabase
    if type(proof) is not RunnerOwnedDatabase:
        raise assembly_error()
    proof.verify_ownership()
    from scripts.cf003_admission_check import isolated_application, check
    from scripts.cf002_interactive_login import safe_print
    try:
        with isolated_application(proof) as observed:
            result = await _verify_meaning_flow_crosspath(proof)
            check(not any(observed.values()), 'CF029 forbidden access')
            return result | {'observed_denials': dict(observed)}
    except BaseException as error:
        frames=[];tb=error.__traceback__
        while tb:
            if tb.tb_frame.f_code.co_filename==__file__:
                frames.append({'source':'meaning_flow_checker','function':tb.tb_frame.f_code.co_name,'line':tb.tb_lineno})
            tb=tb.tb_next
        safe_print({'phase':'cf029_crosspath_failure','frames':frames[-8:]})
        raise


async def _verify_meaning_flow_crosspath(proof):
    import copy
    from contextlib import ExitStack
    from unittest.mock import patch
    from uuid import uuid4
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
    from src.modules.supervisor.domain.contracts import canonical, sha, MEANING_SPEC, MEANING_SPEC_SHA256, validate_plan, Draft
    from src.modules.flow.api.schemas import FlowReportEnvelope
    from scripts.cf002_interactive_login import owned_session, safe_print
    from scripts.cf003_admission_check import check
    from scripts.cf012_analysis_check import flow_app, engine_result

    load_meaning()
    groups=[];dispatch=[];stages=[];snapshots={}
    token='cf029-fake-flow-service-token-at-least32'
    tables=('flow_analysis_runs','analysis_usage_reservations','flow_reports','analysis_provider_calls','analysis_usage_periods')

    def mark(label):
        groups.append(label)
        safe_print({'phase':'cf029_crosspath','label':label,'status':'passed'})

    async def sql(query, params=None):
        async with owned_session(proof) as session:
            return await session.scalar(text(query), params or {})

    async def totals():
        return {table: await sql('SELECT count(*) FROM '+table) for table in tables}

    async def epoch_snapshot():
        async with owned_session(proof) as session:
            row=await session.scalar(select(Epoch).where(Epoch.id==binding.epoch_id))
            return copy.deepcopy(epoch_state(row))

    async def unchanged(expected):
        check(await epoch_snapshot()==held_snapshot,'CF029 meaning unknown hold unchanged')
        check(await totals()==expected,'CF029 Flow counters unchanged')
        check(sum(s.count('mock_count') for s in stages)==2 and sum(s.count('mock_generation') for s in stages)==2 and sum(s.count('synthetic_key_supplied') for s in stages)==2,'CF029 meaning sends unchanged')

    async def user():
        async with owned_session(proof) as session:
            value=AuthUser(id=uuid4());session.add(value);await session.flush()
            cookie,principal=await issue_session(session,value)
            await session.commit()
            return cookie,principal

    primary,other=await user(),await user()
    async with owned_session(proof) as session:
        session.add(Stock(stock_code='000720',stock_name='현대건설',market='KOSPI'))
        await session.commit()
    check(await sql('SELECT count(*) FROM supervisor_meaning_test_epochs')==0,'CF029 new disposable epoch required')
    check(await sql('SELECT count(*) FROM supervisor_meaning_preparations')==0,'CF029 empty preparations required')
    before=await totals();check(not any(before.values()),'CF029 fresh Flow tables')
    binding=await capture_synthetic_epoch(proof,primary[1])
    def request():
        return dict(prepare_key=str(uuid4()),parent_preparation_id=None,draft=dict(original_query='현대건설 수급',answers=[],revision=0,selected_ticker=None,candidate_ref=None))
    first_body=request();last_body=request()
    first=await run_meaning_assembly(mode='synthetic',proof=proof,binding=binding,principal=primary[1],prepare_body=first_body)
    stages.append(list(first['stages']))
    check(first['state']=='ready' and first['meaning_status']=='supplemented' and first['settlement']=='observed','CF029 actual supplemented ready assembly')
    check(first['stages']==['preflight_verified','claim_ACK_identity_verified','count_reservation_ACK','synthetic_key_supplied','mock_count','generation_reservation_ACK','mock_generation','settlement_ACK','preparation_owner_readback'],'CF029 exact ready stage order')
    snapshots['ready']=await epoch_snapshot()
    check(snapshots['ready']['count']==snapshots['ready']['generation']==1 and snapshots['ready']['reserved']==50000000 and not snapshots['ready']['blocked'] and snapshots['ready']['active'] is None,'CF029 first observed accounting')
    check(await totals()==before and not dispatch,'CF029 ready No Flow')
    async with owned_session(proof) as session:
        first_row=(await session.scalars(select(Preparation).where(Preparation.owner_user_id==primary[1].user_id,Preparation.prepare_key_digest==hashlib.sha256(first_body['prepare_key'].encode()).digest()))).one()
        first_id=str(first_row.id)
    async def early_sessions():
        async with owned_session(proof) as session:
            yield session
    early_overrides=dict(app.dependency_overrides);app.dependency_overrides[get_session]=early_sessions
    try:
        with patch.object(settings,'FLOW_ANALYSIS_ENABLED',True),patch.object(settings,'FLOW_SERVICE_TOKEN',token),patch.dict('os.environ',{'FLOW_ANALYSIS_ENABLED':'true','FLOW_SERVICE_TOKEN':token}):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://localhost:8200') as c:
                early=await c.get('/api/supervisor/core/preparations/'+first_id,headers={'cookie':auth.SESSION_COOKIE+'='+primary[0]})
        check(early.status_code==200 and early.headers.get('cache-control')=='private, no-store','CF029 ready owner ASGI GET before unknown')
        early_view=early.json()['data']
        check(early_view['state']=='ready' and early_view['meaning_status']=='supplemented' and early_view['plan']['plan_hash']==first['plan_hash'],'CF029 ready owner plan before unknown')
    finally:
        app.dependency_overrides.clear();app.dependency_overrides.update(early_overrides)
    check(await epoch_snapshot()==snapshots['ready'] and await totals()==before,'CF029 first owner GET no meaning or Flow accounting')
    last=await run_meaning_assembly(mode='synthetic',proof=proof,binding=binding,principal=other[1],prepare_body=last_body,scenario='missing_usage')
    stages.append(list(last['stages']))
    check(last['state']=='clarification' and last['settlement']=='hold' and 'hold_ACK' in last['stages'],'CF029 last unknown clarification')
    held_snapshot=await epoch_snapshot();snapshots['unknown']=held_snapshot
    check(held_snapshot['count']==held_snapshot['generation']==2 and held_snapshot['reserved']==100000000 and held_snapshot['blocked'] and held_snapshot['active'] is not None and len(held_snapshot['attempts'])==2,'CF029 same epoch unknown durable hold')
    observations=[v['observation'] for v in held_snapshot['attempts'].values()]
    check(sorted(v['state'] for v in observations)==['observed','unknown'] and next(v['estimated_nano'] for v in observations if v['state']=='observed')==120000,'CF029 observed estimate distinct from unknown')
    async with owned_session(proof) as session:
        last_row=(await session.scalars(select(Preparation).where(Preparation.owner_user_id==other[1].user_id,Preparation.prepare_key_digest==hashlib.sha256(last_body['prepare_key'].encode()).digest()))).one()
        check(last_row.epoch_id==binding.epoch_id and last_row.state=='clarification' and str(last_row.attempt_id)==held_snapshot['active'] and held_snapshot['attempts'][str(last_row.attempt_id)]['observation']['state']=='unknown','CF029 exact second owner unknown active attempt')
    mark('same_epoch_actual_supplemented_ready_then_unknown_hold')

    # Resolve only the actual owner+prepare-key row, never guessed IDs or replacement plans.
    async with owned_session(proof) as session:
        row=(await session.scalars(select(Preparation).where(Preparation.owner_user_id==primary[1].user_id,Preparation.prepare_key_digest==hashlib.sha256(first_body['prepare_key'].encode()).digest()))).one()
        preparation_id=str(row.id)
        check(row.epoch_id==binding.epoch_id and row.root_id==row.id and row.parent_id is None and row.semantic_sha256==first['semantic_sha256']==MEANING_SPEC_SHA256 and row.semantic_json==canonical(MEANING_SPEC) and row.draft_json==canonical(first_body['draft']),'CF029 exact ready owner draft spec')
        ready_plan=row.plan_json
        check(hashlib.sha256(ready_plan.encode()).hexdigest()==row.plan_sha256,'CF029 stored plan integrity')

    flow=flow_app(lambda request,context:engine_result(request,context))
    def client(*args,**kwargs):
        value=AIClient(*args,**kwargs,transport=httpx.ASGITransport(app=flow))
        original=value.analyze_flow
        async def analyze(payload):
            dispatch.append(payload['analysis_id'])
            return await original(payload)
        async def no_plan(payload):
            check(False,'CF029 confirmation and GET cannot regenerate meaning')
        value.analyze_flow=analyze;value.plan_supervisor_core=no_plan
        return value
    async def sessions():
        async with owned_session(proof) as session:
            yield session
    async def call(method,path,body=None,identity=primary,headers=None):
        h={}
        if identity is not None:
            cookie,principal=identity
            h={'origin':'http://localhost:3200','cookie':auth.SESSION_COOKIE+'='+cookie,'x-csrf-token':csrf_token(principal)}
        h.update(headers or {})
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://localhost:8200') as c:
            return await c.request(method,path,json=body,headers=h)
    def response(value,status=200,code=None):
        check(value.status_code==status,'CF029 fixed HTTP status')
        check(value.headers.get('cache-control')=='private, no-store','CF029 private response')
        result=value.json()
        if code:
            check(result['data'] is None and result['error']['code']==code,'CF029 safe rejection')
        else:
            check(result['error'] is None,'CF029 success envelope')
        return result['data']
    def flow_response(value,status=200,report_id=None):
        # Legacy report routes return FlowReportEnvelope/detail, not Supervisor data/error.
        check(value.status_code==status,'CF029 fixed report HTTP status')
        check(value.headers.get('cache-control')=='private, no-store','CF029 private report response')
        result=value.json()
        if status==200:
            check(set(result)=={'report_id','report'},'CF029 report envelope')
            envelope=FlowReportEnvelope.model_validate(result)
            check(str(envelope.report_id)==report_id,'CF029 same stored report identity')
        elif status==404:
            check(result=={'detail':'report not found'},'CF029 report owner rejection')
        elif status==401:
            check(result=={'detail':{'code':'AUTH_REQUIRED','message':'인증이 필요합니다.'}},'CF029 report auth rejection')
        else:
            check(False,'CF029 unsupported report response expectation')
        return result
    previous=dict(app.dependency_overrides);app.dependency_overrides[get_session]=sessions
    try:
      with ExitStack() as stack:
        for name,value in dict(AI_SERVICE_URL='http://synthetic.invalid',FLOW_ANALYSIS_ENABLED=True,FLOW_SERVICE_TOKEN=token,FLOW_USAGE_LIMITS_ENABLED='true',FLOW_SUPPORTED_TICKERS='000720',FLOW_USER_DAILY_REQUEST_LIMIT='2',FLOW_SERVICE_DAILY_REQUEST_LIMIT='2',FLOW_SERVICE_DAILY_BUDGET_USD='2').items():
            stack.enter_context(patch.object(settings,name,value))
        stack.enter_context(patch.dict('os.environ',{'FLOW_ANALYSIS_ENABLED':'true','FLOW_SERVICE_TOKEN':token}))
        stack.enter_context(patch.object(routes,'AIClient',client))
        view=response(await call('GET','/api/supervisor/core/preparations/'+preparation_id))
        check(view==early_view and preparation_id==first_id and canonical(view['plan'])==ready_plan,'CF029 same owner ASGI ready plan after unknown')
        plan=validate_plan(view['plan'],Draft.model_validate(first_body['draft']))
        check(plan.plan_hash==first['plan_hash'],'CF029 assembly and HTTP plan match')
        confirmation=dict(client_key=str(uuid4()),preparation_id=preparation_id,draft=first_body['draft'],expected_plan_hash=plan.plan_hash,consent=dict(allow_flow=True,allow_partial=plan.partial,waived_conditions=plan.required_waivers))
        mark('owner_key_lookup_actual_ASGI_preparation_same_plan')

        negatives=[('missing_consent',422,'INPUT_INVALID',primary,{}),('no_flow',422,'INPUT_INVALID',primary,{}),('stale',409,'PLAN_STALE',primary,{}),('other_owner',404,'RESOURCE_NOT_FOUND',other,{}),('no_session',401,'AUTH_REQUIRED',None,{}),('invalid_session',401,'AUTH_REQUIRED',primary,{'cookie':auth.SESSION_COOKIE+'=cf029-invalid-session'}),('csrf',401,'AUTH_REQUIRED',primary,{'x-csrf-token':'cf029-invalid-csrf'}),('origin',401,'AUTH_REQUIRED',primary,{'origin':'http://invalid.example'})]
        for label,status,code,identity,headers in negatives:
            value=copy.deepcopy(confirmation);value['client_key']=str(uuid4())
            if label=='missing_consent':value.pop('consent')
            elif label=='no_flow':value['consent']['allow_flow']=False
            elif label=='stale':value['expected_plan_hash']='0'*64
            response(await call('POST','/api/supervisor/core/requests',value,identity,headers),status,code)
            await unchanged(before)
            check(not dispatch and await sql('SELECT count(*) FROM supervisor_request_bindings')==0,'CF029 negative admission0 binding0 dispatch0')
        mark('consent_plan_owner_session_CSRF_origin_before_Flow')

        check(await totals()==before,'CF029 fresh period before budget rejection')
        with patch.object(settings,'FLOW_SERVICE_DAILY_BUDGET_USD','0.01'):
            response(await call('POST','/api/supervisor/core/requests',confirmation),429,'USAGE_LIMIT_EXCEEDED')
        await unchanged(before)
        check(not dispatch,'CF029 denied Flow dispatch0')
        async with owned_session(proof) as session:
            bound=(await session.scalars(select(Binding).where(Binding.owner_user_id==primary[1].user_id,Binding.client_key_digest==hashlib.sha256(confirmation['client_key'].encode()).digest()))).one()
            supervisor_id=str(bound.id)
            check(str(bound.preparation_id)==preparation_id,'CF029 denied binding references actual preparation')
        denied=response(await call('GET','/api/supervisor/core/requests/'+supervisor_id))
        check(denied['flow'] is None and denied['views'][0]['state']=='not_admitted','CF029 committed binding not admitted after rollback')
        snapshots['budget_denied']=await totals()
        mark('Flow_budget429_full_usage_rollback_binding_preserved')

        # No period row is changed/deleted to retry: normal settings create the first one.
        check(await totals()==before,'CF029 no persisted period before same-key retry')
        stored=response(await call('POST','/api/supervisor/core/requests',confirmation))
        check(stored['supervisor_id']==supervisor_id and stored['flow']['state']=='stored' and len(dispatch)==1,'CF029 same-key coordinator stores once')
        after=await totals();snapshots['stored']=after
        check(after['flow_analysis_runs']==after['analysis_usage_reservations']==after['flow_reports']==1 and after['analysis_provider_calls']==9 and after['analysis_usage_periods']==2,'CF029 single run reservation report and nine reserved slots')
        check(await sql('SELECT count(*) FROM analysis_usage_reservations WHERE max_nano=913500000')==1,'CF029 fixed Flow test reservation')
        check(await sql("SELECT count(*) FROM analysis_provider_calls WHERE state='not_called'")==9,'CF029 nine slots are not external calls')
        report_id=stored['flow']['report_id']
        report=flow_response(await call('GET','/api/flow/reports/'+report_id),report_id=report_id)
        check(response(await call('POST','/api/supervisor/core/requests',confirmation))==stored,'CF029 confirmation replay same stored result')
        check(response(await call('GET','/api/supervisor/core/requests/'+supervisor_id))==stored,'CF029 owner request GET same stored binding')
        check(flow_response(await call('GET','/api/flow/reports/'+report_id),report_id=report_id)==report,'CF029 owner report content unchanged')
        response(await call('GET','/api/supervisor/core/requests/'+supervisor_id,identity=other),404,'RESOURCE_NOT_FOUND')
        response(await call('GET','/api/supervisor/core/requests/'+supervisor_id,identity=None),401,'AUTH_REQUIRED')
        flow_response(await call('GET','/api/flow/reports/'+report_id,identity=other),404)
        flow_response(await call('GET','/api/flow/reports/'+report_id,identity=None),401)
        consumed=response(await call('GET','/api/supervisor/core/preparations/'+preparation_id))
        check(consumed['state']=='consumed' and consumed['plan'] is None and consumed['consumed_binding_id']==supervisor_id,'CF029 original preparation consumed reference')
        check(await sql("SELECT count(*) FROM supervisor_meaning_preparations WHERE id=:id AND state='consumed' AND draft_json IS NULL AND frame_json IS NULL AND plan_json IS NULL AND continuation_json IS NULL",{'id':__import__('uuid').UUID(preparation_id)})==1,'CF029 consumed root sensitive redaction')
        await unchanged(after);check(len(dispatch)==1,'CF029 replay GET extra dispatch0')
        mark('same_confirmation_retry_stored_replay_owner_GET_extra_calls0')
        return dict(groups=groups,meaning_mock_count=2,meaning_mock_generation=2,synthetic_supplier=2,fake_flow_dispatch=1,flow_before=before,flow_budget_denied=snapshots['budget_denied'],flow_after=after,meaning_epoch_snapshots={k:snapshots[k] for k in ('ready','unknown')},meaning_epoch_sha256=sha(held_snapshot),meaning_epoch_final_sha256=sha(await epoch_snapshot()),real_provider_requests=0,real_credential_reads=0,google_requests=0,note='PreparationService private initial preparation; actual authenticated ASGI GET/confirmation/report; fake Flow only. Nine provider rows are not_called reservations.')
    finally:
        app.dependency_overrides.clear();app.dependency_overrides.update(previous)


async def verify_meaning_accounting(proof):
    """Only fresh owned PG; real SQL transactions and two-session contention."""
    from scripts.cf003_admission_check import isolated_application,check,migration
    with isolated_application(proof) as denied:
        try:
            result=await _verify_meaning_accounting(proof)
        except BaseException as error:
            from scripts.cf002_interactive_login import safe_print
            frames=[];tb=error.__traceback__
            while tb:
                if tb.tb_frame.f_code.co_filename==__file__:
                    frames.append({'function':tb.tb_frame.f_code.co_name,'line':tb.tb_lineno})
                tb=tb.tb_next
            safe_print({'phase':'cf044_checker_failure','error_type':type(error).__name__ if type(error).__name__ in {'AccountingConflict','AssertionError','IntegrityError','VerificationFailure','RuntimeError','InvalidRequestError','NameError','TypeError','AttributeError'} else 'other','frames':frames[-6:]})
            raise
        check(not any(denied.values()),'CF044 forbidden IO')
        return result|{'observed_denials':dict(denied),'provider_requests':0}


async def _verify_meaning_accounting(proof):
    import asyncio
    from dataclasses import replace
    from datetime import timedelta
    from uuid import uuid4,UUID
    from sqlalchemy import select,text
    from db.models.auth.models import AuthUser,AuthSession
    from db.models.supervisor.preparation import SupervisorMeaningPreparation as Preparation
    from db.models.supervisor.meaning_accounting import SupervisorMeaningAccount as Account,SupervisorMeaningReservation as Reservation
    from src.modules.auth.application.session_service import issue_session
    from src.modules.supervisor.domain.contracts import MEANING_SPEC
    from src.modules.supervisor.domain.meaning_accounting import Policy,Binding,AccountingConflict,canonical,sha
    from src.modules.supervisor.application.meaning_accounting_service import MeaningAccountingService as Service
    from src.modules.supervisor.infrastructure.meaning_accounting_repository import projection
    from scripts.cf002_interactive_login import owned_session,migrate_owned,safe_print
    from scripts.cf003_admission_check import check,migration
    groups=[]
    def mark(label):
        groups.append(label);safe_print({'phase':'cf044_check','label':label,'status':'passed'})
    async def sql(q,params=None):
        async with owned_session(proof) as s:return await s.scalar(text(q),params or {})
    async def fail(call, expected=AccountingConflict):
        try:await call
        except expected:
            return
        raise AssertionError('CF044 expected refusal')
    async with owned_session(proof) as s:
        now=await s.scalar(text('SELECT clock_timestamp()'));user=AuthUser(id=uuid4());other=AuthUser(id=uuid4());s.add_all([user,other]);await s.flush()
        _,principal=await issue_session(s,user);_,foreign=await issue_session(s,other);await s.commit()
    before=await sql('SELECT count(*) FROM auth_users')
    await migration(proof,'c35001a7e0001',downgrade=True);await migrate_owned(proof)
    check(await sql('SELECT count(*) FROM auth_users')==before,'CF044 additive preserved')
    check(await sql('SELECT version_num FROM alembic_version')=='c44001a7e0001','CF044 single head')
    mark('empty_downgrade_reupgrade_preserves_old_rows')
    policy=Policy(operation='meaning',scope='{"scope":"cf044-synthetic"}',starts_at=now-timedelta(seconds=10),ends_at=now+timedelta(minutes=5),limit_nano=1500000,attempt_nano=500000,max_attempts=3,semantic_json=canonical(MEANING_SPEC),price_json=canonical(MEANING_SPEC['price']),model=MEANING_SPEC['model'],tier=MEANING_SPEC['service_tier'],input_cap=MEANING_SPEC['caps']['input_tokens'],output_cap=MEANING_SPEC['caps']['output_tokens'])
    async def create(p=policy,identity=None):
        async with owned_session(proof) as s:return UUID(await Service(s).create_account(principal,p,account_id=identity or uuid4()))
    account=await create()
    check(await create()==account,'CF044 scope cannot duplicate by id')
    for changed in (replace(policy,ends_at=policy.ends_at+timedelta(seconds=1)),replace(policy,limit_nano=2000000)):
        await fail(create(changed))
    async def prep(who=principal,*,expired=False):
        async with owned_session(proof) as s:
            pid,attempt=uuid4(),uuid4();expires=now-timedelta(seconds=1) if expired else now+timedelta(minutes=4)
            created=now-timedelta(minutes=5) if expired else now
            row=Preparation(id=pid,owner_user_id=who.user_id,prepare_key_digest=uuid4().bytes*2,request_digest='a'*64,draft_digest='b'*64,semantic_json=policy.semantic_json,semantic_sha256=sha(policy.semantic_json),root_id=pid,parent_id=None,depth=0,attempt_id=attempt,epoch_id=None,state='pending',meaning_status='unavailable',created_at=created,expires_at=expires)
            s.add(row);await s.flush();bound=Binding(pid,attempt,who.session_id,row.request_digest,row.draft_digest,projection(row),row.semantic_sha256,sha(policy.price_json),expires);await s.commit();return bound
    async def reserve(b,who=principal,acc=account):
        async with owned_session(proof) as s:return await Service(s).reserve(who,acc,b)
    b=await prep()
    first,second=await asyncio.gather(reserve(b),reserve(b))
    check(first==second and await sql('SELECT count(*) FROM supervisor_meaning_reservations')==1,'CF044 concurrent winner one')
    check(await sql('SELECT reserved_nano FROM supervisor_meaning_accounts WHERE id=:id',{'id':account})==500000,'CF044 single consumption')
    await fail(reserve(replace(b,request_sha256='c'*64)));await fail(reserve(replace(b,session_id=foreign.session_id),foreign))
    await fail(reserve(b,acc=uuid4()))
    for field,value in [('attempt_id',uuid4()),('draft_sha256','c'*64),('semantic_sha256','c'*64),('projection_sha256','c'*64),('price_sha256','c'*64),('expires_at',now-timedelta(seconds=1))]:
        await fail(reserve(replace(b,**{field:value})))
    await fail(reserve(replace(b,session_id=foreign.session_id)))
    from sqlalchemy.exc import IntegrityError
    for table,identity,column,value in [('supervisor_meaning_accounts',account,'policy_json','{}'),('supervisor_meaning_accounts',account,'policy_json',canonical(__import__('json').loads(policy.snapshot())|{'operation':None})),('supervisor_meaning_reservations',UUID(first['reservation_id']),'binding_json','{}'),('supervisor_meaning_reservations',UUID(first['reservation_id']),'binding_json',canonical(__import__('json').loads(b.snapshot())|{'session_id':None}))]:
        async with owned_session(proof) as session:
            try:
                hash_column='policy_sha256' if column=='policy_json' else 'binding_sha256'
                await session.execute(text('UPDATE '+table+' SET '+column+'=:value,'+hash_column+'=:digest WHERE id=:id'),{'value':value,'digest':sha(value),'id':identity})
                await session.flush()
            except IntegrityError as error:
                check(error.orig.sqlstate=='23514','CF044 missing/null JSON CHECK violation')
                await session.rollback()
            else:raise AssertionError('CF044 malformed binding must fail DB CHECK')
    # Exercise physical composite owner FKs, not just service prechecks.
    async with owned_session(proof) as session:
        foreign_account=UUID(await Service(session).create_account(foreign,policy,account_id=uuid4()))
    foreign_binding=await prep(foreign);own_binding=await prep()
    for acc,bound in [(foreign_account,own_binding),(account,foreign_binding)]:
        async with owned_session(proof) as session:
            row=Reservation(id=uuid4(),account_id=acc,owner_user_id=principal.user_id,owner_session_id=bound.session_id,preparation_id=bound.preparation_id,attempt_id=bound.attempt_id,binding_json=bound.snapshot(),binding_sha256=sha(bound.snapshot()),expires_at=bound.expires_at,reserved_nano=500000,state='held')
            session.add(row)
            try:await session.flush()
            except IntegrityError as error:
                check(error.orig.sqlstate=='23503','CF044 composite owner FK enforced');await session.rollback()
            else:raise AssertionError('CF044 physical owner FK must refuse')
    expired=await prep(expired=True)
    await fail(reserve(expired))
    deleted=await prep()
    async with owned_session(proof) as session:
        await session.execute(text("UPDATE supervisor_meaning_preparations SET state='deleted',redacted_at=clock_timestamp() WHERE id=:id"),{'id':deleted.preparation_id});await session.commit()
    await fail(reserve(deleted))
    mark('scope_unique_concurrent_winner_and_binding_owner_denials')
    async def settle(binding,receipt,evidence):
        async with owned_session(proof) as s:return await Service(s).settle(owner_id=principal.user_id,account_id=account,reservation_id=UUID(receipt['reservation_id']),binding_sha256=sha(binding.snapshot()),evidence=evidence)
    observed=dict(state='observed',model=policy.model,tier=policy.tier,input=10,cached=2,output=5,total=15,request_sha256=b.request_sha256,projection_sha256=b.projection_sha256,binding_sha256=sha(b.snapshot()),semantic_sha256=b.semantic_sha256,price_sha256=b.price_sha256)
    result=await settle(b,first,observed);check(result['estimated_nano']==28650 and result['state']=='observed','CF044 integer estimate')
    check(await settle(b,first,observed)==result,'CF044 terminal replay')
    await fail(settle(b,first,{'state':'unknown'}))
    # Settlement survives revoked session and redacted source, retaining stored binding.
    async with owned_session(proof) as s:
        await s.execute(text('UPDATE auth_sessions SET revoked_at=clock_timestamp() WHERE id=:id'),{'id':principal.session_id})
        await s.execute(text("UPDATE supervisor_meaning_preparations SET state='deleted',redacted_at=clock_timestamp(),draft_json=NULL WHERE id=:id"),{'id':b.preparation_id});await s.commit()
    check(await settle(b,first,observed)==result,'CF044 settlement independent of current auth/redaction')
    async with owned_session(proof) as s:
        await s.execute(text('UPDATE auth_sessions SET revoked_at=NULL WHERE id=:id'),{'id':principal.session_id});await s.commit()
    b2=await prep()
    # A real committed reservation with simulated lost ACK. Its ID is not returned.
    async with owned_session(proof) as s:
        commit=s.commit
        async def lost_ack():await commit();raise RuntimeError('synthetic ACK loss')
        s.commit=lost_ack
        await fail(Service(s).reserve(principal,account,b2),RuntimeError)
    async with owned_session(proof) as s:
        dirty=AuthUser(id=uuid4());s.add(dirty)
        recovered=await Service(s).reconcile(owner_id=principal.user_id,account_id=account,binding=b2)
        check(dirty in s.new,'CF044 readonly no autoflush')
        await s.rollback()
    unknown=await settle(b2,recovered,{'state':'unknown'})
    check(unknown['state']=='unknown','CF044 unknown hold')
    await fail(settle(b2,recovered,observed))
    check(await sql('SELECT reserved_nano FROM supervisor_meaning_accounts WHERE id=:id',{'id':account})==1000000,'CF044 no refund')
    check(await sql('SELECT blocked FROM supervisor_meaning_accounts WHERE id=:id',{'id':account}) is True,'CF044 durable block')
    await fail(reserve(await prep()))
    mark('integer_settlement_ack_loss_readonly_recovery_terminal_hold_restart')
    # A failed commit before persistence rolls both reservation and account back.
    p2=replace(policy,scope='{"scope":"cf044-limit"}',limit_nano=500000,max_attempts=1)
    a2=await create(p2);b3=await prep()
    async with owned_session(proof) as s:
        async def before_ack():raise RuntimeError('synthetic rollback before commit')
        s.commit=before_ack
        await fail(Service(s).reserve(principal,a2,b3),RuntimeError)
    async with owned_session(proof) as s:
        row=await s.get(Account,a2)
        check(row.attempts==row.reserved_nano==0,'CF044 rollback no partial account')
        check(await s.scalar(select(Reservation.id).where(Reservation.preparation_id==b3.preparation_id)) is None,'CF044 rollback no reservation')
    held=await reserve(b3,acc=a2)
    await fail(reserve(await prep(),acc=a2))
    check(await reserve(b3,acc=a2)==held,'CF044 replay at exact limit')
    async with owned_session(proof) as session:
        await session.execute(text("UPDATE auth_sessions SET expires_at=clock_timestamp()+interval '1 millisecond' WHERE id=:id"),{'id':principal.session_id})
        await session.commit()
    await asyncio.sleep(.02)
    async with owned_session(proof) as session:
        expired_settlement=await Service(session).settle(owner_id=principal.user_id,account_id=a2,reservation_id=UUID(held['reservation_id']),binding_sha256=sha(b3.snapshot()),evidence={'state':'unknown'})
        check(expired_settlement['state']=='unknown','CF044 expired session does not erase settlement')
    async with owned_session(proof) as session:
        await session.execute(text('UPDATE auth_sessions SET expires_at=:expires WHERE id=:id'),{'expires':principal.expires_at,'id':principal.session_id});await session.commit()
    mark('atomic_rollback_and_exact_limit_no_extra_consumption')
    # Each malformed usage is a terminal held/account-blocked result, never raw text.
    bad=[{'state':'observed','secret':'do-not-store-synthetic'},observed|{'input':True},observed|{'input':-1},observed|{'input':1.5},observed|{'input':2**63},observed|{'model':'do-not-store-synthetic'},observed|{'cached':99}]
    for i,e in enumerate(bad):
        pa=replace(policy,scope=canonical({'scope':'cf044-anomalous-'+str(i)}))
        aa=await create(pa);bb=await prep();rr=await reserve(bb,acc=aa)
        async with owned_session(proof) as session:
            value=await Service(session).settle(owner_id=principal.user_id,account_id=aa,reservation_id=UUID(rr['reservation_id']),binding_sha256=sha(bb.snapshot()),evidence=e)
        check(value['state']=='anomalous' and value['estimated_nano'] is None,'CF044 invalid usage preserves hold')
        async with owned_session(proof) as session:
            ar=await session.get(Account,aa);res=await session.get(Reservation,UUID(rr['reservation_id']))
            check(ar.blocked and ar.reserved_nano==500000 and ar.observed_nano==0,'CF044 anomalous durable block')
            check('do-not-store' not in res.receipt_json and set(__import__('json').loads(res.receipt_json))=={'state','reason','evidence_sha256'},'CF044 raw strings never stored')
        await fail(reserve(await prep(),acc=aa))
    mark('strict_usage_anomalous_hold_block_sanitized_receipts')
    # Populated downgrade must refuse atomically; existing records remain.
    await fail(migration(proof,'c35001a7e0001',downgrade=True),RuntimeError)
    check(await sql('SELECT count(*) FROM supervisor_meaning_reservations')==10,'CF044 populated downgrade preserved')
    mark('populated_downgrade_denied')
    return {'groups':groups,'ack_loss':'commit-wrapper-simulation-after-real-commit','actual_SQL':True,'actual_provider':False}
