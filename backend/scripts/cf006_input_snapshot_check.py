"""Fixed CF-006 verification, on freshly minted owned PostgreSQL proofs only."""
import asyncio
from dataclasses import replace
import json
import time
from unittest.mock import patch
from uuid import uuid4

from scripts.cf003_admission_check import check, isolated_application, migration, verify_admission


class SnapshotDDLFailure(RuntimeError):
    """Only raised by the exact post-CREATE hook, never by preflight."""


async def snapshot_migration(proof, target, *, fail_after_create=False, locked=None, release=None):
    """The new DDL failure hook matches only this revision's exact new table."""
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import event
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.util.concurrency import await_only
    from scripts.cf002_interactive_login import _BACKEND
    await proof.preflight()
    engine = create_async_engine(proof.url, connect_args=proof.connection_parameters())
    try:
        async with engine.connect() as connection:
            await proof.attest_connection(connection)
            def apply(sync):
                def hook(conn, cursor, statement, parameters, context, executemany):
                    normalized = statement.lstrip().upper()
                    if fail_after_create and normalized.startswith("CREATE TABLE FLOW_INPUT_SNAPSHOTS"):
                        raise SnapshotDDLFailure("CF006 synthetic DDL failure")
                    if locked is not None and normalized.startswith("LOCK TABLE FLOW_RUNS IN ACCESS EXCLUSIVE MODE"):
                        locked.set()
                        await_only(asyncio.wait_for(release.wait(), timeout=15))
                config = Config(str(_BACKEND / "alembic.ini"))
                config.set_main_option("script_location", str(_BACKEND / "db/migrations"))
                config.attributes.update(connection=sync, verified_test_mode=True)
                event.listen(sync, "after_cursor_execute", hook)
                try:
                    (command.downgrade if target == "c3001a7e0001" else command.upgrade)(config, target)
                finally:
                    event.remove(sync, "after_cursor_execute", hook)
            try:
                await connection.run_sync(apply)
                await connection.commit()
            except Exception:
                await connection.rollback()
                raise
    finally:
        await engine.dispose()


async def verify_input_snapshot(proof):
    # Exact CF-003 baseline runs before CF-006 users/runs/snapshots exist.
    admission = await verify_admission(proof)
    with isolated_application(proof) as observed:
        result = await _verify(proof)
        check(not any(observed.values()), "CF006 forbidden access")
        result.update(existing_admission=admission, observed_denials=dict(observed),
                      observation_scope="scoped-Python-file-socket-httpx-wrappers-not-native-tracing")
        return result


