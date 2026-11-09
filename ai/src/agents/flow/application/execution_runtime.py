"""Cooperative live context and one real sync-job slot; no eager graph import."""
import asyncio
from datetime import UTC,datetime
import math
import os
import threading
import hashlib
from pathlib import Path
from ..api.schemas import canonical,sha,UNITS,USAGE_SPEC
from uuid import UUID,uuid5
from src.shared.runtime.deadline import Deadline,DeadlineExceeded

_SLOT=threading.BoundedSemaphore(1)


class EngineUnavailable(RuntimeError):pass


class ResultContractError(RuntimeError):pass


class ExecutionContext:
    def __init__(self,request):
        self.request=request
        self.deadline=Deadline.after(min(120,(request.deadline_at-datetime.now(UTC)).total_seconds()))
        self.cancelled=threading.Event();self.calls={};self.captured=None
        self._usage=[]
        for provider,action,ordinal in ([('openai','completion',n) for n in range(1,4)]+[('kis',a,n) for a in ('token','supply','quotes') for n in (1,2)]):
            identity=uuid5(UUID('c18001a7-e000-5000-8000-000000000001'),f'{request.analysis_id}:{request.attempt_id}:{provider}:{action}:{ordinal}')
            self._usage.append(dict(id=str(identity),provider=provider,action=action,ordinal=ordinal,attempted=None,state='unknown',
                input_tokens=None,cached_tokens=None,output_tokens=None,input_bytes=None,output_bytes=None,response_model=None,http_status=None))

    def check(self,stage):
        if self.cancelled.is_set():raise DeadlineExceeded('Flow response no longer awaited')
        self.deadline.check(stage)

    def timeout(self,stage,maximum=20):
        self.check(stage);self.calls[stage]=self.calls.get(stage,0)+1
        return min(20,maximum,self.deadline.remaining_seconds())

    def wait_allowed(self,seconds):
        self.check('kis_rate_wait')
        if self.deadline.remaining_seconds()<=seconds:raise DeadlineExceeded('Insufficient retry budget')

    def begin_call(self,provider,action,*,input_bytes=None):
        self.check('provider_dispatch')
        slots=[c for c in self._usage if c['provider']==provider and c['action']==action]
        slot=next((c for c in slots if c['attempted'] is None),None)
        if slot is None:raise EngineUnavailable('Provider call cap exceeded')
        slot['attempted']=True;slot['input_bytes']=input_bytes
        return slot['id']

    def http_observed(self,identity,status):
        slot=next(c for c in self._usage if c['id']==identity)
        if type(status) is int and 100<=status<=599:slot.update(state='observed',http_status=status)

    def openai_observed(self,identity,response):
        slot=next(c for c in self._usage if c['id']==identity)
        metadata=getattr(response,'response_metadata',None)
        metadata=metadata if type(metadata) is dict else {}
        usage=getattr(response,'usage_metadata',None)
        native=usage is None
        if native:usage=metadata.get('token_usage')
        usage=usage if type(usage) is dict else {}
        inp=usage.get('prompt_tokens' if native else 'input_tokens')
        out=usage.get('completion_tokens' if native else 'output_tokens')
        details=usage.get('prompt_tokens_details' if native else 'input_token_details')
        cached=details.get('cached_tokens' if native else 'cache_read') if type(details) is dict else None
        total=usage.get('total_tokens')
        valid_number=lambda v:type(v) is int and 0<=v<=9223372036854775807
        valid=((details is None or type(details) is dict) and valid_number(inp) and valid_number(out) and (cached is None or valid_number(cached) and cached<=inp)
            and (total is None or valid_number(total) and total==inp+out))
        observed_number=lambda v:type(v) is int and v>=0
        slot.update(input_tokens=inp if observed_number(inp) else None,output_tokens=out if observed_number(out) else None,
            cached_tokens=cached if valid_number(cached) and valid_number(inp) and cached<=inp else None)
        model=metadata.get('model_name',metadata.get('model'))
        if isinstance(model,str):
            try:model=model if model in USAGE_SPEC['response_models'] else 'sha256:'+hashlib.sha256(model.encode('utf8')).hexdigest()
            except UnicodeError:model=None
        else:model=None
        slot['response_model']=model
        # Keep chargeability separate: malformed usage stays unknown, while the
        # model digest/observable counts survive for Backend's independent block.
        if valid and model is not None:slot['state']='observed'

    def output_observed(self,identity,size):
        slot=next(c for c in self._usage if c['id']==identity);slot['output_bytes']=size

    def final_usage(self):
        # Called only after the actual synchronous engine returned, never on timeout.
        for slot in self._usage:
            if slot['attempted'] is None:slot.update(attempted=False,state='not_called')
        return dict(schema_version=1,analysis_id=str(self.request.analysis_id),attempt_id=str(self.request.attempt_id),
            admission_request_id=str(self.request.admission_request_id),fingerprint=self.request.fingerprint,
            price_id=USAGE_SPEC['price_id'],complete=True,calls=[dict(c) for c in self._usage])

    def capture(self,supply,quotes,ownership,confirmed):
        self.check('capture')
        def number(value):
            if value is None:return None
            if hasattr(value,'item'):value=value.item()
            if type(value) not in {int,float}:raise ValueError('Invalid observation')
            if isinstance(value,float) and math.isnan(value):return None
            if not math.isfinite(value):raise ValueError('Nonfinite observation')
            return value
        def day(value):
            return value.date().isoformat() if hasattr(value,'date') else value.isoformat()
        def records(frame):
            if frame is None:return None
            if hasattr(frame,'columns'):
                # iterrows coerces mixed rows to float and can lose integer bits.
                return [dict(date=day(row[0]),**{str(k):number(v) for k,v in zip(frame.columns,row[1:])})
                        for row in frame.itertuples(index=True,name=None)]
            return [{'date':day(index),'value':number(value)} for index,value in frame.items()]
        self.captured={'schema_version':1,'request':self.request.wire(),'source':'kis.boundary.frames.v1',
            'observed_at':datetime.now(UTC).isoformat(),'confirmed_date':confirmed.isoformat(),
            'units':UNITS,
            'frames':{'supply':records(supply),'quotes':records(quotes),'ownership':records(ownership)}}


