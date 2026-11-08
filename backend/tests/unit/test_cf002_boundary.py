"""Provider-independent CF-002 checks; never connect to a database or IdP."""

from contextlib import asynccontextmanager
import copy
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from src.shared.http.access_boundary import AccessBoundary, PUBLIC_ROUTES
from tests.db_safety import UnsafeTestDatabase, preflight_database


@pytest.fixture
def approved_config():
    approval = {
        "resource_id": "synthetic-resource-only",
        "host": "127.0.0.1",
        "port": 6543,
        "server_port": 5432,
        "database": "cf002_temp",
        "username": "cf002_limited",
        "cleanup_owner": "synthetic-test-operator",
        "disposable": True,
    }
    return {
        "TEST_DATABASE_URL": "postgresql+asyncpg://cf002_limited:never-real@127.0.0.1:6543/cf002_temp",
        "TEST_DATABASE_APPROVAL": json.dumps(approval),
    }, "postgresql+asyncpg://app:never-real@localhost:5433/runtime"


@pytest.mark.parametrize(
    "problem",
    [
        "no_url",
        "blank_url",
        "no_approval",
        "invalid_approval",
        "not_disposable",
        "no_cleanup_owner",
        "no_resource",
        "wrong_host",
        "wrong_port",
        "wrong_database",
        "wrong_role",
        "same_server",
        "same_credential",
        "query_override",
        "invalid_url",
        "mapped_loopback",
        "short_loopback",
        "unknown_app_target",
    ],
)
async def test_db_configuration_failure_precedes_connection_or_engine(
    approved_config, monkeypatch, problem
):
    environ, app_url = copy.deepcopy(approved_config)
    manifest = json.loads(environ["TEST_DATABASE_APPROVAL"])
    if problem == "no_url":
        environ.pop("TEST_DATABASE_URL")
    elif problem == "blank_url":
        environ["TEST_DATABASE_URL"] = " "
    elif problem == "no_approval":
        environ.pop("TEST_DATABASE_APPROVAL")
    elif problem == "invalid_approval":
        environ["TEST_DATABASE_APPROVAL"] = "[]"
    elif problem == "not_disposable":
        manifest["disposable"] = False
    elif problem == "no_cleanup_owner":
        manifest.pop("cleanup_owner")
    elif problem == "no_resource":
        manifest["resource_id"] = " "
    elif problem.startswith("wrong_"):
        manifest[problem.removeprefix("wrong_").replace("role", "username")] = (
            "mismatch"
        )
    elif problem == "same_server":
        app_url = "postgresql+asyncpg://app:never-real@LOCALHOST.:6543/%63f002_temp"
    elif problem == "same_credential":
        app_url = "postgresql+asyncpg://cf002_limited:never-real@localhost:5433/runtime"
    elif problem == "query_override":
        environ["TEST_DATABASE_URL"] += "?host=somewhere-else"
    elif problem == "invalid_url":
        environ["TEST_DATABASE_URL"] = "never-real-private-invalid-url"
    elif problem == "mapped_loopback":
        app_url = "postgresql+asyncpg://app:never-real@[::ffff:127.0.0.1]:6543/runtime"
    elif problem == "short_loopback":
        app_url = "postgresql+asyncpg://app:never-real@127.1:6543/runtime"
    elif problem == "unknown_app_target":
        app_url = "postgresql+asyncpg:///runtime"
    if problem not in {"no_approval", "invalid_approval"}:
        environ["TEST_DATABASE_APPROVAL"] = json.dumps(manifest)
    connect = AsyncMock()
    engine = Mock(side_effect=AssertionError("engine created before safety gate"))
    monkeypatch.setattr("sqlalchemy.ext.asyncio.create_async_engine", engine)
    with pytest.raises(UnsafeTestDatabase) as exc:
        await preflight_database(environ, app_url, connect=connect)
    assert "never-real" not in str(exc.value)
    connect.assert_not_awaited()
    engine.assert_not_called()


@pytest.mark.parametrize(
    "problem",
    [
        None,
        "database",
        "username",
        "server_port",
        "resource_id",
        "privileged",
        "unavailable",
    ],
)
async def test_db_attestation_is_readonly_and_fail_closed(approved_config, problem):
    environ, app_url = approved_config
    row = {
        "database": "cf002_temp",
        "username": "cf002_limited",
        "server_port": 5432,
        "resource_id": "synthetic-resource-only",
        "privileged": False,
    }
    if problem and problem != "unavailable":
        row[problem] = True if problem == "privileged" else "mismatch"

    @asynccontextmanager
    async def readonly_context():
        yield

    connection = SimpleNamespace(
        transaction=Mock(return_value=readonly_context()),
        fetchrow=AsyncMock(return_value=row),
        execute=AsyncMock(),
        close=AsyncMock(),
    )
    connect = AsyncMock(return_value=connection)
    if problem == "unavailable":
        connect.side_effect = RuntimeError("never-real private connection detail")
    if problem:
        with pytest.raises(UnsafeTestDatabase) as exc:
            await preflight_database(environ, app_url, connect=connect)
        assert "never-real" not in str(exc.value)
    else:
        result = await preflight_database(environ, app_url, connect=connect)
        assert "never-real" not in repr(result)
    connection.execute.assert_not_awaited()
    if problem != "unavailable":
        connection.transaction.assert_called_once_with(readonly=True)
        assert connection.fetchrow.await_args.args[0].lstrip().startswith("SELECT")
        connection.close.assert_awaited_once()


