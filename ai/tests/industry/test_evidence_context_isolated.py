"""근거 책임 분리 회귀. 제품 config import나 실제 원천 파일 읽기 없음."""
from __future__ import annotations
import ast
import json
from pathlib import Path
import re
import unittest
import urllib.parse

ROOT = Path(__file__).resolve().parents[2] / "src/agents/industry/application"


class FakeFile:
    def __init__(self, name, content, parent=None):
        self.name, self.content, self.parent = name, content, parent
        self.reads = 0
    def read_text(self, **kwargs):
        self.reads += 1
        return self.content
    def exists(self):
        return self.content is not None


class FakeCompany:
    def __init__(self, name, text):
        self.name = name
        self.text = FakeFile("business_content.txt", text)
    def __truediv__(self, name):
        assert name == "business_content.txt"
        return self.text


class FakeRoot:
    def __init__(self):
        self.companies = {"A": FakeCompany("A", "다른 기업 원문"),
                          "B": FakeCompany("B", "금리 상승으로 조달 비용이 증가했다.")}
        self.meta = [FakeFile("meta.json", json.dumps({"stock_code": code,
            "source_url": "https://example.test/" + code, "report_nm": "2024 공시"}), company)
            for code, company in self.companies.items()]
        self.globs = 0
    def glob(self, pattern):
        assert pattern == "*/meta.json"
        self.globs += 1
        return self.meta
    def __truediv__(self, name):
        return self.companies[name]


def isolated_helpers():
    path = ROOT / "evidence_context.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    # 제품 import를 실행하지 않고 stdlib와 메모리 원천만 주입한다.
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.Assign, ast.AnnAssign))]
    ns = dict(json=json, re=re, urllib=urllib, RAW_DIR=FakeRoot())
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), ns)
    return ns


class EvidenceContextTests(unittest.TestCase):
    def setUp(self):
        self.h = isolated_helpers()
        self.rows = [{"evidence_edges": [{"source": "B", "relation": "SUPPLIES", "target": "A",
            "evidences": ["금리 상승으로 조달 비용이 증가했다."], "origins": ["A", "B"]}]}]
        self.chunks = [{"company": "B", "section": "위험", "bsns_year": "2024",
            "report_nm": "2024 공시", "source_url": "https://example.test/B",
            "text": "[B] 위험\n금리 상승으로 조달 비용이 증가했다.", "score": 0.75}]

    def test_original_helpers_are_reexported_as_same_objects(self):
        path = ROOT / "retrieval.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = [n for n in tree.body if isinstance(n, ast.ImportFrom)
                   and n.module == "evidence_context" and n.level == 1]
        self.assertEqual(len(imports), 1)
        expected = {name for name, value in self.h.items() if callable(value) and name.startswith("_")}
        expected.discard("_received_chunk_id")  # New local helper, not an original facade API.
        self.assertEqual({a.name for a in imports[0].names}, expected)
        ns = {"__name__": "synthetic.consumer", "__package__": "synthetic"}
        import types
        import sys
        module = types.ModuleType("synthetic.evidence_context")
        module.__dict__.update(self.h)
        sys.modules[module.__name__] = module
        try:
            exec(compile(ast.Module(body=imports, type_ignores=[]), str(path), "exec"), ns)
            for name in expected:
                self.assertIs(ns[name], self.h[name])
        finally:
            del sys.modules[module.__name__]

    def test_filing_metadata_cache_and_source_selection(self):
        first = self.h["_load_filing_meta"]()
        self.assertIs(first, self.h["_load_filing_meta"]())
        self.assertEqual(self.h["RAW_DIR"].globs, 1)
        quote = "금리 상승으로 조달 비용이 증가했다."
        self.assertEqual(self.h["_pick_origin"](["A", "B"], quote), "B")
        self.h["_pick_origin"](["A", "B"], quote)
        self.assertEqual(self.h["RAW_DIR"].companies["B"].text.reads, 1)
        self.assertEqual(self.h["_pick_origin"](["A"], None), "A")
        self.assertIsNone(self.h["_pick_origin"]([], quote))

    def test_citations_keep_order_scope_and_correct_filing(self):
        text = self.h["_format_citations"](self.rows * 2, self.chunks)
        self.assertEqual(text.count("[G1]"), 1)
        self.assertNotIn("[G2]", text)
        self.assertLess(text.index("[G1]"), text.index("[V1]"))
        self.assertIn("https://example.test/B#:~:text=", text)
        self.assertNotIn("https://example.test/A", text)
        self.assertIn("2024 공시 · 2024", text)
        self.assertIn("score=0.750", text)

    def test_grounding_and_context_preserve_limits(self):
        lines = self.h["_evidence_lines"](self.rows, self.chunks * 8)
        self.assertEqual(len(lines), 6)
        self.assertNotIn("[B] 위험", lines[1])
        context = json.loads(self.h["_format_chunk_context"](self.chunks * 8))
        self.assertEqual(len(context), 5)
        self.assertEqual(context[0]["ref"], "V1")
        self.assertEqual(context[0]["bsns_year"], "2024")
        self.assertEqual(self.h["_strip_evidence"]({"x": self.rows}), {"x": [{}]})

    def test_overview_order_and_empty_behavior(self):
        row = {"산업별_소속": [{"industry": "소재", "n": 2, "sample": ["A", "B"]}],
               "공급_허브": [{"supplier": "A", "deg": 3}]}
        refs = self.h["_collect_overview_evidence"](row)
        self.assertTrue(refs[0].startswith("공급_허브"))
        self.assertTrue(refs[1].startswith("산업별_소속"))
        self.assertEqual(self.h["_format_citations"]([], []), "")
        self.assertEqual(self.h["_format_chunk_context"]([]), "[]")
        self.assertEqual(self.h["_evidence_lines"]([], []), [])

    def test_deeplink_encoding_and_no_url(self):
        self.assertEqual(self.h["_deeplink"]("", "quote"), "")
        self.assertEqual(self.h["_deeplink"]("https://example.test", None), "https://example.test")
        self.assertEqual(self.h["_text_fragment"]("A & B ... C,D"), "#:~:text=A%20%26%20B,C%2CD")


if __name__ == "__main__":
    unittest.main(verbosity=2)
