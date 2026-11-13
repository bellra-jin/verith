"""Fixed Flow policy; SQL, snapshots and report semantics remain Flow-owned."""
from datetime import UTC,datetime
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from db.models.flow.flow_report import FlowReport
from src.modules.flow.domain.analysis import OPERATION,SPEC,canonical,candidate
from src.modules.flow.api.analysis_schemas import AnalysisRequest,AnalysisView
from src.modules.flow.domain.execution import ContractViolation,ErrorCode,SafeError
from src.modules.auth.application.session_service import AuthenticationRequired
from src.modules.flow.application.analysis_adapter import FlowAnalysisAdapter
from src.modules.flow.application.report_service import FlowReportIdConflict
from src.modules.flow.infrastructure import analysis_repository as repository,report_repository


class FlowProfile:
    operation=OPERATION
    deadline_seconds=120
    repository=repository
    contract_errors=(ContractViolation,)
    publish_errors=(FlowReportIdConflict,IntegrityError)
    snapshot_conflicts=() # Preserve original Flow accept-error semantics.
    def confirmed_snapshot_conflict(self,error):return False

    def __init__(self,error_type):
        self.error_type=error_type
        self.preserved_errors=(error_type,AuthenticationRequired)
        self.admission_errors=(*self.preserved_errors,ContractViolation)

    def error(self,code,analysis_id=None):return self.error_type(ErrorCode(code),analysis_id)

    def parse(self,body):
        body=AnalysisRequest.model_validate(body.model_dump() if isinstance(body,AnalysisRequest) else body)
        if body.as_of>datetime.now(UTC):raise self.error('INPUT_INVALID')
        return body

    def normalized(self,body):return canonical(body.normalized_input())
    def input_clock(self,body,stamp):return dict(as_of=body.as_of,candidate_date=candidate(body.as_of))
    async def admit_before(self,session,values,before):
        return await self.repository.admit(session,values,before=before)

    def spec_json(self):return canonical(SPEC)
    def adapter(self,row,owner):return FlowAnalysisAdapter(row,owner_user_id=owner)
    def from_stored(self,adapter,row):return adapter.from_stored(row)
    async def dispatch(self,client,request):return await client.analyze_flow(request)

    def view(self,row):
        if row.state=='deleted':raise self.error('RESOURCE_NOT_FOUND')
        stored=row.state=='stored'
        return AnalysisView(analysis_id=row.id,admission_request_id=row.admission_request_id,
            attempt_id=row.attempt_id,state=row.state,deadline_at=row.deadline_at,
            report_id=row.adopted_report_id if stored else None,
            report_url=f'/reports/flow/{row.adopted_report_id}' if stored else None,
            error=SafeError(code=ErrorCode(row.error_code)) if row.error_code else None)

    def confirmed_conflict(self,error):
        cause=getattr(getattr(error,'orig',None),'__cause__',None)
        return isinstance(error,FlowReportIdConflict) or (getattr(cause,'sqlstate',None)=='23505'
            and getattr(cause,'constraint_name',None)=='pk_flow_reports')

    async def report_exists(self,session,report_id):
        existing=await session.scalar(select(FlowReport.id).where(FlowReport.id==report_id))
        indexes=await report_repository.get_agent_indexes(session,report_id)
        return existing is not None or bool(indexes)
