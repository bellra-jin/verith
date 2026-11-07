# CF-002 v0.6 실제 Google 로그인·A/B 검증 기록

정본 SHA-256 `00fb44149066602152002910b446004289de8b3eed1410b8f554dd873b5d32eb`의 4-7절을 적용했다.
사용자가 backend/.env에 직접 저장한 Google 두 키를 이번 일회용 로컬 Backend가 사용하는
per-action 승인 원문을 받았고, 같은 승인을 다시 묻지 않았다. 계정 선택·로그인/MFA/동의는
사용자가 직접 한다. 다른 실행/환경·Console 변경·새 credential 생성 승인이 아니다.

## 현재 실행 상태

**2026-11-07 09:00 UTC 테스트 종료·실제 제거 완료. 현재 실행 중인 앱/PTY는 없다.**
마지막 status는 users2/identities2/sessions2/revoked0/active2/Flow3이었다. 사용자 확인의
A2건·B1건·삭제B2 재접속404와 총3건이 일치했다. 개별 owner별 DB 잔여를 조회한 결과는 아니다.
PTY77282의 `finish` 후 runner exit0·자기 DB/사본 제거를 확인했고, 정확한 전체 CID의 명시적
부재와 사본 경로 부재를 별도 재확인했다. Backend/Next 기록 PID63732/63734와3200/8200
listener도 남아 있지 않았다. 아래 주소·수명·PID는 종료된 환경의 영수증이며 현재 접속 안내가 아니다.

### 종료 영수증: controller 포함 두 번째 환경

- 실행: `backend/.venv/bin/python backend/scripts/cf002_interactive_login.py --google-input approved-file --lifetime-seconds 3600`
- URL: **http://localhost:3200**. Backend는 localhost:8200, Google 외부 callback은
  http://localhost:3200/api/auth/callback이다. code 교환에도 이 외부3200 URI를 유지한다.
- **PTY77282**, controller 포함 두 번째 환경이다.08:21 UTC 자기 자식 시작 신원·각 listener의
  PID/PGID·실행 nonce·200/401 응답을 결합한 readiness 통과.
- resource `CF-002-login-e71baf35469b`, container
  `8c5fb2fd7820b3fd987a70a516d57313e6b3441cbba4475221e750f6015568d4`,
  Created `2026-11-07T08:20:55.351489668Z`, host127.0.0.1:62235→5432, persistent mount0.
- BackendPID63732·Next supervisorPID63734, 시작08:20:57 UTC. 자기 watchdog 최대3600초와 부모
  pipe EOF 감지. 원래 최대 종료09:20~09:21 UTC였으나 **사용자 검사 종료 후09:00경 조기 정리했다**.
