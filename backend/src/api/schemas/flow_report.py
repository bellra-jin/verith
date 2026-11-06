"""flow report API 스키마 — save-only(payload 그대로 저장)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.api.schemas.agent_report import AgentReportListItem
from src.api.schemas.flow_payload import (
    FlowPayloadV1,
    validate_flow_payload,
    validate_storage_string,
)


class FlowReportSaveRequest(BaseModel):
    """POST /api/flow/reports/save 요청 — save-only.

    supervisor 가 만든 flow AgentOutput.payload(storage-spec v1)를 받아 그대로 저장한다.
    backend 는 AI 를 다시 호출하지 않는다(news·fundamental save-only 와 같은 방식).
    """

    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)

    payload: dict[str, Any] = Field(
        description="legacy/internal flow payload (storage-spec v1)"
    )
    question: str = Field(min_length=1, pattern=r"\S")
    client_session_id: str | None = None

    @field_validator("payload", mode="before", json_schema_input_type=FlowPayloadV1)
    @classmethod
    def valid_payload(cls, value: dict[str, Any]) -> dict[str, Any]:
        return validate_flow_payload(value)

    @field_validator("question", "client_session_id")
    @classmethod
    def valid_storage_text(cls, value: str | None) -> str | None:
        return validate_storage_string(value) if value is not None else None


class FlowReportEnvelope(BaseModel):
    """POST/GET 응답 wrapper — { report_id, report }. report 는 payload 형태(재구성)."""

    report_id: UUID
    report: dict[str, Any]


class FlowReportListResponse(BaseModel):
    items: list[AgentReportListItem]
    limit: int
    offset: int
    count: int
