"""Fundamental usage completeness only; no IO, prices, settlement or execution rights.

The caller supplies an authoritative closed call inventory and independently
vouches for receipt provenance. Hashes bind bytes; they do not authenticate them.
Current Fundamental cost_summary does not satisfy this contract.
"""
from dataclasses import dataclass
import re
from uuid import UUID
from src.modules.analysis.domain.contracts import (
    AnalysisContext, AnalysisContractError, canonical_json, strict_json, json_hash,
)

OPERATION = 'fundamental.analysis.v1'
SCHEMA = 'fundamental.usage-evidence.v1'
MAX_INT = 2**63 - 1
MAX_DOCUMENT_BYTES = 65536  # Parsing bound, never a provider/cost/call policy.
SPEC_FIELDS = frozenset({'call_id', 'provider', 'model', 'service_tier',
                         'request_sha256', 'input_token_cap', 'output_token_cap'})
TOKEN_FIELDS = ('input_tokens', 'cached_tokens', 'output_tokens', 'total_tokens')
CALL_FIELDS = (SPEC_FIELDS - {'input_token_cap', 'output_token_cap'}) | frozenset(TOKEN_FIELDS)


class UsageEvidenceInvalid(ValueError):
    def __init__(self):
        super().__init__('Fundamental usage evidence contract is invalid')


def _shape(value, fields):
    if type(value) is not dict or set(value) != fields:
        raise UsageEvidenceInvalid()


def _digest(value):
    if type(value) is not str or re.fullmatch('[0-9a-f]{64}', value) is None:
        raise UsageEvidenceInvalid()


def _uid(value):
    if type(value) is not str:
        raise UsageEvidenceInvalid()
    try:
        parsed = UUID(value)
        if not parsed.int or str(parsed) != value:
            raise UsageEvidenceInvalid()
    except ValueError:
        raise UsageEvidenceInvalid() from None


def _integer(value, *, positive=False):
    if type(value) is not int or not (1 if positive else 0) <= value <= MAX_INT:
        raise UsageEvidenceInvalid()


def _document(text):
    try:
        if (type(text) is not str or not 2 <= len(text) <= MAX_DOCUMENT_BYTES
                or len(text.encode('utf8')) > MAX_DOCUMENT_BYTES):
            raise UsageEvidenceInvalid()
        return strict_json(text)
    except (AnalysisContractError, UnicodeError, ValueError, RecursionError):
        raise UsageEvidenceInvalid() from None


@dataclass(frozen=True, slots=True, repr=False)
class UsageExpectation:
    """Backend-owned snapshot, not a DTO constructed from AI/client claims.

    inventory_closed means the caller proved ALL billable attempts are listed,
    including fallback/retry/failed sends. A planned maximum alone is not proof.
    No current Fundamental dispatcher can yet supply this authoritative inventory.
    """
    context: AnalysisContext
    policy_sha256: str
    calls_json: str
    inventory_closed: bool

    def __post_init__(self):
        self.calls()

    def calls(self):
        try:
            if type(self.context) is not AnalysisContext or self.context.operation != OPERATION:
                raise UsageEvidenceInvalid()
            self.context.validate()
            for key in ('analysis_id', 'admission_request_id', 'attempt_id', 'owner_user_id'):
                _uid(str(getattr(self.context, key)))
            _digest(self.policy_sha256)
            if type(self.inventory_closed) is not bool:
                raise UsageEvidenceInvalid()
            calls = _document(self.calls_json)
            if type(calls) is not list or canonical_json(calls) != self.calls_json:
                raise UsageEvidenceInvalid()
            seen = set()
            for call in calls:
                _shape(call, SPEC_FIELDS)
                _uid(call['call_id']); _digest(call['request_sha256'])
                if call['call_id'] in seen:
                    raise UsageEvidenceInvalid()
                seen.add(call['call_id'])
                for key in ('provider', 'model', 'service_tier'):
                    if type(call[key]) is not str or re.fullmatch('[A-Za-z0-9_.:-]{1,128}', call[key]) is None:
                        raise UsageEvidenceInvalid()
                for key in ('input_token_cap', 'output_token_cap'):
                    _integer(call[key], positive=True)
            return calls
        except (AnalysisContractError, ValueError, TypeError, AttributeError, RecursionError):
            raise UsageEvidenceInvalid() from None

    @property
    def fingerprint(self):
        calls = sorted(self.calls(), key=lambda c: c['call_id'])
        return json_hash(canonical_json(dict(schema_version=SCHEMA,
            context=self.context.identity(), policy_sha256=self.policy_sha256,
            inventory_closed=self.inventory_closed, calls=calls)))


