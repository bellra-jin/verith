"""One-shot internal fake execution/artifact, without changing receipts or inputs."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c7001a7e0001"
down_revision = "c6001a7e0001"
branch_labels = None
depends_on = None

CHECKS = {
    "version": "contract_version = 1",
    "engine": "engine_id = 'flow.fake.summary.v1'",
    "claim": "octet_length(claim_digest) = 32",
    "time": "isfinite(started_at) AND isfinite(deadline_at) AND deadline_at - started_at = interval '10 seconds'",
    "status": "status IN ('running','succeeded','failed','timed_out')",
    "terminal_time": "finished_at IS NULL OR (isfinite(finished_at) AND finished_at >= started_at)",
    "combination": """(status='running' AND finished_at IS NULL AND result_json IS NULL AND result_sha256 IS NULL AND error_code IS NULL)
        OR (status='succeeded' AND finished_at IS NOT NULL AND finished_at < deadline_at AND result_json IS NOT NULL AND result_sha256 IS NOT NULL AND error_code IS NULL)
        OR (status='failed' AND finished_at IS NOT NULL AND result_json IS NULL AND result_sha256 IS NULL AND error_code IS NOT NULL AND error_code IN ('fake_failed','result_invalid'))
        OR (status='timed_out' AND finished_at IS NOT NULL AND result_json IS NULL AND result_sha256 IS NULL AND error_code IS NOT NULL AND error_code IN ('coroutine_timeout','deadline_expired'))""",
    "result": """result_json IS NULL OR (octet_length(convert_to(result_json,'UTF8')) BETWEEN 1 AND 131072
        AND (jsonb_typeof(result_json::jsonb)='object') IS TRUE
        AND (result_json::jsonb->'contract_version'='1'::jsonb) IS TRUE
        AND (result_json::jsonb->>'mode'='synthetic_only') IS TRUE
        AND (result_json::jsonb->>'execution_id'=id::text) IS TRUE
        AND (result_json::jsonb->>'input_snapshot_id'=input_snapshot_id::text) IS TRUE
        AND result_sha256 ~ '^[0-9a-f]{64}$'
        AND result_sha256=encode(digest(convert_to(result_json,'UTF8'),'sha256'),'hex'))""",
}

def upgrade():
    op.create_table("flow_fake_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("input_snapshot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("flow_input_snapshots.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("contract_version", sa.Integer(), nullable=False), sa.Column("engine_id", sa.Text(), nullable=False),
        sa.Column("claim_digest", sa.LargeBinary(), nullable=False), sa.Column("status", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False), sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)), sa.Column("result_json", sa.Text()),
        sa.Column("result_sha256", sa.String(64)), sa.Column("error_code", sa.Text()),
        sa.UniqueConstraint("input_snapshot_id", name="uq_flow_fake_execution_input"),
        *(sa.CheckConstraint(value, name="ck_flow_fake_"+key) for key,value in CHECKS.items()))
    op.execute("""CREATE FUNCTION cf007_execution_transition() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF TG_OP = 'INSERT' THEN
            IF NEW.status <> 'running' THEN RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='Invalid fake execution insert'; END IF;
            RETURN NEW;
        ELSIF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='Fake execution cannot be deleted';
        END IF;
        IF (NEW.id,NEW.input_snapshot_id,NEW.contract_version,NEW.engine_id,NEW.claim_digest,NEW.started_at,NEW.deadline_at)
            IS DISTINCT FROM (OLD.id,OLD.input_snapshot_id,OLD.contract_version,OLD.engine_id,OLD.claim_digest,OLD.started_at,OLD.deadline_at)
            OR OLD.status <> 'running' OR NEW.status NOT IN ('succeeded','failed','timed_out') THEN
            RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='Invalid fake execution transition';
        END IF;
        IF NEW.status = 'succeeded' AND clock_timestamp() >= NEW.deadline_at THEN
            RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='Fake execution deadline exceeded';
        END IF;
        RETURN NEW;
    END; $$""")
    op.execute("""CREATE TRIGGER cf007_execution_guard BEFORE INSERT OR UPDATE OR DELETE ON flow_fake_executions
        FOR EACH ROW EXECUTE FUNCTION cf007_execution_transition()""")


def downgrade():
    connection = op.get_bind()
    for table in ("flow_runs", "flow_input_snapshots", "flow_fake_executions"):
        connection.execute(sa.text("LOCK TABLE " + table + " IN ACCESS EXCLUSIVE MODE"))
    if connection.scalar(sa.text("SELECT EXISTS(SELECT 1 FROM flow_fake_executions)")):
        raise RuntimeError("Refusing fake execution downgrade: grants exist")
    op.drop_table("flow_fake_executions")
    op.execute("DROP FUNCTION cf007_execution_transition()")
