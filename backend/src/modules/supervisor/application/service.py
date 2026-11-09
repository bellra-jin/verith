"""Authenticated meaning/tool planning and immutable binding -> existing owned Flow."""
import asyncio
import hashlib
from datetime import timedelta
from uuid import uuid4
from sqlalchemy import select, func
from src.modules.supervisor.domain.contracts import (
    CoreInvalid, InternalOutput, Resolution, Stock, VERSION, candidate_ref,
    canonical, decode, sha, validate_plan,
)
from src.modules.supervisor.domain.flow_projection import confirmed_plan, flow_body, outcome
from src.modules.supervisor.infrastructure import repository as repo
from src.modules.stocks.application.resolver_service import StockResolverService
from src.modules.auth.application.session_service import AuthenticationRequired, validate_principal
from src.modules.flow.application.analysis_service import AnalysisService, AnalysisError
from src.modules.flow.api.analysis_schemas import AnalysisRequest
from src.shared.infrastructure.clients.ai_client import AIContractError, AITimeoutError

class CoreError(RuntimeError):

    def __init__(self, code='SERVICE_UNAVAILABLE', status=503):
        self.code = code
        self.status = status
        super().__init__('Supervisor request unavailable')

class SupervisorService:

    def __init__(self, session, *, principal, client, resolver_factory=StockResolverService):
        self.session = session
        self.principal = principal
        self.client = client
        self.resolver_factory = resolver_factory

    async def rollback(self):
        try:
            await self.session.rollback()
        except Exception:
            pass

    async def auth(self):
        await validate_principal(self.session, self.principal, lock=True)

    async def exchange(self, input, request_id, trace_id):
        payload = dict(schema_version=VERSION, request_id=str(request_id), trace_id=str(trace_id), data=input, error=None)
        value = await self.client.plan_supervisor_core(payload)
        if type(value) is not dict or set(value) != {'schema_version', 'request_id', 'trace_id', 'data', 'error'} or value['schema_version'] != VERSION or (value['request_id'] != str(request_id)) or (value['trace_id'] != str(trace_id)) or (value['error'] is not None):
            raise CoreInvalid()
        return InternalOutput.model_validate(value['data'])

    async def prepare(self, draft, request_id):
        try:
            async with asyncio.timeout(15):
                await self.session.rollback()
                plan = await self._prepare(draft, request_id)
                await self.auth()
                await self.session.commit()
                return plan
        except asyncio.CancelledError:
            await self.rollback()
            raise
        except AuthenticationRequired:
            await self.rollback()
            raise
        except CoreError:
            await self.rollback()
            raise
        except (TimeoutError, AITimeoutError):
            await self.rollback()
            raise CoreError('DEADLINE_EXCEEDED', 504) from None
        except (CoreInvalid, AIContractError):
            await self.rollback()
            raise CoreError('RESULT_CONTRACT_INVALID', 502) from None
        except Exception:
            await self.rollback()
            raise CoreError() from None

    async def _prepare(self, draft, request_id):
        trace = uuid4()
        start = await self.exchange(dict(phase='start', draft=draft.model_dump(mode='json')), request_id, trace)
        frame = start.frame
        if frame.original_query != draft.original_query or frame.answers != draft.answers or frame.revision != draft.revision:
            raise CoreInvalid()
        if start.action != 'resolve_stock':
            if start.plan is None or start.lookup is not None:
                raise CoreInvalid()
            plan = validate_plan(start.plan.model_dump(mode='json'), draft)
            if plan.status not in {'needs_clarification', 'unsupported'} or plan.resolution is not None or plan.selected_views:
                raise CoreInvalid()
            return plan
        if start.plan is not None or frame.unresolved_slots or start.lookup not in {m.text for m in frame.mentions if not m.negated} or ('flow' not in frame.requested_views):
            raise CoreInvalid()
        async with asyncio.timeout(3):
            async with self.session.begin():
                raw = await self.resolver_factory(self.session).resolve(start.lookup)
        raw = raw.model_dump(mode='json')
        raw['candidates'] = [{k: v for (k, v) in c.items() if k != 'matched_text'} for c in raw['candidates']]
        resolution = Resolution.model_validate(raw)
        ref = candidate_ref(draft, resolution)
        if draft.selected_ticker is not None and (resolution.status != 'ambiguous' or draft.selected_ticker not in {c.stock_code for c in resolution.candidates}):
            raise CoreError('INPUT_INVALID', 422)
        async with asyncio.timeout(3):
            last = await self.exchange(dict(phase='continue', draft=draft.model_dump(mode='json'), frame=frame.model_dump(mode='json'), resolution=resolution.model_dump(mode='json')), request_id, trace)
        if last.action != 'final' or last.lookup is not None or last.frame != frame or (last.plan is None):
            raise CoreInvalid()
        plan = validate_plan(last.plan.model_dump(mode='json'), draft)
        expected = resolution
        if draft.selected_ticker is not None and ref == draft.candidate_ref:
            c = next((c for c in resolution.candidates if c.stock_code == draft.selected_ticker))
            expected = Resolution(status='resolved', reason='exact_match', stock=Stock(**c.model_dump(exclude={'match_type'})), candidates=[])
        if plan.resolution != expected or plan.frame != frame or plan.candidate_ref != ref:
            raise CoreInvalid()
        if draft.selected_ticker is not None and ref != draft.candidate_ref and (plan.status != 'selection_stale'):
            raise CoreInvalid()
        return plan

    def checked(self, binding, digest=None):
        if digest is not None and binding.confirm_digest != digest:
            raise CoreError('IDEMPOTENCY_CONFLICT', 409)
        if binding.redacted_at is not None:
            raise CoreError('RESOURCE_NOT_FOUND', 404)
        if binding.plan_json is None or binding.flow_input_json is None or hashlib.sha256(binding.plan_json.encode()).hexdigest() != binding.plan_sha256 or (hashlib.sha256(binding.flow_input_json.encode()).hexdigest() != binding.flow_sha256):
            raise CoreInvalid()
        return binding

    async def post(self, body, request_id):
        digest = sha(body.model_dump(mode='json', exclude={'preparation_id'} if body.preparation_id is None else set()))
        key = hashlib.sha256(body.client_key.encode()).digest()
        try:
            await self.session.rollback()
            await self.auth()
            row = await repo.by_key(self.session, self.principal.user_id, key)
            binding = repo.snapshot(row) if row is not None else None
            await self.session.commit()
            if binding is None and body.preparation_id is not None:
                from src.modules.supervisor.application.preparation_service import PreparationService
                from src.modules.supervisor.infrastructure.preparation_repository import PreparationConflict
                try:
                    binding = await PreparationService(self.session, principal=self.principal, client=self.client, resolver_factory=self.resolver_factory).adopt(body, digest, key)
                except PreparationConflict as error:
                    raise CoreError(error.code, error.status) from None
                self.checked(binding, digest)
                await self.session.commit()
            if binding is None:
                plan = await self.prepare(body.draft, request_id)
                if plan.plan_hash != body.expected_plan_hash:
                    raise CoreError('PLAN_STALE', 409)
                try:
                    saved = confirmed_plan(plan, body.consent)
                except CoreInvalid:
                    raise CoreError('INPUT_INVALID', 422) from None
                await self.auth()
                row = await repo.by_key(self.session, self.principal.user_id, key)
                if row is None:
                    id = uuid4()
                    stamp = await self.session.scalar(select(func.clock_timestamp()))
                    flow = flow_body(plan, id, stamp)
                    plan_json = canonical(saved)
                    flow_json = canonical(flow)
                    row = await repo.admit(self.session, dict(id=id, owner_user_id=self.principal.user_id, client_key_digest=key, confirm_digest=digest, plan_json=plan_json, plan_sha256=hashlib.sha256(plan_json.encode()).hexdigest(), flow_input_json=flow_json, flow_sha256=hashlib.sha256(flow_json.encode()).hexdigest(), flow_key_digest=hashlib.sha256(str(id).encode()).digest(), confirmed_at=stamp, handoff_before=stamp + timedelta(seconds=120)))
                    if row is None:
                        row = await repo.by_key(self.session, self.principal.user_id, key)
                if row is None:
                    raise CoreError()
                binding = repo.snapshot(row)
                self.checked(binding, digest)
                # Unknown commit ACK exits without Flow; later primary row replay recovers.
                await self.session.commit()
            self.checked(binding, digest)
            await self.auth()
            run = await repo.flow_run(self.session, binding)
            stamp = await self.session.scalar(select(func.clock_timestamp()))
            if run is None and stamp > binding.handoff_before:
                raise CoreError('HANDOFF_EXPIRED', 409)
            # End the binding transaction before entering the existing Flow service.
            await self.session.commit()
            view = await AnalysisService(self.session, principal=self.principal, client=self.client).post(AnalysisRequest.model_validate(decode(binding.flow_input_json)), request_id)
            return await self.observe(binding.id, view)
        except asyncio.CancelledError:
            await self.rollback()
            raise
        except (AuthenticationRequired, CoreError, AnalysisError):
            await self.rollback()
            raise
        except CoreInvalid:
            await self.rollback()
            raise CoreError('RESULT_CONTRACT_INVALID', 502) from None
        except Exception:
            await self.rollback()
            raise CoreError() from None

    async def get(self, id):
        try:
            await self.session.rollback()
            await self.auth()
            row = await repo.owned(self.session, self.principal.user_id, id)
            if row is None:
                raise CoreError('RESOURCE_NOT_FOUND', 404)
            binding = repo.snapshot(row)
            if binding.redacted_at is not None:
                await self.session.commit()
                return outcome(binding)
            self.checked(binding)
            run = await repo.flow_run(self.session, binding)
            run_id = run.id if run is not None else None
            state = run.state if run is not None else None
            await self.session.commit()
            if state == 'deleted':
                return await self.observe(id, missing_error=CoreError('RESOURCE_NOT_FOUND', 404))
            try:
                view = await AnalysisService(self.session, principal=self.principal, client=self.client).get(run_id) if run_id is not None else None
            except AnalysisError as error:
                code = error.code.value if hasattr(error.code, 'value') else error.code
                if code != 'RESOURCE_NOT_FOUND':
                    raise
                await self.session.rollback()
                return await self.observe(id, missing_error=error)
            return await self.observe(id, view)
        except asyncio.CancelledError:
            await self.rollback()
            raise
        except (AuthenticationRequired, CoreError, AnalysisError):
            await self.rollback()
            raise
        except Exception:
            await self.rollback()
            raise CoreError() from None

    async def observe(self, id, view=None, missing_error=None):
        await self.auth()
        row = await repo.owned(self.session, self.principal.user_id, id)
        if row is None:
            raise CoreError('RESOURCE_NOT_FOUND', 404)
        binding = repo.snapshot(row)
        if missing_error is not None and binding.redacted_at is None:
            raise missing_error
        result = outcome(binding, view)
        await self.session.commit()
        return result
