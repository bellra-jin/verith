"""Pure engine and mocked transaction boundaries, separate from actual PG checks."""
import asyncio
import ast
import copy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql
from src.modules.flow.domain import fake_execution as domain
from src.modules.flow.domain import input_snapshot as inputs
from src.modules.flow.application import fake_execution_service as service
from src.modules.flow.infrastructure import fake_execution_repository as repository
from src.modules.flow.api.run_schemas import FlowAdmissionRequest
from src.modules.auth.application.session_service import Principal, AuthenticationRequired


def setup_input(fixture="flow.synthetic.full20"):
    request = FlowAdmissionRequest(ticker="005930", question="CF007", as_of="2026-11-08T00:00:00Z", idempotency_key="unit")
    run = SimpleNamespace(id=uuid4(), owner_user_id=uuid4(), admission_request_id=uuid4(), attempt_id=uuid4(),
        request_contract_version=1, request_input=request.normalized_input(), input_fingerprint=request.input_fingerprint(),
        operation="flow", admission_mode="receipt_only", execution_status="pending", storage_status="not_stored")
    text = inputs.build(run, fixture)
    snap = SimpleNamespace(id=uuid4(), run_id=run.id, owner_user_id=run.owner_user_id, sealed_at=datetime.now(UTC),
                          contract_version=1, mode="synthetic_only", input_json=text, input_sha256=inputs.digest(text))
    return run, snap, inputs.read_seal(snap, run)


def execution(seal, **changes):
    start = datetime.now(UTC)
    return SimpleNamespace(id=uuid4(), input_snapshot_id=seal.id, contract_version=1, engine_id=domain.ENGINE_ID,
        claim_digest=b"x"*32, status="running", started_at=start, deadline_at=start+timedelta(seconds=10),
        finished_at=None, result_json=None, result_sha256=None, error_code=None, **changes)


@pytest.mark.parametrize("fixture,count", [("flow.synthetic.full20",20), ("flow.synthetic.short4",4)])
async def test_real_pure_engine_numbers_units_dates_and_independent_artifact(fixture,count):
    _, _, seal = setup_input(fixture); identity=uuid4()
    result=await domain.fake_engine(seal,identity)
    assert result['row_count']==count and result['totals']==dict(individual=-50000*count,foreign=40000*count,institution=10000*count,trading_value=1000000*count)
    assert result['quantity_unit']=='share' and result['trading_value_unit']=='KRW'
    assert result['end_date']=='2026-11-08' and result['synthetic'] is True
    assert result['source_reference']==seal.body['source_receipt']['reference']
    text=domain.result_text(result,seal,identity)
    result['totals']['foreign']=0
    assert domain.validate_result(text,seal,identity)['totals']['foreign']==40000*count


@pytest.mark.parametrize("key,value", [("row_count",20.0),("row_count",True),("contract_version",True),
    ("execution_id",str(uuid4())),("input_snapshot_id",str(uuid4())),("input_sha256","0"*64),
    ("ticker","000660"),("requested_as_of","2026-11-09T00:00:00Z"),("quantity_unit","KRW"),
    ("synthetic",False),("mode","real"),("engine_id","other"),("notice","\0"),("notice","\ud800"),
    ("extra",1),("row_count",float('nan'))])
async def test_result_schema_and_input_relationship_strict(key,value):
    _,_,seal=setup_input();identity=uuid4();result=await domain.fake_engine(seal,identity);result[key]=value
    with pytest.raises(domain.FakeExecutionError):domain.result_text(result,seal,identity)


@pytest.mark.parametrize("text", ['{}','null','{"x":1,"x":2}','{"x":NaN}','[]','{"x": Infinity}','"'+'x'*131073+'"'])
def test_result_invalid_serialization(text):
    _,_,seal=setup_input()
    with pytest.raises(domain.FakeExecutionError):domain.validate_result(text,seal,uuid4())


