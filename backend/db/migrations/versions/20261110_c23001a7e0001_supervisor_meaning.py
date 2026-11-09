"""Add durable meaning preparations/one verifier epoch; preserve legacy binding rows."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

revision = 'c23001a7e0001'
down_revision = 'c22001a7e0001'
branch_labels = None
depends_on = None
PREPARATION_CHECKS = {'identity': "octet_length(prepare_key_digest)=32 AND request_digest ~ '^[0-9a-f]{64}$' AND draft_digest ~ '^[0-9a-f]{64}$' AND semantic_sha256 ~ '^[0-9a-f]{64}$' AND semantic_sha256=encode(digest(convert_to(semantic_json,'UTF8'),'sha256'),'hex') AND jsonb_typeof(semantic_json::jsonb)='object'", 'clock': "isfinite(created_at) AND isfinite(expires_at) AND expires_at>created_at AND expires_at<=created_at+interval '10 minutes' AND (redacted_at IS NULL OR isfinite(redacted_at) AND redacted_at>=created_at)", 'lineage': 'depth BETWEEN 0 AND 4 AND ((parent_id IS NULL AND root_id=id AND depth=0) OR (parent_id IS NOT NULL AND parent_id<>id AND root_id<>id AND depth>0))', 'state': "state IN ('pending','ready','clarification','unsupported','failed','unknown','expired','deleted','consumed') AND ((state='consumed')=(consumed_binding_id IS NOT NULL)) AND (state NOT IN ('expired','deleted','consumed') OR (redacted_at IS NOT NULL AND draft_json IS NULL AND frame_json IS NULL AND plan_json IS NULL AND continuation_json IS NULL))", 'root_only': 'parent_id IS NULL OR (draft_json IS NULL AND frame_json IS NULL AND plan_json IS NULL)', 'json': "(draft_json IS NULL OR (octet_length(convert_to(draft_json,'UTF8'))<=16384 AND jsonb_typeof(draft_json::jsonb)='object')) AND (frame_json IS NULL OR (octet_length(convert_to(frame_json,'UTF8'))<=65536 AND jsonb_typeof(frame_json::jsonb)='object' AND frame_sha256 IS NOT NULL AND frame_sha256=encode(digest(convert_to(frame_json,'UTF8'),'sha256'),'hex'))) AND (plan_json IS NULL OR (octet_length(convert_to(plan_json,'UTF8'))<=65536 AND jsonb_typeof(plan_json::jsonb)='object' AND plan_sha256 IS NOT NULL AND plan_sha256=encode(digest(convert_to(plan_json,'UTF8'),'sha256'),'hex'))) AND (continuation_json IS NULL OR (octet_length(convert_to(continuation_json,'UTF8'))<=8192 AND jsonb_typeof(continuation_json::jsonb)='object' AND NOT continuation_json::jsonb ?| ARRAY['original_query','answers','frame','plan']))", 'completion': "state NOT IN ('ready','clarification','unsupported') OR (plan_sha256 IS NOT NULL AND plan_sha256 ~ '^[0-9a-f]{64}$' AND ((parent_id IS NULL AND draft_json IS NOT NULL AND frame_json IS NOT NULL AND plan_json IS NOT NULL) OR (parent_id IS NOT NULL AND continuation_json IS NOT NULL)))"}
EPOCH_CHECKS = {'fixed': "unit_id='CF023' AND currency='USD' AND max_nano=100000000 AND attempt_reserve_nano=50000000 AND max_attempts=2 AND price_sha256 ~ '^[0-9a-f]{64}$' AND semantic_sha256 ~ '^[0-9a-f]{64}$'", 'limits': 'reserved_nano BETWEEN 0 AND 100000000 AND count_requests BETWEEN 0 AND 2 AND generation_requests BETWEEN 0 AND 2 AND generation_requests<=count_requests', 'ledger': "jsonb_typeof(attempts_json)='object' AND octet_length(attempts_json::text)<=16384"}


def binding_guard(include_preparation):
    preparation = ',NEW.preparation_id' if include_preparation else ''
    old_preparation = ',OLD.preparation_id' if include_preparation else ''
    return """CREATE OR REPLACE FUNCTION cf022_binding_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
      IF (NEW.id,NEW.owner_user_id,NEW.client_key_digest,NEW.confirm_digest,NEW.plan_sha256,NEW.flow_sha256,NEW.flow_key_digest,NEW.confirmed_at,NEW.handoff_before%s)
       IS DISTINCT FROM
       (OLD.id,OLD.owner_user_id,OLD.client_key_digest,OLD.confirm_digest,OLD.plan_sha256,OLD.flow_sha256,OLD.flow_key_digest,OLD.confirmed_at,OLD.handoff_before%s)
       OR OLD.redacted_at IS NOT NULL OR NEW.redacted_at IS NULL OR NEW.plan_json IS NOT NULL OR NEW.flow_input_json IS NOT NULL THEN
        RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Supervisor binding is immutable';
      END IF; RETURN NEW; END; $$""" % (preparation,old_preparation)


def upgrade():
    op.create_unique_constraint('uq_supervisor_binding_id_owner','supervisor_request_bindings',['id','owner_user_id'])
    op.create_table('supervisor_meaning_test_epochs',
        sa.Column('id',pg.UUID(as_uuid=True),primary_key=True),
        sa.Column('unit_id',sa.Text(),nullable=False,unique=True),
        sa.Column('currency',sa.Text(),nullable=False),
        *[sa.Column(name,sa.BigInteger(),nullable=False) for name in ('max_nano','attempt_reserve_nano','reserved_nano')],
        *[sa.Column(name,sa.Integer(),nullable=False) for name in ('max_attempts','count_requests','generation_requests')],
        *[sa.Column(name,sa.Text(),nullable=False) for name in ('price_sha256','semantic_sha256')],
        sa.Column('blocked',sa.Boolean(),nullable=False),sa.Column('active_attempt_id',pg.UUID(as_uuid=True)),
        sa.Column('attempts_json',pg.JSONB(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        *[sa.CheckConstraint(value,name='cf023_epoch_'+name) for name,value in EPOCH_CHECKS.items()])
    op.create_table('supervisor_meaning_preparations',
        sa.Column('id',pg.UUID(as_uuid=True),primary_key=True),
        sa.Column('owner_user_id',pg.UUID(as_uuid=True),sa.ForeignKey('auth_users.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('prepare_key_digest',sa.LargeBinary(),nullable=False),
        *[sa.Column(name,sa.Text(),nullable=False) for name in ('request_digest','draft_digest','semantic_json','semantic_sha256','state','meaning_status')],
        sa.Column('root_id',pg.UUID(as_uuid=True),nullable=False),sa.Column('parent_id',pg.UUID(as_uuid=True)),
        sa.Column('depth',sa.Integer(),nullable=False),sa.Column('attempt_id',pg.UUID(as_uuid=True),nullable=False,unique=True),
        sa.Column('epoch_id',pg.UUID(as_uuid=True),sa.ForeignKey('supervisor_meaning_test_epochs.id',ondelete='RESTRICT')),
        *[sa.Column(name,sa.Text()) for name in ('draft_json','frame_json','frame_sha256','plan_json','plan_sha256','continuation_json')],
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('redacted_at',sa.DateTime(timezone=True)),sa.Column('consumed_binding_id',pg.UUID(as_uuid=True)),
        sa.UniqueConstraint('owner_user_id','prepare_key_digest',name='uq_meaning_owner_prepare_key'),
        sa.UniqueConstraint('id','owner_user_id',name='uq_meaning_id_owner'),
        *[sa.ForeignKeyConstraint([name,'owner_user_id'],['supervisor_meaning_preparations.id','supervisor_meaning_preparations.owner_user_id'],name=constraint,ondelete='RESTRICT',deferrable=True,initially='DEFERRED') for name,constraint in [('parent_id','fk_meaning_parent_owner'),('root_id','fk_meaning_root_owner')]],
        sa.ForeignKeyConstraint(['consumed_binding_id','owner_user_id'],['supervisor_request_bindings.id','supervisor_request_bindings.owner_user_id'],name='fk_meaning_consumed_owner',ondelete='RESTRICT',deferrable=True,initially='DEFERRED'),
        *[sa.CheckConstraint(value,name='cf023_preparation_'+name) for name,value in PREPARATION_CHECKS.items()])
    op.add_column('supervisor_request_bindings',sa.Column('preparation_id',pg.UUID(as_uuid=True)))
    op.create_unique_constraint('uq_supervisor_binding_preparation','supervisor_request_bindings',['preparation_id'])
    op.create_foreign_key('fk_supervisor_preparation_owner','supervisor_request_bindings','supervisor_meaning_preparations',['preparation_id','owner_user_id'],['id','owner_user_id'],ondelete='RESTRICT',deferrable=True,initially='DEFERRED')
    op.execute(binding_guard(True))
    op.execute(PREPARATION_GUARD)
    op.execute('CREATE TRIGGER cf023_preparation_guard BEFORE INSERT OR UPDATE ON supervisor_meaning_preparations FOR EACH ROW EXECUTE FUNCTION cf023_preparation_guard()')
    op.execute(CONSUMPTION_GUARD)
    op.execute('CREATE CONSTRAINT TRIGGER cf023_binding_consumption AFTER INSERT OR UPDATE ON supervisor_request_bindings DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION cf023_consumption_guard()')
    op.execute('CREATE CONSTRAINT TRIGGER cf023_preparation_consumption AFTER INSERT OR UPDATE ON supervisor_meaning_preparations DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION cf023_consumption_guard()')
    op.execute(EPOCH_GUARD)
    op.execute('CREATE TRIGGER cf023_epoch_guard BEFORE INSERT OR UPDATE ON supervisor_meaning_test_epochs FOR EACH ROW EXECUTE FUNCTION cf023_epoch_guard()')


def downgrade():
    op.execute('LOCK TABLE supervisor_meaning_preparations,supervisor_meaning_test_epochs IN ACCESS EXCLUSIVE MODE')
    populated=op.get_bind().execute(sa.text('SELECT EXISTS(SELECT 1 FROM supervisor_meaning_preparations) OR EXISTS(SELECT 1 FROM supervisor_meaning_test_epochs)')).scalar()
    if populated:
        raise RuntimeError('Nonempty meaning history cannot be downgraded')
    op.execute('DROP TRIGGER cf023_binding_consumption ON supervisor_request_bindings')
    op.execute('DROP TRIGGER cf023_preparation_consumption ON supervisor_meaning_preparations')
    op.execute('DROP FUNCTION cf023_consumption_guard()')
    op.drop_constraint('fk_supervisor_preparation_owner','supervisor_request_bindings',type_='foreignkey')
    op.drop_constraint('uq_supervisor_binding_preparation','supervisor_request_bindings',type_='unique')
    op.execute(binding_guard(False))
    op.drop_column('supervisor_request_bindings','preparation_id')
    op.drop_table('supervisor_meaning_preparations')
    op.execute('DROP FUNCTION cf023_preparation_guard()')
    op.drop_table('supervisor_meaning_test_epochs')
    op.execute('DROP FUNCTION cf023_epoch_guard()')
    op.drop_constraint('uq_supervisor_binding_id_owner','supervisor_request_bindings',type_='unique')


PREPARATION_GUARD = r"""
CREATE FUNCTION cf023_preparation_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE parent supervisor_meaning_preparations%ROWTYPE; item RECORD;
BEGIN
 IF TG_OP='INSERT' THEN
  IF NEW.parent_id IS NOT NULL THEN
   FOR item IN
    WITH RECURSIVE chain AS (
     SELECT p.id,p.parent_id,p.depth FROM supervisor_meaning_preparations p WHERE p.id=NEW.parent_id AND p.owner_user_id=NEW.owner_user_id
     UNION ALL SELECT p.id,p.parent_id,p.depth FROM supervisor_meaning_preparations p JOIN chain c ON p.id=c.parent_id WHERE c.depth>0 AND p.owner_user_id=NEW.owner_user_id)
    SELECT p.* FROM supervisor_meaning_preparations p JOIN chain c ON p.id=c.id ORDER BY p.depth,p.id FOR UPDATE OF p
   LOOP
    IF item.id=NEW.id OR item.state IN ('consumed','deleted','expired') OR item.redacted_at IS NOT NULL OR item.expires_at<=clock_timestamp() THEN
     RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Meaning lineage closed';
    END IF;
   END LOOP;
   SELECT * INTO parent FROM supervisor_meaning_preparations WHERE id=NEW.parent_id AND owner_user_id=NEW.owner_user_id;
   IF NOT FOUND OR parent.root_id<>NEW.root_id OR parent.depth+1<>NEW.depth OR NEW.expires_at>parent.expires_at OR parent.state NOT IN ('ready','clarification') THEN
    RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Meaning parent invalid';
   END IF;
  END IF;
  RETURN NEW;
 END IF;
 IF (NEW.id,NEW.owner_user_id,NEW.prepare_key_digest,NEW.request_digest,NEW.draft_digest,NEW.semantic_json,NEW.semantic_sha256,NEW.root_id,NEW.parent_id,NEW.depth,NEW.attempt_id,NEW.epoch_id,NEW.created_at,NEW.expires_at)
  IS DISTINCT FROM (OLD.id,OLD.owner_user_id,OLD.prepare_key_digest,OLD.request_digest,OLD.draft_digest,OLD.semantic_json,OLD.semantic_sha256,OLD.root_id,OLD.parent_id,OLD.depth,OLD.attempt_id,OLD.epoch_id,OLD.created_at,OLD.expires_at)
  OR OLD.consumed_binding_id IS NOT NULL AND NEW.consumed_binding_id IS DISTINCT FROM OLD.consumed_binding_id
  OR OLD.redacted_at IS NOT NULL AND NEW.redacted_at IS DISTINCT FROM OLD.redacted_at THEN
  RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Meaning identity is immutable';
 END IF;
 IF (NEW.draft_json IS DISTINCT FROM OLD.draft_json AND NEW.draft_json IS NOT NULL)
  OR (OLD.frame_sha256 IS NOT NULL AND NEW.frame_sha256 IS DISTINCT FROM OLD.frame_sha256)
  OR (OLD.plan_sha256 IS NOT NULL AND NEW.plan_sha256 IS DISTINCT FROM OLD.plan_sha256)
  OR (OLD.state<>'pending' AND ((NEW.frame_json IS DISTINCT FROM OLD.frame_json AND NEW.frame_json IS NOT NULL) OR (NEW.plan_json IS DISTINCT FROM OLD.plan_json AND NEW.plan_json IS NOT NULL) OR (NEW.continuation_json IS DISTINCT FROM OLD.continuation_json AND NEW.continuation_json IS NOT NULL))) THEN
  RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Meaning snapshot is immutable';
 END IF;
 IF NEW.state='consumed' AND OLD.state<>'consumed' AND clock_timestamp()>=OLD.expires_at THEN
  RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Meaning preparation expired before consumption';
 END IF;
 IF NEW.state IS DISTINCT FROM OLD.state AND NOT (
  OLD.state='pending' AND NEW.state IN ('ready','clarification','unsupported','failed','unknown','expired','deleted') OR
  OLD.state IN ('ready','clarification','unsupported') AND NEW.state IN ('expired','deleted','consumed') OR
  OLD.state IN ('failed','unknown') AND NEW.state IN ('expired','deleted') OR
  OLD.state='expired' AND NEW.state='deleted') THEN
  RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Meaning transition invalid';
 END IF;
 IF OLD.state='pending' AND NEW.state IN ('ready','clarification','unsupported') AND (OLD.redacted_at IS NOT NULL OR clock_timestamp()>=OLD.expires_at) THEN
  RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Meaning result expired';
 END IF;
 RETURN NEW;
