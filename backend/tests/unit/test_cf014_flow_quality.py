"""CF-014 single focused collection. Pure code + exact AST slices, no AI graph.

All AI modules are explicit reviewed files, in closed package paths. The existing
token-cache module is loaded only to retain the unchanged worker origin check.
No cache operation, pandas/LangChain import or provider invocation occurs.
"""
import ast
import copy
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, date, datetime, timedelta
import hashlib
import importlib.machinery
import importlib.util
import json
import math
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from uuid import uuid4

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_AI = _ROOT / "ai/src"
for _name in ("agents", "agents.flow", "agents.flow.api", "agents.flow.domain",
              "agents.flow.domain.verification", "agents.flow.infrastructure"):
    _module = ModuleType(_name)
    _module.__spec__ = importlib.machinery.ModuleSpec(_name, loader=None, is_package=True)
    _module.__spec__.submodule_search_locations = [str(_AI.joinpath(*_name.split('.')))]
    _module.__path__ = []  # No import search, including adjacent AI modules.
    sys.modules[_name] = _module

for _name in ("domain.observation_window", "domain.verification.consecutive", "domain.interpretation_claims",
              "domain.models", "domain.verification.interpretation", "api.payload", "api.schemas",
              "infrastructure.token_cache"):
    _full = "agents.flow." + _name
    _spec = importlib.util.spec_from_file_location(_full, _AI / (_full.replace('.', '/') + '.py'))
    _module = importlib.util.module_from_spec(_spec)
    sys.modules[_full] = _module
    _spec.loader.exec_module(_module)
    _parent, _leaf = _full.rsplit(".", 1)
    setattr(sys.modules[_parent], _leaf, _module)

from agents.flow.domain import interpretation_claims as claims
from agents.flow.domain.verification.consecutive import verify_consecutive
from agents.flow.domain.verification.interpretation import verify_interpretation
from agents.flow.domain.models import GateResult, SupplyDemandState, AgentInput
from agents.flow.api.payload import build_payload
from agents.flow.api import schemas as ai_schema

SUBJECTS = ("개인", "외국인", "기관")
CONFIG = SimpleNamespace(RECENT_DAYS=5, TREND_DAYS=20, CONSECUTIVE_THRESHOLD=3, MAX_EXPLAIN_RETRIES=2)


def fixture(count=20, values=(1.0, -2.0, 3.0), denominator=100.0):
    dates = [(date(2026, 9, 1) + timedelta(days=i)).isoformat() for i in range(count)]
    supply = [dict(date=d, 거래대금=denominator, **dict(zip(SUBJECTS, values))) for d in dates]
    recent = supply[-5:]
    totals = {s: math.fsum(r[s] for r in recent) for s in SUBJECTS}
    signals = {"alignment": ("동반매수" if totals['외국인'] > 0 and totals['기관'] > 0 else
                             "동반매도" if totals['외국인'] < 0 and totals['기관'] < 0 else "엇갈림"),
        "strength": {s: {"ratio": totals[s] / denominator if denominator else 0.0, "strong": False} for s in SUBJECTS},
        "consecutive": {s: {"days": count if v > 0 else 0, "signal": v > 0 and count >= 3} for s, v in zip(SUBJECTS, values)},
        "daily": [{"date": d, **dict(zip(SUBJECTS, values))} for d in dates[-20:]],
        "persistence": {s: {"sum_5": totals[s], "sum_20": math.fsum(r[s] for r in supply[-20:]),
                            "consistent": v != 0} for s, v in zip(SUBJECTS, values)},
        "inst_detail": None,
        "price_daily": [{"date": d, "close": 10000, "change": -1, "change_rate": -0.01, "volume": 0,
                         "frgn_qty": None, "inst_qty": 0} for d in dates[-20:]],
        "ownership": [{"date": d, "ratio": 10 + i * .001} for i, d in enumerate(dates)][-5:]}
    evidence = {"supply": supply,
        "quotes": [{"date": d, "종가": 10000, "전일비": -1, "등락률": -.01} for d in dates],
        "ownership": [{"date": d, "value": 10 + i * .001} for i, d in enumerate(dates)]}
    meta = dict(stock_name='합성 종목', ticker='005930', market=None, base_date=dates[-1])
    return signals, evidence, meta


