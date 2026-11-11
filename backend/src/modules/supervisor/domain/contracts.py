"""Backend mirror of strict core contracts; never imports AI production modules."""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator
import hashlib
import json
import math
VERSION = 'supervisor.core.v1'
POLICY = 'supervisor.flow-core.1'
UUID_PATTERN = '^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$'
View = Literal['flow', 'technical', 'fundamental', 'macro', 'industry', 'news', 'overview']

class CoreCoreInvalid(ValueError):

    def __init__(self):
        super().__init__('Supervisor core contract invalid')

class CoreStrict(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, hide_input_in_errors=True)

def canonical(value):

    def check(v):
        if type(v) is dict:
            if any((type(k) is not str for k in v)):
                raise CoreCoreInvalid()
            for x in v.values():
                check(x)
        elif type(v) is list:
            for x in v:
                check(x)
        elif type(v) not in {str, int, float, bool, type(None)} or (type(v) is float and (not math.isfinite(v))):
            raise CoreCoreInvalid()
    try:
        check(value)
        return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise CoreCoreInvalid() from None

def sha(value):
    return hashlib.sha256(canonical(value).encode('utf8')).hexdigest()

def decode(raw):

    def pairs(items):
        v = {}
        for (k, x) in items:
            if k in v:
                raise CoreCoreInvalid()
            v[k] = x
        return v
    try:
        v = json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(CoreCoreInvalid()))
        canonical(v)
        return v
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise CoreCoreInvalid() from None

class CoreAnswer(CoreStrict):
    answer_id: str = Field(pattern=UUID_PATTERN)
    slot: Literal['stock', 'views', 'flow_focus', 'period', 'scope']
    value: str = Field(min_length=1, max_length=300)

    @field_validator('value')
    @classmethod
    def text(cls, v):
        if not v.strip() or '\x00' in v:
            raise CoreCoreInvalid()
        v.encode('utf8')
        return v

class CoreDraft(CoreStrict):
    original_query: str = Field(min_length=1, max_length=2000)
    answers: list[CoreAnswer] = Field(default_factory=list, max_length=8)
    revision: int = Field(ge=0, le=4)
    selected_ticker: str | None = Field(default=None, pattern='^[0-9]{6}$')
    candidate_ref: str | None = Field(default=None, pattern='^[0-9a-f]{64}$')

    @model_validator(mode='after')
    def valid(self):
        if not self.original_query.strip() or '\x00' in self.original_query or (self.selected_ticker is None) != (self.candidate_ref is None):
            raise CoreCoreInvalid()
        self.original_query.encode('utf8')
        if len({a.answer_id for a in self.answers}) != len(self.answers) or (self.revision == 0 and self.answers) or self.revision > len(self.answers):
            raise CoreCoreInvalid()
        return self

class CoreEvidence(CoreStrict):
    source_kind: Literal['original_query', 'clarification_answer']
    answer_id: str | None
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    text: str = Field(min_length=1)

class CoreMention(CoreStrict):
    text: str
    negated: bool
    evidence: CoreEvidence

class CoreCondition(CoreStrict):
    condition_id: str = Field(pattern='^[a-z0-9_.-]{1,64}$')
    domain: View
    kind: Literal['focus', 'exclude', 'period', 'cutoff', 'coverage', 'candle_unit', 'statement_basis', 'financial_period', 'years', 'unrecognized']
    value: str
    evidence: list[CoreEvidence] = Field(min_length=1, max_length=8)
    disposition: Literal['honored', 'unsupported', 'unresolved', 'waived_by_explicit_consent']

