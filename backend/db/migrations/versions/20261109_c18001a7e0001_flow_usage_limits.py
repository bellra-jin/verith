"""Flow-adopted accounting only; legacy NULL links and all prior data survive."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg
revision='c18001a7e0001'
down_revision='c15001a7e0001'
branch_labels=None
depends_on=None

class NonemptyUsageHistory(RuntimeError):pass

PERIOD_CHECKS = {'scope': "(scope='user' AND owner_user_id IS NOT NULL AND budget_limit_nano IS NULL AND user_request_limit IS NULL) OR (scope='service' AND owner_user_id IS NULL AND budget_limit_nano IS NOT NULL AND budget_limit_nano>0 AND user_request_limit IS NOT NULL AND user_request_limit>0)", 'identity': "operation='flow.analysis.v1' AND currency='USD' AND isfinite(period_start) AND isfinite(period_end) AND period_end=period_start+interval '24 hours' AND (period_start AT TIME ZONE 'Asia/Seoul')::time=time '00:00:00'", 'amounts': 'request_limit>0 AND request_count>=0 AND request_count<=request_limit AND held_nano>=0 AND estimated_spend_nano>=0'}
RESERVATION_CHECKS = {'policy': 'operation=\'flow.analysis.v1\' AND currency=\'USD\' AND price_id=\'openai.gpt-5.4-mini.standard.2026-11-09.v1\' AND max_nano=913500000 AND policy_json::jsonb=\'{"cached_nano": 75, "currency": "USD", "input_nano": 750, "input_token_cap": 400000, "kis_data_cap": 4, "kis_retry_in_data_cap": 2, "kis_token_cap": 2, "model": "gpt-5.4-mini", "n": 1, "openai_call_cap": 3, "output_byte_cap": 16384, "output_nano": 4500, "output_token_cap": 1000, "price_id": "openai.gpt-5.4-mini.standard.2026-11-09.v1", "prompt_byte_cap": 32768, "response_models": ["gpt-5.4-mini", "gpt-5.4-mini-2026-03-17"], "service_tier": "default", "version": "flow.usage.v1"}\'::jsonb', 'amounts': 'remaining_nano>=0 AND remaining_nano<=max_nano AND estimated_spend_nano>=0', 'state': "state IN ('held','unknown','settled','blocked') AND (state<>'settled' OR remaining_nano=0)", 'identity': 'octet_length(claim_digest)=32 AND user_period_id<>service_period_id'}
CALL_CHECKS = {'slot': "(provider='openai' AND action='completion' AND ordinal BETWEEN 1 AND 3 AND reserved_nano=304500000) OR (provider='kis' AND action IN ('token','supply','quotes') AND ordinal BETWEEN 1 AND 2 AND reserved_nano=0)", 'state': "state IN ('unknown','observed','not_called','anomalous') AND (state<>'observed' OR attempted IS TRUE) AND (state<>'not_called' OR attempted IS FALSE)", 'amounts': "released_nano IN (0,reserved_nano) AND (estimated_nano IS NULL OR estimated_nano>=0) AND (provider<>'kis' OR estimated_nano IS NULL)", 'numbers': '(input_tokens IS NULL OR input_tokens>=0) AND (cached_tokens IS NULL OR (input_tokens IS NOT NULL AND cached_tokens>=0 AND cached_tokens<=input_tokens)) AND (output_tokens IS NULL OR output_tokens>=0) AND (input_bytes IS NULL OR input_bytes>=0) AND (output_bytes IS NULL OR output_bytes>=0) AND (http_status IS NULL OR http_status BETWEEN 100 AND 599)', 'model': "response_model IS NULL OR response_model IN ('gpt-5.4-mini','gpt-5.4-mini-2026-03-17')", 'digests': "(evidence_sha256 IS NULL OR evidence_sha256 ~ '^[0-9a-f]{64}$') AND (model_sha256 IS NULL OR model_sha256 ~ '^[0-9a-f]{64}$')", 'reason': "reason IN ('UNOBSERVED','NOT_CALLED','HTTP_OBSERVED','USAGE_OBSERVED','CACHE_UNREPORTED','USAGE_INVALID','MODEL_MISMATCH','CAP_EXCEEDED','PRICE_MISMATCH','ACCOUNTING_OVERFLOW')"}


def upgrade():
    op.add_column('flow_analysis_runs',sa.Column('budget_reservation_id',pg.UUID(as_uuid=True),nullable=True))
    op.create_check_constraint('ck_flow_analysis_budget_id','flow_analysis_runs','budget_reservation_id IS NULL OR budget_reservation_id=id')
    op.create_unique_constraint('uq_flow_analysis_budget','flow_analysis_runs',['budget_reservation_id'])
    op.create_unique_constraint('uq_flow_analysis_budget_identity','flow_analysis_runs',['id','owner_user_id','operation','attempt_id','claim_digest'])
    op.create_table('analysis_usage_periods',
        sa.Column('id',pg.UUID(as_uuid=True),primary_key=True),sa.Column('scope',sa.Text(),nullable=False),
        sa.Column('owner_user_id',pg.UUID(as_uuid=True),sa.ForeignKey('auth_users.id',ondelete='RESTRICT')),
        sa.Column('operation',sa.Text(),nullable=False),sa.Column('currency',sa.String(3),nullable=False),
        sa.Column('period_start',sa.DateTime(timezone=True),nullable=False),sa.Column('period_end',sa.DateTime(timezone=True),nullable=False),
        sa.Column('request_limit',sa.BigInteger(),nullable=False),sa.Column('budget_limit_nano',sa.BigInteger()),
        sa.Column('user_request_limit',sa.BigInteger()),sa.Column('request_count',sa.BigInteger(),nullable=False),sa.Column('held_nano',sa.BigInteger(),nullable=False),
        sa.Column('estimated_spend_nano',sa.BigInteger(),nullable=False),sa.Column('blocked',sa.Boolean(),nullable=False),
        *(sa.CheckConstraint(v,name='ck_usage_period_'+k) for k,v in PERIOD_CHECKS.items()))
    op.create_index('uq_usage_service_period','analysis_usage_periods',['operation','currency','period_start','period_end'],unique=True,postgresql_where=sa.text("scope='service'"))
    op.create_index('uq_usage_user_period','analysis_usage_periods',['owner_user_id','operation','currency','period_start','period_end'],unique=True,postgresql_where=sa.text("scope='user'"))
    op.create_table('analysis_usage_reservations',
        sa.Column('id',pg.UUID(as_uuid=True),primary_key=True),sa.Column('owner_user_id',pg.UUID(as_uuid=True),nullable=False),
        sa.Column('operation',sa.Text(),nullable=False),sa.Column('attempt_id',pg.UUID(as_uuid=True),nullable=False),
        sa.Column('claim_digest',sa.LargeBinary(),nullable=False),
        sa.Column('user_period_id',pg.UUID(as_uuid=True),sa.ForeignKey('analysis_usage_periods.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('service_period_id',pg.UUID(as_uuid=True),sa.ForeignKey('analysis_usage_periods.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('currency',sa.String(3),nullable=False),sa.Column('price_id',sa.Text(),nullable=False),sa.Column('policy_json',sa.Text(),nullable=False),
        sa.Column('max_nano',sa.BigInteger(),nullable=False),sa.Column('remaining_nano',sa.BigInteger(),nullable=False),
        sa.Column('estimated_spend_nano',sa.BigInteger(),nullable=False),sa.Column('state',sa.Text(),nullable=False),
        sa.UniqueConstraint('id','owner_user_id','operation','attempt_id','claim_digest',name='uq_usage_reservation_identity'),
        sa.UniqueConstraint('attempt_id',name='uq_usage_reservation_attempt'),
        sa.ForeignKeyConstraint(['id','owner_user_id','operation','attempt_id','claim_digest'],
            ['flow_analysis_runs.id','flow_analysis_runs.owner_user_id','flow_analysis_runs.operation','flow_analysis_runs.attempt_id','flow_analysis_runs.claim_digest'],
            name='fk_usage_reservation_run',deferrable=True,initially='DEFERRED'),
        *(sa.CheckConstraint(v,name='ck_usage_reservation_'+k) for k,v in RESERVATION_CHECKS.items()))
    op.create_foreign_key('fk_flow_analysis_budget','flow_analysis_runs','analysis_usage_reservations',
        ['budget_reservation_id','owner_user_id','operation','attempt_id','claim_digest'],['id','owner_user_id','operation','attempt_id','claim_digest'],deferrable=True,initially='DEFERRED')
    op.create_table('analysis_provider_calls',
        sa.Column('id',pg.UUID(as_uuid=True),primary_key=True),
        sa.Column('reservation_id',pg.UUID(as_uuid=True),sa.ForeignKey('analysis_usage_reservations.id',ondelete='RESTRICT'),nullable=False),
        *(sa.Column(n,sa.Text(),nullable=False) for n in ('provider','action')),
        *(sa.Column(n,sa.BigInteger(),nullable=False) for n in ('ordinal','reserved_nano','released_nano')),
        sa.Column('attempted',sa.Boolean()),sa.Column('state',sa.Text(),nullable=False),
        *(sa.Column(n,sa.BigInteger()) for n in ('input_tokens','cached_tokens','output_tokens','input_bytes','output_bytes','http_status','estimated_nano')),
        sa.Column('response_model',sa.Text()),sa.Column('model_sha256',sa.String(64)),
        sa.Column('reason',sa.Text(),nullable=False),sa.Column('evidence_sha256',sa.String(64)),
        sa.UniqueConstraint('reservation_id','provider','action','ordinal',name='uq_usage_call_slot'),
        *(sa.CheckConstraint(v,name='ck_usage_call_'+k) for k,v in CALL_CHECKS.items()))
    op.execute("""CREATE FUNCTION cf018_usage_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF TG_OP='DELETE' THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Accounting history cannot be deleted'; END IF;
        IF TG_TABLE_NAME='flow_analysis_runs' THEN
            IF TG_OP='INSERT' AND NEW.budget_reservation_id IS NULL THEN
                RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='New Flow execution requires reservation';
            END IF;
            IF TG_OP='UPDATE' AND NEW.budget_reservation_id IS DISTINCT FROM OLD.budget_reservation_id THEN
                RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Reservation reference is immutable';
            END IF;
        ELSIF TG_TABLE_NAME='analysis_usage_periods' AND TG_OP='UPDATE' THEN
            IF (NEW.id,NEW.scope,NEW.owner_user_id,NEW.operation,NEW.currency,NEW.period_start,NEW.period_end,NEW.request_limit,NEW.budget_limit_nano,NEW.user_request_limit)
                IS DISTINCT FROM (OLD.id,OLD.scope,OLD.owner_user_id,OLD.operation,OLD.currency,OLD.period_start,OLD.period_end,OLD.request_limit,OLD.budget_limit_nano,OLD.user_request_limit)
                OR NEW.request_count<OLD.request_count OR NEW.estimated_spend_nano<OLD.estimated_spend_nano OR (OLD.blocked AND NOT NEW.blocked) THEN
                RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Period identity and limits are immutable';
            END IF;
        ELSIF TG_TABLE_NAME='analysis_usage_reservations' AND TG_OP='UPDATE' THEN
            IF (NEW.id,NEW.owner_user_id,NEW.operation,NEW.attempt_id,NEW.claim_digest,NEW.user_period_id,NEW.service_period_id,NEW.currency,NEW.price_id,NEW.policy_json,NEW.max_nano)
                IS DISTINCT FROM (OLD.id,OLD.owner_user_id,OLD.operation,OLD.attempt_id,OLD.claim_digest,OLD.user_period_id,OLD.service_period_id,OLD.currency,OLD.price_id,OLD.policy_json,OLD.max_nano)
                OR NEW.remaining_nano>OLD.remaining_nano OR NEW.estimated_spend_nano<OLD.estimated_spend_nano OR (OLD.state='blocked' AND NEW.state<>'blocked') THEN
                RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Reservation identity is immutable';
            END IF;
        ELSIF TG_TABLE_NAME='analysis_provider_calls' AND TG_OP='UPDATE' THEN
            IF (NEW.id,NEW.reservation_id,NEW.provider,NEW.action,NEW.ordinal,NEW.reserved_nano)
                IS DISTINCT FROM (OLD.id,OLD.reservation_id,OLD.provider,OLD.action,OLD.ordinal,OLD.reserved_nano)
                OR NEW.released_nano<OLD.released_nano
                OR (OLD.attempted IS TRUE AND NEW.attempted IS DISTINCT FROM TRUE)
                OR (OLD.state IN ('observed','not_called','anomalous') AND NEW IS DISTINCT FROM OLD) THEN
                RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Confirmed provider evidence is immutable';
            END IF;
        END IF;
        RETURN NEW;
    END; $$""")
    for table in ('flow_analysis_runs','analysis_usage_periods','analysis_usage_reservations','analysis_provider_calls'):
        op.execute('CREATE TRIGGER cf018_guard BEFORE INSERT OR UPDATE OR DELETE ON '+table+' FOR EACH ROW EXECUTE FUNCTION cf018_usage_guard()')
    op.execute("""CREATE FUNCTION cf018_usage_links() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE r analysis_usage_reservations; f flow_analysis_runs; u analysis_usage_periods; s analysis_usage_periods;
    BEGIN
        IF TG_TABLE_NAME='flow_analysis_runs' THEN
            IF NEW.budget_reservation_id IS NULL THEN RETURN NULL; END IF;
            SELECT * INTO r FROM analysis_usage_reservations WHERE id=NEW.budget_reservation_id;
            IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Missing usage reservation'; END IF;
        ELSE r:=NEW; END IF;
        SELECT * INTO f FROM flow_analysis_runs WHERE id=r.id;
        IF NOT FOUND OR f.budget_reservation_id IS DISTINCT FROM r.id THEN
            RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Reservation requires linked run';
        END IF;
        SELECT * INTO u FROM analysis_usage_periods WHERE id=r.user_period_id;
        SELECT * INTO s FROM analysis_usage_periods WHERE id=r.service_period_id;
        IF u.id IS NULL OR s.id IS NULL OR u.scope<>'user' OR s.scope<>'service'
            OR u.owner_user_id IS DISTINCT FROM r.owner_user_id OR s.owner_user_id IS NOT NULL
            OR u.operation<>r.operation OR s.operation<>r.operation OR u.currency<>'USD' OR s.currency<>'USD'
            OR u.period_start<>s.period_start OR u.period_end<>s.period_end
            OR f.started_at<u.period_start OR f.started_at>=u.period_end THEN
            RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Reservation period relationship invalid';
        END IF;
        RETURN NULL;
    END; $$""")
    for table in ('flow_analysis_runs','analysis_usage_reservations'):
        op.execute('CREATE CONSTRAINT TRIGGER cf018_links AFTER INSERT OR UPDATE ON '+table+' DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION cf018_usage_links()')
    op.execute("""CREATE FUNCTION cf018_call_identity() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE attempt uuid; hash bytea; expected uuid;
    BEGIN
        SELECT attempt_id INTO attempt FROM analysis_usage_reservations WHERE id=NEW.reservation_id;
        hash:=digest(uuid_send('c18001a7-e000-5000-8000-000000000001'::uuid)||convert_to(NEW.reservation_id::text||':'||attempt::text||':'||NEW.provider||':'||NEW.action||':'||NEW.ordinal::text,'UTF8'),'sha1');
        hash:=set_byte(set_byte(substring(hash FROM 1 FOR 16),6,(get_byte(hash,6)&15)|80),8,(get_byte(hash,8)&63)|128);
        expected:=encode(hash,'hex')::uuid;
        IF expected IS NULL OR NEW.id IS DISTINCT FROM expected THEN
            RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Provider call identity invalid';
        END IF;
        RETURN NEW;
    END; $$""")
    op.execute('CREATE TRIGGER cf018_call_id BEFORE INSERT ON analysis_provider_calls FOR EACH ROW EXECUTE FUNCTION cf018_call_identity()')


def downgrade():
    op.execute('LOCK TABLE flow_analysis_runs,analysis_usage_periods,analysis_usage_reservations,analysis_provider_calls IN ACCESS EXCLUSIVE MODE')
    if op.get_bind().execute(sa.text('SELECT EXISTS(SELECT 1 FROM analysis_usage_periods) OR EXISTS(SELECT 1 FROM analysis_usage_reservations) OR EXISTS(SELECT 1 FROM analysis_provider_calls)')).scalar():
        raise NonemptyUsageHistory('Nonempty accounting history cannot be downgraded')
    op.execute('DROP TRIGGER cf018_links ON flow_analysis_runs')
    op.execute('DROP TRIGGER cf018_guard ON flow_analysis_runs')
    op.drop_constraint('fk_flow_analysis_budget','flow_analysis_runs',type_='foreignkey')
    op.drop_table('analysis_provider_calls')
    op.drop_table('analysis_usage_reservations')
    op.drop_table('analysis_usage_periods')
    op.drop_constraint('uq_flow_analysis_budget','flow_analysis_runs',type_='unique')
    op.drop_constraint('uq_flow_analysis_budget_identity','flow_analysis_runs',type_='unique')
    op.drop_constraint('ck_flow_analysis_budget_id','flow_analysis_runs',type_='check')
    op.drop_column('flow_analysis_runs','budget_reservation_id')
    for name in ('cf018_call_identity','cf018_usage_links','cf018_usage_guard'):op.execute('DROP FUNCTION '+name+'()')
