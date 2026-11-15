"""Read bounded producer observations from an existing verified result snapshot.

This cannot construct authoritative expectations from AI IDs or grant trust.
No aggregate amount/tokens, additional persistence, receipt authority or I/O.
"""
from dataclasses import dataclass
import re
from uuid import UUID
from src.modules.analysis.domain.contracts import (
    AnalysisContext, FrozenAnalysisResult, AnalysisContractError,
    canonical_json, strict_json, json_hash,
)
from .usage_evidence import UsageEvidenceInvalid, _uid, _digest, _integer, _document

FIELDS = frozenset({'call_id', 'parent_call_id', 'stage', 'attempt_kind', 'provider',
    'model', 'service_tier', 'response_model', 'requested_service_tier',
    'request_sha256', 'policy_sha256', 'outcome', 'input_tokens', 'cached_tokens',
    'output_tokens', 'total_tokens'})
TOKENS = ('input_tokens', 'cached_tokens', 'output_tokens', 'total_tokens')
BASE_REASONS = ('CALL_INVENTORY_UNPROVEN', 'PROVENANCE_UNPROVEN', 'POLICY_UNBOUND', 'CALL_EXECUTION_IDENTITY_UNPROVEN')


@dataclass(frozen=True, slots=True, repr=False)
class UsageObservation:
    context: AnalysisContext
    report_id: UUID
    source_binding_sha256: str
    source_result_sha256: str
    calls_json: str
    state: str
    reasons: tuple[str, ...]

    @property
    def keep_reservation(self):
        return True

    @property
    def fingerprint(self):
        return json_hash(canonical_json(dict(source_binding_sha256=self.source_binding_sha256,
            source_result_sha256=self.source_result_sha256, calls=strict_json(self.calls_json),
            state=self.state, reasons=list(self.reasons))))


def observe_snapshot(frozen):
    """Caller must first enforce current owner/session/root/index validation.

    Source binding locates where claims were stored; it does NOT prove that the
    producer's individual calls actually belong to that execution.
    """
    if type(frozen) is not FrozenAnalysisResult:
        raise AnalysisContractError()
    frozen.validate()
    if (frozen.context.operation != 'fundamental.analysis.v1'
            or frozen.input_schema != 'fundamental.request-context.v1'
            or frozen.result_schema != 'fundamental.agent-output.v1'):
        raise AnalysisContractError()
    observations = {}
    reasons = set(BASE_REASONS)

    def result(state, extra=()):
        rows = [strict_json(raw) for identity in sorted(observations) for raw in sorted(observations[identity])]
        return UsageObservation(frozen.context, frozen.report_id, frozen.binding_sha256,
            frozen.result_sha256, canonical_json(rows), state, tuple(sorted(reasons | set(extra))))

    try:
        raw = strict_json(frozen.result_json)
        if type(raw.get('meta')) is not dict:
            raise UsageEvidenceInvalid()
        value = raw['meta'].get('call_usage')
        if value is None:
            return result('unknown', ('OBSERVATION_MISSING',))
        value = _document(canonical_json(value))
        if (type(value) is not dict or set(value) != {'schema_version', 'calls'}
                or value['schema_version'] != 'fundamental.call-attempts.v1'
                or type(value['calls']) is not list):
            raise UsageEvidenceInvalid()
        for call in value['calls']:
            if type(call) is not dict or set(call) != FIELDS:
                raise UsageEvidenceInvalid()
            _uid(call['call_id'])
            if call['parent_call_id'] is not None:
                _uid(call['parent_call_id'])
            for key in ('request_sha256', 'policy_sha256'):
                _digest(call[key])
            if call['stage'] not in {'planner', 'interpret', 'critic', 'critic_revision', 'verify_retry'}:
                raise UsageEvidenceInvalid()
            if call['attempt_kind'] not in {'initial', 'schema_retry', 'provider_fallback', 'sdk_retry'}:
                raise UsageEvidenceInvalid()
            if call['outcome'] not in {'unknown', 'response_received', 'http_error', 'validated', 'invalid_output'}:
                raise UsageEvidenceInvalid()
            for key in ('provider', 'model', 'response_model', 'service_tier', 'requested_service_tier'):
                item = call[key]
                if item is None and key not in {'provider', 'model'}:
                    reasons.add('METADATA_UNCONFIRMED')
                elif type(item) is not str or re.fullmatch('[A-Za-z0-9_./:-]{1,128}', item) is None:
                    raise UsageEvidenceInvalid()
            for key in TOKENS:
                if call[key] is None:
                    reasons.add('USAGE_MISSING')
                else:
                    _integer(call[key])
            inp, cached, out, total = (call[k] for k in TOKENS)
            if ((inp is not None and cached is not None and cached > inp)
                    or (inp is not None and out is not None and total is not None and inp + out != total)):
                raise UsageEvidenceInvalid()
            if call['outcome'] != 'validated':
                reasons.add('PRODUCER_CALL_INCOMPLETE')
            observations.setdefault(call['call_id'], set()).add(canonical_json(call))
        if any(len(rows) != 1 for rows in observations.values()):
            return result('rejected', ('CALL_CONFLICT',))
        # The retry/fallback parent must exist in the same observed snapshot;
        # validate references/cycles without treating it as a trusted call list.
        parents = {key: strict_json(next(iter(rows)))['parent_call_id'] for key, rows in observations.items()}
        for key in parents:
            seen = set()
            while key is not None:
                if key in seen or key not in parents:
                    raise UsageEvidenceInvalid()
                seen.add(key); key = parents[key]
        if not observations:
            reasons.add('OBSERVATION_MISSING')
        return result('unknown')
    except (UsageEvidenceInvalid, AnalysisContractError, ValueError, TypeError, UnicodeError, RecursionError):
        # Do not expose partial rows or raw invalid values/error messages.
        observations.clear()
        return result('rejected', ('OBSERVATION_INVALID',))
