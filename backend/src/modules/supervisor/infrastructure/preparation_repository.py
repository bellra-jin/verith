"""Owner-bound preparations; every mutation acquires the same root-to-leaf lock order."""
import copy
from uuid import UUID, uuid4
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert
from db.models.supervisor.preparation import SupervisorMeaningPreparation as Preparation, SupervisorMeaningEpoch as Epoch
from src.modules.supervisor.domain.contracts import canonical, decode, sha, MEANING_SPEC, MEANING_SPEC_SHA256


class PreparationConflict(RuntimeError):
    def __init__(self, code='RESULT_CONTRACT_INVALID', status=502):
        self.code, self.status = code, status
        super().__init__('Meaning preparation unavailable')


async def clock(session):
    return await session.scalar(select(func.clock_timestamp()))


async def by_key(session, owner, key):
    return await session.scalar(select(Preparation).where(Preparation.owner_user_id == owner, Preparation.prepare_key_digest == key).execution_options(populate_existing=True))


async def owned(session, owner, id):
    return await session.scalar(select(Preparation).where(Preparation.id == id, Preparation.owner_user_id == owner).execution_options(populate_existing=True))


async def admit(session, values):
    return await session.scalar(insert(Preparation).values(**values).on_conflict_do_nothing(constraint='uq_meaning_owner_prepare_key').returning(Preparation))


async def lineage(session, owner, id, *, lock=True):
    path, seen = [], set()
    current = id
    while current is not None:
        if current in seen or len(path) == 5:
            raise PreparationConflict()
        seen.add(current)
        row = await owned(session, owner, current)
        if row is None:
            raise PreparationConflict('RESOURCE_NOT_FOUND', 404)
        path.append((row.id, row.parent_id, row.root_id, row.depth))
        current = row.parent_id
    path.reverse()
    ids = [item[0] for item in path]
    statement = select(Preparation).where(Preparation.owner_user_id == owner, Preparation.id.in_(ids)).order_by(Preparation.depth, Preparation.id).execution_options(populate_existing=True)
    if lock:
        statement = statement.with_for_update()
    rows = list((await session.scalars(statement)).all())
    if [(p.id, p.parent_id, p.root_id, p.depth) for p in rows] != path:
        raise PreparationConflict()
    for depth, row in enumerate(rows):
        if row.depth != depth or row.root_id != rows[0].id or row.parent_id != (rows[depth - 1].id if depth else None):
            raise PreparationConflict()
    return rows


def closure(rows, stamp):
    for row in rows:
        if row.state == 'consumed':
            return 'consumed', row.consumed_binding_id
    if any(row.state == 'deleted' for row in rows):
        return 'deleted', None
    if any(row.state == 'expired' or row.expires_at <= stamp for row in rows):
        return 'expired', None
    if any(row.redacted_at is not None for row in rows):
        return 'deleted', None
    return None, None


async def redact(session, rows, stamp, *, state='deleted', allow_consumed=False):
    if any(p.state == 'consumed' for p in rows) and not allow_consumed:
        raise PreparationConflict('PREPARATION_CONSUMED', 409)
    for row in rows:
        if row.state == 'consumed':
            if any(getattr(row, name) is not None for name in ('draft_json','frame_json','plan_json','continuation_json')):
                raise PreparationConflict()
            continue
        row.draft_json = row.frame_json = row.plan_json = row.continuation_json = None
        row.redacted_at = row.redacted_at or stamp
        if row.state != 'deleted':
            row.state = state
            row.meaning_status = state
    await session.flush()


async def cleanup_owner(session, owner, *, maximum=16):
    stamp = await clock(session)
    roots = list((await session.scalars(select(Preparation.id).where(Preparation.owner_user_id == owner, Preparation.parent_id.is_(None), Preparation.redacted_at.is_(None), Preparation.expires_at <= stamp).order_by(Preparation.id).limit(maximum))).all())
    for id in roots:
        rows = await lineage(session, owner, id)
        if not any(row.state == 'consumed' for row in rows):
            await redact(session, rows, stamp, state='expired')


async def consume(session, rows, binding_id, stamp):
    stamp = await clock(session)
    if closure(rows, stamp)[0] is not None or any(p.state not in {'ready','clarification'} for p in rows):
        raise PreparationConflict('PREPARATION_CONSUMED', 409)
    for row in rows:
        row.state, row.meaning_status = 'consumed', 'consumed'
        row.consumed_binding_id = binding_id
        row.draft_json = row.frame_json = row.plan_json = row.continuation_json = None
        row.redacted_at = stamp
    await session.flush()


