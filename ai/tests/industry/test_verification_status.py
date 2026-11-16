from src.agents.industry.application.report_export import build_report_payload, parse_answer


def test_citation_presence_is_not_verification_evidence():
    parsed = parse_answer("기업 A가 공급합니다.\n\n근거\n[G1] 기업 A의 공시")
    assert parsed["citationText"]
    assert parsed["faithfulness"]["status"] == "unchecked"
    assert parsed["faithfulness"]["label"] == "근거 검증 정보 없음"


def test_no_citations_remains_unchecked():
    assert parse_answer("기업 A의 설명입니다.")["faithfulness"]["status"] == "unchecked"


def test_export_does_not_trust_unbound_checked_or_verified_hints():
    state = dict(question="합성 질문", answer="기업 A의 설명입니다.\n근거\n[G1] 공시",
                 checked=True, verified=True, faithfulness={"checked": True}, rows=[], chunks=[])
    payload = build_report_payload(state, graph_snapshot={"nodes": {}, "relationships": {}},
                                   created_at="2026-11-15T00:00:00+00:00")
    assert payload["answer"]["faithfulness"]["status"] == "unchecked"
    assert payload["answer"]["body"] == "기업 A의 설명입니다."
    assert payload["schemaVersion"] == "research-report.v1"
    assert state["answer"].endswith("[G1] 공시")


def test_gate_skip_failure_and_clean_run_cannot_be_inferred_from_citations():
    from types import SimpleNamespace
    from src.agents.industry.application.faithfulness import check_faithfulness

    class FakeVerifier:
        def __init__(self, output=None, failure=False):
            self.output, self.failure, self.calls = output, failure, 0
        def invoke(self, prompt):
            self.calls += 1
            if self.failure:
                raise RuntimeError("synthetic verifier failure")
            return SimpleNamespace(content=self.output)

    for evidence, verifier, checked in (
        ([], FakeVerifier("1: SUPPORTED"), False),
        (["합성 근거"], FakeVerifier(failure=True), False),
        (["합성 근거"], FakeVerifier("invalid"), False),
        (["합성 근거"], FakeVerifier("1: SUPPORTED"), True),
    ):
        result = check_faithfulness("기업 A는 공급합니다.", evidence, llm=verifier)
        assert result.checked is checked
        parsed = parse_answer(result.text + "\n근거\n[G1] 합성 출처")
        assert parsed["faithfulness"]["status"] == "unchecked"


def test_explicit_unsupported_warning_is_not_upgraded_or_discarded():
    parsed = parse_answer('기업 A의 주장. ⚠️미검증\n\n⚠️ 검증되지 않은 진술 1건:\n- "기업 A의 주장."\n\n근거\n[G1] 합성 근거')
    assert parsed["faithfulness"]["status"] == "warning"
    assert len(parsed["faithfulness"]["unsupportedClaims"]) == 1


def test_existing_renderer_preserves_unchecked_payload_without_reanalysis():
    import json
    import re
    from src.agents.industry.api.report.render import render_report_html, validate_payload

    state = dict(question="합성 질문", answer="기업 A의 설명입니다.\n근거\n[G1] 합성 출처",
                 rows=[], chunks=[])
    payload = build_report_payload(state, graph_snapshot={"nodes": {}, "relationships": {}},
                                   created_at="2026-11-15T00:00:00+00:00")
    validate_payload(payload)
    html = render_report_html(payload)
    match = re.search(r'<script id="research-report-data" type="application/json">\s*(.*?)\s*</script>', html, re.S)
    assert match
    stored = json.loads(match.group(1))
    assert stored["answer"]["faithfulness"]["status"] == "unchecked"
    assert stored["answer"]["faithfulness"] == payload["answer"]["faithfulness"]


def test_missing_actual_verification_does_not_mark_pipeline_done():
    payload = build_report_payload(dict(question="합성 질문", answer="합성 답변", rows=[], chunks=[]),
                                   graph_snapshot={"nodes": {}, "relationships": {}})
    step = next(item for item in payload["execution"]["pipeline"] if item["id"] == "faithfulness")
    assert step["status"] != "done"


def test_actual_answer_node_preserves_bound_clean_verification_once():
    import json
    from industry_test_boundary import run_answer
    from src.agents.industry.api.report.render import render_report_html
    state, calls = run_answer()
    payload = build_report_payload(state, graph_snapshot={"nodes": {}, "relationships": {}})
    assert calls == ["answer", "verify"]
    assert payload["answer"]["faithfulness"]["status"] == "verified"
    step = next(p for p in payload["execution"]["pipeline"] if p["id"] == "faithfulness")
    assert step["status"] == "done"
    assert "answer_verification" not in json.dumps(payload, ensure_ascii=False)
    assert '"status": "verified"' in render_report_html(payload)


