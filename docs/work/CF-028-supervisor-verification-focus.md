# CF-028 · Supervisor GET 재확인과 계획 포커스

상태: v1.1 정확8파일 구현·보호 집중 검사 완료, 코드/테스트 동결. 독립 최종 검토와 실제 mounted/1440/390/키보드 수용은 별도 조율 측 실행 전이며 완료로 주장하지 않는다.

## 기준과 범위

- base/HEAD: `6e9e625ed18a9a6b48cd06012e662d703aaf1de7`, branch `fix/supervisor-verification-focus`의 새 전용 worktree. 시작 시 clean과 원격 develop 일치, 재현 commit의 대상 source 일치를 확인했다.
- 정본 v1.0 SHA256: `6b903e38991692fbf90d75f969da911f18e36926cbf1b4ed169efab75f4f961e`. 초기 범위는 component2·fixture·core unit·design·이 worklog의6파일이다.
- 새 worktree는 기존 caller가 허용한 sibling source root와 달라 검사 준비가 정적으로 불충족했다. 검사를 실행/우회하지 않고 보고했다. 이후 정본 v1.1 SHA256 `9cc750bb682690386da2151346d3b1d5b619e15b819f214b24862ac9fd14efed`를 읽고 caller/tooling 회귀2파일만 추가했다. exact core/verification sibling과 유일한 기존 dependency/metadata 관계를 유지하며 임의 sibling/유사 prefix·다른 workspace/dependency·비정규 alias·target 불일치·untrusted uid/mode를 거절한다. 기존 package/lock/source/owned manifest drift·postcheck와 worker 원본 내용 거절 회귀도 유지했다.
- 기존 Technical/CF027/CF026 worktree와 private 자료는 입력/변경하지 않는다. Backend/AI/DB/키/provider·브라우저 서버·Git 게시 작업은 이번 개발 측에서 실행하지 않는다.

## 구현과 증거 수준

GET verification token의 동기 선점, 같은 token settlement, invalidation abort, 정상/오류 pending·disabled, 경쟁 handler 차단을 추가했다. 원래 owner 전후 확인·상위 재인증 latch·15초 deadline·fixed key/body·유한 관측 의미를 보존한다. 다음 자동 관측 predicate는 이미 정산된 GET token과 분리한다.

명시 prepare의 새 plan만 origin·generation/owner/URL에 결합하고 실제 사용자 이동/이탈 시 무효화한다. 자기 pending render가 disabled/제거한 origin의 body 이동을 별도 기록한다. commit 뒤 현재 private context/실제 focus/plan identity를 재검사하고 heading에 한 번만 focus하며 GET/rerender는 이동시키지 않는다. 불명한 focus 자격은 보수적으로 유지한다.

추가 unit은 실제 production class/verify/command/commit closure를 AST로 추출하여 실행한다. session/core HTTP·DOM·timer IO 일부는 주입이며 React mount/lifecycle나 실제 키보드 성공이 아니다. DOM prop/handler 연결 source assertion도 별도다. fixture는 production Session/ChatView/CSS를 그대로 제공하고 get-verification/plan-focus의 bounded 관측과 비민감 DOM focus label만 추가했다.

## 검사와 미실행

아래 최종 검사 전에 제품/fixture/caller/core/tooling source를 고정했다. 검사 후에는 design/worklog와 private 인계 자료만 갱신했으며 검사 입력 bytes는 그대로다. 준비 상태를 통과로 집계하지 않는다. 기존 guard SHA256 `3a9cb45bc865d560612ccd5876f060c69aa0abe5ff635576888781d9efe7d3ee`, package `5dcc4949fad70a41d4c4fe5639f63931fcaf99accd3019a53052c00a4e697ef5`, lock `bb3a6a2b6c2e6374a4fa43ab8d3022ea678b0e60a003ff2b2aafb5610a7c7fed`를 읽어 대조했다. 새 설치/guard 완화/raw 검사·전체 build/Backend·PG는 실행하지 않는다.

실제 mounted·1440/390×844·Tab/Space·긴 오류·늦은 응답/뒤로가기 수용은 조율 측이 최종 동결 source와 기존 전용 미로그인 테스트 프로필에서 수행할 예정이다. 실제 Backend/auth/PG/provider 수용과 구분한다.

