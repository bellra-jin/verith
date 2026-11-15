"""CF-005 pure evidence/facts/view tests, never pandas/Jinja/LLM/app imports."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

from tests.unit.test_cf014_flow_quality import fixture as evidence_fixture, claims

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
    dependencies = {'_daily_view': {'_display_number'}, '_persistence_view': {'_display_number'}}
    names = {name, *dependencies.get(name, set())}
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in nodes} == names
    function = next(n for n in nodes if n.name == name)
    assert not function.decorator_list
    assert all(isinstance(n, ast.Constant) for n in function.args.defaults)
    forbidden = (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal, ast.Delete,
                 ast.With, ast.AsyncWith, ast.Await, ast.Yield, ast.YieldFrom, ast.ClassDef)
    pure_calls = {'observation_window','safe_daily','relation_text','finite_number','max','abs','round','type','len','float','valid_bank','SelectionInvalid','_display_number'}
    for node in ast.walk(ast.Module(body=nodes, type_ignores=[])):
        assert not isinstance(node, forbidden)
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name): assert node.func.id in pure_calls
            else:
                assert isinstance(node.func, ast.Attribute) and node.func.attr in {'get','append','join','replace','extend'}
        if isinstance(node, ast.Attribute):
            assert node.attr in {'get','append','join','replace','extend','RECENT_DAYS','TREND_DAYS','skeleton','notice','facts','id','sentence'}
        if isinstance(node, ast.Name):
            assert node.id not in {'open','exec','eval','compile','__import__','globals','locals','getattr'}
    environment = {'__builtins__': {'dict':dict,'list':list,'str':str,'float':float,'type':type,
                                   'max':max,'abs':abs,'round':round,'len':len,'OverflowError':OverflowError},
                   'config':SimpleNamespace(RECENT_DAYS=5,TREND_DAYS=20), 'SUBJECTS':_SUBJECTS,
                   'observation_window':window.observation_window, 'safe_daily':window.safe_daily,
                   'relation_text':window.relation_text,'finite_number':window.finite_number,
                   'valid_bank':claims.valid_bank,'SelectionInvalid':claims.SelectionInvalid}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), '<reviewed-pure-'+name+'>', 'exec'), environment)
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
def test_display_only_signals_cannot_issue_a_prompt_fact_menu(case):
    source=copy.deepcopy(case['signals']); before=copy.deepcopy(source)
    # CF014 requires raw independently verified evidence. Display rows alone
    # cannot recreate the raw observations, consecutive history or fact IDs.
    meta={'stock_name':'합성종목','ticker':'000000','base_date':'2026-01-20'}
    bank=claims.build_bank(source,{},meta,gate2_passed=True)
    assert bank is None
    function=extracted('agents/flow/infrastructure/llm/explain.py','_facts_to_text')
    with pytest.raises(claims.SelectionInvalid,match='^Invalid grounded selection$'):
        function(source,meta,bank)
    assert source==before


@pytest.mark.parametrize('count',[1,4,5,19,20])
def test_actual_facts_menu_preserves_verified_windows_and_input(count):
    source,evidence,meta=evidence_fixture(count)
    before=copy.deepcopy((source,evidence,meta))
    bank=claims.build_bank(source,evidence,meta,gate2_passed=True)
    assert bank is not None and claims.valid_bank(bank,meta,source)
    facts=extracted('agents/flow/infrastructure/llm/explain.py','_facts_to_text')(source,meta,bank)
    assert bank.notice in facts and meta['base_date'] in facts
    assert all(f'{fact.id} | {fact.sentence}' in facts for fact in bank.facts)
    persistence=[fact for fact in bank.facts if fact.kind=='persistence']
    assert bool(persistence)==(count==20)
    if count<20: assert '비교 보류' in facts
    for fact in persistence:
        assert len(fact.dates)==20 and fact.subject in _SUBJECTS
    assert (source,evidence,meta)==before


def expected_display(value):
    """CF019 sign-preserving display contract, independently expected here."""
    if not window.finite_number(value): return '자료 없음'
    magnitude=f'{abs(value):,.0f}'
    if value and float(magnitude.replace(',',''))==0:
        return ('양수' if value>0 else '음수')+'·표시 정밀도 미만()'
    return ('+' if value>0 else '-' if value<0 else '')+magnitude


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
                assert bar['val']==expected_display(raw[subject])
                if raw[subject]==0: assert bar['h']==0
    assert len(persist['rows'])==3
    if evidence['status']!='sufficient_rows':
        assert persist['verdict']=='' and all(r['consistent'] is None for r in persist['rows'])
    claims=source.get('persistence')
    for row,subject in zip(persist['rows'],_SUBJECTS):
        claim=claims.get(subject) if type(claims) is dict else None
        for key,output in [('sum_5','d5'),('sum_20','d20')]:
            raw=claim.get(key) if type(claim) is dict else None
            if window.finite_number(raw): assert row[output]['val']==expected_display(raw)
            else: assert row[output]['val']=='자료 없음' and not row[output]['available']
    assert source==before


@pytest.mark.parametrize('bad',[float('nan'),float('inf'),-float('inf'),True,'1',None,10**1000],
                         ids=['nan','inf','negative-inf','bool','string','null','overflow-int'])
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
    assert '부족/불명 자료로 지속성' in prompt
    assert 'fact_ids' in prompt and '문장은 코드가 구성한다' in prompt


def persistence_rule_ast():
    source=(_AI/'agents/flow/domain/verification/signals.py').read_text()
    # Execute only the existing rule5 block, with a fixed raw-data protocol.
    start=source.index('    persistence = signals.get("persistence")')
    end=source.index('    # ── 규칙 6:',start)
    node=ast.parse('def rule(signals,recent,trend):\n    checks=[]\n    failures=[]\n'+source[start:end]+'    return checks,failures\n')
    validate_persistence_ast(node)
    return node


def validate_persistence_ast(node):
    forbidden=(ast.Import,ast.ImportFrom,ast.Global,ast.Nonlocal,ast.Delete,ast.With,
               ast.AsyncWith,ast.Await,ast.Yield,ast.YieldFrom,ast.ClassDef)
    for child in ast.walk(node):
        assert not isinstance(child,forbidden)
        if isinstance(child,ast.Call):
            if isinstance(child.func,ast.Name): assert child.func.id in {'float','bool','len'}
            else:
                assert isinstance(child.func,ast.Attribute)
                assert child.func.attr in {'get','sum','tail','append','isclose'}
        if isinstance(child,ast.Attribute):
            assert child.attr in {'get','sum','tail','append','isclose','SUBJECTS','TREND_DAYS'}
        if isinstance(child,ast.Name): assert not child.id.startswith('__')


@pytest.mark.parametrize('call',["open('unapproved')","exec('unapproved')","math.unapproved()"])
def test_persistence_source_drift_rejected_before_execution(call):
    node=persistence_rule_ast()
    node.body[0].body.insert(0,ast.parse(call).body[0])
    with pytest.raises(AssertionError):validate_persistence_ast(node)


def test_gate2_persistence_compares_raw_sums_signs_and_never_claims_coverage():
    node=persistence_rule_ast()
    import math
    env={'__builtins__':{'float':float,'bool':bool,'len':len},
         'sig':SimpleNamespace(SUBJECTS=_SUBJECTS),'math':math}
    exec(compile(node,'<reviewed-persistence-rule>','exec'),env)
    class Column:
        def __init__(self,value): self.value=value
        def sum(self): return self.value
    class Frame:
        def __init__(self,count,value): self.count,self.value=count,value
        def __len__(self): return self.count
        def __getitem__(self,subject):
            assert subject in _SUBJECTS
            return Column(self.value)
        def tail(self,count):
            assert count==20
            return self
    env['config']=SimpleNamespace(TREND_DAYS=20)
    env['df']=Frame(19,19)
    valid={'persistence':{s:dict(sum_5=5,sum_20=19,consistent=True) for s in _SUBJECTS}}
    checks,failures=env['rule'](valid,Frame(5,5),Frame(19,19))
    assert not failures and len(checks)==3
    assert all('5행/19행' in text and '기간 충족 검사 아님' in text for text in checks)
    for field,value in [('sum_5',6),('sum_20',20),('consistent',False)]:
        changed=copy.deepcopy(valid);changed['persistence']['외국인'][field]=value
        checks,failures=env['rule'](changed,Frame(5,5),Frame(19,19))
        assert len(checks)==2 and len(failures)==1 and '외국인' in failures[0]


def test_current_fact_selection_prompt_and_execution_use_the_verified_bank():
    tree=ast.parse((_AI/'agents/flow/infrastructure/llm/explain.py').read_text())
    function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='explain')
    calls=[n for n in ast.walk(function) if isinstance(n,ast.Call)]
    facts=next(n for n in calls if isinstance(n.func,ast.Name) and n.func.id=='_facts_to_text')
    assert [n.id for n in facts.args]==['signals','meta','bank']
    construct=next(n for n in calls if isinstance(n.func,ast.Name) and n.func.id=='ChatOpenAI')
    invoke=next(n for n in calls if isinstance(n.func,ast.Attribute) and n.func.attr=='invoke')
    gate=function.body[1] if isinstance(function.body[0],ast.Expr) else function.body[0]
    assert isinstance(gate,ast.If) and ast.unparse(gate.test)=='not gate2.passed'
    assert any(isinstance(n,ast.Raise) for n in ast.walk(gate))
    assert gate.lineno<facts.lineno<construct.lineno<invoke.lineno
    s,e,m=evidence_fixture(20);bank=claims.build_bank(s,e,m,gate2_passed=True)
    function=extracted('agents/flow/infrastructure/llm/explain.py','_facts_to_text')
    changed=copy.deepcopy(s);changed['persistence']['외국인']['sum_20']+=1
    for signals,meta in [(changed,m),(s,{**m,'base_date':'2099-01-01'})]:
        with pytest.raises(claims.SelectionInvalid): function(signals,meta,bank)


def test_render_context_preserves_observation_and_stored_interpretation():
    tree=ast.parse((_AI/'agents/flow/infrastructure/render/builder.py').read_text())
    functions={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
    for node in ast.walk(functions['build_report']):
        assert not isinstance(node,(ast.Import,ast.ImportFrom,ast.Global,ast.Nonlocal,ast.With,ast.AsyncWith,
                                    ast.Await,ast.Yield,ast.YieldFrom,ast.ClassDef,ast.Delete))
        if isinstance(node,ast.Call):
            if isinstance(node.func,ast.Name):
                assert node.func.id in {'_fact_rows','observation_window','_gauge','_headline',
                    '_interpretation_html','_daily_view','_persistence_view','_inst_detail_view',
                    '_ownership_view','_price_table_view','_header_price'}
            else:
                assert isinstance(node.func,ast.Attribute) and node.func.attr in {'get','get_template','render'}
        if isinstance(node,ast.Attribute):
            assert node.attr in {'get','get_template','render','RECENT_DAYS','TREND_DAYS','PRICE_TABLE_DAYS',
                                 'CONSECUTIVE_THRESHOLD','STRENGTH_THRESHOLD'}
        if isinstance(node,ast.Name):assert not node.id.startswith('__')
    # This escaping/markup function really is unchanged; retain its old pin.
    assert hashlib.sha256(ast.dump(functions['_interpretation_html']).encode()).hexdigest()==\
        '3258cfbcc5fcdd5232dd52f7f86a3b38f16742fdcb3244132135163abd02eda5'
    seen=[]
    class Template:
        def render(self,**context): seen.append(context);return 'synthetic-render'
    class Environment:
        def get_template(self,name): assert name=='fixed-template';return Template()
    markers={name:object() for name in ['rows','gauge','headline','daily','persistence','inst_detail','ownership','price_table','header_price']}
    inputs={'daily':[]};meta={'market':'synthetic'};gate1=object();gate2=object();interpretation='<b>stored text</b>'
    observation=object();safe_html=object()
    def unchanged(value): assert value is inputs
    env={'__builtins__':{},'dict':dict,'str':str,'GateResult':object,'_env':Environment(),'_TEMPLATE_NAME':'fixed-template',
         'config':SimpleNamespace(RECENT_DAYS=5,TREND_DAYS=20,PRICE_TABLE_DAYS=10,CONSECUTIVE_THRESHOLD=3,STRENGTH_THRESHOLD=.12)}
    def observe(value,recent,trend):
        unchanged(value);assert (recent,trend)==(5,20);return observation
    def persist(value,window):
        unchanged(value);assert window is observation;return markers['persistence']
    def interpreted(text): assert text is interpretation;return safe_html
    env.update(observation_window=observe,_persistence_view=persist,_interpretation_html=interpreted)
    for name,key in [('_fact_rows','rows'),('_gauge','gauge'),('_daily_view','daily'),('_inst_detail_view','inst_detail'),
                     ('_ownership_view','ownership'),('_price_table_view','price_table'),('_header_price','header_price')]:
        def read(value,key=key): unchanged(value);return markers[key]
        env[name]=read
    def headline(rows): assert rows is markers['rows'];return markers['headline']
    env['_headline']=headline
    exec(compile(ast.Module(body=[functions['build_report']],type_ignores=[]),'<reviewed-render-context>','exec'),env)
    assert env['build_report'](inputs,gate2,meta,interpretation,gate1)=='synthetic-render'
    context=seen.pop();assert not seen
    assert all(context[k] is v for k,v in markers.items())
    assert context['observation'] is observation and context['interpretation'] is interpretation
    assert context['interpretation_html'] is safe_html and context['meta'] is meta
    assert context['gate1'] is gate1 and context['gate2'] is gate2 and inputs=={'daily':[]}
