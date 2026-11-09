"""Owner-bound immutable snapshot SQL. No locks held across Flow execution."""
from sqlalchemy import select, update, func
from sqlalchemy.dialects.postgresql import insert
from db.models.supervisor.request_binding import SupervisorRequestBinding as Binding, KEY_CONSTRAINT
from db.models.flow.analysis_run import FlowAnalysisRun

async def by_key(session, owner, key):
    return await session.scalar(select(Binding).where(Binding.owner_user_id == owner, Binding.client_key_digest == key).execution_options(populate_existing=True))

async def owned(session, owner, id):
    return await session.scalar(select(Binding).where(Binding.id == id, Binding.owner_user_id == owner).execution_options(populate_existing=True))

async def admit(session, values):
    return await session.scalar(insert(Binding).values(**values).on_conflict_do_nothing(constraint=KEY_CONSTRAINT).returning(Binding))

async def flow_run(session, binding):
    return await session.scalar(select(FlowAnalysisRun).where(FlowAnalysisRun.owner_user_id == binding.owner_user_id, FlowAnalysisRun.operation == 'flow.analysis.v1', FlowAnalysisRun.key_digest == binding.flow_key_digest))

async def redact_for_flow(session, owner, key):
    await session.execute(update(Binding).where(Binding.owner_user_id == owner, Binding.flow_key_digest == key, Binding.redacted_at.is_(None)).values(plan_json=None, flow_input_json=None, redacted_at=func.clock_timestamp()))
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class Snapshot:
    id: object
    owner_user_id: object
    confirm_digest: str
    plan_json: str | None
    plan_sha256: str
    flow_input_json: str | None
    flow_sha256: str
    flow_key_digest: bytes
    handoff_before: object
    redacted_at: object

def snapshot(row):
    return Snapshot(**{k: getattr(row, k) for k in Snapshot.__dataclass_fields__})
