"""Add same-run Technical completion snapshots; existing admission IDs/hold stay fixed."""
from alembic import op
import sqlalchemy as sa

revision='c50001a7e0001'
down_revision='c48001a7e0001'
branch_labels=None
depends_on=None

OLD_STATE_CHECK = "((state='admitted' AND claim_consumed_at IS NULL AND intent_json IS NOT NULL AND redacted_at IS NULL AND unknown_reason IS NULL) OR (state='claimed' AND claim_consumed_at IS NOT NULL AND intent_json IS NOT NULL AND redacted_at IS NULL AND unknown_reason IS NULL) OR (state='unknown' AND intent_json IS NULL AND redacted_at IS NOT NULL AND unknown_reason IN ('EXPIRED','CANCELLED','TIMEOUT','REDACTED','DISPATCH_UNCERTAIN','STOCK_CHANGED'))) IS TRUE"
STATE_CHECK = "(((state IN ('admitted','claimed','result_ready') AND intent_json IS NOT NULL AND redacted_at IS NULL AND unknown_reason IS NULL)\n OR (state IN ('stored','failed') AND intent_json IS NULL AND redacted_at IS NOT NULL AND unknown_reason IS NULL)\n OR (state='unknown' AND intent_json IS NULL AND redacted_at IS NOT NULL AND unknown_reason IN ('EXPIRED','CANCELLED','TIMEOUT','REDACTED','DISPATCH_UNCERTAIN','STOCK_CHANGED')))\n AND ((state='admitted' AND claim_consumed_at IS NULL) OR (state IN ('claimed','result_ready','stored','failed') AND claim_consumed_at IS NOT NULL) OR state='unknown') IS TRUE) IS TRUE"
COMPLETION_CHECKS = {'metadata': "((accepted_at IS NULL AND completion_format IS NULL AND input_sha256 IS NULL AND result_sha256 IS NULL AND binding_sha256 IS NULL AND state IN ('admitted','claimed','unknown','failed'))\n OR (isfinite(accepted_at) AND accepted_at>=claim_consumed_at AND accepted_at<deadline_at AND completion_format='technical.result-completion.v1'\n AND input_sha256 ~ '^[0-9a-f]{64}$' AND result_sha256 ~ '^[0-9a-f]{64}$' AND binding_sha256 ~ '^[0-9a-f]{64}$' AND state IN ('result_ready','stored','failed','unknown')\n AND (redacted_at IS NULL OR redacted_at>=accepted_at))) IS TRUE", 'text': "((state='result_ready' AND input_json IS NOT NULL AND result_json IS NOT NULL)\n OR (state<>'result_ready' AND input_json IS NULL AND result_json IS NULL)) IS TRUE\n AND (input_json IS NULL OR (octet_length(input_json) BETWEEN 2 AND 16384 AND jsonb_typeof(input_json::jsonb)='object' AND input_sha256=encode(digest(convert_to(input_json,'UTF8'),'sha256'),'hex'))) IS TRUE\n AND (result_json IS NULL OR (octet_length(result_json) BETWEEN 2 AND 2097152 AND jsonb_typeof(result_json::jsonb)='object' AND result_sha256=encode(digest(convert_to(result_json,'UTF8'),'sha256'),'hex'))) IS TRUE", 'error': "((state='failed' AND error_code IN ('RESULT_CONTRACT_INVALID','RESULT_CONFLICT')) OR (state<>'failed' AND error_code IS NULL)) IS TRUE"}
OLD_RUN_GUARD = "\nCREATE FUNCTION cf048_run_guard() RETURNS trigger LANGUAGE plpgsql AS $$\nDECLARE p technical_usage_periods%ROWTYPE;\nBEGIN\n    IF TG_OP IN ('DELETE','TRUNCATE') THEN\n        RAISE EXCEPTION 'CF048 run retained' USING ERRCODE='23514';\n    END IF;\n    SELECT * INTO p FROM technical_usage_periods WHERE id=NEW.period_id;\n    IF NOT FOUND OR NEW.policy_sha256<>p.policy_sha256 OR NEW.reserved_nano<>p.attempt_reserve_nano\n       OR NEW.started_at<p.period_start OR NEW.deadline_at>p.period_end\n       OR NEW.deadline_at-NEW.started_at>(p.policy_json::jsonb->>'deadline_seconds')::bigint*interval '1 second'\n       OR NOT (p.policy_json::jsonb->'supported_tickers' ? NEW.ticker) THEN\n        RAISE EXCEPTION 'CF048 run period binding' USING ERRCODE='23514';\n    END IF;\n    IF TG_OP='INSERT' THEN\n        IF NEW.state<>'admitted' OR p.blocked OR NEW.deadline_at<=clock_timestamp()\n           OR NOT EXISTS(SELECT 1 FROM auth_sessions s JOIN auth_users u ON u.id=s.user_id\n                         WHERE s.id=NEW.admission_session_id AND s.user_id=NEW.owner_user_id\n                           AND s.revoked_at IS NULL AND s.expires_at>clock_timestamp() AND u.disabled_at IS NULL)\n           OR NOT EXISTS(SELECT 1 FROM stocks s WHERE s.stock_code=NEW.ticker AND s.stock_name=NEW.stock_json::jsonb->>'stock_name') THEN\n            RAISE EXCEPTION 'CF048 fresh admission identity' USING ERRCODE='23514';\n        END IF;\n    ELSE\n        IF ROW(NEW.id,NEW.owner_user_id,NEW.admission_session_id,NEW.period_id,NEW.operation,NEW.key_digest,NEW.intent_sha256,NEW.policy_sha256,NEW.spec_json,NEW.spec_sha256,NEW.stock_json,NEW.stock_sha256,NEW.ticker,NEW.admission_request_id,NEW.attempt_id,NEW.planned_report_id,NEW.boundary_request_id,NEW.trace_id,NEW.as_of,NEW.started_at,NEW.deadline_at,NEW.claim_digest,NEW.reserved_nano,NEW.held_nano)\n           IS DISTINCT FROM ROW(OLD.id,OLD.owner_user_id,OLD.admission_session_id,OLD.period_id,OLD.operation,OLD.key_digest,OLD.intent_sha256,OLD.policy_sha256,OLD.spec_json,OLD.spec_sha256,OLD.stock_json,OLD.stock_sha256,OLD.ticker,OLD.admission_request_id,OLD.attempt_id,OLD.planned_report_id,OLD.boundary_request_id,OLD.trace_id,OLD.as_of,OLD.started_at,OLD.deadline_at,OLD.claim_digest,OLD.reserved_nano,OLD.held_nano)\n           OR (OLD.intent_json IS NULL AND NEW.intent_json IS NOT NULL)\n           OR (OLD.intent_json IS NOT NULL AND NEW.intent_json IS NOT NULL AND NEW.intent_json<>OLD.intent_json)\n           OR (OLD.claim_consumed_at IS NOT NULL AND NEW.claim_consumed_at IS DISTINCT FROM OLD.claim_consumed_at)\n           OR (OLD.redacted_at IS NOT NULL AND NEW.redacted_at IS DISTINCT FROM OLD.redacted_at)\n           OR (OLD.state='unknown' AND (NEW.state<>'unknown' OR NEW.unknown_reason IS DISTINCT FROM OLD.unknown_reason))\n           OR (OLD.state='claimed' AND NEW.state NOT IN ('claimed','unknown')) THEN\n            RAISE EXCEPTION 'CF048 immutable run' USING ERRCODE='23514';\n        END IF;\n        IF OLD.claim_consumed_at IS NULL AND NEW.claim_consumed_at IS NOT NULL THEN\n            IF OLD.state<>'admitted' OR NEW.state<>'claimed' OR p.blocked\n               OR NEW.claim_consumed_at>=NEW.deadline_at OR NEW.deadline_at<=clock_timestamp()\n               OR NOT EXISTS(SELECT 1 FROM auth_sessions s JOIN auth_users u ON u.id=s.user_id\n                             WHERE s.id=NEW.admission_session_id AND s.user_id=NEW.owner_user_id\n                               AND s.revoked_at IS NULL AND s.expires_at>clock_timestamp() AND u.disabled_at IS NULL) THEN\n                RAISE EXCEPTION 'CF048 claim transition' USING ERRCODE='23514';\n            END IF;\n        END IF;\n    END IF;\n    RETURN NEW;\nEND $$\n"
EXTENDED_RUN_GUARD = "\nCREATE OR REPLACE FUNCTION cf048_run_guard() RETURNS trigger LANGUAGE plpgsql AS $$\nDECLARE p technical_usage_periods%ROWTYPE;\nBEGIN\n    IF TG_OP IN ('DELETE','TRUNCATE') THEN\n        RAISE EXCEPTION 'CF048 run retained' USING ERRCODE='23514';\n    END IF;\n    SELECT * INTO p FROM technical_usage_periods WHERE id=NEW.period_id;\n    IF NOT FOUND OR NEW.policy_sha256<>p.policy_sha256 OR NEW.reserved_nano<>p.attempt_reserve_nano\n       OR NEW.started_at<p.period_start OR NEW.deadline_at>p.period_end\n       OR NEW.deadline_at-NEW.started_at>(p.policy_json::jsonb->>'deadline_seconds')::bigint*interval '1 second'\n       OR NOT (p.policy_json::jsonb->'supported_tickers' ? NEW.ticker) THEN\n        RAISE EXCEPTION 'CF048 run period binding' USING ERRCODE='23514';\n    END IF;\n    IF TG_OP='INSERT' THEN\n        IF NEW.state<>'admitted' OR p.blocked OR NEW.deadline_at<=clock_timestamp()\n           OR NOT EXISTS(SELECT 1 FROM auth_sessions s JOIN auth_users u ON u.id=s.user_id\n                         WHERE s.id=NEW.admission_session_id AND s.user_id=NEW.owner_user_id\n                           AND s.revoked_at IS NULL AND s.expires_at>clock_timestamp() AND u.disabled_at IS NULL)\n           OR NOT EXISTS(SELECT 1 FROM stocks s WHERE s.stock_code=NEW.ticker AND s.stock_name=NEW.stock_json::jsonb->>'stock_name') THEN\n            RAISE EXCEPTION 'CF048 fresh admission identity' USING ERRCODE='23514';\n        END IF;\n    ELSE\n        IF ROW(NEW.id,NEW.owner_user_id,NEW.admission_session_id,NEW.period_id,NEW.operation,NEW.key_digest,NEW.intent_sha256,NEW.policy_sha256,NEW.spec_json,NEW.spec_sha256,NEW.stock_json,NEW.stock_sha256,NEW.ticker,NEW.admission_request_id,NEW.attempt_id,NEW.planned_report_id,NEW.boundary_request_id,NEW.trace_id,NEW.as_of,NEW.started_at,NEW.deadline_at,NEW.claim_digest,NEW.reserved_nano,NEW.held_nano)\n           IS DISTINCT FROM ROW(OLD.id,OLD.owner_user_id,OLD.admission_session_id,OLD.period_id,OLD.operation,OLD.key_digest,OLD.intent_sha256,OLD.policy_sha256,OLD.spec_json,OLD.spec_sha256,OLD.stock_json,OLD.stock_sha256,OLD.ticker,OLD.admission_request_id,OLD.attempt_id,OLD.planned_report_id,OLD.boundary_request_id,OLD.trace_id,OLD.as_of,OLD.started_at,OLD.deadline_at,OLD.claim_digest,OLD.reserved_nano,OLD.held_nano)\n           OR (OLD.intent_json IS NULL AND NEW.intent_json IS NOT NULL)\n           OR (OLD.intent_json IS NOT NULL AND NEW.intent_json IS NOT NULL AND NEW.intent_json<>OLD.intent_json)\n           OR (OLD.claim_consumed_at IS NOT NULL AND NEW.claim_consumed_at IS DISTINCT FROM OLD.claim_consumed_at)\n           OR (OLD.redacted_at IS NOT NULL AND NEW.redacted_at IS DISTINCT FROM OLD.redacted_at)\n           OR (OLD.state='unknown' AND (NEW.state<>'unknown' OR NEW.unknown_reason IS DISTINCT FROM OLD.unknown_reason))\n           OR (OLD.state='claimed' AND NEW.state NOT IN ('claimed','unknown','result_ready','stored','failed')) THEN\n            RAISE EXCEPTION 'CF048 immutable run' USING ERRCODE='23514';\n        END IF;\n        IF OLD.claim_consumed_at IS NULL AND NEW.claim_consumed_at IS NOT NULL THEN\n            IF OLD.state<>'admitted' OR NEW.state<>'claimed' OR p.blocked\n               OR NEW.claim_consumed_at>=NEW.deadline_at OR NEW.deadline_at<=clock_timestamp()\n               OR NOT EXISTS(SELECT 1 FROM auth_sessions s JOIN auth_users u ON u.id=s.user_id\n                             WHERE s.id=NEW.admission_session_id AND s.user_id=NEW.owner_user_id\n                               AND s.revoked_at IS NULL AND s.expires_at>clock_timestamp() AND u.disabled_at IS NULL) THEN\n                RAISE EXCEPTION 'CF048 claim transition' USING ERRCODE='23514';\n            END IF;\n        END IF;\n    END IF;\n    RETURN NEW;\nEND $$\n"


