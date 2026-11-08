"""Immutable synthetic input seal; no execution or publication state."""
from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from db.base import Base
from db.models._shared import created_at, uuid_pk

RUN_CONSTRAINT = "uq_flow_input_snapshots_run"
CHECKS = {
    "version": "contract_version = 1",
    "mode": "mode = 'synthetic_only'",
    "time": "isfinite(sealed_at)",
    "size": "octet_length(convert_to(input_json,'UTF8')) BETWEEN 1 AND 131072",
    "object": "(jsonb_typeof(input_json::jsonb) = 'object') IS TRUE",
    "body_version": "(input_json::jsonb -> 'contract_version' = '1'::jsonb) IS TRUE",
    "body_mode": "(input_json::jsonb ->> 'mode' = 'synthetic_only') IS TRUE",
    "digest": "input_sha256 ~ '^[0-9a-f]{64}$' AND input_sha256 = encode(digest(convert_to(input_json,'UTF8'),'sha256'),'hex')",
}


class FlowInputSnapshot(Base):
    __tablename__ = "flow_input_snapshots"
    id: Mapped[UUID] = uuid_pk()
    run_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    owner_user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    contract_version: Mapped[int] = mapped_column(Integer, nullable=False)
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    input_json: Mapped[str] = mapped_column(Text, nullable=False)
    input_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    sealed_at: Mapped[datetime] = created_at()
    __table_args__ = (
        UniqueConstraint("run_id", name=RUN_CONSTRAINT),
        ForeignKeyConstraint(["run_id", "owner_user_id"], ["flow_runs.id", "flow_runs.owner_user_id"], ondelete="RESTRICT", name="fk_flow_input_snapshot_owner_run"),
        *(CheckConstraint(sql, name="ck_flow_input_snapshot_" + name) for name, sql in CHECKS.items()),
    )
