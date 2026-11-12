"""Independent durable accounting, never a production dispatch authority."""
from datetime import datetime
from uuid import UUID
from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, text, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from db.base import Base
from db.models._shared import uuid_pk

ACCOUNT_CHECKS = {
 'policy_binding': "(policy_json::jsonb->>'currency'='USD' AND policy_json::jsonb->>'operation'=operation AND policy_json::jsonb->>'scope'=scope_json AND (policy_json::jsonb->>'limit_nano')::bigint=limit_nano AND (policy_json::jsonb->>'attempt_nano')::bigint=attempt_nano AND (policy_json::jsonb->>'max_attempts')::bigint=max_attempts AND (policy_json::jsonb->>'starts_at')::timestamptz=starts_at AND (policy_json::jsonb->>'ends_at')::timestamptz=ends_at) IS TRUE",
 'text': "length(operation) BETWEEN 1 AND 128 AND octet_length(scope_json) BETWEEN 2 AND 16384 AND jsonb_typeof(scope_json::jsonb)='object' AND octet_length(policy_json) BETWEEN 2 AND 16384 AND jsonb_typeof(policy_json::jsonb)='object'",
 'hash': "scope_sha256 ~ '^[0-9a-f]{64}$' AND policy_sha256 ~ '^[0-9a-f]{64}$' AND scope_sha256=encode(digest(convert_to(scope_json,'UTF8'),'sha256'),'hex') AND policy_sha256=encode(digest(convert_to(policy_json,'UTF8'),'sha256'),'hex')",
 'clock': 'isfinite(starts_at) AND isfinite(ends_at) AND ends_at>starts_at',
 'limits': 'limit_nano>0 AND attempt_nano>0 AND attempt_nano<=limit_nano AND max_attempts>0 AND reserved_nano BETWEEN 0 AND limit_nano AND attempts BETWEEN 0 AND max_attempts AND observed_nano>=0 AND observed_nano<=reserved_nano',
}
RESERVATION_CHECKS = {
 'row_binding': "(binding_json::jsonb->>'preparation_id'=preparation_id::text AND binding_json::jsonb->>'attempt_id'=attempt_id::text AND binding_json::jsonb->>'session_id'=owner_session_id::text AND (binding_json::jsonb->>'expires_at')::timestamptz=expires_at) IS TRUE",
 'state': "state IN ('held','observed','unknown','anomalous') AND ((state='held' AND receipt_sha256 IS NULL AND receipt_json IS NULL AND estimated_nano IS NULL) OR (state<>'held' AND receipt_sha256 IS NOT NULL AND receipt_json IS NOT NULL)) AND ((state='observed')=(estimated_nano IS NOT NULL))",
 'values': "reserved_nano>0 AND (estimated_nano IS NULL OR estimated_nano BETWEEN 0 AND reserved_nano) AND isfinite(expires_at)",
 'binding': "octet_length(binding_json) BETWEEN 2 AND 16384 AND jsonb_typeof(binding_json::jsonb)='object' AND binding_sha256 ~ '^[0-9a-f]{64}$' AND binding_sha256=encode(digest(convert_to(binding_json,'UTF8'),'sha256'),'hex')",
 'receipt': "receipt_json IS NULL OR (octet_length(receipt_json) BETWEEN 2 AND 16384 AND jsonb_typeof(receipt_json::jsonb)='object' AND receipt_sha256 ~ '^[0-9a-f]{64}$' AND receipt_sha256=encode(digest(convert_to(receipt_json,'UTF8'),'sha256'),'hex'))",
}
class SupervisorMeaningAccount(Base):
    __tablename__='supervisor_meaning_accounts'
    id: Mapped[UUID]=uuid_pk()
    owner_user_id: Mapped[UUID]=mapped_column(PGUUID(as_uuid=True),ForeignKey('auth_users.id',ondelete='RESTRICT'),nullable=False)
    operation: Mapped[str]=mapped_column(Text,nullable=False)
    scope_json: Mapped[str]=mapped_column(Text,nullable=False)
    scope_sha256: Mapped[str]=mapped_column(Text,nullable=False)
    policy_json: Mapped[str]=mapped_column(Text,nullable=False)
    policy_sha256: Mapped[str]=mapped_column(Text,nullable=False)
    starts_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    ends_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    limit_nano: Mapped[int]=mapped_column(BigInteger,nullable=False)
    attempt_nano: Mapped[int]=mapped_column(BigInteger,nullable=False)
    max_attempts: Mapped[int]=mapped_column(BigInteger,nullable=False)
    reserved_nano: Mapped[int]=mapped_column(BigInteger,nullable=False)
    attempts: Mapped[int]=mapped_column(BigInteger,nullable=False)
    observed_nano: Mapped[int]=mapped_column(BigInteger,nullable=False)
    blocked: Mapped[bool]=mapped_column(Boolean,nullable=False)
    __table_args__=(Index('uq_meaning_account_canonical_scope','operation','owner_user_id',text('(scope_json::jsonb)'),unique=True),UniqueConstraint('operation','owner_user_id','scope_sha256',name='uq_meaning_account_scope'),UniqueConstraint('id','owner_user_id',name='uq_meaning_account_owner'),*(CheckConstraint(v,name='cf044_account_'+k) for k,v in ACCOUNT_CHECKS.items()))

