"""Company/quote attribution checks using synthetic source text only."""
from __future__ import annotations


def run_company_evidence_tests():
    import ast
    import json
    import os
    from pathlib import Path
    import re
    import sys
    from types import ModuleType
    import urllib.parse

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

    quote = "기업 A는 전해액 사업을 영위하고 있습니다"
    texts = {"A": quote, "B": "기업 B는 배터리 장비를 제조합니다"}
    path = source / "application/evidence_context.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    ns = dict(re=re, urllib=urllib, json=json)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), ns)
    ns["_source_text_norm"] = lambda code: texts.get(code, "")
    ns["_load_filing_meta"] = lambda: {
        "A": {"report_nm": "A report", "source_url": "https://example.test/A"},
        "B": {"report_nm": "B report", "source_url": "https://example.test/B"}}
    facade = ModuleType("src.agents.industry.application.retrieval")
    for name in ("_pick_origin", "_deeplink", "_load_filing_meta"):
        setattr(facade, name, ns[name])
    sys.modules[facade.__name__] = facade
    from src.agents.industry.api.report.graph_payload import build_graph_and_evidence

    failures = []
    def check(name, fn):
        try:
            fn()
            print("PASS", name)
        except Exception as exc:
            failures.append(name)
            print("FAIL", name, type(exc).__name__, str(exc))
    def absent_does_not_choose_first():
        assert ns["_pick_origin"](["B", "A"], "어느 원천에도 없는 합성 인용문") is None
    def split_quote_cannot_mix_companies():
        assert ns["_pick_origin"](["B", "A"], texts["B"] + " ... " + texts["A"]) is None
    def graph_metadata_uses_same_selected_company():
        row = {"evidence_edges": [dict(source="A", relation="SUPPLIES", target="B",
                                      origins=["B", "A"], evidences=[quote])]}
        _, _, evidence = build_graph_and_evidence([row], [])
        assert evidence[0]["source"]["stockCode"] == "A"
        assert evidence[0]["source"]["reportName"] == "A report"
        assert evidence[0]["source"]["url"].startswith("https://example.test/A")
    def short_quote_is_unattributed_not_rejected():
        texts["C"] = "짧은인용"
        assert ns["_pick_origin"](["C"], "짧은인용") is None
        assert ns["_source_link"](["C"], "짧은인용") == ""
    def ordered_same_source_ellipsis_is_supported():
        fragment = "기업 A는 전해액 사업 ... 영위하고 있습니다"
        assert ns["_pick_origin"](["B", "A"], fragment) == "A"
        assert ns["_pick_origin"](["A"], "영위하고 있습니다 ... 기업 A는 전해액 사업") is None
    def source_io_failure_cannot_choose_wrong_first_origin():
        original = ns["_source_text_norm"]
        def load(code):
            if code == "B":
                raise OSError("synthetic source unavailable")
            return texts.get(code, "")
        ns["_source_text_norm"] = load
        try:
            assert ns["_pick_origin"](["B", "A"], quote) == "A"
            assert ns["_pick_origin"](["B"], quote) is None
        finally:
            ns["_source_text_norm"] = original
    def structural_no_quote_provenance_preserves_legacy():
        assert ns["_pick_origin"](["B", "A"], None) == "B"
        assert ns["_source_link"](["B"], None) == "[↗원문](https://example.test/B)"
    def unmatched_graph_and_actual_citation_do_not_invent_link():
        unmatched = "어느 원천에도 없는 합성 인용문"
        row = {"evidence_edges": [dict(source="A", relation="SUPPLIES", target="B",
                                      origins=["B", "A"], evidences=[unmatched])]}
        _, _, evidence = build_graph_and_evidence([row], [])
        assert evidence[0]["source"]["stockCode"] == ""
        assert evidence[0]["source"]["url"] == "" and evidence[0]["source"]["reportName"] == ""
        citations = ns["_format_citations"]([row], [])
        assert "[G1]" in citations and unmatched in citations
        assert "example.test" not in citations
    def received_chunk_id_is_preserved_without_a_release_claim():
        chunk = dict(id='005930-0001-a1b2c3d4', stock_code='005930', company='synthetic',
                     text='synthetic source body', section='segment')
        context = json.loads(ns['_format_chunk_context']([chunk]))
        assert context[0]['chunk_id'] == chunk['id']
        citation = ns['_format_citations']([], [chunk])
        assert citation.startswith('[V1]') and chunk['id'] not in citation
        assert 'immutable release/version unconfirmed' in context[0]['chunk_id_semantics']
        for bad in ({}, {'id': 123}, {'id': 'bad'}, {'id': '005930-0001-a1b2c3d4', 'stock_code': '000001'},
                    {'id': '005930-0001-a1b2c3d4\nINJECT', 'stock_code': '005930'}):
            data = dict(chunk, **bad) if bad else {k:v for k,v in chunk.items() if k != 'id'}
            assert '조회청크 ID=' not in ns['_format_citations']([], [data])
            assert json.loads(ns['_format_chunk_context']([data]))[0]['chunk_id'] == ''
        assert chunk['id'] == '005930-0001-a1b2c3d4'
    def company_modules_and_facade_compatibility():
        from src.agents.industry.api.report.graph_payload import _edge_display_source_url
        name, url = _edge_display_source_url(["B", "A"], quote)
        assert name == "A report" and url.startswith("https://example.test/A")
        for relative in ("application/evidence_context.py", "api/report/graph_payload.py"):
            assert len((source / relative).read_text(encoding="utf-8").splitlines()) <= 400
    check("unmatched quote has no invented source", absent_does_not_choose_first)
    check("ellipsis fragments cannot combine source companies", split_quote_cannot_mix_companies)
    check("stock code report and URL share selected source", graph_metadata_uses_same_selected_company)
    check("short quote remains unattributed", short_quote_is_unattributed_not_rejected)
    check("ordered ellipsis uses a single source", ordered_same_source_ellipsis_is_supported)
    check("source I/O errors do not select wrong fallback", source_io_failure_cannot_choose_wrong_first_origin)
    check("structural no-quote provenance unchanged", structural_no_quote_provenance_preserves_legacy)
    check("actual citations and graph expose no invented link", unmatched_graph_and_actual_citation_do_not_invent_link)
    check("two-value helper and 400-line boundary preserved", company_modules_and_facade_compatibility)
    check("received chunk ID is not an immutable release", received_chunk_id_is_preserved_without_a_release_claim)
    print(f"{10-len(failures)}/10 company evidence regressions passed")
    if failures:
        raise AssertionError("Failed: " + ", ".join(failures))


if __name__ == "__main__":
    run_company_evidence_tests()