@dataclass(frozen=True, slots=True)
class UsageAssessment:
    state: str
    reason: str
    expectation_sha256: str
    calls_json: str
    input_tokens: int | None = None
    cached_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None

    @property
    def keep_reservation(self):
        # Even complete_usage is not settlement authorization in this unit.
        return True


def classify_usage(expected, receipts, *, usage_trusted=False):
    """Classify an entire retained receipt set; exact repeats are idempotent.

    No durable dedup/receipt store is created. A future caller must retain the
    whole set (including conflicts) and enforce provenance outside this function.
    Neither producer complete=true nor a subtotal can establish completeness.
    """
    if type(expected) is not UsageExpectation or type(usage_trusted) is not bool:
        raise UsageEvidenceInvalid()
    specs = {c['call_id']: c for c in expected.calls()}
    fingerprint = expected.fingerprint
    observed = {}  # call ID -> distinct canonical records, never last-write-wins.

    def result(state, reason, totals=None):
        rows = [strict_json(raw) for key in sorted(observed) for raw in sorted(observed[key])]
        return UsageAssessment(state, reason, fingerprint, canonical_json(rows), **(totals or {}))

    # A raw JSON document needs >=2 bytes plus a collection separator. Bound
    # collection overhead before traversal, independently of billable call caps.
    if type(receipts) is not tuple or len(receipts) > (MAX_DOCUMENT_BYTES - 1) // 3:
        return result('rejected', 'EVIDENCE_INVALID')
    size = 2  # Outer collection brackets.
    missing, aggregate = not receipts, False
    try:
        for index, text in enumerate(receipts):
            size += int(index > 0)  # Separator in the retained document set.
            if text is None:
                size += 4  # JSON null is not free input capacity.
                if size > MAX_DOCUMENT_BYTES:
                    raise UsageEvidenceInvalid()
                missing = True
                continue
            value = _document(text)
            size += len(text.encode('utf8'))
            if size > MAX_DOCUMENT_BYTES:
                raise UsageEvidenceInvalid()
            if type(value) is dict and 'cost_summary' in value:
                aggregate = True
                continue
            _shape(value, {'schema_version', 'expectation_sha256', 'calls'})
            if value['schema_version'] != SCHEMA or value['expectation_sha256'] != fingerprint:
                return result('rejected', 'BINDING_MISMATCH')
            if type(value['calls']) is not list:
                raise UsageEvidenceInvalid()
            for call in value['calls']:
                _shape(call, CALL_FIELDS)
                identity = call['call_id']
                _uid(identity)
                if identity not in specs:
                    return result('rejected', 'CALL_NOT_EXPECTED')
                spec = specs[identity]
                if any(type(call[k]) is not str or call[k] != spec[k]
                       for k in SPEC_FIELDS - {'input_token_cap', 'output_token_cap'}):
                    return result('rejected', 'CALL_BINDING_MISMATCH')
                for key in TOKEN_FIELDS:
                    if call[key] is not None:
                        _integer(call[key])
                inp, cached, out, total = (call[k] for k in TOKEN_FIELDS)
                if ((cached is not None and inp is not None and cached > inp)
                        or (inp is not None and out is not None and total is not None and inp + out != total)):
                    return result('rejected', 'USAGE_INVALID')
                if ((inp is not None and inp > spec['input_token_cap'])
                        or (out is not None and out > spec['output_token_cap'])):
                    return result('rejected', 'POLICY_CAP_EXCEEDED')
                observed.setdefault(identity, set()).add(canonical_json(call))
    except (UsageEvidenceInvalid, AnalysisContractError, ValueError, TypeError, UnicodeError, RecursionError):
        return result('rejected', 'EVIDENCE_INVALID')
    if any(len(rows) != 1 for rows in observed.values()):
        return result('rejected', 'CALL_CONFLICT')
    if not expected.inventory_closed or not specs:
        return result('unknown', 'CALL_INVENTORY_UNPROVEN')
    if not usage_trusted:
        return result('unknown', 'PROVENANCE_UNPROVEN')
    if aggregate:
        return result('unknown', 'AGGREGATE_ONLY')
    if missing or set(observed) != set(specs):
        return result('unknown', 'USAGE_MISSING')
    rows = [strict_json(next(iter(values))) for values in observed.values()]
    if any(call[k] is None for call in rows for k in TOKEN_FIELDS):
        return result('unknown', 'USAGE_MISSING')
    totals = {k: sum(call[k] for call in rows) for k in TOKEN_FIELDS}
    if any(v > MAX_INT for v in totals.values()):
        return result('unknown', 'USAGE_OVERFLOW')
    return result('complete_usage', 'ALL_CALLS_OBSERVED', totals)
