## CF-008 합성 데모 웹

별도 `/flow/demo`의 합성 요청/저장 결과 조회다. [계약](../backend/docs/flow_synthetic_demo.md)·[작업 기록](work/CF-008-flow-synthetic-demo.md)을 따른다. Backend/Frontend 서버 demo gate는 기본 닫힘이며, 실제 설정/키/외부 API·보관함 게시는 바꾸지 않는다. 기존 admission 공개 gate와 독립이다.

새 고정 PG mode는 `--verify-flow-synthetic-demo-db`이고 기존 own-resource/attestation/자기 HOME/최종 정리를 전제로 한다. Backend/FE 보호 unit·type/lint와 실제 PG/ASGI, Next HTTP, 브라우저를 나누어 보고한다. 기존 Mac build 차단과 demo flag가 preload whitelist에서 제거되는 제약 때문에 현재 helper의 gate-on HTTP는 실행 준비 완료가 아니다. guard를 넓히거나 원본 앱·새 설치·일반 runner로 우회하지 않는다. 아래 이전 검사는 각 당시 이력이다.

## CF-007 내부 fake 실행/저장

[내부 계약](../backend/docs/flow_fake_execution.md)·[작업 기록](work/CF-007-flow-fake-execution.md)을 따른다. 봉인 합성 입력에 strict opt-in한 실제 owner의 fake 일회 실행/내부 결과 저장·재조회만 연결한다. 공개 route/BFF/UI/기존 보관함·실제 KIS/AI는 포함하지 않는다. receipt의 pending은 계속 receipt_only다.

기존 보호 self/unit과 고정 `--verify-flow-fake-execution-db` mode를 사용한다. clean env·정확한 기존 Python/dependency·새 owned PG proof/attestation·자기 HOME·finally 정리를 전제로 하며 일반 pytest/app DB/실환경으로 대체하지 않는다. 실제 launcher와 결과는 작업 기록에 남긴다. 아래 이전 단계는 당시 이력이다.

## CF-006 내부 합성 입력 준비

공개 route/실행권 없이 receipt의 입력 준비본만 봉인·본인 재조회한다. [내부 계약](../backend/docs/flow_input_snapshot.md)·[작업 기록](work/CF-006-flow-input-snapshot.md)을 따른다. 기존 보호 self/unit과 고정 DB-only `--verify-flow-input-snapshot-db`만 해당 검증 입구다. DB-only는 clean env·기존 Python `-I -S -B`·정확한 site-packages launcher, 검증된 local Docker/기존 image·새 소유 PG·attested 연결·자기 HOME·finally 정리를 전제로 한다. 실제 launcher는 작업 기록에 있다. 일반 앱/pytest/.env/기존 DB로 대체하지 않는다.

최종 self18/unit851 및 실제 PG 합성 준비/경합 검사를 기존 결과와 구분한다. 새 snapshot은 실행 가능 작업이 아니며 실제 AI/Google/브라우저/worker/결과 게시를 검증한 것이 아니다. 아래 이전 단계는 당시 이력이다.

# 공용 환경 참고와 실행 경계

## CF-005 한정 관측 안내 검사

[관측 정책](../ai/docs/contracts/flow/observation-window.md)·[CF-005 기록](work/CF-005-flow-observation-window.md)은
v1 숫자/저장 원문·Gate 판정을 유지한 표시/LLM facts 보완이다. 기존 Backend self-test/unit과
Frontend self-test/unit/standalone type/대상 lint 입구만 사용한다. exact stdlib helper1·HTML을 포함한
source-only4·공통 합성 JSON과 고정 unit만 추가한다. 전체 launcher와 실제 수는 기록을 따른다.
pandas/Gate2/Jinja/React DOM/브라우저/실제 LLM·키/캐시/API/DB·앱 실행은 포함하지 않는다.
아래 CF-004/CF-003/ST-001 수치는 각 단계 이력이며 이번 검사 결과로 재사용하지 않는다.


## CF-004 한정 캐시 검사

현재 무키 Flow 캐시 보완은 [캐시 계약](../ai/docs/contracts/flow/kis-token-cache.md)과
[CF-004 작업 기록](work/CF-004-flow-kis-token-cache.md)을 따른다. 기존 Backend 보호 입구의
`self-test`/`unit`에 exact stdlib AI source 하나와 고정 unit 하나만 추가한다. clean env와
기존 절대 Backend Python `-I -S`를 사용하며 전체 launcher는 작업 기록에 있다.
실제 KIS client import·AI pytest·키/.env·기존 캐시·외부 KIS/AI·DB는 실행하지 않는다.
아래 CF-003/ST-001 수치와 명령은 해당 단계 이력이며 이번 검증 결과로 재사용하지 않는다.

## CF-003 현재 접수 기반 검증

현재 feature 기준은 PR #6 병합 `d67f731b1c2f452179d66abaa2b3381cccb8a15d`다.
아래 ST-001 수치/차단/명령은 당시 이력이며 이번 변경의 통과 증거가 아니다.
[접수 계약](../backend/docs/flow_run_admission.md)·[CF-003 작업 기록](work/CF-003-flow-run-admission.md)을 따른다.
기존 clean env·절대 Python -I -S의 `backend/scripts/check_safe.py self-test`/`unit`이 보호 단위 입구다.
새 `backend/scripts/cf002_interactive_login.py --verify-flow-admission-db`는 소유 증명된 새 PG만 사용하는
고정 DB-only 분기이며 직접 pytest/기존 .env fixture/실제 앱 DB 대체가 아니다.
전체 launcher·실행 준비/제한은 작업 기록의 최종 실제 명령을 확인한다. 문서의 경로는 실행 승인이나
Google/AI/키 사용 허가가 아니며 Next/BFF/UI·worker를 기동하지 않는다.

