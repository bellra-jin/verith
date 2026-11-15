"""CF-017: fixed copied sources, fake providers, no graph/SDK/env/cache discovery."""
import ast
import asyncio
import hashlib
import importlib.machinery
import importlib.util
import json
from datetime import UTC,date,datetime,timedelta
from pathlib import Path
import sys
import threading
import types
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock,Mock
from uuid import uuid4
import httpx
import pytest
from scripts.check_safe import CF017_INPUTS
from scripts.cf012_analysis_check import flow_app,engine_result
from src.modules.flow.domain import analysis as domain
from src.shared.infrastructure.clients.ai_client import AIClient,AIContractError,AIUnavailableError,AIValidationError,AITimeoutError

ROOT=Path(__file__).resolve().parents[3]
TOKEN='cf017-synthetic-service-token-32bytes'
SECRET='cf017-private-sentinel-never-export'


def source(relative):
    assert relative in CF017_INPUTS
    data=(ROOT/relative).read_bytes()
    assert hashlib.sha256(data).hexdigest()==CF017_INPUTS[relative]
    return data.decode('utf8')


def origins():
    for name in ('agents','agents.flow','agents.flow.api','agents.flow.domain','agents.flow.domain.verification','agents.flow.infrastructure'):
        if name not in sys.modules:
            value=types.ModuleType(name);value.__spec__=importlib.machinery.ModuleSpec(name,None,is_package=True)
            value.__spec__.submodule_search_locations=[str(ROOT/'ai/src'/name.replace('.','/'))]
            value.__path__=[];sys.modules[name]=value
    for suffix in ('domain.observation_window','domain.verification.consecutive','domain.interpretation_claims','domain.models','api.payload','infrastructure.token_cache'):
        name='agents.flow.'+suffix;relative='ai/src/'+name.replace('.','/')+'.py'
        source(relative)
        if name not in sys.modules:
            spec=importlib.util.spec_from_file_location(name,ROOT/relative);value=importlib.util.module_from_spec(spec)
            sys.modules[name]=value;spec.loader.exec_module(value)
        assert Path(sys.modules[name].__spec__.origin).resolve()==(ROOT/relative).resolve()


origins()
CACHE=sys.modules['agents.flow.infrastructure.token_cache']
flow_app(engine_result)
RUNTIME=sys.modules['_cf012_flow.application.execution_runtime']
DeadlineExceeded=sys.modules['src.shared.runtime.deadline'].DeadlineExceeded


def row():
    normalized=domain.canonical({'ticker':'005930','question':'합성 오류 검사','as_of':datetime(2026,11,8,tzinfo=UTC).isoformat()})
    return NS(id=uuid4(),attempt_id=uuid4(),admission_request_id=uuid4(),ticker='005930',stock_name='합성 종목',
        request_json=normalized,input_fingerprint=domain.sha(normalized),as_of=datetime(2026,11,8,tzinfo=UTC),
        candidate_date=domain.candidate(datetime(2026,11,8,tzinfo=UTC)),deadline_at=datetime.now(UTC)+timedelta(seconds=30),spec_json=domain.canonical(domain.SPEC))


def request():return domain.ai_request(row())


async def call(app,body=None,headers=None):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://synthetic.invalid') as client:
        response=await client.post('/internal/flow/analyze',content=json.dumps(request()).encode() if body is None else body,
            headers=headers or {'content-type':'application/json','x-flow-service-token':TOKEN})
    assert response.headers['cache-control']=='no-store'
    assert SECRET not in response.text and SECRET not in str(response.headers)
    return response


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setenv('FLOW_ANALYSIS_ENABLED','true');monkeypatch.setenv('FLOW_SERVICE_TOKEN',TOKEN)


@pytest.mark.parametrize('kind,status,code',[
    ('value',503,'SERVICE_UNAVAILABLE'),('provider',503,'SERVICE_UNAVAILABLE'),('timeout',504,'DEADLINE_EXCEEDED'),
    ('deadline',504,'DEADLINE_EXCEEDED'),('missing',502,'RESULT_CONTRACT_INVALID'),('binding',502,'RESULT_CONTRACT_INVALID'),
    ('nonfinite',502,'RESULT_CONTRACT_INVALID'),('large',502,'RESULT_CONTRACT_INVALID')])
