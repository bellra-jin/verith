"""Synthetic contract tests. No database, principal verification, or external AI."""

from __future__ import annotations

import copy
import json
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from src.api.schemas.flow_execution import (
    CommonResponse,
    ContractViolation,
    DataObservation,
    ErrorCode,
    ExecutionContext,
    FlowRunRequest,
    FlowRunState,
    IdempotencyReference,
    SafeError,
    bind_flow_result,
    validate_result_binding,
)
from src.api.schemas.flow_payload import FlowPayloadV1, validate_flow_payload
from src.api.schemas.flow_report import FlowReportSaveRequest
from src.api.services import flow_report_service as service_module
from src.api.services.flow_report_service import (
    PAYLOAD_SNAPSHOT_KEY,
    STORAGE_FORMAT_KEY,
    FlowPayloadError,
    FlowReportService,
    FlowStoredPayloadError,
)
from tests.fixtures.flow_payload import make_flow_payload


@pytest.fixture
def payload():
    return make_flow_payload()


def changed(payload, path, value):
    result = copy.deepcopy(payload)
    node = result
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    return result


INVALID_VALUES = [
    (("meta",), []),
    (("meta",), "bad"),
    (("meta",), 7),
    (("meta",), None),
    (("signals",), []),
    (("signals",), "bad"),
    (("verification",), []),
    (("verification", "gate1"), "bad"),
    (("verification", "gate1", "passed"), "true"),
    (("verification", "gate1", "checks"), "bad"),
    (("verification", "gate1", "failures"), [1]),
    (("verification", "gate1", "gate"), 2),
    (("verification", "gate1", "gate"), True),
    (("verification", "regen_count"), -1),
    (("interpretation_meta",), 12),
    (("report_id",), "bad"),
    (("report_id",), None),
    (("report_id",), 123),
    (("meta", "ticker"), "5930"),
    (("meta", "ticker"), 5930),
    (("meta", "ticker"), "００５９３０"),
    (("meta", "base_date"), "2026-02-30"),
    (("meta", "base_date"), "2026-11-05T00:00:00"),
    (("meta", "base_date"), "20261105"),
    (("meta", "base_date"), ""),
    (("meta", "base_date"), 1793836800),
    (("signals", "daily", 0, "date"), "2026-13-01"),
    (("signals", "price_daily", 0, "date"), "2026-02-29"),
    (("signals", "ownership", 0, "date"), "yesterday"),
    (("signals", "strength", "외국인", "ratio"), "0"),
    (("signals", "strength", "외국인", "ratio"), None),
    (("signals", "strength", "외국인", "ratio"), True),
    (("signals", "strength", "외국인", "ratio"), float("nan")),
    (("signals", "price_daily", 0, "close"), float("inf")),
    (("signals", "consecutive", "외국인", "days"), -1),
    (("signals", "persistence", "외국인"), {}),
    (("signals", "daily", 0, "기관"), None),
    (("signals", "inst_detail"), {"증권": None}),
    (("signals", "ownership", 0, "ratio"), False),
    (("version",), 2),
    (("version",), "1"),
    (("version",), True),
    (("version",), 1.0),
    (("version",), None),
    (("data_status",), "normal"),
    (("data_status",), "data_limited"),
    (("verification", "outcome"), "fact_only"),
    (("verification", "gate3", "passed"), False),
    (("interpretation_meta", "source"), "fallback"),
]