> **최종 구조 우선 계약:** ST-001 v1.15(명시 Flow 설정·최종 marker 정리)에 따라 불필요한 old shim을 제거하며 canonical 구현 하나로 정리한다. Flow 마지막3도 AI 루트 .env 명시 정책으로 이동했다. 실제 설정 값/AI 실행은 미검증이다. [진행 기록](work/ST-001-layout-progress.md)을 따른다.

> **현재 안내 — ST-001 v1.10:** 실제 폴더 이동은 [전체 진행 기록](work/ST-001-layout-progress.md)을 따릅니다. 아래 3-A 정적 검사·v1.7/3-B 보류·실패·명령은 당시 이력이며 재배치 비교 대기는 해소됐습니다. 현재 FE-01 standalone core/image tsc와 대상 lint는 통과했고 full generated-route/typegen·build/HTTP 검증은 별개로 미완료입니다. manifest/과거 source hash·수치를 새 상태로 덮어쓰지 않습니다.

ST-001 v1.3 / 3-A, 검토 기준 `6308d8c9517d8d8d4f1c7b69e845fb5fe33836ef`.
공용 source를 정적으로 읽어 작성한 **비밀 없는 참고 예제**다. 실제 설정·안전한 검사 bootstrap·
실행 승인이나 검증된 재현 환경이 아니다. 예제를 .env로 복사하거나 source하는 명령을 제공하지 않는다.
기존 .env/credentials/ignored Compose·Docker Env·개인 설정은 읽거나 바꾸지 않는다.

## 먼저 읽을 자료

[문서 권위](documentation.md), [root 안내](../AGENTS.md), [현재 책임/DB 경계](architecture/current-boundaries.md),
[포트 계약](local_ports.md)을 함께 적용한다. [Frontend](examples/frontend.env.example),
[Backend](examples/backend.env.example), [AI](examples/ai.env.example),
[명시 선택 Compose](examples/compose.local.example.yaml)는 자동 탐색 이름이 아니다.
실제 시작 전 대상·자격·비용/데이터 영향·격리와 필요한 승인을 별도로 확인한다.
기존 관리 Docker/migration/seed/restore 명령은 기본 테스트 준비가 아니다.

선언 의존성은 [Frontend package](../frontend/package.json)/[lock](../frontend/package-lock.json),
[Backend pyproject](../backend/pyproject.toml)/[lock](../backend/uv.lock),
[AI pyproject](../ai/pyproject.toml)/[lock](../ai/uv.lock)이다. Next 16.2.10, Python 선언 >=3.12이며
Backend는 SQLAlchemy/asyncpg, Fundamental은 psycopg를 사용한다. 선언/lock 확인은 설치 상태나
서비스 동작 확인이 아니다. 자동 sync·새 설치·앱 config import는 이 단계에 없다.

## Frontend 변수

소비자는 [공개 helper](../frontend/src/shared/api/backend.ts),
[서버 URL/SSR](../frontend/src/shared/server/session-backend.ts), [BFF](../frontend/src/shared/server/session-proxy.ts)다.

| 변수 | 형식·비밀 여부 | 필수 조건·미설정/빈 값 동작 |
|---|---|---|
| NEXT_PUBLIC_API_URL | 공개 HTTP base URL, 비밀 금지. 참고 http://localhost:8200 | 비개인 helper만 사용. 미설정은 localhost:8200, 명시 빈 값은 `??` 때문에 그대로 남아 상대 경로가 될 수 있음 |
| BACKEND_URL | 서버 전용 HTTP(S) origin, 자격/query/path 금지. 참고 http://localhost:8200 | 개인 BFF/SSR에 명시 필요. 미설정/빈 값은 거부하며 공개 변수로 fallback하지 않음. 잘못된 URL 문자열은 URL 파싱 예외도 가능하므로 정상 종료를 보장하는 설정 검증으로 확대하지 않음 |

브라우저는 http://localhost:3200, 서버는 Backend 8200이다. 정본 local Backend 사용 시
Host/Origin/forwarded-host는 3200 계약을 유지한다. localhost와 127.0.0.1을 브라우저 인증에서
혼용하지 않는다. Google/DB 비밀은 Next나 NEXT_PUBLIC 변수에 넣지 않는다. 세션 전달·no-store·
원문 중복 Cookie·최종 Backend owner 검증을 유지하며 예제로 공개 save/직접 AI 경로를 열지 않는다.

## Backend 변수

[Settings/_load_settings](../backend/src/shared/config.py)를 import하지 않고 읽었다. 기본 dotenv source는
backend/.env이며 프로세스 환경과 별개로 읽힐 수 있다. 예제를 두었다고 dotenv가 비활성화되지 않는다.
아래 빈 값은 자격 발급이나 인증 비활성화 성공이 아니다.

