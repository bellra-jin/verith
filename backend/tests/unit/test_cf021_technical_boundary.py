"""One exact protected collection: synthetic boundary, no provider/DB/config imports."""
import asyncio
import ast
import copy
import hashlib
import importlib.abc
import importlib.machinery
import importlib.util
import json
from datetime import datetime, timedelta
from pathlib import Path
import sys
import types
import threading
import time
from uuid import UUID
from unittest.mock import patch

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[3]
ATTEMPTS = []
FORBIDDEN = ('dotenv', 'src.shared.config', 'src.api.main', 'src.api.dependencies',
             'src.agents.technical.config', 'src.agents.technical.application.agent',
             'src.agents.technical.application.orchestration', 'src.agents.technical.infrastructure',
             'src.agents.technical.application.fallback', 'src.agents.news',
             'src.supervisor.config', 'src.supervisor.application.execution',
             'openai', 'langchain_openai', 'langgraph', 'redis', 'kis', 'pandas')


class ImportSentinel(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if any(fullname == n or fullname.startswith(n + '.') for n in FORBIDDEN):
            ATTEMPTS.append(fullname)
            raise AssertionError('Forbidden Technical boundary import')


SENTINEL = ImportSentinel()
sys.meta_path.insert(0, SENTINEL)
# Bootstrap deliberately supplies a harmless dotenv stub. Removing that loaded stub
# makes an accidental source import observable by the pre-collection sentinel.
sys.modules.pop('dotenv', None)


def _package(name, location):
    if name in sys.modules:
        return
    module = types.ModuleType(name)
    module.__spec__ = importlib.machinery.ModuleSpec(name, None, is_package=True)
    module.__spec__.submodule_search_locations = [str(location)]
    module.__path__ = []
    sys.modules[name] = module
    parent, _, leaf = name.rpartition('.')
    if parent in sys.modules:
        setattr(sys.modules[parent], leaf, module)


def _load(name, relative, pins):
    path = ROOT / relative
    assert hashlib.sha256(path.read_bytes()).hexdigest() == pins[relative]
    parent = name.rpartition('.')[0]
    # Namespace locations are explicit, while __path__ remains closed to discovery.
    components = parent.split('.')
    for index in range(1, len(components) + 1):
        package = '.'.join(components[:index])
        _package(package, path.parent)
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        setattr(sys.modules[parent], name.rsplit('.', 1)[1], module)
    assert Path(sys.modules[name].__spec__.origin).resolve() == path.resolve()
    return sys.modules[name]


def load_boundary():
    from scripts.check_safe import CF021_INPUTS, CF021_FIXED_INPUTS
    # Keep the pre-existing origin invariant, loading only the same pinned pure six.
    ai = ROOT / 'ai/src'
    for suffix in ('', '.flow', '.flow.api', '.flow.domain', '.flow.domain.verification', '.flow.infrastructure'):
        name = 'agents' + suffix
        _package(name, ai.joinpath(*name.split('.')))
    for suffix in ('domain.observation_window', 'domain.verification.consecutive',
                   'domain.interpretation_claims', 'domain.models', 'api.payload', 'infrastructure.token_cache'):
        _load('agents.flow.' + suffix, 'ai/src/agents/flow/' + suffix.replace('.', '/') + '.py', CF021_INPUTS)
    for name, relative in (
        ('src.modules.analysis.domain.contracts', 'backend/src/modules/analysis/domain/contracts.py'),
        ('src.modules.analysis.domain.agent_envelope', 'backend/src/modules/analysis/domain/agent_envelope.py'),
        ('src.modules.technical.domain.chart_contracts', 'backend/src/modules/technical/domain/chart_contracts.py'),
        ('src.modules.technical.domain.execution_boundary', 'backend/src/modules/technical/domain/execution_boundary.py'),
        ('src.modules.technical.application.boundary_adapter', 'backend/src/modules/technical/application/boundary_adapter.py'),
        ('src.shared.infrastructure.clients.ai_client', 'backend/src/shared/infrastructure/clients/ai_client.py'),
    ):
        _load(name, relative, CF021_FIXED_INPUTS)
    for suffix in ('shared.contracts.agent_envelope', 'shared.runtime.deadline', 'agents.technical.domain.intraday_limits',
                   'agents.technical.domain.models.enums', 'agents.technical.domain.models.ohlcv',
                   'agents.technical.domain.models.chart', 'agents.technical.domain.models.intraday',
                   'agents.technical.domain.models.contracts', 'agents.technical.domain.boundary_contracts',
                   'supervisor.domain.planning.interpret', 'supervisor.application.planning.technical_boundary',
                   'agents.technical.application.boundary_adapter', 'agents.technical.application.boundary_runtime',
                   'agents.technical.application.engine_bridge',
                   'agents.technical.api.routes'):
        _load('src.' + suffix, 'ai/src/' + suffix.replace('.', '/') + '.py', CF021_INPUTS)
    assert not ATTEMPTS
    return sys.modules['src.agents.technical.api.routes']


R = load_boundary()
A = sys.modules['src.agents.technical.domain.boundary_contracts']
B = sys.modules['src.modules.technical.domain.execution_boundary']
AD = sys.modules['src.modules.technical.application.boundary_adapter']
AC = sys.modules['src.modules.analysis.domain.contracts']
C = sys.modules['src.shared.infrastructure.clients.ai_client']
RUN = sys.modules['src.agents.technical.application.boundary_runtime']
BRIDGE = sys.modules['src.agents.technical.application.engine_bridge']
DEADLINE = sys.modules['src.shared.runtime.deadline']
PLAN = sys.modules['src.supervisor.application.planning.technical_boundary']
WIRE = sys.modules['src.modules.analysis.domain.agent_envelope']
FIXTURE = json.loads((ROOT / 'frontend/tests/fixtures/cf021-technical-boundary.json').read_text())
TOKEN = 'cf021-synthetic-token-never-production-32bytes'
PRIVATE = 'cf021-private-sentinel-never-echo'


def request():
    return copy.deepcopy(FIXTURE['request'])


def result():
    return copy.deepcopy(FIXTURE['result'])


@pytest.mark.parametrize('model',[
    sys.modules['src.agents.technical.domain.models.ohlcv'].OHLCV,
    sys.modules['src.agents.technical.domain.models.intraday'].IntradayCandle,
    sys.modules['src.modules.technical.domain.chart_contracts'].OHLCV,
    sys.modules['src.modules.technical.domain.chart_contracts'].IntradayCandle,
])
@pytest.mark.parametrize('field,value',[('open',89),('open',111),('close',89),('close',111)])
def test_candle_open_and_close_outside_range_are_rejected_on_both_boundaries(model,field,value):
    data=dict(open=100,high=110,low=90,close=100,volume=0,trading_value=0)
    data.update(timestamp='2026-06-30T09:00:00',interval='1min') if model.__name__=='IntradayCandle' else data.update(date='2026-06-30')
    data[field]=value;before=copy.deepcopy(data)
    with pytest.raises(ValueError,match=field+' must be within'):
        model.model_validate(data)
    assert data==before  # no clamping or silent repair


@pytest.mark.parametrize('model',[
    sys.modules['src.agents.technical.domain.models.ohlcv'].OHLCV,
    sys.modules['src.agents.technical.domain.models.intraday'].IntradayCandle,
    sys.modules['src.modules.technical.domain.chart_contracts'].OHLCV,
    sys.modules['src.modules.technical.domain.chart_contracts'].IntradayCandle,
])
@pytest.mark.parametrize('prices',[(90,110,90,110),(110,110,90,90),(0,0,0,0),(100.25,100.5,100.0,100.5)])
def test_candle_inclusive_edges_zero_and_fractional_values_are_preserved(model,prices):
    data=dict(zip(('open','high','low','close'),prices),volume=0,trading_value=0)
    if model.__name__=='IntradayCandle':data.update(timestamp='2026-06-30T09:00:00',interval='1min',trading_value=None)
    else:data.update(date='2026-06-30')
    assert model.model_validate(data).model_dump()==data


@pytest.mark.parametrize('module',[A,B])
@pytest.mark.parametrize('field',['open','close'])
def test_invalid_range_candle_cannot_cross_complete_result_boundary(module,field):
    output=result();candle=output['charts'][0]['chart_data']['candles'][0]
    candle[field]=candle['high']+1
    with pytest.raises(ValueError):module.validate_result(output,request())


def binding(value=None):
    value = value or request()
    data = value['data']; ids = data['context']
    as_of = datetime.fromisoformat(data['requested_as_of'])
    context = AC.AnalysisContext(analysis_id=UUID(ids['analysis_id']),
        admission_request_id=UUID(ids['admission_request_id']), attempt_id=UUID(ids['attempt_id']),
        owner_user_id=UUID(FIXTURE['owner_user_id']), operation=data['operation'],
        input_fingerprint=ids['input_fingerprint'], as_of=as_of, deadline_at=as_of + timedelta(seconds=3))
    return AD.TechnicalBoundaryBinding(context=context, report_id=UUID(ids['report_id']),
        request_id=UUID(value['request_id']), trace_id=UUID(value['trace_id']), input_json=B.canonical(value))


def app(engine=None, *, enabled=True, token=TOKEN, timeout=3):
    from fastapi import FastAPI
    value = FastAPI()
    value.include_router(R.make_router(engine=engine, enabled=enabled, service_token=token, timeout=timeout))
    return value


async def fake(payload, *, trace_id):
    assert payload.query == request()['data']['original_query']
    assert payload.stock_name == request()['data']['stock']['stock_name']
    assert payload.request_id == request()['request_id']
    assert trace_id == request()['trace_id']
    return result()


def client(application=None, transport=None, base='http://boundary.invalid', token=TOKEN):
    return C.AIClient(base, 3, transport=transport or httpx.ASGITransport(app=application or app(fake)), service_token=token)


async def post(application, *, body=None, headers=None, path='/internal/technical/boundary'):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=application), base_url='http://boundary.invalid') as c:
        return await c.post(path, content=B.canonical(request()).encode() if body is None else body,
            headers=headers if headers is not None else {'content-type': 'application/json', 'x-technical-service-token': TOKEN})


