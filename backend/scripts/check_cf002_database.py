"""Explicitly approved disposable-only CF-002 DB verification.

No app DB connection, named volume, .env edit, downloaded image, or durable secret.
The flag acknowledges a separately granted approval; it does not grant permission.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
from uuid import uuid4

from dotenv import dotenv_values
from sqlalchemy.engine import make_url

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from tests.db_safety import preflight_database  # noqa: E402


def docker(*args: str, input_text: str | None = None, env=None) -> str:
    result = subprocess.run(
        ["docker", *args], input=input_text, text=True, capture_output=True, env=env
    )
    if result.returncode:
        # Never include role password SQL, connection URLs, or container env in errors.
        raise RuntimeError(f"Disposable Docker operation failed: {args[0]}")
    return result.stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approved-disposable", action="store_true", required=True)
    parser.parse_args()
    app_url = os.getenv("DATABASE_URL") or dotenv_values(_BACKEND / ".env").get(
        "DATABASE_URL"
    )
    if not app_url:
        raise RuntimeError("App target identification is required; no resource created")
    suffix = uuid4().hex[:12]
    name = f"verith-cf002-test-{suffix}"
    resource_id = f"CF-002-{suffix}"
    admin, role, database = (
        f"cf002_admin_{suffix}",
        f"cf002_role_{suffix}",
        f"cf002_db_{suffix}",
    )
    password, admin_password = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    container_id = None
    try:
        container_env = {**os.environ, "POSTGRES_PASSWORD": admin_password}
        container_id = docker(
            "run",
            "--detach",
            "--rm",
            "--pull=never",
            "--name",
            name,
            "--label",
            "verith.task=CF-002",
            "--label",
            f"verith.resource_id={resource_id}",
            "--read-only",
            "--memory",
            "512m",
            "--cpus",
            "1",
            "--tmpfs",
            "/var/lib/postgresql/data:rw",
            "--tmpfs",
            "/var/run/postgresql:rw",
            "--tmpfs",
            "/tmp:rw",
            "--publish",
            "127.0.0.1::5432",
            "--env",
            f"POSTGRES_USER={admin}",
            "--env",
            f"POSTGRES_DB={database}",
            "--env",
            "POSTGRES_PASSWORD",
            "--env",
            "POSTGRES_HOST_AUTH_METHOD=scram-sha-256",
            "pgvector/pgvector:pg16",
            "postgres",
            "-c",
            f"verith.test_resource_id={resource_id}",
            env=container_env,
        )
        info = json.loads(docker("inspect", name))[0]
        assert info["Id"] == container_id and info["Mounts"] == []
        assert info["HostConfig"]["ReadonlyRootfs"] is True
        assert set(info["HostConfig"]["Tmpfs"]) == {
            "/var/lib/postgresql/data",
            "/var/run/postgresql",
            "/tmp",
        }
        assert info["Config"]["Labels"]["verith.resource_id"] == resource_id
        (binding,) = info["NetworkSettings"]["Ports"]["5432/tcp"]
        assert binding["HostIp"] == "127.0.0.1"
        port = int(binding["HostPort"])
        for _ in range(40):
            ready = subprocess.run(
                [
                    "docker",
                    "exec",
                    name,
                    "pg_isready",
                    "-h",
                    "127.0.0.1",
                    "-U",
                    admin,
                    "-d",
                    database,
                ],
                capture_output=True,
            )
            if ready.returncode == 0:
                break
            time.sleep(0.25)
        else:
            raise RuntimeError("Disposable PostgreSQL did not become ready")

        # Environment provisioning only, inside the newly inspected container.
        # Read the server identity before creating the temporary limited test role.
        identity = docker(
            "exec",
            name,
            "psql",
            "-U",
            admin,
            "-d",
            database,
            "-Atc",
            "SELECT current_database() || '|' || current_setting('verith.test_resource_id');",
        )
        assert identity == f"{database}|{resource_id}"
        docker(
            "exec",
            "-i",
            name,
            "psql",
            "-U",
            admin,
            "-d",
            database,
            "-v",
            "ON_ERROR_STOP=1",
            input_text=f"CREATE ROLE {role} LOGIN PASSWORD '{password}' NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;\n"
            f"REVOKE CONNECT ON DATABASE postgres FROM PUBLIC;\n"
            f"REVOKE CONNECT ON DATABASE template1 FROM PUBLIC;\n"
            f"GRANT CONNECT, TEMPORARY, CREATE ON DATABASE {database} TO {role};\n"
            f"GRANT USAGE, CREATE ON SCHEMA public TO {role};\n",
        )
        target = make_url(
            f"postgresql+asyncpg://{role}@127.0.0.1:{port}/{database}"
        ).set(password=password)
        manifest = {
            "resource_id": resource_id,
            "host": "127.0.0.1",
            "port": port,
            "server_port": 5432,
            "database": database,
            "username": role,
            "cleanup_owner": "CF-002 delegated disposable test runner",
            "disposable": True,
        }
        environ = {
            **os.environ,
            "DATABASE_URL": app_url,
            "TEST_DATABASE_URL": target.render_as_string(hide_password=False),
            "TEST_DATABASE_APPROVAL": json.dumps(manifest),
            "ENABLE_NEWS_GRAPH": "false",
        }
        asyncio.run(preflight_database(environ, app_url))
        print(
            json.dumps(
                {
                    "resource_id": resource_id,
                    "container_id": container_id,
                    "host": "127.0.0.1",
                    "port": port,
                    "database": database,
                    "role": role,
                    "persistent_mounts": 0,
                    "readonly_preflight": "passed",
                }
            ),
            flush=True,
        )

        # Extensions require the temporary bootstrap admin. Only after preflight;
        # migrations and tests themselves use the limited role above.
        docker(
            "exec",
            "-i",
            name,
            "psql",
            "-U",
            admin,
            "-d",
            database,
            "-v",
            "ON_ERROR_STOP=1",
            input_text="CREATE EXTENSION IF NOT EXISTS pgcrypto;\nCREATE EXTENSION IF NOT EXISTS vector;\n",
        )
        subprocess.run(
            [sys.executable, "scripts/cf002_migration_check.py"],
            cwd=_BACKEND,
            env=environ,
            check=True,
        )
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "--confcutdir=tests/flow_integration",
                "tests/flow_integration",
                "-q",
                "--maxfail=1",
            ],
            cwd=_BACKEND,
            env=environ,
            check=True,
        )
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/test_seed_stocks.py",
                "-q",
                "--maxfail=1",
            ],
            cwd=_BACKEND,
            env=environ,
            check=True,
        )
        subprocess.run(
            [sys.executable, "scripts/cf002_concurrency_check.py"],
            cwd=_BACKEND,
            env=environ,
            check=True,
        )
        counts = docker(
            "exec",
            name,
            "psql",
            "-U",
            admin,
            "-d",
            database,
            "-Atc",
            """
            SELECT json_build_object('stocks', (SELECT count(*) FROM stocks),
                'reports', (SELECT count(*) FROM flow_reports),
                'interpretations', (SELECT count(*) FROM flow_report_interpretations),
                'verifications', (SELECT count(*) FROM flow_report_verifications),
                'indexes', (SELECT count(*) FROM agent_reports),
                'users', (SELECT count(*) FROM auth_users),
                'identities', (SELECT count(*) FROM auth_identities),
                'sessions', (SELECT count(*) FROM auth_sessions));
        """,
        )
        assert all(count == 0 for count in json.loads(counts).values())
        print("Residual rows after rollback: " + counts, flush=True)
    finally:
        if container_id:
            info = json.loads(docker("inspect", container_id))[0]
            assert (
                info["Config"]["Labels"]["verith.resource_id"] == resource_id
                and info["Mounts"] == []
            )
            docker("stop", "--time", "5", container_id)
            gone = (
                subprocess.run(
                    ["docker", "inspect", container_id], capture_output=True
                ).returncode
                != 0
            )
            assert gone, "Disposable container cleanup not confirmed"
            print(f"Removed owned disposable resource: {resource_id}", flush=True)


if __name__ == "__main__":
    main()
