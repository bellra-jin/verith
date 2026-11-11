"""Fixed CF024 collection: callback simulations, no actual provider/DB or credentials."""
import asyncio
import ast
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
import hashlib
import importlib.abc
from pathlib import Path
import sys
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID,uuid4

import httpx
import pytest

IMPORTS=[]
class ImportGuard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in {'dotenv','src.supervisor.config','src.api.dependencies','openai','langchain_openai','redis','langgraph'} or fullname.startswith(('src.agents.technical','src.agents.news','src.agents.fundamental','src.supervisor.application.execution','src.supervisor.application.planning.rewrite')):
            IMPORTS.append(fullname)
            raise AssertionError('Forbidden assembly import')
GUARD=ImportGuard();sys.meta_path.insert(0,GUARD)
from scripts import cf023_supervisor_meaning_check as C
C.load_meaning()
O=sys.modules['src.supervisor.infrastructure.openai_meaning_gateway']
M=sys.modules['src.supervisor.domain.meaning']
T=sys.modules['src.supervisor.domain.meaning_proposals']
from src.modules.supervisor.domain import contracts as B
from src.modules.auth.application.session_service import Principal,AuthenticationRequired
from src.supervisor.infrastructure.meaning_gateway import CounterUnavailable,MeaningUnavailable
ROOT=Path(__file__).resolve().parents[3]
PRIVATE='cf024-private-sentinel-never-in-result'


def draft():return M.Draft(original_query='현대건설 수급',answers=[],revision=0)
def agreement():return O.CounterAgreement(O.COUNT_DOCUMENTATION,C.SYNTHETIC_MAPPING_SHA,O.INPUT_FIELDS,1)
def body():return B.PreparationRequest(prepare_key=str(uuid4()),draft=B.Draft.model_validate(draft().model_dump(mode='json')),parent_preparation_id=None)
def principal():return Principal(uuid4(),uuid4(),datetime.now(timezone.utc)+timedelta(hours=1),b'x'*32)
def candidate():return {'schema_version':'supervisor.meaning.v1','mentions':[{'evidence':{'source_kind':'original_query','answer_id':None,'start':0,'end':4,'text':'현대건설'},'negation':None}],'views':[],'conditions':[]}
def response(*,usage=True,model=None):return {'model':model or T.MODEL,'status':'completed','service_tier':'default','error':None,'usage':{'input_tokens':100,'output_tokens':10,'total_tokens':110,'input_tokens_details':{'cached_tokens':0}} if usage else None,'output':[{'type':'message','role':'assistant','status':'completed','content':[{'type':'output_text','text':M.canonical(candidate())}]}]}


class Ledger:
    def __init__(self):self.rows={};self.blocked=False;self.active=None;self.reserved=0


class CallbackBudget:
    """Explicit simulation, not a PostgreSQL receipt/role or actual durable ACK."""
    def __init__(self, ledger=None, fail=None):
        self.ledger=ledger or Ledger();self.fail=fail;self.events=[];self.deadline=float('inf')
    async def authorize(self, attempt, phase, request, projection, evidence):
        self.events.append(phase+'_entered')
        if self.fail==phase+'_before':raise OSError(PRIVATE)
        if self.ledger.blocked:return False
        if phase=='count':
            if self.ledger.active is not None or attempt in self.ledger.rows or len(self.ledger.rows)>=2:return False
            self.ledger.rows[attempt]={'count':True,'generation':False,'observation':None};self.ledger.active=attempt;self.ledger.reserved+=50000000
        else:
            row=self.ledger.rows.get(attempt)
            if row is None or row['generation'] or self.ledger.active!=attempt:return False
            assert evidence.request_sha256==request and evidence.projection_sha256==projection
            row['generation']=True
        self.events.append(phase+'_ACK')
        if self.fail==phase+'_after':raise OSError(PRIVATE)
        if self.fail==phase+'_expires':self.deadline=asyncio.get_running_loop().time()-1
        return True
    async def finish(self, attempt, observation, *, blocked):
        self.events.append('finish_entered')
        row=self.ledger.rows.get(attempt)
        if row is not None:
            row['observation']=observation
            self.ledger.blocked|=blocked
            if not self.ledger.blocked:self.ledger.active=None
        if self.fail=='finish_after':raise OSError(PRIVATE)
        self.events.append('finish_ACK')


def gateway(*,budget=None,supplier=None,value=None,send=None,deadline=None,preflight=None):
    budget=budget or CallbackBudget();requests=[]
    async def supply():
        budget.events.append('supplier');return 'synthetic-key'
    async def provider(request):
        requests.append(request)
        budget.events.append('count_send' if request.url.path==O.COUNT_PATH else 'generation_send')
        if send is not None:return await send(request)
        return httpx.Response(200,json={'object':'response.input_tokens','input_tokens':100} if request.url.path==O.COUNT_PATH else value or response())
    instance=O.OpenAIMeaningGateway(key_supplier=supplier or supply,budget=budget,counter_agreement=agreement(),transport=httpx.MockTransport(provider),deadline=deadline,preflight=preflight)
    return instance,budget,requests


async def test_default_live_closed_without_supplier_or_epoch_initialization(monkeypatch):
    from src.modules.supervisor.infrastructure import preparation_repository as repo
    initialize=AsyncMock(side_effect=AssertionError('Live must never initialize'))
    monkeypatch.setattr(repo,'verifier_epoch',initialize)
    supplier=AsyncMock(side_effect=AssertionError('Must not read key'))
    with pytest.raises(CounterUnavailable):await C.verify_live(key_supplier=supplier,counter_agreement=agreement())
    supplier.assert_not_awaited();initialize.assert_not_awaited();assert not IMPORTS


async def test_count_ACK_precedes_one_supplier_and_same_key_generation():
    instance,budget,requests=gateway()
    result=await instance.propose(draft(),attempt_id=str(uuid4()))
    assert result==T.MeaningProposal.model_validate(candidate())
    assert budget.events==['count_entered','count_ACK','supplier','count_send','generation_entered','generation_ACK','generation_send','finish_entered','finish_ACK']
    assert [str(r.url) for r in requests]==[O.ORIGIN+O.COUNT_PATH,O.ORIGIN+O.GENERATE_PATH]
    assert [r.headers['authorization'] for r in requests]==['Bearer synthetic-key']*2
    count,generation=[M.decode(r.content) for r in requests]
    assert count=={k:generation[k] for k in O.INPUT_FIELDS}
    assert not {'max_output_tokens','service_tier','store','stream'}&count.keys()
    assert budget.ledger.reserved==50000000 and len(budget.ledger.rows)==1
    assert instance._key is None and instance._key_supplier is None
    with pytest.raises(CounterUnavailable):await instance.propose(draft(),attempt_id=str(uuid4()))
    assert budget.events.count('supplier')==1


