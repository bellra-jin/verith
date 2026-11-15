"""Verifier-result validity checks without config/provider/source access."""
from __future__ import annotations


def run_faithfulness_tests():
    import ast
    import os
    from pathlib import Path
    import sys
    from types import ModuleType, SimpleNamespace as NS
    import unittest

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
    path = source / "application/faithfulness.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    nodes = [node for node in tree.body if not isinstance(node, ast.ImportFrom) or not node.level]
    module = ModuleType("isolated_faithfulness")
    sys.modules[module.__name__] = module
    def forbidden_factory(**kwargs):
        raise AssertionError("Actual verifier initialization forbidden")
    module.get_chat_llm = forbidden_factory
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), module.__dict__)

    class Model:
        def __init__(self, text):
            self.text, self.calls, self.prompts = text, 0, []
        def invoke(self, prompt):
            self.calls += 1
            self.prompts.append(prompt)
            return NS(content=self.text)

    class Cases(unittest.TestCase):
        def test_conflicting_duplicate_verdicts_are_indeterminate(self):
            for output in ("1: UNSUPPORTED\n1: SUPPORTED", "1: SUPPORTED\n1: UNSUPPORTED"):
                self.assertIsNone(module._parse_verdicts(output, 1))

        def test_supported_prefix_or_embedded_explanation_is_not_a_verdict(self):
            for output in ("1: SUPPORTED_BUT_UNCHECKED", "I think 1: SUPPORTED",
                           "1: SUPPORTED. maybe", "1: SUPPORTED\nextra explanation"):
                self.assertIsNone(module._parse_verdicts(output, 1))

        def test_extra_and_duplicate_indices_are_not_silently_ignored(self):
            for output in ("1: SUPPORTED\n2: SUPPORTED", "0: UNSUPPORTED\n1: SUPPORTED",
                           "1: SUPPORTED\n1: SUPPORTED"):
                self.assertIsNone(module._parse_verdicts(output, 1))

        def test_valid_and_missing_verdict_compatibility(self):
            self.assertEqual(module._parse_verdicts("1: SUPPORTED\n2: UNSUPPORTED", 2), [True, False])
            self.assertEqual(module._parse_verdicts("1: SUPPORTED", 2), [True, False])
            self.assertEqual(module._parse_verdicts("1) SUPPORTED\n2. SUPPORTED", 2), [True, True])

        def test_partial_refusal_does_not_skip_the_factual_claim(self):
            answer = "기업 A는 공급망 핵심 기업입니다. 시장점유율 정보가 없습니다."
            model = Model("1: UNSUPPORTED\n2: SUPPORTED")
            result = module.check_faithfulness(answer, ["합성 근거"], llm=model)
            self.assertEqual(model.calls, 1)
            self.assertTrue(result.checked)
            self.assertEqual(result.unsupported, ["기업 A는 공급망 핵심 기업입니다."])

        def test_known_whole_refusal_remains_unchecked_without_call(self):
            model = Model("1: SUPPORTED")
            result = module.check_faithfulness("근거에서 해당 연결을 찾지 못했습니다.", ["합성 근거"], llm=model)
            self.assertEqual(model.calls, 0)
            self.assertFalse(result.checked)
            self.assertEqual(result.outcome, "not_run")

        def test_claim_after_reference_marker_is_not_dropped(self):
            model = Model("1: UNSUPPORTED")
            result = module.check_faithfulness("[G1] 기업 A는 공급망 핵심 기업입니다.", ["합성 근거"], llm=model)
            self.assertEqual(model.calls, 1)
            self.assertTrue(result.checked)
            self.assertEqual(result.unsupported, ["[G1] 기업 A는 공급망 핵심 기업입니다."])

        def test_only_known_whole_refusal_sentence_is_excluded_from_composite(self):
            refusal = "근거에서 해당 연결을 찾지 못했습니다."
            answer = "기업 A는 공급망 핵심 기업입니다. " + refusal
            model = Model("1: UNSUPPORTED")
            result = module.check_faithfulness(answer, ["합성 근거"], llm=model)
            self.assertEqual(model.calls, 1)
            self.assertNotIn(refusal, model.prompts[0])
            self.assertIn(refusal, result.text)
            self.assertEqual(result.unsupported, ["기업 A는 공급망 핵심 기업입니다."])

        def test_negated_facts_and_refusal_like_phrases_are_still_checked(self):
            answer = "기업 A는 B와 경쟁하지 않습니다. 정보가 없다는 뜻은 아닙니다."
            model = Model("1: SUPPORTED" + chr(10) + "2: SUPPORTED")
            result = module.check_faithfulness(answer, ["합성 근거"], llm=model)
            self.assertEqual(model.calls, 1)
            self.assertTrue(result.checked)
            self.assertEqual(result.text, answer)
            self.assertEqual(len(module._split_sentences(answer)), 2)

        def test_bare_reference_marker_is_not_a_factual_sentence(self):
            model = Model("1: SUPPORTED")
            result = module.check_faithfulness("[G1] [V2]", ["합성 근거"], llm=model)
            self.assertFalse(result.checked)
            self.assertEqual(model.calls, 0)

        def test_unknown_labels_and_empty_output_are_indeterminate(self):
            for output in ("1: UNKNOWN", "", "   ", "1: probably supported"):
                result = module.check_faithfulness("기업 A는 공급합니다.", ["합성 근거"], llm=Model(output))
                self.assertFalse(result.checked)
                self.assertEqual(result.outcome, "indeterminate")

        def test_list_markers_and_decimal_claims_are_preserved(self):
            answer = "1. 기업 A의 비율은 3.25%입니다." + chr(10) + "2. 기업 B는 공급하지 않습니다."
            self.assertEqual(len(module._split_sentences(answer)), 2)
            result = module.check_faithfulness(answer, ["합성 근거"],
                llm=Model("1: SUPPORTED" + chr(10) + "2: SUPPORTED"))
            self.assertTrue(result.checked)
            self.assertEqual(result.text, answer)

        def test_malformed_verifier_never_becomes_checked_clean(self):
            model = Model("1: UNSUPPORTED\n1: SUPPORTED")
            result = module.check_faithfulness("기업 A는 공급합니다.", ["합성 근거"], llm=model)
            self.assertFalse(result.checked)
            self.assertEqual(result.outcome, "indeterminate")

    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Cases))
    if not result.wasSuccessful():
        raise AssertionError("Faithfulness validity regression failed")


if __name__ == "__main__":
    run_faithfulness_tests()
