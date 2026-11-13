"""AI(technical) 서버 HTTP 클라이언트.

backend 는 AI 코드를 **import 하지 않고** HTTP 로만 호출한다(coding_guidelines §1.2).
`POST {AI_SERVICE_URL}/internal/technical/analyze` 를 호출하고 raw JSON(dict)을 돌려준다.
AI 의 §9 error envelope/타임아웃을 backend 도메인 예외로 매핑한다.

secret 미로깅: 예외 메시지에 요청 payload(원 질의 등)·응답 본문을 싣지 않는다.
"""

from __future__ import annotations

import httpx
import asyncio
import time
import math
from dataclasses import dataclass

_ANALYZE_PATH = "/internal/technical/analyze"
_FUNDAMENTAL_ANALYZE_PATH = "/internal/fundamental/analyze"
_INDUSTRY_ANALYZE_PATH = "/internal/industry/analyze"
_INDUSTRY_RENDER_PATH = "/internal/industry/render"


@dataclass(frozen=True,slots=True,repr=False)
class _TechnicalBoundaryConfiguration:
    base_url:str
    token:bytes
    transport:object

    def same(self,other):
        return (type(other) is _TechnicalBoundaryConfiguration and self.base_url==other.base_url
                and self.token==other.token and self.transport is other.transport)


@dataclass(frozen=True,slots=True,repr=False)
class _TechnicalExecutionConfiguration:
    origin:str
    token:bytes
    configuration:str
    transport:object

class AIClientError(Exception):
    """AI 호출 실패의 베이스."""


class AITimeoutError(AIClientError):
    """AI 응답이 timeout(또는 504)."""


class AIUnavailableError(AIClientError):
    """AI 서버 연결 불가/5xx(502/503) 등 일시적 장애."""


class AIValidationError(AIClientError):
    """요청이 AI 계약 검증에 실패(422). 예: 범위 밖 ticker·형식 오류.

    status_code=422 응답을 그대로 전달하기 위한 예외.
    """


class AIContractError(AIClientError):
    """AI 의 200 응답이 계약을 위반(구조/범위/정합성). upstream 오류 → 502 로 매핑.

    예: 필수 필드 누락, 수치 범위 초과, indicator 중복, 요청↔응답 ticker/request_id 불일치.
    """


