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


def cf043_principal(user=None):
    from datetime import datetime, timezone, timedelta
    from src.modules.auth.application.session_service import Principal
    return Principal(user or uuid4(), uuid4(), datetime.now(timezone.utc) + timedelta(days=1), b'c' * 32)


# CF042: real AccessBoundary + CoreRoute + dependency + PreparationService.post.
# Only auth/session/persistence/AI IO is fake; timers execute against an accelerated clock.
class CF042Clock:
    scale = .01
    def __init__(self):
        self.loop = asyncio.get_running_loop()
        self.anchor = self.loop.time()
        self.absolute, self.relative = [], []
    def time(self):
        return self.anchor + (self.loop.time() - self.anchor) / self.scale
    def __getattr__(self, name):
        return getattr(self.loop, name)
    def install(self, patcher):
        timeout, timeout_at = asyncio.timeout, asyncio.timeout_at
        def absolute(deadline):
            self.absolute.append(deadline)
            return timeout_at(self.anchor + (deadline - self.anchor) * self.scale)
        def relative(seconds):
            self.relative.append(seconds)
            return timeout(seconds * self.scale)
        patcher.setattr(asyncio, 'get_running_loop', lambda: self)
        patcher.setattr(asyncio, 'timeout_at', absolute)
        patcher.setattr(asyncio, 'timeout', relative)


async def cf042_public(monkeypatch, *, work=0, auth_delay=0, auth_error=None, middleware=True):
    from datetime import datetime, timezone
    from fastapi import FastAPI, HTTPException
    from src.modules.supervisor.api import router as R
    from src.modules.auth.api import router as auth_router
    from src.modules.auth.application.session_service import AuthenticationRequired
    from src.modules.supervisor.application.preparation_service import PreparationService
    from src.modules.supervisor.infrastructure import preparation_repository as repo
    from src.shared.http.access_boundary import AccessBoundary
    first = await P.start_v2(draft())
    plan = B.Plan.model_validate(P.continuation_v2(draft(), first.frame, resolution()).plan.model_dump(mode='json'))
    value = B.PreparationRequest(prepare_key=str(uuid4()), draft=B.Draft.model_validate(draft().model_dump(mode='json')))
    h = NS(rows={}, events=[], scopes=[], scope_times=[], deadlines=[], initial_auth=0, admissions=0, ai=0, ai_cancelled=0, closed=0, current_user=uuid4(), clock=CF042Clock(), body=value.model_dump(mode='json'))
    h.plan = plan
    h.session = NS(rollback=AsyncMock(), commit=AsyncMock(), flush=AsyncMock())
    stamp = datetime(2026, 11, 11, tzinfo=timezone.utc)
    async def session():
        try:
            yield h.session
        finally:
            await h.session.rollback()
            h.closed += 1
    async def principal(request, db, *, mutation=False):
        h.initial_auth += 1
        await asyncio.sleep(auth_delay * h.clock.scale)
        if auth_error == 'unauth':
            raise AuthenticationRequired()
        if auth_error in {'csrf', 'owner'}:
            raise HTTPException(403)
        return cf043_principal(h.current_user)
    async def fresh_auth(service):
        h.events.append('fresh_auth')
    async def by_key(db, owner, key):
        return next((r for r in h.rows.values() if r.owner_user_id == owner and r.prepare_key_digest == key), None)
    async def admit(db, values):
        h.admissions += 1
        row = NS(**values, redacted_at=None, consumed_binding_id=None, frame_json=None, frame_sha256=None, plan_json=None, plan_sha256=None)
        h.rows[row.id] = row
        return row
    async def lineage(db, owner, id):
        row = h.rows.get(id)
        if row is None or row.owner_user_id != owner:
            raise repo.PreparationConflict('RESOURCE_NOT_FOUND', 404)
        return [row]
    async def build(service, *args, **kwargs):
        h.ai += 1
        h.events.append('ai_started')
        try:
            await asyncio.sleep(work * h.clock.scale)
        except asyncio.CancelledError:
            h.ai_cancelled += 1
            raise
        h.events.append('ai_returned')
        return plan, 'deterministic'
    original_post = PreparationService.post
    async def post(service, body, request_id, **kwargs):
        h.deadlines.append(kwargs.get('deadline'))
        return await original_post(service, body, request_id, **kwargs)
    monkeypatch.setattr(R.settings, 'FLOW_ANALYSIS_ENABLED', True)
    monkeypatch.setattr(auth_router, 'configured', lambda: True)
    monkeypatch.setattr(R, 'request_principal', principal)
    monkeypatch.setattr(PreparationService, 'auth', fresh_auth)
    monkeypatch.setattr(PreparationService, 'build', build)
    monkeypatch.setattr(PreparationService, 'post', post)
    monkeypatch.setattr(repo, 'by_key', by_key)
    monkeypatch.setattr(repo, 'admit', admit)
    monkeypatch.setattr(repo, 'lineage', lineage)
    monkeypatch.setattr(repo, 'clock', AsyncMock(return_value=stamp))
    monkeypatch.setattr(repo, 'cleanup_owner', AsyncMock())
    h.reserve = AsyncMock(side_effect=AssertionError('No meaning reservation in boundary-only test'))
    h.epoch_create = AsyncMock(side_effect=AssertionError('No epoch creation in boundary-only test'))
    monkeypatch.setattr(repo.DurableMeaningBudget, 'authorize', h.reserve)
    monkeypatch.setattr(repo, 'verifier_epoch', h.epoch_create)
    app = FastAPI()
    app.include_router(R.router)
    app.dependency_overrides[R.get_session] = session
    target = AccessBoundary(app) if middleware else app
    async def capture(scope, receive, send):
        h.scopes.append(scope)
        h.scope_times.append(h.clock.time())
        await target(scope, receive, send)
    h.app = capture
    async def request(*, method='POST', path='/api/supervisor/core/preparations', body_delay=0, raw=None, body=None, state=None):
        async def with_state(scope, receive, send):
            if state is not None:
                scope['state'] = state(h.clock)
            await h.app(scope, receive, send)
        async def stream():
            await asyncio.sleep(body_delay * h.clock.scale)
            yield raw if raw is not None else json.dumps(body if body is not None else h.body).encode()
        with monkeypatch.context() as timers:
            h.clock.install(timers)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=with_state), base_url='http://localhost:8200') as client:
                return await client.request(method, path, content=stream() if method == 'POST' else None,
                    headers={'Content-Type': 'application/json'} if method == 'POST' else {})
    h.request = request
    return h


async def test_cf042_public_preparation_survives_old15_and_replay_get_add_no_AI(monkeypatch):
    h = await cf042_public(monkeypatch, work=30, auth_delay=2)
    response = await h.request(body_delay=2)
    assert response.status_code == 200
    state = h.scopes[0]['state']
    assert state['core_deadline'] == state['core_preparation_started_at'] + 75
    assert state['core_admission_deadline'] == state['core_preparation_started_at'] + 15
    assert h.deadlines == [state['core_deadline']] and h.clock.time() > state['core_admission_deadline']
    assert h.admissions == h.ai == h.closed == 1
    assert h.session.commit.await_count >= 2 and h.session.rollback.await_count >= 2
    assert 'private' in response.headers['cache-control'] and 'no-store' in response.headers['cache-control']
    replay = await h.request()
    read = await h.request(method='GET', path='/api/supervisor/core/preparations/' + response.json()['data']['preparation_id'])
    assert replay.status_code == read.status_code == 200
    assert replay.json()['data'] == read.json()['data'] == response.json()['data']
    assert h.admissions == h.ai == 1 and h.closed == 3
    h.reserve.assert_not_awaited()
    h.epoch_create.assert_not_awaited()
    h.current_user = uuid4()
    foreign = await h.request(method='GET', path='/api/supervisor/core/preparations/' + response.json()['data']['preparation_id'])
    assert foreign.status_code == 404 and h.ai == 1


@pytest.mark.parametrize('body_delay,auth_delay', [(20, 0), (8, 10), (0, 20)])
async def test_cf042_body_and_initial_auth_share_first15(monkeypatch, body_delay, auth_delay):
    h = await cf042_public(monkeypatch, auth_delay=auth_delay)
    response = await h.request(body_delay=body_delay)
    assert response.status_code == 504 and response.json()['error']['code'] == 'DEADLINE_EXCEEDED'
    assert h.ai == h.admissions == 0
    assert h.closed == (0 if body_delay == 20 else 1)
    if h.closed:
        h.session.rollback.assert_awaited()


async def test_cf042_total75_cancels_AI_and_closes_session_without_late_adoption(monkeypatch):
    h = await cf042_public(monkeypatch, work=100)
    response = await h.request()
    assert response.status_code == 504 and response.json()['error']['code'] == 'DEADLINE_EXCEEDED'
    assert h.ai == h.ai_cancelled == h.admissions == h.closed == 1
    assert 'ai_returned' not in h.events and all(row.state != 'ready' for row in h.rows.values())
    h.session.rollback.assert_awaited()
    assert 'no-store' in response.headers['cache-control']


