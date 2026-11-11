"""Internal stage/read only. No engine, public save, transaction or usage authority."""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select
from db.models.common.agent_report import AgentReport
from db.models.technical.technical_report import TechnicalReport
from db.models.technical.report_snapshot import TechnicalReportSnapshot, FORMAT, TEXT_LIMITS
from db.models.technical.report_chart import TechnicalReportChart
from db.models.technical.report_signal import TechnicalReportSignal
from db.models.technical.report_risk_note import TechnicalReportRiskNote
from db.models.technical.report_interpretation import TechnicalReportInterpretation
from db.models.technical.report_verification import TechnicalReportVerification
from src.modules.analysis.domain.contracts import (
    AnalysisContext, FrozenAnalysisResult, StagedReportReference, canonical_json, strict_json,
)
from src.modules.auth.application.session_service import Principal, AuthenticationRequired, validate_principal
from src.modules.technical.application.boundary_adapter import TechnicalBoundaryBinding
from src.modules.technical.application.boundary_restore import TechnicalReadBinding
from src.modules.technical.domain.execution_boundary import PERIODS
from src.modules.technical.domain.ai_output import TechnicalAgentOutputMirror
from src.modules.technical.infrastructure import report_repository as repo

OPERATION = 'technical.owned-stage.v1'


class TechnicalStorageInputError(ValueError):
    def __init__(self): super().__init__('Technical storage input is invalid')


class TechnicalReportConflict(ValueError):
    def __init__(self): super().__init__('Technical report ID already claimed')


class TechnicalStoredPayloadError(ValueError):
    def __init__(self): super().__init__('Stored Technical result is inconsistent')


@dataclass(frozen=True, slots=True)
class TechnicalStoredReport:
    frozen: FrozenAnalysisResult
    preview: dict
    coverage: dict


def canonical_text(value, limit):
    if type(value) is not str or not 2 <= len(value.encode('utf-8')) <= limit:
        raise TechnicalStorageInputError()
    parsed = strict_json(value)
    if type(parsed) is not dict or canonical_json(parsed) != value:
        raise TechnicalStorageInputError()
    return parsed


def checked(binding, frozen):
    """Revalidate separate expectations even for unsafe-constructed dataclasses."""
    try:
        if not isinstance(binding, TechnicalReadBinding) or not isinstance(frozen, FrozenAnalysisResult):
            raise TechnicalStorageInputError()
        binding.__post_init__()
        boundary = canonical_text(binding.boundary.input_json, TEXT_LIMITS['input_json'])
        caller = canonical_text(binding.caller_input_json, TEXT_LIMITS['caller_input_json'])
        if (binding.caller_context.operation != OPERATION or
                caller != {'operation':OPERATION, 'boundary_request':boundary}):
            raise TechnicalStorageInputError()
        # Equality above checks structure; exact canonical text preserves numeric representation.
        if binding.caller_input_json != canonical_json({'operation':OPERATION, 'boundary_request':boundary}):
            raise TechnicalStorageInputError()
        for context in (binding.caller_context, binding.boundary.context):
            canonical_text(canonical_json(context.identity()), 4096)
        canonical_text(frozen.input_json, TEXT_LIMITS['input_json'])
        response = canonical_text(frozen.result_json, TEXT_LIMITS['result_json'])
        preview = binding.restore(frozen)
        preview['charts'].sort(key=lambda chart:chart['display_order'])
        return boundary, response, preview
    except (ValueError, TypeError, AttributeError, KeyError, UnicodeError, RecursionError):
        raise TechnicalStorageInputError() from None


def snapshot_values(binding, frozen, created_at, owner_session_id):
    return dict(report_id=frozen.report_id, owner_user_id=binding.caller_context.owner_user_id,
        owner_session_id=owner_session_id,
        request_id=binding.boundary.request_id, trace_id=binding.boundary.trace_id, format=FORMAT,
        caller_context_json=canonical_json(binding.caller_context.identity()),
        boundary_context_json=canonical_json(binding.boundary.context.identity()),
        caller_input_json=binding.caller_input_json, created_at=created_at,
        **{name:getattr(frozen,name) for name in ('input_schema','result_schema','input_json','result_json',
                                                'input_sha256','result_sha256','binding_sha256')})