def test_actual_skip_error_invalid_and_unsupported_are_distinct_without_new_wire_status():
    from industry_test_boundary import run_answer
    cases = [
        ({"verify": False}, "unchecked", "미실행", ["answer"]),
        ({"rows": []}, "unchecked", "미실행", ["answer"]),
        ({"failure": True}, "unchecked", "판정 불가", ["answer", "verify"]),
        ({"verdict": "invalid"}, "unchecked", "판정 불가", ["answer", "verify"]),
        ({"verdict": "1: UNSUPPORTED"}, "warning", "검사 완료", ["answer", "verify"]),
    ]
    for kwargs, status, label, expected_calls in cases:
        state, calls = run_answer(**kwargs)
        payload = build_report_payload(state, graph_snapshot={"nodes": {}, "relationships": {}})
        assert calls == expected_calls
        assert payload["answer"]["faithfulness"]["status"] == status
        step = next(p for p in payload["execution"]["pipeline"] if p["id"] == "faithfulness")
        assert step["statusText"] == label
        assert step["status"] == ("done" if status == "warning" else "skipped")


def test_stale_answer_question_rows_chunks_and_forged_dict_cannot_promote_verification():
    from copy import deepcopy
    from dataclasses import asdict
    from industry_test_boundary import run_answer
    state, _ = run_answer()
    for key, value in (("answer", "changed answer"), ("question", "changed question"),
                       ("rows", [{"company": "B"}]), ("chunks", [{"text": "changed"}]),
                       ("answer_verification", asdict(state["answer_verification"]))):
        changed = deepcopy(state)
        changed[key] = value
        payload = build_report_payload(changed, graph_snapshot={"nodes": {}, "relationships": {}})
        assert payload["answer"]["faithfulness"]["status"] == "unchecked"
        step = next(p for p in payload["execution"]["pipeline"] if p["id"] == "faithfulness")
        assert step["status"] == "skipped" and step["statusText"] == "실행 미확인"


def test_nonfinite_binding_and_verifier_initialization_failure_stay_unconfirmed():
    from industry_test_boundary import run_answer
    from src.agents.industry.application.faithfulness import check_faithfulness
    result = check_faithfulness("기업 A는 공급합니다.", ["합성 근거"])
    assert result.checked is False and result.outcome == "indeterminate"
    state, _ = run_answer(rows=[{"value": float("nan")}])
    payload = build_report_payload(state, graph_snapshot={"nodes": {}, "relationships": {}})
    assert payload["answer"]["faithfulness"]["status"] == "unchecked"


def test_internal_verification_record_is_frozen_and_absent_from_wire():
    import json
    from dataclasses import FrozenInstanceError
    from industry_test_boundary import run_answer
    state, _ = run_answer()
    try:
        state["answer_verification"].outcome = "not_run"
    except FrozenInstanceError:
        pass
    else:
        raise AssertionError("Record must not be mutable")
    payload = build_report_payload(state, graph_snapshot={"nodes": {}, "relationships": {}})
    assert set(payload["answer"]["faithfulness"]) == {"status", "label", "unsupportedClaims"}
    assert set(payload["execution"]["pipeline"][-1]) == {"id", "title", "status", "statusText", "body"}
    wire = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    assert "answer_verification" not in wire and '"binding"' not in wire


def test_reporting_responsibility_modules_stay_within_400_lines():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2] / "src/agents/industry"
    for path in ("application/report_export.py", "api/report/graph_payload.py", "api/report/pipeline.py",
                 "domain/answer_verification.py"):
        assert len((root / path).read_text(encoding="utf-8").splitlines()) <= 400, path


def test_internal_query_rejection_state_does_not_leak_or_mark_cypher_done():
    import json
    state = dict(question="synthetic", answer="synthetic fallback answer", rows=[], chunks=[],
                 cypher="", cypher_rejected=True, error="Generated Cypher is outside the supported read subset")
    payload = build_report_payload(state, graph_snapshot={"nodes": {}, "relationships": {}})
    step = next(item for item in payload["execution"]["pipeline"] if item["id"] == "cypher")
    assert step["status"] == "skipped"
    wire = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    assert "cypher_rejected" not in wire and "supported read subset" not in wire