async def test_actual_backend_asgi_fake_freeze_and_preview_preserve_raw():
    holder = binding(); adapter = AD.TechnicalBoundaryAdapter(holder)
    frozen = await adapter.run(client())
    assert frozen.context is holder.context and frozen.report_id == holder.report_id
    assert frozen.input_json == holder.input_json and frozen.input_sha256 == B.digest(request())
    response = B.decode(frozen.result_json)
    assert response['data']['request_snapshot'] == request()['data']
    assert response['data']['result'] == result()
    assert 'detail_reason' not in response['data']['result']['technical_signals'][0]
    assert type(response['data']['result']['signal']['confidence']) is int
    assert adapter.chart_preview(frozen) == FIXTURE['expected_preview']
    assert response['data']['coverage']['periods'][1] == dict(period='1y',candle_unit='D',start=None,end=None,count=0,status='empty')
    assert response['data']['coverage']['cutoff_validation'] == 'unverified'
    assert response['data']['coverage']['engine_generated_at'] is None
    assert response['data']['execution_mode'] == 'synthetic'
    with pytest.raises(RuntimeError, match='non-persistent'):
        await adapter.stage(object())
    assert not ATTEMPTS


@pytest.mark.parametrize('module', [A, B])
@pytest.mark.parametrize('field,value', [
    ('profile','fundamental.ofs'),('periods',['1d']),('periods',['1y','3m','5y']),
    ('periods',['3m','1y','5y','5y']),('years',3),('financial_scope','OFS')])
