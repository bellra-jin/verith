# CF-019 Flow 표시 품질·삭제 확인 UX

- 사용 정본 CF-019 v1.1 SHA256 `34180934c6bd0c2ab3e4d9075579c976b5cf5e26349c2e68fc58bd0bf47c45d4`.
- 전체 작업 운영 v1.3 §4.1 SHA256 `fe2cceb21661baa3b2a546b2f337374ea6d45c5817bcc5cdd6958f16b91761f5`를 최종 UX·승인순서의 유일한 현재 기준으로 참조한다.
- base clean develop `67bb1e143cb9c59579ca20a184369a845111bbdb`, branch `fix/flow-display-delete-ux`. PR23 병합/최종 head771e554b…의 CI42569408189 성공은 선행 전달 증거이며 이번 직접 재실행이 아니다.

## 현재 수용 상태

**사용자가 요청한 기본 실화면 흐름은 통과했지만 CF-019 전체 수용/merge-ready는 아니다.** 기존 Backend self3/unit54, Frontend94/type0/lint 오류·경고0 및 독립 source/로그 검토와 구분해, run6에서 실제 본문·삭제 확인창·취소 DELETE0·단일 삭제 DELETE1/204 보관함 이동을 확인했다. run8에서는 정확127.0.0.1 origin의 새 합성 URL로 삭제 뒤 뒤로가기의 gone 안내·본문 비공개와 같은 보고서의 직접 HTTP404 재조회를 추가 확인했다. 표시 대표값 전수·더블클릭·고급 오류/timeout/늦은 응답·owner/URL 등 실제 UI 및 NextSSR/BFF/BackendPG/providers/OAuth 통합은 미완료다.

run7은 조정 측이 localhost URL을 잘못 안내해 fixture의 고정127.0.0.1 origin과 달랐다. Origin 불일치403은 DELETE 카운터 증가 전 차단이며 제품 결함으로 확정하지 않는다. 고정 origin과 보호 규칙은 바꾸지 않았다. Mac 연결 중단 후 완료 로그에는 자기 group 정리 불완전/root 유지가 남았다. 재연결 뒤 PID/process group/listener 부재는 독립 확인했지만 해당 임시 root는 남아 있고 삭제/이동하지 않았다. 이를 정리 완료라고 쓰지 않는다.

run1–6는 기존 자동 기한/실패 종료와 자기 root 정리 이력을 보존한다. run8은 종료 요청 후 기존 연결 대기를 거쳐 exit0/CF019_FIXTURE_CLOSED로 정상 종료했고 자기 root 부재를 확인했다. 타임아웃 종료가 아니며 종료 버튼만으로 즉시 완전 종료됐다고 하지 않는다. 기존 연결이 server.close callback을 지연할 수 있는 fixture 자립 종료 편의성 제한을 남긴다. 실제 테스트 탭을 닫았다는 사용자 회신은 없어 그 인과를 확정하지 않는다. run7의 잔존 root와 run8 정리 성공을 구분한다.

앞선 테스트 창 닫기1회는 동작/검증 timeout으로 도구 완료를 확정하지 못했으나 사용자가 닫힌 것으로 보인다고 알렸다. 이후 수동 검증에는 로그인 없는 CF019 테스트 프로필을 사용했다. 프로필 자료는 유지하며 영구 삭제하지 않았다. 기존 일반 프로필/쿠키·실계정/원본 DB·키·provider/Google는 사용하지 않았다. 아래 회차별 대기·미확인 문장은 당시 이력이고 현재 상태는 이 절과 run7/run8 기록을 우선한다. 현재 근거로 기록과 Draft 전용 사용자 명령을 갱신하며 Ready/merge는 보류한다.

## 구현과 불변 경계

활성 FlowReportView/HTML 표시에서 누락·저장0·작은 비영값/underflow·기관 부분 범위·강도 단위를 구분한다. 기존 숫자·정밀도·해석 본문을 보존하고 TS/Python 표시 wrapper는 정확 binary64 half-even으로 맞춘다. 표시 계약은 [flow-display-quality-v1](../contracts/flow-display-quality-v1.md), 운영값을 선택/활성화하지 않는 안내는 [usage 설정](../flow-usage-configuration.md)이다.

실제 상세가 사용하는 SessionControls에 화면 내 확인/취소·동기 pending lock·fresh session/CSRF·URL/owner/report/generation·총15초 및 본문 공개 경계를 연결했다. 비활성 FlowActions/목록 컴포넌트는 새로 연결하지 않았고 로그아웃 의미도 유지한다. payload v1·원숫자·수급 계산/신호·CF014 fact/prompt·관측창·기존 저장 해석·Backend/DB/owner/tombstone·CF018 회계와 guard/worker는 바꾸지 않았다.

