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
    async def execution_request(request,ready=False):
        from src.agents.technical.domain import execution_contracts as P
        from src.agents.technical.application.execution_runtime import TechnicalProviderRuntime
        try:
            runtime=getattr(request.app.state,'technical_execution_runtime',None)
            if type(runtime) is not TechnicalProviderRuntime:raise P.ExecutionInvalid()
            path='/internal/technical/execution/ready' if ready else '/internal/technical/execution'
            scope=request.scope
            if scope['method']!='POST' or scope['path']!=path or scope.get('raw_path',path.encode())!=path.encode() or scope.get('query_string'):raise P.ExecutionInvalid()
            values={};allowed={b'host',b'content-type',b'content-length',b'accept',b'accept-encoding',b'user-agent',b'connection',b'x-technical-service-token'}
            if not ready:allowed.add(b'x-technical-execution-grant')
            for key,value in scope.get('headers',[]):
                key=key.lower()
                if key not in allowed or key in values or any(c<32 or c>126 for c in value):raise P.ExecutionInvalid()
                values[key]=value
            if not hmac.compare_digest(runtime.service_token,values.get(b'x-technical-service-token',b'')):return error('AUTH_REQUIRED',401)
            if values.get(b'content-type',b'').lower()!=b'application/json':raise P.ExecutionInvalid()
            cap=32768 if ready else 65536;length=values.get(b'content-length')
            if length is not None and (not length.isdigit() or len(length)>8 or int(length)>cap):raise P.ExecutionInvalid()
            raw=bytearray()
            async with asyncio.timeout(5):
                async for chunk in request.stream():
                    if len(raw)+len(chunk)>cap:raise P.ExecutionInvalid()
                    raw.extend(chunk)
            if length is not None and int(length)!=len(raw):raise P.ExecutionInvalid()
            value=P.decode(raw,cap)
            if ready:
                P.shape(value,{'schema_version'})
                if value['schema_version']!=P.SCHEMA:raise P.ExecutionInvalid()
                return JSONResponse(runtime.readiness(),headers=PRIVATE)
            grant=values.get(b'x-technical-execution-grant',b'').decode('ascii');P.digest(grant)
            result=await runtime.execute(value,grant)
            if len(P.canonical(result).encode('utf8'))>2097152:raise P.ExecutionInvalid()
            return JSONResponse(result,headers=PRIVATE)
        except asyncio.CancelledError:raise
        except TimeoutError:return error('DEADLINE_EXCEEDED',504)
        except Exception:return error('SERVICE_UNAVAILABLE',503)
    @router.post('/execution/ready',include_in_schema=False)
    async def execution_ready(request:Request):return await execution_request(request,True)
    @router.post('/execution',include_in_schema=False)
    async def execution_run(request:Request):return await execution_request(request)
    return router
router=make_router()
