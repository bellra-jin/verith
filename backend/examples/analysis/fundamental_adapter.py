"""Unregistered synthetic example. Never calls the legacy financial service/DB."""
from dataclasses import dataclass
import re
from uuid import UUID
from typing import Callable,Awaitable,Any
from src.modules.analysis.domain.contracts import AnalysisContext,AnalysisContractError,FrozenAnalysisResult,StagedReportReference,canonical_json,json_hash,strict_json
from src.modules.auth.application.session_service import Principal,AuthenticationRequired,validate_principal
from src.modules.fundamental.domain.ai_output import FundamentalAgentOutputMirror

EXAMPLE_OPERATION='fundamental.analysis.example.v1'
ProjectionWriter=Callable[[Any,Principal,FrozenAnalysisResult],Awaitable[StagedReportReference]]


class ExampleWriterUnavailable(RuntimeError):
    def __init__(self):super().__init__('Owner-aware financial projection writer is not implemented')


@dataclass(frozen=True,slots=True)
class FundamentalExampleAdapter:
    context:AnalysisContext
    ticker:str
    question:str
    writer:ProjectionWriter|None=None

    def __post_init__(self):
        self.context.validate()
        if (self.context.operation!=EXAMPLE_OPERATION or not isinstance(self.ticker,str)
                or not re.fullmatch('[0-9]{6}',self.ticker) or not isinstance(self.question,str)
                or not self.question.strip() or len(self.question)>2000 or '\x00' in self.question):raise AnalysisContractError()
        normalized=dict(ticker=self.ticker,question=self.question,as_of=self.context.as_of.isoformat())
        if json_hash(canonical_json(normalized))!=self.context.input_fingerprint:raise AnalysisContractError()

    def build_request(self):
        return dict(request_id='req-'+self.context.admission_request_id.hex,
            trace_id='trace-'+self.context.attempt_id.hex,ticker=self.ticker,query=self.question)

    def validate_and_freeze(self,response):
        try:
            original=strict_json(response) if isinstance(response,str) else strict_json(canonical_json(response))
            mirror=FundamentalAgentOutputMirror.model_validate(original)
            request=self.build_request()
            if (mirror.request_id!=request['request_id'] or mirror.ticker!=request['ticker']
                    or mirror.meta.trace_id!=request['trace_id']):raise AnalysisContractError()
            report_id=UUID(mirror.meta.erd_payload.fundamental_report['id'])
            return FrozenAnalysisResult.freeze(context=self.context,report_id=report_id,
                input_schema='fundamental.synthetic-request.v1',result_schema='fundamental.agent-output.v1',
                input_json=canonical_json(request),result_json=canonical_json(original))
        except (ValueError,TypeError,KeyError,AttributeError):raise AnalysisContractError() from None

    async def stage(self,session,principal,frozen):
        if not isinstance(principal,Principal) or principal.user_id!=self.context.owner_user_id:raise AuthenticationRequired()
        frozen.validate()
        if (frozen.context!=self.context or self.validate_and_freeze(strict_json(frozen.result_json))!=frozen):raise AnalysisContractError()
        if self.writer is None:raise ExampleWriterUnavailable()
        await validate_principal(session,principal,lock=True)
        reference=await self.writer(session,principal,frozen)
        if (not isinstance(reference,StagedReportReference) or reference.report_id!=frozen.report_id
                or reference.owner_user_id!=self.context.owner_user_id):raise AnalysisContractError()
        await session.flush()
        return reference
