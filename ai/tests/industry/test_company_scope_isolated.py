"""Known-company retrieval scope checks with fake vector results only."""
from __future__ import annotations


def run_scope_tests():
    import ast
    import os
    from pathlib import Path
    import re
    import sys

    root = Path(__file__).resolve().parents[2]
    source = root / "src/agents/industry"
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(root))
    def guard(event, args):
        if event in {"socket.connect", "socket.getaddrinfo", "subprocess.Popen", "os.system"}:
            raise AssertionError("External operation blocked")
        if event == "open" and isinstance(args[0], (str, bytes)):
            path = Path(os.fsdecode(args[0])).resolve()
            mode, flags = args[1:3]
            if (isinstance(mode, str) and any(c in mode for c in "wax+")) or flags & (os.O_WRONLY | os.O_RDWR):
                raise AssertionError("File write blocked")
            if path.name == ".env" or (path.is_relative_to(root) and path.suffix not in {".py", ".pyc"}):
                raise AssertionError("Project configuration/data read blocked")
    sys.addaudithook(guard)
    from src.agents.industry.domain.companies import COMPANIES
    normal_path = source / "infrastructure/entity_normalization.py"
    normal_tree = ast.parse(normal_path.read_text(encoding="utf-8"))
    constants = {"_AFFIX_PATTERNS", "_AFFIX_RE", "_FOOTNOTE_RE", "_PAREN_NOTE_RE", "_TYPE_LEAK_RE"}
    normal_nodes = [n for n in normal_tree.body if
        isinstance(n, ast.FunctionDef) and n.name in {"_clean", "_key", "normalize_lookup_key"} or
        isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in constants for t in n.targets)]
    normalization = {"re": re}
    exec(compile(ast.Module(body=normal_nodes, type_ignores=[]), str(normal_path), "exec"), normalization)
    path = source / "application/company_retrieval.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    selected = {"_build_company_surfaces", "_mentioned_company", "requires_company_scope", "retrieve_company_chunks"}
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in selected]
    calls = []
    rows = [{"company": "LG화학", "stock_code": "051910", "text": "synthetic A filing"},
            {"company": "삼성SDI", "stock_code": "006400", "text": "synthetic B filing"}]
    def search(question, *, k, company, graph):
        calls.append((k, company))
        return [row for row in rows if company is None or row["company"] == company]
    from src.agents.industry.domain.company_scope import (
        MAX_VECTOR_RESULTS, SURFACE_PRIORITY, CompanyScope, plan_company_scope, retain_company_chunks, company_scope_policy)
    ns = dict(AgentState=dict, MAX_VECTOR_RESULTS=MAX_VECTOR_RESULTS,
              plan_company_scope=plan_company_scope, retain_company_chunks=retain_company_chunks, COMPANIES=COMPANIES, normalize_lookup_key=normalization["normalize_lookup_key"],
              _SURFACE_PRIORITY=SURFACE_PRIORITY, vector_search=search)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), ns)
    ns["_COMPANY_SURFACES"] = ns["_build_company_surfaces"]()
    state = ns["retrieve_company_chunks"]({"question": "LG화학과 삼성SDI의 사업 구조를 비교해줘"}, graph=object())
    assert {row["company"] for row in state["chunks"]} == {"LG화학", "삼성SDI"}
    assert len(calls) == 1
    print("PASS both named companies retained within one existing search call")
    surfaces = ns["_COMPANY_SURFACES"]
    normalize = normalization["normalize_lookup_key"]
    def retrieve(question, chunks):
        rows[:] = chunks
        calls.clear()
        return ns["retrieve_company_chunks"]({"question": question}, graph=object())
    good_a = {"company": "LG화학", "stock_code": "051910", "text": "synthetic A filing"}
    good_b = {"company": "삼성SDI", "stock_code": "006400", "text": "synthetic B filing"}
    for question in ("LG화학과 삼성SDI 사업구조 비교", "Compare LG Chem and Samsung SDI", "LG화학vs삼성SDI"):
        result = retrieve(question, [good_a, good_b])
        assert calls == [(5, None)]
        assert set(result["company_scope"].matched) == {"LG화학", "삼성SDI"}
        hold, note = company_scope_policy(result["company_scope"], question)
        assert not hold and "동일 시점" in note
    print("PASS explicit known two-company comparison keeps a single search budget")

    for question in ("LG화학 말고 삼성SDI 비교", "LG화학과 삼성SDI, 엔켐 비교",
                     "LG화학과 삼성SDI 사업구조", "LG화학과 모르는 기업 비교",
                     "2025년 LG화학과 삼성SDI 비교", "LG화학 공시만으로 삼성SDI와 비교"):
        result = retrieve(question, [good_a, good_b])
        assert calls == [] and result["chunks"] == []
        assert company_scope_policy(result["company_scope"], question)[0] is True
    print("PASS exclusions, complex/unknown comparison scope is not guessed")

    question = "LG화학과 삼성SDI 사업구조 비교"
    result = retrieve(question, [good_a, dict(good_a, text="another A source")])
    assert calls == [(5, None)]
    assert result["company_scope"].missing == ("삼성SDI",)
    hold, note = company_scope_policy(result["company_scope"], question)
    assert hold and "실제 자료가 없다는 뜻은 아닙니다" in note
    assert all(chunk["company"] == "LG화학" for chunk in result["chunks"])
    print("PASS asymmetric search evidence is held, not claimed absent from corpus")

    bad_chunks = [dict(good_a, stock_code="006400"), {"text": "unattributed source"},
                  dict(good_a, company="untrusted alias"), dict(good_a, stock_code="051910."),
                  dict(good_a, stock_code=51910)]
    result = retrieve(question, bad_chunks)
    assert calls == [(5, None)] and result["chunks"] == []
    assert result["company_scope"].discarded == 5
    assert company_scope_policy(result["company_scope"], question)[0] is True
    print("PASS mismatched, absent and malformed source identities are never assigned to a target")

    collision = [("shared", "A", "canonical"), ("shared", "B", "alias")]
    plan = plan_company_scope("shared 사업구조", collision)
    assert plan.reason == "ambiguous"
    assert company_scope_policy(plan, plan.question)[0] is True
    selected, scope = retain_company_chunks(plan, [{"company": "shared", "text": "untrusted"}],
                                             collision, lambda value: value.lower())
    assert selected == []
    long = plan_company_scope("에코프로비엠의 사업구조", surfaces)
    assert long.companies == ("에코프로비엠",)
    both = plan_company_scope("에코프로비엠과 에코프로 비교", surfaces)
    assert both.companies == ("에코프로비엠", "에코프로")
    assert not plan_company_scope("10064001 수치 설명", surfaces).companies
    print("PASS alias collision, nested names and embedded numeric codes are distinguished")

    for question, expected_filter in (("LG화학 사업구조", "LG화학"), ("금리 상승의 산업 영향", None)):
        source_rows = [dict(good_a, nested={"value": 1})]
        result = retrieve(question, source_rows)
        assert calls == [(5, expected_filter)]
        assert company_scope_policy(result["company_scope"], question) == (False, "")
        result["chunks"][0]["nested"]["value"] = 2
        assert source_rows[0]["nested"]["value"] == 1
    alias_source = dict(good_a, company="LG Chem")
    result = retrieve("금리 산업 영향", [alias_source])
    assert result["chunks"][0]["company"] == "LG Chem"
    assert alias_source["company"] == "LG Chem"
    print("PASS valid single/global paths and source snapshot values remain compatible")

    stale = CompanyScope(question="older question", companies=("LG화학",), matched=("LG화학",), reason="observed")
    assert company_scope_policy(stale, "new question")[0] is True
    assert company_scope_policy({"reason": "observed"}, "new question")[0] is True
    print("PASS stale/forged scope is not treated as current observed evidence")
    agent_path = source / "application/agent.py"
    agent_tree = ast.parse(agent_path.read_text(encoding="utf-8"))
    route = next(n for n in agent_tree.body if isinstance(n, ast.FunctionDef) and n.name == "_route_after_classify")
    routing = dict(AgentState=dict, requires_company_scope=ns["requires_company_scope"],
                   _is_hub_question=lambda question: False)
    exec(compile(ast.Module(body=[route], type_ignores=[]), str(agent_path), "exec"), routing)
    for question in ("LG화학과 삼성SDI 비교", "LG화학 말고 삼성SDI 비교"):
        assert routing["_route_after_classify"]({"question": question, "label": "global"}) == "vector"
    assert routing["_route_after_classify"]({"question": "금리 산업 영향", "label": "global"}) == "overview"
    assert routing["_route_after_classify"]({"question": "LG화학 사업구조", "label": "relational"}) == "cypher"
    print("PASS deterministic company scope cannot be bypassed by model route label")
    print("All company retrieval scope regressions passed")


if __name__ == "__main__":
    run_scope_tests()