| 변수 | 형식·비밀 여부 | 필수 조건·미설정/빈 값·기존 기본 |
|---|---|---|
| DATABASE_URL | 비밀 DSN. `postgresql+asyncpg://REPLACE_WITH_APPROVED_USER:REPLACE_WITH_APPROVED_PASSWORD@localhost:15432/REPLACE_WITH_APPROVED_DATABASE`는 형식 예시 | startup loader가 미설정/빈 값/공백을 거부. 별도 대상/역할 확인 없이 앱 또는 테스트 DB에 연결하지 않음 |
| TEST_DATABASE_URL | 별도 검사 DSN/비밀, 예제는 빈 값 | 앱 runtime 대체값 아님. [DB guard](../backend/tests/db_safety.py)와 승인 일회용 자원·제한 역할·읽기 전용 preflight 필요. 가짜 approval/고정 manifest 없음 |
| AI_SERVICE_URL | 비밀 아닌 base URL, 참고 http://localhost:9200 | 실제 기본 빈 문자열. loader에는 필수 검증 없음. 오래된 주석의 ‘없으면 오류’를 실제 보장으로 쓰지 않음 |
| AI_REQUEST_TIMEOUT_SECONDS | 초 단위 float, 비밀 아님 | 기존 기본 90.0. 미설정 시 기본, 빈 문자열은 숫자 파싱 오류 가능. timeout 변경/실제 AI 호출 없음 |
| GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET | client 식별자/비밀, 둘 다 빈 값 | startup DB 필수와 별개. login/protected 경로는 키/유효 auth 구성 없으면 fail-closed. 실제 client/계정 사용·Console 변경 없음 |
| AUTH_REDIRECT_URI | 외부 callback URI, 비밀 아님 | 예제 http://localhost:3200/api/auth/callback. code 교환도 같은 URI. 미설정/빈 값·잘못된 구성은 인증 거부 |
| AUTH_ORIGINS | 콤마 구분 정확한 origin, 비밀 아님 | 기본 빈 문자열. 로컬 참고 http://localhost:3200. callback origin 포함/검증 필요 |
| CORS_ORIGINS | 콤마 구분 origin, 비밀 아님 | 기본 http://localhost:3200. 빈 값은 허용 목록이 비며 인증 허용을 대신하지 않음 |
| AUTH_ALLOW_LOCAL_HTTP | bool, 비밀 아님 | 기본/예제 false. 로컬 callback을 실제 시험할 별도 단계에서만 명시 true와 localhost:3200 예외를 함께 선택. HTTPS/쿠키/CSRF 일반 완화 아님 |
| AUTH_SESSION_TTL_SECONDS | 정수 초, 비밀 아님 | 기본 3600, `0 < 값 <= 2147483647`. 유한 세션 수명이며 빈 값/범위 오류는 설정 오류 |
| ENABLE_NEWS_GRAPH | bool, 비밀 아님 | 기본/예제 false. 빈 문자열은 bool 검증 오류 가능. true일 때만 아래 3개 필수 |
| NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD | Bolt URI / 사용자 / 비밀 | 기본 빈 값. graph true일 때 loader가 셋의 빈 값/공백 거부. host bolt://localhost:17687, 같은 network bolt://neo4j:7687 |
| DART_API_KEY | 비밀, 빈 값 | corp-code 수동 sync 전용, 일반 startup 비필수. 실제 sync 전 별도 확인 |
| DART_BASE_URL | 공개 URL | 기본/예제 https://opendart.fss.or.kr/api. 미설정 시 기본, 빈 값은 문자열로 남음 |

인증 근거는 [Google 구성 검증](../backend/src/modules/auth/infrastructure/google_oidc.py)과
[auth routes](../backend/src/modules/auth/api/router.py)다. 고정 Google discovery/최소 openid/PKCE·
state/nonce/서버 폐기 세션 정책을 바꾸지 않는다. 예제에는 실제 키·테스트 사용자·브라우저 자격이 없다.

## AI 변수와 fallback

AI 예제에 Backend 앱 DSN의 호환 alias 항목을 넣지 않는다. 부모 프로세스의 앱 자격 상속도
별도로 차단해야 하며 빈 VERITH_DB_URL만으로 모든 소비자의 안전성을 보장하지 않는다.
설정·호출 경로에 따라 dotenv 탐색/외부 호출/모델 로딩·다운로드가 가능하다. **예제나 빈 키는
AI 전체 차단·오프라인 모드·안전한 비활성화가 아니다.** 아래는 연결/모델 경계이며 분석 임계값 전부를
새 설정 체계로 옮기지 않는다.

