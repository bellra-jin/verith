"""Add one Technical provider start and independent bounded evidence; old bytes retained."""
from alembic import op
import sqlalchemy as sa
import importlib.util
from pathlib import Path
revision='c53001a7e0001'
down_revision='c50001a7e0001'
branch_labels=None
depends_on=None

_old_spec=importlib.util.spec_from_file_location('_cf053_c500',Path(__file__).with_name('20261112_c50001a7e0001_technical_result_completion.py'))
_old=importlib.util.module_from_spec(_old_spec);_old_spec.loader.exec_module(_old)

PROVIDER_SPEC_JSON='{"boundary":"technical.boundary.v1","operation":"technical.analysis.v1","periods":["3m","1y","5y"],"profile":"technical.multiframe.v1","provider_authority":true,"settlement":false,"storage":"technical.owned-stage.v1","version":"technical.provider-execution.v1"}'
PROVIDER_SPEC_SHA256='b526fffe2e3c2ccce4c2c6a75f259bb61d82349ae2ceda16347b7b20f3d21e88'
OLD_SPEC_CHECK="(octet_length(spec_json) BETWEEN 2 AND 4096 AND jsonb_typeof(spec_json::jsonb)='object' AND spec_json::jsonb->>'version'='technical.admission.v1' AND spec_json::jsonb->>'operation'=operation AND spec_json::jsonb->>'boundary'='technical.boundary.v1' AND spec_json::jsonb->>'storage'='technical.owned-stage.v1' AND spec_json::jsonb->'provider_authority'='false'::jsonb AND spec_json::jsonb->'settlement'='false'::jsonb) IS TRUE"
SPEC_CHECK="((octet_length(spec_json) BETWEEN 2 AND 4096 AND jsonb_typeof(spec_json::jsonb)='object' AND spec_json::jsonb->>'version'='technical.admission.v1' AND spec_json::jsonb->>'operation'=operation AND spec_json::jsonb->>'boundary'='technical.boundary.v1' AND spec_json::jsonb->>'storage'='technical.owned-stage.v1' AND spec_json::jsonb->'provider_authority'='false'::jsonb AND spec_json::jsonb->'settlement'='false'::jsonb) IS TRUE) OR (spec_json=convert_from(decode('7b22626f756e64617279223a22746563686e6963616c2e626f756e646172792e7631222c226f7065726174696f6e223a22746563686e6963616c2e616e616c797369732e7631222c22706572696f6473223a5b22336d222c223179222c223579225d2c2270726f66696c65223a22746563686e6963616c2e6d756c74696672616d652e7631222c2270726f76696465725f617574686f72697479223a747275652c22736574746c656d656e74223a66616c73652c2273746f72616765223a22746563686e6963616c2e6f776e65642d73746167652e7631222c2276657273696f6e223a22746563686e6963616c2e70726f76696465722d657865637574696f6e2e7631227d','hex'),'UTF8') AND spec_sha256='b526fffe2e3c2ccce4c2c6a75f259bb61d82349ae2ceda16347b7b20f3d21e88')"
CHECKS={'configuration': "((spec_sha256='b526fffe2e3c2ccce4c2c6a75f259bb61d82349ae2ceda16347b7b20f3d21e88' AND execution_configuration_json IS NOT NULL AND octet_length(execution_configuration_json) BETWEEN 2 AND 32768 AND execution_configuration_sha256=encode(digest(convert_to(execution_configuration_json,'UTF8'),'sha256'),'hex')) OR (spec_sha256<>'b526fffe2e3c2ccce4c2c6a75f259bb61d82349ae2ceda16347b7b20f3d21e88' AND execution_configuration_json IS NULL AND execution_configuration_sha256 IS NULL)) IS TRUE", 'grant': "((execution_grant_digest IS NULL AND execution_control_json IS NULL AND execution_control_sha256 IS NULL) OR (spec_sha256='b526fffe2e3c2ccce4c2c6a75f259bb61d82349ae2ceda16347b7b20f3d21e88' AND claim_consumed_at IS NOT NULL AND octet_length(execution_grant_digest)=32 AND execution_control_json IS NOT NULL AND octet_length(execution_control_json) BETWEEN 2 AND 8192 AND execution_control_sha256 ~ '^[0-9a-f]{64}$')) IS TRUE", 'start': "((execution_started_at IS NULL AND execution_executor_id IS NULL AND execution_start_json IS NULL AND execution_start_sha256 IS NULL) OR (execution_grant_digest IS NOT NULL AND isfinite(execution_started_at) AND execution_started_at>=claim_consumed_at AND execution_started_at<deadline_at AND execution_executor_id IS NOT NULL AND execution_start_json IS NOT NULL AND octet_length(execution_start_json) BETWEEN 2 AND 8192 AND execution_start_sha256 ~ '^[0-9a-f]{64}$')) IS TRUE", 'evidence': "((execution_evidence_json IS NULL AND execution_evidence_sha256 IS NULL AND execution_observed_at IS NULL) OR (execution_started_at IS NOT NULL AND execution_evidence_json IS NOT NULL AND octet_length(execution_evidence_json) BETWEEN 2 AND 16384 AND jsonb_typeof(execution_evidence_json::jsonb)='object' AND execution_evidence_sha256=encode(digest(convert_to(execution_evidence_json,'UTF8'),'sha256'),'hex') AND isfinite(execution_observed_at) AND execution_observed_at>=execution_started_at)) IS TRUE"}
SNAPSHOT_CHECK="""((input_schema='analysis.agent.v1' AND result_schema='technical.boundary.v1' AND result_json::jsonb->>'schema_version'='analysis.agent.v1' AND result_json::jsonb->'data'->>'execution_mode'='synthetic') OR (input_schema='analysis.agent.v1' AND result_schema='technical.execution.v1' AND result_json::jsonb->>'schema_version'='technical.execution.v1' AND result_json::jsonb->'data'->>'execution_mode'='controlled')) IS TRUE"""
CANONICAL=r'''
CREATE FUNCTION cf053_canonical(v jsonb) RETURNS text LANGUAGE plpgsql IMMUTABLE STRICT AS $$
DECLARE s text;
BEGIN
 CASE jsonb_typeof(v)
 WHEN 'object' THEN SELECT '{'||coalesce(string_agg(to_jsonb(key)::text||':'||cf053_canonical(value),',' ORDER BY key COLLATE "C"),'')||'}' INTO s FROM jsonb_each(v);
 WHEN 'array' THEN SELECT '['||coalesce(string_agg(cf053_canonical(value),',' ORDER BY ordinal),'')||']' INTO s FROM jsonb_array_elements(v) WITH ORDINALITY a(value,ordinal);
 ELSE s=v::text; END CASE;
 RETURN s;
END $$;
CREATE FUNCTION cf053_hash(v text) RETURNS text LANGUAGE sql IMMUTABLE STRICT AS $$ SELECT encode(digest(convert_to(v,'UTF8'),'sha256'),'hex') $$;
CREATE FUNCTION cf053_boundary(r technical_analysis_runs) RETURNS text LANGUAGE plpgsql IMMUTABLE STRICT AS $$
DECLARE d jsonb; semantic jsonb;
BEGIN
 semantic=jsonb_build_object('operation','technical.boundary.v1','original_query',r.intent_json::jsonb->'original_query','stock',r.stock_json::jsonb,
  'requested_as_of',cf050_iso(r.as_of),'conditions',r.intent_json::jsonb->'conditions');
 d=semantic||jsonb_build_object('requested_views',jsonb_build_array('technical'),'context',jsonb_build_object('analysis_id',r.id,'admission_request_id',r.admission_request_id,
  'attempt_id',r.attempt_id,'report_id',r.planned_report_id,'input_fingerprint',cf053_hash(cf053_canonical(semantic))));
 RETURN cf053_canonical(jsonb_build_object('schema_version','analysis.agent.v1','request_id',r.boundary_request_id,'trace_id',r.trace_id,'data',d,'error',NULL));
END $$;
CREATE FUNCTION cf053_control(r technical_analysis_runs) RETURNS text LANGUAGE sql IMMUTABLE STRICT AS $$
 SELECT cf053_canonical(jsonb_build_object('analysis_id',r.id,'admission_request_id',r.admission_request_id,'attempt_id',r.attempt_id,'report_id',r.planned_report_id,
 'boundary_request_id',r.boundary_request_id,'trace_id',r.trace_id,'spec_sha256',r.spec_sha256,'policy_sha256',r.policy_sha256,
 'configuration_sha256',r.execution_configuration_sha256,'intent_sha256',r.intent_sha256,'boundary_sha256',cf053_hash(cf053_boundary(r)),
 'stock_sha256',r.stock_sha256,'reserved_nano',r.reserved_nano,'started_at',cf050_iso(r.started_at),'deadline_at',cf050_iso(r.deadline_at)))
$$;
CREATE FUNCTION cf053_control_hash(r technical_analysis_runs) RETURNS text LANGUAGE sql IMMUTABLE STRICT AS $$
 SELECT cf053_hash(cf053_canonical(jsonb_build_object('schema_version','technical.execution.v1','boundary_request',cf053_boundary(r)::jsonb,'control',r.execution_control_json::jsonb)))
$$;
'''
EVIDENCE=r'''
CREATE FUNCTION cf053_evidence_valid(r technical_analysis_runs,body jsonb) RETURNS boolean LANGUAGE plpgsql IMMUTABLE STRICT AS $$
DECLARE item jsonb; p jsonb; n integer=0; hold numeric; usage jsonb; estimated numeric; k text; expected_keys text[];
BEGIN
 p=r.execution_configuration_json::jsonb->'policy';
 IF EXISTS(SELECT 1 FROM jsonb_each(body) kv WHERE kv.value='null'::jsonb) THEN RETURN false; END IF;
 IF jsonb_typeof(body)<>'object' OR ARRAY(SELECT object_key FROM jsonb_object_keys(body) AS object_key ORDER BY object_key COLLATE "C")<>ARRAY['analysis_id','attempt_id','control_sha256','executor_id','outcome','policy_sha256','records','schema_version','start_sha256']
 OR body->>'schema_version'<>'technical.usage.v1' OR body->>'analysis_id'<>r.id::text OR body->>'attempt_id'<>r.attempt_id::text OR body->>'policy_sha256'<>r.policy_sha256
 OR body->>'control_sha256'<>r.execution_control_sha256 OR body->>'executor_id'<>r.execution_executor_id::text OR body->>'start_sha256'<>r.execution_start_sha256
 OR body->>'outcome' NOT IN ('completed','failed','cancelled','deadline','unknown') OR jsonb_typeof(body->'records')<>'array'
 OR jsonb_array_length(body->'records')>(p->>'max_calls')::integer THEN RETURN false; END IF;
 hold=(p->>'input_token_cap')::numeric*(p->>'input_nano_per_token')::numeric+(p->>'output_token_cap')::numeric*(p->>'output_nano_per_token')::numeric;
 expected_keys=ARRAY['analysis_id','attempt_id','count_entered','count_response_received','count_validated','counted_input_tokens','elapsed_ms','entered','estimated_nano','held_nano','input_token_cap','model','ordinal','output_token_cap','policy_sha256','projection_sha256','prompt_sha256','reason','request_sha256','response_model','response_received','response_tier','service_tier','text_accepted','usage'];
 FOR item IN SELECT value FROM jsonb_array_elements(body->'records') LOOP
  n=n+1;
  IF EXISTS(SELECT 1 FROM jsonb_each(item) kv WHERE kv.key NOT IN ('usage','reason','estimated_nano','counted_input_tokens') AND kv.value='null'::jsonb) THEN RETURN false; END IF;
  IF jsonb_typeof(item)<>'object' OR ARRAY(SELECT object_key FROM jsonb_object_keys(item) AS object_key ORDER BY object_key COLLATE "C")<>expected_keys THEN RETURN false; END IF;
  FOREACH k IN ARRAY ARRAY['ordinal','held_nano','input_token_cap','output_token_cap','elapsed_ms'] LOOP
   IF jsonb_typeof(item->k)<>'number' OR item->>k !~ '^[0-9]+$' OR (item->>k)::numeric>9223372036854775807 THEN RETURN false; END IF;
  END LOOP;
  IF (item->>'ordinal')::integer<>n OR item->>'analysis_id'<>r.id::text OR item->>'attempt_id'<>r.attempt_id::text OR item->>'policy_sha256'<>r.policy_sha256
   OR item->'model'<>p->'model' OR item->'service_tier'<>p->'service_tier' OR item->'input_token_cap'<>p->'input_token_cap' OR item->'output_token_cap'<>p->'output_token_cap'
   OR (item->>'held_nano')::numeric<>hold OR item->>'response_model' NOT IN ('unknown','match','mismatch') OR item->>'response_tier' NOT IN ('unknown','match','mismatch') THEN RETURN false; END IF;
  FOREACH k IN ARRAY ARRAY['request_sha256','prompt_sha256','projection_sha256'] LOOP
   IF jsonb_typeof(item->k) IS DISTINCT FROM 'string' OR item->>k !~ '^[0-9a-f]{64}$' THEN RETURN false; END IF;
  END LOOP;
  FOREACH k IN ARRAY ARRAY['entered','response_received','text_accepted','count_entered','count_response_received','count_validated'] LOOP
   IF jsonb_typeof(item->k)<>'boolean' THEN RETURN false; END IF;
  END LOOP;
  IF item->'reason'<>'null'::jsonb AND item->>'reason' NOT IN ('POLICY_INVALID','DEADLINE_EXCEEDED','SDK_POLICY_INVALID','COUNT_UNAVAILABLE','COUNT_INVALID','CLOSED','BUDGET_EXCEEDED','PROMPT_INVALID','SDK_UNKNOWN','COUNT_FAILED','USAGE_UNKNOWN','USAGE_LIMIT_MISMATCH','RESPONSE_METADATA_MISMATCH','RESPONSE_NOT_COMPLETED','TEXT_INVALID','CLOCK_INVALID','HTTP_INVALID','RESPONSE_LIMIT') THEN RETURN false; END IF;
  IF (item->>'entered')::boolean AND NOT (item->>'count_validated')::boolean
   OR (item->>'count_validated')::boolean AND NOT ((item->>'count_entered')::boolean AND (item->>'count_response_received')::boolean)
   OR (item->>'count_response_received')::boolean AND NOT (item->>'count_entered')::boolean
   OR (item->>'response_received')::boolean AND NOT (item->>'entered')::boolean THEN RETURN false; END IF;
  IF (item->>'count_validated')::boolean THEN
   IF jsonb_typeof(item->'counted_input_tokens')<>'number' OR item->>'counted_input_tokens' !~ '^[0-9]+$' OR (item->>'counted_input_tokens')::numeric>(p->>'input_token_cap')::numeric THEN RETURN false; END IF;
  ELSIF item->'counted_input_tokens'<>'null'::jsonb THEN RETURN false; END IF;
  usage=item->'usage';
  IF usage='null'::jsonb THEN
   IF item->'estimated_nano'<>'null'::jsonb OR (item->>'text_accepted')::boolean THEN RETURN false; END IF;
  ELSE
   IF jsonb_typeof(usage)<>'array' OR jsonb_array_length(usage)<>3 OR NOT (item->>'response_received')::boolean THEN RETURN false; END IF;
   IF EXISTS(SELECT 1 FROM jsonb_array_elements(usage) v WHERE jsonb_typeof(v)<>'number' OR v::text !~ '^[0-9]+$' OR v::text::numeric>9223372036854775807) THEN RETURN false; END IF;
   IF (usage->>0)::numeric+(usage->>1)::numeric<>(usage->>2)::numeric THEN RETURN false; END IF;
   estimated=(usage->>0)::numeric*(p->>'input_nano_per_token')::numeric+(usage->>1)::numeric*(p->>'output_nano_per_token')::numeric;
   IF estimated>9223372036854775807 THEN
    IF item->'estimated_nano'<>'null'::jsonb THEN RETURN false; END IF;
   ELSIF jsonb_typeof(item->'estimated_nano')<>'number' OR item->>'estimated_nano' !~ '^[0-9]+$' OR (item->>'estimated_nano')::numeric<>estimated THEN RETURN false; END IF;
   IF (item->>'text_accepted')::boolean AND (item->>'response_model'='mismatch' OR item->>'response_tier'='mismatch' OR item->'reason'<>'null'::jsonb OR (usage->>0)::numeric<>(item->>'counted_input_tokens')::numeric OR (usage->>0)::numeric>(p->>'input_token_cap')::numeric OR (usage->>1)::numeric>(p->>'output_token_cap')::numeric) THEN RETURN false; END IF;
  END IF;
 END LOOP;
 RETURN n*hold<=r.reserved_nano;
EXCEPTION WHEN OTHERS THEN RETURN false;
END $$;
'''
GUARD=r'''
CREATE FUNCTION cf053_provider_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE cfg jsonb; p jsonb; start_body jsonb; k text;
BEGIN
 IF NEW.spec_sha256<>'@SPEC@' THEN
  IF ROW(NEW.execution_configuration_json,NEW.execution_grant_digest,NEW.execution_control_json,NEW.execution_started_at,NEW.execution_evidence_json)
     IS DISTINCT FROM ROW(NULL::text,NULL::bytea,NULL::text,NULL::timestamptz,NULL::text) THEN RAISE EXCEPTION 'CF053 old run unchanged' USING ERRCODE='23514'; END IF;
  RETURN NEW;
 END IF;
 cfg=NEW.execution_configuration_json::jsonb;p=cfg->'policy';
 IF EXISTS(SELECT 1 FROM jsonb_each(cfg) kv WHERE kv.value='null'::jsonb) OR jsonb_typeof(cfg->'policy')<>'object' OR jsonb_typeof(cfg->'counter')<>'object' OR jsonb_typeof(cfg->'caps')<>'object' THEN RAISE EXCEPTION 'CF053 configuration types' USING ERRCODE='23514'; END IF;
 IF ARRAY(SELECT object_key FROM jsonb_object_keys(cfg->'counter') AS object_key ORDER BY object_key COLLATE "C")<>ARRAY['evidence_sha256','free','mapping','provenance_sha256','version'] OR ARRAY(SELECT object_key FROM jsonb_object_keys(cfg->'caps') AS object_key ORDER BY object_key COLLATE "C")<>ARRAY['count','generation','request'] OR EXISTS(SELECT 1 FROM jsonb_each(cfg->'counter') kv WHERE kv.value='null'::jsonb OR kv.key<>'free' AND jsonb_typeof(kv.value)<>'string') THEN RAISE EXCEPTION 'CF053 counter shape' USING ERRCODE='23514'; END IF;
 FOREACH k IN ARRAY ARRAY['request','count','generation'] LOOP
  IF (jsonb_typeof(cfg->'caps'->k)='number' AND cfg->'caps'->>k ~ '^[0-9]+$' AND (cfg->'caps'->>k)::numeric BETWEEN 1 AND 2097152) IS NOT TRUE THEN RAISE EXCEPTION 'CF053 strict cap' USING ERRCODE='23514'; END IF;
 END LOOP;
 IF cf053_canonical(cfg)<>NEW.execution_configuration_json OR ARRAY(SELECT object_key FROM jsonb_object_keys(cfg) AS object_key ORDER BY object_key COLLATE "C")<>ARRAY['ai_origin','authority_origin','cache_mode','caps','counter','policy','schema_version','trace_mode']
  OR cfg->>'schema_version'<>'technical.execution.v1' OR cf053_hash(cf053_canonical(p))<>NEW.policy_sha256
  OR p->>'enabled'<>'true' OR p->>'service_tier'<>'default' OR (p->>'max_calls')::integer NOT BETWEEN 1 AND 4
  OR cfg->'counter'->'free'<>'true'::jsonb OR cfg->'counter'->>'mapping'<>'technical.responses.model-input.v1'
  OR cfg->'counter'->>'version' !~ '^[A-Za-z0-9_.:-]{1,128}$' OR cfg->'counter'->>'provenance_sha256' !~ '^[0-9a-f]{64}$' OR cfg->'counter'->>'evidence_sha256' !~ '^[0-9a-f]{64}$'
  OR (cfg->'caps'->>'request')::integer NOT BETWEEN 1 AND 2097152 OR (cfg->'caps'->>'count')::integer NOT BETWEEN 1 AND 2097152 OR (cfg->'caps'->>'generation')::integer NOT BETWEEN 1 AND 2097152
  OR cfg->>'cache_mode' NOT IN ('none','injected') OR cfg->>'trace_mode' NOT IN ('none','injected') THEN RAISE EXCEPTION 'CF053 configuration' USING ERRCODE='23514'; END IF;
 IF TG_OP='INSERT' THEN
  IF NEW.execution_grant_digest IS NOT NULL OR NEW.execution_started_at IS NOT NULL OR NEW.execution_evidence_json IS NOT NULL THEN RAISE EXCEPTION 'CF053 starts unconsumed' USING ERRCODE='23514'; END IF;
  RETURN NEW;
 END IF;
 IF ROW(NEW.execution_configuration_json,NEW.execution_configuration_sha256) IS DISTINCT FROM ROW(OLD.execution_configuration_json,OLD.execution_configuration_sha256)
 OR OLD.execution_grant_digest IS NOT NULL AND ROW(NEW.execution_grant_digest,NEW.execution_control_json,NEW.execution_control_sha256) IS DISTINCT FROM ROW(OLD.execution_grant_digest,OLD.execution_control_json,OLD.execution_control_sha256)
 OR OLD.execution_started_at IS NOT NULL AND ROW(NEW.execution_started_at,NEW.execution_executor_id,NEW.execution_start_json,NEW.execution_start_sha256) IS DISTINCT FROM ROW(OLD.execution_started_at,OLD.execution_executor_id,OLD.execution_start_json,OLD.execution_start_sha256)
 OR OLD.execution_evidence_json IS NOT NULL AND ROW(NEW.execution_evidence_json,NEW.execution_evidence_sha256,NEW.execution_observed_at) IS DISTINCT FROM ROW(OLD.execution_evidence_json,OLD.execution_evidence_sha256,OLD.execution_observed_at) THEN RAISE EXCEPTION 'CF053 immutable execution' USING ERRCODE='23514'; END IF;
 IF OLD.claim_consumed_at IS NULL AND NEW.claim_consumed_at IS NOT NULL THEN
  IF NEW.execution_grant_digest IS NULL OR NEW.execution_control_json<>cf053_control(NEW) OR NEW.execution_control_sha256<>cf053_control_hash(NEW) THEN RAISE EXCEPTION 'CF053 claim grant binding' USING ERRCODE='23514'; END IF;
 ELSIF OLD.execution_grant_digest IS NULL AND NEW.execution_grant_digest IS NOT NULL THEN RAISE EXCEPTION 'CF053 no grant refresh' USING ERRCODE='23514'; END IF;
 IF OLD.execution_started_at IS NULL AND NEW.execution_started_at IS NOT NULL THEN
  IF OLD.state<>'claimed' OR OLD.accepted_at IS NOT NULL OR OLD.execution_grant_digest IS NULL OR clock_timestamp()>=OLD.deadline_at OR NEW.execution_started_at>clock_timestamp()
   OR (SELECT blocked FROM technical_usage_periods WHERE id=NEW.period_id)
   OR NOT EXISTS(SELECT 1 FROM auth_sessions s JOIN auth_users u ON u.id=s.user_id WHERE s.id=NEW.admission_session_id AND s.user_id=NEW.owner_user_id AND s.revoked_at IS NULL AND s.expires_at>clock_timestamp() AND u.disabled_at IS NULL)
   OR NOT EXISTS(SELECT 1 FROM stocks s WHERE s.stock_code=NEW.ticker AND jsonb_build_object('stock_code',s.stock_code,'stock_name',s.stock_name,'market',s.market)=NEW.stock_json::jsonb) THEN RAISE EXCEPTION 'CF053 fresh start' USING ERRCODE='23514'; END IF;
  start_body=NEW.execution_start_json::jsonb;
  IF start_body<>jsonb_build_object('control_sha256',NEW.execution_control_sha256,'executor_id',NEW.execution_executor_id,'started_at',cf050_iso(NEW.execution_started_at),'start_sha256',NEW.execution_start_sha256)
   OR NEW.execution_start_json<>cf053_canonical(start_body) OR NEW.execution_start_sha256<>cf053_hash(cf053_canonical(start_body-'start_sha256')) THEN RAISE EXCEPTION 'CF053 start binding' USING ERRCODE='23514'; END IF;
 END IF;
 IF OLD.execution_evidence_json IS NULL AND NEW.execution_evidence_json IS NOT NULL THEN
  IF OLD.execution_started_at IS NULL OR NEW.execution_evidence_json<>cf053_canonical(NEW.execution_evidence_json::jsonb) OR cf053_evidence_valid(NEW,NEW.execution_evidence_json::jsonb) IS NOT TRUE THEN RAISE EXCEPTION 'CF053 evidence binding' USING ERRCODE='23514'; END IF;
 END IF;
 RETURN NEW;
END $$;
'''.replace('@SPEC@',PROVIDER_SPEC_SHA256)
BINDING=r'''
CREATE OR REPLACE FUNCTION cf050_binding(r technical_analysis_runs,input_text text,result_hash text) RETURNS text LANGUAGE plpgsql IMMUTABLE STRICT AS $$
DECLARE caller text; context text; schema text;
BEGIN
 caller='{"boundary_request":'||input_text||',"operation":"technical.owned-stage.v1"}';
 context=cf050_context(r,'technical.owned-stage.v1',encode(digest(convert_to(caller,'UTF8'),'sha256'),'hex'));
 schema=CASE WHEN r.spec_sha256='@SPEC@' THEN 'technical.execution.v1' ELSE 'technical.boundary.v1' END;
 RETURN encode(digest(convert_to('{"context":'||context||',"input_schema":"analysis.agent.v1","input_sha256":"'||
 encode(digest(convert_to(input_text,'UTF8'),'sha256'),'hex')||'","report_id":"'||r.planned_report_id::text||
 '","result_schema":"'||schema||'","result_sha256":"'||result_hash||'"}','UTF8'),'sha256'),'hex');
END $$;
'''.replace('@SPEC@',PROVIDER_SPEC_SHA256)

