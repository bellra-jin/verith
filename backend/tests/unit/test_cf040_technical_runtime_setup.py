"""Actual config and selected dependency AST bodies, with self-owned I/O spies only.

No legacy dependencies module, graph, provider, real environment or dotenv file is
imported/read. Every config case is a fresh independent module, never a repair of
an already imported pipeline or a reload of its copied settings.
"""
import ast
import asyncio
import builtins
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, contextmanager
from dataclasses import FrozenInstanceError, dataclass, fields, replace
from datetime import UTC, datetime, timedelta
import hashlib
import logging
import httpx
import importlib.machinery
import importlib.util
from itertools import count
from pathlib import Path
import json
import math
import ssl
import re
import sys
import threading
from types import ModuleType, SimpleNamespace
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest

ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = 'ai/src/agents/technical/config.py'
DEPENDENCIES_PATH = 'ai/src/api/dependencies.py'
LIMITS_PATH = 'ai/src/agents/technical/domain/intraday_limits.py'
DEADLINE_PATH = 'ai/src/shared/runtime/deadline.py'
LLM_PATH = 'ai/src/agents/technical/infrastructure/openai_llm_client.py'
KIS_PATH = 'ai/src/agents/technical/infrastructure/kis_client.py'
PRIVATE = 'cf040-synthetic-private-sentinel-never-output'
FORBIDDEN = ('src.agents.technical.application.', 'agents.technical.application.',
             'src.agents.technical.infrastructure.', 'agents.technical.infrastructure.',
             'src.supervisor.', 'src.api.dependencies', 'openai', 'redis', 'langgraph')
SERIAL = count()


def load_readonly():
    """Preserve the existing six actual pure Flow source origins before collection."""
    from scripts.check_safe import CF040_COMPAT, CF040_INPUTS
    ai = ROOT/'ai/src'
    assert len(CF040_COMPAT) == 6 and set(CF040_INPUTS) == {CONFIG_PATH, DEPENDENCIES_PATH, LIMITS_PATH, DEADLINE_PATH, LLM_PATH, KIS_PATH}
    for name in ('agents','agents.flow','agents.flow.api','agents.flow.domain','agents.flow.domain.verification','agents.flow.infrastructure'):
        if name not in sys.modules:
            module = ModuleType(name)
            module.__spec__ = importlib.machinery.ModuleSpec(name,None,is_package=True)
            module.__spec__.submodule_search_locations = [str(ai.joinpath(*name.split('.')))]
            module.__path__ = []
            sys.modules[name] = module
    for relative, expected in CF040_COMPAT.items():
        path = ROOT/relative
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
        name = relative.removeprefix('ai/src/').removesuffix('.py').replace('/','.')
        if name not in sys.modules:
            spec = importlib.util.spec_from_file_location(name,path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module; spec.loader.exec_module(module)
        assert isinstance(sys.modules[name].__spec__.loader,importlib.machinery.SourceFileLoader)
        assert Path(sys.modules[name].__spec__.origin).resolve() == path.resolve()
    for relative, expected in CF040_INPUTS.items():
        assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest() == expected


load_readonly()
CONFIG_SOURCE = (ROOT/CONFIG_PATH).read_text()
DEPENDENCIES_SOURCE = (ROOT/DEPENDENCIES_PATH).read_text()


def pure_module(relative, label):
    name = '_cf040_' + label
    spec = importlib.util.spec_from_file_location(name,ROOT/relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module; spec.loader.exec_module(module)
    return module


LIMITS = pure_module(LIMITS_PATH,'actual_limits')
DEADLINE = pure_module(DEADLINE_PATH,'actual_deadline')


class Probe:
    """No source of settings other than this synthetic mapping reaches the module."""
    def __init__(self, env=None, dotenv=None, *, present=True):
        self.env = dict(env or {})
        self.dotenv = dict(dotenv or {})
        self.present = present
        self.events = []
        self.io = []
        self.imports = []
        self.loads = []
        self.on_load = None
        self.fail_get = None
        self.config = None
        self.os = ModuleType('os')
        self.os.getenv = self.getenv
        self.dotenv_module = ModuleType('dotenv')
        self.dotenv_module.load_dotenv = self.load_dotenv

    def getenv(self, key, default=None):
        self.events.append(('getenv',key))
        if key == self.fail_get: raise RuntimeError(PRIVATE)
        return self.env.get(key,default)

    def load_dotenv(self, path, *, override):
        self.events.append(('dotenv_load',))
        self.loads.append((path,override))
        assert override is False
        for key,value in self.dotenv.items(): self.env.setdefault(key,value)
        if self.on_load is not None: self.on_load()
        return True

    def exists(self, path):
        self.io.append(('exists',str(path)))
        return self.present and path.name == '.env'

    def blocked_file(self, *args, **kwargs):
        self.io.append(('forbidden_file',))
        raise AssertionError('Actual file I/O prohibited in runtime setup probe')

    def import_config(self, name, globals=None, locals=None, fromlist=(), level=0):
        self.imports.append((name,level))
        if name == 'os': return self.os
        if name == 'dotenv': return self.dotenv_module
        if level and name == 'domain.intraday_limits': return LIMITS
        if name == 'dotenv' or any(name == value.rstrip('.') or name.startswith(value) for value in FORBIDDEN):
            raise AssertionError('Actual graph/provider import prohibited')
        return builtins.__import__(name,globals,locals,fromlist,level)

    @contextmanager
    def file_spies(self):
        # Ancestor checks are synthetic. Path.resolve only computes the allowed
        # source/default path; no real .env is inspected or opened.
        with ExitStack() as stack:
            stack.enter_context(patch.object(Path,'exists',lambda path:self.exists(path)))
            for method in ('open','read_text','read_bytes','write_text','write_bytes','mkdir','iterdir','glob','rglob','is_file','is_dir'):
                stack.enter_context(patch.object(Path,method,self.blocked_file))
            yield

    def import_actual(self):
        name = '_cf040_config_case_' + str(next(SERIAL))
        spec = importlib.util.spec_from_file_location(name,ROOT/CONFIG_PATH)
        module = importlib.util.module_from_spec(spec)
        module.__package__ = '_cf040_closed_config'
        module.__dict__['__builtins__'] = dict(vars(builtins),__import__=self.import_config,open=self.blocked_file)
        sys.modules[name] = module
        with self.file_spies(): exec(compile(CONFIG_SOURCE,str(ROOT/CONFIG_PATH),'exec'),module.__dict__)
        self.config = module
        assert isinstance(module.__spec__.loader,importlib.machinery.SourceFileLoader)
        assert Path(module.__spec__.origin).resolve() == ROOT/CONFIG_PATH
        assert not self.events and not self.loads and not self.io
        assert not any(name == 'dotenv' for name,_ in self.imports)
        return module

    def initialize(self):
        with self.file_spies(): return self.config.initialize_runtime()


def assert_defaults(config):
    assert config.INTRADAY_FETCH_ENABLED is False and config.TECHNICAL_TRACE_ENABLED is True
    assert config.TECHNICAL_TRACE_PATH == str(config._DEFAULT_TRACE_PATH)


# This observation is at collection, before unit conftest/autouse fixtures run.
COLLECTION_PROBE = Probe({'INTRADAY_FETCH_ENABLED':'true','TECHNICAL_TRACE_ENABLED':'false','TECHNICAL_TRACE_PATH':PRIVATE})
COLLECTION_CONFIG = COLLECTION_PROBE.import_actual()
assert_defaults(COLLECTION_CONFIG)


def dependencies(probe):
    """Execute the actual selected definitions, never the legacy module chain."""
    tree = ast.parse(DEPENDENCIES_SOURCE)
    functions = {'_setup_technical_runtime','get_llm_client','get_fetcher','get_cache','get_trace_sink'}
    declarations = {'LlmClientFactory','default_openai_client'}
    selected = []
    for node in tree.body:
        if isinstance(node,ast.ImportFrom) and node.module in {'__future__','typing'}: selected.append(node)
        elif isinstance(node,ast.FunctionDef) and node.name in functions: selected.append(node)
        elif isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id in declarations for t in node.targets): selected.append(node)
        elif isinstance(node,ast.AnnAssign) and isinstance(node.target,ast.Name) and node.target.id in declarations: selected.append(node)
    assert {n.name for n in selected if isinstance(n,ast.FunctionDef)} == functions
    assert len([n for n in selected if isinstance(n,(ast.Assign,ast.AnnAssign))]) == 2
    name = '_cf040_selected_dependencies_' + str(next(SERIAL))
    module = ModuleType(name)
    module.__file__ = str(ROOT/DEPENDENCIES_PATH)
    events = probe.events
    class Unavailable(RuntimeError): pass
    def unavailable(): return Unavailable('AI_UNAVAILABLE')
    def llm(*,deadline=None): events.append(('llm_factory',deadline)); return ('llm',deadline)
    def cache(): events.append(('cache_factory',)); return 'synthetic-cache'
    def sink(path): events.append(('trace_factory',path)); return ('synthetic-trace',path)
    def importer(fullname, globals=None, locals=None, fromlist=(), level=0):
        events.append(('dependency_import',fullname))
        if fullname == 'src.agents.technical.config': return probe.config
        if fullname == 'src.agents.technical.infrastructure.openai_llm_client':
            assert probe.config.initialize_runtime() is probe.config.initialize_runtime()
            return SimpleNamespace(default_openai_client=llm)
        if fullname == 'src.agents.technical.infrastructure.cache_service': return SimpleNamespace(default_cache=cache)
        if fullname == 'src.agents.technical.infrastructure.observability.trace_logger': return SimpleNamespace(JsonlTraceSink=sink)
        if fullname in {'typing','__future__'}: return builtins.__import__(fullname,globals,locals,fromlist,level)
        raise AssertionError('Unexpected dependency import')
    module.__dict__.update(Deadline=DEADLINE.Deadline,ai_unavailable=unavailable,
        __builtins__=dict(vars(builtins),__import__=importer,open=probe.blocked_file))
    with probe.file_spies(): exec(compile(ast.Module(body=selected,type_ignores=[]),module.__file__,'exec'),module.__dict__)
    assert not any(e[0] == 'dependency_import' and e[1].startswith('src.') for e in events)
    return module


def test_collection_import_attempts_are_zero_despite_synthetic_true_values():
    assert_defaults(COLLECTION_CONFIG)
    assert not COLLECTION_PROBE.events and not COLLECTION_PROBE.loads and not COLLECTION_PROBE.io
    assert not any(name == 'dotenv' for name,_ in COLLECTION_PROBE.imports)
    assert COLLECTION_CONFIG.TECHNICAL_TRACE_PATH != PRIVATE


@pytest.mark.parametrize('raw,expected',[('1',True),(' true ',True),('YES',True),('On',True),('0',False),(' false ',False),('NO',False),('OFF',False),('',False)])
def test_actual_runtime_parsing_snapshot_and_env_priority(raw,expected):
    p=Probe({'INTRADAY_FETCH_ENABLED':raw,'TECHNICAL_TRACE_ENABLED':raw,'TECHNICAL_TRACE_PATH':'synthetic-process-trace'},
        {'INTRADAY_FETCH_ENABLED':'true','TECHNICAL_TRACE_ENABLED':'true','TECHNICAL_TRACE_PATH':'synthetic-dotenv-trace'})
    config=p.import_actual(); snapshot=p.initialize()
    assert snapshot.intraday_fetch_enabled is expected and snapshot.trace_enabled is expected
    assert snapshot.trace_path=='synthetic-process-trace'
    assert (config.INTRADAY_FETCH_ENABLED,config.TECHNICAL_TRACE_ENABLED,config.TECHNICAL_TRACE_PATH)==(expected,expected,'synthetic-process-trace')
    assert len(p.loads)==1 and p.loads[0][1] is False
    assert any(n=='dotenv' for n,_ in p.imports) and p.io and all(e[0]=='exists' for e in p.io)
    p.env.update(INTRADAY_FETCH_ENABLED='false',TECHNICAL_TRACE_PATH='changed-after-snapshot')
    before=(len(p.events),len(p.loads),len(p.io))
    assert p.initialize() is snapshot and (len(p.events),len(p.loads),len(p.io))==before
    with pytest.raises(FrozenInstanceError): snapshot.trace_enabled=False


@pytest.mark.parametrize('present',[False,True])
def test_unset_defaults_and_dotenv_mapping_are_explicit_only(present):
    p=Probe(present=present);config=p.import_actual();snapshot=p.initialize()
    assert snapshot.intraday_fetch_enabled is False and snapshot.trace_enabled is True
    assert snapshot.trace_path==str(config._DEFAULT_TRACE_PATH)
    assert len(p.loads)==int(present)
    p2=Probe(dotenv={'INTRADAY_FETCH_ENABLED':'true','TECHNICAL_TRACE_ENABLED':'off','TECHNICAL_TRACE_PATH':'synthetic-dotenv'})
    p2.import_actual();snapshot2=p2.initialize()
    assert (snapshot2.intraday_fetch_enabled,snapshot2.trace_enabled,snapshot2.trace_path)==(True,False,'synthetic-dotenv')


def test_invalid_bool_warning_and_snapshot_repr_do_not_expose_values():
    p=Probe({'INTRADAY_FETCH_ENABLED':PRIVATE,'TECHNICAL_TRACE_ENABLED':PRIVATE,'TECHNICAL_TRACE_PATH':PRIVATE});p.import_actual()
    with pytest.warns(UserWarning) as observed: snapshot=p.initialize()
    assert len(observed)==2 and all(PRIVATE not in str(w.message) for w in observed)
    assert snapshot.intraday_fetch_enabled is False and snapshot.trace_enabled is False
    assert PRIVATE not in repr(snapshot)


@pytest.mark.parametrize('phase',['dotenv','second_getenv','path_type','reentrant'])
def test_failed_initialization_is_atomic_safe_and_latched(phase):
    p=Probe({'INTRADAY_FETCH_ENABLED':'true','TECHNICAL_TRACE_ENABLED':'off','TECHNICAL_TRACE_PATH':'synthetic-path'})
    config=p.import_actual()
    if phase=='dotenv': p.on_load=lambda:(_ for _ in ()).throw(RuntimeError(PRIVATE))
    elif phase=='second_getenv': p.fail_get='TECHNICAL_TRACE_ENABLED'
    elif phase=='path_type': p.env['TECHNICAL_TRACE_PATH']=object()
    else:p.on_load=config.initialize_runtime
    with pytest.raises(RuntimeError) as error:p.initialize()
    assert PRIVATE not in str(error.value) and error.value.__suppress_context__
    assert_defaults(config)
    before=(len(p.loads),len(p.events),len(p.io))
    p.on_load=None;p.fail_get=None;p.env.clear()
    with pytest.raises(RuntimeError):p.initialize()
    assert before==(len(p.loads),len(p.events),len(p.io))
    assert_defaults(config)


LATE = [prefix+suffix for prefix in ('src.agents.technical.','agents.technical.') for suffix in (
    'application.orchestration.pipeline_steps','application.orchestration.technical_graph',
    'application.orchestration.technical_supervisor','application.agent')]
@pytest.mark.parametrize('name',LATE)
def test_late_pipeline_or_graph_is_rejected_before_any_settings_read(name):
    p=Probe({'INTRADAY_FETCH_ENABLED':'true'});config=p.import_actual()
    with patch.dict(sys.modules,{name:ModuleType(name)}):
        with pytest.raises(RuntimeError) as error:p.initialize()
    assert PRIVATE not in str(error.value) and not p.loads and not p.events and not p.io
    assert_defaults(config)
    with pytest.raises(RuntimeError):p.initialize()
    assert not p.events and not p.loads


def test_graph_appearing_during_loader_is_rejected_before_snapshot_publish(monkeypatch):
    p=Probe({'INTRADAY_FETCH_ENABLED':'true'});config=p.import_actual()
    p.on_load=lambda:monkeypatch.setitem(sys.modules,LATE[0],ModuleType(LATE[0]))
    with pytest.raises(RuntimeError):p.initialize()
    assert_defaults(config)
    assert len(p.loads)==1


def test_concurrent_callers_see_one_identical_complete_snapshot():
    p=Probe({'INTRADAY_FETCH_ENABLED':'true','TECHNICAL_TRACE_ENABLED':'off','TECHNICAL_TRACE_PATH':'synthetic-concurrent'})
    config=p.import_actual();entered=threading.Event();release=threading.Event()
    def loading():entered.set();assert release.wait(2)
    p.on_load=loading
    with p.file_spies(),ThreadPoolExecutor(max_workers=8) as executor:
        futures=[executor.submit(config.initialize_runtime) for _ in range(8)]
        try:
            assert entered.wait(2)
            assert_defaults(config)
        finally:release.set()
        snapshots=[f.result(timeout=2) for f in futures]
    assert len({id(x) for x in snapshots})==1 and len(p.loads)==1
    assert (snapshots[0].intraday_fetch_enabled,snapshots[0].trace_enabled,snapshots[0].trace_path)==(True,False,'synthetic-concurrent')


def test_actual_kis_openai_loaders_keep_explicit_lazy_import_and_override_false():
    p=Probe({'KIS_API_KEY':' synthetic-process-key ','KIS_API_SECRET':' synthetic-process-secret ','KIS_BASE_URL':' https://synthetic.invalid/// ',
        'OPENAI_API_KEY':' synthetic-process-openai ','OPENAI_MODEL':' synthetic-process-model '},
        {'KIS_API_KEY':'dotenv-key','OPENAI_API_KEY':'dotenv-openai','OPENAI_MODEL':'dotenv-model'})
    config=p.import_actual()
    with p.file_spies():kis=config.load_kis_settings();llm=config.load_openai_settings()
    assert (kis.api_key,kis.api_secret,kis.base_url)==('synthetic-process-key','synthetic-process-secret','https://synthetic.invalid')
    assert (llm.api_key,llm.model)==('synthetic-process-openai','synthetic-process-model')
    assert len(p.loads)==2 and all(override is False for _,override in p.loads)
    assert 'synthetic-process-key' not in repr(kis) and 'synthetic-process-secret' not in repr(kis)
    assert 'synthetic-process-openai' not in repr(llm)
    assert_defaults(config)
    assert (config.KIS_TIMEOUT_SECONDS,config.KIS_MAX_RETRIES,config.KIS_BACKOFF_SECONDS)==(5,3,[1,2,4])
    assert (config.OPENAI_TIMEOUT_SECONDS,config.OPENAI_MAX_RETRIES,config.OPENAI_MAX_OUTPUT_TOKENS,config.OPENAI_STORE)==(35.0,0,3000,False)
    assert (config.INTRADAY_CONFIDENCE_ADJUSTMENT_CAP,config.INTRADAY_RISK_NOTE_MAX_COUNT)==(.05,3)


@pytest.mark.parametrize('factory',['get_llm_client','get_fetcher','get_cache','get_trace_sink'])
def test_actual_factory_setup_precedes_runtime_import_and_creation(factory):
    p=Probe({'TECHNICAL_TRACE_PATH':'synthetic-path'});p.import_actual();deps=dependencies(p)
    assert deps.default_openai_client is None
    with p.file_spies(): value=getattr(deps,factory)()
    loaded=next(i for i,e in enumerate(p.events) if e[0]=='dotenv_load')
    dependent=[i for i,e in enumerate(p.events) if e[0]=='dependency_import' and e[1].startswith('src.agents.technical.infrastructure.')]
    created=[i for i,e in enumerate(p.events) if e[0] in {'cache_factory','trace_factory','llm_factory'}]
    assert all(i>loaded for i in dependent+created)
    if factory=='get_llm_client':
        assert not created
        deadline=DEADLINE.Deadline(123.0)
        assert value(deadline)==('llm',deadline)
    elif factory=='get_fetcher':assert value is None and not dependent and not created
    elif factory=='get_cache':assert value=='synthetic-cache'
    else:assert value==('synthetic-trace','synthetic-path')


def test_trace_uses_snapshot_after_env_changes_and_disabled_trace_import_is_zero():
    p=Probe({'TECHNICAL_TRACE_ENABLED':'off','TECHNICAL_TRACE_PATH':PRIVATE});p.import_actual();deps=dependencies(p)
    with p.file_spies():assert deps.get_trace_sink() is None
    p.env['TECHNICAL_TRACE_ENABLED']='true'
    with p.file_spies():assert deps.get_trace_sink() is None
    assert not any(e[0]=='dependency_import' and 'trace_logger' in e[1] for e in p.events)
    p2=Probe({'TECHNICAL_TRACE_PATH':'original-synthetic-path'});p2.import_actual();d2=dependencies(p2);p2.initialize()
    p2.env['TECHNICAL_TRACE_PATH']='changed-path'
    with p2.file_spies():assert d2.get_trace_sink()==('synthetic-trace','original-synthetic-path')


def test_llm_override_point_and_safe_error_preserve_deadline_and_no_real_import():
    p=Probe();p.import_actual();deps=dependencies(p);seen=[]
    def custom(*,deadline=None):seen.append(deadline);return 'override-client'
    deps.default_openai_client=custom
    with p.file_spies(): factory=deps.get_llm_client()
    deadline=DEADLINE.Deadline(42.0)
    assert factory(deadline)=='override-client' and seen==[deadline]
    assert not any(e[0]=='dependency_import' and 'openai_llm_client' in e[1] for e in p.events)
    def failure(*,deadline=None):raise RuntimeError(PRIVATE)
    deps.default_openai_client=failure
    with pytest.raises(RuntimeError) as error:factory(deadline)
    assert str(error.value)=='AI_UNAVAILABLE' and error.value.__suppress_context__
    assert PRIVATE not in str(error.value)


@pytest.mark.parametrize('factory',['get_llm_client','get_fetcher','get_cache','get_trace_sink'])
def test_setup_failure_creates_no_client_and_does_not_expose_original(factory):
    p=Probe();p.import_actual();deps=dependencies(p)
    p.on_load=lambda:(_ for _ in ()).throw(RuntimeError(PRIVATE))
    with p.file_spies(),pytest.raises(RuntimeError) as error:getattr(deps,factory)()
    assert str(error.value)=='AI_UNAVAILABLE' and error.value.__suppress_context__
    assert not any(e[0] in {'cache_factory','trace_factory','llm_factory'} for e in p.events)
    assert not any(e[0]=='dependency_import' and 'infrastructure.' in e[1] for e in p.events)
    assert_defaults(p.config)


def test_selected_body_alias_and_graph_import_boundary_are_explicit():
    source=ast.parse(DEPENDENCIES_SOURCE)
    alias=next(n for n in source.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='LlmClientFactory' for t in n.targets))
    assert "'LlmClient'" in ast.unparse(alias)
    assert 'src.api.dependencies' not in sys.modules
    assert all(name not in sys.modules for name in LATE)
    for name in ('openai','redis','langgraph','src.supervisor.application.execution.adapters'):
        assert name not in sys.modules
    from scripts.safe_checks_bootstrap import valid_flow_origins
    assert valid_flow_origins(ROOT/'backend',sys.modules)


