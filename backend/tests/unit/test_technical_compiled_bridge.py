"""Exact copied compiled graph with fake LLM/OHLCV; no provider or DB."""
import asyncio
import copy
import hashlib
import importlib.abc
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import sys
import threading
from types import ModuleType
from uuid import UUID,uuid4

import pytest

ROOT = Path(__file__).resolve().parents[3]
from scripts.check_safe import GRAPH_INPUTS
for relative, digest in GRAPH_INPUTS.items():
    assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest() == digest

# The worker installed file/network/process guards BEFORE this collection.
# Only copied sources can be discovered; no original checkout is on sys.path.
sys.path.insert(0,str(ROOT/'ai'))
FORBIDDEN = ('openai','langchain_openai','redis','src.api','src.main',
             'src.agents.fundamental','src.agents.industry','src.agents.news',
             'src.shared.config','sqlalchemy','asyncpg')
ATTEMPTS = []
class ImportSentinel(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if any(fullname == name or fullname.startswith(name+'.') for name in FORBIDDEN):
            ATTEMPTS.append(fullname)
            raise AssertionError('External capability import prohibited')
sys.meta_path.insert(0,ImportSentinel())


def namespace(name, location):
    if name in sys.modules:
        return sys.modules[name]
    module=ModuleType(name)
    module.__spec__=importlib.machinery.ModuleSpec(name,None,is_package=True)
    module.__spec__.submodule_search_locations=[str(location)]
    module.__path__=[str(location)]
    sys.modules[name]=module
    parent,_,leaf=name.rpartition('.')
    if parent in sys.modules:setattr(sys.modules[parent],leaf,module)
    return module

# Preserve the unchanged worker's six pure Flow input and origin invariant.
for name in ('agents','agents.flow','agents.flow.api','agents.flow.domain',
             'agents.flow.domain.verification','agents.flow.infrastructure'):
    namespace(name,(ROOT/'ai/src').joinpath(*name.split('.')))
for suffix in ('domain.observation_window','domain.verification.consecutive',
               'domain.interpretation_claims','domain.models','api.payload','infrastructure.token_cache'):
    name='agents.flow.'+suffix
    path=ROOT/'ai/src/agents/flow'/ (suffix.replace('.','/')+'.py')
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)

# Synthetic settings only. Initialize once BEFORE pipeline imports; no reload or
# mutation of copied module flags. Worker blocks every .env open and all network.
os.environ.update(INTRADAY_FETCH_ENABLED='false',TECHNICAL_TRACE_ENABLED='false',
                  LANGCHAIN_TRACING_V2='false',LANGSMITH_TRACING='false')
from src.agents.technical import config
snapshot=config.initialize_runtime()
assert snapshot.intraday_fetch_enabled is False and snapshot.trace_enabled is False
namespace('tests',ROOT/'backend/tests')
namespace('tests.technical',ROOT/'ai/tests/technical')
# urllib3's import-only platform probe otherwise binds ::1:0, even with
# tracing disabled. Model an IPv4-only platform before importing dependencies;
# this prevents the probe rather than granting a network capability.
import socket
from unittest.mock import patch
with patch.object(socket,'has_ipv6',False):
    from tests.technical import test_technical_supervisor as st
    from tests.technical import test_technical_langgraph as graph_fixtures
from src.agents.technical.application.agent import run_technical_agent
from src.agents.technical.application.engine_bridge import TechnicalEngineBridge
from src.agents.technical.application import boundary_runtime as runtime
from src.agents.technical.domain import boundary_contracts as contract
from src.shared.contracts.agent_envelope import SCHEMA_VERSION


for module in (st,graph_fixtures,config):
    assert Path(module.__spec__.origin).resolve().is_relative_to(ROOT/'ai')


