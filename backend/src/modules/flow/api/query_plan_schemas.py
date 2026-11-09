"""Public preparation DTO, not an execution token or analysis request."""
from typing import Literal
from uuid import UUID
from pydantic import Field,model_validator
from src.modules.flow.domain.query_plan import StrictPlanModel,PlanView

PATH='/api/flow/plans'
class QueryPlanRequest(StrictPlanModel):
    query:str=Field(min_length=1,max_length=300)
    selected_ticker:str|None=Field(default=None,pattern=r'^[0-9]{6}$')
    candidate_ref:str|None=Field(default=None,pattern=r'^[0-9a-f]{64}$')
    @model_validator(mode='after')
    def valid_query(self):
        self.query.encode('utf8')
        if not self.query.strip() or '\x00' in self.query:raise ValueError('Invalid query')
        if (self.selected_ticker is None)!=(self.candidate_ref is None):raise ValueError('Invalid selection')
        return self

class QueryPlanSafeError(StrictPlanModel):
    code:Literal['AUTH_REQUIRED','AUTH_REQUEST_INVALID','FEATURE_UNAVAILABLE','INPUT_INVALID','SERVICE_UNAVAILABLE','DEADLINE_EXCEEDED','RESULT_CONTRACT_INVALID']
    message:Literal['준비 요청을 확인할 수 없습니다.']='준비 요청을 확인할 수 없습니다.'
class QueryPlanResponse(StrictPlanModel):
    request_id:UUID
    data:PlanView|None=None
    error:QueryPlanSafeError|None=None
