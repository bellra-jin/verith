"""Once-only meaning preparation and immutable adoption into the existing Flow binding."""
import asyncio
import hashlib
from datetime import timedelta
from uuid import UUID, uuid4

from src.modules.auth.application.session_service import AuthenticationRequired, validate_principal
from src.modules.stocks.application.resolver_service import StockResolverService
from src.modules.supervisor.domain.contracts import (
    CoreInvalid, Draft, MeaningRunOutput, Plan, PreparationView, Resolution, Stock,
    VERSION, MEANING_SPEC, MEANING_SPEC_SHA256, candidate_ref, canonical, decode,
    sha, validate_plan,
)
from src.modules.supervisor.domain.flow_projection import confirmed_plan, flow_body
from src.modules.supervisor.infrastructure import repository as bindings
from src.modules.supervisor.infrastructure import preparation_repository as repo
from src.modules.supervisor.infrastructure.preparation_repository import PreparationConflict

POLICY = 'supervisor.flow-core.2'
SELECTION_FIELDS = {'resolution', 'candidate_ref', 'selected_views', 'status', 'partial', 'required_waivers', 'plan_hash'}


def draft_identity(draft):
    return draft.model_dump(mode='json', exclude={'selected_ticker', 'candidate_ref'})


def digest_text(value):
    return hashlib.sha256(value.encode('utf8')).hexdigest()


def assembled(rows):
    root, selected = rows[0], rows[-1]
    if root.draft_json is None or root.plan_json is None or root.frame_json is None:
        raise CoreInvalid()
    if digest_text(root.frame_json) != root.frame_sha256 or digest_text(root.plan_json) != root.plan_sha256:
        raise CoreInvalid()
    draft = Draft.model_validate(decode(root.draft_json))
    raw = decode(root.plan_json)
    if raw.get('frame') != decode(root.frame_json):
        raise CoreInvalid()
    if selected.parent_id is not None:
        changes = decode(selected.continuation_json)
        if type(changes) is not dict or set(changes) != SELECTION_FIELDS | {'selected_ticker', 'selection_ref'}:
            raise CoreInvalid()
        draft = draft.model_copy(update={'selected_ticker': changes['selected_ticker'], 'candidate_ref': changes['selection_ref']})
        raw.update({name: changes[name] for name in SELECTION_FIELDS})
        if digest_text(canonical(raw)) != selected.plan_sha256:
            raise CoreInvalid()
    plan = validate_plan(raw, draft)
    if plan.policy_version != POLICY or sha(draft_identity(draft)) != root.draft_digest:
        raise CoreInvalid()
    return draft, plan