ISO_FUNCTION = """
CREATE FUNCTION cf050_iso(stamp timestamptz) RETURNS text LANGUAGE sql IMMUTABLE STRICT AS $$
 SELECT CASE WHEN extract(microseconds FROM stamp)::bigint % 1000000=0
 THEN to_char(stamp AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS')
 ELSE to_char(stamp AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US') END || '+00:00'
$$
"""
CONTEXT_FUNCTION = """
CREATE FUNCTION cf050_context(r technical_analysis_runs, operation text, fingerprint text)
 RETURNS text LANGUAGE sql IMMUTABLE STRICT AS $$
 SELECT '{"admission_request_id":"'||r.admission_request_id::text||'","analysis_id":"'||r.id::text||
 '","as_of":"'||cf050_iso(r.as_of)||'","attempt_id":"'||r.attempt_id::text||
 '","deadline_at":"'||cf050_iso(r.deadline_at)||'","input_fingerprint":"'||fingerprint||
 '","operation":"'||operation||'","owner_user_id":"'||r.owner_user_id::text||'"}'
$$
"""
BINDING_FUNCTION = """
CREATE FUNCTION cf050_binding(r technical_analysis_runs, input_text text, result_hash text)
 RETURNS text LANGUAGE plpgsql IMMUTABLE STRICT AS $$
DECLARE caller text; context text;
BEGIN
 caller='{"boundary_request":'||input_text||',"operation":"technical.owned-stage.v1"}';
 context=cf050_context(r,'technical.owned-stage.v1',encode(digest(convert_to(caller,'UTF8'),'sha256'),'hex'));
 RETURN encode(digest(convert_to('{"context":'||context||',"input_schema":"analysis.agent.v1","input_sha256":"'||
 encode(digest(convert_to(input_text,'UTF8'),'sha256'),'hex')||'","report_id":"'||r.planned_report_id::text||
 '","result_schema":"technical.boundary.v1","result_sha256":"'||result_hash||'"}','UTF8'),'sha256'),'hex');
END $$
"""
COMPLETION_GUARD = """
CREATE FUNCTION cf050_completion_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE d jsonb; result jsonb; semantic text; b_hash text;
BEGIN
 IF TG_OP='INSERT' THEN
  IF ROW(NEW.completion_format,NEW.input_json,NEW.input_sha256,NEW.result_json,NEW.result_sha256,NEW.binding_sha256,NEW.accepted_at,NEW.error_code)
     IS DISTINCT FROM ROW(NULL::text,NULL::text,NULL::text,NULL::text,NULL::text,NULL::text,NULL::timestamptz,NULL::text) THEN
   RAISE EXCEPTION 'CF050 completion starts empty' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
 END IF;
 IF (OLD.state IN ('stored','failed','unknown') AND NEW.state<>OLD.state)
 OR (OLD.state='admitted' AND NEW.state NOT IN ('admitted','claimed','unknown'))
 OR (OLD.state='claimed' AND NEW.state NOT IN ('claimed','result_ready','failed','unknown'))
 OR (OLD.state='result_ready' AND NEW.state NOT IN ('result_ready','stored','failed','unknown')) THEN
  RAISE EXCEPTION 'CF050 terminal transition' USING ERRCODE='23514';
 END IF;
 IF OLD.accepted_at IS NOT NULL AND
  ROW(NEW.completion_format,NEW.input_sha256,NEW.result_sha256,NEW.binding_sha256,NEW.accepted_at)
  IS DISTINCT FROM ROW(OLD.completion_format,OLD.input_sha256,OLD.result_sha256,OLD.binding_sha256,OLD.accepted_at) THEN
  RAISE EXCEPTION 'CF050 accepted identity immutable' USING ERRCODE='23514';
 END IF;
 IF OLD.accepted_at IS NOT NULL AND
 ((OLD.input_json IS NULL AND NEW.input_json IS NOT NULL) OR (OLD.result_json IS NULL AND NEW.result_json IS NOT NULL)
  OR (OLD.input_json IS NOT NULL AND NEW.input_json IS NOT NULL AND OLD.input_json<>NEW.input_json)
  OR (OLD.result_json IS NOT NULL AND NEW.result_json IS NOT NULL AND OLD.result_json<>NEW.result_json)) THEN
  RAISE EXCEPTION 'CF050 snapshot immutable' USING ERRCODE='23514';
 END IF;
 IF OLD.state='failed' AND NEW.error_code IS DISTINCT FROM OLD.error_code THEN
  RAISE EXCEPTION 'CF050 failure immutable' USING ERRCODE='23514';
 END IF;
 IF OLD.accepted_at IS NULL AND NEW.accepted_at IS NOT NULL THEN
  IF OLD.state<>'claimed' OR NEW.state<>'result_ready' OR OLD.claim_consumed_at IS NULL
    OR clock_timestamp()>=OLD.deadline_at OR NEW.accepted_at>clock_timestamp()
    OR NOT EXISTS(SELECT 1 FROM auth_sessions s JOIN auth_users u ON u.id=s.user_id
      WHERE s.id=OLD.admission_session_id AND s.user_id=OLD.owner_user_id AND s.revoked_at IS NULL
       AND s.expires_at>clock_timestamp() AND u.disabled_at IS NULL)
    OR EXISTS(SELECT 1 FROM technical_usage_periods p WHERE p.id=OLD.period_id AND p.blocked)
    OR NOT EXISTS(SELECT 1 FROM stocks s WHERE s.stock_code=OLD.ticker AND
       jsonb_build_object('stock_code',s.stock_code,'stock_name',s.stock_name,'market',s.market)=OLD.stock_json::jsonb) THEN
   RAISE EXCEPTION 'CF050 receive fence' USING ERRCODE='23514';
  END IF;
  d=NEW.input_json::jsonb->'data';result=NEW.result_json::jsonb;
  semantic='{"conditions":{"periods":["3m","1y","5y"],"profile":"technical.multiframe.v1"},"operation":"technical.boundary.v1","original_query":'||
    (d->'original_query')::text||',"requested_as_of":'||(d->'requested_as_of')::text||',"stock":'||OLD.stock_json||'}';
  b_hash=encode(digest(convert_to(semantic,'UTF8'),'sha256'),'hex');
  IF (NEW.input_json::jsonb->>'schema_version'='analysis.agent.v1'
   AND NEW.input_json::jsonb->>'request_id'=OLD.boundary_request_id::text AND NEW.input_json::jsonb->>'trace_id'=OLD.trace_id::text
   AND d->>'operation'='technical.boundary.v1' AND d->'stock'=OLD.stock_json::jsonb
   AND d->>'original_query'=OLD.intent_json::jsonb->>'original_query' AND d->'conditions'=OLD.intent_json::jsonb->'conditions'
   AND d->'requested_views'='["technical"]'::jsonb AND d->>'requested_as_of'=cf050_iso(OLD.as_of)
   AND d->'context'=jsonb_build_object('analysis_id',OLD.id::text,'admission_request_id',OLD.admission_request_id::text,
    'attempt_id',OLD.attempt_id::text,'report_id',OLD.planned_report_id::text,'input_fingerprint',b_hash)
   AND result->>'schema_version'='analysis.agent.v1' AND result->>'request_id'=OLD.boundary_request_id::text
   AND result->>'trace_id'=OLD.trace_id::text AND result->'error'='null'::jsonb
   AND result->'data'->'request_snapshot'=d AND result->'data'->>'request_sha256'=NEW.input_sha256
   AND NEW.binding_sha256=cf050_binding(OLD,NEW.input_json,NEW.result_sha256)) IS NOT TRUE THEN
   RAISE EXCEPTION 'CF050 independent input/result binding' USING ERRCODE='23514';
  END IF;
 ELSIF OLD.accepted_at IS NULL AND
  ROW(NEW.completion_format,NEW.input_json,NEW.input_sha256,NEW.result_json,NEW.result_sha256,NEW.binding_sha256)
  IS DISTINCT FROM ROW(OLD.completion_format,OLD.input_json,OLD.input_sha256,OLD.result_json,OLD.result_sha256,OLD.binding_sha256) THEN
  RAISE EXCEPTION 'CF050 no snapshot without acceptance' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$
"""
STORED_ASSERT = """
CREATE FUNCTION cf050_assert_stored(report uuid) RETURNS void LANGUAGE plpgsql AS $$
DECLARE r technical_analysis_runs%ROWTYPE; root technical_reports%ROWTYPE;
 snap technical_report_snapshots%ROWTYPE; idx agent_reports%ROWTYPE; caller text;
BEGIN
 -- Also serialize changes against an in-flight ready publisher. Deferred report
 -- changes cannot pass while its period/run transaction is still uncommitted.
 FOR r IN SELECT * FROM technical_analysis_runs WHERE planned_report_id=report LOOP
  PERFORM 1 FROM technical_usage_periods WHERE id=r.period_id FOR UPDATE;
  SELECT * INTO r FROM technical_analysis_runs WHERE id=r.id FOR UPDATE;
  IF r.state<>'stored' THEN CONTINUE; END IF;
  SELECT * INTO root FROM technical_reports WHERE id=report;
  IF NOT FOUND THEN RAISE EXCEPTION 'CF050 stored root missing' USING ERRCODE='23514'; END IF;
  SELECT * INTO snap FROM technical_report_snapshots WHERE report_id=report;
  IF NOT FOUND THEN RAISE EXCEPTION 'CF050 stored snapshot missing' USING ERRCODE='23514'; END IF;
  IF (SELECT count(*) FROM agent_reports WHERE agent_type='technical' AND agent_report_id=report)<>1 THEN
   RAISE EXCEPTION 'CF050 exact stored index required' USING ERRCODE='23514';
  END IF;
  SELECT * INTO idx FROM agent_reports WHERE agent_type='technical' AND agent_report_id=report;
  caller='{"boundary_request":'||snap.input_json||',"operation":"technical.owned-stage.v1"}';
  IF (root.owner_user_id=r.owner_user_id AND snap.owner_user_id=r.owner_user_id AND idx.owner_user_id=r.owner_user_id
   AND snap.request_id=r.boundary_request_id AND snap.trace_id=r.trace_id AND snap.input_sha256=r.input_sha256
   AND snap.result_sha256=r.result_sha256 AND snap.binding_sha256=r.binding_sha256
   AND snap.binding_sha256=cf050_binding(r,snap.input_json,snap.result_sha256)
   AND snap.owner_session_id=idx.owner_session_id AND snap.created_at=idx.created_at
   AND snap.caller_input_json=caller
   AND snap.caller_context_json=cf050_context(r,'technical.owned-stage.v1',encode(digest(convert_to(caller,'UTF8'),'sha256'),'hex'))
   AND snap.boundary_context_json=cf050_context(r,'technical.boundary.v1',snap.input_json::jsonb->'data'->'context'->>'input_fingerprint')
   AND root.request_id=r.boundary_request_id::text AND root.trace_id=r.trace_id::text AND root.as_of=r.as_of
   AND root.stock_code=r.ticker AND root.ticker=r.ticker AND root.stock_name=r.stock_json::jsonb->>'stock_name'
   AND root.input_payload=snap.input_json::jsonb AND root.output_payload=snap.result_json::jsonb
   AND idx.request_id=r.boundary_request_id::text AND idx.trace_id=r.trace_id::text AND idx.as_of=r.as_of
   AND idx.stock_code=r.ticker AND idx.stock_name=r.stock_json::jsonb->>'stock_name'
   AND idx.question=snap.input_json::jsonb->'data'->>'original_query'
   AND idx.data_status=snap.result_json::jsonb->'data'->'result'->>'data_status'
   AND idx.answer_text=snap.result_json::jsonb->'data'->'result'->'interpretation'->>'text') IS NOT TRUE THEN
   RAISE EXCEPTION 'CF050 stored owner/hash/session binding' USING ERRCODE='23514';
  END IF;
 END LOOP;
END $$
"""
LINK_GUARD = """
CREATE FUNCTION cf050_link_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE previous_report uuid;
BEGIN
 IF TG_TABLE_NAME='technical_analysis_runs' THEN
  PERFORM cf050_assert_stored(NEW.planned_report_id);
 ELSIF TG_TABLE_NAME='technical_reports' THEN
  IF TG_OP<>'INSERT' THEN PERFORM cf050_assert_stored(OLD.id); END IF;
  IF TG_OP<>'DELETE' THEN PERFORM cf050_assert_stored(NEW.id); END IF;
 ELSIF TG_TABLE_NAME='technical_report_snapshots' THEN
  IF TG_OP<>'INSERT' THEN PERFORM cf050_assert_stored(OLD.report_id); END IF;
  IF TG_OP<>'DELETE' THEN PERFORM cf050_assert_stored(NEW.report_id); END IF;
 ELSE
  IF TG_OP<>'INSERT' AND OLD.agent_type='technical' THEN PERFORM cf050_assert_stored(OLD.agent_report_id); END IF;
  IF TG_OP<>'DELETE' AND NEW.agent_type='technical' THEN PERFORM cf050_assert_stored(NEW.agent_report_id); END IF;
 END IF;
 IF TG_TABLE_NAME<>'technical_analysis_runs' AND TG_OP<>'INSERT' THEN
  IF TG_TABLE_NAME='technical_reports' THEN previous_report=OLD.id;
  ELSIF TG_TABLE_NAME='technical_report_snapshots' THEN previous_report=OLD.report_id;
  ELSIF OLD.agent_type='technical' THEN previous_report=OLD.agent_report_id; END IF;
  IF previous_report IS NOT NULL AND EXISTS(SELECT 1 FROM technical_analysis_runs WHERE planned_report_id=previous_report AND state='stored')
   AND (TG_OP='DELETE' OR OLD IS DISTINCT FROM NEW) THEN
   RAISE EXCEPTION 'CF050 stored canonical rows immutable' USING ERRCODE='23514';
  END IF;
 END IF;
 RETURN NULL;
END $$
"""
TRUNCATE_GUARD = """
CREATE FUNCTION cf050_report_truncate() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF EXISTS(SELECT 1 FROM technical_analysis_runs WHERE state='stored') THEN
  RAISE EXCEPTION 'CF050 stored canonical rows retained' USING ERRCODE='23514';
 END IF;
 RETURN NULL;
END $$
"""


