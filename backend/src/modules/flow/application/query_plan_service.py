"""Authenticated tool orchestration; intent belongs exclusively to AI planning."""
import asyncio
from uuid import uuid4
from src.modules.auth.application.session_service import AuthenticationRequired,validate_principal
from src.modules.stocks.application.resolver_service import StockResolverService,EmptyQueryError
from src.shared.infrastructure.clients.ai_client import AIContractError,AIUnavailableError,AITimeoutError
from src.modules.flow.domain.query_plan import VERSION,POLICY,digest,PlanView,QueryPlanError,resolver_result,resolution_ref,validate_wire

class QueryPlanService:
    def __init__(self,session,*,principal,client,resolver_factory=StockResolverService,deadline_at=None):
        self.session=session;self.principal=principal;self.client=client;self.resolver_factory=resolver_factory;self.deadline_at=deadline_at
    async def prepare(self,body,request_id):
        # The dependency's authentication transaction must not span any AI wait.
        try:
            async with asyncio.timeout_at(self.deadline_at if self.deadline_at is not None else asyncio.get_running_loop().time()+10):
                await self.session.rollback()
                result=await self._prepare(body,str(request_id))
                # New transaction + fresh SQL session/user validation, not a cached Principal check.
                async with self.session.begin():await validate_principal(self.session,self.principal)
                return result
        except AuthenticationRequired:raise
        except QueryPlanError:raise
        except (TimeoutError,AITimeoutError):raise QueryPlanError('DEADLINE_EXCEEDED',504) from None
        except AIContractError:raise QueryPlanError() from None
        except EmptyQueryError:raise QueryPlanError('INPUT_INVALID',422) from None
        except Exception:raise QueryPlanError('SERVICE_UNAVAILABLE',503) from None
    async def _prepare(self,body,request_id):
        request=dict(phase='start',query=body.query,request_id=request_id,trace_id=str(uuid4()),policy_version=POLICY,query_sha256=digest(body.query))
        async with asyncio.timeout(3):start=validate_wire(await self.client.plan_flow(request),request)
        if start['kind']=='final':
            if body.selected_ticker is not None:raise QueryPlanError('INPUT_INVALID',422)
            return PlanView.model_validate(start['plan'])
        async with asyncio.timeout(3):
            async with self.session.begin():raw=await self.resolver_factory(self.session).resolve(body.query)
        resolution=resolver_result(raw);reference=resolution_ref(body.query,resolution)
        if body.selected_ticker is not None:
            if resolution.status!='ambiguous' or body.selected_ticker not in {c.stock_code for c in resolution.candidates}:raise QueryPlanError('INPUT_INVALID',422)
            if reference!=body.candidate_ref:
                return PlanView(version=VERSION,policy_version=POLICY,query_sha256=digest(body.query),requested_views=start['requested_views'],status='selection_stale',reason='selection_changed',resolution=resolution,candidate_ref=reference)
        continuation={**request,'phase':'continue','requested_views':start['requested_views'],'resolution':resolution.model_dump(mode='json'),'selected_ticker':body.selected_ticker,'candidate_ref':body.candidate_ref}
        async with asyncio.timeout(3):
            value=validate_wire(await self.client.plan_flow(continuation),continuation,start=start,resolution=resolution,selected=body.selected_ticker)
        return PlanView.model_validate(value['plan'])
