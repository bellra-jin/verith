"""Fixed lock order: service period, user period, reservation, ordered calls."""
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from db.models.common.analysis_usage import AnalysisUsagePeriod as Period,AnalysisUsageReservation as Reservation,AnalysisProviderCall as Call


async def period(session,scope,owner,start,end,*,request_limit,budget_limit,user_request_limit=None):
    await session.execute(insert(Period).values(id=uuid4(),scope=scope,owner_user_id=owner,operation='flow.analysis.v1',currency='USD',
        period_start=start,period_end=end,request_limit=request_limit,budget_limit_nano=budget_limit,user_request_limit=user_request_limit,
        request_count=0,held_nano=0,estimated_spend_nano=0,blocked=False).on_conflict_do_nothing())
    return await session.scalar(select(Period).where(Period.scope==scope,Period.owner_user_id==owner,
        Period.operation=='flow.analysis.v1',Period.currency=='USD',Period.period_start==start,Period.period_end==end)
        .with_for_update().execution_options(populate_existing=True))


async def accounting(session,reservation_id):
    # Identity is immutable. The initial unlocked lookup only identifies lock keys.
    ref=await session.scalar(select(Reservation).where(Reservation.id==reservation_id))
    if ref is None:return None
    service=await session.scalar(select(Period).where(Period.id==ref.service_period_id).with_for_update().execution_options(populate_existing=True))
    user=await session.scalar(select(Period).where(Period.id==ref.user_period_id).with_for_update().execution_options(populate_existing=True))
    reservation=await session.scalar(select(Reservation).where(Reservation.id==reservation_id).with_for_update().execution_options(populate_existing=True))
    calls=list((await session.scalars(select(Call).where(Call.reservation_id==reservation_id).order_by(Call.provider,Call.action,Call.ordinal)
        .with_for_update().execution_options(populate_existing=True))).all())
    return service,user,reservation,calls
