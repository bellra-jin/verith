"""OpenAI LLM client adapter — Technical Agent의 `complete(prompt) -> str` 계약 구현.

명시 opt-in strict 경로는 요청별 로컬 소비/전 호출 증거를 추가한다. 계수 DI는 기본 unavailable이며,
Backend claim/영속 정산·실제 SDK/계수 provenance·운영 활성화를 대신하지 않는다. legacy는 기존 계약이다.

legacy 경로는 OpenAI Responses API 호출 → `output_text` 추출 → 예외를 `LlmCallError`로
변환하는 것만 한다. supervisor/node orchestration·prompt 구조·응답 schema·검증 로직은 건드리지 않고,
기존 fake LLM과 **교체 가능한 adapter**로 동작한다(구조적 Protocol `complete`).

secret-safe(technical_coding_guidelines §2.2·§13.2): raw prompt·raw response body·API key·
Authorization 헤더를 저장하거나 예외 메시지에 담지 않는다. 예외는 **type 이름 수준**만 남기고,
`from None`으로 chain을 끊어 원본 OpenAIError가 상위 traceback에 노출되지 않게 한다.

운영 안전: **SDK 재시도 끔(`max_retries=0`)** — agent-level 재생성/template fallback이 있으므로
SDK retry는 중복이자 60초 API 계약 초과 위험. **`store=False`** — OpenAI 측 application state에
저장하지 않는다(stateless). 사용자 분석 이력·follow-up context는 우리 backend DB가 관리한다(이 브랜치
범위 밖). 총 60초 deadline 완전 보장(호출 간 deadline 전파)은 후속 AI endpoint 범위다.

trace 경계 밖: 이 어댑터는 trace sink를 알지 못한다. 대신 `model`과 `last_usage`(호출당 토큰
사용량)를 optional 속성으로 노출해, 후속 AI endpoint 통합에서 trace 배선을 준비만 해 둔다.

runtime wiring은 이 브랜치 범위 밖 — `run_technical_agent`는 자동으로 이 client를 만들지 않고
계속 주입식이다. 운영에서는 endpoint가 `default_openai_client()`를 생성해 주입한다.
"""

from __future__ import annotations

import logging
import os
import time
import asyncio
from dataclasses import dataclass, fields, replace
from datetime import datetime, UTC
import hashlib
import json
import math
import re
import threading
from typing import Any
from uuid import UUID

import openai
import httpx

from ..config import OPENAI_MAX_OUTPUT_TOKENS, OPENAI_MAX_RETRIES, OPENAI_STORE, OPENAI_TEMPERATURE, OPENAI_TIMEOUT_SECONDS, load_openai_settings
from .llm.utils import LlmCallError
from ....shared.runtime.deadline import Deadline, DeadlineExceeded

logger = logging.getLogger(__name__)

_STRICT_MAX = 2**63-1
_COUNT_MAPPING = 'technical.responses.model-input.v1'
_STRICT_REASONS = frozenset({'POLICY_INVALID','DEADLINE_EXCEEDED','SDK_POLICY_INVALID',
    'COUNT_UNAVAILABLE','COUNT_INVALID','CLOSED','BUDGET_EXCEEDED','PROMPT_INVALID',
    'SDK_UNKNOWN','COUNT_FAILED','USAGE_UNKNOWN','USAGE_LIMIT_MISMATCH',
    'RESPONSE_METADATA_MISMATCH','RESPONSE_NOT_COMPLETED','TEXT_INVALID','CLOCK_INVALID',
    'HTTP_INVALID','RESPONSE_LIMIT'})
_STRICT_POLICY_FIELDS = frozenset({'operation','enabled','currency','supported_tickers',
    'user_daily_limit','service_daily_limit','daily_budget_nano','attempt_reserve_nano',
    'deadline_seconds','model','service_tier','price_id','price_evidence_sha256',
    'input_nano_per_token','output_nano_per_token','input_token_cap','output_token_cap',
    'input_byte_cap','output_byte_cap','max_calls'})


class _StrictLlmFailure(RuntimeError):
    """Only module-owned fixed reasons, never provider or caller text."""
    def __init__(self,reason):
        super().__init__(reason if type(reason) is str and reason in _STRICT_REASONS else 'POLICY_INVALID')


def _strict_json(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)


