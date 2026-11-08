"""Versioned internal synthetic artifact. No provider, network, environment or IO."""
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID
from src.modules.flow.domain.input_snapshot import canonical, decode, digest, validate

ENGINE_ID = "flow.fake.summary.v1"
FAILURES = frozenset({"fake_failed", "result_invalid", "coroutine_timeout", "deadline_expired"})
CODES = frozenset({"invalid", "not_found", "auth_required", "corrupt", "unavailable", "fence"})


class FakeExecutionError(ValueError):
    def __init__(self, code):
        self.code = code if code in CODES else "unavailable"
        super().__init__("Flow fake execution: " + self.code)


def _v1_facts(seal, execution_id):
    """Fixed schema-v1 validation rules, independent of the engine binding."""
    body = validate(seal.input_json)
    data = body["fixture"]["data"]
    rows = data["rows"]
    return {"contract_version": 1, "mode": "synthetic_only", "synthetic": True,
            "execution_id": str(execution_id), "input_snapshot_id": str(seal.id),
            "input_sha256": seal.input_sha256, "source_reference": body["source_receipt"]["reference"],
            "ticker": body["source_receipt"]["request"]["ticker"],
            "requested_as_of": body["source_receipt"]["request"]["as_of"], "engine_id": ENGINE_ID,
            "row_count": len(rows), "start_date": rows[0]["date"], "end_date": rows[-1]["date"],
            "calendar": "consecutive_calendar_dates_not_trading_days", "quantity_unit": "share",
            "trading_value_unit": "KRW", "totals": {key: sum(row[key] for row in rows)
                for key in ("individual", "foreign", "institution", "trading_value")},
            "notice": "Synthetic calendar rows; not market observations or a Gate/investment result."
                if len(rows) == 20 else "Short synthetic calendar sample; no 20-day persistence conclusion."}


async def fake_engine(seal, execution_id):
    return _v1_facts(seal, execution_id)


def result_text(value, seal, execution_id):
    try:
        text = canonical(value)
        validate_result(text, seal, execution_id)
        return text
    except Exception:
        raise FakeExecutionError("invalid") from None


def validate_result(text, seal, execution_id):
    try:
        value = decode(text)
        if canonical(value) != canonical(_v1_facts(seal, execution_id)):
            raise FakeExecutionError("corrupt")
        return value
    except Exception:
        raise FakeExecutionError("corrupt") from None


@dataclass(frozen=True)
class ExecutionView:
    id: UUID
    input_snapshot_id: UUID
    status: str
    started_at: object
    deadline_at: object
    finished_at: object
    result_json: str | None
    result_sha256: str | None
    error_code: str | None

    @property
    def body(self):
        return None if self.result_json is None else decode(self.result_json)


def read_execution(row, seal):
    try:
        if (not isinstance(row.id, UUID) or row.input_snapshot_id != seal.id
                or type(row.contract_version) is not int or row.contract_version != 1
                or row.engine_id != ENGINE_ID or type(row.claim_digest) is not bytes or len(row.claim_digest) != 32
                or row.started_at.utcoffset() is None or row.deadline_at.utcoffset() is None
                or row.deadline_at - row.started_at != timedelta(seconds=10)):
            raise FakeExecutionError("corrupt")
        if row.status == "running":
            if any(v is not None for v in (row.finished_at, row.result_json, row.result_sha256, row.error_code)):
                raise FakeExecutionError("corrupt")
        elif row.status in {"succeeded", "failed", "timed_out"}:
            if row.finished_at is None or row.finished_at.utcoffset() is None or row.finished_at < row.started_at:
                raise FakeExecutionError("corrupt")
            if row.status == "succeeded":
                if (row.finished_at >= row.deadline_at or row.error_code is not None
                        or row.result_json is None or digest(row.result_json) != row.result_sha256):
                    raise FakeExecutionError("corrupt")
                validate_result(row.result_json, seal, row.id)
            elif row.result_json is not None or row.result_sha256 is not None or row.error_code not in FAILURES:
                raise FakeExecutionError("corrupt")
            elif row.status == "failed" and row.error_code not in {"fake_failed", "result_invalid"}:
                raise FakeExecutionError("corrupt")
            elif row.status == "timed_out" and row.error_code not in {"coroutine_timeout", "deadline_expired"}:
                raise FakeExecutionError("corrupt")
        else:
            raise FakeExecutionError("corrupt")
        return ExecutionView(row.id, row.input_snapshot_id, row.status, row.started_at, row.deadline_at,
                             row.finished_at, row.result_json, row.result_sha256, row.error_code)
    except Exception:
        raise FakeExecutionError("corrupt") from None
