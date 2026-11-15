from src.agents.fundamental.domain.verification.verdict_guard import guard_llm_output


RATIOS = {"roe": {"value": 3.25, "unit": "%", "fiscal_year": "2025"},
          "debt_ratio": {"value": 142.16, "unit": "%", "fiscal_year": "2025"},
          "eps": {"value": 2, "unit": "원", "fiscal_year": "2025"}}


def test_guard_rejects_numbers_swapped_between_explicit_metric_claims():
    result = guard_llm_output("보통 수준입니다.", "ROE는 142.16%, 부채비율은 3.25%입니다.", RATIOS, [])
    assert not result.ok
    assert "metric claim mismatch: roe" in result.violations
    assert "metric claim mismatch: debt_ratio" in result.violations


def test_guard_rejects_explicit_wrong_unit_even_when_number_exists():
    result = guard_llm_output("보통 수준입니다.", "ROE는 3.25원이며 EPS는 2%입니다.", RATIOS, [])
    assert not result.ok
    assert "metric unit mismatch: roe" in result.violations
    assert "metric unit mismatch: eps" in result.violations


def test_unavailable_metric_is_not_made_known_by_zero_or_hundred_benchmark():
    for value in (0, 100):
        result = guard_llm_output("자료 부족입니다.", f"ROE는 {value}%입니다.",
            {"roe": {"value": None, "unit": "%", "status": "unavailable"}}, [])
        assert not result.ok
        assert "metric claim unavailable: roe" in result.violations


def test_direct_metric_claims_keep_existing_rounding_and_valid_units():
    result = guard_llm_output("보통 수준입니다.", "ROE는 3.3%, 부채비율은 142%, EPS는 2원입니다.", RATIOS, [])
    assert result.ok


def test_existing_benchmark_percentpoint_past_period_and_compound_policies_are_preserved():
    for text in ("부채비율은 100% 기준선을 상회합니다. ROE는 3.25%입니다.",
                 "영업이익률은 전년 대비 20%p 상승했습니다.",
                 "2024년 ROE는 10%였습니다.",
                 "ROE와 부채비율은 각각 3.25%, 142.16%입니다."):
        result = guard_llm_output("보통 수준입니다.", text, RATIOS, [], trend={"roe": [10]})
        assert result.ok, result.violations


def test_direct_claim_of_missing_supported_metric_is_unavailable_not_borrowed_number():
    result = guard_llm_output("보통 수준입니다.", "순이익률은 142.16%입니다.", RATIOS, [])
    assert not result.ok
    assert "metric claim unavailable: net_margin" in result.violations


def test_korean_direct_connectors_aliases_and_approximation_do_not_allow_swapped_numbers():
    for text in ("ROE가 142.16%입니다.", "ROE 값은 142.16%입니다.", "ROE의 수치는 142.16%입니다.",
                 "ROE: 142.16%입니다.", "ROE=142.16%입니다.", "ROE는 약 142.16%입니다.",
                 "자기자본이익률은 142.16%입니다.", "부채 비율은 3.25% 수준입니다."):
        result = guard_llm_output("보통 수준입니다.", text, RATIOS, [])
        assert not result.ok, text
        assert any(v.startswith("metric claim mismatch:") for v in result.violations)


def test_explicit_current_year_is_bound_but_threshold_comparisons_keep_existing_policy():
    result = guard_llm_output("보통 수준입니다.", "2025년 ROE는 142.16%입니다.", RATIOS, [])
    assert not result.ok
    for text in ("부채비율은 100%보다 높습니다.", "부채비율은 100% 이상입니다.", "부채비율은 100%의 기준선을 상회합니다."):
        assert guard_llm_output("보통 수준입니다.", text, RATIOS, []).ok


def test_explicit_from_to_comparison_is_not_mistaken_for_current_direct_value():
    ratios = {"roe": {"value": 10, "unit": "%", "fiscal_year": "2025"}}
    for text in ("ROE는 -3.25%에서 10%로 상승했습니다.", "ROE는 -3.25%였으나 현재 10%입니다."):
        result = guard_llm_output("보통 수준입니다.", text, ratios, [], trend={"roe": [-3.25, 10]})
        assert result.ok, result.violations


