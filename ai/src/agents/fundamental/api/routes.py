"""Fundamental-only gated HTTP. No eager agent/workflow/provider import."""
import asyncio,hmac,os
from fastapi import APIRouter,Request
from fastapi.routing import APIRoute
from starlette.responses import JSONResponse,Response
from .analysis_schemas import FundamentalAnalysisInput,decode,canonical
from .execution import FundamentalRuntime,FundamentalUnavailable,FundamentalEngineFailure,FundamentalResultInvalid


def error(status,code):
    return JSONResponse(dict(error=dict(code=code,message='Financial analysis unavailable')),
                        status_code=status,headers={'Cache-Control':'no-store'})


def make_router(engine=None):
    runtime=FundamentalRuntime(engine)
    class StrictRoute(APIRoute):
        def get_route_handler(self):
            handler=super().get_route_handler()
            async def checked(request):
                if os.getenv('FUNDAMENTAL_ANALYSIS_ENABLED')!='true':return error(403,'FEATURE_UNAVAILABLE')
                try:expected=os.getenv('FUNDAMENTAL_SERVICE_TOKEN','').encode('utf8')
                except UnicodeError:return error(401,'AUTH_REQUIRED')
                values=[v for k,v in request.scope.get('headers',[]) if k.lower()==b'x-fundamental-service-token']
                if len(expected)<32 or len(values)!=1 or not hmac.compare_digest(expected,values[0]):return error(401,'AUTH_REQUIRED')
                try:
                    async with asyncio.timeout(60):
                        if request.headers.getlist('content-encoding') or len(request.headers.getlist('content-type'))!=1 or len(request.headers.getlist('content-length'))>1:raise ValueError()
                        if request.headers['content-type'].split(';')[0].strip().lower()!='application/json':raise ValueError()
                        length=request.headers.get('content-length')
                        if length is not None and (not length.isascii() or not length.isdigit() or int(length)>8192):raise ValueError()
                        raw=bytearray()
                        async for part in request.stream():
                            raw.extend(part)
                            if len(raw)>8192:raise ValueError()
                        request.state.financial_input=FundamentalAnalysisInput.model_validate(decode(bytes(raw)))
                        return await handler(request)
                except TimeoutError:return error(504,'DEADLINE_EXCEEDED')
                except (FundamentalUnavailable,FundamentalEngineFailure):return error(503,'SERVICE_UNAVAILABLE')
                except FundamentalResultInvalid:return error(502,'RESULT_CONTRACT_INVALID')
                except (ValueError,RecursionError,UnicodeError):return error(422,'INPUT_INVALID')
                except Exception:return error(502,'RESULT_CONTRACT_INVALID')
            return checked
    router=APIRouter()
    protected=APIRouter(route_class=StrictRoute)
    @router.get('/internal/fundamental/health')
    async def health():return {'status':'ok','service':'fundamental-agent','version':'0.1.0'}
    @protected.post('/internal/fundamental/analyze')
    async def analyze(request:Request):
        result=await runtime.run(request.state.financial_input)
        return Response(canonical(result),media_type='application/json',headers={'Cache-Control':'no-store'})
    router.include_router(protected)
    return router


router=make_router()
