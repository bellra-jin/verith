"""Optional verifier-only Responses boundary. No environment, SDK or default key."""
import asyncio
from dataclasses import dataclass
from pathlib import Path
import hashlib
import re
from uuid import UUID
import httpx
from src.supervisor.domain.meaning import canonical, decode, sha
from src.supervisor.domain.meaning_proposals import (
    CAPS, CANDIDATE_SCHEMA, MODEL, PRICE, InputTokenEvidence, MeaningProposal, semantic_spec,
)
from src.supervisor.infrastructure.meaning_gateway import CounterUnavailable, MeaningUnavailable

ORIGIN = 'https://api.openai.com'
COUNT_PATH = '/v1/responses/input_tokens'
GENERATE_PATH = '/v1/responses'
INPUT_FIELDS = ('model', 'instructions', 'input', 'text', 'tools', 'tool_choice', 'parallel_tool_calls', 'reasoning')
COUNT_DOCUMENTATION = 'https://developers.openai.com/api/reference/resources/responses/subresources/input_tokens/methods/count'


@dataclass(frozen=True)
class CounterAgreement:
    documentation_url: str
    documentation_sha256: str
    input_fields: tuple
    counting_fee_bound_nano: int

    def validate(self):
        if self.documentation_url != COUNT_DOCUMENTATION or not re.fullmatch(r'[0-9a-f]{64}', self.documentation_sha256):
            raise CounterUnavailable()
        if self.input_fields != INPUT_FIELDS or type(self.counting_fee_bound_nano) is not int or not 0 <= self.counting_fee_bound_nano <= 28496000:
            raise CounterUnavailable()


def rendered_request(draft):
    prompt = (Path(__file__).resolve().parents[1] / 'prompts/meaning.txt').read_text('utf8')
    request = {'model': MODEL, 'instructions': prompt,
               'input': [{'role': 'user', 'content': [{'type': 'input_text', 'text': canonical(draft.model_dump(mode='json'))}]}],
               'text': {'format': {'type': 'json_schema', 'name': 'supervisor_meaning_v1', 'strict': True, 'schema': CANDIDATE_SCHEMA}},
               'tools': [], 'tool_choice': 'none', 'parallel_tool_calls': False,
               'reasoning': {'effort': 'none'}, 'service_tier': 'default', 'store': False,
               'stream': False, 'max_output_tokens': CAPS['output_tokens']}
    if len(canonical(request).encode('utf8')) > CAPS['request_bytes']:
        raise MeaningUnavailable('Meaning request unavailable')
    return request


def usage_observation(response):
    """Independently classify observations; no missing usage or cache count becomes zero."""
    result = {'state': 'unknown', 'reason': 'USAGE_UNAVAILABLE', 'estimated_nano': None}
    if type(response) is not dict:
        return result
    model = response.get('model')
    if type(model) is str:
        result['model_sha256'] = hashlib.sha256(model.encode('utf8')).hexdigest()
    if model != MODEL:
        return result | {'state': 'anomalous', 'reason': 'MODEL_MISMATCH'}
    usage = response.get('usage')
    if type(usage) is not dict:
        return result
    observed = {name: usage.get(name) for name in ('input_tokens', 'output_tokens', 'total_tokens')}
    if any(type(observed[name]) is int and observed[name] > CAPS[name] for name in ('input_tokens', 'output_tokens')):
        return result | {'state': 'anomalous', 'reason': 'CAP_EXCEEDED'}
    if any(type(value) is not int or value < 0 for value in observed.values()):
        return result
    if observed['total_tokens'] != observed['input_tokens'] + observed['output_tokens']:
        return result
    details = usage.get('input_tokens_details')
    cached = details.get('cached_tokens') if type(details) is dict else None
    if type(cached) is not int or not 0 <= cached <= observed['input_tokens'] or response.get('service_tier') != 'default':
        return result
    estimate = (observed['input_tokens'] - cached) * PRICE['input_nano_per_token'] + cached * PRICE['cached_nano_per_token'] + observed['output_tokens'] * PRICE['output_nano_per_token']
    return result | {'state': 'observed', 'reason': 'USAGE_OBSERVED', 'estimated_nano': estimate,
                     **observed, 'cached_tokens': cached, 'price_sha256': sha(PRICE)}


