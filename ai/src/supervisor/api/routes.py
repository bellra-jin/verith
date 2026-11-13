"""Import-safe Supervisor HTTP factory. Auth/gate precede planning imports."""
import asyncio
import hmac
import os
from fastapi import APIRouter,Request
from starlette.responses import JSONResponse

BODY_TIMEOUT_SECONDS=3.0
PRIVATE={'Cache-Control':'private, no-store'}
def error(status,code):
    return JSONResponse({'error':{'code':code,'message':'Supervisor plan unavailable'}},status_code=status,headers=PRIVATE)

def make_router(*,gateway=None,runtime=None,technical=False):
    router=APIRouter(prefix='/internal/supervisor',tags=['supervisor-internal'])
    @router.post('/analyze')
    async def legacy():return error(403,'FEATURE_UNAVAILABLE')
    @router.get('/health')
    async def health():return {'status':'ok','service':'supervisor-planning'}
    @router.post('/plan')
    async def prepare(request:Request):
        if os.getenv('FLOW_ANALYSIS_ENABLED')!='true':return error(403,'FEATURE_UNAVAILABLE')
        expected=os.getenv('FLOW_SERVICE_TOKEN','')
        try:token=expected.encode('ascii')
        except UnicodeError:return error(401,'AUTH_REQUIRED')
        values=[v for k,v in request.scope.get('headers',[]) if k.lower()==b'x-flow-service-token']
        if len(token)<32 or any(c<32 or c>126 for c in token) or len(values)!=1 or not hmac.compare_digest(token,values[0]):return error(401,'AUTH_REQUIRED')
        try:
            headers=request.headers
            if request.url.query or len(headers.getlist('content-type'))!=1 or headers.get('content-type','').split(';')[0].strip().lower()!='application/json' or headers.get('content-encoding') is not None:raise ValueError()
            lengths=headers.getlist('content-length')
            if len(lengths)>1 or lengths and (not lengths[0].isascii() or not lengths[0].isdigit() or int(lengths[0])>32768):raise ValueError()
            raw=bytearray()
            async with asyncio.timeout(BODY_TIMEOUT_SECONDS):
                async for part in request.stream():
                    raw.extend(part)
                    if len(raw)>32768:raise ValueError()
            from src.supervisor.domain.models import PlanInput,decode,canonical
            value=PlanInput.model_validate(decode(bytes(raw)))
        except TimeoutError:return error(504,'DEADLINE_EXCEEDED')
        except (ValueError,TypeError,UnicodeError,RecursionError):return error(422,'INPUT_INVALID')
        try:
            from src.supervisor.application.runtime import run_plan
            result=run_plan(value).model_dump(mode='json')
            if len(canonical(result).encode('utf8'))>32768:raise ValueError()
            return JSONResponse(result,headers=PRIVATE)
        except Exception:return error(502,'RESULT_CONTRACT_INVALID')
    router.include_router(make_core_router(gateway=gateway,runtime=runtime))
    if technical is True:router.include_router(make_technical_core_router())
    return router

def make_core_router(*,gateway=None,token=None,enabled=None,runtime=None):
    from uuid import uuid4
    core=APIRouter()
    def fail(status,code,ids=None):
        request_id,trace_id=ids or (str(uuid4()),str(uuid4()))
        return JSONResponse(dict(schema_version='supervisor.core.v1',request_id=request_id,trace_id=trace_id,data=None,error=dict(code=code,message='Supervisor request unavailable')),status_code=status,headers=PRIVATE)
    @core.post('/core/plan')
    async def prepare_core(request:Request):
        if (enabled if enabled is not None else os.getenv('FLOW_ANALYSIS_ENABLED')=='true') is not True:return fail(403,'FEATURE_UNAVAILABLE')
        try:expected=(token if token is not None else os.getenv('FLOW_SERVICE_TOKEN','')).encode('ascii')
        except UnicodeError:return fail(401,'AUTH_REQUIRED')
        values=[v for k,v in request.scope['headers'] if k.lower()==b'x-flow-service-token']
        if len(expected)<32 or any(c<32 or c>126 for c in expected) or len(values)!=1 or not hmac.compare_digest(expected,values[0]):return fail(401,'AUTH_REQUIRED')
        started=asyncio.get_running_loop().time()
        try:
            async with asyncio.timeout_at(started+15):
                h=request.headers
                if request.url.query or len(h.getlist('content-type'))!=1 or h.get('content-type','').split(';')[0].strip().lower()!='application/json' or h.get('content-encoding') not in {None,'identity'}:raise ValueError()
                lengths=h.getlist('content-length')
                if len(lengths)>1 or lengths and (not lengths[0].isascii() or not lengths[0].isdigit() or int(lengths[0])>16384):raise ValueError()
                raw=bytearray()
                async for chunk in request.stream():
                    if len(raw)+len(chunk)>16384:raise ValueError()
                    raw.extend(chunk)
                from src.supervisor.domain.core_contracts import Envelope,InternalInput,decode,canonical
                decoded=decode(raw)
                data=decoded.get('data') if isinstance(decoded,dict) else None
                if isinstance(data,dict) and data.get('policy_version')=='supervisor.flow-core.2':
                    from src.supervisor.domain.core_contracts import MeaningRunInput
                    body=Envelope[MeaningRunInput].model_validate(decoded)
                else:
                    body=Envelope[InternalInput].model_validate(decoded)
                if body.error is not None or body.data is None:raise ValueError()
            # Body/auth retain their original bound. Policy1 also retains its
            # original total deadline; only policy2 gets the longer exchange.
            policy2=isinstance(data,dict) and data.get('policy_version')=='supervisor.flow-core.2'
            async with asyncio.timeout_at(started+(65 if policy2 else 15)):
                from src.supervisor.application.runtime import run_core
                selected=gateway
                if selected is None and policy2 and body.data.phase=='start' and runtime is not None:
                    from src.supervisor.application.meaning_policy import assess
                    from src.supervisor.infrastructure.meaning_gateway import CounterUnavailable
                    if assess(body.data.draft).needs_supplement:
                        installed=runtime() if callable(runtime) else runtime
                        values=[v for k,v in request.scope['headers'] if k.lower()==b'x-supervisor-meaning-grant']
                        try:
                            if installed is not None and len(values)==1:
                                selected=installed.gateway(body.data.draft,values[0].decode('ascii'),deadline=min(started+60,asyncio.get_running_loop().time()+60))
                        except (CounterUnavailable,ValueError,TypeError,UnicodeError):
                            selected=None
                result=await run_core(body.data,gateway=selected)
                value=dict(schema_version='supervisor.core.v1',request_id=body.request_id,trace_id=body.trace_id,data=result.model_dump(mode='json'),error=None)
                if len(canonical(value).encode('utf8'))>65536:return fail(502,'RESULT_CONTRACT_INVALID',(body.request_id,body.trace_id))
                return JSONResponse(value,headers=PRIVATE)
        except TimeoutError:return fail(504,'DEADLINE_EXCEEDED')
        except (ValueError,TypeError,UnicodeError,RecursionError):return fail(422,'INPUT_INVALID')
        except Exception:return fail(503,'SERVICE_UNAVAILABLE')
    return core



