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


# Old Flow CHECK text remains the exact branch of each new conditional CHECK.
OLD_CHECKS=dict(CHECKS)
TECHNICAL_FIELDS=('technical_intent_json','technical_intent_sha256','technical_key_digest',
 'technical_configuration_json','technical_configuration_sha256','technical_policy_sha256',
 'technical_spec_sha256','technical_stock_json','technical_stock_sha256',
 'technical_confirmation_session_id','technical_run_id','technical_run_json')
CHECKS['digests']="((target='flow' AND ("+OLD_CHECKS['digests']+")) OR (target='technical' AND octet_length(client_key_digest)=32 AND confirm_digest ~ '^[0-9a-f]{64}$' AND plan_sha256 ~ '^[0-9a-f]{64}$' AND technical_intent_sha256 ~ '^[0-9a-f]{64}$' AND technical_key_digest=digest(convert_to('supervisor.technical-core.1:'||id::text,'UTF8'),'sha256') AND technical_configuration_sha256=encode(digest(convert_to(technical_configuration_json,'UTF8'),'sha256'),'hex') AND technical_stock_sha256=encode(digest(convert_to(technical_stock_json,'UTF8'),'sha256'),'hex') AND technical_policy_sha256 ~ '^[0-9a-f]{64}$' AND technical_spec_sha256='b526fffe2e3c2ccce4c2c6a75f259bb61d82349ae2ceda16347b7b20f3d21e88')) IS TRUE"
CHECKS['snapshot']="((target='flow' AND ("+OLD_CHECKS['snapshot']+")) OR (target='technical' AND ((redacted_at IS NULL AND plan_json IS NOT NULL AND technical_intent_json IS NOT NULL AND octet_length(convert_to(plan_json,'UTF8')) BETWEEN 2 AND 65536 AND octet_length(convert_to(technical_intent_json,'UTF8')) BETWEEN 2 AND 16384 AND plan_sha256=encode(digest(convert_to(plan_json,'UTF8'),'sha256'),'hex') AND technical_intent_sha256=encode(digest(convert_to(technical_intent_json,'UTF8'),'sha256'),'hex')) OR (redacted_at IS NOT NULL AND plan_json IS NULL AND technical_intent_json IS NULL)))) IS TRUE"
CHECKS['target']="((target='flow' AND "+' AND '.join(n+' IS NULL' for n in TECHNICAL_FIELDS)+") OR (target='technical' AND flow_input_json IS NULL AND flow_sha256 IS NULL AND flow_key_digest IS NULL AND preparation_id IS NULL AND technical_confirmation_session_id IS NOT NULL AND octet_length(convert_to(technical_configuration_json,'UTF8')) BETWEEN 2 AND 32768 AND octet_length(convert_to(technical_stock_json,'UTF8')) BETWEEN 2 AND 4096 AND ((technical_run_id IS NULL AND technical_run_json IS NULL) OR (technical_run_id IS NOT NULL AND octet_length(convert_to(technical_run_json,'UTF8')) BETWEEN 2 AND 8192)))) IS TRUE"

CHECKS['canonical'] = "(target='flow' OR (technical_configuration_json=cf053_canonical(technical_configuration_json::jsonb) AND technical_stock_json=cf053_canonical(technical_stock_json::jsonb) AND (technical_intent_json IS NULL OR technical_intent_json=cf053_canonical(technical_intent_json::jsonb)) AND (plan_json IS NULL OR plan_json=cf053_canonical(plan_json::jsonb)) AND (technical_run_json IS NULL OR technical_run_json=cf053_canonical(technical_run_json::jsonb)))) IS TRUE"

class SupervisorRequestBinding(Base):
    __tablename__ = 'supervisor_request_bindings'
    id: Mapped[UUID] = uuid_pk()
    owner_user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey('auth_users.id', ondelete='RESTRICT'), nullable=False)
    client_key_digest: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    confirm_digest: Mapped[str] = mapped_column(Text, nullable=False)
    plan_json: Mapped[str | None] = mapped_column(Text)
    plan_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    flow_input_json: Mapped[str | None] = mapped_column(Text)
    flow_sha256: Mapped[str | None] = mapped_column(Text)
    flow_key_digest: Mapped[bytes | None] = mapped_column(LargeBinary)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    handoff_before: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    redacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    preparation_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    target: Mapped[str] = mapped_column(Text, nullable=False, server_default='flow')
    technical_intent_json: Mapped[str | None] = mapped_column(Text)
    technical_intent_sha256: Mapped[str | None] = mapped_column(Text)
    technical_configuration_json: Mapped[str | None] = mapped_column(Text)
    technical_configuration_sha256: Mapped[str | None] = mapped_column(Text)
    technical_policy_sha256: Mapped[str | None] = mapped_column(Text)
    technical_spec_sha256: Mapped[str | None] = mapped_column(Text)
    technical_stock_json: Mapped[str | None] = mapped_column(Text)
    technical_stock_sha256: Mapped[str | None] = mapped_column(Text)
    technical_run_json: Mapped[str | None] = mapped_column(Text)
    technical_key_digest: Mapped[bytes | None] = mapped_column(LargeBinary)
    technical_confirmation_session_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    technical_run_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    __table_args__ = (ForeignKeyConstraint(['technical_run_id','owner_user_id'],['technical_analysis_runs.id','technical_analysis_runs.owner_user_id'],name='fk_supervisor_technical_run_owner',ondelete='RESTRICT'), UniqueConstraint('id','owner_user_id',name='uq_supervisor_binding_id_owner'), UniqueConstraint('preparation_id',name='uq_supervisor_binding_preparation'), ForeignKeyConstraint(['preparation_id','owner_user_id'],['supervisor_meaning_preparations.id','supervisor_meaning_preparations.owner_user_id'],name='fk_supervisor_preparation_owner',ondelete='RESTRICT',deferrable=True,initially='DEFERRED',use_alter=True), UniqueConstraint('owner_user_id', 'client_key_digest', name=KEY_CONSTRAINT), *[CheckConstraint(v, name='supervisor_binding_' + k) for (k, v) in CHECKS.items()])
