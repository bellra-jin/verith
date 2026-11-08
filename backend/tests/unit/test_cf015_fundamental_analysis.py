"""One focused collection: common coordinator and authenticated financial boundary."""
import asyncio,copy,hashlib,inspect,json,sys,threading
from datetime import UTC,datetime,timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
from uuid import UUID,uuid4
import httpx,pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from scripts.cf015_fundamental_check import fundamental_app,engine_result,load_origins
from src.modules.analysis.domain.contracts import AnalysisContractError,strict_json
from src.modules.analysis.application.coordinator import AnalysisCoordinator
from src.modules.fundamental.domain import analysis as domain
from src.modules.fundamental.api.analysis_schemas import FundamentalAnalysisRequest
from src.modules.fundamental.application.analysis_adapter import FundamentalAnalysisAdapter
from src.modules.fundamental.application.analysis_profile import FundamentalProfile
from src.modules.fundamental.application.analysis_service import FundamentalAnalysisService,FundamentalAnalysisError
from src.modules.auth.application.session_service import Principal,AuthenticationRequired
from src.shared.infrastructure.clients.ai_client import AIClient,AIContractError,AIUnavailableError
from tests.unit.test_flow_contract import test_relocation_public_contract_baseline as _baseline
from tests.unit.test_cf012_flow_analysis import test_confirmed_collision_stays_terminal_after_winner_deleted as _collision
from tests.unit.test_cf012_flow_analysis import test_other_integrity_failure_is_not_confirmed_report_collision as _integrity

load_origins()
TOKEN='cf015-public-synthetic-service-token-32bytes'

def row():
    stamp=datetime.now(UTC)-timedelta(seconds=1);text=domain.canonical({'ticker':'005930','question':'합성 재무 질문'})
    return SimpleNamespace(id=uuid4(),admission_request_id=uuid4(),attempt_id=uuid4(),owner_user_id=uuid4(),operation=domain.OPERATION,
        ticker='005930',stock_name='고정 종목명',request_json=text,input_fingerprint=domain.sha(text),as_of=stamp,started_at=stamp,
        deadline_at=stamp+timedelta(seconds=60),spec_json=domain.canonical(domain.SPEC),state='running',claim_digest=b'0'*32,error_code=None)

def dto(value):
    fundamental_app(engine_result)
    from _cf015_fundamental.api.analysis_schemas import FundamentalAnalysisInput
    return FundamentalAnalysisInput.model_validate(domain.ai_request(value))

async def envelope(value,engine=engine_result):
    app=fundamental_app(engine)
    with patch.dict('os.environ',{'FUNDAMENTAL_ANALYSIS_ENABLED':'true','FUNDAMENTAL_SERVICE_TOKEN':TOKEN}):
        return await AIClient('http://synthetic.invalid',65,service_token=TOKEN,transport=httpx.ASGITransport(app=app)).analyze_fundamental(domain.ai_request(value))


def test_existing_public_baseline_wrapper(monkeypatch):_baseline(monkeypatch)
async def test_existing_Flow_collision_wrapper(monkeypatch):await _collision(monkeypatch)
async def test_existing_Flow_other_integrity_wrapper(monkeypatch):await _integrity(monkeypatch)

@pytest.mark.parametrize('change',[{'as_of':'2026-01-01'},{'owner_user_id':str(uuid4())},{'allow_analysis':False},{'allow_analysis':1},{'ticker':'１２３４５６'},{'question':' '},{'question':'\x00'},{'idempotency_key':'가'*100}])
def test_public_four_field_strict_opt_in(change):
    with pytest.raises((ValidationError,ValueError)):
        FundamentalAnalysisRequest.model_validate(dict(ticker='005930',question='질문',idempotency_key='key',allow_analysis=True)|change)

def test_request_time_is_not_fingerprint_or_historical_input():
    body=FundamentalAnalysisRequest(ticker='005930',question='질문',idempotency_key='key',allow_analysis=True)
    profile=FundamentalProfile(FundamentalAnalysisError);stamp=datetime.now(UTC)
    assert profile.input_clock(body,stamp)=={'as_of':stamp}
    assert strict_json(profile.normalized(body))=={'ticker':'005930','question':'질문'}
    assert issubclass(FundamentalAnalysisService,AnalysisCoordinator)
    from src.modules.flow.application.analysis_service import AnalysisService
    assert issubclass(AnalysisService,AnalysisCoordinator)