@pytest.mark.parametrize("entry", ["tests.conftest", "tests.flow_integration.conftest"])
async def test_existing_db_entrypoints_cannot_fallback(monkeypatch, entry):
    import importlib

    module = importlib.import_module(entry)
    if hasattr(module, "dotenv_values"):
        monkeypatch.setattr(module, "dotenv_values", lambda *args, **kwargs: {})
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    monkeypatch.delenv("TEST_DATABASE_APPROVAL", raising=False)
    engine = Mock(side_effect=AssertionError("unsafe engine"))
    monkeypatch.setattr(module, "create_async_engine", engine)
    fixture = module.db_session if entry == "tests.conftest" else module.flow_db
    generator = fixture.__wrapped__()
    with pytest.raises(pytest.fail.Exception, match="approval are required"):
        await anext(generator)
    engine.assert_not_called()


@pytest.mark.parametrize(
    "method,path,status",
    [
        ("GET", "/api/flow/reports", 401),
        ("GET", "/api/reports/archive", 401),
        ("DELETE", "/api/flow/reports/example", 401),
        ("DELETE", "/api/flow/reports", 403),
        ("POST", "/api/flow/reports/save", 403),
        ("GET", "/news/reports/example", 403),
        ("POST", "/api/technical/reports", 403),
        ("GET", "/api/industry/reports/example/html", 403),
    ],
)
async def test_unverified_headers_and_cookies_never_reach_services(
    method, path, status
):
    downstream = AsyncMock(side_effect=AssertionError("upstream/service invoked"))
    app = AccessBoundary(downstream)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://unit"
    ) as client:
        response = await client.request(
            method,
            path,
            headers={
                "X-User-ID": str(uuid4()),
                "Authorization": "Bearer not-a-principal",
                "Cookie": "session=expired-or-revoked",
            },
            content=b"invalid-json",
        )
    assert response.status_code == status
    assert response.headers["cache-control"] == "private, no-store"
    downstream.assert_not_awaited()


async def test_actual_backend_route_inventory_is_closed_before_dependencies(
    monkeypatch,
):
    from src.api.main import app
    from db.session import get_session

    async def forbidden_dependency():
        raise AssertionError("DB/session dependency invoked")

    monkeypatch.setitem(app.dependency_overrides, get_session, forbidden_dependency)
    routes = [
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        for method in operations
        if method.upper()
        in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
        and (method.upper(), path) not in PUBLIC_ROUTES
    ]
    assert routes
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://unit"
    ) as client:
        for method, path in routes:
            for part in ("report_id", "reportId", "stock_code", "news_id"):
                path = path.replace("{" + part + "}", str(uuid4()))
            response = await client.request(method, path, content=b"{}")
            assert response.status_code in {401, 403}, (method, path, response.text)
        assert (await client.get("/health")).status_code == 200


async def test_app_import_is_lazy_and_graph_bootstrap_is_opt_in(monkeypatch):
    from db.session import get_engine
    from db.graph.driver import get_driver
    from src.api import main

    assert get_engine.cache_info().currsize == get_driver.cache_info().currsize == 0
    bootstrap = AsyncMock(
        side_effect=AssertionError("graph startup touched a database")
    )
    monkeypatch.setattr(main, "ensure_constraints", bootstrap)
    monkeypatch.setattr(main.settings, "ENABLE_NEWS_GRAPH", False)
    async with main.lifespan(main.app):
        pass
    bootstrap.assert_not_awaited()


async def test_opted_in_graph_failure_still_closes_its_driver(monkeypatch):
    from src.api import main

    bootstrap = AsyncMock(side_effect=RuntimeError("synthetic bootstrap failure"))
    close = AsyncMock()
    monkeypatch.setattr(main.settings, "ENABLE_NEWS_GRAPH", True)
    monkeypatch.setattr(main, "ensure_constraints", bootstrap)
    monkeypatch.setattr(main, "close_driver", close)
    with pytest.raises(RuntimeError, match="synthetic bootstrap failure"):
        async with main.lifespan(main.app):
            pass
    close.assert_awaited_once()


@pytest.mark.parametrize(
    "name",
    [
        "scripts.seed_stocks",
        "scripts.seed_stock_aliases",
        "scripts.seed_representative_stocks",
    ],
)
def test_seed_imports_used_by_existing_db_tests_do_not_create_engines(
    monkeypatch, name
):
    import importlib
    from db import session

    engine = Mock(side_effect=AssertionError("DB test collection created an engine"))
    factory = Mock(
        side_effect=AssertionError("DB test collection created a session factory")
    )
    monkeypatch.setattr(session, "get_engine", engine)
    monkeypatch.setattr(session, "get_session_factory", factory)
    importlib.reload(importlib.import_module(name))
    engine.assert_not_called()
    factory.assert_not_called()
