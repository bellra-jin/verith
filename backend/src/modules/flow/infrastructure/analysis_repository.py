"""Analysis SQL only: precise owner/key lookup, DB clock and fenced acceptance."""
from sqlalchemy import select,func,update,literal
from sqlalchemy.dialects.postgresql import insert
from db.models.flow.analysis_run import FlowAnalysisRun,KEY_CONSTRAINT


async def owned(session,analysis_id,owner):
    return await session.scalar(select(FlowAnalysisRun).where(FlowAnalysisRun.id==analysis_id,
        FlowAnalysisRun.owner_user_id==owner).with_for_update().execution_options(populate_existing=True))


async def by_key(session,owner,key):
    return await session.scalar(select(FlowAnalysisRun).where(FlowAnalysisRun.owner_user_id==owner,
        FlowAnalysisRun.operation=='flow.analysis.v1',FlowAnalysisRun.key_digest==key)
        .with_for_update().execution_options(populate_existing=True))


async def admit(session,values,*,before=None):
    statement=insert(FlowAnalysisRun)
    if before is None:
        statement=statement.values(**values)
    else:
        # The fixed admission cutoff is checked by the INSERT itself, not by a
        # prior SELECT that can become stale while another SQL lock is awaited.
        columns=[FlowAnalysisRun.__table__.c[name] for name in values]
        statement=statement.from_select([c.name for c in columns],select(
            *(literal(values[c.name],type_=c.type) for c in columns)).where(func.clock_timestamp()<before))
    return await session.scalar(statement.on_conflict_do_nothing(constraint=KEY_CONSTRAINT).returning(FlowAnalysisRun))


async def expire(session,row):
    value=await session.scalar(select(func.clock_timestamp()))
    if row.state=='running' and value>=row.deadline_at:
        row.state='unknown';row.error_code='SERVICE_UNAVAILABLE'
        await session.flush()


async def accept(session,row,claim,*,report_id,input_json,input_sha256,result_json,result_sha256):
    stamp=select(func.clock_timestamp().label('value')).cte('analysis_clock').prefix_with('MATERIALIZED')
    statement=update(FlowAnalysisRun).where(FlowAnalysisRun.id==row.id,FlowAnalysisRun.state=='running',
        FlowAnalysisRun.claim_digest==claim,stamp.c.value<FlowAnalysisRun.deadline_at).values(
        state='result_ready',adopted_report_id=report_id,input_json=input_json,input_sha256=input_sha256,
        result_json=result_json,result_sha256=result_sha256,accepted_at=stamp.c.value)
    return await session.scalar(statement.returning(FlowAnalysisRun).execution_options(populate_existing=True))
