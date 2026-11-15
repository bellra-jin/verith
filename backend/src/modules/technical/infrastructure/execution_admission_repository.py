"""Technical-only SQL. Mutations lock auth first, then period, then run."""
from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID, uuid4
from types import SimpleNamespace
from sqlalchemy import func, select, literal
from sqlalchemy.dialects.postgresql import insert
from db.models.common.stock import Stock
from db.models.technical.execution_admission import TechnicalAnalysisRun as Run, TechnicalUsagePeriod as Period
from src.modules.technical.domain.execution_admission import OPERATION, TechnicalAdmissionError


def database_uuid(value):
    """Only values already obtained from trusted SQL/auth SELECT boundaries."""
    if not isinstance(value, UUID) or value.int == 0:
        raise TechnicalAdmissionError('STORED_INVALID')
    return UUID(str(value))


async def clock(session):
    value = await session.scalar(select(func.clock_timestamp()).execution_options(autoflush=False))
    if type(value) is not datetime or value.utcoffset() is None:
        raise TechnicalAdmissionError('UNAVAILABLE')
    return value.astimezone(UTC)


def kst_period(stamp):
    day = stamp.astimezone(timezone(timedelta(hours=9))).date()
    start = datetime.combine(day, datetime.min.time(), tzinfo=timezone(timedelta(hours=9))).astimezone(UTC)
    return day, start, start + timedelta(days=1)


async def by_key(session, owner, key, *, lock=False):
    statement = select(Run).where(Run.owner_user_id == owner, Run.operation == OPERATION, Run.key_digest == key)
    if lock:
        statement = statement.with_for_update()
    return await session.scalar(statement.execution_options(populate_existing=True, autoflush=False))


async def owned(session, owner, analysis_id, *, lock=False):
    statement = select(Run).where(Run.owner_user_id == owner, Run.id == analysis_id, Run.operation == OPERATION)
    if lock:
        statement = statement.with_for_update()
    return await session.scalar(statement.execution_options(populate_existing=True, autoflush=False))


async def period(session, period_id, *, lock=True):
    statement = select(Period).where(Period.id == period_id, Period.operation == OPERATION)
    if lock:
        statement = statement.with_for_update()
    return await session.scalar(statement.execution_options(populate_existing=True, autoflush=False))


async def admit_period(session, stamp, policy):
    values = policy.enabled()
    day, start, end = kst_period(stamp)
    # The UNIQUE operation/KST date chooses one first policy; an alternate ID
    # cannot fork/reset the day's budget. This insertion is part of admission.
    await session.execute(insert(Period).values(id=uuid4(),operation=OPERATION,kst_date=day,
        period_start=start,period_end=end,policy_json=policy.text,policy_sha256=policy.fingerprint,
        user_request_limit=values['user_daily_limit'],request_limit=values['service_daily_limit'],
        budget_limit_nano=values['daily_budget_nano'],attempt_reserve_nano=values['attempt_reserve_nano'],
        request_count=0,reserved_nano=0,blocked=False).on_conflict_do_nothing(constraint='uq_technical_usage_day'))
    return await session.scalar(select(Period).where(Period.operation == OPERATION, Period.kst_date == day)
        .with_for_update().execution_options(populate_existing=True,autoflush=False))


async def user_count(session, period_id, owner):
    return await session.scalar(select(func.count()).select_from(Run).where(Run.period_id == period_id, Run.owner_user_id == owner)
        .execution_options(autoflush=False))


async def stock(session, code):
    return await session.scalar(select(Stock).where(Stock.stock_code == code)
        .execution_options(populate_existing=True,autoflush=False))


async def insert_run(session, values, *, before=None):
    statement=insert(Run)
    if before is None:
        statement=statement.values(**values)
    else:
        columns=[Run.__table__.c[name] for name in values]
        statement=statement.from_select([c.name for c in columns],select(
            *(literal(values[c.name],type_=c.type) for c in columns)).where(func.clock_timestamp()<before))
    return await session.scalar(statement.on_conflict_do_nothing(constraint='uq_technical_analysis_key').returning(Run)
        .execution_options(populate_existing=True,autoflush=False))


async def read_by_key(session, owner, key):
    # Core mappings do not refresh/overwrite a caller's pending ORM run changes.
    value = (await session.execute(select(Run.__table__).where(Run.owner_user_id == owner,
        Run.operation == OPERATION, Run.key_digest == key).execution_options(autoflush=False))).mappings().one_or_none()
    return SimpleNamespace(**value) if value is not None else None


async def read_period(session, period_id):
    value = (await session.execute(select(Period.__table__).where(Period.id == period_id,
        Period.operation == OPERATION).execution_options(autoflush=False))).mappings().one_or_none()
    return SimpleNamespace(**value) if value is not None else None
