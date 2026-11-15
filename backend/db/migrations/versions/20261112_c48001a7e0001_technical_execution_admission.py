"""Add dedicated Technical admission/hold tables; no existing data conversion."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
revision = 'c48001a7e0001'
down_revision = 'c45001a7e0001'
branch_labels = None
depends_on = None

PERIOD_CHECKS = {'operation': "operation='technical.analysis.v1'", 'clock': "isfinite(period_start) AND isfinite(period_end) AND period_end=period_start+interval '24 hours' AND (period_start AT TIME ZONE 'Asia/Seoul')::date=kst_date AND (period_start AT TIME ZONE 'Asia/Seoul')::time=time '00:00:00'", 'limits': 'user_request_limit>0 AND request_limit>=user_request_limit AND request_count BETWEEN 0 AND request_limit AND budget_limit_nano>0 AND attempt_reserve_nano>0 AND attempt_reserve_nano<=budget_limit_nano AND reserved_nano BETWEEN 0 AND budget_limit_nano', 'policy': "(octet_length(policy_json) BETWEEN 2 AND 16384 AND jsonb_typeof(policy_json::jsonb)='object' AND policy_sha256 ~ '^[0-9a-f]{64}$' AND policy_sha256=encode(digest(convert_to(policy_json,'UTF8'),'sha256'),'hex') AND policy_json::jsonb->>'operation'=operation AND policy_json::jsonb->>'currency'='USD' AND policy_json::jsonb->>'enabled'='true' AND (policy_json::jsonb->>'user_daily_limit')::bigint=user_request_limit AND (policy_json::jsonb->>'service_daily_limit')::bigint=request_limit AND (policy_json::jsonb->>'daily_budget_nano')::bigint=budget_limit_nano AND (policy_json::jsonb->>'attempt_reserve_nano')::bigint=attempt_reserve_nano AND jsonb_typeof(policy_json::jsonb->'supported_tickers')='array' AND jsonb_array_length(policy_json::jsonb->'supported_tickers')>0) IS TRUE", 'price_caps': "(policy_json::jsonb->>'model' ~ '^[A-Za-z0-9_.:-]{1,128}$' AND policy_json::jsonb->>'service_tier'='default' AND policy_json::jsonb->>'price_id' ~ '^[A-Za-z0-9_.:-]{1,128}$' AND policy_json::jsonb->>'price_evidence_sha256' ~ '^[0-9a-f]{64}$' AND (policy_json::jsonb->>'deadline_seconds')::bigint BETWEEN 1 AND 86400 AND (policy_json::jsonb->>'input_byte_cap')::bigint>0 AND (policy_json::jsonb->>'output_byte_cap')::bigint>0 AND (policy_json::jsonb->>'input_token_cap')::bigint>0 AND (policy_json::jsonb->>'output_token_cap')::bigint>0 AND (policy_json::jsonb->>'input_nano_per_token')::bigint>0 AND (policy_json::jsonb->>'output_nano_per_token')::bigint>0 AND (policy_json::jsonb->>'max_calls')::bigint>0 AND (policy_json::jsonb->>'max_calls')::numeric*((policy_json::jsonb->>'input_token_cap')::numeric*(policy_json::jsonb->>'input_nano_per_token')::numeric+(policy_json::jsonb->>'output_token_cap')::numeric*(policy_json::jsonb->>'output_nano_per_token')::numeric)<=attempt_reserve_nano) IS TRUE"}
PERIOD_CHECKS['integer_policy'] = "(jsonb_typeof(policy_json::jsonb->'enabled')='boolean' AND (jsonb_typeof(policy_json::jsonb->'user_daily_limit')='number' AND policy_json::jsonb->>'user_daily_limit' ~ '^[1-9][0-9]*$') AND (jsonb_typeof(policy_json::jsonb->'service_daily_limit')='number' AND policy_json::jsonb->>'service_daily_limit' ~ '^[1-9][0-9]*$') AND (jsonb_typeof(policy_json::jsonb->'daily_budget_nano')='number' AND policy_json::jsonb->>'daily_budget_nano' ~ '^[1-9][0-9]*$') AND (jsonb_typeof(policy_json::jsonb->'attempt_reserve_nano')='number' AND policy_json::jsonb->>'attempt_reserve_nano' ~ '^[1-9][0-9]*$') AND (jsonb_typeof(policy_json::jsonb->'deadline_seconds')='number' AND policy_json::jsonb->>'deadline_seconds' ~ '^[1-9][0-9]*$') AND (jsonb_typeof(policy_json::jsonb->'input_nano_per_token')='number' AND policy_json::jsonb->>'input_nano_per_token' ~ '^[1-9][0-9]*$') AND (jsonb_typeof(policy_json::jsonb->'output_nano_per_token')='number' AND policy_json::jsonb->>'output_nano_per_token' ~ '^[1-9][0-9]*$') AND (jsonb_typeof(policy_json::jsonb->'input_token_cap')='number' AND policy_json::jsonb->>'input_token_cap' ~ '^[1-9][0-9]*$') AND (jsonb_typeof(policy_json::jsonb->'output_token_cap')='number' AND policy_json::jsonb->>'output_token_cap' ~ '^[1-9][0-9]*$') AND (jsonb_typeof(policy_json::jsonb->'input_byte_cap')='number' AND policy_json::jsonb->>'input_byte_cap' ~ '^[1-9][0-9]*$') AND (jsonb_typeof(policy_json::jsonb->'output_byte_cap')='number' AND policy_json::jsonb->>'output_byte_cap' ~ '^[1-9][0-9]*$') AND (jsonb_typeof(policy_json::jsonb->'max_calls')='number' AND policy_json::jsonb->>'max_calls' ~ '^[1-9][0-9]*$')) IS TRUE"
RUN_CHECKS = {'operation': "operation='technical.analysis.v1'", 'hashes': "octet_length(key_digest)=32 AND octet_length(claim_digest)=32 AND intent_sha256 ~ '^[0-9a-f]{64}$' AND policy_sha256 ~ '^[0-9a-f]{64}$' AND stock_sha256 ~ '^[0-9a-f]{64}$' AND spec_sha256 ~ '^[0-9a-f]{64}$' AND stock_sha256=encode(digest(convert_to(stock_json,'UTF8'),'sha256'),'hex') AND spec_sha256=encode(digest(convert_to(spec_json,'UTF8'),'sha256'),'hex')", 'clock': 'isfinite(as_of) AND isfinite(started_at) AND isfinite(deadline_at) AND as_of=started_at AND deadline_at>started_at AND (claim_consumed_at IS NULL OR (isfinite(claim_consumed_at) AND claim_consumed_at>=started_at AND claim_consumed_at<deadline_at)) AND (redacted_at IS NULL OR (isfinite(redacted_at) AND redacted_at>=started_at))', 'hold': 'reserved_nano>0 AND held_nano=reserved_nano', 'stock': "(ticker ~ '^[0-9]{6}$' AND octet_length(stock_json) BETWEEN 2 AND 4096 AND jsonb_typeof(stock_json::jsonb)='object' AND stock_json::jsonb->>'stock_code'=ticker AND jsonb_typeof(stock_json::jsonb->'stock_name')='string' AND length(btrim(stock_json::jsonb->>'stock_name')) BETWEEN 1 AND 200) IS TRUE", 'spec': "(octet_length(spec_json) BETWEEN 2 AND 4096 AND jsonb_typeof(spec_json::jsonb)='object' AND spec_json::jsonb->>'version'='technical.admission.v1' AND spec_json::jsonb->>'operation'=operation AND spec_json::jsonb->>'boundary'='technical.boundary.v1' AND spec_json::jsonb->>'storage'='technical.owned-stage.v1' AND spec_json::jsonb->'provider_authority'='false'::jsonb AND spec_json::jsonb->'settlement'='false'::jsonb) IS TRUE", 'intent': 'intent_json IS NULL OR (octet_length(intent_json) BETWEEN 2 AND 16384 AND jsonb_typeof(intent_json::jsonb)=\'object\' AND intent_sha256=encode(digest(convert_to(intent_json,\'UTF8\'),\'sha256\'),\'hex\') AND intent_json::jsonb->>\'operation\'=operation AND intent_json::jsonb->>\'ticker\'=ticker AND jsonb_typeof(intent_json::jsonb->\'original_query\')=\'string\' AND length(btrim(intent_json::jsonb->>\'original_query\')) BETWEEN 1 AND 2000 AND intent_json::jsonb->\'requested_views\'=\'["technical"]\'::jsonb AND intent_json::jsonb->\'conditions\'=\'{"profile":"technical.multiframe.v1","periods":["3m","1y","5y"]}\'::jsonb) IS TRUE', 'state': "((state='admitted' AND claim_consumed_at IS NULL AND intent_json IS NOT NULL AND redacted_at IS NULL AND unknown_reason IS NULL) OR (state='claimed' AND claim_consumed_at IS NOT NULL AND intent_json IS NOT NULL AND redacted_at IS NULL AND unknown_reason IS NULL) OR (state='unknown' AND intent_json IS NULL AND redacted_at IS NOT NULL AND unknown_reason IN ('EXPIRED','CANCELLED','TIMEOUT','REDACTED','DISPATCH_UNCERTAIN','STOCK_CHANGED'))) IS TRUE", 'distinct_ids': 'id<>admission_request_id AND id<>attempt_id AND id<>planned_report_id AND id<>boundary_request_id AND id<>trace_id AND admission_request_id<>attempt_id AND admission_request_id<>planned_report_id AND admission_request_id<>boundary_request_id AND admission_request_id<>trace_id AND attempt_id<>planned_report_id AND attempt_id<>boundary_request_id AND attempt_id<>trace_id AND planned_report_id<>boundary_request_id AND planned_report_id<>trace_id AND boundary_request_id<>trace_id', 'nonzero_ids': "id<>'00000000-0000-0000-0000-000000000000'::uuid AND admission_request_id<>'00000000-0000-0000-0000-000000000000'::uuid AND attempt_id<>'00000000-0000-0000-0000-000000000000'::uuid AND planned_report_id<>'00000000-0000-0000-0000-000000000000'::uuid AND boundary_request_id<>'00000000-0000-0000-0000-000000000000'::uuid AND trace_id<>'00000000-0000-0000-0000-000000000000'::uuid"}


PERIOD_GUARD = """
CREATE FUNCTION cf048_period_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP IN ('DELETE','TRUNCATE') THEN
        RAISE EXCEPTION 'CF048 period retained' USING ERRCODE='23514';
    END IF;
    IF TG_OP='INSERT' THEN
        IF NEW.request_count<>0 OR NEW.reserved_nano<>0 OR NEW.blocked THEN
            RAISE EXCEPTION 'CF048 period starts empty' USING ERRCODE='23514';
        END IF;
    ELSE
        IF ROW(NEW.id,NEW.operation,NEW.kst_date,NEW.period_start,NEW.period_end,NEW.policy_json,NEW.policy_sha256,NEW.user_request_limit,NEW.request_limit,NEW.budget_limit_nano,NEW.attempt_reserve_nano)
           IS DISTINCT FROM ROW(OLD.id,OLD.operation,OLD.kst_date,OLD.period_start,OLD.period_end,OLD.policy_json,OLD.policy_sha256,OLD.user_request_limit,OLD.request_limit,OLD.budget_limit_nano,OLD.attempt_reserve_nano)
           OR NEW.request_count<OLD.request_count OR NEW.reserved_nano<OLD.reserved_nano
           OR (OLD.blocked AND NOT NEW.blocked) THEN
            RAISE EXCEPTION 'CF048 immutable period' USING ERRCODE='23514';
        END IF;
    END IF;
    RETURN NEW;
