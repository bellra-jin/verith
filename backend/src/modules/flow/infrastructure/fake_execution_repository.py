"""Owner joins, specific grant UNIQUE, fence and DB deadline CAS only."""
from sqlalchemy import func, literal, select, text, update
from sqlalchemy.dialects.postgresql import insert, UUID
from db.models.flow.flow_run import FlowRun
from db.models.flow.input_snapshot import FlowInputSnapshot
from db.models.flow.fake_execution import FlowFakeExecution, INPUT_CONSTRAINT


async def get_owned(session, run_id, owner):
    return await session.scalar(select(FlowFakeExecution).join(FlowInputSnapshot,
        FlowInputSnapshot.id == FlowFakeExecution.input_snapshot_id).join(FlowRun,
        (FlowRun.id == FlowInputSnapshot.run_id) & (FlowRun.owner_user_id == FlowInputSnapshot.owner_user_id))
        .where(FlowRun.id == run_id, FlowRun.owner_user_id == owner, FlowInputSnapshot.owner_user_id == owner)
        .with_for_update(of=FlowFakeExecution).execution_options(populate_existing=True))


async def claim(session, execution_id, input_id, claim_digest):
    stamp = select(func.clock_timestamp().label("started")).cte("claim_clock").prefix_with("MATERIALIZED")
    fields = ["id", "input_snapshot_id", "contract_version", "engine_id", "claim_digest", "status", "started_at", "deadline_at"]
    values = select(literal(execution_id, type_=UUID(as_uuid=True)), literal(input_id, type_=UUID(as_uuid=True)),
        literal(1), literal("flow.fake.summary.v1"), literal(claim_digest), literal("running"),
        stamp.c.started, stamp.c.started + text("interval '10 seconds'"))
    return await session.scalar(insert(FlowFakeExecution).from_select(fields, values)
        .on_conflict_do_nothing(constraint=INPUT_CONSTRAINT).returning(FlowFakeExecution))


async def finalize(session, row, *, claim_digest=None, status=None, result_json=None, result_sha256=None, error_code=None, expired=False):
    stamp = select(func.clock_timestamp().label("finished")).cte("terminal_clock").prefix_with("MATERIALIZED")
    statement = update(FlowFakeExecution).where(FlowFakeExecution.id == row.id,
        FlowFakeExecution.input_snapshot_id == row.input_snapshot_id, FlowFakeExecution.status == "running")
    if expired:
        statement = statement.where(stamp.c.finished >= FlowFakeExecution.deadline_at)
        status, result_json, result_sha256, error_code = "timed_out", None, None, "deadline_expired"
    else:
        statement = statement.where(FlowFakeExecution.claim_digest == claim_digest, stamp.c.finished < FlowFakeExecution.deadline_at)
    return await session.scalar(statement.values(status=status, result_json=result_json, result_sha256=result_sha256,
        error_code=error_code, finished_at=stamp.c.finished).returning(FlowFakeExecution)
        .execution_options(populate_existing=True))