- **08:57:38 UTC status:** users2/identities2/sessions2/revoked0/active_sessions2/**Flow3**.
  B2 UI 삭제 사용자 보고 뒤 Flow4→3을 직접 확인했다.08:59:53 UTC 마지막 status도 같았다.
  총건수와 별도로 사용자가 A2건 보존·B2 재접속404를 확인했다. ID별 DB 재조회는 하지 않았다.
- 사용자 확인: A 목록2건·상세, B seed 전0건·seed 후2건·B2 삭제 후 B1만1건,
  B 시크릿에서 A1 접근404, 삭제 후 A2건 보존·B2 재접속404. A→B 역방향 UI는 미실행이다.
- 실제 서로 다른 Google identity/활성 session의 bind-A/B 및 각2건 저장, 삭제 전 내부
  check-owner는 통과했다. 실제 DB/service의 본인 목록/count/페이지/상세·타인 조회/삭제 거부다.
  사용자 UI 확인과 개별 HTTP/BFF/SSR 직접 관측을 구분한다.
- 실제 시간 만료·옛 cookie 재전송은 미검증이다. 현재 TTL3600의 자연 만료는 runtime 종료보다
  늦다. raw account/sub/token/cookie/secret 수집·공개 테스트 endpoint·코드 주입은 하지 않는다.
- `status`는 비민감 aggregate만 제공한다. 삭제 뒤 각2건 전제의 check-owner와 일괄
  delete-A/B는 실행하지 않는다. 사용자 확인 종료 또는 수명 종료 뒤 `finish`와 자기 소유
  CID/Created/nonce·자식 신원·사본 경계를 대조한 제거 결과를 확인했다.

추가 사용자 조작은 요청하지 않는다. 두 실제 사용자의 로그인 행·남은 합성3건은 이번 일회용 DB와
함께 제거됐다. 이를 로그아웃/세션 만료 통과로 계산하지 않는다. 원본 앱 DB/기존 컨테이너·volume·
Google Console·사용자 비밀 파일은 변경하지 않았다.

### 이력: 첫 환경 PTY12079 (종료·정리 완료)

07:51 readiness의 첫 resource는 CF-002-login-1b00c9c0873f/CID2192080fed68585be25db013bfbe7466313a25bd08ef78706fd59b509404ea73,
DB loopback61631/mount0, Backend59152/Next supervisor59154였다. 처음에는 사용자0건이었고,
사용자 첫 로그인 후 users1/active1, 사용자 로그아웃 후 revoked1/active0을 확인했다.
08:19 재확인 뒤 parent 지시로 finish/runner exit0·해당 DB/사본 제거를 확인했다.
당시 종료 예정08:50~08:51이나 status/finish-only 제약은 **현재 실행 상태가 아닌 이력**이다.

## 프로세스·자원 경계

`scripts/runner_owned_database.py`는 로컬 Unix Docker endpoint·직접 create 영수증 full ID/
Created/label/nonce·tmpfs/no mounts·loopback ephemeral binding·비관리자 전체 role flags를
검증한다. 일반 app URL 비교 guard는 그대로이며 fake app URL/skip/adoption 경로가 없다.
새 역할 asyncpg readonly 확인 뒤 engine을 만들고 실제 연결을 다시 readonly 확인한 동일
연결로 migration한다. 기존 앱 DB 정보나 .env의 DATABASE_URL을 읽지 않는다.

`scripts/google_login_workspace.py`는 명시한 source/config/public asset allowlist만 실제 복사한다.
private/backup/key/pem/sql/log 자료와 symlink를 거부하고 .env*는 열거나 복사하지 않는다.
Backend 사본 Settings(_env_file=None)를 명시해 dotenv source를 끈다. 원본 설정은 바꾸지 않는다.

`cf002_interactive_login.py`는 새 exec 자식을 private process group으로 생성하고 signal을 잠시
막은 spawn-등록 경계에서 raw PID/Popen 영수증을 즉시 추적한다. 부모의 admin owner/Docker/
bootstrap 비밀은 exec를 넘지 않는다. 제한 역할 DTO만 anonymous pipe로 Backend에 전달한다.
Next DTO/환경/인자에는 DB나 Google 필드가 없다. 부모 환경은 최소 allowlist만 사용한다.

`google_login_bootstrap.py`가 Backend 안에서만 승인된 입력 파일의 두 Google key를 선택한다.
`google_login_inputs.py`는 multiline/quoted duplicate/모호한 키·빈 값·공백 값·symlink 등을
원문 없는 오류로 거부하고 보간/환경 fallback/전체 dotenv source를 하지 않는다. 다른 assignment는
문법 상태만 확인하며 값을 해석·보관·복사하지 않는다. 텍스트의 행 스캔은 필요하므로 다른 바이트가
전혀 메모리를 지나지 않는다는 주장은 하지 않는다. raw Google 두 값은 부모/Next/인자/로그/
history/상태파일에 쓰지 않는다. Backend도 입력 전 제한 DB의 readonly 실연결을 다시 확인한다.

새 runtime pool connection은 첫 쓰기 전 readonly DB/user/nonce/server port·전체 제한 역할을
재대조한다. 자식 자체 유한 수명과 부모 종료 EOF를 감시하며 비밀을 보유한 앱을 무기한 남기지 않는다.
Backend access log와 Next callback query log는 껐고 자식 stdout/stderr도 노출하지 않는다.
진단 파일은 오류 class/module/함수·line 번호만 기록하며 message·입력·locals를 포함하지 않는다.
AI/Redis/Neo4j/기존 컨테이너·volume/데이터는 기동·연결·변경하지 않았다.

## 준비 회차의 직접 검증 이력

- controller 추가 전 Backend unit **334 passed**, 대상 Ruff/format·diff check 통과.
  이후 controller9개를 포함한 최종 unit343 통과 근거는 아래08:10 기록에 있다.
- reader/workspace의 독립 재현 결함 3건: private 자료 복사, multiline 가짜 key,
  quoted duplicate/whitespace를 회귀로 거부. 임의 URL/manifest/원격 context/ID·nonce·binding·
  권한/실연결 불일치, Docker daemon 오류를 absence로 오인하는 경우도 거부한다.
- 새로운 소유 DB `CF-002-login-13c19acb9314`: 실제 이중 readonly·동일 연결 upgrade,
  내부 session/Flow save/list/detail/delete와 잔여0·제거 통과. 과거 v0.4 결과를 재사용하지 않았다.
- 최종 fake exec 실행 `CF-002-login-213b03808aa2`, CID
  `4502ba719c1da8c1938deee2fa0713e365266d40055439fb1bde735227b26bba`, host61513:
  fake key·Google transport 차단, 제한 역할 runtime pool 실제 내부 write/outer rollback,
  각 건수0·nonce/listener readiness·save/Supervisor 차단·DB/사본 제거 통과.
- 부분 시작 실패 `CF-002-login-47e5dcad64ca`: Backend spawn 후 의도된 오류→exit1,
  기록된 자식·DB·사본 정리 통과. 실제 SIGTERM `CF-002-login-3ccef925279b`: ready 뒤 signal→
  exit130, 자식·DB·사본 정리 통과. lifecycle 옵션은 fake mode에만 허용한다.
- 초기 fake exec fixture import 실패 `CF-002-login-bed062ba6d95`는 DB가 제거됐지만 사본 정리
  미확인을 보고했다. 이후 정확한 CID/nonce/자기 경로 UID·mode/symlink 경계와 기록된 두 PID 부재를
  확인해 그 사본만 회수했다. 실패를 성공 정리로 덮지 않았다. fixture를 독립 synthetic JSON으로
  바꿨고 그 뒤 normal/partial/signal 실행은 자동 정리를 통과했다.
- 독립 검토는 exec/제한 DTO·즉시 추적·watchdog·실제 bind/nonce와 후속 fake fixture/진단 변경에서
  새 차단 결함이 없다고 전달했다. 마지막 fake-only lifecycle 옵션도 통합 검사로 확인했다.

준비 검증 명령(실제 Google 키 읽기 없음):

```sh
cd backend
.venv/bin/python -m pytest --confcutdir=tests/unit tests/unit -q
.venv/bin/python scripts/cf002_interactive_login.py --verify-owned-db
.venv/bin/python scripts/cf002_interactive_login.py --verify-fake-environment
# fake 전용 lifecycle 검사: --simulate-startup-failure / --hold-fake-seconds 15
```

## 실제 Google 사용과 A/B 수용

로그인 시작은 accounts.google.com authorization으로 scope **openid만** 사용한다. Backend는
callback에서 https://oauth2.googleapis.com/token에 code/verifier/client ID/secret을 서버 POST로
보내고 고정 discovery/JWKS를 확인한다. UserInfo/추가 scope·실제 AI·자동 계정 선택은 없다.
Console 등록·OAuth 테스트 사용자 변경이 필요하면 별도 대상 확인이며 자동으로 수정하지 않는다.

A 실제 왕복·callback·DB session과 재접속 연결 → 검증된 내부 principal로 합성 Flow 준비 →
실제 DB 재조회 목록/count/pagination·상세/근거·개별 삭제 → 사용자가 별도 프로필에서 다른 실제 B
선택 → 본인 성공·타인 목록0/상세·삭제404·legacy/stock 보존 순서로 확인한다.
로그아웃·서버 폐기·별도 짧은 TTL 실제 시간 만료·옛 cookie 재사용 거부(Backend/BFF401·SSR 개인자료0)는
각각 별도 증거가 필요하다. raw sub/token/cookie/secret은 보고하지 않는다. 현재 runtime에는 이 최종
A/B 전체 자동 검사/쿠키 보관 도구를 구현했다고 주장하지 않으며 실제 사용자 조작 후 검증을 이어간다.

정리는 시작 신원이 같은 자기 child group만 종료·pool 종료 후 자기 CID/Created/nonce/mount/binding을
다시 대조해 stop/rm한다. 중지·OOM 자기 container도 소유 증명과 실행 상태를 분리해 정리한다.
정확한 no-such-object만 부재로 보고 daemon/권한/timeout은 미확인으로 남긴다. 자기 inode가 같은
임시 사본만 삭제한다. SIGKILL/호스트 종료의 finally 보장은 하지 않으며 비밀 없는 영수증으로
잔여를 보고한다. 기존 자원 채택·prune/down -v/포트 기반 kill은 하지 않는다.

## 이력: 첫 환경 사용자 A 대기와 자동 도구 경계 (07:57 UTC)

당시 PTY12079는 유지했다. 07:57 status는 users/sessions/active/revoked/reports 모두0이었다.
사용자 로그인·계정 선택을 자동 조작하지 않는다. 실제 A 도착 후 우선 같은 status로
users1/sessions1/active1/revoked0을 확인하고 사용자에게 로컬 보관함 도착 여부만 확인한다.
원시 sub/cookie/token·브라우저 저장소·화면의 credential을 읽거나 요청하지 않는다.

운영상 한계: 이 **실행 중인 인스턴스**의 제어 명령은 status/finish뿐이다. source에 새 함수나
명령을 추가해도 Python이 자동 reload하지 않으며, 현재 status에는 identities 직접 count도 없다.
외부 프로세스가 영수증만으로 proof를 재생성해 DB에 접속하거나 환경/메모리에서 자격을 추출하지
않는다. debugger 주입·runtime code injection·public save/dev auth endpoint로 우회하지 않는다.
A의 첫 로그인/로그아웃은 현재 환경에서 진행할 수 있지만 fixture/control 확장을 이 인스턴스에
즉시 실행할 수 있다고 표현하지 않는다. 확장에는 검토된 controller를 탑재한 런타임 전환과
사용자 재로그인이 필요하므로 현재 환경을 임의 종료하지 않고 parent에게 이 좁은 실행 변경을 보고한다.

다음 controller의 최소 private 제어(새 Backend API나 인증 우회가 아님)는 다음과 같다.

- `status`: users/identities/sessions/active/revoked/Flow 건수만. AuthIdentity.subject·token/digest를 출력하지 않는다.
- `bind-A`/`bind-B`: 실제 Google callback이 만든 활성 session과 canonical Google identity 연결을
  내부 DB에서 확인하고 A/B 메모리 label로만 관리한다. B는 기존 A와 다른 실제 내부 user여야 한다.
  UUID/owner header 입력으로 label을 지정하지 않고, 모호한 다중 후보·같은 계정 B는 거부한다.
- `seed-A`/`seed-B`: 그 활성 session의 내부 principal을 재검증하고 기존 FlowReportService로
  합성 결과만 저장한다. owner/context는 public payload에서 받지 않는다. 반환은 합성 report ID/
  건수뿐이며 세션 자격·원시 외부 신원은 출력/파일 보관하지 않는다. stocks와 legacy 보존을 검사한다.
- 내부 A/B service/DB 검사는 실제 Google로 만들어진 principal로 own 성공·other 없음/삭제false를
  확인하되, 이것을 실제 브라우저/BFF/SSR 검증으로 대신하지 않는다.

브라우저 검증은 A와 B의 별도 프로필에서 사용자가 자기 결과·상대 합성 report 링크를 직접 연다.
본인 목록/count·상세·개별 삭제, 상대 상세404·상대 삭제404·legacy 비노출을 각각 확인한다.
자동화가 필요하면 **사용자가 누르는 임시 local 검사 UI**가 기존 same-origin API와 브라우저의
HttpOnly cookie를 정상 사용하고 status/건수만 표시하는 방안을 먼저 parent에게 설명한다.
이 방식도 client-side raw cookie/sub를 추출하거나 새 서버 인증 권한을 만들지는 않는다.
현재 임시 앱에 그 UI를 임의 추가하거나 사용자 계정을 자동 조작하지 않았다.

폐기/만료는 해당 일회용 A session만 내부 서버에서 폐기하거나, 테스트 만료를 짧게 설정하고
실제 시간 경과 후 기존 브라우저의 API 거부를 검사할 수 있다. 로그아웃은 기존 UI로 검증한다.
**로그아웃 후 옛 cookie 재전송**은 HttpOnly이므로 현재 status 도구만으로는 검사할 수 없다.
브라우저 cookie를 assistant에게 넘기는 방식을 쓰지 않는다. 필요하다면 Backend 내부가 이번에
발급한 값을 메모리에만 잠깐 보관해 localhost 재사용을 검사하는 구체적 test wrapper/접근 범위를
parent에게 먼저 보고한다. 별도 합의/검토 전 session 자격 수집·보관을 실행하지 않는다.

종료 예정은 여전히08:50~08:51 UTC이며 그 전에 parent의 종료 요청 또는 수명 종료를 확인하고
같은 runner의 child·DB·사본 제거 결과를 기록한다. A 한 계정 결과와 실제 B owner 검증, raw-cookie
재사용 미검증을 분리해 보고한다.

## Private controller 준비·별도 실제 DB 검증 (08:10 UTC)

`scripts/google_login_controller.py`와 `scripts/cf002_controller_check.py`,
`tests/unit/test_google_login_controller.py`를 추가하고 runner의 **향후 인스턴스**에 연결했다.
공개 endpoint·인증 우회·schema 변경은 없다. `bind-A/B`는 canonical Google identity 존재와
활성 session/비활성화되지 않은 user를 SQL로 확인하며 subject는 SELECT하지 않는다.
여러 session의 동일 user는 한 후보이고, 서로 다른 미배정 user가 여러 명이면 거부한다.
별칭에는 내부 user/session ID만 메모리로 보관하고 seed/check/delete 때 세션을 재검증한다.
token은 DB에도 없으며 browser credential을 추출하지 않는다. digest는 principal 검증에만
일시 사용하며 출력·파일·별칭 상태에 보관하지 않는다.

`seed-A/B`는 기존 내부 Flow 서비스로 각2건을 만들고 합성 report ID만 반환한다. 쓰기 전에
ID를 기록하므로 부분 저장 실패 후 무작정 재실행하지 않는다. `check-owner`는 A/B의 본인
목록/count·페이지·상세 성공과 타인 목록0·상세없음·삭제false를 검사한다. `delete-A/B`는
그 controller가 기록한 합성 ID에만 동작하며 반복 삭제는0건이다. 알 수 없는 명령은 거부하고,
예외의 SQL/값은 출력하지 않는다. 실제 browser/HTTP 검증이나 실제 callback 성공 판정은 아니다.

준비 검증 명령(실제 키/고정 앱 포트/브라우저/Google 사용 없음):

```sh
cd /Users/parkjinhee/AI/verith_refactor/verith/backend
.venv/bin/python -m pytest --confcutdir=tests/unit tests/unit -q
.venv/bin/python scripts/cf002_interactive_login.py --verify-controller
```

Backend unit **343 passed**, controller9개+기존 runner security14개를 포함한다. 변경4개 Python
파일 Ruff·format과 `git diff --check`도 통과했다. 실제 DB 첫 실행08:08 resource
`CF-002-login-cc0ad49cf556`/port61880은 내부 A/B 저장·조회·삭제·반복삭제·종목 보존,
동일계정/모호한 후보·만료/폐기 거부를 통과하고 해당 컨테이너를 제거했다.

owner-NULL legacy 회귀 추가 후 **최종 재실행08:09**:

- resource `CF-002-login-acde3564d4fe`, full CID
  `be118b04420175f1ad600b948061d55edb1d2e8fbe7fcb2c47cfb458c047c169`.
- Created `2026-11-07T08:09:30.493274378Z`, loopback127.0.0.1:61950→5432, persistent mounts0.
- 소유 증명·제한 역할·이중 readonly 사전 대조·동일 연결 migration 통과.
- 위 내부 A/B 검사와 새 owner-NULL 합성 legacy의 목록/count·상세·삭제 차단 및 owner 미변경 보존 통과.
- 마지막 users5/identities5/sessions6/revoked2/active3/Flow1. Flow1은 보존 여부를 확인한
  합성 legacy이며 별칭의 결과4건은 삭제됐다. 전부 합성 신원으로 실제 Google A/B 증거가 아니다.
- exit0, `owned_db_removed` 확인. 이 실행은 workspace/Backend/Next를 생성하지 않았다.
  live resource `CF-002-login-1b00c9c0873f`와 PTY12079는 변경·정리하지 않았다.

독립 검토는 controller `9a8058bc…75bb50`/runner `a5f2cc47…1fd96`에서 새 차단 결함 없음과
단위9개·실제/가짜 mode 동시 선택 거부(Docker0)를 직접 확인했다는 parent 전달이다.
그 뒤 synthetic check에 legacy 보존 검사를 보완한 최종 hash는
`2196ed84e74e0c140deb73e9cc830c0a65d138f643636e815d2f1cb462cc5610`이며 위 실제 DB에서 재검증했다.
독립 검토가 그 마지막 legacy 검사까지 실행했다고 주장하지 않는다.

**현재 PTY12079는 계속 옛 status/finish 명령만 지원**한다. 08:09:44 UTC status는 users0/
sessions0/active0/revoked0/Flow0이며 실제 callback 완료는 확인되지 않았다. 이 인스턴스에는
identity count/controller를 적용하지 않았고 임의 재시작하지 않았다. 로그인 성공 후 현재 도구로
알 수 있는 것은 aggregate user/session 건수뿐이다. identity issuer/연결, 특정 A principal,
fixture/browser/BFF/SSR·옛 cookie 재사용의 완료 근거는 아직 없다.
새 controller 사용은 parent와 조율한 종료·새 환경 전환 및 사용자 재로그인 이후에만 가능하다.

## 실제 첫 로그인 보고와 현재 세션 확인 (08:16:56 UTC)

사용자가 “로그인 되었어”라고 보고한 뒤, 살아 있는 PTY12079에 `status`만 보냈다.
반환은 users1/sessions1/active_sessions1/revoked0/Flow0이다. 기존0건에서 이 실행의 앱 사용자와
활성 세션1건이 생성됐다. 사용자 보고와 실제 격리 DB aggregate 확인을 첫 로그인 증거로
기록한다. 개별 Google HTTP 왕복·callback 응답·issuer/sub·브라우저 자격을 assistant가 직접
열람/수집한 것은 아니다. 현재 status는 identity count를 제공하지 않는다. 실제 owner fixture,
A/B·BFF/SSR·만료·폐기·옛 cookie 재사용을 통과로 확대하지 않는다.

현재 세션을 바꾸지 않았고 logout/fixture/재시작/DB 전환은 실행하지 않았다. 사용자가 직접
`http://localhost:3200/`의 “내 Flow 보관함” 화면에서 **로그아웃**을 누르면 같은 `/`로 이동하며
“Google로 로그인” 링크가 보여야 한다. 새로고침해도 개인 보관함이 재노출되지 않는지 확인한다.
그 이후에만 `status`를 다시 확인하며 기대는 users1/sessions1/revoked1/active_sessions0이다.
UI 이동만으로 DB 폐기 통과를 선언하거나, 이를 옛 cookie 재전송 검사로 간주하지 않는다.

controller 환경 전환은 아직 실행하지 않았다. 전환 시 `finish`로 이번 child/DB/workspace를
소유 대조 후 정리하고 새 runner가 새 CID·ephemeral 주소·제한 역할·빈 DB를 만들며 migration과
readiness를 재검증해야 한다. 현재 DB의 A 내부 user/identity/session은 일회용 자원 제거와 함께
사라지고 위 비민감 증거만 남는다. 이전 internal user UUID의 연속성을 검증하는 것은 아니다.
Google 계정/Google 자체 SSO 상태·Console·원본 .env는 변경하지 않는다. 같은 localhost origin에
남은 앱 cookie는 새 DB에서 미등록이므로 인증 근거가 되지 않으며 다음 callback에서 새로 발급된다.
이 동작은 아직 실제 전환/옛 cookie 검사를 실행한 결과가 아니다.

새 환경에서 A는 사용자가 다시 로그인해야 하고 그 다음 private `bind-A`→`seed-A`를 실행한다.
B는 별도 브라우저 프로필/세션에서 사용자가 다른 실제 Google 계정을 직접 선택한 뒤
`bind-B`→`seed-B`→`check-owner`를 진행한다. 두 브라우저에서 본인 목록·상세·개별 삭제와
상대 합성 ID의 거부를 따로 검증한다. controller 결과는 내부 DB/service 근거일 뿐이다.
사용자에게 지금 환경 전환/재로그인을 요구하지 않으며, parent가 현재 로그아웃 결과와 다음
운영 순서를 전달한 뒤 진행한다. 기존 실행 종료 예정08:50~08:51 UTC는 유지한다.

## 사용자 직접 로그아웃·실제 서버 폐기 확인 (08:18:29 UTC)

사용자가 “로그아웃 버튼 눌렀고, Google로 로그인이 보여”라고 보고한 직후, PTY12079에
`status`만 보냈다. users1/sessions1/**revoked1/active_sessions0**/Flow0을 확인했다.
로그인 후 active1/revoked0에서 서버 폐기 상태로 바뀌었으므로 사용자 UI 복귀와 실제 DB 폐기가
일치한다. 브라우저/신원/cookie/token을 추출하지 않았고 assistant가 logout을 대신 호출하지 않았다.
이것은 옛 cookie를 재전송한 결과나 실제 시간 만료·다른 B 인가 검증은 아니다.
현재 앱/DB/PTY를 종료하지 않았으며 controller를 주입하지 않았다.