| 변수 | 소비자 source | 형식·비밀/선택 조건·미설정과 빈 값 |
|---|---|---|
| BACKEND_BASE_URL | [Supervisor config](../ai/src/supervisor/config.py), [News config](../ai/src/agents/news/config.py) | HTTP URL, 비밀 아님. 양쪽 모두 미설정/빈 값/공백이면 localhost:8200. resolver/News 호출 때 연결될 수 있음 |
| BACKEND_AUTH_TOKEN | 같은 News config | 선택 비밀. 미설정/공백은 None. 기존 주석의 내부망 전제를 새 서비스 인증/현재 차단 해제로 간주하지 않음 |
| OPENAI_API_KEY / OPENAI_MODEL | [Technical loader](../ai/src/agents/technical/config.py), [Fundamental config](../ai/src/agents/fundamental/core/config.py) | 비밀키/모델명. Technical은 loader 호출 시 둘의 공백을 거부하며 모델 기본 없음. Fundamental은 키 기본 빈 값, 모델 기존 기본 있음; 빈 키는 OpenAI fallback 생략, Qwen까지 중단하는 조건 아님 |
| OPENAI_API_KEY | [Flow explain](../ai/src/agents/flow/infrastructure/llm/explain.py), [Flow config](../ai/src/agents/flow/config.py) | SDK 사용 비밀. Flow 모델은 코드 INTERPRETER_MODEL에서 결정하며 OPENAI_MODEL 예제로 바뀌지 않음. 명시 AI 루트 .env/기존 process env 사용 후 호출 가능, 키 누락 처리는 SDK/해당 경로에 의존 |
| KIS_API_KEY / KIS_API_SECRET / KIS_BASE_URL | [Flow KIS](../ai/src/agents/flow/infrastructure/kis_client.py), Technical loader | 비밀 2개/HTTP URL. Flow는 누락/빈 값, Technical은 strip 후 공백까지 거부. Flow는 AI 루트 .env만 명시하고 process env의 빈 값도 우선한다. Technical의 기존 loader 탐색은 별도다. 예제 endpoint는 .invalid placeholder이며 실제 연결/토큰 발급 안 함 |
| DART_API_KEY / DART_BASE_URL | Fundamental config, [Industry config](../ai/src/agents/industry/config.py) | 비밀/공개 URL. Fundamental은 빈 키/기존 공개 URL 기본. Industry get_dart_api_key는 호출 시 누락/빈 값 거부(strip 없음). Industry는 이 DART_BASE_URL 변수를 읽지 않음 |
| VERITH_DB_URL | Fundamental config·[corp_code](../ai/src/agents/fundamental/infrastructure/data/corp_code.py) | 선택 비밀 DSN, 기본 빈 값. `AliasChoices("VERITH_DB_URL", "DATABASE_URL")` 순서로 앱 자격을 받을 위험. psycopg는 `postgresql://...` 안내; 기존 asyncpg 접두 정규화 호환도 유지 |
| QWEN_API_KEY / QWEN_BASE_URL | Fundamental config, News config | **endpoint URL, API 비밀키 아님**. Fundamental은 QWEN_API_KEY가 첫 alias, QWEN_BASE_URL이 둘째; 첫 값이 명시 빈 값이어도 둘째로 넘어간다고 보장하지 않음. 미설정은 기존 별도 모델 주소, 빈 문자열은 보존. News는 QWEN_API_KEY만 읽고 누락/빈 값/공백이면 기존 localhost 추론 주소로 fallback |
| QWEN_MODEL / LLM_DUMMY_KEY | Fundamental config·[LLM client](../ai/src/agents/fundamental/infrastructure/llm/client.py) | 모델명/SDK key 필드. 기존 코드 기본값 존재, 명시 빈 값은 그대로. 예제는 승인 대상 placeholder, 기본 무인증 endpoint의 dummy를 유효 서비스 인증으로 간주하지 않음 |
| LLM_BASE_URL / LLM_MODEL / LLM_API_KEY | Industry get_chat_llm | URL/모델명/비밀. 미설정이면 기존 별도 endpoint/모델/dummy 기본, 명시 빈 값은 그대로 전달. 예제 .invalid/빈 키는 전체 호출 차단 장치 아님 |
| EMBED_MODEL | Industry get_embeddings | 모델 식별자, 비밀 아님. 미설정이면 기존 기본, 명시 빈 값도 모델 loader에 전달. News의 EMBED_MODEL 상수는 이 env를 읽지 않음. News FinBERT/embedding과 Industry 모델 로딩·다운로드 가능 |
| NEO4J_URI / NEO4J_USERNAME / NEO4J_PASSWORD | Industry get_neo4j_graph | Bolt URI/사용자/비밀. 호출 시 누락/빈 값 거부(strip 없음). Backend NEO4J_USER와 다름. 실제 권한·Cypher 접근 미검증 |
| REDIS_URL | [Technical cache factory](../ai/src/agents/technical/infrastructure/cache_service.py) | 선택 연결 URL/자격 포함 시 비밀. 미설정/빈 값·dependency/연결 오류는 cache 생략 경로. 기본 Supervisor cache=None. 공백은 명시 차단 보장 아님 |

Fundamental `_backend_lookup()`는 URL 공백을 거부하지만 `resolve_details()`는 저장소 불가/조회 오류를
받아 지원 종목의 `static_fallback`으로 진행할 수 있다. `source`와 `CORP_CODE_FALLBACK_STATIC` risk flag·
cache를 유지한다. 이는 실제 DB 조회 성공도 Fundamental 전체 중단도 아니다. SELECT는 공유 master의
stock_code/corp_code/corp_name_from_dart 3필드뿐이며 **실제 최소 read-only 권한은 미확인**이다.
실연결 전 전용 역할/대상·필드 권한/timeout·오류 출처 검증이 필요하다. 사용자 report/auth/owner 접근,
write/DDL·앱 자격 복사·새 API나 권한 부여로 확대하지 않는다.

예제에는 기존 개인 endpoint/사설 주소·실제 모델 식별자를 추천 기본값으로 배포하지 않고
`.invalid`와 `REPLACE_WITH_APPROVED_*`를 쓴다. 이 placeholder는 모든 SDK/loader가 시작 전에
거부한다는 보장이 아니다. Supervisor LLM rewrite는 기본 on이며 News 모델과 별도 LLM 기본도
남아 있다. 3-C 안전 entry 없이 import/전체 pytest를 안전 검사로 실행하지 않는다.

## 주소·driver·자원 수명

| 대상 | host 실행 참고 | 같은 Compose network 안의 참고 |
|---|---|---|
| Frontend / Backend / AI | localhost:3200 / localhost:8200 / localhost:9200 | 예제에는 앱/AI 컨테이너가 없음 |
| Backend PostgreSQL | postgresql+asyncpg://...@localhost:15432/... | postgresql+asyncpg://...@postgres:5432/... |
| Fundamental PostgreSQL | postgresql://...@localhost:15432/... | postgresql://...@postgres:5432/...; 별도 최소 권한 확인 필요 |
| Neo4j | bolt://localhost:17687, HTTP localhost:17474 | bolt://neo4j:7687, HTTP neo4j:7474 |
| Redis | redis://localhost:16379/0 | redis://redis:6379/0; 인증 구성 미완성, 접속 안내일 뿐 |

DB listener의 127.0.0.1 bind는 브라우저 auth에서 localhost alias를 허용하는 것과 다르다.
추론용 포트와 ephemeral 검사 포트를 이 표로 일괄 치환하지 않는다.

[새 Compose 예제](examples/compose.local.example.yaml)는 명시 선택 참고 파일이며 기존 ignored 파일에서
복사하지 않았다. `verith-st001-example` namespace의 부재는 보장하지 않는다. 향후 승인 실행 전 새
project 이름과 동일 Compose labels의 컨테이너/network/volume 존재 여부·host 포트 점유를 확인하고,
충돌 시 기존 자원을 재사용/삭제하지 않고 중단한다. 이번에는 Docker 조회도 하지 않았다.

