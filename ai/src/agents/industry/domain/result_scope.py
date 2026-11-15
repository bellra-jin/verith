"""Bound retained AI rows, never claim DB materialization/time/cost bounds."""
from __future__ import annotations

from copy import deepcopy
from itertools import islice

# Existing answer-context policy, shared with state/evidence/export consumers.
MAX_CONTEXT_ROWS = 50


def limit_query_rows(rows, limit: int = MAX_CONTEXT_ROWS) -> tuple[list[dict], bool]:
    if type(limit) is not int or not 1 <= limit <= MAX_CONTEXT_ROWS:
        raise ValueError("Invalid retained query-row limit")
    try:
        sample = list(islice(iter(rows), limit + 1))
        if any(not isinstance(row, dict) for row in sample):
            raise TypeError()
        retained = deepcopy(sample[:limit])
    except Exception:
        raise ValueError("Unsupported query-result row shape") from None
    return retained, len(sample) > limit


def row_scope_notice(truncated: bool) -> str:
    if truncated is not True:
        return ""
    return (f"조회 범위 제한: AI는 반환된 결과의 앞 {MAX_CONTEXT_ROWS}행만 보관·분석했습니다. "
            "전체 관계·기업을 빠짐없이 조사했다는 뜻이 아니며, DB 조회 시간·원천 결과량·비용의 상한도 아닙니다.")
