"""Fixed Flow/Technical composition identity and conservative observation.

No admission, dispatch, SQL, pricing, or execution authority lives in this module.
Native child states are retained; a missing receipt is never proof of no call.
"""
from dataclasses import dataclass, field
from uuid import UUID, uuid5


VERSION = 'supervisor.composition.v1'
VIEWS = ('flow', 'technical')
STATES = frozenset({'not_started', 'not_admitted', 'admitted', 'running', 'claimed',
                    'result_ready', 'stored', 'failed', 'unknown', 'deleted'})
PENDING = frozenset({'not_started', 'admitted', 'running', 'claimed', 'result_ready'})


class CompositionInvalid(ValueError):
    def __init__(self):
        super().__init__('Supervisor composition unavailable')


def fixed_child_key(parent_id: UUID, view: str, identity_seed: bytes) -> str:
    """A stable input key, never a provider token or a claim capability."""
    if (type(parent_id) is not UUID or type(view) is not str or view not in VIEWS
            or type(identity_seed) is not bytes or len(identity_seed)!=32):
        raise CompositionInvalid()
    return str(uuid5(parent_id, VERSION + ':' + view + ':' + identity_seed.hex()))


@dataclass(frozen=True, slots=True)
class ChildObservation:
    view: str
    state: str
    handoff_consumed: bool
    receipt_confirmed: bool

    def __post_init__(self):
        if (type(self.view) is not str or type(self.state) is not str
                or self.view not in VIEWS or self.state not in STATES
                or type(self.handoff_consumed) is not bool or type(self.receipt_confirmed) is not bool):
            raise CompositionInvalid()
        if not self.handoff_consumed and (self.state != 'not_started' or self.receipt_confirmed):
            raise CompositionInvalid()
        if self.handoff_consumed and self.state == 'not_started':
            raise CompositionInvalid()
        if not self.receipt_confirmed and self.state not in {'not_started', 'unknown'}:
            raise CompositionInvalid()


def coverage(children: tuple[ChildObservation, ...], *, dispatch_closed: bool) -> str:
    """Aggregate fulfillment only; never collapse unknown into failed/not_called."""
    if (type(dispatch_closed) is not bool or type(children) is not tuple or not 1 <= len(children) <= 2
            or any(type(c) is not ChildObservation for c in children)
            or len({c.view for c in children}) != len(children)):
        raise CompositionInvalid()
    states = {c.state for c in children}
    if states == {'stored'}:
        return 'fulfilled'
    if 'stored' in states:
        return 'partial'
    if 'unknown' in states:
        return 'unknown'
    if states & (PENDING - {'not_started'} if dispatch_closed else PENDING):
        return 'pending'
    if states == {'deleted'}:
        return 'deleted'
    return 'unfulfilled'


@dataclass(frozen=True, slots=True)
class CompositionSnapshot:
    """Internal confirmed scope, not an execution capability or a public DTO.

    The first serial unit accepts fully resolved fixed profiles only. Conditions
    and ambiguity must stay in clarification; they are not projected away.
    """
    text: str = field(repr=False)

    def __post_init__(self):
        from .contracts import decode, canonical, Draft, MeaningFrame, Stock
        from src.modules.analysis.domain.usage import MAX_INT, RUN_RESERVE
        from src.modules.technical.domain import provider_execution as provider
        from src.modules.technical.domain.execution_admission import Policy
        try:
            value = decode(self.text)
            if (type(value) is not dict or set(value) != {'schema_version', 'draft', 'frame', 'stock',
                    'selected_views', 'consent', 'flow_policy', 'technical_configuration'}
                    or value['schema_version'] != VERSION or canonical(value) != self.text
                    or len(self.text.encode('utf8')) > 65536):
                raise ValueError()
            draft = Draft.model_validate(value['draft'])
            frame = MeaningFrame.model_validate(value['frame'])
            stock = Stock.model_validate(value['stock'])
            views = value['selected_views']
            if (type(views) is not list or not 1 <= len(views) <= 2
                    or any(type(v) is not str or v not in VIEWS for v in views)
                    or views != [v for v in VIEWS if v in frame.requested_views]
                    or len(frame.requested_views) != len(views)
                    or frame.original_query != draft.original_query or frame.answers != draft.answers
                    or frame.revision != draft.revision or frame.unresolved_slots or frame.conditions
                    or frame.interpretation_source != 'deterministic'
                    or any(m.negated and m.text.casefold() in {stock.stock_code.casefold(), stock.stock_name.casefold()} for m in frame.mentions)
                    or set(views) & set(frame.negated_views)
                    or len({m.text for m in frame.mentions if not m.negated}) != 1):
                raise ValueError()
            consent = value['consent']
            if (type(consent) is not dict or set(consent) != {'allow_views', 'allow_partial_results', 'waived_conditions'}
                    or consent['allow_views'] != views or type(consent['allow_partial_results']) is not bool
                    or len(views) == 2 and consent['allow_partial_results'] is not True
                    or consent['waived_conditions'] != []):
                raise ValueError()
            maximum = 0
            flow = value['flow_policy']
            if 'flow' in views:
                if (type(flow) is not dict or set(flow) != {'supported_tickers', 'user_limit', 'service_limit', 'budget'}
                        or type(flow['supported_tickers']) is not list
                        or flow['supported_tickers'] != sorted(set(flow['supported_tickers']))
                        or stock.stock_code not in flow['supported_tickers']
                        or any(type(t) is not str or len(t) != 6 or not t.isascii() or not t.isdecimal() for t in flow['supported_tickers'])
                        or any(type(flow[k]) is not int or not 0 < flow[k] <= MAX_INT for k in ('user_limit', 'service_limit', 'budget'))
                        or flow['budget'] < RUN_RESERVE):
                    raise ValueError()
                maximum += RUN_RESERVE
            elif flow is not None:
                raise ValueError()
            technical = value['technical_configuration']
            if 'technical' in views:
                cfg = provider.Configuration(technical)
                policy = Policy(provider.canonical(cfg.data()['policy']))
                policy.enabled()
                if stock.stock_code not in policy.data()['supported_tickers'] or policy.data()['deadline_seconds']>140-15:
                    raise ValueError()
                maximum += policy.data()['attempt_reserve_nano']
            elif technical is not None:
                raise ValueError()
            if maximum > MAX_INT:
                raise ValueError()
        except Exception:
            raise CompositionInvalid() from None

    @property
    def fingerprint(self):
        import hashlib
        return hashlib.sha256(self.text.encode('utf8')).hexdigest()

    def data(self):
        from .contracts import decode
        return decode(self.text)
