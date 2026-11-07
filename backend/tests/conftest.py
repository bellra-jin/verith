"""테스트 공통 fixture.

- DB: docker PostgreSQL(5433) 실제 사용. 테스트별 트랜잭션 + savepoint 롤백으로 격리
  (schema 는 이미 alembic 로 적용돼 있다고 가정 — 테스트에서 migration 실행하지 않음).
- DB URL: 명시적 TEST_DATABASE_URL + 승인된 일회용 자원 + 읽기 전용 preflight 필수.
  앱 DB fallback·경고 후 실행·자동 생성/초기화는 금지한다.
- AI: FakeAIClient 로 mock(실제 AI 서버 호출 없음). `ai_output` 을 indirect 로 바꿔 계약위반 등 검증.
"""

from __future__ import annotations

import copy
import os
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from dotenv import dotenv_values
from tests.db_safety import (
    UnsafeTestDatabase,
    preflight_database,
    attest_engine_connection,
)
from tests.fixtures.ai_output import (
    DUP_OUTPUT,
    MALFORMED_OUTPUT,
    MISMATCH_TICKER_OUTPUT,
    NORMAL_OUTPUT,
)

_AI_OUTPUTS: dict[str, dict] = {
    "NORMAL": NORMAL_OUTPUT,
    "DUP": DUP_OUTPUT,
    "MISMATCH": MISMATCH_TICKER_OUTPUT,
    "MALFORMED": MALFORMED_OUTPUT,
}


class FakeAIClient:
    """analyze_technical 이 미리 지정한 output(dict)을 반환. 실제 네트워크 없음."""

    def __init__(self, output: dict) -> None:
        self._output = output

    async def analyze_technical(self, payload: dict) -> dict:
        # 실제 AI 처럼 요청 request_id 를 응답에 echo(placeholder 치환). 매 호출 deepcopy.
        out = copy.deepcopy(self._output)
        if out.get("request_id") == "__REQUEST_ID__":
            out["request_id"] = payload["request_id"]
        return out


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """트랜잭션 안에서 세션 제공 → 종료 시 롤백(테스트 데이터 비영속)."""
    app_url = os.getenv("DATABASE_URL") or dotenv_values(
        Path(__file__).resolve().parents[1] / ".env"
    ).get("DATABASE_URL")
    try:
        approval = await preflight_database(os.environ, app_url)
    except UnsafeTestDatabase as exc:
        pytest.fail(str(exc), pytrace=False)
    engine = create_async_engine(
        approval.url, connect_args=approval.connection_parameters()
    )
    conn = None
    try:
        conn = await engine.connect()
        await attest_engine_connection(conn, approval)
    except Exception as exc:  # noqa: BLE001 — 접속 불가를 명확한 안내로 전환
        if conn is not None:
            await conn.close()
        await engine.dispose()
        pytest.fail(
            f"승인된 일회용 테스트 DB 연결/정체 확인 실패({type(exc).__name__}). 앱 DB 대체 금지.",
            pytrace=False,
        )
    trans = await conn.begin()
    session = AsyncSession(
        bind=conn,
        join_transaction_mode="create_savepoint",  # service 의 commit 을 savepoint 로 흡수
        expire_on_commit=False,
    )
    try:
        yield session
    finally:
        await session.close()
        await trans.rollback()
        await conn.close()
        await engine.dispose()


@pytest.fixture
def ai_output(request) -> dict:
    """기본 AI output(정상). indirect parametrize 키(DUP/MISMATCH/MALFORMED)로 교체."""
    return _AI_OUTPUTS[getattr(request, "param", "NORMAL")]


@pytest_asyncio.fixture
async def client(db_session: AsyncSession, ai_output: dict) -> AsyncClient:
    """앱 세션/AIClient 를 테스트용으로 교체한 httpx AsyncClient."""

    # Import only after the db_session preflight. App startup is not run here.
    from db.session import get_session
    from src.api.deps import get_ai_client
    from src.api.main import app

    async def _override_session():
        yield db_session

    app.dependency_overrides[get_session] = _override_session
    app.dependency_overrides[get_ai_client] = lambda: FakeAIClient(ai_output)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
