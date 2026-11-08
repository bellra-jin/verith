"""Flow implementation of the common port; no claim, state or commit ownership."""
from dataclasses import dataclass
from datetime import date
from uuid import UUID
from src.modules.analysis.domain.contracts import AnalysisContext,AnalysisContractError,FrozenAnalysisResult,StagedReportReference,strict_json
from src.modules.auth.application.session_service import Principal,AuthenticationRequired
from src.modules.flow.domain import analysis as domain
from src.modules.flow.domain.execution import ContractViolation,ErrorCode
from src.modules.flow.api.schemas import FlowReportSaveRequest
from src.modules.flow.application.report_service import FlowReportService


@dataclass(frozen=True,slots=True)
class _FlowBinding:
    context:AnalysisContext
    ticker:str
    stock_name:str
    candidate_date:date
    request_json:str
    spec_json:str

    @property
    def id(self):return self.context.analysis_id
    @property
    def attempt_id(self):return self.context.attempt_id
    @property
    def admission_request_id(self):return self.context.admission_request_id
    @property
    def input_fingerprint(self):return self.context.input_fingerprint
    @property
    def deadline_at(self):return self.context.deadline_at


@dataclass(frozen=True,slots=True,init=False)
class FlowAnalysisAdapter:
    context:AnalysisContext
    _binding:_FlowBinding
    def __init__(self,row,*,owner_user_id):
        try:
            if row.owner_user_id!=owner_user_id or row.operation!=domain.OPERATION:raise AnalysisContractError()
            context=AnalysisContext(row.id,row.admission_request_id,row.attempt_id,row.owner_user_id,
                row.operation,row.input_fingerprint,row.as_of,row.deadline_at)
            object.__setattr__(self,"context",context)
            object.__setattr__(self,"_binding",_FlowBinding(context,row.ticker,row.stock_name,row.candidate_date,row.request_json,row.spec_json))
        except (AnalysisContractError,AttributeError):raise ContractViolation(ErrorCode.RESULT_CONTRACT_INVALID) from None

    def build_request(self):return domain.ai_request(self._binding)

    def validate_and_freeze(self,response):
        ref,a,b=domain.validate_response(self._binding,response,self.context.owner_user_id)
        try:return FrozenAnalysisResult.freeze(context=self.context,report_id=ref.report_id,
            input_schema='flow.input.v1',result_schema='flow.payload.v1',input_json=a,result_json=b)
        except AnalysisContractError:raise ContractViolation(ErrorCode.RESULT_CONTRACT_INVALID) from None

    def from_stored(self,row):
        # The ledger's original SHA checks are preserved before generic freezing.
        return self.validate_and_freeze(domain.stored_response(row))

    def _checked(self,frozen):
        try:
            frozen.validate()
            if (frozen.context!=self.context or frozen.input_schema!='flow.input.v1'
                    or frozen.result_schema!='flow.payload.v1'):raise AnalysisContractError()
            response={'schema_version':1,'analysis_id':str(self.context.analysis_id),'attempt_id':str(self.context.attempt_id),
                'admission_request_id':str(self.context.admission_request_id),'fingerprint':self.context.input_fingerprint,
                'report_id':str(frozen.report_id),'input_snapshot':strict_json(frozen.input_json),
                'input_sha256':frozen.input_sha256,'payload':strict_json(frozen.result_json)}
            checked=self.validate_and_freeze(response)
            if checked!=frozen:raise AnalysisContractError()
            return response
        except (AnalysisContractError,AttributeError):raise ContractViolation(ErrorCode.RESULT_CONTRACT_INVALID) from None

    async def stage(self,session,principal,frozen):
        if not isinstance(principal,Principal) or principal.user_id!=self.context.owner_user_id:raise AuthenticationRequired()
        response=self._checked(frozen)
        # Existing writer validates the real principal/session, writes and flushes;
        # this adapter neither opens a session nor commits/rolls back.
        value=await FlowReportService(session,principal=principal).stage_report(
            FlowReportSaveRequest(payload=response['payload'],question=self.build_request()['question']))
        if value.report_id!=frozen.report_id:raise ContractViolation(ErrorCode.RESULT_CONTRACT_INVALID)
        return StagedReportReference(value.report_id,principal.user_id)
