"""New default-off demo ASGI/owned-PG round, without repeating older PG suites."""
import asyncio
import hashlib
import json
import secrets
import time
from datetime import timedelta
from unittest.mock import patch
from uuid import UUID,uuid4
from scripts.cf003_admission_check import check,isolated_application


def failure_locations(error):
 """Only fixed checker source/function aliases and line numbers, never text/locals."""
 frames=[];trace=error.__traceback__
 while trace is not None:
  code=trace.tb_frame.f_code
  if code.co_filename==failure_locations.__code__.co_filename and code.co_name in {'verify_synthetic_demo','_verify','response','wait_lock','stored_bytes','internal','call'}:
   frames.append({'source':'synthetic_demo_checker','function':code.co_name,'line':trace.tb_lineno})
  trace=trace.tb_next
 return frames[-8:]


async def verify_synthetic_demo(proof):
 with isolated_application(proof) as observed:
  try:result=await _verify(proof)
  except Exception as error:
   from scripts.cf002_interactive_login import safe_print
   safe_print({'phase':'cf008_checker_failure_locations','frames':failure_locations(error)})
   raise
  check(not any(observed.values()),'CF008 unexpected forbidden access')
  result['observed_denials']=dict(observed);result['observation_scope']='scoped-Python-file-socket-httpx-not-native-tracing'
  return result


