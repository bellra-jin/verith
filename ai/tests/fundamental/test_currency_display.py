from src.agents.fundamental.domain.normalization.standardize import MetricValue
from src.agents.fundamental.domain.ratios.calculators import calculate_ratios
from src.agents.fundamental.domain.ratios.trend import build_trend, trend_non_krw_money
from src.agents.fundamental.infrastructure.data.regular_disclosure import ShareCountData
from src.agents.fundamental.api.reporting.formatting import attach_display_fields
from src.agents.fundamental.api.payload import build_erd_payload
from src.agents.fundamental.api.rendering.html_builder import _trend_rows, FLAG_DESCRIPTIONS


def metric(value, currency):
    return MetricValue(value=value, fiscal_year="2025", rcept_no="20260301000001",
        account_id="synthetic", account_nm="합성 계정", sj_div="BS", currency=currency)


def test_single_year_usd_money_trend_is_not_mislabeled_as_won():
    data = {"2025": {"revenue": metric(123, "USD"), "operating_income": metric(12, "USD"),
                     "profit_loss": metric(10, "USD"), "equity": metric(100, "USD")}}
    trend = build_trend(data)
    assert trend["years"] == ["2025"]
    assert trend["revenue"] == [None] and trend["op_income"] == [None]
    assert trend["roe"] == [10]
    assert trend_non_krw_money(data) == ["revenue", "operating_income"]
    attach_display_fields({}, trend, [])
    assert trend["display"]["revenue"] == ["산출 불가"]
    html = _trend_rows(trend)
    assert "123원" not in html and "12원" not in html
    assert "산출 불가" in html and "10%" in html


def test_single_year_krw_money_keeps_zero_negative_and_year_axis():
    data = {"2025": {"revenue": metric(0, "KRW"), "operating_income": metric(-12, "KRW")}}
    trend = build_trend(data)
    assert trend["years"] == ["2025"]
    assert trend["revenue"] == [0] and trend["op_income"] == [-12]
    assert trend_non_krw_money(data) == []
    attach_display_fields({}, trend, [])
    assert trend["display"]["revenue"] == ["0원"]
    assert trend["display"]["op_income"] == ["-12원"]


def test_explicit_non_krw_eps_bps_are_unavailable_not_false_won_values():
    shares = ShareCountData(issued_shares=100, distributed_shares=None, treasury_shares=None,
        share_class="보통주", basis="common_issued_shares", rcept_no="20260301000002", stlm_dt="2025-12-31")
    for currency in ("USD", "EUR"):
        ratios, evidence, flags = calculate_ratios({"2025": {
            "equity": metric(100, currency), "basic_eps": metric(2, currency)}}, share_count=shares)
        attach_display_fields(ratios, {}, evidence)
        for name in ("eps", "bps"):
            assert ratios[name]["value"] is None and ratios[name]["status"] == "unavailable"
            assert ratios[name]["display_value"] == "산출 불가"
            assert "원화가 아니어서" in ratios[name]["reason"]
            assert "CURRENCY_UNIT_UNSUPPORTED_" + name.upper() in flags
            assert not any(e.metric == name for e in evidence)


def test_masked_trend_existing_payload_has_no_available_false_won_rows():
    for data in ({"2025": {"revenue": metric(123, "USD")}},
                 {"2024": {"revenue": metric(123, "USD")}, "2025": {"revenue": metric(456, "KRW")}}):
        trend = build_trend(data)
        payload = build_erd_payload(request_id="synthetic", trace_id="synthetic", ticker="005930",
            corp_name="합성 기업", corp_code="synthetic", bsns_year=2025, fs_div="CFS", reprt_code="11011",
            verdict="limited", confidence=0.3, score=0, label="insufficient_data", ratios={}, evidence=[],
            trend=trend, interpretation="단위 미확인", interpretation_source="template",
            risk_flags=["TREND_UNIT_UNSUPPORTED_REVENUE"], verification={}, retrieval_summary={})
        assert not any(r["ratio_name"] in ("revenue", "op_income") for r in payload["report_ratios"])
        assert trend["years"] == sorted(data)
        assert len(trend["revenue"]) == len(data)


def test_currency_limit_flags_have_human_readable_ai_display_reasons():
    for flag in ("CURRENCY_MISMATCH_REVENUE_GROWTH", "CURRENCY_MISMATCH_OPERATING_INCOME_GROWTH",
                 "TREND_CURRENCY_MISMATCH_REVENUE", "TREND_UNIT_UNSUPPORTED_REVENUE",
                 "CURRENCY_UNIT_UNSUPPORTED_EPS", "CURRENCY_UNIT_UNSUPPORTED_BPS"):
        assert flag in FLAG_DESCRIPTIONS
        assert FLAG_DESCRIPTIONS[flag] != flag


def test_full_ai_html_non_krw_money_has_no_false_won_amount_and_explains_unit_limit():
    from src.agents.fundamental.api.rendering.html_builder import build_report_html
    trend = build_trend({"2025": {"revenue": metric(123, "USD"), "operating_income": metric(12, "USD")}})
    attach_display_fields({}, trend, [])
    html = build_report_html(corp_name="합성 기업", ticker="005930", score=0,
        label="insufficient_data", confidence=0.3, ratios={}, trend=trend,
        interpretation="통화 단위 제한", evidence=[], risk_flags=["TREND_UNIT_UNSUPPORTED_REVENUE"])
    assert "123원" not in html and "12원" not in html
    assert "원화 단위가 확인되지 않은 금액 추세 표시를 보류" in html
    assert "산출 불가" in html
