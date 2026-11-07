"""Signed synthetic OIDC fixtures and in-memory HTTPX only; no Google/account calls."""

from urllib.parse import parse_qs, urlsplit
import hashlib
import base64
import time

import httpx
import pytest
from authlib.jose import JsonWebKey, JsonWebToken
from starlette.datastructures import QueryParams

from src.api.auth.google import (
    GoogleConfig,
    GoogleOIDC,
    Attempts,
    LoginFailed,
    ISSUER,
    DISCOVERY,
    ENDPOINTS,
)


@pytest.fixture(scope="module")
def rsa():
    return JsonWebKey.generate_key("RSA", 2048, {"kid": "fixture"}, is_private=True)


@pytest.fixture
def provider(rsa):
    config = GoogleConfig(
        "fixture.apps.googleusercontent.com",
        "unit-secret",
        "https://app.unit/api/auth/callback",
        ("https://app.unit",),
    )
    state = {
        "claims": {},
        "token_calls": 0,
        "keys_calls": 0,
        "headers": {"alg": "RS256", "kid": "fixture"},
    }

    def handle(request):
        if str(request.url) == DISCOVERY:
            return httpx.Response(
                200,
                json={
                    "issuer": ISSUER,
                    **ENDPOINTS,
                    "id_token_signing_alg_values_supported": ["RS256"],
                },
            )
        if str(request.url) == ENDPOINTS["jwks_uri"]:
            state["keys_calls"] += 1
            return httpx.Response(200, json={"keys": [rsa.as_dict(is_private=False)]})
        if str(request.url) == ENDPOINTS["token_endpoint"]:
            state["token_calls"] += 1
            params = parse_qs(request.content.decode())
            assert params["redirect_uri"] == [
                state.get("expected_redirect", config.redirect_uri)
            ]
            assert params["code_verifier"]
            assert params["grant_type"] == ["authorization_code"]
            state["verifier"] = params["code_verifier"][0]
            raw = (
                JsonWebToken(["RS256"])
                .encode(state["headers"], state["claims"], rsa)
                .decode()
            )
            return httpx.Response(
                200,
                json={
                    "access_token": "synthetic-only",
                    "token_type": "Bearer",
                    "id_token": raw,
                },
            )
        raise AssertionError("Unexpected external target")

    return GoogleOIDC(config, transport=httpx.MockTransport(handle)), state


async def prepare(provider, changes=None):
    client, state = provider
    url, browser = await client.start()
    query = parse_qs(urlsplit(url).query)
    assert (
        query["scope"] == ["openid"]
        and query["response_type"] == ["code"]
        and query["code_challenge_method"] == ["S256"]
    )
    assert "access_type" not in query
    now = int(time.time())
    state["claims"] = {
        "iss": ISSUER,
        "sub": "CaseSensitive123",
        "aud": client.config.client_id,
        "iat": now,
        "exp": now + 300,
        "nonce": query["nonce"][0],
    }
    state["claims"].update(changes or {})
    return (
        QueryParams({"state": query["state"][0], "code": "synthetic-code"}),
        browser,
        query,
    )


@pytest.mark.parametrize("issuer", [ISSUER, "accounts.google.com"])
async def test_signed_google_issuers_and_pkce(provider, issuer):
    client, state = provider
    params, browser, query = await prepare(provider, {"iss": issuer})
    assert await client.callback(params, browser) == (ISSUER, "CaseSensitive123")
    digest = (
        base64.urlsafe_b64encode(hashlib.sha256(state["verifier"].encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    assert query["code_challenge"] == [digest]
    with pytest.raises(LoginFailed):
        await client.callback(params, browser)
    assert state["token_calls"] == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"iss": "https://accounts.google.com/"},
        {"iss": "ACCOUNTS.google.com"},
        {"aud": "other"},
        {"aud": ["fixture.apps.googleusercontent.com", "other"]},
        {"aud": ["fixture.apps.googleusercontent.com"], "azp": "other"},
        {"azp": "other"},
        {"exp": 0},
        {"exp": True},
        {"iat": True},
        {"iat": 9999999999},
        {"nbf": 9999999999},
        {"nonce": "other"},
        {"sub": ""},
        {"sub": "가"},
        {"sub": "x" * 256},
        {"iat": None},
    ],
)
async def test_invalid_signed_claims(provider, changes):
    client, state = provider
    params, browser, _ = await prepare(provider, changes)
    with pytest.raises(LoginFailed):
        await client.callback(params, browser)
    assert state["token_calls"] == 1
    with pytest.raises(LoginFailed):
        await client.callback(params, browser)
    assert state["token_calls"] == 1


