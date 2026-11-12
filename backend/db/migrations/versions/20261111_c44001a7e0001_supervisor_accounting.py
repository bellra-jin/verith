"""Add independent Supervisor accounting without rewriting existing records."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
revision='c44001a7e0001'
down_revision='c35001a7e0001'
branch_labels=None
depends_on=None
ACCOUNT_CHECKS={'policy_binding': "(policy_json::jsonb->>'currency'='USD' AND policy_json::jsonb->>'operation'=operation AND policy_json::jsonb->>'scope'=scope_json AND (policy_json::jsonb->>'limit_nano')::bigint=limit_nano AND (policy_json::jsonb->>'attempt_nano')::bigint=attempt_nano AND (policy_json::jsonb->>'max_attempts')::bigint=max_attempts AND (policy_json::jsonb->>'starts_at')::timestamptz=starts_at AND (policy_json::jsonb->>'ends_at')::timestamptz=ends_at) IS TRUE", 'text': "length(operation) BETWEEN 1 AND 128 AND octet_length(scope_json) BETWEEN 2 AND 16384 AND jsonb_typeof(scope_json::jsonb)='object' AND octet_length(policy_json) BETWEEN 2 AND 16384 AND jsonb_typeof(policy_json::jsonb)='object'", 'hash': "scope_sha256 ~ '^[0-9a-f]{64}$' AND policy_sha256 ~ '^[0-9a-f]{64}$' AND scope_sha256=encode(digest(convert_to(scope_json,'UTF8'),'sha256'),'hex') AND policy_sha256=encode(digest(convert_to(policy_json,'UTF8'),'sha256'),'hex')", 'clock': 'isfinite(starts_at) AND isfinite(ends_at) AND ends_at>starts_at', 'limits': 'limit_nano>0 AND attempt_nano>0 AND attempt_nano<=limit_nano AND max_attempts>0 AND reserved_nano BETWEEN 0 AND limit_nano AND attempts BETWEEN 0 AND max_attempts AND observed_nano>=0 AND observed_nano<=reserved_nano'}
RESERVATION_CHECKS={'row_binding': "(binding_json::jsonb->>'preparation_id'=preparation_id::text AND binding_json::jsonb->>'attempt_id'=attempt_id::text AND binding_json::jsonb->>'session_id'=owner_session_id::text AND (binding_json::jsonb->>'expires_at')::timestamptz=expires_at) IS TRUE", 'state': "state IN ('held','observed','unknown','anomalous') AND ((state='held' AND receipt_sha256 IS NULL AND receipt_json IS NULL AND estimated_nano IS NULL) OR (state<>'held' AND receipt_sha256 IS NOT NULL AND receipt_json IS NOT NULL)) AND ((state='observed')=(estimated_nano IS NOT NULL))", 'values': 'reserved_nano>0 AND (estimated_nano IS NULL OR estimated_nano BETWEEN 0 AND reserved_nano) AND isfinite(expires_at)', 'binding': "octet_length(binding_json) BETWEEN 2 AND 16384 AND jsonb_typeof(binding_json::jsonb)='object' AND binding_sha256 ~ '^[0-9a-f]{64}$' AND binding_sha256=encode(digest(convert_to(binding_json,'UTF8'),'sha256'),'hex')", 'receipt': "receipt_json IS NULL OR (octet_length(receipt_json) BETWEEN 2 AND 16384 AND jsonb_typeof(receipt_json::jsonb)='object' AND receipt_sha256 ~ '^[0-9a-f]{64}$' AND receipt_sha256=encode(digest(convert_to(receipt_json,'UTF8'),'sha256'),'hex'))"}

def upgrade():
    op.create_table('supervisor_meaning_accounts',
        sa.Column('id',UUID(as_uuid=True),primary_key=True),
        sa.Column('owner_user_id',UUID(as_uuid=True),sa.ForeignKey('auth_users.id',ondelete='RESTRICT'),nullable=False),
        *(sa.Column(n,sa.Text(),nullable=False) for n in ('operation','scope_json','scope_sha256','policy_json','policy_sha256')),
        *(sa.Column(n,sa.DateTime(timezone=True),nullable=False) for n in ('starts_at','ends_at')),
        *(sa.Column(n,sa.BigInteger(),nullable=False) for n in ('limit_nano','attempt_nano','max_attempts','reserved_nano','attempts','observed_nano')),
        sa.Column('blocked',sa.Boolean(),nullable=False),
        sa.UniqueConstraint('operation','owner_user_id','scope_sha256',name='uq_meaning_account_scope'),sa.UniqueConstraint('id','owner_user_id',name='uq_meaning_account_owner'),
        *(sa.CheckConstraint(v,name='cf044_account_'+k) for k,v in ACCOUNT_CHECKS.items()))
    op.create_index('uq_meaning_account_canonical_scope','supervisor_meaning_accounts',['operation','owner_user_id',sa.text('(scope_json::jsonb)')],unique=True)
    op.create_table('supervisor_meaning_reservations',
        sa.Column('id',UUID(as_uuid=True),primary_key=True),
        *(sa.Column(n,UUID(as_uuid=True),nullable=False) for n in ('account_id','owner_user_id','preparation_id')),
        sa.Column('owner_session_id',UUID(as_uuid=True),sa.ForeignKey('auth_sessions.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('attempt_id',UUID(as_uuid=True),nullable=False,unique=True),
        *(sa.Column(n,sa.Text(),nullable=False) for n in ('binding_json','binding_sha256','state')),
        sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False),sa.Column('reserved_nano',sa.BigInteger(),nullable=False),
        sa.Column('receipt_json',sa.Text()),sa.Column('receipt_sha256',sa.Text()),sa.Column('estimated_nano',sa.BigInteger()),
        sa.UniqueConstraint('preparation_id',name='uq_meaning_reservation_preparation'),
        sa.ForeignKeyConstraint(['account_id','owner_user_id'],['supervisor_meaning_accounts.id','supervisor_meaning_accounts.owner_user_id'],ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['preparation_id','owner_user_id'],['supervisor_meaning_preparations.id','supervisor_meaning_preparations.owner_user_id'],ondelete='RESTRICT'),
        *(sa.CheckConstraint(v,name='cf044_reservation_'+k) for k,v in RESERVATION_CHECKS.items()))

def downgrade():
    op.execute('LOCK TABLE supervisor_meaning_accounts,supervisor_meaning_reservations IN ACCESS EXCLUSIVE MODE')
    if op.get_bind().execute(sa.text('SELECT EXISTS(SELECT 1 FROM supervisor_meaning_accounts) OR EXISTS(SELECT 1 FROM supervisor_meaning_reservations)')).scalar():
        raise RuntimeError('Supervisor accounting populated; downgrade denied')
    op.drop_table('supervisor_meaning_reservations')
    op.drop_table('supervisor_meaning_accounts')