async def test_real_client_to_AI_router_header_raw_extra_zero_null_and_fixed_request():
    value=row();response=await envelope(value);original=copy.deepcopy(response)
    adapter=FundamentalAnalysisAdapter(value,owner_user_id=value.owner_user_id);frozen=adapter.validate_and_freeze(response)
    assert strict_json(frozen.result_json)==response['output']==original['output']
    assert response['output']['extension']['integer']==9007199254740993
    assert response['output']['ratios']=={'zero':0,'missing':None}
    assert strict_json(frozen.input_json)['kind']=='fundamental.request-context.v1'
    for name in ('input_json','input_sha256','result_json','result_sha256'):setattr(value,name,getattr(frozen,name))
    value.adopted_report_id=frozen.report_id
    assert adapter.from_stored(value)==frozen

@pytest.mark.parametrize('change',['correlation','root','child','ratio','duplicate','nonfinite','snapshot_bool'])
async def test_bad_response_binding_cross_reference_finite(change):
    value=row();response=await envelope(value);raw=response['output'];erd=raw['meta']['erd_payload']
    if change=='correlation':raw['request_id']='wrong'
    elif change=='root':erd['fundamental_report']['stock_code']='000001'
    elif change=='child':erd['report_ratios'][0]['report_id']=str(uuid4())
    elif change=='ratio':erd['report_evidence']=[dict(id=str(uuid4()),report_id=response['report_id'],ratio_id=str(uuid4()))]
    elif change=='duplicate':erd['report_ratios']*=2
    elif change=='nonfinite':raw['confidence']=float('nan')
    else:response['input_snapshot']['schema_version']=True
    with pytest.raises(AnalysisContractError):FundamentalAnalysisAdapter(value,owner_user_id=value.owner_user_id).validate_and_freeze(response)

async def test_optional_projection_lists_and_admission_name_are_preserved(monkeypatch):
    from src.modules.fundamental.application import report_service as service
    value=row();response=await envelope(value)
    for key in ('report_ratios','report_evidence','report_insights','report_filing_snippets'):response['output']['meta']['erd_payload'].pop(key,None)
    adapter=FundamentalAnalysisAdapter(value,owner_user_id=value.owner_user_id);frozen=adapter.validate_and_freeze(response)
    principal=Principal(value.owner_user_id,uuid4(),datetime.now(UTC)+timedelta(hours=1),b'x'*32)
    session=SimpleNamespace(commit=AsyncMock(),rollback=AsyncMock(),flush=AsyncMock())
    writer=AsyncMock();monkeypatch.setattr(service.FundamentalReportService,'stage_report',writer)
    await adapter.stage(session,principal,frozen)
    assert writer.call_args.kwargs['stock_name']==value.stock_name
    root,ratios,evidence,interp,verif,insights,snippets,index=service._projection(response['output'],principal,'질문',value.stock_name,datetime.now(UTC))
    assert ratios==evidence==insights==snippets==[] and root.as_of is None and index.stock_name==value.stock_name
    session.commit.assert_not_awaited();session.rollback.assert_not_awaited()
    with pytest.raises(AuthenticationRequired):await adapter.stage(session,Principal(uuid4(),principal.session_id,principal.expires_at,b'x'*32),frozen)

@pytest.mark.parametrize('kind,status,exception',[('engine',503,AIUnavailableError),('bad',502,AIContractError)])
async def test_engine_failure_is_not_user_input_error(kind,status,exception):
    def engine(request):
        if kind=='engine':raise RuntimeError('private synthetic content must not be public')
        return {'invalid':'private result'}
    value=row();app=fundamental_app(engine)
    with patch.dict('os.environ',{'FUNDAMENTAL_ANALYSIS_ENABLED':'true','FUNDAMENTAL_SERVICE_TOKEN':TOKEN}):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://synthetic.invalid') as client:
            response=await client.post('/internal/fundamental/analyze',json=domain.ai_request(value),headers={'X-Fundamental-Service-Token':TOKEN})
        assert response.status_code==status and 'private' not in response.text
        with pytest.raises(exception):await AIClient('http://synthetic.invalid',65,service_token=TOKEN,transport=httpx.ASGITransport(app=app)).analyze_fundamental(domain.ai_request(value))