def bank_for(*args, **kwargs):
    s, e, m = fixture(*args, **kwargs)
    return s, e, m, claims.build_bank(s, e, m, gate2_passed=True)


def selected(bank, *kinds):
    return tuple(f.id for f in bank.facts if f.kind in (kinds or ('strength',)))[:8]


@pytest.mark.parametrize('values,days', [([1, 2, 3], 3), ([1, 0, 2], 1), ([3, -1, 1, 2], 2), ([1, 0], 0), ([-1], 0)])
def test_consecutive_independent_break_and_signal(values, days):
    dates = [(date(2026, 1, 1) + timedelta(days=i)).isoformat() for i in range(len(values))]
    assert verify_consecutive(values, days, days >= 3, 3, dates=dates, subject='외국인')
    assert not verify_consecutive(values, days, not (days >= 3), 3, dates=dates, subject='외국인')


@pytest.mark.parametrize('bad', [True, None, float('nan'), float('inf'), -float('inf'), '1'])
def test_consecutive_rejects_every_invalid_raw_even_before_latest_break(bad):
    assert not verify_consecutive([bad, 0], 0, False, 3, dates=['2026-01-01', '2026-01-02'], subject='기관')


@pytest.mark.parametrize('days', [True, -1, 1.0, 3, None, 0])
def test_consecutive_wrong_claim_type_range_and_in_range(days):
    assert not verify_consecutive([1, 1], days, False, 3, dates=['2026-01-01', '2026-01-02'], subject='개인')


@pytest.mark.parametrize('dates,subject', [(['2026-01-02', '2026-01-01'], '개인'),
    (['2026-01-01', '2026-01-01'], '개인'), (['invalid', '2026-01-02'], '개인'),
    (['2026-01-01'], '개인'), (['2026-01-01', '2026-01-02'], 'unknown')])
def test_consecutive_dates_subject_and_context_fail_closed(dates, subject):
    assert not verify_consecutive([1, 1], 2, False, 3, dates=dates, subject=subject)


@pytest.mark.parametrize('count', [1, 4, 5, 19, 20, 27])
def test_full_source_counts_strength_definition_and_windows(count):
    s, e, m, bank = bank_for(count)
    assert bank and len(bank.facts) <= 24
    assert claims.valid_bank(bank, m, s)
    strength = [f for f in bank.facts if f.kind == 'strength']
    assert len(strength) == 3
    for fact in strength:
        assert len(fact.dates) == min(5, count) and f'관측 {min(5, count)}행' in fact.sentence
        assert '일평균 거래대금' in fact.sentence and fact.unit == 'ratio→%'
    assert len(next(f for f in bank.facts if f.kind == 'consecutive').dates) == count
    assert bool([f for f in bank.facts if f.kind == 'persistence']) == (count >= 20)
    if count < 20:
        assert '비교 보류' in bank.notice
    assert len([f for f in bank.facts if f.kind == 'ownership']) == 2
    change = next(f for f in bank.facts if f.subject == '외국인변화')
    assert len(change.dates) == min(5, count)  # Actual producer window, not tail20.
    assert s == fixture(count)[0] and e == fixture(count)[1]


@pytest.mark.parametrize('value,word', [(0.0, '0.0%'), (-0.0, '0.0%'), (1e-12, '양수·표시 정밀도 미만'),
    (-1e-12, '음수·표시 정밀도 미만'), (50.0, '+250.0%')])
def test_ratio_precision_zero_sign_and_greater_than_one(value, word):
    s, e, m, bank = bank_for(values=(value, value, value))
    fact = next(f for f in bank.facts if f.kind == 'strength')
    assert word in fact.sentence
    assert fact.signs[0] == claims.sign(value)
    if value:
        altered = copy.deepcopy(s); altered['strength']['개인']['ratio'] = 0
        other = claims.build_bank(altered, e, m, gate2_passed=True)
        assert not any(f.kind == 'strength' and f.subject == '개인' for f in other.facts)


