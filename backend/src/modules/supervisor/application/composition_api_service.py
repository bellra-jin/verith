"""Server planning and confirmed invocation; replay only observes a fixed root."""
import asyncio
import hashlib
import time
from uuid import UUID, uuid4
from src.modules.auth.application.session_service import validate_principal, AuthenticationRequired
from src.modules.supervisor.application.service import SupervisorService, CoreError
from src.modules.supervisor.application.composition_service import CompositionService, CompositionError, database_uuid
from src.modules.supervisor.application.composition_runtime import CompositionRuntime
from src.modules.supervisor.domain import composition_api as C
from src.modules.supervisor.domain.composition import CompositionSnapshot, PROJECTED_VERSION, projected_inputs
from src.modules.supervisor.domain.contracts import canonical, Resolution
from src.modules.supervisor.infrastructure import composition_repository as repo


class CompositionAPIService:
    def __init__(self, session, *, principal, planner, flow_policy, technical_configuration,
                 flow_client=None, technical_client=None, enabled=False, resolver_factory=None):
        self.session, self.principal = session, principal
        self.planner, self.flow_policy, self.technical_configuration = planner, flow_policy, technical_configuration
        self.flow_client, self.technical_client, self.enabled = flow_client, technical_client, enabled
        self.resolver_factory = resolver_factory or planner.resolver_factory

    async def _snapshot(self, draft, request_id, deadline):
        if self.enabled is not True: raise CoreError('FEATURE_UNAVAILABLE', 403)
        await self.session.rollback()
        async with asyncio.timeout_at(deadline):
            first = await self.planner.exchange(dict(phase='start', draft=draft.model_dump(mode='json')), request_id, uuid4())
            frame = first.frame
            if (frame.original_query != draft.original_query or frame.answers != draft.answers
                    or frame.revision != draft.revision): raise CoreError('RESULT_CONTRACT_INVALID', 502)
            active = [m for m in frame.mentions if not m.negated]
            views = [v for v in ('flow', 'technical') if v in frame.requested_views]
            if (frame.unresolved_slots or frame.conditions or frame.interpretation_source != 'deterministic'
                    or len({m.text for m in active}) != 1 or not views
                    or len(views) != len(frame.requested_views) or draft.selected_ticker is not None):
                return None
            await validate_principal(self.session, self.principal, lock=True)
            resolver = self.resolver_factory(self.session)
            raw = await resolver.resolve(active[0].text)
            data = raw.model_dump(mode='json')
            data['candidates'] = [{k:v for k,v in c.items() if k != 'matched_text'} for c in data['candidates']]
            resolution = Resolution.model_validate(data)
            if resolution.status != 'resolved':
                await self.session.rollback(); return None
            stock = resolution.stock.model_dump(mode='json')
            for mention in frame.mentions:
                if mention.negated:
                    negative = await resolver.resolve(mention.text)
                    if negative.status != 'resolved' or negative.stock is None or negative.stock.stock_code == stock['stock_code']:
                        await self.session.rollback(); return None
            # No SQL lock survives the native readiness/planning boundary.
            await self.session.commit()
            flow = self.flow_policy() if 'flow' in views else None
            cfg = self.technical_configuration() if 'technical' in views else None
            snapshot = CompositionSnapshot(canonical(dict(schema_version=PROJECTED_VERSION,
                draft=draft.model_dump(mode='json'), frame=frame.model_dump(mode='json'), stock=stock,
                selected_views=views, child_inputs=projected_inputs(stock,draft.original_query,views),
                consent=dict(allow_views=views,allow_partial_results=len(views)==2,waived_conditions=[]),
                flow_policy=flow, technical_configuration=cfg.text if cfg is not None else None)))
            if time.monotonic() >= deadline: raise TimeoutError()
            return snapshot

    async def prepare(self, draft, request_id, *, deadline):
        snapshot = await self._snapshot(draft, request_id, deadline)
        await validate_principal(self.session,self.principal); await self.session.rollback()
        return C.plan(snapshot) if snapshot is not None else dict(schema_version=C.VERSION,status='needs_clarification',plan_hash=None)

    async def confirm(self, body, request_id, *, started_at, deadline):
        # Current policies, clients and AI are unnecessary for durable replay.
        await self.session.rollback(); await validate_principal(self.session,self.principal)
        row = await repo.read(self.session,self.principal.user_id,key=hashlib.sha256(body.client_key.encode()).digest())
        if row is not None:
            snapshot = CompositionService(self.session,principal=self.principal)._checked(row)
            if snapshot is None: raise CoreError('RESOURCE_NOT_FOUND',404)
            try: C.confirms(body,snapshot)
            except ValueError: raise CoreError('IDEMPOTENCY_CONFLICT',409) from None
            id = database_uuid(row.id); await self.session.rollback()
            return await self.get(id)
        await self.session.rollback()
        snapshot = await self._snapshot(body.draft,request_id,deadline)
        if snapshot is None: raise CoreError('INPUT_INVALID',422)
        try: C.confirms(body,snapshot)
        except ValueError: raise CoreError('PLAN_STALE',409) from None
        if time.monotonic() >= deadline: raise TimeoutError()
        views=snapshot.data()['selected_views']
        flow_client=(self.flow_client() if callable(self.flow_client) else self.flow_client) if 'flow' in views else None
        technical_client=(self.technical_client() if callable(self.technical_client) else self.technical_client) if 'technical' in views else None
        root = CompositionService(self.session,principal=self.principal)
        admitted = await root.admit(body.client_key,snapshot,request_started_at=started_at)
        runtime = CompositionRuntime(self.session,principal=self.principal,flow_client=flow_client,
                                     technical_client=technical_client,enabled=self.enabled)
        result = await runtime.execute_once(admitted)
        return await self.get(UUID(result['composition_id']))

    async def get(self, id):
        result = await CompositionService(self.session,principal=self.principal).get(id)
        # Native owned readers validate root/index/snapshot contracts. No POST,
        # re-publication or policy parsing occurs while restoring result payloads.
        for item in result['views']:
            item['result'] = None
            if item['state'] != 'stored': continue
            if item['view'] == 'flow':
                from src.modules.flow.application.report_service import FlowReportService
                stored = await FlowReportService(self.session,principal=self.principal).get_report(UUID(item['report_id']))
                if stored is not None: item['result'] = stored.model_dump(mode='json')
            else:
                from src.modules.technical.application.owned_report_service import TechnicalOwnedReportService
                stored = await TechnicalOwnedReportService(self.session,principal=self.principal).read(UUID(item['report_id']))
                if stored is not None:
                    from src.modules.supervisor.domain.contracts import decode
                    item['result'] = C.technical_result(decode(stored.frozen.result_json)['data']['result'])
            if item['result'] is None: raise CoreError('RESOURCE_NOT_FOUND',404)
        await validate_principal(self.session,self.principal); await self.session.rollback()
        return result
