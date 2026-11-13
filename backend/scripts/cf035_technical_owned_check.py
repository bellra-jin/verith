"""Fixed owned-PG storage verification. No app/config/engine/provider bootstrap."""
import copy
from dataclasses import replace
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
from uuid import UUID, uuid4


def storage_fixture(owner_user_id, *, report_id=None, request_id=None, change=None, binding=None):
    """Shared public synthetic fixture; never inspect an environment or credential."""
    from src.modules.analysis.domain.contracts import AnalysisContext, canonical_json, json_hash
    from src.modules.analysis.domain.agent_envelope import digest
    from src.modules.technical.application.boundary_adapter import TechnicalBoundaryBinding
    from src.modules.technical.application.boundary_restore import TechnicalReadBinding
    from src.modules.technical.application.owned_report_service import OPERATION
    path = Path(__file__).resolve().parents[2]/'frontend/tests/fixtures/cf031-technical-boundary-read.json'
    if hashlib.sha256(path.read_bytes()).hexdigest() != '46380ea4c998e3130cf1c447c278b93ed32288c42af9d62f84b90b7acabce5e0':
        raise RuntimeError('Technical fixture source changed')
    fixture = json.loads(path.read_text(encoding='utf-8'))
    request = copy.deepcopy(fixture['expected']['request']); response = copy.deepcopy(fixture['response'])
    if binding is not None:
        if (not isinstance(binding,TechnicalReadBinding) or binding.caller_context.owner_user_id!=owner_user_id
                or report_id is not None or request_id is not None):
            raise RuntimeError('Fixed completion fixture binding required')
        binding.__post_init__();request=json.loads(binding.boundary.input_json);data=request['data']
        response.update(request_id=request['request_id'],trace_id=request['trace_id'])
        response['data'].update(request_snapshot=copy.deepcopy(data),request_sha256=json_hash(binding.boundary.input_json))
        response['data']['result'].update(request_id=request['request_id'],trace_id=request['trace_id'],
            ticker=data['stock']['stock_code'],as_of=data['requested_as_of'],resolved_stock_name=data['stock']['stock_name'])
        if change is not None:change(response)
        return binding,binding.compose(response)
    if report_id is not None: request['data']['context']['report_id'] = str(report_id)
    if request_id is not None: request['request_id'] = str(request_id)
    ids = request['data']['context']; stamp = datetime.fromisoformat(request['data']['requested_as_of'])
    context = AnalysisContext(UUID(ids['analysis_id']),UUID(ids['admission_request_id']),UUID(ids['attempt_id']),
        owner_user_id,request['data']['operation'],ids['input_fingerprint'],stamp,stamp+timedelta(seconds=3))
    boundary = TechnicalBoundaryBinding(context,UUID(ids['report_id']),UUID(request['request_id']),UUID(request['trace_id']),canonical_json(request))
    caller_text = canonical_json({'operation':OPERATION,'boundary_request':request})
    binding = TechnicalReadBinding(replace(context,operation=OPERATION,input_fingerprint=json_hash(caller_text)),caller_text,boundary)
    response['request_id'] = request['request_id']
    response['data']['request_snapshot'] = copy.deepcopy(request['data'])
    response['data']['request_sha256'] = digest(request)
    response['data']['result']['request_id'] = request['request_id']
    if change is not None: change(response)
    return binding,binding.compose(response)


async def verify_technical_owned(proof):
    from scripts.cf003_admission_check import isolated_application, check
    with isolated_application(proof) as observed:
        result = await _verify(proof)
        check(not any(observed.values()), 'Technical forbidden I/O')
        result['observed_denials'] = dict(observed)
        return result


async def verify_technical_admission(proof):
    """Fixed CF048 SQL-only entry, never an engine/provider or DB adoption API."""
    from scripts.runner_owned_database import RunnerOwnedDatabase
    from scripts.cf003_admission_check import isolated_application, check
    if type(proof) is not RunnerOwnedDatabase:
        raise RuntimeError('Technical admission requires original owned proof')
    proof.verify_ownership()
    with isolated_application(proof) as observed:
        result=await _verify_admission(proof)
        check(not any(observed.values()),'CF048 forbidden I/O')
        return result | {'observed_denials':dict(observed)}


async def _verify_admission(proof):
    import asyncio
    from sqlalchemy import select,text,event
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.ext.asyncio import create_async_engine
    from alembic import command
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from db.models.auth.models import AuthUser,AuthSession
    from db.models.common.stock import Stock
    from db.models.technical.execution_admission import TechnicalAnalysisRun as Run,TechnicalUsagePeriod as Period
    from src.modules.auth.application.session_service import issue_session,revoke_session,AuthenticationRequired
    from src.modules.technical.domain.execution_admission import Intent,Policy,TechnicalAdmissionError,canonical
    from src.modules.technical.application.execution_admission_service import TechnicalAdmissionService as Service
    from scripts.cf002_interactive_login import owned_session,safe_print
    from scripts.cf003_admission_check import check,migration
    groups=[];base_policy=dict(operation='technical.analysis.v1',enabled=True,currency='USD',supported_tickers=['000720'],
        user_daily_limit=3,service_daily_limit=30,daily_budget_nano=300000,attempt_reserve_nano=10000,
        deadline_seconds=10,model='synthetic-model',service_tier='default',price_id='cf048.synthetic.v1',
        price_evidence_sha256='a'*64,input_nano_per_token=10,output_nano_per_token=20,
        input_token_cap=100,output_token_cap=50,input_byte_cap=1000,output_byte_cap=500,max_calls=4)
    policy=Policy.parse(base_policy)
    intent=Intent.parse(dict(operation='technical.analysis.v1',ticker='000720',original_query='CF048 synthetic chart',requested_views=['technical'],
        conditions=dict(profile='technical.multiframe.v1',periods=['3m','1y','5y'])))

    def mark(name):
        groups.append(name);safe_print({'phase':'cf048_check','label':name,'status':'passed'})
    async def scalar(query,params=None):
        async with owned_session(proof) as session:return await session.scalar(text(query),params or {})
    async def totals():
        async with owned_session(proof) as session:
            return tuple((await session.execute(text('SELECT (SELECT count(*) FROM technical_analysis_runs),(SELECT count(*) FROM technical_usage_periods),coalesce((SELECT sum(request_count) FROM technical_usage_periods),0),coalesce((SELECT sum(reserved_nano) FROM technical_usage_periods),0)'))).one())
    async def user():
        async with owned_session(proof) as session:
            a=AuthUser(id=uuid4());session.add(a);await session.flush()
            _,p=await issue_session(session,a);_,p2=await issue_session(session,a);await session.commit()
            return p,p2
    async def admit(p,key,*,supplied=policy,body=intent):
        async with owned_session(proof) as session:return await Service(session,principal=p,policy=supplied).admit(key,body)
    async def claim(p,receipt,token=None,*,supplied=policy):
        async with owned_session(proof) as session:return await Service(session,principal=p,policy=supplied).dispatch_claim(receipt.run,receipt.claim_token if token is None else token)
    async def read(p,id):
        async with owned_session(proof) as session:return await Service(session,principal=p).get(id)
    async def close(p,id,reason='CANCELLED'):
        async with owned_session(proof) as session:return await Service(session,principal=p).close_unknown(id,reason)
    async def denied(awaitable,code):
        try:await awaitable
        except TechnicalAdmissionError as error:check(error.code==code,'CF048 fixed refusal');return
        check(False,'CF048 expected refusal')
    async def sql_denied(query,params=None,*,deferred=False):
        async with owned_session(proof) as session:
            executed=False
            try:
                await session.execute(text(query),params or {});executed=True;await session.commit()
            except IntegrityError:
                await session.rollback()
                check(not deferred or executed,'CF048 aggregate refused at commit')
                return
            check(False,'CF048 SQL constraint must reject')

    config=Config();config.set_main_option('script_location',str(Path(__file__).resolve().parents[1]/'db/migrations'))
    graph=ScriptDirectory.from_config(config);heads=graph.get_heads()
    check(len(heads)==1 and 'c48001a7e0001' in {r.revision for r in graph.walk_revisions()},'CF048 single migration lineage')
    check(await scalar('SELECT version_num FROM alembic_version')==heads[0],'CF048 exact graph head')
    check(await totals()==(0,0,0,0),'CF048 empty Technical ledger')
    await migration(proof,'c45001a7e0001',downgrade=True)
    check(await scalar("SELECT to_regclass('technical_analysis_runs') IS NULL AND to_regclass('technical_usage_periods') IS NULL"),'CF048 empty downgrade')
    class InjectedDDL(RuntimeError):pass
    await proof.preflight();engine=create_async_engine(proof.url,connect_args=proof.connection_parameters());reached=[]
    try:
        async with engine.connect() as connection:
            await proof.attest_connection(connection)
            def inject(sync):
                cfg=Config();cfg.set_main_option('script_location',str(Path(__file__).resolve().parents[1]/'db/migrations'))
                cfg.attributes.update(connection=sync,verified_test_mode=True)
                def after(conn,cursor,statement,parameters,context,executemany):
                    if statement.lstrip().upper().startswith('CREATE TABLE TECHNICAL_ANALYSIS_RUNS'):
                        reached.append(True);raise InjectedDDL('fixed CF048 DDL failure')
                event.listen(sync,'after_cursor_execute',after)
                try:command.upgrade(cfg,heads[0])
                finally:event.remove(sync,'after_cursor_execute',after)
            try:await connection.run_sync(inject);await connection.commit()
            except InjectedDDL:await connection.rollback()
    finally:await engine.dispose()
    check(reached==[True] and await scalar("SELECT to_regclass('technical_usage_periods') IS NULL") and await scalar('SELECT version_num FROM alembic_version')=='c45001a7e0001','CF048 actual DDL atomic rollback')
    await migration(proof,heads[0]);mark('empty_downgrade_same_connection_DDL_rollback')

    p,a2=await user();other,_=await user()
    await denied(admit(p,'disabled',supplied=None),'POLICY_UNAVAILABLE')
    await denied(admit(p,'missing-stock'),'INPUT_INVALID')
    check(await totals()==(0,0,0,0),'CF048 refused requests no period/reserve')
    async with owned_session(proof) as session:
        session.add(Stock(stock_code='000720',stock_name='CF048 synthetic canonical',market='KOSPI'));await session.commit()
    mark('explicit_policy_and_registered_stock_before_reservation')

    raced=await asyncio.gather(admit(p,'same-key'),admit(p,'same-key'))
    check(sum(v.newly_admitted for v in raced)==1 and len({v.run.analysis_id for v in raced})==1,'CF048 actual same-key winner1')
    first=next(v for v in raced if v.newly_admitted)
    check(await totals()==(1,1,1,10000),'CF048 exactly one atomic reservation')
    changed=Intent.parse({**intent.data(),'original_query':'different synthetic query'})
    await denied(admit(p,'same-key',body=changed),'IDEMPOTENCY_CONFLICT')
    replay=await admit(a2,'same-key',supplied=None)
    check(not replay.newly_admitted and replay.claim_token is None and replay.run==first.run,'CF048 A2 immutable same-key recovery')
    check(await read(a2,first.run.analysis_id)==first.run,'CF048 actual new owner session GET')
    await denied(read(other,first.run.analysis_id),'NOT_FOUND')
    await denied(claim(a2,first),'CLAIM_DENIED')
    await denied(claim(p,first,b'x'*32),'CLAIM_DENIED')
    claims=await asyncio.gather(claim(p,first),claim(p,first))
    check(sum(v.newly_claimed for v in claims)==1 and all(v.run.state=='claimed' for v in claims),'CF048 actual claim winner1')
    check(not (await claim(p,first,supplied=None)).newly_claimed,'CF048 claimed replay no new right without policy')
    check(await totals()==(1,1,1,10000),'CF048 claim/replay no second reservation')
    mark('same_key_and_claim_two_SQL_session_winner1_A2_read_not_execution')

    rid=first.run.analysis_id;pid=first.run.period_id
    await sql_denied("UPDATE technical_analysis_runs SET claim_consumed_at=NULL,state='admitted' WHERE id=:id",{'id':rid})
    for column,value in (('id',uuid4()),('owner_user_id',other.user_id),('admission_session_id',a2.session_id),
            ('period_id',uuid4()),('policy_sha256','f'*64),('key_digest',b'z'*32),('attempt_id',uuid4()),
            ('reserved_nano',9999),('deadline_at',first.run.deadline_at+timedelta(seconds=1))):
        await sql_denied('UPDATE technical_analysis_runs SET '+column+'=:value WHERE id=:id',{'value':value,'id':rid})
    for column,value in (('policy_json','{}'),('policy_sha256','f'*64),('request_count',0),('reserved_nano',0),('kst_date',datetime(2020,1,1).date())):
        await sql_denied('UPDATE technical_usage_periods SET '+column+'=:value WHERE id=:id',{'value':value,'id':pid})
    await sql_denied('UPDATE technical_usage_periods SET request_count=request_count+1 WHERE id=:id',{'id':pid},deferred=True)
    await sql_denied('UPDATE technical_usage_periods SET reserved_nano=reserved_nano+1 WHERE id=:id',{'id':pid},deferred=True)
    for query in ('DELETE FROM technical_analysis_runs WHERE id=:id','DELETE FROM technical_usage_periods WHERE id=:id'):
        await sql_denied(query,{'id':rid if 'analysis_runs' in query else pid})
    await sql_denied('TRUNCATE technical_analysis_runs,technical_usage_periods')
    check(await totals()==(1,1,1,10000),'CF048 rejected direct mutations preserve accounting')
    mark('SQL_identity_policy_period_claim_counters_DELETE_TRUNCATE_deferred_guards')

    # A fresh direct INSERT with a valid hash/policy/amount but excessive deadline
    # must be rejected too, independently of UPDATE immutability.
    async with owned_session(proof) as session:
        root=await session.get(Run,rid);values={c.name:getattr(root,c.name) for c in Run.__table__.columns}
        fresh_stamp=await session.scalar(text('SELECT clock_timestamp()'))
    values.update(id=uuid4(),admission_request_id=uuid4(),attempt_id=uuid4(),planned_report_id=uuid4(),boundary_request_id=uuid4(),trace_id=uuid4(),
        key_digest=hashlib.sha256(b'deadline-tamper').digest(),state='admitted',claim_consumed_at=None,
        as_of=fresh_stamp,started_at=fresh_stamp,deadline_at=fresh_stamp+timedelta(seconds=11))
    async with owned_session(proof) as session:
        try:
            session.add(Run(**values));await session.flush()
        except IntegrityError:await session.rollback()
        else:
            await session.rollback()
            check(False,'CF048 policy deadline must reject INSERT before deferred totals')
    check(await totals()==(1,1,1,10000),'CF048 direct deadline tamper rollback')
    mark('stored_policy_deadline_bound_direct_INSERT')

    # These wrappers simulate ACK loss around actual PostgreSQL commits. They do
    # not simulate a provider send, and no returned ID/token is used to recover.
    ack_owner,_=await user()
    for where in ('before','after'):
        key='ack-'+where;before=await totals()
        async with owned_session(proof) as session:
            original=session.commit
            async def lost():
                if where=='after':await original()
                raise OSError('fixed CF048 commit ACK loss')
            session.commit=lost
            await denied(Service(session,principal=ack_owner,policy=policy).admit(key,intent),'ACK_UNKNOWN')
        if where=='before':check(await totals()==before,'CF048 actual rollback before commit')
        else:
            async with owned_session(proof) as session:
                dirty=AuthUser(id=uuid4());session.add(dirty);writes=[]
                def sql_written(conn,cursor,statement,parameters,context,executemany):
                    if statement.lstrip().upper().startswith(('INSERT','UPDATE','DELETE')):writes.append(True)
                event.listen(session.bind.sync_connection,'before_cursor_execute',sql_written)
                try:recovered=await Service(session,principal=ack_owner).reconcile(key)
                finally:event.remove(session.bind.sync_connection,'before_cursor_execute',sql_written)
                check(dirty in session.new and not writes and recovered.claim_token is None and not recovered.newly_admitted,'CF048 dirty session readonly caller-key ACK recovery')
                await session.rollback()
            check((await totals())[0]==before[0]+1,'CF048 committed reservation survives lost ACK')
            await close(ack_owner,recovered.run.analysis_id,'DISPATCH_UNCERTAIN')
    mark('actual_commit_rollback_and_ACK_wrapper_loss_readonly_key_recovery')

    claim_owner,_=await user();claimable=await admit(claim_owner,'claim-ACK')
    async with owned_session(proof) as session:
        original=session.commit
        async def claim_lost():await original();raise OSError('fixed CF048 claim ACK loss')
        session.commit=claim_lost
        await denied(Service(session,principal=claim_owner,policy=policy).dispatch_claim(claimable.run,claimable.claim_token),'ACK_UNKNOWN')
    check((await read(claim_owner,claimable.run.analysis_id)).state=='claimed','CF048 committed claim consumed despite ACK loss')
    check(not (await claim(claim_owner,claimable)).newly_claimed,'CF048 ACK loss cannot claim again')
    cancelled=await admit(claim_owner,'claim-cancel')
    async with owned_session(proof) as session:
        original=session.commit
        async def commit_cancelled():await original();raise asyncio.CancelledError()
        session.commit=commit_cancelled
        try:await Service(session,principal=claim_owner,policy=policy).dispatch_claim(cancelled.run,cancelled.claim_token)
        except asyncio.CancelledError:pass
        else:check(False,'CF048 cancellation propagates')
    check(not (await claim(claim_owner,cancelled)).newly_claimed,'CF048 cancellation after ACK consumed claim')
    closed=await close(claim_owner,cancelled.run.analysis_id,'CANCELLED')
    check(closed.state=='unknown' and closed.held_nano==10000,'CF048 cancel hold')
    mark('claim_ACK_loss_and_cancel_preserve_consumption_hold')

    exp_owner,_=await user();expiring=await admit(exp_owner,'expiry')
    now=await scalar('SELECT clock_timestamp()')
    await asyncio.sleep(max(0,(expiring.run.deadline_at-now).total_seconds())+0.02)
    expired=await read(exp_owner,expiring.run.analysis_id)
    check(expired.state=='unknown' and expired.unknown_reason=='EXPIRED' and expired.redacted_at is not None,'CF048 actual DB-clock expiry')
    check(await scalar('SELECT intent_json IS NULL AND held_nano=reserved_nano FROM technical_analysis_runs WHERE id=:id',{'id':expired.analysis_id}),'CF048 actual SQL redaction without refund')
    await sql_denied("UPDATE technical_analysis_runs SET state='admitted',intent_json=:intent,redacted_at=NULL,unknown_reason=NULL WHERE id=:id",{'id':expired.analysis_id,'intent':intent.text})
    check(not (await admit(exp_owner,'expiry',supplied=None)).newly_admitted,'CF048 redacted key stays consumed')
    mark('actual_expiry_redaction_terminal_no_restore_or_refund')

    revoked,_=await user();pending=await admit(revoked,'revoked')
    async with owned_session(proof) as session:await revoke_session(session,revoked)
    try:await claim(revoked,pending)
    except AuthenticationRequired:pass
    else:check(False,'CF048 fresh revoked session denied')
    drift=Policy.parse(base_policy|{'deadline_seconds':9})
    await denied(admit(exp_owner,'drift',supplied=drift),'POLICY_UNAVAILABLE')
    # Historical admission session may be physically cleaned; the retained run
    # still prevents deleting its owner or losing the key/counters.
    async with owned_session(proof) as session:
        await session.execute(text('DELETE FROM auth_sessions WHERE user_id=:id'),{'id':revoked.user_id});await session.commit()
    await sql_denied('DELETE FROM auth_users WHERE id=:id',{'id':revoked.user_id})
    mark('revoked_auth_policy_drift_original_session_metadata_owner_RESTRICT')

    cap_owner,_=await user();await admit(cap_owner,'cap-1');await admit(cap_owner,'cap-2')
    async def compete(p,key):
        try:return await admit(p,key)
        except TechnicalAdmissionError as error:
            check(error.code=='LIMIT_EXCEEDED','CF048 race fixed cap error');return None
    user_race=await asyncio.gather(compete(cap_owner,'cap-3'),compete(cap_owner,'cap-4'))
    check(sum(value is not None for value in user_race)==1,'CF048 actual user-count race')
    # A fixed immutable day policy intentionally gives service-count and maximum
    # reservation the same final boundary. Units isolate each predicate; this
    # real two-session race verifies the shared lock and both SQL invariants.
    while (await totals())[0]<29:
        fresh,_=await user();await admit(fresh,str(uuid4()))
    left,_=await user();right,_=await user()
    final_race=await asyncio.gather(compete(left,'final-left'),compete(right,'final-right'))
    check(sum(value is not None for value in final_race)==1 and await totals()==(30,1,30,300000),'CF048 actual service/budget boundary winner1')
    await sql_denied('UPDATE technical_usage_periods SET reserved_nano=300001 WHERE id=:id',{'id':pid})
    check((await admit(a2,'same-key',supplied=None)).run.analysis_id==first.run.analysis_id,'CF048 capped owner replay no re-admission')
    mark('user_race_service_budget_race_no_limit_or_period_reset')

    before=await totals()
    try:await migration(proof,'c45001a7e0001',downgrade=True)
    except RuntimeError:pass
    else:check(False,'CF048 populated downgrade must deny')
    check(await totals()==before and await scalar('SELECT version_num FROM alembic_version')==heads[0],'CF048 populated downgrade preserves all rows')
    mark('populated_downgrade_locked_and_preserved')
    return dict(status='passed',groups=groups,run_count=30,period_count=1,reserved_nano=300000,
        local_claim_only=True,provider_authority=False,settlement_implemented=False,
        real_provider_requests=0,real_credential_reads=0,concurrency='actual two SQL sessions',
        ACK_loss='wrapper simulation around actual PG commits',expiry='actual DB clock; redaction on get, no sweeper')


