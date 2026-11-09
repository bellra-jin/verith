"""Closed pure AI loader and focused owned-PG acceptance; no production provider."""
from pathlib import Path
import hashlib,sys,importlib.util
CORE_MODULES=('domain.meaning','domain.core_contracts','domain.capabilities','infrastructure.meaning_gateway','application.meaning_service','application.planning.core_planner')
def load_core(*,gateway=None):
    from scripts.cf020_supervisor_check import load_planner
    from scripts.check_safe import CF022_INPUTS
    load_planner();root=Path(__file__).resolve().parents[2]
    for suffix in CORE_MODULES:
        name='src.supervisor.'+suffix;relative='ai/src/supervisor/'+suffix.replace('.','/')+'.py';path=root/relative
        if hashlib.sha256(path.read_bytes()).hexdigest()!=CF022_INPUTS[relative]:raise RuntimeError('Core source pin mismatch')
        if name not in sys.modules:
            spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
            parent,_,leaf=name.rpartition('.');setattr(sys.modules[parent],leaf,module)
        if Path(sys.modules[name].__spec__.origin).resolve()!=path.resolve():raise RuntimeError('Core module origin mismatch')
    from fastapi import FastAPI
    app=FastAPI();app.include_router(sys.modules['src.supervisor.api.routes'].make_router(gateway=gateway));return app

async def verify_core(proof):
    from scripts.cf003_admission_check import isolated_application,check
    with isolated_application(proof) as observed:
        try:result=await _verify_core(proof)
        except BaseException as error:
            from scripts.cf002_interactive_login import safe_print
            frames=[];tb=error.__traceback__
            while tb:
                if tb.tb_frame.f_code.co_filename==__file__:frames.append({'source':'core_checker','function':tb.tb_frame.f_code.co_name,'line':tb.tb_lineno})
                tb=tb.tb_next
            safe_print({'phase':'cf022_checker_failure','frames':frames[-8:],'observed_denials':dict(observed)})
            raise
        check(not any(observed.values()),'CF022 forbidden access')
        return result|{'observed_denials':dict(observed)}