이미지는 모두 required input placeholder다. PostgreSQL은 POSTGRES_*와 PGDATA, Neo4j는 NEO4J_AUTH를
지원하는 승인 image/tag를 나중에 선택·검증해야 한다. 그 이미지의 volume 선언/UID·tmpfs 권한·확장
지원(Backend pgvector 포함)·버전 호환·존재/다운로드 가능 여부는 **미검증**이다. 자동 migration/seed가 없다.
각 필수 자격은 VERITH_EXAMPLE_*의 `${NAME:?message}` 입력 요구이며 실제 값/고정 password가 없다.
Neo4j는 optional-graph profile이고 Redis는 unfinished-redis profile로 기본 서비스에서 제외한다.
Redis는 지원되지 않는 password 환경변수를 만들지 않고 **실패 placeholder 명령(exit 78)**만 둔다.
인증을 갖춘 Redis가 실행되는 예제가 아니며 이후 검토된 인증 구성 없이는 서비스로 사용할 수 없다.
profile 제외가 Compose의 모든 변수 보간을 생략한다는 보장도 없으므로 이 파일은 즉시 실행용이 아니다.

host mapping은 127.0.0.1의 15432→5432·16379→6379·17474→7474·17687→7687/tcp뿐이다.
container_name·external/named volume·host bind·host network·privileged·socket·env_file·secret mount가 없다.
데이터 경로는 tmpfs이며 중단/제거 시 유실된다. 이는 백업/내구성/운영 보안 구성도 자동 만료/정리도 아니다.
실제 image의 추가 volume·임시 자원 수명/자기 자원만 종료할 절차를 나중에 검증해야 하며 기존 자료를
가져오거나 삭제하지 않는다. 실서비스·실제 계정·운영/private 데이터용으로 검증한 구성이 아니다.

## 3-A 당시 정적 검사와 후속 (이력)

새 YAML bytes만 기존 PyYAML SafeLoader 계열로 비확장 파싱하고 중복 key/unsafe tag/예상 밖 구조를
거부한다. `${...}`는 문자열로 유지하며 parent env를 대입하지 않는다. env 예제는 명시 새 stream만
중복/문법/다중행을 거부하는 비실행·비보간 parser로 읽는다. source/exec·자동 dotenv 탐색을 하지 않는다.
검사 결과/명령은 [3-A 기록](work/ST-001-stage-3-A.md)에 둔다. `docker compose config`도 호출하지 않는다.

