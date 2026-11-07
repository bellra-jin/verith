"""flow report 라우트 — save-only(POST /save) + GET/LIST/DELETE."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from collections.abc import Callable, Coroutine
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_session
from src.api.schemas.flow_execution import ErrorCode, SafeError
from src.api.schemas.flow_report import (
    FlowReportEnvelope,
    FlowReportListResponse,
    FlowReportSaveRequest,
)
from src.api.services.flow_report_service import (
    FlowPayloadError,
    FlowReportService,
    FlowStoredPayloadError,
)


class FlowContractRoute(APIRoute):
    """Legacy response wrapper, with safe validation errors that omit rejected payloads."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        handler = super().get_route_handler()

        async def safe_handler(request: Request) -> Response:
            try:
                return await handler(request)
            except RequestValidationError as exc:
                code = ErrorCode.INPUT_INVALID
                if any(
                    error["type"] == "flow_unsupported_version"
                    for error in exc.errors()
                ):
                    code = ErrorCode.UNSUPPORTED_VERSION
                error = SafeError(code=code)
                return JSONResponse(
                    status_code=error.http_status,
                    content={"detail": error.model_dump(mode="json")},
                )

        return safe_handler


router = APIRouter(
    prefix="/api/flow/reports", tags=["flow-reports"], route_class=FlowContractRoute
)


async def get_flow_report_service(
    session: AsyncSession = Depends(get_session),
) -> AsyncGenerator[FlowReportService, None]:
    yield FlowReportService(session=session)


@router.post(
    "/save", response_model=FlowReportEnvelope, status_code=status.HTTP_201_CREATED
)
async def save_flow_report(
    req: FlowReportSaveRequest,
    service: FlowReportService = Depends(get_flow_report_service),
) -> FlowReportEnvelope:
    """save-only — supervisor 가 만든 flow payload 를 AI 재호출 없이 저장(news·fundamental 방식)."""
    try:
        return await service.save_report(req)
    except FlowPayloadError as exc:
        raise HTTPException(
            status_code=exc.error.http_status, detail=exc.error.model_dump(mode="json")
        ) from exc


@router.get("", response_model=FlowReportListResponse)
async def list_flow_reports(
    stock_code: str | None = Query(default=None, pattern=r"^[0-9]{6}$"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: FlowReportService = Depends(get_flow_report_service),
) -> FlowReportListResponse:
    try:
        return await service.list_reports(
            stock_code=stock_code, limit=limit, offset=offset
        )
    except FlowStoredPayloadError as exc:
        error = SafeError(code=ErrorCode.RESULT_CONTRACT_INVALID)
        raise HTTPException(
            status_code=error.http_status, detail=error.model_dump(mode="json")
        ) from exc


@router.get("/{report_id}", response_model=FlowReportEnvelope)
async def get_flow_report(
    report_id: UUID,
    service: FlowReportService = Depends(get_flow_report_service),
) -> FlowReportEnvelope:
    try:
        envelope = await service.get_report(report_id)
    except FlowStoredPayloadError as exc:
        error = SafeError(code=ErrorCode.RESULT_CONTRACT_INVALID)
        raise HTTPException(
            status_code=error.http_status,
            detail=error.model_dump(mode="json"),
        ) from exc
    if envelope is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="report not found"
        )
    return envelope


@router.delete("", status_code=status.HTTP_200_OK)
async def delete_all_flow_reports(
    service: FlowReportService = Depends(get_flow_report_service),
) -> dict:
    """flow 리포트 전체 삭제. 삭제 건수 반환."""
    deleted = await service.delete_all_reports()
    return {"deleted": deleted}


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_flow_report(
    report_id: UUID,
    service: FlowReportService = Depends(get_flow_report_service),
) -> Response:
    deleted = await service.delete_report(report_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="report not found"
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
