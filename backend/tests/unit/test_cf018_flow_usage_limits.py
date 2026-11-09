"""One protected collection: pure policy, real receipt/control and injected AI only."""
import asyncio,copy,hashlib,json,sys
from datetime import UTC,datetime,timedelta
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock,Mock
from uuid import uuid4
import httpx,pytest
from scripts.cf012_analysis_check import flow_app,engine_result,zero_call_usage
from tests.unit.test_cf017_flow_error_classification import extract,kis,origins,TOKEN,SECRET
from tests.unit.test_cf017_flow_error_classification import test_slot_held_until_actual_worker_exit as _slot
from tests.unit.test_cf017_flow_error_classification import test_SDK_timeout_binding_to_HTTP as _sdk_timeout
from tests.unit.test_flow_contract import test_relocation_public_contract_baseline as _baseline
from tests.unit.test_flow_contract import test_cf003_snapshot_projection_rejects_unapproved_changes as _negative
from src.modules.analysis.domain import usage as u
from src.modules.analysis.application.usage_service import FlowUsageControl
from src.modules.analysis.infrastructure import usage_repository as repository
from db.models.common.analysis_usage import AnalysisProviderCall
from src.modules.flow.domain import analysis as flow
from src.modules.flow.application.analysis_service import AnalysisError
from src.modules.flow.domain.execution import ErrorCode


def settings(**changes):return NS(FLOW_USAGE_LIMITS_ENABLED='true',FLOW_SUPPORTED_TICKERS='005930',FLOW_USER_DAILY_REQUEST_LIMIT='2',FLOW_SERVICE_DAILY_REQUEST_LIMIT='3',FLOW_SERVICE_DAILY_BUDGET_USD='3',**changes)

def configured(**changes):
    values=vars(settings())|changes;return NS(**values)


def row():
    stamp=datetime(2026,11,8,tzinfo=UTC);request=flow.canonical({'ticker':'005930','question':'합성 사용량','as_of':stamp.isoformat()})
    return NS(id=uuid4(),attempt_id=uuid4(),admission_request_id=uuid4(),owner_user_id=uuid4(),operation='flow.analysis.v1',claim_digest=hashlib.sha256(b'synthetic-grant').digest(),
        ticker='005930',stock_name='합성 종목',request_json=request,input_fingerprint=flow.sha(request),as_of=stamp,
        candidate_date=flow.candidate(stamp),deadline_at=datetime.now(UTC)+timedelta(seconds=30),spec_json=flow.canonical(flow.SPEC))


def dto(value):
    flow_app(engine_result)
    return sys.modules['_cf012_flow.api.schemas'].FlowAnalysisInput.model_validate(flow.ai_request(value))


def envelope(value):
    req=dto(value);result=engine_result(req,None)
    return dict(schema_version=1,**{k:req.wire()[k] for k in ('analysis_id','attempt_id','admission_request_id','fingerprint')},
        report_id=result['payload']['report_id'],payload=result['payload'],input_snapshot=result['input_snapshot'],input_sha256=flow.sha(flow.canonical(result['input_snapshot'])))


def call_receipt(value,*,state='observed',model='gpt-5.4-mini',inp=100,cached=None,out=10):
    response=envelope(value);call=response['input_snapshot']['provider_usage']['calls'][0]
    call.update(state=state,attempted=True,input_tokens=inp,cached_tokens=cached,output_tokens=out,
        response_model=model,input_bytes=100,output_bytes=20)
    return response


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setenv('FLOW_ANALYSIS_ENABLED','true');monkeypatch.setenv('FLOW_SERVICE_TOKEN',TOKEN)


def test_exact_public_enum_projection(monkeypatch):
    _baseline(monkeypatch);_negative(monkeypatch,'fourth_enum')


@pytest.mark.parametrize('key,value',[
 ('FLOW_USAGE_LIMITS_ENABLED',None),('FLOW_USAGE_LIMITS_ENABLED',True),('FLOW_USAGE_LIMITS_ENABLED','TRUE'),
 ('FLOW_SUPPORTED_TICKERS',''),('FLOW_SUPPORTED_TICKERS','005930,005930'),('FLOW_SUPPORTED_TICKERS','１２３４５６'),('FLOW_SUPPORTED_TICKERS',['005930']),
 ('FLOW_USER_DAILY_REQUEST_LIMIT',0),('FLOW_USER_DAILY_REQUEST_LIMIT','0'),('FLOW_USER_DAILY_REQUEST_LIMIT','01'),('FLOW_USER_DAILY_REQUEST_LIMIT','1e3'),
 ('FLOW_SERVICE_DAILY_REQUEST_LIMIT',True),('FLOW_SERVICE_DAILY_REQUEST_LIMIT',str(u.MAX_INT+1)),
 ('FLOW_SERVICE_DAILY_BUDGET_USD',.1),('FLOW_SERVICE_DAILY_BUDGET_USD','1e1'),('FLOW_SERVICE_DAILY_BUDGET_USD','NaN'),('FLOW_SERVICE_DAILY_BUDGET_USD','-1'),('FLOW_SERVICE_DAILY_BUDGET_USD','0'),('FLOW_SERVICE_DAILY_BUDGET_USD','0.1234567890')])