@pytest.mark.parametrize('phase',['count','generation'])
@pytest.mark.parametrize('when',['before','after'])
async def test_reservation_ACK_simulations_hold_without_later_key_or_send(phase,when):
    instance,budget,requests=gateway(budget=CallbackBudget(fail=phase+'_'+when))
    with pytest.raises(OSError) as error:await instance.propose(draft(),attempt_id=str(uuid4()))
    assert PRIVATE not in str(error.value)
    assert budget.events.count('supplier')==(0 if phase=='count' else 1)
    assert len(requests)==(0 if phase=='count' else 1)
    if budget.ledger.rows:assert budget.ledger.blocked and budget.ledger.reserved==50000000
    assert instance._key is None and instance._key_supplier is None


@pytest.mark.parametrize('phase',['count','generation'])
async def test_expiry_shortened_during_reservation_ACK_blocks_send_immediately(phase):
    instance,budget,requests=gateway(budget=CallbackBudget(fail=phase+'_expires'))
    with pytest.raises(TimeoutError):await instance.propose(draft(),attempt_id=str(uuid4()))
    assert len(requests)==(0 if phase=='count' else 1)
    assert budget.events.count('supplier')==(0 if phase=='count' else 1)
    assert instance.settlement_uncertain and not instance.block_confirmed
    assert 'finish_entered' not in budget.events


@pytest.mark.parametrize('bad',[None,'',True,'bad\ncredential','x'*513])
async def test_invalid_supplier_result_holds_and_sends_zero(bad):
    supplier=AsyncMock(return_value=bad)
    instance,budget,requests=gateway(supplier=supplier)
    with pytest.raises(MeaningUnavailable):await instance.propose(draft(),attempt_id=str(uuid4()))
    supplier.assert_awaited_once();assert not requests and budget.ledger.blocked
    assert instance._key is None and instance._key_supplier is None


async def test_supplier_failure_never_exposes_raw_message_or_retries():
    supplier=AsyncMock(side_effect=ValueError(PRIVATE))
    instance,budget,requests=gateway(supplier=supplier)
    with pytest.raises(MeaningUnavailable) as error:await instance.propose(draft(),attempt_id=str(uuid4()))
    assert PRIVATE not in str(error.value) and not requests and budget.ledger.blocked
    supplier.assert_awaited_once()


async def test_missing_or_invalid_count_evidence_has_supplier_zero_send_zero():
    for evidence in (None,O.CounterAgreement(O.COUNT_DOCUMENTATION,'a'*64,(),1),O.CounterAgreement(O.COUNT_DOCUMENTATION,'a'*64,O.INPUT_FIELDS,28496001)):
        supplier=AsyncMock(return_value=PRIVATE);send=AsyncMock()
        instance=O.OpenAIMeaningGateway(key_supplier=supplier,budget=CallbackBudget(),counter_agreement=evidence,transport=httpx.MockTransport(send))
        with pytest.raises(CounterUnavailable):await instance.propose(draft(),attempt_id=str(uuid4()))
        supplier.assert_not_awaited();send.assert_not_awaited()


@pytest.mark.parametrize('kind',['missing_usage','model','malformed','overflow_input','overflow_count','timeout'])
async def test_provider_failures_preserve_unknown_hold_and_bounded_fixed_error(kind):
    async def send(req):
        if req.url.path==O.COUNT_PATH:
            if kind=='overflow_count':return httpx.Response(200,content=b'x'*8193)
            return httpx.Response(200,json={'object':'response.input_tokens','input_tokens':16385 if kind=='overflow_input' else 100})
        if kind=='timeout':raise httpx.ReadTimeout(PRIVATE)
        if kind=='malformed':return httpx.Response(200,content=b'{')
        return httpx.Response(200,json=response(usage=kind!='missing_usage',model='different-model' if kind=='model' else None))
    instance,budget,requests=gateway(send=send)
    with pytest.raises(Exception) as error:await instance.propose(draft(),attempt_id=str(uuid4()))
    assert PRIVATE not in str(error.value) and budget.ledger.blocked and budget.ledger.reserved==50000000
    assert instance._key is None and instance._key_supplier is None
    if kind=='timeout':
        assert isinstance(error.value,TimeoutError)
        assert 'provider_timeout' in [x['stage'] for x in instance.diagnostic()['events']]


async def test_one_simulated_epoch_success_unknown_restart_cannot_reset_two_reservations():
    ledger=Ledger()
    first,_,_=gateway(budget=CallbackBudget(ledger));await first.propose(draft(),attempt_id=str(uuid4()))
    second,_,_=gateway(budget=CallbackBudget(ledger),value=response(usage=False))
    with pytest.raises(MeaningUnavailable):await second.propose(draft(),attempt_id=str(uuid4()))
    restart,budget,requests=gateway(budget=CallbackBudget(ledger))
    with pytest.raises(CounterUnavailable):await restart.propose(draft(),attempt_id=str(uuid4()))
    assert not requests and budget.events.count('supplier')==0
    assert ledger.blocked and ledger.reserved==100000000 and len(ledger.rows)==2


async def test_settlement_ACK_unknown_never_returns_success_candidate():
    instance,budget,_=gateway(budget=CallbackBudget(fail='finish_after'))
    with pytest.raises(OSError):await instance.propose(draft(),attempt_id=str(uuid4()))
    assert instance.settlement_uncertain and budget.ledger.reserved==50000000
    assert budget.events.count('finish_entered')==1


@pytest.mark.parametrize('failure',['ack_loss','db_before','timeout'])
async def test_settlement_attempt_latched_before_failure_and_never_retried(failure):
    budget=CallbackBudget();entered=[];original=budget.finish
    async def finish(*args,**kwargs):
        entered.append('finish')
        if failure=='ack_loss':
            await original(*args,**kwargs)
            raise OSError(PRIVATE)
        if failure=='db_before':raise OSError(PRIVATE)
        await asyncio.Event().wait()
    budget.finish=finish
    instance,_,requests=gateway(budget=budget,deadline=asyncio.get_running_loop().time()+.06)
    with pytest.raises((OSError,TimeoutError)):await instance.propose(draft(),attempt_id=str(uuid4()))
    assert entered==['finish'] and len(requests)==2 and budget.ledger.reserved==50000000
    assert instance.settlement_uncertain and instance._key is None and instance._key_supplier is None
    assert 'settlement_ACK' not in [x['stage'] for x in instance.diagnostic()['events']]


async def test_settlement_wait_uses_original_deadline_no_background_task():
    budget=CallbackBudget();entered=asyncio.Event()
    async def finish(*args,**kw):entered.set();await asyncio.Event().wait()
    budget.finish=finish
    before=asyncio.get_running_loop().time()
    instance,_,_=gateway(budget=budget,deadline=before+.04)
    with pytest.raises(TimeoutError):await instance.propose(draft(),attempt_id=str(uuid4()))
    assert entered.is_set() and asyncio.get_running_loop().time()-before<.3
    assert instance.settlement_uncertain and not instance.block_confirmed


