"""Exact pure render slices + shared fixtures; never import builder/Jinja/config."""
import ast,copy,json,math
from pathlib import Path
from types import SimpleNamespace
import pytest
from tests.unit.test_cf014_flow_quality import fixture as _fixture
from tests.unit.test_cf014_flow_quality import test_full_source_counts_strength_definition_and_windows as _counts
from tests.unit.test_cf014_flow_quality import test_unknown_persistence_no_fact_and_actual_confirmed_date_not_candidate as _unknown
from agents.flow.domain.observation_window import finite_number,observation_window,relation_text,safe_daily

ROOT=Path(__file__).resolve().parents[3]
NAMES={'_display_number','_record','_direction','_fact_rows','_gauge','_daily_view','_persistence_view','_ownership_view','_inst_detail_view','_price_table_view','_header_price','_headline'}
source=(ROOT/'ai/src/agents/flow/infrastructure/render/builder.py').read_text();tree=ast.parse(source)
functions=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in NAMES]
assert {node.name for node in functions}==NAMES
namespace=dict(finite_number=finite_number,observation_window=observation_window,relation_text=relation_text,safe_daily=safe_daily,
 SUBJECTS=('개인','외국인','기관'),COL_FORE='외국인',COL_INST='기관',_DETAIL_DISPLAY=('기금','증권','투자신탁','사모펀드','보험'),
 _DETAIL_LABELS={'기금':'기금(연기금)','증권':'증권(금융투자)'},config=SimpleNamespace(RECENT_DAYS=5,TREND_DAYS=20))
exec(compile(ast.Module(body=functions,type_ignores=[]),'<cf019-fixed-render-slices>','exec'),namespace)
CASES=json.loads((ROOT/'frontend/tests/fixtures/cf019-flow-display-cases.json').read_text())

@pytest.mark.parametrize('item',CASES['numbers'],ids=lambda c:c['name'])
def test_shared_numbers(item):
 before=copy.deepcopy(item)
 assert namespace['_display_number'](item['value'],item['precision'],item['unit'],item['scale'])==item['expected']
 assert item==before

@pytest.mark.parametrize('item',CASES['gauges'])
def test_shared_gauge(item):
 s={'strength':{'외국인':{'ratio':item['fore']},'기관':{'ratio':item['inst']}}};before=copy.deepcopy(s)
 assert namespace['_gauge'](s)['verdict']==item['expected'] and s==before

@pytest.mark.parametrize('item',CASES['institutions'])
def test_institution_partial_scope(item):
 value=namespace['_inst_detail_view']({'inst_detail':dict(zip(('기금','증권'),item['values']))})
 assert (value['leader'] if value else None)==item['expected']

@pytest.mark.parametrize('bad',[math.nan,math.inf,-math.inf,False,'1',None])
def test_invalid_cells_never_become_neutral_or_zero(bad):
 s={'strength':{'외국인':{'ratio':bad},'기관':{'ratio':1}},'consecutive':{'개인':{'days':bad}}}
 assert namespace['_gauge'](s)['verdict']=='판단 보류'
 rows=namespace['_fact_rows'](s);assert rows[0]['days'] is None and rows[1]['direction']=='판단 보류'
 assert namespace['_display_number'](bad)=='자료 없음'

@pytest.mark.parametrize('count',[1,19,20])
def test_existing_CF014_window_contract(count):_counts(count)

def test_existing_unknown_window_and_actual_confirmed_date():_unknown()

def test_table_cells_and_raw_sign_underflow_leave_input_unchanged():
 s={'daily':[{'date':'2026-11-06','개인':5e-324,'외국인':-5e-324,'기관':0}],
 'price_daily':[{'date':'2026-11-06','close':1000,'change':-5e-324,'change_rate':math.nan,'volume':False,'inst_qty':None,'frgn_qty':0}],
 'ownership':[{'date':'2026-11-06','ratio':5e-324}]}
 original=copy.deepcopy(s)
 assert '음수·표시 정밀도 미만' in namespace['_header_price'](s)['chg']
 assert namespace['_price_table_view'](s)[0]['vol']=='자료 없음'
 assert '양수·표시 정밀도 미만' in namespace['_ownership_view'](s)['latest']
 assert namespace['_daily_view'](s)[0]['bars'][2]['cls']=='mut'
 assert s['daily']==original['daily'] and s['price_daily'][0]['change']==original['price_daily'][0]['change']

