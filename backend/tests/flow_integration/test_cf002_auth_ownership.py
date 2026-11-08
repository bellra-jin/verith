"""Real isolated PostgreSQL auth/session/owner checks; no external OIDC login claim."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4
import hashlib

import pytest
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.exc import IntegrityError

from db.models.auth.models import AuthIdentity, AuthSession, AuthUser
from db.models.common.agent_report import AgentReport
from db.models.common.stock import Stock
from db.models.flow.flow_report import FlowReport
from db.models.flow.report_verification import FlowReportVerification
from src.modules.flow.infrastructure.report_repository import list_owned_indexes
from src.modules.flow.api.schemas import FlowReportSaveRequest
from src.modules.auth.application.session_service import AuthenticationRequired, authenticate, issue_session, link_verified_identity, revoke_session, validate_principal, csrf_token, verify_csrf
from src.modules.flow.application.report_service import FlowReportService
from tests.fixtures.flow_payload import make_flow_payload


async def save(context):
    payload = make_flow_payload()
    from uuid import UUID

    context.report_ids.append(UUID(payload["report_id"]))
    return await context.service.save_report(
        FlowReportSaveRequest(payload=payload, question="합성")
    )


async def test_internal_identity_case_sensitive_and_stable(flow_db):
    session = flow_db.session
    a = await link_verified_identity(
        session, issuer="https://identity.unit", subject="AbC"
    )
    again = await link_verified_identity(
        session, issuer="https://identity.unit", subject="AbC"
    )
    b = await link_verified_identity(
        session, issuer="https://identity.unit", subject="abc"
    )
    assert a.id == again.id != b.id
    assert await session.scalar(select(func.count()).select_from(AuthIdentity)) == 2
    a.disabled_at = datetime.now(UTC)
    await session.flush()
    with pytest.raises(AuthenticationRequired):
        await link_verified_identity(
            session, issuer="https://identity.unit", subject="AbC"
        )


async def test_digest_expiry_revocation_rotation_and_disabled(flow_db):
    session = flow_db.session
    principal = await authenticate(session, flow_db.token)
    stored = await session.get(AuthSession, principal.session_id)
    assert stored.token_digest == hashlib.sha256(flow_db.token.encode()).digest()
    assert len(stored.token_digest) == 32 and flow_db.token not in repr(principal)
    with pytest.raises(AuthenticationRequired):
        await authenticate(session, str(principal.session_id))
    verify_csrf(
        principal, csrf_token(principal), "https://app.unit", ["https://app.unit"]
    )
    for value, origin in [
        (None, "https://app.unit"),
        ("bad", "https://app.unit"),
        (csrf_token(principal), "https://evil.unit"),
    ]:
        with pytest.raises(AuthenticationRequired):
            verify_csrf(principal, value, origin, ["https://app.unit"])
    await revoke_session(session, principal)
    with pytest.raises(AuthenticationRequired):
        await authenticate(session, flow_db.token)
    with pytest.raises(AuthenticationRequired):
        await validate_principal(session, principal, lock=True)
    user = await session.get(AuthUser, principal.user_id)
    token, new = await issue_session(session, user)
    assert new.session_id != principal.session_id and token != flow_db.token
    await session.execute(
        update(AuthSession)
        .where(AuthSession.id == new.session_id)
        .values(
            created_at=datetime.now(UTC) - timedelta(hours=2),
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        )
    )
    with pytest.raises(AuthenticationRequired):
        await authenticate(session, token)
    token, newer = await issue_session(session, user)
    user.disabled_at = datetime.now(UTC)
    await session.flush()
    with pytest.raises(AuthenticationRequired):
        await authenticate(session, token)


@pytest.mark.parametrize(
    "case",
    [
        "digest",
        "infinity",
        "expiry",
        "revocation",
        "user_fk",
        "identity_empty",
        "identity_unique",
        "token_unique",
        "root_fk",
    ],
)
async def test_database_constraints(flow_db, case):
    session = flow_db.session
    now = datetime.now(UTC)
    async with session.begin_nested():
        existing = await session.get(AuthSession, flow_db.principal.session_id)
        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                if case.startswith("identity"):
                    if case == "identity_unique":
                        session.add(
                            AuthIdentity(
                                id=uuid4(),
                                user_id=flow_db.principal.user_id,
                                issuer="test",
                                subject="same",
                            )
                        )
                        await session.flush()
                    session.add(
                        AuthIdentity(
                            id=uuid4(),
                            user_id=flow_db.principal.user_id,
                            issuer="" if case == "identity_empty" else "test",
                            subject="same",
                        )
                    )
                elif case == "root_fk":
                    await session.execute(
                        text(
                            "INSERT INTO stocks(stock_code,stock_name) VALUES('999991','fixture')"
                        )
                    )
                    session.add(
                        FlowReport(
                            id=uuid4(), stock_code="999991", owner_user_id=uuid4()
                        )
                    )
                else:
                    values = dict(
                        id=uuid4(),
                        user_id=flow_db.principal.user_id,
                        token_digest=b"x" * 32,
                        created_at=now,
                        expires_at=now + timedelta(hours=1),
                    )
                    if case == "digest":
                        values["token_digest"] = b"x"
                    if case == "expiry":
                        values["expires_at"] = now
                    if case == "revocation":
                        values["revoked_at"] = now - timedelta(seconds=1)
                    if case == "user_fk":
                        values["user_id"] = uuid4()
                    if case == "token_unique":
                        values["token_digest"] = existing.token_digest
                    if case == "infinity":
                        await session.execute(
                            text(
                                "INSERT INTO auth_sessions(id,user_id,token_digest,expires_at) VALUES(:id,:user,:digest,'infinity')"
                            ),
                            {
                                "id": uuid4(),
                                "user": flow_db.principal.user_id,
                                "digest": b"q" * 32,
                            },
                        )
                    else:
                        session.add(AuthSession(**values))
                await session.flush()


async def test_owner_a_b_untrusted_principal_and_authorize_before_payload(flow_db):
    report = await save(flow_db)
    session = flow_db.session
    b = AuthUser(id=uuid4())
    session.add(b)
    await session.flush()
    token, principal = await issue_session(session, b)
    await session.commit()
    session.expire_all()
    other = FlowReportService(session, principal=principal)
    assert await other.get_report(report.report_id) is None
    assert not (await other.list_reports(stock_code=None, limit=20, offset=0)).items
    assert (await other.list_report_archive()).total == 0
    assert not await other.delete_report(report.report_id)
    # Corruption belonging to A must never be reconstructed by B.
    await session.execute(
        update(FlowReportVerification)
        .where(FlowReportVerification.report_id == report.report_id)
        .values(checks={"broken": True})
    )
    await session.commit()
    assert await other.get_report(report.report_id) is None
    assert not await other.delete_report(report.report_id)
    with pytest.raises(AuthenticationRequired):
        await FlowReportService(session).get_report(report.report_id)
    from dataclasses import replace

    with pytest.raises(AuthenticationRequired):
        await FlowReportService(
            session, principal=replace(principal, user_id=flow_db.principal.user_id)
        ).delete_report(report.report_id)


@pytest.mark.parametrize("damage", ["null", "mismatch", "duplicate", "orphan"])
async def test_projection_fail_closed_in_sql(flow_db, damage):
    report = await save(flow_db)
    session = flow_db.session
    index = await session.scalar(
        select(AgentReport).where(AgentReport.agent_report_id == report.report_id)
    )
    if damage == "duplicate":
        session.add(
            AgentReport(
                id=uuid4(),
                agent_type="flow",
                agent_report_id=report.report_id,
                owner_user_id=flow_db.principal.user_id,
            )
        )
    elif damage == "orphan":
        await session.execute(
            delete(FlowReport).where(FlowReport.id == report.report_id)
        )
    elif damage == "null":
        index.owner_user_id = None
    else:
        index.owner_user_id = uuid4()
    await session.commit()
    session.expire_all()
    assert await flow_db.service.get_report(report.report_id) is None
    assert not await flow_db.service.delete_report(report.report_id)
    assert not await list_owned_indexes(
        session, owner_user_id=flow_db.principal.user_id
    )
    assert (
        await list_owned_indexes(
            session, owner_user_id=flow_db.principal.user_id, count=True
        )
        == 0
    )
    assert (await flow_db.service.list_report_archive()).total == 0


async def test_owned_pagination_count_delete_and_stock_preserved(flow_db):
    reports = [await save(flow_db) for _ in range(3)]
    session = flow_db.session
    session.expire_all()
    first = await flow_db.service.list_report_archive(limit=1, offset=0)
    second = await flow_db.service.list_report_archive(limit=1, offset=1)
    assert first.total == second.total == 3
    assert first.items[0].report_id != second.items[0].report_id
    assert await flow_db.service.delete_report(reports[0].report_id)
    assert not await flow_db.service.delete_report(reports[0].report_id)
    assert await flow_db.service.get_report(reports[0].report_id) is None
    assert (await flow_db.service.list_report_archive()).total == 2
    assert await session.get(Stock, "005930") is not None


async def test_actual_backend_http_internal_a_b_session_and_csrf(flow_db, monkeypatch):
    """Actual FastAPI + real DB; provider identity prepared internally, not Google login."""
    from types import SimpleNamespace
    from httpx import AsyncClient, ASGITransport
    from src.api.main import app
    from src.modules.auth.api import router as auth
    from src.modules.auth.infrastructure.google_oidc import GoogleConfig
    from db.session import get_session

    saved = await save(flow_db)
    session = flow_db.session
    b = AuthUser(id=uuid4())
    session.add(b)
    await session.flush()
    token_b, _ = await issue_session(session, b)
    await session.commit()
    monkeypatch.setattr(
        auth,
        "get_oidc",
        lambda: SimpleNamespace(
            config=GoogleConfig(
                "fixture",
                "synthetic-secret",
                "https://app.unit/api/auth/callback",
                ("https://app.unit",),
            )
        ),
    )

    async def test_session():
        yield session

    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_session] = test_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="https://backend.unit"
        ) as client:
            path = f"/api/flow/reports/{saved.report_id}"
            assert (await client.get(path)).status_code == 401
            assert (
                await client.get(
                    path, headers={"X-User-ID": str(flow_db.principal.user_id)}
                )
            ).status_code == 401
            cookie_a = {"Cookie": f"verith_session={flow_db.token}"}
            cookie_b = {"Cookie": f"verith_session={token_b}"}
            response = await client.get(path, headers=cookie_a)
            assert response.status_code == 200
            assert response.headers["cache-control"] == "private, no-store"
            assert (await client.get(path, headers=cookie_b)).status_code == 404
            assert (await client.get("/api/reports/archive", headers=cookie_a)).json()[
                "total"
            ] == 1
            assert (await client.get("/api/reports/archive", headers=cookie_b)).json()[
                "total"
            ] == 0
            assert (
                await client.get(
                    "/api/reports/archive?agent_type=technical", headers=cookie_a
                )
            ).status_code == 403
            for forbidden in [
                "/api/flow/reports/save",
                "/api/technical/reports",
                "/api/news/reports",
            ]:
                assert (
                    await client.post(forbidden, headers=cookie_a, json={})
                ).status_code == 403
            assert (
                await client.delete("/api/flow/reports", headers=cookie_a)
            ).status_code == 403
            assert (await client.delete(path, headers=cookie_a)).status_code == 401
            csrf = (await client.get("/api/auth/session", headers=cookie_a)).json()[
                "csrf_token"
            ]
            bad = {**cookie_a, "X-CSRF-Token": csrf, "Origin": "https://evil.unit"}
            assert (await client.delete(path, headers=bad)).status_code == 401
            valid = {**cookie_a, "X-CSRF-Token": csrf, "Origin": "https://app.unit"}
            assert (await client.delete(path, headers=valid)).status_code == 204
            assert (await client.delete(path, headers=valid)).status_code == 404
            assert (
                await client.post("/api/auth/logout", headers=valid)
            ).status_code == 200
            assert (
                await client.get("/api/auth/session", headers=cookie_a)
            ).status_code == 401
            assert (await client.get(path, headers=cookie_a)).status_code == 401
            assert (
                await client.get("/api/auth/session", headers=cookie_b)
            ).status_code == 200
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


async def test_signed_synthetic_google_callback_commits_revocable_session(
    flow_db, monkeypatch
):
    """Synthetic signed Google-shaped protocol over MockTransport + real PG; no Google login."""
    from httpx import AsyncClient, ASGITransport
    from src.api.main import app
    from src.modules.auth.api import router as auth
    from db.session import get_session
    from tests.unit.test_cf002_google import (
        provider as provider_fixture,
        rsa as rsa_fixture,
    )
    from urllib.parse import urlsplit, parse_qs
    import time

    oidc, state = provider_fixture.__wrapped__(rsa_fixture.__wrapped__())
    monkeypatch.setattr(auth, "get_oidc", lambda: oidc)
    session = flow_db.session

    async def test_session():
        yield session

    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_session] = test_session
    initial = await session.scalar(select(func.count()).select_from(AuthUser))
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="https://backend.unit"
        ) as client:
            ids = []
            old_cookie = None
            for issuer in ["accounts.google.com", "https://accounts.google.com"]:
                started = await client.get("/api/auth/login")
                assert started.status_code == 303
                q = parse_qs(urlsplit(started.headers["location"]).query)
                now = int(time.time())
                state["claims"] = {
                    "iss": issuer,
                    "aud": oidc.config.client_id,
                    "sub": "same-sub",
                    "nonce": q["nonce"][0],
                    "iat": now,
                    "exp": now + 300,
                }
                callback = await client.get(
                    "/api/auth/callback",
                    params={"state": q["state"][0], "code": "synthetic-code"},
                )
                assert callback.status_code == 303
                assert (
                    "HttpOnly" in callback.headers["set-cookie"]
                    and "Secure" in callback.headers["set-cookie"]
                )
                token = client.cookies.get(auth.SESSION_COOKIE)
                info = await client.get("/api/auth/session")
                assert info.status_code == 200
                ids.append(info.json()["user_id"])
                if old_cookie:
                    assert old_cookie != token
                    assert (
                        await client.get(
                            "/api/auth/session",
                            headers={"Cookie": f"verith_session={old_cookie}"},
                        )
                    ).status_code == 401
                old_cookie = token
            assert ids[0] == ids[1]
            assert (
                await session.scalar(select(func.count()).select_from(AuthUser))
                == initial + 1
            )
            assert (
                await session.scalar(select(func.count()).select_from(AuthIdentity))
                == 1
            )
            before = await session.scalar(select(func.count()).select_from(AuthSession))
            started = await client.get("/api/auth/login")
            q = parse_qs(urlsplit(started.headers["location"]).query)
            state["claims"]["nonce"] = "wrong"
            failed = await client.get(
                "/api/auth/callback",
                params={"state": q["state"][0], "code": "bad-code"},
            )
            assert (
                failed.status_code == 400
                and failed.json()["detail"]["code"] == "LOGIN_FAILED"
            )
            assert (
                await session.scalar(select(func.count()).select_from(AuthSession))
                == before
            )
            assert (
                await session.scalar(select(func.count()).select_from(AuthUser))
                == initial + 1
            )
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


async def test_delete_failure_rolls_back_index_and_root(flow_db, monkeypatch):
    from src.modules.flow.application import report_service as module

    saved = await save(flow_db)

    async def failed_root(*args, **kwargs):
        raise RuntimeError("synthetic delete failure")

    monkeypatch.setattr(module.flow_repo, "delete_root", failed_root)
    with pytest.raises(RuntimeError, match="synthetic delete failure"):
        await flow_db.service.delete_report(saved.report_id)
    flow_db.session.expire_all()
    assert await flow_db.service.get_report(saved.report_id) is not None
    assert (
        await flow_db.session.scalar(
            select(func.count())
            .select_from(AgentReport)
            .where(AgentReport.agent_report_id == saved.report_id)
        )
        == 1
    )


async def test_internal_save_does_not_adopt_legacy_or_overwrite_existing_id(flow_db):
    from src.modules.flow.application.report_service import FlowStoredPayloadError

    saved = await save(flow_db)
    session = flow_db.session
    payload = saved.report
    req = FlowReportSaveRequest(
        payload=payload, question="same ID retry must not overwrite"
    )
    with pytest.raises(FlowStoredPayloadError):
        await flow_db.service.save_report(req)
    assert (await flow_db.service.get_report(saved.report_id)).report == payload
    await session.execute(
        update(FlowReport)
        .where(FlowReport.id == saved.report_id)
        .values(owner_user_id=None)
    )
    await session.commit()
    with pytest.raises(FlowStoredPayloadError):
        await flow_db.service.save_report(req)
    assert (
        await session.scalar(
            select(FlowReport.owner_user_id).where(FlowReport.id == saved.report_id)
        )
        is None
    )
    assert (
        await session.scalar(
            select(func.count())
            .select_from(FlowReport)
            .where(FlowReport.id == saved.report_id)
        )
        == 1
    )
