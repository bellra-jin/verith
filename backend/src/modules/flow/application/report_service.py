"""flow report 저장/조회/삭제 오케스트레이션 — save-only.

news·fundamental save-only 와 같은 방식: supervisor 가 만든 flow payload(storage-spec v1)를
받아 flow 3테이블(root/interpretation/verification) + agent_reports 인덱스로 매핑·저장한다.
AI 를 다시 호출하지 않는다. 저장 시 승격 컬럼(ticker·stock_name·market·base_date·alignment)은
payload 에서 뽑아 채운다(storage-spec §3-3, 두 소스 금지). report_id 는 AI 발급 uuid4 를 PK 로
그대로 관통한다(§3-5, 확인 A).
"""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.common.agent_report import AgentReport
from db.models.flow.flow_report import FlowReport
from db.models.flow.report_interpretation import FlowReportInterpretation
from db.models.flow.report_verification import FlowReportVerification
from src.modules.reports.infrastructure import agent_report_repository as agent_repo
from src.modules.flow.infrastructure import report_repository as flow_repo
from src.modules.reports.api.report_schemas import AgentReportListItem
from src.modules.flow.domain.execution import ErrorCode, SafeError
from src.modules.flow.domain.payload import projection_values_equal, validate_flow_payload
from src.modules.flow.api.schemas import (
    FlowReportEnvelope,
    FlowReportListResponse,
    FlowReportSaveRequest,
)

from src.modules.auth.application.session_service import Principal, AuthenticationRequired, validate_principal

PAYLOAD_SNAPSHOT_KEY = "_flow_payload_snapshot"
STORAGE_FORMAT_KEY = "_flow_storage_format"
STORAGE_FORMAT = "flow-payload-snapshot.v1"


class FlowPayloadError(ValueError):
    """Safe error at the legacy save boundary, without raw validation input."""

    def __init__(self, code: ErrorCode = ErrorCode.INPUT_INVALID) -> None:
        self.error = SafeError(code=code)
        super().__init__(self.error.message)


class FlowStoredPayloadError(ValueError):
    """Stored/internal result is invalid and must not be returned as a normal result."""


class FlowReportIdConflict(FlowStoredPayloadError):
    """An existing root/index has conclusively claimed the requested report ID."""


