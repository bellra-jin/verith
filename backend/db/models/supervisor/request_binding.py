"""Immutable confirmed plan -> fixed Flow body; never an execution ledger."""
from datetime import datetime
from uuid import UUID
from sqlalchemy import DateTime, Text, LargeBinary, ForeignKey, CheckConstraint, UniqueConstraint, ForeignKeyConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from db.base import Base
from db.models._shared import uuid_pk
KEY_CONSTRAINT = 'uq_supervisor_owner_client_key'
CHECKS = {'digests': "octet_length(client_key_digest)=32 AND octet_length(flow_key_digest)=32 AND confirm_digest ~ '^[0-9a-f]{64}$' AND plan_sha256 ~ '^[0-9a-f]{64}$' AND flow_sha256 ~ '^[0-9a-f]{64}$' AND flow_key_digest=digest(convert_to(id::text,'UTF8'),'sha256')", 'clock': "isfinite(confirmed_at) AND isfinite(handoff_before) AND handoff_before=confirmed_at+interval '120 seconds' AND (redacted_at IS NULL OR isfinite(redacted_at) AND redacted_at>=confirmed_at)", 'snapshot': "(redacted_at IS NULL AND plan_json IS NOT NULL AND flow_input_json IS NOT NULL AND octet_length(convert_to(plan_json,'UTF8')) BETWEEN 2 AND 65536 AND octet_length(convert_to(flow_input_json,'UTF8')) BETWEEN 2 AND 8192 AND jsonb_typeof(plan_json::jsonb)='object' AND jsonb_typeof(flow_input_json::jsonb)='object' AND plan_sha256=encode(digest(convert_to(plan_json,'UTF8'),'sha256'),'hex') AND flow_sha256=encode(digest(convert_to(flow_input_json,'UTF8'),'sha256'),'hex') AND flow_input_json::jsonb->>'idempotency_key'=id::text) OR (redacted_at IS NOT NULL AND plan_json IS NULL AND flow_input_json IS NULL)"}

class SupervisorRequestBinding(Base):
    __tablename__ = 'supervisor_request_bindings'
    id: Mapped[UUID] = uuid_pk()
    owner_user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey('auth_users.id', ondelete='RESTRICT'), nullable=False)
    client_key_digest: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    confirm_digest: Mapped[str] = mapped_column(Text, nullable=False)
    plan_json: Mapped[str | None] = mapped_column(Text)
    plan_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    flow_input_json: Mapped[str | None] = mapped_column(Text)
    flow_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    flow_key_digest: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    handoff_before: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    redacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    preparation_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    __table_args__ = (UniqueConstraint('id','owner_user_id',name='uq_supervisor_binding_id_owner'), UniqueConstraint('preparation_id',name='uq_supervisor_binding_preparation'), ForeignKeyConstraint(['preparation_id','owner_user_id'],['supervisor_meaning_preparations.id','supervisor_meaning_preparations.owner_user_id'],name='fk_supervisor_preparation_owner',ondelete='RESTRICT',deferrable=True,initially='DEFERRED',use_alter=True), UniqueConstraint('owner_user_id', 'client_key_digest', name=KEY_CONSTRAINT), *[CheckConstraint(v, name='supervisor_binding_' + k) for (k, v) in CHECKS.items()])
