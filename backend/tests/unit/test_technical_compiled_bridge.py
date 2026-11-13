"""Exact copied compiled graph with fake LLM/OHLCV; no provider or DB."""
import asyncio
import copy
import hashlib
import importlib.abc
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import sys
import threading
from types import ModuleType
from uuid import UUID,uuid4

import pytest

ROOT = Path(__file__).resolve().parents[3]
from scripts.check_safe import GRAPH_INPUTS
for relative, digest in GRAPH_INPUTS.items():
    assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest() == digest

# The worker installed file/network/process guards BEFORE this collection.
# Only copied sources can be discovered; no original checkout is on sys.path.
sys.path.insert(0,str(ROOT/'ai'))
FORBIDDEN = ('openai','langchain_openai','redis','src.api','src.main',
             'src.agents.fundamental','src.agents.industry','src.agents.news',
             'src.shared.config','sqlalchemy','asyncpg')
ATTEMPTS = []
# Only the fixed SDK wire regression below may import the already snapshotted
# SDK package, on its own thread, while OS file/network/process guards remain.
_SDK_TEST_SCOPE = threading.local()
class ImportSentinel(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        sdk_root=getattr(_SDK_TEST_SCOPE,'root',None)
        if sdk_root is not None and (fullname=='openai' or fullname.startswith('openai.')):
            spec=importlib.machinery.PathFinder.find_spec(fullname,path)
            if spec is None or spec.origin is None or not Path(spec.origin).resolve().is_relative_to(sdk_root):
                raise AssertionError('Pinned SDK source origin rejected')
            return spec
        if any(fullname == name or fullname.startswith(name+'.') for name in FORBIDDEN):
            ATTEMPTS.append(fullname)
            raise AssertionError('External capability import prohibited')
sys.meta_path.insert(0,ImportSentinel())


def namespace(name, location):
    if name in sys.modules:
        return sys.modules[name]
    module=ModuleType(name)
    module.__spec__=importlib.machinery.ModuleSpec(name,None,is_package=True)
    module.__spec__.submodule_search_locations=[str(location)]
    module.__path__=[str(location)]
    sys.modules[name]=module
    parent,_,leaf=name.rpartition('.')
    if parent in sys.modules:setattr(sys.modules[parent],leaf,module)
    return module

# Preserve the unchanged worker's six pure Flow input and origin invariant.
for name in ('agents','agents.flow','agents.flow.api','agents.flow.domain',
             'agents.flow.domain.verification','agents.flow.infrastructure'):
    namespace(name,(ROOT/'ai/src').joinpath(*name.split('.')))
for suffix in ('domain.observation_window','domain.verification.consecutive',
               'domain.interpretation_claims','domain.models','api.payload','infrastructure.token_cache'):
    name='agents.flow.'+suffix
    path=ROOT/'ai/src/agents/flow'/ (suffix.replace('.','/')+'.py')
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)

# Synthetic settings only. Initialize once BEFORE pipeline imports; no reload or
# mutation of copied module flags. Worker blocks every .env open and all network.
os.environ.update(INTRADAY_FETCH_ENABLED='false',TECHNICAL_TRACE_ENABLED='false',
                  LANGCHAIN_TRACING_V2='false',LANGSMITH_TRACING='false')
from src.agents.technical import config
snapshot=config.initialize_runtime(settings=config.RuntimeSettings(False,False,str(Path(os.environ['TMPDIR'])/'unused-technical-trace.jsonl')))
assert snapshot.intraday_fetch_enabled is False and snapshot.trace_enabled is False
namespace('tests',ROOT/'backend/tests')
namespace('tests.technical',ROOT/'ai/tests/technical')
# urllib3's import-only platform probe otherwise binds ::1:0, even with
# tracing disabled. Model an IPv4-only platform before importing dependencies;
# this prevents the probe rather than granting a network capability.
import socket
from unittest.mock import patch
with patch.object(socket,'has_ipv6',False):
    from tests.technical import test_technical_supervisor as st
    from tests.technical import test_technical_langgraph as graph_fixtures
from src.agents.technical.application.agent import run_technical_agent
from src.agents.technical.application.engine_bridge import TechnicalEngineBridge
from src.agents.technical.application import boundary_runtime as runtime
from src.agents.technical.domain import boundary_contracts as contract
from src.shared.contracts.agent_envelope import SCHEMA_VERSION


for module in (st,graph_fixtures,config):
    assert Path(module.__spec__.origin).resolve().is_relative_to(ROOT/'ai')


def request():
    ids=[str(UUID(int=index)) for index in range(1,7)]
    data=dict(operation=contract.OPERATION,context=dict(zip(
        ('analysis_id','admission_request_id','attempt_id','report_id'),ids[2:])),
        original_query='LG에너지솔루션 차트',stock=dict(stock_code=st.TICKER,stock_name='LG에너지솔루션',market='KOSPI'),
        requested_views=['technical'],requested_as_of='2026-06-30T05:30:00+00:00',
        conditions=dict(profile=contract.PROFILE,periods=list(contract.PERIODS)))
    data['context']['input_fingerprint']=contract.fingerprint(data)
    return dict(schema_version=SCHEMA_VERSION,request_id=ids[0],trace_id=ids[1],data=data,error=None)


@pytest.mark.parametrize('case,expected',[
    ('normal','normal'),('data_limited','data_limited'),('regime_unavailable','regime_unavailable')])
async def test_real_compiled_graph_through_thread_bridge_and_strict_completion(case,expected):
    main_thread=threading.get_ident();calls=[];fetches=[];threads=[]
    daily=st.DAILY if case=='normal' else [] if case=='data_limited' else st._series(40,day_stride=1,start='2023-01-02')
    def fetcher(ticker,*,end_date=None):
        fetches.append((ticker,end_date))
        return {'D':daily,'W':st.WEEKLY,'M':st.MONTHLY}
    llm=st.ScriptedLlm(graph_fixtures._HAPPY if case=='normal' else [st.NORM_OK,st.FOCUS_OK])
    req=request();before=copy.deepcopy(req)
    def runner(payload,**kwargs):
        threads.append(threading.current_thread())
        assert threading.get_ident()!=main_thread
        calls.append(payload.model_dump(mode='json'))
        return run_technical_agent(payload,**kwargs)
    bridge=TechnicalEngineBridge(sync_runner=runner,llm_client=llm,fetcher=fetcher,
                                 cache=None,trace_sink=None,enabled=True)
    try:
        result=await runtime.BoundaryRuntime(bridge).run(req)
        contract.validate_response(result,req)
        assert req==before and len(calls)==1 and len(fetches)==1
        actual=result['data']['result']
        assert actual['data_status']==expected
        assert (actual['signal'] is None)==(case!='normal')
        assert actual['ticker']==st.TICKER and actual['as_of']==req['data']['requested_as_of']
        assert actual['request_id']==req['request_id'] and actual['trace_id']==req['trace_id']
        assert calls[0]['query']==req['data']['original_query'] and calls[0]['stock_name']=='LG에너지솔루션'
        assert len(llm.prompts)==(4 if case=='normal' else 2)
        coverage=result['data']['coverage']
        assert coverage['requested_periods']==contract.PERIODS and coverage['cutoff_validation']=='unverified'
        assert result['data']['request_snapshot']==req['data']
        assert coverage['available_periods']==([] if case=='data_limited' else contract.PERIODS)
        assert len(actual['charts'])==(0 if case=='data_limited' else 3)
        assert not ATTEMPTS
    finally:
        await asyncio.sleep(0)
        assert runtime._ACTIVE_TASK is None
        for worker in threads:
            worker.join(timeout=1)
            assert not worker.is_alive()
        assert not any(t.name=='verith-technical-bridge' and t.is_alive() for t in threading.enumerate())