@pytest.mark.parametrize('kind', ['unauth', 'csrf', 'owner'])
async def test_cf042_initial_security_denials_never_admit_or_call_AI(monkeypatch, kind):
    h = await cf042_public(monkeypatch, auth_error=kind)
    response = await h.request()
    assert response.status_code == (401 if kind == 'unauth' else 403)
    assert h.ai == h.admissions == 0 and h.closed == 1


@pytest.mark.parametrize('path', ['/api/supervisor/core/preparations?x=1', '/api/supervisor/core/preparations/', '/api/supervisor/core/preparations/extra'])
async def test_cf042_bad_target_never_admits(monkeypatch, path):
    h = await cf042_public(monkeypatch)
    response = await h.request(path=path)
    assert response.status_code == 422 and h.initial_auth == h.ai == h.admissions == 0


@pytest.mark.parametrize('raw', [b'{', b'x' * 16385])
async def test_cf042_bad_or_oversize_body_never_authenticates(monkeypatch, raw):
    h = await cf042_public(monkeypatch)
    response = await h.request(raw=raw)
    assert response.status_code == 422 and h.initial_auth == h.ai == h.admissions == 0


async def test_cf042_shorter_outer_deadline_is_not_extended(monkeypatch):
    h = await cf042_public(monkeypatch, work=20)
    response = await h.request(state=lambda clock: {'core_deadline': clock.time() + 5})
    assert response.status_code == 504 and h.ai == h.ai_cancelled == 1
    state = h.scopes[0]['state']
    assert h.deadlines == [state['core_deadline']]
    assert state['core_deadline'] - state['core_preparation_started_at'] < 6


async def test_cf042_direct_route_keeps_short_fallback_in_real_service(monkeypatch):
    h = await cf042_public(monkeypatch, work=30, middleware=False)
    response = await h.request()
    assert response.status_code == 504 and h.ai == h.ai_cancelled == h.closed == 1
    assert 'core_preparation_started_at' not in h.scopes[0]['state']
    assert h.deadlines == [h.scopes[0]['state']['core_deadline']]


@pytest.mark.parametrize('value', [0, -1, float('nan'), float('inf'), float('-inf'), True, '75'])
async def test_cf042_service_bad_absolute_deadline_precedes_admission(monkeypatch, value):
    from src.modules.supervisor.application.preparation_service import PreparationService
    from src.modules.supervisor.infrastructure.preparation_repository import PreparationConflict
    session = NS(rollback=AsyncMock())
    service = PreparationService(session, principal=NS(), client=NS())
    service.auth = AsyncMock()
    with pytest.raises(PreparationConflict) as error:
        await service.post(NS(), uuid4(), deadline=value)
    assert error.value.code == 'DEADLINE_EXCEEDED' and error.value.status == 504
    service.auth.assert_not_awaited()
    session.rollback.assert_awaited_once()


async def test_cf042_private_direct_service_preserves_relative75(monkeypatch):
    from src.modules.supervisor.application.preparation_service import PreparationService
    class Stop(RuntimeError): pass
    session = NS(rollback=AsyncMock(side_effect=Stop))
    service = PreparationService(session, principal=cf043_principal(), client=NS())
    body = B.PreparationRequest(prepare_key=str(uuid4()), draft=B.Draft.model_validate(draft().model_dump(mode='json')))
    clock = CF042Clock()
    with monkeypatch.context() as timers:
        clock.install(timers)
        with pytest.raises(Stop):
            await service.post(body, uuid4())
    assert clock.relative == [75] and not clock.absolute


async def test_cf042_direct_absolute_service_still_caps_at75(monkeypatch):
    from src.modules.supervisor.application.preparation_service import PreparationService
    h = await cf042_public(monkeypatch, work=100)
    service = PreparationService(h.session, principal=cf043_principal(h.current_user), client=NS())
    with monkeypatch.context() as timers:
        h.clock.install(timers)
        started = h.clock.time()
        with pytest.raises(TimeoutError):
            await service.post(B.PreparationRequest.model_validate(h.body), uuid4(), deadline=started + 1000)
    assert 75 <= h.clock.absolute[0] - started < 76
    assert h.ai == h.ai_cancelled == 1 and 'ai_returned' not in h.events
    h.session.rollback.assert_awaited()


@pytest.mark.parametrize('kind', ['nonfinite', 'future_start', 'missing_start_expired_admission', 'bad_admission'])
async def test_cf042_invalid_direct_route_context_cannot_grant_longer_time(monkeypatch, kind):
    h = await cf042_public(monkeypatch, middleware=False)
    def state(clock):
        now = clock.time()
        if kind == 'nonfinite': return {'core_deadline': float('inf')}
        if kind == 'missing_start_expired_admission': return {'core_admission_deadline': now - 1}
        return {'core_preparation_started_at': now + 1 if kind == 'future_start' else now,
                'core_deadline': now + 75, 'core_admission_deadline': float('nan') if kind == 'bad_admission' else now + 15}
    response = await h.request(state=state)
    assert response.status_code == 504 and h.initial_auth == h.admissions == h.ai == 0


async def test_cf042_external_cancel_propagates_and_cleans_dependency(monkeypatch):
    h = await cf042_public(monkeypatch, work=100)
    task = asyncio.create_task(h.request())
    for _ in range(100):
        if h.ai: break
        await asyncio.sleep(.001)
    assert h.ai == 1
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert h.ai_cancelled == h.closed == 1 and 'ai_returned' not in h.events
    assert all(row.state != 'ready' for row in h.rows.values())
    h.session.rollback.assert_awaited()


