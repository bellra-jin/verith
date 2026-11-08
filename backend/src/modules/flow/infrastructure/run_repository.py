"""Owner-scoped receipt SQL. The unique conflict target is intentionally specific."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.flow.flow_run import FlowRun, KEY_CONSTRAINT


async def insert_receipt(session: AsyncSession, values: dict) -> FlowRun | None:
    statement = (insert(FlowRun).values(**values)
                 .on_conflict_do_nothing(constraint=KEY_CONSTRAINT).returning(FlowRun))
    return await session.scalar(statement)


async def find_key(session: AsyncSession, owner: UUID, digest: bytes) -> FlowRun | None:
    # Separate READ COMMITTED statement sees the committed unique-key winner.
    return await session.scalar(select(FlowRun).where(
        FlowRun.owner_user_id == owner, FlowRun.operation == "flow",
        FlowRun.idempotency_key_digest == digest,
    ))


async def get_owned(session: AsyncSession, run_id: UUID, owner: UUID) -> FlowRun | None:
    return await session.scalar(select(FlowRun).where(
        FlowRun.id == run_id, FlowRun.owner_user_id == owner,
    ))