async def _verify(proof):
    # Imports stay inside the proof-bound invocation, not parser/startup.
    import asyncio
    from contextlib import ExitStack
    from unittest.mock import patch
    from sqlalchemy import select, text, update, delete, func, event
    from sqlalchemy.exc import IntegrityError, DBAPIError
    from db.models.auth.models import AuthUser, AuthSession
    from db.models.common.stock import Stock
    from db.models.common.agent_report import AgentReport
    from db.models.technical.technical_report import TechnicalReport
    from db.models.technical.report_snapshot import TechnicalReportSnapshot
    from db.models.technical.report_chart import TechnicalReportChart
    from src.modules.auth.application.session_service import issue_session, Principal, AuthenticationRequired
    from src.modules.technical.application.owned_report_service import (
        TechnicalOwnedReportService, TechnicalReportConflict, TechnicalStoredPayloadError,
    )
    from src.modules.technical.infrastructure import report_repository as repo
    from scripts.cf002_interactive_login import owned_session
    from scripts.cf003_admission_check import migration, check
    groups = []
    async def scalar(statement):
        async with owned_session(proof) as session: return await session.scalar(statement)
    async def read(principal,rid):
        async with owned_session(proof) as session:
            value = await TechnicalOwnedReportService(session,principal=principal).read(rid)
            await session.rollback()
            return value

    # Later additive migrations may follow CF035; compare to this copied
    # source graph and require the Technical snapshot revision in its lineage.
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    config = Config()
    config.set_main_option('script_location',str(Path(__file__).resolve().parents[1]/'db/migrations'))
    graph = ScriptDirectory.from_config(config)
    heads = graph.get_heads()
    check(len(heads) == 1 and 'c35001a7e0001' in {r.revision for r in graph.walk_revisions()},'Technical migration lineage')
    check(await scalar(text('SELECT version_num FROM alembic_version')) == heads[0],'Technical source graph head')
    async with owned_session(proof) as session:
        a,b = AuthUser(id=uuid4()),AuthUser(id=uuid4()); session.add_all([a,b]); await session.flush()
        _,pa = await issue_session(session,a); _,pa2 = await issue_session(session,a); _,pb = await issue_session(session,b)
        session.add(Stock(stock_code='005930',stock_name='fixed canonical stock',market='KOSPI'))
        await session.commit()
    binding,frozen = storage_fixture(pa.user_id)
    rid = frozen.report_id
    # Legacy rows retain NULL owners and arbitrary preexisting JSONB untouched.
    legacy_root = None
    from src.modules.technical.application.owned_report_service import projection
    async with owned_session(proof) as session:
        now = await session.scalar(select(func.clock_timestamp()))
        legacy_root = projection(binding,frozen,pa,now)[0]
        legacy_root.id = uuid4(); legacy_root.request_id = 'legacy-technical-owned-fixture'
        legacy_root.owner_user_id = None
        session.add(legacy_root); await session.commit()
        legacy_before = await session.scalar(text('SELECT row_to_json(t)::text FROM technical_reports t WHERE id=:id').bindparams(id=legacy_root.id))
    await migration(proof,'c23001a7e0001',downgrade=True)
    await migration(proof,'head')
    check(legacy_before == await scalar(text('SELECT row_to_json(t)::text FROM technical_reports t WHERE id=:id').bindparams(id=legacy_root.id)), 'legacy preserved across downgrade and upgrade')
    groups.append('fresh_upgrade_empty_owned_downgrade_reupgrade_legacy_preserved')
    async with owned_session(proof) as staging:
        await TechnicalOwnedReportService(staging,principal=pa).stage(binding,frozen)
        check(await read(pa2,rid) is None,'uncommitted root must be invisible')
        await staging.commit()
    recovered = await read(pa2,rid)
    check(recovered.frozen == frozen and recovered.preview['charts'][0]['period'] == '3m','owned canonical restore')
    recovered.preview['charts'].clear()
    check(len((await read(pa2,rid)).preview['charts']) == 3,'detached preview')
    check(await read(pb,rid) is None and await read(pa,legacy_root.id) is None,'other owner and legacy hidden')
    groups.append('stage_flush_visibility_commit_restore_new_session_detached_owner')
    # Same stored ID and exact canonical bytes are read-only replay, not a new
    # storage/execution claim. Dirty unrelated ORM state must not autoflush.
    async with owned_session(proof) as session:
        stock = await session.scalar(select(Stock).where(Stock.stock_code == '005930'))
        stock.stock_name = 'unrelated local change must not flush'
        statements = []
        def trace(connection,cursor,statement,parameters,context,executemany):
            statements.append(statement.lstrip().split()[0].upper())
        connection = session.bind.sync_connection
        event.listen(connection,'before_cursor_execute',trace)
        try:
            replay = await TechnicalOwnedReportService(session,principal=pa2).stage(binding,frozen)
        finally: event.remove(connection,'before_cursor_execute',trace)
        check(replay.report_id == rid and replay.owner_user_id == pa.user_id,'exact stored replay reference')
        check(statements and set(statements) == {'SELECT'},'replay performed SQL writes')
        check(session.is_modified(stock),'replay committed or discarded unrelated caller changes')
        await session.rollback()
    for principal in (pa,pb):
        other_binding,other_output = storage_fixture(principal.user_id,report_id=rid,request_id=uuid4())
        async with owned_session(proof) as session:
            try: await TechnicalOwnedReportService(session,principal=principal).stage(other_binding,other_output)
            except TechnicalReportConflict: pass
            else: check(False,'nonidentical or other-owner stage replay accepted')
            await session.rollback()
    check((await read(pa2,rid)).frozen == frozen,'replay changed stored canonical bytes')
    groups.append('exact_stage_replay_select_only_dirty_session_conflicts')

    for kind in ('expired','revoked','forged'):
        if kind == 'forged': principal = replace(pa,token_digest=b'!'*32)
        else:
            async with owned_session(proof) as session:
                _,principal = await issue_session(session,a)
                now = datetime.now(principal.expires_at.tzinfo)
                await session.execute(update(AuthSession).where(AuthSession.id == principal.session_id).values(
                    **({'created_at':now-timedelta(seconds=2),'expires_at':now-timedelta(seconds=1)} if kind == 'expired' else {'revoked_at':now})))
                await session.commit()
        try: await read(principal,rid)
        except AuthenticationRequired: pass
        else: check(False,'invalid actual session accepted')
    groups.append('actual_session_expiry_revocation_forgery')
    # Every mutation is rolled back, keeping the stored positive anchor unchanged.
    for model,field,value,not_found in (
        (TechnicalReport,'owner_user_id',pb.user_id,True),
        (AgentReport,'owner_user_id',None,True),
        (AgentReport,'owner_user_id',pb.user_id,True),
        (AgentReport,'owner_session_id',pb.session_id,False),
        (TechnicalReport,'original_query','tampered',False),
        (TechnicalReport,'stock_name','tampered',False),
        (TechnicalReportChart,'display_order',99,False)):
        async with owned_session(proof) as session:
            condition = model.id == rid if model is TechnicalReport else model.agent_report_id == rid if model is AgentReport else model.report_id == rid
            await session.execute(update(model).where(condition).values(**{field:value}))
            try: value_read = await TechnicalOwnedReportService(session,principal=pa).read(rid)
            except TechnicalStoredPayloadError:
                check(not not_found,'SQL ownership must be invisible')
            else: check(not_found and value_read is None,'projection tamper accepted')
            await session.rollback()
    for action in ('missing_snapshot','wrong_snapshot_owner','missing_index','duplicate_null_index'):
        async with owned_session(proof) as session:
            if action == 'missing_snapshot': await session.execute(delete(TechnicalReportSnapshot).where(TechnicalReportSnapshot.report_id == rid))
            elif action == 'wrong_snapshot_owner':
                snapshot = await session.get(TechnicalReportSnapshot,rid)
                values = {column.key:getattr(snapshot,column.key) for column in TechnicalReportSnapshot.__table__.columns}
                await session.delete(snapshot); await session.flush()
                values['owner_user_id'] = pb.user_id
                session.add(TechnicalReportSnapshot(**values)); await session.flush()
            elif action == 'missing_index': await session.execute(delete(AgentReport).where(AgentReport.agent_type == 'technical',AgentReport.agent_report_id == rid))
            else:
                session.add(AgentReport(id=uuid4(),agent_type='technical',agent_report_id=rid,owner_user_id=None))
                await session.flush()
            check(await TechnicalOwnedReportService(session,principal=pa).read(rid) is None,'missing/duplicate total index/snapshot must be hidden')
            await session.rollback()
    for field,value in (('result_json','{}'),('input_json','{}'),('result_sha256','0'*64),
                        ('request_id',uuid4()),('owner_user_id',pb.user_id),('caller_input_json','{}')):
        async with owned_session(proof) as session:
            try:
                await session.execute(update(TechnicalReportSnapshot).where(TechnicalReportSnapshot.report_id == rid).values(**{field:value}))
            except DBAPIError: await session.rollback()
            else: check(False,'immutable snapshot update accepted')
    groups.append('sql_owner_total_index_snapshot_immutable_projection_tamper')
    for failure in ('child','snapshot','index'):
        candidate,output = storage_fixture(pa.user_id,report_id=uuid4(),request_id=uuid4())
        async with owned_session(proof) as session:
            async def broken_children(*args,**kwargs):
                session.add(kwargs['report']); await session.flush()
                raise RuntimeError('synthetic child write failure')
            original_add = session.add
            def add(obj):
                if (failure == 'snapshot' and isinstance(obj,TechnicalReportSnapshot) or failure == 'index' and isinstance(obj,AgentReport)):
                    raise RuntimeError('synthetic storage write failure')
                original_add(obj)
            with ExitStack() as stack:
                if failure == 'child': stack.enter_context(patch.object(repo,'add_report',broken_children))
                else: stack.enter_context(patch.object(session,'add',add))
                try: await TechnicalOwnedReportService(session,principal=pa).stage(candidate,output)
                except RuntimeError: pass
                else: check(False,'injected staging failure missing')
            await session.rollback()
        check(await scalar(select(func.count()).select_from(TechnicalReport).where(TechnicalReport.id == output.report_id)) == 0,'partial root retained')
    # Concurrent same report: independent valid sessions avoid artificial auth lock waiting.
    one,out = storage_fixture(pa.user_id,report_id=uuid4(),request_id=uuid4())
    original_lookup = repo.storage_root_for_update
    waiting = 0; both_absent = asyncio.Event()
    async def racing_lookup(session,report_id):
        nonlocal waiting
        found = await original_lookup(session,report_id)
        check(found is None,'race must start absent')
        waiting += 1
        if waiting == 2: both_absent.set()
        await asyncio.wait_for(both_absent.wait(),timeout=5)
        return found
    async def contender(principal):
        async with owned_session(proof) as session:
            try:
                await TechnicalOwnedReportService(session,principal=principal).stage(one,out)
                await session.commit(); return 'winner'
            except (IntegrityError,TechnicalReportConflict):
                await session.rollback(); return 'conflict'
    with patch.object(repo,'storage_root_for_update',racing_lookup):
        results = await asyncio.wait_for(asyncio.gather(contender(pa),contender(pa2)),timeout=15)
    check(sorted(results) == ['conflict','winner'],'concurrent winner count')
    check((await read(pa,out.report_id)).frozen == out,'concurrent winner fixed-ID read')
    # Simulate only the caller ACK loss, AFTER a real database commit succeeded.
    class CommitAcknowledgementLost(RuntimeError): pass
    ack_binding,ack_frozen = storage_fixture(pa.user_id,report_id=uuid4(),request_id=uuid4())
    stage_calls = 0
    try:
        async with owned_session(proof) as session:
            stage_calls += 1
            await TechnicalOwnedReportService(session,principal=pa).stage(ack_binding,ack_frozen)
            await session.commit()
            raise CommitAcknowledgementLost()
    except CommitAcknowledgementLost: pass
    with patch.object(TechnicalOwnedReportService,'stage',side_effect=AssertionError('recovery cannot stage')) as restage:
        check((await read(pa2,ack_frozen.report_id)).frozen == ack_frozen,'post-commit ACK loss fixed-ID read')
        check(stage_calls == 1 and restage.call_count == 0,'ACK recovery restaged result')
    # Distinct report ID cannot reuse an already persisted request ID.
    request_conflict,conflict_out = storage_fixture(pa.user_id,report_id=uuid4(),request_id=one.boundary.request_id)
    async with owned_session(proof) as session:
        try: await TechnicalOwnedReportService(session,principal=pa).stage(request_conflict,conflict_out)
        except IntegrityError: await session.rollback()
        else: check(False,'duplicate request ID accepted')
    check((await read(pa2,out.report_id)).frozen == out,'winning stored bytes changed')
    # The history UUID is not a live session FK; remove only this synthetic session.
    async with owned_session(proof) as session:
        await session.execute(delete(AuthSession).where(AuthSession.id == pa.session_id)); await session.commit()
    check((await read(pa2,rid)).frozen == frozen,'old session removal must preserve new-session read')
    groups.append('partial_rollback_concurrent_id_conflict_fixed_id_ack_recovery')
    try: await migration(proof,'c23001a7e0001',downgrade=True)
    except RuntimeError: pass
    else: check(False,'nonempty owned storage downgrade accepted')
    check(await scalar(text('SELECT version_num FROM alembic_version')) == heads[0],'failed downgrade preserves revision')
    legacy_after = await scalar(text('SELECT row_to_json(t)::text FROM technical_reports t WHERE id=:id').bindparams(id=legacy_root.id))
    check(legacy_before == legacy_after,'legacy row rewritten')
    groups.append('nonempty_downgrade_rejected_legacy_unchanged')
    return {'status':'passed','groups':groups,'engine_calls':0,'provider_calls':0,'public_http_calls':0}



async def verify_technical_completion(proof):
    from scripts.runner_owned_database import RunnerOwnedDatabase
    from scripts.cf003_admission_check import isolated_application,check
    if type(proof) is not RunnerOwnedDatabase:raise RuntimeError('Technical completion requires original owned proof')
    proof.verify_ownership()
    with isolated_application(proof) as observed:
        result=await _verify_completion(proof)
        check(not any(observed.values()),'CF050 forbidden I/O')
        return result | {'observed_denials':dict(observed)}