class CoreMeaningFrame(CoreStrict):
    original_query: str
    query_sha256: str = Field(pattern='^[0-9a-f]{64}$')
    revision: int = Field(ge=0, le=4)
    answers: list[CoreAnswer] = Field(max_length=8)
    mentions: list[CoreMention] = Field(max_length=8)
    requested_views: list[View] = Field(max_length=7)
    negated_views: list[View] = Field(max_length=7)
    conditions: list[CoreCondition] = Field(max_length=32)
    unresolved_slots: list[Literal['stock', 'views', 'meaning', 'multi_stock', 'scope']] = Field(max_length=5)
    interpretation_source: Literal['deterministic', 'model_assisted', 'unavailable']

    @model_validator(mode='after')
    def sources(self):
        if self.query_sha256 != sha(self.original_query) or len(set(self.requested_views)) != len(self.requested_views) or len(set(self.negated_views)) != len(self.negated_views) or set(self.requested_views) & set(self.negated_views):
            raise CoreCoreInvalid()
        if len({c.condition_id for c in self.conditions}) != len(self.conditions):
            raise CoreCoreInvalid()
        sources = {a.answer_id: a.value for a in self.answers}
        for e in [m.evidence for m in self.mentions] + [e for c in self.conditions for e in c.evidence]:
            text = self.original_query if e.source_kind == 'original_query' and e.answer_id is None else sources.get(e.answer_id) if e.source_kind == 'clarification_answer' else None
            if text is None or not 0 <= e.start < e.end <= len(text) or text[e.start:e.end] != e.text:
                raise CoreCoreInvalid()
        if any((m.text != m.evidence.text for m in self.mentions)):
            raise CoreCoreInvalid()
        return self
from typing import Literal, Generic, TypeVar
from pydantic import Field, field_validator, model_validator

class CoreStock(CoreStrict):
    stock_code: str = Field(pattern='^[0-9]{6}$')
    stock_name: str = Field(min_length=1, max_length=256)
    market: Literal['KOSPI', 'KOSDAQ', 'KONEX'] | None

    @field_validator('stock_name')
    @classmethod
    def name(cls, v):
        if not v.strip() or any((ord(c) < 32 or 127 <= ord(c) <= 159 for c in v)):
            raise CoreCoreInvalid()
        v.encode('utf8')
        return v

class CoreCandidate(CoreStock):
    match_type: Literal['stock_code', 'stock_name', 'alias', 'ambiguous_group']

class CoreResolution(CoreStrict):
    status: Literal['resolved', 'ambiguous', 'not_found']
    reason: str
    stock: CoreStock | None
    candidates: list[CoreCandidate] = Field(max_length=10)

    @model_validator(mode='after')
    def valid(self):
        if len({c.stock_code for c in self.candidates}) != len(self.candidates):
            raise CoreCoreInvalid()
        if self.status == 'resolved' and (self.stock is None or self.candidates or self.reason != 'exact_match'):
            raise CoreCoreInvalid()
        if self.status == 'not_found' and (self.stock is not None or self.candidates or self.reason != 'no_match'):
            raise CoreCoreInvalid()
        if self.status == 'ambiguous' and (self.stock is not None or self.reason not in {'multiple_stocks', 'conflicting_identifiers', 'ambiguous_alias', 'unknown_identifier'}):
            raise CoreCoreInvalid()
        return self

class CoreCapability(CoreStrict):
    view: View
    connected: bool
    reason: Literal['connected_flow', 'not_connected', 'news_excluded']

class CorePlan(CoreStrict):
    schema_version: Literal['supervisor.core.v1']
    policy_version: Literal['supervisor.flow-core.1', 'supervisor.flow-core.2']
    frame: CoreMeaningFrame
    resolution: CoreResolution | None
    candidate_ref: str | None = Field(pattern='^[0-9a-f]{64}$')
    requested_views: list[View]
    capabilities: list[CoreCapability]
    selected_views: list[Literal['flow']]
    status: Literal['needs_clarification', 'needs_stock_selection', 'selection_stale', 'not_found', 'scope_confirmation', 'ready', 'unsupported']
    partial: bool
    required_waivers: list[str]
    plan_hash: str = Field(pattern='^[0-9a-f]{64}$')

class CoreConsent(CoreStrict):
    allow_flow: Literal[True]
    allow_partial: bool
    waived_conditions: list[str] = Field(max_length=32)

class CoreConfirm(CoreStrict):
    client_key: str = Field(pattern=UUID_PATTERN)
    draft: CoreDraft
    expected_plan_hash: str = Field(pattern='^[0-9a-f]{64}$')
    consent: CoreConsent
    preparation_id: str | None = Field(default=None, pattern=UUID_PATTERN)

