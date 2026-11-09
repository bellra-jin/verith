"""Flow-only internal HTTP. Gate/auth/body precede every engine/graph import."""
import asyncio
import hmac
import os
from fastapi import APIRouter,Request
from fastapi.routing import APIRoute
from starlette.responses import JSONResponse,Response
from .schemas import FlowAnalysisInput,canonical,decode
from ..application.execution_runtime import FlowExecutionRuntime,EngineUnavailable,ResultContractError
from src.shared.runtime.deadline import DeadlineExceeded


def error(status,code):
    return JSONResponse({'error':{'code':code,'message':'Flow analysis unavailable'}},status_code=status,
                        headers={'Cache-Control':'no-store'})


def make_router(engine=None):
    runtime=FlowExecutionRuntime(engine)
    class StrictRoute(APIRoute):
        def get_route_handler(self):
            handler=super().get_route_handler()
            async def checked(request):
                if os.getenv('FLOW_ANALYSIS_ENABLED')!='true':return error(403,'FEATURE_UNAVAILABLE')
                try:expected=os.getenv('FLOW_SERVICE_TOKEN','').encode('utf8')
                except UnicodeError:return error(401,'AUTH_REQUIRED')
                values=[value for key,value in request.scope.get('headers',[]) if key.lower()==b'x-flow-service-token']
                supplied=values[0] if len(values)==1 else b''
                if len(expected)<32 or not hmac.compare_digest(expected,supplied):return error(401,'AUTH_REQUIRED')
                try:
                    if request.headers.get('content-encoding') is not None or request.headers.get('content-type','').split(';')[0].strip().lower()!='application/json':raise ValueError()
                    raw=bytearray()
                    async for part in request.stream():
                        raw.extend(part)
                        if len(raw)>8192:raise ValueError()
                    request.state.flow_input=FlowAnalysisInput.model_validate(decode(bytes(raw)))
                except (ValueError,RecursionError):return error(422,'INPUT_INVALID')
                try:
                    return await handler(request)
                except (TimeoutError,DeadlineExceeded):return error(504,'DEADLINE_EXCEEDED')
                except ResultContractError:return error(502,'RESULT_CONTRACT_INVALID')
                except Exception:return error(503,'SERVICE_UNAVAILABLE')
            return checked
    router=APIRouter(route_class=StrictRoute)
    @router.post('/internal/flow/analyze')
    async def analyze(request:Request):
        value=await runtime.run(request.state.flow_input)
        return Response(canonical(value),media_type='application/json',headers={'Cache-Control':'no-store'})
    return router


router=make_router()