async def _verify_completion(proof):
    import asyncio
    from unittest.mock import patch
    from sqlalchemy import text,select,event
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.ext.asyncio import create_async_engine
    from alembic import command
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from db.models.auth.models import AuthUser
    from db.models.common.stock import Stock
    from db.models.technical.technical_report import TechnicalReport
    from src.modules.auth.application.session_service import issue_session,revoke_session,AuthenticationRequired
    from src.modules.technical.domain.execution_admission import Policy,Intent,TechnicalAdmissionError,TechnicalCompletionError
    from src.modules.technical.application.execution_admission_service import TechnicalAdmissionService as Admission
    from src.modules.technical.application import execution_completion as E
    from src.modules.technical.infrastructure import execution_completion_repository as CR
    from src.modules.analysis.application.coordinator import AnalysisCoordinator
    from scripts.cf002_interactive_login import owned_session,safe_print
    from scripts.cf003_admission_check import check,migration
    groups=[]
    limits=dict(operation='technical.analysis.v1',enabled=True,currency='USD',supported_tickers=['000720'],
        user_daily_limit=100,service_daily_limit=100,daily_budget_nano=1000000,attempt_reserve_nano=10000,
        deadline_seconds=10,model='synthetic-model',service_tier='default',price_id='cf050.synthetic.v1',
        price_evidence_sha256='a'*64,input_nano_per_token=10,output_nano_per_token=20,
        input_token_cap=100,output_token_cap=50,input_byte_cap=1000,output_byte_cap=500,max_calls=4)
    policy=Policy.parse(limits)
    intent=Intent.parse(dict(operation='technical.analysis.v1',ticker='000720',original_query='CF050 synthetic private chart',
        requested_views=['technical'],conditions=dict(profile='technical.multiframe.v1',periods=['3m','1y','5y'])))
    def mark(label):groups.append(label);safe_print({'phase':'cf050_check','label':label,'status':'passed'})
    def coord(session,p,current=policy):return AnalysisCoordinator(session,principal=p,client=None,profile=E.TechnicalCompletionProfile(policy=current))
    async def scalar(query,params=None):
        async with owned_session(proof) as s:return await s.scalar(text(query),params or {})
    async def totals():
        async with owned_session(proof) as s:return tuple((await s.execute(text('SELECT (SELECT count(*) FROM technical_analysis_runs),coalesce((SELECT sum(request_count) FROM technical_usage_periods),0),coalesce((SELECT sum(reserved_nano) FROM technical_usage_periods),0),(SELECT coalesce(sum(held_nano),0) FROM technical_analysis_runs)'))).one())
    async def user():
        async with owned_session(proof) as s:
            owner=AuthUser(id=uuid4());s.add(owner);await s.flush()
            _,p=await issue_session(s,owner);_,a2=await issue_session(s,owner);await s.commit();return p,a2
    async def new_run(p):
        key='cf050-'+str(uuid4())
        async with owned_session(proof) as s:first=await Admission(s,principal=p,policy=policy).admit(key,intent)
        async with owned_session(proof) as s:claimed=await Admission(s,principal=p,policy=policy).dispatch_claim(first.run,first.claim_token)
        check(first.newly_admitted and claimed.newly_claimed,'CF050 original admission and claim ACK')
        async with owned_session(proof) as s:
            row=await CR.owned(s,claimed.run.analysis_id,p.user_id);binding=E.binding_from_sql(row)
        _,frozen=storage_fixture(p.user_id,binding=binding)
        return dict(key=key,first=first,claimed=claimed,binding=binding,frozen=frozen,response=json.loads(frozen.result_json))
    async def receive(p,item,response=None):
        async with owned_session(proof) as s:return await coord(s,p).receive(item['claimed'].run,item['first'].claim_token,item['response'] if response is None else response)
    async def publish(p,item):
        async with owned_session(proof) as s:return await coord(s,p,None).publish(item['claimed'].run.analysis_id)
    async def reconcile(p,item):
        async with owned_session(proof) as s:return await E.reconcile_completion(s,principal=p,analysis_id=item['claimed'].run.analysis_id)
    async def unavailable_stage(*args):raise OSError('fixed synthetic unavailable stage')
    async def ready(p,item):
        with patch.object(E.TechnicalCompletionAdapter,'stage',unavailable_stage):
            try:await receive(p,item)
            except TechnicalCompletionError as error:check(error.code=='SERVICE_UNAVAILABLE','CF050 ready retained')
            else:check(False,'CF050 expected stage unavailable')
        result=await reconcile(p,item);check(result.run.state=='result_ready','CF050 durable ready exists');return result
    async def refused(query,params=None,*,deferred=False):
        async with owned_session(proof) as s:
            executed=False
            try:
                await s.execute(text(query),params or {});executed=True;await s.commit()
            except IntegrityError:
                await s.rollback();check(not deferred or executed,'CF050 deferred refusal after execute');return
            check(False,'CF050 SQL must refuse')
    async def expect_error(call,codes):
        try:await call
        except (TechnicalCompletionError,TechnicalAdmissionError) as error:
            check(error.code in codes,'CF050 fixed refusal');return
        check(False,'CF050 expected fixed refusal')
    async def get_report(p,item):
        async with owned_session(proof) as s:return await E.TechnicalOwnedReportService(s,principal=p).read(item['claimed'].run.report_id)

    config=Config();config.set_main_option('script_location',str(Path(__file__).resolve().parents[1]/'db/migrations'))
    heads=ScriptDirectory.from_config(config).get_heads();check(heads==['c61001a7e0001'],'Composition single migration head')
    check(await scalar('SELECT version_num FROM alembic_version')==heads[0],'CF050 current head')
    async with owned_session(proof) as s:s.add(Stock(stock_code='000720',stock_name='CF050 synthetic canonical',market='KOSPI'));await s.commit()
    p,a2=await user();other,_=await user()
    try:
        async with owned_session(proof) as s:old=await Admission(s,principal=p,policy=policy).admit('cf050-old-row',intent)
    except Exception as error:
        _provider_diagnostic(error,'old_admission');raise

    before=await totals();await migration(proof,'c48001a7e0001',downgrade=True)
    check(not await scalar("SELECT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_name='technical_analysis_runs' AND column_name='accepted_at')"),'CF050 old columns absent')
    class DDLFailure(RuntimeError):pass
    await proof.preflight();engine=create_async_engine(proof.url,connect_args=proof.connection_parameters());reached=[]
    try:
        async with engine.connect() as connection:
            await proof.attest_connection(connection)
            def inject(sync):
                cfg=Config();cfg.set_main_option('script_location',str(Path(__file__).resolve().parents[1]/'db/migrations'))
                cfg.attributes.update(connection=sync,verified_test_mode=True)
                def after(conn,cursor,statement,parameters,context,executemany):
                    if statement.lstrip().upper().startswith('ALTER TABLE TECHNICAL_ANALYSIS_RUNS ADD COLUMN COMPLETION_FORMAT'):
                        reached.append(True);raise DDLFailure('fixed CF050 DDL rollback')
                event.listen(sync,'after_cursor_execute',after)
                try:command.upgrade(cfg,heads[0])
                finally:event.remove(sync,'after_cursor_execute',after)
            try:await connection.run_sync(inject);await connection.commit()
            except DDLFailure:await connection.rollback()
    finally:await engine.dispose()
    check(reached==[True] and await scalar('SELECT version_num FROM alembic_version')=='c48001a7e0001','CF050 same connection DDL rollback')
    check(not await scalar("SELECT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_name='technical_analysis_runs' AND column_name='completion_format')"),'CF050 partial DDL absent')
    await migration(proof,heads[0]);check(await totals()==before,'CF050 old identity/accounting preserved')
    async with owned_session(proof) as s:check((await Admission(s,principal=p).get(old.run.analysis_id)).held_nano==10000,'CF050 old row readable')
    mark('old_row_downgrade_upgrade_same_connection_DDL_rollback')

    normal=await new_run(p);before=await totals();result=await receive(p,normal)
    check(result.run.state=='stored' and result.run.held_nano==10000 and await totals()==before,'CF050 normal same-run stored no extra reservation')
    stored=await get_report(a2,normal)
    check(stored is not None and stored.frozen==normal['frozen'],'CF050 full owner report exact restore')
    id=normal['claimed'].run.analysis_id;rid=normal['claimed'].run.report_id
    check(await scalar('SELECT intent_json IS NULL AND input_json IS NULL AND result_json IS NULL FROM technical_analysis_runs WHERE id=:id',{'id':id}),'CF050 stored raw TEXT consumed')
    check(await scalar("SELECT count(*) FROM agent_reports WHERE agent_type='technical' AND agent_report_id=:id",{'id':rid})==1,'CF050 exact index1')
    check((await receive(p,normal)).run.state=='stored','CF050 exact incoming replay')
    changed=copy.deepcopy(normal['response']);changed['data']['result']['interpretation']['text']='different synthetic result'
    await expect_error(receive(p,normal,changed),{'RESULT_CONFLICT'})
    async with owned_session(proof) as s:
        check(not (await Admission(s,principal=p).dispatch_claim(normal['claimed'].run,normal['first'].claim_token)).newly_claimed,'CF050 completed claim authority false')
    check(await totals()==before and (await get_report(a2,normal)).frozen==normal['frozen'],'CF050 replay read no new work')
    mark('real_coordinator_CF031_CF035_normal_lossless_owner_read_replay_no_new_claim')

    raced=await new_run(p);before=await totals();accepted=[];original_accept=CR.accept
    async def accepted_once(*args):accepted.append(True);return await original_accept(*args)
    async def race():
        try:return await receive(p,raced)
        except TechnicalCompletionError as error:check(error.code=='SERVICE_UNAVAILABLE','CF050 winner publication held');return None
    with patch.object(E.TechnicalCompletionAdapter,'stage',unavailable_stage),patch.object(CR,'accept',accepted_once):
        results=await asyncio.gather(race(),race())
    check(len(accepted)==1 and any(value is not None for value in results),'CF050 two SQL sessions receive winner1')
    check((await reconcile(p,raced)).run.state=='result_ready' and await totals()==before,'CF050 race snapshot atomic no second hold')
    mark('two_SQL_session_receive_single_snapshot_winner1')

    mismatch=await new_run(p);before=await totals()
    for kind in ('owner','A2','token','attempt','policy'):
        actual=other if kind=='owner' else a2 if kind=='A2' else p
        expected=replace(mismatch['claimed'].run,attempt_id=uuid4()) if kind=='attempt' else mismatch['claimed'].run
        token=b'z'*32 if kind=='token' else mismatch['first'].claim_token
        current=Policy.parse(limits|{'deadline_seconds':9}) if kind=='policy' else policy
        async with owned_session(proof) as s:
            await expect_error(coord(s,actual,current).receive(expected,token,mismatch['response']),{'RESOURCE_NOT_FOUND','RESULT_CONTRACT_INVALID','POLICY_UNAVAILABLE'})
    async with owned_session(proof) as s:await s.execute(text("UPDATE stocks SET stock_name='CF050 changed master' WHERE stock_code='000720'"));await s.commit()
    await expect_error(receive(p,mismatch),{'RESULT_CONTRACT_INVALID'})
    async with owned_session(proof) as s:await s.execute(text("UPDATE stocks SET stock_name='CF050 synthetic canonical' WHERE stock_code='000720'"));await s.commit()
    check(await scalar('SELECT state FROM technical_analysis_runs WHERE id=:id',{'id':mismatch['claimed'].run.analysis_id})=='claimed' and await totals()==before,'CF050 untrusted mismatch cannot fail run')
    invalid=await new_run(p);bad=await receive(p,invalid,{'invalid':'result'})
    check(bad.run.state=='failed' and bad.accepted_at is None and bad.error_code=='RESULT_CONTRACT_INVALID','CF050 authenticated invalid response failed without snapshot')
    mark('fresh_owner_A1_token_expected_policy_Stock_invalid_result_fences')

    recovery_owner,recovery_a2=await user();late_ready=await new_run(recovery_owner);late_claim=await new_run(recovery_owner)
    accepted=await ready(recovery_owner,late_ready);original=(accepted.run,accepted.input_sha256,accepted.result_sha256,accepted.binding_sha256,accepted.accepted_at)
    async with owned_session(proof) as s:await revoke_session(s,recovery_owner)
    stamp=await scalar('SELECT clock_timestamp()');end=max(late_ready['claimed'].run.deadline_at,late_claim['claimed'].run.deadline_at)
    await asyncio.sleep(max(0,(end-stamp).total_seconds())+0.03)
    before=await totals()
    async with owned_session(proof) as s:
        check((await coord(s,recovery_a2,None).get(late_ready['claimed'].run.analysis_id)).run.state=='result_ready','CF050 GET after deadline no publish')
    check(await get_report(recovery_a2,late_ready) is None,'CF050 GET kept unposted snapshot')
    completed=await publish(recovery_a2,late_ready)
    check(completed.run.state=='stored' and (completed.input_sha256,completed.result_sha256,completed.binding_sha256,completed.accepted_at)==original[1:],'CF050 same accepted snapshot after deadline')
    check(completed.run.admission_session_id==recovery_owner.session_id,'CF050 original admission session retained')
    check(await scalar('SELECT owner_session_id FROM technical_report_snapshots WHERE report_id=:id',{'id':late_ready['claimed'].run.report_id})==recovery_a2.session_id,'CF050 actual A2 stage session')
    # A1 is revoked. A2 can observe the expired unaccepted run but cannot receive
    # a new snapshot or new claim; the original failure is not made unused.
    late=await receive(recovery_a2,late_claim)
    check(late.run.state=='unknown' and late.accepted_at is None and await totals()==before,'CF050 late unaccepted result refused')
    cancelled=await new_run(p);ready_receipt=await ready(p,cancelled)
    async with owned_session(proof) as s:await Admission(s,principal=a2).close_unknown(cancelled['claimed'].run.analysis_id,'CANCELLED')
    late=await receive(p,cancelled)
    check(late.run.state=='unknown' and late.result_sha256==ready_receipt.result_sha256 and await get_report(a2,cancelled) is None,'CF050 cancelled ready cannot restore/publish')
    mark('DB_clock_expiry_A1_revoked_actual_A2_late_ready_publish_cancelled_late_refused')

    for where in ('before','after'):
        item=await new_run(p);before=await totals()
        async with owned_session(proof) as s:
            original_commit=s.commit
            async def lost():
                if where=='after':await original_commit()
                raise OSError('fixed CF050 snapshot ACK wrapper')
            s.commit=lost
            await expect_error(coord(s,p).receive(item['claimed'].run,item['first'].claim_token,item['response']),{'SERVICE_UNAVAILABLE'})
        check(await totals()==before and await get_report(a2,item) is None,'CF050 snapshot ACK no automatic publication')
        receipt=await reconcile(a2,item)
        check(receipt.run.state==('claimed' if where=='before' else 'result_ready'),'CF050 actual snapshot ACK readonly state')
        if where=='after':check((await publish(a2,item)).run.state=='stored','CF050 snapshot ACK explicit recovery')
    mark('actual_snapshot_commit_before_after_ACK_wrapper_readonly_recovery')

    for where in ('before','after'):
        item=await new_run(p);before=await totals()
        async with owned_session(proof) as s:
            original_commit=s.commit;commits=[]
            async def lost():
                commits.append(True)
                if len(commits)==2:
                    if where=='after':await original_commit()
                    raise OSError('fixed CF050 publication ACK wrapper')
                await original_commit()
            s.commit=lost
            await expect_error(coord(s,p).receive(item['claimed'].run,item['first'].claim_token,item['response']),{'SERVICE_UNAVAILABLE'})
        receipt=await reconcile(a2,item)
        check(receipt.run.state==('result_ready' if where=='before' else 'stored'),'CF050 actual publish ACK readonly state')
        check((await publish(a2,item)).run.state=='stored' and await totals()==before,'CF050 publish ACK explicit same-run recovery')
        check((await get_report(a2,item)).frozen==item['frozen'],'CF050 publish ACK full restore')
    mark('real_publication_root_snapshot_index_state_commit_ACK_recovery')

    item=await new_run(p);before=await totals();original_stage=E.TechnicalCompletionAdapter.stage
    async def stage_cancel(self,session,principal,frozen):
        await original_stage(self,session,principal,frozen);raise asyncio.CancelledError()
    with patch.object(E.TechnicalCompletionAdapter,'stage',stage_cancel):
        async with owned_session(proof) as s:
            try:await coord(s,p).receive(item['claimed'].run,item['first'].claim_token,item['response'])
            except asyncio.CancelledError:pass
            else:check(False,'CF050 automatic publish cancellation propagates')
            check(not s.in_transaction(),'CF050 cancellation rollback before caller context exit')
            async with owned_session(proof) as other_session:
                await other_session.execute(text("SET LOCAL lock_timeout='250ms'"))
                await other_session.execute(text('SELECT id FROM technical_usage_periods WHERE id=:id FOR UPDATE'),{'id':item['claimed'].run.period_id})
    check((await reconcile(a2,item)).run.state=='result_ready' and await get_report(a2,item) is None,'CF050 cancelled uncommitted report absent')
    check((await publish(a2,item)).run.state=='stored' and await totals()==before,'CF050 cancellation explicit snapshot recovery')
    mark('actual_stage_cancel_rollback_session_lock_release_ready_hold_preserved')

    same=await new_run(p);await ready(p,same)
    async with owned_session(proof) as s:
        await E.TechnicalOwnedReportService(s,principal=a2).stage(same['binding'],same['frozen']);await s.commit()
    with patch.object(E.TechnicalCompletionAdapter,'stage',unavailable_stage):await expect_error(publish(a2,same),{'SERVICE_UNAVAILABLE'})
    check((await reconcile(a2,same)).run.state=='result_ready','CF050 same complete stored report transient error is not conflict')
    check((await publish(a2,same)).run.state=='stored','CF050 same complete report explicit exact replay')
    unknown=await new_run(p);await ready(p,unknown)
    async with owned_session(proof) as s:
        await E.TechnicalOwnedReportService(s,principal=a2).stage(unknown['binding'],unknown['frozen']);await s.commit()
    async def unavailable_read(*args):raise OSError('fixed CF050 stored lookup unavailable')
    with patch.object(E.TechnicalCompletionAdapter,'stage',unavailable_stage),patch.object(E.TechnicalOwnedReportService,'read',unavailable_read):
        await expect_error(publish(a2,unknown),{'SERVICE_UNAVAILABLE'})
    check((await reconcile(a2,unknown)).run.state=='result_ready','CF050 unconfirmed lookup preserves ready')
    check((await publish(a2,unknown)).run.state=='stored','CF050 lookup recovery exact replay')
    conflict=await new_run(p);await ready(p,conflict)
    def changed_result(response):response['data']['result']['interpretation']['text']='different committed synthetic result'
    _,different=storage_fixture(p.user_id,binding=conflict['binding'],change=changed_result)
    async with owned_session(proof) as s:
        await E.TechnicalOwnedReportService(s,principal=a2).stage(conflict['binding'],different);await s.commit()
    await refused("UPDATE technical_analysis_runs SET state='stored',intent_json=NULL,input_json=NULL,result_json=NULL,redacted_at=clock_timestamp() WHERE id=:id",{'id':conflict['claimed'].run.analysis_id},deferred=True)
    await expect_error(publish(a2,conflict),{'RESULT_CONFLICT'})
    check((await reconcile(a2,conflict)).run.state=='failed' and (await get_report(a2,conflict)).frozen==different,'CF050 confirmed conflict no report overwrite')
    mark('same_complete_report_vs_confirmed_conflict_vs_unknown_classification')

    # Actual dirty ORM state must be rejected before CF035 populate_existing can
    # refresh it. This is distinct from merely suppressing autoflush.
    async with owned_session(proof) as s:
        root=await s.get(TechnicalReport,rid);root.stock_name='CF050 pending caller change';writes=[]
        def observed(conn,cursor,statement,parameters,context,executemany):
            if statement.lstrip().upper().startswith(('INSERT','UPDATE','DELETE')):writes.append(True)
        event.listen(s.bind.sync_connection,'before_cursor_execute',observed)
        try:
            await expect_error(E.reconcile_completion(s,principal=a2,analysis_id=id),{'CONTEXT_DIRTY'})
            check(root.stock_name=='CF050 pending caller change' and root in s.dirty and not writes,'CF050 pending cache remains unchanged')
        finally:event.remove(s.bind.sync_connection,'before_cursor_execute',observed)
        await s.rollback()
    mark('readonly_reconcile_pending_ORM_no_refresh_flush_or_commit')

    ready_id=raced['claimed'].run.analysis_id;before=await totals()
    for query,params,deferred in (
        ('UPDATE technical_analysis_runs SET accepted_at=accepted_at+interval \'1 microsecond\' WHERE id=:id',{'id':ready_id},False),
        ("UPDATE technical_analysis_runs SET result_sha256=:sha WHERE id=:id",{'id':ready_id,'sha':'f'*64},False),
        ("UPDATE technical_analysis_runs SET state='claimed' WHERE id=:id",{'id':ready_id},False),
        ("UPDATE technical_analysis_runs SET state='stored',intent_json=NULL,input_json=NULL,result_json=NULL,redacted_at=clock_timestamp() WHERE id=:id",{'id':ready_id},True),
        ("UPDATE technical_reports SET owner_user_id=:owner WHERE id=:id",{'id':rid,'owner':other.user_id},True),
        ("UPDATE technical_reports SET final_regime='cf050-changed' WHERE id=:id",{'id':rid},True),
        ("UPDATE technical_reports SET created_at=created_at+interval '1 second' WHERE id=:id",{'id':rid},True),
        ('DELETE FROM technical_reports WHERE id=:id',{'id':rid},True),
        ("UPDATE technical_report_snapshots SET binding_sha256=:sha WHERE report_id=:id",{'id':rid,'sha':'f'*64},False),
        ('DELETE FROM technical_report_snapshots WHERE report_id=:id',{'id':rid},True),
        ("UPDATE agent_reports SET owner_session_id=:session WHERE agent_type='technical' AND agent_report_id=:id",{'id':rid,'session':other.session_id},True),
        ("DELETE FROM agent_reports WHERE agent_type='technical' AND agent_report_id=:id",{'id':rid},True),
        ("INSERT INTO agent_reports(id,agent_type,agent_report_id,owner_user_id) VALUES(:new,'technical',:id,NULL)",{'id':rid,'new':uuid4()},True),
        ('TRUNCATE technical_reports CASCADE',{},False),('TRUNCATE technical_report_snapshots',{},False),('TRUNCATE agent_reports',{},False)):
        await refused(query,params,deferred=deferred)
    check(await totals()==before and (await get_report(a2,normal)).frozen==normal['frozen'],'CF050 direct SQL attacks preserve all accounting/canonical report')
    mark('SQL_accepted_snapshot_terminal_and_stored_root_snapshot_full_index_update_delete_truncate_guards')

    # Wrong binding must fail on the actual receive UPDATE, with fresh active
    # A1/Stock/time, before any publication or deferred stored linkage checks.
    tamper=await new_run(p);frozen=tamper['frozen'];tid=tamper['claimed'].run.analysis_id
    check(await scalar('SELECT clock_timestamp()<deadline_at FROM technical_analysis_runs WHERE id=:id',{'id':tid}),'CF050 tamper active deadline')
    await refused("UPDATE technical_analysis_runs SET state='result_ready',completion_format='technical.result-completion.v1',input_json=:input,input_sha256=:ih,result_json=:result,result_sha256=:rh,binding_sha256=:bad,accepted_at=clock_timestamp() WHERE id=:id",
        {'id':tid,'input':frozen.input_json,'ih':frozen.input_sha256,'result':frozen.result_json,'rh':frozen.result_sha256,'bad':'0'*64})
    check((await reconcile(p,tamper)).accepted_at is None,'CF050 wrong S binding not accepted')
    mark('fresh_SQL_receive_expected_binding_fence_before_publication')
    before=await totals()
    try:await migration(proof,'c48001a7e0001',downgrade=True)
    except RuntimeError:pass
    else:check(False,'CF050 populated completion downgrade must reject')
    check(await scalar('SELECT version_num FROM alembic_version')==heads[0] and await totals()==before,'CF050 populated downgrade retained')
    mark('new_completion_populated_downgrade_refused_old_ledger_unchanged')
    # CF052: keep CF050's already-claimed baseline above; these new fixtures
    # begin admitted-only and exercise the concrete runtime and real AIClient.
    import httpx
    from src.modules.technical.application.execution_runtime import TechnicalExecutionRuntime
    from src.shared.infrastructure.clients.ai_client import AIClient
    runtime_groups=[];synthetic_boundary_invocations=[]
    async def admitted_only(owner):
        key='cf052-'+str(uuid4())
        async with owned_session(proof) as s:first=await Admission(s,principal=owner,policy=policy).admit(key,intent)
        check(first.newly_admitted and first.run.state=='admitted','CF052 admit-only setup')
        async with owned_session(proof) as s:
            row=await CR.owned(s,first.run.analysis_id,owner.user_id);binding=E.binding_from_sql(row)
        _,frozen=storage_fixture(owner.user_id,binding=binding)
        return dict(first=first,binding=binding,frozen=frozen,response=json.loads(frozen.result_json))
    def fixed_client(item,*,mode='ok'):
        async def app(scope,receive,send):
            check(scope['type']=='http' and scope['method']=='POST' and scope['path']=='/internal/technical/boundary' and not scope.get('query_string'),'CF052 exact synthetic ASGI path')
            check(dict(scope['headers']).get(b'x-technical-service-token')==b't'*32,'CF052 synthetic service authentication')
            raw=bytearray()
            while True:
                message=await receive();raw.extend(message.get('body',b''))
                if not message.get('more_body'):break
            check(json.loads(raw)==json.loads(item['binding'].boundary.input_json),'CF052 unchanged B IDs and as_of')
            synthetic_boundary_invocations.append(True)
            if mode=='cancel':raise asyncio.CancelledError()
            if mode=='race_ready':
                owner=item['owner']
                async with owned_session(proof) as s:
                    row=await CR.owned(s,item['first'].run.analysis_id,owner.user_id);claimed=E.run_receipt(row)
                with patch.object(E.TechnicalCompletionAdapter,'stage',unavailable_stage):
                    async with owned_session(proof) as s:
                        await expect_error(coord(s,owner).receive(claimed,item['first'].claim_token,item['response']),{'SERVICE_UNAVAILABLE'})
            status=504 if mode=='timeout' else 503 if mode in {'fail','race_ready'} else 200
            body=json.dumps(item['response']).encode() if status==200 else b'{}'
            await send({'type':'http.response.start','status':status,'headers':[(b'content-type',b'application/json'),(b'content-length',str(len(body)).encode())]})
            await send({'type':'http.response.body','body':body})
        return AIClient('http://technical.synthetic',3,transport=httpx.ASGITransport(app=app),service_token='t'*32)
    def runtime(s,owner,client):return TechnicalExecutionRuntime(s,principal=owner,client=client,policy=policy,enabled=True)
    async def run_once(owner,item,client):
        async with owned_session(proof) as s:return await runtime(s,owner,client).execute_admitted_once(item['first'].run,item['first'].claim_token)
    async def runtime_reconcile(owner,item):
        async with owned_session(proof) as s:return await E.reconcile_completion(s,principal=owner,analysis_id=item['first'].run.analysis_id)
    async def runtime_publish(owner,item):
        async with owned_session(proof) as s:return await coord(s,owner,None).publish(item['first'].run.analysis_id)
    async def runtime_report(owner,item):
        async with owned_session(proof) as s:return await E.TechnicalOwnedReportService(s,principal=owner).read(item['first'].run.report_id)
    def runtime_mark(label):runtime_groups.append(label);mark('CF052_'+label)

    owner,owner_a2=await user();item=await admitted_only(owner);before=await totals();initial=len(synthetic_boundary_invocations)
    client=fixed_client(item)
    results=await asyncio.gather(run_once(owner,item,client),run_once(owner,item,client))
    check(len(synthetic_boundary_invocations)-initial==1 and any(v.run.state=='stored' for v in results),'CF052 actual SQL claim winner sends once')
    check((await runtime_reconcile(owner_a2,item)).run.state=='stored' and (await runtime_report(owner_a2,item)).frozen==item['frozen'],'CF052 A2 complete report lossless')
    check((await run_once(owner,item,client)).run.state=='stored' and len(synthetic_boundary_invocations)-initial==1 and await totals()==before,'CF052 replay no second call or reserve')
    async with owned_session(proof) as s:
        spent=runtime(s,owner,client)
        await spent.execute_admitted_once(item['first'].run,item['first'].claim_token)
        await expect_error(spent.execute_admitted_once(item['first'].run,item['first'].claim_token),{'SERVICE_UNAVAILABLE'})
    runtime_mark('admit_only_actual_runtime_client_ASGI_CF050_CF035_A2_claim_winner1')

    for phase in (1,3,4):
        item=await admitted_only(owner);client=fixed_client(item);before=await totals();initial=len(synthetic_boundary_invocations)
        async with owned_session(proof) as s:
            original=s.commit;commits=[]
            async def lost_runtime_ACK():
                commits.append(True);await original()
                if len(commits)==phase:raise OSError('fixed synthetic runtime ACK loss')
            with patch.object(s,'commit',lost_runtime_ACK):
                await expect_error(runtime(s,owner,client).execute_admitted_once(item['first'].run,item['first'].claim_token),{'ACK_UNKNOWN','SERVICE_UNAVAILABLE'})
        current=await runtime_reconcile(owner_a2,item)
        expected='claimed' if phase==1 else 'result_ready' if phase==3 else 'stored'
        check(current.run.state==expected and len(synthetic_boundary_invocations)-initial==(0 if phase==1 else 1),'CF052 phase-specific real commit ACK recovery')
        if phase==3:check((await runtime_publish(owner_a2,item)).run.state=='stored','CF052 accepted snapshot publishes without rerun')
        if phase!=1:check((await run_once(owner,item,client)).run.state=='stored','CF052 stored ACK recovery returns stored')
        check(await totals()==before and len(synthetic_boundary_invocations)-initial==(0 if phase==1 else 1),'CF052 ACK uncertainty never resets hold or resends')
    runtime_mark('claim_receive_publish_actual_commit_ACK_wrappers_preserve_once_and_hold')

    for mode in ('fail','timeout','cancel','receive_cancel','race_ready'):
        item=await admitted_only(owner);item['owner']=owner;client=fixed_client(item,mode=mode);before=await totals();initial=len(synthetic_boundary_invocations)
        if mode=='receive_cancel':
            async def cancel_receive(*args):raise asyncio.CancelledError()
            with patch.object(E.TechnicalCompletionAdapter,'stage',cancel_receive):
                try:await run_once(owner,item,client)
                except asyncio.CancelledError:pass
                else:check(False,'CF052 receive cancellation must propagate')
        elif mode=='cancel':
            try:await run_once(owner,item,client)
            except asyncio.CancelledError:pass
            else:check(False,'CF052 client cancellation must propagate')
        else:await run_once(owner,item,client)
        current=await runtime_reconcile(owner_a2,item)
        expected='unknown' if mode in {'fail','timeout'} else 'claimed' if mode=='cancel' else 'result_ready'
        check(current.run.state==expected and current.run.held_nano==10000,'CF052 failure phase preserves accepted state/full hold')
        if mode in {'receive_cancel','race_ready'}:check((await runtime_publish(owner_a2,item)).run.state=='stored','CF052 ready cancellation/error recovery no client')
        check(len(synthetic_boundary_invocations)-initial==1 and await totals()==before,'CF052 client vs receive failure no new reserve or retry')
    runtime_mark('client_failure_cancel_receive_cancel_ready_race_fence_preserve_raw_snapshot_hold')
    try:provider_groups=await _verify_provider(proof,policy,intent,user,totals,scalar,refused,mark)
    except Exception as error:
        _provider_diagnostic(error,'provider_connection');raise
    return dict(status='passed',groups=groups,receiving_only=False,baseline_receiving_only=True,
        runtime_groups=runtime_groups,provider_groups=provider_groups,synthetic_boundary_invocations=len(synthetic_boundary_invocations),new_admission_or_claim_in_completion=0,
        provider_calls=0,engine_dispatch=0,compiled_graph_dispatch=0,synthetic_provider_execution_runs=3,mock_provider_HTTP_requests=6,usage_settlement=False,hold_refund=0,
        concurrency='actual two SQL sessions',ACK_loss='wrapper simulation around actual PG commits',
        expiry='actual DB clock',dirty_session='rejected before ORM refresh',fixture='synthetic CF031; no actual engine')

