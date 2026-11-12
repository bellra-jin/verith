"""v0.6 owned disposable DB and env-free interactive Google check.

--verify-owned-db / --verify-fake-environment never read real credentials or call
Google. --google-input approved-file is the already-approved, separately reviewed
runtime action; only the exec-isolated Backend reads the two keys. No Console automation.
"""

from __future__ import annotations
import argparse
import asyncio
from contextlib import ExitStack, asynccontextmanager
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from scripts.google_login_workspace import (  # noqa: E402
    prepare_projects,  # noqa: E402
    child_base_environment,
    ensure_local_ports_free,
)
from scripts.runner_owned_database import LocalDocker, OwnedPostgres  # noqa: E402


def safe_print(data):
    print(json.dumps(data, ensure_ascii=False), flush=True)


def cf003_failure_diagnostic(error, stage):
    """Fixed CF-003 diagnostics only: never exception text, locals or runtime paths."""
    stages = {"local_context", "owned_creation", "migration", "admission_check", "cleanup"}
    kinds = {"OwnedDatabaseError", "VerificationFailure", "TimeoutError", "TimeoutExpired",
             "OSError", "PermissionError", "AssertionError", "RuntimeError", "AuthenticationRequired"}
    sources = {
        str(_BACKEND / "scripts/runner_owned_database.py"): "owned_database",
        str(_BACKEND / "scripts/cf002_interactive_login.py"): "db_runner",
        str(_BACKEND / "scripts/cf003_admission_check.py"): "admission_checker",
        str(_BACKEND / "scripts/cf018_usage_check.py"): "usage_checker",
        str(_BACKEND / "scripts/cf020_supervisor_check.py"): "supervisor_checker",
        str(_BACKEND / "scripts/cf022_supervisor_core_check.py"): "core_checker",
        str(_BACKEND / "scripts/cf023_supervisor_meaning_check.py"): "meaning_checker",
        str(_BACKEND / "scripts/cf035_technical_owned_check.py"): "technical_storage_checker",
        str(_BACKEND / "scripts/cf036_technical_owned_read_check.py"): "technical_read_checker",
    }
    functions = {"create", "verify_metadata", "call", "inspect", "verify", "sql",
                 "preflight", "attest_connection", "main", "migrate_owned",
                 "owned_session", "verify_admission", "check", "cleanup", "verify_owned_report_backend_reads",
                 "_prepare_owned_flow_read_anchor", "_verify_meaning_flow_crosspath", "capture_synthetic_epoch",
                 "verify_technical_admission", "_verify_admission",
                 "_create", "_verify_post_start", "_cleanup", "verify_usage", "_verify", "usage_migration"}
    frames = []
    trace = error.__traceback__
    while trace is not None:
        code = trace.tb_frame.f_code
        if code.co_filename in sources and code.co_name in functions:
            frames.append({"source": sources[code.co_filename], "function": code.co_name,
                           "line": trace.tb_lineno})
        trace = trace.tb_next
    return {"phase": "cf003_failure_diagnostic", "stage": stage if stage in stages else "other",
            "error_type": type(error).__name__ if type(error).__name__ in kinds else "other",
            "frames": frames[-8:]}


def cf006_failure_diagnostic(error, stage):
    result = cf003_failure_diagnostic(error, stage)
    result["phase"] = "cf006_failure_diagnostic"
    return result


async def migrate_owned(proof, *, target="head"):
    if target not in {"head", "c6001a7e0001", "c15001a7e0001"}:
        raise ValueError("Unsupported owned migration target")
    # No engine before this full, independently attested restricted-role check.
    await proof.preflight()
    proof._owner.sql(
        "CREATE EXTENSION IF NOT EXISTS pgcrypto;\nCREATE EXTENSION IF NOT EXISTS vector;"
    )
    from sqlalchemy.ext.asyncio import create_async_engine
    from alembic import command
    from alembic.config import Config

    engine = create_async_engine(proof.url, connect_args=proof.connection_parameters())
    try:
        async with engine.connect() as connection:
            await proof.attest_connection(connection)

            def upgrade(sync):
                config = Config(str(_BACKEND / "alembic.ini"))
                config.set_main_option(
                    "script_location", str(_BACKEND / "db/migrations")
                )
                config.attributes.update(connection=sync, verified_test_mode=True)
                command.upgrade(config, target)

            await connection.run_sync(upgrade)
            await connection.commit()
    finally:
        await engine.dispose()


@asynccontextmanager
async def owned_session(proof):
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    await proof.preflight()
    engine = create_async_engine(proof.url, connect_args=proof.connection_parameters())
    try:
        async with engine.connect() as connection:
            await proof.attest_connection(connection)
            async with AsyncSession(bind=connection, expire_on_commit=False) as session:
                yield session
    finally:
        await engine.dispose()


async def internal_check(proof):
    from uuid import uuid4
    from sqlalchemy import delete
    from db.models.auth.models import AuthUser, AuthSession
    from db.models.common.stock import Stock
    from src.modules.auth.application.session_service import issue_session
    from src.modules.flow.application.report_service import FlowReportService
    from src.modules.flow.api.schemas import FlowReportSaveRequest
    from tests.fixtures.flow_payload import make_flow_payload

    async with owned_session(proof) as session:
        user = AuthUser(id=uuid4())
        session.add(user)
        await session.flush()
        _, principal = await issue_session(session, user)
        payload = make_flow_payload()
        payload["meta"]["ticker"] = "999989"
        service = FlowReportService(session, principal=principal)
        saved = await service.save_report(
            FlowReportSaveRequest(
                payload=payload, question="owned interactive DB synthetic verification"
            )
        )
        assert (await service.get_report(saved.report_id)).report == payload
        assert (await service.list_report_archive()).total == 1
        assert await service.delete_report(saved.report_id)
        assert await service.get_report(saved.report_id) is None
        await session.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
        await session.execute(delete(AuthUser).where(AuthUser.id == user.id))
        await session.execute(delete(Stock).where(Stock.stock_code == "999989"))
        await session.commit()


