"""No Docker/DB/Google: mutated creation receipts, early-stop and copy regressions."""

from datetime import UTC, datetime, timedelta
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
import json

import pytest

from scripts.runner_owned_database import (
    CreationReceipt,
    OwnedDatabaseError,
    RunnerOwnedDatabase,
    verify_metadata,
    LocalDocker,
)


def fixture_metadata():
    now = datetime.now(UTC)
    receipt = CreationReceipt(
        "a" * 64,
        "synthetic-owned",
        "synthetic-nonce",
        now - timedelta(seconds=1),
        now + timedelta(seconds=1),
    )
    info = dict(
        Id="a" * 64,
        Created=now.isoformat(),
        Running=True,
        Status="running",
        Image="pgvector/pgvector:pg16",
        Labels={
            "verith.task": "CF-002-interactive",
            "verith.resource_id": "synthetic-owned",
            "verith.nonce": "synthetic-nonce",
        },
        Mounts=[],
        Readonly=True,
        Tmpfs={
            "/var/lib/postgresql/data": "rw",
            "/var/run/postgresql": "rw",
            "/tmp": "rw",
        },
        Network="bridge",
        Privileged=False,
        VolumesFrom=None,
        Binds=None,
        Links=None,
        PidMode="",
        IpcMode="private",
        PortBindings={"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": ""}]},
        Ports={"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": "6550"}]},
    )
    return receipt, info


def test_created_receipt_and_recheck_are_exact():
    receipt, info = fixture_metadata()
    created, port = verify_metadata(receipt, info)
    assert port == 6550
    verify_metadata(replace(receipt, created_at=created, bound_port=port), info)


@pytest.mark.parametrize(
    "field,value",
    [
        ("Id", "b" * 64),
        ("Created", "2000-01-01T00:00:00Z"),
        ("Readonly", False),
        ("Privileged", True),
        ("Mounts", [{"Type": "bind"}]),
        ("Binds", ["/fake:/fake"]),
        ("VolumesFrom", ["old"]),
        ("Network", "host"),
        ("PidMode", "host"),
        ("IpcMode", "host"),
        ("Links", ["old"]),
        ("Image", "postgres:latest"),
        ("Tmpfs", {"/tmp": "rw"}),
        ("Running", False),
        ("Status", "exited"),
        ("PortBindings", {"5432/tcp": [{"HostIp": "0.0.0.0", "HostPort": "6550"}]}),
        ("Ports", {"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": "15432"}]}),
        ("Ports", {"5432/tcp": [{"HostIp": "0.0.0.0", "HostPort": "6550"}]}),
        (
            "Ports",
            {
                "5432/tcp": [
                    {"HostIp": "127.0.0.1", "HostPort": "6550"},
                    {"HostIp": "::1", "HostPort": "6550"},
                ]
            },
        ),
    ],
)
def test_bad_ownership_metadata_is_rejected(field, value):
    receipt, info = fixture_metadata()
    info[field] = value
    with pytest.raises(OwnedDatabaseError):
        verify_metadata(receipt, info)


@pytest.mark.parametrize("label", ["verith.task", "verith.resource_id", "verith.nonce"])
def test_marker_alone_is_not_ownership(label):
    receipt, info = fixture_metadata()
    info["Labels"][label] = "forged"
    with pytest.raises(OwnedDatabaseError):
        verify_metadata(receipt, info)


def test_existing_timestamp_or_changed_binding_rejected():
    receipt, info = fixture_metadata()
    with pytest.raises(OwnedDatabaseError):
        verify_metadata(replace(receipt, created_at="different"), info)
    with pytest.raises(OwnedDatabaseError):
        verify_metadata(replace(receipt, bound_port=6551), info)


def test_external_config_cannot_mint_proof():
    with pytest.raises(OwnedDatabaseError):
        RunnerOwnedDatabase(None, {"url": "fake", "nonce": "fake"})


@pytest.mark.parametrize(
    "endpoint",
    [
        "ssh://remote",
        "tcp://127.0.0.1:2375",
        "https://remote",
        "unix:///unapproved/forward.sock",
    ],
)
def test_remote_or_unknown_daemon_is_refused(endpoint):
    execute = Mock(
        return_value=SimpleNamespace(returncode=0, stdout=json.dumps(endpoint))
    )
    with pytest.raises(OwnedDatabaseError):
        LocalDocker(execute=execute)
    assert execute.call_count == 1


async def test_failed_readonly_preflight_precedes_engine_migration_or_apps(monkeypatch):
    from scripts.cf002_interactive_login import migrate_owned
    import sqlalchemy.ext.asyncio as sa

    create = Mock(side_effect=AssertionError("No engine before attestation"))
    monkeypatch.setattr(sa, "create_async_engine", create)
    proof = SimpleNamespace(preflight=AsyncMock(side_effect=OwnedDatabaseError()))
    with pytest.raises(OwnedDatabaseError):
        await migrate_owned(proof)
    create.assert_not_called()


@pytest.mark.parametrize(
    "error",
    [
        "Cannot connect to the Docker daemon at unix:///fake/socket",
        "permission denied: fake-secret-do-not-log",
        "request timed out",
        "Error: No such object: another-id",
    ],
)
def test_inspect_failure_does_not_count_as_absence(error):
    docker = LocalDocker.__new__(LocalDocker)
    docker.call = Mock(
        return_value=SimpleNamespace(returncode=1, stdout="", stderr=error)
    )
    with pytest.raises(OwnedDatabaseError, match="unconfirmed") as caught:
        docker.absent("a" * 64)
    assert "fake-secret" not in str(caught.value)


def test_only_exact_not_found_confirms_absence():
    docker = LocalDocker.__new__(LocalDocker)
    docker.call = Mock(
        return_value=SimpleNamespace(
            returncode=1, stdout="", stderr="Error: No such object: " + "a" * 64
        )
    )
    assert docker.absent("a" * 64)


def test_stopped_owned_resource_cleanup_retry_and_idempotence():
    from scripts.runner_owned_database import OwnedPostgres

    receipt, info = fixture_metadata()
    receipt = replace(receipt, created_at=info["Created"], bound_port=6550)
    info.update(Running=False, Status="exited", Ports={"5432/tcp": None})
    docker = SimpleNamespace(
        absent=Mock(side_effect=[False, False, True]),
        inspect=Mock(return_value=info),
        call=Mock(),
    )
    owner = OwnedPostgres(docker)
    owner.receipt = receipt
    docker.call.side_effect = [OwnedDatabaseError(), None]
    with pytest.raises(OwnedDatabaseError):
        owner.cleanup()
    assert not owner._removed
    owner.cleanup()
    owner.cleanup()
    assert owner._removed
    assert docker.call.call_count == 2
    assert all(call.args[0] == "rm" for call in docker.call.call_args_list)


def test_cleanup_absence_error_keeps_receipt_and_retryable_state():
    from scripts.runner_owned_database import OwnedPostgres

    receipt, info = fixture_metadata()
    docker = SimpleNamespace(
        absent=Mock(
            side_effect=[
                False,
                OwnedDatabaseError("Owned resource absence is unconfirmed"),
            ]
        ),
        inspect=Mock(return_value=info),
        call=Mock(),
    )
    owner = OwnedPostgres(docker)
    owner.receipt = replace(receipt, created_at=info["Created"], bound_port=6550)
    with pytest.raises(OwnedDatabaseError):
        owner.cleanup()
    assert not owner._removed and owner.receipt.container_id == "a" * 64