@pytest.fixture
def memory(monkeypatch):
    rows = SimpleNamespace(
        report=None, interpretation=None, verification=None, index=None
    )

    async def store(session, **values):
        for key, value in values.items():
            setattr(rows, key, value)
        # Simulate a JSON serializer roundtrip, never real persistence.
        rows.report.signals = json.loads(json.dumps(rows.report.signals))
        rows.verification.checks = json.loads(json.dumps(rows.verification.checks))

    async def store_index(session, index):
        rows.index = index

    mocks = {}
    for name in (
        "ensure_stock",
        "add_report",
        "get_report",
        "get_interpretation",
        "get_verification",
        "get_agent_indexes",
        "get_report_parts",
    ):
        method = AsyncMock()
        mocks[name] = method
        monkeypatch.setattr(service_module.flow_repo, name, method)
    mocks["add_report"].side_effect = store
    for name in ("report", "interpretation", "verification"):
        mocks[f"get_{name}"].side_effect = lambda *args, name=name: getattr(rows, name)
    mocks["index"] = AsyncMock(side_effect=store_index)
    mocks["get_agent_indexes"].side_effect = lambda *args: (
        [rows.index] if rows.index else []
    )
    mocks["get_report_parts"].side_effect = lambda *args: (
        [rows.report] if rows.report else [],
        [rows.interpretation] if rows.interpretation else [],
        [rows.verification] if rows.verification else [],
        [rows.index] if rows.index else [],
    )
    monkeypatch.setattr(service_module.agent_repo, "add", mocks["index"])
    monkeypatch.setattr(
        service_module.agent_repo,
        "list_reports",
        AsyncMock(
            side_effect=lambda *args, **kwargs: [rows.index] if rows.index else []
        ),
    )
    session = SimpleNamespace(commit=AsyncMock())
    return SimpleNamespace(
        service=FlowReportService(session), session=session, mocks=mocks, rows=rows
    )


@pytest.fixture
async def client(memory):
    # Load settings only after isolated_environment and no_network are active.
    from src.api.routes.flow_reports import get_flow_report_service, router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_flow_report_service] = lambda: memory.service
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://unit"
    ) as client:
        yield client


def assert_no_writes(memory):
    for name in ("ensure_stock", "add_report", "index"):
        memory.mocks[name].assert_not_awaited()
    memory.session.commit.assert_not_awaited()


@pytest.mark.parametrize("path,value", INVALID_VALUES)
async def test_invalid_nested_payload_returns_safe_422_before_any_write(
    client, memory, payload, path, value
):
    bad = changed(payload, path, value)
    # Non-finite numbers cannot be sent by httpx's strict JSON serializer.
    if isinstance(value, float) and value != value or value == float("inf"):
        with pytest.raises(ValidationError):
            FlowReportSaveRequest(payload=bad, question="질문")
    else:
        response = await client.post(
            "/api/flow/reports/save", json={"payload": bad, "question": "질문"}
        )
        assert response.status_code == 422
        expected = "UNSUPPORTED_VERSION" if path == ("version",) else "INPUT_INVALID"
        assert response.json() == {
            "detail": SafeError(code=expected).model_dump(mode="json")
        }
    assert_no_writes(memory)


@pytest.mark.parametrize(
    "field",
    ["version", "report_id", "meta", "signals", "verification", "interpretation"],
)
async def test_missing_required_field_rejected(client, memory, payload, field):
    del payload[field]
    response = await client.post(
        "/api/flow/reports/save", json={"payload": payload, "question": "질문"}
    )
    assert response.status_code == 422
    assert_no_writes(memory)


@pytest.mark.parametrize("value", [[], "bad", None, 12])
async def test_service_revalidates_mutated_request_before_writing(
    memory, payload, value
):
    request = FlowReportSaveRequest(payload=payload, question="질문")
    request.payload["meta"] = value
    with pytest.raises(FlowPayloadError):
        await memory.service.save_report(request)
    assert_no_writes(memory)


async def test_current_producer_payload_roundtrip_preserves_identity_values_periods_and_checks(
    client, memory, payload
):
    original = copy.deepcopy(payload)
    response = await client.post(
        "/api/flow/reports/save", json={"payload": payload, "question": "질문"}
    )
    assert response.status_code == 201, response.text
    assert response.json()["report"] == original
    report_id = UUID(original["report_id"])
    assert (
        memory.rows.report.id
        == memory.rows.interpretation.report_id
        == memory.rows.verification.report_id
        == report_id
    )
    assert (
        memory.rows.report.ticker
        == memory.rows.report.stock_code
        == memory.rows.index.stock_code
        == "005930"
    )
    assert memory.rows.report.base_date == date(2026, 11, 5)
    assert (
        memory.rows.index.owner_user_id is None
    )  # legacy, not authenticated ownership
    result = await client.get(f"/api/flow/reports/{report_id}")
    assert result.status_code == 200
    assert result.json() == {"report_id": str(report_id), "report": original}
    assert payload == original


