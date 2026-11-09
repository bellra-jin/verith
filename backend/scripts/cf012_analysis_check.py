"""Focused CF-012 owned-PG + in-process real ASGI integration, no provider imports."""
import asyncio
from contextlib import contextmanager
from datetime import UTC,datetime,timedelta
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import types
from unittest.mock import patch
from uuid import UUID,uuid4
from scripts.cf003_admission_check import check,isolated_application,migration


def flow_app(engine):
    """Only the exact four reviewed source copies; no searchable AI package path."""
    from fastapi import FastAPI
    from scripts.check_safe import CF012_INPUTS
    root=Path(__file__).resolve().parents[2]
    def module(name,relative):
        path=root/relative
        check(hashlib.sha256(path.read_bytes()).hexdigest()==CF012_INPUTS[relative],'CF012 AI source pin')
        spec=importlib.util.spec_from_file_location(name,path)
        value=importlib.util.module_from_spec(spec);sys.modules[name]=value
        spec.loader.exec_module(value)
        check(Path(value.__spec__.origin).resolve()==path.resolve(),'CF012 AI source origin')
        return value
    for name in ('_cf012_flow','_cf012_flow.api','_cf012_flow.application','src.shared.runtime'):
        if name not in sys.modules:
            value=types.ModuleType(name);value.__path__=[];sys.modules[name]=value
    if 'src.shared.runtime.deadline' not in sys.modules:
        module('src.shared.runtime.deadline','ai/src/shared/runtime/deadline.py')
    module('_cf012_flow.api.schemas','ai/src/agents/flow/api/schemas.py')
    module('_cf012_flow.application.execution_runtime','ai/src/agents/flow/application/execution_runtime.py')
    http=module('_cf012_flow.api.http','ai/src/agents/flow/api/http.py')
    app=FastAPI();app.include_router(http.make_router(engine))
    return app


def zero_call_usage(request):
    """Explicit injected-engine fixture, never a provider execution receipt."""
    from src.modules.analysis.domain.usage import SLOTS,PRICE_ID,call_id
    return dict(schema_version=1,analysis_id=str(request.analysis_id),attempt_id=str(request.attempt_id),
        admission_request_id=str(request.admission_request_id),fingerprint=request.fingerprint,price_id=PRICE_ID,complete=True,
        calls=[dict(id=str(call_id(request.analysis_id,request.attempt_id,provider,action,ordinal)),provider=provider,action=action,
            ordinal=ordinal,attempted=False,state='not_called',input_tokens=None,cached_tokens=None,output_tokens=None,
            input_bytes=None,output_bytes=None,response_model=None,http_status=None) for provider,action,ordinal in SLOTS])


def engine_result(request,context,*,report_id=None):
    """Deterministic synthetic observations, never presented as provider evidence."""
    from tests.fixtures.flow_payload import make_flow_payload
    from src.modules.flow.domain.analysis import UNITS
    payload=make_flow_payload()
    payload['meta'].update(ticker=request.ticker,stock_name=request.stock_name)
    if report_id is not None:payload['report_id']=str(report_id)
    day=payload['meta']['base_date']
    frames={name:[{key:day if key=='date' else 0 for key in units}] for name,units in UNITS.items()}
    return {'payload':payload,'input_snapshot':{'schema_version':1,'request':request.wire(),
        'source':'kis.boundary.frames.v1','observed_at':datetime.now(UTC).isoformat(),
        'confirmed_date':day,'units':UNITS,'frames':frames,**({'provider_usage':zero_call_usage(request)} if 'usage' in request.spec else {})}}


def failure_locations(error):
    result=[];tb=error.__traceback__
    while tb:
        if tb.tb_frame.f_code.co_filename==__file__:
            result.append({'source':'analysis_checker','line':tb.tb_lineno})
        tb=tb.tb_next
    return result[-8:]


async def verify_analysis(proof):
    with isolated_application(proof) as observed:
        try:result=await _verify(proof)
        except Exception as error:
            from scripts.cf002_interactive_login import safe_print
            safe_print({'phase':'cf012_failure','type':type(error).__name__ if type(error).__name__ in {'VerificationFailure','TimeoutError','IntegrityError','RuntimeError'} else 'other','frames':failure_locations(error)})
            raise
        check(not any(observed.values()),'CF012 unexpected forbidden access')
        result['observed_denials']=dict(observed)
        return result


