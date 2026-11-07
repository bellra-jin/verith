"""Opt-in PostgreSQL tests. No app-DB fallback, migration, AI, or persistent seed."""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest
import pytest_asyncio
from dotenv import dotenv_values
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from db.models.common.agent_report import AgentReport
from db.models.flow.flow_report import FlowReport
from src.api.services.flow_report_service import FlowReportService
from tests.db_safety import (
    UnsafeTestDatabase,
    preflight_database,
    attest_engine_connection,
)


@pytest_asyncio.fixture
async def flow_db():
    values = dotenv_values(Path(__file__).resolve().parents[2] / ".env")
    raw_app = os.getenv("DATABASE_URL") or values.get("DATABASE_URL")
    try:
        approval = await preflight_database(os.environ, raw_app)
    except UnsafeTestDatabase as exc:
        pytest.fail(str(exc), pytrace=False)
    engine = create_async_engine(
        approval.url, connect_args={**approval.connection_parameters(), "timeout": 3}
    )
    connection = None
    connection_error = None
    try:
        connection = await engine.connect()
    except Exception as exc:
        connection_error = type(exc).__name__
    if connection_error:
        await engine.dispose()
        pytest.fail(
            f"Dedicated test DB unavailable ({connection_error}); no app DB fallback",
            pytrace=False,
        )
    assert connection is not None
    outer = None
    session = None

    class TestContext(SimpleNamespace):
        def __repr__(self):
            return "<isolated Flow test context>"

    context = TestContext(report_ids=[])
    try:
        # Read-only readiness checks before beginning the rollback-isolated test.
        await attest_engine_connection(connection, approval)
        assert (
            await connection.scalar(text("SELECT current_database()"))
            == approval.database
        )
        for table in (
            "stocks",
            "flow_reports",
            "flow_report_interpretations",
            "flow_report_verifications",
            "agent_reports",
        ):
            exists = await connection.scalar(
                text("SELECT to_regclass(:table) IS NOT NULL"),
                {"table": f"public.{table}"},
            )
            assert exists, (
                "Test schema is not ready; migrations are not run by this suite"
            )
        await connection.rollback()
        outer = await connection.begin()
        session = AsyncSession(
            bind=connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        )
        context.session = session
        from db.models.auth.models import AuthUser
        from src.api.services.auth_service import issue_session
        from uuid import uuid4

        user = AuthUser(id=uuid4())
        session.add(user)
        await session.flush()
        token, principal = await issue_session(session, user)
        await session.commit()
        context.principal = principal
        context.token = token
        context.service = FlowReportService(session, principal=principal)
        yield context
    finally:
        if session is not None:
            await session.close()
        if outer is not None:
            await outer.rollback()
        try:
            # Service commit must not escape the outer rollback.
            if context.report_ids:
                for model, column in (
                    (FlowReport, FlowReport.id),
                    (AgentReport, AgentReport.agent_report_id),
                ):
                    count = await connection.scalar(
                        select(func.count())
                        .select_from(model)
                        .where(column.in_(context.report_ids))
                    )
                    assert count == 0, "Test result survived rollback"
        finally:
            await connection.close()
            await engine.dispose()
