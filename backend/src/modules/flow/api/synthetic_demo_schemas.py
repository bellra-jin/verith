"""Exact synthetic-only HTTP contract; private IDs never imply authentication."""
from datetime import datetime
import json
import re
from typing import Literal
from uuid import UUID, uuid4
from pydantic import AwareDatetime, BaseModel, ConfigDict, StrictBool, field_validator, model_validator
from starlette.responses import JSONResponse
from src.modules.flow.api.run_schemas import FlowAdmissionRequest, PRIVATE
from src.modules.flow.domain.execution import CommonResponse, ErrorCode, SafeError
from src.modules.flow.domain.input_snapshot import canonical, digest

DEMO_PATH = '/api/flow/synthetic-demo/runs'
TICKER = '005930'
QUESTION = 'Flow 합성 데모 v1'


def is_demo_endpoint(method, path):
    return method == 'POST' and path == DEMO_PATH or method == 'GET' and path.startswith(DEMO_PATH+'/') and bool(path[len(DEMO_PATH)+1:]) and '/' not in path[len(DEMO_PATH)+1:]


def request_id(scope):
    state = scope.setdefault('state', {})
    if 'cf008_request_id' not in state:state['cf008_request_id'] = uuid4()
    return state['cf008_request_id']


class DemoRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', hide_input_in_errors=True)
    idempotency_key: str
    as_of: AwareDatetime
    allow_fake: Literal[True]

    @model_validator(mode='before')
    @classmethod
    def exact(cls, value):
        if not isinstance(value, dict) or set(value) != {'idempotency_key','as_of','allow_fake'} or type(value['allow_fake']) is not bool or value['allow_fake'] is not True:
            raise ValueError('Invalid demo request')
        req = FlowAdmissionRequest.model_validate(dict(ticker=TICKER, question=QUESTION,
            as_of=value['as_of'], idempotency_key=value['idempotency_key']))
        return dict(idempotency_key=req.idempotency_key, as_of=req.as_of, allow_fake=True)

    def admission(self):
        return FlowAdmissionRequest(ticker=TICKER, question=QUESTION, as_of=self.as_of, idempotency_key=self.idempotency_key)


class DemoRunView(BaseModel):
    model_config = ConfigDict(extra='forbid', hide_input_in_errors=True)
    version: Literal[1] = 1
    synthetic: Literal[True] = True
    mode: Literal['synthetic_demo'] = 'synthetic_demo'
    run_id: UUID
    request_id: UUID
    attempt_id: UUID
    input_snapshot_id: UUID | None
    execution_id: UUID | None
    stage: Literal['admitted','prepared','running','succeeded','failed','timed_out']
    deadline_at: AwareDatetime | None
    finished_at: AwareDatetime | None
    result_stored: StrictBool
    result: dict | None
    result_sha256: str | None
    failure_code: Literal['fake_failed','result_invalid','coroutine_timeout','deadline_expired'] | None

    @field_validator('version', 'synthetic', mode='before')
    @classmethod
    def exact_literals(cls, value, info):
        if type(value) is not (int if info.field_name=='version' else bool):raise ValueError('Invalid demo literal')
        return value

    @model_validator(mode='after')
    def consistent(self):
        input_exists = self.input_snapshot_id is not None
        execution_exists = self.execution_id is not None
        if input_exists != (self.stage != 'admitted') or execution_exists != (self.stage not in {'admitted','prepared'}):
            raise ValueError('Invalid demo identities')
        if (self.deadline_at is not None) != execution_exists or (self.finished_at is not None) != (self.stage in {'succeeded','failed','timed_out'}):
            raise ValueError('Invalid demo time')
        success = self.stage == 'succeeded'
        if type(self.result_stored) is not bool or self.result_stored != success or (self.result is not None) != success or (self.result_sha256 is not None) != success:
            raise ValueError('Invalid demo artifact')
        if (self.failure_code is not None) != (self.stage in {'failed','timed_out'}):raise ValueError('Invalid demo failure')
        if self.stage=='failed' and self.failure_code not in {'fake_failed','result_invalid'} or self.stage=='timed_out' and self.failure_code not in {'coroutine_timeout','deadline_expired'}:raise ValueError('Invalid demo failure type')
        if success:
            if self.finished_at >= self.deadline_at:raise ValueError('Invalid demo success deadline')
            data = self.result
            if not isinstance(data.get('source_reference'),dict):raise ValueError('Invalid demo reference')
            if (not isinstance(self.result_sha256,str) or re.fullmatch('[0-9a-f]{64}',self.result_sha256) is None
                    or digest(canonical(data)) != self.result_sha256
                    or data.get('execution_id') != str(self.execution_id) or data.get('input_snapshot_id') != str(self.input_snapshot_id)
                    or data.get('source_reference',{}).get('run_id') != str(self.run_id)
                    or data.get('source_reference',{}).get('request_id') != str(self.request_id)
                    or data.get('source_reference',{}).get('attempt_id') != str(self.attempt_id)):
                raise ValueError('Invalid demo artifact binding')
        return self


DemoResponse = CommonResponse[DemoRunView]


def error_response(scope, code, run_id=None):
    headers = dict(PRIVATE)
    if run_id is not None:headers['Location'] = DEMO_PATH+'/'+str(run_id)
    error = SafeError(code=code)
    return JSONResponse(DemoResponse(request_id=request_id(scope), error=error).model_dump(mode='json'), status_code=error.http_status, headers=headers)


def _pairs(pairs):
    result = {}
    for key,value in pairs:
        if key in result:raise ValueError('Duplicate JSON key')
        result[key]=value
    return result


def parse_raw(raw):
    if len(raw) > 4096:raise ValueError('Demo body too large')
    return DemoRequest.model_validate(json.loads(raw.decode('utf-8','strict'), object_pairs_hook=_pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON'))))


def json_media(headers):
    content = headers.get('content-type','')
    return re.fullmatch(r'application/json(?:\s*;\s*charset\s*=\s*(?:utf-8|"utf-8"))?\s*', content, re.I) is not None and headers.get('content-encoding','identity').lower() == 'identity'
