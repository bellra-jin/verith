"""Fixed Technical admission unit collection. Real owned SQL is a separate check."""
import ast
import asyncio
import copy
from contextlib import contextmanager
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
import hashlib
import importlib.util
import importlib.machinery
import json
from pathlib import Path
import sys
from types import SimpleNamespace as NS, ModuleType
from unittest.mock import AsyncMock
from uuid import UUID, uuid4
import pytest


def _existing_flow_origin_sentinel():
    """Same six pure files as the existing Technical check, not an AI engine."""
    from scripts.check_safe import CF048_COMPAT
    root=Path(__file__).resolve().parents[3];ai=root/'ai/src'
    for name in ('agents','agents.flow','agents.flow.api','agents.flow.domain',
                 'agents.flow.domain.verification','agents.flow.infrastructure'):
        if name not in sys.modules:
            module=ModuleType(name)
            module.__spec__=importlib.machinery.ModuleSpec(name,None,is_package=True)
            module.__spec__.submodule_search_locations=[str(ai.joinpath(*name.split('.')))]
            module.__path__=[];sys.modules[name]=module
    for relative,expected in CF048_COMPAT.items():
        path=root/relative;assert hashlib.sha256(path.read_bytes()).hexdigest()==expected
        name=relative.removeprefix('ai/src/').removesuffix('.py').replace('/','.')
        if name not in sys.modules:
            spec=importlib.util.spec_from_file_location(name,path)
            module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
        module=sys.modules[name]
        assert isinstance(module.__spec__.loader,importlib.machinery.SourceFileLoader)
        assert Path(module.__spec__.origin).resolve()==path.resolve()


_existing_flow_origin_sentinel()
from src.modules.technical.domain import execution_admission as D
from src.modules.technical.application import execution_admission_service as S
from src.modules.technical.infrastructure import execution_admission_repository as R
from src.modules.auth.application.session_service import Principal

ROOT=Path(__file__).resolve().parents[3]
PRIVATE='cf048-synthetic-private-question-not-in-receipt'


def policy_values(**changes):
    # Explicit artificial accounting numbers, not operational prices or approval.
    return dict(operation=D.OPERATION,enabled=True,currency='USD',supported_tickers=['000720'],
        user_daily_limit=3,service_daily_limit=10,daily_budget_nano=100000,attempt_reserve_nano=10000,
        deadline_seconds=60,model='synthetic-model',service_tier='default',price_id='cf048.synthetic.v1',
        price_evidence_sha256='a'*64,input_nano_per_token=10,output_nano_per_token=20,
        input_token_cap=100,output_token_cap=50,input_byte_cap=1000,output_byte_cap=500,max_calls=4)|changes


def intent_values(**changes):
    return dict(operation=D.OPERATION,ticker='000720',original_query=PRIVATE,requested_views=['technical'],
        conditions=dict(profile='technical.multiframe.v1',periods=['3m','1y','5y']))|changes


def principal(owner=None):
    return Principal(owner or uuid4(),uuid4(),datetime.now(UTC)+timedelta(hours=1),b'x'*32)


@pytest.mark.parametrize('field',sorted(D.POLICY_INTEGERS))
@pytest.mark.parametrize('bad',[True,False,0,-1,1.0,'1',None,D.MAX_INT+1])
def test_policy_rejects_nonpositive_noninteger_or_overflow(field,bad):
    with pytest.raises(D.TechnicalAdmissionError,match='^POLICY_UNAVAILABLE$'):
        D.Policy.parse(policy_values(**{field:bad}))


@pytest.mark.parametrize('changes',[
    {'operation':'flow.analysis.v1'},{'enabled':1},{'currency':'KRW'},{'supported_tickers':[]},
    {'supported_tickers':['000720','000720']},{'supported_tickers':['000720',720]},
    {'supported_tickers':['ABC720']},{'model':''},{'model':PRIVATE+' '},
    {'service_tier':'priority'},{'price_id':None},{'price_evidence_sha256':'unverified'},
    {'attempt_reserve_nano':7999},{'attempt_reserve_nano':100001},
    {'input_token_cap':D.MAX_INT},{'max_calls':D.MAX_INT},{'deadline_seconds':86401},
    {'user_daily_limit':11},{'unknown':True},
])
def test_policy_binding_caps_and_exact_shape(changes):
    with pytest.raises(D.TechnicalAdmissionError):D.Policy.parse(policy_values(**changes))


@pytest.mark.parametrize('raw',[
    '{"enabled":true,"enabled":false}', '{"amount":NaN}', '{"amount":Infinity}',
    D.canonical(policy_values()).replace('"daily_budget_nano":100000','"daily_budget_nano":1e5'),
])
def test_raw_policy_duplicate_nonfinite_and_exponent_are_closed(raw):
    with pytest.raises(D.TechnicalAdmissionError):D.Policy.parse(raw)


@pytest.mark.parametrize('changes',[
    {'owner_user_id':str(uuid4())},{'as_of':'2026-11-12T00:00:00Z'},{'stock_name':'invented'},
    {'ticker':720},{'ticker':'１２３４５６'},{'requested_views':['flow']},{'requested_views':['technical','flow']},
    {'original_query':''},{'original_query':'  '},{'original_query':'x\x00y'},
    {'conditions':{'profile':'technical.multiframe.v1','periods':['1y','3m','5y']}},
    {'conditions':{'profile':'technical.multiframe.v1','periods':('3m','1y','5y')}},
    {'conditions':{'profile':'technical.multiframe.v1','periods':['3m','1y','5y'],'negation':True}},
])
def test_intent_does_not_accept_owner_server_context_other_views_or_conditions(changes):
    with pytest.raises(D.TechnicalAdmissionError):D.Intent.parse(intent_values(**changes))


def test_intent_and_policy_are_deeply_frozen_text_not_mutable_input_references():
    raw=intent_values();intent=D.Intent.parse(raw);p=policy_values();policy=D.Policy.parse(p)
    raw['conditions']['periods'].clear();p['supported_tickers'].append('005930')
    assert intent.data()==intent_values() and policy.data()==policy_values()
    returned=intent.data();returned['conditions']['periods'].clear()
    assert intent.data()['conditions']['periods']==['3m','1y','5y']
    with pytest.raises(FrozenInstanceError):intent.text='{}'
    assert PRIVATE not in repr(intent) and 'synthetic-model' not in repr(policy)


class Session:
    def __init__(self):
        self.new=set();self.dirty=set();self.deleted=set();self.in_no_autoflush=False
        self.flush=AsyncMock();self.commit=AsyncMock();self.rollback=AsyncMock()
    @property
    @contextmanager
    def no_autoflush(self):
        self.in_no_autoflush=True
        try:yield
        finally:self.in_no_autoflush=False


def setup(monkeypatch):
    session=Session();p=principal();policy=D.Policy.parse(policy_values());intent=D.Intent.parse(intent_values())
    stamp=datetime(2026,11,12,3,0,tzinfo=UTC);day,start,end=R.kst_period(stamp)
    period=NS(id=uuid4(),operation=D.OPERATION,kst_date=day,period_start=start,period_end=end,
        policy_json=policy.text,policy_sha256=policy.fingerprint,user_request_limit=3,request_limit=10,
        budget_limit_nano=100000,attempt_reserve_nano=10000,request_count=0,reserved_nano=0,blocked=False)
    store=NS(row=None,period=period,stamp=stamp,events=[],stock=NS(stock_code='000720',stock_name='canonical synthetic stock',market='KOSPI'))
    async def auth(s,given,**kw):assert s is session;store.events.append(('auth',given.session_id,kw))
    async def by_key(s,owner,key,**kw):
        store.events.append(('key',kw));return store.row if store.row and store.row.owner_user_id==owner and store.row.key_digest==key else None
    async def owned(s,owner,id,**kw):
        store.events.append(('run',kw));return store.row if store.row and store.row.id==id and store.row.owner_user_id==owner else None
    async def lock_period(s,id,**kw):assert id==period.id;store.events.append(('period',kw));return period
    async def admit_period(s,stamp,given):assert given.text==period.policy_json;store.events.append(('period_admit',{}));return period
    async def insert(s,values):
        assert store.row is None;store.events.append(('insert',{}));store.row=NS(**values);return store.row
    monkeypatch.setattr(S,'validate_principal',AsyncMock(side_effect=auth))
    monkeypatch.setattr(R,'by_key',AsyncMock(side_effect=by_key));monkeypatch.setattr(R,'owned',AsyncMock(side_effect=owned))
    monkeypatch.setattr(R,'period',AsyncMock(side_effect=lock_period));monkeypatch.setattr(R,'admit_period',AsyncMock(side_effect=admit_period))
    monkeypatch.setattr(R,'clock',AsyncMock(side_effect=lambda _:store.stamp))
    monkeypatch.setattr(R,'user_count',AsyncMock(return_value=0));monkeypatch.setattr(R,'stock',AsyncMock(side_effect=lambda *a:store.stock))
    monkeypatch.setattr(R,'insert_run',AsyncMock(side_effect=insert))
    return session,p,policy,intent,store


async def admitted(monkeypatch):
    session,p,policy,intent,store=setup(monkeypatch)
    result=await S.TechnicalAdmissionService(session,principal=p,policy=policy).admit('fixed-key',intent)
    return session,p,policy,intent,store,result


