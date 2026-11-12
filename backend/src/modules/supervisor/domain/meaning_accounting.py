"""Strict, immutable accounting inputs. Receipts never authorize provider dispatch."""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
import hashlib
import json
import re

MAX = 9223372036854775807
class AccountingConflict(ValueError):
    def __init__(self): super().__init__('Supervisor accounting conflict')

def integer(v, minimum=0):
    if type(v) is not int or not minimum <= v <= MAX: raise AccountingConflict()
    return v

def digest(v):
    if type(v) is not str or re.fullmatch('[0-9a-f]{64}',v) is None: raise AccountingConflict()
    return v

def canonical(v):
    def check(x):
        if type(x) is dict:
            if any(type(k) is not str for k in x): raise AccountingConflict()
            for item in x.values(): check(item)
        elif type(x) is list:
            for item in x: check(item)
        elif type(x) is int: integer(x)
        elif type(x) not in (str, bool, type(None)): raise AccountingConflict()
    check(v)
    s=json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':'))
    if len(s.encode())>16384: raise AccountingConflict()
    return s

def sha(s): return hashlib.sha256(s.encode()).hexdigest()
def instant(v):
    if type(v) is not datetime or v.tzinfo is None or v.utcoffset() is None: raise AccountingConflict()
    return v

def uid(v):
    if type(v) is not UUID: raise AccountingConflict()
    return v

@dataclass(frozen=True, repr=False)
class Policy:
    operation: str
    scope: str
    starts_at: datetime
    ends_at: datetime
    limit_nano: int
    attempt_nano: int
    max_attempts: int
    semantic_json: str
    price_json: str
    model: str
    tier: str
    input_cap: int
    output_cap: int

    def __post_init__(self):
        for v in (self.operation,self.model,self.tier):
            if type(v) is not str or not 1<=len(v)<=128 or v.strip()!=v: raise AccountingConflict()
        if type(self.scope) is not str or canonical(json.loads(self.scope))!=self.scope or type(json.loads(self.scope)) is not dict or self.scope=='{}': raise AccountingConflict()
        if instant(self.starts_at)>=instant(self.ends_at): raise AccountingConflict()
        for v in (self.limit_nano,self.attempt_nano,self.max_attempts,self.input_cap,self.output_cap): integer(v,1)
        if self.attempt_nano>self.limit_nano: raise AccountingConflict()
        for raw in (self.semantic_json,self.price_json):
            if type(raw) is not str or canonical(json.loads(raw))!=raw or type(json.loads(raw)) is not dict: raise AccountingConflict()
        p=json.loads(self.price_json)
        if set(p)!={'id','currency','input_nano_per_token','cached_nano_per_token','output_nano_per_token'} or p['currency']!='USD': raise AccountingConflict()
        for k in ('input_nano_per_token','cached_nano_per_token','output_nano_per_token'): integer(p[k],1)
        if p['cached_nano_per_token']>p['input_nano_per_token']: raise AccountingConflict()
        spec=json.loads(self.semantic_json)
        try:
            matches=self.price_json==canonical(spec['price']) and self.model==spec['model'] and self.tier==spec['service_tier'] and self.input_cap==spec['caps']['input_tokens'] and self.output_cap==spec['caps']['output_tokens']
        except (KeyError,TypeError): raise AccountingConflict() from None
        if not matches: raise AccountingConflict()
    def require_current(self):
        # New accounts/reservations use today's contract; historical settlement
        # uses only the immutable internally consistent snapshot already stored.
        from src.modules.supervisor.domain.contracts import MEANING_SPEC
        if self.semantic_json!=canonical(MEANING_SPEC): raise AccountingConflict()
    def snapshot(self):
        return canonical(dict(operation=self.operation,scope=self.scope,starts_at=self.starts_at.isoformat(),ends_at=self.ends_at.isoformat(),limit_nano=self.limit_nano,attempt_nano=self.attempt_nano,max_attempts=self.max_attempts,semantic_json=self.semantic_json,price_json=self.price_json,model=self.model,tier=self.tier,input_cap=self.input_cap,output_cap=self.output_cap,currency='USD'))

@dataclass(frozen=True)
class Binding:
    preparation_id: UUID
    attempt_id: UUID
    session_id: UUID
    request_sha256: str
    draft_sha256: str
    projection_sha256: str
    semantic_sha256: str
    price_sha256: str
    expires_at: datetime
    def __post_init__(self):
        for v in (self.preparation_id,self.attempt_id,self.session_id): uid(v)
        for v in (self.request_sha256,self.draft_sha256,self.projection_sha256,self.semantic_sha256,self.price_sha256): digest(v)
        instant(self.expires_at)
    def snapshot(self):
        return canonical({k:(str(v) if type(v) is UUID else v.isoformat() if type(v) is datetime else v) for k,v in vars(self).items()})

def settlement(policy, evidence):
    """Return fixed state/estimate; never clamp or release a reservation."""
    if type(evidence) is not dict: raise AccountingConflict()
    if evidence=={'state':'unknown'}: return 'unknown',None
    required={'state','model','tier','input','cached','output','total','request_sha256','projection_sha256','binding_sha256','semantic_sha256','price_sha256'}
    if set(evidence)!=required or evidence['state']!='observed': return 'anomalous',None
    try:
        for k in ('input','cached','output','total'): integer(evidence[k])
        if evidence['cached']>evidence['input'] or evidence['input']+evidence['output']!=evidence['total'] or evidence['input']>policy.input_cap or evidence['output']>policy.output_cap or evidence['model']!=policy.model or evidence['tier']!=policy.tier: raise AccountingConflict()
        p=json.loads(policy.price_json)
        amount=(evidence['input']-evidence['cached'])*p['input_nano_per_token']+evidence['cached']*p['cached_nano_per_token']+evidence['output']*p['output_nano_per_token']
        integer(amount)
        if amount>policy.attempt_nano: raise AccountingConflict()
        return 'observed',amount
    except (AccountingConflict,KeyError,TypeError): return 'anomalous',None