@pytest.mark.parametrize('denominator', [0, None, float('nan')])
def test_unmeasured_denominator_is_not_measured_zero(denominator):
    s, e, m = fixture()
    for r in e['supply']: r['거래대금'] = None if isinstance(denominator, float) and math.isnan(denominator) else denominator
    for v in s['strength'].values(): v['ratio'] = 0.0
    bank = claims.build_bank(s, e, m, gate2_passed=True)
    assert bank and not any(f.kind == 'strength' for f in bank.facts)
    assert '강도 산출근거 부족' in ' '.join(bank.skeleton)


def test_unknown_persistence_no_fact_and_actual_confirmed_date_not_candidate():
    s, e, m = fixture(); s['persistence']['외국인']['sum_20'] += 1
    bank = claims.build_bank(s, e, m, gate2_passed=True)
    assert not any(f.kind == 'persistence' for f in bank.facts) and '미확인' in bank.notice
    assert claims.build_bank(s, e, dict(m, base_date='2026-12-31'), gate2_passed=True) is None
    assert claims.build_bank(s, e, m, gate2_passed=False) is None


def test_daily_twenty_and_raw_nineteen_cannot_forge_a_persistence_window():
    s, e, m = fixture(20)
    for subject, value in zip(SUBJECTS, (1.0, -2.0, 3.0)):
        s['daily'][0][subject] = e['supply'][0][subject] = 0
        s['persistence'][subject]['sum_20'] = value * 19
        s['consecutive'][subject]['days'] = 19 if value > 0 else 0
    assert claims.build_bank(s, e, m, gate2_passed=True) is not None
    e['supply'].pop(0)
    assert claims.build_bank(s, e, m, gate2_passed=True) is None
    s['daily'].pop(0)
    bank = claims.build_bank(s, e, m, gate2_passed=True)
    assert bank is not None and not any(f.kind == 'persistence' for f in bank.facts)
    assert '부족' in bank.notice


@pytest.mark.parametrize('field', ['ratio', 'price', 'ownership', 'consecutive'])
def test_tampered_claim_is_never_reissued(field):
    s, e, m = fixture()
    if field == 'ratio': s['strength']['외국인']['ratio'] *= -1
    elif field == 'price': s['price_daily'][-1]['close'] += 1
    elif field == 'ownership': s['ownership'][-1]['ratio'] += .01
    else: s['consecutive']['기관']['days'] -= 1
    bank = claims.build_bank(s, e, m, gate2_passed=True)
    if field == 'consecutive': assert bank is None
    else:
        assert bank
        assert not any((field == 'ratio' and f.kind == 'strength' and f.subject == '외국인') or
                       (field == 'price' and f.kind == 'price' and f.subject == 'close') or
                       (field == 'ownership' and f.kind == 'ownership') for f in bank.facts)


@pytest.mark.parametrize('field,value', [('unit','%p'), ('subject','기관'), ('dates',('2026-01-01',)),
    ('sentence','임의 가격 999원'), ('values',(0,)), ('precision',7)])
def test_immutable_bank_rebuild_rejects_unit_subject_window_number_override(field, value):
    s, e, m, bank = bank_for()
    with pytest.raises(FrozenInstanceError): bank.facts = ()
    changed = replace(bank, facts=(replace(bank.facts[0], **{field: value}), *bank.facts[1:]))
    assert not claims.valid_bank(changed, m, s)
    with pytest.raises(claims.SelectionInvalid): claims.compose(changed, selected(changed), m, s)


def test_composition_fixed_three_paragraphs_and_order_gate3():
    s, e, m, bank = bank_for()
    ids = selected(bank, 'strength', 'price', 'ownership')
    text = claims.compose(bank, ids, m, s)
    assert text == claims.compose(bank, tuple(reversed(ids)), m, s) and len(text.split('\n\n')) == 3
    assert m['base_date'] in text and '개인 제외' in text
    assert verify_interpretation(text, s, bank=bank, selection=ids, meta=m).passed
    for bad in ('', text+' 추천 매수', text.replace(m['base_date'], '2099-01-01'), '외국인 순매수'):
        assert not verify_interpretation(bad, s, bank=bank, selection=ids, meta=m).passed
    assert not verify_interpretation(text, s).passed
    assert not verify_interpretation(text, s, bank=bank, selection=ids, meta=dict(m, ticker='000001')).passed