# Execute only the actual usage/text helpers and adapter class body. No SDK,
# client factory, config loader, graph or provider module is imported.
def usage_adapter():
    from http.cookiejar import CookieJar, DefaultCookiePolicy
    tree=ast.parse((ROOT/LLM_PATH).read_text())
    names={'_extract_usage','_extract_text','OpenAiLlmClient','_StrictLlmFailure',
           '_strict_json','_strict_sha','_strict_int','_strict_hash','_strict_same_callable',
           'TechnicalLlmPolicy','TechnicalTokenCount','TechnicalLlmEvidence',
           'TechnicalRequestLlmBudget','default_openai_client','_count_wire_json',
           '_TechnicalResponseStream','_TechnicalPhase','_TechnicalOwnedTransport',
           '_TechnicalOfficialCounter','_TechnicalOwnedBundle','official_count_openai_client'}
    nodes=[node for node in tree.body if isinstance(node,(ast.FunctionDef,ast.ClassDef)) and node.name in names]
    assert {node.name for node in nodes}==names
    constants={'_STRICT_MAX','_COUNT_MAPPING','_STRICT_POLICY_FIELDS','_STRICT_REASONS'}
    assignments=[node for node in tree.body if isinstance(node,ast.Assign)
                 and any(isinstance(t,ast.Name) and t.id in constants for t in node.targets)]
    assert len(assignments)==4
    module=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),*assignments,*nodes],type_ignores=[])
    class SDKError(Exception):pass
    class CallError(Exception):pass
    values={name:getattr(COLLECTION_CONFIG,name) for name in (
        'OPENAI_TEMPERATURE','OPENAI_MAX_OUTPUT_TOKENS','OPENAI_TIMEOUT_SECONDS','OPENAI_STORE','OPENAI_MAX_RETRIES')}
    selected=ModuleType('_cf049_selected_adapter_'+str(next(SERIAL)));sys.modules[selected.__name__]=selected
    selected.__dict__.update(values);values=selected.__dict__
    values.update(time=SimpleNamespace(perf_counter=lambda:1.0,monotonic=lambda:1.0),openai=SimpleNamespace(OpenAIError=SDKError),
                  asyncio=asyncio,dataclass=dataclass,fields=fields,replace=replace,datetime=datetime,UTC=UTC,
                  hashlib=hashlib,json=json,math=math,re=re,threading=threading,UUID=UUID,
                  CookieJar=CookieJar,DefaultCookiePolicy=DefaultCookiePolicy,
                  httpx=SimpleNamespace(BaseTransport=httpx.BaseTransport,SyncByteStream=httpx.SyncByteStream,Response=httpx.Response),
                  os=SimpleNamespace(environ={}),logging=SimpleNamespace(DEBUG=logging.DEBUG,getLogger=lambda _:SimpleNamespace(isEnabledFor=lambda _:False)),
                  logger=SimpleNamespace(warning=lambda *a,**kw:None),
                  DeadlineExceeded=DEADLINE.DeadlineExceeded,LlmCallError=CallError)
    exec(compile(ast.fix_missing_locations(module),str(ROOT/LLM_PATH),'exec'),values)
    return values


