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


def admission_settings(**values):
    return SimpleNamespace(**(dict(FUNDAMENTAL_USER_DAILY_REQUEST_LIMIT='2',FUNDAMENTAL_SERVICE_DAILY_REQUEST_LIMIT='5')|values))


@pytest.mark.parametrize('field,value',[(name,value) for name in ('FUNDAMENTAL_USER_DAILY_REQUEST_LIMIT','FUNDAMENTAL_SERVICE_DAILY_REQUEST_LIMIT') for value in ('0','-1','01','1.0',' 1','１',True,False,0,-1,1.5,None,'','9223372036854775808',9223372036854775808)])
def test_fundamental_admission_count_limit_strict_values(field,value):
    from src.modules.fundamental.domain.execution_limits import policy,AdmissionPolicyUnavailable
    settings=admission_settings();setattr(settings,field,value)
    with pytest.raises(AdmissionPolicyUnavailable):policy(settings)


def test_fundamental_admission_limits_and_KST_period_boundaries_are_pure():
    from src.modules.fundamental.domain.execution_limits import policy,period,AdmissionPolicy,AdmissionPolicyUnavailable
    assert policy(admission_settings())==AdmissionPolicy(2,5)
    assert policy(admission_settings(FUNDAMENTAL_USER_DAILY_REQUEST_LIMIT=7,FUNDAMENTAL_SERVICE_DAILY_REQUEST_LIMIT=3))==AdmissionPolicy(7,3)
    with pytest.raises(AdmissionPolicyUnavailable):policy(SimpleNamespace())
    before=datetime(2026,11,13,14,59,59,tzinfo=UTC);after=before+timedelta(seconds=1)
    assert period(before)==(datetime(2026,11,12,15,tzinfo=UTC),datetime(2026,11,13,15,tzinfo=UTC))
    assert period(after)==(datetime(2026,11,13,15,tzinfo=UTC),datetime(2026,11,14,15,tzinfo=UTC))
    with pytest.raises(AdmissionPolicyUnavailable):period(before.replace(tzinfo=None))


@pytest.mark.parametrize('service_count,owner_count,code',[(5,2,None),(6,2,'USAGE_LIMIT_EXCEEDED'),(5,3,'USAGE_LIMIT_EXCEEDED'),(0,0,'SERVICE_UNAVAILABLE')])
async def test_fundamental_limiter_counts_insert_and_preserves_captured_policy(service_count,owner_count,code):
    from src.modules.fundamental.application.execution_limit_control import FundamentalExecutionLimitControl
    events=[]
    async def scalar(statement):
        events.append(str(statement))
        return 'read committed' if len(events)==1 else True
    async def execute(statement):
        events.append(str(statement));return SimpleNamespace(one=lambda:(service_count,owner_count))
    session=SimpleNamespace(scalar=scalar,execute=execute,commit=AsyncMock(),rollback=AsyncMock())
    settings=admission_settings();control=FundamentalExecutionLimitControl(session,FundamentalAnalysisError,settings)
    assert control.new_values(None,{'id':uuid4()})=={}
    settings.FUNDAMENTAL_USER_DAILY_REQUEST_LIMIT='100';settings.FUNDAMENTAL_SERVICE_DAILY_REQUEST_LIMIT='100'
    value=row()
    if code:
        with pytest.raises(FundamentalAnalysisError) as error:await control.reserve(value,value.started_at)
        assert error.value.code.value==code
    else:await control.reserve(value,value.started_at)
    assert len(events)==3 and 'current_setting' in events[0] and 'pg_try_advisory_xact_lock' in events[1]
    assert 'count(*)' in events[2] and 'state' not in events[2] and 'fundamental_analysis_runs' in events[2]
    await control.observe(value,b'?',{'private':'ignored'})
    assert len(events)==3 and session.commit.await_count==session.rollback.await_count==0