기능/unit/build/lint·새 설치·앱 import·Docker up/build/pull/config·migration/seed·DB/Google/AI·
모델 다운로드는 미실행이다. 기존 전체 lint 실패와 실제 인증 미검증은 [검증 상태](documentation.md#검증-상태와-이력)에
보존한다. private override/권한/실제 포트·namespace는 미확인이다. 3-A 검토/사용자 병합 후 최신 develop에서
3-B Backend/Frontend 수집 전 안전 entry → 3-C AI 안전 entry를 각각 구현한다. 3-A 당시 둘 다 미구현이었으며,
현재 3-B 구현/차단은 아래 실행표로 구분한다. 3-C는 여전히 미구현이다.
큰 파일 분리/구조 재배치는 비교 판단 전 보류한다.

<a id="3-b-검사-입구와-현재-차단"></a>

## 3-B 검사 입구와 당시 차단 (이력)

ST-001 v1.7 / 기준 `7df12403848e480f223767232540d4c2c055ba5e`의 당시 구현 이력이다.
위 3-A 변수/미설정 표는 그대로 유지하며 실제 설정이나 앱 동작을 바꾸지 않는다.
[전체 결과·차단·선택 목록](work/ST-001-stage-3-B.md)을 함께 읽는다. **3-B 전체 수용은 미완료**다.

공개 시작은 저장소 루트에서 기존 검증된 절대 interpreter와 clean env다. 아래 `$(pwd -P)`는
현재 저장소의 canonical 절대 경로를 shell이 결정하며 worker가 임의 interpreter를 선택하는 입력이 아니다.
현재 Backend는 backend/.venv/bin/python(Python 3.12), Node는 /opt/homebrew/Cellar/node/22.7.0/bin/node다.
symlink의 canonical target·소유/mode·dependency root와 고정 패키지 존재를 입구에서 재확인한다.
다른 interpreter/새 설치로 조용히 대체하지 않는다.

```sh
/usr/bin/env -i LANG=en_US.UTF-8 TZ=UTC "$(pwd -P)/backend/.venv/bin/python" -I -S backend/scripts/check_safe.py --help
/usr/bin/env -i LANG=en_US.UTF-8 TZ=UTC OPENSSL_CONF=/dev/null /opt/homebrew/Cellar/node/22.7.0/bin/node frontend/scripts/check-local-ports.mjs --help
```

| 입구/모드 | 대상·자원·한도 | 현재 직접 확인 |
|---|---|---|
| 양쪽 --help / list / 오류 인자 | 앱/pytest import·사본/소켓/worker 전에 처리 | 각 help/list 0, external/추가 인자 2. 합성 startup canary 미실행 |
| Backend self-test / unit / 무인자 전체 | fresh -I -S bootstrap, 자기 사본·고정 6개·pytest_asyncio만 명시. 90/300/전체 480초 | v1.5에서 보호 self-test 9개·고정 6파일 unit 244개 통과, guard 0/exit 0/root 정리 완료 |
| Frontend self-test / unit | 자기 사본·기존 unit 3개와 새 안전성 회귀, 각 120초 | 최신 v1.7 self-test 20개·unit 4파일 35개 실제 통과, exit 0/root 정리 완료 |
| Frontend build / local-http | 사본 next build --webpack(900초) → production start·가짜 Backend HTTP 3개(각 120초/ready 60초), 정확한 자기 port/nonce/child | v1.5/v1.6 실패 이력 보존. v1.7 진단 1회는 22회 거부/ID 10개로 exit 78·root 정리. HTTP는 미실행. 원본 dev server/기존 build 사용 금지 |
| Frontend type / lint | 사본 tsc --noEmit --incremental false, 기존 9개+변경 mjs/cjs/HTTP helper 대상 ESLint, 각 180초 | 미실행/미검증. 전체 lint 기존 실패는 유지 |

기능 모드 명령은 위 clean launch의 마지막 --help를 지정된 고정 모드로 바꾼 형태다.
임의 추가 argv/plugin/경로/db/external 모드를 받지 않는다. npm의 `check:safe` alias도 npm/Node 자체를
clean env로 시작해야 하며 상속 NODE_OPTIONS 등을 script가 나중에 지워 해결했다고 주장하지 않는다.
이 문서에서는 검증하지 않은 npm 시작 경로를 권장 명령으로 제공하지 않는다.

초기 `/usr/bin/sandbox-exec` 사전 실행은 exit 71 / `sandbox_apply: Operation not permitted`로 실패했다.
자기 합성 canary 폴더는 제거됐고 pytest/Next/app worker는 시작하지 않았다. 이후 같은 최소 probe 한정으로 정식 require_escalated를 요청·실행했으나 -6(SIGABRT)/빈 stderr로 실패했으며 원인은 미확인이다. 두 결과는 3-B 기록에 구분한다. OS 보호를 무음 해제하거나
같은 거부 동작을 다른 실행 경로로 우회하지 않는다. 먼저 OS 보호가 허용되는 실행 대상/권한을 확인하고
같은 최소 profile과 자기 합성 canary 검증부터 이어가야 한다. 그 전에는 위 기능 모드를 실행하지 않는다.
OS 허용 환경에서의 실패 수정·독립 검토·실제 선택 검사 완료가 남아 있으며 새로운 기능 설계 결정은 없다.

threat model은 검토한 source/신뢰 dependency의 우발적 private 읽기·자격 상속·외부 연결 방지다.
악의적 native/dependency·관리자·동시 공격자에 대한 완전한 OS 격리를 주장하지 않는다.
Python audit/JS preload는 OS 보호의 대체물이 아니다. 현재 profile/native/자손·TCP/UDP/DNS 통제,
copy race/신호/timeout/TERM·KILL 뒤 종료·HTTP listener 소유 등 실제 회귀는 **미검증**이다.

구현은 Git metadata와 명시 source 교집합/고정 신규 예외, symlink·비정규·hardlink·변경 identity 거부,
검증 dependency의 읽기 전용 참조를 사용한다. home/repo 전체 읽기나 parent env 전체 상속을 허용하지 않는다.
소유 임시 root는 nonce/identity와 함께 보관하고 자기 자원만 종료/삭제한다. OS profile은 원본 private/
외부 network·사본 밖 쓰기를 제한하는 방식이며 실제 지원은 canary 통과 후에만 인정한다.
실제 DB/Google/AI/모델·Docker·migration/seed·원본 앱 기동·기존 자료 변경은 이 입구의 대상이 아니다.
3-C는 3-B 검토·수정/검증과 사용자 병합 이후 별도 단계이며 구조 재배치/큰 파일 분리는 계속 보류한다.


### 최소 native probe 후속 결과 · 본 검사는 별도

설치 macOS dyld-support.sb의 root literal 필수 규칙을 확인하고, root 디렉터리 자체의 read/existence만
두 controller profile에 추가했다. subpath /·home/repo 전체 허용이나 system.sb import는 추가하지 않았다.
과거 use_default exit 71 / 정식 승인 경로 -6 실패는 위 이력이며 다음 결과로 덮어쓰지 않는다.

새 근거에 한정한 정식 require_escalated 최소 probe에서는 true 0·허용 자기 canary cat 0/정확한 내용·
금지 자기 canary cat 1/정상 권한 거부가 순서대로 통과했고 자기 폴더 제거를 확인했다.
이는 standalone 최소 profile의 결과이며 본 Python/Node profile·native/자손·네트워크/신호·안전 회귀·
unit/build/HTTP/type/lint 통과가 아니다. 상세 명령/범위/다음 실행 조건은 3-B 기록에 있다.
컨트롤러도 같은 양성/음성 판정 순서로 보완했으며 signal/timeout/초기화 실패는 차단 성공으로 세지 않는다.
본 self-test를 공식 실행 경로에서 수행할 별도 조건/권한과 최종 코드 검토를 확인한 뒤 단계적으로 이어간다.


### 보호 self-test 실제 통과와 Native OpenSSL 시작 조건

별도 공식 require_escalated 요청으로 Backend self-test 9개를 실행해 9개 통과/exit 0/자기 root 제거를 확인했다.
Frontend의 첫 self-test는 suite 수집 전에 Node native startup이 기존 OpenSSL 기본 설정 경로에 접근하려다가
OS profile에 거부돼 controller exit 78(내부 Node 1)로 종료됐고 root는 제거됐다. 해당 설정 파일 내용은 읽거나
출력하지 않았으며 그 경로를 profile에 허용하지 않았다.

현재 Frontend 공개 clean launch는 **OPENSSL_CONF=/dev/null을 Node 시작 전에** 지정한다. controller가 나중에
환경을 지우는 조치로 native startup을 소급 보호하지 않는다. 생성한 child env·CJS allowlist·fork env·HTTP helper도
같은 고정값을 유지하고 자손 spawn에서 다른 값/누락은 거부한다. 프로세스 전용 설정 입력 제한이며 OS/전역
OpenSSL 설정 파일·서비스 보안을 변경하거나 TLS 검증을 해제하지 않는다. 이 조건의 최종 Frontend self-test는
14개 통과/실패·skip·cancel·todo 0/exit 0/자기 root 제거를 확인했다.

실제 self-test의 언어 guard·OS filesystem/native startup·정상 child/group 종료와 합성 로직 회귀는 확인했지만,
실제 Next fork/IPC·강제 TERM/KILL·live bind/HTTP·실제 DB/Google/AI 통과가 아니다. 다음은 Backend 고정 6개 unit과
Frontend 기존 unit의 개별 공식 실행 조건 확인이며, unit 결과 확인 뒤 build/HTTP/type/대상 lint로 확장한다.
이번 self-test 승인을 전체 workload 실행 허가로 확대하지 않는다. 정확한 명령·시점·실패/수정·해시·한계는 3-B 기록에 있다.


### 선택 unit 결과 · Backend 입력 범위 답변 대기

Frontend는 추적된 BFF source `src/app/api/private/[...path]/route.ts`가 일반 private-directory 이름 차단에
잘못 분류돼 두 번째 unit에서 ENOENT가 발생했다. 승인된 tracked src 입력의 정확한 이 파일만 구분하고
나머지 private/secret/key/dump/backup/log 경로 거부·index/identity/race 검증을 유지했다. 원본 route나
기존 unit 기대값은 변경하지 않았다. 공식 재실행에서 4파일·29개(10+2+3+14)가 모두 통과했고 root 제거를 확인했다.

Backend 첫 unit은 pytest 기본 logger의 /dev/null 쓰기를 Python guard가 거부해 수집 전에 중단됐다.
외부 쓰기 예외를 추가하지 않고 생성 pytest config의 log_file을 자기 root/pytest.log로 지정했다.
재실행은 수집 96개/실행 0/수집 오류 1/guard 위반 1로 중단됐고 root는 제거됐다. Flow fixture가 요구하는
`ai/src/agents/flow/export/to_json.py`와 `ai/src/agents/flow/schemas.py`가 현재 허용 입력 목록에 없다.
두 파일은 stdlib/Pydantic의 순수 exporter/schema이지만 현 정본의 config 3개 data-copy 제한 밖이므로
추가 복사/import는 정본 답변 전 보류한다. fixture 대체·skip·AI 전체 복사·원본 AI root 직접 import로 우회하지 않는다.
남은 read guard 위반의 원인도 해소 전 통과로 표시하지 않는다. 정확한 근거/대안은 3-B 기록에 있다.


### v1.5 적용 결과 · 선택 Backend 통과 / Frontend build 차단

정본 v1.5의 정확한 Flow source 2개를 기존 사본 검증 아래 추가했고, namespace 3개와 module 2개의 origin을
자기 사본의 정확한 경로와 대조한다. 인접 AI source/config/__init__는 추가하지 않는다.
Backend는 self-test 9개 통과 뒤 고정 6파일 244개가 통과했지만 read guard 1건으로 전체 exit 78이었다.
호출 진단과 설치 Python `_osx_support.py:99`의 source-only 대조로 대상이
`/System/Library/CoreServices/SystemVersion.plist`임을 확인했다. 파일 내용은 조사 도구로 읽지 않았다.
OS profile의 기존 /System 읽기는 바꾸지 않고 Python guard에 그 고정 파일의 read만 추가했다.
이후 self-test 9개와 선택 unit 244개가 모두 통과·guard 0·exit 0이며 자기 root 제거를 확인했다.
인접 metadata 경로/외부 write는 계속 거부한다. 초기 수집 오류·guard 실패는 이전 실행 이력이다.

Frontend build는 별도 공식 실행 3회 모두 webpack의 원본 `frontend/package.json` 읽기에서 차단됐다.
최종 비민감 진단은 정확한 original-project-root:package.json이며 설치 webpack readFile/CacheBackend.provide
호출이다. 원본 manifest 내용을 읽게 허용하거나 dependency/source 접근을 넓히지 않았다.
각 worker 1/controller 78·자기 group/root 정리를 확인했다. 작성 측의 단일 사본 metadata 해법 검토 전 build 반복은 보류한다.
최신 진단 회귀를 포함한 self-test 14개는 별도 공식 재실행에서 통과·root 제거됐다.
Frontend unit 29개는 진단 보완 전 실제 결과이며 production HTTP/type/lint는 아직 미실행이다.


### v1.6 package snapshot · 아직 실행 검증 전

기존 공개 package copy의 정확한 bytes/identity와 owned snapshot을 고정하고 worker/fork에서 길이·hash·identity를 검증한다.
정확한 원본 literal의 callback/sync/Promise readFile 내용만 메모리에서 응답하고 원본 open/read 권한은 추가하지 않는다.
controller의 최초 capture는 기존 copy Buffer를 재사용하고 command 전/후는 6-B.7의 공개 source 재검증을 수행한다.
신규 safety 16개/unit 31개는 실제 수집/통과 수가 아니라 구현상 선택 집합이다. 공식 self-test 실행 요청은 자동 승인 검토가
부모 source 재검증을 원본 raw-read 금지와 충돌한다고 판단해 거절하여 시작되지 않았다. 역할 구분의 확인 전 우회/재실행하지 않는다.
이전 v1.5 Backend 9개/244개·Frontend 14개/29개와 build 실패 3회는 당시 source/실행 기록으로 보존한다.


### v1.6 후속 상태 · 공식 실행과 보류 구분

최초 self-test 요청은 CreateProcess 전에 거절됐지만, copy Buffer 재사용 보완 후 별도 공식 요청은 승인돼
16개 중 15개 통과·1개 실패·exit 78·자기 root 제거를 확인했다. 잘못된 capability의 metadata 오류가 안전한 거부 대신
ENOENT를 드러낸 문제를 정규화했다. 그 재검증 요청은 최신 실행 보류 지시가 적용되어 CreateProcess 전에 거절됐다.
현재 신규 실행은 보류하며 parent의 source-copy/command 전후 공개 package 재검증과 worker 원본 raw-read 금지의
경계를 독립 검토 중이다. 최신 오류 정규화의 실행 검증·unit 31개·build·후속 검사는 미실행이다.


### v1.6 최신 직접 검증 · 17/32 통과와 추가 build 소비 차단

2026-11-08T02:54:30+09:00. 오류 메시지 정규화와 독립 검토 P2 두 건을 보완했다. responder의 상수 rawOriginalReadCalls 필드는
제거했으며 과거 출력의 0은 실측 증거에서 제외한다. 실제 설치 fs mapping의 raw consumer dispatch·원본 요청 거부를
계측하고, owned root의 bounded journal에 hit/실패/expected-negative를 보존한다. 정상 종료 기록이 없는 worker는
partial로 표시하며 native는 미관측이다. OS 합성 true/허용 cat/금지 cat 대조와 부모 공개 source 검증 읽기는 별도다.
controller packageRecord/recheckPackage/checkedCommand의 실제 연결을 합성 source·snapshot 변조, ancestor/root 교체,
command 실패/중복 실패·child receipt retire·root 소유 거부·형제 보존으로 확인했다. 새 spy가 변조용 쓰기를 읽기로 세던
첫 오류를 읽기 flags 집계로 수정했고, 최종 공식 self-test 17개·unit 4파일 32개가 모두 통과·exit 0·자기 root 정리됐다.

v1.6 build는 세 공식 실행 모두 컴파일·내장 TypeScript·정적 생성/trace 단계까지 진행했지만 guard 거부로 전체 exit 78이었다.
첫 build의 parent process 기록은 거부 1건이며 전체 자손 수치로 확대하지 않는다. journal 보강 후 두 실행은 worker 16개
(정상 exit 기록 1개/partial 15개), 관측된 원본 raw dispatch 0·추가 거부 22건·snapshot callback hit 2회였다.
부모 공개 package source 검증 읽기는 별도 4회다. 모든 자기 group/root는 제거됐다. private 파일의 실제 내용을 읽은 것은 아니다.

설치 source 대조로 telemetry/is-docker의 /proc/self/cgroup 탐색과 webpack FileSystemInfo._readFileHash의 추가 입력 해시
요청을 확인했다. 후자의 정확한 대상은 일부 redacted이며 원본 프로젝트/외부/private 분류를 포함한다. 단일 metadata snapshot
계약을 넘어 새 파일/OS/네트워크 허용·resolver/캐시 동작 변경으로 해결하지 않았다. 추가 계약 판단 전 build 반복을 보류하고
HTTP/type/대상 lint도 미실행이다. 전체 lint 기존 실패·Backend v1.5 9개/244개 통과·실DB/Google/AI 미실행은 그대로다.


### v1.7 진단 한정 결과 · 새 읽기/환경 정책 없음

2026-11-08T03:15:12+09:00. v1.7/hash를 대조한 뒤 fixed public allowset/검증 copy 입력과 실행별 HMAC-SHA-256 식별만 보강했다.
부모가 매 실행 32-byte 난수 key를 만들고 자기 0700 root/0600 capability에만 저장했다. argv/env/출력/journal/보고서에는
key를 두지 않는다. 같은 run의 worker는 같은 key로 상관 ID를 만들고 새 실행은 다른 key를 쓴다. 정리 시 capability/원시 journal도 제거했다.
진단은 기존 deny가 이미 계산한 lexical/canonical 값만 사용하고 unknown open/read/stat/exists/walk를 추가하지 않는다.
role/private-name flag·known-copy membership·API/caller family·횟수만 출력한다. private 이름의 공개 BFF source는 exact 예외 label이다.
이 label/ID는 허용 판단에 쓰지 않는다. 기존 원 실패·deny·partial/native 한계와 부모 source 검증/metadata hit/expected negative를 보존했다.

공식 self-test 20/20·unit 4파일 35/35 통과, fail/skip/cancel/todo 0·exit 0·자기 root 제거다.
후속 진단 build는 한 번 실행해 거부 22회를 정규화 대상 ID 10개로 식별하고 최종 exit 78을 유지했다.
cgroup 1개 ID 4회, unknown webpack hash 9개 ID 각 2회(총 18회)다. hash 대상은 original-project 1개·original-repo 1개·outside 7개,
모두 known-copy=false·공개 label 없음이다. outside ID 1개만 private-name flag이며 실제 credential 존재/내용이라는 뜻이 아니다.
현재 ID 수는 요청 문자열의 상관 식별이며 파일 실재/필수성·22파일을 의미하지 않는다. unknown raw 경로 역탐색은 하지 않았다.

worker 기록 16개 중 exit 1/partial 15개를 그대로 유지했고 JS 관측의 단일 원본 package literal raw dispatch 0·diagnostic failure 0,
callback metadata hit 2를 확인했다. native 전체를 관측한 것은 아니다. 부모 공개 source 검증은 별도 4회다.
child/group·자기 root·임시 key 자료 제거를 확인했다. 추가 build 반복/읽기 권한/CI·telemetry 환경/cache·resolver 변경은 하지 않으며,
HTTP/별도 type/대상 lint는 미실행이다. 식별 후 접근/대체 정책은 미결정이고 3-B 전체 수용도 미완료다.

## 현재 Flow 명시 설정 정책 (ST-001 v1.15)

[Flow KIS](../ai/src/agents/flow/infrastructure/kis_client.py), [해석](../ai/src/agents/flow/infrastructure/llm/explain.py), [수동 lab](../ai/devtools/flow/streamlit_flow_lab.py)은 같은 AI 서비스 루트의 `.env`를 명시한다. process environment는 빈 문자열도 기존 값으로 우선하며 `override=False`다. 파일이 없으면 process environment만 사용하고 feature/source 중간·부모·cwd `.env`로 자동 탐색하지 않는다. 다른 위치의 `.env`에만 의존했던 실행 환경은 사용자가 AI 루트 `.env` 또는 process environment에 설정해야 한다. 이번 정리에서 실제 자격 값을 조회·복사·이전하지 않았다.

합성 검사는 source의 엄격히 검증된 Path/call AST와 StringIO parser 동작을 확인한다. 물리 `.env` I/O·실제 자격·KIS/LLM/Streamlit 성공은 검증하지 않았다. 현재 연결 주소·다른 agent 설정 정책을 일괄 변경하는 계약도 아니다.
