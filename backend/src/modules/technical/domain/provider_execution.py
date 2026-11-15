"""Closed provider execution/control/usage contract. No I/O or defaults for policy."""
from dataclasses import dataclass
from datetime import datetime,UTC
import hashlib
import hmac
import json
import math
import re
from urllib.parse import urlsplit
from uuid import UUID
from .execution_boundary import parse_request,validate_result,coverage_for

SCHEMA='technical.execution.v1'
SPEC={'version':'technical.provider-execution.v1','operation':'technical.analysis.v1',
      'boundary':'technical.boundary.v1','storage':'technical.owned-stage.v1',
      'profile':'technical.multiframe.v1','periods':['3m','1y','5y'],
      'provider_authority':True,'settlement':False}
MAX=2**63-1
REASONS=frozenset({'POLICY_INVALID','DEADLINE_EXCEEDED','SDK_POLICY_INVALID','COUNT_UNAVAILABLE',
    'COUNT_INVALID','CLOSED','BUDGET_EXCEEDED','PROMPT_INVALID','SDK_UNKNOWN','COUNT_FAILED',
    'USAGE_UNKNOWN','USAGE_LIMIT_MISMATCH','RESPONSE_METADATA_MISMATCH','RESPONSE_NOT_COMPLETED',
    'TEXT_INVALID','CLOCK_INVALID','HTTP_INVALID','RESPONSE_LIMIT'})
POLICY_FIELDS=frozenset({'operation','enabled','currency','supported_tickers','user_daily_limit',
    'service_daily_limit','daily_budget_nano','attempt_reserve_nano','deadline_seconds','model',
    'service_tier','price_id','price_evidence_sha256','input_nano_per_token','output_nano_per_token',
    'input_token_cap','output_token_cap','input_byte_cap','output_byte_cap','max_calls'})
CONTROL_FIELDS=frozenset({'analysis_id','admission_request_id','attempt_id','report_id','boundary_request_id',
    'trace_id','spec_sha256','policy_sha256','configuration_sha256','intent_sha256','boundary_sha256',
    'stock_sha256','reserved_nano','started_at','deadline_at'})
RECORD_FIELDS=frozenset({'ordinal','analysis_id','attempt_id','policy_sha256','request_sha256','prompt_sha256',
    'projection_sha256','model','service_tier','input_token_cap','output_token_cap','held_nano','entered',
    'response_received','usage','estimated_nano','response_model','response_tier','text_accepted','reason',
    'elapsed_ms','count_entered','count_response_received','count_validated','counted_input_tokens'})

class ExecutionInvalid(ValueError):
    def __init__(self):super().__init__('Technical execution unavailable')

def canonical(value):
    try:return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
    except (TypeError,ValueError,UnicodeError,RecursionError,OverflowError):raise ExecutionInvalid() from None

def sha(text):return hashlib.sha256(text.encode('utf-8')).hexdigest()

def decode(raw,limit=65536):
    def unique(pairs):
        result={}
        for k,v in pairs:
            if k in result:raise ExecutionInvalid()
            result[k]=v
        return result
    try:
        if type(raw) is str:raw=raw.encode('utf-8')
        if type(raw) not in (bytes,bytearray) or not 0<len(raw)<=limit:raise ExecutionInvalid()
        return json.loads(raw.decode('utf-8'),object_pairs_hook=unique,
            parse_constant=lambda _:(_ for _ in ()).throw(ExecutionInvalid()))
    except (ValueError,TypeError,UnicodeError,RecursionError,OverflowError):raise ExecutionInvalid() from None

def shape(value,keys):
    if type(value) is not dict or set(value)!=set(keys):raise ExecutionInvalid()

def integer(value,zero=False):
    if type(value) is not int or not (0 if zero else 1)<=value<=MAX:raise ExecutionInvalid()
    return value

def digest(value):
    if type(value) is not str or re.fullmatch('[0-9a-f]{64}',value) is None:raise ExecutionInvalid()
    return value

def uid(value):
    try:
        if type(value) is not str or str(UUID(value))!=value or not UUID(value).int:raise ExecutionInvalid()
        return value
    except (ValueError,TypeError,AttributeError):raise ExecutionInvalid() from None

def stamp(value):
    try:
        if type(value) is not str:raise ExecutionInvalid()
        d=datetime.fromisoformat(value)
        if d.utcoffset()!=UTC.utcoffset(None):raise ExecutionInvalid()
        return d
    except (ValueError,TypeError,OverflowError):raise ExecutionInvalid() from None