def upgrade():
    for name in ('completion_format','input_json','input_sha256','result_json','result_sha256','binding_sha256','error_code'):
        op.add_column('technical_analysis_runs',sa.Column(name,sa.Text(),nullable=True))
    op.add_column('technical_analysis_runs',sa.Column('accepted_at',sa.DateTime(timezone=True),nullable=True))
    op.drop_constraint('cf048_run_state','technical_analysis_runs',type_='check')
    op.create_check_constraint('cf048_run_state','technical_analysis_runs',STATE_CHECK)
    for key,value in COMPLETION_CHECKS.items():op.create_check_constraint('cf050_completion_'+key,'technical_analysis_runs',value)
    op.execute(EXTENDED_RUN_GUARD)
    for function in (ISO_FUNCTION,CONTEXT_FUNCTION,BINDING_FUNCTION,COMPLETION_GUARD,STORED_ASSERT,LINK_GUARD,TRUNCATE_GUARD):op.execute(function)
    op.execute('CREATE TRIGGER cf050_completion_transition BEFORE INSERT OR UPDATE ON technical_analysis_runs FOR EACH ROW EXECUTE FUNCTION cf050_completion_guard()')
    for table in ('technical_analysis_runs','technical_reports','technical_report_snapshots','agent_reports'):
        op.execute('CREATE CONSTRAINT TRIGGER cf050_link_'+table+' AFTER INSERT OR UPDATE OR DELETE ON '+table+' DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION cf050_link_guard()')
    for table in ('technical_reports','technical_report_snapshots','agent_reports'):
        op.execute('CREATE TRIGGER cf050_truncate_'+table+' BEFORE TRUNCATE ON '+table+' FOR EACH STATEMENT EXECUTE FUNCTION cf050_report_truncate()')


