"""Explicit scope consent -> original Flow body; no new execution fingerprint."""
from src.modules.supervisor.domain.contracts import CoreInvalid, Outcome, Plan, decode
from src.modules.flow.api.analysis_schemas import AnalysisRequest

def confirmed_plan(plan, consent):
    if plan.status not in {'ready', 'scope_confirmation'} or plan.selected_views != ['flow'] or plan.resolution is None or (plan.resolution.stock is None) or (consent.allow_flow is not True):
        raise CoreInvalid()
    if plan.partial and (not consent.allow_partial) or sorted(consent.waived_conditions) != sorted(plan.required_waivers):
        raise CoreInvalid()
    result = plan.model_dump(mode='json')
    result['effective_scope'] = {'selected_views': ['flow'], 'fixed_observation_window': True, 'all_subjects_retained': True, 'waived_conditions': list(consent.waived_conditions), 'partial_consent': consent.allow_partial}
    return result

def flow_body(plan, id, stamp):
    return AnalysisRequest(ticker=plan.resolution.stock.stock_code, question=plan.frame.original_query, as_of=stamp, idempotency_key=str(id), allow_analysis=True).model_dump(mode='json')

def outcome(binding, flow=None):
    if binding.redacted_at is not None:
        return dict(supervisor_id=str(binding.id), plan=None, plan_status='deleted', effective_scope=None, views=[], coverage='deleted', flow=None)
    saved = decode(binding.plan_json)
    raw = {k: v for (k, v) in saved.items() if k != 'effective_scope'}
    plan = Plan.model_validate(raw)
    state = flow.state if flow is not None else 'not_admitted'
    views = [dict(view=v, state=state if v == 'flow' else 'not_executed', reason='flow_state' if v == 'flow' and flow is not None else 'awaiting_admission' if v == 'flow' else 'not_connected') for v in plan.requested_views]
    coverage = 'partial' if state == 'stored' and plan.partial else 'fulfilled' if state == 'stored' else 'unfulfilled' if state in {'failed', 'unknown'} else 'pending'
    return Outcome(supervisor_id=str(binding.id), plan=plan, plan_status='confirmed', effective_scope=saved['effective_scope'], views=views, coverage=coverage, flow=flow.model_dump(mode='json') if flow is not None else None).model_dump(mode='json')