async def test_new_admission_returns_fenced_token_only_after_commit_and_replay_keeps_identity(monkeypatch):
    session,p,policy,intent,store,first=await admitted(monkeypatch)
    assert first.newly_admitted and type(first.claim_token) is bytes and len(first.claim_token)==32
    assert hashlib.sha256(first.claim_token).digest()==store.row.claim_digest
    assert store.period.request_count==1 and store.period.reserved_nano==first.run.held_nano==10000
    assert PRIVATE not in repr(first) and repr(first.claim_token) not in repr(first)
    session.commit.assert_awaited_once()
    original=(first.run,store.row.intent_json,store.row.stock_json,store.row.claim_digest)
    store.stock.stock_name='changed current master'
    replay=await S.TechnicalAdmissionService(session,principal=p,policy=None).admit('fixed-key',intent)
    assert not replay.newly_admitted and replay.claim_token is None and replay.run==first.run
    assert (replay.run,store.row.intent_json,store.row.stock_json,store.row.claim_digest)==original
    assert store.period.request_count==1 and store.period.reserved_nano==10000
    assert R.insert_run.await_count==1


async def test_mutating_original_nested_input_policy_and_principal_during_auth_cannot_rebind(monkeypatch):
    session,p,policy,intent,store=setup(monkeypatch)
    original_text=intent.text;original_policy=policy.text
    service=S.TechnicalAdmissionService(session,principal=p,policy=policy)
    async def mutate(*args,**kw):
        object.__setattr__(intent,'text',D.Intent.parse(intent_values(original_query='changed')).text)
        object.__setattr__(policy,'text',D.Policy.parse(policy_values(user_daily_limit=2)).text)
        service.principal=principal()
    monkeypatch.setattr(S,'validate_principal',AsyncMock(side_effect=mutate))
    result=await service.admit('fixed-key',intent)
    assert result.newly_admitted and store.row.intent_json==original_text
    assert store.row.owner_user_id==p.user_id and store.row.admission_session_id==p.session_id
    assert store.row.policy_sha256==D.sha(original_policy)


@pytest.mark.parametrize('change',['missing','disabled','invalid'])
async def test_missing_or_invalid_policy_closes_only_new_admission(change,monkeypatch):
    session,p,policy,intent,store=setup(monkeypatch)
    supplied=None if change=='missing' else D.Policy.parse(policy_values(enabled=False)) if change=='disabled' else object()
    with pytest.raises(D.TechnicalAdmissionError,match='^POLICY_UNAVAILABLE$'):
        await S.TechnicalAdmissionService(session,principal=p,policy=supplied).admit('key',intent)
    R.admit_period.assert_not_awaited();R.insert_run.assert_not_awaited();session.commit.assert_not_awaited()


@pytest.mark.parametrize('changed',['user','service','budget','blocked'])
async def test_limit_or_block_never_inserts_run_or_returns_claim(changed,monkeypatch):
    session,p,policy,intent,store=setup(monkeypatch)
    if changed=='user':R.user_count.return_value=3;R.user_count.side_effect=None
    elif changed=='service':store.period.request_count=10
    elif changed=='budget':store.period.reserved_nano=95000
    else:store.period.blocked=True
    with pytest.raises(D.TechnicalAdmissionError):await S.TechnicalAdmissionService(session,principal=p,policy=policy).admit('key',intent)
    R.insert_run.assert_not_awaited();session.commit.assert_not_awaited()


async def test_original_session_claim_is_once_and_A2_owner_replay_cannot_dispatch(monkeypatch):
    session,p,policy,intent,store,first=await admitted(monkeypatch)
    a2=principal(p.user_id);service=S.TechnicalAdmissionService(session,principal=a2,policy=policy)
    assert await service.get(first.run.analysis_id)==first.run
    assert not (await service.admit('fixed-key',intent)).newly_admitted
    with pytest.raises(D.TechnicalAdmissionError,match='^CLAIM_DENIED$'):
        await service.dispatch_claim(first.run,first.claim_token)
    assert store.row.state=='admitted' and store.row.claim_consumed_at is None
    original=S.TechnicalAdmissionService(session,principal=p,policy=policy)
    claimed=await original.dispatch_claim(first.run,first.claim_token)
    assert claimed.newly_claimed and claimed.run.state=='claimed' and claimed.intent_json==intent.text
    assert PRIVATE not in repr(claimed)
    original.policy=None
    replay=await original.dispatch_claim(first.run,first.claim_token)
    assert not replay.newly_claimed and replay.intent_json is None and replay.run==claimed.run
    assert store.period.request_count==1 and store.period.reserved_nano==10000


@pytest.mark.parametrize('change',['token','expected_id','expected_hash','expected_deadline','policy_missing','policy_drift','blocked'])
async def test_claim_refuses_wrong_context_token_or_current_policy(change,monkeypatch):
    session,p,policy,intent,store,first=await admitted(monkeypatch)
    expected=first.run;token=first.claim_token;service=S.TechnicalAdmissionService(session,principal=p,policy=policy)
    if change=='token':token=b'wrong-token-not-authorized'.ljust(32,b'x')
    elif change=='expected_id':expected=replace(expected,attempt_id=uuid4())
    elif change=='expected_hash':expected=replace(expected,intent_sha256='f'*64)
    elif change=='expected_deadline':expected=replace(expected,deadline_at=expected.deadline_at+timedelta(seconds=1))
    elif change=='policy_missing':service.policy=None
    elif change=='policy_drift':service.policy=D.Policy.parse(policy_values(user_daily_limit=2))
    else:store.period.blocked=True
    with pytest.raises(D.TechnicalAdmissionError):await service.dispatch_claim(expected,token)
    assert store.row.state=='admitted' and store.row.claim_consumed_at is None
    assert store.period.reserved_nano==10000


@pytest.mark.parametrize('change',['deadline','input','stock_hash','policy_hash','spec','hold','reason'])
async def test_stored_row_policy_binding_is_checked_without_repair(change,monkeypatch):
    session,p,policy,intent,store,first=await admitted(monkeypatch)
    if change=='deadline':store.row.deadline_at=store.row.started_at+timedelta(seconds=61)
    elif change=='input':store.row.intent_json=D.Intent.parse(intent_values(original_query='tampered')).text
    elif change=='stock_hash':store.row.stock_sha256='f'*64
    elif change=='policy_hash':store.row.policy_sha256='f'*64
    elif change=='spec':store.row.spec_json='{}'
    elif change=='hold':store.row.held_nano=0
    else:store.row.unknown_reason='arbitrary'
    with pytest.raises(D.TechnicalAdmissionError):S.TechnicalAdmissionService._receipt(store.row,store.period)


async def test_stock_drift_closes_and_redacts_without_refunding_or_claiming(monkeypatch):
    session,p,policy,intent,store,first=await admitted(monkeypatch)
    store.stock.stock_name='new canonical master name'
    result=await S.TechnicalAdmissionService(session,principal=p,policy=policy).dispatch_claim(first.run,first.claim_token)
    assert not result.newly_claimed and result.intent_json is None
    assert result.run.state=='unknown' and result.run.unknown_reason=='STOCK_CHANGED'
    assert store.row.intent_json is None and store.row.claim_consumed_at is None
    assert store.period.request_count==1 and store.period.reserved_nano==result.run.held_nano==10000


@pytest.mark.parametrize('operation',['get','claim','close'])
async def test_expiry_physically_redacts_on_operation_and_preserves_original_key_period_hold(operation,monkeypatch):
    session,p,policy,intent,store,first=await admitted(monkeypatch)
    store.stamp=first.run.deadline_at+timedelta(seconds=1)
    service=S.TechnicalAdmissionService(session,principal=p,policy=None)
    if operation=='get':result=await service.get(first.run.analysis_id)
    elif operation=='claim':result=(await service.dispatch_claim(first.run,first.claim_token)).run
    else:result=await service.close_unknown(first.run.analysis_id,'CANCELLED')
    assert result.state=='unknown' and result.unknown_reason=='EXPIRED' and result.redacted_at==store.stamp
    assert store.row.intent_json is None and result.held_nano==first.run.held_nano
    assert (result.period_id,result.analysis_id,result.as_of,result.deadline_at,result.intent_sha256)==(first.run.period_id,first.run.analysis_id,first.run.as_of,first.run.deadline_at,first.run.intent_sha256)
    replay=await service.admit('fixed-key',intent)
    assert not replay.newly_admitted and replay.claim_token is None and replay.run==result
    assert store.period.request_count==1 and store.period.reserved_nano==10000
    R.insert_run.assert_awaited_once()


async def test_unknown_terminal_replay_preserves_reason_and_redaction(monkeypatch):
    session,p,policy,intent,store,first=await admitted(monkeypatch)
    service=S.TechnicalAdmissionService(session,principal=p,policy=None)
    closed=await service.close_unknown(first.run.analysis_id,'CANCELLED')
    store.stamp+=timedelta(seconds=1)
    assert await service.close_unknown(first.run.analysis_id,'CANCELLED')==closed
    with pytest.raises(D.TechnicalAdmissionError,match='^IDEMPOTENCY_CONFLICT$'):
        await service.close_unknown(first.run.analysis_id,'TIMEOUT')
    assert store.row.intent_json is None and store.period.reserved_nano==10000


@pytest.mark.parametrize('stage',['admission','claim'])
@pytest.mark.parametrize('error',[OSError('private synthetic failure'),asyncio.CancelledError()])
async def test_commit_ACK_failure_or_cancellation_never_returns_new_rights(stage,error,monkeypatch):
    if stage=='admission':
        session,p,policy,intent,store=setup(monkeypatch);first=None
    else:session,p,policy,intent,store,first=await admitted(monkeypatch)
    session.commit=AsyncMock(side_effect=error)
    service=S.TechnicalAdmissionService(session,principal=p,policy=policy)
    call=service.admit('fixed-key',intent) if stage=='admission' else service.dispatch_claim(first.run,first.claim_token)
    if isinstance(error,asyncio.CancelledError):
        with pytest.raises(asyncio.CancelledError):await call
    else:
        with pytest.raises(D.TechnicalAdmissionError,match='^ACK_UNKNOWN$') as failed:await call
        assert 'private synthetic' not in str(failed.value)
    assert session.rollback.await_count==1


