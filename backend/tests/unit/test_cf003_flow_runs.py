"""CF-003 offline tests. Mocks here are never PostgreSQL/auth integration evidence."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import SQLAlchemyError

from src.modules.flow.api.run_schemas import FlowAdmissionRequest, is_run_endpoint
from src.modules.flow.domain.execution import ContractViolation, ErrorCode, FlowRunRequest, FlowRunState


def request_values(**changes):
    return dict(ticker="005930", question=" synthetic ", as_of="2026-11-08T09:00:00+09:00",
                idempotency_key=" synthetic-key ") | changes


@pytest.mark.parametrize("changes", [
    {"question": " "}, {"question": "x" * 2001}, {"question": True},
    {"question": "x\x00"}, {"question": "\ud800"}, {"idempotency_key": ""},
    {"idempotency_key": " "}, {"idempotency_key": "x" * 257},
    {"idempotency_key": "가" * 86}, {"idempotency_key": "\x00"},
    {"idempotency_key": "\udfff"}, {"idempotency_key": 1},
    {"ticker": "5930"}, {"ticker": "００５９３０"}, {"ticker": 5930},
    {"as_of": "2026-11-08T09:00:00"}, {"as_of": 1}, {"as_of": "1700000000"},
    {"as_of": "0001-01-01T00:00:00+14:00"}, {"as_of": "9999-12-31T23:59:59-14:00"},
    {"owner_user_id": str(uuid4())}, {"run_id": str(uuid4())}, {"payload": {}},
    {"client_session_id": "not-an-identity"},
])
def test_input_rejects_before_any_service_or_storage(changes):
    with pytest.raises(ValidationError):
        FlowAdmissionRequest.model_validate(request_values(**changes))


@pytest.mark.parametrize("key", ["x", "x" * 256, "가" * 85 + "x", " spaced "])
def test_limits_unicode_and_fingerprint_preserve_input(key):
    values = request_values(idempotency_key=key, question=" " + "가" * 1998 + " ")
    request = FlowAdmissionRequest.model_validate(values)
    assert request.question == values["question"]
    assert request.idempotency_key == key
    assert request.as_of == datetime(2026, 11, 8, tzinfo=UTC)
    assert request.normalized_input() == dict(ticker="005930", question=values["question"], as_of="2026-11-08T00:00:00+00:00")
    assert request.input_fingerprint() == FlowRunRequest.model_validate(values).input_fingerprint()
    other = FlowAdmissionRequest.model_validate(values | {"as_of": "2026-11-08T00:00:00Z", "idempotency_key": "other"})
    assert other.input_fingerprint() == request.input_fingerprint()


@pytest.mark.parametrize("method,path,allowed", [
    ("POST", "/api/flow/runs", True), ("GET", "/api/flow/runs/not-a-uuid", True),
    ("GET", "/api/flow/runs", False), ("POST", "/api/flow/runs/", False),
    ("GET", "/api/flow/runs/x/", False), ("GET", "/api/flow/runs/x/execute", False),
    ("GET", "/api/flow/runs-extra/x", False), ("DELETE", "/api/flow/runs/x", False),
    ("POST", "/v1/runs", False),
])
def test_exact_endpoint_matcher(method, path, allowed):
    assert is_run_endpoint(method, path) is allowed


async def test_default_gate_precedes_dependencies_and_never_redirects(monkeypatch):
    from src.api.main import app
    from db.session import get_session
    from src.shared.config import settings
    monkeypatch.setattr(settings, "FLOW_RUN_ADMISSION_ENABLED", False)
    hits = []
    async def forbidden():
        hits.append(True)
        raise AssertionError("disabled admission reached DB")
    before = dict(app.dependency_overrides)
    app.dependency_overrides[get_session] = forbidden
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:8200") as client:
            a = await client.post("/api/flow/runs", json=request_values(), headers={"x-request-id": "spoof"})
            b = await client.get("/api/flow/runs/" + str(uuid4()))
            for response in (a, b):
                assert response.status_code == 403
                assert response.json()["data"] is None
                assert response.json()["error"]["code"] == "FEATURE_UNAVAILABLE"
                assert response.json()["request_id"] != "spoof"
                assert response.headers["cache-control"] == "private, no-store"
                assert response.headers["vary"] == "Cookie, Origin"
            assert a.json()["request_id"] != b.json()["request_id"]
            for method, path in [("POST", "/api/flow/runs/"), ("GET", "/api/flow/runs/x/"), ("DELETE", "/api/flow/runs/x")]:
                r = await client.request(method, path)
                assert r.status_code == 403
                assert "location" not in r.headers
        assert not hits
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(before)


async def test_enabled_but_auth_unconfigured_never_reaches_db(monkeypatch):
    from src.api.main import app
    from src.modules.auth.api import router as auth
    from src.shared.config import settings
    monkeypatch.setattr(settings, "FLOW_RUN_ADMISSION_ENABLED", True)
    monkeypatch.setattr(auth, "configured", lambda: False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:8200") as client:
        r = await client.post("/api/flow/runs", json=request_values())
    assert r.status_code == 401 and r.json()["error"]["code"] == "AUTH_REQUIRED"
    assert r.headers["vary"] == "Cookie, Origin"


def receipt(request, **changes):
    return SimpleNamespace(id=uuid4(), admission_request_id=uuid4(), attempt_id=uuid4(),
                           execution_status="pending", storage_status="not_stored", request_contract_version=1,
                           input_fingerprint=request.input_fingerprint(), request_input=request.normalized_input(), **changes)


@pytest.mark.parametrize("replay", [False, True])
async def test_service_revalidates_session_and_commits_before_return(monkeypatch, replay):
    from src.modules.flow.application import run_service as module
    request = FlowAdmissionRequest.model_validate(request_values())
    row = receipt(request)
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    principal = SimpleNamespace(user_id=uuid4())
    authorize = AsyncMock()
    monkeypatch.setattr(module, "validate_principal", authorize)
    insert = AsyncMock(return_value=None if replay else row)
    lookup = AsyncMock(return_value=row)
    monkeypatch.setattr(module.repository, "insert_receipt", insert)
    monkeypatch.setattr(module.repository, "find_key", lookup)
    result = await module.FlowRunService(session, principal=principal).admit(request, uuid4())
    authorize.assert_awaited_once_with(session, principal, lock=True)
    session.commit.assert_awaited_once()
    assert result.run_id == row.id and result.report_id is None
    assert result.request_id == row.admission_request_id
    values = insert.await_args.args[1]
    assert values["admission_mode"] == "receipt_only"
    assert len(values["idempotency_key_digest"]) == 32
    assert "idempotency_key" not in values["request_input"]
    assert set(values["request_input"]) == {"ticker", "question", "as_of"}
    assert lookup.await_count == int(replay)
    session.rollback.assert_not_awaited()


@pytest.mark.parametrize("failure", ["input", "insert", "commit", "conflict", "missing_winner"])
async def test_service_failure_rolls_back_without_success_or_reissue(monkeypatch, failure):
    from src.modules.flow.application import run_service as module
    request = FlowAdmissionRequest.model_validate(request_values())
    row = receipt(request)
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    monkeypatch.setattr(module, "validate_principal", AsyncMock())
    insert = AsyncMock(return_value=row)
    monkeypatch.setattr(module.repository, "insert_receipt", insert)
    monkeypatch.setattr(module.repository, "find_key", AsyncMock(return_value=row))
    expected = ErrorCode.SERVICE_UNAVAILABLE
    if failure == "input":
        request.question = "bad\x00"
        expected = ErrorCode.INPUT_INVALID
    elif failure == "insert":
        insert.side_effect = SQLAlchemyError("synthetic-private-detail")
    elif failure == "commit":
        session.commit.side_effect = SQLAlchemyError("synthetic-private-detail")
    else:
        insert.return_value = None
        if failure == "conflict":
            row.request_input = row.request_input | {"question": "different"}
            expected = ErrorCode.IDEMPOTENCY_CONFLICT
        else:
            module.repository.find_key.return_value = None
    with pytest.raises(ContractViolation) as error:
        await module.FlowRunService(session, principal=SimpleNamespace(user_id=uuid4())).admit(request, uuid4())
    assert error.value.error.code == expected
    assert "synthetic-private-detail" not in str(error.value)
    session.rollback.assert_awaited_once()
    assert insert.await_count <= 1


async def test_repository_sql_uses_specific_conflict_and_owner_predicates():
    from src.modules.flow.infrastructure import run_repository as repo
    session = SimpleNamespace(scalar=AsyncMock(return_value=None))
    await repo.insert_receipt(session, dict(id=uuid4()))
    sql = str(session.scalar.await_args.args[0].compile(dialect=postgresql.dialect()))
    assert "ON CONFLICT ON CONSTRAINT uq_flow_runs_owner_operation_key DO NOTHING" in sql
    owner, run_id = uuid4(), uuid4()
    await repo.get_owned(session, run_id, owner)
    statement = session.scalar.await_args.args[0]
    assert owner in statement.compile().params.values() and run_id in statement.compile().params.values()
    assert "flow_runs.owner_user_id =" in str(statement) and "flow_runs.id =" in str(statement)


@pytest.mark.parametrize("stage", ["acquire", "authenticate", "teardown"])
@pytest.mark.parametrize("error_type", [OSError, TimeoutError])
async def test_new_http_boundary_catches_raw_db_and_teardown_errors(monkeypatch, stage, error_type):
    from src.api.main import app
    from db.session import get_session
    from src.shared.config import settings
    from src.modules.auth.api import router as auth
    monkeypatch.setattr(settings, "FLOW_RUN_ADMISSION_ENABLED", True)
    monkeypatch.setattr(auth, "get_oidc", lambda: SimpleNamespace(config=SimpleNamespace(
        redirect_uri="http://localhost:3200/api/auth/callback", origins=("http://localhost:3200",))))
    session = SimpleNamespace(scalar=AsyncMock(return_value=None))
    if stage == "authenticate":
        session.scalar.side_effect = error_type("synthetic-private-db-detail")
    async def failing_session():
        if stage == "acquire":
            raise error_type("synthetic-private-db-detail")
        try:
            yield session
        finally:
            if stage == "teardown":
                raise error_type("synthetic-private-db-detail")
    before = dict(app.dependency_overrides)
    app.dependency_overrides[get_session] = failing_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:8200") as client:
            # Valid token shape reaches the real digest/authenticate DB call; no
            # principal is mocked into a successful authentication.
            r = await client.post("/api/flow/runs", json=request_values(), headers={"cookie": "verith_session=" + "S" * 64})
        assert r.status_code == 503
        assert r.json()["data"] is None and r.json()["error"]["code"] == "SERVICE_UNAVAILABLE"
        assert r.headers["cache-control"] == "private, no-store" and r.headers["vary"] == "Cookie, Origin"
        assert "synthetic-private-db-detail" not in r.text
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(before)


async def test_malformed_utf8_json_is_safe_422_before_db(monkeypatch):
    from src.api.main import app
    from db.session import get_session
    from src.shared.config import settings
    from src.modules.auth.api import router as auth
    monkeypatch.setattr(settings, "FLOW_RUN_ADMISSION_ENABLED", True)
    monkeypatch.setattr(auth, "configured", lambda: True)
    calls = []
    async def forbidden():
        calls.append(True)
        raise AssertionError("malformed body reached database")
    before = dict(app.dependency_overrides)
    app.dependency_overrides[get_session] = forbidden
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:8200") as client:
            r = await client.post("/api/flow/runs", content=b'\xff', headers={"content-type": "application/json"})
        assert r.status_code == 422 and r.json()["error"]["code"] == "INPUT_INVALID"
        assert r.json()["data"] is None and r.headers["vary"] == "Cookie, Origin"
        assert not calls
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(before)


@pytest.mark.parametrize("method", ["POST", "GET"])
async def test_successful_handler_teardown_failure_sends_503_not_success(monkeypatch, method):
    """Mock DB unit only; real auth/CSRF functions run, never Google/PG evidence."""
    from datetime import timedelta
    from src.api.main import app
    from db.session import get_session
    from src.shared.config import settings
    from src.modules.auth.api import router as auth
    from src.modules.auth.application.session_service import Principal, csrf_token, token_digest
    from src.modules.flow.application import run_service as module
    monkeypatch.setattr(settings, "FLOW_RUN_ADMISSION_ENABLED", True)
    monkeypatch.setattr(auth, "get_oidc", lambda: SimpleNamespace(config=SimpleNamespace(
        redirect_uri="http://localhost:3200/api/auth/callback", origins=("http://localhost:3200",))))
    token = "S" * 64
    auth_row = SimpleNamespace(id=uuid4(), user_id=uuid4(), expires_at=datetime.now(UTC)+timedelta(hours=1), token_digest=token_digest(token))
    principal = Principal(auth_row.user_id, auth_row.id, auth_row.expires_at, auth_row.token_digest)
    session = SimpleNamespace(scalar=AsyncMock(return_value=auth_row), commit=AsyncMock(), rollback=AsyncMock())
    row = receipt(FlowAdmissionRequest.model_validate(request_values()))
    insert = AsyncMock(return_value=row)
    get = AsyncMock(return_value=row)
    monkeypatch.setattr(module.repository, "insert_receipt", insert)
    monkeypatch.setattr(module.repository, "get_owned", get)
    async def session_then_failure():
        try:
            yield session
        finally:
            raise OSError("synthetic successful-handler teardown failure")
    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_session] = session_then_failure
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:8200") as client:
            path = "/api/flow/runs" if method == "POST" else "/api/flow/runs/" + str(row.id)
            response = await client.request(method, path, json=request_values() if method == "POST" else None,
                headers={"cookie": "verith_session="+token, "origin": "http://localhost:3200", "x-csrf-token": csrf_token(principal)})
        assert response.status_code == 503 and response.json()["error"]["code"] == "SERVICE_UNAVAILABLE"
        assert response.json()["data"] is None
        assert response.headers["cache-control"] == "private, no-store"
        # Outer Starlette CORS appends Origin to the existing Vary list. Require
        # exactly the same field-name set, with no missing or extra dimensions.
        assert {part.strip().lower() for part in response.headers["vary"].split(",")} == {"cookie", "origin"}
        if method == "POST":
            insert.assert_awaited_once()
            session.commit.assert_awaited_once()
        else:
            get.assert_awaited_once()
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


def test_fixed_db_mode_returns_before_apps_and_downgrade_locks_before_check():
    import ast
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    tree = ast.parse((root / "scripts/cf002_interactive_login.py").read_text())
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    mode = next(n for n in ast.walk(main) if isinstance(n, ast.If) and isinstance(n.test, ast.Attribute)
                and isinstance(n.test.value, ast.Name) and n.test.value.id == "args" and n.test.attr == "verify_flow_admission_db")
    # The first matching branch sets up the owned HOME; find the actual verifier branch.
    branches = [n for n in ast.walk(main) if isinstance(n, ast.If) and isinstance(n.test, ast.Attribute)
                and n.test.attr == "verify_flow_admission_db"]
    verify = next(n for n in branches if any(isinstance(c, ast.Name) and c.id == "verify_admission" for c in ast.walk(n)))
    assert isinstance(verify.body[-1], ast.Return)
    prepare = next(n for n in ast.walk(main) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "prepare_projects")
    assert mode.lineno < verify.lineno < prepare.lineno
    migration = ast.parse((root / "db/migrations/versions/20261108_c3001a7e0001_flow_run_admission.py").read_text())
    downgrade = next(n for n in migration.body if isinstance(n, ast.FunctionDef) and n.name == "downgrade")
    source = ast.unparse(downgrade)
    assert source.index("LOCK TABLE flow_runs IN ACCESS EXCLUSIVE MODE") < source.index("SELECT EXISTS") < source.index("drop_table")


@pytest.mark.parametrize("kind,stage,expected_kind,expected_stage", [
    ("OwnedDatabaseError", "owned_creation", "OwnedDatabaseError", "owned_creation"),
    ("SecretCustomError", "secret-runtime-stage", "other", "other"),
])
def test_db_failure_diagnostic_exposes_only_fixed_source_location(kind, stage, expected_kind, expected_stage):
    import ast
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    tree = ast.parse((root / "scripts/cf002_interactive_login.py").read_text())
    helper = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "cf003_failure_diagnostic")
    namespace = {"_BACKEND": root}
    exec(compile(ast.Module(body=[helper], type_ignores=[]), "synthetic-diagnostic", "exec"), namespace)
    error_class = type(kind, (RuntimeError,), {})
    synthetic = {"failure": error_class}
    exec(compile("def verify_metadata():\n    private_local = 'never-output-private-value'\n    raise failure(private_local)\n", str(root / "scripts/runner_owned_database.py"), "exec"), synthetic)
    try:
        synthetic["verify_metadata"]()
    except RuntimeError as error:
        result = namespace["cf003_failure_diagnostic"](error, stage)
    assert result == {"phase": "cf003_failure_diagnostic", "stage": expected_stage,
                      "error_type": expected_kind,
                      "frames": [{"source": "owned_database", "function": "verify_metadata", "line": 3}]}
    encoded = json.dumps(result)
    assert "never-output-private-value" not in encoded and str(root) not in encoded
    assert "SecretCustomError" not in encoded and "secret-runtime-stage" not in encoded
