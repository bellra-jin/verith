"""Closed deterministic Technical planning and consent contract; no execution authority."""
from typing import Generic, Literal, TypeVar
from pydantic import Field, model_validator, field_validator
from src.modules.supervisor.domain.contracts import Strict, Draft, MeaningFrame, Resolution, CoreInvalid, UUID_PATTERN, candidate_ref as core_candidate_ref, sha, canonical, decode

VERSION='supervisor.technical.v1'
POLICY='supervisor.technical-core.1'
SPEC_SHA256='b526fffe2e3c2ccce4c2c6a75f259bb61d82349ae2ceda16347b7b20f3d21e88'
HASH='^[0-9a-f]{64}$'
class TechnicalContext(Strict):
    configuration_sha256: str=Field(pattern=HASH)
    policy_sha256: str=Field(pattern=HASH)
    spec_sha256: Literal['b526fffe2e3c2ccce4c2c6a75f259bb61d82349ae2ceda16347b7b20f3d21e88']
    reserved_nano: int=Field(gt=0,le=9223372036854775807)
class TechnicalProfile(Strict):
    profile: Literal['technical.multiframe.v1']='technical.multiframe.v1'
    periods: list[Literal['3m','1y','5y']]=Field(default_factory=lambda:['3m','1y','5y'])
    cutoff: Literal['unverified']='unverified'
    source_as_of: None=None
    intraday: Literal['unavailable']='unavailable'
    @model_validator(mode='after')
    def fixed(self):
        if self.periods!=['3m','1y','5y']:raise CoreInvalid()
        return self
class TechnicalPlan(Strict):
    schema_version: Literal['supervisor.technical.v1']
    policy_version: Literal['supervisor.technical-core.1']
    context: TechnicalContext
    frame: MeaningFrame
    resolution: Resolution|None
    candidate_ref: str|None=Field(pattern=HASH)
    requested_views: list[str]
    selected_views: list[Literal['technical']]
    support: TechnicalProfile
    execution_query: str|None
    status: Literal['needs_clarification','unsupported','needs_stock_selection','not_found','selection_stale','scope_confirmation','ready']
    partial: bool
    required_waivers: list[str]=Field(max_length=32)
    plan_hash: str=Field(pattern=HASH)
    @model_validator(mode='after')
    def checked(self):
        data=self.model_dump(mode='json');data.pop('plan_hash')
        waivers=[c.condition_id for c in self.frame.conditions if c.disposition!='honored']
        if (sha(data)!=self.plan_hash or self.requested_views!=self.frame.requested_views
                or self.required_waivers!=waivers or self.partial!=bool(waivers)
                or self.selected_views not in ([],['technical'])):raise CoreInvalid()
        if self.selected_views:
            if (self.frame.unresolved_slots or self.requested_views!=['technical']
                    or 'technical' in self.frame.negated_views or self.resolution is None
                    or self.resolution.status!='resolved'
                    or any(c.kind=='unrecognized' for c in self.frame.conditions)
                    or self.execution_query!=self.resolution.stock.stock_code+' 차트'
                    or self.status!=('scope_confirmation' if waivers else 'ready')):raise CoreInvalid()
        elif self.status in {'ready','scope_confirmation'} or self.execution_query is not None:raise CoreInvalid()
        return self
class TechnicalConsent(Strict):
    allow_technical: Literal[True]
    allow_partial: bool
    waived_conditions: list[str]=Field(max_length=32)
    @field_validator('allow_technical',mode='before')
    @classmethod
    def explicit(cls,value):
        if type(value) is not bool or value is not True:raise CoreInvalid()
        return value
class TechnicalConfirm(Strict):
    client_key: str=Field(pattern=UUID_PATTERN)
    draft: Draft
    expected_plan_hash: str=Field(pattern=HASH)
    consent: TechnicalConsent
class TechnicalInternalInput(Strict):
    phase: Literal['start','continue']
    draft: Draft
    context: TechnicalContext
    frame: MeaningFrame|None=None
    resolution: Resolution|None=None
    @model_validator(mode='after')
    def phase_fields(self):
        if (self.phase=='continue')!=(self.frame is not None and self.resolution is not None):raise CoreInvalid()
        if self.phase=='start' and (self.frame is not None or self.resolution is not None):raise CoreInvalid()
        return self
class TechnicalInternalOutput(Strict):
    action: Literal['clarify','resolve_stock','final']
    frame: MeaningFrame
    lookup: str|None
    plan: TechnicalPlan|None
class TechnicalReference(Strict):
    analysis_id: str=Field(pattern=UUID_PATTERN)
    admission_request_id: str=Field(pattern=UUID_PATTERN)
    attempt_id: str=Field(pattern=UUID_PATTERN)
    report_id: str|None=Field(pattern=UUID_PATTERN)
    report_url: None=None
    state: Literal['admitted','claimed','result_ready','stored','failed','unknown']
    as_of: str
    deadline_at: str
    reserved_nano: int=Field(gt=0)
    held_nano: int=Field(gt=0)
class TechnicalEffectiveScope(Strict):
    selected_views: list[Literal['technical']]
    profile: TechnicalProfile
    execution_query: str
    waived_conditions: list[str]
    partial_consent: bool
class TechnicalOutcome(Strict):
    supervisor_id: str=Field(pattern=UUID_PATTERN)
    plan: TechnicalPlan|None
    effective_scope: TechnicalEffectiveScope|None
    technical: TechnicalReference|None
    coverage: Literal['pending','fulfilled','partial','unfulfilled','deleted']
class TechnicalSafeError(Strict):
    code: Literal['INPUT_INVALID','AUTH_REQUIRED','AUTH_REQUEST_INVALID','FEATURE_UNAVAILABLE','SERVICE_UNAVAILABLE','DEADLINE_EXCEEDED','RESULT_CONTRACT_INVALID','PLAN_STALE','IDEMPOTENCY_CONFLICT','RESOURCE_NOT_FOUND','HANDOFF_EXPIRED','USAGE_LIMIT_EXCEEDED']
    message: Literal['Supervisor request unavailable']
T=TypeVar('T')
class TechnicalEnvelope(Strict,Generic[T]):
    schema_version: Literal['supervisor.technical.v1']
    request_id: str=Field(pattern=UUID_PATTERN)
    trace_id: str=Field(pattern=UUID_PATTERN)
    data: T|None
    error: TechnicalSafeError|None
    @model_validator(mode='after')
    def exclusive(self):
        if (self.data is None)==(self.error is None):raise CoreInvalid()
        return self

def candidate_ref(draft,resolution):
    return core_candidate_ref(draft,resolution,policy_version=POLICY)

def validate_plan(value,draft,context):
    plan=TechnicalPlan.model_validate(value)
    if (plan.context!=context or plan.frame.original_query!=draft.original_query
            or plan.frame.answers!=draft.answers or plan.frame.revision!=draft.revision
            or plan.frame.interpretation_source!='deterministic'):raise CoreInvalid()
    return plan

Context=TechnicalContext
Profile=TechnicalProfile
Plan=TechnicalPlan
Consent=TechnicalConsent
Confirm=TechnicalConfirm
InternalInput=TechnicalInternalInput
InternalOutput=TechnicalInternalOutput
Reference=TechnicalReference
EffectiveScope=TechnicalEffectiveScope
Outcome=TechnicalOutcome
SafeError=TechnicalSafeError
Envelope=TechnicalEnvelope
