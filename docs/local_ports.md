# CF-002 v0.5 로컬 포트 계약

| 서비스 | Host 주소/포트 | 컨테이너 내부 |
|---|---|---|
| Frontend dev/start | http://localhost:3200 | 이번 범위에서 container화하지 않음 |
| Backend | http://localhost:8200 | 기존 서비스 구조 유지 |
| AI FastAPI | http://localhost:9200 | 기존 서비스 구조 유지 |
| PostgreSQL | 15432:5432 | postgres:5432 |
| Redis | 16379:6379 | redis:6379 |
| Neo4j HTTP | 17474:7474 | 7474 |
| Neo4j Bolt | 17687:7687 | neo4j:7687 |

Next 서버 전용 안내는 `BACKEND_URL=http://localhost:8200`, 비개인 공개 helper 기본은
`NEXT_PUBLIC_API_URL=http://localhost:8200`이다. 서버 URL 누락 시 공개 변수로 fallback하지 않는다.
브라우저는 localhost:3200만 사용한다. 로컬 Google 설정 안내는 다음과 같다(실제 주입 없음).

```text
AUTH_REDIRECT_URI=http://localhost:3200/api/auth/callback
AUTH_ORIGINS=http://localhost:3200
CORS_ORIGINS=http://localhost:3200
AUTH_ALLOW_LOCAL_HTTP=true
AI_SERVICE_URL=http://localhost:9200
BACKEND_BASE_URL=http://localhost:8200
```

Google code 교환의 redirect_uri도 외부에 등록한 **3200 callback 그대로**다. Next가 Backend의
8200 callback으로 전달한다는 이유로 code 교환 redirect를 바꾸지 않는다. Google ID/secret,
프로젝트/OAuth client 등록·A/B 계정 사용은 별도 승인/안전한 전달 대상이다.
AUTH_* 미설정은 계속 거부하며 운영 HTTPS/cookie 정책을 완화하지 않는다.
허용 local HTTP는 localhost:3200으로 한정하고 3000/다른 port/127.0.0.1 alias를 추가하지 않는다.
로컬 정본 Backend 인증 Host는 localhost:8200이다. Host/proxy header로 callback을 만들지 않는다.
Next의 정본 local BACKEND_URL 사용 시 Host/Origin도 localhost:3200에 맞아야 한다.
합성 app.unit과 독립 임시 HTTP 대역의 ephemeral 포트는 실제 배포 설정이 아니다.

Backend host DB DSN: `postgresql+asyncpg://<user>:<password>@localhost:15432/<database>`.
Fundamental host DB는 기존 driver에 맞춰
`postgresql://<user>:<password>@localhost:15432/<database>` (VERITH_DB_URL/DATABASE_URL).
Industry/Backend host graph는 `NEO4J_URI=bolt://localhost:17687`, HTTP UI는 localhost:17474.
Technical host cache 안내는 `REDIS_URL=redis://localhost:16379/0`이며 미설정 시 cache 비활성이다.
Compose 내부 서비스명/포트는 위 표대로 유지한다.

현재 파일 패치는 실행 중 서비스 전환이 아니다. 기존 .env·credentials·Docker Env는 읽거나
수정하지 않았고 private override가 새 값과 일치하는지는 미확인이다. 기존 Verith 컨테이너는
과거 PortBindings를 유지할 수 있다. 재생성/재기동은 대상·연결 단절·private override 확인 뒤
별도 승인 대상이다. 다른 프로젝트 프로세스/컨테이너·volume/데이터를 변경하지 않는다.
Docker-compose.yml은 현재 저장소 ignore 대상이므로 로컬 파일 수정과 Git 공유 상태를 구분한다.
환경/비밀 섹션을 포함한 전체 Compose 출력·docker compose config 검증을 하지 않는다.
현재 검증은 정적 YAML의 ports 및 비포트 구조를 메모리에서 대조한다.

Frontend env-free 검증은 `node frontend/scripts/check-local-ports.mjs`를 사용한다.
private 환경 파일을 복사하지 않은 새 임시 프로젝트와 합성 HTTP 대역만 실행·정리한다.
실행 직전 점유를 재확인하며 점유된 기존 프로세스를 종료하지 않는다.
AI 추론용 8001/v1·외부 모델 주소·토큰 수·과거 실행 기록은 포트 일괄 치환 대상이 아니다.