@pytest.mark.parametrize('isolation,locked',[('repeatable read',True),('serializable',True),(None,True),('read committed',False),('read committed',None)])
async def test_fundamental_limiter_rejects_unfresh_isolation_or_busy_without_count_retry(isolation,locked):
    from src.modules.fundamental.infrastructure.analysis_repository import admission_counts,AdmissionCountUnavailable,ADMISSION_LOCK_KEY
    seen=[]
    async def scalar(statement):seen.append(statement);return isolation if len(seen)==1 else locked
    session=SimpleNamespace(scalar=scalar,execute=AsyncMock())
    with pytest.raises(AdmissionCountUnavailable):await admission_counts(session,uuid4(),datetime.now(UTC))
    assert len(seen)==(2 if isolation=='read committed' else 1) and session.execute.await_count==0
    assert ADMISSION_LOCK_KEY==0x466E644C696D6974
    if len(seen)==2:assert ADMISSION_LOCK_KEY in seen[1].compile().params.values()


async def test_fundamental_existing_key_observation_skips_missing_limits_and_new_dispatch(monkeypatch):
    value=row();session=SimpleNamespace(commit=AsyncMock(),rollback=AsyncMock())
    service=FundamentalAnalysisService(session,principal=None,client=SimpleNamespace(analyze_fundamental=AsyncMock()),limit_settings=SimpleNamespace())
    service._authorize=AsyncMock();service.principal=SimpleNamespace(user_id=value.owner_user_id)
    monkeypatch.setattr(service.profile.repository,'by_key',AsyncMock(return_value=value))
    monkeypatch.setattr(service.profile.repository,'expire',AsyncMock())
    service.usage_control.new_values=lambda *args:(_ for _ in ()).throw(AssertionError('Replay must not parse policy'))
    result=await service.post(dict(ticker='005930',question='합성 재무 질문',idempotency_key='same-key',allow_analysis=True),uuid4())
    assert result.analysis_id==value.id and service.client.analyze_fundamental.await_count==0


async def test_fundamental_new_missing_stock_is_explicit_eligibility_error(monkeypatch):
    session=SimpleNamespace(scalar=AsyncMock(return_value=None),commit=AsyncMock(),rollback=AsyncMock())
    service=FundamentalAnalysisService(session,principal=None,client=None,limit_settings=admission_settings())
    service._authorize=AsyncMock()
    service.principal=SimpleNamespace(user_id=uuid4())
    monkeypatch.setattr(service.profile.repository,'by_key',AsyncMock(return_value=None))
    with pytest.raises(FundamentalAnalysisError) as error:
        await service.post(dict(ticker='005930',question='질문',idempotency_key='key',allow_analysis=True),uuid4())
    assert error.value.code.value=='FEATURE_UNAVAILABLE' and session.commit.await_count==0


# CF061: actual middleware with controlled ASGI IO and deterministic timer delivery.
# No network, database, wall-clock waits or production timer configuration.
class CF061Clock:
    def __init__(self, monkeypatch):
        self.now = 1000.0
        self.loop = asyncio.get_running_loop()
        self.original = asyncio.timeout_at
        self.timers, self.deadlines = [], []
        monkeypatch.setattr(asyncio, 'get_running_loop', lambda: self)
        monkeypatch.setattr(asyncio, 'timeout_at', self.timeout_at)

    def __getattr__(self, name):
        return getattr(self.loop, name)

    def time(self):
        return self.now

    def timeout_at(self, deadline):
        clock = self
        self.deadlines.append(deadline)
        class ControlledTimeout:
            active = False
            def __init__(self):
                self.timer = clock.original(None)
            async def __aenter__(self):
                await self.timer.__aenter__()
                self.active = True
                clock.timers.append((deadline, self))
                if deadline <= clock.now:
                    self.timer.reschedule(clock.loop.time() - 1)
                return self
            async def __aexit__(self, *args):
                self.active = False
                return await self.timer.__aexit__(*args)
            def expired(self):
                return self.timer.expired()
        return ControlledTimeout()

    def jump(self, seconds):
        self.now += seconds

    async def elapse(self, seconds):
        self.jump(seconds)
        for deadline, context in self.timers:
            if context.active and not context.expired() and deadline <= self.now:
                context.timer.reschedule(self.loop.time() - 1)
        await asyncio.sleep(0)
        await asyncio.sleep(0)


