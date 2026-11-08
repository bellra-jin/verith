"""Authenticated live analysis HTTP contracts, separate from receipt/demo."""
from datetime import UTC,datetime,timedelta
from typing import Literal
from uuid import UUID
from pydantic import BaseModel,ConfigDict,model_validator
from src.modules.flow.api.run_schemas import FlowAdmissionRequest
from src.modules.flow.domain.execution import CommonResponse,SafeError

PATH='/api/flow/analyses'


class AnalysisRequest(FlowAdmissionRequest):
    allow_analysis:Literal[True]

    @model_validator(mode='before')
    @classmethod
    def opt_in(cls,value):
        if not isinstance(value,dict) or set(value)!={'ticker','question','as_of','idempotency_key','allow_analysis'} or value.get('allow_analysis') is not True:
            raise ValueError('Explicit analysis opt in required')
        raw=value.get('as_of')
        parsed=datetime.fromisoformat(raw) if isinstance(raw,str) else raw
        if not isinstance(parsed,datetime) or parsed.utcoffset()!=timedelta(0):raise ValueError('UTC as_of required')
        return value

    def normalized_input(self):
        return FlowAdmissionRequest(ticker=self.ticker,question=self.question,as_of=self.as_of,idempotency_key=self.idempotency_key).normalized_input()


class AnalysisView(BaseModel):
    model_config=ConfigDict(extra='forbid',hide_input_in_errors=True)
    analysis_id:UUID
    admission_request_id:UUID
    attempt_id:UUID
    state:Literal['running','result_ready','stored','failed','unknown']
    deadline_at:datetime
    report_id:UUID|None=None
    report_url:str|None=None
    error:SafeError|None=None

AnalysisResponse=CommonResponse[AnalysisView]
