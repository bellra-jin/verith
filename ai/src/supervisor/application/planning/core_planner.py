"""Meaning first, bounded read-only tool request, canonical continuation only."""
from src.supervisor.domain.meaning import CoreInvalid, Draft, MeaningFrame, POLICY, VERSION, sha
from src.supervisor.domain.core_contracts import InternalOutput, Plan, Resolution, Stock, candidate_ref
from src.supervisor.domain.capabilities import capability_list
from src.supervisor.application.meaning_service import understand

def plan_for(draft, frame, resolution=None):
    status = 'needs_clarification'
    selected = []
    reference = None
    if not frame.unresolved_slots:
        if 'flow' not in frame.requested_views:
            status = 'unsupported'
        elif resolution is not None:
            reference = candidate_ref(draft, resolution)
            if draft.selected_ticker is not None:
                options = {c.stock_code: c for c in resolution.candidates}
                if resolution.status != 'ambiguous' or draft.selected_ticker not in options:
                    raise CoreInvalid()
                if reference != draft.candidate_ref:
                    status = 'selection_stale'
                else:
                    c = options[draft.selected_ticker]
                    resolution = Resolution(status='resolved', reason='exact_match', stock=Stock(**c.model_dump(exclude={'match_type'})), candidates=[])
            if status != 'selection_stale':
                status = {'resolved': 'ready', 'ambiguous': 'needs_stock_selection', 'not_found': 'not_found'}[resolution.status]
            if status == 'ready':
                selected = ['flow']
    waivers = [c.condition_id for c in frame.conditions if c.domain == 'flow' and c.disposition != 'honored']
    partial = any((v != 'flow' for v in frame.requested_views)) or bool(waivers)
    if status == 'ready' and partial:
        status = 'scope_confirmation'
    value = dict(schema_version=VERSION, policy_version=POLICY, frame=frame.model_dump(mode='json'), resolution=resolution.model_dump(mode='json') if resolution is not None else None, candidate_ref=reference, requested_views=frame.requested_views, capabilities=capability_list(), selected_views=selected, status=status, partial=partial, required_waivers=waivers)
    return Plan(**value, plan_hash=sha(value))

async def start(draft, gateway=None):
    frame = await understand(draft, gateway)
    if frame.unresolved_slots or 'flow' not in frame.requested_views:
        return InternalOutput(action='clarify' if frame.unresolved_slots else 'final', frame=frame, lookup=None, plan=plan_for(draft, frame))
    mention = next((m for m in frame.mentions if not m.negated))
    return InternalOutput(action='resolve_stock', frame=frame, lookup=mention.text, plan=None)

def continuation(draft, frame, resolution):
    MeaningFrame.model_validate(frame.model_dump())
    Draft.model_validate(draft.model_dump())
    if frame.original_query != draft.original_query or frame.answers != draft.answers or frame.revision != draft.revision or frame.unresolved_slots or ('flow' not in frame.requested_views):
        raise CoreInvalid()
    return InternalOutput(action='final', frame=frame, lookup=None, plan=plan_for(draft, frame, resolution))
