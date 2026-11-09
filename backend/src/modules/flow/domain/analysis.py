"""Live analysis ledger rules; no engine, environment or persistence imports."""
from datetime import UTC, date, datetime, timedelta
import hashlib
import json
import math
from datetime import timezone
from uuid import UUID
from src.modules.flow.domain.execution import ContractViolation, ErrorCode, ExecutionContext, bind_flow_result

from src.modules.analysis.domain.usage import USAGE_SPEC,valid_complete_usage

OPERATION = 'flow.analysis.v1'
SPEC = {'engine': 'flow.graph.v1', 'model': 'gpt-5.4-mini', 'provider': 'openai', 'payload_schema': 1, 'input_schema': 1, 'prompt': 'flow.explain.fact-selection.v1', 'prompt_sha256': '9e8a04b6d7d0f534d54552e78ed489cb74f3cc7160fbd379b030758ae891406c', 'config_sha256': '91c95356110d0294051eb7871bfb06100ebd003ccb0f2da33c6add2b0594b637', 'config': 'flow.analysis.fact-selection.v1', 'deadline_seconds': 120, 'provider_timeout_seconds': 20, 'sdk_retries': 0, 'dispatch_retries': 0, 'explain_regenerations': 2, 'max_completion_tokens': 1000, 'policy': 'flow.fact-selection.v1', 'policy_sha256': '4cf9fa103736cc5c852eb96cbb1f42253ad875f89bccf3dcd47a43bb76f6fd22'}
LEGACY_SPEC=dict(SPEC)
SPEC={**SPEC,'usage':USAGE_SPEC}

UNITS = {'supply': {'date': 'ISO8601-date', '개인': 'million_KRW', '외국인': 'million_KRW', '기관': 'million_KRW', '거래대금': 'million_KRW', '증권': 'million_KRW', '투자신탁': 'million_KRW', '사모펀드': 'million_KRW', '은행': 'million_KRW', '보험': 'million_KRW', '종금': 'million_KRW', '기금': 'million_KRW', '외국인순매매량': 'share', '기관순매매량': 'share'}, 'quotes': {'date': 'ISO8601-date', '종가': 'KRW', '전일비': 'KRW', '등락률': 'percent', '거래량': 'share', '외국인한도소진율': 'percent'}, 'ownership': {'date': 'ISO8601-date', 'value': 'percent'}}
STATES = frozenset({'running','result_ready','stored','failed','unknown','deleted'})


def canonical(value):
    return json.dumps(value,ensure_ascii=False,allow_nan=False,sort_keys=True,separators=(',',':'))


def sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


def decode(value):
    def pairs(items):
        result={}
        for k,v in items:
            if k in result:raise ValueError('duplicate')
            result[k]=v
        return result
    return json.loads(value,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('finite JSON required')))


def candidate(as_of):
    local=as_of.astimezone(timezone(timedelta(hours=9)))
    return local.date() if local.hour>=18 else local.date()-timedelta(days=1)


def input_request(row):
    value=decode(row.request_json)
    if sha(canonical(value))!=row.input_fingerprint:raise ContractViolation(ErrorCode.RESULT_CONTRACT_INVALID)
    return value


def ai_request(row):
    request=input_request(row)
    return {'schema_version':1,'analysis_id':str(row.id),'attempt_id':str(row.attempt_id),
        'admission_request_id':str(row.admission_request_id),'fingerprint':row.input_fingerprint,
        'ticker':row.ticker,'stock_name':row.stock_name,'question':request['question'],
        'as_of':request['as_of'],'candidate_date':row.candidate_date.isoformat(),
        'deadline_at':row.deadline_at.astimezone(UTC).isoformat(),'spec':decode(row.spec_json)}


