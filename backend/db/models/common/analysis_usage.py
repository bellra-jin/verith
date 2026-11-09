"""Minimal Flow-adopted accounting; no report, prompt or credential bodies."""
from datetime import datetime
from uuid import UUID
from sqlalchemy import BigInteger,Boolean,CheckConstraint,DateTime,ForeignKey,ForeignKeyConstraint,Index,LargeBinary,String,Text,UniqueConstraint,text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped,mapped_column
from db.base import Base
from db.models._shared import uuid_pk

PERIOD_CHECKS={
 'scope':"(scope='user' AND owner_user_id IS NOT NULL AND budget_limit_nano IS NULL AND user_request_limit IS NULL) OR (scope='service' AND owner_user_id IS NULL AND budget_limit_nano IS NOT NULL AND budget_limit_nano>0 AND user_request_limit IS NOT NULL AND user_request_limit>0)",
 'identity':"operation='flow.analysis.v1' AND currency='USD' AND isfinite(period_start) AND isfinite(period_end) AND period_end=period_start+interval '24 hours' AND (period_start AT TIME ZONE 'Asia/Seoul')::time=time '00:00:00'",
 'amounts':"request_limit>0 AND request_count>=0 AND request_count<=request_limit AND held_nano>=0 AND estimated_spend_nano>=0",
}
RESERVATION_CHECKS = {'policy': 'operation=\'flow.analysis.v1\' AND currency=\'USD\' AND price_id=\'openai.gpt-5.4-mini.standard.2026-11-09.v1\' AND max_nano=913500000 AND policy_json::jsonb=\'{"cached_nano": 75, "currency": "USD", "input_nano": 750, "input_token_cap": 400000, "kis_data_cap": 4, "kis_retry_in_data_cap": 2, "kis_token_cap": 2, "model": "gpt-5.4-mini", "n": 1, "openai_call_cap": 3, "output_byte_cap": 16384, "output_nano": 4500, "output_token_cap": 1000, "price_id": "openai.gpt-5.4-mini.standard.2026-11-09.v1", "prompt_byte_cap": 32768, "response_models": ["gpt-5.4-mini", "gpt-5.4-mini-2026-03-17"], "service_tier": "default", "version": "flow.usage.v1"}\'::jsonb', 'amounts': 'remaining_nano>=0 AND remaining_nano<=max_nano AND estimated_spend_nano>=0', 'state': "state IN ('held','unknown','settled','blocked') AND (state<>'settled' OR remaining_nano=0)", 'identity': 'octet_length(claim_digest)=32 AND user_period_id<>service_period_id'}
CALL_CHECKS={
 'slot':"(provider='openai' AND action='completion' AND ordinal BETWEEN 1 AND 3 AND reserved_nano=304500000) OR (provider='kis' AND action IN ('token','supply','quotes') AND ordinal BETWEEN 1 AND 2 AND reserved_nano=0)",
 'state':"state IN ('unknown','observed','not_called','anomalous') AND (state<>'observed' OR attempted IS TRUE) AND (state<>'not_called' OR attempted IS FALSE)",
 'amounts':"released_nano IN (0,reserved_nano) AND (estimated_nano IS NULL OR estimated_nano>=0) AND (provider<>'kis' OR estimated_nano IS NULL)",
 'numbers':"(input_tokens IS NULL OR input_tokens>=0) AND (cached_tokens IS NULL OR (input_tokens IS NOT NULL AND cached_tokens>=0 AND cached_tokens<=input_tokens)) AND (output_tokens IS NULL OR output_tokens>=0) AND (input_bytes IS NULL OR input_bytes>=0) AND (output_bytes IS NULL OR output_bytes>=0) AND (http_status IS NULL OR http_status BETWEEN 100 AND 599)",
 'model':"response_model IS NULL OR response_model IN ('gpt-5.4-mini','gpt-5.4-mini-2026-03-17')",
 'digests':"(evidence_sha256 IS NULL OR evidence_sha256 ~ '^[0-9a-f]{64}$') AND (model_sha256 IS NULL OR model_sha256 ~ '^[0-9a-f]{64}$')",
 'reason':"reason IN ('UNOBSERVED','NOT_CALLED','HTTP_OBSERVED','USAGE_OBSERVED','CACHE_UNREPORTED','USAGE_INVALID','MODEL_MISMATCH','CAP_EXCEEDED','PRICE_MISMATCH','ACCOUNTING_OVERFLOW')",
}