async def test_real_router_distinguishes_execution_and_result(enabled,kind,status,code):
    calls=[]
    def engine(req,context):
        calls.append(1)
        if kind=='value':raise ValueError(SECRET)
        if kind=='provider':raise RuntimeError(SECRET)
        if kind=='timeout':raise TimeoutError(SECRET)
        if kind=='deadline':raise DeadlineExceeded(SECRET)
        if kind=='missing':return {}
        result=engine_result(req,context)
        if kind=='binding':result['input_snapshot']['request']={}
        if kind=='nonfinite':result['payload']['x']=float('nan')
        if kind=='large':result['payload']['x']='x'*2097152
        return result
    response=await call(flow_app(engine));assert response.status_code==status and response.json()['error']['code']==code and calls==[1]


@pytest.mark.parametrize('body',[b'{',b'\xff',b'[]',b'x'*8193,b'['*1100+b']'*1100])
async def test_bad_input_never_invokes_engine(enabled,body):
    calls=[];response=await call(flow_app(lambda *args:calls.append(1)),body)
    assert response.status_code==422 and response.json()['error']['code']=='INPUT_INVALID' and not calls


async def test_gate_auth_and_duplicate_headers_before_engine(monkeypatch):
    calls=[];app=flow_app(lambda *args:calls.append(1))
    assert (await call(app)).status_code==403
    monkeypatch.setenv('FLOW_ANALYSIS_ENABLED','true');monkeypatch.setenv('FLOW_SERVICE_TOKEN',TOKEN)
    assert (await call(app,headers={'content-type':'application/json'})).status_code==401
    assert (await call(app,headers=[('content-type','application/json'),('x-flow-service-token',TOKEN)]*2)).status_code==401
    assert not calls and '_cf012_flow.application.agent' not in sys.modules and '_cf012_flow.config' not in sys.modules


@pytest.mark.parametrize('url,token',[('',TOKEN),('http://[bad',TOKEN),('http://synthetic.invalid:bad',TOKEN),('http://synthetic.invalid:99999',TOKEN),('http://synthetic.invalid:0',TOKEN),('https://999.999.999.999',TOKEN),('https://999.999.999.999/'+SECRET,TOKEN),('http://user:pass@synthetic.invalid',TOKEN),('http://synthetic.invalid/?x=1',TOKEN),('http://synthetic.invalid/#x',TOKEN),('http://synthetic.invalid/path',TOKEN),('http://synthetic.invalid','short'),('http://synthetic.invalid','\ud800'),('http://synthetic.invalid','x'*32+'\n')])
async def test_bad_service_configuration_unavailable_before_send(url,token):
    sent=[]
    with pytest.raises(AIUnavailableError) as caught:await AIClient(url,1,service_token=token,transport=httpx.MockTransport(lambda req:sent.append(req))).analyze_flow({})
    assert not sent and SECRET not in str(caught.value)


@pytest.mark.parametrize('status,body,expected',[
    (401,{},AIUnavailableError),(403,{},AIUnavailableError),(422,{},AIValidationError),(400,{},AIValidationError),(409,{},AIValidationError),
    (500,{},AIUnavailableError),(503,{},AIUnavailableError),(504,{},AITimeoutError),(302,{},AIUnavailableError),
    (502,{'error':{'code':'RESULT_CONTRACT_INVALID'}},AIContractError),(502,{'error':{'code':'INPUT_INVALID'}},AIUnavailableError),
    (502,{'error':'bad'},AIUnavailableError),(200,[],AIContractError)])
async def test_backend_bounded_status_mapping(status,body,expected):
    sent=[]
    def respond(req):
        sent.append(req);assert req.headers['x-flow-service-token']==TOKEN
        return httpx.Response(status,json=body,headers={'location':'https://unapproved.invalid/'+SECRET,'x-private':SECRET})
    with pytest.raises(expected) as caught:
        await AIClient('http://synthetic.invalid',1,service_token=TOKEN,transport=httpx.MockTransport(respond)).analyze_flow({})
    assert len(sent)==1 and SECRET not in str(caught.value)