async def test_additive_v1_fields_and_omissions_are_preserved(memory, payload):
    for field in ("trace_id", "data_status", "interpretation_meta"):
        payload.pop(field)
    payload["verification"].pop("outcome")
    payload["verification"].pop("regen_count")
    payload["meta"]["future_metadata"] = {
        "unit": "백만원",
        "period": ["2026-11-01", "2026-11-05"],
    }
    payload["future_flag"] = False
    payload["trace_id"] = "legacy-trace-string"
    await memory.service.save_report(
        FlowReportSaveRequest(payload=payload, question="질문")
    )
    result = await memory.service.get_report(UUID(payload["report_id"]))
    assert result.report == payload


async def test_data_limited_missing_is_distinct_from_real_zero(memory, payload):
    payload["signals"]["price_daily"] = None
    payload["data_status"] = "data_limited"
    payload["verification"]["gate3"] = None
    payload["verification"]["outcome"] = "fact_only"
    payload["interpretation"] = None
    payload["interpretation_meta"] = {
        "source": "fallback",
        "provider": None,
        "model": None,
    }
    await memory.service.save_report(
        FlowReportSaveRequest(payload=payload, question="질문")
    )
    result = await memory.service.get_report(UUID(payload["report_id"]))
    assert result.report == payload
    assert result.report["signals"]["strength"]["외국인"]["ratio"] == 0
    assert result.report["signals"]["price_daily"] is None


async def test_explicit_null_base_date_and_signals_not_replaced(memory, payload):
    payload.update(
        signals=None,
        interpretation=None,
        verification=None,
        interpretation_meta=None,
        data_status="data_limited",
    )
    payload["meta"]["base_date"] = None
    await memory.service.save_report(
        FlowReportSaveRequest(payload=payload, question="질문")
    )
    assert memory.rows.report.signals is None
    assert (
        await memory.service.get_report(UUID(payload["report_id"]))
    ).report == payload


async def test_explicit_legacy_v1_adapter(memory, payload):
    await memory.service.save_report(
        FlowReportSaveRequest(payload=payload, question="질문")
    )
    del memory.rows.verification.checks[PAYLOAD_SNAPSHOT_KEY]
    del memory.rows.verification.checks[STORAGE_FORMAT_KEY]
    del memory.rows.index.summary[STORAGE_FORMAT_KEY]
    result = await memory.service.get_report(UUID(payload["report_id"]))
    assert result.report == payload


@pytest.mark.parametrize(
    "field,value", [("version", 2), ("report_id", str(uuid4())), ("meta", [])]
)
async def test_invalid_stored_snapshot_is_safe_error_not_relabelled(
    client, memory, payload, field, value
):
    await memory.service.save_report(
        FlowReportSaveRequest(payload=payload, question="질문")
    )
    snapshot = memory.rows.verification.checks[PAYLOAD_SNAPSHOT_KEY]
    snapshot[field] = value
    result = await client.get(f"/api/flow/reports/{payload['report_id']}")
    assert result.status_code == 502
    assert result.json()["detail"]["code"] == "RESULT_CONTRACT_INVALID"
    assert snapshot[field] == value


@pytest.mark.parametrize("checks", [["bad"], [], "bad", 0])
def test_invalid_legacy_checks_never_raise_attribute_error(checks):
    report = SimpleNamespace()
    with pytest.raises(FlowStoredPayloadError):
        FlowReportService._reconstruct_payload(
            report, None, SimpleNamespace(checks=checks)
        )


@pytest.mark.parametrize(
    "extension", [{1: "bad-key"}, {"bad": (1, 2)}, {"bad": float("nan")}]
)
def test_extensions_must_be_finite_native_json(payload, extension):
    payload["extension"] = extension
    with pytest.raises(ValueError):
        validate_flow_payload(payload)


@pytest.fixture
def public_input():
    return {
        "ticker": "005930",
        "question": "분석",
        "as_of": "2026-11-06T00:00:00Z",
        "idempotency_key": "fixture-key",
    }


@pytest.mark.parametrize(
    "field,value",
    [
        ("owner_user_id", str(uuid4())),
        ("owner", "spoof"),
        ("payload", {}),
        ("passed", True),
        ("client_session_id", "not-auth"),
        ("run_id", str(uuid4())),
    ],
)
def test_public_input_cannot_assert_internal_context(public_input, field, value):
    with pytest.raises(ValidationError):
        FlowRunRequest(**public_input, **{field: value})