@pytest.mark.parametrize('method,suffix,seconds,body_kind', [
    ('GET', '/preparations/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 15, None),
    ('DELETE', '/preparations/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 15, None),
    ('GET', '/requests/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 15, None),
    ('POST', '/prepare', 15, 'draft'),
    ('POST', '/requests', 140, 'confirm'),
    ('POST', '/preparations/extra', 15, None),
    ('PUT', '/preparations', 15, None),
])
async def test_cf042_other_core_routes_keep_their_original_limits(monkeypatch, method, suffix, seconds, body_kind):
    from src.modules.supervisor.application.service import SupervisorService
    h = await cf042_public(monkeypatch)
    outcome = dict(supervisor_id=str(uuid4()), plan=None, plan_status='deleted', effective_scope=None, flow=None, views=[], coverage='deleted')
    monkeypatch.setattr(SupervisorService, 'prepare', AsyncMock(return_value=h.plan))
    monkeypatch.setattr(SupervisorService, 'post', AsyncMock(return_value=outcome))
    monkeypatch.setattr(SupervisorService, 'get', AsyncMock(return_value=outcome))
    body = h.body['draft'] if body_kind == 'draft' else None
    if body_kind == 'confirm':
        body = dict(client_key=str(uuid4()), draft=h.body['draft'], expected_plan_hash=h.plan.plan_hash,
                    consent=dict(allow_flow=True, allow_partial=False, waived_conditions=[]))
    response = await h.request(method=method, path='/api/supervisor/core' + suffix, body=body)
    state = h.scopes[-1]['state']
    assert abs(state['core_deadline'] - h.scope_times[-1] - seconds) < 1
    assert 'core_admission_deadline' not in state and 'core_preparation_started_at' not in state
    assert h.ai == h.admissions == 0
    assert response.status_code in {200, 404, 422}


def test_cf042_other_access_boundary_branches_are_unchanged_source_only():
    import ast, hashlib
    from src.shared.http.access_boundary import AccessBoundary
    tree = ast.parse(Path(sys.modules[AccessBoundary.__module__].__file__).read_text())
    klass = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'AccessBoundary')
    fn = next(n for n in klass.body if isinstance(n, ast.AsyncFunctionDef) and n.name == '__call__')
    # CF045 adds only these two internal endpoints; keep the old public digest.
    additions=[n for n in fn.body if isinstance(n,ast.If) and isinstance(n.test,ast.Compare) and isinstance(n.test.left,ast.Name) and n.test.left.id=='path' and len(n.test.ops)==1 and isinstance(n.test.ops[0],ast.In) and isinstance(n.test.comparators[0],ast.Set) and {v.value for v in n.test.comparators[0].elts}=={'/internal/supervisor/meaning/authorize','/internal/supervisor/meaning/settle'}]
    assert len(additions)==1
    fn.body = [n for n in fn.body if n is not additions[0] and not (isinstance(n, ast.If) and ast.unparse(n.test) == "path.startswith('/api/supervisor/core')")]
    assert hashlib.sha256(ast.dump(tree, include_attributes=False).encode()).hexdigest() == '51234b692024b6b96a7ec99caa2ff731f5e90dd117da97cefe2c24201b81ca0a'


# CF043: actual post/build/exchange/dispatch guard + actual Principal SQL construction.
# Session/row return values and the AI ASGI transport are explicit synthetic IO.
async def cf043_service(monkeypatch, *, source=None, ambiguous=False):
    from datetime import datetime, timezone
    from src.modules.supervisor.application import preparation_service as PS
    from src.modules.supervisor.infrastructure import preparation_repository as repo
    from src.shared.infrastructure.clients.ai_client import AIClient
    h = NS(rows={}, phases=[], sent=[], events=[], commits=0, rollbacks=0, in_tx=False,
           revoked=False, on_commit=None, on_clock=None, on_send=None, clock_calls=0, validations=[], lineage_calls=[], closed=0,
           db_now=datetime(2026, 11, 11, tzinfo=timezone.utc), epoch=uuid4())
    h.principal = cf043_principal()
    h.body = B.PreparationRequest(prepare_key=str(uuid4()), draft=B.Draft.model_validate((source or draft()).model_dump(mode='json')))
    async def scalar(statement):
        assert statement.get_execution_options()['populate_existing'] is True
        assert statement._for_update_arg is not None and statement._for_update_arg.read is True
        params = statement.compile().params
        assert h.principal.user_id in params.values() and h.principal.session_id in params.values()
        h.validations.append(statement)
        h.in_tx = True
        return None if h.revoked else NS()
    async def commit():
        h.commits += 1
        h.events.append(('commit', h.commits))
        h.in_tx = False
        if h.on_commit is not None:
            await h.on_commit(h.commits)
    async def rollback():
        h.rollbacks += 1
        h.in_tx = False
        h.events.append(('rollback', h.rollbacks))
    session = NS(scalar=scalar, commit=commit, rollback=rollback, flush=AsyncMock())
    h.session = session
    async def by_key(db, owner, key):
        h.in_tx = True
        return next((row for row in h.rows.values() if row.owner_user_id == owner and row.prepare_key_digest == key), None)
    async def clock(db):
        h.clock_calls += 1
        h.in_tx = True
        if h.on_clock is not None:
            return await h.on_clock(h.clock_calls)
        return h.db_now
    async def admit(db, values):
        h.in_tx = True
        row = NS(**{name: values.get(name) for name in PS.DISPATCH_FIELDS})
        h.rows[row.id] = row
        h.events.append(('admit', row.id))
        return row
    async def lineage(db, owner, id, *, lock=True):
        assert lock is True
        h.lineage_calls.append((owner, id, lock))
        h.in_tx = True
        rows = []
        while id is not None:
            row = h.rows.get(id)
            if row is None or row.owner_user_id != owner:
                raise repo.PreparationConflict('RESOURCE_NOT_FOUND', 404)
            rows.append(row)
            id = row.parent_id
        return list(reversed(rows))
    async def resolve(lookup):
        h.events.append(('resolve', lookup))
        if ambiguous:
            return B.Resolution(status='ambiguous', reason='ambiguous_alias', stock=None, candidates=[
                B.Candidate(stock_code=code, stock_name=name, market='KOSPI', match_type='ambiguous_group')
                for code, name in [('005930', '합성 삼성전자'), ('000660', '합성 하이닉스')]])
        return B.Resolution.model_validate(resolution().model_dump(mode='json'))
    real_client = AIClient('http://synthetic.invalid', 8, transport=httpx.ASGITransport(app=APP), service_token=TOKEN)
    async def send(payload):
        assert h.in_tx is False  # Actual guard/resolver commit ACK must precede HTTP.
        phase = payload['data']['phase']
        h.phases.append(phase)
        h.sent.append(copy.deepcopy(payload))
        h.events.append(('send', phase, h.commits))
        if h.on_send is not None:
            await h.on_send(payload)
        return await real_client.plan_supervisor_core(payload)
    monkeypatch.setattr(repo, 'by_key', by_key)
    monkeypatch.setattr(repo, 'admit', admit)
    monkeypatch.setattr(repo, 'lineage', lineage)
    monkeypatch.setattr(repo, 'clock', clock)
    monkeypatch.setattr(repo, 'cleanup_owner', AsyncMock())
    h.reserve = AsyncMock(side_effect=AssertionError('No budget reserve in dispatch guard tests'))
    h.epoch_create = AsyncMock(side_effect=AssertionError('No epoch creation in dispatch guard tests'))
    monkeypatch.setattr(repo.DurableMeaningBudget, 'authorize', h.reserve)
    monkeypatch.setattr(repo, 'verifier_epoch', h.epoch_create)
    h.service = PS.PreparationService(session, principal=h.principal, client=NS(plan_supervisor_core=send),
        resolver_factory=lambda session: NS(resolve=resolve), epoch_id=h.epoch)
    from fastapi import FastAPI
    from src.modules.supervisor.api import router as R
    from src.modules.auth.api import router as auth_router
    from src.shared.http.access_boundary import AccessBoundary
    async def sessions():
        try:
            yield session
        finally:
            await rollback()
            h.closed += 1
    monkeypatch.setattr(R.settings, 'FLOW_ANALYSIS_ENABLED', True)
    monkeypatch.setattr(auth_router, 'configured', lambda: True)
    monkeypatch.setattr(R, 'request_principal', AsyncMock(return_value=h.principal))
    monkeypatch.setattr(R, 'AIClient', lambda *args, **kwargs: h.service.client)
    supervisor_service = R.SupervisorService
    monkeypatch.setattr(R, 'SupervisorService', lambda *args, **kwargs:
        supervisor_service(*args, **kwargs, resolver_factory=h.service.resolver_factory))
    app = FastAPI(); app.include_router(R.router)
    app.dependency_overrides[R.get_session] = sessions
    h.app = AccessBoundary(app)
    return h


async def test_cf043_real_root_guard_order_replay_and_GET(monkeypatch):
    h = await cf043_service(monkeypatch)
    result = await h.service.post(h.body, uuid4())
    assert result['state'] == 'ready' and h.phases == ['start', 'continue']
    assert [event for event in h.events if event[0] == 'send'] == [('send', 'start', 2), ('send', 'continue', 4)]
    assert len(h.validations) >= 5 and all(owner == h.principal.user_id for owner, id, lock in h.lineage_calls)
    replay = await h.service.post(h.body, uuid4())
    observed = await h.service.get(__import__('uuid').UUID(result['preparation_id']))
    assert replay == observed == result and h.phases == ['start', 'continue']
    h.reserve.assert_not_awaited(); h.epoch_create.assert_not_awaited()


@pytest.mark.parametrize('at', [1, 2, 4])
async def test_cf043_uncertain_admit_or_guard_ACK_stops_next_phase(monkeypatch, at):
    h = await cf043_service(monkeypatch)
    async def fail(number):
        if number == at: raise OSError('synthetic ACK unavailable')
    h.on_commit = fail
    with pytest.raises(OSError): await h.service.post(h.body, uuid4())
    assert h.phases == ([] if at < 4 else ['start']) and h.in_tx is False and h.rollbacks >= 2


@pytest.mark.parametrize('stage', [1, 3])
@pytest.mark.parametrize('field', ['revoked', 'owner', 'attempt', 'request', 'draft', 'semantic_json', 'semantic_sha', 'epoch', 'key', 'root', 'depth'])
async def test_cf043_fresh_drift_stops_next_phase(monkeypatch, stage, field):
    from src.modules.supervisor.infrastructure.preparation_repository import PreparationConflict
    from src.modules.auth.application.session_service import AuthenticationRequired
    h = await cf043_service(monkeypatch)
    async def drift(number):
        if number != stage: return
        row = next(iter(h.rows.values()))
        names = {'owner':'owner_user_id', 'attempt':'attempt_id', 'request':'request_digest', 'draft':'draft_digest',
                 'semantic_json':'semantic_json', 'semantic_sha':'semantic_sha256', 'epoch':'epoch_id',
                 'key':'prepare_key_digest', 'root':'root_id', 'depth':'depth'}
        if field == 'revoked': h.revoked = True
        elif field in {'owner', 'attempt', 'epoch', 'root'}: setattr(row, names[field], uuid4())
        elif field == 'key': row.prepare_key_digest = b'x' * 32
        elif field == 'depth': row.depth = 3
        else: setattr(row, names[field], 'x' * 64)
    h.on_commit = drift
    with pytest.raises((PreparationConflict, AuthenticationRequired)):
        await h.service.post(h.body, uuid4())
    assert h.phases == ([] if stage == 1 else ['start'])
    assert h.in_tx is False


@pytest.mark.parametrize('stage', [1, 3])
async def test_cf043_observed_delete_preserves_safe_view_and_no_next_send(monkeypatch, stage):
    h = await cf043_service(monkeypatch)
    async def delete(number):
        if number == stage:
            row = next(iter(h.rows.values()))
            row.state = 'deleted'; row.redacted_at = h.db_now
            row.draft_json = row.frame_json = row.plan_json = row.continuation_json = None
    h.on_commit = delete
    result = await h.service.post(h.body, uuid4())
    assert result['state'] == 'deleted' and result['plan'] is None
    assert h.phases == ([] if stage == 1 else ['start']) and h.in_tx is False


async def test_cf043_late_delete_real_route_returns200_not_new409(monkeypatch):
    from fastapi import FastAPI
    from src.modules.supervisor.api import router as R
    h = await cf043_service(monkeypatch)
    async def during_start(payload):
        if payload['data']['phase'] == 'start':
            row = next(iter(h.rows.values())); row.state = 'deleted'; row.redacted_at = h.db_now
            row.draft_json = row.frame_json = row.plan_json = row.continuation_json = None
    h.on_send = during_start
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=h.app), base_url='http://localhost:8200') as client:
        response = await client.post('/api/supervisor/core/preparations', json=h.body.model_dump(mode='json'))
    assert response.status_code == 200 and response.json()['data']['state'] == 'deleted'
    assert response.json()['data']['plan'] is None and h.phases == ['start'] and h.closed == 1