def downgrade():
    op.execute('LOCK TABLE technical_usage_periods,technical_analysis_runs IN ACCESS EXCLUSIVE MODE')
    if op.get_bind().execute(sa.text("SELECT EXISTS(SELECT 1 FROM technical_analysis_runs WHERE state NOT IN ('admitted','claimed','unknown') OR completion_format IS NOT NULL OR input_json IS NOT NULL OR input_sha256 IS NOT NULL OR result_json IS NOT NULL OR result_sha256 IS NOT NULL OR binding_sha256 IS NOT NULL OR accepted_at IS NOT NULL OR error_code IS NOT NULL)")).scalar():
        raise RuntimeError('Technical completion populated; downgrade denied')
    for table in ('technical_analysis_runs','technical_reports','technical_report_snapshots','agent_reports'):
        op.execute('DROP TRIGGER cf050_link_'+table+' ON '+table)
    for table in ('technical_reports','technical_report_snapshots','agent_reports'):
        op.execute('DROP TRIGGER cf050_truncate_'+table+' ON '+table)
    op.execute('DROP TRIGGER cf050_completion_transition ON technical_analysis_runs')
    for function,args in (('cf050_report_truncate',''),('cf050_link_guard',''),('cf050_assert_stored','uuid'),('cf050_completion_guard',''),
                          ('cf050_binding','technical_analysis_runs,text,text'),('cf050_context','technical_analysis_runs,text,text'),('cf050_iso','timestamptz')):
        op.execute('DROP FUNCTION '+function+'('+args+')')
    op.execute(OLD_RUN_GUARD.replace('CREATE FUNCTION','CREATE OR REPLACE FUNCTION',1))
    for key in COMPLETION_CHECKS:op.drop_constraint('cf050_completion_'+key,'technical_analysis_runs',type_='check')
    op.drop_constraint('cf048_run_state','technical_analysis_runs',type_='check')
    op.create_check_constraint('cf048_run_state','technical_analysis_runs',OLD_STATE_CHECK)
    for name in ('completion_format','input_json','input_sha256','result_json','result_sha256','binding_sha256','accepted_at','error_code'):
        op.drop_column('technical_analysis_runs',name)