def cf061_boundary(monkeypatch, inner, *, method='POST', path='/api/fundamental/analyses'):
    from src.shared.http.access_boundary import AccessBoundary
    from src.shared.config import settings
    from src.modules.auth.api import router as auth
    monkeypatch.setattr(settings, 'FUNDAMENTAL_ANALYSIS_ENABLED', True)
    monkeypatch.setattr(auth, 'configured', lambda: True)
    h = SimpleNamespace(scope=dict(type='http', asgi={'version':'3.0'}, http_version='1.1',
        method=method, path=path, raw_path=path.encode(), query_string=b'', scheme='http',
        server=('synthetic.invalid',80), client=('127.0.0.1',1),
        headers=[(b'content-type',b'application/json')]), sent=[])
    h.raw = json.dumps(dict(ticker='005930', question='synthetic', idempotency_key='key', allow_analysis=True)).encode()
    async def receive():
        return dict(type='http.request', body=h.raw, more_body=False)
    async def send(message):
        h.sent.append(message)
    h.receive, h.send = receive, send
    async def run():
        await AccessBoundary(inner)(h.scope, h.receive, h.send)
    h.run = run
    return h


def cf061_reply(h, status, code=None):
    starts = [m for m in h.sent if m['type']=='http.response.start']
    assert len(starts)==1 and starts[0]['status']==status
    headers = dict(starts[0]['headers'])
    assert headers[b'cache-control']==b'private, no-store' and headers[b'vary']==b'Cookie, Origin'
    if code:
        body = json.loads(b''.join(m.get('body',b'') for m in h.sent if m['type']=='http.response.body'))
        assert body['error']['code']==code and body['request_id']==str(h.scope['state']['cf003_request_id'])


@pytest.mark.parametrize('trickle', [False, True])
async def test_cf061_first_body_deadline_not_renewed_per_chunk(monkeypatch, trickle):
    inner = AsyncMock()
    h = cf061_boundary(monkeypatch, inner)
    clock = CF061Clock(monkeypatch)
    pieces = 0
    async def receive():
        nonlocal pieces
        pieces += 1
        await clock.elapse(8 if trickle else 16)
        return dict(type='http.request', body=b' ', more_body=True)
    h.receive = receive
    await h.run()
    cf061_reply(h, 503, 'SERVICE_UNAVAILABLE')
    inner.assert_not_awaited()
    assert pieces==(2 if trickle else 1)
    assert clock.deadlines==[1065,1015,1065]


@pytest.mark.parametrize('chunk', [b'x'*4097, bytearray(b'{}'), 'not bytes', None])
async def test_cf061_bad_chunk_rejected_before_downstream(monkeypatch, chunk):
    inner = AsyncMock()
    h = cf061_boundary(monkeypatch, inner)
    async def receive():
        return dict(type='http.request', body=chunk)
    h.receive=receive
    await h.run()
    cf061_reply(h,422,'INPUT_INVALID')
    inner.assert_not_awaited()


@pytest.mark.parametrize('size', [4096,4097])
async def test_cf061_cumulative_boundary_and_exact_body_forwarded_once(monkeypatch,size):
    from starlette.responses import JSONResponse
    observed=[]
    async def inner(scope,receive,send):
        observed.append(await receive())
        await JSONResponse({'ok':True})(scope,receive,send)
    h=cf061_boundary(monkeypatch,inner)
    raw=h.raw+b' '*(size-len(h.raw))
    # Distinct position, rather than content, determines the final chunk.
    count=0
    async def chunks():
        nonlocal count
        count+=1
        return dict(type='http.request',body=raw[:2048] if count==1 else raw[2048:],more_body=count==1)
    h.receive=chunks
    await h.run()
    if size==4096:
        cf061_reply(h,200)
        assert observed==[dict(type='http.request',body=raw,more_body=False)]
    else:
        cf061_reply(h,422,'INPUT_INVALID');assert observed==[]