@pytest.mark.parametrize('stage',['admission','claim'])
async def test_delayed_commit_ACK_cannot_extend_original_deadline(stage,monkeypatch):
    clock=[0.0];monkeypatch.setattr(S,'time',NS(monotonic=lambda:clock[0]))
    if stage=='admission':session,p,policy,intent,store=setup(monkeypatch);first=None
    else:session,p,policy,intent,store,first=await admitted(monkeypatch)
    async def delayed():clock[0]=61.0
    session.commit=AsyncMock(side_effect=delayed)
    service=S.TechnicalAdmissionService(session,principal=p,policy=policy)
    result=await service.admit('fixed-key',intent) if stage=='admission' else await service.dispatch_claim(first.run,first.claim_token)
    if stage=='admission':assert not result.newly_admitted and result.claim_token is None
    else:assert not result.newly_claimed and result.intent_json is None and result.run.state=='claimed'
    assert store.period.reserved_nano==10000 and store.period.request_count==1


async def test_readonly_ACK_recovery_has_no_autoflush_commit_or_new_token_even_dirty_session(monkeypatch):
    session,p,policy,intent,store,first=await admitted(monkeypatch)
    session.flush.reset_mock();session.commit.reset_mock();session.rollback.reset_mock()
    dirty=object();session.dirty={dirty}
    async def read_key(*args):assert session.in_no_autoflush;return NS(**vars(store.row))
    async def read_period(*args):assert session.in_no_autoflush;return NS(**vars(store.period))
    monkeypatch.setattr(R,'read_by_key',AsyncMock(side_effect=read_key));monkeypatch.setattr(R,'read_period',AsyncMock(side_effect=read_period))
    recovered=await S.TechnicalAdmissionService(session,principal=p,policy=None).reconcile('fixed-key')
    assert recovered.run==first.run and not recovered.newly_admitted and recovered.claim_token is None
    assert session.dirty=={dirty} and not session.in_no_autoflush
    session.flush.assert_not_awaited();session.commit.assert_not_awaited();session.rollback.assert_not_awaited()


async def test_mutations_refuse_unrelated_pending_work_instead_of_committing_it(monkeypatch):
    session,p,policy,intent,store=setup(monkeypatch);session.new={object()}
    with pytest.raises(D.TechnicalAdmissionError,match='^CONTEXT_DIRTY$'):
        await S.TechnicalAdmissionService(session,principal=p,policy=policy).admit('key',intent)
    S.validate_principal.assert_not_awaited();session.commit.assert_not_awaited();session.rollback.assert_not_awaited()


def test_migration_and_model_share_exact_constraints_and_retained_identity_links():
    from db.models.technical import execution_admission as model
    tree=ast.parse((ROOT/'backend/db/migrations/versions/20261112_c48001a7e0001_technical_execution_admission.py').read_text())
    values={node.targets[0].id:ast.literal_eval(node.value) for node in tree.body
            if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name)
            and node.targets[0].id in {'PERIOD_CHECKS','RUN_CHECKS','revision','down_revision'}}
    for node in tree.body:
        if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Subscript):
            target=node.targets[0]
            if isinstance(target.value,ast.Name) and target.value.id=='PERIOD_CHECKS':
                values['PERIOD_CHECKS'][ast.literal_eval(target.slice)]=ast.literal_eval(node.value)
    assert values['PERIOD_CHECKS']==model.PERIOD_CHECKS
    assert {k:v for k,v in values['RUN_CHECKS'].items() if k!='state'}=={k:(model.OLD_SPEC_CHECK if k=='spec' else v) for k,v in model.RUN_CHECKS.items() if k!='state'}
    newer=ast.parse((ROOT/'backend/db/migrations/versions/20261112_c50001a7e0001_technical_result_completion.py').read_text())
    additions={n.targets[0].id:ast.literal_eval(n.value) for n in newer.body
        if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id in {'OLD_STATE_CHECK','STATE_CHECK','COMPLETION_CHECKS'}}
    assert additions['OLD_STATE_CHECK']==values['RUN_CHECKS']['state']
    assert additions['STATE_CHECK']==model.RUN_CHECKS['state'] and additions['COMPLETION_CHECKS']==model.COMPLETION_CHECKS
    assert (values['revision'],values['down_revision'])==('c48001a7e0001','c45001a7e0001')
    run=model.TechnicalAnalysisRun.__table__
    assert not run.c.admission_session_id.foreign_keys and not run.c.planned_report_id.foreign_keys
    assert {fk.ondelete for fk in run.foreign_keys}=={'RESTRICT'}
    assert {fk.column.table.name for fk in run.foreign_keys}=={'auth_users','technical_usage_periods'}


async def test_owned_SQL_entry_rejects_non_original_proof_before_resource_or_application_use():
    from scripts.cf035_technical_owned_check import verify_technical_admission
    with pytest.raises(RuntimeError,match='^Technical admission requires original owned proof$'):
        await verify_technical_admission(NS(verify_ownership=lambda:pytest.fail('untrusted proof used')))


def completion_response(binding):
    path=ROOT/'frontend/tests/fixtures/cf031-technical-boundary-read.json'
    assert hashlib.sha256(path.read_bytes()).hexdigest()=='46380ea4c998e3130cf1c447c278b93ed32288c42af9d62f84b90b7acabce5e0'
    response=copy.deepcopy(json.loads(path.read_text())['response'])
    request=json.loads(binding.boundary.input_json);data=request['data']
    response.update(request_id=request['request_id'],trace_id=request['trace_id'])
    response['data'].update(request_snapshot=copy.deepcopy(data),request_sha256=hashlib.sha256(binding.boundary.input_json.encode()).hexdigest())
    response['data']['result'].update(request_id=request['request_id'],trace_id=request['trace_id'],
        ticker=data['stock']['stock_code'],as_of=data['requested_as_of'],resolved_stock_name=data['stock']['stock_name'])
    return response


async def completion_setup(monkeypatch,*,claim=True):
    """Actual coordinator/profile/CF031/CF035; persistence/auth I/O is explicit DI."""
    from src.modules.technical.application import execution_completion as E,owned_report_service as W
    from src.modules.technical.infrastructure import execution_completion_repository as CR,report_repository as WR
    from src.modules.analysis.application import coordinator as C
    from db.models.technical.report_snapshot import TechnicalReportSnapshot
    from db.models.common.agent_report import AgentReport
    session,p,policy,intent,store,first=await admitted(monkeypatch)
    claimed=await S.TechnicalAdmissionService(session,principal=p,policy=policy).dispatch_claim(first.run,first.claim_token) if claim else None
    if claim:assert claimed.newly_claimed
    for field in ('completion_format','input_json','input_sha256','result_json','result_sha256','binding_sha256','accepted_at','error_code'):
        setattr(store.row,field,None)
    store.row._completion_period=store.period
    binding=E.binding_from_sql(store.row);response=completion_response(binding)
    ledger=NS(root=None,snapshot=None,indexes=[],groups=[],commits=[],stage_auth=[])
    async def auth(s,actual,**kw):
        assert s is session;ledger.stage_auth.append(actual)
    monkeypatch.setattr(C,'validate_principal',AsyncMock(side_effect=auth))
    monkeypatch.setattr(W,'validate_principal',AsyncMock(side_effect=auth))
    async def commit():
        ledger.commits.append((store.row.state,store.row.intent_json,getattr(store.row,'input_json',None)))
        session.new.clear();session.dirty.clear();session.deleted.clear()
    session.commit=AsyncMock(side_effect=commit)
    session.scalar=AsyncMock(side_effect=lambda statement:store.stamp)
    def add(value):
        session.new.add(value)
        if isinstance(value,TechnicalReportSnapshot):ledger.snapshot=value
        elif isinstance(value,AgentReport):ledger.indexes.append(value)
    session.add=add
    async def add_report(s,**rows):
        ledger.root=rows['report']
        ledger.groups=[rows['signals'],rows['charts'],rows['risk_notes'],[rows['interpretation']],[rows['verification']]]
    monkeypatch.setattr(WR,'storage_root_for_update',AsyncMock(side_effect=lambda s,id:ledger.root))
    monkeypatch.setattr(WR,'technical_indexes',AsyncMock(side_effect=lambda s,id:list(ledger.indexes)))
    monkeypatch.setattr(WR,'get_stock',AsyncMock(side_effect=lambda s,ticker:store.stock))
    monkeypatch.setattr(WR,'add_report',AsyncMock(side_effect=add_report))
    async def stored(s,id,owner):
        if ledger.root and ledger.snapshot and ledger.root.owner_user_id==owner and any(i.owner_user_id==owner for i in ledger.indexes):
            return ledger.root,ledger.snapshot
    monkeypatch.setattr(WR,'get_owned_storage',AsyncMock(side_effect=stored))
    monkeypatch.setattr(WR,'storage_children',AsyncMock(side_effect=lambda s,id:ledger.groups))
    async def accept(s,row,claim,frozen):
        assert row.state=='claimed' and claim==row.claim_digest
        row.state='result_ready';row.completion_format=D.COMPLETION_FORMAT;row.accepted_at=store.stamp
        for key in ('input_json','input_sha256','result_json','result_sha256','binding_sha256'):setattr(row,key,getattr(frozen,key))
        row.error_code=None;return row
    monkeypatch.setattr(CR,'accept',AsyncMock(side_effect=accept))
    async def readonly(s,owner,id):
        assert s.in_no_autoflush
        return NS(**vars(store.row)) if owner==p.user_id and id==store.row.id else None
    monkeypatch.setattr(CR,'read_owned',AsyncMock(side_effect=readonly))
    def coordinator(actual=p,current_policy=policy):
        return C.AnalysisCoordinator(session,principal=actual,client=None,profile=E.TechnicalCompletionProfile(policy=current_policy))
    return NS(session=session,p=p,policy=policy,intent=intent,store=store,first=first,claimed=claimed,
        binding=binding,response=response,ledger=ledger,E=E,W=W,CR=CR,C=C,WR=WR,coordinator=coordinator)


