"""One exact authenticated preparation POST, separate from execution ledger."""
import asyncio
from contextlib import AsyncExitStack
from fastapi import APIRouter,Depends,Request
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from db.session import get_session
from src.shared.config import settings
from src.modules.auth.api.router import request_principal
from src.modules.auth.application.session_service import AuthenticationRequired
from src.shared.infrastructure.clients.ai_client import AIClient
from src.modules.flow.api.run_schemas import PRIVATE,http_request_id
from src.modules.flow.api.query_plan_schemas import PATH,QueryPlanRequest,QueryPlanResponse,QueryPlanSafeError
from src.modules.flow.domain.query_plan import QueryPlanError
from src.modules.flow.application.query_plan_service import QueryPlanService

def failure(scope,code,status):
    return JSONResponse(QueryPlanResponse(request_id=http_request_id(scope),error=QueryPlanSafeError(code=code)).model_dump(mode='json'),status_code=status,headers=PRIVATE)

class PlanRoute(APIRoute):
    def get_route_handler(self):
        handler=super().get_route_handler()
        async def checked(request):
            try:
                previous=request.scope.get('fastapi_function_astack')
                try:
                    async with asyncio.timeout_at(request.scope.get('state',{}).get('cf020_deadline',asyncio.get_running_loop().time()+10)):
                        async with AsyncExitStack() as stack:
                            request.scope['fastapi_function_astack']=stack
                            response=await handler(request)
                finally:request.scope['fastapi_function_astack']=previous
                response.headers.update(PRIVATE);return response
            except TimeoutError:return failure(request.scope,'DEADLINE_EXCEEDED',504)
            except QueryPlanError as error:return failure(request.scope,error.code,error.status)
            except AuthenticationRequired:return failure(request.scope,'AUTH_REQUIRED',401)
            except RequestValidationError:return failure(request.scope,'INPUT_INVALID',422)
            except HTTPException as error:return failure(request.scope,'AUTH_REQUIRED' if error.status_code==401 else 'AUTH_REQUEST_INVALID',401 if error.status_code==401 else 403)
            except Exception:return failure(request.scope,'SERVICE_UNAVAILABLE',503)
        return checked

router=APIRouter(prefix=PATH,tags=['flow-plans'],route_class=PlanRoute)
async def service(request:Request,session=Depends(get_session,scope='function')):
    principal=await request_principal(request,session,mutation=True)
    return QueryPlanService(session,principal=principal,client=AIClient(settings.AI_SERVICE_URL,3,service_token=settings.FLOW_SERVICE_TOKEN),deadline_at=request.scope.get('state',{}).get('cf020_deadline'))

@router.post('',response_model=QueryPlanResponse)
async def post(request:Request,body:QueryPlanRequest,value=Depends(service)):
    return QueryPlanResponse(request_id=http_request_id(request.scope),data=await value.prepare(body,http_request_id(request.scope)))
