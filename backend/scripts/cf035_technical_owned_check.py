"""Fixed owned-PG storage verification. No app/config/engine/provider bootstrap."""
import copy
from dataclasses import replace
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
from uuid import UUID, uuid4


def storage_fixture(owner_user_id, *, report_id=None, request_id=None, change=None):
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
