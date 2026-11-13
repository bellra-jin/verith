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

def execution_fixture(case='normal',pause=None,calls=4,on_start=None,server_remaining=None,fetcher_stop=None,data_fetcher=None,trace_sink=None,interpret_scripts=None):
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
        caps={'request':131072,'count':4096,'generation':1048576},ai_origin='https://ai.invalid',authority_origin='https://backend.invalid',cache_mode='none',trace_mode='none' if trace_sink is None else 'injected'))
    control={k:req['data']['context'][k] for k in ('analysis_id','admission_request_id','attempt_id','report_id')}
    control.update(boundary_request_id=req['request_id'],trace_id=req['trace_id'],spec_sha256=P.SPEC_SHA256,policy_sha256=cfg.policy_sha256,configuration_sha256=cfg.fingerprint,
        intent_sha256=P.sha(P.canonical(dict(operation='technical.analysis.v1',ticker=st.TICKER,original_query=req['data']['original_query'],requested_views=['technical'],conditions=req['data']['conditions']))),
        boundary_sha256=P.sha(P.canonical(req)),stock_sha256=P.sha(P.canonical(req['data']['stock'])),reserved_nano=p['attempt_reserve_nano'],started_at=now.isoformat(),deadline_at=(now+timedelta(seconds=60)).isoformat())
    value=P.execution(req,control,cfg);events=[];observations=[];starts=[];budgets=[];credentials=[];start_anchors=[]
    scripts=list(graph_fixtures._HAPPY if case=='normal' else [st.NORM_OK,st.FOCUS_OK]);generation_inputs=[]
    if interpret_scripts is not None:scripts[2:]=interpret_scripts
    def inner(request,Parts):
        events.append((request.url.path,threading.get_ident()))
        if pause is not None and len(events)==1:
            pause[0].set();assert pause[1].wait(3)
        if request.url.path.endswith('input_tokens'):body={'object':'response.input_tokens','input_tokens':12}
        else:
            generation_inputs.append(json.loads(request.content)['input'])
            script=scripts.pop(0)
            output=script(generation_inputs[-1]) if callable(script) else script
            body={'status':'completed','model':p['model'],'service_tier':'default','output_text':output,'usage':{'input_tokens':12,'output_tokens':3,'total_tokens':15}}
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
    options=ExecutionOptions(cfg,'a'*32,'b'*32,credential,data_fetcher or fetcher,None,trace_sink,fetcher_stop=fetcher_stop)
    instance=TechnicalProviderRuntime(options,agent_module=actual_agent,steps_module=actual_steps,llm_module=llm,authority=authority)
    return SimpleNamespace(instance=instance,value=value,events=events,observations=observations,starts=starts,budgets=budgets,credentials=credentials,helper=helper,cfg=cfg,start_anchors=start_anchors,generation_inputs=generation_inputs)

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


@pytest.mark.parametrize('text',['과매수 상태입니다.','과매도 상태를 관찰합니다.','과매도 구간을 관찰합니다.','RSI는 **과매수**·**과매도** 기준을 확인합니다.','과매수는 기술적 상태입니다.'])
def test_technical_state_nouns_are_not_trade_instructions(text):
    from src.agents.technical.domain.interpretation import trajectory_eval as ev
    assert ev.contains_forbidden_terms(text)==[]


@pytest.mark.parametrize('text',['매수 신호는 아닙니다.','과매수 상태이므로 매수하세요.','과매도 구간에서 매도합니다.','과매수 추천','과매도 목표가','과매수하세요','초과매수','과매도하지 마세요'])
def test_state_nouns_never_hide_trade_instructions_or_other_forbidden_terms(text):
    from src.agents.technical.domain.interpretation import trajectory_eval as ev
    assert ev.contains_forbidden_terms(text)


def test_state_noun_fix_does_not_relax_signal_or_numeric_validation():
    from src.agents.technical.domain.interpretation import trajectory_eval as ev
    from src.agents.technical.domain.models.enums import IndicatorType,Signal
    good=[{'indicator':'rsi','detail':'과매수 상태이며 부정 신호입니다.'}]
    assert not ev.evaluate_details(good,signals=[(IndicatorType.RSI,Signal.NEGATIVE)])
    assert ev.evaluate_details(good,signals=[(IndicatorType.RSI,Signal.POSITIVE)])
    good=json.loads(qualitative_response());good['details'][0]['detail_reason']='과매수 상태의 현재값은 99입니다.'
    context=numeric_context()
    result=context.node.verify(good,regime=context.regime,signal=context.signal,signals=context.rows,risks=context.risks)
    assert any(f.reason=='numeric_claim_unsupported' for f in result.failures)


def test_diagnostic_codes_are_closed_deduplicated_and_bounded(caplog):
    from src.agents.technical.domain.interpretation import trajectory_eval as ev
    from src.agents.technical.application.orchestration import pipeline_steps as steps
    from src.agents.technical.infrastructure.observability.trace_logger import InMemoryTraceSink,TraceLogger
    sentinel='private-model-response-should-never-appear'
    failures=[ev.TargetFailure('interpretation.text','numeric_claim_unsupported'),
              ev.TargetFailure('technical_signals[rsi].detail','conflict:긍정','rsi'),
              ev.TargetFailure('technical_signals[pattern].detail',sentinel,sentinel),
              ev.TargetFailure(sentinel,sentinel,sentinel)]*100
    result=ev.EvalResult(False,tuple(failures));codes=ev.diagnostic_codes(result)
    assert len(codes)<=12 and len({(x['target'],x['reason']) for x in codes})==len(codes)
    assert {'target':'interpretation.text','reason':'numeric_claim_unsupported'} in codes
    assert {'target':'technical_signals[rsi].detail','reason':'label_conflict'} in codes
    sink=InMemoryTraceSink();steps._emit_validation(TraceLogger(sink,trace_id='fixed-diagnostic'),steps._Attempt(False,{},result),1)
    assert sentinel not in json.dumps(sink.events) and sentinel not in str([x.__dict__ for x in caplog.records])
    assert sink.events[0]['output_summary']['failures']==codes


async def test_provider_runtime_preserves_bounded_validation_codes_via_existing_injected_trace():
    # Fake SDK + the actual graph/runtime, no new wire/schema or provider call.
    from src.agents.technical.infrastructure.observability.trace_logger import InMemoryTraceSink
    bad=json.loads(qualitative_response());bad['one_line_summary']='현재 가격은 999원입니다.'
    next(x for x in bad['details'] if x['indicator']=='rsi')['detail_caution']='현재 RSI는 88입니다.'
    raw=json.dumps(bad,ensure_ascii=False);sink=InMemoryTraceSink()
    h=execution_fixture(trace_sink=sink,interpret_scripts=[raw,raw])
    result=await h.instance.execute(h.value,'f'*64)
    assert result['data']['result']['verification']['label_matched'] is False
    events=[x for x in sink.events if x['event_type']=='validation' and x['node']=='interpret_report']
    assert len(events)==2
    for event in events:
        codes=event['output_summary']['failures']
        assert {'target':'interpretation.one_line_summary','reason':'numeric_claim_unsupported'} in codes
        assert {'target':'technical_signals[rsi].detail_caution','reason':'numeric_claim_unsupported'} in codes
    summaries=[event['output_summary'] for event in events]
    assert '999' not in json.dumps(summaries) and '88' not in json.dumps(summaries)
    payloads=[json.loads(prompt.rsplit('```json\n',1)[1].split('\n```',1)[0]) for prompt in h.generation_inputs[-2:]]
    assert 'validation_feedback' not in payloads[0]
    assert payloads[1]['validation_feedback']==events[0]['output_summary']['failures']
    assert 'numeric_claim_unsupported' in json.dumps(payloads[1]['validation_feedback'])
    assert '현재 가격은 999원입니다.' not in json.dumps(payloads[1],ensure_ascii=False)
    assert len(h.budgets)==1 and len(h.events)==8 and len(h.starts)==len(h.observations)==1
    assert runtime._ACTIVE_TASK is None


def kis_bar(date='20240105',close='100'):
    return dict(stck_bsop_date=date,stck_oprc='100',stck_hgpr='105',stck_lwpr='95',stck_clpr=close,acml_vol='1000',acml_tr_pbmn='100000')


@pytest.mark.parametrize('conflict',[False,True])
def test_KIS_duplicate_candles_identical_replay_or_fixed_conflict(monkeypatch,conflict):
    from src.agents.technical.infrastructure import kis_client as kis
    from datetime import date
    seen=[]
    def chart(*args,**kwargs):seen.append(True);return {'output2':[kis_bar(),kis_bar(close='101' if conflict else '100')]}
    monkeypatch.setattr(kis,'_call_chart',chart)
    settings=config.KISSettings('fake-key','fake-secret','https://kis.invalid')
    def run():return kis._fetch_ohlcv_range('000720','D',date(2024,1,1),date(2024,1,5),None,settings=settings,_token='fake-token')
    if conflict:
        with pytest.raises(kis.KisFieldError,match='^KIS_MARKET_CONFLICTING_BAR$'):run()
    else:
        rows=run();assert len(rows)==1 and rows[0].close==100
    assert seen==[True]


@pytest.mark.parametrize('status,marker,recovered',[(500,True,True),(500,False,False),(429,False,True)])
def test_KIS_retry_conditions_remain_bounded_and_nonretry_500_fails(monkeypatch,status,marker,recovered):
    from src.agents.technical.infrastructure import kis_client as kis
    calls=[];backoff=[]
    request=httpx.Request('GET','https://kis.invalid/market')
    class Client:
        def get(self,*args,**kwargs):
            calls.append(True)
            return httpx.Response(status if len(calls)==1 else 200,request=request,
                json={'rt_cd':'0','output2':[kis_bar()]} if len(calls)>1 else {'msg_cd':kis.RATE_LIMIT_MSG_CODE if marker else 'unavailable'})
    monkeypatch.setattr(kis,'_sleep_backoff',lambda attempt:backoff.append(attempt))
    settings=config.KISSettings('fake-key','fake-secret','https://kis.invalid')
    def run():return kis._call_chart(settings,'fake-token','000720','D','20240101','20240105',Client(),safe_errors=True)
    if recovered:assert run()['rt_cd']=='0' and len(calls)==2 and backoff==[0]
    else:
        with pytest.raises(kis.KisApiError,match='^KIS_MARKET_HTTP_FAILED$'):run()
        assert len(calls)==1 and not backoff


