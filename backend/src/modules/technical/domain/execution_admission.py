"""Technical SQL admission only; no provider, environment or policy defaults."""
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import hashlib
import json
import re
from uuid import UUID

OPERATION = 'technical.analysis.v1'
MAX_INT = (1 << 63) - 1
PERIODS = ('3m', '1y', '5y')
SPEC = {'version': 'technical.admission.v1', 'operation': OPERATION,
        'boundary': 'technical.boundary.v1', 'storage': 'technical.owned-stage.v1',
        'profile': 'technical.multiframe.v1', 'periods': list(PERIODS),
        'provider_authority': False, 'settlement': False}
ERRORS = frozenset({'INPUT_INVALID', 'POLICY_UNAVAILABLE', 'LIMIT_EXCEEDED',
    'IDEMPOTENCY_CONFLICT', 'NOT_FOUND', 'CLAIM_DENIED', 'ACK_UNKNOWN',
    'UNAVAILABLE', 'CONTEXT_DIRTY', 'STORED_INVALID'})
REASONS = frozenset({'EXPIRED', 'CANCELLED', 'TIMEOUT', 'REDACTED',
                    'DISPATCH_UNCERTAIN', 'STOCK_CHANGED'})


class TechnicalAdmissionError(ValueError):
    def __init__(self, code='INPUT_INVALID'):
        self.code = code if code in ERRORS else 'UNAVAILABLE'
        super().__init__(self.code)


def canonical(value):
    def shape(item):
        if type(item) is dict:
            if any(type(key) is not str for key in item):
                raise TechnicalAdmissionError()
            for child in item.values():shape(child)
        elif type(item) is list:
            for child in item:shape(child)
        elif type(item) not in {str,int,float,bool,type(None)}:
            raise TechnicalAdmissionError()
    try:
        shape(value)
        result = json.dumps(value, sort_keys=True, ensure_ascii=False,
                            separators=(',', ':'), allow_nan=False)
        result.encode('utf-8')
        return result
    except (ValueError, TypeError, UnicodeError, RecursionError, OverflowError):
        raise TechnicalAdmissionError() from None


def sha(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def decode(value, limit=16384):
    def pairs(items):
        result = {}
        for key, item in items:
            if key in result:
                raise TechnicalAdmissionError()
            result[key] = item
        return result
    try:
        if type(value) is not str or not 2 <= len(value.encode('utf-8')) <= limit:
            raise TechnicalAdmissionError()
        return json.loads(value, object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(TechnicalAdmissionError()))
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise TechnicalAdmissionError() from None


def integer(value, *, positive=True):
    if type(value) is not int or not (1 if positive else 0) <= value <= MAX_INT:
        raise TechnicalAdmissionError()
    return value


def uid(value):
    # User/internal caller values remain strict. Driver subclasses are normalized
    # explicitly by the repository's SELECT boundary, never accepted here.
    if type(value) is not UUID or value.int == 0:
        raise TechnicalAdmissionError()
    return value


def digest(value):
    if type(value) is not str or re.fullmatch(r'[0-9a-f]{64}', value) is None:
        raise TechnicalAdmissionError()
    return value


def ticker(value):
    if type(value) is not str or re.fullmatch(r'[0-9]{6}', value) is None:
        raise TechnicalAdmissionError()
    return value


def utc(value):
    if type(value) is not datetime or value.utcoffset() != timedelta(0):
        raise TechnicalAdmissionError()
    return value.astimezone(UTC)


@dataclass(frozen=True, slots=True, repr=False)
class Intent:
    text: str = field(repr=False)

    def __post_init__(self):
        value = decode(self.text)
        if type(value) is not dict or set(value) != {'operation', 'ticker', 'original_query', 'requested_views', 'conditions'}:
            raise TechnicalAdmissionError()
        ticker(value['ticker'])
        query = value['original_query']
        if (value['operation'] != OPERATION or type(query) is not str
                or not 1 <= len(query) <= 2000 or not query.strip() or '\x00' in query
                or value['requested_views'] != ['technical']
                or value['conditions'] != {'profile': 'technical.multiframe.v1', 'periods': list(PERIODS)}
                or canonical(value) != self.text):
            raise TechnicalAdmissionError()

    @classmethod
    def parse(cls, value):
        return cls(canonical(decode(value) if type(value) is str else value))

    @property
    def fingerprint(self):
        return sha(self.text)

    def data(self):
        return decode(self.text)


POLICY_FIELDS = frozenset({'operation', 'enabled', 'currency', 'supported_tickers',
    'user_daily_limit', 'service_daily_limit', 'daily_budget_nano', 'attempt_reserve_nano',
    'deadline_seconds', 'model', 'service_tier', 'price_id', 'price_evidence_sha256',
    'input_nano_per_token', 'output_nano_per_token', 'input_token_cap', 'output_token_cap',
    'input_byte_cap', 'output_byte_cap', 'max_calls'})
POLICY_INTEGERS = POLICY_FIELDS - {'operation', 'enabled', 'currency', 'supported_tickers',
    'model', 'service_tier', 'price_id', 'price_evidence_sha256'}


@dataclass(frozen=True, slots=True, repr=False)
class Policy:
    text: str = field(repr=False)

    def __post_init__(self):
        try:
            value = decode(self.text)
            if type(value) is not dict or set(value) != POLICY_FIELDS or canonical(value) != self.text:
                raise TechnicalAdmissionError()
            if (value['operation'] != OPERATION or type(value['enabled']) is not bool
                    or value['currency'] != 'USD' or value['service_tier'] != 'default'):
                raise TechnicalAdmissionError()
            names = value['supported_tickers']
            if type(names) is not list or not names or len(names) > 1000:
                raise TechnicalAdmissionError()
            for name in names:
                ticker(name)
            if names != sorted(set(names)):
                raise TechnicalAdmissionError()
            for key in POLICY_INTEGERS:
                integer(value[key])
            for key in ('model', 'price_id'):
                if type(value[key]) is not str or re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}', value[key]) is None:
                    raise TechnicalAdmissionError()
            digest(value['price_evidence_sha256'])
            subtotal = integer(integer(value['input_token_cap'] * value['input_nano_per_token'])
                               + integer(value['output_token_cap'] * value['output_nano_per_token']))
            maximum = integer(value['max_calls'] * subtotal)
            if not maximum <= value['attempt_reserve_nano'] <= value['daily_budget_nano']:
                raise TechnicalAdmissionError()
            if not value['user_daily_limit'] <= value['service_daily_limit'] or value['deadline_seconds'] > 86400:
                raise TechnicalAdmissionError()
        except TechnicalAdmissionError:
            raise TechnicalAdmissionError('POLICY_UNAVAILABLE') from None

    @classmethod
    def parse(cls, value):
        try:
            return cls(canonical(decode(value) if type(value) is str else value))
        except TechnicalAdmissionError:
            raise TechnicalAdmissionError('POLICY_UNAVAILABLE') from None

    @property
    def fingerprint(self):
        return sha(self.text)

    def data(self):
        return decode(self.text)

    def enabled(self):
        if not self.data()['enabled']:
            raise TechnicalAdmissionError('POLICY_UNAVAILABLE')
        return self.data()