class AIClient:
    """technical AI 서버 호출기. 요청마다 짧게 AsyncClient 를 연다."""

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float,
        transport: httpx.AsyncBaseTransport | None = None,
        *, service_token: str = "", execution_token: str = "",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._transport = transport  # 테스트에서 MockTransport 주입용
        self._execution_token = execution_token
        self._flow_token = service_token
        self._fundamental_token = service_token

    async def plan_supervisor_core(self,payload:dict,*,meaning_grant=None)->dict:
        # Policy2/attempt fields travel only inside the authenticated typed core envelope.
        from urllib.parse import urlsplit
        from src.modules.supervisor.domain.contracts import canonical,decode
        try:
            target=urlsplit(self._base_url);httpx.URL(self._base_url);token=self._flow_token.encode('ascii')
            if target.scheme not in {'http','https'} or not target.hostname or target.port==0 or target.username or target.password or target.path not in {'','/'} or target.query or target.fragment or len(token)<32 or any(c<32 or c>126 for c in token):raise ValueError()
            extra={}
            if meaning_grant is not None:
                import re
                if type(meaning_grant) is not str or re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\.[0-9a-f]{64}',meaning_grant) is None:raise ValueError()
                extra['X-Supervisor-Meaning-Grant']=meaning_grant
            body=canonical(payload).encode('utf8')
            if len(body)>16384:raise ValueError()
        except (ValueError,TypeError,UnicodeError,httpx.InvalidURL):raise AIUnavailableError('Supervisor request unavailable') from None
        policy2=type(payload) is dict and type(payload.get('data')) is dict and payload['data'].get('policy_version')=='supervisor.flow-core.2'
        timeout=70 if policy2 else 8
        try:
            async with asyncio.timeout(timeout):
                async with httpx.AsyncClient(timeout=timeout,transport=self._transport,trust_env=False,follow_redirects=False) as client:
                    async with client.stream('POST',self._base_url+'/internal/supervisor/core/plan',content=body,headers={'Content-Type':'application/json','Accept':'application/json','Accept-Encoding':'identity','X-Flow-Service-Token':token.decode('ascii'),**extra}) as response:
                        if response.status_code==504:raise AITimeoutError('Supervisor request unavailable')
                        if response.status_code!=200:raise AIUnavailableError('Supervisor request unavailable')
                        if response.headers.get('content-encoding','identity').lower()!='identity':raise AIContractError('Supervisor request unavailable')
                        raw=bytearray()
                        async for chunk in response.aiter_bytes():
                            if len(raw)+len(chunk)>65536:raise AIContractError('Supervisor request unavailable')
                            raw.extend(chunk)
                        try:
                            value=decode(raw)
                            if type(value) is not dict:raise ValueError()
                            return value
                        except (ValueError,TypeError,UnicodeError,RecursionError):raise AIContractError('Supervisor request unavailable') from None
        except (TimeoutError,httpx.TimeoutException):raise AITimeoutError('Supervisor request unavailable') from None
        except (httpx.HTTPError,httpx.InvalidURL):raise AIUnavailableError('Supervisor request unavailable') from None

    async def plan_flow(self,payload:dict)->dict:
        """One 3s/32KiB decoded planning exchange, fixed origin/path/header; retry0."""
        from urllib.parse import urlsplit
        from src.modules.flow.domain.query_plan import canonical,decode
        try:
            target=urlsplit(self._base_url);httpx.URL(self._base_url);token=self._flow_token.encode('ascii')
            if (target.scheme not in {'http','https'} or not target.hostname or target.port==0 or target.username or target.password or target.path not in {'','/'} or target.query or target.fragment or len(token)<32 or any(c<32 or c>126 for c in token)):raise ValueError()
        except (ValueError,UnicodeError,httpx.InvalidURL):raise AIUnavailableError('Planning service unavailable') from None
        try:
            data=canonical(payload).encode('utf8')
            if len(data)>32768:raise AIContractError('Invalid planning request')
            async with asyncio.timeout(3):
                async with httpx.AsyncClient(timeout=3,transport=self._transport,follow_redirects=False,trust_env=False) as client:
                    async with client.stream('POST',self._base_url+'/internal/supervisor/plan',content=data,headers={'Content-Type':'application/json','Accept':'application/json','Accept-Encoding':'identity','X-Flow-Service-Token':token.decode('ascii')}) as response:
                        if response.headers.get('content-encoding','identity').lower()!='identity':
                            if response.status_code==200:raise AIContractError('Invalid planning response')
                            raise AIUnavailableError('Planning service unavailable')
                        if response.status_code==504:raise AITimeoutError('Planning deadline exceeded')
                        if response.status_code not in {200,502}:raise AIUnavailableError('Planning service unavailable')
                        raw=bytearray()
                        async for part in response.aiter_bytes():
                            if len(raw)+len(part)>32768:
                                if response.status_code==200:raise AIContractError('Invalid planning response')
                                raise AIUnavailableError('Planning service unavailable')
                            raw.extend(part)
                        try:
                            value=decode(bytes(raw))
                            if type(value) is not dict:raise ValueError()
                            if response.status_code==502:
                                if set(value)=={'error'} and type(value['error']) is dict and set(value['error'])=={'code','message'} and value['error']['code']=='RESULT_CONTRACT_INVALID' and type(value['error']['message']) is str:raise AIContractError('Invalid planning response')
                                raise AIUnavailableError('Planning service unavailable')
                            return value
                        except (ValueError,UnicodeError,RecursionError):
                            if response.status_code==502:raise AIUnavailableError('Planning service unavailable') from None
                            raise AIContractError('Invalid planning response') from None
        except (TimeoutError,httpx.TimeoutException):raise AITimeoutError('Planning deadline exceeded') from None
        except (httpx.HTTPError,httpx.InvalidURL):raise AIUnavailableError('Planning service unavailable') from None

    async def analyze_flow(self, payload: dict) -> dict:
        """One bounded internal Flow request. No redirect, environment proxy or retry."""
        from urllib.parse import urlsplit
        from src.modules.flow.domain.analysis import canonical, decode
        try:
            target=urlsplit(self._base_url)
            httpx.URL(self._base_url)  # Parse with the transport's own grammar before any send.
            token=self._flow_token.encode('utf8')
            valid=(target.scheme in {'http','https'} and target.hostname and not target.username and not target.password
                   and target.port != 0 and target.path in {'','/'} and not target.query and not target.fragment
                   and len(token)>=32 and not any(value<32 or value==127 for value in token))
        except (ValueError,UnicodeError,httpx.InvalidURL):raise AIUnavailableError('Flow service is unavailable') from None
        if not valid:raise AIUnavailableError('Flow service is unavailable')
        try:
            data=canonical(payload).encode('utf8')
            if len(data)>8192:raise AIValidationError('Flow request is invalid')
            async def exchange():
                async with httpx.AsyncClient(timeout=125,transport=self._transport,follow_redirects=False,trust_env=False) as client:
                    async with client.stream('POST',self._base_url+'/internal/flow/analyze',content=data,
                        headers=[(b'Content-Type',b'application/json'),(b'X-Flow-Service-Token',token)]) as response:
                        raw=bytearray()
                        async for part in response.aiter_bytes():
                            if len(raw)+len(part)>2097152:
                                if response.status_code==200:raise AIContractError('Flow result is invalid')
                                raise AIUnavailableError('Flow engine unavailable')
                            raw.extend(part)
                        if response.status_code==200:
                            try:
                                value=decode(bytes(raw).decode('utf8'))
                                if not isinstance(value,dict):raise ValueError()
                                return value
                            except Exception:raise AIContractError('Flow result is invalid') from None
                        if response.status_code in {400,409,422}:raise AIValidationError('Flow engine declined the request')
                        if response.status_code==502:
                            try:error=decode(bytes(raw).decode('utf8'))
                            except (ValueError,UnicodeError,RecursionError):error=None
                            if isinstance(error,dict) and isinstance(error.get('error'),dict) and error['error'].get('code')=='RESULT_CONTRACT_INVALID':
                                raise AIContractError('Flow result is invalid')
                        if response.status_code==504:raise AITimeoutError('Flow engine timeout')
                        raise AIUnavailableError('Flow engine unavailable')
            async with asyncio.timeout(125):
                return await exchange()
        except (httpx.TimeoutException,TimeoutError):raise AITimeoutError('Flow engine timeout') from None
        except (httpx.HTTPError,httpx.InvalidURL):raise AIUnavailableError('Flow engine unavailable') from None

    async def analyze_technical(self, payload: dict) -> dict:
        """Legacy unauthenticated execution is closed before transport."""
        raise AIUnavailableError('Technical execution unavailable')

    def _technical_boundary_configuration(self):
        """Pure private snapshot; no settings/env/DNS/client or HTTP side effects."""
        from urllib.parse import urlsplit
        try:
            base=self._base_url;transport=self._transport;raw_token=self._flow_token
            if type(base) is not str or type(raw_token) is not str:raise ValueError()
            url=urlsplit(base);httpx.URL(base);token=raw_token.encode('ascii')
            if url.scheme not in {'http','https'} or not url.hostname or url.port==0 or url.username or url.password or url.path not in {'','/'} or url.query or url.fragment or len(token)<32 or any(c<32 or c>126 for c in token):raise ValueError()
            if transport is not None and not isinstance(transport,httpx.AsyncBaseTransport):raise ValueError()
            return _TechnicalBoundaryConfiguration(base,token,transport)
        except (ValueError,TypeError,UnicodeError,httpx.InvalidURL):raise AIUnavailableError('Technical boundary unavailable') from None

    async def technical_boundary(self,payload:dict,*,_configuration=None)->dict:
        """Fixed synthetic typed boundary; no retry, proxy, redirect or production engine."""
        from src.modules.technical.domain.execution_boundary import REQUEST_LIMIT,RESPONSE_LIMIT,WAIT_SECONDS,parse_request,canonical,decode,BoundaryInvalid
        captured=self._technical_boundary_configuration()
        if _configuration is not None:
            if type(_configuration) is not _TechnicalBoundaryConfiguration or not captured.same(_configuration):
                raise AIUnavailableError('Technical boundary unavailable')
            captured=_configuration
        try:
            parse_request(payload);body=canonical(payload).encode('utf8')
            if len(body)>REQUEST_LIMIT:raise BoundaryInvalid()
        except (ValueError,TypeError,UnicodeError,RecursionError):raise AIValidationError('Technical boundary input invalid') from None
        try:
            async with asyncio.timeout(WAIT_SECONDS):
                async with httpx.AsyncClient(timeout=WAIT_SECONDS,transport=captured.transport,trust_env=False,follow_redirects=False) as client:
                    async with client.stream('POST',captured.base_url+'/internal/technical/boundary',content=body,headers={'Content-Type':'application/json','Accept':'application/json','Accept-Encoding':'identity','X-Technical-Service-Token':captured.token.decode('ascii')}) as response:
                        if response.status_code==504:raise AITimeoutError('Technical boundary deadline exceeded')
                        if response.status_code!=200:raise AIUnavailableError('Technical boundary unavailable')
                        if response.headers.get('content-encoding','identity').lower()!='identity':raise AIContractError('Technical boundary result invalid')
                        raw=bytearray()
                        async for chunk in response.aiter_bytes():
                            if len(raw)+len(chunk)>RESPONSE_LIMIT:raise AIContractError('Technical boundary result invalid')
                            raw.extend(chunk)
                        try:
                            value=decode(raw)
                            if type(value) is not dict:raise BoundaryInvalid()
                            return value
                        except (ValueError,TypeError,UnicodeError,RecursionError):raise AIContractError('Technical boundary result invalid') from None
        except (TimeoutError,httpx.TimeoutException):raise AITimeoutError('Technical boundary deadline exceeded') from None
        except (httpx.HTTPError,httpx.InvalidURL):raise AIUnavailableError('Technical boundary unavailable') from None

    def _technical_execution_configuration(self,configuration):
        from src.modules.technical.domain import provider_execution as P
        try:
            if type(configuration) is not P.Configuration:raise P.ExecutionInvalid()
            cfg=P.Configuration(configuration.text);origin=P.origin(self._base_url)
            token=P.service_token(self._execution_token)
            if origin!=cfg.data()['ai_origin'] or self._transport is not None and type(self._transport) is not httpx.ASGITransport:raise P.ExecutionInvalid()
            return _TechnicalExecutionConfiguration(origin,token,cfg.text,self._transport)
        except Exception:raise AIUnavailableError('Technical execution unavailable') from None

    async def _technical_execution_post(self,path,body,captured,remaining,cap,grant=None):
        from src.modules.technical.domain import provider_execution as P
        if type(captured) is not _TechnicalExecutionConfiguration:raise AIUnavailableError('Technical execution unavailable')
        fresh=self._technical_execution_configuration(P.Configuration(captured.configuration))
        if (fresh.origin!=captured.origin or fresh.token!=captured.token or fresh.transport is not captured.transport):raise AIUnavailableError('Technical execution unavailable')
        raw=P.canonical(body).encode('utf8');headers={'Content-Type':'application/json','Accept':'application/json','Accept-Encoding':'identity','X-Technical-Service-Token':captured.token.decode('ascii')}
        if grant is not None:P.digest(grant);headers['X-Technical-Execution-Grant']=grant
        if len(raw)>(32768 if path.endswith('/ready') else 65536) or type(remaining) not in (int,float) or not math.isfinite(remaining) or not 0<remaining<=86400:raise AIUnavailableError('Technical execution unavailable')
        deadline=time.monotonic()+remaining
        try:
            async with asyncio.timeout(remaining):
                async with httpx.AsyncClient(verify=True,trust_env=False,follow_redirects=False,transport=captured.transport,timeout=remaining) as client:
                    async with client.stream('POST',captured.origin+path,content=raw,headers=headers) as response:
                        if response.status_code!=200 or response.headers.get('content-encoding','identity')!='identity':raise AIUnavailableError('Technical execution unavailable')
                        result=bytearray()
                        async for chunk in response.aiter_bytes():
                            if len(result)+len(chunk)>cap:raise AIContractError('Technical execution result invalid')
                            result.extend(chunk)
                        parsed=P.decode(result,cap)
                        if time.monotonic()>=deadline:raise AITimeoutError('Technical execution deadline exceeded')
            if time.monotonic()>=deadline:raise AITimeoutError('Technical execution deadline exceeded')
            return parsed
        except asyncio.CancelledError:raise
        except AITimeoutError:raise
        except (TimeoutError,httpx.TimeoutException):raise AITimeoutError('Technical execution deadline exceeded') from None
        except Exception:raise AIUnavailableError('Technical execution unavailable') from None

    async def technical_execution_ready(self,configuration,*,_configuration=None):
        from src.modules.technical.domain import provider_execution as P
        captured=self._technical_execution_configuration(configuration) if _configuration is None else _configuration
        value=await self._technical_execution_post('/internal/technical/execution/ready',{'schema_version':P.SCHEMA},captured,5,32768)
        if P.canonical(value)!=P.canonical({'schema_version':P.SCHEMA,'configuration':configuration.data(),'spec_sha256':P.SPEC_SHA256,'ready':True}):raise AIUnavailableError('Technical execution unavailable')
        return captured

    async def technical_execute(self,payload,grant,*,remaining,_configuration):
        from src.modules.technical.domain import provider_execution as P
        P.parse_execution(payload,P.Configuration(_configuration.configuration))
        return await self._technical_execution_post('/internal/technical/execution',payload,_configuration,remaining,2097152,grant)

    async def analyze_fundamental(self, payload: dict) -> dict:
        """One bounded internal Financial request. No redirect, environment proxy or retry."""
        from urllib.parse import urlsplit
        from src.modules.fundamental.domain.analysis import canonical, decode
        target=urlsplit(self._base_url)
        try:token=self._fundamental_token.encode('utf8')
        except UnicodeError:raise AIValidationError('Financial service is unavailable') from None
        if (target.scheme not in {'http','https'} or not target.hostname or target.username or target.password
                or target.path not in {'','/'} or target.query or target.fragment
                or len(token)<32 or any(value<32 or value==127 for value in token)):
            raise AIValidationError('Financial service is unavailable')
        try:
            data=canonical(payload).encode('utf8')
            if len(data)>8192:raise AIValidationError('Financial request is invalid')
            async def exchange():
                async with httpx.AsyncClient(timeout=65,transport=self._transport,follow_redirects=False,trust_env=False) as client:
                    async with client.stream('POST',self._base_url+'/internal/fundamental/analyze',content=data,
                        headers=[(b'Content-Type',b'application/json'),(b'X-Fundamental-Service-Token',token)]) as response:
                        raw=bytearray()
                        async for part in response.aiter_bytes():
                            if len(raw)+len(part)>2097152:raise AIContractError('Financial result is invalid')
                            raw.extend(part)
                        if response.status_code==200:
                            try:
                                value=decode(bytes(raw).decode('utf8'))
                                if not isinstance(value,dict):raise ValueError()
                                return value
                            except Exception:raise AIContractError('Financial result is invalid') from None
                        if response.status_code in {400,401,403,409,422}:raise AIValidationError('Financial engine declined the request')
                        if response.status_code==502:
                            try:contract=decode(bytes(raw).decode('utf8')).get('error',{}).get('code')=='RESULT_CONTRACT_INVALID'
                            except Exception:contract=False
                            if contract:raise AIContractError('Financial result is invalid')
                        if response.status_code==504:raise AITimeoutError('Financial engine timeout')
                        raise AIUnavailableError('Financial engine unavailable')
            async with asyncio.timeout(65):
                return await exchange()
        except (httpx.TimeoutException,TimeoutError):raise AITimeoutError('Financial engine timeout') from None
        except httpx.HTTPError:raise AIUnavailableError('Financial engine unavailable') from None

    async def render_industry_html(self, payload: dict) -> str:
        """`/internal/industry/render` 호출 → 완결 HTML 문서(text) 반환.

        payload 는 저장된 research-report.v1(dict). 검증 실패(422)는 payload 손상 →
        AIValidationError 로 올려 라우트가 422 로 매핑한다(빈 iframe 금지, handoff §5).
        """
        url = self._base_url + _INDUSTRY_RENDER_PATH
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                resp = await client.post(url, json=payload)
        except httpx.TimeoutException as exc:
            raise AITimeoutError("AI 서버 응답 timeout") from exc
        except httpx.HTTPError as exc:
            raise AIUnavailableError(f"AI 서버 연결 실패: {type(exc).__name__}") from exc

        if resp.status_code == 200:
            return resp.text
        if resp.status_code == 422:
            raise AIValidationError("리포트 payload 검증 실패(422)")
        if resp.status_code == 504:
            raise AITimeoutError("AI 서버 timeout(504)")
        if resp.status_code in (502, 503):
            raise AIUnavailableError(f"AI 서버 사용 불가({resp.status_code})")
        raise AIUnavailableError(f"AI 서버 오류({resp.status_code})")

    async def analyze_industry(self, payload: dict) -> dict:
        """`/internal/industry/analyze` 호출 → research-report.v1 JSON(dict) 반환."""
        url = self._base_url + _INDUSTRY_ANALYZE_PATH
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                resp = await client.post(url, json=payload)
        except httpx.TimeoutException as exc:
            raise AITimeoutError("AI 서버 응답 timeout") from exc
        except httpx.HTTPError as exc:
            raise AIUnavailableError(f"AI 서버 연결 실패: {type(exc).__name__}") from exc

        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 422:
            raise AIValidationError("AI 요청 검증 실패(422)")
        if resp.status_code == 504:
            raise AITimeoutError("AI 서버 timeout(504)")
        if resp.status_code in (502, 503):
            raise AIUnavailableError(f"AI 서버 사용 불가({resp.status_code})")
        raise AIUnavailableError(f"AI 서버 오류({resp.status_code})")

    async def plan_supervisor_technical(self,payload,configuration,*,remaining):
        """Fixed deterministic planner, authenticated only by the Technical token."""
        from src.modules.supervisor.domain import technical_core_contracts as C
        body=C.Envelope[C.InternalInput].model_validate(payload)
        expected=C.Context(configuration_sha256=configuration.fingerprint,policy_sha256=configuration.policy_sha256,spec_sha256=body.data.context.spec_sha256,reserved_nano=configuration.data()['policy']['attempt_reserve_nano'])
        if body.data.context!=expected:raise AIContractError('Technical plan invalid')
        captured=self._technical_execution_configuration(configuration)
        return await self._technical_execution_post('/internal/supervisor/core/technical-plan',payload,captured,min(15,remaining),65536)