END $$;
"""

CONSUMPTION_GUARD = r"""
CREATE FUNCTION cf023_consumption_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE binding supervisor_request_bindings%ROWTYPE; item RECORD; seen INTEGER=0; direct_depth INTEGER; contains_source BOOLEAN=FALSE;
BEGIN
 IF TG_TABLE_NAME='supervisor_request_bindings' THEN
  IF NEW.preparation_id IS NULL THEN RETURN NULL; END IF;
  SELECT * INTO binding FROM supervisor_request_bindings WHERE id=NEW.id;
 ELSE
  IF NEW.consumed_binding_id IS NULL THEN RETURN NULL; END IF;
  SELECT * INTO binding FROM supervisor_request_bindings WHERE id=NEW.consumed_binding_id AND owner_user_id=NEW.owner_user_id;
 END IF;
 IF NOT FOUND OR binding.preparation_id IS NULL THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Meaning consumption binding missing'; END IF;
 SELECT depth INTO direct_depth FROM supervisor_meaning_preparations WHERE id=binding.preparation_id AND owner_user_id=binding.owner_user_id;
 FOR item IN
  WITH RECURSIVE chain AS (
   SELECT p.* FROM supervisor_meaning_preparations p WHERE p.id=binding.preparation_id AND p.owner_user_id=binding.owner_user_id
   UNION ALL SELECT p.* FROM supervisor_meaning_preparations p JOIN chain c ON p.id=c.parent_id WHERE c.depth>0 AND p.owner_user_id=binding.owner_user_id)
  SELECT * FROM chain
 LOOP
  seen=seen+1;
  IF item.id=NEW.id THEN contains_source=TRUE; END IF;
  IF item.state<>'consumed' OR item.consumed_binding_id IS DISTINCT FROM binding.id THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Meaning ancestor not consumed by winner';
  END IF;
 END LOOP;
 IF seen<>direct_depth+1 OR TG_TABLE_NAME='supervisor_meaning_preparations' AND NOT contains_source THEN
  RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Meaning consumption path invalid';
 END IF;
 RETURN NULL;