@pytest.mark.parametrize('raw', ['', ' ', '{', '```json\n{}\n```', 'null', '[]',
    '{"schema_version":true,"fact_ids":[]}', '{"schema_version":1.0,"fact_ids":[]}',
    '{"schema_version":1,"schema_version":1,"fact_ids":[]}',
    '{"schema_version":1,"fact_ids":[],"text":"override"}', 'x'*4097,
    '{"schema_version":1,"fact_ids":["unknown"]}', '{"schema_version":1,"fact_ids":[1]}',
    '{"schema_version":1,"fact_ids":["'+'x'*161+'"]}', '\ud800', None])
def test_strict_raw_schema_refusals(raw):
    bank = bank_for()[-1]
    with pytest.raises(claims.SelectionInvalid, match='^Invalid grounded selection$'):
        claims.parse_selection(raw, bank)


def test_selection_cardinality_duplicates_extra_and_exact_utf8_bytes():
    bank = bank_for()[-1]; ids = [f.id for f in bank.facts]
    for value in ({'schema_version':1, 'fact_ids':[]}, {'schema_version':1, 'fact_ids':[ids[0]]*2},
                  {'schema_version':1, 'fact_ids':ids[:9]}, {'schema_version':1, 'fact_ids':ids[:1], 'subject':'기관'}):
        with pytest.raises(claims.SelectionInvalid): claims.parse_selection(json.dumps(value), bank)
    raw = json.dumps(dict(schema_version=1, fact_ids=ids[:1]))
    padded = raw+' '*(4096-len(raw.encode()))
    assert claims.parse_selection(padded, bank) == (ids[0],)
    with pytest.raises(claims.SelectionInvalid): claims.parse_selection(padded+' ', bank)


def workflow_functions():
    tree = ast.parse((_AI/'agents/flow/application/workflow.py').read_text())
    names = {'_meta','explain_node','gate3_node','route_after_collect','route_after_gate3','_interpretation_evidence'}
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in nodes} == names
    assert not any(isinstance(n, (ast.Import, ast.ImportFrom)) for f in nodes for n in ast.walk(f))
    env = dict(SupplyDemandState=SupplyDemandState, config=CONFIG, build_bank=claims.build_bank,
        parse_selection=claims.parse_selection, compose=claims.compose, SelectionInvalid=claims.SelectionInvalid,
        verify_interpretation=verify_interpretation, math=math)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'<cf014-fixed-workflow-nodes>','exec'),env)
    return env


@pytest.mark.parametrize('responses,attempts,passed', [(['','',''],3,False), (['{','{','{'],3,False),
    (['invalid','valid'],2,True), (['valid'],1,True), (['','{','valid'],3,True)])
def test_actual_workflow_nodes_bounded_attempts_and_safe_payload_fallback(responses, attempts, passed):
    s,e,m,bank=bank_for();env=workflow_functions();calls=[]
    def fake(*args, **kwargs):
        assert kwargs['bank'] == bank
        raw=responses[len(calls)];calls.append(True)
        return json.dumps(dict(schema_version=1,fact_ids=selected(bank))) if raw=='valid' else raw
    env['explain']=fake
    state=SupplyDemandState(input=AgentInput(query='unused',stock_name=m['stock_name'],ticker=m['ticker']),
        base_date=date.fromisoformat(m['base_date']),signals=s,gate2=GateResult(gate=2,passed=True),fact_bank=bank)
    for _ in range(4):
        state=state.model_copy(update=env['explain_node'](state));state=state.model_copy(update=env['gate3_node'](state))
        if env['route_after_gate3'](state)=='render':break
    assert len(calls)==state.explain_attempts==attempts and state.explain_retries==attempts-1
    assert state.gate3.passed is passed
    payload=build_payload(s,m,None,state.gate2,state.gate3,state.interpretation,uuid4(),
                          regen_count=state.explain_retries,provider='fixture',model='synthetic')
    assert payload['signals']==s and payload['version']==1
    assert payload['verification']['regen_count']==attempts-1
    assert (payload['interpretation'] is not None)==passed
    if not passed:
        assert payload['interpretation_meta']==dict(source='fallback',provider=None,model=None)
        assert payload['verification']['outcome']=='fact_only'
        assert 'invalid' not in json.dumps(payload['verification'])


