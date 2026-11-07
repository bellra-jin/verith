"""Google-only OIDC code/PKCE adapter. Never follows token-supplied key URLs.

Pending attempts are one-use, bounded and process-local. Restart or a callback to
another worker fails closed; this is not a multi-process shared state store.
"""

from __future__ import annotations
import asyncio
from dataclasses import dataclass, field
import hmac
import math
import secrets
import time
from urllib.parse import urlsplit

import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client
from authlib.jose import JsonWebToken
from authlib.oidc.core import CodeIDToken

ISSUER = "https://accounts.google.com"
DISCOVERY = ISSUER + "/.well-known/openid-configuration"
ENDPOINTS = {
    "authorization_endpoint": ISSUER + "/o/oauth2/v2/auth",
    "token_endpoint": "https://oauth2.googleapis.com/token",
    "jwks_uri": "https://www.googleapis.com/oauth2/v3/certs",
}


class LoginFailed(ValueError):
    def __init__(self):
        super().__init__("Login failed; start a new login attempt")


@dataclass(frozen=True)
class GoogleConfig:
    client_id: str
    client_secret: str = field(repr=False)
    redirect_uri: str
    origins: tuple[str, ...]
    allow_local_http: bool = False

    def validate(self):
        if not self.client_id or not self.client_secret or not self.origins:
            raise LoginFailed()
        redirect = urlsplit(self.redirect_uri)
        origin = f"{redirect.scheme}://{redirect.netloc}"
        if (
            redirect.path != "/api/auth/callback"
            or redirect.query
            or redirect.fragment
            or redirect.username
            or redirect.password
            or origin not in self.origins
        ):
            raise LoginFailed()
        for item in (*self.origins, origin):
            url = urlsplit(item)
            if (
                url.path
                or url.query
                or url.fragment
                or url.username
                or url.password
                or not url.hostname
            ):
                raise LoginFailed()
            if url.scheme != "https" and not (
                self.allow_local_http
                and url.scheme == "http"
                and url.hostname == "localhost"
                and url.port == 3200
            ):
                raise LoginFailed()


@dataclass(frozen=True, repr=False)
class Attempt:
    nonce: str
    verifier: str
    browser: str
    redirect_uri: str
    expires_at: float


class Attempts:
    def __init__(self):
        self._entries: dict[str, Attempt] = {}
        self._lock = asyncio.Lock()

    async def create(self, redirect_uri):
        async with self._lock:
            now = time.monotonic()
            self._entries = {
                k: v for k, v in self._entries.items() if v.expires_at > now
            }
            if len(self._entries) >= 1024:
                raise LoginFailed()
            state, browser = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            attempt = Attempt(
                secrets.token_urlsafe(32),
                secrets.token_urlsafe(48),
                browser,
                redirect_uri,
                now + 300,
            )
            self._entries[state] = attempt
            return state, attempt

    async def consume(self, state, browser):
        async with self._lock:
            attempt = self._entries.pop(state, None)
        if (
            not attempt
            or not browser
            or attempt.expires_at <= time.monotonic()
            or not hmac.compare_digest(attempt.browser, browser)
        ):
            raise LoginFailed()
        return attempt


