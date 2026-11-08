"""Distinct financial DTOs. Server fixes request time once; no historical as_of."""
from datetime import datetime
from typing import Literal,Annotated
from uuid import UUID
from pydantic import BaseModel,ConfigDict,Field,model_validator
from src.modules.flow.domain.execution import CommonResponse,SafeError

PATH='/api/fundamental/analyses'


class FundamentalAnalysisRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',hide_input_in_errors=True)
    ticker:Annotated[str,Field(strict=True,pattern='^[0-9]{6}$')]
    question:Annotated[str,Field(strict=True,min_length=1,max_length=2000)]
    idempotency_key:Annotated[str,Field(strict=True,min_length=1,max_length=256)]
    allow_analysis:Literal[True]

    @model_validator(mode='before')
    @classmethod
    def strict(cls,value):
        if type(value) is not dict or set(value)!={'ticker','question','idempotency_key','allow_analysis'} or value.get('allow_analysis') is not True:raise ValueError('Explicit financial opt in required')
        for name in ('question','idempotency_key'):
            item=value.get(name)
            if type(item) is not str or not item.strip() or '\x00' in item:raise ValueError('Invalid financial input')
        if len(value['idempotency_key'].encode('utf8'))>256:raise ValueError('Invalid key byte length')
        value['question'].encode('utf8');value['idempotency_key'].encode('utf8')
        return value

    def normalized_input(self):return {'ticker':self.ticker,'question':self.question}


class FundamentalAnalysisView(BaseModel):
    model_config=ConfigDict(extra='forbid',hide_input_in_errors=True)
    analysis_id:UUID
    admission_request_id:UUID
    attempt_id:UUID
    state:Literal['running','result_ready','stored','failed','unknown']
    deadline_at:datetime
    report_id:UUID|None=None
    report_url:str|None=None
    error:SafeError|None=None


FundamentalAnalysisResponse=CommonResponse[FundamentalAnalysisView]