async def test_wrong_browser_duplicate_missing_and_provider_error_before_exchange(
    provider,
):
    client, state = provider
    params, browser, _ = await prepare(provider)
    with pytest.raises(LoginFailed):
        await client.callback(params, "different-browser")
    with pytest.raises(LoginFailed):
        await client.callback(params, browser)
    params, browser, _ = await prepare(provider)
    with pytest.raises(LoginFailed):
        await client.callback(QueryParams(str(params) + "&code=duplicate"), browser)
    with pytest.raises(LoginFailed):
        await client.callback(QueryParams({"code": "no-state"}), browser)
    with pytest.raises(LoginFailed):
        await client.callback(
            QueryParams({"state": params["state"], "error": "access_denied"}), browser
        )
    assert state["token_calls"] == 0


async def test_expired_restart_and_single_consumer():
    from dataclasses import replace
    import asyncio

    attempts = Attempts()
    state, attempt = await attempts.create("https://app.unit/api/auth/callback")
    attempts._entries[state] = replace(attempt, expires_at=0)
    with pytest.raises(LoginFailed):
        await attempts.consume(state, attempt.browser)
    with pytest.raises(LoginFailed):
        await Attempts().consume(state, attempt.browser)
    state, attempt = await attempts.create("https://app.unit/api/auth/callback")
    result = await asyncio.gather(
        attempts.consume(state, attempt.browser),
        attempts.consume(state, attempt.browser),
        return_exceptions=True,
    )
    assert sum(isinstance(item, LoginFailed) for item in result) == 1


@pytest.mark.parametrize(
    "config",
    [
        GoogleConfig("", "", "", ()),
        GoogleConfig(
            "client",
            "secret",
            "https://evil.unit/api/auth/callback",
            ("https://app.unit",),
        ),
        GoogleConfig(
            "client",
            "secret",
            "http://app.unit/api/auth/callback",
            ("http://app.unit",),
            True,
        ),
        GoogleConfig(
            "client",
            "secret",
            "https://app.unit/api/auth/callback?next=evil",
            ("https://app.unit",),
        ),
        GoogleConfig(
            "client",
            "secret",
            "https://app.unit/api/auth/callback",
            ("https://app.unit/path",),
        ),
    ],
)
def test_config_fails_closed(config):
    with pytest.raises(LoginFailed):
        config.validate()


def test_explicit_loopback_only_exception():
    GoogleConfig(
        "client",
        "secret",
        "http://localhost:3200/api/auth/callback",
        ("http://localhost:3200",),
        True,
    ).validate()


@pytest.mark.parametrize(
    "wire", ["missing", "unsigned", "hs256", "unknown_kid", "jku", "bad_signature"]
)
async def test_token_and_key_failures_are_safe_and_one_use(provider, rsa, wire):
    from unittest.mock import AsyncMock

    client, state = provider
    params, browser, _ = await prepare(provider)
    claims = state["claims"]
    if wire == "unsigned":
        raw = JsonWebToken(["none"]).encode({"alg": "none"}, claims, None).decode()
    elif wire == "hs256":
        raw = (
            JsonWebToken(["HS256"])
            .encode(
                {"alg": "HS256", "kid": "fixture"},
                claims,
                b"synthetic-secret-at-least-32-bytes-long",
            )
            .decode()
        )
    else:
        key = (
            JsonWebKey.generate_key(
                "RSA",
                2048,
                {"kid": "absent" if wire == "unknown_kid" else "fixture"},
                is_private=True,
            )
            if wire in {"bad_signature", "unknown_kid"}
            else rsa
        )
        header = {
            "alg": "RS256",
            "kid": "absent" if wire == "unknown_kid" else "fixture",
        }
        if wire == "jku":
            header["jku"] = "https://evil.unit/keys"
        raw = JsonWebToken(["RS256"]).encode(header, claims, key).decode()
    exchange = AsyncMock(
        return_value={
            "token_type": "Bearer",
            "access_token": "synthetic",
            **({} if wire == "missing" else {"id_token": raw}),
        }
    )
    # Patch this client's code exchange only; JWKS remains the actual MockTransport path.
    original = client.client

    def session(**kwargs):
        result = original(**kwargs)
        result.fetch_token = exchange
        return result

    client.client = session
    with pytest.raises(LoginFailed):
        await client.callback(params, browser)
    with pytest.raises(LoginFailed):
        await client.callback(params, browser)
    assert exchange.await_count == 1
    assert state["keys_calls"] == (2 if wire == "unknown_kid" else 1)