def request():
    ids=[str(UUID(int=index)) for index in range(1,7)]
    data=dict(operation=contract.OPERATION,context=dict(zip(
        ('analysis_id','admission_request_id','attempt_id','report_id'),ids[2:])),
        original_query='LG에너지솔루션 차트',stock=dict(stock_code=st.TICKER,stock_name='LG에너지솔루션',market='KOSPI'),
        requested_views=['technical'],requested_as_of='2026-06-30T05:30:00+00:00',
        conditions=dict(profile=contract.PROFILE,periods=list(contract.PERIODS)))
    data['context']['input_fingerprint']=contract.fingerprint(data)
    return dict(schema_version=SCHEMA_VERSION,request_id=ids[0],trace_id=ids[1],data=data,error=None)


@pytest.mark.parametrize('case,expected',[
    ('normal','normal'),('data_limited','data_limited'),('regime_unavailable','regime_unavailable')])
async def test_real_compiled_graph_through_thread_bridge_and_strict_completion(case,expected):
    main_thread=threading.get_ident();calls=[];fetches=[];threads=[]
    daily=st.DAILY if case=='normal' else [] if case=='data_limited' else st._series(40,day_stride=1,start='2023-01-02')
    def fetcher(ticker,*,end_date=None):
        fetches.append((ticker,end_date))
        return {'D':daily,'W':st.WEEKLY,'M':st.MONTHLY}
    llm=st.ScriptedLlm(graph_fixtures._HAPPY if case=='normal' else [st.NORM_OK,st.FOCUS_OK])
    req=request();before=copy.deepcopy(req)
    def runner(payload,**kwargs):
        threads.append(threading.current_thread())
        assert threading.get_ident()!=main_thread
        calls.append(payload.model_dump(mode='json'))
        return run_technical_agent(payload,**kwargs)
    bridge=TechnicalEngineBridge(sync_runner=runner,llm_client=llm,fetcher=fetcher,
                                 cache=None,trace_sink=None,enabled=True)
    try:
        result=await runtime.BoundaryRuntime(bridge).run(req)
        contract.validate_response(result,req)
        assert req==before and len(calls)==1 and len(fetches)==1
        actual=result['data']['result']
        assert actual['data_status']==expected
        assert (actual['signal'] is None)==(case!='normal')
        assert actual['ticker']==st.TICKER and actual['as_of']==req['data']['requested_as_of']
        assert actual['request_id']==req['request_id'] and actual['trace_id']==req['trace_id']
        assert calls[0]['query']==req['data']['original_query'] and calls[0]['stock_name']=='LG에너지솔루션'
        assert len(llm.prompts)==(4 if case=='normal' else 2)
        coverage=result['data']['coverage']
        assert coverage['requested_periods']==contract.PERIODS and coverage['cutoff_validation']=='unverified'
        assert result['data']['request_snapshot']==req['data']
        assert coverage['available_periods']==([] if case=='data_limited' else contract.PERIODS)
        assert len(actual['charts'])==(0 if case=='data_limited' else 3)
        assert not ATTEMPTS
    finally:
        await asyncio.sleep(0)
        assert runtime._ACTIVE_TASK is None
        for worker in threads:
            worker.join(timeout=1)
            assert not worker.is_alive()
        assert not any(t.name=='verith-technical-bridge' and t.is_alive() for t in threading.enumerate())

async def test_narrow_range_support_and_resistance_remain_neutral_in_compiled_result():
    from src.agents.technical.domain.models.ohlcv import OHLCV
    from src.agents.technical.domain.synthesis.signal_score import compute_signal_score
    daily=[OHLCV(date=bar.date,open=100,high=101,low=99,close=100,
                 volume=bar.volume,trading_value=bar.trading_value) for bar in st.DAILY]
    expected=compute_signal_score(daily)
    row=next(r for r in expected.technical_signals if r.indicator.value=='support_resistance')
    assert row.signal.value=='neutral' and row.metrics==['지지 99.0','저항 101.0']
    llm=st.ScriptedLlm(list(graph_fixtures._HAPPY))
    bridge=TechnicalEngineBridge(sync_runner=run_technical_agent,llm_client=llm,
        fetcher=lambda ticker,**kwargs:dict(D=daily,W=st.WEEKLY,M=st.MONTHLY),
        cache=None,trace_sink=None,enabled=True)
    req=request()
    try:
        result=await runtime.BoundaryRuntime(bridge).run(req)
        contract.validate_response(result,req)
        actual=result['data']['result']
        stored=next(r for r in actual['technical_signals'] if r['indicator']=='support_resistance')
        assert actual['data_status']=='normal' and stored['signal']=='neutral'
        assert stored['metrics']==row.metrics and stored['weight']==row.weight and stored['value']==100
        assert actual['signal']['signal_score']==expected.signal_score
        assert actual['signal']['consensus']==expected.consensus.value
        assert len(llm.prompts)<=4 and not ATTEMPTS
    finally:
        await asyncio.sleep(0)
        assert runtime._ACTIVE_TASK is None
        assert not any(t.name=='verith-technical-bridge' and t.is_alive() for t in threading.enumerate())