async def test_completion_real_coordinator_and_writer_preserve_E_B_S_and_consume_text(monkeypatch):
    h=await completion_setup(monkeypatch)
    result=await h.coordinator().receive(h.claimed.run,h.first.claim_token,h.response)
    assert result.run.state=='stored' and len(h.ledger.indexes)==1 and h.ledger.root is not None
    assert [v[0] for v in h.ledger.commits]==['result_ready','stored']
    assert h.store.row.intent_json is h.store.row.input_json is h.store.row.result_json is None
    assert h.ledger.snapshot.input_json==h.binding.boundary.input_json
    assert h.ledger.snapshot.result_json==h.E.canonical_json(h.response)
    assert h.intent.fingerprint!=result.input_sha256!=h.binding.caller_context.input_fingerprint
    assert h.store.period.request_count==1 and h.store.period.reserved_nano==10000 and result.run.held_nano==10000
    assert not (await S.TechnicalAdmissionService(h.session,principal=h.p,policy=None).dispatch_claim(h.claimed.run,h.first.claim_token)).newly_claimed
    before=h.session.commit.await_count
    assert (await h.coordinator(current_policy=None).get(h.claimed.run.analysis_id)).run.state=='stored'
    assert h.session.commit.await_count==before+1 and len(h.ledger.indexes)==1


@pytest.mark.parametrize('drift',['owner','A2','token','attempt','policy','Stock'])
async def test_completion_wrong_identity_cannot_accept_or_fail_legitimate_run(drift,monkeypatch):
    h=await completion_setup(monkeypatch);actual=h.p;expected=h.claimed.run;token=h.first.claim_token;policy=h.policy
    if drift=='owner':actual=principal()
    if drift=='A2':actual=principal(h.p.user_id)
    if drift=='token':token=b'z'*32
    if drift=='attempt':expected=replace(expected,attempt_id=uuid4())
    if drift=='policy':policy=D.Policy.parse(policy_values(deadline_seconds=59))
    if drift=='Stock':h.store.stock.stock_name='changed master'
    with pytest.raises((D.TechnicalAdmissionError,D.TechnicalCompletionError)):
        await h.coordinator(actual,policy).receive(expected,token,h.response)
    assert h.store.row.state=='claimed' and h.ledger.root is None and not h.ledger.commits
    assert h.store.period.request_count==1 and h.store.period.reserved_nano==10000


async def ready_completion(h,monkeypatch):
    async def unavailable(*args):raise OSError('synthetic transient writer')
    original=h.E.TechnicalCompletionAdapter.stage
    monkeypatch.setattr(h.E.TechnicalCompletionAdapter,'stage',unavailable)
    with pytest.raises(D.TechnicalCompletionError,match='SERVICE_UNAVAILABLE'):
        await h.coordinator().receive(h.claimed.run,h.first.claim_token,h.response)
    assert h.store.row.state=='result_ready' and h.store.row.input_json is not None
    monkeypatch.setattr(h.E.TechnicalCompletionAdapter,'stage',original)


async def test_completion_A2_publishes_after_original_deadline_without_reclaim_or_policy(monkeypatch):
    h=await completion_setup(monkeypatch);await ready_completion(h,monkeypatch)
    original_times=(h.store.row.as_of,h.store.row.deadline_at,h.store.row.claim_consumed_at,h.store.row.accepted_at)
    h.store.stamp+=timedelta(seconds=120);a2=principal(h.p.user_id)
    assert (await h.coordinator(a2,None).get(h.claimed.run.analysis_id)).run.state=='result_ready'
    assert h.ledger.root is None # GET never auto-publishes.
    result=await h.coordinator(a2,None).publish(h.claimed.run.analysis_id)
    assert result.run.state=='stored' and h.ledger.snapshot.owner_session_id==a2.session_id
    assert h.ledger.indexes[0].owner_session_id==a2.session_id!=h.store.row.admission_session_id
    assert original_times==(h.store.row.as_of,h.store.row.deadline_at,h.store.row.claim_consumed_at,h.store.row.accepted_at)
    assert h.ledger.stage_auth[-1].session_id==a2.session_id
    assert result.run.held_nano==10000 and h.store.period.request_count==1


async def test_same_stored_incoming_replay_is_checked_and_different_result_cannot_overwrite(monkeypatch):
    h=await completion_setup(monkeypatch);await h.coordinator().receive(h.claimed.run,h.first.claim_token,h.response)
    original=h.ledger.snapshot.result_json
    assert (await h.coordinator(current_policy=None).receive(h.claimed.run,h.first.claim_token,h.response)).run.state=='stored'
    changed=copy.deepcopy(h.response);changed['data']['result']['interpretation']['text']='different valid result'
    with pytest.raises(D.TechnicalCompletionError,match='RESULT_CONFLICT'):
        await h.coordinator(current_policy=None).receive(h.claimed.run,h.first.claim_token,changed)
    assert h.ledger.snapshot.result_json==original and h.store.row.state=='stored' and len(h.ledger.indexes)==1


@pytest.mark.parametrize('pending',['new','dirty','deleted'])
async def test_completion_readonly_reconcile_refuses_pending_caller_work_without_refresh(pending,monkeypatch):
    h=await completion_setup(monkeypatch)
    h.C.validate_principal.reset_mock();h.CR.read_owned.reset_mock();h.session.commit.reset_mock();h.session.flush.reset_mock()
    value=NS(private='pending value');getattr(h.session,pending).add(id(value))
    with pytest.raises(D.TechnicalAdmissionError,match='CONTEXT_DIRTY'):
        await h.E.reconcile_completion(h.session,principal=h.p,analysis_id=h.claimed.run.analysis_id)
    assert value.private=='pending value' and id(value) in getattr(h.session,pending)
    h.C.validate_principal.assert_not_awaited();h.CR.read_owned.assert_not_awaited()
    h.session.flush.assert_not_awaited();h.session.commit.assert_not_awaited()


@pytest.mark.parametrize('boundary',['stage','publish_flush','publish_commit'])
async def test_automatic_publication_cancel_rolls_back_and_propagates(boundary,monkeypatch):
    h=await completion_setup(monkeypatch);original=h.E.TechnicalCompletionAdapter.stage
    async def stage(*args):
        if boundary=='stage':raise asyncio.CancelledError()
        return await original(*args)
    monkeypatch.setattr(h.E.TechnicalCompletionAdapter,'stage',stage)
    if boundary=='publish_flush':h.session.flush=AsyncMock(side_effect=[None,asyncio.CancelledError()])
    if boundary=='publish_commit':
        committed=h.session.commit
        async def commit():
            if len(h.ledger.commits)==1:raise asyncio.CancelledError()
            await committed()
        h.session.commit=AsyncMock(side_effect=commit)
    h.session.rollback.reset_mock()
    with pytest.raises(asyncio.CancelledError):await h.coordinator().receive(h.claimed.run,h.first.claim_token,h.response)
    assert h.session.rollback.await_count==1 and h.ledger.commits[0][0]=='result_ready'
    assert h.store.period.reserved_nano==10000 and h.store.row.claim_consumed_at is not None


async def test_same_existing_full_report_and_transient_stage_error_is_not_a_conflict(monkeypatch):
    h=await completion_setup(monkeypatch);await ready_completion(h,monkeypatch)
    frozen=h.coordinator().profile.from_stored(h.E.TechnicalCompletionAdapter(h.binding),h.store.row)
    a2=principal(h.p.user_id)
    await h.W.TechnicalOwnedReportService(h.session,principal=a2).stage(h.binding,frozen);await h.session.commit()
    original=h.E.TechnicalCompletionAdapter.stage
    async def transient(*args):raise OSError('synthetic transient stage error')
    monkeypatch.setattr(h.E.TechnicalCompletionAdapter,'stage',transient)
    with pytest.raises(D.TechnicalCompletionError,match='SERVICE_UNAVAILABLE'):
        await h.coordinator(a2,None).publish(h.claimed.run.analysis_id)
    assert h.store.row.state=='result_ready' and h.store.row.result_sha256==frozen.result_sha256 and h.store.row.held_nano==10000
    monkeypatch.setattr(h.E.TechnicalCompletionAdapter,'stage',original)
    assert (await h.coordinator(a2,None).publish(h.claimed.run.analysis_id)).run.state=='stored'
    assert len(h.ledger.indexes)==1 and h.ledger.snapshot.owner_session_id==a2.session_id


async def test_other_valid_stored_result_is_confirmed_conflict_without_overwrite(monkeypatch):
    h=await completion_setup(monkeypatch);await ready_completion(h,monkeypatch)
    changed=copy.deepcopy(h.response);changed['data']['result']['interpretation']['text']='different valid stored result'
    frozen=h.binding.compose(changed)
    await h.W.TechnicalOwnedReportService(h.session,principal=h.p).stage(h.binding,frozen);await h.session.commit()
    with pytest.raises(D.TechnicalCompletionError,match='RESULT_CONFLICT'):
        await h.coordinator(current_policy=None).publish(h.claimed.run.analysis_id)
    assert h.store.row.state=='failed' and h.store.row.result_json is None and h.store.row.intent_json is None
    assert h.ledger.snapshot.result_json==frozen.result_json and h.store.row.result_sha256!=frozen.result_sha256
    assert h.store.row.held_nano==10000 and len(h.ledger.indexes)==1


