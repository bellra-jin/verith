"""Flow-only standard-price accounting. No environment, I/O, float money or SDK."""
from dataclasses import dataclass
from datetime import UTC,datetime,time,timedelta,timezone
from decimal import Decimal
import hashlib,json,re
from uuid import UUID,uuid5

MAX_INT=9223372036854775807
PRICE_ID='openai.gpt-5.4-mini.standard.2026-11-09.v1'
MODELS=('gpt-5.4-mini','gpt-5.4-mini-2026-03-17')
CALL_RESERVE=304500000
RUN_RESERVE=913500000
USAGE_SPEC={'version':'flow.usage.v1','price_id':PRICE_ID,'currency':'USD','model':'gpt-5.4-mini',
    'response_models':list(MODELS),'input_token_cap':400000,'output_token_cap':1000,'openai_call_cap':3,
    'prompt_byte_cap':32768,'output_byte_cap':16384,'input_nano':750,'cached_nano':75,'output_nano':4500,
    'kis_token_cap':2,'kis_data_cap':4,'kis_retry_in_data_cap':2,'n':1,'service_tier':'default'}
SLOTS=tuple([('openai','completion',n) for n in range(1,4)]+[('kis',action,n) for action in ('token','supply','quotes') for n in (1,2)])
NAMESPACE=UUID('c18001a7-e000-5000-8000-000000000001')


def canonical(value):return json.dumps(value,ensure_ascii=False,allow_nan=False,sort_keys=True,separators=(',',':'))
def sha(value):return hashlib.sha256(canonical(value).encode('utf8')).hexdigest()
def call_id(analysis,attempt,provider,action,ordinal):return uuid5(NAMESPACE,f'{analysis}:{attempt}:{provider}:{action}:{ordinal}')
def integer(value):return type(value) is int and 0<=value<=MAX_INT


class PolicyUnavailable(ValueError):pass
class UsageConflict(ValueError):pass


@dataclass(frozen=True)
class Policy:
    tickers:frozenset[str]
    user_limit:int
    service_limit:int
    budget:int


def policy(settings):
    """Parse only for new admission. Invalid raw values never break Settings/GET."""
    try:
        if settings.FLOW_USAGE_LIMITS_ENABLED!='true':raise ValueError()
        raw=settings.FLOW_SUPPORTED_TICKERS
        if not isinstance(raw,str):raise ValueError()
        items=[v.strip() for v in raw.split(',')]
        if not items or len(set(items))!=len(items) or any(re.fullmatch('[0-9]{6}',v) is None for v in items):raise ValueError()
        def limit(value):
            if not isinstance(value,str) or re.fullmatch('[1-9][0-9]{0,18}',value) is None:raise ValueError()
            number=int(value)
            if number>MAX_INT:raise ValueError()
            return number
        raw=settings.FLOW_SERVICE_DAILY_BUDGET_USD
        if not isinstance(raw,str) or len(raw)>30 or re.fullmatch(r'(0|[1-9][0-9]*)(\.[0-9]{1,9})?',raw) is None:raise ValueError()
        amount=int(Decimal(raw)*1000000000)
        if not 0<amount<=MAX_INT:raise ValueError()
        return Policy(frozenset(items),limit(settings.FLOW_USER_DAILY_REQUEST_LIMIT),limit(settings.FLOW_SERVICE_DAILY_REQUEST_LIMIT),amount)
    except (ValueError,TypeError,AttributeError,ArithmeticError):raise PolicyUnavailable('Flow usage policy unavailable') from None


def period(stamp):
    if not isinstance(stamp,datetime) or stamp.utcoffset() is None:raise ValueError('Invalid accounting clock')
    day=stamp.astimezone(timezone(timedelta(hours=9))).date()
    start=datetime.combine(day,time(),tzinfo=timezone(timedelta(hours=9))).astimezone(UTC)
    return start,start+timedelta(days=1)


def amount(input_tokens,cached_tokens,output_tokens):
    if not integer(input_tokens) or not integer(output_tokens):raise ValueError('Invalid usage')
    if cached_tokens is not None and (not integer(cached_tokens) or cached_tokens>input_tokens):raise ValueError('Invalid usage')
    cached=0 if cached_tokens is None else cached_tokens
    result=(input_tokens-cached)*750+cached*75+output_tokens*4500
    if result>MAX_INT:raise ValueError('Usage exceeds accounting range')
    return result


@dataclass(frozen=True)
class Evidence:
    id:UUID
    provider:str
    action:str
    ordinal:int
    attempted:bool|None
    state:str
    input_tokens:int|None
    cached_tokens:int|None
    output_tokens:int|None
    input_bytes:int|None
    output_bytes:int|None
    response_model:str|None
    model_sha256:str|None
    http_status:int|None
    estimated_nano:int|None
    reason:str
    hash:str


