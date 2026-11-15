"""Actual internal storage functions with mock transactions; PG is separate."""
import ast
import copy
from contextlib import nullcontext
from dataclasses import replace
from datetime import UTC, datetime, timedelta
import importlib.util
import importlib.machinery
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest


def load_flow_compat():
    """Only six pinned pure files; no CF021 loader, cache operation or fake origin."""
    from scripts.check_safe import CF035_COMPAT
    from types import ModuleType
    root = Path(__file__).resolve().parents[3]
    ai = root/'ai/src'
    for name in ('agents','agents.flow','agents.flow.api','agents.flow.domain',
                 'agents.flow.domain.verification','agents.flow.infrastructure'):
        if name not in sys.modules:
            module = ModuleType(name)
            module.__spec__ = importlib.machinery.ModuleSpec(name,None,is_package=True)
            module.__spec__.submodule_search_locations = [str(ai.joinpath(*name.split('.')))]
            module.__path__ = []
            sys.modules[name] = module
    for relative,expected in CF035_COMPAT.items():
        path = root/relative
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, 'Technical readonly source pin'
        name = relative.removeprefix('ai/src/').removesuffix('.py').replace('/','.')
        if name not in sys.modules:
            spec = importlib.util.spec_from_file_location(name,path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
        module = sys.modules[name]
        assert isinstance(module.__spec__.loader,importlib.machinery.SourceFileLoader)
        assert Path(module.__spec__.origin).resolve() == path.resolve(), 'Technical readonly source origin'
    from scripts.check_safe import CF035_INPUTS
    for relative,expected in CF035_INPUTS.items():
        assert hashlib.sha256((root/relative).read_bytes()).hexdigest() == expected, 'Technical readonly input pin'


load_flow_compat()
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from scripts.cf035_technical_owned_check import storage_fixture
from src.modules.analysis.domain.contracts import canonical_json, json_hash, FrozenAnalysisResult
from src.modules.technical.application import owned_report_service as service
from src.modules.technical.infrastructure import report_repository as repo
from db.models.technical.report_snapshot import TechnicalReportSnapshot, CHECKS, TEXT_LIMITS


class Session:
    def __init__(self):
        self.no_autoflush = nullcontext()
        self.rows = []
        self.flush = AsyncMock()
        self.commit = AsyncMock(); self.rollback = AsyncMock()
        self.scalar = AsyncMock(return_value=datetime.now(UTC))
    def add(self,row): self.rows.append(row)
    def add_all(self,rows): self.rows.extend(rows)


def principal(user=None):
    return service.Principal(user or uuid4(),uuid4(),datetime.now(UTC)+timedelta(hours=1),b'x'*32)


def setup(monkeypatch):
    p = principal(); binding,frozen = storage_fixture(p.user_id); session = Session()
    authorize = AsyncMock()
    monkeypatch.setattr(service,'validate_principal',authorize)
    monkeypatch.setattr(repo,'storage_root_for_update',AsyncMock(return_value=None))
    monkeypatch.setattr(repo,'technical_indexes',AsyncMock(return_value=[]))
    monkeypatch.setattr(repo,'get_stock',AsyncMock(return_value=object()))
    monkeypatch.setattr(repo,'get_owned_storage',AsyncMock(return_value=None))
    return p,binding,frozen,session,authorize


async def staged(monkeypatch):
    p,b,f,s,a = setup(monkeypatch)
    ref = await service.TechnicalOwnedReportService(s,principal=p).stage(b,f)
    from db.models.technical.technical_report import TechnicalReport
    from db.models.common.agent_report import AgentReport
    root = next(x for x in s.rows if isinstance(x,TechnicalReport))
    snapshot = next(x for x in s.rows if isinstance(x,TechnicalReportSnapshot))
    index = next(x for x in s.rows if isinstance(x,AgentReport))
    classes = [service.TechnicalReportSignal, service.TechnicalReportChart, service.TechnicalReportRiskNote,
               service.TechnicalReportInterpretation, service.TechnicalReportVerification]
    children = [[row for row in s.rows if isinstance(row,cls)] for cls in classes]
    monkeypatch.setattr(repo,'get_owned_storage',AsyncMock(return_value=(root,snapshot)))
    monkeypatch.setattr(repo,'technical_indexes',AsyncMock(return_value=[index]))
    monkeypatch.setattr(repo,'storage_children',AsyncMock(return_value=children))
    return p,b,f,s,a,root,snapshot,index,children,ref


async def test_actual_stage_flush_only_and_new_session_read_detaches_values(monkeypatch):
    p,b,f,s,a,root,snapshot,index,children,ref = await staged(monkeypatch)
    assert ref.report_id == f.report_id and ref.owner_user_id == p.user_id
    assert s.flush.await_count == 3
    s.commit.assert_not_awaited(); s.rollback.assert_not_awaited()
    assert a.call_args.kwargs == {'lock':True}
    assert snapshot.input_json == f.input_json and snapshot.result_json == f.result_json
    assert root.owner_user_id == snapshot.owner_user_id == index.owner_user_id == p.user_id
    result = await service.TechnicalOwnedReportService(s,principal=replace(p,session_id=uuid4())).read(f.report_id)
    assert result.frozen == f and result.coverage['cutoff_validation'] == 'unverified'
    result.preview['charts'].clear(); result.coverage.clear()
    assert len((await service.TechnicalOwnedReportService(s,principal=p).read(f.report_id)).preview['charts']) == 3
    assert snapshot.result_json == f.result_json


@pytest.mark.parametrize('failure',['auth','owner','stock','root','index'])
async def test_stage_negative_checks_before_first_write(monkeypatch,failure):
    p,b,f,s,a = setup(monkeypatch)
    error = service.TechnicalStorageInputError
    if failure == 'auth': a.side_effect = service.AuthenticationRequired(); error = service.AuthenticationRequired
    elif failure == 'owner': p = replace(p,user_id=uuid4()); error = service.AuthenticationRequired
    elif failure == 'stock': repo.get_stock.return_value = None
    elif failure == 'root': repo.storage_root_for_update.return_value = object(); error = service.TechnicalReportConflict
    else: repo.technical_indexes.return_value = [object()]; error = service.TechnicalReportConflict
    with pytest.raises(error): await service.TechnicalOwnedReportService(s,principal=p).stage(b,f)
    assert not s.rows
    s.flush.assert_not_awaited(); s.commit.assert_not_awaited(); s.rollback.assert_not_awaited()


@pytest.mark.parametrize('field',['analysis_id','admission_request_id','attempt_id','owner_user_id','operation','input_fingerprint','as_of','deadline_at'])
def test_frozen_self_consistent_context_replacement_is_not_authority(field):
    p = principal(); b,f = storage_fixture(p.user_id); old = getattr(f.context,field)
    new = old+timedelta(seconds=1) if isinstance(old,datetime) else uuid4() if hasattr(old,'hex') else '0'*64 if field == 'input_fingerprint' else 'other.v1'
    altered = FrozenAnalysisResult.freeze(context=replace(f.context,**{field:new}),report_id=f.report_id,
        input_schema=f.input_schema,result_schema=f.result_schema,input_json=f.input_json,result_json=f.result_json)
    with pytest.raises(service.TechnicalStorageInputError): service.checked(b,altered)


@pytest.mark.parametrize('attack',['wrapper_extra','wrapper_operation','wrapper_original','raw_hash','unsafe_binding','unsafe_frozen','report','schema'])
def test_closed_wrapper_hash_ids_and_unsafe_constructed_values(attack):
    b,f = storage_fixture(uuid4())
    if attack.startswith('wrapper'):
        value = json.loads(b.caller_input_json)
        if attack == 'wrapper_extra': value['metadata'] = 'untrusted'
        elif attack == 'wrapper_operation': value['operation'] = 'other.v1'
        else: value['boundary_request']['data']['original_query'] = 'secret sentinel changed'
        raw = canonical_json(value)
        b = replace(b,caller_input_json=raw,caller_context=replace(b.caller_context,input_fingerprint=json_hash(raw)))
    elif attack == 'raw_hash':
        f = copy.copy(f); object.__setattr__(f,'result_sha256','0'*64)
    elif attack == 'unsafe_binding':
        b = copy.copy(b); object.__setattr__(b,'caller_input_json','{bad secret sentinel')
    elif attack == 'unsafe_frozen':
        f = copy.copy(f); object.__setattr__(f,'context',object())
    else:
        f = FrozenAnalysisResult.freeze(context=f.context,report_id=uuid4() if attack == 'report' else f.report_id,
            input_schema='wrong.v1' if attack == 'schema' else f.input_schema,result_schema=f.result_schema,
            input_json=f.input_json,result_json=f.result_json)
    with pytest.raises(service.TechnicalStorageInputError,match='^Technical storage input is invalid$'):
        service.checked(b,f)


@pytest.mark.parametrize('field',['caller_context_json','boundary_context_json','caller_input_json','input_json','result_json'])
@pytest.mark.parametrize('kind',['malformed','noncanonical','too_large','duplicate'])
def test_text_boundaries_and_secret_free_fixed_errors(field,kind):
    b,f = storage_fixture(uuid4()); p = principal(b.caller_context.owner_user_id)
    snapshot = TechnicalReportSnapshot(**service.snapshot_values(b,f,datetime.now(UTC),p.session_id))
    value = {'malformed':'{secret sentinel','noncanonical':'{ "sentinel":1}',
             'duplicate':'{"secret":1,"secret":2}','too_large':'{"secret":"'+'x'*TEXT_LIMITS[field]+'"}'}[kind]
    setattr(snapshot,field,value)
    with pytest.raises(ValueError): service.restore_snapshot(snapshot)


@pytest.mark.parametrize('field',['caller_context_json','boundary_context_json'])
def test_context_identity_text_cannot_normalize_away_zulu_or_uuid_spelling(field):
    b,f = storage_fixture(uuid4()); snapshot = TechnicalReportSnapshot(**service.snapshot_values(b,f,datetime.now(UTC),uuid4()))
    setattr(snapshot,field,getattr(snapshot,field).replace('+00:00','Z'))
    with pytest.raises(service.TechnicalStorageInputError): service.restore_snapshot(snapshot)


@pytest.mark.parametrize('target',['root','index','index_session','chart','signal','interpretation','verification','snapshot_hash','snapshot_request','snapshot_owner'])
async def test_stored_projection_and_anchor_tamper_fails_closed(monkeypatch,target):
    p,b,f,s,a,root,snapshot,index,children,_ = await staged(monkeypatch)
    if target == 'root': root.original_query = 'secret sentinel'
    elif target == 'index': index.trace_id = str(uuid4())
    elif target == 'index_session': index.owner_session_id = uuid4()
    elif target == 'chart': children[1][0].display_order = 99
    elif target == 'signal': children[0][0].value = 99
    elif target == 'interpretation': children[3][0].interpretation = 'secret sentinel'
    elif target == 'verification': children[4][0].calc_passed = False
    elif target == 'snapshot_hash': snapshot.result_sha256 = '0'*64
    elif target == 'snapshot_request': snapshot.request_id = uuid4()
    else: snapshot.owner_user_id = uuid4()
    with pytest.raises(service.TechnicalStoredPayloadError,match='^Stored Technical result is inconsistent$'):
        await service.TechnicalOwnedReportService(s,principal=p).read(f.report_id)
    s.commit.assert_not_awaited(); s.rollback.assert_not_awaited()


async def test_absence_is_returned_without_snapshot_restore(monkeypatch):
    p,b,f,s,a = setup(monkeypatch)
    monkeypatch.setattr(repo,'get_owned_storage',AsyncMock(return_value=None))
    with patch.object(service,'restore_snapshot',side_effect=AssertionError('must not restore')):
        assert await service.TechnicalOwnedReportService(s,principal=p).read(f.report_id) is None


@pytest.mark.parametrize('fail_at',[1,2,3])
async def test_flush_error_propagates_without_internal_commit_or_rollback(monkeypatch,fail_at):
    p,b,f,s,a = setup(monkeypatch)
    s.flush.side_effect = [None]*(fail_at-1)+[IntegrityError('synthetic',{},Exception('private sentinel'))]
    with pytest.raises(IntegrityError): await service.TechnicalOwnedReportService(s,principal=p).stage(b,f)
    s.commit.assert_not_awaited(); s.rollback.assert_not_awaited()


def test_sql_filters_root_snapshot_and_all_indexes_before_read():
    text = str(repo.owned_statement(uuid4(),uuid4()).compile(dialect=postgresql.dialect()))
    assert 'technical_reports.owner_user_id =' in text and 'technical_report_snapshots.owner_user_id =' in text
    assert 'HAVING count(*) =' in text and 'FILTER (WHERE agent_reports.owner_user_id =' in text
    assert "GROUP BY agent_reports.agent_report_id" in text
    # No owner filtering of the total index set before GROUP/HAVING.
    subquery = text[text.index('SELECT agent_reports.agent_report_id'):]
    assert 'owner_user_id' not in subquery.split('GROUP BY')[0]


def test_projection_sort_empty_missing_and_precise_raw_text_are_distinct():
    def alter(response):
        raw = response['data']['result']
        raw['charts'] = list(reversed(raw['charts']))
        raw['charts'][0]['chart_data']['annotations'][0]['meta'] = {'negative_zero':-0.0,'big':9007199254740993,'zero':0,'null':None}
    b,f = storage_fixture(uuid4(),change=alter)
    _,_,preview = service.checked(b,f)
    assert [c['period'] for c in preview['charts']] == ['3m','1y','5y']
    assert json.loads(f.result_json)['data']['result']['charts'][0]['period'] == '5y'
    assert '9007199254740993' in f.result_json and '"negative_zero":-0.0' in f.result_json
    assert preview['charts'][1]['has_chart_data'] is False


def test_missing_chart_is_not_empty_and_raw_conditions_are_not_rewritten():
    from src.modules.technical.domain.execution_boundary import coverage_for
    def change(response):
        response['data']['result']['charts'] = [chart for chart in response['data']['result']['charts'] if chart['period'] != '1y']
        response['data']['coverage'] = coverage_for(response['data']['result'])
    b,f = storage_fixture(uuid4(),change=change)
    _,response,preview = service.checked(b,f)
    assert [row['period'] for row in preview['charts']] == ['3m','5y']
    assert response['data']['coverage']['periods'][1]['status'] == 'not_provided'
    assert '"conditions"' in f.input_json


async def test_session_lock_precedes_root_lock_and_stock_query(monkeypatch):
    p,b,f,s,a = setup(monkeypatch); events = []
    async def authorize(*args,**kwargs): events.append('session_lock')
    async def root(*args,**kwargs): events.append('root_lock'); return None
    async def stock(*args,**kwargs): events.append('stock_select'); return object()
    a.side_effect = authorize
    repo.storage_root_for_update.side_effect = root
    repo.get_stock.side_effect = stock
    await service.TechnicalOwnedReportService(s,principal=p).stage(b,f)
    assert events == ['session_lock','root_lock','stock_select']


def test_migration_matches_model_checks_and_preserves_old_revision():
    path = Path(__file__).resolve().parents[2]/'db/migrations/versions/20261111_c35001a7e0001_technical_owned_snapshot.py'
    spec = importlib.util.spec_from_file_location('_cf035_migration',path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    historical = CHECKS | {'schemas':"input_schema='analysis.agent.v1' AND result_schema='technical.boundary.v1'"}
    assert module.CHECKS == historical and module.LIMITS == TEXT_LIMITS
    new_path=path.with_name('20261112_c53001a7e0001_technical_provider_execution.py')
    new_spec=importlib.util.spec_from_file_location('_cf053_snapshot_migration',new_path)
    current=importlib.util.module_from_spec(new_spec);new_spec.loader.exec_module(current)
    assert current.SNAPSHOT_CHECK==CHECKS['schemas']
    assert current.down_revision=='c50001a7e0001'
    assert hashlib.sha256(path.read_bytes()).hexdigest()=='27adbb499e1daa46e3c59cc7688c5920c50d4688d51938ba05f014ea01792885'
    assert module.down_revision == 'c23001a7e0001'
    text = path.read_text()
    assert 'BEFORE UPDATE ON technical_report_snapshots' in text
    assert "owner_user_id IS NOT NULL" in text and 'legacy data preserved' in text
    assert 'UPDATE technical_reports' not in text


def test_no_provider_legacy_transaction_or_public_route_imports():
    tree = ast.parse(Path(service.__file__).read_text())
    imports = [node.module or '' for node in ast.walk(tree) if isinstance(node,ast.ImportFrom)]
    assert not any(x.endswith(('report_service','ai_client','config')) or '.api.' in x for x in imports)
    names = [node.func.attr for node in ast.walk(tree) if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)]
    assert not {'commit','rollback','begin','analyze_technical','ensure_stock'} & set(names)
    assert not any(name in sys.modules for name in ('src.shared.config','src.api.main','src.modules.technical.application.report_service'))


def test_readonly_pin_and_origin_mismatch_rejected(monkeypatch):
    from scripts.check_safe import CF035_COMPAT
    first = next(iter(CF035_COMPAT))
    monkeypatch.setitem(CF035_COMPAT,first,'0'*64)
    with pytest.raises(AssertionError,match='readonly source pin'): load_flow_compat()
    monkeypatch.undo()
    module = sys.modules['agents.flow.api.payload']
    with patch.object(module.__spec__,'origin','/unapproved/payload.py'):
        with pytest.raises(AssertionError,match='readonly source origin'): load_flow_compat()


async def test_identical_stage_replay_reads_verified_snapshot_without_any_write(monkeypatch):
    p,b,f,s,auth,root,snapshot,index,children,reference = await staged(monkeypatch)
    repo.storage_root_for_update.return_value=root
    before=(len(s.rows),snapshot.owner_session_id,index.owner_session_id,snapshot.result_json)
    s.flush.reset_mock();s.scalar.reset_mock();auth.reset_mock()
    current=replace(p,session_id=uuid4())
    replay=await service.TechnicalOwnedReportService(s,principal=current).stage(b,f)
    assert replay==reference
    assert (len(s.rows),snapshot.owner_session_id,index.owner_session_id,snapshot.result_json)==before
    s.flush.assert_not_awaited();s.scalar.assert_not_awaited();s.commit.assert_not_awaited()
    assert auth.await_count==2 and all(call.kwargs=={'lock':True} for call in auth.await_args_list)
    assert snapshot.owner_session_id==p.session_id!=current.session_id


@pytest.mark.parametrize('attack',['different_result','different_binding','other_owner','snapshot','duplicate_index','child'])
async def test_existing_stage_rejects_nonidentical_or_inconsistent_replay(monkeypatch,attack):
    p,b,f,s,auth,root,snapshot,index,children,reference=await staged(monkeypatch)
    repo.storage_root_for_update.return_value=root
    if attack=='different_result':
        value=json.loads(f.result_json)
        value['data']['boundary_observed_at']=(datetime.fromisoformat(value['data']['boundary_observed_at'])+timedelta(seconds=1)).isoformat()
        f=FrozenAnalysisResult.freeze(context=f.context,report_id=f.report_id,input_schema=f.input_schema,result_schema=f.result_schema,input_json=f.input_json,result_json=canonical_json(value))
    elif attack=='different_binding':b,f=storage_fixture(p.user_id,report_id=f.report_id,request_id=uuid4())
    elif attack=='other_owner':repo.get_owned_storage.return_value=None
    elif attack=='snapshot':snapshot.result_json='{}'
    elif attack=='duplicate_index':repo.technical_indexes.return_value=[index,index]
    else:children[-1][0].outcome='corrupted'
    s.flush.reset_mock();s.scalar.reset_mock();count=len(s.rows)
    with pytest.raises(service.TechnicalReportConflict):await service.TechnicalOwnedReportService(s,principal=p).stage(b,f)
    assert len(s.rows)==count
    s.flush.assert_not_awaited();s.scalar.assert_not_awaited();s.commit.assert_not_awaited()
