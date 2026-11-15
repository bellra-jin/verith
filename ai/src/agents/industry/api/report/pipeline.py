"""Pure presentation of the observed pipeline for the same final result."""
from __future__ import annotations

from typing import Any

from ...domain.answer_verification import bound_verification


def _pipeline_steps(final_state: dict[str, Any]) -> list[dict[str, str]]:
    used_vector = bool(final_state.get("chunks"))
    used_cypher = bool(final_state.get("cypher"))
    verification = bound_verification(final_state)
    checked = verification is not None and verification.outcome == "checked"
    verification_label = ("검사 완료" if checked else
                          "미실행" if verification and verification.outcome == "not_run" else
                          "판정 불가" if verification else "실행 미확인")
    return [
        {
            "id": "classify",
            "title": "Question classification",
            "status": "done",
            "statusText": "Implemented",
            "body": f"Classified as {final_state.get('label') or 'unknown'}.",
        },
        {
            "id": "cypher",
            "title": "Cypher generation and execution",
            "status": "done" if used_cypher else "skipped",
            "statusText": "Implemented" if used_cypher else "Skipped",
            "body": "Generated and executed a schema-constrained Cypher query.",
        },
        {
            "id": "vector",
            "title": "Vector fallback",
            "status": "done" if used_vector else "skipped",
            "statusText": "Implemented" if used_vector else "Skipped",
            "body": "Retrieved source chunks for qualitative or fallback grounding.",
        },
        {
            "id": "faithfulness",
            "title": "Faithfulness gate",
            "status": "done" if checked else "skipped",
            "statusText": verification_label,
            "body": ("Completed the sentence-evidence check; this does not prove all facts."
                     if checked else "No completed check is established for this answer and evidence."),
        },
    ]
