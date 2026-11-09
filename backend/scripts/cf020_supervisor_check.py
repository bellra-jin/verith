"""Exact closed-source AI loader and owned-PG integration, no provider dependencies."""
import hashlib,importlib.util,importlib.machinery,sys,types
from pathlib import Path

SUPERVISOR_MODULES=('domain.models','domain.planning.interpret','domain.planning.policy','infrastructure.backend.resolve_client','application.planning.planner','application.runtime','api.routes')

def load_planner():
    from scripts.check_safe import CF020_INPUTS
    from scripts.cf015_fundamental_check import load_origins
    load_origins()
    root=Path(__file__).resolve().parents[2]/'ai/src'
    for suffix in ('','domain','domain.planning','infrastructure','infrastructure.backend','application','application.planning','api'):
        name='src.supervisor'+('.'+suffix if suffix else '')
        if name not in sys.modules:
            package=types.ModuleType(name);package.__spec__=importlib.machinery.ModuleSpec(name,None,is_package=True);package.__spec__.submodule_search_locations=[str(root/'supervisor'/suffix.replace('.','/'))];package.__path__=[];sys.modules[name]=package
            parent,_,leaf=name.rpartition('.')
            if parent in sys.modules:setattr(sys.modules[parent],leaf,package)
    for suffix in SUPERVISOR_MODULES:
        name='src.supervisor.'+suffix;relative='ai/src/supervisor/'+suffix.replace('.','/')+'.py';path=root/'supervisor'/ (suffix.replace('.','/')+'.py')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=CF020_INPUTS[relative]:raise RuntimeError('Supervisor source pin mismatch')
        if name not in sys.modules:
            spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
            parent,_,leaf=name.rpartition('.');setattr(sys.modules[parent],leaf,module)
        if Path(sys.modules[name].__spec__.origin).resolve()!=path.resolve():raise RuntimeError('Supervisor source origin mismatch')
    from fastapi import FastAPI
    app=FastAPI();app.include_router(sys.modules['src.supervisor.api.routes'].make_router());return app

async def verify_supervisor(proof):
    from scripts.cf003_admission_check import isolated_application,check
    with isolated_application(proof) as observed:
        result=await _verify(proof)
        check(not any(observed.values()),'CF020 forbidden access')
        return result|{'observed_denials':dict(observed)}