def test_unknown_domain_period_and_policy_rejected(module, field, value):
    value_request = request(); value_request['data']['conditions'][field] = value
    with pytest.raises(ValueError): module.parse_request(value_request)


@pytest.mark.parametrize('module',[A,B])
@pytest.mark.parametrize('mutation',['request_id','trace_id','analysis_id','admission_request_id','attempt_id','report_id','fingerprint','stock_code','stock_name','market','query','cutoff','views','operation','owner'])
def test_same_type_request_tampering_rejected(module, mutation):
    value = request()
    if mutation in ('request_id','trace_id'):
        value[mutation] = value['data']['context']['report_id']
    elif mutation in ('analysis_id','admission_request_id','attempt_id','report_id'):
        value['data']['context'][mutation] = value['request_id']
    elif mutation == 'fingerprint': value['data']['context']['input_fingerprint']='0'*64
    elif mutation in ('stock_code','stock_name','market'): value['data']['stock'][mutation]={'stock_code':'000660','stock_name':'changed','market':None}[mutation]
    elif mutation == 'query': value['data']['original_query']='changed'
    elif mutation == 'cutoff': value['data']['requested_as_of']='2026-11-08T00:00:00+00:00'
    elif mutation == 'views': value['data']['requested_views']=['technical','flow']
    elif mutation == 'operation': value['data']['operation']='flow.analysis.v1'
    else: value['data']['owner']=PRIVATE
    with pytest.raises(ValueError): module.parse_request(value)


@pytest.mark.parametrize('module',[A,B])
@pytest.mark.parametrize('mutation',['request_id','trace_id','ticker','as_of','candle_unit','duplicate','period','coercion','boolean','extra','nonfinite','annotation','date_order'])
def test_result_strictness_and_identity(module,mutation):
    value=result()
    if mutation in ('request_id','trace_id'):value[mutation]=request()['data']['context']['analysis_id']
    elif mutation=='ticker':value['ticker']='000660'
    elif mutation=='as_of':value['as_of']='2026-11-08T00:00:00+00:00'
    elif mutation=='candle_unit':value['charts'][0]['chart_data']['candle_unit']='W'
    elif mutation=='duplicate':value['charts'].append(copy.deepcopy(value['charts'][0]))
    elif mutation=='period':value['charts'][0]['period']='1d'
    elif mutation=='coercion':value['charts'][0]['chart_data']['candles'][0]['open']='100'
    elif mutation=='boolean':value['charts'][0]['chart_data']['candles'][0]['volume']=False
    elif mutation=='extra':value['charts'][0]['chart_data']['hidden']=PRIVATE
    elif mutation=='nonfinite':value['technical_signals'][0]['value']=float('inf')
    elif mutation=='annotation':value['charts'][0]['chart_data']['annotations'][0]['source']='llm'
    else:value['charts'][0]['chart_data']['candles'].reverse()
    with pytest.raises(ValueError):module.validate_result(value,request())


@pytest.mark.parametrize('module',[A,B])
@pytest.mark.parametrize('raw',[b'{"a":1,"a":2}',b'{"a":NaN}',b'{"a":Infinity}',b'{"a":1e999}',b'\xff', '{"a":"\\ud800"}', '{"a":1}'.encode('utf-16')])
def test_strict_json_rejects_duplicate_nonfinite_non_utf8(module,raw):
    with pytest.raises(ValueError):module.decode(raw)


@pytest.mark.parametrize('module',[A,B])
def test_defaults_lossless_snapshot_and_allowed_annotation_json(module):
    value=request();del value['data']['conditions']
    value['data']['context']['input_fingerprint']=module.fingerprint(request()['data'])
    module.parse_request(value)
    output=result();output['charts'][0]['chart_data']['annotations'][0]['meta']={'nested':[None,False,0,{'label':'한글'}]}
    module.validate_result(output,value)
    complete=sys.modules['src.agents.technical.application.boundary_adapter'].complete(value,output)
    module.validate_response(complete,value)
    assert 'conditions' not in complete['data']['request_snapshot']
    missing=result();missing['charts']=[]
    coverage=module.validate_result(missing,request())
    assert coverage['available_periods']==[] and all(p['status']=='not_provided' and p['count']==0 and p['start'] is None for p in coverage['periods'])


