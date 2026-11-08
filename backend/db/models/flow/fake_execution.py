"""One immutable grant and at most one terminal synthetic artifact per input."""
from datetime import datetime
from uuid import UUID
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from db.base import Base
from db.models._shared import uuid_pk

INPUT_CONSTRAINT = "uq_flow_fake_execution_input"
CHECKS = {
    "version": "contract_version = 1",
    "engine": "engine_id = 'flow.fake.summary.v1'",
    "claim": "octet_length(claim_digest) = 32",
    "time": "isfinite(started_at) AND isfinite(deadline_at) AND deadline_at - started_at = interval '10 seconds'",
    "status": "status IN ('running','succeeded','failed','timed_out')",
    "terminal_time": "finished_at IS NULL OR (isfinite(finished_at) AND finished_at >= started_at)",
    "combination": """(status='running' AND finished_at IS NULL AND result_json IS NULL AND result_sha256 IS NULL AND error_code IS NULL)
        OR (status='succeeded' AND finished_at IS NOT NULL AND finished_at < deadline_at AND result_json IS NOT NULL AND result_sha256 IS NOT NULL AND error_code IS NULL)
        OR (status='failed' AND finished_at IS NOT NULL AND result_json IS NULL AND result_sha256 IS NULL AND error_code IS NOT NULL AND error_code IN ('fake_failed','result_invalid'))
        OR (status='timed_out' AND finished_at IS NOT NULL AND result_json IS NULL AND result_sha256 IS NULL AND error_code IS NOT NULL AND error_code IN ('coroutine_timeout','deadline_expired'))""",
    "result": """result_json IS NULL OR (octet_length(convert_to(result_json,'UTF8')) BETWEEN 1 AND 131072
        AND (jsonb_typeof(result_json::jsonb)='object') IS TRUE
        AND (result_json::jsonb->'contract_version'='1'::jsonb) IS TRUE
        AND (result_json::jsonb->>'mode'='synthetic_only') IS TRUE
        AND (result_json::jsonb->>'execution_id'=id::text) IS TRUE
        AND (result_json::jsonb->>'input_snapshot_id'=input_snapshot_id::text) IS TRUE
        AND result_sha256 ~ '^[0-9a-f]{64}$'
        AND result_sha256=encode(digest(convert_to(result_json,'UTF8'),'sha256'),'hex'))""",
}


class FlowFakeExecution(Base):
    __tablename__ = "flow_fake_executions"
    id: Mapped[UUID] = uuid_pk()
    input_snapshot_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("flow_input_snapshots.id", ondelete="RESTRICT"), nullable=False)
    contract_version: Mapped[int] = mapped_column(Integer, nullable=False)
    engine_id: Mapped[str] = mapped_column(Text, nullable=False)
    claim_digest: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_json: Mapped[str | None] = mapped_column(Text)
    result_sha256: Mapped[str | None] = mapped_column(String(64))
    error_code: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (UniqueConstraint("input_snapshot_id", name=INPUT_CONSTRAINT),
                      *(CheckConstraint(value, name="ck_flow_fake_"+name) for name, value in CHECKS.items()))
