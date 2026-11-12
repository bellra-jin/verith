"""Default-off sync runner DI seam; no graph, config or provider construction."""
import asyncio
import copy
from datetime import date, datetime
from enum import Enum
import inspect
import math
import threading
import time

from pydantic import BaseModel
from src.shared.runtime.deadline import Deadline
from src.agents.technical.domain.boundary_contracts import WAIT_SECONDS


class EngineBridgeUnavailable(RuntimeError):
    def __init__(self):
        super().__init__('Technical engine unavailable')


def _json_value(value):
    """Serialize declared typed values; never fill or repair analysis fields."""
    if isinstance(value, BaseModel):
        return _json_value(value.model_dump(mode='python'))
    if isinstance(value, Enum):
        return _json_value(value.value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if type(value) in {str, int, bool, type(None)}:
        return value
    if type(value) is float and math.isfinite(value):
        return value
    if type(value) is list:
        return [_json_value(item) for item in value]
    if type(value) is dict and all(type(key) is str for key in value):
        return {key: _json_value(item) for key, item in value.items()}
    raise EngineBridgeUnavailable()


class TechnicalEngineBridge:
    """The caller supplies capabilities; BoundaryRuntime owns admission/HTTP wait.

    Cancellation delays this engine task's termination until its physical thread
    ends. It never delays a shielded HTTP waiter's independent timeout/cancel.
    A cooperative deadline cannot stop an unresponsive synchronous function.
    """
    def __init__(self, *, sync_runner, llm_client, fetcher, cache, trace_sink,
                 enabled=False, deadline=None, controlled=False, on_cancel=None):
        if (type(enabled) is not bool or not callable(sync_runner)
            or inspect.iscoroutinefunction(sync_runner)
            or inspect.iscoroutinefunction(getattr(sync_runner, '__call__', None))
            or llm_client is None or not callable(getattr(llm_client, 'complete', None))
            or inspect.iscoroutinefunction(getattr(llm_client, 'complete', None))
            or inspect.iscoroutinefunction(getattr(getattr(llm_client, 'complete', None), '__call__', None))
            or fetcher is None or not callable(fetcher)
            or inspect.iscoroutinefunction(fetcher)
            or inspect.iscoroutinefunction(getattr(fetcher, '__call__', None))):
            raise EngineBridgeUnavailable()
        if deadline is not None and (type(deadline) is not Deadline
            or type(deadline.expires_at) not in {int, float}
            or not math.isfinite(deadline.expires_at)):
            raise EngineBridgeUnavailable()
        if type(controlled) is not bool or controlled and deadline is None:raise EngineBridgeUnavailable()
        if on_cancel is not None and not callable(on_cancel):raise EngineBridgeUnavailable()
        self.on_cancel=on_cancel
        self.controlled=controlled
        self.enabled = enabled
        self.sync_runner = sync_runner
        self.llm_client = llm_client
        self.fetcher = fetcher
        self.cache = cache
        self.trace_sink = trace_sink
        self.deadline = deadline

    async def __call__(self, payload, *, trace_id):
        if not self.enabled or type(trace_id) is not str or not trace_id:
            raise EngineBridgeUnavailable()
        deadline = Deadline(min(math.inf if self.controlled else time.monotonic() + WAIT_SECONDS,
            self.deadline.expires_at if self.deadline is not None else math.inf))
        deadline.check('technical_bridge_snapshot')
        snapshot = copy.deepcopy(payload)
        loop = asyncio.get_running_loop()
        completed = loop.create_future()
        outcome = {}

        def notify():
            if not completed.done():
                completed.set_result(None)

        def work():
            try:
                deadline.check('technical_bridge_worker')
                value = self.sync_runner(snapshot, llm_client=self.llm_client,
                    fetcher=self.fetcher, cache=self.cache, trace_sink=self.trace_sink,
                    deadline=deadline, trace_id=trace_id)
                outcome['value'] = _json_value(value)
            except BaseException:
                outcome['failed'] = True
            finally:
                try:
                    loop.call_soon_threadsafe(notify)
                except RuntimeError:
                    # An already closed loop cannot receive a late result.
                    pass

        deadline.check('technical_bridge_dispatch')
        worker = threading.Thread(target=work, name='verith-technical-bridge', daemon=False)
        worker.start()
        cancelled = None
        while True:
            try:
                await asyncio.shield(completed)
                if not worker.is_alive():
                    break
                # Notification may run just before the thread actually returns.
                await asyncio.sleep(0)
            except asyncio.CancelledError as error:
                if cancelled is None:
                    cancelled = error
                    if self.on_cancel is not None:self.on_cancel()
        worker.join()  # is_alive() is already false; no blocking runner work here.
        if cancelled is not None:
            raise cancelled
        deadline.check('technical_bridge_result')
        if outcome.get('failed') or 'value' not in outcome:
            raise EngineBridgeUnavailable()
        return outcome['value']


def make_engine_bridge(*, sync_runner, llm_client, fetcher, cache, trace_sink,
                       enabled=False, deadline=None, controlled=False, on_cancel=None):
    return TechnicalEngineBridge(sync_runner=sync_runner, llm_client=llm_client,
        fetcher=fetcher, cache=cache, trace_sink=trace_sink,
        enabled=enabled, deadline=deadline, controlled=controlled, on_cancel=on_cancel)