## 검사별 최종 직접 실행 결과 (2026-11-09 KST)

| 보호 입구 | 최종 결과 | 로그 이름 | 최종 로그 쓰기 시각 KST |
|---|---|---|---|
| Backend display-self | 3/3, exit0 | backend-self-3.log | 15:55:11 |
| Backend display-unit | 단일 파일54/54, guard0, exit0 | backend-unit-4.log | 16:09:14 |
| Frontend flow-review-unit | 표시36 + 삭제26 + 보호 tooling32 =94/94, exit0 | frontend-fetch-unit-1.log | 17:03:56 |
| Frontend flow-review-type | 대상5파일, 오류0, exit0 | frontend-fetch-type-1.log | 17:04:04 |
| Frontend flow-review-lint | 대상 제품/검사/fixture/입구, 오류0·경고0, exit0 | frontend-fetch-lint-1.log | 17:04:14 |

실제 명령은 clean env의 기존 절대 Python `-I -S .../backend/scripts/check_safe.py display-self/display-unit`, 검증된 절대 Node와 `OPENSSL_CONF=/dev/null .../frontend/scripts/check-local-ports.mjs flow-review-unit/type/lint`다. 자세한 절대 명령·전체 로그 SHA·source manifest는 저장소 밖 자기 checkpoint의 validation-evidence.json에 보존한다. 표의 시각은 로그 최종 쓰기 metadata이며 subprocess 내부 타이머와 구분한다. 각 보호 입구는 자기 임시 root 제거를 기록했다. Frontend 예상 부정 보호14건 외 예상 밖 위반/diagnostic 실패0이며 native 전체 관측은 아니다.

Backend는 exact AI17개와 고정 AST slice만 사용한다. 새 회귀가 실제 `_persistence_view`/`_headline`/일별 표시를 호출하여 1/19/20행 관측창, 확정 날짜·중복/역순/잘못된 날짜, 주체·단위, 누락 합 및 입력 불변을 확인했다. 기존 CF014 2개 회귀 함수의 4개 사례만 명시 호출하며 전체77개/PG는 반복하지 않았다. Frontend는 pure helper/VM 실행과 JSX/HTML source assertion을 포함한다. 15초를 실제 기다리지 않고 session 지연과 DELETE 진입 후 지연을 fake clock으로 각각 확인했다.

독립 source 검토의 헤더 raw 등락률, midpoint 반올림, 확인 시작 URL/epoch·늦은 오류, 검증 href 결합, blur/focus 복귀 경계를 보완했다. 서버 계정이 관측 이벤트 없이 변경되면 즉시 알 수 있다고 주장하지 않으며, 다음 blur/focus·visibility/page·대상/URL 이벤트와 삭제 직전 session 확인을 경계로 한다. 07:09 UTC 회차의 type 이후 변경은 당시 검사/fixture뿐이었으며 unit8/lint8에서 확인했다. 이후 focus/fetch 제품 변경은 위 최신 unit/type/lint로 별도 확인했다. Backend self 이후 entry/AI17 pin은 같고 추가 AST 회귀는 unit4에서 확인했다.

### 실패·수정 이력

첫 Backend mode 분기 오류로 기존 CF018 self2/unit57이 실행됐다. 신규 CF019 결과로 집계하지 않으며 CLI 분기를 고친 뒤 실제 display-self3/신규 단일 unit을 실행했다. 초기 Frontend type의 ES2017 BigInt literal 오류는 정확 반올림 로직의 BigInt 생성자 사용으로, lint의 React ref/effect·unused 오류는 layout effect/취소 가능한 microtask/cleanup으로 수정했다. 이후 관련 type/lint가 통과했다. unit7의 DELETE 지연 회귀는 고정 microtask 횟수 안에 fetch에 도달한다고 가정해 실패했으며, 실제 DELETE 진입 barrier를 기다리도록 검사만 수정한 unit8이 통과했다. 과거 로그는 보존하고 최종 통과와 구분한다.

### 당시 React 클릭 준비와 후속 재개 체크리스트

React fixture는 실제 설치 production 파일5개·같은 보호 unit worker·소유 loopback/nonce/PID/cwd·CSP·10분 이내 수명·finally 정리로 준비했다. 설치된5파일의 lock/version/hash metadata 확인과 fixture bundle 구문·제어 함수 VM 검사를 직접 수행했다. 제어 POST의 적용 중/완료 및 합성 account/status/authStatus/reportStatus/delay가 화면에 표시되도록 준비했고 오류 시 다음 조작을 막는다. 이것은 실제 React mount/클릭 증거가 아니다.