@pytest.mark.parametrize('method,path', [('POST','/api/fundamental/analyses'),('GET','/api/fundamental/analyses/'+str(uuid4())),('DELETE','/api/fundamental/reports/'+str(uuid4()))])
async def test_cf061_total_deadline_includes_body_and_downstream_cleanup(monkeypatch,method,path):
    closed=[]
    async def inner(scope,receive,send):
        try:
            await clock.elapse(54)
            await asyncio.Event().wait()
        finally:
            closed.append('session_closed')
    h=cf061_boundary(monkeypatch,inner,method=method,path=path)
    clock=CF061Clock(monkeypatch)
    if method=='POST':
        original=h.receive
        async def receive():
            await clock.elapse(12)
            return await original()
        h.receive=receive
    else:
        clock.jump(12)  # The middleware still fixes a new first-ingress timestamp.
    task=asyncio.create_task(h.run())
    for _ in range(5):await asyncio.sleep(0)
    if not task.done():await clock.elapse(12)
    await task
    cf061_reply(h,503,'SERVICE_UNAVAILABLE')
    assert closed==['session_closed']
    state=h.scope['state'];assert state['fundamental_deadline']==state['fundamental_started_at']+65
    assert clock.deadlines[-1]==state['fundamental_started_at']+70


async def test_cf061_real_route_dependency_session_unwinds_on_auth_wait(monkeypatch):
    from fastapi import FastAPI
    from src.modules.fundamental.api import analysis_router as routes
    events=[]
    async def session():
        events.append('opened')
        try:yield SimpleNamespace()
        finally:events.append('rollback_and_close')
    async def principal(*args,**kwargs):
        await clock.elapse(66)
        pytest.fail('auth must be cancelled before native service construction')
    monkeypatch.setattr(routes,'request_principal',principal)
    app=FastAPI();app.include_router(routes.router)
    app.dependency_overrides[routes.get_session]=session
    h=cf061_boundary(monkeypatch,app);clock=CF061Clock(monkeypatch)
    await h.run()
    cf061_reply(h,503,'SERVICE_UNAVAILABLE')
    assert events==['opened','rollback_and_close']


@pytest.mark.parametrize('started', [False,True])
async def test_cf061_external_cancel_preserved_and_no_second_response(monkeypatch,started):
    entered=asyncio.Event();closed=[]
    async def inner(scope,receive,send):
        try:
            if started:await send(dict(type='http.response.start',status=200,headers=[]))
            entered.set();await asyncio.Event().wait()
        finally:closed.append(1)
    h=cf061_boundary(monkeypatch,inner);task=asyncio.create_task(h.run())
    await entered.wait();task.cancel()
    with pytest.raises(asyncio.CancelledError):await task
    assert closed==[1] and len(h.sent)==int(started)


@pytest.mark.parametrize('point', ['body','downstream'])
async def test_cf061_internal_timeouterror_is_not_own_timeout(monkeypatch,point):
    sentinel=TimeoutError('synthetic internal failure')
    async def fail(*args):raise sentinel
    h=cf061_boundary(monkeypatch,fail)
    if point=='body':h.receive=fail
    with pytest.raises(TimeoutError) as caught:await h.run()
    assert caught.value is sentinel and h.sent==[]


async def test_cf061_disconnect_propagates_without_error_response(monkeypatch):
    inner=AsyncMock();h=cf061_boundary(monkeypatch,inner)
    async def receive():return {'type':'http.disconnect'}
    h.receive=receive
    with pytest.raises(asyncio.CancelledError):await h.run()
    inner.assert_not_awaited();assert h.sent==[]