다음 전환의 자동 가능 범위는 이미 승인된 같은 로컬 격리 테스트의 자기 자원 정리·새 자원
생성·제한 역할/migration·env-free 앱 준비와 Backend-only Google 두 키 선택 사용이다.
같은 액션에 대한 새 credential 사용 승인을 요구하지 않는다. 다만 현재 환경을 유지하라는
parent 지시가 있으므로 **전환 실행 지시 전 finish/재시작은 하지 않는다**. 전환이 정해지면:

1. 현재 `finish` 후 자기 child·CID/Created/nonce·workspace 제거를 확인한다. 앱 원본이나
   Google SSO/Console/기존 DB에는 손대지 않는다. 현재 합성 결과는0건이고 일회용 사용자·폐기
   세션은 DB와 함께 사라진다. 첫 로그인·로그아웃의 aggregate 증거는 이 기록에 보존한다.
2. 포트 점유를 새로 확인하고 현재 검토된 runner로 새 disposable DB·같은 localhost3200/8200
   앱을 시작한다. 키 사용 방식은 기존 승인과 동일하며 값·전체 .env를 assistant가 읽지 않는다.
3. 사용자가 A 계정으로 다시 로그인한다. callback이 만든 활성 session을 private bind-A로
   확인하고 seed-A로 합성2건을 준비한다. A UI의 본인 목록·상세·삭제는 별도 사용자 확인이다.
