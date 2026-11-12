"""Core authentication/CSRF/private response boundary; no direct AI proxy."""
import asyncio
import math
from contextlib import AsyncExitStack
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, Request, Response
from fastapi.routing import APIRoute
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from db.session import get_session
from src.shared.config import settings
from src.shared.infrastructure.clients.ai_client import AIClient
from src.modules.auth.api.router import request_principal
from src.modules.auth.application.session_service import AuthenticationRequired
from src.modules.flow.application.analysis_service import AnalysisError
from src.modules.flow.api.run_schemas import PRIVATE, http_request_id
from src.modules.supervisor.application.service import SupervisorService, CoreError
from src.modules.supervisor.application.preparation_service import PreparationService
from src.modules.supervisor.infrastructure.preparation_repository import PreparationConflict
from src.modules.supervisor.api.schemas import Confirm, Draft, PATH, PrepareResponse, RequestResponse, PreparationRequest, PreparationResponse

def failure(scope, code, status):
    known = {'INPUT_INVALID', 'AUTH_REQUIRED', 'AUTH_REQUEST_INVALID', 'FEATURE_UNAVAILABLE', 'SERVICE_UNAVAILABLE', 'DEADLINE_EXCEEDED', 'RESULT_CONTRACT_INVALID', 'PLAN_STALE', 'IDEMPOTENCY_CONFLICT', 'RESOURCE_NOT_FOUND', 'HANDOFF_EXPIRED', 'USAGE_LIMIT_EXCEEDED', 'PREPARATION_EXPIRED', 'PREPARATION_DELETED', 'PREPARATION_CONSUMED', 'MEANING_LIMIT_EXCEEDED'}
    if code not in known:
        code = 'SERVICE_UNAVAILABLE'
        status = 503
    return JSONResponse(dict(schema_version='supervisor.core.v1', request_id=str(http_request_id(scope)), trace_id=str(uuid4()), data=None, error=dict(code=code, message='Supervisor request unavailable')), status_code=status, headers=PRIVATE)

def finite_deadline(value):
    return type(value) in {int, float} and (type(value) is int or math.isfinite(value))


def preparation_deadlines(request, now):
    """Latch one public deadline; a route without middleware retains the short bound."""
    state = request.scope.setdefault('state', {})
    started = state.get('core_preparation_started_at')
    total = state.get('core_deadline')
    admission = state.get('core_admission_deadline')
    if started is None:
        if total is not None and not finite_deadline(total):
            raise TimeoutError()
        total = min(total, now + 15) if total is not None else now + 15
        if admission is not None:
            if not finite_deadline(admission):
                raise TimeoutError()
            total = min(total, admission)
        admission = total
    else:
        if not all(finite_deadline(value) for value in (started, total, admission)) or started > now:
            raise TimeoutError()
        total = min(total, started + 75)
        admission = min(admission, total, started + 15)
    if now >= min(total, admission):
        raise TimeoutError()
    state['core_deadline'], state['core_admission_deadline'] = total, admission
    return total


class CoreRoute(APIRoute):

    def get_route_handler(self):
        handler = super().get_route_handler()

        async def safe(request):
            try:
                prior = request.scope.get('fastapi_function_astack')
                try:
                    now = asyncio.get_running_loop().time()
                    if request.method == 'POST' and request.url.path == PATH + '/preparations':
                        deadline = preparation_deadlines(request, now)
                    else:
                        timeout = 140 if request.method == 'POST' and request.url.path.endswith('/requests') else 15
                        deadline = request.scope.get('state', {}).get('core_deadline', now + timeout)
                    async with asyncio.timeout_at(deadline):
                        async with AsyncExitStack() as stack:
                            request.scope['fastapi_function_astack'] = stack
                            response = await handler(request)
                finally:
                    request.scope['fastapi_function_astack'] = prior
                if len(response.body) > 65536:
                    return failure(request.scope, 'RESULT_CONTRACT_INVALID', 502)
                response.headers.update(PRIVATE)
                return response
            except PreparationConflict as e:
                return failure(request.scope, e.code, e.status)
            except CoreError as e:
                return failure(request.scope, e.code, e.status)
            except AnalysisError as e:
                code = e.code.value if hasattr(e.code, 'value') else e.code
                return failure(request.scope, code, {'RESOURCE_NOT_FOUND': 404, 'IDEMPOTENCY_CONFLICT': 409, 'USAGE_LIMIT_EXCEEDED': 429, 'FEATURE_UNAVAILABLE': 403}.get(code, 503))
            except AuthenticationRequired:
                return failure(request.scope, 'AUTH_REQUIRED', 401)
            except RequestValidationError:
                return failure(request.scope, 'INPUT_INVALID', 422)
            except HTTPException as e:
                return failure(request.scope, 'AUTH_REQUIRED' if e.status_code == 401 else 'AUTH_REQUEST_INVALID', 401 if e.status_code == 401 else 403)
            except TimeoutError:
                return failure(request.scope, 'DEADLINE_EXCEEDED', 504)
            except Exception:
                return failure(request.scope, 'SERVICE_UNAVAILABLE', 503)
        return safe