@pytest.mark.parametrize('delay_at', ['clock', 'commit', 'payload'])
async def test_cf043_TTL_is_anchored_before_clock_and_rechecked_at_send(monkeypatch, delay_at):
    from datetime import timedelta
    from src.modules.supervisor.application import preparation_service as PS
    h = await cf043_service(monkeypatch)
    base = h.db_now
    async def clock(number):
        if number == 1: return base
        if number == 2:
            captured = base + timedelta(seconds=599.99)
            if delay_at == 'clock': await asyncio.sleep(.025)
            return captured
        return base + timedelta(seconds=601)
    h.on_clock = clock
    async def commit(number):
        if delay_at == 'commit' and number == 2: await asyncio.sleep(.025)
    h.on_commit = commit
    original = PS.canonical
    def canonical(value):
        if delay_at == 'payload' and isinstance(value, dict) and value.get('phase') == 'start':
            __import__('time').sleep(.025)
        return original(value)
    monkeypatch.setattr(PS, 'canonical', canonical)
    result = await h.service.post(h.body, uuid4())
    assert result['state'] == 'expired' and result['plan'] is None and h.phases == []


async def test_cf043_absolute_deadline_and_cancel_during_guard_send_zero(monkeypatch):
    h = await cf043_service(monkeypatch)
    async def commit(number):
        if number == 2: await asyncio.sleep(.1)
    h.on_commit = commit
    with pytest.raises(TimeoutError):
        await h.service.post(h.body, uuid4(), deadline=asyncio.get_running_loop().time() + .03)
    assert h.phases == [] and h.in_tx is False and h.rollbacks >= 2


async def test_cf043_first_await_body_and_nested_answer_mutation_cannot_change_wire(monkeypatch):
    source = draft('삼성전자 주식 정보', answers=[dict(answer_id=str(uuid4()), slot='views', value='수급')])
    h = await cf043_service(monkeypatch, source=source)
    original = copy.deepcopy(h.body.model_dump(mode='json'))
    first_rollback = h.session.rollback
    mutated = False
    async def rollback():
        nonlocal mutated
        if not mutated:
            mutated = True
            h.body.draft.original_query = '다른 질문'
            h.body.draft.answers[0].value = '차트'
            h.body.draft.selected_ticker = '000660'
        await first_rollback()
    h.session.rollback = rollback
    result = await h.service.post(h.body, uuid4())
    assert result['state'] == 'ready' and h.phases == ['start', 'continue']
    assert all(payload['data']['draft'] == original['draft'] for payload in h.sent)
    assert next(iter(h.rows.values())).draft_json == M.canonical(original['draft'])


async def test_cf043_valid_child_uses_frozen_ancestors_and_NULL_leaf_source(monkeypatch):
    h = await cf043_service(monkeypatch, source=draft('005930 수급'), ambiguous=True)
    root = await h.service.post(h.body, uuid4())
    assert root['plan']['status'] == 'needs_stock_selection'
    child = B.PreparationRequest(prepare_key=str(uuid4()), parent_preparation_id=root['preparation_id'],
        draft=h.body.draft.model_copy(update={'selected_ticker':'005930', 'candidate_ref':root['plan']['candidate_ref']}))
    result = await h.service.post(child, uuid4())
    assert result['state'] == 'ready' and h.phases == ['start', 'continue', 'continue']
    leaf = h.rows[__import__('uuid').UUID(result['preparation_id'])]
    assert leaf.draft_json is None and leaf.parent_id is not None
    bad = child.model_copy(update={'prepare_key':str(uuid4()), 'draft':child.draft.model_copy(update={'selected_ticker':'999999'})})
    from src.modules.supervisor.infrastructure.preparation_repository import PreparationConflict
    with pytest.raises(PreparationConflict): await h.service.post(bad, uuid4())
    assert h.phases == ['start', 'continue', 'continue']


async def test_cf043_actual_lineage_SQL_retains_owner_freshness_and_lock():
    from src.modules.supervisor.infrastructure import preparation_repository as repo
    owner, root_id, leaf_id = uuid4(), uuid4(), uuid4()
    root = NS(id=root_id, parent_id=None, root_id=root_id, depth=0)
    leaf = NS(id=leaf_id, parent_id=root_id, root_id=root_id, depth=1)
    observed = []
    async def scalar(statement):
        assert statement.get_execution_options()['populate_existing'] is True
        params = statement.compile().params; assert owner in params.values()
        observed.append(statement)
        return leaf if leaf_id in params.values() else root
    async def scalars(statement):
        assert statement.get_execution_options()['populate_existing'] is True
        assert statement._for_update_arg is not None
        assert owner in statement.compile().params.values()
        observed.append(statement)
        return NS(all=lambda:[root, leaf])
    result = await repo.lineage(NS(scalar=scalar, scalars=scalars), owner, leaf_id)
    assert result == [root, leaf] and len(observed) == 3


@pytest.mark.parametrize('stage', [1, 3])
async def test_cf043_post_ACK_DB_TTL_expiry_stops_next_phase(monkeypatch, stage):
    from datetime import timedelta
    h = await cf043_service(monkeypatch)
    async def expire(number):
        if number == stage: h.db_now += timedelta(seconds=601)
    h.on_commit = expire
    result = await h.service.post(h.body, uuid4())
    assert result['state'] == 'expired' and result['plan'] is None
    assert h.phases == ([] if stage == 1 else ['start'])


async def test_cf043_child_ancestor_mutation_after_ACK_cannot_send_continue(monkeypatch):
    from src.modules.supervisor.infrastructure.preparation_repository import PreparationConflict
    h = await cf043_service(monkeypatch, source=draft('005930 수급'), ambiguous=True)
    root = await h.service.post(h.body, uuid4())
    child = B.PreparationRequest(prepare_key=str(uuid4()), parent_preparation_id=root['preparation_id'],
        draft=h.body.draft.model_copy(update={'selected_ticker':'005930', 'candidate_ref':root['plan']['candidate_ref']}))
    target = h.commits + 1
    async def corrupt(number):
        if number == target:
            h.rows[__import__('uuid').UUID(root['preparation_id'])].frame_json = '{}'
    h.on_commit = corrupt
    with pytest.raises(PreparationConflict): await h.service.post(child, uuid4())
    assert h.phases == ['start', 'continue']
    assert [row for row in h.rows.values() if row.parent_id is not None][0].draft_json is None


async def test_cf043_public_cancel_during_guard_keeps_zero_send_and_session_cleanup(monkeypatch):
    h = await cf043_service(monkeypatch)
    reached, release = asyncio.Event(), asyncio.Event()
    async def hold(number):
        if number == 2:
            reached.set()
            await release.wait()
    h.on_commit = hold
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=h.app), base_url='http://localhost:8200') as client:
        task = asyncio.create_task(client.post('/api/supervisor/core/preparations', json=h.body.model_dump(mode='json')))
        try:
            await asyncio.wait_for(reached.wait(), 1)
            task.cancel()
            with pytest.raises(asyncio.CancelledError): await task
        finally:
            release.set()
            if not task.done(): task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    assert h.phases == [] and h.in_tx is False and h.closed == 1 and h.rollbacks >= 2


@pytest.mark.parametrize('field', ['semantic', 'epoch'])
async def test_cf043_child_ancestor_must_match_independent_current_spec_and_epoch(monkeypatch, field):
    from src.modules.supervisor.infrastructure.preparation_repository import PreparationConflict
    h = await cf043_service(monkeypatch, source=draft('005930 수급'), ambiguous=True)
    root = await h.service.post(h.body, uuid4())
    row = h.rows[__import__('uuid').UUID(root['preparation_id'])]
    if field == 'semantic':
        row.semantic_json = '{}'; row.semantic_sha256 = B.sha({})
    else:
        row.epoch_id = uuid4()
    child = B.PreparationRequest(prepare_key=str(uuid4()), parent_preparation_id=root['preparation_id'],
        draft=h.body.draft.model_copy(update={'selected_ticker':'005930', 'candidate_ref':root['plan']['candidate_ref']}))
    with pytest.raises(PreparationConflict): await h.service.post(child, uuid4())
    assert h.phases == ['start', 'continue']


# CF044: isolated durable accounting primitives, no provider or new test mode.
from src.modules.supervisor.domain import meaning_accounting as A44
from src.modules.supervisor.application.meaning_accounting_service import MeaningAccountingService as Accounting44
from src.modules.supervisor.infrastructure import meaning_accounting_repository as AR44
from datetime import datetime, UTC, timedelta
from dataclasses import replace