@pytest.mark.parametrize('stage',['supplier','settlement'])
async def test_cancellation_propagates_and_key_references_clear(stage):
    entered=asyncio.Event();budget=CallbackBudget()
    async def blocked(*args,**kw):entered.set();await asyncio.Event().wait()
    supplier=blocked if stage=='supplier' else None
    if stage=='settlement':budget.finish=blocked
    instance,_,_=gateway(budget=budget,supplier=supplier,deadline=asyncio.get_running_loop().time()+.08)
    task=asyncio.create_task(instance.propose(draft(),attempt_id=str(uuid4())))
    await entered.wait();task.cancel()
    with pytest.raises(asyncio.CancelledError):await task
    assert instance._key is None and instance._key_supplier is None


async def test_gateway_whole_deadline_uses_verifier_with_reserved_settlement():
    observed=[]
    async def preflight(*args,deadline,**kwargs):
        observed.append(deadline-asyncio.get_running_loop().time())
        return deadline
    instance,_,requests=gateway(preflight=preflight)
    await instance.propose(draft(),attempt_id=str(uuid4()))
    assert 54<observed[0]<=55 and len(requests)==2
    assert T.CAPS['provider_seconds']==55 and T.CAPS['verifier_seconds']==60
    assert B.MEANING_SPEC==T.semantic_spec()
    old=B.decode(B.canonical(B.MEANING_SPEC));old['caps']['provider_seconds']=5
    assert B.sha(old)!=B.MEANING_SPEC_SHA256 and old['price']==B.MEANING_SPEC['price']
    events=instance.diagnostic()['events']
    assert [x['stage'] for x in events]==['count_dispatch_entered','count_response_received','count_validated',
        'generation_dispatch_entered','generation_response_received','usage_observed','settlement_ACK']
    assert all(set(x)=={'stage','elapsed_ms'} for x in events)
    assert PRIVATE not in M.canonical(instance.diagnostic())
    assert all(0<value<=55 for request in requests for value in request.extensions['timeout'].values())


@pytest.mark.parametrize('constructor',['missing','later','earlier'])
async def test_gateway_clamps_to_earliest_internal_caller_deadline(constructor):
    now=asyncio.get_running_loop().time();caller=now+.08
    configured=None if constructor=='missing' else now+(.04 if constructor=='earlier' else 20)
    earliest=min(caller,configured if configured is not None else caller)
    observed=[]
    async def preflight(*args,deadline,**kwargs):observed.append(deadline);return deadline
    instance,_,requests=gateway(deadline=configured,preflight=preflight)
    await instance.propose(draft(),attempt_id=str(uuid4()),caller_deadline=caller)
    assert observed[0]<earliest and len(requests)==2
    assert all(0<value<.08 for request in requests for value in request.extensions['timeout'].values())


async def test_meaning_outer_absolute_deadline_is_injected_into_real_gateway():
    from src.supervisor.application.meaning_service import understand_v2
    instance,_,_=gateway(deadline=asyncio.get_running_loop().time()+600)
    propose=AsyncMock(return_value=T.MeaningProposal.model_validate(candidate()))
    with patch.object(instance,'propose',propose):await understand_v2(draft(),instance,attempt_id=str(uuid4()))
    received=propose.call_args.kwargs['caller_deadline']
    assert 59<received-asyncio.get_running_loop().time()<=60


async def test_send_timeout_leaves_deadline_for_normal_task_hold_ACK():
    budget=CallbackBudget();finish=budget.finish
    async def checked_finish(*args,**kwargs):
        assert not asyncio.current_task().cancelling()
        await finish(*args,**kwargs)
    budget.finish=checked_finish
    async def provider(request):
        if request.url.path==O.COUNT_PATH:return httpx.Response(200,json={'object':'response.input_tokens','input_tokens':100})
        await asyncio.Event().wait()
    overall=asyncio.get_running_loop().time()+.08
    budget.settlement_deadline=overall  # Explicit verifier-backed tail, not a legacy fallback.
    instance,_,requests=gateway(budget=budget,send=provider,deadline=overall)
    with pytest.raises(TimeoutError):await instance.propose(draft(),attempt_id=str(uuid4()))
    assert len(requests)==2 and budget.ledger.blocked and budget.ledger.reserved==50000000
    assert instance.block_confirmed and not instance.settlement_uncertain
    stages=[x['stage'] for x in instance.diagnostic()['events']]
    assert 'provider_timeout' in stages and stages[-1]=='hold_ACK'
    assert 'generation_response_received' not in stages
    assert all(0<value<.08 for request in requests for value in request.extensions['timeout'].values())


async def test_external_cancellation_never_reenters_settlement_SQL():
    budget=CallbackBudget();entered=asyncio.Event()
    async def provider(request):
        if request.url.path==O.COUNT_PATH:return httpx.Response(200,json={'object':'response.input_tokens','input_tokens':100})
        entered.set();await asyncio.Event().wait()
    instance,_,requests=gateway(budget=budget,send=provider)
    task=asyncio.create_task(instance.propose(draft(),attempt_id=str(uuid4())))
    await entered.wait();task.cancel()
    with pytest.raises(asyncio.CancelledError):await task
    assert 'finish_entered' not in budget.events and budget.ledger.active is not None
    assert len(requests)==2 and budget.ledger.reserved==50000000 and instance.settlement_uncertain
    assert instance.diagnostic()['events'][-1]['stage']=='cancelled'


async def test_policy2_real_ASGI_client_and_meaning_have_nested_bounds():
    from src.shared.infrastructure.clients.ai_client import AIClient
    calls=[];timeouts=[];absolute=[]
    class SlowSyntheticGateway:
        async def propose(self,*args,**kwargs):
            calls.append('propose');await asyncio.sleep(.12)
            return T.MeaningProposal.model_validate(candidate())
    app=C.load_meaning(gateway=SlowSyntheticGateway())
    token='cf024-asgi-synthetic-service-token-at-least32'
    client=AIClient('http://synthetic.invalid',8,transport=httpx.ASGITransport(app=app),service_token=token)
    raw=dict(schema_version='supervisor.core.v1',request_id=str(uuid4()),trace_id=str(uuid4()),
        data=dict(policy_version='supervisor.flow-core.2',phase='start',draft=draft().model_dump(mode='json'),attempt_id=str(uuid4())),error=None)
    original=asyncio.timeout;original_at=asyncio.timeout_at
    def scaled(seconds):
        timeouts.append(seconds)
        return original(seconds*.01)
    def recorded(deadline):
        absolute.append(deadline-asyncio.get_running_loop().time())
        return original_at(deadline)
    with patch.dict(__import__('os').environ,{'FLOW_ANALYSIS_ENABLED':'true','FLOW_SERVICE_TOKEN':token}),patch.object(asyncio,'timeout',scaled),patch.object(asyncio,'timeout_at',recorded):
        result=await client.plan_supervisor_core(raw)
    assert result['error'] is None and calls==['propose']
    assert timeouts[0]==70
    assert any(14<seconds<=15 for seconds in absolute) and any(64<seconds<=65 for seconds in absolute)
    assert any(59<seconds<=60 for seconds in absolute)


