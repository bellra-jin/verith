"""Explicit, default-off composition API; native single-agent routes are unchanged."""
import asyncio
import math
import re
from contextlib import AsyncExitStack
from datetime import datetime, UTC
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, Request
from fastapi.routing import APIRoute
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from db.session import get_session
from src.shared.config import settings
from src.modules.auth.api.router import request_principal
from src.modules.auth.application.session_service import AuthenticationRequired
from src.modules.supervisor.domain import composition_api as C
from src.modules.supervisor.domain.contracts import Draft, decode
from src.modules.supervisor.application.service import SupervisorService, CoreError
from src.modules.supervisor.application.composition_service import CompositionError
from src.modules.supervisor.application.composition_api_service import CompositionAPIService
from src.shared.infrastructure.clients.ai_client import AIClient
from src.modules.flow.api.run_schemas import PRIVATE, http_request_id

PATH = '/api/supervisor/core/composition'
RESULT_LIMIT = 2097152


def response(scope, data=None, *, code=None, status=200):
    return JSONResponse(dict(schema_version=C.VERSION, request_id=str(http_request_id(scope)),
        trace_id=str(uuid4()), data=data, error=None if code is None else dict(code=code,message='Supervisor request unavailable')),
        status_code=status,headers=PRIVATE)


async def boundary(app, scope, receive, send):
    """Called only for this exact prefix before the legacy core middleware branch."""
    from src.modules.auth.api.router import configured
    path, method = scope['path'], scope['method']
    loop=asyncio.get_running_loop(); started=loop.time()
    state=scope.setdefault('state',{})
    state['composition_started_at']=datetime.now(UTC)
    state['composition_deadline']=started+(140 if method=='POST' and path==PATH+'/requests' else 15)
    state['composition_admission_deadline']=started+15
    raw=None
    try:
        if (scope.get('query_string') or scope.get('raw_path',path.encode())!=path.encode()
                or not (method=='POST' and path in {PATH+'/prepare',PATH+'/requests'}
                    or method=='GET' and re.fullmatch(re.escape(PATH)+r'/requests/[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',path))): raise ValueError()
        if not configured():
            await response(scope,code='AUTH_REQUIRED',status=401)(scope,receive,send);return
        headers=scope.get('headers',[])
        if len({k.lower() for k,v in headers})!=len(headers):raise ValueError()
        if method=='POST':
            ct=[v for k,v in headers if k.lower()==b'content-type'];cl=[v for k,v in headers if k.lower()==b'content-length']
            if (len(ct)!=1 or ct[0].split(b';')[0].strip().lower()!=b'application/json'
                    or any(k.lower()==b'content-encoding' for k,v in headers)
                    or cl and (not cl[0].isdigit() or int(cl[0])>16384)):raise ValueError()
            raw=bytearray()
            async with asyncio.timeout_at(state['composition_admission_deadline']):
                while True:
                    message=await receive()
                    if message['type']!='http.request':raise ValueError()
                    raw.extend(message.get('body',b''))
                    if len(raw)>16384:raise ValueError()
                    if not message.get('more_body',False):break
            if cl and len(raw)!=int(cl[0]):raise ValueError()
            (Draft if path.endswith('/prepare') else C.Confirm).model_validate(decode(raw))
    except TimeoutError:
        await response(scope,code='DEADLINE_EXCEEDED',status=504)(scope,receive,send);return
    except (ValueError,TypeError,UnicodeError,RecursionError):
        await response(scope,code='INPUT_INVALID',status=422)(scope,receive,send);return
    delivered=False
    async def replay():
        nonlocal delivered
        if raw is not None and not delivered:
            delivered=True;return dict(type='http.request',body=bytes(raw),more_body=False)
        return await receive()
    await app(scope,replay,send)