SPEC_JSON = canonical(SPEC)
SPEC_SHA256 = sha(SPEC_JSON)


@dataclass(frozen=True, slots=True)
class RunReceipt:
    analysis_id: UUID
    admission_request_id: UUID
    attempt_id: UUID
    report_id: UUID
    boundary_request_id: UUID
    trace_id: UUID
    admission_session_id: UUID
    period_id: UUID
    intent_sha256: str
    policy_sha256: str
    spec_sha256: str
    as_of: datetime
    deadline_at: datetime
    state: str
    reserved_nano: int
    held_nano: int
    claim_consumed_at: datetime | None
    redacted_at: datetime | None
    unknown_reason: str | None

    def __post_init__(self):
        for key in ('analysis_id', 'admission_request_id', 'attempt_id', 'report_id',
                    'boundary_request_id', 'trace_id', 'admission_session_id', 'period_id'):
            uid(getattr(self, key))
        if len({getattr(self,key) for key in ('analysis_id','admission_request_id','attempt_id','report_id','boundary_request_id','trace_id')}) != 6:
            raise TechnicalAdmissionError('STORED_INVALID')
        for key in ('intent_sha256', 'policy_sha256', 'spec_sha256'):
            digest(getattr(self, key))
        utc(self.as_of);utc(self.deadline_at)
        integer(self.reserved_nano);integer(self.held_nano)
        if self.held_nano != self.reserved_nano or self.deadline_at <= self.as_of or self.spec_sha256 != SPEC_SHA256:
            raise TechnicalAdmissionError('STORED_INVALID')
        if type(self.state) is not str or self.state not in {'admitted', 'claimed', 'unknown'}:
            raise TechnicalAdmissionError('STORED_INVALID')
        if self.claim_consumed_at is not None:
            utc(self.claim_consumed_at)
            if not self.as_of <= self.claim_consumed_at < self.deadline_at:
                raise TechnicalAdmissionError('STORED_INVALID')
        if self.redacted_at is not None:
            utc(self.redacted_at)
            if self.redacted_at < self.as_of:
                raise TechnicalAdmissionError('STORED_INVALID')
        if (self.state == 'admitted' and self.claim_consumed_at is not None
                or self.state == 'claimed' and self.claim_consumed_at is None
                or (self.state == 'unknown') != (self.redacted_at is not None)
                or (self.state == 'unknown' and (type(self.unknown_reason) is not str or self.unknown_reason not in REASONS))
                or (self.state != 'unknown' and self.unknown_reason is not None)):
            raise TechnicalAdmissionError('STORED_INVALID')


@dataclass(frozen=True, slots=True)
class AdmissionReceipt:
    run: RunReceipt
    newly_admitted: bool
    claim_token: bytes | None = field(default=None, repr=False)

    def __post_init__(self):
        if type(self.run) is not RunReceipt or type(self.newly_admitted) is not bool:
            raise TechnicalAdmissionError('STORED_INVALID')
        self.run.__post_init__()
        if self.newly_admitted:
            if self.run.state != 'admitted' or type(self.claim_token) is not bytes or len(self.claim_token) != 32:
                raise TechnicalAdmissionError('STORED_INVALID')
        elif self.claim_token is not None:
            raise TechnicalAdmissionError('STORED_INVALID')


@dataclass(frozen=True, slots=True)
class ClaimReceipt:
    run: RunReceipt
    newly_claimed: bool
    intent_json: str | None = field(default=None, repr=False)

    def __post_init__(self):
        if type(self.run) is not RunReceipt or type(self.newly_claimed) is not bool:
            raise TechnicalAdmissionError('STORED_INVALID')
        self.run.__post_init__()
        if self.newly_claimed:
            if self.run.state != 'claimed' or Intent(self.intent_json).fingerprint != self.run.intent_sha256:
                raise TechnicalAdmissionError('STORED_INVALID')
        elif self.intent_json is not None:
            raise TechnicalAdmissionError('STORED_INVALID')