def strict_adapter(*,counter=True,calls=4,create=None):
    a=usage_adapter();clock=SimpleNamespace(value=0.0)
    started=datetime(2026,11,12,12,tzinfo=UTC)
    policy=dict(operation='technical.analysis.v1',enabled=True,currency='USD',supported_tickers=['000720'],
        user_daily_limit=3,service_daily_limit=10,daily_budget_nano=100000,attempt_reserve_nano=10000,
        deadline_seconds=60,model='synthetic-model',service_tier='default',price_id='cf049.synthetic.v1',
        price_evidence_sha256='a'*64,input_nano_per_token=10,output_nano_per_token=20,
        input_token_cap=100,output_token_cap=50,input_byte_cap=1000,output_byte_cap=500,max_calls=calls)
    raw=a['_strict_json'](policy)
    projection={f.name:policy[f.name] for f in fields(a['TechnicalLlmPolicy']) if f.name not in {'policy_json','policy_sha256'}}
    bound=a['TechnicalLlmPolicy'](policy_json=raw,policy_sha256=a['_strict_sha'](raw),**projection)
    class Counter:
        # Synthetic only: identity-authenticated receipts from this one fake
        # issuer are not evidence of any real tokenizer/count transport.
        mapping=a['_COUNT_MAPPING'];version='synthetic.v1';provenance_sha256='b'*64
        def __init__(self):self.issued=[];self.calls=[];self.after=None
        def count(self,**request):
            self.calls.append(request.copy())
            evidence=a['TechnicalTokenCount'](12,request['model'],request['mapping'],'synthetic.v1','b'*64,
                request['prompt_sha256'],request['projection_sha256'],request['request_sha256'],object(),request['ordinal'])
            self.issued.append((evidence,request.copy()))
            if self.after:self.after()
            return evidence
        def verify(self,evidence,**request):return any(evidence is issued and expected==request for issued,expected in self.issued)
    issuer=Counter() if counter else None
    budget=a['TechnicalRequestLlmBudget'](policy=bound,analysis_id=uuid4(),attempt_id=uuid4(),
        reserved_nano=10000,started_at=started,deadline_at=started+timedelta(seconds=60),counter=issuer,
        clock=lambda:clock.value,utcnow=lambda:started+timedelta(seconds=clock.value))
    dispatched=[]
    def response(**request):
        dispatched.append(request)
        return SimpleNamespace(status='completed',output_text=' synthetic result ',
            usage=SimpleNamespace(input_tokens=12,output_tokens=3,total_tokens=15))
    sdk=SimpleNamespace(max_retries=0,responses=SimpleNamespace(create=create or response))
    client=a['OpenAiLlmClient'](sdk,model='synthetic-model',temperature=None,max_output_tokens=50,
        timeout=30,store=False,strict=True,request_budget=budget)
    return SimpleNamespace(a=a,clock=clock,policy=bound,budget=budget,counter=issuer,sdk=sdk,client=client,
        dispatched=dispatched,response=response,started=started)


@pytest.mark.parametrize('values',[
    {},dict(input_tokens=1,output_tokens=2),
    dict(input_tokens=None,output_tokens=2,total_tokens=2),
    dict(input_tokens=True,output_tokens=2,total_tokens=3),
    dict(input_tokens='1',output_tokens=2,total_tokens=3),
    dict(input_tokens=1.9,output_tokens=2,total_tokens=3),
    dict(input_tokens=-1,output_tokens=2,total_tokens=1),
    dict(input_tokens=1,output_tokens=2,total_tokens=4),
    dict(input_tokens=1,output_tokens=False,total_tokens=1),
    dict(input_tokens=1,output_tokens=2,total_tokens=3.0),
])
def test_usage_invalid_or_missing_is_unknown_without_coercion(values):
    adapter=usage_adapter()
    assert adapter['_extract_usage'](SimpleNamespace(usage=SimpleNamespace(**values))) is None
    assert 'openai' not in sys.modules


@pytest.mark.parametrize('values',[(0,0,0),(11,22,33)])
def test_explicit_strict_usage_is_preserved(values):
    adapter=usage_adapter();usage=dict(zip(('input_tokens','output_tokens','total_tokens'),values))
    assert adapter['_extract_usage'](SimpleNamespace(usage=SimpleNamespace(**usage)))==usage
    assert adapter['_extract_usage'](SimpleNamespace()) is None


def test_actual_complete_does_not_carry_or_invent_usage_and_keeps_text():
    adapter=usage_adapter();responses=[
        SimpleNamespace(output_text='first',usage=SimpleNamespace(input_tokens=11,output_tokens=22,total_tokens=33)),
        SimpleNamespace(output_text='second',usage=SimpleNamespace(input_tokens='1',output_tokens=2,total_tokens=3)),
        SimpleNamespace(output_text='third',usage=None)]
    calls=[]
    def create(**kwargs):calls.append(kwargs);return responses.pop(0)
    client=adapter['OpenAiLlmClient'](SimpleNamespace(responses=SimpleNamespace(create=create)),model='synthetic-model')
    assert client.complete('synthetic-question')=='first' and client.last_usage==dict(input_tokens=11,output_tokens=22,total_tokens=33)
    assert client.complete('synthetic-question')=='second' and client.last_usage is None
    assert client.complete('synthetic-question')=='third' and client.last_usage is None
    assert len(calls)==3 and 'openai' not in sys.modules


def test_strict_selection_missing_budget_is_not_legacy_fallback():
    a=usage_adapter();calls=[]
    with pytest.raises(a['LlmCallError'],match='^TECHNICAL_LLM_POLICY_INVALID$'):
        a['OpenAiLlmClient'](SimpleNamespace(responses=SimpleNamespace(create=lambda **v:calls.append(v))),
            model='synthetic-model',strict=True)
    assert not calls


def test_missing_strict_factory_budget_cannot_read_settings_or_construct_SDK():
    a=usage_adapter();calls=[]
    def unavailable():calls.append(True);raise AssertionError('No settings allowed')
    a['load_openai_settings']=unavailable
    a['openai'].OpenAI=lambda **v:calls.append(True)
    with pytest.raises(a['LlmCallError']):a['default_openai_client'](strict=True)
    assert not calls


def test_legacy_and_explicit_factory_injection_are_preserved():
    h=strict_adapter();calls=[]
    h.a['load_openai_settings']=lambda:SimpleNamespace(api_key=PRIVATE,model='synthetic-model')
    def sdk(**values):calls.append(values);return h.sdk
    h.a['openai'].OpenAI=sdk
    client=h.a['default_openai_client'](strict=True,request_budget=h.budget,temperature=None,max_output_tokens=50)
    assert client._request_budget is h.budget and calls[0]['max_retries']==0
    assert client.complete('synthetic')=='synthetic result'
    legacy=h.a['default_openai_client']()
    assert legacy._strict is False and legacy._request_budget is None


@pytest.mark.parametrize('bad',[True,-1,101,2**63,'12',1.2,None])
def test_bad_or_over_cap_count_keeps_pair_hold_and_closes(bad):
    h=strict_adapter();original=h.counter.count
    def altered(**request):
        issued=original(**request);changed=replace(issued,input_tokens=bad)
        h.counter.issued.append((changed,request.copy()));return changed
    h.counter.count=altered
    with pytest.raises(h.a['LlmCallError']):h.client.complete('synthetic')
    assert not h.dispatched and len(h.budget.snapshot())==1 and h.budget.snapshot()[0].held_nano==2000


@pytest.mark.parametrize('field,value',[
    ('mapping','unreviewed'),('version',''),('provenance_sha256','c'*64),
    ('prompt_sha256','d'*64),('projection_sha256','d'*64),('request_sha256','d'*64),('receipt',True)])
def test_count_shape_mapping_and_authentication_are_bound_to_exact_request(field,value):
    h=strict_adapter();original=h.counter.count
    def altered(**request):
        issued=replace(original(**request),**{field:value})
        h.counter.issued.append((issued,request.copy()));return issued
    h.counter.count=altered
    with pytest.raises(h.a['LlmCallError']):h.client.complete('synthetic')
    assert not h.dispatched and len(h.budget.snapshot())==1


@pytest.mark.parametrize('remaining',[0,-1,float('nan'),float('inf'),True])
def test_expired_or_unknown_narrower_deadline_cannot_authorize_SDK(remaining):
    h=strict_adapter();h.client._deadline=SimpleNamespace(remaining_seconds=lambda:remaining)
    with pytest.raises(h.a['LlmCallError'],match='DEADLINE_EXCEEDED'):h.client.complete('synthetic')
    assert not h.budget.snapshot() and not h.counter.calls and not h.dispatched


def test_already_expired_request_has_no_count_or_SDK():
    h=strict_adapter();h.clock.value=61
    with pytest.raises(h.a['LlmCallError'],match='DEADLINE_EXCEEDED'):h.client.complete('synthetic')
    assert not h.counter.calls and not h.dispatched and not h.budget.snapshot()


def test_clock_conversion_cannot_extend_original_duration_when_UTC_lags():
    h=strict_adapter()
    with pytest.raises(h.a['_StrictLlmFailure'],match='^CLOCK_INVALID$'):
        h.a['TechnicalRequestLlmBudget'](policy=h.policy,analysis_id=uuid4(),attempt_id=uuid4(),
            reserved_nano=10000,started_at=h.started,deadline_at=h.started+timedelta(seconds=60),
            counter=h.counter,clock=lambda:0,utcnow=lambda:h.started-timedelta(seconds=60))
    assert not h.dispatched and not h.counter.calls


def test_clock_conversion_observation_delay_and_later_wall_rollback_do_not_extend():
    h=strict_adapter();clock=[0]
    def now():clock[0]=5;return h.started+timedelta(seconds=20)
    budget=h.a['TechnicalRequestLlmBudget'](policy=h.policy,analysis_id=uuid4(),attempt_id=uuid4(),
        reserved_nano=10000,started_at=h.started,deadline_at=h.started+timedelta(seconds=60),
        counter=h.counter,clock=lambda:clock[0],utcnow=now)
    assert budget._remaining()==35
    budget._utcnow=lambda:h.started-timedelta(seconds=60);clock[0]=39
    assert budget._remaining()==1
    clock[0]=41
    with pytest.raises(h.a['_StrictLlmFailure'],match='DEADLINE_EXCEEDED'):budget._remaining()


def test_caller_policy_reference_mutation_does_not_rebind_frozen_budget():
    h=strict_adapter();object.__setattr__(h.policy,'model','mutated')
    assert h.client.complete('synthetic')=='synthetic result'
    assert h.budget.snapshot()[0].model=='synthetic-model'
    object.__setattr__(h.budget._policy,'model','mutated')
    with pytest.raises(h.a['LlmCallError']):h.client.complete('synthetic')
    assert len(h.dispatched)==1


@pytest.mark.parametrize('change',[
    {'input_token_cap':True},{'output_token_cap':0},{'max_calls':5},{'input_nano_per_token':1.2},
    {'output_nano_per_token':-1},{'attempt_reserve_nano':2**63},{'service_tier':'priority'},
    {'policy_sha256':'f'*64},{'model':PRIVATE},{'price_evidence_sha256':'unverified'},
])
def test_strict_full_policy_and_projection_must_match(change):
    h=strict_adapter()
    altered=replace(h.policy,**change)
    with pytest.raises(h.a['_StrictLlmFailure']):altered.validated()
    assert not h.dispatched


@pytest.mark.parametrize('bad',[None,True,12,{'input_tokens':12}])
def test_bare_count_value_or_unverified_receipt_cannot_authorize(bad):
    h=strict_adapter();h.counter.count=lambda **v:bad
    with pytest.raises(h.a['LlmCallError']):h.client.complete('synthetic')
    assert not h.dispatched and len(h.budget.snapshot())==1 and h.budget.closed_reason


def test_default_missing_counter_and_forged_receipt_are_closed():
    h=strict_adapter(counter=False)
    with pytest.raises(h.a['LlmCallError'],match='COUNT_UNAVAILABLE'):h.client.complete('synthetic')
    assert not h.dispatched and not h.budget.snapshot()
    h=strict_adapter();original=h.counter.count
    def forged(**request):return replace(original(**request),receipt=object())
    h.counter.count=forged
    with pytest.raises(h.a['LlmCallError'],match='COUNT_INVALID'):h.client.complete('synthetic')
    assert not h.dispatched


@pytest.mark.parametrize('field,value',[
    ('model','other'),('_max_output_tokens',51),('_max_output_tokens',True),('_store',True),
    ('_timeout',float('nan')),('_timeout',0),('_temperature',True),
])
def test_strict_SDK_arguments_do_not_drift(field,value):
    h=strict_adapter();setattr(h.client,field,value)
    with pytest.raises(h.a['LlmCallError']):h.client.complete('synthetic')
    assert not h.dispatched


@pytest.mark.parametrize('retry',[None,True,1,'0'])
def test_retry_zero_requires_exact_SDK_evidence(retry):
    h=strict_adapter();h.sdk.max_retries=retry
    with pytest.raises(h.a['LlmCallError']):h.client.complete('synthetic')
    assert not h.dispatched


@pytest.mark.parametrize('prompt',[None,12,'','x'*1001,'\ud800'])
def test_invalid_prompt_never_enters_count_or_SDK(prompt):
    h=strict_adapter()
    with pytest.raises(h.a['LlmCallError']):h.client.complete(prompt)
    assert not h.dispatched and not h.counter.calls


def test_successful_calls_keep_all_evidence_and_N_plus_one_has_no_refund():
    h=strict_adapter(calls=2)
    for _ in range(2):assert h.client.complete('synthetic')=='synthetic result'
    with pytest.raises(h.a['LlmCallError'],match='BUDGET_EXCEEDED'):h.client.complete('synthetic')
    records=h.budget.snapshot()
    assert len(records)==len(h.dispatched)==2 and sum(v.held_nano for v in records)==4000
    assert all(v.entered and v.response_received and v.text_accepted and v.usage==(12,3,15) and v.estimated_nano==180 for v in records)
    with pytest.raises(FrozenInstanceError):records[0].held_nano=0
    object.__setattr__(records[0],'held_nano',0)
    assert h.budget.snapshot()[0].held_nano==2000
    assert PRIVATE not in repr(records) and not any('synthetic' in repr(v) for v in records)