def test_closed_raw_policy(key,value):
    with pytest.raises(u.PolicyUnavailable):u.policy(configured(**{key:value}))


def test_policy_period_integer_prices_and_settings_no_startup_failure():
    from src.shared.config import Settings
    raw=Settings(_env_file=None,DATABASE_URL='postgresql+asyncpg://unused:unused@127.0.0.1:1/unused',
        FLOW_USAGE_LIMITS_ENABLED={'bad':True},FLOW_SERVICE_DAILY_BUDGET_USD=float('nan'),FLOW_USER_DAILY_REQUEST_LIMIT=False)
    assert raw.FLOW_USAGE_LIMITS_ENABLED=={'bad':True}
    with pytest.raises(u.PolicyUnavailable):u.policy(raw)
    assert u.policy(settings()).budget==3000000000
    assert u.RUN_RESERVE==3*(400000*750+1000*4500)==913500000
    assert u.amount(100,10,10)==113250 and u.amount(100,None,10)==120000
    assert u.period(datetime(2026,11,8,15,tzinfo=UTC))[0]==datetime(2026,11,8,15,tzinfo=UTC)
    assert u.period(datetime(2026,11,8,14,59,59,tzinfo=UTC))[0]==datetime(2026,11,7,15,tzinfo=UTC)
    with pytest.raises(ValueError):u.amount(u.MAX_INT,None,u.MAX_INT)


@pytest.mark.parametrize('mutation',['bool','negative','float','cached','missing','binding','price','model'])
def test_strict_usage_unknown_and_independent_anomaly(mutation):
    value=row();response=call_receipt(value);metadata=response['input_snapshot']['provider_usage'];call=metadata['calls'][0]
    if mutation=='bool':call['input_tokens']=True
    elif mutation=='negative':call['output_tokens']=-1
    elif mutation=='float':call['input_tokens']=1.5
    elif mutation=='cached':call['cached_tokens']=101
    elif mutation=='missing':call['output_tokens']=None
    elif mutation=='binding':metadata['attempt_id']=str(uuid4())
    elif mutation=='price':metadata['price_id']='unreviewed'
    else:call['response_model']='unreviewed-'+SECRET
    result=u.receipt(value,response)
    if mutation=='binding':assert result is None
    elif mutation in {'price','model'}:
        assert result[0].state=='anomalous' and result[0].estimated_nano is None
        assert SECRET not in repr(result)
    else:assert result[0].state=='unknown' and result[0].estimated_nano is None


@pytest.mark.parametrize('problem',['missing','total','cached'])
@pytest.mark.parametrize('anomaly',['model','cap'])
def test_runtime_preserves_anomaly_independently_of_unchargeable_usage(problem,anomaly):
    value=row();req=dto(value);module=sys.modules['_cf012_flow.application.execution_runtime'];ctx=module.ExecutionContext(req)
    identity=ctx.begin_call('openai','completion',input_bytes=100)
    inp=400001 if anomaly=='cap' else 100
    usage={'input_tokens':inp,'output_tokens':10,'total_tokens':inp+10}
    if problem=='missing':usage=None
    elif problem=='total':usage['total_tokens']=1
    else:usage['input_token_details']={'cache_read':True}
    # A missing record can still expose an independently large input in another
    # field only when actually observed; do not invent it for the cap case.
    if problem=='missing' and anomaly=='cap':usage={'input_tokens':inp}
    ctx.openai_observed(identity,NS(usage_metadata=usage,response_metadata={'model_name':'other-model-'+SECRET if anomaly=='model' else 'gpt-5.4-mini'}))
    response=envelope(value);response['input_snapshot']['provider_usage']=ctx.final_usage()
    record=u.receipt(value,response)[0]
    assert record.state=='anomalous' and record.estimated_nano is None
    assert record.reason==('MODEL_MISMATCH' if anomaly=='model' else 'CAP_EXCEEDED')
    assert SECRET not in repr(record) and not u.valid_complete_usage(value,response)


