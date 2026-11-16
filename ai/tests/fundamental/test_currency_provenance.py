from dataclasses import asdict
from src.agents.fundamental.domain.normalization.standardize import MetricValue, standardize_year_rows
from src.agents.fundamental.domain.ratios.calculators import calculate_ratios
from src.agents.fundamental.domain.ratios.trend import build_trend
from src.agents.fundamental.infrastructure.data.regular_disclosure import ShareCountData


ACCOUNTS = {"revenue": "ifrs-full_Revenue", "operating_income": "dart_OperatingIncomeLoss",
    "profit_loss": "ifrs-full_ProfitLoss", "equity": "ifrs-full_Equity", "basic_eps": "ifrs-full_BasicEarningsLossPerShare"}


def normalize(values, currencies, year="2025"):
    rows = []
    for name, value in values.items():
        row = dict(account_id=ACCOUNTS[name], account_nm=ACCOUNTS[name], thstrm_amount=str(value),
                   rcept_no=year+"0301000001", sj_div="BS")
        if name in currencies:
            row["currency"] = currencies[name]
        rows.append(row)
    provenance = {}
    metrics = standardize_year_rows(rows, year, currency_provenance=provenance)
    return metrics, provenance


def test_source_currency_sidecar_preserves_fallback_without_changing_metric_dataclass_shape():
    for missing in (None, "", "   ", 0, False):
        metrics, provenance = normalize({"equity": 100}, {"equity": missing})
        assert provenance == {"equity": False}
        assert metrics["equity"].value == 100
        assert set(asdict(metrics["equity"])) == {"value", "fiscal_year", "rcept_no", "account_id", "account_nm", "sj_div", "currency"}
    metrics, provenance = normalize({"equity": 100}, {})
    assert metrics["equity"].currency == "KRW" and provenance["equity"] is False
    _, known = normalize({"equity": 100}, {"equity": "KRW"})
    assert known["equity"] is True


def test_missing_source_currency_blocks_ratio_not_as_known_mismatch():
    for currencies in ({"equity": "KRW"}, {"profit_loss": "KRW"}, {}):
        metrics, proof = normalize({"profit_loss": 10, "equity": 100}, currencies)
        ratios, evidence, flags = calculate_ratios({"2025": metrics}, currency_provenance={"2025": proof})
        assert ratios["roe"]["value"] is None and ratios["roe"]["status"] == "unavailable"
        assert "원문 통화" in ratios["roe"]["reason"]
        assert "CURRENCY_UNPROVEN_ROE" in flags
        assert "CURRENCY_MISMATCH_ROE" not in flags and "MISSING_ROE" not in flags
        assert not any(e.metric == "roe" for e in evidence)


def test_missing_source_currency_blocks_growth_direction_and_money_trend():
    previous, old_proof = normalize({"revenue": 100, "operating_income": -10}, {}, "2024")
    latest, new_proof = normalize({"revenue": 150, "operating_income": 20}, {"revenue": "KRW", "operating_income": "KRW"})
    data = {"2024": previous, "2025": latest}
    proof = {"2024": old_proof, "2025": new_proof}
    ratios, _, flags = calculate_ratios(data, currency_provenance=proof)
    for name in ("revenue_growth", "operating_income_growth"):
        assert ratios[name]["value"] is None and ratios[name]["status"] == "unavailable"
        assert "direction" not in ratios[name] and "display_value" not in ratios[name]
        assert "CURRENCY_UNPROVEN_"+name.upper() in flags
    trend = build_trend(data, currency_provenance=proof)
    assert trend["years"] == ["2024", "2025"]
    assert trend["revenue"] == [None, None] and trend["op_income"] == [None, None]


def test_missing_source_currency_blocks_eps_bps_not_as_known_non_krw():
    metrics, proof = normalize({"equity": 100, "basic_eps": 2}, {})
    shares = ShareCountData(100, None, None, "보통주", "common_issued_shares", "20260301000002", "2025-12-31")
    ratios, evidence, flags = calculate_ratios({"2025": metrics}, share_count=shares, currency_provenance={"2025": proof})
    for name in ("eps", "bps"):
        assert ratios[name]["value"] is None and ratios[name]["status"] == "unavailable"
        assert "CURRENCY_UNPROVEN_"+name.upper() in flags
        assert "CURRENCY_UNIT_UNSUPPORTED_"+name.upper() not in flags
        assert not any(e.metric == name for e in evidence)


