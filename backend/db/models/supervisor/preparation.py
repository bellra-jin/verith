"""Short-lived meaning preparation and one fixed verifier budget, never a Flow ledger."""
from datetime import datetime
from uuid import UUID
from sqlalchemy import (BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Integer, LargeBinary, Text, UniqueConstraint)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from db.base import Base
from db.models._shared import uuid_pk

PREPARATION_CHECKS = {'identity': "octet_length(prepare_key_digest)=32 AND request_digest ~ '^[0-9a-f]{64}$' AND draft_digest ~ '^[0-9a-f]{64}$' AND semantic_sha256 ~ '^[0-9a-f]{64}$' AND semantic_sha256=encode(digest(convert_to(semantic_json,'UTF8'),'sha256'),'hex') AND jsonb_typeof(semantic_json::jsonb)='object'", 'clock': "isfinite(created_at) AND isfinite(expires_at) AND expires_at>created_at AND expires_at<=created_at+interval '10 minutes' AND (redacted_at IS NULL OR isfinite(redacted_at) AND redacted_at>=created_at)", 'lineage': 'depth BETWEEN 0 AND 4 AND ((parent_id IS NULL AND root_id=id AND depth=0) OR (parent_id IS NOT NULL AND parent_id<>id AND root_id<>id AND depth>0))', 'state': "state IN ('pending','ready','clarification','unsupported','failed','unknown','expired','deleted','consumed') AND ((state='consumed')=(consumed_binding_id IS NOT NULL)) AND (state NOT IN ('expired','deleted','consumed') OR (redacted_at IS NOT NULL AND draft_json IS NULL AND frame_json IS NULL AND plan_json IS NULL AND continuation_json IS NULL))", 'root_only': 'parent_id IS NULL OR (draft_json IS NULL AND frame_json IS NULL AND plan_json IS NULL)', 'json': "(draft_json IS NULL OR (octet_length(convert_to(draft_json,'UTF8'))<=16384 AND jsonb_typeof(draft_json::jsonb)='object')) AND (frame_json IS NULL OR (octet_length(convert_to(frame_json,'UTF8'))<=65536 AND jsonb_typeof(frame_json::jsonb)='object' AND frame_sha256 IS NOT NULL AND frame_sha256=encode(digest(convert_to(frame_json,'UTF8'),'sha256'),'hex'))) AND (plan_json IS NULL OR (octet_length(convert_to(plan_json,'UTF8'))<=65536 AND jsonb_typeof(plan_json::jsonb)='object' AND plan_sha256 IS NOT NULL AND plan_sha256=encode(digest(convert_to(plan_json,'UTF8'),'sha256'),'hex'))) AND (continuation_json IS NULL OR (octet_length(convert_to(continuation_json,'UTF8'))<=8192 AND jsonb_typeof(continuation_json::jsonb)='object' AND NOT continuation_json::jsonb ?| ARRAY['original_query','answers','frame','plan']))", 'completion': "state NOT IN ('ready','clarification','unsupported') OR (plan_sha256 IS NOT NULL AND plan_sha256 ~ '^[0-9a-f]{64}$' AND ((parent_id IS NULL AND draft_json IS NOT NULL AND frame_json IS NOT NULL AND plan_json IS NOT NULL) OR (parent_id IS NOT NULL AND continuation_json IS NOT NULL)))"}
EPOCH_CHECKS = {'fixed': "unit_id='CF023' AND currency='USD' AND max_nano=100000000 AND attempt_reserve_nano=50000000 AND max_attempts=2 AND price_sha256 ~ '^[0-9a-f]{64}$' AND semantic_sha256 ~ '^[0-9a-f]{64}$'", 'limits': 'reserved_nano BETWEEN 0 AND 100000000 AND count_requests BETWEEN 0 AND 2 AND generation_requests BETWEEN 0 AND 2 AND generation_requests<=count_requests', 'ledger': "jsonb_typeof(attempts_json)='object' AND octet_length(attempts_json::text)<=16384"}


class SupervisorMeaningEpoch(Base):
    __tablename__ = 'supervisor_meaning_test_epochs'
    id: Mapped[UUID] = uuid_pk()
    unit_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    currency: Mapped[str] = mapped_column(Text, nullable=False)
    max_nano: Mapped[int] = mapped_column(BigInteger, nullable=False)
    attempt_reserve_nano: Mapped[int] = mapped_column(BigInteger, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    price_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    semantic_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    reserved_nano: Mapped[int] = mapped_column(BigInteger, nullable=False)
    count_requests: Mapped[int] = mapped_column(Integer, nullable=False)
    generation_requests: Mapped[int] = mapped_column(Integer, nullable=False)
    blocked: Mapped[bool] = mapped_column(Boolean, nullable=False)
    active_attempt_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    attempts_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = tuple(CheckConstraint(value, name='cf023_epoch_'+name) for name, value in EPOCH_CHECKS.items())


class SupervisorMeaningPreparation(Base):
    __tablename__ = 'supervisor_meaning_preparations'
    id: Mapped[UUID] = uuid_pk()
    owner_user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey('auth_users.id', ondelete='RESTRICT'), nullable=False)
    prepare_key_digest: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    request_digest: Mapped[str] = mapped_column(Text, nullable=False)
    draft_digest: Mapped[str] = mapped_column(Text, nullable=False)
    semantic_json: Mapped[str] = mapped_column(Text, nullable=False)
    semantic_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    root_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    parent_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    depth: Mapped[int] = mapped_column(Integer, nullable=False)
    attempt_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, unique=True)
    epoch_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey('supervisor_meaning_test_epochs.id', ondelete='RESTRICT'))
    state: Mapped[str] = mapped_column(Text, nullable=False)
    meaning_status: Mapped[str] = mapped_column(Text, nullable=False)
    draft_json: Mapped[str | None] = mapped_column(Text)
    frame_json: Mapped[str | None] = mapped_column(Text)
    frame_sha256: Mapped[str | None] = mapped_column(Text)
    plan_json: Mapped[str | None] = mapped_column(Text)
    plan_sha256: Mapped[str | None] = mapped_column(Text)
    continuation_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    redacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consumed_binding_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    __table_args__ = (
        UniqueConstraint('owner_user_id','prepare_key_digest',name='uq_meaning_owner_prepare_key'),
        UniqueConstraint('id','owner_user_id',name='uq_meaning_id_owner'),
        ForeignKeyConstraint(['parent_id','owner_user_id'],['supervisor_meaning_preparations.id','supervisor_meaning_preparations.owner_user_id'],name='fk_meaning_parent_owner',ondelete='RESTRICT',deferrable=True,initially='DEFERRED'),
        ForeignKeyConstraint(['root_id','owner_user_id'],['supervisor_meaning_preparations.id','supervisor_meaning_preparations.owner_user_id'],name='fk_meaning_root_owner',ondelete='RESTRICT',deferrable=True,initially='DEFERRED'),
        ForeignKeyConstraint(['consumed_binding_id','owner_user_id'],['supervisor_request_bindings.id','supervisor_request_bindings.owner_user_id'],name='fk_meaning_consumed_owner',ondelete='RESTRICT',deferrable=True,initially='DEFERRED',use_alter=True),
        *(CheckConstraint(value,name='cf023_preparation_'+name) for name,value in PREPARATION_CHECKS.items()),
    )