def arrange(monkeypatch):
    run,snap,seal=setup_input();row=execution(seal)
    principal=Principal(run.owner_user_id,uuid4(),datetime.now(UTC),b"p"*32)
    session=SimpleNamespace(commit=AsyncMock(),rollback=AsyncMock())
    auth=AsyncMock();lock=AsyncMock(return_value=run);read=AsyncMock(return_value=snap)
    monkeypatch.setattr(service,"validate_principal",auth)
    monkeypatch.setattr(service.inputs,"lock_run",lock);monkeypatch.setattr(service.inputs,"get_owned",read)
    get=AsyncMock(side_effect=[None,row]);claim=AsyncMock(return_value=row)
    async def do_claim(s,identity,input_id,claim_digest):
        row.id, row.claim_digest=identity,claim_digest
        return row
    claim.side_effect=do_claim
    async def finalize(s,r,**kw):
        if kw.get('expired'):return None
        r.status=kw['status'];r.result_json=kw['result_json'];r.result_sha256=kw['result_sha256'];r.error_code=kw['error_code'];r.finished_at=datetime.now(UTC)
        return r
    final=AsyncMock(side_effect=finalize)
    monkeypatch.setattr(repository,"get_owned",get);monkeypatch.setattr(repository,"claim",claim);monkeypatch.setattr(repository,"finalize",final)
    engine=AsyncMock(wraps=domain.fake_engine);monkeypatch.setattr(service,"fake_engine",engine)
    return run,seal,row,session,principal,auth,lock,get,claim,final,engine


@pytest.mark.parametrize("opt",[False,1,0,"true",None,{},[]])
async def test_opt_in_is_exact_true_before_auth_or_any_grant(monkeypatch,opt):
    run,seal,row,session,p,auth,lock,get,claim,final,engine=arrange(monkeypatch)
    obj=service.FakeExecutionService(session,principal=p)
    with pytest.raises(domain.FakeExecutionError) as caught:await obj.execute_once(run.id,allow_fake=opt)
    assert caught.value.code=='invalid'
    auth.assert_not_awaited();claim.assert_not_awaited();engine.assert_not_awaited()
    with pytest.raises(TypeError):await obj.execute_once(run.id)


async def test_grant_commit_engine_terminal_commit_replay_and_read_no_call(monkeypatch):
    run,seal,row,session,p,auth,lock,get,claim,final,engine=arrange(monkeypatch)
    order=[]
    auth.side_effect=lambda *a,**kw:order.append('auth_SHARE')
    lock.side_effect=lambda *a:(order.append('run_lock'),run)[1]
    session.commit.side_effect=lambda:order.append('commit')
    async def counted(*args):
        order.append('engine');return await domain.fake_engine(*args)
    engine.side_effect=counted
    obj=service.FakeExecutionService(session,principal=p)
    first=await obj.execute_once(run.id,allow_fake=True)
    assert first.status=='succeeded' and order.index('commit')<order.index('engine')<len(order)-1
    assert order[:2]==['auth_SHARE','run_lock'] and session.commit.await_count==2
    get.side_effect=None;get.return_value=row
    monkeypatch.setattr(service,"fake_engine",AsyncMock(side_effect=AssertionError('reader called engine')))
    assert await obj.get(run.id)==await obj.execute_once(run.id,allow_fake=True)==first
    body=first.body;body['totals']['foreign']=0
    assert first.body['totals']['foreign']==800000
    assert not hasattr(first,'claim_digest') and 'claim_digest' not in str(first)


