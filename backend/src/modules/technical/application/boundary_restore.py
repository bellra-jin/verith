"""Pure caller/boundary composition, with no execution or persistence authority.

L checks the supplied canonical caller text, not ledger provenance or operation
semantics. B is checked independently by the existing CF021 request parser.
Expected contexts must come from an independent caller; UUID agreement is not
authentication, SQL ownership, or a receipt against replacement of all expectations.
"""
from dataclasses import dataclass

from src.modules.analysis.domain.contracts import (
    AnalysisContext, FrozenAnalysisResult, canonical_json, json_hash, strict_json,
)
from src.modules.analysis.domain.agent_envelope import BoundaryInvalid
from src.modules.technical.application.boundary_adapter import (
    TechnicalBoundaryAdapter, TechnicalBoundaryBinding,
)


@dataclass(frozen=True, slots=True)
class TechnicalReadBinding:
    caller_context: AnalysisContext
    caller_input_json: str
    boundary: TechnicalBoundaryBinding

    def __post_init__(self):
        try:
            if not isinstance(self.caller_context, AnalysisContext) or not isinstance(self.boundary, TechnicalBoundaryBinding):
                raise BoundaryInvalid()
            self.caller_context.validate()
            # Recheck the independent frozen holder and its raw request/B binding.
            TechnicalBoundaryBinding(
                context=self.boundary.context, report_id=self.boundary.report_id,
                request_id=self.boundary.request_id, trace_id=self.boundary.trace_id,
                input_json=self.boundary.input_json,
            )
            value = strict_json(self.caller_input_json)
            if (not isinstance(value, dict) or canonical_json(value) != self.caller_input_json
                    or json_hash(self.caller_input_json) != self.caller_context.input_fingerprint):
                raise BoundaryInvalid()
            for field in ('analysis_id', 'admission_request_id', 'attempt_id',
                          'owner_user_id', 'as_of', 'deadline_at'):
                if getattr(self.caller_context, field) != getattr(self.boundary.context, field):
                    raise BoundaryInvalid()
        except (ValueError, TypeError, AttributeError, UnicodeError, RecursionError):
            raise BoundaryInvalid() from None

    def compose(self, response):
        """Validate CF021 response/frozen bytes, then explicitly bind to caller L."""
        try:
            self.__post_init__()
            adapter = TechnicalBoundaryAdapter(self.boundary)
            if isinstance(response, FrozenAnalysisResult):
                adapter.chart_preview(response)
                frozen = response
            else:
                frozen = adapter.validate_and_freeze(response)
            return FrozenAnalysisResult.freeze(
                context=self.caller_context, report_id=frozen.report_id,
                input_schema=frozen.input_schema, result_schema=frozen.result_schema,
                input_json=frozen.input_json, result_json=frozen.result_json,
            )
        except (ValueError, TypeError, AttributeError, KeyError, UnicodeError, RecursionError):
            raise BoundaryInvalid() from None

    def restore(self, frozen):
        """Compare independent expectations before reusing CF021 chart validation."""
        try:
            self.__post_init__()
            if not isinstance(frozen, FrozenAnalysisResult):
                raise BoundaryInvalid()
            frozen.validate()
            if (frozen.context != self.caller_context or frozen.report_id != self.boundary.report_id
                    or frozen.input_json != self.boundary.input_json):
                raise BoundaryInvalid()
            boundary_frozen = FrozenAnalysisResult.freeze(
                context=self.boundary.context, report_id=frozen.report_id,
                input_schema=frozen.input_schema, result_schema=frozen.result_schema,
                input_json=frozen.input_json, result_json=frozen.result_json,
            )
            return TechnicalBoundaryAdapter(self.boundary).chart_preview(boundary_frozen)
        except (ValueError, TypeError, AttributeError, KeyError, UnicodeError, RecursionError):
            raise BoundaryInvalid() from None
