"""재무 AI의 관측 증거만 수집한다. 신뢰·완결성·정산 권한은 만들지 않는다."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import json
from typing import Any
from uuid import uuid4


_run_records: ContextVar[list[dict] | None] = ContextVar("fundamental_call_usage", default=None)


@contextmanager
def capture_usage(records):
    # LangGraph 하위 task도 같은 실행 collector를 상속한다. 종료/취소 뒤 다른 실행으로 새지 않는다.
    token = _run_records.set(records)
    try:
        yield records
    finally:
        _run_records.reset(token)


def retain_attempt(records, row):
    records.append(row)
    run_records = _run_records.get()
    if run_records is not None and run_records is not records:
        run_records.append(row)


def digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def new_attempt(*, provider, model, request, timeout, stage, kind, parent_call_id=None):
    # 비밀값·URL·원문은 보존하지 않는다. 요청/정책의 digest는 인증 증명이 아니다.
    return dict(call_id=str(uuid4()), parent_call_id=parent_call_id, stage=stage,
                attempt_kind=kind, provider=provider, model=model, service_tier=None, response_model=None,
                requested_service_tier=request.get("service_tier"),
                request_sha256=digest(request),
                policy_sha256=digest(dict(timeout_seconds=timeout,
                    max_tokens=request["max_tokens"], sdk_retry_policy="openai-default")),
                outcome="unknown", input_tokens=None, cached_tokens=None,
                output_tokens=None, total_tokens=None)


def observe_usage(row, usage):
    # 누락·0·잘못된 타입도 원값 그대로 둔다. Backend 검증을 대신하거나 합계를 추정하지 않는다.
    row.update(input_tokens=usage.get("prompt_tokens"),
               cached_tokens=usage.get("cached_tokens"),
               output_tokens=usage.get("completion_tokens"),
               total_tokens=usage.get("total_tokens"))


def transport_hooks(records, first):
    current = first
    sent = False

    async def on_request(request):
        nonlocal current, sent
        if sent:
            current = dict(first, call_id=str(uuid4()), parent_call_id=current["call_id"],
                           attempt_kind="sdk_retry", outcome="unknown", service_tier=None, response_model=None,
                           input_tokens=None, cached_tokens=None, output_tokens=None, total_tokens=None)
            retain_attempt(records, current)
        sent = True
        # 실제 SDK 전송 본문의 정규화 digest. 인증 헤더와 요청 본문은 기록하지 않는다.
        current["request_sha256"] = digest(json.loads(request.content))

    async def on_response(response):
        await response.aread()
        current["outcome"] = "response_received" if response.is_success else "http_error"
        try:
            payload = response.json()
        except ValueError:
            return  # JSON이 아닌 오류 응답도 usage가 없는 HTTP 응답으로 보존한다.
        if not isinstance(payload, dict):
            return
        current["service_tier"] = payload.get("service_tier")
        current["response_model"] = payload.get("model")
        usage = payload.get("usage")
        if isinstance(usage, dict):
            details = usage.get("prompt_tokens_details")
            observe_usage(current, dict(usage, cached_tokens=details.get("cached_tokens")
                          if isinstance(details, dict) else None))

    return {"request": [on_request], "response": [on_response]}
