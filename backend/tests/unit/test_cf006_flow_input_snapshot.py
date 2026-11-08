"""Pure/domain and mocked service evidence; not PostgreSQL/auth integration."""
import ast
from datetime import UTC, datetime
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql
from src.modules.auth.application.session_service import AuthenticationRequired, Principal
from src.modules.flow.api.run_schemas import FlowAdmissionRequest
from src.modules.flow.domain import input_snapshot as domain
from src.modules.flow.application import input_preparation_service as service
from src.modules.flow.infrastructure import input_snapshot_repository as repository


def row():
    request = FlowAdmissionRequest(ticker="005930", question=" synthetic ", as_of="2026-11-08T09:00:00+09:00", idempotency_key="fixed")
    return SimpleNamespace(id=uuid4(), owner_user_id=uuid4(), admission_request_id=uuid4(), attempt_id=uuid4(),
        request_contract_version=1, request_input=request.normalized_input(), input_fingerprint=request.input_fingerprint(),
        operation="flow", admission_mode="receipt_only", execution_status="pending", storage_status="not_stored")


def snapshot(source, text=None):
    text = text or domain.build(source, "flow.synthetic.full20")
    return SimpleNamespace(id=uuid4(), run_id=source.id, owner_user_id=source.owner_user_id, sealed_at=datetime.now(UTC),
        contract_version=1, mode="synthetic_only", input_json=text, input_sha256=domain.digest(text))


def fixed(error, code):
    assert isinstance(error, domain.SnapshotError) and error.code == code
    assert str(error) == "Flow input snapshot: " + code
    assert error.__cause__ is None and error.__suppress_context__


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), {1: "x"}, {"a": object()}, (1,), "\0", "\ud800", "\udfff", "x" * (domain.MAX_BYTES + 1)])
def test_canonical_rejects_non_json_and_storage_boundaries(value):
    with pytest.raises(domain.SnapshotError):
        domain.canonical(value)


@pytest.mark.parametrize("text", ['{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}', '{"a": 1}', 'null', '{}', '[]', '{', '"x"'])
def test_strict_body_rejects_duplicate_nonfinite_noncanonical_and_shape(text):
    with pytest.raises(domain.SnapshotError):
        domain.validate(text)


def test_json_distinctions_and_size():
    values = [0, False, None, "0", {}, {"x": None}, {"x": 0}]
    assert len({domain.canonical(v) for v in values}) == len(values)
    assert domain.canonical("가" * 43690)  # 131072 UTF-8 bytes including quotes.
    with pytest.raises(domain.SnapshotError):
        domain.canonical("가" * 43691)


@pytest.mark.parametrize("fixture,count", [("flow.synthetic.full20", 20), ("flow.synthetic.short4", 4)])
def test_determinism_dates_synthetic_units_no_execution_and_fresh_tree(fixture, count):
    source = row()
    text = domain.build(source, fixture)
    assert text == domain.build(source, fixture)
    body = domain.validate(text)
    data = body["fixture"]["data"]
    assert len(data["rows"]) == count and data["rows"][-1]["date"] == "2026-11-08"
    assert data["totals"]["individual"] == -50000 * count
    assert data["quantity_unit"] == "share" and data["trading_value_unit"] == "KRW"
    assert data["published_at"] is data["observed_at"] is data["retrieved_at"] is None
    assert body["preparation_spec"] == {"version": 1, "provider": "fixture", "executable": False,
        "external_calls_allowed": 0, "max_cost": 0, "reservation_status": "not_reserved"}
    sealed = domain.read_seal(snapshot(source, text), source)
    copy = sealed.body
    copy["fixture"]["data"]["rows"][0]["individual"] = 999
    assert sealed.body == body
    assert domain.digest(text) != source.input_fingerprint


@pytest.mark.parametrize("path,value", [
    (("contract_version",), True), (("contract_version",), 1.0), (("mode",), "execute"),
    (("fixture", "version"), True), (("fixture", "version"), 1.0),
    (("fixture", "data", "totals", "foreign"), True),
    (("preparation_spec", "executable"), 0), (("preparation_spec", "max_cost"), False),
    (("preparation_spec", "external_calls_allowed"), 0.0),
    (("source_receipt", "request_contract_version"), True),
    (("source_receipt", "request", "question"), "changed"),
    (("source_receipt", "reference", "run_id"), "not-a-uuid"),
])
def test_body_schema_rejects_exact_type_and_reference_changes(path, value):
    data = domain.validate(domain.build(row(), "flow.synthetic.full20"))
    parent = data
    for key in path[:-1]:
        parent = parent[key]
    parent[path[-1]] = value
    with pytest.raises(domain.SnapshotError):
        domain.validate(domain.canonical(data))


