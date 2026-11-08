"""One collected file. Only three explicitly named old regressions are called."""
import ast
import copy
from dataclasses import FrozenInstanceError,replace
from datetime import UTC,datetime,timedelta,timezone
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID,uuid4
import pytest
from src.modules.analysis.domain.contracts import AnalysisContext,AnalysisContractError,FrozenAnalysisResult,StagedReportReference,canonical_json,json_hash,strict_json
from src.modules.analysis.application.ports import AnalysisAdapter
from src.modules.flow.application.analysis_adapter import FlowAnalysisAdapter
from src.modules.auth.application.session_service import Principal,AuthenticationRequired
from examples.analysis import fundamental_adapter as fundamental
from tests.unit.test_flow_contract import test_relocation_public_contract_baseline as _baseline
from tests.unit.test_cf012_flow_analysis import test_confirmed_collision_stays_terminal_after_winner_deleted as _collision
from tests.unit.test_cf012_flow_analysis import test_other_integrity_failure_is_not_confirmed_report_collision as _other_integrity


def test_existing_public_baseline_wrapper(monkeypatch):_baseline(monkeypatch)


async def test_existing_confirmed_collision_wrapper(monkeypatch):await _collision(monkeypatch)


async def test_existing_other_integrity_wrapper(monkeypatch):await _other_integrity(monkeypatch)


def context(operation='example.analysis.v1'):
    return AnalysisContext(UUID('00000000-0000-4000-8000-000000000001'),UUID('00000000-0000-4000-8000-000000000002'),UUID('00000000-0000-4000-8000-000000000003'),UUID('00000000-0000-4000-8000-000000000004'),operation,'0'*64,datetime(2026,11,8,tzinfo=UTC),datetime(2026,11,8,0,2,tzinfo=UTC))


def frozen():return FrozenAnalysisResult.freeze(context=context(),report_id=uuid4(),input_schema='example.input.v1',result_schema='example.result.v1',input_json=canonical_json({'zero':0,'missing':None}),result_json=canonical_json({'zero':0,'added':{'preserve':True}}))


def principal(owner):return Principal(owner,uuid4(),datetime.now(UTC)+timedelta(hours=1),b'x'*32)


def test_context_and_result_are_immutable_and_bound():
    value=frozen();value.validate()
    for target,name,new in ((value,'report_id',uuid4()),(value.context,'owner_user_id',uuid4())):
        with pytest.raises(FrozenInstanceError):setattr(target,name,new)
    for change in ({'report_id':uuid4()},{'context':replace(value.context,attempt_id=uuid4())},{'input_sha256':'1'*64},{'result_json':value.result_json+' '},{'input_schema':'other.v1'}):
        with pytest.raises(AnalysisContractError):replace(value,**change)
    assert strict_json(value.input_json)=={'zero':0,'missing':None}


@pytest.mark.parametrize('text',['{"duplicate":1,"duplicate":2}','{"number":NaN}','{"number":Infinity}','{"number":1e999}','{"text":"\\ud800"}','[]'])
def test_invalid_frozen_JSON_is_rejected(text):
    with pytest.raises(AnalysisContractError):FrozenAnalysisResult.freeze(context=context(),report_id=uuid4(),input_schema='input.v1',result_schema='result.v1',input_json=text,result_json='{}')


@pytest.mark.parametrize('change',[{'owner_user_id':'not-a-UUID'},{'input_fingerprint':'secret-invalid'},{'operation':'bad operation'},{'as_of':datetime(2026,11,8)},{'deadline_at':datetime(2026,11,8,tzinfo=timezone(timedelta(hours=9)))}])
def test_invalid_context_is_rejected(change):
    with pytest.raises(AnalysisContractError):replace(context(),**change)


