"""Production financial adapter: preserve raw JSON, caller-owned stage only."""
from dataclasses import dataclass
from types import SimpleNamespace
from src.modules.analysis.domain.contracts import AnalysisContext,AnalysisContractError,FrozenAnalysisResult,StagedReportReference,strict_json
from src.modules.auth.application.session_service import Principal,AuthenticationRequired
from src.modules.fundamental.domain import analysis as domain


@dataclass(frozen=True,slots=True)
class _Binding:
    id:object
    admission_request_id:object
    attempt_id:object
    ticker:str
    stock_name:str
    request_json:str
    input_fingerprint:str
    as_of:object
    deadline_at:object
    spec_json:str


@dataclass(frozen=True,slots=True,init=False)
class FundamentalAnalysisAdapter:
    context:AnalysisContext
    _binding:_Binding

    def __init__(self,row,*,owner_user_id):
        if row.owner_user_id!=owner_user_id or row.operation!=domain.OPERATION:raise AnalysisContractError()
        context=AnalysisContext(row.id,row.admission_request_id,row.attempt_id,owner_user_id,row.operation,row.input_fingerprint,row.as_of,row.deadline_at)
        object.__setattr__(self,'context',context)
        object.__setattr__(self,'_binding',_Binding(**{name:getattr(row,name) for name in _Binding.__dataclass_fields__}))

    def build_request(self):return domain.ai_request(self._binding)

    def validate_and_freeze(self,response):
        rid,a,b=domain.validate_response(self._binding,response)
        return FrozenAnalysisResult.freeze(context=self.context,report_id=rid,input_schema='fundamental.request-context.v1',
            result_schema='fundamental.agent-output.v1',input_json=a,result_json=b)

    def from_stored(self,row):return self.validate_and_freeze(domain.stored_response(row))

    def checked(self,frozen):
        frozen.validate()
        if (frozen.context!=self.context or frozen.input_schema!='fundamental.request-context.v1'
                or frozen.result_schema!='fundamental.agent-output.v1'):raise AnalysisContractError()
        response=dict(schema_version=1,analysis_id=str(self.context.analysis_id),admission_request_id=str(self.context.admission_request_id),
            attempt_id=str(self.context.attempt_id),fingerprint=self.context.input_fingerprint,report_id=str(frozen.report_id),
            input_snapshot=strict_json(frozen.input_json),input_sha256=frozen.input_sha256,output=strict_json(frozen.result_json))
        if self.validate_and_freeze(response)!=frozen:raise AnalysisContractError()
        return response['output']

    async def stage(self,session,principal,frozen):
        if not isinstance(principal,Principal) or principal.user_id!=self.context.owner_user_id:raise AuthenticationRequired()
        raw=self.checked(frozen)
        from src.modules.fundamental.application.report_service import FundamentalReportService
        await FundamentalReportService(session=session,principal=principal).stage_report(raw,
            report_id=frozen.report_id,question=domain.input_request(self._binding)['question'],stock_name=self._binding.stock_name)
        return StagedReportReference(frozen.report_id,principal.user_id)