@pytest.mark.parametrize('mutation',['code','name','market','query','conditions','cutoff','analysis_id','admission_request_id','attempt_id','report_id','input_fingerprint','request_id','trace_id','hash','coverage','observed'])
def test_response_bound_to_original_value_not_only_schema(mutation):
    complete=sys.modules['src.agents.technical.application.boundary_adapter'].complete(request(),result())
    snapshot=complete['data']['request_snapshot']
    if mutation in ('code','name','market'):snapshot['stock'][{'code':'stock_code','name':'stock_name','market':'market'}[mutation]]={'code':'000660','name':'changed','market':None}[mutation]
    elif mutation=='query':snapshot['original_query']='changed'
    elif mutation=='conditions':snapshot['conditions']['profile']='unsupported'
    elif mutation=='cutoff':snapshot['requested_as_of']='2026-11-08T00:00:00+00:00'
    elif mutation in ('analysis_id','admission_request_id','attempt_id','report_id'):snapshot['context'][mutation]='10000000-0000-4000-8000-000000000001'
    elif mutation=='input_fingerprint':snapshot['context'][mutation]='0'*64
    elif mutation in ('request_id','trace_id'):complete[mutation]='10000000-0000-4000-8000-000000000001'
    elif mutation=='hash':complete['data']['request_sha256']='0'*64
    elif mutation=='coverage':complete['data']['coverage']['periods'][0]['count']=3
    else:complete['data']['boundary_observed_at']='not-a-time'
    for module in (A,B):
        with pytest.raises(ValueError):module.validate_response(complete,request())


@pytest.mark.parametrize('query',['삼성전자 수급과 차트','삼성전자 종합 분석','삼성전자 뉴스','시장 차트','삼성전자 어때?','삼성전자 차트 말고 재무','삼성전자 차트 제외','전체 종목 차트'])
def test_internal_plan_never_promotes_mixed_or_ambiguous(query):
    value=request();value['data']['original_query']=query
    value['data']['context']['input_fingerprint']=A.fingerprint(value['data'])
    with pytest.raises(ValueError):PLAN.build_plan(value)


async def test_gate_and_legacy_close_before_auth_body_or_engine():
    calls=[]
    async def forbidden(*a,**kw):calls.append(1);raise AssertionError(PRIVATE)
    for application in (app(forbidden,enabled=False),app(None)):
        response=await post(application,body=b'broken',headers={})
        assert response.status_code==403 and response.json()['error']['code']=='FEATURE_UNAVAILABLE'
    response=await post(app(forbidden),path='/internal/technical/analyze',body=b'broken',headers={})
    assert response.status_code==403 and not calls
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app()),base_url='http://boundary.invalid') as c:
        assert (await c.get('/internal/technical/health')).json()['status']=='ok'
    with pytest.raises(C.AIUnavailableError):await client(transport=httpx.MockTransport(lambda r:calls.append(1))).analyze_technical({})
    assert not calls


@pytest.mark.parametrize('headers',[
    {},{'x-technical-service-token':'wrong'},
    [('x-technical-service-token',TOKEN),('x-technical-service-token',TOKEN)],
])
async def test_auth_before_invalid_json(headers):
    response=await post(app(fake),body=b'broken',headers=headers)
    assert response.status_code==401 and response.json()['error']['code']=='AUTH_REQUIRED'


@pytest.mark.parametrize('headers,body',[
    ({'content-type':'text/plain'},b'{}'),({'content-encoding':'gzip'},b'{}'),
    ([('content-encoding','identity'),('content-encoding','identity')],b'{}'),
    ([('content-type','application/json'),('content-type','application/json')],b'{}'),
    ({'content-length':'16385'},b'{}'),({'content-length':'wrong'},b'{}'),
    ([('content-length','2'),('content-length','2')],b'{}'),({'content-length':'1'},b'{}'),
    ({},b'x'*16385),({},b'{"schema_version":1,"schema_version":2}'),
])
async def test_bounded_strict_headers_and_body(headers,body):
    values=[('content-type','application/json'),('x-technical-service-token',TOKEN)]
    extra=list(headers.items()) if isinstance(headers,dict) else headers
    if any(k=='content-type' for k,v in extra):values=values[1:]
    response=await post(app(fake),body=body,headers=values+extra)
    assert response.status_code==422
    assert PRIVATE not in response.text and response.headers['cache-control']=='private, no-store'


async def test_body_deadline_and_query_rejected_before_engine():
    assert (await post(app(fake),path='/internal/technical/boundary?provider='+PRIVATE)).status_code==422
    async def delayed():
        await asyncio.sleep(.03)
        yield B.canonical(request()).encode()
    response=await post(app(fake,timeout=.005),body=delayed())
    assert response.status_code==504


async def test_timeout_keeps_process_slot_until_actual_child_settles():
    entered=asyncio.Event();release=asyncio.Event();calls=[]
    async def delayed(payload,*,trace_id):
        calls.append(payload);entered.set();await release.wait();return result()
    runtime=RUN.BoundaryRuntime(delayed,timeout=.005)
    with pytest.raises(RUN.BoundaryTimeout):await runtime.run(request())
    assert entered.is_set() and RUN._ACTIVE_TASK is not None
    with pytest.raises(RUN.BoundaryBusy):await RUN.BoundaryRuntime(fake).run(request())
    task=RUN._ACTIVE_TASK;release.set();await task;await asyncio.sleep(0)
    assert RUN._ACTIVE_TASK is None and len(calls)==1
    assert (await RUN.BoundaryRuntime(fake).run(request()))['data']['execution_mode']=='synthetic'


async def test_cancelled_waiter_never_cancels_child_and_busy_until_settled():
    entered=asyncio.Event();release=asyncio.Event()
    async def delayed(payload,*,trace_id):entered.set();await release.wait();return result()
    runtime=RUN.BoundaryRuntime(delayed)
    waiter=asyncio.create_task(runtime.run(request()));await entered.wait();waiter.cancel()
    with pytest.raises(asyncio.CancelledError):await waiter
    task=RUN._ACTIVE_TASK;assert task is not None and not task.cancelled()
    with pytest.raises(RUN.BoundaryBusy):await runtime.run(request())
    release.set();await task;await asyncio.sleep(0)
    assert RUN._ACTIVE_TASK is None