@pytest.mark.parametrize(
    "field,value",
    [
        ("question", "  "),
        ("as_of", "2026-02-30T00:00:00Z"),
        ("as_of", "2026-11-06T00:00:00"),
        ("as_of", 123),
        ("as_of", "123"),
        ("as_of", "1793923200.0"),
        ("ticker", "123"),
        ("idempotency_key", " "),
    ],
)
def test_public_input_rejects_invalid_fields(public_input, field, value):
    public_input[field] = value
    with pytest.raises(ValidationError):
        FlowRunRequest(**public_input)


def test_owner_scoped_idempotency_contract(public_input):
    request = FlowRunRequest(**public_input)
    owner, run = uuid4(), uuid4()
    stored = IdempotencyReference(
        owner_user_id=owner,
        key=request.idempotency_key,
        input_fingerprint=request.input_fingerprint(),
        run_id=run,
    )
    assert stored.validate_replay(owner, request) == run
    public_input["as_of"] = "2026-11-06T09:00:00+09:00"
    assert stored.validate_replay(owner, FlowRunRequest(**public_input)) == run
    public_input["question"] = "다른 입력"
    with pytest.raises(ContractViolation) as error:
        stored.validate_replay(owner, FlowRunRequest(**public_input))
    assert error.value.error.http_status == 409
    with pytest.raises(ContractViolation) as error:
        stored.validate_replay(uuid4(), request)
    assert error.value.error.http_status == 404


def test_result_id_attempt_content_and_deletion_contract(payload):
    context = ExecutionContext(
        owner_user_id=uuid4(), request_id=uuid4(), run_id=uuid4(), attempt_id=uuid4()
    )
    result = bind_flow_result(context, payload)
    assert str(result.report_id) == payload["report_id"]
    validate_result_binding(
        context, bind_flow_result(context, copy.deepcopy(payload)), existing=result
    )
    for mutation in ({"report_id": str(uuid4())}, {"interpretation": "다른 최종 해석"}):
        other = bind_flow_result(context, {**payload, **mutation})
        with pytest.raises(ContractViolation) as error:
            validate_result_binding(context, other, existing=result)
        assert error.value.error.http_status == 409
    with pytest.raises(ContractViolation) as error:
        validate_result_binding(context, result, deleted=True)
    assert error.value.error.http_status == 404
    with pytest.raises(ContractViolation) as error:
        validate_result_binding(
            context.model_copy(update={"attempt_id": uuid4()}), result
        )
    assert error.value.error.code == ErrorCode.RESULT_CONTRACT_INVALID
    with pytest.raises(ContractViolation) as error:
        bind_flow_result(context, {**payload, "version": 99})
    assert error.value.error.code == ErrorCode.RESULT_CONTRACT_INVALID


def test_common_response_safe_errors_roundtrip_and_state_axes():
    for code in ErrorCode:
        error = SafeError(code=code)
        response = CommonResponse[dict](request_id=uuid4(), error=error)
        assert (
            CommonResponse[dict].model_validate_json(response.model_dump_json())
            == response
        )
    with pytest.raises(ValidationError):
        SafeError(code=ErrorCode.INPUT_INVALID, message="secret raw exception")
    for values in ({}, {"data": {}, "error": SafeError(code=ErrorCode.INPUT_INVALID)}):
        with pytest.raises(ValidationError):
            CommonResponse[dict](request_id=uuid4(), **values)
    refs = {"request_id": uuid4(), "run_id": uuid4(), "attempt_id": uuid4()}
    for state in ("pending", "running", "succeeded", "failed", "unknown"):
        FlowRunState(
            **refs,
            execution_status=state,
            storage_status="not_stored",
            error=SafeError(code=ErrorCode.RESULT_CONTRACT_INVALID)
            if state == "failed"
            else None,
        )
    with pytest.raises(ValidationError):
        FlowRunState(**refs, execution_status="running", storage_status="stored")