@pytest.mark.parametrize('signal,text',[
    ('positive','긍정 신호지만 약세로 단정하지 않습니다.'),
    ('negative','부정 신호이며 강세 전환을 확정할 수 없습니다.'),
])
def test_exact_complete_label_cautions_do_not_assert_opposite_signal(signal,text):
    from src.agents.technical.domain.interpretation.trajectory_eval import check_label
    from src.agents.technical.domain.interpretation.keyword_rules import SIGNAL_RULES
    from src.agents.technical.domain.models.enums import Signal
    assert check_label(text,SIGNAL_RULES[Signal(signal)])==[]
    assert check_label(text+' '+('약세입니다.' if signal=='positive' else '강세입니다.'),SIGNAL_RULES[Signal(signal)])


def test_closed_caution_does_not_mask_other_clauses_advice_numbers_or_fuzzy_negation():
    from src.agents.technical.domain.interpretation.trajectory_eval import check_label,contains_forbidden_terms
    from src.agents.technical.domain.interpretation.keyword_rules import REGIME_RULES,SIGNAL_RULES
    from src.agents.technical.domain.models.enums import Regime,Signal
    assert not check_label('횡보이며 상승 추세를 확정하지 않습니다.',REGIME_RULES[Regime.SIDEWAYS])
    for text in ('긍정이지만 약세일 수도 있습니다.','긍정이며 약세로 단정하지 않습니다. 약세입니다.',
                 '긍정이지만 약세로 단정하지 않습니다라고 말합니다.','긍정이며 약세로 단정하지 않습니다만 약세입니다.'):
        assert check_label(text,SIGNAL_RULES[Signal.POSITIVE])
    assert contains_forbidden_terms('약세로 단정하지 않습니다. 매수하지 마세요.')==['매수']


def test_code_regime_name_overbought_does_not_contradict_forbidden_vocabulary():
    from src.agents.technical.domain.interpretation import trajectory_eval as ev
    from src.agents.technical.domain.models.enums import Regime,Consensus,AlignmentFlag
    assert not ev.evaluate_text('과매수 국면의 약한 부정 신호이며 상위 방향과 정합합니다.',
        final_regime=Regime.OVERHEATED,consensus=Consensus.WEAK_NEGATIVE,alignment_flag=AlignmentFlag.ALIGNED)


def test_KIS_body_read_failure_is_distinct_from_confirmed_rate_marker_and_bounded(monkeypatch,caplog):
    from src.agents.technical.infrastructure import kis_client as kis
    calls=[];backoff=[];request=httpx.Request('GET','https://kis.invalid/market')
    class Client:
        def get(self,*args,**kwargs):
            calls.append(True)
            if len(calls)==1:raise httpx.ReadError('private-response-body-sentinel',request=request)
            return httpx.Response(200,request=request,json={'rt_cd':'0','output2':[kis_bar()]})
    monkeypatch.setattr(kis,'_sleep_backoff',lambda n:backoff.append(n))
    data=kis._call_chart(config.KISSettings('fake-key','fake-secret','https://kis.invalid'),'fake-token','000720','D','20240101','20240105',Client(),safe_errors=True)
    assert len(calls)==2 and backoff==[0] and data['rt_cd']=='0'
    assert 'private-response-body-sentinel' not in str([r.__dict__ for r in caplog.records])


def test_KIS_overlapping_pages_may_not_replace_a_conflicting_candle(monkeypatch):
    from src.agents.technical.infrastructure import kis_client as kis
    from datetime import date
    calls=[]
    def chart(*args,**kwargs):
        calls.append(True)
        return {'output2':[kis_bar(close='100' if len(calls)==1 else '101')]}
    monkeypatch.setattr(kis,'_call_chart',chart)
    with pytest.raises(kis.KisFieldError,match='^KIS_MARKET_CONFLICTING_BAR$'):
        kis._fetch_ohlcv_range('000720','D',date(2023,1,1),date(2024,1,5),None,
            settings=config.KISSettings('fake-key','fake-secret','https://kis.invalid'),_token='fake-token')
    assert len(calls)==2


@pytest.mark.parametrize('text',['과매수 하세요','과매도 해 주세요','과매수 조금만 하세요','과매도 하십시오'])
def test_spaced_state_noun_cannot_hide_action_directive(text):
    from src.agents.technical.domain.interpretation.trajectory_eval import contains_forbidden_terms
    assert contains_forbidden_terms(text)


def test_noop_trace_still_logs_closed_diagnostics_in_the_rendered_message(caplog):
    import logging
    from src.agents.technical.domain.interpretation import trajectory_eval as ev
    from src.agents.technical.application.orchestration import pipeline_steps as steps
    from src.agents.technical.infrastructure.observability.trace_logger import TraceLogger
    result=ev.EvalResult(False,(ev.TargetFailure('interpretation.text','numeric_claim_unsupported'),
        ev.TargetFailure('private-candidate-sentinel','private-reason-sentinel','private-info-sentinel')))
    with caplog.at_level(logging.WARNING,logger=steps.logger.name):
        steps._emit_validation(TraceLogger(None,trace_id='fixed'),steps._Attempt(False,{},result),1)
    messages=[x.getMessage() for x in caplog.records]
    assert any('numeric_claim_unsupported' in m and 'interpretation.text' in m for m in messages)
    assert 'private-candidate-sentinel' not in str(messages) and 'private-reason-sentinel' not in str(messages) and 'private-info-sentinel' not in str(messages)


@pytest.mark.parametrize('text',['과매수를 하세요','과매도 하시죠','과매수 해보세요','과매수 적극 실행','과매도 부탁합니다'])
def test_only_closed_technical_state_contexts_are_exempt(text):
    from src.agents.technical.domain.interpretation.trajectory_eval import contains_forbidden_terms
    assert contains_forbidden_terms(text)


@pytest.mark.parametrize('field',['key_drivers','warning_points'])
def test_numeric_list_diagnostic_targets_normalize_exact_indices_only(field):
    from src.agents.technical.domain.interpretation import trajectory_eval as ev
    result=ev.EvalResult(False,(ev.TargetFailure(f'interpretation.{field}[0]','numeric_claim_unsupported'),
        ev.TargetFailure(f'interpretation.{field}[23]','numeric_claim_unsupported')))
    assert ev.diagnostic_codes(result)==[dict(target='interpretation.'+field,reason='numeric_claim_unsupported')]
    for suffix in ('[-1]','[00]','[1.0]','[True]','[0]private','[private]'):
        assert ev.diagnostic_codes(ev.EvalResult(False,(ev.TargetFailure('interpretation.'+field+suffix,'numeric_claim_unsupported'),)))[0]['target']=='output'


def weekly_source(start,end,*,missing=()):
    from datetime import timedelta
    rows=[];cursor=start
    while cursor<=end:
        if cursor.weekday()==0 and cursor.isoformat() not in missing:rows.append(kis_bar(cursor.strftime('%Y%m%d')))
        cursor+=timedelta(days=1)
    return rows


@pytest.mark.parametrize('cap_first',[True,False])
def test_weekly_chunk_pages_from_returned_oldest_not_requested_lower_bound(monkeypatch,cap_first):
    from datetime import date,timedelta
    from src.agents.technical.infrastructure import kis_client as kis
    from src.agents.technical.application.nodes.chart_generate import run_chart_generate
    start=date(2020,9,15);end=date(2026,11,13);source=weekly_source(start,end);calls=[]
    def chart(settings,token,ticker,period,lo,hi,client,**kwargs):
        got=sorted([x for x in source if lo<=x['stck_bsop_date']<=hi],key=lambda x:x['stck_bsop_date'],reverse=True)
        if not calls and cap_first:
            # Synthetic valid short page: omit the oldest week in this window.
            # This matches the observed date pattern, NOT proven KIS behavior.
            assert got[-1]['stck_bsop_date']=='20250324';got=got[:-1]
        calls.append((lo,hi,[x['stck_bsop_date'] for x in got]))
        return {'output2':got[:100]}
    monkeypatch.setattr(kis,'_call_chart',chart)
    rows=kis._fetch_ohlcv_range('000720','W',start,end,None,settings=config.KISSettings('fake-key','fake-secret','https://kis.invalid'),_token='fake-token')
    assert [x.date for x in rows]==[date.fromisoformat(x['stck_bsop_date'][:4]+'-'+x['stck_bsop_date'][4:6]+'-'+x['stck_bsop_date'][6:]).isoformat() for x in source]
    assert '2025-03-24' in [x.date for x in rows] and len(calls)<=config.KIS_MAX_CHUNKS
    if cap_first:
        assert calls[0][0]=='20250323' and min(calls[0][2])=='20250331'
        assert calls[1][1]=='20250330' # no replay of the previously accepted week
    for previous,current in zip(calls,calls[1:]):
        assert previous[2] and current[1]==(date.fromisoformat(previous[2][-1][:4]+'-'+previous[2][-1][4:6]+'-'+previous[2][-1][6:])-timedelta(days=1)).strftime('%Y%m%d')
    chart=next(x for x in run_chart_generate(st.DAILY,rows,st.MONTHLY) if x.period.value=='5y')
    assert '2025-03-24' in [x['date'] for x in chart.model_dump(mode='json')['chart_data']['candles']]


@pytest.mark.parametrize('behavior',['repeat','empty','capped'])
def test_pagination_no_progress_and_cap_are_not_silent_completion(monkeypatch,behavior):
    from datetime import date
    from src.agents.technical.infrastructure import kis_client as kis
    calls=[]
    def chart(settings,token,ticker,period,lo,hi,client,**kwargs):
        calls.append((lo,hi))
        available=weekly_source(date(2020,9,15),date(2026,11,13))
        eligible=[r for r in available if lo<=r['stck_bsop_date']<=hi]
        return {'output2':[] if behavior=='empty' else [kis_bar('20261109')] if behavior=='repeat' else eligible[-1:]}
    monkeypatch.setattr(kis,'_call_chart',chart)
    def run():return kis._fetch_ohlcv_range('000720','W',date(2020,9,15),date(2026,11,13),None,settings=config.KISSettings('fake-key','fake-secret','https://kis.invalid'),_token='fake-token')
    if behavior=='empty':assert run()==[] and len(calls)==1
    elif behavior=='repeat':
        with pytest.raises(kis.KisRangeIncompleteError,match='^KIS_RANGE_NO_PROGRESS$'):run()
        assert len(calls)==2
    else:
        with pytest.raises(kis.KisRangeIncompleteError):run()
        assert len(calls)==config.KIS_MAX_CHUNKS


