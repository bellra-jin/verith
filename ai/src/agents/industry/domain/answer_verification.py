"""Internal, same-result verification binding; never a public trust/settlement token."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any


def answer_binding(question: str, answer: str, rows: list, chunks: list) -> str | None:
    try:
        data = json.dumps([question, answer, rows, chunks], sort_keys=True,
                          ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        return sha256(data.encode("utf-8")).hexdigest()
    except (TypeError, ValueError, OverflowError):
        return None  # Unsupported/non-finite source data cannot establish this binding.


@dataclass(frozen=True)
class AnswerVerification:
    binding: str | None
    outcome: str  # checked / not_run / indeterminate
    unsupported: tuple[str, ...] = ()


def bound_verification(state: dict[str, Any]) -> AnswerVerification | None:
    record = state.get("answer_verification")
    if type(record) is not AnswerVerification or not record.binding:
        return None
    if record.outcome not in {"checked", "not_run", "indeterminate"}:
        return None
    binding = answer_binding(state.get("question") or "", state.get("answer") or "",
                             state.get("rows") or [], state.get("chunks") or [])
    return record if binding == record.binding else None
