"""Explicit Technical scope and fixed intent; no new run/claim/provider authority."""
from src.modules.supervisor.domain.technical_core_contracts import Plan,Outcome,CoreInvalid,decode,canonical
from src.modules.technical.domain.execution_admission import Intent

def confirmed_plan(plan,consent):
    if (plan.status not in {'ready','scope_confirmation'} or plan.selected_views!=['technical']
            or consent.allow_technical is not True or plan.partial and not consent.allow_partial
            or sorted(consent.waived_conditions)!=sorted(plan.required_waivers)
            or len(set(consent.waived_conditions))!=len(consent.waived_conditions)):raise CoreInvalid()
    return dict(plan=plan.model_dump(mode='json'),effective_scope=dict(selected_views=['technical'],profile=plan.support.model_dump(mode='json'),execution_query=plan.execution_query,waived_conditions=list(consent.waived_conditions),partial_consent=consent.allow_partial))

def intent_for(plan):
    return Intent.parse(dict(operation='technical.analysis.v1',ticker=plan.resolution.stock.stock_code,original_query=plan.execution_query,requested_views=['technical'],conditions={'profile':'technical.multiframe.v1','periods':['3m','1y','5y']}))

def fixed_key(id):return 'supervisor.technical-core.1:'+str(id)

def outcome(binding,run=None):
    if binding.redacted_at is not None:return Outcome(supervisor_id=str(binding.id),plan=None,effective_scope=None,technical=None,coverage='deleted').model_dump(mode='json')
    saved=decode(binding.plan_json);plan=Plan.model_validate(saved['plan'])
    reference=None;coverage='pending'
    if run is not None:
        reference=dict(analysis_id=str(run.analysis_id),admission_request_id=str(run.admission_request_id),attempt_id=str(run.attempt_id),report_id=str(run.report_id) if run.state=='stored' else None,report_url=None,state=run.state,as_of=run.as_of.isoformat(),deadline_at=run.deadline_at.isoformat(),reserved_nano=run.reserved_nano,held_nano=run.held_nano)
        coverage=('partial' if plan.partial else 'fulfilled') if run.state=='stored' else 'unfulfilled' if run.state in {'unknown','failed'} else 'pending'
    return Outcome(supervisor_id=str(binding.id),plan=plan,effective_scope=saved['effective_scope'],technical=reference,coverage=coverage).model_dump(mode='json')