def test_unreturned_week_is_not_invented_and_holiday_week_labels_are_preserved(monkeypatch):
    from datetime import date
    from src.agents.technical.infrastructure import kis_client as kis
    source=[kis_bar(d) for d in ('20250304','20250310','20250317','20250331')];calls=[]
    def chart(settings,token,ticker,period,lo,hi,client,**kwargs):
        calls.append((lo,hi));return {'output2':[x for x in reversed(source) if lo<=x['stck_bsop_date']<=hi]}
    monkeypatch.setattr(kis,'_call_chart',chart)
    rows=kis._fetch_ohlcv_range('000720','W',date(2025,3,1),date(2025,3,31),None,settings=config.KISSettings('fake-key','fake-secret','https://kis.invalid'),_token='fake-token')
    assert [r.date for r in rows]==['2025-03-04','2025-03-10','2025-03-17','2025-03-31']
    assert len(calls)==2 # explicit empty tail, not a completeness guarantee


@pytest.mark.parametrize('name',[
    'test_multiple_chunks_walk_backward','test_dedup_and_ascending','test_range_filter_drops_out_of_range',
    'test_empty_chunk_stops','test_stops_when_oldest_not_progressing','test_max_chunks_incomplete_raises',
    'test_reaches_start_within_max_chunks_returns','test_reversed_range_fail_fast_before_network'])
def test_existing_KIS_pagination_regressions_through_protected_source_copy(name,monkeypatch):
    from tests.technical import test_kis_client_mapping as existing
    assert Path(existing.__spec__.origin).resolve()==ROOT/'ai/tests/technical/test_kis_client_mapping.py'
    getattr(existing,name)(monkeypatch)


@pytest.mark.parametrize('failures',[0,2])
def test_received_date_pagination_keeps_existing_owned_market_send_cap(monkeypatch,failures):
    from datetime import date,timedelta
    from src.agents.technical.infrastructure import kis_client as kis
    end=date(2026,11,13);source={};cursor=end-timedelta(days=2300)
    while cursor<=end:
        raw=kis_bar(cursor.strftime('%Y%m%d'))
        if cursor.weekday()<5:source.setdefault('D',[]).append(raw)
        if cursor.weekday()==0:source.setdefault('W',[]).append(raw)
        if cursor.day==1:source.setdefault('M',[]).append(raw)
        cursor+=timedelta(days=1)
    settings=config.KISSettings('fake-key','fake-secret','https://kis.invalid');calls=[];attempts={}
    hook,observed=kis.kis_request_gate(settings=settings,ticker='000720',deadline=SimpleNamespace(remaining_seconds=lambda:30),stopped=threading.Event(),token_limit=3,market_limit=30)
    def respond(request):
        calls.append(request)
        if request.method=='POST':return httpx.Response(200,json={'access_token':'fake-token','expires_in':86400})
        key=str(request.url);attempts[key]=attempts.get(key,0)+1
        if attempts[key]<=failures:return httpx.Response(429,json={})
        params=request.url.params;rows=[r for r in source[params['FID_PERIOD_DIV_CODE']] if params['FID_INPUT_DATE_1']<=r['stck_bsop_date']<=params['FID_INPUT_DATE_2']]
        return httpx.Response(200,json={'rt_cd':'0','output2':list(reversed(rows))[:100]})
    monkeypatch.setattr(kis,'_sleep_backoff',lambda attempt:None)
    with httpx.Client(transport=httpx.MockTransport(respond),trust_env=False,follow_redirects=False,event_hooks={'request':[hook]}) as client:
        if failures:
            with pytest.raises(kis.KisApiError,match='^KIS invocation limit reached$'):
                kis.fetch_multi_timeframe_ohlcv('000720',end_date=end,client=client,settings=settings)
            assert observed()=={'token':1,'market':30}
        else:
            result=kis.fetch_multi_timeframe_ohlcv('000720',end_date=end,client=client,settings=settings)
            for period,rows in result.items():
                lower=(end-timedelta(days=config.KIS_FETCH_LOOKBACK_DAYS[period])).strftime('%Y%m%d')
                assert [r.date for r in rows]==[date.fromisoformat(r['stck_bsop_date'][:4]+'-'+r['stck_bsop_date'][4:6]+'-'+r['stck_bsop_date'][6:]).isoformat() for r in source[period] if r['stck_bsop_date']>=lower]
            assert observed()['token']==1 and observed()['market']<=30
        assert len([x for x in calls if x.method=='GET'])==observed()['market']


@pytest.mark.parametrize('partial_month',[False,True])
def test_month_end_and_progressing_month_keep_original_terminal_request(monkeypatch,partial_month):
    from datetime import date
    from src.agents.technical.infrastructure import kis_client as kis
    calls=[]
    def chart(settings,token,ticker,period,lo,hi,client,**kwargs):
        calls.append((lo,hi));assert period=='M'
        # A cutoff-sensitive producer could return May 28 if asked a second
        # time. The monthly terminal contract must not make that request.
        dates=['20260529','20260630']+(['20260703'] if partial_month else [])
        return {'output2':[kis_bar(d) for d in reversed(dates)]}
    monkeypatch.setattr(kis,'_call_chart',chart)
    rows=kis._fetch_ohlcv_range('000720','M',date(2026,5,1),date(2026,7,3),None,settings=config.KISSettings('fake-key','fake-secret','https://kis.invalid'),_token='fake-token')
    assert calls==[('20260501','20260703')]
    assert [r.date for r in rows]==['2026-05-29','2026-06-30']+(['2026-07-03'] if partial_month else [])


def test_weekly_cutoff_cannot_accumulate_another_version_of_same_week(monkeypatch):
    from datetime import date
    from src.agents.technical.infrastructure import kis_client as kis
    calls=[]
    def chart(settings,token,ticker,period,lo,hi,client,**kwargs):
        calls.append((lo,hi));return {'output2':[kis_bar('20260703' if len(calls)==1 else '20260702')]}
    monkeypatch.setattr(kis,'_call_chart',chart)
    with pytest.raises(kis.KisRangeIncompleteError,match='^KIS_WEEKLY_PERIOD_AMBIGUOUS$'):
        kis._fetch_ohlcv_range('000720','W',date(2026,5,1),date(2026,7,3),None,settings=config.KISSettings('fake-key','fake-secret','https://kis.invalid'),_token='fake-token')
    assert len(calls)==2


@pytest.mark.parametrize('extra',['19990104','20210301','20270104'])
def test_weekly_mixed_outside_rows_cannot_prove_progress_or_completion(monkeypatch,extra):
    from datetime import date
    from src.agents.technical.infrastructure import kis_client as kis
    start=date(2020,9,15);end=date(2026,11,13);source=weekly_source(start,end);calls=[]
    def chart(settings,token,ticker,period,lo,hi,client,**kwargs):
        got=[r for r in reversed(source) if lo<=r['stck_bsop_date']<=hi][:100]
        if not calls:got=got[:-1]+[kis_bar(extra)] # short valid prefix plus an unrelated row
        calls.append((lo,hi))
        return {'output2':got}
    monkeypatch.setattr(kis,'_call_chart',chart)
    rows=kis._fetch_ohlcv_range('000720','W',start,end,None,settings=config.KISSettings('fake-key','fake-secret','https://kis.invalid'),_token='fake-token')
    assert [r.date.replace('-','') for r in rows]==[r['stck_bsop_date'] for r in source]
    assert '2025-03-24' in [r.date for r in rows] and len(calls)<=config.KIS_MAX_CHUNKS


@pytest.mark.parametrize('dates',[['19990104'],['20270104'],['19990104','20270104']])
def test_weekly_nonempty_response_without_request_window_evidence_is_incomplete(monkeypatch,dates):
    from datetime import date
    from src.agents.technical.infrastructure import kis_client as kis
    calls=[]
    def chart(*args,**kwargs):calls.append(True);return {'output2':[kis_bar(d) for d in dates]}
    monkeypatch.setattr(kis,'_call_chart',chart)
    with pytest.raises(kis.KisRangeIncompleteError,match='^KIS_RANGE_NO_PROGRESS$'):
        kis._fetch_ohlcv_range('000720','W',date(2020,9,15),date(2026,11,13),None,settings=config.KISSettings('fake-key','fake-secret','https://kis.invalid'),_token='fake-token')
    assert calls==[True]


def test_safe_market_sample_recovers_skipped_week_without_changing_values(monkeypatch):
    # Three normalized public market candles from the approved current comparison.
    # The projected fake pages do not replay the unrecorded historic responses or
    # claim the updated long next-window request has been tested live.
    from datetime import date
    from src.agents.technical.infrastructure import kis_client as kis
    samples = [{'close': 34200,
  'date': '2025-03-17',
  'high': 34450,
  'low': 31650,
  'open': 32700,
  'trading_value': 87786722575,
  'volume': 2617464},
 {'close': 34700,
  'date': '2025-03-24',
  'high': 35500,
  'low': 33200,
  'open': 33700,
  'trading_value': 99080542400,
  'volume': 2865047},
 {'close': 35700,
  'date': '2025-03-31',
  'high': 36500,
  'low': 34250,
  'open': 34550,
  'trading_value': 134842725000,
  'volume': 3768328}]
    def raw(row):
        return dict(stck_bsop_date=row['date'].replace('-',''),stck_oprc=str(row['open']),
            stck_hgpr=str(row['high']),stck_lwpr=str(row['low']),stck_clpr=str(row['close']),
            acml_vol=str(row['volume']),acml_tr_pbmn=str(row['trading_value']))
    calls=[]
    def chart(settings,token,ticker,period,lo,hi,client,**kwargs):
        calls.append((lo,hi))
        available = samples[-1:] if len(calls)==1 else samples
        return {'output2':[raw(row) for row in reversed(available) if lo<=row['date'].replace('-','')<=hi]}
    monkeypatch.setattr(kis,'_call_chart',chart)
    rows=kis._fetch_ohlcv_range('000720','W',date(2020,9,15),date(2026,11,13),None,
        settings=config.KISSettings('fake-key','fake-secret','https://kis.invalid'),_token='fake-token')
    assert calls[0]==('20250323','20261113') and calls[1][1]=='20250330'
    assert [row.model_dump(mode='json') for row in rows]==samples
    assert next(row for row in rows if row.date=='2025-03-24').model_dump(mode='json')==samples[1]


