"""Real service/repositories/PostgreSQL; synthetic producer output and no AI calls.

This is not login/authorization/run admission/worker or complete Flow integration.
"""

from copy import deepcopy
from datetime import date
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, update

from db.models.common.agent_report import AgentReport
from db.models.common.stock import Stock
from db.models.flow.flow_report import FlowReport
from db.models.flow.report_interpretation import FlowReportInterpretation
from db.models.flow.report_verification import FlowReportVerification
from src.modules.flow.infrastructure import report_repository as flow_repo
from src.modules.flow.api.schemas import FlowReportSaveRequest
from src.modules.flow.application.report_service import (
    PAYLOAD_SNAPSHOT_KEY,
    STORAGE_FORMAT_KEY,
    FlowPayloadError,
    FlowStoredPayloadError,
)
from tests.fixtures.flow_payload import make_flow_payload


async def test_postgres_legacy_v1_roundtrip(flow_db):
    """Existing split-table v1 read contract; independent of proposed snapshot storage."""
    payload = make_flow_payload()
    report_id = UUID(payload["report_id"])
    flow_db.report_ids.append(report_id)
    meta = payload["meta"]
    verification = payload["verification"]
    interpretation_meta = payload["interpretation_meta"]
    await flow_repo.ensure_stock(
        flow_db.session,
        stock_code=meta["ticker"],
        stock_name=meta["stock_name"],
        market=meta["market"],
    )
    await flow_repo.add_report(
        flow_db.session,
        report=FlowReport(
            id=report_id,
            ticker=meta["ticker"],
            stock_code=meta["ticker"],
            stock_name=meta["stock_name"],
            market=meta["market"],
            base_date=date.fromisoformat(meta["base_date"]),
            signals=payload["signals"],
            alignment=payload["signals"]["alignment"],
            trace_id=payload["trace_id"],
            data_status=payload["data_status"],
        ),
        interpretation=FlowReportInterpretation(
            id=uuid4(),
            report_id=report_id,
            interpretation=payload["interpretation"],
            interpretation_source=interpretation_meta["source"],
            provider=interpretation_meta["provider"],
            model=interpretation_meta["model"],
        ),
        verification=FlowReportVerification(
            id=uuid4(),
            report_id=report_id,
            gate1_passed=verification["gate1"]["passed"],
            gate2_passed=verification["gate2"]["passed"],
            gate3_passed=verification["gate3"]["passed"],
            checks={key: verification[key] for key in ("gate1", "gate2", "gate3")},
            outcome=verification["outcome"],
            regen_count=verification["regen_count"],
        ),
    )
    await flow_db.session.commit()
    flow_db.session.expire_all()
    assert await flow_db.service.get_report(report_id) is None
    root = await flow_repo.get_report(flow_db.session, report_id)
    interp = await flow_repo.get_interpretation(flow_db.session, report_id)
    verif = await flow_repo.get_verification(flow_db.session, report_id)
    from src.modules.flow.application.report_service import FlowReportService

    assert FlowReportService._reconstruct_payload(root, interp, verif, []) == payload


@pytest.mark.parametrize("variant", ["normal", "limited", "additive"])
async def test_postgres_snapshot_roundtrip(flow_db, variant):
    payload = make_flow_payload()
    if variant == "limited":
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
    if variant == "additive":
        payload.pop("data_status")
        payload.pop("trace_id")
        payload["meta"]["extension"] = {"unit": "백만원", "period_start": "2026-11-01"}
    report_id = UUID(payload["report_id"])
    flow_db.report_ids.append(report_id)
    original = deepcopy(payload)
    await flow_db.service.save_report(
        FlowReportSaveRequest(payload=payload, question="합성 DB 검증")
    )
    flow_db.session.expire_all()
    actual = await flow_db.service.get_report(report_id)
    assert actual.report == original
    assert actual.report_id == report_id
    root = await flow_db.session.get(FlowReport, report_id)
    index = await flow_db.session.scalar(
        select(AgentReport).where(AgentReport.agent_report_id == report_id)
    )
    assert root.stock_code == index.stock_code == original["meta"]["ticker"]
    assert root.base_date.isoformat() == original["meta"]["base_date"]
    verification = await flow_db.session.scalar(
        select(FlowReportVerification).where(
            FlowReportVerification.report_id == report_id
        )
    )
    assert verification.checks[PAYLOAD_SNAPSHOT_KEY] == original


