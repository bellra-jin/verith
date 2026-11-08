"""Fixed financial policy; current request time, existing engine, owned writer."""
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from db.models.fundamental.fundamental_report import FundamentalReport
from db.models.common.agent_report import AgentReport
from src.modules.analysis.domain.contracts import AnalysisContractError
from src.modules.auth.application.session_service import AuthenticationRequired
from src.modules.fundamental.domain import analysis as domain
from src.modules.fundamental.api.analysis_schemas import FundamentalAnalysisRequest,FundamentalAnalysisView
from src.modules.fundamental.application.analysis_adapter import FundamentalAnalysisAdapter
from src.modules.fundamental.infrastructure import analysis_repository as repository
from src.modules.flow.domain.execution import ErrorCode,SafeError


class FundamentalProfile:
    operation=domain.OPERATION
    deadline_seconds=60
    repository=repository
    contract_errors=(AnalysisContractError,)
    snapshot_conflicts=(IntegrityError,)
    def confirmed_snapshot_conflict(self,error):
        cause=getattr(getattr(error,'orig',None),'__cause__',None)
        return getattr(cause,'sqlstate',None)=='23505' and getattr(cause,'constraint_name',None)=='uq_fundamental_analysis_report'

    # The writer's explicit conflict is set in __init__ to avoid import cycles.
    def __init__(self,error_type):
        from src.modules.fundamental.application.report_service import FundamentalReportIdConflict
        self.error_type=error_type
        self.preserved_errors=(error_type,AuthenticationRequired)
        self.admission_errors=(*self.preserved_errors,AnalysisContractError)
        self.publish_errors=(FundamentalReportIdConflict,IntegrityError)
        self.conflict_type=FundamentalReportIdConflict
    def error(self,code,analysis_id=None):return self.error_type(ErrorCode(code),analysis_id)
    def parse(self,body):return FundamentalAnalysisRequest.model_validate(body.model_dump() if isinstance(body,FundamentalAnalysisRequest) else body)
    def normalized(self,body):return domain.canonical(body.normalized_input())
    def input_clock(self,body,stamp):return dict(as_of=stamp)
    def spec_json(self):return domain.canonical(domain.SPEC)
    def adapter(self,row,owner):return FundamentalAnalysisAdapter(row,owner_user_id=owner)
    def from_stored(self,adapter,row):return adapter.from_stored(row)
    async def dispatch(self,client,request):return await client.analyze_fundamental(request)
    def view(self,row):
        if row.state=='deleted':raise self.error('RESOURCE_NOT_FOUND')
        stored=row.state=='stored'
        return FundamentalAnalysisView(analysis_id=row.id,admission_request_id=row.admission_request_id,
            attempt_id=row.attempt_id,state=row.state,deadline_at=row.deadline_at,
            report_id=row.adopted_report_id if stored else None,
            report_url=f'/reports/fundamental/{row.adopted_report_id}' if stored else None,
            error=SafeError(code=ErrorCode(row.error_code)) if row.error_code else None)
    def confirmed_conflict(self,error):
        cause=getattr(getattr(error,'orig',None),'__cause__',None)
        return isinstance(error,self.conflict_type) or (getattr(cause,'sqlstate',None)=='23505'
            and getattr(cause,'constraint_name',None) in {'pk_fundamental_reports','uq_fundamental_owned_agent_report'})
    async def report_exists(self,session,report_id):
        root=await session.scalar(select(FundamentalReport.id).where(FundamentalReport.id==report_id))
        index=await session.scalar(select(AgentReport.id).where(AgentReport.agent_type=='fundamental',AgentReport.agent_report_id==report_id).limit(1))
        return root is not None or index is not None
