"""Deterministic one-view Technical plan; never invokes meaning/provider gateways."""
from src.supervisor.application.meaning_policy import assess
from src.supervisor.domain.technical_core_contracts import (
    Plan,Profile,InternalOutput,CoreInvalid,Resolution,VERSION,POLICY,sha,candidate_ref,
)
from src.supervisor.domain.core_contracts import Stock

def eligible(frame):
    active={m.text for m in frame.mentions if not m.negated}
    return (not frame.unresolved_slots and frame.requested_views==['technical']
            and 'technical' not in frame.negated_views and len(active)==1
            and not any(c.kind=='unrecognized' for c in frame.conditions))

def plan_for(draft,frame,context,resolution=None):
    status='needs_clarification';selected=[];reference=None
    if not frame.unresolved_slots and frame.requested_views!=['technical']:status='unsupported'
    if eligible(frame) and resolution is not None:
        reference=candidate_ref(draft,resolution)
        if draft.selected_ticker is not None:
            choices={c.stock_code:c for c in resolution.candidates}
            if resolution.status!='ambiguous' or draft.selected_ticker not in choices:raise CoreInvalid()
            if reference!=draft.candidate_ref:status='selection_stale'
            else:
                c=choices[draft.selected_ticker]
                resolution=Resolution(status='resolved',reason='exact_match',stock=Stock(**c.model_dump(exclude={'match_type'})),candidates=[])
        if status!='selection_stale':status={'resolved':'ready','ambiguous':'needs_stock_selection','not_found':'not_found'}[resolution.status]
        if status=='ready':
            excluded={m.text.casefold() for m in frame.mentions if m.negated}
            if resolution.stock.stock_code.casefold() in excluded or resolution.stock.stock_name.casefold() in excluded:status='needs_clarification'
            else:selected=['technical']
    waivers=[c.condition_id for c in frame.conditions if c.disposition!='honored']
    if status=='ready' and waivers:status='scope_confirmation'
    value=dict(schema_version=VERSION,policy_version=POLICY,context=context.model_dump(mode='json'),frame=frame.model_dump(mode='json'),resolution=resolution.model_dump(mode='json') if resolution else None,candidate_ref=reference,requested_views=frame.requested_views,selected_views=selected,support=Profile().model_dump(mode='json'),execution_query=resolution.stock.stock_code+' 차트' if selected else None,status=status,partial=bool(waivers),required_waivers=waivers)
    return Plan(**value,plan_hash=sha(value))

def run(value):
    assessed=assess(value.draft);frame=assessed.frame
    if value.phase=='continue':
        if value.frame!=frame or not eligible(frame):raise CoreInvalid()
        return InternalOutput(action='final',frame=frame,lookup=None,plan=plan_for(value.draft,frame,value.context,value.resolution))
    if not eligible(frame):
        plan=plan_for(value.draft,frame,value.context)
        return InternalOutput(action='clarify' if plan.status=='needs_clarification' else 'final',frame=frame,lookup=None,plan=plan)
    return InternalOutput(action='resolve_stock',frame=frame,lookup=next(m.text for m in frame.mentions if not m.negated),plan=None)
