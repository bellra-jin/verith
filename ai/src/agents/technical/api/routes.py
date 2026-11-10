"""Import-safe disabled-by-default Technical boundary factory. No production engine."""
import asyncio,hmac,math
from uuid import uuid4
from fastapi import APIRouter,Request
from starlette.responses import JSONResponse

PRIVATE={'Cache-Control':'private, no-store'}
def make_router(*,engine=None,enabled=False,service_token='',timeout=3.0):
    # Runtime/detail imports occur only after gate/auth/body, never in the default export.
    router=APIRouter(prefix='/internal/technical',tags=['technical-internal']);runtime=None
    if type(timeout) not in {int,float} or not math.isfinite(timeout) or timeout<=0:raise ValueError('Invalid boundary deadline')
    timeout=min(timeout,3.0)
    def error(code,status,ids=None):
        request_id,trace_id=ids or (str(uuid4()),str(uuid4()))
        return JSONResponse(dict(schema_version='analysis.agent.v1',request_id=request_id,trace_id=trace_id,data=None,error=dict(code=code,message='Technical boundary unavailable')),status_code=status,headers=PRIVATE)
    @router.get('/health')
    async def health():return {'status':'ok','service':'technical-boundary','version':'1.0'}
    @router.post('/analyze')
    async def legacy():return error('FEATURE_UNAVAILABLE',403)
    @router.post('/boundary')
    async def boundary(request:Request):
        nonlocal runtime
        if enabled is not True or engine is None:return error('FEATURE_UNAVAILABLE',403)
        try:token=service_token.encode('ascii')
        except (AttributeError,UnicodeError):return error('AUTH_REQUIRED',401)
        headers=request.headers;tokens=[v for k,v in request.scope['headers'] if k.lower()==b'x-technical-service-token']
        if len(token)<32 or any(c<32 or c>126 for c in token) or len(tokens)!=1 or not hmac.compare_digest(token,tokens[0]):return error('AUTH_REQUIRED',401)
        deadline=asyncio.get_running_loop().time()+timeout
        try:
            if request.url.query or len(headers.getlist('content-type'))!=1 or headers.get('content-type','').lower() not in {'application/json','application/json; charset=utf-8'} or len(headers.getlist('content-encoding'))>1 or headers.get('content-encoding') not in {None,'identity'}:raise ValueError()
            lengths=headers.getlist('content-length')
            if len(lengths)>1 or lengths and (not lengths[0].isascii() or not lengths[0].isdigit() or int(lengths[0])>16384):raise ValueError()
            raw=bytearray()
            async with asyncio.timeout_at(deadline):
                async for chunk in request.stream():
                    if len(raw)+len(chunk)>16384:raise ValueError()
                    raw.extend(chunk)
            if lengths and len(raw)!=int(lengths[0]):raise ValueError()
            from src.agents.technical.domain.boundary_contracts import decode,parse_request
            value=decode(raw);parse_request(value)
        except TimeoutError:return error('DEADLINE_EXCEEDED',504)
        except (ValueError,TypeError,UnicodeError,RecursionError):return error('INPUT_INVALID',422)
        from src.agents.technical.application.boundary_runtime import BoundaryRuntime,BoundaryBusy,BoundaryTimeout,BoundaryEngineFailure
        from src.agents.technical.domain.boundary_contracts import BoundaryInvalid,canonical
        if runtime is None:runtime=BoundaryRuntime(engine,timeout=timeout)
        ids=(value['request_id'],value['trace_id'])
        try:
            result=await runtime.run(value,remaining=max(0,deadline-asyncio.get_running_loop().time()))
            if len(canonical(result).encode('utf8'))>2097152:raise BoundaryInvalid()
            return JSONResponse(result,headers=PRIVATE)
        except BoundaryBusy:return error('BUSY',503,ids)
        except BoundaryTimeout:return error('DEADLINE_EXCEEDED',504,ids)
        except BoundaryEngineFailure:return error('RESULT_CONTRACT_INVALID',502,ids)
        except BoundaryInvalid:return error('RESULT_CONTRACT_INVALID',502,ids)
        except Exception:return error('SERVICE_UNAVAILABLE',503,ids)
    return router
router=make_router()
