"""CF008 pure/mocked HTTP evidence; actual identity/PG remains the owned checker."""
from datetime import UTC,datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
from httpx import ASGITransport,AsyncClient
from pydantic import ValidationError
from src.modules.flow.api.synthetic_demo_schemas import DemoRequest,DemoRunView,DEMO_PATH,parse_raw,is_demo_endpoint
from src.modules.flow.domain.execution import ErrorCode
from src.modules.flow.domain.input_snapshot import SnapshotError
from src.modules.flow.domain.fake_execution import FakeExecutionError
from src.modules.flow.application import synthetic_demo_service as service


def body(**changes):return dict(idempotency_key='CF008-key',as_of='2026-11-08T09:00:00+09:00',allow_fake=True)|changes


def test_checker_failure_locations_never_expose_exception_or_runtime_source():
 from scripts.cf008_synthetic_demo_check import failure_locations
 namespace={}
 exec(compile('def _verify():\n raise RuntimeError("synthetic credential DSN nonce secret")',failure_locations.__code__.co_filename,'exec'),namespace)
 try:namespace['_verify']()
 except RuntimeError as error:
  frames=failure_locations(error)
  assert frames==[{'source':'synthetic_demo_checker','function':'_verify','line':2}]
  assert not any(word in repr(frames) for word in ('credential','DSN','nonce','secret'))
 try:raise RuntimeError('synthetic other source')
 except RuntimeError as error:assert failure_locations(error)==[]


@pytest.mark.parametrize('change',[{'allow_fake':False},{'allow_fake':1},{'allow_fake':'true'},{'allow_fake':None},{'owner_user_id':str(uuid4())},{'ticker':'000660'},{'as_of':1},{'as_of':'2026-11-08'},{'idempotency_key':'x'*257},{'idempotency_key':'\0'},{'idempotency_key':'\ud800'}])
def test_exact_optin_and_reused_admission_limits(change):
 with pytest.raises(ValidationError):DemoRequest.model_validate(body(**change))


@pytest.mark.parametrize('raw',[b'{}',b'[]',b'{"idempotency_key":"x","idempotency_key":"y","as_of":"2026-11-08T00:00:00Z","allow_fake":true}',b'{"x":NaN}',b'null'])
def test_strict_bounded_raw_json(raw):
 with pytest.raises((ValueError,UnicodeError)):parse_raw(raw)


def test_normalization_and_exact_paths():
 request=DemoRequest.model_validate(body());assert request.as_of==datetime(2026,11,8,tzinfo=UTC)
 assert request.admission().ticker=='005930' and request.admission().question=='Flow 합성 데모 v1'
 assert is_demo_endpoint('POST',DEMO_PATH) and is_demo_endpoint('GET',DEMO_PATH+'/'+str(uuid4()))
 for method,path in [('GET',DEMO_PATH),('POST',DEMO_PATH+'/'),('DELETE',DEMO_PATH+'/x'),('GET',DEMO_PATH+'/x/y')]:assert not is_demo_endpoint(method,path)


def view():
 return dict(run_id=uuid4(),request_id=uuid4(),attempt_id=uuid4(),input_snapshot_id=None,execution_id=None,stage='admitted',deadline_at=None,finished_at=None,result_stored=False,result=None,result_sha256=None,failure_code=None)


@pytest.mark.parametrize('change',[{'version':True},{'synthetic':1},{'result_stored':0},{'stage':'running'},{'input_snapshot_id':uuid4()},{'result':{}},{'failure_code':'fake_failed'},{'execution_id':uuid4()}])
def test_view_rejects_contradictions(change):
 with pytest.raises(ValidationError):DemoRunView.model_validate(view()|change)


async def test_default_off_precedes_receive_dependencies_and_engine(monkeypatch):
 from src.api.main import app
 from src.shared.config import settings
 from src.modules.flow.api.synthetic_demo_router import demo_service
 monkeypatch.setattr(settings,'FLOW_SYNTHETIC_DEMO_ENABLED',False)
 calls=[]
 async def forbidden():calls.append('dependency');raise AssertionError('off dependency')
 async def streamed():calls.append('body');yield b'forbidden'
 original=dict(app.dependency_overrides);app.dependency_overrides[demo_service]=forbidden
 try:
  async with AsyncClient(transport=ASGITransport(app=app),base_url='http://localhost:8200') as client:
   response=await client.post(DEMO_PATH,content=streamed(),headers={'content-type':'application/json','x-request-id':str(uuid4())})
   assert response.status_code==403 and response.json()['error']['code']=='FEATURE_UNAVAILABLE' and response.json()['data'] is None
   assert response.headers['cache-control']=='private, no-store' and set(response.headers['vary'].lower().replace(' ','').split(','))=={'cookie','origin'}
  assert not calls
 finally:app.dependency_overrides.clear();app.dependency_overrides.update(original)