def make_technical_core_router():
    """No planning import, credential supply or provider work before service auth."""
    from uuid import uuid4
    router=APIRouter()
    def fail(status,code):
        return JSONResponse(dict(schema_version='supervisor.technical.v1',request_id=str(uuid4()),trace_id=str(uuid4()),data=None,error=dict(code=code,message='Supervisor request unavailable')),status_code=status,headers=PRIVATE)
    @router.post('/core/technical-plan')
    async def technical_plan(request:Request):
        installed=getattr(request.app.state,'technical_execution_runtime',None)
        if installed is None:return fail(403,'FEATURE_UNAVAILABLE')
        try:
            token=installed.service_token
            values=[v for k,v in request.scope['headers'] if k.lower()==b'x-technical-service-token']
            if type(token) is not bytes or len(token)<32 or len(values)!=1 or not hmac.compare_digest(token,values[0]):return fail(401,'AUTH_REQUIRED')
            path='/internal/supervisor/core/technical-plan'
            if request.scope.get('raw_path',path.encode())!=path.encode() or request.url.query:raise ValueError()
            h=request.headers
            if len(h.getlist('content-type'))!=1 or h.get('content-type','').lower()!='application/json' or h.getlist('content-encoding'):raise ValueError()
            if len(h.getlist('content-length'))>1:raise ValueError()
            length=h.get('content-length')
            if length is not None and (not length.isascii() or not length.isdigit() or len(length)>8 or int(length)>16384):raise ValueError()
            deadline=asyncio.get_running_loop().time()+15
            async with asyncio.timeout_at(deadline):
                raw=bytearray()
                async for chunk in request.stream():
                    if len(raw)+len(chunk)>16384:raise ValueError()
                    raw.extend(chunk)
                if length is not None and int(length)!=len(raw):raise ValueError()
                from src.supervisor.domain import technical_core_contracts as C
                from src.supervisor.application.planning.technical_core import run
                body=C.Envelope[C.InternalInput].model_validate(C.decode(raw))
                if body.data is None or body.error is not None:raise ValueError()
                ready=installed.readiness();configuration=ready['configuration']
                context=C.Context(configuration_sha256=C.sha(configuration),policy_sha256=C.sha(configuration['policy']),spec_sha256=ready['spec_sha256'],reserved_nano=configuration['policy']['attempt_reserve_nano'])
                if ready['ready'] is not True or body.data.context!=context:raise ValueError()
                result=run(body.data)
                value=dict(schema_version=C.VERSION,request_id=body.request_id,trace_id=body.trace_id,data=result.model_dump(mode='json'),error=None)
                if len(C.canonical(value).encode('utf8'))>65536:raise ValueError()
            if asyncio.get_running_loop().time()>=deadline:raise TimeoutError()
            return JSONResponse(value,headers=PRIVATE)
        except asyncio.CancelledError:raise
        except TimeoutError:return fail(504,'DEADLINE_EXCEEDED')
        except (ValueError,TypeError,UnicodeError,RecursionError):return fail(422,'INPUT_INVALID')
        except Exception:return fail(503,'SERVICE_UNAVAILABLE')
    return router

router=make_router(technical=True)