END $$
"""

RUN_GUARD = """
CREATE FUNCTION cf048_run_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE p technical_usage_periods%ROWTYPE;
BEGIN
    IF TG_OP IN ('DELETE','TRUNCATE') THEN
        RAISE EXCEPTION 'CF048 run retained' USING ERRCODE='23514';
    END IF;
    SELECT * INTO p FROM technical_usage_periods WHERE id=NEW.period_id;
    IF NOT FOUND OR NEW.policy_sha256<>p.policy_sha256 OR NEW.reserved_nano<>p.attempt_reserve_nano
       OR NEW.started_at<p.period_start OR NEW.deadline_at>p.period_end
       OR NEW.deadline_at-NEW.started_at>(p.policy_json::jsonb->>'deadline_seconds')::bigint*interval '1 second'
       OR NOT (p.policy_json::jsonb->'supported_tickers' ? NEW.ticker) THEN
        RAISE EXCEPTION 'CF048 run period binding' USING ERRCODE='23514';
    END IF;
    IF TG_OP='INSERT' THEN
        IF NEW.state<>'admitted' OR p.blocked OR NEW.deadline_at<=clock_timestamp()
           OR NOT EXISTS(SELECT 1 FROM auth_sessions s JOIN auth_users u ON u.id=s.user_id
                         WHERE s.id=NEW.admission_session_id AND s.user_id=NEW.owner_user_id
                           AND s.revoked_at IS NULL AND s.expires_at>clock_timestamp() AND u.disabled_at IS NULL)
           OR NOT EXISTS(SELECT 1 FROM stocks s WHERE s.stock_code=NEW.ticker AND s.stock_name=NEW.stock_json::jsonb->>'stock_name') THEN
            RAISE EXCEPTION 'CF048 fresh admission identity' USING ERRCODE='23514';
        END IF;
    ELSE
        IF ROW(NEW.id,NEW.owner_user_id,NEW.admission_session_id,NEW.period_id,NEW.operation,NEW.key_digest,NEW.intent_sha256,NEW.policy_sha256,NEW.spec_json,NEW.spec_sha256,NEW.stock_json,NEW.stock_sha256,NEW.ticker,NEW.admission_request_id,NEW.attempt_id,NEW.planned_report_id,NEW.boundary_request_id,NEW.trace_id,NEW.as_of,NEW.started_at,NEW.deadline_at,NEW.claim_digest,NEW.reserved_nano,NEW.held_nano)
           IS DISTINCT FROM ROW(OLD.id,OLD.owner_user_id,OLD.admission_session_id,OLD.period_id,OLD.operation,OLD.key_digest,OLD.intent_sha256,OLD.policy_sha256,OLD.spec_json,OLD.spec_sha256,OLD.stock_json,OLD.stock_sha256,OLD.ticker,OLD.admission_request_id,OLD.attempt_id,OLD.planned_report_id,OLD.boundary_request_id,OLD.trace_id,OLD.as_of,OLD.started_at,OLD.deadline_at,OLD.claim_digest,OLD.reserved_nano,OLD.held_nano)
           OR (OLD.intent_json IS NULL AND NEW.intent_json IS NOT NULL)
           OR (OLD.intent_json IS NOT NULL AND NEW.intent_json IS NOT NULL AND NEW.intent_json<>OLD.intent_json)
           OR (OLD.claim_consumed_at IS NOT NULL AND NEW.claim_consumed_at IS DISTINCT FROM OLD.claim_consumed_at)
           OR (OLD.redacted_at IS NOT NULL AND NEW.redacted_at IS DISTINCT FROM OLD.redacted_at)
           OR (OLD.state='unknown' AND (NEW.state<>'unknown' OR NEW.unknown_reason IS DISTINCT FROM OLD.unknown_reason))
           OR (OLD.state='claimed' AND NEW.state NOT IN ('claimed','unknown')) THEN
            RAISE EXCEPTION 'CF048 immutable run' USING ERRCODE='23514';
        END IF;
        IF OLD.claim_consumed_at IS NULL AND NEW.claim_consumed_at IS NOT NULL THEN
            IF OLD.state<>'admitted' OR NEW.state<>'claimed' OR p.blocked
               OR NEW.claim_consumed_at>=NEW.deadline_at OR NEW.deadline_at<=clock_timestamp()
               OR NOT EXISTS(SELECT 1 FROM auth_sessions s JOIN auth_users u ON u.id=s.user_id
                             WHERE s.id=NEW.admission_session_id AND s.user_id=NEW.owner_user_id
                               AND s.revoked_at IS NULL AND s.expires_at>clock_timestamp() AND u.disabled_at IS NULL) THEN
                RAISE EXCEPTION 'CF048 claim transition' USING ERRCODE='23514';
            END IF;
        END IF;
    END IF;
    RETURN NEW;
