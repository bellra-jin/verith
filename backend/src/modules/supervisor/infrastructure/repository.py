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
    ids = list((await session.scalars(update(Binding).where(Binding.owner_user_id == owner, Binding.target == "flow", Binding.flow_key_digest == key, Binding.redacted_at.is_(None)).values(plan_json=None, flow_input_json=None, redacted_at=func.clock_timestamp()).returning(Binding.preparation_id))).all())
    from src.modules.supervisor.infrastructure import preparation_repository as preparations
    for id in sorted((value for value in ids if value is not None), key=str):
        rows = await preparations.lineage(session, owner, id)
        await preparations.redact(session, rows, await preparations.clock(session), allow_consumed=True)
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
    preparation_id: object = None
    target: str = "flow"

def snapshot(row):
    return Snapshot(**{k: getattr(row, k, "flow" if k=="target" else None) for k in Snapshot.__dataclass_fields__})

async def technical_link_row(session,owner,id):
    return await session.scalar(select(Binding).where(Binding.owner_user_id==owner,Binding.id==id,Binding.target=='technical').with_for_update().execution_options(populate_existing=True,autoflush=False))

async def technical_read(session,owner,id=None,key=None):
    from types import SimpleNamespace
    query=select(Binding.__table__).where(Binding.owner_user_id==owner)
    query=query.where(Binding.id==id) if id is not None else query.where(Binding.client_key_digest==key)
    value=(await session.execute(query.execution_options(autoflush=False))).mappings().one_or_none()
    return SimpleNamespace(**value) if value is not None else None
