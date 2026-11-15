"""Generated-query boundary checks; fake graph/model only."""
from __future__ import annotations


def run_cypher_tests():
    import ast
    import os
    from pathlib import Path
    import re
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

    agent_path = source / "application/agent.py"
    tree = ast.parse(agent_path.read_text(encoding="utf-8"))
    execute = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_execute_cypher")
    from src.agents.industry.domain.cypher_guard import validate_generated_cypher, UnsupportedCypher
    from src.agents.industry.domain.result_scope import limit_query_rows
    ns = dict(AgentState=dict, limit_query_rows=limit_query_rows, validate_generated_cypher=validate_generated_cypher,
              UnsupportedCypher=UnsupportedCypher)
    exec(compile(ast.Module(body=[execute], type_ignores=[]), str(agent_path), "exec"), ns)
    calls = []
    graph = NS(query=lambda query: calls.append(query) or [{"unsafe": "executed"}])
    failures = []
    for query in ("MATCH (n) DETACH DELETE n", "CREATE (n:Company)", "CALL apoc.cypher.run('CREATE (n)', {})"):
        calls.clear()
        result = ns["_execute_cypher"]({"cypher": query}, graph=graph)
        if calls or result.get("rows"):
            failures.append(query)
    assert not failures, "Unsafe queries reached fake graph: " + str(failures)
    print("PASS explicit mutations/procedure calls blocked before graph")

    slash = chr(92)
    reads = [
        "MATCH (n:Company {name: 'CREATE SET DELETE CALL'}) RETURN n.name LIMIT 5",
        "MATCH (n) WHERE n.name = $create RETURN n",
        "MATCH (n) RETURN n." + chr(96) + "SET" + chr(96),
        "MATCH (n) // DELETE n; CALL apoc.foo()" + chr(10) + "RETURN n",
        "MATCH (n) /* DELETE n; CALL apoc.foo() */ RETURN count(n)",
        "RETURN 'text" + slash + "' CREATE' AS text",
        'RETURN "text' + slash + '" DELETE" AS text',
        "RETURN 'unicode" + slash + "uAC00' AS text",
        "RETURN CASE WHEN 1=1 THEN 'SET' ELSE 'DELETE' END AS label",
        "MATCH (n) WHERE EXISTS { MATCH (n)-[:SUPPLIES]->(m) RETURN m } RETURN n",
        "OPTIONAL MATCH (n) RETURN n;",
        "UNWIND [1, 2] AS value RETURN value",
        "RETURN " + chr(96) + "count" + chr(96) + "(1)",
    ]
    retrieval_path = source / "application/retrieval.py"
    retrieval_tree = ast.parse(retrieval_path.read_text(encoding="utf-8"))
    template_node = next(n.value for n in retrieval_tree.body if isinstance(n, ast.Assign)
                         and any(isinstance(t, ast.Name) and t.id == "CYPHER_GENERATION_TEMPLATE" for t in n.targets))
    template = ast.literal_eval(template_node)
    formatted = template.format(schema="synthetic schema", question="synthetic question")
    examples = re.findall(r"Cypher: (MATCH .*?)(?=\n\n#|\n\n질문:)", formatted, re.S)
    assert len(examples) == 5
    reads += examples
    for query in reads:
        assert validate_generated_cypher(query) is None
    print(f"PASS {len(reads)} normal/quoted/commented reads including all five prompt examples")

    blocked = [
        "", "CREATE (n)", "INSERT (n)", "MATCH (n) SET n.x=1 RETURN n",
        "MATCH (n) REMOVE n.x RETURN n", "MATCH(n) FOREACH (x IN [1] | DELETE n) RETURN n",
        "MATCH (n) RETURN n; MATCH (m) DELETE m", "MATCH(n) RETURN n;;",
        "CALL { MATCH(n) RETURN n } RETURN 1",
        "LOAD CSV FROM 'https://example.test/data' AS x RETURN x",
        "MATCH(n) RETURN apoc.cypher.run('CREATE(n)', {})",
        "MATCH(n) RETURN unknownFunction(n)", "MATCH(n) RETURN custom.count(n)",
        "CYPHER 25 MATCH(n) RETURN n", "PROFILE MATCH(n) RETURN n",
        "RETURN s'unsafe {customFunction()}'",
        "RETURN " + chr(96) + "MATCH" + chr(96) + "(1)",
        "RETURN range(1, 1000000000000)", "RETURN range(1, 3)",
        "RETURN " + chr(96) + "range" + chr(96) + "(1, 1000000)",
        "RETURN custom.range(1, 1000000)", "RETURN RANGE(1, 1000000)",
        "MATCH(n) /* outer /* nested */ RETURN n */ RETURN n",
        "MATCH(n) /* unterminated RETURN n",
        "MATCH(n) // comment" + chr(10) + "DELETE n",
        "MATCH(n) // " + slash + "u000a DELETE n",
        "MATCH(n) // " + chr(8232) + " DELETE n",
        "MATCH(n) RETURN n." + chr(96) + "field" + slash + "u0060" + chr(96),
        "RET/**/URN 1", "MATCH (n RETURN n", "MATCH(n) RETURN ]",
        "MATCH(n)", "RETURN 'unterminated", "RETURN 'bad" + slash + "q'",
    ]
    for query in blocked:
        try:
            validate_generated_cypher(query)
        except UnsupportedCypher as exc:
            assert str(exc) == "Generated Cypher is outside the supported read subset"
        else:
            raise AssertionError("Unsupported query accepted: " + query)
    for query in blocked:
        calls.clear()
        result = ns["_execute_cypher"]({"cypher": query}, graph=graph)
        assert calls == [] and result["rows"] == []
        assert result["error"] == "Generated Cypher is outside the supported read subset"
    calls.clear()
    read_state = ns["_execute_cypher"]({"cypher": reads[0]}, graph=graph)
    assert calls == [reads[0]] and read_state["error"] == ""
    assert read_state["rows"] == [{"unsafe": "executed"}]
    print(f"PASS {len(blocked)} write/procedure/escape/script/unsupported cases fail closed")

    from src.agents.industry.domain.cypher_guard import MAX_GENERATED_QUERY_CHARS
    at_limit = "RETURN 1" + " " * (MAX_GENERATED_QUERY_CHARS - len("RETURN 1"))
    validate_generated_cypher(at_limit)
    try:
        validate_generated_cypher(at_limit + " ")
    except UnsupportedCypher:
        pass
    else:
        raise AssertionError("Input cap exceeded")
    print("PASS input work cap boundary (not a DB execution/result budget)")

    generation_names = {"_extract_cypher", "generate_cypher", "answer_question", "main"}
    generation_nodes = [n for n in retrieval_tree.body if isinstance(n, ast.FunctionDef) and n.name in generation_names]
    def factory_forbidden(**kwargs):
        raise AssertionError("Actual model initialization forbidden")
    generation_ns = dict(re=re, limit_query_rows=limit_query_rows, CYPHER_GENERATION_TEMPLATE=template, CYPHER_SCHEMA="synthetic",
        validate_generated_cypher=validate_generated_cypher, get_chat_llm=factory_forbidden,
        generate_answer=lambda *args, **kwargs: "synthetic answer")
    exec(compile(ast.Module(body=generation_nodes, type_ignores=[]), str(retrieval_path), "exec"), generation_ns)
    class Model:
        def __init__(self, text):
            self.text = text
        def invoke(self, prompt):
            return NS(content=self.text)
    calls.clear()
    safe_query = "MATCH(n) RETURN n LIMIT 5"
    result = generation_ns["answer_question"]("synthetic", graph=graph, cypher_llm=Model(safe_query))
    assert calls == [safe_query] and result["cypher"] == safe_query
    for query in blocked[1:]:
        calls.clear()
        try:
            generation_ns["answer_question"]("synthetic", graph=graph, cypher_llm=Model(query))
        except UnsupportedCypher:
            pass
        else:
            raise AssertionError("Generated unsupported query was not rejected")
        assert calls == []
    print("PASS actual generation and answer_question paths block before fake graph")

    args = NS(question="synthetic", cypher_only=False, show_cypher=False)
    class Parser:
        def add_argument(self, *args, **kwargs):
            pass
        def parse_args(self):
            return args
    closed = []
    cli_graph = NS(query=lambda query: calls.append(query), close=lambda: closed.append(True))
    generation_ns.update(argparse=NS(ArgumentParser=lambda **kwargs: Parser()),
        get_neo4j_graph=lambda: cli_graph, get_chat_llm=lambda **kwargs: Model("CREATE(n)"))
    calls.clear()
    try:
        generation_ns["main"]()
    except UnsupportedCypher:
        pass
    else:
        raise AssertionError("CLI generated write was not rejected")
    assert calls == [] and closed == [True]
    print("PASS actual CLI generation blocks query and closes owned fake graph")
    node_names = {"_augmented_question", "_generate_cypher", "_should_retry",
                  "_retrieve_chunks", "_generate_answer"}
    node_functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in node_names]
    hint_node = next(n.value for n in tree.body if isinstance(n, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == "_RETRY_HINT" for t in n.targets))
    node_ns = dict(AgentState=dict, MAX_ATTEMPTS=3, _RETRY_HINT=ast.literal_eval(hint_node),
                   generate_cypher=generation_ns["generate_cypher"], UnsupportedCypher=UnsupportedCypher)
    exec(compile(ast.Module(body=node_functions, type_ignores=[]), str(agent_path), "exec"), node_ns)
    calls.clear()
    state = {"question": "synthetic", "attempts": 0}
    state.update(node_ns["_generate_cypher"](state, schema="synthetic", llm=Model("CREATE (:PRIVATE_NODE)")))
    assert state["cypher_rejected"] is True and state["attempts"] == 1
    assert state["cypher"] == "" and "PRIVATE_NODE" not in str(state)
    state.update(ns["_execute_cypher"](state, graph=graph))
    assert state["rows"] == [] and state["error"] and calls == []
    assert node_ns["_should_retry"](state) == "vector"
    qa_calls, vector_calls = [], []
    def vector_search(question, **kwargs):
        vector_calls.append((question, kwargs))
        return [{"company": "synthetic A", "text": "synthetic source"}]
    def answer(*args, **kwargs):
        qa_calls.append((args, kwargs))
        return "synthetic fallback answer"
    def retrieve_company_chunks(state, *, graph):
        return {"chunks": vector_search(state["question"], k=5, company="synthetic A", graph=graph),
                "error": state.get("error", "")}
    node_ns.update(retrieve_company_chunks=retrieve_company_chunks,
                   vector_search=vector_search, generate_answer=answer)
    state.update(node_ns["_retrieve_chunks"](state, graph=graph))
    state.update(node_ns["_generate_answer"](state, llm=NS()))
    assert len(vector_calls) == 1 and len(qa_calls) == 1 and calls == []
    assert qa_calls[0][0][1] == [] and qa_calls[0][0][2] == state["chunks"]
    assert state["answer"] == "synthetic fallback answer" and state["error"]
    assert "PRIVATE_NODE" not in str(state)
    print("PASS actual generation node preserves fail-closed vector fallback")

    state.update(node_ns["_generate_cypher"](state, schema="synthetic", llm=Model(safe_query)))
    assert state["cypher_rejected"] is False and state["attempts"] == 2
    state.update(ns["_execute_cypher"](state, graph=graph))
    assert node_ns["_should_retry"](state) == "answer"
    def db_failure(query):
        raise RuntimeError("synthetic read failure")
    state.update(ns["_execute_cypher"](state, graph=NS(query=db_failure)))
    assert node_ns["_should_retry"](state) == "retry"
    state["attempts"] = 3
    assert node_ns["_should_retry"](state) == "vector"
    try:
        node_ns["_generate_cypher"]({"question": "synthetic"},
            schema="synthetic", llm=NS(invoke=lambda prompt: (_ for _ in ()).throw(RuntimeError("synthetic model failure"))))
    except RuntimeError:
        pass
    else:
        raise AssertionError("Unrelated provider failure must not be misclassified as query rejection")
    print("PASS rejection flag resets and existing read retry/provider-failure semantics remain")
    print("All synthetic Cypher boundary regressions passed")


if __name__ == "__main__":
    run_cypher_tests()
