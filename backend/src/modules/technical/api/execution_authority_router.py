"""Authenticated, bounded record callbacks. No browser or Flow token authority."""
import asyncio
import hmac
from contextlib import aclosing
from fastapi import APIRouter,Request
from starlette.responses import JSONResponse
from src.modules.technical.domain import provider_execution as P

PATHS=frozenset({'/internal/technical/execution/start','/internal/technical/execution/observe'})
PRIVATE={'Cache-Control':'private, no-store'}
def failure(status=403):return JSONResponse({'error':{'code':'TECHNICAL_EXECUTION_UNAVAILABLE'}},status_code=status,headers=PRIVATE)
def authenticate_headers(scope,token):
    if (scope.get('method')!='POST' or scope.get('path') not in PATHS or scope.get('query_string')
            or scope.get('raw_path',scope['path'].encode())!=scope['path'].encode()):raise P.ExecutionInvalid()
    token=P.service_token(token);values={}
    allowed={b'host',b'content-type',b'content-length',b'accept',b'accept-encoding',b'user-agent',b'connection',b'x-technical-authority-token',b'x-technical-execution-grant'}
    for key,value in scope.get('headers',[]):
        key=key.lower()
        if key not in allowed or key in values or any(c<32 or c>126 for c in value):raise P.ExecutionInvalid()
        values[key]=value
    if not hmac.compare_digest(token,values.get(b'x-technical-authority-token',b'')):raise P.ExecutionInvalid()
    grant=values.get(b'x-technical-execution-grant',b'').decode('ascii');P.digest(grant)
    limit=16384 if scope['path'].endswith('/observe') else 8192
    length=values.get(b'content-length')
    if (values.get(b'content-type',b'').lower()!=b'application/json' or length is not None
            and (not length.isdigit() or len(length)>8 or int(length)>limit)):raise P.ExecutionInvalid()
    return grant

def make_router(*,session_factory,configuration,token):
    router=APIRouter(include_in_schema=False)
    async def callback(request:Request):
        try:
            grant=authenticate_headers(request.scope,token())
            observe=request.url.path.endswith('/observe');limit=16384 if observe else 8192
            loop=asyncio.get_running_loop();deadline=min(loop.time()+5,request.scope.get('state',{}).get('technical_callback_deadline',loop.time()+5))
            async with asyncio.timeout_at(deadline):
                raw=bytearray()
                async for chunk in request.stream():
                    if len(raw)+len(chunk)>limit:raise P.ExecutionInvalid()
                    raw.extend(chunk)
                length=request.headers.get('content-length')
                if length is not None and int(length)!=len(raw):raise P.ExecutionInvalid()
                body=P.decode(raw,limit)
                # Dependency construction, DB access and rollback/close all live
                # inside this authenticated scope, including callback cancellation.
                from src.modules.technical.application.execution_authority_service import TechnicalExecutionAuthority
                async with aclosing(session_factory()) as sessions:
                    session=await anext(sessions)
                    service=TechnicalExecutionAuthority(session,configuration=None if observe else configuration())
                    result=await service.observe(body,grant) if observe else await service.start(body,grant)
                return JSONResponse(result,headers=PRIVATE)
        except asyncio.CancelledError:raise
        except TimeoutError:return failure(504)
        except Exception:return failure()
    for path in sorted(PATHS):router.add_api_route(path,callback,methods=['POST'],include_in_schema=False)
    return router

def enabled(value):
    if type(value) is bool:return value
    if type(value) is str and value.lower() in {'true','false'}:return value.lower()=='true'
    raise P.ExecutionInvalid()

def configured_router():
    from db.session import get_session
    from src.shared.config import settings
    def config():
        if not enabled(settings.TECHNICAL_EXECUTION_ENABLED):raise P.ExecutionInvalid()
        if P.service_token(settings.TECHNICAL_EXECUTION_AI_SERVICE_TOKEN)==P.service_token(settings.TECHNICAL_EXECUTION_AUTHORITY_TOKEN):raise P.ExecutionInvalid()
        return P.Configuration(settings.TECHNICAL_EXECUTION_CONFIG)
    return make_router(session_factory=get_session,configuration=config,token=lambda:settings.TECHNICAL_EXECUTION_AUTHORITY_TOKEN)
