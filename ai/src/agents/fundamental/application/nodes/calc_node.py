from __future__ import annotations

from typing import Any

from ...domain.ratios.calculators import calculate_ratios
from ...domain.ratios.scorer import score_financials
from ...domain.ratios.trend import build_trend, trend_currency_mismatches, trend_non_krw_money, trend_unproven_currency
from ...domain.reporting.period import period_labels
from ...domain.verification.binding import check_evidence_binding
from ...domain.verification.consistency import validate_balance_identity, validate_eps_consistency
from ..state import FundamentalAgentState, extend_unique


def calc_node(state: FundamentalAgentState) -> dict[str, Any]:
    risk_flags = list(state.get("risk_flags", []))
    yearly_metrics = state["yearly_metrics"]
    currency_provenance = state.get("metric_currency_provenance")

    ratios, evidence, ratio_flags = calculate_ratios(yearly_metrics, share_count=state.get("share_count"), currency_provenance=currency_provenance)
    extend_unique(risk_flags, ratio_flags)

    evidence, binding_flags = check_evidence_binding(evidence)
    extend_unique(risk_flags, binding_flags)
    extend_unique(risk_flags, validate_balance_identity(yearly_metrics, currency_provenance=currency_provenance))
    eps_flags, consistency_notes = validate_eps_consistency(
        ratios,
        state.get("insights", {}),
        state.get("reprt_code", ""),
    )
    extend_unique(risk_flags, eps_flags)

    trend = build_trend(yearly_metrics, currency_provenance=currency_provenance)
    extend_unique(risk_flags, [f"TREND_CURRENCY_MISMATCH_{name.upper()}"
                               for name in trend_currency_mismatches(yearly_metrics, currency_provenance=currency_provenance)])
    extend_unique(risk_flags, [f"TREND_UNIT_UNSUPPORTED_{name.upper()}"
                               for name in trend_non_krw_money(yearly_metrics, currency_provenance=currency_provenance)])
    extend_unique(risk_flags, [f"TREND_CURRENCY_UNPROVEN_{name.upper()}"
                               for name in trend_unproven_currency(yearly_metrics, currency_provenance=currency_provenance)])
    trend["period_labels"] = period_labels(trend.get("years", []), state.get("reprt_code"))
    score, score_breakdown, label = score_financials(ratios)

    return {
        "ratios": ratios,
        "evidence": evidence,
        "risk_flags": risk_flags,
        "consistency_notes": consistency_notes,
        "trend": trend,
        "score": score,
        "score_breakdown": score_breakdown,
        "label": label,
    }