## 동결 뒤 브라우저 인계 시나리오

1. 부모의 exact emitted origin만 연다. stored 결과와200을 준비하고 baseline을 수집한다. get-verification arm → session hold_next → 제품 GET 재확인. 첫 hold 시 session+1/outcome+0, pending/disabled를 확인한다. 중복 클릭은 추가 request/abort0이어야 한다. 15초 자동 해제 전에만 release하고30초 안에 collect한다. 정상 settlement는 보통 session+3/outcome+1, POST0이다.
2. 합성503 뒤 명시 GET 재시도에서도 pending/disabled와 중복0을 확인한다.200 복구 성공은 stale 오류를 지워야 한다.401은 상위 latch/private 숨김이고 자동 반복이 없어야 한다. timeout/hide/URL/back은 현재 요청을 무효화해야 한다.
3. plan-focus arm → 명시 키보드 제출/typed 답변/후보를 확인한다. 유효 origin이면 heading1회 및 다음 Tab 첫 실제 plan control, 사용자 Tab/pointer 이동이면 현재 focus 보존을 확인한다. GET/동일 plan/rerender는 focus0이다. 동의와 실행은 명시 입력만 허용한다.
4. completed/cancelled와 UI 수용을 구분한다. fixture 완료 또는 취소 버튼의 strict ACK와 부모 settlement·source/dependency postcheck·자기 listener/child/root 정리를 확인한다. 잘못된 release409·실패/parent78은 통과로 바꾸지 않는다.

정확 보호 시작 명령·최종8경로 source manifest·로그/정리 근거는 별도 private checkpoint에 확정했다. 개발 측은 브라우저 서버를 중복 시작하지 않는다. 원격 게시 전 독립 검토를 기다리며 Git stage/commit/push/PR/Ready/merge는 아직 실행하지 않는다.


## 최종 직접 보호 검사 · 2026-11-10 UTC

검증한 절대 Node는 `22.7.0`, SHA256 `8ed7a1f99faeec4afa90a507905b4ca4b9b7494e1d49f73e6ee514edde54f26f`다. package/lock과 설치된 TypeScript5.9.3·Next16.2.10·React/ReactDOM19.2.4·scheduler0.27.0의 공개 metadata/소유·mode·nlink를 대조한 뒤 새 worktree의 frontend/node_modules에 정확 dependency alias 하나만 만들었다. 설치/사본·기존 dependency 변경은 없다. 공식 require_escalated 심사로 기존 보호 입구를 실행했으며 OS/FS/network/env/worker 정책은 불변이다.

각 명령은 전용 worktree root에서 `/usr/bin/env -i OPENSSL_CONF=/dev/null /opt/homebrew/Cellar/node/22.7.0/bin/node frontend/scripts/check-local-ports.mjs <mode>`다. 아래 시각은 로그 생성/마지막 기록의 파일시스템 UTC 시각이다.

| mode / 로그 | 시각 UTC | 최종 결과 | 로그 SHA256 |
|---|---|---|---|
| core-unit / core-unit-3.log | 16:17:48–16:17:51 | 150통과 = core80+BFF14+config6+tooling50, fail/cancel/skip0, parent exit0 | `456bee6146b86d5379a36eeeb8f9356adb84590818997b86335a91c824bc0928` |
| core-type / core-type-2.log | 16:17:46–16:17:48 | 오류0, parent exit0 | `68bf502de2edd289af61785f07a2c44f67d2d6049dc73bc4ff042411b160b733` |
| core-lint / core-lint-2.log | 16:17:48–16:17:50 | 오류/경고0, CF019_LINT [], parent exit0 | `9235a9b805928a68e788e9855bfb00775305d7986a59b6c6c66942e28aaf7a07` |

