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
    assert values['RUN_CHECKS']==model.RUN_CHECKS
    assert (values['revision'],values['down_revision'])==('c48001a7e0001','c45001a7e0001')
    run=model.TechnicalAnalysisRun.__table__
    assert not run.c.admission_session_id.foreign_keys and not run.c.planned_report_id.foreign_keys
    assert {fk.ondelete for fk in run.foreign_keys}=={'RESTRICT'}
    assert {fk.column.table.name for fk in run.foreign_keys}=={'auth_users','technical_usage_periods'}


async def test_owned_SQL_entry_rejects_non_original_proof_before_resource_or_application_use():
    from scripts.cf035_technical_owned_check import verify_technical_admission
    with pytest.raises(RuntimeError,match='^Technical admission requires original owned proof$'):
        await verify_technical_admission(NS(verify_ownership=lambda:pytest.fail('untrusted proof used')))