def projection(binding, frozen, principal, created_at):
    """Project validated data only; JSON TEXT stays authoritative and unmodified."""
    request, response, _ = checked(binding, frozen)
    data = request['data']; stock = data['stock']; raw = response['data']['result']
    output = TechnicalAgentOutputMirror.model_validate(raw)
    rid = frozen.report_id; signal = output.signal
    root = TechnicalReport(id=rid, owner_user_id=principal.user_id,
        request_id=str(binding.boundary.request_id), client_session_id=None,
        ticker=stock['stock_code'], stock_code=stock['stock_code'], stock_name=stock['stock_name'],
        original_query=data['original_query'], normalized_query=None, analysis_focus=None,
        final_regime=output.regime.final_regime, daily_regime=output.regime.daily_regime,
        weekly_trend=output.regime.weekly_trend, monthly_trend=output.regime.monthly_trend,
        alignment_flag=output.regime.alignment_flag, regime_context=output.regime.regime_context,
        consensus=signal.consensus if signal else None, signal_score=signal.signal_score if signal else None,
        confidence=signal.confidence if signal else None, confidence_basis=signal.confidence_basis if signal else None,
        data_status=output.data_status, source=output.source, trace_id=str(binding.boundary.trace_id),
        model_name=None, as_of=binding.boundary.context.as_of, created_at=created_at,
        input_payload=request, output_payload=response)
    signals = [TechnicalReportSignal(id=uuid4(), report_id=rid, indicator=s.indicator, timeframe=None,
        signal=s.signal, value=s.value, value_unit=None, metrics=s.metrics, detail=s.detail,
        detail_source=s.detail_source, weight=s.weight, display_order=i) for i,s in enumerate(output.technical_signals)]
    charts = [TechnicalReportChart(id=uuid4(), report_id=rid, period=c['period'],
        candle_unit=c['chart_data']['candle_unit'], chart_data=c['chart_data'],
        annotations=c['chart_data']['annotations'], chart_payload=None, display_order=PERIODS.index(c['period']))
        for c in raw.get('charts', [])]
    risks = [TechnicalReportRiskNote(id=uuid4(), report_id=rid, flag=r.flag, severity=None,
        note=r.note, ref_price=r.ref_price, note_metadata=None, display_order=i)
        for i,r in enumerate(output.risk.items if output.risk else [])]
    interpretation = TechnicalReportInterpretation(id=uuid4(), report_id=rid,
        interpretation=output.interpretation.text, interpretation_source=output.interpretation.source,
        model_name=None, template_fallback_used=output.interpretation.source == 'template_fallback',
        detail_source_count=None, sections=output.interpretation.sections_dict())
    v = output.verification
    verification = TechnicalReportVerification(id=uuid4(), report_id=rid, calc_passed=v.calc_passed,
        regime_passed=v.regime_passed, label_matched=v.label_matched, outcome=v.outcome,
        regen_count=v.regen_count, failed_indicators=None, validation_summary=None)
    index = AgentReport(id=uuid4(), agent_type='technical', agent_report_id=rid,
        request_id=str(binding.boundary.request_id), client_session_id=None, owner_user_id=principal.user_id,
        owner_session_id=principal.session_id, stock_code=stock['stock_code'], stock_name=stock['stock_name'],
        question=data['original_query'], answer_text=output.interpretation.text, data_status=output.data_status,
        trace_id=str(binding.boundary.trace_id), as_of=binding.boundary.context.as_of, created_at=created_at,
        summary={'storage_format':FORMAT, 'execution_mode':response['data']['execution_mode'],
                 'coverage':response['data']['coverage']})
    return root, signals, charts, risks, interpretation, verification, index


def _context(text):
    values = canonical_text(text,4096)
    for name in ('analysis_id','admission_request_id','attempt_id','owner_user_id'):
        values[name] = UUID(values[name])
    for name in ('as_of','deadline_at'): values[name] = datetime.fromisoformat(values[name])
    context = AnalysisContext(**values)
    if canonical_json(context.identity()) != text: raise TechnicalStorageInputError()
    return context


