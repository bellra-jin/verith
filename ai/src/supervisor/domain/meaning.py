"""Pure bounded semantic input and source evidence; no provider dependencies."""
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

class CoreInvalid(ValueError):

    def __init__(self):
        super().__init__('Supervisor core contract invalid')

class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, hide_input_in_errors=True)

def canonical(value):

    def check(v):
        if type(v) is dict:
            if any((type(k) is not str for k in v)):
                raise CoreInvalid()
            for x in v.values():
                check(x)
        elif type(v) is list:
            for x in v:
                check(x)
        elif type(v) not in {str, int, float, bool, type(None)} or (type(v) is float and (not math.isfinite(v))):
            raise CoreInvalid()
    try:
        check(value)
        return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise CoreInvalid() from None

def sha(value):
    return hashlib.sha256(canonical(value).encode('utf8')).hexdigest()

def decode(raw):

    def pairs(items):
        v = {}
        for (k, x) in items:
            if k in v:
                raise CoreInvalid()
            v[k] = x
        return v
    try:
        v = json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(CoreInvalid()))
        canonical(v)
        return v
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise CoreInvalid() from None

class Answer(Strict):
    answer_id: str = Field(pattern=UUID_PATTERN)
    slot: Literal['stock', 'views', 'flow_focus', 'period', 'scope']
    value: str = Field(min_length=1, max_length=300)

    @field_validator('value')
    @classmethod
    def text(cls, v):
        if not v.strip() or '\x00' in v:
            raise CoreInvalid()
        v.encode('utf8')
        return v

class Draft(Strict):
    original_query: str = Field(min_length=1, max_length=2000)
    answers: list[Answer] = Field(default_factory=list, max_length=8)
    revision: int = Field(ge=0, le=4)
    selected_ticker: str | None = Field(default=None, pattern='^[0-9]{6}$')
    candidate_ref: str | None = Field(default=None, pattern='^[0-9a-f]{64}$')

    @model_validator(mode='after')
    def valid(self):
        if not self.original_query.strip() or '\x00' in self.original_query or (self.selected_ticker is None) != (self.candidate_ref is None):
            raise CoreInvalid()
        self.original_query.encode('utf8')
        if len({a.answer_id for a in self.answers}) != len(self.answers) or (self.revision == 0 and self.answers) or self.revision > len(self.answers):
            raise CoreInvalid()
        return self

class Evidence(Strict):
    source_kind: Literal['original_query', 'clarification_answer']
    answer_id: str | None
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    text: str = Field(min_length=1)

class Mention(Strict):
    text: str
    negated: bool
    evidence: Evidence

class Condition(Strict):
    condition_id: str = Field(pattern='^[a-z0-9_.-]{1,64}$')
    domain: View
    kind: Literal['focus', 'exclude', 'period', 'cutoff', 'coverage', 'candle_unit', 'statement_basis', 'financial_period', 'years', 'unrecognized']
    value: str
    evidence: list[Evidence] = Field(min_length=1, max_length=8)
    disposition: Literal['honored', 'unsupported', 'unresolved', 'waived_by_explicit_consent']

class MeaningFrame(Strict):
    original_query: str
    query_sha256: str = Field(pattern='^[0-9a-f]{64}$')
    revision: int = Field(ge=0, le=4)
    answers: list[Answer] = Field(max_length=8)
    mentions: list[Mention] = Field(max_length=8)
    requested_views: list[View] = Field(max_length=7)
    negated_views: list[View] = Field(max_length=7)
    conditions: list[Condition] = Field(max_length=32)
    unresolved_slots: list[Literal['stock', 'views', 'meaning', 'multi_stock', 'scope']] = Field(max_length=5)
    interpretation_source: Literal['deterministic', 'model_assisted', 'unavailable']

    @model_validator(mode='after')
    def sources(self):
        if self.query_sha256 != sha(self.original_query) or len(set(self.requested_views)) != len(self.requested_views) or len(set(self.negated_views)) != len(self.negated_views) or set(self.requested_views) & set(self.negated_views):
            raise CoreInvalid()
        if len({c.condition_id for c in self.conditions}) != len(self.conditions):
            raise CoreInvalid()
        sources = {a.answer_id: a.value for a in self.answers}
        for e in [m.evidence for m in self.mentions] + [e for c in self.conditions for e in c.evidence]:
            text = self.original_query if e.source_kind == 'original_query' and e.answer_id is None else sources.get(e.answer_id) if e.source_kind == 'clarification_answer' else None
            if text is None or text[e.start:e.end] != e.text:
                raise CoreInvalid()
        if any((m.text != m.evidence.text for m in self.mentions)):
            raise CoreInvalid()
        return self