async def test_narrow_range_support_and_resistance_remain_neutral_in_compiled_result():
    from src.agents.technical.domain.models.ohlcv import OHLCV
    from src.agents.technical.domain.synthesis.signal_score import compute_signal_score
    daily=[OHLCV(date=bar.date,open=100,high=101,low=99,close=100,
                 volume=bar.volume,trading_value=bar.trading_value) for bar in st.DAILY]
    expected=compute_signal_score(daily)
    row=next(r for r in expected.technical_signals if r.indicator.value=='support_resistance')
    assert row.signal.value=='neutral' and row.metrics==['지지 99.0','저항 101.0']
    llm=st.ScriptedLlm(list(graph_fixtures._HAPPY))
    bridge=TechnicalEngineBridge(sync_runner=run_technical_agent,llm_client=llm,
        fetcher=lambda ticker,**kwargs:dict(D=daily,W=st.WEEKLY,M=st.MONTHLY),
        cache=None,trace_sink=None,enabled=True)
    req=request()
    try:
        result=await runtime.BoundaryRuntime(bridge).run(req)
        contract.validate_response(result,req)
        actual=result['data']['result']
        stored=next(r for r in actual['technical_signals'] if r['indicator']=='support_resistance')
        assert actual['data_status']=='normal' and stored['signal']=='neutral'
        assert stored['metrics']==row.metrics and stored['weight']==row.weight and stored['value']==100
        assert actual['signal']['signal_score']==expected.signal_score
        assert actual['signal']['consensus']==expected.consensus.value
        assert len(llm.prompts)<=4 and not ATTEMPTS
    finally:
        await asyncio.sleep(0)
        assert runtime._ACTIVE_TASK is None
        assert not any(t.name=='verith-technical-bridge' and t.is_alive() for t in threading.enumerate())


def warmup_bars(n,case='flat'):
    from src.agents.technical.domain.models.ohlcv import OHLCV
    bars=[]
    for i,bar in enumerate(st.DAILY[:n]):
        close=100 if case in ('flat','overheated') else 200-i
        if case=='overheated' and i==n-1:close=120
        opened=close+.25 if case=='downtrend' else close-.25 if case=='oversold' else close
        bars.append(OHLCV(date=bar.date,open=opened,high=max(opened,close)+.25,
                          low=min(opened,close),close=close,volume=bar.volume,trading_value=bar.trading_value))
    return bars


@pytest.mark.parametrize('n,expected',[(60,'unavailable'),(64,'unavailable'),(65,'sideways')])
def test_actual_long_MA_slope_warmup_does_not_claim_sideways(n,expected):
    from src.agents.technical.domain.regime import rules
    bars=warmup_bars(n)
    mas=rules.calculate_moving_averages(bars)
    slope=rules._slope(mas[config.MA_LONG_WINDOW],config.SLOPE_LOOKBACK_DAYS)
    assert (slope is None)==(n<65)
    if n==65:assert slope==0
    assert config.MIN_DAILY_BARS==60
    assert rules.classify_daily_regime(bars).value==expected


@pytest.mark.parametrize('n',[60,64])
@pytest.mark.parametrize('case,expected',[
    ('overheated','overheated'),('oversold','oversold_rebound_watch'),('downtrend','downtrend')])
def test_actual_extreme_and_downtrend_survive_missing_long_slope(n,case,expected):
    from src.agents.technical.domain.regime import rules
    bars=warmup_bars(n,case)
    assert rules._slope(rules.calculate_moving_averages(bars)[config.MA_LONG_WINDOW],config.SLOPE_LOOKBACK_DAYS) is None
    assert rules.classify_daily_regime(bars).value==expected


@pytest.mark.parametrize('weekly',['up','down','unavailable'])
@pytest.mark.parametrize('monthly',['up','down','unavailable'])
def test_unavailable_context_is_history_shortage_not_directionless_sideways(weekly,monthly):
    from src.agents.technical.domain.regime.multiframe import _alignment_and_context
    from src.agents.technical.domain.models.enums import Regime,Trend
    flag,context=_alignment_and_context(Regime.UNAVAILABLE,Trend(weekly),Trend(monthly))
    assert flag.value=='neutral' and '데이터/지표 이력이 부족' in context and '방향성이 없는 중립 국면' not in context
    assert _alignment_and_context(Regime.SIDEWAYS,Trend(weekly),Trend(monthly))[1]=='방향성이 없는 중립 국면이라 상위 추세와의 정합/역행을 판정하지 않습니다.'


@pytest.mark.parametrize('n,expected',[(60,'regime_unavailable'),(64,'regime_unavailable'),(65,'normal')])
async def test_warmup_actual_graph_preserves_existing_unavailable_completion_contract(n,expected):
    daily=warmup_bars(n);llm=st.ScriptedLlm(list(graph_fixtures._HAPPY))
    bridge=TechnicalEngineBridge(sync_runner=run_technical_agent,llm_client=llm,
        fetcher=lambda ticker,**kwargs:dict(D=daily,W=st.WEEKLY,M=st.MONTHLY),
        cache=None,trace_sink=None,enabled=True)
    req=request()
    try:
        result=await runtime.BoundaryRuntime(bridge).run(req)
        contract.validate_response(result,req)
        actual=result['data']['result']
        assert actual['data_status']==expected and len(actual['charts'])==3
        assert actual['request_id']==req['request_id'] and actual['trace_id']==req['trace_id']
        assert actual['as_of']==req['data']['requested_as_of']
        if n<65:
            assert actual['regime']['daily_regime']==actual['regime']['final_regime']=='unavailable'
            assert actual['signal'] is None and actual['risk'] is None and actual['technical_signals']==[]
            assert '데이터/지표 이력이 부족' in actual['regime']['regime_context']
            assert len(llm.prompts)==2
        else:
            assert actual['regime']['final_regime']=='sideways'
            assert actual['signal'] is not None and actual['technical_signals'] and actual['risk'] is not None
            assert len(llm.prompts)==4
        assert not ATTEMPTS
    finally:
        await asyncio.sleep(0)
        assert runtime._ACTIVE_TASK is None
        assert not any(t.name=='verith-technical-bridge' and t.is_alive() for t in threading.enumerate())


@pytest.mark.parametrize('directions,counts',[
    (['positive'],(1,0,0)),(['negative'],(0,0,1)),
    (['positive','neutral','negative'],(1,1,1)),([],(0,0,0))])
def test_confidence_basis_preserves_evidence_counts_without_probability_claim(directions,counts):
    from src.agents.technical.domain.synthesis.confidence import compute_confidence,CONFIDENCE_MEANING
    from src.agents.technical.domain.synthesis.signal_score import IndicatorSignalResult,SignalScoreResult,aggregate_signal_score
    from src.agents.technical.domain.models.enums import Signal,IndicatorType,Regime,AlignmentFlag
    rows=[IndicatorSignalResult(indicator,Signal(direction),None,[],config.INDICATOR_WEIGHTS[indicator.value])
          for indicator,direction in zip((IndicatorType.MOVING_AVERAGE,IndicatorType.RSI,IndicatorType.PATTERN),directions)]
    score,consensus=aggregate_signal_score(rows)
    result=compute_confidence(SignalScoreResult(rows,score,consensus),volume_ratio=1,
                              final_regime=Regime.SIDEWAYS,alignment_flag=AlignmentFlag.NEUTRAL)
    pos,neu,neg=counts
    assert f'지표 {sum(counts)}개 중 긍정 {pos}·중립 {neu}·부정 {neg}' in result.confidence_basis
    assert CONFIDENCE_MEANING in result.confidence_basis and '개수 자체의 충분함을 보장하지 않습니다' in result.confidence_basis
    if len(directions)==1:
        assert result.confidence==pytest.approx(.8) and result.confidence_level.value=='high'
        assert (result.agreement,result.volume_confirm,result.trend_clarity,result.conflict_absence)==(1,1,0,1)


