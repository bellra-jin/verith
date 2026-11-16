"""AI retained-row scope only; no DB execution/time/cost guarantee."""
from __future__ import annotations


def run_scope_tests():
    import ast
    import os
    from pathlib import Path
    import sys
    from types import SimpleNamespace as NS

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
    from src.agents.industry.domain.cypher_guard import UnsupportedCypher, validate_generated_cypher
    from src.agents.industry.domain.result_scope import limit_query_rows
    path = source / "application/agent.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_execute_cypher")
    ns = dict(AgentState=dict, limit_query_rows=limit_query_rows, UnsupportedCypher=UnsupportedCypher,
              validate_generated_cypher=validate_generated_cypher)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), ns)
    original = [{"row": index, "nested": {"value": index}} for index in range(51)]
    state = ns["_execute_cypher"]({"cypher": "MATCH(n) RETURN n"}, graph=NS(query=lambda query: original))
    assert len(state["rows"]) == 50
    assert state["query_rows_truncated"] is True
    assert len(original) == 51
    print("PASS retained rows bounded without rewriting source results")
    from src.agents.industry.domain.result_scope import MAX_CONTEXT_ROWS, row_scope_notice
    from copy import deepcopy
    state["rows"][0]["nested"]["value"] = "changed retained copy"
    assert original[0]["nested"]["value"] == 0
    original[1]["nested"]["value"] = "changed original"
    assert state["rows"][1]["nested"]["value"] == 1
    for count in (0, 1, 49, 50, 51, 100):
        rows, clipped = limit_query_rows([{"row": i} for i in range(count)])
        assert len(rows) == min(count, MAX_CONTEXT_ROWS)
        assert clipped is (count > MAX_CONTEXT_ROWS)
    consumed = []
    def lazy_rows():
        for i in range(1000):
            consumed.append(i)
            yield {"row": i}
    rows, clipped = limit_query_rows(lazy_rows())
    assert len(rows) == 50 and clipped and len(consumed) == 51
    assert row_scope_notice(False) == "" and row_scope_notice("true") == ""
    print("PASS cap boundaries, copy independence and cap-plus-one lazy observation")

    for invalid in (None, ["not a row"], [{"valid": True}, None]):
        try:
            limit_query_rows(invalid)
        except ValueError as exc:
            assert str(exc) == "Unsupported query-result row shape"
        else:
            raise AssertionError("Bad result shape accepted")
    def bad_graph(query):
        raise RuntimeError("synthetic read error")
    failed = ns["_execute_cypher"]({"cypher": "MATCH(n) RETURN n",
                                   "query_rows_truncated": True}, graph=NS(query=bad_graph))
    assert failed["rows"] == [] and failed["query_rows_truncated"] is False and failed["error"]
    print("PASS malformed/error result cannot masquerade as clipped usable data")

    import json
    import re
    from datetime import datetime
    from typing import Any
    from src.agents.industry.domain.answer_policy import ANSWER_TEMPLATE
    from src.agents.industry.domain.company_scope import CompanyScope, company_scope_policy
    from src.agents.industry.domain.answer_verification import AnswerVerification, answer_binding, bound_verification
    from src.agents.industry.api.report.graph_payload import MAX_TAGS, _extract_tags, _slug, build_graph_and_evidence
    from src.agents.industry.api.report.pipeline import _pipeline_steps
    prompts, used_evidence, used_citations = [], [], []
    def invoke(prompt):
        prompts.append(prompt)
        return NS(content="근거 기반 합성 답변입니다.")
    def evidence(rows, chunks):
        used_evidence.append(deepcopy(rows))
        return ["synthetic evidence"]
    def citations(rows, chunks):
        used_citations.append(deepcopy(rows))
        return "[G1] synthetic source"
    retrieval_path = source / "application/retrieval.py"
    retrieval_tree = ast.parse(retrieval_path.read_text(encoding="utf-8"))
    generate = next(n for n in retrieval_tree.body if isinstance(n, ast.FunctionDef) and n.name == "generate_answer")
    generation_ns = dict(AnswerVerification=AnswerVerification, answer_binding=answer_binding,
        CompanyScope=CompanyScope, company_scope_policy=company_scope_policy,
        json=json, MAX_CONTEXT_ROWS=MAX_CONTEXT_ROWS, ANSWER_TEMPLATE=ANSWER_TEMPLATE,
        limit_query_rows=limit_query_rows, row_scope_notice=row_scope_notice,
        _strip_evidence=lambda row: row, _format_chunk_context=json.dumps,
        _evidence_lines=evidence, _format_citations=citations,
        check_faithfulness=lambda answer, lines, **kwargs: NS(text=answer, outcome="checked", unsupported=[]),
        get_chat_llm=lambda **kwargs: NS(invoke=invoke))
    exec(compile(ast.Module(body=[generate], type_ignores=[]), str(retrieval_path), "exec"), generation_ns)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_generate_answer")
    answer_ns = dict(AgentState=dict, generate_answer=generation_ns["generate_answer"])
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), answer_ns)
    state = ns["_execute_cypher"]({"cypher": "MATCH(n) RETURN n"},
                                  graph=NS(query=lambda query: [{"row": i} for i in range(51)]))
    state.update(question="synthetic", chunks=[], cypher="MATCH(n) RETURN n")
    state.update(answer_ns["_generate_answer"](state, llm=NS(invoke=invoke)))
    assert len(used_evidence[-1]) == 50 and len(used_citations[-1]) == 50
    assert '"row": 49' in prompts[-1] and '"row": 50' not in prompts[-1]
    assert row_scope_notice(True) in prompts[-1] and row_scope_notice(True) in state["answer"]
    assert bound_verification(state) is state["answer_verification"]
    print("PASS actual answer node, prompt, evidence, citations and binding share retained scope")

    report_path = source / "application/report_export.py"
    report_tree = ast.parse(report_path.read_text(encoding="utf-8"))
    names = {"_now_iso", "parse_answer", "_headline_from_body", "_retrieval_flow",
             "build_report_payload", "_question_label"}
    report_ns = dict(Any=Any, json=json, re=re, datetime=datetime, SCHEMA_VERSION="research-report.v1",
                     LOCALE="ko-KR", MAX_TAGS=MAX_TAGS, _extract_tags=_extract_tags, _slug=_slug,
                     build_graph_and_evidence=build_graph_and_evidence, _pipeline_steps=_pipeline_steps,
                     bound_verification=bound_verification)
    definitions = [n for n in report_tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    exec(compile(ast.Module(body=definitions, type_ignores=[]), str(report_path), "exec"), report_ns)
    payload = report_ns["build_report_payload"](state, graph_snapshot={"nodes": {}, "relationships": {}})
    assert payload["metrics"]["rows"] == 50
    assert row_scope_notice(True) in payload["answer"]["body"]
    assert "query_rows_truncated" not in json.dumps(payload, ensure_ascii=False, allow_nan=False)
    from src.agents.industry.api.report.render import validate_payload
    validate_payload(payload)
    print("PASS actual existing payload exposes limitation without a new schema field")

    entry_names = {"answer_question", "main"}
    entry_nodes = [n for n in retrieval_tree.body if isinstance(n, ast.FunctionDef) and n.name in entry_names]
    generation_ns.update(generate_cypher=lambda *args, **kwargs: "MATCH(n) RETURN n", CYPHER_SCHEMA="synthetic")
    exec(compile(ast.Module(body=entry_nodes, type_ignores=[]), str(retrieval_path), "exec"), generation_ns)
    result = generation_ns["answer_question"]("synthetic", graph=NS(query=lambda query: original),
                                             qa_llm=NS(invoke=invoke))
    assert len(result["rows"]) == 50 and row_scope_notice(True) in result["answer"]
    import io
    from contextlib import redirect_stdout
    args = NS(question="synthetic", cypher_only=False, show_cypher=False)
    class Parser:
        def add_argument(self, *args, **kwargs):
            pass
        def parse_args(self):
            return args
    closed = []
    generation_ns.update(argparse=NS(ArgumentParser=lambda **kwargs: Parser()),
                         get_neo4j_graph=lambda: NS(query=lambda query: original, close=lambda: closed.append(True)))
    output = io.StringIO()
    with redirect_stdout(output):
        assert generation_ns["main"]() is None
    assert closed == [True] and row_scope_notice(True) in output.getvalue()
    print("PASS direct answer_question and CLI retain the same limited view")

    initialized = []
    generation_ns["get_chat_llm"] = lambda **kwargs: initialized.append(True) or NS(invoke=invoke)
    before = len(prompts)
    try:
        generation_ns["generate_answer"]("synthetic", ["bad result row"])
    except ValueError:
        pass
    else:
        raise AssertionError("Malformed rows must fail before model invocation")
    assert len(prompts) == before and initialized == []
    print("All retained-result scope regressions passed")


if __name__ == "__main__":
    run_scope_tests()