@pytest.mark.parametrize("invalid", ["nested", "date", "version"])
async def test_postgres_invalid_input_has_no_stock_or_result_writes(flow_db, invalid):
    payload = make_flow_payload()
    if invalid == "nested":
        payload["meta"] = []
    elif invalid == "date":
        payload["meta"]["base_date"] = "2026-02-30"
    else:
        payload["version"] = 2
    counts = [
        await flow_db.session.scalar(select(func.count()).select_from(model))
        for model in (Stock, FlowReport, AgentReport)
    ]
    request = FlowReportSaveRequest.model_construct(
        payload=payload, question="합성 DB 검증"
    )
    with pytest.raises(FlowPayloadError):
        await flow_db.service.save_report(request)
    after = [
        await flow_db.session.scalar(select(func.count()).select_from(model))
        for model in (Stock, FlowReport, AgentReport)
    ]
    assert after == counts


async def test_postgres_unsupported_stored_version_is_not_relabelled(flow_db):
    payload = make_flow_payload()
    report_id = UUID(payload["report_id"])
    flow_db.report_ids.append(report_id)
    await flow_db.service.save_report(
        FlowReportSaveRequest(payload=payload, question="합성 DB 검증")
    )
    row = await flow_db.session.scalar(
        select(FlowReportVerification).where(
            FlowReportVerification.report_id == report_id
        )
    )
    checks = deepcopy(row.checks)
    checks[PAYLOAD_SNAPSHOT_KEY]["version"] = 2
    row.checks = checks
    await flow_db.session.commit()
    flow_db.session.expire_all()
    with pytest.raises(FlowStoredPayloadError):
        await flow_db.service.get_report(report_id)


async def test_postgres_new_snapshot_lists_and_delete_cascade(flow_db):

    payload = make_flow_payload()
    report_id = UUID(payload["report_id"])
    flow_db.report_ids.append(report_id)
    await flow_db.service.save_report(
        FlowReportSaveRequest(payload=payload, question="합성 DB 검증")
    )
    flow_db.session.expire_all()
    common = flow_db.service
    own_list = await flow_db.service.list_reports(stock_code=None, limit=20, offset=0)
    common_list = await common.list_common(
        agent_type="flow", client_session_id=None, stock_code=None, limit=20, offset=0
    )
    archive = await common.list_report_archive(agent_type="flow")
    assert (
        own_list.items[0].agent_report_id == common_list[0].agent_report_id == report_id
    )
    assert len(archive.items) == 1
    assert await flow_db.service.delete_report(report_id)
    flow_db.session.expire_all()
    assert await flow_db.service.get_report(report_id) is None
    assert (
        await flow_db.service.list_reports(stock_code=None, limit=20, offset=0)
    ).items == []
    for model, column in (
        (FlowReport, FlowReport.id),
        (FlowReportInterpretation, FlowReportInterpretation.report_id),
        (FlowReportVerification, FlowReportVerification.report_id),
        (AgentReport, AgentReport.agent_report_id),
    ):
        assert (
            await flow_db.session.scalar(
                select(func.count()).select_from(model).where(column == report_id)
            )
            == 0
        )


@pytest.mark.parametrize(
    "damage",
    [
        "root",
        "interpretation",
        "verification",
        "index",
        "snapshot_missing",
        "format_missing",
        "checks_empty",
        "child_missing",
        "index_marker_missing",
    ],
)
async def test_postgres_damaged_projection_fails_closed(flow_db, damage):
    payload = make_flow_payload()
    report_id = UUID(payload["report_id"])
    flow_db.report_ids.append(report_id)
    await flow_db.service.save_report(
        FlowReportSaveRequest(payload=payload, question="合成 DB 검증")
    )
    root = await flow_db.session.get(FlowReport, report_id)
    interpretation = await flow_db.session.scalar(
        select(FlowReportInterpretation).where(
            FlowReportInterpretation.report_id == report_id
        )
    )
    verification = await flow_db.session.scalar(
        select(FlowReportVerification).where(
            FlowReportVerification.report_id == report_id
        )
    )
    index = await flow_db.session.scalar(
        select(AgentReport).where(AgentReport.agent_report_id == report_id)
    )
    if damage == "root":
        root.stock_name = "different"
    elif damage == "interpretation":
        interpretation.interpretation = "different"
    elif damage == "verification":
        verification.gate2_passed = False
    elif damage == "index":
        index.answer_text = "different"
    elif damage == "snapshot_missing":
        checks = deepcopy(verification.checks)
        del checks[PAYLOAD_SNAPSHOT_KEY]
        verification.checks = checks
    elif damage == "format_missing":
        checks = deepcopy(verification.checks)
        del checks[STORAGE_FORMAT_KEY]
        verification.checks = checks
    elif damage == "checks_empty":
        verification.checks = {}
    elif damage == "child_missing":
        await flow_db.session.delete(interpretation)
    elif damage == "index_marker_missing":
        summary = deepcopy(index.summary)
        del summary[STORAGE_FORMAT_KEY]
        index.summary = summary
    await flow_db.session.commit()
    flow_db.session.expire_all()
    with pytest.raises(FlowStoredPayloadError):
        await flow_db.service.get_report(report_id)
    with pytest.raises(FlowStoredPayloadError):
        await flow_db.service.list_reports(stock_code=None, limit=20, offset=0)


