"""Run pure Industry export checks without importing config/graph/provider modules."""
from __future__ import annotations


def run_export_tests():
    import ast
    import os
    from pathlib import Path
    import runpy
    import sys
    from types import ModuleType

    root = Path(__file__).resolve().parents[2]
    source = root / "src/agents/industry"
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(root))
    assets = {source / "api/report/report_template.html", source / "api/report/support.js"}

    def guard(event, args):
        if event in {"socket.connect", "socket.getaddrinfo", "subprocess.Popen", "os.system"}:
            raise AssertionError("External operation blocked: " + event)
        if event == "open" and isinstance(args[0], (str, bytes)):
            path = Path(os.fsdecode(args[0])).resolve()
            mode, flags = args[1:3]
            if (isinstance(mode, str) and any(c in mode for c in "wax+")) or flags & (os.O_WRONLY | os.O_RDWR):
                raise AssertionError("File write blocked")
            if path.name == ".env" or (path.is_relative_to(root) and path.suffix not in {".py", ".pyc"} and path not in assets):
                raise AssertionError("Project configuration/data read blocked")
    sys.addaudithook(guard)

    path = source / "application/report_export.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    safe_modules = {"argparse", "json", "re", "sys", "collections", "datetime", "pathlib", "typing", "__future__"}
    nodes = [node for node in tree.body if
             isinstance(node, (ast.FunctionDef, ast.Assign)) or
             isinstance(node, ast.Import) and all(a.name in safe_modules for a in node.names) or
             isinstance(node, ast.ImportFrom) and node.module in safe_modules and not node.level]
    from src.agents.industry.domain.answer_verification import bound_verification
    module = ModuleType("src.agents.industry.application.report_export")
    module.bound_verification = bound_verification
    from src.agents.industry.api.report.pipeline import _pipeline_steps
    module._pipeline_steps = _pipeline_steps
    from src.agents.industry.api.report import graph_payload
    for name in ("MAX_TAGS", "_extract_tags", "_slug", "build_graph_and_evidence"):
        module.__dict__[name] = getattr(graph_payload, name)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), module.__dict__)
    sys.modules[module.__name__] = module
    # Graph provenance metadata is unavailable here; never import retrieval/config as a fallback.
    graph_payload._edge_source_metadata = lambda origins, quote: ("", "", "")
    faith_path = source / "application/faithfulness.py"
    faith_tree = ast.parse(faith_path.read_text(encoding="utf-8"))
    faith_nodes = [n for n in faith_tree.body if not isinstance(n, ast.ImportFrom) or not n.level]
    faith = ModuleType("src.agents.industry.application.faithfulness")
    sys.modules[faith.__name__] = faith
    def provider_forbidden(**kwargs):
        raise AssertionError("Provider initialization blocked")
    faith.get_chat_llm = provider_forbidden
    exec(compile(ast.Module(body=faith_nodes, type_ignores=[]), str(faith_path), "exec"), faith.__dict__)
    import json
    from types import SimpleNamespace
    from src.agents.industry.domain.answer_policy import ANSWER_TEMPLATE
    from src.agents.industry.domain.company_scope import CompanyScope, company_scope_policy
    from src.agents.industry.domain.answer_verification import AnswerVerification, answer_binding
    from src.agents.industry.domain.result_scope import MAX_CONTEXT_ROWS, limit_query_rows, row_scope_notice

    retrieval_path = source / "application/retrieval.py"
    retrieval_tree = ast.parse(retrieval_path.read_text(encoding="utf-8"))
    generator = next(n for n in retrieval_tree.body if isinstance(n, ast.FunctionDef) and n.name == "generate_answer")
    generation_ns = dict(AnswerVerification=AnswerVerification, answer_binding=answer_binding,
        CompanyScope=CompanyScope, company_scope_policy=company_scope_policy,
        json=json, MAX_CONTEXT_ROWS=MAX_CONTEXT_ROWS, ANSWER_TEMPLATE=ANSWER_TEMPLATE,
        limit_query_rows=limit_query_rows, row_scope_notice=row_scope_notice,
        check_faithfulness=faith.check_faithfulness, get_chat_llm=provider_forbidden,
        _strip_evidence=lambda row: row, _format_chunk_context=json.dumps,
        _evidence_lines=lambda rows, chunks: ["synthetic evidence"] if rows or chunks else [],
        _format_citations=lambda rows, chunks: "[G1] synthetic source" if rows or chunks else "")
    exec(compile(ast.Module(body=[generator], type_ignores=[]), str(retrieval_path), "exec"), generation_ns)
    agent_path = source / "application/agent.py"
    agent_tree = ast.parse(agent_path.read_text(encoding="utf-8"))
    answer_node = next(n for n in agent_tree.body if isinstance(n, ast.FunctionDef) and n.name == "_generate_answer")

    def run_answer(*, question="synthetic question", rows=None, chunks=None,
                   verdict="1: SUPPORTED", failure=False, verify=True,
                   answer="기업 A는 공급합니다.", company_scope=None):
        calls = []
        class Model:
            def __init__(self, verifier=False):
                self.verifier = verifier
            def invoke(self, prompt):
                calls.append("verify" if self.verifier else "answer")
                if self.verifier and failure:
                    raise RuntimeError("synthetic verifier failure")
                return SimpleNamespace(content=verdict if self.verifier else answer)
        def generate(*args, **kwargs):
            return generation_ns["generate_answer"](*args, **kwargs, verify=verify,
                verify_llm=Model(verifier=True))
        ns = dict(AgentState=dict, AnswerVerification=AnswerVerification, generate_answer=generate)
        exec(compile(ast.Module(body=[answer_node], type_ignores=[]), str(agent_path), "exec"), ns)
        state = dict(question=question, rows=[{"company": "A"}] if rows is None else rows,
                     chunks=[] if chunks is None else chunks, company_scope=company_scope)
        state.update(ns["_generate_answer"](state, llm=Model()))
        return state, calls

    boundary = ModuleType("industry_test_boundary")
    boundary.run_answer = run_answer
    sys.modules[boundary.__name__] = boundary
    render = ModuleType("src.agents.industry.api.report.render")
    render.__dict__.update(runpy.run_path(str(source / "api/report/render.py")))
    sys.modules["src.agents.industry.api.report.render"] = render
    tests = {}
    for filename in ("test_report_export.py", "test_verification_status.py"):
        ns = runpy.run_path(str(root / "tests/industry" / filename))
        for name, function in ns.items():
            if name.startswith("test_"):
                if name in tests:
                    raise AssertionError("Duplicate test name")
                tests[name] = function
    failures = []
    for name, function in sorted(tests.items()):
        try:
            function()
            print("PASS", name)
        except Exception as exc:
            failures.append(name)
            print("FAIL", name, type(exc).__name__, str(exc))
    print(f"{len(tests)-len(failures)}/{len(tests)} Industry export regressions passed")
    if failures:
        raise AssertionError("Failed regressions: " + ", ".join(failures))


if __name__ == "__main__":
    run_export_tests()
