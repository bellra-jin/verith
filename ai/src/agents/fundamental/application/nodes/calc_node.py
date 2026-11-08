from __future__ import annotations

from typing import Any

from ...domain.ratios.calculators import calculate_ratios
from ...domain.ratios.scorer import score_financials
from ...domain.ratios.trend import build_trend
from ...domain.reporting.period import period_labels
from ...domain.verification.binding import check_evidence_binding
from ...domain.verification.consistency import validate_balance_identity, validate_eps_consistency
from ..state import FundamentalAgentState, extend_unique


def calc_node(state: FundamentalAgentState) -> dict[str, Any]:
    risk_flags = list(state.get("risk_flags", []))
    yearly_metrics = state["yearly_metrics"]

    ratios, evidence, ratio_flags = calculate_ratios(yearly_metrics, share_count=state.get("share_count"))
    extend_unique(risk_flags, ratio_flags)

    evidence, binding_flags = check_evidence_binding(evidence)
    extend_unique(risk_flags, binding_flags)
    extend_unique(risk_flags, validate_balance_identity(yearly_metrics))
    eps_flags, consistency_notes = validate_eps_consistency(
        ratios,
        state.get("insights", {}),
        state.get("reprt_code", ""),
    )
    extend_unique(risk_flags, eps_flags)

    trend = build_trend(yearly_metrics)
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
