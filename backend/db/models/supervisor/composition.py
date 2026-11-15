"""Fixed two-child Supervisor identity, not a money ledger or a provider grant."""
from datetime import datetime
from uuid import UUID
from sqlalchemy import CheckConstraint,DateTime,ForeignKey,LargeBinary,Text,UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped,mapped_column
from db.base import Base
from db.models._shared import uuid_pk

KEY_CONSTRAINT = 'uq_composition_owner_key'
CHECKS = {
    'digests': "octet_length(client_key_digest)=32 AND octet_length(claim_digest)=32 AND confirm_digest ~ '^[0-9a-f]{64}$' AND snapshot_sha256 ~ '^[0-9a-f]{64}$'",
    'snapshot': "(snapshot_json IS NULL AND state='redacted') OR (snapshot_json IS NOT NULL AND state<>'redacted' AND octet_length(convert_to(snapshot_json,'UTF8')) BETWEEN 2 AND 65536 AND snapshot_sha256=encode(digest(convert_to(snapshot_json,'UTF8'),'sha256'),'hex') AND snapshot_json=cf053_canonical(snapshot_json::jsonb))",
    'clock': "isfinite(request_started_at) AND isfinite(confirmed_at) AND confirmed_at>=request_started_at AND confirmed_at<admission_before AND admission_before=request_started_at+interval '15 seconds' AND deadline_at=request_started_at+interval '140 seconds' AND (claimed_at IS NULL OR isfinite(claimed_at)) AND (closed_at IS NULL OR isfinite(closed_at)) AND (analysis_as_of IS NULL OR (isfinite(analysis_as_of) AND analysis_as_of>=confirmed_at AND analysis_as_of<deadline_at))",
    'state': "(state='admitted' AND claimed_at IS NULL AND closed_at IS NULL) OR (state='claimed' AND claimed_at>=confirmed_at AND claimed_at<deadline_at AND closed_at IS NULL) OR (state='closed' AND closed_at>=confirmed_at AND (claimed_at IS NULL OR (claimed_at>=confirmed_at AND claimed_at<deadline_at))) OR (state='redacted' AND closed_at>=confirmed_at)",
    'flow': "(flow_handoff_at IS NULL AND flow_run_id IS NULL) OR (flow_handoff_at>=claimed_at AND flow_handoff_at<deadline_at AND claimed_at IS NOT NULL AND analysis_as_of IS NOT NULL)",
    'technical': "(technical_handoff_at IS NULL AND technical_run_id IS NULL) OR (technical_handoff_at>=claimed_at AND technical_handoff_at<deadline_at AND claimed_at IS NOT NULL)",
}

CHECKS = {name: '(' + value + ') IS TRUE' for name, value in CHECKS.items()}

class SupervisorComposition(Base):
    __tablename__='supervisor_compositions'
    id:Mapped[UUID]=uuid_pk()
    owner_user_id:Mapped[UUID]=mapped_column(PGUUID(as_uuid=True),ForeignKey('auth_users.id',ondelete='RESTRICT'),nullable=False)
    confirmation_session_id:Mapped[UUID]=mapped_column(PGUUID(as_uuid=True),ForeignKey('auth_sessions.id',ondelete='RESTRICT'),nullable=False)
    client_key_digest:Mapped[bytes]=mapped_column(LargeBinary,nullable=False)
    confirm_digest:Mapped[str]=mapped_column(Text,nullable=False)
    snapshot_json:Mapped[str|None]=mapped_column(Text)
    snapshot_sha256:Mapped[str]=mapped_column(Text,nullable=False)
    claim_digest:Mapped[bytes]=mapped_column(LargeBinary,nullable=False)
    request_started_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    confirmed_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    admission_before:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    deadline_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    analysis_as_of:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    claimed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    closed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    state:Mapped[str]=mapped_column(Text,nullable=False)
    flow_key_digest:Mapped[bytes|None]=mapped_column(LargeBinary)
    technical_key_digest:Mapped[bytes|None]=mapped_column(LargeBinary)
    flow_handoff_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    technical_handoff_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    flow_run_id:Mapped[UUID|None]=mapped_column(PGUUID(as_uuid=True),ForeignKey('flow_analysis_runs.id',ondelete='RESTRICT'))
    technical_run_id:Mapped[UUID|None]=mapped_column(PGUUID(as_uuid=True),ForeignKey('technical_analysis_runs.id',ondelete='RESTRICT'))
    __table_args__=(UniqueConstraint('owner_user_id','client_key_digest',name=KEY_CONSTRAINT),
                   *(CheckConstraint(value,name='composition_'+name) for name,value in CHECKS.items()))
