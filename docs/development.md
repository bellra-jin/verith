# 공용 환경 참고와 실행 경계

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

소비자는 [공개 helper](../frontend/src/api/backend.ts),
[서버 URL/SSR](../frontend/src/lib/session-backend.ts), [BFF](../frontend/src/lib/session-proxy.ts)다.

| 변수 | 형식·비밀 여부 | 필수 조건·미설정/빈 값 동작 |
|---|---|---|
| NEXT_PUBLIC_API_URL | 공개 HTTP base URL, 비밀 금지. 참고 http://localhost:8200 | 비개인 helper만 사용. 미설정은 localhost:8200, 명시 빈 값은 `??` 때문에 그대로 남아 상대 경로가 될 수 있음 |
| BACKEND_URL | 서버 전용 HTTP(S) origin, 자격/query/path 금지. 참고 http://localhost:8200 | 개인 BFF/SSR에 명시 필요. 미설정/빈 값은 거부하며 공개 변수로 fallback하지 않음. 잘못된 URL 문자열은 URL 파싱 예외도 가능하므로 정상 종료를 보장하는 설정 검증으로 확대하지 않음 |

브라우저는 http://localhost:3200, 서버는 Backend 8200이다. 정본 local Backend 사용 시
Host/Origin/forwarded-host는 3200 계약을 유지한다. localhost와 127.0.0.1을 브라우저 인증에서
혼용하지 않는다. Google/DB 비밀은 Next나 NEXT_PUBLIC 변수에 넣지 않는다. 세션 전달·no-store·
원문 중복 Cookie·최종 Backend owner 검증을 유지하며 예제로 공개 save/직접 AI 경로를 열지 않는다.

## Backend 변수

[Settings/_load_settings](../backend/src/api/config.py)를 import하지 않고 읽었다. 기본 dotenv source는
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

인증 근거는 [Google 구성 검증](../backend/src/api/auth/google.py)과
[auth routes](../backend/src/api/routes/auth.py)다. 고정 Google discovery/최소 openid/PKCE·
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
| OPENAI_API_KEY | [Flow explain](../ai/src/agents/flow/nodes/explain.py), [Flow config](../ai/src/agents/flow/config.py) | SDK 사용 비밀. Flow 모델은 코드 INTERPRETER_MODEL에서 결정하며 OPENAI_MODEL 예제로 바뀌지 않음. dotenv 탐색 후 호출 가능, 키 누락 처리는 SDK/해당 경로에 의존 |
| KIS_API_KEY / KIS_API_SECRET / KIS_BASE_URL | [Flow KIS](../ai/src/agents/flow/core/kis_client.py), Technical loader | 비밀 2개/HTTP URL. Flow는 누락/빈 값, Technical은 strip 후 공백까지 거부. 두 loader 모두 dotenv 탐색 가능. 예제 endpoint는 .invalid placeholder이며 실제 연결/토큰 발급 안 함 |
| DART_API_KEY / DART_BASE_URL | Fundamental config, [Industry config](../ai/src/agents/industry/config.py) | 비밀/공개 URL. Fundamental은 빈 키/기존 공개 URL 기본. Industry get_dart_api_key는 호출 시 누락/빈 값 거부(strip 없음). Industry는 이 DART_BASE_URL 변수를 읽지 않음 |
| VERITH_DB_URL | Fundamental config·[corp_code](../ai/src/agents/fundamental/data/corp_code.py) | 선택 비밀 DSN, 기본 빈 값. `AliasChoices("VERITH_DB_URL", "DATABASE_URL")` 순서로 앱 자격을 받을 위험. psycopg는 `postgresql://...` 안내; 기존 asyncpg 접두 정규화 호환도 유지 |
| QWEN_API_KEY / QWEN_BASE_URL | Fundamental config, News config | **endpoint URL, API 비밀키 아님**. Fundamental은 QWEN_API_KEY가 첫 alias, QWEN_BASE_URL이 둘째; 첫 값이 명시 빈 값이어도 둘째로 넘어간다고 보장하지 않음. 미설정은 기존 별도 모델 주소, 빈 문자열은 보존. News는 QWEN_API_KEY만 읽고 누락/빈 값/공백이면 기존 localhost 추론 주소로 fallback |
| QWEN_MODEL / LLM_DUMMY_KEY | Fundamental config·[LLM client](../ai/src/agents/fundamental/interpret/llm_client.py) | 모델명/SDK key 필드. 기존 코드 기본값 존재, 명시 빈 값은 그대로. 예제는 승인 대상 placeholder, 기본 무인증 endpoint의 dummy를 유효 서비스 인증으로 간주하지 않음 |
| LLM_BASE_URL / LLM_MODEL / LLM_API_KEY | Industry get_chat_llm | URL/모델명/비밀. 미설정이면 기존 별도 endpoint/모델/dummy 기본, 명시 빈 값은 그대로 전달. 예제 .invalid/빈 키는 전체 호출 차단 장치 아님 |
| EMBED_MODEL | Industry get_embeddings | 모델 식별자, 비밀 아님. 미설정이면 기존 기본, 명시 빈 값도 모델 loader에 전달. News의 EMBED_MODEL 상수는 이 env를 읽지 않음. News FinBERT/embedding과 Industry 모델 로딩·다운로드 가능 |
| NEO4J_URI / NEO4J_USERNAME / NEO4J_PASSWORD | Industry get_neo4j_graph | Bolt URI/사용자/비밀. 호출 시 누락/빈 값 거부(strip 없음). Backend NEO4J_USER와 다름. 실제 권한·Cypher 접근 미검증 |
| REDIS_URL | [Technical cache factory](../ai/src/agents/technical/services/cache_service.py) | 선택 연결 URL/자격 포함 시 비밀. 미설정/빈 값·dependency/연결 오류는 cache 생략 경로. 기본 Supervisor cache=None. 공백은 명시 차단 보장 아님 |

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

## 이번 정적 검사와 후속

새 YAML bytes만 기존 PyYAML SafeLoader 계열로 비확장 파싱하고 중복 key/unsafe tag/예상 밖 구조를
거부한다. `${...}`는 문자열로 유지하며 parent env를 대입하지 않는다. env 예제는 명시 새 stream만
중복/문법/다중행을 거부하는 비실행·비보간 parser로 읽는다. source/exec·자동 dotenv 탐색을 하지 않는다.
검사 결과/명령은 [3-A 기록](work/ST-001-stage-3-A.md)에 둔다. `docker compose config`도 호출하지 않는다.

기능/unit/build/lint·새 설치·앱 import·Docker up/build/pull/config·migration/seed·DB/Google/AI·
모델 다운로드는 미실행이다. 기존 전체 lint 실패와 실제 인증 미검증은 [검증 상태](documentation.md#검증-상태와-이력)에
보존한다. private override/권한/실제 포트·namespace는 미확인이다. 3-A 검토/사용자 병합 후 최신 develop에서
3-B Backend/Frontend 수집 전 안전 entry → 3-C AI 안전 entry를 각각 구현한다. 둘 다 아직 미구현이며
큰 파일 분리/구조 재배치는 비교 판단 전 보류한다.
