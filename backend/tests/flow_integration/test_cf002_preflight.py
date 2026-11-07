"""Real approved disposable DB checks, not real OIDC/owner acceptance."""

import json
import os
from unittest.mock import AsyncMock, Mock

import asyncpg
import pytest
from sqlalchemy import func, select
from sqlalchemy.engine import make_url

from db.models.common.stock import Stock
from tests.db_safety import UnsafeTestDatabase, preflight_database


@pytest.mark.parametrize(
    "problem", ["missing_approval", "wrong_port", "app_alias", "wrong_resource"]
)
async def test_actual_disposable_db_rejects_bad_approval_without_writes(
    flow_db, monkeypatch, problem
):
    environ = dict(os.environ)
    app_url = environ["DATABASE_URL"]
    manifest = json.loads(environ["TEST_DATABASE_APPROVAL"])
    if problem == "missing_approval":
        environ.pop("TEST_DATABASE_APPROVAL")
    elif problem == "wrong_port":
        manifest["port"] += 1
    elif problem == "app_alias":
        app_url = (
            make_url(environ["TEST_DATABASE_URL"])
            .set(host="LOCALHOST.")
            .render_as_string(hide_password=False)
        )
    else:
        manifest["resource_id"] = "not-the-approved-disposable-resource"
    if problem != "missing_approval":
        environ["TEST_DATABASE_APPROVAL"] = json.dumps(manifest)
    connect = AsyncMock(wraps=asyncpg.connect)
    engine = Mock(side_effect=AssertionError("engine created for rejected target"))
    monkeypatch.setattr("sqlalchemy.ext.asyncio.create_async_engine", engine)
    before = await flow_db.session.scalar(select(func.count()).select_from(Stock))
    with pytest.raises(UnsafeTestDatabase):
        await preflight_database(environ, app_url, connect=connect)
    if problem == "wrong_resource":
        connect.assert_awaited_once()  # Approved target only, read-only attestation rejects it.
    else:
        connect.assert_not_awaited()
    engine.assert_not_called()
    assert (
        await flow_db.session.scalar(select(func.count()).select_from(Stock)) == before
    )
