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
        if path in {'/internal/technical/execution/start','/internal/technical/execution/observe'}:
            import asyncio
            from src.shared.config import settings
            from src.modules.technical.api.execution_authority_router import authenticate_headers,failure
            started=asyncio.get_running_loop().time()
            try:authenticate_headers(scope,settings.TECHNICAL_EXECUTION_AUTHORITY_TOKEN)
            except Exception:
                await failure()(scope,receive,send);return
            scope.setdefault('state',{})['technical_callback_deadline']=started+5
            try:
                async with asyncio.timeout_at(started+5):await self.app(scope,receive,send)
            except TimeoutError:await failure(504)(scope,receive,send)
            return
        if path in {'/internal/supervisor/meaning/authorize','/internal/supervisor/meaning/settle'}:
            import asyncio
            from src.shared.config import settings
            from src.modules.supervisor.api.meaning_phase_router import authenticate_headers,failure
            started=asyncio.get_running_loop().time()
            try:
                authenticate_headers(scope,settings.SUPERVISOR_MEANING_SERVICE_TOKEN)
            except Exception:
                await failure()(scope,receive,send);return
            scope.setdefault('state',{})['meaning_callback_deadline']=started+5
            try:
                async with asyncio.timeout_at(started+5):
                    await self.app(scope,receive,send)
            except TimeoutError:
                await failure(504)(scope,receive,send)
            return
        if path == '/api/technical/owned-reports' or path.startswith('/api/technical/owned-reports/'):
            from src.modules.technical.api import owned_report_schemas as technical_read
            from src.modules.auth.api.router import configured
            try: technical_read.target(method,path,scope.get('query_string',b''))
            except technical_read.ReadInvalid as failure:
                await technical_read.error(scope,failure.code)(scope,receive,send); return
            if not configured():
                await technical_read.error(scope,'AUTH_REQUIRED')(scope,receive,send); return
            async def technical_private_send(message):
                if message['type'] == 'http.response.start':
                    headers = [(k,v) for k,v in message.get('headers',[]) if k.lower() not in {b'cache-control',b'vary'}]
                    message = {**message,'headers':headers+[(b'cache-control',b'private, no-store'),(b'vary',b'Cookie, Origin')]}
                await send(message)
            await self.app(scope,receive,technical_private_send)
            return
        if path == '/api/fundamental' or path.startswith('/api/fundamental/'):
            from uuid import UUID
            from urllib.parse import parse_qsl
            from starlette.datastructures import Headers
            from src.shared.config import settings
            from src.modules.auth.api.router import configured
            from src.modules.flow.api.run_schemas import error_response,http_request_id
            from src.modules.flow.domain.execution import ErrorCode
            from src.modules.flow.api.synthetic_demo_schemas import json_media
            from src.modules.fundamental.api.analysis_schemas import FundamentalAnalysisRequest
            from src.modules.fundamental.domain.analysis import decode
            http_request_id(scope)
            async def reject(code):await error_response(scope,code)(scope,receive,send)
            if not settings.FUNDAMENTAL_ANALYSIS_ENABLED:
                await reject(ErrorCode.FEATURE_UNAVAILABLE);return
            if not configured():
                await reject(ErrorCode.AUTH_REQUIRED);return
            analyses='/api/fundamental/analyses';reports='/api/fundamental/reports';raw=None
            try:
                query=scope.get('query_string',b'')
                if path==analyses and method=='POST':
                    if query:raise ValueError()
                    headers=Headers(scope=scope)
                    if len(headers.getlist('content-type'))!=1 or not json_media(headers) or headers.getlist('content-encoding') or len(headers.getlist('content-length'))>1:raise ValueError()
                    length=headers.get('content-length')
                    if length is not None and (not length.isascii() or not length.isdigit() or int(length)>4096):raise ValueError()
                    raw=bytearray()
                    while True:
                        message=await receive()
                        if message['type']!='http.request':raise ValueError()
                        raw.extend(message.get('body',b''))
                        if len(raw)>4096:raise ValueError()
                        if not message.get('more_body',False):break
                    FundamentalAnalysisRequest.model_validate(decode(bytes(raw).decode('utf8')))
                elif path==reports and method=='GET':
                    pairs=parse_qsl(query.decode('ascii'),keep_blank_values=True,strict_parsing=True)
                    if len({k for k,v in pairs})!=len(pairs) or any(k not in {'stock_code','limit','offset'} for k,v in pairs):raise ValueError()
                elif method=='GET' and path.startswith(analyses+'/') or method in {'GET','DELETE'} and path.startswith(reports+'/'):
                    if query:raise ValueError()
                    segment=path.rsplit('/',1)[1]
                    prefix=analyses if path.startswith(analyses+'/') else reports
                    if path!=prefix+'/'+segment:
                        await reject(ErrorCode.FEATURE_UNAVAILABLE);return
                    if str(UUID(segment))!=segment.lower():raise ValueError()
                else:
                    await reject(ErrorCode.FEATURE_UNAVAILABLE);return
            except (ValueError,TypeError,UnicodeError,RecursionError):
                await reject(ErrorCode.INPUT_INVALID);return
            delivered=False
            async def fundamental_receive():
                nonlocal delivered
                if raw is not None and not delivered:
                    delivered=True;return {'type':'http.request','body':bytes(raw),'more_body':False}
                return await receive()
            async def fundamental_send(message):
                if message['type']=='http.response.start':
                    headers=[(k,v) for k,v in message.get('headers',[]) if k.lower() not in {b'cache-control',b'vary'}]
                    message={**message,'headers':headers+[(b'cache-control',b'private, no-store'),(b'vary',b'Cookie, Origin')]}
                await send(message)
            await self.app(scope,fundamental_receive,fundamental_send);return
        if path.startswith('/api/supervisor/core'):
            import asyncio,math,re
            started=asyncio.get_running_loop().time()
            from src.shared.config import settings
            from src.modules.auth.api.router import configured
            from src.modules.supervisor.api.router import failure
            from src.modules.supervisor.api.schemas import Draft,Confirm,PreparationRequest
            from src.modules.supervisor.domain.contracts import decode
            if not settings.FLOW_ANALYSIS_ENABLED:await failure(scope,'FEATURE_UNAVAILABLE',403)(scope,receive,send);return
            if not configured():await failure(scope,'AUTH_REQUIRED',401)(scope,receive,send);return
            preparation=method=='POST' and path=='/api/supervisor/core/preparations'
            timeout=75 if preparation else 140 if method=='POST' and path=='/api/supervisor/core/requests' else 15
            deadline=started+timeout
            try:
                state=scope.setdefault('state',{})
                if preparation:
                    earlier=state.get('core_deadline',deadline)
                    if type(earlier) not in {int,float} or type(earlier) is float and not math.isfinite(earlier):raise TimeoutError()
                    deadline=min(deadline,earlier)
                    state['core_preparation_started_at']=started
                    state['core_admission_deadline']=min(deadline,started+15)
                state['core_deadline']=deadline
                if scope.get('query_string') or not (method=='POST' and path in {'/api/supervisor/core/prepare','/api/supervisor/core/requests','/api/supervisor/core/preparations'} or method=='GET' and re.fullmatch(r'/api/supervisor/core/requests/[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',path) or method in {'GET','DELETE'} and re.fullmatch(r'/api/supervisor/core/preparations/[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',path)):raise ValueError()
                raw=None
                if method=='POST':
                    h=scope.get('headers',[]);ct=[v for k,v in h if k.lower()==b'content-type'];cl=[v for k,v in h if k.lower()==b'content-length']
                    if len(ct)!=1 or ct[0].split(b';')[0].strip().lower()!=b'application/json' or any(k.lower()==b'content-encoding' for k,v in h) or len(cl)>1 or cl and (not cl[0].isdigit() or int(cl[0])>16384):raise ValueError()
                    raw=bytearray()
                    async with asyncio.timeout_at(state['core_admission_deadline'] if preparation else deadline):
                        while True:
                            msg=await receive()
                            if msg['type']!='http.request':raise ValueError()
                            if len(raw)+len(msg.get('body',b''))>16384:raise ValueError()
                            raw.extend(msg.get('body',b''))
                            if not msg.get('more_body',False):break
                    (Draft if path.endswith('/prepare') else PreparationRequest if path.endswith('/preparations') else Confirm).model_validate(decode(raw))
                    if preparation and asyncio.get_running_loop().time()>=state['core_admission_deadline']:raise TimeoutError()
            except TimeoutError:await failure(scope,'DEADLINE_EXCEEDED',504)(scope,receive,send);return
            except (ValueError,TypeError,UnicodeError,RecursionError):await failure(scope,'INPUT_INVALID',422)(scope,receive,send);return
            delivered=False
            async def core_receive():
                nonlocal delivered
                if raw is not None and not delivered:delivered=True;return {'type':'http.request','body':bytes(raw),'more_body':False}
                return await receive()
            await self.app(scope,core_receive,send);return
        if path == '/api/flow/plans' or path.startswith('/api/flow/plans/'):
            import asyncio
            from starlette.datastructures import Headers
            from src.shared.config import settings
            from src.modules.auth.api.router import configured
            from src.modules.flow.api.query_plan_router import failure
            from src.modules.flow.api.query_plan_schemas import QueryPlanRequest
            from src.modules.flow.domain.query_plan import decode,PLAN_TIMEOUT_SECONDS
            from src.modules.flow.api.synthetic_demo_schemas import json_media
            async def reject(code,status):await failure(scope,code,status)(scope,receive,send)
            if not settings.FLOW_ANALYSIS_ENABLED:
                await reject('FEATURE_UNAVAILABLE',403);return
            if not configured():
                await reject('AUTH_REQUIRED',401);return
            if path!='/api/flow/plans' or method!='POST':
                await reject('FEATURE_UNAVAILABLE',403);return
            deadline=asyncio.get_running_loop().time()+PLAN_TIMEOUT_SECONDS
            scope.setdefault('state',{})['cf020_deadline']=deadline
            try:
                headers=Headers(scope=scope)
                if scope.get('query_string') or len(headers.getlist('content-type'))!=1 or not json_media(headers) or headers.getlist('content-encoding') or len(headers.getlist('content-length'))>1:raise ValueError()
                length=headers.get('content-length')
                if length is not None and (not length.isascii() or not length.isdigit() or int(length)>4096):raise ValueError()
                raw=bytearray()
                async with asyncio.timeout_at(deadline):
                    while True:
                        message=await receive()
                        if message['type']!='http.request':raise ValueError()
                        raw.extend(message.get('body',b''))
                        if len(raw)>4096:raise ValueError()
                        if not message.get('more_body',False):break
                QueryPlanRequest.model_validate(decode(bytes(raw)))
            except TimeoutError:
                await reject('DEADLINE_EXCEEDED',504);return
            except (ValueError,TypeError,UnicodeError,RecursionError):
                await reject('INPUT_INVALID',422);return
            consumed=False
            async def plan_receive():
                nonlocal consumed
                if not consumed:consumed=True;return {'type':'http.request','body':bytes(raw),'more_body':False}
                return await receive()
            async def plan_send(message):
                if message['type']=='http.response.start':
                    values=[(k,v) for k,v in message.get('headers',[]) if k.lower() not in {b'cache-control',b'vary'}]
                    message={**message,'headers':values+[(b'cache-control',b'private, no-store'),(b'vary',b'Cookie, Origin')]}
                await send(message)
            await self.app(scope,plan_receive,plan_send);return
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