4. 사용자가 별도 브라우저 프로필/세션에서 서로 다른 실제 B 계정을 선택·로그인한다.
   bind-B/seed-B/check-owner의 DB/service 검사와 두 브라우저의 타인 접근 거부를 구분해 남긴다.

계정 선택·비밀번호/MFA/동의는 계속 사용자만 수행한다. B 계정을 임의 지정·생성하거나 기존
브라우저 credential을 수집하지 않는다. 공개 테스트 endpoint·다른 환경 접근도 추가하지 않는다.
옛 cookie 재사용 등 새 자격 수집이 필요한 자동 검사는 현재 도구 범위 밖 미검증으로 유지한다.

## Controller 포함 새 실제 대기 환경 전환 (08:21 UTC)

parent의 전환 실행 지시 후08:19:46 UTC에 기존 PTY12079 status를 재확인했다.
users1/sessions1/revoked1/active0/Flow0으로 조건을 충족했고 `finish`를 보냈다.
session_end 동일 건수, resource `CF-002-login-1b00c9c0873f`의 `owned_db_removed`와
`owned_workspace_removed`, runner exit0을 확인했다. 로그인/폐기 행은 해당 DB와 함께 제거됐고
사용자 보고·aggregate 증거는 위에 남겼다. 기존 앱/다른 컨테이너·volume는 건드리지 않았다.