async def test_route_timeout_busy_and_engine_error_never_adopt_late_results():
    release=asyncio.Event()
    async def delayed(payload,*,trace_id):await release.wait();return result()
    application=app(delayed,timeout=.005)
    response=await post(application);assert response.status_code==504 and response.json()['data'] is None
    assert (await post(application)).status_code==503
    task=RUN._ACTIVE_TASK;release.set();await task;await asyncio.sleep(0)
    async def failure(payload,*,trace_id):raise RuntimeError(PRIVATE)
    response=await post(app(failure));assert response.status_code==502 and PRIVATE not in response.text
    assert RUN._ACTIVE_TASK is None


@pytest.mark.parametrize('base',['http://user:pass@host.invalid','http://host.invalid/path','http://host.invalid?query=x','http://host.invalid#fragment','http://host.invalid:0','http://host.invalid:bad','https://999.999.999.999'])
async def test_fixed_destination_rejected_before_transport(base):
    calls=[]
    with pytest.raises(C.AIUnavailableError):await client(transport=httpx.MockTransport(lambda r:calls.append(r)),base=base).technical_boundary(request())
    assert not calls


@pytest.mark.parametrize('token',['short','x'*31,'x'*32+'\n','한'*32])
async def test_invalid_token_zero_transport(token):
    calls=[]
    with pytest.raises(C.AIUnavailableError):await client(transport=httpx.MockTransport(lambda r:calls.append(r)),token=token).technical_boundary(request())
    assert not calls
    assert (await post(app(fake,token=token))).status_code==401


@pytest.mark.parametrize('status',[301,302,307,308,401,403,422,500,502,503,504])
async def test_no_redirect_retry_or_upstream_secret(status):
    calls=[]
    def send(r):calls.append(r);return httpx.Response(status,json={'secret':PRIVATE},headers={'location':'https://other.invalid'})
    with pytest.raises(C.AITimeoutError if status==504 else C.AIUnavailableError) as error:
        await client(transport=httpx.MockTransport(send)).technical_boundary(request())
    assert len(calls)==1 and PRIVATE not in str(error.value)
    assert str(calls[0].url)=='http://boundary.invalid/internal/technical/boundary'
    assert calls[0].headers['accept-encoding']=='identity'
    assert calls[0].headers['x-technical-service-token']==TOKEN


@pytest.mark.parametrize('kind',['encoding','duplicate','nonfinite','not_object','oversize','timeout','network'])
async def test_bounded_decoded_response_errors(kind):
    class Parts(httpx.AsyncByteStream):
        async def __aiter__(self):
            for _ in range(33):yield b'x'*65536
    async def send(r):
        if kind=='timeout':raise httpx.ReadTimeout(PRIVATE)
        if kind=='network':raise httpx.ConnectError(PRIVATE)
        if kind=='encoding':return httpx.Response(200,content=b'{}',headers={'content-encoding':'unknown'})
        if kind=='oversize':return httpx.Response(200,stream=Parts())
        return httpx.Response(200,content={'duplicate':b'{"x":1,"x":2}','nonfinite':b'{"x":NaN}','not_object':b'[]'}[kind])
    with pytest.raises(C.AITimeoutError if kind=='timeout' else C.AIUnavailableError if kind=='network' else C.AIContractError) as error:
        await client(transport=httpx.MockTransport(send)).technical_boundary(request())
    assert PRIVATE not in str(error.value)


async def test_client_does_not_use_environment_proxy_and_cancels_deadline(monkeypatch):
    actual=httpx.AsyncClient; options=[]
    def checked(*args,**kwargs):options.append(kwargs);return actual(*args,**kwargs)
    with patch.object(httpx,'AsyncClient',checked):
        await client().technical_boundary(request())
    assert options and all(o['trust_env'] is False and o['follow_redirects'] is False for o in options)
    async def send(r):await asyncio.sleep(.1);return httpx.Response(200,json={})
    with patch.object(B,'WAIT_SECONDS',.005):
        with pytest.raises(C.AITimeoutError):await client(transport=httpx.MockTransport(send)).technical_boundary(request())


def test_constant_separation_and_readonly_agent_graph_source():
    limits=sys.modules['src.agents.technical.domain.intraday_limits']
    assert limits.INTRADAY_CONFIDENCE_ADJUSTMENT_CAP==.05 and limits.INTRADAY_RISK_NOTE_MAX_COUNT==3
    root=ROOT/'ai/src/agents/technical'
    config=ast.parse((root/'config.py').read_text())
    imports=[n for n in config.body if isinstance(n,ast.ImportFrom) and n.module=='domain.intraday_limits']
    assert len(imports)==1 and imports[0].level==1
    assert {n.name for n in imports[0].names}=={'INTRADAY_CONFIDENCE_ADJUSTMENT_CAP','INTRADAY_RISK_NOTE_MAX_COUNT'}
    for relative in ('application/agent.py','application/orchestration/technical_graph.py'):
        assert ast.parse((root/relative).read_text())
    for name in FORBIDDEN:
        assert name not in sys.modules
    assert not ATTEMPTS


