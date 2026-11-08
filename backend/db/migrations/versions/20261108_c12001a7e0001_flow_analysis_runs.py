"""Add separate live Flow analysis ledger; preserve all earlier histories."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision='c12001a7e0001'
down_revision='c7001a7e0001'
branch_labels=None
depends_on=None
CHECKS={'operation': "operation='flow.analysis.v1'", 'digests': "octet_length(key_digest)=32 AND octet_length(claim_digest)=32 AND input_fingerprint ~ '^[0-9a-f]{64}$'", 'time': "isfinite(started_at) AND isfinite(deadline_at) AND isfinite(as_of) AND deadline_at=started_at+interval '120 seconds' AND (accepted_at IS NULL OR (isfinite(accepted_at) AND accepted_at>=started_at AND accepted_at<deadline_at))", 'spec': "jsonb_typeof(spec_json::jsonb)='object'", 'snapshot': "(input_json IS NULL AND result_json IS NULL) OR (octet_length(convert_to(input_json,'UTF8')) BETWEEN 2 AND 2097152 AND octet_length(convert_to(result_json,'UTF8')) BETWEEN 2 AND 2097152 AND jsonb_typeof(input_json::jsonb)='object' AND jsonb_typeof(result_json::jsonb)='object' AND input_sha256=encode(digest(convert_to(input_json,'UTF8'),'sha256'),'hex') AND result_sha256=encode(digest(convert_to(result_json,'UTF8'),'sha256'),'hex') AND (result_json::jsonb->>'report_id')=adopted_report_id::text)", 'state': "(state='running' AND request_json IS NOT NULL AND stock_name IS NOT NULL AND input_json IS NULL AND result_json IS NULL AND input_sha256 IS NULL AND result_sha256 IS NULL AND adopted_report_id IS NULL AND accepted_at IS NULL AND error_code IS NULL)\n OR (state IN ('failed','unknown') AND request_json IS NOT NULL AND stock_name IS NOT NULL AND input_json IS NULL AND result_json IS NULL AND input_sha256 IS NULL AND result_sha256 IS NULL AND adopted_report_id IS NULL AND accepted_at IS NULL AND error_code IS NOT NULL)\n OR (state IN ('result_ready','stored') AND request_json IS NOT NULL AND stock_name IS NOT NULL AND input_json IS NOT NULL AND result_json IS NOT NULL AND input_sha256 IS NOT NULL AND result_sha256 IS NOT NULL AND adopted_report_id IS NOT NULL AND accepted_at IS NOT NULL AND error_code IS NULL)\n OR (state='failed' AND error_code='RESULT_CONFLICT' AND request_json IS NOT NULL AND stock_name IS NOT NULL AND input_json IS NOT NULL AND result_json IS NOT NULL AND input_sha256 IS NOT NULL AND result_sha256 IS NOT NULL AND adopted_report_id IS NOT NULL AND accepted_at IS NOT NULL)\n OR (state='deleted' AND request_json IS NULL AND stock_name IS NULL AND input_json IS NULL AND result_json IS NULL AND adopted_report_id IS NOT NULL AND input_sha256 IS NOT NULL AND result_sha256 IS NOT NULL AND accepted_at IS NOT NULL AND error_code IS NULL)", 'request': "request_json IS NULL OR (octet_length(convert_to(request_json,'UTF8')) BETWEEN 2 AND 8192 AND jsonb_typeof(request_json::jsonb)='object' AND input_fingerprint=encode(digest(convert_to(request_json,'UTF8'),'sha256'),'hex'))", 'identity': "ticker ~ '^[0-9]{6}$' AND (stock_name IS NULL OR length(btrim(stock_name))>0)"}

def upgrade():
    columns=[sa.Column('id',postgresql.UUID(as_uuid=True),primary_key=True),
        sa.Column('owner_user_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('auth_users.id',ondelete='RESTRICT'),nullable=False)]
    for name in ('operation','input_fingerprint','ticker','spec_json','state'):
        columns.append(sa.Column(name,sa.Text(),nullable=False))
    for name in ('stock_name','request_json','error_code','input_json','input_sha256','result_json','result_sha256'):
        columns.append(sa.Column(name,sa.Text()))
    for name in ('admission_request_id','attempt_id'):
        columns.append(sa.Column(name,postgresql.UUID(as_uuid=True),nullable=False))
    columns.append(sa.Column('adopted_report_id',postgresql.UUID(as_uuid=True)))
    for name in ('key_digest','claim_digest'):
        columns.append(sa.Column(name,sa.LargeBinary(),nullable=False))
    for name in ('as_of','started_at','deadline_at'):
        columns.append(sa.Column(name,sa.DateTime(timezone=True),nullable=False))
    columns.extend([sa.Column('accepted_at',sa.DateTime(timezone=True)),sa.Column('candidate_date',sa.Date(),nullable=False)])
    op.create_table('flow_analysis_runs',*columns,
        sa.UniqueConstraint('owner_user_id','operation','key_digest',name='uq_flow_analysis_owner_operation_key'),
        sa.UniqueConstraint('attempt_id',name='uq_flow_analysis_attempt'),
        sa.UniqueConstraint('adopted_report_id',name='uq_flow_analysis_report'),
        *(sa.CheckConstraint(value,name='ck_flow_analysis_'+key) for key,value in CHECKS.items()))


    op.execute("""CREATE FUNCTION cf012_analysis_transition() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF TG_OP='DELETE' THEN RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='Analysis ledger cannot be deleted'; END IF;
        IF TG_OP='INSERT' THEN
            IF NEW.state<>'running' THEN RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='Invalid initial analysis state'; END IF;
            RETURN NEW;
        END IF;
        IF (NEW.id,NEW.owner_user_id,NEW.operation,NEW.key_digest,NEW.input_fingerprint,
            NEW.admission_request_id,NEW.attempt_id,NEW.ticker,NEW.as_of,NEW.candidate_date,
            NEW.spec_json,NEW.claim_digest,NEW.started_at,NEW.deadline_at)
            IS DISTINCT FROM (OLD.id,OLD.owner_user_id,OLD.operation,OLD.key_digest,OLD.input_fingerprint,
            OLD.admission_request_id,OLD.attempt_id,OLD.ticker,OLD.as_of,OLD.candidate_date,
            OLD.spec_json,OLD.claim_digest,OLD.started_at,OLD.deadline_at) THEN
            RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='Analysis identity is immutable';
        END IF;
        IF NOT ((OLD.state='running' AND NEW.state IN ('result_ready','failed','unknown'))
            OR (OLD.state='result_ready' AND (NEW.state='stored' OR (NEW.state='failed' AND NEW.error_code='RESULT_CONFLICT')))
            OR (OLD.state='stored' AND NEW.state='deleted')) THEN
            RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='Invalid analysis transition';
        END IF;
        IF NEW.state<>'deleted' AND (NEW.request_json,NEW.stock_name) IS DISTINCT FROM (OLD.request_json,OLD.stock_name) THEN
            RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='Analysis request is immutable';
        END IF;
        IF OLD.state='running' AND NEW.state='result_ready' AND clock_timestamp()>=OLD.deadline_at THEN
            RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='Late analysis result';
        END IF;
        IF OLD.state IN ('result_ready','stored') AND
            (NEW.adopted_report_id,NEW.input_sha256,NEW.result_sha256,NEW.accepted_at)
            IS DISTINCT FROM (OLD.adopted_report_id,OLD.input_sha256,OLD.result_sha256,OLD.accepted_at) THEN
            RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='Analysis result reference is immutable';
        END IF;
        IF OLD.state IN ('result_ready','stored') AND NEW.state<>'deleted' AND (NEW.input_json,NEW.result_json) IS DISTINCT FROM (OLD.input_json,OLD.result_json) THEN
            RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='Analysis result is immutable';
        END IF;
        RETURN NEW;
    END; $$""")
    op.execute("CREATE TRIGGER cf012_analysis_guard BEFORE INSERT OR UPDATE OR DELETE ON flow_analysis_runs FOR EACH ROW EXECUTE FUNCTION cf012_analysis_transition()")

def downgrade():
    op.execute('LOCK TABLE flow_analysis_runs IN ACCESS EXCLUSIVE MODE')
    if op.get_bind().execute(sa.text('SELECT EXISTS(SELECT 1 FROM flow_analysis_runs)')).scalar():
        raise RuntimeError('Nonempty live analysis ledger cannot be downgraded')
    op.drop_table('flow_analysis_runs')
    op.execute('DROP FUNCTION cf012_analysis_transition()')