@pytest.mark.parametrize(
    "value,reason,valid",
    [
        (0, None, True),
        (None, "미수집", True),
        (None, None, False),
        (0, "미수집", False),
        (True, None, False),
        (float("inf"), None, False),
    ],
)
def test_observation_value_missing_unit_and_period(value, reason, valid):
    values = dict(
        source="synthetic",
        as_of="2026-11-06",
        period_start="2026-11-01",
        period_end="2026-11-05",
        unit="백만원",
        value=value,
        missing_reason=reason,
    )
    if valid:
        assert DataObservation(**values).value == value
    else:
        with pytest.raises(ValidationError):
            DataObservation(**values)
    for mutation in (
        {"unit": " "},
        {"source": ""},
        {"period_start": "2026-11-07"},
        {"as_of": "2026-11-04"},
        {"period_end": "2026-02-30"},
    ):
        with pytest.raises(ValidationError):
            DataObservation(**{**values, **mutation})


def test_version_schema_and_payload_validation_do_not_change_input(payload):
    assert FlowPayloadV1.model_json_schema()["properties"]["version"]["const"] == 1
    original = copy.deepcopy(payload)
    assert validate_flow_payload(payload) is payload
    assert payload == original
    assert FlowReportSaveRequest.model_json_schema()["properties"]["payload"][
        "$ref"
    ].endswith("/FlowPayloadV1")


@pytest.mark.parametrize("field", ["owner_user_id", "run_id", "passed"])
async def test_legacy_save_rejects_extra_internal_claims(
    client, memory, payload, field
):
    response = await client.post(
        "/api/flow/reports/save",
        json={
            "payload": payload,
            "question": "질문",
            field: "spoofed",
        },
    )
    assert response.status_code == 422
    assert_no_writes(memory)


@pytest.mark.parametrize("field", ["source", "provider", "model"])
def test_missing_interpretation_has_no_false_provenance(payload, field):
    payload["interpretation"] = None
    payload["verification"]["gate3"] = None
    payload["verification"]["outcome"] = "fact_only"
    payload["interpretation_meta"] = {
        "source": "fallback",
        "provider": None,
        "model": None,
    }
    payload["interpretation_meta"][field] = (
        "llm" if field == "source" else "false-provenance"
    )
    with pytest.raises(ValidationError):
        FlowReportSaveRequest(payload=payload, question="질문")


@pytest.mark.parametrize("stock_code", ["００５９３０", "5930", "005930 "])
async def test_list_ticker_filter_is_canonical_ascii(client, memory, stock_code):
    response = await client.get("/api/flow/reports", params={"stock_code": stock_code})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INPUT_INVALID"
    assert_no_writes(memory)


@pytest.mark.parametrize(
    "damage",
    [
        "root",
        "signals",
        "interpretation",
        "verification",
        "gate",
        "summary",
        "index",
        "missing_snapshot",
        "missing_format",
        "unknown_format",
        "empty_checks",
        "no_interpretation",
        "no_verification",
        "no_index",
        "duplicate_index",
        "missing_index_marker",
    ],
)
async def test_new_snapshot_projection_damage_is_rejected_without_legacy_fallback(
    memory, payload, damage
):
    await memory.service.save_report(
        FlowReportSaveRequest(payload=payload, question="질문")
    )
    rows = memory.rows
    if damage == "root":
        rows.report.stock_name = "different"
    elif damage == "signals":
        rows.report.signals["strength"]["외국인"]["ratio"] = 123
    elif damage == "interpretation":
        rows.interpretation.interpretation = "different"
    elif damage == "verification":
        rows.verification.gate2_passed = False
    elif damage == "gate":
        rows.verification.checks["gate2"]["checks"] = ["different"]
    elif damage == "summary":
        rows.index.summary["base_date"] = "2026-11-01"
    elif damage == "index":
        rows.index.answer_text = "different"
    elif damage == "missing_snapshot":
        del rows.verification.checks[PAYLOAD_SNAPSHOT_KEY]
    elif damage == "missing_format":
        del rows.verification.checks[STORAGE_FORMAT_KEY]
    elif damage == "unknown_format":
        rows.verification.checks[STORAGE_FORMAT_KEY] = "unknown"
    elif damage == "empty_checks":
        rows.verification.checks = {}
    elif damage == "no_interpretation":
        rows.interpretation = None
    elif damage == "no_verification":
        rows.verification = None
    elif damage == "no_index":
        rows.index = None
    elif damage == "duplicate_index":
        memory.mocks["get_agent_indexes"].side_effect = lambda *args: [
            rows.index,
            rows.index,
        ]
    elif damage == "missing_index_marker":
        del rows.index.summary[STORAGE_FORMAT_KEY]
    with pytest.raises(FlowStoredPayloadError):
        await memory.service.get_report(UUID(payload["report_id"]))