async def _verify_provider(proof,policy,intent,user,totals,scalar,refused,mark):
    """Actual SQL + production clients/ASGI; graph is an explicit synthetic runner.

    Compiled graph/real CF051 definitions are separately verified in graph-unit.
    No dependency sites are united and no provider/market request can connect.
    """
    import asyncio,sys,time,importlib.util,importlib.machinery
    from contextlib import asynccontextmanager
    from dataclasses import fields
    from types import ModuleType,SimpleNamespace as NS
    from unittest.mock import patch
    import httpx
    from fastapi import FastAPI
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError
    from scripts.cf002_interactive_login import owned_session
    from scripts.cf003_admission_check import check,migration
    from scripts import check_safe as pins
    from src.modules.auth.application.session_service import revoke_session
    from src.modules.technical.domain import provider_execution as P
    from src.modules.technical.domain.execution_admission import TechnicalAdmissionError
    from src.modules.technical.application.execution_admission_service import TechnicalAdmissionService as Admission
    from src.modules.technical.application.execution_authority_service import TechnicalExecutionAuthority as Authority,AuthorityUnavailable,AuthorityConflict
    from src.modules.technical.api.execution_authority_router import make_router as authority_router
    from src.modules.technical.application.execution_runtime import TechnicalExecutionRuntime
    from src.modules.technical.application import execution_completion as E
    from src.modules.technical.infrastructure import execution_completion_repository as CR
    from src.shared.infrastructure.clients.ai_client import AIClient
    root=Path(__file__).resolve().parents[2];labels=[]
    # Exercise this revision's own DDL rollback, after the old-row compatibility
    # baseline but before any provider row is admitted. No policy/reset changes.
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import event
    from alembic import command
    from alembic.config import Config
    from scripts.cf002_interactive_login import safe_print
    before_ddl=await totals()
    await migration(proof,'c50001a7e0001',downgrade=True)
    check(not await scalar("SELECT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_name='technical_analysis_runs' AND column_name='execution_grant_digest')"),'CF053 empty additive downgrade before provider data')
    class ProviderDDLFailure(RuntimeError):pass
    await proof.preflight();engine=create_async_engine(proof.url,connect_args=proof.connection_parameters());reached=[]
    try:
        async with engine.connect() as connection:
            await proof.attest_connection(connection)
            def apply(sync):
                config=Config();config.set_main_option('script_location',str(Path(__file__).resolve().parents[1]/'db/migrations'))
                config.attributes.update(connection=sync,verified_test_mode=True)
                def after(conn,cursor,statement,parameters,context,executemany):
                    if statement.lstrip().upper().startswith('ALTER TABLE TECHNICAL_ANALYSIS_RUNS ADD COLUMN EXECUTION_GRANT_DIGEST'):
                        reached.append(True);raise ProviderDDLFailure('fixed CF053 same connection DDL rollback')
                event.listen(sync,'after_cursor_execute',after)
                try:command.upgrade(config,'c53001a7e0001')
                finally:event.remove(sync,'after_cursor_execute',after)
            try:await connection.run_sync(apply);await connection.commit()
            except ProviderDDLFailure:await connection.rollback()
    finally:await engine.dispose()
    check(reached==[True] and await scalar('SELECT version_num FROM alembic_version')=='c50001a7e0001','CF053 partial upgrade rolls back revision and all columns')
    check(not await scalar("SELECT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_name='technical_analysis_runs' AND column_name='execution_configuration_json')"),'CF053 first added column rollback')
    await migration(proof,'c53001a7e0001')
    check(await totals()==before_ddl,'CF053 old rows/holds survive additive migration roundtrip')
    labels.append('own_additive_revision_same_connection_DDL_atomicity_old_rows_hold_preserved')
    mark('CF053_'+labels[-1])

    from src.modules.technical.domain.execution_admission import Intent
    intent=Intent.parse(intent.data()|{'original_query':'현대건설 차트'})
    def passed(label):labels.append(label);mark('CF053_'+label)
    def load(suffix):
        name='src.'+suffix;path=root/'ai/src'/Path(suffix.replace('.','/')+'.py')
        check(hashlib.sha256(path.read_bytes()).hexdigest()==pins.CF053_INPUTS[path.relative_to(root).as_posix()],'CF053 exact selected AI bytes')
        parts=name.split('.')
        for index in range(1,len(parts)):
            parent='.'.join(parts[:index])
            if parent not in sys.modules:
                module=ModuleType(parent);module.__path__=[];module.__spec__=importlib.machinery.ModuleSpec(parent,None,is_package=True);module.__spec__.submodule_search_locations=[str(path.parent)]
                sys.modules[parent]=module
                if index>1:setattr(sys.modules['.'.join(parts[:index-1])],parts[index-1],module)
        if name not in sys.modules:
            spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
            setattr(sys.modules[name.rpartition('.')[0]],name.rpartition('.')[2],module)
        check(Path(sys.modules[name].__spec__.origin).resolve()==path.resolve(),'CF053 AI source origin')
        return sys.modules[name]
    for suffix in ('shared.contracts.agent_envelope','shared.runtime.deadline','agents.technical.domain.intraday_limits',
        'agents.technical.domain.models.enums','agents.technical.domain.models.ohlcv','agents.technical.domain.models.chart','agents.technical.domain.models.intraday','agents.technical.domain.models.contracts','agents.technical.domain.boundary_contracts',
        'supervisor.domain.planning.interpret','supervisor.application.planning.technical_boundary','agents.technical.application.boundary_adapter','agents.technical.application.boundary_runtime','agents.technical.application.engine_bridge','agents.technical.domain.execution_contracts','agents.technical.infrastructure.execution_authority_client','agents.technical.application.execution_runtime','agents.technical.api.routes'):load(suffix)
    AP=sys.modules['src.agents.technical.domain.execution_contracts'];AR=sys.modules['src.agents.technical.application.execution_runtime']
    from tests.unit import test_cf040_technical_runtime_setup as helper
    cfg=P.Configuration.parse(dict(schema_version=P.SCHEMA,policy=policy.data(),counter={'free':True,'mapping':'technical.responses.model-input.v1','version':'synthetic.v1','provenance_sha256':'c'*64,'evidence_sha256':'d'*64},caps={'request':4096,'count':4096,'generation':1048576},ai_origin='https://ai.invalid',authority_origin='https://backend.invalid',cache_mode='none',trace_mode='none'))
    async def sessions():
        async with owned_session(proof) as session:yield session
    backend=FastAPI();backend.include_router(authority_router(session_factory=sessions,configuration=lambda:cfg,token=lambda:'b'*32))
    authority_client=sys.modules['src.agents.technical.infrastructure.execution_authority_client'].ExecutionAuthorityClient(origin=cfg.data()['authority_origin'],token='b'*32,transport=httpx.ASGITransport(app=backend))
    template=json.loads(storage_fixture(uuid4())[1].result_json)['data']['result'];factory_calls=[];runner_calls=[];credential_calls=[];runner_mode=['normal']
    sdk=helper.official_adapter(defer=True);sdk.a['time']=time
    def factory(**kwargs):factory_calls.append(kwargs['request_budget']);return sdk.a['official_count_openai_client'](**kwargs)
    llm=NS(TechnicalLlmPolicy=sdk.a['TechnicalLlmPolicy'],TechnicalRequestLlmBudget=sdk.a['TechnicalRequestLlmBudget'],official_count_openai_client=factory)
    def synthetic_runner(payload,**kwargs):
        runner_calls.append(payload.request_id);kwargs['llm_client'].complete('synthetic SQL ASGI accounting evidence')
        result=copy.deepcopy(template);result.update(request_id=payload.request_id,trace_id=kwargs['trace_id'],ticker=payload.ticker,as_of=payload.as_of.isoformat(),resolved_stock_name=payload.stock_name)
        if runner_mode[0]=='invalid':result['ticker']='999999'
        return result
    def credential():credential_calls.append(True);return 'synthetic-not-a-provider-key'
    opts=AR.ExecutionOptions(AP.Configuration(cfg.text),'a'*32,'b'*32,credential,lambda *a,**k:{},None,None)
    ai_runtime=AR.TechnicalProviderRuntime(opts,agent_module=NS(run_technical_agent=synthetic_runner),steps_module=NS(INTRADAY_FETCH_ENABLED=False),llm_module=llm,authority=authority_client)
    ai=FastAPI();ai.state.technical_execution_runtime=ai_runtime;ai.include_router(sys.modules['src.agents.technical.api.routes'].make_router())
    client=AIClient('https://ai.invalid',10,httpx.ASGITransport(app=ai),execution_token='a'*32)
    definition=await scalar("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid='technical_analysis_runs'::regclass AND conname='cf048_run_spec'")
    check(P.SPEC_SHA256 in definition and P.SPEC_JSON.encode().hex() in definition,'CF053 byte-safe new spec CHECK retained after downgrade refusal')
    check(await scalar('SELECT version_num FROM alembic_version')=='c53001a7e0001','CF053 head retained before provider admission')
    p,a2=await user();other,_=await user();before=await totals()
    async with owned_session(proof) as session:
        runtime=TechnicalExecutionRuntime(session,principal=p,client=client,policy=policy,enabled=True)
        first=await runtime.admit_provider_once('cf053-runtime',intent,cfg)
        result=await runtime.execute_provider_once(first.run,first.claim_token,cfg)
        if result.run.state!='stored':
            from scripts.cf002_interactive_login import safe_print
            safe_print({'phase':'cf053_runtime_state','state':result.run.state,'reason':result.run.unknown_reason,'runner_count':len(runner_calls),'factory_count':len(factory_calls),'credential_count':len(credential_calls),'fake_provider_http_count':len(sdk.sent)})
        check(result.run.state=='stored','CF053 actual Backend runtime through AI ASGI stored')
    check(len(runner_calls)==len(factory_calls)==len(credential_calls)==1 and len(sdk.sent)==2,'CF053 actual one runtime/start/budget/fake pair')
    async with owned_session(proof) as session:
        stored=await E.TechnicalOwnedReportService(session,principal=a2).read(first.run.report_id)
        check(stored.frozen.result_schema==P.SCHEMA,'CF053 A2 controlled internal restore')
        check(await E.TechnicalOwnedReportService(session,principal=a2).read_projection(first.run.report_id) is None,'CF053 public detail404')
        check(str(first.run.report_id) not in [x['report_id'] for x in (await E.TechnicalOwnedReportService(session,principal=a2).list_owned(limit=20))['items']],'CF053 public SQL list/pagination excludes controlled')
        check(await E.TechnicalOwnedReportService(session,principal=other).read(first.run.report_id) is None,'CF053 wrong owner404')
    check(await scalar('SELECT execution_started_at IS NOT NULL AND execution_evidence_json IS NOT NULL AND held_nano=reserved_nano FROM technical_analysis_runs WHERE id=:id',{'id':first.run.analysis_id}),'CF053 independent evidence durable/full hold')
    saved=await scalar('SELECT execution_evidence_json FROM technical_analysis_runs WHERE id=:id',{'id':first.run.analysis_id})
    check(json.loads(saved)['records'][0]['usage']==[12,3,15],'CF053 usage independently preserved')
    passed('actual_Backend_ready_claim_AI_route_budget_Bridge_callback_SQL_receive_storage_A2_public_exclusion')

    async def pending(owner,key):
        async with owned_session(proof) as s:f=await Admission(s,principal=owner,policy=policy).admit_provider(key,intent,cfg)
        async with owned_session(proof) as s:c=await Admission(s,principal=owner,policy=policy).dispatch_provider_claim(f.run,f.claim_token,cfg)
        return f,c,P.decode(c.execution_json)
    async def start(owner,claim,execution,executor=None):
        body={'schema_version':P.SCHEMA,'analysis_id':str(claim.run.analysis_id),'control_sha256':execution['control_sha256'],'executor_id':executor or str(uuid4())}
        async with owned_session(proof) as s:return await Authority(s,configuration=cfg).start(body,claim.grant)
    # A malformed graph result must not erase independently observed usage.
    runner_mode[0]='invalid'
    try:
        async with owned_session(proof) as session:
            runtime=TechnicalExecutionRuntime(session,principal=p,client=client,policy=policy,enabled=True)
            bad=await runtime.admit_provider_once('cf053-invalid-result',intent,cfg)
            rejected=await runtime.execute_provider_once(bad.run,bad.claim_token,cfg)
        check(rejected.run.state=='unknown' and rejected.run.held_nano==10000,'CF053 invalid result closes unknown/full hold')
        check(await scalar("SELECT accepted_at IS NULL AND execution_evidence_json IS NOT NULL AND execution_evidence_json::jsonb->>'outcome'='failed' FROM technical_analysis_runs WHERE id=:id",{'id':bad.run.analysis_id}),'CF053 invalid result preserves durable usage independently')
        async with owned_session(proof) as session:check(await E.TechnicalOwnedReportService(session,principal=a2).read(bad.run.report_id) is None,'CF053 invalid result not published')
        check(len(runner_calls)==2 and len(factory_calls)==2 and len(sdk.sent)==4,'CF053 each run has one isolated budget and pair')
    finally:runner_mode[0]='normal'
    passed('invalid_result_no_storage_but_independent_usage_commit_and_full_hold')
    dispatch_count=len(runner_calls)
    f,c,x=await pending(p,'cf053-race');race=await asyncio.gather(start(p,c,x),start(p,c,x))
    check(sum(r['newly_started'] for r in race)==1,'CF053 two SQL sessions only first start ACK fresh')
    winning=next(r for r in race if r['newly_started']);check(not (await start(p,c,x,winning['executor_id']))['newly_started'],'CF053 same executor replay never authority')
    passed('two_actual_SQL_start_workers_winner1_replay_false')
    # Tampering reaches the new strict SQL guard, not an immutable-row or
    # deferred-period-count refusal. Each clone is a fresh admitted INSERT.
    from db.models.technical.execution_admission import TechnicalAnalysisRun as Run
    from sqlalchemy import select,insert
    async with owned_session(proof) as session:
        original=dict((await session.execute(select(Run.__table__).where(Run.id==c.run.analysis_id))).mappings().one())
    for cap in ('request','count','generation'):
        for bad in (None,'4096',4096.0,True):
            changed=cfg.data();changed['caps'][cap]=bad;values=dict(original)
            values.update(id=uuid4(),admission_request_id=uuid4(),attempt_id=uuid4(),planned_report_id=uuid4(),boundary_request_id=uuid4(),trace_id=uuid4(),key_digest=hashlib.sha256(str(uuid4()).encode()).digest(),claim_digest=hashlib.sha256(str(uuid4()).encode()).digest(),state='admitted',claim_consumed_at=None,
                execution_configuration_json=P.canonical(changed),execution_configuration_sha256=P.sha(P.canonical(changed)))
            for column in Run.__table__.columns:
                if column.name.startswith('execution_') and column.name not in {'execution_configuration_json','execution_configuration_sha256'}:values[column.name]=None
            async with owned_session(proof) as session:
                from sqlalchemy import func
                stamp=await session.scalar(select(func.clock_timestamp()))
                values.update(as_of=stamp,started_at=stamp,deadline_at=stamp+timedelta(seconds=policy.data()['deadline_seconds']))
                executed=False
                try:await session.execute(insert(Run).values(**values));executed=True
                except IntegrityError as error:
                    check('CF053 strict cap' in str(error),'CF053 exact strict cap guard; no unrelated constraint masking')
                    await session.rollback()
                else:check(False,'CF053 malformed cap must fail at INSERT before deferred totals')
                check(not executed,'CF053 strict cap rejection not masked by deferred sum')
    passed('strict_SQL_caps_null_string_float_bool_direct_fresh_INSERT')
    # Provider completion metadata is mandatory even when all CF050 hashes,
    # IDs, accepted state, and canonical bytes are otherwise consistent.
    from src.modules.analysis.domain.contracts import FrozenAnalysisResult
    async with owned_session(proof) as session:
        row=await CR.owned(session,c.run.analysis_id,p.user_id);binding=E.binding_from_sql(row)
    raw=copy.deepcopy(template);b=x['boundary_request'];raw.update(request_id=b['request_id'],trace_id=b['trace_id'],ticker=b['data']['stock']['stock_code'],as_of=b['data']['requested_as_of'],resolved_stock_name=b['data']['stock']['stock_name'])
    response=P.result(b,raw,{k:winning[k] for k in ('control_sha256','start_sha256','executor_id')})
    valid=E.TechnicalCompletionAdapter(binding).validate_and_freeze(response)
    for key in ('control_sha256','start_sha256','executor_id'):
        for missing in (True,False):
            bad=copy.deepcopy(response)
            if missing:del bad['data'][key]
            else:bad['data'][key]=None
            frozen=FrozenAnalysisResult.freeze(context=valid.context,report_id=valid.report_id,input_schema=valid.input_schema,result_schema=valid.result_schema,input_json=valid.input_json,result_json=P.canonical(bad))
            async with owned_session(proof) as session:
                row=await CR.owned(session,c.run.analysis_id,p.user_id)
                try:
                    adopted=await CR.accept(session,row,hashlib.sha256(f.claim_token).digest(),frozen)
                    check(adopted is not None,'CF053 test reaches live original deadline')
                    await session.commit()
                except IntegrityError:await session.rollback()
                else:check(False,'CF053 missing/null controlled metadata must deny')
    passed('controlled_metadata_missing_null_SQL_accept_rejected_all3')
    for key in ('request_sha256','prompt_sha256','projection_sha256'):
        evidence=json.loads(saved);evidence.update(analysis_id=str(c.run.analysis_id),attempt_id=str(c.run.attempt_id),control_sha256=x['control_sha256'],start_sha256=winning['start_sha256'],executor_id=winning['executor_id'])
        evidence['records'][0].update(analysis_id=str(c.run.analysis_id),attempt_id=str(c.run.attempt_id));evidence['records'][0][key]=int('1'*64)
        value=P.canonical(evidence)
        await refused('UPDATE technical_analysis_runs SET execution_evidence_json=:body,execution_evidence_sha256=:sha,execution_observed_at=clock_timestamp() WHERE id=:id',{'body':value,'sha':P.sha(value),'id':c.run.analysis_id})
    passed('numeric_digest_direct_SQL_observation_rejected_all3')

    body={'schema_version':P.SCHEMA,'analysis_id':str(c.run.analysis_id),'control_sha256':x['control_sha256'],'executor_id':str(uuid4())}
    async with owned_session(proof) as s:
        # Already-started replay is False even when simulated ACK is lost.
        commit=s.commit
        async def lost():await commit();raise OSError('fixed synthetic ACK unknown')
        with patch.object(s,'commit',lost):
            try:await Authority(s,configuration=cfg).start(body,c.grant)
            except AuthorityUnavailable:pass
            else:check(False,'CF053 lost ACK must not return capability')
    check(not (await start(p,c,x))['newly_started'] and len(runner_calls)==dispatch_count,'CF053 ACK unknown no graph replay')
    passed('start_ACK_unknown_and_restart_no_new_invocation')
    af,ac,ax=await pending(p,'cf053-first-start-ACK-loss')
    body={'schema_version':P.SCHEMA,'analysis_id':str(ac.run.analysis_id),'control_sha256':ax['control_sha256'],'executor_id':str(uuid4())}
    async with owned_session(proof) as session:
        original_commit=session.commit
        async def lost_first_ACK():await original_commit();raise OSError('fixed first start ACK unknown')
        with patch.object(session,'commit',lost_first_ACK):
            try:await Authority(session,configuration=cfg).start(body,ac.grant)
            except AuthorityUnavailable:pass
            else:check(False,'CF053 first start ACK lost never returns fresh capability')
    check(await scalar('SELECT execution_started_at IS NOT NULL AND held_nano=reserved_nano FROM technical_analysis_runs WHERE id=:id',{'id':ac.run.analysis_id}),'CF053 first start commit retained after ACK loss')
    check(not (await start(p,ac,ax,body['executor_id']))['newly_started'] and len(runner_calls)==dispatch_count,'CF053 lost first ACK restart cannot execute')
    # New-spec claim/grant ACK loss never returns/reconstructs its raw grant.
    async with owned_session(proof) as session:gf=await Admission(session,principal=p,policy=policy).admit_provider('cf053-grant-ACK-loss',intent,cfg)
    async with owned_session(proof) as session:
        original_commit=session.commit
        async def lost_grant_ACK():await original_commit();raise OSError('fixed grant ACK unknown')
        with patch.object(session,'commit',lost_grant_ACK):
            try:await Admission(session,principal=p,policy=policy).dispatch_provider_claim(gf.run,gf.claim_token,cfg)
            except TechnicalAdmissionError as error:check(error.code=='ACK_UNKNOWN','CF053 claim grant ACK unknown fixed')
            else:check(False,'CF053 claim/grant ACK loss cannot return authority')
    async with owned_session(proof) as session:
        replay=await Admission(session,principal=p,policy=policy).dispatch_provider_claim(gf.run,gf.claim_token,cfg)
        check(not replay.newly_claimed and replay.grant is None and replay.execution_json is None,'CF053 grant never recovered after ambiguous ACK')
    check(await scalar('SELECT execution_grant_digest IS NOT NULL AND execution_started_at IS NULL AND held_nano=reserved_nano FROM technical_analysis_runs WHERE id=:id',{'id':gf.run.analysis_id}),'CF053 consumed grant/hold remains unstarted')
    passed('fresh_start_and_claim_grant_actual_commit_ACK_losses_no_reissue_no_execution')

    revoked,_=await user();rf,rc,rx=await pending(revoked,'cf053-revoke-before')
    async with owned_session(proof) as s:await revoke_session(s,revoked)
    try:await start(revoked,rc,rx)
    except (AuthorityUnavailable,Exception) as error:
        from src.modules.auth.application.session_service import AuthenticationRequired
        check(type(error) in {AuthorityUnavailable,AuthenticationRequired},'CF053 revoked original session start denied')
    else:check(False,'CF053 revoked start must deny')
    # A consumed start can still record its same evidence after revocation.
    async with owned_session(proof) as s:await revoke_session(s,p)
    remaining=await scalar('SELECT greatest(0,extract(epoch FROM deadline_at-clock_timestamp())) FROM technical_analysis_runs WHERE id=:id',{'id':c.run.analysis_id})
    await asyncio.sleep(min(11,float(remaining)+.02))
    check(await scalar('SELECT clock_timestamp()>=deadline_at FROM technical_analysis_runs WHERE id=:id',{'id':c.run.analysis_id}),'CF053 record-only observation after original deadline')
    observation={'schema_version':'technical.usage.v1','analysis_id':str(c.run.analysis_id),'attempt_id':str(c.run.attempt_id),'policy_sha256':c.run.policy_sha256,'control_sha256':x['control_sha256'],'start_sha256':winning['start_sha256'],'executor_id':winning['executor_id'],'outcome':'unknown','records':[]}
    ob={'schema_version':P.SCHEMA,'analysis_id':str(c.run.analysis_id),'control_sha256':x['control_sha256'],'start_sha256':winning['start_sha256'],'executor_id':winning['executor_id'],'evidence':observation,'evidence_sha256':P.sha(P.canonical(observation))}
    async with owned_session(proof) as session:
        original_commit=session.commit
        async def lost_observe_ACK():await original_commit();raise OSError('fixed observe ACK unknown')
        with patch.object(session,'commit',lost_observe_ACK):
            try:await Authority(session).observe(ob,c.grant)
            except AuthorityUnavailable:pass
            else:check(False,'CF053 observation commit ACK uncertainty fixed')
    check(await scalar('SELECT execution_evidence_json IS NOT NULL AND held_nano=reserved_nano FROM technical_analysis_runs WHERE id=:id',{'id':c.run.analysis_id}),'CF053 observation ACK loss preserves record and hold')
    async with owned_session(proof) as s:check((await Authority(s).observe(ob,c.grant))['recorded'],'CF053 exact evidence ACK replay')
    changed=copy.deepcopy(ob);changed['evidence']['outcome']='failed';changed['evidence_sha256']=P.sha(P.canonical(changed['evidence']))
    async with owned_session(proof) as s:
        try:await Authority(s).observe(changed,c.grant)
        except AuthorityConflict:pass
        else:check(False,'CF053 different late evidence conflict')
    passed('revoked_before_start_denied_after_start_observe_only_replay_conflict_full_hold')
    await refused('UPDATE technical_analysis_runs SET execution_evidence_json=NULL,execution_evidence_sha256=NULL,execution_observed_at=NULL WHERE id=:id',{'id':c.run.analysis_id})
    await refused('DELETE FROM technical_analysis_runs WHERE id=:id',{'id':c.run.analysis_id})
    await refused('UPDATE technical_analysis_runs SET execution_executor_id=:other WHERE id=:id',{'id':c.run.analysis_id,'other':uuid4()})
    passed('direct_SQL_start_evidence_mutation_delete_denied')
    before_downgrade=await totals()
    try:await migration(proof,'c50001a7e0001',downgrade=True)
    except RuntimeError:pass
    else:check(False,'CF053 provider data blocks downgrade')
    check(await totals()==before_downgrade and await scalar('SELECT version_num FROM alembic_version')=='c53001a7e0001','CF053 downgrade refusal preserves provider/old rows and all holds')
    passed('provider_populated_downgrade_refused_before_drop_preserves_all_accounting')

    await migration(proof,'c54001a7e0001')
    await _verify_supervisor_handoff(proof,cfg,policy,ai,client,backend,runner_calls,factory_calls,mark,scalar,refused,totals,load)
    await migration(proof,'c60001a7e0001')
    legacy=await _verify_composition(proof,cfg,policy,mark,scalar,refused,totals)
    await migration(proof,'c61001a7e0001')
    await _verify_composition_runtime(proof,cfg,policy,ai,client,runner_calls,sdk,runner_mode,legacy,mark,scalar,totals)
    return labels


