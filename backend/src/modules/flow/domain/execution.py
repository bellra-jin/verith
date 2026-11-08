"""CF-001 contracts only: no authentication, run admission, or persistence services."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Generic, Literal, TypeVar
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from src.modules.flow.domain.payload import ISODate, Number, Ticker, validate_flow_payload


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


NonBlank = Annotated[str, Field(strict=True, min_length=1, pattern=r"\S")]


class FlowRunRequest(ContractModel):
    """Future public input. Never accept an owner, AI payload, or pass/fail flag here."""

    ticker: Ticker
    question: NonBlank
    as_of: AwareDatetime
    idempotency_key: NonBlank

    @field_validator("as_of", mode="before")
    @classmethod
    def explicit_datetime(cls, value: object) -> object:
        # AwareDatetime also accepts numeric strings as Unix timestamps. The public
        # contract requires an explicit ISO datetime, never an inferred epoch value.
        if isinstance(value, str):
            return datetime.fromisoformat(value)
        if isinstance(value, datetime):
            return value
        raise ValueError("as_of requires a timezone-aware ISO datetime")

    def input_fingerprint(self) -> str:
        # The key identifies the admission, not the input. Owner is scoped separately.
        value = self.model_dump(mode="json", exclude={"idempotency_key"})
        value["as_of"] = self.as_of.astimezone(UTC).isoformat()
        encoded = json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        return hashlib.sha256(encoded.encode()).hexdigest()


class ExecutionReference(ContractModel):
    request_id: UUID
    run_id: UUID
    attempt_id: UUID


class ExecutionContext(ExecutionReference):
    """Created by trusted Backend code *after* principal verification, never from headers."""

    owner_user_id: UUID


class FlowResultReference(ExecutionContext):
    report_id: UUID
    payload_fingerprint: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class ErrorCode(StrEnum):
    AUTH_REQUIRED = "AUTH_REQUIRED"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    RESULT_CONFLICT = "RESULT_CONFLICT"
    INPUT_INVALID = "INPUT_INVALID"
    UNSUPPORTED_VERSION = "UNSUPPORTED_VERSION"
    RESULT_CONTRACT_INVALID = "RESULT_CONTRACT_INVALID"
    DATA_INSUFFICIENT = "DATA_INSUFFICIENT"
    FEATURE_UNAVAILABLE = "FEATURE_UNAVAILABLE"
    AUTH_REQUEST_INVALID = "AUTH_REQUEST_INVALID"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


ERRORS: dict[ErrorCode, tuple[int, str]] = {
    ErrorCode.AUTH_REQUIRED: (401, "인증이 필요합니다."),
    ErrorCode.RESOURCE_NOT_FOUND: (404, "리소스를 찾을 수 없습니다."),
    ErrorCode.IDEMPOTENCY_CONFLICT: (409, "같은 멱등키에 다른 입력이 사용되었습니다."),
    ErrorCode.RESULT_CONFLICT: (409, "이미 확정된 결과와 충돌합니다."),
    ErrorCode.INPUT_INVALID: (422, "요청 형식이 올바르지 않습니다."),
    ErrorCode.UNSUPPORTED_VERSION: (422, "지원하지 않는 payload version입니다."),
    ErrorCode.RESULT_CONTRACT_INVALID: (502, "분석 결과를 확인할 수 없습니다."),
    ErrorCode.DATA_INSUFFICIENT: (422, "분석에 필요한 자료가 부족합니다."),
    ErrorCode.FEATURE_UNAVAILABLE: (403, "현재 사용할 수 없는 기능입니다."),
    ErrorCode.AUTH_REQUEST_INVALID: (403, "잘못된 인증 요청입니다."),
    ErrorCode.SERVICE_UNAVAILABLE: (503, "요청을 처리할 수 없습니다."),
}


class SafeError(ContractModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True, frozen=True)

    code: ErrorCode
    message: str = ""

    # Fixed by code: do not accept raw exception messages, even internally.
    @property
    def http_status(self) -> int:
        return ERRORS[self.code][0]

    @model_validator(mode="after")
    def fixed_message(self) -> SafeError:
        expected = ERRORS[self.code][1]
        if self.message and self.message != expected:
            raise ValueError("error message does not match its safe code")
        object.__setattr__(self, "message", expected)
        return self


class ContractViolation(ValueError):
    def __init__(self, code: ErrorCode) -> None:
        self.error = SafeError(code=code)
        super().__init__(self.error.message)


T = TypeVar("T")


class CommonResponse(ContractModel, Generic[T]):
    request_id: UUID
    data: T | None = None
    error: SafeError | None = None

    @model_validator(mode="after")
    def exactly_one_result(self) -> CommonResponse[T]:
        if (self.data is None) == (self.error is None):
            raise ValueError("exactly one of data/error is required")
        return self


class FlowRunState(ExecutionReference):
    execution_status: Literal["pending", "running", "succeeded", "failed", "unknown"]
    storage_status: Literal["not_stored", "stored", "unknown"]
    report_id: UUID | None = None
    error: SafeError | None = None

    @model_validator(mode="after")
    def consistent_state(self) -> FlowRunState:
        if self.storage_status == "stored" and (
            self.report_id is None or self.execution_status != "succeeded"
        ):
            raise ValueError("stored requires a successful analysis result")
        if self.execution_status == "failed" and self.error is None:
            raise ValueError("failed execution requires a safe error")
        return self


class DataObservation(ContractModel):
    """New internal metadata; v1 cannot retroactively supply actual source/period/reason."""

    source: NonBlank
    as_of: ISODate
    period_start: ISODate
    period_end: ISODate
    unit: NonBlank
    value: Number | None
    missing_reason: NonBlank | None = None

    @model_validator(mode="after")
    def value_and_period(self) -> DataObservation:
        if self.period_start > self.period_end or self.period_end > self.as_of:
            raise ValueError("period must be ordered and no later than as_of")
        if (self.value is None) != (self.missing_reason is not None):
            raise ValueError(
                "missing values require a reason; real values cannot have one"
            )
        return self


class IdempotencyReference(ContractModel):
    owner_user_id: UUID
    key: NonBlank
    input_fingerprint: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    run_id: UUID

    def validate_replay(self, owner_user_id: UUID, request: FlowRunRequest) -> UUID:
        """Contract check, not atomic admission. Call only after owner/key scoped lookup."""
        if owner_user_id != self.owner_user_id:
            raise ContractViolation(ErrorCode.RESOURCE_NOT_FOUND)
        if (
            self.key != request.idempotency_key
            or self.input_fingerprint != request.input_fingerprint()
        ):
            raise ContractViolation(ErrorCode.IDEMPOTENCY_CONFLICT)
        return self.run_id


def bind_flow_result(context: ExecutionContext, payload: dict) -> FlowResultReference:
    """Validate an internal AI result before adopting its ID; no persistence or auth."""
    try:
        validate_flow_payload(payload)
    except (ValueError, TypeError) as exc:
        raise ContractViolation(ErrorCode.RESULT_CONTRACT_INVALID) from exc
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return FlowResultReference(
        **context.model_dump(),
        report_id=payload["report_id"],
        payload_fingerprint=hashlib.sha256(encoded.encode()).hexdigest(),
    )


def validate_result_binding(
    expected: ExecutionContext,
    candidate: FlowResultReference,
    *,
    existing: FlowResultReference | None = None,
    deleted: bool = False,
) -> None:
    """Caller must load trusted context/tombstone atomically; this is no access service."""
    if deleted or candidate.owner_user_id != expected.owner_user_id:
        raise ContractViolation(ErrorCode.RESOURCE_NOT_FOUND)
    if any(
        getattr(candidate, key) != getattr(expected, key)
        for key in ("request_id", "run_id", "attempt_id")
    ):
        raise ContractViolation(ErrorCode.RESULT_CONTRACT_INVALID)
    if existing is not None and existing != candidate:
        raise ContractViolation(ErrorCode.RESULT_CONFLICT)