async def test_postgres_failed_save_can_be_rolled_back_without_partial_rows(
    flow_db, monkeypatch
):
    from src.modules.flow.application import report_service as module

    async def fail_index(*args, **kwargs):
        raise RuntimeError("synthetic index failure")

    monkeypatch.setattr(module.agent_repo, "add", fail_index)
    payload = make_flow_payload()
    flow_db.report_ids.append(UUID(payload["report_id"]))
    with pytest.raises(RuntimeError, match="synthetic index failure"):
        await flow_db.service.save_report(
            FlowReportSaveRequest(payload=payload, question="합성 DB 검증")
        )
    # Service rolls back the full failed write; no publish-retry service is implied.
    for model in (
        Stock,
        FlowReport,
        FlowReportInterpretation,
        FlowReportVerification,
        AgentReport,
    ):
        assert (
            await flow_db.session.scalar(select(func.count()).select_from(model)) == 0
        )


@pytest.mark.parametrize("bad", ["\x00", "\ud800", "\udfff"])
@pytest.mark.parametrize("location", ["key", "value"])
async def test_postgres_incompatible_json_strings_cannot_reach_writes(
    flow_db, bad, location
):
    payload = make_flow_payload()
    payload["extension"] = {
        "nested": [
            {"fixture" + bad: 0} if location == "key" else {"text": "fixture" + bad}
        ]
    }
    original = deepcopy(payload)
    request = FlowReportSaveRequest.model_construct(
        payload=payload, question="합성 DB 검증"
    )
    with pytest.raises(FlowPayloadError):
        await flow_db.service.save_report(request)
    assert payload == original
    for model in (
        Stock,
        FlowReport,
        FlowReportInterpretation,
        FlowReportVerification,
        AgentReport,
    ):
        assert (
            await flow_db.session.scalar(select(func.count()).select_from(model)) == 0
        )


@pytest.mark.parametrize(
    "damage", ["number_to_bool", "bool_to_number", "gate_number_to_bool"]
)
async def test_postgres_json_number_boolean_damage_is_rejected(flow_db, damage):
    payload = make_flow_payload()
    report_id = UUID(payload["report_id"])
    flow_db.report_ids.append(report_id)
    await flow_db.service.save_report(
        FlowReportSaveRequest(payload=payload, question="합성 DB 검증")
    )
    if damage == "gate_number_to_bool":
        row = await flow_db.session.scalar(
            select(FlowReportVerification).where(
                FlowReportVerification.report_id == report_id
            )
        )
        checks = deepcopy(row.checks)
        checks["gate1"]["gate"] = True
        await flow_db.session.execute(
            update(FlowReportVerification)
            .where(FlowReportVerification.report_id == report_id)
            .values(checks=checks)
        )
    else:
        root = await flow_db.session.get(FlowReport, report_id)
        signals = deepcopy(root.signals)
        signals["strength"]["외국인"][
            "ratio" if damage == "number_to_bool" else "strong"
        ] = False if damage == "number_to_bool" else 0
        # Assigning an equal-by-Python dict can be skipped by ORM dirty tracking.
        # Force the SQL write, then verify the actual JSONB type before testing reads.
        await flow_db.session.execute(
            update(FlowReport).where(FlowReport.id == report_id).values(signals=signals)
        )
    await flow_db.session.commit()
    flow_db.session.expire_all()
    if damage == "gate_number_to_bool":
        actual = await flow_db.session.scalar(
            select(FlowReportVerification.checks).where(
                FlowReportVerification.report_id == report_id
            )
        )
        assert actual["gate1"]["gate"] is True
    else:
        actual = await flow_db.session.scalar(
            select(FlowReport.signals).where(FlowReport.id == report_id)
        )
        if damage == "number_to_bool":
            assert actual["strength"]["외국인"]["ratio"] is False
        else:
            actual_value = actual["strength"]["외국인"]["strong"]
            assert type(actual_value) is int and actual_value == 0
    with pytest.raises(FlowStoredPayloadError):
        await flow_db.service.get_report(report_id)
    with pytest.raises(FlowStoredPayloadError):
        await flow_db.service.list_reports(stock_code=None, limit=20, offset=0)


async def test_postgres_valid_unicode_and_literal_escapes_roundtrip(flow_db):
    payload = make_flow_payload()
    payload["extension"] = {"한글😀": ["e\u0301", r"\u0000", r"\ud800"]}
    report_id = UUID(payload["report_id"])
    flow_db.report_ids.append(report_id)
    original = deepcopy(payload)
    await flow_db.service.save_report(
        FlowReportSaveRequest(payload=payload, question="질문😀")
    )
    flow_db.session.expire_all()
    assert (await flow_db.service.get_report(report_id)).report == original
