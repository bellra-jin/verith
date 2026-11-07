"""CF-002 provider-independent authentication records; raw bearer tokens are never persisted."""

from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from db.base import Base
from db.models._shared import created_at, uuid_pk


class AuthUser(Base):
    __tablename__ = "auth_users"
    id: Mapped[uuid.UUID] = uuid_pk()
    created_at: Mapped[datetime] = created_at()
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuthIdentity(Base):
    __tablename__ = "auth_identities"
    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth_users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    issuer: Mapped[str] = mapped_column(Text, nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = created_at()
    __table_args__ = (
        UniqueConstraint("issuer", "subject"),
        CheckConstraint(
            "length(issuer) > 0 AND length(subject) > 0",
            name="ck_auth_identity_nonempty",
        ),
        Index("ix_auth_identities_user_id", "user_id"),
    )


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth_users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    token_digest: Mapped[bytes] = mapped_column(
        LargeBinary, nullable=False, unique=True
    )
    created_at: Mapped[datetime] = created_at()
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint(
            "octet_length(token_digest) = 32", name="ck_auth_session_digest_length"
        ),
        CheckConstraint(
            "isfinite(expires_at) AND isfinite(created_at) AND expires_at > created_at",
            name="ck_auth_session_expiry",
        ),
        CheckConstraint(
            "revoked_at IS NULL OR (isfinite(revoked_at) AND revoked_at >= created_at)",
            name="ck_auth_session_revocation",
        ),
        Index("ix_auth_sessions_user_id_expires_at", "user_id", "expires_at"),
        Index("ix_auth_sessions_expires_at", "expires_at"),
    )
