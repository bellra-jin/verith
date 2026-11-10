"""Focused pure restoration tests; reuse only CF021's closed pinned loader."""
import copy
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta
import hashlib
import json
import math
from pathlib import Path
import sys
from uuid import UUID
from unittest.mock import patch

import pytest
from tests.unit import test_cf021_technical_boundary as loader
from scripts.check_safe import CF031_INPUTS

loader.load_boundary()
RESTORE = loader._load('src.modules.technical.application.boundary_restore',
    'backend/src/modules/technical/application/boundary_restore.py', CF031_INPUTS)
AC = sys.modules['src.modules.analysis.domain.contracts']
AD = sys.modules['src.modules.technical.application.boundary_adapter']
WIRE = sys.modules['src.modules.analysis.domain.agent_envelope']
ROOT = Path(__file__).resolve().parents[3]
FIXTURE_PATH = 'frontend/tests/fixtures/cf031-technical-boundary-read.json'
assert hashlib.sha256((ROOT / FIXTURE_PATH).read_bytes()).hexdigest() == CF031_INPUTS[FIXTURE_PATH]
FIXTURE = json.loads((ROOT / FIXTURE_PATH).read_text())


def bindings(request=None):
    request = copy.deepcopy(request or FIXTURE['expected']['request'])
    data = request['data']; ids = data['context']
    as_of = datetime.fromisoformat(data['requested_as_of'])
    context = AC.AnalysisContext(analysis_id=UUID(ids['analysis_id']),
        admission_request_id=UUID(ids['admission_request_id']), attempt_id=UUID(ids['attempt_id']),
        owner_user_id=UUID(FIXTURE['owner_user_id']), operation=data['operation'],
        input_fingerprint=ids['input_fingerprint'], as_of=as_of, deadline_at=as_of + timedelta(seconds=3))
    boundary = AD.TechnicalBoundaryBinding(context=context, report_id=UUID(ids['report_id']),
        request_id=UUID(request['request_id']), trace_id=UUID(request['trace_id']), input_json=WIRE.canonical(request))
    text = FIXTURE['caller_input_json']
    caller = replace(context, operation='caller.technical.v1', input_fingerprint=AC.json_hash(text))
    return RESTORE.TechnicalReadBinding(caller, text, boundary)


def frozen_again(frozen, **changes):
    values = {key: getattr(frozen, key) for key in ('context', 'report_id', 'input_schema', 'result_schema', 'input_json', 'result_json')}
    return AC.FrozenAnalysisResult.freeze(**(values | changes))


def test_composition_restore_reuses_cf021_and_returns_detached_values():
    binding = bindings(); response = copy.deepcopy(FIXTURE['response']); before = copy.deepcopy(response)
    boundary_frozen = AD.TechnicalBoundaryAdapter(binding.boundary).validate_and_freeze(response)
    frozen = binding.compose(response)
    assert binding.compose(boundary_frozen) == frozen
    assert frozen.context == binding.caller_context
    assert frozen.input_json == boundary_frozen.input_json and frozen.result_json == boundary_frozen.result_json
    assert binding.caller_context.input_fingerprint != binding.boundary.context.input_fingerprint
    with patch.object(AD.TechnicalBoundaryAdapter, 'chart_preview', wraps=AD.TechnicalBoundaryAdapter(binding.boundary).chart_preview) as preview:
        result = binding.restore(frozen)
        assert preview.call_count == 1
    assert result == FIXTURE['expected_preview']
    result['charts'][0]['annotations'][0]['meta']['original'] = 99
    assert binding.restore(frozen) == FIXTURE['expected_preview'] and response == before
    with pytest.raises(FrozenInstanceError): binding.caller_input_json = '{}'


@pytest.mark.parametrize('field', ['analysis_id','admission_request_id','attempt_id','owner_user_id','as_of','deadline_at'])
def test_contexts_must_match_independent_expected_shared_fields(field):
    binding = bindings(); value = getattr(binding.caller_context, field)
    changed = value + timedelta(seconds=1) if isinstance(value, datetime) else UUID('10000000-0000-4000-8000-000000000001')
    with pytest.raises(ValueError, match='Technical boundary contract is invalid'):
        replace(binding, caller_context=replace(binding.caller_context, **{field:changed}))


@pytest.mark.parametrize('field', ['analysis_id','admission_request_id','attempt_id','owner_user_id','operation','input_fingerprint','as_of','deadline_at'])
def test_self_consistent_frozen_context_is_insufficient(field):
    binding = bindings(); frozen = binding.compose(FIXTURE['response']); value = getattr(frozen.context, field)
    changed = value + timedelta(seconds=1) if isinstance(value, datetime) else UUID('10000000-0000-4000-8000-000000000001') if isinstance(value, UUID) else '0'*64 if field == 'input_fingerprint' else 'other.v1'
    swapped = frozen_again(frozen, context=replace(frozen.context, **{field:changed}))
    swapped.validate()
    with pytest.raises(ValueError, match='Technical boundary contract is invalid'): binding.restore(swapped)


