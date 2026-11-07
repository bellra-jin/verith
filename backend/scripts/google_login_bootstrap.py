"""Fresh exec child: receives only role-specific DTOs over private anonymous pipes.

No parent/admin owner/Docker object is inherited. Only Backend reads the approved
Google keys. Next receives neither Google fields nor any DB configuration.
"""

from __future__ import annotations
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
import argparse
import json
import os
import re
from pathlib import Path
import select
import signal
import subprocess
import sys
import threading
import time


@dataclass(frozen=True)
class RuntimeDatabase:
    database: str
    username: str
    resource_id: str = field(repr=False)
    server_port: int
    host: str
    port: int
    password: str = field(repr=False)

    @classmethod
    def from_dto(cls, data):
        fields = {
            "database",
            "username",
            "resource_id",
            "server_port",
            "host",
            "port",
            "password",
        }
        if (
            not isinstance(data, dict)
            or set(data) != fields
            or data["host"] != "127.0.0.1"
            or data["server_port"] != 5432
            or type(data["port"]) is not int
            or not 1024 < data["port"] < 65536
            or data["port"] in {5432, 5433, 15432}
        ):
            raise RuntimeError("Invalid runtime target")
        if any(
            not isinstance(data[k], str) or not data[k]
            for k in ["database", "username", "resource_id", "password"]
        ):
            raise RuntimeError("Invalid runtime target")
        if (
            re.fullmatch(r"cf002_role_[0-9a-f]{12}", data["username"]) is None
            or data["database"]
            != "cf002_db_" + data["username"].removeprefix("cf002_role_")
            or re.fullmatch(r"[0-9a-f]{64}", data["resource_id"]) is None
        ):
            raise RuntimeError("Invalid runtime target")
        return cls(**data)

    def connection_parameters(self):
        return dict(
            host=self.host,
            port=self.port,
            database=self.database,
            user=self.username,
            password=self.password,
        )

    @property
    def url(self):
        from sqlalchemy.engine import URL

        return URL.create(
            "postgresql+asyncpg",
            username=self.username,
            password=self.password,
            host=self.host,
            port=self.port,
            database=self.database,
        ).render_as_string(hide_password=False)


async def runtime_write_probe(engine):
    from uuid import uuid4
    from sqlalchemy.ext.asyncio import AsyncSession
    from db.models.auth.models import AuthUser
    from src.api.services.auth_service import issue_session
    from src.api.services.flow_report_service import FlowReportService
    from src.api.schemas.flow_report import FlowReportSaveRequest

    async with engine.connect() as connection:
        outer = await connection.begin()
        try:
            async with AsyncSession(
                bind=connection,
                join_transaction_mode="create_savepoint",
                expire_on_commit=False,
            ) as session:
                user = AuthUser(id=uuid4())
                session.add(user)
                await session.flush()
                _, principal = await issue_session(session, user)
                payload = json.loads(
                    (Path.cwd() / "runtime_fixture_payload.json").read_text()
                )
                payload["meta"]["ticker"] = "999988"
                service = FlowReportService(session, principal=principal)
                saved = await service.save_report(
                    FlowReportSaveRequest(
                        payload=payload, question="runtime pool synthetic probe"
                    )
                )
                assert (await service.get_report(saved.report_id)).report == payload
                assert await service.delete_report(saved.report_id)
        finally:
            await outer.rollback()


def start_watchdog(life_fd, seconds):
    if type(seconds) is not int or not 30 <= seconds <= 7200:
        raise RuntimeError("Finite runtime required")

    def watch():
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            readable, _, _ = select.select(
                [life_fd], [], [], min(0.5, max(0, deadline - time.monotonic()))
            )
            if readable and not os.read(life_fd, 1):
                break
        try:
            os.kill(os.getpid(), signal.SIGTERM)
        except ProcessLookupError:
            return
        time.sleep(5)
        os._exit(124)

    threading.Thread(target=watch, daemon=True).start()


def validate_configuration(config, role):
    shared = {"project_root", "run_nonce", "lifetime_seconds"}
    allowed = shared | (
        {"database", "google_mode", "google_source"} if role == "backend" else set()
    )
    if (
        not isinstance(config, dict)
        or set(config) != allowed
        or not isinstance(config["run_nonce"], str)
        or len(config["run_nonce"]) != 64
    ):
        raise RuntimeError("Invalid private bootstrap input")
    if role == "backend":
        RuntimeDatabase.from_dto(config["database"])


async def attest_runtime_native(native, target):
    from runtime_db_guard import identity_query, _identity_matches

    async with native.transaction(readonly=True):
        row = await native.fetchrow(identity_query(True))
        if not _identity_matches(row, target):
            raise RuntimeError("Runtime connection verification failed")