def accounting_policy44():
    return A44.Policy(operation='meaning',scope='{"budget":"synthetic"}',starts_at=datetime(2026,1,1,tzinfo=UTC),ends_at=datetime(2030,1,1,tzinfo=UTC),limit_nano=1000000,attempt_nano=500000,max_attempts=2,semantic_json=A44.canonical(B.MEANING_SPEC),price_json=A44.canonical(B.MEANING_SPEC['price']),model=B.MEANING_SPEC['model'],tier='default',input_cap=16384,output_cap=2048)

@pytest.mark.parametrize('field,value', [('limit_nano',True),('attempt_nano',-1),('max_attempts',1.0),('input_cap',2**63),('scope','{}'),('price_json','{}'),('semantic_json','{ "a":1}'),('model','')])
def test_cf044_policy_is_strict_and_no_defaults(field,value):
    with pytest.raises((A44.AccountingConflict,ValueError)): replace(accounting_policy44(),**{field:value})

def test_cf044_integer_estimate_and_immutable_inputs():
    p=accounting_policy44()
    e=dict(state='observed',model=p.model,tier=p.tier,input=10,cached=2,output=5,total=15,request_sha256='a'*64,projection_sha256='b'*64,binding_sha256='c'*64,semantic_sha256='d'*64,price_sha256='e'*64)
    assert A44.settlement(p,e)==('observed',28650)
    assert A44.settlement(p,{'state':'unknown'})==('unknown',None)
    for k,v in [('input',True),('cached',11),('output',2049),('total',16),('model','other'),('input',2**63),('output',-1)]:
        assert A44.settlement(p,e|{k:v})==('anomalous',None)
    assert e['input']==10
    with pytest.raises(Exception):p.limit_nano=1

async def test_cf044_mutation_commit_ack_cancel_and_rollback():
    for exc in [RuntimeError(),asyncio.CancelledError()]:
        session=NS(commit=AsyncMock(side_effect=exc),rollback=AsyncMock())
        service=Accounting44(session);action=AsyncMock(return_value={'safe':'receipt'})
        with pytest.raises(type(exc)):await service.mutation(action)
        session.rollback.assert_awaited_once()
    session=NS(commit=AsyncMock(),rollback=AsyncMock());service=Accounting44(session)
    assert await service.mutation(AsyncMock(return_value='ok'))=='ok'
    session.commit.assert_awaited_once();session.rollback.assert_not_awaited()

async def test_cf044_readonly_reconcile_never_mutates():
    from contextlib import nullcontext
    owner,account,rid=uuid4(),uuid4(),uuid4()
    binding=A44.Binding(uuid4(),uuid4(),uuid4(),*['a'*64]*5,datetime(2027,1,1,tzinfo=UTC))
    row=NS(id=rid,account_id=account,binding_json=binding.snapshot(),binding_sha256=A44.sha(binding.snapshot()),state='unknown',reserved_nano=500,estimated_nano=None,receipt_sha256='b'*64)
    session=NS(no_autoflush=nullcontext(),scalar=AsyncMock(side_effect=[NS(id=account),row]),commit=AsyncMock(),rollback=AsyncMock())
    assert (await Accounting44(session).reconcile(owner_id=owner,account_id=account,binding=binding))['state']=='unknown'
    for call in session.scalar.call_args_list:
        sql=str(call.args[0]);assert 'FOR UPDATE' not in sql and 'INSERT' not in sql and 'UPDATE ' not in sql
    session.commit.assert_not_awaited();session.rollback.assert_not_awaited()


def test_cf044_model_migration_checks_and_single_head():
    import ast
    from db.models.supervisor.meaning_accounting import ACCOUNT_CHECKS,RESERVATION_CHECKS
    file=ROOT/'backend/db/migrations/versions/20261111_c44001a7e0001_supervisor_accounting.py'
    tree=ast.parse(file.read_text())
    values={n.targets[0].id:ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name)}
    assert values['ACCOUNT_CHECKS']==ACCOUNT_CHECKS and values['RESERVATION_CHECKS']==RESERVATION_CHECKS
    assert values['down_revision']=='c35001a7e0001'
    source=file.read_text();assert source.index('LOCK TABLE')<source.index('SELECT EXISTS')<source.index("op.drop_table")


@pytest.mark.parametrize('field,value',[('model','other'),('tier','other'),('input_cap',1),('output_cap',1)])
def test_cf044_policy_snapshot_must_match_current_contract(field,value):
    with pytest.raises(A44.AccountingConflict):replace(accounting_policy44(),**{field:value})

@pytest.mark.parametrize('invalid',[{'state':'observed','secret':'synthetic-private'}, {'state':'observed','input':-1}, {'state':'observed','input':1.5}, {'state':'observed','input':2**63}])
async def test_cf044_anomalous_is_blocked_without_raw_strings(invalid):
    p=accounting_policy44();binding=A44.Binding(uuid4(),uuid4(),uuid4(),*['a'*64]*3,A44.sha(p.semantic_json),A44.sha(p.price_json),datetime(2027,1,1,tzinfo=UTC))
    row=NS(id=uuid4(),account_id=uuid4(),binding_json=binding.snapshot(),binding_sha256=A44.sha(binding.snapshot()),state='held',reserved_nano=p.attempt_nano,estimated_nano=None,receipt_sha256=None)
    account=NS(id=row.account_id,policy_json=p.snapshot(),policy_sha256=A44.sha(p.snapshot()),scope_json=p.scope,scope_sha256=A44.sha(p.scope),reserved_nano=p.attempt_nano,observed_nano=0,blocked=False,**{k:getattr(p,k) for k in ('operation','starts_at','ends_at','limit_nano','attempt_nano','max_attempts')})
    session=NS(commit=AsyncMock(),rollback=AsyncMock(),flush=AsyncMock())
    with patch.object(AR44,'account',AsyncMock(return_value=account)),patch.object(AR44,'reservation',AsyncMock(return_value=row)):
        result=await Accounting44(session).settle(owner_id=uuid4(),account_id=account.id,reservation_id=row.id,binding_sha256=row.binding_sha256,evidence=invalid)
    assert result['state']=='anomalous' and result['estimated_nano'] is None and account.blocked
    assert account.reserved_nano==p.attempt_nano and account.observed_nano==0
    assert 'synthetic-private' not in row.receipt_json
    assert set(json.loads(row.receipt_json))=={'state','reason','evidence_sha256'}
    session.commit.assert_awaited_once()


def test_cf044_historical_price_snapshot_settles_but_cannot_issue_new_budget(monkeypatch):
    p=accounting_policy44()
    monkeypatch.setattr(B,'MEANING_SPEC',dict(B.MEANING_SPEC,model='future-contract'))
    with pytest.raises(A44.AccountingConflict):p.require_current()
    assert replace(p).snapshot()==p.snapshot()
    e=dict(state='observed',model=p.model,tier=p.tier,input=10,cached=2,output=5,total=15,request_sha256='a'*64,projection_sha256='b'*64,binding_sha256='c'*64,semantic_sha256='d'*64,price_sha256='e'*64)
    assert A44.settlement(p,e)==('observed',28650)


async def test_cf044_commit_cancellation_survives_rollback_failure():
    session=NS(commit=AsyncMock(side_effect=asyncio.CancelledError()),rollback=AsyncMock(side_effect=RuntimeError()))
    with pytest.raises(asyncio.CancelledError):await Accounting44(session).mutation(AsyncMock(return_value='not-acknowledged'))
    session.rollback.assert_awaited_once()


async def test_cf044_new_cancellation_during_rollback_is_not_swallowed():
    session=NS(commit=AsyncMock(side_effect=RuntimeError()),rollback=AsyncMock(side_effect=asyncio.CancelledError()))
    with pytest.raises(asyncio.CancelledError):await Accounting44(session).mutation(AsyncMock(return_value='not-acknowledged'))

# CF045 request-scoped production assembly, entirely synthetic transports.
from src.modules.supervisor.domain import meaning_accounting as A45

def runtime45(*,backend=None,provider_transport=None,supplier=None):
    F=sys.modules['src.supervisor.application.meaning_gateway_factory']
    return F.MeaningRuntime(F.MeaningRuntimeOptions(backend_origin='http://127.0.0.1:8200',service_token='meaning-'+('s'*40),counter_agreement=agreement(),key_supplier=supplier or AsyncMock(return_value='synthetic-only'),backend_transport=backend,provider_transport=provider_transport,allow_loopback=True))

@pytest.mark.parametrize('change',['none','offset','draft','model','schema','instructions','bool','extra'])
def test_cf045_provider_hash_space_is_verified_not_substituted(change):
    d=draft('현대건설 외국인 말고 3주 수급');r=O.rendered_request(d)
    raw=M.canonical(d.model_dump(mode='json'));spec=A45.canonical(B.MEANING_SPEC)
    if change=='draft':r['input'][0]['content'][0]['text']+=' '
    elif change=='model':r['model']='other'
    elif change=='schema':r['text']['format']['schema']={}
    elif change=='instructions':r['instructions']+=' '
    elif change=='bool':r['store']=0
    elif change=='extra':r['metadata']={}
    elif change=='offset':r['max_output_tokens']=True
    if change=='none':
        request,projection=A45.provider_identity(r,raw,spec)
        assert (request,projection)==(M.sha(r),M.sha({k:r[k] for k in O.INPUT_FIELDS}))
        assert request!=B.sha({'preparation':'separate'})
    else:
        with pytest.raises(A45.AccountingConflict):A45.provider_identity(r,raw,spec)

