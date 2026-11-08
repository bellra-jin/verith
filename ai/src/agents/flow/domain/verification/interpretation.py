"""Gate3 for new generation only: exact evidence + IDs + code-owned prose."""
from ..interpretation_claims import compose, SelectionInvalid
from ..models import GateResult


def verify_interpretation(interpretation, signals, *, bank=None, selection=None,
                          meta=None, invalid_selection=False):
    try:
        if invalid_selection or type(interpretation) is not str or not interpretation or selection is None:
            raise SelectionInvalid()
        if interpretation != compose(bank, selection, meta, signals):
            raise SelectionInvalid()
    except (SelectionInvalid, ValueError, TypeError, AttributeError, OverflowError, RecursionError):
        return GateResult(gate=3, passed=False, checks=[],
                          failures=["선택 schema·검증 근거·확정 문장 정합 실패"])
    return GateResult(gate=3, passed=True, checks=["선택 ID·불변 원자료 근거·확정일·결정적 문장 일치"], failures=[])
