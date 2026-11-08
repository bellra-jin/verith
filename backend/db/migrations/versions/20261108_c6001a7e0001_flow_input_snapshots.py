"""Immutable, non-executable synthetic input snapshots. No existing row rewrites."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c6001a7e0001"
down_revision = "c3001a7e0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint("uq_flow_runs_id_owner", "flow_runs", ["id", "owner_user_id"])
    op.create_table(
        "flow_input_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contract_version", sa.Integer(), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("input_json", sa.Text(), nullable=False),
        sa.Column("input_sha256", sa.String(64), nullable=False),
        sa.Column("sealed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("run_id", name="uq_flow_input_snapshots_run"),
        sa.ForeignKeyConstraint(["run_id", "owner_user_id"], ["flow_runs.id", "flow_runs.owner_user_id"], ondelete="RESTRICT", name="fk_flow_input_snapshot_owner_run"),
        sa.CheckConstraint("contract_version = 1", name="ck_flow_input_snapshot_version"),
        sa.CheckConstraint("mode = 'synthetic_only'", name="ck_flow_input_snapshot_mode"),
        sa.CheckConstraint("isfinite(sealed_at)", name="ck_flow_input_snapshot_time"),
        sa.CheckConstraint("octet_length(convert_to(input_json,'UTF8')) BETWEEN 1 AND 131072", name="ck_flow_input_snapshot_size"),
        sa.CheckConstraint("(jsonb_typeof(input_json::jsonb) = 'object') IS TRUE", name="ck_flow_input_snapshot_object"),
        sa.CheckConstraint("(input_json::jsonb -> 'contract_version' = '1'::jsonb) IS TRUE", name="ck_flow_input_snapshot_body_version"),
        sa.CheckConstraint("(input_json::jsonb ->> 'mode' = 'synthetic_only') IS TRUE", name="ck_flow_input_snapshot_body_mode"),
        sa.CheckConstraint("input_sha256 ~ '^[0-9a-f]{64}$' AND input_sha256 = encode(digest(convert_to(input_json,'UTF8'),'sha256'),'hex')", name="ck_flow_input_snapshot_digest"),
    )
    op.execute("""CREATE FUNCTION cf006_reject_snapshot_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'Flow input snapshot is immutable'; END; $$""")
    op.execute("""CREATE TRIGGER cf006_snapshot_immutable BEFORE UPDATE OR DELETE ON flow_input_snapshots
        FOR EACH ROW EXECUTE FUNCTION cf006_reject_snapshot_mutation()""")


def downgrade():
    connection = op.get_bind()
    connection.execute(sa.text("LOCK TABLE flow_runs IN ACCESS EXCLUSIVE MODE"))
    connection.execute(sa.text("LOCK TABLE flow_input_snapshots IN ACCESS EXCLUSIVE MODE"))
    if connection.scalar(sa.text("SELECT EXISTS(SELECT 1 FROM flow_input_snapshots)")):
        raise RuntimeError("Refusing input snapshot downgrade: sealed inputs exist")
    op.drop_table("flow_input_snapshots")
    op.execute("DROP FUNCTION cf006_reject_snapshot_mutation()")
    op.drop_constraint("uq_flow_runs_id_owner", "flow_runs", type_="unique")
