"""Add revocable authentication and nullable Flow ownership, preserving legacy rows.
Revision ID: c2001a7e0001
Revises: b1e9d4a7c2f1
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c2001a7e0001"
down_revision = "b1e9d4a7c2f1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "auth_users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("disabled_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "auth_identities",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("auth_users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("issuer", sa.Text(), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("issuer", "subject"),
        sa.CheckConstraint(
            "length(issuer) > 0 AND length(subject) > 0",
            name="ck_auth_identity_nonempty",
        ),
    )
    op.create_index("ix_auth_identities_user_id", "auth_identities", ["user_id"])
    op.create_table(
        "auth_sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("auth_users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("token_digest", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("token_digest"),
        sa.CheckConstraint(
            "octet_length(token_digest) = 32", name="ck_auth_session_digest_length"
        ),
        sa.CheckConstraint(
            "isfinite(expires_at) AND isfinite(created_at) AND expires_at > created_at",
            name="ck_auth_session_expiry",
        ),
        sa.CheckConstraint(
            "revoked_at IS NULL OR (isfinite(revoked_at) AND revoked_at >= created_at)",
            name="ck_auth_session_revocation",
        ),
    )
    op.create_index(
        "ix_auth_sessions_user_id_expires_at",
        "auth_sessions",
        ["user_id", "expires_at"],
    )
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"])
    op.add_column(
        "flow_reports",
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_flow_reports_owner_user_id_auth_users",
        "flow_reports",
        "auth_users",
        ["owner_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_flow_reports_owner_created_id",
        "flow_reports",
        ["owner_user_id", sa.text("created_at DESC"), sa.text("id DESC")],
    )
    op.create_index(
        "ix_agent_reports_type_owner_created_id",
        "agent_reports",
        ["agent_type", "owner_user_id", sa.text("created_at DESC"), sa.text("id DESC")],
    )


def downgrade():
    connection = op.get_bind()
    if connection.scalar(
        sa.text(
            "SELECT EXISTS(SELECT 1 FROM auth_users) OR EXISTS(SELECT 1 FROM auth_identities) OR EXISTS(SELECT 1 FROM auth_sessions) OR EXISTS(SELECT 1 FROM flow_reports WHERE owner_user_id IS NOT NULL)"
        )
    ):
        raise RuntimeError(
            "Refusing destructive auth downgrade: new authentication/ownership data exists"
        )
    op.drop_index("ix_agent_reports_type_owner_created_id", table_name="agent_reports")
    op.drop_index("ix_flow_reports_owner_created_id", table_name="flow_reports")
    op.drop_constraint(
        "fk_flow_reports_owner_user_id_auth_users", "flow_reports", type_="foreignkey"
    )
    op.drop_column("flow_reports", "owner_user_id")
    op.drop_table("auth_sessions")
    op.drop_table("auth_identities")
    op.drop_table("auth_users")
