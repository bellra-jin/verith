"""Cooperative live context and one real sync-job slot; no eager graph import."""
import asyncio
from datetime import UTC,datetime
import math
import os
import threading
import hashlib
from pathlib import Path
from ..api.schemas import canonical,sha,UNITS
from src.shared.runtime.deadline import Deadline,DeadlineExceeded

_SLOT=threading.BoundedSemaphore(1)


class EngineUnavailable(RuntimeError):pass


class ExecutionContext:
    def __init__(self,request):
        self.request=request
        self.deadline=Deadline.after(min(120,(request.deadline_at-datetime.now(UTC)).total_seconds()))
        self.cancelled=threading.Event();self.calls={};self.captured=None

    def check(self,stage):
        if self.cancelled.is_set():raise DeadlineExceeded('Flow response no longer awaited')
        self.deadline.check(stage)

    def timeout(self,stage,maximum=20):
        self.check(stage);self.calls[stage]=self.calls.get(stage,0)+1
        return min(20,maximum,self.deadline.remaining_seconds())

    def wait_allowed(self,seconds):
        self.check('kis_rate_wait')
        if self.deadline.remaining_seconds()<=seconds:raise DeadlineExceeded('Insufficient retry budget')

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
                    payload,snapshot=result['payload'],result['input_snapshot']
                else:
                    # Only after exact route gate + service token + engine gate.
                    from .. import config
                    if (config.INTERPRETER_MODEL!=request.spec['model'] or config.INTERPRETER_PROVIDER!=request.spec['provider'] or config.MAX_EXPLAIN_RETRIES!=request.spec['explain_regenerations']):raise EngineUnavailable()
                    if hashlib.sha256(Path(config.__file__).read_bytes()).hexdigest()!=request.spec['config_sha256'] or hashlib.sha256((Path(config.__file__).parent/'prompts/explain.txt').read_bytes()).hexdigest()!=request.spec['prompt_sha256']:raise EngineUnavailable()
                    if (request.spec['policy']!='flow.fact-selection.v1' or hashlib.sha256((Path(config.__file__).parent/'domain/interpretation_claims.py').read_bytes()).hexdigest()!=request.spec['policy_sha256']):raise EngineUnavailable()
                    from .agent import run
                    value=run(query=request.question,stock_name=request.stock_name,ticker=request.ticker,
                              base_date=request.candidate_date,execution_context=context)
                    payload,snapshot=value.payload,context.captured
                    if snapshot is None:raise ValueError('Input observations missing')
                    snapshot={**snapshot,'observed_calls':dict(context.calls)}
                context.check('export')
                if snapshot.get('request')!=request.wire():raise ValueError('Input binding mismatch')
                value={'schema_version':1,'analysis_id':str(request.analysis_id),'attempt_id':str(request.attempt_id),
                    'admission_request_id':str(request.admission_request_id),'fingerprint':request.fingerprint,
                    'report_id':payload['report_id'],'input_snapshot':snapshot,'input_sha256':sha(snapshot),'payload':payload}
                if len(canonical(value).encode())>2097152:raise ValueError('Flow result too large')
                return value
            finally:_SLOT.release() # Slot is released by actual sync completion, never response timeout.
        try:future=asyncio.get_running_loop().run_in_executor(None,work)
        except BaseException:_SLOT.release();raise
        def consume(value):
            if not value.cancelled():value.exception()
        future.add_done_callback(consume)
        try:return await asyncio.wait_for(asyncio.shield(future),timeout=context.deadline.remaining_seconds())
        except (asyncio.TimeoutError,asyncio.CancelledError):
            context.cancelled.set();raise