core-lint가 변경 fixture/caller/core unit/tooling을 이미 포함하므로 별도 fixture-lint를 중복 실행하지 않았다. core-unit의 실제 provenance는 codeRootKind=verith-supervisor-verification, split=true, workerPackageOwned=true와 입력 manifest SHA256 `6fc3ec889fc522d0e235e1cea1a26925866ea3cf414e71716c617d95cbd05c02`를 기록했다. unit workers/exitRecords4/4, type와lint 각각1/1, partial/diagnosticFailure0, 예상 밖 violation0이다. tooling의 거절16개는 expected negative16개이며 보호 제거가 아니다. original raw dispatch0 관측은 instrumented JS FS 범위이며 native 전체 읽기 부재 증명으로 확대하지 않는다. 세 검사 모두 owned temporary root removed를 기록했다. 앱 listener나 브라우저 fixture는 시작하지 않았다.

### 실패·수정 이력

- core-unit-1은 core79 중78통과/1실패, child1/parent78로 중단했고 guard 위반0·자기 root 정리였다. caller의 실패 출력이 뒤쪽만 남겨 개별 assertion 원문은 보존되지 않았다. 추가 회귀의 추출 VM에서 performance 입력이 생성 후 설정돼 전달되지 않는 정적 오류를 확인해 입력을 생성 시 주입했다. 제품 보호를 바꾸지 않았다. 이후 core-unit-2는149통과였다.
- 첫 type는 오류0, 첫 lint는 오류0/새 hook 경고3개였다. callback props를 분리하고 effect가 소유하는 focusIntent를 캡처해 경고를 해소했다.
- 독립 중간 source 검토에서 deleted 결과의 pending status가 private content 분기 안에 있는 누락을 확인했다. 공통 polite thread로 이동하고 실제 ChatView JSX를 주입 hooks/JSX runtime으로 실행하는 정상/deleted 회귀를 추가했다. 이 시험은 React mount가 아니다. 최종 unit150/type/lint는 이 수정 뒤의 동일 입력이다.

동기 잠금·timeout·stale finally·경쟁 handler·자동 관측 predicate·focus intent/실제 commit callback은 production class/closure를 추출하여 검사했다. UI disabled/heading Tab 순서·실제 DOM focus·사용자 이동·1440/390 수용은 이 결과에 포함되지 않는다. 원래 회계/key/DB/AI/Backend/CI·보안 gate는 수정하지 않았다. provider/키/.env/DB 실행0, Git 게시0이다.

## 화면 담당에게 넘길 보호 절차

개발 측은 서버를 열지 않았다. 화면 담당이 동결 manifest를 대조한 뒤 위 clean-env/절대 Node 명령의 mode만 `core-browser`로 지정한다. 부모가 내보낸 `CF025_FIXTURE_URL`의 exact origin/readiness만 확인하고 기존 전용 테스트 프로필에서 연다. nonce·실행 PID·포트·원시 receipt는 공개 문서에 복사하지 않는다. hold_next가 실제 held인 경우만15초 이내 release하며 자동 해제 후 다시 보내지 않는다.30초 안에 관측 수집, 시나리오 종료 후 fixture 완료/취소 버튼으로 자기 lifecycle만 끝낸다. 정상/취소 ACK·영수증·parent settlement·source/dependency postcheck와 자기 listener/등록 child/root 제거를 함께 확인한다. completed는 그 자체로 UI 수용이 아니며 cancelled/실패는 전체 통과가 아니다. 새 source 수정이 필요하면 기존 브라우저 회차를 종료·정리하고 새 동결 이후 실행한다.


## 추가 진단 동결 · 실제 focus 실패와 분리

조율 측이 이전 동결 source의 실제 Chrome 회차를 전달했다.390 회차는 native Return 뒤 계획 채택/heading 관측0 및 제한시간 실패였고, 이후1440×844는 textarea→Tab→질문 확인의 native focus→Return 뒤 계획을 채택했으나 heading 관측0·다음 Tab이 취소로 향했다. 후자는 completed receipt/parent0·정리였지만 focus 수용은 실패다. AX HTML root와 기존 focusin 기반 stale label만으로 DOM activeElement를 단정할 수 없다. 개발 측의 직접 브라우저 실행은 없으며 이 전달을 전체 UI 성공으로 바꾸지 않는다.