def test_two_observed_normalized_weekly_responses_replay_exact_request_chain(monkeypatch):
    # Normalized market fields only: first 85 rows from the approved long
    # comparison, then 2 rows from its short comparison. No auth/raw response.
    from datetime import date
    from src.agents.technical.infrastructure import kis_client as kis
    sample_csv = """2025-03-31,34550,36500,34250,35700,3768328,134842725000
2025-04-07,35000,38200,33950,38200,3959866,144335655225
2025-04-14,37900,39850,37450,39350,3210699,125126188850
2025-04-21,39350,40500,38050,39350,2865127,112241978875
2025-04-28,39500,41950,39450,40800,3023283,124331611950
2025-05-07,40350,43500,40200,41200,2597893,110058547000
2025-05-12,42400,45000,42300,44600,3386191,148728391550
2025-05-19,44500,54400,44350,54200,7280414,363348828605
2025-05-26,56200,66900,55000,63800,15839067,979299909900
2025-06-02,61900,71100,61800,68000,7226849,482108615900
2025-06-09,67600,78800,65000,73600,12250807,892956439000
2025-06-16,74200,81600,74000,75300,8887667,684299738050
2025-06-23,72900,85100,72600,78800,13977549,1104127055050
2025-06-30,80600,83900,70700,71300,8503005,648841620400
2025-07-07,69100,74900,69000,72100,5649354,409913166600
2025-07-14,71300,75200,68000,70900,6257390,446697816002
2025-07-21,71600,71600,65000,66800,7728897,521119766850
2025-07-28,65700,68500,63400,65600,8332676,551507535176
2025-08-04,65000,71700,64000,68400,6131945,423123935150
2025-08-11,68500,69400,62100,63800,5072345,328781760250
2025-08-18,63200,64200,54350,62500,7975994,480724735700
2025-08-25,64500,65500,61000,62100,4011401,251216582500
2025-09-01,61200,61800,58900,59600,3570640,213577840650
2025-09-08,60200,61300,57100,59400,3628298,215269345450
2025-09-15,60200,62700,56200,57000,5795961,342969323050
2025-09-22,57700,58200,54600,54800,3466814,194234570950
2025-09-29,55300,57300,54100,55500,3105030,172329606624
2025-10-10,55100,56900,54800,56200,862602,48526819650
2025-10-13,55600,63000,54800,56000,7489612,442937304850
2025-10-20,56400,68000,55700,66600,7196737,437853666050
2025-10-27,73500,76400,67200,70300,15810451,1125545888650
2025-11-03,69000,69200,60600,61900,9403480,610492808900
2025-11-10,62100,65900,61600,62800,5205209,329420811750
2025-11-17,62900,64400,58700,59300,4416219,270969613150
2025-11-24,60600,68200,59200,67000,7587649,491229027600
2025-12-01,67500,75900,63400,75100,14272362,1001914247450
2025-12-08,75100,78500,71000,78000,13120532,985922419750
2025-12-15,70700,74500,68000,69400,11653491,821521435450
2025-12-22,70500,71800,67900,68700,4508764,317206484350
2025-12-29,68100,71100,67900,69000,3639870,251092321100
2026-01-05,70200,77900,70100,75800,5931319,442934293050
2026-01-12,78000,105900,77900,104300,24897738,2306846201900
2026-01-19,108500,122000,103000,109200,12194789,1336411489800
2026-01-26,109000,110800,102400,102600,7617741,806969726420
2026-02-02,99600,119000,98000,106600,8018863,870720194350
2026-02-09,110600,121400,109500,114300,7651346,878226420495
2026-02-19,116100,132100,115500,128300,3676108,458505103200
2026-02-23,132000,176900,130100,164700,17819885,2799493273250
2026-03-03,162900,166000,122700,156800,7976635,1154511623200
2026-03-09,147400,169000,139800,164400,8029905,1248648216950
2026-03-16,166400,174900,157500,164000,6102741,1022009763882
2026-03-23,165600,165600,142600,149800,5826274,886638639700
2026-03-30,140800,165400,139600,151100,5623722,849752812950
2026-04-06,151100,198400,150100,179500,11099337,1981915557950
2026-04-13,172000,186500,170200,177000,5532561,989463543050
2026-04-20,171800,179500,166800,173000,8211582,1430920415594
2026-04-27,173600,179300,160900,161800,4873561,824899744700
2026-05-04,163100,175500,157600,164000,4788255,784380271900
2026-05-11,162000,170900,150200,155000,6139897,993976692208
2026-05-18,143800,154600,130000,150300,4852547,687066012950
2026-05-26,157100,160700,135800,147000,3526789,513619336800
2026-06-01,142500,144100,126600,131900,3335373,451731428100
2026-06-08,116000,157500,115100,157500,4744958,599979995650
2026-06-15,157600,157700,125000,128600,6594358,937407555300
2026-06-22,126100,132100,100000,103300,4583287,530632464150
2026-06-29,102400,122700,101200,115300,2950697,338097859000
2026-07-06,116400,120200,96400,107200,3233794,340400566150
2026-07-13,105600,109200,94200,99000,1837162,183909047000
2026-07-20,94700,111150,88800,106200,2572156,256929926700
2026-07-27,108100,108700,77700,94600,3337026,300166304950
2026-08-03,94500,115800,89000,109900,2916532,305884946450
2026-08-10,110400,121700,105800,115800,2276430,258245433300
2026-08-18,116200,118700,103500,105600,2401284,269064818950
2026-08-24,105700,135900,103300,128900,6020165,748506774650
2026-08-31,126000,126000,110700,119700,3216885,380913360850
2026-09-07,119400,142000,117600,134900,4758728,628595098150
2026-09-14,133000,133100,123300,124800,2738837,346579071700
2026-09-21,126700,136100,120200,121100,2612439,330430315200
2026-09-28,121900,126800,113000,114400,2839013,335964976900
2026-10-06,115100,116600,103950,107800,2070291,226746896600
2026-10-12,104000,104500,89200,93800,3421919,332270414516
2026-10-19,92100,96900,88200,92500,2316741,214161034300
2026-10-26,90000,97100,81600,83600,3419095,305242559550
2026-11-02,81000,91600,73100,78100,3051908,257321526035
2026-11-09,76400,87400,74800,84000,2361598,192730782150
2025-03-17,32700,34450,31650,34200,2617464,87786722575
2025-03-24,33700,35500,33200,34700,2865047,99080542400"""
    columns=('date','open','high','low','close','volume','trading_value')
    all_rows=[dict(zip(columns,line.split(','))) for line in sample_csv.splitlines()]
    pages=[all_rows[:85],all_rows[85:]];expected_windows=[('20250323','20261113'),('20250317','20250330')];calls=[]
    def chart(settings,token,ticker,period,lo,hi,client,**kwargs):
        i=len(calls);assert i<2 and (lo,hi)==expected_windows[i];calls.append((lo,hi))
        return {'output2':[dict(stck_bsop_date=r['date'].replace('-',''),stck_oprc=r['open'],stck_hgpr=r['high'],stck_lwpr=r['low'],stck_clpr=r['close'],acml_vol=r['volume'],acml_tr_pbmn=r['trading_value']) for r in reversed(pages[i])]}
    monkeypatch.setattr(kis,'_call_chart',chart)
    result=kis._fetch_ohlcv_range('000720','W',date(2025,3,17),date(2026,11,13),None,
        settings=config.KISSettings('fake-key','fake-secret','https://kis.invalid'),_token='fake-token')
    expected=sorted([dict(date=r['date'],**{k:float(r[k]) for k in columns[1:5]},volume=int(r['volume']),trading_value=int(r['trading_value'])) for r in all_rows],key=lambda r:r['date'])
    assert len(result)==87 and [r.model_dump(mode='json') for r in result]==expected
    assert result[1].date=='2025-03-24' and calls==expected_windows


# Explanation input contracts: unchanged validators and actual compiled graph.
@pytest.mark.parametrize('consensus', ['strong_negative','strong_positive','neutral','weak_negative','weak_positive'])
@pytest.mark.parametrize('regime_name', ['downtrend','sideways','overheated','oversold_rebound_watch','uptrend_intact','bullish_reversal_watch'])
def test_complete_prompt_example_passes_real_parser_and_verifier(consensus,regime_name):
    from src.agents.technical.domain.models.enums import Regime,Consensus
    c=numeric_context();regime=c.regime.model_copy(update={'daily_regime':Regime(regime_name),'final_regime':Regime(regime_name)})
    signal=c.signal.model_copy(update={'consensus':Consensus(consensus)})
    before=copy.deepcopy((regime.model_dump(),signal.model_dump(),c.rows,c.risks))
    payload=c.node.build_payload(regime=regime,signal=signal,signals=c.rows,risks=c.risks)
    example=payload['validated_output_example']
    assert example is not None
    assert set(example)==c.node._ALLOWED_TOP_KEYS
    parsed=c.node.parse_llm_output(json.dumps(example,ensure_ascii=False))
    assert c.node.verify(parsed,regime=regime,signal=signal,signals=c.rows,risks=c.risks).passed
    assert before==(regime.model_dump(),signal.model_dump(),c.rows,c.risks)
    assert payload['technical_signals']==[dict(indicator=s.indicator.value,signal=s.signal.value,value=s.value,metrics=s.metrics) for s in c.rows]


@pytest.mark.parametrize('signal_name',['positive','neutral','negative'])
def test_detail_examples_use_own_signal_and_calculation_meaning_not_global_labels(signal_name):
    from dataclasses import replace
    from src.agents.technical.domain.models.enums import Signal,Consensus
    c=numeric_context();rows=[replace(s,signal=Signal(signal_name)) for s in c.rows]
    signal=c.signal.model_copy(update={'consensus':Consensus.STRONG_NEGATIVE})
    payload=c.node.build_payload(regime=c.regime,signal=signal,signals=rows,risks=c.risks)
    expressions=payload['verify_expressions']
    assert expressions['must_avoid_scope']=='interpretation_text' and '긍정' in expressions['must_avoid']
    expected=c.node.SIGNAL_RULES[Signal(signal_name)]
    assert expressions['detail_must_avoid_by_indicator']=={s.indicator.value:list(expected.conflict_any) for s in rows}
    example=payload['validated_output_example'];assert example is not None
    assert c.node.verify(example,regime=c.regime,signal=signal,signals=rows,risks=c.risks).passed
    pattern=next(x for x in example['details'] if x['indicator']=='pattern')
    assert {'positive':'양봉','negative':'음봉','neutral':'도지'}[signal_name] in pattern['detail_reason']
    assert '근거 부족' not in pattern['detail_reason']
    for entry in example['details']:
        assert entry['detail_reason']!=entry['detail'] and '분류됩니다' not in entry['detail_reason']
    if signal_name=='positive':assert '긍정' in pattern['detail'] and '긍정' not in example['interpretation_text']