class CompositionRoute(APIRoute):
    def get_route_handler(self):
        handler=super().get_route_handler()
        async def safe(request):
            state=request.scope.setdefault('state',{});loop=asyncio.get_running_loop();now=loop.time()
            # Standalone ASGI tests retain the same ingress limits without middleware.
            state.setdefault('composition_started_at',datetime.now(UTC))
            state.setdefault('composition_admission_deadline',now+15)
            state.setdefault('composition_deadline',now+(140 if request.method=='POST' and request.url.path==PATH+'/requests' else 15))
            try:
                deadline=state['composition_deadline']
                if type(deadline) not in {int,float} or not math.isfinite(deadline):raise TimeoutError()
                prior=request.scope.get('fastapi_function_astack')
                try:
                    async with asyncio.timeout_at(deadline):
                        async with AsyncExitStack() as stack:
                            request.scope['fastapi_function_astack']=stack
                            result=await handler(request)
                finally:request.scope['fastapi_function_astack']=prior
                if len(result.body)>RESULT_LIMIT:return response(request.scope,code='RESULT_CONTRACT_INVALID',status=502)
                result.headers.update(PRIVATE);return result
            except AuthenticationRequired:return response(request.scope,code='AUTH_REQUIRED',status=401)
            except CoreError as error:return response(request.scope,code=error.code,status=error.status)
            except CompositionError as error:
                code,status={'NOT_FOUND':('RESOURCE_NOT_FOUND',404),'CONFLICT':('IDEMPOTENCY_CONFLICT',409),'EXPIRED':('HANDOFF_EXPIRED',409)}.get(error.code,('SERVICE_UNAVAILABLE',503))
                return response(request.scope,code=code,status=status)
            except RequestValidationError:return response(request.scope,code='INPUT_INVALID',status=422)
            except HTTPException as error:return response(request.scope,code='AUTH_REQUIRED' if error.status_code==401 else 'AUTH_REQUEST_INVALID',status=401 if error.status_code==401 else 403)
            except TimeoutError:return response(request.scope,code='DEADLINE_EXCEEDED',status=504)
            except Exception:return response(request.scope,code='SERVICE_UNAVAILABLE',status=503)
        return safe


router=APIRouter(prefix='/composition',route_class=CompositionRoute,tags=['supervisor-composition'])


async def service(request:Request,session=Depends(get_session,scope='function')):
    from src.modules.technical.api.execution_authority_router import enabled
    from src.modules.technical.domain import provider_execution as P
    from src.modules.analysis.domain.usage import policy
    deadline=request.scope['state']['composition_admission_deadline']
    async with asyncio.timeout_at(deadline):
        principal=await request_principal(request,session,mutation=request.method=='POST')
    # GET and replay never parse current settings or require current AI clients.
    def flow():
        if not settings.FLOW_ANALYSIS_ENABLED:raise CoreError('FEATURE_UNAVAILABLE',403)
        p=policy(settings)
        return dict(supported_tickers=sorted(p.tickers),user_limit=p.user_limit,service_limit=p.service_limit,budget=p.budget)
    def technical():
        if not enabled(settings.TECHNICAL_EXECUTION_ENABLED):raise CoreError('FEATURE_UNAVAILABLE',403)
        if P.service_token(settings.TECHNICAL_EXECUTION_AI_SERVICE_TOKEN)==P.service_token(settings.TECHNICAL_EXECUTION_AUTHORITY_TOKEN):raise CoreError('FEATURE_UNAVAILABLE',403)
        return P.Configuration(settings.TECHNICAL_EXECUTION_CONFIG)
    # Lazy construction avoids credential/config dependencies on GET/replay.
    class Planner:
        from src.modules.stocks.application.resolver_service import StockResolverService as resolver_factory
        async def exchange(self,*args):
            client=AIClient(settings.AI_SERVICE_URL,125,service_token=settings.FLOW_SERVICE_TOKEN)
            return await SupervisorService(session,principal=principal,client=client).exchange(*args)
    value=CompositionAPIService(session,principal=principal,planner=Planner(),flow_policy=flow,
        technical_configuration=technical,enabled=False)
    if request.method=='POST':
        # Parsed at use for fresh work; invalid/off gates still permit replay.
        try:value.enabled=enabled(getattr(settings,'SUPERVISOR_COMPOSITION_ENABLED',False))
        except ValueError:value.enabled=False
        value.flow_client=lambda: AIClient(settings.AI_SERVICE_URL,125,service_token=settings.FLOW_SERVICE_TOKEN)
        value.technical_client=lambda: AIClient(settings.AI_SERVICE_URL,125,execution_token=settings.TECHNICAL_EXECUTION_AI_SERVICE_TOKEN,
            technical_tls_context=getattr(request.app.state,'technical_execution_tls_context',None))
    return value


@router.post('/prepare')
async def prepare(request:Request,body:Draft,value=Depends(service)):
    data=await value.prepare(body,http_request_id(request.scope),deadline=request.scope['state']['composition_admission_deadline'])
    return response(request.scope,data)


@router.post('/requests')
async def confirm(request:Request,body:C.Confirm,value=Depends(service)):
    state=request.scope['state']
    data=await value.confirm(body,http_request_id(request.scope),started_at=state['composition_started_at'],deadline=state['composition_admission_deadline'])
    return response(request.scope,data,status=202 if data['coverage']=='pending' else 200)


@router.get('/requests/{composition_id}')
async def get(request:Request,composition_id:UUID,value=Depends(service)):
    return response(request.scope,await value.get(composition_id))
