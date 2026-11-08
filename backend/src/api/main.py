from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db.graph import close_driver, ensure_constraints
from src.shared.config import settings
from src.shared.http.access_boundary import AccessBoundary
from src.modules.industry.api import router as industry_reports
from src.modules.news.api import router as news
from src.modules.reports.api import router as reports
from src.modules.stocks.api import router as stocks
from src.modules.technical.api import router as technical_reports
from src.modules.fundamental.api import router as fundamental_reports
from src.modules.auth.api import router as auth
from src.modules.flow.api import router as flow_reports
from src.modules.flow.api import run_router as flow_runs
from src.modules.auth.application.session_service import AuthenticationRequired
from src.modules.auth.infrastructure.google_oidc import LoginFailed
from starlette.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # 시작: Neo4j 노드 정체성 키 유니크 제약 보장(멱등).
    try:
        if settings.ENABLE_NEWS_GRAPH:
            await ensure_constraints()
        yield
    finally:
        await close_driver()


app = FastAPI(title="verith-backend", lifespan=lifespan)
app.add_middleware(AccessBoundary)

# 프론트(다른 origin)의 브라우저 직접 호출 허용. 허용 origin 은 settings(CORS_ORIGINS, env override).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],  # GET/POST/DELETE/OPTIONS 등
    allow_headers=["*"],
)


@app.exception_handler(AuthenticationRequired)
async def authentication_error(request, exc):
    return JSONResponse(
        {"detail": {"code": "AUTH_REQUIRED", "message": "인증이 필요합니다."}},
        status_code=401,
        headers=auth.PRIVATE,
    )


@app.exception_handler(LoginFailed)
async def login_error(request, exc):
    response = JSONResponse(
        {"detail": {"code": "LOGIN_FAILED", "message": "로그인을 다시 시작해 주세요."}},
        status_code=400,
        headers=auth.PRIVATE,
    )
    response.delete_cookie(
        auth.CORRELATION_COOKIE,
        path="/api/auth/callback",
        secure=auth.secure_cookie(),
        httponly=True,
        samesite="lax",
    )
    return response


@app.exception_handler(PermissionError)
async def permission_error(request, exc):
    return JSONResponse(
        {
            "detail": {
                "code": "FEATURE_UNAVAILABLE",
                "message": "현재 사용할 수 없는 기능입니다.",
            }
        },
        status_code=403,
        headers=auth.PRIVATE,
    )


@app.exception_handler(SQLAlchemyError)
async def database_error(request, exc):
    return JSONResponse(
        {
            "detail": {
                "code": "SERVICE_UNAVAILABLE",
                "message": "요청을 처리할 수 없습니다.",
            }
        },
        status_code=503,
        headers=auth.PRIVATE,
    )


app.include_router(auth.router)
app.include_router(technical_reports.router)
app.include_router(fundamental_reports.router)
app.include_router(flow_reports.router)
app.include_router(flow_runs.router)
app.include_router(industry_reports.router)
app.include_router(reports.router)
app.include_router(news.router)
app.include_router(stocks.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "backend"}