async def _verify_core(proof):
    import asyncio,copy,hashlib,httpx
    from contextlib import ExitStack
    from datetime import timedelta
    from unittest.mock import patch
    from uuid import uuid4,UUID
    from sqlalchemy import select,text,func
    from sqlalchemy.exc import SQLAlchemyError
    from db.models.auth.models import AuthUser
    from db.models.common.stock import Stock
    from db.models.supervisor.request_binding import SupervisorRequestBinding as Binding
    from db.models.flow.analysis_run import FlowAnalysisRun
    from db.session import get_session
    from src.api.main import app
    from src.shared.config import settings
    from src.modules.auth.api import router as auth
    from src.modules.auth.application.session_service import issue_session,csrf_token,revoke_session
    from src.modules.supervisor.api import router as core_router
    from src.modules.supervisor.application.service import SupervisorService
    from src.modules.supervisor.domain.contracts import canonical,sha
    from src.modules.supervisor.domain.flow_projection import confirmed_plan,flow_body
    from src.modules.supervisor.infrastructure import repository as core_repo
    from src.modules.stocks.application.resolver_service import StockResolverService
    from src.modules.flow.api import analysis_router
    from src.modules.flow.application.analysis_service import AnalysisService
    from src.modules.flow.application.analysis_adapter import FlowAnalysisAdapter
    from src.shared.infrastructure.clients.ai_client import AIClient
    from scripts.cf002_interactive_login import owned_session,safe_print,migrate_owned
    from scripts.cf003_admission_check import check,migration
    from scripts.cf012_analysis_check import flow_app,engine_result
    groups=[];planning=[];resolves=[];dispatch={};engines={};tasks=[];mode='normal';target_key=None;ack_injected=False;fail_stage=False;prepare_count=0
    held=asyncio.Event();release=asyncio.Event();both=asyncio.Event()
    def mark(name):groups.append(name);safe_print({'phase':'cf022_check','label':name,'status':'passed'})
    async def sql(q,p=None):
        async with owned_session(proof) as session:return await session.scalar(text(q),p or {})
    async def counts():return tuple([await sql('SELECT count(*) FROM '+n) for n in ('supervisor_request_bindings','flow_analysis_runs','analysis_usage_reservations','analysis_provider_calls')])
    async def user():
        async with owned_session(proof) as session:
            u=AuthUser(id=uuid4());session.add(u);await session.flush();cookie,principal=await issue_session(session,u);await session.commit();return cookie,principal
    primary=await user();other=await user();revoked=await user()
    async with owned_session(proof) as session:session.add(Stock(stock_code='005930',stock_name='삼성전자',market='KOSPI'));await session.commit()
    before=await sql('SELECT count(*) FROM auth_users');await migration(proof,'c18001a7e0001',downgrade=True);check(await sql("SELECT to_regclass('supervisor_request_bindings')") is None,'CF022 empty downgrade');await migrate_owned(proof);check(await sql('SELECT count(*) FROM auth_users')==before,'CF022 existing rows preserved');mark('migration_up_down_preserves_existing_tables')
    async def request_session():
        async with owned_session(proof) as session:
            original=session.commit
            async def commit():
                nonlocal ack_injected
                if mode=='binding_ack' and not ack_injected and target_key is not None:
                    exists=await session.scalar(select(Binding.id).where(Binding.client_key_digest==target_key))
                    if exists is not None:await original();ack_injected=True;raise OSError('Fixed synthetic binding commit ACK loss')
                await original()
            session.commit=commit;yield session
    async def call(method,path,value=None,identity=None,headers=None):
        cookie,principal=identity or primary;h={'origin':'http://localhost:3200','cookie':auth.SESSION_COOKIE+'='+cookie,'x-csrf-token':csrf_token(principal)}|(headers or {})
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://localhost:8200') as c:return await c.request(method,path,json=value,headers=h)
    def data(response,status):
        check(response.status_code==status,'CF022 HTTP status');check(response.headers.get('cache-control')=='private, no-store','CF022 private response');v=response.json();check(v['schema_version']=='supervisor.core.v1' and v['error'] is None,'CF022 core success envelope');return v['data']
    def error(response,status,code=None):
        check(response.status_code==status,'CF022 safe error status');v=response.json();check(v['data'] is None and v['error']['message']=='Supervisor request unavailable','CF022 safe error envelope');check(code is None or v['error']['code']==code,'CF022 fixed error')
    async def prepare(query='삼성전자 수급',identity=None):return data(await call('POST','/api/supervisor/core/prepare',dict(original_query=query,answers=[],revision=0),identity),200)
    def confirm(plan):return dict(client_key=str(uuid4()),draft=dict(original_query=plan['frame']['original_query'],answers=plan['frame']['answers'],revision=plan['frame']['revision']),expected_plan_hash=plan['plan_hash'],consent=dict(allow_flow=True,allow_partial=plan['partial'],waived_conditions=plan['required_waivers']))
    def engine(request,context):
        id=str(request.analysis_id);engines[id]=engines.get(id,0)+1;check(engines[id]==1,'CF022 engine once');return engine_result(request,context)
    planner=load_core();flow=flow_app(engine);token='cf022-synthetic-service-token-at-least32'
    def client(*args,**kwargs):
        c=AIClient(*args,**kwargs);plan_c=AIClient(*args,**kwargs,transport=httpx.ASGITransport(app=planner));flow_c=AIClient(*args,**kwargs,transport=httpx.ASGITransport(app=flow));original=flow_c.analyze_flow
        async def core(payload):
            planning.append(payload['data']['phase'])
            if mode=='revoke_planning' and payload['data']['phase']=='continue':held.set();await release.wait()
            return await plan_c.plan_supervisor_core(payload)
        async def analyze(payload):
            id=payload['analysis_id'];dispatch[id]=dispatch.get(id,0)+1
            if mode=='race':held.set();await release.wait()
            return await original(payload)
        c.plan_supervisor_core=core;c.analyze_flow=analyze;return c
    original_resolve=StockResolverService.resolve
    async def resolve(self,query):resolves.append(query);return await original_resolve(self,query)
    original_prepare=SupervisorService._prepare
    async def limited_prepare(self,*args):
        nonlocal prepare_count
        value=await original_prepare(self,*args)
        if mode=='race':
            prepare_count+=1
            if prepare_count==2:both.set()
            await both.wait()
        return value
    original_admit=core_repo.admit
    async def admit(session,values):
        if mode=='expired_binding':
            values=dict(values);stamp=values['confirmed_at']-timedelta(seconds=121)
            values['confirmed_at']=stamp;values['handoff_before']=stamp+timedelta(seconds=120)
            raw=__import__('json').loads(values['flow_input_json']);raw['as_of']=stamp.isoformat()
            values['flow_input_json']=canonical(raw);values['flow_sha256']=hashlib.sha256(values['flow_input_json'].encode()).hexdigest()
        return await original_admit(session,values)
    original_flow_run=core_repo.flow_run
    async def flow_run(session,binding):
        if mode=='get_before_flow_read':held.set();await release.wait()
        return await original_flow_run(session,binding)
    original_get=AnalysisService.get
    async def flow_get(self,*args):
        if mode=='get_after_delete':held.set();await release.wait()
        return await original_get(self,*args)
    original_observe=SupervisorService.observe
    async def observe(self,*args,**kwargs):
        if mode=='confirm_after_delete':held.set();await release.wait()
        return await original_observe(self,*args,**kwargs)
    original_post=AnalysisService.post
    async def flow_post(self,*args):
        if mode=='before_admission':raise OSError('Fixed synthetic pre-admission stop')
        return await original_post(self,*args)
    original_stage=FlowAnalysisAdapter.stage
    async def stage(self,*args):
        if fail_stage:raise OSError('Fixed synthetic stage failure')
        return await original_stage(self,*args)
    previous=dict(app.dependency_overrides);app.dependency_overrides[get_session]=request_session
    try:
      with ExitStack() as stack:
        for name,value in dict(AI_SERVICE_URL='http://synthetic.invalid',FLOW_ANALYSIS_ENABLED=True,FLOW_SERVICE_TOKEN=token,FLOW_USAGE_LIMITS_ENABLED='true',FLOW_SUPPORTED_TICKERS='005930',FLOW_USER_DAILY_REQUEST_LIMIT='5',FLOW_SERVICE_DAILY_REQUEST_LIMIT='40',FLOW_SERVICE_DAILY_BUDGET_USD='50').items():stack.enter_context(patch.object(settings,name,value))
        stack.enter_context(patch.dict('os.environ',{'FLOW_ANALYSIS_ENABLED':'true','FLOW_SERVICE_TOKEN':token}));stack.enter_context(patch.object(core_router,'AIClient',client));stack.enter_context(patch.object(StockResolverService,'resolve',resolve));stack.enter_context(patch.object(SupervisorService,'_prepare',limited_prepare));stack.enter_context(patch.object(AnalysisService,'post',flow_post));stack.enter_context(patch.object(FlowAnalysisAdapter,'stage',stage));stack.enter_context(patch.object(core_repo,'admit',admit));stack.enter_context(patch.object(core_repo,'flow_run',flow_run));stack.enter_context(patch.object(AnalysisService,'get',flow_get));stack.enter_context(patch.object(SupervisorService,'observe',observe));stack.enter_context(patch.object(analysis_router,'AIClient',client))
        check(await counts()==(0,0,0,0),'CF022 initial empty new tables')
        for headers in ({'cookie':''},{'x-csrf-token':'bad'},{'origin':'https://other.invalid'}):error(await call('POST','/api/supervisor/core/prepare',dict(original_query='삼성전자 수급',answers=[],revision=0),headers=headers),401)
        p=await prepare('삼성전자 어제 외국인 말고 기관 수급과 차트');check(p['partial'] and p['required_waivers'] and p['requested_views']==['flow','technical'],'CF022 actual partial meaning');check(await counts()==(0,0,0,0),'CF022 prepare no mutation');body=confirm(p)
        rejected=copy.deepcopy(body);rejected['consent']['waived_conditions']=[];error(await call('POST','/api/supervisor/core/requests',rejected),422)
        mark('prepare_auth_explicit_conditions_no_execution')
        held.clear();release.clear();mode='revoke_planning';before_counts=await counts()
        denied=asyncio.create_task(call('POST','/api/supervisor/core/prepare',dict(original_query='삼성전자 수급',answers=[],revision=0),revoked));tasks.append(denied)
        await asyncio.wait_for(held.wait(),5)
        async with owned_session(proof) as session:await revoke_session(session,revoked[1])
        release.set();error(await denied,401);mode='normal';check(await counts()==before_counts,'CF022 revoked planning mutation0');mark('planning_revocation_fresh_session_auth')
        held.clear();release.clear()
        # Both requests observed initial absence. Two bounded validations are allowed; unique winner is immutable.
        baseplan=await prepare();body1=confirm(baseplan);prepare_count=0;mode='race'
        a=asyncio.create_task(call('POST','/api/supervisor/core/requests',body1));b=asyncio.create_task(call('POST','/api/supervisor/core/requests',body1));tasks.extend([a,b]);await asyncio.wait_for(held.wait(),10)
        check(await counts()==(1,1,1,9),'CF022 binding/run/reservation winner once');check(await sql('SELECT request_count FROM analysis_usage_periods WHERE scope=\'service\'')==1,'CF022 one quota increment');release.set();responses=await asyncio.gather(a,b);check({x.status_code for x in responses}<={200,202},'CF022 concurrent responses');first=data(next(x for x in responses if x.status_code==200),200);id=first['supervisor_id'];mode='normal';n=(len(planning),len(resolves),len(dispatch));replay=data(await call('POST','/api/supervisor/core/requests',body1),200);check(replay==first and (len(planning),len(resolves),len(dispatch))==n,'CF022 row-confirmed replay has planner/resolver/dispatch zero')
        error(await call('POST','/api/supervisor/core/requests',body1|{'expected_plan_hash':'0'*64}),409,'IDEMPOTENCY_CONFLICT');error(await call('GET','/api/supervisor/core/requests/'+id,identity=other),404)
        check(data(await call('GET','/api/supervisor/core/requests/'+id),200)==first,'CF022 observe same outcome');mark('binding_winner_existing_Flow_usage_and_replay')
        # Commit succeeded but ACK was lost: first response has Flow0, next primary row replay recovers.
        body2=confirm(await prepare());target_key=hashlib.sha256(body2['client_key'].encode()).digest();mode='binding_ack';before_calls=len(dispatch);error(await call('POST','/api/supervisor/core/requests',body2),503);check(ack_injected and len(dispatch)==before_calls,'CF022 unknown binding ACK first Flow0');mode='normal';n=(len(planning),len(resolves));second=data(await call('POST','/api/supervisor/core/requests',body2),200);check((len(planning),len(resolves))==n and len(dispatch)==before_calls+1,'CF022 ACK row replay only');mark('binding_ACK_unknown_then_primary_row_replay')
        body3=confirm(await prepare());mode='before_admission';before_calls=len(dispatch);error(await call('POST','/api/supervisor/core/requests',body3),503);mode='normal'
        async with owned_session(proof) as session:row=await core_repo.by_key(session,primary[1].user_id,hashlib.sha256(body3['client_key'].encode()).digest());pending_id=str(row.id)
        pending=data(await call('GET','/api/supervisor/core/requests/'+pending_id),200);check(pending['flow'] is None and pending['views'][0]['state']=='not_admitted' and len(dispatch)==before_calls,'CF022 pre-admission GET observes only');third=data(await call('POST','/api/supervisor/core/requests',body3),200);mark('binding_before_admission_stop_recovers_fixed_input')
        fail_stage=True;body4=confirm(await prepare('삼성전자 어제 수급과 차트'));before_calls=len(dispatch);error(await call('POST','/api/supervisor/core/requests',body4),503);fail_stage=False
        async with owned_session(proof) as session:row=await core_repo.by_key(session,primary[1].user_id,hashlib.sha256(body4['client_key'].encode()).digest());ready_id=str(row.id)
        ready=data(await call('GET','/api/supervisor/core/requests/'+ready_id),200);check(ready['flow']['state']=='result_ready' and len(dispatch)==before_calls+1,'CF022 GET does not publish');n=(len(planning),len(resolves),len(dispatch));fourth=data(await call('POST','/api/supervisor/core/requests',body4),200);check(fourth['flow']['state']=='stored' and fourth['coverage']=='partial' and fourth['effective_scope']['waived_conditions']==body4['consent']['waived_conditions'] and (len(planning),len(resolves),len(dispatch))==n,'CF022 snapshot-only scope-aware recovery');mark('result_ready_GET_only_same_key_snapshot_publish')
        before_usage=await sql('SELECT count(*) FROM analysis_usage_reservations');report=first['flow']['report_id']
        async def fail_redact(*args):raise SQLAlchemyError('Fixed synthetic redaction failure')
        with patch.object(core_repo,'redact_for_flow',fail_redact):check((await call('DELETE','/api/flow/reports/'+report)).status_code==503,'CF022 redaction failure request')
        check((await call('GET','/api/flow/reports/'+report)).status_code==200,'CF022 delete rollback retains original report');check(data(await call('GET','/api/supervisor/core/requests/'+id),200)['plan'] is not None,'CF022 delete rollback retains binding')
        # GET has already read a live binding and ended its transaction before deletion.
        held.clear();release.clear();mode='get_after_delete'
        reading=asyncio.create_task(call('GET','/api/supervisor/core/requests/'+id));tasks.append(reading);await asyncio.wait_for(held.wait(),5)
        check((await call('DELETE','/api/flow/reports/'+report)).status_code==204,'CF022 owned delete');release.set();gone=data(await reading,200);mode='normal'
        check(gone['coverage']=='deleted' and gone['plan'] is None and gone['effective_scope'] is None and gone['flow'] is None,'CF022 delete/GET redaction');error(await call('POST','/api/supervisor/core/requests',body1),404);check(await sql('SELECT count(*) FROM supervisor_request_bindings WHERE plan_json IS NULL AND flow_input_json IS NULL')==1 and await sql('SELECT count(*) FROM analysis_usage_reservations')==before_usage,'CF022 sensitive redaction/accounting retained');mark('redaction_rollback_delete_GET_race_and_usage_retained')
        # The replay completed Flow observation, then deletion commits before Sup final publication.
        held.clear();release.clear();mode='confirm_after_delete';before_calls=len(dispatch)
        confirming=asyncio.create_task(call('POST','/api/supervisor/core/requests',body2));tasks.append(confirming);await asyncio.wait_for(held.wait(),5)
        check((await call('DELETE','/api/flow/reports/'+second['flow']['report_id'])).status_code==204,'CF022 delete during replay');release.set();redacted=data(await confirming,200);mode='normal'
        check(redacted['coverage']=='deleted' and redacted['plan'] is None and len(dispatch)==before_calls,'CF022 confirm returns fresh redaction');mark('confirm_delete_barrier_preserves_no_private_result')
        # Earlier interleaving: binding was live, but deletion completes before the first
        # plain Flow-run SELECT. No Flow get call is needed to observe a deleted Outcome.
        held.clear();release.clear();mode='get_before_flow_read';before_calls=len(dispatch)
        early=asyncio.create_task(call('GET','/api/supervisor/core/requests/'+third['supervisor_id']));tasks.append(early);await asyncio.wait_for(held.wait(),5)
        check((await call('DELETE','/api/flow/reports/'+third['flow']['report_id'])).status_code==204,'CF022 delete before run read');release.set();early_deleted=data(await early,200);mode='normal'
        check(early_deleted['coverage']=='deleted' and early_deleted['plan'] is None and early_deleted['flow'] is None and len(dispatch)==before_calls,'CF022 earlier run-read redaction');mark('deleted_before_first_run_read_fresh_binding')
        # A durable expired binding cannot create a new run. A run seeded through the existing
        # authenticated Flow route still recovers with its original key after that handoff cutoff.
        expired_body=confirm(await prepare());mode='expired_binding';before_calls=len(dispatch)
        error(await call('POST','/api/supervisor/core/requests',expired_body),409,'HANDOFF_EXPIRED');mode='normal'
        async with owned_session(proof) as session:expired=core_repo.snapshot(await core_repo.by_key(session,primary[1].user_id,hashlib.sha256(expired_body['client_key'].encode()).digest()))
        check(len(dispatch)==before_calls,'CF022 expired first handoff Flow0')
        direct=await call('POST','/api/flow/analyses',__import__('json').loads(expired.flow_input_json));check(direct.status_code==200,'CF022 existing Flow route seed')
        n=(len(planning),len(resolves),len(dispatch));recovered=data(await call('POST','/api/supervisor/core/requests',expired_body),200)
        check(recovered['flow']['state']=='stored' and (len(planning),len(resolves),len(dispatch))==n,'CF022 expired existing run recovery');mark('handoff_expiry_new_blocked_existing_replay_allowed')
        # Five real admissions consumed the immutable user bucket; the next Sup confirmation
        # must fail in the existing usage control without another run/reservation/dispatch.
        quota_body=confirm(await prepare());before_quota=await counts();before_calls=len(dispatch)
        error(await call('POST','/api/supervisor/core/requests',quota_body),429,'USAGE_LIMIT_EXCEEDED')
        after_quota=await counts();check(after_quota[0]==before_quota[0]+1 and after_quota[1:]==before_quota[1:] and len(dispatch)==before_calls,'CF022 quota blocks new Flow but retains binding')
        check(await sql('SELECT request_count FROM analysis_usage_periods WHERE scope=\'user\' AND owner_user_id=:owner',{'owner':primary[1].user_id})==5,'CF022 user quota actually exhausted');mark('existing_quota_enforced_no_dispatch_or_reservation')
        # Empty policy blocks a fresh admission but keeps the fixed binding; no provider fallback.
        blocked_body=confirm(await prepare());n=len(dispatch)
        with patch.object(settings,'FLOW_USAGE_LIMITS_ENABLED','false'):error(await call('POST','/api/supervisor/core/requests',blocked_body),403)
        check(len(dispatch)==n,'CF022 gate no provider');mark('new_admission_policy_closes_without_provider')
    finally:
        for task in tasks:
            if not task.done():task.cancel()
        if tasks:await asyncio.gather(*tasks,return_exceptions=True)
        app.dependency_overrides.clear();app.dependency_overrides.update(previous)
    return dict(groups=groups,binding_count=await sql('SELECT count(*) FROM supervisor_request_bindings'),analyses=len(engines),dispatches=sum(dispatch.values()),engine_calls=sum(engines.values()),planning_HTTP_calls=len(planning),resolver_calls=len(resolves))