async def verifier_epoch(session):
    """Private verifier initialization. Reuses durable identity; never resets a prior epoch."""
    from hashlib import sha256
    price_sha = sha(MEANING_SPEC['price'])
    stamp = await clock(session)
    statement = insert(Epoch).values(id=uuid4(), unit_id='CF023', currency='USD', max_nano=100000000, attempt_reserve_nano=50000000,
        max_attempts=2, price_sha256=price_sha, semantic_sha256=MEANING_SPEC_SHA256, reserved_nano=0, count_requests=0,
        generation_requests=0, blocked=False, active_attempt_id=None, attempts_json={}, created_at=stamp).on_conflict_do_nothing(index_elements=['unit_id'])
    await session.execute(statement)
    row = await session.scalar(select(Epoch).where(Epoch.unit_id == 'CF023').with_for_update().execution_options(populate_existing=True))
    if row is None or row.price_sha256 != price_sha or row.semantic_sha256 != MEANING_SPEC_SHA256:
        raise PreparationConflict('MEANING_LIMIT_EXCEEDED', 429)
    return row


class DurableMeaningBudget:
    """Same proof/session factory, no AI DB credential or public budget endpoint."""
    def __init__(self, session_factory, *, epoch_id, owner):
        self._sessions, self._epoch_id, self._owner = session_factory, epoch_id, owner

    async def authorize(self, attempt_id, phase, request_hash, projection_hash, evidence):
        from uuid import UUID
        if phase not in {'count','generation'}:
            return False
        async with self._sessions() as session:
            epoch = await session.scalar(select(Epoch).where(Epoch.id == self._epoch_id).with_for_update().execution_options(populate_existing=True))
            if epoch is None or epoch.unit_id != 'CF023' or epoch.semantic_sha256 != MEANING_SPEC_SHA256 or epoch.price_sha256 != sha(MEANING_SPEC['price']) or epoch.blocked:
                return False
            preparation = await session.scalar(select(Preparation).where(Preparation.attempt_id == UUID(attempt_id), Preparation.owner_user_id == self._owner, Preparation.epoch_id == epoch.id))
            stamp = await clock(session)
            if preparation is None or preparation.state != 'pending' or preparation.redacted_at is not None or preparation.expires_at <= stamp:
                return False
            ledger = copy.deepcopy(epoch.attempts_json)
            existing = ledger.get(attempt_id)
            if phase == 'count':
                if existing is not None or len(ledger) >= 2 or epoch.active_attempt_id is not None or epoch.reserved_nano + 50000000 > 100000000:
                    return False
                ledger[attempt_id] = {'request_sha256': request_hash, 'projection_sha256': projection_hash, 'count_done': True, 'generation_done': False, 'observation': None}
                epoch.reserved_nano += 50000000
                epoch.count_requests += 1
                epoch.active_attempt_id = UUID(attempt_id)
            else:
                if existing is None or existing['generation_done'] or epoch.active_attempt_id != UUID(attempt_id) or evidence is None:
                    return False
                if existing['request_sha256'] != request_hash or existing['projection_sha256'] != projection_hash or evidence.request_sha256 != request_hash or evidence.projection_sha256 != projection_hash or evidence.model != MEANING_SPEC['model'] or evidence.price_sha256 != epoch.price_sha256 or type(evidence.input_tokens) is not int or not 0 <= evidence.input_tokens <= 16384 or type(evidence.count_fee_bound_nano) is not int or not 0 <= evidence.count_fee_bound_nano <= 28496000:
                    return False
                ledger[attempt_id]['generation_done'] = True
                epoch.generation_requests += 1
            epoch.attempts_json = ledger
            await session.flush()
            await session.commit()  # Only confirmed ACK authorizes the immediately following send.
            return True

    async def finish(self, attempt_id, observation, *, blocked):
        allowed = {'state','reason','estimated_nano','model_sha256','input_tokens','output_tokens','total_tokens','cached_tokens','price_sha256'}
        if type(observation) is not dict or set(observation) - allowed or observation.get('state') not in {'unknown','observed','anomalous'}:
            raise PreparationConflict()
        blocked = bool(blocked) or observation['state'] != 'observed'
        async with self._sessions() as session:
            epoch = await session.scalar(select(Epoch).where(Epoch.id == self._epoch_id).with_for_update().execution_options(populate_existing=True))
            if epoch is None:
                raise PreparationConflict()
            ledger = copy.deepcopy(epoch.attempts_json)
            row = ledger.get(attempt_id)
            if row is None:
                return
            previous = row.get('observation')
            if previous is not None and previous.get('state') in {'observed','anomalous'} and previous != observation:
                raise PreparationConflict()
            row['observation'] = dict(observation)
            epoch.attempts_json = ledger
            epoch.blocked |= bool(blocked)
            if not epoch.blocked and epoch.active_attempt_id == UUID(attempt_id):
                epoch.active_attempt_id = None
            await session.flush()
            await session.commit()