@pytest.mark.parametrize('status,data,expected',[(200,b'\xff',AIContractError),(200,b'{' ,AIContractError),(200,b'x'*2097153,AIContractError),(502,b'x'*2097153,AIUnavailableError),(502,b'{',AIUnavailableError),(502,b'['*1100+b']'*1100,AIUnavailableError)])
async def test_bad_or_oversize_response(status,data,expected):
    with pytest.raises(expected):await AIClient('http://synthetic.invalid',1,service_token=TOKEN,transport=httpx.MockTransport(lambda req:httpx.Response(status,content=data))).analyze_flow({})


@pytest.mark.parametrize('error',[httpx.ReadTimeout(SECRET),TimeoutError(SECRET),httpx.ConnectError(SECRET)])
async def test_transport_errors_are_fixed(error):
    def send(req):raise error
    with pytest.raises(AITimeoutError if isinstance(error,(httpx.TimeoutException,TimeoutError)) else AIUnavailableError) as caught:
        await AIClient('http://synthetic.invalid',1,service_token=TOKEN,transport=httpx.MockTransport(send)).analyze_flow({})
    assert SECRET not in str(caught.value)


def extract(relative,names,binding):
    tree=ast.parse(source(relative));nodes=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in names]
    assert len(nodes)==len(names) and {n.name for n in nodes}==set(names)
    # Execute only these exact source definitions, never imports/top-level initializers.
    code=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),*nodes],type_ignores=[])
    exec(compile(ast.fix_missing_locations(code),relative,'exec'),binding)
    return binding


def kis(tmp_path,client=None):
    return extract('ai/src/agents/flow/infrastructure/kis_client.py',{'KisError','_issue_token','_get_token','_get_json'},
        dict(httpx=httpx,DeadlineExceeded=DeadlineExceeded,get_token=CACHE.get_token,TokenCacheError=CACHE.TokenCacheError,
             validate_issued_response=CACHE.validate_issued_response,_TOKEN_CACHE_PATH=tmp_path/'legacy.json',time=NS(time=lambda:1000,sleep=Mock()),
             _OAUTH_PATH='/oauth2/tokenP',_QUOTATIONS_PATH='/synthetic',_DAILY_PRICE_PATH='/synthetic-quotes',_TIMEOUT=15.,_RATE_LIMIT_MSG_CD='EGW00201',_RATE_LIMIT_RETRY_WAIT_SEC=.6))


@pytest.mark.parametrize('error',[DeadlineExceeded(SECRET),httpx.ReadTimeout(SECRET),TimeoutError(SECRET)])
async def test_issuer_cache_wrapper_to_HTTP_preserves_deadline(enabled,tmp_path,error):
    code=kis(tmp_path);client=NS(post=Mock(side_effect=error))
    def engine(req,context):code['_get_token'](client,'synthetic-key','synthetic-secret','https://synthetic.invalid',execution_context=context)
    response=await call(flow_app(engine));assert response.status_code==504 and client.post.call_count==1
    assert not list(tmp_path.rglob('*.tmp'))


@pytest.mark.parametrize('error',[ValueError(SECRET),RuntimeError(SECRET)])
async def test_token_non_timeout_is_unavailable(enabled,tmp_path,error):
    code=kis(tmp_path);client=NS(post=Mock(side_effect=error))
    def engine(req,context):code['_get_token'](client,'key','secret','https://synthetic.invalid',execution_context=context)
    assert (await call(flow_app(engine))).status_code==503 and client.post.call_count==1