새 첫 시작은 resource_id:null/exit1로 자원 생성 전에 fail-closed 중단됐다. 구체적 예외 값은
출력하지 않아 원인을 확정하지 않는다. 읽기 전용 lsof에서3200/8200 listener 없음과 별도
IPv4/IPv6 loopback bind 전부 가능을 확인한 뒤 동일 경로 재실행이 성공했다. guard를 완화하거나
다른 프로세스를 종료하지 않았다.

실행 명령은 backend 작업 폴더의 다음과 같으며 Google 두 키는 승인된 Backend-only reader만 사용했다.

```sh
.venv/bin/python scripts/cf002_interactive_login.py --google-input approved-file --lifetime-seconds 3600
```

- 새 PTY **77282**, URL **http://localhost:3200**, Backend localhost8200.
- resource `CF-002-login-e71baf35469b`, full CID
  `8c5fb2fd7820b3fd987a70a516d57313e6b3441cbba4475221e750f6015568d4`.
- Created `2026-11-07T08:20:55.351489668Z`, loopback127.0.0.1:62235→5432, persistent mounts0.
- workspace `/Users/parkjinhee/AI/verith_refactor/.cf002-google-check-5o8c028c`.
- BackendPID63732/Frontend supervisorPID63734, 시작08:20:57 UTC. 자기 PID/PGID·listener·nonce
  readiness, 제한 역할 readonly 대조, 동일 연결 migration 모두 통과.
- 예상 자동 종료09:20~09:21 UTC, readiness 관측 시각 기준 보수적 상한09:21:05 UTC.
  parent EOF/child 유한 수명도 적용한다. 조기 종료는 이 PTY의 `finish`로 자기 자원만 정리한다.
- 새 `status`는 users0/identities0/sessions0/revoked0/active0/Flow0이다. private controller
  명령을 제공하지만 아직 bind/seed/check/delete는 실제 계정으로 실행하지 않았다.
- 실행 소스는 독립 검토 runner `a5f2cc47…1fd96`, controller `9a8058bc…75bb50`,
  bootstrap `c66c2c03…a5e9`, owned DB `6ad32139…626d8`과 일치했다.

계정 선택/Google 로그인/MFA/동의는 사용자에게 맡겼다. A는 새 DB이므로 다시 로그인해야 한다.
현재 실제 A/B는 새 환경에서 미실행이다. 원시 sub/token/cookie/두 키를 열람·출력·파일 보관하지
않았으며 원본 .env 전체·Google Console·AI·기존 앱 DB·다른 컨테이너는 변경하지 않았다.

## 새 환경 A 실제 로그인·내부 합성 fixture 준비 (08:26 UTC)

