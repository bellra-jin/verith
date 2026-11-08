"""Fixed CF-003 checks on a newly created, attested disposable PostgreSQL only.

No pytest fixtures, real credentials, Google/AI requests or application listeners.
Synthetic cookies stay in memory. All failures carry fixed phase names only.
"""

import asyncio
from contextlib import ExitStack, contextmanager
import hashlib
import json
import os
from pathlib import Path
import stat
import time
from unittest.mock import patch
from uuid import UUID, uuid4


class VerificationFailure(RuntimeError):
    """Only fixed labels supplied by this checker, never runtime input text."""


def check(value, label):
    if not value:
        raise VerificationFailure(label)


@contextmanager
def owned_postgres_home(docker):
    """After local context verification, keep asyncpg's optional cert search owned.

    Docker keeps its already-verified endpoint/environment. TLS settings are not
    changed; only this new DB-only invocation's HOME is scoped and restored.
    """
    raw = Path(docker._config.name)
    check(not raw.is_symlink(), "owned database home symlink denied")
    root = raw.resolve(strict=True)
    metadata = root.lstat()
    check(stat.S_ISDIR(metadata.st_mode) and metadata.st_uid == os.getuid()
          and metadata.st_mode & 0o077 == 0, "owned database home metadata")
    with patch.dict(os.environ, {"HOME": str(root)}):
        yield


@contextmanager
def isolated_application(proof):
    """Disable dotenv before app import; only the proven DB socket may connect."""
    import builtins
    import io
    import socket
    import dotenv
    import httpx
    from pydantic_settings.sources import DotEnvSettingsSource

    home = Path(proof._owner.docker._config.name).resolve(strict=True)
    check(os.environ.get("HOME") == str(home), "owned database home required")
    safe_env = {
        "PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "en_US.UTF-8", "TZ": "UTC",
        "HOME": str(home),
        "PYTHONDONTWRITEBYTECODE": "1",
        # This unconnected engine is never the verification DB. Only the request
        # get_session override below can obtain an attested owned connection.
        "DATABASE_URL": "postgresql+asyncpg://synthetic:unused@127.0.0.1:1/cf003_no_db",
        "ENABLE_NEWS_GRAPH": "false", "FLOW_RUN_ADMISSION_ENABLED": "true",
        "GOOGLE_CLIENT_ID": "cf003-synthetic.apps.googleusercontent.com",
        "GOOGLE_CLIENT_SECRET": "cf003-synthetic-not-a-real-secret",
        "AUTH_REDIRECT_URI": "http://localhost:3200/api/auth/callback",
        "AUTH_ORIGINS": "http://localhost:3200", "AUTH_ALLOW_LOCAL_HTTP": "true",
    }
    params = proof.connection_parameters()
    target = (params["host"], params["port"])
    original_open, original_io_open, original_os_open = builtins.open, io.open, os.open
    original_connect, original_connect_ex = socket.socket.connect, socket.socket.connect_ex
    original_resolve = socket.getaddrinfo
    original_http = httpx.AsyncClient.request
    observed = {"private_file_denials": 0, "external_network_denials": 0, "external_http_denials": 0, "dotenv_discovery_denials": 0}

    def guard_file(function):
        def guarded(name, *args, **kwargs):
            if not isinstance(name, int):
                if any(part.startswith(".env") for part in Path(os.fsdecode(name)).parts):
                    observed["private_file_denials"] += 1
                    raise PermissionError("CF003 private dotenv access denied")
            return function(name, *args, **kwargs)
        return guarded

    def connect(function):
        def guarded(sock, address):
            if not isinstance(address, tuple) or address[:2] != target:
                observed["external_network_denials"] += 1
                raise PermissionError("CF003 non-owned network access denied")
            return function(sock, address)
        return guarded

    def resolve(host, port, *args, **kwargs):
        if (host, port) != target:
            observed["external_network_denials"] += 1
            raise PermissionError("CF003 non-owned DNS denied")
        return original_resolve(host, port, *args, **kwargs)

    async def request(client, *args, **kwargs):
        if not isinstance(client._transport, httpx.ASGITransport):
            observed["external_http_denials"] += 1
            raise PermissionError("CF003 external HTTP denied")
        return await original_http(client, *args, **kwargs)

    def no_discovery(*args, **kwargs):
        observed["dotenv_discovery_denials"] += 1
        raise PermissionError("CF003 dotenv discovery denied")

    with ExitStack() as stack:
        stack.enter_context(patch.dict(os.environ, safe_env, clear=True))
        stack.enter_context(patch.object(DotEnvSettingsSource, "_read_env_files", lambda self: {}))
        for name in ("load_dotenv", "dotenv_values", "find_dotenv"):
            stack.enter_context(patch.object(dotenv, name, no_discovery))
        for module, name, function in ((builtins, "open", original_open), (io, "open", original_io_open), (os, "open", original_os_open)):
            stack.enter_context(patch.object(module, name, guard_file(function)))
        stack.enter_context(patch.object(socket.socket, "connect", connect(original_connect)))
        stack.enter_context(patch.object(socket.socket, "connect_ex", connect(original_connect_ex)))
        stack.enter_context(patch.object(socket, "getaddrinfo", resolve))
        stack.enter_context(patch.object(httpx.AsyncClient, "request", request))
        yield observed