def test_cache_hit_and_unsafe_files_never_reissue(tmp_path):
    code=kis(tmp_path);client=NS(post=Mock(return_value=NS(status_code=200,json=lambda:{'access_token':'synthetic-token','expires_in':3600})))
    args=(client,'key','secret','https://synthetic.invalid')
    assert code['_get_token'](*args)==code['_get_token'](*args)=='synthetic-token' and client.post.call_count==1
    unsafe=tmp_path/'unsafe';unsafe.symlink_to(tmp_path,target_is_directory=True);code['_TOKEN_CACHE_PATH']=unsafe/'legacy.json'
    with pytest.raises(code['KisError']):code['_get_token'](*args)
    assert client.post.call_count==1


@pytest.mark.parametrize('error',[DeadlineExceeded(SECRET),httpx.ReadTimeout(SECRET),TimeoutError(SECRET)])
async def test_data_timeout_to_HTTP(enabled,tmp_path,error):
    code=kis(tmp_path);client=NS(get=Mock(side_effect=error))
    def engine(req,context):code['_get_json'](client,'/synthetic',{}, {},'synthetic',execution_context=context)
    assert (await call(flow_app(engine))).status_code==504 and client.get.call_count==1


def test_rate_limit_only_once_and_no_raw_error(tmp_path):
    code=kis(tmp_path);wait=Mock();context=NS(timeout=lambda *args:15,check=Mock(),wait_allowed=wait,begin_call=Mock(return_value='synthetic'),http_observed=Mock())
    limited=NS(status_code=500,json=lambda:{'msg_cd':'EGW00201','msg1':SECRET})
    client=NS(get=Mock(side_effect=[limited,limited]))
    with pytest.raises(code['KisError']) as caught:code['_get_json'](client,'/synthetic',{}, {},SECRET,execution_context=context)
    assert SECRET not in str(caught.value) and client.get.call_count==2
    code['time'].sleep.assert_called_once_with(.6);wait.assert_called_once_with(.6)
    context.wait_allowed=Mock(side_effect=DeadlineExceeded(SECRET));client.get.reset_mock();client.get.side_effect=[limited]
    with pytest.raises(DeadlineExceeded):code['_get_json'](client,'/synthetic',{}, {},'fixed',execution_context=context)
    assert client.get.call_count==1


@pytest.mark.parametrize('where',['constructor','invoke'])
async def test_SDK_timeout_binding_to_HTTP(enabled,where):
    class SDKTimeout(Exception):pass
    seen=[]
    class LLM:
        def __init__(self,**kwargs):
            seen.append(kwargs)
            if where=='constructor':raise SDKTimeout(SECRET)
        def invoke(self,prompt):raise SDKTimeout(SECRET)
    binding=extract('ai/src/agents/flow/infrastructure/llm/explain.py',{'explain'},dict(
        ChatOpenAI=LLM,APITimeoutError=SDKTimeout,DeadlineExceeded=DeadlineExceeded,load_dotenv=lambda **kwargs:None,
        _ENV_FILE=None,_PROMPT_PATH=NS(read_text=lambda **kwargs:'{{facts}}'),_facts_to_text=lambda *args:'fixed verified facts',_MODEL='gpt-5.4-mini',_TEMPERATURE=.2))
    def engine(req,context):binding['explain']({},NS(passed=True),{},execution_context=context)
    assert (await call(flow_app(engine))).status_code==504
    assert seen==[dict(model='gpt-5.4-mini',temperature=.2,timeout=seen[0]['timeout'],max_retries=0,max_completion_tokens=1000,n=1,service_tier='default')]


@pytest.mark.parametrize('stop',['timeout','cancel'])
async def test_slot_held_until_actual_worker_exit(stop):
    flow_app(engine_result);dto=sys.modules['_cf012_flow.api.schemas'].FlowAnalysisInput.model_validate(request())
    runtime=sys.modules['_cf012_flow.application.execution_runtime']
    held=threading.Event();release=threading.Event();done=threading.Event();calls=[]
    def engine(req,context):
        calls.append(1);held.set()
        try:release.wait(3);return engine_result(req,context)
        finally:done.set()
    runner=runtime.FlowExecutionRuntime(engine)
    if stop=='timeout':dto=dto.model_copy(update={'deadline_at':datetime.now(UTC)+timedelta(milliseconds=40)})
    task=asyncio.create_task(runner.run(dto))
    try:
        while not held.is_set():await asyncio.sleep(.001)
        if stop=='cancel':task.cancel()
        with pytest.raises(TimeoutError if stop=='timeout' else asyncio.CancelledError):await task
        with pytest.raises(runtime.EngineUnavailable):await runner.run(dto.model_copy(update={'deadline_at':datetime.now(UTC)+timedelta(seconds=10)}))
        assert calls==[1]
    finally:
        release.set()
        while not done.is_set():await asyncio.sleep(.001)
        # Callback/worker finally may run just after engine's done flag.
        for _ in range(100):
            if runtime._SLOT.acquire(blocking=False):runtime._SLOT.release();break
            await asyncio.sleep(.001)
        else:raise AssertionError('slot was not released')