async def test_uncertain_stored_lookup_keeps_ready_snapshot_and_hold(monkeypatch):
    h=await completion_setup(monkeypatch);await ready_completion(h,monkeypatch)
    original=h.E.TechnicalCompletionAdapter.stage
    async def unavailable(*args):raise OSError('synthetic unavailable')
    monkeypatch.setattr(h.E.TechnicalCompletionAdapter,'stage',unavailable)
    monkeypatch.setattr(h.W.TechnicalOwnedReportService,'read',AsyncMock(side_effect=OSError('synthetic lookup unavailable')))
    before=(h.store.row.input_json,h.store.row.result_json,h.store.row.binding_sha256,h.store.row.accepted_at)
    with pytest.raises(D.TechnicalCompletionError,match='SERVICE_UNAVAILABLE'):
        await h.coordinator(current_policy=None).publish(h.claimed.run.analysis_id)
    assert h.store.row.state=='result_ready' and before==(h.store.row.input_json,h.store.row.result_json,h.store.row.binding_sha256,h.store.row.accepted_at)
    assert h.store.row.held_nano==10000


async def test_ready_cancel_and_late_result_do_not_restore_snapshot_or_reexecute(monkeypatch):
    h=await completion_setup(monkeypatch);await ready_completion(h,monkeypatch)
    old=(h.store.row.input_sha256,h.store.row.result_sha256,h.store.row.binding_sha256,h.store.row.accepted_at)
    await S.TechnicalAdmissionService(h.session,principal=h.p).close_unknown(h.claimed.run.analysis_id,'CANCELLED')
    assert h.store.row.state=='unknown' and h.store.row.intent_json is h.store.row.input_json is h.store.row.result_json is None
    assert (await h.coordinator(current_policy=None).receive(h.claimed.run,h.first.claim_token,h.response)).run.state=='unknown'
    assert h.ledger.root is None and old==(h.store.row.input_sha256,h.store.row.result_sha256,h.store.row.binding_sha256,h.store.row.accepted_at)
    assert h.store.row.held_nano==10000


async def test_mutable_response_and_expected_UUID_are_frozen_before_first_await(monkeypatch):
    h=await completion_setup(monkeypatch);expected=replace(h.claimed.run)
    original_id=UUID(int=expected.analysis_id.int);response_text=h.E.canonical_json(h.response)
    async def mutate(*args,**kw):
        h.response['data']['result']['interpretation']['text']='changed after first await'
        object.__setattr__(expected.analysis_id,'int',uuid4().int)
    monkeypatch.setattr(h.C,'validate_principal',AsyncMock(side_effect=mutate))
    result=await h.coordinator().receive(expected,h.first.claim_token,h.response)
    assert result.run.analysis_id==original_id and h.ledger.snapshot.result_json==response_text


@pytest.mark.parametrize('bad',[None,{'invalid':'response'},{'value':float('nan')}])
async def test_invalid_result_only_closes_authenticated_matching_claim(bad,monkeypatch):
    h=await completion_setup(monkeypatch)
    result=await h.coordinator().receive(h.claimed.run,h.first.claim_token,bad)
    assert result.run.state=='failed' and result.error_code=='RESULT_CONTRACT_INVALID'
    assert result.accepted_at is None and h.store.row.intent_json is None and h.ledger.root is None
    assert h.store.row.held_nano==10000


async def test_snapshot_ACK_error_never_automatically_publishes_or_claims(monkeypatch):
    h=await completion_setup(monkeypatch)
    committed=h.session.commit
    async def lost():await committed();raise OSError('synthetic ACK wrapper')
    h.session.commit=AsyncMock(side_effect=lost)
    with pytest.raises(D.TechnicalCompletionError,match='SERVICE_UNAVAILABLE'):
        await h.coordinator().receive(h.claimed.run,h.first.claim_token,h.response)
    assert h.ledger.commits[0][0]=='result_ready' and h.store.row.state=='result_ready' and h.ledger.root is None
    assert h.store.row.held_nano==10000 and h.store.row.claim_consumed_at is not None


async def test_clean_readonly_completion_reconcile_has_no_commit_or_new_claim(monkeypatch):
    h=await completion_setup(monkeypatch);await ready_completion(h,monkeypatch)
    monkeypatch.setattr(h.E,'validate_principal',AsyncMock())
    h.session.flush.reset_mock();h.session.commit.reset_mock();h.session.rollback.reset_mock()
    result=await h.E.reconcile_completion(h.session,principal=h.p,analysis_id=h.claimed.run.analysis_id)
    assert result.run.state=='result_ready' and result.run.held_nano==10000
    h.session.flush.assert_not_awaited();h.session.commit.assert_not_awaited();h.session.rollback.assert_not_awaited()


async def test_receive_only_profile_has_no_second_admission_dispatch_post(monkeypatch):
    h=await completion_setup(monkeypatch)
    with pytest.raises(D.TechnicalCompletionError,match='INPUT_INVALID'):
        await h.coordinator().post({},uuid4())
    assert h.session.commit.await_count==0 and h.store.period.request_count==1


@pytest.mark.parametrize('extra',[['--google-input','approved-file'],['--lifetime-seconds','300']])
def test_completion_bad_CLI_options_stop_before_Docker(extra):
    import argparse
    source=ast.parse((ROOT/'backend/scripts/cf002_interactive_login.py').read_text())
    actual=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='main')
    calls=[]
    def Docker():calls.append(True);raise AssertionError('No resource call permitted')
    values=dict(argparse=argparse,sys=NS(argv=['entry','--verify-technical-completion-db',*extra]),
        __doc__='fixed CLI regression',LocalDocker=Docker)
    exec(compile(ast.Module(body=[actual],type_ignores=[]),'<actual fixed CLI main>','exec'),values)
    with pytest.raises(SystemExit) as stopped:values['main']()
    assert stopped.value.code==2 and not calls


async def test_completion_owned_entry_rejects_non_original_proof_before_resources():
    from scripts.cf035_technical_owned_check import verify_technical_completion
    with pytest.raises(RuntimeError,match='Technical completion requires original owned proof'):
        await verify_technical_completion(NS(verify_ownership=lambda:pytest.fail('Untrusted proof used')))


async def runtime_setup(monkeypatch,*,status=200,handler=None):
    import httpx
    from src.modules.technical.application import execution_runtime as X
    from src.shared.infrastructure.clients.ai_client import AIClient
    h=await completion_setup(monkeypatch,claim=False);sent=[]
    async def reply(request):
        sent.append(request)
        assert request.url.path=='/internal/technical/boundary' and request.headers['X-Technical-Service-Token']=='t'*32
        if handler:return await handler(request)
        return httpx.Response(status,json=completion_response(h.E.binding_from_sql(h.store.row)))
    client=AIClient('http://technical.synthetic',10,httpx.MockTransport(reply),service_token='t'*32)
    monkeypatch.setattr(X,'validate_principal',S.validate_principal)
    def runtime(**changes):
        options=dict(principal=h.p,client=client,policy=h.policy,enabled=True,utcnow=lambda:h.store.stamp)
        options.update(changes);return X.TechnicalExecutionRuntime(h.session,**options)
    h.X=X;h.client=client;h.sent=sent;h.runtime=runtime
    return h


@pytest.mark.parametrize('invalid',['disabled','client','policy','bad_policy','token','URL','service_token','transport','method','context'])
async def test_runtime_preflight_bad_configuration_never_claims_or_sends(invalid,monkeypatch):
    h=await runtime_setup(monkeypatch);options={};token=h.first.claim_token
    if invalid=='disabled':options['enabled']=False
    if invalid=='client':options['client']=object()
    if invalid=='policy':options['policy']=None
    if invalid=='bad_policy':options['policy']=D.Policy.parse(policy_values(enabled=False))
    if invalid=='token':token=b'x'
    if invalid=='URL':h.client._base_url='http://user@technical.synthetic/path'
    if invalid=='service_token':h.client._flow_token='bad'
    if invalid=='transport':h.client._transport=object()
    if invalid=='method':h.client.technical_boundary=AsyncMock()
    if invalid=='context':h.session.dirty.add(object())
    with pytest.raises(D.TechnicalCompletionError,match='SERVICE_UNAVAILABLE'):
        await h.runtime(**options).execute_admitted_once(h.first.run,token)
    assert h.store.row.state=='admitted' and h.store.row.claim_consumed_at is None and not h.sent and not h.ledger.commits


async def test_runtime_real_admission_claim_client_receive_writer_one_invocation(monkeypatch):
    h=await runtime_setup(monkeypatch);runtime=h.runtime()
    result=await runtime.execute_admitted_once(h.first.run,h.first.claim_token)
    assert result.run.state=='stored' and result.run.held_nano==10000 and len(h.sent)==1
    assert [v[0] for v in h.ledger.commits]==['claimed','claimed','result_ready','stored']
    request=json.loads(h.sent[0].content)
    assert request==json.loads(h.binding.boundary.input_json)
    assert len(h.ledger.indexes)==1 and h.ledger.snapshot.input_json==h.binding.boundary.input_json
    assert h.store.period.request_count==1 and h.store.period.reserved_nano==10000
    before=h.session.commit.await_count
    with pytest.raises(D.TechnicalCompletionError):await runtime.execute_admitted_once(h.first.run,h.first.claim_token)
    assert h.session.commit.await_count==before and len(h.sent)==1
    assert (await h.runtime().execute_admitted_once(h.first.run,h.first.claim_token)).run.state=='stored'
    assert len(h.sent)==1


@pytest.mark.parametrize('phase',['claim','fresh'])
async def test_runtime_commit_ACK_unknown_never_dispatches(phase,monkeypatch):
    h=await runtime_setup(monkeypatch);commit=h.session.commit;calls=0
    async def lost():
        nonlocal calls
        calls+=1;await commit()
        if calls==(1 if phase=='claim' else 2):raise OSError(PRIVATE)
    h.session.commit=AsyncMock(side_effect=lost)
    with pytest.raises((D.TechnicalAdmissionError,D.TechnicalCompletionError)) as error:
        await h.runtime().execute_admitted_once(h.first.run,h.first.claim_token)
    assert PRIVATE not in str(error.value) and not h.sent and h.store.period.reserved_nano==10000