class CoreViewOutcome(CoreStrict):
    view: View
    state: Literal['not_executed', 'not_admitted', 'running', 'result_ready', 'stored', 'failed', 'unknown', 'deleted']
    reason: Literal['not_connected', 'awaiting_admission', 'flow_state', 'deleted']

class CoreFlowReference(CoreStrict):
    analysis_id: str = Field(pattern=UUID_PATTERN)
    admission_request_id: str = Field(pattern=UUID_PATTERN)
    attempt_id: str | None
    state: Literal['running', 'result_ready', 'stored', 'failed', 'unknown']
    deadline_at: str
    report_id: str | None
    report_url: str | None
    error: dict | None

class CoreEffectiveScope(CoreStrict):
    selected_views: list[Literal['flow']]
    fixed_observation_window: Literal[True]
    all_subjects_retained: Literal[True]
    waived_conditions: list[str]
    partial_consent: bool

class CoreOutcome(CoreStrict):
    supervisor_id: str = Field(pattern=UUID_PATTERN)
    plan: CorePlan | None
    plan_status: Literal['confirmed', 'deleted']
    effective_scope: CoreEffectiveScope | None
    views: list[CoreViewOutcome]
    coverage: Literal['pending', 'partial', 'fulfilled', 'unfulfilled', 'deleted']
    flow: CoreFlowReference | None

class CoreSafeError(CoreStrict):
    code: Literal['INPUT_INVALID', 'AUTH_REQUIRED', 'AUTH_REQUEST_INVALID', 'FEATURE_UNAVAILABLE', 'SERVICE_UNAVAILABLE', 'DEADLINE_EXCEEDED', 'RESULT_CONTRACT_INVALID', 'PLAN_STALE', 'IDEMPOTENCY_CONFLICT', 'RESOURCE_NOT_FOUND', 'HANDOFF_EXPIRED', 'USAGE_LIMIT_EXCEEDED', 'PREPARATION_EXPIRED', 'PREPARATION_DELETED', 'PREPARATION_CONSUMED', 'MEANING_LIMIT_EXCEEDED']
    message: Literal['Supervisor request unavailable'] = 'Supervisor request unavailable'
T = TypeVar('T')

class CoreEnvelope(CoreStrict, Generic[T]):
    schema_version: Literal['supervisor.core.v1']
    request_id: str = Field(pattern=UUID_PATTERN)
    trace_id: str = Field(pattern=UUID_PATTERN)
    data: T | None
    error: CoreSafeError | None

    @model_validator(mode='after')
    def exclusive(self):
        if (self.data is None) == (self.error is None):
            raise CoreCoreInvalid()
        return self

class CoreInternalInput(CoreStrict):
    phase: Literal['start', 'continue']
    draft: CoreDraft
    frame: CoreMeaningFrame | None = None
    resolution: CoreResolution | None = None

class CoreInternalOutput(CoreStrict):
    action: Literal['clarify', 'resolve_stock', 'final']
    frame: CoreMeaningFrame
    lookup: str | None
    plan: CorePlan | None

def semantic_plan_hash(value):
    return sha({k: v for (k, v) in value.items() if k != 'plan_hash'})

def candidate_ref(draft, resolution, *, policy_version=POLICY):
    value = resolution.model_dump(mode='json') if isinstance(resolution, CoreResolution) else resolution
    value = {**value, 'candidates': sorted(value['candidates'], key=lambda c: c['stock_code'])}
    return sha(dict(policy=policy_version, draft=draft.model_dump(mode='json', exclude={'selected_ticker', 'candidate_ref'}), resolution=value))

def validate_plan(value, draft):
    plan = CorePlan.model_validate(value)
    if plan.frame.original_query != draft.original_query or plan.frame.answers != draft.answers or plan.frame.revision != draft.revision or (semantic_plan_hash(value) != plan.plan_hash) or (plan.requested_views != plan.frame.requested_views):
        raise CoreCoreInvalid()
    return plan