사용자가 새 환경에서 “로그인 했어”라고 보고했다. PTY77282 status는08:26:20 UTC
users1/identities1/sessions1/revoked0/active1/Flow0이었다. 순서대로 private `bind-A` 성공
(canonical Google identity 존재·enabled user·활성 session 조건 확인), `seed-A` 성공 count2를
확인했다. 모호한 후보/소유 증명 거부는 없었으며 다른 owner 입력이나 public save는 쓰지 않았다.
08:26:55 UTC status는 users1/identities1/sessions1/revoked0/active1/**Flow2**였다.
사용자/identity/session 식별자·subject·token/cookie/digest·Google 키는 출력/보관하지 않았다.

아래 ID는 개인 신원이나 credential이 아닌 새로 생성한 **합성 리포트 ID**다.

- A1: `3b27bc32-e957-42b1-bb8f-b8c9353f809f` — B의 타인 조회·삭제 거부 검사용으로 보존.
- A2: `19afe873-600b-43c8-9869-520a7077b602` — B 내부 `check-owner` 완료 후 사용자 본인
  삭제 검사용. 지금은 이 결과도 보존한다.

현재 `check-owner`는 A/B 각2건을 기대하므로 **지금 삭제해도 되는 리포트는 없다**. controller의
delete-A, UI의 “이 결과 삭제”, 자동 로그아웃/새 환경 전환은 실행하지 않았다. 계정 선택도
사용자만 수행했다. B 준비와 내부 검사 후 본인 삭제 순서를 따로 전달한다.

지금 사용자 최소 행동은 A가 로그인한 같은 브라우저의 `http://localhost:3200/` 새로고침이다.
“내 Flow 보관함”, “2개 결과”, `CF002 합성 A`/`수급 리포트` 문구의 링크2개가 보여야 한다.
목록 제목은 두 건이 같을 수 있으므로 순서만으로 A1/A2를 구분하지 않는다. 하나를 열어
수급·자금흐름 상세가 표시되는지만 확인하고 삭제 버튼은 누르지 않는다.
직접 A1 URL은 `http://localhost:3200/reports/flow/3b27bc32-e957-42b1-bb8f-b8c9353f809f`다.

현재 근거는 실제 로그인 사용자 보고 + DB Google identity/활성 session 조건부 bind + 내부 저장
성공/DB Flow2건이다. 사용자 브라우저의 목록/상세·BFF/SSR 렌더 성공은 아직 회신 전이므로
통과로 세지 않는다. B 계정/상대 접근 거부·개별 삭제·새 환경 로그아웃·만료/옛 cookie 재사용도
미검증이다. 환경·A 세션은 유지 중이며 종료 예정09:20~09:21 UTC다.

## 실제 A 목록·상세 사용자 확인, B 수동 로그인 대기 (08:40 UTC)

사용자가 A 목록에 두 합성 링크가 보인다고 전달하고, 이어 “클릭하면 보여”라고 상세 표시를
확인했다. **실제 A 보관함2건·상세 렌더의 사용자 확인**으로 기록한다. 개별 HTTP status나
SSR/BFF의 각 네트워크 응답을 직접 관측한 결과, 타인 거부·옛 cookie 재사용으로 확대하지 않는다.
08:39 UTC PTY77282 status는 users1/identities1/sessions1/revoked0/active1/Flow2로 유지됐다.
그 뒤 bind-B/seed-B/check-owner/delete/logout/환경 전환은 실행하지 않았다.

B 최소 순서는 A 창을 그대로 두고 별도 cookie 문맥(일반 A와 분리된 Chrome 시크릿 창 또는
별도 프로필)에서 `http://localhost:3200/`에 접속하는 것이다. 미인증 첫 화면에는
“Google로 로그인”이 보여야 한다. 사용자가 A와 다른 실제 Google 계정을 직접 선택·로그인한
뒤에는 **내 Flow 보관함 0개 결과**가 기대된다. A의2건이 B 창에 보이면 seed하지 않고 중단한다.
B 로그인 보고와 status 확인 전에는 내부 B 명령을 실행하지 않는다.

B 보고 후 status users2/identities2와 활성 session 추가를 확인하고 `bind-B`를 실행한다.
같은 계정/복수 미배정 owner/소유 증명 불일치는 거부 그대로 중단한다. 성공 시 `seed-B`로 B2건을
준비하고 `check-owner`로 내부 A/B 목록/count/페이지/상세·타인 삭제 차단을 검사한다.
이 내부 결과와 별개로 B 브라우저 자신의2건·A 링크 거부, A 창의 자신의2건·B 링크 거부를
사용자에게 확인한다. 두 계정의 네 결과는 이 검사 전 보존하며 삭제 검사는 그 뒤 진행한다.

현재 최대 환경 수명은 여전히09:20~09:21 UTC(보수적 상한09:21:05)이다. A session의 만료와
프로세스 수명은 다른 조건이며 이를 실제 시간 만료 검증으로 보고하지 않는다.

Google `access_denied`가 나면 계정 값·callback 전체 URL·code/state·화면 비밀을 받지 않고
오류 코드와 비민감 이유만 확인한다. 사용자가 취소/거부한 경우 본인이 계속하기를 원할 때
보관함의 로그인 링크에서 새 시도를 시작한다. 앱 callback은 state를 일회 소비한 뒤 error를
거부하므로 예전 callback URL을 새로고침/재전송하지 않는다. A 세션은 변경하지 않는다.

Google 공식 문서상 `openid` 등 기본 identity scope만 쓰는 요청은 Testing의 test-user 목록
예외가 있다. **현재 openid-only 경로에서 access_denied를 곧바로 “B가 test user가 아님”으로
단정하지 않는다.** 실제 화면이 테스트 사용자 제한 또는 조직/계정 정책을 가리키면 해당
대상/이유를 먼저 확인한다. 필요한 Console test-user 변경·조직 정책 변경은 현재 미실행이며
정확한 대상 액션 확인 후 진행한다. 앱 게시/새 client·secret/추가 scope·정책 우회는 하지 않는다.

근거: [Google OAuth 응답 처리](https://developers.google.com/identity/protocols/oauth2/web-server),
[Google 앱 Audience/기본 신원 scope 예외](https://support.google.com/cloud/answer/15549945?hl=en-MC).

## 실제 서로 다른 B 로그인·내부 A/B owner 검사 (08:47 UTC)

사용자가 A와 다른 Google 계정으로 시크릿 창에 로그인한 뒤 “보관함 비어져 있어 아무것도
안보여”라고 보고했다. 이는 **B 브라우저의 seed 전 본인0건 표시 사용자 확인**이다.
08:46:58 UTC PTY77282 status는 users2/identities2/sessions2/revoked0/active2/Flow2였다.
이어 순서대로 `bind-B`→`seed-B`→`check-owner`를 실행했다.

- bind-B는 A와 다른 내부 user, canonical Google identity 존재, enabled user와 활성 session을
  확인해 성공했다. synthetic 신원/임의 UUID/header로 대체하지 않았다.
- seed-B count2 성공. 합성 B1 `0632f418-ca9b-4da9-85a7-cf42d7c8a1cd`,
  B2 `8350bbdd-d2ce-4aa6-93b2-45de1732db32`를 준비했다.
- check-owner는 **internal_service_owner_check:passed**,
  **browser_BFF_SSR:not_verified_by_controller**를 반환했다. 실제 callback으로 생성된 두
  사용자/활성 session을 재검증한 내부 서비스+실제 DB 경로로, 각 본인 목록/count2·1건씩
  pagination·상세 성공과 상대 목록0·상세없음·삭제false가 통과했다.
- 08:47:51 UTC 최종 status는 users2/identities2/sessions2/revoked0/active2/**Flow4**다.
  A의2건과 B의2건 모두 보존됐다. 본인 삭제/로그아웃/브라우저 계정 조작/환경 전환은 하지 않았다.
  원시 account/sub/token/cookie/digest/secret을 출력·보관하지 않았다.

다음 사용자 최소 행동은 **현재 B 시크릿 창**에서 localhost3200 보관함을 새로고침하여
“2개 결과”와 `CF002 합성 B` 수급 리포트2건이 보이는지 확인하는 것이다. 그 다음 아래 A1
주소를 **복사해 B 시크릿 창 주소창에 붙여넣는다**. A 일반 창에서 링크를 클릭하지 않는다.

`http://localhost:3200/reports/flow/3b27bc32-e957-42b1-bb8f-b8c9353f809f`

기대는 A 본문/수치 없이 404·페이지를 찾을 수 없음 화면이다. SSR 상세 코드가 Backend404를
`notFound()`로 처리한다는 코드 근거이며 실제 B 화면/HTTP status 확인은 아직 회신 전이다.
로그인 화면으로만 돌아간다면 정상 로그인 B의 타인404 증거와 구분해 추가 확인한다.
검사 후 보관함으로 돌아가 B2건이 유지되는지도 사용자에게 확인한다.

A2 본인 삭제는 내부 검사 완료 조건은 충족했지만 **이번 단계에서는 아직 실행/요청하지
않았다**. B UI2건/타인 거부 확인 후 별도로 진행한다. A 목록·상세, B seed 전0건의 사용자
확인과 위 내부 검사, 아직 미검증 B UI·개별 HTTP/BFF 응답·옛 cookie 재사용을 구분한다.
PTY77282와 두 사용자 세션은 유지 중이며09:20~09:21 UTC 종료 예정은 그대로다.

## B→A 실제 상세 거부 사용자 확인·남은 UI 검사 (08:52 UTC)

사용자가 **B 시크릿 창**에서 A1 주소가 `404 / This page could not be found.`로 보인다고
보고했다. 실제 서로 다른 계정의 **교차 상세 접근 거부 사용자 확인**으로 기록한다.
브라우저 네트워크 status를 assistant가 직접 캡처한 결과로 표현하지 않는다. B 본인2건 목록과
B 본인 상세는 아직 사용자 보고가 없으므로 미검증이다.
08:52:26 UTC status는 users2/identities2/sessions2/revoked0/active2/Flow4다. 환경·A/B 세션과
합성4건을 유지했고 웹 DELETE/controller delete/로그아웃/전환을 실행하지 않았다.

남은 UI 최소 순서(계정 조작·요청은 사용자가 정상 브라우저에서 수행):

1. **B 시크릿 창**의 localhost3200 보관함 새로고침: CF002 합성 B2건 확인. B1
   `http://localhost:3200/reports/flow/0632f418-ca9b-4da9-85a7-cf42d7c8a1cd`를 같은 창에서
   열어 본인 상세 확인. 지금 B1/B2는 삭제하지 않는다.
2. **A 원래 창**에서 같은 B1 주소를 주소창에 붙여넣어 반대 방향404/본문 비노출 확인.
3. **A 원래 창**에서 A2
   `http://localhost:3200/reports/flow/19afe873-600b-43c8-9869-520a7077b602`를 열고
   “이 결과 삭제”를 한 번 누른다. 삭제 전 A2건 → 삭제 후 보관함 A1건이 기대된다.
   남아야 하는 A1은 `3b27bc32-e957-42b1-bb8f-b8c9353f809f`다.
4. **B 시크릿 창** 보관함 새로고침: B1/B2 두 건이 그대로여야 한다. 사용자 삭제 보고 후
   private status의 Flow3을 확인한다. A2 재접속은 없는 결과404가 기대된다.

이 안내는 아직 수행 결과가 아니다. 승인된 브라우저 제어 문맥을 확보하거나 session 자격을
수집하지 않았으므로 실제 웹 삭제는 사용자 UI의 한 번 클릭으로 검증한다. 내부 delete-A는
A의 두 건을 모두 대상으로 하므로 실행하지 않는다. check-owner는 각2건을 기대하는 검사여서
**의도된 A2 삭제 뒤 재실행하지 않는다**. 삭제 후 aggregate3건과 A1/B2건 보존의 사용자 확인을
구분해 기록한다.

현재 도구로 가능한 폐기 검사는 각 사용자 브라우저의 정상 로그아웃 후 status의 revoked/active
변화·새로고침 로그인 화면을 확인하는 것이다. 첫 환경에서는 이미 통과했고 현재 두 계정
환경의 폐기는 아직 미검증이다. 실행 중 Backend의 세션 TTL은3600초로 고정이고 A/B 발급은
08:26/08:46경이므로 자연 만료는09:26/09:46경으로 현 런타임 종료09:20~09:21보다 늦다.
따라서 **현재 인스턴스에서 실제 시간 만료를 검증할 수 없다**. 다음 짧은 TTL 별도 환경의
준비/검토와 정상 브라우저 재접속 검사가 필요하며 지금 설정/수명을 임의 변경하지 않는다.
옛 cookie 재전송은 이번 controller가 bearer를 수집/보관하지 않으므로 미검증이다.
별도 credential 수집·공개 인증 endpoint로 우회하지 않는다.

사용자 확인이 끝나거나 유한 수명이 종료될 때만 자기 자원을 finish/소유 대조로 정리한다.
현재 테스트 중이므로 지금 종료하지 않는다. Console·기존 DB·브랜치·commit/push/PR도 변경하지 않는다.

## B 목록2건 확인·삭제 대상을 B2로 변경 (08:54 UTC)

사용자가 B 시크릿 창 새로고침 후 B1/B2 두 링크를 전달했다. **B 본인2건 목록의 사용자 확인**을
추가한다. B2 링크 전달만으로 상세 본문 확인을 확정하지 않는다.08:54:07 UTC status는 여전히
users2/identities2/sessions2/revoked0/active2/Flow4다. 실제 DELETE는 실행하지 않았다.

최신 사용자 절차는 앞의 **A2 삭제 계획을 대체**한다. A2는 보존한다.

- B 시크릿 창에서 B2 `http://localhost:3200/reports/flow/8350bbdd-d2ce-4aa6-93b2-45de1732db32`
  상세를 확인한 뒤 “이 결과 삭제”를 한 번 누른다. 삭제 전 B2건 → 삭제 후 B1건이어야 한다.
- 남는 B1은 `0632f418-ca9b-4da9-85a7-cf42d7c8a1cd`다. A 원래 창의 A1/A2 두 건은 그대로여야 한다.
- 삭제 보고 후 private status의 Flow3을 확인한다. B2 재접속404·B1 상세 유지·A 목록2건의
  사용자 확인과 합쳐 기록한다. A→B 반대 방향 교차 확인에는 남은 B1 링크를 사용한다.

`delete-B`는 두 결과를 모두 지울 수 있어 사용하지 않는다. 기존 check-owner는 각2건 전제라
삭제 뒤 재실행하지 않으며08:47 성공 근거를 보존한다. **현재 살아 있는 controller에는 별도
read-only 잔여 command가 없다**. status는 aggregate만 제공하므로 report ID별 DB 잔여 확인으로
확대하지 않는다. 현재 안전한 경로는 status3과 두 정상 브라우저의 A2건/B1건·삭제대상404 확인이다.
새 잔여 checker를 source에 추가해도 현재 프로세스에 적용되지 않으며 debugger/reload/외부
credential 추출/영수증만의 DB 재접속으로 우회하지 않는다. 필요 시 후속 runner에 read-only
checker를 구현·검토·새 소유 자원에서 검증하되 지금 사용자 환경을 전환하지 않는다.

## B2 실제 UI 삭제·총건수 대조 (08:57 UTC)

사용자가 B2를 삭제했고 B 시크릿 보관함 “1개 결과”에 B1
`0632f418-ca9b-4da9-85a7-cf42d7c8a1cd`만 남았다고 확인했다. PTY77282 status의08:57:38 UTC
users2/identities2/sessions2/revoked0/active2/**Flow3**을 직접 확인했다. 삭제 전4→3과 사용자
B 목록1건이 일치한다. B2별 DB 조회나 DELETE HTTP status를 직접 관측한 것은 아니다.
사용자 정상 UI 클릭이며 assistant의 일괄/HTTP 삭제·credential 추출은 없었다.

남은 최소 사용자 확인:

- **A 원래 창:** `http://localhost:3200/` 새로고침 → A1/A2 **2개 결과**가 유지돼야 한다.
- **B 시크릿 창:** 삭제된 B2 주소
  `http://localhost:3200/reports/flow/8350bbdd-d2ce-4aa6-93b2-45de1732db32`를 주소창에 붙여넣기 →
  본문 없이404/This page could not be found.가 기대된다.
- 아직 미검증인 반대 방향 교차 UI는 **A 원래 창**에서 남은 B1 주소
  `http://localhost:3200/reports/flow/0632f418-ca9b-4da9-85a7-cf42d7c8a1cd`를 열어404를 확인한다.

A2건 보존·삭제B2 재접속404·역방향 UI는 아직 회신 전이며 총3건만으로 확정하지 않는다.
현 환경에서 각 사용자 로그아웃의 DB revoked 변화, 실제 시간 만료·옛 cookie 재전송도 미검증이다.
시간 만료는 현 TTL/수명으로 자연 만료까지 도달할 수 없다는 한계를 유지한다.
최종 독립 재검토는 현재 runtime/controller 해시 유지, synthetic-only legacy 추가 검사 안전,
controller unit9개 재통과와 새 코드 차단 결함 없음이라는 parent 전달이며 실제 UI/현 DB 조작을
독립 검토자가 실행한 것으로 바꾸지 않는다. 소스 변경은 없고 문서 diff check만 다시 실행했다.

현재 환경은 종료하지 않는다. 마지막 사용자 확인 또는 수명 종료 뒤 status로 최종 합성/세션
건수를 기록하고 같은 PTY의 finish→자기 child 정리→소유 검증된 전체 CID 제거/명확한 부재
확인→자기 inode/경로 사본 제거→runner exit 결과를 확인한다. 실패 시 해당 잔여 영수증과
미확인 항목만 보고하며 다른 컨테이너/포트 점유자를 정리하지 않는다.

## 최종 사용자 확인·실제 종료/정리·산출물 (09:00~09:07 UTC)

사용자가 A 일반 창의 A1/A2 **2개 결과**와 B 시크릿 창의 삭제B2 **404**를 확인했다.
08:59:53 UTC 마지막 status는 users2/identities2/sessions2/revoked0/active2/**Flow3**으로,
사용자 확인의 A2건/B1건과 일치한다. 개별 owner별 DB 재조회나 네트워크 status를 직접 캡처한
결과는 아니다. A→B 반대 방향 UI·B 본문 표시 명시 확인·실제 시간 만료·옛 cookie 재전송은
미검증으로 유지한다. B 본인 UI 삭제는 사용자 클릭과 B1건/서버 총3건으로 확인했다.

parent의 테스트 종료 지시에 따라 같은 PTY77282에 `finish`를 보냈다. session_end의 동일 건수,
resource `CF-002-login-e71baf35469b`의 **owned_db_removed/owned_workspace_removed/exit0**을
확인했다. owner.cleanup은 생성 영수증의 full CID/Created/nonce·labels·mount/binding을
대조한 자기 자원만 제거했다. 이어 LocalDocker의 exact no-such-object 판정으로
CID `8c5fb2fd7820b3fd987a70a516d57313e6b3441cbba4475221e750f6015568d4` 부재true,
`/Users/parkjinhee/AI/verith_refactor/.cf002-google-check-5o8c028c` 부재true를 별도로 확인했다.
ps의 Backend63732/Next supervisor63734 결과와 lsof3200/8200 listener 결과도 비어 있었다.
**현재 테스트 앱/PTY/해당 컨테이너/사본은 종료·제거 완료**다. 활성세션2행과 합성3건은 DB
제거와 함께 사라졌으며 이를 정상 로그아웃/시간 만료로 보고하지 않는다. 기존 자원은 건드리지 않았다.

최종 비파괴 검사:

- Backend unit **343 passed** 재실행, 준비 도우미/테스트12파일 Ruff·format 통과.
- 변경 Python62파일 AST 통과. 전체 diff check 통과.
- 비밀 env 없는 새 allowlist 사본에서 Frontend **18 passed**(단위15+로컬 Next HTTP3),
  tsc --noEmit 통과. 실제 Google/DB에 연결하지 않는 합성 HTTP 검사다.
- 전체 `npm run lint`는 **실패**: 기존 technical.ts:191/207 explicit-any2건과 unused 경고3건.
  해당 파일이 기준 HEAD와 byte 단위로 같음을 확인했고 범위 밖 수정을 하지 않았다.
- 별도 비밀 env 없는 사본에서 CF-002 변경 TS/TSX24파일 ESLint와 production build 통과.
  첫 검사 사본도 finally에서 제거했고 두 번째 사본도 정상 제거했다. build 미실행으로 남기지 않았다.
- 문서의 exact git-add115개와 현재 작업 변경115개가 일치, zsh 명령4블록 syntax-only 통과,
  staged0 확인. 실제 add/commit/push/PR/브랜치 전환은 하지 않았다.

산출물은 `backend/docs/cf002_commit_pr.md`의 사용자 실행 블록과
`backend/docs/cf002_pr_body.md`의 완성된 Draft PR 본문이다. branch/HEAD/origin·선행 staged
guard와 검토 단계가 있으며 ignored `.env`/Docker-compose.yml·임시 자료는 포함하지 않는다.
Docker-compose.yml의 네 host mapping 변경은 **로컬 ignored 상태로만 남으며 commit/PR에
전달되지 않는다**. 추적된 코드·README·docs/local_ports.md의 안전한 포트 안내와 구분한다.
기존 사용자 private env는 path의 ignore 여부만 확인했고 값은 읽거나 stage하지 않았다.
전체 완료/서비스 공개가 아니라 남은 수용 항목과 기존 lint 결함을 드러낸 Draft 초안이다.

parent의09:06:47 UTC 독립 읽기 재확인도 전달받았다: Docker daemon27.4.0 정상 응답,
같은 정확 CID의 No such container·지정 PID63732/63734 부재·지정 workspace 부재다.
독립 검토자는 Env/비밀 조회나 추가 삭제를 하지 않았다고 보고했다. 위 자체 실행/확인 근거와
이 별도 전달 근거를 구분한다.
