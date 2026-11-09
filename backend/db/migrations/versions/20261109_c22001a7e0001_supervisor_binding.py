"""Confirmed Supervisor binding only; no run/usage backfill."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision='c22001a7e0001'
down_revision='c18001a7e0001'
branch_labels=None
depends_on=None
# Revision-local SQL must not import a mutable application model.
CHECKS={'digests': "octet_length(client_key_digest)=32 AND octet_length(flow_key_digest)=32 AND confirm_digest ~ '^[0-9a-f]{64}$' AND plan_sha256 ~ '^[0-9a-f]{64}$' AND flow_sha256 ~ '^[0-9a-f]{64}$' AND flow_key_digest=digest(convert_to(id::text,'UTF8'),'sha256')", 'clock': "isfinite(confirmed_at) AND isfinite(handoff_before) AND handoff_before=confirmed_at+interval '120 seconds' AND (redacted_at IS NULL OR isfinite(redacted_at) AND redacted_at>=confirmed_at)", 'snapshot': "(redacted_at IS NULL AND plan_json IS NOT NULL AND flow_input_json IS NOT NULL AND octet_length(convert_to(plan_json,'UTF8')) BETWEEN 2 AND 65536 AND octet_length(convert_to(flow_input_json,'UTF8')) BETWEEN 2 AND 8192 AND jsonb_typeof(plan_json::jsonb)='object' AND jsonb_typeof(flow_input_json::jsonb)='object' AND plan_sha256=encode(digest(convert_to(plan_json,'UTF8'),'sha256'),'hex') AND flow_sha256=encode(digest(convert_to(flow_input_json,'UTF8'),'sha256'),'hex') AND flow_input_json::jsonb->>'idempotency_key'=id::text) OR (redacted_at IS NOT NULL AND plan_json IS NULL AND flow_input_json IS NULL)"}

def upgrade():
    op.create_table('supervisor_request_bindings',sa.Column('id',postgresql.UUID(as_uuid=True),primary_key=True),sa.Column('owner_user_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('auth_users.id',ondelete='RESTRICT'),nullable=False),*[sa.Column(n,sa.LargeBinary(),nullable=False) for n in ('client_key_digest','flow_key_digest')],*[sa.Column(n,sa.Text(),nullable=False) for n in ('confirm_digest','plan_sha256','flow_sha256')],sa.Column('plan_json',sa.Text()),sa.Column('flow_input_json',sa.Text()),sa.Column('confirmed_at',sa.DateTime(timezone=True),nullable=False),sa.Column('handoff_before',sa.DateTime(timezone=True),nullable=False),sa.Column('redacted_at',sa.DateTime(timezone=True)),sa.UniqueConstraint('owner_user_id','client_key_digest',name='uq_supervisor_owner_client_key'),*[sa.CheckConstraint(v,name='supervisor_binding_'+k) for k,v in CHECKS.items()])
    op.execute("""CREATE FUNCTION cf022_binding_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
      IF (NEW.id,NEW.owner_user_id,NEW.client_key_digest,NEW.confirm_digest,NEW.plan_sha256,NEW.flow_sha256,NEW.flow_key_digest,NEW.confirmed_at,NEW.handoff_before) IS DISTINCT FROM (OLD.id,OLD.owner_user_id,OLD.client_key_digest,OLD.confirm_digest,OLD.plan_sha256,OLD.flow_sha256,OLD.flow_key_digest,OLD.confirmed_at,OLD.handoff_before) OR OLD.redacted_at IS NOT NULL OR NEW.redacted_at IS NULL OR NEW.plan_json IS NOT NULL OR NEW.flow_input_json IS NOT NULL THEN
        RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Supervisor binding is immutable'; END IF; RETURN NEW; END; $$""")
    op.execute('CREATE TRIGGER cf022_binding_guard BEFORE UPDATE ON supervisor_request_bindings FOR EACH ROW EXECUTE FUNCTION cf022_binding_guard()')
def downgrade():
    op.execute('LOCK TABLE supervisor_request_bindings IN ACCESS EXCLUSIVE MODE')
    if op.get_bind().execute(sa.text('SELECT EXISTS(SELECT 1 FROM supervisor_request_bindings)')).scalar():raise RuntimeError('Nonempty Supervisor binding history cannot be downgraded')
    op.drop_table('supervisor_request_bindings');op.execute('DROP FUNCTION cf022_binding_guard()')
