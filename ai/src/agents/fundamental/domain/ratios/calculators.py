from __future__ import annotations

from math import isfinite
from typing import Any

from ..contracts import Evidence, EvidenceAccount
from ...infrastructure.data.regular_disclosure import ShareCountData
from ..normalization.standardize import MetricValue, currency_unproven

RATIO_META = {
    "roe": {"label": "ROE", "category": "수익성", "unit": "%"},
    "operating_margin": {"label": "영업이익률", "category": "수익성", "unit": "%"},
    "net_margin": {"label": "순이익률", "category": "수익성", "unit": "%"},
    "debt_ratio": {"label": "부채비율", "category": "안정성", "unit": "%"},
    "current_ratio": {"label": "유동비율", "category": "안정성", "unit": "%"},
    "revenue_growth": {"label": "매출성장률", "category": "성장성", "unit": "%"},
    "operating_income_growth": {"label": "영업이익성장률", "category": "성장성", "unit": "%"},
    "eps": {"label": "EPS", "category": "밸류 기초", "unit": "원"},
    "bps": {"label": "BPS", "category": "밸류 기초", "unit": "원"},
}

MISSING_REASONS = {
    "roe": "당기순이익 또는 자본총계가 누락되었거나 자본총계가 0 이하라 ROE를 왜곡 없이 계산할 수 없습니다.",
    "operating_margin": "매출액 또는 영업이익 계정이 누락되어 영업이익률을 계산하지 않았습니다.",
    "net_margin": "매출액 또는 당기순이익 계정이 누락되어 순이익률을 계산하지 않았습니다.",
    "debt_ratio": "부채총계 또는 자본총계가 누락되었거나 자본총계가 0 이하라 부채비율을 계산하지 않았습니다.",
    "current_ratio": "유동자산 또는 유동부채 계정이 누락되어 유동비율을 계산하지 않았습니다.",
    "revenue_growth": "당기 또는 전기 매출액이 누락되었거나 전기 매출액이 0 이하라 성장률을 %로 산출하지 않았습니다.",
    "operating_income_growth": "전기 영업이익이 0 이하이거나 필수 계정이 누락되어 흑자전환/적자지속 가능성을 % 성장률로 강제 표현하지 않았습니다.",
    "eps": "DART 원문에서 보통주 기본 EPS 계정을 안정적으로 식별하지 못해 추정하지 않았습니다.",
    "bps": "자본총계·발행주식수 누락, 유효하지 않은 분모 또는 비유한 계산 결과로 BPS를 산출하지 않았습니다.",
}


def _safe_ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    if denominator < 0:
        return None
    return numerator / denominator * 100


def _book_value_per_share(equity: float | None, shares: ShareCountData | None) -> float | None:
    # 자본0은 알려진0이다. 분모 결측·비정상과 나눗셈 overflow만 미확인으로 남긴다.
    if equity is None or shares is None:
        return None
    issued = shares.issued_shares
    if not isfinite(equity) or not isfinite(issued) or issued <= 0:
        return None
    value = equity / issued
    return round(value, 2) if isfinite(value) else None


def _metric_value(metrics: dict[str, MetricValue], key: str) -> float | None:
    item = metrics.get(key)
    return item.value if item else None


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 2)


