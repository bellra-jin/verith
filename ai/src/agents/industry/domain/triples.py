"""Candidate triple value and deterministic merge; no source or graph I/O."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Triple:
    source: str
    source_type: str
    relation: str
    target: str
    target_type: str
    origins: set[str] = field(default_factory=set)
    evidences: set[str] = field(default_factory=set)
    qota_rt: str = ""  # OWNS_STAKE 지분율(%), backbone edges only


SYMMETRIC_RELATIONS = {"COMPETES_WITH"}


def merge_triples(triples: list[Triple]) -> list[Triple]:
    """Dedupe on (source, relation, target); union origins, keep first 지분율.

    Symmetric relations (COMPETES_WITH) are order-normalized so both directions
    collapse to one edge.
    """
    merged: dict[tuple[str, str, str], Triple] = {}
    for t in triples:
        if t.relation in SYMMETRIC_RELATIONS and t.source > t.target:
            t = Triple(t.target, t.target_type, t.relation, t.source, t.source_type,
                       set(t.origins), set(t.evidences), t.qota_rt)
        key = (t.source, t.relation, t.target)
        if key in merged:
            merged[key].origins |= t.origins
            merged[key].evidences |= t.evidences
            if not merged[key].qota_rt and t.qota_rt:
                merged[key].qota_rt = t.qota_rt
        else:
            merged[key] = Triple(t.source, t.source_type, t.relation, t.target,
                                 t.target_type, set(t.origins), set(t.evidences), t.qota_rt)
    return list(merged.values())