async def test_backend_asgi_timeout_preserves_busy_until_actual_engine_settlement():
    entered=asyncio.Event();release=asyncio.Event();seen=[]
    async def delayed(payload,*,trace_id):
        entered.set();await release.wait();seen.append('finished');return result()
    application=app(delayed)
    adapter=AD.TechnicalBoundaryAdapter(binding())
    with patch.object(B,'WAIT_SECONDS',.005):
        with pytest.raises(C.AITimeoutError):await adapter.run(client(application))
    assert entered.is_set() and RUN._ACTIVE_TASK is not None and not seen
    response=await post(application)
    assert response.status_code==503 and response.json()['error']['code']=='BUSY'
    task=RUN._ACTIVE_TASK;release.set();await task;await asyncio.sleep(0)
    assert seen==['finished'] and RUN._ACTIVE_TASK is None
    # No timed-out result was returned/frozen; a separate explicit call can succeed.
    assert (await AD.TechnicalBoundaryAdapter(binding()).run(client())).report_id==binding().report_id


@pytest.mark.parametrize('mutation',['both','neither','extra','uppercase_uuid','non_uuid','coercion'])
def test_common_header_closed_error_success_and_exact_ids(mutation):
    value=request()
    if mutation=='both':value['error']={'code':'BUSY','message':'Technical boundary unavailable'}
    elif mutation=='neither':value['data']=None
    elif mutation=='extra':value['provider_url']=PRIVATE
    elif mutation=='uppercase_uuid':value['request_id']='AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA'
    elif mutation=='non_uuid':value['request_id']='opaque-caller-id'
    else:value['trace_id']=1
    for module in (A,B):
        with pytest.raises(ValueError):module.parse_request(value)


async def test_request_limit_and_invalid_schema_reject_before_transport():
    calls=[];transport=httpx.MockTransport(lambda r:calls.append(r))
    value=request();value['data']['original_query']='차트'*1000
    value['data']['stock']['stock_name']='가'*256
    value['data']['context']['input_fingerprint']=B.fingerprint(value['data'])
    # An extra large unknown field must also fail schema rather than reach transport.
    value['data']['unexpected']=PRIVATE*1000
    with pytest.raises(C.AIValidationError):await client(transport=transport).technical_boundary(value)
    assert not calls


async def test_route_output_size_and_invalid_engine_shape_close_without_secret():
    async def oversized(payload,*,trace_id):
        value=result();value['interpretation']['text']=PRIVATE*100000;return value
    response=await post(app(oversized))
    assert response.status_code==502 and response.json()['data'] is None and PRIVATE not in response.text
    async def invalid(payload,*,trace_id):return {'secret':PRIVATE}
    response=await post(app(invalid))
    assert response.status_code==502 and PRIVATE not in response.text


def test_immutable_holder_and_preview_schema_binding():
    from dataclasses import FrozenInstanceError, replace
    holder=binding()
    with pytest.raises(FrozenInstanceError):holder.report_id=UUID('10000000-0000-4000-8000-000000000001')
    with pytest.raises(ValueError):replace(holder,report_id=UUID('10000000-0000-4000-8000-000000000001'))
    adapter=AD.TechnicalBoundaryAdapter(holder)
    response=sys.modules['src.agents.technical.application.boundary_adapter'].complete(request(),result())
    frozen=adapter.validate_and_freeze(response)
    wrong=AC.FrozenAnalysisResult.freeze(context=holder.context,report_id=holder.report_id,
        input_schema='other.v1',result_schema='other.v1',input_json=frozen.input_json,result_json=frozen.result_json)
    with pytest.raises(ValueError):adapter.chart_preview(wrong)
    assert RUN.BoundaryRuntime(fake,timeout=30).timeout==3
    for invalid in (0,-1,True,float('inf'),float('nan')):
        with pytest.raises(ValueError):RUN.BoundaryRuntime(fake,timeout=invalid)
        with pytest.raises(ValueError):R.make_router(timeout=invalid)


@pytest.mark.parametrize('remaining',[0,-1,1e-323,False,float('nan'),float('inf')])
async def test_exhausted_remaining_never_schedules_engine_or_occupies_slot(remaining):
    calls=[]
    async def engine(payload,*,trace_id):calls.append(1);return result()
    assert RUN._ACTIVE_TASK is None
    with pytest.raises(RUN.BoundaryTimeout):await RUN.BoundaryRuntime(engine).run(request(),remaining=remaining)
    await asyncio.sleep(0)
    assert not calls and RUN._ACTIVE_TASK is None


async def test_expired_projection_budget_never_schedules_engine_or_occupies_slot():
    calls=[]
    async def engine(payload,*,trace_id):calls.append(1);return result()
    assert RUN._ACTIVE_TASK is None
    with pytest.raises(RUN.BoundaryTimeout):await RUN.BoundaryRuntime(engine,timeout=1e-323).run(request())
    await asyncio.sleep(0)
    assert not calls and RUN._ACTIVE_TASK is None


class ThreadProbe:
    """Own every real worker used here; no graph, market data or LLM executes."""
    def __init__(self, output=None):
        self.entered=threading.Event();self.release=threading.Event()
        self.threads=[];self.calls=[];self.output=output or (lambda:result())
        self.llm=types.SimpleNamespace(complete=lambda prompt:'synthetic only')
        self.fetcher=lambda *args,**kwargs:[]
        self.cache=object();self.trace=object()
    def runner(self,payload,**kwargs):
        self.threads.append(threading.current_thread());self.calls.append((payload,kwargs,time.monotonic()))
        self.entered.set()
        assert self.release.wait(2), 'Test must release its owned worker'
        return self.output()
    def bridge(self,**kwargs):
        return BRIDGE.make_engine_bridge(sync_runner=self.runner,llm_client=self.llm,fetcher=self.fetcher,
            cache=self.cache,trace_sink=self.trace,enabled=True,**kwargs)


async def wait_thread(probe):
    async def wait():
        while not probe.entered.is_set():await asyncio.sleep(0)
    await asyncio.wait_for(wait(),1)
    assert len(probe.threads)==1 and probe.threads[0].ident!=threading.get_ident()