승인된 fixture/core unit/design/worklog만 추가 보완했다. pending 및 새 plan DOM commit 때 activeElement tag/disabled/connected·실제 hasFocus/visibility를 기록하고 focusin/window blur/focus를 관측한다. 최근 snapshot8개·각 event count32 상한이며 원문/owner/token/credential·입력 value를 읽거나 출력하지 않는다. observer는 aria-busy/childList의 변화만 관측하고 cleanup한다. 같은 상태의 자체 label rerender는 다시 표본화하지 않는다. focus를 강제하거나 HTML/body 허용 조건을 넓히지 않았다.

기존 status 제어에 deleted 한 값만 추가했다. 응답은 plan/effective_scope/flow=null, views=[], coverage=deleted로 기존 production outcomeValue를 그대로 통과하며 삭제된 알려진 ID의 pending 관측에 쓴다. 실제 DB 삭제나 production route 변경이 아니다.

직접 보호 core-unit-diagnostic-1은152통과(core82+BFF14+config6+tooling50), core-lint-diagnostic-1은오류/경고0, 둘 모두 parent0·소유 root 정리·예상 밖 guard 위반0이다. type는 직전 core-type-2 결과를 유지하며 production TS 두 파일 bytes가 동일함을 확인했다. 추가 회귀는 실제 fixture DOM observer 함수를 합성 IO로 실행하는 bounded/cleanup/privacy 시험과 고정 deleted 응답의 실제 production validator 시험이다. React mount/키보드 성공으로 집계하지 않는다. 화면 담당은 새 동결 manifest로 짧게 재현하며 그 회차 동안 추가 source 변경은 하지 않는다.

- core-unit-diagnostic-1.log SHA256 `237577960c6481123d868498c08ef2b0aeb9f84ae29df7cade9f50a8cf816b4f`
- core-lint-diagnostic-1.log SHA256 `9235a9b805928a68e788e9855bfb00775305d7986a59b6c6c66942e28aaf7a07`


## 늦은 BODY blur의 근거 기반 수정

조율 측의 진단 source1440 회차는 정상 completed receipt/parent0·정리였다. 관측은 pending-commit BUTTON disabled=true/connected=true/hasFocus=true → pending-commit BODY → plan-commit BODY, 모두 visible이며 focusin3/windowFocus0/windowBlur0였다. 뒤 H2 focus가 없고 다음 Tab은 취소였다. 이는 실제 DOM 표본이며 과거 AX HTML root와 구분한다. 개발 측의 직접 화면 실행은 아니다.

기존 pendingCommit은 그 순간 current=BODY인 경우만 기록했다. native blur가 commit보다 늦고 focusin 없이 발생해 final render에서 origin이 다시 enabled이면 consume이 거절되는 소스 경로를 확인했다. 최소 수정으로 pending commit에서 origin의 disabled/removed 상태가 실제 관측되고 current가 origin 또는 BODY일 때만 같은 의도의 BODY 근거를 보존한다. HTML/unconditional autofocus는 추가하지 않았다. 실제사용자 이동/이탈·context 검증과 한 번 소비는 그대로다.

production PlanFocusIntent의 disabled origin pendingCommit → connected origin 재활성화 + silent BODY → consume1회 성공, 중간 invalidate false, HTML false, enabled origin의 근거 없는 BODY false 회귀를 추가했다. 최종 보호 core-unit-late-blur-1은153통과(core83+BFF14+config6+tooling50), core-type-late-blur-1은오류0, core-lint-late-blur-1은오류/경고0, parent모두0·자기root정리·예상밖guard위반0이다. 이 source로 다시 동결하며 수정 후 실제 키보드·deleted/GET 수용은 아직 별도 미검증이다.


## 고정 fixture-owned mounted GET case 준비

조율 측의 후속 실제 회차에서1440/390 native Return→heading→첫 실제 control,390 waiver→부분→최종 동의→활성 Flow 버튼의 Tab/Space,250ms 지연 중 사용자 Tab 이동의 no-steal이 completed receipt/parent0·정리로 통과했다. confirmPOST는0이다. 별도 GET 회차는 pending·GET/새 요청 disabled와 반복 Return의 session+1/core+0을 관측했으나 CUA 왕복 지연으로30초 collect를 넘겼다. 이 회차는 실패이며 GET 전체 수용으로 세지 않는다. 개발 측의 직접 화면 관측은 아니며 활성 fixture는 정리됐다는 전달 뒤 보완했다.

