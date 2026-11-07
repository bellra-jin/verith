# CF-002 구현·검증 기록

> **현재 상태 주석 · ST-001 1단계 / 2026-11-07T18:52:34+09:00**
> 검토 head: `a5b60f2fd0b00efedae2c98a2004ede62470b094`. CF-002 구현은 사용자 commit
> `7a5853d5f8725f593f647b2b0e5898dba50254fd`로 [PR #2](https://github.com/bellra-jin/verith/pull/2)에
> 포함되어 develop에 병합됐다. PR 병합 시각 18:22:15 KST (`2026-11-07T09:22:15Z`, 전달된 원격 기록),
> 병합 commit은 위 head이며 이번 fetch/로컬 그래프로 포함을 재확인했다.
> 본문의 미커밋·PR 미생성·당시 대기/미실행 표현과 실행 명령은 **작성/실행 당시 이력**이다.
> 현재 미커밋 작업은 별도 `docs/document-authority`의 ST-001 문서 수정이며 CF-002 구현과 구분한다.
> 이 단계는 과거 기능 검사를 재실행하지 않았다. 자연 시간 만료·옛 cookie 재전송·A→B 교차 UI·
> 개별 실제 HTTP/BFF 직접 관측·B 상세 본문 명시 확인의 미검증과 전체 ESLint 기존 실패는 유지한다.
> [현재 문서 권위/검증 상태](../../docs/documentation.md).

2026-11-07 09:00 UTC 사용자 테스트 종료·자기 자원 제거 완료. **실제 Google A/B 사용자 로그인,
내부 owner 검사, A 목록/상세·B 목록·B→A 상세404·B2 본인 UI 삭제 후 A2건/B1건·B2 재접속404를
확인했다. 실제 시간 만료·옛 cookie 재전송·A→B 역방향 UI·개별 HTTP status 직접 관측은 미검증이다.
전체 lint에는 기준 HEAD와 동일한 technical.ts의 기존 오류2건이 남는다. CF-002 전체 완료·서비스
공개 준비 완료로 선언하지 않는다.**

마지막 환경은 **PTY77282**/localhost3200·Backend8200, resource CF-002-login-e71baf35469b였다.
08:59:53 UTC users2/identities2/sessions2/revoked0/active2/Flow3과 사용자 A2건/B1건·삭제B2 404를
확인하고 finish했다. exit0·자기 full CID/사본 제거, 별도 exact-CID 부재·기록 PID/포트 listener
부재를 확인했다. **현재 실행 중인 테스트 환경은 없다.**
이하 첫 PTY12079·로그인 전 상태는 시간별 이력이며 현재 환경으로 사용하지 않는다.

정본은 저장소 밖 `../../../지시서/CF-002_실제_인증과_Flow_소유권_경계.md` v0.6,
SHA-256 `00fb44149066602152002910b446004289de8b3eed1410b8f554dd873b5d32eb`.
v0.2의 전환 차단에서 v0.3의 내부 모델·migration·세션·owner 확정 계약을 구현하고,
v0.4의 Google 선택과 Google adapter 계약, v0.5의 로컬 포트/전환 계약을 적용했다. 운영 정본 두 개는 v1.2다.
기존 보고서의 ‘DB 환경/내부 모델 미승인’ 대기는 이후 승인·정본으로 해소됐다.

작업 브랜치 `feat/flow-auth-ownership`, 기준 develop/origin develop/HEAD
`d8d800b104822dfc72e1a7b0daecfa1ac45b9e43`. 착수 당시 깨끗한 작업 트리에서
develop 전환 → origin fetch → ff-only 갱신 → 새 브랜치 순서로 시작했다.
v0.3/v0.4 수신 뒤에는 같은 브랜치를 유지했다. 현재 변경은 미커밋·미스테이징이다.
commit/push/실제 PR/Ready/merge/deploy·기존 DB migration은 실행하지 않았다.

## 구현 계약과 영향

- `db/models/auth/models.py`, registry, `docs/schema.md`, 새 revision
  `c2001a7e0001`(부모 `b1e9d4a7c2f1`): auth_users/identities/sessions,
  case-sensitive UNIQUE(issuer,subject), SHA-256 digest BYTEA(32), 유한 만료/폐기 CHECK,
  RESTRICT user FK와 nullable Flow root owner FK 및 비유일 조회 인덱스.
  common owner/session은 기존 외부 UUID를 허용하는 논리 링크로 보존한다.
  legacy root owner NULL·payload·stock·ID를 변경하거나 사용자에게 자동 귀속하지 않는다.
  새 인증 행/소유권이 있으면 파괴적 downgrade를 거부한다.
- `services/auth_service.py`: 내부 검증 신원만 연결하며 사용자+신원의 savepoint/UNIQUE
  경쟁에서 패자 사용자도 rollback한다. 난수 32바이트 이상 bearer 원문은 저장하지 않는다.
  서버 세션의 만료/폐기/사용자 disabled를 매 요청 DB에서 확인한다. 기본 TTL 3600초,
  sliding 없음. cookie만 인증 자격으로 받고 UUID/임의 헤더/Google ID token을 대신 받지 않는다.
  CSRF는 세션에 결합한 synchronizer와 정확한 Origin을 함께 확인한다. 로그아웃은 처음부터
  세션 FOR UPDATE로 직렬화하고, 이미 폐기된 자격의 반복 요청은 401로 거부한다.
- `auth/google.py`, `routes/auth.py`, config: Authlib **1.6.10** + HTTPX, Google 고정
  discovery와 endpoint 대조, openid만, code+PKCE S256, 5분·최대 1024건 process-local
  state/nonce/verifier/browser 상관관계, 교환 전 원자적 일회 소비. RS256/JWKS, aud/azp,
  exp/iat/nbf/nonce/sub를 확인한 두 Google issuer 입력만 canonical issuer로 연결한다.
  교환 실패 자동 재시도/임의 URL 키 조회/UserInfo fallback 없음. 새 로그인 때 기존 앱
  세션을 폐기하고 새 세션을 같은 DB transaction에서 commit한 뒤 cookie를 반환한다.
  미설정은 로그인 503·보호 API 401로 닫는다. 토큰·비밀을 오류 본문에 반환하지 않는다.
- `flow_report_repository.py`, `flow_report_service.py`: root owner와 정확히 한 Flow
  index/동일 owner를 SQL로 확인한다. 목록·공통 목록·count·pagination·batch·상세·삭제에
  같은 적격 조건을 적용한다. 타인/legacy/없는 결과는 payload 복원 전에 404.
  신규 내부 저장은 유효 principal을 필수로 하고 root/index owner/session을 함께 기록한다.
  기존 ID를 덮어쓰거나 NULL owner를 채택하지 않는다. 삭제는 세션 공유 잠금 → 소유 root
  FOR UPDATE → projection 확인 → index/root(자식 CASCADE) 순서다. 저장/삭제 실패는 rollback.
  common 목록을 Technical 서비스의 무인가 reader로 제공하지 않는다. stocks는 삭제하지 않는다.
- `access_boundary.py`, main/deps/Flow·common route: 본인 Flow 목록/상세/개별 삭제와
  로그인/세션/로그아웃·health·종목 resolve만 허용한다. 공개 payload 저장·전체 삭제·
  다른 관점·관리/HTML/분석은 사용자 호출에서 403. CORS가 바깥에서 정상 preflight를 처리한다.
- Next auth/private BFF, server session helper, Home/Flow detail/session controls:
  브라우저는 같은 origin 경로를 쓰고 Backend가 최종 인증/owner를 확인한다. server-only
  `BACKEND_URL`이 없으면 fallback 없이 닫는다. owner/user/service 헤더를 전달하지 않으며
  cookie·Origin·CSRF만 필요한 경로에 전달한다. 개인 응답/SSR fetch는 private/no-store.
  본인 목록/상세/개별 삭제/로그아웃 UI를 연결하고 비Flow SSR는 준비 중으로 보낸다.
  SSR은 축약된 RequestCookies 대신 원문 Cookie를 전달해 Backend의 중복 거부와 통일한다.
  목록은 검증한 limit/offset과 이전/다음 링크를 제공하고, 삭제 뒤 해당 목록 페이지로 복귀하되
  빈 마지막 페이지는 남은 마지막 페이지(또는 offset 0)로 이동한다.
- 기존 Next 8개 저장/분석/HTML proxy와 Supervisor 호출 함수는 upstream 이전에 차단한다.
  로그인 여부와 관계없이 새 분석·저장·전체 삭제를 할 수 없다. 연구 화면의 데모 성공
  fallback과 자동 후속 호출을 제거했다. 기존 알고리즘·mock 원본은 보존했다.
- `db/session.py`, graph driver, seed 스크립트 3개: import 때 engine/driver를 만들지 않는다.
  News graph bootstrap은 ENABLE_NEWS_GRAPH 명시 opt-in이다. 테스트 수집 때문에 seed하지 않는다.

이전 무인증 시연·분석·타 관점·전체 삭제가 중단되는 의도된 동작 변경이다.
CF-001 v1 ID·수치·기간·검증 정보·추가 필드·JSON 타입/Unicode·한시 snapshot 계약은 유지한다.
새 AI/worker/게시 복구/늦은 결과 재게시·전용 snapshot/회원 탈퇴는 이번에 구현하지 않았다.

## DB 안전 경로와 두 검토 결함

기존 공통 conftest와 Flow 전용 conftest 모두 명시적 TEST_DATABASE_URL과
TEST_DATABASE_APPROVAL 없이는 engine/연결/DDL/DML 전에 setup error로 중단한다.
manifest는 자원 ID·주소·별도 역할·DB·실서버 포트·disposable·cleanup_owner를 명시한다.
앱 URL은 비교만 하며 접속하지 않는다. 같은 앱 서버/별칭·같은 사용자 자격·query/driver
대상 변경 옵션·모호한 percent encoding을 거부한다. asyncpg readonly preflight 후 engine을
만들고 실제 SQLAlchemy 연결도 readonly로 DB/user/server port/resource marker·비관리자
역할을 재대조한다. readonly transaction 종료 후 **동일 연결**을 Alembic config attributes와
run_sync로 전달한다. verified_test_mode에서 연결이 없으면 앱 settings 로딩 이전에 실패한다.

- P1: URI decoding/SQLAlchemy 대상 차이는 대상의 percent encoding과 query/fragment/control
  문자를 거부하고 정규화한 asyncpg URL 및 동일 explicit connect args를 사용하도록 수정했다.
  percent-encoded DB/user/host, query/driver 옵션, 실제 connect args/readonly 불일치를 spy로
  검사한다. 위험 DB로 연결해서 거부를 시험하지 않는다.
- P2: AccessBoundary/CORS 순서를 수정했다. 허용 origin의 종목 POST preflight·실제 요청은
  허용하고 미허용 origin preflight 및 보호 본 요청은 거부하는 메모리 ASGI 회귀를 통과했다.
- 직접 재실행: `tests/unit/test_cf002_review_regressions.py` **11 passed**.
  별도 검토 채팅도 06:06:21 UTC 변경본에 대해 네트워크 차단·대역/ASGI로 11개 통과와
  검사 전후 파일 해시 동일을 확인했다고 전달했다. 그 독립 결과는 P1/P2 두 수정에 한정한다.

## 최종 독립 검토의 P2 세 건 수정 (06:32 UTC)

1. 동시 logout: 기존 mutation 인증의 FOR SHARE → UPDATE 승격이 두 logout 사이에서
   deadlock을 만들 수 있었다. logout은 `exclusive_session_lock=True`로 최초 인증 SELECT부터
   FOR UPDATE를 획득한다. 일반 조회/Flow 삭제의 공유 잠금 정책·Origin/CSRF는 유지한다.
   정책은 폐기 한 번 commit/성공 200, 경쟁 패자·폐기 뒤 반복·옛 cookie 재사용 401이다.
   응답을 모두 200으로 만드는 멱등 로그인 자격 정책은 아니다. 실패 응답은 cookie를 지우지 않는다.
   `cf002_concurrency_check.py`는 별도 pre-attested 연결 두 개와 HTTPX ASGITransport를 통해
   실제 FastAPI logout route를 동시에 호출하고 인증 직후 overlap을 만들어 검증했다. 200+401, 추가 반복 2회 401,
   session 조회 401, DB revoked_at 존재를 확인했다. 기존 직접 revoke/delete 경쟁도 유지했다.
2. SSR 중복 Cookie: Next RequestCookies Map 축약 뒤 getAll 길이 확인으로는 중복 판정을 할 수
   없었다. `headers()`의 원문 Cookie를 Backend로 그대로 전달한다. 실제 Next HTTP에서
   expired→valid-B와 valid-B→expired 두 순서를 SSR/BFF 모두 거부하고 raw 값 보존을 확인했다.
   valid-B는 합성 HTTP fixture 자격이며 실제 Google/사용자 계정 검증이 아니다.
3. 목록 pagination: 기본 20개만 표시하던 Home에 검색 파라미터·이전/다음 링크를 추가했다.
   limit는 1..100 정수, offset는 덧셈 가능한 안전한 비음수 정수로 검사한다. 음수/NaN/배열·
   지나치게 큰 입력은 각각 20/0 기본값으로 처리한다. 기존 owner SQL·count·no-store를 유지한다.
   합성 25개에서 21~25번째 접근, 빈 목록·마지막 페이지·마지막 항목 삭제 후 유효 페이지 복귀를
   실제 로컬 Next HTTP로 검증했다. 상세/삭제 복귀 URL은 검증한 숫자로 서버에서 구성한다.

추가 회귀는 Backend unit 2건과 실제 동시 logout HTTP, Frontend BFF 중복 순서 검사와
`tests/session-http.test.mjs`다. 위 검사들을 기존 단위 통과로 대체하지 않았다.

## 직접 실행한 검사

| 검사 | 최종 확인 결과 | 해석 |
|---|---|---|
| Backend unit | **343 passed** | CF-001 포함, 실제 네트워크 금지. Google 서명 합성·세션/잠금·local port/callback/CORS/Host·private controller 회귀 포함 |
| PostgreSQL integration (v0.4 회차, 포트 패치에서 미재실행) | **54 passed** | 실제 SQLAlchemy/서비스/FastAPI와 일회용 PG. 합성 내부 A/B 및 signed fake Google HTTPX로만 인증 준비 |
| 공통 seed fixture (v0.4 회차) | **3 passed** | 같은 사전 검증된 대상, outer rollback |
| 별도 committed PG 경쟁 검사 (v0.4 회차) | 통과 | 신원 경쟁 패자 rollback/사용자 1명; 세션 공유 잠금과 폐기 UPDATE 직렬화; 폐기 commit 후 재사용 거부 |
| Migration (v0.4 회차) | 통과 | fresh head·metadata check, 이전 head+legacy 확장 보존, auth 데이터 downgrade 거부, 빈 새 데이터 downgrade/reupgrade, metadata 차이 없음 |
| 기존 보관함 카드 | **4 passed, 3 deselected** | 카드 projection만 |
| Frontend handler/BFF | **15 passed** | 구 proxy 8개 차단·Supervisor upstream 0·허용 BFF/cookie/CSRF 전달·위조 owner 누락 |
| 실제 로컬 Next HTTP | **3 passed** | 구 proxy 40 HTTP·research/SSR 차단과 원문 중복 cookie 두 순서·25건 pagination·마지막 페이지 삭제 복귀. 합성 HTTP backend만 사용 |
| Frontend type/build/대상 ESLint | 통과 | Next 16.2.10, TypeScript; 실제 Google·DB와 브라우저 통합 아님 |
| 전체 Frontend ESLint (최종 별도 실행) | **실패: 2 errors·3 warnings** | 기준 HEAD와 동일한 technical.ts:191/207의 explicit-any 오류2건, 기존 unused 경고3건. 대상24파일 ESLint 통과와 구분 |
| 대상 Backend Ruff/format·git diff --check | 통과 | 별도 Backend static type checker는 저장소에 구성되지 않음 |

초기 적용 도중 fixture의 옛 owner=None 기대·principal 누락, 합성 요청 question 누락,
proxy 테스트의 구 SSR 기대, unused import 등을 수정하고 재실행했다. 미해결 assertion 실패는 없다.
로컬 sandbox에서 Docker socket/Next Turbopack 내부 포트 바인딩 제한은 승인된 일회용/로컬
검증 실행 권한으로 재실행해 통과했다. 외부 Google·실제 AI·앱 DB로 우회하지 않았다.

최종 일회용 DB 실행: `CF-002-ed8277697505`, container
`f1e4f24662790c2c7ac8f50ce02010d0280862fb2e3b9852d5a5cee49fc4cdbb`,
127.0.0.1:59869, DB `cf002_db_ed8277697505`, limited role `cf002_role_ed8277697505`.
앱과 다른 주소/자격, label/실서버 resource GUC·cleanup_owner 일치 확인. 캐시된
`pgvector/pgvector:pg16`을 pull 없이 사용했다. read-only container + tmpfs만 사용하며
persistent mount/volume 0, 제한 역할은 NOSUPERUSER/NOCREATEDB/NOCREATEROLE/NOINHERIT/
NOREPLICATION/NOBYPASSRLS다. bootstrap admin은 새 컨테이너 안의 제한 역할/extension 준비만
맡고 preflight 뒤 migration/tests는 제한 역할로 실행했다. 비밀은 메모리 env에만 두고 출력/
.env 저장하지 않았다. 기존 `verith-postgres`/볼륨·사용자 데이터는 변경하지 않았다.

종료 전 stocks/root/interpretation/verification/index/auth_users/auth_identities/auth_sessions
잔여 건수 **모두 0**, 이번 자원만 stop/--rm 후 inspect 부재를 확인했다. 정리 책임은
`CF-002 delegated disposable test runner`. 앞선 실패 회차도 finally에서 각 임시 자원을 정리했다.

재현(Backend 루트, 사전 승인된 별도 일회용 환경을 생성/정리하는 마지막 명령에 유의):

```sh
.venv/bin/python -m pytest --confcutdir=tests/unit tests/unit -q
.venv/bin/python -m pytest --noconftest tests/test_report_archive.py -k test_archive_card -q
.venv/bin/python scripts/check_cf002_database.py --approved-disposable
```

Frontend v0.5 검증은 기존 private env 자동 로딩을 피하도록 새 env-free 사본에서 수행한다.
기존 Frontend 디렉터리에서 직접 dev/build를 실행하지 않는다.

```sh
node frontend/scripts/check-local-ports.mjs  # 저장소 루트; 새 사본/합성 프로세스만 정리
```

## 실제 Google 연결의 정확한 차단과 필요한 작업

Google **선택은 완료**됐다. baseline tracked Backend/Frontend 코드와 현재 Backend/Frontend
.env 및 프로세스 환경의 설정 이름만 읽기 확인했고 Google/OIDC client 구성은 찾지 못했다.
Google Console·개인 계정·프로젝트에 로그인하거나 설정/자격증명을 생성·주입하지 않았다.
parent 전달로 Google 프로젝트 verith-dev 생성 사실을 받았으나 개발 채팅은 Console을 조회/변경하지 않았다.
Web client/secret 주입은 여전히 승인 대기다. 따라서 외부 Google 실제 A/B 로그인·callback·cookie 브라우저 동작·SSO 재접속·실제 만료/
폐기/로그아웃 후 Backend/BFF/SSR 재사용 통합은 **미실행**이며 최종 수용을 보류한다.

설정 담당자와 다음 대상별 결정/승인이 필요하다.

1. 사용할 기존 Google Cloud 프로젝트와 그 설정 권한을 확인한다. 재사용 대상이 없으면
   새 프로젝트 생성 여부/소유자부터 승인한다. 임의 생성·billing/유료 설정을 하지 않는다.
2. 사용할 앱 origin·Backend 주소·Google 등록용 **전체** callback URI
   로컬 `http://localhost:3200/api/auth/callback`과 origin `http://localhost:3200`은 v0.5에서 확정됐다.
   배포 도메인은 별도 확인하며, 코드/문서 확정이 Google Console 실제 등록을 뜻하지 않는다.
3. 해당 프로젝트의 OAuth consent/audience와 실제 서로 다른 A/B 계정의 테스트 사용을
   승인하고 필요한 test users를 설정한다. 이번 scope는 openid만이다.
4. 해당 프로젝트의 **Web application** OAuth client 생성/재사용 및 정확한 redirect 등록을
   승인한다. ID/secret은 서버 전용 안전한 전달 경로로 담당자가 주입한다. 채팅/문서·Next public
   변수에 secret을 넣지 않는다. 코드가 기대하는 이름은 GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET,
   AUTH_REDIRECT_URI/AUTH_ORIGINS, Next 서버 BACKEND_URL이다. 로컬 HTTP가 실제 승인된
   loopback이면 AUTH_ALLOW_LOCAL_HTTP만 명시한다(기본 false). 현재 실제 값을 설정하지 않았다.
5. 승인된 실제 A/B 계정과 일회용 DB로 로그인부터 목록/count/detail/delete·logout·만료/폐기·
   직접 Backend/BFF/SSR·이전 우회까지 최종 통합한다. 새 비용·지속 권한이 생기면 먼저 보고한다.

Pending login state는 단일 프로세스 메모리다. 재시작/다른 프로세스 callback은 실패하며
다중 인증 프로세스 지원을 주장하지 않는다. Google endpoint 변경 시 현재 정확 대조는 닫히므로
정본과 metadata를 다시 확인해야 한다. Next dev callback access log는 제외했고 Backend ASGI
callback query도 제거한다. 실제 배포 proxy/호스팅 access log의 callback query·cookie redaction과
HTTPS/cookie 설정은 실제 환경 단계의 필수 점검이다. 운영 트래픽·실제 로그인 브라우저·외부 AI
포트 노출/서비스 공개 안전성은 이번 로컬 결과로 검증하지 않았다.


## v0.5 포트 패치·검증 (07:02 UTC)

정본 v0.5 SHA-256 `b6dd272ef4a31f9f68640ef87fc8be55a7412aad01ead894fd0ad1f2265ac5ad`와
4-6절 전체를 읽고 같은 feat/flow-auth-ownership / d8d800b10482에서 기존 변경을 보존하며 적용했다.

| 접점 | 변경/유지 |
|---|---|
| Frontend dev/start | 3200; 공개 비개인 API 기본 localhost:8200 |
| Next private 서버 주소 | BACKEND_URL 명시 유지. 누락 503·upstream 0, NEXT_PUBLIC fallback 없음 |
| 로컬 Google | localhost:3200 origin + /api/auth/callback. code 교환도 외부3200 URI 유지 |
| Backend·AI | 실행 안내 8200·9200. AI→Backend 기본과 news/supervisor lab Backend 용도8001을 localhost:8200으로 수정 |
| Compose host mappings | 15432:5432, 16379:6379, 17474:7474, 17687:7687만 변경 |
| Graph export | host fallback bolt://localhost:17687; 실제 export 미실행 |
| 직접 PG/Bolt/cache | Fundamental driver 규약을 보존한 host PG15432, Industry Bolt17687, Technical optional Redis16379 안내. 새 기본 연결/자동 cache 활성화 없음 |

정적 PyYAML safe_load로 전/후 ports 노드와 ports를 제거한 전체 구조를 **메모리에서** 대조했다.
비포트 구조 동일=true를 확인한 뒤 host 문자열 네 곳만 저장했다. environment/credentials·volume·
컨테이너/서비스명·내부 포트·network bind는 동일하며 전체 YAML/환경값을 출력하지 않았다.
`docker compose config`나 Docker Env/inspect는 실행하지 않았다. Docker-compose.yml은 기존
.gitignore 312행의 ignore 대상이라 **로컬 파일은 수정됐지만 Git 공유 대상에는 아직 없다**.
임의 force-add/.gitignore 변경이나 비밀 포함 파일 공개는 하지 않았다. 공유 방법은 별도 검토 대상이다.

사전 비포트 지문을 파일/외부 로그에 따로 저장하지는 않았다. 위 동일성 근거는 **최초 패치 실행**에서
원문을 읽은 직후 보관한 메모리 객체와 저장 전 변경 객체를 비교한 실행 로그다. 새 현재 파일을
옛 기준이라고 간주해 비교/해시한 결과가 아니다. 당시 절차는 다음과 같았고 출력은 아래 boolean과
서비스별 port 목록뿐이었다(환경값/전체 파일 없음).

```python
raw = path.read_text()
# Each old quoted host:container literal must occur exactly once (4 exact replacements).
updated = replace_four_port_literals(raw)
before, after = yaml.safe_load(raw), yaml.safe_load(updated)
left, right = deepcopy(before), deepcopy(after)
for document in (left, right):
    for service in document["services"].values():
        service.pop("ports", None)
assert left == right
path.write_text(updated)  # only after the assertion
# observed output: non_port_structure_preserved = true
```

사전 원본/지문을 별도로 보존하지 않아 현재 독립 검토자가 HEAD와 대조해 이를 재현할 수 없는
한계는 남는다. 수행한 최소 패치는 quoted `5433:5432`→`15432:5432`, `6379:6379`→`16379:6379`,
`7474:7474`→`17474:7474`, `7687:7687`→`17687:7687` 네 문자열 교체다.
추후 검토를 위해 사전 지문이 있는 것처럼 만들거나 환경값을 공개하지 않았다.


Backend 단위 **244 통과**, v0.5 local callback/CORS/Host·정적 기본값 7건 포함이다.
실제 네트워크 없는 signed MockTransport에서 redirect_uri3200 code 교환을 확인했다.
CORS 허용3200 성공, 3000/3201/127.0.0.1 alias 거부, cookie Path/HttpOnly·명시적 로컬 Secure 예외,
Origin/CSRF·개인 no-store 및 로컬 Backend Host8200/X-Forwarded-Host 주입 거부를 확인했다.
AUTH_* 미설정·HTTPS 정책은 유지한다. 로컬 HTTP 예외만 localhost:3200으로 제한한다.

Frontend는 private .env를 읽는 Next 자동 로딩을 피하려고 **새 .cf002-port-check-* 사본**을
만들었다. src/public/tests와 명시한 비밀 없는 프로젝트 설정만 복사하고 .env*는 복사하지 않았으며
app 환경값을 상속하지 않았다. node_modules는 기존 설치를 재사용했다. 이 사본에서 handler/config
**15**, 실제 로컬 HTTP **3**, production build·type·대상 ESLint가 통과했다.
3200 Next +8200 합성 Backend로 callback 전달·외부3200 redirect·cookie/no-store와 잘못된 Host/
Origin/alias 거부·금지 분석/save upstream0을 확인했다. SSR도 정본 로컬 Host가 아니면 private
Backend 조회를 시작하지 않는다. 기존 중복 Cookie·25건 pagination 회귀도 유지했다.
Host 주입 검사는 fetch가 Host를 재작성할 수 있어 node:http의 실제 wire 요청으로 검사했다.
해당 사본/자체 프로세스·대역은 성공/실패 회차 모두 정리했다. 기존 프로젝트/다른 앱은 중단하지 않았다.
Backend 단위는 DotEnvSettingsSource와 fixture dotenv_values를 대체해 private 환경 파일을 읽지 않았다.
AI/graph/현재 docstring 관련 변경 Python 12파일은 import/실연결 없이 AST 문법 검증을 통과했다.

추가 독립 검토에서 확정 P1/P2 포트 결함은 없고 Frontend 단위15/Backend 포트 회귀7이
직접 통과했다는 전달을 받았다. 마지막 P3 안내는 Frontend VITE/8000을 Next 공개8200 예시로,
seed 두 파일의 PG 전제15432·supervisor smoke/설정/news HTTP client의 현재 Backend 설명8200으로
정정했다. 해당 seed/smoke/client는 실행하지 않았고 소스 AST 문법만 확인했다.

### 남은 포트 검색 분류

- 변경: 현재 launch/공개 기본/CORS·Google local fixture/AI Backend resolver·lab/graph export·host mapping.
- 유지: Compose 내부 5432/6379/7474/7687·서비스명, News 추론 localhost:8001/v1,
  Fundamental 외부 모델 pbd.mtvs2026.work:8000/v1, technical 3000 token/090000 시각 등 수치.
- 유지: app.unit/HTTPS 합성 origin, in-memory 127.0.0.1:1, DB 안전장치 대역6543·5432,
  HTTP spy/테스트 Docker의 ephemeral 포트. 실제 브라우저 설정으로 승격하지 않았다.
- 과거 기록: db_boundaries의 예전5433/8000 및 과거 검증 자원/지시서 task/eval 기록은 현재 가이드와
  구분해 보존했다. backend README의 과거 ‘경고 후 같은 서버 test DB’ 준비 명령은 현 fail-closed
  절차와 충돌하므로 현재 검사 안내로 교체했다. 3000은 거부 사례로만 남는다.

이번 포트 회차에서는 **DB/migration/seed·실제 AI·Google 호출을 실행하지 않았다**.
표의 실DB54/seed3·신원 경쟁/동시 logout·migration은 이전 v0.4 회차의 근거다.
기존 .env/credentials/Docker Env·기존 컨테이너/volume/데이터는 조회·수정/재시작하지 않았다.
실행 전 후보 포트 미점유를 재확인했고 기존 점유 프로세스를 종료하지 않았다.
기존 컨테이너는 이전 PortBindings를 계속 가질 수 있으므로 실제 전환은 대상·연결 단절 영향·
private override 일치·새 점유 확인 뒤 별도 승인해야 한다. 현재 private override는 **미확인**이다.
Google client/secret/Console callback 등록과 실제 A/B 로그인도 **미실행/미검증**이다.
[전체 비밀 없는 포트 안내](../../docs/local_ports.md)에 설정 항목과 역할별 driver를 기록했다.

## v0.6 interactive 실행·현재 대기

v0.6 정본의 새 소유 자원 증명 경로를 구현·검증했다. 일반 app URL guard는 유지하고 사용자의
기존 앱 DB 정보를 추가로 묻거나 .env의 DATABASE_URL을 가져오지 않았다. 선택 reader/copy/
cleanup·권한·exec/DTO·PID/PGID/listener/nonce·watchdog와 runtime readonly guard의 독립 결함을
수정·회귀한 뒤 새 실DB/fake 앱·부분 startup/실제 SIGTERM 정리를 확인했다.

첫 **승인된 실제 입력 모드 대기 환경**은 localhost3200/Backend8200, resource
CF-002-login-1b00c9c0873f (CID2192080fed68585be25db013bfbe7466313a25bd08ef78706fd59b509404ea73,
loopback DB61631, mount0)이다. Backend bootstrap만 실제 Google 두 키를 읽었으며 값은
assistant/parent runner/Next/인자/로그에 노출하지 않았다. 최대3600초 수명·parent EOF watchdog을
유지한다. 사용자가 첫 Google 로그인 성공을 보고한 뒤08:16:56 UTC status에서 users1/sessions1/
active1/revoked0/Flow0을 직접 확인했다. 첫 로그인은 사용자 보고+실제 DB 세션 생성 근거이며
개별 callback HTTP/외부 신원·cookie를 직접 수집하지 않았다. 사용자 직접 로그아웃/UI 복귀 보고
직후08:18:29 UTC status는 users1/sessions1/revoked1/active0/Flow0으로 서버 폐기를 확인했다.
실제 서로 다른 B·브라우저 owner·시간 만료·옛 cookie 재사용 검증은 아직 미실행이다.
이 회차는 전체 .env source나 기존 DB/container/volume·AI·Console
실행이 아니다. 현재 인스턴스의 status/finish 한계와 전환 절차는 아래 검증 기록에 구분했다.

로그아웃·active0을 재확인한 뒤 parent 지시로 첫 환경을 finish/exit0 정리했다. 새 controller
포함 환경은 resource CF-002-login-e71baf35469b/CID8c5fb2fd7820b3fd987a70a516d57313e6b3441cbba4475221e750f6015568d4,
DB loopback62235/mount0, PTY77282로08:21 UTC readiness 통과했다. URL은 같은 localhost3200이며
새 status의 users/identities/sessions/active/revoked/Flow는 모두0이다. 사용자의 A 재로그인·다른
실제 B 로그인을 기다리며 자동 계정 조작은 없다. 수명 종료는09:20~09:21 UTC다.

그 뒤 사용자 A 재로그인 보고에 따라08:26 UTC status의 users1/identities1/sessions1/active1을
확인하고 private bind-A/seed-A로 합성2건을 준비했다. A와 두 결과는 현재 유지 중이다.
실제 A 브라우저의 목록/상세 확인, 다른 실제 B와 타인 접근 차단은 아직 미검증이며 두 결과를
B 검사 전 삭제하지 않는다. 합성 ID·화면 확인 절차는 검증 기록에 구분했다.

이후 사용자가 A 목록2건과 상세 열기를 확인했다. 실제 UI 사용자 확인 범위로만 기록하며
개별 HTTP status·BFF/SSR 각 응답·옛 cookie 거부의 직접 관측은 아니다.08:39 UTC active1/Flow2를
유지하며 다른 실제 B 수동 로그인 보고를 기다린다. B 내부 명령/삭제/전환은 실행하지 않았다.

08:47 UTC에는 사용자 B의 별도 시크릿 로그인·본인0건 보고 후 users2/identities2/active2를
확인했다. canonical Google/활성 session/서로 다른 user 검증의 bind-B와 seed-B2건,
내부 check-owner가 통과했다. 실제 DB/service에서 A/B 본인 목록/count·페이지·상세 성공,
타인 목록0/상세없음/삭제false를 확인했고 최종Flow4건으로 A/B 결과를 보존했다. B 브라우저의
본인2건·A 링크 거부와 개별 HTTP/BFF status·옛 cookie 재사용은 아직 미검증이다.

이후 B 시크릿에서 A1의404 화면을 사용자가 확인했다. 실제 교차 상세 거부의 사용자 확인이며
B 본인2건/본인 상세·A→B 반대 방향·현재 환경 본인 웹 삭제는 아직 회신 전이다.
08:52 UTC active2/Flow4를 유지했다. 세션TTL3600은 현 런타임 수명보다 늦게 끝나므로 실제
시간 만료는 이번 인스턴스에서 검사하지 못하며, 옛 cookie 재사용도 미검증이다.

현재 Backend unit343 통과. 새 owned DB 실제 session/Flow 경로, 최종 fake 환경의 runtime
제한역할 쓰기/rollback·normal/실패/signal 정리는 **이번 v0.6 직접 실행 근거**다.
이전 v0.4의 54/seed3과 구분한다. 실제 A/B 통과는 아직 주장하지 않는다.
[정확한 명령·실행 영수증·수명·종료·검증 기록](google_login_check.md)을 따른다.

## 사용자 실행용 초안

권장 commit: `feat(auth): enforce Google sessions and Flow ownership boundaries`

Draft PR 제목: `CF-002: Google OIDC 세션과 Flow 소유권 경계 구현`

Draft PR 본문:

> 기존 무인증 리포트/직접 AI proxy 접근을 닫고 Google code+PKCE와 PostgreSQL 폐기 세션,
> Flow root owner 및 정확히 한 index를 검증하는 본인 목록/count/detail/개별 삭제를 추가합니다.
> 기존 payload·legacy owner NULL·common 외부 UUID를 보존하는 확장 migration과 모든 DB
> 테스트의 fail-closed preflight/동일 검증 연결 migration 경로를 포함합니다.
>
> 검증: 현재 Backend unit 343, Frontend handler/BFF 15·로컬 HTTP 3·env-free type/build/lint 통과.
> 이전 v0.4 회차의 실제 일회용 PostgreSQL 54 + seed 3, committed identity race와
> revoke/delete·동시 실제 logout 잠금 순서, fresh/legacy migration·downgrade guard·metadata check, 카드 4(이전 회차),
> 격리 자원 잔여 0·제거 확인. DB/migration은 포트 패치 회차에서 재실행하지 않았습니다.
> P1 대상 해석 및 P2 CORS 회귀 11건 통과(별도 독립 재검토도 통과 전달).
>
> v0.6의 직접 생성 영수증/제한 역할·이중 readonly/same-connection migration과 env-free
> exec 앱·유한 수명·자기 자원 정리를 실제 새 일회용 PostgreSQL에서 검증했습니다.
> Backend-only Google 두 키 선택 사용은 이번 로컬 테스트에 승인됐고 사용자가 실제 A/B 로그인,
> A 목록2건/상세, B seed 전0건과 A 상세404를 확인했습니다. 별도 실제 Google 두 계정의
> DB/service 검사에서 본인 목록/count/페이지/상세·타인 조회/삭제 차단이 통과했습니다.
> 첫 환경의 사용자 로그아웃+DB revoked1/active0도 확인했고 이후 B 본인2건 목록도 확인했습니다.
> B2 본인 UI 삭제와 B 목록1건 사용자 보고 후 DB 총Flow4→3을 확인했습니다. A2건 보존 재확인·
> 삭제B2 재접속404도 사용자 확인했습니다. B 상세 본문 명시 확인·역방향404·실제 시간 만료·
> 옛 cookie 재사용과 개별 HTTP/BFF 관측은 아직 미검증입니다.
> 실제 Google 사용자 확인, 내부 서비스 검사, 합성-only/오프라인 검사를 구분합니다.
> 두 번째 대화형 환경은 finish/exit0·자기 child/정확한 CID/사본 제거를 확인했습니다.
> 전체 ESLint는 기존 technical.ts any2건에서 실패하며 CF-002 대상 lint와 구분합니다. 새 분석·AI·worker·게시 복구는
> 제외하며 단일 프로세스 login state 한계와 미설정 차단 정책을 유지합니다. 최종 수용 전 Draft입니다.


## 변경 파일 목록

- `README.md`
- `ai/src/agents/fundamental/README.md`
- `ai/src/agents/fundamental/README/06_DEV_GUIDE.md`
- `ai/src/agents/industry/config.py`
- `ai/src/agents/news/CLAUDE.md`
- `ai/src/agents/news/README.md`
- `ai/src/agents/news/config.py`
- `ai/src/agents/news/demo_pipeline_app.py`
- `ai/src/agents/news/services/backend/__init__.py`
- `ai/src/agents/news/services/backend/client.py`
- `ai/src/agents/technical/README.md`
- `ai/src/agents/technical/docs/config.md`
- `ai/src/supervisor/README.md`
- `ai/src/supervisor/config.py`
- `ai/src/supervisor/devtools/streamlit_supervisor_news_lab.py`
- `ai/src/supervisor/scripts/smoke_supervisor.py`
- `backend/README.md`
- `backend/db/graph/driver.py`
- `backend/db/migrations/env.py`
- `backend/db/migrations/versions/20261107_c2001a7e0001_auth_and_flow_owner.py`
- `backend/db/models/auth/__init__.py`
- `backend/db/models/auth/models.py`
- `backend/db/models/common/agent_report.py`
- `backend/db/models/flow/flow_report.py`
- `backend/db/models/registry.py`
- `backend/db/session.py`
- `backend/docs/cf002_commit_pr.md`
- `backend/docs/cf002_pr_body.md`
- `backend/docs/db_boundaries.md`
- `backend/docs/flow_auth_ownership.md`
- `backend/docs/google_login_check.md`
- `backend/docs/migrations.md`
- `backend/docs/schema.md`
- `backend/pyproject.toml`
- `backend/scripts/cf002_concurrency_check.py`
- `backend/scripts/cf002_controller_check.py`
- `backend/scripts/cf002_interactive_login.py`
- `backend/scripts/cf002_migration_check.py`
- `backend/scripts/check_cf002_database.py`
- `backend/scripts/export_industry_graph.py`
- `backend/scripts/export_news_graph.py`
- `backend/scripts/google_login_bootstrap.py`
- `backend/scripts/google_login_controller.py`
- `backend/scripts/google_login_inputs.py`
- `backend/scripts/google_login_workspace.py`
- `backend/scripts/runner_owned_database.py`
- `backend/scripts/seed_representative_stocks.py`
- `backend/scripts/seed_stock_aliases.py`
- `backend/scripts/seed_stocks.py`
- `backend/src/api/access_boundary.py`
- `backend/src/api/auth/__init__.py`
- `backend/src/api/auth/google.py`
- `backend/src/api/config.py`
- `backend/src/api/main.py`
- `backend/src/api/repositories/flow_report_repository.py`
- `backend/src/api/routes/auth.py`
- `backend/src/api/routes/flow_reports.py`
- `backend/src/api/routes/reports.py`
- `backend/src/api/services/auth_service.py`
- `backend/src/api/services/flow_report_service.py`
- `backend/src/api/services/technical_report_service.py`
- `backend/tests/conftest.py`
- `backend/tests/db_safety.py`
- `backend/tests/flow_integration/conftest.py`
- `backend/tests/flow_integration/test_cf002_auth_ownership.py`
- `backend/tests/flow_integration/test_cf002_preflight.py`
- `backend/tests/flow_integration/test_flow_persistence.py`
- `backend/tests/unit/conftest.py`
- `backend/tests/unit/test_cf002_boundary.py`
- `backend/tests/unit/test_cf002_google.py`
- `backend/tests/unit/test_cf002_local_ports.py`
- `backend/tests/unit/test_cf002_review_regressions.py`
- `backend/tests/unit/test_cf002_session_failures.py`
- `backend/tests/unit/test_flow_contract.py`
- `backend/tests/unit/test_google_login_controller.py`
- `backend/tests/unit/test_google_login_inputs.py`
- `backend/tests/unit/test_google_login_workspace.py`
- `backend/tests/unit/test_interactive_runner_security.py`
- `backend/tests/unit/test_runner_owned_database.py`
- `backend/uv.lock`
- `docs/local_ports.md`
- `frontend/README.md`
- `frontend/docs/frontend_coding_guidelines.md`
- `frontend/next.config.ts`
- `frontend/package.json`
- `frontend/scripts/check-local-ports.mjs`
- `frontend/src/api/backend.ts`
- `frontend/src/api/flow.ts`
- `frontend/src/api/supervisor.ts`
- `frontend/src/app/api/auth/[action]/route.ts`
- `frontend/src/app/api/flow/reports/route.ts`
- `frontend/src/app/api/fundamental/reports/[reportId]/html/route.ts`
- `frontend/src/app/api/fundamental/reports/route.ts`
- `frontend/src/app/api/industry/reports/[reportId]/html/route.ts`
- `frontend/src/app/api/industry/reports/route.ts`
- `frontend/src/app/api/news/reports/route.ts`
- `frontend/src/app/api/private/[...path]/route.ts`
- `frontend/src/app/api/supervisor/analyze/route.ts`
- `frontend/src/app/api/technical/reports/route.ts`
- `frontend/src/app/page.tsx`
- `frontend/src/app/reports/flow/[reportId]/page.tsx`
- `frontend/src/app/research/page.tsx`
- `frontend/src/app/unavailable/page.tsx`
- `frontend/src/features/flow/components/session-controls.tsx`
- `frontend/src/lib/archive-pagination.ts`
- `frontend/src/lib/disabled-feature.ts`
- `frontend/src/lib/session-backend.ts`
- `frontend/src/lib/session-proxy.ts`
- `frontend/src/proxy.ts`
- `frontend/tests/disabled-http.test.mjs`
- `frontend/tests/disabled-routes.test.mjs`
- `frontend/tests/ports-http.test.mjs`
- `frontend/tests/ports.test.mjs`
- `frontend/tests/session-http.test.mjs`
- `frontend/tests/session-proxy.test.mjs`

별도 ignore 대상 로컬 변경: `Docker-compose.yml` (host mapping 네 곳만 변경, 미추적/미스테이징).
