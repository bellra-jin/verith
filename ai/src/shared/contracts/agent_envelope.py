"""Pure versioned wire primitives; no configuration, persistence or provider imports."""
from __future__ import annotations
import hashlib,json,math,re
from datetime import datetime,timedelta
from typing import Generic,Literal,TypeVar
from pydantic import BaseModel,ConfigDict,Field,field_validator,model_validator

SCHEMA_VERSION='analysis.agent.v1'
UUID_PATTERN=r'^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$'
class BoundaryInvalid(ValueError):
    def __init__(self):super().__init__('Technical boundary contract is invalid')
def canonical(value):
    def checked(v):
        if type(v) is dict:
            if any(type(k) is not str for k in v):raise BoundaryInvalid()
            for child in v.values():checked(child)
        elif type(v) is list:
            for child in v:checked(child)
        elif type(v) not in {str,int,float,bool,type(None)} or type(v) is float and not math.isfinite(v):raise BoundaryInvalid()
    try:
        checked(value)
        result=json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
        result.encode('utf8')
        return result
    except (ValueError,TypeError,UnicodeError,RecursionError):raise BoundaryInvalid() from None

def digest(value):return hashlib.sha256(canonical(value).encode('utf8')).hexdigest()
def decode(raw):
    def pairs(items):
        result={}
        for k,v in items:
            if k in result:raise BoundaryInvalid()
            result[k]=v
        return result
    try:
        if isinstance(raw,(bytes,bytearray)):raw=bytes(raw).decode('utf8')
        value=json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(BoundaryInvalid()));canonical(value);return value
    except (ValueError,TypeError,UnicodeError,RecursionError):raise BoundaryInvalid() from None
class StrictModel(BaseModel):model_config=ConfigDict(extra='forbid',strict=True,hide_input_in_errors=True)
class Stock(StrictModel):
    stock_code:str=Field(pattern=r'^[0-9]{6}$')
    stock_name:str=Field(min_length=1,max_length=256)
    market:Literal['KOSPI','KOSDAQ','KONEX']|None
    @field_validator('stock_name')
    @classmethod
    def name(cls,v):
        if not v.strip() or any(ord(c)<32 or 127<=ord(c)<=159 for c in v):raise BoundaryInvalid()
        v.encode('utf8');return v
class SafeError(StrictModel):
    code:Literal['FEATURE_UNAVAILABLE','AUTH_REQUIRED','INPUT_INVALID','SERVICE_UNAVAILABLE','DEADLINE_EXCEEDED','RESULT_CONTRACT_INVALID','BUSY']
    message:Literal['Technical boundary unavailable']='Technical boundary unavailable'
T=TypeVar('T')
class AgentEnvelope(StrictModel,Generic[T]):
    schema_version:Literal['analysis.agent.v1']
    request_id:str=Field(pattern=UUID_PATTERN)
    trace_id:str=Field(pattern=UUID_PATTERN)
    data:T|None
    error:SafeError|None
    @model_validator(mode='after')
    def exclusive(self):
        if (self.data is None)==(self.error is None):raise BoundaryInvalid()
        return self

def validate_json(model,value):
    try:return model.model_validate_json(canonical(value),strict=True)
    except (ValueError,TypeError,UnicodeError,RecursionError):raise BoundaryInvalid() from None

def utc(value):
    try:
        result=datetime.fromisoformat(value.replace('Z','+00:00'))
        if result.utcoffset()!=timedelta(0):raise BoundaryInvalid()
        return result
    except (ValueError,TypeError,AttributeError):raise BoundaryInvalid() from None