현재 도구의 Chrome extension/viewport/management 확인에서 새 격리 browser context 생성 API를 확인하지 못했다. 일반 프로필·쿠키를 쓰지 않았고 새 테스트 전용 프로필의 사용자 승인/지원 제어 경로는 아직 대기다. fixture 서버·브라우저 클릭은 실행0이다. 이는 권한 거절/OS/loopback 실패가 관측된 것이 아니라 준비 기능과 별도 승인 대기이며 다른 경로로 우회하지 않았다.

도구 제어 가능성이 후속 확보되고 재개가 승인된 경우에만 적용할 최소 체크리스트다. 현재는 실행하지 않는다. 먼저 capture 클릭 증가와 수정 후 초기 session/report GET·본문 표시부터 확인하고 실패하면 추가 사용자 클릭/환경 확장 없이 중단한다. 이후 실제 클릭 전의 고정 순서는 다음과 같다. 각 합성 control은 화면의 적용 완료를 기다리고 오류면 중단한다. counter는 누적값에서 각 단계 직전/후 차이를 읽으며 초기·복귀 재검증의 sessionGET/reportGET은 DELETE와 분리한다.

1. 계정 A·상태200/204에서 초기 sessionGET1/reportGET1과 본문을 확인한다. 표시 missing/zero/tiny/large/negative를 각각 보고 누락/저장0 한계·원부호·100%초과·기관 부분 범위를 확인한다. 표시는 API 호출을 추가하지 않는다.
2. 확인 열기→취소는 DELETE0, 삭제 확인 더블클릭은 fresh sessionGET1/DELETE1만 허용한다. 성공204는 보관함으로 이동한다. 매 사례는 합성 보고서를 복원하고 새로 조회하되 counter를 초기화하지 않는다.
3. DELETE404/401/403/500을 각각 적용해 fresh sessionGET1/DELETE1과 안전 안내·본문 비공개·새 GET 복구를 본다. session401/403은 sessionGET1/DELETE0이어야 한다.
4. delay16000에서 fresh sessionGET1 뒤 DELETE1이 진입한 것을 counter로 보고15초 timeout 안내를 확인한다. timeout은 서버 rollback이 아니며 뒤늦은204가 화면을 이동시키지 않아야 한다. 복구는 GET-only이며 DELETE 자동 재시도0이다.
5. delay250에서 DELETE 진입 후 대상/URL을 바꾸거나 창 blur/focus 후 복귀해 늦은 성공/오류가 새 화면에 적용되지 않는지 본다. 계정 B 제어는 서버만 바꾸므로 즉시 본문 숨김을 가정하지 않는다. 실제 창 이동/복귀 후 owner 재검증 또는 다음 삭제 전 session에서 DELETE0으로 닫히는지 확인한다.
6. 정확 자기 fixture 종료 후 listener/worker/root 정리·production dependency 후대조를 확인해야 한다. 현재 이 단계들을 실행 완료로 주장하지 않는다.

### 첫 브라우저 준비 실행과 오류 보존 보완

조정 측이 테스트 전용 로그인 없는 프로필 생성과 native 제어를 확인한 뒤 기존 보호 명령을1회 실행했다. 전달된 browser-run-1.log는 약10초 뒤 exit78 `CF019 worker readiness ownership mismatch`, workers0/exitRecords0/diagnosticFailures0 및 자기 임시 root 제거를 기록한다. fixture 주소를 연 실제 클릭은 없었다. 이전의 프로필 승인 대기는 해소됐지만 실제 UI 수용은 여전히 미완료다.

직접 source 대조로 runner가 worker task의 조기 실패를 무시하고10초 후 일반 readiness 오류로 덮는 문제를 확인했다. 보존된 첫 로그에 원 stderr/종료 이유가 없고 root도 정리돼 최초 worker 원인은 복원할 수 없다. 권한 거절이나 OS 차단으로 단정하지 않는다. 같은 허용 runner에서 조기 task 실패를 즉시 전달하고, 긴 종료 `ST001_SNAPSHOT` JSON이 실제 오류 요약을 가리지 않도록 bounded 실패 요약만 보완했다. 원 journal/보호 집계·OS policy/capability·nonce/PID/cwd/socket/소유 검사는 그대로다.