def test_deterministic_confidence_summary_and_both_prompt_variants_preserve_one_indicator_high():
    from src.agents.technical.application.nodes import interpret_report as interp
    from src.agents.technical.domain.synthesis.confidence import compute_confidence,CONFIDENCE_MEANING
    from src.agents.technical.domain.synthesis.signal_score import IndicatorSignalResult,SignalScoreResult
    from src.agents.technical.domain.models.enums import Signal,IndicatorType,Regime,AlignmentFlag,Trend,Consensus
    from src.agents.technical.domain.models.contracts import SignalSummary,RegimeResult
    row=IndicatorSignalResult(IndicatorType.MOVING_AVERAGE,Signal.POSITIVE,100,[],config.INDICATOR_WEIGHTS['moving_average'])
    conf=compute_confidence(SignalScoreResult([row],1,Consensus.STRONG_POSITIVE),volume_ratio=1,
                            final_regime=Regime.SIDEWAYS,alignment_flag=AlignmentFlag.NEUTRAL)
    signal=SignalSummary(consensus=Consensus.STRONG_POSITIVE,signal_score=1,
        confidence=conf.confidence,confidence_level=conf.confidence_level,confidence_basis=conf.confidence_basis)
    regime=RegimeResult(daily_regime=Regime.SIDEWAYS,final_regime=Regime.SIDEWAYS,
        weekly_trend=Trend.SIDEWAYS,monthly_trend=Trend.SIDEWAYS,alignment_flag=AlignmentFlag.NEUTRAL,regime_context='횡보')
    before=signal.model_dump(mode='json')
    fallback=interp.fallback_interpretation(regime=regime,signal=signal,risks=[],signals=[row])
    assert all(CONFIDENCE_MEANING in text for text in (fallback.text,fallback.signal_interpretation))
    assert '근거 점수 높음' in fallback.one_line_summary and len(fallback.one_line_summary)<=40
    payload=interp.build_payload(regime=regime,signal=signal,signals=[row],risks=[])
    assert payload['confidence']==pytest.approx(.8) and payload['confidence_level']=='high'
    assert payload['confidence_basis']==conf.confidence_basis
    for name in (interp.INTERPRET_PROMPT,interp.REGENERATE_PROMPT):
        rendered=interp.render_prompt(interp.load_prompt(name),payload)
        assert '현재 지표의 규칙 기반 근거 점수' in rendered and '상승 확률·예측 정확도가 아닙니다' in rendered
        assert '개별 부정 기여:' in rendered and '개별 긍정 기여:' in rendered
        assert '약세 근거:' not in rendered and '완충 신호:' not in rendered
        assert '검증(③) 대상이 아니지만' not in rendered and '{payload_json}' not in rendered
    assert signal.model_dump(mode='json')==before


async def test_confidence_meaning_actual_graph_keeps_calculated_numbers_and_regeneration_cap():
    from src.agents.technical.application.nodes.signal_aggregate import run_signal_aggregate
    from src.agents.technical.application.nodes.regime_classify import run_regime_classify
    from src.agents.technical.domain.indicators.volume import calculate_volume_ratio
    from src.agents.technical.domain.synthesis.confidence import compute_confidence,CONFIDENCE_MEANING
    aggregate=run_signal_aggregate(st.DAILY)
    regime=run_regime_classify(st.DAILY,st.WEEKLY,st.MONTHLY)
    conf=compute_confidence(aggregate,volume_ratio=calculate_volume_ratio(st.DAILY)[-1],
                            final_regime=regime.final_regime,alignment_flag=regime.alignment_flag)
    llm=st.ScriptedLlm(list(graph_fixtures._HAPPY))
    bridge=TechnicalEngineBridge(sync_runner=run_technical_agent,llm_client=llm,
        fetcher=lambda ticker,**kwargs:dict(D=st.DAILY,W=st.WEEKLY,M=st.MONTHLY),
        cache=None,trace_sink=None,enabled=True)
    req=request()
    try:
        result=await runtime.BoundaryRuntime(bridge).run(req)
        contract.validate_response(result,req);actual=result['data']['result'];signal=actual['signal']
        assert signal['confidence']==conf.confidence and signal['confidence_level']==conf.confidence_level.value
        assert signal['confidence_basis']==conf.confidence_basis
        assert signal['signal_score']==aggregate.signal_score and signal['consensus']==aggregate.consensus.value
        assert [(r['indicator'],r['signal'],r['value'],r['metrics'],r['weight']) for r in actual['technical_signals']]==[
            (r.indicator.value,r.signal.value,r.value,r.metrics,r.weight) for r in aggregate.technical_signals]
        assert actual['regime']['final_regime']==regime.final_regime.value
        assert all(CONFIDENCE_MEANING in actual['interpretation'][key] for key in ('text','signal_interpretation'))
        assert '근거 점수' in actual['interpretation']['one_line_summary'] and len(actual['interpretation']['one_line_summary'])<=40
        assert len(llm.prompts)==4 and not ATTEMPTS
        for prompt in llm.prompts[2:]:
            assert '현재 지표의 규칙 기반 근거 점수' in prompt and '상승 확률·예측 정확도가 아닙니다' in prompt
    finally:
        await asyncio.sleep(0);assert runtime._ACTIVE_TASK is None
        assert not any(t.name=='verith-technical-bridge' and t.is_alive() for t in threading.enumerate())


def qualitative_response():
    """Fake LLM reply for the qualitative-only contract; never patches product validation."""
    from src.agents.technical.application.nodes import interpret_report as interp
    good=json.loads(st._good_interp_response(st.DAILY,st.WEEKLY,st.MONTHLY))
    rows={row.indicator.value:row for row in st.run_signal_aggregate(st.DAILY).technical_signals}
    for entry in good['details']:
        row=rows[entry['indicator']]
        entry['detail']=interp.fallback_detail(row.indicator,row.signal,()).detail
    return json.dumps(good,ensure_ascii=False)


def numeric_context():
    from src.agents.technical.application.nodes import interpret_report as interp
    from src.agents.technical.application.orchestration import pipeline_steps as steps
    rr=st.run_regime_classify(st.DAILY,st.WEEKLY,st.MONTHLY)
    bundle=st.run_indicator_calculate(st.DAILY);score=st.run_signal_aggregate(st.DAILY)
    conf=st.run_confidence_calculate(score,bundle,rr);risks=st.run_risk_detect(score,bundle,rr)
    return SimpleNamespace(node=interp,rows=score.technical_signals,regime=steps._to_regime_result(rr),
        signal=steps._to_signal_summary(score,conf),risks=risks,good=json.loads(qualitative_response()))


@pytest.mark.parametrize('indicator,text,accepted',[
    ('moving_average','5MA와 20MA 및 60일선의 배열을 관찰합니다.',True),
    ('moving_average','**20일선**의 방향을 관찰합니다.',True),
    ('moving_average','5MA, 20MA 배열을 관찰합니다.',True),
    ('moving_average','5MA,20MA 배열을 관찰합니다.',True),
    ('moving_average','추세를 확인합니다. 20MA 회복 여부를 봅니다.',True),
    ('rsi','RSI(14)는 중립 신호입니다.',True),
    ('volume','가격과 동반된 거래량인지 살펴야 합니다.',True),
    ('rsi','RSI 현재값 50',False),('moving_average','현재가 50원',False),
    ('volume','거래량 50배',False),('rsi','50%',False),('volume','3주',False),
    ('moving_average','5MA 100',False),('moving_average','15MA',False),
    ('moving_average','5MA50',False),('moving_average','5MA%',False),
    ('moving_average','(5MA)%',False),('moving_average','‘5MA’원',False),
    ('moving_average','- 5MA',False),('moving_average','1/5MA',False),
    ('moving_average','5.0MA',False),('moving_average','５MA',False),
    ('moving_average','.5MA',False),
    ('moving_average','5MA²',False),('moving_average','100,000원',False),
    ('moving_average','+1.2e3',False),('moving_average','2026-11-13',False),
    ('moving_average','Ⅳ',False),('moving_average','0',False),
    ('rsi','5MA',False),('volume','RSI(14)',False),('rsi','RSI(14)원',False),
])
def test_numeric_roles_bind_identifier_unit_and_indicator_not_numeric_whitelist(indicator,text,accepted):
    from src.agents.technical.application.nodes import interpret_report as interp
    from src.agents.technical.domain.interpretation import numeric_claims as n
    assert n.unsupported(text,indicators=(indicator,),field='detail',roles=interp._numeric_roles()) is (not accepted)


def test_numeric_reference_is_exact_code_watchpoint_in_its_own_field_only():
    from src.agents.technical.application.nodes import interpret_report as interp
    from src.agents.technical.domain.interpretation import numeric_claims as n
    roles=interp._numeric_roles()
    for indicator in ('moving_average','rsi'):
        reference=interp._FALLBACK_DETAIL_HINTS[indicator][1]
        assert not n.unsupported(reference,indicators=(indicator,),field='detail_watchpoint',roles=roles)
        assert not n.unsupported(reference,indicators=(indicator,),field='what_to_watch_next',roles=roles)
        for field in ('detail','detail_reason','detail_caution','text','key_drivers'):
            assert n.unsupported(reference,indicators=(indicator,),field=field,roles=roles)
        for text in ('현재값 '+reference,reference+' 현재값입니다.',reference+' 50원',
                     'RSI 50선이 현재값입니다.','RSI 현재값50이므로 50선을 관찰합니다.'):
            assert n.unsupported(text,indicators=(indicator,),field='detail_watchpoint',roles=roles)
        assert n.unsupported(reference,indicators=('volume',),field='detail_watchpoint',roles=roles)