class CoreMeaningRunInput(CoreInternalInput):
    policy_version: Literal['supervisor.flow-core.2']
    attempt_id: str | None = Field(default=None, pattern=UUID_PATTERN)

class CoreMeaningRunOutput(CoreInternalOutput):
    meaning_status: Literal['deterministic', 'supplemented', 'unavailable', 'rejected', 'incomplete', 'unsupported', 'counter_unavailable']
    semantic_spec_sha256: str = Field(pattern='^[0-9a-f]{64}$')
CoreInvalid=CoreCoreInvalid
Strict=CoreStrict
Answer=CoreAnswer
Draft=CoreDraft
Evidence=CoreEvidence
Mention=CoreMention
Condition=CoreCondition
MeaningFrame=CoreMeaningFrame
Stock=CoreStock
Candidate=CoreCandidate
Resolution=CoreResolution
Capability=CoreCapability
Plan=CorePlan
Consent=CoreConsent
Confirm=CoreConfirm
ViewOutcome=CoreViewOutcome
FlowReference=CoreFlowReference
EffectiveScope=CoreEffectiveScope
Outcome=CoreOutcome
SafeError=CoreSafeError
Envelope=CoreEnvelope
InternalInput=CoreInternalInput
InternalOutput=CoreInternalOutput
MeaningRunInput=CoreMeaningRunInput
MeaningRunOutput=CoreMeaningRunOutput

MEANING_SPEC={'version': 'supervisor.meaning.v1', 'policy': 'supervisor.flow-core.2', 'model': 'gpt-5.4-mini-2026-03-17', 'price': {'id': 'openai.gpt-5.4-mini.standard.2026-11-10.v1', 'currency': 'USD', 'input_nano_per_token': 750, 'cached_nano_per_token': 75, 'output_nano_per_token': 4500}, 'caps': {'input_tokens': 16384, 'output_tokens': 2048, 'attempts': 2, 'count_requests': 2, 'generation_requests': 2, 'attempt_reserve_nano': 50000000, 'unit_budget_nano': 100000000, 'request_bytes': 65536, 'count_response_bytes': 8192, 'response_bytes': 65536, 'candidate_bytes': 16384, 'provider_seconds': 55, 'verifier_seconds': 60}, 'service_tier': 'default', 'store': False, 'prompt_sha256': '0456f2afc6939b45a61c6d59159bd42a8e807647c656b15fb7ed23a0bf7714c4', 'schema_sha256': '1a3a394f965270af18a4cb5e1b46f3e99a37a6c770970d1c8d09fc1bc211dbb1'}
MEANING_SPEC_SHA256='8a873009b7bf71f78b90efbf495ecd920ea12a8027f0ad629b5a530759f3c943'


class CorePreparationRequest(CoreStrict):
    prepare_key: str = Field(pattern=UUID_PATTERN)
    draft: CoreDraft
    parent_preparation_id: str | None = Field(default=None, pattern=UUID_PATTERN)

    @model_validator(mode='after')
    def selection(self):
        if (self.parent_preparation_id is None) != (self.draft.selected_ticker is None):
            raise CoreInvalid()
        return self


class CorePreparationView(CoreStrict):
    preparation_id: str = Field(pattern=UUID_PATTERN)
    state: Literal['pending','ready','clarification','unsupported','failed','unknown','expired','deleted','consumed']
    plan: CorePlan | None
    created_at: str
    expires_at: str
    meaning_status: Literal['pending','deterministic','supplemented','unavailable','rejected','incomplete','unsupported','counter_unavailable','failed','unknown','expired','deleted','consumed']
    consumed_binding_id: str | None = Field(default=None, pattern=UUID_PATTERN)

    @model_validator(mode='after')
    def sensitive(self):
        if (self.state in {'ready','clarification','unsupported'}) != (self.plan is not None):
            raise CoreInvalid()
        if self.state != 'consumed' and self.consumed_binding_id is not None:
            raise CoreInvalid()
        return self


PreparationRequest = CorePreparationRequest
PreparationView = CorePreparationView
