"""Synthetic project trees, fake socket probes, no private env/application/DB/Google."""

import io
from pathlib import Path
import shutil
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scripts.google_login_workspace import (
    LoginPreparationError,
    child_base_environment,
    ensure_local_ports_free,
    prepare_projects,
)


@pytest.fixture
def fake_project(tmp_path):
    repo = tmp_path / "repo"
    files = {
        "backend/src/shared/config.py": "# synthetic configuration source\ns = Settings()\n",
        "backend/db/migrations/env.py": "# synthetic migration source\n",
        "backend/alembic.ini": "[alembic]\n",
        "backend/.env": "GOOGLE_CLIENT_SECRET=FAKE_PRIVATE_NEVER_READ\n",
        "backend/src/.env.private": "FAKE_UNRELATED=never-read\n",
        "frontend/.env": "FAKE_PRIVATE=never-read\n",
        "frontend/src/app/page.tsx": "export default function Page() {return null}\n",
        "frontend/next.config.ts": 'import type {NextConfig} from "next";\nconst nextConfig: NextConfig = {\n};\nexport default nextConfig;\n',
        "frontend/package.json": '{"name":"fake"}',
    }
    for name, content in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    (repo / "frontend/node_modules").mkdir()
    (repo / "frontend/node_modules/marker.txt").write_text("fake dependency, preserve")
    return repo


def test_copy_does_not_open_env_and_cleanup_preserves_original_and_dependencies(
    fake_project, monkeypatch
):
    original = io.open

    def deny_private(file, *args, **kwargs):
        if isinstance(file, (str, Path)) and Path(file).name.startswith(".env"):
            raise AssertionError("Private env must not be opened/copied")
        return original(file, *args, **kwargs)

    monkeypatch.setattr(io, "open", deny_private)
    prepared = prepare_projects(fake_project)
    assert not (prepared.backend / ".env").exists()
    assert not (prepared.backend / "src/.env.private").exists()
    assert not (prepared.frontend / ".env").exists()
    assert not (prepared.backend / "src").is_symlink()
    assert (prepared.frontend / "node_modules").is_symlink()
    assert "turbopack:" in (prepared.frontend / "next.config.ts").read_text()
    assert "turbopack:" not in (fake_project / "frontend/next.config.ts").read_text()
    prepared.cleanup()
    prepared.cleanup()
    assert not prepared.root.exists()
    assert (fake_project / "frontend/node_modules/marker.txt").is_file()
    assert (fake_project / "backend/src/shared/config.py").is_file()


@pytest.mark.parametrize(
    "damage", ["symlink", "credential", "missing_config", "unknown_config"]
)
def test_unsafe_copy_fails_and_removes_only_its_workspace(fake_project, damage):
    if damage == "symlink":
        (fake_project / "backend/src/alias.py").symlink_to(
            fake_project / "backend/.env"
        )
    if damage == "credential":
        (fake_project / "frontend/src/credentials.json").write_text(
            "fake credential material"
        )
    if damage == "missing_config":
        (fake_project / "backend/src/shared/config.py").unlink()
    if damage == "unknown_config":
        (fake_project / "frontend/next.config.ts").write_text("unexpected fake config")
    before = set(fake_project.parent.iterdir())
    with pytest.raises(LoginPreparationError):
        prepare_projects(fake_project)
    assert set(fake_project.parent.iterdir()) == before
    assert fake_project.is_dir()


def test_parent_application_environment_is_not_inherited(monkeypatch):
    for key in [
        "GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET",
        "DATABASE_URL",
        "NODE_OPTIONS",
        "BACKEND_URL",
        "PYTHONPATH",
    ]:
        monkeypatch.setenv(key, "FAKE_PARENT_MUST_NOT_INHERIT")
    env = child_base_environment()
    assert set(env) == {
        "PATH",
        "LANG",
        "TZ",
        "NEXT_TELEMETRY_DISABLED",
        "PYTHONNOUSERSITE",
    }
    assert "FAKE_PARENT_MUST_NOT_INHERIT" not in repr(env)


def test_port_conflict_closes_own_probes_and_never_terminates_existing_process():
    handles = []

    def socket_factory(*args):
        handle = SimpleNamespace(close=Mock(), bind=Mock())
        if len(handles) == 2:
            handle.bind.side_effect = OSError("fake occupied")
        handles.append(handle)
        return handle

    with pytest.raises(LoginPreparationError, match="port is unavailable"):
        ensure_local_ports_free(socket_factory=socket_factory)
    assert all(handle.close.call_count == 1 for handle in handles)


def test_port_success_closes_all_probes():
    handles = []

    def socket_factory(*args):
        handle = SimpleNamespace(close=Mock(), bind=Mock())
        handles.append(handle)
        return handle

    ensure_local_ports_free(socket_factory=socket_factory)
    assert len(handles) == 4 and all(handle.close.call_count == 1 for handle in handles)


def test_cleanup_refuses_replaced_root(fake_project):
    prepared = prepare_projects(fake_project)
    moved = prepared.root.with_name(prepared.root.name + "-original")
    prepared.root.rename(moved)
    prepared.root.mkdir()
    marker = prepared.root / "unrelated.txt"
    marker.write_text("do not remove")
    try:
        with pytest.raises(LoginPreparationError, match="unowned"):
            prepared.cleanup()
        assert marker.exists()
    finally:
        marker.unlink()
        prepared.root.rmdir()
        shutil.rmtree(moved)


@pytest.mark.parametrize(
    "name",
    [
        "server.key",
        "private.pem",
        "database.sql",
        "session.log",
        "credentials.backup.json",
    ],
)
@pytest.mark.parametrize("location", ["backend/src", "frontend/src", "frontend/public"])
def test_explicit_copy_allowlist_never_reads_or_copies_private_material(
    fake_project, monkeypatch, name, location
):
    import scripts.google_login_workspace as module

    target = fake_project / location / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("FAKE_PRIVATE_MATERIAL_MUST_NOT_COPY")
    copied = []
    original = module.shutil.copyfile

    def record(source, destination):
        assert Path(source) != target
        copied.append(Path(source).name)
        return original(source, destination)

    monkeypatch.setattr(module.shutil, "copyfile", record)
    with pytest.raises(LoginPreparationError):
        prepare_projects(fake_project)
    assert name not in copied
