"""One owned worker at a time. HTTP timeout never releases a running worker."""
import asyncio
from concurrent.futures import Future
from datetime import UTC,datetime
import inspect,os,threading
from uuid import UUID
from .analysis_schemas import canonical,sha

_SLOT=threading.BoundedSemaphore(1)
_WORKERS=set()
_WORKERS_LOCK=threading.Lock()


class FundamentalUnavailable(RuntimeError):pass
class FundamentalEngineFailure(RuntimeError):pass
class FundamentalResultInvalid(RuntimeError):pass


class FundamentalRuntime:
    def __init__(self,engine=None):self.engine=engine

    async def run(self,request):
        if self.engine is None and os.getenv('FUNDAMENTAL_ENGINE_EXECUTION_ENABLED')!='true':raise FundamentalUnavailable()
        remaining=min(60,(request.deadline_at-datetime.now(UTC)).total_seconds())
        if remaining<=0:raise TimeoutError()
        if not _SLOT.acquire(blocking=False):raise FundamentalUnavailable()
        completed=Future()
        def work():
            value=None;failure=None
            try:
                if self.engine is None:
                    from ..application.agent import analyze_fundamental_public
                    result=analyze_fundamental_public(request.request)
                else:result=self.engine(request)
                if inspect.isawaitable(result):
                    async def await_result():
                        try:return await result
                        finally:
                            # Never infer completion from asyncio.run's bounded
                            # default-executor shutdown timeout.
                            await asyncio.get_running_loop().shutdown_default_executor(timeout=None)
                    # Includes actual shutdown of this loop's default executor.
                    result=asyncio.run(await_result())
            except BaseException:
                failure=FundamentalEngineFailure('Financial engine unavailable')
            else:
                try:
                    if hasattr(result,'model_dump'):result=result.model_dump(mode='json')
                    if type(result) is not dict:raise ValueError()
                    report_id=str(UUID(result['meta']['erd_payload']['fundamental_report']['id']))
                    wire=request.wire()
                    snapshot=dict(schema_version=1,kind='fundamental.request-context.v1',request=wire)
                    value=dict(schema_version=1,**{k:wire[k] for k in ('analysis_id','admission_request_id','attempt_id','fingerprint')},
                        report_id=report_id,input_snapshot=snapshot,input_sha256=sha(snapshot),output=result)
                    if len(canonical(value).encode('utf8'))>2097152:raise ValueError()
                except BaseException:
                    failure=FundamentalResultInvalid('Financial result invalid')
            finally:
                # Actual engine/executor completion precedes release. HTTP await
                # cancellation cannot complete this worker or free its slot.
                with _WORKERS_LOCK:_WORKERS.discard(threading.current_thread())
                _SLOT.release()
            if failure is not None:completed.set_exception(failure)
            else:completed.set_result(value)
        worker=threading.Thread(target=work,name='fundamental-owned-worker',daemon=True)
        with _WORKERS_LOCK:_WORKERS.add(worker)
        try:worker.start()
        except BaseException:
            with _WORKERS_LOCK:_WORKERS.discard(worker)
            _SLOT.release();raise
        future=asyncio.wrap_future(completed)
        def consume(value):
            if not value.cancelled():value.exception()
        future.add_done_callback(consume)
        return await asyncio.wait_for(asyncio.shield(future),timeout=remaining)