def _strict_sha(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _strict_int(value, *, zero=False):
    if type(value) is not int or not (0 if zero else 1)<=value<=_STRICT_MAX:
        raise _StrictLlmFailure('POLICY_INVALID')
    return value


def _strict_hash(value):
    if type(value) is not str or re.fullmatch('[0-9a-f]{64}',value) is None:
        raise _StrictLlmFailure('POLICY_INVALID')


def _strict_same_callable(left,right):
    if left is right:return True
    # Re-reading a Python bound method creates a new method object. Compare its
    # actual receiver/function identities, without invoking caller equality.
    owner=getattr(left,'__self__',None);function=getattr(left,'__func__',None)
    return (owner is not None and function is not None
            and owner is getattr(right,'__self__',None) and function is getattr(right,'__func__',None))


@dataclass(frozen=True,slots=True,repr=False)
class TechnicalLlmPolicy:
    """Full CF048 bytes/hash plus an independently supplied typed projection."""
    policy_json: str
    policy_sha256: str
    model: str
    service_tier: str
    price_id: str
    price_evidence_sha256: str
    input_nano_per_token: int
    output_nano_per_token: int
    input_token_cap: int
    output_token_cap: int
    input_byte_cap: int
    output_byte_cap: int
    max_calls: int
    attempt_reserve_nano: int

    def validated(self):
        try:
            _strict_hash(self.policy_sha256)
            if type(self.policy_json) is not str or len(self.policy_json.encode('utf-8'))>16384:
                raise _StrictLlmFailure('POLICY_INVALID')
            def unique(pairs):
                result={}
                for key,value in pairs:
                    if key in result:raise _StrictLlmFailure('POLICY_INVALID')
                    result[key]=value
                return result
            value=json.loads(self.policy_json,object_pairs_hook=unique)
            if (type(value) is not dict or set(value)!=_STRICT_POLICY_FIELDS
                    or _strict_json(value)!=self.policy_json or _strict_sha(self.policy_json)!=self.policy_sha256
                    or value['operation']!='technical.analysis.v1' or value['enabled'] is not True
                    or value['currency']!='USD' or value['service_tier']!='default'):
                raise _StrictLlmFailure('POLICY_INVALID')
            for field in fields(self):
                if field.name not in {'policy_json','policy_sha256'}:
                    supplied=getattr(self,field.name)
                    if type(supplied) is not type(value[field.name]) or supplied!=value[field.name]:
                        raise _StrictLlmFailure('POLICY_INVALID')
            numbers=_STRICT_POLICY_FIELDS-{'operation','enabled','currency','supported_tickers','model','service_tier','price_id','price_evidence_sha256'}
            for name in numbers:_strict_int(value[name])
            for name in ('model','price_id'):
                if type(value[name]) is not str or re.fullmatch('[A-Za-z0-9_.:-]{1,128}',value[name]) is None:
                    raise _StrictLlmFailure('POLICY_INVALID')
            _strict_hash(value['price_evidence_sha256'])
            tickers=value['supported_tickers']
            if (type(tickers) is not list or not 1<=len(tickers)<=1000
                    or any(type(t) is not str or re.fullmatch('[0-9]{6}',t) is None for t in tickers)
                    or tickers!=sorted(set(tickers)) or value['user_daily_limit']>value['service_daily_limit']
                    or value['deadline_seconds']>86400 or not 1<=value['max_calls']<=4):
                raise _StrictLlmFailure('POLICY_INVALID')
            hold=_strict_int(_strict_int(self.input_token_cap*self.input_nano_per_token)
                             +_strict_int(self.output_token_cap*self.output_nano_per_token))
            if not _strict_int(hold*self.max_calls)<=self.attempt_reserve_nano<=value['daily_budget_nano']:
                raise _StrictLlmFailure('POLICY_INVALID')
            return value
        except (ValueError,TypeError,UnicodeError,RecursionError,OverflowError):
            raise _StrictLlmFailure('POLICY_INVALID') from None


@dataclass(frozen=True,slots=True,repr=False)
class TechnicalTokenCount:
    """An opaque receipt must also be authenticated by the trusted count DI.

    Constructing these integers/hashes is insufficient. Only explicit reviewed
    DI or the owned official-count factory supplies one; default DI is absent.
    """
    input_tokens: int
    model: str
    mapping: str
    version: str
    provenance_sha256: str
    prompt_sha256: str
    projection_sha256: str
    request_sha256: str
    receipt: Any
    ordinal: int=0


@dataclass(frozen=True,slots=True,repr=False)
class TechnicalLlmEvidence:
    ordinal: int
    analysis_id: UUID
    attempt_id: UUID
    policy_sha256: str
    request_sha256: str
    prompt_sha256: str
    projection_sha256: str
    model: str
    service_tier: str
    input_token_cap: int
    output_token_cap: int
    held_nano: int
    entered: bool=False
    response_received: bool=False
    usage: tuple[int,int,int] | None=None
    estimated_nano: int | None=None
    response_model: str='unknown'
    response_tier: str='unknown'
    text_accepted: bool=False
    reason: str | None=None
    elapsed_ms: int=0
    count_entered: bool=False
    count_response_received: bool=False
    count_validated: bool=False
    counted_input_tokens: int | None=None


class TechnicalRequestLlmBudget:
    """One request-local, thread-safe consumed budget; no reset or durable claim.

    The explicitly injected counter must count the exact projection and verify
    its own opaque receipt/provenance. Arbitrary DI/SDK internals are outside
    this local gate's provenance guarantee. No tokenizer/API is auto-created.
    """
    def __init__(self, *, policy, analysis_id, attempt_id, reserved_nano, started_at,
                 deadline_at, counter=None, clock=time.monotonic, utcnow=None):
        if type(policy) is not TechnicalLlmPolicy:
            raise _StrictLlmFailure('POLICY_INVALID')
        policy=TechnicalLlmPolicy(**{field.name:getattr(policy,field.name) for field in fields(policy)})
        limits=policy.validated()
        if (type(analysis_id) is not UUID or type(attempt_id) is not UUID or not analysis_id.int
                or not attempt_id.int or analysis_id==attempt_id
                or type(started_at) is not datetime or type(deadline_at) is not datetime
                or started_at.utcoffset()!=UTC.utcoffset(None) or deadline_at.utcoffset()!=UTC.utcoffset(None)
                or not 0<(deadline_at-started_at).total_seconds()<=limits['deadline_seconds']
                or type(reserved_nano) is not int or reserved_nano!=policy.attempt_reserve_nano):
            raise _StrictLlmFailure('POLICY_INVALID')
        self._policy=policy
        self._unit_prices=(policy.input_nano_per_token,policy.output_nano_per_token)
        self._policy_json,self._policy_sha=policy.policy_json,policy.policy_sha256
        self._analysis_id,self._attempt_id=UUID(int=analysis_id.int),UUID(int=attempt_id.int)
        self._reserved=reserved_nano
        self._utcnow=utcnow or (lambda:datetime.now(UTC));self._clock=clock
        self._deadline_at=deadline_at
        anchor=clock()  # precede the wall-clock observation; include its delay conservatively
        now=self._utcnow()
        if (type(anchor) not in (int,float) or not math.isfinite(anchor)
                or type(now) is not datetime or now.utcoffset()!=UTC.utcoffset(None) or now<started_at):
            raise _StrictLlmFailure('CLOCK_INVALID')
        remaining=max(0,min((deadline_at-now).total_seconds(),(deadline_at-started_at).total_seconds()))
        self._monotonic_deadline=anchor+remaining
        self._identity=_strict_sha(_strict_json(dict(analysis_id=str(analysis_id),attempt_id=str(attempt_id),
            policy_sha256=self._policy_sha,reserved_nano=reserved_nano,
            started_at=started_at.isoformat(),deadline_at=deadline_at.isoformat())))
        self._counter=counter
        self._counter_binding=None if counter is None else tuple(getattr(counter,k,None) for k in ('mapping','version','provenance_sha256'))
        self._lock=threading.Lock();self._records=();self._closed=None
        self._official_bundle=None

    def snapshot(self):
        with self._lock:
            return tuple(replace(record,analysis_id=UUID(int=record.analysis_id.int),
                attempt_id=UUID(int=record.attempt_id.int)) for record in self._records)

    @property
    def closed_reason(self):
        with self._lock:return self._closed

    def _close(self,reason):
        with self._lock:
            if self._closed is None:self._closed=reason

    def _remaining(self):
        remaining=min(self._monotonic_deadline-self._clock(),(self._deadline_at-self._utcnow()).total_seconds())
        if not math.isfinite(remaining) or remaining<=0:raise _StrictLlmFailure('DEADLINE_EXCEEDED')
        return remaining

    def _policy_check(self):
        self._policy.validated()
        if (self._policy.policy_json,self._policy.policy_sha256)!=(self._policy_json,self._policy_sha):
            raise _StrictLlmFailure('POLICY_INVALID')

    def _request_check(self,adapter,request,dispatch=None):
        self._policy_check();p=self._policy
        if self._official_bundle is not None:self._official_bundle.check()
        if dispatch is not None:
            sdk,responses,create=dispatch
            if (adapter._client is not sdk or sdk.responses is not responses
                    or not _strict_same_callable(responses.create,create)):
                raise _StrictLlmFailure('SDK_POLICY_INVALID')
        if (adapter.model!=p.model or type(adapter._max_output_tokens) is not int
                or adapter._max_output_tokens!=p.output_token_cap or adapter._store is not False
                or type(getattr(adapter._client,'max_retries',None)) is not int or adapter._client.max_retries!=0
                or type(adapter._timeout) not in (int,float) or not math.isfinite(adapter._timeout) or adapter._timeout<=0
                or request['model']!=p.model or request['service_tier']!=p.service_tier
                or request['max_output_tokens']!=p.output_token_cap or request['store'] is not False
                or request.get('temperature')!=adapter._temperature):
            raise _StrictLlmFailure('SDK_POLICY_INVALID')
        if adapter._temperature is not None and (type(adapter._temperature) not in (int,float)
                or not math.isfinite(adapter._temperature) or not 0<=adapter._temperature<=2):
            raise _StrictLlmFailure('SDK_POLICY_INVALID')
        self._remaining()

    def _request_sha(self,request):
        return _strict_sha(_strict_json({'request_identity':self._identity,'generation':request}))

    def _count(self,ordinal,adapter,request,prompt_sha,projection_sha,request_sha,dispatch):
        counter=self._counter
        if self._official_bundle is None:
            self._enter_count(ordinal,adapter,request,request_sha,dispatch)
        # Official counter enters only inside the owned transport immediately
        # before forwarding; creating an SDK streaming context sends nothing.
        evidence=counter.count(model=request['model'],input=request['input'],mapping=_COUNT_MAPPING,
            prompt_sha256=prompt_sha,projection_sha256=projection_sha,request_sha256=request_sha,
            ordinal=ordinal)
        with self._lock:
            record=self._records[ordinal-1]
            self._records=self._records[:ordinal-1]+(replace(record,count_response_received=True),)+self._records[ordinal:]
            self._remaining()
        if type(evidence) is not TechnicalTokenCount:raise _StrictLlmFailure('COUNT_INVALID')
        _strict_int(evidence.input_tokens,zero=True)
        _strict_hash(evidence.provenance_sha256)
        for value in (evidence.prompt_sha256,evidence.projection_sha256,evidence.request_sha256):_strict_hash(value)
        if (evidence.input_tokens>self._policy.input_token_cap or evidence.model!=request['model']
                or type(evidence.model) is not str or type(evidence.mapping) is not str
                or evidence.mapping!=_COUNT_MAPPING or type(evidence.version) is not str
                or re.fullmatch('[A-Za-z0-9_.:-]{1,128}',evidence.version) is None
                or self._counter_binding!=(evidence.mapping,evidence.version,evidence.provenance_sha256)
                or self._counter_binding!=tuple(getattr(counter,k,None) for k in ('mapping','version','provenance_sha256'))
                or evidence.prompt_sha256!=prompt_sha or evidence.projection_sha256!=projection_sha
                or evidence.request_sha256!=request_sha or evidence.receipt is None
                or type(evidence.ordinal) is not int or evidence.ordinal!=ordinal
                or type(evidence.receipt) in (bool,int,float)
                or counter.verify(evidence,model=request['model'],input=request['input'],mapping=_COUNT_MAPPING,
                    prompt_sha256=prompt_sha,projection_sha256=projection_sha,request_sha256=request_sha,
                    ordinal=ordinal) is not True):
            raise _StrictLlmFailure('COUNT_INVALID')
        with self._lock:
            record=self._records[ordinal-1]
            if not record.count_entered or record.count_validated:raise _StrictLlmFailure('COUNT_INVALID')
            self._records=self._records[:ordinal-1]+(replace(record,count_validated=True,
                counted_input_tokens=evidence.input_tokens),)+self._records[ordinal:]
        return evidence.input_tokens

    def _reserve(self,adapter,request,prompt_sha,projection_sha,request_sha,dispatch):
        with self._lock:
            if self._closed is not None:raise _StrictLlmFailure('CLOSED')
            self._request_check(adapter,request,dispatch)
            if self._counter is None:raise _StrictLlmFailure('COUNT_UNAVAILABLE')
            if not callable(getattr(self._counter,'count',None)) or not callable(getattr(self._counter,'verify',None)):
                raise _StrictLlmFailure('COUNT_UNAVAILABLE')
            self._timeout_for(adapter)
            if self._request_sha(request)!=request_sha:raise _StrictLlmFailure('COUNT_INVALID')
            hold=self._policy.input_token_cap*self._policy.input_nano_per_token+self._policy.output_token_cap*self._policy.output_nano_per_token
            if (len(self._records)>=self._policy.max_calls
                    or _strict_int(sum(r.held_nano for r in self._records)+hold)>self._reserved):
                raise _StrictLlmFailure('BUDGET_EXCEEDED')
            ordinal=len(self._records)+1
            self._records+= (TechnicalLlmEvidence(ordinal,self._analysis_id,self._attempt_id,self._policy_sha,
                request_sha,prompt_sha,projection_sha,self._policy.model,self._policy.service_tier,
                self._policy.input_token_cap,self._policy.output_token_cap,hold),)
            return ordinal

    def _timeout_for(self,adapter):
        remaining=min(float(adapter._timeout),self._remaining())
        if adapter._deadline is not None:
            narrower=adapter._deadline.remaining_seconds()
            if type(narrower) not in (int,float) or not math.isfinite(narrower) or narrower<=0:
                raise _StrictLlmFailure('DEADLINE_EXCEEDED')
            remaining=min(remaining,narrower)
        if not math.isfinite(remaining) or remaining<=0:raise _StrictLlmFailure('DEADLINE_EXCEEDED')
        return remaining

    def _enter_count(self,ordinal,adapter,request,request_sha,dispatch):
        with self._lock:
            record=self._records[ordinal-1]
            if self._closed is not None or record.count_entered or record.request_sha256!=request_sha:
                raise _StrictLlmFailure('CLOSED')
            self._request_check(adapter,request,dispatch)
            if self._request_sha(request)!=request_sha:raise _StrictLlmFailure('COUNT_INVALID')
            timeout=self._timeout_for(adapter)
            self._records=self._records[:ordinal-1]+(replace(record,count_entered=True),)+self._records[ordinal:]
            return timeout

    def _enter(self,ordinal,adapter,request,request_sha,dispatch):
        with self._lock:
            record=self._records[ordinal-1]
            if self._closed is not None or record.entered or not record.count_validated or record.request_sha256!=request_sha:
                raise _StrictLlmFailure('CLOSED')
            self._request_check(adapter,request,dispatch)
            if self._request_sha(request)!=request_sha:raise _StrictLlmFailure('COUNT_INVALID')
            remaining=self._timeout_for(adapter)
            self._records=self._records[:ordinal-1]+(replace(record,entered=True),)+self._records[ordinal:]
            return remaining

    def _finish(self,ordinal, *, response_received=False, usage=None, model='unknown',tier='unknown',
                accepted=False,reason=None,elapsed_ms=0):
        with self._lock:
            if accepted:
                self._policy_check();self._remaining()
            if reason is not None and self._closed is None:self._closed=reason
            if ordinal is None:return
            record=self._records[ordinal-1]
            estimate=None if usage is None else usage[0]*self._unit_prices[0]+usage[1]*self._unit_prices[1]
            if estimate is not None and estimate>_STRICT_MAX:estimate=None
            self._records=self._records[:ordinal-1]+(replace(record,response_received=response_received,
                usage=usage,estimated_nano=estimate,response_model=model,response_tier=tier,text_accepted=accepted,
                reason=reason,elapsed_ms=max(0,min(_STRICT_MAX,elapsed_ms))),)+self._records[ordinal:]


class OpenAiLlmClient:
    """OpenAI SDK를 감싼 `complete(prompt) -> str` 어댑터.

    주입식 SDK client(`client`)는 `client.responses.create(...)`만 요구한다 — 테스트는 fake를
    주입해 네트워크 없이 검증한다. `temperature`가 None이면 요청에서 생략한다(일부 모델 미허용 대비).
    """

    def __init__(
        self,
        client: Any,
        *,
        model: str,  # 코드 기본값 없음 — .env가 단일 출처(default_openai_client가 주입)
        temperature: float | None = OPENAI_TEMPERATURE,
        max_output_tokens: int = OPENAI_MAX_OUTPUT_TOKENS,
        timeout: float = OPENAI_TIMEOUT_SECONDS,
        store: bool = OPENAI_STORE,
        deadline: Deadline | None = None,
        strict: bool = False,
        request_budget: TechnicalRequestLlmBudget | None = None,
    ) -> None:
        self._client = client
        self.model = model
        self._temperature = temperature
        self._max_output_tokens = max_output_tokens
        self._timeout = timeout
        self._store = store  # False면 OpenAI 측 application state 미저장(stateless)
        self._deadline = deadline  # 있으면 per-call timeout을 남은 예산 이하로 줄인다(60초 계약 보호)
        if type(strict) is not bool or (strict and type(request_budget) is not TechnicalRequestLlmBudget):
            raise LlmCallError('TECHNICAL_LLM_POLICY_INVALID') from None
        self._strict,self._request_budget=strict,request_budget
        # 후속 trace 배선용 best-effort 노출 — **마지막 성공 호출**의 토큰 사용량(실패/미호출 시 None).
        # 동시 실행에서 request-scoped state로 신뢰하지 말 것(공유 client면 다른 요청이 덮을 수 있음).
        self.last_usage: dict[str, int] | None = None

    def complete(self, prompt: str) -> str:
        """Responses API 1회 호출 → `output_text` 반환. 실패는 모두 `LlmCallError`로 변환한다.

        어떤 실패든 `last_usage`는 None으로 남는다(진입 시 리셋 → text 추출 성공 후에만 저장).
        OpenAI 예외는 chain을 끊어(`from None`) raw 오류가 상위 traceback에 노출되지 않게 한다.
        """
        self.last_usage = None  # 진입 시 리셋 — 어떤 실패든 last_usage=None 보장
        if self._strict:
            return self._complete_strict(prompt)
        # deadline이 있으면 per-call timeout을 남은 예산 이하로 줄인다. 남은 예산이 없으면 호출 안 함.
        timeout = self._timeout
        if self._deadline is not None:
            remaining = self._deadline.remaining_seconds()
            if remaining <= 0.0:
                raise DeadlineExceeded("deadline exceeded before openai call")
            timeout = min(timeout, remaining)
        request: dict[str, Any] = {
            "model": self.model,
            "input": prompt,
            "max_output_tokens": self._max_output_tokens,
            "timeout": timeout,
            "store": self._store,  # OpenAI 측 저장 여부(기본 False=stateless)
        }
        if self._temperature is not None:  # None이면 파라미터 생략(모델별 미허용 대비)
            request["temperature"] = self._temperature
        started = time.perf_counter()
        try:
            response = self._client.responses.create(**request)
        except openai.OpenAIError as exc:  # timeout·rate limit·auth·connection·API·BadRequest 전부
            duration_ms = int((time.perf_counter() - started) * 1000)
            # 안전 breadcrumb만(error_type·model·duration) — raw 응답/prompt/key 미기록.
            logger.warning(
                "openai_call_failed",
                extra={"error_type": type(exc).__name__, "model": self.model, "duration_ms": duration_ms},
            )
            # from None: 원본 OpenAIError를 __cause__로 남기지 않아 상위 logger.exception이 raw를 못 찍는다.
            raise LlmCallError(f"OpenAI 호출 실패: {type(exc).__name__}") from None
        text = _extract_text(response)          # 빈 output이면 여기서 LlmCallError(last_usage는 None 유지)
        self.last_usage = _extract_usage(response)  # text 추출 성공 후에만 usage 저장
        return text

    def _complete_strict(self,prompt):
        budget=self._request_budget
        if type(budget) is not TechnicalRequestLlmBudget:
            raise LlmCallError('TECHNICAL_LLM_POLICY_INVALID') from None
        ordinal=None;received=False;usage=None;model=tier='unknown';phase='VALIDATION'
        started=time.perf_counter()
        try:
            if type(prompt) is not str:
                raise _StrictLlmFailure('PROMPT_INVALID')
            try:raw=prompt.encode('utf-8')
            except UnicodeError:raise _StrictLlmFailure('PROMPT_INVALID') from None
            if not raw or len(raw)>budget._policy.input_byte_cap:
                raise _StrictLlmFailure('PROMPT_INVALID')
            request=dict(model=self.model,input=prompt,max_output_tokens=self._max_output_tokens,
                store=self._store,service_tier=budget._policy.service_tier)
            if self._temperature is not None:request['temperature']=self._temperature
            budget._request_check(self,request)
            prompt_sha=_strict_sha(prompt)
            projection_sha=_strict_sha(_strict_json({'model':request['model'],'input':prompt}))
            request_sha=budget._request_sha(request)
            sdk=self._client;responses=sdk.responses;create=responses.create
            dispatch=(sdk,responses,create)
            if not callable(create):raise _StrictLlmFailure('SDK_POLICY_INVALID')
            ordinal=budget._reserve(self,request,prompt_sha,projection_sha,request_sha,dispatch)
            bundle=budget._official_bundle
            phase='COUNT'
            if bundle is None:
                count=budget._count(ordinal,self,request,prompt_sha,projection_sha,request_sha,dispatch)
            else:
                with bundle.phase(ordinal,'count',self,request,dispatch):
                    count=budget._count(ordinal,self,request,prompt_sha,projection_sha,request_sha,dispatch)
            phase='VALIDATION'
            if bundle is None:
                timeout=budget._enter(ordinal,self,request,request_sha,dispatch)
                phase='SDK'
                response=create(**request,timeout=timeout)
            else:
                with bundle.phase(ordinal,'generation',self,request,dispatch):
                    timeout=budget._timeout_for(self)
                    bundle._local.scope.timeout=timeout
                    phase='SDK'
                    response=create(**request,stream=False,timeout=timeout)
            received=True
            observed=_extract_usage(response)
            if observed is not None and all(value<=_STRICT_MAX for value in observed.values()):
                usage=tuple(observed[key] for key in ('input_tokens','output_tokens','total_tokens'))
            raw_model=getattr(response,'model',None);raw_tier=getattr(response,'service_tier',None)
            model='unknown' if raw_model is None else 'match' if type(raw_model) is str and raw_model==budget._policy.model else 'mismatch'
            tier='unknown' if raw_tier is None else 'match' if type(raw_tier) is str and raw_tier==budget._policy.service_tier else 'mismatch'
            if usage is None:raise _StrictLlmFailure('USAGE_UNKNOWN')
            if usage[0]!=count or usage[0]>budget._policy.input_token_cap or usage[1]>budget._policy.output_token_cap:
                raise _StrictLlmFailure('USAGE_LIMIT_MISMATCH')
            if model=='mismatch' or tier=='mismatch':raise _StrictLlmFailure('RESPONSE_METADATA_MISMATCH')
            status=getattr(response,'status',None)
            if type(status) is not str or status!='completed':raise _StrictLlmFailure('RESPONSE_NOT_COMPLETED')
            # Usage is captured before text/quality validation and remains even
            # when completed output is empty, malformed or over its UTF-8 cap.
            raw_text=getattr(response,'output_text',None)
            if type(raw_text) is not str or not raw_text.strip():raise _StrictLlmFailure('TEXT_INVALID')
            try:output_bytes=raw_text.encode('utf-8')
            except UnicodeError:raise _StrictLlmFailure('TEXT_INVALID') from None
            if len(output_bytes)>budget._policy.output_byte_cap:raise _StrictLlmFailure('TEXT_INVALID')
            output=getattr(response,'output',None)
            if getattr(response,'refusal',None) is not None:raise _StrictLlmFailure('RESPONSE_NOT_COMPLETED')
            if output is not None:
                if type(output) is not list:raise _StrictLlmFailure('RESPONSE_NOT_COMPLETED')
                for item in output:
                    for content in getattr(item,'content',()) or ():
                        if getattr(content,'type',None)=='refusal':raise _StrictLlmFailure('RESPONSE_NOT_COMPLETED')
            text=raw_text.strip()  # accept the exact UTF-8-capped text snapshot, not a second property read
            if self._deadline is not None:
                narrower=self._deadline.remaining_seconds()
                if type(narrower) not in (int,float) or not math.isfinite(narrower) or narrower<=0:
                    raise _StrictLlmFailure('DEADLINE_EXCEEDED')
            budget._finish(ordinal,response_received=True,usage=usage,model=model,tier=tier,accepted=True,
                elapsed_ms=int((time.perf_counter()-started)*1000))
            self.last_usage=dict(zip(('input_tokens','output_tokens','total_tokens'),usage))
            return text
        except BaseException as error:
            supplied=str(error) if type(error) is _StrictLlmFailure else None
            reason=supplied if supplied in _STRICT_REASONS else 'SDK_UNKNOWN' if phase=='SDK' else 'COUNT_FAILED' if phase=='COUNT' else 'POLICY_INVALID'
            budget._finish(ordinal,response_received=received,usage=usage,model=model,tier=tier,reason=reason,
                elapsed_ms=int((time.perf_counter()-started)*1000))
            if isinstance(error,asyncio.CancelledError):raise asyncio.CancelledError() from None
            if isinstance(error,KeyboardInterrupt):raise KeyboardInterrupt() from None
            if isinstance(error,SystemExit):raise SystemExit(1) from None
            raise LlmCallError('TECHNICAL_LLM_'+reason) from None

    def close(self):
        """Close only this request's owned bundle, after its physical work ends."""
        if self._strict and self._request_budget._official_bundle is not None:
            self._request_budget._official_bundle.close()


def _count_wire_json(raw):
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise _StrictLlmFailure('COUNT_INVALID')
            result[key]=value
        return result
    try:
        return json.loads(raw.decode('utf-8'),object_pairs_hook=unique,
            parse_constant=lambda _:(_ for _ in ()).throw(_StrictLlmFailure('COUNT_INVALID')))
    except (ValueError,UnicodeError,RecursionError,OverflowError):
        raise _StrictLlmFailure('COUNT_INVALID') from None


class _TechnicalResponseStream(httpx.SyncByteStream):
    """Bound reads underneath both SDK eager parsing and count iteration."""
    def __init__(self,response,bundle,scope,cap,length):
        self._response,self._bundle,self._scope=response,bundle,scope
        self._cap,self._length=cap,length;self._closed=False

    def __iter__(self):
        size=0
        try:
            for part in self._response.stream:
                self._bundle.remaining(self._scope)
                if type(part) is not bytes:raise _StrictLlmFailure('HTTP_INVALID')
                size+=len(part)
                if size>self._cap or (self._length is not None and size>self._length):
                    raise _StrictLlmFailure('RESPONSE_LIMIT')
                yield part
            self._bundle.remaining(self._scope)
            if self._length is not None and size!=self._length:raise _StrictLlmFailure('RESPONSE_LIMIT')
        except BaseException:
            try:self.close()
            except BaseException:pass
            raise
        else:self.close()

    def close(self):
        if not self._closed:
            self._closed=True
            try:self._response.close()
            except Exception:raise _StrictLlmFailure('HTTP_INVALID') from None


class _TechnicalPhase:
    def __init__(self,bundle,ordinal,phase,adapter,request,dispatch):
        self.bundle=bundle;self.ordinal=ordinal;self.phase=phase;self.adapter=adapter
        self.request=json.loads(_strict_json(request));self.dispatch=dispatch
        self.request_sha=bundle.budget._request_sha(request);self.forwarded=False;self.timeout=None

    def __enter__(self):
        b=self.bundle
        with b._lifetime_lock:
            if b._closing or getattr(b._local,'scope',None) is not None:raise _StrictLlmFailure('CLOSED')
            if self.adapter._client is not b.sdk or self.dispatch[0] is not b.sdk:
                raise _StrictLlmFailure('SDK_POLICY_INVALID')
            b.check();b.budget._request_check(self.adapter,self.request,self.dispatch)
            b.remaining(self);b._active+=1;b._local.scope=self
        return self

    def __exit__(self,*args):
        b=self.bundle
        with b._lifetime_lock:
            b._local.scope=None;b._active-=1
            if b._closing and b._active==0:
                try:b._dispose()
                except BaseException:
                    # Preserve the original phase error/cancellation.
                    if not args or args[0] is None:raise _StrictLlmFailure('HTTP_INVALID') from None


class _TechnicalOwnedTransport(httpx.BaseTransport):
    def __init__(self,inner):self._inner=inner;self._original=inner;self.bundle=None;self._closed=False

    def handle_request(self,request):
        b=self.bundle;scope=None if b is None else getattr(b._local,'scope',None)
        if scope is None:raise _StrictLlmFailure('SDK_POLICY_INVALID')
        b.check();b.remaining(scope)
        if self._inner is not self._original:raise _StrictLlmFailure('SDK_POLICY_INVALID')
        url=request.url
        path=b'/v1/responses/input_tokens' if scope.phase=='count' else b'/v1/responses'
        if (request.method!='POST' or url.scheme!='https' or url.host!='api.openai.com'
                or url.port not in (None,443) or url.raw_path!=path or url.query
                or url.username or url.password or url.fragment):raise _StrictLlmFailure('HTTP_INVALID')
        body=request.content
        if type(body) is not bytes or not body or len(body)>b.request_cap:raise _StrictLlmFailure('HTTP_INVALID')
        expected=({'model':scope.request['model'],'input':scope.request['input']} if scope.phase=='count'
                  else dict(scope.request,stream=False))
        parsed=_count_wire_json(body)
        if _strict_json(parsed)!=_strict_json(expected):raise _StrictLlmFailure('HTTP_INVALID')
        headers={};allowed={'authorization','host','accept','accept-encoding','connection','content-type',
            'content-length','user-agent','x-stainless-lang','x-stainless-package-version','x-stainless-os',
            'x-stainless-arch','x-stainless-runtime','x-stainless-runtime-version','x-stainless-async',
            'x-stainless-retry-count','x-stainless-read-timeout','x-stainless-raw-response'}
        for name,value in request.headers.multi_items():
            name=name.lower()
            if name not in allowed or name in headers or '\r' in value or '\n' in value:
                raise _StrictLlmFailure('HTTP_INVALID')
            headers[name]=value
            if name in b._metadata and value!=b._metadata[name]:raise _StrictLlmFailure('HTTP_INVALID')
            if ((name.startswith('x-stainless-') and name not in {
                    'x-stainless-retry-count','x-stainless-read-timeout','x-stainless-raw-response'})
                    or name in {'user-agent','accept'}) and value!=b._metadata.get(name):
                raise _StrictLlmFailure('HTTP_INVALID')
            if name=='connection' and value!='keep-alive':raise _StrictLlmFailure('HTTP_INVALID')
        if (headers.get('authorization')!='Bearer '+b._credential
                or headers.get('host') not in ('api.openai.com','api.openai.com:443')
                or headers.get('content-type')!='application/json'
                or headers.get('accept-encoding')!='identity'
                or headers.get('x-stainless-retry-count')!='0'
                or headers.get('content-length')!=str(len(body))
                or headers.get('x-stainless-raw-response') not in (None,'stream')
                or (scope.phase!='count' and 'x-stainless-raw-response' in headers)):
            raise _StrictLlmFailure('HTTP_INVALID')
        read_timeout=headers.get('x-stainless-read-timeout')
        if read_timeout is not None:
            try:value=float(read_timeout)
            except ValueError:raise _StrictLlmFailure('HTTP_INVALID') from None
            if not math.isfinite(value) or value<=0 or scope.timeout is None or value>scope.timeout:
                raise _StrictLlmFailure('HTTP_INVALID')
        timeouts=request.extensions.get('timeout')
        if type(timeouts) is not dict or set(timeouts)!={'connect','read','write','pool'}:
            raise _StrictLlmFailure('HTTP_INVALID')
        remaining=b.remaining(scope)
        for key,value in timeouts.items():
            if type(value) not in (int,float) or not math.isfinite(value) or value<=0 or scope.timeout is None or value>scope.timeout:
                raise _StrictLlmFailure('HTTP_INVALID')
            timeouts[key]=min(value,remaining)
        # A scope is bound to one physical phase. Consume only after every
        # outgoing check, immediately before forwarding, never around I/O.
        enter=b.budget._enter_count if scope.phase=='count' else b.budget._enter
        with b._lifetime_lock:
            if b._closing or scope.forwarded:raise _StrictLlmFailure('CLOSED')
            latest=enter(scope.ordinal,scope.adapter,scope.request,scope.request_sha,scope.dispatch)
            scope.forwarded=True
        for key in timeouts:timeouts[key]=min(timeouts[key],latest)
        response=None
        try:
            response=self._inner.handle_request(request)
            if scope.phase=='count':
                with b.budget._lock:
                    record=b.budget._records[scope.ordinal-1]
                    b.budget._records=b.budget._records[:scope.ordinal-1]+(replace(record,count_response_received=True),)+b.budget._records[scope.ordinal:]
            b.remaining(scope)
            if response.status_code!=200:raise _StrictLlmFailure('HTTP_INVALID')
            encoding=response.headers.get('content-encoding','identity')
            if encoding!='identity':raise _StrictLlmFailure('HTTP_INVALID')
            cap=b.count_cap if scope.phase=='count' else b.generation_cap
            lengths=response.headers.get_list('content-length')
            if len(lengths)>1:raise _StrictLlmFailure('RESPONSE_LIMIT')
            length=None
            if lengths:
                if re.fullmatch('[0-9]{1,10}',lengths[0]) is None:raise _StrictLlmFailure('RESPONSE_LIMIT')
                length=int(lengths[0])
                if length>cap:raise _StrictLlmFailure('RESPONSE_LIMIT')
            return httpx.Response(200,headers=response.headers,request=request,extensions=response.extensions,
                stream=_TechnicalResponseStream(response,b,scope,cap,length))
        except BaseException:
            if response is not None:
                try:response.close()
                except BaseException:pass
            raise

    def close(self):
        if not self._closed:
            self._closed=True
            try:self._original.close()
            except Exception:raise _StrictLlmFailure('HTTP_INVALID') from None


class _TechnicalOfficialCounter:
    mapping=_COUNT_MAPPING
    def __init__(self,bundle,version,provenance):
        self.bundle=bundle;self.version=version;self.provenance_sha256=provenance;self._receipts={}

    def count(self,**values):
        b=self.bundle;scope=getattr(b._local,'scope',None)
        if (scope is None or scope.phase!='count' or values.get('ordinal')!=scope.ordinal
                or values.get('request_sha256')!=scope.request_sha):raise _StrictLlmFailure('COUNT_INVALID')
        b.check();timeout=b.remaining(scope);scope.timeout=timeout
        with b.count_method(model=values['model'],input=values['input'],timeout=timeout) as response:
            # iter_bytes is bounded below the SDK; do not call parse/json.
            raw=b''.join(response.iter_bytes())
        b.remaining(scope)
        value=_count_wire_json(raw)
        if (type(value) is not dict or set(value)!={'object','input_tokens'}
                or value['object']!='response.input_tokens' or type(value['input_tokens']) is not int
                or not 0<=value['input_tokens']<=b.budget._policy.input_token_cap):
            raise _StrictLlmFailure('COUNT_INVALID')
        receipt=object()
        result=TechnicalTokenCount(value['input_tokens'],values['model'],self.mapping,self.version,
            self.provenance_sha256,values['prompt_sha256'],values['projection_sha256'],values['request_sha256'],
            receipt,scope.ordinal)
        with b.budget._lock:
            record=b.budget._records[scope.ordinal-1]
            if not record.count_entered or scope.ordinal in self._receipts:raise _StrictLlmFailure('COUNT_INVALID')
            self._receipts[scope.ordinal]=(result,{k:v for k,v in values.items() if k!='input'})
        return result

    def verify(self,evidence,**values):
        text=values.get('input')
        if (type(text) is not str or _strict_sha(text)!=values.get('prompt_sha256')
                or _strict_sha(_strict_json({'model':values.get('model'),'input':text}))!=values.get('projection_sha256')):
            return False
        with self.bundle.budget._lock:
            original=self._receipts.get(values.get('ordinal'))
            return original is not None and original[0] is evidence and original[1]=={k:v for k,v in values.items() if k!='input'}


class _TechnicalOwnedBundle:
    def __init__(self,budget,credential,request_cap,count_cap,generation_cap):
        self.budget=budget;self._credential=credential
        self.request_cap,self.count_cap,self.generation_cap=request_cap,count_cap,generation_cap
        self._local=threading.local();self._lifetime_lock=threading.RLock()
        self._active=0;self._closing=False;self._disposed=False
        self.sdk=self.client=self.transport=self.inner=None

    def check(self):
        if ('OPENAI_CUSTOM_HEADERS' in os.environ or any(logging.getLogger(name).isEnabledFor(logging.DEBUG)
                for name in ('openai','openai._base_client','openai._client'))):
            raise _StrictLlmFailure('SDK_POLICY_INVALID')
        s=self.sdk;c=self.client
        if (s is None or s._client is not c or c._transport is not self.transport
                or c._trust_env is not False or c.follow_redirects is not False or c._mounts
                or any(c._event_hooks.values()) or self.transport._inner is not self.inner
                or type(s.max_retries) is not int or s.max_retries!=0
                or str(s.base_url)!='https://api.openai.com/v1/' or s.api_key!=self._credential
                or s.responses is not self.responses
                or not _strict_same_callable(s.responses.create,self.create_method)
                or s.responses.input_tokens is not self.tokens
                or self.tokens.with_streaming_response is not self.streaming
                or not _strict_same_callable(self.streaming.count,self.count_method)
                or self.budget._official_bundle is not self or self.budget._counter is not self.counter):
            raise _StrictLlmFailure('SDK_POLICY_INVALID')

    def remaining(self,scope):return self.budget._timeout_for(scope.adapter)

    def phase(self,*args):return _TechnicalPhase(self,*args)

    def _dispose(self):
        if self._disposed:return
        self._disposed=True
        # SDK.close() delegates to its mutable _client. Close the captured
        # owned HTTP resources directly; never a substituted client/mount.
        failed=False
        try:
            if self.client is not None and self.client._transport is self.transport and not self.client._mounts:
                self.client.close()
        except BaseException:failed=True
        try:
            if self.transport is not None:self.transport.close()
            elif self.inner is not None:self.inner.close()
        except BaseException:failed=True
        if failed:raise _StrictLlmFailure('HTTP_INVALID') from None

    def close(self):
        with self._lifetime_lock:
            self._closing=True
            if self._active==0:self._dispose()


def official_count_openai_client(*,request_budget,api_key,request_wire_cap,count_wire_cap,
        generation_wire_cap,count_version,count_provenance_sha256,timeout,temperature=None,deadline=None):
    """Explicit opt-in only. No settings/env-file/key discovery or real authority.

    The caller supplies reviewed free-count mapping/provenance and one run's
    budget. This factory owns fresh SDK/HTTP resources until client.close().
    """
    bundle=None
    try:
        if type(request_budget) is not TechnicalRequestLlmBudget:raise _StrictLlmFailure('POLICY_INVALID')
        p=request_budget._policy;request_budget._policy_check();request_budget._remaining()
        if (type(api_key) is not str or not api_key or not api_key.isascii()
                or any(ord(c)<=32 or ord(c)>=127 for c in api_key)
                or type(timeout) not in (int,float) or not math.isfinite(timeout) or timeout<=0
                or type(count_version) is not str or re.fullmatch('[A-Za-z0-9_.:-]{1,128}',count_version) is None):
            raise _StrictLlmFailure('POLICY_INVALID')
        for cap in (request_wire_cap,count_wire_cap,generation_wire_cap):
            if type(cap) is not int or not 0<cap<=2*1024*1024:raise _StrictLlmFailure('POLICY_INVALID')
        _strict_hash(count_provenance_sha256)
        if ('OPENAI_CUSTOM_HEADERS' in os.environ or any(logging.getLogger(name).isEnabledFor(logging.DEBUG)
                for name in ('openai','openai._base_client','openai._client'))):
            raise _StrictLlmFailure('SDK_POLICY_INVALID')
        with request_budget._lock:
            if request_budget._official_bundle is not None or request_budget._counter is not None or request_budget._records or request_budget._closed:
                raise _StrictLlmFailure('POLICY_INVALID')
            # A failed construction cannot be rebound to another SDK or caller.
            bundle=_TechnicalOwnedBundle(request_budget,api_key,request_wire_cap,count_wire_cap,generation_wire_cap)
            request_budget._official_bundle=bundle
        bundle.inner=httpx.HTTPTransport(verify=True,trust_env=False,proxy=None,retries=0)
        bundle.transport=_TechnicalOwnedTransport(bundle.inner);bundle.transport.bundle=bundle
        bundle.client=httpx.Client(transport=bundle.transport,trust_env=False,follow_redirects=False,
            proxy=None,mounts=None,event_hooks=None,timeout=timeout)
        bundle.sdk=openai.OpenAI(api_key=api_key,admin_api_key='',organization='',project='',webhook_secret='',
            base_url='https://api.openai.com/v1/',max_retries=0,timeout=timeout,http_client=bundle.client,
            default_headers={'Accept-Encoding':'identity','OpenAI-Organization':openai.omit,'OpenAI-Project':openai.omit},
            default_query={})
        bundle._metadata={str(k).lower():v for k,v in bundle.sdk.default_headers.items()
            if type(v) is str and str(k).lower() not in {'authorization','content-length'}}
        bundle.responses=bundle.sdk.responses;bundle.create_method=bundle.responses.create
        bundle.tokens=bundle.responses.input_tokens;bundle.streaming=bundle.tokens.with_streaming_response
        bundle.count_method=bundle.streaming.count
        bundle.counter=_TechnicalOfficialCounter(bundle,count_version,count_provenance_sha256)
        request_budget._counter=bundle.counter
        request_budget._counter_binding=(bundle.counter.mapping,count_version,count_provenance_sha256)
        bundle.check()
        return OpenAiLlmClient(bundle.sdk,model=p.model,temperature=temperature,max_output_tokens=p.output_token_cap,
            timeout=timeout,store=False,deadline=deadline,strict=True,request_budget=request_budget)
    except BaseException as error:
        if bundle is not None:
            request_budget._close('SDK_POLICY_INVALID')
            try:bundle.close()
            except BaseException:pass  # Preserve original error/cancellation, never cleanup text.
        if isinstance(error,asyncio.CancelledError):raise asyncio.CancelledError() from None
        if isinstance(error,KeyboardInterrupt):raise KeyboardInterrupt() from None
        if isinstance(error,SystemExit):raise SystemExit(1) from None
        raise LlmCallError('TECHNICAL_LLM_SDK_POLICY_INVALID') from None


def _extract_text(response: Any) -> str:
    """Responses API 편의 property `output_text`에서 text만 추출. 비어 있으면 `LlmCallError`."""
    text = getattr(response, "output_text", None)
    if not isinstance(text, str) or not text.strip():
        # 응답 shape가 예상과 다르거나 빈 응답 → 호출 실패로 취급(raw 미포함).
        raise LlmCallError("OpenAI 응답에서 text를 추출하지 못했습니다(빈 output_text).")
    return text.strip()


def _extract_usage(response: Any) -> dict[str, int] | None:
    """`response.usage`에서 input/output/total 토큰만 안전 추출(없거나 불안정하면 None)."""
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    values = {name: getattr(usage, name, None)
              for name in ("input_tokens", "output_tokens", "total_tokens")}
    # Missing/invalid evidence is unknown, never an invented zero or a truncated
    # number. bool is an int subclass, so require the exact wire integer type.
    if any(type(value) is not int or value < 0 for value in values.values()):
        return None
    if values["input_tokens"] + values["output_tokens"] != values["total_tokens"]:
        return None
    return values


def default_openai_client(
    *,
    model: str | None = None,
    temperature: float | None = OPENAI_TEMPERATURE,
    max_output_tokens: int = OPENAI_MAX_OUTPUT_TOKENS,
    timeout: float = OPENAI_TIMEOUT_SECONDS,
    max_retries: int = OPENAI_MAX_RETRIES,
    store: bool = OPENAI_STORE,
    deadline: Deadline | None = None,
    strict: bool = False,
    request_budget: TechnicalRequestLlmBudget | None = None,
) -> OpenAiLlmClient:
    """운영용 OpenAI client 생성. **API key·model 누락은 여기서 fail-fast**(config error, LlmCallError 아님).

    api_key·model은 `config.load_openai_settings()`가 .env/환경변수에서 읽는다(코드/로그/trace 미저장).
    `model` 인자를 명시하면 .env 값 대신 그것을 쓴다(테스트/실험용). **`max_retries=0`(SDK 재시도 끔)**
    으로 60초 계약 안에서 agent-level 재생성/fallback을 우선한다. `store=False`로 OpenAI 측 저장을 끈다.
    `run_technical_agent`는 이걸 자동 호출하지 않는다 — endpoint 통합에서 주입한다(A안).
    """
    if type(strict) is not bool or (strict and type(request_budget) is not TechnicalRequestLlmBudget):
        raise LlmCallError('TECHNICAL_LLM_POLICY_INVALID') from None
    if strict:
        try:request_budget._policy_check()
        except _StrictLlmFailure:raise LlmCallError('TECHNICAL_LLM_POLICY_INVALID') from None
    settings = load_openai_settings()  # api_key·model 누락 시 RuntimeError(어디에 무엇을 넣을지 명시)
    sdk_client = openai.OpenAI(api_key=settings.api_key, timeout=timeout, max_retries=max_retries)
    return OpenAiLlmClient(
        sdk_client,
        model=model or settings.model,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        timeout=timeout,
        store=store,
        deadline=deadline,
        strict=strict,
        request_budget=request_budget,
    )
