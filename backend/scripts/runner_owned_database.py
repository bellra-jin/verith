"""v0.6: direct local creation receipts only; never an app-URL-check bypass."""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import tempfile
import time
from uuid import uuid4

from sqlalchemy.engine import URL

from scripts.google_login_workspace import child_base_environment
from tests.db_safety import attest_database, attest_engine_connection

_ALLOWED_IMAGE = "pgvector/pgvector:pg16"
_CAPABILITY = object()
_INSPECT = """{"Id":{{json .Id}},"Created":{{json .Created}},"Running":{{json .State.Running}},"Status":{{json .State.Status}},"Image":{{json .Config.Image}},"Labels":{{json .Config.Labels}},"Mounts":{{json .Mounts}},"Readonly":{{json .HostConfig.ReadonlyRootfs}},"Tmpfs":{{json .HostConfig.Tmpfs}},"Network":{{json .HostConfig.NetworkMode}},"Privileged":{{json .HostConfig.Privileged}},"VolumesFrom":{{json .HostConfig.VolumesFrom}},"Binds":{{json .HostConfig.Binds}},"Links":{{json .HostConfig.Links}},"PidMode":{{json .HostConfig.PidMode}},"IpcMode":{{json .HostConfig.IpcMode}},"PortBindings":{{json .HostConfig.PortBindings}},"Ports":{{json .NetworkSettings.Ports}}}"""


class OwnedDatabaseError(RuntimeError):
    def __init__(self, message="Owned disposable resource verification failed"):
        super().__init__(message)


def _timestamp(value):
    # Docker may return nanosecond precision; datetime accepts microseconds.
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@dataclass(frozen=True)
class CreationReceipt:
    container_id: str
    resource_id: str
    nonce: str = field(repr=False)
    requested_at: datetime
    returned_at: datetime
    created_at: str | None = None
    bound_port: int | None = None


def verify_metadata(
    receipt: CreationReceipt, info: dict, *, require_running=True
) -> tuple[str, int | None]:
    """No output of inspect data, Env, URLs or credentials on any rejection."""
    try:
        if (
            not re.fullmatch(r"[0-9a-f]{64}", receipt.container_id)
            or info["Id"] != receipt.container_id
        ):
            raise ValueError
        labels = info["Labels"]
        if (
            labels.get("verith.task") != "CF-002-interactive"
            or labels.get("verith.resource_id") != receipt.resource_id
            or labels.get("verith.nonce") != receipt.nonce
        ):
            raise ValueError
        created = info["Created"]
        if (
            not receipt.requested_at - timedelta(seconds=2)
            <= _timestamp(created)
            <= receipt.returned_at + timedelta(seconds=2)
        ):
            raise ValueError
        if receipt.created_at is not None and created != receipt.created_at:
            raise ValueError
        if (
            info["Image"] != _ALLOWED_IMAGE
            or info["Readonly"] is not True
            or info["Privileged"] is not False
        ):
            raise ValueError
        if info["Mounts"] or info["Binds"] or info["VolumesFrom"] or info["Links"]:
            raise ValueError
        if (
            info["Network"] not in {"bridge", "default"}
            or info["PidMode"]
            or info["IpcMode"] not in {"private", ""}
        ):
            raise ValueError
        if set(info["Tmpfs"]) != {
            "/var/lib/postgresql/data",
            "/var/run/postgresql",
            "/tmp",
        } or any(value != "rw" for value in info["Tmpfs"].values()):
            raise ValueError
        bindings = info["PortBindings"]
        if set(bindings) != {"5432/tcp"} or len(bindings["5432/tcp"]) != 1:
            raise ValueError
        requested = bindings["5432/tcp"][0]
        if requested["HostIp"] != "127.0.0.1":
            raise ValueError
        port = receipt.bound_port
        if require_running and (
            info["Running"] is not True or info["Status"] != "running"
        ):
            raise ValueError
        if info["Running"]:
            if info["Status"] not in {"running", "paused"} or set(info["Ports"]) != {
                "5432/tcp"
            }:
                raise ValueError
            (actual,) = info["Ports"]["5432/tcp"]
            port = int(actual["HostPort"])
            if (
                actual["HostIp"] != "127.0.0.1"
                or not 1024 < port < 65536
                or port in {5432, 5433, 15432}
            ):
                raise ValueError
            if receipt.bound_port is not None and port != receipt.bound_port:
                raise ValueError
        else:
            if info["Status"] not in {"created", "exited", "dead"}:
                raise ValueError
            # Stopped Docker containers normally lose their live Ports projection.
            live_ports = info.get("Ports") or {}
            if set(live_ports) - {"5432/tcp"}:
                raise ValueError
            if live_ports.get("5432/tcp"):
                (actual,) = live_ports["5432/tcp"]
                if (
                    actual["HostIp"] != "127.0.0.1"
                    or receipt.bound_port is None
                    or int(actual["HostPort"]) != receipt.bound_port
                ):
                    raise ValueError
        if requested["HostPort"] not in ("", "0", str(port)):
            raise ValueError
        return created, port
    except (KeyError, ValueError, TypeError, AttributeError):
        raise OwnedDatabaseError() from None