async def _verify(proof):
    from sqlalchemy import func, insert, select, text, update
    from sqlalchemy.exc import DBAPIError
    from db.models.auth.models import AuthUser, AuthSession
    from db.models.flow.flow_run import FlowRun
    from db.models.flow.input_snapshot import FlowInputSnapshot
    from scripts.cf002_interactive_login import owned_session, safe_print
    from src.modules.auth.application.session_service import issue_session, authenticate, revoke_session
    from src.modules.flow.application.run_service import FlowRunService
    from src.modules.flow.api.run_schemas import FlowAdmissionRequest
    from src.modules.flow.application.input_preparation_service import InputPreparationService
    from src.modules.flow.domain import input_snapshot as domain

    passed, rejects = [], []
    def mark(label):
        passed.append(label)
        safe_print({"phase": "cf006_check", "label": label, "status": "passed"})

    async def scalar(sql, params=None):
        async with owned_session(proof) as session:
            return await session.scalar(text(sql), params or {})

    async def preserved():
        async with owned_session(proof) as session:
            result = {}
            for table in ("stocks", "flow_reports", "flow_report_interpretations", "flow_report_verifications", "agent_reports", "auth_users", "auth_identities", "auth_sessions", "flow_runs"):
                result[table] = sorted((await session.execute(text(f"SELECT row_to_json(t)::text FROM {table} t"))).scalars().all())
            return result

    safe_print({"phase": "cf006_check", "label": "migration_preservation", "status": "started"})
    check(await scalar("SELECT version_num FROM alembic_version") == "c6001a7e0001", "CF006 restored head")
    await migration(proof, "c3001a7e0001", downgrade=True)
    # Existing receipt at c3001 must survive the new revision unchanged.
    async with owned_session(proof) as session:
        from src.modules.auth.application.session_service import issue_session
        from src.modules.flow.application.run_service import FlowRunService
        from src.modules.flow.api.run_schemas import FlowAdmissionRequest
        existing_user = AuthUser(id=uuid4())
        session.add(existing_user)
        await session.flush()
        _, existing_principal = await issue_session(session, existing_user)
        await session.commit()
        await FlowRunService(session, principal=existing_principal).admit(
            FlowAdmissionRequest(ticker="005930", question="CF006 pre-upgrade receipt", as_of="2026-11-08T00:00:00Z", idempotency_key="cf006-pre-upgrade"), uuid4())
    before = await preserved()
    try:
        await snapshot_migration(proof, "c6001a7e0001", fail_after_create=True)
    except SnapshotDDLFailure:
        pass
    else:
        raise RuntimeError("CF006 DDL injection did not fail")
    check(await scalar("SELECT version_num FROM alembic_version") == "c3001a7e0001"
          and await scalar("SELECT to_regclass('flow_input_snapshots')") is None
          and not await scalar("SELECT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='uq_flow_runs_id_owner')"), "CF006 DDL rollback")
    check(await preserved() == before, "CF006 DDL existing rows preserved")
    before_upgrade = before
    await migration(proof, "c6001a7e0001")
    check(await preserved() == before_upgrade, "CF006 existing receipt keys and values upgrade preserved")
    await migration(proof, "c3001a7e0001", downgrade=True)
    await migration(proof, "c6001a7e0001")
    check(await preserved() == before_upgrade, "CF006 empty round trip preserved")
    mark("CF003_regression_before_users_and_CF006_DDL_rollback_empty_roundtrip")

    safe_print({"phase": "cf006_check", "label": "seal_owner_read", "status": "started"})
    async with owned_session(proof) as session:
        a, b = AuthUser(id=uuid4()), AuthUser(id=uuid4())
        session.add_all([a, b]); await session.flush()
        ta, pa = await issue_session(session, a)
        ta2, pa2 = await issue_session(session, a)
        tb, pb = await issue_session(session, b)
        expired, pe = await issue_session(session, a)
        revoked, pr = await issue_session(session, a)
        await session.execute(update(AuthSession).where(AuthSession.id == pe.session_id).values(
            created_at=func.clock_timestamp()-text("interval '2 hours'"), expires_at=func.clock_timestamp()-text("interval '1 hour'")))
        await session.commit()
        await revoke_session(session, pr)

    async def admit(principal=pa):
        async with owned_session(proof) as session:
            request = FlowAdmissionRequest(ticker="005930", question="CF006 synthetic", as_of="2026-11-08T00:00:00Z", idempotency_key=str(uuid4()))
            return (await FlowRunService(session, principal=principal).admit(request, uuid4())).run_id

    async def prepare(run, fixture="flow.synthetic.full20", principal=pa, hook=None, pid=None):
        async with owned_session(proof) as session:
            if pid is not None:
                pid["pid"] = await session.scalar(text("SELECT pg_backend_pid()"))
                pid["ready"].set()
            if hook:
                hook(session)
            return await InputPreparationService(session, principal=principal).prepare(run, fixture)

    async def get(run, principal=pa):
        async with owned_session(proof) as session:
            return await InputPreparationService(session, principal=principal).get(run)

    async def denied(awaitable, code, label):
        try:
            await awaitable
        except domain.SnapshotError as exc:
            check(exc.code == code and str(exc) == "Flow input snapshot: " + code and exc.__cause__ is None, label)
        else:
            raise RuntimeError("CF006 expected internal rejection")
        rejects.append(label)

    async def unchanged_public_tables():
        values = await preserved()
        return {k: v for k, v in values.items() if k not in {"auth_users", "auth_identities", "auth_sessions", "flow_runs"}}

    public_before = await unchanged_public_tables()
    async def wait_lock(pid):
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            if await scalar("SELECT wait_event_type FROM pg_stat_activity WHERE pid=:pid", {"pid": pid}) == "Lock":
                return
            await asyncio.sleep(0.02)
        raise RuntimeError("CF006 expected owned lock wait")

    async def await_task_signal(task, event):
        signal = asyncio.create_task(event.wait())
        try:
            done, _ = await asyncio.wait({task, signal}, timeout=15, return_when=asyncio.FIRST_COMPLETED)
            if task in done:
                # Preserve the fixed internal failure instead of masking it by
                # waiting for a barrier that a failed task can never signal.
                try:
                    task.result()
                except domain.SnapshotError as exc:
                    labels = {code: "prepare_first_" + code for code in domain.ERRORS}
                    safe_print({"phase": "cf006_check", "label": labels[exc.code], "status": "failed"})
                    raise
            check(signal in done, "CF006 commit barrier not reached")
        finally:
            signal.cancel()
            await asyncio.gather(signal, return_exceptions=True)

    def hold_commit(session):
        original = session.commit
        async def commit():
            ready.set(); await asyncio.wait_for(release.wait(), 15); await original()
        session.commit = commit
    safe_print({"phase": "cf006_check", "label": "prepare_first_downgrade", "status": "started"})
    # Prepare commits first while downgrade waits on parent table lock.
    ready, release = asyncio.Event(), asyncio.Event()
    candidate = await admit(); tasks = []
    check(await scalar("SELECT count(*) FROM flow_input_snapshots") == 0, "CF006 prepare-first starts empty")
    try:
        sealing = asyncio.create_task(prepare(candidate, hook=hold_commit)); tasks.append(sealing)
        await await_task_signal(sealing, ready)
        started, pids = asyncio.Event(), {}
        downgrade = asyncio.create_task(migration(proof, "c3001a7e0001", downgrade=True, started=started, pids=pids)); tasks.append(downgrade)
        await asyncio.wait_for(started.wait(), 15); await wait_lock(pids["migration"])
        release.set(); sealed = await asyncio.wait_for(sealing, 15)
        try:
            await downgrade
        except RuntimeError:
            pass
        else:
            raise RuntimeError("CF006 nonempty downgrade accepted")
        check(await scalar("SELECT version_num FROM alembic_version") == "c6001a7e0001" and await get(candidate) == sealed, "CF006 prepare first downgrade refuses atomically")
    finally:
        release.set()
        for task in tasks:
            if not task.done(): task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    check(await scalar("SELECT count(*) FROM flow_input_snapshots") == 1, "CF006 prepare-first commit sole snapshot")
    mark("first_snapshot_commit_before_downgrade_atomic_refusal")
    run = await admit()
    async with owned_session(proof) as session:
        check((await authenticate(session, ta)).user_id == pa.user_id, "CF006 actual session authentication")
    first = await prepare(run)
    check(first == await get(run) == await prepare(run, principal=pa2), "CF006 first seal independent read replay")
    first.body["fixture"]["data"]["rows"][0]["foreign"] = 0
    with patch.object(domain, "FIXTURES", {}), patch.object(domain, "SPEC", {}), patch.object(domain, "_data", side_effect=RuntimeError("synthetic generator change")):
        check(await get(run) == first, "CF006 stored read independent of catalog and generator")
        await denied(prepare(run), "invalid", "changed_catalog_not_resealed")
    check(await get(run) == first, "CF006 independent parsed copy")
    await denied(prepare(run, "flow.synthetic.short4"), "conflict", "different_fixture_conflict")
    before_denials = await scalar("SELECT count(*) FROM flow_input_snapshots")
    for principal in (pb, pe, pr, replace(pa, user_id=pb.user_id), replace(pa, token_digest=b"x"*32)):
        code = "not_found" if principal == pb else "auth_required"
        await denied(get(run, principal), code, "owner_or_session_read_denied")
        await denied(prepare(run, principal=principal), code, "owner_or_session_prepare_denied")
    await denied(get(uuid4(), pb), "not_found", "absent_same_not_found")
    check(await scalar("SELECT count(*) FROM flow_input_snapshots") == before_denials, "CF006 rejection writes zero")
    mark("seal_independent_read_actual_session_owner_replay_catalog_and_no_execution")

    safe_print({"phase": "cf006_check", "label": "physical_constraints", "status": "started"})
    # Every negative constraint case uses a distinct unsealed receipt to avoid
    # mistaking the run UNIQUE failure for the constraint under test.
    async def sql_reject(label, expected, sql=None, changes=None):
        if sql is None:
            candidate = await admit()
            async with owned_session(proof) as session:
                source = await session.get(FlowRun, candidate)
                body = domain.build(source, "flow.synthetic.short4")
            values = dict(id=uuid4(), run_id=candidate, owner_user_id=pa.user_id, contract_version=1,
                          mode="synthetic_only", input_json=body, input_sha256=domain.digest(body))
            values.update(changes or {})
            statement = insert(FlowInputSnapshot).values(**values)
        else:
            statement = text(sql)
        try:
            async with owned_session(proof) as session:
                await session.execute(statement)
                await session.commit()
        except DBAPIError as exc:
            state = getattr(exc.orig, "sqlstate", None)
            check(state == expected, "CF006 exact SQLSTATE " + label)
            rejects.append(label)
        else:
            raise RuntimeError("CF006 expected SQL rejection")

    for label, changes, state in [
        ("owner_composite_FK", {"owner_user_id": pb.user_id}, "23503"),
        ("missing_parent_FK", {"run_id": uuid4()}, "23503"),
        ("version_CHECK", {"contract_version": 2}, "23514"),
        ("mode_CHECK", {"mode": "executable"}, "23514"),
        ("finite_time_CHECK", {"sealed_at": text("'infinity'::timestamptz")}, "23514"),
        ("digest_CHECK", {"input_sha256": "A"*64}, "23514"),
        ("wrong_digest_CHECK", {"input_sha256": "0"*64}, "23514"),
    ]:
        await sql_reject(label, state, changes=changes)
    for raw in ("{}", "[]", '{"contract_version":1}', '{"mode":"synthetic_only"}', '{"contract_version":true,"mode":"synthetic_only"}', '{"contract_version":2,"mode":"synthetic_only"}', '{"contract_version":1,"mode":"execute"}', json.dumps({"contract_version": 1, "mode": "synthetic_only", "padding": "x"*131073})):
        await sql_reject("body_CHECK", "23514", changes={"input_json": raw, "input_sha256": domain.digest(raw)})
    await sql_reject("malformed_JSON", "22P02", changes={"input_json": "{", "input_sha256": domain.digest("{")})
    for name in ("id", "run_id", "owner_user_id", "contract_version", "mode", "input_json", "input_sha256", "sealed_at"):
        await sql_reject("NOT_NULL_" + name, "23502", changes={name: None})
    async with owned_session(proof) as session:
        existing = await session.get(FlowInputSnapshot, first.id)
        duplicate = {c.name: getattr(existing, c.name) for c in FlowInputSnapshot.__table__.columns}
        duplicate["id"] = uuid4()
    try:
        async with owned_session(proof) as session:
            await session.execute(insert(FlowInputSnapshot).values(**duplicate)); await session.commit()
    except DBAPIError as exc:
        check(getattr(exc.orig, "sqlstate", None) == "23505", "CF006 run UNIQUE")
        rejects.append("run_UNIQUE")
    else:
        raise RuntimeError("CF006 duplicate run accepted")
    for statement in ("UPDATE flow_input_snapshots SET mode=mode", "DELETE FROM flow_input_snapshots"):
        await sql_reject("immutable_trigger", "23514", sql=statement)
    await sql_reject("parent_delete_RESTRICT", "23503", sql=f"DELETE FROM flow_runs WHERE id='{run}'")
    await sql_reject("parent_owner_RESTRICT", "23503", sql=f"UPDATE flow_runs SET owner_user_id='{pb.user_id}' WHERE id='{run}'")
    check(await get(run) == first, "CF006 physical denials preserve seal")
    mark("physical_FK_UNIQUE_NOT_NULL_CHECK_immutable_and_parent_RESTRICT")

    safe_print({"phase": "cf006_check", "label": "preparation_races", "status": "started"})
    for different in (False, True):
        candidate = await admit()
        pids = [{"ready": asyncio.Event()}, {"ready": asyncio.Event()}]
        tasks = []
        try:
            async with owned_session(proof) as blocker:
                await blocker.execute(select(FlowRun).where(FlowRun.id == candidate).with_for_update())
                tasks = [asyncio.create_task(prepare(candidate, "flow.synthetic.full20", pid=pids[0])),
                         asyncio.create_task(prepare(candidate, "flow.synthetic.short4" if different else "flow.synthetic.full20", pid=pids[1]))]
                await asyncio.gather(*(asyncio.wait_for(p["ready"].wait(), 15) for p in pids))
                await asyncio.gather(*(wait_lock(p["pid"]) for p in pids))
                await blocker.commit()
            results = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), 20)
            good = [r for r in results if isinstance(r, domain.SealedInput)]
            if different:
                check(len(good) == 1 and sum(isinstance(r, domain.SnapshotError) and r.code == "conflict" for r in results) == 1, "CF006 different preparation race")
            else:
                check(len(good) == 2 and good[0] == good[1], "CF006 identical preparation race")
            check(await scalar("SELECT count(*) FROM flow_input_snapshots WHERE run_id=:id", {"id": candidate}) == 1, "CF006 one race winner row")
        finally:
            for task in tasks:
                if not task.done(): task.cancel()
            if tasks: await asyncio.gather(*tasks, return_exceptions=True)
    mark("barrier_attested_connections_same_and_different_preparation_races")

    safe_print({"phase": "cf006_check", "label": "commit_outcomes", "status": "started"})
    # Pre-commit rollback and post-commit lost ACK are distinct DB outcomes.
    for outcome in ("before_commit", "after_insert", "ack_lost"):
        candidate = await admit()
        captured = {}
        def hook(session):
            original = session.commit
            async def commit():
                if outcome == "ack_lost":
                    # Capture the uncommitted original before a real DB commit.
                    seal = await session.scalar(select(FlowInputSnapshot).where(FlowInputSnapshot.run_id == candidate))
                    captured["id"] = seal.id
                    await original()
                raise OSError("CF006 synthetic commit acknowledgement failure")
            if outcome == "after_insert":
                from src.modules.flow.infrastructure import input_snapshot_repository as repo
                original_insert = repo.insert_snapshot
                async def failed_insert(*args, **kwargs):
                    await original_insert(*args, **kwargs)
                    raise RuntimeError("CF006 synthetic post INSERT failure")
                captured["patch"] = patch.object(repo, "insert_snapshot", failed_insert)
                captured["patch"].start()
            else:
                session.commit = commit
        try:
            await denied(prepare(candidate, hook=hook), "unavailable", "fixed_" + outcome)
        finally:
            if "patch" in captured: captured["patch"].stop()
        count = await scalar("SELECT count(*) FROM flow_input_snapshots WHERE run_id=:id", {"id": candidate})
        check(count == (1 if outcome == "ack_lost" else 0), "CF006 commit outcome exact residue")
        recovered = await prepare(candidate)
        if outcome == "ack_lost":
            check(recovered.id == captured["id"] and recovered == await get(candidate), "CF006 committed ACK loss original reused")
    # Caller loses a successful response: no database failure or re-seal.
    candidate = await admit(); lost = await prepare(candidate)
    check(await prepare(candidate) == lost, "CF006 post response loss original reused")
    mark("confirmed_rollback_zero_and_committed_ACK_or_response_loss_original_reused")

    safe_print({"phase": "cf006_check", "label": "session_races", "status": "started"})
    # Revoke wins while holding the actual session lock; prepare must wait and fail.
    async with owned_session(proof) as session:
        user = await session.get(AuthUser, pa.user_id)
        _, revoked_race = await issue_session(session, user)
        _, prepared_race = await issue_session(session, user)
        await session.commit()
    candidate = await admit(); pid = {"ready": asyncio.Event()}; tasks = []
    try:
        async with owned_session(proof) as revoker:
            await revoker.execute(update(AuthSession).where(AuthSession.id == revoked_race.session_id).values(revoked_at=func.clock_timestamp()))
            task = asyncio.create_task(prepare(candidate, principal=revoked_race, pid=pid)); tasks.append(task)
            await asyncio.wait_for(pid["ready"].wait(), 15); await wait_lock(pid["pid"])
            await revoker.commit()
        await denied(task, "auth_required", "revoke_first_prepare_denied")
        check(await scalar("SELECT count(*) FROM flow_input_snapshots WHERE run_id=:id", {"id": candidate}) == 0, "CF006 revoke first writes zero")
    finally:
        for task in tasks:
            if not task.done(): task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    # Prepare holds SHARE and run locks until actual commit, revocation waits.
    ready, release = asyncio.Event(), asyncio.Event()
    candidate = await admit(); pid = {"ready": asyncio.Event()}; tasks = []
    async def revoke_waiter():
        async with owned_session(proof) as session:
            pid["pid"] = await session.scalar(text("SELECT pg_backend_pid()")); pid["ready"].set()
            await revoke_session(session, prepared_race)
    try:
        sealing = asyncio.create_task(prepare(candidate, principal=prepared_race, hook=hold_commit)); tasks.append(sealing)
        await await_task_signal(sealing, ready)
        revocation = asyncio.create_task(revoke_waiter()); tasks.append(revocation)
        await asyncio.wait_for(pid["ready"].wait(), 15); await wait_lock(pid["pid"])
        release.set(); sealed = await asyncio.wait_for(sealing, 15); await asyncio.wait_for(revocation, 15)
        await denied(get(candidate, prepared_race), "auth_required", "prepare_first_future_read_denied")
        check((await get(candidate)).id == sealed.id, "CF006 committed seal persists after revoke")
    finally:
        release.set()
        for task in tasks:
            if not task.done(): task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    mark("actual_session_lock_revoke_first_and_prepare_first")

    safe_print({"phase": "cf006_check", "label": "source_drift", "status": "started"})
    for values in ({"request_input": {"ticker": "005930", "question": "drift", "as_of": "2026-11-08T00:00:00+00:00"}},
                   {"admission_request_id": uuid4()}, {"attempt_id": uuid4()}, {"input_fingerprint": "0"*64}):
        async with owned_session(proof) as session:
            source = await session.get(FlowRun, run)
            old = {key: getattr(source, key) for key in values}
            await session.execute(update(FlowRun).where(FlowRun.id == run).values(**values)); await session.commit()
        await denied(get(run), "corrupt", "source_drift_read_closed")
        await denied(prepare(run), "corrupt", "source_drift_prepare_closed")
        async with owned_session(proof) as session:
            stored = await session.get(FlowInputSnapshot, first.id)
            check(stored.input_json == first.input_json, "CF006 drift does not rewrite seal")
            await session.execute(update(FlowRun).where(FlowRun.id == run).values(**old)); await session.commit()
    mark("source_request_reference_drift_fail_closed_without_snapshot_rewrite")

    check(await unchanged_public_tables() == public_before, "CF006 report index stock writes zero")
    check(await get(run) == first, "CF006 original bytes final unchanged")
    check(await scalar("SELECT count(*) FROM flow_runs WHERE admission_mode <> 'receipt_only' OR execution_status <> 'pending' OR storage_status <> 'not_stored'") == 0, "CF006 no execution promotion")
    mark("prepare_first_nonempty_downgrade_refused_original_data_and_public_contract_preserved")
    return {"status": "passed", "groups": passed, "sql_and_internal_rejections": len(rejects)}


