"""Add per-preparation server grant; existing rows and policies are unchanged."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
revision='c45001a7e0001'
down_revision='c44001a7e0001'
branch_labels=None
depends_on=None
GRANT_CHECKS={'identity': "binding_sha256=encode(digest(convert_to(binding_json,'UTF8'),'sha256'),'hex') AND counter_sha256=encode(digest(convert_to(counter_json,'UTF8'),'sha256'),'hex') AND principal_sha256 ~ '^[0-9a-f]{64}$' AND nonce_sha256 ~ '^[0-9a-f]{64}$' AND policy_sha256 ~ '^[0-9a-f]{64}$' AND scope_sha256 ~ '^[0-9a-f]{64}$'", 'binding': "(binding_json::jsonb->>'preparation_id'=preparation_id::text AND binding_json::jsonb->>'attempt_id'=attempt_id::text AND binding_json::jsonb->>'session_id'=owner_session_id::text) IS TRUE AND octet_length(binding_json) BETWEEN 2 AND 16384 AND octet_length(counter_json) BETWEEN 2 AND 16384", 'clock': 'isfinite(created_at) AND isfinite(deadline_at) AND deadline_at>created_at', 'phases': '(count_receipt IS NULL)=(reservation_id IS NULL) AND (count_receipt IS NULL)=(provider_request_sha256 IS NULL) AND (count_receipt IS NULL)=(provider_projection_sha256 IS NULL) AND (generation_receipt IS NULL OR count_receipt IS NOT NULL) AND (terminal_sha256 IS NULL OR count_receipt IS NOT NULL)', 'receipts': "(count_receipt IS NULL OR (octet_length(count_receipt)<=8192 AND jsonb_typeof(count_receipt::jsonb)='object')) AND (generation_receipt IS NULL OR (octet_length(generation_receipt)<=8192 AND jsonb_typeof(generation_receipt::jsonb)='object')) AND (terminal_sha256 IS NULL OR terminal_sha256 ~ '^[0-9a-f]{64}$') AND (provider_request_sha256 IS NULL OR provider_request_sha256 ~ '^[0-9a-f]{64}$') AND (provider_projection_sha256 IS NULL OR provider_projection_sha256 ~ '^[0-9a-f]{64}$')"}

def upgrade():
    op.create_unique_constraint('uq_meaning_reservation_grant','supervisor_meaning_reservations',['id','account_id','owner_user_id','preparation_id','attempt_id'])
    op.create_table('supervisor_meaning_grants',
        sa.Column('id',UUID(as_uuid=True),primary_key=True),
        *(sa.Column(n,UUID(as_uuid=True),nullable=False) for n in ('owner_user_id','owner_session_id','preparation_id','attempt_id','account_id')),
        sa.Column('reservation_id',UUID(as_uuid=True)),
        *(sa.Column(n,sa.Text(),nullable=False) for n in ('principal_sha256','nonce_sha256','policy_sha256','scope_sha256','binding_json','binding_sha256','counter_json','counter_sha256')),
        *(sa.Column(n,sa.DateTime(timezone=True),nullable=False) for n in ('created_at','deadline_at')),
        *(sa.Column(n,sa.Text()) for n in ('provider_request_sha256','provider_projection_sha256','count_receipt','generation_receipt','terminal_sha256')),
        sa.UniqueConstraint('preparation_id'),sa.UniqueConstraint('attempt_id'),sa.UniqueConstraint('nonce_sha256'),
        sa.ForeignKeyConstraint(['owner_session_id'],['auth_sessions.id'],ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['account_id','owner_user_id'],['supervisor_meaning_accounts.id','supervisor_meaning_accounts.owner_user_id'],ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['preparation_id','owner_user_id'],['supervisor_meaning_preparations.id','supervisor_meaning_preparations.owner_user_id'],ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['reservation_id','account_id','owner_user_id','preparation_id','attempt_id'],['supervisor_meaning_reservations.id','supervisor_meaning_reservations.account_id','supervisor_meaning_reservations.owner_user_id','supervisor_meaning_reservations.preparation_id','supervisor_meaning_reservations.attempt_id'],ondelete='RESTRICT'),
        *(sa.CheckConstraint(v,name='cf045_grant_'+k) for k,v in GRANT_CHECKS.items()))

def downgrade():
    op.execute('LOCK TABLE supervisor_meaning_grants IN ACCESS EXCLUSIVE MODE')
    if op.get_bind().execute(sa.text('SELECT EXISTS(SELECT 1 FROM supervisor_meaning_grants)')).scalar():
        raise RuntimeError('Supervisor grants populated; downgrade denied')
    op.drop_table('supervisor_meaning_grants')
    op.drop_constraint('uq_meaning_reservation_grant','supervisor_meaning_reservations',type_='unique')