@pytest.mark.parametrize('partial', [False,True])
async def test_cf061_response_already_started_then_timeout_aborts(monkeypatch,partial):
    closed=[]
    async def inner(scope,receive,send):
        try:
            await send(dict(type='http.response.start',status=200,headers=[]))
            if partial:await send(dict(type='http.response.body',body=b'partial',more_body=True))
            await clock.elapse(66)
        finally:closed.append(1)
    h=cf061_boundary(monkeypatch,inner);clock=CF061Clock(monkeypatch)
    with pytest.raises(TimeoutError):await h.run()
    assert [m['type'] for m in h.sent]==['http.response.start']+(['http.response.body'] if partial else [])
    assert closed==[1]


@pytest.mark.parametrize('failure', [RuntimeError('synthetic send failure'),TimeoutError('synthetic transport timeout'),asyncio.CancelledError()])
async def test_cf061_start_attempt_failure_is_never_retried(monkeypatch,failure):
    async def inner(scope,receive,send):await send(dict(type='http.response.start',status=200,headers=[]))
    h=cf061_boundary(monkeypatch,inner)
    async def send(message):
        h.sent.append(message)
        raise failure
    h.send=send
    with pytest.raises(type(failure)) as caught:await h.run()
    assert caught.value is failure and len(h.sent)==1


async def test_cf061_cleanup_past_response_deadline_never_starts_error(monkeypatch):
    closed=[]
    async def inner(scope,receive,send):
        try:await clock.elapse(66)
        finally:
            clock.jump(5);closed.append(1)
    h=cf061_boundary(monkeypatch,inner);clock=CF061Clock(monkeypatch)
    with pytest.raises(TimeoutError):await h.run()
    assert h.sent==[] and closed==[1] and clock.deadlines==[1065,1015]


async def test_cf061_error_send_bounded_by_original70_and_never_retried(monkeypatch):
    async def inner(scope,receive,send):await clock.elapse(66)
    h=cf061_boundary(monkeypatch,inner);clock=CF061Clock(monkeypatch)
    async def send(message):
        h.sent.append(message)
        await clock.elapse(5)
    h.send=send
    with pytest.raises(TimeoutError):await h.run()
    assert len(h.sent)==1 and h.sent[0]['status']==503 and clock.deadlines[-1]==1070


@pytest.mark.parametrize('phase', ['body','processing','send'])
async def test_cf061_late_waiter_cannot_accept_after_fixed_deadline(monkeypatch,phase):
    from starlette.responses import JSONResponse
    async def inner(scope,receive,send):
        if phase=='processing':clock.jump(66)
        await JSONResponse({'ok':True})(scope,receive,send)
    h=cf061_boundary(monkeypatch,inner);clock=CF061Clock(monkeypatch)
    if phase=='body':
        original=h.receive
        async def receive():
            clock.jump(16);return await original()
        h.receive=receive
    if phase=='send':
        async def send(message):
            h.sent.append(message);clock.jump(66)
        h.send=send
        with pytest.raises(TimeoutError):await h.run()
        assert len(h.sent)==1
    else:
        await h.run();cf061_reply(h,503,'SERVICE_UNAVAILABLE')


async def test_cf061_untrusted_state_cannot_extend_deadlines_and_fast_path_unchanged(monkeypatch):
    from starlette.responses import JSONResponse
    async def inner(scope,receive,send):await JSONResponse({'ok':True})(scope,receive,send)
    h=cf061_boundary(monkeypatch,inner);clock=CF061Clock(monkeypatch)
    h.scope['state']={'fundamental_started_at':999999,'fundamental_deadline':999999}
    await h.run();cf061_reply(h,200)
    assert h.scope['state']['fundamental_started_at']==1000 and h.scope['state']['fundamental_deadline']==1065
    assert clock.deadlines==[1065,1015]
    assert domain.SPEC['deadline_seconds']==60 and domain.SPEC['http_timeout_seconds']==65 and domain.SPEC['bff_timeout_seconds']==70
    assert domain.SPEC['dispatch_retries']==0