def test_ambiguous_verifier_output_cannot_become_verified_in_actual_export_flow():
    from industry_test_boundary import run_answer
    for output in ("1: UNSUPPORTED" + chr(10) + "1: SUPPORTED",
                   "1: SUPPORTED_BUT_UNCHECKED", "1: UNKNOWN"):
        state, calls = run_answer(verdict=output)
        payload = build_report_payload(state, graph_snapshot={"nodes": {}, "relationships": {}})
        assert calls == ["answer", "verify"]
        assert payload["answer"]["faithfulness"]["status"] == "unchecked"
        step = next(p for p in payload["execution"]["pipeline"] if p["id"] == "faithfulness")
        assert step["statusText"] == "판정 불가"


def test_known_refusal_sentence_preserves_other_claim_warning_in_actual_flow():
    from industry_test_boundary import run_answer
    refusal = "근거에서 해당 연결을 찾지 못했습니다."
    state, calls = run_answer(answer="기업 A는 공급망 핵심 기업입니다. " + refusal,
                              verdict="1: UNSUPPORTED")
    payload = build_report_payload(state, graph_snapshot={"nodes": {}, "relationships": {}})
    faith = payload["answer"]["faithfulness"]
    assert calls == ["answer", "verify"]
    assert faith["status"] == "warning" and len(faith["unsupportedClaims"]) == 1
    assert faith["unsupportedClaims"][0]["sentence"] == "기업 A는 공급망 핵심 기업입니다."
    assert refusal in payload["answer"]["body"]


def test_whole_refusal_and_reference_prefixed_claim_have_distinct_actual_flow():
    from industry_test_boundary import run_answer
    state, calls = run_answer(answer="근거에서 해당 연결을 찾지 못했습니다.")
    payload = build_report_payload(state, graph_snapshot={"nodes": {}, "relationships": {}})
    assert calls == ["answer"] and payload["answer"]["faithfulness"]["status"] == "unchecked"
    state, calls = run_answer(answer="[G1] 기업 A는 공급망 핵심 기업입니다.", verdict="1: UNSUPPORTED")
    payload = build_report_payload(state, graph_snapshot={"nodes": {}, "relationships": {}})
    assert calls == ["answer", "verify"]
    assert payload["answer"]["faithfulness"]["status"] == "warning"


def test_missing_company_scope_holds_actual_qa_without_new_wire_fields():
    import json
    from industry_test_boundary import run_answer
    from src.agents.industry.domain.company_scope import CompanyScope
    question = "LG화학과 삼성SDI 사업구조 비교"
    scope = CompanyScope(question, ("LG화학", "삼성SDI"), ("LG화학",), ("삼성SDI",), "search_uncovered")
    state, calls = run_answer(question=question, rows=[],
        chunks=[{"company": "LG화학", "stock_code": "051910", "text": "synthetic A filing"}], company_scope=scope)
    assert calls == []
    assert "실제 자료가 없다는 뜻은 아닙니다" in state["answer"]
    payload = build_report_payload(state, graph_snapshot={"nodes": {}, "relationships": {}})
    assert payload["answer"]["faithfulness"]["status"] == "unchecked"
    assert "company_scope" not in json.dumps(payload, ensure_ascii=False, allow_nan=False)
    step = next(p for p in payload["execution"]["pipeline"] if p["id"] == "faithfulness")
    assert step["statusText"] == "미실행"


def test_observed_two_company_scope_uses_existing_qa_with_honest_limit():
    from industry_test_boundary import run_answer
    from src.agents.industry.domain.company_scope import CompanyScope
    question = "LG화학과 삼성SDI 사업구조 비교"
    scope = CompanyScope(question, ("LG화학", "삼성SDI"), ("LG화학", "삼성SDI"), (), "observed")
    state, calls = run_answer(question=question, rows=[], company_scope=scope,
        chunks=[{"company": "LG화학", "stock_code": "051910", "text": "synthetic A filing"},
                {"company": "삼성SDI", "stock_code": "006400", "text": "synthetic B filing"}])
    assert calls == ["answer", "verify"]
    assert "LG화학·삼성SDI" in state["answer"] and "동일 시점" in state["answer"]
    payload = build_report_payload(state, graph_snapshot={"nodes": {}, "relationships": {}})
    assert "동일 시점" in payload["answer"]["body"]


def test_ambiguous_stale_and_inconsistent_company_scope_cannot_invoke_qa():
    from industry_test_boundary import run_answer
    from src.agents.industry.domain.company_scope import CompanyScope
    question = "LG화학과 삼성SDI 사업구조 비교"
    records = [
        CompanyScope(question, reason="ambiguous"),
        CompanyScope("older question", ("LG화학",), ("LG화학",), (), "observed"),
        CompanyScope(question, ("LG화학", "삼성SDI"), ("LG화학",), (), "observed"),
        {"reason": "observed"},
    ]
    for scope in records:
        state, calls = run_answer(question=question, company_scope=scope)
        assert calls == [] and "보류" in state["answer"]


