"""P1 target-parser consistency and P2 browser CORS, without network or DB access."""

from contextlib import asynccontextmanager
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.dialects.postgresql.asyncpg import PGDialect_asyncpg
from sqlalchemy.engine import make_url

from tests.db_safety import (
    UnsafeTestDatabase,
    approved_database,
    preflight_database,
    attest_engine_connection,
)


def config(url):
    approval = {
        "resource_id": "synthetic-only",
        "host": "127.0.0.1",
        "port": 6543,
        "database": "cf002_temp",
        "username": "cf002_role",
        "server_port": 5432,
        "disposable": True,
        "cleanup_owner": "synthetic-operator",
    }
    return {"TEST_DATABASE_URL": url, "TEST_DATABASE_APPROVAL": json.dumps(approval)}


APP = "postgresql+asyncpg://app:synthetic@localhost:5433/runtime"


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+asyncpg://cf002_role:synthetic@127.0.0.1:6543/%63f002_temp",
        "postgresql+asyncpg://%63f002_role:synthetic@127.0.0.1:6543/cf002_temp",
        "postgresql+asyncpg://cf002_role:synthetic@%31%32%37.0.0.1:6543/cf002_temp",
        "postgresql+asyncpg://cf002_role:synthetic@127.0.0.1:6543/cf002_temp?host=other",
        "postgresql+psycopg://cf002_role:synthetic@127.0.0.1:6543/cf002_temp",
        "postgresql+asyncpg://cf002_role:synthetic@127.0.0.1:6543/cf002_temp#ignored",
        "postgresql+asyncpg://cf002_role:synthetic@127.0.0.1:6543/cf002_temp\t",
    ],
)
async def test_ambiguous_targets_rejected_before_any_connection(url):
    connect = AsyncMock(side_effect=AssertionError("ambiguous target connected"))
    with pytest.raises(UnsafeTestDatabase):
        await preflight_database(config(url), APP, connect=connect)
    connect.assert_not_awaited()


@pytest.mark.parametrize("password", ["synthetic", "p%40ss:word/with#chars"])
async def test_preflight_and_engine_receive_identical_connection_parameters(password):
    url = make_url("postgresql+asyncpg://cf002_role@127.0.0.1:6543/cf002_temp").set(
        password=password
    )
    environ = config(url.render_as_string(hide_password=False))
    approval = approved_database(environ, APP)
    args, kwargs = PGDialect_asyncpg().create_connect_args(make_url(approval.url))
    assert args == []
    assert kwargs == approval.connection_parameters()

    @asynccontextmanager
    async def readonly():
        yield

    connection = SimpleNamespace(
        transaction=Mock(return_value=readonly()),
        close=AsyncMock(),
        fetchrow=AsyncMock(
            return_value={
                "database": "cf002_temp",
                "username": "cf002_role",
                "server_port": 5432,
                "resource_id": "synthetic-only",
                "privileged": False,
            }
        ),
    )
    connect = AsyncMock(return_value=connection)
    await preflight_database(environ, APP, connect=connect)
    connect.assert_awaited_once_with(**kwargs, timeout=3)


async def test_actual_engine_mismatch_rejected_in_readonly_transaction():
    approval = approved_database(
        config("postgresql+asyncpg://cf002_role:synthetic@127.0.0.1:6543/cf002_temp"),
        APP,
    )
    statements = []

    @asynccontextmanager
    async def transaction():
        yield

    async def execute(statement):
        statements.append(str(statement).strip())
        row = {
            "database": "%63f002_temp",
            "username": "cf002_role",
            "server_port": 5432,
            "resource_id": "synthetic-only",
            "privileged": False,
        }
        return SimpleNamespace(mappings=lambda: SimpleNamespace(one=lambda: row))

    connection = SimpleNamespace(
        begin=Mock(return_value=transaction()), execute=execute
    )
    with pytest.raises(UnsafeTestDatabase, match="Actual engine"):
        await attest_engine_connection(connection, approval)
    assert statements[0] == "SET TRANSACTION READ ONLY"
    assert len(statements) == 2 and statements[1].startswith("SELECT")


async def test_cors_public_preflight_and_protected_actual_requests(monkeypatch):
    from src.api.main import app
    from src.shared.config import settings
    from src.api.deps import get_stock_resolver_service
    from src.modules.stocks.api.schemas import StockResolveResponse

    origin = settings.cors_origin_list[0]
    service = SimpleNamespace(
        resolve=AsyncMock(
            return_value=StockResolveResponse(status="not_found", reason="no_match")
        )
    )
    monkeypatch.setitem(
        app.dependency_overrides, get_stock_resolver_service, lambda: service
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://unit"
    ) as client:
        request_headers = {
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        }
        allowed = await client.options("/api/stocks/resolve", headers=request_headers)
        assert allowed.status_code == 200
        assert allowed.headers["access-control-allow-origin"] == origin
        denied = await client.options(
            "/api/stocks/resolve",
            headers={**request_headers, "Origin": "https://not-approved.invalid"},
        )
        assert (
            denied.status_code == 400
            and "access-control-allow-origin" not in denied.headers
        )
        actual = await client.post(
            "/api/stocks/resolve",
            headers={"Origin": origin},
            json={"query": "synthetic"},
        )
        assert (
            actual.status_code == 200
            and actual.headers["access-control-allow-origin"] == origin
        )
        for path, method, status in [
            ("/api/flow/reports", "GET", 401),
            ("/api/flow/reports/save", "POST", 403),
        ]:
            response = await client.request(
                method, path, headers={"Origin": origin}, content=b"invalid-json"
            )
            assert (
                response.status_code == status
                and response.headers["access-control-allow-origin"] == origin
            )
    service.resolve.assert_awaited_once()