def test_prompt_templates_share_complete_shape_scope_and_optional_reference_contract():
    c=numeric_context();payload=c.node.build_payload(regime=c.regime,signal=c.signal,signals=c.rows,risks=c.risks)
    texts=[c.node.load_prompt(n) for n in (c.node.INTERPRET_PROMPT,c.node.REGENERATE_PROMPT)]
    assert texts[0].split('\n',2)[2]==texts[1].split('\n',2)[2]
    for text in texts:
        layout=json.loads(text.split('```json\n',1)[1].split('\n```',1)[0])
        assert set(layout)==c.node._ALLOWED_TOP_KEYS
        assert set(layout['details'][0])==c.node._ALLOWED_DETAIL_KEYS
        assert 'must_avoid_scope=interpretation_text' in text and 'detail_must_avoid_by_indicator' in text
        assert '항목은 필수가 아닙니다' in text and '**필드 전체 그대로**' in text
        assert '생략·null·빈 문자열' in text and '양봉·음봉·도지' in text
        assert '가능하면 2~3문장' not in text and '가장 흔한' not in text and 'annotation-only' not in text
        assert '정확히 복사한 숫자도' in text and '{payload_json}' not in c.node.render_prompt(text,payload)


def test_repair_guidance_is_bounded_code_only_and_replacements_keep_strict_validation():
    from src.agents.technical.domain.interpretation import trajectory_eval as ev
    c=numeric_context();bad=copy.deepcopy(c.good)
    bad['interpretation_text']+=' 현재가 999원입니다.'
    for entry in bad['details']:
        if entry['indicator'] in ('moving_average','rsi'):entry['detail_watchpoint']='현재 50입니다.'
        if entry['indicator']=='rsi':entry['detail_reason']='매수 하세요.'
        if entry['indicator']=='pattern':entry['detail_reason']='강한 긍정과 강한 부정입니다.'
    failed=c.node.verify(bad,regime=c.regime,signal=c.signal,signals=c.rows,risks=c.risks)
    guidance=c.node.repair_guidance(failed,signals=c.rows)
    assert 1<=len(guidance)<=12 and '999' not in json.dumps(guidance) and '매수 하세요' not in json.dumps(guidance)
    assert any(x['reason']=='numeric_claim_unsupported' and x['target']=='interpretation.text' for x in guidance)
    repaired=copy.deepcopy(c.good)
    entries={x['indicator']:x for x in repaired['details']}
    for item in guidance:
        if 'whole_field_replacement' not in item:continue
        target=item['target'];indicator=target.split('[',1)[1].split(']',1)[0];field=target.rsplit('.',1)[1]
        entries[indicator][field]=item['whole_field_replacement']
        assert item['may_omit'] is (field!='detail')
        assert item['must_include_signal_label'] is (field=='detail')
    assert c.node.verify(repaired,regime=c.regime,signal=c.signal,signals=c.rows,risks=c.risks).passed
    for indicator in ('moving_average','rsi'):
        damaged=copy.deepcopy(repaired);entry=next(x for x in damaged['details'] if x['indicator']==indicator)
        entry['detail_watchpoint']+=' 현재값 50입니다.'
        result=c.node.verify(damaged,regime=c.regime,signal=c.signal,signals=c.rows,risks=c.risks)
        assert not result.passed and indicator in result.failed_indicators
    sentinel='UNTRUSTED_PRIVATE_DIAGNOSTIC'
    unknown=ev.EvalResult(False,tuple(ev.TargetFailure(sentinel,sentinel,sentinel) for _ in range(200)))
    safe=c.node.repair_guidance(unknown,signals=c.rows)
    assert len(safe)<=12 and sentinel not in json.dumps(safe)
    assert all(x['target']=='output' and x['reason']=='unclassified' for x in safe)


@pytest.mark.parametrize('optional',[None,'','absent'])
def test_repair_optional_fields_keep_null_empty_omission_backfill(optional):
    c=numeric_context();reply=copy.deepcopy(c.good)
    for entry in reply['details']:
        for field in ('detail_reason','detail_caution','detail_watchpoint'):
            if optional=='absent':entry.pop(field,None)
            else:entry[field]=optional
    parsed=c.node.parse_llm_output(json.dumps(reply))
    assert c.node.verify(parsed,regime=c.regime,signal=c.signal,signals=c.rows,risks=c.risks).passed
    from src.agents.technical.domain.models.enums import GenerationSource
    details=c.node.details_from_llm(parsed,signals=c.rows,source=GenerationSource.LLM)
    for detail,row in zip(details,c.rows):
        defaults=c.node.fallback_detail(row.indicator,row.signal,row.metrics)
        assert all(getattr(detail,k)==getattr(defaults,k) for k in ('detail_reason','detail_caution','detail_watchpoint'))


async def test_actual_compiled_graph_uses_targeted_regeneration_contract_without_extra_calls():
    from src.agents.technical.infrastructure.observability.trace_logger import InMemoryTraceSink
    c=numeric_context();bad=copy.deepcopy(c.good);bad['interpretation_text']+=' 現在値999円'
    for entry in bad['details']:
        if entry['indicator'] in ('moving_average','rsi'):entry['detail_watchpoint']='現在値 50'
        if entry['indicator']=='rsi':entry['detail_reason']='매수하세요.'
        if entry['indicator']=='pattern':entry['detail_caution']='강한 긍정과 강한 부정입니다.'
    supplied=[]
    def regenerate(prompt):
        assert isinstance(prompt,str)
        payload=json.loads(prompt.rsplit('```json\n',1)[1].split('\n```',1)[0]);supplied.append(payload)
        assert payload['validation_feedback'] and payload['validation_repair_guidance']
        assert '999円' not in json.dumps(payload,ensure_ascii=False)
        return json.dumps(payload['validated_output_example'],ensure_ascii=False)
    sink=InMemoryTraceSink();h=execution_fixture(trace_sink=sink,interpret_scripts=[json.dumps(bad),regenerate])
    result=await h.instance.execute(h.value,'f'*64);out=result['data']['result']
    assert out['verification']['outcome']=='passed' and out['verification']['regen_count']==1
    assert out['interpretation']['source']=='llm_regenerated'
    assert all(x['detail_source']=='llm_regenerated' for x in out['technical_signals'])
    assert out['signal']==c.signal.model_dump(mode='json')
    assert [(x['indicator'],x['signal'],x['value'],x['metrics'],x['weight']) for x in out['technical_signals']]==[
        (s.indicator.value,s.signal.value,s.value,s.metrics,s.weight) for s in c.rows]
    assert len(supplied)==1 and len(h.events)==8 and len(h.budgets)==1
    assert len(h.starts)==len(h.observations)==1
    events=[x for x in sink.events if x['event_type']=='validation' and x['node']=='interpret_report']
    assert len(events)==2 and events[0]['status']=='failed' and events[1]['status']=='success'
    assert runtime._ACTIVE_TASK is None and not ATTEMPTS