영향 검사만 실행했다. frontend-readiness-self-2.log는 보호 tooling30/30·exit0·예상 부정14건 외 위반0·자기 root 제거, frontend-readiness-lint-2.log는 오류/경고0·exit0·자기 root 제거다. 조기 실패 원 객체, 정상 조기 종료의 거부,100회 고정 대기, 기존 소유 검사, 긴 종료 JSON 뒤에도 실제 stderr 표시 및 cleanup을 합성으로 확인했다. 첫 영향 self도 exit78이었고 긴 계측 JSON이 실패 요약을 가려 정확한 assertion은 확인하지 못했다. 해당 로그를 보존했으며 source 검토에서 확인한 microtask 횟수 가정을 없애도록 조기 실패 사례의 pause를 미완료 Promise로 고정한 뒤 통과했다. 제품5파일/AI17은 이전과 같아 Backend54/Frontend 표시·삭제55/type를 반복하지 않았다. 이전 전체 FE83과 이번 tooling30은 실행 시점/범위가 다른 결과다.

두 번째 fixture 서버는 개발 측에서 시작하지 않았다. 조정 worker가 같은 보호 명령으로1회 실행해 실제 초기 오류 또는 readiness·클릭·정리 결과를 보존할 예정이다. 원인 해결/실제 클릭 성공을 아직 주장하지 않는다.

### 두 번째 브라우저 준비 실행의 정책 문법 오류와 최소 수정

조정 측의 browser-run-2.log에서 child65 `host must be * or localhost in network address`를 직접 읽었다. worker 시작 전에 생성 Seatbelt 정책의 `(local tcp "127.0.0.1:예약포트")`를 parser가 거부한 것이며 workers0·exit78·자기 root 제거다. 실행 접근의 권한 거절과 구분한다. 첫 로그의 누락된 stderr를 소급 복원했다고 하지는 않는다. 두 번째도 서버/페이지/실제 클릭은 시작되지 않았다.