def replace_functions():
    guard=_old.COMPLETION_GUARD.replace('CREATE FUNCTION','CREATE OR REPLACE FUNCTION',1)
    guard=guard.replace("result->>'schema_version'='analysis.agent.v1'", "result->>'schema_version'=CASE WHEN NEW.spec_sha256='"+PROVIDER_SPEC_SHA256+"' THEN 'technical.execution.v1' ELSE 'analysis.agent.v1' END")
    insertion="""IF NEW.spec_sha256='@SPEC@' AND (NEW.execution_started_at IS NULL OR NEW.result_json::jsonb->'data'->>'execution_mode' IS DISTINCT FROM 'controlled' OR NEW.result_json::jsonb->'data'->>'control_sha256' IS DISTINCT FROM NEW.execution_control_sha256 OR NEW.result_json::jsonb->'data'->>'start_sha256' IS DISTINCT FROM NEW.execution_start_sha256 OR NEW.result_json::jsonb->'data'->>'executor_id' IS DISTINCT FROM NEW.execution_executor_id::text) THEN RAISE EXCEPTION 'CF053 controlled acceptance' USING ERRCODE='23514'; END IF;
  """.replace('@SPEC@',PROVIDER_SPEC_SHA256)
    guard=guard.replace('d=NEW.input_json::jsonb',insertion+'d=NEW.input_json::jsonb')
    stored=_old.STORED_ASSERT.replace('CREATE FUNCTION','CREATE OR REPLACE FUNCTION',1)
    stored=stored.replace('BEGIN',"BEGIN IF EXISTS(SELECT 1 FROM technical_report_snapshots s WHERE s.report_id=report AND s.result_schema='technical.execution.v1') AND NOT EXISTS(SELECT 1 FROM technical_analysis_runs provider_candidate WHERE provider_candidate.planned_report_id=report AND provider_candidate.spec_sha256='"+PROVIDER_SPEC_SHA256+"' AND provider_candidate.accepted_at IS NOT NULL AND provider_candidate.state='stored') THEN RAISE EXCEPTION 'CF053 controlled storage requires run' USING ERRCODE='23514'; END IF;",1)
    stored=stored.replace('AND snap.request_id=r.boundary_request_id',"AND snap.input_schema='analysis.agent.v1' AND snap.result_schema=CASE WHEN r.spec_sha256='"+PROVIDER_SPEC_SHA256+"' THEN 'technical.execution.v1' ELSE 'technical.boundary.v1' END AND snap.request_id=r.boundary_request_id")
    return guard,stored