class AnalysisUsagePeriod(Base):
    __tablename__='analysis_usage_periods'
    id:Mapped[UUID]=uuid_pk()
    scope:Mapped[str]=mapped_column(Text,nullable=False)
    owner_user_id:Mapped[UUID|None]=mapped_column(PGUUID(as_uuid=True),ForeignKey('auth_users.id',ondelete='RESTRICT'))
    operation:Mapped[str]=mapped_column(Text,nullable=False)
    currency:Mapped[str]=mapped_column(String(3),nullable=False)
    period_start:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    period_end:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    request_limit:Mapped[int]=mapped_column(BigInteger,nullable=False)
    budget_limit_nano:Mapped[int|None]=mapped_column(BigInteger)
    user_request_limit:Mapped[int|None]=mapped_column(BigInteger)
    request_count:Mapped[int]=mapped_column(BigInteger,nullable=False)
    held_nano:Mapped[int]=mapped_column(BigInteger,nullable=False)
    estimated_spend_nano:Mapped[int]=mapped_column(BigInteger,nullable=False)
    blocked:Mapped[bool]=mapped_column(Boolean,nullable=False)
    __table_args__=(
        Index('uq_usage_service_period','operation','currency','period_start','period_end',unique=True,postgresql_where=text("scope='service'")),
        Index('uq_usage_user_period','owner_user_id','operation','currency','period_start','period_end',unique=True,postgresql_where=text("scope='user'")),
        *(CheckConstraint(v,name='ck_usage_period_'+k) for k,v in PERIOD_CHECKS.items()))


class AnalysisUsageReservation(Base):
    __tablename__='analysis_usage_reservations'
    id:Mapped[UUID]=mapped_column(PGUUID(as_uuid=True),primary_key=True)
    owner_user_id:Mapped[UUID]=mapped_column(PGUUID(as_uuid=True),nullable=False)
    operation:Mapped[str]=mapped_column(Text,nullable=False)
    attempt_id:Mapped[UUID]=mapped_column(PGUUID(as_uuid=True),nullable=False)
    claim_digest:Mapped[bytes]=mapped_column(LargeBinary,nullable=False)
    user_period_id:Mapped[UUID]=mapped_column(PGUUID(as_uuid=True),ForeignKey('analysis_usage_periods.id',ondelete='RESTRICT'),nullable=False)
    service_period_id:Mapped[UUID]=mapped_column(PGUUID(as_uuid=True),ForeignKey('analysis_usage_periods.id',ondelete='RESTRICT'),nullable=False)
    currency:Mapped[str]=mapped_column(String(3),nullable=False)
    price_id:Mapped[str]=mapped_column(Text,nullable=False)
    policy_json:Mapped[str]=mapped_column(Text,nullable=False)
    max_nano:Mapped[int]=mapped_column(BigInteger,nullable=False)
    remaining_nano:Mapped[int]=mapped_column(BigInteger,nullable=False)
    estimated_spend_nano:Mapped[int]=mapped_column(BigInteger,nullable=False)
    state:Mapped[str]=mapped_column(Text,nullable=False)
    __table_args__=(UniqueConstraint('id','owner_user_id','operation','attempt_id','claim_digest',name='uq_usage_reservation_identity'),
        UniqueConstraint('attempt_id',name='uq_usage_reservation_attempt'),
        ForeignKeyConstraint(['id','owner_user_id','operation','attempt_id','claim_digest'],
            ['flow_analysis_runs.id','flow_analysis_runs.owner_user_id','flow_analysis_runs.operation','flow_analysis_runs.attempt_id','flow_analysis_runs.claim_digest'],
            name='fk_usage_reservation_run',deferrable=True,initially='DEFERRED',use_alter=True),
        *(CheckConstraint(v,name='ck_usage_reservation_'+k) for k,v in RESERVATION_CHECKS.items()))


class AnalysisProviderCall(Base):
    __tablename__='analysis_provider_calls'
    id:Mapped[UUID]=mapped_column(PGUUID(as_uuid=True),primary_key=True)
    reservation_id:Mapped[UUID]=mapped_column(PGUUID(as_uuid=True),ForeignKey('analysis_usage_reservations.id',ondelete='RESTRICT'),nullable=False)
    provider:Mapped[str]=mapped_column(Text,nullable=False)
    action:Mapped[str]=mapped_column(Text,nullable=False)
    ordinal:Mapped[int]=mapped_column(BigInteger,nullable=False)
    reserved_nano:Mapped[int]=mapped_column(BigInteger,nullable=False)
    released_nano:Mapped[int]=mapped_column(BigInteger,nullable=False)
    attempted:Mapped[bool|None]=mapped_column(Boolean)
    state:Mapped[str]=mapped_column(Text,nullable=False)
    input_tokens:Mapped[int|None]=mapped_column(BigInteger)
    cached_tokens:Mapped[int|None]=mapped_column(BigInteger)
    output_tokens:Mapped[int|None]=mapped_column(BigInteger)
    input_bytes:Mapped[int|None]=mapped_column(BigInteger)
    output_bytes:Mapped[int|None]=mapped_column(BigInteger)
    response_model:Mapped[str|None]=mapped_column(Text)
    model_sha256:Mapped[str|None]=mapped_column(String(64))
    http_status:Mapped[int|None]=mapped_column(BigInteger)
    estimated_nano:Mapped[int|None]=mapped_column(BigInteger)
    reason:Mapped[str]=mapped_column(Text,nullable=False)
    evidence_sha256:Mapped[str|None]=mapped_column(String(64))
    __table_args__=(UniqueConstraint('reservation_id','provider','action','ordinal',name='uq_usage_call_slot'),
        *(CheckConstraint(v,name='ck_usage_call_'+k) for k,v in CALL_CHECKS.items()))