@pytest.mark.parametrize("changes", [{"request_input": {}}, {"input_fingerprint": "0" * 64},
    {"execution_status": "running"}, {"request_contract_version": True}, {"attempt_id": uuid4()}])
def test_source_drift_is_not_resealed(changes):
    source = row(); sealed = snapshot(source)
    for name, value in changes.items():
        setattr(source, name, value)
    with pytest.raises(domain.SnapshotError) as caught:
        domain.read_seal(sealed, source)
    fixed(caught.value, "corrupt")


def arrange(monkeypatch):
    source = row()
    principal = Principal(source.owner_user_id, uuid4(), datetime.now(UTC), b"x" * 32)
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    authorize, lock, get, insert = AsyncMock(), AsyncMock(return_value=source), AsyncMock(return_value=None), AsyncMock(return_value=snapshot(source))
    monkeypatch.setattr(service, "validate_principal", authorize)
    for name, mock in (("lock_run", lock), ("get_owned", get), ("insert_snapshot", insert)):
        monkeypatch.setattr(repository, name, mock)
    return source, session, principal, authorize, lock, get, insert


async def test_prepare_auth_lock_order_commits_then_returns_stable_replay(monkeypatch):
    source, session, principal, authorize, lock, get, insert = arrange(monkeypatch)
    order = []
    authorize.side_effect = lambda *a, **k: order.append("session_SHARE")
    lock.side_effect = lambda *a: (order.append("run_lock"), source)[1]
    session.commit.side_effect = lambda: order.append("commit")
    obj = service.InputPreparationService(session, principal=principal)
    first = await obj.prepare(source.id, "flow.synthetic.full20")
    get.return_value = insert.return_value
    again = await obj.prepare(source.id, "flow.synthetic.full20")
    read = await obj.get(source.id)
    assert first == again == read and order[:3] == ["session_SHARE", "run_lock", "commit"]
    assert insert.await_count == 1 and authorize.call_args.kwargs == {"lock": True}
    session.rollback.assert_not_awaited()
    # Stored retrieval does not consult the mutable catalog.
    monkeypatch.setattr(domain, "FIXTURES", {})
    monkeypatch.setattr(domain, "SPEC", {})
    def forbidden_generator(*args):
        raise AssertionError("stored input must not regenerate")
    monkeypatch.setattr(domain, "_data", forbidden_generator)
    domain.validate(first.input_json)
    assert domain.read_seal(insert.return_value, source) == first
    assert await obj.get(source.id) == first


@pytest.mark.parametrize("kind", ["auth", "missing", "conflict", "commit", "ack", "insert", "rollback"])
async def test_fixed_failures_never_claim_rollback_proves_commit_absence(monkeypatch, kind):
    source, session, principal, authorize, lock, get, insert = arrange(monkeypatch)
    expected = "unavailable"
    if kind == "auth":
        authorize.side_effect = AuthenticationRequired(); expected = "auth_required"
    elif kind == "missing":
        lock.return_value = None; expected = "not_found"
    elif kind == "conflict":
        get.return_value = snapshot(source, domain.build(source, "flow.synthetic.short4")); expected = "conflict"
    elif kind == "insert":
        insert.side_effect = RuntimeError("synthetic-sensitive-canary")
    else:
        session.commit.side_effect = OSError("synthetic-sensitive-canary")
        if kind == "rollback":
            session.rollback.side_effect = OSError("synthetic-sensitive-canary")
    obj = service.InputPreparationService(session, principal=principal)
    with pytest.raises(domain.SnapshotError) as caught:
        await obj.prepare(source.id, "flow.synthetic.full20")
    fixed(caught.value, expected)
    session.rollback.assert_awaited_once()
    if kind == "ack":
        # Simulate a committed write with lost ACK: subsequent retrieval/replay
        # returns the persisted original, never an invented second snapshot.
        get.return_value = insert.return_value
        session.commit.side_effect = None
        recovered = await obj.get(source.id)
        assert await obj.prepare(source.id, "flow.synthetic.full20") == recovered
        assert insert.await_count == 1


