"""Fake DTOs/processes/private pipes/HTTP only, never real input, Docker or Google."""

import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scripts import cf002_interactive_login as runner
from scripts import google_login_bootstrap as bootstrap


def target_dto():
    return dict(
        database="cf002_db_0123456789ab",
        username="cf002_role_0123456789ab",
        resource_id="a" * 64,
        server_port=5432,
        host="127.0.0.1",
        port=6550,
        password="FAKE_LIMITED_PASSWORD",
    )


def fake_proof():
    data = target_dto()
    return SimpleNamespace(
        database=data["database"],
        username=data["username"],
        resource_id=data["resource_id"],
        server_port=5432,
        verify_ownership=Mock(),
        connection_parameters=lambda: dict(
            host=data["host"],
            port=data["port"],
            user=data["username"],
            database=data["database"],
            password=data["password"],
        ),
        _owner=SimpleNamespace(
            admin="FAKE_ADMIN", _admin_password="FAKE_ADMIN_PASSWORD", sql=Mock()
        ),
    )


def test_runtime_dto_contains_only_restricted_connection_and_identity():
    data = runner.runtime_database_dto(fake_proof())
    assert set(data) == set(target_dto())
    assert "FAKE_ADMIN" not in json.dumps(data)
    assert "owner" not in data and "sql" not in data
    runtime = bootstrap.RuntimeDatabase.from_dto(data)
    assert "FAKE_LIMITED_PASSWORD" not in repr(runtime)
    with pytest.raises(RuntimeError):
        bootstrap.RuntimeDatabase.from_dto({**data, "admin": "forbidden"})


def test_frontend_dto_rejects_database_and_google_fields():
    shared = dict(project_root="/fake", run_nonce="f" * 64, lifetime_seconds=30)
    bootstrap.validate_configuration(shared, "frontend")
    for key in ["database", "google_mode", "google_source", "GOOGLE_CLIENT_SECRET"]:
        with pytest.raises(RuntimeError):
            bootstrap.validate_configuration({**shared, key: "fake"}, "frontend")


def project(tmp_path):
    backend, frontend = tmp_path / "backend", tmp_path / "frontend"
    backend.mkdir()
    frontend.mkdir()
    (frontend / "next.config.ts").write_text("const nextConfig: NextConfig = {\n};\n")
    return SimpleNamespace(backend=backend, frontend=frontend)


def test_fresh_exec_dtos_no_admin_or_google_secrets_in_parent_env_argv_or_next(
    tmp_path, monkeypatch
):
    import shutil

    monkeypatch.setattr(
        shutil, "copyfile", lambda src, dst: Path(dst).write_text("# fake helper")
    )
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "FAKE_PARENT_GOOGLE_SECRET")
    records = []
    readers = []
    life_readers = []

    def spawn(args, **kwargs):
        assert kwargs["start_new_session"] is True
        records.append((args, kwargs))
        readers.append(os.dup(kwargs["pass_fds"][0]))
        life_readers.append(os.dup(kwargs["pass_fds"][1]))
        return SimpleNamespace(pid=10000 + len(records), wait=Mock())

    monkeypatch.setattr(runner.subprocess, "Popen", spawn)
    monkeypatch.setattr(runner.ChildProcess, "_start_time", lambda self: "fake-start")
    monkeypatch.setattr(runner.ChildProcess, "_pgid", lambda self: self.pid)
    children = []
    try:
        nonce = runner.start_apps(
            project(tmp_path),
            fake_proof(),
            "approved-file",
            Path("/fake/approved-input"),
            30,
            children,
        )
        data = [json.loads(os.read(fd, 32768)) for fd in readers]
        assert len(children) == 2 and all(
            child.start_time == "fake-start" for child in children
        )
        assert data[0]["database"] == target_dto()
        assert set(data[1]) == {"project_root", "run_nonce", "lifetime_seconds"}
        assert all(item["run_nonce"] == nonce for item in data)
        encoded = json.dumps(data)
        assert (
            "FAKE_ADMIN" not in encoded and "FAKE_PARENT_GOOGLE_SECRET" not in encoded
        )
        for args, kwargs in records:
            assert "--config-fd" in args and "--life-fd" in args
            assert set(kwargs["env"]) == set(runner.child_base_environment())
            assert "FAKE_LIMITED_PASSWORD" not in repr(args) + repr(kwargs["env"])
    finally:
        for child in children:
            for name in ("life_write", "config_write"):
                value = getattr(child, name, None)
                if value is not None:
                    try:
                        os.close(value)
                    except OSError:
                        pass
        for fd in readers + life_readers:
            os.close(fd)


