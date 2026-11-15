"""가짜 producer receipt의 PR88 멱등/충돌 계약. 실제 정산·신뢰 수집기와 구분한다."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
import runpy
import sys
from types import ModuleType
import unittest
from unittest.mock import patch
from uuid import UUID

HERE = Path(__file__).resolve().parent
SUPPORT = runpy.run_path(str(HERE / "test_call_usage_isolated.py"), run_name="usage_test_support")
ROOT = HERE.parents[2]


def source_module(name, path):
    module = ModuleType(name)
    module.__package__ = name.rpartition(".")[0]
    sys.modules[name] = module
    exec(compile(path.read_text(encoding="utf8"), str(path), "exec"), module.__dict__)
    return module


class ReceiptContractCases(unittest.TestCase):
    def setUp(self):
        modules = patch.dict(sys.modules)
        modules.start()
        self.addCleanup(modules.stop)
        self.client = SUPPORT["load_client"]()
        self.contract = source_module("src.modules.analysis.domain.contracts",
            ROOT / "backend/src/modules/analysis/domain/contracts.py")
        self.usage = source_module("isolated_backend_usage_evidence",
            ROOT / "backend/src/modules/fundamental/domain/usage_evidence.py")

    async def fixture(self):
        rows = []
        raw = dict(prompt_tokens=10, completion_tokens=5, total_tokens=15,
                   prompt_tokens_details={"cached_tokens": 2})
        sdk = SUPPORT["fake_sdk"]([[SUPPORT["payload"](usage=raw)]], [])
        with patch.dict(sys.modules, openai=sdk):
            await self.client.complete_structured(SUPPORT["Schema"], system="synthetic-system",
                prompt="synthetic-prompt", timeout=8, max_tokens=20,
                attempt_records=rows, stage="interpret")
        self.assertEqual(len(rows), 1)
        now = datetime(2026, 11, 14, tzinfo=UTC)
        context = self.contract.AnalysisContext(*(UUID(int=i) for i in (1,2,3,4)),
            "fundamental.analysis.v1", "a"*64, now, now + timedelta(seconds=60))
        # 테스트에서만 만든 별도 synthetic Backend expectation. producer만으로 신뢰를 얻지 않는다.
        call = {key: rows[0][key] for key in self.usage.CALL_FIELDS}
        spec = {key: call[key] for key in self.usage.SPEC_FIELDS - {"input_token_cap", "output_token_cap"}}
        spec.update(input_token_cap=100, output_token_cap=100)
        expected = self.usage.UsageExpectation(context, "b"*64,
            self.contract.canonical_json([spec]), inventory_closed=True)
        wire = dict(schema_version=self.usage.SCHEMA,
                    expectation_sha256=expected.fingerprint, calls=[call])
        return rows, expected, wire

    @SUPPORT["synchronous_coroutine"]
    async def test_same_id_identical_redelivery_is_idempotent(self):
        rows, expected, wire = await self.fixture()
        canonical = self.contract.canonical_json
        once = self.usage.classify_usage(expected, (canonical(wire),), usage_trusted=True)
        twice = self.usage.classify_usage(expected, (canonical(wire), canonical(wire)), usage_trusted=True)
        repeated_inside = dict(wire, calls=wire["calls"] * 2)
        inside = self.usage.classify_usage(expected, (canonical(repeated_inside),), usage_trusted=True)
        self.assertEqual(once, twice)
        self.assertEqual(once, inside)
        self.assertEqual(once.state, "complete_usage")
        self.assertEqual((once.input_tokens, once.cached_tokens, once.output_tokens, once.total_tokens), (10,2,5,15))
        self.assertEqual(len(self.contract.strict_json(once.calls_json)), 1)
        self.assertEqual(rows[0]["call_id"], wire["calls"][0]["call_id"])
        self.assertTrue(once.keep_reservation)
        # 동일한 bytes도 provenance의 독립 검증이 없으면 complete로 승격하지 않는다.
        untrusted = self.usage.classify_usage(expected, (canonical(wire), canonical(wire)))
        self.assertEqual((untrusted.state, untrusted.reason), ("unknown", "PROVENANCE_UNPROVEN"))
        self.assertIsNone(untrusted.total_tokens)

    @SUPPORT["synchronous_coroutine"]
    async def test_same_id_conflicting_numbers_reject_without_overwrite(self):
        rows, expected, original = await self.fixture()
        canonical = self.contract.canonical_json
        changed_call = dict(original["calls"][0], input_tokens=11, total_tokens=16)
        changed = dict(original, calls=[changed_call])
        self.assertEqual(changed_call["call_id"], rows[0]["call_id"])
        pair = (canonical(original), canonical(changed))
        forward = self.usage.classify_usage(expected, pair, usage_trusted=True)
        backward = self.usage.classify_usage(expected, tuple(reversed(pair)), usage_trusted=True)
        replayed = self.usage.classify_usage(expected, pair + (canonical(original),), usage_trusted=True)
        self.assertEqual(forward, backward)
        self.assertEqual(forward, replayed)
        self.assertEqual((forward.state, forward.reason), ("rejected", "CALL_CONFLICT"))
        self.assertEqual((forward.input_tokens, forward.cached_tokens, forward.output_tokens, forward.total_tokens), (None,)*4)
        retained = self.contract.strict_json(forward.calls_json)
        self.assertEqual(len(retained), 2)
        self.assertEqual({call["input_tokens"] for call in retained}, {10,11})
        self.assertTrue(all(call["call_id"] == rows[0]["call_id"] for call in retained))
        self.assertEqual(rows[0]["input_tokens"], 10)
        self.assertTrue(forward.keep_reservation)


if __name__ == "__main__":
    sys.addaudithook(SUPPORT["guard"])
    unittest.main(verbosity=2)
