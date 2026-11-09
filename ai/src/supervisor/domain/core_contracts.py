"""Common MeaningFrame, typed Plan and observation Outcome."""
from typing import Literal, Generic, TypeVar
from pydantic import Field, field_validator, model_validator
from src.supervisor.domain.meaning import (
    CoreInvalid, Draft, MeaningFrame, POLICY, Strict, UUID_PATTERN, VERSION,
    View, canonical, decode, sha,
)

class Stock(Strict):
    stock_code: str = Field(pattern='^[0-9]{6}$')
    stock_name: str = Field(min_length=1, max_length=256)
    market: Literal['KOSPI', 'KOSDAQ', 'KONEX'] | None

    @field_validator('stock_name')
    @classmethod
    def name(cls, v):
        if not v.strip() or any((ord(c) < 32 or 127 <= ord(c) <= 159 for c in v)):
            raise CoreInvalid()
        v.encode('utf8')
        return v

class Candidate(Stock):
    match_type: Literal['stock_code', 'stock_name', 'alias', 'ambiguous_group']

class Resolution(Strict):
    status: Literal['resolved', 'ambiguous', 'not_found']
    reason: str
    stock: Stock | None
    candidates: list[Candidate] = Field(max_length=10)

    @model_validator(mode='after')
    def valid(self):
        if len({c.stock_code for c in self.candidates}) != len(self.candidates):
            raise CoreInvalid()
        if self.status == 'resolved' and (self.stock is None or self.candidates or self.reason != 'exact_match'):
            raise CoreInvalid()
        if self.status == 'not_found' and (self.stock is not None or self.candidates or self.reason != 'no_match'):
            raise CoreInvalid()
        if self.status == 'ambiguous' and (self.stock is not None or self.reason not in {'multiple_stocks', 'conflicting_identifiers', 'ambiguous_alias', 'unknown_identifier'}):
            raise CoreInvalid()
        return self

class Capability(Strict):
    view: View
    connected: bool
    reason: Literal['connected_flow', 'not_connected', 'news_excluded']

class Plan(Strict):
    schema_version: Literal['supervisor.core.v1']
    policy_version: Literal['supervisor.flow-core.1', 'supervisor.flow-core.2']
    frame: MeaningFrame
    resolution: Resolution | None
    candidate_ref: str | None = Field(pattern='^[0-9a-f]{64}$')
    requested_views: list[View]
    capabilities: list[Capability]
    selected_views: list[Literal['flow']]
    status: Literal['needs_clarification', 'needs_stock_selection', 'selection_stale', 'not_found', 'scope_confirmation', 'ready', 'unsupported']
    partial: bool
    required_waivers: list[str]
    plan_hash: str = Field(pattern='^[0-9a-f]{64}$')

class Consent(Strict):
    allow_flow: Literal[True]
    allow_partial: bool
    waived_conditions: list[str] = Field(max_length=32)

class Confirm(Strict):
    client_key: str = Field(pattern=UUID_PATTERN)
    draft: Draft
    expected_plan_hash: str = Field(pattern='^[0-9a-f]{64}$')
    consent: Consent

class ViewOutcome(Strict):
    view: View
    state: Literal['not_executed', 'not_admitted', 'running', 'result_ready', 'stored', 'failed', 'unknown', 'deleted']
    reason: Literal['not_connected', 'awaiting_admission', 'flow_state', 'deleted']

class FlowReference(Strict):
    analysis_id: str = Field(pattern=UUID_PATTERN)
    admission_request_id: str = Field(pattern=UUID_PATTERN)
    attempt_id: str | None
    state: Literal['running', 'result_ready', 'stored', 'failed', 'unknown']
    deadline_at: str
    report_id: str | None
    report_url: str | None
    error: dict | None

class EffectiveScope(Strict):
    selected_views: list[Literal['flow']]
    fixed_observation_window: Literal[True]
    all_subjects_retained: Literal[True]
    waived_conditions: list[str]
    partial_consent: bool

class Outcome(Strict):
    supervisor_id: str = Field(pattern=UUID_PATTERN)
    plan: Plan | None
    plan_status: Literal['confirmed', 'deleted']
    effective_scope: EffectiveScope | None
    views: list[ViewOutcome]
    coverage: Literal['pending', 'partial', 'fulfilled', 'unfulfilled', 'deleted']
    flow: FlowReference | None

class SafeError(Strict):
    code: Literal['INPUT_INVALID', 'AUTH_REQUIRED', 'AUTH_REQUEST_INVALID', 'FEATURE_UNAVAILABLE', 'SERVICE_UNAVAILABLE', 'DEADLINE_EXCEEDED', 'RESULT_CONTRACT_INVALID', 'PLAN_STALE', 'IDEMPOTENCY_CONFLICT', 'RESOURCE_NOT_FOUND', 'HANDOFF_EXPIRED', 'USAGE_LIMIT_EXCEEDED']
    message: Literal['Supervisor request unavailable'] = 'Supervisor request unavailable'
T = TypeVar('T')

class Envelope(Strict, Generic[T]):
    schema_version: Literal['supervisor.core.v1']
    request_id: str = Field(pattern=UUID_PATTERN)
    trace_id: str = Field(pattern=UUID_PATTERN)
    data: T | None
    error: SafeError | None

    @model_validator(mode='after')
    def exclusive(self):
        if (self.data is None) == (self.error is None):
            raise CoreInvalid()
        return self

class InternalInput(Strict):
    phase: Literal['start', 'continue']
    draft: Draft
    frame: MeaningFrame | None = None
    resolution: Resolution | None = None

class InternalOutput(Strict):
    action: Literal['clarify', 'resolve_stock', 'final']
    frame: MeaningFrame
    lookup: str | None
    plan: Plan | None

def semantic_plan_hash(value):
    return sha({k: v for (k, v) in value.items() if k != 'plan_hash'})

def candidate_ref(draft, resolution, *, policy_version=POLICY):
    value = resolution.model_dump(mode='json') if isinstance(resolution, Resolution) else resolution
    value = {**value, 'candidates': sorted(value['candidates'], key=lambda c: c['stock_code'])}
    return sha(dict(policy=policy_version, draft=draft.model_dump(mode='json', exclude={'selected_ticker', 'candidate_ref'}), resolution=value))

def validate_plan(value, draft):
    plan = Plan.model_validate(value)
    if plan.frame.original_query != draft.original_query or plan.frame.answers != draft.answers or plan.frame.revision != draft.revision or (semantic_plan_hash(value) != plan.plan_hash) or (plan.requested_views != plan.frame.requested_views):
        raise CoreInvalid()
    return plan


class MeaningRunInput(InternalInput):
    policy_version: Literal['supervisor.flow-core.2']
    attempt_id: str | None = Field(default=None, pattern=UUID_PATTERN)


class MeaningRunOutput(InternalOutput):
    meaning_status: Literal['deterministic', 'supplemented', 'unavailable', 'rejected', 'incomplete', 'unsupported', 'counter_unavailable']
    semantic_spec_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
