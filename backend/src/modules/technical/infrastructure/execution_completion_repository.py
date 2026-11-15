"""Same Technical run only: auth is caller-owned, then lock period before run."""
from sqlalchemy import update,func
from db.models.technical.execution_admission import TechnicalAnalysisRun as Run
from src.modules.technical.infrastructure import execution_admission_repository as admission
from src.modules.technical.application.execution_admission_service import TechnicalAdmissionService
from src.modules.technical.domain.execution_admission import COMPLETION_FORMAT,TechnicalAdmissionError


async def owned(session,analysis_id,owner):
    with session.no_autoflush:
        hint=await admission.owned(session,owner,analysis_id)
        if hint is None:return None
        period=await admission.period(session,hint.period_id)
        row=await admission.owned(session,owner,analysis_id,lock=True)
        if row is None or row.period_id!=period.id:raise TechnicalAdmissionError('STORED_INVALID')
        # Private SQL expectation, never supplied by a response or caller DTO.
        row._completion_period=period
        TechnicalAdmissionService._receipt(row,period)
        return row


async def expire(session,row):
    TechnicalAdmissionService._expire(row,await admission.clock(session))


async def accept(session,row,claim,frozen):
    result=await session.scalar(update(Run).where(Run.id==row.id,Run.owner_user_id==row.owner_user_id,
        Run.state=='claimed',Run.claim_digest==claim,Run.claim_consumed_at.is_not(None),
        Run.deadline_at>func.clock_timestamp()).values(state='result_ready',completion_format=COMPLETION_FORMAT,
        input_json=frozen.input_json,input_sha256=frozen.input_sha256,result_json=frozen.result_json,
        result_sha256=frozen.result_sha256,binding_sha256=frozen.binding_sha256,
        accepted_at=func.clock_timestamp(),error_code=None).returning(Run)
        .execution_options(populate_existing=True,autoflush=False))
    if result is not None:result._completion_period=row._completion_period
    return result


async def terminal(session,row,state,code=None):
    row.state=state;row.error_code=code
    row.intent_json=None;row.input_json=None;row.result_json=None
    row.redacted_at=await admission.clock(session)


async def read_owned(session,owner,analysis_id):
    # Core snapshots avoid refreshing/overwriting pending ORM changes in a
    # caller's dirty session. No flush, mutation, claim or commit occurs here.
    from sqlalchemy import select
    from types import SimpleNamespace
    with session.no_autoflush:
        value=(await session.execute(select(Run.__table__).where(Run.id==analysis_id,
            Run.owner_user_id==owner).execution_options(autoflush=False))).mappings().one_or_none()
        if value is None:return None
        row=SimpleNamespace(**value)
        row._completion_period=await admission.read_period(session,row.period_id)
        return row
