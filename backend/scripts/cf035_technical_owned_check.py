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

    check(await scalar(text('SELECT version_num FROM alembic_version')) == 'c35001a7e0001','Technical revision')
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
    check(await scalar(text('SELECT version_num FROM alembic_version')) == 'c35001a7e0001','failed downgrade preserves revision')
    legacy_after = await scalar(text('SELECT row_to_json(t)::text FROM technical_reports t WHERE id=:id').bindparams(id=legacy_root.id))
    check(legacy_before == legacy_after,'legacy row rewritten')
    groups.append('nonempty_downgrade_rejected_legacy_unchanged')
    return {'status':'passed','groups':groups,'engine_calls':0,'provider_calls':0,'public_http_calls':0}