# Observed market-only projection from the owned 000720 report (KIS D chart).
# Captured 2026-11-13; provider publication/close finality unreported. No raw
# request, approval, owner identity, token or model candidate is included.
# Visible 1y chart history is NOT the complete original D/W/M engine input.
OBSERVED_000720_DAILY = (
    ('2025-11-13', 62000, 65200, 61600, 65200, 1615590, 102896673250),
    ('2025-11-14', 63700, 65900, 62300, 62800, 1161641, 74107461450),
    ('2025-11-17', 62900, 64400, 62200, 63900, 783255, 49622235300),
    ('2025-11-18', 63100, 64000, 60100, 60800, 1211557, 74496794200),
    ('2025-11-19', 61400, 61800, 59400, 60600, 775878, 47058697900),
    ('2025-11-20', 61800, 63500, 61500, 61600, 751829, 46857363450),
    ('2025-11-21', 60000, 60200, 58700, 59300, 893700, 52934522300),
    ('2025-11-24', 60600, 61500, 59200, 59700, 873020, 52515206050),
    ('2025-11-25', 61100, 63000, 60200, 60800, 733921, 45002455350),
    ('2025-11-26', 62700, 66400, 62700, 65500, 2724164, 177248674950),
    ('2025-11-27', 65600, 68200, 64500, 65200, 1603476, 105962509850),
    ('2025-11-28', 65200, 67800, 64500, 67000, 1653068, 110500181400),
    ('2025-12-01', 67500, 67600, 64000, 64100, 1105629, 71930946650),
    ('2025-12-02', 64100, 66400, 63400, 65900, 884562, 57905067300),
    ('2025-12-03', 68200, 70900, 65800, 70500, 3685154, 254857446500),
    ('2025-12-04', 70700, 70700, 67100, 68300, 2100648, 143648785850),
    ('2025-12-05', 68300, 75900, 67700, 75100, 6496369, 473572001150),
    ('2025-12-08', 75100, 77800, 73200, 74100, 4018024, 302750411150),
    ('2025-12-09', 74100, 74200, 72300, 72900, 1122926, 81879525750),
    ('2025-12-10', 73200, 73700, 71000, 71800, 1344321, 97083642000),
    ('2025-12-11', 71800, 77200, 71600, 73600, 3186617, 238474872650),
    ('2025-12-12', 75000, 78500, 74500, 78000, 3448644, 265733968200),
    ('2025-12-15', 70700, 74500, 70000, 73100, 4609253, 328507426300),
    ('2025-12-16', 72000, 72100, 69000, 69500, 2738310, 191486418250),
    ('2025-12-17', 69800, 71600, 69300, 70800, 1686432, 119309181550),
    ('2025-12-18', 69000, 70500, 68000, 69400, 1236991, 85972810800),
    ('2025-12-19', 70000, 71200, 68800, 69400, 1382505, 96245598550),
    ('2025-12-22', 70500, 71800, 70300, 71100, 1083046, 76929552550),
    ('2025-12-23', 71100, 71600, 69800, 70000, 891216, 62774906950),
    ('2025-12-24', 70100, 70800, 69500, 70000, 666441, 46737841250),
    ('2025-12-26', 69900, 70300, 67900, 68700, 1868061, 130764183600),
    ('2025-12-29', 68100, 70800, 67900, 70000, 1373087, 94301788050),
    ('2025-12-30', 70000, 71100, 68800, 70100, 1169220, 81472803200),
    ('2026-01-02', 70100, 70100, 68400, 69000, 1097563, 75317729850),
    ('2026-01-05', 70200, 74200, 70100, 74000, 1630936, 119535112500),
    ('2026-01-06', 74400, 76300, 72800, 76200, 1196318, 89626849250),
    ('2026-01-07', 75600, 77900, 73800, 74700, 985607, 73781164750),
    ('2026-01-08', 74900, 76400, 74700, 75000, 1053683, 79314007700),
    ('2026-01-09', 76400, 77900, 74300, 75800, 1064775, 80677158850),
    ('2026-01-12', 78000, 92700, 77900, 91100, 10105765, 886301714000),
    ('2026-01-13', 88800, 92000, 87400, 92000, 3254252, 292503091600),
    ('2026-01-14', 92000, 100100, 91300, 94900, 6077551, 583723125950),
    ('2026-01-15', 94000, 100000, 92600, 99900, 2337522, 226567613600),
    ('2026-01-16', 99600, 105900, 97400, 104300, 3122648, 317750656750),
    ('2026-01-19', 108500, 109400, 103000, 107900, 1759969, 187799941250),
    ('2026-01-20', 106600, 111600, 105400, 107600, 2247114, 243098335000),
    ('2026-01-21', 103000, 109500, 103000, 108500, 1896790, 203321563550),
    ('2026-01-22', 111500, 112300, 103000, 104000, 1685978, 179740817800),
    ('2026-01-23', 105400, 122000, 105100, 109200, 4604938, 522450832200),
    ('2026-01-26', 109000, 110800, 103900, 106200, 1528569, 162072401900),
    ('2026-01-27', 110500, 110500, 104400, 105900, 1305240, 138686603550),
    ('2026-01-28', 105900, 107000, 103600, 105700, 1384140, 145695566450),
    ('2026-01-29', 105700, 110600, 105600, 108700, 1694731, 183242569420),
    ('2026-01-30', 106600, 107800, 102400, 102600, 1705061, 177272585100),
    ('2026-02-02', 99600, 103700, 98000, 98800, 1111606, 111495021000),
    ('2026-02-03', 100900, 109300, 100900, 108600, 1502300, 159215964400),
    ('2026-02-04', 115200, 115400, 106600, 113000, 2061897, 231007631700),
    ('2026-02-05', 109500, 119000, 107800, 110000, 2272728, 256184499650),
    ('2026-02-06', 105500, 107200, 102300, 106600, 1070332, 112817077600),
    ('2026-02-09', 110600, 119300, 109500, 114200, 2217238, 254972103650),
    ('2026-02-10', 115000, 116100, 111300, 112000, 976442, 110650261821),
    ('2026-02-11', 114100, 116500, 110600, 114600, 1361153, 155699143574),
    ('2026-02-12', 114700, 115400, 111200, 115400, 1565751, 178635826500),
    ('2026-02-13', 113200, 121400, 113200, 114300, 1530762, 178269084950),
    ('2026-02-19', 116100, 127700, 115500, 124300, 2167996, 265035105250),
    ('2026-02-20', 124500, 132100, 122500, 128300, 1508112, 193469997950),
    ('2026-02-23', 132000, 143000, 130100, 135400, 1769867, 241326134500),
    ('2026-02-24', 136300, 140500, 133100, 138500, 1596458, 218944289550),
    ('2026-02-25', 140500, 159800, 139400, 155200, 2922470, 446878836600),
    ('2026-02-26', 160200, 163400, 155200, 162000, 1872361, 300073340200),
    ('2026-02-27', 165000, 176900, 160300, 164700, 9658729, 1592270672400),
    ('2026-03-03', 162900, 166000, 147400, 150500, 2187209, 339084517550),
    ('2026-03-04', 139800, 147700, 122700, 126900, 2405244, 321983361650),
    ('2026-03-05', 145000, 148500, 136400, 144000, 1583053, 226112379150),
    ('2026-03-06', 140400, 157800, 139400, 156800, 1801129, 267331364850),
    ('2026-03-09', 147400, 147700, 139800, 146400, 1584152, 227400984600),
    ('2026-03-10', 155500, 160400, 149000, 152000, 1212368, 187265191100),
    ('2026-03-11', 157900, 158000, 146400, 148800, 1032454, 157871780250),
    ('2026-03-12', 147200, 161900, 147200, 155700, 1490261, 232402159700),
    ('2026-03-13', 152800, 169000, 151800, 164400, 2710670, 443708101300),
    ('2026-03-16', 166400, 166400, 157500, 159600, 1051718, 170302236582),
    ('2026-03-17', 163400, 168500, 160400, 161000, 716382, 117479166700),
    ('2026-03-18', 163700, 173600, 162800, 170100, 1475128, 248894829350),
    ('2026-03-19', 167300, 174400, 166700, 169500, 1053700, 180170996200),
    ('2026-03-20', 173200, 174900, 164000, 164000, 1805813, 305162535050),
    ('2026-03-23', 165600, 165600, 153600, 154100, 1314307, 205441693900),
    ('2026-03-24', 161100, 161600, 143300, 149900, 1703908, 254399464100),
    ('2026-03-25', 153600, 161900, 150700, 157900, 994207, 156324089100),
    ('2026-03-26', 158000, 160300, 150100, 152400, 664660, 102332704750),
    ('2026-03-27', 147400, 150600, 142600, 149800, 1149192, 168140687850),
    ('2026-03-30', 140800, 149200, 139600, 148400, 855222, 124618013750),
    ('2026-03-31', 148500, 148500, 141300, 142100, 977221, 140652068500),
    ('2026-04-01', 152300, 161800, 152100, 159900, 1304104, 204819733300),
    ('2026-04-02', 165400, 165400, 146000, 148800, 1646258, 252114744000),
    ('2026-04-03', 153900, 155500, 147800, 151100, 840917, 127548253400),
    ('2026-04-06', 151100, 156900, 150100, 151900, 672484, 102822289750),
    ('2026-04-07', 155400, 166300, 153200, 155900, 1276012, 202428728550),
    ('2026-04-08', 165200, 198400, 164900, 188700, 5892562, 1084373267700),
    ('2026-04-09', 182500, 185800, 177200, 183400, 1607503, 291282439350),
    ('2026-04-10', 191000, 191100, 179100, 179500, 1650776, 301008832600),
    ('2026-04-13', 172000, 177400, 170200, 176000, 1047344, 184743699050),
    ('2026-04-14', 180400, 180500, 173900, 176700, 1110504, 196564172900),
    ('2026-04-15', 180700, 186500, 177300, 179100, 1824686, 332011551350),
    ('2026-04-16', 181600, 181900, 176000, 179500, 880334, 157372385800),
    ('2026-04-17', 179600, 179800, 176500, 177000, 669693, 118771733950),
    ('2026-04-20', 171800, 178100, 170300, 174300, 2193984, 386461280844),
    ('2026-04-21', 176600, 179500, 173800, 174900, 1390912, 244781781100),
    ('2026-04-22', 173000, 173200, 166800, 168800, 1864120, 318455611250),
    ('2026-04-23', 173200, 178300, 171100, 175400, 1925314, 336853505150),
    ('2026-04-24', 174500, 174500, 170400, 173000, 837252, 144368237250),
    ('2026-04-27', 173600, 173700, 169500, 171400, 727618, 124758001500),
    ('2026-04-28', 171600, 179300, 165800, 167100, 2075193, 360144732250),
    ('2026-04-29', 169500, 169600, 164100, 168600, 831334, 138977919600),
    ('2026-04-30', 167600, 168800, 160900, 161800, 1239416, 201019091350),
    ('2026-05-04', 163100, 163200, 157600, 159400, 1088761, 172806140100),
    ('2026-05-06', 161000, 165800, 159100, 163700, 1313559, 214809552500),
    ('2026-05-07', 172100, 175500, 165100, 167400, 1504678, 253941104600),
    ('2026-05-08', 165000, 165000, 159800, 164000, 881257, 142823474700),
    ('2026-05-11', 162000, 170900, 161500, 165800, 1086998, 180889903300),
    ('2026-05-12', 164400, 164500, 150300, 156000, 1224048, 192180533400),
    ('2026-05-13', 154500, 163500, 150200, 160700, 982899, 155394043958),
    ('2026-05-14', 160900, 170300, 160800, 169300, 1696756, 283833526650),
    ('2026-05-15', 167500, 167500, 151700, 155000, 1149196, 181678684900),
    ('2026-05-18', 143800, 149700, 136200, 144900, 1238386, 176645759700),
    ('2026-05-19', 142900, 147300, 136800, 139300, 942475, 131948341700),
    ('2026-05-20', 137000, 139000, 130000, 136200, 1092585, 146588802500),
    ('2026-05-21', 143500, 148500, 139100, 147100, 967862, 140025966700),
    ('2026-05-22', 154300, 154600, 147900, 150300, 611239, 91857142350),
    ('2026-05-26', 157100, 160700, 149100, 152000, 725637, 111419684100),
    ('2026-05-27', 151000, 151100, 143200, 143600, 776042, 113312577750),
    ('2026-05-28', 144000, 146800, 135800, 141400, 648547, 91005632500),
    ('2026-05-29', 143400, 147000, 138000, 147000, 1376563, 197881442450),
    ('2026-06-01', 142500, 144100, 138300, 138900, 1175049, 165063714300),
    ('2026-06-02', 135900, 137000, 129500, 134200, 909449, 119968268600),
    ('2026-06-04', 132000, 139100, 131400, 136600, 722094, 97826400900),
    ('2026-06-05', 135300, 136600, 126600, 131900, 528781, 68873044300),
    ('2026-06-08', 116000, 121000, 115100, 116500, 834619, 98116036850),
    ('2026-06-09', 117500, 123900, 115900, 122300, 633184, 76146464250),
    ('2026-06-10', 119800, 133000, 118400, 130300, 1145106, 147196726050),
    ('2026-06-11', 125200, 126300, 118500, 122700, 974982, 118739587600),
    ('2026-06-12', 138500, 157500, 128500, 157500, 1157067, 159781180900),
    ('2026-06-15', 157600, 157700, 141900, 145000, 1817675, 265147698200),
    ('2026-06-16', 146000, 155500, 140600, 147800, 1894314, 282811869050),
    ('2026-06-17', 150500, 150500, 138900, 139300, 931255, 131551305100),
    ('2026-06-18', 142700, 145000, 133100, 133200, 896771, 121763336200),
    ('2026-06-19', 133700, 135600, 125000, 128600, 1054343, 136133346750),
    ('2026-06-22', 126100, 132100, 124900, 127800, 856076, 110337567550),
    ('2026-06-23', 127800, 128900, 114500, 115100, 963337, 115093347600),
    ('2026-06-24', 113900, 119000, 112600, 114700, 918853, 105865921050),
    ('2026-06-25', 115400, 117400, 111400, 112600, 735354, 83727141900),
    ('2026-06-26', 110600, 112500, 100000, 103300, 1109667, 115608486050),
    ('2026-06-29', 102400, 117000, 101200, 116100, 980428, 110159121500),
    ('2026-06-30', 115900, 119000, 112500, 114200, 512443, 59061200400),
    ('2026-07-01', 118200, 122700, 114300, 119000, 540386, 64297358250),
    ('2026-07-02', 118500, 119400, 111700, 115200, 446151, 51731160100),
    ('2026-07-03', 115000, 115800, 107500, 115300, 471289, 52849018750),
    ('2026-07-06', 116400, 120200, 111600, 115000, 456578, 52580358800),
    ('2026-07-07', 112500, 113400, 105400, 109500, 553518, 60184142750),
    ('2026-07-08', 105000, 106900, 98200, 100700, 858870, 87673744150),
    ('2026-07-09', 99500, 102500, 96400, 98900, 818799, 81345747300),
    ('2026-07-10', 100200, 110000, 99600, 107200, 546029, 58616573150),
    ('2026-07-13', 105600, 109200, 99500, 101500, 436521, 45079529350),
    ('2026-07-14', 99600, 101500, 94200, 98000, 579021, 56628931300),
    ('2026-07-15', 100900, 104000, 100000, 101400, 440956, 44784720550),
    ('2026-07-16', 99400, 100600, 95900, 99000, 380664, 37415865800),
    ('2026-07-20', 94700, 95800, 90100, 91000, 590535, 54452722900),
    ('2026-07-21', 90000, 95800, 88800, 93800, 376027, 34858269350),
    ('2026-07-22', 96500, 102700, 96000, 98600, 536179, 53520770650),
    ('2026-07-23', 98600, 110000, 97600, 108900, 538299, 56773597600),
    ('2026-07-24', 107000, 111150, 105500, 106200, 531116, 57324566200),
    ('2026-07-27', 108100, 108700, 101400, 103600, 236933, 24702688800),
    ('2026-07-28', 99200, 99700, 92600, 94300, 331845, 31542639700),
    ('2026-07-29', 94800, 96300, 77700, 84600, 812537, 68989174150),
    ('2026-07-30', 80300, 88800, 80300, 81700, 563735, 47391570200),
    ('2026-07-31', 85500, 94600, 85500, 94600, 1391976, 127540232100),
    ('2026-08-03', 94500, 97300, 89000, 95600, 477597, 44837828550),
    ('2026-08-04', 97300, 101900, 94300, 101500, 622625, 61453827450),
    ('2026-08-05', 104600, 110600, 102400, 110100, 732453, 79645289050),
    ('2026-08-06', 112900, 115800, 109200, 112600, 643555, 72497198050),
    ('2026-08-07', 110300, 111900, 105200, 109900, 440302, 47450803350),
    ('2026-08-10', 110400, 110800, 105800, 110600, 324857, 35442480400),
    ('2026-08-11', 112000, 117500, 110100, 112300, 608973, 69055475150),
    ('2026-08-12', 114800, 117500, 112200, 113800, 391227, 44573669450),
    ('2026-08-13', 115900, 117200, 111800, 113700, 458053, 52161390650),
    ('2026-08-14', 118900, 121700, 112400, 115800, 493320, 57012417650),
    ('2026-08-18', 116200, 117400, 109000, 110100, 429694, 48096731250),
    ('2026-08-19', 105200, 118700, 103500, 116500, 848390, 97322577650),
    ('2026-08-20', 115200, 116600, 112600, 113800, 482327, 55348891500),
    ('2026-08-21', 112600, 113000, 105000, 105600, 640873, 68296618550),
    ('2026-08-24', 105700, 105900, 103300, 105600, 226607, 23722044500),
    ('2026-08-25', 108800, 122600, 106200, 121300, 2051210, 240024385950),
    ('2026-08-26', 126900, 132600, 122700, 130400, 2203826, 285125010400),
    ('2026-08-27', 129200, 135900, 128100, 129300, 978040, 128253062750),
    ('2026-08-28', 129000, 130300, 124300, 128900, 560482, 71382271050),
    ('2026-08-31', 126000, 126000, 120400, 123300, 675675, 82937410150),
    ('2026-09-01', 122100, 124000, 118000, 120700, 475204, 56869952950),
    ('2026-09-02', 115600, 116700, 112300, 112600, 703058, 79985873650),
    ('2026-09-03', 115000, 123200, 110700, 119500, 929172, 109539562900),
    ('2026-09-04', 119300, 120200, 116800, 119700, 433776, 51580561200),
    ('2026-09-07', 119400, 128700, 117600, 126900, 812263, 101108385100),
    ('2026-09-08', 129500, 137100, 127900, 131400, 1684608, 225034286900),
    ('2026-09-09', 134300, 142000, 131600, 133600, 873138, 119138361400),
    ('2026-09-10', 129100, 132900, 127100, 131200, 662837, 86151132050),
    ('2026-09-11', 129600, 136400, 128400, 134900, 725882, 97162932700),
    ('2026-09-14', 133000, 133100, 126200, 128200, 608828, 78291481450),
    ('2026-09-15', 126100, 128800, 124500, 128100, 418746, 53265237050),
    ('2026-09-16', 127400, 127500, 123500, 124300, 463631, 57754453250),
    ('2026-09-17', 125300, 129200, 124600, 125300, 428542, 54294086350),
    ('2026-09-18', 127000, 129300, 123300, 124800, 819090, 102973813600),
    ('2026-09-21', 126700, 128100, 123500, 125600, 387162, 48692654700),
    ('2026-09-22', 130600, 136100, 125700, 131300, 1023754, 134330315300),
    ('2026-09-23', 130000, 130000, 120200, 121100, 1201523, 147407345200),
    ('2026-09-28', 121900, 126800, 118900, 124600, 663034, 82544596050),
    ('2026-09-29', 122900, 123700, 115500, 117000, 619980, 72891315400),
    ('2026-09-30', 118300, 120200, 117000, 117500, 308341, 36443942800),
    ('2026-10-01', 122100, 123500, 113800, 117200, 541904, 63426556400),
    ('2026-10-02', 116100, 116200, 113000, 114400, 705754, 80658566250),
    ('2026-10-06', 115100, 116600, 112600, 112900, 578555, 65727277550),
    ('2026-10-07', 114600, 114700, 110600, 110900, 445459, 49879942200),
    ('2026-10-08', 108800, 109800, 103950, 107800, 1046277, 111139676850),
    ('2026-10-12', 104000, 104500, 99800, 100200, 809875, 81906657116),
    ('2026-10-13', 96800, 98800, 93100, 98200, 867562, 83630828200),
    ('2026-10-14', 97900, 101600, 97100, 98800, 676092, 67411175250),
    ('2026-10-15', 93200, 94900, 89200, 91100, 605718, 55529538400),
    ('2026-10-16', 91900, 96400, 91900, 93800, 462672, 43792215550),
    ('2026-10-19', 92100, 95000, 89000, 94900, 491427, 45485776800),
    ('2026-10-20', 94300, 95200, 90200, 91500, 388691, 35614638800),
    ('2026-10-21', 93000, 94600, 91100, 92500, 380239, 35244065750),
    ('2026-10-22', 92600, 96900, 92100, 93000, 524278, 49441535000),
    ('2026-10-23', 90200, 92500, 88200, 92500, 532106, 48375017950),
    ('2026-10-26', 90000, 93200, 89100, 90700, 434777, 39358489500),
    ('2026-10-27', 91500, 93900, 90800, 91700, 415721, 38342007000),
    ('2026-10-28', 92900, 97100, 92800, 95500, 486076, 46360858100),
    ('2026-10-29', 94800, 95400, 85000, 91400, 1404017, 123754743700),
    ('2026-10-30', 89300, 89400, 81600, 83600, 678504, 57426461250),
    ('2026-11-02', 81000, 90500, 80300, 89700, 575396, 50879935250),
    ('2026-11-03', 88000, 90500, 84800, 88000, 463695, 40638638900),
    ('2026-11-04', 89100, 91600, 84500, 87700, 593092, 51774538000),
    ('2026-11-05', 89100, 90000, 82500, 83300, 555711, 47222502135),
    ('2026-11-06', 75500, 80800, 73100, 78100, 864014, 66805911750),
    ('2026-11-09', 76400, 78700, 74800, 75200, 636751, 48647494800),
    ('2026-11-10', 78200, 84400, 78200, 84200, 619252, 50857206400),
    ('2026-11-11', 82900, 85000, 82400, 84700, 325062, 27344909850),
    ('2026-11-12', 84300, 85500, 82500, 83600, 441626, 37015120500),
    ('2026-11-13', 83600, 87400, 83300, 84300, 341498, 29083917900),
)
OBSERVED_000720_DAILY_SHA256 = 'eedced5821cf1807b80e4feab49021c4ee6c986f5e1819a0632cf5797c641c6b'