@pytest.mark.parametrize('change',['ready','unknown','config','method','deadline'])
async def test_runtime_fresh_state_and_capture_drift_prevents_boundary(change,monkeypatch):
    h=await runtime_setup(monkeypatch);commit=h.session.commit;changed=False
    async def after_claim():
        nonlocal changed
        await commit()
        if changed:return
        changed=True
        if change=='config':h.client._flow_token='u'*32
        elif change=='method':h.client.technical_boundary=AsyncMock()
        elif change=='deadline':h.store.stamp=h.first.run.deadline_at
        elif change=='unknown':
            h.store.row.state='unknown';h.store.row.intent_json=None;h.store.row.redacted_at=h.store.stamp;h.store.row.unknown_reason='CANCELLED'
        else:
            # Independent result accepted before this invocation's fresh lock.
            frozen=h.E.TechnicalCompletionAdapter(h.binding).validate_and_freeze(h.response)
            await h.CR.accept(h.session,h.store.row,h.store.row.claim_digest,frozen)
    h.session.commit=AsyncMock(side_effect=after_claim)
    try:result=await h.runtime().execute_admitted_once(h.first.run,h.first.claim_token)
    except D.TechnicalCompletionError:assert change in {'config','method','deadline'}
    else:assert result.run.state in {'result_ready','unknown'}
    assert not h.sent and h.store.period.reserved_nano==10000


async def test_runtime_incoming_expected_policy_and_principal_are_frozen_before_auth(monkeypatch):
    h=await runtime_setup(monkeypatch);runtime=h.runtime();expected=replace(h.first.run)
    original=S.validate_principal
    async def mutate(*args,**kwargs):
        await original(*args,**kwargs)
        object.__setattr__(expected.analysis_id,'int',uuid4().int)
        object.__setattr__(h.policy,'text',D.Policy.parse(policy_values(user_daily_limit=2)).text)
        runtime.principal=principal()
    monkeypatch.setattr(S,'validate_principal',AsyncMock(side_effect=mutate))
    result=await runtime.execute_admitted_once(expected,h.first.claim_token)
    assert result.run.state=='stored' and result.run.analysis_id==h.store.row.id and len(h.sent)==1
    assert h.ledger.snapshot.owner_user_id==h.p.user_id


@pytest.mark.parametrize('status',[403,422,500,504])
async def test_runtime_client_failure_uses_claimed_fence_and_full_hold(status,monkeypatch):
    h=await runtime_setup(monkeypatch,status=status)
    result=await h.runtime().execute_admitted_once(h.first.run,h.first.claim_token)
    assert result.run.state=='unknown' and result.run.held_nano==10000 and len(h.sent)==1
    assert result.run.unknown_reason==('TIMEOUT' if status==504 else 'DISPATCH_UNCERTAIN')
    assert h.ledger.root is None and h.store.row.intent_json is None
    assert (await h.runtime().execute_admitted_once(h.first.run,h.first.claim_token)).run.state=='unknown' and len(h.sent)==1


async def test_runtime_external_client_cancel_adds_no_SQL_cleanup(monkeypatch):
    async def cancelled(request):raise asyncio.CancelledError(PRIVATE)
    h=await runtime_setup(monkeypatch,handler=cancelled);close=AsyncMock()
    monkeypatch.setattr(S.TechnicalAdmissionService,'close_unknown',close)
    with pytest.raises(asyncio.CancelledError):await h.runtime().execute_admitted_once(h.first.run,h.first.claim_token)
    close.assert_not_awaited();assert h.store.row.state=='claimed' and len(h.sent)==1
    assert [v[0] for v in h.ledger.commits]==['claimed','claimed'] and h.store.period.reserved_nano==10000


@pytest.mark.parametrize('failure',['stage','cancel','receive_ACK'])
async def test_runtime_receive_failure_never_closes_already_accepted_result(failure,monkeypatch):
    h=await runtime_setup(monkeypatch);close=AsyncMock()
    monkeypatch.setattr(S.TechnicalAdmissionService,'close_unknown',close)
    if failure in {'stage','cancel'}:
        async def fail(*args):
            if failure=='cancel':raise asyncio.CancelledError(PRIVATE)
            raise OSError(PRIVATE)
        monkeypatch.setattr(h.E.TechnicalCompletionAdapter,'stage',fail)
    else:
        original=h.session.commit
        async def lost():
            await original()
            if h.store.row.state=='result_ready':raise OSError(PRIVATE)
        h.session.commit=AsyncMock(side_effect=lost)
    with pytest.raises(asyncio.CancelledError if failure=='cancel' else D.TechnicalCompletionError):
        await h.runtime().execute_admitted_once(h.first.run,h.first.claim_token)
    close.assert_not_awaited();assert h.store.row.state=='result_ready' and h.store.row.result_json and len(h.sent)==1
    assert h.store.period.reserved_nano==h.store.row.held_nano==10000


async def test_runtime_client_failure_racing_ready_never_redacts_accepted_snapshot(monkeypatch):
    async def accept_then_fail(request):
        frozen=h.E.TechnicalCompletionAdapter(h.binding).validate_and_freeze(h.response)
        await h.CR.accept(h.session,h.store.row,h.store.row.claim_digest,frozen)
        import httpx
        return httpx.Response(500)
    h=await runtime_setup(monkeypatch,handler=accept_then_fail);close=AsyncMock()
    monkeypatch.setattr(S.TechnicalAdmissionService,'close_unknown',close)
    result=await h.runtime().execute_admitted_once(h.first.run,h.first.claim_token)
    close.assert_not_awaited();assert result.run.state=='result_ready' and h.store.row.result_json and len(h.sent)==1


async def test_AIClient_technical_snapshot_is_used_after_await_without_mutable_readback(monkeypatch):
    import httpx
    from src.shared.infrastructure.clients import ai_client as A
    h=await runtime_setup(monkeypatch);original=httpx.AsyncClient
    class MutatingClient(original):
        async def __aenter__(self):
            h.client._base_url='http://changed.invalid';h.client._flow_token='changed';h.client._transport=None
            return await super().__aenter__()
    monkeypatch.setattr(A.httpx,'AsyncClient',MutatingClient)
    result=await h.runtime().execute_admitted_once(h.first.run,h.first.claim_token)
    assert result.run.state=='stored' and h.sent[0].url.host=='technical.synthetic'
    assert h.sent[0].headers['X-Technical-Service-Token']=='t'*32
    assert PRIVATE not in repr(h.client._technical_boundary_configuration) # bound method repr has no secret snapshot


@pytest.mark.parametrize('phase',['fresh','client_failure'])
async def test_runtime_unexpected_SQL_error_is_fixed_without_raw_parameters_or_retry(phase,monkeypatch):
    from sqlalchemy.exc import StatementError
    h=await runtime_setup(monkeypatch,status=503);original=h.X.validate_principal;calls=0
    async def broken(*args,**kw):
        nonlocal calls
        calls+=1
        if calls==(1 if phase=='fresh' else 2):raise StatementError(PRIVATE,PRIVATE,{'private':PRIVATE},RuntimeError(PRIVATE))
        return await original(*args,**kw)
    monkeypatch.setattr(h.X,'validate_principal',broken)
    with pytest.raises(D.TechnicalCompletionError,match='SERVICE_UNAVAILABLE') as error:
        await h.runtime().execute_admitted_once(h.first.run,h.first.claim_token)
    assert PRIVATE not in str(error.value) and error.value.__suppress_context__
    assert h.store.row.state=='claimed' and h.store.row.held_nano==10000 and len(h.sent)==(0 if phase=='fresh' else 1)
    assert h.store.period.request_count==1 and h.store.period.reserved_nano==10000


async def test_runtime_external_ClaimReceipt_is_not_an_execution_authority(monkeypatch):
    h=await runtime_setup(monkeypatch)
    with pytest.raises(D.TechnicalCompletionError):
        await h.runtime().execute_admitted_once(D.ClaimReceipt(h.first.run,False),h.first.claim_token)
    assert h.store.row.state=='admitted' and not h.sent and not h.ledger.commits


async def test_runtime_shorter_waiter_timeout_exits_context_before_claimed_cleanup(monkeypatch):
    async def never(request):await asyncio.Event().wait()
    h=await runtime_setup(monkeypatch,handler=never);monkeypatch.setattr(h.X,'WAIT_SECONDS',0.01)
    result=await h.runtime().execute_admitted_once(h.first.run,h.first.claim_token)
    assert result.run.state=='unknown' and result.run.unknown_reason=='TIMEOUT' and result.run.held_nano==10000
    assert asyncio.current_task().cancelling()==0 and len(h.sent)==1


async def test_runtime_delayed_fresh_ACK_cannot_extend_original_deadline(monkeypatch):
    h=await runtime_setup(monkeypatch);original=h.session.commit;calls=0
    async def delayed():
        nonlocal calls
        calls+=1;await original()
        if calls==2:h.store.stamp=h.first.run.deadline_at+timedelta(seconds=1)
    h.session.commit=AsyncMock(side_effect=delayed)
    with pytest.raises(D.TechnicalCompletionError):await h.runtime().execute_admitted_once(h.first.run,h.first.claim_token)
    assert not h.sent and h.store.row.state=='claimed' and h.store.row.held_nano==10000


async def test_runtime_late_client_return_cannot_escape_shorter_waiter_deadline(monkeypatch):
    import httpx
    clock=[0.0]
    async def late(request):
        clock[0]=4.0  # model a delayed timeout callback while synchronous work returns
        return httpx.Response(200,json=h.response)
    h=await runtime_setup(monkeypatch,handler=late)
    result=await h.runtime(clock=lambda:clock[0]).execute_admitted_once(h.first.run,h.first.claim_token)
    assert result.run.state=='unknown' and result.run.unknown_reason=='TIMEOUT'
    assert h.ledger.root is None and h.store.row.held_nano==10000 and len(h.sent)==1