async def database_status(proof):
    from sqlalchemy import text

    async with owned_session(proof) as session:
        row = (
            (
                await session.execute(
                    text(
                        "SELECT (SELECT count(*) FROM auth_users) AS users, (SELECT count(*) FROM auth_identities) AS identities, (SELECT count(*) FROM auth_sessions) AS sessions, (SELECT count(*) FROM auth_sessions WHERE revoked_at IS NOT NULL) AS revoked, (SELECT count(*) FROM auth_sessions WHERE revoked_at IS NULL AND expires_at>clock_timestamp()) AS active_sessions, (SELECT count(*) FROM flow_reports) AS synthetic_reports"
                    )
                )
            )
            .mappings()
            .one()
        )
        return dict(row)


class ChildProcess:
    def __init__(self, pid, kind, popen=None):
        self.pid, self.kind, self.popen = pid, kind, popen
        self.start_time = self._start_time()
        for _ in range(100):
            if self._pgid() == pid:
                self.start_time = self._start_time()
                if self.start_time:
                    break
            time.sleep(0.01)
        if not self.start_time or self._pgid() != pid:
            self._abort_startup()
            raise RuntimeError(
                "Owned application child did not establish its process group"
            )

    def _abort_startup(self):
        # A not-yet-registered child may still belong to our process group; never
        # signal that group. Use its direct-parent/start-time creation identity.
        result = subprocess.run(
            ["ps", "-p", str(self.pid), "-o", "ppid="],
            capture_output=True,
            text=True,
            env=child_base_environment(),
            timeout=3,
        )
        if (
            result.returncode == 0
            and result.stdout.strip() == str(os.getpid())
            and self._start_time() == self.start_time
        ):
            try:
                if self._pgid() == self.pid:
                    os.killpg(self.pid, signal.SIGKILL)
                else:
                    os.kill(self.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if self.popen is not None:
            self.popen.wait(timeout=5)
        else:
            try:
                os.waitpid(self.pid, 0)
            except ChildProcessError:
                pass

    def _start_time(self):
        result = subprocess.run(
            ["ps", "-p", str(self.pid), "-o", "lstart="],
            capture_output=True,
            text=True,
            env=child_base_environment(),
            timeout=3,
        )
        return result.stdout.strip() if result.returncode == 0 else None

    def _pgid(self):
        try:
            return os.getpgid(self.pid)
        except ProcessLookupError:
            return None

    def cleanup(self):
        if getattr(self, "config_write", None) is not None:
            try:
                os.close(self.config_write)
            except OSError:
                pass
            self.config_write = None
        if getattr(self, "life_write", None) is not None:
            os.close(self.life_write)
            self.life_write = None
        current = self._start_time()
        if current is None:
            return
        if self.start_time is None:
            self._abort_startup()
            return
        if current != self.start_time or self._pgid() != self.pid:
            raise RuntimeError(
                "Owned application process identity changed; cleanup refused"
            )
        try:
            os.killpg(self.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        # Keep the leader unreaped while checking/sending signals, preventing PID reuse.
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            status = subprocess.run(
                ["ps", "-p", str(self.pid), "-o", "stat="],
                capture_output=True,
                text=True,
                env=child_base_environment(),
                timeout=3,
            )
            if status.returncode or status.stdout.strip().startswith("Z"):
                break
            time.sleep(0.05)
        if self._start_time() == self.start_time and self._pgid() == self.pid:
            try:
                os.killpg(self.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if self.popen is not None:
            self.popen.wait(timeout=5)
        else:
            try:
                os.waitpid(self.pid, 0)
            except ChildProcessError:
                pass


def runtime_database_dto(proof):
    proof.verify_ownership()
    params = proof.connection_parameters()
    return dict(
        database=proof.database,
        username=proof.username,
        resource_id=proof.resource_id,
        server_port=proof.server_port,
        host=params["host"],
        port=params["port"],
        password=params["password"],
    )


def start_apps(
    project, proof, mode, source, lifetime, children, *, fail_after_backend=False, backend_only=False
):
    import secrets

    if backend_only and mode != "fake":
        raise RuntimeError("Backend-only check requires synthetic authentication")

    run_nonce = secrets.token_hex(32)
    # Static, non-secret helpers only; no original Backend import path in child exec.
    for original, name in [
        ("tests/db_safety.py", "runtime_db_guard.py"),
    ]:
        import shutil

        shutil.copyfile(_BACKEND / original, project.backend / name)
    if mode == "fake":
        from tests.fixtures.flow_payload import make_flow_payload

        (project.backend / "runtime_fixture_payload.json").write_text(
            json.dumps(make_flow_payload())
        )
    if not backend_only:
        config = project.frontend / "next.config.ts"
        text = config.read_text()
        if "headers()" in text:
            raise RuntimeError("Unexpected Next readiness configuration")
        config.write_text(
            text.replace(
                "const nextConfig: NextConfig = {",
                "const nextConfig: NextConfig = {\n  async headers() { return [{source: '/:path*', headers: [{key: 'X-CF002-Run', value: '"
                + run_nonce
                + "'}]}]; },",
                1,
            )
        )
    roles = (("backend", project.backend),) if backend_only else (("backend", project.backend), ("frontend", project.frontend))
    for role, root in roles:
        config_read, config_write = os.pipe()
        life_read, life_write = os.pipe()
        dto = dict(
            project_root=str(root), run_nonce=run_nonce, lifetime_seconds=lifetime
        )
        if role == "backend":
            dto.update(
                database=runtime_database_dto(proof),
                google_mode=mode,
                google_source=str(source),
            )
        blocked = {signal.SIGINT, signal.SIGTERM}
        previous = signal.pthread_sigmask(signal.SIG_BLOCK, blocked)
        try:
            environment = child_base_environment()
            if backend_only:
                environment.update(HOME=str(project.root / "cf047-home"), PYTHONDONTWRITEBYTECODE="1")
            process = subprocess.Popen(
                [
                    sys.executable,
                    str(_BACKEND / "scripts/google_login_bootstrap.py"),
                    "--role",
                    role,
                    "--config-fd",
                    str(config_read),
                    "--life-fd",
                    str(life_read),
                ],
                cwd=root,
                env=environment,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
                pass_fds=(config_read, life_read),
            )
            # Register the raw spawn receipt before validation or signal delivery.
            record = ChildProcess.__new__(ChildProcess)
            record.pid, record.kind, record.popen = process.pid, role, process
            record.start_time = None
            record.life_write = life_write
            record.config_write = config_write
            children.append(record)
        except BaseException:
            os.close(config_write)
            os.close(life_write)
            raise
        finally:
            os.close(config_read)
            os.close(life_read)
            signal.pthread_sigmask(signal.SIG_SETMASK, previous)
        try:
            record.start_time = record._start_time()
            if not record.start_time or record._pgid() != record.pid:
                raise RuntimeError("Owned child spawn identity verification failed")
            with os.fdopen(config_write, "w", encoding="utf-8") as pipe:
                json.dump(dto, pipe)
            record.config_write = None
            if role == "backend" and fail_after_backend:
                raise RuntimeError("Synthetic partial-startup failure")
        except BaseException:
            try:
                os.close(config_write)
            except OSError:
                pass
            record.config_write = None
            for child in reversed(children):
                child.cleanup()
            raise
    return run_nonce


def _child_is_alive(child):
    if child._start_time() != child.start_time or child._pgid() != child.pid:
        return False
    status = subprocess.run(
        ["ps", "-p", str(child.pid), "-o", "stat="],
        capture_output=True,
        text=True,
        env=child_base_environment(),
        timeout=3,
    )
    return (
        status.returncode == 0
        and status.stdout.strip()
        and not status.stdout.strip().startswith("Z")
    )


def _application_owns_port(child, port):
    result = subprocess.run(
        ["lsof", "-nP", "-a", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
        capture_output=True,
        text=True,
        env=child_base_environment(),
        timeout=3,
    )
    pids = result.stdout.split()
    if result.returncode or not pids or not all(value.isdigit() for value in pids):
        return False
    for value in pids:
        try:
            if os.getpgid(int(value)) != child.pid:
                return False
        except ProcessLookupError:
            return False
    return True


def wait_readiness(run_nonce, children, *, timeout_seconds=45, client_factory=None, backend_only=False):
    import httpx

    deadline = time.monotonic() + timeout_seconds
    roles = {child.kind: child for child in children}
    if len(roles) != len(children) or set(roles) != ({"backend"} if backend_only else {"backend", "frontend"}):
        raise RuntimeError("Expected owned child roles are missing")
    if client_factory is None:
        client_factory = httpx.Client
    with client_factory(timeout=2, follow_redirects=False, trust_env=False) as client:
        while time.monotonic() < deadline:
            if any(not _child_is_alive(child) for child in children):
                raise RuntimeError("Owned child exited or changed before readiness")
            if not _application_owns_port(
                roles["backend"], 8200
            ) or (not backend_only and not _application_owns_port(roles["frontend"], 3200)):
                time.sleep(0.1)
                continue
            try:
                backend = client.get("http://localhost:8200/health")
                frontend = None if backend_only else client.get("http://localhost:3200/")
                session = client.get("http://localhost:8200/api/auth/session" if backend_only else "http://localhost:3200/api/auth/session")
                if (
                    backend.status_code == 200
                    and (backend_only or frontend.status_code == 200)
                    and session.status_code == 401
                    and all(
                        response.headers.get("x-cf002-run") == run_nonce
                        for response in ((backend, session) if backend_only else (backend, frontend, session))
                    )
                ):
                    # Bind ownership must still hold after requests, not just before.
                    if (
                        all(_child_is_alive(child) for child in children)
                        and _application_owns_port(roles["backend"], 8200)
                        and (backend_only or _application_owns_port(roles["frontend"], 3200))
                    ):
                        return
            except httpx.HTTPError:
                pass
            time.sleep(0.1)
    raise RuntimeError("Owned local application readiness timed out")


def verify_owned_report_backend_reads(project, proof, anchor, children, deadline):
    """CF047 fixed GET-only observation through two sequential real Backend execs.

    The original owner retains the DB and expected payload/private anchor.
    Cookies travel only in localhost GET headers, never bootstrap DTO/argv/env/log.
    """
    import hashlib
    import httpx
    from scripts.cf003_admission_check import check, isolated_application
    from src.modules.auth.api.router import SESSION_COOKIE

    def remaining():
        seconds=deadline-time.monotonic()
        check(seconds>0,'CF047 absolute parent deadline')
        return seconds

    async def guarded(callback):
        with isolated_application(proof) as observed:
            result=await callback()
            check(not any(observed.values()),'CF047 parent observation forbidden access')
            return result

    def observe(callback):
        return asyncio.run(asyncio.wait_for(guarded(callback),timeout=min(30,remaining())))

    def source_state():
        return {str(p.relative_to(project.backend)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in project.backend.rglob('*') if p.is_file()
            and (p.is_relative_to(project.backend/'src') or p.is_relative_to(project.backend/'db') or p.name=='alembic.ini')
            and p.suffix in {'.py','.ini','.mako'}}

    def absent_listener():
        result=subprocess.run(['lsof','-nP','-a','-iTCP:8200','-sTCP:LISTEN','-t'],capture_output=True,text=True,
            env=child_base_environment(),timeout=min(3,remaining()))
        check(result.returncode==1 and not result.stdout.strip(),'CF047 Backend listener absent')

    def get(client,child,nonce,path,identity):
        check(_child_is_alive(child) and _application_owns_port(child,8200),'CF047 current child owns observation port')
        value=client.get('http://localhost:8200'+path,headers={'cookie':SESSION_COOKIE+'='+identity[0]},timeout=min(5,remaining()))
        check(value.headers.get('x-cf002-run')==nonce,'CF047 current Backend nonce')
        check(_child_is_alive(child) and _application_owns_port(child,8200),'CF047 child identity after observation')
        return value

    baseline=None;pids=[];nonces=[];groups=[]
    try:
        baseline=source_state();committed=observe(anchor['committed_state'])
        for number in (1,2):
            check(remaining()>=30,'CF047 finite child watchdog budget')
            owned=[]
            try:
                nonce=start_apps(project,proof,'fake',None,min(300,int(remaining())),owned,backend_only=True)
                children.extend(owned)
                check(len(owned)==1 and owned[0].kind=='backend','CF047 only Backend child')
                child=owned[0]
                check(child.pid not in pids and nonce not in nonces,'CF047 fresh Backend PID and nonce')
                wait_readiness(nonce,owned,timeout_seconds=min(45,remaining()),backend_only=True)
                check(source_state()==baseline,'CF047 Backend source before reads')
                check(observe(anchor['committed_state'])==committed,'CF047 startup probe fully rolled back')
                observe(anchor['assert_current'])
                with httpx.Client(follow_redirects=False,trust_env=False,timeout=5) as client:
                    path='/api/flow/reports/'+anchor['report_id']
                    anchor['detail'](get(client,child,nonce,path,anchor['a2']))
                    anchor['listing'](get(client,child,nonce,'/api/flow/reports',anchor['a2']),True)
                    anchor['denied'](get(client,child,nonce,path,anchor['other']),404)
                    anchor['listing'](get(client,child,nonce,'/api/flow/reports',anchor['other']),False)
                    check(observe(anchor['committed_state'])==committed,'CF047 child GET no committed writes')
                    observe(anchor['assert_current'])
                    if number==2:
                        observe(anchor['revoke_a2'])
                        anchor['denied'](get(client,child,nonce,path,anchor['a2']),401)
                        denied=get(client,child,nonce,'/api/flow/reports',anchor['a2'])
                        check(denied.status_code==401 and denied.headers.get('cache-control')=='private, no-store'
                              and denied.json()=={'detail':{'code':'AUTH_REQUIRED','message':'인증이 필요합니다.'}},'CF047 revoked child list private')
                        anchor['detail'](get(client,child,nonce,path,anchor['primary']))
                        observe(anchor['assert_current'])
                        observe(anchor['remove_index'])
                        anchor['denied'](get(client,child,nonce,path,anchor['primary']),404)
                        hidden=anchor['listing'](get(client,child,nonce,'/api/flow/reports',anchor['primary']),False)
                        check(hidden['count']==0,'CF047 child omits index-only orphan')
                        observe(anchor['assert_current'])
                        groups.extend(['A2_revoked_child401_A1_valid','index_only_missing_root_preserved_child404_list_omits'])
                pids.append(child.pid);nonces.append(nonce)
                groups.append('Backend'+str(number)+'_new_PID_A2_lossless_list_detail_no_calls')
                safe_print({'phase':'cf047_backend_read','number':number,'pid':child.pid,'status':'passed',
                            'HTTP_methods':['GET'],'startup_probe':'synthetic_write_outer_rollback'})
            finally:
                for child in reversed(owned):
                    if child not in children:children.append(child)
                    child.cleanup()
                    check(child.popen.poll() is not None and child._start_time() is None,'CF047 child exited and reaped')
                absent_listener()
        return {'groups':groups,'backend_PIDs':pids,'new_Backend_process':True,'GET_observation_only':True,
                'startup_probe_rollback_verified':True,'child_cleanup_confirmed':True,'real_provider_requests':0,'google_requests':0}
    finally:
        try:
            if baseline is not None:
                check(source_state()==baseline,'CF047 Backend source postcheck')
        finally:
            anchor.clear()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--verify-technical-owned-read-db", action="store_true")
    mode.add_argument("--verify-technical-owned-db", action="store_true")
    mode.add_argument("--verify-technical-admission-db", action="store_true")
    mode.add_argument("--verify-owned-db", action="store_true")
    mode.add_argument("--verify-controller", action="store_true")
    mode.add_argument("--verify-flow-admission-db", action="store_true")
    mode.add_argument("--verify-flow-input-snapshot-db", action="store_true")
    mode.add_argument("--verify-flow-fake-execution-db", action="store_true")
    mode.add_argument("--verify-flow-synthetic-demo-db", action="store_true")
    mode.add_argument("--verify-flow-usage-db", action="store_true")
    mode.add_argument("--verify-supervisor-flow-db", action="store_true")
    mode.add_argument("--verify-supervisor-core-db", action="store_true")
    mode.add_argument("--verify-supervisor-meaning-db", action="store_true")
    mode.add_argument("--verify-supervisor-meaning-assembly-db", action="store_true")
    mode.add_argument("--verify-supervisor-meaning-flow-db", action="store_true")
    mode.add_argument("--verify-flow-owned-report-read-db", action="store_true")
    mode.add_argument("--verify-supervisor-accounting-db", action="store_true")
    mode.add_argument("--verify-supervisor-meaning-runtime-db", action="store_true")
    mode.add_argument("--verify-flow-analysis-db", action="store_true")
    mode.add_argument("--verify-analysis-adapter-db", action="store_true")
    mode.add_argument("--verify-fundamental-analysis-db", action="store_true")
    mode.add_argument("--verify-fake-environment", action="store_true")
    mode.add_argument("--google-input", choices=["approved-file"])
    parser.add_argument("--lifetime-seconds", type=int, default=3600)
    parser.add_argument("--hold-fake-seconds", type=int, default=0)
    parser.add_argument("--simulate-startup-failure", action="store_true")
    args = parser.parse_args()
    if args.verify_technical_admission_db and sys.argv[1:] != ["--verify-technical-admission-db"]:
        parser.error("Technical admission check accepts no credential or lifecycle options")
    if args.verify_flow_owned_report_read_db and sys.argv[1:] != ["--verify-flow-owned-report-read-db"]:
        parser.error("Owned report read mode accepts no credential or lifecycle options")
    if (
        args.hold_fake_seconds or args.simulate_startup_failure
    ) and not args.verify_fake_environment:
        parser.error("Lifecycle test options require fake environment mode")
    if not 0 <= args.hold_fake_seconds <= 30:
        parser.error("Fake hold must be between 0 and 30 seconds")
    if not 30 <= args.lifetime_seconds <= 7200:
        parser.error("Finite lifetime must be between 30 and 7200 seconds")
    docker = owner = project = None
    db_test_context = ExitStack()
    children = []
    old_handlers = {}
    interrupted = False
    secondary_cleanup_failed = False
    cf006_failure_owner = None
    cf003_stage = "local_context"

    def stop(signum, frame):
        raise KeyboardInterrupt

    for signum in (signal.SIGINT, signal.SIGTERM):
        old_handlers[signum] = signal.signal(signum, stop)
    flow_read_deadline = flow_read_whole_deadline = None
    if args.verify_flow_owned_report_read_db:
        # One non-renewing 300s mode, reserving the final 30s for owned cleanup.
        flow_read_whole_deadline = time.monotonic() + 300
        flow_read_deadline = flow_read_whole_deadline - 30
        def read_expired(signum, frame):
            raise TimeoutError("Owned report read deadline exceeded")
        old_handlers[signal.SIGALRM] = signal.signal(signal.SIGALRM, read_expired)
        signal.setitimer(signal.ITIMER_REAL, 270)
    try:
        if args.verify_flow_owned_report_read_db:
            ensure_local_ports_free(backend_only=True)
        elif not (args.verify_supervisor_meaning_runtime_db or args.verify_supervisor_accounting_db or args.verify_owned_db or args.verify_controller or args.verify_flow_admission_db or args.verify_flow_input_snapshot_db or args.verify_flow_fake_execution_db or args.verify_flow_synthetic_demo_db or args.verify_technical_owned_read_db or args.verify_technical_admission_db or args.verify_technical_owned_db or args.verify_supervisor_meaning_assembly_db or args.verify_flow_owned_report_read_db or args.verify_supervisor_meaning_flow_db or args.verify_supervisor_meaning_db or args.verify_supervisor_core_db or args.verify_supervisor_flow_db or args.verify_flow_usage_db or args.verify_flow_analysis_db or args.verify_analysis_adapter_db or args.verify_fundamental_analysis_db):
            ensure_local_ports_free()
        docker = LocalDocker()
        if args.verify_flow_admission_db:
            from scripts.cf003_admission_check import owned_postgres_home

            db_test_context.enter_context(owned_postgres_home(docker))
        elif args.verify_flow_input_snapshot_db:
            from scripts.cf003_admission_check import owned_postgres_home

            db_test_context.enter_context(owned_postgres_home(docker))
        elif args.verify_flow_fake_execution_db:
            from scripts.cf003_admission_check import owned_postgres_home

            db_test_context.enter_context(owned_postgres_home(docker))
        elif args.verify_supervisor_meaning_runtime_db or args.verify_supervisor_accounting_db or args.verify_flow_synthetic_demo_db or args.verify_technical_owned_read_db or args.verify_technical_admission_db or args.verify_technical_owned_db or args.verify_supervisor_meaning_assembly_db or args.verify_flow_owned_report_read_db or args.verify_supervisor_meaning_flow_db or args.verify_supervisor_meaning_db or args.verify_supervisor_core_db or args.verify_supervisor_flow_db or args.verify_flow_usage_db or args.verify_flow_analysis_db or args.verify_analysis_adapter_db or args.verify_fundamental_analysis_db:
            from scripts.cf003_admission_check import owned_postgres_home

            db_test_context.enter_context(owned_postgres_home(docker))
        owner = OwnedPostgres(docker)
        cf006_failure_owner = owner
        cf003_stage = "owned_creation"
        proof = owner.create()
        receipt_output = proof.safe_receipt()
        if args.verify_supervisor_meaning_runtime_db or args.verify_supervisor_accounting_db or args.verify_technical_owned_read_db or args.verify_technical_admission_db or args.verify_technical_owned_db or args.verify_supervisor_meaning_assembly_db or args.verify_flow_owned_report_read_db or args.verify_supervisor_meaning_flow_db or args.verify_supervisor_meaning_db or args.verify_supervisor_core_db or args.verify_supervisor_flow_db or args.verify_flow_usage_db or args.verify_flow_analysis_db or args.verify_analysis_adapter_db or args.verify_fundamental_analysis_db:
            # The original nonce belongs only to private cleanup evidence.
            receipt_output = {key: receipt_output[key] for key in (
                "resource_id", "container_id", "created_at", "host", "port", "persistent_mounts", "cleanup_owner")}
        safe_print({"phase": "owned_resource_created", **receipt_output})
        cf003_stage = "migration"
        asyncio.run(asyncio.wait_for(migrate_owned(proof, target="c15001a7e0001" if args.verify_flow_usage_db else "c6001a7e0001" if (args.verify_flow_admission_db or args.verify_flow_input_snapshot_db) else "head"), timeout=90))
        safe_print(
            {
                "phase": "owned_preflight_and_same_connection_migration",
                "status": "passed",
            }
        )
        if args.verify_owned_db:
            asyncio.run(asyncio.wait_for(internal_check(proof), timeout=45))
            safe_print(
                {
                    "phase": "owned_db_internal_check",
                    "status": "passed",
                    "counts": asyncio.run(database_status(proof)),
                }
            )
            return
        if args.verify_controller:
            from scripts.cf002_controller_check import verify_controller

            result = asyncio.run(asyncio.wait_for(verify_controller(proof), timeout=90))
            safe_print({"phase": "synthetic_controller_check", **result})
            return
        if args.verify_flow_admission_db:
            from scripts.cf003_admission_check import verify_admission

            cf003_stage = "admission_check"
            result = asyncio.run(asyncio.wait_for(verify_admission(proof), timeout=180))
            safe_print({"phase": "flow_admission_db_check", **result})
            return
        if args.verify_flow_input_snapshot_db:
            from scripts.cf006_input_snapshot_check import verify_input_snapshot, verify_downgrade_first

            cf003_stage = "admission_check"
            result = asyncio.run(asyncio.wait_for(verify_input_snapshot(proof), timeout=300))
            safe_print({"phase": "flow_input_snapshot_db_check", **result})
            # A second minted resource is required: the lock-first experiment
            # must leave the table absent, never recreate it to recover a test.
            second_owner = OwnedPostgres(docker)
            cf006_failure_owner = second_owner
            try:
                cf003_stage = "owned_creation"
                second_proof = second_owner.create()
                safe_print({"phase": "cf006_lock_first_resource_created", **second_proof.safe_receipt()})
                cf003_stage = "migration"
                asyncio.run(asyncio.wait_for(migrate_owned(second_proof, target="c6001a7e0001"), timeout=90))
                cf003_stage = "admission_check"
                result = asyncio.run(asyncio.wait_for(verify_downgrade_first(second_proof), timeout=90))
                safe_print({"phase": "flow_input_snapshot_downgrade_first_check", **result})
            finally:
                try:
                    second_owner.cleanup()
                    safe_print({"phase": "owned_db_removed", "resource_id": second_owner.resource_id})
                except BaseException as error:
                    secondary_cleanup_failed = True
                    safe_print(cf006_failure_diagnostic(error, "cleanup"))
                    safe_print({"phase": "cleanup_failed", "resource_id": second_owner.resource_id,
                                "container_id": getattr(getattr(second_owner, "receipt", None), "container_id", None)})
                    raise
            return
        if args.verify_flow_fake_execution_db:
            from scripts.cf007_fake_execution_check import verify_fake_execution

            cf003_stage = "admission_check"
            result = asyncio.run(asyncio.wait_for(verify_fake_execution(proof), timeout=180))
            safe_print({"phase": "flow_fake_execution_db_check", **result})
            return
        if args.verify_flow_synthetic_demo_db:
            from scripts.cf008_synthetic_demo_check import verify_synthetic_demo

            cf003_stage = "admission_check"
            result = asyncio.run(asyncio.wait_for(verify_synthetic_demo(proof), timeout=180))
            safe_print({"phase": "flow_synthetic_demo_db_check", **result})
            return
        if args.verify_technical_owned_read_db:
            from scripts.cf036_technical_owned_read_check import verify_technical_owned_read
            cf003_stage = "admission_check"
            result = asyncio.run(asyncio.wait_for(verify_technical_owned_read(proof), timeout=180))
            safe_print({"phase":"technical_owned_read_db_check", **result})
            return
        if args.verify_technical_admission_db:
            from scripts.cf035_technical_owned_check import verify_technical_admission
            cf003_stage = "admission_check"
            result = asyncio.run(asyncio.wait_for(verify_technical_admission(proof),timeout=180))
            safe_print({"phase":"technical_admission_db_check",**result})
            return
        if args.verify_technical_owned_db:
            from scripts.cf035_technical_owned_check import verify_technical_owned
            cf003_stage = "admission_check"
            result = asyncio.run(asyncio.wait_for(verify_technical_owned(proof), timeout=180))
            safe_print({"phase":"technical_owned_db_check", **result})
            return
        if args.verify_supervisor_meaning_runtime_db:
            from scripts.cf023_supervisor_meaning_check import verify_meaning_runtime
            cf003_stage='admission_check'
            result=asyncio.run(asyncio.wait_for(verify_meaning_runtime(proof),timeout=180))
            safe_print({'phase':'supervisor_meaning_runtime_db_check',**result})
            return
        if args.verify_supervisor_accounting_db:
            from scripts.cf023_supervisor_meaning_check import verify_meaning_accounting
            cf003_stage='admission_check'
            result=asyncio.run(asyncio.wait_for(verify_meaning_accounting(proof),timeout=180))
            safe_print({'phase':'supervisor_accounting_db_check',**result})
            return
        if args.verify_flow_owned_report_read_db:
            from scripts.cf023_supervisor_meaning_check import _prepare_owned_flow_read_anchor
            cf003_stage = "admission_check"
            private_anchor = {}
            try:
                result = asyncio.run(asyncio.wait_for(_prepare_owned_flow_read_anchor(proof,private_anchor),timeout=min(120,flow_read_deadline-time.monotonic())))
                project = prepare_projects(_BACKEND.parent,backend_only=True)
                observed = verify_owned_report_backend_reads(project,proof,private_anchor,children,flow_read_deadline)
                safe_print({"phase":"flow_owned_report_read_db_check",**result,**observed,
                            "groups":result.get('groups',[])+observed.get('groups',[]),"whole_limit_seconds":300,"cleanup_reserve_seconds":30})
            finally:
                private_anchor.clear()
            return
        if args.verify_supervisor_meaning_flow_db:
            from scripts.cf023_supervisor_meaning_check import verify_meaning_flow_crosspath
            cf003_stage="admission_check"
            result=asyncio.run(asyncio.wait_for(verify_meaning_flow_crosspath(proof),timeout=120))
            safe_print({"phase":"supervisor_meaning_flow_db_check",**result})
            return
        if args.verify_supervisor_meaning_assembly_db:
            from scripts.cf023_supervisor_meaning_check import verify_meaning_assembly
            cf003_stage='admission_check'
            result=asyncio.run(asyncio.wait_for(verify_meaning_assembly(proof),timeout=120))
            safe_print({'phase':'supervisor_meaning_assembly_db_check',**result})
            return
        if args.verify_supervisor_meaning_db:
            from scripts.cf023_supervisor_meaning_check import verify_meaning
            cf003_stage='admission_check'
            result=asyncio.run(asyncio.wait_for(verify_meaning(proof),timeout=300))
            safe_print({'phase':'supervisor_meaning_db_check',**result})
            return
        if args.verify_supervisor_core_db:
            from scripts.cf022_supervisor_core_check import verify_core
            cf003_stage='admission_check'
            result=asyncio.run(asyncio.wait_for(verify_core(proof),timeout=240))
            safe_print({'phase':'supervisor_core_db_check',**result})
            return
        if args.verify_supervisor_flow_db:
            from scripts.cf020_supervisor_check import verify_supervisor
            cf003_stage='admission_check'
            result=asyncio.run(asyncio.wait_for(verify_supervisor(proof),timeout=180))
            safe_print({'phase':'supervisor_flow_db_check',**result})
            return
        if args.verify_flow_usage_db:
            from scripts.cf018_usage_check import verify_usage
            cf003_stage="admission_check"
            result=asyncio.run(asyncio.wait_for(verify_usage(proof),timeout=300))
            safe_print({"phase":"flow_usage_db_check",**result})
            return
        if args.verify_fundamental_analysis_db:
            from scripts.cf015_fundamental_check import verify_fundamental
            cf003_stage="admission_check"
            result=asyncio.run(asyncio.wait_for(verify_fundamental(proof),timeout=300))
            safe_print({"phase":"fundamental_analysis_db_check",**result})
            return
        if args.verify_analysis_adapter_db:
            from scripts.cf013_contract_check import verify_contract
            cf003_stage = "admission_check"
            result = asyncio.run(asyncio.wait_for(verify_contract(proof), timeout=120))
            safe_print({"phase":"analysis_adapter_db_check", **result})
            return
        if args.verify_flow_analysis_db:
            from scripts.cf012_analysis_check import verify_analysis
            cf003_stage = "admission_check"
            result = asyncio.run(asyncio.wait_for(verify_analysis(proof), timeout=240))
            safe_print({"phase":"flow_analysis_db_check", **result})
            return
        project = prepare_projects(_BACKEND.parent)
        # Secret-free recovery receipt; no DSN/password/Google inputs/tokens/subs.
        receipt = project.root / "resource_receipt.json"
        receipt.write_text(
            json.dumps(
                {"created_at": datetime.now(UTC).isoformat(), **proof.safe_receipt()}
            )
        )
        run_nonce = start_apps(
            project,
            proof,
            "fake" if args.verify_fake_environment else "approved-file",
            _BACKEND / ".env",
            args.lifetime_seconds,
            children,
            fail_after_backend=args.simulate_startup_failure,
        )
        receipt.write_text(
            json.dumps(
                {
                    **json.loads(receipt.read_text()),
                    "children": [
                        dict(
                            pid=child.pid, kind=child.kind, start_time=child.start_time
                        )
                        for child in children
                    ],
                }
            )
        )
        wait_readiness(run_nonce, children)
        safe_print(
            {
                "phase": "ready",
                "url": "http://localhost:3200",
                "scope": "openid",
                "input": "fake" if args.verify_fake_environment else "approved-file",
                "lifetime_seconds": args.lifetime_seconds,
            }
        )
        if args.verify_fake_environment:
            import httpx

            with httpx.Client(timeout=10, trust_env=False) as client:
                assert (
                    client.get("http://localhost:3200/api/auth/login").status_code
                    == 400
                )
                assert (
                    client.post(
                        "http://localhost:3200/api/supervisor/analyze"
                    ).status_code
                    == 403
                )
                assert (
                    client.post("http://localhost:3200/api/flow/reports").status_code
                    == 403
                )
            counts = asyncio.run(database_status(proof))
            if any(counts.values()):
                raise RuntimeError("Fake runtime probe did not rollback")
            safe_print(
                {
                    "phase": "fake_bootstrap",
                    "status": "passed",
                    "google_network": "blocked",
                    "private_inputs_read": 0,
                    "runtime_pool_internal_write_and_rollback": "passed",
                    "counts": counts,
                }
            )
            if args.hold_fake_seconds:
                safe_print({"phase": "fake_hold", "seconds": args.hold_fake_seconds})
                time.sleep(args.hold_fake_seconds)
            return
        from scripts.google_login_controller import ControllerError, LoginController

        controller = LoginController(proof)
        safe_print(
            {
                "instruction": "User: open the local URL and select your Google account yourself. Private commands: status, bind-A/B, seed-A/B, check-owner, delete-A/B, finish. No account automation."
            }
        )
        deadline = time.monotonic() + args.lifetime_seconds
        while time.monotonic() < deadline:
            readable, _, _ = select.select(
                [sys.stdin], [], [], min(2, max(0, deadline - time.monotonic()))
            )
            if readable:
                command = sys.stdin.readline().strip()
                if command == "finish" or command == "":
                    break
                if command == "status":
                    safe_print(
                        {
                            "phase": "status",
                            "counts": asyncio.run(database_status(proof)),
                        }
                    )
                elif command:
                    try:
                        result = asyncio.run(
                            asyncio.wait_for(controller.command(command), timeout=30)
                        )
                        safe_print({"phase": "private_controller", **result})
                    except ControllerError as exc:
                        safe_print(
                            {"phase": "private_controller_refused", "code": str(exc)}
                        )
                    except Exception:
                        # Keep the interactive environment and known fixture IDs.
                        # SQL exceptions can contain values; never print them.
                        safe_print(
                            {
                                "phase": "private_controller_failed",
                                "code": "internal_check_failed",
                            }
                        )
        safe_print(
            {
                "phase": "session_end",
                "counts": asyncio.run(database_status(proof)),
                "note": "Retained session rows during interactive validation are not batch rollback failures",
            }
        )
    except KeyboardInterrupt:
        interrupted = True
        safe_print({"phase": "interrupted", "status": "cleaning_owned_resources"})
    except Exception as error:
        if args.verify_supervisor_meaning_runtime_db or args.verify_supervisor_accounting_db or args.verify_technical_owned_read_db or args.verify_technical_admission_db or args.verify_technical_owned_db or args.verify_supervisor_meaning_assembly_db or args.verify_flow_owned_report_read_db or args.verify_supervisor_meaning_flow_db or args.verify_supervisor_meaning_db or args.verify_supervisor_core_db or args.verify_supervisor_flow_db or args.verify_flow_usage_db or args.verify_flow_analysis_db or args.verify_analysis_adapter_db or args.verify_fundamental_analysis_db:
            detail = cf003_failure_diagnostic(error, cf003_stage)
            detail["phase"] = "cf045_failure_diagnostic" if args.verify_supervisor_meaning_runtime_db else "cf044_failure_diagnostic" if args.verify_supervisor_accounting_db else "cf036_failure_diagnostic" if args.verify_technical_owned_read_db else "cf048_failure_diagnostic" if args.verify_technical_admission_db else "cf035_failure_diagnostic" if args.verify_technical_owned_db else "cf047_failure_diagnostic" if args.verify_flow_owned_report_read_db else "cf029_failure_diagnostic" if args.verify_supervisor_meaning_flow_db else "cf024_failure_diagnostic" if args.verify_supervisor_meaning_assembly_db else "cf023_failure_diagnostic" if args.verify_supervisor_meaning_db else "cf022_failure_diagnostic" if args.verify_supervisor_core_db else "cf020_failure_diagnostic" if args.verify_supervisor_flow_db else "cf018_failure_diagnostic" if args.verify_flow_usage_db else "cf015_failure_diagnostic" if args.verify_fundamental_analysis_db else "cf013_failure_diagnostic" if args.verify_analysis_adapter_db else "cf012_failure_diagnostic"
            if owner is not None:
                detail["metadata_failures"] = list(owner.metadata_failures)
            if owner is not None and owner.cleanup_receipt_path is not None:
                detail["cleanup_receipt_file"] = str(owner.cleanup_receipt_path)
            safe_print(detail)
        elif args.verify_flow_synthetic_demo_db:
            detail = cf003_failure_diagnostic(error, cf003_stage)
            detail["phase"] = "cf008_failure_diagnostic"
            safe_print(detail)
        elif args.verify_flow_fake_execution_db:
            detail = cf003_failure_diagnostic(error, cf003_stage)
            detail["phase"] = "cf007_failure_diagnostic"
            safe_print(detail)
        elif args.verify_flow_input_snapshot_db:
            if cf006_failure_owner is not None and cf006_failure_owner.receipt is not None:
                # Only the current failing resource; no nonce or helper receipt expansion.
                failed_receipt = cf006_failure_owner.receipt
                safe_print({"phase": "cf006_failed_resource", "resource_id": cf006_failure_owner.resource_id,
                            "container_id": failed_receipt.container_id, "created_at": failed_receipt.created_at})
            safe_print(cf006_failure_diagnostic(error, cf003_stage))
        elif args.verify_flow_admission_db:
            safe_print(cf003_failure_diagnostic(error, cf003_stage))
        if project:
            for directory in (project.backend, project.frontend):
                error_file = directory / "bootstrap_status.json"
                if error_file.exists():
                    data = json.loads(error_file.read_text())
                    safe_print(
                        {
                            "phase": "bootstrap_error",
                            "role": directory.name,
                            "error_type": data.get("error_type"),
                            "module": data.get("module"),
                            "frames": data.get("frames"),
                        }
                    )
        safe_print(
            {
                "phase": "failed",
                "status": "stopped_without_fallback",
                "resource_id": getattr(owner, "resource_id", None),
            }
        )
        raise SystemExit(1) from None
    finally:
        if args.verify_flow_owned_report_read_db:
            # Rearm only to the original absolute end, never give cleanup a new
            # relative 30s. The same alarm also interrupts a blocked cleanup call.
            signal.setitimer(signal.ITIMER_REAL, max(0.001,flow_read_whole_deadline-time.monotonic()))
        for signum in old_handlers:
            if not (args.verify_flow_owned_report_read_db and signum==signal.SIGALRM):
                signal.signal(signum, signal.SIG_IGN)
        def cleanup_budget():
            if args.verify_flow_owned_report_read_db and time.monotonic()>=flow_read_whole_deadline:
                raise TimeoutError("Owned report cleanup deadline exceeded")
        original_cleanup_call = None
        if args.verify_flow_owned_report_read_db and docker:
            original_cleanup_call = docker.call
            def cleanup_call(*values,**options):
                cleanup_budget()
                options['timeout']=min(options.get('timeout',15),flow_read_whole_deadline-time.monotonic())
                return original_cleanup_call(*values,**options)
            docker.call = cleanup_call
        cleanup_failed = secondary_cleanup_failed
        for child in reversed(children):
            try:
                cleanup_budget()
                child.cleanup()
            except BaseException:
                cleanup_failed = True
                safe_print(
                    {"phase": "cleanup_failed", "kind": child.kind, "pid": child.pid}
                )
        if owner:
            try:
                cleanup_budget()
                receipt_observed = owner.receipt is not None
                owner.cleanup()
                if (args.verify_supervisor_meaning_runtime_db or args.verify_supervisor_accounting_db or args.verify_technical_owned_read_db or args.verify_technical_admission_db or args.verify_technical_owned_db or args.verify_supervisor_meaning_assembly_db or args.verify_flow_owned_report_read_db or args.verify_supervisor_meaning_flow_db or args.verify_supervisor_meaning_db or args.verify_supervisor_core_db) and not receipt_observed:
                    cleanup_failed = True
                    safe_print({"phase": "owned_db_cleanup_unverified",
                                "reason": "creation_receipt_missing",
                                "resource_id": owner.resource_id})
                else:
                    safe_print({"phase": "owned_db_removed", "resource_id": owner.resource_id})
            except BaseException as error:
                cleanup_failed = True
                if args.verify_supervisor_meaning_runtime_db or args.verify_supervisor_accounting_db or args.verify_technical_owned_read_db or args.verify_technical_admission_db or args.verify_technical_owned_db or args.verify_supervisor_meaning_assembly_db or args.verify_flow_owned_report_read_db or args.verify_supervisor_meaning_flow_db or args.verify_supervisor_meaning_db or args.verify_supervisor_core_db or args.verify_supervisor_flow_db or args.verify_flow_usage_db or args.verify_flow_analysis_db or args.verify_analysis_adapter_db or args.verify_fundamental_analysis_db:
                    detail = cf003_failure_diagnostic(error, "cleanup")
                    detail["phase"] = "cf045_failure_diagnostic" if args.verify_supervisor_meaning_runtime_db else "cf044_failure_diagnostic" if args.verify_supervisor_accounting_db else "cf036_failure_diagnostic" if args.verify_technical_owned_read_db else "cf048_failure_diagnostic" if args.verify_technical_admission_db else "cf035_failure_diagnostic" if args.verify_technical_owned_db else "cf047_failure_diagnostic" if args.verify_flow_owned_report_read_db else "cf029_failure_diagnostic" if args.verify_supervisor_meaning_flow_db else "cf024_failure_diagnostic" if args.verify_supervisor_meaning_assembly_db else "cf023_failure_diagnostic" if args.verify_supervisor_meaning_db else "cf022_failure_diagnostic" if args.verify_supervisor_core_db else "cf020_failure_diagnostic" if args.verify_supervisor_flow_db else "cf018_failure_diagnostic" if args.verify_flow_usage_db else "cf015_failure_diagnostic" if args.verify_fundamental_analysis_db else "cf013_failure_diagnostic" if args.verify_analysis_adapter_db else "cf012_failure_diagnostic"
                    detail["metadata_failures"] = list(owner.metadata_failures)
                    if owner.cleanup_receipt_path is not None:
                        detail["cleanup_receipt_file"] = str(owner.cleanup_receipt_path)
                    safe_print(detail)
                elif args.verify_flow_synthetic_demo_db:
                    detail = cf003_failure_diagnostic(error, "cleanup")
                    detail["phase"] = "cf008_failure_diagnostic"
                    safe_print(detail)
                elif args.verify_flow_fake_execution_db:
                    detail = cf003_failure_diagnostic(error, "cleanup")
                    detail["phase"] = "cf007_failure_diagnostic"
                    safe_print(detail)
                elif args.verify_flow_input_snapshot_db:
                    safe_print(cf006_failure_diagnostic(error, "cleanup"))
                elif args.verify_flow_admission_db:
                    safe_print(cf003_failure_diagnostic(error, "cleanup"))
                safe_print(
                    {
                        "phase": "cleanup_failed",
                        "resource_id": owner.resource_id,
                        "container_id": getattr(
                            getattr(owner, "receipt", None), "container_id", None
                        ),
                    }
                )
        if project and not cleanup_failed:
            try:
                cleanup_budget()
                project.cleanup()
                safe_print({"phase": "owned_workspace_removed"})
            except BaseException:
                cleanup_failed = True
                safe_print({"phase": "workspace_cleanup_failed"})
        if docker:
            if original_cleanup_call is not None:
                docker.call = original_cleanup_call
            db_test_context.close()
            docker.close()
        if args.verify_flow_owned_report_read_db:
            signal.setitimer(signal.ITIMER_REAL, 0)
        for signum, handler in old_handlers.items():
            signal.signal(signum, handler)
        if cleanup_failed:
            raise SystemExit(2)
    if interrupted:
        raise SystemExit(130)


if __name__ == "__main__":
    main()
