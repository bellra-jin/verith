"""Private, runner-owned fixture control; no HTTP endpoints or browser credentials.

Aliases are process-local. Eligibility means a canonical Google identity and an
active DB session, not proof of browser behavior. Synthetic verification mode
must always be reported separately from real Google callback/login evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4

from sqlalchemy import exists, func, select

from db.models.auth.models import AuthIdentity, AuthSession, AuthUser
from scripts.runner_owned_database import RunnerOwnedDatabase
from src.modules.auth.application.session_service import Principal, validate_principal


class ControllerError(ValueError):
    """Only fixed, credential-free codes may reach the private command output."""


@dataclass(repr=False)
class Binding:
    user_id: UUID
    session_id: UUID
    reports: list[UUID] = field(default_factory=list)
    seeded: bool = False


def eligible_sessions():
    # Do not select subject, bearer tokens, or any external account profile.
    identity = exists().where(
        AuthIdentity.user_id == AuthUser.id,
        AuthIdentity.issuer == "https://accounts.google.com",
    )
    return (
        select(AuthSession)
        .join(AuthUser, AuthUser.id == AuthSession.user_id)
        .where(
            AuthUser.disabled_at.is_(None),
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > func.clock_timestamp(),
            identity,
        )
        .order_by(AuthSession.created_at.desc(), AuthSession.id)
    )


def choose_candidate(rows, excluded):
    candidates = [row for row in rows if row.user_id not in excluded]
    if len({row.user_id for row in candidates}) != 1:
        raise ControllerError("active_google_owner_missing_or_ambiguous")
    return candidates[0]


class LoginController:
    def __init__(self, proof):
        if not isinstance(proof, RunnerOwnedDatabase):
            raise ControllerError("runner_owned_capability_required")
        self._proof = proof
        self._bindings: dict[str, Binding] = {}

    def _session(self):
        # Import lazily: the owning runner also exposes the command dispatcher.
        from scripts.cf002_interactive_login import owned_session

        return owned_session(self._proof)

    @staticmethod
    def _alias(alias):
        if alias not in ("A", "B"):
            raise ControllerError("invalid_alias")

    def _binding(self, alias):
        self._alias(alias)
        if alias not in self._bindings:
            raise ControllerError("alias_not_bound")
        return self._bindings[alias]

    async def bind(self, alias):
        self._alias(alias)
        if alias in self._bindings:
            raise ControllerError("alias_already_bound")
        if alias == "B" and "A" not in self._bindings:
            raise ControllerError("bind_A_first")
        async with self._session() as session:
            rows = (await session.scalars(eligible_sessions())).all()
            row = choose_candidate(
                rows, {bound.user_id for bound in self._bindings.values()}
            )
            self._bindings[alias] = Binding(row.user_id, row.id)
        return {"alias": alias, "bound": True, "distinct_owner": True}

    async def _principal(self, session, alias):
        bound = self._binding(alias)
        row = await session.scalar(
            eligible_sessions().where(
                AuthSession.id == bound.session_id,
                AuthSession.user_id == bound.user_id,
            )
        )
        if row is None:
            raise ControllerError("bound_session_no_longer_active")
        principal = Principal(row.user_id, row.id, row.expires_at, row.token_digest)
        await validate_principal(session, principal)
        return principal

    @staticmethod
    def ticker(alias):
        LoginController._alias(alias)
        return {"A": "999987", "B": "999986"}[alias]

    async def seed(self, alias):
        from src.modules.flow.api.schemas import FlowReportSaveRequest
        from src.modules.flow.application.report_service import FlowReportService
        from tests.fixtures.flow_payload import make_flow_payload

        bound = self._binding(alias)
        if bound.reports:
            # Partial/ambiguous writes retain their known IDs; never blindly retry.
            raise ControllerError("fixture_already_started")
        async with self._session() as session:
            principal = await self._principal(session, alias)
            service = FlowReportService(session, principal=principal)
            for index in range(2):
                payload = make_flow_payload()
                payload["report_id"] = str(uuid4())
                payload["meta"].update(
                    ticker=self.ticker(alias), stock_name=f"CF002 합성 {alias}"
                )
                report_id = UUID(payload["report_id"])
                bound.reports.append(report_id)  # Track before any possible commit.
                saved = await service.save_report(
                    FlowReportSaveRequest(
                        payload=payload, question=f"CF002 synthetic {alias} {index + 1}"
                    )
                )
                if saved.report_id != report_id:
                    raise ControllerError("fixture_result_id_mismatch")
            bound.seeded = True
        return {
            "alias": alias,
            "synthetic_report_ids": [str(value) for value in bound.reports],
            "count": len(bound.reports),
        }

    async def check_owner(self):
        from src.modules.flow.application.report_service import FlowReportService

        for alias, other in (("A", "B"), ("B", "A")):
            bound, foreign = self._binding(alias), self._binding(other)
            if not bound.seeded or not foreign.seeded:
                raise ControllerError("both_fixtures_required")
            async with self._session() as session:
                service = FlowReportService(
                    session, principal=await self._principal(session, alias)
                )
                own = await service.list_report_archive(stock_code=self.ticker(alias))
                hidden = await service.list_report_archive(
                    stock_code=self.ticker(other)
                )
                first = await service.list_report_archive(
                    stock_code=self.ticker(alias), limit=1, offset=0
                )
                second = await service.list_report_archive(
                    stock_code=self.ticker(alias), limit=1, offset=1
                )
                if (
                    own.total != 2
                    or {row.report_id for row in own.items} != set(bound.reports)
                    or hidden.total != 0
                    or hidden.items
                    or first.total != 2
                    or second.total != 2
                    or len(first.items) != 1
                    or len(second.items) != 1
                    or first.items[0].report_id == second.items[0].report_id
                ):
                    raise ControllerError("fixture_list_or_count_mismatch")
                for report_id in bound.reports:
                    if await service.get_report(report_id) is None:
                        raise ControllerError("own_fixture_missing")
                for report_id in foreign.reports:
                    if await service.get_report(report_id) is not None:
                        raise ControllerError("foreign_fixture_visible")
                    if await service.delete_report(report_id):
                        raise ControllerError("foreign_fixture_deleted")
        return {
            "internal_service_owner_check": "passed",
            "browser_BFF_SSR": "not_verified_by_controller",
        }

    async def delete_fixture(self, alias):
        """Only this controller's recorded synthetic IDs, never a blanket delete."""
        from src.modules.flow.application.report_service import FlowReportService

        bound = self._binding(alias)
        deleted = 0
        async with self._session() as session:
            service = FlowReportService(
                session, principal=await self._principal(session, alias)
            )
            for report_id in bound.reports:
                deleted += bool(await service.delete_report(report_id))
        return {"alias": alias, "synthetic_deleted": deleted}

    async def command(self, command):
        if command == "check-owner":
            return await self.check_owner()
        for verb, action in (
            ("bind", self.bind),
            ("seed", self.seed),
            ("delete", self.delete_fixture),
        ):
            if command in (f"{verb}-A", f"{verb}-B"):
                return await action(command[-1])
        raise ControllerError("unknown_private_command")
