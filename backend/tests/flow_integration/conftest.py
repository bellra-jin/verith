"""Opt-in PostgreSQL tests. No app-DB fallback, migration, AI, or persistent seed."""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest
import pytest_asyncio
from dotenv import dotenv_values
from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from db.models.common.agent_report import AgentReport
from db.models.flow.flow_report import FlowReport
from src.api.services.flow_report_service import FlowReportService


@pytest_asyncio.fixture
async def flow_db():
    if os.getenv("CF001_RUN_DB_TESTS") != "1":
        pytest.skip(
            "Opt in with CF001_RUN_DB_TESTS=1 after verifying verith_test isolation"
        )
    values = dotenv_values(Path(__file__).resolve().parents[2] / ".env")
    raw_test = os.getenv("TEST_DATABASE_URL") or values.get("TEST_DATABASE_URL")
    raw_app = os.getenv("DATABASE_URL") or values.get("DATABASE_URL")
    if not raw_test:
        pytest.fail(
            "TEST_DATABASE_URL is required; app DB fallback is forbidden", pytrace=False
        )
    target = make_url(raw_test)
    app_target = make_url(raw_app) if raw_app else None
    if (
        target.database != "verith_test"
        or target.host not in ("localhost", "127.0.0.1", "::1")
        or app_target is None
        or app_target.database == target.database
    ):
        pytest.fail(
            "Only the documented local verith_test, distinct from app DB, is allowed",
            pytrace=False,
        )
    engine = create_async_engine(target, connect_args={"timeout": 3})
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
    context = SimpleNamespace(report_ids=[])
    try:
        # Read-only readiness checks before beginning the rollback-isolated test.
        assert (
            await connection.scalar(text("SELECT current_database()")) == "verith_test"
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
        context.service = FlowReportService(session)
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
