"""Backend validates canonical inputs and tool protocol, never classifies intent."""
import hashlib
import json
import re
import unicodedata
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,field_validator,model_validator

VERSION='supervisor.flow-plan.v1'
POLICY='supervisor.flow-only.1'
PLAN_TIMEOUT_SECONDS=10.0
VIEWS=('flow','technical','fundamental','macro','industry','news','overview')

def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(value):return hashlib.sha256(value.encode('utf8')).hexdigest()
def decode(raw):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('Invalid JSON')
            result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Invalid JSON')))

class StrictPlanModel(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,hide_input_in_errors=True)

class StockReference(StrictPlanModel):
    stock_code:str=Field(pattern=r'^[0-9]{6}$')
    stock_name:str=Field(min_length=1,max_length=256)
    market:Literal['KOSPI','KOSDAQ','KONEX']|None
    @field_validator('stock_name')
    @classmethod
    def valid_name(cls,value):
        value.encode('utf8')
        if not value.strip() or any(unicodedata.category(c)=='Cc' for c in value):raise ValueError('Invalid stock name')
        return value

class StockOption(StockReference):
    match_type:Literal['stock_code','stock_name','alias','ambiguous_group']

class CanonicalResolution(StrictPlanModel):
    status:Literal['resolved','ambiguous','not_found']
    reason:Literal['exact_match','multiple_stocks','conflicting_identifiers','ambiguous_alias','unknown_identifier','no_match']
    stock:StockReference|None
    candidates:list[StockOption]=Field(max_length=10)
    @model_validator(mode='after')
    def consistent(self):
        codes=[c.stock_code for c in self.candidates]
        if len(set(codes))!=len(codes):raise ValueError('Invalid canonical result')
        if self.status=='resolved':
            if self.stock is None or self.candidates or self.reason!='exact_match':raise ValueError('Invalid canonical result')
        elif self.status=='not_found':
            if self.stock is not None or self.candidates or self.reason!='no_match':raise ValueError('Invalid canonical result')
        elif self.stock is not None or self.reason not in {'multiple_stocks','conflicting_identifiers','ambiguous_alias','unknown_identifier'}:raise ValueError('Invalid canonical result')
        return self

def resolution_ref(query,resolution):
    value=resolution.model_dump(mode='json') if isinstance(resolution,CanonicalResolution) else resolution
    value={**value,'candidates':sorted(value['candidates'],key=lambda x:x['stock_code'])}
    return digest(canonical({'version':VERSION,'policy_version':POLICY,'query':query,'resolution':value}))

def selected_resolution(resolution,selected):
    if selected is None:return resolution
    if resolution.status!='ambiguous':raise ValueError('Invalid selection')
    item=next((c for c in resolution.candidates if c.stock_code==selected),None)
    if item is None:raise ValueError('Invalid selection')
    return CanonicalResolution(status='resolved',reason='exact_match',stock=StockReference(**item.model_dump(exclude={'match_type'})),candidates=[])

class PlanView(StrictPlanModel):
    version:Literal['supervisor.flow-plan.v1']
    policy_version:Literal['supervisor.flow-only.1']
    query_sha256:str=Field(pattern=r'^[0-9a-f]{64}$')
    requested_views:list[str]=Field(max_length=7)
    status:Literal['ready_for_confirmation','needs_stock_selection','selection_stale','not_found','needs_clarification','unsupported']
    reason:Literal['unsupported_views','clarify_intent','clarify_stock_scope','stock_resolved','stock_ambiguous','stock_not_found','selection_changed']
    resolution:CanonicalResolution|None
    candidate_ref:str|None=Field(pattern=r'^[0-9a-f]{64}$')
    @field_validator('requested_views')
    @classmethod
    def valid_views(cls,value):
        if len(set(value))!=len(value) or any(v not in VIEWS for v in value):raise ValueError('Invalid views')
        return value
    @model_validator(mode='after')
    def consistent(self):
        pairs={'ready_for_confirmation':'stock_resolved','needs_stock_selection':'stock_ambiguous','not_found':'stock_not_found','selection_stale':'selection_changed','unsupported':'unsupported_views'}
        if self.status in pairs and self.reason!=pairs[self.status]:raise ValueError('Invalid plan')
        if self.status=='needs_clarification' and self.reason not in {'clarify_intent','clarify_stock_scope'}:raise ValueError('Invalid plan')
        if self.status in {'unsupported','needs_clarification'}:
            if self.resolution is not None or self.candidate_ref is not None:raise ValueError('Invalid plan')
        else:
            if self.requested_views!=['flow'] or self.resolution is None or self.candidate_ref is None:raise ValueError('Invalid plan')
            wanted={'ready_for_confirmation':'resolved','needs_stock_selection':'ambiguous','selection_stale':'ambiguous','not_found':'not_found'}[self.status]
            if self.resolution.status!=wanted:raise ValueError('Invalid plan')
        return self

class QueryPlanError(Exception):
    def __init__(self,code='RESULT_CONTRACT_INVALID',status=502):
        super().__init__('Plan unavailable');self.code=code;self.status=status

def resolver_result(value):
    try:
        if hasattr(value,'model_dump'):value=value.model_dump(mode='json')
        if type(value) is not dict or set(value)!={'status','reason','stock','candidates'}:raise ValueError()
        if type(value['candidates']) is not list:raise ValueError()
        options=[]
        for item in value['candidates']:
            if type(item) is not dict or set(item)!={'stock_code','stock_name','market','match_type','matched_text'} or type(item['matched_text']) is not str:raise ValueError()
            options.append({k:v for k,v in item.items() if k!='matched_text'})
        return CanonicalResolution.model_validate({**value,'candidates':options})
    except (ValueError,TypeError,UnicodeError):raise QueryPlanError() from None

def validate_wire(value,request,*,start=None,resolution=None,selected=None):
    try:
        keys={'version','policy_version','request_id','trace_id','query_sha256','requested_views','kind','plan'}
        if type(value) is not dict or set(value)!=keys:raise ValueError()
        for key in ('policy_version','request_id','trace_id','query_sha256'):
            if value[key]!=request[key]:raise ValueError()
        if value['version']!=VERSION or type(value['requested_views']) is not list or len(set(value['requested_views']))!=len(value['requested_views']) or any(type(v) is not str or v not in VIEWS for v in value['requested_views']):raise ValueError()
        if request['phase']=='start':
            if value['kind']=='resolve_stock':
                if value['plan'] is not None or value['requested_views']!=['flow']:raise ValueError()
                return value
            plan=PlanView.model_validate(value['plan'])
            if value['kind']!='final' or plan.status not in {'unsupported','needs_clarification'}:raise ValueError()
        else:
            if value['kind']!='final' or value['requested_views']!=start['requested_views']:raise ValueError()
            plan=PlanView.model_validate(value['plan'])
            expected=selected_resolution(resolution,selected)
            if plan.resolution!=expected or plan.candidate_ref!=resolution_ref(request['query'],resolution):raise ValueError()
            wanted={'resolved':'ready_for_confirmation','ambiguous':'needs_stock_selection','not_found':'not_found'}[expected.status]
            if plan.status!=wanted:raise ValueError()
        if plan.query_sha256!=request['query_sha256'] or plan.requested_views!=value['requested_views'] or plan.policy_version!=request['policy_version']:raise ValueError()
        return value
    except (ValueError,TypeError,UnicodeError,KeyError,AttributeError):raise QueryPlanError() from None
