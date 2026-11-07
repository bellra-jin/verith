"""No network or DB: safe cookie/CSRF and logout failure responses."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock

from httpx import AsyncClient, ASGITransport
import pytest
from sqlalchemy.exc import SQLAlchemyError
from starlette.requests import Request

from src.api.services.auth_service import (
    Principal,
    AuthenticationRequired,
    csrf_token,
    verify_csrf,
)


def principal():
    return Principal(
        uuid4(), uuid4(), datetime.now(UTC) + timedelta(hours=1), b"x" * 32
    )


def test_csrf_non_ascii_is_a_safe_rejection():
    user = principal()
    with pytest.raises(AuthenticationRequired):
        verify_csrf(user, "é", "https://app.unit", ["https://app.unit"])
    verify_csrf(user, csrf_token(user), "https://app.unit", ["https://app.unit"])


def test_duplicate_same_name_cookies_are_rejected():
    from src.api.routes.auth import unique_cookie

    request = Request(
        {
            "type": "http",
            "headers": [(b"cookie", b"verith_session=first; verith_session=second")],
        }
    )
    assert unique_cookie(request, "verith_session") is None


async def test_logout_db_failure_does_not_report_success_or_remove_cookie(monkeypatch):
    from src.api.main import app
    from src.api.routes import auth
    from db.session import get_session

    previous = dict(app.dependency_overrides)

    async def session():
        yield object()

    app.dependency_overrides[get_session] = session
    monkeypatch.setattr(auth, "request_principal", AsyncMock(return_value=principal()))
    monkeypatch.setattr(
        auth,
        "revoke_session",
        AsyncMock(side_effect=SQLAlchemyError("synthetic failure")),
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="https://app.unit"
        ) as client:
            response = await client.post("/api/auth/logout")
            assert response.status_code == 503
            assert "set-cookie" not in response.headers
            assert response.json()["detail"]["code"] == "SERVICE_UNAVAILABLE"
            assert "synthetic" not in response.text
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


async def test_logout_acquires_exclusive_session_lock_before_revocation(monkeypatch):
    from src.api.routes import auth

    user = principal()
    authenticate_request = AsyncMock(return_value=user)
    revoke = AsyncMock()
    monkeypatch.setattr(auth, "request_principal", authenticate_request)
    monkeypatch.setattr(auth, "revoke_session", revoke)
    request = Request({"type": "http", "headers": []})
    session = object()
    response = await auth.logout(request, session)
    assert response.status_code == 200
    authenticate_request.assert_awaited_once_with(
        request, session, mutation=True, exclusive_session_lock=True
    )
    revoke.assert_awaited_once_with(session, user)


async def test_exclusive_authentication_uses_for_update_not_for_share():
    from types import SimpleNamespace
    from sqlalchemy.dialects import postgresql
    from src.api.services.auth_service import authenticate

    user = principal()
    row = SimpleNamespace(
        user_id=user.user_id,
        id=user.session_id,
        expires_at=user.expires_at,
        token_digest=user.token_digest,
    )
    session = SimpleNamespace(scalar=AsyncMock(return_value=row))
    await authenticate(
        session, "synthetic-token-" + "x" * 32, lock=True, exclusive_lock=True
    )
    statement = session.scalar.await_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE OF auth_sessions" in sql
    assert "FOR SHARE" not in sql