async def migration(proof, target, *, downgrade=False, fail_after_create=False, locked=None, release=None, started=None, pids=None):
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import event, text
    from sqlalchemy.util.concurrency import await_only
    from alembic import command
    from alembic.config import Config
    from scripts.cf002_interactive_login import _BACKEND

    await proof.preflight()
    engine = create_async_engine(proof.url, connect_args=proof.connection_parameters())
    try:
        async with engine.connect() as connection:
            await proof.attest_connection(connection)
            if started is not None:
                pids["migration"] = await connection.scalar(text("SELECT pg_backend_pid()"))
                started.set()
            def apply(sync):
                def after_create(conn, cursor, statement, parameters, context, executemany):
                    normalized = statement.lstrip().upper()
                    if fail_after_create and normalized.startswith("CREATE TABLE FLOW_RUNS"):
                        raise RuntimeError("synthetic migration failure after DDL")
                    if locked is not None and normalized.startswith("LOCK TABLE FLOW_RUNS IN ACCESS EXCLUSIVE MODE"):
                        locked.set()
                        await_only(asyncio.wait_for(release.wait(), timeout=10))
                config = Config(str(_BACKEND / "alembic.ini"))
                config.set_main_option("script_location", str(_BACKEND / "db/migrations"))
                config.attributes.update(connection=sync, verified_test_mode=True)
                if fail_after_create or locked is not None:
                    event.listen(sync, "after_cursor_execute", after_create)
                try:
                    (command.downgrade if downgrade else command.upgrade)(config, target)
                finally:
                    if fail_after_create or locked is not None:
                        event.remove(sync, "after_cursor_execute", after_create)
            try:
                await connection.run_sync(apply)
                await connection.commit()
            except Exception:
                await connection.rollback()
                raise
    finally:
        await engine.dispose()


async def verify_admission(proof):
    phase = "initial"
    phases = []
    try:
        with isolated_application(proof) as observed:
            from sqlalchemy import text
            from scripts.cf002_interactive_login import owned_session
            async def revision():
                async with owned_session(proof) as session:
                    return await session.scalar(text("SELECT version_num FROM alembic_version"))
            initial = await revision()
            check(initial in {"c3001a7e0001", "c6001a7e0001"}, "exact admission revision required")
            if initial == "c6001a7e0001":
                await migration(proof, "c3001a7e0001", downgrade=True)
                check(await revision() == "c3001a7e0001", "admission baseline revision restored")
            result = await _verify(proof, lambda name: phases.append(name))
            if initial == "c6001a7e0001":
                await migration(proof, "c6001a7e0001")
                check(await revision() == initial, "input snapshot revision restored")
            check(not any(observed.values()), "unexpected forbidden access attempt")
            result["observed_denials"] = dict(observed)
            result["observation_scope"] = "scoped-Python-file-socket-httpx-wrappers-not-native-tracing"
            return result
    except Exception as exc:
        phase = phases[-1] if phases else phase
        detail = ": " + str(exc) if isinstance(exc, VerificationFailure) else ""
        raise RuntimeError("CF003 check failed: " + phase + " (" + type(exc).__name__ + ")" + detail) from None