def _provider_diagnostic(error,stage):
    """Bounded synthetic PG diagnosis; never SQL, parameters, messages or secrets."""
    from scripts.cf002_interactive_login import safe_print
    rows=[];seen=set()
    while error is not None and id(error) not in seen and len(rows)<8:
        seen.add(id(error));row={'kind':type(error).__name__ if type(error).__name__ in {'TechnicalAdmissionError','AttributeError','NameError','ProgrammingError','IntegrityError','DataError'} else 'other'}
        code=getattr(error,'code',None)
        if code in {'UNAVAILABLE','ACK_UNKNOWN','STORED_INVALID','CONTEXT_DIRTY','CLAIM_DENIED','POLICY_UNAVAILABLE'}:row['code']=code
        state=getattr(error,'sqlstate',None)
        if type(state) is str and len(state)==5 and state.isalnum():row['sqlstate']=state
        frames=[];trace=error.__traceback__
        while trace is not None:
            filename=Path(trace.tb_frame.f_code.co_filename)
            if filename.name in {'execution_admission_service.py','execution_authority_service.py','execution_runtime.py','provider_execution.py','execution_contracts.py','cf035_technical_owned_check.py','execution_completion.py','owned_report_service.py'}:
                frames.append({'source':filename.name,'function':trace.tb_frame.f_code.co_name,'line':trace.tb_lineno})
            trace=trace.tb_next
        if frames:row['frames']=frames[-6:]
        constraint=getattr(error,'constraint_name',None)
        if type(constraint) is str and constraint.startswith(('cf053_','cf048_','ck_technical_')) and len(constraint)<100 and all(ch.isalnum() or ch=='_' for ch in constraint):row['constraint']=constraint
        tags=('CF053 evidence binding','CF053 configuration types','CF053 counter shape','CF053 strict cap','CF053 configuration','CF053 starts unconsumed','CF053 old run unchanged','CF048 fresh admission identity','CF048 run period binding')
        for tag in tags:
            if tag in str(error):row['fixed_guard']=tag;break
        rows.append(row);error=getattr(error,'orig',None) or error.__context__
    safe_print({'phase':'cf053_bounded_diagnostic','stage':stage,'errors':rows})