def test_unproven_revenue_does_not_drive_low_base_policy_for_known_operating_income():
    old, old_proof = normalize({"operating_income": 100}, {"operating_income": "KRW"}, "2024")
    new, new_proof = normalize({"operating_income": 180, "revenue": 100000}, {"operating_income": "KRW"})
    ratios, _, flags = calculate_ratios({"2024": old, "2025": new}, currency_provenance={"2024": old_proof, "2025": new_proof})
    assert ratios["operating_income_growth"]["value"] == 80
    assert "direction" not in ratios["operating_income_growth"]
    assert "CURRENCY_UNPROVEN_OPERATING_MARGIN" in flags


def test_known_krw_source_zero_and_legacy_no_sidecar_behavior_are_preserved_without_trust_claim():
    metrics, proof = normalize({"profit_loss": 0, "equity": 100}, {"profit_loss": "KRW", "equity": "KRW"})
    ratios, _, flags = calculate_ratios({"2025": metrics}, currency_provenance={"2025": proof})
    assert ratios["roe"]["value"] == 0 and "CURRENCY_UNPROVEN_ROE" not in flags
    legacy = {"profit_loss": MetricValue(10, "2025", "20260301000001", "p", "p"),
              "equity": MetricValue(100, "2025", "20260301000001", "e", "e")}
    legacy_ratios, _, legacy_flags = calculate_ratios({"2025": legacy})
    assert legacy_ratios["roe"]["value"] == 10
    assert "CURRENCY_UNPROVEN_LEGACY" in legacy_flags


def test_sidecar_follows_same_filing_first_winner_without_metric_field_addition():
    for first, second in (("KRW", None), (None, "KRW")):
        rows = [dict(account_id="ifrs-full_Equity", thstrm_amount=str(value),
            rcept_no="20250301000001", currency=currency, sj_div="BS")
            for value, currency in ((100, first), (200, second))]
        proof = {}
        metrics = standardize_year_rows(rows, "2024", currency_provenance=proof)
        assert metrics["equity"].value == 100
        assert proof["equity"] is (first is not None)


