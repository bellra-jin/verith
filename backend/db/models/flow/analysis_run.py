"""Live analysis ledger. Synthetic/receipt tables remain unchanged."""
from datetime import date,datetime
from uuid import UUID
from sqlalchemy import CheckConstraint,Date,DateTime,ForeignKey,LargeBinary,String,Text,UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped,mapped_column
from db.base import Base
from db.models._shared import uuid_pk

KEY_CONSTRAINT='uq_flow_analysis_owner_operation_key'
CHECKS={
 'operation':"operation='flow.analysis.v1'",
 'digests':"octet_length(key_digest)=32 AND octet_length(claim_digest)=32 AND input_fingerprint ~ '^[0-9a-f]{64}$'",
 'time':"isfinite(started_at) AND isfinite(deadline_at) AND isfinite(as_of) AND deadline_at=started_at+interval '120 seconds' AND (accepted_at IS NULL OR (isfinite(accepted_at) AND accepted_at>=started_at AND accepted_at<deadline_at))",
 'spec':"jsonb_typeof(spec_json::jsonb)='object'",
 'snapshot':"(input_json IS NULL AND result_json IS NULL) OR (octet_length(convert_to(input_json,'UTF8')) BETWEEN 2 AND 2097152 AND octet_length(convert_to(result_json,'UTF8')) BETWEEN 2 AND 2097152 AND jsonb_typeof(input_json::jsonb)='object' AND jsonb_typeof(result_json::jsonb)='object' AND input_sha256=encode(digest(convert_to(input_json,'UTF8'),'sha256'),'hex') AND result_sha256=encode(digest(convert_to(result_json,'UTF8'),'sha256'),'hex') AND (result_json::jsonb->>'report_id')=adopted_report_id::text)",
 'state':"""(state='running' AND request_json IS NOT NULL AND stock_name IS NOT NULL AND input_json IS NULL AND result_json IS NULL AND input_sha256 IS NULL AND result_sha256 IS NULL AND adopted_report_id IS NULL AND accepted_at IS NULL AND error_code IS NULL)
 OR (state IN ('failed','unknown') AND request_json IS NOT NULL AND stock_name IS NOT NULL AND input_json IS NULL AND result_json IS NULL AND input_sha256 IS NULL AND result_sha256 IS NULL AND adopted_report_id IS NULL AND accepted_at IS NULL AND error_code IS NOT NULL)
 OR (state IN ('result_ready','stored') AND request_json IS NOT NULL AND stock_name IS NOT NULL AND input_json IS NOT NULL AND result_json IS NOT NULL AND input_sha256 IS NOT NULL AND result_sha256 IS NOT NULL AND adopted_report_id IS NOT NULL AND accepted_at IS NOT NULL AND error_code IS NULL)
 OR (state='failed' AND error_code='RESULT_CONFLICT' AND request_json IS NOT NULL AND stock_name IS NOT NULL AND input_json IS NOT NULL AND result_json IS NOT NULL AND input_sha256 IS NOT NULL AND result_sha256 IS NOT NULL AND adopted_report_id IS NOT NULL AND accepted_at IS NOT NULL)
 OR (state='deleted' AND request_json IS NULL AND stock_name IS NULL AND input_json IS NULL AND result_json IS NULL AND adopted_report_id IS NOT NULL AND input_sha256 IS NOT NULL AND result_sha256 IS NOT NULL AND accepted_at IS NOT NULL AND error_code IS NULL)""",
 'request':"request_json IS NULL OR (octet_length(convert_to(request_json,'UTF8')) BETWEEN 2 AND 8192 AND jsonb_typeof(request_json::jsonb)='object' AND input_fingerprint=encode(digest(convert_to(request_json,'UTF8'),'sha256'),'hex'))",
 'identity':"ticker ~ '^[0-9]{6}$' AND (stock_name IS NULL OR length(btrim(stock_name))>0)",
}


class FlowAnalysisRun(Base):
    __tablename__='flow_analysis_runs'
    id:Mapped[UUID]=uuid_pk()
    owner_user_id:Mapped[UUID]=mapped_column(PGUUID(as_uuid=True),ForeignKey('auth_users.id',ondelete='RESTRICT'),nullable=False)
    operation:Mapped[str]=mapped_column(Text,nullable=False)
    key_digest:Mapped[bytes]=mapped_column(LargeBinary,nullable=False)
    input_fingerprint:Mapped[str]=mapped_column(String(64),nullable=False)
    admission_request_id:Mapped[UUID]=mapped_column(PGUUID(as_uuid=True),nullable=False)
    attempt_id:Mapped[UUID]=mapped_column(PGUUID(as_uuid=True),nullable=False)
    ticker:Mapped[str]=mapped_column(String(6),nullable=False)
    stock_name:Mapped[str|None]=mapped_column(Text)
    as_of:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    candidate_date:Mapped[date]=mapped_column(Date,nullable=False)
    request_json:Mapped[str|None]=mapped_column(Text)
    spec_json:Mapped[str]=mapped_column(Text,nullable=False)
    claim_digest:Mapped[bytes]=mapped_column(LargeBinary,nullable=False)
    started_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    deadline_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    accepted_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    state:Mapped[str]=mapped_column(Text,nullable=False)
    error_code:Mapped[str|None]=mapped_column(Text)
    adopted_report_id:Mapped[UUID|None]=mapped_column(PGUUID(as_uuid=True))
    input_json:Mapped[str|None]=mapped_column(Text)
    input_sha256:Mapped[str|None]=mapped_column(String(64))
    result_json:Mapped[str|None]=mapped_column(Text)
    result_sha256:Mapped[str|None]=mapped_column(String(64))
    __table_args__=(UniqueConstraint('owner_user_id','operation','key_digest',name=KEY_CONSTRAINT),
        UniqueConstraint('attempt_id',name='uq_flow_analysis_attempt'),
        UniqueConstraint('adopted_report_id',name='uq_flow_analysis_report'),
        *(CheckConstraint(value,name='ck_flow_analysis_'+key) for key,value in CHECKS.items()))