@pytest.mark.parametrize('exception,state,code',[(AIValidationError,'failed','DATA_INSUFFICIENT'),(AIContractError,'failed','RESULT_CONTRACT_INVALID'),(AIUnavailableError,'unknown','SERVICE_UNAVAILABLE'),(AITimeoutError,'unknown','SERVICE_UNAVAILABLE')])
async def test_existing_coordinator_state_mapping_synthetic_only(exception,state,code):
    from src.modules.analysis.application.coordinator import AnalysisCoordinator
    from src.modules.auth.application.session_service import Principal
    token_hash=lambda value:hashlib.sha256(value).hexdigest()
    value=NS(id=uuid4(),state='running',input_fingerprint=token_hash(b'{}'),error_code=None)
    async def admit(session,values):value.claim_digest=values['claim_digest'];return value
    profile=NS(parse=lambda body:body,normalized=lambda body:'{}',operation='fixed',deadline_seconds=120,
        input_clock=lambda body,stamp:{},spec_json=lambda:'{}',preserved_errors=(),admission_errors=(),
        repository=NS(by_key=AsyncMock(return_value=None),admit=AsyncMock(side_effect=admit),expire=AsyncMock()),
        adapter=lambda row,owner:NS(build_request=lambda:{}),view=lambda row:NS(state=row.state,code=row.error_code),
        dispatch=AsyncMock(side_effect=exception(SECRET)))
    session=NS(scalar=AsyncMock(side_effect=[NS(stock_name='synthetic'),datetime.now(UTC)]),commit=AsyncMock(),rollback=AsyncMock())
    principal=Principal(uuid4(),uuid4(),datetime.now(UTC)+timedelta(hours=1),b'x'*32)
    coordinator=AnalysisCoordinator(session,principal=principal,client=None,profile=profile)
    coordinator._authorize=AsyncMock();coordinator._locked=AsyncMock(return_value=value)
    result=await coordinator.post(NS(idempotency_key='same',ticker='005930'),uuid4())
    assert result.state==state and result.code==code
    profile.dispatch.assert_awaited_once();profile.repository.admit.assert_awaited_once();assert session.commit.await_count==2


async def test_sentinel_logs_remain_empty(enabled,tmp_path,capsys,caplog):
    code=kis(tmp_path)
    def engine(req,context):code['_get_json'](NS(get=Mock(return_value=NS(status_code=500,json=lambda:{'msg_cd':SECRET,'msg1':SECRET}))),'/synthetic',{'secret':SECRET},{},SECRET,execution_context=context)
    assert (await call(flow_app(engine))).status_code==503
    captured=capsys.readouterr();assert SECRET not in captured.out+captured.err+caplog.text


async def test_valid_envelope_round_trip_and_fixed_transport_options(enabled,monkeypatch):
    actual=httpx.AsyncClient;options=[]
    def client(*args,**kwargs):options.append(kwargs);return actual(*args,**kwargs)
    monkeypatch.setattr(httpx,'AsyncClient',client)
    value=await AIClient('http://synthetic.invalid',1,service_token=TOKEN,transport=httpx.ASGITransport(app=flow_app(engine_result))).analyze_flow(request())
    assert value['schema_version']==1 and value['payload']['report_id']==value['report_id']
    assert options[0]['follow_redirects'] is False and options[0]['trust_env'] is False and options[0]['timeout']==125


