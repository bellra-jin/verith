"""Fail-closed DB-test configuration and read-only attestation. No app imports."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from ipaddress import ip_address
from socket import inet_aton
from typing import Mapping
from urllib.parse import urlsplit

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class UnsafeTestDatabase(ValueError):
    pass


def _host(value: str | None) -> str:
    value = (value or "").lower().rstrip(".")
    if value == "localhost":
        return "loopback"
    try:
        address = ip_address(value)
        if getattr(address, "ipv4_mapped", None) is not None:
            address = address.ipv4_mapped
        return "loopback" if address.is_loopback else str(address)
    except ValueError:
        try:
            address = ip_address(inet_aton(value))
            return "loopback" if address.is_loopback else str(address)
        except OSError:
            return value


@dataclass(frozen=True)
class ApprovedTestDatabase:
    url: str = field(repr=False)
    resource_id: str
    database: str
    username: str
    server_port: int
    cleanup_owner: str

    def connection_parameters(self) -> dict:
        url = make_url(self.url)
        return {
            "host": url.host,
            "port": url.port,
            "database": url.database,
            "user": url.username,
            "password": url.password,
        }


def _unambiguous_url(raw: str):
    """No URI decoding of target components may differ across DSN/dialect parsers."""
    if "#" in raw or any(ord(char) < 32 or ord(char) == 127 for char in raw):
        raise ValueError
    parts, url = urlsplit(raw), make_url(raw)
    if any(
        "%" in (value or "") for value in (parts.hostname, parts.username, parts.path)
    ):
        raise ValueError
    if (
        parts.path != "/" + (url.database or "")
        or parts.username != url.username
        or _host(parts.hostname) != _host(url.host)
        or parts.port != url.port
    ):
        raise ValueError
    return url


def approved_database(
    environ: Mapping[str, str], app_url: str | None
) -> ApprovedTestDatabase:
    """The operator supplies approval after resource selection, never inferred from a URL."""
    raw = environ.get("TEST_DATABASE_URL", "")
    manifest = environ.get("TEST_DATABASE_APPROVAL", "").strip()
    if not raw.strip() or not manifest or not app_url:
        raise UnsafeTestDatabase(
            "Explicit test URL, app target and disposable-resource approval are required"
        )
    try:
        target, app = _unambiguous_url(raw), _unambiguous_url(app_url)
        approval = json.loads(manifest)
        required = ("resource_id", "host", "database", "username", "cleanup_owner")
        if not isinstance(approval, dict) or any(
            not isinstance(approval.get(key), str) or not approval[key].strip()
            for key in required
        ):
            raise ValueError
        if (
            approval.get("disposable") is not True
            or type(approval.get("port")) is not int
            or type(approval.get("server_port")) is not int
            or not 0 < approval["port"] < 65536
        ):
            raise ValueError
        if (
            target.drivername not in {"postgresql", "postgresql+asyncpg"}
            or target.query
            or app.query
        ):
            raise ValueError
        target_identity = (
            _host(target.host),
            target.port or 5432,
            target.database or "",
        )
        app_identity = (_host(app.host), app.port or 5432, app.database or "")
        if not all(app_identity) or not app.username:
            raise ValueError
        expected = (_host(approval["host"]), approval["port"], approval["database"])
        # Alias/equivalent spellings cannot bypass the app-target boundary.
        if target_identity[:2] == app_identity[:2] or target_identity != expected:
            raise ValueError
        if (
            not all(target_identity)
            or not target.username
            or target.username == app.username
        ):
            raise ValueError
        if target.username != approval["username"] or not (
            0 < approval["server_port"] < 65536
        ):
            raise ValueError
    except (ArgumentError, ValueError, TypeError, KeyError):
        raise UnsafeTestDatabase(
            "Test target does not match an approved isolated resource"
        ) from None
    return ApprovedTestDatabase(
        target.set(
            drivername="postgresql+asyncpg", port=target.port or 5432
        ).render_as_string(hide_password=False),
        approval["resource_id"],
        approval["database"],
        approval["username"],
        approval["server_port"],
        approval["cleanup_owner"],
    )


async def attest_database(
    approval: ApprovedTestDatabase, *, connect=None, all_restrictions=False
) -> None:
    """No SQLAlchemy engine or DDL/DML before this read-only check has succeeded."""
    if connect is None:
        from asyncpg import connect
    connection = None
    failed = False
    try:
        connection = await connect(**approval.connection_parameters(), timeout=3)
        async with connection.transaction(readonly=True):
            row = await connection.fetchrow(identity_query(all_restrictions))
            failed = not _identity_matches(row, approval)
    except Exception:
        failed = True
    finally:
        if connection is not None:
            try:
                await connection.close()
            except Exception:
                failed = True
    if failed:
        raise UnsafeTestDatabase(
            "Read-only disposable DB/role/resource attestation failed"
        ) from None


async def preflight_database(
    environ: Mapping[str, str], app_url: str | None, *, connect=None
) -> ApprovedTestDatabase:
    approval = approved_database(environ, app_url)
    await attest_database(approval, connect=connect)
    return approval


def identity_query(all_restrictions=False) -> str:
    flags = "rolsuper OR rolcreatedb OR rolcreaterole"
    if all_restrictions:
        flags += " OR rolinherit OR rolreplication OR rolbypassrls OR NOT rolcanlogin"
    return f"""SELECT current_database() AS database, current_user AS username,
        inet_server_port() AS server_port,
        current_setting('verith.test_resource_id', true) AS resource_id,
        ({flags}) AS privileged
        FROM pg_roles WHERE rolname = current_user"""


def _identity_matches(row, approval: ApprovedTestDatabase) -> bool:
    return (
        bool(row)
        and row["privileged"] is False
        and all(
            row[key] == value
            for key, value in {
                "database": approval.database,
                "username": approval.username,
                "server_port": approval.server_port,
                "resource_id": approval.resource_id,
            }.items()
        )
    )


async def attest_engine_connection(
    connection, approval: ApprovedTestDatabase, *, all_restrictions=False
) -> None:
    """Recheck the actual SQLAlchemy connection before even fixture DDL/DML begins."""
    try:
        async with connection.begin():
            await connection.execute(text("SET TRANSACTION READ ONLY"))
            result = await connection.execute(text(identity_query(all_restrictions)))
            if not _identity_matches(result.mappings().one(), approval):
                raise ValueError
    except Exception:
        raise UnsafeTestDatabase(
            "Actual engine connection identity mismatch; no fixture writes allowed"
        ) from None