def test_actual_report_response_and_api_json_never_expose_internal_currency_sidecar():
    import ast
    from datetime import datetime, timezone
    import json
    from pathlib import Path
    from uuid import UUID
    from src.agents.fundamental.domain.contracts import FundamentalRequest, FundamentalResponse
    from src.agents.fundamental.api.payload import build_erd_payload
    from src.agents.fundamental.api.reporting.formatting import attach_display_fields
    from src.agents.fundamental.api.rendering.html_builder import build_report_html
    metrics, proof = normalize({"profit_loss": 10, "equity": 100, "revenue": 100}, {"equity": "KRW"})
    provenance = {"2025": proof}
    ratios, evidence, flags = calculate_ratios({"2025": metrics}, currency_provenance=provenance)
    trend = build_trend({"2025": metrics}, currency_provenance=provenance)
    request = FundamentalRequest(request_id="synthetic", trace_id="synthetic", ticker="005930", years=1)
    state = dict(request=request, yearly_metrics={"2025": metrics}, metric_currency_provenance=provenance,
        corp_name="합성 기업", corp_code="synthetic", years=["2025"], fs_div="CFS", reprt_code="11011",
        reprt_name="사업보고서", report_mode="annual", ratios=ratios, evidence=evidence, trend=trend,
        risk_flags=flags, llm_provider="template", llm_model="rule-based", llm_latency_ms=0, dart_calls=0,
        verdict="자료 제한", confidence=0.3, score=0, label="insufficient_data", score_breakdown={},
        interpretation="원문 통화 미확인")
    path = Path(__file__).resolve().parents[2] / 'src/agents/fundamental/application/nodes/report_node.py'
    functions = [n for n in ast.parse(path.read_text(encoding='utf8')).body if isinstance(n, ast.FunctionDef)]
    history = []
    namespace = dict(Any=object, FundamentalAgentState=dict, FundamentalResponse=FundamentalResponse,
        datetime=datetime, timezone=timezone, build_erd_payload=build_erd_payload,
        attach_display_fields=attach_display_fields, build_report_html=build_report_html,
        append_history=history.append, recent_stats=lambda:{})
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), 'exec'), namespace)
    # 실제 verify 함수의 template 경로도 실행하여 미입증이 verified로 승격되지 않게 한다.
    from types import SimpleNamespace as NS
    from src.agents.fundamental.domain.verification.consistency import is_consistency_flag
    verify_path = path.with_name('verify_node.py')
    verify_function = next(n for n in ast.parse(verify_path.read_text(encoding='utf8')).body
                           if isinstance(n, ast.AsyncFunctionDef) and n.name == 'verify_node')
    verify_namespace = dict(Any=object, FundamentalAgentState=dict, EVIDENCE_UNBOUND_FLAG='EVIDENCE_UNBOUND_EXCLUDED',
        is_consistency_flag=is_consistency_flag,
        assess_verdict_stability=lambda *a:NS(verdict_stable=True, outcome='stable', reasons=[]),
        confidence_from=lambda *a:0.3, record_decision=lambda existing, **kw:list(existing or []))
    exec(compile(ast.Module(body=[verify_function], type_ignores=[]), str(verify_path), 'exec'), verify_namespace)
    coroutine = verify_namespace['verify_node'](state)
    try:
        coroutine.send(None)
    except StopIteration as finished:
        verified = finished.value
    finally:
        coroutine.close()
    assert verified['verification_summary']['consistency_passed'] is False
    assert any('통화' in reason for reason in verified['verification_summary']['reasons'])
    state.update(verified)
    response = namespace['report_node'](state)['response']
    # 실제 API execution.py와 같은 FundamentalResponse.model_dump(mode='json') 반환 경로.
    wire = response.model_dump(mode='json')
    json.dumps(wire, ensure_ascii=False, allow_nan=False)
    UUID(wire['meta']['erd_payload']['fundamental_report']['id'])
    # 읽기 전용 실제 Backend 미러 Pydantic 계약도 검증한다. DB/서비스는 import하지 않는다.
    import runpy
    mirror_path = Path(__file__).resolve().parents[3] / 'backend/src/modules/fundamental/domain/ai_output.py'
    mirror = runpy.run_path(str(mirror_path))['FundamentalAgentOutputMirror'].model_validate(wire)
    assert mirror.meta.erd_payload.report_verification['consistency_passed'] is False
    assert set(wire) == set(FundamentalResponse.model_fields)
    def keys(value):
        if isinstance(value, dict):
            return set(value).union(*(keys(v) for v in value.values()))
        if isinstance(value, list):
            return set().union(*(keys(v) for v in value))
        return set()
    assert not {'metric_currency_provenance', 'currency_provenance', 'currency_source_known'} & keys(wire)
    assert not {'yearly_metrics', 'MetricValue'} & keys(wire)
    assert wire['ratios']['roe']['status'] == 'unavailable'
    assert wire['trend']['revenue'] == [None]
    assert wire['meta']['erd_payload']['report_verification']['consistency_passed'] is False
    assert '검증됨' not in wire['report_html']
    assert len(history) == 1


def test_partial_or_non_boolean_sidecar_does_not_establish_known_source_currency():
    metrics, _ = normalize({"profit_loss": 10, "equity": 100}, {"profit_loss": "KRW", "equity": "KRW"})
    for proof in ({}, {"profit_loss": True}, {"profit_loss": 1, "equity": True}):
        ratios, _, flags = calculate_ratios({"2025": metrics}, currency_provenance={"2025": proof})
        assert ratios["roe"]["value"] is None
        assert "CURRENCY_UNPROVEN_ROE" in flags


def test_balance_identity_never_adds_unproven_or_explicit_mixed_currency_amounts():
    from src.agents.fundamental.domain.verification.consistency import validate_balance_identity, is_consistency_flag
    assets = MetricValue(100000000, "2025", "20260301000001", "a", "a", currency="KRW")
    equity = MetricValue(4000000, "2025", "20260301000001", "e", "e", currency="KRW")
    liabilities = MetricValue(6000000, "2025", "20260301000001", "l", "l", currency="KRW")
    data = {"2025": {"assets": assets, "equity": equity, "liabilities": liabilities}}
    proof = {"2025": {"assets": False, "equity": True, "liabilities": True}}
    flags = validate_balance_identity(data, currency_provenance=proof)
    assert flags == ["CURRENCY_UNPROVEN_BALANCE_2025"]
    assert is_consistency_flag(flags[0])
    assets.currency = "USD"
    proof["2025"]["assets"] = True
    flags = validate_balance_identity(data, currency_provenance=proof)
    assert flags == ["CURRENCY_MISMATCH_BALANCE_2025"]
    assert is_consistency_flag(flags[0])
    assets.currency = "KRW"
    assert validate_balance_identity(data, currency_provenance=proof) == ["VERIFY_BALANCE_IDENTITY_FAILED_2025"]
