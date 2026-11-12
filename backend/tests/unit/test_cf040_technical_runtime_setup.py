"""Actual config and selected dependency AST bodies, with self-owned I/O spies only.

No legacy dependencies module, graph, provider, real environment or dotenv file is
imported/read. Every config case is a fresh independent module, never a repair of
an already imported pipeline or a reload of its copied settings.
"""
import ast
import builtins
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, contextmanager
from dataclasses import FrozenInstanceError
import hashlib
import importlib.machinery
import importlib.util
from itertools import count
from pathlib import Path
import sys
import threading
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = 'ai/src/agents/technical/config.py'
DEPENDENCIES_PATH = 'ai/src/api/dependencies.py'
LIMITS_PATH = 'ai/src/agents/technical/domain/intraday_limits.py'
DEADLINE_PATH = 'ai/src/shared/runtime/deadline.py'
LLM_PATH = 'ai/src/agents/technical/infrastructure/openai_llm_client.py'
PRIVATE = 'cf040-synthetic-private-sentinel-never-output'
FORBIDDEN = ('src.agents.technical.application.', 'agents.technical.application.',
             'src.agents.technical.infrastructure.', 'agents.technical.infrastructure.',
             'src.supervisor.', 'src.api.dependencies', 'openai', 'redis', 'langgraph')
SERIAL = count()


def load_readonly():
    """Preserve the existing six actual pure Flow source origins before collection."""
    from scripts.check_safe import CF040_COMPAT, CF040_INPUTS
    ai = ROOT/'ai/src'
    assert len(CF040_COMPAT) == 6 and set(CF040_INPUTS) == {CONFIG_PATH, DEPENDENCIES_PATH, LIMITS_PATH, DEADLINE_PATH, LLM_PATH}
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
    tree=ast.parse((ROOT/LLM_PATH).read_text())
    names={'_extract_usage','_extract_text','OpenAiLlmClient'}
    nodes=[node for node in tree.body if isinstance(node,(ast.FunctionDef,ast.ClassDef)) and node.name in names]
    assert {node.name for node in nodes}==names
    module=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),*nodes],type_ignores=[])
    class SDKError(Exception):pass
    class CallError(Exception):pass
    values={name:getattr(COLLECTION_CONFIG,name) for name in (
        'OPENAI_TEMPERATURE','OPENAI_MAX_OUTPUT_TOKENS','OPENAI_TIMEOUT_SECONDS','OPENAI_STORE')}
    values.update(time=SimpleNamespace(perf_counter=lambda:1.0),openai=SimpleNamespace(OpenAIError=SDKError),
                  logger=SimpleNamespace(warning=lambda *a,**kw:None),
                  DeadlineExceeded=DEADLINE.DeadlineExceeded,LlmCallError=CallError)
    exec(compile(ast.fix_missing_locations(module),str(ROOT/LLM_PATH),'exec'),values)
    return values


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