def test_snapshot_UUIDs_are_copies_even_for_unsafe_consumer_mutation():
    h=strict_adapter();h.client.complete('synthetic')
    original=h.budget.snapshot()[0];first=h.budget.snapshot()[0]
    object.__setattr__(first.analysis_id,'int',uuid4().int)
    object.__setattr__(first.attempt_id,'int',uuid4().int)
    assert h.budget.snapshot()[0]==original


def test_all_adapter_instances_must_share_the_same_request_budget():
    h=strict_adapter(calls=2)
    second=h.a['OpenAiLlmClient'](h.sdk,model='synthetic-model',temperature=None,max_output_tokens=50,
        timeout=30,store=False,strict=True,request_budget=h.budget)
    assert h.client.complete('first')=='synthetic result'
    assert second.complete('second')=='synthetic result'
    with pytest.raises(h.a['LlmCallError']):second.complete('third')
    assert len(h.dispatched)==2 and [r.ordinal for r in h.budget.snapshot()]==[1,2]


def test_post_count_semantic_mutation_is_not_transport_recalculation():
    h=strict_adapter();reserve=h.budget._reserve
    def tamper(adapter,request,*args):
        ordinal=reserve(adapter,request,*args);request['input']='different';return ordinal
    h.budget._reserve=tamper
    with pytest.raises(h.a['LlmCallError'],match='COUNT_INVALID'):h.client.complete('synthetic')
    record,=h.budget.snapshot();assert not record.entered and record.held_nano==2000 and not h.dispatched


def test_evidence_and_errors_never_contain_prompt_or_raw_provider_metadata():
    h=strict_adapter();h.client.complete(PRIVATE)
    record,=h.budget.snapshot()
    assert all(PRIVATE not in str(getattr(record,field.name)) for field in fields(record))
    assert record.prompt_sha256==h.a['_strict_sha'](PRIVATE)


@pytest.mark.parametrize('status',['incomplete','failed',None,'unknown'])
@pytest.mark.parametrize('text',['valid-looking',''])
def test_usage_survives_rejected_response_status_and_text(status,text):
    h=strict_adapter()
    h.sdk.responses.create=lambda **v:SimpleNamespace(status=status,output_text=text,
        usage=SimpleNamespace(input_tokens=12,output_tokens=3,total_tokens=15))
    with pytest.raises(h.a['LlmCallError']):h.client.complete('synthetic')
    record,=h.budget.snapshot()
    assert record.entered and record.response_received and record.usage==(12,3,15)
    assert not record.text_accepted and record.reason=='RESPONSE_NOT_COMPLETED' and h.client.last_usage is None


@pytest.mark.parametrize('kind',['missing','invalid','count','output_cap','empty','bytes','refusal','metadata'])
def test_observed_usage_and_unknown_are_distinct_and_sticky_closed(kind):
    h=strict_adapter();response=h.response()
    if kind=='missing':response.usage=None
    if kind=='invalid':response.usage.input_tokens=True
    if kind=='count':response.usage=SimpleNamespace(input_tokens=11,output_tokens=3,total_tokens=14)
    if kind=='output_cap':response.usage=SimpleNamespace(input_tokens=12,output_tokens=51,total_tokens=63)
    if kind=='empty':response.output_text=' '
    if kind=='bytes':response.output_text='가'*167
    if kind=='refusal':response.output=[SimpleNamespace(content=[SimpleNamespace(type='refusal')])]
    if kind=='metadata':response.model=PRIVATE
    h.sdk.responses.create=lambda **v:response
    with pytest.raises(h.a['LlmCallError']) as error:h.client.complete('synthetic')
    record,=h.budget.snapshot();counted=len(h.counter.calls)
    assert (record.usage is None)==(kind in {'missing','invalid'})
    assert record.held_nano==2000 and not record.text_accepted and PRIVATE not in str(error.value)
    with pytest.raises(h.a['LlmCallError']):h.client.complete('synthetic')
    assert len(h.budget.snapshot())==1 and len(h.counter.calls)==counted


@pytest.mark.parametrize('failure',[RuntimeError(PRIVATE),asyncio.CancelledError(PRIVATE),KeyboardInterrupt(PRIVATE)])
def test_SDK_failure_keeps_consumed_hold_and_propagates_safe_cancellation(failure):
    h=strict_adapter()
    def fail(**v):raise failure
    h.sdk.responses.create=fail
    expected=asyncio.CancelledError if isinstance(failure,asyncio.CancelledError) else KeyboardInterrupt if isinstance(failure,KeyboardInterrupt) else h.a['LlmCallError']
    with pytest.raises(expected) as error:h.client.complete('synthetic')
    record,=h.budget.snapshot()
    assert record.entered and not record.response_received and record.usage is None and record.held_nano==2000
    assert record.reason=='SDK_UNKNOWN' and PRIVATE not in str(error.value) and error.value.__suppress_context__


def test_counted_semantics_survive_smaller_transport_timeout_but_not_meaning_drift():
    h=strict_adapter();h.counter.after=lambda:setattr(h.clock,'value',40)
    assert h.client.complete('synthetic')=='synthetic result'
    assert h.dispatched[0]['timeout']==20 and 'timeout' not in h.counter.calls[0]
    assert h.counter.calls[0]['ordinal']==1
    assert h.counter.calls[0]['projection_sha256']==h.a['_strict_sha'](h.a['_strict_json']({'model':'synthetic-model','input':'synthetic'}))
    h=strict_adapter();h.counter.after=lambda:setattr(h.client,'model','drift')
    with pytest.raises(h.a['LlmCallError']):h.client.complete('synthetic')
    assert not h.dispatched


@pytest.mark.parametrize('drift',['SDK','responses','create','captured_retry'])
def test_count_wait_cannot_replace_actual_dispatch_identity(drift):
    h=strict_adapter();old=h.sdk
    def change():
        if drift=='SDK':h.client._client=SimpleNamespace(max_retries=0,responses=SimpleNamespace(create=h.response))
        elif drift=='responses':old.responses=SimpleNamespace(create=h.response)
        elif drift=='create':old.responses.create=lambda **request:h.response(**request)
        else:
            old.max_retries=1
            h.client._client=SimpleNamespace(max_retries=0,responses=SimpleNamespace(create=h.response))
    h.counter.after=change
    with pytest.raises(h.a['LlmCallError'],match='SDK_POLICY_INVALID'):h.client.complete('synthetic')
    assert not h.dispatched and len(h.budget.snapshot())==1


def test_bound_SDK_method_identity_is_checked_without_false_rejection():
    h=strict_adapter()
    class Responses:
        def create(self,**request):return h.response(**request)
    h.sdk.responses=Responses()
    assert h.client.complete('synthetic')=='synthetic result'


@pytest.mark.parametrize('phase',['counter','SDK'])
def test_exact_internal_exception_cannot_inject_arbitrary_reason(phase):
    h=strict_adapter()
    def fail(**request):
        error=h.a['_StrictLlmFailure']('COUNT_INVALID');error.args=(PRIVATE,)
        raise error
    if phase=='counter':h.counter.count=fail
    else:h.sdk.responses.create=fail
    with pytest.raises(h.a['LlmCallError']) as error:h.client.complete('synthetic')
    assert PRIVATE not in str(error.value) and PRIVATE not in str(h.budget.closed_reason)
    assert all(record.reason in h.a['_STRICT_REASONS'] for record in h.budget.snapshot())


def test_expiry_after_consumption_keeps_ordinal_without_SDK_entry_or_refund():
    h=strict_adapter();enter=h.budget._enter
    def expire(*args):h.clock.value=61;return enter(*args)
    h.budget._enter=expire
    with pytest.raises(h.a['LlmCallError'],match='DEADLINE_EXCEEDED'):h.client.complete('synthetic')
    record,=h.budget.snapshot()
    assert not h.dispatched and not record.entered and record.held_nano==2000


@pytest.mark.parametrize('clock_kind',['monotonic','UTC','adapter'])
def test_late_completed_response_keeps_usage_but_never_accepts_text(clock_kind):
    h=strict_adapter();remaining=[1.0]
    if clock_kind=='adapter':h.client._deadline=SimpleNamespace(remaining_seconds=lambda:remaining[0])
    def late(**request):
        result=h.response(**request)
        if clock_kind=='monotonic':h.budget._clock=lambda:61
        elif clock_kind=='UTC':h.budget._utcnow=lambda:h.started+timedelta(seconds=61)
        else:remaining[0]=0
        return result
    h.sdk.responses.create=late
    with pytest.raises(h.a['LlmCallError'],match='DEADLINE_EXCEEDED'):h.client.complete('synthetic')
    record,=h.budget.snapshot()
    assert record.entered and record.response_received and record.usage==(12,3,15)
    assert not record.text_accepted and record.held_nano==2000 and h.client.last_usage is None
    assert h.budget.closed_reason=='DEADLINE_EXCEEDED'


def test_shared_budget_concurrent_cap_and_request_isolation():
    h=strict_adapter(calls=2)
    def call(_):
        try:return h.client.complete('synthetic')
        except h.a['LlmCallError']:return None
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(call,range(4)))
    assert len(h.dispatched)<=2 and len(h.budget.snapshot())<=2
    assert [r.ordinal for r in h.budget.snapshot()]==list(range(1,len(h.budget.snapshot())+1))
    other=strict_adapter(calls=1);assert other.client.complete('synthetic')=='synthetic result'
    assert other.budget.snapshot()[0].request_sha256!=h.budget.snapshot()[0].request_sha256


@pytest.mark.parametrize('entered_first',[False,True])
def test_closed_linearization_separates_consumed_and_entered_calls(entered_first):
    h=strict_adapter();paused=threading.Event();release=threading.Event();original=h.budget._enter
    def gated(ordinal,*args):
        if ordinal==1:
            if entered_first:
                timeout=original(ordinal,*args);paused.set();assert release.wait(2);return timeout
            paused.set();assert release.wait(2)
        return original(ordinal,*args)
    h.budget._enter=gated
    def dispatch(**request):
        h.dispatched.append(request)
        if threading.current_thread().name.startswith('cf049-A'):return h.response()
        return SimpleNamespace(status='completed',output_text='x',usage=None)
    h.sdk.responses.create=dispatch
    errors=[]
    def first():
        try:h.client.complete('A')
        except h.a['LlmCallError']:errors.append(True)
    worker=threading.Thread(target=first,name='cf049-A');worker.start()
    try:
        assert paused.wait(2)
        with pytest.raises(h.a['LlmCallError']):h.client.complete('B')
    finally:release.set();worker.join(2)
    assert not worker.is_alive()
    a,b=h.budget.snapshot()
    assert a.entered is entered_first and b.entered and b.reason=='USAGE_UNKNOWN'
    assert a.held_nano==b.held_nano==2000 and len(h.budget.snapshot())==2
    assert a.text_accepted is entered_first and bool(errors) is not entered_first


def test_reverse_response_order_keeps_usage_on_original_ordinal():
    h=strict_adapter();paused=threading.Event();release=threading.Event()
    def dispatch(**request):
        if request['input']=='A':paused.set();assert release.wait(2)
        n=3 if request['input']=='A' else 4
        return SimpleNamespace(status='completed',output_text='ok',usage=SimpleNamespace(input_tokens=12,output_tokens=n,total_tokens=12+n))
    h.sdk.responses.create=dispatch;errors=[]
    def first():
        try:h.client.complete('A')
        except BaseException:errors.append(True)
    worker=threading.Thread(target=first);worker.start()
    try:assert paused.wait(2);assert h.client.complete('B')=='ok'
    finally:release.set();worker.join(2)
    assert not worker.is_alive() and not errors
    a,b=h.budget.snapshot();assert a.usage==(12,3,15) and b.usage==(12,4,16)


