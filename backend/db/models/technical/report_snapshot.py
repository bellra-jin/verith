"""Immutable owned storage anchor; not an execution or usage ledger."""
from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from db.base import Base


FORMAT = 'technical.owned-snapshot.v1'
TEXT_LIMITS = {'caller_context_json':4096, 'boundary_context_json':4096,
               'caller_input_json':32768, 'input_json':16384, 'result_json':2097152}
CHECKS = {'format': "format='technical.owned-snapshot.v1'",
          'created': 'isfinite(created_at)'}
for _name, _limit in TEXT_LIMITS.items():
    CHECKS[_name] = (f"octet_length(convert_to({_name},'UTF8')) BETWEEN 2 AND {_limit} "
                     f"AND jsonb_typeof({_name}::jsonb)='object'")
for _name in ('input_sha256', 'result_sha256', 'binding_sha256'):
    CHECKS[_name] = f"{_name} ~ '^[0-9a-f]{{64}}$'"
for _name in ('input', 'result'):
    CHECKS[_name+'_hash'] = f"{_name}_sha256=encode(digest(convert_to({_name}_json,'UTF8'),'sha256'),'hex')"
CHECKS['caller_hash'] = "caller_context_json::jsonb->>'input_fingerprint'=encode(digest(convert_to(caller_input_json,'UTF8'),'sha256'),'hex')"
CHECKS['schemas'] = "((input_schema='analysis.agent.v1' AND result_schema='technical.boundary.v1' AND result_json::jsonb->>'schema_version'='analysis.agent.v1' AND result_json::jsonb->'data'->>'execution_mode'='synthetic') OR (input_schema='analysis.agent.v1' AND result_schema='technical.execution.v1' AND result_json::jsonb->>'schema_version'='technical.execution.v1' AND result_json::jsonb->'data'->>'execution_mode'='controlled')) IS TRUE"


class TechnicalReportSnapshot(Base):
    __tablename__ = 'technical_report_snapshots'
    report_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey('technical_reports.id', ondelete='CASCADE'), primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey('auth_users.id', ondelete='RESTRICT'), nullable=False)
    owner_session_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    request_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    trace_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    format: Mapped[str] = mapped_column(Text, nullable=False)
    caller_context_json: Mapped[str] = mapped_column(Text, nullable=False)
    boundary_context_json: Mapped[str] = mapped_column(Text, nullable=False)
    caller_input_json: Mapped[str] = mapped_column(Text, nullable=False)
    input_schema: Mapped[str] = mapped_column(Text, nullable=False)
    result_schema: Mapped[str] = mapped_column(Text, nullable=False)
    input_json: Mapped[str] = mapped_column(Text, nullable=False)
    result_json: Mapped[str] = mapped_column(Text, nullable=False)
    input_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    result_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    binding_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = tuple(CheckConstraint(value, name='ck_technical_snapshot_'+key) for key,value in CHECKS.items())
