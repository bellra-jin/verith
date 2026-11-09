"""Typed start → canonical tool continuation; no LLM, fallback or agent import."""
from src.supervisor.domain.models import PlanInput,PlanView,PlanWire,VERSION,POLICY,resolution_ref,selected_resolution
from src.supervisor.domain.planning.interpret import interpret
from src.supervisor.domain.planning.policy import final_status
from src.supervisor.infrastructure.backend.resolve_client import parse_resolution

def plan(value:PlanInput)->PlanWire:
    intent=interpret(value.query)
    base=dict(version=VERSION,policy_version=POLICY,request_id=value.request_id,trace_id=value.trace_id,query_sha256=value.query_sha256,requested_views=list(intent.requested_views))
    if value.phase=='start':
        if intent.should_resolve:return PlanWire(**base,kind='resolve_stock',plan=None)
        view=PlanView(version=VERSION,policy_version=POLICY,query_sha256=value.query_sha256,requested_views=list(intent.requested_views),status='unsupported' if intent.reason=='unsupported_views' else 'needs_clarification',reason=intent.reason,resolution=None,candidate_ref=None)
    else:
        if not intent.should_resolve or value.requested_views!=list(intent.requested_views):raise ValueError('Invalid continuation')
        raw=parse_resolution(value.resolution.model_dump(mode='json'))
        reference=resolution_ref(value.query,raw)
        if value.selected_ticker is not None and value.candidate_ref!=reference:raise ValueError('Invalid continuation')
        resolution=selected_resolution(raw,value.selected_ticker)
        status=final_status(resolution)
        view=PlanView(version=VERSION,policy_version=POLICY,query_sha256=value.query_sha256,requested_views=list(intent.requested_views),status=status,reason={'resolved':'stock_resolved','ambiguous':'stock_ambiguous','not_found':'stock_not_found'}[resolution.status],resolution=resolution,candidate_ref=reference)
    return PlanWire(**base,kind='final',plan=view)

def run_supervisor(*args,**kwargs):raise RuntimeError('Legacy Supervisor planning/execution unavailable')
