"""Owned financial execution binding. Request context is not source financial data."""
from datetime import UTC,datetime
from uuid import UUID
from src.modules.analysis.domain.contracts import canonical_json,strict_json,json_hash,AnalysisContractError
from src.modules.fundamental.domain.ai_output import FundamentalAgentOutputMirror

OPERATION='fundamental.analysis.v1'
SPEC={'engine':'fundamental.public.v1','input_schema':'fundamental.request-context.v1',
      'result_schema':'fundamental.agent-output.v1','as_of_semantics':'request_time_only',
      'deadline_seconds':60,'http_timeout_seconds':65,'bff_timeout_seconds':70,'dispatch_retries':0}
canonical=canonical_json
decode=strict_json
sha=json_hash


def input_request(row):
    value=decode(row.request_json)
    if sha(canonical(value))!=row.input_fingerprint or set(value)!={'ticker','question'}:raise AnalysisContractError()
    return value


def ai_request(row):
    value=input_request(row)
    return dict(schema_version=1,analysis_id=str(row.id),admission_request_id=str(row.admission_request_id),
        attempt_id=str(row.attempt_id),fingerprint=row.input_fingerprint,
        requested_at=row.as_of.astimezone(UTC).isoformat(),deadline_at=row.deadline_at.astimezone(UTC).isoformat(),
        spec=decode(row.spec_json),request=dict(request_id='req-'+row.admission_request_id.hex,
        trace_id='trace-'+row.attempt_id.hex,ticker=row.ticker,query=value['question']))


def validate_output(value,request):
    raw=decode(canonical(value))
    FundamentalAgentOutputMirror.model_validate(raw) # Shape only; never snapshot model_dump.
    if (raw.get('request_id')!=request['request_id'] or raw.get('ticker')!=request['ticker']
            or raw['meta'].get('trace_id')!=request['trace_id']):raise AnalysisContractError()
    if type(raw.get('score')) is not int or type(raw.get('confidence')) not in (int,float):raise AnalysisContractError()
    erd=raw['meta']['erd_payload'];root=erd['fundamental_report'];rid=UUID(root['id'])
    if root.get('stock_code')!=request['ticker']:raise AnalysisContractError()
    if root.get('as_of') is not None:
        if type(root['as_of']) is not str:raise AnalysisContractError()
        stamp=datetime.fromisoformat(root['as_of'])
        if stamp.tzinfo is None or stamp.utcoffset() is None:raise AnalysisContractError()
    for field,key in (('request_id','request_id'),('trace_id','trace_id')):
        if root.get(field) is not None and root[field]!=request[key]:raise AnalysisContractError()
    ratio_ids=set()
    for name in ('report_ratios','report_evidence','report_interpretation','report_verification','report_insights','report_filing_snippets'):
        rows=[erd.get(name)] if name in {'report_interpretation','report_verification'} else erd.get(name,[])
        if type(rows) is not list:raise AnalysisContractError()
        ids=set()
        for item in rows:
            if type(item) is not dict or UUID(item['report_id'])!=rid:raise AnalysisContractError()
            identifier=UUID(item['id'])
            if identifier in ids:raise AnalysisContractError()
            ids.add(identifier)
        if name=='report_ratios':ratio_ids=ids
    for evidence in erd.get('report_evidence',[]):
        if evidence.get('ratio_id') is not None and UUID(evidence['ratio_id']) not in ratio_ids:raise AnalysisContractError()
    return rid,raw


def validate_response(row,response):
    try:
        wire=ai_request(row)
        if (type(response) is not dict or set(response)!={'schema_version','analysis_id','admission_request_id','attempt_id','fingerprint','report_id','input_snapshot','input_sha256','output'}
                or type(response['schema_version']) is not int or response['schema_version']!=1):raise AnalysisContractError()
        for key in ('analysis_id','admission_request_id','attempt_id','fingerprint'):
            if response[key]!=wire[key]:raise AnalysisContractError()
        snapshot=response['input_snapshot']
        expected={'schema_version':1,'kind':'fundamental.request-context.v1','request':wire}
        if canonical(snapshot)!=canonical(expected) or response['input_sha256']!=sha(canonical(snapshot)):raise AnalysisContractError()
        rid,raw=validate_output(response['output'],wire['request'])
        if str(rid)!=response['report_id']:raise AnalysisContractError()
        a,b=canonical(snapshot),canonical(raw)
        if max(len(a.encode()),len(b.encode()))>2097152:raise AnalysisContractError()
        return rid,a,b
    except (ValueError,TypeError,KeyError,AttributeError,RecursionError):raise AnalysisContractError() from None


def stored_response(row):
    if sha(row.input_json)!=row.input_sha256 or sha(row.result_json)!=row.result_sha256:raise AnalysisContractError()
    return dict(schema_version=1,analysis_id=str(row.id),admission_request_id=str(row.admission_request_id),
        attempt_id=str(row.attempt_id),fingerprint=row.input_fingerprint,report_id=str(row.adopted_report_id),
        input_snapshot=decode(row.input_json),input_sha256=row.input_sha256,output=decode(row.result_json))