def origin(value):
    try:
        if type(value) is not str or not value.isascii() or any(ord(c)<=32 or ord(c)>=127 for c in value):raise ExecutionInvalid()
        u=urlsplit(value)
        if u.scheme!='https' or not u.hostname or u.username or u.password or u.path or u.query or u.fragment or u.port==0:raise ExecutionInvalid()
        if value!='https://'+u.netloc or u.hostname!=u.hostname.lower():raise ExecutionInvalid()
        return value
    except (ValueError,TypeError):raise ExecutionInvalid() from None

def service_token(value):
    if type(value) is not str or not 32<=len(value)<=512 or not value.isascii() or any(ord(c)<32 or ord(c)>126 for c in value):raise ExecutionInvalid()
    return value.encode('ascii')

def policy(value):
    shape(value,POLICY_FIELDS)
    if value['operation']!='technical.analysis.v1' or value['enabled'] is not True or value['currency']!='USD' or value['service_tier']!='default':raise ExecutionInvalid()
    for k in POLICY_FIELDS-{'operation','enabled','currency','supported_tickers','model','service_tier','price_id','price_evidence_sha256'}:integer(value[k])
    for k in ('model','price_id'):
        if type(value[k]) is not str or re.fullmatch('[A-Za-z0-9_.:-]{1,128}',value[k]) is None:raise ExecutionInvalid()
    digest(value['price_evidence_sha256']);tickers=value['supported_tickers']
    if type(tickers) is not list or not tickers or len(tickers)>1000 or any(type(t) is not str or re.fullmatch('[0-9]{6}',t) is None for t in tickers) or tickers!=sorted(set(tickers)):raise ExecutionInvalid()
    hold=integer(integer(value['input_token_cap']*value['input_nano_per_token'])+integer(value['output_token_cap']*value['output_nano_per_token']))
    if not 1<=value['max_calls']<=4 or value['deadline_seconds']>86400 or value['user_daily_limit']>value['service_daily_limit'] or not integer(hold*value['max_calls'])<=value['attempt_reserve_nano']<=value['daily_budget_nano']:raise ExecutionInvalid()
    return value

@dataclass(frozen=True,slots=True,repr=False)
class Configuration:
    text:str
    def __post_init__(self):self.data()
    def data(self):
        v=decode(self.text,32768);shape(v,{'schema_version','policy','counter','caps','ai_origin','authority_origin','cache_mode','trace_mode'})
        if v['schema_version']!=SCHEMA or canonical(v)!=self.text:raise ExecutionInvalid()
        policy(v['policy']);c=v['counter'];shape(c,{'free','mapping','version','provenance_sha256','evidence_sha256'})
        if c['free'] is not True or c['mapping']!='technical.responses.model-input.v1' or type(c['version']) is not str or re.fullmatch('[A-Za-z0-9_.:-]{1,128}',c['version']) is None:raise ExecutionInvalid()
        digest(c['provenance_sha256']);digest(c['evidence_sha256']);shape(v['caps'],{'request','count','generation'})
        if any(integer(x)>2097152 for x in v['caps'].values()):raise ExecutionInvalid()
        origin(v['ai_origin']);origin(v['authority_origin'])
        if v['cache_mode'] not in {'none','injected'} or v['trace_mode'] not in {'none','injected'}:raise ExecutionInvalid()
        return v
    @classmethod
    def parse(cls,value):return cls(canonical(value))
    @property
    def fingerprint(self):return sha(self.text)
    @property
    def policy_sha256(self):return sha(canonical(self.data()['policy']))

SPEC_JSON=canonical(SPEC)
SPEC_SHA256=sha(SPEC_JSON)

