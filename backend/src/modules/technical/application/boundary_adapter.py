"""Non-persistent Technical boundary; not registered as an execution profile."""
from dataclasses import dataclass
from uuid import UUID
from src.modules.analysis.domain.contracts import AnalysisContext,FrozenAnalysisResult
from src.modules.analysis.domain.agent_envelope import canonical,decode,BoundaryInvalid,SCHEMA_VERSION,utc
from src.modules.technical.domain.execution_boundary import OPERATION,PROFILE,PERIODS,parse_request,validate_response,fingerprint

@dataclass(frozen=True,slots=True)
class TechnicalBoundaryBinding:
    context:AnalysisContext
    report_id:UUID
    request_id:UUID
    trace_id:UUID
    input_json:str
    def __post_init__(self):
        self.context.validate()
        if not all(isinstance(x,UUID) for x in (self.report_id,self.request_id,self.trace_id)):raise BoundaryInvalid()
        value=decode(self.input_json);parse_request(value);data=value['data'];ctx=data['context']
        if canonical(value)!=self.input_json or self.context.operation!=OPERATION or data['operation']!=self.context.operation or utc(data['requested_as_of'])!=self.context.as_of:raise BoundaryInvalid()
        if value['request_id']!=str(self.request_id) or value['trace_id']!=str(self.trace_id):raise BoundaryInvalid()
        expected=dict(analysis_id=str(self.context.analysis_id),admission_request_id=str(self.context.admission_request_id),attempt_id=str(self.context.attempt_id),report_id=str(self.report_id),input_fingerprint=self.context.input_fingerprint)
        if ctx!=expected:raise BoundaryInvalid()

class TechnicalBoundaryAdapter:
    def __init__(self,binding:TechnicalBoundaryBinding):
        if not isinstance(binding,TechnicalBoundaryBinding):raise BoundaryInvalid()
        self.binding=binding
    def build_request(self):return decode(self.binding.input_json)
    async def run(self,client):return self.validate_and_freeze(await client.technical_boundary(self.build_request()))
    def validate_and_freeze(self,response):
        request=self.build_request();validate_response(response,request)
        return FrozenAnalysisResult.freeze(context=self.binding.context,report_id=self.binding.report_id,input_schema=SCHEMA_VERSION,result_schema='technical.boundary.v1',input_json=self.binding.input_json,result_json=canonical(response))
    def chart_preview(self,frozen):
        frozen.validate()
        if frozen.context!=self.binding.context or frozen.report_id!=self.binding.report_id or frozen.input_json!=self.binding.input_json or frozen.input_schema!=SCHEMA_VERSION or frozen.result_schema!=OPERATION:raise BoundaryInvalid()
        response=decode(frozen.result_json);validate_response(response,self.build_request());data=response['data'];charts=data['result'].get('charts',[])
        return dict(report_id=str(frozen.report_id),stock=self.build_request()['data']['stock'],available_periods=data['coverage']['available_periods'],charts=[dict(period=c['period'],candle_unit=c['chart_data']['candle_unit'],display_order=PERIODS.index(c['period']),has_chart_data=bool(c['chart_data']['candles']),annotation_count=len(c['chart_data']['annotations']),chart_data=c['chart_data'],annotations=c['chart_data']['annotations']) for c in charts])
    async def stage(self,*args,**kwargs):raise RuntimeError('Technical boundary is non-persistent')