async def test_cf061_oversized_chunk_never_reaches_accumulation_copy(monkeypatch):
    from src.shared.http import access_boundary as boundary
    copies=[]
    class TrackedBuffer(bytearray):
        def extend(self,chunk):
            copies.append(len(chunk));return super().extend(chunk)
    monkeypatch.setattr(boundary,'bytearray',TrackedBuffer,raising=False)
    h=cf061_boundary(monkeypatch,AsyncMock());h.raw=b'x'*4097
    await h.run();cf061_reply(h,422,'INPUT_INVALID')
    assert copies==[]


async def test_cf061_body_timeout_error_send_has_no_extra70_window(monkeypatch):
    h=cf061_boundary(monkeypatch,AsyncMock());clock=CF061Clock(monkeypatch)
    async def receive():await clock.elapse(16)
    async def send(message):
        h.sent.append(message);await clock.elapse(50)
    h.receive,h.send=receive,send
    with pytest.raises(TimeoutError):await h.run()
    assert len(h.sent)==1 and clock.deadlines==[1065,1015,1065]


@pytest.mark.parametrize('case,status,code', [('feature',403,'FEATURE_UNAVAILABLE'),('auth',401,'AUTH_REQUIRED'),('media',422,'INPUT_INVALID'),('json',422,'INPUT_INVALID'),('uuid',422,'INPUT_INVALID')])
async def test_cf061_existing_early_errors_are_preserved(monkeypatch,case,status,code):
    from src.shared.config import settings
    from src.modules.auth.api import router as auth
    inner=AsyncMock();h=cf061_boundary(monkeypatch,inner)
    if case=='feature':monkeypatch.setattr(settings,'FUNDAMENTAL_ANALYSIS_ENABLED',False)
    if case=='auth':monkeypatch.setattr(auth,'configured',lambda:False)
    if case=='media':h.scope['headers']=[(b'content-type',b'text/plain')]
    if case=='json':h.raw=b'[]'
    if case=='uuid':h.scope.update(method='GET',path='/api/fundamental/analyses/not-uuid')
    await h.run();cf061_reply(h,status,code);inner.assert_not_awaited()


@pytest.mark.parametrize('failure_type',[ValueError,TypeError])
@pytest.mark.parametrize('phase',['start','body'])
async def test_cf061_unsupported_route_error_send_failure_never_retries(monkeypatch,failure_type,phase):
    inner=AsyncMock();h=cf061_boundary(monkeypatch,inner,path='/api/fundamental/reports')
    sentinel=failure_type('synthetic send failure')
    async def send(message):
        h.sent.append(message)
        if message['type']=='http.response.'+phase:raise sentinel
    h.send=send
    with pytest.raises(failure_type) as caught:await h.run()
    assert caught.value is sentinel
    assert sum(m['type']=='http.response.start' for m in h.sent)==1
    assert len(h.sent)==(1 if phase=='start' else 2)
    inner.assert_not_awaited()


@pytest.mark.parametrize('invalid',[False,True])
async def test_cf061_late_synchronous_parser_is_not_accepted_as_result_or_input_error(monkeypatch,invalid):
    inner=AsyncMock();h=cf061_boundary(monkeypatch,inner);clock=CF061Clock(monkeypatch)
    def parse(value):
        clock.jump(16)
        if invalid:raise ValueError('synthetic parse failure')
        return SimpleNamespace()
    monkeypatch.setattr(FundamentalAnalysisRequest,'model_validate',parse)
    await h.run();cf061_reply(h,503,'SERVICE_UNAVAILABLE');inner.assert_not_awaited()
