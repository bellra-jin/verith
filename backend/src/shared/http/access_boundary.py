"""CF-002 transition gate: no unverified identity may reach real services.

This closed state is deliberate until the approved external OIDC/session/owner
implementation exists. It never interprets arbitrary headers/cookies as identity.
"""

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

PUBLIC_ROUTES = frozenset(
    {
        ("GET", "/health"),
        ("POST", "/api/stocks/resolve"),
        ("GET", "/api/auth/login"),
        ("GET", "/api/auth/callback"),
        ("GET", "/api/auth/session"),
        ("POST", "/api/auth/logout"),
    }
)


class AccessBoundary:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            await self.app(scope, receive, send)
            return
        if scope["type"] != "http":
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
            return
        method, path = scope["method"], scope["path"]
        if path == '/api/flow/analyses' or path.startswith('/api/flow/analyses/'):
            from uuid import UUID
            from src.shared.config import settings
            from src.modules.auth.api.router import configured
            from src.modules.flow.api.run_schemas import error_response,http_request_id
            from src.modules.flow.api.analysis_schemas import AnalysisRequest
            from src.modules.flow.domain.analysis import decode
            from src.modules.flow.domain.execution import ErrorCode
            from src.modules.flow.api.synthetic_demo_schemas import json_media
            from datetime import UTC,datetime
            http_request_id(scope)
            if not settings.FLOW_ANALYSIS_ENABLED:
                await error_response(scope,ErrorCode.FEATURE_UNAVAILABLE)(scope,receive,send);return
            if not configured():
                await error_response(scope,ErrorCode.AUTH_REQUIRED)(scope,receive,send);return
            try:
                if scope.get('query_string'):raise ValueError()
                if method=='POST' and path=='/api/flow/analyses':pass
                elif method=='GET' and path.startswith('/api/flow/analyses/'):
                    segment=path[len('/api/flow/analyses/'):]
                    if str(UUID(segment))!=segment.lower():raise ValueError()
                else:raise ValueError()
                raw=None
                if method=='POST':
                    headers={k.lower():v for k,v in scope.get('headers',[])}
                    if headers.get(b'content-encoding') is not None:raise ValueError()
                    if not json_media({'content-type':headers.get(b'content-type',b'').decode('latin1')}):raise ValueError()
                    length=headers.get(b'content-length')
                    if length is not None and (not length.isdigit() or int(length)>4096):raise ValueError()
                    raw=bytearray()
                    while True:
                        message=await receive()
                        if message['type']!='http.request':raise ValueError()
                        raw.extend(message.get('body',b''))
                        if len(raw)>4096:raise ValueError()
                        if not message.get('more_body',False):break
                    parsed=AnalysisRequest.model_validate(decode(bytes(raw).decode('utf8')))
                    if parsed.as_of>datetime.now(UTC):raise ValueError()
            except (ValueError,TypeError,UnicodeError,RecursionError):
                await error_response(scope,ErrorCode.INPUT_INVALID)(scope,receive,send);return
            delivered=False
            async def analysis_receive():
                nonlocal delivered
                if raw is not None and not delivered:
                    delivered=True;return {'type':'http.request','body':bytes(raw),'more_body':False}
                return await receive()
            async def analysis_send(message):
                if message['type']=='http.response.start':
                    headers=[(k,v) for k,v in message.get('headers',[]) if k.lower() not in {b'cache-control',b'vary'}]
                    message={**message,'headers':headers+[(b'cache-control',b'private, no-store'),(b'vary',b'Cookie, Origin')]}
                await send(message)
            await self.app(scope,analysis_receive,analysis_send);return
        from src.modules.flow.api.run_schemas import (
            PRIVATE, error_response, http_request_id, is_run_endpoint,
        )

        from src.modules.flow.api.synthetic_demo_schemas import is_demo_endpoint
        if is_demo_endpoint(method, path):
            from src.shared.config import settings
            from src.modules.auth.api.router import configured
            from src.modules.flow.api.synthetic_demo_schemas import request_id, error_response as demo_error, parse_raw, json_media
            from src.modules.flow.domain.execution import ErrorCode
            request_id(scope)
            if not settings.FLOW_SYNTHETIC_DEMO_ENABLED:
                await demo_error(scope,ErrorCode.FEATURE_UNAVAILABLE)(scope,receive,send)
                return
            if not configured():
                await demo_error(scope,ErrorCode.AUTH_REQUIRED)(scope,receive,send)
                return
            if scope.get('query_string'):
                await demo_error(scope,ErrorCode.INPUT_INVALID)(scope,receive,send)
                return
            if method=='GET':
                try:
                    from uuid import UUID
                    segment=path.rsplit('/',1)[1]
                    if str(UUID(segment))!=segment.lower():raise ValueError('Invalid UUID')
                except ValueError:
                    await demo_error(scope,ErrorCode.INPUT_INVALID)(scope,receive,send)
                    return
            next_receive=receive
            if method=='POST':
                try:
                    from starlette.datastructures import Headers
                    headers=Headers(scope=scope)
                    if not json_media(headers) or len(headers.getlist('content-type'))!=1 or len(headers.getlist('content-encoding'))>1 or len(headers.getlist('content-length'))>1:
                        raise ValueError('Invalid media')
                    length=headers.get('content-length')
                    if length is not None and (not length.isascii() or not length.isdigit() or int(length)>4096):raise ValueError('Invalid length')
                    raw=bytearray()
                    while True:
                        message=await receive()
                        if message['type']!='http.request':raise ValueError('Body disconnected')
                        raw.extend(message.get('body',b''))
                        if len(raw)>4096:raise ValueError('Body too large')
                        if not message.get('more_body',False):break
                    parse_raw(bytes(raw))
                    consumed=False
                    async def body_receive():
                        nonlocal consumed
                        if not consumed:
                            consumed=True
                            return {'type':'http.request','body':bytes(raw),'more_body':False}
                        return await receive()
                    next_receive=body_receive
                except Exception:
                    await demo_error(scope,ErrorCode.INPUT_INVALID)(scope,receive,send)
                    return
            async def demo_send(message):
                if message['type']=='http.response.start':
                    headers=[(k,v) for k,v in message.get('headers',[]) if k.lower() not in {b'cache-control',b'vary'}]
                    message={**message,'headers':headers+[(b'cache-control',b'private, no-store'),(b'vary',b'Cookie, Origin')]}
                await send(message)
            await self.app(scope,next_receive,demo_send)
            return
        if is_run_endpoint(method, path):
            from src.shared.config import settings
            from src.modules.auth.api.router import configured
            from src.modules.flow.domain.execution import ErrorCode

            http_request_id(scope)
            if not settings.FLOW_RUN_ADMISSION_ENABLED:
                await error_response(scope, ErrorCode.FEATURE_UNAVAILABLE)(scope, receive, send)
                return
            if not configured():
                await error_response(scope, ErrorCode.AUTH_REQUIRED)(scope, receive, send)
                return

            async def run_private_send(message):
                if message["type"] == "http.response.start":
                    headers = [(key, value) for key, value in message.get("headers", [])
                               if key.lower() not in {b"cache-control", b"vary"}]
                    message = {**message, "headers": headers + [
                        (key.lower().encode(), value.encode()) for key, value in PRIVATE.items()
                    ]}
                await send(message)

            await self.app(scope, receive, run_private_send)
            return
        if (method, path) in PUBLIC_ROUTES:
            await self.app(scope, receive, send)
            return
        personal = (
            method == "GET"
            and (
                path.startswith("/api/flow/reports")
                or path in {"/api/reports", "/api/reports/archive"}
            )
            or method == "DELETE"
            and path.startswith("/api/flow/reports/")
        )
        if personal:
            from src.modules.auth.api.router import configured

            if configured():

                async def private_send(message):
                    if message["type"] == "http.response.start":
                        headers = [
                            (key, value)
                            for key, value in message.get("headers", [])
                            if key.lower() not in {b"cache-control", b"vary"}
                        ]
                        message = {
                            **message,
                            "headers": headers
                            + [
                                (b"cache-control", b"private, no-store"),
                                (b"vary", b"Cookie, Origin"),
                            ],
                        }
                    await send(message)

                await self.app(scope, receive, private_send)
                return
        status = 401 if personal else 403
        error = (
            {"code": "AUTH_REQUIRED", "message": "인증이 필요합니다."}
            if personal
            else {
                "code": "FEATURE_UNAVAILABLE",
                "message": "현재 사용할 수 없는 기능입니다.",
            }
        )
        await JSONResponse(
            {"detail": error},
            status_code=status,
            headers={
                "Cache-Control": "private, no-store",
                "Vary": "Cookie, Authorization, Origin",
            },
        )(scope, receive, send)