class FlowReportService:
    def __init__(
        self, session: AsyncSession, *, principal: Principal | None = None
    ) -> None:
        self._session = session
        self._principal = principal

    async def _authorize(self, *, lock=False) -> Principal:
        if self._principal is None:
            raise AuthenticationRequired()
        await validate_principal(self._session, self._principal, lock=lock)
        return self._principal

    # ── 저장 ──────────────────────────────────────────────────────────────────
    async def save_report(self, req: FlowReportSaveRequest) -> FlowReportEnvelope:
        try:
            return await self._save_report(req)
        except Exception:
            await self._session.rollback()
            raise

    async def _save_report(self, req: FlowReportSaveRequest) -> FlowReportEnvelope:
        result = await self.stage_report(req)
        await self._session.commit()
        return result

    async def stage_report(self, req: FlowReportSaveRequest) -> FlowReportEnvelope:
        """Internal validated writer. Caller owns the transaction and rollback."""
        # Revalidate even if a model was constructed unsafely or its nested dict mutated.
        # Nothing, including ensure_stock, can write before this boundary succeeds.
        try:
            validated = FlowReportSaveRequest.model_validate(req.model_dump())
        except ValidationError as exc:
            code = ErrorCode.INPUT_INVALID
            if any(
                error["type"] == "flow_unsupported_version" for error in exc.errors()
            ):
                code = ErrorCode.UNSUPPORTED_VERSION
            raise FlowPayloadError(code) from exc
        principal = await self._authorize(lock=True)
        payload = deepcopy(validated.payload)
        report_id = UUID(payload["report_id"])

        meta = payload.get("meta") or {}
        signals = payload.get("signals") or {}
        verification = payload.get("verification") or {}
        interp_meta = payload.get("interpretation_meta") or {}
        ticker = meta["ticker"]

        stock_name = meta.get("stock_name")
        market = meta.get("market")
        base_date = (
            date.fromisoformat(meta["base_date"])
            if meta["base_date"] is not None
            else None
        )
        now = datetime.now(UTC)

        def gate(name: str) -> dict[str, Any] | None:
            g = verification.get(name)
            return g if isinstance(g, dict) else None

        def gate_passed(name: str) -> bool | None:
            g = gate(name)
            return g.get("passed") if g else None

        report = FlowReport(
            id=report_id,
            owner_user_id=principal.user_id,
            ticker=ticker,
            stock_code=ticker,  # handoff §4.1 — stock_code = meta.ticker
            stock_name=stock_name,
            market=market,
            base_date=base_date,
            alignment=signals.get("alignment"),
            data_status=payload.get("data_status"),
            trace_id=payload.get("trace_id"),
            signals=payload["signals"],
            created_at=now,
        )
        interpretation = FlowReportInterpretation(
            id=uuid4(),
            report_id=report_id,
            interpretation=payload.get("interpretation"),
            interpretation_source=interp_meta.get("source"),
            provider=interp_meta.get("provider"),
            model=interp_meta.get("model"),
        )
        verification_row = FlowReportVerification(
            id=uuid4(),
            report_id=report_id,
            gate1_passed=gate_passed("gate1"),
            gate2_passed=gate_passed("gate2"),
            gate3_passed=gate_passed("gate3"),
            # checks: 3게이트 전문(passed/checks/failures) — 조회 시 verification 재구성용.
            checks={
                "gate1": gate("gate1"),
                "gate2": gate("gate2"),
                "gate3": gate("gate3"),
                STORAGE_FORMAT_KEY: STORAGE_FORMAT,
                PAYLOAD_SNAPSHOT_KEY: deepcopy(payload),
            },
            outcome=verification.get("outcome"),
            regen_count=verification.get("regen_count"),
        )

        agent_report = AgentReport(
            id=uuid4(),
            agent_type="flow",
            agent_report_id=report_id,
            request_id=None,
            client_session_id=validated.client_session_id,
            owner_user_id=principal.user_id,
            owner_session_id=principal.session_id,
            stock_code=ticker,
            stock_name=stock_name,
            question=validated.question,
            answer_text=payload.get("interpretation"),
            data_status=payload.get("data_status"),
            trace_id=payload.get("trace_id"),
            as_of=now,
            created_at=now,
            summary={
                STORAGE_FORMAT_KEY: STORAGE_FORMAT,
                "alignment": signals.get("alignment"),
                "outcome": verification.get("outcome"),
                "base_date": meta.get("base_date"),
            },
        )

        # Root lock first for an existing ID; never adopt legacy or overwrite another owner.
        existing = await self._session.scalar(
            select(FlowReport).where(FlowReport.id == report_id).with_for_update()
        )
        if existing is not None:
            raise FlowReportIdConflict("결과 ID가 이미 존재합니다.")
        if await flow_repo.get_agent_indexes(self._session, report_id):
            raise FlowReportIdConflict("결과 ID를 사용할 수 없습니다.")

        await flow_repo.ensure_stock(
            self._session, stock_code=ticker, stock_name=stock_name, market=market
        )
        await flow_repo.add_report(
            self._session,
            report=report,
            interpretation=interpretation,
            verification=verification_row,
        )
        await agent_repo.add(self._session, agent_report)
        await self._session.flush()

        return FlowReportEnvelope(report_id=report_id, report=payload)

    # ── 조회 ──────────────────────────────────────────────────────────────────
    async def get_report(self, report_id: UUID) -> FlowReportEnvelope | None:
        principal = await self._authorize()
        report = await flow_repo.get_owned_report(
            self._session, report_id, owner_user_id=principal.user_id
        )
        if report is None:
            return None
        interp = await flow_repo.get_interpretation(self._session, report_id)
        verif = await flow_repo.get_verification(self._session, report_id)
        indexes = await flow_repo.get_agent_indexes(self._session, report_id)
        payload = self._reconstruct_payload(report, interp, verif, indexes)
        return FlowReportEnvelope(report_id=report.id, report=payload)

    async def list_reports(
        self, *, stock_code: str | None, limit: int, offset: int
    ) -> FlowReportListResponse:
        principal = await self._authorize()
        rows = await flow_repo.list_owned_indexes(
            self._session,
            owner_user_id=principal.user_id,
            stock_code=stock_code,
            limit=limit,
            offset=offset,
        )
        await self.validate_index_rows(rows)
        items = [AgentReportListItem.model_validate(row) for row in rows]
        return FlowReportListResponse(
            items=items, limit=limit, offset=offset, count=len(items)
        )

    async def list_common(
        self,
        *,
        agent_type=None,
        client_session_id=None,
        stock_code=None,
        limit=20,
        offset=0,
    ):
        if agent_type not in (None, "flow"):
            raise PermissionError("Only Flow is available")
        principal = await self._authorize()
        rows = await flow_repo.list_owned_indexes(
            self._session,
            owner_user_id=principal.user_id,
            client_session_id=client_session_id,
            stock_code=stock_code,
            limit=limit,
            offset=offset,
        )
        await self.validate_index_rows(rows)
        return [AgentReportListItem.model_validate(row) for row in rows]

    async def list_report_archive(
        self,
        *,
        agent_type=None,
        client_session_id=None,
        stock_code=None,
        limit=20,
        offset=0,
    ):
        from src.modules.technical.application.report_service import build_archive_item
        from src.modules.technical.infrastructure import report_repository as tr_repo
        from src.modules.reports.api.archive_schemas import ArchiveListResponse

        if agent_type not in (None, "flow"):
            raise PermissionError("Only Flow is available")
        principal = await self._authorize()
        filters = dict(
            owner_user_id=principal.user_id,
            client_session_id=client_session_id,
            stock_code=stock_code,
        )
        rows = await flow_repo.list_owned_indexes(
            self._session, **filters, limit=limit, offset=offset
        )
        await self.validate_index_rows(rows)
        total = await flow_repo.list_owned_indexes(self._session, **filters, count=True)
        stocks = await tr_repo.get_stocks(
            self._session, list({row.stock_code for row in rows if row.stock_code})
        )
        return ArchiveListResponse(
            items=[
                build_archive_item(row=row, stock=stocks.get(row.stock_code))
                for row in rows
            ],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def validate_index_rows(self, rows: list[AgentReport]) -> None:
        """Shared by Flow and common lists; a missing marker cannot bypass validation."""
        principal = await self._authorize()
        report_ids = list(
            {row.agent_report_id for row in rows if row.agent_type == "flow"}
        )
        if not report_ids:
            return
        (
            roots,
            interpretations,
            verifications,
            indexes,
        ) = await flow_repo.get_report_parts(
            self._session, report_ids, owner_user_id=principal.user_id
        )
        root_by_id = {row.id: row for row in roots}
        interp_by_id = {row.report_id: row for row in interpretations}
        verif_by_id = {row.report_id: row for row in verifications}
        index_by_id: dict[UUID, list[AgentReport]] = {}
        for row in indexes:
            index_by_id.setdefault(row.agent_report_id, []).append(row)
        for report_id in report_ids:
            report = root_by_id.get(report_id)
            if report is None:
                raise FlowStoredPayloadError("저장된 Flow 결과를 확인할 수 없습니다.")
            self._reconstruct_payload(
                report,
                interp_by_id.get(report_id),
                verif_by_id.get(report_id),
                index_by_id.get(report_id, []),
            )

    # ── 삭제 ──────────────────────────────────────────────────────────────────
    async def delete_report(self, report_id: UUID) -> bool:
        try:
            return await self._delete_report(report_id)
        except Exception:
            await self._session.rollback()
            raise

    async def _delete_report(self, report_id: UUID) -> bool:
        principal = await self._authorize(lock=True)
        # Discover root + live-analysis association in ONE SQL snapshot. Never
        # adopt a root which appeared after an earlier "no connection" observation.
        from db.models.flow.analysis_run import FlowAnalysisRun
        from sqlalchemy import literal_column
        discovered = (await self._session.execute(
            select(FlowReport.id, literal_column('flow_reports.xmin::text'), FlowAnalysisRun.id)
            .outerjoin(FlowAnalysisRun, (FlowAnalysisRun.adopted_report_id == FlowReport.id) & (FlowAnalysisRun.state == 'stored'))
            .where(FlowReport.id == report_id, FlowReport.id.in_(flow_repo.eligible_flow_ids(principal.user_id)))
        )).one_or_none()
        if discovered is None:
            return False
        analysis = None
        if discovered[2] is not None:
            analysis = await self._session.scalar(select(FlowAnalysisRun).where(
                FlowAnalysisRun.id == discovered[2], FlowAnalysisRun.owner_user_id == principal.user_id
            ).with_for_update().execution_options(populate_existing=True))
            if analysis is None or analysis.state != 'stored' or analysis.adopted_report_id != report_id:
                raise FlowStoredPayloadError('저장 연결을 확인할 수 없습니다.')
        # Lock order: session -> analysis (when present) -> original report root.
        version = await self._session.scalar(select(literal_column('flow_reports.xmin::text'))
            .select_from(FlowReport).where(FlowReport.id == report_id)
            .with_for_update(of=FlowReport))
        if version != discovered[1]:
            return False
        root = await flow_repo.get_owned_report(
            self._session, report_id, owner_user_id=principal.user_id, lock=True
        )
        if root is None:
            return False
        current_analysis = await self._session.scalar(select(FlowAnalysisRun.id).where(
            FlowAnalysisRun.adopted_report_id == report_id, FlowAnalysisRun.state == 'stored'))
        if current_analysis != discovered[2]:
            raise FlowStoredPayloadError('저장 연결이 변경됐습니다.')
        if analysis is not None:
            analysis.state = 'deleted'
            analysis.request_json = analysis.stock_name = analysis.input_json = analysis.result_json = None
            await self._session.flush()
        await flow_repo.delete_agent_index(self._session, report_id)
        deleted = await flow_repo.delete_root(self._session, report_id)
        if analysis is not None:
            from src.modules.supervisor.infrastructure.repository import redact_for_flow
            await redact_for_flow(self._session, principal.user_id, analysis.key_digest)
        await self._session.commit()
        return deleted > 0

    async def delete_all_reports(self) -> int:
        raise PermissionError("Public bulk deletion is disabled")

    # ── payload 재구성(저장 시 3테이블로 분해한 것을 다시 payload 형태로) ───────
    @staticmethod
    def _reconstruct_payload(
        report: FlowReport,
        interp: FlowReportInterpretation | None,
        verif: FlowReportVerification | None,
        indexes: list[AgentReport] | None = None,
    ) -> dict[str, Any]:
        checks = verif.checks if verif else None
        checks = {} if checks is None else checks
        if not isinstance(checks, dict):
            raise FlowStoredPayloadError("저장된 Flow 결과를 확인할 수 없습니다.")
        indexed_format = any(
            isinstance(row.summary, dict) and STORAGE_FORMAT_KEY in row.summary
            for row in indexes or []
        )
        new_format = (
            PAYLOAD_SNAPSHOT_KEY in checks
            or STORAGE_FORMAT_KEY in checks
            or indexed_format
        )
        if new_format:
            if (
                checks.get(STORAGE_FORMAT_KEY) != STORAGE_FORMAT
                or PAYLOAD_SNAPSHOT_KEY not in checks
            ):
                raise FlowStoredPayloadError("저장된 Flow 결과를 확인할 수 없습니다.")
            snapshot = deepcopy(checks[PAYLOAD_SNAPSHOT_KEY])
            try:
                validate_flow_payload(snapshot)
                if UUID(snapshot["report_id"]) != report.id:
                    raise ValueError("snapshot ID mismatch")
                FlowReportService._check_snapshot_consistency(
                    snapshot, report, interp, verif, indexes
                )
            except (ValidationError, ValueError, TypeError) as exc:
                raise FlowStoredPayloadError(
                    "저장된 Flow 결과를 확인할 수 없습니다."
                ) from exc
            return snapshot
        verification: dict[str, Any] | None = None
        if verif is not None:
            verification = {
                "gate1": checks.get("gate1"),
                "gate2": checks.get("gate2"),
                "gate3": checks.get("gate3"),
                "outcome": verif.outcome,
                "regen_count": verif.regen_count,
            }
        interpretation_meta: dict[str, Any] | None = None
        if interp is not None:
            interpretation_meta = {
                "source": interp.interpretation_source,
                "provider": interp.provider,
                "model": interp.model,
            }
        # Explicit legacy-v1 adapter: old tables never persisted a version.
        # New records always use the snapshot above, never this inferred version.
        payload = {
            "version": 1,
            "report_id": str(report.id),
            "trace_id": report.trace_id,
            "data_status": report.data_status,
            "meta": {
                "stock_name": report.stock_name,
                "ticker": report.ticker,
                "market": report.market,
                "base_date": report.base_date.isoformat() if report.base_date else None,
            },
            "signals": report.signals,
            "verification": verification,
            "interpretation": interp.interpretation if interp else None,
            "interpretation_meta": interpretation_meta,
        }
        try:
            validate_flow_payload(payload)
        except (ValidationError, ValueError) as exc:
            raise FlowStoredPayloadError(
                "저장된 Flow 결과를 확인할 수 없습니다."
            ) from exc
        return payload

    @staticmethod
    def _check_snapshot_consistency(
        payload: dict[str, Any],
        report: FlowReport,
        interp: FlowReportInterpretation | None,
        verif: FlowReportVerification | None,
        indexes: list[AgentReport] | None,
    ) -> None:
        """Validate every saved projection; never repair a corrupt row at read time."""
        if interp is None or verif is None or not indexes or len(indexes) != 1:
            raise ValueError("snapshot projection missing or duplicated")
        index = indexes[0]
        meta = payload["meta"]
        signals = payload["signals"] or {}
        verification = payload["verification"] or {}
        interpretation_meta = payload.get("interpretation_meta") or {}
        expected_root = {
            "ticker": meta["ticker"],
            "stock_code": meta["ticker"],
            "stock_name": meta.get("stock_name"),
            "market": meta.get("market"),
            "base_date": date.fromisoformat(meta["base_date"])
            if meta["base_date"]
            else None,
            "alignment": signals.get("alignment"),
            "signals": payload["signals"],
            "trace_id": payload.get("trace_id"),
            "data_status": payload.get("data_status"),
        }
        expected_interp = {
            "report_id": report.id,
            "interpretation": payload["interpretation"],
            "interpretation_source": interpretation_meta.get("source"),
            "provider": interpretation_meta.get("provider"),
            "model": interpretation_meta.get("model"),
        }
        expected_verif = {
            "report_id": report.id,
            "outcome": verification.get("outcome"),
            "regen_count": verification.get("regen_count"),
        }
        for gate in ("gate1", "gate2", "gate3"):
            expected_verif[f"{gate}_passed"] = (verification.get(gate) or {}).get(
                "passed"
            )
            if not projection_values_equal(
                verif.checks.get(gate), verification.get(gate)
            ):
                raise ValueError("snapshot gate projection mismatch")
        expected_index = {
            "agent_type": "flow",
            "agent_report_id": report.id,
            "stock_code": meta["ticker"],
            "stock_name": meta.get("stock_name"),
            "answer_text": payload["interpretation"],
            "data_status": payload.get("data_status"),
            "trace_id": payload.get("trace_id"),
        }
        for row, expected in (
            (report, expected_root),
            (interp, expected_interp),
            (verif, expected_verif),
            (index, expected_index),
        ):
            if any(
                not projection_values_equal(getattr(row, key), value)
                for key, value in expected.items()
            ):
                raise ValueError("snapshot projection mismatch")
        summary = index.summary
        expected_summary = {
            STORAGE_FORMAT_KEY: STORAGE_FORMAT,
            "alignment": signals.get("alignment"),
            "outcome": verification.get("outcome"),
            "base_date": meta["base_date"],
        }
        if not isinstance(summary, dict) or any(
            not projection_values_equal(summary.get(key), value)
            for key, value in expected_summary.items()
        ):
            raise ValueError("snapshot list summary mismatch")
