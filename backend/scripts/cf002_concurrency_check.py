"""Committed isolated-DB identity race and session revoke/delete serialization."""

from __future__ import annotations
import asyncio
import os
from pathlib import Path
import sys
from uuid import uuid4
from contextlib import asynccontextmanager

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import dotenv_values
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from tests.db_safety import preflight_database, attest_engine_connection
from db.models.auth.models import AuthIdentity, AuthSession, AuthUser
from db.models.common.stock import Stock
from src.api.services.auth_service import (
    link_verified_identity,
    issue_session,
    validate_principal,
    revoke_session,
    AuthenticationRequired,
)
from src.api.services.flow_report_service import FlowReportService
from src.api.schemas.flow_report import FlowReportSaveRequest
from tests.fixtures.flow_payload import make_flow_payload


async def main():
    app_url = os.getenv("DATABASE_URL") or dotenv_values(".env").get("DATABASE_URL")
    approval = await preflight_database(os.environ, app_url)
    engine = create_async_engine(
        approval.url, connect_args=approval.connection_parameters()
    )
    issuer = "urn:verith:cf002:fixture:" + uuid4().hex
    user_id = None
    report_id = None

    @asynccontextmanager
    async def verified_session():
        async with engine.connect() as connection:
            await attest_engine_connection(connection, approval)
            async with AsyncSession(bind=connection, expire_on_commit=False) as session:
                yield session

    try:
        # Both transactions see no identity before the first insert is committed.
        ready = asyncio.Event()
        async with verified_session() as first, verified_session() as second:
            original_count = await first.scalar(
                select(func.count()).select_from(AuthUser)
            )

            async def winner():
                user = await link_verified_identity(
                    first, issuer=issuer, subject="race"
                )
                ready.set()
                await asyncio.sleep(0.15)
                await first.commit()
                return user.id

            async def loser():
                await ready.wait()
                user = await link_verified_identity(
                    second, issuer=issuer, subject="race"
                )
                await second.commit()
                return user.id

            ids = await asyncio.wait_for(asyncio.gather(winner(), loser()), timeout=10)
            assert ids[0] == ids[1]
            user_id = ids[0]
            assert (
                await first.scalar(select(func.count()).select_from(AuthUser))
                == original_count + 1
            )
            assert (
                await first.scalar(
                    select(func.count())
                    .select_from(AuthIdentity)
                    .where(AuthIdentity.issuer == issuer)
                )
                == 1
            )
            user = await first.get(AuthUser, user_id)
            token, principal = await issue_session(first, user)
            payload = make_flow_payload()
            payload["meta"]["ticker"] = "999990"
            report = await FlowReportService(first, principal=principal).save_report(
                FlowReportSaveRequest(
                    payload=payload, question="isolated serialization fixture"
                )
            )
            report_id = report.report_id
        async with verified_session() as deleting, verified_session() as revoking:
            await validate_principal(deleting, principal, lock=True)
            task = asyncio.create_task(revoke_session(revoking, principal))
            await asyncio.sleep(0.1)
            assert not task.done(), (
                "Revoke UPDATE must wait for the protected transaction share lock"
            )
            assert await FlowReportService(deleting, principal=principal).delete_report(
                report_id
            )
            await asyncio.wait_for(task, timeout=5)
            try:
                await FlowReportService(deleting, principal=principal).delete_report(
                    report_id
                )
            except AuthenticationRequired:
                pass
            else:
                raise AssertionError(
                    "Revoked principal was reused after committed revocation"
                )
        # Exercise the real logout route on two distinct, pre-attested connections.
        # A short overlap after authentication also reproduces the old SHARE->UPDATE
        # deadlock deterministically instead of testing revoke_session in isolation.
        from httpx import ASGITransport, AsyncClient
        from unittest.mock import patch
        from types import SimpleNamespace
        from src.api.main import app
        from src.api.routes import auth
        from src.api.auth.google import GoogleConfig
        from src.api.services.auth_service import csrf_token
        from db.session import get_session

        async with verified_session() as setup:
            user = await setup.get(AuthUser, user_id)
            logout_token, logout_principal = await issue_session(setup, user)
            await setup.commit()
        arrivals, started = 0, asyncio.Event()
        real_authenticate = auth.authenticate

        async def overlapping_authenticate(*args, **kwargs):
            nonlocal arrivals
            arrivals += 1
            if arrivals >= 2:
                started.set()
            await asyncio.wait_for(started.wait(), timeout=5)
            result = await real_authenticate(*args, **kwargs)
            await asyncio.sleep(0.1)
            return result

        async def request_session():
            async with verified_session() as session:
                yield session

        previous = dict(app.dependency_overrides)
        app.dependency_overrides[get_session] = request_session
        config = GoogleConfig(
            "fixture",
            "synthetic-secret",
            "https://app.unit/api/auth/callback",
            ("https://app.unit",),
        )
        try:
            with (
                patch.object(
                    auth, "get_oidc", return_value=SimpleNamespace(config=config)
                ),
                patch.object(
                    auth, "authenticate", side_effect=overlapping_authenticate
                ),
            ):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="https://app.unit"
                ) as client:
                    headers = {
                        "Cookie": f"verith_session={logout_token}",
                        "Origin": "https://app.unit",
                        "X-CSRF-Token": csrf_token(logout_principal),
                    }
                    responses = await asyncio.wait_for(
                        asyncio.gather(
                            client.post("/api/auth/logout", headers=headers),
                            client.post("/api/auth/logout", headers=headers),
                        ),
                        timeout=8,
                    )
                    assert sorted(response.status_code for response in responses) == [
                        200,
                        401,
                    ], (
                        "Concurrent logout must commit once and reject the revoked session, without 503/deadlock"
                    )
                    success = next(
                        response
                        for response in responses
                        if response.status_code == 200
                    )
                    rejected = next(
                        response
                        for response in responses
                        if response.status_code == 401
                    )
                    assert (
                        "set-cookie" in success.headers
                        and "set-cookie" not in rejected.headers
                    )
                    for _ in range(2):
                        assert (
                            await client.post("/api/auth/logout", headers=headers)
                        ).status_code == 401
                    assert (
                        await client.get("/api/auth/session", headers=headers)
                    ).status_code == 401
        finally:
            app.dependency_overrides.clear()
            app.dependency_overrides.update(previous)
        async with verified_session() as check:
            row = await check.get(AuthSession, logout_principal.session_id)
            assert row.revoked_at is not None
        print(
            "Actual simultaneous logout HTTP routes: 200 + 401, repeats 401, no deadlock/503; old cookie reuse rejected",
            flush=True,
        )
        print(
            "Committed PostgreSQL identity race: one user/mapping, loser rollback; delete/share-lock/revoke serialization and post-revoke reuse rejection passed",
            flush=True,
        )
    finally:
        if user_id:
            async with verified_session() as cleanup:
                # Only rows created by this unique fixture; engine pre-attested again.
                await cleanup.execute(
                    delete(AuthSession).where(AuthSession.user_id == user_id)
                )
                await cleanup.execute(
                    delete(AuthIdentity).where(AuthIdentity.issuer == issuer)
                )
                await cleanup.execute(delete(AuthUser).where(AuthUser.id == user_id))
                await cleanup.execute(delete(Stock).where(Stock.stock_code == "999990"))
                await cleanup.commit()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