def representative_daily(case):
    """Authored synthetic stress cases; calendar days are NOT an exchange calendar."""
    from src.agents.technical.domain.models.ohlcv import OHLCV
    bars=[]
    for i,seed in enumerate(st.DAILY):
        if case in ('rising','low_liquidity'):close=100+.2*i+(1 if i%2 else -1)
        elif case=='falling':close=200-i
        else:close=100
        if case=='crash' and i==len(st.DAILY)-1:close=60
        opened=100 if case=='crash' and i==len(st.DAILY)-1 else close+.25 if case=='falling' else close-.25 if case in ('rising','low_liquidity') else close
        bars.append(OHLCV(date=seed.date,open=opened,high=max(opened,close)+.25,
                          low=min(opened,close),close=close,volume=1 if case=='low_liquidity' else 1000000,
                          trading_value=100 if case=='low_liquidity' else 2000000000))
    return bars


# Oracle authored from the input construction and published rule order/weights,
# before running the product. A crash is NOT a new enum or a return forecast.
REPRESENTATIVE_EXPECTED = {
    'rising':('uptrend_intact',('positive','positive','positive','negative','positive'),.6),
    'falling':('downtrend',('negative','neutral','negative','positive','negative'),-.4),
    'sideways':('sideways',('neutral','neutral','neutral','neutral','neutral'),0),
    'crash':('downtrend',('negative','neutral','negative','positive','negative'),-.4),
    'low_liquidity':('uptrend_intact',('positive','positive','positive','negative','positive'),.6),
}


