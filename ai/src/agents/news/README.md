

## CF-002 v0.5 로컬 연결 안내

AI FastAPI 실행 주소는 `http://localhost:9200` (`uv run uvicorn src.main:app --reload --port 9200`, ai 루트),
Backend resolver/HTTP 경계는 `BACKEND_BASE_URL=http://localhost:8200`이다.
Backend의 `AI_SERVICE_URL` 안내도 9200이다. News는 계속 Backend HTTP로만 DB에 접근한다.
Fundamental의 `VERITH_DB_URL`/`DATABASE_URL`은 기존 소비자 드라이버 규약을 유지하며
host 포트15432만 사용한다. 예: `postgresql://<user>:<password>@localhost:15432/<database>`.
Industry의 host `NEO4J_URI=bolt://localhost:17687` (HTTP UI 17474), Technical의 선택적
host cache는 `REDIS_URL=redis://localhost:16379/0`이다. REDIS_URL 미설정은 계속 cache 비활성이다.
Compose 내부는 postgres:5432·redis:6379·neo4j:7687을 유지한다. 추론용 8001/v1이나 외부
모델 서버 주소는 AI FastAPI 서비스 포트가 아니므로 바꾸지 않는다.
기존 private 환경값은 미확인이다. 이 안내는 실제 AI/DB/Redis/Neo4j 기동·호출·계정 설정을
실행했다는 뜻이 아니며, CF-002 사용자 경로의 새 분석/저장 차단은 그대로다.
