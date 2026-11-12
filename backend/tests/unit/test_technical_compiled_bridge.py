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
from uuid import UUID

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