async def _verify_supervisor_handoff(proof,cfg,policy,ai,client,backend,runner_calls,factory_calls,mark,scalar,refused,totals,load):
    """CF054 real auth/SQL/public Backend -> AI deterministic planner -> CF053 synthetic runner."""
    import asyncio
    from contextlib import ExitStack
    from unittest.mock import patch
    import httpx
    from sqlalchemy import select,func,text
    from db.models.auth.models import AuthUser
    from db.models.supervisor.request_binding import SupervisorRequestBinding as Binding
    from db.models.technical.execution_admission import TechnicalAnalysisRun as Run
    from db.session import get_session
    from src.api.main import app
    from src.shared.config import settings
    from src.modules.auth.api import router as auth
    from src.modules.auth.application.session_service import issue_session,csrf_token,revoke_session
    from src.modules.supervisor.api import router as core
    from src.modules.supervisor.application.technical_service import TechnicalSupervisorService as Service
    from src.modules.supervisor.domain import technical_core_contracts as C
    from src.modules.supervisor.domain.technical_projection import fixed_key
    from src.modules.supervisor.infrastructure import repository as bindings
    from src.modules.technical.application.execution_admission_service import TechnicalAdmissionService as Admission
    from src.modules.technical.application.execution_runtime import TechnicalExecutionRuntime
    from src.modules.technical.application.execution_authority_service import TechnicalExecutionAuthority as Authority
    from src.modules.technical.domain.execution_admission import Intent,TechnicalAdmissionError
    from src.modules.technical.domain import provider_execution as P
    from scripts.cf002_interactive_login import owned_session
    from scripts.cf003_admission_check import check,migration
    from src.shared.infrastructure.clients.ai_client import AIClient
    for suffix in ('supervisor.domain.meaning','supervisor.domain.core_contracts','supervisor.domain.meaning_proposals','supervisor.application.meaning_policy','supervisor.domain.technical_core_contracts','supervisor.application.planning.technical_core','supervisor.api.routes'):load(suffix)
    import sys
    ai.include_router(sys.modules['src.supervisor.api.routes'].make_router(technical=True))
    async def identity(owner=None):
        async with owned_session(proof) as s:
            if owner is None:owner=AuthUser(id=uuid4());s.add(owner);await s.flush()
            cookie,p=await issue_session(s,owner);await s.commit();return cookie,p
    a=await identity()
    async with owned_session(proof) as s:owner=await s.get(AuthUser,a[1].user_id)
    a2=await identity(owner);b=await identity()
    mode=['normal'];target=[None];injected=[False];planning=[]
    async def sessions():
        async with owned_session(proof) as s:
            original=s.commit
            async def commit():
                if target[0] is not None and not injected[0] and mode[0] in {'binding_ack','admission_ack','link_ack'}:
                    await s.flush()  # Match commit's flush before inspecting the exact ACK stage.
                    row=await bindings.technical_read(s,a[1].user_id,key=target[0])
                    exists=row is not None
                    if exists and mode[0]=='admission_ack':exists=await s.scalar(select(Run.id).where(Run.key_digest==row.technical_key_digest,Run.owner_user_id==row.owner_user_id)) is not None and row.technical_run_id is None
                    if exists and mode[0]=='link_ack':exists=row.technical_run_id is not None
                    if exists:await original();injected[0]=True;raise OSError('fixed CF054 commit ACK loss')
                await original()
            s.commit=commit;yield s
    transport=httpx.ASGITransport(app=ai)
    def client_factory(*args,**kwargs):return AIClient(cfg.data()['ai_origin'],125,transport=transport,execution_token='a'*32)
    async def call(method,path,body=None,who=None,headers=None):
        cookie,p=who or a
        h={'origin':'http://localhost:3200','cookie':auth.SESSION_COOKIE+'='+cookie,'x-csrf-token':csrf_token(p)}|(headers or {})
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://localhost:8200') as c:return await c.request(method,path,json=body,headers=h)
    base='/api/supervisor/core/technical'
    def data(response,status=200):
        check(response.status_code==status,'CF054 public HTTP status')
        value=response.json();check(value['schema_version']==C.VERSION and value['error'] is None and response.headers.get('cache-control')=='private, no-store','CF054 closed private envelope');return value['data']
    def error(response,status,code=None):
        check(response.status_code==status,'CF054 fixed failure status');value=response.json();check(value['data'] is None and value['error']['message']=='Supervisor request unavailable' and value['schema_version']==C.VERSION,'CF054 safe failure')
        if code is not None:check(value['error']['code']==code,'CF054 safe error code')
    query='000720 외국인 제외 3주 차트'
    draft={'original_query':query,'answers':[],'revision':0}
    async def prepare():
        planning.append(True);return data(await call('POST',base+'/prepare',draft))
    def confirm(plan,key=None):return dict(client_key=key or str(uuid4()),draft=copy.deepcopy(draft),expected_plan_hash=plan['plan_hash'],consent=dict(allow_technical=True,allow_partial=True,waived_conditions=list(plan['required_waivers'])))
    async def binding_for(body):
        async with owned_session(proof) as s:return await bindings.technical_read(s,a[1].user_id,key=hashlib.sha256(body['client_key'].encode()).digest())
    original_overrides=dict(app.dependency_overrides);app.dependency_overrides[get_session]=sessions
    try:
      with ExitStack() as stack:
        for name,value in dict(AI_SERVICE_URL=cfg.data()['ai_origin'],FLOW_ANALYSIS_ENABLED=True,TECHNICAL_EXECUTION_ENABLED='true',TECHNICAL_EXECUTION_CONFIG=cfg.text,TECHNICAL_EXECUTION_AI_SERVICE_TOKEN='a'*32,TECHNICAL_EXECUTION_AUTHORITY_TOKEN='b'*32).items():stack.enter_context(patch.object(settings,name,value))
        stack.enter_context(patch.object(core,'AIClient',client_factory))
        before=await totals();starts=len(runner_calls)
        from db.models.common.stock_alias import StockAlias
        from src.modules.stocks.domain.text_normalize import normalize_stock_text
        async with owned_session(proof) as s:
            s.add(StockAlias(stock_code='000720',alias='대우전자',normalized_alias=normalize_stock_text('대우전자'),alias_type='alias'));await s.commit()
        error(await call('POST',base+'/prepare',dict(original_query='대우전자 말고 000720 차트',answers=[],revision=0)),422,'INPUT_INVALID')
        error(await call('POST',base+'/prepare',draft,headers={'cookie':''}),401,'AUTH_REQUIRED')
        error(await call('POST',base+'/prepare',draft,headers={'x-csrf-token':'bad'}),401,'AUTH_REQUIRED')
        error(await call('POST',base+'/prepare?unexpected=1',draft),422,'INPUT_INVALID')
        check(await totals()==before and len(runner_calls)==starts,'CF054 negated canonical alias/auth/query denied before admission')
        mark('CF054_negated_alias_canonical_master_and_public_auth_fences')
        plan=await prepare();check(plan['selected_views']==['technical'] and plan['partial'] and len(plan['required_waivers'])==2,'CF054 exact conditions retained as two waivers')
        body=confirm(plan)
        bad=copy.deepcopy(body);bad['consent']['waived_conditions']=[];error(await call('POST',base+'/requests',bad),422,'INPUT_INVALID')
        bad=copy.deepcopy(body);bad['expected_plan_hash']='f'*64;error(await call('POST',base+'/requests',bad),409,'PLAN_STALE')
        check(await totals()==before and len(runner_calls)==starts,'CF054 invalid consent/hash admission0')
        responses=await asyncio.gather(call('POST',base+'/requests',body),call('POST',base+'/requests',body))
        check(all(r.status_code in {200,202} for r in responses),'CF054 concurrent confirms safe')
        current=await binding_for(body);result=data(await call('GET',base+'/requests/'+str(current.id)))
        check(result['technical']['state']=='stored' and result['technical']['report_id'] is not None and result['technical']['report_url'] is None and result['coverage']=='partial','CF054 stored internal reference no public URL')
        check(result['effective_scope']['waived_conditions']==plan['required_waivers'] and len(runner_calls)==starts+1,'CF054 graph once and exact waivers')
        after=await totals();check(after[0]==before[0]+1 and after[1]==before[1]+1 and after[2]==before[2]+policy.data()['attempt_reserve_nano'] and after[3]==before[3]+policy.data()['attempt_reserve_nano'],'CF054 one admission/hold')
        mark('CF054_public_prepare_concurrent_confirm_admission_link_start_store_once')
        with patch.object(settings,'TECHNICAL_EXECUTION_ENABLED',False),patch.object(settings,'TECHNICAL_EXECUTION_CONFIG',''),patch.object(settings,'FLOW_ANALYSIS_ENABLED',False):
            check(data(await call('GET',base+'/requests/'+str(current.id),who=a2))==result,'CF054 A2 settings-off readonly same owner result')
            check(data(await call('POST',base+'/requests',body,who=a2))==result,'CF054 same-key A2 no replan/admission')
        error(await call('GET',base+'/requests/'+str(current.id),who=b),404,'RESOURCE_NOT_FOUND')
        old_get=await call('GET','/api/supervisor/core/requests/'+str(current.id));check(old_get.status_code==404,'CF054 old Flow GET hides Technical target')
        flow_body=dict(client_key=body['client_key'],draft=draft,expected_plan_hash=plan['plan_hash'],consent=dict(allow_flow=True,allow_partial=True,waived_conditions=[]))
        check((await call('POST','/api/supervisor/core/requests',flow_body)).status_code==409,'CF054 Flow confirm cannot adopt Technical key')
        check(await totals()==after and len(runner_calls)==starts+1,'CF054 all replays/read new work0')
        mark('CF054_A2_B_cross_target_settings_off_readonly_replay_hold_unchanged')
        # Opposite target uses a valid old SQL binding; no fake Flow execution.
        flow_id=uuid4();flow_client=str(uuid4());flow_text=C.canonical({'idempotency_key':str(flow_id)})
        async with owned_session(proof) as s:
            from src.modules.technical.infrastructure import execution_admission_repository as R
            stamp=await R.clock(s)
            await bindings.admit(s,dict(id=flow_id,owner_user_id=a[1].user_id,client_key_digest=hashlib.sha256(flow_client.encode()).digest(),confirm_digest='a'*64,plan_json='{}',plan_sha256=P.sha('{}'),flow_input_json=flow_text,flow_sha256=P.sha(flow_text),flow_key_digest=hashlib.sha256(str(flow_id).encode()).digest(),confirmed_at=stamp,handoff_before=stamp+timedelta(seconds=120)))
            await s.commit()
        error(await call('POST',base+'/requests',confirm(plan,flow_client)),409,'IDEMPOTENCY_CONFLICT')
        error(await call('GET',base+'/requests/'+str(flow_id)),404,'RESOURCE_NOT_FOUND')
        mark('CF054_old_Flow_target_not_promoted')
        # Each actual commit wrapper loses only the first ACK at its named stage.
        rows={}
        for stage in ('binding_ack','admission_ack','link_ack'):
            body_lost=confirm(plan);target[0]=hashlib.sha256(body_lost['client_key'].encode()).digest();mode[0]=stage;injected[0]=False;initial=await totals();sent=len(runner_calls)
            error(await call('POST',base+'/requests',body_lost),503);check(injected[0],'CF054 requested ACK boundary reached');mode[0]='normal'
            lost=await binding_for(body_lost);rows[stage]=lost
            if stage=='admission_ack':
                async with owned_session(proof) as s:
                    recovery=await Admission(s,principal=a2[1]).reconcile(fixed_key(lost.id))
                    await s.rollback()
                snapshot=Service.run_snapshot(recovery.run)
                from datetime import timezone
                alternative=copy.deepcopy(snapshot);alternative['as_of']=recovery.run.as_of.astimezone(timezone(timedelta(hours=9))).isoformat()
                check(await scalar('SELECT clock_timestamp()<deadline_at FROM technical_analysis_runs WHERE id=:id',{'id':recovery.run.analysis_id}),'CF054 fresh timestamp negative fixture')
                await refused('UPDATE supervisor_request_bindings SET technical_run_id=:run,technical_run_json=:value WHERE id=:id',{'run':recovery.run.analysis_id,'value':C.canonical(alternative),'id':lost.id})
                await refused('UPDATE supervisor_request_bindings SET technical_run_id=:run,technical_run_json=:value WHERE id=:id',{'run':recovery.run.analysis_id,'value':json.dumps(snapshot,indent=2),'id':lost.id})
                async with owned_session(proof) as s:
                    await s.execute(text('UPDATE supervisor_request_bindings SET technical_run_id=:run,technical_run_json=:value WHERE id=:id'),{'run':recovery.run.analysis_id,'value':C.canonical(snapshot),'id':lost.id});await s.rollback()
            view=data(await call('GET',base+'/requests/'+str(lost.id),who=a2))
            check(data(await call('POST',base+'/requests',body_lost,who=a2),202 if view['coverage']=='pending' else 200)==view,'CF054 lost ACK read-only replay')
            check(len(runner_calls)==sent,'CF054 lost ACK never executes')
            final=await totals();check(final==initial if stage=='binding_ack' else final[0]==initial[0]+1 and final[2]==initial[2]+policy.data()['attempt_reserve_nano'],'CF054 ACK accounting retained')
            check(view['technical'] is None if stage=='binding_ack' else view['technical']['state']=='admitted','CF054 fixed-key readonly reconcile without token')
        target[0]=None;mark('CF054_binding_admission_link_commit_ACK_loss_no_reissue_no_dispatch')
        # Same-owner wrong-key run must not be linkable to the unaccepted binding.
        unlinked=rows['binding_ack'];wrong_intent=Intent(unlinked.technical_intent_json)
        async with owned_session(proof) as s:wrong=await Admission(s,principal=a[1],policy=policy).admit_provider('cf054-wrong-key',wrong_intent,cfg)
        values={'run':wrong.run.analysis_id,'value':C.canonical(Service.run_snapshot(wrong.run)),'id':unlinked.id}
        await refused('UPDATE supervisor_request_bindings SET technical_run_id=:run,technical_run_json=:value WHERE id=:id',values)
        await refused("UPDATE supervisor_request_bindings SET target='flow' WHERE id=:id",{'id':current.id})
        await refused('DELETE FROM supervisor_request_bindings WHERE id=:id',{'id':current.id})
        # Existing incoming FK may refuse TRUNCATE before this revision's trigger.
        # Do not add CASCADE or broaden the target tables to reach the trigger.
        from sqlalchemy.exc import DBAPIError
        async with owned_session(proof) as s:
            try:await s.execute(text('TRUNCATE supervisor_request_bindings'))
            except DBAPIError as denied:
                check(getattr(denied.orig,'sqlstate',None) in {'0A000','23514'},'CF054 exact TRUNCATE FK/trigger denial');await s.rollback()
            else:check(False,'CF054 TRUNCATE must fail')
        mark('CF054_fixed_key_owner_intent_run_link_SQL_and_delete_guards')
        # Durable start ACK loss cannot grant the graph; all underlying SQL is real.
        body_start=confirm(plan);sent=len(runner_calls);original_start=Authority.start;start_lost=[False]
        async def lose_start(self,*args,**kwargs):
            original=self.session.commit
            async def lost():await original();start_lost[0]=True;raise OSError('fixed CF054 start ACK loss')
            self.session.commit=lost
            try:return await original_start(self,*args,**kwargs)
            finally:self.session.commit=original
        with patch.object(Authority,'start',lose_start):
            # The HTTP client remains unchanged; only the Backend SQL callback is wrapped.
            response=await call('POST',base+'/requests',body_start)
        lost=await binding_for(body_start);view=data(await call('GET',base+'/requests/'+str(lost.id),who=a2))
        check(start_lost[0] and len(runner_calls)==sent and view['technical']['state']=='unknown','CF054 consumed start/unknown full hold without graph')
        mark('CF054_start_ACK_loss_retains_consumption_unknown_full_hold')
        # A task cancelled after acknowledged admission must not link/reclaim/retry it.
        cancel_body=confirm(plan);original_admit=TechnicalExecutionRuntime.admit_provider_once;sent=len(runner_calls)
        async def cancel_after_admission(self,*args,**kwargs):
            await original_admit(self,*args,**kwargs)
            asyncio.current_task().cancel();await asyncio.sleep(0)
        with patch.object(TechnicalExecutionRuntime,'admit_provider_once',cancel_after_admission):
            cancelled=asyncio.create_task(call('POST',base+'/requests',cancel_body))
            try:await cancelled
            except asyncio.CancelledError:pass
            else:check(False,'CF054 cancellation must propagate')
        cancelled_binding=await binding_for(cancel_body)
        cancelled_view=data(await call('GET',base+'/requests/'+str(cancelled_binding.id),who=a2))
        check(cancelled_binding.technical_run_id is None and cancelled_view['technical']['state']=='admitted' and len(runner_calls)==sent,'CF054 cancellation preserves acknowledged hold without link/execution')
        mark('CF054_post_admission_task_cancel_propagates_hold_no_resume')
        # A stale binding cannot create a reservation even through direct admission SQL.
        from src.modules.technical.infrastructure import execution_admission_repository as R
        expired_id=uuid4();expired_body=confirm(plan);expired_key=hashlib.sha256(expired_body['client_key'].encode()).digest()
        async with owned_session(proof) as s:
            original=await bindings.technical_read(s,a[1].user_id,id=unlinked.id)
            values={c.key:getattr(original,c.key) for c in Binding.__table__.columns}
            stamp=await R.clock(s)
            values.update(id=expired_id,client_key_digest=expired_key,confirm_digest=C.sha(expired_body),confirmed_at=stamp-timedelta(seconds=121),handoff_before=stamp-timedelta(seconds=1),technical_key_digest=hashlib.sha256(fixed_key(expired_id).encode()).digest())
            await bindings.admit(s,values);await s.commit()
        before_expired=await totals()
        async with owned_session(proof) as s:
            try:await Admission(s,principal=a[1],policy=policy).admit_provider(fixed_key(expired_id),wrong_intent,cfg)
            except TechnicalAdmissionError as closed:check(closed.code=='UNAVAILABLE','CF054 expired handoff SQL guard refusal')
            else:check(False,'CF054 expired handoff cannot reserve')
        check(await totals()==before_expired and data(await call('GET',base+'/requests/'+str(expired_id),who=a2))['technical'] is None,'CF054 expired binding no run/counter/hold delta')
        mark('CF054_expired_handoff_SQL_admission_reservation0')
        # New original session revocation after admission, before link; A2 may only observe.
        body_revoke=confirm(plan);original_admit=TechnicalExecutionRuntime.admit_provider_once;revocation=[False]
        async def revoked_admission(self,*args,**kwargs):
            result=await original_admit(self,*args,**kwargs)
            async with owned_session(proof) as s:await revoke_session(s,a[1]);revocation[0]=True
            return result
        sent=len(runner_calls)
        with patch.object(TechnicalExecutionRuntime,'admit_provider_once',revoked_admission):error(await call('POST',base+'/requests',body_revoke),401,'AUTH_REQUIRED')
        revoked_binding=await binding_for(body_revoke)
        check(revocation[0] and len(runner_calls)==sent and data(await call('GET',base+'/requests/'+str(revoked_binding.id),who=a2))['technical']['state']=='admitted','CF054 revoked original no link/execute; A2 observes only')
        mark('CF054_admission_then_original_session_revoke_no_link_or_execution')
        before_downgrade=await totals()
        try:await migration(proof,'c53001a7e0001',downgrade=True)
        except RuntimeError:pass
        else:check(False,'CF054 populated downgrade denied')
        check(await totals()==before_downgrade and await scalar('SELECT version_num FROM alembic_version')=='c54001a7e0001','CF054 populated handoff history and full hold retained')
        mark('CF054_populated_downgrade_denied_before_drop')
    finally:
        app.dependency_overrides.clear();app.dependency_overrides.update(original_overrides)


