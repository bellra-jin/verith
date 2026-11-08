"""Internal verified-identity linking and PostgreSQL-revocable app sessions.

No public caller can choose a user UUID or mint a session through this module.
The OIDC adapter must verify issuer/signature/audience/nonce before identity linking.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import secrets
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.auth.models import AuthIdentity, AuthSession, AuthUser


class AuthenticationRequired(ValueError):
    def __init__(self):
        super().__init__("Authentication required")


@dataclass(frozen=True)
class Principal:
    user_id: UUID
    session_id: UUID
    expires_at: datetime
    token_digest: bytes = field(repr=False)


def token_digest(token: str) -> bytes:
    if not isinstance(token, str) or not 40 <= len(token) <= 256 or not token.isascii():
        raise AuthenticationRequired()
    return hashlib.sha256(token.encode("ascii")).digest()


async def link_verified_identity(
    session: AsyncSession, *, issuer: str, subject: str
) -> AuthUser:
    if not issuer or not subject or len(subject) > 255:
        raise AuthenticationRequired()

    async def existing():
        return await session.scalar(
            select(AuthUser)
            .join(AuthIdentity, AuthIdentity.user_id == AuthUser.id)
            .where(AuthIdentity.issuer == issuer, AuthIdentity.subject == subject)
        )

    user = await existing()
    if user is None:
        try:
            async with session.begin_nested():
                user = AuthUser(id=uuid4())
                session.add(user)
                await session.flush()
                session.add(
                    AuthIdentity(
                        id=uuid4(), user_id=user.id, issuer=issuer, subject=subject
                    )
                )
                await session.flush()
        except IntegrityError:
            # The losing savepoint rolls back the new user as well as its identity.
            user = await existing()
            if user is None:
                raise AuthenticationRequired() from None
    if user.disabled_at is not None:
        raise AuthenticationRequired()
    return user


async def issue_session(
    session: AsyncSession, user: AuthUser, *, ttl_seconds: int = 3600
) -> tuple[str, Principal]:
    if (
        type(ttl_seconds) is not int
        or not 0 < ttl_seconds <= 2147483647
        or user.disabled_at is not None
    ):
        raise AuthenticationRequired()
    now, token = datetime.now(UTC), secrets.token_urlsafe(32)
    row = AuthSession(
        id=uuid4(),
        user_id=user.id,
        token_digest=token_digest(token),
        created_at=now,
        expires_at=now + timedelta(seconds=ttl_seconds),
    )
    session.add(row)
    await session.flush()
    return token, Principal(user.id, row.id, row.expires_at, row.token_digest)


async def authenticate(
    session: AsyncSession,
    token: str,
    *,
    lock: bool = False,
    exclusive_lock: bool = False,
) -> Principal:
    digest = token_digest(token)
    statement = (
        select(AuthSession)
        .join(AuthUser, AuthUser.id == AuthSession.user_id)
        .where(
            AuthSession.token_digest == digest,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > func.clock_timestamp(),
            AuthUser.disabled_at.is_(None),
        )
    )
    if lock or exclusive_lock:
        statement = statement.with_for_update(read=not exclusive_lock, of=AuthSession)
    row = await session.scalar(statement.execution_options(populate_existing=True))
    if row is None:
        raise AuthenticationRequired()
    return Principal(row.user_id, row.id, row.expires_at, row.token_digest)


async def validate_principal(
    session: AsyncSession, principal: Principal, *, lock: bool = False
) -> None:
    statement = (
        select(AuthSession)
        .join(AuthUser, AuthUser.id == AuthSession.user_id)
        .where(
            AuthSession.id == principal.session_id,
            AuthSession.user_id == principal.user_id,
            AuthSession.token_digest == principal.token_digest,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > func.clock_timestamp(),
            AuthUser.disabled_at.is_(None),
        )
    )
    if lock:
        statement = statement.with_for_update(read=True, of=AuthSession)
    if (
        await session.scalar(statement.execution_options(populate_existing=True))
        is None
    ):
        raise AuthenticationRequired()


async def revoke_session(session: AsyncSession, principal: Principal) -> None:
    await session.execute(
        update(AuthSession)
        .where(
            AuthSession.id == principal.session_id,
            AuthSession.user_id == principal.user_id,
        )
        .values(revoked_at=func.clock_timestamp())
    )
    await session.commit()


def csrf_token(principal: Principal) -> str:
    # Session-bound synchronizer derived from the secret digest; never an auth bearer.
    return hmac.new(
        principal.token_digest, b"verith.csrf.v1", hashlib.sha256
    ).hexdigest()


def verify_csrf(
    principal: Principal,
    supplied: str | None,
    origin: str | None,
    allowed_origins: list[str],
) -> None:
    if (
        origin not in allowed_origins
        or not isinstance(supplied, str)
        or not supplied.isascii()
        or not supplied
        or not hmac.compare_digest(supplied, csrf_token(principal))
    ):
        raise AuthenticationRequired()
