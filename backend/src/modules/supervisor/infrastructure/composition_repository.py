"""Owned composition rows; raw SELECTs never overwrite caller ORM objects."""
from types import SimpleNamespace
from sqlalchemy import func,select,update
from sqlalchemy.dialects.postgresql import insert
from db.models.supervisor.composition import SupervisorComposition as Root,KEY_CONSTRAINT
from db.models.common.stock import Stock
from db.models.flow.analysis_run import FlowAnalysisRun
from db.models.technical.execution_admission import TechnicalAnalysisRun,TechnicalUsagePeriod


def _row(value):
    return SimpleNamespace(**value) if value is not None else None


async def clock(session):
    return await session.scalar(select(func.clock_timestamp()).execution_options(autoflush=False))


async def read(session,owner,*,id=None,key=None,lock=False):
    q=select(Root.__table__).where(Root.owner_user_id==owner)
    q=q.where(Root.id==id) if id is not None else q.where(Root.client_key_digest==key)
    if lock:q=q.with_for_update()
    return _row((await session.execute(q.execution_options(autoflush=False))).mappings().one_or_none())


async def admit(session,values):
    q=insert(Root).values(**values).on_conflict_do_nothing(constraint=KEY_CONSTRAINT).returning(Root.__table__)
    return _row((await session.execute(q)).mappings().one_or_none())


async def change(session,row,values):
    q=update(Root).where(Root.id==row.id,Root.owner_user_id==row.owner_user_id).values(**values).returning(Root.__table__)
    return _row((await session.execute(q.execution_options(synchronize_session=False))).mappings().one())


async def stock(session,ticker):
    q=select(Stock.__table__).where(Stock.stock_code==ticker).execution_options(autoflush=False)
    return _row((await session.execute(q)).mappings().one_or_none())


async def native(session,owner,view,key):
    if view not in ('flow','technical'):raise ValueError('Composition view invalid')
    cls=FlowAnalysisRun if view=='flow' else TechnicalAnalysisRun
    q=select(cls.__table__).where(cls.owner_user_id==owner,cls.key_digest==key,cls.operation==view+'.analysis.v1')
    return _row((await session.execute(q.execution_options(autoflush=False))).mappings().one_or_none())


async def technical_period(session,id):
    q=select(TechnicalUsagePeriod.__table__).where(TechnicalUsagePeriod.id==id)
    return _row((await session.execute(q.execution_options(autoflush=False))).mappings().one_or_none())


async def flow_policy(session,id):
    from db.models.common.analysis_usage import AnalysisUsageReservation as R,AnalysisUsagePeriod as P
    u=P.__table__.alias('composition_user_period');v=P.__table__.alias('composition_service_period')
    q=select(u.c.request_limit.label('user_limit'),v.c.request_limit.label('service_limit'),
        v.c.budget_limit_nano.label('budget'),v.c.user_request_limit.label('service_user_limit')).select_from(
        R.__table__.join(u,R.user_period_id==u.c.id).join(v,R.service_period_id==v.c.id)).where(R.id==id)
    return _row((await session.execute(q.execution_options(autoflush=False))).mappings().one_or_none())