# CF051 uses real Request/Response/stream protocol objects but synthetic SDK,
# HTTP client/transport constructors and bytes. No SDK import or socket exists.
def official_adapter(*,calls=4,count_body=None,status=200,chunks=None,headers=None,
                     request_change=None,inner=None,constructor_failure=None,defer=False,wrap_transport_errors=False,**limits):
    h=strict_adapter(counter=False,calls=calls);events=[];sent=[];closed=[];read=[]
    a=h.a
    class Parts(httpx.SyncByteStream):
        def __init__(self,parts):self.parts=parts;self.closed=False
        def __iter__(self):
            for part in self.parts:read.append(len(part));yield part
        def close(self):self.closed=True;closed.append('response')
    class Transport:
        def __init__(self,**kwargs):
            events.append(('transport',kwargs));self.closed=False
            if constructor_failure=='transport':raise RuntimeError(PRIVATE)
        def handle_request(self,request):
            sent.append(request)
            if inner:return inner(request,Parts)
            body=(b'{"object":"response.input_tokens","input_tokens":12}' if count_body is None else count_body) if request.url.path.endswith('input_tokens') else json.dumps(dict(status='completed',output_text=' official result ',usage=dict(input_tokens=12,output_tokens=3,total_tokens=15))).encode()
            parts=chunks if chunks is not None else [body[:7],body[7:]]
            hs={'Content-Type':'application/json','Content-Length':str(sum(map(len,parts)))}
            hs.update(headers or {})
            return httpx.Response(status,headers=hs,stream=Parts(parts))
        def close(self):self.closed=True;closed.append('transport')
    class Client:
        def __init__(self,**kwargs):
            events.append(('client',kwargs))
            if constructor_failure=='client':raise RuntimeError(PRIVATE)
            self._transport=kwargs['transport'];self._trust_env=kwargs['trust_env']
            self.follow_redirects=kwargs['follow_redirects'];self._mounts={};self._event_hooks={'request':[],'response':[]};self.cookies=httpx.Cookies(kwargs.get('cookies'))
        def close(self):closed.append('client');self._transport.close()
    def send(sdk,path,request,timeout,streaming=False):
        values=dict(sdk.default_headers);values={k:v for k,v in values.items() if type(v) is str}
        values.update(Authorization='Bearer '+sdk.api_key,Host='api.openai.com',
            **{'Content-Type':'application/json','X-Stainless-Retry-Count':'0','X-Stainless-Read-Timeout':str(timeout)})
        if streaming:values['X-Stainless-Raw-Response']='stream'
        raw=json.dumps(request,ensure_ascii=False).encode()
        values['Content-Length']=str(len(raw))
        req=httpx.Request('POST','https://api.openai.com/v1/'+path,content=raw,headers=values,
            extensions={'timeout':dict.fromkeys(('connect','read','write','pool'),timeout)})
        if request_change:request_change(req)
        try:return sdk._client._transport.handle_request(req)
        except a['_StrictLlmFailure'] as error:
            if wrap_transport_errors:raise RuntimeError(PRIVATE) from error
            raise
    class CountContext:
        def __init__(self,sdk,request,timeout):self.sdk=sdk;self.request=request;self.timeout=timeout;events.append(('context-created',None))
        def __enter__(self):
            events.append(('context-entered',None));self.response=send(self.sdk,'responses/input_tokens',self.request,self.timeout,True)
            return self
        def iter_bytes(self):return self.response.iter_bytes()
        def __exit__(self,*args):self.response.close()
    class SDK:
        def __init__(self,**kwargs):
            events.append(('sdk',kwargs))
            if constructor_failure=='sdk':raise RuntimeError(PRIVATE)
            self._client=kwargs['http_client'];self.max_retries=kwargs['max_retries'];self.base_url=kwargs['base_url'];self.api_key=kwargs['api_key']
            self.default_headers={'Accept':'application/json','User-Agent':'OpenAI/Python synthetic',**kwargs['default_headers']}
            sdk=self
            class Responses:
                def create(self,**request):
                    timeout=request.pop('timeout');response=send(sdk,'responses',request,timeout)
                    try:v=json.loads(response.read())
                    finally:response.close()
                    v['usage']=SimpleNamespace(**v['usage']);return SimpleNamespace(**v)
            self.responses=Responses()
            self.responses.input_tokens=SimpleNamespace(with_streaming_response=SimpleNamespace(
                count=lambda **request:CountContext(self,{k:v for k,v in request.items() if k!='timeout'},request['timeout'])))
        def close(self):closed.append('sdk');self._client.close()
    a['httpx']=SimpleNamespace(HTTPTransport=Transport,Client=Client,Response=httpx.Response)
    a['openai'].OpenAI=SDK;a['openai'].omit=object()
    opts=dict(request_wire_cap=4096,count_wire_cap=1024,generation_wire_cap=4096,count_version='official.synthetic.v1',
        count_provenance_sha256='c'*64,timeout=30)
    opts.update(limits)
    h.official_options=opts;h.events=events;h.sent=sent;h.closed=closed;h.read=read
    def factory():return a['official_count_openai_client'](request_budget=h.budget,api_key=PRIVATE,**opts)
    h.factory=factory
    if constructor_failure or defer:h.client=None
    else:h.client=factory();h.sdk=h.client._client
    return h


def test_official_count_actual_transport_and_complete_share_owned_bundle():
    h=official_adapter(calls=2)
    assert h.events[0]==('transport',dict(verify=True,trust_env=False,proxy=None,retries=0))
    assert h.events[1][1]['trust_env'] is False and h.events[1][1]['follow_redirects'] is False
    assert all(h.events[1][1][k] is None for k in ('proxy','mounts','event_hooks'))
    config=h.events[2][1]
    assert all(config[k] is not None for k in ('api_key','base_url','admin_api_key','organization','project','webhook_secret'))
    assert config['max_retries']==0 and config['default_query']=={}
    for _ in range(2):assert h.client.complete('synthetic')=='official result'
    assert [r.url.path for r in h.sent]==['/v1/responses/input_tokens','/v1/responses']*2
    assert all(v.count_entered and v.count_response_received and v.count_validated and v.entered and v.counted_input_tokens==12 for v in h.budget.snapshot())
    assert 'sdk' not in h.closed and 'client' not in h.closed
    h.client.close();h.client.close();assert h.closed.count('client')==h.closed.count('transport')==1
    with pytest.raises(h.a['LlmCallError']):h.client.complete('synthetic')
    assert len(h.sent)==4


def test_official_context_creation_is_not_send_and_direct_phase_calls_are_closed():
    h=official_adapter();b=h.budget._official_bundle
    ctx=b.count_method(model='synthetic-model',input='synthetic',timeout=1)
    assert not h.sent and h.events[-1][0]=='context-created'
    with pytest.raises(h.a['_StrictLlmFailure']):ctx.__enter__()
    with pytest.raises(h.a['_StrictLlmFailure']):h.sdk.responses.create(model='synthetic-model',input='synthetic',timeout=1)
    with pytest.raises(h.a['_StrictLlmFailure']):b.counter.count(ordinal=1)
    assert not h.sent;h.client.close()


@pytest.mark.parametrize('body',[
    b'{"object":"response.input_tokens","input_tokens":true}',
    b'{"object":"response.input_tokens","input_tokens":12.0}',
    b'{"object":"response.input_tokens","input_tokens":"12"}',
    b'{"object":"response.input_tokens","input_tokens":-1}',
    b'{"object":"response.input_tokens","input_tokens":101}',
    b'{"object":"response.input_tokens","input_tokens":12,"input_tokens":13}',
    b'{"object":"response.input_tokens","input_tokens":NaN}',
    b'{"object":"wrong","input_tokens":12}',b'{"object":"response.input_tokens","input_tokens":12,"extra":"private"}',
    b'[]',b'null',b'\xff',b'{'])
def test_official_count_strict_raw_wire_failure_preserves_pair_hold(body):
    h=official_adapter(count_body=body)
    with pytest.raises(h.a['LlmCallError']) as error:h.client.complete('synthetic')
    record,=h.budget.snapshot()
    assert record.count_entered and record.count_response_received and not record.count_validated and not record.entered
    assert record.held_nano==2000 and len(h.sent)==1 and h.budget.closed_reason and PRIVATE not in str(error.value)
    with pytest.raises(h.a['LlmCallError']):h.client.complete('again')
    assert len(h.sent)==1;h.client.close()


@pytest.mark.parametrize('status',[201,301,400,429,500])
def test_transport_closes_non200_before_SDK_can_read_error_body(status):
    h=official_adapter(status=status,chunks=[PRIVATE.encode()])
    with pytest.raises(h.a['LlmCallError']):h.client.complete('synthetic')
    assert not h.read and 'response' in h.closed and len(h.sent)==1
    assert h.budget.snapshot()[0].count_entered;h.client.close()


@pytest.mark.parametrize('headers,chunks',[
    ({'Content-Encoding':'gzip'},[b'x']),({'Content-Length':'99999'},[b'x']),
    ({'Content-Length':'1'},[b'xx']),({'Content-Length':'9'},[b'x']),
    ({'Content-Length':'-1'},[b'x']),({'Content-Length':'1, 1'},[b'x']),
    ({},[b'x'*600,b'y'*600]),
])
def test_owned_stream_cap_encoding_length_and_chunk_aggregate(headers,chunks):
    h=official_adapter(headers=headers,chunks=chunks)
    with pytest.raises(h.a['LlmCallError']):h.client.complete('synthetic')
    assert 'response' in h.closed and len(h.sent)==1 and not h.budget.snapshot()[0].entered;h.client.close()


@pytest.mark.parametrize('change',[
    lambda r:setattr(r,'url',httpx.URL('http://api.openai.com/v1/responses/input_tokens')),
    lambda r:setattr(r,'url',httpx.URL('https://api.openai.com.evil/v1/responses/input_tokens')),
    lambda r:setattr(r,'url',httpx.URL('https://x@api.openai.com/v1/responses/input_tokens')),
    lambda r:setattr(r,'url',httpx.URL('https://api.openai.com:444/v1/responses/input_tokens')),
    lambda r:setattr(r,'url',httpx.URL('https://api.openai.com/v1/responses/input_tokens?q=1')),
    lambda r:setattr(r,'url',httpx.URL('https://api.openai.com/v1/%72esponses/input_tokens')),
    lambda r:setattr(r,'method','GET'),lambda r:r.headers.update({'Cookie':PRIVATE}),
    lambda r:r.headers.update({'Proxy-Authorization':PRIVATE}),lambda r:r.headers.update({'X-Other':PRIVATE}),
    lambda r:r.headers.update({'User-Agent':PRIVATE}),lambda r:r.headers.update({'X-Stainless-Arch':PRIVATE}),
    lambda r:r.headers.update({'X-Stainless-Retry-Count':'1'}),
    lambda r:r.headers.update({'Accept-Encoding':'gzip'}),lambda r:r.extensions.update(timeout=dict.fromkeys(('connect','read','write','pool'),99)),
    lambda r:setattr(r,'_content',b'{"model":"other","input":"private"}'),
])
def test_official_outgoing_url_header_query_body_and_timeout_drift_has_inner0(change):
    h=official_adapter(request_change=change)
    with pytest.raises(h.a['LlmCallError']) as error:h.client.complete('synthetic')
    assert not h.sent and not h.budget.snapshot()[0].count_entered and PRIVATE not in str(error.value);h.client.close()


@pytest.mark.parametrize('field', ['SDK','HTTP','transport','mount','hooks','retry','count_method','generation_method','base'])
def test_official_captured_identity_drift_has_no_forward(field):
    h=official_adapter();b=h.budget._official_bundle
    if field=='SDK':h.client._client=SimpleNamespace(max_retries=0,responses=h.sdk.responses)
    elif field=='HTTP':h.sdk._client=object()
    elif field=='transport':b.client._transport=object()
    elif field=='mount':b.client._mounts['anything']=object()
    elif field=='hooks':b.client._event_hooks['request'].append(object())
    elif field=='retry':h.sdk.max_retries=1
    elif field=='count_method':b.streaming.count=lambda **v:None
    elif field=='generation_method':b.responses.create=lambda **v:None
    else:h.sdk.base_url='https://other/'
    with pytest.raises(h.a['LlmCallError']):h.client.complete('synthetic')
    assert not h.sent
    # Restore owned cleanup target instead of invoking injected fake objects.
    h.sdk._client=b.client;b.client._transport=b.transport;h.client.close()


@pytest.mark.parametrize('where',['custom_headers','debug'])
def test_official_presence_and_current_effective_DEBUG_close_before_send(where):
    h=official_adapter()
    if where=='custom_headers':h.a['os'].environ['OPENAI_CUSTOM_HEADERS']=PRIVATE
    else:h.a['logging'].getLogger=lambda _:SimpleNamespace(isEnabledFor=lambda _:True)
    with pytest.raises(h.a['LlmCallError']):h.client.complete('synthetic')
    assert not h.sent;h.client.close()


def test_explicit_instance_ignores_unrelated_SDK_environment_and_module_client_settings():
    h=official_adapter();h.a['os'].environ.update(OPENAI_API_KEY=PRIVATE,OPENAI_BASE_URL=PRIVATE,OPENAI_ORG_ID=PRIVATE,OPENAI_PROJECT_ID=PRIVATE,OPENAI_LOG='info')
    h.a['openai'].api_key=PRIVATE;h.a['openai'].base_url=PRIVATE;h.a['openai'].api_type='azure'
    assert h.client.complete('synthetic')=='official result';h.client.close()


@pytest.mark.parametrize('stage',['transport','client','sdk'])
def test_owned_partial_constructor_failure_only_closes_own_resources(stage):
    h=official_adapter(constructor_failure=stage)
    with pytest.raises(h.a['LlmCallError']) as error:h.factory()
    assert not h.sent and PRIVATE not in str(error.value)
    if stage=='client':assert h.closed==['transport']
    if stage=='sdk':assert h.closed==['client','transport']
    with pytest.raises(h.a['LlmCallError']):h.factory()
    assert h.budget.closed_reason


@pytest.mark.parametrize('cap',[None,True,0,-1,2*1024*1024+1])
def test_official_wire_caps_are_explicit_and_bounded(cap):
    h=strict_adapter(counter=False)
    with pytest.raises(h.a['LlmCallError']):h.a['official_count_openai_client'](request_budget=h.budget,api_key=PRIVATE,
        request_wire_cap=cap,count_wire_cap=100,generation_wire_cap=100,count_version='synthetic.v1',count_provenance_sha256='a'*64,timeout=1)
    assert not h.budget.snapshot() and h.budget._official_bundle is None


def test_failed_count_consumes_last_pair_before_count_IO_and_never_refunds():
    h=strict_adapter(calls=1);paused=threading.Event();release=threading.Event();original=h.counter.count
    def count(**values):paused.set();assert release.wait(2);return original(**values)
    h.counter.count=count;errors=[]
    def first():
        try:h.client.complete('first')
        except h.a['LlmCallError']:errors.append(True)
    thread=threading.Thread(target=first);thread.start()
    try:
        assert paused.wait(2)
        record,=h.budget.snapshot();assert record.count_entered and record.held_nano==2000
        with pytest.raises(h.a['LlmCallError']):h.client.complete('second')
    finally:release.set();thread.join(2)
    assert not thread.is_alive() and len(h.counter.calls)==1 and not h.dispatched and errors
    assert len(h.budget.snapshot())==1 and h.budget.snapshot()[0].held_nano==2000