def execution(boundary,control,configuration=None):
    parse_request(boundary);shape(control,CONTROL_FIELDS)
    for k in CONTROL_FIELDS-{'reserved_nano','started_at','deadline_at'}:
        (uid if k in {'analysis_id','admission_request_id','attempt_id','report_id','boundary_request_id','trace_id'} else digest)(control[k])
    integer(control['reserved_nano']);start,end=stamp(control['started_at']),stamp(control['deadline_at'])
    if end<=start or control['spec_sha256']!=SPEC_SHA256:raise ExecutionInvalid()
    data=boundary['data'];ctx=data['context']
    if any(control[k]!=ctx[k] for k in ('analysis_id','admission_request_id','attempt_id','report_id')) or control['boundary_request_id']!=boundary['request_id'] or control['trace_id']!=boundary['trace_id']:raise ExecutionInvalid()
    intent={'operation':'technical.analysis.v1','ticker':data['stock']['stock_code'],'original_query':data['original_query'],'requested_views':data['requested_views'],'conditions':data['conditions']}
    if (control['boundary_sha256']!=sha(canonical(boundary)) or control['stock_sha256']!=sha(canonical(data['stock'])) or control['intent_sha256']!=sha(canonical(intent)) or start!=stamp(data['requested_as_of'])):raise ExecutionInvalid()
    if configuration is not None:
        if type(configuration) is not Configuration or control['configuration_sha256']!=configuration.fingerprint or control['policy_sha256']!=configuration.policy_sha256:raise ExecutionInvalid()
        p=configuration.data()['policy']
        if control['reserved_nano']!=p['attempt_reserve_nano'] or (end-start).total_seconds()>p['deadline_seconds'] or data['stock']['stock_code'] not in p['supported_tickers']:raise ExecutionInvalid()
    value={'schema_version':SCHEMA,'boundary_request':boundary,'control':control}
    return value|{'control_sha256':sha(canonical(value))}

def parse_execution(value,configuration=None):
    shape(value,{'schema_version','boundary_request','control','control_sha256'})
    if value['schema_version']!=SCHEMA or execution(value['boundary_request'],value['control'],configuration)!=value:raise ExecutionInvalid()
    return value

def start_receipt(control_sha256,executor_id,started_at):
    digest(control_sha256);uid(executor_id);stamp(started_at)
    value={'control_sha256':control_sha256,'executor_id':executor_id,'started_at':started_at}
    return value|{'start_sha256':sha(canonical(value))}

def check_start(value,control_sha256,executor_id):
    shape(value,{'schema_version','newly_started','control_sha256','executor_id','started_at','start_sha256'})
    if value['schema_version']!=SCHEMA or type(value['newly_started']) is not bool or start_receipt(value['control_sha256'],value['executor_id'],value['started_at'])!={k:v for k,v in value.items() if k not in {'schema_version','newly_started'}}:raise ExecutionInvalid()
    if value['control_sha256']!=control_sha256 or value['newly_started'] and value['executor_id']!=executor_id:raise ExecutionInvalid()
    return value

def validate_controlled(value,boundary,expected):
    shape(value,{'schema_version','request_id','trace_id','data','error'})
    if value['schema_version']!=SCHEMA or value['request_id']!=boundary['request_id'] or value['trace_id']!=boundary['trace_id'] or value['error'] is not None:raise ExecutionInvalid()
    d=value['data'];shape(d,{'request_snapshot','request_sha256','result','coverage','execution_mode','boundary_observed_at','control_sha256','start_sha256','executor_id'})
    if d['execution_mode']!='controlled' or canonical(d['request_snapshot'])!=canonical(boundary['data']) or d['request_sha256']!=sha(canonical(boundary)):raise ExecutionInvalid()
    if any(d[k]!=expected[k] for k in ('control_sha256','start_sha256','executor_id')):raise ExecutionInvalid()
    stamp(d['boundary_observed_at'])
    if canonical(d['coverage'])!=canonical(validate_result(d['result'],boundary)):raise ExecutionInvalid()
    return value

def result(boundary,output,expected):
    data={'request_snapshot':boundary['data'],'request_sha256':sha(canonical(boundary)),'result':output,
          'coverage':validate_result(output,boundary),'execution_mode':'controlled',
          'boundary_observed_at':datetime.now(UTC).isoformat(),**{k:expected[k] for k in ('control_sha256','start_sha256','executor_id')}}
    value={'schema_version':SCHEMA,'request_id':boundary['request_id'],'trace_id':boundary['trace_id'],'data':data,'error':None}
    return validate_controlled(value,boundary,expected)

