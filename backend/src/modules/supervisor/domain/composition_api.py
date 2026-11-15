"""Public consent is distinct from either native single-agent plan."""
from typing import Literal
from pydantic import Field
from .contracts import CoreStrict, Draft, UUID_PATTERN, sha
from .composition import CompositionSnapshot

VERSION = 'supervisor.composition-api.v1'


class Consent(CoreStrict):
    allow_views: list[Literal['flow', 'technical']] = Field(min_length=1, max_length=2)
    allow_partial_results: bool
    waived_conditions: list[str] = Field(max_length=0)


class Confirm(CoreStrict):
    client_key: str = Field(pattern=UUID_PATTERN)
    draft: Draft
    expected_plan_hash: str = Field(pattern='^[0-9a-f]{64}$')
    consent: Consent


class TechnicalResult(CoreStrict):
    """Composition-only projection after full owned snapshot validation.

    Internal request snapshots, execution authority, usage and transport metadata
    never cross this DTO. Nested analysis/chart structures retain native values.
    """
    ticker: str = Field(pattern='^[0-9]{6}$')
    as_of: str
    data_status: str
    regime: dict
    signal: dict | None
    technical_signals: list[dict] = Field(max_length=5)
    risk: dict | None
    charts: list[dict] = Field(max_length=3)
    interpretation: dict
    verification: dict


def technical_result(raw):
    return TechnicalResult.model_validate({key:raw[key] for key in TechnicalResult.model_fields}).model_dump(mode='json')


def plan(snapshot: CompositionSnapshot):
    """Expose scope/policy fingerprints, never private configuration/capabilities."""
    data = snapshot.data()
    from src.modules.analysis.domain.usage import RUN_RESERVE
    from src.modules.technical.domain.provider_execution import Configuration
    cfg=Configuration(data['technical_configuration']) if data['technical_configuration'] else None
    reservations={}
    if data['flow_policy']:reservations['flow']=RUN_RESERVE
    if cfg is not None:reservations['technical']=cfg.data()['policy']['attempt_reserve_nano']
    value = dict(schema_version=VERSION, status='ready', draft=data['draft'], frame=data['frame'],
        stock=data['stock'], selected_views=data['selected_views'], child_inputs=data['child_inputs'],
        required_consent=data['consent'], scope_sha256=snapshot.fingerprint,
        reservation_caps_nano=reservations, maximum_reserved_nano=sum(reservations.values()),
        flow_policy_sha256=sha(data['flow_policy']) if data['flow_policy'] else None,
        technical_configuration_sha256=cfg.fingerprint if cfg is not None else None)
    return value | dict(plan_hash=sha(value))


def confirms(body: Confirm, snapshot: CompositionSnapshot):
    from .composition import CompositionInvalid
    if (body.draft.model_dump(mode='json') != snapshot.data()['draft']
            or body.expected_plan_hash != plan(snapshot)['plan_hash']
            or body.consent.model_dump(mode='json') != snapshot.data()['consent']):
        raise CompositionInvalid()