def _flow_row():
    from src.modules.flow.api.analysis_schemas import AnalysisRequest
    from src.modules.flow.domain import analysis as domain
    request=AnalysisRequest(ticker='005930',question='합성 adapter',as_of='2026-11-08T00:00:00Z',idempotency_key='fixture',allow_analysis=True)
    text=domain.canonical(request.normalized_input())
    return SimpleNamespace(id=uuid4(),attempt_id=uuid4(),admission_request_id=uuid4(),owner_user_id=uuid4(),operation=domain.OPERATION,
        ticker='005930',stock_name='합성 종목',request_json=text,input_fingerprint=domain.sha(text),as_of=request.as_of,
        candidate_date=domain.candidate(request.as_of),deadline_at=datetime.now(UTC)+timedelta(seconds=20),spec_json=domain.canonical(domain.SPEC))


def _flow_envelope(row):
    from scripts.cf012_analysis_check import flow_app,engine_result
    from src.modules.flow.domain import analysis as domain
    flow_app(engine_result)
    from _cf012_flow.api.schemas import FlowAnalysisInput
    request=FlowAnalysisInput.model_validate(domain.ai_request(row));result=engine_result(request,None)
    return dict(schema_version=1,**{k:request.wire()[k] for k in ('analysis_id','attempt_id','admission_request_id','fingerprint')},
        report_id=result['payload']['report_id'],payload=result['payload'],input_snapshot=result['input_snapshot'],input_sha256=domain.sha(domain.canonical(result['input_snapshot'])))


def flow():
    row=_flow_row();row.owner_user_id=uuid4();row.operation='flow.analysis.v1'
    return row,FlowAnalysisAdapter(row,owner_user_id=row.owner_user_id)


def test_Flow_request_validation_and_frozen_bytes_are_original():
    row,adapter=flow();assert isinstance(adapter,AnalysisAdapter)
    from src.modules.flow.domain import analysis as legacy
    response=_flow_envelope(row);original=copy.deepcopy(response)
    assert adapter.build_request()==legacy.ai_request(row)
    ref,a,b=legacy.validate_response(row,response,row.owner_user_id);value=adapter.validate_and_freeze(response)
    assert (value.report_id,value.input_json,value.result_json,value.input_sha256,value.result_sha256)==(ref.report_id,a,b,legacy.sha(a),legacy.sha(b))
    assert response==original
    row.input_json=a;row.result_json=b;row.input_sha256=value.input_sha256;row.result_sha256=value.result_sha256;row.adopted_report_id=ref.report_id
    assert adapter.from_stored(row)==value
    request=adapter.build_request();request['ticker']='changed';assert adapter.build_request()['ticker']=='005930'
    with pytest.raises(FrozenInstanceError):adapter.context=context()


async def test_Flow_stage_uses_same_session_and_owner_no_transaction_control(monkeypatch):
    from src.modules.flow.application import analysis_adapter as module
    row,adapter=flow();value=adapter.validate_and_freeze(_flow_envelope(row));session=SimpleNamespace(commit=AsyncMock(),rollback=AsyncMock())
    staged=AsyncMock(return_value=SimpleNamespace(report_id=value.report_id));instances=[]
    def writer(actual,*,principal):instances.append((actual,principal));return SimpleNamespace(stage_report=staged)
    monkeypatch.setattr(module,'FlowReportService',writer);owner=principal(row.owner_user_id)
    reference=await adapter.stage(session,owner,value)
    assert reference==StagedReportReference(value.report_id,owner.user_id) and instances==[(session,owner)]
    assert staged.call_args.args[0].payload==strict_json(value.result_json)
    session.commit.assert_not_awaited();session.rollback.assert_not_awaited()
    with pytest.raises(AuthenticationRequired):await adapter.stage(session,principal(uuid4()),value)
    assert len(instances)==1
    object.__setattr__(value,'result_json','{}')
    from src.modules.flow.domain.execution import ContractViolation
    with pytest.raises(ContractViolation):await adapter.stage(session,owner,value)
    assert len(instances)==1


def example(writer=None):
    base=context(fundamental.EXAMPLE_OPERATION);ticker,question='005930','합성 재무 연결 예제'
    digest=json_hash(canonical_json(dict(ticker=ticker,question=question,as_of=base.as_of.isoformat())))
    return fundamental.FundamentalExampleAdapter(replace(base,input_fingerprint=digest),ticker,question,writer)