def test_provider_error_propagates_without_selection_retry():
    s,e,m,bank=bank_for();env=workflow_functions()
    def timeout(*args,**kwargs):raise TimeoutError('synthetic provider deadline')
    env['explain']=timeout
    state=SupplyDemandState(input=AgentInput(query='unused',stock_name=m['stock_name'],ticker=m['ticker']),
        base_date=date.fromisoformat(m['base_date']),signals=s,gate2=GateResult(gate=2,passed=True),fact_bank=bank)
    with pytest.raises(TimeoutError):env['explain_node'](state)


def test_collect_evidence_preserves_integer_scalar_and_unknown_denominator():
    class Column:
        def __init__(self, values):self.values=values
        def tolist(self):return self.values
    class Frame:
        index=[datetime(2026,9,1)]
        columns=('개인','외국인','기관','거래대금')
        def __getitem__(self,key):return Column([float('nan') if key=='거래대금' else 9007199254740993])
    result=workflow_functions()['_interpretation_evidence'](Frame(),None,None)
    assert result['supply'][0]['개인']==9007199254740993
    assert type(result['supply'][0]['개인']) is int
    assert result['supply'][0]['거래대금'] is None
    assert result['quotes'] is result['ownership'] is None


def test_actual_prompt_facts_function_excludes_user_text_and_binds_menu():
    tree=ast.parse((_AI/'agents/flow/infrastructure/llm/explain.py').read_text())
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_facts_to_text']
    assert len(nodes)==1
    env=dict(valid_bank=claims.valid_bank,SelectionInvalid=claims.SelectionInvalid)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'<cf014-fixed-facts-function>','exec'),env)
    s,e,m,bank=bank_for();text=env['_facts_to_text'](s,m,bank)
    assert '일평균 거래대금' in text and '관측 5행' in text and m['base_date'] in text
    for f in bank.facts:assert f.id in text and f.sentence in text
    with pytest.raises(claims.SelectionInvalid):env['_facts_to_text'](s,dict(m,base_date='2099-01-01'),bank)


def test_new_spec_hashes_runtime_fencing_and_calculation_body_unchanged():
    from src.modules.flow.domain import analysis as backend
    assert backend.SPEC==ai_schema.SPEC
    assert backend.SPEC['policy']==claims.POLICY_ID=='flow.fact-selection.v1'
    assert backend.SPEC['prompt']=='flow.explain.fact-selection.v1'
    for key,name in (('policy_sha256','domain/interpretation_claims.py'),('prompt_sha256','prompts/explain.txt'),('config_sha256','config.py')):
        assert hashlib.sha256((_AI/'agents/flow'/name).read_bytes()).hexdigest()==backend.SPEC[key]
    assert {k:backend.SPEC[k] for k in ('deadline_seconds','provider_timeout_seconds','sdk_retries','dispatch_retries','explain_regenerations','max_completion_tokens')}==dict(deadline_seconds=120,provider_timeout_seconds=20,sdk_retries=0,dispatch_retries=0,explain_regenerations=2,max_completion_tokens=1000)
    runtime=(_AI/'agents/flow/application/execution_runtime.py').read_text()
    assert "request.spec['policy_sha256']" in runtime and runtime.index("request.spec['policy_sha256']") < runtime.index('from .agent import run')
    explain=(_AI/'agents/flow/infrastructure/llm/explain.py').read_text()
    assert "'max_retries':0" in explain and "'max_completion_tokens':1000" in explain and "execution_context.timeout('openai')" in explain
    assert hashlib.sha256((_AI/'agents/flow/domain/signals.py').read_bytes()).hexdigest() == '15de1236f86a78a14e5d5106247d0329167e12eb390b29ebf97cd5cd012ae2be'