@pytest.mark.parametrize('change',['default','scheme','token','userinfo','query','slash','supplier'])
def test_cf045_runtime_install_is_inert_and_strict(change):
    F=sys.modules['src.supervisor.application.meaning_gateway_factory'];supplier=AsyncMock()
    values=dict(backend_origin='https://backend.example',service_token='s'*40,counter_agreement=agreement(),key_supplier=supplier)
    if change=='scheme':values['backend_origin']='http://backend.example'
    elif change=='token':values['service_token']='short'
    elif change=='userinfo':values['backend_origin']='https://user:secret@backend.example'
    elif change=='query':values['backend_origin']='https://backend.example?x=1'
    elif change=='slash':values['backend_origin']+='/'
    elif change=='supplier':values['key_supplier']=None
    if change=='default':F.MeaningRuntime(F.MeaningRuntimeOptions(**values))
    else:
        with pytest.raises(sys.modules['src.supervisor.infrastructure.meaning_gateway'].CounterUnavailable):F.MeaningRuntime(F.MeaningRuntimeOptions(**values))
    supplier.assert_not_called()

async def test_cf045_actual_core_factory_gateway_client_authorize_settle_mock_http():
    from fastapi import FastAPI,Request
    phases=[];outbound=[];keys=AsyncMock(return_value='synthetic-only');handle=str(uuid4())+'.'+'a'*64
    server=FastAPI()
    @server.post('/internal/supervisor/meaning/{phase}')
    async def phase(phase:str,request:Request):
        value=await request.json();phases.append((phase,value))
        assert request.headers['x-supervisor-meaning-grant']==handle
        if phase=='settle':
            assert value['observation']['state']=='observed' and value['observation']['total_tokens']==110
            return {'settlement':{'state':'observed'}}
        assert A45.provider_identity(value['rendered_request'],M.canonical(d.model_dump(mode='json')),A45.canonical(B.MEANING_SPEC))==(value['request_sha256'],value['projection_sha256']) if value['phase']=='count' else value['evidence']['input_tokens']==100
        receipt=dict(phase=value['phase'],reservation_id=str(uuid4()),binding_sha256='a'*64,request_sha256=value['request_sha256'],projection_sha256=value['projection_sha256'],evidence_sha256='b'*64)
        return dict(newly_authorized=True,remaining_ms=50000,receipt=receipt)
    def send(request):
        outbound.append(request.url.path)
        return httpx.Response(200,json=dict(object='response.input_tokens',input_tokens=100) if request.url.path==O.COUNT_PATH else provider(proposal(mentions=[dict(evidence=ev(d.original_query,'현대건설'),negation=None)])))
    d=draft('현대건설 수급')
    rt=runtime45(backend=httpx.ASGITransport(app=server),provider_transport=httpx.MockTransport(send),supplier=keys)
    app=load_meaning(runtime=rt)
    payload=dict(schema_version=B.VERSION,request_id=str(uuid4()),trace_id=str(uuid4()),data=dict(phase='start',policy_version='supervisor.flow-core.2',draft=d.model_dump(mode='json'),attempt_id=str(uuid4())),error=None)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://ai') as c:
        result=await c.post('/internal/supervisor/core/plan',json=payload,headers={'X-Flow-Service-Token':TOKEN,'X-Supervisor-Meaning-Grant':handle})
    assert result.status_code==200 and result.json()['data']['meaning_status']=='supplemented'
    assert [p[0] for p in phases]==['authorize','authorize','settle'] and outbound==[O.COUNT_PATH,O.GENERATE_PATH]
    keys.assert_awaited_once()

async def test_cf045_deterministic_and_continue_do_not_create_gateway():
    rt=NS(gateway=lambda *a,**kw:(_ for _ in ()).throw(AssertionError('deterministic gateway forbidden')))
    app=load_meaning(runtime=rt)
    d=draft('삼성전자 수급');first=await P.start_v2(d)
    base=dict(schema_version=B.VERSION,request_id=str(uuid4()),trace_id=str(uuid4()),error=None)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://ai') as c:
        for value in (dict(phase='start',draft=d.model_dump(mode='json')),dict(phase='continue',draft=d.model_dump(mode='json'),frame=first.frame.model_dump(mode='json'),resolution=resolution().model_dump(mode='json'))):
            value.update(policy_version='supervisor.flow-core.2',attempt_id=str(uuid4()))
            response=await c.post('/internal/supervisor/core/plan',json=base|{'data':value},headers={'X-Flow-Service-Token':TOKEN})
            assert response.status_code==200

@pytest.mark.parametrize('case',['same','no-owner','extra','noncanonical','counter','fee','tiny'])
def test_cf045_explicit_existing_account_selection_and_worst_case(case):
    from dataclasses import replace,asdict
    owner=uuid4();identity=uuid4();v={str(owner):dict(account_id=str(identity),scope_sha256='a'*64,policy_sha256='b'*64)}
    counter=asdict(agreement());counter['input_fields']=list(counter['input_fields'])
    if case=='no-owner':v={}
    elif case=='extra':v[str(owner)]['other']=1
    elif case=='noncanonical':v[str(owner)]['account_id']=str(identity).upper()
    elif case=='counter':counter['input_fields']=['model']
    elif case=='fee':counter['counting_fee_bound_nano']=True
    policy=A45.RuntimePolicy(True,json.dumps(v),json.dumps(counter))
    if case in {'same','tiny'}:
        account,scope,expected,raw=policy.select(owner)
        assert account==identity
        p=replace(accounting_policy44(),attempt_nano=50000000,limit_nano=100000000)
        if case=='tiny':
            with pytest.raises(A45.AccountingConflict):A45.maximum_reserve(accounting_policy44(),raw)
        else:assert A45.maximum_reserve(p,raw)==23654401
    else:
        with pytest.raises((A45.AccountingConflict,ValueError)):policy.select(owner)

@pytest.mark.parametrize('bad',['token','flow-token','grant','duplicate','origin','cookie','authorization','query','method','unknown','encoding','contenttype'])
async def test_cf045_internal_auth_rejects_before_body_or_database(monkeypatch,bad):
    from fastapi import FastAPI
    from src.modules.supervisor.api import meaning_phase_router as R
    from src.shared.http.access_boundary import AccessBoundary
    monkeypatch.setattr(R.settings,'SUPERVISOR_MEANING_SERVICE_TOKEN','s'*40)
    headers=[(b'host',b'backend'),(b'content-type',b'application/json'),(b'x-supervisor-meaning-service-token',b's'*40),(b'x-supervisor-meaning-grant',(str(uuid4())+'.'+'a'*64).encode())]
    scope={'type':'http','asgi':{'version':'3.0'},'method':'POST','path':'/internal/supervisor/meaning/authorize','query_string':b'','headers':headers}
    if bad=='token':headers[2]=(headers[2][0],b'bad')
    elif bad=='flow-token':headers[2]=(b'x-flow-service-token',b's'*40)
    elif bad=='grant':headers[3]=(headers[3][0],b'malformed')
    elif bad=='duplicate':headers.append(headers[2])
    elif bad in {'origin','cookie','authorization','unknown','encoding'}:headers.append(({'unknown':b'x-other','encoding':b'content-encoding'}.get(bad,bad.encode()),b'value'))
    elif bad=='query':scope['query_string']=b'x=1'
    elif bad=='method':scope['method']='GET'
    elif bad=='contenttype':headers[1]=(b'content-type',b'text/plain')
    touched=[];messages=[]
    async def app(scope,receive,send):touched.append('app')
    async def receive():touched.append('body');raise AssertionError('auth before body')
    await AccessBoundary(app)(scope,receive,lambda msg: capture45(messages,msg))
    assert touched==[] and messages[0]['status']==403

async def capture45(messages,value):messages.append(value)