def test_current_macro_snapshot_is_held_without_trusting_filing_metadata():
    from industry_test_boundary import run_answer
    questions = ('현재 기준금리 얼마야?', '오늘 원달러 환율 알려줘', '최신 미국 CPI 수치',
                 '금리는 지금 몇 퍼센트야?', 'current interest rate', 'latest exchange rate',
                 'What is the current interest rate?', 'Show me current exchange rates',
                 'Tell me the latest CPI value')
    for question in questions:
        state, calls = run_answer(question=question,
            rows=[{'rate': 99, 'source': 'official', 'as_of': '2099-01-01'}],
            chunks=[{'text': '현재 금리 99%', 'source': '한국은행', 'date': '2099-01-01'}])
        assert calls == []
        assert '최신 지표 원천' in state['answer'] and '미확인' in state['answer']
        assert '99' not in state['answer']
        payload = build_report_payload(state, graph_snapshot={'nodes': {}, 'relationships': {}})
        assert payload['answer']['faithfulness']['status'] == 'unchecked'
        assert '최신 지표 원천' in payload['answer']['body']


def test_macro_guard_does_not_broaden_current_modifier_or_historical_requests():
    from industry_test_boundary import run_answer
    for question in ('2023년 금리와 2024년 금리 비교', '현재 LG화학의 과거 환율 리스크 설명',
                     '오늘 발표한 회사의 2022년 금리 민감도', '금리 상승이 기업에 전달되는 경로',
                     '현재 금리가 아닌 2020년 금리 설명', 'historical interest rate comparison',
                     '현재 주가와 과거 금리 비교', '현재 금리가 기업에 미치는 연결 경로',
                     '2020년 현재 금리 수준을 2021년과 비교', 'in 2020, current interest rate',
                     'Explain how the current interest rate affects LG Chem financing',
                     'The 2020 filing used the phrase current interest rate; explain its historical context'):
        state, calls = run_answer(question=question)
        assert calls == ['answer', 'verify'], question


def test_macro_hold_is_bounded_observation_not_entire_run_or_source_proof():
    from industry_test_boundary import run_answer
    from src.agents.industry.domain.macro_scope import current_macro_hold
    assert current_macro_hold('2020년 현재 금리 수준과 현재 금리 얼마인지 비교')
    # Known limitations: no complete NLP or implicit-current interpretation.
    assert not current_macro_hold('금리 알려줘')
    assert not current_macro_hold('오늘 발표된 미국의 정책 기준 금리 몇 퍼센트?')
    state, calls = run_answer(question='현재 기준금리 얼마야?', rows=[], chunks=[], verify=False)
    assert calls == []
    assert state['answer_verification'].outcome == 'not_run'


def test_internal_chunk_locator_does_not_change_citation_parser_json_or_html_schema():
    import ast
    import json
    from pathlib import Path
    import re
    import urllib.parse
    from src.agents.industry.application.report_export import parse_answer
    from src.agents.industry.api.report.render import render_report_html, validate_payload
    path = Path(__file__).resolve().parents[2] / 'src/agents/industry/application/evidence_context.py'
    tree = ast.parse(path.read_text(encoding='utf8'))
    ns = dict(json=json, re=re, urllib=urllib)
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), ns)
    chunk = dict(id='005930-0001-a1b2c3d4', stock_code='005930', company='synthetic',
                 text='synthetic body', source_url='https://example.test/filing')
    citation = ns['_format_citations']([], [chunk])
    answer = 'synthetic answer\n\n근거\n' + citation
    parsed = parse_answer(answer)
    assert parsed['body'] == 'synthetic answer'
    assert parsed['citationText'] == citation and parsed['faithfulness']['status'] == 'unchecked'
    state = dict(question='synthetic question', answer=answer, rows=[], chunks=[chunk])
    payload = build_report_payload(state, graph_snapshot={'nodes': {}, 'relationships': {}})
    validate_payload(payload)
    html = render_report_html(payload)
    match = re.search(r'<script id="research-report-data" type="application/json">\s*(.*?)\s*</script>', html, re.S)
    stored = json.loads(match.group(1))
    assert 'citationText' not in stored['answer']
    assert chunk['id'] not in json.dumps(stored, ensure_ascii=False)
    assert stored['answer']['body'] == 'synthetic answer'
    assert stored['answer']['faithfulness']['status'] == 'unchecked'
    # No public evidence ID or source schema is repurposed as a release locator.
    assert stored['evidence'][0]['id'] == 'ev:V1'
    assert 'chunk_id' not in stored['evidence'][0]['source']
    assert ns['_format_citations']([], [dict(chunk, id=None)]).startswith('[V1]')