class LocalDocker:
    def __init__(self, *, execute=subprocess.run):
        self._execute = execute
        self._environment = child_base_environment()
        self._environment["HOME"] = str(Path.home())
        # Read only the selected current context endpoint. Never inspect Docker Env.
        result = execute(
            [
                "docker",
                "context",
                "inspect",
                "--format",
                "{{json .Endpoints.docker.Host}}",
            ],
            env=self._environment,
            capture_output=True,
            text=True,
            timeout=15,
        )
        try:
            endpoint = json.loads(result.stdout)
            if (
                result.returncode
                or not isinstance(endpoint, str)
                or not endpoint.startswith("unix:///")
                or "?" in endpoint
                or "#" in endpoint
            ):
                raise ValueError
            socket_path = Path(endpoint.removeprefix("unix://")).resolve()
            allowed = {
                (Path.home() / ".docker/run/docker.sock").resolve(),
                Path("/var/run/docker.sock").resolve(),
            }
            if socket_path not in allowed or not stat.S_ISSOCK(
                socket_path.stat().st_mode
            ):
                raise ValueError
            for name in ("DOCKER_HOST",):
                declared = os.environ.get(name)
                if declared and declared != endpoint:
                    raise ValueError
        except (OSError, TypeError, ValueError):
            raise OwnedDatabaseError(
                "A verified local Unix Docker context is required"
            ) from None
        self._endpoint = endpoint
        self._config = tempfile.TemporaryDirectory(prefix="cf002-docker-cli-")

    def call(
        self, *arguments, input_text=None, extra_environment=None, allow_failure=False
    ):
        result = self._execute(
            [
                "docker",
                "--host",
                self._endpoint,
                "--config",
                self._config.name,
                *arguments,
            ],
            env={**self._environment, **(extra_environment or {})},
            input=input_text,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode and not allow_failure:
            raise OwnedDatabaseError("Owned local Docker operation failed")
        return result

    def inspect(self, identifier):
        try:
            return json.loads(
                self.call("inspect", "--format", _INSPECT, identifier).stdout
            )
        except (TypeError, ValueError):
            raise OwnedDatabaseError() from None

    def absent(self, identifier):
        result = self.call(
            "inspect", "--format", "{{.Id}}", identifier, allow_failure=True
        )
        if result.returncode == 0:
            return False
        # A daemon/permission/timeout error is not absence. Never print raw stderr.
        expected = re.compile(
            r"(?:Error: No such object:|Error response from daemon: No such (?:object|container):)\s*"
            + re.escape(identifier)
        )
        if (
            result.stdout.strip() not in {"", "[]"}
            or expected.fullmatch(result.stderr.strip()) is None
        ):
            raise OwnedDatabaseError("Owned resource absence is unconfirmed")
        return True

    def close(self):
        self._config.cleanup()


class RunnerOwnedDatabase:
    """Minted only by this process's create receipt, not URL/JSON/env input."""

    def __init__(self, capability, owner):
        if capability is not _CAPABILITY:
            raise OwnedDatabaseError()
        self._owner = owner
        self.database, self.username = owner.database, owner.role
        self.server_port, self.resource_id = 5432, owner.nonce
        self.cleanup_owner = "CF-002 interactive runner"
        self.url = URL.create(
            "postgresql+asyncpg",
            username=owner.role,
            password=owner._password,
            host="127.0.0.1",
            port=owner.receipt.bound_port,
            database=owner.database,
        ).render_as_string(hide_password=False)

    def __repr__(self):
        return "<RunnerOwnedDatabase verified temporary target>"

    def connection_parameters(self):
        from sqlalchemy.engine import make_url

        url = make_url(self.url)
        return dict(
            host=url.host,
            port=url.port,
            database=url.database,
            user=url.username,
            password=url.password,
        )

    def verify_ownership(self):
        self._owner.verify()

    async def preflight(self, *, connect=None):
        self.verify_ownership()
        await attest_database(self, connect=connect, all_restrictions=True)

    async def attest_connection(self, connection):
        self.verify_ownership()
        await attest_engine_connection(connection, self, all_restrictions=True)

    def safe_receipt(self):
        return self._owner.safe_receipt()


class OwnedPostgres:
    def __init__(self, docker: LocalDocker):
        self.docker = docker
        suffix = uuid4().hex[:12]
        self.name = "verith-cf002-login-" + suffix
        self.resource_id = "CF-002-login-" + suffix
        self.nonce = secrets.token_hex(32)
        self.admin = "cf002_admin_" + suffix
        self.database = "cf002_db_" + suffix
        self.role = "cf002_role_" + suffix
        self._password = secrets.token_urlsafe(32)
        self._admin_password = secrets.token_urlsafe(32)
        self.receipt = None
        self.proof = None
        self._removed = False

    def create(self):
        if self.receipt is not None:
            raise OwnedDatabaseError("Resource already created by this owner")
        before = datetime.now(UTC)
        result = self.docker.call(
            "create",
            "--pull=never",
            "--name",
            self.name,
            "--label",
            "verith.task=CF-002-interactive",
            "--label",
            f"verith.resource_id={self.resource_id}",
            "--label",
            f"verith.nonce={self.nonce}",
            "--read-only",
            "--memory",
            "512m",
            "--cpus",
            "1",
            "--network",
            "bridge",
            "--tmpfs",
            "/var/lib/postgresql/data:rw",
            "--tmpfs",
            "/var/run/postgresql:rw",
            "--tmpfs",
            "/tmp:rw",
            "--publish",
            "127.0.0.1::5432",
            "--env",
            f"POSTGRES_USER={self.admin}",
            "--env",
            f"POSTGRES_DB={self.database}",
            "--env",
            "POSTGRES_PASSWORD",
            "--env",
            "POSTGRES_HOST_AUTH_METHOD=scram-sha-256",
            _ALLOWED_IMAGE,
            "postgres",
            "-c",
            f"verith.test_resource_id={self.nonce}",
            extra_environment={"POSTGRES_PASSWORD": self._admin_password},
        )
        identifier = result.stdout.strip()
        if not re.fullmatch(r"[0-9a-f]{64}", identifier):
            raise OwnedDatabaseError("Creation receipt was not a full container ID")
        self.receipt = CreationReceipt(
            identifier, self.resource_id, self.nonce, before, datetime.now(UTC)
        )
        initial = self.docker.inspect(identifier)
        created, _ = verify_metadata(self.receipt, initial, require_running=False)
        from dataclasses import replace

        self.receipt = replace(self.receipt, created_at=created)
        self.docker.call("start", identifier)
        _, port = verify_metadata(self.receipt, self.docker.inspect(identifier))
        self.receipt = replace(self.receipt, bound_port=port)
        for _ in range(80):
            if (
                self.docker.call(
                    "exec",
                    identifier,
                    "pg_isready",
                    "-h",
                    "127.0.0.1",
                    "-U",
                    self.admin,
                    "-d",
                    self.database,
                    allow_failure=True,
                ).returncode
                == 0
            ):
                break
            time.sleep(0.1)
        else:
            raise OwnedDatabaseError("Owned PostgreSQL readiness timed out")
        self.verify()
        # Read-only bootstrap identity before limited-role provisioning in this new resource.
        identity = self.sql(
            "BEGIN READ ONLY; SELECT current_database() || '|' || current_user || '|' || current_setting('verith.test_resource_id'); COMMIT;",
            tuples=True,
        )
        if f"{self.database}|{self.admin}|{self.nonce}" not in identity.splitlines():
            raise OwnedDatabaseError("Bootstrap server identity mismatch")
        self.sql(
            f"CREATE ROLE {self.role} LOGIN PASSWORD '{self._password}' NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;\nREVOKE CONNECT ON DATABASE postgres FROM PUBLIC;\nREVOKE CONNECT ON DATABASE template1 FROM PUBLIC;\nGRANT CONNECT,TEMPORARY,CREATE ON DATABASE {self.database} TO {self.role};\nGRANT USAGE,CREATE ON SCHEMA public TO {self.role};"
        )
        self.proof = RunnerOwnedDatabase(_CAPABILITY, self)
        return self.proof

    def verify(self):
        if self.receipt is None or self._removed:
            raise OwnedDatabaseError()
        verify_metadata(self.receipt, self.docker.inspect(self.receipt.container_id))

    def sql(self, statement, *, tuples=False):
        self.verify()
        return self.docker.call(
            "exec",
            "-i",
            self.receipt.container_id,
            "psql",
            "-U",
            self.admin,
            "-d",
            self.database,
            "-v",
            "ON_ERROR_STOP=1",
            *(["-At"] if tuples else []),
            input_text=statement,
        ).stdout

    def safe_receipt(self):
        r = self.receipt
        return dict(
            resource_id=self.resource_id,
            container_id=r.container_id,
            created_at=r.created_at,
            nonce=self.nonce,
            host="127.0.0.1",
            port=r.bound_port,
            persistent_mounts=0,
            cleanup_owner="CF-002 interactive runner",
        )

    def cleanup(self):
        if self.receipt is None or self._removed:
            return
        # A clearly absent resource is idempotent; daemon errors are not absence.
        if self.docker.absent(self.receipt.container_id):
            self._removed = True
            return
        info = self.docker.inspect(self.receipt.container_id)
        verify_metadata(self.receipt, info, require_running=False)
        if info["Running"]:
            self.docker.call("stop", "--time", "5", self.receipt.container_id)
        self.docker.call("rm", "--force", self.receipt.container_id)
        if not self.docker.absent(self.receipt.container_id):
            raise OwnedDatabaseError("Owned resource removal not confirmed")
        self._removed = True