async def test_invalid_arguments_precede_auth_and_wrong_principal_denied(monkeypatch):
    source, session, principal, auth, lock, get, insert = arrange(monkeypatch)
    obj = service.InputPreparationService(session, principal=principal)
    for fixture, version in [("unknown", 1), ("flow.synthetic.full20", True), ("flow.synthetic.full20", 1.0)]:
        with pytest.raises(domain.SnapshotError):
            await obj.prepare(source.id, fixture, version)
    auth.assert_not_awaited()
    with pytest.raises(domain.SnapshotError) as caught:
        await service.InputPreparationService(session, principal=None).get(source.id)
    fixed(caught.value, "auth_required")
    get.assert_not_awaited(); insert.assert_not_awaited()


async def test_conflict_loser_separate_select_and_exact_sql(monkeypatch):
    source, session, principal, auth, lock, get, insert = arrange(monkeypatch)
    stored = snapshot(source)
    get.side_effect = [None, stored]; insert.return_value = None
    assert (await service.InputPreparationService(session, principal=principal).prepare(source.id, "flow.synthetic.full20")).id == stored.id
    assert get.await_count == 2


async def test_repository_owner_scope_exact_unique_and_no_update():
    from db.models.flow.flow_run import FlowRun
    from db.models.flow.input_snapshot import FlowInputSnapshot
    statements = []
    async def capture(statement):
        statements.append(str(statement.compile(dialect=postgresql.dialect())))
    session = SimpleNamespace(scalar=capture)
    await repository.lock_run(session, uuid4(), uuid4())
    await repository.get_owned(session, uuid4(), uuid4())
    await repository.insert_snapshot(session, dict(id=uuid4(), run_id=uuid4(), owner_user_id=uuid4(), contract_version=1, mode="synthetic_only", input_json="{}", input_sha256="a"*64))
    assert "FOR UPDATE OF flow_runs" in statements[0] and "flow_runs.owner_user_id =" in statements[0]
    assert "JOIN flow_runs" in statements[1] and "flow_input_snapshots.owner_user_id =" in statements[1]
    assert "ON CONFLICT ON CONSTRAINT uq_flow_input_snapshots_run DO NOTHING" in statements[2]
    assert all("UPDATE SET" not in sql and "DELETE" not in sql for sql in statements)
    assert any(c.name == "uq_flow_runs_id_owner" for c in FlowRun.__table__.constraints)
    assert all(not column.nullable for column in FlowInputSnapshot.__table__.columns)


def test_exact_wiring_no_public_reexport_and_migration_lock_order():
    root = Path(__file__).resolve().parents[2]
    migration = (root / "db/migrations/versions/20261108_c6001a7e0001_flow_input_snapshots.py").read_text()
    ast.parse(migration)
    assert migration.index('LOCK TABLE flow_runs') < migration.index('LOCK TABLE flow_input_snapshots') < migration.index('SELECT EXISTS')
    assert 'CREATE EXTENSION' not in migration and 'DROP EXTENSION' not in migration
    for path in ["src/modules/flow/domain/execution.py", "src/modules/flow/api/run_router.py", "src/modules/flow/api/run_schemas.py", "src/api/main.py"]:
        assert "input_snapshot" not in (root / path).read_text()


