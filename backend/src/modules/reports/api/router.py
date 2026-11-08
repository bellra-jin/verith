"""공통 리포트 목록 라우트 — GET /reports (agent_reports 기준)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from src.modules.flow.api.router import get_flow_report_service
from src.modules.reports.api.report_schemas import ReportsListResponse
from src.modules.reports.api.archive_schemas import ArchiveListResponse
from src.modules.flow.domain.execution import ErrorCode, SafeError
from src.modules.flow.application.report_service import FlowStoredPayloadError
from src.modules.flow.application.report_service import FlowReportService

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/archive", response_model=ArchiveListResponse)
async def list_report_archive(
    agent_type: str | None = None,
    client_session_id: str | None = None,
    stock_code: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: FlowReportService = Depends(get_flow_report_service),
) -> ArchiveListResponse:
    """리포트 보관함 공통 카드 목록(agent_type 필터, created_at DESC). agent 상세와 분리된 프론트 view model."""
    try:
        return await service.list_report_archive(
            agent_type=agent_type,
            client_session_id=client_session_id,
            stock_code=stock_code,
            limit=limit,
            offset=offset,
        )
    except FlowStoredPayloadError as exc:
        error = SafeError(code=ErrorCode.RESULT_CONTRACT_INVALID)
        raise HTTPException(
            status_code=error.http_status, detail=error.model_dump(mode="json")
        ) from exc


@router.get("", response_model=ReportsListResponse)
async def list_reports(
    agent_type: str | None = None,
    client_session_id: str | None = None,
    stock_code: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: FlowReportService = Depends(get_flow_report_service),
) -> ReportsListResponse:
    try:
        items = await service.list_common(
            agent_type=agent_type,
            client_session_id=client_session_id,
            stock_code=stock_code,
            limit=limit,
            offset=offset,
        )
    except FlowStoredPayloadError as exc:
        error = SafeError(code=ErrorCode.RESULT_CONTRACT_INVALID)
        raise HTTPException(
            status_code=error.http_status, detail=error.model_dump(mode="json")
        ) from exc
    return ReportsListResponse(
        items=items, limit=limit, offset=offset, count=len(items)
    )