class SupervisorMeaningReservation(Base):
    __tablename__='supervisor_meaning_reservations'
    id: Mapped[UUID]=uuid_pk()
    account_id: Mapped[UUID]=mapped_column(PGUUID(as_uuid=True),nullable=False)
    owner_user_id: Mapped[UUID]=mapped_column(PGUUID(as_uuid=True),nullable=False)
    owner_session_id: Mapped[UUID]=mapped_column(PGUUID(as_uuid=True),ForeignKey('auth_sessions.id',ondelete='RESTRICT'),nullable=False)
    preparation_id: Mapped[UUID]=mapped_column(PGUUID(as_uuid=True),nullable=False)
    attempt_id: Mapped[UUID]=mapped_column(PGUUID(as_uuid=True),nullable=False,unique=True)
    binding_json: Mapped[str]=mapped_column(Text,nullable=False)
    binding_sha256: Mapped[str]=mapped_column(Text,nullable=False)
    expires_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    reserved_nano: Mapped[int]=mapped_column(BigInteger,nullable=False)
    state: Mapped[str]=mapped_column(Text,nullable=False)
    receipt_json: Mapped[str|None]=mapped_column(Text)
    receipt_sha256: Mapped[str|None]=mapped_column(Text)
    estimated_nano: Mapped[int|None]=mapped_column(BigInteger)
    __table_args__=(UniqueConstraint('preparation_id',name='uq_meaning_reservation_preparation'),ForeignKeyConstraint(['account_id','owner_user_id'],['supervisor_meaning_accounts.id','supervisor_meaning_accounts.owner_user_id'],ondelete='RESTRICT'),ForeignKeyConstraint(['preparation_id','owner_user_id'],['supervisor_meaning_preparations.id','supervisor_meaning_preparations.owner_user_id'],ondelete='RESTRICT'),*(CheckConstraint(v,name='cf044_reservation_'+k) for k,v in RESERVATION_CHECKS.items()))