async def _verify(proof):
 import httpx
 from sqlalchemy import func,insert,select,text,update
 from db.models.auth.models import AuthUser,AuthSession
 from db.models.flow.flow_run import FlowRun
 from db.models.flow.input_snapshot import FlowInputSnapshot
 from db.models.flow.fake_execution import FlowFakeExecution
 from db.session import get_session
 from scripts.cf002_interactive_login import owned_session,safe_print
 from src.api.main import app
 from src.shared.config import settings
 from src.modules.auth.api import router as auth
 from src.modules.auth.application.session_service import issue_session,csrf_token,revoke_session
 from src.modules.flow.api.synthetic_demo_schemas import DEMO_PATH,QUESTION,TICKER
 from src.modules.flow.api.run_schemas import FlowAdmissionRequest
 from src.modules.flow.application.run_service import FlowRunService
 from src.modules.flow.application.input_preparation_service import InputPreparationService
 from src.modules.flow.application.fake_execution_service import FakeExecutionService
 from src.modules.flow.application import fake_execution_service as execution_module
 from src.modules.flow.domain import fake_execution as engine_domain
 from src.modules.flow.domain.input_snapshot import SnapshotError
 from src.modules.flow.domain.fake_execution import FakeExecutionError

 groups=[];rejections=0;calls={};behavior='normal';dep_calls=0;commit_mode=None;race_pids=[];race_ready=asyncio.Event();race_collect=False
 def phase(label):safe_print({'phase':'cf008_check','label':label,'status':'started'})
 def mark(label):groups.append(label);safe_print({'phase':'cf008_check','label':label,'status':'passed'})
 async def scalar(statement,params=None):
  async with owned_session(proof) as session:return await session.scalar(text(statement),params or {})
 async def counts():return tuple([await scalar('SELECT count(*) FROM '+table) for table in ('flow_runs','flow_input_snapshots','flow_fake_executions','flow_reports','agent_reports','stocks')])
 async def counted(seal,identity):
  calls[identity]=calls.get(identity,0)+1;check(calls[identity]==1,'CF008 engine max1')
  if behavior=='error':raise RuntimeError('synthetic fake failure')
  if behavior=='timeout':await asyncio.Event().wait()
  return await engine_domain.fake_engine(seal,identity)
 async def request_session():
  nonlocal dep_calls
  dep_calls+=1
  async with owned_session(proof) as session:
   if race_collect:
    race_pids.append(await session.scalar(text('SELECT pg_backend_pid()')))
    if len(race_pids)==2:race_ready.set()
   original=session.commit;n=0;mode=commit_mode
   async def commit():
    nonlocal n
    n+=1
    if mode is not None and n==mode[0]:
     if mode[1]=='ack':await original()
     raise OSError('synthetic commit failure')
    await original()
   session.commit=commit
   yield session
 async def call(method,path=DEMO_PATH,*,body=None,raw=None,token=None,principal=None,headers=None,transport=None):
  headers={'origin':'http://localhost:3200','cookie':auth.SESSION_COOKIE+'='+(ta if token is None else token),'x-csrf-token':csrf_token(pa if principal is None else principal)}|(headers or {})
  async with httpx.AsyncClient(transport=transport or httpx.ASGITransport(app=app),base_url='http://localhost:8200') as client:
   return await client.request(method,path,json=body,content=raw,headers=headers)
 async def stored_bytes(run_id):
  async with owned_session(proof) as session:
   row=(await session.execute(text('SELECT row_to_json(r)::text,s.input_json,s.input_sha256,e.result_json,e.result_sha256 FROM flow_runs r JOIN flow_input_snapshots s ON s.run_id=r.id JOIN flow_fake_executions e ON e.input_snapshot_id=s.id WHERE r.id=:id'),{'id':run_id})).one()
   return tuple(row)
 def body(key=None,**change):return dict(idempotency_key=str(uuid4()) if key is None else key,as_of='2026-11-08T00:00:00Z',allow_fake=True)|change
 def response(value,status,code=None):
  nonlocal rejections
  check(value.status_code==status,'CF008 status')
  vary={s.strip().lower() for s in value.headers.get('vary','').split(',')}
  check(value.headers.get('cache-control')=='private, no-store' and vary=={'cookie','origin'},'CF008 private headers')
  result=value.json();UUID(result['request_id']);check(set(result)=={'request_id','data','error'},'CF008 envelope')
  if code is not None:check(result['data'] is None and result['error']['code']==code,'CF008 fixed error');rejections+=1
  else:check(result['error'] is None and result['data']['mode']=='synthetic_demo','CF008 demo data')
  return result['data']
 async def internal(request,fixture=None):
  async with owned_session(proof) as session:
   run=await FlowRunService(session,principal=pa).admit(request,uuid4())
   seal=None if fixture is None else await InputPreparationService(session,principal=pa).prepare(run.run_id,fixture)
   return run,seal
 async def wait_lock(pid):
  deadline=time.monotonic()+12
  while time.monotonic()<deadline:
   if await scalar('SELECT wait_event_type FROM pg_stat_activity WHERE pid=:pid',{'pid':pid})=='Lock':return
   await asyncio.sleep(.02)
  raise RuntimeError('CF008 expected owned lock wait')

 check(await scalar('SELECT version_num FROM alembic_version')=='c7001a7e0001','CF008 exact head')
 async with owned_session(proof) as session:
  a,b=AuthUser(id=uuid4()),AuthUser(id=uuid4());session.add_all([a,b]);await session.flush()
  ta,pa=await issue_session(session,a);ta2,pa2=await issue_session(session,a);tb,pb=await issue_session(session,b)
  te,pe=await issue_session(session,a);tr,pr=await issue_session(session,a)
  await session.execute(update(AuthSession).where(AuthSession.id==pe.session_id).values(created_at=func.clock_timestamp()-text("interval '2 hours'"),expires_at=func.clock_timestamp()-text("interval '1 hour'")))
  await session.commit();await revoke_session(session,pr)
 previous=dict(app.dependency_overrides);app.dependency_overrides[get_session]=request_session
 old_gate=settings.FLOW_SYNTHETIC_DEMO_ENABLED;old_admission=settings.FLOW_RUN_ADMISSION_ENABLED
 try:
  with patch.object(execution_module,'fake_engine',counted):
   phase('default_off_before_body_or_dependencies')
   settings.FLOW_SYNTHETIC_DEMO_ENABLED=False;settings.FLOW_RUN_ADMISSION_ENABLED=False
   touched=[]
   async def stream():touched.append(True);yield b'x'*5000
   before=await counts();response(await call('POST',raw=stream(),headers={'content-type':'application/json'}),403,'FEATURE_UNAVAILABLE')
   check(not touched and dep_calls==0 and not calls and await counts()==before,'CF008 off zero side effects')
   settings.FLOW_SYNTHETIC_DEMO_ENABLED=True
   with patch.object(auth,'configured',lambda:False):response(await call('POST',raw=stream(),headers={'content-type':'application/json'}),401,'AUTH_REQUIRED')
   check(not touched and dep_calls==0,'CF008 unconfigured zero dependencies')
   check((await call('POST','/api/flow/runs',body={})).status_code==403,'CF008 admission gate remains independent')
   mark('default_off_unconfigured_body_dependency_engine_zero_independent_gate')

   phase('strict_body_and_auth')
   for raw,headers in [(b'{"x":NaN}',{'content-type':'application/json'}),(b'{}',{'content-type':'text/plain'}),(b'{}',{'content-type':'application/json','content-encoding':'gzip'})]:response(await call('POST',raw=raw,headers=headers),422,'INPUT_INVALID')
   for declared in (None,'1'):
    for size in (4096,4097):
     raw=json.dumps(body()).encode();raw+=b' '*(size-len(raw))
     async def bounded_stream(raw=raw):
      for part in (raw[:2000],raw[2000:4095],raw[4095:4096],raw[4096:]):
       if part:yield part
     headers={'content-type':'application/json'}
     if declared is not None:headers['content-length']=declared
     if size==4096:
      # A prepared-only result proves valid JSON reached the application, while
      # avoiding an engine invocation in this byte-boundary case.
      with patch.object(FakeExecutionService,'execute_once',side_effect=FakeExecutionError('unavailable')):
       result=await call('POST',raw=bounded_stream(),headers=headers);response(result,503,'SERVICE_UNAVAILABLE')
      check(result.headers.get('location','').startswith(DEMO_PATH+'/'),'CF008 exact4096 JSON admitted')
     else:
      old_counts=await counts();old_dep=dep_calls
      response(await call('POST',raw=bounded_stream(),headers=headers),422,'INPUT_INVALID')
      check(await counts()==old_counts and dep_calls==old_dep,'CF008 exact4097 denied before dependency')
   before=await counts()
   invalid_utf8=b'{"idempotency_key":"valid-\xff-key","as_of":"2026-11-08T00:00:00Z","allow_fake":true}'
   response(await call('POST',raw=invalid_utf8,headers={'content-type':'application/json'}),422,'INPUT_INVALID')
   duplicate=b'{"idempotency_key":"x","idempotency_key":"y","as_of":"2026-11-08T00:00:00Z","allow_fake":true}'
   response(await call('POST',raw=duplicate,headers={'content-type':'application/json'}),422,'INPUT_INVALID')
   for change in ({'allow_fake':False},{'allow_fake':1},{'owner_user_id':str(pa.user_id)},{'as_of':1}):response(await call('POST',body=body(**change)),422,'INPUT_INVALID')
   for token,principal in ((te,pe),(tr,pr)):response(await call('POST',body=body(),token=token,principal=principal),401,'AUTH_REQUIRED')
   response(await call('POST',body=body(),headers={'cookie':auth.SESSION_COOKIE+'='+ta+'; '+auth.SESSION_COOKIE+'='+tb}),401,'AUTH_REQUIRED')
   # Existing request_principal/verify_csrf rejects CSRF/Origin as authentication
   # failures; the distinct local Host guard remains HTTP 403.
   for headers in ({'x-csrf-token':'bad'},{'origin':'https://other.invalid'}):response(await call('POST',body=body(),headers=headers),401,'AUTH_REQUIRED')
   response(await call('POST',body=body(),headers={'host':'127.0.0.1:8200'}),403,'AUTH_REQUEST_INVALID')
   response(await call('GET',DEMO_PATH+'/'+str(uuid4())+'?owner=other'),422,'INPUT_INVALID')
   check(await counts()==before and not calls,'CF008 invalid writes calls zero')
   mark('actual_session_CSRF_Origin_Host_duplicate_cookie_and_bounded_strict_JSON')

   phase('post_store_owner_get_replay')
   request=body();first=response(await call('POST',body=request),200);run=UUID(first['run_id'])
   check(first['stage']=='succeeded' and first['result_stored'] is True and first['result']['totals']['foreign']==800000 and first['result']['totals']['trading_value']==20000000,'CF008 stored summary values')
   preserved_bytes=await stored_bytes(run)
   state=await counts();seen=sum(calls.values())
   check(response(await call('POST',body=request,token=ta2,principal=pa2),200)==first,'CF008 second session replay')
   check(response(await call('GET',DEMO_PATH+'/'+str(run),token=ta2,principal=pa2),200)==first,'CF008 independent owner read')
   check(await counts()==state and sum(calls.values())==seen,'CF008 replay/read create nothing')
   response(await call('POST',body=body(request['idempotency_key'],as_of='2026-11-09T00:00:00Z')),409,'IDEMPOTENCY_CONFLICT')
   response(await call('GET',DEMO_PATH+'/'+str(run),token=tb,principal=pb),404,'RESOURCE_NOT_FOUND');response(await call('GET',DEMO_PATH+'/'+str(uuid4()),token=tb,principal=pb),404,'RESOURCE_NOT_FOUND')
   mark('POST_full20_atomic_artifact_owner_GET_same_key_replay_and_conflict')

   phase('partial_commits_and_HTTP_loss')
   for stopped in ('admit','prepare'):
    request=body()
    target=patch.object(InputPreparationService,'prepare',side_effect=SnapshotError('unavailable')) if stopped=='admit' else patch.object(FakeExecutionService,'execute_once',side_effect=FakeExecutionError('unavailable'))
    with target:
     failed=await call('POST',body=request);response(failed,503,'SERVICE_UNAVAILABLE')
    location=failed.headers.get('location');check(location is not None and location.startswith(DEMO_PATH+'/'),'CF008 committed ID only Location')
    stable=await counts();seen=sum(calls.values());data=response(await call('GET',location),200)
    check(data['stage']==('admitted' if stopped=='admit' else 'prepared') and await counts()==stable and sum(calls.values())==seen,'CF008 GET does not advance partial stages')
    recovered=response(await call('POST',body=request),200);check(recovered['run_id']==data['run_id'] and recovered['stage']=='succeeded','CF008 explicit replay resumes')
   for number in (3,4):
    request=body();prior=sum(calls.values());commit_mode=(number,'ack')
    try:failed=await call('POST',body=request);response(failed,503,'SERVICE_UNAVAILABLE')
    finally:commit_mode=None
    recovered=response(await call('POST',body=request),202 if number==3 else 200)
    check(recovered['stage']==('running' if number==3 else 'succeeded') and sum(calls.values())==prior+(0 if number==3 else 1),'CF008 ACK recovery no engine recall')
   class LostResponse(httpx.ASGITransport):
    async def handle_async_request(self,request):
     result=await super().handle_async_request(request);await result.aclose();raise OSError('synthetic response loss')
   request=body()
   try:await call('POST',body=request,transport=LostResponse(app=app))
   except OSError:pass
   else:raise RuntimeError('CF008 expected synthetic HTTP loss')
   prior=sum(calls.values());check(response(await call('POST',body=request),200)['stage']=='succeeded' and sum(calls.values())==prior,'CF008 response loss original result')
   for mode,stage in (('error','failed'),('timeout','timed_out')):
    behavior=mode;request=body();result=response(await call('POST',body=request),200);check(result['stage']==stage and not result['result_stored'] and result['result'] is None,'CF008 terminal failure data')
    behavior='normal';prior=sum(calls.values());check(response(await call('POST',body=request),200)==result and sum(calls.values())==prior,'CF008 failed request cannot rerun')
   mark('admit_prepare_partial_commit_ACK_HTTP_loss_and_failure_replay')

   phase('concurrent_same_POST')
   request=body();dto=FlowAdmissionRequest(ticker=TICKER,question=QUESTION,as_of=request['as_of'],idempotency_key=request['idempotency_key'])
   prior_run,_=await internal(dto)
   race_collect=True;tasks=[]
   try:
    async with owned_session(proof) as blocker:
     await blocker.execute(select(FlowRun).where(FlowRun.id==prior_run.run_id).with_for_update())
     tasks=[asyncio.create_task(call('POST',body=request)),asyncio.create_task(call('POST',body=request,token=ta2,principal=pa2))]
     await asyncio.wait_for(race_ready.wait(),15);await asyncio.gather(*(wait_lock(pid) for pid in race_pids));await blocker.commit()
    values=await asyncio.wait_for(asyncio.gather(*tasks),20);race_collect=False;data=[response(v,v.status_code) for v in values]
    check(data[0]['run_id']==data[1]['run_id'] and data[0]['execution_id']==data[1]['execution_id'],'CF008 same POST stable IDs')
    stored=response(await call('GET',DEMO_PATH+'/'+str(prior_run.run_id)),200);check(stored['stage']=='succeeded' and calls[UUID(stored['execution_id'])]==1,'CF008 concurrent max1')
   finally:
    race_collect=False
    for task in tasks:
     if not task.done():task.cancel()
    if tasks:await asyncio.gather(*tasks,return_exceptions=True)
   mark('barrier_same_POST_one_run_seal_execution_engine')

   phase('GET_classification_corruption_and_expiry')
   normal,_=await internal(FlowAdmissionRequest(ticker=TICKER,question='not a demo',as_of=request['as_of'],idempotency_key=str(uuid4())),'flow.synthetic.full20')
   response(await call('GET',DEMO_PATH+'/'+str(normal.run_id)),404,'RESOURCE_NOT_FOUND')
   for terminal in (False,True):
    short,_=await internal(FlowAdmissionRequest(ticker=TICKER,question=QUESTION,as_of=request['as_of'],idempotency_key=str(uuid4())),'flow.synthetic.short4')
    if terminal:
     async with owned_session(proof) as session:await FakeExecutionService(session,principal=pa).execute_once(short.run_id,allow_fake=True)
    response(await call('GET',DEMO_PATH+'/'+str(short.run_id)),404,'RESOURCE_NOT_FOUND')
   expired,seal=await internal(FlowAdmissionRequest(ticker=TICKER,question=QUESTION,as_of=request['as_of'],idempotency_key=str(uuid4())),'flow.synthetic.full20')
   async with owned_session(proof) as session:
    stamp=await session.scalar(text("SELECT clock_timestamp()-interval '20 seconds'"))
    session.add(FlowFakeExecution(id=uuid4(),input_snapshot_id=seal.id,contract_version=1,engine_id=engine_domain.ENGINE_ID,claim_digest=hashlib.sha256(secrets.token_bytes(32)).digest(),status='running',started_at=stamp,deadline_at=stamp+timedelta(seconds=10)));await session.commit()
   state=await counts();prior=sum(calls.values());data=response(await call('GET',DEMO_PATH+'/'+str(expired.run_id)),200)
   check(data['stage']=='timed_out' and data['failure_code']=='deadline_expired' and await counts()==state and sum(calls.values())==prior,'CF008 GET only expiry no row creation')
   async with owned_session(proof) as session:
    source=await session.get(FlowRun,run);old=source.input_fingerprint;await session.execute(update(FlowRun).where(FlowRun.id==run).values(input_fingerprint='0'*64));await session.commit()
   response(await call('GET',DEMO_PATH+'/'+str(run)),502,'RESULT_CONTRACT_INVALID')
   async with owned_session(proof) as session:await session.execute(update(FlowRun).where(FlowRun.id==run).values(input_fingerprint=old));await session.commit()
   commit_mode=(1,'before')
   try:response(await call('GET',DEMO_PATH+'/'+str(run)),503,'SERVICE_UNAVAILABLE')
   finally:commit_mode=None
   check((await call('POST','/api/supervisor/analyze',body={})).status_code==403,'CF008 old analyze remains closed')
   check(await stored_bytes(run)==preserved_bytes,'CF008 original receipt input result bytes unchanged')
   check((await counts())[3:]==before[3:] and all(n==1 for n in calls.values()),'CF008 report index stock untouched and max1')
   mark('non_demo_short4_closed_corrupt_unavailable_distinct_and_owner_GET_expiry_only')
   return {'status':'passed','groups':groups,'rejections':rejections,'engine_invocations':sum(calls.values()),'distinct_invoked_execution_ids':len(calls),'max_calls_per_execution':max(calls.values(),default=0)}
 finally:
  app.dependency_overrides.clear();app.dependency_overrides.update(previous)
  settings.FLOW_SYNTHETIC_DEMO_ENABLED=old_gate;settings.FLOW_RUN_ADMISSION_ENABLED=old_admission