def bootstrap_backend(config):
    root = Path(config["project_root"]).resolve()
    os.chdir(root)
    sys.path.insert(0, str(root))
    from google_login_workspace import child_base_environment
    from google_login_inputs import GoogleInputs, read_google_inputs

    target = RuntimeDatabase.from_dto(config["database"])
    import asyncio
    from runtime_db_guard import attest_database

    # Verify the restricted native connection before opening even approved inputs.
    asyncio.run(attest_database(target, all_restrictions=True))
    environment = child_base_environment()
    environment.update(
        DATABASE_URL=target.url,
        AUTH_REDIRECT_URI="http://localhost:3200/api/auth/callback",
        AUTH_ORIGINS="http://localhost:3200",
        CORS_ORIGINS="http://localhost:3200",
        AUTH_ALLOW_LOCAL_HTTP="true",
        ENABLE_NEWS_GRAPH="false",
        AUTH_SESSION_TTL_SECONDS="3600",
    )
    if config["google_mode"] == "approved-file":
        credentials = read_google_inputs(Path(config["google_source"]))
    elif config["google_mode"] == "fake":
        credentials = GoogleInputs(
            "fake.apps.googleusercontent.com", "fake-only-not-a-real-secret"
        )
    else:
        raise RuntimeError("Unsupported input mode")
    environment.update(credentials.backend_environment())
    os.environ.clear()
    os.environ.update(environment)
    from src.api.config import settings
    from src.api.auth.google import GoogleConfig

    GoogleConfig(
        settings.GOOGLE_CLIENT_ID,
        settings.GOOGLE_CLIENT_SECRET,
        settings.AUTH_REDIRECT_URI,
        (settings.AUTH_ORIGINS,),
        True,
    ).validate()
    from sqlalchemy import event
    from sqlalchemy.ext.asyncio import create_async_engine
    from runtime_db_guard import attest_engine_connection

    engine = create_async_engine(
        target.url, connect_args=target.connection_parameters(), pool_pre_ping=True
    )

    @event.listens_for(engine.sync_engine, "connect")
    def attest_new_connection(dbapi_connection, connection_record):
        dbapi_connection.run_async(lambda native: attest_runtime_native(native, target))

    import db.session as sessions

    sessions.get_engine = lambda: engine
    sessions.get_session_factory.cache_clear()
    from src.api.main import app

    if config["google_mode"] == "fake":
        from src.api.routes import auth
        from src.api.auth.google import GoogleOIDC
        import httpx

        def deny_google(request):
            raise RuntimeError("External requests forbidden in fake bootstrap")

        original = auth.get_oidc()
        fake = GoogleOIDC(original.config, transport=httpx.MockTransport(deny_google))
        auth.get_oidc = lambda: fake

    @app.middleware("http")
    async def run_identity(request, call_next):
        response = await call_next(request)
        response.headers["X-CF002-Run"] = config["run_nonce"]
        return response

    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application):
        try:
            async with engine.connect() as connection:
                await attest_engine_connection(
                    connection, target, all_restrictions=True
                )
            if config["google_mode"] == "fake":
                await runtime_write_probe(engine)
            async with original_lifespan(application):
                yield
        finally:
            await engine.dispose()

    app.router.lifespan_context = lifespan
    import uvicorn

    uvicorn.run(
        app, host="localhost", port=8200, access_log=False, log_level="critical"
    )


def bootstrap_frontend(config):
    from google_login_workspace import child_base_environment

    root = Path(config["project_root"]).resolve()
    environment = {**child_base_environment(), "BACKEND_URL": "http://localhost:8200"}
    stopping = threading.Event()
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *args: stopping.set())
    child = subprocess.Popen(
        [
            "node",
            str(root / "node_modules/next/dist/bin/next"),
            "dev",
            "--hostname",
            "localhost",
            "--port",
            "3200",
        ],
        cwd=root,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        while not stopping.wait(0.2):
            if child.poll() is not None:
                return
    finally:
        # This exec child is the leader of a private group including its Node workers.
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        try:
            os.killpg(os.getpgrp(), signal.SIGTERM)
        except ProcessLookupError:
            pass
        time.sleep(0.4)
        os.killpg(os.getpgrp(), signal.SIGKILL)


def main():
    signal.pthread_sigmask(signal.SIG_UNBLOCK, {signal.SIGINT, signal.SIGTERM})
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", choices=["backend", "frontend"], required=True)
    parser.add_argument("--config-fd", type=int, required=True)
    parser.add_argument("--life-fd", type=int, required=True)
    args = parser.parse_args()
    config = None
    try:
        with os.fdopen(args.config_fd, encoding="utf-8") as stream:
            raw = stream.read(32769)
        if len(raw) > 32768:
            raise RuntimeError("Oversize private bootstrap input")
        config = json.loads(raw)
        validate_configuration(config, args.role)
        start_watchdog(args.life_fd, config["lifetime_seconds"])
        if args.role == "backend":
            bootstrap_backend(config)
        else:
            bootstrap_frontend(config)
    except BaseException as exc:
        # Error class and stack function/line only; never messages, inputs or locals.
        if config is not None:
            try:
                import traceback

                module = getattr(exc, "name", None)
                if (
                    not isinstance(module, str)
                    or re.fullmatch(r"[A-Za-z0-9_.]+", module) is None
                ):
                    module = None
                safe = {
                    "error_type": type(exc).__name__,
                    "module": module,
                    "frames": [
                        {"function": frame.name, "line": frame.lineno}
                        for frame in traceback.extract_tb(exc.__traceback__)
                    ],
                }
                (Path(config["project_root"]) / "bootstrap_status.json").write_text(
                    json.dumps(safe)
                )
            except BaseException:
                pass
        os._exit(1)


if __name__ == "__main__":
    main()
