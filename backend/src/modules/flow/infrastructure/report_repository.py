"""flow report 영속화(repository)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.common.agent_report import AgentReport
from db.models.common.stock import Stock
from db.models.flow.flow_report import FlowReport
from db.models.flow.report_interpretation import FlowReportInterpretation
from db.models.flow.report_verification import FlowReportVerification


async def ensure_stock(
    session: AsyncSession,
    *,
    stock_code: str,
    stock_name: str | None,
    market: str | None,
) -> None:
    """flow_reports.stock_code 는 stocks FK(NOT NULL) — 없으면 먼저 채운다(멱등)."""
    values: dict[str, object] = {
        "stock_code": stock_code,
        "stock_name": stock_name or stock_code,
    }
    if market:
        values["market"] = market
    stmt = (
        pg_insert(Stock)
        .values(**values)
        .on_conflict_do_nothing(index_elements=[Stock.stock_code])
    )
    await session.execute(stmt)


async def add_report(
    session: AsyncSession,
    *,
    report: FlowReport,
    interpretation: FlowReportInterpretation,
    verification: FlowReportVerification,
) -> None:
    session.add(report)
    await session.flush()
    session.add(interpretation)
    session.add(verification)
    await session.flush()


async def get_report(session: AsyncSession, report_id: UUID) -> FlowReport | None:
    return await session.get(FlowReport, report_id)


async def get_interpretation(
    session: AsyncSession, report_id: UUID
) -> FlowReportInterpretation | None:
    return await session.scalar(
        select(FlowReportInterpretation).where(
            FlowReportInterpretation.report_id == report_id
        )
    )


async def get_verification(
    session: AsyncSession, report_id: UUID
) -> FlowReportVerification | None:
    return await session.scalar(
        select(FlowReportVerification).where(
            FlowReportVerification.report_id == report_id
        )
    )


async def get_agent_indexes(
    session: AsyncSession, report_id: UUID
) -> list[AgentReport]:
    rows = await session.scalars(
        select(AgentReport).where(
            AgentReport.agent_type == "flow",
            AgentReport.agent_report_id == report_id,
        )
    )
    return list(rows.all())


async def get_report_parts(
    session: AsyncSession, report_ids: list[UUID], *, owner_user_id: UUID
) -> tuple[
    list[FlowReport],
    list[FlowReportInterpretation],
    list[FlowReportVerification],
    list[AgentReport],
]:
    """Batch projections for a list page; keep reads bounded as page size increases."""
    eligible = eligible_flow_ids(owner_user_id).where(FlowReport.id.in_(report_ids))
    roots = await session.scalars(select(FlowReport).where(FlowReport.id.in_(eligible)))
    interpretations = await session.scalars(
        select(FlowReportInterpretation).where(
            FlowReportInterpretation.report_id.in_(eligible)
        )
    )
    verifications = await session.scalars(
        select(FlowReportVerification).where(
            FlowReportVerification.report_id.in_(eligible)
        )
    )
    indexes = await session.scalars(
        select(AgentReport).where(
            AgentReport.agent_type == "flow",
            AgentReport.agent_report_id.in_(eligible),
        )
    )
    return (
        list(roots.all()),
        list(interpretations.all()),
        list(verifications.all()),
        list(indexes.all()),
    )


async def delete_agent_index(session: AsyncSession, report_id: UUID) -> int:
    result = await session.execute(
        delete(AgentReport).where(
            AgentReport.agent_type == "flow",
            AgentReport.agent_report_id == report_id,
        )
    )
    return result.rowcount or 0


async def delete_root(session: AsyncSession, report_id: UUID) -> int:
    # interpretation·verification 은 FK CASCADE 로 함께 지워진다.
    result = await session.execute(delete(FlowReport).where(FlowReport.id == report_id))
    return result.rowcount or 0


def eligible_flow_ids(owner_user_id: UUID):
    """One SQL predicate shared by detail/list/count/batches, before pagination."""
    counts = (
        select(AgentReport.agent_report_id.label("root_id"), func.count().label("n"))
        .where(AgentReport.agent_type == "flow")
        .group_by(AgentReport.agent_report_id)
        .subquery()
    )
    return (
        select(FlowReport.id)
        .join(counts, counts.c.root_id == FlowReport.id)
        .join(
            AgentReport,
            (AgentReport.agent_report_id == FlowReport.id)
            & (AgentReport.agent_type == "flow"),
        )
        .where(
            FlowReport.owner_user_id == owner_user_id,
            counts.c.n == 1,
            AgentReport.owner_user_id == FlowReport.owner_user_id,
        )
    )


async def get_owned_report(
    session: AsyncSession, report_id: UUID, *, owner_user_id: UUID, lock: bool = False
):
    # Root lock must precede projection inspection for writers.
    statement = select(FlowReport).where(
        FlowReport.id == report_id, FlowReport.owner_user_id == owner_user_id
    )
    if lock:
        statement = statement.with_for_update()
    root = await session.scalar(statement.execution_options(populate_existing=True))
    if root is None:
        return None
    eligible = await session.scalar(
        select(FlowReport.id).where(
            FlowReport.id == report_id,
            FlowReport.id.in_(eligible_flow_ids(owner_user_id)),
        )
    )
    return root if eligible is not None else None


async def list_owned_indexes(
    session: AsyncSession,
    *,
    owner_user_id: UUID,
    stock_code=None,
    client_session_id=None,
    limit=20,
    offset=0,
    count=False,
):
    statement = select(func.count() if count else AgentReport).where(
        AgentReport.agent_type == "flow",
        AgentReport.agent_report_id.in_(eligible_flow_ids(owner_user_id)),
    )
    if stock_code is not None:
        statement = statement.where(AgentReport.stock_code == stock_code)
    if client_session_id is not None:
        statement = statement.where(AgentReport.client_session_id == client_session_id)
    if count:
        return int(await session.scalar(statement) or 0)
    rows = await session.scalars(
        statement.order_by(AgentReport.created_at.desc(), AgentReport.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(rows.all())
