"""AI(technical) 서버 HTTP 클라이언트.

backend 는 AI 코드를 **import 하지 않고** HTTP 로만 호출한다(coding_guidelines §1.2).
`POST {AI_SERVICE_URL}/internal/technical/analyze` 를 호출하고 raw JSON(dict)을 돌려준다.
AI 의 §9 error envelope/타임아웃을 backend 도메인 예외로 매핑한다.

secret 미로깅: 예외 메시지에 요청 payload(원 질의 등)·응답 본문을 싣지 않는다.
"""

from __future__ import annotations

import httpx
import asyncio

_ANALYZE_PATH = "/internal/technical/analyze"
_FUNDAMENTAL_ANALYZE_PATH = "/internal/fundamental/analyze"
_INDUSTRY_ANALYZE_PATH = "/internal/industry/analyze"
_INDUSTRY_RENDER_PATH = "/internal/industry/render"


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
        *, service_token: str = "",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._transport = transport  # 테스트에서 MockTransport 주입용
        self._flow_token = service_token
        self._fundamental_token = service_token

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
        """`/internal/technical/analyze` 호출 → 응답 JSON(dict) 반환.

        payload 는 TechnicalAgentInput 형태(ticker/query/request_id/as_of).
        """
        url = self._base_url + _ANALYZE_PATH
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                resp = await client.post(url, json=payload)
        except httpx.TimeoutException as exc:
            raise AITimeoutError("AI 서버 응답 timeout") from exc
        except httpx.HTTPError as exc:
            # 연결 실패 등 — 메시지에 payload/URL 세부는 싣지 않는다.
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