class GoogleOIDC:
    def __init__(self, config: GoogleConfig, *, transport=None):
        self.config = config
        self.attempts = Attempts()
        self.transport = transport
        self._metadata = None
        self._keys = None
        self._cached_at = 0
        self._cache_lock = asyncio.Lock()

    async def metadata(self, *, refresh=False):
        self.config.validate()
        async with self._cache_lock:
            if (
                not refresh
                and self._metadata
                and time.monotonic() - self._cached_at < 300
            ):
                return self._metadata, self._keys
            async with httpx.AsyncClient(
                timeout=10, follow_redirects=False, transport=self.transport
            ) as client:
                response = await client.get(DISCOVERY)
                response.raise_for_status()
                metadata = response.json()
                if metadata.get("issuer") != ISSUER or any(
                    metadata.get(k) != v for k, v in ENDPOINTS.items()
                ):
                    raise LoginFailed()
                if "RS256" not in metadata.get(
                    "id_token_signing_alg_values_supported", []
                ):
                    raise LoginFailed()
                response = await client.get(ENDPOINTS["jwks_uri"])
                response.raise_for_status()
                keys = response.json()
                if not isinstance(keys.get("keys"), list) or not keys["keys"]:
                    raise LoginFailed()
            self._metadata, self._keys, self._cached_at = (
                metadata,
                keys,
                time.monotonic(),
            )
            return metadata, keys

    def client(self, **kwargs):
        return AsyncOAuth2Client(
            self.config.client_id,
            self.config.client_secret,
            scope="openid",
            redirect_uri=self.config.redirect_uri,
            code_challenge_method="S256",
            token_endpoint_auth_method="client_secret_post",
            timeout=10,
            follow_redirects=False,
            transport=self.transport,
            **kwargs,
        )

    async def start(self):
        metadata, _ = await self.metadata()
        state, attempt = await self.attempts.create(self.config.redirect_uri)
        async with self.client() as client:
            url, _ = client.create_authorization_url(
                metadata["authorization_endpoint"],
                state=state,
                nonce=attempt.nonce,
                code_verifier=attempt.verifier,
                response_type="code",
            )
        return url, attempt.browser

    async def callback(self, params, browser):
        try:
            return await self._callback(params, browser)
        except Exception:
            raise LoginFailed() from None

    async def _callback(self, params, browser):
        # Reject ambiguous query parameters before any code exchange.
        if any(
            len(params.getlist(key)) != 1 for key in params.keys()
        ) or not params.get("state"):
            raise LoginFailed()
        attempt = await self.attempts.consume(params["state"], browser)
        if params.get("error") or not params.get("code"):
            raise LoginFailed()
        metadata, keys = await self.metadata()
        async with self.client(state=params["state"]) as client:
            # Code exchange is not automatically retried.
            token = await client.fetch_token(
                metadata["token_endpoint"],
                grant_type="authorization_code",
                code=params["code"],
                code_verifier=attempt.verifier,
                redirect_uri=attempt.redirect_uri,
            )
        raw = token.get("id_token")
        if not isinstance(raw, str):
            raise LoginFailed()
        # Restricted Authlib decoder, no jku/x5u fetching. Refresh once only for an unknown kid.
        from authlib.jose.errors import InvalidClaimError
        from authlib.common.encoding import json_loads, urlsafe_b64decode

        header = json_loads(urlsafe_b64decode(raw.split(".")[0].encode("ascii")))
        kid = header.get("kid")
        if (
            header.get("alg") != "RS256"
            or not isinstance(kid, str)
            or not kid
            or header.get("jku")
            or header.get("x5u")
        ):
            raise LoginFailed()
        if not any(key.get("kid") == kid for key in keys["keys"]):
            _, keys = await self.metadata(refresh=True)
        try:
            claims = JsonWebToken(["RS256"]).decode(
                raw,
                keys,
                claims_cls=CodeIDToken,
                claims_options={
                    "iss": {
                        "essential": True,
                        "values": [ISSUER, "accounts.google.com"],
                    },
                    "aud": {"essential": True, "value": self.config.client_id},
                },
                claims_params={
                    "nonce": attempt.nonce,
                    "client_id": self.config.client_id,
                    "access_token": token.get("access_token"),
                },
            )
            claims.validate(leeway=60)
        except InvalidClaimError:
            raise LoginFailed() from None
        self.validate_claims(claims, attempt.nonce)
        return ISSUER, claims["sub"]

    def validate_claims(self, claims, nonce, *, now=None):
        now = time.time() if now is None else now
        if (
            claims.get("iss") not in {ISSUER, "accounts.google.com"}
            or claims.get("nonce") != nonce
        ):
            raise LoginFailed()
        subject = claims.get("sub")
        if (
            not isinstance(subject, str)
            or not subject
            or len(subject) > 255
            or not subject.isascii()
        ):
            raise LoginFailed()
        aud, azp = claims.get("aud"), claims.get("azp")
        if isinstance(aud, list):
            if (
                not all(isinstance(item, str) for item in aud)
                or self.config.client_id not in aud
                or azp != self.config.client_id
            ):
                raise LoginFailed()
        elif (
            aud != self.config.client_id
            or azp is not None
            and azp != self.config.client_id
        ):
            raise LoginFailed()
        for key in ("exp", "iat", "nbf"):
            if key == "nbf" and key not in claims:
                continue
            value = claims.get(key)
            if type(value) not in (int, float) or not math.isfinite(value):
                raise LoginFailed()
        if (
            not now < claims["exp"]
            or claims["exp"] <= claims["iat"]
            or claims["iat"] > now + 60
            or claims.get("nbf", now) > now + 60
        ):
            raise LoginFailed()