async def _verify(proof, phase):
    import httpx
    from sqlalchemy import delete, func, insert, null, select, text, update
    from sqlalchemy.exc import IntegrityError, SQLAlchemyError
    from db.models.auth.models import AuthUser, AuthSession
    from db.models.common.agent_report import AgentReport
    from db.models.common.stock import Stock
    from db.models.flow.flow_report import FlowReport
    from db.models.flow.flow_run import FlowRun
    from db.session import get_session
    from scripts.cf002_interactive_login import owned_session
    from src.api.main import app
    from src.shared.config import settings
    from src.modules.auth.api.router import SESSION_COOKIE
    from src.modules.auth.application.session_service import issue_session, csrf_token, authenticate, revoke_session
    from src.modules.flow.application import run_service
    from src.modules.flow.infrastructure import run_repository
    from src.modules.flow.api.schemas import FlowReportSaveRequest
    from src.modules.flow.application.report_service import FlowReportService
    from tests.fixtures.flow_payload import make_flow_payload

    passed = []
    def mark(name):
        passed.append(name)
        phase(name)

    async def scalar(statement, parameters=None):
        async with owned_session(proof) as session:
            return await session.scalar(statement, parameters or {})

    async def revision():
        return await scalar(text("SELECT version_num FROM alembic_version"))

    async def count_runs():
        return await scalar(select(func.count()).select_from(FlowRun))

    async def preserved():
        # Only synthetic rows in this fresh owned DB; keep their contents in memory.
        async with owned_session(proof) as session:
            result = {}
            for table in ("stocks", "flow_reports", "flow_report_interpretations", "flow_report_verifications", "agent_reports"):
                rows = (await session.execute(text(f"SELECT row_to_json(t)::text FROM {table} t"))).scalars().all()
                result[table] = sorted(rows)
            return result

    phase("fresh_upgrade")
    check(await revision() == "c3001a7e0001" and await count_runs() == 0, "fresh revision")
    check(await scalar(text("SHOW transaction_isolation")) == "read committed", "READ COMMITTED required")
    check(await scalar(select(func.count()).select_from(AuthUser)) == 0, "fresh users")
    await migration(proof, "c2001a7e0001", downgrade=True)
    async with owned_session(proof) as session:
        a, b = AuthUser(id=uuid4()), AuthUser(id=uuid4())
        session.add_all([a, b])
        await session.flush()
        token_a, principal_a = await issue_session(session, a)
        token_a2, principal_a2 = await issue_session(session, a)
        token_b, principal_b = await issue_session(session, b)
        expired, expired_principal = await issue_session(session, a)
        await session.execute(update(AuthSession).where(AuthSession.id == expired_principal.session_id).values(
            created_at=func.clock_timestamp()-text("interval '2 hours'"), expires_at=func.clock_timestamp()-text("interval '1 hour'")))
        payload = make_flow_payload()
        payload["meta"]["ticker"] = "999984"
        await FlowReportService(session, principal=principal_a).save_report(FlowReportSaveRequest(payload=payload, question="CF003 synthetic preserved result"))
        session.add(FlowReport(id=uuid4(), stock_code="999984", owner_user_id=None))
        await session.commit()
        owner_a, owner_b = a.id, b.id
    before = await preserved()
    try:
        await migration(proof, "c3001a7e0001", fail_after_create=True)
    except RuntimeError:
        pass
    else:
        raise RuntimeError("DDL failure was not injected")
    check(await revision() == "c2001a7e0001", "failed migration revision rollback")
    check(await scalar(text("SELECT to_regclass('public.flow_runs')")) is None, "failed DDL rollback")
    check(await preserved() == before, "failed migration preserved old data")
    await migration(proof, "c3001a7e0001")
    check(await preserved() == before, "upgrade preserved old data")
    mark("fresh_upgrade_existing_data_and_DDL_rollback")

    async def request_session():
        async with owned_session(proof) as session:
            yield session

    old_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_session] = request_session
    transport = httpx.ASGITransport(app=app)
    async def call(method, path="/api/flow/runs", *, token=token_a, principal=principal_a,
                   body=None, headers=None, content=None, client_transport=None):
        values = {"origin": "http://localhost:3200", "x-csrf-token": csrf_token(principal)}
        if token is not None:
            values["cookie"] = SESSION_COOKIE + "=" + token
        values.update(headers or {})
        async with httpx.AsyncClient(transport=client_transport or transport, base_url="http://localhost:8200") as client:
            return await client.request(method, path, headers=values, json=body, content=content)

    def body(key, **changes):
        return dict(ticker="005930", question="CF003 synthetic question", as_of="2026-11-08T09:00:00+09:00", idempotency_key=key) | changes

    def response(value, status, code=None):
        check(value.status_code == status, "HTTP status")
        vary = {part.strip().lower() for part in value.headers.get("vary", "").split(",")}
        check(value.headers.get("cache-control") == "private, no-store" and vary == {"cookie", "origin"}, "private headers")
        data = value.json()
        UUID(data["request_id"])
        check(set(data) == {"request_id", "data", "error"}, "safe envelope")
        if code is not None:
            check(data["data"] is None and data["error"]["code"] == code, "safe code")
        return data

    async def wait_lock(pid):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if await scalar(text("SELECT wait_event_type FROM pg_stat_activity WHERE pid=:pid"), {"pid": pid}) == "Lock":
                return
            await asyncio.sleep(0.03)
        raise RuntimeError("owned task never reached database lock wait")

    try:
        phase("http_admission")
        first = await call("POST", body=body("first"))
        initial = response(first, 202)["data"]
        run_id = initial["run_id"]
        check(first.headers["location"] == "/api/flow/runs/" + run_id, "relative Location")
        check(initial["execution_status"] == "pending" and initial["storage_status"] == "not_stored"
              and initial["report_id"] is None and initial["error"] is None, "receipt state")
        check(await count_runs() == 1, "committed receipt visible on independent connection")
        replay = response(await call("POST", body=body("first", as_of="2026-11-08T00:00:00Z"), token=token_a2, principal=principal_a2), 202)
        fetched = response(await call("GET", "/api/flow/runs/" + run_id), 200)
        check(replay["data"] == fetched["data"] == initial, "stable references")
        check(len({first.json()["request_id"], replay["request_id"], fetched["request_id"]}) == 3, "fresh HTTP IDs")
        async with owned_session(proof) as session:
            row = await session.get(FlowRun, UUID(run_id))
            check(row.request_input == dict(ticker="005930", question="CF003 synthetic question", as_of="2026-11-08T00:00:00+00:00"), "normalized stored input")
            check(row.idempotency_key_digest == hashlib.sha256(b"first").digest() and row.admission_mode == "receipt_only", "digest and admission mode")
            first_created = row.created_at
        response(await call("POST", body=body("first", question="different")), 409, "IDEMPOTENCY_CONFLICT")
        response(await call("GET", "/api/flow/runs/" + run_id, token=token_b, principal=principal_b), 404, "RESOURCE_NOT_FOUND")
        response(await call("GET", "/api/flow/runs/" + str(uuid4()), token=token_b, principal=principal_b), 404, "RESOURCE_NOT_FOUND")
        other = response(await call("POST", body=body("first"), token=token_b, principal=principal_b), 202)
        check(other["data"]["run_id"] != run_id, "different owner same key")
        async with owned_session(proof) as session:
            check((await session.get(FlowRun, UUID(run_id))).created_at == first_created, "replay timestamp unchanged")
        mark("ASGI_PG_commit_replay_owner_and_ids")

        phase("http_rejections")
        baseline_count = await count_runs()
        invalid = [dict(question="x"*2001), dict(question="\x00"), dict(question="\ud800"),
                   dict(idempotency_key="x"*257), dict(idempotency_key="가"*86), dict(idempotency_key="\udfff"),
                   dict(owner_user_id=str(owner_b)), dict(ticker="5930"), dict(as_of="2026-11-08"), dict(as_of=123)]
        for changes in invalid:
            raw = json.dumps(body("bad-input") | changes, ensure_ascii=True).encode()
            response(await call("POST", content=raw, headers={"content-type": "application/json"}), 422, "INPUT_INVALID")
        response(await call("POST", content=b"\xff", headers={"content-type": "application/json"}), 422, "INPUT_INVALID")
        response(await call("GET", "/api/flow/runs/not-a-uuid"), 422, "INPUT_INVALID")
        for changes in [dict(token=None), dict(token=expired, principal=expired_principal),
                        dict(headers={"x-csrf-token": "invalid"}), dict(headers={"origin": "http://127.0.0.1:3200"}),
                        dict(headers={"cookie": f"{SESSION_COOKIE}={token_a}; {SESSION_COOKIE}={token_b}"}),
                        dict(token=None, headers={"authorization": "Bearer synthetic", "x-user-id": str(owner_a)})]:
            response(await call("POST", body=body("auth-failure"), **changes), 401, "AUTH_REQUIRED")
        response(await call("POST", body=body("bad-host"), headers={"host": "127.0.0.1:8200"}), 403, "AUTH_REQUEST_INVALID")
        check(await count_runs() == baseline_count, "rejection writes zero")
        for key in ("x"*256, "가"*85+"x"):
            response(await call("POST", body=body(key, question="x"*2000)), 202)
        mark("input_authentication_CSRF_and_owner_rejections")

        phase("gate_and_error_boundaries")
        async def no_dependency():
            raise RuntimeError("disabled route reached dependency")
            yield
        app.dependency_overrides[get_session] = no_dependency
        settings.FLOW_RUN_ADMISSION_ENABLED = False
        response(await call("POST", body=body("off")), 403, "FEATURE_UNAVAILABLE")
        settings.FLOW_RUN_ADMISSION_ENABLED = True
        saved_client_id = settings.GOOGLE_CLIENT_ID
        from src.modules.auth.api.router import get_oidc
        get_oidc.cache_clear()
        settings.GOOGLE_CLIENT_ID = ""
        response(await call("POST", body=body("unconfigured")), 401, "AUTH_REQUIRED")
        settings.GOOGLE_CLIENT_ID = saved_client_id
        get_oidc.cache_clear()
        app.dependency_overrides[get_session] = request_session
        for method, path in [("POST", "/api/flow/runs/"), ("DELETE", "/api/flow/runs/"+run_id), ("GET", "/api/flow/runs/x/execute"),
                             ("POST", "/api/flow/reports/save"), ("DELETE", "/api/flow/reports"), ("POST", "/api/supervisor/analyze")]:
            check((await call(method, path)).status_code == 403, "closed path remains closed")
        async def broken_acquisition():
            raise OSError("synthetic acquisition failure")
            yield
        app.dependency_overrides[get_session] = broken_acquisition
        response(await call("POST", body=body("acquisition")), 503, "SERVICE_UNAVAILABLE")
        async def broken_teardown():
            async with owned_session(proof) as session:
                yield session
            raise TimeoutError("synthetic teardown failure")
        app.dependency_overrides[get_session] = broken_teardown
        response(await call("GET", "/api/flow/runs/"+run_id), 503, "SERVICE_UNAVAILABLE")
        app.dependency_overrides[get_session] = request_session
        mark("gate_disabled_dependency_zero_and_safe_error_boundaries")

        async def race(key, different=False):
            inserted, second_started, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
            pids = {}
            original = run_repository.insert_receipt
            async def coordinated(session, values):
                name = "first" if "first" not in pids else "second"
                pids[name] = await session.scalar(text("SELECT pg_backend_pid()"))
                if name == "second":
                    second_started.set()
                row = await original(session, values)
                if name == "first":
                    inserted.set()
                    await asyncio.wait_for(release.wait(), timeout=10)
                return row
            tasks = []
            try:
                with patch.object(run_repository, "insert_receipt", coordinated):
                    tasks.append(asyncio.create_task(call("POST", body=body(key))))
                    await asyncio.wait_for(inserted.wait(), timeout=10)
                    tasks.append(asyncio.create_task(call("POST", body=body(key, question="different" if different else "CF003 synthetic question"))))
                    await asyncio.wait_for(second_started.wait(), timeout=10)
                    check(pids["first"] != pids["second"], "independent race connections")
                    await wait_lock(pids["second"])
                    release.set()
                    results = await asyncio.wait_for(asyncio.gather(*tasks), timeout=15)
                response(results[0], 202)
                response(results[1], 409 if different else 202, "IDEMPOTENCY_CONFLICT" if different else None)
                if not different:
                    check(results[0].json()["data"] == results[1].json()["data"], "concurrent same receipt")
                digest = hashlib.sha256(key.encode()).digest()
                check(await scalar(select(func.count()).select_from(FlowRun).where(FlowRun.owner_user_id==owner_a, FlowRun.idempotency_key_digest==digest)) == 1, "race row count")
            finally:
                release.set()
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)

        phase("idempotency_races")
        await race("concurrent-same")
        await race("concurrent-different", different=True)
        mark("same_and_different_input_real_commit_lock_races")

        phase("rollback_and_response_loss")
        original_insert = run_repository.insert_receipt
        async def failed_insert(session, values):
            await original_insert(session, values)
            await session.execute(text("SELECT 1/0"))
        with patch.object(run_repository, "insert_receipt", failed_insert):
            response(await call("POST", body=body("rollback")), 503, "SERVICE_UNAVAILABLE")
        check(await scalar(select(func.count()).select_from(FlowRun).where(FlowRun.idempotency_key_digest==hashlib.sha256(b"rollback").digest())) == 0, "rolled back insert absent")
        response(await call("POST", body=body("rollback")), 202)
        class LostResponse(httpx.ASGITransport):
            async def handle_async_request(self, request):
                result = await super().handle_async_request(request)
                await result.aclose()
                raise httpx.ReadError("synthetic response loss")
        try:
            await call("POST", body=body("lost-response"), client_transport=LostResponse(app=app))
        except httpx.ReadError:
            pass
        else:
            raise RuntimeError("response loss not injected")
        async with owned_session(proof) as session:
            committed = await run_repository.find_key(session, owner_a, hashlib.sha256(b"lost-response").digest())
            expected = str(committed.id)
        check(response(await call("POST", body=body("lost-response")), 202)["data"]["run_id"] == expected, "response loss reuses committed run")
        mark("insert_rollback_readmission_and_postcommit_response_loss")

        phase("session_revoke_race")
        entered, release, revoking = asyncio.Event(), asyncio.Event(), asyncio.Event()
        pid = {}
        async def hold_insert(session, values):
            row = await original_insert(session, values)
            entered.set()
            await asyncio.wait_for(release.wait(), timeout=10)
            return row
        async def logout():
            async with owned_session(proof) as session:
                pid["revoke"] = await session.scalar(text("SELECT pg_backend_pid()"))
                revoking.set()
                principal = await authenticate(session, token_a, exclusive_lock=True)
                await revoke_session(session, principal)
        tasks = []
        try:
            with patch.object(run_repository, "insert_receipt", hold_insert):
                tasks.append(asyncio.create_task(call("POST", body=body("revoke-race"))))
                await asyncio.wait_for(entered.wait(), timeout=10)
                tasks.append(asyncio.create_task(logout()))
                await asyncio.wait_for(revoking.wait(), timeout=10)
                await wait_lock(pid["revoke"])
                release.set()
                results = await asyncio.wait_for(asyncio.gather(*tasks), timeout=15)
            response(results[0], 202)
        finally:
            release.set()
            for task in tasks:
                if not task.done(): task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        response(await call("POST", body=body("revoked")), 401, "AUTH_REQUIRED")
        response(await call("GET", "/api/flow/runs/"+run_id), 401, "AUTH_REQUIRED")
        mark("admission_SHARE_before_revoke_and_revoked_cookie_denial")

        phase("constraints_and_downgrade")
        async with owned_session(proof) as session:
            reference = (await session.scalars(select(FlowRun))).first()
            values = {column.name: getattr(reference, column.name) for column in FlowRun.__table__.columns}
        changes = [(dict(owner_user_id=uuid4()), "23503")]
        changes += [(change, "23514") for change in [dict(idempotency_key_digest=b"short"), dict(input_fingerprint="invalid"),
                       dict(operation="other"), dict(request_contract_version=2), dict(request_input=[]),
                       dict(admission_mode="executable"), dict(execution_status="running"), dict(storage_status="stored"),
                       dict(created_at=text("'infinity'::timestamptz"))]]
        changes += [(dict(attempt_id=values["attempt_id"]), "23505"),
                    (dict(id=values["id"]), "23505"),
                    (dict(idempotency_key_digest=values["idempotency_key_digest"]), "23505")]
        # SQL NULL expressions also test JSONB's real NOT NULL, rather than JSON null.
        changes += [({column.name: null()}, "23502") for column in FlowRun.__table__.columns if not column.nullable]
        for change, expected_sqlstate in changes:
            async with owned_session(proof) as session:
                candidate = values | dict(id=uuid4(), attempt_id=uuid4(), idempotency_key_digest=os.urandom(32)) | change
                try:
                    await session.execute(insert(FlowRun).values(**candidate))
                    await session.commit()
                except IntegrityError as exc:
                    await session.rollback()
                    check(getattr(exc.orig, "sqlstate", None) == expected_sqlstate, "expected physical constraint SQLSTATE")
                else:
                    raise RuntimeError("constraint accepted invalid receipt")
        count = await count_runs()
        try:
            await migration(proof, "c2001a7e0001", downgrade=True)
        except RuntimeError:
            pass
        else:
            raise RuntimeError("nonempty downgrade accepted")
        check(await count_runs() == count and await revision() == "c3001a7e0001", "nonempty downgrade preserved")
        check(await preserved() == before, "existing report stock index payload preserved")
        # Only this verifier's synthetic owner rows on its fresh disposable DB.
        async with owned_session(proof) as session:
            await session.execute(delete(FlowRun).where(FlowRun.owner_user_id.in_([owner_a, owner_b])))
            await session.commit()
        # Insert wins first: downgrade must wait, recheck and refuse, never drop
        # an uncommitted row that becomes committed while it waits.
        started, pids = asyncio.Event(), {}
        candidate = values | dict(id=uuid4(), attempt_id=uuid4(), idempotency_key_digest=os.urandom(32))
        task = None
        try:
            async with owned_session(proof) as session:
                await session.execute(insert(FlowRun).values(**candidate))
                task = asyncio.create_task(migration(proof, "c2001a7e0001", downgrade=True, started=started, pids=pids))
                await asyncio.wait_for(started.wait(), timeout=10)
                await wait_lock(pids["migration"])
                await session.commit()
            try:
                await asyncio.wait_for(task, timeout=15)
            except RuntimeError:
                pass
            else:
                raise RuntimeError("downgrade removed a concurrently committed receipt")
            check(await count_runs() == 1 and await revision() == "c3001a7e0001", "insert-first downgrade atomic refusal")
        finally:
            if task is not None and not task.done(): task.cancel()
            if task is not None: await asyncio.gather(task, return_exceptions=True)
        async with owned_session(proof) as session:
            await session.execute(delete(FlowRun).where(FlowRun.id == candidate["id"]))
            await session.commit()

        # Downgrade wins first: pause after its real ACCESS EXCLUSIVE statement,
        # before EXISTS. The late insert must block and cannot silently commit.
        locked, release, inserting = asyncio.Event(), asyncio.Event(), asyncio.Event()
        insertion_pid, tasks = {}, []
        async def late_insert():
            async with owned_session(proof) as session:
                insertion_pid["pid"] = await session.scalar(text("SELECT pg_backend_pid()"))
                inserting.set()
                try:
                    await session.execute(insert(FlowRun).values(**(candidate | dict(id=uuid4(), attempt_id=uuid4()))))
                    await session.commit()
                    return True
                except SQLAlchemyError:
                    await session.rollback()
                    return False
        try:
            tasks.append(asyncio.create_task(migration(proof, "c2001a7e0001", downgrade=True, locked=locked, release=release)))
            await asyncio.wait_for(locked.wait(), timeout=10)
            tasks.append(asyncio.create_task(late_insert()))
            await asyncio.wait_for(inserting.wait(), timeout=10)
            await wait_lock(insertion_pid["pid"])
            release.set()
            result = await asyncio.wait_for(asyncio.gather(*tasks), timeout=15)
            check(result[1] is False and await revision() == "c2001a7e0001", "downgrade-first late insert rejected")
        finally:
            release.set()
            for task in tasks:
                if not task.done(): task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        await migration(proof, "c3001a7e0001")
        check(await count_runs() == 0 and await preserved() == before, "empty downgrade reupgrade preserved")
        mark("constraints_nonempty_refusal_both_downgrade_insert_orders_and_reupgrade")
        return dict(status="passed", checks=passed, run_rows=0, constraint_rejections=len(changes),
                    scope="actual-ASGI-and-owned-PostgreSQL-with-synthetic-provider-identities")
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(old_overrides)