def test_count_receipt_same_prompt_from_previous_ordinal_cannot_be_replayed():
    h=strict_adapter();assert h.client.complete('same')=='synthetic result'
    evidence=h.counter.issued[0][0]
    h.counter.count=lambda **v:evidence
    with pytest.raises(h.a['LlmCallError']):h.client.complete('same')
    assert len(h.dispatched)==1 and len(h.budget.snapshot())==2 and not h.budget.snapshot()[1].count_validated


def test_transport_recomputes_timeout_after_SDK_request_construction():
    clock=[]
    def delay(request):
        if request.url.path.endswith('input_tokens'):h.clock.value=45
    h=official_adapter(request_change=delay)
    assert h.client.complete('synthetic')=='official result'
    assert all(0<v<=15 for r in h.sent for v in r.extensions['timeout'].values())
    assert h.budget.snapshot()[0].count_validated;h.client.close()


def test_late_count_stream_closes_without_generation_or_refund():
    def response(request,parts):
        class Late(parts):
            def __iter__(self):
                yield b'{"object":"response.input_tokens",'
                h.clock.value=61
                yield b'"input_tokens":12}'
        return httpx.Response(200,stream=Late([]))
    h=official_adapter(inner=response)
    with pytest.raises(h.a['LlmCallError'],match='DEADLINE_EXCEEDED'):h.client.complete('synthetic')
    v,=h.budget.snapshot();assert v.count_entered and v.count_response_received and not v.count_validated and not v.entered and v.held_nano==2000
    assert len(h.sent)==1 and 'response' in h.closed;h.client.close()


@pytest.mark.parametrize('phase',['count','generation'])
def test_split_no_length_stream_is_bounded_under_eager_SDK_read(phase):
    def response(request,parts):
        is_count=request.url.path.endswith('input_tokens')
        if is_count and phase=='generation':return httpx.Response(200,stream=parts([b'{"object":"response.input_tokens","input_tokens":12}']))
        return httpx.Response(200,stream=parts([b'x'*600,b'y'*600]))
    h=official_adapter(inner=response,generation_wire_cap=1024)
    with pytest.raises(h.a['LlmCallError'],match='RESPONSE_LIMIT'):h.client.complete('synthetic')
    v,=h.budget.snapshot();assert v.entered is (phase=='generation') and not v.text_accepted and v.held_nano==2000
    assert len(h.sent)==(2 if phase=='generation' else 1) and 'response' in h.closed;h.client.close()


def test_actual_owned_count_race_consumes_only_one_last_pair_and_IO_holds_no_lock():
    paused=threading.Event();release=threading.Event()
    def response(request,parts):
        assert h.budget._lock.acquire(blocking=False);h.budget._lock.release()
        if request.url.path.endswith('input_tokens'):
            paused.set();assert release.wait(2)
            return httpx.Response(200,stream=parts([b'{"object":"response.input_tokens","input_tokens":12}']))
        raise AssertionError('closed generation must not dispatch')
    h=official_adapter(calls=1,inner=response);errors=[]
    def first():
        try:h.client.complete('first')
        except h.a['LlmCallError']:errors.append(True)
    thread=threading.Thread(target=first);thread.start()
    try:
        assert paused.wait(2)
        with pytest.raises(h.a['LlmCallError']):h.client.complete('second')
    finally:release.set();thread.join(2)
    assert not thread.is_alive() and len(h.sent)==1 and errors
    v,=h.budget.snapshot();assert v.held_nano==2000 and v.count_validated and not v.entered;h.client.close()


def test_bundle_close_defers_owned_disposal_until_physical_count_finishes():
    paused=threading.Event();release=threading.Event()
    def response(request,parts):
        paused.set();assert release.wait(2)
        assert 'sdk' not in h.closed
        return httpx.Response(200,stream=parts([b'{"object":"response.input_tokens","input_tokens":12}']))
    h=official_adapter(inner=response);errors=[]
    def run():
        try:h.client.complete('synthetic')
        except h.a['LlmCallError']:errors.append(True)
    thread=threading.Thread(target=run);thread.start()
    try:
        assert paused.wait(2);h.client.close();assert 'sdk' not in h.closed
    finally:release.set();thread.join(2)
    assert not thread.is_alive() and errors and len(h.sent)==1
    assert h.closed.count('client')==1 and h.closed.count('transport')==1


def test_owned_generation_usage_is_preserved_when_text_rejected():
    def response(request,parts):
        if request.url.path.endswith('input_tokens'):raw=b'{"object":"response.input_tokens","input_tokens":12}'
        else:raw=b'{"status":"completed","output_text":"","usage":{"input_tokens":12,"output_tokens":3,"total_tokens":15}}'
        return httpx.Response(200,stream=parts([raw]))
    h=official_adapter(inner=response)
    with pytest.raises(h.a['LlmCallError'],match='TEXT_INVALID'):h.client.complete('synthetic')
    v,=h.budget.snapshot();assert v.count_validated and v.entered and v.response_received and v.usage==(12,3,15) and v.estimated_nano==180 and not v.text_accepted
    h.client.close()


@pytest.mark.parametrize('phase',['count','generation'])
def test_bundle_close_before_real_transport_entry_forbids_new_phase(phase):
    def close_before_send(request):
        is_count=request.url.path.endswith('input_tokens')
        if is_count==(phase=='count'):h.client.close()
    h=official_adapter(request_change=close_before_send)
    with pytest.raises(h.a['LlmCallError'],match='CLOSED'):h.client.complete('synthetic')
    record,=h.budget.snapshot()
    assert record.count_entered is (phase=='generation') and not record.entered and record.held_nano==2000
    assert len(h.sent)==(1 if phase=='generation' else 0) and h.closed.count('transport')==1


def test_partial_creation_cleanup_exception_remains_fixed_and_foreign_client_not_closed():
    h=official_adapter(constructor_failure='client')
    transport=h.a['httpx'].HTTPTransport
    class BadClose(transport):
        def close(self):h.closed.append('bad-close');raise RuntimeError(PRIVATE)
    h.a['httpx'].HTTPTransport=BadClose
    with pytest.raises(h.a['LlmCallError']) as error:h.factory()
    assert str(error.value)=='TECHNICAL_LLM_SDK_POLICY_INVALID' and PRIVATE not in str(error.value)
    assert h.closed==['bad-close']
    other=official_adapter();foreign=[];other.sdk._client=SimpleNamespace(close=lambda:foreign.append(True))
    other.client.close()
    assert not foreign and other.closed.count('client')==1 and other.closed.count('transport')==1


@pytest.mark.parametrize('failure',[RuntimeError(PRIVATE),asyncio.CancelledError(PRIVATE),KeyboardInterrupt(PRIVATE)])
def test_count_failure_preserves_consumed_pair_and_safe_exception(failure):
    h=strict_adapter()
    def fail(**values):raise failure
    h.counter.count=fail
    expected=asyncio.CancelledError if isinstance(failure,asyncio.CancelledError) else KeyboardInterrupt if isinstance(failure,KeyboardInterrupt) else h.a['LlmCallError']
    with pytest.raises(expected) as error:h.client.complete('synthetic')
    v,=h.budget.snapshot();assert v.count_entered and not v.count_validated and not v.entered and v.held_nano==2000 and v.reason=='COUNT_FAILED'
    assert not h.dispatched and PRIVATE not in str(error.value)


@pytest.mark.parametrize('failure',[RuntimeError(PRIVATE),asyncio.CancelledError(PRIVATE)])
def test_deferred_cleanup_failure_does_not_mask_original_error_or_cancellation(failure):
    def response(request,parts):
        h.client.close()
        h.budget._official_bundle.client.close=lambda:(_ for _ in ()).throw(RuntimeError(PRIVATE))
        raise failure
    h=official_adapter(inner=response)
    expected=asyncio.CancelledError if isinstance(failure,asyncio.CancelledError) else h.a['LlmCallError']
    with pytest.raises(expected) as error:h.client.complete('synthetic')
    assert PRIVATE not in str(error.value) and error.value.__suppress_context__
    v,=h.budget.snapshot();assert v.count_entered and not v.entered and v.held_nano==2000
    assert h.closed.count('transport')==1


def test_factory_cancel_preserves_cancel_when_owned_cleanup_also_fails():
    h=official_adapter(constructor_failure='client');transport=h.a['httpx'].HTTPTransport
    class BadClose(transport):
        def close(self):raise RuntimeError(PRIVATE)
    def fail(**values):raise asyncio.CancelledError(PRIVATE)
    h.a['httpx'].HTTPTransport=BadClose;h.a['httpx'].Client=fail
    with pytest.raises(asyncio.CancelledError) as error:h.factory()
    assert PRIVATE not in str(error.value) and error.value.__suppress_context__ and not h.sent


def test_stream_cancel_survives_response_close_failure():
    def response(request,parts):
        class Cancelled(parts):
            def __iter__(self):raise asyncio.CancelledError(PRIVATE);yield b''
            def close(self):h.closed.append('response');raise RuntimeError(PRIVATE)
        return httpx.Response(200,stream=Cancelled([]))
    h=official_adapter(inner=response)
    with pytest.raises(asyncio.CancelledError) as error:h.client.complete('synthetic')
    assert PRIVATE not in str(error.value) and error.value.__suppress_context__
    v,=h.budget.snapshot();assert v.count_entered and not v.entered and v.held_nano==2000
    h.client.close()


def test_official_opaque_receipt_keeps_hash_binding_without_retaining_prompt():
    h=official_adapter();assert h.client.complete(PRIVATE)=='official result'
    receipts=h.budget._official_bundle.counter._receipts
    assert PRIVATE not in repr(receipts) and all('input' not in binding for _,binding in receipts.values())
    assert all(PRIVATE not in str(getattr(r,f.name)) for r in h.budget.snapshot() for f in fields(r))
    h.client.close()

async def test_CF053_callback_late_fixed_ACK_is_not_adopted_after_clock_advance():
    from src.modules.technical.domain import provider_execution as P
    path=ROOT/'ai/src/agents/technical/infrastructure/execution_authority_client.py'
    nodes=authority_nodes(path)
    clock=SimpleNamespace(value=0.0)
    values={'P':P,'asyncio':asyncio,'httpx':httpx,'math':math,'time':SimpleNamespace(monotonic=lambda:clock.value)}
    values.update(ssl=ssl,hashlib=hashlib)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),values)
    from fastapi import FastAPI
    from starlette.responses import JSONResponse
    app=FastAPI();seen=[]
    @app.post('/internal/technical/execution/start')
    async def start():
        seen.append(True);clock.value=6
        return JSONResponse({'schema_version':P.SCHEMA})
    client=values['ExecutionAuthorityClient'](origin='https://backend.invalid',token='b'*32,transport=httpx.ASGITransport(app=app))
    with pytest.raises(P.ExecutionInvalid):await client._post('/internal/technical/execution/start',{'schema_version':P.SCHEMA},'f'*64,5,8192)
    assert seen==[True]

async def test_CF053_authority_snapshot_survives_await_mutation_without_credential_redirect():
    from src.modules.technical.domain import provider_execution as P
    path=ROOT/'ai/src/agents/technical/infrastructure/execution_authority_client.py'
    nodes=authority_nodes(path)
    values={'P':P,'asyncio':asyncio,'httpx':httpx,'math':math,'time':__import__('time')}
    values.update(ssl=ssl,hashlib=hashlib)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),values)
    from fastapi import FastAPI,Request
    from starlette.responses import JSONResponse
    app=FastAPI();seen=[]
    @app.post('/internal/technical/execution/start')
    async def start(request:Request):
        seen.append((request.url.hostname,request.headers['x-technical-authority-token']))
        return JSONResponse({'bounded':True})
    client=values['ExecutionAuthorityClient'](origin='https://backend.invalid',token='b'*32,transport=httpx.ASGITransport(app=app))
    class AwaitMutation:
        def __init__(self,**kwargs):self.inner=httpx.AsyncClient(**kwargs)
        async def __aenter__(self):
            await self.inner.__aenter__();client.origin='https://other.invalid';client.token=b'c'*32;client.transport=None;return self.inner
        async def __aexit__(self,*args):return await self.inner.__aexit__(*args)
    values['httpx']=SimpleNamespace(AsyncClient=AwaitMutation,ASGITransport=httpx.ASGITransport)
    assert await client._post('/internal/technical/execution/start',{'schema_version':P.SCHEMA},'f'*64,5,8192)=={'bounded':True}
    assert seen==[('backend.invalid','b'*32)]
    with pytest.raises(P.ExecutionInvalid):await client._post('/internal/technical/execution/start',{'schema_version':P.SCHEMA},'f'*64,5,8192)
    assert len(seen)==1