@pytest.mark.parametrize('raw,headers',[(b'{"x":NaN}',{'content-type':'application/json'}),(b'{}',{'content-type':'text/plain'}),(b'{}',{'content-type':'application/json','content-encoding':'gzip'})])
async def test_invalid_raw_before_dependency(monkeypatch,raw,headers):
 from src.api.main import app
 from src.shared.config import settings
 from src.modules.auth.api import router as auth
 from src.modules.flow.api.synthetic_demo_router import demo_service
 monkeypatch.setattr(settings,'FLOW_SYNTHETIC_DEMO_ENABLED',True);monkeypatch.setattr(auth,'configured',lambda:True)
 dependency=AsyncMock(side_effect=AssertionError('invalid body dependency'))
 previous=dict(app.dependency_overrides);app.dependency_overrides[demo_service]=dependency
 try:
  async with AsyncClient(transport=ASGITransport(app=app),base_url='http://localhost:8200') as client:
   result=await client.post(DEMO_PATH,content=raw,headers=headers)
   assert result.status_code==422 and result.json()['error']['code']=='INPUT_INVALID'
  dependency.assert_not_awaited()
 finally:app.dependency_overrides.clear();app.dependency_overrides.update(previous)


async def test_sequential_commits_partial_failure_location_and_no_nested_transaction(monkeypatch):
 order=[];state=SimpleNamespace(run_id=uuid4(),request_id=uuid4(),attempt_id=uuid4());seal=SimpleNamespace(id=uuid4())
 async def admit(*args):order.append('admit_committed');return state
 async def prepare(*args):order.append('prepare_committed');raise SnapshotError('unavailable')
 run=SimpleNamespace(admit=admit);prep=SimpleNamespace(prepare=prepare);fake=SimpleNamespace(execute_once=AsyncMock())
 monkeypatch.setattr(service,'FlowRunService',lambda *a,**k:run);monkeypatch.setattr(service,'InputPreparationService',lambda *a,**k:prep);monkeypatch.setattr(service,'FakeExecutionService',lambda *a,**k:fake)
 with pytest.raises(service.DemoError) as caught:await service.SyntheticDemoService(object(),principal=object()).post(DemoRequest.model_validate(body()),uuid4())
 assert caught.value.code==ErrorCode.SERVICE_UNAVAILABLE and caught.value.run_id==state.run_id
 assert order==['admit_committed','prepare_committed'];fake.execute_once.assert_not_awaited()


@pytest.mark.parametrize('fixture,execution_exists',[('flow.synthetic.short4',False),('flow.synthetic.short4',True)])
async def test_same_marker_short_fixture_is_not_a_web_demo(monkeypatch,fixture,execution_exists):
 state=SimpleNamespace(run_id=uuid4(),request_id=uuid4(),attempt_id=uuid4());principal=SimpleNamespace(user_id=uuid4())
 from tests.unit.test_cf006_flow_input_snapshot import row
 source=row();source.id=state.run_id;source.owner_user_id=principal.user_id;source.request_input['question']='Flow 합성 데모 v1'
 from src.modules.flow.api.run_schemas import FlowAdmissionRequest
 req=FlowAdmissionRequest(**source.request_input,idempotency_key='unit');source.input_fingerprint=req.input_fingerprint()
 seal=SimpleNamespace(id=uuid4(),body={'fixture':{'id':fixture,'version':1}})
 fake=SimpleNamespace(get=AsyncMock(return_value=object() if execution_exists else None))
 monkeypatch.setattr(service,'FlowRunService',lambda *a,**k:SimpleNamespace(get=AsyncMock(return_value=state)))
 monkeypatch.setattr(service,'get_owned',AsyncMock(return_value=source));monkeypatch.setattr(service,'InputPreparationService',lambda *a,**k:SimpleNamespace(get=AsyncMock(return_value=seal)));monkeypatch.setattr(service,'FakeExecutionService',lambda *a,**k:fake)
 with pytest.raises(service.DemoError) as caught:await service.SyntheticDemoService(object(),principal=principal).get(state.run_id)
 assert caught.value.code==ErrorCode.RESOURCE_NOT_FOUND;fake.get.assert_not_awaited()