@pytest.mark.parametrize(
    "endpoint", ["/api/flow/reports", "/api/reports", "/api/reports/archive"]
)
async def test_all_flow_list_paths_reject_inconsistent_snapshot(
    memory, payload, endpoint
):
    from src.api.deps import get_technical_report_service
    from src.api.routes.flow_reports import (
        get_flow_report_service,
        router as flow_router,
    )
    from src.api.routes.reports import router as common_router
    from src.api.services.technical_report_service import TechnicalReportService

    await memory.service.save_report(
        FlowReportSaveRequest(payload=payload, question="질문")
    )
    # Even a removed index format marker cannot bypass list validation.
    del memory.rows.index.summary[STORAGE_FORMAT_KEY]
    memory.rows.index.answer_text = "different"
    app = FastAPI()
    app.include_router(flow_router)
    app.include_router(common_router)
    app.dependency_overrides[get_flow_report_service] = lambda: memory.service
    app.dependency_overrides[get_technical_report_service] = lambda: (
        TechnicalReportService(memory.session, ai_client=None)
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://unit"
    ) as client:
        response = await client.get(endpoint)
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "RESULT_CONTRACT_INVALID"


@pytest.mark.parametrize("bad", ["\x00", "\ud800", "\udfff"])
@pytest.mark.parametrize(
    "location", ["known_value", "nested_value", "nested_key", "root_key"]
)
async def test_jsonb_unrepresentable_strings_are_rejected_before_writes(
    client, memory, payload, bad, location
):
    if location == "known_value":
        payload["meta"]["stock_name"] = "fixture" + bad
    elif location == "nested_value":
        payload["extension"] = {"nested": [{"text": "fixture" + bad}]}
    elif location == "nested_key":
        payload["extension"] = {"nested": [{"fixture" + bad: 0}]}
    else:
        payload["fixture" + bad] = 0
    original = copy.deepcopy(payload)
    with pytest.raises(ValidationError):
        FlowReportSaveRequest(payload=payload, question="질문")
    response = await client.post(
        "/api/flow/reports/save",
        content=json.dumps({"payload": payload, "question": "질문"}, ensure_ascii=True),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert response.json() == {
        "detail": SafeError(code=ErrorCode.INPUT_INVALID).model_dump(mode="json")
    }
    assert payload == original
    assert_no_writes(memory)


@pytest.mark.parametrize(
    "damage", ["number_to_bool", "bool_to_number", "gate_number_to_bool"]
)
async def test_snapshot_projection_distinguishes_json_boolean_and_number(
    memory, payload, damage
):
    await memory.service.save_report(
        FlowReportSaveRequest(payload=payload, question="질문")
    )
    if damage == "number_to_bool":
        memory.rows.report.signals["strength"]["외국인"]["ratio"] = False
    elif damage == "bool_to_number":
        memory.rows.report.signals["strength"]["외국인"]["strong"] = 0
    else:
        memory.rows.verification.checks["gate1"]["gate"] = True
    with pytest.raises(FlowStoredPayloadError):
        await memory.service.get_report(UUID(payload["report_id"]))
    with pytest.raises(FlowStoredPayloadError):
        await memory.service.list_reports(stock_code=None, limit=20, offset=0)


@pytest.mark.parametrize("bad", ["\x00", "\ud800", "\udfff"])
@pytest.mark.parametrize("field", ["question", "client_session_id"])
async def test_non_payload_storage_text_rejected_before_writes(
    client, memory, payload, bad, field
):
    body = {"payload": payload, "question": "질문", field: "fixture" + bad}
    response = await client.post(
        "/api/flow/reports/save",
        content=json.dumps(body, ensure_ascii=True),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert_no_writes(memory)


def test_valid_unicode_and_literal_escape_sequences_are_preserved(payload):
    payload["extension"] = {"한글😀": ["e\u0301", r"\u0000", r"\ud800"]}
    original = copy.deepcopy(payload)
    request = FlowReportSaveRequest(payload=payload, question="질문😀")
    assert request.payload == original
