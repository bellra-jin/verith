"""CF-003 receipt input and HTTP helpers; no execution or external calls."""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

from pydantic import Field, field_validator
from starlette.responses import JSONResponse

from src.modules.flow.domain.execution import (
    CommonResponse, ErrorCode, FlowRunRequest, FlowRunState, SafeError,
)
from src.modules.flow.domain.payload import validate_storage_string

RUNS_PATH = "/api/flow/runs"
PRIVATE = {"Cache-Control": "private, no-store", "Vary": "Cookie, Origin"}
RunResponse = CommonResponse[FlowRunState]


class FlowAdmissionRequest(FlowRunRequest):
    question: Annotated[str, Field(strict=True, min_length=1, max_length=2000, pattern=r"\S")]

    @field_validator("question", "idempotency_key")
    @classmethod
    def storage_text(cls, value: str) -> str:
        return validate_storage_string(value)

    @field_validator("idempotency_key")
    @classmethod
    def bounded_key(cls, value: str) -> str:
        if not 1 <= len(value.encode("utf-8")) <= 256:
            raise ValueError("idempotency key exceeds its byte limit")
        return value

    @field_validator("as_of")
    @classmethod
    def utc_timestamp(cls, value: datetime) -> datetime:
        try:
            return value.astimezone(UTC)
        except OverflowError:
            raise ValueError("as_of is outside the UTC datetime range") from None

    def normalized_input(self) -> dict:
        value = self.model_dump(mode="json", exclude={"idempotency_key"})
        value["as_of"] = self.as_of.astimezone(UTC).isoformat()
        return value


def is_run_endpoint(method: str, path: str) -> bool:
    if method == "POST":
        return path == RUNS_PATH
    if method == "GET" and path.startswith(RUNS_PATH + "/"):
        segment = path[len(RUNS_PATH) + 1:]
        return bool(segment) and "/" not in segment
    return False


def http_request_id(scope: dict) -> UUID:
    state = scope.setdefault("state", {})
    if "cf003_request_id" not in state:
        state["cf003_request_id"] = uuid4()
    return state["cf003_request_id"]


def error_response(scope: dict, code: ErrorCode) -> JSONResponse:
    error = SafeError(code=code)
    return JSONResponse(
        RunResponse(request_id=http_request_id(scope), error=error).model_dump(mode="json"),
        status_code=error.http_status, headers=PRIVATE,
    )
