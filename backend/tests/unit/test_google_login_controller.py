"""No Docker, Google, DB, browser session, or real .env is used here."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from scripts import google_login_controller as control


def row(user=None):
    return SimpleNamespace(
        id=uuid4(),
        user_id=user or uuid4(),
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
        token_digest=b"FAKE-DIGEST-NEVER-A-BEARER-00000000",
    )


def controller_with(session):
    controller = object.__new__(control.LoginController)
    controller._bindings = {}
    controller._proof = None

    @asynccontextmanager
    async def scope():
        yield session

    controller._session = scope
    return controller


def test_requires_live_owned_capability_not_url_receipt_or_header():
    for untrusted in (None, "postgresql://fake", {"resource_id": "fake"}, uuid4()):
        with pytest.raises(
            control.ControllerError, match="runner_owned_capability_required"
        ):
            control.LoginController(untrusted)


def test_eligibility_sql_does_not_select_external_subject_and_requires_active_google():
    sql = str(control.eligible_sessions().compile(dialect=postgresql.dialect()))
    assert "subject" not in sql
    assert "auth_identities.issuer" in sql
    assert "auth_sessions.revoked_at IS NULL" in sql
    assert "auth_sessions.expires_at > clock_timestamp()" in sql
    assert "auth_users.disabled_at IS NULL" in sql
    assert "EXISTS" in sql


def test_one_owner_many_sessions_and_distinct_owner_selection():
    a = row()
    older_a = row(a.user_id)
    b = row()
    assert control.choose_candidate([a, older_a], set()) is a
    assert control.choose_candidate([a, b], {a.user_id}) is b
    for rows, excluded in (([], set()), ([a, b], set()), ([a], {a.user_id})):
        with pytest.raises(control.ControllerError, match="missing_or_ambiguous"):
            control.choose_candidate(rows, excluded)


@pytest.mark.asyncio
async def test_binding_distinct_owners_has_no_identity_or_session_output():
    a, b = row(), row()
    session = SimpleNamespace(scalars=AsyncMock())
    session.scalars.side_effect = [
        SimpleNamespace(all=lambda: [a]),
        SimpleNamespace(all=lambda: [a, b]),
    ]
    controller = controller_with(session)
    assert await controller.bind("A") == {
        "alias": "A",
        "bound": True,
        "distinct_owner": True,
    }
    assert await controller.bind("B") == {
        "alias": "B",
        "bound": True,
        "distinct_owner": True,
    }
    assert controller._bindings["A"].user_id != controller._bindings["B"].user_id
    assert str(a.user_id) not in repr(controller._bindings["A"])
    assert not hasattr(controller._bindings["A"], "token_digest")


@pytest.mark.asyncio
async def test_alias_order_duplicate_and_unknown_commands_refused_before_db():
    session = SimpleNamespace(scalars=AsyncMock())
    controller = controller_with(session)
    for command, code in (
        ("bind-B", "bind_A_first"),
        ("bind-FAKE_PRIVATE_INPUT", "unknown_private_command"),
        ("seed-A", "alias_not_bound"),
    ):
        with pytest.raises(control.ControllerError, match=code):
            await controller.command(command)
    controller._bindings["A"] = control.Binding(uuid4(), uuid4())
    with pytest.raises(control.ControllerError, match="alias_already_bound"):
        await controller.bind("A")
    session.scalars.assert_not_awaited()


@pytest.mark.asyncio
async def test_expired_revoked_disabled_or_missing_identity_rejected_before_service(
    monkeypatch,
):
    session = SimpleNamespace(scalar=AsyncMock(return_value=None))
    controller = controller_with(session)
    controller._bindings["A"] = control.Binding(uuid4(), uuid4())
    validate = AsyncMock()
    monkeypatch.setattr(control, "validate_principal", validate)
    with pytest.raises(control.ControllerError, match="bound_session_no_longer_active"):
        await controller.delete_fixture("A")
    validate.assert_not_awaited()


@pytest.mark.asyncio
async def test_principal_revalidated_without_minting_bearer(monkeypatch):
    a = row()
    session = SimpleNamespace(scalar=AsyncMock(return_value=a))
    controller = controller_with(session)
    controller._bindings["A"] = control.Binding(a.user_id, a.id)
    validate = AsyncMock()
    monkeypatch.setattr(control, "validate_principal", validate)
    principal = await controller._principal(session, "A")
    validate.assert_awaited_once_with(session, principal)
    assert principal.user_id == a.user_id and principal.session_id == a.id
    assert "FAKE-DIGEST" not in repr(principal)


@pytest.mark.asyncio
async def test_partial_save_tracks_known_id_and_refuses_blind_retry(monkeypatch):
    from src.api.services.flow_report_service import FlowReportService

    a = row()
    controller = controller_with(SimpleNamespace(scalar=AsyncMock(return_value=a)))
    controller._bindings["A"] = control.Binding(a.user_id, a.id)
    monkeypatch.setattr(control, "validate_principal", AsyncMock())
    save = AsyncMock(side_effect=RuntimeError("SYNTHETIC PRIVATE ERROR"))
    monkeypatch.setattr(FlowReportService, "save_report", save)
    with pytest.raises(RuntimeError):
        await controller.seed("A")
    assert len(controller._bindings["A"].reports) == 1
    assert controller._bindings["A"].seeded is False
    with pytest.raises(control.ControllerError, match="fixture_already_started"):
        await controller.seed("A")
    save.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_only_recorded_ids_and_own_active_principal(monkeypatch):
    from src.api.services.flow_report_service import FlowReportService

    a = row()
    controller = controller_with(SimpleNamespace(scalar=AsyncMock(return_value=a)))
    ids = [uuid4(), uuid4()]
    controller._bindings["A"] = control.Binding(a.user_id, a.id, ids, True)
    monkeypatch.setattr(control, "validate_principal", AsyncMock())
    delete = AsyncMock(side_effect=[True, False])
    monkeypatch.setattr(FlowReportService, "delete_report", delete)
    assert await controller.delete_fixture("A") == {
        "alias": "A",
        "synthetic_deleted": 1,
    }
    assert [call.args[0] for call in delete.await_args_list] == ids