async def finish_thread(probe,task=None):
    probe.release.set();task=task or RUN._ACTIVE_TASK
    if task is not None:
        try:await asyncio.wait_for(asyncio.shield(task),1)
        except (asyncio.CancelledError,RUN.BoundaryEngineFailure,BRIDGE.EngineBridgeUnavailable,DEADLINE.DeadlineExceeded):pass
    await asyncio.sleep(0)
    for thread in probe.threads:
        thread.join(timeout=1)
        assert not thread.is_alive()
    assert RUN._ACTIVE_TASK is None


@pytest.mark.parametrize('bad',['runner','async_runner','async_runner_object','llm','async_llm','async_llm_object','fetcher','async_fetcher','async_fetcher_object','enabled','deadline'])
def test_bridge_invalid_dependencies_start_no_worker(bad):
    async def asynchronous(*args,**kwargs):return result()
    class AsyncCallable:
        async def __call__(self,*args,**kwargs):return result()
    kwargs=dict(sync_runner=lambda *a,**k:result(),llm_client=types.SimpleNamespace(complete=lambda p:''),
                fetcher=lambda *a,**k:[],cache=None,trace_sink=None)
    if bad=='runner':kwargs['sync_runner']=None
    elif bad=='async_runner':kwargs['sync_runner']=asynchronous
    elif bad=='async_runner_object':kwargs['sync_runner']=AsyncCallable()
    elif bad=='llm':kwargs['llm_client']=object()
    elif bad=='async_llm':kwargs['llm_client']=types.SimpleNamespace(complete=asynchronous)
    elif bad=='async_llm_object':kwargs['llm_client']=types.SimpleNamespace(complete=AsyncCallable())
    elif bad=='fetcher':kwargs['fetcher']=None
    elif bad=='async_fetcher':kwargs['fetcher']=asynchronous
    elif bad=='async_fetcher_object':kwargs['fetcher']=AsyncCallable()
    elif bad=='enabled':kwargs['enabled']=1
    else:kwargs['deadline']=DEADLINE.Deadline(float('nan'))
    with patch.object(BRIDGE.threading,'Thread') as worker:
        with pytest.raises(BRIDGE.EngineBridgeUnavailable):BRIDGE.make_engine_bridge(**kwargs)
        worker.assert_not_called()
    assert not ATTEMPTS


@pytest.mark.parametrize('missing',['sync_runner','llm_client','fetcher','cache','trace_sink'])
def test_bridge_requires_explicit_dependencies_even_for_unused_cache_and_trace(missing):
    kwargs=dict(sync_runner=lambda *a,**k:result(),llm_client=types.SimpleNamespace(complete=lambda p:''),
                fetcher=lambda *a,**k:[],cache=None,trace_sink=None)
    del kwargs[missing]
    with patch.object(BRIDGE.threading,'Thread') as worker:
        with pytest.raises(TypeError):BRIDGE.make_engine_bridge(**kwargs)
        worker.assert_not_called()


@pytest.mark.parametrize('off',[True,False])
async def test_default_off_or_expired_bridge_and_default_route_execute_nothing(off):
    probe=ThreadProbe();kwargs=dict(sync_runner=probe.runner,llm_client=probe.llm,fetcher=probe.fetcher,cache=None,trace_sink=None)
    bridge=BRIDGE.make_engine_bridge(**kwargs) if off else BRIDGE.make_engine_bridge(**kwargs,enabled=True,deadline=DEADLINE.Deadline(time.monotonic()-1))
    with patch.object(BRIDGE.threading,'Thread') as worker:
        with pytest.raises(BRIDGE.EngineBridgeUnavailable if off else DEADLINE.DeadlineExceeded):
            await bridge(object(),trace_id=request()['trace_id'])
        response=await post(app(engine=bridge,enabled=False))
        assert response.status_code==403 and response.json()['error']['code']=='FEATURE_UNAVAILABLE'
        worker.assert_not_called()
    assert not probe.calls and not ATTEMPTS and RUN._ACTIVE_TASK is None


async def test_real_thread_snapshot_dependencies_trace_and_loop_heartbeat():
    probe=ThreadProbe();bridge=probe.bridge();req=request()
    payload=sys.modules['src.agents.technical.application.boundary_adapter'].project_input(req)
    snapshot=payload.model_dump(mode='json');task=asyncio.create_task(bridge(payload,trace_id=req['trace_id']))
    try:
        await wait_thread(probe);payload.query='caller mutation must stay outside the worker'
        pulses=[]
        for _ in range(5):await asyncio.sleep(0);pulses.append(time.monotonic())
        assert len(pulses)==5 and not task.done() and probe.threads[0].is_alive()
        actual,kwargs,entered=probe.calls[0]
        assert actual is not payload and actual.model_dump(mode='json')==snapshot
        assert kwargs['llm_client'] is probe.llm and kwargs['fetcher'] is probe.fetcher
        assert kwargs['cache'] is probe.cache and kwargs['trace_sink'] is probe.trace
        assert kwargs['trace_id']==req['trace_id']
        assert 0<kwargs['deadline'].expires_at-entered<=A.WAIT_SECONDS
        probe.release.set();value=await task
        assert B.canonical(value)==B.canonical(result())
    finally:await finish_thread(probe,task)


