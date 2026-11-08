"""Authenticated snapshot-aware Fundamental readers and individual deletion."""
from uuid import UUID
from fastapi import APIRouter,Depends,Request,Query,Response
from db.session import get_session
from src.modules.auth.api.router import request_principal
from src.modules.fundamental.api.analysis_router import FundamentalAnalysisRoute
from src.modules.fundamental.api.schemas import FundamentalReportEnvelope,FundamentalReportListResponse
from src.modules.fundamental.application.report_service import FundamentalReportService
from src.modules.fundamental.application.analysis_service import FundamentalAnalysisError
from src.modules.flow.domain.execution import ErrorCode

router=APIRouter(prefix='/api/fundamental/reports',tags=['fundamental-reports'],route_class=FundamentalAnalysisRoute)

async def get_fundamental_report_service(request:Request,session=Depends(get_session,scope='function')):
    principal=await request_principal(request,session,mutation=request.method=='DELETE')
    return FundamentalReportService(session,principal=principal)

@router.get('',response_model=FundamentalReportListResponse)
async def list_fundamental_reports(stock_code:str|None=Query(default=None,pattern=r'^[0-9]{6}$'),limit:int=Query(default=20,ge=1,le=100),offset:int=Query(default=0,ge=0),service=Depends(get_fundamental_report_service)):
    return await service.list_reports(stock_code=stock_code,limit=limit,offset=offset)

@router.get('/{report_id}',response_model=FundamentalReportEnvelope)
async def get_fundamental_report(report_id:UUID,service=Depends(get_fundamental_report_service)):
    result=await service.get_report(report_id)
    if result is None:raise FundamentalAnalysisError(ErrorCode.RESOURCE_NOT_FOUND)
    return result

@router.delete('/{report_id}',status_code=204)
async def delete_fundamental_report(report_id:UUID,service=Depends(get_fundamental_report_service)):
    if not await service.delete_report(report_id):raise FundamentalAnalysisError(ErrorCode.RESOURCE_NOT_FOUND)
    return Response(status_code=204)

# Retained public schema for existing clients; AccessBoundary and service both
# reject these legacy writes before any AI, DB write or transaction starts.
from src.modules.fundamental.api.schemas import FundamentalReportCreateRequest,FundamentalReportSaveRequest
@router.post('',response_model=FundamentalReportEnvelope,status_code=201)
async def create_fundamental_report(req:FundamentalReportCreateRequest,service:FundamentalReportService=Depends(get_fundamental_report_service))->FundamentalReportEnvelope:
    raise PermissionError('Public creation is disabled')
@router.post('/save',response_model=FundamentalReportEnvelope,status_code=201)
async def save_fundamental_report(req:FundamentalReportSaveRequest,service:FundamentalReportService=Depends(get_fundamental_report_service))->FundamentalReportEnvelope:
    """save-only — supervisor 가 이미 만든 fundamental output 을 AI 재호출 없이 저장(news 방식)."""
    raise PermissionError('Public save is disabled')
@router.delete('',status_code=200)
async def delete_all_fundamental_reports(service:FundamentalReportService=Depends(get_fundamental_report_service))->dict:
    """fundamental 리포트 전체 삭제. 삭제 건수 반환."""
    raise PermissionError('Public bulk deletion is disabled')
