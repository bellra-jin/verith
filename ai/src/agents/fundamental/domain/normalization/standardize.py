from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any

from .account_mapper import canonical_metric
from ..reporting.period import REPORT_SHORT_LABELS


@dataclass
class MetricValue:
    value: float
    fiscal_year: str
    rcept_no: str
    account_id: str
    account_nm: str
    sj_div: str = ""
    currency: str = "KRW"


def _parse_amount(value: Any) -> float | None:
    if value in (None, "", "-"):
        return None
    try:
        amount = float(str(value).replace(",", "").strip())
        return amount if isfinite(amount) else None
    except ValueError:
        return None


def _pick_latest(existing: MetricValue | None, candidate: MetricValue) -> MetricValue:
    if existing is None:
        return candidate
    return candidate if candidate.rcept_no > existing.rcept_no else existing


def currency_unproven(provenance, year: str, metric: str) -> bool:
    # sidecar 부재는 legacy 호환일 뿐 통화 검증 증거가 아니다.
    return provenance is not None and provenance.get(year, {}).get(metric) is not True


def standardize_year_rows(rows: list[dict[str, Any]], fiscal_year: str, *,
                          currency_provenance: dict[str, bool] | None = None,
                          reprt_code: str | None = None) -> dict[str, MetricValue]:
    metrics: dict[str, MetricValue] = {}
    # 기존 표시용 KRW fallback과 원천에 실제 통화가 있었는지를 분리한다.
    source_currencies: dict[str, str | None] = {}
    for row in rows:
        # bsns_year는 당기금액의 사업연도다. 전기/전전기 컬럼으로 옮겨 읽지 않는다.
        # 누락·비정형 연도는 기존 호환을 유지하며 검증된 기간으로 승격하지 않는다.
        source_year = str(row.get("bsns_year") or "").strip()
        if (len(source_year) == 4 and source_year.isascii() and source_year.isdecimal()
                and source_year != str(fiscal_year)):
            continue
        # thstrm_amount belongs to this row's report, not frmtrm/bfefrmtrm.
        # Reject only a recognized explicit period mismatch; absent/malformed
        # metadata remains legacy input, not proof of comparable periods.
        source_report = row.get("reprt_code")
        source_report = source_report.strip() if isinstance(source_report, str) else None
        if (reprt_code in REPORT_SHORT_LABELS and source_report in REPORT_SHORT_LABELS
                and source_report != reprt_code):
            continue
        canonical = canonical_metric(row)
        if canonical is None:
            continue
        amount = _parse_amount(row.get("thstrm_amount"))
        if amount is None:
            continue
        value = MetricValue(
            value=amount,
            fiscal_year=fiscal_year,
            rcept_no=str(row.get("rcept_no") or ""),
            account_id=str(row.get("account_id") or row.get("account_nm") or canonical),
            account_nm=str(row.get("account_nm") or canonical),
            sj_div=str(row.get("sj_div") or ""),
            currency=str(row.get("currency") or "KRW"),
        )
        selected = _pick_latest(metrics.get(canonical), value)
        metrics[canonical] = selected
        if selected is value:
            raw_currency = row.get("currency")
            source_currencies[canonical] = (raw_currency
                if isinstance(raw_currency, str) and raw_currency.strip() else None)
            if currency_provenance is not None:
                currency_provenance[canonical] = source_currencies[canonical] is not None
    if "liabilities" not in metrics and "equity_and_liabilities" in metrics and "equity" in metrics:
        base = metrics["equity_and_liabilities"]
        equity = metrics["equity"]
        # 서로 다른 공시·통화·재무표를 섞어 부채를 만들면 출처와 실제 수치가 어긋난다.
        if (len(base.rcept_no) != 14 or not base.rcept_no.isascii() or not base.rcept_no.isdecimal()
                or base.rcept_no != equity.rcept_no
                or source_currencies.get("equity_and_liabilities") is None
                or source_currencies.get("equity") is None
                or base.currency != equity.currency or base.sj_div != "BS" or equity.sj_div != "BS"):
            return metrics
        amount = base.value - equity.value
        if not isfinite(amount):
            return metrics
        metrics["liabilities"] = MetricValue(
            value=amount,
            fiscal_year=fiscal_year,
            rcept_no=base.rcept_no,
            account_id="derived:equity_and_liabilities_minus_equity",
            account_nm="부채총계(자본과부채총계-자본총계)",
            sj_div=base.sj_div or "BS",
            currency=base.currency,
        )
        if currency_provenance is not None:
            currency_provenance["liabilities"] = True
    return metrics
