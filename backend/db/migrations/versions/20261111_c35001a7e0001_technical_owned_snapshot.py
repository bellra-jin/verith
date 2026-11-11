"""Add owned Technical storage without adopting or rewriting legacy reports."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'c35001a7e0001'
down_revision = 'c23001a7e0001'
branch_labels = None
depends_on = None

# Frozen migration definitions; do not import a mutable application model.
LIMITS = {'caller_context_json':4096, 'boundary_context_json':4096,
          'caller_input_json':32768, 'input_json':16384, 'result_json':2097152}
CHECKS = {'format': "format='technical.owned-snapshot.v1'", 'created': 'isfinite(created_at)'}
for name,limit in LIMITS.items():
    CHECKS[name] = f"octet_length(convert_to({name},'UTF8')) BETWEEN 2 AND {limit} AND jsonb_typeof({name}::jsonb)='object'"
for name in ('input_sha256','result_sha256','binding_sha256'):
    CHECKS[name] = f"{name} ~ '^[0-9a-f]{{64}}$'"
for name in ('input','result'):
    CHECKS[name+'_hash'] = f"{name}_sha256=encode(digest(convert_to({name}_json,'UTF8'),'sha256'),'hex')"
CHECKS['caller_hash'] = "caller_context_json::jsonb->>'input_fingerprint'=encode(digest(convert_to(caller_input_json,'UTF8'),'sha256'),'hex')"
CHECKS['schemas'] = "input_schema='analysis.agent.v1' AND result_schema='technical.boundary.v1'"


def upgrade():
    op.add_column('technical_reports', sa.Column('owner_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('auth_users.id', ondelete='RESTRICT'), nullable=True))
    op.create_index('ix_technical_reports_owner_id', 'technical_reports', ['owner_user_id','id'])
    op.execute('LOCK TABLE agent_reports IN SHARE ROW EXCLUSIVE MODE')
    if op.get_bind().execute(sa.text("SELECT EXISTS(SELECT 1 FROM agent_reports WHERE agent_type='technical' AND owner_user_id IS NOT NULL GROUP BY agent_report_id HAVING count(*)>1)")).scalar():
        raise RuntimeError('Owned Technical index conflict; legacy data preserved')
    op.create_index('uq_technical_owned_agent_report', 'agent_reports', ['agent_type','agent_report_id'], unique=True, postgresql_where=sa.text("agent_type='technical' AND owner_user_id IS NOT NULL"))
    columns = [sa.Column('report_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('technical_reports.id', ondelete='CASCADE'), primary_key=True),
               sa.Column('owner_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('auth_users.id', ondelete='RESTRICT'), nullable=False),
               sa.Column('owner_session_id', postgresql.UUID(as_uuid=True), nullable=False),
               sa.Column('request_id', postgresql.UUID(as_uuid=True), nullable=False), sa.Column('trace_id', postgresql.UUID(as_uuid=True), nullable=False)]
    for name in ('format',*LIMITS,'input_schema','result_schema','input_sha256','result_sha256','binding_sha256'):
        columns.append(sa.Column(name, sa.Text(), nullable=False))
    columns.append(sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_table('technical_report_snapshots', *columns,
                    *(sa.CheckConstraint(value,name='ck_technical_snapshot_'+key) for key,value in CHECKS.items()))
    op.execute("""CREATE FUNCTION cf035_snapshot_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='Technical snapshot is immutable'; END; $$""")
    op.execute('CREATE TRIGGER cf035_snapshot_guard BEFORE UPDATE ON technical_report_snapshots FOR EACH ROW EXECUTE FUNCTION cf035_snapshot_immutable()')


def downgrade():
    op.execute('LOCK TABLE technical_reports,technical_report_snapshots,agent_reports IN ACCESS EXCLUSIVE MODE')
    if op.get_bind().execute(sa.text("SELECT EXISTS(SELECT 1 FROM technical_report_snapshots) OR EXISTS(SELECT 1 FROM technical_reports WHERE owner_user_id IS NOT NULL) OR EXISTS(SELECT 1 FROM agent_reports WHERE agent_type='technical' AND owner_user_id IS NOT NULL)")).scalar():
        raise RuntimeError('Owned Technical storage cannot be downgraded')
    op.drop_table('technical_report_snapshots')
    op.execute('DROP FUNCTION cf035_snapshot_immutable()')
    op.drop_index('uq_technical_owned_agent_report',table_name='agent_reports')
    op.drop_index('ix_technical_reports_owner_id',table_name='technical_reports')
    op.drop_column('technical_reports','owner_user_id')