async def test_cf045_readonly_handle_reconcile_never_flushes_locks_or_commits(monkeypatch):
    from contextlib import nullcontext
    from src.modules.supervisor.application.meaning_accounting_service import MeaningRuntimeService
    from src.modules.supervisor.infrastructure import meaning_accounting_repository as repo
    identity=uuid4();attempt=uuid4();rid=uuid4();owner=uuid4();nonce='a'*64
    row=NS(id=identity,owner_user_id=owner,owner_session_id=uuid4(),preparation_id=uuid4(),attempt_id=attempt,account_id=uuid4(),nonce_sha256=A45.sha(nonce),principal_sha256='a'*64,binding_json='{}',binding_sha256='b'*64,counter_json='{}',counter_sha256='c'*64,policy_sha256='d'*64,scope_sha256='e'*64,deadline_at=None,reservation_id=rid,provider_request_sha256='f'*64,provider_projection_sha256='a'*64,count_receipt='{"phase":"count"}',generation_receipt=None,terminal_sha256=None)
    reserved=NS(id=rid,account_id=row.account_id,binding_sha256='b'*64,state='held',reserved_nano=50000000,estimated_nano=None,receipt_sha256=None)
    session=NS(no_autoflush=nullcontext(),commit=AsyncMock(),flush=AsyncMock(),rollback=AsyncMock(),new=['unrelated-dirty-object'])
    reads=[]
    async def grant(s,identity,*,lock=False):reads.append(lock);return row
    async def reservation(s,who,identity,*,lock=True):reads.append(lock);return reserved
    monkeypatch.setattr(repo,'grant',grant);monkeypatch.setattr(repo,'reservation',reservation)
    value=await MeaningRuntimeService(session).reconcile_phase(str(identity)+'.'+nonce,dict(action='reconcile',phase='count',attempt_id=str(attempt),request_sha256='f'*64,projection_sha256='a'*64))
    assert value['newly_authorized'] is False and value['terminal_ACK'] is False and value['settlement']['state']=='held'
    assert reads and not any(reads) and session.new==['unrelated-dirty-object']
    session.commit.assert_not_called();session.flush.assert_not_called();session.rollback.assert_not_called()

@pytest.mark.parametrize('observation',[{'state':'unknown','reason':'UNOBSERVED','estimated_nano':None,'secret':'do-not-store'},{'state':'unknown','reason':'free-text-secret','estimated_nano':None},{'state':'other','reason':'UNOBSERVED','estimated_nano':None},{'state':'anomalous','reason':'MODEL_MISMATCH','estimated_nano':1}])
async def test_cf045_unknown_observation_closed_shape_precedes_SQL(monkeypatch,observation):
    from src.modules.supervisor.application.meaning_accounting_service import MeaningRuntimeService
    service=MeaningRuntimeService(NS());service.lookup=AsyncMock(side_effect=AssertionError('bad shape before SQL'))
    with pytest.raises(A45.AccountingConflict):await service.finish(str(uuid4())+'.'+'a'*64,dict(attempt_id=str(uuid4()),request_sha256='b'*64,projection_sha256='c'*64,observation=observation,blocked=True))
    service.lookup.assert_not_called()

async def test_cf045_phase_callback_RTT_narrows_from_send_start_not_receipt(monkeypatch):
    C=sys.modules['src.supervisor.infrastructure.backend.meaning_budget_client'];d=draft('현대건설 수급');calls=[]
    request=O.rendered_request(d);rh=M.sha(request);ph=M.sha({k:request[k] for k in O.INPUT_FIELDS})
    async def send(req):
        calls.append(asyncio.get_running_loop().time());await asyncio.sleep(.04)
        return httpx.Response(200,json=dict(newly_authorized=True,remaining_ms=20,receipt=dict(phase='count',reservation_id=str(uuid4()),binding_sha256='a'*64,request_sha256=rh,projection_sha256=ph,evidence_sha256='b'*64)))
    started=asyncio.get_running_loop().time();budget=C.BackendMeaningBudget(origin='https://backend.example',service_token='s'*40,grant=str(uuid4())+'.'+'a'*64,draft=d,agreement=agreement(),transport=httpx.MockTransport(send),deadline=started+60)
    assert await budget.authorize(str(uuid4()),'count',rh,ph,None) is False
    assert budget.deadline<=calls[0]+.02 and len(calls)==1

def test_cf045_main_installer_is_explicit_and_existing_core_route_uses_it_source_only():
    import ast
    source=(ROOT/'ai/src/main.py').read_text();tree=ast.parse(source)
    defaults=[n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='supervisor_meaning_runtime' for t in n.targets)]
    assert len(defaults)==1 and isinstance(defaults[0].value,ast.Constant) and defaults[0].value.value is None
    installer=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='install_supervisor_meaning_runtime')
    assert 'MeaningRuntime(options)' in ast.unparse(installer)
    assert 'make_supervisor_router(runtime=lambda: supervisor_meaning_runtime)' in source
    assert 'app.include_router(supervisor_router)' in source

@pytest.mark.parametrize('account',[1,True,None,[],{},1.5])
async def test_cf045_malformed_paid_mapping_disables_only_paid_boundary(account):
    from src.modules.supervisor.application.meaning_accounting_service import MeaningRuntimeService
    owner=uuid4();mapping=json.dumps({str(owner):dict(account_id=account,scope_sha256='a'*64,policy_sha256='b'*64)})
    service=MeaningRuntimeService(NS(),runtime_policy=A45.RuntimePolicy(True,mapping,'{}'))
    assert await service.issue(NS(user_id=owner),uuid4(),deadline=asyncio.get_running_loop().time()+1) is None

@pytest.mark.parametrize('raw',[b'{"phase":"count","phase":"generation"}',b'{}',b'{"phase":"other"}',b'{"phase":"count","extra":1}',b'x'*98305,b'{"phase":"generation","extra":"'+b'x'*8192+b'"}'])
async def test_cf045_internal_body_closed_before_grant_SQL(monkeypatch,raw):
    from fastapi import FastAPI
    from src.modules.supervisor.api import meaning_phase_router as R
    from src.modules.supervisor.application.meaning_accounting_service import MeaningRuntimeService
    from src.shared.http.access_boundary import AccessBoundary
    app=FastAPI();app.include_router(R.router);sessions=[]
    async def db():sessions.append('open');yield NS()
    app.dependency_overrides[R.get_session]=db
    monkeypatch.setattr(R.settings,'SUPERVISOR_MEANING_SERVICE_TOKEN','s'*40)
    lookup=AsyncMock(side_effect=AssertionError('invalid body before grant SQL'))
    monkeypatch.setattr(MeaningRuntimeService,'lookup',lookup)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=AccessBoundary(app)),base_url='http://backend') as c:
        response=await c.post('/internal/supervisor/meaning/authorize',content=raw,headers={'Content-Type':'application/json','X-Supervisor-Meaning-Service-Token':'s'*40,'X-Supervisor-Meaning-Grant':str(uuid4())+'.'+'a'*64})
    assert response.status_code==403
    lookup.assert_not_called()

@pytest.mark.parametrize('flag',[False,'false','TRUE','yes',1,None,[]])
async def test_cf045_raw_invalid_enable_flag_keeps_paid_config_inert(flag):
    from src.modules.supervisor.application.meaning_accounting_service import MeaningRuntimeService
    policy=A45.RuntimePolicy(flag,'not-json','not-json')
    assert not policy.active()
    assert await MeaningRuntimeService(NS(),runtime_policy=policy).issue(NS(),uuid4(),deadline=asyncio.get_running_loop().time()+1) is None

def test_cf045_bad_paid_enable_configuration_does_not_break_settings_startup():
    from src.shared.config import Settings
    value=Settings(_env_file=None,SUPERVISOR_MEANING_ENABLED='invalid',SUPERVISOR_MEANING_SERVICE_TOKEN='synthetic-hidden-'+('s'*40))
    assert value.SUPERVISOR_MEANING_ENABLED=='invalid'
    assert 'synthetic-hidden-' not in repr(value)
    assert A45.RuntimePolicy('true','{}','{}').active()


def test_cf042_deadline_precision_at_observed_CI_fraction_never_extends_shorter_bound():
    from starlette.requests import Request
    from src.modules.supervisor.api.router import preparation_deadlines
    started=183.325537915998
    # The previous subtraction is not bit-exact at this real CI baseline.
    assert (started+75)-started != 75
    state=dict(core_preparation_started_at=started,core_deadline=started+75,core_admission_deadline=started+15)
    request=Request(dict(type='http',method='POST',path='/api/supervisor/core/preparations',headers=[],state=state))
    assert preparation_deadlines(request,started+4)==started+75
    assert state['core_admission_deadline']==started+15
    state['core_deadline']=state['core_admission_deadline']=started+10
    assert preparation_deadlines(request,started+4)==started+10
    assert state['core_admission_deadline']==started+10

# Default-off AI lifespan assembly; selected main functions, not full AI startup.
def startup_settings():
    return dict(SUPERVISOR_MEANING_ENABLED='true',
                SUPERVISOR_MEANING_BACKEND_ORIGIN='https://backend.example',
                SUPERVISOR_MEANING_SERVICE_TOKEN='meaning-'+('s'*40),
                SUPERVISOR_MEANING_COUNTER_AGREEMENT=M.canonical(dict(
                    documentation_url=O.COUNT_DOCUMENTATION,documentation_sha256='a'*64,
                    input_fields=list(O.INPUT_FIELDS),counting_fee_bound_nano=1)))