def test_rule2_actual_slice_uses_raw_subject_dates_and_threshold():
    source=(_AI/'agents/flow/domain/verification/signals.py').read_text()
    segment=source[source.index('    consecutive = signals.get("consecutive"'):source.index('    # ── 규칙 3:')]
    # This exact existing rule block is the only Gate2 code executed here.
    module=ast.parse('def rule(df,signals):\n    checks=[]\n    failures=[]\n'+segment+'    return checks,failures\n')
    env=dict(sig=SimpleNamespace(SUBJECTS=SUBJECTS),config=CONFIG,verify_consecutive=verify_consecutive)
    exec(compile(module,'<cf014-fixed-rule2>','exec'),env)
    class Column:
        def tolist(self):return [1,1,1]
    class Frame:
        index=[datetime(2026,1,i) for i in (1,2,3)]
        def __getitem__(self,key):assert key in SUBJECTS;return Column()
    value={'consecutive':{s:dict(days=3,signal=True) for s in SUBJECTS}}
    assert len(env['rule'](Frame(),value)[0])==3
    for bad in (True,-1,1.0,2,4,None):
        altered=copy.deepcopy(value);altered['consecutive']['외국인']['days']=bad
        checks,failures=env['rule'](Frame(),altered)
        assert len(checks)==2 and len(failures)==1
    assert 'calc_consecutive(' not in segment and 'consecutive_net_buy_days(' not in segment


def test_old_spec_stored_snapshot_keeps_original_id_json_hash_without_new_gate(monkeypatch):
    from src.modules.flow.domain import analysis as domain
    from src.modules.flow.application.analysis_adapter import FlowAnalysisAdapter
    from tests.fixtures.flow_payload import make_flow_payload
    old_spec={'engine': 'flow.graph.v1', 'model': 'gpt-5.4-mini', 'provider': 'openai', 'payload_schema': 1, 'input_schema': 1, 'prompt': 'flow.explain.v1', 'prompt_sha256': 'f2990926e5b8c95ebbc423aa40529476c3fe53981a67d3abbeb5f6f0096294c5', 'config_sha256': '91c95356110d0294051eb7871bfb06100ebd003ccb0f2da33c6add2b0594b637', 'config': 'flow.analysis.v1', 'deadline_seconds': 120, 'provider_timeout_seconds': 20, 'sdk_retries': 0, 'dispatch_retries': 0, 'explain_regenerations': 2, 'max_completion_tokens': 1000}
    as_of=datetime(2026,11,8,tzinfo=UTC)
    normalized=domain.canonical(dict(ticker='005930',question='합성 복구',as_of=as_of.isoformat()))
    row=SimpleNamespace(id=uuid4(),attempt_id=uuid4(),admission_request_id=uuid4(),owner_user_id=uuid4(),
        operation=domain.OPERATION,ticker='005930',stock_name='합성 종목',request_json=normalized,
        input_fingerprint=domain.sha(normalized),as_of=as_of,candidate_date=domain.candidate(as_of),
        deadline_at=as_of+timedelta(seconds=120),spec_json=domain.canonical(old_spec))
    request=domain.ai_request(row);payload=make_flow_payload();confirmed=payload['meta']['base_date']
    frames={name:[dict(date=confirmed,**{k:(0 if name=='supply' else None) for k in columns if k!='date'})]
            for name,columns in domain.UNITS.items()}
    snapshot=dict(schema_version=1,request=request,source='kis.boundary.frames.v1',observed_at=as_of.isoformat(),
                  confirmed_date=confirmed,units=copy.deepcopy(domain.UNITS),frames=frames)
    response=dict(schema_version=1,analysis_id=str(row.id),attempt_id=str(row.attempt_id),admission_request_id=str(row.admission_request_id),
        fingerprint=row.input_fingerprint,report_id=payload['report_id'],payload=payload,input_snapshot=snapshot,input_sha256=domain.sha(domain.canonical(snapshot)))
    adapter=FlowAnalysisAdapter(row,owner_user_id=row.owner_user_id);frozen=adapter.validate_and_freeze(response)
    row.input_json=frozen.input_json;row.result_json=frozen.result_json;row.input_sha256=frozen.input_sha256
    row.result_sha256=frozen.result_sha256;row.adopted_report_id=frozen.report_id
    def forbidden(*args,**kwargs):raise AssertionError('new policy must not reinterpret old bytes')
    monkeypatch.setattr(claims,'compose',forbidden);monkeypatch.setattr(domain,'SPEC',{'unsupported':'current'})
    assert adapter.from_stored(row)==frozen
    assert adapter.build_request()['spec']==old_spec and row.result_json==domain.canonical(payload)
    assert str(frozen.report_id)==payload['report_id'] and json.loads(frozen.result_json)['interpretation']=='합성 해석'
