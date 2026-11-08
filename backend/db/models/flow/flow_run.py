"""A durable receipt only. No worker may claim these rows."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base
from db.models._shared import created_at, uuid_pk

KEY_CONSTRAINT = "uq_flow_runs_owner_operation_key"


class FlowRun(Base):
    __tablename__ = "flow_runs"

    id: Mapped[UUID] = uuid_pk()
    owner_user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("auth_users.id", ondelete="RESTRICT"), nullable=False)
    operation: Mapped[str] = mapped_column(Text, nullable=False)
    request_contract_version: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key_digest: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    request_input: Mapped[dict] = mapped_column(JSONB, nullable=False)
    admission_request_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    attempt_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    admission_mode: Mapped[str] = mapped_column(Text, nullable=False)
    execution_status: Mapped[str] = mapped_column(Text, nullable=False)
    storage_status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = created_at()

    __table_args__ = (
        UniqueConstraint("owner_user_id", "operation", "idempotency_key_digest", name=KEY_CONSTRAINT),
        UniqueConstraint("attempt_id", name="uq_flow_runs_attempt_id"),
        CheckConstraint("operation = 'flow'", name="ck_flow_run_operation"),
        CheckConstraint("request_contract_version = 1", name="ck_flow_run_version"),
        CheckConstraint("octet_length(idempotency_key_digest) = 32", name="ck_flow_run_key_digest"),
        CheckConstraint("input_fingerprint ~ '^[0-9a-f]{64}$'", name="ck_flow_run_fingerprint"),
        CheckConstraint("jsonb_typeof(request_input) = 'object'", name="ck_flow_run_input_object"),
        CheckConstraint("admission_mode = 'receipt_only'", name="ck_flow_run_receipt_only"),
        CheckConstraint("execution_status = 'pending'", name="ck_flow_run_pending"),
        CheckConstraint("storage_status = 'not_stored'", name="ck_flow_run_not_stored"),
        CheckConstraint("isfinite(created_at)", name="ck_flow_run_created_at"),
    )
