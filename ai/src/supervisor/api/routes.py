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

def make_router():
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
    return router

router=make_router()
