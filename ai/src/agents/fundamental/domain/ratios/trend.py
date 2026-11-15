from typing import Any

from ..normalization.standardize import MetricValue, currency_unproven
from .calculators import _safe_ratio


def trend_currency_mismatches(yearly_metrics: dict[str, dict[str, MetricValue]], *, currency_provenance=None) -> list[str]:
    mismatches = []
    for metric in ("revenue", "operating_income"):
        currencies = {rows[metric].currency for year, rows in yearly_metrics.items()
                      if rows.get(metric) and not currency_unproven(currency_provenance, year, metric)}
        if len(currencies) > 1:
            mismatches.append(metric)
    if any(rows.get("profit_loss") and rows.get("equity")
           and not currency_unproven(currency_provenance, year, "profit_loss")
           and not currency_unproven(currency_provenance, year, "equity")
           and rows["profit_loss"].currency != rows["equity"].currency for year, rows in yearly_metrics.items()):
        mismatches.append("roe")
    return mismatches


def trend_non_krw_money(yearly_metrics: dict[str, dict[str, MetricValue]], *, currency_provenance=None) -> list[str]:
    # 기존 금액 추세의 표시/저장 unit은 원화 고정이므로 단일연도도 같은 경계를 적용한다.
    return [metric for metric in ("revenue", "operating_income")
            if any(rows.get(metric) and not currency_unproven(currency_provenance, year, metric)
                   and rows[metric].currency not in {"KRW", "원"} for year, rows in yearly_metrics.items())]


def trend_unproven_currency(yearly_metrics, *, currency_provenance=None):
    limited = [key for key in ("revenue", "operating_income")
        if any(rows.get(key) and currency_unproven(currency_provenance, year, key) for year, rows in yearly_metrics.items())]
    if any(rows.get("profit_loss") and rows.get("equity")
           and any(currency_unproven(currency_provenance, year, key) for key in ("profit_loss", "equity"))
           for year, rows in yearly_metrics.items()):
        limited.append("roe")
    return limited


def build_trend(yearly_metrics: dict[str, dict[str, MetricValue]], *, currency_provenance=None) -> dict[str, Any]:
    years = sorted(yearly_metrics)
    revenue: list[float | None] = []
    operating_income: list[float | None] = []
    roe: list[float | None] = []
    for year in years:
        metrics = yearly_metrics[year]
        rev = metrics.get("revenue")
        op = metrics.get("operating_income")
        profit = metrics.get("profit_loss")
        equity = metrics.get("equity")
        revenue.append(rev.value if rev else None)
        operating_income.append(op.value if op else None)
        roe_value = (_safe_ratio(profit.value, equity.value)
                     if profit and equity and profit.currency == equity.currency
                     and not currency_unproven(currency_provenance, year, "profit_loss")
                     and not currency_unproven(currency_provenance, year, "equity") else None)
        roe.append(round(roe_value, 2) if roe_value is not None else None)
    # 통화 없는 기존 금액 series에는 서로 다른 통화를 같은 단위처럼 나열하지 않는다.
    mismatches = (trend_currency_mismatches(yearly_metrics, currency_provenance=currency_provenance)
                  + trend_non_krw_money(yearly_metrics, currency_provenance=currency_provenance)
                  + trend_unproven_currency(yearly_metrics, currency_provenance=currency_provenance))
    if "revenue" in mismatches:
        revenue = [None] * len(years)
    if "operating_income" in mismatches:
        operating_income = [None] * len(years)
    return {"years": years, "revenue": revenue, "op_income": operating_income, "roe": roe}