def test_numeric_identifier_policy_tracks_configured_window_and_keeps_role_metadata():
    from src.agents.technical.domain.interpretation import numeric_claims as n
    roles=n.build_roles(ma_windows=(7,21,63),rsi_period=9,references=())
    assert not n.unsupported('7MA와 21일선',indicators=('moving_average',),field='detail',roles=roles)
    assert n.unsupported('5MA',indicators=('moving_average',),field='detail',roles=roles)
    assert not n.unsupported('RSI(9)',indicators=('rsi',),field='detail',roles=roles)
    assert n.unsupported('RSI(14)',indicators=('rsi',),field='detail',roles=roles)
    assert all(role.role=='identifier' and role.unit and role.window in {7,21,63,9} for role in roles)


@pytest.mark.parametrize('field',['detail','detail_reason','detail_caution','detail_watchpoint'])
def test_actual_verify_adds_fixed_failure_to_old_label_validation_without_changing_facts(field):
    c=numeric_context();bad=copy.deepcopy(c.good);code=bad['details'][0]['indicator']
    bad['details'][0][field]=bad['details'][0].get(field,'')+' 관측값 50원'
    before=[(r.indicator,r.signal,r.value,list(r.metrics),r.weight) for r in c.rows]
    old=c.node.trajectory_eval.evaluate(bad,final_regime=c.regime.final_regime,consensus=c.signal.consensus,
        alignment_flag=c.regime.alignment_flag,signals=[(r.indicator,r.signal) for r in c.rows],
        confidence_level=c.signal.confidence_level,risk_flags=[r.flag for r in c.risks])
    assert old.passed  # Existing label/forbidden/shape checks alone do not establish numeric truth.
    checked=c.node.verify(bad,regime=c.regime,signal=c.signal,signals=c.rows,risks=c.risks)
    assert not checked.passed and checked.failed_indicators==frozenset({code}) and not checked.interpretation_failed
    assert any(f.target==f'technical_signals[{code}].{field}' and f.info==code and f.reason=='numeric_claim_unsupported' for f in checked.failures)
    assert all('50원' not in (f.info or '') for f in checked.failures)
    assert before==[(r.indicator,r.signal,r.value,list(r.metrics),r.weight) for r in c.rows]


def test_qualitative_reply_nullable_optional_fields_and_correct_numeric_copy_tradeoff():
    c=numeric_context()
    for entry in c.good['details']:
        entry.update(detail_reason=None,detail_caution='',detail_watchpoint=None)
    checked=c.node.verify(c.good,regime=c.regime,signal=c.signal,signals=c.rows,risks=c.risks)
    assert checked.passed
    copied=json.loads(st._good_interp_response(st.DAILY,st.WEEKLY,st.MONTHLY))
    assert not c.node.verify(copied,regime=c.regime,signal=c.signal,signals=c.rows,risks=c.risks).passed
    payload=c.node.build_payload(regime=c.regime,signal=c.signal,signals=c.rows,risks=c.risks)
    assert payload['numeric_prose_policy'] and all({'indicator','role','expression','unit','window','fields'}==set(r) for r in payload['numeric_prose_policy'])
    assert [(r['indicator'],r['value'],r['metrics']) for r in payload['technical_signals']]==[(r.indicator.value,r.value,r.metrics) for r in c.rows]


async def run_numeric_reply(reply,regenerated=None):
    llm=st.ScriptedLlm([st.NORM_OK,st.FOCUS_OK,json.dumps(reply,ensure_ascii=False),
        json.dumps(reply if regenerated is None else regenerated,ensure_ascii=False)])
    bridge=TechnicalEngineBridge(sync_runner=run_technical_agent,llm_client=llm,
        fetcher=lambda ticker,**kw:dict(D=st.DAILY,W=st.WEEKLY,M=st.MONTHLY),cache=None,trace_sink=None,enabled=True)
    req=request()
    try:
        result=await runtime.BoundaryRuntime(bridge).run(req);contract.validate_response(result,req)
        assert runtime._ACTIVE_TASK is None and not ATTEMPTS and len(llm.prompts)==4
        assert result['data']['result']['verification']['regen_count']==1
        return result['data']['result'],llm
    finally:
        await asyncio.sleep(0);assert runtime._ACTIVE_TASK is None
        assert not any(t.name=='verith-technical-bridge' and t.is_alive() for t in threading.enumerate())


@pytest.mark.parametrize('field',['detail','detail_reason','detail_caution','detail_watchpoint'])
async def test_numeric_graph_replaces_four_fields_of_only_failed_indicator(field):
    c=numeric_context();bad=copy.deepcopy(c.good);code=bad['details'][0]['indicator']
    bad['details'][0][field]=bad['details'][0].get(field,'')+' 현재가 50원입니다.'
    out,llm=await run_numeric_reply(bad)
    assert out['interpretation']['source']=='llm_regenerated'
    for actual,row,good in zip(out['technical_signals'],c.rows,c.good['details']):
        assert (actual['indicator'],actual['signal'],actual['value'],actual['metrics'],actual['weight'])==(row.indicator.value,row.signal.value,row.value,row.metrics,row.weight)
        if actual['indicator']==code:
            fallback=c.node.fallback_detail(row.indicator,row.signal,row.metrics)
            assert actual['detail_source']=='template_fallback'
            for key in ('detail','detail_reason','detail_caution','detail_watchpoint'):assert actual[key]==getattr(fallback,key)
        else:
            assert actual['detail_source']=='llm_regenerated' and actual['detail']==good['detail']
    assert out['signal']==c.signal.model_dump(mode='json') and out['verification']['label_matched'] is False
    for prompt in llm.prompts[2:]:assert 'numeric_prose_policy' in prompt and '정확히 복사한 숫자도' in prompt


@pytest.mark.parametrize('field',['interpretation_text','one_line_summary','trend_interpretation','signal_interpretation',
    'risk_interpretation','timeframe_alignment','what_to_watch_next','invalidation_or_caution','key_drivers','warning_points'])
async def test_numeric_graph_summary_and_lists_use_existing_whole_interpretation_fallback(field):
    c=numeric_context();bad=copy.deepcopy(c.good)
    if field=='interpretation_text':bad[field]+=' 현재가 50원입니다.'
    else:bad[field]=['현재가 50원입니다.'] if field in ('key_drivers','warning_points') else '현재가 50원입니다.'
    out,_=await run_numeric_reply(bad)
    assert out['interpretation']['source']=='template_fallback'
    assert all(row['detail_source']=='llm_regenerated' for row in out['technical_signals'])
    assert '현재가 50원입니다.' not in json.dumps(out['interpretation'],ensure_ascii=False)
    assert out['signal']==c.signal.model_dump(mode='json') and out['verification']['label_matched'] is False


async def test_numeric_regeneration_can_keep_valid_qualitative_reply_without_an_extra_call():
    c=numeric_context();bad=copy.deepcopy(c.good);bad['details'][0]['detail']+=' 현재가 50원입니다.'
    out,_=await run_numeric_reply(bad,c.good)
    assert out['verification']['outcome']=='passed' and out['verification']['label_matched'] is True
    assert out['interpretation']['source']=='llm_regenerated'
    assert all(row['detail_source']=='llm_regenerated' for row in out['technical_signals'])
    assert out['signal']==c.signal.model_dump(mode='json')


def test_missing_observed_value_cannot_become_zero_in_LLM_prose_or_prompt_facts():
    from dataclasses import replace
    c=numeric_context();row=replace(c.rows[0],value=None,metrics=[])
    reply=copy.deepcopy(c.good);reply['details']=reply['details'][:1]
    reply['details'][0]['detail']+=' 현재값 0입니다.'
    checked=c.node.verify(reply,regime=c.regime,signal=c.signal,signals=[row],risks=c.risks)
    assert not checked.passed and checked.failed_indicators==frozenset({row.indicator.value})
    payload=c.node.build_payload(regime=c.regime,signal=c.signal,signals=[row],risks=c.risks)
    assert row.value is None and payload['technical_signals'][0]['value'] is None and payload['technical_signals'][0]['metrics']==[]