router = APIRouter(prefix=PATH, route_class=CoreRoute, tags=['supervisor-core'])

async def service(request: Request, session=Depends(get_session, scope='function')):
    if request.method == 'POST' and request.url.path == PATH + '/preparations':
        state = request.scope.get('state', {})
        total, admission = state.get('core_deadline'), state.get('core_admission_deadline')
        if not all(finite_deadline(value) for value in (total, admission)):
            raise TimeoutError()
        deadline = min(total, admission)
        if asyncio.get_running_loop().time() >= deadline:
            raise TimeoutError()
        async with asyncio.timeout_at(deadline):
            principal = await request_principal(request, session, mutation=True)
        if asyncio.get_running_loop().time() >= deadline:
            raise TimeoutError()
    else:
        principal = await request_principal(request, session, mutation=request.method in {'POST', 'DELETE'})
    return SupervisorService(session, principal=principal, client=AIClient(settings.AI_SERVICE_URL, 125, service_token=settings.FLOW_SERVICE_TOKEN))

def envelope(request, data):
    return dict(schema_version='supervisor.core.v1', request_id=str(http_request_id(request.scope)), trace_id=str(uuid4()), data=data, error=None)

@router.post('/prepare', response_model=PrepareResponse)
async def prepare(request: Request, body: Draft, value=Depends(service)):
    return envelope(request, (await value.prepare(body, http_request_id(request.scope))).model_dump(mode='json'))

@router.post('/requests', response_model=RequestResponse)
async def post(request: Request, body: Confirm, response: Response, value=Depends(service)):
    result = await value.post(body, http_request_id(request.scope))
    response.status_code = 202 if result['coverage'] == 'pending' else 200
    return envelope(request, result)

@router.get('/requests/{supervisor_id}', response_model=RequestResponse)
async def get(request: Request, supervisor_id: UUID, value=Depends(service)):
    return envelope(request, await value.get(supervisor_id))


def preparations(value):
    from src.modules.supervisor.domain.meaning_accounting import RuntimePolicy
    # Parse only on new root supplementation metadata, never startup or GET.
    policy=RuntimePolicy(getattr(settings,'SUPERVISOR_MEANING_ENABLED',False),getattr(settings,'SUPERVISOR_MEANING_ACCOUNT_BINDINGS',''),getattr(settings,'SUPERVISOR_MEANING_COUNTER_AGREEMENT',''))
    return PreparationService(value.session, principal=value.principal, client=value.client, resolver_factory=value.resolver_factory, meaning_policy=policy)


@router.post('/preparations', response_model=PreparationResponse)
async def prepare_once(request: Request, body: PreparationRequest, response: Response, value=Depends(service)):
    deadline = request.scope.get('state', {}).get('core_deadline')
    if not finite_deadline(deadline) or asyncio.get_running_loop().time() >= deadline:
        raise TimeoutError()
    result = await preparations(value).post(body, http_request_id(request.scope), deadline=deadline)
    response.status_code = 202 if result['state'] == 'pending' else 200
    return envelope(request, result)


@router.get('/preparations/{preparation_id}', response_model=PreparationResponse)
async def preparation_get(request: Request, preparation_id: UUID, value=Depends(service)):
    return envelope(request, await preparations(value).get(preparation_id))


@router.delete('/preparations/{preparation_id}', response_model=PreparationResponse)
async def preparation_delete(request: Request, preparation_id: UUID, value=Depends(service)):
    return envelope(request, await preparations(value).delete(preparation_id))