TEXT_COLUMNS=('execution_configuration_json','execution_configuration_sha256','execution_control_json','execution_control_sha256',
 'execution_start_json','execution_start_sha256','execution_evidence_json','execution_evidence_sha256')
def upgrade():
    for name in TEXT_COLUMNS:op.add_column('technical_analysis_runs',sa.Column(name,sa.Text(),nullable=True))
    op.add_column('technical_analysis_runs',sa.Column('execution_grant_digest',sa.LargeBinary(),nullable=True))
    op.add_column('technical_analysis_runs',sa.Column('execution_executor_id',sa.Uuid(),nullable=True))
    for name in ('execution_started_at','execution_observed_at'):op.add_column('technical_analysis_runs',sa.Column(name,sa.DateTime(timezone=True),nullable=True))
    op.drop_constraint('cf048_run_spec','technical_analysis_runs',type_='check');op.create_check_constraint('cf048_run_spec','technical_analysis_runs',SPEC_CHECK)
    for key,value in CHECKS.items():op.create_check_constraint('cf053_provider_'+key,'technical_analysis_runs',value)
    op.drop_constraint('ck_technical_snapshot_schemas','technical_report_snapshots',type_='check');op.create_check_constraint('ck_technical_snapshot_schemas','technical_report_snapshots',SNAPSHOT_CHECK)
    pieces=CANONICAL.strip().split('\nCREATE FUNCTION ')
    for index,sql in enumerate(pieces):op.execute(sql if index==0 else 'CREATE FUNCTION '+sql)
    for sql in (EVIDENCE,GUARD,BINDING,*replace_functions()):op.execute(sql)
    op.execute('CREATE TRIGGER cf053_provider_transition BEFORE INSERT OR UPDATE ON technical_analysis_runs FOR EACH ROW EXECUTE FUNCTION cf053_provider_guard()')

