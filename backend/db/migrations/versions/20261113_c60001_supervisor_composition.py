"""Immutable two-child composition journal; no child execution or new budget ledger."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg
revision='c60001a7e0001'
down_revision='c54001a7e0001'
branch_labels=None
depends_on=None
CHECKS = {'digests': '(octet_length(client_key_digest)=32 AND octet_length(claim_digest)=32 AND '
            "confirm_digest ~ '^[0-9a-f]{64}$' AND snapshot_sha256 ~ '^[0-9a-f]{64}$') IS TRUE",
 'snapshot': "((snapshot_json IS NULL AND state='redacted') OR (snapshot_json IS NOT NULL AND "
             "state<>'redacted' AND octet_length(convert_to(snapshot_json,'UTF8')) BETWEEN 2 AND "
             '65536 AND '
             "snapshot_sha256=encode(digest(convert_to(snapshot_json,'UTF8'),'sha256'),'hex') AND "
             'snapshot_json=cf053_canonical(snapshot_json::jsonb))) IS TRUE',
 'clock': '(isfinite(request_started_at) AND isfinite(confirmed_at) AND '
          'confirmed_at>=request_started_at AND confirmed_at<admission_before AND '
          "admission_before=request_started_at+interval '15 seconds' AND "
          "deadline_at=request_started_at+interval '140 seconds' AND (claimed_at IS NULL OR "
          'isfinite(claimed_at)) AND (closed_at IS NULL OR isfinite(closed_at)) AND '
          '(analysis_as_of IS NULL OR (isfinite(analysis_as_of) AND analysis_as_of>=confirmed_at '
          'AND analysis_as_of<deadline_at))) IS TRUE',
 'state': "((state='admitted' AND claimed_at IS NULL AND closed_at IS NULL) OR (state='claimed' "
          'AND claimed_at>=confirmed_at AND claimed_at<deadline_at AND closed_at IS NULL) OR '
          "(state='closed' AND closed_at>=confirmed_at AND (claimed_at IS NULL OR "
          "(claimed_at>=confirmed_at AND claimed_at<deadline_at))) OR (state='redacted' AND "
          'closed_at>=confirmed_at)) IS TRUE',
 'flow': '((flow_handoff_at IS NULL AND flow_run_id IS NULL) OR (flow_handoff_at>=claimed_at AND '
         'flow_handoff_at<deadline_at AND claimed_at IS NOT NULL AND analysis_as_of IS NOT NULL)) '
         'IS TRUE',
 'technical': '((technical_handoff_at IS NULL AND technical_run_id IS NULL) OR '
              '(technical_handoff_at>=claimed_at AND technical_handoff_at<deadline_at AND '
              'claimed_at IS NOT NULL)) IS TRUE'}
GUARD = """CREATE OR REPLACE FUNCTION c60001_child_key(parent uuid, view_name text, identity_seed bytea) RETURNS uuid
LANGUAGE sql IMMUTABLE STRICT SET search_path=pg_catalog,public AS $$
 SELECT (substr(h,1,8)||'-'||substr(h,9,4)||'-5'||substr(h,14,3)||'-'||
         substr('89ab',((get_byte(decode(h,'hex'),8)>>4)&3)+1,1)||substr(h,18,3)||'-'||substr(h,21,12))::uuid
 FROM (SELECT encode(digest(uuid_send(parent)||convert_to('supervisor.composition.v1:'||view_name||':'||encode(identity_seed,'hex'),'UTF8'),'sha1'),'hex') h) s