@pytest.mark.parametrize("stage",[1,2])
async def test_commit_failure_or_lost_ACK_never_returns_success_or_reinvokes(monkeypatch,stage):
    run,seal,row,session,p,auth,lock,get,claim,final,engine=arrange(monkeypatch)
    commits=0
    async def commit():
        nonlocal commits
        commits+=1
        if commits==stage:raise OSError('synthetic-sensitive-canary')
    session.commit.side_effect=commit
    with pytest.raises(domain.FakeExecutionError) as caught:
        await service.FakeExecutionService(session,principal=p).execute_once(run.id,allow_fake=True)
    assert caught.value.code=='unavailable' and str(caught.value)=='Flow fake execution: unavailable'
    assert caught.value.__cause__ is None and caught.value.__suppress_context__
    assert engine.await_count==(0 if stage==1 else 1)
    session.rollback.assert_awaited_once()
    # ACK distinction is real PG evidence; these mocks assert only control flow.


@pytest.mark.parametrize("failure,expected",[('engine','fake_failed'),('invalid','result_invalid'),('timeout','coroutine_timeout')])
async def test_fake_error_bad_result_and_one_second_cooperative_timeout(monkeypatch,failure,expected):
    run,seal,row,session,p,auth,lock,get,claim,final,engine=arrange(monkeypatch)
    if failure=='engine':engine.side_effect=RuntimeError('sensitive-canary')
    elif failure=='invalid':engine.return_value={};engine._mock_wraps=None
    else:
        async def slow(*args):await asyncio.Event().wait()
        engine.side_effect=slow
    result=await service.FakeExecutionService(session,principal=p).execute_once(run.id,allow_fake=True)
    assert result.error_code==expected and result.body is None and engine.await_count==1


async def test_get_expiration_and_wrong_claim_fence_never_execute(monkeypatch):
    run,seal,row,session,p,auth,lock,get,claim,final,engine=arrange(monkeypatch)
    get.side_effect=None;get.return_value=row
    row.started_at-=timedelta(seconds=20);row.deadline_at-=timedelta(seconds=20)
    async def expire(s,r,**kw):
        assert kw=={'expired':True};r.status='timed_out';r.error_code='deadline_expired';r.finished_at=datetime.now(UTC);return r
    final.side_effect=expire
    obj=service.FakeExecutionService(session,principal=p)
    with pytest.raises(domain.FakeExecutionError) as caught:await obj._finish(run.id,row.id,b'w'*32,('succeeded','{}',None))
    assert caught.value.code=='fence';final.assert_not_awaited()
    result=await obj.get(run.id);assert result.status=='timed_out' and result.body is None
    engine.assert_not_awaited();claim.assert_not_awaited()


async def test_auth_invalid_missing_and_source_corruption_fail_closed(monkeypatch):
    run,seal,row,session,p,auth,lock,get,claim,final,engine=arrange(monkeypatch)
    auth.side_effect=AuthenticationRequired()
    with pytest.raises(domain.FakeExecutionError) as caught:await service.FakeExecutionService(session,principal=p).get(run.id)
    assert caught.value.code=='auth_required'
    auth.side_effect=None;lock.return_value=None
    with pytest.raises(domain.FakeExecutionError) as caught:await service.FakeExecutionService(session,principal=p).get(run.id)
    assert caught.value.code=='not_found'
    lock.return_value=run;run.input_fingerprint='0'*64
    with pytest.raises(domain.FakeExecutionError) as caught:await service.FakeExecutionService(session,principal=p).get(run.id)
    assert caught.value.code=='corrupt'
    claim.assert_not_awaited();engine.assert_not_awaited()


async def test_exact_sql_owner_unique_fence_and_separate_deadline_predicates():
    sql=[]
    async def scalar(statement):sql.append(str(statement.compile(dialect=postgresql.dialect())))
    session=SimpleNamespace(scalar=scalar)
    await repository.get_owned(session,uuid4(),uuid4())
    await repository.claim(session,uuid4(),uuid4(),b'x'*32)
    r=SimpleNamespace(id=uuid4(),input_snapshot_id=uuid4())
    await repository.finalize(session,r,claim_digest=b'x'*32,status='failed',error_code='fake_failed')
    await repository.finalize(session,r,expired=True)
    assert 'JOIN flow_runs' in sql[0] and 'flow_runs.owner_user_id =' in sql[0] and 'FOR UPDATE OF flow_fake_executions' in sql[0]
    assert 'ON CONFLICT ON CONSTRAINT uq_flow_fake_execution_input DO NOTHING' in sql[1]
    assert sql[1].count('clock_timestamp()')==1 and 'MATERIALIZED' in sql[1]
    assert 'claim_digest =' in sql[2] and 'finished < flow_fake_executions.deadline_at' in sql[2]
    assert 'finished >= flow_fake_executions.deadline_at' in sql[3]