def receipt(row,envelope):
    """Return independent sanitized evidence, or None (full unknown hold).

    Payload/hash/date/auth/deadline publication validation is deliberately separate.
    No raw provider text, unknown model names, prompt or credentials are persisted.
    """
    try:
        raw=envelope['input_snapshot']['provider_usage']
        expected={'schema_version','analysis_id','attempt_id','admission_request_id','fingerprint','price_id','complete','calls'}
        if type(raw) is not dict or set(raw)!=expected or type(raw['schema_version']) is not int or raw['schema_version']!=1:raise ValueError()
        for key,value in (('analysis_id',row.id),('attempt_id',row.attempt_id),('admission_request_id',row.admission_request_id),('fingerprint',row.input_fingerprint)):
            if raw[key]!=str(value):raise ValueError()
        if type(raw['complete']) is not bool or type(raw['calls']) is not list or len(raw['calls'])!=9:raise ValueError()
        price_bad=raw['price_id']!=PRICE_ID
        normalized=[];seen=set()
        for call in raw['calls']:
            fields={'id','provider','action','ordinal','attempted','state','input_tokens','cached_tokens','output_tokens','input_bytes','output_bytes','response_model','http_status'}
            if type(call) is not dict or set(call)!=fields:raise ValueError()
            slot=(call['provider'],call['action'],call['ordinal'])
            if type(slot[2]) is not int or slot not in SLOTS or slot in seen:raise ValueError()
            seen.add(slot);identity=call_id(row.id,row.attempt_id,*slot)
            if call['id']!=str(identity):raise ValueError()
            attempted=call['attempted'];state=call['state']
            if attempted is not None and type(attempted) is not bool:raise ValueError()
            if state not in {'unknown','observed','not_called'}:raise ValueError()
            inp,cached,out=(call[k] for k in ('input_tokens','cached_tokens','output_tokens'))
            ib,ob=call['input_bytes'],call['output_bytes'];model=call['response_model'];http=call['http_status']
            model_hash=hashlib.sha256(model.encode('utf8')).hexdigest() if isinstance(model,str) else None
            safe_model=model if model in MODELS else None
            reason='UNOBSERVED';estimate=None;final='unknown'
            # Preserve independently well-typed numbers even for anomalous receipts.
            inp=inp if integer(inp) else None;cached=cached if integer(cached) and inp is not None and cached<=inp else None;out=out if integer(out) else None
            ib=ib if integer(ib) else None;ob=ob if integer(ob) else None
            http=http if type(http) is int and 100<=http<=599 else None
            if state=='not_called':
                if attempted is not False or not raw['complete'] or any(call[k] is not None for k in fields-{'id','provider','action','ordinal','attempted','state'}):raise ValueError()
                final='not_called';reason='NOT_CALLED';estimate=0 if slot[0]=='openai' else None
            elif state=='observed' and attempted is True:
                if slot[0]=='kis':
                    if http is not None and all(call[k] is None for k in ('input_tokens','cached_tokens','output_tokens','response_model')):
                        final='observed';reason='HTTP_OBSERVED'
                else:
                    valid=(inp is not None and out is not None and
                        (call['cached_tokens'] is None or cached is not None and cached<=inp))
                    if valid:
                        if isinstance(model,str) and safe_model is None:
                            final='anomalous';reason='MODEL_MISMATCH'
                        elif safe_model is not None:
                            try:estimate=amount(inp,cached,out)
                            except ValueError:final='anomalous';reason='ACCOUNTING_OVERFLOW'
                            else:
                                final='observed';reason='CACHE_UNREPORTED' if cached is None else 'USAGE_OBSERVED'
                                if inp>400000 or out>1000 or ib is not None and ib>32768 or ob is not None and ob>16384:
                                    final='anomalous';reason='CAP_EXCEEDED'
                    if final=='unknown':reason='USAGE_INVALID'
            elif attempted is False:raise ValueError()
            if attempted is True:
                # Anomalies do not depend on a complete/chargeable usage record.
                counts={k:call[k] for k in ('input_tokens','cached_tokens','output_tokens','input_bytes','output_bytes')}
                overflow=any(type(v) is int and v>MAX_INT for v in counts.values())
                exceeded=any(type(call[k]) is int and call[k]>cap for k,cap in
                    (('input_tokens',400000),('output_tokens',1000),('input_bytes',32768),('output_bytes',16384)))
                if exceeded:final='anomalous';reason='CAP_EXCEEDED'
                if overflow:final='anomalous';reason='ACCOUNTING_OVERFLOW';estimate=None
                if isinstance(model,str) and safe_model is None:final='anomalous';reason='MODEL_MISMATCH';estimate=None
            if price_bad:
                final='anomalous';reason='PRICE_MISMATCH';estimate=None
            values=dict(id=str(identity),provider=slot[0],action=slot[1],ordinal=slot[2],attempted=attempted,state=final,
                input_tokens=inp,cached_tokens=cached,output_tokens=out,input_bytes=ib,output_bytes=ob,
                response_model=safe_model,model_sha256=model_hash,http_status=http,estimated_nano=estimate,reason=reason)
            overflow_hashes={k:hashlib.sha256(str(call[k]).encode()).hexdigest() for k in ('input_tokens','cached_tokens','output_tokens','input_bytes','output_bytes') if type(call[k]) is int and call[k]>MAX_INT}
            normalized.append(Evidence(**(values|{'id':identity,'hash':sha(values|{'overflow_hashes':overflow_hashes})})))
        return tuple(normalized)
    except (ValueError,TypeError,KeyError,AttributeError,UnicodeError,RecursionError):return None


def valid_complete_usage(row,envelope):
    result=receipt(row,envelope)
    return result is not None and all(c.state!='anomalous' for c in result)