$$;
CREATE OR REPLACE FUNCTION c60001_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE snapshot jsonb; views jsonb; auth_owner uuid; valid_session boolean; native record;
BEGIN
 IF TG_OP='DELETE' OR TG_OP='TRUNCATE' THEN
  RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Composition history retained';
 END IF;
 IF TG_OP='INSERT' THEN
  IF NEW.state<>'admitted' OR NEW.claimed_at IS NOT NULL OR NEW.closed_at IS NOT NULL
     OR NEW.flow_handoff_at IS NOT NULL OR NEW.technical_handoff_at IS NOT NULL
     OR NEW.flow_run_id IS NOT NULL OR NEW.technical_run_id IS NOT NULL
     OR clock_timestamp()>=NEW.admission_before OR clock_timestamp()<NEW.confirmed_at THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Composition admission invalid';
  END IF;
  SELECT user_id INTO auth_owner FROM auth_sessions WHERE id=NEW.confirmation_session_id AND revoked_at IS NULL AND clock_timestamp()<expires_at;
  IF auth_owner IS DISTINCT FROM NEW.owner_user_id THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Composition session owner invalid';
  END IF;
 ELSE
  IF (NEW.id,NEW.owner_user_id,NEW.confirmation_session_id,NEW.client_key_digest,NEW.confirm_digest,
      NEW.snapshot_sha256,NEW.claim_digest,NEW.request_started_at,NEW.confirmed_at,NEW.admission_before,
      NEW.deadline_at,NEW.flow_key_digest,NEW.technical_key_digest)
     IS DISTINCT FROM
     (OLD.id,OLD.owner_user_id,OLD.confirmation_session_id,OLD.client_key_digest,OLD.confirm_digest,
      OLD.snapshot_sha256,OLD.claim_digest,OLD.request_started_at,OLD.confirmed_at,OLD.admission_before,
      OLD.deadline_at,OLD.flow_key_digest,OLD.technical_key_digest) THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Composition identity immutable';
  END IF;
  IF OLD.state IN ('closed','redacted') AND (NEW.state<>'redacted' OR OLD.state='redacted')
     OR OLD.state='claimed' AND NEW.state NOT IN ('claimed','closed','redacted')
     OR OLD.state='admitted' AND NEW.state NOT IN ('admitted','claimed','closed','redacted') THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Composition transition invalid';
  END IF;
  IF NEW.snapshot_json IS DISTINCT FROM OLD.snapshot_json AND
     (NEW.state<>'redacted' OR NEW.snapshot_json IS NOT NULL OR OLD.snapshot_json IS NULL) THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Composition scope immutable';
  END IF;
  IF NEW.state='redacted' AND
     (NEW.claimed_at,NEW.analysis_as_of,NEW.flow_handoff_at,NEW.technical_handoff_at,NEW.flow_run_id,NEW.technical_run_id)
      IS DISTINCT FROM
     (OLD.claimed_at,OLD.analysis_as_of,OLD.flow_handoff_at,OLD.technical_handoff_at,OLD.flow_run_id,OLD.technical_run_id) THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Composition redaction invalid';
  END IF;
  IF OLD.claimed_at IS NOT NULL AND NEW.claimed_at IS DISTINCT FROM OLD.claimed_at
     OR OLD.closed_at IS NOT NULL AND NEW.closed_at IS DISTINCT FROM OLD.closed_at
     OR OLD.analysis_as_of IS NOT NULL AND NEW.analysis_as_of IS DISTINCT FROM OLD.analysis_as_of
     OR OLD.flow_handoff_at IS NOT NULL AND NEW.flow_handoff_at IS DISTINCT FROM OLD.flow_handoff_at
     OR OLD.technical_handoff_at IS NOT NULL AND NEW.technical_handoff_at IS DISTINCT FROM OLD.technical_handoff_at
     OR OLD.flow_run_id IS NOT NULL AND NEW.flow_run_id IS DISTINCT FROM OLD.flow_run_id
     OR OLD.technical_run_id IS NOT NULL AND NEW.technical_run_id IS DISTINCT FROM OLD.technical_run_id THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Composition consumption immutable';
  END IF;
  IF NEW.claimed_at IS DISTINCT FROM OLD.claimed_at OR NEW.flow_handoff_at IS DISTINCT FROM OLD.flow_handoff_at
     OR NEW.technical_handoff_at IS DISTINCT FROM OLD.technical_handoff_at
     OR NEW.flow_run_id IS DISTINCT FROM OLD.flow_run_id OR NEW.technical_run_id IS DISTINCT FROM OLD.technical_run_id THEN
   SELECT user_id=NEW.owner_user_id AND revoked_at IS NULL AND clock_timestamp()<expires_at
    INTO valid_session FROM auth_sessions WHERE id=NEW.confirmation_session_id;
   IF valid_session IS NOT TRUE OR NEW.state<>'claimed' OR clock_timestamp()>=NEW.deadline_at THEN
    RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Composition start unavailable';
   END IF;
  END IF;
  IF ((OLD.claimed_at IS NULL AND NEW.claimed_at IS NOT NULL) OR NEW.technical_run_id IS DISTINCT FROM OLD.technical_run_id) AND clock_timestamp()>=NEW.admission_before THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Composition admission window expired';
  END IF;
  IF (NEW.flow_handoff_at IS DISTINCT FROM OLD.flow_handoff_at OR NEW.technical_handoff_at IS DISTINCT FROM OLD.technical_handoff_at) AND clock_timestamp()>=NEW.admission_before THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Composition admission window expired';
  END IF;
 END IF;
 IF NEW.snapshot_json IS NOT NULL THEN
  snapshot=NEW.snapshot_json::jsonb;views=snapshot->'selected_views';
  IF (snapshot->>'schema_version'='supervisor.composition.v1'
      AND views IN ('["flow"]'::jsonb,'["technical"]'::jsonb,'["flow","technical"]'::jsonb)
      AND jsonb_typeof(snapshot->'stock')='object' AND snapshot->'frame'->'conditions'='[]'::jsonb
      AND snapshot->'frame'->'unresolved_slots'='[]'::jsonb) IS NOT TRUE THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Composition scope invalid';
  END IF;
  IF ((CASE WHEN views ? 'flow' THEN NEW.flow_key_digest=digest(convert_to(c60001_child_key(NEW.id,'flow',NEW.claim_digest)::text,'UTF8'),'sha256')
           ELSE NEW.flow_key_digest IS NULL AND NEW.flow_handoff_at IS NULL AND NEW.flow_run_id IS NULL END)
      AND (CASE WHEN views ? 'technical' THEN NEW.technical_key_digest=digest(convert_to(c60001_child_key(NEW.id,'technical',NEW.claim_digest)::text,'UTF8'),'sha256')
           ELSE NEW.technical_key_digest IS NULL AND NEW.technical_handoff_at IS NULL AND NEW.technical_run_id IS NULL END)) IS NOT TRUE THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Composition child identity invalid';
  END IF;
  IF views ? 'technical' THEN
   IF NEW.analysis_as_of IS NOT NULL AND NEW.technical_run_id IS NULL THEN
    RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Composition analysis clock unbound';
   END IF;
   IF NEW.flow_handoff_at IS NOT NULL AND (NEW.technical_run_id IS NULL OR NEW.analysis_as_of IS NULL) THEN
    RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Composition analysis clock unavailable';
   END IF;
  ELSIF NEW.analysis_as_of IS DISTINCT FROM NEW.confirmed_at THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Composition analysis clock invalid';
  END IF;
  IF NEW.technical_run_id IS NOT NULL AND (TG_OP='INSERT' OR NEW.technical_run_id IS DISTINCT FROM OLD.technical_run_id) THEN
   SELECT * INTO native FROM technical_analysis_runs WHERE id=NEW.technical_run_id;
   IF NOT FOUND OR (native.owner_user_id=NEW.owner_user_id AND native.key_digest=NEW.technical_key_digest
      AND native.admission_session_id=NEW.confirmation_session_id
      AND native.ticker=snapshot->'stock'->>'stock_code' AND native.as_of=NEW.analysis_as_of
      AND native.started_at>=NEW.technical_handoff_at AND native.started_at<NEW.admission_before AND native.deadline_at<=NEW.deadline_at
      AND native.stock_json::jsonb=snapshot->'stock'
      AND native.execution_configuration_json=snapshot->>'technical_configuration') IS NOT TRUE THEN
    RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Composition Technical reference invalid';
   END IF;
  END IF;
  IF NEW.flow_run_id IS NOT NULL AND (TG_OP='INSERT' OR NEW.flow_run_id IS DISTINCT FROM OLD.flow_run_id) THEN
   SELECT * INTO native FROM flow_analysis_runs WHERE id=NEW.flow_run_id;
   IF NOT FOUND OR (native.owner_user_id=NEW.owner_user_id AND native.key_digest=NEW.flow_key_digest
      AND native.budget_reservation_id=native.id AND native.operation='flow.analysis.v1' AND native.ticker=snapshot->'stock'->>'stock_code'
      AND native.as_of=NEW.analysis_as_of AND native.started_at>=NEW.flow_handoff_at
      AND native.started_at<NEW.admission_before AND native.deadline_at<=NEW.deadline_at
      AND native.stock_name=snapshot->'stock'->>'stock_name'
      AND EXISTS(SELECT 1 FROM analysis_usage_reservations r
        JOIN analysis_usage_periods u ON u.id=r.user_period_id
        JOIN analysis_usage_periods v ON v.id=r.service_period_id
        WHERE r.id=native.id AND u.request_limit=(snapshot->'flow_policy'->>'user_limit')::bigint
        AND v.request_limit=(snapshot->'flow_policy'->>'service_limit')::bigint
        AND v.user_request_limit=(snapshot->'flow_policy'->>'user_limit')::bigint
        AND v.budget_limit_nano=(snapshot->'flow_policy'->>'budget')::bigint)) IS NOT TRUE THEN
    RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Composition Flow reference invalid';
   END IF;
  END IF;
 END IF;
 RETURN NEW;