async def test_preparation_real_post_ASGI_survives_old_15_second_scaled_boundary():
    """Actual post/build/exchange/ASGI/meaning, with only persistence/resolver mocked."""
    from src.modules.supervisor.application.preparation_service import PreparationService
    from src.modules.supervisor.infrastructure import preparation_repository as repo
    from src.shared.infrastructure.clients.ai_client import AIClient
    session=NS(rollback=AsyncMock(),commit=AsyncMock(),flush=AsyncMock(),scalar=AsyncMock(return_value=NS()))
    principal_value=principal();request=body();now=datetime.now(timezone.utc);rows=[];calls=[]
    class SlowSyntheticGateway:
        async def propose(self,*args,**kwargs):
            calls.append('propose');await asyncio.sleep(.2)
            return T.MeaningProposal.model_validate(candidate())
    app=C.load_meaning(gateway=SlowSyntheticGateway());token='cf024-asgi-synthetic-service-token-at-least32'
    client=AIClient('http://synthetic.invalid',8,transport=httpx.ASGITransport(app=app),service_token=token)
    service=PreparationService(session,principal=principal_value,client=client,epoch_id=uuid4())
    async def admit(db,value):
        row=NS(**value);row.redacted_at=None;row.consumed_binding_id=None
        row.frame_json=row.frame_sha256=row.plan_json=row.plan_sha256=None
        rows.append(row);return row
    resolution=B.Resolution(status='resolved',reason='exact_match',stock=B.Stock(stock_code='000720',stock_name='현대건설',market='KOSPI'),candidates=[])
    relative=[];absolute=[];original=asyncio.timeout;original_at=asyncio.timeout_at
    def scaled(seconds):relative.append(seconds);return original(seconds*.01)
    def scaled_at(deadline):
        remaining=deadline-asyncio.get_running_loop().time();absolute.append(remaining)
        return original_at(asyncio.get_running_loop().time()+max(0,remaining)*.01)
    with patch.dict(__import__('os').environ,{'FLOW_ANALYSIS_ENABLED':'true','FLOW_SERVICE_TOKEN':token}),\
         patch.object(repo,'by_key',AsyncMock(return_value=None)),patch.object(repo,'cleanup_owner',AsyncMock()),\
         patch.object(repo,'clock',AsyncMock(return_value=now)),patch.object(repo,'admit',admit),\
         patch.object(repo,'lineage',AsyncMock(side_effect=lambda *args:list(rows))),\
         patch.object(repo,'closure',lambda *args:(None,None)),patch.object(service,'auth',AsyncMock()),\
         patch.object(service,'resolve',AsyncMock(return_value=resolution)),\
         patch.object(asyncio,'timeout',scaled),patch.object(asyncio,'timeout_at',scaled_at):
        result=await service.post(request,uuid4())
    assert result['state'] in {'ready','clarification','unsupported'} and calls==['propose']
    assert relative[0]==75 and 70 in relative and session.commit.await_count>=2
    assert session.scalar.await_count==2  # Real fresh Principal SQL in both dispatch guards.
    assert session.commit.await_count>=4  # Claim, start guard, continue guard, final result.
    assert any(14<seconds<=15 for seconds in absolute)
    assert any(64<seconds<=65 for seconds in absolute) and any(59<seconds<=60 for seconds in absolute)


@pytest.mark.parametrize('policy,expected',[('supervisor.flow-core.1',8),('supervisor.flow-core.2',70)])
async def test_client_policy1_timeout_is_unchanged(policy,expected):
    from src.shared.infrastructure.clients.ai_client import AIClient
    class StopBeforeHTTP(Exception):pass
    factory=Mock(side_effect=StopBeforeHTTP)
    client=AIClient('http://synthetic.invalid',8,service_token='cf024-asgi-synthetic-service-token-at-least32')
    with patch.object(httpx,'AsyncClient',factory),pytest.raises(StopBeforeHTTP):
        await client.plan_supervisor_core({'data':{'policy_version':policy}})
    assert factory.call_args.kwargs['timeout']==expected


def epoch_row():
    return NS(id=uuid4(),created_at=datetime.now(timezone.utc),unit_id='CF023',currency='USD',semantic_sha256=B.MEANING_SPEC_SHA256,price_sha256=B.sha(B.MEANING_SPEC['price']),max_nano=100000000,attempt_reserve_nano=50000000,max_attempts=2,reserved_nano=0,count_requests=0,generation_requests=0,blocked=False,active_attempt_id=None,attempts_json={})


@pytest.mark.parametrize('change',['missing','created','unit','spec','price','blocked','totals','snapshot'])
async def test_live_epoch_is_SELECT_only_and_missing_replacement_or_state_drift_closes(change):
    row=epoch_row();binding=C.OwnedEpochBinding(object(),object(),row.id,row.created_at,B.sha(C.epoch_state(row)),'live')
    if change=='created':row.created_at+=timedelta(seconds=1)
    elif change=='unit':row.unit_id='CF024'
    elif change=='spec':row.semantic_sha256='a'*64
    elif change=='price':row.price_sha256='b'*64
    elif change=='blocked':row.blocked=True
    elif change=='totals':row.reserved_nano=1
    elif change=='snapshot':row.attempts_json={'unexpected':{}}
    calls=[]
    async def scalar(statement):calls.append(statement);return None if change=='missing' else row
    with pytest.raises(CounterUnavailable):await C.existing_epoch(NS(scalar=scalar),binding,initial=True)
    assert len(calls)==1 and calls[0].is_select


def test_replaced_original_proof_or_receipt_never_re_adopts_same_epoch_UUID():
    from scripts.runner_owned_database import RunnerOwnedDatabase
    proof=object.__new__(RunnerOwnedDatabase);proof._owner=NS(receipt=object());proof.verify_ownership=Mock()
    binding=C.OwnedEpochBinding(proof,proof._owner.receipt,uuid4(),datetime.now(timezone.utc),'a'*64,'live')
    other=object.__new__(RunnerOwnedDatabase);other._owner=proof._owner
    with pytest.raises(CounterUnavailable):C.proof_identity(other,binding,'live')
    proof._owner.receipt=object()
    with pytest.raises(CounterUnavailable):C.proof_identity(proof,binding,'live')
    proof.verify_ownership.assert_not_called()