def representative_facts(daily):
    from src.agents.technical.application.orchestration import pipeline_steps as steps
    rr=st.run_regime_classify(daily,st.WEEKLY,st.MONTHLY)
    bundle=st.run_indicator_calculate(daily);score=st.run_signal_aggregate(daily)
    conf=st.run_confidence_calculate(score,bundle,rr);risks=st.run_risk_detect(score,bundle,rr)
    return SimpleNamespace(regime=steps._to_regime_result(rr),signal=steps._to_signal_summary(score,conf),rows=score.technical_signals,risks=risks,bundle=bundle)


@pytest.mark.parametrize('case',list(REPRESENTATIVE_EXPECTED))
async def test_representative_synthetic_cases_actual_graph_independent_oracle_and_repeatability(case):
    from src.agents.technical.application.nodes import interpret_report as node
    daily=representative_daily(case);before=copy.deepcopy(daily);facts=representative_facts(daily)
    regime,directions,expected_score=REPRESENTATIVE_EXPECTED[case]
    assert facts.regime.daily_regime.value==regime
    assert tuple(s.signal.value for s in facts.rows)==directions
    assert facts.signal.signal_score==pytest.approx(expected_score)
    assert facts.bundle.ma_short==pytest.approx(sum(x.close for x in daily[-config.MA_SHORT_WINDOW:])/config.MA_SHORT_WINDOW)
    assert facts.bundle.ma_mid==pytest.approx(sum(x.close for x in daily[-config.MA_MID_WINDOW:])/config.MA_MID_WINDOW)
    if case in ('rising','low_liquidity'):assert 50<facts.bundle.rsi<config.RSI_OVERBOUGHT
    elif case=='sideways':assert facts.bundle.rsi==50
    else:assert facts.bundle.rsi==0
    low='low_liquidity' in [r.flag.value for r in facts.risks]
    assert low is (case=='low_liquidity')
    if case=='crash':
        assert (daily[-1].close/daily[-2].close-1)==pytest.approx(-.4)
        assert facts.bundle.latest_candle['lower_wick']==0 and not facts.bundle.latest_candle['is_bullish']
        assert facts.regime.daily_regime.value!='oversold_rebound_watch'
    outputs=[]
    for _ in range(2):
        class Llm:
            def __init__(self):self.prompts=[]
            def complete(self,prompt):
                self.prompts.append(prompt)
                if len(self.prompts)==1:return st.NORM_OK
                if len(self.prompts)==2:return st.FOCUS_OK
                payload=json.loads(prompt.rsplit('```json\n',1)[1].split('\n```',1)[0])
                assert payload['validated_output_example'] is not None
                return json.dumps(payload['validated_output_example'],ensure_ascii=False)
        llm=Llm();seen=[]
        def fetcher(ticker,*,end_date=None):
            seen.append(end_date);return dict(D=daily,W=st.WEEKLY,M=st.MONTHLY)
        bridge=TechnicalEngineBridge(sync_runner=run_technical_agent,llm_client=llm,fetcher=fetcher,cache=None,trace_sink=None,enabled=True)
        req=request();result=await runtime.BoundaryRuntime(bridge).run(req);contract.validate_response(result,req)
        actual=result['data']['result'];outputs.append(actual)
        assert seen==[datetime.fromisoformat(req['data']['requested_as_of']).date()]
        assert actual['regime']==facts.regime.model_dump(mode='json') and actual['signal']==facts.signal.model_dump(mode='json')
        assert tuple(x['signal'] for x in actual['technical_signals'])==directions
        assert [x['value'] for x in actual['technical_signals']]==[s.value for s in facts.rows]
        assert [x['metrics'] for x in actual['technical_signals']]==[s.metrics for s in facts.rows]
        assert actual['technical_signals'][-1]['value']==abs(daily[-1].close-daily[-1].open)
        assert not any(a['kind']=='cup_handle_candidate' for chart in actual['charts'] for a in chart['chart_data']['annotations'])
        assert actual['verification']['outcome']=='passed' and actual['verification']['regen_count']==0
        assert actual['interpretation']['source']=='llm' and all(x['detail_source']=='llm' for x in actual['technical_signals'])
        assert len(llm.prompts)==3 and result['data']['coverage']['cutoff_validation']=='unverified'
        assert actual['as_of']==req['data']['requested_as_of']
        assert runtime._ACTIVE_TASK is None and not ATTEMPTS
    assert outputs[0]==outputs[1] and daily==before
    # Independent negative oracle: correct label does not excuse a measurement
    # claim, an opposite label, or trading instructions. No threshold relaxation.
    payload=node.build_payload(regime=facts.regime,signal=facts.signal,signals=facts.rows,risks=facts.risks)
    for text in ('현재 가격 50원입니다.','매수하세요.','강한 부정' if directions[0]=='positive' else '강한 긍정'):
        bad=copy.deepcopy(payload['validated_output_example']);bad['details'][0]['detail']+=' '+text
        assert not node.verify(bad,regime=facts.regime,signal=facts.signal,signals=facts.rows,risks=facts.risks).passed


@pytest.mark.parametrize('case',list(REPRESENTATIVE_EXPECTED))
def test_representative_indicator_prefixes_do_not_change_when_later_bars_are_appended(case):
    from src.agents.technical.domain.indicators.moving_average import calculate_moving_averages
    from src.agents.technical.domain.indicators.rsi import calculate_rsi
    from src.agents.technical.domain.indicators.pattern import calculate_candle_features
    daily=representative_daily(case)
    mas=calculate_moving_averages(daily);rsi=calculate_rsi(daily);candles=calculate_candle_features(daily)
    for n in (65,80,100,len(daily)):
        subset=daily[:n];part=calculate_moving_averages(subset)
        assert all(part[w]==values[:n] for w,values in mas.items())
        assert calculate_rsi(subset)==rsi[:n] and calculate_candle_features(subset)==candles[:n]
    # This is causality of pure calculations, NOT proof that a fetcher cuts data
    # or that a historical W/M aggregate was finalized at its date label.


@pytest.mark.parametrize('period',['D','W','M'])
def test_standard_KIS_range_discards_after_cutoff_dates_in_all_periods(monkeypatch,period):
    from datetime import date
    from src.agents.technical.infrastructure import kis_client as kis
    seen=[]
    def chart(settings,token,ticker,kind,lo,hi,client,**kwargs):
        seen.append((kind,lo,hi));return {'output2':[kis_bar(d) for d in ('20250331','20250324','20250317')]}
    monkeypatch.setattr(kis,'_call_chart',chart)
    bars=kis._fetch_ohlcv_range('000720',period,date(2025,3,17),date(2025,3,24),None,
        settings=config.KISSettings('fake-key','fake-secret','https://kis.invalid'),_token='fake-token')
    assert [x.date for x in bars]==['2025-03-17','2025-03-24'] and len(seen)==1
    # W/M row values can still be an in-progress aggregate. Dates alone cannot
    # establish publication time, session-close finality, or point-in-time truth.


def test_observed_market_projection_provenance_and_limited_daily_replay():
    from src.agents.technical.domain.models.ohlcv import OHLCV
    from src.agents.technical.domain.indicators.moving_average import calculate_moving_averages
    from src.agents.technical.domain.indicators.rsi import calculate_rsi
    assert hashlib.sha256(json.dumps(OBSERVED_000720_DAILY,separators=(',',':')).encode()).hexdigest()==OBSERVED_000720_DAILY_SHA256
    bars=[OHLCV(**dict(zip(('date','open','high','low','close','volume','trading_value'),row))) for row in OBSERVED_000720_DAILY]
    assert len(bars)==245 and (bars[0].date,bars[-1].date)==('2025-11-13','2026-11-13')
    assert len({x.date for x in bars})==len(bars) and bars==sorted(bars,key=lambda x:x.date)
    bundle=st.run_indicator_calculate(bars)
    assert bundle.close==bars[-1].close and bundle.ma_long==pytest.approx(sum(x.close for x in bars[-config.MA_LONG_WINDOW:])/config.MA_LONG_WINDOW)
    assert st.run_regime_classify(bars,[],[]).daily_regime.value=='downtrend'
    full=calculate_rsi(bars);mas=calculate_moving_averages(bars)
    for n in (65,120,200,245):
        assert calculate_rsi(bars[:n])==full[:n]
        assert all(calculate_moving_averages(bars[:n])[w]==v[:n] for w,v in mas.items())
    # No invented M history, exchange calendar, future return labels, or claim
    # that chart-visible bars reproduce the complete original engine input.


@pytest.mark.parametrize('vol_delta,value_delta,expected',[(0,0,False),(-1,0,True),(0,-1,True),(1,1,False)])
def test_representative_liquidity_boundary_is_OR_and_strictly_below(vol_delta,value_delta,expected):
    bars=[b.model_copy(update={'volume':config.MIN_AVG_VOLUME+vol_delta,
                              'trading_value':config.MIN_AVG_TRADING_VALUE+value_delta}) for b in representative_daily('rising')]
    facts=representative_facts(bars)
    assert facts.bundle.avg_volume==config.MIN_AVG_VOLUME+vol_delta
    assert facts.bundle.avg_trading_value==config.MIN_AVG_TRADING_VALUE+value_delta
    assert ('low_liquidity' in [r.flag.value for r in facts.risks]) is expected


@pytest.mark.parametrize('case',list(REPRESENTATIVE_EXPECTED))
def test_representative_pattern_anchor_does_not_read_appended_future_bar(case):
    from datetime import date
    from src.agents.technical.api.charts import chart_builder as charts
    from src.agents.technical.domain.indicators.volume import calculate_volume_average
    from src.agents.technical.domain.models.ohlcv import OHLCV
    bars=representative_daily(case);end=len(bars)-1
    # None of these authored cases has a rounded bottom AND a recovered rim
    # AND a handle: a crash without recovery is not a cup-and-handle candidate.
    future=OHLCV(date=(date.fromisoformat(bars[-1].date)+timedelta(days=1)).isoformat(),
                  open=1000,high=1000,low=1000,close=1000,volume=9999999,trading_value=9999999999)
    extended=bars+[future]
    assert charts._cup_handle_at(bars,end,lookback=config.CUP_HANDLE_DAILY_LOOKBACK_BARS,
                                 vol_avg=calculate_volume_average(bars)) is None
    assert charts._cup_handle_at(extended,end,lookback=config.CUP_HANDLE_DAILY_LOOKBACK_BARS,
                                 vol_avg=calculate_volume_average(extended)) is None
    assert charts._box_range_at(extended,end)==charts._box_range_at(bars,end)
