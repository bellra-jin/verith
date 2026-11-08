"""v0.5 local ports: no private env reads, actual network/Google/DB/AI calls."""

from dataclasses import replace
from urllib.parse import parse_qs, urlsplit
from pathlib import Path

from httpx import ASGITransport, AsyncClient
import pytest

from src.modules.auth.infrastructure.google_oidc import GoogleConfig, LoginFailed
from src.modules.auth.application.session_service import Principal
from tests.unit.test_cf002_google import prepare

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "origin",
    ["http://localhost:3000", "http://localhost:3201", "http://127.0.0.1:3200"],
)
def test_unapproved_local_browser_config_is_rejected(origin):
    with pytest.raises(LoginFailed):
        GoogleConfig(
            "fixture", "synthetic", origin + "/api/auth/callback", (origin,), True
        ).validate()


async def test_google_exchange_retains_registered_external_3200_callback(provider):
    # Use the signed MockTransport fixture; nothing connects to Google.
    client, state = provider
    client.config = replace(
        client.config,
        redirect_uri="http://localhost:3200/api/auth/callback",
        origins=("http://localhost:3200",),
        allow_local_http=True,
    )
    state["expected_redirect"] = client.config.redirect_uri
    params, browser, query = await prepare(provider)
    assert query["redirect_uri"] == ["http://localhost:3200/api/auth/callback"]
    assert await client.callback(params, browser) == (
        "https://accounts.google.com",
        "CaseSensitive123",
    )
    assert state["token_calls"] == 1


@pytest.fixture
def provider(request):
    from tests.unit.test_cf002_google import provider as factory, rsa as key_factory

    return factory.__wrapped__(key_factory.__wrapped__())


async def test_local_callback_cookies_origin_and_host_injection(monkeypatch, provider):
    from src.api.main import app
    from src.modules.auth.api import router as auth
    from db.session import get_session
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from datetime import datetime, UTC, timedelta
    from uuid import uuid4

    client, state = provider
    client.config = replace(
        client.config,
        redirect_uri="http://localhost:3200/api/auth/callback",
        origins=("http://localhost:3200",),
        allow_local_http=True,
    )
    monkeypatch.setattr(auth, "get_oidc", lambda: client)
    monkeypatch.setattr(auth.settings, "AUTH_REDIRECT_URI", client.config.redirect_uri)
    monkeypatch.setattr(auth.settings, "AUTH_ALLOW_LOCAL_HTTP", True)
    fake_session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    principal = Principal(
        uuid4(), uuid4(), datetime.now(UTC) + timedelta(hours=1), b"x" * 32
    )

    async def session():
        yield fake_session

    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_session] = session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://localhost:8200"
        ) as http:
            started = await http.get("/api/auth/login")
            assert started.status_code == 303
            assert parse_qs(urlsplit(started.headers["location"]).query)[
                "redirect_uri"
            ] == [client.config.redirect_uri]
            cookie = started.headers["set-cookie"]
            assert (
                "HttpOnly" in cookie
                and "Path=/api/auth/callback" in cookie
                and "SameSite=lax" in cookie
                and "Secure" not in cookie
            )
            for headers in [
                {"Host": "evil.unit"},
                {"Host": "localhost:3000"},
                {"Host": "127.0.0.1:8200"},
                {"X-Forwarded-Host": "evil.unit"},
            ]:
                assert (
                    await http.get("/api/auth/login", headers=headers)
                ).status_code == 403
            assert state["token_calls"] == 0
            # Origin and synchronizer remain required at the actual session endpoint.
            authenticate = AsyncMock(return_value=principal)
            monkeypatch.setattr(auth, "authenticate", authenticate)
            headers = {
                "Cookie": "verith_session=" + "x" * 43,
                "X-CSRF-Token": auth.csrf_token(principal),
            }
            for origin in [
                "http://localhost:3000",
                "http://localhost:3201",
                "http://127.0.0.1:3200",
            ]:
                assert (
                    await http.post(
                        "/api/auth/logout", headers={**headers, "Origin": origin}
                    )
                ).status_code == 401
            revoke = AsyncMock()
            monkeypatch.setattr(auth, "revoke_session", revoke)
            response = await http.post(
                "/api/auth/logout",
                headers={**headers, "Origin": "http://localhost:3200"},
            )
            assert response.status_code == 200
            assert (
                "Path=/" in response.headers["set-cookie"]
                and "HttpOnly" in response.headers["set-cookie"]
            )
            assert response.headers["cache-control"] == "private, no-store"
            revoke.assert_awaited_once()
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


def test_scoped_static_defaults_preserve_inference_and_cache_off():
    assert "http://localhost:3200" in (ROOT / "src/shared/config.py").read_text()
    repo = ROOT.parent
    assert (
        '"http://localhost:8200"' in (repo / "ai/src/supervisor/config.py").read_text()
    )
    assert (
        '"http://localhost:8200"' in (repo / "ai/src/agents/news/config.py").read_text()
    )
    for name in ["export_news_graph.py", "export_industry_graph.py"]:
        assert "bolt://localhost:17687" in (ROOT / "scripts" / name).read_text()
    # Original external inference service is independent of the AI FastAPI port.
    assert (
        "http://pbd.mtvs2026.work:8000/v1"
        in (repo / "ai/src/agents/fundamental/core/config.py").read_text()
    )


async def test_cors_3200_allows_only_canonical_local_origin():
    from src.api.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://localhost:8200"
    ) as http:
        headers = {
            "Origin": "http://localhost:3200",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        }
        allowed = await http.options("/api/stocks/resolve", headers=headers)
        assert allowed.status_code == 200
        assert allowed.headers["access-control-allow-origin"] == "http://localhost:3200"
        for origin in [
            "http://localhost:3000",
            "http://localhost:3201",
            "http://127.0.0.1:3200",
        ]:
            denied = await http.options(
                "/api/stocks/resolve", headers={**headers, "Origin": origin}
            )
            assert (
                denied.status_code == 400
                and "access-control-allow-origin" not in denied.headers
            )
