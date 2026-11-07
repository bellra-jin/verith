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
            from src.api.routes.auth import configured

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
