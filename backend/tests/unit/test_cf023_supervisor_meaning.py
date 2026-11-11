"""One collection: grounded policy2, exact HTTP/budget seams and legacy digest compatibility."""
import asyncio
import copy
import importlib.abc
import json
import sys
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
import pytest

ATTEMPTS = []
class ImportBoundary(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in {'dotenv','src.api.dependencies','src.supervisor.config','src.agents.flow.config','openai','langchain_openai','redis','langgraph'} or fullname.startswith(('src.agents.technical','src.agents.news','src.agents.fundamental','src.supervisor.application.execution','src.supervisor.application.planning.rewrite','src.supervisor.domain.planning.fallback','src.agents.flow.application.agent')):
            ATTEMPTS.append(fullname)
            raise AssertionError('Forbidden meaning import')
GUARD=ImportBoundary();sys.meta_path.insert(0,GUARD)
from scripts.cf023_supervisor_meaning_check import load_meaning
APP=load_meaning()
M=sys.modules['src.supervisor.domain.meaning']
P=sys.modules['src.supervisor.application.planning.core_planner']
S=sys.modules['src.supervisor.application.meaning_service']
G=sys.modules['src.supervisor.application.meaning_policy']
O=sys.modules['src.supervisor.infrastructure.openai_meaning_gateway']
T=sys.modules['src.supervisor.domain.meaning_proposals']
from src.modules.supervisor.domain import contracts as B
ROOT=Path(__file__).resolve().parents[3]
FIXTURE=json.loads((ROOT/'frontend/tests/fixtures/cf023-supervisor-meaning.json').read_text())
TOKEN='cf023-synthetic-token-no-provider-at-least32'

@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv('FLOW_ANALYSIS_ENABLED','true')
    monkeypatch.setenv('FLOW_SERVICE_TOKEN',TOKEN)


def draft(query='삼성전자 수급', answers=None, **extra):
    return M.Draft(original_query=query, answers=answers or [], revision=len(answers or []), **extra)


def ev(text, value):
    start=text.index(value)
    return dict(source_kind='original_query',answer_id=None,start=start,end=start+len(value),text=value)


def proposal(**extra):
    return dict(schema_version='supervisor.meaning.v1',mentions=[],views=[],conditions=[])|extra


def resolution():
    return sys.modules['src.supervisor.domain.core_contracts'].Resolution(status='resolved',reason='exact_match',stock=dict(stock_code='005930',stock_name='삼성전자',market='KOSPI'),candidates=[])


@pytest.mark.parametrize('case',FIXTURE['cases'])
async def test_sufficiency_remainder_and_grounded_barriers(case):
    gateway=NS(propose=AsyncMock(return_value=proposal()))
    frame,status=await S.understand_v2(draft(case['query']),gateway,attempt_id=str(uuid4()))
    assert frame.original_query==case['query'] and not ATTEMPTS
    assert gateway.propose.await_count==(0 if case['model_zero'] else 1)
    if 'barrier' in case:assert case['barrier'] in frame.unresolved_slots
    if 'exclude' in case:
        assert frame.requested_views==['flow'] and 'flow' not in frame.negated_views
        assert any(c.kind=='exclude' and c.value==case['exclude'] for c in frame.conditions)
    if 'period' in case:assert any(c.value==case['period'] and c.disposition=='unsupported' for c in frame.conditions)


async def test_unknown_mention_can_be_grounded_once_and_continue_fixed_conditions():
    q='현대건설 어제 말고 외국인 말고 기관 수급'
    # The two standalone '말고' occurrences are ambiguous under model-only anchoring.
    # A unique contiguous phrase retains the same explicit embedded negation.
    candidate=proposal(mentions=[dict(evidence=ev(q,'현대건설'),negation=None)],conditions=[dict(domain='flow',kind='cutoff',value='어제',evidence=ev(q,'어제 말고'),negation=None)])
    gateway=NS(propose=AsyncMock(return_value=candidate))
    frame,status=await S.understand_v2(draft(q),gateway,attempt_id=str(uuid4()))
    assert status=='supplemented' and frame.interpretation_source=='model_assisted'
    assert G.validate_fixed_frame(draft(q),frame)==frame
    result=P.continuation_v2(draft(q),frame,resolution())
    assert result.plan.partial and result.plan.required_waivers and result.plan.policy_version=='supervisor.flow-core.2'
    gateway.propose.assert_awaited_once()


@pytest.mark.parametrize('change',['view','actor','unit','negation','domain','missing_text','canonical'])
async def test_candidate_span_does_not_approve_semantic_substitution(change):
    q='현대건설 외국인 말고 3주 수급'
    value=proposal(mentions=[dict(evidence=ev(q,'현대건설'),negation=None)])
    if change=='view':value['views']=[dict(view='flow',evidence=ev(q,'외국인'),negation=ev(q,'말고'))]
    elif change=='actor':value['conditions']=[dict(domain='flow',kind='exclude',value='기관',evidence=ev(q,'외국인'),negation=ev(q,'말고'))]
    elif change=='unit':value['conditions']=[dict(domain='flow',kind='period',value='3개월',evidence=ev(q,'3주'),negation=None)]
    elif change=='negation':value['conditions']=[dict(domain='flow',kind='exclude',value='외국인',evidence=ev(q,'외국인'),negation=None)]
    elif change=='domain':value['conditions']=[dict(domain='technical',kind='period',value='3주',evidence=ev(q,'3주'),negation=None)]
    elif change=='missing_text':value['mentions'][0]['evidence']['text']='없는회사'
    else:value['stock_code']='005930'
    frame,status=await S.understand_v2(draft(q),NS(propose=AsyncMock(return_value=value)),attempt_id=str(uuid4()))
    assert status=='rejected' and frame.interpretation_source=='unavailable' and frame.unresolved_slots


async def test_model_cannot_remove_multi_stock_or_explicit_negation():
    d=draft('삼성전자와 SK하이닉스 수급 내년 목표가')
    frame,_=await S.understand_v2(d,NS(propose=AsyncMock(return_value=proposal(mentions=[dict(evidence=ev(d.original_query,'삼성전자'),negation=None)]))))
    assert 'multi_stock' in frame.unresolved_slots and len(frame.mentions)==2
    d=draft('삼성전자 말고 삼성전자 수급',answers=[dict(answer_id=str(uuid4()),slot='stock',value='삼성전자')])
    assert 'scope' in G.assess(d).frame.unresolved_slots


@pytest.mark.parametrize('failure',[TimeoutError(),httpx.ConnectError('private sentinel')])
async def test_transport_failures_return_conservative_fixed_unavailable(failure):
    frame,status=await S.understand_v2(draft('현대건설 수급'),NS(propose=AsyncMock(side_effect=failure)))
    assert status=='unavailable' and frame.interpretation_source=='unavailable' and frame.unresolved_slots


async def test_cancellation_is_not_a_semantic_failure():
    with pytest.raises(asyncio.CancelledError):
        await S.understand_v2(draft('현대건설 수급'),NS(propose=AsyncMock(side_effect=asyncio.CancelledError())))


async def test_policy_specific_candidate_ref_and_legacy_confirm_digest():
    d=draft();first=await P.start_v2(d)
    plan=P.continuation_v2(d,first.frame,resolution()).plan
    core=sys.modules['src.supervisor.domain.core_contracts']
    assert plan.candidate_ref==core.candidate_ref(d,resolution(),policy_version='supervisor.flow-core.2')
    assert core.candidate_ref(d,resolution())!=plan.candidate_ref
    legacy=dict(client_key=str(uuid4()),draft=d.model_dump(mode='json'),expected_plan_hash='a'*64,consent=dict(allow_flow=True,allow_partial=False,waived_conditions=[]))
    body=B.Confirm.model_validate(legacy)
    assert B.sha(body.model_dump(mode='json',exclude={'preparation_id'}))==B.sha(legacy)


async def test_default_gateway_and_missing_fee_proof_send_zero():
    sends=[]
    gateway=O.OpenAIMeaningGateway(api_key='synthetic',transport=httpx.MockTransport(lambda request:sends.append(request)))
    with pytest.raises(sys.modules['src.supervisor.infrastructure.meaning_gateway'].CounterUnavailable):
        await gateway.propose(draft('현대건설 수급'),attempt_id=str(uuid4()))
    assert sends==[]


class Budget:
    def __init__(self):self.phases=[];self.finishes=[]
    async def authorize(self,*args):self.phases.append(args);return True
    async def finish(self,*args,**kw):self.finishes.append((args,kw))


def agreement():return O.CounterAgreement(O.COUNT_DOCUMENTATION,'a'*64,O.INPUT_FIELDS,1)

def provider(candidate=None,usage=True,model=None):
    return dict(model=model or T.MODEL,service_tier='default',status='completed',error=None,usage=dict(input_tokens=100,output_tokens=10,total_tokens=110,input_tokens_details=dict(cached_tokens=0)) if usage else None,
                output=[dict(type='message',role='assistant',status='completed',content=[dict(type='output_text',text=M.canonical(candidate or proposal()))])])


async def test_exact_count_projection_budget_ACKs_and_generation_usage():
    seen=[];budget=Budget()
    def send(request):
        seen.append(request)
        return httpx.Response(200,json=dict(object='response.input_tokens',input_tokens=100) if request.url.path==O.COUNT_PATH else provider())
    gateway=O.OpenAIMeaningGateway(api_key='synthetic',budget=budget,counter_agreement=agreement(),transport=httpx.MockTransport(send))
    await gateway.propose(draft(),attempt_id=str(uuid4()))
    assert [request.url.path for request in seen]==[O.COUNT_PATH,O.GENERATE_PATH]
    assert all(str(request.url).startswith('https://api.openai.com/v1/responses') for request in seen)
    count,generation=[M.decode(request.content) for request in seen]
    assert count=={field:generation[field] for field in O.INPUT_FIELDS}
    assert not {'max_output_tokens','store','stream','service_tier'}&set(count)
    assert [p[1] for p in budget.phases]==['count','generation']
    assert budget.finishes[-1][0][1]['state']=='observed' and budget.finishes[-1][1]['blocked'] is False


@pytest.mark.parametrize('kind',['missing','model','cap','total','cached'])
async def test_usage_unknown_or_independent_anomaly_holds(kind):
    value=provider();budget=Budget()
    if kind=='missing':value['usage']=None
    elif kind=='model':value['model']='private-model';value['usage']=None
    elif kind=='cap':value['usage']['input_tokens']=16385;value['usage']['total_tokens']=None
    elif kind=='total':value['usage']['total_tokens']=1
    else:value['usage']['input_tokens_details']={}
    gateway=O.OpenAIMeaningGateway(api_key='synthetic',budget=budget,counter_agreement=agreement(),transport=httpx.MockTransport(lambda request:httpx.Response(200,json=dict(object='response.input_tokens',input_tokens=100) if request.url.path==O.COUNT_PATH else value)))
    with pytest.raises(Exception):await gateway.propose(draft(),attempt_id=str(uuid4()))
    assert budget.finishes[-1][1]['blocked'] is True
    assert budget.finishes[-1][0][1]['state']==('anomalous' if kind in {'model','cap'} else 'unknown')


@pytest.mark.parametrize('kind',['refusal','incomplete','duplicate','multiple','tool','overflow'])
async def test_completed_single_candidate_only_and_observed_cost_retained(kind):
    value=provider();budget=Budget()
    if kind=='refusal':value['output'][0]['content']=[dict(type='refusal',refusal='private')]
    elif kind=='incomplete':value['status']='incomplete'
    elif kind=='duplicate':value['output'][0]['content'][0]['text']='{"schema_version":"supervisor.meaning.v1","schema_version":"duplicate"}'
    elif kind=='multiple':value['output']*=2
    elif kind=='tool':value['output'].append(dict(type='function_call'))
    else:value['output'][0]['content'][0]['text']='x'*16385
    gateway=O.OpenAIMeaningGateway(api_key='synthetic',budget=budget,counter_agreement=agreement(),transport=httpx.MockTransport(lambda request:httpx.Response(200,json=dict(object='response.input_tokens',input_tokens=100) if request.url.path==O.COUNT_PATH else value)))
    with pytest.raises(Exception):await gateway.propose(draft(),attempt_id=str(uuid4()))
    assert budget.finishes[-1][0][1]['state']=='observed'


async def test_reservation_ACK_unknown_has_send_zero_and_block_callback():
    budget=Budget();budget.authorize=AsyncMock(side_effect=OSError('private ACK sentinel'));seen=[]
    gateway=O.OpenAIMeaningGateway(api_key='synthetic',budget=budget,counter_agreement=agreement(),transport=httpx.MockTransport(lambda request:seen.append(request)))
    with pytest.raises(OSError):await gateway.propose(draft(),attempt_id=str(uuid4()))
    assert not seen and budget.finishes[-1][1]['blocked']


async def test_stream_cap_stops_before_later_chunks_and_redirect_is_closed():
    seen=[]
    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            seen.append(1);yield b'x'*8193
            seen.append(2);yield b'never'
    gateway=O.OpenAIMeaningGateway(api_key='synthetic',transport=httpx.MockTransport(lambda request:httpx.Response(200,stream=Stream())))
    with pytest.raises(Exception):await gateway._post(O.COUNT_PATH,{},8192)
    assert seen==[1]
    gateway._transport=httpx.MockTransport(lambda request:httpx.Response(302,headers={'location':'https://other.invalid'}))
    with pytest.raises(Exception):await gateway._post(O.COUNT_PATH,{},8192)


def test_spec_identity_and_root_only_schema():
    assert M.sha(T.semantic_spec())==B.MEANING_SPEC_SHA256 and T.semantic_spec()==B.MEANING_SPEC
    from db.models.supervisor.preparation import SupervisorMeaningPreparation,SupervisorMeaningEpoch
    assert SupervisorMeaningPreparation.__tablename__=='supervisor_meaning_preparations'
    assert SupervisorMeaningEpoch.__tablename__=='supervisor_meaning_test_epochs'
    assert not ATTEMPTS


def test_public_contract_baseline_and_negative_projections(monkeypatch):
    sys.meta_path.remove(GUARD)
    try:
        from tests.unit.test_flow_contract import test_relocation_public_contract_baseline,test_cf003_snapshot_projection_rejects_unapproved_changes
        test_relocation_public_contract_baseline(monkeypatch)
        for key in ('path','component'):test_cf003_snapshot_projection_rejects_unapproved_changes(monkeypatch,key)
    finally:sys.meta_path.insert(0,GUARD)


async def test_non_observed_finish_cannot_release_active_hold_even_with_false_flag():
    from src.modules.supervisor.infrastructure.preparation_repository import DurableMeaningBudget
    attempt=str(uuid4())
    epoch=NS(attempts_json={attempt:dict(observation=None)},blocked=False,active_attempt_id=__import__('uuid').UUID(attempt))
    session=NS(scalar=AsyncMock(return_value=epoch),flush=AsyncMock(),commit=AsyncMock())
    class Context:
        async def __aenter__(self):return session
        async def __aexit__(self,*args):return False
    budget=DurableMeaningBudget(lambda:Context(),epoch_id=uuid4(),owner=uuid4())
    for state in ('unknown','anomalous'):
        epoch.attempts_json={attempt:dict(observation=None)};epoch.blocked=False
        await budget.finish(attempt,dict(state=state,reason='FIXED',estimated_nano=None),blocked=False)
        assert epoch.blocked and str(epoch.active_attempt_id)==attempt


async def test_delayed_resolver_cannot_adopt_expired_preparation(monkeypatch):
    from datetime import datetime,timezone,timedelta
    from src.modules.supervisor.application.preparation_service import PreparationService
    from src.modules.supervisor.infrastructure import preparation_repository as repo
    from src.modules.supervisor.infrastructure import repository as bindings
    d=draft();start=await P.start_v2(d);plan=P.continuation_v2(d,start.frame,resolution()).plan
    stamp=datetime(2026,11,9,tzinfo=timezone.utc);expires=stamp+timedelta(seconds=1)
    raw=M.canonical(plan.model_dump(mode='json'))
    row=NS(id=uuid4(),state='ready',redacted_at=None,consumed_binding_id=None,parent_id=None,expires_at=expires,draft_digest=B.sha(d.model_dump(mode='json',exclude={'selected_ticker','candidate_ref'})),draft_json=M.canonical(d.model_dump(mode='json')),frame_json=M.canonical(plan.frame.model_dump(mode='json')),frame_sha256=__import__('hashlib').sha256(M.canonical(plan.frame.model_dump(mode='json')).encode()).hexdigest(),plan_json=raw,plan_sha256=__import__('hashlib').sha256(raw.encode()).hexdigest())
    session=NS();resolver=NS(resolve=AsyncMock(return_value=resolution()))
    service=PreparationService(session,principal=NS(user_id=uuid4()),client=NS(),resolver_factory=lambda session:resolver)
    service.auth=AsyncMock()
    monkeypatch.setattr(repo,'lineage',AsyncMock(return_value=[row]));monkeypatch.setattr(repo,'clock',AsyncMock(side_effect=[stamp,expires+timedelta(seconds=2)]));monkeypatch.setattr(bindings,'by_key',AsyncMock(return_value=None));insert=AsyncMock();monkeypatch.setattr(bindings,'admit',insert)
    body=B.Confirm(client_key=str(uuid4()),preparation_id=str(row.id),draft=B.Draft.model_validate(d.model_dump(mode='json')),expected_plan_hash=plan.plan_hash,consent=B.Consent(allow_flow=True,allow_partial=False,waived_conditions=[]))
    with pytest.raises(repo.PreparationConflict) as error:await service.adopt(body,'a'*64,b'k'*32)
    assert error.value.code=='PREPARATION_EXPIRED';resolver.resolve.assert_awaited_once();insert.assert_not_awaited()


async def test_frozen_UI_fixture_uses_real_planner_and_backend_validator(capsys):
    import base64,zlib
    cases=[]
    for d in (draft(),draft('수급'),draft('수급',answers=[dict(answer_id='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',slot='stock',value='삼성전자')]),draft('삼성전자 주식 정보',answers=[dict(answer_id='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',slot='views',value='수급')]),draft('삼성전자 외국인 수급과 차트'),draft('005930 수급')):
        first=await P.start_v2(d)
        plan=first.plan
        if first.action=='resolve_stock':
            res=resolution()
            if d.original_query=='005930 수급':
                res=res.model_copy(update={'status':'ambiguous','reason':'ambiguous_alias','stock':None,'candidates':[sys.modules['src.supervisor.domain.core_contracts'].Candidate(stock_code=code,stock_name=name,market='KOSPI',match_type='ambiguous_group') for code,name in [('005930','합성 삼성전자'),('000660','합성 하이닉스')]]})
            plan=P.continuation_v2(d,first.frame,res).plan
            if plan.status=='needs_stock_selection':
                selected=d.model_copy(update={'selected_ticker':'005930','candidate_ref':plan.candidate_ref})
                child=P.continuation_v2(selected,first.frame,res).plan
                B.validate_plan(child.model_dump(mode='json'),B.Draft.model_validate(selected.model_dump(mode='json')))
                cases.append(dict(draft=selected.model_dump(mode='json'),plan=child.model_dump(mode='json'),meaning_status='deterministic'))
        B.validate_plan(plan.model_dump(mode='json'),B.Draft.model_validate(d.model_dump(mode='json')))
        cases.append(dict(draft=d.model_dump(mode='json'),plan=plan.model_dump(mode='json'),meaning_status=first.meaning_status))
    with capsys.disabled():print('CF023_UI_FIXTURE '+base64.b64encode(zlib.compress(M.canonical(cases).encode())).decode(),flush=True)


async def test_canonical_alias_cannot_override_excluded_stock():
    from src.modules.supervisor.application.preparation_service import PreparationService
    from src.modules.supervisor.infrastructure.preparation_repository import PreparationConflict
    d=draft('삼성전자 말고 005930 수급')
    frame=G.assess(d).frame
    assert not frame.unresolved_slots
    resolver=NS(resolve=AsyncMock(return_value=resolution()))
    session=NS(commit=AsyncMock())
    service=PreparationService(session,principal=NS(user_id=uuid4()),client=None,resolver_factory=lambda session:resolver)
    service.auth=AsyncMock()
    with pytest.raises(PreparationConflict) as error:await service.resolve(B.Draft.model_validate(d.model_dump(mode='json')),B.MeaningFrame.model_validate(frame.model_dump(mode='json')),'005930')
    assert error.value.code=='INPUT_INVALID' and resolver.resolve.await_count==2
    session.commit.assert_not_awaited()


@pytest.mark.parametrize('name',[
    '현대차 수급 3억원 이상', '현대차 3억원 이상', '현대차 최근 3주',
    '현대차 3주', '현대차 외국인', '현대차보다', '현대차 기아', '가'*257,
])
async def test_overbroad_stock_candidate_cannot_cover_views_amount_period_or_modifiers(name):
    q=name+' 수급'
    candidate=proposal(mentions=[dict(evidence=ev(q,name),negation=None)])
    gateway=NS(propose=AsyncMock(return_value=candidate))
    frame,status=await S.understand_v2(draft(q),gateway,attempt_id=str(uuid4()))
    gateway.propose.assert_awaited_once()
    assert status=='rejected' and 'meaning' in frame.unresolved_slots
    assert any(c.kind=='unrecognized' for c in frame.conditions)
    if '3억원' in q:assert any('3억원' in c.value for c in frame.conditions)


async def test_valid_narrow_name_does_not_cover_adjacent_amount_or_comparison():
    q='현대차 수급 3억원 이상'
    candidate=proposal(mentions=[dict(evidence=ev(q,'현대차'),negation=None)])
    frame,status=await S.understand_v2(draft(q),NS(propose=AsyncMock(return_value=candidate)))
    assert status=='incomplete' and 'meaning' in frame.unresolved_slots
    assert any(c.value=='3억원' for c in frame.conditions)
    assert any(c.value=='이상' for c in frame.conditions)
    assert [m.text for m in frame.mentions]==['현대차']
    assert G.validate_fixed_frame(draft(q),frame)==frame


@pytest.mark.parametrize('name',['현대차','현대 건설','SK 하이닉스','삼성 전자','005930'])
def test_bounded_name_shapes_accept_names_not_whole_question(name):
    assert G.stock_name_shape(name)
    grounding=G.Grounding(draft(name+' 수급'))
    grounding.add_mention(M.Evidence.model_validate(ev(name+' 수급',name)),proposal=True)
    assert grounding.remainder()  # Name coverage itself does not cover the separate view.


@pytest.mark.parametrize('value',['수급만','수급 만','  수급만  '])
async def test_typed_views_only_suffix_finishes_without_gateway_and_reconstructs(value):
    d=draft('삼성전자 주식 정보',answers=[dict(answer_id=str(uuid4()),slot='views',value=value)])
    gateway=NS(propose=AsyncMock(side_effect=AssertionError('Gateway must remain unused')))
    first=await P.start_v2(d,gateway)
    gateway.propose.assert_not_awaited()
    assert first.action=='resolve_stock' and first.frame.requested_views==['flow']
    assert not first.frame.unresolved_slots and first.frame.answers[-1].value==value
    assert G.validate_fixed_frame(d,first.frame)==first.frame
    assert P.continuation_v2(d,first.frame,resolution()).plan.status=='ready'


@pytest.mark.parametrize('query,value',[
    ('삼성전자 수급만',None),
    ('삼성전자 주식 정보','수급만 3억원 이상'),
    ('삼성전자 주식 정보','수급만 최근 3주'),
])
async def test_only_suffix_is_not_global_filler_and_cannot_erase_other_conditions(query,value):
    answers=[] if value is None else [dict(answer_id=str(uuid4()),slot='views',value=value)]
    first=await P.start_v2(draft(query,answers=answers))
    assert first.action!='resolve_stock' and 'meaning' in first.frame.unresolved_slots
    assert any(c.kind=='unrecognized' for c in first.frame.conditions)
    if value and '3억원' in value:assert any('3억원' in c.value for c in first.frame.conditions)
    if value and '3주' in value:assert any('3주' in c.value and c.kind=='period' for c in first.frame.conditions)


async def test_views_only_answer_does_not_restore_explicitly_excluded_flow():
    d=draft('삼성전자 수급 말고 차트',answers=[dict(answer_id=str(uuid4()),slot='views',value='수급만')])
    first=await P.start_v2(d)
    assert first.action!='resolve_stock' and 'flow' in first.frame.negated_views
    assert 'flow' not in first.frame.requested_views
    assert G.validate_fixed_frame(d,first.frame)==first.frame


@pytest.mark.parametrize('query',['현대차 수급','현대차는 수급'])
async def test_typed_stock_links_exact_original_span_without_gateway(query):
    d=draft(query,answers=[dict(answer_id=str(uuid4()),slot='stock',value='현대차')])
    gateway=NS(propose=AsyncMock(side_effect=AssertionError('Gateway must remain unused')))
    first=await P.start_v2(d,gateway)
    gateway.propose.assert_not_awaited()
    assert first.action=='resolve_stock' and not first.frame.unresolved_slots
    assert first.lookup=='현대차'
    assert G.validate_fixed_frame(d,first.frame)==first.frame
    plan=P.continuation_v2(d,first.frame,resolution()).plan
    B.validate_plan(plan.model_dump(mode='json'),B.Draft.model_validate(d.model_dump(mode='json')))


@pytest.mark.parametrize('query',['수현대차 수급','현대차량 수급','현대차이상 수급'])
async def test_typed_stock_never_covers_arbitrary_substring(query):
    d=draft(query,answers=[dict(answer_id=str(uuid4()),slot='stock',value='현대차')])
    first=await P.start_v2(d)
    assert first.action!='resolve_stock' and 'meaning' in first.frame.unresolved_slots
    assert any(c.kind=='unrecognized' and c.evidence[0].source_kind=='original_query' for c in first.frame.conditions)


async def test_typed_stock_keeps_original_negation_period_and_other_stock_evidence():
    for q in ('현대차 말고 기아 수급','현대차말고 기관 수급'):
        d=draft(q,answers=[dict(answer_id=str(uuid4()),slot='stock',value='현대차')])
        first=await P.start_v2(d)
        assert first.action!='resolve_stock' and 'scope' in first.frame.unresolved_slots
        assert any(m.negated and m.text=='현대차' and m.evidence.source_kind=='original_query' for m in first.frame.mentions)
        assert G.validate_fixed_frame(d,first.frame)==first.frame
    d=draft('현대차 최근 3주 수급',answers=[dict(answer_id=str(uuid4()),slot='stock',value='현대차')])
    first=await P.start_v2(d)
    assert first.action=='resolve_stock'
    plan=P.continuation_v2(d,first.frame,resolution()).plan
    assert plan.status=='scope_confirmation' and plan.partial and plan.required_waivers
    assert any(c.kind=='period' and c.value=='최근 3주' for c in plan.frame.conditions)
    d=draft('현대차와 SK하이닉스 수급',answers=[dict(answer_id=str(uuid4()),slot='stock',value='현대차')])
    first=await P.start_v2(d)
    plan=P.continuation_v2(d,first.frame,resolution()).plan
    assert plan.partial and plan.status=='scope_confirmation'
    narrowing=next(c for c in plan.frame.conditions if '다중 종목' in c.value)
    assert {e.text for e in narrowing.evidence}=={'현대차','SK하이닉스'}
    d=draft('현대차와 기아 수급',answers=[dict(answer_id=str(uuid4()),slot='stock',value='현대차')])
    first=await P.start_v2(d)
    assert first.action!='resolve_stock' and any(c.value=='기아' for c in first.frame.conditions)


@pytest.mark.parametrize('query',['현대건설 수급','😀 현대건설 수급','  현대건설  수급'])
@pytest.mark.parametrize('typed',[False,True])
def test_model_alignment_uses_python_text_positions_without_mutating_inputs(query,typed):
    d=draft(query);expected=proposal(mentions=[dict(evidence=ev(query,'현대건설'),negation=None)])
    raw=copy.deepcopy(expected);raw['mentions'][0]['evidence'].update(start=9999,end=1)
    candidate=T.MeaningProposal.model_validate(raw) if typed else raw
    before=copy.deepcopy(candidate);before_draft=d.model_dump(mode='python')
    aligned=G.align_model_proposal(d,candidate)
    assert aligned.model_dump(mode='python')==expected
    assert aligned.mentions[0].evidence.start==query.index('현대건설')
    assert G.assess(d,candidate,source='model_assisted')==G.assess(d,expected,source='model_assisted')
    assert candidate==before and d.model_dump(mode='python')==before_draft
    assert aligned is not candidate


def test_all_proposal_sections_and_negation_keep_exact_meaning_values():
    q='현대건설 외국인 말고 3주 수급';d=draft(q)
    expected=proposal(mentions=[dict(evidence=ev(q,'현대건설'),negation=None)],
        views=[dict(view='flow',evidence=ev(q,'수급'),negation=None)],
        conditions=[dict(domain='flow',kind='exclude',value='외국인',evidence=ev(q,'외국인'),negation=ev(q,'말고')),
                    dict(domain='flow',kind='period',value='3주',evidence=ev(q,'3주'),negation=None)])
    raw=copy.deepcopy(expected)
    for section in ('mentions','views','conditions'):
        for item in raw[section]:
            for name in ('evidence','negation'):
                if item[name] is not None:item[name].update(start=9000,end=1)
    before=copy.deepcopy(raw);aligned=G.align_model_proposal(d,raw)
    assert aligned.model_dump()==expected and raw==before
    frame=G.assess(d,raw,source='model_assisted').frame
    assert frame.requested_views==['flow'] and 'flow' not in frame.negated_views
    assert any(c.kind=='exclude' and c.value=='외국인' for c in frame.conditions)
    assert any(c.kind=='period' and c.value=='3주' for c in frame.conditions)
    assert G.validate_fixed_frame(d,frame)==frame


@pytest.mark.parametrize('patch_value',[
    {'start':True},{'start':'0'},{'start':-1},{'end':0},{'end':'4'},
    {'text':''},{'text':None},{'extra':'forbidden'},
])
def test_alignment_preserves_raw_strict_shape_and_minimum_checks(patch_value):
    q='현대건설 수급';candidate=proposal(mentions=[dict(evidence=ev(q,'현대건설')|patch_value,negation=None)])
    with pytest.raises((M.CoreInvalid,ValueError,TypeError)):G.assess(draft(q),candidate)


@pytest.mark.parametrize('query,text',[
    ('현대건설 수급','현대 건설'),('현대건설 수급','없는회사'),
    ('현대건설 flow','FLOW'),('é 수급','e\u0301'),
    ('현대건설 현대건설 수급','현대건설'),('aaa 수급','aa'),('😀😀😀 수급','😀😀'),
])
def test_missing_nonexact_repeated_and_overlapping_text_never_uses_raw_offset(query,text):
    candidate=proposal(mentions=[dict(evidence=dict(source_kind='original_query',answer_id=None,start=0,end=1,text=text),negation=None)])
    before=copy.deepcopy(candidate)
    with pytest.raises(M.CoreInvalid):G.align_model_proposal(draft(query),candidate)
    assert candidate==before


@pytest.mark.parametrize('source_case',['missing_answer','query_with_answer_id','answer_without_id','other_answer_only','original_only'])
def test_alignment_never_searches_a_different_source_pair(source_case):
    aid,bid=str(uuid4()),str(uuid4())
    d=draft('현대건설 수급',answers=[dict(answer_id=aid,slot='stock',value='한빛건설'),dict(answer_id=bid,slot='stock',value='별빛건설')])
    evidence=dict(source_kind='clarification_answer',answer_id=aid,start=0,end=1,text='한빛건설')
    if source_case=='missing_answer':evidence['answer_id']=str(uuid4())
    elif source_case=='query_with_answer_id':evidence['source_kind']='original_query'
    elif source_case=='answer_without_id':evidence['answer_id']=None
    elif source_case=='other_answer_only':evidence['answer_id']=bid
    else:evidence['text']='현대건설'
    with pytest.raises(M.CoreInvalid):G.assess(d,proposal(mentions=[dict(evidence=evidence,negation=None)]))


def test_clarification_alignment_is_answer_relative_and_preserves_identity():
    aid=str(uuid4());d=draft('종목 수급',answers=[dict(answer_id=aid,slot='stock',value='한빛건설')])
    candidate=proposal(mentions=[dict(evidence=dict(source_kind='clarification_answer',answer_id=aid,start=999,end=1,text='한빛건설'),negation=None)])
    aligned=G.align_model_proposal(d,candidate)
    assert aligned.mentions[0].evidence.model_dump()==dict(source_kind='clarification_answer',answer_id=aid,start=0,end=4,text='한빛건설')
    assert G.assess(d,candidate).frame.answers==d.answers


def test_canonicalization_revalidates_duplicates_created_from_different_offsets():
    q='현대건설 수급';one=dict(evidence=ev(q,'현대건설'),negation=None)
    two=copy.deepcopy(one);two['evidence'].update(start=999,end=1)
    raw=proposal(mentions=[one,two]);assert len(T.MeaningProposal.model_validate(raw).mentions)==2
    with pytest.raises(ValueError):G.align_model_proposal(draft(q),raw)
    assert raw['mentions'][1]['evidence']['start']==999


@pytest.mark.parametrize('domain,kind,value,query',[
    ('flow','period','3주','현대건설 3주 수급'),
    ('flow','period','20거래일','현대건설 20거래일 수급'),
    ('flow','cutoff','지난달','현대건설 지난달 수급'),
    ('fundamental','statement_basis','OFS','현대건설 재무 OFS'),
    ('fundamental','statement_basis','CFS','현대건설 재무 CFS'),
])
def test_alignment_never_changes_period_actor_or_financial_units(domain,kind,value,query):
    candidate=proposal(mentions=[dict(evidence=ev(query,'현대건설'),negation=None)],
        conditions=[dict(domain=domain,kind=kind,value=value,evidence=ev(query,value)|dict(start=999,end=1),negation=None)])
    frame=G.assess(draft(query),candidate).frame
    assert any(c.domain==domain and c.kind==kind and c.value==value for c in frame.conditions)


@pytest.mark.parametrize('ambiguous',[False,True])
def test_alignment_keeps_adjacent_negation_relationship_checks(ambiguous):
    q='현대건설 외국인 말고 기관 '+('말고' if ambiguous else '빼고')+' 수급'
    candidate=proposal(conditions=[dict(domain='flow',kind='exclude',value='외국인',evidence=ev(q,'외국인'),
        negation=ev(q,'말고' if ambiguous else '빼고'))])
    with pytest.raises(M.CoreInvalid):G.assess(draft(q),candidate)


async def test_observed_overview_candidate_still_fails_meaning_after_alignment():
    q='현대건설 외국인 말고 3주 수급'
    candidate=proposal(mentions=[dict(evidence=ev(q,'현대건설'),negation=None)],views=[dict(view='overview',
        evidence=dict(source_kind='original_query',answer_id=None,start=0,end=15,text='현대건설 외국인'),negation=None)])
    aligned=G.align_model_proposal(draft(q),candidate)
    assert aligned.views[0].evidence.end==8 and aligned.views[0].view=='overview'
    with pytest.raises(M.CoreInvalid):G.assess(draft(q),candidate)
    gateway=NS(propose=AsyncMock(return_value=candidate));frame,status=await S.understand_v2(draft(q),gateway)
    assert status=='rejected' and frame.interpretation_source=='unavailable'
    gateway.propose.assert_awaited_once()


async def test_actual_service_uses_alignment_once_and_keeps_fixed_frame_and_policy1_outside_it():
    q='현대건설 외국인 말고 3주 수급';d=draft(q)
    candidate=proposal(mentions=[dict(evidence=ev(q,'현대건설')|dict(start=9999,end=1),negation=None)])
    gateway=NS(propose=AsyncMock(return_value=candidate));frame,status=await S.understand_v2(d,gateway)
    assert status=='supplemented' and frame.requested_views==['flow']
    assert any(c.kind=='exclude' and c.value=='외국인' for c in frame.conditions)
    assert any(c.kind=='period' and c.value=='3주' for c in frame.conditions)
    gateway.propose.assert_awaited_once()
    bad=copy.deepcopy(frame);bad.mentions[0].evidence.end+=1
    with patch.object(G,'align_model_proposal',side_effect=AssertionError('Canonical frame must not be reanchored')):
        assert G.validate_fixed_frame(d,frame)==frame
        with pytest.raises(M.CoreInvalid):G.validate_fixed_frame(d,bad)
        assert G.assess(d).frame.interpretation_source=='deterministic'
        legacy=await S.understand(draft('삼성전자 수급'),NS(extract=AsyncMock(side_effect=AssertionError('No legacy gateway'))))
        assert legacy.interpretation_source=='deterministic'


async def test_invalid_typed_stock_prose_stays_unrecognized_and_fixed_frame_rejects_widening():
    d=draft('현대차 수급 3억원 이상',answers=[dict(answer_id=str(uuid4()),slot='stock',value='현대차 수급 3억원 이상')])
    first=await P.start_v2(d)
    assert first.action!='resolve_stock' and 'meaning' in first.frame.unresolved_slots
    d=draft('현대차 수급',answers=[dict(answer_id=str(uuid4()),slot='stock',value='현대차')])
    frame=(await P.start_v2(d)).frame
    changed=frame.model_dump(mode='json')
    changed['mentions'].append(dict(text=d.original_query,negated=False,evidence=ev(d.original_query,d.original_query)))
    altered=M.MeaningFrame.model_validate(changed)
    with pytest.raises(M.CoreInvalid):G.validate_fixed_frame(d,altered)