기존 fixture/core unit/design/worklog4파일만 보완했다. stored GET·실제503 오류 뒤200 명시 retry·실제 deleted GET 뒤 재확인의 고정3case를 추가했다. 보호 helper/runner/endpoint/guard·production components는 바꾸지 않았다. visible production GET 버튼을 고정 class/text로 정확1개 찾고 모호하면 실패한다. 기존 실제 confirmation의 소유 binding과 known-ID/저장 report link·합성 stored/HTTP200/auth200/지연0/hold 없음이 선행 조건이다. storage/ID 생성이나 component callback 직접 호출은 없다.

각 case는 동기 fixture lock으로 시작해 실행 중 다른 fixture control을 잠근다.20초 전체 deadline, poll80/read100 상한,50ms 유한 대기와 signal/unmount 정리를 둔다. 기존 nonce controls·failure watch·30초 scenario/15초 one-shot hold/590초 fixture/600초 worker는 그대로다. 고정 상태/baseline → hold_next → 실제 버튼 DOM click → held/pending/disabled 확인 → disabled DOM click → 추가 session/core0 → fresh held 확인과 클릭 후3초 안 release1회 → settlement/error 해제 → collect를 수행한다. hold 불명·만료면 release 재전송하지 않고 실패하며 기존 failed receipt/cleanup으로 이어간다. 성공 retry는 session+3/core+1·POST/DELETE0을 검사한다.503 priming은 실제 error UI와 session+2/core+1, deleted priming은 실제 production validator/표시를 통과해야 한다.

직접 보호 core-unit-mounted-cases-1은163통과(core93+BFF14+config6+tooling50), core-lint-mounted-cases-1은오류/경고0, parent둘다0·owned root 제거·예상밖 guard위반0이다. type는 직전 core-type-late-blur-1 결과를 유지하며 관련 production TS bytes가 같음을 확인했다. 새로운 unit은 실제 fixed helper를 주입 DOM/HTTP 모델로 실행해3case의 절차·모호 selector·추가POST·hold 소실/만료·deadline/cancel·소유 confirmation 선행 조건을 확인한다. 이는 React mount/실제 DOM 수용이 아니며 준비된 programmatic mounted case의 실제 브라우저 실행도 아직 미실행이다. source wiring과 기존 동기 handler 검사는 별도다.

### 화면 담당 실행 순서

새 동결 source/manifest를 확인하고 기존 clean-env 절대 Node entry의 mode core-browser를 사용한다. 개발 측은 서버를 시작하지 않았다. exact emitted origin을 기존 전용 테스트 프로필에서 열고 failure-watch registered를 확인한다. 합성 stored·HTTP200·sessionHTTP200·지연0을 설정하고 실제 UI로 질문 준비→필요한 명시 동의→확정→저장 report link와 known-ID 대화까지 도달한다. 원래 storage/key/ID를 임의로 만들지 않는다.

1. **고정 mounted GET · stored**만 누른다. 별도 arm/hold/release/collect 클릭은 하지 않는다. helper가20초 안에 phase 기록과 collected-programmatic-mounted까지 진행해야 한다.
2. 같은 저장 대화에서 **고정 mounted GET · error-retry**를 누른다. helper가503 실제 오류→200 명시 DOM retry→hold/중복 억제/해제를 수집한다.
3. **고정 mounted GET · deleted**를 누른다. 실제 GET으로 삭제 표시를 먼저 받고 다음 재확인을 수집한다. 삭제 뒤 새 stored case를 바로 누르지 않는다.

각 case는 별도의30초 scenario이며 성공 뒤 버튼이 재활성화되고 기록에는 phase·pending/disabled booleans·counter delta만 남는다. ID/원문/storage/token은 기록하지 않는다. 실패하면 새 작업을 누르지 않고 고정 실패·Session 해제·terminal/cleanup 결과를 확인한다. 정상3case 뒤 fixture 완료 버튼으로 strict ACK/영수증·parent postcheck·자기 listener/child/root 부재를 확인한다. collected는 각 programmatic case의 관측이며 native keyboard나 실제 Backend/DB/provider 전체 수용으로 확대하지 않는다.