@pytest.mark.parametrize('attack', FIXTURE['attacks'], ids=lambda x:x['name'])
def test_shared_adversarial_packet_rejected_by_existing_validator(attack):
    value = copy.deepcopy(FIXTURE['response']); target = value
    for key in attack['path'][:-1]: target = target[key]
    target[attack['path'][-1]] = attack['value']
    binding = bindings()
    with pytest.raises(ValueError, match='Technical boundary contract is invalid'): binding.compose(value)
    frozen = binding.compose(FIXTURE['response'])
    swapped = frozen_again(frozen, result_json=WIRE.canonical(value))
    with pytest.raises(ValueError, match='Technical boundary contract is invalid'): binding.restore(swapped)


@pytest.mark.parametrize('raw', FIXTURE['raw_text_attacks'])
def test_raw_text_duplicate_malformed_nonfinite_noncanonical_rejected(raw):
    binding = bindings()
    with pytest.raises(ValueError): replace(binding, caller_input_json=raw,
        caller_context=replace(binding.caller_context, input_fingerprint=AC.json_hash(raw)))
    frozen = binding.compose(FIXTURE['response'])
    for field in ('input_json', 'result_json'):
        with pytest.raises(ValueError): frozen_again(frozen, **{field: raw})


@pytest.mark.parametrize('field', ['input_sha256','result_sha256','binding_sha256'])
def test_hash_tampering_rejected(field):
    binding = bindings(); frozen = binding.compose(FIXTURE['response'])
    with pytest.raises(ValueError): replace(frozen, **{field:'0'*64})


@pytest.mark.parametrize('field,value', [('report_id', UUID('10000000-0000-4000-8000-000000000001')),
    ('input_schema','other.v1'), ('result_schema','other.v1')])
def test_independent_report_and_existing_schema_binding(field, value):
    binding = bindings(); frozen = binding.compose(FIXTURE['response'])
    with pytest.raises(ValueError): binding.restore(frozen_again(frozen, **{field:value}))


def test_default_condition_raw_snapshot_and_numeric_representation_preserved():
    request = copy.deepcopy(FIXTURE['expected']['request']); del request['data']['conditions']
    binding = bindings(request); response = copy.deepcopy(FIXTURE['response'])
    response['data']['request_snapshot'] = copy.deepcopy(request['data'])
    response['data']['request_sha256'] = WIRE.digest(request)
    response['data']['result']['charts'][0]['chart_data']['annotations'][0]['meta'] = {'zero':0, 'negative_zero':-0.0, 'null':None, 'float':1.0, 'integer':9007199254740992}
    frozen = binding.compose(response); preview = binding.restore(frozen)
    meta = preview['charts'][0]['annotations'][0]['meta']
    assert math.copysign(1, meta['negative_zero']) == -1 and meta['zero'] == 0 and meta['null'] is None
    assert '"float":1.0' in frozen.result_json and '"negative_zero":-0.0' in frozen.result_json
    assert 'conditions' not in WIRE.decode(frozen.input_json)['data']
    assert all(AC.strict_json(raw) is not None for raw in FIXTURE['numeric_texts'])


def test_l_is_not_aliased_to_b_and_raw_boundary_request_cannot_be_rebound():
    binding = bindings()
    # Equality is permitted when the independently supplied caller text really hashes to B.
    data = FIXTURE['expected']['request']['data']
    semantic_text = WIRE.canonical({key:data[key] for key in
        ('operation', 'original_query', 'stock', 'requested_as_of', 'conditions')})
    same = replace(binding, caller_input_json=semantic_text,
        caller_context=replace(binding.caller_context, operation=binding.boundary.context.operation,
            input_fingerprint=AC.json_hash(semantic_text)))
    assert same.caller_context.input_fingerprint == same.boundary.context.input_fingerprint
    assert same.restore(same.compose(FIXTURE['response'])) == FIXTURE['expected_preview']
    with pytest.raises(ValueError): replace(binding,
        caller_context=replace(binding.caller_context, input_fingerprint=binding.boundary.context.input_fingerprint))
    request = copy.deepcopy(FIXTURE['expected']['request']); request['data']['original_query'] = 'changed'
    request['data']['context']['input_fingerprint'] = sys.modules['src.modules.technical.domain.execution_boundary'].fingerprint(request['data'])
    other = bindings(request); response = copy.deepcopy(FIXTURE['response'])
    response['data']['request_snapshot'] = request['data']; response['data']['request_sha256'] = WIRE.digest(request)
    with pytest.raises(ValueError): binding.restore(other.compose(response))
    assert not loader.ATTEMPTS