def test_CF053_actual_CF051_overflow_failure_keeps_usage_and_null_estimate():
    from src.modules.technical.domain import provider_execution as P
    h=strict_adapter();huge=P.MAX//10+1
    h.sdk.responses.create=lambda **kwargs:SimpleNamespace(status='completed',model='synthetic-model',service_tier='default',output_text='synthetic',usage=SimpleNamespace(input_tokens=huge,output_tokens=0,total_tokens=huge))
    with pytest.raises(h.a['LlmCallError'],match='USAGE_LIMIT_MISMATCH'):h.client.complete('synthetic')
    record,=h.budget.snapshot()
    assert record.usage==(huge,0,huge) and record.estimated_nano is None and not record.text_accepted
    p=json.loads(h.budget._policy_json)
    cfg=P.Configuration.parse({'schema_version':P.SCHEMA,'policy':p,'counter':{'free':True,'mapping':'technical.responses.model-input.v1','version':'synthetic.v1','provenance_sha256':'c'*64,'evidence_sha256':'d'*64},'caps':{'request':4096,'count':4096,'generation':4096},'ai_origin':'https://ai.invalid','authority_origin':'https://backend.invalid','cache_mode':'none','trace_mode':'none'})
    start=P.start_receipt('e'*64,str(uuid4()),h.started.isoformat())
    row={f.name:(str(getattr(record,f.name)) if isinstance(getattr(record,f.name),UUID) else list(getattr(record,f.name)) if type(getattr(record,f.name)) is tuple else getattr(record,f.name)) for f in fields(record)}
    control={'analysis_id':row['analysis_id'],'attempt_id':row['attempt_id'],'policy_sha256':row['policy_sha256'],'reserved_nano':h.budget._reserved}
    value={'schema_version':'technical.usage.v1','analysis_id':row['analysis_id'],'attempt_id':row['attempt_id'],'policy_sha256':row['policy_sha256'],'control_sha256':start['control_sha256'],'start_sha256':start['start_sha256'],'executor_id':start['executor_id'],'outcome':'failed','records':[row]}
    assert P.evidence(value,cfg,control,start)==value

async def test_CF053_authority_cleanup_delay_cannot_return_late_ACK():
    from src.modules.technical.domain import provider_execution as P
    path=ROOT/'ai/src/agents/technical/infrastructure/execution_authority_client.py'
    nodes=authority_nodes(path)
    clock=SimpleNamespace(value=0.0);app=__import__('fastapi').FastAPI()
    from starlette.responses import JSONResponse
    @app.post('/internal/technical/execution/start')
    async def callback():return JSONResponse({'bounded':True})
    class DelayedClose:
        def __init__(self,**kwargs):self.inner=httpx.AsyncClient(**kwargs)
        async def __aenter__(self):return await self.inner.__aenter__()
        async def __aexit__(self,*args):
            result=await self.inner.__aexit__(*args);clock.value=6;return result
    values={'P':P,'asyncio':asyncio,'httpx':SimpleNamespace(AsyncClient=DelayedClose,ASGITransport=httpx.ASGITransport,AsyncBaseTransport=httpx.AsyncBaseTransport),'math':math,'time':SimpleNamespace(monotonic=lambda:clock.value)}
    values.update(ssl=ssl,hashlib=hashlib)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),values)
    client=values['ExecutionAuthorityClient'](origin='https://backend.invalid',token='b'*32,transport=httpx.ASGITransport(app=app))
    with pytest.raises(P.ExecutionInvalid):await client._post('/internal/technical/execution/start',{'schema_version':P.SCHEMA},'f'*64,5,8192)


def explicit_kis_slices():
    """Closed copied adapter functions, actual pure OHLCV, MockTransport only."""
    import __future__
    import _strptime
    import time
    from datetime import date
    from urllib.parse import urlsplit
    tree=ast.parse((ROOT/KIS_PATH).read_text())
    names={'kis_request_gate','_explicit_settings','get_access_token','validate_ticker','validate_period',
        '_to_iso_date','_to_price','_to_int','parse_kis_ohlcv_item','parse_kis_ohlcv_output',
        '_normalize_to_date','_ymd','normalize_end_date','_sleep_backoff','_call_chart',
        '_extract_output2','_fetch_ohlcv_range','fetch_ohlcv_range','fetch_ohlcv','fetch_multi_timeframe_ohlcv'}
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
    assert {n.name for n in nodes}==names
    calls=names|{'type','any','ord','ValueError','TypeError','AttributeError','isinstance','float','int','str',
        'KisApiError','KisFieldError','KisRangeIncompleteError','OutOfScopeTickerError','InvalidPeriodError',
        'KISSettings','urlsplit','len','max','min','range','list','dict','set','timedelta','OHLCV','sorted','load_kis_settings',
        'is_supported_ticker'}
    attrs={'api_key','api_secret','base_url','scheme','hostname','username','password','path','query','fragment','port',
        'rstrip','strip','match','time','Client','post','get','close','status_code','text','json','info','warning',
        'replace','strftime','fromisoformat','strptime','date','now','today','tzinfo','isoformat','sleep','RequestError',
        'fullmatch','isdigit','lstrip','isfinite','sort','values','isascii','URL','Lock','remaining_seconds','is_set',
        'url','host','userinfo','method','params','multi_items','extensions'}
    for n in ast.walk(ast.Module(body=nodes,type_ignores=[])):
        assert not isinstance(n,(ast.Import,ast.ImportFrom,ast.Global,ast.Nonlocal,ast.ClassDef,ast.AsyncWith,
                                 ast.Await,ast.Yield,ast.YieldFrom,ast.Delete))
        if isinstance(n,ast.With):
            assert len(n.items)==1 and ast.dump(n.items[0].context_expr)==ast.dump(ast.Name(id='lock',ctx=ast.Load()))
            assert n.items[0].optional_vars is None
        if isinstance(n,ast.Call):
            if isinstance(n.func,ast.Name): assert n.func.id in calls,n.func.id
            else: assert isinstance(n.func,ast.Attribute) and n.func.attr in attrs,n.func.attr
        if isinstance(n,ast.Attribute):
            if n.attr=='__name__':
                assert ast.dump(n.value) in {ast.dump(ast.parse(x,mode='eval').body)
                                             for x in ('type(value)','type(output2)')}
            else:assert n.attr in attrs,n.attr
        if isinstance(n,ast.Name):assert not n.id.startswith('__')
    config=COLLECTION_CONFIG
    env={'__builtins__':{k:getattr(builtins,k) for k in ('type','any','ord','ValueError','TypeError','AttributeError',
         'isinstance','float','int','str','len','max','min','range','list','dict','set','sorted','OverflowError')},
         'KISSettings':config.KISSettings,'date':date,'datetime':datetime,'timedelta':timedelta,'urlsplit':urlsplit,
         'math':math,'httpx':httpx,'threading':threading,'time':SimpleNamespace(time=lambda:1000,sleep=lambda _:None),
         'logger':SimpleNamespace(info=lambda *a,**k:None,warning=lambda *a,**k:None),
         'is_supported_ticker':config.is_supported_ticker}
    def datetime_import(name,*args,**kwargs):
        # datetime's C strptime/strftime uses this exact stdlib lookup, even
        # when already loaded. Never forward arbitrary generated imports.
        assert name in {'_strptime','time'}
        return {'_strptime':_strptime,'time':time}[name]
    env['__builtins__']['__import__']=datetime_import
    for name in ('KisApiError','KisFieldError','KisRangeIncompleteError','OutOfScopeTickerError','InvalidPeriodError'):
        env[name]=ValueError
    for name in ('KIS_BACKOFF_SECONDS','KIS_FETCH_CHUNK_DAYS','KIS_FETCH_LOOKBACK_DAYS','KIS_MAX_CHUNKS',
                 'KIS_MAX_RETRIES','KIS_TIMEOUT_SECONDS','KIS_PERIOD_WEEKLY'):
        env[name]=getattr(config,name)
    constants={'TOKEN_PATH','CHART_PATH','TR_ID','MARKET_DIV_CODE','ORG_ADJ_PRC','CUST_TYPE','RATE_LIMIT_MSG_CODE',
        'KIS_FIELD_DATE','KIS_FIELD_OPEN','KIS_FIELD_HIGH','KIS_FIELD_LOW','KIS_FIELD_CLOSE','KIS_FIELD_VOLUME',
        'KIS_FIELD_TRADING_VALUE','_TOKEN_EXPIRY_MARGIN_SECONDS'}
    for node in tree.body:
        if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name) and node.targets[0].id in constants:
            env[node.targets[0].id]=ast.literal_eval(node.value)
    env.update(ALLOWED_PERIODS=('D','W','M'),_YMD_RE=re.compile(r'^\d{8}$'),_ISO_DATE_RE=re.compile(r'^\d{4}-\d{2}-\d{2}$'))
    env['REQUIRED_KIS_FIELDS']=tuple(env[k] for k in ('KIS_FIELD_DATE','KIS_FIELD_OPEN','KIS_FIELD_HIGH','KIS_FIELD_LOW',
        'KIS_FIELD_CLOSE','KIS_FIELD_VOLUME','KIS_FIELD_TRADING_VALUE'))
    env['OHLCV']=pure_module('ai/src/agents/technical/domain/models/ohlcv.py','kis_actual_ohlcv').OHLCV
    state={'access_token':'old-cached-synthetic-token','expires_at':1000000}
    env['_token_state']=state
    loads=[]
    def forbidden():loads.append(True);raise AssertionError('KIS env discovery prohibited')
    env['load_kis_settings']=forbidden
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'<fixed-explicit-kis-slices>','exec',
                 flags=__future__.annotations.compiler_flag,dont_inherit=True),env)
    return env,state,loads


@pytest.mark.parametrize('failures',[0,2])
def test_explicit_kis_standard_fetcher_preserves_DWM_bounds_and_never_loads_env_or_cache(failures):
    env,state,loads=explicit_kis_slices();before=dict(state);calls=[];attempts={}
    settings=COLLECTION_CONFIG.KISSettings('synthetic-key','synthetic-secret','https://kis.example.invalid:9443')
    def respond(req):
        calls.append(req)
        assert req.url.host=='kis.example.invalid' and req.url.scheme=='https'
        if req.method=='POST':
            assert req.url.path==env['TOKEN_PATH']
            assert json.loads(req.content)==dict(grant_type='client_credentials',appkey=settings.api_key,appsecret=settings.api_secret)
            return httpx.Response(200,json={'access_token':'new-synthetic-token','expires_in':86400})
        assert req.method=='GET' and req.url.path==env['CHART_PATH']
        assert req.headers['authorization']=='Bearer new-synthetic-token'
        key=str(req.url)
        attempts[key]=attempts.get(key,0)+1
        if attempts[key]<=failures:return httpx.Response(429,json={})
        day=req.url.params['FID_INPUT_DATE_1']
        return httpx.Response(200,json={'rt_cd':'0','output2':[dict(stck_bsop_date=day,stck_oprc='10',stck_hgpr='12',
            stck_lwpr='9',stck_clpr='11',acml_vol='100',acml_tr_pbmn='1000')]})
    hook,observed=env['kis_request_gate'](settings=settings,ticker='000720',deadline=SimpleNamespace(remaining_seconds=lambda:10),
        stopped=threading.Event(),token_limit=3,market_limit=30)
    with httpx.Client(transport=httpx.MockTransport(respond),trust_env=False,follow_redirects=False,event_hooks={'request':[hook]}) as client:
        data=env['fetch_multi_timeframe_ohlcv']('000720',end_date='2026-11-12',client=client,settings=settings)
    assert set(data)=={'D','W','M'} and all(data.values())
    assert len([r for r in calls if r.method=='POST'])==1
    assert [len([r for r in calls if r.method=='GET' and r.url.params['FID_PERIOD_DIV_CODE']==p]) for p in ('D','W','M')]==[n*(failures+1) for n in (5,4,1)]
    assert observed()=={'token':1,'market':10*(failures+1)}
    assert not loads and state==before
    assert all(r.headers.get('appkey')==settings.api_key for r in calls if r.method=='GET')


@pytest.mark.parametrize('base',['http://kis.example.invalid','https://user:secret@kis.example.invalid',
    'https://kis.example.invalid/path','https://kis.example.invalid?x=y','https://kis.example.invalid#fragment',
    'https://kis.example.invalid:0','https://kis.example.invalid\n'])
def test_explicit_kis_invalid_origin_fails_before_token_or_client(base):
    env,state,loads=explicit_kis_slices();calls=[];before=dict(state)
    settings=COLLECTION_CONFIG.KISSettings('synthetic-key','synthetic-secret',base)
    with httpx.Client(transport=httpx.MockTransport(lambda r:calls.append(r))) as client:
        with pytest.raises(ValueError,match='^Invalid explicit KIS settings$'):
            env['fetch_multi_timeframe_ohlcv']('000720',end_date='2026-11-12',client=client,settings=settings)
    assert not calls and not loads and state==before


@pytest.mark.parametrize('field,value',[('api_key',''),('api_secret','secret\n'),('api_key',123),('base_url',None)])
def test_explicit_kis_invalid_fields_use_fixed_secret_free_error(field,value):
    env,state,loads=explicit_kis_slices();calls=[]
    settings=replace(COLLECTION_CONFIG.KISSettings('synthetic-key',PRIVATE,'https://kis.example.invalid'),**{field:value})
    with httpx.Client(transport=httpx.MockTransport(lambda r:calls.append(r))) as client:
        with pytest.raises(ValueError,match='^Invalid explicit KIS settings$') as error:
            env['get_access_token'](client=client,settings=settings)
    assert PRIVATE not in str(error.value) and not calls and not loads


def test_legacy_kis_cache_still_returns_before_config_or_http():
    env,state,loads=explicit_kis_slices();calls=[]
    with httpx.Client(transport=httpx.MockTransport(lambda r:calls.append(r))) as client:
        assert env['get_access_token'](client=client)=='old-cached-synthetic-token'
    assert not calls and not loads