async def test_gate_auth_body_fail_before_engine_import(monkeypatch):
    calls=[];app=fundamental_app(lambda request:calls.append(request))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://synthetic.invalid') as client:
        assert (await client.post('/internal/fundamental/analyze',content=b'invalid')).status_code==403
        monkeypatch.setenv('FUNDAMENTAL_ANALYSIS_ENABLED','true');monkeypatch.setenv('FUNDAMENTAL_SERVICE_TOKEN',TOKEN)
        assert (await client.post('/internal/fundamental/analyze',json=domain.ai_request(row()))).status_code==401
        assert (await client.post('/internal/fundamental/analyze',content=b'[]',headers={'X-Fundamental-Service-Token':TOKEN,'content-type':'application/json'})).status_code==422
        assert (await client.post('/internal/fundamental/analyze',json=domain.ai_request(row()),headers=[('X-Fundamental-Service-Token',TOKEN),('X-Fundamental-Service-Token',TOKEN)])).status_code==401
    assert calls==[] and '_cf015_fundamental.application.agent' not in sys.modules

@pytest.mark.parametrize('stop',['timeout','cancel'])
@pytest.mark.parametrize('outcome',['success','failure'])
async def test_inflight_slot_held_until_actual_worker_completion(stop,outcome):
    value=dto(row());runtime_module=sys.modules['_cf015_fundamental.api.execution']
    started=threading.Event();release=threading.Event();done=threading.Event();calls=[]
    def engine(request):
        calls.append(1);started.set()
        try:
            release.wait(3)
            if outcome=='failure':raise RuntimeError('synthetic')
            return engine_result(request)
        finally:done.set()
    runtime=runtime_module.FundamentalRuntime(engine)
    if stop=='timeout':value=value.model_copy(update={'deadline_at':datetime.now(UTC)+timedelta(milliseconds=30)})
    task=asyncio.create_task(runtime.run(value))
    while not started.is_set():await asyncio.sleep(.001)
    if stop=='cancel':task.cancel()
    with pytest.raises(TimeoutError if stop=='timeout' else asyncio.CancelledError):await task
    with pytest.raises(runtime_module.FundamentalUnavailable):await runtime.run(dto(row()))
    assert calls==[1] and not done.is_set()
    release.set()
    for _ in range(300):
        if done.is_set() and not runtime_module._WORKERS:break
        await asyncio.sleep(.001)
    assert done.is_set() and not runtime_module._WORKERS
    assert (await runtime_module.FundamentalRuntime(engine_result).run(dto(row())))['output']['score']==0

@pytest.mark.parametrize('constraint,confirmed',[('uq_fundamental_analysis_report',True),('uq_fundamental_analysis_attempt',False),(None,False)])
async def test_only_exact_report_unique_is_terminal_under_claim_fence(constraint,confirmed,monkeypatch):
    value=row();token=b't'*32;value.claim_digest=hashlib.sha256(token).digest();response=await envelope(value)
    original=RuntimeError('private DB original')
    class Cause(Exception):pass
    cause=Cause();cause.sqlstate='23505';cause.constraint_name=constraint;original.__cause__=cause
    failure=IntegrityError(None,None,original)
    session=SimpleNamespace(rollback=AsyncMock(),commit=AsyncMock())
    instance=FundamentalAnalysisService(session,principal=Principal(value.owner_user_id,uuid4(),datetime.now(UTC)+timedelta(hours=1),b'x'*32),client=None);instance._locked=AsyncMock(return_value=value)
    monkeypatch.setattr(instance.profile.repository,'expire',AsyncMock());monkeypatch.setattr(instance.profile.repository,'accept',AsyncMock(side_effect=failure))
    if confirmed:
        result=await instance._receive(value.id,token,response)
        assert result.state=='failed' and result.error.code.value=='RESULT_CONFLICT'
    else:
        with pytest.raises(FundamentalAnalysisError) as caught:await instance._receive(value.id,token,response)
        assert caught.value.code.value=='SERVICE_UNAVAILABLE' and value.state=='running'
    instance.profile.repository.accept.assert_awaited_once()