class FlowExecutionRuntime:
    def __init__(self,engine=None):self.engine=engine

    async def run(self,request):
        if self.engine is None and os.getenv('FLOW_ENGINE_EXECUTION_ENABLED')!='true':raise EngineUnavailable()
        context=ExecutionContext(request);context.check('dispatch')
        if not _SLOT.acquire(blocking=False):raise EngineUnavailable()
        def work():
            try:
                context.check('engine')
                if self.engine is not None:
                    result=self.engine(request,context)

                else:
                    # Only after exact route gate + service token + engine gate.
                    from .. import config
                    if (config.INTERPRETER_MODEL!=request.spec['model'] or config.INTERPRETER_PROVIDER!=request.spec['provider'] or config.MAX_EXPLAIN_RETRIES!=request.spec['explain_regenerations']):raise EngineUnavailable()
                    if hashlib.sha256(Path(config.__file__).read_bytes()).hexdigest()!=request.spec['config_sha256'] or hashlib.sha256((Path(config.__file__).parent/'prompts/explain.txt').read_bytes()).hexdigest()!=request.spec['prompt_sha256']:raise EngineUnavailable()
                    if (request.spec['policy']!='flow.fact-selection.v1' or hashlib.sha256((Path(config.__file__).parent/'domain/interpretation_claims.py').read_bytes()).hexdigest()!=request.spec['policy_sha256']):raise EngineUnavailable()
                    from .agent import run
                    value=run(query=request.question,stock_name=request.stock_name,ticker=request.ticker,
                              base_date=request.candidate_date,execution_context=context)
                provider_usage=context.final_usage()
                context.check('export')
                # Provider invocation is outside this result-only boundary.
                try:
                    if self.engine is not None:
                        payload,snapshot=result['payload'],result['input_snapshot']
                    else:
                        payload,snapshot=value.payload,context.captured
                        if snapshot is None:raise ValueError()
                        snapshot={**snapshot,'observed_calls':dict(context.calls)}
                    if not isinstance(payload,dict) or not isinstance(snapshot,dict):raise ValueError()
                    if snapshot.get('request')!=request.wire():raise ValueError()
                    snapshot={**snapshot,'provider_usage':provider_usage}
                    value={'schema_version':1,'analysis_id':str(request.analysis_id),'attempt_id':str(request.attempt_id),
                        'admission_request_id':str(request.admission_request_id),'fingerprint':request.fingerprint,
                        'report_id':payload['report_id'],'input_snapshot':snapshot,'input_sha256':sha(snapshot),'payload':payload}
                    if len(canonical(value).encode('utf8'))>2097152:raise ValueError()
                    return value
                except (ValueError,TypeError,KeyError,AttributeError,OverflowError,RecursionError):
                    raise ResultContractError('Flow result is invalid') from None
            finally:_SLOT.release() # Slot is released by actual sync completion, never response timeout.
        try:future=asyncio.get_running_loop().run_in_executor(None,work)
        except BaseException:_SLOT.release();raise
        def consume(value):
            if not value.cancelled():value.exception()
        future.add_done_callback(consume)
        try:return await asyncio.wait_for(asyncio.shield(future),timeout=context.deadline.remaining_seconds())
        except (asyncio.TimeoutError,asyncio.CancelledError):
            context.cancelled.set();raise
