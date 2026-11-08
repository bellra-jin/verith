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
from src.modules.analysis.domain.contracts import AnalysisContractError
from src.modules.fundamental.api.analysis_schemas import PATH,FundamentalAnalysisRequest,FundamentalAnalysisResponse
from src.modules.flow.api.run_schemas import PRIVATE,http_request_id,error_response
from src.modules.flow.domain.execution import ContractViolation,ErrorCode
from src.modules.fundamental.application.analysis_service import FundamentalAnalysisError,FundamentalAnalysisService


class FundamentalAnalysisRoute(APIRoute):
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
            except (FundamentalAnalysisError,ContractViolation) as error:return error_response(request.scope,error.code if isinstance(error,FundamentalAnalysisError) else error.error.code)
            except AnalysisContractError:return error_response(request.scope,ErrorCode.RESULT_CONTRACT_INVALID)
            except AuthenticationRequired:return error_response(request.scope,ErrorCode.AUTH_REQUIRED)
            except RequestValidationError:return error_response(request.scope,ErrorCode.INPUT_INVALID)
            except HTTPException as error:return error_response(request.scope,ErrorCode.AUTH_REQUIRED if error.status_code==401 else ErrorCode.AUTH_REQUEST_INVALID if error.status_code==403 else ErrorCode.INPUT_INVALID if error.status_code==400 else ErrorCode.SERVICE_UNAVAILABLE)
            except Exception:return error_response(request.scope,ErrorCode.SERVICE_UNAVAILABLE)
        return safe


router=APIRouter(prefix=PATH,tags=['fundamental-analyses'],route_class=FundamentalAnalysisRoute)


async def service(request:Request,session=Depends(get_session,scope='function')):
    principal=await request_principal(request,session,mutation=request.method=='POST')
    client=AIClient(settings.AI_SERVICE_URL,65,service_token=settings.FUNDAMENTAL_SERVICE_TOKEN)
    return FundamentalAnalysisService(session,principal=principal,client=client)


@router.post('',response_model=FundamentalAnalysisResponse,responses={202:{'model':FundamentalAnalysisResponse}})
async def post(request:Request,body:FundamentalAnalysisRequest,response:Response,value=Depends(service)):
    view=await value.post(body,http_request_id(request.scope))
    response.status_code=200 if view.state in {'stored','failed'} else 202
    response.headers['Location']=PATH+'/'+str(view.analysis_id)
    return FundamentalAnalysisResponse(request_id=http_request_id(request.scope),data=view)


@router.get('/{analysis_id}',response_model=FundamentalAnalysisResponse,responses={202:{'model':FundamentalAnalysisResponse}})
async def get(analysis_id:UUID,request:Request,response:Response,value=Depends(service)):
    view=await value.get(analysis_id);response.status_code=200 if view.state in {'stored','failed'} else 202
    return FundamentalAnalysisResponse(request_id=http_request_id(request.scope),data=view)
