from src.agents.fundamental.domain.normalization.standardize import MetricValue
from src.agents.fundamental.domain.ratios.calculators import calculate_ratios


PAIRS = {
    "roe": ("profit_loss", "equity"),
    "operating_margin": ("operating_income", "revenue"),
    "net_margin": ("profit_loss", "revenue"),
    "debt_ratio": ("liabilities", "equity"),
    "current_ratio": ("current_assets", "current_liabilities"),
}


def metric(value, currency):
    return MetricValue(value=value, fiscal_year="2025", rcept_no="20260301000001",
        account_id="synthetic", account_nm="합성 계정", sj_div="BS", currency=currency)


def test_explicit_mixed_currency_ratios_are_unavailable_not_false_percentages():
    for name, (numerator, denominator) in PAIRS.items():
        ratios, evidence, flags = calculate_ratios({"2025": {
            numerator: metric(10, "USD"), denominator: metric(100, "KRW")}})
        item = ratios[name]
        assert item["value"] is None
        assert item["status"] == "unavailable"
        assert "통화가 달라" in item["reason"]
        assert "CURRENCY_MISMATCH_" + name.upper() in flags
        assert "MISSING_" + name.upper() not in flags
        assert not any(e.metric == name for e in evidence)


def test_same_currency_percentages_preserve_values_zero_and_negative():
    for name, (numerator, denominator) in PAIRS.items():
        for currency in ("KRW", "USD"):
            for value in (10, 0, -10):
                ratios, evidence, flags = calculate_ratios({"2025": {
                    numerator: metric(value, currency), denominator: metric(100, currency)}})
                assert ratios[name]["value"] == value
                assert ratios[name]["status"] == "available"
                assert "CURRENCY_MISMATCH_" + name.upper() not in flags
                assert next(e for e in evidence if e.metric == name).value == value


def test_currency_mismatch_does_not_hide_independent_valid_ratio():
    ratios, evidence, flags = calculate_ratios({"2025": {
        "profit_loss": metric(10, "USD"), "equity": metric(100, "KRW"),
        "revenue": metric(100, "USD")}})
    assert ratios["roe"]["value"] is None
    assert ratios["net_margin"]["value"] == 10
    assert next(e for e in evidence if e.metric == "net_margin").accounts[0].currency == "USD"
    assert "CURRENCY_MISMATCH_ROE" in flags


def test_missing_account_retains_existing_missing_reason_not_currency_mismatch():
    ratios, _, flags = calculate_ratios({"2025": {"equity": metric(100, "USD")}})
    assert ratios["roe"]["status"] == "unavailable"
    assert "MISSING_ROE" in flags
    assert "CURRENCY_MISMATCH_ROE" not in flags


def test_growth_currency_mismatch_overrides_percent_turnaround_and_low_base_display():
    for key, name in (("revenue", "revenue_growth"), ("operating_income", "operating_income_growth")):
        for previous, current in ((100, 200), (100, 0), (-100, 200), (100, -50)):
            ratios, evidence, flags = calculate_ratios({
                "2024": {key: metric(previous, "USD")},
                "2025": {key: metric(current, "KRW")}})
            item = ratios[name]
            assert item["value"] is None
            assert item["status"] == "unavailable"
            assert "통화가 달라" in item["reason"]
            assert "direction" not in item and "display_value" not in item
            assert "CURRENCY_MISMATCH_" + name.upper() in flags
            assert not any(e.metric == name for e in evidence)


def test_same_currency_growth_keeps_computed_percent_and_evidence():
    for currency in ("USD", "KRW"):
        ratios, evidence, flags = calculate_ratios({
            "2024": {"revenue": metric(1000, currency), "operating_income": metric(100, currency)},
            "2025": {"revenue": metric(1500, currency), "operating_income": metric(150, currency)}})
        for name in ("revenue_growth", "operating_income_growth"):
            assert ratios[name]["value"] == 50
            assert ratios[name]["status"] == "available"
            assert next(e for e in evidence if e.metric == name).value == 50
            assert "CURRENCY_MISMATCH_" + name.upper() not in flags


def test_trend_masks_mixed_money_series_without_changing_source_or_years():
    from src.agents.fundamental.domain.ratios.trend import build_trend
    data = {"2024": {"revenue": metric(100, "USD"), "operating_income": metric(10, "USD")},
            "2025": {"revenue": metric(200, "KRW"), "operating_income": metric(20, "KRW")}}
    before = repr(data)
    trend = build_trend(data)
    assert trend["years"] == ["2024", "2025"]
    assert trend["revenue"] == [None, None]
    assert trend["op_income"] == [None, None]
    assert repr(data) == before


def test_trend_roe_rejects_only_the_year_with_mixed_account_currencies():
    from src.agents.fundamental.domain.ratios.trend import build_trend
    trend = build_trend({
        "2024": {"profit_loss": metric(10, "USD"), "equity": metric(100, "KRW")},
        "2025": {"profit_loss": metric(10, "USD"), "equity": metric(100, "USD")}})
    assert trend["roe"] == [None, 10]


