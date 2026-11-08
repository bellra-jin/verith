"""One bounded CF007 owned-PG round; no nested CF003/CF006 suite or provider IO."""
import asyncio
from contextlib import ExitStack
from dataclasses import replace
from datetime import timedelta
import hashlib
import json
import secrets
import time
from unittest.mock import patch
from uuid import UUID, uuid4
from scripts.cf003_admission_check import check, isolated_application


class FakeDDLFailure(RuntimeError):
    pass


async def migration(proof, target, *, fail=False):
    from sqlalchemy import event
    from sqlalchemy.ext.asyncio import create_async_engine
    from alembic import command
    from alembic.config import Config
    from scripts.cf002_interactive_login import _BACKEND
    check(target in {"c6001a7e0001", "c7001a7e0001"}, "CF007 exact revision")
    await proof.preflight()
    engine=create_async_engine(proof.url,connect_args=proof.connection_parameters())
    try:
        async with engine.connect() as connection:
            await proof.attest_connection(connection)
            def apply(sync):
                def hook(conn,cursor,statement,params,context,many):
                    if fail and statement.lstrip().upper().startswith("CREATE TABLE FLOW_FAKE_EXECUTIONS"):
                        raise FakeDDLFailure("CF007 post CREATE injection")
                config=Config(str(_BACKEND/'alembic.ini'));config.set_main_option('script_location',str(_BACKEND/'db/migrations'))
                config.attributes.update(connection=sync,verified_test_mode=True)
                event.listen(sync,'after_cursor_execute',hook)
                try:(command.downgrade if target=='c6001a7e0001' else command.upgrade)(config,target)
                finally:event.remove(sync,'after_cursor_execute',hook)
            try:await connection.run_sync(apply);await connection.commit()
            except Exception:await connection.rollback();raise
    finally:await engine.dispose()


async def verify_fake_execution(proof):
    with isolated_application(proof) as observed:
        result=await _verify(proof)
        check(not any(observed.values()),'CF007 unexpected forbidden access')
        result['observed_denials']=dict(observed)
        result['observation_scope']='scoped-Python-file-socket-httpx-wrappers-not-native-tracing'
        return result


