"""Google login and revocable session endpoints. Unconfigured deployment fails closed."""

from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.responses import JSONResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_session
from src.modules.auth.infrastructure.google_oidc import GoogleConfig, GoogleOIDC, LoginFailed
from src.shared.config import settings
from src.modules.auth.application.session_service import AuthenticationRequired, authenticate, csrf_token, issue_session, link_verified_identity, revoke_session, verify_csrf

router = APIRouter(prefix="/api/auth", tags=["auth"])
SESSION_COOKIE = "verith_session"
CORRELATION_COOKIE = "verith_login"
PRIVATE = {"Cache-Control": "private, no-store", "Vary": "Cookie, Origin"}


@lru_cache(maxsize=1)
def get_oidc():
    config = GoogleConfig(
        settings.GOOGLE_CLIENT_ID,
        settings.GOOGLE_CLIENT_SECRET,
        settings.AUTH_REDIRECT_URI,
        tuple(
            item.strip() for item in settings.AUTH_ORIGINS.split(",") if item.strip()
        ),
        settings.AUTH_ALLOW_LOCAL_HTTP,
    )
    config.validate()
    return GoogleOIDC(config)


def configured():
    try:
        get_oidc()
        return True
    except (ValueError, TypeError):
        return False


def secure_cookie():
    return not (
        settings.AUTH_ALLOW_LOCAL_HTTP
        and settings.AUTH_REDIRECT_URI.startswith("http://")
    )


def unique_cookie(request: Request, name: str) -> str | None:
    tokens = []
    for header in request.headers.getlist("cookie"):
        tokens.extend(
            part.strip().split("=", 1)[1]
            for part in header.split(";")
            if part.strip().split("=", 1)[0] == name and "=" in part
        )
    return tokens[0] if len(tokens) == 1 else None


def validate_local_auth_host(request: Request) -> None:
    """Local v0.5 BFF contract: localhost:3200 -> localhost:8200 only.

    Callback/redirect/cookie settings still come solely from validated server
    configuration, never Host or proxy headers. Production host policy is separate.
    """
    config = get_oidc().config
    if config.redirect_uri.startswith("http://"):
        if request.headers.get("host") != "localhost:8200" or request.headers.get(
            "x-forwarded-host"
        ) not in (None, "localhost:3200"):
            raise HTTPException(
                403,
                detail={
                    "code": "AUTH_REQUEST_INVALID",
                    "message": "잘못된 인증 요청입니다.",
                },
                headers=PRIVATE,
            )


async def request_principal(
    request: Request,
    session: AsyncSession,
    *,
    mutation=False,
    exclusive_session_lock=False,
):
    if not configured():
        raise AuthenticationRequired()
    validate_local_auth_host(request)
    token = unique_cookie(request, SESSION_COOKIE)
    if token is None:
        raise AuthenticationRequired()
    principal = await authenticate(
        session, token, lock=mutation, exclusive_lock=exclusive_session_lock
    )
    if mutation:
        verify_csrf(
            principal,
            request.headers.get("x-csrf-token"),
            request.headers.get("origin"),
            list(get_oidc().config.origins),
        )
    return principal


@router.get("/login")
async def login(request: Request):
    if not configured():
        raise HTTPException(
            503,
            headers=PRIVATE,
            detail={
                "code": "AUTH_UNCONFIGURED",
                "message": "로그인 설정이 필요합니다.",
            },
        )
    validate_local_auth_host(request)
    try:
        url, browser = await get_oidc().start()
    except Exception:
        raise LoginFailed() from None
    response = RedirectResponse(url, status_code=303, headers=PRIVATE)
    response.set_cookie(
        CORRELATION_COOKIE,
        browser,
        max_age=300,
        httponly=True,
        secure=secure_cookie(),
        samesite="lax",
        path="/api/auth/callback",
    )
    return response


@router.get("/callback")
async def callback(request: Request, session: AsyncSession = Depends(get_session)):
    params = request.query_params
    # Keep the callback code out of ASGI access-log path/query formatting.
    request.scope["query_string"] = b""
    if not configured():
        raise HTTPException(
            503,
            headers=PRIVATE,
            detail={
                "code": "AUTH_UNCONFIGURED",
                "message": "로그인 설정이 필요합니다.",
            },
        )
    validate_local_auth_host(request)
    try:
        issuer, subject = await get_oidc().callback(
            params, unique_cookie(request, CORRELATION_COOKIE)
        )
        user = await link_verified_identity(session, issuer=issuer, subject=subject)
        old = unique_cookie(request, SESSION_COOKIE)
        if old:
            try:
                principal = await authenticate(session, old)
            except AuthenticationRequired:
                pass
            else:
                # Revoke old session in the same transaction as replacement creation.
                from sqlalchemy import update, func
                from db.models.auth.models import AuthSession

                await session.execute(
                    update(AuthSession)
                    .where(AuthSession.id == principal.session_id)
                    .values(revoked_at=func.clock_timestamp())
                )
        token, _ = await issue_session(
            session, user, ttl_seconds=settings.AUTH_SESSION_TTL_SECONDS
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise LoginFailed() from None
    response = RedirectResponse("/", status_code=303, headers=PRIVATE)
    response.delete_cookie(
        CORRELATION_COOKIE,
        path="/api/auth/callback",
        secure=secure_cookie(),
        httponly=True,
        samesite="lax",
    )
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.AUTH_SESSION_TTL_SECONDS,
        httponly=True,
        secure=secure_cookie(),
        samesite="lax",
        path="/",
    )
    return response


@router.get("/session")
async def session_info(request: Request, session: AsyncSession = Depends(get_session)):
    principal = await request_principal(request, session)
    return JSONResponse(
        {
            "user_id": str(principal.user_id),
            "expires_at": principal.expires_at.isoformat(),
            "csrf_token": csrf_token(principal),
        },
        headers=PRIVATE,
    )


@router.post("/logout")
async def logout(request: Request, session: AsyncSession = Depends(get_session)):
    # Acquire the revoke row exclusively from the start; concurrent logouts must
    # never acquire two SHARE locks and deadlock while upgrading to UPDATE.
    principal = await request_principal(
        request, session, mutation=True, exclusive_session_lock=True
    )
    await revoke_session(session, principal)
    response = JSONResponse({"logged_out": True}, headers=PRIVATE)
    response.delete_cookie(
        SESSION_COOKIE, path="/", secure=secure_cookie(), httponly=True, samesite="lax"
    )
    return response
