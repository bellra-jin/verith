"""Two authenticated server-only callbacks. No browser/session-token authority."""
import asyncio
import hmac
from fastapi import APIRouter,Depends,Request
from starlette.responses import JSONResponse
from db.session import get_session
from src.shared.config import settings
from src.modules.supervisor.domain.meaning_accounting import AccountingConflict,RuntimePolicy,strict_json
from src.modules.supervisor.application.meaning_accounting_service import MeaningRuntimeService

PATHS=frozenset({'/internal/supervisor/meaning/authorize','/internal/supervisor/meaning/settle'})
PRIVATE={'Cache-Control':'private, no-store'}
def failure(status=403):
    return JSONResponse({'error':{'code':'MEANING_AUTHORIZATION_UNAVAILABLE'}},status_code=status,headers=PRIVATE)

def authenticate_headers(scope,token):
    # The middleware and route use the same exact contract. No body/DB access.
    if scope.get('method')!='POST' or scope.get('path') not in PATHS or scope.get('query_string') or scope.get('raw_path',scope['path'].encode())!=scope['path'].encode(): raise AccountingConflict()
    if type(token) is not str or not 32<=len(token)<=512 or any(not 33<=ord(c)<=126 for c in token): raise AccountingConflict()
    values={}
    allowed={b'host',b'content-type',b'content-length',b'accept',b'accept-encoding',b'user-agent',b'connection',b'x-supervisor-meaning-service-token',b'x-supervisor-meaning-grant'}
    for k,v in scope.get('headers',[]):
        k=k.lower()
        if k not in allowed or k in values or any(c<32 or c>126 for c in v): raise AccountingConflict()
        values[k]=v
    if not hmac.compare_digest(values.get(b'x-supervisor-meaning-service-token',b''),token.encode('ascii')): raise AccountingConflict()
    handle=values.get(b'x-supervisor-meaning-grant',b'').decode('ascii')
    MeaningRuntimeService.handle(handle)
    if values.get(b'content-type',b'').lower()!=b'application/json': raise AccountingConflict()
    length=values.get(b'content-length')
    limit=98304 if scope['path'].endswith('/authorize') else 8192
    if length is not None and (not length.isdigit() or len(length)>8 or int(length)>limit): raise AccountingConflict()
    return handle

def configured_policy():
    return RuntimePolicy(settings.SUPERVISOR_MEANING_ENABLED,settings.SUPERVISOR_MEANING_ACCOUNT_BINDINGS,settings.SUPERVISOR_MEANING_COUNTER_AGREEMENT)

router=APIRouter(include_in_schema=False)
async def callback(request:Request,session=Depends(get_session,scope='function')):
    try:
        handle=authenticate_headers(request.scope,settings.SUPERVISOR_MEANING_SERVICE_TOKEN)
        loop=asyncio.get_running_loop()
        deadline=min(loop.time()+5,request.scope.get('state',{}).get('meaning_callback_deadline',loop.time()+5))
        async with asyncio.timeout_at(deadline):
            raw=bytearray();settle=request.url.path.endswith('/settle');limit=8192 if settle else 98304
            async for chunk in request.stream():
                if len(raw)+len(chunk)>limit: raise AccountingConflict()
                raw.extend(chunk)
            value=strict_json(raw,limit)
            if not settle and type(value) is dict and value.get('phase')!='count' and len(raw)>8192: raise AccountingConflict()
            service=MeaningRuntimeService(session,runtime_policy=configured_policy())
            result=await service.finish(handle,value) if settle else await service.reconcile_phase(handle,value) if type(value) is dict and value.get('action')=='reconcile' else await service.authorize(handle,value)
            return JSONResponse(result,headers=PRIVATE)
    except asyncio.CancelledError:
        raise
    except TimeoutError:
        return failure(504)
    except Exception:
        # No raw errors/requests/nonces are returned or logged.
        return failure(403)
for path in sorted(PATHS): router.add_api_route(path,callback,methods=['POST'],include_in_schema=False)