def phase_scope():
    p=principal();request=body();epoch=uuid4();attempt=str(uuid4());now=datetime.now(timezone.utc)
    source=C.DeferredKeySource(AsyncMock(return_value=PRIVATE),object())
    scope=C.PhaseBudget(proof=None,binding=C.OwnedEpochBinding(None,None,epoch,now,'a'*64,'synthetic'),principal=p,body=request,authority=C.SyntheticAuthority(now+timedelta(seconds=30),source),agreement=agreement(),key_source=source,deadline=asyncio.get_running_loop().time()+30,stages=[])
    row=NS(id=uuid4(),attempt_id=UUID(attempt),owner_user_id=p.user_id,epoch_id=epoch,parent_id=None,state='pending',redacted_at=None,expires_at=now+timedelta(minutes=10),semantic_sha256=B.MEANING_SPEC_SHA256,semantic_json=B.canonical(B.MEANING_SPEC),prepare_key_digest=hashlib.sha256(request.prepare_key.encode()).digest(),request_digest=B.sha(request.model_dump(mode='json')),draft_digest=B.sha(request.draft.model_dump(mode='json',exclude={'selected_ticker','candidate_ref'})),draft_json=B.canonical(request.draft.model_dump(mode='json')))
    row.root_id=row.id
    return scope,row,attempt,now


async def test_phase_budget_settlement_can_outlive_send_but_not_authority():
    from contextlib import nullcontext
    from src.modules.supervisor.infrastructure.preparation_repository import DurableMeaningBudget
    scope,_,attempt,_=phase_scope();scope.attempt=attempt
    scope.deadline=asyncio.get_running_loop().time()-1
    scope.settlement_deadline=asyncio.get_running_loop().time()+.1
    completed=AsyncMock()
    with patch.object(C,'proof_identity',Mock()),patch.object(C,'bounded_owned_calls',lambda *args:nullcontext()),patch.object(DurableMeaningBudget,'finish',completed):
        await scope.finish(attempt,{'state':'unknown','estimated_nano':None},blocked=True)
    completed.assert_awaited_once();assert scope.stages==['hold_ACK'] and not scope.uncertain
    scope.settlement_deadline=asyncio.get_running_loop().time()-1
    with pytest.raises(CounterUnavailable):await scope.finish(attempt,{'state':'unknown','estimated_nano':None},blocked=True)
    assert completed.await_count==1 and scope.uncertain


async def test_phase_budget_cancelling_task_never_checks_driver_or_SQL():
    from src.modules.supervisor.infrastructure.preparation_repository import DurableMeaningBudget
    scope,_,attempt,_=phase_scope();scope.attempt=attempt;entered=asyncio.Event()
    async def worker():
        entered.set()
        try:await asyncio.Event().wait()
        except asyncio.CancelledError:
            await scope.finish(attempt,{'state':'unknown','estimated_nano':None},blocked=True)
    identity=Mock();finish=AsyncMock()
    with patch.object(C,'proof_identity',identity),patch.object(DurableMeaningBudget,'finish',finish):
        task=asyncio.create_task(worker());await entered.wait();task.cancel()
        with pytest.raises(asyncio.CancelledError):await task
    identity.assert_not_called();finish.assert_not_awaited();assert scope.uncertain


@pytest.mark.parametrize('change',['owner','attempt','epoch','spec','draft','expired','deleted','revoked'])
async def test_each_phase_revalidates_real_principal_and_exact_preparation_shape(change,monkeypatch):
    from src.modules.auth.application import session_service
    scope,row,attempt,now=phase_scope()
    if change=='owner':row.owner_user_id=uuid4()
    elif change=='attempt':row.attempt_id=uuid4()
    elif change=='epoch':row.epoch_id=uuid4()
    elif change=='spec':row.semantic_sha256='a'*64
    elif change=='draft':row.draft_json='{}'
    elif change=='expired':row.expires_at=now-timedelta(seconds=1)
    elif change=='deleted':row.redacted_at=now
    auth=AsyncMock(side_effect=AuthenticationRequired() if change=='revoked' else None);monkeypatch.setattr(session_service,'validate_principal',auth)
    session=NS(scalar=AsyncMock(side_effect=[row,now]))
    with pytest.raises((CounterUnavailable,AuthenticationRequired)):await scope.validate_preparation(session,attempt,lock=True)
    auth.assert_awaited_once()


async def test_wrong_rendered_request_projection_is_rejected_before_claim_or_supplier():
    scope,_,attempt,_=phase_scope()
    with pytest.raises(CounterUnavailable):await scope.preflight(draft(),attempt,'a'*64,'b'*64,deadline=scope.deadline)
    scope.key_source.supplier.assert_not_awaited()


async def test_supplier_source_capability_is_in_authority_scope_before_reservation():
    scope,_,_,_=phase_scope();approved=scope.key_source
    other=C.DeferredKeySource(AsyncMock(return_value=PRIVATE),object());scope.key_source=other
    with pytest.raises(CounterUnavailable):await scope.lease('count')
    other.supplier.assert_not_awaited();approved.supplier.assert_not_awaited()
    scope.key_source=approved
    await scope.lease('count')
    approved.supplier.assert_not_awaited()


async def test_driver_lock_serializes_two_proofs_and_restores_on_cancellation(monkeypatch):
    from scripts.runner_owned_database import RunnerOwnedDatabase
    driver=NS()
    # A normal object is a weak-referenceable driver, matching LocalDocker's identity behavior.
    class Driver:
        def call(self,*args,**kwargs):return kwargs.get('timeout')
    driver=Driver();original=driver.call
    one=object.__new__(RunnerOwnedDatabase);one._owner=NS(docker=driver)
    two=object.__new__(RunnerOwnedDatabase);two._owner=NS(docker=driver)
    entered=asyncio.Event();second=asyncio.Event();order=[]
    async def exercise(*,proof,deadline,**scope):
        order.append(proof)
        if proof is one:
            entered.set();await asyncio.Event().wait()
        second.set();assert 0<driver.call('synthetic',timeout=15)<=15
        return 'done'
    monkeypatch.setattr(C,'_run_meaning_assembly',exercise)
    first=asyncio.create_task(C.run_meaning_assembly(proof=one));await entered.wait()
    later=asyncio.create_task(C.run_meaning_assembly(proof=two));await asyncio.sleep(0)
    assert not second.is_set()
    first.cancel()
    with pytest.raises(asyncio.CancelledError):await first
    assert await later=='done' and order==[one,two]
    assert driver.call==original