def test_calc_node_propagates_currency_trend_limit_flags_with_existing_shape():
    import ast
    from pathlib import Path
    from src.agents.fundamental.domain.ratios.scorer import score_financials
    from src.agents.fundamental.domain.ratios.trend import build_trend, trend_currency_mismatches, trend_non_krw_money, trend_unproven_currency
    from src.agents.fundamental.domain.reporting.period import period_labels
    from src.agents.fundamental.domain.verification.binding import check_evidence_binding
    from src.agents.fundamental.domain.verification.consistency import validate_balance_identity, validate_eps_consistency
    from src.agents.fundamental.application.state import extend_unique
    path = Path(__file__).resolve().parents[2] / 'src/agents/fundamental/application/nodes/calc_node.py'
    function = next(n for n in ast.parse(path.read_text(encoding='utf8')).body
                    if isinstance(n, ast.FunctionDef) and n.name == 'calc_node')
    namespace = dict(Any=object, FundamentalAgentState=dict, calculate_ratios=calculate_ratios,
        score_financials=score_financials, build_trend=build_trend, trend_currency_mismatches=trend_currency_mismatches, trend_non_krw_money=trend_non_krw_money, trend_unproven_currency=trend_unproven_currency,
        period_labels=period_labels, check_evidence_binding=check_evidence_binding,
        validate_balance_identity=validate_balance_identity, validate_eps_consistency=validate_eps_consistency,
        extend_unique=extend_unique)
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), 'exec'), namespace)
    calc_node = namespace['calc_node']
    state = {"yearly_metrics": {
        "2024": {"revenue": metric(100, "USD")},
        "2025": {"revenue": metric(200, "KRW")}}, "reprt_code": "11011"}
    result = calc_node(state)
    assert "TREND_CURRENCY_MISMATCH_REVENUE" in result["risk_flags"]
    assert result["trend"]["revenue"] == [None, None]
    assert result["ratios"]["revenue_growth"]["status"] == "unavailable"
    state["metric_currency_provenance"] = {"2024": {"revenue": True}, "2025": {"revenue": False}}
    limited = calc_node(state)
    assert "CURRENCY_UNPROVEN_REVENUE_GROWTH" in limited["risk_flags"]
    assert "TREND_CURRENCY_UNPROVEN_REVENUE" in limited["risk_flags"]
    assert "TREND_CURRENCY_MISMATCH_REVENUE" not in limited["risk_flags"]


def test_operating_growth_skips_low_base_threshold_when_revenue_currency_differs():
    ratios, evidence, flags = calculate_ratios({
        "2024": {"operating_income": metric(100, "USD")},
        "2025": {"operating_income": metric(180, "USD"), "revenue": metric(100000, "KRW")}})
    item = ratios["operating_income_growth"]
    assert item["value"] == 80 and item["status"] == "available"
    assert "direction" not in item and "display_value" not in item
    assert "NOT_MEANINGFUL_OPERATING_INCOME_GROWTH" not in flags
    assert next(e for e in evidence if e.metric == "operating_income_growth").value == 80
    assert "CURRENCY_MISMATCH_OPERATING_MARGIN" in flags


def test_non_krw_operating_growth_does_not_use_won_absolute_threshold_without_positive_revenue():
    for revenue in (None, 0, -1):
        latest = {"operating_income": metric(180, "USD")}
        if revenue is not None:
            latest["revenue"] = metric(revenue, "USD")
        ratios, _, flags = calculate_ratios({"2024": {"operating_income": metric(100, "USD")}, "2025": latest})
        item = ratios["operating_income_growth"]
        assert item["value"] == 80 and item["status"] == "available"
        assert "direction" not in item
        assert "NOT_MEANINGFUL_OPERATING_INCOME_GROWTH" not in flags


def test_compatible_relative_and_won_absolute_low_base_policies_are_preserved():
    for currency, revenue in (("USD", 100000), ("KRW", None)):
        latest = {"operating_income": metric(180, currency)}
        if revenue is not None:
            latest["revenue"] = metric(revenue, currency)
        ratios, _, flags = calculate_ratios({"2024": {"operating_income": metric(100, currency)}, "2025": latest})
        item = ratios["operating_income_growth"]
        assert item["value"] is None and item["status"] == "not_meaningful"
        assert item["direction"] == "low_base"
        assert "NOT_MEANINGFUL_OPERATING_INCOME_GROWTH" in flags


def test_dimensionless_extreme_growth_policy_is_preserved_without_monetary_threshold():
    ratios, _, _ = calculate_ratios({"2024": {"operating_income": metric(100, "USD")},
                                    "2025": {"operating_income": metric(1000, "USD")}})
    assert ratios["operating_income_growth"]["value"] is None
    assert ratios["operating_income_growth"]["status"] == "not_meaningful"


def test_report_period_filtered_component_yields_unavailable_not_wrong_comparison():
    from src.agents.fundamental.domain.normalization.standardize import standardize_year_rows
    def source(account, amount, code):
        return dict(account_id=account, account_nm=account, thstrm_amount=str(amount),
                    reprt_code=code, bsns_year='2025', sj_div='IS', currency='KRW',
                    rcept_no='20260301000001')
    rows = [source('ifrs-full_Revenue', 100, '11011'),
            source('ifrs-full_ProfitLoss', 10, '11013')]
    metrics = standardize_year_rows(rows, '2025', reprt_code='11011')
    ratios, evidence, flags = calculate_ratios({'2025': metrics})
    assert metrics['revenue'].value == 100 and 'profit_loss' not in metrics
    assert ratios['net_margin']['value'] is None
    assert ratios['net_margin']['status'] == 'unavailable'
    assert 'MISSING_NET_MARGIN' in flags
    assert not any(item.metric == 'net_margin' for item in evidence)
