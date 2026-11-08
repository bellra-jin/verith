"""Exact owner SQL and run-specific conflict target. No update or delete API."""
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from db.models.flow.flow_run import FlowRun
from db.models.flow.input_snapshot import FlowInputSnapshot, RUN_CONSTRAINT


async def lock_run(session, run_id, owner):
    return await session.scalar(select(FlowRun).where(
        FlowRun.id == run_id, FlowRun.owner_user_id == owner,
    ).with_for_update(of=FlowRun).execution_options(populate_existing=True))


async def get_owned(session, run_id, owner):
    return await session.scalar(select(FlowInputSnapshot).join(FlowRun,
        (FlowRun.id == FlowInputSnapshot.run_id) & (FlowRun.owner_user_id == FlowInputSnapshot.owner_user_id)
    ).where(FlowRun.id == run_id, FlowRun.owner_user_id == owner,
            FlowInputSnapshot.owner_user_id == owner).execution_options(populate_existing=True))


async def insert_snapshot(session, values):
    return await session.scalar(insert(FlowInputSnapshot).values(**values)
        .on_conflict_do_nothing(constraint=RUN_CONSTRAINT).returning(FlowInputSnapshot))
