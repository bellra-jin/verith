"""CF-012 concentrated synthetic boundaries; no provider/DB/graph imports."""
import asyncio
import copy
from datetime import UTC,datetime,timedelta
import hashlib
import json
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
from fastapi import FastAPI
from httpx import ASGITransport,AsyncClient,MockTransport,Response,AsyncByteStream
from pydantic import ValidationError
from scripts.cf012_analysis_check import flow_app,engine_result
from src.modules.flow.api.analysis_schemas import AnalysisRequest
from src.modules.flow.domain import analysis as domain
from src.modules.flow.domain.execution import ContractViolation,ErrorCode
from src.modules.flow.application.analysis_service import AnalysisService,AnalysisError
from src.modules.flow.application import analysis_service as service
from src.modules.flow.application.report_service import FlowReportIdConflict
from src.shared.infrastructure.clients.ai_client import AIClient,AITimeoutError,AIContractError

# The unchanged worker origin invariant requires these two pre-existing pinned,
# pure modules at collection as well as exit. No cache operation is invoked.
_AI_COPY=Path(__file__).resolve().parents[3]/'ai/src'
sys.path.append(str(_AI_COPY))
try:
    from agents.flow.infrastructure import token_cache as _origin_cache
    from agents.flow.domain import observation_window as _origin_window
finally:sys.path.remove(str(_AI_COPY))


def body(**change):return dict(ticker='005930',question='합성 검증',as_of='2026-11-08T00:00:00Z',idempotency_key='unit',allow_analysis=True)|change

def row():
    normalized=domain.canonical(AnalysisRequest.model_validate(body()).normalized_input())
    return SimpleNamespace(id=uuid4(),attempt_id=uuid4(),admission_request_id=uuid4(),ticker='005930',stock_name='합성 종목',request_json=normalized,input_fingerprint=domain.sha(normalized),as_of=datetime(2026,11,8,tzinfo=UTC),candidate_date=domain.candidate(datetime(2026,11,8,tzinfo=UTC)),deadline_at=datetime.now(UTC)+timedelta(seconds=20),spec_json=domain.canonical(domain.SPEC),state='result_ready',error_code=None)


def envelope(value):
    flow_app(engine_result)
    from _cf012_flow.api.schemas import FlowAnalysisInput
    request=FlowAnalysisInput.model_validate(domain.ai_request(value));result=engine_result(request,None)
    return dict(schema_version=1,**{k:request.wire()[k] for k in ('analysis_id','attempt_id','admission_request_id','fingerprint')},report_id=result['payload']['report_id'],payload=result['payload'],input_snapshot=result['input_snapshot'],input_sha256=domain.sha(domain.canonical(result['input_snapshot'])))


@pytest.mark.parametrize('change',[{'allow_analysis':False},{'allow_analysis':1},{'owner':'forbidden'},{'ticker':'00000'},{'as_of':'2026-11-08T09:00:00+09:00'},{'as_of':'2026-11-08T00:00:00'},{'idempotency_key':'x'*257},{'question':' ' }])
def test_strict_request(change):
    with pytest.raises(ValidationError):AnalysisRequest.model_validate(body(**change))


def test_canonical_binding_and_zero_null_preservation():
    value=row();response=envelope(value);original=copy.deepcopy(response)
    ref,input_text,result_text=domain.validate_response(value,response,uuid4())
    assert str(ref.report_id)==response['report_id'];assert json.loads(result_text)==original['payload'];assert json.loads(input_text)==original['input_snapshot']
    assert response==original and response['payload']['signals']['daily'][0]['개인']==0
    value.input_json=input_text;value.result_json=result_text;value.input_sha256=domain.sha(input_text);value.result_sha256=domain.sha(result_text);value.adopted_report_id=ref.report_id
    assert domain.stored_response(value)==response
    value.result_json+=' '
    with pytest.raises(ContractViolation):domain.stored_response(value)


