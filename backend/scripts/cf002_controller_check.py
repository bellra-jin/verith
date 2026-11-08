"""Synthetic principals on a fresh owned DB only; never real OAuth evidence."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update

from db.models.auth.models import AuthSession
from db.models.common.stock import Stock
from db.models.common.agent_report import AgentReport
from db.models.flow.flow_report import FlowReport
from scripts.cf002_interactive_login import database_status, owned_session
from scripts.google_login_controller import ControllerError, LoginController
from src.modules.auth.application.session_service import issue_session, link_verified_identity


async def verify_controller(proof):
    if any((await database_status(proof)).values()):
        raise RuntimeError(
            "Synthetic controller verification requires a fresh empty DB"
        )
    controller = LoginController(proof)

    async def refused(command, code):
        try:
            await controller.command(command)
        except ControllerError as exc:
            if str(exc) != code:
                raise RuntimeError("Unexpected private refusal") from None
        else:
            raise RuntimeError("Expected private refusal was missing")

    await refused("bind-B", "bind_A_first")
    await refused("bind-A", "active_google_owner_missing_or_ambiguous")
    async with owned_session(proof) as session:
        a = await link_verified_identity(
            session,
            issuer="https://accounts.google.com",
            subject="SYNTHETIC-CONTROLLER-A",
        )
        # Two sessions of one owner are not two accounts; choose latest only.
        await issue_session(session, a)
        await issue_session(session, a)
        foreign = await link_verified_identity(
            session, issuer="https://other.invalid", subject="SYNTHETIC-NON-GOOGLE"
        )
        await issue_session(session, foreign)
        disabled = await link_verified_identity(
            session, issuer="https://accounts.google.com", subject="SYNTHETIC-DISABLED"
        )
        await issue_session(session, disabled)
        disabled.disabled_at = datetime.now(UTC)
        await session.commit()
    await controller.command("bind-A")
    await refused("bind-A", "alias_already_bound")
    await refused("bind-B", "active_google_owner_missing_or_ambiguous")
    seed_a = await controller.command("seed-A")
    await refused("seed-A", "fixture_already_started")
    async with owned_session(proof) as session:
        b = await link_verified_identity(
            session,
            issuer="https://accounts.google.com",
            subject="SYNTHETIC-CONTROLLER-B",
        )
        await issue_session(session, b)
        ambiguous = await link_verified_identity(
            session, issuer="https://accounts.google.com", subject="SYNTHETIC-AMBIGUOUS"
        )
        await issue_session(session, ambiguous)
        await session.commit()
        ambiguous_id = ambiguous.id
    await refused("bind-B", "active_google_owner_missing_or_ambiguous")
    async with owned_session(proof) as session:
        await session.execute(
            update(AuthSession)
            .where(AuthSession.user_id == ambiguous_id)
            .values(revoked_at=func.clock_timestamp())
        )
        await session.commit()
    await controller.command("bind-B")
    seed_b = await controller.command("seed-B")
    # A newly made owner-NULL legacy fixture, never reassignment of existing data.
    from uuid import uuid4
    from src.modules.flow.application.report_service import FlowReportService

    legacy_id = uuid4()
    async with owned_session(proof) as session:
        session.add(Stock(stock_code="999985", stock_name="CF002 synthetic legacy"))
        await session.flush()
        session.add(FlowReport(id=legacy_id, stock_code="999985", owner_user_id=None))
        session.add(
            AgentReport(
                agent_type="flow",
                agent_report_id=legacy_id,
                stock_code="999985",
                owner_user_id=None,
            )
        )
        await session.commit()
    for alias in ("A", "B"):
        async with owned_session(proof) as session:
            service = FlowReportService(
                session, principal=await controller._principal(session, alias)
            )
            if await service.get_report(legacy_id) is not None:
                raise RuntimeError("Legacy fixture was visible")
            if await service.delete_report(legacy_id):
                raise RuntimeError("Legacy fixture was deleted")
            archive = await service.list_report_archive(stock_code="999985")
            if archive.total or archive.items:
                raise RuntimeError("Legacy fixture leaked through archive")
    checked = await controller.command("check-owner")
    if len(set(seed_a["synthetic_report_ids"] + seed_b["synthetic_report_ids"])) != 4:
        raise RuntimeError("Synthetic result IDs were not distinct")
    for alias in ("A", "B"):
        if (await controller.command(f"delete-{alias}"))["synthetic_deleted"] != 2:
            raise RuntimeError("Own synthetic delete failed")
        if (await controller.command(f"delete-{alias}"))["synthetic_deleted"] != 0:
            raise RuntimeError("Repeated own synthetic delete was not empty")
    async with owned_session(proof) as session:
        preserved = await session.scalar(
            select(func.count())
            .select_from(Stock)
            .where(Stock.stock_code.in_(["999987", "999986"]))
        )
        if preserved != 2:
            raise RuntimeError("Fixture stock preservation failed")
        legacy = await session.get(FlowReport, legacy_id)
        if legacy is None or legacy.owner_user_id is not None:
            raise RuntimeError("Owner-NULL legacy fixture was not preserved")
        # Expiry is persisted and checked using the same actual DB clock path.
        now = datetime.now(UTC)
        await session.execute(
            update(AuthSession)
            .where(AuthSession.id == controller._bindings["A"].session_id)
            .values(
                created_at=now - timedelta(seconds=120),
                expires_at=now - timedelta(seconds=60),
            )
        )
        await session.commit()
    await refused("delete-A", "bound_session_no_longer_active")
    async with owned_session(proof) as session:
        await session.execute(
            update(AuthSession)
            .where(AuthSession.id == controller._bindings["B"].session_id)
            .values(revoked_at=func.clock_timestamp())
        )
        await session.commit()
    await refused("delete-B", "bound_session_no_longer_active")
    counts = await database_status(proof)
    if counts["synthetic_reports"] != 1:
        raise RuntimeError("Synthetic report cleanup failed")
    return {
        "status": "passed",
        "principal_source": "synthetic_only",
        "actual_Google_A_B": "not_run",
        **checked,
        "same_account_and_ambiguous_binding": "refused",
        "expired_revoked_binding": "refused",
        "own_delete_repeat_and_stock_preservation": "passed",
        "owner_NULL_legacy_hidden_and_preserved_until_container_disposal": "passed",
        "counts": counts,
    }
