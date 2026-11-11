"""Evidence proposals only. No canonical stock, capability, owner or execution grant."""
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from pydantic import Field, model_validator
from src.supervisor.domain.meaning import CoreInvalid, Evidence, Strict, View, sha

POLICY = 'supervisor.flow-core.2'
MODEL = 'gpt-5.4-mini-2026-03-17'
PRICE = {'id': 'openai.gpt-5.4-mini.standard.2026-11-10.v1', 'currency': 'USD',
         'input_nano_per_token': 750, 'cached_nano_per_token': 75, 'output_nano_per_token': 4500}
CAPS = {'input_tokens': 16384, 'output_tokens': 2048, 'attempts': 2,
        'count_requests': 2, 'generation_requests': 2, 'attempt_reserve_nano': 50000000,
        'unit_budget_nano': 100000000, 'request_bytes': 65536, 'count_response_bytes': 8192,
        'response_bytes': 65536, 'candidate_bytes': 16384, 'provider_seconds': 55, 'verifier_seconds': 60}

CANDIDATE_SCHEMA = {'type': 'object', 'additionalProperties': False, 'properties': {'schema_version': {'type': 'string', 'enum': ['supervisor.meaning.v1']}, 'mentions': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False, 'properties': {'evidence': {'type': 'object', 'additionalProperties': False, 'properties': {'source_kind': {'type': 'string', 'enum': ['original_query', 'clarification_answer']}, 'answer_id': {'type': ['string', 'null']}, 'start': {'type': 'integer', 'minimum': 0}, 'end': {'type': 'integer', 'minimum': 1}, 'text': {'type': 'string', 'minLength': 1}}, 'required': ['source_kind', 'answer_id', 'start', 'end', 'text']}, 'negation': {'anyOf': [{'type': 'object', 'additionalProperties': False, 'properties': {'source_kind': {'type': 'string', 'enum': ['original_query', 'clarification_answer']}, 'answer_id': {'type': ['string', 'null']}, 'start': {'type': 'integer', 'minimum': 0}, 'end': {'type': 'integer', 'minimum': 1}, 'text': {'type': 'string', 'minLength': 1}}, 'required': ['source_kind', 'answer_id', 'start', 'end', 'text']}, {'type': 'null'}]}}, 'required': ['evidence', 'negation']}, 'maxItems': 8}, 'views': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False, 'properties': {'view': {'type': 'string', 'enum': ['flow', 'technical', 'fundamental', 'macro', 'industry', 'news', 'overview']}, 'evidence': {'type': 'object', 'additionalProperties': False, 'properties': {'source_kind': {'type': 'string', 'enum': ['original_query', 'clarification_answer']}, 'answer_id': {'type': ['string', 'null']}, 'start': {'type': 'integer', 'minimum': 0}, 'end': {'type': 'integer', 'minimum': 1}, 'text': {'type': 'string', 'minLength': 1}}, 'required': ['source_kind', 'answer_id', 'start', 'end', 'text']}, 'negation': {'anyOf': [{'type': 'object', 'additionalProperties': False, 'properties': {'source_kind': {'type': 'string', 'enum': ['original_query', 'clarification_answer']}, 'answer_id': {'type': ['string', 'null']}, 'start': {'type': 'integer', 'minimum': 0}, 'end': {'type': 'integer', 'minimum': 1}, 'text': {'type': 'string', 'minLength': 1}}, 'required': ['source_kind', 'answer_id', 'start', 'end', 'text']}, {'type': 'null'}]}}, 'required': ['view', 'evidence', 'negation']}, 'maxItems': 14}, 'conditions': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False, 'properties': {'domain': {'type': 'string', 'enum': ['flow', 'technical', 'fundamental', 'macro', 'industry', 'news', 'overview']}, 'kind': {'type': 'string', 'enum': ['focus', 'exclude', 'period', 'cutoff', 'coverage', 'candle_unit', 'statement_basis', 'financial_period', 'years', 'unrecognized']}, 'value': {'type': 'string', 'minLength': 1, 'maxLength': 300}, 'evidence': {'type': 'object', 'additionalProperties': False, 'properties': {'source_kind': {'type': 'string', 'enum': ['original_query', 'clarification_answer']}, 'answer_id': {'type': ['string', 'null']}, 'start': {'type': 'integer', 'minimum': 0}, 'end': {'type': 'integer', 'minimum': 1}, 'text': {'type': 'string', 'minLength': 1}}, 'required': ['source_kind', 'answer_id', 'start', 'end', 'text']}, 'negation': {'anyOf': [{'type': 'object', 'additionalProperties': False, 'properties': {'source_kind': {'type': 'string', 'enum': ['original_query', 'clarification_answer']}, 'answer_id': {'type': ['string', 'null']}, 'start': {'type': 'integer', 'minimum': 0}, 'end': {'type': 'integer', 'minimum': 1}, 'text': {'type': 'string', 'minLength': 1}}, 'required': ['source_kind', 'answer_id', 'start', 'end', 'text']}, {'type': 'null'}]}}, 'required': ['domain', 'kind', 'value', 'evidence', 'negation']}, 'maxItems': 32}}, 'required': ['schema_version', 'mentions', 'views', 'conditions']}

class MentionProposal(Strict):
    evidence: Evidence
    negation: Evidence | None


class ViewProposal(Strict):
    view: View
    evidence: Evidence
    negation: Evidence | None


class ConditionProposal(Strict):
    domain: View
    kind: Literal['focus', 'exclude', 'period', 'cutoff', 'coverage', 'candle_unit', 'statement_basis', 'financial_period', 'years', 'unrecognized']
    value: str = Field(min_length=1, max_length=300)
    evidence: Evidence
    negation: Evidence | None


class MeaningProposal(Strict):
    schema_version: Literal['supervisor.meaning.v1']
    mentions: list[MentionProposal] = Field(max_length=8)
    views: list[ViewProposal] = Field(max_length=14)
    conditions: list[ConditionProposal] = Field(max_length=32)

    @model_validator(mode='after')
    def no_duplicate(self):
        for values in (self.mentions, self.views, self.conditions):
            if len({sha(v.model_dump(mode='json')) for v in values}) != len(values):
                raise CoreInvalid()
        return self


def semantic_spec():
    import hashlib
    prompt = Path(__file__).resolve().parents[1] / 'prompts/meaning.txt'
    raw = prompt.read_bytes()
    return {'version': 'supervisor.meaning.v1', 'policy': POLICY, 'model': MODEL,
            'price': PRICE, 'caps': CAPS, 'service_tier': 'default', 'store': False,
            'prompt_sha256': hashlib.sha256(raw).hexdigest(),
            'schema_sha256': sha(CANDIDATE_SCHEMA)}


@dataclass(frozen=True)
class InputTokenEvidence:
    request_sha256: str
    projection_sha256: str
    input_tokens: int
    model: str
    price_sha256: str
    mapping_sha256: str
    count_fee_bound_nano: int
