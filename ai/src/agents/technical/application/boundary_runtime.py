"""Injected async engine only. An outstanding task retains its slot after timeout."""
import asyncio,copy,math
from typing import Protocol
from src.agents.technical.domain.boundary_contracts import WAIT_SECONDS
from src.agents.technical.application.boundary_adapter import project_input,complete
class AsyncTechnicalEngine(Protocol):
    async def __call__(self,payload,*,trace_id:str)->dict:...
class BoundaryBusy(RuntimeError):pass
class BoundaryTimeout(RuntimeError):pass
class BoundaryEngineFailure(RuntimeError):pass
_ACTIVE_TASK=None
class BoundaryRuntime:
    def __init__(self,engine:AsyncTechnicalEngine,*,timeout=WAIT_SECONDS):
        if type(timeout) not in {int,float} or not math.isfinite(timeout) or timeout<=0:raise ValueError('Invalid boundary deadline')
        self.engine=engine;self.timeout=min(timeout,WAIT_SECONDS)
    async def run(self,request,*,remaining=None):
        global _ACTIVE_TASK
        if remaining is not None and (type(remaining) not in {int,float} or not math.isfinite(remaining) or remaining<=0):
            raise BoundaryTimeout('Technical boundary unavailable')
        loop=asyncio.get_running_loop()
        deadline=loop.time()+min(self.timeout,self.timeout if remaining is None else remaining)
        if _ACTIVE_TASK is not None:raise BoundaryBusy('Technical boundary unavailable')
        request=copy.deepcopy(request);payload=project_input(request)
        # Input validation/projection is part of the caller's remaining wait budget.
        # Refuse before scheduling an engine or occupying the process slot.
        wait_remaining=deadline-loop.time()
        if wait_remaining<=0:raise BoundaryTimeout('Technical boundary unavailable')
        async def work():
            try:return complete(request,await self.engine(payload,trace_id=request['trace_id']))
            except Exception:raise BoundaryEngineFailure('Technical boundary unavailable') from None
        task=asyncio.create_task(work());_ACTIVE_TASK=task
        def finished(done):
            global _ACTIVE_TASK
            try:done.exception()
            except asyncio.CancelledError:pass
            if _ACTIVE_TASK is done:_ACTIVE_TASK=None
        task.add_done_callback(finished)
        try:return await asyncio.wait_for(asyncio.shield(task),wait_remaining)
        except TimeoutError:raise BoundaryTimeout('Technical boundary unavailable') from None
