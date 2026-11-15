"""stdlib 격리 회귀: python -I -S tests/fundamental/test_call_usage_isolated.py.
설정/SDK/pydantic은 fake이며 실제 공급자·graph·DB를 import하지 않는다.
"""
from __future__ import annotations

import asyncio
import ast
from contextvars import copy_context
import dataclasses
import hashlib
import json
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace as NS
import unittest
from unittest.mock import patch
from uuid import UUID

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src/agents/fundamental"
sys.dont_write_bytecode = True


def guard(event, args):
    if event in {"socket.connect", "socket.getaddrinfo", "subprocess.Popen", "os.system"}:
        raise AssertionError("외부 부작용 차단: " + event)
    if event == "open" and isinstance(args[0], (str, bytes)):
        path = Path(os.fsdecode(args[0])).resolve()
        mode, flags = args[1:3]
        if (isinstance(mode, str) and any(c in mode for c in "wax+")) or flags & (os.O_WRONLY | os.O_RDWR):
            raise AssertionError("테스트 중 파일 쓰기 차단")
        if path.name == ".env" or path.suffix not in {".py", ".pyc"}:
            raise AssertionError("설정/자료 읽기 차단")


class FakeValidationError(ValueError):
    def errors(self):
        return [{"type": "synthetic_schema_error"}]


class Schema:
    @classmethod
    def model_validate_json(cls, content):
        try:
            data = json.loads(content)
            if data != {"ok": True}:
                raise ValueError()
        except ValueError:
            raise FakeValidationError() from None
        return data


def load_client():
    prefix = "isolated_fundamental"
    for tail in ("", ".core", ".infrastructure", ".infrastructure.llm"):
        name = prefix + tail
        module = ModuleType(name)
        module.__path__ = []
        sys.modules[name] = module
    config = ModuleType(prefix + ".core.config")
    config.settings = NS(QWEN_BASE_URL="https://synthetic.invalid", LLM_DUMMY_KEY="fake-key",
                         QWEN_MODEL="synthetic-qwen", OPENAI_API_KEY="fake-openai-key",
                         OPENAI_MODEL="synthetic-openai")
    sys.modules[config.__name__] = config
    fake_pydantic = ModuleType("pydantic")
    fake_pydantic.BaseModel = Schema
    fake_pydantic.ValidationError = FakeValidationError
    sys.modules["pydantic"] = fake_pydantic
    for leaf in ("usage", "client"):
        name = prefix + ".infrastructure.llm." + leaf
        module = ModuleType(name)
        module.__package__ = prefix + ".infrastructure.llm"
        sys.modules[name] = module
        path = SOURCE / "infrastructure/llm" / (leaf + ".py")
        exec(compile(path.read_text(encoding="utf8"), str(path), "exec"), module.__dict__)
    return module


class FakeResponse:
    def __init__(self, payload, success=True):
        self.payload, self.is_success = payload, success

    async def aread(self):
        return b""

    def json(self):
        return self.payload


def payload(*, content='{"ok":true}', usage=None, tier="default"):
    return dict(content=content, usage=usage, service_tier=tier, model="returned-model")


def fake_sdk(scenarios, clients):
    class HttpClient:
        def __init__(self, *, event_hooks):
            self.hooks = event_hooks

    class Client:
        def __init__(self, **kwargs):
            # max_retries를 덮어쓰지 않아 기존 SDK 자동 retry 정책을 유지한다.
            assert "max_retries" not in kwargs
            clients.append(kwargs)
            self.hooks = kwargs["http_client"].hooks
            self.chat = NS(completions=NS(create=self.create))

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def create(self, **kwargs):
            events = scenarios.pop(0)
            for event in events:
                request = NS(content=json.dumps(kwargs).encode())
                await self.hooks["request"][0](request)
                if isinstance(event, BaseException):
                    raise event
                if event == "sdk_timeout_retry":
                    continue
                if event == "sdk_http_retry":
                    await self.hooks["response"][0](FakeResponse({"usage": {"prompt_tokens": 7}}, False))
                    continue
                await self.hooks["response"][0](FakeResponse(event))
                raw = event.get("sdk_usage", event["usage"])
                usage = None if raw is None else NS(**raw)
                if raw is not None and isinstance(raw.get("prompt_tokens_details"), dict):
                    usage.prompt_tokens_details = NS(**raw["prompt_tokens_details"])
                return NS(choices=[NS(message=NS(content=event["content"]))], usage=usage)
            raise AssertionError("fake SDK 시나리오에 최종 결과가 없음")

    module = ModuleType("openai")
    module.AsyncOpenAI, module.DefaultAsyncHttpxClient = Client, HttpClient
    return module


