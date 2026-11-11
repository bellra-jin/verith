"""Lossless input projection and typed synthetic boundary result assembly."""
from datetime import UTC,datetime
from src.shared.contracts.agent_envelope import SCHEMA_VERSION
from src.agents.technical.domain.models.contracts import TechnicalAgentInput
from src.agents.technical.domain.boundary_contracts import validate_json,validate_result,validate_response,digest
from src.supervisor.application.planning.technical_boundary import build_plan

def project_input(request):
    build_plan(request);data=request['data']
    return validate_json(TechnicalAgentInput,dict(ticker=data['stock']['stock_code'],stock_name=data['stock']['stock_name'],query=data['original_query'],request_id=request['request_id'],as_of=data['requested_as_of']))
def complete(request,result):
    coverage=validate_result(result,request)
    value=dict(schema_version=SCHEMA_VERSION,request_id=request['request_id'],trace_id=request['trace_id'],data=dict(request_snapshot=request['data'],request_sha256=digest(request),result=result,coverage=coverage,execution_mode='synthetic',boundary_observed_at=datetime.now(UTC).isoformat()),error=None)
    validate_response(value,request);return value
