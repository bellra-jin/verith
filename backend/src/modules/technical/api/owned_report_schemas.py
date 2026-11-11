"""Closed read-only wire and exact target grammar; no configuration or I/O."""
import json
import re
from typing import Literal
from urllib.parse import parse_qsl
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from src.modules.analysis.domain.agent_envelope import utc
from starlette.responses import JSONResponse

PATH = '/api/technical/owned-reports'
SCHEMA = 'technical.owned-read.v1'
LIST_CAP = 65536
DETAIL_CAP = 4259840
PRIVATE = {'Cache-Control':'private, no-store','Vary':'Cookie, Origin'}
STATUSES = {'AUTH_REQUIRED':401,'AUTH_REQUEST_INVALID':403,'FEATURE_UNAVAILABLE':403,'RESOURCE_NOT_FOUND':404,'INPUT_INVALID':422,
            'RESULT_CONTRACT_INVALID':502,'SERVICE_UNAVAILABLE':503,'DEADLINE_EXCEEDED':504}


class ReadInvalid(ValueError):
    def __init__(self, code='INPUT_INVALID'):
        self.code = code
        super().__init__('Technical read unavailable')


def target(method, path, query=b''):
    if method != 'GET': raise ReadInvalid('FEATURE_UNAVAILABLE')
    if path == PATH:
        try:
            pairs = parse_qsl(query.decode('ascii'),keep_blank_values=True,strict_parsing=True)
            values = dict(pairs)
            if len(values) != len(pairs) or set(values)-{'stock_code','limit','offset'}: raise ValueError()
            if 'stock_code' in values and not re.fullmatch('[0-9]{6}',values['stock_code']): raise ValueError()
            for key in ('limit','offset'):
                if key in values and not re.fullmatch('[0-9]{1,5}',values[key]): raise ValueError()
            limit,offset = int(values.get('limit','10')),int(values.get('offset','0'))
            if not 1<=limit<=20 or not 0<=offset<=10000: raise ValueError()
            return None,dict(stock_code=values.get('stock_code'),limit=limit,offset=offset)
        except (ValueError,UnicodeError): raise ReadInvalid() from None
    if query: raise ReadInvalid()
    if not path.startswith(PATH+'/') or '/' in path[len(PATH)+1:]: raise ReadInvalid('FEATURE_UNAVAILABLE')
    segment = path[len(PATH)+1:]
    try:
        value = UUID(segment)
        if str(value) != segment: raise ValueError()
        return value,{}
    except ValueError: raise ReadInvalid() from None


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid',strict=True)


class Stock(Strict):
    stock_code: str = Field(pattern='^[0-9]{6}$')
    stock_name: str = Field(min_length=1,max_length=256)
    market: Literal['KOSPI','KOSDAQ','KONEX'] | None

    @field_validator('stock_name')
    @classmethod
    def name_valid(cls,value):
        if not value.strip() or any(ord(c)<32 or 127<=ord(c)<=159 for c in value): raise ValueError('Invalid stock')
        value.encode('utf-8')
        return value


class Item(Strict):
    report_id: UUID
    stock: Stock
    created_at: str
    requested_as_of: str
    execution_mode: Literal['synthetic']
    cutoff_validation: Literal['unverified']

    @field_validator('created_at','requested_as_of')
    @classmethod
    def timestamp(cls,value):
        utc(value)
        return value


class ListData(Strict):
    items: list[Item] = Field(max_length=20)
    limit: int = Field(ge=1,le=20)
    offset: int = Field(ge=0,le=10000)
    has_more: bool

    @model_validator(mode='after')
    def bounded(self):
        if len(self.items)>self.limit or len({item.report_id for item in self.items})!=len(self.items):
            raise ValueError('Invalid list')
        return self


class DetailData(Strict):
    report_id: UUID
    created_at: str
    request_json: str
    request_sha256: str = Field(pattern='^[0-9a-f]{64}$')
    result_json: str
    result_sha256: str = Field(pattern='^[0-9a-f]{64}$')

    @field_validator('created_at')
    @classmethod
    def timestamp(cls,value):
        utc(value)
        return value

    @field_validator('request_json','result_json')
    @classmethod
    def text_limit(cls,value,info):
        if not 2<=len(value.encode('utf-8'))<=(16384 if info.field_name=='request_json' else 2097152):
            raise ValueError('Invalid stored text')
        return value


def response(scope, data, *, detail=False):
    model = DetailData if detail else ListData
    # JSON validation accepts transport UUID strings while preserving strict numeric types.
    validated = model.model_validate_json(json.dumps(data,ensure_ascii=False,allow_nan=False)).model_dump(mode='json')
    wire = JSONResponse(dict(schema_version=SCHEMA,request_id=request_id(scope),data=validated,error=None),headers=PRIVATE)
    if len(wire.body) > (DETAIL_CAP if detail else LIST_CAP): raise ReadInvalid('RESULT_CONTRACT_INVALID')
    return wire


def request_id(scope):
    return scope.setdefault('technical_owned_read_request_id',str(uuid4()))


def error(scope, code):
    if code not in STATUSES: code = 'SERVICE_UNAVAILABLE'
    return JSONResponse(dict(schema_version=SCHEMA,request_id=request_id(scope),data=None,
        error=dict(code=code,message='Technical result unavailable')),status_code=STATUSES[code],headers=PRIVATE)