@pytest.mark.parametrize("second_cleanup_fails", [False, True])
@pytest.mark.parametrize("second_check_fails", [False, True])
def test_db_only_second_cleanup_failure_preserves_exit_two(monkeypatch, second_cleanup_fails, second_check_fails):
    """Only lifecycle control is mocked; no Docker/application/PG is started."""
    from contextlib import nullcontext
    from unittest.mock import Mock
    import argparse
    import asyncio
    from contextlib import ExitStack
    from scripts import cf003_admission_check as admission
    from scripts import cf006_input_snapshot_check as checker
    import sys
    first = SimpleNamespace(resource_id="synthetic-first", receipt=None, cleanup=Mock())
    second = SimpleNamespace(resource_id="synthetic-second", receipt=None, cleanup=Mock())
    for n, owner in enumerate((first, second)):
        owner.receipt = SimpleNamespace(container_id=str(n+1)*64, created_at="synthetic-time", nonce="synthetic-sensitive-nonce")
        proof = SimpleNamespace(safe_receipt=lambda owner=owner: {"resource_id": owner.resource_id})
        owner.create = Mock(return_value=proof)
    if second_cleanup_fails:
        second.cleanup.side_effect = OSError("synthetic-sensitive-cleanup-canary")
    docker = SimpleNamespace(close=Mock())
    monkeypatch.setattr(sys, "argv", ["cf002_interactive_login.py", "--verify-flow-input-snapshot-db"])
    monkeypatch.setattr(admission, "owned_postgres_home", lambda value: nullcontext())
    monkeypatch.setattr(checker, "verify_input_snapshot", AsyncMock(return_value={"status": "passed"}))
    monkeypatch.setattr(checker, "verify_downgrade_first", AsyncMock(return_value={"status": "passed"}, side_effect=OSError("synthetic-sensitive-error") if second_check_fails else None))
    outputs = []
    # Extract only the fixed controller function, not its Google/workspace imports.
    # The function has no defaults/decorators to evaluate during compilation.
    root = Path(__file__).resolve().parents[2]
    tree = ast.parse((root / "scripts/cf002_interactive_login.py").read_text())
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    assert not main.decorator_list and not main.args.args and not main.args.defaults and main.returns is None
    forbidden = Mock(side_effect=AssertionError("DB-only reached app or port work"))
    def diagnostic(error, stage):
        return {"phase": "cf006_failure_diagnostic", "stage": stage, "error_type": "other", "frames": []}
    namespace = {"argparse": argparse, "asyncio": asyncio, "ExitStack": ExitStack,
        "signal": SimpleNamespace(SIGINT=2, SIGTERM=15, SIG_IGN=1, signal=lambda *args: None),
        "LocalDocker": lambda: docker, "OwnedPostgres": Mock(side_effect=[first, second]),
        "migrate_owned": AsyncMock(), "safe_print": outputs.append,
        "cf006_failure_diagnostic": diagnostic, "cf003_failure_diagnostic": diagnostic,
        "ensure_local_ports_free": forbidden, "prepare_projects": forbidden}
    exec(compile(ast.Module(body=[main], type_ignores=[]), "cf006-fixed-controller-main", "exec"), namespace)
    runner = SimpleNamespace(main=namespace["main"])
    if second_cleanup_fails:
        with pytest.raises(SystemExit) as caught:
            runner.main()
        assert caught.value.code == 2
        assert any(v["phase"] == "cleanup_failed" for v in outputs)
    elif second_check_fails:
        with pytest.raises(SystemExit) as caught:
            runner.main()
        assert caught.value.code == 1
    else:
        runner.main()
    failures = [v for v in outputs if v["phase"] == "cf006_failed_resource"]
    if second_cleanup_fails or second_check_fails:
        assert len(failures) == 1 and failures[0]["container_id"] == second.receipt.container_id
        assert set(failures[0]) == {"phase", "resource_id", "container_id", "created_at"}
    assert "synthetic-sensitive-nonce" not in json.dumps(outputs)
    assert "synthetic-sensitive-error" not in json.dumps(outputs)
    first.cleanup.assert_called_once(); second.cleanup.assert_called_once()
    docker.close.assert_called_once()
    assert "synthetic-sensitive-cleanup-canary" not in json.dumps(outputs)


async def test_actual_asyncpg_uuid_subclass_is_a_uuid_not_an_arbitrary_input(monkeypatch):
    from asyncpg.pgproto.pgproto import UUID as DriverUUID
    from uuid import UUID
    source, session, principal, auth, lock, get, insert = arrange(monkeypatch)
    source.id = DriverUUID(str(source.id))
    assert isinstance(source.id, UUID)
    stored = snapshot(source)
    stored.id = DriverUUID(str(stored.id))
    insert.return_value = stored
    sealed = await service.InputPreparationService(session, principal=principal).prepare(source.id, "flow.synthetic.full20")
    assert sealed.id == stored.id
    with pytest.raises(domain.SnapshotError) as caught:
        await service.InputPreparationService(session, principal=principal).get(str(source.id))
    fixed(caught.value, "invalid")