@pytest.mark.parametrize('case',['analysis_id','attempt_id','admission_request_id','fingerprint','ticker','name','date','hash','unit','missing','boolean','naive','gate','report_id'])
def test_result_rejects_without_repair(case):
    value=row();response=envelope(value)
    if case in {'analysis_id','attempt_id','admission_request_id'}:response[case]=str(uuid4())
    elif case=='fingerprint':response[case]='0'*64
    elif case=='ticker':response['payload']['meta']['ticker']='000001'
    elif case=='name':response['payload']['meta']['stock_name']='다른 이름'
    elif case=='date':response['input_snapshot']['confirmed_date']='2099-01-01'
    elif case=='hash':response['input_sha256']='0'*64
    elif case=='unit':response['input_snapshot']['units']=copy.deepcopy(domain.UNITS);response['input_snapshot']['units']['supply']['외국인순매매량']='million_KRW'
    elif case=='missing':del response['input_snapshot']['frames']['supply'][0]['개인']
    elif case=='boolean':response['input_snapshot']['frames']['supply'][0]['개인']=True
    elif case=='naive':response['input_snapshot']['observed_at']='2026-11-08T00:00:00'
    elif case=='gate':response['payload']['verification']['gate2']['passed']=False
    elif case=='report_id':response['report_id']=str(uuid4())
    if case!='hash':response['input_sha256']=domain.sha(domain.canonical(response['input_snapshot']))
    with pytest.raises(ContractViolation):domain.validate_response(value,response,uuid4())


@pytest.mark.asyncio
async def test_AI_gate_token_strict_body_and_injected_engine(monkeypatch):
    calls=[]
    def engine(req,ctx):calls.append(req.analysis_id);return engine_result(req,ctx)
    app=flow_app(engine);wire=domain.ai_request(row());token='synthetic-service-token-at-least-32'
    async with AsyncClient(transport=ASGITransport(app=app),base_url='http://synthetic.invalid') as client:
        monkeypatch.delenv('FLOW_ANALYSIS_ENABLED',raising=False)
        assert (await client.post('/internal/flow/analyze',content=b'x'*9000)).status_code==403
        monkeypatch.setenv('FLOW_ANALYSIS_ENABLED','true');monkeypatch.setenv('FLOW_SERVICE_TOKEN',token)
        assert (await client.post('/internal/flow/analyze',json=wire)).status_code==401
        h={'x-flow-service-token':token,'content-type':'application/json'}
        for raw in (b'x'*8193,b'['*1100+b']'*1100,b'{"x":NaN}',b'{"question":"\xff"}'):
            assert (await client.post('/internal/flow/analyze',content=raw,headers=h)).status_code==422
        for change in ({'as_of':'2026-11-08T09:00:00+09:00'},{'as_of':'2099-01-01T00:00:00Z'},{'schema_version':True},{'spec':{}},{'ticker':'000001'}):
            assert (await client.post('/internal/flow/analyze',json=wire|change,headers=h)).status_code==422
        assert not calls
        response=await client.post('/internal/flow/analyze',json=wire,headers=h)
        assert response.status_code==200 and len(calls)==1
    assert not any(name.startswith(('agents.flow.application','agents.flow.infrastructure.kis_client','agents.flow.infrastructure.llm','_cf012_flow.config','_cf012_flow.application.agent')) for name in sys.modules)


@pytest.mark.asyncio
async def test_total_HTTP_deadline_even_with_active_stream(monkeypatch):
    calls=[];timeouts=[];original=asyncio.timeout
    class Slow(AsyncByteStream):
        async def __aiter__(self):
            while True:
                yield b' '
                await asyncio.sleep(.002)
    def exchange(request):calls.append(request);return Response(200,stream=Slow())
    def timeout(seconds):timeouts.append(seconds);return original(.02)
    monkeypatch.setattr(asyncio,'timeout',timeout)
    client=AIClient('http://synthetic.invalid',125,service_token='x'*32,transport=MockTransport(exchange))
    with pytest.raises(AITimeoutError):await client.analyze_flow(domain.ai_request(row()))
    assert timeouts==[125] and len(calls)==1


@pytest.mark.asyncio
async def test_sync_slot_held_after_response_timeout(monkeypatch):
    flow_app(engine_result)
    from _cf012_flow.api.schemas import FlowAnalysisInput
    from _cf012_flow.application.execution_runtime import FlowExecutionRuntime,EngineUnavailable
    entered=threading.Event();release=threading.Event()
    def blocked(req,ctx):entered.set();release.wait(2);return engine_result(req,ctx)
    runtime=FlowExecutionRuntime(blocked)
    value=row();value.deadline_at=datetime.now(UTC)+timedelta(seconds=.05)
    req=FlowAnalysisInput.model_validate(domain.ai_request(value))
    try:
        with pytest.raises(TimeoutError):await runtime.run(req)
        assert entered.is_set()
        with pytest.raises(EngineUnavailable):await runtime.run(FlowAnalysisInput.model_validate(domain.ai_request(row())))
    finally:release.set()
    await asyncio.sleep(.03)
    assert (await FlowExecutionRuntime(engine_result).run(FlowAnalysisInput.model_validate(domain.ai_request(row()))))['schema_version']==1