## 최종 동결 source의 실제 브라우저 결과와 게시 준비

조율 측이 최종 manifest `5faefa2b431ac8e0cb10253e03fc5e61503f4a2301207660d0d00311aa173c9f`의 source 전후 hash 일치와 다음 직접 브라우저 결과를 전달했다. 개발 측은 이 회차를 재실행하지 않았으며, 전달받은 실제 화면 관측과 위 직접 보호 단위 검사를 구분한다. 이후 코드·시험 입력은 바꾸지 않고 이 문서와 디자인의 결과 기록만 갱신했다.

실제 production Session/ChatView 및 합성 same-origin HTTP에서 세 고정 case가 모두 `collected-programmatic-mounted`에 도달했다.

| 고정 case | held 관측 | disabled 중 두 번째 DOM click | settlement | 전체 case |
|---|---|---|---|---|
| stored GET | pending/disabled=true, session +1 / core +0 | 추가 HTTP 0 | pending/disabled=false, session +3 / core +1 | GET 4, POST/DELETE 0 |
| 실제 503 오류 → 200 명시 retry | pending/disabled=true, session +1 / core +0 | 추가 HTTP 0 | pending/disabled=false, session +3 / core +1, 오류 해제 | GET 7, POST/DELETE 0 |
| deleted GET | pending/disabled=true, session +1 / core +0 | 추가 HTTP 0 | pending/disabled=false, session +3 / core +1 | GET 8, POST/DELETE 0 |

Deleted 화면에서 원문·계획·결과가 사라졌다. 마지막 fixture counters는 session 24 / prepare 1 / confirm 1 / outcome 5 / model 0 / provider 0이었다. prepare/confirm 1회는 선행 실제 UI 준비·동의·확정이며, 각 고정 GET case의 추가 POST/DELETE 0과 구분한다. disabled DOM click은 UI 억제 근거이고, 동기 handler가 직접 실행된 증거로 바꾸지 않는다. 그 handler 경계는 별도 production 함수 unit에서 검사했다.

이 회차는 completed receipt·parent exit 0, 원래 소유 PID/port listener와 임시 root 부재, source/dependency 후검사 및 guard 이상 0으로 종료했다. receipt ACK는 `not_observed`이므로 ACK 또는 commit ACK가 관측됐다고 표현하지 않는다. 원시 PID/port·receipt·개인 프로필 정보는 공개 문서에 넣지 않는다.

별도 native 1440 및 390 회차에서는 질문 Return → H2 → 첫 실제 동의/waiver로 Tab 이동, 390의 waiver/부분/최종 동의/활성 Flow 버튼 접근과 레이아웃, 250ms 응답 지연 동안 사용자가 Tab으로 보관함으로 이동했을 때 focus를 빼앗지 않는 경로가 각각 positive completion으로 확인됐다. confirmPOST는 0이었다. programmatic mounted GET, native keyboard, 주입식 unit은 서로 다른 증거다. 실제 폰·Safari·screen reader·실제 Backend/BFF 인증·DB·provider 수용은 아니다.

이전 30초 collect timeout과 이전 focus 실패 회차는 실패 이력으로 보존한다. 최신 성공 결과로 과거 실패를 통과로 바꾸지 않는다. 현재 활성 fixture는 없으며, 코드와 시험 입력이 같으므로 추가 검사나 서버를 시작하지 않았다.

독립 source 및 delta 검토는 최종 동결 입력에서 통과했다는 조율 측 결과를 반영한다. 문서 갱신 뒤 정확 8경로·hash·index·privacy를 대조해 Draft PR을 준비하며, 원격 exact-head CI와 Ready 이벤트 CI·리뷰/merge 조건은 별도로 확인한다. CF029의 게시 거절이나 그 4파일은 이 branch로 옮기지 않는다. 실제 키·provider·기존 승인 원장·운영 설정은 변경하지 않는다.
