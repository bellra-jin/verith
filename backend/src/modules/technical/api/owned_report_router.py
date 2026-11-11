"""Authenticated owned reads only; no AI dependency or legacy writer."""
import asyncio
from contextlib import AsyncExitStack
from fastapi import APIRouter, Depends, Request
from fastapi.routing import APIRoute
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from pydantic import ValidationError
from src.modules.auth.application.session_service import AuthenticationRequired
from src.modules.technical.application.owned_report_service import TechnicalOwnedReportService, TechnicalStoredPayloadError
from src.modules.technical.api import owned_report_schemas as wire


async def session_dependency():
    # App composition remains lazy for pure storage and schema imports.
    from db.session import get_session
    async for session in get_session(): yield session


class OwnedReadRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()
        async def safe(request):
            try:
                async with asyncio.timeout(15):
                    previous = request.scope.get('fastapi_function_astack')
                    try:
                        async with AsyncExitStack() as stack:
                            request.scope['fastapi_function_astack'] = stack
                            return await handler(request)
                    finally: request.scope['fastapi_function_astack'] = previous
            except AuthenticationRequired: return wire.error(request.scope,'AUTH_REQUIRED')
            except TechnicalStoredPayloadError: return wire.error(request.scope,'RESULT_CONTRACT_INVALID')
            except ValidationError: return wire.error(request.scope,'RESULT_CONTRACT_INVALID')
            except wire.ReadInvalid as failure: return wire.error(request.scope,failure.code)
            except RequestValidationError: return wire.error(request.scope,'INPUT_INVALID')
            except HTTPException as failure:
                return wire.error(request.scope,'AUTH_REQUIRED' if failure.status_code==401 else
                    'AUTH_REQUEST_INVALID' if failure.status_code==403 else 'SERVICE_UNAVAILABLE')
            except TimeoutError: return wire.error(request.scope,'DEADLINE_EXCEEDED')
            except Exception: return wire.error(request.scope,'SERVICE_UNAVAILABLE')
        return safe


router = APIRouter(prefix=wire.PATH,tags=['technical-owned-read'],route_class=OwnedReadRoute)


async def read(request,session):
    from src.modules.auth.api.router import request_principal
    principal = await request_principal(request,session,mutation=False)
    report_id,query = wire.target(request.method,request.url.path,request.scope.get('query_string',b''))
    service = TechnicalOwnedReportService(session,principal=principal)
    data = await service.list_owned(**query) if report_id is None else await service.read_projection(report_id)
    if data is None: return wire.error(request.scope,'RESOURCE_NOT_FOUND')
    return wire.response(request.scope,data,detail=report_id is not None)


@router.get('')
async def listing(request:Request,session=Depends(session_dependency,scope='function')):
    return await read(request,session)


@router.get('/{report_id}')
async def detail(request:Request,session=Depends(session_dependency,scope='function')):
    return await read(request,session)
