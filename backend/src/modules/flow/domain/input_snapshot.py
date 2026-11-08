"""CF-006 synthetic input seal. This is neither an execution right nor a result."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import json
import math
import re
from uuid import UUID

from src.modules.flow.api.run_schemas import FlowAdmissionRequest

MAX_BYTES = 128 * 1024
FIXTURES = {"flow.synthetic.full20": 20, "flow.synthetic.short4": 4}
SPEC = {"version": 1, "provider": "fixture", "executable": False,
        "external_calls_allowed": 0, "max_cost": 0, "reservation_status": "not_reserved"}
ERRORS = frozenset({"invalid", "not_found", "conflict", "corrupt", "unavailable", "auth_required"})


class SnapshotError(ValueError):
    def __init__(self, code):
        self.code = code if code in ERRORS else "unavailable"
        super().__init__("Flow input snapshot: " + self.code)


def _tree(value):
    if value is None or type(value) is bool or type(value) is int:
        return
    if type(value) is float and math.isfinite(value):
        return
    if type(value) is str:
        if "\0" not in value and not any(0xD800 <= ord(c) <= 0xDFFF for c in value):
            return
    elif type(value) is list:
        for child in value:
            _tree(child)
        return
    elif type(value) is dict:
        for key, child in value.items():
            if type(key) is not str:
                raise SnapshotError("invalid")
            _tree(key)
            _tree(child)
        return
    raise SnapshotError("invalid")


def canonical(value):
    try:
        _tree(value)
        result = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        if len(result.encode("utf-8")) > MAX_BYTES:
            raise SnapshotError("invalid")
        return result
    except (ValueError, TypeError, RecursionError, OverflowError):
        raise SnapshotError("invalid") from None


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _pairs(pairs):
    value = {}
    for key, child in pairs:
        if key in value:
            raise SnapshotError("invalid")
        value[key] = child
    return value


def decode(text):
    try:
        if type(text) is not str or len(text.encode("utf-8")) > MAX_BYTES:
            raise SnapshotError("invalid")
        value = json.loads(text, object_pairs_hook=_pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(SnapshotError("invalid")))
        if canonical(value) != text:
            raise SnapshotError("invalid")
        return value
    except (ValueError, TypeError, UnicodeError, RecursionError, OverflowError):
        raise SnapshotError("invalid") from None


def fixture_selection(fixture_id, version):
    if type(fixture_id) is not str or fixture_id not in FIXTURES or type(version) is not int or version != 1:
        raise SnapshotError("invalid")


def receipt(row):
    """Validate the current receipt, without changing its fingerprint algorithm."""
    try:
        if (row.admission_mode, row.execution_status, row.storage_status, row.operation) != (
                "receipt_only", "pending", "not_stored", "flow"):
            raise SnapshotError("corrupt")
        if type(row.request_contract_version) is not int or row.request_contract_version != 1:
            raise SnapshotError("corrupt")
        request = FlowAdmissionRequest.model_validate(dict(row.request_input, idempotency_key="cf006-internal-validation"))
        if canonical(request.normalized_input()) != canonical(row.request_input) or request.input_fingerprint() != row.input_fingerprint:
            raise SnapshotError("corrupt")
        refs = {name: str(getattr(row, attr)) for name, attr in (
            ("request_id", "admission_request_id"), ("run_id", "id"),
            ("attempt_id", "attempt_id"), ("owner_user_id", "owner_user_id"))}
        for value in refs.values():
            if str(UUID(value)) != value:
                raise SnapshotError("corrupt")
        return {"reference": refs, "request_contract_version": 1,
                "request": request.normalized_input(), "request_fingerprint": row.input_fingerprint}
    except Exception:
        raise SnapshotError("corrupt") from None


def _data(as_of, count):
    end = datetime.fromisoformat(as_of).astimezone(UTC).date()
    rows = [{"date": (end - timedelta(days=count - 1 - n)).isoformat(),
             "individual": -50000, "foreign": 40000, "institution": 10000,
             "trading_value": 1000000} for n in range(count)]
    return {"rows": rows, "calendar": "consecutive_calendar_dates_not_trading_days",
            "source": "synthetic", "quantity_unit": "share", "trading_value_unit": "KRW",
            "totals": {"individual": -50000 * count, "foreign": 40000 * count,
                       "institution": 10000 * count, "trading_value": 1000000 * count},
            "published_at": None, "observed_at": None, "retrieved_at": None,
            "observation_reason": "synthetic_no_external_observation"}


def build(row, fixture_id, version=1):
    fixture_selection(fixture_id, version)
    source = receipt(row)
    try:
        data = _data(source["request"]["as_of"], FIXTURES[fixture_id])
        body = {"contract_version": 1, "mode": "synthetic_only", "source_receipt": source,
                "fixture": {"id": fixture_id, "version": version, "schema_id": "flow.synthetic.rows.v1",
                            "data": data, "content_sha256": digest(canonical(data))},
                "preparation_spec": dict(SPEC)}
        text = canonical(body)
        validate(text)
        return text
    except Exception:
        raise SnapshotError("invalid") from None


def _keys(value, keys):
    if type(value) is not dict or set(value) != set(keys):
        raise SnapshotError("invalid")


def validate(text):
    """Validate stored bytes independently of the current fixture catalog/generator."""
    body = decode(text)
    _keys(body, ("contract_version", "mode", "source_receipt", "fixture", "preparation_spec"))
    if type(body["contract_version"]) is not int or body["contract_version"] != 1 or body["mode"] != "synthetic_only":
        raise SnapshotError("invalid")
    # Comparing canonical bytes preserves bool/int and all nested type distinctions.
    expected_spec = {"version": 1, "provider": "fixture", "executable": False,
                     "external_calls_allowed": 0, "max_cost": 0, "reservation_status": "not_reserved"}
    if canonical(body["preparation_spec"]) != canonical(expected_spec):
        raise SnapshotError("invalid")
    source = body["source_receipt"]
    _keys(source, ("reference", "request_contract_version", "request", "request_fingerprint"))
    _keys(source["reference"], ("request_id", "run_id", "attempt_id", "owner_user_id"))
    try:
        for value in source["reference"].values():
            if type(value) is not str or str(UUID(value)) != value:
                raise SnapshotError("invalid")
        if type(source["request_contract_version"]) is not int or source["request_contract_version"] != 1:
            raise SnapshotError("invalid")
        req = FlowAdmissionRequest.model_validate(dict(source["request"], idempotency_key="cf006-internal-validation"))
        if canonical(req.normalized_input()) != canonical(source["request"]) or req.input_fingerprint() != source["request_fingerprint"]:
            raise SnapshotError("invalid")
        fixture = body["fixture"]
        _keys(fixture, ("id", "version", "schema_id", "data", "content_sha256"))
        counts = {"flow.synthetic.full20": 20, "flow.synthetic.short4": 4}
        if type(fixture["version"]) is not int or fixture["version"] != 1 or fixture["id"] not in counts or fixture["schema_id"] != "flow.synthetic.rows.v1":
            raise SnapshotError("invalid")
        data = fixture["data"]
        _keys(data, ("rows", "calendar", "source", "quantity_unit", "trading_value_unit", "totals",
                     "published_at", "observed_at", "retrieved_at", "observation_reason"))
        count = counts[fixture["id"]]
        if (data["calendar"] != "consecutive_calendar_dates_not_trading_days" or data["source"] != "synthetic"
                or data["quantity_unit"] != "share" or data["trading_value_unit"] != "KRW"
                or data["published_at"] is not None or data["observed_at"] is not None or data["retrieved_at"] is not None
                or data["observation_reason"] != "synthetic_no_external_observation"
                or type(data["rows"]) is not list or len(data["rows"]) != count):
            raise SnapshotError("invalid")
        end = req.as_of.astimezone(UTC).date()
        numbers = {"individual": -50000, "foreign": 40000, "institution": 10000, "trading_value": 1000000}
        for n, row in enumerate(data["rows"]):
            _keys(row, ("date", *numbers))
            if type(row["date"]) is not str or row["date"] != (end - timedelta(days=count - 1 - n)).isoformat():
                raise SnapshotError("invalid")
            if any(type(row[key]) is not int or row[key] != value for key, value in numbers.items()):
                raise SnapshotError("invalid")
        _keys(data["totals"], numbers)
        if any(type(data["totals"][key]) is not int or data["totals"][key] != value * count for key, value in numbers.items()):
            raise SnapshotError("invalid")
        if fixture["content_sha256"] != digest(canonical(data)):
            raise SnapshotError("invalid")
    except Exception:
        raise SnapshotError("invalid") from None
    return body


@dataclass(frozen=True)
class SealedInput:
    id: UUID
    run_id: UUID
    owner_user_id: UUID
    sealed_at: datetime
    input_json: str
    input_sha256: str

    @property
    def body(self):
        return validate(self.input_json)  # A fresh, independent tree on every access.


def read_seal(snapshot, row):
    try:
        if (type(snapshot.contract_version) is not int or snapshot.contract_version != 1
                or snapshot.mode != "synthetic_only" or snapshot.run_id != row.id
                or snapshot.owner_user_id != row.owner_user_id
                or type(snapshot.input_sha256) is not str
                or re.fullmatch(r"[0-9a-f]{64}", snapshot.input_sha256) is None
                or digest(snapshot.input_json) != snapshot.input_sha256
                or not isinstance(snapshot.id, UUID)
                or not isinstance(snapshot.sealed_at, datetime) or snapshot.sealed_at.utcoffset() is None):
            raise SnapshotError("corrupt")
        body = validate(snapshot.input_json)
        if canonical(body["source_receipt"]) != canonical(receipt(row)):
            raise SnapshotError("corrupt")
        return SealedInput(snapshot.id, snapshot.run_id, snapshot.owner_user_id, snapshot.sealed_at,
                           snapshot.input_json, snapshot.input_sha256)
    except Exception:
        raise SnapshotError("corrupt") from None