END $$
"""

TOTALS_GUARD = """
CREATE FUNCTION cf048_totals_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE target_id uuid; p technical_usage_periods%ROWTYPE; total_count bigint; total_reserved numeric;
BEGIN
    IF TG_TABLE_NAME='technical_usage_periods' THEN target_id=NEW.id;
    ELSE target_id=NEW.period_id; END IF;
    SELECT * INTO p FROM technical_usage_periods WHERE id=target_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'CF048 period missing' USING ERRCODE='23514'; END IF;
    SELECT count(*),coalesce(sum(reserved_nano),0) INTO total_count,total_reserved
        FROM technical_analysis_runs WHERE period_id=target_id;
    IF total_count<>p.request_count OR total_reserved<>p.reserved_nano
       OR EXISTS(SELECT 1 FROM technical_analysis_runs WHERE period_id=target_id GROUP BY owner_user_id HAVING count(*)>p.user_request_limit) THEN
        RAISE EXCEPTION 'CF048 period totals mismatch' USING ERRCODE='23514';
    END IF;
    RETURN NULL;
END $$
"""


def upgrade():
    op.create_table('technical_usage_periods',
        sa.Column('id',UUID(as_uuid=True),primary_key=True,server_default=sa.text('gen_random_uuid()')),
        sa.Column('operation',sa.Text(),nullable=False),
        sa.Column('kst_date',sa.Date(),nullable=False),
        *(sa.Column(n,sa.DateTime(timezone=True),nullable=False) for n in ('period_start','period_end')),
        *(sa.Column(n,sa.Text(),nullable=False) for n in ('policy_json','policy_sha256')),
        *(sa.Column(n,sa.BigInteger(),nullable=False) for n in ('user_request_limit','request_limit','budget_limit_nano','attempt_reserve_nano','request_count','reserved_nano')),
        sa.Column('blocked',sa.Boolean(),nullable=False),
        sa.UniqueConstraint('operation','kst_date',name='uq_technical_usage_day'),
        sa.UniqueConstraint('id','policy_sha256',name='uq_technical_period_policy'),
        *(sa.CheckConstraint(v,name='cf048_period_'+k) for k,v in PERIOD_CHECKS.items()))
    op.create_table('technical_analysis_runs',
        sa.Column('id',UUID(as_uuid=True),primary_key=True,server_default=sa.text('gen_random_uuid()')),
        sa.Column('owner_user_id',UUID(as_uuid=True),sa.ForeignKey('auth_users.id',ondelete='RESTRICT'),nullable=False),
        *(sa.Column(n,UUID(as_uuid=True),nullable=False) for n in ('admission_session_id','period_id')),
        *(sa.Column(n,sa.Text(),nullable=False) for n in ('operation','intent_sha256','policy_sha256','spec_json','spec_sha256','stock_json','stock_sha256','ticker')),
        sa.Column('intent_json',sa.Text()),
        *(sa.Column(n,sa.LargeBinary(),nullable=False) for n in ('key_digest','claim_digest')),
        *(sa.Column(n,UUID(as_uuid=True),nullable=False,unique=True) for n in ('admission_request_id','attempt_id','planned_report_id','boundary_request_id','trace_id')),
        *(sa.Column(n,sa.DateTime(timezone=True),nullable=False) for n in ('as_of','started_at','deadline_at')),
        *(sa.Column(n,sa.DateTime(timezone=True)) for n in ('claim_consumed_at','redacted_at')),
        *(sa.Column(n,sa.BigInteger(),nullable=False) for n in ('reserved_nano','held_nano')),
        sa.Column('state',sa.Text(),nullable=False),sa.Column('unknown_reason',sa.Text()),
        sa.UniqueConstraint('owner_user_id','operation','key_digest',name='uq_technical_analysis_key'),
        sa.ForeignKeyConstraint(['period_id','policy_sha256'],['technical_usage_periods.id','technical_usage_periods.policy_sha256'],ondelete='RESTRICT',name='fk_technical_run_period_policy'),
        *(sa.CheckConstraint(v,name='cf048_run_'+k) for k,v in RUN_CHECKS.items()))
    op.create_index('ix_technical_run_period_owner','technical_analysis_runs',['period_id','owner_user_id'])
    op.execute(PERIOD_GUARD)
    op.execute(RUN_GUARD)
    op.execute(TOTALS_GUARD)
    for table,function in (('technical_usage_periods','cf048_period_guard'),('technical_analysis_runs','cf048_run_guard')):
        op.execute('CREATE TRIGGER '+function+'_transition BEFORE INSERT OR UPDATE OR DELETE ON '+table+' FOR EACH ROW EXECUTE FUNCTION '+function+'()')
        op.execute('CREATE TRIGGER '+function+'_truncate BEFORE TRUNCATE ON '+table+' FOR EACH STATEMENT EXECUTE FUNCTION '+function+'()')
        op.execute('CREATE CONSTRAINT TRIGGER '+function+'_totals AFTER INSERT OR UPDATE ON '+table+' DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION cf048_totals_guard()')


def downgrade():
    op.execute('LOCK TABLE technical_usage_periods,technical_analysis_runs IN ACCESS EXCLUSIVE MODE')
    if op.get_bind().execute(sa.text('SELECT EXISTS(SELECT 1 FROM technical_usage_periods) OR EXISTS(SELECT 1 FROM technical_analysis_runs)')).scalar():
        raise RuntimeError('Technical admission populated; downgrade denied')
    for table,function in (('technical_usage_periods','cf048_period_guard'),('technical_analysis_runs','cf048_run_guard')):
        for suffix in ('transition','truncate','totals'):
            op.execute('DROP TRIGGER '+function+'_'+suffix+' ON '+table)
    for name in ('cf048_totals_guard','cf048_run_guard','cf048_period_guard'):
        op.execute('DROP FUNCTION '+name+'()')
    op.drop_table('technical_analysis_runs')
    op.drop_table('technical_usage_periods')
