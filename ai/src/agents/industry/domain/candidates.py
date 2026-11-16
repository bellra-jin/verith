"""Pure normalization of new LLM candidates with explicit verification outcomes."""
from __future__ import annotations

from copy import deepcopy

from .schema import REL_SHAPES
from .triples import Triple


def normalize_candidates(raw, *, by_stock_code, is_self_reference, normalize_name,
                         load_source, verify):
    triples, rejects, quarantine, observations = [], [], [], []
    skipped = 0
    for row in raw:
        origin = row.get("origin", "")
        filer = by_stock_code(origin)
        filer_name = filer.canonical if filer else ""
        def resolve(name, typ):
            if typ == "Company" and filer_name and is_self_reference(name):
                return filer_name
            return normalize_name(name, typ)
        source = resolve(row["source"], row["source_type"])
        target = resolve(row["target"], row["target_type"])
        if not source or not target or source == target:
            continue
        if (row["source_type"], row["type"], row["target_type"]) not in REL_SHAPES:
            skipped += 1
            continue
        evidence = str(row.get("evidence") or "").strip()
        status, reason, kept, score = "not_run", "no_quote", set(), None
        if evidence:
            try:
                source_text = load_source(origin)
                if not source_text:
                    reason = "source_unavailable"
                else:
                    verdict = verify(evidence, source_text)
                    if (not isinstance(verdict, tuple) or len(verdict) != 2
                            or type(verdict[0]) is not bool):
                        status, reason = "indeterminate", "invalid_verifier_result"
                    else:
                        ok, score = verdict
                        if ok is True:
                            status, reason, kept = "supported", "quote_matched", {evidence}
                        else:
                            status, reason = "rejected", "quote_rejected"
            except Exception as exc:
                status, reason = "indeterminate", type(exc).__name__
        observation = dict(source=source, relation=row["type"], target=target,
                           origin=origin, status=status, reason=reason)
        observations.append(observation)
        if status == "rejected":
            rejects.append(dict(source=source, relation=row["type"], target=target,
                                origin=origin, score=score, evidence=evidence))
            continue
        if status != "supported":
            # Preserve raw and normalized observations without exporting an uncertain fact.
            quarantine.append(dict(candidate=deepcopy(row), observation=dict(observation)))
            continue
        triples.append(Triple(source, row["source_type"], row["type"], target,
                              row["target_type"], {origin}, kept))
    return triples, rejects, quarantine, observations, skipped
