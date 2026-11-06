"""Storage-spec v1 validation; validation never rewrites the producer's JSON."""

from __future__ import annotations

import json
from datetime import date
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)
from pydantic_core import PydanticCustomError


def _iso_date(value: str) -> str:
    if date.fromisoformat(value).isoformat() != value:
        raise ValueError("expected YYYY-MM-DD")
    return value


def _uuid_string(value: str) -> str:
    UUID(value)
    return value


ISODate = Annotated[
    str, Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$"), AfterValidator(_iso_date)
]
UUIDString = Annotated[str, AfterValidator(_uuid_string)]
Ticker = Annotated[str, Field(pattern=r"^[0-9]{6}$")]
Number = (
    Annotated[int, Field(strict=True)]
    | Annotated[float, Field(strict=True, allow_inf_nan=False)]
)


class PayloadPart(BaseModel):
    # v1 was extended additively. Keep unknown JSON keys, but validate all known fields.
    model_config = ConfigDict(strict=True, extra="allow", hide_input_in_errors=True)


class FlowMeta(PayloadPart):
    ticker: Ticker
    stock_name: str | None = None
    market: str | None = None
    base_date: ISODate | None


class FlowStrength(PayloadPart):
    ratio: Number
    strong: bool


class FlowConsecutive(PayloadPart):
    days: Annotated[int, Field(ge=0)]
    signal: bool


class FlowPersistence(PayloadPart):
    sum_5: Number
    sum_20: Number
    consistent: bool


class FlowDaily(PayloadPart):
    date: ISODate
    개인: Number
    외국인: Number
    기관: Number


class FlowOwnership(PayloadPart):
    date: ISODate
    ratio: Number


class FlowPriceDaily(PayloadPart):
    date: ISODate
    close: Number
    change: Number
    change_rate: Number
    volume: Number
    frgn_qty: Number | None = None
    inst_qty: Number | None = None


class FlowSignals(PayloadPart):
    alignment: str | None = None
    consecutive: dict[str, FlowConsecutive] = Field(default_factory=dict)
    strength: dict[str, FlowStrength] = Field(default_factory=dict)
    persistence: dict[str, FlowPersistence] = Field(default_factory=dict)
    daily: list[FlowDaily] | None = None
    inst_detail: dict[str, Number] | None = None
    ownership: list[FlowOwnership] | None = None
    price_daily: list[FlowPriceDaily] | None = None


class FlowGate(PayloadPart):
    gate: Annotated[int, Field(ge=1, le=3)] | None = None
    passed: bool
    checks: list[str]
    failures: list[str]


class FlowVerification(PayloadPart):
    gate1: FlowGate | None = None
    gate2: FlowGate | None = None
    gate3: FlowGate | None = None
    outcome: Literal["explained", "fact_only"] | None = None
    regen_count: Annotated[int, Field(ge=0)] | None = None

    @model_validator(mode="after")
    def gate_numbers_match(self) -> FlowVerification:
        for number in (1, 2, 3):
            gate = getattr(self, f"gate{number}")
            if gate and gate.gate is not None and gate.gate != number:
                raise ValueError("gate number does not match its key")
        return self


class FlowInterpretationMeta(PayloadPart):
    source: Literal["llm", "fallback"] | None = None
    provider: str | None = None
    model: str | None = None


class FlowPayloadV1(PayloadPart):
    version: Literal[1]
    report_id: UUIDString
    meta: FlowMeta
    signals: FlowSignals | None
    verification: FlowVerification | None
    interpretation: str | None
    trace_id: str | None = None
    data_status: Literal["ok", "data_limited"] | None = None
    interpretation_meta: FlowInterpretationMeta | None = None

    @field_validator("version", mode="before")
    @classmethod
    def supported_version(cls, value: Any) -> int:
        if type(value) is not int or value != 1:
            raise PydanticCustomError(
                "flow_unsupported_version", "unsupported Flow payload version"
            )
        return value

    @model_validator(mode="after")
    def consistent_result(self) -> FlowPayloadV1:
        passed3 = bool(
            self.verification
            and self.verification.gate3
            and self.verification.gate3.passed
        )
        if self.interpretation is not None and not passed3:
            raise ValueError("interpretation requires gate3 pass")
        if self.verification and self.verification.outcome is not None:
            expected = "explained" if passed3 else "fact_only"
            if self.verification.outcome != expected:
                raise ValueError("outcome does not match gate3")
        if self.interpretation_meta:
            meta = self.interpretation_meta
            if meta.source is not None and meta.source != (
                "llm" if passed3 else "fallback"
            ):
                raise ValueError("interpretation source does not match gate3")
            if self.interpretation is None and (
                meta.provider is not None or meta.model is not None
            ):
                raise ValueError("missing interpretation cannot have provider/model")
        if self.data_status is not None:
            expected = (
                "ok"
                if self.signals and self.signals.price_daily is not None
                else "data_limited"
            )
            if self.data_status != expected:
                raise ValueError("data_status does not match price_daily availability")
        return self


def validate_flow_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Check the entire payload, including JSONB compatibility, without coercion/defaults."""
    FlowPayloadV1.model_validate(payload)
    _check_json_types(payload)
    try:
        json.dumps(payload, allow_nan=False)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Flow payload must contain finite JSON values") from exc
    return payload


def _check_json_types(value: Any) -> None:
    """json.dumps silently changes tuples and non-string keys; reject them instead."""
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise ValueError("Flow JSON keys must be strings")
            validate_storage_string(key)
            _check_json_types(item)
    elif type(value) is list:
        for item in value:
            _check_json_types(item)
    elif type(value) is str:
        validate_storage_string(value)
    elif value is not None and type(value) not in (bool, int, float):
        raise ValueError("Flow payload must contain JSON values")


def validate_storage_string(value: str) -> str:
    """Reject PostgreSQL-incompatible text without replacing or stripping any codepoint."""
    if "\x00" in value:
        raise ValueError("Flow text cannot contain NUL")
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise ValueError("Flow text must contain valid Unicode scalar values") from exc
    return value


def projection_values_equal(left: Any, right: Any) -> bool:
    """Compare JSON types recursively; JSON numbers exclude bool (unlike Python equality).

    int/float are one JSON number category. Non-JSON promoted UUID/date values must
    have the same Python type as well as the same value.
    """
    if type(left) in (int, float) and type(right) in (int, float):
        return left == right
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return left.keys() == right.keys() and all(
            projection_values_equal(left[key], right[key]) for key in left
        )
    if type(left) is list:
        return len(left) == len(right) and all(
            projection_values_equal(a, b) for a, b in zip(left, right)
        )
    return left == right