async def _verify(proof):
    import httpx
    from sqlalchemy import func, insert, select, text, update
    from sqlalchemy.exc import DBAPIError
    from db.models.auth.models import AuthUser,AuthSession
    from db.models.flow.flow_run import FlowRun
    from db.models.flow.flow_report import FlowReport
    from db.models.flow.input_snapshot import FlowInputSnapshot
    from db.models.flow.fake_execution import FlowFakeExecution
    from db.session import get_session
    from scripts.cf002_interactive_login import owned_session,safe_print
    from src.api.main import app
    from src.modules.auth.api.router import SESSION_COOKIE
    from src.modules.auth.application.session_service import issue_session,authenticate,csrf_token,revoke_session
    from src.modules.flow.application.run_service import FlowRunService
    from src.modules.flow.api.run_schemas import FlowAdmissionRequest
    from src.modules.flow.application.input_preparation_service import InputPreparationService
    from src.modules.flow.application.report_service import FlowReportService
    from src.modules.flow.api.schemas import FlowReportSaveRequest
    from src.modules.flow.application import fake_execution_service as service
    from src.modules.flow.domain import fake_execution as domain
    from src.modules.flow.infrastructure import fake_execution_repository as repository
    from src.modules.flow.domain.input_snapshot import read_seal
    from tests.fixtures.flow_payload import make_flow_payload

    groups=[];rejects=[];calls={};behavior='normal';engine_ready=asyncio.Event();engine_release=asyncio.Event()
    def phase(label):safe_print({'phase':'cf007_check','label':label,'status':'started'})
    def mark(label):groups.append(label);safe_print({'phase':'cf007_check','label':label,'status':'passed'})
    async def scalar(sql,params=None):
        async with owned_session(proof) as session:return await session.scalar(text(sql),params or {})
    async def preserved():
        async with owned_session(proof) as session:
            return {table:sorted((await session.execute(text(f'SELECT row_to_json(t)::text FROM {table} t'))).scalars().all()) for table in
                ('auth_users','auth_identities','auth_sessions','flow_runs','flow_input_snapshots','stocks','flow_reports','flow_report_interpretations','flow_report_verifications','agent_reports')}
    async def denied(awaitable,code,label):
        try:await awaitable
        except domain.FakeExecutionError as exc:check(exc.code==code and exc.__cause__ is None,label)
        else:raise RuntimeError('CF007 expected fixed rejection')
        rejects.append(label)

    phase('migration_preservation')
    check(await scalar('SELECT version_num FROM alembic_version')=='c7001a7e0001','CF007 fresh head')
    phase('migration_downgrade_c6')
    await migration(proof,'c6001a7e0001')
    phase('migration_seed_users_sessions_reports')
    async with owned_session(proof) as session:
        a,b=AuthUser(id=uuid4()),AuthUser(id=uuid4());session.add_all([a,b]);await session.flush()
        ta,pa=await issue_session(session,a);ta2,pa2=await issue_session(session,a);tb,pb=await issue_session(session,b)
        _,pe=await issue_session(session,a);_,pr=await issue_session(session,a)
        await session.execute(update(AuthSession).where(AuthSession.id==pe.session_id).values(created_at=func.clock_timestamp()-text("interval '2 hours'"),expires_at=func.clock_timestamp()-text("interval '1 hour'")))
        phase('migration_seed_sessions_commit')
        await session.commit();await revoke_session(session,pr)
        phase('migration_seed_report')
        payload=make_flow_payload();payload['meta']['ticker']='999983'
        await FlowReportService(session,principal=pa).save_report(FlowReportSaveRequest(payload=payload,question='CF007 preserved synthetic report'))
        phase('migration_seed_legacy_row')
        session.add(FlowReport(id=uuid4(),stock_code='999983',owner_user_id=None));await session.commit()

    async def admitted(principal=pa,fixture='flow.synthetic.full20'):
        async with owned_session(proof) as session:
            run=await FlowRunService(session,principal=principal).admit(FlowAdmissionRequest(ticker='005930',question='CF007 synthetic',as_of='2026-11-08T00:00:00Z',idempotency_key=str(uuid4())),uuid4())
            seal=None if fixture is None else await InputPreparationService(session,principal=principal).prepare(run.run_id,fixture)
            return run.run_id,seal
    phase('migration_seed_receipt_input')
    first_run,first_input=await admitted()
    before=await preserved()
    phase('migration_exact_DDL_hook')
    try:await migration(proof,'c7001a7e0001',fail=True)
    except FakeDDLFailure:pass
    else:raise RuntimeError('CF007 DDL hook not reached')
    check(await scalar('SELECT version_num FROM alembic_version')=='c6001a7e0001' and await scalar("SELECT to_regclass('flow_fake_executions')") is None,'CF007 DDL rollback')
    check(await preserved()==before,'CF007 rollback old values')
    phase('migration_upgrade_preserved')
    await migration(proof,'c7001a7e0001');check(await preserved()==before,'CF007 c6 upgrade old values')
    phase('migration_empty_roundtrip')
    await migration(proof,'c6001a7e0001');await migration(proof,'c7001a7e0001');check(await preserved()==before,'CF007 empty grants roundtrip with sealed input')
    mark('fresh_c7_c6_existing_receipt_input_report_upgrade_and_postCREATE_rollback')

    async def counted(seal,identity):
        calls[identity]=calls.get(identity,0)+1
        check(calls[identity]<=1,'CF007 at most one engine call per execution')
        if behavior=='error':raise RuntimeError('synthetic error never persisted')
        if behavior=='timeout':await asyncio.Event().wait()
        if behavior=='gate':engine_ready.set();await asyncio.wait_for(engine_release.wait(),15)
        value=await domain.fake_engine(seal,identity)
        if behavior=='invalid':value['ticker']='000660'
        return value

    async def execute(run,principal=pa,opt=True,commit_mode=None,pid=None,commit_gate=None):
        async with owned_session(proof) as session:
            if pid is not None:pid['value']=await session.scalar(text('SELECT pg_backend_pid()'));pid['ready'].set()
            original=session.commit;commits=0
            async def commit():
                nonlocal commits
                commits+=1
                if commit_gate and commits==commit_gate[0]:commit_gate[1].set();await asyncio.wait_for(commit_gate[2].wait(),15)
                if commit_mode and commits==commit_mode[0]:
                    if commit_mode[1]=='ack':await original()
                    raise OSError('synthetic commit outcome')
                await original()
            session.commit=commit
            return await service.FakeExecutionService(session,principal=principal).execute_once(run,allow_fake=opt)
    async def get(run,principal=pa):
        async with owned_session(proof) as session:return await service.FakeExecutionService(session,principal=principal).get(run)
    async def wait_lock(pid):
        deadline=time.monotonic()+12
        while time.monotonic()<deadline:
            if await scalar('SELECT wait_event_type FROM pg_stat_activity WHERE pid=:pid',{'pid':pid})=='Lock':return
            await asyncio.sleep(.02)
        raise RuntimeError('CF007 owned lock wait not reached')
    async def raw_grant(run,seal,*,past=False,changes=None):
        stamp=await scalar('SELECT clock_timestamp()')
        if past:stamp-=timedelta(seconds=20)
        token=secrets.token_bytes(32)
        values=dict(id=uuid4(),input_snapshot_id=seal.id,contract_version=1,engine_id=domain.ENGINE_ID,
            claim_digest=hashlib.sha256(token).digest(),status='running',started_at=stamp,deadline_at=stamp+timedelta(seconds=10))
        values.update(changes or {})
        async with owned_session(proof) as session:row=await session.scalar(insert(FlowFakeExecution).values(**values).returning(FlowFakeExecution));await session.commit()
        return row,token
    async def nonempty_refused():
        state=await scalar('SELECT count(*) FROM flow_fake_executions')
        try:await migration(proof,'c6001a7e0001')
        except RuntimeError as exc:
            check(type(exc) is RuntimeError and str(exc)=='Refusing fake execution downgrade: grants exist','CF007 exact nonempty refusal')
        else:raise RuntimeError('CF007 nonempty downgrade accepted')
        check(await scalar('SELECT count(*) FROM flow_fake_executions')==state and await scalar('SELECT version_num FROM alembic_version')=='c7001a7e0001','CF007 nonempty state preserved')

    old_overrides=dict(app.dependency_overrides)
    async def request_session():
        async with owned_session(proof) as session:yield session
    app.dependency_overrides[get_session]=request_session
    try:
        with patch.object(service,'fake_engine',counted):
            phase('one_shot_expired_crash')
            crash_run,crash_input=await admitted();crash,claim=await raw_grant(crash_run,crash_input,past=True)
            await nonempty_refused()  # A running grant alone is enough to refuse.
            async with owned_session(proof) as session:
                late=await service.FakeExecutionService(session,principal=pa)._finish(crash_run,crash.id,claim,('succeeded',domain.result_text(domain._v1_facts(crash_input,crash.id),crash_input,crash.id),None))
            check(late.status=='timed_out' and late.error_code=='deadline_expired' and not calls,'CF007 late candidate discarded')
            check((await execute(crash_run)).id==crash.id and not calls,'CF007 crash grant has no takeover')
            await nonempty_refused()
            mark('running_and_timedout_nonempty_downgrade_late_candidate_no_takeover')

            phase('ASGI_receipt_prepare_execute_read')
            async with owned_session(proof) as session:check((await authenticate(session,ta)).user_id==pa.user_id,'CF007 real session authentication')
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://localhost:8200') as client:
                for fixture,count in [('flow.synthetic.full20',20),('flow.synthetic.short4',4)]:
                    response=await client.post('/api/flow/runs',json=dict(ticker='005930',question='CF007 ASGI',as_of='2026-11-08T00:00:00Z',idempotency_key=str(uuid4())),headers={'cookie':SESSION_COOKIE+'='+ta,'origin':'http://localhost:3200','x-csrf-token':csrf_token(pa)})
                    check(response.status_code==202 and response.headers['cache-control']=='private, no-store','CF007 ASGI real admission')
                    run=UUID(response.json()['data']['run_id'])
                    async with owned_session(proof) as session:seal=await InputPreparationService(session,principal=pa).prepare(run,fixture)
                    result=await execute(run);read=await get(run,pa2)
                    check(result==read and result.status=='succeeded' and result.body['row_count']==count and result.body['totals']['foreign']==40000*count,'CF007 artifact actual values')
                    result.body['totals']['foreign']=0;check((await get(run)).body['totals']['foreign']==40000*count,'CF007 returned copy')
                    check(await execute(run,pa2)==read and calls[result.id]==1,'CF007 other session replay no call')
                    fetched=await client.get('/api/flow/runs/'+str(run),headers={'cookie':SESSION_COOKIE+'='+ta})
                    check(fetched.status_code==200 and fetched.json()['data']['execution_status']=='pending' and fetched.json()['data']['storage_status']=='not_stored','CF007 public receipt unchanged')
            mark('actual_ASGI_CSRF_session_receipt_seal_full20_short4_store_and_owner_read')

            phase('owner_preconditions')
            count_before=await scalar('SELECT count(*) FROM flow_fake_executions');call_before=sum(calls.values())
            for principal in (pb,pe,pr,replace(pa,user_id=pb.user_id),replace(pa,token_digest=b'x'*32)):
                code='not_found' if principal==pb else 'auth_required'
                await denied(execute(first_run,principal),code,'owner_session_execute')
                await denied(get(first_run,principal),code,'owner_session_get')
            await denied(get(uuid4(),pb),'not_found','absent_same_not_found')
            unprepared,_=await admitted(fixture=None);await denied(execute(unprepared),'not_found','unprepared')
            for opt in (False,1,'true',None):await denied(execute(first_run,opt=opt),'invalid','strict_opt_in')
            async with owned_session(proof) as session:
                row=await session.get(FlowRun,first_run);old=row.input_fingerprint
                await session.execute(update(FlowRun).where(FlowRun.id==first_run).values(input_fingerprint='0'*64));await session.commit()
            await denied(execute(first_run),'corrupt','source_corruption')
            async with owned_session(proof) as session:await session.execute(update(FlowRun).where(FlowRun.id==first_run).values(input_fingerprint=old));await session.commit()
            check(await scalar('SELECT count(*) FROM flow_fake_executions')==count_before and sum(calls.values())==call_before,'CF007 precondition writes calls zero')
            mark('real_owner_expired_revoked_forged_unprepared_corrupt_optin_denials')

            phase('same_run_race')
            race_run,_=await admitted();pids=[{'ready':asyncio.Event()},{'ready':asyncio.Event()}];tasks=[]
            try:
                async with owned_session(proof) as blocker:
                    await blocker.execute(select(FlowRun).where(FlowRun.id==race_run).with_for_update())
                    tasks=[asyncio.create_task(execute(race_run,pa,pid=pids[0])),asyncio.create_task(execute(race_run,pa2,pid=pids[1]))]
                    await asyncio.gather(*(asyncio.wait_for(p['ready'].wait(),15) for p in pids));await asyncio.gather(*(wait_lock(p['value']) for p in pids));await blocker.commit()
                results=await asyncio.wait_for(asyncio.gather(*tasks),20)
                check(results[0].id==results[1].id and (await get(race_run)).status=='succeeded' and calls[results[0].id]==1,'CF007 same grant race')
            finally:
                for task in tasks:
                    if not task.done():task.cancel()
                if tasks:await asyncio.gather(*tasks,return_exceptions=True)
            mark('barrier_two_attested_connections_one_grant_one_engine')

            phase('failure_ACK_timeout')
            for mode in [(1,'before'),(1,'ack'),(2,'before'),(2,'ack')]:
                run,seal=await admitted();before_calls=sum(calls.values())
                await denied(execute(run,commit_mode=mode),'unavailable','commit_'+str(mode[0])+'_'+mode[1])
                async with owned_session(proof) as session:row=await repository.get_owned(session,run,pa.user_id)
                if mode==(1,'before'):
                    check(row is None and sum(calls.values())==before_calls,'CF007 grant rollback no grant call')
                    check((await execute(run)).status=='succeeded','CF007 retry after confirmed grant rollback')
                    continue
                expected='succeeded' if mode==(2,'ack') else 'running'
                check(row.status==expected and sum(calls.values())==before_calls+(1 if mode[0]==2 else 0),'CF007 actual commit ACK state')
                previous=sum(calls.values());check((await execute(run)).id==row.id and sum(calls.values())==previous,'CF007 ACK replay engine zero')
            for mode,error in [('error','fake_failed'),('invalid','result_invalid'),('timeout','coroutine_timeout')]:
                behavior=mode;run,_=await admitted();result=await execute(run)
                check(result.error_code==error and result.body is None and calls[result.id]==1,'CF007 failed outcome')
                behavior='normal';check(await execute(run)==result and calls[result.id]==1,'CF007 terminal retry no invocation')
            behavior='normal'
            mark('grant_terminal_confirmed_rollback_ACK_loss_engine_error_bad_result_and_timeout')

            phase('session_ordering')
            for stage,revoke_first in [('grant',True),('grant',False),('terminal',True),('terminal',False)]:
                async with owned_session(proof) as session:
                    user=await session.get(AuthUser,pa.user_id);_,principal=await issue_session(session,user);await session.commit()
                run,_=await admitted();tasks=[];release=asyncio.Event();ready=asyncio.Event();pid={'ready':asyncio.Event()}
                try:
                    if revoke_first and stage=='grant':
                        async with owned_session(proof) as revoker:
                            await revoker.execute(update(AuthSession).where(AuthSession.id==principal.session_id).values(revoked_at=func.clock_timestamp()))
                            task=asyncio.create_task(execute(run,principal,pid=pid));tasks.append(task)
                            await asyncio.wait_for(pid['ready'].wait(),15);await wait_lock(pid['value']);await revoker.commit()
                        await denied(task,'auth_required','revoke_before_grant')
                        check(await scalar('SELECT count(*) FROM flow_fake_executions e JOIN flow_input_snapshots s ON s.id=e.input_snapshot_id WHERE s.run_id=:id',{'id':run})==0,'CF007 revoked no grant')
                    elif revoke_first:
                        behavior='gate';engine_ready=asyncio.Event();engine_release=asyncio.Event()
                        task=asyncio.create_task(execute(run,principal,pid=pid));tasks.append(task)
                        await asyncio.wait_for(engine_ready.wait(),15)
                        async with owned_session(proof) as revoker:
                            await revoker.execute(update(AuthSession).where(AuthSession.id==principal.session_id).values(revoked_at=func.clock_timestamp()))
                            engine_release.set()
                            await wait_lock(pid['value'])
                            await revoker.commit()
                        await denied(task,'auth_required','revoke_before_terminal')
                        check((await get(run)).status=='running','CF007 revoked terminal not stored')
                    else:
                        behavior='gate' if stage=='grant' else 'normal';engine_ready=asyncio.Event();engine_release=asyncio.Event()
                        task=asyncio.create_task(execute(run,principal,commit_gate=(1 if stage=='grant' else 2,ready,release)));tasks.append(task)
                        await asyncio.wait_for(ready.wait(),15)
                        async def revoke_waiter():
                            async with owned_session(proof) as session:
                                pid['value']=await session.scalar(text('SELECT pg_backend_pid()'));pid['ready'].set();await revoke_session(session,principal)
                        revocation=asyncio.create_task(revoke_waiter());tasks.append(revocation)
                        await asyncio.wait_for(pid['ready'].wait(),15);await wait_lock(pid['value']);release.set()
                        if stage=='grant':
                            await asyncio.wait_for(engine_ready.wait(),15);await revocation;engine_release.set();await denied(task,'auth_required','grant_before_revoke_terminal_denied')
                        else:
                            check((await task).status=='succeeded','CF007 terminal precedes revoke');await revocation
                        await denied(get(run,principal),'auth_required','future_revoked_read')
                finally:
                    release.set();engine_release.set();behavior='normal'
                    for task in tasks:
                        if not task.done():task.cancel()
                    if tasks:await asyncio.gather(*tasks,return_exceptions=True)
            mark('actual_session_SHARE_grant_and_terminal_revoke_both_orders')

            phase('physical_fence_deadline')
            async def reject_sql(statement,state,label):
                try:
                    async with owned_session(proof) as session:await session.execute(statement);await session.commit()
                except DBAPIError as exc:check(getattr(exc.orig,'sqlstate',None)==state,'CF007 SQLSTATE '+label)
                else:raise RuntimeError('CF007 SQL accepted invalid transition')
                rejects.append(label)
            fresh_run,fresh_input=await admitted();row,token=await raw_grant(fresh_run,fresh_input)
            async with owned_session(proof) as session:
                await denied(service.FakeExecutionService(session,principal=pa)._finish(fresh_run,row.id,b'z'*32,('failed',None,'fake_failed')),'fence','wrong_token')
            await reject_sql(update(FlowFakeExecution).where(FlowFakeExecution.id==row.id).values(claim_digest=b'z'*32),'23514','identity_token')
            await reject_sql(text("DELETE FROM flow_fake_executions"),'23514','all_delete')
            for changes in ({'status':'running'},{'deadline_at':row.deadline_at+timedelta(seconds=1)}):
                await reject_sql(update(FlowFakeExecution).where(FlowFakeExecution.id==row.id).values(**changes),'23514','no_regrant_identity')
            for raw in ('{}',json.dumps({'contract_version':1,'mode':'synthetic_only','execution_id':str(uuid4()),'input_snapshot_id':str(fresh_input.id)})):
                await reject_sql(update(FlowFakeExecution).where(FlowFakeExecution.id==row.id).values(status='succeeded',finished_at=func.clock_timestamp(),result_json=raw,result_sha256=hashlib.sha256(raw.encode()).hexdigest()),'23514','body_links')
            # Each invalid INSERT has a new unclaimed input; FK/NOT NULL/CHECK
            # failures cannot be mistaken for the input UNIQUE violation.
            for key,value,state in [('input_snapshot_id',uuid4(),'23503'),('contract_version',2,'23514'),('engine_id','other','23514'),('claim_digest',b'x','23514'),('status','failed','23514'),('deadline_at',row.started_at+timedelta(seconds=11),'23514'),('started_at',text("'infinity'::timestamptz"),'23514')]:
                run,seal=await admitted();now=await scalar('SELECT clock_timestamp()')
                values=dict(id=uuid4(),input_snapshot_id=seal.id,contract_version=1,engine_id=domain.ENGINE_ID,claim_digest=b'x'*32,status='running',started_at=now,deadline_at=now+timedelta(seconds=10));values[key]=value
                await reject_sql(insert(FlowFakeExecution).values(**values),state,'insert_'+key)
            for key in ('id','input_snapshot_id','contract_version','engine_id','claim_digest','status','started_at','deadline_at'):
                run,seal=await admitted();now=await scalar('SELECT clock_timestamp()');values=dict(id=uuid4(),input_snapshot_id=seal.id,contract_version=1,engine_id=domain.ENGINE_ID,claim_digest=b'x'*32,status='running',started_at=now,deadline_at=now+timedelta(seconds=10));values[key]=None
                await reject_sql(insert(FlowFakeExecution).values(**values),'23502','NOT_NULL_'+key)
            # Fresh running grant for each combination: no terminal trigger is
            # bypassed, and an unrelated expired deadline cannot mask the CHECK.
            combinations = [
                ('success_missing_finished', {'status':'succeeded','finished_at':None}),
                ('success_missing_result', {'status':'succeeded','result_json':None}),
                ('success_missing_hash', {'status':'succeeded','result_sha256':None}),
                ('success_error_present', {'status':'succeeded','error_code':'fake_failed'}),
                ('failed_missing_finished', {'status':'failed','finished_at':None}),
                ('failed_result_present', {'status':'failed','result_json':'{}'}),
                ('failed_hash_present', {'status':'failed','result_sha256':'0'*64}),
                ('failed_wrong_error', {'status':'failed','error_code':'deadline_expired'}),
                ('timeout_missing_finished', {'status':'timed_out','finished_at':None}),
                ('timeout_result_present', {'status':'timed_out','result_json':'{}'}),
                ('timeout_hash_present', {'status':'timed_out','result_sha256':'0'*64}),
                ('timeout_wrong_error', {'status':'timed_out','error_code':'fake_failed'}),
                ('running_finished_present', {'status':'running','finished_at':func.clock_timestamp()}),
                ('running_result_present', {'status':'running','result_json':'{}'}),
            ]
            for label, delta in combinations:
                candidate_run,candidate_input=await admitted()
                if delta['status']=='running':
                    stamp=await scalar('SELECT clock_timestamp()');identity=uuid4()
                    body=domain.result_text(domain._v1_facts(candidate_input,identity),candidate_input,identity)
                    values=dict(id=identity,input_snapshot_id=candidate_input.id,contract_version=1,engine_id=domain.ENGINE_ID,
                        claim_digest=b'x'*32,status='running',started_at=stamp,deadline_at=stamp+timedelta(seconds=10))
                    if 'finished_at' in delta:values['finished_at']=stamp
                    if 'result_json' in delta:values.update(result_json=body,result_sha256=hashlib.sha256(body.encode()).hexdigest())
                    await reject_sql(insert(FlowFakeExecution).values(**values),'23514',label)
                    check(await scalar('SELECT count(*) FROM flow_fake_executions WHERE input_snapshot_id=:id',{'id':candidate_input.id})==0,'CF007 invalid running insert writes zero')
                    continue
                candidate,_=await raw_grant(candidate_run,candidate_input)
                body=domain.result_text(domain._v1_facts(candidate_input,candidate.id),candidate_input,candidate.id)
                succeeded=delta['status']=='succeeded'
                values=dict(status=delta['status'],finished_at=func.clock_timestamp(),
                    result_json=body if succeeded else None,result_sha256=hashlib.sha256(body.encode()).hexdigest() if succeeded else None,
                    error_code=None if succeeded else 'fake_failed' if delta['status']=='failed' else 'coroutine_timeout' if delta['status']=='timed_out' else None)
                values.update(delta)
                if delta.get('result_json')=='{}':
                    values.update(result_json=body,result_sha256=hashlib.sha256(body.encode()).hexdigest())
                check(await scalar('SELECT clock_timestamp() < deadline_at FROM flow_fake_executions WHERE id=:id',{'id':candidate.id}), 'CF007 combination deadline still valid')
                await reject_sql(update(FlowFakeExecution).where(FlowFakeExecution.id==candidate.id).values(**values),'23514',label)
                check(await scalar("SELECT status FROM flow_fake_executions WHERE id=:id",{'id':candidate.id})=='running','CF007 rejected combination preserved running')
            terminal=await get(crash_run)
            await reject_sql(update(FlowFakeExecution).where(FlowFakeExecution.id==terminal.id).values(status='timed_out'),'23514','terminal_noop')
            late_run,late_input=await admitted();late,token=await raw_grant(late_run,late_input,past=True)
            text_body=domain.result_text(domain._v1_facts(late_input,late.id),late_input,late.id)
            await reject_sql(update(FlowFakeExecution).where(FlowFakeExecution.id==late.id).values(status='succeeded',finished_at=late.started_at+timedelta(seconds=1),result_json=text_body,result_sha256=hashlib.sha256(text_body.encode()).hexdigest()),'23514','DB_now_late_result')
            check((await get(late_run)).error_code=='deadline_expired','CF007 query expires running')
            await nonempty_refused()
            mark('real_SQL_fence_identity_null_combinations_body_links_deadline_trigger_and_expiry')

            after=await preserved()
            for table in ('stocks','flow_reports','flow_report_interpretations','flow_report_verifications','agent_reports'):
                check(after[table]==before[table],'CF007 public report index stock untouched')
            check(await scalar("SELECT count(*) FROM flow_runs WHERE admission_mode<>'receipt_only' OR execution_status<>'pending' OR storage_status<>'not_stored'")==0,'CF007 receipt unchanged')
            check(await InputPreparationService_read(proof,first_run,pa)==first_input,'CF007 original sealed bytes unchanged')
            check(all(n==1 for n in calls.values()),'CF007 each engine max1')
            mark('original_input_receipt_and_public_storage_preserved_no_external_calls')
            return {'status':'passed','groups':groups,'rejections':len(rejects),'engine_invocations':sum(calls.values()),'distinct_invoked_execution_ids':len(calls),'max_calls_per_execution':max(calls.values(),default=0)}
    finally:
        app.dependency_overrides.clear();app.dependency_overrides.update(old_overrides)


async def InputPreparationService_read(proof,run,principal):
    from scripts.cf002_interactive_login import owned_session
    from src.modules.flow.application.input_preparation_service import InputPreparationService
    async with owned_session(proof) as session:return await InputPreparationService(session,principal=principal).get(run)