@pytest.mark.parametrize('committed',[False,True])
async def test_actual_preparation_claim_ACK_uncertain_starts_no_gateway(committed,monkeypatch):
    from src.modules.supervisor.application.preparation_service import PreparationService
    from src.modules.supervisor.infrastructure import preparation_repository as repo
    request=body();now=datetime.now(timezone.utc);owner=principal();row=NS(id=uuid4())
    session=NS(rollback=AsyncMock(),commit=AsyncMock(side_effect=OSError(PRIVATE)))
    service=PreparationService(session,principal=owner,client=NS(plan_supervisor_core=AsyncMock()),epoch_id=uuid4())
    service.auth=AsyncMock();service.build=AsyncMock()
    monkeypatch.setattr(repo,'by_key',AsyncMock(return_value=None));monkeypatch.setattr(repo,'cleanup_owner',AsyncMock());monkeypatch.setattr(repo,'clock',AsyncMock(return_value=now));insert=AsyncMock(return_value=row);monkeypatch.setattr(repo,'admit',insert)
    # Both callback simulations raise at the same uncertain ACK boundary; neither grants send permission.
    row.synthetic_commit_observed=committed
    with pytest.raises(OSError):await service.post(request,uuid4())
    insert.assert_awaited_once();service.build.assert_not_awaited();service.client.plan_supervisor_core.assert_not_awaited()


def test_live_source_contains_no_epoch_initialization_or_key_discovery_and_production_stays_unavailable():
    source=(ROOT/'backend/scripts/cf023_supervisor_meaning_check.py').read_text();tree=ast.parse(source)
    live=next(node for node in tree.body if isinstance(node,ast.AsyncFunctionDef) and node.name=='verify_live')
    assembly=next(node for node in tree.body if isinstance(node,ast.AsyncFunctionDef) and node.name=='_run_meaning_assembly')
    assert 'verifier_epoch' not in ast.unparse(live)+ast.unparse(assembly)
    gateway_source=(ROOT/'ai/src/supervisor/infrastructure/openai_meaning_gateway.py').read_text()
    assert 'getenv' not in gateway_source and 'load_dotenv' not in gateway_source
    assert not IMPORTS


@pytest.mark.parametrize('change',['revoked','expired','draft','approval'])
async def test_count_then_fresh_generation_scope_failure_keeps_prior_count_but_sends_no_generation(change,monkeypatch):
    """Same production phase wrapper, with explicit session/delegate simulations (not real DB)."""
    from contextlib import nullcontext
    from scripts import cf002_interactive_login as runner
    from src.modules.auth.application import session_service
    from src.modules.supervisor.infrastructure import preparation_repository
    scope,row,attempt,now=phase_scope();revoked=False;requests=[];sessions=[];holds=[]
    async def validate(session,p,**kw):
        if revoked:raise AuthenticationRequired()
    monkeypatch.setattr(session_service,'validate_principal',validate)
    session=NS(commit=AsyncMock())
    async def scalar(statement):return datetime.now(timezone.utc) if 'clock_timestamp' in str(statement) else row
    session.scalar=scalar
    @asynccontextmanager
    async def owned(proof):sessions.append(session);yield session
    monkeypatch.setattr(runner,'owned_session',owned)
    monkeypatch.setattr(C,'proof_identity',lambda *args:None)
    monkeypatch.setattr(C,'bounded_owned_calls',lambda *args:nullcontext())
    monkeypatch.setattr(C,'existing_epoch',AsyncMock(return_value=epoch_row()))
    class Delegate:
        def __init__(self,sessions,**kw):self.sessions=sessions
        async def authorize(self,*args):
            async with self.sessions() as actual:
                assert actual is session
                await actual.commit()
                return True
        async def finish(self,*args,blocked):
            async with self.sessions() as actual:
                holds.append(blocked);await actual.commit()
    monkeypatch.setattr(preparation_repository,'DurableMeaningBudget',Delegate)
    async def send(request):
        nonlocal revoked
        requests.append(request.url.path)
        if change=='revoked':revoked=True
        elif change=='expired':row.expires_at=now-timedelta(seconds=1)
        elif change=='draft':row.draft_json='{}'
        else:scope.authority.expires_at=now-timedelta(seconds=1)
        return httpx.Response(200,json={'object':'response.input_tokens','input_tokens':100})
    instance=O.OpenAIMeaningGateway(key_supplier=scope.key_source,budget=scope,counter_agreement=agreement(),transport=httpx.MockTransport(send),preflight=scope.preflight)
    with pytest.raises(Exception):await instance.propose(draft(),attempt_id=attempt)
    assert requests==[O.COUNT_PATH] and scope.key_source.supplier.await_count==1
    assert scope.phases==['count'] and scope.uncertain
    assert 'generation_reservation_ACK' not in scope.stages
    assert instance._key is None and instance._key_supplier is None


@pytest.mark.parametrize('injected',['authority','counter_agreement','key_supplier','transport'])
async def test_synthetic_factory_rejects_external_supplier_agreement_or_transport_before_IO(injected,monkeypatch):
    from scripts import cf002_interactive_login as runner
    scope,_,_,_=phase_scope();supplier=AsyncMock(return_value=PRIVATE)
    monkeypatch.setattr(C,'proof_identity',lambda *args:None)
    forbidden=Mock(side_effect=AssertionError('No owned DB access for invalid synthetic injection'))
    monkeypatch.setattr(runner,'owned_session',forbidden)
    value={'authority':object(),'counter_agreement':agreement(),'key_supplier':supplier,'transport':httpx.MockTransport(lambda request:(_ for _ in ()).throw(AssertionError('No send')))}[injected]
    with pytest.raises(CounterUnavailable):
        await C._run_meaning_assembly(mode='synthetic',proof=None,binding=scope.binding,principal=scope.principal,prepare_body=scope.body,deadline=scope.deadline,**{injected:value})
    supplier.assert_not_awaited();forbidden.assert_not_called()


@pytest.mark.parametrize('invalid',['fake_agreement','synthetic_authority','expired_approval','unknown_fee'])
async def test_live_preflight_cannot_promote_fake_or_expired_scope_to_key_read(invalid,monkeypatch):
    from scripts import cf002_interactive_login as runner
    scope,_,_,_=phase_scope();source=scope.key_source
    binding=C.OwnedEpochBinding(None,None,uuid4(),datetime.now(timezone.utc),'a'*64,'live')
    authority=NS(verify=AsyncMock(return_value=datetime.now(timezone.utc)-timedelta(seconds=1)))
    agreed=O.CounterAgreement(O.COUNT_DOCUMENTATION,'a'*64,O.INPUT_FIELDS,1)
    if invalid=='fake_agreement':agreed=agreement()
    elif invalid=='synthetic_authority':authority=scope.authority
    elif invalid=='unknown_fee':agreed=O.CounterAgreement(O.COUNT_DOCUMENTATION,'a'*64,O.INPUT_FIELDS,-1)
    monkeypatch.setattr(C,'proof_identity',lambda *args:None)
    forbidden=Mock(side_effect=AssertionError('Rejected approval cannot reach DB or epoch initialization'))
    monkeypatch.setattr(runner,'owned_session',forbidden)
    with pytest.raises(CounterUnavailable):
        await C._run_meaning_assembly(mode='live',proof=None,binding=binding,principal=scope.principal,prepare_body=scope.body,deadline=scope.deadline,authority=authority,counter_agreement=agreed,key_supplier=source)
    source.supplier.assert_not_awaited();forbidden.assert_not_called()