def test_HTML_source_discloses_zero_and_partial_scope_without_Jinja_execution():
 text=(ROOT/'ai/src/agents/flow/infrastructure/render/templates/supply_demand.html').read_text()
 for phrase in ('일평균 거래대금 대비 강도','분모 미확인','100%','r.days is not none'):assert phrase in text
 assert 'payload' not in NAMES and 'build_report' not in NAMES


@pytest.mark.parametrize('count',[1,19,20])
def test_actual_render_slices_preserve_windows_dates_subjects_units_and_input(count):
 s,e,meta=_fixture(count);before=copy.deepcopy((s,e,meta))
 window=observation_window(s,5,20)
 rendered=namespace['_persistence_view'](s)
 assert window['status']==('sufficient_rows' if count==20 else 'insufficient')
 assert (window['shortCount'],window['longCount'])==(min(count,5),count)
 assert window['shortLabel']==f'단기 제공 {min(count,5)}개'
 assert window['longLabel']==f'장기 제공 {count}개'
 assert [row['name'] for row in rendered['rows']]==['개인','외국인','기관']
 for row,subject in zip(rendered['rows'],('개인','외국인','기관')):
  for key,cell in [('sum_5','d5'),('sum_20','d20')]:
   assert row[cell]['val']==namespace['_display_number'](s['persistence'][subject][key])
   assert row[cell]['available'] is True
  assert row['consistent'] is (True if count==20 else None)
 if count==20:
  assert rendered['verdict']=='개인은 단기·장기 모두 순매수 · 외국인은 단기·장기 모두 순매도 · 기관은 단기·장기 모두 순매수'
 else:assert rendered['verdict']==''
 rows=namespace['_fact_rows'](s)
 assert namespace['_headline'](rows)=='개인·기관이 사고, 외국인이 파는 국면'
 assert [r['amt'] for r in rows]==[namespace['_display_number'](s['persistence'][x]['sum_5'],1,'억원',.01) for x in ('개인','외국인','기관')]
 daily=namespace['_daily_view'](s)
 assert [r['iso'] for r in daily]==[r['date'] for r in s['daily']]
 assert daily[-1]['iso']==meta['base_date']
 assert [bar['subject'] for bar in daily[-1]['bars']]==['개인','외국인','기관']
 assert [bar['val'] for bar in daily[-1]['bars']]==['+1','-2','+3']
 # A candidate/request date is not substituted into the actual daily display.
 candidate={**meta,'base_date':'2099-12-31'}
 assert namespace['_daily_view'](s)[-1]['iso']!=candidate['base_date']
 assert (s,e,meta)==before


@pytest.mark.parametrize('kind',['duplicate','reversed','invalid-date','missing-subject','missing-sum'])
def test_actual_render_slices_fail_closed_without_sorting_filling_or_mutating(kind):
 s,_,_=_fixture(20)
 if kind=='duplicate':s['daily'][-1]['date']=s['daily'][-2]['date']
 elif kind=='reversed':s['daily'].reverse()
 elif kind=='invalid-date':s['daily'][-1]['date']='2026-02-30'
 elif kind=='missing-subject':del s['daily'][-1]['기관']
 else:del s['persistence']['기관']['sum_5']
 before=copy.deepcopy(s);window=observation_window(s,5,20)
 rendered=namespace['_persistence_view'](s,window)
 assert window['status']=='unknown' and rendered['verdict']==''
 assert all(row['consistent'] is None for row in rendered['rows'])
 if kind=='missing-sum':
  assert rendered['rows'][2]['d5']['val']=='자료 없음'
  assert rendered['rows'][2]['d5']['available'] is False
  assert namespace['_fact_rows'](s)[2]['amt'] is None
 else:assert namespace['_daily_view'](s) is None
 assert s==before


def test_actual_headline_uses_only_available_stored_subject_directions():
 s={'strength':{'개인':{'ratio':None},'외국인':{'ratio':False},'기관':{'ratio':'1'}}}
 before=copy.deepcopy(s)
 assert namespace['_headline'](namespace['_fact_rows'](s))=='자료 부족으로 방향 판단 보류'
 s['strength']['외국인']['ratio']=-1
 assert namespace['_headline'](namespace['_fact_rows'](s))=='외국인 매도 국면'
 s['strength']['외국인']['ratio']=False
 assert s==before