def accounting(value):
    value.budget_reservation_id=value.id;grant=b'synthetic-grant';value.claim_digest=hashlib.sha256(grant).digest()
    bucket=lambda:NS(id=uuid4(),request_count=1,held_nano=u.RUN_RESERVE,estimated_spend_nano=0,blocked=False)
    service,user=bucket(),bucket()
    reservation=NS(id=value.id,owner_user_id=value.owner_user_id,operation=value.operation,attempt_id=value.attempt_id,
        claim_digest=value.claim_digest,remaining_nano=u.RUN_RESERVE,estimated_spend_nano=0,state='held')
    calls=[AnalysisProviderCall(id=u.call_id(value.id,value.attempt_id,*slot),reservation_id=value.id,
        provider=slot[0],action=slot[1],ordinal=slot[2],reserved_nano=u.CALL_RESERVE if slot[0]=='openai' else 0,
        released_nano=0,attempted=None,state='unknown',reason='UNOBSERVED') for slot in u.SLOTS]
    session=NS(flush=AsyncMock(),commit=AsyncMock(),rollback=AsyncMock(),add=Mock())
    return grant,(service,user,reservation,calls),session


async def test_unknown_attempt_cannot_become_not_called_and_valid_receipt_settles_once(monkeypatch):
    value=row();grant,locked,session=accounting(value);service,user,reservation,calls=locked
    monkeypatch.setattr(repository,'accounting',AsyncMock(return_value=locked));control=FlowUsageControl(session,AnalysisError)
    unknown=call_receipt(value,state='unknown',model=None,inp=None,out=None)
    await control.observe(value,grant,unknown)
    assert calls[0].attempted is True and reservation.remaining_nano==u.CALL_RESERVE
    contradicted=envelope(value)
    before=(service.held_nano,service.estimated_spend_nano,reservation.remaining_nano)
    with pytest.raises(u.UsageConflict):await control.observe(value,grant,contradicted)
    assert before==(service.held_nano,service.estimated_spend_nano,reservation.remaining_nano)
    confirmed=call_receipt(value)
    await control.observe(value,grant,confirmed);amount=service.estimated_spend_nano
    assert reservation.remaining_nano==0 and amount==120000 and calls[0].attempted is True
    await control.observe(value,grant,copy.deepcopy(confirmed));assert service.estimated_spend_nano==amount
    changed=call_receipt(value,out=11)
    with pytest.raises(u.UsageConflict):await control.observe(value,grant,changed)


@pytest.mark.parametrize('kind',['model_missing','model_cached','cap_missing','cap_cached','usage_missing'])
async def test_anomaly_commits_blocked_hold_separately_from_normal_usage(monkeypatch,kind):
    value=row();grant,locked,session=accounting(value);service,user,reservation,calls=locked
    monkeypatch.setattr(repository,'accounting',AsyncMock(return_value=locked));control=FlowUsageControl(session,AnalysisError)
    response=call_receipt(value,state='unknown',model='wrong' if kind.startswith('model') else 'gpt-5.4-mini',
        inp=400001 if kind.startswith('cap') else 100,cached=True if kind.endswith('cached') else None,out=None)
    await control.observe(value,grant,response)
    assert reservation.remaining_nano==u.CALL_RESERVE and service.estimated_spend_nano==0
    assert service.blocked==user.blocked==(kind!='usage_missing')
    assert reservation.state==('blocked' if kind!='usage_missing' else 'unknown')
    session.commit.assert_awaited_once()


async def test_unobserved_final_not_called_releases_but_bodyless_does_not(monkeypatch):
    value=row();grant,locked,session=accounting(value);monkeypatch.setattr(repository,'accounting',AsyncMock(return_value=locked))
    control=FlowUsageControl(session,AnalysisError);await control.observe(value,grant,{})
    assert locked[0].held_nano==u.RUN_RESERVE;session.commit.assert_not_awaited()
    await control.observe(value,grant,envelope(value));assert locked[0].held_nano==0 and locked[2].state=='settled'