# CF045: closed server policy and provider input identities. No source discovery.
INPUT_FIELDS=('model','instructions','input','text','tools','tool_choice','parallel_tool_calls','reasoning')
COUNT_DOCUMENTATION='https://developers.openai.com/api/reference/resources/responses/subresources/input_tokens/methods/count'

def wire(value, maximum=98304):
    try: raw=json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)
    except (ValueError,TypeError,OverflowError,RecursionError): raise AccountingConflict() from None
    if len(raw.encode())>maximum: raise AccountingConflict()
    return raw

def strict_json(raw, maximum=98304):
    if type(raw) not in {str,bytes,bytearray} or len(raw.encode() if type(raw) is str else raw)>maximum: raise AccountingConflict()
    def pairs(items):
        out={}
        for k,v in items:
            if k in out: raise AccountingConflict()
            out[k]=v
        return out
    try: return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(AccountingConflict()))
    except (ValueError,TypeError,UnicodeError,RecursionError): raise AccountingConflict() from None

def counter(value):
    names={'documentation_url','documentation_sha256','input_fields','counting_fee_bound_nano'}
    if type(value) is not dict or set(value)!=names or value['documentation_url']!=COUNT_DOCUMENTATION or value['input_fields']!=list(INPUT_FIELDS): raise AccountingConflict()
    digest(value['documentation_sha256']);integer(value['counting_fee_bound_nano'])
    if value['counting_fee_bound_nano']>28496000: raise AccountingConflict()
    return canonical(value)

@dataclass(frozen=True,repr=False)
class RuntimePolicy:
    enabled: object
    bindings_json: str
    counter_json: str
    def active(self):
        return self.enabled is True or type(self.enabled) is str and self.enabled=='true'
    def select(self,owner):
        if not self.active(): raise AccountingConflict()
        values=strict_json(self.bindings_json,16384)
        if type(values) is not dict: raise AccountingConflict()
        for k,v in values.items():
            if str(UUID(k))!=k or type(v) is not dict or set(v)!={'account_id','scope_sha256','policy_sha256'}: raise AccountingConflict()
            if type(v['account_id']) is not str or str(UUID(v['account_id']))!=v['account_id']: raise AccountingConflict()
            digest(v['scope_sha256']);digest(v['policy_sha256'])
        result=values.get(str(owner))
        if result is None: raise AccountingConflict()
        agreement=counter(strict_json(self.counter_json,16384))
        return UUID(result['account_id']),result['scope_sha256'],result['policy_sha256'],agreement

def principal_fingerprint(principal):
    return sha(canonical(dict(owner=str(principal.user_id),session=str(principal.session_id),expires=principal.expires_at.isoformat(),token_sha256=hashlib.sha256(principal.token_digest).hexdigest())))

def provider_identity(request,draft_json,semantic_json):
    """Validate transient wire bytes against stored draft/spec, without AI imports."""
    spec=strict_json(semantic_json,16384)
    required=set(INPUT_FIELDS)|{'service_tier','store','stream','max_output_tokens'}
    if type(request) is not dict or set(request)!=required: raise AccountingConflict()
    expected={'model':spec['model'],'input':[{'role':'user','content':[{'type':'input_text','text':draft_json}]}],
              'tools':[],'tool_choice':'none','parallel_tool_calls':False,'reasoning':{'effort':'none'},
              'service_tier':spec['service_tier'],'store':False,'stream':False,'max_output_tokens':spec['caps']['output_tokens']}
    for k,v in expected.items():
        # Canonical comparison distinguishes bool from integer, nested shape too.
        if wire(request[k])!=wire(v): raise AccountingConflict()
    if type(request['instructions']) is not str or sha(request['instructions'])!=spec['prompt_sha256']: raise AccountingConflict()
    form=request['text']
    if type(form) is not dict or set(form)!={'format'} or type(form['format']) is not dict: raise AccountingConflict()
    f=form['format']
    if set(f)!={'type','name','strict','schema'} or f['type']!='json_schema' or f['name']!='supervisor_meaning_v1' or f['strict'] is not True or sha(wire(f['schema']))!=spec['schema_sha256']: raise AccountingConflict()
    return sha(wire(request,65536)),sha(wire({k:request[k] for k in INPUT_FIELDS},65536))

def maximum_reserve(policy,agreement,input_tokens=None):
    c=strict_json(agreement);counter(c)
    tokens=policy.input_cap if input_tokens is None else integer(input_tokens)
    if tokens>policy.input_cap: raise AccountingConflict()
    p=strict_json(policy.price_json)
    # Ten percent regional allowance, rounded upward; no cached-token discount.
    base=tokens*p['input_nano_per_token']+policy.output_cap*p['output_nano_per_token']
    amount=(base*110+99)//100+c['counting_fee_bound_nano'];integer(amount)
    if amount>policy.attempt_nano: raise AccountingConflict()
    return amount