END;$$;
"""

def upgrade():
    # asyncpg prepares one statement per execute; keep each fixed function DDL
    # separate within the caller's single attested migration transaction.
    for sql in GUARD.split('CREATE OR REPLACE FUNCTION ')[1:]:
        op.execute('CREATE OR REPLACE FUNCTION '+sql)
    op.create_table('supervisor_compositions',
        sa.Column('id',pg.UUID(as_uuid=True),nullable=False,primary_key=True),
        sa.Column('owner_user_id',pg.UUID(as_uuid=True),nullable=False),
        sa.Column('confirmation_session_id',pg.UUID(as_uuid=True),nullable=False),
        sa.Column('flow_run_id',pg.UUID(as_uuid=True),nullable=True),
        sa.Column('technical_run_id',pg.UUID(as_uuid=True),nullable=True),
        sa.Column('client_key_digest',sa.LargeBinary(),nullable=False),
        sa.Column('claim_digest',sa.LargeBinary(),nullable=False),
        sa.Column('flow_key_digest',sa.LargeBinary(),nullable=True),
        sa.Column('technical_key_digest',sa.LargeBinary(),nullable=True),
        sa.Column('confirm_digest',sa.Text(),nullable=False),
        sa.Column('snapshot_json',sa.Text(),nullable=True),
        sa.Column('snapshot_sha256',sa.Text(),nullable=False),
        sa.Column('state',sa.Text(),nullable=False),
        sa.Column('request_started_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('confirmed_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('admission_before',sa.DateTime(timezone=True),nullable=False),
        sa.Column('deadline_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('analysis_as_of',sa.DateTime(timezone=True),nullable=True),
        sa.Column('claimed_at',sa.DateTime(timezone=True),nullable=True),
        sa.Column('closed_at',sa.DateTime(timezone=True),nullable=True),
        sa.Column('flow_handoff_at',sa.DateTime(timezone=True),nullable=True),
        sa.Column('technical_handoff_at',sa.DateTime(timezone=True),nullable=True),
        sa.ForeignKeyConstraint(['owner_user_id'],['auth_users.id'],ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['confirmation_session_id'],['auth_sessions.id'],ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['flow_run_id'],['flow_analysis_runs.id'],ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['technical_run_id'],['technical_analysis_runs.id'],ondelete='RESTRICT'),
        sa.UniqueConstraint('owner_user_id','client_key_digest',name='uq_composition_owner_key'),
        *[sa.CheckConstraint(v,name='composition_'+k) for k,v in CHECKS.items()])
    op.execute('CREATE TRIGGER c60001_guard BEFORE INSERT OR UPDATE OR DELETE ON supervisor_compositions FOR EACH ROW EXECUTE FUNCTION c60001_guard()')
    op.execute('CREATE TRIGGER c60001_truncate BEFORE TRUNCATE ON supervisor_compositions FOR EACH STATEMENT EXECUTE FUNCTION c60001_guard()')

def downgrade():
    op.execute('LOCK TABLE supervisor_compositions IN ACCESS EXCLUSIVE MODE')
    if op.get_bind().execute(sa.text('SELECT EXISTS(SELECT 1 FROM supervisor_compositions)')).scalar():
        raise RuntimeError('Composition history retained')
    op.drop_table('supervisor_compositions')
    op.execute('DROP FUNCTION c60001_guard()')
    op.execute('DROP FUNCTION c60001_child_key(uuid,text,bytea)')