async def _verify_composition(proof,cfg,policy,mark,scalar,refused,totals):
    """Native SQL admission/link/owner observation, never a new dispatcher."""
    import asyncio,time
    from dataclasses import replace
    from datetime import timedelta
    from types import SimpleNamespace as NS
    from unittest.mock import patch
    from sqlalchemy import text
    from db.models.auth.models import AuthUser
    from src.modules.auth.application.session_service import issue_session,revoke_session,AuthenticationRequired
    from src.modules.supervisor.domain import contracts as B
    from src.modules.supervisor.domain.composition import CompositionSnapshot,VERSION,fixed_child_key
    from src.modules.supervisor.application import composition_service as C
    from src.modules.supervisor.infrastructure import composition_repository as R
    from src.modules.technical.application.execution_admission_service import TechnicalAdmissionService as Admission
    from src.modules.technical.application.execution_runtime import TechnicalExecutionRuntime
    from src.modules.flow.application.analysis_service import AnalysisService as Flow
    from src.shared.config import settings
    from scripts.cf002_interactive_login import owned_session
    from scripts.cf003_admission_check import check,migration

    async def identity():
        async with owned_session(proof) as s:
            owner=AuthUser(id=uuid4());s.add(owner);await s.flush()
            _,p=await issue_session(s,owner);_,a2=await issue_session(s,owner);await s.commit();return p,a2
    p,a2=await identity();other,_=await identity()
    stock=await scalar("SELECT json_build_object('stock_code',stock_code,'stock_name',stock_name,'market',market)::text FROM stocks WHERE stock_code='000720'")
    query='000720 수급과 차트';views=['flow','technical']
    frame=dict(original_query=query,query_sha256=B.sha(query),revision=0,answers=[],
        mentions=[dict(text='000720',negated=False,evidence=dict(source_kind='original_query',answer_id=None,start=0,end=6,text='000720'))],
        requested_views=views,negated_views=[],conditions=[],unresolved_slots=[],interpretation_source='deterministic')
    snapshot=CompositionSnapshot(B.canonical(dict(schema_version=VERSION,draft=dict(original_query=query,answers=[],revision=0,selected_ticker=None,candidate_ref=None),
        frame=frame,stock=json.loads(stock),selected_views=views,consent=dict(allow_views=views,allow_partial_results=True,waived_conditions=[]),
        flow_policy=dict(supported_tickers=['000720'],user_limit=100,service_limit=100,budget=10000000000),technical_configuration=cfg.text)))
    async def admitted(service,key=None):
        stamp=await R.clock(service.session)
        return await service.admit(key or str(uuid4()),snapshot,request_started_at=stamp)
    async def observe(owner,id):
        async with owned_session(proof) as s:return await C.CompositionService(s,principal=owner).get(id)
    async def expect(call,codes):
        try:await call
        except C.CompositionError as error:check(error.code in codes,'composition fixed error');return
        check(False,'composition operation must refuse')
    baseline=await totals()
    async with owned_session(proof) as s:
        service=C.CompositionService(s,principal=p);key=str(uuid4());first=await admitted(service,key)
        replay=await admitted(service,key)
        check(first.newly_admitted and not replay.newly_admitted and replay.token is None,'composition no replay token')
        row=await R.read(s,p.user_id,id=first.id)
        check(str(await s.scalar(text("SELECT c60001_child_key(:id,'technical',:seed)"),dict(id=first.id,seed=row.claim_digest)))==fixed_child_key(first.id,'technical',bytes(row.claim_digest)),'composition SQL/Python UUID parity')
        await s.rollback()
        right=await service.start(first);check(right.newly_started,'composition fresh start ACK')
        check(not (await service.start(first)).newly_started,'composition second start closed')
        await service.handoff(right,'technical');native_key,_=service.take_handoff(right,'technical')
        native=await Admission(s,principal=p,policy=policy).admit_provider(native_key,service.technical_intent(snapshot),cfg)
        await service.link(right,'technical',native)
        row=await R.read(s,p.user_id,id=first.id)
        check(row.analysis_as_of==native.run.as_of and row.technical_run_id==native.run.analysis_id,'composition SQL UUID normalization and shared native clock')
        await s.rollback()
        # These native services are invoked explicitly by the fixture. The
        # composition service itself neither invokes nor republishes children.
        from src.modules.technical.application.execution_authority_service import TechnicalExecutionAuthority
        from src.modules.technical.domain import provider_execution as P
        from src.modules.technical.application import execution_completion as E
        from src.modules.analysis.application.coordinator import AnalysisCoordinator
        claim=await Admission(s,principal=p,policy=policy).dispatch_provider_claim(native.run,native.claim_token,cfg)
        execution=P.decode(claim.execution_json);boundary=execution['boundary_request']
        start=await TechnicalExecutionAuthority(s,configuration=cfg).start(dict(schema_version=P.SCHEMA,
            analysis_id=str(claim.run.analysis_id),control_sha256=execution['control_sha256'],executor_id=str(uuid4())),claim.grant)
        raw=copy.deepcopy(json.loads(storage_fixture(uuid4())[1].result_json)['data']['result'])
        raw.update(request_id=boundary['request_id'],trace_id=boundary['trace_id'],ticker='000720',
            as_of=boundary['data']['requested_as_of'],resolved_stock_name=snapshot.data()['stock']['stock_name'])
        response=P.result(boundary,raw,{k:start[k] for k in ('control_sha256','start_sha256','executor_id')})
        result=await AnalysisCoordinator(s,principal=p,client=None,profile=E.TechnicalCompletionProfile(policy=policy)).receive(claim.run,native.claim_token,response)
        check(result.run.state=='stored','composition native stored child fixture')
        await service.handoff(right,'flow');flow_key,as_of=service.take_handoff(right,'flow')
        async def unavailable(*args,**kwargs):raise OSError('fixed synthetic no Flow provider')
        flow_service=Flow(s,principal=p,client=NS(analyze_flow=unavailable))
        flow_service.usage_control.settings=NS(FLOW_USAGE_LIMITS_ENABLED='true',FLOW_SUPPORTED_TICKERS='000720',
            FLOW_USER_DAILY_REQUEST_LIMIT='100',FLOW_SERVICE_DAILY_REQUEST_LIMIT='100',FLOW_SERVICE_DAILY_BUDGET_USD='10')
        flow=await flow_service.post(dict(ticker='000720',question=query,as_of=as_of.isoformat(),idempotency_key=flow_key,allow_analysis=True),uuid4())
        check(flow.state=='unknown','composition independent child uncertainty')
        await service.link(right,'flow',flow)
        await service.close(right)
        try:service.take_handoff(right,'flow')
        except C.CompositionError:pass
        else:check(False,'composition close consumes unspent local ticket')
    before=await totals()
    for owner in (p,a2):
        view=await observe(owner,first.id)
        check(view['state']=='closed' and view['coverage']=='partial','composition A1/A2 partial owner read')
        states={item['view']:item['state'] for item in view['views']}
        check(states=={'flow':'unknown','technical':'stored'},'composition stored survives other child unknown')
        check(all(secret not in json.dumps(view) for secret in ('claim_digest',native_key,flow_key)),'composition response no capabilities')
    await expect(observe(other,first.id),{'NOT_FOUND'})
    check(await totals()==before,'composition GET/restart no new native accounting')
    mark('composition_actual_owner_A2_stored_plus_unknown_fixed_children_no_reexecution')

    # One winner across independent SQL sessions; the loser never receives a
    # fresh right even though it has the original admission receipt in memory.
    async with owned_session(proof) as s:
        service=C.CompositionService(s,principal=p);race=await admitted(service)
    async def start_once():
        async with owned_session(proof) as s:return await C.CompositionService(s,principal=p).start(race)
    rights=await asyncio.gather(start_once(),start_once())
    check(sum(r.newly_started for r in rights)==1,'composition concurrent start single winner')
    async with owned_session(proof) as s:
        service=C.CompositionService(s,principal=p);lost=await admitted(service);original=s.commit
        async def missing_ack():await original();raise OSError('fixed synthetic lost ACK')
        s.commit=missing_ack
        await expect(service.start(lost),{'ACK_UNKNOWN'})
        s.commit=original
        check((await service.get(lost.id))['state']=='claimed','composition durable lost ACK observation')
        await expect(service.start(lost),{'ACK_UNKNOWN'})
    check(await totals()==before,'composition races/ACK do not admit native children')
    mark('composition_concurrent_start_ACK_loss_observation_no_native_reservation')

    # An unlinked consumed handoff remains unknown, not proof of no call; an
    # expired unstarted parent closes once and cannot remain pending forever.
    async with owned_session(proof) as s:
        service=C.CompositionService(s,principal=p);uncertain=await admitted(service);right=await service.start(uncertain)
        await service.handoff(right,'technical');await service.close(right)
    check((await observe(a2,uncertain.id))['coverage']=='unknown','composition consumed unconfirmed unknown')
    async with owned_session(proof) as s:
        service=C.CompositionService(s,principal=p);expired=await admitted(service)
    real_clock=R.clock
    async def later(session):return await real_clock(session)+timedelta(seconds=141)
    with patch.object(R,'clock',later):
        view=await observe(a2,expired.id)
    check(view['state']=='closed' and view['coverage']=='unfulfilled','composition expiry closes nonstarted dispatch')
    mark('composition_missing_receipt_unknown_expired_nonstarted_closed')

    # Cancel the actual handoff while its SQL/auth/root locks are held. The
    # service rethrows immediately; its owning session context rolls back.
    locked=asyncio.Event();cancelled_id=[];original_change=R.change
    async def pause_handoff(session,row,values):
        changed=await original_change(session,row,values)
        if 'technical_handoff_at' in values:
            locked.set();await asyncio.Event().wait()
        return changed
    async def cancelled_owner():
        async with owned_session(proof) as s:
            service=C.CompositionService(s,principal=p);item=await admitted(service);right=await service.start(item)
            cancelled_id.append(item.id)
            with patch.object(R,'change',pause_handoff):await service.handoff(right,'technical')
    task=asyncio.create_task(cancelled_owner());await locked.wait();task.cancel()
    try:await task
    except asyncio.CancelledError:pass
    async with owned_session(proof) as s:
        await s.execute(text("SET LOCAL lock_timeout='1000ms'"))
        await s.execute(text('SELECT id FROM auth_sessions WHERE id=:id FOR UPDATE NOWAIT'),{'id':p.session_id})
        row=(await s.execute(text('SELECT technical_handoff_at FROM supervisor_compositions WHERE id=:id FOR UPDATE NOWAIT'),{'id':cancelled_id[0]})).one()
        check(row[0] is None,'composition cancelled uncommitted handoff rolled back by context')
    mark('composition_cancel_owner_session_context_releases_auth_root_locks')

    # The persisted handoff itself is atomic across independent connections.
    async def consume_handoff():
        async with owned_session(proof) as s:
            result=await s.scalar(text('UPDATE supervisor_compositions SET technical_handoff_at=clock_timestamp() WHERE id=:id AND technical_handoff_at IS NULL RETURNING id'),{'id':race.id})
            await s.commit();return result
    winners=await asyncio.gather(consume_handoff(),consume_handoff())
    check(sum(value is not None for value in winners)==1,'composition concurrent handoff single winner')
    revoked,revoked_a2=await identity()
    async with owned_session(proof) as s:
        service=C.CompositionService(s,principal=revoked);item=await admitted(service);right=await service.start(item)
        await revoke_session(s,revoked)
        try:await service.handoff(right,'technical')
        except AuthenticationRequired:pass
        else:check(False,'composition revoked original must not hand off')
    await refused('UPDATE supervisor_compositions SET technical_handoff_at=clock_timestamp() WHERE id=:id',{'id':item.id})
    check((await observe(revoked_a2,item.id))['views'][1]['state']=='not_started','composition A2 observes revoked original without authority')
    mark('composition_actual_SQL_handoff_race_revoked_original_A2_read_only')

    # Redaction may remove scope, but may never add previously absent links.
    async with owned_session(proof) as s:
        service=C.CompositionService(s,principal=other);foreign=await admitted(service);fr=await service.start(foreign)
        await service.handoff(fr,'technical');fk,_=service.take_handoff(fr,'technical')
        foreign_native=await Admission(s,principal=other,policy=policy).admit_provider(fk,service.technical_intent(snapshot),cfg)
        await service.link(fr,'technical',foreign_native)
    await refused("UPDATE supervisor_compositions SET state='redacted',snapshot_json=NULL,closed_at=clock_timestamp(),technical_run_id=:foreign,analysis_as_of=:asof WHERE id=:id",dict(id=uncertain.id,foreign=foreign_native.run.analysis_id,asof=foreign_native.run.as_of))
    await refused('UPDATE supervisor_compositions SET technical_run_id=:foreign,analysis_as_of=:asof WHERE id=:id',dict(id=race.id,foreign=foreign_native.run.analysis_id,asof=foreign_native.run.as_of))
    await refused('DELETE FROM supervisor_compositions WHERE id=:id',{'id':first.id})
    await refused('TRUNCATE supervisor_compositions')
    await refused('DELETE FROM technical_analysis_runs WHERE id=:id',{'id':native.run.analysis_id})
    # Redaction is still a valid one-direction privacy transition when all
    # consumed identity fields are held exactly unchanged.
    async with owned_session(proof) as s:
        await s.execute(text("UPDATE supervisor_compositions SET state='redacted',snapshot_json=NULL WHERE id=:id"),{'id':uncertain.id});await s.commit()
    check((await observe(a2,uncertain.id))['coverage']=='deleted','composition redacted owner tombstone')
    mark('composition_direct_SQL_foreign_link_redaction_null_link_delete_truncate_refused')
    before=await totals()
    try:await migration(proof,'c54001a7e0001',downgrade=True)
    except RuntimeError:pass
    else:check(False,'composition history blocks downgrade')
    check(await scalar('SELECT version_num FROM alembic_version')=='c60001a7e0001' and await totals()==before,'composition populated downgrade retains all old holds')
    mark('composition_populated_downgrade_retained_old_native_holds')
    return dict(owner=a2,id=first.id)


