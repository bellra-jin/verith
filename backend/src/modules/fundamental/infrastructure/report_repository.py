"""fundamental report 영속화(repository)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.common.agent_report import AgentReport
from db.models.common.stock import Stock
from db.models.fundamental.fundamental_report import FundamentalReport
from db.models.fundamental.report_evidence import ReportEvidence
from db.models.fundamental.report_filing_snippet import ReportFilingSnippet
from db.models.fundamental.report_insight import ReportInsight
from db.models.fundamental.report_interpretation import FundamentalReportInterpretation
from db.models.fundamental.report_ratio import ReportRatio
from db.models.fundamental.report_verification import FundamentalReportVerification


async def ensure_stock(session: AsyncSession, *, stock_code: str, stock_name: str) -> None:
    stmt = pg_insert(Stock).values(stock_code=stock_code, stock_name=stock_name)
    stmt = stmt.on_conflict_do_nothing(index_elements=[Stock.stock_code])
    await session.execute(stmt)


async def add_report(
    session: AsyncSession,
    *,
    report: FundamentalReport,
    ratios: list[ReportRatio],
    evidence: list[ReportEvidence],
    interpretation: FundamentalReportInterpretation,
    verification: FundamentalReportVerification,
    insights: list[ReportInsight],
    filing_snippets: list[ReportFilingSnippet],
) -> None:
    session.add(report)
    await session.flush()
    session.add_all(ratios)
    await session.flush()
    session.add_all(evidence)
    session.add(interpretation)
    session.add(verification)
    session.add_all(insights)
    session.add_all(filing_snippets)
    await session.flush()


async def get_report(session: AsyncSession, report_id: UUID) -> FundamentalReport | None:
    return await session.get(FundamentalReport, report_id)


async def list_reports_by_stock(
    session: AsyncSession,
    *,
    stock_code: str,
    limit: int,
    offset: int,
) -> list[FundamentalReport]:
    stmt = (
        select(FundamentalReport)
        .where(FundamentalReport.stock_code == stock_code)
        .order_by(FundamentalReport.as_of.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = await session.execute(stmt)
    return list(rows.scalars().all())


async def list_ratios(session: AsyncSession, report_id: UUID) -> list[ReportRatio]:
    rows = await session.execute(select(ReportRatio).where(ReportRatio.report_id == report_id))
    return list(rows.scalars().all())


async def list_evidence(session: AsyncSession, report_id: UUID) -> list[ReportEvidence]:
    rows = await session.execute(select(ReportEvidence).where(ReportEvidence.report_id == report_id))
    return list(rows.scalars().all())


async def get_interpretation(
    session: AsyncSession,
    report_id: UUID,
) -> FundamentalReportInterpretation | None:
    return await session.scalar(
        select(FundamentalReportInterpretation).where(
            FundamentalReportInterpretation.report_id == report_id
        )
    )


async def get_verification(
    session: AsyncSession,
    report_id: UUID,
) -> FundamentalReportVerification | None:
    return await session.scalar(
        select(FundamentalReportVerification).where(
            FundamentalReportVerification.report_id == report_id
        )
    )


async def list_insights(session: AsyncSession, report_id: UUID) -> list[ReportInsight]:
    rows = await session.execute(select(ReportInsight).where(ReportInsight.report_id == report_id))
    return list(rows.scalars().all())


async def list_filing_snippets(
    session: AsyncSession,
    report_id: UUID,
) -> list[ReportFilingSnippet]:
    rows = await session.execute(
        select(ReportFilingSnippet).where(ReportFilingSnippet.report_id == report_id)
    )
    return list(rows.scalars().all())


async def delete_agent_index(session: AsyncSession, report_id: UUID) -> int:
    result = await session.execute(
        delete(AgentReport).where(
            AgentReport.agent_type == "fundamental",
            AgentReport.agent_report_id == report_id,
        )
    )
    return result.rowcount or 0


async def delete_root(session: AsyncSession, report_id: UUID) -> int:
    result = await session.execute(
        delete(FundamentalReport).where(FundamentalReport.id == report_id)
    )
    return result.rowcount or 0


# Every eligible root has exactly one total Fundamental index, same owner, and
# one immutable stored-ledger association. Filter before count/pagination.
def eligible_ids(owner_user_id):
    from db.models.fundamental.analysis_run import FundamentalAnalysisRun
    indexes=select(AgentReport.agent_report_id).where(AgentReport.agent_type=='fundamental').group_by(AgentReport.agent_report_id).having(func.count()==1,func.count().filter(AgentReport.owner_user_id==owner_user_id)==1)
    return select(FundamentalReport.id).join(FundamentalAnalysisRun,(FundamentalAnalysisRun.adopted_report_id==FundamentalReport.id)&(FundamentalAnalysisRun.owner_user_id==owner_user_id)&(FundamentalAnalysisRun.state=='stored')).where(FundamentalReport.owner_user_id==owner_user_id,FundamentalReport.id.in_(indexes))

async def get_owned_report(session,report_id,*,owner_user_id,lock=False):
    statement=select(FundamentalReport).where(FundamentalReport.id==report_id,FundamentalReport.id.in_(eligible_ids(owner_user_id)))
    if lock:statement=statement.with_for_update(of=FundamentalReport)
    return await session.scalar(statement.execution_options(populate_existing=True))

async def get_agent_indexes(session,report_id):
    return list((await session.scalars(select(AgentReport).where(AgentReport.agent_type=='fundamental',AgentReport.agent_report_id==report_id))).all())

async def list_owned_indexes(session,*,owner_user_id,stock_code=None,limit=20,offset=0,count=False):
    statement=select(AgentReport).where(AgentReport.agent_type=='fundamental',AgentReport.owner_user_id==owner_user_id,AgentReport.agent_report_id.in_(eligible_ids(owner_user_id)))
    if stock_code:statement=statement.where(AgentReport.stock_code==stock_code)
    if count:return await session.scalar(select(func.count()).select_from(statement.subquery()))
    return list((await session.scalars(statement.order_by(AgentReport.created_at.desc(),AgentReport.id.desc()).limit(limit).offset(offset))).all())