@pytest.mark.parametrize('code,expected',[('corrupt',ErrorCode.RESULT_CONTRACT_INVALID),('unavailable',ErrorCode.SERVICE_UNAVAILABLE),('auth_required',ErrorCode.AUTH_REQUIRED)])
async def test_get_does_not_hide_errors_as_preparing(monkeypatch,code,expected):
 from tests.unit.test_cf006_flow_input_snapshot import row
 source=row();source.request_input['question']='Flow 합성 데모 v1'
 from src.modules.flow.api.run_schemas import FlowAdmissionRequest
 source.input_fingerprint=FlowAdmissionRequest(**source.request_input,idempotency_key='unit').input_fingerprint()
 state=SimpleNamespace(run_id=source.id,request_id=source.admission_request_id,attempt_id=source.attempt_id)
 monkeypatch.setattr(service,'FlowRunService',lambda *a,**k:SimpleNamespace(get=AsyncMock(return_value=state)))
 monkeypatch.setattr(service,'get_owned',AsyncMock(return_value=source));monkeypatch.setattr(service,'InputPreparationService',lambda *a,**k:SimpleNamespace(get=AsyncMock(side_effect=SnapshotError(code))))
 with pytest.raises(service.DemoError) as caught:await service.SyntheticDemoService(object(),principal=SimpleNamespace(user_id=source.owner_user_id)).get(source.id)
 assert caught.value.code==expected


async def test_successful_handler_teardown_failure_returns_private_503(monkeypatch):
 from src.api.main import app
 from src.shared.config import settings
 from src.modules.auth.api import router as auth
 from src.modules.flow.api import synthetic_demo_router as routes
 from db.session import get_session
 monkeypatch.setattr(settings,'FLOW_SYNTHETIC_DEMO_ENABLED',True);monkeypatch.setattr(auth,'configured',lambda:True)
 monkeypatch.setattr(routes,'request_principal',AsyncMock(return_value=object()))
 result=DemoRunView.model_validate(view())
 monkeypatch.setattr(routes,'SyntheticDemoService',lambda *a,**k:SimpleNamespace(get=AsyncMock(return_value=result)))
 async def broken():
  yield object()
  raise OSError('synthetic-sensitive-teardown')
 previous=dict(app.dependency_overrides);app.dependency_overrides[get_session]=broken
 try:
  async with AsyncClient(transport=ASGITransport(app=app),base_url='http://localhost:8200') as client:
   response=await client.get(DEMO_PATH+'/'+str(result.run_id))
   assert response.status_code==503 and response.json()['data'] is None
   assert response.json()['error']['code']=='SERVICE_UNAVAILABLE' and response.headers['cache-control']=='private, no-store'
   assert 'synthetic-sensitive-teardown' not in response.text
 finally:app.dependency_overrides.clear();app.dependency_overrides.update(previous)


@pytest.mark.parametrize('declared',[None,'1'])
@pytest.mark.parametrize('size',[4096,4097])
async def test_valid_JSON_stream_exact_byte_boundary(monkeypatch,declared,size):
 import json
 from src.api.main import app
 from src.shared.config import settings
 from src.modules.auth.api import router as auth
 from src.modules.flow.api.synthetic_demo_router import demo_service
 monkeypatch.setattr(settings,'FLOW_SYNTHETIC_DEMO_ENABLED',True);monkeypatch.setattr(auth,'configured',lambda:True)
 result=DemoRunView.model_validate(view());post=AsyncMock(return_value=result)
 async def dependency():return SimpleNamespace(post=post)
 previous=dict(app.dependency_overrides);app.dependency_overrides[demo_service]=dependency
 raw=json.dumps(body()).encode();raw+=b' '*(size-len(raw))
 async def chunks():
  for piece in (raw[:2000],raw[2000:4095],raw[4095:4096],raw[4096:]):
   if piece:yield piece
 headers={'content-type':'application/json'}
 if declared is not None:headers['content-length']=declared
 try:
  async with AsyncClient(transport=ASGITransport(app=app),base_url='http://localhost:8200') as client:
   response=await client.post(DEMO_PATH,content=chunks(),headers=headers)
  assert response.status_code==(202 if size==4096 else 422)
  assert post.await_count==(1 if size==4096 else 0)
 finally:app.dependency_overrides.clear();app.dependency_overrides.update(previous)


async def test_invalid_UTF8_inside_otherwise_valid_key_is_not_replacement_decoded(monkeypatch):
 from src.api.main import app
 from src.shared.config import settings
 from src.modules.auth.api import router as auth
 from src.modules.flow.api.synthetic_demo_router import demo_service
 monkeypatch.setattr(settings,'FLOW_SYNTHETIC_DEMO_ENABLED',True);monkeypatch.setattr(auth,'configured',lambda:True)
 calls=[]
 async def forbidden():calls.append(True);raise AssertionError('invalid UTF8 dependency')
 previous=dict(app.dependency_overrides);app.dependency_overrides[demo_service]=forbidden
 raw=b'{"idempotency_key":"valid-\xff-key","as_of":"2026-11-08T00:00:00Z","allow_fake":true}'
 try:
  async with AsyncClient(transport=ASGITransport(app=app),base_url='http://localhost:8200') as client:
   response=await client.post(DEMO_PATH,content=raw,headers={'content-type':'application/json'})
  assert response.status_code==422 and not calls
 finally:app.dependency_overrides.clear();app.dependency_overrides.update(previous)
