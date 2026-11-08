"""Exactly two development receipt endpoints, gated before dependencies run."""

from contextlib import AsyncExitStack
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.exceptions import HTTPException

from db.session import get_session
from src.modules.auth.api.router import request_principal
from src.modules.auth.application.session_service import AuthenticationRequired
from src.modules.flow.api.run_schemas import PRIVATE, FlowAdmissionRequest, RunResponse, error_response, http_request_id
from src.modules.flow.application.run_service import FlowRunService
from src.modules.flow.domain.execution import ContractViolation, ErrorCode


class AdmissionRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def safe_handler(request: Request):
            http_request_id(request.scope)
            try:
                # Function-scoped session teardown must finish inside the safe
                # boundary, before any successful response can be sent.
                previous = request.scope.get("fastapi_function_astack")
                try:
                    async with AsyncExitStack() as stack:
                        request.scope["fastapi_function_astack"] = stack
                        response = await handler(request)
                finally:
                    request.scope["fastapi_function_astack"] = previous
                response.headers.update(PRIVATE)
                return response
            except RequestValidationError:
                return error_response(request.scope, ErrorCode.INPUT_INVALID)
            except AuthenticationRequired:
                return error_response(request.scope, ErrorCode.AUTH_REQUIRED)
            except ContractViolation as exc:
                return error_response(request.scope, exc.error.code)
            except HTTPException as exc:
                if exc.status_code == 400 and exc.detail == "There was an error parsing the body":
                    code = ErrorCode.INPUT_INVALID
                elif exc.status_code == 403:
                    code = ErrorCode.AUTH_REQUEST_INVALID
                elif exc.status_code == 401:
                    code = ErrorCode.AUTH_REQUIRED
                else:
                    code = ErrorCode.SERVICE_UNAVAILABLE
                return error_response(request.scope, code)
            except (SQLAlchemyError, OSError, TimeoutError):
                return error_response(request.scope, ErrorCode.SERVICE_UNAVAILABLE)

        return safe_handler


router = APIRouter(prefix="/api/flow/runs", tags=["flow-runs"], route_class=AdmissionRoute)


async def get_run_service(request: Request, session: AsyncSession = Depends(get_session, scope="function")):
    principal = await request_principal(request, session, mutation=request.method == "POST")
    return FlowRunService(session, principal=principal)


@router.post("", response_model=RunResponse, status_code=202)
async def admit_run(request: Request, body: FlowAdmissionRequest, response: Response,
                    service: FlowRunService = Depends(get_run_service)) -> RunResponse:
    request_id = http_request_id(request.scope)
    state = await service.admit(body, request_id)
    response.headers["Location"] = f"/api/flow/runs/{state.run_id}"
    return RunResponse(request_id=request_id, data=state)


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(run_id: UUID, request: Request,
                  service: FlowRunService = Depends(get_run_service)) -> RunResponse:
    return RunResponse(request_id=http_request_id(request.scope), data=await service.get(run_id))
