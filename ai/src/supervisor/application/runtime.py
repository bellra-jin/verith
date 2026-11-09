"""Planning-only assembly. Legacy execution cannot import or dispatch adapters."""
from src.supervisor.application.planning.planner import plan

class SupervisorExecutionUnavailable(RuntimeError):pass

def run_analysis(*args,**kwargs):
    raise SupervisorExecutionUnavailable('Supervisor execution unavailable')

def run_plan(value):return plan(value)

def to_response_dict(*args,**kwargs):
    raise SupervisorExecutionUnavailable('Supervisor execution unavailable')