def financial_response():return json.loads((Path(__file__).resolve().parents[2]/'examples/analysis/fundamental-response.v1.json').read_text())


def test_financial_field_mapping_and_raw_extra_zero_null_preservation():
    adapter=example();assert isinstance(adapter,AnalysisAdapter)
    request=adapter.build_request();assert request==dict(request_id='req-'+adapter.context.admission_request_id.hex,trace_id='trace-'+adapter.context.attempt_id.hex,ticker='005930',query='합성 재무 연결 예제')
    assert set(request)=={'request_id','trace_id','ticker','query'}
    response=financial_response();original=copy.deepcopy(response);value=adapter.validate_and_freeze(response)
    assert strict_json(value.result_json)==original and response==original
    assert value.report_id==UUID(response['meta']['erd_payload']['fundamental_report']['id'])
    assert strict_json(value.input_json)==request
    assert value.input_schema=='fundamental.synthetic-request.v1'
    assert original['ratios']=={'synthetic_zero':0,'synthetic_missing':None}
    assert strict_json(value.result_json)['example_extension']['large_integer']==9007199254740993


@pytest.mark.parametrize('field',['request_id','trace_id','ticker','report_id','nonfinite'])
def test_financial_binding_or_finite_failure(field):
    value=financial_response()
    if field=='request_id':value['request_id']='other'
    elif field=='trace_id':value['meta']['trace_id']='other'
    elif field=='ticker':value['ticker']='000001'
    elif field=='report_id':value['meta']['erd_payload']['fundamental_report']['id']='invalid'
    else:value['confidence']=float('nan')
    with pytest.raises(AnalysisContractError):example().validate_and_freeze(value)


async def test_financial_explicit_writer_flush_only_fail_closed_and_owner(monkeypatch):
    writer=AsyncMock();session=SimpleNamespace(flush=AsyncMock(),commit=AsyncMock(),rollback=AsyncMock())
    adapter=example(writer);value=adapter.validate_and_freeze(financial_response());owner=principal(adapter.context.owner_user_id)
    with pytest.raises(fundamental.ExampleWriterUnavailable):await example().stage(session,owner,value)
    validate=AsyncMock();monkeypatch.setattr(fundamental,'validate_principal',validate)
    writer.return_value=StagedReportReference(value.report_id,owner.user_id)
    assert await adapter.stage(session,owner,value)==writer.return_value
    validate.assert_awaited_once_with(session,owner,lock=True);writer.assert_awaited_once_with(session,owner,value);session.flush.assert_awaited_once()
    session.commit.assert_not_awaited();session.rollback.assert_not_awaited()
    with pytest.raises(AuthenticationRequired):await adapter.stage(session,principal(uuid4()),value)
    assert writer.await_count==1
    object.__setattr__(value,'report_id',uuid4())
    with pytest.raises(AnalysisContractError):await adapter.stage(session,owner,value)
    assert writer.await_count==1


def test_neutral_modules_and_unregistered_example_do_not_reverse_import_domains():
    root=Path(__file__).resolve().parents[2]
    for path in ('src/modules/analysis/domain/contracts.py','src/modules/analysis/application/ports.py'):
        tree=ast.parse((root/path).read_text())
        imports=[n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom) and n.module]
        assert not any('flow' in name or 'fundamental' in name or 'config' in name or 'db.' in name for name in imports)
    source=(root/'examples/analysis/fundamental_adapter.py').read_text()
    assert 'FundamentalReportService' not in source and 'create_report' not in source
    facade=(root/'src/modules/flow/application/analysis_service.py').read_text()
    assert 'FlowProfile' in facade and 'AnalysisCoordinator' in facade
    service=(root/'src/modules/analysis/application/coordinator.py').read_text()
    for text in ('adapter.build_request()','adapter.validate_and_freeze(response)','adapter.stage(self.session,self.principal,frozen)'):assert text in service
    assert 'FlowReportIdConflict' in (root/'src/modules/flow/application/analysis_profile.py').read_text() and "row.state='stored'" in service and 'self.session.commit()' in service
