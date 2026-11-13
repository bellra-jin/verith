"""Explicit v2 native inputs; retain v1 scope/key/read semantics and native guards."""
from pathlib import Path
import importlib.util
from alembic import op
import sqlalchemy as sa
revision='c61001a7e0001'
down_revision='c60001a7e0001'
branch_labels=None
depends_on=None

_path=Path(__file__).with_name('20261113_c60001_supervisor_composition.py')
_spec=importlib.util.spec_from_file_location('_composition_v1_guard',_path)
_old=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_old)
OLD_GUARD='CREATE OR REPLACE FUNCTION c60001_guard()'+_old.GUARD.split('CREATE OR REPLACE FUNCTION c60001_guard()',1)[1]
assert OLD_GUARD.count("snapshot->>'schema_version'='supervisor.composition.v1'")==1
GUARD=OLD_GUARD.replace("snapshot->>'schema_version'='supervisor.composition.v1'", "snapshot->>'schema_version' IN ('supervisor.composition.v1','supervisor.composition.v2')")
PROJECTION="""
  IF snapshot->>'schema_version'='supervisor.composition.v2' THEN
   IF (snapshot->'child_inputs') IS DISTINCT FROM
       (CASE WHEN views ? 'flow' THEN jsonb_build_object('flow',jsonb_build_object(
          'operation','flow.analysis.v1','ticker',snapshot->'stock'->>'stock_code',
          'question',snapshot->'draft'->>'original_query')) ELSE '{}'::jsonb END ||
        CASE WHEN views ? 'technical' THEN jsonb_build_object('technical',jsonb_build_object(
          'operation','technical.analysis.v1','ticker',snapshot->'stock'->>'stock_code',
          'original_query',(snapshot->'stock'->>'stock_code')||' 차트','requested_views','["technical"]'::jsonb,
          'conditions',jsonb_build_object('profile','technical.multiframe.v1','periods','["3m","1y","5y"]'::jsonb))) ELSE '{}'::jsonb END) THEN
    RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='Composition native projection invalid';
   END IF;
  END IF;
"""
_anchor="  IF NEW.technical_run_id IS NOT NULL AND (TG_OP='INSERT' OR NEW.technical_run_id IS DISTINCT FROM OLD.technical_run_id) THEN"
assert GUARD.count(_anchor)==1
GUARD=GUARD.replace(_anchor,PROJECTION+_anchor)
assert GUARD.count("AND native.execution_configuration_json=snapshot->>'technical_configuration')")==1
GUARD=GUARD.replace("AND native.execution_configuration_json=snapshot->>'technical_configuration')", """AND native.execution_configuration_json=snapshot->>'technical_configuration'
      AND (snapshot->>'schema_version'='supervisor.composition.v1' OR
       native.intent_sha256=encode(digest(convert_to(cf053_canonical(snapshot->'child_inputs'->'technical'),'UTF8'),'sha256'),'hex')))""")


def upgrade():
    op.execute('LOCK TABLE supervisor_compositions IN SHARE ROW EXCLUSIVE MODE')
    op.execute(GUARD)


def downgrade():
    op.execute('LOCK TABLE supervisor_compositions IN ACCESS EXCLUSIVE MODE')
    if op.get_bind().execute(sa.text('SELECT EXISTS(SELECT 1 FROM supervisor_compositions)')).scalar():
        # Redacted scope cannot be reclassified as v1; never silently discard a
        # consumed v2 projection or reconstruct grants across a downgrade.
        raise RuntimeError('Composition history retained')
    op.execute(OLD_GUARD)