@pytest.mark.parametrize('proof',[None,object(),NS()])
async def test_crosspath_rejects_non_owned_proof_before_application_or_IO(proof,monkeypatch):
    inner=AsyncMock();monkeypatch.setattr(C,'_verify_meaning_flow_crosspath',inner)
    with pytest.raises(CounterUnavailable):await C.verify_meaning_flow_crosspath(proof)
    inner.assert_not_awaited()


@pytest.mark.parametrize('option',['mode','key_supplier','transport','authority','binding'])
async def test_crosspath_has_no_live_or_external_input_options(option):
    with pytest.raises(TypeError):await C.verify_meaning_flow_crosspath(None,**{option:object()})


@pytest.mark.parametrize('failure',[None,RuntimeError(PRIVATE),asyncio.CancelledError()])
async def test_crosspath_wrapper_owned_identity_isolation_and_cancel_cleanup(failure,monkeypatch):
    """Callback simulation of wrapper cleanup, no PG/auth claim."""
    from contextlib import contextmanager
    from scripts import cf003_admission_check as admission,cf002_interactive_login as runner
    from scripts.runner_owned_database import RunnerOwnedDatabase
    proof=object.__new__(RunnerOwnedDatabase);events=[];logs=[]
    monkeypatch.setattr(RunnerOwnedDatabase,'verify_ownership',lambda value:events.append('ownership'))
    @contextmanager
    def isolated(value):
        assert value is proof;events.append('enter')
        try:yield {'forbidden':0}
        finally:events.append('exit')
    monkeypatch.setattr(admission,'isolated_application',isolated)
    monkeypatch.setattr(runner,'safe_print',logs.append)
    inner=AsyncMock(return_value={'synthetic':True},side_effect=failure);monkeypatch.setattr(C,'_verify_meaning_flow_crosspath',inner)
    if failure is None:
        assert await C.verify_meaning_flow_crosspath(proof)=={'synthetic':True,'observed_denials':{'forbidden':0}}
    else:
        with pytest.raises(type(failure)):await C.verify_meaning_flow_crosspath(proof)
        assert PRIVATE not in repr(logs)
    assert events==['ownership','enter','exit'];inner.assert_awaited_once_with(proof)


def crosspath_ast():
    tree=ast.parse((ROOT/'backend/scripts/cf023_supervisor_meaning_check.py').read_text())
    return next(n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='_verify_meaning_flow_crosspath')


@pytest.mark.parametrize('cancelled',[False,True])
async def test_first_owner_GET_scopes_synthetic_feature_token_and_restores_after_cancel(cancelled):
    """Execute actual early-GET scope with HTTP callback, not authenticated PG."""
    import os
    node=next(n for n in crosspath_ast().body if isinstance(n,ast.Try) and any(isinstance(v,ast.Name) and v.id=='early' for v in ast.walk(n)))
    settings=NS(FLOW_ANALYSIS_ENABLED=False,FLOW_SERVICE_TOKEN='original-synthetic')
    original_env=dict(os.environ);dependency=object();original_override=object()
    app=NS(dependency_overrides={dependency:object()});early_overrides={dependency:original_override};seen=[]
    plan={'plan_hash':'a'*64};first={'plan_hash':'a'*64};token='cf029-test-synthetic-token'
    class Client:
        def __init__(self,**kw):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def get(self,*args,**kwargs):
            assert settings.FLOW_ANALYSIS_ENABLED is True and settings.FLOW_SERVICE_TOKEN==token
            assert os.environ['FLOW_ANALYSIS_ENABLED']=='true' and os.environ['FLOW_SERVICE_TOKEN']==token
            seen.append(True)
            if cancelled:raise asyncio.CancelledError()
            return NS(status_code=200,headers={'cache-control':'private, no-store'},json=lambda:{'data':{'state':'ready','meaning_status':'supplemented','plan':plan}})
    def check(value,label):assert value,label
    namespace=dict(check=check,settings=settings,patch=patch,token=token,httpx=NS(AsyncClient=Client,ASGITransport=lambda **kw:object()),app=app,first_id=str(uuid4()),primary=('synthetic-cookie',None),auth=NS(SESSION_COOKIE='synthetic-session'),first=first,early_overrides=early_overrides)
    function=ast.AsyncFunctionDef(name='exercise',args=ast.arguments(posonlyargs=[],args=[],kwonlyargs=[],kw_defaults=[],defaults=[]),body=[node],decorator_list=[])
    exec(compile(ast.fix_missing_locations(ast.Module(body=[function],type_ignores=[])),'<actual-early-GET-scope>','exec'),namespace)
    if cancelled:
        with pytest.raises(asyncio.CancelledError):await namespace['exercise']()
    else:await namespace['exercise']()
    assert seen==[True] and settings.FLOW_ANALYSIS_ENABLED is False and settings.FLOW_SERVICE_TOKEN=='original-synthetic'
    assert dict(os.environ)==original_env and app.dependency_overrides==early_overrides


@pytest.mark.parametrize('status',[200,404,401])
def test_crosspath_legacy_report_decoder_uses_actual_contract_and_stored_identity(status):
    """Execute the checker's actual decoder with synthetic HTTP responses; no PG claim."""
    from src.modules.flow.api.schemas import FlowReportEnvelope
    node=next(n for n in crosspath_ast().body if isinstance(n,ast.FunctionDef) and n.name=='flow_response')
    def check(value,label):assert value,label
    namespace=dict(check=check,FlowReportEnvelope=FlowReportEnvelope)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),'<crosspath-legacy-report-decoder>','exec'),namespace)
    decode=namespace['flow_response'];report_id=str(uuid4())
    expected={200:{'report_id':report_id,'report':{'fixed':'stored-payload'}},404:{'detail':'report not found'},401:{'detail':{'code':'AUTH_REQUIRED','message':'인증이 필요합니다.'}}}[status]
    def response(value,*,code=status,private=True):return httpx.Response(code,json=value,headers={'cache-control':'private, no-store'} if private else {})
    assert decode(response(expected),status,report_id)==expected
    for invalid in ({'data':expected,'error':None},{'detail':{'code':'RESOURCE_NOT_FOUND'}},{'report_id':str(uuid4()),'report':{}}):
        with pytest.raises(AssertionError):decode(response(invalid),status,report_id)
    with pytest.raises(AssertionError):decode(response(expected,code=503),status,report_id)
    with pytest.raises(AssertionError):decode(response(expected,private=False),status,report_id)


