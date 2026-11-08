"""Service-authenticated financial request, no agent/config imports."""
from datetime import UTC,datetime,timedelta
import hashlib,json
from typing import Annotated,Literal
from uuid import UUID
from pydantic import BaseModel,ConfigDict,Field,model_validator
from ..domain.contracts import FundamentalAgentInput

SPEC={'engine':'fundamental.public.v1','input_schema':'fundamental.request-context.v1',
      'result_schema':'fundamental.agent-output.v1','as_of_semantics':'request_time_only',
      'deadline_seconds':60,'http_timeout_seconds':65,'bff_timeout_seconds':70,'dispatch_retries':0}


def canonical(value):return json.dumps(value,ensure_ascii=False,allow_nan=False,sort_keys=True,separators=(',',':'))
def sha(value):return hashlib.sha256(canonical(value).encode('utf8')).hexdigest()
def decode(raw):
    def pairs(items):
        value={}
        for key,item in items:
            if key in value:raise ValueError('Invalid financial JSON')
            value[key]=item
        return value
    return json.loads(raw.decode('utf8'),object_pairs_hook=pairs,
        parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Invalid financial JSON')))


class FundamentalAnalysisInput(BaseModel):
    model_config=ConfigDict(extra='forbid',hide_input_in_errors=True)
    schema_version:Literal[1]
    analysis_id:UUID
    admission_request_id:UUID
    attempt_id:UUID
    fingerprint:Annotated[str,Field(strict=True,pattern='^[0-9a-f]{64}$')]
    requested_at:datetime
    deadline_at:datetime
    spec:dict
    request:FundamentalAgentInput

    @model_validator(mode='before')
    @classmethod
    def explicit(cls,value):
        if type(value) is not dict or type(value.get('schema_version')) is not int or value['schema_version']!=1:raise ValueError('Invalid financial envelope')
        for name in ('requested_at','deadline_at'):
            raw=value.get(name)
            if type(raw) is not str or datetime.fromisoformat(raw).utcoffset()!=timedelta(0):raise ValueError('Explicit UTC required')
        raw=value.get('request')
        if type(raw) is not dict or set(raw)!={'request_id','trace_id','ticker','query'}:raise ValueError('Invalid financial request')
        for name,item in raw.items():
            if type(item) is not str or not item.strip() or '\x00' in item:raise ValueError('Invalid financial text')
            item.encode('utf8')
        if len(raw['query'])>2000 or len(raw['ticker'])!=6 or not raw['ticker'].isascii() or not raw['ticker'].isdigit():raise ValueError('Invalid financial request')
        return value

    @model_validator(mode='after')
    def bound(self):
        if (self.deadline_at-self.requested_at!=timedelta(seconds=60) or self.requested_at>datetime.now(UTC)
                or self.request.request_id!='req-'+self.admission_request_id.hex
                or self.request.trace_id!='trace-'+self.attempt_id.hex or canonical(self.spec)!=canonical(SPEC)):
            raise ValueError('Invalid financial binding')
        if sha(dict(ticker=self.request.ticker,question=self.request.query))!=self.fingerprint:raise ValueError('Invalid financial fingerprint')
        return self

    def wire(self):
        value=self.model_dump(mode='json')
        for name in ('requested_at','deadline_at'):value[name]=getattr(self,name).astimezone(UTC).isoformat()
        return value