# CF053: explicit artificial policy/configuration, never operational settings.
from src.modules.technical.domain import provider_execution as P

def provider_configuration(policy=None,**changes):
    return P.Configuration.parse(dict(schema_version=P.SCHEMA,policy=(policy or D.Policy.parse(policy_values())).data(),
        counter={'free':True,'mapping':'technical.responses.model-input.v1','version':'synthetic.v1','provenance_sha256':'b'*64,'evidence_sha256':'c'*64},
        caps={'request':4096,'count':4096,'generation':4096},ai_origin='https://ai.invalid',authority_origin='https://backend.invalid',cache_mode='none',trace_mode='none')|changes)

async def provider_admitted(monkeypatch):
    session,p,policy,intent,store=setup(monkeypatch);cfg=provider_configuration(policy)
    first=await S.TechnicalAdmissionService(session,principal=p,policy=policy).admit_provider('provider-key',intent,cfg)
    from db.models.technical.execution_admission import TechnicalAnalysisRun
    for column in TechnicalAnalysisRun.__table__.columns:
        if not hasattr(store.row,column.name):setattr(store.row,column.name,None)
    store.row._completion_period=store.period
    return session,p,policy,intent,store,cfg,first

async def provider_claimed(monkeypatch):
    values=await provider_admitted(monkeypatch);session,p,policy,intent,store,cfg,first=values
    claim=await S.TechnicalAdmissionService(session,principal=p,policy=policy).dispatch_provider_claim(first.run,first.claim_token,cfg)
    return (*values,claim)

async def test_CF053_new_spec_same_namespace_once_grant_replay_never_reissues(monkeypatch):
    session,p,policy,intent,store,cfg,first,claim=await provider_claimed(monkeypatch)
    assert first.run.spec_sha256==P.SPEC_SHA256 and claim.newly_claimed and len(claim.grant)==64
    body=P.parse_execution(P.decode(claim.execution_json),cfg)
    assert body['control_sha256']==store.row.execution_control_sha256
    assert hashlib.sha256(claim.grant.encode()).digest()==store.row.execution_grant_digest
    second=await S.TechnicalAdmissionService(session,principal=p,policy=policy).dispatch_provider_claim(claim.run,first.claim_token,cfg)
    assert not second.newly_claimed and second.grant is None and second.execution_json is None
    assert store.period.request_count==1 and store.period.reserved_nano==10000
    with pytest.raises(D.TechnicalAdmissionError,match='IDEMPOTENCY_CONFLICT'):
        await S.TechnicalAdmissionService(session,principal=p,policy=policy).admit('provider-key',intent)
    assert claim.grant not in repr(claim)

@pytest.mark.parametrize('cap',[None,True,False,'10',1.0,0,-1,2097153])
def test_CF053_configuration_caps_strict(cap):
    with pytest.raises(P.ExecutionInvalid):provider_configuration(caps={'request':cap,'count':4096,'generation':4096})

@pytest.mark.parametrize('raw',['http://ai.invalid','https://u:p@ai.invalid','https://ai.invalid/path','https://ai.invalid?query=1','https://ai.invalid#x'])
def test_CF053_origins_are_closed_HTTPS(raw):
    with pytest.raises(P.ExecutionInvalid):provider_configuration(ai_origin=raw)

def test_CF053_mirror_source_exact_except_existing_relative_boundary_import():
    backend=(ROOT/'backend/src/modules/technical/domain/provider_execution.py').read_text()
    ai=(ROOT/'ai/src/agents/technical/domain/execution_contracts.py').read_text()
    assert ai==backend.replace('.execution_boundary','.boundary_contracts')

@pytest.mark.parametrize('number_kind',['float','bool'])
async def test_CF053_old_binding_rejects_controlled_and_strict_coverage(monkeypatch,number_kind):
    from src.modules.technical.application import execution_completion as E
    from src.modules.technical.application.boundary_adapter import TechnicalBoundaryBinding,TechnicalBoundaryAdapter
    session,p,policy,intent,store,cfg,first,claim=await provider_claimed(monkeypatch)
    execution=P.decode(claim.execution_json);start=P.start_receipt(execution['control_sha256'],str(uuid4()),store.stamp.isoformat())
    store.row.execution_started_at=store.stamp;store.row.execution_executor_id=UUID(start['executor_id'])
    store.row.execution_start_json=P.canonical(start);store.row.execution_start_sha256=start['start_sha256']
    binding=E.binding_from_sql(store.row)
    old=TechnicalBoundaryBinding(binding.boundary.context,binding.boundary.report_id,binding.boundary.request_id,binding.boundary.trace_id,binding.boundary.input_json)
    synthetic=completion_response(NS(boundary=old))
    expected={k:start[k] for k in ('control_sha256','start_sha256','executor_id')}
    response=P.result(execution['boundary_request'],synthetic['data']['result'],expected)
    controlled=TechnicalBoundaryAdapter(binding.boundary).validate_and_freeze(response)
    assert controlled.result_schema==P.SCHEMA
    with pytest.raises(ValueError):TechnicalBoundaryAdapter(old).validate_and_freeze(response)
    # Every integer count has canonical integer identity; bool/float are not aliases.
    def alter(value):
        if type(value) is dict:
            for k,v in value.items():
                if type(v) is int and (number_kind=='float' or v in {0,1}):value[k]=float(v) if number_kind=='float' else bool(v);return True
                if alter(v):return True
        if type(value) is list:
            for v in value:
                if alter(v):return True
        return False
    bad=copy.deepcopy(response);assert alter(bad['data']['coverage'])
    with pytest.raises(P.ExecutionInvalid):P.validate_controlled(bad,execution['boundary_request'],expected)


def evidence_record(control,**changes):
    return dict(ordinal=1,analysis_id=control['analysis_id'],attempt_id=control['attempt_id'],policy_sha256=control['policy_sha256'],
        request_sha256='d'*64,prompt_sha256='e'*64,projection_sha256='f'*64,model='synthetic-model',service_tier='default',input_token_cap=100,output_token_cap=50,held_nano=2000,
        entered=True,response_received=True,usage=[1,1,2],estimated_nano=30,response_model='match',response_tier='match',text_accepted=True,reason=None,elapsed_ms=1,
        count_entered=True,count_response_received=True,count_validated=True,counted_input_tokens=1)|changes

async def test_CF053_usage_overflow_preserves_usage_failure_without_false_success(monkeypatch):
    *_,cfg,first,claim=await provider_claimed(monkeypatch)
    execution=P.decode(claim.execution_json);control=execution['control'];start=P.start_receipt(execution['control_sha256'],str(uuid4()),control['started_at'])
    value=dict(schema_version='technical.usage.v1',analysis_id=control['analysis_id'],attempt_id=control['attempt_id'],policy_sha256=control['policy_sha256'],
        control_sha256=start['control_sha256'],start_sha256=start['start_sha256'],executor_id=start['executor_id'],outcome='failed',records=[])
    huge=P.MAX//10+1
    row=evidence_record(control,usage=[huge,0,huge],estimated_nano=None,text_accepted=False,reason='USAGE_LIMIT_MISMATCH')
    value['records']=[row];assert P.evidence(value,cfg,control,start)==value
    for field in ('response_model','response_tier'):
        value['records']=[evidence_record(control,**{field:'mismatch'})]
        with pytest.raises(P.ExecutionInvalid):P.evidence(value,cfg,control,start)
    value['records']=[evidence_record(control,request_sha256=int('1'*64))]
    with pytest.raises(P.ExecutionInvalid):P.evidence(value,cfg,control,start)

@pytest.mark.parametrize('raw,expected',[(True,True),(False,False),('true',True),('false',False),('TRUE',True)])
def test_CF053_enable_is_explicit_delayed_parser(raw,expected):
    from src.modules.technical.api.execution_authority_router import enabled
    assert enabled(raw) is expected

@pytest.mark.parametrize('raw',[None,1,'1',' true ',[],{}])
def test_CF053_enable_invalid_is_closed(raw):
    from src.modules.technical.api.execution_authority_router import enabled
    with pytest.raises(P.ExecutionInvalid):enabled(raw)

@pytest.mark.parametrize('change',['query','raw_path','method','duplicate','cookie','encoding','grant','token','length'])
def test_CF053_callback_auth_and_closed_headers_before_any_dependency(change):
    from src.modules.technical.api.execution_authority_router import authenticate_headers
    path='/internal/technical/execution/start'
    scope={'type':'http','method':'POST','path':path,'raw_path':path.encode(),'query_string':b'',
        'headers':[(b'content-type',b'application/json'),(b'x-technical-authority-token',b'b'*32),(b'x-technical-execution-grant',b'f'*64)]}
    if change=='query':scope['query_string']=b'x=1'
    elif change=='raw_path':scope['raw_path']=b'/internal/technical/execution/%73tart'
    elif change=='method':scope['method']='GET'
    elif change=='duplicate':scope['headers'].append((b'x-technical-authority-token',b'b'*32))
    elif change=='cookie':scope['headers'].append((b'cookie',b'session=private'))
    elif change=='encoding':scope['headers'].append((b'content-encoding',b'gzip'))
    elif change=='grant':scope['headers'][-1]=(b'x-technical-execution-grant',b'e'*63)
    elif change=='token':scope['headers'][1]=(b'x-technical-authority-token',b'c'*32)
    else:scope['headers'].append((b'content-length',b'8193'))
    with pytest.raises(P.ExecutionInvalid):authenticate_headers(scope,'b'*32)

