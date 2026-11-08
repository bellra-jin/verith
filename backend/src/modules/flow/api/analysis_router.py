"""New exact authenticated analyses routes; legacy raw save remains closed."""
from contextlib import AsyncExitStack
from uuid import UUID
from fastapi import APIRouter,Depends,Request,Response
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from starlette.exceptions import HTTPException
from db.session import get_session
from src.shared.config import settings
from src.shared.infrastructure.clients.ai_client import AIClient
from src.modules.auth.api.router import request_principal
from src.modules.auth.application.session_service import AuthenticationRequired
from src.modules.flow.api.analysis_schemas import PATH,AnalysisRequest,AnalysisResponse
from src.modules.flow.api.run_schemas import PRIVATE,http_request_id,error_response
from src.modules.flow.domain.execution import ContractViolation,ErrorCode
from src.modules.flow.application.analysis_service import AnalysisError,AnalysisService


class AnalysisRoute(APIRoute):
    def get_route_handler(self):
        handler=super().get_route_handler()
        async def safe(request):
            try:
                previous=request.scope.get('fastapi_function_astack')
                try:
                    async with AsyncExitStack() as stack:
                        request.scope['fastapi_function_astack']=stack
                        response=await handler(request)
                finally:request.scope['fastapi_function_astack']=previous
                response.headers.update(PRIVATE);return response
            except (AnalysisError,ContractViolation) as error:return error_response(request.scope,error.code if isinstance(error,AnalysisError) else error.error.code)
            except AuthenticationRequired:return error_response(request.scope,ErrorCode.AUTH_REQUIRED)
            except RequestValidationError:return error_response(request.scope,ErrorCode.INPUT_INVALID)
            except HTTPException as error:return error_response(request.scope,ErrorCode.AUTH_REQUIRED if error.status_code==401 else ErrorCode.AUTH_REQUEST_INVALID if error.status_code==403 else ErrorCode.INPUT_INVALID if error.status_code==400 else ErrorCode.SERVICE_UNAVAILABLE)
            except Exception:return error_response(request.scope,ErrorCode.SERVICE_UNAVAILABLE)
        return safe


router=APIRouter(prefix=PATH,tags=['flow-analyses'],route_class=AnalysisRoute)


async def service(request:Request,session=Depends(get_session,scope='function')):
    principal=await request_principal(request,session,mutation=request.method=='POST')
    client=AIClient(settings.AI_SERVICE_URL,125,service_token=settings.FLOW_SERVICE_TOKEN)
    return AnalysisService(session,principal=principal,client=client)


@router.post('',response_model=AnalysisResponse,responses={202:{'model':AnalysisResponse}})
async def post(request:Request,body:AnalysisRequest,response:Response,value=Depends(service)):
    view=await value.post(body,http_request_id(request.scope))
    response.status_code=200 if view.state in {'stored','failed'} else 202
    response.headers['Location']=PATH+'/'+str(view.analysis_id)
    return AnalysisResponse(request_id=http_request_id(request.scope),data=view)


@router.get('/{analysis_id}',response_model=AnalysisResponse,responses={202:{'model':AnalysisResponse}})
async def get(analysis_id:UUID,request:Request,response:Response,value=Depends(service)):
    view=await value.get(analysis_id);response.status_code=200 if view.state in {'stored','failed'} else 202
    return AnalysisResponse(request_id=http_request_id(request.scope),data=view)