def synchronous_coroutine(method):
    # 모든 fake await는 즉시 완료된다. Windows asyncio socketpair 생성도 하지 않는다.
    def run(self):
        coroutine = method(self)
        try:
            coroutine.send(None)
        except StopIteration:
            return
        finally:
            coroutine.close()
        raise AssertionError("격리 fake가 외부 이벤트 루프를 요구함")
    return run


class UsageCases(unittest.TestCase):
    def setUp(self):
        modules = patch.dict(sys.modules)
        modules.start()
        self.addCleanup(modules.stop)
        self.client = load_client()
        self.clients, self.rows = [], []

    async def run_fake(self, scenarios, stage="interpret"):
        with patch.dict(sys.modules, openai=fake_sdk(scenarios, self.clients)):
            result = await self.client.complete_structured(Schema, system="private-system",
                prompt="private-prompt", timeout=8, max_tokens=20,
                attempt_records=self.rows, stage=stage)
        self.assertEqual(scenarios, [])
        return result

    def assert_ids(self):
        ids = [row["call_id"] for row in self.rows]
        self.assertEqual(len(ids), len(set(ids)))
        for row in self.rows:
            self.assertEqual(str(UUID(row["call_id"])), row["call_id"])
            self.assertNotEqual(UUID(row["call_id"]).int, 0)
            for key in ("request_sha256", "policy_sha256"):
                self.assertEqual(len(row[key]), 64)
            self.assertNotIn("private-", json.dumps(row))
            self.assertNotIn("fake-key", json.dumps(row))
            self.assertNotIn("complete", row)
            self.assertNotIn("usage_trusted", row)

    @synchronous_coroutine
    async def test_1_complete_known_zero_and_request_binding(self):
        usage = dict(prompt_tokens=0, completion_tokens=0, total_tokens=0,
                     prompt_tokens_details={"cached_tokens": 0})
        result = await self.run_fake([[payload(usage=usage)]], "planner")
        self.assertEqual(result.prompt_tokens, 0)
        row = self.rows[0]
        self.assertEqual([row[k] for k in ("input_tokens", "cached_tokens", "output_tokens", "total_tokens")], [0]*4)
        self.assertEqual((row["provider"], row["model"], row["service_tier"], row["stage"]),
                         ("qwen", "synthetic-qwen", "default", "planner"))
        expected = self.client._request_kwargs("synthetic", "synthetic-qwen", "private-system", "private-prompt", 20)
        usage_module = sys.modules["isolated_fundamental.infrastructure.llm.usage"]
        self.assertEqual(row["request_sha256"], usage_module.digest(expected))
        self.assertIsNone(row["requested_service_tier"])
        self.assertEqual(row["outcome"], "validated")
        self.assert_ids()

    @synchronous_coroutine
    async def test_2_missing_usage_preserves_null_and_independent_zero(self):
        for raw in (None, {"prompt_tokens": 0, "completion_tokens": None}):
            with self.subTest(raw=raw):
                self.rows.clear()
                await self.run_fake([[payload(usage=raw, tier=None)]])
                row = self.rows[0]
                self.assertIsNone(row["cached_tokens"])
                self.assertIsNone(row["output_tokens"])
                self.assertIsNone(row["total_tokens"])
                self.assertIsNone(row["service_tier"])
                self.assertEqual(row["input_tokens"], None if raw is None else 0)
                self.assert_ids()

    @synchronous_coroutine
    async def test_5_raw_http_usage_is_not_overwritten_by_sdk_coercion(self):
        event = payload(usage={"prompt_tokens": "7", "completion_tokens": False,
                               "total_tokens": 7, "prompt_tokens_details": {"cached_tokens": None}})
        event["sdk_usage"] = {"prompt_tokens": 7, "completion_tokens": 0, "total_tokens": 7}
        result = await self.run_fake([[event]])
        # Compatibility summary may reflect SDK parsing; evidence must preserve raw types.
        self.assertEqual(result.prompt_tokens, 7)
        self.assertEqual(self.rows[0]["input_tokens"], "7")
        self.assertIs(self.rows[0]["output_tokens"], False)
        self.assertIsNone(self.rows[0]["cached_tokens"])
        self.assertEqual(self.rows[0]["outcome"], "validated")

    @synchronous_coroutine
    async def test_3_schema_retry_and_all_failed_fallback_retain_evidence(self):
        bad = payload(content="invalid-json", usage={"prompt_tokens": 11, "completion_tokens": 2, "total_tokens": 13})
        await self.run_fake([[bad], [payload(usage={"prompt_tokens": 5})]], "verify_retry")
        self.assertEqual([r["attempt_kind"] for r in self.rows], ["initial", "schema_retry"])
        self.assertEqual([r["outcome"] for r in self.rows], ["invalid_output", "validated"])
        self.assertEqual(self.rows[0]["input_tokens"], 11)
        self.assertNotEqual(self.rows[0]["request_sha256"], self.rows[1]["request_sha256"])
        self.assertEqual(self.rows[1]["parent_call_id"], self.rows[0]["call_id"])
        self.assert_ids()
        self.rows.clear()
        result = await self.run_fake([[bad], [bad], [bad], [bad]], "critic")
        self.assertIsNone(result)
        self.assertEqual(len(self.rows), 4)
        self.assertEqual(self.rows[2]["attempt_kind"], "provider_fallback")
        self.assertTrue(all(r["outcome"] == "invalid_output" for r in self.rows))
        self.assert_ids()

    @synchronous_coroutine
    async def test_4_sdk_retries_uncertain_sends_fallback_and_cancellation(self):
        await self.run_fake([["sdk_timeout_retry", "sdk_http_retry", TimeoutError("synthetic")],
                             [payload(usage={"prompt_tokens": 0})]], "critic_revision")
        self.assertEqual([r["attempt_kind"] for r in self.rows], ["initial", "sdk_retry", "sdk_retry", "provider_fallback"])
        self.assertEqual([r["outcome"] for r in self.rows], ["unknown", "http_error", "unknown", "validated"])
        self.assertIsNone(self.rows[0]["input_tokens"])
        self.assertEqual(self.rows[1]["input_tokens"], 7)
        self.assertEqual(self.rows[3]["input_tokens"], 0)
        self.assertIsNone(self.rows[3]["total_tokens"])
        for parent, child in zip(self.rows, self.rows[1:]):
            self.assertEqual(child["parent_call_id"], parent["call_id"])
        self.assert_ids()
        self.rows.clear()
        with self.assertRaises(asyncio.CancelledError):
            await self.run_fake([[asyncio.CancelledError()]])
        self.assertEqual(len(self.rows), 1)
        self.assertEqual(self.rows[0]["outcome"], "unknown")
        await self.assert_node_propagation()
        await self.assert_agent_cancellation_capture()


    async def assert_node_propagation(self):
        def node(name, dependencies):
            path = SOURCE / "application/nodes" / (name + ".py")
            tree = ast.parse(path.read_text(encoding="utf8"))
            function = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == name)
            namespace = dict(dependencies, FundamentalAgentState=dict, Any=object)
            exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), "exec"), namespace)
            return namespace[name]

        preserved = [dict(self.rows[0])]
        new = [dict(self.rows[0], call_id="00000000-0000-0000-0000-000000000001")]
        result = NS(call_usage_records=new, provider="template", model="rule-based", flags=[],
                    verdict="safe", interpretation="safe", verdict_label="moderate", latency_ms=0,
                    prompt_tokens=None, completion_tokens=0)
        async def interpret(*args, **kwargs):
            return result
        state = dict(llm_call_usage_records=preserved, corp_name="synthetic", score=45,
                     label="moderate", ratios={}, trend={}, risk_flags=[])
        interpreted = await node("interpret_node", dict(interpret=interpret, extend_unique=lambda a,b: a.extend(b)))(state)
        self.assertEqual(interpreted["llm_call_usage_records"], preserved + new)
        self.assertEqual(state["llm_call_usage_records"], preserved)
        state.update(interpreted, evidence=[], llm_usage_records=[dict(prompt_tokens=0, completion_tokens=None)])
        stable = NS(verdict_stable=True, outcome="stable", reasons=[])
        verified = await node("verify_node", dict(assess_verdict_stability=lambda *a: stable,
            EVIDENCE_UNBOUND_FLAG="unbound", is_consistency_flag=lambda f: False,
            record_decision=lambda *a,**kw: [], confidence_from=lambda *a: 0.5))(state)
        self.assertEqual(verified["llm_call_usage_records"], preserved + new)
        self.assertEqual(verified["cost_summary"]["prompt_tokens"], 0)
        self.assertIsNone(verified["cost_summary"]["completion_tokens"])

        async def critic_review(state):
            return NS(output=None, call_usage_records=new, provider="template", model="skipped")
        state["llm_provider"] = "qwen"
        skipped = await node("critic_node", dict(critic_review=critic_review,
            record_failure=lambda *a,**kw: [], record_decision=lambda *a,**kw: []))(state)
        self.assertEqual(skipped["llm_call_usage_records"], preserved + new + new)
        self.assertEqual(state["llm_call_usage_records"], preserved + new)


    async def assert_agent_cancellation_capture(self):
        usage = sys.modules["isolated_fundamental.infrastructure.llm.usage"]
        path = SOURCE / "application/agent.py"
        tree = ast.parse(path.read_text(encoding="utf8"))
        functions = [n for n in tree.body if isinstance(n, ast.AsyncFunctionDef)]
        async def invoke(initial):
            # 실제 wrapper처럼 별도 로컬 collector를 쓰고 정상 반환 전에 취소된다.
            local = []
            with patch.dict(sys.modules, openai=fake_sdk([["sdk_timeout_retry", asyncio.CancelledError()]], [])):
                await self.client.complete_structured(Schema, system="private-system", prompt="private-prompt",
                    timeout=8, attempt_records=local, stage=initial["request"])
        namespace = dict(asyncio=asyncio, capture_usage=usage.capture_usage,
            _WORKFLOW=NS(ainvoke=invoke), FundamentalRequest=object, FundamentalAgentInput=object,
            FundamentalResponse=object, Any=object)
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), "exec"), namespace)
        external = []
        with self.assertRaises(asyncio.CancelledError) as caught:
            await namespace["analyze_fundamental"]("cancelled-run", call_usage_records=external)
        self.assertEqual(len(external), 2)
        self.assertEqual([r["outcome"] for r in external], ["unknown", "unknown"])
        self.assertEqual(tuple(external), caught.exception.fundamental_call_usage_records)
        self.assertTrue(all(r["stage"] == "cancelled-run" for r in external))
        self.assertIsNone(usage._run_records.get())
        # 별도 실행과 nested ContextVar scope가 서로의 증거를 공유하지 않는다.
        other, nested = [], []
        with usage.capture_usage(other):
            with usage.capture_usage(nested):
                usage.retain_attempt([], {"call_id": "nested"})
            usage.retain_attempt([], {"call_id": "other"})
        self.assertEqual(nested, [{"call_id": "nested"}])
        self.assertEqual(other, [{"call_id": "other"}])
        self.assertEqual(len(external), 2)
        self.assertIsNone(usage._run_records.get())
        class Pause:
            def __await__(self):
                yield "paused"
        async def scoped(records, label):
            with usage.capture_usage(records):
                usage.retain_attempt([], {"call_id": label + "-start"})
                await Pause()
                usage.retain_attempt([], {"call_id": label + "-end"})
        a, b = [], []
        ca, cb = scoped(a, "a"), scoped(b, "b")
        xa, xb = copy_context(), copy_context()
        self.assertEqual(xa.run(ca.send, None), "paused")
        self.assertEqual(xb.run(cb.send, None), "paused")
        for context, coroutine in ((xa, ca), (xb, cb)):
            with self.assertRaises(StopIteration):
                context.run(coroutine.send, None)
        self.assertEqual(a, [{"call_id": "a-start"}, {"call_id": "a-end"}])
        self.assertEqual(b, [{"call_id": "b-start"}, {"call_id": "b-end"}])
        self.assertIsNone(usage._run_records.get())


if __name__ == "__main__":
    sys.addaudithook(guard)  # source 수집·실행 전에 설정/외부 부작용을 차단한다.
    unittest.main(verbosity=2)