def test_raw_spawn_receipt_registered_before_identity_validation_or_signal(
    tmp_path, monkeypatch
):
    import shutil

    monkeypatch.setattr(
        shutil, "copyfile", lambda src, dst: Path(dst).write_text("# fake helper")
    )
    readers = []
    children = []

    def spawn(args, **kwargs):
        readers.extend(os.dup(fd) for fd in kwargs["pass_fds"])
        return SimpleNamespace(pid=10001, wait=Mock())

    def interrupted(self):
        assert children and children[0] is self and self.pid == 10001
        raise KeyboardInterrupt

    monkeypatch.setattr(runner.subprocess, "Popen", spawn)
    monkeypatch.setattr(runner.ChildProcess, "_start_time", interrupted)
    cleanup = Mock()
    monkeypatch.setattr(runner.ChildProcess, "cleanup", cleanup)
    try:
        with pytest.raises(KeyboardInterrupt):
            runner.start_apps(
                project(tmp_path), fake_proof(), "fake", Path("/fake"), 30, children
            )
        assert len(children) == 1
        cleanup.assert_called_once()
    finally:
        for child in children:
            for name in ("life_write", "config_write"):
                value = getattr(child, name, None)
                if value is not None:
                    try:
                        os.close(value)
                    except OSError:
                        pass
        for fd in readers:
            os.close(fd)


@pytest.mark.parametrize("failure", ["other_app", "dead_child", "nonce", "bind_race"])
def test_readiness_rejects_non_owned_responses_and_bind_races(monkeypatch, failure):
    children = [
        SimpleNamespace(kind="backend", pid=1),
        SimpleNamespace(kind="frontend", pid=2),
    ]
    alive = Mock(return_value=failure != "dead_child")
    binding = Mock(return_value=failure != "other_app")
    if failure == "bind_race":
        binding.side_effect = [True, True, False]
    monkeypatch.setattr(runner, "_child_is_alive", alive)
    monkeypatch.setattr(runner, "_application_owns_port", binding)
    calls = []

    class Client:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, url):
            calls.append(url)
            return SimpleNamespace(
                status_code=401 if url.endswith("/session") else 200,
                headers={"x-cf002-run": "wrong" if failure == "nonce" else "r" * 64},
            )

    with pytest.raises(RuntimeError):
        runner.wait_readiness(
            "r" * 64,
            children,
            timeout_seconds=0.001,
            client_factory=lambda **kwargs: Client(),
        )
    if failure in {"other_app", "dead_child"}:
        assert not calls


@pytest.mark.parametrize("cause", ["expiry", "parent_eof"])
def test_child_own_lifetime_and_parent_death_are_bounded(monkeypatch, cause):
    clocks = [0, 31] if cause == "expiry" else [0, 0, 0]
    monkeypatch.setattr(bootstrap.time, "monotonic", Mock(side_effect=clocks))
    monkeypatch.setattr(bootstrap.time, "sleep", Mock())
    monkeypatch.setattr(bootstrap.select, "select", lambda *args: ([123], [], []))
    monkeypatch.setattr(bootstrap.os, "read", lambda *args: b"")
    kill = Mock()
    terminate = Mock()
    monkeypatch.setattr(bootstrap.os, "kill", kill)
    monkeypatch.setattr(bootstrap.os, "_exit", terminate)
    monkeypatch.setattr(
        bootstrap.threading,
        "Thread",
        lambda target, daemon: SimpleNamespace(start=target),
    )
    bootstrap.start_watchdog(123, 30)
    kill.assert_called_once_with(os.getpid(), bootstrap.signal.SIGTERM)
    terminate.assert_called_once_with(124)


@pytest.mark.parametrize("mismatch", ["role", "nonce", "database", "privilege"])
async def test_runtime_native_mismatch_stops_in_readonly_before_write(
    monkeypatch, mismatch
):
    import sys
    from contextlib import asynccontextmanager
    from unittest.mock import AsyncMock
    from tests import db_safety

    monkeypatch.setitem(sys.modules, "runtime_db_guard", db_safety)
    target = bootstrap.RuntimeDatabase.from_dto(target_dto())
    row = {
        "database": target.database,
        "username": target.username,
        "resource_id": target.resource_id,
        "server_port": 5432,
        "privileged": False,
    }
    column = {
        "role": "username",
        "nonce": "resource_id",
        "database": "database",
        "privilege": "privileged",
    }[mismatch]
    row[column] = True if mismatch == "privilege" else "wrong"

    @asynccontextmanager
    async def transaction(**kwargs):
        assert kwargs == {"readonly": True}
        yield

    native = SimpleNamespace(
        transaction=transaction,
        fetchrow=AsyncMock(return_value=row),
        execute=AsyncMock(),
    )
    with pytest.raises(RuntimeError, match="verification failed"):
        await bootstrap.attest_runtime_native(native, target)
    query = native.fetchrow.await_args.args[0]
    assert all(
        flag in query
        for flag in ["rolinherit", "rolreplication", "rolbypassrls", "rolcanlogin"]
    )
    native.execute.assert_not_awaited()