@pytest.mark.parametrize('changed',['none','meaning','Flow','count','generation','supplier'])
async def test_crosspath_observation_guard_rejects_extra_calls_or_unknown_hold_mutation(changed):
    """Execute actual nested guard against simulated observations, not SQL."""
    node=next(n for n in crosspath_ast().body if isinstance(n,ast.AsyncFunctionDef) and n.name=='unchanged')
    held={'blocked':True,'active':'fixed-unknown','reserved':100000000,'count':2,'generation':2}
    actual=dict(held);expected={'runs':1,'reservations':1,'reports':1};totals=dict(expected)
    stages=[['mock_count','mock_generation','synthetic_key_supplied'] for _ in range(2)]
    if changed=='meaning':actual['blocked']=False
    elif changed=='Flow':totals['runs']=2
    elif changed!='none':stages[0].append({'count':'mock_count','generation':'mock_generation','supplier':'synthetic_key_supplied'}[changed])
    def check(value,label):assert value,label
    namespace=dict(check=check,epoch_snapshot=AsyncMock(return_value=actual),held_snapshot=held,totals=AsyncMock(return_value=totals),stages=stages)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),'<crosspath-observation-guard>','exec'),namespace)
    if changed=='none':await namespace['unchanged'](expected)
    else:
        with pytest.raises(AssertionError):await namespace['unchanged'](expected)


def test_crosspath_source_keeps_two_assemblies_same_epoch_and_adopts_actual_owner_plan():
    node=crosspath_ast();source=ast.unparse(node)
    calls=[n for n in ast.walk(node) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)]
    assert len([n for n in calls if n.func.id=='capture_synthetic_epoch'])==1
    assemblies=[n for n in calls if n.func.id=='run_meaning_assembly']
    assert len(assemblies)==2
    assert all(next(k.value.value for k in n.keywords if k.arg=='mode')=='synthetic' for n in assemblies)
    assert next(k.value.value for k in assemblies[-1].keywords if k.arg=='scenario')=='missing_usage'
    assert all(n.lineno<next(n.lineno for n in node.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='call') for n in assemblies)
    assert 'Preparation.owner_user_id == primary[1].user_id' in source and 'Preparation.prepare_key_digest' in source
    assert 'validate_plan(view[\'plan\'], Draft.model_validate(first_body[\'draft\']))' in source
    assert "value['client_key'] = str(uuid4())" in source
    confirmations=[n for n in ast.walk(node) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='call' and len(n.args)>=3 and isinstance(n.args[2],ast.Name) and n.args[2].id=='confirmation']
    assert len(confirmations)==3  # 429, same key/body retry, replay
    assert "patch.dict('os.environ'" in source and 'app.dependency_overrides.update(previous)' in source
    assert 'DELETE' not in source and 'verify_live' not in source


@pytest.mark.parametrize('flag,checker,phase',[('--verify-supervisor-meaning-flow-db','verify_meaning_flow_crosspath','supervisor_meaning_flow_db_check'),('--verify-supervisor-meaning-assembly-db','verify_meaning_assembly','supervisor_meaning_assembly_db_check')])
def test_actual_CLI_parser_DB_only_routing_bounded_dispatch_and_cleanup(flag,checker,phase,monkeypatch):
    """Actual main AST with DI callbacks, no Docker/SQL/bootstrap/server invocation."""
    import argparse
    from contextlib import ExitStack,contextmanager
    from scripts import cf003_admission_check as admission
    tree=ast.parse((ROOT/'backend/scripts/cf002_interactive_login.py').read_text())
    main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
    events=[];logs=[];proof=NS(safe_receipt=lambda:dict(resource_id='synthetic-owned',container_id='0'*64,created_at='synthetic',host='127.0.0.1',port=1234,persistent_mounts=[],cleanup_owner='synthetic',nonce=PRIVATE))
    owner=NS(create=lambda:(events.append('create') or proof),cleanup=lambda:events.append('remove'),receipt=object(),resource_id='synthetic-owned')
    docker=NS(close=lambda:events.append('docker-close'))
    @contextmanager
    def home(value):
        assert value is docker;events.append('home-enter')
        try:yield
        finally:events.append('home-exit')
    monkeypatch.setattr(admission,'owned_postgres_home',home)
    async def migrate(value,**kw):assert value is proof;events.append(('migrate',kw))
    async def verify(value):assert value is proof;events.append(checker);return {'simulation':True}
    monkeypatch.setattr(C,checker,verify)
    def forbidden(*a,**kw):raise AssertionError('No frontend/Google/ports/server fall-through')
    async def wait_for(coro,timeout):
        events.append(('timeout',timeout));return await coro
    def run(coro):return asyncio.run(coro)
    namespace=dict(argparse=argparse,__doc__='synthetic CLI routing',ExitStack=ExitStack,signal=NS(SIGINT=2,SIGTERM=15,SIG_IGN=0,signal=lambda *a:None),LocalDocker=lambda:docker,OwnedPostgres=lambda value:owner,ensure_local_ports_free=forbidden,prepare_projects=forbidden,migrate_owned=migrate,asyncio=NS(run=run,wait_for=wait_for),safe_print=logs.append)
    monkeypatch.setattr(sys,'argv',['cf002_interactive_login.py',flag])
    exec(compile(ast.fix_missing_locations(ast.Module(body=[main],type_ignores=[])),'<actual-CF029-CLI-main>','exec'),namespace)
    namespace['main']()
    assert events==['home-enter','create',('timeout',90),('migrate',{'target':'head'}),('timeout',120),checker,'remove','home-exit','docker-close']
    assert [v for v in logs if v['phase']==phase]==[{'phase':phase,'simulation':True}]
    assert PRIVATE not in repr(logs)


def test_new_CLI_flag_is_mutually_exclusive_and_in_all_owned_failure_cleanup_branches():
    tree=ast.parse((ROOT/'backend/scripts/cf002_interactive_login.py').read_text())
    main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
    for node in ast.walk(main):
        if isinstance(node,ast.If):
            attrs={n.attr for n in ast.walk(node.test) if isinstance(n,ast.Attribute)}
            if 'verify_supervisor_meaning_assembly_db' in attrs and len(attrs)>1:
                assert 'verify_supervisor_meaning_flow_db' in attrs
    source=ast.unparse(main)
    assert "mode.add_argument('--verify-supervisor-meaning-flow-db', action='store_true')" in source
    assert "'cf029_failure_diagnostic' if args.verify_supervisor_meaning_flow_db" in source