@pytest.mark.parametrize('typed',[False,True])
async def test_actual_asgi_bridge_output_uses_existing_strict_contract(typed):
    value=A.TechnicalAgentOutput.model_validate(result()) if typed else result()
    probe=ThreadProbe(lambda:value);probe.release.set()
    try:
        response=await post(app(probe.bridge()))
        assert response.status_code==200
        out=response.json();A.validate_response(out,request())
        assert out['data']['execution_mode']=='synthetic' and out['data']['coverage']['cutoff_validation']=='unverified'
        expected=value.model_dump(mode='json') if typed else value
        if typed:expected['as_of']=value.as_of.isoformat()
        assert B.canonical(out['data']['result'])==B.canonical(expected)
        if not typed:assert type(out['data']['result']['signal']['confidence']) is int
        assert len(probe.calls)==1 and probe.threads[0].ident!=threading.get_ident()
    finally:await finish_thread(probe)


async def test_typed_timestamp_representation_is_not_rewritten_to_match_request():
    probe=ThreadProbe(lambda:A.TechnicalAgentOutput.model_validate(result()));probe.release.set()
    value=request();value['data']['requested_as_of']=value['data']['requested_as_of'].replace('+00:00','Z')
    value['data']['context']['input_fingerprint']=A.fingerprint(value['data'])
    try:
        response=await post(app(probe.bridge()),body=B.canonical(value).encode())
        assert response.status_code==502 and response.json()['error']['code']=='RESULT_CONTRACT_INVALID'
        assert PRIVATE not in response.text and len(probe.calls)==1
    finally:await finish_thread(probe)


@pytest.mark.parametrize('bad',['identity','ticker','as_of','extra','nonfinite','exception'])
async def test_bridge_invalid_output_or_runner_error_never_repairs_or_exposes_values(bad):
    def output():
        if bad=='exception':raise RuntimeError(PRIVATE)
        value=result()
        if bad=='identity':value['request_id']='00000000-0000-4000-8000-000000000099'
        elif bad=='ticker':value['ticker']='000660'
        elif bad=='as_of':value['as_of']='2026-11-05T00:00:00Z'
        elif bad=='extra':value['unexpected']=PRIVATE
        else:value['signal']['confidence']=float('nan')
        return value
    probe=ThreadProbe(output);probe.release.set()
    try:
        response=await post(app(probe.bridge()))
        assert response.status_code==502 and response.json()['error']['code']=='RESULT_CONTRACT_INVALID'
        assert PRIVATE not in response.text and response.json()['data'] is None
        assert len(probe.calls)==1
    finally:await finish_thread(probe)


@pytest.mark.parametrize('late_failure',[False,True])
async def test_real_thread_http_timeout_keeps_global_slot_until_worker_end(late_failure):
    def output():
        if late_failure:raise RuntimeError(PRIVATE)
        return result()
    probe=ThreadProbe(output);application=app(probe.bridge(),timeout=.01)
    try:
        response=await post(application)
        await wait_thread(probe)
        assert response.status_code==504 and probe.entered.is_set()
        active=RUN._ACTIVE_TASK;assert active is not None and not active.done() and probe.threads[0].is_alive()
        again=await post(application)
        assert again.status_code==503 and again.json()['error']['code']=='BUSY' and len(probe.calls)==1
        await finish_thread(probe,active)
        assert response.status_code==504 and response.json()['data'] is None
        probe.output=lambda:result()
        assert (await post(application)).status_code==200 and len(probe.calls)==2
    finally:await finish_thread(probe)


async def test_waiter_cancellation_is_immediate_without_releasing_running_thread_slot():
    probe=ThreadProbe();runtime=RUN.BoundaryRuntime(probe.bridge());waiter=asyncio.create_task(runtime.run(request()))
    try:
        await wait_thread(probe);waiter.cancel()
        with pytest.raises(asyncio.CancelledError):await waiter
        assert probe.threads[0].is_alive() and not RUN._ACTIVE_TASK.done()
        with pytest.raises(RUN.BoundaryBusy):await runtime.run(request())
        assert len(probe.calls)==1
    finally:await finish_thread(probe)


async def test_repeated_inner_task_cancellation_cannot_complete_before_physical_worker():
    probe=ThreadProbe();runtime=RUN.BoundaryRuntime(probe.bridge())
    try:
        # Only the first waiter is deliberately short; slot recovery is not a 10ms performance test.
        with pytest.raises(RUN.BoundaryTimeout):await runtime.run(request(),remaining=.01)
        await wait_thread(probe)
        active=RUN._ACTIVE_TASK;assert active is not None and probe.entered.is_set()
        for _ in range(2):
            active.cancel();await asyncio.sleep(0)
            assert not active.done() and probe.threads[0].is_alive()
            with pytest.raises(RUN.BoundaryBusy):await runtime.run(request(),remaining=.01)
        assert len(probe.calls)==1
        await finish_thread(probe,active)
        assert active.cancelled()
        assert runtime.timeout==A.WAIT_SECONDS
        assert (await runtime.run(request()))['data']['result']==result()
    finally:await finish_thread(probe)


async def test_injected_earlier_cooperative_deadline_is_never_renewed():
    probe=ThreadProbe();early=DEADLINE.Deadline.after(.5)
    runtime=RUN.BoundaryRuntime(probe.bridge(deadline=early),timeout=.005)
    try:
        with pytest.raises(RUN.BoundaryTimeout):await runtime.run(request())
        await wait_thread(probe)
        assert probe.calls[0][1]['deadline'].expires_at<=early.expires_at
        await asyncio.sleep(.51)
        assert early.expired() and probe.threads[0].is_alive()
        with pytest.raises(RUN.BoundaryBusy):await runtime.run(request())
        await finish_thread(probe)
    finally:await finish_thread(probe)