async def verify_downgrade_first(proof):
    """Separate fresh owned DB. Deliberately leaves c3001; never recreates the table."""
    with isolated_application(proof) as observed:
        from sqlalchemy import select, text
        from scripts.cf002_interactive_login import owned_session
        from db.models.auth.models import AuthUser
        from src.modules.auth.application.session_service import issue_session
        from src.modules.flow.api.run_schemas import FlowAdmissionRequest
        from src.modules.flow.application.run_service import FlowRunService
        from src.modules.flow.application.input_preparation_service import InputPreparationService
        from src.modules.flow.domain.input_snapshot import SnapshotError
        async with owned_session(proof) as session:
            user = AuthUser(id=uuid4()); session.add(user); await session.flush()
            _, principal = await issue_session(session, user); await session.commit()
            run = await FlowRunService(session, principal=principal).admit(FlowAdmissionRequest(ticker="005930", question="CF006 lock-first", as_of="2026-11-08T00:00:00Z", idempotency_key="lock-first"), uuid4())
        locked, release, started = asyncio.Event(), asyncio.Event(), asyncio.Event()
        pid, tasks = {}, []
        async def late_prepare():
            async with owned_session(proof) as session:
                pid["value"] = await session.scalar(text("SELECT pg_backend_pid()")); started.set()
                return await InputPreparationService(session, principal=principal).prepare(run.run_id, "flow.synthetic.full20")
        try:
            downgrade = asyncio.create_task(snapshot_migration(proof, "c3001a7e0001", locked=locked, release=release)); tasks.append(downgrade)
            await asyncio.wait_for(locked.wait(), 15)
            preparing = asyncio.create_task(late_prepare()); tasks.append(preparing)
            await asyncio.wait_for(started.wait(), 15)
            deadline = time.monotonic() + 12
            while True:
                async with owned_session(proof) as session:
                    waiting = await session.scalar(text("SELECT wait_event_type FROM pg_stat_activity WHERE pid=:pid"), {"pid": pid["value"]})
                if waiting == "Lock": break
                check(time.monotonic() < deadline, "CF006 downgrade-first owned lock wait")
                await asyncio.sleep(0.02)
            release.set(); await asyncio.wait_for(downgrade, 15)
            try:
                await preparing
            except SnapshotError as exc:
                check(exc.code == "unavailable", "CF006 late prepare fixed failure")
            else:
                raise RuntimeError("CF006 late prepare returned success")
            async with owned_session(proof) as session:
                check(await session.scalar(text("SELECT version_num FROM alembic_version")) == "c3001a7e0001"
                      and await session.scalar(text("SELECT to_regclass('flow_input_snapshots')")) is None, "CF006 downgrade-first left table absent without recovery")
            check(not any(observed.values()), "CF006 downgrade-first forbidden access")
            return {"status": "passed", "groups": ["downgrade_lock_first_late_prepare_fixed_failure_no_recreate"], "observed_denials": dict(observed)}
        finally:
            release.set()
            for task in tasks:
                if not task.done(): task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