# CF053: the actual graph/bridge/runtime plus selected CF051 definitions; SDK
# constructors and OHLCV are synthetic. This is not a SQL or provider test.
import json
import time
from datetime import datetime,UTC,timedelta
from dataclasses import fields
from types import SimpleNamespace
import httpx
from fastapi import FastAPI,Request
from starlette.responses import JSONResponse
from src.agents.technical.domain import execution_contracts as P
from src.agents.technical.application import agent as actual_agent
from src.agents.technical.application.orchestration import pipeline_steps as actual_steps
from src.agents.technical.application.execution_runtime import ExecutionOptions,TechnicalProviderRuntime
from src.agents.technical.infrastructure.execution_authority_client import ExecutionAuthorityClient


def cf051_selected():
    # Reuse the existing reviewed AST collector/fake HTTP SDK, never import SDK.
    path=ROOT/'backend/tests/unit/test_cf040_technical_runtime_setup.py'
    spec=importlib.util.spec_from_file_location('_cf053_existing_adapter_tests',path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    return module

ADAPTER_FIXTURES=cf051_selected()

def execution_fixture(case='normal',pause=None,calls=4,on_start=None,server_remaining=None,fetcher_stop=None,data_fetcher=None):
    req=request();ids=[str(uuid4()) for _ in range(6)];req['request_id'],req['trace_id']=ids[:2]
    req['data']['context'].update(dict(zip(('analysis_id','admission_request_id','attempt_id','report_id'),ids[2:])))
    now=datetime.now(UTC);req['data']['requested_as_of']=now.isoformat()
    req['data']['context']['input_fingerprint']=contract.fingerprint(req['data'])
    p=dict(operation='technical.analysis.v1',enabled=True,currency='USD',supported_tickers=[st.TICKER],
        user_daily_limit=3,service_daily_limit=10,daily_budget_nano=1000000,attempt_reserve_nano=420000,
        deadline_seconds=60,model='synthetic-model',service_tier='default',price_id='cf053.synthetic.v1',
        price_evidence_sha256='a'*64,input_nano_per_token=1,output_nano_per_token=1,
        input_token_cap=100000,output_token_cap=5000,input_byte_cap=100000,output_byte_cap=100000,max_calls=calls)
    cfg=P.Configuration.parse(dict(schema_version=P.SCHEMA,policy=p,counter={'free':True,'mapping':'technical.responses.model-input.v1','version':'synthetic.v1','provenance_sha256':'c'*64,'evidence_sha256':'d'*64},
        caps={'request':131072,'count':4096,'generation':1048576},ai_origin='https://ai.invalid',authority_origin='https://backend.invalid',cache_mode='none',trace_mode='none'))
    control={k:req['data']['context'][k] for k in ('analysis_id','admission_request_id','attempt_id','report_id')}
    control.update(boundary_request_id=req['request_id'],trace_id=req['trace_id'],spec_sha256=P.SPEC_SHA256,policy_sha256=cfg.policy_sha256,configuration_sha256=cfg.fingerprint,
        intent_sha256=P.sha(P.canonical(dict(operation='technical.analysis.v1',ticker=st.TICKER,original_query=req['data']['original_query'],requested_views=['technical'],conditions=req['data']['conditions']))),
        boundary_sha256=P.sha(P.canonical(req)),stock_sha256=P.sha(P.canonical(req['data']['stock'])),reserved_nano=p['attempt_reserve_nano'],started_at=now.isoformat(),deadline_at=(now+timedelta(seconds=60)).isoformat())
    value=P.execution(req,control,cfg);events=[];observations=[];starts=[];budgets=[];credentials=[];start_anchors=[]
    scripts=list(graph_fixtures._HAPPY if case=='normal' else [st.NORM_OK,st.FOCUS_OK])
    def inner(request,Parts):
        events.append((request.url.path,threading.get_ident()))
        if pause is not None and len(events)==1:
            pause[0].set();assert pause[1].wait(3)
        if request.url.path.endswith('input_tokens'):body={'object':'response.input_tokens','input_tokens':12}
        else:
            body={'status':'completed','model':p['model'],'service_tier':'default','output_text':scripts.pop(0),'usage':{'input_tokens':12,'output_tokens':3,'total_tokens':15}}
        raw=json.dumps(body,ensure_ascii=False).encode()
        return httpx.Response(200,headers={'Content-Type':'application/json','Content-Length':str(len(raw))},stream=Parts([raw]))
    helper=ADAPTER_FIXTURES.official_adapter(defer=True,inner=inner)
    helper.a['time']=time
    factory=helper.a['official_count_openai_client']
    def create(**kwargs):
        budgets.append(kwargs['request_budget']);return factory(**kwargs)
    llm=SimpleNamespace(TechnicalLlmPolicy=helper.a['TechnicalLlmPolicy'],TechnicalRequestLlmBudget=helper.a['TechnicalRequestLlmBudget'],official_count_openai_client=create)
    daily=st.DAILY if case=='normal' else [] if case=='data_limited' else st._series(40,day_stride=1,start='2023-01-02')
    def fetcher(ticker,*,end_date=None):return {'D':daily,'W':st.WEEKLY,'M':st.MONTHLY}
    def credential():credentials.append(True);return 'synthetic-auth-not-real'
    app=FastAPI()
    @app.post('/internal/technical/execution/start')
    async def start(request:Request):
        assert request.headers['x-technical-authority-token']=='b'*32
        assert request.headers['x-technical-execution-grant']=='f'*64
        body=await request.json();starts.append(body)
        start_anchors.append(time.monotonic())
        stamp=datetime.now(UTC) if server_remaining is None else P.stamp(value['control']['deadline_at'])-timedelta(seconds=server_remaining)
        receipt=P.start_receipt(value['control_sha256'],body['executor_id'],stamp.isoformat())
        if on_start is not None:on_start(instance)
        return JSONResponse({'schema_version':P.SCHEMA,'newly_started':True,**receipt})
    @app.post('/internal/technical/execution/observe')
    async def observe(request:Request):
        body=await request.json();observations.append(body)
        return JSONResponse({'schema_version':P.SCHEMA,'recorded':True,'analysis_id':body['analysis_id'],'evidence_sha256':body['evidence_sha256']})
    authority=ExecutionAuthorityClient(origin=cfg.data()['authority_origin'],token='b'*32,transport=httpx.ASGITransport(app=app))
    options=ExecutionOptions(cfg,'a'*32,'b'*32,credential,data_fetcher or fetcher,None,None,fetcher_stop=fetcher_stop)
    instance=TechnicalProviderRuntime(options,agent_module=actual_agent,steps_module=actual_steps,llm_module=llm,authority=authority)
    return SimpleNamespace(instance=instance,value=value,events=events,observations=observations,starts=starts,budgets=budgets,credentials=credentials,helper=helper,cfg=cfg,start_anchors=start_anchors)

@pytest.mark.parametrize('case,expected',[('normal','normal'),('data_limited','data_limited'),('regime_unavailable','regime_unavailable')])
async def test_CF053_actual_graph_one_start_one_budget_all_nodes_and_independent_usage(case,expected):
    h=execution_fixture(case)
    assert h.instance.readiness()['ready'] is True and not h.credentials
    result=await h.instance.execute(h.value,'f'*64)
    assert result['data']['result']['data_status']==expected
    assert len(h.starts)==len(h.budgets)==len(h.credentials)==len(h.observations)==1
    records=h.budgets[0].snapshot();assert len(records)==(4 if case=='normal' else 2)
    assert [r.ordinal for r in records]==list(range(1,len(records)+1))
    assert len(h.events)==2*len(records)<=8 and all(tid!=threading.get_ident() for _,tid in h.events)
    observed=h.observations[0]['evidence'];start={k:h.observations[0][k] for k in ('control_sha256','start_sha256','executor_id')}
    assert P.evidence(observed,h.cfg,h.value['control'],start)==observed
    assert all(r['usage']==[12,3,15] for r in observed['records'])
    assert h.helper.closed.count('client')==h.helper.closed.count('transport')==1
    await asyncio.sleep(0);assert runtime._ACTIVE_TASK is None and not ATTEMPTS

@pytest.mark.parametrize('actual_task',[False,True])
async def test_CF053_cancel_closes_pending_budget_now_but_retains_physical_slot_and_bundle(actual_task):
    paused=threading.Event();release=threading.Event();stopped=threading.Event();h=execution_fixture(pause=(paused,release),fetcher_stop=stopped)
    waiter=asyncio.create_task(h.instance.execute(h.value,'f'*64))
    try:
        for _ in range(1000):
            if paused.is_set():break
            await asyncio.sleep(.001)
        assert paused.is_set() and runtime._ACTIVE_TASK is not None
        task=runtime._ACTIVE_TASK
        (task if actual_task else waiter).cancel()
        for _ in range(100):
            if h.budgets[0].closed_reason:break
            await asyncio.sleep(.001)
        assert h.budgets[0].closed_reason is not None and stopped.is_set()
        assert runtime._ACTIVE_TASK is task and 'client' not in h.helper.closed
        with pytest.raises(runtime.BoundaryBusy):await runtime.controlled_slot(lambda:None,remaining=1,close_pending=lambda:None)
    finally:
        release.set()
        try:await waiter
        except (asyncio.CancelledError,P.ExecutionInvalid):pass
        for _ in range(1000):
            if runtime._ACTIVE_TASK is None:break
            await asyncio.sleep(.001)
        assert runtime._ACTIVE_TASK is None
        assert len(h.events)==1 and h.helper.closed.count('client')==1
        assert len(h.observations)==(0 if actual_task else 1)

async def test_CF053_existing_planning_rejection_precedes_start_key_and_budget():
    h=execution_fixture();b=h.value['boundary_request'];b['data']['original_query']='CF050 synthetic private chart'
    b['data']['context']['input_fingerprint']=contract.fingerprint(b['data'])
    c=h.value['control'];c['boundary_sha256']=P.sha(P.canonical(b))
    c['intent_sha256']=P.sha(P.canonical(dict(operation='technical.analysis.v1',ticker=st.TICKER,original_query=b['data']['original_query'],requested_views=['technical'],conditions=b['data']['conditions'])))
    value=P.execution(b,c,h.cfg);h.value.clear();h.value.update(value)
    with pytest.raises(ValueError):await h.instance.execute(h.value,'f'*64)
    assert not h.starts and not h.credentials and not h.budgets and not h.events
    assert runtime._ACTIVE_TASK is None

@pytest.mark.parametrize('field',['origin','token','transport'])
async def test_CF053_ready_authority_configuration_drift_has_start_and_key0(field):
    h=execution_fixture();assert h.instance.readiness()['ready']
    setattr(h.instance.authority,field,'https://other.invalid' if field=='origin' else b'c'*32 if field=='token' else None)
    with pytest.raises(P.ExecutionInvalid):await h.instance.execute(h.value,'f'*64)
    assert not h.starts and not h.credentials and not h.budgets and not h.events

async def test_CF053_real_graph_call_cap_closes_later_nodes_without_recreating_budget():
    h=execution_fixture(calls=2)
    result=await h.instance.execute(h.value,'f'*64)
    assert result['data']['result']['ticker']==st.TICKER
    assert len(h.budgets)==len(h.starts)==len(h.credentials)==1
    assert len(h.budgets[0].snapshot())==2 and len(h.events)==4
    assert h.budgets[0].closed_reason=='BUDGET_EXCEEDED'
    assert h.observations[0]['evidence']['records']==[
        {f.name:(str(getattr(item,f.name)) if isinstance(getattr(item,f.name),UUID) else list(getattr(item,f.name)) if type(getattr(item,f.name)) is tuple else getattr(item,f.name)) for f in fields(item)} for item in h.budgets[0].snapshot()]

async def test_CF053_waiter_timeout_keeps_slot_bundle_until_physical_count_finishes():
    pause=(threading.Event(),threading.Event());h=execution_fixture(pause=pause)
    value=h.value;c=value['control'];c['deadline_at']=(P.stamp(c['started_at'])+timedelta(seconds=1)).isoformat()
    fixed=P.execution(value['boundary_request'],c,h.cfg);value.clear();value.update(fixed)
    waiter=asyncio.create_task(h.instance.execute(value,'f'*64))
    try:
        for _ in range(500):
            if pause[0].is_set():break
            await asyncio.sleep(.001)
        assert pause[0].is_set()
        with pytest.raises(runtime.BoundaryTimeout):await waiter
        assert runtime._ACTIVE_TASK is not None and 'client' not in h.helper.closed
        assert h.budgets[0].closed_reason=='DEADLINE_EXCEEDED'
    finally:
        pause[1].set()
        for _ in range(1500):
            if runtime._ACTIVE_TASK is None:break
            await asyncio.sleep(.001)
        assert runtime._ACTIVE_TASK is None and len(h.events)==1
        assert h.helper.closed.count('client')==1
        assert len(h.observations)==1 and h.observations[0]['evidence']['outcome']=='deadline'

@pytest.mark.parametrize('flag',['LANGCHAIN_TRACING','LANGCHAIN_TRACING_V2','LANGSMITH_TRACING','LANGSMITH_TRACING_V2'])
async def test_CF053_process_auto_trace_enabled_is_unready_before_start(flag,monkeypatch):
    h=execution_fixture()
    monkeypatch.setenv(flag,'true')  # self-owned unit worker only; never open a real runtime
    with pytest.raises(P.ExecutionInvalid):h.instance.readiness()
    with pytest.raises(P.ExecutionInvalid):await h.instance.execute(h.value,'f'*64)
    assert not h.starts and not h.credentials and not h.events

@pytest.mark.parametrize('capability',['fetcher','credential_supplier'])
async def test_CF053_async_callable_object_is_unready_before_start(capability):
    h=execution_fixture()
    class AsyncCapability:
        async def __call__(self,*args,**kwargs):raise AssertionError('must not enter')
    object.__setattr__(h.instance.options,capability,AsyncCapability())
    with pytest.raises(P.ExecutionInvalid):h.instance.readiness()
    assert not h.starts and not h.credentials and not h.events

async def test_CF053_config_drift_after_start_cannot_reprice_or_create_budget_but_records_failure():
    def drift(instance):
        changed=instance.configuration.data();changed['caps']['request']=262144
        instance.configuration=P.Configuration.parse(changed)
    h=execution_fixture(on_start=drift)
    with pytest.raises(P.ExecutionInvalid):await h.instance.execute(h.value,'f'*64)
    assert len(h.starts)==1 and not h.credentials and not h.budgets and not h.events
    assert len(h.observations)==1 and h.observations[0]['evidence']['outcome']=='failed'
    assert h.observations[0]['evidence']['records']==[]
    await asyncio.sleep(0);assert runtime._ACTIVE_TASK is None

async def test_CF053_start_DB_remaining_only_narrows_original_monotonic_deadline():
    # Explicit DB-clock step simulation, no real sleep or environment clock edit.
    h=execution_fixture(server_remaining=20)
    result=await h.instance.execute(h.value,'f'*64)
    assert result['data']['execution_mode']=='controlled' and len(h.budgets)==1
    assert h.budgets[0]._monotonic_deadline<=h.start_anchors[0]+20
    assert h.value['control']['deadline_at']==(P.stamp(h.value['control']['started_at'])+timedelta(seconds=60)).isoformat()
    assert len(h.events)==8 and len(h.observations)==1


@pytest.mark.parametrize('field',['one_line_summary','trend_interpretation','signal_interpretation',
    'risk_interpretation','timeframe_alignment','what_to_watch_next','invalidation_or_caution',
    'key_drivers','warning_points'])
async def test_explanation_failed_summary_section_never_survives_final_fallback(field):
    bad=json.loads(qualitative_response())
    bad[field]=['금지된 매수 문장'] if field in {'key_drivers','warning_points'} else '금지된 매수 문장'
    llm=st.ScriptedLlm([st.NORM_OK,st.FOCUS_OK]+[json.dumps(bad,ensure_ascii=False)]*2)
    req=request()
    bridge=TechnicalEngineBridge(sync_runner=run_technical_agent,llm_client=llm,fetcher=lambda ticker,**kw:{'D':st.DAILY,'W':st.WEEKLY,'M':st.MONTHLY},cache=None,trace_sink=None,enabled=True)
    result=await runtime.BoundaryRuntime(bridge).run(req)
    contract.validate_response(result,req);out=result['data']['result']
    assert '금지된 매수 문장' not in json.dumps(out,ensure_ascii=False)
    assert out['interpretation']['source']=='template_fallback'
    assert out['verification']['outcome']=='template_fallback' and out['verification']['label_matched'] is False
    assert out['verification']['regen_count']==1 and len(llm.prompts)==4
    assert all(item['detail_source']=='llm_regenerated' for item in out['technical_signals'])
    confirmed=st.run_signal_aggregate(st.DAILY).technical_signals
    assert [(x['indicator'],x['signal'],x['value'],x['metrics'],x['weight']) for x in out['technical_signals']]==[(x.indicator.value,x.signal.value,x.value,x.metrics,x.weight) for x in confirmed]
    assert runtime._ACTIVE_TASK is None and not ATTEMPTS


@pytest.mark.parametrize('field',['detail_reason','detail_caution','detail_watchpoint'])
@pytest.mark.parametrize('bad_kind',['forbidden','conflict'])
async def test_explanation_bad_additive_detail_is_replaced_and_verification_reflects_failure(field,bad_kind):
    bad=json.loads(qualitative_response())
    first=bad['details'][0];code=first['indicator']
    first[field]='금지된 매수 문장' if bad_kind=='forbidden' else ('부정 약세' if '긍정' in first['detail'] else '강한 긍정')
    raw=json.dumps(bad,ensure_ascii=False);llm=st.ScriptedLlm([st.NORM_OK,st.FOCUS_OK,raw,raw]);req=request()
    bridge=TechnicalEngineBridge(sync_runner=run_technical_agent,llm_client=llm,fetcher=lambda ticker,**kw:{'D':st.DAILY,'W':st.WEEKLY,'M':st.MONTHLY},cache=None,trace_sink=None,enabled=True)
    result=await runtime.BoundaryRuntime(bridge).run(req);contract.validate_response(result,req);out=result['data']['result']
    selected=next(item for item in out['technical_signals'] if item['indicator']==code)
    assert selected['detail_source']=='template_fallback' and selected[field]!=first[field]
    assert out['interpretation']['source']=='llm_regenerated'
    assert out['verification']['label_matched'] is False and out['verification']['outcome']=='template_fallback'
    confirmed=st.run_signal_aggregate(st.DAILY).technical_signals
    assert [(x['indicator'],x['signal'],x['value'],x['metrics'],x['weight']) for x in out['technical_signals']]==[(x.indicator.value,x.signal.value,x.value,x.metrics,x.weight) for x in confirmed]
    assert len(llm.prompts)==4 and runtime._ACTIVE_TASK is None


@pytest.mark.parametrize('field',['indicator','detail','detail_reason','detail_caution','detail_watchpoint'])
@pytest.mark.parametrize('value',[123,True,{'unsafe':'not a string'},['not a string']])
def test_explanation_detail_fields_are_never_coerced_from_other_types(field,value):
    bad=json.loads(qualitative_response());bad['details'][0][field]=value
    with pytest.raises(st.interp.LlmOutputParseError):st.interp.parse_llm_output(json.dumps(bad))


@pytest.mark.parametrize('direction',['positive','negative'])
def test_explanation_fallback_does_not_describe_positive_signals_as_a_downturn_in_every_regime(direction):
    from src.agents.technical.domain.models.contracts import RegimeResult,SignalSummary
    from src.agents.technical.domain.models.enums import Regime,Trend,AlignmentFlag,Consensus,ConfidenceLevel,Signal,IndicatorType
    from src.agents.technical.domain.synthesis.signal_score import IndicatorSignalResult
    signal=SignalSummary(consensus=Consensus.WEAK_POSITIVE,signal_score=.3,confidence=.42,confidence_level=ConfidenceLevel.MEDIUM,confidence_basis='synthetic')
    chosen=Signal(direction)
    signals=[IndicatorSignalResult(IndicatorType.MOVING_AVERAGE,chosen,100.0,['5MA 100.0'],.3)]
    for final in Regime:
        if final==Regime.UNAVAILABLE:continue
        regime=RegimeResult(final_regime=final,daily_regime=final,weekly_trend=Trend.UP,monthly_trend=Trend.UP,alignment_flag=AlignmentFlag.NEUTRAL,regime_context='synthetic')
        text=st.interp.fallback_interpretation(regime=regime,signal=signal,signals=signals,risks=[]).text
        assert '하락 압력을 다소 완화' not in text and '방향 전환 확정으로 보기엔 이른' not in text
        assert '추세 복원 신호가 아직 충분하지' not in text
        assert st.interp.SIGNAL_LABELS[chosen]+' 신호' in text and st.interp.REGIME_LABELS[final] in text


@pytest.mark.parametrize('regenerate',[False,True])
@pytest.mark.parametrize('optional',['text',None,''])
async def test_explanation_safe_additive_fields_and_successful_regeneration_keep_LLM(regenerate,optional):
    good=json.loads(qualitative_response())
    good['one_line_summary']='확정된 기술적 상태를 참고합니다.'
    for entry in good['details']:
        entry.update(detail_reason='확정된 지표 수치를 기준으로 설명합니다.',
            detail_caution='한 지표로 방향을 단정하지 않습니다.',detail_watchpoint='거래량과 지표 변화를 관찰합니다.')
        if optional!='text':entry.update(detail_reason=optional,detail_caution=optional,detail_watchpoint=optional)
    raw=json.dumps(good,ensure_ascii=False);responses=[st.NORM_OK,st.FOCUS_OK]
    if regenerate:
        bad=dict(good,one_line_summary='금지된 매수 문장');responses.append(json.dumps(bad,ensure_ascii=False))
    responses.append(raw);llm=st.ScriptedLlm(responses);req=request()
    bridge=TechnicalEngineBridge(sync_runner=run_technical_agent,llm_client=llm,
        fetcher=lambda ticker,**kw:{'D':st.DAILY,'W':st.WEEKLY,'M':st.MONTHLY},cache=None,trace_sink=None,enabled=True)
    result=await runtime.BoundaryRuntime(bridge).run(req);contract.validate_response(result,req);out=result['data']['result']
    assert out['interpretation']['source']==('llm_regenerated' if regenerate else 'llm')
    assert out['interpretation']['one_line_summary']==good['one_line_summary']
    assert all(item['detail_source']==out['interpretation']['source'] for item in out['technical_signals'])
    assert out['verification']['outcome']=='passed' and out['verification']['label_matched'] is True
    assert all(type(item[field]) is str and item[field] for item in out['technical_signals'] for field in ('detail_reason','detail_caution','detail_watchpoint'))
    assert out['verification']['regen_count']==int(regenerate) and len(llm.prompts)==3+int(regenerate)
    assert runtime._ACTIVE_TASK is None


@pytest.mark.parametrize('case',['call_error','parse_error','both_failed'])
async def test_explanation_existing_full_fallback_and_combined_failure_keep_original_limits(case):
    good=json.loads(qualitative_response());sentinel='cf055-synthetic-exception-never-serialized'
    if case=='call_error':responses=[RuntimeError(sentinel)]
    elif case=='parse_error':responses=['{','{']
    else:
        good['one_line_summary']='금지된 매수 문장';good['details'][0]['detail_reason']='금지된 매수 문장'
        raw=json.dumps(good,ensure_ascii=False);responses=[raw,raw]
    llm=st.ScriptedLlm([st.NORM_OK,st.FOCUS_OK]+responses);req=request()
    bridge=TechnicalEngineBridge(sync_runner=run_technical_agent,llm_client=llm,
        fetcher=lambda ticker,**kw:{'D':st.DAILY,'W':st.WEEKLY,'M':st.MONTHLY},cache=None,trace_sink=None,enabled=True)
    result=await runtime.BoundaryRuntime(bridge).run(req);contract.validate_response(result,req);out=result['data']['result']
    assert sentinel not in json.dumps(out,ensure_ascii=False) and '금지된 매수 문장' not in json.dumps(out,ensure_ascii=False)
    assert out['interpretation']['source']=='template_fallback'
    assert out['verification']['label_matched'] is False and out['verification']['outcome']=='template_fallback'
    assert out['verification']['regen_count']==(0 if case=='call_error' else 1)
    assert len(llm.prompts)==(3 if case=='call_error' else 4)
    if case=='both_failed':
        bad_code=good['details'][0]['indicator']
        assert all(x['detail_source']==('template_fallback' if x['indicator']==bad_code else 'llm_regenerated') for x in out['technical_signals'])
    else:assert all(x['detail_source']=='template_fallback' for x in out['technical_signals'])
    confirmed=st.run_signal_aggregate(st.DAILY).technical_signals
    assert [(x['indicator'],x['signal'],x['value'],x['metrics'],x['weight']) for x in out['technical_signals']]==[(x.indicator.value,x.signal.value,x.value,x.metrics,x.weight) for x in confirmed]
    assert runtime._ACTIVE_TASK is None and not ATTEMPTS


async def test_runtime_first_cancel_closes_same_KIS_event_before_physical_fetch_finishes():
    import httpx
    from types import SimpleNamespace
    env,_,_=ADAPTER_FIXTURES.explicit_kis_slices()
    settings=ADAPTER_FIXTURES.COLLECTION_CONFIG.KISSettings('synthetic-key','synthetic-secret','https://kis.example.invalid:9443')
    stopped=threading.Event();paused=threading.Event();release=threading.Event();blocked=threading.Event();sent=[]
    hook,observed=env['kis_request_gate'](settings=settings,ticker=st.TICKER,deadline=SimpleNamespace(remaining_seconds=lambda:30),
        stopped=stopped,token_limit=3,market_limit=30)
    def fetcher(ticker,*,end_date=None):
        with httpx.Client(transport=httpx.MockTransport(lambda r:(sent.append(r),httpx.Response(200,json={}))[1]),
                          trust_env=False,follow_redirects=False,event_hooks={'request':[hook]}) as client:
            client.post(settings.base_url+env['TOKEN_PATH'])
            paused.set();assert release.wait(3)
            try:client.post(settings.base_url+env['TOKEN_PATH'])
            except ValueError:blocked.set();raise
        raise AssertionError('Cancelled KIS request must not continue')
    h=execution_fixture(fetcher_stop=stopped,data_fetcher=fetcher)
    waiter=asyncio.create_task(h.instance.execute(h.value,'f'*64))
    try:
        for _ in range(1000):
            if paused.is_set():break
            await asyncio.sleep(.001)
        assert paused.is_set() and runtime._ACTIVE_TASK is not None
        # Normalize/focus precede market collection in the real graph. Preserve
        # those already-observed calls; only forbid additional calls on cancel.
        prior_calls=len(h.events)
        assert prior_calls==4
        task=runtime._ACTIVE_TASK;task.cancel()
        for _ in range(100):
            if stopped.is_set():break
            await asyncio.sleep(.001)
        assert stopped.is_set() and runtime._ACTIVE_TASK is task and not release.is_set()
        assert h.budgets[0].closed_reason is not None
    finally:
        release.set()
        try:await waiter
        except (asyncio.CancelledError,P.ExecutionInvalid):pass
        for _ in range(1000):
            if runtime._ACTIVE_TASK is None:break
            await asyncio.sleep(.001)
    assert runtime._ACTIVE_TASK is None and blocked.is_set()
    assert observed()=={'token':1,'market':0} and len(sent)==1 and len(h.events)==prior_calls


@pytest.mark.parametrize('case',['provider_cookie','forbidden_header'])
async def test_pinned_real_SDK_cookie_wire_and_wrapped_denial_under_existing_OS_guard(case):
    """Real installed/pinned SDK serialization; only inner HTTP is synthetic.

    No socket, env credential, DB, or SDK retry capability is granted. The
    source/dependency snapshots and existing OS canaries still apply.
    """
    def exercise():
        import importlib
        from scripts.check_safe import GRAPH_DISTRIBUTIONS
        assert not any(n=='openai' or n.startswith('openai.') for n in sys.modules)
        before=set(sys.modules);attempts=list(ATTEMPTS)
        spec=importlib.machinery.PathFinder.find_spec('openai')
        assert spec is not None and spec.origin is not None
        sdk_root=Path(spec.origin).resolve().parent
        assert sdk_root.name=='openai' and not sdk_root.is_relative_to(ROOT)
        _SDK_TEST_SCOPE.root=sdk_root
        adapter=None;mock=None
        try:
            sdk=importlib.import_module('openai')
            assert sdk.__version__==GRAPH_DISTRIBUTIONS['openai']=='2.44.0'
            assert Path(sdk.__file__).resolve().parent==sdk_root
            # SDK platform.platform() can invoke native processor discovery.
            # Supply only that SDK module's header metadata as a fixed input;
            # never patch stdlib platform or permit its probe/process/file I/O.
            base=importlib.import_module('openai._base_client')
            base.platform=SimpleNamespace(system=lambda:'Darwin',platform=lambda:'Darwin-keyless-fixed',
                machine=lambda:'arm64',python_implementation=lambda:'CPython',
                python_version=lambda:'3.12.13')
            helper=ADAPTER_FIXTURES.strict_adapter(counter=False,calls=1)
            helper.a.update(openai=sdk,httpx=httpx,time=time,os=os,logging=__import__('logging'))
            provenance=hashlib.sha256((sdk_root/'resources/responses/input_tokens.py').read_bytes()).hexdigest()
            adapter=helper.a['official_count_openai_client'](request_budget=helper.budget,
                api_key='keyless-fixed-SDK-regression',request_wire_cap=4096,count_wire_cap=1024,
                generation_wire_cap=4096,count_version='openai.2.44.0.keyless',
                count_provenance_sha256=provenance,timeout=30)
            bundle=helper.budget._official_bundle;sent=[]
            def respond(request):
                assert 'Cookie' not in request.headers
                sent.append(request.url.path)
                if request.url.path.endswith('/input_tokens'):
                    if case=='forbidden_header':bundle.sdk._custom_headers['Cookie']=ADAPTER_FIXTURES.PRIVATE
                    return httpx.Response(200,headers={'Set-Cookie':'verith_synthetic=not-secret; Secure; Path=/'},
                        json={'object':'response.input_tokens','input_tokens':12})
                return httpx.Response(200,json={'id':'resp_keyless','object':'response','created_at':1,
                    'model':'synthetic-model','service_tier':'default','status':'completed',
                    'output':[{'type':'message','id':'msg_keyless','role':'assistant','status':'completed',
                        'content':[{'type':'output_text','text':'keyless result','annotations':[]}]}],
                    'usage':{'input_tokens':12,'output_tokens':3,'total_tokens':15}})
            mock=httpx.MockTransport(respond)
            # Keep the captured inner object identity and every original outer
            # check; replace only its final I/O method with MockTransport.
            bundle.inner.handle_request=mock.handle_request
            if case=='provider_cookie':
                assert adapter.complete('synthetic fixed SDK prompt')=='keyless result'
                row,=helper.budget.snapshot()
                assert row.count_validated and row.entered and row.text_accepted and row.usage==(12,3,15)
                assert sent==['/v1/responses/input_tokens','/v1/responses']
            else:
                with pytest.raises(helper.a['LlmCallError']) as error:adapter.complete('synthetic fixed SDK prompt')
                assert str(error.value)=='TECHNICAL_LLM_HTTP_INVALID'
                assert ADAPTER_FIXTURES.PRIVATE not in str(error.value) and error.value.__suppress_context__
                row,=helper.budget.snapshot()
                assert row.count_validated and not row.entered and row.reason=='HTTP_INVALID' and row.held_nano==2000
                with pytest.raises(helper.a['LlmCallError']):adapter.complete('again')
                assert sent==['/v1/responses/input_tokens']
            assert not list(bundle.client.cookies.jar) and bundle.sdk.max_retries==0
            assert ATTEMPTS==attempts
        finally:
            if adapter is not None:adapter.close()
            if mock is not None:mock.close()
            _SDK_TEST_SCOPE.root=None
            for name in set(sys.modules)-before:
                if name=='openai' or name.startswith('openai.'):sys.modules.pop(name,None)
        assert not any(n=='openai' or n.startswith('openai.') for n in sys.modules)
    await asyncio.to_thread(exercise)
    assert not ATTEMPTS and runtime._ACTIVE_TASK is None