async def _verify(proof):
    import httpx
    from sqlalchemy import select,text,update,event
    from sqlalchemy.ext.asyncio import create_async_engine
    from alembic import command
    from alembic.config import Config
    from db.models.auth.models import AuthUser
    from db.models.common.stock import Stock
    from db.models.flow.analysis_run import FlowAnalysisRun
    from db.session import get_session
    from src.api.main import app
    from src.shared.config import settings
    from src.modules.auth.api import router as auth
    from src.modules.auth.application.session_service import issue_session,csrf_token,revoke_session
    from src.modules.flow.api import analysis_router
    from src.modules.flow.application.analysis_service import AnalysisService,AnalysisError
    from src.modules.flow.application.report_service import FlowReportService,FlowReportIdConflict
    from src.modules.flow.api.schemas import FlowReportSaveRequest
    from src.modules.flow.domain.analysis import canonical,sha,SPEC,OPERATION,candidate,ai_request
    from src.modules.flow.domain.execution import ErrorCode
    from src.modules.flow.infrastructure import analysis_repository as repo
    from scripts.cf002_interactive_login import owned_session,safe_print,_BACKEND
    from tests.fixtures.flow_payload import make_flow_payload
    groups=[];calls={};behavior='normal';chosen_report=None;commit_mode=None;rejections=0
    held=asyncio.Event();release=asyncio.Event()
    def phase(name):safe_print({'phase':'cf012_check','label':name,'status':'started'})
    def mark(name):groups.append(name);safe_print({'phase':'cf012_check','label':name,'status':'passed'})
    async def sql(statement,params=None):
        async with owned_session(proof) as s:return await s.scalar(text(statement),params or {})
    async def request_session():
        async with owned_session(proof) as session:
            n=0;original=session.commit;mode=commit_mode
            async def commit():
                nonlocal n
                n+=1
                if mode and n==mode[0]:
                    if mode[1]=='ack':await original()
                    raise OSError('synthetic commit boundary')
                await original()
            session.commit=commit
            yield session
    def engine(request,context):
        identity=str(request.analysis_id);calls[identity]=calls.get(identity,0)+1
        check(calls[identity]==1,'CF012 one engine per grant')
        result=engine_result(request,context,report_id=chosen_report)
        if behavior=='ticker':result['payload']['meta']['ticker']='000001'
        if behavior=='date':result['input_snapshot']['confirmed_date']='2099-01-01'
        if behavior=='missing':del result['input_snapshot']['frames']['supply'][0]['개인']
        return result
    ai=flow_app(engine);client_type=analysis_router.AIClient
    def client(*args,**kwargs):
        value=client_type(*args,**kwargs,transport=httpx.ASGITransport(app=ai));original=value.analyze_flow
        async def analyze(request):
            result=await original(request)
            if behavior=='revoke':
                async with owned_session(proof) as session:await revoke_session(session,pw)
            return result
        value.analyze_flow=analyze
        return value
    def body(key=None,**change):return {'ticker':'005930','question':'합성 분석 경계','as_of':'2026-11-08T00:00:00Z','idempotency_key':key or str(uuid4()),'allow_analysis':True}|change
    async def call(method,path='/api/flow/analyses',*,value=None,raw=None,token=None,principal=None,headers=None):
        headers={'origin':'http://localhost:3200','cookie':auth.SESSION_COOKIE+'='+(ta if token is None else token),'x-csrf-token':csrf_token(pa if principal is None else principal)}|(headers or {})
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://localhost:8200') as c:
            return await c.request(method,path,json=value,content=raw,headers=headers)
    def response(value,status,code=None):
        nonlocal rejections
        check(value.status_code==status,'CF012 HTTP status')
        check(value.headers.get('cache-control')=='private, no-store' and {'cookie','origin'}<={v.strip().lower() for v in value.headers.get('vary','').split(',')},'CF012 private headers')
        result=value.json();UUID(result['request_id'])
        check(set(result)=={'request_id','data','error'},'CF012 common envelope')
        if code:check(result['error']['code']==code and result['data'] is None,'CF012 safe code');rejections+=1
        else:check(result['error'] is None,'CF012 success envelope')
        return result['data']
    async def ledger(id):
        async with owned_session(proof) as s:return await s.get(FlowAnalysisRun,UUID(str(id)))
    async def counts():return tuple([await sql('SELECT count(*) FROM '+name) for name in ('flow_analysis_runs','flow_reports','agent_reports')])

    phase('new_revision_rollback_and_old_rows')
    check(await sql('SELECT version_num FROM alembic_version')=='c12001a7e0001','CF012 exact revision')
    await migration(proof,'c7001a7e0001',downgrade=True)
    async with owned_session(proof) as s:
        a,b=AuthUser(id=uuid4()),AuthUser(id=uuid4());s.add_all([a,b]);await s.flush()
        ta,pa=await issue_session(s,a);tb,pb=await issue_session(s,b);tr,pr=await issue_session(s,a)
        s.add(Stock(stock_code='005930',stock_name='합성 종목'));await s.commit();await revoke_session(s,pr)
        legacy=make_flow_payload();legacy_id=UUID(legacy['report_id'])
        await FlowReportService(s,principal=pa).save_report(FlowReportSaveRequest(payload=legacy,question='합성 이전 자료'))
    old_tables=('flow_runs','flow_input_snapshots','flow_fake_executions','flow_reports','agent_reports')
    async def old_bytes():return [await sql('SELECT coalesce(jsonb_agg(to_jsonb(r) ORDER BY id)::text,\'[]\') FROM '+name+' r') for name in old_tables]
    # Seed the pre-existing receipt/snapshot/fake tables, without repeating their suites.
    from src.modules.flow.application.run_service import FlowRunService
    from src.modules.flow.api.run_schemas import FlowAdmissionRequest
    from src.modules.flow.application.input_preparation_service import InputPreparationService
    from src.modules.flow.application.fake_execution_service import FakeExecutionService
    async with owned_session(proof) as s:
        receipt=await FlowRunService(s,principal=pa).admit(FlowAdmissionRequest(ticker='005930',question='이전 합성 보존',as_of=datetime(2026,11,8,tzinfo=UTC),idempotency_key=str(uuid4())),uuid4())
        seal=await InputPreparationService(s,principal=pa).prepare(receipt.run_id,'flow.synthetic.full20')
        await FakeExecutionService(s,principal=pa).execute_once(receipt.run_id,allow_fake=True)
    before=await old_bytes();injected=[]
    await proof.preflight();db=create_async_engine(proof.url,connect_args=proof.connection_parameters())
    try:
        async with db.connect() as connection:
            await proof.attest_connection(connection)
            def apply(sync):
                def fail(conn,cursor,statement,params,context,many):
                    if statement.lstrip().upper().startswith('CREATE TABLE FLOW_ANALYSIS_RUNS'):
                        injected.append(True);raise RuntimeError('CF012 injected DDL')
                config=Config(str(_BACKEND/'alembic.ini'));config.set_main_option('script_location',str(_BACKEND/'db/migrations'))
                config.attributes.update(connection=sync,verified_test_mode=True)
                event.listen(sync,'after_cursor_execute',fail)
                try:command.upgrade(config,'head')
                finally:event.remove(sync,'after_cursor_execute',fail)
            try:await connection.run_sync(apply)
            except RuntimeError:await connection.rollback()
            else:raise RuntimeError('CF012 expected DDL rollback')
        check(injected==[True] and await sql("SELECT to_regclass('flow_analysis_runs')") is None,'CF012 exact DDL rollback')
    finally:await db.dispose()
    check(before==await old_bytes(),'CF012 prior rows unchanged after rollback')
    await migration(proof,'head');check(before==await old_bytes(),'CF012 prior rows unchanged after upgrade')
    mark('new_revision_rollback_and_old_rows')
    previous=dict(app.dependency_overrides);app.dependency_overrides[get_session]=request_session
    try:
      with patch.object(settings,'AI_SERVICE_URL','http://synthetic.invalid'),patch.object(settings,'FLOW_ANALYSIS_ENABLED',True),patch.object(settings,'FLOW_SERVICE_TOKEN','cf012-synthetic-service-token-32bytes'),patch.object(analysis_router,'AIClient',client),patch.dict('os.environ',{'FLOW_ANALYSIS_ENABLED':'true','FLOW_SERVICE_TOKEN':'cf012-synthetic-service-token-32bytes'}):
        phase('strict_body_session_owner')
        for change in ({'allow_analysis':False},{'owner_user_id':str(pa.user_id)},{'as_of':'2026-11-08T09:00:00+09:00'},{'as_of':'2099-01-01T00:00:00Z'}):response(await call('POST',value=body(**change)),422,'INPUT_INVALID')
        for raw in (b'{"idempotency_key":"x\xff"}',b'['*1100+b']'*1100,b'{"ticker":"005930","ticker":"005930"}',b'{"x":NaN}'):
            response(await call('POST',raw=raw,headers={'content-type':'application/json'}),422,'INPUT_INVALID')
        for headers,status,code in (({'x-csrf-token':'wrong'},401,'AUTH_REQUIRED'),({'origin':'https://other.invalid'},401,'AUTH_REQUIRED'),({'cookie':''},401,'AUTH_REQUIRED'),({'host':'127.0.0.1:8200'},403,'AUTH_REQUEST_INVALID')):
            response(await call('POST',value=body(),headers=headers),status,code)
        response(await call('POST',value=body(),token=tr,principal=pr),401,'AUTH_REQUIRED')
        mark('strict_body_session_owner')

        phase('store_replay_same_URL_and_concurrent_key')
        request=body();original_body=dict(request);first_response=await call('POST',value=request)
        captured=first_response.json();captured_data=captured.get('data') or {};captured_error=captured_data.get('error') or captured.get('error') or {}
        safe_state=captured_data.get('state');safe_code=captured_error.get('code')
        safe_print({'phase':'cf012_first_response','status':first_response.status_code,
            'state':safe_state if safe_state in {'running','result_ready','stored','failed','unknown'} else 'UNKNOWN',
            'code':safe_code if safe_code in {value.value for value in ErrorCode} else None if safe_code is None else 'UNKNOWN',
            'engine_dispatches':sum(calls.values())})
        first=response(first_response,200);id=first['analysis_id'];path='/api/flow/analyses/'+id
        check(first['state']=='stored' and calls[id]==1,'CF012 stored one dispatch')
        original=await ledger(id);saved=(original.input_json,original.result_json,original.input_sha256,original.result_sha256,original.attempt_id)
        replay=response(await call('POST',value=request),200);check(replay==first and calls[id]==1,'CF012 snapshot replay')
        check(response(await call('GET',path),200)==first,'CF012 same URL')
        response(await call('GET',path,token=tb,principal=pb),404,'RESOURCE_NOT_FOUND')
        response(await call('POST',value=request|{'question':'다른 입력'}),409,'IDEMPOTENCY_CONFLICT')
        race=body();values=await asyncio.gather(call('POST',value=race),call('POST',value=race))
        check(all(v.status_code in {200,202} for v in values),'CF012 race status')
        ids={v.json()['data']['analysis_id'] for v in values};check(len(ids)==1 and calls[next(iter(ids))]==1,'CF012 race winner1')
        mark('store_replay_same_URL_and_concurrent_key')

        phase('commit_ACK_and_publication_rollback')
        for number,kind in ((1,'ack'),(2,'before'),(2,'ack'),(3,'before'),(3,'ack')):
            request=body();seen=sum(calls.values());commit_mode=(number,kind)
            response(await call('POST',value=request),503,'SERVICE_UNAVAILABLE');commit_mode=None
            async with owned_session(proof) as s:
                row=await repo.by_key(s,pa.user_id,hashlib.sha256(request['idempotency_key'].encode()).digest());rid=str(row.id)
                check(row.state==('running' if number==1 or (number==2 and kind=='before') else 'result_ready' if number==2 or kind=='before' else 'stored'),'CF012 durable boundary')
                if row.state=='result_ready':check(await s.scalar(select(FlowAnalysisRun.result_json).where(FlowAnalysisRun.id==row.id)) is not None,'CF012 durable result')
            unresolved=number==1 or (number==2 and kind=='before')
            result=response(await call('POST',value=request),202 if unresolved else 200)
            check(sum(calls.values())==seen+(0 if number==1 else 1),'CF012 recovery dispatch0')
            if not unresolved:check(result['state']=='stored','CF012 publication recovered')
            else:check(result['state']=='running','CF012 no redispatch after rollback/ACK')
        mark('commit_ACK_and_publication_rollback')

        phase('invalid_payload_fence_and_no_publication')
        for behavior in ('ticker','date','missing'):
            result=response(await call('POST',value=body()),200)
            check(result['state']=='failed' and result['report_id'] is None,'CF012 invalid result failed')
            row=await ledger(result['analysis_id']);check(row.input_json is None and row.result_json is None,'CF012 invalid snapshot0')
        behavior='revoke'
        async with owned_session(proof) as s:
            account=await s.get(AuthUser,pa.user_id);tw,pw=await issue_session(s,account);await s.commit()
        before=await counts();response(await call('POST',value=body(),token=tw,principal=pw),401,'AUTH_REQUIRED')
        after=await counts();check(after[0]==before[0]+1 and after[1:]==before[1:],'CF012 revocation during AI prevents publication')
        behavior='normal'
        async with owned_session(proof) as s:
            # Legal historical admission models a completed 120s lease without sleeping.
            stamp=await s.scalar(select(__import__('sqlalchemy').func.clock_timestamp()));start=stamp-timedelta(seconds=121)
            request=body();normalized=canonical({k:v for k,v in request.items() if k not in {'allow_analysis','idempotency_key'}})
            from src.modules.flow.api.analysis_schemas import AnalysisRequest
            normalized=canonical(AnalysisRequest.model_validate(request).normalized_input());secret=b'x'*32
            row=await repo.admit(s,dict(id=uuid4(),owner_user_id=pa.user_id,operation=OPERATION,key_digest=hashlib.sha256(request['idempotency_key'].encode()).digest(),input_fingerprint=sha(normalized),admission_request_id=uuid4(),attempt_id=uuid4(),ticker='005930',stock_name='합성 종목',as_of=datetime(2026,11,8,tzinfo=UTC),candidate_date=candidate(datetime(2026,11,8,tzinfo=UTC)),request_json=normalized,spec_json=canonical(SPEC),claim_digest=hashlib.sha256(secret).digest(),started_at=start,deadline_at=start+timedelta(seconds=120),state='running'))
            rid=row.id;wire=ai_request(row);await s.commit()
        from _cf012_flow.api.schemas import FlowAnalysisInput
        from _cf012_flow.application.execution_runtime import FlowExecutionRuntime
        # Construct a late envelope, without dispatching the expired runtime.
        req=FlowAnalysisInput.model_validate(wire|{'deadline_at':(datetime.now(UTC)+timedelta(seconds=10)).isoformat()})
        late=engine_result(req,None);late['input_snapshot']['request']=wire
        envelope={'schema_version':1,**{k:wire[k] for k in ('analysis_id','attempt_id','admission_request_id','fingerprint')},'report_id':late['payload']['report_id'],'payload':late['payload'],'input_snapshot':late['input_snapshot'],'input_sha256':sha(canonical(late['input_snapshot']))}
        async with owned_session(proof) as s:
            value=await AnalysisService(s,principal=pa,client=None)._receive(rid,secret,envelope)
            check(value.state=='unknown' and value.report_id is None,'CF012 late response fenced')
        mark('invalid_payload_fence_and_no_publication')

        phase('delete_tombstone_legacy_conflict_race')
        # Explicit collision remains terminal even if the legacy winner disappears
        # exactly between stage rollback and the analysis lock re-acquisition.
        chosen_report=legacy_id;original_stage=FlowReportService.stage_report
        deleted=[]
        async def collided(service,request):
            try:return await original_stage(service,request)
            except FlowReportIdConflict:
                await service._session.rollback()
                async with owned_session(proof) as s:
                    check(await FlowReportService(s,principal=pa).delete_report(legacy_id),'CF012 legacy deletion')
                deleted.append(True);raise
        with patch.object(FlowReportService,'stage_report',collided):
            conflict_body=body();response(await call('POST',value=conflict_body),409,'RESULT_CONFLICT')
        check(deleted==[True],'CF012 collision race exercised')
        failed=response(await call('POST',value=conflict_body),200);check(failed['state']=='failed' and failed['report_id'] is None,'CF012 collision stays terminal')
        chosen_report=None
        report_id=UUID(first['report_id'])
        async with owned_session(proof) as s:check(await FlowReportService(s,principal=pa).delete_report(report_id),'CF012 owner deletion')
        row=await ledger(id);check(row.state=='deleted' and row.request_json is None and row.input_json is None and row.result_json is None and row.stock_name is None,'CF012 tombstone clears bodies')
        check((row.input_sha256,row.result_sha256,row.attempt_id)==saved[2:],'CF012 tombstone identities preserved')
        response(await call('GET',path),404,'RESOURCE_NOT_FOUND');response(await call('POST',value=original_body),404,'RESOURCE_NOT_FOUND')
        check(await sql('SELECT count(*) FROM stocks WHERE stock_code=\'005930\'')==1,'CF012 stock preserved')
        mark('delete_tombstone_legacy_conflict_race')
    finally:app.dependency_overrides.clear();app.dependency_overrides.update(previous)
    check(all(v==1 for v in calls.values()),'CF012 engine count all1')
    return {'status':'passed','groups':groups,'rejections':rejections,'engine_dispatches':sum(calls.values()),'analysis_ids':len(calls),'transport':'ASGI-only deterministic Flow engine; real owned PG'}