같은 runner의 생성 규칙만 macOS의 특수 host `localhost:정확예약포트`로 수정했다. 로컬 Apple 기본 정책 `/System/Library/Sandbox/Profiles/com.apple.AssetCacheTetheratorService.sb`의 `localhost:62078` 사용례와 `/usr/share/sandbox/com.apple.CommCenter.sb`의 localhost network 필터를 읽기 확인했다. [일차 구현 문서](https://github.com/anthropics/sandbox-runtime#how-it-works)도 macOS Seatbelt의 specific localhost port 격리를 설명한다. policy의 localhost는 loopback용 표현이며 기존 JS guard의 허용 host127.0.0.1/::1/localhost·정확 cap 포트·고정 DNS 결과, fixture127.0.0.1 bind 및 socket 소유 검사는 유지했다. wildcard host/port·UDP·외부 연결·새 policy grant는 추가하지 않았다. 현재 생성 문자열 회귀가 실제 새 정책의 IPv4/IPv6 기동 시험을 대신하지는 않는다.

readiness 실패 시에는 등록된 자기 child를 중지한 뒤 원 command의 finally와 package 후검사 settlement를 기다리고 나서 source-copy root 정리로 진행하도록 보완했다. cleanup 실패는 계속 실패이며 첫 오류 및 별도 task 오류도 보존한다. 기존10분 fixture 수명/finally·nonce/PID/cwd/socket/guard는 그대로다.

직접 영향 검사는 frontend-policy-self-1.log의 tooling32/32·exit0 및 frontend-policy-lint-1.log의 오류/경고0·exit0이다. 예상 부정14건 외 보호 위반0이며 자기 root 제거를 확인했다. 정확 localhost TCP 포트 문자열·잘못된/중복/임의 포트 거절, owned stop→package 후검사→root 정리 순서·실패 보존을 합성으로 검사했다. 제품/Backend/AI/type/표시·삭제 unit은 변경이 없어 반복하지 않았다. 세 번째 fixture 실행은 조정 worker가 맡으며 개발 측 서버 실행은0이다.

### 세 번째 실제 준비/클릭 관측과 focus 재표본화

세 번째 조정 측 보호 실행은 nonce/PID/cwd/listener readiness를 통과했다. 전달받은 native UI 관측은 새 로그인 없는 테스트 프로필의 실제 React 화면·합성 계정 A 제어 적용 완료까지 확인했지만 sessionGET/reportGET/DELETE는 모두0, 본문은 숨김이었다. 재확인 클릭 시도와 콘솔 오류0 보고만으로 원인을 사용자 조작이나 document focus 상태로 단정하지 않는다. 기존 cached focused=false가 focus 이벤트를 놓쳤을 때 명시 재조회도 GET 없이 반환하는 경로는 source상 확인했지만 이번 실제0-call의 확정 원인은 아니다.

browser-run-3.log는 원래 기한으로 종료됐다. exit78/child1 `CF019 deadline: browser evidence incomplete`, worker1/exitRecords1, 원본 raw dispatch0·denial0·diagnosticFailure0·자기 root 제거다. 종료 버튼 조작은 승인 검토에서 실행 전 거절됐다는 전달을 받았고 실행/다른 중지 우회는 없었다. 자동 기한 정리와 수동 종료 성공을 구분한다. 새 테스트 프로필은 조정 측에서 유지 중이며 삭제 완료로 쓰지 않는다.

동일 허용 component에서 명시 observe/복귀가 실제 `document.hasFocus()`를 재표본화하고, await 이후/삭제 확인에도 실제 focus·visibility를 검사하도록 보완했다. 실제 false/hidden이면 GET·본문 공개0이며 클릭으로 focus를 true로 강제하지 않는다. 이벤트를 놓친 focus 상실 뒤에도 같은 identity/URL/generation인 요청만 본문을 숨기고 pending을 해제해 다음 GET-only 재확인이 가능하다. 기존 owner/session/report/URL/generation·삭제 의도 무효화는 유지했다. fixture에만 현재 hasFocus/visibility와 실제 재확인 버튼의 capture 클릭 횟수를 읽기 전용으로 표시한다. 제품 상시 진단·실제 ID/계정/CSRF/nonce 출력은 추가하지 않았다.

최종 직접 영향 검사는 frontend-focus-unit-2.log의 표시36/삭제24/tooling32=92통과, frontend-focus-type-2.log 오류0 및 frontend-focus-lint-2.log 오류/경고0, 모두 exit0·자기 root 제거다. 로그 최종 쓰기 시각은 각각2026-11-09 16:55:14/16:55:22/16:55:31 KST다. 실제 observe callback을 추출한 VM에서 cached false/actual true의 두 GET 복구, actual false/hidden의 GET0, await 중 실제 focus 변경 뒤 본문 비공개·pending 해제를 확인했다. 이는 실제 React 클릭 시험과 구분한다. Backend/AI/PG는 변경이 없어 반복하지 않았다.

독립 source 및 위 로그 읽기 검토에서 보호 완화 없음과 결과 일치가 확인됐다. 이 제품/fixture/runner를 고정해 네 번째 실행을 조정 측이 맡는다. 개발 측 서버 실행은0이며 실제 focus label/capture/GET 및 종료·정리 결과를 받은 뒤 이 기록을 갱신한다. 현재 실제 삭제 확인/취소·오류·늦은 응답·표시 대표값 클릭 수용은 미완료다.

### 네 번째 실행 중 source 검토와 fetch receiver 보완

조정 측 전달에서 초기 fixture label은 hasFocus=true/visibility=visible인데 sessionGET/reportGET/DELETE0 및 안전 unavailable 안내가 관측됐다. 따라서 단순 실제 focus=false로 원인을 확정하지 않는다. 앞선 재확인 capture 관측은0이었으나 이후 창 닫기 과정의 관측에서는 hasFocus=false/visibility=visible, recheckClicks1, sessionGET/reportGET/DELETE0이었다. 정확 클릭 시점과 주체는 미확인이다. capture 클릭이 전혀 없었다고 하거나 사용자 조작 실수로 단정하지 않는다. 최종 browser-run-4.log는 자동 기한 exit78/child1과 자기 root 제거를 확인했으며 완료 로그 해시에 포함한다. 이는 수정 전 source copy의 관측이고 아래 fetch 수정의 실제 브라우저 재검증은 아니다.

source 검토로 ReportIntent가 기본 native fetch를 저장한 뒤 `this.fetcher(...)`로 호출해 receiver를 ReportIntent로 바꾸는 결함을 확인했다. fixture의 canonical UUID/경로/returnTo에서는 불일치를 찾지 못했다. 이 receiver 결함이 실제 브라우저의 정확 예외였는지는 아직 미관측이다. 같은 helper 생성자에서 전달받은 fetch를 globalThis에 한 번 bind했다. owner/session/report/CSRF/URL/generation·15초 timeout·안전 오류 문구는 변경하지 않았고 원 오류를 제품에 노출하지 않는다. active fixture는 기존 고정 source copy를 계속 사용하며 개발 측 서버/브라우저 실행은0이다.

기본 `new ReportIntent()` 및 주입 경로를 receiver-sensitive 일반 함수의 VM global fetch로 확인했다. 잘못된 receiver는 transport 계수 증가 전에 거절됨을 먼저 확인하고, 올바른 receiver에서 session/report GET 및 fresh session+DELETE가 no-store/CSRF와 함께 수행됨을 검증했다. 이는 Node의 receiver 무관 fetch/화살표 fake만 쓰던 검사의 빈틈을 보완한 것이며 실제 Chrome 재실행 증거는 아니다.

직접 영향 결과는 frontend-fetch-unit-1.log의 표시36/삭제26/tooling32=94통과, frontend-fetch-type-1.log 오류0, frontend-fetch-lint-1.log 오류/경고0, 모두 exit0·자기 root 제거다. runner/fixture/component·AI/Backend는 이 변경에서 같고 기존 Backend/PG는 반복하지 않았다. 현재 판단은 source 결함 수정 완료·실제 초기 GET/전체 클릭 수용은 별도 대기다.

### 여섯 번째 사용자 수동 기본 흐름 검증

새 로그인 없는 CF019 테스트 프로필/새 합성 URL의 실제 사용자 화면에서 합성 표시 종목000000·원형 게이지·보고서 본문을 확인했다. 조정 측이 읽은 서버 누적값은 sessionGET6/reportGET5/DELETE0이었다. 이후 사용자는 삭제 버튼→확인창 문구→취소 순서가 정상이라고 명시했고 같은 시점 서버는 sessionGET8/reportGET7/DELETE0이었다. 확인창과 취소는 실제 수동 UI 확인 및 DELETE 증가0으로 통과다.

이어 사용자가 성공을 알리며 합성 보관함/204 navigation target 화면을 보냈고 조정 측의 누적 서버값은 sessionGET10/reportGET8/DELETE1이었다. 단일 삭제 확인과204 보관함 이동은 수동 UI 및 정확 DELETE1로 확인했다. GET 수치는 복귀/재확인 등을 포함한 누적값이며 각 사용자 동작의 정확 GET 횟수나 더블클릭 방지를 별도 검증했다고 해석하지 않는다. 기본 fetch receiver 수정 후 실제 GET/본문 경로가 동작한 증거이며 VM/단위검사와 구분한다.

삭제 후 뒤로가기의 gone/404 화면은 현재 근거로 미확인이다. 조정 측의 마지막 진단 요청은 이미 기한 종료된 서버에 연결되지 않아 connection refused/status000이었으며404 응답이 아니다. 진단 GET은 서버에서 실행되지 않았고 카운터 추가도 없다. 이 결과로 삭제 후 재접근/404 성공을 주장하지 않는다.

browser-run-6.log는 원래 기한으로 exit78/child1 `CF019 deadline: browser evidence incomplete`, workers1/exitRecords1/partial0·원본 raw dispatch0·denial0·diagnosticFailures0·자기 임시 root 제거를 기록했다. UI 성공은 조정 측이 전달한 사용자 첨부/명시 응답과 서버 카운터의 별도 증거이며 이 deadline 로그가 해당 클릭들을 직접 기록한 것은 아니다. 완료 로그와 수동 관측의 출처를 checkpoint에서 따로 묶었다. 기존 실행/실패 로그는 보존한다.

현재 기본 본문·확인·취소·단일 삭제/이동만 수용했다. 확인 더블클릭, 표시 대표값 전수, DELETE404/401/403/500·session401/403, 실제15초 timeout, 늦은 응답, 계정 B/창 복귀/대상·URL 변경과 공개 경계의 실제 UI 수용은 아직 미실행이다. 이 문서 보정에서 제품 코드/검사/Git/서버/브라우저 추가 실행은 없다.

### 일곱 번째 재접근 준비의 origin 오안내와 남은 임시 root

08:52 UTC경 새 보호 fixture를 시작했으나 조정 측이 localhost URL을 잘못 안내했다. fixture의 정확 origin은127.0.0.1이므로 DELETE가403으로 counter 증가 전에 차단됐다. 조정 측은08:59:24 읽기 요청에서 Origin localhost403 대127.0.0.1 200을 직접 재현했다.08:59:52 마지막 누적값은 sessionGET16/reportGET7/DELETE0이며 이 중 직접 진단의 sessionGET2/reportGET1을 포함한다. 사용자 동작만의 GET 횟수나 단일 삭제 성공으로 해석하지 않는다. 제품 source·exact origin·보호 정책은 변경하지 않았다.

Mac 연결이 끊겨 결과를 확인하지 못했다가10:57 UTC 재연결 뒤 browser-run7.log를 확인했다. 로그는 READY 뒤 `SAFE_CHECK_BLOCKED: Owned group cleanup incomplete; root retained`로 끝난다. 정상 종료/전체 정리 성공이 아니다. 독립 검토는 해당 PID93266·동일 process group·60792 listener가 없음을 확인했으나 소유 임시 root는 owner501/0700·관련 파일0600 상태로 남아 있었다. 기존 log와 root를 삭제/이동하지 않았으며 원본과 실패 이력을 보존한다. 정확 경로와 독립 검토 출처는 저장소 밖 checkpoint에 기록한다.

### 여덟 번째 삭제 후 뒤로가기·404 재조회

사용자 준비 확인 뒤11:00:17 UTC경 같은 제품/fixture/runner source로 새 보호 fixture를 시작하고 정확127.0.0.1 origin의 새 URL을 안내했다. 사용자가 직접 삭제와 뒤로가기를 수행했다. 첫 첨부의 OCR은 합성 보관함/204 navigation target, 두 번째 첨부는 sessionGET5/reportGET2/DELETE1, hasFocus=true/visibility=visible/recheckClicks0과 `이미 없거나 접근할 수 없는 결과입니다. 이번 삭제의 성공을 확인한 것은 아닙니다.` 안내 및 본문 부재를 확인했다. 사용자 첨부/OCR 전달과 이 기록 작성자의 직접 브라우저 실행을 구분한다.

조정 측은11:01:45 누적 counter5/2/1을 직접 확인한 뒤 같은 보고서 GET의 HTTP404를 확인했고 진단 후에는5/3/1이었다. 마지막 reportGET 증가는 조정 측 직접 진단1회이며 사용자 클릭 추가 성공으로 집계하지 않는다. 따라서 run6의 본문/확인/취소/단일삭제·204 이동에 더해 run8의 삭제 후 뒤로가기 gone 안내·본문 비공개 및 같은 결과 직접404 재조회가 통과했다. 안내 문구 자체는 이번 삭제 성공을 단정하지 않으며 그 앞선204 이동과 DELETE1을 별도 근거로 사용한다. run6 만료 뒤 status000은 여전히404 증거가 아니고 이번 run8의 실제404와 구분한다.

run8은 사용자에게 종료 클릭을 요청한 뒤 종료 버튼 직후 화면이 바뀌지 않는다는 문의가 있었다. 소스상 버튼은 종료 fetch만 수행하며 화면 전환을 제공하지 않는다.11:05 UTC경 조정 측 읽기 관측에서는 listener가 없고 PID97066에 기존 ESTABLISHED 연결1개가 남아 종료 callback을 기다렸다. 해당 테스트 탭만 닫도록 안내한 뒤 정상 종료를 받았지만 사용자가 실제 탭을 닫았다는 명시 회신은 없으므로 원인으로 확정하지 않는다.

최종 browser-run8.log는 CF019_FIXTURE_CLOSED의 누적 sessionGET7/reportGET5/DELETE1, workers1/exitRecords1/partial0·원본 raw dispatch0·denial0·diagnosticFailures0·자기 root 제거와 package pre/post 확인을 기록했다. 조정 측 세션의 process exit0 및11:07:06 UTC 직접 root 부재 확인을 별도로 전달받았다. 이는 기한 timeout이 아니라 종료 요청 후 기존 연결 대기를 거친 정상 종료다. source 검토상 server.close callback 뒤 finally closeAllConnections 순서에서 기존 연결이 callback을 지연할 수 있다. 이번 기본 검증을 무효화하지 않지만 fixture 자립 종료 편의성의 제한으로 남기며 코드 변경이나 추가 사용자 검증을 하지 않았다.

기본 사용자 흐름의 이 추가 확인을 전체 고급 UI나 실제 NextSSR/BFF/BackendPG/providers/OAuth 통합 수용으로 확대하지 않는다. 이번 증거 보정에서 제품/검사/Git/서버/브라우저 추가 실행은 없다.

## 인계와 미검증

08:14 UTC 읽기 Git 상태 기록은 exact22·범위 밖0·staged0이며 branch `fix/flow-display-delete-ux`, HEAD/develop/origin/develop 및 읽기 원격 develop는 base `67bb1e143cb9c59579ca20a184369a845111bbdb`다. worktree1개이고 원격 작업 branch는 아직 없다. 사용자 변경을 정리/폐기하지 않았다. 착수 시 branch 준비/fetch 이후 이번 최종 인계 준비에서는 fetch 및 게시용 add/commit/push/PR/Ready/merge를 실행하지 않았다. AI17/기존14 pin·기존 guard/bootstrap/safe-http와 제품 원 payload/Backend/DB/회계는 유지했다.

체크포인트의 source22 manifest·NUL pathspec·완료 로그 SHA·검증 명령/시간과 단계별 사용자 터미널 명령을 준비한다. 지금 사용자에게 Git 실행을 요청하지 않는다. Draft용 검토/정확 stage/commit/committed-tree 검증/push/원격 HEAD 확인 명령과 Ready/merge 조건을 분리한다. **현 브라우저 수용 미완료 상태에서 Ready/merge 단계는 실행 대상이 아니다.** 원격 최신 PR head 및 Ready 이후 새 CI 성공은 사용자 게시 후 별도 확인해야 한다. Backend CI를 Frontend/실제 브라우저 검증으로 확대하지 않는다.

이번 source22 bytes/hash는 직접 대조했다. staged0·제품 hash 불변의 최근 상태는 조정 측/독립 검토 전달이며 이 문서 작성자가 Git을 재실행한 결과가 아니다. 원본08:14 UTC 읽기 Git 상태 파일은 그대로 보존한다. run6 기본 UI와 run8 재접근/404 성공, run7 origin 오안내 실패·임시 root 잔존, 로그인 없는 프로필 자료 유지를 따로 기록했다. 완료/실패 로그53개와 수동 관측 출처를 구분해 묶었으며 UI 통과가 runner 정리 성공을 대신하지 않는다. 간결한 exact22 literal 경로 stage·commit·push/Draft 명령과 긴 검증 보조본을 저장소 밖 checkpoint에 제공한다. 현재 Git 쓰기는 실행하지 않았고 사용자 검토/선택 뒤 각 단계 오류 없이 통과할 때만 진행한다. Ready/merge와 고급 UI·통합 수용은 보류다. 만료된 localhost URL을 재사용하지 않고 비밀·기존 DB·운영 활성화/재기동/migration·설치를 수행하지 않았다.

<!-- CF019_PR_BODY_START -->
## 변경

Flow 표·게이지·헤더의 누락/저장0/작은 비영값·underflow·기관 부분 범위·강도 단위를 구분하고, 활성 상세의 삭제 확인/취소·fresh session/CSRF·pending·대상/계정/URL/generation·focus 재검증과 기본 fetch receiver를 보완합니다. payload/원숫자/해석·Backend/DB/회계와 보호 경계는 유지합니다.

## 검증과 미완료

- 기존 Backend self3/unit54, Frontend94(표시36/삭제26/보호32), 대상 type0·lint 오류/경고0이 통과했습니다. 이번 기록 보정에서 제품 검사는 반복하지 않았습니다.
- run6 수동 UI와 별도 서버 관측으로 본문, 삭제 확인창→취소 DELETE0, 확인1회 DELETE1/204 보관함 이동을 확인했습니다. run8 정확127.0.0.1 origin에서 삭제 뒤 뒤로가기 gone 안내·본문 비공개와 직접 HTTP404 재조회도 확인했습니다. 진단 GET은 사용자 동작과 분리합니다.
- run7은 조정 측 localhost URL 오안내로 고정 origin과 불일치해403/DELETE0이었습니다. 연결 복구 후 PID/process group/listener 부재는 확인했지만 정리 실패로 해당 임시 root가 남았고 삭제/이동하지 않았습니다. 제품의 고정 origin을 완화하지 않았습니다.
- run8은 종료 요청 후 기존 연결 대기를 거쳐 정상 exit0/CF019_FIXTURE_CLOSED·자기 root 제거를 확인했습니다. 종료 버튼만으로 즉시 종료되거나 탭닫기가 원인이었다고 확정하지 않습니다. fixture 자립 종료 편의성 제한을 남깁니다. 로그인 없는 테스트 프로필 자료는 유지하며 영구 삭제하지 않았습니다. 이전 실패·정리 로그와 source snapshot을 보존합니다.
- 표시 대표값 전수·더블클릭·고급 오류/timeout/늦은 응답·owner/URL 등 실제 UI와 NextSSR/BFF/BackendPG/providers/OAuth 통합은 미완료입니다. 전체 CF-019 수용/merge-ready가 아니며 Draft 검토와 Ready/merge를 구분합니다.

세부 기록: `docs/work/CF-019-flow-quality-delete-ux.md`.
<!-- CF019_PR_BODY_END -->