async def _verify_composition_runtime(proof,cfg,policy,ai,technical_client,runner_calls,sdk,runner_mode,legacy,mark,scalar,totals):
    """Actual SQL -> production clients/two AI routes -> synthetic engines/store.

    Neither this group nor the existing PG site imports the compiled graph/SDK
    site. Both runtime/bridge paths execute injected engines and fake SDK/HTTP.
    """
    import asyncio,os,time,threading
    from contextlib import ExitStack
    from datetime import UTC
    from types import SimpleNamespace as NS
    from unittest.mock import patch
    import httpx
    from sqlalchemy import text,select
    from db.models.auth.models import AuthUser
    from db.models.flow.analysis_run import FlowAnalysisRun
    from src.modules.auth.application.session_service import issue_session
    from src.modules.supervisor.domain import contracts as B
    from src.modules.supervisor.domain.composition import CompositionSnapshot,PROJECTED_VERSION,projected_inputs
    from src.modules.supervisor.application.composition_service import CompositionService,CompositionError
    from src.modules.supervisor.application.composition_runtime import CompositionRuntime
    from src.modules.supervisor.infrastructure import composition_repository as roots
    from src.modules.flow.application.analysis_service import AnalysisService as FlowService,AnalysisError
    from src.modules.technical.application.execution_admission_service import TechnicalAdmissionService as Admission
    from src.modules.technical.domain.execution_admission import TechnicalAdmissionError,REASONS
    from src.shared.infrastructure.clients.ai_client import AIClient
    from scripts.cf002_interactive_login import owned_session,safe_print
    from scripts.cf003_admission_check import check
    from scripts.cf012_analysis_check import flow_app,engine_result
    token='synthetic-composition-flow-token-at-least32';http_events=[];flow_calls=[];flow_mode=['normal']
    entered=threading.Event();release=threading.Event()
    def flow_engine(request,context):
        flow_calls.append(str(request.analysis_id))
        if flow_mode[0]=='fail':raise RuntimeError('fixed synthetic Flow failure')
        if flow_mode[0]=='pause':entered.set();release.wait(5);context.check('synthetic_wait_end')
        return engine_result(request,context)
    flow_app_instance=flow_app(flow_engine)
    async def observed_ai(scope,receive,send):
        status=[None];raw=bytearray()
        async def record(message):
            if message['type']=='http.response.start':status[0]=message['status']
            if message['type']=='http.response.body' and status[0] is not None and status[0]>=400:
                if len(raw)+len(message.get('body',b''))<=2048:raw.extend(message.get('body',b''))
                if not message.get('more_body',False):
                    try:code=json.loads(raw).get('error',{}).get('code')
                    except Exception:code=None
                    allowed={'SERVICE_UNAVAILABLE','FEATURE_UNAVAILABLE','AUTH_REQUIRED','INPUT_INVALID','DEADLINE_EXCEEDED','RESULT_CONTRACT_INVALID','BUSY'}
                    http_events.append(dict(status=status[0],code=code if type(code) is str and code in allowed else 'other'))
            await send(message)
        await ai(scope,receive,record)
    tech_client=AIClient(cfg.data()['ai_origin'],10,httpx.ASGITransport(app=observed_ai),execution_token='a'*32)
    flow_client=AIClient('http://flow.synthetic.invalid',125,httpx.ASGITransport(app=flow_app_instance),service_token=token)
    async with owned_session(proof) as s:
        owner=AuthUser(id=uuid4());other=AuthUser(id=uuid4());s.add_all([owner,other]);await s.flush()
        _,p=await issue_session(s,owner);_,a2=await issue_session(s,owner);_,b=await issue_session(s,other);await s.commit()
    stock=json.loads(await scalar("SELECT json_build_object('stock_code',stock_code,'stock_name',stock_name,'market',market)::text FROM stocks WHERE stock_code='000720'"))
    def scope(views):
        query='000720 '+('수급과 차트' if len(views)==2 else '수급' if views==['flow'] else '차트')
        frame=dict(original_query=query,query_sha256=B.sha(query),revision=0,answers=[],
            mentions=[dict(text='000720',negated=False,evidence=dict(source_kind='original_query',answer_id=None,start=0,end=6,text='000720'))],
            requested_views=views,negated_views=[],conditions=[],unresolved_slots=[],interpretation_source='deterministic')
        return CompositionSnapshot(B.canonical(dict(schema_version=PROJECTED_VERSION,child_inputs=projected_inputs(stock,query,views),draft=B.Draft(original_query=query,answers=[],revision=0).model_dump(mode='json'),
            frame=frame,stock=stock,selected_views=views,consent=dict(allow_views=views,allow_partial_results=len(views)==2,waived_conditions=[]),
            flow_policy=dict(supported_tickers=['000720'],user_limit=100,service_limit=100,budget=10000000000) if 'flow' in views else None,
            technical_configuration=cfg.text if 'technical' in views else None)))
    async def new(views=None):
        snapshot=scope(views or ['flow','technical'])
        async with owned_session(proof) as s:
            first=await CompositionService(s,principal=p).admit(str(uuid4()),snapshot,request_started_at=await roots.clock(s))
        return first,snapshot
    async def read(who,id):
        async with owned_session(proof) as s:return await CompositionService(s,principal=who).get(id)
    async def accounting():
        return tuple([await scalar(q) for q in (
            'SELECT count(*) FROM flow_analysis_runs','SELECT coalesce(sum(request_count),0) FROM analysis_usage_periods',
            'SELECT coalesce(sum(held_nano),0) FROM analysis_usage_periods','SELECT coalesce(sum(estimated_spend_nano),0) FROM analysis_usage_periods')])+(await totals())
    def diagnostic(view):
        safe_print(dict(phase='composition_runtime_diagnostic',coverage=view.get('coverage'),
            child_states=[{k:item[k] for k in ('view','state') if k in item} for item in view.get('views',[])],
            technical_HTTP_errors=http_events[-4:],fake_engine_runs=len(runner_calls),fake_SDK_HTTP=len(sdk.sent),flow_engine_runs=len(flow_calls)))
    with patch.dict(os.environ,{'FLOW_ANALYSIS_ENABLED':'true','FLOW_SERVICE_TOKEN':token}):
        old=await read(legacy['owner'],legacy['id'])
        check(old['coverage']=='partial' and {v['view']:v['state'] for v in old['views']}=={'flow':'unknown','technical':'stored'},'composition v1 native input/owner read survives projection revision')
        first,snapshot=await new();tech_before=len(runner_calls);flow_before=len(flow_calls);sdk_before=len(sdk.sent)
        async with owned_session(proof) as s:
            result=await CompositionRuntime(s,principal=p,flow_client=flow_client,technical_client=tech_client,enabled=True).execute_once(first)
        diagnostic(result)
        check(result['coverage']=='fulfilled' and {v['state'] for v in result['views']}=={'stored'},'composition both native runtime paths stored')
        check(len(runner_calls)==tech_before+1 and len(flow_calls)==flow_before+1 and len(sdk.sent)==sdk_before+2,'composition actual two engines and one fake count/generation pair')
        before=await accounting();calls=(len(runner_calls),len(flow_calls),len(sdk.sent))
        for who in (p,a2):check((await read(who,first.id))==result,'composition fresh owner DB session restores both native refs')
        try:await read(b,first.id)
        except CompositionError as error:check(error.code=='NOT_FOUND','composition other owner blocked')
        else:check(False,'composition other owner must fail')
        for receipt in (first,replace(first,newly_admitted=False,token=None)):
            async with owned_session(proof) as s:
                replay=await CompositionRuntime(s,principal=p,flow_client=flow_client,technical_client=tech_client,enabled=True).execute_once(receipt)
                check(replay==result,'composition POST replay only observes')
        check(await accounting()==before and calls==(len(runner_calls),len(flow_calls),len(sdk.sent)),'composition GET/POST replay no engine or spend')
        mark('composition_runtime_two_real_AI_routes_injected_engines_native_store_owner_A2_replay_no_cost')

        for mode in ('flow_fail','technical_invalid'):
            first,_=await new();flow_mode[0]='fail' if mode=='flow_fail' else 'normal';runner_mode[0]='invalid' if mode=='technical_invalid' else 'normal'
            try:
                async with owned_session(proof) as s:partial=await CompositionRuntime(s,principal=p,flow_client=flow_client,technical_client=tech_client,enabled=True).execute_once(first)
            finally:flow_mode[0]='normal';runner_mode[0]='normal'
            diagnostic(partial);states={v['view']:v['state'] for v in partial['views']}
            check(partial['coverage']=='partial' and states==({'flow':'unknown','technical':'stored'} if mode=='flow_fail' else {'flow':'stored','technical':'unknown'}),'composition partial keeps stored child')
            check((await read(a2,first.id))==partial,'composition partial durable owner read')
        mark('composition_runtime_either_child_failure_keeps_other_stored_and_independent_holds')

        first,_=await new();lost=[False];flows_before=len(flow_calls);tech_before=len(runner_calls)
        async with owned_session(proof) as s:
            original=s.commit
            async def lose_flow_ACK():
                await s.flush();root=await roots.read(s,p.user_id,id=first.id)
                native=await roots.native(s,p.user_id,'flow',root.flow_key_digest)
                hit=not lost[0] and native is not None and root.flow_run_id is None
                await original()
                if hit:lost[0]=True;raise OSError('fixed synthetic Flow admission ACK loss')
            s.commit=lose_flow_ACK
            result=await CompositionRuntime(s,principal=p,flow_client=flow_client,technical_client=tech_client,enabled=True).execute_once(first)
        diagnostic(result)
        check(lost[0] and len(flow_calls)==flows_before and len(runner_calls)==tech_before+1,'composition lost Flow ACK no Flow execution; confirmed Technical still executes')
        check(result['coverage']=='partial' and {v['view']:v['state'] for v in result['views']}=={'flow':'unknown','technical':'stored'},'composition lost ACK remains unknown not uncalled')
        before=await accounting()
        async with owned_session(proof) as s:await CompositionRuntime(s,principal=p,flow_client=flow_client,technical_client=tech_client,enabled=True).execute_once(first)
        check(await accounting()==before and len(flow_calls)==flows_before,'composition lost ACK replay cannot issue continuation')
        mark('composition_runtime_real_Flow_admission_commit_ACK_loss_no_redispatch_full_unknown_hold')

        # No continuation is reconstructed when two requests share the original
        # receipt. Each request owns its own SQL session.
        first,_=await new(['flow']);calls_before=len(flow_calls)
        async def compete():
            async with owned_session(proof) as s:return await CompositionRuntime(s,principal=p,flow_client=flow_client,enabled=True).execute_once(first)
        await asyncio.gather(compete(),compete())
        check(len(flow_calls)==calls_before+1 and (await read(a2,first.id))['coverage']=='fulfilled','composition concurrent root only one native execution')
        mark('composition_runtime_actual_two_SQL_sessions_same_receipt_one_native_execution')

        first,_=await new(['flow']);flow_mode[0]='pause';calls_before=len(flow_calls)
        async def cancelled():
            async with owned_session(proof) as s:return await CompositionRuntime(s,principal=p,flow_client=flow_client,enabled=True).execute_once(first)
        task=asyncio.create_task(cancelled())
        try:
            async with asyncio.timeout(10):
                while not entered.is_set():await asyncio.sleep(.005)
            task.cancel();release.set()
            try:await task
            except asyncio.CancelledError:pass
            else:check(False,'composition cancel must propagate')
        finally:release.set();flow_mode[0]='normal'
        before=await accounting()
        async with owned_session(proof) as s:await CompositionRuntime(s,principal=p,flow_client=flow_client,enabled=True).execute_once(first)
        check(len(flow_calls)==calls_before+1 and await accounting()==before,'composition cancellation consumes grant, replay cannot resend')
        mark('composition_runtime_cancel_propagates_owned_session_cleanup_no_continuation_reissue')

        # A UTC cutoff already elapsed while the caller's waiter remains live
        # reaches the conditional INSERT and creates no run/reservation.
        before=await accounting()
        async with owned_session(proof) as s:
            now=await roots.clock(s)
            flow=FlowService(s,principal=p,client=flow_client)
            flow.usage_control.settings=NS(FLOW_USAGE_LIMITS_ENABLED='true',FLOW_SUPPORTED_TICKERS='000720',FLOW_USER_DAILY_REQUEST_LIMIT='100',FLOW_SERVICE_DAILY_REQUEST_LIMIT='100',FLOW_SERVICE_DAILY_BUDGET_USD='10')
            try:await flow.admit_only(dict(ticker='000720',question='synthetic cutoff',as_of=now.isoformat(),idempotency_key=str(uuid4()),allow_analysis=True),uuid4(),
                admission_before=now-timedelta(seconds=1),admission_deadline=time.monotonic()+5,total_deadline=time.monotonic()+140)
            except AnalysisError:pass
            else:check(False,'composition expired Flow SQL INSERT must reject')
        async with owned_session(proof) as s:
            try:await Admission(s,principal=p,policy=policy).admit_provider(str(uuid4()),CompositionService.technical_intent(scope(['technical'])),cfg,admission_before=await roots.clock(s)-timedelta(seconds=1))
            except TechnicalAdmissionError:pass
            else:check(False,'composition expired Technical admission must reject')
        check(await accounting()==before,'composition both native cutoffs reserve zero after original admission window')
        mark('composition_runtime_SQL_cutoff_no_late_native_reservation')

    # A bad projection is refused by its own new guard on a fresh INSERT, not
    # by the old root's immutability, FK, clock or deferred native totals.
    from sqlalchemy import insert
    from sqlalchemy.exc import IntegrityError
    from db.models.supervisor.composition import SupervisorComposition as Root
    from src.modules.supervisor.domain.composition import fixed_child_key
    fresh,snapshot=await new()
    async with owned_session(proof) as s:
        values=dict((await s.execute(select(Root.__table__).where(Root.id==fresh.id))).mappings().one())
    altered=snapshot.data();altered['child_inputs']['technical']['original_query']='000720 수급과 차트'
    values['snapshot_json']=B.canonical(altered);values['snapshot_sha256']=hashlib.sha256(values['snapshot_json'].encode()).hexdigest();values['confirm_digest']=values['snapshot_sha256']
    values['id']=uuid4();values['client_key_digest']=hashlib.sha256(str(uuid4()).encode()).digest()
    values.update({v+'_key_digest':hashlib.sha256(fixed_child_key(values['id'],v,bytes(values['claim_digest'])).encode()).digest() for v in ('flow','technical')})
    async with owned_session(proof) as s:
        stamp=await roots.clock(s);values.update(request_started_at=stamp,confirmed_at=stamp,admission_before=stamp+timedelta(seconds=15),deadline_at=stamp+timedelta(seconds=140))
        try:await s.execute(insert(Root).values(**values))
        except IntegrityError as error:
            check('Composition native projection invalid' in str(error),'composition exact new projection guard; no other masking')
            await s.rollback()
        else:check(False,'composition malformed projection must fail at INSERT')
    # A native run with this private fixed key but the old mixed question is
    # not the v2 child input, even with identical owner/config/stock/as-of.
    from src.modules.technical.domain.execution_admission import Intent
    async with owned_session(proof) as s:
        service=CompositionService(s,principal=p);right=await service.start(fresh)
        await service.handoff(right,'technical');key,_=service.take_handoff(right,'technical')
        wrong=snapshot.data()['child_inputs']['technical']|{'original_query':snapshot.data()['draft']['original_query']}
        receipt=await Admission(s,principal=p,policy=policy).admit_provider(key,Intent.parse(wrong),cfg)
        try:await service.link(right,'technical',receipt)
        except CompositionError as error:check(error.code=='INVALID','composition v2 native intent mismatch fixed refusal')
        else:check(False,'composition v2 wrong native input cannot link')
        try:
            await s.execute(text('UPDATE supervisor_compositions SET technical_run_id=:run,analysis_as_of=:asof WHERE id=:id'),dict(run=receipt.run.analysis_id,asof=receipt.run.as_of,id=fresh.id))
        except IntegrityError as error:
            check('Composition Technical reference invalid' in str(error),'composition SQL v2 exact input hash binding')
            await s.rollback()
        else:check(False,'composition direct SQL v2 wrong input must refuse')
    mark('composition_runtime_v1_read_unchanged_v2_projection_and_native_input_SQL_binding')
    before=await accounting()
    from scripts.cf003_admission_check import migration
    try:await migration(proof,'c60001a7e0001',downgrade=True)
    except RuntimeError:pass
    else:check(False,'composition v2 consumed history must block downgrade')
    check(await scalar('SELECT version_num FROM alembic_version')=='c61001a7e0001' and await accounting()==before,'composition v2 populated downgrade preserves all holds')
    mark('composition_runtime_projection_populated_downgrade_retains_v1_v2_identity_and_hold')