# CF053: the actual graph/bridge/runtime plus selected CF051 definitions; SDK
# constructors and OHLCV are synthetic. This is not a SQL or provider test.
import json
import time
from datetime import datetime,UTC,timedelta
from dataclasses import fields
from types import SimpleNamespace
import httpx
from fastapi import FastAPI,Request
from starlette.responses import JSONResponse
from src.agents.technical.domain import execution_contracts as P
from src.agents.technical.application import agent as actual_agent
from src.agents.technical.application.orchestration import pipeline_steps as actual_steps
from src.agents.technical.application.execution_runtime import ExecutionOptions,TechnicalProviderRuntime
from src.agents.technical.infrastructure.execution_authority_client import ExecutionAuthorityClient


def cf051_selected():
    # Reuse the existing reviewed AST collector/fake HTTP SDK, never import SDK.
    path=ROOT/'backend/tests/unit/test_cf040_technical_runtime_setup.py'
    spec=importlib.util.spec_from_file_location('_cf053_existing_adapter_tests',path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    return module

ADAPTER_FIXTURES=cf051_selected()

def execution_fixture(case='normal',pause=None,calls=4,on_start=None,server_remaining=None):
    req=request();ids=[str(uuid4()) for _ in range(6)];req['request_id'],req['trace_id']=ids[:2]
    req['data']['context'].update(dict(zip(('analysis_id','admission_request_id','attempt_id','report_id'),ids[2:])))
    now=datetime.now(UTC);req['data']['requested_as_of']=now.isoformat()
    req['data']['context']['input_fingerprint']=contract.fingerprint(req['data'])
    p=dict(operation='technical.analysis.v1',enabled=True,currency='USD',supported_tickers=[st.TICKER],
        user_daily_limit=3,service_daily_limit=10,daily_budget_nano=1000000,attempt_reserve_nano=420000,
        deadline_seconds=60,model='synthetic-model',service_tier='default',price_id='cf053.synthetic.v1',
        price_evidence_sha256='a'*64,input_nano_per_token=1,output_nano_per_token=1,
        input_token_cap=100000,output_token_cap=5000,input_byte_cap=100000,output_byte_cap=100000,max_calls=calls)
    cfg=P.Configuration.parse(dict(schema_version=P.SCHEMA,policy=p,counter={'free':True,'mapping':'technical.responses.model-input.v1','version':'synthetic.v1','provenance_sha256':'c'*64,'evidence_sha256':'d'*64},
        caps={'request':131072,'count':4096,'generation':1048576},ai_origin='https://ai.invalid',authority_origin='https://backend.invalid',cache_mode='none',trace_mode='none'))
    control={k:req['data']['context'][k] for k in ('analysis_id','admission_request_id','attempt_id','report_id')}
    control.update(boundary_request_id=req['request_id'],trace_id=req['trace_id'],spec_sha256=P.SPEC_SHA256,policy_sha256=cfg.policy_sha256,configuration_sha256=cfg.fingerprint,
        intent_sha256=P.sha(P.canonical(dict(operation='technical.analysis.v1',ticker=st.TICKER,original_query=req['data']['original_query'],requested_views=['technical'],conditions=req['data']['conditions']))),
        boundary_sha256=P.sha(P.canonical(req)),stock_sha256=P.sha(P.canonical(req['data']['stock'])),reserved_nano=p['attempt_reserve_nano'],started_at=now.isoformat(),deadline_at=(now+timedelta(seconds=60)).isoformat())
    value=P.execution(req,control,cfg);events=[];observations=[];starts=[];budgets=[];credentials=[];start_anchors=[]
    scripts=list(graph_fixtures._HAPPY if case=='normal' else [st.NORM_OK,st.FOCUS_OK])
    def inner(request,Parts):
        events.append((request.url.path,threading.get_ident()))
        if pause is not None and len(events)==1:
            pause[0].set();assert pause[1].wait(3)
        if request.url.path.endswith('input_tokens'):body={'object':'response.input_tokens','input_tokens':12}
        else:
            body={'status':'completed','model':p['model'],'service_tier':'default','output_text':scripts.pop(0),'usage':{'input_tokens':12,'output_tokens':3,'total_tokens':15}}
        raw=json.dumps(body,ensure_ascii=False).encode()
        return httpx.Response(200,headers={'Content-Type':'application/json','Content-Length':str(len(raw))},stream=Parts([raw]))
    helper=ADAPTER_FIXTURES.official_adapter(defer=True,inner=inner)
    helper.a['time']=time
    factory=helper.a['official_count_openai_client']
    def create(**kwargs):
        budgets.append(kwargs['request_budget']);return factory(**kwargs)
    llm=SimpleNamespace(TechnicalLlmPolicy=helper.a['TechnicalLlmPolicy'],TechnicalRequestLlmBudget=helper.a['TechnicalRequestLlmBudget'],official_count_openai_client=create)
    daily=st.DAILY if case=='normal' else [] if case=='data_limited' else st._series(40,day_stride=1,start='2023-01-02')
    def fetcher(ticker,*,end_date=None):return {'D':daily,'W':st.WEEKLY,'M':st.MONTHLY}
    def credential():credentials.append(True);return 'synthetic-auth-not-real'
    app=FastAPI()
    @app.post('/internal/technical/execution/start')
    async def start(request:Request):
        assert request.headers['x-technical-authority-token']=='b'*32
        assert request.headers['x-technical-execution-grant']=='f'*64
        body=await request.json();starts.append(body)
        start_anchors.append(time.monotonic())
        stamp=datetime.now(UTC) if server_remaining is None else P.stamp(value['control']['deadline_at'])-timedelta(seconds=server_remaining)
        receipt=P.start_receipt(value['control_sha256'],body['executor_id'],stamp.isoformat())
        if on_start is not None:on_start(instance)
        return JSONResponse({'schema_version':P.SCHEMA,'newly_started':True,**receipt})
    @app.post('/internal/technical/execution/observe')
    async def observe(request:Request):
        body=await request.json();observations.append(body)
        return JSONResponse({'schema_version':P.SCHEMA,'recorded':True,'analysis_id':body['analysis_id'],'evidence_sha256':body['evidence_sha256']})
    authority=ExecutionAuthorityClient(origin=cfg.data()['authority_origin'],token='b'*32,transport=httpx.ASGITransport(app=app))
    options=ExecutionOptions(cfg,'a'*32,'b'*32,credential,fetcher,None,None)
    instance=TechnicalProviderRuntime(options,agent_module=actual_agent,steps_module=actual_steps,llm_module=llm,authority=authority)
    return SimpleNamespace(instance=instance,value=value,events=events,observations=observations,starts=starts,budgets=budgets,credentials=credentials,helper=helper,cfg=cfg,start_anchors=start_anchors)

@pytest.mark.parametrize('case,expected',[('normal','normal'),('data_limited','data_limited'),('regime_unavailable','regime_unavailable')])
async def test_CF053_actual_graph_one_start_one_budget_all_nodes_and_independent_usage(case,expected):
    h=execution_fixture(case)
    assert h.instance.readiness()['ready'] is True and not h.credentials
    result=await h.instance.execute(h.value,'f'*64)
    assert result['data']['result']['data_status']==expected
    assert len(h.starts)==len(h.budgets)==len(h.credentials)==len(h.observations)==1
    records=h.budgets[0].snapshot();assert len(records)==(4 if case=='normal' else 2)
    assert [r.ordinal for r in records]==list(range(1,len(records)+1))
    assert len(h.events)==2*len(records)<=8 and all(tid!=threading.get_ident() for _,tid in h.events)
    observed=h.observations[0]['evidence'];start={k:h.observations[0][k] for k in ('control_sha256','start_sha256','executor_id')}
    assert P.evidence(observed,h.cfg,h.value['control'],start)==observed
    assert all(r['usage']==[12,3,15] for r in observed['records'])
    assert h.helper.closed.count('client')==h.helper.closed.count('transport')==1
    await asyncio.sleep(0);assert runtime._ACTIVE_TASK is None and not ATTEMPTS

@pytest.mark.parametrize('actual_task',[False,True])
async def test_CF053_cancel_closes_pending_budget_now_but_retains_physical_slot_and_bundle(actual_task):
    paused=threading.Event();release=threading.Event();h=execution_fixture(pause=(paused,release))
    waiter=asyncio.create_task(h.instance.execute(h.value,'f'*64))
    try:
        for _ in range(1000):
            if paused.is_set():break
            await asyncio.sleep(.001)
        assert paused.is_set() and runtime._ACTIVE_TASK is not None
        task=runtime._ACTIVE_TASK
        (task if actual_task else waiter).cancel()
        for _ in range(100):
            if h.budgets[0].closed_reason:break
            await asyncio.sleep(.001)
        assert h.budgets[0].closed_reason is not None
        assert runtime._ACTIVE_TASK is task and 'client' not in h.helper.closed
        with pytest.raises(runtime.BoundaryBusy):await runtime.controlled_slot(lambda:None,remaining=1,close_pending=lambda:None)
    finally:
        release.set()
        try:await waiter
        except (asyncio.CancelledError,P.ExecutionInvalid):pass
        for _ in range(1000):
            if runtime._ACTIVE_TASK is None:break
            await asyncio.sleep(.001)
        assert runtime._ACTIVE_TASK is None
        assert len(h.events)==1 and h.helper.closed.count('client')==1
        assert len(h.observations)==(0 if actual_task else 1)

async def test_CF053_existing_planning_rejection_precedes_start_key_and_budget():
    h=execution_fixture();b=h.value['boundary_request'];b['data']['original_query']='CF050 synthetic private chart'
    b['data']['context']['input_fingerprint']=contract.fingerprint(b['data'])
    c=h.value['control'];c['boundary_sha256']=P.sha(P.canonical(b))
    c['intent_sha256']=P.sha(P.canonical(dict(operation='technical.analysis.v1',ticker=st.TICKER,original_query=b['data']['original_query'],requested_views=['technical'],conditions=b['data']['conditions'])))
    value=P.execution(b,c,h.cfg);h.value.clear();h.value.update(value)
    with pytest.raises(ValueError):await h.instance.execute(h.value,'f'*64)
    assert not h.starts and not h.credentials and not h.budgets and not h.events
    assert runtime._ACTIVE_TASK is None

@pytest.mark.parametrize('field',['origin','token','transport'])
async def test_CF053_ready_authority_configuration_drift_has_start_and_key0(field):
    h=execution_fixture();assert h.instance.readiness()['ready']
    setattr(h.instance.authority,field,'https://other.invalid' if field=='origin' else b'c'*32 if field=='token' else None)
    with pytest.raises(P.ExecutionInvalid):await h.instance.execute(h.value,'f'*64)
    assert not h.starts and not h.credentials and not h.budgets and not h.events

async def test_CF053_real_graph_call_cap_closes_later_nodes_without_recreating_budget():
    h=execution_fixture(calls=2)
    result=await h.instance.execute(h.value,'f'*64)
    assert result['data']['result']['ticker']==st.TICKER
    assert len(h.budgets)==len(h.starts)==len(h.credentials)==1
    assert len(h.budgets[0].snapshot())==2 and len(h.events)==4
    assert h.budgets[0].closed_reason=='BUDGET_EXCEEDED'
    assert h.observations[0]['evidence']['records']==[
        {f.name:(str(getattr(item,f.name)) if isinstance(getattr(item,f.name),UUID) else list(getattr(item,f.name)) if type(getattr(item,f.name)) is tuple else getattr(item,f.name)) for f in fields(item)} for item in h.budgets[0].snapshot()]

async def test_CF053_waiter_timeout_keeps_slot_bundle_until_physical_count_finishes():
    pause=(threading.Event(),threading.Event());h=execution_fixture(pause=pause)
    value=h.value;c=value['control'];c['deadline_at']=(P.stamp(c['started_at'])+timedelta(seconds=1)).isoformat()
    fixed=P.execution(value['boundary_request'],c,h.cfg);value.clear();value.update(fixed)
    waiter=asyncio.create_task(h.instance.execute(value,'f'*64))
    try:
        for _ in range(500):
            if pause[0].is_set():break
            await asyncio.sleep(.001)
        assert pause[0].is_set()
        with pytest.raises(runtime.BoundaryTimeout):await waiter
        assert runtime._ACTIVE_TASK is not None and 'client' not in h.helper.closed
        assert h.budgets[0].closed_reason=='DEADLINE_EXCEEDED'
    finally:
        pause[1].set()
        for _ in range(1500):
            if runtime._ACTIVE_TASK is None:break
            await asyncio.sleep(.001)
        assert runtime._ACTIVE_TASK is None and len(h.events)==1
        assert h.helper.closed.count('client')==1
        assert len(h.observations)==1 and h.observations[0]['evidence']['outcome']=='deadline'

@pytest.mark.parametrize('flag',['LANGCHAIN_TRACING','LANGCHAIN_TRACING_V2','LANGSMITH_TRACING','LANGSMITH_TRACING_V2'])
async def test_CF053_process_auto_trace_enabled_is_unready_before_start(flag,monkeypatch):
    h=execution_fixture()
    monkeypatch.setenv(flag,'true')  # self-owned unit worker only; never open a real runtime
    with pytest.raises(P.ExecutionInvalid):h.instance.readiness()
    with pytest.raises(P.ExecutionInvalid):await h.instance.execute(h.value,'f'*64)
    assert not h.starts and not h.credentials and not h.events

@pytest.mark.parametrize('capability',['fetcher','credential_supplier'])
async def test_CF053_async_callable_object_is_unready_before_start(capability):
    h=execution_fixture()
    class AsyncCapability:
        async def __call__(self,*args,**kwargs):raise AssertionError('must not enter')
    object.__setattr__(h.instance.options,capability,AsyncCapability())
    with pytest.raises(P.ExecutionInvalid):h.instance.readiness()
    assert not h.starts and not h.credentials and not h.events

async def test_CF053_config_drift_after_start_cannot_reprice_or_create_budget_but_records_failure():
    def drift(instance):
        changed=instance.configuration.data();changed['caps']['request']=262144
        instance.configuration=P.Configuration.parse(changed)
    h=execution_fixture(on_start=drift)
    with pytest.raises(P.ExecutionInvalid):await h.instance.execute(h.value,'f'*64)
    assert len(h.starts)==1 and not h.credentials and not h.budgets and not h.events
    assert len(h.observations)==1 and h.observations[0]['evidence']['outcome']=='failed'
    assert h.observations[0]['evidence']['records']==[]
    await asyncio.sleep(0);assert runtime._ACTIVE_TASK is None

async def test_CF053_start_DB_remaining_only_narrows_original_monotonic_deadline():
    # Explicit DB-clock step simulation, no real sleep or environment clock edit.
    h=execution_fixture(server_remaining=20)
    result=await h.instance.execute(h.value,'f'*64)
    assert result['data']['execution_mode']=='controlled' and len(h.budgets)==1
    assert h.budgets[0]._monotonic_deadline<=h.start_anchors[0]+20
    assert h.value['control']['deadline_at']==(P.stamp(h.value['control']['started_at'])+timedelta(seconds=60)).isoformat()
    assert len(h.events)==8 and len(h.observations)==1