def evidence(value,configuration,control,start):
    shape(value,{'schema_version','analysis_id','attempt_id','policy_sha256','control_sha256','start_sha256','executor_id','outcome','records'})
    if value['schema_version']!='technical.usage.v1' or value['outcome'] not in {'completed','failed','cancelled','deadline','unknown'}:raise ExecutionInvalid()
    for k in ('analysis_id','attempt_id','policy_sha256'):
        if value[k]!=control[k]:raise ExecutionInvalid()
    for k in ('control_sha256','start_sha256','executor_id'):
        if value[k]!=start[k]:raise ExecutionInvalid()
    p=configuration.data()['policy'];rows=value['records']
    if type(rows) is not list or len(rows)>p['max_calls']:raise ExecutionInvalid()
    held=p['input_token_cap']*p['input_nano_per_token']+p['output_token_cap']*p['output_nano_per_token']
    for i,r in enumerate(rows,1):
        shape(r,RECORD_FIELDS)
        if type(r['ordinal']) is not int or r['ordinal']!=i or any(r[k]!=value[k] for k in ('analysis_id','attempt_id','policy_sha256')):raise ExecutionInvalid()
        for k in ('model','service_tier','input_token_cap','output_token_cap'):
            if type(r[k]) is not type(p[k]) or r[k]!=p[k]:raise ExecutionInvalid()
        if type(r['held_nano']) is not int or r['held_nano']!=held:raise ExecutionInvalid()
        for k in ('request_sha256','prompt_sha256','projection_sha256'):digest(r[k])
        for k in ('entered','response_received','text_accepted','count_entered','count_response_received','count_validated'):
            if type(r[k]) is not bool:raise ExecutionInvalid()
        if r['response_model'] not in {'unknown','match','mismatch'} or r['response_tier'] not in {'unknown','match','mismatch'} or r['reason'] is not None and r['reason'] not in REASONS:raise ExecutionInvalid()
        integer(r['elapsed_ms'],True)
        if (r['entered'] and not r['count_validated'] or r['count_validated'] and not (r['count_entered'] and r['count_response_received']) or r['count_response_received'] and not r['count_entered'] or r['response_received'] and not r['entered']):raise ExecutionInvalid()
        if r['counted_input_tokens'] is not None:
            integer(r['counted_input_tokens'],True)
            if not r['count_validated'] or r['counted_input_tokens']>p['input_token_cap']:raise ExecutionInvalid()
        elif r['count_validated']:raise ExecutionInvalid()
        usage=r['usage']
        if usage is None:
            if r['estimated_nano'] is not None or r['text_accepted']:raise ExecutionInvalid()
        else:
            if type(usage) is not list or len(usage)!=3 or not r['response_received']:raise ExecutionInvalid()
            for n in usage:integer(n,True)
            if usage[0]+usage[1]!=usage[2]:raise ExecutionInvalid()
            estimate=usage[0]*p['input_nano_per_token']+usage[1]*p['output_nano_per_token']
            if estimate>MAX:
                if r['estimated_nano'] is not None:raise ExecutionInvalid()
            elif type(r['estimated_nano']) is not int or r['estimated_nano']!=estimate:raise ExecutionInvalid()
        if r['text_accepted'] and (r['response_model']=='mismatch' or r['response_tier']=='mismatch' or not r['response_received'] or r['reason'] is not None or usage[0]!=r['counted_input_tokens'] or usage[0]>p['input_token_cap'] or usage[1]>p['output_token_cap']):raise ExecutionInvalid()
    if len(rows)*held>control['reserved_nano']:raise ExecutionInvalid()
    if len(canonical(value).encode('utf-8'))>16384:raise ExecutionInvalid()
    return value


def boundary_for(run,intent,stock):
    from .execution_boundary import fingerprint
    data={'operation':'technical.boundary.v1','original_query':intent['original_query'],'stock':stock,
          'requested_views':intent['requested_views'],'requested_as_of':run.as_of.isoformat(),'conditions':intent['conditions']}
    data['context']={'analysis_id':str(run.analysis_id),'admission_request_id':str(run.admission_request_id),
        'attempt_id':str(run.attempt_id),'report_id':str(run.report_id),'input_fingerprint':fingerprint(data)}
    value={'schema_version':'analysis.agent.v1','request_id':str(run.boundary_request_id),'trace_id':str(run.trace_id),'data':data,'error':None}
    parse_request(value);return value

def control_for(run,boundary,configuration):
    value={k:str(getattr(run,k)) for k in ('analysis_id','admission_request_id','attempt_id','report_id','boundary_request_id','trace_id')}
    value.update(spec_sha256=SPEC_SHA256,policy_sha256=run.policy_sha256,configuration_sha256=configuration.fingerprint,
        intent_sha256=run.intent_sha256,boundary_sha256=sha(canonical(boundary)),stock_sha256=sha(canonical(boundary['data']['stock'])),
        reserved_nano=run.reserved_nano,started_at=run.as_of.isoformat(),deadline_at=run.deadline_at.isoformat())
    return execution(boundary,value,configuration)