def restore_snapshot(snapshot):
    if snapshot.format != FORMAT: raise TechnicalStorageInputError()
    caller = _context(snapshot.caller_context_json); boundary = _context(snapshot.boundary_context_json)
    binding = TechnicalReadBinding(caller, snapshot.caller_input_json,
        TechnicalBoundaryBinding(boundary, snapshot.report_id, snapshot.request_id, snapshot.trace_id, snapshot.input_json))
    frozen = FrozenAnalysisResult(context=caller, report_id=snapshot.report_id,
        **{name:getattr(snapshot,name) for name in ('input_schema','result_schema','input_json','result_json',
                                                'input_sha256','result_sha256','binding_sha256')})
    _, response, preview = checked(binding, frozen)
    if snapshot.owner_user_id != caller.owner_user_id: raise TechnicalStorageInputError()
    return binding, TechnicalStoredReport(frozen,preview,response['data']['coverage'])


def check_projection(actual, expected, *, generated_id=False):
    if actual is None: raise TechnicalStoredPayloadError()
    if generated_id and not isinstance(actual.id, UUID): raise TechnicalStoredPayloadError()
    for prop in expected.__mapper__.column_attrs:
        key = prop.key
        if generated_id and key == 'id': continue
        if getattr(actual,key) != getattr(expected,key): raise TechnicalStoredPayloadError()


class TechnicalOwnedReportService:
    def __init__(self, session, *, principal): self.session, self.principal = session, principal

    async def _authorize(self):
        if not isinstance(self.principal, Principal): raise AuthenticationRequired()
        await validate_principal(self.session,self.principal,lock=True)
        return self.principal

    async def stage(self, binding, frozen):
        with self.session.no_autoflush:
            principal = await self._authorize()
            request, _, _ = checked(binding,frozen)
            if principal.user_id != binding.caller_context.owner_user_id: raise AuthenticationRequired()
            if (await repo.storage_root_for_update(self.session,frozen.report_id) is not None or
                    await repo.technical_indexes(self.session,frozen.report_id)):
                raise TechnicalReportConflict()
            if await repo.get_stock(self.session,request['data']['stock']['stock_code']) is None:
                raise TechnicalStorageInputError()
            stamp = await self.session.scalar(select(func.clock_timestamp()))
            rows = projection(binding,frozen,principal,stamp)
            snapshot = TechnicalReportSnapshot(**snapshot_values(binding,frozen,stamp,principal.session_id))
        root,signals,charts,risks,interpretation,verification,index = rows
        await repo.add_report(self.session,report=root,signals=signals,charts=charts,risk_notes=risks,
                              interpretation=interpretation,verification=verification)
        self.session.add(snapshot); self.session.add(index)
        await self.session.flush()
        return StagedReportReference(frozen.report_id,principal.user_id)

    async def read(self, report_id):
        if not isinstance(report_id,UUID): raise TechnicalStorageInputError()
        with self.session.no_autoflush:
            principal = await self._authorize()
            selected = await repo.get_owned_storage(self.session,report_id,principal.user_id)
            if selected is None: return None
            root,snapshot = selected
            try:
                binding,result = restore_snapshot(snapshot)
                indexes = await repo.technical_indexes(self.session,report_id)
                if (len(indexes) != 1 or indexes[0].owner_user_id != principal.user_id or
                        not isinstance(snapshot.owner_session_id,UUID) or
                        indexes[0].owner_session_id != snapshot.owner_session_id or
                        snapshot.owner_user_id != principal.user_id):
                    raise TechnicalStoredPayloadError()
                # Admission session is preserved, not replaced by the reader's new session.
                stored_principal = Principal(principal.user_id,snapshot.owner_session_id,principal.expires_at,principal.token_digest)
                expected = projection(binding,result.frozen,stored_principal,snapshot.created_at)
                check_projection(root,expected[0]); check_projection(indexes[0],expected[-1],generated_id=True)
                actual_groups = await repo.storage_children(self.session,report_id)
                for actual, wanted in zip(actual_groups,expected[1:6]):
                    wanted = wanted if isinstance(wanted,list) else [wanted]
                    if len(actual) != len(wanted): raise TechnicalStoredPayloadError()
                    if wanted and hasattr(wanted[0],'display_order'):
                        actual = sorted(actual,key=lambda row:row.display_order)
                        wanted = sorted(wanted,key=lambda row:row.display_order)
                    for got,want in zip(actual,wanted): check_projection(got,want,generated_id=True)
                return result
            except (ValueError, TypeError, AttributeError, KeyError, UnicodeError, RecursionError):
                raise TechnicalStoredPayloadError() from None
