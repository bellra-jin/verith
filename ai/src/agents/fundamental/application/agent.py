from __future__ import annotations

import asyncio
from typing import Any

from ..infrastructure.llm.usage import capture_usage
from ..domain.contracts import FundamentalAgentInput, FundamentalRequest, FundamentalResponse
from .query_interpreter import to_fundamental_request
from .nodes.workflow import build_fundamental_workflow


_WORKFLOW = build_fundamental_workflow()


async def _run_workflow(initial, call_usage_records):
    records = [] if call_usage_records is None else call_usage_records
    with capture_usage(records):
        try:
            state = await _WORKFLOW.ainvoke(initial)
        except (asyncio.CancelledError, Exception) as exc:
            # 노드 반환이 없어도 실행 호출자가 메모리 증거를 회수할 수 있게 한다. 영속 ACK는 아니다.
            exc.fundamental_call_usage_records = tuple(dict(row) for row in records)
            raise
    return state["response"]


async def analyze_fundamental(
    request: FundamentalRequest, *, use_cache: bool = True,
    call_usage_records: list[dict[str, Any]] | None = None,
) -> FundamentalResponse:
    return await _run_workflow({"request": request, "use_cache": use_cache}, call_usage_records)


async def analyze_fundamental_public(
    public_input: FundamentalAgentInput,
    *,
    use_cache: bool = True,
    call_usage_records: list[dict[str, Any]] | None = None,
) -> FundamentalResponse:
    request, interpretation = to_fundamental_request(public_input)
    return await _run_workflow(
        {
            "request": request,
            "use_cache": use_cache,
            "input_interpretation": interpretation.model_dump(),
        },
        call_usage_records,
    )