async def test_new_admission_counters_and_period_snapshot_only(monkeypatch):
    value=row();stamp=datetime.now(UTC)
    service=NS(id=uuid4(),blocked=False,request_count=0,request_limit=3,budget_limit_nano=3*u.RUN_RESERVE,
        user_request_limit=2,held_nano=0,estimated_spend_nano=0)
    user=NS(id=uuid4(),blocked=False,request_count=0,request_limit=2,held_nano=0,estimated_spend_nano=0)
    method=AsyncMock(side_effect=[service,user]);monkeypatch.setattr(repository,'period',method)
    session=NS(add=Mock(),flush=AsyncMock(),commit=AsyncMock());control=FlowUsageControl(session,AnalysisError,settings())
    assert control.new_values(NS(ticker='005930'),{'id':value.id})=={'budget_reservation_id':value.id}
    await control.reserve(value,stamp)
    assert service.request_count==user.request_count==1 and service.held_nano==user.held_nano==u.RUN_RESERVE
    assert session.add.call_count==10;session.commit.assert_not_awaited()
    assert method.await_args_list[1].kwargs['request_limit']==service.user_request_limit
    with pytest.raises(AnalysisError) as error:control.new_values(NS(ticker='000001'),{'id':value.id})
    assert error.value.code==ErrorCode.FEATURE_UNAVAILABLE


async def test_existing_get_and_snapshot_replay_do_not_parse_invalid_settings(monkeypatch):
    from src.modules.flow.application.analysis_service import AnalysisService
    from src.modules.auth.application.session_service import Principal
    from src.modules.flow.application import analysis_service
    value=row();value.state='result_ready';value.budget_reservation_id=None
    principal=Principal(value.owner_user_id,uuid4(),datetime.now(UTC)+timedelta(hours=1),b'x'*32)
    session=NS(commit=AsyncMock(),rollback=AsyncMock());service=AnalysisService(session,principal=principal,client=None)
    service._authorize=AsyncMock();service._locked=AsyncMock(return_value=value);service._view=Mock(return_value='view');service._publish=AsyncMock(return_value='restored')
    service.usage_control.new_values=Mock(side_effect=AssertionError('new policy must not run'))
    monkeypatch.setattr(analysis_service.repository,'owned',AsyncMock(return_value=value))
    monkeypatch.setattr(analysis_service.repository,'expire',AsyncMock())
    monkeypatch.setattr(analysis_service.repository,'by_key',AsyncMock(return_value=value))
    body={'ticker':value.ticker,'question':'합성 사용량','as_of':value.as_of.isoformat(),'idempotency_key':'existing','allow_analysis':True}
    assert await service.post(body,uuid4())=='restored';service._publish.assert_awaited_once()
    assert await service.get(value.id)=='view';service.usage_control.new_values.assert_not_called()


@pytest.mark.parametrize('where',['constructor','invoke'])
async def test_preserved_SDK_timeout_caps(enabled,where):await _sdk_timeout(enabled,where)
@pytest.mark.parametrize('stop',['timeout','cancel'])
async def test_preserved_actual_sync_slot_lifetime(stop):await _slot(stop)


def runtime_context():
    value=row();req=dto(value);return value,sys.modules['_cf012_flow.application.execution_runtime'].ExecutionContext(req)


@pytest.mark.parametrize('size,allowed',[(32768,True),(32769,False)])
def test_prompt_cap_before_constructor_and_fixed_options(size,allowed):
    value,context=runtime_context();construct=Mock();invoke=Mock(return_value=NS(content='ok',usage_metadata=None,response_metadata={}))
    construct.return_value=NS(invoke=invoke)
    code=extract('ai/src/agents/flow/infrastructure/llm/explain.py',{'explain'},dict(ChatOpenAI=construct,APITimeoutError=type('SDKTimeout',(Exception,),{}),
        DeadlineExceeded=sys.modules['src.shared.runtime.deadline'].DeadlineExceeded,load_dotenv=lambda **kwargs:None,_ENV_FILE=None,
        _PROMPT_PATH=NS(read_text=lambda **kwargs:'x'*size),_facts_to_text=lambda *args:'',_MODEL='gpt-5.4-mini',_TEMPERATURE=.2))
    if allowed:
        assert code['explain']({},NS(passed=True),{},execution_context=context)=='ok'
        assert construct.call_args.kwargs|{}==dict(model='gpt-5.4-mini',temperature=.2,timeout=construct.call_args.kwargs['timeout'],max_retries=0,max_completion_tokens=1000,n=1,service_tier='default')
        assert sum(c['attempted'] is True for c in context.final_usage()['calls'])==1
    else:
        with pytest.raises(ValueError):code['explain']({},NS(passed=True),{},execution_context=context)
        construct.assert_not_called();invoke.assert_not_called()


