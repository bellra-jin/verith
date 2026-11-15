"""Technical grant/start/evidence SQL, no policy defaults or execution replay."""
from sqlalchemy import select,update
from db.models.technical.execution_admission import TechnicalAnalysisRun as Run
from db.models.auth.models import AuthSession
from src.modules.technical.infrastructure import execution_admission_repository as admission

async def hint(session,analysis_id,grant_digest):
    return await session.scalar(select(Run).where(Run.id==analysis_id,Run.execution_grant_digest==grant_digest)
        .execution_options(populate_existing=True,autoflush=False))

async def original_session(session,row):
    return await session.scalar(select(AuthSession).where(AuthSession.id==row.admission_session_id,
        AuthSession.user_id==row.owner_user_id).execution_options(populate_existing=True,autoflush=False))

async def locked(session,hint_row):
    period=await admission.period(session,hint_row.period_id)
    row=await admission.owned(session,hint_row.owner_user_id,admission.database_uuid(hint_row.id),lock=True)
    if row is not None:row._completion_period=period
    return row,period

async def start(session,row,*,executor_id,stamp,start_json,start_sha256):
    return await session.scalar(update(Run).where(Run.id==row.id,Run.execution_started_at.is_(None),
        Run.execution_grant_digest==row.execution_grant_digest,Run.state=='claimed',Run.accepted_at.is_(None),
        Run.deadline_at>stamp).values(execution_started_at=stamp,execution_executor_id=executor_id,
            execution_start_json=start_json,execution_start_sha256=start_sha256).returning(Run)
        .execution_options(populate_existing=True,autoflush=False))

async def observe(session,row,*,body,sha256,stamp):
    return await session.scalar(update(Run).where(Run.id==row.id,Run.execution_started_at.is_not(None),
        Run.execution_evidence_json.is_(None)).values(execution_evidence_json=body,
            execution_evidence_sha256=sha256,execution_observed_at=stamp).returning(Run)
        .execution_options(populate_existing=True,autoflush=False))
