"""Dedicated Technical admission/hold records, never Flow accounting rows."""
from datetime import date, datetime
from uuid import UUID
from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Date, DateTime,
    ForeignKey, ForeignKeyConstraint, Index, LargeBinary, Text, UniqueConstraint)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from db.base import Base
from db.models._shared import uuid_pk

PERIOD_CHECKS = {
    'operation': "operation='technical.analysis.v1'",
    'clock': "isfinite(period_start) AND isfinite(period_end) AND period_end=period_start+interval '24 hours' AND (period_start AT TIME ZONE 'Asia/Seoul')::date=kst_date AND (period_start AT TIME ZONE 'Asia/Seoul')::time=time '00:00:00'",
    'limits': 'user_request_limit>0 AND request_limit>=user_request_limit AND request_count BETWEEN 0 AND request_limit AND budget_limit_nano>0 AND attempt_reserve_nano>0 AND attempt_reserve_nano<=budget_limit_nano AND reserved_nano BETWEEN 0 AND budget_limit_nano',
    'policy': "(octet_length(policy_json) BETWEEN 2 AND 16384 AND jsonb_typeof(policy_json::jsonb)='object' AND policy_sha256 ~ '^[0-9a-f]{64}$' AND policy_sha256=encode(digest(convert_to(policy_json,'UTF8'),'sha256'),'hex') AND policy_json::jsonb->>'operation'=operation AND policy_json::jsonb->>'currency'='USD' AND policy_json::jsonb->>'enabled'='true' AND (policy_json::jsonb->>'user_daily_limit')::bigint=user_request_limit AND (policy_json::jsonb->>'service_daily_limit')::bigint=request_limit AND (policy_json::jsonb->>'daily_budget_nano')::bigint=budget_limit_nano AND (policy_json::jsonb->>'attempt_reserve_nano')::bigint=attempt_reserve_nano AND jsonb_typeof(policy_json::jsonb->'supported_tickers')='array' AND jsonb_array_length(policy_json::jsonb->'supported_tickers')>0) IS TRUE",
    'price_caps': "(policy_json::jsonb->>'model' ~ '^[A-Za-z0-9_.:-]{1,128}$' AND policy_json::jsonb->>'service_tier'='default' AND policy_json::jsonb->>'price_id' ~ '^[A-Za-z0-9_.:-]{1,128}$' AND policy_json::jsonb->>'price_evidence_sha256' ~ '^[0-9a-f]{64}$' AND (policy_json::jsonb->>'deadline_seconds')::bigint BETWEEN 1 AND 86400 AND (policy_json::jsonb->>'input_byte_cap')::bigint>0 AND (policy_json::jsonb->>'output_byte_cap')::bigint>0 AND (policy_json::jsonb->>'input_token_cap')::bigint>0 AND (policy_json::jsonb->>'output_token_cap')::bigint>0 AND (policy_json::jsonb->>'input_nano_per_token')::bigint>0 AND (policy_json::jsonb->>'output_nano_per_token')::bigint>0 AND (policy_json::jsonb->>'max_calls')::bigint>0 AND (policy_json::jsonb->>'max_calls')::numeric*((policy_json::jsonb->>'input_token_cap')::numeric*(policy_json::jsonb->>'input_nano_per_token')::numeric+(policy_json::jsonb->>'output_token_cap')::numeric*(policy_json::jsonb->>'output_nano_per_token')::numeric)<=attempt_reserve_nano) IS TRUE",
}
PERIOD_CHECKS['integer_policy'] = "(jsonb_typeof(policy_json::jsonb->'enabled')='boolean' AND (jsonb_typeof(policy_json::jsonb->'user_daily_limit')='number' AND policy_json::jsonb->>'user_daily_limit' ~ '^[1-9][0-9]*$') AND (jsonb_typeof(policy_json::jsonb->'service_daily_limit')='number' AND policy_json::jsonb->>'service_daily_limit' ~ '^[1-9][0-9]*$') AND (jsonb_typeof(policy_json::jsonb->'daily_budget_nano')='number' AND policy_json::jsonb->>'daily_budget_nano' ~ '^[1-9][0-9]*$') AND (jsonb_typeof(policy_json::jsonb->'attempt_reserve_nano')='number' AND policy_json::jsonb->>'attempt_reserve_nano' ~ '^[1-9][0-9]*$') AND (jsonb_typeof(policy_json::jsonb->'deadline_seconds')='number' AND policy_json::jsonb->>'deadline_seconds' ~ '^[1-9][0-9]*$') AND (jsonb_typeof(policy_json::jsonb->'input_nano_per_token')='number' AND policy_json::jsonb->>'input_nano_per_token' ~ '^[1-9][0-9]*$') AND (jsonb_typeof(policy_json::jsonb->'output_nano_per_token')='number' AND policy_json::jsonb->>'output_nano_per_token' ~ '^[1-9][0-9]*$') AND (jsonb_typeof(policy_json::jsonb->'input_token_cap')='number' AND policy_json::jsonb->>'input_token_cap' ~ '^[1-9][0-9]*$') AND (jsonb_typeof(policy_json::jsonb->'output_token_cap')='number' AND policy_json::jsonb->>'output_token_cap' ~ '^[1-9][0-9]*$') AND (jsonb_typeof(policy_json::jsonb->'input_byte_cap')='number' AND policy_json::jsonb->>'input_byte_cap' ~ '^[1-9][0-9]*$') AND (jsonb_typeof(policy_json::jsonb->'output_byte_cap')='number' AND policy_json::jsonb->>'output_byte_cap' ~ '^[1-9][0-9]*$') AND (jsonb_typeof(policy_json::jsonb->'max_calls')='number' AND policy_json::jsonb->>'max_calls' ~ '^[1-9][0-9]*$')) IS TRUE"
RUN_CHECKS = {
    'operation': "operation='technical.analysis.v1'",
    'hashes': "octet_length(key_digest)=32 AND octet_length(claim_digest)=32 AND intent_sha256 ~ '^[0-9a-f]{64}$' AND policy_sha256 ~ '^[0-9a-f]{64}$' AND stock_sha256 ~ '^[0-9a-f]{64}$' AND spec_sha256 ~ '^[0-9a-f]{64}$' AND stock_sha256=encode(digest(convert_to(stock_json,'UTF8'),'sha256'),'hex') AND spec_sha256=encode(digest(convert_to(spec_json,'UTF8'),'sha256'),'hex')",
    'clock': 'isfinite(as_of) AND isfinite(started_at) AND isfinite(deadline_at) AND as_of=started_at AND deadline_at>started_at AND (claim_consumed_at IS NULL OR (isfinite(claim_consumed_at) AND claim_consumed_at>=started_at AND claim_consumed_at<deadline_at)) AND (redacted_at IS NULL OR (isfinite(redacted_at) AND redacted_at>=started_at))',
    'hold': 'reserved_nano>0 AND held_nano=reserved_nano',
    'stock': "(ticker ~ '^[0-9]{6}$' AND octet_length(stock_json) BETWEEN 2 AND 4096 AND jsonb_typeof(stock_json::jsonb)='object' AND stock_json::jsonb->>'stock_code'=ticker AND jsonb_typeof(stock_json::jsonb->'stock_name')='string' AND length(btrim(stock_json::jsonb->>'stock_name')) BETWEEN 1 AND 200) IS TRUE",
    'spec': "(octet_length(spec_json) BETWEEN 2 AND 4096 AND jsonb_typeof(spec_json::jsonb)='object' AND spec_json::jsonb->>'version'='technical.admission.v1' AND spec_json::jsonb->>'operation'=operation AND spec_json::jsonb->>'boundary'='technical.boundary.v1' AND spec_json::jsonb->>'storage'='technical.owned-stage.v1' AND spec_json::jsonb->'provider_authority'='false'::jsonb AND spec_json::jsonb->'settlement'='false'::jsonb) IS TRUE",
    'intent': "intent_json IS NULL OR (octet_length(intent_json) BETWEEN 2 AND 16384 AND jsonb_typeof(intent_json::jsonb)='object' AND intent_sha256=encode(digest(convert_to(intent_json,'UTF8'),'sha256'),'hex') AND intent_json::jsonb->>'operation'=operation AND intent_json::jsonb->>'ticker'=ticker AND jsonb_typeof(intent_json::jsonb->'original_query')='string' AND length(btrim(intent_json::jsonb->>'original_query')) BETWEEN 1 AND 2000 AND intent_json::jsonb->'requested_views'='[\"technical\"]'::jsonb AND intent_json::jsonb->'conditions'='{\"profile\":\"technical.multiframe.v1\",\"periods\":[\"3m\",\"1y\",\"5y\"]}'::jsonb) IS TRUE",
    'state': "(state='admitted' AND claim_consumed_at IS NULL AND intent_json IS NOT NULL AND redacted_at IS NULL AND unknown_reason IS NULL) OR (state='claimed' AND claim_consumed_at IS NOT NULL AND intent_json IS NOT NULL AND redacted_at IS NULL AND unknown_reason IS NULL) OR (state='unknown' AND intent_json IS NULL AND redacted_at IS NOT NULL AND unknown_reason IN ('EXPIRED','CANCELLED','TIMEOUT','REDACTED','DISPATCH_UNCERTAIN','STOCK_CHANGED'))",
}
_IDS = ('id','admission_request_id','attempt_id','planned_report_id','boundary_request_id','trace_id')
RUN_CHECKS['distinct_ids'] = ' AND '.join(a+'<>'+b for i,a in enumerate(_IDS) for b in _IDS[i+1:])
RUN_CHECKS['state'] = '('+RUN_CHECKS['state']+') IS TRUE'
RUN_CHECKS['nonzero_ids'] = ' AND '.join(key+"<>'00000000-0000-0000-0000-000000000000'::uuid" for key in _IDS)