async def test_CF053_bad_ready_precedes_any_admission_or_claim(monkeypatch):
    from src.modules.technical.application.execution_runtime import TechnicalExecutionRuntime
    from src.shared.infrastructure.clients.ai_client import AIClient,AIUnavailableError
    from fastapi import FastAPI
    from starlette.responses import JSONResponse
    app=FastAPI();seen=[]
    @app.post('/internal/technical/execution/ready')
    async def ready():seen.append(True);return JSONResponse({'ready':True})
    session,p,policy,intent,store=setup(monkeypatch);cfg=provider_configuration(policy)
    import httpx
    client=AIClient('https://ai.invalid',60,httpx.ASGITransport(app=app),execution_token='a'*32)
    runtime=TechnicalExecutionRuntime(session,principal=p,client=client,policy=policy,enabled=True)
    with pytest.raises(AIUnavailableError):await runtime.admit_provider_once('key',intent,cfg)
    assert seen==[True] and store.row is None and store.period.request_count==0
    session.commit.assert_not_awaited()

def test_CF053_spec_CHECK_SQL_compilation_retains_exact_boolean_bytes():
    from sqlalchemy import Table,MetaData,Column,Text,CheckConstraint
    from sqlalchemy.schema import CreateTable
    from sqlalchemy.dialects.postgresql import dialect
    from db.models.technical import execution_admission as model
    table=Table('cf053_literal_probe',MetaData(),Column('spec_json',Text),Column('spec_sha256',Text),Column('operation',Text),CheckConstraint(model.RUN_CHECKS['spec']))
    compiled=str(CreateTable(table).compile(dialect=dialect()))
    # SQLAlchemy text bind syntax must never consume :true/:false in a JSON
    # literal. The server receives exact canonical bytes, not NULL substitution.
    assert '"provider_authority"NULL' not in compiled and '"settlement"NULL' not in compiled
    assert P.SPEC_JSON.encode().hex() in compiled

async def test_CF053_late_ready_fixed5_has_admission_and_claim0(monkeypatch):
    from src.modules.technical.application.execution_runtime import TechnicalExecutionRuntime
    from src.shared.infrastructure.clients import ai_client as C
    from fastapi import FastAPI
    from starlette.responses import JSONResponse
    import httpx
    session,p,policy,intent,store=setup(monkeypatch);cfg=provider_configuration(policy);clock=NS(value=0.0)
    monkeypatch.setattr(C,'time',NS(monotonic=lambda:clock.value));app=FastAPI();seen=[]
    @app.post('/internal/technical/execution/ready')
    async def ready():
        seen.append(True);clock.value=6
        return JSONResponse({'schema_version':P.SCHEMA,'configuration':cfg.data(),'spec_sha256':P.SPEC_SHA256,'ready':True})
    client=C.AIClient('https://ai.invalid',60,httpx.ASGITransport(app=app),execution_token='a'*32)
    runtime=TechnicalExecutionRuntime(session,principal=p,client=client,policy=policy,enabled=True)
    with pytest.raises(C.AITimeoutError):await runtime.admit_provider_once('late-key',intent,cfg)
    assert seen==[True] and store.row is None and store.period.request_count==0
    session.commit.assert_not_awaited()

async def test_CF053_callback_cancellation_closes_only_its_owned_dependency(monkeypatch):
    from fastapi import FastAPI
    import httpx
    from src.modules.technical.api.execution_authority_router import make_router
    from src.modules.technical.application.execution_authority_service import TechnicalExecutionAuthority
    events=[];entered=asyncio.Event();session=Session()
    async def sessions():
        try:events.append('opened');yield session
        finally:events.append('closed')
    async def start(self,*args):
        assert self.session is session;entered.set();await asyncio.Future()
    monkeypatch.setattr(TechnicalExecutionAuthority,'start',start)
    app=FastAPI();app.include_router(make_router(session_factory=sessions,configuration=provider_configuration,token=lambda:'b'*32))
    body={'schema_version':P.SCHEMA,'analysis_id':str(uuid4()),'control_sha256':'c'*64,'executor_id':str(uuid4())}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='https://backend.invalid') as client:
        task=asyncio.create_task(client.post('/internal/technical/execution/start',json=body,headers={'X-Technical-Authority-Token':'b'*32,'X-Technical-Execution-Grant':'f'*64}))
        await entered.wait();task.cancel()
        with pytest.raises(asyncio.CancelledError):await task
    assert events==['opened','closed']
    session.commit.assert_not_awaited();session.flush.assert_not_awaited()

async def test_CF053_late_ready_cleanup_has_admission0(monkeypatch):
    from src.modules.technical.application.execution_runtime import TechnicalExecutionRuntime
    from src.shared.infrastructure.clients import ai_client as C
    from fastapi import FastAPI
    from starlette.responses import JSONResponse
    import httpx
    session,p,policy,intent,store=setup(monkeypatch);cfg=provider_configuration(policy);clock=NS(value=0.0)
    app=FastAPI();seen=[]
    @app.post('/internal/technical/execution/ready')
    async def ready():
        seen.append(True);return JSONResponse({'schema_version':P.SCHEMA,'configuration':cfg.data(),'spec_sha256':P.SPEC_SHA256,'ready':True})
    class DelayedClose:
        def __init__(self,**kwargs):self.inner=httpx.AsyncClient(**kwargs)
        async def __aenter__(self):return await self.inner.__aenter__()
        async def __aexit__(self,*args):
            result=await self.inner.__aexit__(*args);clock.value=6;return result
    monkeypatch.setattr(C,'httpx',NS(AsyncClient=DelayedClose,ASGITransport=httpx.ASGITransport,TimeoutException=httpx.TimeoutException))
    monkeypatch.setattr(C,'time',NS(monotonic=lambda:clock.value))
    client=C.AIClient('https://ai.invalid',60,httpx.ASGITransport(app=app),execution_token='a'*32)
    runtime=TechnicalExecutionRuntime(session,principal=p,client=client,policy=policy,enabled=True)
    with pytest.raises(C.AITimeoutError):await runtime.admit_provider_once('cleanup-late-key',intent,cfg)
    assert seen==[True] and store.row is None and store.period.request_count==0
    session.commit.assert_not_awaited()


def client_tls_context():
    import ssl
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



async def test_Technical_TLS_snapshot_uses_owned_CA_after_caller_context_mutation(monkeypatch):
    import ssl,httpx
    from src.shared.infrastructure.clients import ai_client as C
    from fastapi import FastAPI
    from starlette.responses import JSONResponse
    session,p,policy,intent,store=setup(monkeypatch);cfg=provider_configuration(policy)
    context=client_tls_context();app=FastAPI();seen=[];verified=[]
    @app.post('/internal/technical/execution/ready')
    async def ready():
        seen.append(True)
        return JSONResponse({'schema_version':P.SCHEMA,'configuration':cfg.data(),'spec_sha256':P.SPEC_SHA256,'ready':True})
    original=httpx.AsyncClient
    class CheckingClient:
        def __init__(self,**kwargs):
            owned=kwargs['verify'];assert owned is not context
            assert owned.verify_mode==ssl.CERT_REQUIRED and owned.check_hostname is True
            assert kwargs['trust_env'] is False and kwargs['follow_redirects'] is False
            verified.append(owned);self.inner=original(**kwargs)
        async def __aenter__(self):
            value=await self.inner.__aenter__()
            context.check_hostname=False;context.verify_mode=ssl.CERT_NONE
            assert verified[-1].verify_mode==ssl.CERT_REQUIRED and verified[-1].check_hostname is True
            return value
        async def __aexit__(self,*args):return await self.inner.__aexit__(*args)
    client=C.AIClient('https://ai.invalid',60,httpx.ASGITransport(app=app),execution_token='a'*32,technical_tls_context=context)
    monkeypatch.setattr(C.httpx,'AsyncClient',CheckingClient)
    captured=await client.technical_execution_ready(cfg)
    assert len(verified)==len(seen)==1 and captured.owned_tls is verified[0]
    with pytest.raises(C.AIUnavailableError):await client.technical_execution_ready(cfg)
    assert len(seen)==1 and store.row is None


@pytest.mark.parametrize('kind',['empty','weak'])
def test_Technical_TLS_invalid_context_never_opens_HTTP(kind):
    import ssl,httpx
    from src.shared.infrastructure.clients import ai_client as C
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    if kind=='weak':context.check_hostname=False;context.verify_mode=ssl.CERT_NONE
    with pytest.raises(C.AIUnavailableError,match='^Technical execution unavailable$'):
        C.AIClient('https://ai.invalid',60,execution_token='a'*32,technical_tls_context=context)


async def test_Supervisor_technical_service_passes_only_server_owned_TLS_context(monkeypatch):
    import httpx
    from fastapi import FastAPI
    from starlette.requests import Request
    from src.modules.supervisor.api import router as core
    session,p,policy,intent,store=setup(monkeypatch);cfg=provider_configuration(policy)
    app=FastAPI();context=client_tls_context();app.state.technical_execution_tls_context=context;auth=[]
    async def principal(request,db,*,mutation):
        assert db is session;auth.append(mutation);return p
    monkeypatch.setattr(core,'request_principal',principal)
    for name,value in dict(AI_SERVICE_URL=cfg.data()['ai_origin'],TECHNICAL_EXECUTION_ENABLED=True,
        TECHNICAL_EXECUTION_CONFIG=cfg.text,TECHNICAL_EXECUTION_AI_SERVICE_TOKEN='a'*32,
        TECHNICAL_EXECUTION_AUTHORITY_TOKEN='b'*32).items():monkeypatch.setattr(core.settings,name,value)
    request=Request({'type':'http','method':'POST','app':app,'state':{'core_planning_deadline':asyncio.get_running_loop().time()+15}})
    service=await core.technical_service(request,session)
    snapshot=service.client._technical_execution_configuration(cfg)
    assert snapshot.tls_context is context and snapshot.owned_tls is not context and auth==[True]
    assert store.row is None and store.period.request_count==0
    del app.state.technical_execution_tls_context
    service=await core.technical_service(request,session)
    assert service.client._technical_execution_configuration(cfg).tls_context is None
    assert auth==[True,True]