END $$;
"""

EPOCH_GUARD = r"""
CREATE FUNCTION cf023_epoch_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE item RECORD; old_item jsonb; attempts INTEGER=0; counts INTEGER=0; generations INTEGER=0;
BEGIN
 FOR item IN SELECT * FROM jsonb_each(NEW.attempts_json) LOOP
  attempts=attempts+1;
  IF item.key!~'^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$' OR jsonb_typeof(item.value)<>'object'
   OR NOT (item.value ?& ARRAY['request_sha256','projection_sha256','count_done','generation_done','observation']) OR item.value->'count_done' IS DISTINCT FROM 'true'::jsonb OR item.value->'generation_done' NOT IN ('true'::jsonb,'false'::jsonb)
   OR item.value->>'request_sha256'!~'^[0-9a-f]{64}$' OR item.value->>'projection_sha256'!~'^[0-9a-f]{64}$'
   OR NOT EXISTS(SELECT 1 FROM supervisor_meaning_preparations p WHERE p.attempt_id=item.key::uuid AND p.epoch_id=NEW.id) THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Meaning budget attempt invalid';
  END IF;
  IF item.value->'observation' <> 'null'::jsonb AND (
    jsonb_typeof(item.value->'observation') IS DISTINCT FROM 'object'
    OR item.value->'observation'->>'state' NOT IN ('unknown','observed','anomalous')
    OR item.value->'observation'->>'state' IS NULL
    OR item.value->'observation'->>'state' <> 'observed' AND (NOT NEW.blocked OR NEW.active_attempt_id IS DISTINCT FROM item.key::uuid)) THEN
    RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Uncertain meaning usage must remain held';
  END IF;
  counts=counts+1;
  IF item.value->'generation_done'='true'::jsonb THEN generations=generations+1; END IF;
  IF TG_OP='UPDATE' AND OLD.attempts_json ? item.key THEN
   old_item=OLD.attempts_json->item.key;
   IF item.value->'request_sha256' IS DISTINCT FROM old_item->'request_sha256' OR item.value->'projection_sha256' IS DISTINCT FROM old_item->'projection_sha256'
    OR old_item->'generation_done'='true'::jsonb AND item.value->'generation_done'<>'true'::jsonb
    OR old_item->'observation'->>'state' IN ('observed','anomalous') AND item.value->'observation' IS DISTINCT FROM old_item->'observation' THEN
    RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Meaning budget evidence is immutable';
   END IF;
  ELSIF TG_OP='UPDATE' AND OLD.active_attempt_id IS NOT NULL THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Meaning budget already active';
  END IF;
 END LOOP;
 IF attempts>2 OR NEW.reserved_nano<>attempts*50000000 OR NEW.count_requests<>counts OR NEW.generation_requests<>generations OR NEW.active_attempt_id IS NOT NULL AND NOT NEW.attempts_json ? NEW.active_attempt_id::text THEN
  RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Meaning budget totals invalid';
 END IF;
 IF TG_OP='UPDATE' THEN
  IF (NEW.id,NEW.unit_id,NEW.currency,NEW.max_nano,NEW.attempt_reserve_nano,NEW.max_attempts,NEW.price_sha256,NEW.semantic_sha256,NEW.created_at)
   IS DISTINCT FROM (OLD.id,OLD.unit_id,OLD.currency,OLD.max_nano,OLD.attempt_reserve_nano,OLD.max_attempts,OLD.price_sha256,OLD.semantic_sha256,OLD.created_at)
   OR OLD.blocked AND (NOT NEW.blocked OR NEW.count_requests<>OLD.count_requests OR NEW.generation_requests<>OLD.generation_requests OR NEW.active_attempt_id IS DISTINCT FROM OLD.active_attempt_id)
   OR OLD.active_attempt_id IS NOT NULL AND NEW.active_attempt_id IS NULL AND COALESCE(NEW.attempts_json->OLD.active_attempt_id::text->'observation'->>'state','unknown')<>'observed'
   OR NEW.reserved_nano<OLD.reserved_nano
   OR EXISTS(SELECT 1 FROM jsonb_object_keys(OLD.attempts_json) old_key WHERE NOT NEW.attempts_json ? old_key) THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Meaning budget cannot reset';
  END IF;
 END IF;
 RETURN NEW;
END $$;
"""
