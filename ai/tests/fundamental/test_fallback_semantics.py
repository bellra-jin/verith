from src.agents.fundamental.domain.interpretation.fallback_template import _display_metric, build_fallback_interpretation
from src.agents.fundamental.domain.verification.verdict_guard import guard_llm_output
from src.agents.fundamental.domain.verification.stability import assess_verdict_stability


def test_fallback_preserves_known_transition_without_fabricated_percentage_or_unavailable_claim():
    for display in ("흑자전환", "적자전환", "흑자 기조 회복(저기저)"):
        item = {"value": None, "status": "not_meaningful", "display_value": display,
                "label": "영업이익 변화", "unit": "%"}
        text = _display_metric({"operating_income_growth": item}, "operating_income_growth")
        assert display in text
        assert "퍼센트" in text
        assert "표시하지" in text
        assert "산출 불가" not in text
        assert "%" not in text


def test_fallback_unavailable_never_promotes_stale_display_and_preserves_known_zero():
    unavailable = {"value": None, "status": "unavailable", "display_value": "흑자전환", "label": "성장", "unit": "%"}
    assert "산출 불가" in _display_metric({"growth": unavailable}, "growth")
    assert "흑자전환" not in _display_metric({"growth": unavailable}, "growth")
    zero = {"value": 0, "status": "available", "label": "ROE", "unit": "%"}
    assert "0%" in _display_metric({"roe": zero}, "roe")


def test_insufficient_fallback_score_is_explicitly_not_a_normal_financial_evaluation():
    verdict, interpretation = build_fallback_interpretation("합성 기업", 0, "insufficient_data", {})
    assert "자료 부족" in verdict
    assert "정상 재무 평가" in verdict
    assert "아닙니다" in verdict
    assert "현재 점수 0점 기준으로" not in verdict
    assert assess_verdict_stability(verdict, "insufficient_data", "insufficient_data").verdict_stable
    assert guard_llm_output(verdict, interpretation, {}, [], score=0).ok


def test_normal_fallback_score_and_transition_pass_existing_guard_and_stability():
    ratios = {"operating_income_growth": {"value": None, "status": "not_meaningful",
              "display_value": "흑자전환", "label": "영업이익 변화", "unit": "%"}}
    verdict, interpretation = build_fallback_interpretation("합성 기업", 45, "moderate", ratios)
    assert "현재 점수 45점 기준으로" in verdict
    assert "보통 수준" in verdict
    assert "흑자전환" in interpretation
    assert assess_verdict_stability(verdict, "moderate", "moderate").verdict_stable
    assert guard_llm_output(verdict, interpretation, ratios, [], score=45).ok