def test_usage_observed_before_output_cap_and_deadline():
    value,context=runtime_context();events=[]
    original=context.openai_observed
    def observe(*args):events.append('usage');original(*args)
    context.openai_observed=observe
    code=extract('ai/src/agents/flow/infrastructure/llm/explain.py',{'explain'},dict(ChatOpenAI=lambda **kwargs:NS(invoke=lambda prompt:NS(content='x'*16385,usage_metadata={'input_tokens':100,'output_tokens':10},response_metadata={'model_name':'gpt-5.4-mini'})),
        APITimeoutError=type('SDKTimeout',(Exception,),{}),DeadlineExceeded=sys.modules['src.shared.runtime.deadline'].DeadlineExceeded,load_dotenv=lambda **kwargs:None,
        _ENV_FILE=None,_PROMPT_PATH=NS(read_text=lambda **kwargs:'fixed'),_facts_to_text=lambda *args:'',_MODEL='gpt-5.4-mini',_TEMPERATURE=.2))
    with pytest.raises(ValueError):code['explain']({},NS(passed=True),{},execution_context=context)
    trace=context.final_usage();assert events==['usage'] and trace['calls'][0]['output_bytes']==16385 and trace['calls'][0]['input_tokens']==100


def test_KIS_cache_hit_actual_HTTP_entries_and_bounded_retry(tmp_path):
    value,context=runtime_context();code=kis(tmp_path)
    client=NS(post=Mock(return_value=NS(status_code=200,json=lambda:{'access_token':'synthetic-token','expires_in':3600})),get=Mock())
    for _ in range(2):assert code['_get_token'](client,'key','secret','https://synthetic.invalid',execution_context=context)=='synthetic-token'
    assert client.post.call_count==1
    client.get.side_effect=[NS(status_code=500,json=lambda:{'msg_cd':'EGW00201','msg1':SECRET}),NS(status_code=200,json=lambda:{'ok':True})]
    assert code['_get_json'](client,code['_QUOTATIONS_PATH'],{}, {},'fixed',execution_context=context)=={'ok':True}
    code['time'].sleep.assert_called_once_with(.6);assert client.get.call_count==2
    with pytest.raises(code['KisError']):code['_get_json'](client,code['_QUOTATIONS_PATH'],{}, {},'fixed',execution_context=context)
    assert client.get.call_count==2
    trace=context.final_usage()['calls'];assert sum(c['attempted'] is True for c in trace)==3
    assert [c['http_status'] for c in trace if c['provider']=='kis' and c['action']=='supply']==[500,200]
    assert all(c['input_tokens'] is None for c in trace if c['provider']=='kis')


@pytest.mark.parametrize('kind',['user','service','money','blocked'])
async def test_valid_exhausted_policy_is_429_without_counter_or_reservation(monkeypatch,kind):
    value=row();service=NS(id=uuid4(),blocked=kind=='blocked',request_count=3 if kind=='service' else 0,request_limit=3,
        budget_limit_nano=u.RUN_RESERVE-1 if kind=='money' else 3*u.RUN_RESERVE,user_request_limit=2,held_nano=0,estimated_spend_nano=0)
    user=NS(id=uuid4(),blocked=False,request_count=2 if kind=='user' else 0,request_limit=2,held_nano=0,estimated_spend_nano=0)
    monkeypatch.setattr(repository,'period',AsyncMock(side_effect=[service,user]));session=NS(add=Mock(),flush=AsyncMock())
    control=FlowUsageControl(session,AnalysisError,settings());control.new_values(NS(ticker='005930'),{'id':value.id})
    before=(service.request_count,user.request_count,service.held_nano,user.held_nano)
    with pytest.raises(AnalysisError) as caught:await control.reserve(value,datetime.now(UTC))
    assert caught.value.code==ErrorCode.USAGE_LIMIT_EXCEEDED and before==(service.request_count,user.request_count,service.held_nano,user.held_nano)
    session.add.assert_not_called()


def test_compiled_migration_and_ORM_policy_JSON_is_literal_not_bind():
    import ast
    from pathlib import Path
    import sqlalchemy as sa
    from sqlalchemy.schema import CreateTable
    from sqlalchemy.dialects import postgresql
    for path in ('db/models/common/analysis_usage.py','db/migrations/versions/20261109_c18001a7e0001_flow_usage_limits.py'):
        tree=ast.parse(Path(path).read_text())
        checks=next(ast.literal_eval(node.value) for node in tree.body if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name) and node.targets[0].id=='RESERVATION_CHECKS')
        table=sa.Table('synthetic_policy',sa.MetaData(),sa.Column('policy_json',sa.Text()),sa.CheckConstraint(checks['policy']))
        sql=str(CreateTable(table).compile(dialect=postgresql.dialect()))
        literal=sql.split("policy_json::jsonb='")[1].split("'::jsonb")[0]
        assert json.loads(literal)==u.USAGE_SPEC and 'NULL' not in literal
