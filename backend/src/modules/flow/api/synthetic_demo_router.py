"""Private, default-off synthetic demo endpoints. Function teardown stays inside errors."""
from contextlib import AsyncExitStack
from uuid import UUID
from fastapi import APIRouter, Depends, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from starlette.exceptions import HTTPException
from db.session import get_session
from src.modules.auth.api.router import request_principal
from src.modules.auth.application.session_service import AuthenticationRequired
from src.modules.flow.api.synthetic_demo_schemas import DemoRequest, DemoResponse, DEMO_PATH, request_id, error_response
from src.modules.flow.api.run_schemas import PRIVATE
from src.modules.flow.application.synthetic_demo_service import SyntheticDemoService, DemoError
from src.modules.flow.domain.execution import ErrorCode


class DemoRoute(APIRoute):
    def get_route_handler(self):
        handler=super().get_route_handler()
        async def safe(request):
            request_id(request.scope)
            try:
                previous=request.scope.get('fastapi_function_astack')
                try:
                    async with AsyncExitStack() as stack:
                        request.scope['fastapi_function_astack']=stack
                        response=await handler(request)
                finally:request.scope['fastapi_function_astack']=previous
                response.headers.update(PRIVATE)
                return response
            except RequestValidationError:return error_response(request.scope,ErrorCode.INPUT_INVALID)
            except AuthenticationRequired:return error_response(request.scope,ErrorCode.AUTH_REQUIRED)
            except DemoError as error:return error_response(request.scope,error.code,error.run_id)
            except HTTPException as error:return error_response(request.scope,ErrorCode.AUTH_REQUIRED if error.status_code==401 else ErrorCode.AUTH_REQUEST_INVALID if error.status_code==403 else ErrorCode.INPUT_INVALID if error.status_code==400 else ErrorCode.SERVICE_UNAVAILABLE)
            except Exception:return error_response(request.scope,ErrorCode.SERVICE_UNAVAILABLE)
        return safe


router=APIRouter(prefix=DEMO_PATH,tags=['flow-synthetic-demo'],route_class=DemoRoute)


async def demo_service(request:Request,session=Depends(get_session,scope='function')):
    principal=await request_principal(request,session,mutation=request.method=='POST')
    return SyntheticDemoService(session,principal=principal)


@router.post('',response_model=DemoResponse,responses={202:{'model':DemoResponse}})
async def post_demo(request:Request,body:DemoRequest,response:Response,service=Depends(demo_service)):
    view=await service.post(body,request_id(request.scope))
    response.status_code=200 if view.stage in {'succeeded','failed','timed_out'} else 202
    response.headers['Location']=DEMO_PATH+'/'+str(view.run_id)
    return DemoResponse(request_id=request_id(request.scope),data=view)


@router.get('/{run_id}',response_model=DemoResponse)
async def get_demo(run_id:UUID,request:Request,service=Depends(demo_service)):
    return DemoResponse(request_id=request_id(request.scope),data=await service.get(run_id))
