"""Receipt-only Flow admission. Existing reports/authentication are untouched."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c3001a7e0001"
down_revision = "c2001a7e0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "flow_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("auth_users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("operation", sa.Text(), nullable=False),
        sa.Column("request_contract_version", sa.Integer(), nullable=False),
        sa.Column("idempotency_key_digest", sa.LargeBinary(), nullable=False),
        sa.Column("input_fingerprint", sa.String(64), nullable=False),
        sa.Column("request_input", postgresql.JSONB(), nullable=False),
        sa.Column("admission_request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attempt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("admission_mode", sa.Text(), nullable=False),
        sa.Column("execution_status", sa.Text(), nullable=False),
        sa.Column("storage_status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("owner_user_id", "operation", "idempotency_key_digest", name="uq_flow_runs_owner_operation_key"),
        sa.UniqueConstraint("attempt_id", name="uq_flow_runs_attempt_id"),
        sa.CheckConstraint("operation = 'flow'", name="ck_flow_run_operation"),
        sa.CheckConstraint("request_contract_version = 1", name="ck_flow_run_version"),
        sa.CheckConstraint("octet_length(idempotency_key_digest) = 32", name="ck_flow_run_key_digest"),
        sa.CheckConstraint("input_fingerprint ~ '^[0-9a-f]{64}$'", name="ck_flow_run_fingerprint"),
        sa.CheckConstraint("jsonb_typeof(request_input) = 'object'", name="ck_flow_run_input_object"),
        sa.CheckConstraint("admission_mode = 'receipt_only'", name="ck_flow_run_receipt_only"),
        sa.CheckConstraint("execution_status = 'pending'", name="ck_flow_run_pending"),
        sa.CheckConstraint("storage_status = 'not_stored'", name="ck_flow_run_not_stored"),
        sa.CheckConstraint("isfinite(created_at)", name="ck_flow_run_created_at"),
    )


def downgrade():
    connection = op.get_bind()
    # Keep the emptiness check and DROP atomic against concurrent admissions.
    connection.execute(sa.text("LOCK TABLE flow_runs IN ACCESS EXCLUSIVE MODE"))
    if connection.scalar(sa.text("SELECT EXISTS(SELECT 1 FROM flow_runs)")):
        raise RuntimeError("Refusing Flow admission downgrade: receipts exist")
    op.drop_table("flow_runs")
