"""Pure synthetic candidate checks; no collection, output files, DB or provider."""
from __future__ import annotations


def run_candidate_tests():
    import ast
    from dataclasses import dataclass, field
    import os
    from pathlib import Path
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
    path = source / "infrastructure/extraction/extract.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    declarations = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Triple" or
                    isinstance(n, ast.FunctionDef) and n.name in {"raw_to_triples", "merge_triples"}]
    from src.agents.industry.domain.schema import REL_SHAPES
    from src.agents.industry.domain.triples import Triple, merge_triples
    from src.agents.industry.domain.candidates import normalize_candidates
    from src.agents.industry.domain.candidate_review import build_candidate_review
    ns = dict(Triple=Triple, merge_triples=merge_triples, normalize_candidates=normalize_candidates,
              dataclass=dataclass, field=field, REL_SHAPES=REL_SHAPES, SYMMETRIC_RELATIONS={"COMPETES_WITH"},
              by_stock_code=lambda code: None, is_self_reference=lambda name: False,
              normalize_name=lambda name, typ: name, _load_source_norm=lambda origin: "source",
              _write_evidence_rejects=lambda rows: None)
    exec(compile(ast.Module(body=declarations, type_ignores=[]), str(path), "exec"), ns)
    sample = dict(source="A", source_type="Company", type="SUPPLIES", target="B",
                  target_type="Company", origin="source-A", evidence="fabricated quote")
    ns["verify_evidence"] = lambda quote, text: (False, 0)
    rejected = ns["raw_to_triples"]([sample])
    assert rejected == [], "Rejected citation must not leave its asserted relation"
    print("PASS rejected relation removed")
    ns["verify_evidence"] = lambda quote, text: (True, 100)
    accepted = ns["raw_to_triples"]([sample])
    assert len(accepted) == 1 and accepted[0].evidences == {"fabricated quote"}
    print("PASS supported relation preserved")

    logs, observations, quarantine = [], [], []
    ns["_write_evidence_rejects"] = lambda records: logs.extend(records)
    def check(row, expected_status, expected_reason=None):
        logs.clear()
        observations.clear()
        quarantine.clear()
        result = ns["raw_to_triples"]([row], verification_observations=observations,
                                      quarantined_candidates=quarantine)
        assert observations[0]["status"] == expected_status, observations
        if expected_reason:
            assert observations[0]["reason"] == expected_reason, observations
        assert bool(logs) is (expected_status == "rejected")
        assert bool(result) is (expected_status == "supported")
        assert len(quarantine) == (1 if expected_status in {"not_run", "indeterminate"} else 0)
        if quarantine:
            assert quarantine[0]["candidate"] == row
            assert quarantine[0]["observation"] == observations[0]
        return result

    ns["verify_evidence"] = lambda quote, text: (False, 12)
    check(sample, "rejected", "quote_rejected")
    assert logs[0]["evidence"] == sample["evidence"] and logs[0]["origin"] == "source-A"
    ns["verify_evidence"] = lambda quote, text: (True, 100)
    assert check(sample, "supported")[0].evidences == {sample["evidence"]}
    assert check(dict(sample, evidence=""), "not_run", "no_quote") == []
    ns["_load_source_norm"] = lambda origin: ""
    ns["verify_evidence"] = lambda *args: (_ for _ in ()).throw(AssertionError("must not run"))
    assert check(sample, "not_run", "source_unavailable") == []

    ns["_load_source_norm"] = lambda origin: "source"
    for bad in ((None, 0), (0, 0), (1, 100), [False, 0], None):
        ns["verify_evidence"] = lambda *args, bad=bad: bad
        assert check(sample, "indeterminate", "invalid_verifier_result") == []
    ns["verify_evidence"] = lambda *args: (_ for _ in ()).throw(RuntimeError("synthetic"))
    assert check(sample, "indeterminate", "RuntimeError") == []
    ns["_load_source_norm"] = lambda origin: (_ for _ in ()).throw(OSError("synthetic"))
    check(sample, "indeterminate", "OSError")
    print("PASS skipped, missing source, errors and non-bool results distinguished")

    from copy import deepcopy
    ns["_load_source_norm"] = lambda origin: "source"
    ns["verify_evidence"] = lambda quote, text: (quote == "supported", 100 if quote == "supported" else 0)
    good = dict(sample, origin="source-B", evidence="supported")
    original = deepcopy([sample, good])
    result = ns["raw_to_triples"]([sample, good])
    merged = ns["merge_triples"](result)
    assert len(merged) == 1 and merged[0].origins == {"source-B"}
    assert merged[0].evidences == {"supported"}
    assert [sample, good] == original
    print("PASS rejected origin cannot contaminate supported duplicate")

    uncertain = dict(sample, evidence="", origin="source-C", context={"values": [1, 2]})
    logs.clear()
    observations.clear()
    quarantine.clear()
    result = ns["raw_to_triples"]([sample, good, uncertain],
        verification_observations=observations, quarantined_candidates=quarantine)
    assert len(result) == 1 and result[0].origins == {"source-B"}
    assert [item["status"] for item in observations] == ["rejected", "supported", "not_run"]
    assert len(logs) == 1 and len(quarantine) == 1
    assert quarantine[0]["candidate"]["origin"] == "source-C"
    quarantine[0]["candidate"]["context"]["values"].append(3)
    assert uncertain["context"]["values"] == [1, 2]
    uncertain["context"]["values"].append(4)
    assert quarantine[0]["candidate"]["context"]["values"] == [1, 2, 3]
    assert ns["raw_to_triples"]([dict(sample, evidence="")]) == []
    print("PASS unknown quarantined without input mutation or default export")

    structured = Triple("owner", "Company", "OWNS_STAKE", "target", "Company", {"structured"}, set(), "0")
    merged = ns["merge_triples"]([structured])
    assert merged[0].qota_rt == "0" and merged[0].origins == {"structured"}
    assert merged[0].evidences == set()
    print("PASS structured ownership values unchanged")
    for name in ("infrastructure/extraction/extract.py", "infrastructure/extraction/evidence_verification.py",
                 "domain/candidates.py", "domain/triples.py", "domain/candidate_review.py",
                 "infrastructure/extraction/cli_args.py"):
        assert len((source / name).read_text(encoding="utf-8").splitlines()) <= 400, name
    print("PASS candidate responsibility modules within 400 lines")
    import io
    from contextlib import redirect_stdout
    from types import SimpleNamespace as NS
    args = NS(company=None, limit=None, from_cache=True, skip_llm=False, no_shareholders=False)
    class Parser:
        def add_argument(self, *args, **kwargs):
            pass
        def parse_args(self):
            return args
    main_node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    main_ns = dict(ns, build_candidate_review=build_candidate_review, argparse=NS(ArgumentParser=lambda **kwargs: Parser()),
                   parse_extraction_args=lambda: args,
                   _select_companies=lambda *args: [NS(canonical="public synthetic company", stock_code="source-A")],
                   load_raw_cache=lambda: [dict(sample, evidence="", private_context="SECRET_CONTEXT")],
                   extract_ownstake_triples=lambda **kwargs: [structured], write_outputs=lambda rows: None)
    exec(compile(ast.Module(body=[main_node], type_ignores=[]), str(path), "exec"), main_ns)
    reviews, output = [], io.StringIO()
    with redirect_stdout(output):
        returned = main_ns["main"](review_records=reviews)
    assert returned is None
    assert len(reviews) == 1 and len(reviews[0]["quarantined_candidates"]) == 1
    assert reviews[0]["summary"]["retention"] == "process_memory_only"
    assert "SECRET_CONTEXT" not in output.getvalue() and sample["evidence"] not in output.getvalue()
    assert "process_memory_only" in output.getvalue()
    print("PASS main retains caller review without logging raw evidence")
    review = reviews[0]
    main_ns["load_raw_cache"] = lambda: []
    with redirect_stdout(io.StringIO()):
        assert main_ns["main"]() is None
    assert len(review["quarantined_candidates"]) == 1

    args.from_cache, args.skip_llm = False, True
    main_ns["load_raw_cache"] = lambda: (_ for _ in ()).throw(AssertionError("cache forbidden"))
    captured = []
    main_ns["write_outputs"] = captured.extend
    skip_reviews = []
    with redirect_stdout(io.StringIO()):
        assert main_ns["main"](review_records=skip_reviews) is None
    assert captured == [structured]
    assert skip_reviews[0]["summary"]["quarantined_count"] == 0
    assert all(count == 0 for count in skip_reviews[0]["summary"]["statuses"].values())
    print("PASS no-sink/structured-only main keeps return and independent review state")

    def fail_writer(rows):
        raise RuntimeError("synthetic output failure")
    main_ns["write_outputs"] = fail_writer
    failures = []
    try:
        with redirect_stdout(io.StringIO()):
            main_ns["main"](review_records=failures)
    except RuntimeError:
        pass
    else:
        raise AssertionError("Writer failure must not become success")
    assert len(failures) == 1
    print("PASS writer failure propagates without claiming persistence")

    from src.agents.industry.infrastructure.extraction.cli_args import parse_extraction_args
    cli = parse_extraction_args(["--company", "123456", "--limit", "2", "--from-cache", "--no-shareholders"])
    assert cli.company == "123456" and cli.limit == 2 and cli.from_cache and cli.no_shareholders
    assert cli.skip_llm is False
    assert parse_extraction_args(["--skip-llm"]).skip_llm is True
    sanitized = build_candidate_review([{"status": "indeterminate"}],
        [{"candidate": {"evidence": "SECRET_EVIDENCE"}, "observation": {"reason": "SECRET_EXCEPTION"}}])
    assert "SECRET" not in str(sanitized["summary"])
    print("PASS CLI flags compatible and review summary sanitized")
    print("All synthetic candidate regressions passed")


if __name__ == "__main__":
    run_candidate_tests()
