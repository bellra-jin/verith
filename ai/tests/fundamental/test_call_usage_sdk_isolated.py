"""Real locked SDK + HTTPX MockTransport. No provider, dotenv, graph or DB imports."""
from __future__ import annotations

def run_boundary_tests():
    import asyncio
    import json
    import os
    from pathlib import Path
    import sys
    from types import ModuleType, SimpleNamespace
    from unittest.mock import patch

    sys.dont_write_bytecode = True
    ROOT = Path(__file__).resolve().parents[2]
    SOURCE = ROOT / 'src/agents/fundamental'
    # Bootstrap Windows' internal loop socketpair before blocking all network calls.
    loop = asyncio.new_event_loop()

    def guard(event, args):
        if event in {'socket.connect', 'socket.getaddrinfo', 'subprocess.Popen', 'os.system'}:
            raise AssertionError('External operation blocked: ' + event)
        if event == 'open' and isinstance(args[0], (str, bytes)):
            path = Path(os.fsdecode(args[0])).resolve()
            mode, flags = args[1:3]
            if (isinstance(mode, str) and any(c in mode for c in 'wax+')) or flags & (os.O_WRONLY | os.O_RDWR):
                raise AssertionError('File write blocked')
            if path.name == '.env' or (path.is_relative_to(ROOT) and path.suffix not in {'.py', '.pyc'}):
                raise AssertionError('Project configuration/data read blocked')

    sys.addaudithook(guard)
    import httpx
    import openai
    from pydantic import BaseModel

    class Schema(BaseModel):
        ok: bool

    prefix = 'sdk_boundary_fundamental'
    for tail in ('', '.core', '.infrastructure', '.infrastructure.llm'):
        module = ModuleType(prefix + tail)
        module.__path__ = []
        sys.modules[module.__name__] = module
    config = ModuleType(prefix + '.core.config')
    config.settings = SimpleNamespace(QWEN_BASE_URL='https://synthetic.invalid/v1',
        LLM_DUMMY_KEY='synthetic-only', QWEN_MODEL='synthetic-qwen',
        OPENAI_API_KEY='synthetic-only', OPENAI_MODEL='synthetic-openai')
    sys.modules[config.__name__] = config
    for leaf in ('usage', 'client'):
        module = ModuleType(prefix + '.infrastructure.llm.' + leaf)
        module.__package__ = prefix + '.infrastructure.llm'
        sys.modules[module.__name__] = module
        path = SOURCE / 'infrastructure/llm' / (leaf + '.py')
        exec(compile(path.read_text(encoding='utf8'),str(path),'exec'),module.__dict__)
    client = module

    def response(usage, content='{"ok":true}'):
        return httpx.Response(200, json={'id':'synthetic','created':0,'object':'chat.completion',
            'model':'synthetic-returned', 'service_tier':'default',
            'choices':[{'index':0,'message':{'role':'assistant','content':content},'finish_reason':'stop'}],
            'usage': usage})

    async def run_case(events):
        rows, requests = [], []
        async def handler(request):
            requests.append(request)
            event = events.pop(0)
            if isinstance(event, BaseException): raise event
            return event
        original = openai.DefaultAsyncHttpxClient
        def mock_client(**kwargs):
            return original(transport=httpx.MockTransport(handler),trust_env=False,**kwargs)
        async def no_delay(*args, **kwargs): pass
        client._qwen_failures = 0
        client._qwen_skip_until = 0.0
        with patch.object(openai, 'DefaultAsyncHttpxClient',mock_client), patch.object(asyncio,'sleep',no_delay):
            result = await client.complete_structured(Schema,system='synthetic',prompt='synthetic',
                timeout=2,max_tokens=20,attempt_records=rows,stage='interpret')
        assert not events
        return result, rows, requests

    async def main():
        result, rows, requests = await run_case([response({'prompt_tokens':0,'completion_tokens':0,
            'total_tokens':0,'prompt_tokens_details':{'cached_tokens':0}})])
        assert result.data.ok and rows[0]['input_tokens'] == 0 and rows[0]['cached_tokens'] == 0
        usage = sys.modules[prefix + '.infrastructure.llm.usage']
        assert rows[0]['request_sha256'] == usage.digest(json.loads(requests[0].content))
        assert rows[0]['response_model'] == 'synthetic-returned'
        print('PASS real SDK success/zero/exact HTTP body digest')
        result, rows, _ = await run_case([response(None)])
        assert result.data.ok and all(rows[0][k] is None for k in ('input_tokens','cached_tokens','output_tokens','total_tokens'))
        print('PASS real SDK missing usage')
        result, rows, _ = await run_case([response({'prompt_tokens':'7','completion_tokens':False,'total_tokens':7})])
        assert rows[0]['input_tokens'] == '7' and rows[0]['output_tokens'] is False
        print('PASS real SDK raw malformed token types preserved')
        result, rows, _ = await run_case([httpx.Response(429,json={'error':{'message':'synthetic'}}),
            httpx.ReadTimeout('synthetic'),response({'prompt_tokens':2,'completion_tokens':1,'total_tokens':3})])
        assert result.data.ok and [r['attempt_kind'] for r in rows] == ['initial','sdk_retry','sdk_retry']
        assert [r['outcome'] for r in rows] == ['http_error','unknown','validated']
        assert all(b['parent_call_id'] == a['call_id'] for a,b in zip(rows,rows[1:]))
        print('PASS real SDK automatic HTTP/timeout retry inventory')
        result, rows, _ = await run_case([response({'prompt_tokens':1},'not json'),response({'prompt_tokens':2})])
        assert result.data.ok and [r['outcome'] for r in rows] == ['invalid_output','validated']
        assert rows[1]['attempt_kind'] == 'schema_retry'
        print('PASS real pydantic schema retry')
        result, rows, _ = await run_case([httpx.ReadTimeout('synthetic') for _ in range(3)] + [response({'prompt_tokens':4})])
        assert result.provider == 'openai' and len(rows) == 4 and rows[-1]['attempt_kind'] == 'provider_fallback'
        print('PASS real SDK retry exhaustion/provider fallback')
        try:
            await run_case([asyncio.CancelledError()])
        except asyncio.CancelledError: pass
        else: raise AssertionError('Cancellation swallowed')
        print('PASS real SDK cancellation propagated')

    try:
        loop.run_until_complete(main())
    finally:
        loop.close()


if __name__ == "__main__":
    run_boundary_tests()
