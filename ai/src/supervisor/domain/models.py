"""Supervisor 입출력 typed 계약 (schema-first).

Supervisor 는 사용자 질문을 해석하고, 필요 시 backend 종목 정본으로 context 를 보강한 뒤,
등록된 legacy task에 대해 실행용 task envelope 를 생성한다. 자유 텍스트가 아니라 이 모듈의
구조화된 모델로만 결과를 표현한다.

경계: 이 모듈은 backend DB 를 import 하지 않는다. 종목 식별은 resolver HTTP 경계로만 하고,
ticker/corp_code 를 임의로 만들지 않는다(context 의 stock_code 는 resolver 결과에서만 온다).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Legacy model compatibility only; runtime execution is closed.
AgentType = Literal["fundamental", "technical", "flow", "industry"]
AGENT_ORDER: tuple[AgentType, ...] = ("fundamental", "technical", "flow", "industry")

# resolver 호출 결과 요약 상태. not_found 와 error(tool-error)·not_attempted 를 절대 섞지 않는다.
ResolutionStatus = Literal[
    "resolved",       # 단일 종목 확정
    "ambiguous",      # 후보 다수 — 단일 확정 아님
    "not_found",      # 정상 200 도메인 결과: 종목 context 없음
    "not_attempted",  # 비종목 질문 등으로 resolver 를 호출하지 않음
    "error",          # tool-error(timeout·연결·5xx) — not_found 와 다르다
]

# resolver 호출이 도구 장애로 실패한 종류(도메인 not_found 와 구분).
ResolverErrorKind = Literal["timeout", "connection", "backend_error", "invalid_response"]

# 종목 context 의 출처. canonical resolver(정본, persisted) vs fallback lookup(이번 요청용 임시, ephemeral).
ResolutionSource = Literal["canonical_resolver", "fallback_lookup"]

# can_run 판정에 대한 단일 사유 코드(성공/실패 공통). 자유 텍스트가 아니라 코드값으로 표현한다.
ReasonCode = Literal[
    "stock_resolved",       # 종목 확정 → 실행 가능
    "no_stock_required",    # 종목 없이도 실행 가능(industry)
    "stock_not_resolved",   # 종목 의존 agent인데 resolve 미시도/미확정
    "stock_ambiguous",      # 종목 후보 다수 → 단일 확정 필요
    "stock_not_found",      # 종목 의존 agent인데 not_found
    "resolver_unavailable", # 종목 의존 agent인데 resolver tool-error
]


class StockContext(BaseModel):
    """agent 에 내려주는 최소 공통 종목 context. 미해결이면 code/name/market 전부 None.

    `source`/`persisted` 는 이 종목이 어디서 왔는지 자기서술한다. canonical resolver 결과는 기본값
    (canonical_resolver·persisted=True)이고, fallback lookup 으로 이번 요청에 한해 만든 **ephemeral**
    context 는 `source="fallback_lookup"·persisted=False`. persisted=False 는 **정본(stocks)로 승격 금지**
    를 뜻한다 — agent 로 전달은 되지만 DB 저장/색인/seed 경로로 이어지지 않는다."""

    model_config = ConfigDict(extra="forbid")

    stock_code: str | None = None
    stock_name: str | None = None
    market: str | None = None
    source: ResolutionSource = "canonical_resolver"
    persisted: bool = True


class StockCandidate(BaseModel):
    """ambiguous 시 후보(표시용). matched_text/match_type 등 backend 세부에는 결합하지 않는다."""

    model_config = ConfigDict(extra="forbid")

    stock_code: str
    stock_name: str
    market: str | None = None


class ResolverError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: ResolverErrorKind


class Resolution(BaseModel):
    """resolver 사용 여부와 결과. status 로 not_found/not_attempted/error 를 구분한다.

    fallback lookup 경계: canonical resolver 가 not_found 일 때만 보조 lookup 을 시도한다(§fallback).

    **세 필드를 함께 읽어야 한다(단독 오독 주의):**
    - `used_stock_resolver=True` = 1차 canonical resolver 를 **시도**했다(최종 결과가 canonical 에서 나왔다는
      뜻이 **아니다** — fallback 이 최종일 때도 True 다).
    - `used_fallback_lookup=True` = 2차 fallback 도 **시도**했다.
    - `source` = **최종 종목이 어디서 왔는지**(canonical_resolver | fallback_lookup). 최종 출처 판단은 이걸 본다.
    조합: canonical resolved → (used_stock_resolver=True, used_fallback_lookup=False, source=canonical_resolver,
    persisted=True). fallback high-confidence 단일 → (True, True, source=fallback_lookup, persisted=False,
    status=resolved, stock=ephemeral). fallback ambiguous → source=fallback_lookup 이되 stock 없음(자동선택 금지).
    `source`/`persisted` 는 resolved 일 때 `stock.source`/`stock.persisted` 와 일치한다."""

    model_config = ConfigDict(extra="forbid")

    used_stock_resolver: bool
    used_fallback_lookup: bool = False
    status: ResolutionStatus
    stock: StockContext | None = None
    candidates: list[StockCandidate] = Field(default_factory=list)
    error: ResolverError | None = None
    source: ResolutionSource = "canonical_resolver"
    persisted: bool = True


class TaskEnvelope(BaseModel):
    """한 agent 실행용 봉투. supervisor 는 자연어 query 와 공통 stock context 까지만 책임진다
    (agent 내부 세부 파라미터는 조립하지 않는다)."""

    model_config = ConfigDict(extra="forbid")

    agent_type: AgentType
    rewritten_query: str
    context: StockContext
    can_run: bool
    reason: ReasonCode


class SupervisorInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1)
    request_id: str | None = None
    trace_id: str | None = None


class SupervisorDecision(BaseModel):
    """supervisor 최종 산출. legacy typed decision; not executable."""

    model_config = ConfigDict(extra="forbid")

    original_query: str            # 원본 질문 절대 보존
    resolution: Resolution
    tasks: list[TaskEnvelope]


import hashlib
import json
import re
import unicodedata
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,field_validator,model_validator

VERSION='supervisor.flow-plan.v1'
POLICY='supervisor.flow-only.1'
VIEWS=('flow','technical','fundamental','macro','industry','news','overview')

def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(value):return hashlib.sha256(value.encode('utf8')).hexdigest()
def decode(raw):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('Invalid JSON')
            result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Invalid JSON')))

class StrictPlanModel(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,hide_input_in_errors=True)

class StockReference(StrictPlanModel):
    stock_code:str=Field(pattern=r'^[0-9]{6}$')
    stock_name:str=Field(min_length=1,max_length=256)
    market:Literal['KOSPI','KOSDAQ','KONEX']|None
    @field_validator('stock_name')
    @classmethod
    def valid_name(cls,value):
        value.encode('utf8')
        if not value.strip() or any(unicodedata.category(c)=='Cc' for c in value):raise ValueError('Invalid stock name')
        return value

class StockOption(StockReference):
    match_type:Literal['stock_code','stock_name','alias','ambiguous_group']

class CanonicalResolution(StrictPlanModel):
    status:Literal['resolved','ambiguous','not_found']
    reason:Literal['exact_match','multiple_stocks','conflicting_identifiers','ambiguous_alias','unknown_identifier','no_match']
    stock:StockReference|None
    candidates:list[StockOption]=Field(max_length=10)
    @model_validator(mode='after')
    def consistent(self):
        codes=[c.stock_code for c in self.candidates]
        if len(set(codes))!=len(codes):raise ValueError('Invalid canonical result')
        if self.status=='resolved':
            if self.stock is None or self.candidates or self.reason!='exact_match':raise ValueError('Invalid canonical result')
        elif self.status=='not_found':
            if self.stock is not None or self.candidates or self.reason!='no_match':raise ValueError('Invalid canonical result')
        elif self.stock is not None or self.reason not in {'multiple_stocks','conflicting_identifiers','ambiguous_alias','unknown_identifier'}:raise ValueError('Invalid canonical result')
        return self

def resolution_ref(query,resolution):
    value=resolution.model_dump(mode='json') if isinstance(resolution,CanonicalResolution) else resolution
    value={**value,'candidates':sorted(value['candidates'],key=lambda x:x['stock_code'])}
    return digest(canonical({'version':VERSION,'policy_version':POLICY,'query':query,'resolution':value}))

def selected_resolution(resolution,selected):
    if selected is None:return resolution
    if resolution.status!='ambiguous':raise ValueError('Invalid selection')
    item=next((c for c in resolution.candidates if c.stock_code==selected),None)
    if item is None:raise ValueError('Invalid selection')
    return CanonicalResolution(status='resolved',reason='exact_match',stock=StockReference(**item.model_dump(exclude={'match_type'})),candidates=[])

class PlanView(StrictPlanModel):
    version:Literal['supervisor.flow-plan.v1']
    policy_version:Literal['supervisor.flow-only.1']
    query_sha256:str=Field(pattern=r'^[0-9a-f]{64}$')
    requested_views:list[str]=Field(max_length=7)
    status:Literal['ready_for_confirmation','needs_stock_selection','selection_stale','not_found','needs_clarification','unsupported']
    reason:Literal['unsupported_views','clarify_intent','clarify_stock_scope','stock_resolved','stock_ambiguous','stock_not_found','selection_changed']
    resolution:CanonicalResolution|None
    candidate_ref:str|None=Field(pattern=r'^[0-9a-f]{64}$')
    @field_validator('requested_views')
    @classmethod
    def valid_views(cls,value):
        if len(set(value))!=len(value) or any(v not in VIEWS for v in value):raise ValueError('Invalid views')
        return value
    @model_validator(mode='after')
    def consistent(self):
        pairs={'ready_for_confirmation':'stock_resolved','needs_stock_selection':'stock_ambiguous','not_found':'stock_not_found','selection_stale':'selection_changed','unsupported':'unsupported_views'}
        if self.status in pairs and self.reason!=pairs[self.status]:raise ValueError('Invalid plan')
        if self.status=='needs_clarification' and self.reason not in {'clarify_intent','clarify_stock_scope'}:raise ValueError('Invalid plan')
        if self.status in {'unsupported','needs_clarification'}:
            if self.resolution is not None or self.candidate_ref is not None:raise ValueError('Invalid plan')
        else:
            if self.requested_views!=['flow'] or self.resolution is None or self.candidate_ref is None:raise ValueError('Invalid plan')
            wanted={'ready_for_confirmation':'resolved','needs_stock_selection':'ambiguous','selection_stale':'ambiguous','not_found':'not_found'}[self.status]
            if self.resolution.status!=wanted:raise ValueError('Invalid plan')
        return self

class PlanInput(StrictPlanModel):
    phase:Literal['start','continue']
    query:str=Field(min_length=1,max_length=300)
    request_id:str=Field(pattern=r'^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$')
    trace_id:str=Field(pattern=r'^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$')
    policy_version:Literal['supervisor.flow-only.1']
    query_sha256:str=Field(pattern=r'^[0-9a-f]{64}$')
    requested_views:list[str]|None=None
    resolution:CanonicalResolution|None=None
    selected_ticker:str|None=Field(default=None,pattern=r'^[0-9]{6}$')
    candidate_ref:str|None=Field(default=None,pattern=r'^[0-9a-f]{64}$')
    @model_validator(mode='after')
    def consistent(self):
        if not self.query.strip() or '\x00' in self.query or digest(self.query)!=self.query_sha256:raise ValueError('Invalid query')
        if self.phase=='start':
            if any(v is not None for v in (self.requested_views,self.resolution,self.selected_ticker,self.candidate_ref)):raise ValueError('Invalid phase')
        elif self.requested_views is None or self.resolution is None:raise ValueError('Invalid phase')
        if (self.selected_ticker is None)!=(self.candidate_ref is None):raise ValueError('Invalid selection')
        return self

class PlanWire(StrictPlanModel):
    version:Literal['supervisor.flow-plan.v1']
    policy_version:Literal['supervisor.flow-only.1']
    request_id:str
    trace_id:str
    query_sha256:str
    requested_views:list[str]
    kind:Literal['resolve_stock','final']
    plan:PlanView|None
    @model_validator(mode='after')
    def consistent(self):
        if self.kind=='resolve_stock':
            if self.plan is not None or self.requested_views!=['flow']:raise ValueError('Invalid tool')
        elif self.plan is None or self.plan.query_sha256!=self.query_sha256 or self.plan.requested_views!=self.requested_views:raise ValueError('Invalid final plan')
        return self