async def test_Flow_dispatch_publish_contract_error_503_replay_502(monkeypatch):
    from tests.unit.test_cf012_flow_analysis import row as flow_row,envelope as flow_envelope
    from src.modules.flow.application.analysis_service import AnalysisService,AnalysisError
    from src.modules.flow.domain.execution import ContractViolation,ErrorCode
    from src.modules.flow.domain.analysis import sha
    value=flow_row();value.owner_user_id=uuid4();value.operation='flow.analysis.v1';token=b't'*32;value.claim_digest=hashlib.sha256(token).digest()
    value.state='running';value.error_code=None;session=SimpleNamespace(rollback=AsyncMock(),commit=AsyncMock())
    service=AnalysisService(session,principal=Principal(value.owner_user_id,uuid4(),datetime.now(UTC)+timedelta(hours=1),b'x'*32),client=None);service._locked=AsyncMock(return_value=value)
    monkeypatch.setattr(service.profile.repository,'expire',AsyncMock())
    async def accept(session,row,token,**fields):
        for name,item in fields.items():setattr(row,'adopted_report_id' if name=='report_id' else name,item)
        row.state='result_ready';return row
    monkeypatch.setattr(service.profile.repository,'accept',accept)
    service._publish=AsyncMock(side_effect=ContractViolation(ErrorCode.RESULT_CONTRACT_INVALID))
    with pytest.raises(AnalysisError) as caught:await service._receive(value.id,token,flow_envelope(value))
    assert caught.value.code==ErrorCode.SERVICE_UNAVAILABLE
    service._publish.assert_awaited_once_with(value)
    assert ContractViolation in service.profile.admission_errors and ContractViolation not in service.profile.preserved_errors


def test_stage_and_common_composition_do_not_own_commit_or_agent_registry():
    from src.modules.fundamental.application.report_service import FundamentalReportService
    source=inspect.getsource(FundamentalReportService.stage_report)
    assert '.commit(' not in source and '.rollback(' not in source and 'principal=principal' not in source
    root=Path(__file__).resolve().parents[2]
    coordinator=(root/'src/modules/analysis/application/coordinator.py').read_text()
    assert 'src.modules.flow' not in coordinator and 'src.modules.fundamental' not in coordinator
    assert 'adapter.stage(self.session,self.principal,frozen)' in coordinator

async def test_legacy_HTML_and_bulk_paths_are_closed_before_services(monkeypatch):
    from fastapi import FastAPI
    from src.shared.http.access_boundary import AccessBoundary
    from src.shared.config import settings
    from src.modules.auth.api import router as auth
    monkeypatch.setattr(settings,'FUNDAMENTAL_ANALYSIS_ENABLED',True);monkeypatch.setattr(auth,'configured',lambda:True)
    app=FastAPI();app.add_middleware(AccessBoundary)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://synthetic.invalid') as client:
        for method,path in (('GET','/api/fundamental/reports/'+str(uuid4())+'/html'),('POST','/api/fundamental/reports'),('POST','/api/fundamental/reports/save'),('DELETE','/api/fundamental/reports')):
            response=await client.request(method,path)
            assert response.status_code==403 and response.json()['error']['code']=='FEATURE_UNAVAILABLE'
            assert response.headers['cache-control']=='private, no-store'

async def test_public_raw_limit_and_duplicate_headers_fail_closed_before_DB(monkeypatch):
    from starlette.responses import JSONResponse
    from src.shared.http.access_boundary import AccessBoundary
    from src.shared.config import settings
    from src.modules.auth.api import router as auth
    monkeypatch.setattr(settings,'FUNDAMENTAL_ANALYSIS_ENABLED',True);monkeypatch.setattr(auth,'configured',lambda:True)
    seen=[]
    async def inner(scope,receive,send):
        seen.append(await receive());await JSONResponse({'accepted':True})(scope,receive,send)
    app=AccessBoundary(inner);value=json.dumps(dict(ticker='005930',question='synthetic',idempotency_key='key',allow_analysis=True)).encode()
    valid=value+b' '*(4096-len(value))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://synthetic.invalid') as client:
        async def chunks(raw):
            for offset in range(0,len(raw),777):yield raw[offset:offset+777]
        for content,headers in ((valid,{'content-type':'application/json'}),(chunks(valid),{'content-type':'application/json'}),(chunks(valid),{'content-type':'application/json','content-length':'1'})):
            response=await client.post('/api/fundamental/analyses',content=content,headers=headers);assert response.status_code==200
        count=len(seen)
        for content,headers in ((valid+b' ',{'content-type':'application/json'}),(chunks(valid+b' '),{'content-type':'application/json','content-length':'1'}),(value.replace(b'"key"',b'"k\xffy"'),{'content-type':'application/json'}),(value,[('content-type','application/json'),('content-type','application/json')])):
            response=await client.post('/api/fundamental/analyses',content=content,headers=headers)
            assert response.status_code==422 and response.json()['error']['code']=='INPUT_INVALID'
        assert len(seen)==count==3