def validate_response(row,response,owner):
    """Bind the original v1 payload and real captured inputs; never repair values."""
    try:
        request=ai_request(row)
        keys={'schema_version','analysis_id','attempt_id','admission_request_id','fingerprint','report_id','input_snapshot','input_sha256','payload'}
        if not isinstance(response,dict) or set(response)!=keys or type(response['schema_version']) is not int or response['schema_version']!=1:raise ValueError()
        for k in ('analysis_id','attempt_id','admission_request_id','fingerprint'):
            if response[k]!=request[k]:raise ValueError()
        snapshot=response['input_snapshot'];payload=response['payload']
        if 'usage' in request['spec'] and (request['spec']['usage']!=USAGE_SPEC or not valid_complete_usage(row,response)):raise ValueError()
        if not isinstance(snapshot,dict) or snapshot.get('schema_version')!=1 or type(snapshot.get('schema_version')) is not int:raise ValueError()
        if snapshot.get('request')!=request or snapshot.get('source')!='kis.boundary.frames.v1':raise ValueError()
        if sha(canonical(snapshot))!=response['input_sha256']:raise ValueError()
        if snapshot.get('units')!=UNITS:raise ValueError()
        confirmed=date.fromisoformat(snapshot['confirmed_date'])
        if confirmed>row.candidate_date or payload['meta']['base_date']!=confirmed.isoformat():raise ValueError()
        observed=datetime.fromisoformat(snapshot['observed_at'])
        if observed.utcoffset() is None:raise ValueError()
        frames=snapshot['frames']
        if set(frames)!={'supply','quotes','ownership'} or not isinstance(frames['supply'],list) or not frames['supply']:raise ValueError()
        for name,rows in frames.items():
            if rows is None and name in {'quotes','ownership'}:continue
            if not isinstance(rows,list) or not rows:raise ValueError()
            dates=[date.fromisoformat(v['date']) for v in rows]
            if dates!=sorted(set(dates)) or dates[-1]!=confirmed:raise ValueError()
            required={'supply':{'개인','외국인','기관','거래대금','외국인순매매량','기관순매매량',
                              '증권','투자신탁','사모펀드','은행','보험','종금','기금'},
                      'quotes':{'종가','전일비','등락률','거래량','외국인한도소진율'},'ownership':{'value'}}[name]
            for record in rows:
                if set(record)!=set(UNITS[name]) or not required<=record.keys():raise ValueError()
                for key,value in record.items():
                    if key=='date':continue
                    if value is None:
                        if name=='supply' and key in {'개인','외국인','기관','거래대금','외국인순매매량','기관순매매량'}:raise ValueError()
                    elif type(value) not in {int,float} or not math.isfinite(value):raise ValueError()
        if payload['meta']['ticker']!=row.ticker or payload['meta']['stock_name']!=row.stock_name:raise ValueError()
        daily=payload['signals'].get('daily')
        if not isinstance(daily,list) or not daily or daily[-1]['date']!=confirmed.isoformat():raise ValueError()
        if [v['date'] for v in daily]!=sorted(set(v['date'] for v in daily)):raise ValueError()
        if not {v['date'] for v in daily}<={v['date'] for v in frames['supply']}:raise ValueError()
        if any(date.fromisoformat(v['date'])>confirmed for v in daily):raise ValueError()
        gates=payload['verification']
        if not isinstance(gates.get('gate2'),dict) or gates['gate2'].get('passed') is not True:raise ValueError()
        if payload['report_id']!=response['report_id']:raise ValueError()
        ref=bind_flow_result(ExecutionContext(request_id=row.admission_request_id,run_id=row.id,
            attempt_id=row.attempt_id,owner_user_id=owner),payload)
        return ref,canonical(snapshot),canonical(payload)
    except Exception:
        raise ContractViolation(ErrorCode.RESULT_CONTRACT_INVALID) from None


def stored_response(row):
    payload=decode(row.result_json);snapshot=decode(row.input_json)
    if sha(row.input_json)!=row.input_sha256 or sha(row.result_json)!=row.result_sha256:raise ContractViolation(ErrorCode.RESULT_CONTRACT_INVALID)
    return {'schema_version':1,'analysis_id':str(row.id),'attempt_id':str(row.attempt_id),
        'admission_request_id':str(row.admission_request_id),'fingerprint':row.input_fingerprint,
        'report_id':str(row.adopted_report_id),'input_snapshot':snapshot,'input_sha256':row.input_sha256,'payload':payload}