async def _verify(proof):
    import asyncio,httpx
    from contextlib import ExitStack
    from datetime import UTC,datetime
    from unittest.mock import patch
    from uuid import uuid4,UUID
    from sqlalchemy import select,text,update
    from db.models.auth.models import AuthUser
    from db.models.common.stock import Stock
    from db.models.common.stock_alias import StockAlias
    from db.models.flow.analysis_run import FlowAnalysisRun
    from db.session import get_session
    from src.api.main import app
    from src.shared.config import settings
    from src.modules.auth.api import router as auth
    from src.modules.auth.application.session_service import issue_session,csrf_token,revoke_session
    from src.modules.flow.api import query_plan_router,analysis_router
    from src.modules.flow.application.analysis_adapter import FlowAnalysisAdapter
    from src.shared.infrastructure.clients.ai_client import AIClient
    from scripts.cf002_interactive_login import owned_session,safe_print
    from scripts.cf003_admission_check import check
    from scripts.cf012_analysis_check import flow_app,engine_result
    token='cf020-synthetic-service-token-32bytes';groups=[];planning=[];dispatch={};engines={};captured={};mode='normal';fail_stage=False
    held=asyncio.Event();release=asyncio.Event();tasks=[]
    def mark(name):groups.append(name);safe_print({'phase':'cf020_check','label':name,'status':'passed'})
    async def sql(statement,params=None):
        async with owned_session(proof) as session:return await session.scalar(text(statement),params or {})
    async def totals():return [await sql('SELECT count(*) FROM '+t) for t in ('flow_analysis_runs','analysis_usage_reservations','analysis_provider_calls')]
    async def user():
        async with owned_session(proof) as session:
            value=AuthUser(id=uuid4());session.add(value);await session.flush();cookie,principal=await issue_session(session,value);await session.commit();return cookie,principal
    async def request_session():
        async with owned_session(proof) as session:yield session
    async def call(method,path,*,value=None,identity=None,headers=None):
        cookie,principal=identity or primary
        h={'origin':'http://localhost:3200','cookie':auth.SESSION_COOKIE+'='+cookie,'x-csrf-token':csrf_token(principal)}|(headers or {})
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://localhost:8200') as c:return await c.request(method,path,json=value,headers=h)
    def data(response,status):
        check(response.status_code==status,'CF020 HTTP status')
        check(response.headers.get('cache-control')=='private, no-store','CF020 private response')
        result=response.json();check(set(result)=={'request_id','data','error'},'CF020 envelope')
        if status<400:check(result['error'] is None,'CF020 success envelope')
        else:check(result['data'] is None,'CF020 no error result exposure')
        return result['data']
    def analysis_body(query):return dict(ticker='005930',question=query,as_of='2026-11-08T00:00:00Z',idempotency_key=str(uuid4()),allow_analysis=True)
    def engine(request,context):
        id=str(request.analysis_id);engines[id]=engines.get(id,0)+1;captured[id]=request.stock_name
        check(engines[id]==1,'CF020 engine once');return engine_result(request,context)
    planner=load_planner();flow=flow_app(engine)
    def planning_client(*args,**kwargs):
        c=AIClient(*args,**kwargs,transport=httpx.ASGITransport(app=planner));original=c.plan_flow
        async def prepare(payload):
            planning.append(payload['phase'])
            if mode=='revoke' and payload['phase']=='continue':held.set();await release.wait()
            return await original(payload)
        c.plan_flow=prepare;return c
    def analysis_client(*args,**kwargs):
        c=AIClient(*args,**kwargs,transport=httpx.ASGITransport(app=flow));original=c.analyze_flow
        async def analyze(payload):
            id=payload['analysis_id'];dispatch[id]=dispatch.get(id,0)+1;check(dispatch[id]==1,'CF020 transport dispatch once')
            if mode=='same_key':held.set();await release.wait()
            return await original(payload)
        c.analyze_flow=analyze;return c
    original_stage=FlowAnalysisAdapter.stage
    async def stage(self,session,principal,frozen):
        if fail_stage:raise OSError('fixed synthetic publication failure')
        return await original_stage(self,session,principal,frozen)
    async def ledger(key):
        async with owned_session(proof) as session:
            row=await session.scalar(select(FlowAnalysisRun).where(FlowAnalysisRun.key_digest==__import__('hashlib').sha256(key.encode()).digest()))
            return dict(id=row.id,state=row.state,stock_name=row.stock_name,input_json=row.input_json,result_json=row.result_json,attempt_id=row.attempt_id)
    primary=await user();other=await user();revoked=await user()
    async with owned_session(proof) as session:
        session.add_all([Stock(stock_code='005930',stock_name='합성전자',market='KOSPI'),Stock(stock_code='000660',stock_name='합성전자2',market='KOSPI')]);await session.flush()
        for code in ('005930','000660'):session.add(StockAlias(stock_code=code,alias='공유종목',normalized_alias='공유종목',alias_type='ambiguous_group'))
        await session.commit()
    previous=dict(app.dependency_overrides);app.dependency_overrides[get_session]=request_session
    try:
      with ExitStack() as stack:
        for key,value in dict(AI_SERVICE_URL='http://synthetic.invalid',FLOW_ANALYSIS_ENABLED=True,FLOW_SERVICE_TOKEN=token,FLOW_USAGE_LIMITS_ENABLED='true',FLOW_SUPPORTED_TICKERS='005930,000660',FLOW_USER_DAILY_REQUEST_LIMIT='1',FLOW_SERVICE_DAILY_REQUEST_LIMIT='10',FLOW_SERVICE_DAILY_BUDGET_USD='10').items():stack.enter_context(patch.object(settings,key,value))
        stack.enter_context(patch.dict('os.environ',{'FLOW_ANALYSIS_ENABLED':'true','FLOW_SERVICE_TOKEN':token}));stack.enter_context(patch.object(query_plan_router,'AIClient',planning_client));stack.enter_context(patch.object(analysis_router,'AIClient',analysis_client));stack.enter_context(patch.object(FlowAnalysisAdapter,'stage',stage))
        start=await totals();check(start==[0,0,0],'CF020 new database')
        question='005930 외국인 수급'
        prepared=data(await call('POST','/api/flow/plans',value={'query':question}),200)
        check(prepared['status']=='ready_for_confirmation' and prepared['resolution']['stock']['stock_name']=='합성전자','CF020 canonical preparation')
        for h in ({'cookie':''},{'x-csrf-token':'wrong'},{'origin':'https://other.invalid'}):data(await call('POST','/api/flow/plans',value={'query':question},headers=h),401)
        unsupported=data(await call('POST','/api/flow/plans',value={'query':'합성전자 차트'}),200);check(unsupported['status']=='unsupported','CF020 unsupported')
        check(await totals()==start and not dispatch,'CF020 planning creates no ledger or reserve')
        mark('canonical_plan_and_auth_no_execution')
        ambiguous=data(await call('POST','/api/flow/plans',value={'query':'공유종목 외국인 수급'}),200)
        check(ambiguous['status']=='needs_stock_selection' and len(ambiguous['resolution']['candidates'])==2,'CF020 ambiguous candidates')
        selected={'query':'공유종목 외국인 수급','selected_ticker':'005930','candidate_ref':ambiguous['candidate_ref']}
        check(data(await call('POST','/api/flow/plans',value=selected),200)['status']=='ready_for_confirmation','CF020 explicit selection')
        async with owned_session(proof) as session:await session.execute(update(Stock).where(Stock.stock_code=='005930').values(stock_name='접수현재합성전자'));await session.commit()
        check(data(await call('POST','/api/flow/plans',value=selected),200)['status']=='selection_stale','CF020 changed canonical ref')
        check(await totals()==start,'CF020 selection no execution')
        mark('selection_fresh_ref_and_master_change')
        body=analysis_body(question);mode='same_key';held.clear();release.clear()
        async def lost_ack():
            response=await call('POST','/api/flow/analyses',value=body);check(response.status_code==200,'CF020 successful commit before lost ACK')
            raise OSError('fixed synthetic wire ACK loss')
        task=asyncio.create_task(lost_ack());tasks.append(task);await asyncio.wait_for(held.wait(),5)
        loser=data(await call('POST','/api/flow/analyses',value=body),202);id=loser['analysis_id']
        check(loser['state']=='running' and await totals()==[1,1,9],'CF020 one concurrent admission reservation')
        release.set()
        try:await task
        except OSError:pass
        else:check(False,'CF020 lost ACK injected')
        mode='normal';before_plan=len(planning)
        first=data(await call('POST','/api/flow/analyses',value=body),200);check(first['state']=='stored' and first['analysis_id']==id,'CF020 lost ACK replay')
        frozen=await ledger(body['idempotency_key']);check(frozen['stock_name']=='접수현재합성전자' and captured[id]=='접수현재합성전자','CF020 admission name authority')
        async with owned_session(proof) as session:await session.execute(update(Stock).where(Stock.stock_code=='005930').values(stock_name='후속마스터변경'));await session.commit()
        check(data(await call('POST','/api/flow/analyses',value=body),200)==first,'CF020 replay after master change')
        check(await ledger(body['idempotency_key'])==frozen,'CF020 original frozen inputs unchanged')
        check(data(await call('GET','/api/flow/analyses/'+id),200)==first and len(planning)==before_plan,'CF020 GET and replay bypass planner')
        data(await call('POST','/api/flow/analyses',value=body|{'question':'different query'}),409)
        data(await call('POST','/api/flow/analyses',value=body|{'ticker':'000660'}),409)
        data(await call('GET','/api/flow/analyses/'+id,identity=other),404)
        report=await call('GET','/api/flow/reports/'+first['report_id']);check(report.status_code==200 and report.json()['report']['meta']['stock_name']=='접수현재합성전자','CF020 owner report snapshot GET')
        check((await call('GET','/api/flow/reports/'+first['report_id'],identity=other)).status_code==404,'CF020 other owner report hidden')
        data(await call('POST','/api/flow/analyses',value=analysis_body('005930 기관 수급')),429)
        with patch.object(settings,'FLOW_USAGE_LIMITS_ENABLED','false'):
            data(await call('POST','/api/flow/analyses',value=analysis_body(question)),403)
            check(data(await call('POST','/api/flow/analyses',value=body),200)==first,'CF020 disabled new policy keeps replay')
        check(dispatch=={id:1} and engines=={id:1} and await totals()==[1,1,9],'CF020 no extra quota or replay dispatch')
        mark('existing_usage_coordinator_concurrency_ACK_replay_owner')
        fail_stage=True;second_body=analysis_body('005930 기관 수급')
        data(await call('POST','/api/flow/analyses',value=second_body,identity=other),503)
        ready=await ledger(second_body['idempotency_key']);check(ready['state']=='result_ready','CF020 durable snapshot before publication failure')
        result=data(await call('GET','/api/flow/analyses/'+str(ready['id']),identity=other),202);check(result['state']=='result_ready','CF020 GET does not publish')
        fail_stage=False;stored=data(await call('POST','/api/flow/analyses',value=second_body,identity=other),200);check(stored['state']=='stored' and len(engines)==2 and all(v==1 for v in engines.values()),'CF020 snapshot-only recovery')
        check(await totals()==[2,2,18],'CF020 recovery no extra reservation')
        deleted=await call('DELETE','/api/flow/reports/'+first['report_id']);check(deleted.status_code==204,'CF020 owner delete')
        data(await call('GET','/api/flow/analyses/'+id),404);data(await call('POST','/api/flow/analyses',value=body),404)
        check(await totals()==[2,2,18],'CF020 delete retains accounting')
        mark('snapshot_only_publish_recovery_and_deleted_fence')
        mode='revoke';held.clear();release.clear()
        task=asyncio.create_task(call('POST','/api/flow/plans',value={'query':question},identity=revoked));tasks.append(task);await asyncio.wait_for(held.wait(),5)
        async def revoke():
            async with owned_session(proof) as session:await revoke_session(session,revoked[1]);await session.commit()
        await asyncio.wait_for(revoke(),2);release.set();data(await task,401)
        check(await totals()==[2,2,18] and len(engines)==2,'CF020 fresh final session SQL closes publication')
        mark('session_revocation_during_AI_wait')
    finally:
        for task in tasks:
            if not task.done():task.cancel()
        if tasks:await asyncio.gather(*tasks,return_exceptions=True)
        app.dependency_overrides.clear();app.dependency_overrides.update(previous)
    return {'groups':groups,'analyses':len(engines),'dispatches':sum(dispatch.values()),'engine_calls':sum(engines.values()),'planning_HTTP_calls':len(planning),'report_count':await sql('SELECT count(*) FROM flow_reports'),'usage_reservations':2}