async def test_total_deadline_covers_response_stream(monkeypatch):
    original=asyncio.timeout;budgets=[]
    def timeout(seconds):budgets.append(seconds);return original(.01)
    monkeypatch.setattr(asyncio,'timeout',timeout)
    class Slow(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'{'
            await asyncio.sleep(.05)
            yield b'}'
    with pytest.raises(AITimeoutError):
        await AIClient('http://synthetic.invalid',1,service_token=TOKEN,transport=httpx.MockTransport(lambda req:httpx.Response(200,stream=Slow()))).analyze_flow({})
    assert budgets==[125]


async def test_SDK_generic_ValueError_is_unavailable(enabled):
    class SDKTimeout(Exception):pass
    class LLM:
        def __init__(self,**kwargs):pass
        def invoke(self,prompt):raise ValueError(SECRET)
    binding=extract('ai/src/agents/flow/infrastructure/llm/explain.py',{'explain'},dict(
        ChatOpenAI=LLM,APITimeoutError=SDKTimeout,DeadlineExceeded=DeadlineExceeded,load_dotenv=lambda **kwargs:None,
        _ENV_FILE=None,_PROMPT_PATH=NS(read_text=lambda **kwargs:'{{facts}}'),_facts_to_text=lambda *args:'fixed facts',_MODEL='gpt-5.4-mini',_TEMPERATURE=.2))
    def engine(req,context):binding['explain']({},NS(passed=True),{},execution_context=context)
    assert (await call(flow_app(engine))).status_code==503


@pytest.mark.parametrize('function,output',[('fetch_supply_demand','output2'),('fetch_daily_quotes','output')])
@pytest.mark.parametrize('kind',['business_failure','empty'])
async def test_HTTP200_business_failure_and_empty_are_fixed(enabled,tmp_path,capsys,caplog,function,output,kind):
    code=kis(tmp_path)
    # Exact fetch definitions only; no pandas/module/env import. Error paths stop
    # before dataframe construction and do not stand in for numeric conversion.
    extract('ai/src/agents/flow/infrastructure/kis_client.py',{'fetch_supply_demand','fetch_daily_quotes'},code)
    body={'rt_cd':SECRET,'msg_cd':SECRET,'msg1':SECRET} if kind=='business_failure' else {'rt_cd':'0',output:[]}
    get=Mock(return_value=NS(status_code=200,json=lambda:body))
    class Client:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def get(self,*args,**kwargs):return get(*args,**kwargs)
    code.update(date=date,httpx=NS(Client=Client,TimeoutException=httpx.TimeoutException),
        _load_credentials=lambda:('synthetic-key','synthetic-secret','https://synthetic.invalid'),
        _get_token=lambda *args,**kwargs:'synthetic-token',_auth_headers=lambda *args:{},
        _QUOTATIONS_PATH='/synthetic-supply',_TR_ID='synthetic',_DAILY_PRICE_PATH='/synthetic-quotes',_DAILY_PRICE_TR_ID='synthetic')
    with pytest.raises(code['KisError']) as caught:code[function](SECRET,SECRET)
    assert SECRET not in str(caught.value)
    def engine(req,context):return code[function](SECRET,SECRET,execution_context=context)
    response=await call(flow_app(engine))
    assert response.status_code==503 and get.call_count==2
    capture=capsys.readouterr();assert SECRET not in capture.out+capture.err+caplog.text


def test_all_KIS_explicit_errors_are_fixed_literals():
    tree=ast.parse(source('ai/src/agents/flow/infrastructure/kis_client.py'))
    raises=[n.exc for n in ast.walk(tree) if isinstance(n,ast.Raise) and isinstance(n.exc,ast.Call) and isinstance(n.exc.func,ast.Name) and n.exc.func.id=='KisError']
    assert len(raises)==11
    assert all(len(n.args)==1 and isinstance(n.args[0],ast.Constant) and isinstance(n.args[0].value,str) and not n.keywords for n in raises)


PRODUCTION_KIS='https://openapi.koreainvestment.com:9443'
BAD_KIS_ORIGINS=[
    'https://openapivts.koreainvestment.com:29443',
    'http://openapi.koreainvestment.com:9443',
    'https://openapi.koreainvestment.com',
    'https://openapi.koreainvestment.com:443',
    'https://openapi.koreainvestment.com:99999',
    'https://openapi.koreainvestment.com.evil.invalid:9443',
    'https://evil.invalid:9443',
    'https://'+SECRET+'@openapi.koreainvestment.com:9443',
    'https://user:'+SECRET+'@openapi.koreainvestment.com:9443',
    PRODUCTION_KIS+'/uapi/domestic-stock',PRODUCTION_KIS+'//',
    PRODUCTION_KIS+'?'+SECRET,PRODUCTION_KIS+'?',PRODUCTION_KIS+'#'+SECRET,
    ' '+PRODUCTION_KIS,PRODUCTION_KIS+'\n',
    'https://openapi.koreainvestment.com.:9443',
    'https://openapi.koreainvestment.com%2eevil.invalid:9443',
    'https://oрenapi.koreainvestment.com:9443',
]


def credential_boundary(base_url):
    from urllib.parse import urlsplit
    client=Mock(side_effect=AssertionError('No HTTP client before valid configuration'))
    token=Mock(side_effect=AssertionError('No token/cache before valid configuration'))
    load=Mock()
    values=dict(KIS_API_KEY=SECRET,KIS_API_SECRET=SECRET,KIS_BASE_URL=base_url)
    code=extract('ai/src/agents/flow/infrastructure/kis_client.py',
                 {'KisError','KisConfigurationError','_production_base_url','_load_credentials','fetch_supply_demand','fetch_daily_quotes'},
                 dict(urlsplit=urlsplit,load_dotenv=load,os=NS(getenv=values.get),_ENV_FILE=Path('/synthetic/ai/.env'),httpx=NS(Client=client),date=date,_TIMEOUT=15.,_get_token=token))
    return code,client,token,load


@pytest.mark.parametrize('base_url',BAD_KIS_ORIGINS)
@pytest.mark.parametrize('function',['fetch_supply_demand','fetch_daily_quotes'])
def test_real_only_KIS_origin_declined_before_client_token_cache_or_provider(base_url,function,capsys,caplog):
    code,client,token,load=credential_boundary(base_url);context=NS(check=Mock())
    with pytest.raises(code['KisConfigurationError']) as caught:
        code[function](date(2026,11,6),'000720',execution_context=context)
    assert isinstance(caught.value,code['KisError']) and caught.value.code=='KIS_CONFIGURATION_INVALID'
    assert caught.value.__cause__ is None and SECRET not in str(caught.value) and base_url not in str(caught.value)
    client.assert_not_called();token.assert_not_called();context.check.assert_called_once_with('kis_credentials')
    load.assert_called_once_with(dotenv_path=Path('/synthetic/ai/.env'),override=False)
    capture=capsys.readouterr();assert SECRET not in capture.out+capture.err+caplog.text


@pytest.mark.parametrize('base_url',[PRODUCTION_KIS,PRODUCTION_KIS+'/',PRODUCTION_KIS.upper()+'/'])
def test_production_KIS_origin_preserves_credential_and_normalization_contract(base_url):
    code,client,token,load=credential_boundary(base_url)
    assert code['_load_credentials']()==(SECRET,SECRET,base_url.rstrip('/'))
    client.assert_not_called();token.assert_not_called()


@pytest.mark.parametrize('base_url',[None,False,42,[],{},'',b'https://openapi.koreainvestment.com:9443'])
def test_KIS_origin_parser_rejects_non_string_and_empty_without_input_echo(base_url):
    code,client,token,_=credential_boundary(PRODUCTION_KIS)
    with pytest.raises(code['KisConfigurationError']) as caught:code['_production_base_url'](base_url)
    assert str(caught.value)=='KIS 실전 조회 서버 설정이 올바르지 않습니다.'
    client.assert_not_called();token.assert_not_called()