def checked_target_guard(guard):
    expected=ast.parse('if target not in {"head", "c6001a7e0001", "c15001a7e0001"}:\n'
                       '    raise ValueError("Unsupported owned migration target")').body[0]
    # Full shape equality: no additional comparator, call, body or else can run.
    assert ast.dump(guard)==ast.dump(expected)
    return guard


@pytest.mark.parametrize('mutation',['call','else','comparator'])
def test_migration_gate_source_drift_rejected_before_execution(mutation):
    source=(Path(__file__).resolve().parents[2]/'scripts/cf002_interactive_login.py').read_text()
    tree=ast.parse(source)
    migrate=next(n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='migrate_owned')
    guard=copy.deepcopy(migrate.body[0])
    if mutation=='call':guard.body.append(ast.parse("open('unapproved')").body[0])
    elif mutation=='else':guard.orelse=[ast.Pass()]
    else:
        guard.test.ops.append(ast.Eq());guard.test.comparators.append(ast.Constant(True))
    with pytest.raises(AssertionError):checked_target_guard(guard)


def test_migration_and_wiring_are_internal_only():
    root=Path(__file__).resolve().parents[2]
    source=(root/'scripts/cf002_interactive_login.py').read_text()
    import ast
    tree=ast.parse(source)
    migrate=next(n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='migrate_owned')
    guard=checked_target_guard(migrate.body[0])
    assert isinstance(guard,ast.If) and isinstance(guard.test,ast.Compare)
    assert isinstance(guard.test.ops[0],ast.NotIn) and guard.test.left.id=='target'
    assert ast.literal_eval(guard.test.comparators[0])=={'head','c6001a7e0001','c15001a7e0001'}
    assert isinstance(guard.body[0],ast.Raise) and guard.body[0].exc.func.id=='ValueError'
    assert ast.unparse(migrate.body[1])=='await proof.preflight()'
    # Evaluate the actual closed target gate without importing/spawning the DB runner.
    prefix=ast.FunctionDef(name='target_allowed',args=ast.arguments(posonlyargs=[],args=[ast.arg(arg='target')],
        kwonlyargs=[],kw_defaults=[],defaults=[]),body=[guard,ast.Return(value=ast.Constant(True))],decorator_list=[])
    env={'__builtins__':{'ValueError':ValueError}}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[prefix],type_ignores=[])),'<fixed-owned-target-gate>','exec'),env)
    for target in ('head','c6001a7e0001','c15001a7e0001'):assert env['target_allowed'](target) is True
    for target in ('base','c7001a7e0001','../alembic.ini','head; DROP TABLE flow_runs',None):
        with pytest.raises(ValueError,match='^Unsupported owned migration target$'):env['target_allowed'](target)
    assert 'migrate_owned(second_proof, target="c6001a7e0001")' in source
    assert source.index('verify_fake_execution(proof)')<source.index('project = prepare_projects')
    migration=(root/'db/migrations/versions/20261108_c7001a7e0001_flow_fake_execution.py').read_text()
    assert '"flow_runs", "flow_input_snapshots", "flow_fake_executions"' in migration
    assert 'OLD.status' in migration and "TG_OP = 'DELETE'" in migration and 'clock_timestamp() >= NEW.deadline_at' in migration
    for path in ['src/api/main.py','src/modules/flow/domain/execution.py','src/modules/flow/api/run_schemas.py']:
        assert 'fake_execution' not in (root/path).read_text()