def selected_startup_app():
    import ast
    from contextlib import asynccontextmanager
    from fastapi import FastAPI
    tree=ast.parse((ROOT/'ai/src/main.py').read_text())
    selected=[]
    for node in tree.body:
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name in {'install_supervisor_meaning_runtime','lifespan'}:
            selected.append(node)
        elif isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id in {'supervisor_meaning_runtime','supervisor_router','app'} for t in node.targets):
            selected.append(node)
        elif isinstance(node,ast.Expr) and isinstance(node.value,ast.Call) and ast.unparse(node.value)=='app.include_router(supervisor_router)':
            selected.append(node)
    ns=dict(FastAPI=FastAPI,asynccontextmanager=asynccontextmanager,
            make_supervisor_router=sys.modules['src.supervisor.api.routes'].make_router)
    exec(compile(ast.Module(body=selected,type_ignores=[]),'<selected-ai-lifespan>','exec'),ns)
    assert ns['supervisor_meaning_runtime'] is None
    return ns


@pytest.mark.parametrize('fault',['off','missing_origin','missing_token','missing_counter','flow_only',
                                  'http','bad_port','zero_port','bad_origin_type','token_type','counter_type','counter_large',
                                  'duplicate','unknown','bad_sha','bool_fee','bad_fields','bad_url'])
def test_meaning_startup_invalid_explicit_settings_close_without_key_read(fault):
    F=sys.modules['src.supervisor.application.meaning_gateway_factory'];values=startup_settings();reads=[]
    if fault=='off':values['SUPERVISOR_MEANING_ENABLED']='TRUE'
    elif fault.startswith('missing_'):
        values.pop({'missing_origin':'SUPERVISOR_MEANING_BACKEND_ORIGIN','missing_token':'SUPERVISOR_MEANING_SERVICE_TOKEN','missing_counter':'SUPERVISOR_MEANING_COUNTER_AGREEMENT'}[fault])
    elif fault=='flow_only':values={'FLOW_ANALYSIS_ENABLED':'true','FLOW_SERVICE_TOKEN':'s'*40}
    elif fault=='http':values['SUPERVISOR_MEANING_BACKEND_ORIGIN']='http://127.0.0.1:8200'
    elif fault=='bad_port':values['SUPERVISOR_MEANING_BACKEND_ORIGIN']='https://backend.example:bad'
    elif fault=='zero_port':values['SUPERVISOR_MEANING_BACKEND_ORIGIN']='https://backend.example:0'
    elif fault=='bad_origin_type':values['SUPERVISOR_MEANING_BACKEND_ORIGIN']=[]
    elif fault=='token_type':values['SUPERVISOR_MEANING_SERVICE_TOKEN']=42
    elif fault=='counter_type':values['SUPERVISOR_MEANING_COUNTER_AGREEMENT']=None
    elif fault=='counter_large':values['SUPERVISOR_MEANING_COUNTER_AGREEMENT']='x'*16385
    elif fault=='duplicate':values['SUPERVISOR_MEANING_COUNTER_AGREEMENT']='{"input_fields":[],"input_fields":[]}'
    else:
        counter=json.loads(values['SUPERVISOR_MEANING_COUNTER_AGREEMENT'])
        if fault=='unknown':counter['extra']='synthetic-not-exposed'
        elif fault=='bad_sha':counter['documentation_sha256']=[]
        elif fault=='bool_fee':counter['counting_fee_bound_nano']=False
        elif fault=='bad_fields':counter['input_fields']={}
        elif fault=='bad_url':counter['documentation_url']='https://other.example'
        values['SUPERVISOR_MEANING_COUNTER_AGREEMENT']=M.canonical(counter)
    class Settings(dict):
        def get(self,key,default=None):
            reads.append(key)
            assert key!='OPENAI_API_KEY'
            return super().get(key,default)
    assert F.startup_options(Settings(values)) is None
    assert not any('FLOW_' in k for k in reads)


def test_meaning_startup_module_import_is_inert_and_key_is_deferred(monkeypatch):
    import importlib.util
    F=sys.modules['src.supervisor.application.meaning_gateway_factory']
    with patch('os.getenv',side_effect=AssertionError('import env forbidden')),patch('pathlib.Path.read_text',side_effect=AssertionError('import file forbidden')):
        spec=importlib.util.spec_from_file_location(F.__name__,F.__file__)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    values=startup_settings();reads=[]
    class Settings(dict):
        def get(self,key,default=None):reads.append(key);return super().get(key,default)
    options=F.startup_options(Settings(values));assert options is not None
    F.MeaningRuntime(options)
    assert 'OPENAI_API_KEY' not in reads and not ATTEMPTS
    assert 'service_token' not in repr(options) and 's'*40 not in repr(options)


@pytest.mark.parametrize('configured',[False,True])
async def test_meaning_default_lifespan_preserves_deterministic_continue_and_unavailable(monkeypatch,configured):
    F=sys.modules['src.supervisor.application.meaning_gateway_factory'];settings=startup_settings() if configured else {}
    if configured:settings['SUPERVISOR_MEANING_COUNTER_AGREEMENT']='invalid'
    monkeypatch.setattr(F,'startup_options',lambda _:F_start(settings))
    ns=selected_startup_app();app=ns['app']
    d=draft('삼성전자 수급');first=await P.start_v2(d)
    base=dict(schema_version=B.VERSION,request_id=str(uuid4()),trace_id=str(uuid4()),error=None)
    async with app.router.lifespan_context(app):
        assert ns['supervisor_meaning_runtime'] is None
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='https://ai.example') as c:
            for value in (dict(phase='start',draft=d.model_dump(mode='json')),
                          dict(phase='continue',draft=d.model_dump(mode='json'),frame=first.frame.model_dump(mode='json'),resolution=resolution().model_dump(mode='json')),
                          dict(phase='start',draft=draft('현대건설 수급').model_dump(mode='json'))):
                value.update(policy_version='supervisor.flow-core.2',attempt_id=str(uuid4()))
                result=await c.post('/internal/supervisor/core/plan',json=base|{'data':value},headers={'X-Flow-Service-Token':TOKEN})
                assert result.status_code==200
                if value['draft']['original_query']=='현대건설 수급':assert result.json()['data']['meaning_status']=='unavailable'
    assert ns['supervisor_meaning_runtime'] is None


# Preserve the actual parser when a lifespan test substitutes only its input mapping.
F_start=sys.modules['src.supervisor.application.meaning_gateway_factory'].startup_options


@pytest.mark.parametrize('authorized',[True,False])
async def test_meaning_lifespan_actual_gateway_reads_key_only_after_count_ACK(monkeypatch,authorized):
    from dataclasses import replace
    from fastapi import FastAPI,Request
    F=sys.modules['src.supervisor.application.meaning_gateway_factory'];events=[];server=FastAPI();d=draft('현대건설 수급')
    @server.post('/internal/supervisor/meaning/{phase}')
    async def phase(phase:str,request:Request):
        value=await request.json();events.append('backend-'+phase+(('-'+value['phase']) if phase=='authorize' else ''))
        if phase=='settle':return {'settlement':{'state':'observed' if authorized else 'unknown'}}
        receipt=dict(phase=value['phase'],reservation_id=str(uuid4()),binding_sha256='a'*64,request_sha256=value['request_sha256'],projection_sha256=value['projection_sha256'],evidence_sha256='b'*64)
        return dict(newly_authorized=authorized,remaining_ms=50000,receipt=receipt)
    def provider_send(request):
        events.append(request.url.path)
        return httpx.Response(200,json=dict(object='response.input_tokens',input_tokens=100) if request.url.path==O.COUNT_PATH else provider(proposal(mentions=[dict(evidence=ev(d.original_query,'현대건설'),negation=None)])))
    class Settings(dict):
        def get(self,key,default=None):
            if key=='OPENAI_API_KEY':
                assert events==['backend-authorize-count'];events.append('key-read')
                return 'synthetic-only'
            return super().get(key,default)
    settings=Settings(startup_settings())
    def options(_):
        value=F_start(settings)
        return replace(value,backend_transport=httpx.ASGITransport(app=server),provider_transport=httpx.MockTransport(provider_send))
    monkeypatch.setattr(F,'startup_options',options)
    ns=selected_startup_app();app=ns['app']
    async with app.router.lifespan_context(app):
        installed=ns['supervisor_meaning_runtime'];assert type(installed) is F.MeaningRuntime and not events
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='https://ai.example') as c:
            payload=dict(schema_version=B.VERSION,request_id=str(uuid4()),trace_id=str(uuid4()),data=dict(phase='start',policy_version='supervisor.flow-core.2',draft=d.model_dump(mode='json'),attempt_id=str(uuid4())),error=None)
            headers={'X-Flow-Service-Token':TOKEN,'X-Supervisor-Meaning-Grant':str(uuid4())+'.'+'a'*64}
            result=await c.post('/internal/supervisor/core/plan',json=payload,headers=headers)
        assert result.status_code==200
        assert result.json()['data']['meaning_status']==('supplemented' if authorized else 'counter_unavailable')
    assert ns['supervisor_meaning_runtime'] is None
    assert events==(['backend-authorize-count','key-read',O.COUNT_PATH,'backend-authorize-generation',O.GENERATE_PATH,'backend-settle'] if authorized else ['backend-authorize-count'])
