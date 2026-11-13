"""AIClient 단위 테스트 — 실제 AI 서버 없이 httpx MockTransport 로 상태코드 매핑 검증."""

from __future__ import annotations

import httpx
import pytest
import json
from pathlib import Path

from src.shared.infrastructure.clients.ai_client import AIClient, AITimeoutError, AIUnavailableError, AIValidationError


def _client(handler) -> AIClient:
    return AIClient(
        base_url="http://ai-test",
        timeout_seconds=5.0,
        transport=httpx.MockTransport(handler),
        service_token="synthetic-technical-unit-service-token-32bytes",
    )


def _request():
    # Existing reviewed typed synthetic wire; no AI/config imports.
    fixture = Path(__file__).resolve().parents[2] / "frontend/tests/fixtures/cf021-technical-boundary.json"
    return json.loads(fixture.read_text())["request"]


async def test_success_returns_json():
    seen = []
    payload = _request()
    def respond(req):
        seen.append(req)
        assert req.method == "POST" and str(req.url) == "http://ai-test/internal/technical/boundary"
        assert req.headers["X-Technical-Service-Token"] == "synthetic-technical-unit-service-token-32bytes"
        assert json.loads(req.content) == payload
        return httpx.Response(200, json={"ok": True})
    out = await _client(respond).technical_boundary(payload)
    assert out == {"ok": True}
    assert len(seen) == 1


async def test_422_raises_validation():
    # Malformed typed input is rejected locally, before any HTTP exchange.
    seen = []
    with pytest.raises(AIValidationError):
        await _client(lambda req: seen.append(req)).technical_boundary({})
    assert not seen


async def test_504_raises_timeout():
    with pytest.raises(AITimeoutError):
        await _client(lambda req: httpx.Response(504)).technical_boundary(_request())


@pytest.mark.parametrize("code", [502, 503, 500])
async def test_5xx_raises_unavailable(code: int):
    with pytest.raises(AIUnavailableError):
        await _client(lambda req: httpx.Response(code)).technical_boundary(_request())


async def test_timeout_exception_raises_timeout():
    def _raise(req):
        raise httpx.TimeoutException("timeout")

    with pytest.raises(AITimeoutError):
        await _client(_raise).technical_boundary(_request())


async def test_connect_error_raises_unavailable():
    def _raise(req):
        raise httpx.ConnectError("refused")

    with pytest.raises(AIUnavailableError):
        await _client(_raise).technical_boundary(_request())


async def test_boundary_upstream_422_is_unavailable():
    seen = []
    def respond(req):
        seen.append(req)
        return httpx.Response(422, json={})
    with pytest.raises(AIUnavailableError):
        await _client(respond).technical_boundary(_request())
    assert len(seen) == 1


@pytest.mark.parametrize("code", [200, 422, 504, 502, 503, 500])
async def test_legacy_execution_is_closed_before_transport(code):
    seen = []
    def respond(req):
        seen.append(req)
        return httpx.Response(code, json={})
    with pytest.raises(AIUnavailableError, match="^Technical execution unavailable$"):
        await _client(respond).analyze_technical({"ticker": "000720"})
    assert not seen


@pytest.mark.parametrize("token", ["", "short", "x" * 31, "x" * 32 + "\n"])
async def test_boundary_invalid_token_is_closed_before_transport(token):
    seen = []
    client = AIClient("http://ai-test", 5.0, transport=httpx.MockTransport(lambda req: seen.append(req)), service_token=token)
    with pytest.raises(AIUnavailableError):
        await client.technical_boundary(_request())
    assert not seen