@pytest.mark.asyncio
async def test_confirmed_collision_stays_terminal_after_winner_deleted(monkeypatch):
    value=row();response=envelope(value);ref,input_text,result_text=domain.validate_response(value,response,uuid4())
    value.input_json=input_text;value.result_json=result_text;value.input_sha256=domain.sha(input_text);value.result_sha256=domain.sha(result_text);value.adopted_report_id=ref.report_id
    value.owner_user_id=uuid4();value.operation=domain.OPERATION
    session=SimpleNamespace(rollback=AsyncMock(),scalar=AsyncMock(return_value=None),commit=AsyncMock())
    instance=AnalysisService(session,principal=SimpleNamespace(user_id=value.owner_user_id),client=None);instance._locked=AsyncMock(return_value=value)
    monkeypatch.setattr(service.FlowAnalysisAdapter,'stage',AsyncMock(side_effect=FlowReportIdConflict('safe fixed conflict')))
    monkeypatch.setattr(service.report_repository,'get_agent_indexes',AsyncMock(return_value=[]))
    with pytest.raises(AnalysisError) as caught:await instance._publish(value)
    assert caught.value.code==ErrorCode.RESULT_CONFLICT and value.state=='failed'
    session.commit.assert_awaited_once();session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_other_integrity_failure_is_not_confirmed_report_collision(monkeypatch):
    from sqlalchemy.exc import IntegrityError
    value=row();response=envelope(value);ref,a,b=domain.validate_response(value,response,uuid4())
    value.input_json=a;value.result_json=b;value.input_sha256=domain.sha(a);value.result_sha256=domain.sha(b);value.adopted_report_id=ref.report_id
    value.owner_user_id=uuid4();value.operation=domain.OPERATION
    session=SimpleNamespace(rollback=AsyncMock(),scalar=AsyncMock(return_value=None),commit=AsyncMock())
    instance=AnalysisService(session,principal=SimpleNamespace(user_id=value.owner_user_id),client=None);instance._locked=AsyncMock(return_value=value)
    monkeypatch.setattr(service.FlowAnalysisAdapter,'stage',AsyncMock(side_effect=IntegrityError(None,None,ValueError('fixed synthetic'))))
    monkeypatch.setattr(service.report_repository,'get_agent_indexes',AsyncMock(return_value=[]))
    with pytest.raises(AnalysisError) as caught:await instance._publish(value)
    assert caught.value.code==ErrorCode.SERVICE_UNAVAILABLE and value.state=='result_ready'
    session.commit.assert_not_awaited()


def test_source_wiring_caps_and_exact_capture_preserve_integer():
    import ast
    checkout=Path(__file__).resolve().parents[3]
    def source(relative):return (checkout/relative).read_text()
    runtime=source('ai/src/agents/flow/application/execution_runtime.py')
    assert '.itertuples(index=True,name=None)' in runtime and '.iterrows(' not in runtime
    assert 'execution_context=context' in runtime and 'finally:_SLOT.release()' in runtime
    tree=ast.parse(runtime)
    invoke=[node for node in ast.walk(tree) if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='run']
    assert len(invoke)==1 and {k.arg for k in invoke[0].keywords}=={'query','stock_name','ticker','base_date','execution_context'}
    flow_app(engine_result)
    from _cf012_flow.api.schemas import FlowAnalysisInput
    from _cf012_flow.application.execution_runtime import ExecutionContext
    class Mixed:
        columns=['개인','외국인']
        def itertuples(self,*,index,name):
            assert index is True and name is None
            return iter([(datetime(2026,11,5),9007199254740993,0.5)])
    ctx=ExecutionContext(FlowAnalysisInput.model_validate(domain.ai_request(row())))
    ctx.capture(Mixed(),None,None,datetime(2026,11,5).date())
    assert ctx.captured['frames']['supply'][0]['개인']==9007199254740993