class PreparationService:
    def __init__(self, session, *, principal, client, resolver_factory=StockResolverService, epoch_id=None):
        self.session = session
        self.principal = principal
        self.client = client
        self.resolver_factory = resolver_factory
        self.epoch_id = epoch_id  # Private verifier injection only; no HTTP field chooses an epoch.

    async def auth(self):
        await validate_principal(self.session, self.principal, lock=True)

    async def exchange(self, payload, request_id, trace):
        value = await self.client.plan_supervisor_core(dict(schema_version=VERSION, request_id=str(request_id), trace_id=str(trace), data=payload, error=None))
        if type(value) is not dict or set(value) != {'schema_version', 'request_id', 'trace_id', 'data', 'error'} or value['schema_version'] != VERSION or value['request_id'] != str(request_id) or value['trace_id'] != str(trace) or value['error'] is not None:
            raise CoreInvalid()
        result = MeaningRunOutput.model_validate(value['data'])
        if result.semantic_spec_sha256 != MEANING_SPEC_SHA256:
            raise CoreInvalid()
        return result

    async def resolve(self, draft, frame, lookup):
        async with asyncio.timeout(3):
            await self.auth()
            resolver = self.resolver_factory(self.session)
            raw = await resolver.resolve(lookup)
            data = raw.model_dump(mode='json')
            data['candidates'] = [{k: v for k, v in c.items() if k != 'matched_text'} for c in data['candidates']]
            resolution = Resolution.model_validate(data)
            positive = {resolution.stock.stock_code} if resolution.stock is not None else {c.stock_code for c in resolution.candidates}
            # Alias spelling does not erase an explicit stock exclusion. All lookups share the same bounded transaction.
            for mention in frame.mentions:
                if not mention.negated:
                    continue
                excluded = await resolver.resolve(mention.text)
                negative = {excluded.stock.stock_code} if excluded.stock is not None else {c.stock_code for c in excluded.candidates}
                if positive & negative:
                    raise PreparationConflict('INPUT_INVALID', 422)
            await self.session.commit()
            return resolution

    async def build(self, draft, attempt, request_id, *, fixed=None):
        trace = uuid4()
        common = dict(policy_version=POLICY, draft=draft.model_dump(mode='json'), attempt_id=str(attempt))
        if fixed is None:
            result = await self.exchange(dict(**common, phase='start'), request_id, trace)
            frame = result.frame
            if frame.original_query != draft.original_query or frame.answers != draft.answers or frame.revision != draft.revision:
                raise CoreInvalid()
            if result.action != 'resolve_stock':
                if result.lookup is not None or result.plan is None:
                    raise CoreInvalid()
                plan = validate_plan(result.plan.model_dump(mode='json'), draft)
                if plan.status not in {'needs_clarification', 'unsupported'} or plan.resolution is not None or plan.selected_views:
                    raise CoreInvalid()
                return plan, result.meaning_status
            if result.plan is not None or frame.unresolved_slots or result.lookup not in {m.text for m in frame.mentions if not m.negated} or 'flow' not in frame.requested_views:
                raise CoreInvalid()
            lookup = result.lookup
        else:
            frame = fixed.frame
            active = [m.text for m in frame.mentions if not m.negated]
            if len(set(active)) != 1 or frame.unresolved_slots:
                raise CoreInvalid()
            lookup = active[0]
        resolution = await self.resolve(draft, frame, lookup)
        reference = candidate_ref(draft, resolution, policy_version=POLICY)
        if draft.selected_ticker is not None and (resolution.status != 'ambiguous' or draft.selected_ticker not in {c.stock_code for c in resolution.candidates}):
            raise PreparationConflict('PLAN_STALE', 409)
        result = await self.exchange(dict(**common, phase='continue', frame=frame.model_dump(mode='json'), resolution=resolution.model_dump(mode='json')), request_id, trace)
        if result.action != 'final' or result.lookup is not None or result.frame != frame or result.plan is None:
            raise CoreInvalid()
        plan = validate_plan(result.plan.model_dump(mode='json'), draft)
        expected = resolution
        if draft.selected_ticker is not None and reference == draft.candidate_ref:
            candidate = next(c for c in resolution.candidates if c.stock_code == draft.selected_ticker)
            expected = Resolution(status='resolved', reason='exact_match', stock=Stock(**candidate.model_dump(exclude={'match_type'})), candidates=[])
        if plan.policy_version != POLICY or plan.resolution != expected or plan.candidate_ref != reference or plan.frame != frame:
            raise CoreInvalid()
        if draft.selected_ticker is not None and reference != draft.candidate_ref and plan.status != 'selection_stale':
            raise CoreInvalid()
        return plan, result.meaning_status

    async def view(self, rows):
        stamp = await repo.clock(self.session)
        state, winner = repo.closure(rows, stamp)
        row = rows[-1]
        if state == 'expired':
            await repo.redact(self.session, rows, stamp, state='expired')
        plan = None
        if state is None:
            state = row.state
            if state in {'ready', 'clarification', 'unsupported'}:
                _, plan = assembled(rows)
        return PreparationView(preparation_id=str(row.id), state=state, plan=plan,
            created_at=row.created_at.isoformat(), expires_at=row.expires_at.isoformat(),
            meaning_status=state if state in {'consumed','deleted','expired'} else row.meaning_status,
            consumed_binding_id=str(winner) if winner is not None else None).model_dump(mode='json')

    async def get(self, id):
        try:
            await self.session.rollback()
            await self.auth()
            rows = await repo.lineage(self.session, self.principal.user_id, id)
            value = await self.view(rows)
            await self.session.commit()
            return value
        except BaseException:
            await self.session.rollback()
            raise

    async def delete(self, id):
        try:
            await self.session.rollback()
            await self.auth()
            rows = await repo.lineage(self.session, self.principal.user_id, id)
            await repo.redact(self.session, rows, await repo.clock(self.session))
            value = await self.view(rows)
            await self.session.commit()
            return value
        except BaseException:
            await self.session.rollback()
            raise

    async def post(self, body, request_id):
        id = None
        claimed = False
        try:
            async with asyncio.timeout(15):
                await self.session.rollback()
                await self.auth()
                key = hashlib.sha256(body.prepare_key.encode()).digest()
                digest = sha(body.model_dump(mode='json'))
                existing = await repo.by_key(self.session, self.principal.user_id, key)
                if existing is not None:
                    if existing.request_digest != digest:
                        raise PreparationConflict('IDEMPOTENCY_CONFLICT', 409)
                    rows = await repo.lineage(self.session, self.principal.user_id, existing.id)
                    value = await self.view(rows)
                    await self.session.commit()
                    return value
                await repo.cleanup_owner(self.session, self.principal.user_id)
                stamp = await repo.clock(self.session)
                id = uuid4()
                fixed = None
                parent = None
                root_id, depth, expires = id, 0, stamp + timedelta(minutes=10)
                if body.parent_preparation_id is not None:
                    rows = await repo.lineage(self.session, self.principal.user_id, UUID(body.parent_preparation_id))
                    closed, _ = repo.closure(rows, stamp)
                    if closed is not None:
                        raise PreparationConflict('PREPARATION_' + closed.upper(), 409)
                    parent = rows[-1]
                    original, fixed = assembled(rows)
                    root_options = Plan.model_validate(decode(rows[0].plan_json))
                    if parent.depth >= 4 or root_options.status != 'needs_stock_selection' or sha(draft_identity(body.draft)) != parent.draft_digest or draft_identity(body.draft) != draft_identity(original):
                        raise PreparationConflict('INPUT_INVALID', 422)
                    if body.draft.candidate_ref != fixed.candidate_ref or body.draft.selected_ticker not in {c.stock_code for c in root_options.resolution.candidates}:
                        raise PreparationConflict('PLAN_STALE', 409)
                    root_id, depth, expires = rows[0].id, parent.depth + 1, min(expires, parent.expires_at)
                attempt = uuid4()
                row = await repo.admit(self.session, dict(id=id, owner_user_id=self.principal.user_id,
                    prepare_key_digest=key, request_digest=digest, draft_digest=sha(draft_identity(body.draft)),
                    semantic_json=canonical(MEANING_SPEC), semantic_sha256=MEANING_SPEC_SHA256,
                    root_id=root_id, parent_id=parent.id if parent is not None else None, depth=depth,
                    attempt_id=attempt, epoch_id=self.epoch_id, state='pending', meaning_status='pending',
                    draft_json=canonical(body.draft.model_dump(mode='json')) if parent is None else None,
                    continuation_json=None, created_at=stamp, expires_at=expires))
                if row is None:
                    row = await repo.by_key(self.session, self.principal.user_id, key)
                    if row is None or row.request_digest != digest:
                        raise PreparationConflict('IDEMPOTENCY_CONFLICT', 409)
                    value = await self.view(await repo.lineage(self.session, self.principal.user_id, row.id))
                    await self.session.commit()
                    return value
                # Snapshot identifiers before commit expiration. Unknown ACK never starts AI.
                await self.session.commit()
                claimed = True
                plan, status = await self.build(body.draft, attempt, request_id, fixed=fixed)
                await self.auth()
                rows = await repo.lineage(self.session, self.principal.user_id, id)
                row = rows[-1]
                stamp = await repo.clock(self.session)
                if repo.closure(rows, stamp)[0] is not None:
                    value = await self.view(rows)
                    await self.session.commit()
                    return value
                if row.attempt_id != attempt or row.state != 'pending':
                    raise PreparationConflict()
                if repo.closure(rows, stamp)[0] is None:
                    row.state = 'ready' if plan.status in {'ready','scope_confirmation'} else 'unsupported' if plan.status == 'unsupported' else 'clarification'
                    row.meaning_status = status
                    raw = plan.model_dump(mode='json')
                    row.plan_sha256 = digest_text(canonical(raw))
                    if row.parent_id is None:
                        row.frame_json = canonical(plan.frame.model_dump(mode='json'))
                        row.frame_sha256 = digest_text(row.frame_json)
                        row.plan_json = canonical(raw)
                    else:
                        row.continuation_json = canonical({**{name: raw[name] for name in SELECTION_FIELDS},
                            'selected_ticker': body.draft.selected_ticker, 'selection_ref': body.draft.candidate_ref})
                    await self.session.flush()
                value = await self.view(rows)
                await self.session.commit()
                return value
        except BaseException as error:
            await self.session.rollback()
            if claimed and id is not None:
                # Separate failure transaction cannot resurrect a closed lineage or repeat extraction.
                try:
                    await self.auth()
                    rows = await repo.lineage(self.session, self.principal.user_id, id)
                    row = rows[-1]
                    if repo.closure(rows, await repo.clock(self.session))[0] is None and row.state == 'pending':
                        row.state = row.meaning_status = 'failed' if isinstance(error, (CoreInvalid, PreparationConflict)) else 'unknown'
                        await self.session.flush()
                    await self.session.commit()
                except BaseException:
                    await self.session.rollback()
            raise

    async def adopt(self, body, digest, key):
        """Called only after the existing owner/key replay path missed; no HTTP or Flow under locks."""
        await self.auth()
        rows = await repo.lineage(self.session, self.principal.user_id, UUID(body.preparation_id))
        # A winner for the same confirm key may have committed while these preparation locks waited.
        existing = await bindings.by_key(self.session, self.principal.user_id, key)
        if existing is not None:
            return bindings.snapshot(existing)
        stamp = await repo.clock(self.session)
        closed, _ = repo.closure(rows, stamp)
        if closed is not None:
            raise PreparationConflict('PREPARATION_' + closed.upper(), 409)
        draft, plan = assembled(rows)
        if draft.model_dump(mode='json') != body.draft.model_dump(mode='json') or plan.plan_hash != body.expected_plan_hash:
            raise PreparationConflict('PLAN_STALE', 409)
        # Current master and alias polarity are checked without a new meaning/model call.
        active = [m.text for m in plan.frame.mentions if not m.negated]
        if len(set(active)) != 1:
            raise CoreInvalid()
        resolver = self.resolver_factory(self.session)
        async with asyncio.timeout(3):
            current = await resolver.resolve(active[0])
            data = current.model_dump(mode='json')
            data['candidates'] = [{k: v for k, v in c.items() if k != 'matched_text'} for c in data['candidates']]
            resolution = Resolution.model_validate(data)
            reference = candidate_ref(draft, resolution, policy_version=POLICY)
            expected = resolution.stock
            if draft.selected_ticker is not None and resolution.status == 'ambiguous' and reference == draft.candidate_ref:
                candidate = next((c for c in resolution.candidates if c.stock_code == draft.selected_ticker), None)
                expected = Stock(**candidate.model_dump(exclude={'match_type'})) if candidate is not None else None
            if plan.resolution is None or expected is None or plan.resolution.stock != expected or plan.candidate_ref != reference:
                raise PreparationConflict('PLAN_STALE', 409)
            for mention in plan.frame.mentions:
                if mention.negated:
                    excluded = await resolver.resolve(mention.text)
                    codes = {excluded.stock.stock_code} if excluded.stock is not None else {c.stock_code for c in excluded.candidates}
                    if expected.stock_code in codes:
                        raise PreparationConflict('INPUT_INVALID', 422)
        stamp = await repo.clock(self.session)
        closed, _ = repo.closure(rows, stamp)
        if closed is not None:
            raise PreparationConflict('PREPARATION_' + closed.upper(), 409)
        saved = confirmed_plan(plan, body.consent)
        id = uuid4()
        raw_plan = canonical(saved)
        raw_flow = canonical(flow_body(plan, id, stamp))
        row = await bindings.admit(self.session, dict(id=id, owner_user_id=self.principal.user_id,
            client_key_digest=key, confirm_digest=digest, preparation_id=rows[-1].id,
            plan_json=raw_plan, plan_sha256=digest_text(raw_plan), flow_input_json=raw_flow,
            flow_sha256=digest_text(raw_flow), flow_key_digest=hashlib.sha256(str(id).encode()).digest(),
            confirmed_at=stamp, handoff_before=stamp + timedelta(seconds=120)))
        if row is None:
            row = await bindings.by_key(self.session, self.principal.user_id, key)
            if row is None:
                raise PreparationConflict()
            return bindings.snapshot(row)
        await repo.consume(self.session, rows, row.id, stamp)
        return bindings.snapshot(row)
