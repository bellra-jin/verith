"""CF-001 unit boundary. Run with --confcutdir=tests/unit to exclude DB conftest."""

import socket

import pytest


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    # Never read private .env files in isolated unit/config checks.
    from pydantic_settings.sources import DotEnvSettingsSource

    monkeypatch.setattr(DotEnvSettingsSource, "_read_env_files", lambda self: {})
    # Route imports construct an unused engine. Set dummy values before the lazy
    # route import, and restore the process environment after every unit test.
    values = {
        "DATABASE_URL": "postgresql+asyncpg://unused:unused@127.0.0.1:1/cf001_no_db",
        "TEST_DATABASE_URL": "postgresql+asyncpg://unused:unused@127.0.0.1:1/cf001_no_db",
        "NEO4J_URI": "bolt://127.0.0.1:1",
        "NEO4J_USER": "unused",
        "NEO4J_PASSWORD": "unused",
        "AI_SERVICE_URL": "http://127.0.0.1:1",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Network/DB access is forbidden in CF-001 unit tests")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
