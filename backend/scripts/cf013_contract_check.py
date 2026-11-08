"""Small real owned-PG regression for the adapter boundary, not CF-012 replay."""
from unittest.mock import patch
from uuid import UUID,uuid4
from scripts.cf003_admission_check import isolated_application,check
from scripts.cf012_analysis_check import flow_app,engine_result


async def verify_contract(proof):
    with isolated_application(proof) as observed:
        try:result=await _verify(proof)
        except Exception as error:
            from scripts.cf002_interactive_login import safe_print
            frames=[];trace=error.__traceback__
            while trace is not None:
                if trace.tb_frame.f_code.co_filename==__file__:
                    frames.append({'source':'adapter_checker','line':trace.tb_lineno})
                trace=trace.tb_next
            safe_print({'phase':'cf013_checker_failure','type':type(error).__name__ if type(error).__name__ in {'VerificationFailure','RuntimeError','TimeoutError','IntegrityError'} else 'OTHER','frames':frames[-8:],'observed_denials':dict(observed)})
            raise
        check(not any(observed.values()),'CF013 forbidden access')
        result['observed_denials']=dict(observed)
        return result


async def _verify(proof):
    import httpx
    from sqlalchemy import text
    from db.session import get_session
    from db.models.auth.models import AuthUser
    from db.models.common.stock import Stock
    from db.models.flow.analysis_run import FlowAnalysisRun
    from scripts.cf002_interactive_login import owned_session,safe_print
    from src.api.main import app
    from src.shared.config import settings
    from src.modules.auth.api import router as auth
    from src.modules.auth.application.session_service import issue_session,csrf_token
    from src.modules.flow.api import analysis_router
    from src.modules.flow.application.report_service import FlowReportService
    from src.modules.flow.application.analysis_adapter import FlowAnalysisAdapter
    calls={};fail_stage=False;groups=[]
    def engine(request,context):
        key=str(request.analysis_id);calls[key]=calls.get(key,0)+1
        check(calls[key]==1,'CF013 dispatch max1')
        return engine_result(request,context)
    ai=flow_app(engine);original_client=analysis_router.AIClient
    def client(*args,**kwargs):return original_client(*args,**kwargs,transport=httpx.ASGITransport(app=ai))
    original_stage=FlowAnalysisAdapter.stage
    async def stage(adapter,session,principal,frozen):
        reference=await original_stage(adapter,session,principal,frozen)
        if fail_stage:raise RuntimeError('CF013 synthetic post-flush failure')
        return reference
    async def request_session():
        async with owned_session(proof) as session:yield session
    def request():return dict(ticker='005930',question='합성 adapter 저장',as_of='2026-11-08T00:00:00Z',idempotency_key=str(uuid4()),allow_analysis=True)
    async def call(method,path='/api/flow/analyses',*,body=None,other=False):
        headers={'cookie':auth.SESSION_COOKIE+'='+(tb if other else ta),'origin':'http://localhost:3200','x-csrf-token':csrf_token(pb if other else pa)}
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://localhost:8200') as value:
            return await value.request(method,path,json=body,headers=headers)
    def response(value,status,code=None):
        check(value.status_code==status,'CF013 HTTP status')
        check(value.headers.get('cache-control')=='private, no-store','CF013 private response')
        result=value.json();UUID(result['request_id'])
        if code:check(result['error']['code']==code and result['data'] is None,'CF013 safe error')
        else:check(result['error'] is None,'CF013 success')
        return result['data']
    async def row(id):
        async with owned_session(proof) as session:return await session.get(FlowAnalysisRun,UUID(str(id)))
    async def report_counts(report_id):
        values=[]
        async with owned_session(proof) as session:
            for table,key in (('flow_reports','id'),('flow_report_interpretations','report_id'),('flow_report_verifications','report_id'),('agent_reports','agent_report_id')):
                values.append(await session.scalar(text('SELECT count(*) FROM '+table+' WHERE '+key+'=:id'),{'id':report_id}))
        return tuple(values)
    async with owned_session(proof) as session:
        check(await session.scalar(text('SELECT version_num FROM alembic_version'))=='c12001a7e0001','CF013 unchanged revision')
        a,b=AuthUser(id=uuid4()),AuthUser(id=uuid4());session.add_all([a,b]);await session.flush()
        ta,pa=await issue_session(session,a);tb,pb=await issue_session(session,b)
        session.add(Stock(stock_code='005930',stock_name='합성 종목'));await session.commit()
    previous=dict(app.dependency_overrides);app.dependency_overrides[get_session]=request_session
    try:
      with patch.object(settings,'AI_SERVICE_URL','http://synthetic.invalid'),patch.object(settings,'FLOW_ANALYSIS_ENABLED',True),patch.object(settings,'FLOW_SERVICE_TOKEN','cf013-synthetic-service-token-32bytes'),patch.dict('os.environ',{'FLOW_ANALYSIS_ENABLED':'true','FLOW_SERVICE_TOKEN':'cf013-synthetic-service-token-32bytes'}),patch.object(analysis_router,'AIClient',client),patch.object(FlowAnalysisAdapter,'stage',stage):
        body=request();first=response(await call('POST',body=body),200);id=first['analysis_id'];report_id=UUID(first['report_id']);path='/api/flow/analyses/'+id
        check(first['state']=='stored' and calls[id]==1 and await report_counts(report_id)==(1,1,1,1),'CF013 staged publication atomic')
        original=await row(id);frozen=(original.input_json,original.result_json,original.input_sha256,original.result_sha256,original.attempt_id)
        check(response(await call('GET',path),200)==first,'CF013 owner GET')
        check(response(await call('POST',body=body),200)==first and calls[id]==1,'CF013 replay no dispatch')
        again=await row(id);check((again.input_json,again.result_json,again.input_sha256,again.result_sha256,again.attempt_id)==frozen,'CF013 immutable replay')
        response(await call('GET',path,other=True),404,'RESOURCE_NOT_FOUND')
        denied=await call('GET','/api/flow/reports/'+str(report_id),other=True)
        check(denied.status_code==404 and denied.headers.get('cache-control')=='private, no-store','CF013 legacy report owner denied')
        groups.append('adapter_publication_owner_replay_identity_hash')
        fail_stage=True;retry=request();response(await call('POST',body=retry),503,'SERVICE_UNAVAILABLE');fail_stage=False
        from src.modules.flow.infrastructure import analysis_repository
        import hashlib
        async with owned_session(proof) as session:
            pending=await analysis_repository.by_key(session,pa.user_id,hashlib.sha256(retry['idempotency_key'].encode()).digest())
            pending_id=str(pending.id);pending_report=pending.adopted_report_id;snapshot=(pending.input_json,pending.result_json,pending.input_sha256,pending.result_sha256)
            check(pending.state=='result_ready' and all(snapshot),'CF013 snapshot survives flush rollback')
        check(await report_counts(pending_report)==(0,0,0,0) and calls[pending_id]==1,'CF013 publication rollback all0')
        restored=response(await call('POST',body=retry),200);check(restored['state']=='stored' and restored['analysis_id']==pending_id and calls[pending_id]==1,'CF013 resume without AI')
        after=await row(pending_id);check((after.input_json,after.result_json,after.input_sha256,after.result_sha256)==snapshot,'CF013 original snapshots reused')
        check(await report_counts(pending_report)==(1,1,1,1),'CF013 recovered atomic publication')
        groups.append('post_flush_rollback_snapshot_only_resume')
        async with owned_session(proof) as session:check(await FlowReportService(session,principal=pa).delete_report(report_id),'CF013 owner delete')
        deleted=await row(id);check(deleted.state=='deleted' and deleted.input_json is None and deleted.result_json is None and deleted.request_json is None,'CF013 deleted tombstone')
        check((deleted.input_sha256,deleted.result_sha256,deleted.attempt_id)==frozen[2:] and await report_counts(report_id)==(0,0,0,0),'CF013 delete preserves hashes only')
        response(await call('GET',path),404,'RESOURCE_NOT_FOUND');response(await call('POST',body=body),404,'RESOURCE_NOT_FOUND');check(calls[id]==1,'CF013 deleted replay never redispatch')
        groups.append('delete_tombstone_no_replay_visibility')
    finally:app.dependency_overrides.clear();app.dependency_overrides.update(previous)
    safe_print({'phase':'cf013_groups','status':'passed','groups':groups,'analysis_ids':len(calls),'dispatches':sum(calls.values())})
    return {'status':'passed','groups':groups,'analysis_ids':len(calls),'dispatches':sum(calls.values()),'financial_DB_or_provider':'not exercised'}