def test_correct_negation_and_immediate_correction_are_not_positive_claim_false_positives():
    for text in ("ROE는 142.16%가 아닙니다. ROE는 3.25%입니다.",
                 "ROE는 99.9%가 아닙니다. ROE는 3.25%입니다.",
                 "ROE는 142.16%가 아니라 3.25%입니다.",
                 "ROE는 99.9%가 아니고 3.25%입니다.",
                 "ROE는 3.25원이 아니라 3.25%입니다.",
                 "ROE는 3%가 아니라 3.25%입니다.",
                 "ROE는 142.16%가 아니라 ROE는 3.25%입니다.",
                 "ROE는 142.16%가 아니라 부채비율은 142.16%입니다."):
        result = guard_llm_output("보통 수준입니다.", text, RATIOS, [])
        assert result.ok, (text, result.violations)


def test_wrong_negation_and_corrected_wrong_value_or_unit_are_still_rejected():
    for text in ("ROE는 3.25%가 아닙니다.",
                 "ROE는 3.25%가 아니라 142.16%입니다.",
                 "ROE는 3.25원이 아니라 142.16%입니다.",
                 "ROE는 142.16%가 아니라 3.25원입니다."):
        result = guard_llm_output("보통 수준입니다.", text, RATIOS, [])
        assert not result.ok, text
        assert any(v.startswith('metric claim contradicts:') or v.startswith('metric claim mismatch:')
                   or v.startswith('metric unit mismatch:') for v in result.violations)


def test_unknown_metric_value_cannot_support_a_numeric_negation_either():
    result = guard_llm_output("자료 부족입니다.", "ROE는 0%가 아닙니다.",
        {"roe": {"value": None, "unit": "%", "status": "unavailable"}}, [])
    assert not result.ok
    assert "metric claim unavailable: roe" in result.violations


def test_immediate_correction_handles_nominal_negation_and_long_spacing_but_keeps_comparison_scope():
    for text in ("ROE는 142.16%가 아닌 3.25%입니다.", "ROE는 142.16%가 아니라 100% 기준선을 하회합니다."):
        result = guard_llm_output("보통 수준입니다.", text, RATIOS, [])
        assert result.ok, result.violations
    for text in ("ROE는 99.9%가 아닌 142.16%입니다.", "ROE는 99.9%가 아니라" + " " * 40 + "142.16%입니다."):
        result = guard_llm_output("보통 수준입니다.", text, RATIOS, [])
        assert not result.ok
        assert "metric claim mismatch: roe" in result.violations


def test_known_zero_is_preserved_but_cannot_be_falsely_denied():
    ratios = {"roe": {"value": 0, "unit": "%", "status": "available"}}
    assert guard_llm_output("보통 수준입니다.", "ROE는 100%가 아니라 0%입니다.", ratios, []).ok
    result = guard_llm_output("보통 수준입니다.", "ROE는 0%가 아닙니다.", ratios, [])
    assert not result.ok and "metric claim contradicts: roe" in result.violations


def test_nonfinite_candidates_never_become_numeric_whitelist_proof_or_raise_round_error():
    from src.agents.fundamental.domain.verification.verdict_guard import _matches_allowed
    assert not _matches_allowed(9.99, [float('inf'), float('nan')])
    assert not _matches_allowed(float('inf'), [float('inf')])


def test_explicit_approximate_negation_uses_existing_rounding_policy_not_literal_equality():
    result = guard_llm_output("보통 수준입니다.", "ROE는 약 3%가 아닙니다.", RATIOS, [])
    assert not result.ok and "metric claim contradicts: roe" in result.violations
    assert guard_llm_output("보통 수준입니다.", "ROE는 약 142%가 아니라 3.25%입니다.", RATIOS, []).ok


def test_recognized_but_unsupported_double_negation_is_held_not_assumed_true():
    for text in ("ROE는 99.9%가 아닌 것은 아닙니다.", "ROE는 99.9%가 아닌 ROE의 것은 아닙니다."):
        result = guard_llm_output("보통 수준입니다.", text, RATIOS, [])
        assert not result.ok
        assert "metric negation ambiguous: roe" in result.violations
