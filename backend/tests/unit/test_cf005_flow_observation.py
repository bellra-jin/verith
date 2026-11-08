"""CF-005 pure evidence/facts/view tests, never pandas/Jinja/LLM/app imports."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_AI = _ROOT / "ai/src"
sys.path.append(str(_AI))
try:
    from agents.flow.domain import observation_window as window
finally:
    sys.path.remove(str(_AI))
_CASES = json.loads((_ROOT / "frontend/tests/fixtures/cf005-observation-cases.json").read_text())["cases"]
_SUBJECTS = ("개인", "외국인", "기관")


def extracted(relative, name):
    """Compile exactly the reviewed pure function, with no module imports/init."""
    tree = ast.parse((_AI / relative).read_text())
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name]
    assert len(nodes) == 1
    function = nodes[0]
    assert not function.decorator_list
    assert all(isinstance(n, ast.Constant) for n in function.args.defaults)
    forbidden = (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal, ast.Delete,
                 ast.With, ast.AsyncWith, ast.Await, ast.Yield, ast.YieldFrom, ast.ClassDef)
    pure_calls = {'observation_window','safe_daily','relation_text','finite_number','max','abs','round','type','len'}
    for node in ast.walk(function):
        assert not isinstance(node, forbidden)
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name): assert node.func.id in pure_calls
            else:
                assert isinstance(node.func, ast.Attribute) and node.func.attr in {'get','append','join','replace'}
        if isinstance(node, ast.Attribute):
            assert node.attr in {'get','append','join','replace','RECENT_DAYS','TREND_DAYS'}
        if isinstance(node, ast.Name):
            assert node.id not in {'open','exec','eval','compile','__import__','globals','locals','getattr'}
    environment = {'__builtins__': {'dict':dict,'list':list,'str':str,'float':float,'type':type,
                                   'max':max,'abs':abs,'round':round,'len':len},
                   'config':SimpleNamespace(RECENT_DAYS=5,TREND_DAYS=20), 'SUBJECTS':_SUBJECTS,
                   'observation_window':window.observation_window, 'safe_daily':window.safe_daily,
                   'relation_text':window.relation_text,'finite_number':window.finite_number}
    exec(compile(ast.Module(body=[function], type_ignores=[]), '<reviewed-pure-'+name+'>', 'exec'), environment)
    return environment[name]


@pytest.mark.parametrize('case',_CASES,ids=lambda c:c['name'])
def test_shared_window_evidence_counts_sign_and_no_mutation(case):
    source=copy.deepcopy(case['signals']); before=copy.deepcopy(source)
    result=window.observation_window(source,5,20)
    for key in ('status','shownRows','shortCount','longCount','relations'):
        assert result[key] == case['expected'][key]
    assert (window.safe_daily(source) is not None) == case['expected']['safeDaily']
    if result['status']=='unknown':
        assert '미확인' in result['notice'] and '비교 보류' in result['notice']
    elif result['status']=='insufficient':
        assert '부족' in result['notice'] and '비교 보류' in result['notice']
    else:
        assert '제공 자료 기준' in result['notice']
    assert result['interpretationNotice'].startswith('저장 당시 해석')
    assert source == before


@pytest.mark.parametrize('case',_CASES,ids=lambda c:c['name'])
def test_actual_facts_function_omits_unproven_persistence_and_preserves_input(case):
    source=copy.deepcopy(case['signals']); before=copy.deepcopy(source)
    function=extracted('agents/flow/infrastructure/llm/explain.py','_facts_to_text')
    facts=function(source,{'stock_name':'합성종목','ticker':'000000','base_date':'2026-01-20'})
    evidence=window.observation_window(source,5,20)
    assert evidence['notice'] in facts
    if evidence['status']!='sufficient_rows':
        assert '순매수 합' not in facts and '억원' not in facts
        assert '지속성 비교 보류' in facts
    else:
        assert '제공 자료 기준 단기 제공 5개 순매수 합' in facts
        for subject in _SUBJECTS: assert window.relation_text(evidence['relations'][subject]) in facts
    assert source==before


@pytest.mark.parametrize('case',_CASES,ids=lambda c:c['name'])
def test_actual_daily_and_persistence_views_are_safe_before_warning(case):
    source=copy.deepcopy(case['signals']); before=copy.deepcopy(source)
    daily=extracted('agents/flow/infrastructure/render/builder.py','_daily_view')(source)
    persist=extracted('agents/flow/infrastructure/render/builder.py','_persistence_view')(source)
    evidence=window.observation_window(source,5,20)
    assert (daily is not None)==case['expected']['safeDaily']
    if daily:
        assert [row['iso'] for row in daily]==[row['date'] for row in source['daily']]
        for row,raw in zip(daily,source['daily']):
            for bar,subject in zip(row['bars'],_SUBJECTS):
                assert bar['val']==f"{raw[subject]:+,.0f}"
                if raw[subject]==0: assert bar['h']==0
    assert len(persist['rows'])==3
    if evidence['status']!='sufficient_rows':
        assert persist['verdict']=='' and all(r['consistent'] is None for r in persist['rows'])
    claims=source.get('persistence')
    for row,subject in zip(persist['rows'],_SUBJECTS):
        claim=claims.get(subject) if type(claims) is dict else None
        for key,output in [('sum_5','d5'),('sum_20','d20')]:
            raw=claim.get(key) if type(claim) is dict else None
            if window.finite_number(raw): assert row[output]['val']==f"{raw:+,.0f}"
            else: assert row[output]['val']=='자료 없음' and not row[output]['available']
    assert source==before


@pytest.mark.parametrize('bad',[float('nan'),float('inf'),-float('inf'),True,'1',None,10**1000])
@pytest.mark.parametrize('where',['cell','short','long'])
def test_non_json_numbers_are_unknown_and_display_never_formats_them(bad,where):
    source=copy.deepcopy(_CASES[4]['signals'])
    if where=='cell': source['daily'][0]['개인']=bad
    else: source['persistence']['개인']['sum_5' if where=='short' else 'sum_20']=bad
    assert window.observation_window(source,5,20)['status']=='unknown'
    daily=extracted('agents/flow/infrastructure/render/builder.py','_daily_view')(source)
    persist=extracted('agents/flow/infrastructure/render/builder.py','_persistence_view')(source)
    if where=='cell': assert daily is None
    else: assert persist['rows'][0]['d5' if where=='short' else 'd20']['val']=='자료 없음'


@pytest.mark.parametrize('short,long',[(0,20),(True,20),(5,False),(6,5),(5,21)])
def test_invalid_display_windows_are_unknown(short,long):
    assert window.observation_window(_CASES[4]['signals'],short,long)['status']=='unknown'


@pytest.mark.parametrize('value,valid',[('2024-02-29',True),('0001-01-01',True),('9999-12-31',True),
                                      ('0000-01-01',False),('2026-02-29',False),('2026-01-01T00:00:00Z',False)])
def test_canonical_calendar_dates(value,valid):
    assert window.iso_date(value) is valid


def test_helper_exact_origin_stdlib_and_source_only_html_wiring():
    source=_AI/'agents/flow/domain/observation_window.py'
    assert Path(window.__spec__.origin).resolve()==source.resolve()
    tree=ast.parse(source.read_text())
    imports={n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)} | {a.name for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names}
    assert imports=={'datetime','math'}
    assert all(isinstance(n,(ast.Import,ast.ImportFrom,ast.FunctionDef,ast.Assign)) or isinstance(n,ast.Expr) and isinstance(n.value,ast.Constant) for n in tree.body)
    assert not any(isinstance(n,ast.Attribute) and n.attr in {'home','getenv','environ'} for n in ast.walk(tree))
    html=(_AI/'agents/flow/infrastructure/render/templates/supply_demand.html').read_text()
    assert '{{ observation.notice }}' in html and '{{ observation.dailyLabel }}' in html
    assert 'observation.status == "sufficient_rows" and r.consistent' in html
    assert html.index('{{ observation.interpretationNotice }}')<html.index('{{ interpretation_html }}')
    assert '저장 당시 수치·해석 대조 결과이며 기간 충족 보증이 아닙니다.' in html
    assert '최근 {{ trend_days }}거래일' not in html
    prompt=(_AI/'agents/flow/prompts/explain.txt').read_text()
    assert '관측 안내가 부족/미확인이면 지속성 비교를 보류' in prompt


_GOLDEN_SOURCE = {'verification': '9f20f1ba75b47a8bf0002cea3ad9bdcd1ed4f2bcd5786fe93c0a98171c94c53d', 'old_check': "checks.append(f'지속성 정합: {subject} 5일·20일 합과 일관 판정이 원본과 일치')", 'explain': 'f10f6f254a13260762727565ffb595750553e34109e64d7fc06ada3b1b35ec09', 'builder': {'_gauge': '0456f637c4db565b6ecafadf52e92e863cee169c566248842c9456ddc35731e2', '_ownership_view': '639abfb0516c663c07f291e7284b6d4963ff6fccac66fbf9fe4edbd8fa86d220', '_inst_detail_view': 'fe3bab8772205da2afb41b78a78eec1772ba1a863f23033386b115e935221329', '_price_table_view': '2b6e8fff8f19a8e045e05992f01d2c3bbdfdcf6a32498805604f685eb28a828a', '_interpretation_html': '3258cfbcc5fcdd5232dd52f7f86a3b38f16742fdcb3244132135163abd02eda5', '_header_price': '094dc3fca5a4cfbffe66abcee88b023726b9f5fde64a7f2e846199f8acc56bc5', '_headline': '38835d5212b97f68032330f19fa414f636006ab16df385f2f85658f4b2618fec', 'build_report': '7fa18b4976843e22ae40e9f4c906d3efa722c5f9ed79e26eab23ba1ea68901da'}}

def test_gate2_conditions_and_llm_execution_are_unchanged():
    tree=ast.parse((_AI/'agents/flow/domain/verification/signals.py').read_text())
    count=[]
    class OriginalSuccessText(ast.NodeTransformer):
        def visit_Call(self,node):
            node=self.generic_visit(node)
            if isinstance(node.func,ast.Attribute) and node.func.attr=='append' and '기간 충족 검사 아님' in ast.unparse(node):
                count.append(True)
                return ast.parse(_GOLDEN_SOURCE['old_check']).body[0].value
            return node
    projected=OriginalSuccessText().visit(tree)
    assert count==[True]
    assert hashlib.sha256(ast.dump(projected).encode()).hexdigest()==_GOLDEN_SOURCE['verification']
    tree=ast.parse((_AI/'agents/flow/infrastructure/llm/explain.py').read_text())
    actual=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='explain')
    assert hashlib.sha256(ast.dump(actual).encode()).hexdigest()==_GOLDEN_SOURCE['explain']


def test_unrelated_builder_numeric_and_stored_interpretation_paths_unchanged():
    tree=ast.parse((_AI/'agents/flow/infrastructure/render/builder.py').read_text())
    functions={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
    for name,expected in _GOLDEN_SOURCE['builder'].items():
        node=copy.deepcopy(functions[name])
        if name=='build_report':
            node.body=[n for n in node.body if not (isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='observation' for t in n.targets))]
            for mapping in [n for n in ast.walk(node) if isinstance(n,ast.Dict)]:
                pairs=[(k,v) for k,v in zip(mapping.keys,mapping.values) if not isinstance(k,ast.Constant) or k.value!='observation']
                mapping.keys=[k for k,v in pairs];mapping.values=[v for k,v in pairs]
            for call in [n for n in ast.walk(node) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='_persistence_view']:
                assert len(call.args)==2 and isinstance(call.args[-1],ast.Name) and call.args[-1].id=='observation'
                call.args.pop()
        assert hashlib.sha256(ast.dump(node).encode()).hexdigest()==expected,name