def yoy(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    if previous < 0:
        return None
    if current < 0:
        return None
    return round((current - previous) / abs(previous) * 100, 2)


LOW_BASE_DISPLAY = "흑자 기조 회복(저기저)"
LOW_BASE_ABSOLUTE_THRESHOLD = 1_000_000_000.0
LOW_BASE_REVENUE_RATIO = 0.01
EXTREME_GROWTH_PERCENT = 300.0


def _growth_status(current: float | None, previous: float | None) -> tuple[str, str | None, str | None]:
    if current is None or previous in (None, 0):
        return "unavailable", None, None
    if previous < 0:
        if current > 0:
            return "not_meaningful", "전기 적자에서 당기 흑자로 전환되어 성장률을 %로 표시하지 않습니다.", "turnaround_positive"
        return "not_meaningful", "전기 적자 또는 음수 기준이라 성장률을 %로 표시하지 않습니다.", "loss_continued"
    if current < 0:
        return "not_meaningful", "전기 흑자에서 당기 적자로 전환되어 성장률을 %로 표시하지 않습니다.", "turnaround_negative"
    return "available", None, None


def _is_low_base_operating_income(previous: float, current_revenue: float | None) -> bool:
    threshold = LOW_BASE_ABSOLUTE_THRESHOLD
    if current_revenue is not None and current_revenue > 0:
        threshold = abs(current_revenue) * LOW_BASE_REVENUE_RATIO
    return abs(previous) < threshold


def _operating_income_growth_status(
    current: float | None,
    previous: float | None,
    current_revenue: float | None,
    *, low_base_comparable: bool = True,
) -> tuple[str, str | None, str | None]:
    # 저기저 흑자 확대는 퍼센트가 과장되므로 display_value와 direction으로만 전달한다.
    status, reason, direction = _growth_status(current, previous)
    if status != "available" or current is None or previous is None:
        return status, reason, direction
    # 저기저라도 감소·보합은 회복이 아니다. 음의 성장률과 0을 원래대로 보존한다.
    if low_base_comparable and current > previous and _is_low_base_operating_income(previous, current_revenue):
        return (
            "not_meaningful",
            "전기 영업이익이 당기 매출 대비 1% 미만의 낮은 기저라 성장률을 %로 표시하지 않습니다.",
            "low_base",
        )
    growth = yoy(current, previous)
    if growth is not None and abs(growth) > EXTREME_GROWTH_PERCENT:
        return (
            "not_meaningful",
            "영업이익 성장률이 300%를 초과해 방향성으로만 설명합니다.",
            "low_base",
        )
    return status, reason, direction


def _source_url(rcept_no: str) -> str:
    return f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"


def _account_evidence(item: MetricValue | None, role: str) -> EvidenceAccount | None:
    if item is None:
        return None
    return EvidenceAccount(
        account_id=item.account_id,
        account_nm=item.account_nm,
        sj_div=item.sj_div,
        amount=item.value,
        currency=item.currency,
        role=role,
        fiscal_year=item.fiscal_year,
        rcept_no=item.rcept_no,
        source_url=_source_url(item.rcept_no),
    )


def _share_count_evidence(share_count: ShareCountData, fiscal_year: str) -> EvidenceAccount:
    return EvidenceAccount(
        account_id=f"{share_count.source_endpoint}:{share_count.source_field}",
        account_nm="발행주식수",
        sj_div="SHARES",
        amount=share_count.issued_shares,
        currency="shares",
        role="share_count",
        fiscal_year=fiscal_year,
        rcept_no=share_count.rcept_no,
        source_url=_source_url(share_count.rcept_no),
    )


def _compact_accounts(accounts: list[EvidenceAccount | None]) -> list[EvidenceAccount]:
    return [account for account in accounts if account is not None]


def calculate_ratios(
    yearly_metrics: dict[str, dict[str, MetricValue]],
    share_count: ShareCountData | None = None,
    *, currency_provenance: dict[str, dict[str, bool]] | None = None,
) -> tuple[dict[str, Any], list[Evidence], list[str]]:
    # 이 함수가 지표 값과 evidence의 단일 생성 지점이다. LLM 계층은 여기서 나온 값을 수정하지 않는다.
    years = sorted(yearly_metrics)
    latest_year = years[-1] if years else ""
    previous_year = years[-2] if len(years) >= 2 else None
    latest = yearly_metrics.get(latest_year, {})
    previous = yearly_metrics.get(previous_year, {}) if previous_year else {}
    risk_flags: list[str] = []
    if currency_provenance is None:
        risk_flags.append("CURRENCY_UNPROVEN_LEGACY")

    revenue = _metric_value(latest, "revenue")
    operating_income = _metric_value(latest, "operating_income")
    profit_loss = _metric_value(latest, "profit_loss")
    equity = _metric_value(latest, "equity")
    liabilities = _metric_value(latest, "liabilities")
    current_assets = _metric_value(latest, "current_assets")
    current_liabilities = _metric_value(latest, "current_liabilities")

    revenue_growth_status, revenue_growth_reason, revenue_growth_direction = _growth_status(revenue, _metric_value(previous, "revenue"))
    operating_metric = latest.get("operating_income")
    revenue_metric = latest.get("revenue")
    # 매출비례 임계값은 같은 통화일 때만, 매출 없는 절대 임계값은 원화일 때만 적용한다.
    low_base_comparable = bool(operating_metric and (
        operating_metric.currency == revenue_metric.currency if revenue_metric and revenue is not None and revenue > 0
        else operating_metric.currency in {"KRW", "원"}))
    low_base_comparable = low_base_comparable and not currency_unproven(currency_provenance, latest_year, "operating_income")
    if revenue is not None and revenue > 0:
        low_base_comparable = low_base_comparable and not currency_unproven(currency_provenance, latest_year, "revenue")
    operating_income_growth_status, operating_income_growth_reason, operating_income_growth_direction = _operating_income_growth_status(
        operating_income,
        _metric_value(previous, "operating_income"),
        revenue, low_base_comparable=low_base_comparable,
    )

    values = {
        "roe": _round(_safe_ratio(profit_loss, equity)),
        "operating_margin": _round(_safe_ratio(operating_income, revenue)),
        "net_margin": _round(_safe_ratio(profit_loss, revenue)),
        "debt_ratio": _round(_safe_ratio(liabilities, equity)),
        "current_ratio": _round(_safe_ratio(current_assets, current_liabilities)),
        "revenue_growth": yoy(revenue, _metric_value(previous, "revenue")),
        "operating_income_growth": (
            yoy(operating_income, _metric_value(previous, "operating_income"))
            if operating_income_growth_status == "available"
            else None
        ),
        "eps": _metric_value(latest, "basic_eps"),
        "bps": _book_value_per_share(equity, share_count),
    }
    # 환산 근거 없이 서로 다른 통화의 계정 금액을 나누지 않는다.
    currency_pairs = {
        "roe": ("profit_loss", "equity"), "operating_margin": ("operating_income", "revenue"),
        "net_margin": ("profit_loss", "revenue"), "debt_ratio": ("liabilities", "equity"),
        "current_ratio": ("current_assets", "current_liabilities"),
    }
    currency_mismatches = {name for name, (numerator, denominator) in currency_pairs.items()
        if latest.get(numerator) and latest.get(denominator)
        and latest[numerator].currency != latest[denominator].currency}
    growth_currency_mismatches = {name for name, metric in
        (("revenue_growth", "revenue"), ("operating_income_growth", "operating_income"))
        if latest.get(metric) and previous.get(metric)
        and latest[metric].currency != previous[metric].currency}
    currency_mismatches |= growth_currency_mismatches
    for name in currency_mismatches:
        values[name] = None

    # 기존 EPS/BPS 표시 계약은 원화다. 명시적 다른 통화를 원으로 오표시하지 않는다.
    unsupported_money_units = {name for name, metric in (("eps", "basic_eps"), ("bps", "equity"))
        if latest.get(metric) and latest[metric].currency not in {"KRW", "원"}}
    for name in unsupported_money_units:
        values[name] = None
    unproven_currency = {name for name, pair in currency_pairs.items()
        if any(latest.get(key) and currency_unproven(currency_provenance, latest_year, key) for key in pair)}
    unproven_currency |= {name for name, key in (("revenue_growth", "revenue"), ("operating_income_growth", "operating_income"))
        if (latest.get(key) and currency_unproven(currency_provenance, latest_year, key))
        or (previous.get(key) and currency_unproven(currency_provenance, previous_year, key))}
    unproven_currency |= {name for name, key in (("eps", "basic_eps"), ("bps", "equity"))
        if latest.get(key) and currency_unproven(currency_provenance, latest_year, key)}
    currency_mismatches -= unproven_currency
    unsupported_money_units -= unproven_currency
    for name in unproven_currency:
        values[name] = None
    status_overrides = {
        "revenue_growth": "unavailable" if "revenue_growth" in growth_currency_mismatches else revenue_growth_status,
        "operating_income_growth": "unavailable" if "operating_income_growth" in growth_currency_mismatches else operating_income_growth_status,
    }
    status_overrides.update({name: "unavailable" for name in unproven_currency})
    reason_overrides = {
        "revenue_growth": revenue_growth_reason,
        "operating_income_growth": operating_income_growth_reason,
    }
    reason_overrides.update({name: "계정에 기록된 통화가 달라 환산 근거 없이 비율을 계산하지 않았습니다."
                             for name in currency_mismatches})
    reason_overrides.update({name: "기록된 통화가 원화가 아니어서 원화 기준 지표를 표시하지 않았습니다."
                             for name in unsupported_money_units})
    reason_overrides.update({name: "원문 통화가 확인되지 않아 기본 KRW 값만으로 계산하거나 원화 표시하지 않았습니다."
                             for name in unproven_currency})
    direction_overrides = {
        "revenue_growth": revenue_growth_direction,
        "operating_income_growth": operating_income_growth_direction,
    }
    display_overrides = {
        "revenue_growth": (
            "흑자전환"
            if revenue_growth_direction == "turnaround_positive"
            else "적자전환"
            if revenue_growth_direction == "turnaround_negative"
            else None
        ),
        "operating_income_growth": (
            "흑자전환"
            if operating_income_growth_direction == "turnaround_positive"
            else "적자전환"
            if operating_income_growth_direction == "turnaround_negative"
            else LOW_BASE_DISPLAY
            if operating_income_growth_direction == "low_base"
            else None
        ),
    }
    for name in growth_currency_mismatches | unproven_currency:
        # 다른 통화의 원문금액으로 흑적자 전환/저기저 회복 방향도 단정하지 않는다.
        direction_overrides[name] = None
        display_overrides[name] = None
    if latest.get("liabilities") and latest["liabilities"].account_id.startswith("derived:"):
        risk_flags.append("DERIVED_LIABILITIES")

    evidence: list[Evidence] = []
    metric_sources: dict[str, tuple[tuple[str, str, str], ...]] = {
        "roe": (("profit_loss", "numerator", "latest"), ("equity", "denominator", "latest")),
        "operating_margin": (("operating_income", "numerator", "latest"), ("revenue", "denominator", "latest")),
        "net_margin": (("profit_loss", "numerator", "latest"), ("revenue", "denominator", "latest")),
        "debt_ratio": (("liabilities", "numerator", "latest"), ("equity", "denominator", "latest")),
        "current_ratio": (("current_assets", "numerator", "latest"), ("current_liabilities", "denominator", "latest")),
        "revenue_growth": (("revenue", "current", "latest"), ("revenue", "previous", "previous")),
        "operating_income_growth": (
            ("operating_income", "current", "latest"),
            ("operating_income", "previous", "previous"),
        ),
        "eps": (("basic_eps", "source_value", "latest"),),
        "bps": (("equity", "equity", "latest"),),
    }
    for metric, value in values.items():
        # not_meaningful은 결측이 아니라 표시 정책이다. 숫자 대신 방향성과 사유를 JSON에 남긴다.
        status = status_overrides.get(metric, "available" if value is not None else "unavailable")
        if value is None and status == "unavailable":
            prefix = ("CURRENCY_UNPROVEN" if metric in unproven_currency else
                      "CURRENCY_UNIT_UNSUPPORTED" if metric in unsupported_money_units else
                      "CURRENCY_MISMATCH" if metric in currency_mismatches else "MISSING")
            risk_flags.append(f"{prefix}_{metric.upper()}")
            continue
        if value is None and status == "not_meaningful":
            risk_flags.append(f"NOT_MEANINGFUL_{metric.upper()}")
            continue
        source_specs = metric_sources.get(metric)
        if source_specs is None:
            continue
        accounts = _compact_accounts(
            [
                _account_evidence(
                    latest.get(key) if period == "latest" else previous.get(key),
                    role,
                )
                for key, role, period in source_specs
            ]
        )
        if metric == "bps" and share_count is not None:
            accounts.append(_share_count_evidence(share_count, latest_year))
        if not accounts:
            continue
        primary = accounts[0]
        evidence.append(
            Evidence(
                claim=f"{metric} {value}",
                metric=metric,
                value=float(value),
                unit=RATIO_META[metric]["unit"],
                fiscal_year=latest_year,
                rcept_no=primary.rcept_no or "",
                account_ids=[account.account_id for account in accounts],
                accounts=accounts,
                source_url=primary.source_url or _source_url(primary.rcept_no or ""),
            )
        )

    ratios = {}
    for metric, value in values.items():
        meta = RATIO_META[metric]
        status = status_overrides.get(metric, "available" if value is not None else "unavailable")
        item = {
            "label": meta["label"],
            "category": meta["category"],
            "value": value,
            "unit": meta["unit"],
            "fiscal_year": latest_year,
            "status": status,
        }
        if value is None:
            item["reason"] = reason_overrides.get(metric) or MISSING_REASONS[metric]
        if display_overrides.get(metric):
            item["display_value"] = display_overrides[metric]
        if direction_overrides.get(metric):
            item["direction"] = direction_overrides[metric]
        if metric == "bps" and value is not None and share_count is not None:
            item["basis"] = share_count.basis
            item["share_class"] = share_count.share_class
            item["issued_shares"] = share_count.issued_shares
            item["distributed_shares"] = share_count.distributed_shares
            item["treasury_shares"] = share_count.treasury_shares
            item["source_endpoint"] = share_count.source_endpoint
            item["source_field"] = share_count.source_field
        ratios[metric] = item
    return ratios, evidence, risk_flags