def test_owned_kis_hook_denies_destination_paths_stock_and_count_without_send():
    env,_,_=explicit_kis_slices();calls=[]
    settings=COLLECTION_CONFIG.KISSettings('synthetic-key','synthetic-secret','https://kis.example.invalid:9443')
    hook,observed=env['kis_request_gate'](settings=settings,ticker='000720',deadline=SimpleNamespace(remaining_seconds=lambda:10),
        stopped=threading.Event(),token_limit=1,market_limit=1)
    with httpx.Client(transport=httpx.MockTransport(lambda r:(calls.append(r),httpx.Response(200,json={}))[1]),
                      trust_env=False,follow_redirects=False,event_hooks={'request':[hook]}) as client:
        for url in ('https://other.invalid:9443'+env['TOKEN_PATH'],'https://kis.example.invalid'+env['TOKEN_PATH'],
                    settings.base_url+'/uapi/domestic-stock/v1/trading/order-cash',
                    settings.base_url+'/uapi/domestic-stock/v1/trading/inquire-balance'):
            with pytest.raises(ValueError,match='^KIS request denied$'):client.post(url)
        assert not calls and observed()=={'token':0,'market':0}
        client.post(settings.base_url+env['TOKEN_PATH'])
        with pytest.raises(ValueError,match='^KIS invocation limit reached$'):client.post(settings.base_url+env['TOKEN_PATH'])
        params=dict(FID_COND_MRKT_DIV_CODE='J',FID_INPUT_ISCD='005930',FID_INPUT_DATE_1='20261101',
                    FID_INPUT_DATE_2='20261112',FID_PERIOD_DIV_CODE='D',FID_ORG_ADJ_PRC='0')
        with pytest.raises(ValueError,match='^KIS request denied$'):client.get(settings.base_url+env['CHART_PATH'],params=params)
        params['FID_INPUT_ISCD']='000720'
        client.get(settings.base_url+env['CHART_PATH'],params=params)
        with pytest.raises(ValueError,match='^KIS invocation limit reached$'):client.get(settings.base_url+env['CHART_PATH'],params=params)
    assert len(calls)==2 and observed()=={'token':1,'market':1}
    result=observed();result['token']=0
    assert observed()['token']==1


@pytest.mark.parametrize('kind',['expired','cancelled','nan'])
def test_owned_kis_hook_stops_before_next_send_and_preserves_consumption(kind):
    env,_,_=explicit_kis_slices();calls=[];remaining=[10];stopped=threading.Event()
    settings=COLLECTION_CONFIG.KISSettings('synthetic-key','synthetic-secret','https://kis.example.invalid:9443')
    hook,observed=env['kis_request_gate'](settings=settings,ticker='000720',deadline=SimpleNamespace(remaining_seconds=lambda:remaining[0]),
        stopped=stopped,token_limit=3,market_limit=30)
    with httpx.Client(transport=httpx.MockTransport(lambda r:(calls.append(r),httpx.Response(200,json={}))[1]),
                      trust_env=False,follow_redirects=False,event_hooks={'request':[hook]}) as client:
        request=client.build_request('POST',settings.base_url+env['TOKEN_PATH'])
        request.extensions['timeout']={'connect':None,'read':float('nan'),'write':.5,'pool':20}
        remaining[0]=1.25
        client.send(request)
        assert calls[0].extensions['timeout']==dict(connect=1.25,read=1.25,write=.5,pool=1.25)
        if kind=='cancelled':stopped.set()
        else:remaining[0]=0 if kind=='expired' else float('nan')
        with pytest.raises(ValueError,match='^KIS invocation closed$'):client.post(settings.base_url+env['TOKEN_PATH'])
    assert len(calls)==1 and observed()=={'token':1,'market':0}


def authority_nodes(path):
    tree=ast.parse(path.read_text())
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'_tls_snapshot','_owned_tls'}
           or isinstance(n,ast.ClassDef) and n.name=='ExecutionAuthorityClient']
    assert {n.name for n in nodes}=={'_tls_snapshot','_owned_tls','ExecutionAuthorityClient'}
    assert not any(isinstance(n,(ast.Import,ast.ImportFrom)) for root in nodes for n in ast.walk(root))
    return nodes


def test_explicit_runtime_snapshot_has_no_env_discovery_and_cannot_reconfigure():
    p=Probe({'INTRADAY_FETCH_ENABLED':'true','TECHNICAL_TRACE_ENABLED':'true'});config=p.import_actual()
    settings=config.RuntimeSettings(False,False,'synthetic-owned-trace-unused')
    with p.file_spies():
        assert config.initialize_runtime(settings=settings) is settings
        assert config.initialize_runtime(settings=settings) is settings
        assert config.initialize_runtime() is settings
        with pytest.raises(config.TechnicalRuntimeUnavailable):
            config.initialize_runtime(settings=config.RuntimeSettings(True,False,'other'))
    assert not p.loads and not p.events and not p.io
    assert config.INTRADAY_FETCH_ENABLED is False and config.TECHNICAL_TRACE_ENABLED is False


@pytest.mark.parametrize('kind',['bool','path','type','late'])
def test_explicit_runtime_snapshot_invalid_or_late_stays_closed_without_env(kind):
    p=Probe();config=p.import_actual();settings=config.RuntimeSettings(False,False,'unused')
    if kind=='bool':settings=config.RuntimeSettings(1,False,'unused')
    elif kind=='path':settings=config.RuntimeSettings(False,False,None)
    elif kind=='type':settings=SimpleNamespace(intraday_fetch_enabled=False,trace_enabled=False,trace_path='unused')
    with p.file_spies(),ExitStack() as stack:
        if kind=='late':stack.enter_context(patch.dict(sys.modules,{next(iter(config._runtime_readers)):ModuleType('late')}))
        with pytest.raises(config.TechnicalRuntimeUnavailable):config.initialize_runtime(settings=settings)
    assert not p.loads and not p.events and not p.io
    assert_defaults(config)


def synthetic_tls_context():
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes,serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    key=ec.generate_private_key(ec.SECP256R1())
    name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'owned synthetic CA')])
    now=datetime.now(UTC)
    cert=(x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=1)).not_valid_after(now+timedelta(hours=1))
        .add_extension(x509.BasicConstraints(ca=True,path_length=None),critical=True).sign(key,hashes.SHA256()))
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_verify_locations(cadata=cert.public_bytes(serialization.Encoding.PEM).decode('ascii'))
    return context


def authority_tls_values():
    from src.modules.technical.domain import provider_execution as P
    path=ROOT/'ai/src/agents/technical/infrastructure/execution_authority_client.py'
    env={'P':P,'asyncio':asyncio,'httpx':httpx,'math':math,'time':__import__('time'),'ssl':ssl,'hashlib':hashlib}
    exec(compile(ast.Module(body=authority_nodes(path),type_ignores=[]),str(path),'exec'),env)
    return env,P


def test_authority_TLS_owns_CA_copy_and_rejects_weakened_or_empty_trust():
    env,P=authority_tls_values();context=synthetic_tls_context()
    client=env['ExecutionAuthorityClient'](origin='https://backend.invalid',token='b'*32,tls_context=context)
    owned=client._configuration[-1]
    assert owned is not context and env['_tls_snapshot'](owned)==env['_tls_snapshot'](context)
    assert owned.verify_mode==ssl.CERT_REQUIRED and owned.check_hostname is True
    context.check_hostname=False;context.verify_mode=ssl.CERT_NONE
    assert owned.verify_mode==ssl.CERT_REQUIRED and owned.check_hostname is True
    with pytest.raises(P.ExecutionInvalid):env['ExecutionAuthorityClient'](origin='https://backend.invalid',token='b'*32,tls_context=context)
    with pytest.raises(P.ExecutionInvalid):env['ExecutionAuthorityClient'](origin='https://backend.invalid',token='b'*32,tls_context=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT))


async def test_authority_TLS_drift_fails_before_callback_HTTP():
    env,P=authority_tls_values();context=synthetic_tls_context();calls=[]
    from fastapi import FastAPI
    app=FastAPI()
    @app.post('/internal/technical/execution/start')
    async def callback():calls.append(True);return {}
    client=env['ExecutionAuthorityClient'](origin='https://backend.invalid',token='b'*32,
        tls_context=context,transport=httpx.ASGITransport(app=app))
    context.check_hostname=False
    with pytest.raises(P.ExecutionInvalid):await client._post('/internal/technical/execution/start',{},'f'*64,5,8192)
    assert not calls


@pytest.mark.parametrize('phase',['count','generation'])
def test_owned_transport_fixed_reason_survives_SDK_wrapper_without_raw_text(phase):
    def add_denied_header(request):
        if request.url.path.endswith('input_tokens')==(phase=='count'):
            request.headers['Cookie']=PRIVATE
    h=official_adapter(request_change=add_denied_header,wrap_transport_errors=True)
    with pytest.raises(h.a['LlmCallError']) as error:h.client.complete('synthetic')
    assert str(error.value)=='TECHNICAL_LLM_HTTP_INVALID' and PRIVATE not in str(error.value)
    row,=h.budget.snapshot()
    assert row.reason=='HTTP_INVALID' and row.held_nano==2000 and not row.entered
    assert row.count_validated is (phase=='generation') and len(h.sent)==(phase=='generation')
    with pytest.raises(h.a['LlmCallError']):h.client.complete('again')
    assert len(h.sent)==(phase=='generation');h.client.close()


def test_official_owned_cookie_jar_rejects_provider_cookie_and_injected_cookie():
    h=official_adapter();cookies=h.budget._official_bundle.client.cookies
    req=httpx.Request('POST','https://api.openai.com/v1/responses/input_tokens')
    response=httpx.Response(200,headers={'Set-Cookie':PRIVATE+'=synthetic; Secure; Path=/'},request=req)
    cookies.extract_cookies(response)
    assert not list(cookies.jar)
    generation=httpx.Request('POST','https://api.openai.com/v1/responses')
    cookies.set_cookie_header(generation)
    assert 'Cookie' not in generation.headers
    assert h.client.complete('synthetic')=='official result'
    cookies.set('injected',PRIVATE,domain='api.openai.com')
    with pytest.raises(h.a['LlmCallError'],match='SDK_POLICY_INVALID') as error:h.client.complete('again')
    assert PRIVATE not in str(error.value) and len(h.sent)==2;h.client.close()


@pytest.mark.parametrize('kind',['auth','market_http','market_api','market_network'])
def test_explicit_KIS_failures_are_fixed_and_do_not_reauthenticate_or_leak(kind):
    env,state,loads=explicit_kis_slices();before=dict(state);calls=[]
    settings=COLLECTION_CONFIG.KISSettings('synthetic-key','synthetic-secret','https://kis.example.invalid')
    def respond(request):
        calls.append(request.method)
        if request.method=='POST':
            if kind=='auth':return httpx.Response(403,text=PRIVATE)
            return httpx.Response(200,json={'access_token':'synthetic-token','expires_in':86400})
        if kind=='market_http':return httpx.Response(500,text=PRIVATE)
        if kind=='market_api':return httpx.Response(200,json={'rt_cd':'1','msg_cd':PRIVATE,'msg1':PRIVATE})
        raise httpx.ConnectError(PRIVATE,request=request)
    codes={'auth':'KIS_AUTH_HTTP_FAILED','market_http':'KIS_MARKET_HTTP_FAILED',
           'market_api':'KIS_MARKET_API_FAILED','market_network':'KIS_MARKET_RETRY_EXHAUSTED'}
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(env['KisApiError']) as error:
            env['fetch_multi_timeframe_ohlcv']('000720',end_date='2026-11-12',settings=settings,client=client)
    assert str(error.value)==codes[kind] and PRIVATE not in str(error.value)
    assert calls.count('POST')==1 and calls.count('GET')==({'auth':0,'market_http':1,'market_api':1,'market_network':3}[kind])
    assert not loads and state==before


def test_explicit_KIS_separate_invocations_do_not_share_token_or_global_cache():
    env,state,loads=explicit_kis_slices();before=dict(state);token_count=[];used=[]
    settings=COLLECTION_CONFIG.KISSettings('synthetic-key','synthetic-secret','https://kis.example.invalid')
    def respond(request):
        if request.method=='POST':
            token_count.append(True);return httpx.Response(200,json={'access_token':'synthetic-token-'+str(len(token_count)),'expires_in':86400})
        used.append(request.headers['authorization']);return httpx.Response(200,json={'rt_cd':'0','output2':[]})
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        for _ in range(2):env['fetch_multi_timeframe_ohlcv']('000720',end_date='2026-11-12',settings=settings,client=client)
    assert len(token_count)==2 and used==['Bearer synthetic-token-1']*3+['Bearer synthetic-token-2']*3
    assert not loads and state==before


@pytest.mark.parametrize('payload',[[],{'access_token':'synthetic-token','expires_in':True},
    {'access_token':'synthetic-token','expires_in':'private-not-a-number'},
    {'access_token':'synthetic-token','expires_in':0}])
def test_explicit_KIS_auth_response_invalid_is_fixed_no_followup(payload):
    env,state,loads=explicit_kis_slices();before=dict(state);calls=[]
    settings=COLLECTION_CONFIG.KISSettings('synthetic-key','synthetic-secret','https://kis.example.invalid')
    def respond(request):calls.append(request.method);return httpx.Response(200,json=payload)
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(env['KisApiError'],match='^KIS_AUTH_RESPONSE_INVALID$'):
            env['fetch_multi_timeframe_ohlcv']('000720',end_date='2026-11-12',settings=settings,client=client)
    assert calls==['POST'] and not loads and state==before
