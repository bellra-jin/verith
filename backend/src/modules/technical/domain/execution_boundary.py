"""Technical-only detail contract. Validation never rewrites raw JSON."""
from __future__ import annotations
from typing import Literal
from pydantic import Field,model_validator,field_validator
from src.modules.analysis.domain.agent_envelope import AgentEnvelope,BoundaryInvalid,StrictModel,Stock,UUID_PATTERN,canonical,decode,digest,validate_json,utc
from src.modules.technical.domain.chart_contracts import TechnicalAgentOutput

OPERATION='technical.boundary.v1'
PROFILE='technical.multiframe.v1'
PERIODS=['3m','1y','5y']
REQUEST_LIMIT=16384
RESPONSE_LIMIT=2097152
WAIT_SECONDS=3.0
class Conditions(StrictModel):
    profile:Literal['technical.multiframe.v1']=PROFILE
    periods:list[Literal['3m','1y','5y']]=Field(default_factory=lambda:list(PERIODS))
    @field_validator('periods')
    @classmethod
    def periods_fixed(cls,v):
        if v!=PERIODS:raise BoundaryInvalid()
        return v
class ExecutionContext(StrictModel):
    analysis_id:str=Field(pattern=UUID_PATTERN)
    admission_request_id:str=Field(pattern=UUID_PATTERN)
    attempt_id:str=Field(pattern=UUID_PATTERN)
    report_id:str=Field(pattern=UUID_PATTERN)
    input_fingerprint:str=Field(pattern=r'^[0-9a-f]{64}$')
class TechnicalRequest(StrictModel):
    operation:Literal['technical.boundary.v1']
    context:ExecutionContext
    original_query:str=Field(min_length=1,max_length=2000)
    stock:Stock
    requested_views:list[Literal['technical']]
    requested_as_of:str
    conditions:Conditions=Field(default_factory=Conditions)
    @model_validator(mode='after')
    def binding(self):
        if not self.original_query.strip() or '\x00' in self.original_query or self.requested_views!=['technical']:raise BoundaryInvalid()
        self.original_query.encode('utf8');utc(self.requested_as_of)
        return self
class PeriodCoverage(StrictModel):
    period:Literal['3m','1y','5y']
    candle_unit:Literal['D','W']
    start:str|None
    end:str|None
    count:int=Field(ge=0)
    status:Literal['available','empty','not_provided']
class Coverage(StrictModel):
    requested_periods:list[Literal['3m','1y','5y']]
    available_periods:list[Literal['3m','1y','5y']]
    periods:list[PeriodCoverage]
    cutoff_validation:Literal['unverified']
    engine_generated_at:None
    source_published_at:None
    unreported_reason:Literal['engine_does_not_report']
class TechnicalSuccess(StrictModel):
    request_snapshot:TechnicalRequest
    request_sha256:str=Field(pattern=r'^[0-9a-f]{64}$')
    result:TechnicalAgentOutput
    coverage:Coverage
    execution_mode:Literal['synthetic']
    boundary_observed_at:str
RequestEnvelope=AgentEnvelope[TechnicalRequest]
ResponseEnvelope=AgentEnvelope[TechnicalSuccess]

def fingerprint(data):
    return digest({k:data[k] for k in ('operation','original_query','stock','requested_as_of','conditions')})
def parse_request(value):
    parsed=validate_json(RequestEnvelope,value)
    if parsed.data is None or parsed.error is not None:raise BoundaryInvalid()
    data=value['data'];conditions=data.get('conditions',{})
    # Defaults apply to the semantic profile; the raw snapshot remains untouched.
    condition=validate_json(Conditions,conditions).model_dump(mode='json')
    semantic={**data,'conditions':condition}
    if data['context']['input_fingerprint']!=fingerprint(semantic):raise BoundaryInvalid()
    ids=[value['request_id'],value['trace_id'],*[data['context'][k] for k in ('analysis_id','admission_request_id','attempt_id','report_id')]]
    if len(set(ids))!=len(ids):raise BoundaryInvalid()
    return parsed

def coverage_for(result):
    rows=[];available=[];charts=result.get('charts',[]);seen=set()
    for chart in charts:
        if chart['period'] not in PERIODS or chart['period'] in seen:raise BoundaryInvalid()
        seen.add(chart['period'])
    by_period={c['period']:c['chart_data'] for c in charts}
    for period in PERIODS:
        chart=by_period.get(period);dates=[c['date'] for c in chart['candles']] if chart else []
        if dates!=sorted(set(dates)):raise BoundaryInvalid()
        if dates:available.append(period)
        rows.append(dict(period=period,candle_unit='W' if period=='5y' else 'D',start=dates[0] if dates else None,end=dates[-1] if dates else None,count=len(dates),status='available' if dates else 'empty' if chart else 'not_provided'))
    return dict(requested_periods=list(PERIODS),available_periods=available,periods=rows,cutoff_validation='unverified',engine_generated_at=None,source_published_at=None,unreported_reason='engine_does_not_report')

def validate_result(result,request):
    validate_json(TechnicalAgentOutput,result);data=request['data']
    if any(result[k]!=v for k,v in {'request_id':request['request_id'],'trace_id':request['trace_id'],'ticker':data['stock']['stock_code'],'as_of':data['requested_as_of']}.items()):raise BoundaryInvalid()
    return coverage_for(result)
def validate_response(value,request):
    parse_request(request);parsed=validate_json(ResponseEnvelope,value)
    if parsed.data is None or parsed.error is not None:raise BoundaryInvalid()
    data=value['data']
    if value['request_id']!=request['request_id'] or value['trace_id']!=request['trace_id'] or data['request_snapshot']!=request['data'] or canonical(data['request_snapshot'])!=canonical(request['data']) or data['request_sha256']!=digest(request):raise BoundaryInvalid()
    if data['coverage']!=validate_result(data['result'],request):raise BoundaryInvalid()
    utc(data['boundary_observed_at']);return parsed
