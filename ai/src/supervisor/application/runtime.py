"""Planning-only assembly. Legacy execution cannot import or dispatch adapters."""
from src.supervisor.application.planning.planner import plan

class SupervisorExecutionUnavailable(RuntimeError):pass

def run_analysis(*args,**kwargs):
    raise SupervisorExecutionUnavailable('Supervisor execution unavailable')

def run_plan(value):return plan(value)

def to_response_dict(*args,**kwargs):
    raise SupervisorExecutionUnavailable('Supervisor execution unavailable')

async def run_core(value,*,gateway=None):
    from src.supervisor.application.planning.core_planner import start,continuation
    if value.phase=='start':
        if value.frame is not None or value.resolution is not None:raise ValueError('Invalid core phase')
        return await start(value.draft,gateway)
    if value.frame is None or value.resolution is None:raise ValueError('Invalid core phase')
    return continuation(value.draft,value.frame,value.resolution)
