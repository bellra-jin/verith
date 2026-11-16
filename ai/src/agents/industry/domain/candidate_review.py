"""Caller-owned, nonpersistent review snapshots and log-safe aggregate summaries."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy


def build_candidate_review(observations: list[dict], quarantine: list[dict]) -> dict:
    statuses = ("supported", "rejected", "not_run", "indeterminate")
    counts = {status: sum(o.get("status") == status for o in observations) for status in statuses}
    reasons = Counter()
    known = {"no_quote", "source_unavailable", "invalid_verifier_result"}
    for item in quarantine:
        reason = item.get("observation", {}).get("reason")
        # Do not log origin/name/quote/context, arbitrary exception text or dynamic type names.
        reasons[reason if reason in known else "verification_error_or_unknown"] += 1
    return {
        "summary": {"retention": "process_memory_only", "statuses": counts,
                    "quarantined_count": len(quarantine), "quarantine_reasons": dict(reasons)},
        "quarantined_candidates": deepcopy(quarantine),
        "verification_observations": deepcopy(observations),
    }