def downgrade():
    op.execute('LOCK TABLE technical_usage_periods,technical_analysis_runs,technical_report_snapshots IN ACCESS EXCLUSIVE MODE')
    if op.get_bind().execute(sa.text("SELECT EXISTS(SELECT 1 FROM technical_analysis_runs WHERE execution_configuration_json IS NOT NULL) OR EXISTS(SELECT 1 FROM technical_report_snapshots WHERE result_schema='technical.execution.v1')")).scalar():raise RuntimeError('Technical provider records retained; downgrade denied')
    op.execute('DROP TRIGGER cf053_provider_transition ON technical_analysis_runs')
    for sql in (_old.BINDING_FUNCTION,_old.COMPLETION_GUARD,_old.STORED_ASSERT):op.execute(sql.replace('CREATE FUNCTION','CREATE OR REPLACE FUNCTION',1))
    for f,args in [('cf053_provider_guard',''),('cf053_evidence_valid','technical_analysis_runs,jsonb'),('cf053_control_hash','technical_analysis_runs'),('cf053_control','technical_analysis_runs'),('cf053_boundary','technical_analysis_runs'),('cf053_hash','text'),('cf053_canonical','jsonb')]:op.execute('DROP FUNCTION '+f+'('+args+')')
    for key in CHECKS:op.drop_constraint('cf053_provider_'+key,'technical_analysis_runs',type_='check')
    op.drop_constraint('cf048_run_spec','technical_analysis_runs',type_='check');op.create_check_constraint('cf048_run_spec','technical_analysis_runs',OLD_SPEC_CHECK)
    op.drop_constraint('ck_technical_snapshot_schemas','technical_report_snapshots',type_='check');op.create_check_constraint('ck_technical_snapshot_schemas','technical_report_snapshots',"input_schema='analysis.agent.v1' AND result_schema='technical.boundary.v1'")
    for name in (*TEXT_COLUMNS,'execution_grant_digest','execution_executor_id','execution_started_at','execution_observed_at'):op.drop_column('technical_analysis_runs',name)