class TechnicalUsagePeriod(Base):
    __tablename__ = 'technical_usage_periods'
    id: Mapped[UUID] = uuid_pk()
    operation: Mapped[str] = mapped_column(Text, nullable=False)
    kst_date: Mapped[date] = mapped_column(Date, nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    policy_json: Mapped[str] = mapped_column(Text, nullable=False)
    policy_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    user_request_limit: Mapped[int] = mapped_column(BigInteger, nullable=False)
    request_limit: Mapped[int] = mapped_column(BigInteger, nullable=False)
    budget_limit_nano: Mapped[int] = mapped_column(BigInteger, nullable=False)
    attempt_reserve_nano: Mapped[int] = mapped_column(BigInteger, nullable=False)
    request_count: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reserved_nano: Mapped[int] = mapped_column(BigInteger, nullable=False)
    blocked: Mapped[bool] = mapped_column(Boolean, nullable=False)
    __table_args__ = (
        UniqueConstraint('operation','kst_date',name='uq_technical_usage_day'),
        UniqueConstraint('id','policy_sha256',name='uq_technical_period_policy'),
        *(CheckConstraint(value,name='cf048_period_'+key) for key,value in PERIOD_CHECKS.items()),
    )


class TechnicalAnalysisRun(Base):
    __tablename__ = 'technical_analysis_runs'
    id: Mapped[UUID] = uuid_pk()
    owner_user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True),ForeignKey('auth_users.id',ondelete='RESTRICT'),nullable=False)
    # Historical identity, deliberately not a new FK blocking session retention.
    admission_session_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True),nullable=False)
    period_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True),nullable=False)
    operation: Mapped[str] = mapped_column(Text,nullable=False)
    key_digest: Mapped[bytes] = mapped_column(LargeBinary,nullable=False)
    intent_json: Mapped[str | None] = mapped_column(Text)
    intent_sha256: Mapped[str] = mapped_column(Text,nullable=False)
    policy_sha256: Mapped[str] = mapped_column(Text,nullable=False)
    spec_json: Mapped[str] = mapped_column(Text,nullable=False)
    spec_sha256: Mapped[str] = mapped_column(Text,nullable=False)
    stock_json: Mapped[str] = mapped_column(Text,nullable=False)
    stock_sha256: Mapped[str] = mapped_column(Text,nullable=False)
    ticker: Mapped[str] = mapped_column(Text,nullable=False)
    admission_request_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True),nullable=False,unique=True)
    attempt_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True),nullable=False,unique=True)
    planned_report_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True),nullable=False,unique=True)
    boundary_request_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True),nullable=False,unique=True)
    trace_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True),nullable=False,unique=True)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True),nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),nullable=False)
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),nullable=False)
    claim_digest: Mapped[bytes] = mapped_column(LargeBinary,nullable=False)
    claim_consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reserved_nano: Mapped[int] = mapped_column(BigInteger,nullable=False)
    held_nano: Mapped[int] = mapped_column(BigInteger,nullable=False)
    state: Mapped[str] = mapped_column(Text,nullable=False)
    unknown_reason: Mapped[str | None] = mapped_column(Text)
    redacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint('owner_user_id','operation','key_digest',name='uq_technical_analysis_key'),
        ForeignKeyConstraint(['period_id','policy_sha256'],['technical_usage_periods.id','technical_usage_periods.policy_sha256'],ondelete='RESTRICT',name='fk_technical_run_period_policy'),
        Index('ix_technical_run_period_owner','period_id','owner_user_id'),
        *(CheckConstraint(value,name='cf048_run_'+key) for key,value in RUN_CHECKS.items()),
    )