def candidate_output(response):
    if type(response) is not dict or response.get('status') != 'completed' or response.get('error') is not None:
        raise MeaningUnavailable('Meaning result unavailable')
    output = response.get('output')
    if type(output) is not list or len(output) != 1:
        raise MeaningUnavailable('Meaning result unavailable')
    message = output[0]
    if type(message) is not dict or message.get('type') != 'message' or message.get('role') != 'assistant' or message.get('status') != 'completed':
        raise MeaningUnavailable('Meaning result unavailable')
    content = message.get('content')
    if type(content) is not list or len(content) != 1 or type(content[0]) is not dict or content[0].get('type') != 'output_text':
        raise MeaningUnavailable('Meaning result unavailable')
    text = content[0].get('text')
    if type(text) is not str or len(text.encode('utf8')) > CAPS['candidate_bytes']:
        raise MeaningUnavailable('Meaning result unavailable')
    try:
        return MeaningProposal.model_validate(decode(text))
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise MeaningUnavailable('Meaning result unavailable') from None


class OpenAIMeaningGateway:
    """Only an explicit verifier supplies key/agreement/durable budget; none are discovered."""
    def __init__(self, *, api_key=None, budget=None, counter_agreement=None, transport=None):
        self._key = api_key
        self._budget = budget
        self._agreement = counter_agreement
        self._transport = transport

    async def _post(self, path, value, limit):
        if path not in {COUNT_PATH, GENERATE_PATH}:
            raise MeaningUnavailable('Meaning destination unavailable')
        raw = canonical(value).encode('utf8')
        if len(raw) > CAPS['request_bytes']:
            raise MeaningUnavailable('Meaning request unavailable')
        async with httpx.AsyncClient(transport=self._transport, timeout=CAPS['provider_seconds'], trust_env=False, follow_redirects=False, verify=True) as client:
            async with client.stream('POST', ORIGIN + path, content=raw,
                                     headers={'Authorization': 'Bearer ' + self._key, 'Content-Type': 'application/json', 'Accept-Encoding': 'identity'}) as response:
                if response.headers.get('content-encoding', 'identity').lower() != 'identity' or response.status_code != 200:
                    raise MeaningUnavailable('Meaning provider unavailable')
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(body) + len(chunk) > limit:
                        raise MeaningUnavailable('Meaning response unavailable')
                    body.extend(chunk)
                return decode(bytes(body))

    async def _finish(self, attempt_id, observation, blocked):
        try:
            await self._budget.finish(attempt_id, observation, blocked=blocked)
        except BaseException:
            # The already committed maximum/active-attempt remains held on uncertain ACK.
            pass

    async def propose(self, draft, *, attempt_id=None):
        if self._budget is None or self._agreement is None or type(self._key) is not str or not self._key or len(self._key) > 512 or any(ord(c) < 33 or ord(c) > 126 for c in self._key):
            raise CounterUnavailable()
        self._agreement.validate()
        try:
            if type(attempt_id) is not str or str(UUID(attempt_id)) != attempt_id:
                raise ValueError()
        except (TypeError, ValueError):
            raise CounterUnavailable() from None
        request = rendered_request(draft)
        projection = {name: request[name] for name in INPUT_FIELDS}
        request_hash, projection_hash = sha(request), sha(projection)
        observation = {'state': 'unknown', 'reason': 'UNOBSERVED', 'estimated_nano': None}
        authorized = False
        try:
            async with asyncio.timeout(CAPS['provider_seconds']):
                authorized = True  # An uncertain reservation ACK must retain/block its durable hold.
                if await self._budget.authorize(attempt_id, 'count', request_hash, projection_hash, None) is not True:
                    raise CounterUnavailable()
                authorized = True
                count = await self._post(COUNT_PATH, projection, CAPS['count_response_bytes'])
                if type(count) is not dict or set(count) != {'object', 'input_tokens'} or count['object'] != 'response.input_tokens' or type(count['input_tokens']) is not int or not 0 <= count['input_tokens'] <= CAPS['input_tokens']:
                    raise CounterUnavailable()
                evidence = InputTokenEvidence(request_hash, projection_hash, count['input_tokens'], MODEL, sha(PRICE), self._agreement.documentation_sha256, self._agreement.counting_fee_bound_nano)
                maximum = evidence.input_tokens * PRICE['input_nano_per_token'] + CAPS['output_tokens'] * PRICE['output_nano_per_token'] + evidence.count_fee_bound_nano
                if maximum > CAPS['attempt_reserve_nano'] or evidence.request_sha256 != sha(request) or evidence.projection_sha256 != sha({name: request[name] for name in INPUT_FIELDS}):
                    raise CounterUnavailable()
                if await self._budget.authorize(attempt_id, 'generation', request_hash, projection_hash, evidence) is not True:
                    raise CounterUnavailable()
                response = await self._post(GENERATE_PATH, request, CAPS['response_bytes'])
                observation = usage_observation(response)
                if observation['state'] != 'observed':
                    raise MeaningUnavailable('Meaning usage unavailable')
                candidate = candidate_output(response)
                await self._finish(attempt_id, observation, False)
                return candidate
        except BaseException:
            if authorized:
                await self._finish(attempt_id, observation, observation['state'] != 'observed')
            raise