# A grant is server metadata until an atomic phase receipt has committed.
GRANT_CHECKS={
 'identity': "binding_sha256=encode(digest(convert_to(binding_json,'UTF8'),'sha256'),'hex') AND counter_sha256=encode(digest(convert_to(counter_json,'UTF8'),'sha256'),'hex') AND principal_sha256 ~ '^[0-9a-f]{64}$' AND nonce_sha256 ~ '^[0-9a-f]{64}$' AND policy_sha256 ~ '^[0-9a-f]{64}$' AND scope_sha256 ~ '^[0-9a-f]{64}$'",
 'binding': "(binding_json::jsonb->>'preparation_id'=preparation_id::text AND binding_json::jsonb->>'attempt_id'=attempt_id::text AND binding_json::jsonb->>'session_id'=owner_session_id::text) IS TRUE AND octet_length(binding_json) BETWEEN 2 AND 16384 AND octet_length(counter_json) BETWEEN 2 AND 16384",
 'clock': 'isfinite(created_at) AND isfinite(deadline_at) AND deadline_at>created_at',
 'phases': "(count_receipt IS NULL)=(reservation_id IS NULL) AND (count_receipt IS NULL)=(provider_request_sha256 IS NULL) AND (count_receipt IS NULL)=(provider_projection_sha256 IS NULL) AND (generation_receipt IS NULL OR count_receipt IS NOT NULL) AND (terminal_sha256 IS NULL OR count_receipt IS NOT NULL)",
 'receipts': "(count_receipt IS NULL OR (octet_length(count_receipt)<=8192 AND jsonb_typeof(count_receipt::jsonb)='object')) AND (generation_receipt IS NULL OR (octet_length(generation_receipt)<=8192 AND jsonb_typeof(generation_receipt::jsonb)='object')) AND (terminal_sha256 IS NULL OR terminal_sha256 ~ '^[0-9a-f]{64}$') AND (provider_request_sha256 IS NULL OR provider_request_sha256 ~ '^[0-9a-f]{64}$') AND (provider_projection_sha256 IS NULL OR provider_projection_sha256 ~ '^[0-9a-f]{64}$')",
}
class SupervisorMeaningGrant(Base):
    __tablename__='supervisor_meaning_grants'
    id: Mapped[UUID]=uuid_pk()
    owner_user_id: Mapped[UUID]=mapped_column(PGUUID(as_uuid=True),nullable=False)
    owner_session_id: Mapped[UUID]=mapped_column(PGUUID(as_uuid=True),ForeignKey('auth_sessions.id',ondelete='RESTRICT'),nullable=False)
    preparation_id: Mapped[UUID]=mapped_column(PGUUID(as_uuid=True),nullable=False,unique=True)
    attempt_id: Mapped[UUID]=mapped_column(PGUUID(as_uuid=True),nullable=False,unique=True)
    account_id: Mapped[UUID]=mapped_column(PGUUID(as_uuid=True),nullable=False)
    reservation_id: Mapped[UUID|None]=mapped_column(PGUUID(as_uuid=True))
    principal_sha256: Mapped[str]=mapped_column(Text,nullable=False)
    nonce_sha256: Mapped[str]=mapped_column(Text,nullable=False,unique=True)
    policy_sha256: Mapped[str]=mapped_column(Text,nullable=False)
    scope_sha256: Mapped[str]=mapped_column(Text,nullable=False)
    binding_json: Mapped[str]=mapped_column(Text,nullable=False)
    binding_sha256: Mapped[str]=mapped_column(Text,nullable=False)
    counter_json: Mapped[str]=mapped_column(Text,nullable=False)
    counter_sha256: Mapped[str]=mapped_column(Text,nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    deadline_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    provider_request_sha256: Mapped[str|None]=mapped_column(Text)
    provider_projection_sha256: Mapped[str|None]=mapped_column(Text)
    count_receipt: Mapped[str|None]=mapped_column(Text)
    generation_receipt: Mapped[str|None]=mapped_column(Text)
    terminal_sha256: Mapped[str|None]=mapped_column(Text)
    __table_args__=(ForeignKeyConstraint(['account_id','owner_user_id'],['supervisor_meaning_accounts.id','supervisor_meaning_accounts.owner_user_id'],ondelete='RESTRICT'),ForeignKeyConstraint(['preparation_id','owner_user_id'],['supervisor_meaning_preparations.id','supervisor_meaning_preparations.owner_user_id'],ondelete='RESTRICT'),ForeignKeyConstraint(['reservation_id','account_id','owner_user_id','preparation_id','attempt_id'],['supervisor_meaning_reservations.id','supervisor_meaning_reservations.account_id','supervisor_meaning_reservations.owner_user_id','supervisor_meaning_reservations.preparation_id','supervisor_meaning_reservations.attempt_id'],ondelete='RESTRICT'),*(CheckConstraint(v,name='cf045_grant_'+k) for k,v in GRANT_CHECKS.items()))

SupervisorMeaningReservation.__table__.append_constraint(UniqueConstraint('id','account_id','owner_user_id','preparation_id','attempt_id',name='uq_meaning_reservation_grant'))
