# CF-027 Supervisor 재인증과 화면 수명주기

정본 v1.0 SHA256 `564d8e6c93c57c41d01bf29d80527d35c8290804503aa6e80806c88a73d954eb`, 기준/HEAD `ad7ced12df1b227f07106b82598cd67d6e687768`, branch `feat/supervisor-reauth-lifecycle`의 정확5파일 수정이다. 기존 CF021 WIP·CF026 live bootstrap·Technical·News와 분리한다.

## 이전 실제 재현과 이번 책임

조율 측이 전용 미로그인 테스트 프로필에서 production Session/ChatView/CSS와 합성 HTTP를 실제 마운트했다. 명확화/후보/동의/확정/reload·일부1440/390/Tab을 확인하던 중 pending 준비의 core401/session200에서 무한 재인증이 재현돼 취소했다. 이전 receipt의 sessionGET8703과 provider/model0, cancelled·child/listener/root 정리는 조율 측 전달 근거다. prepareGET0은 인증 거절 전에 시도를 세지 않던 이전 counter 한계이며 시도0을 뜻하지 않는다. 전체 브라우저 수용은 실패했고 지연/back 등 후속은 중단됐다. 이번 개발 측 직접 브라우저 실행이나 현재 source의 통과로 집계하지 않는다.

## 수정

- inline account callback을 안정 useCallback으로 바꾸고 기존 effect 의존성·cleanup을 유지했다. 단순 부모 rerender는 인증/Conversation 효과를 다시 시작하지 않는다.
- 상위 Session이 static tab-local marker와 메모리 latch를 소유한다. 401/계정 변경은 즉시 화면·요청/timer를 무효화하고 자동 retry를 제거한다. route remount/URL/back/visibility 복귀는 latch를 해제하지 않는다. marker read/write 불명도 자동 복구하지 않는다. 기존 fixed recovery storage schema/bytes를 변경하지 않는다.
- 마지막 검증 owner는 별도의 tab-local SHA256 fingerprint로 보존하고, hide/retire 시 지우는 활성 callback owner/epoch와 분리했다. 자동 A→B 조회와 route remount의 B는 grant 전에 latch로 닫는다. 초기 최초 로그인·명시 B 확인은 별도 검증 후 provenance를 갱신한다. raw owner ID/원문/쿠키는 이 metadata에 저장하지 않으며 불명/불일치도 자동 채택하지 않는다. 기존 session/owner 검증은 그대로다.
- 부모 session 조회에 generation·원 URL·mounted/visibility·abort, 현재 owner/epoch/href callback 대조를 추가했다. 명시 재확인의 ref-lock을 클릭 즉시 잡고 child GET 검증까지15초로 제한한다. 버튼 disabled와 같은 ID GET-only 복구를 유지하며 새 POST/key·자동 polling을 시작하지 않는다. 성공한 private 조회 뒤만 latch를 해제한다. 더 오래된 callback/session200은 새 owner/세대를 되살리지 못한다.
- ended는 실제 자동 관측 시작 뒤 수동 중지/기한·예산 종료에서만 표시한다. 새 대화는 marker/관측기를 초기화하고 빈 요청에 종료 안내를 켜지 않는다. 기존 unknown/result_ready·same-key 게시·취소 편집 draft 의미는 보존한다.
- fixture의 session/core·method별 `attempts`를 인증/오류 gate 앞에서 별도 계수한다. 성공 counter8개/terminal receipt schema는 그대로다. 전체128회·rolling2초24회 상한과 arm한 시나리오30초 상한을 넘으면 고정 실패를 기록하고 기존 failed terminal/소유 정리로 끝낸다. 무응답 polling으로 숨기지 않는다.
- fixture-counts의 nonce-bound failure 대기는 기존 소유 origin에서 단일 요청으로 등록하고 fixture 잔여 수명 안에만 유지한다. 서버는 watcher 최대2개와 scenario30초 상한을 유지하며 cap/timeout 실패를 먼저 전송한다. client는 다음 클릭 없이 고정 실패 banner·동기 ref 잠금·Session 해제를 수행한다. 무한 polling/재연결은 없고, 정상 terminal은 수명주기 종료로 구분한다. 늦은 control/refresh가 실패 표시/잠금을 덮지 못하며 실패 알림 connection의 settlement 뒤 기존 terminal drain/receipt/cleanup을 유지한다.
- 유한한 scenario arm/collect·one-shot session hold_next/release·합성 auth 상태 제어를 추가했다. session 응답 owner/status는 지연 시작 전에 고정되며 뒤의 계정/상태 제어로 과거 응답을 바꾸지 않는다. observations는 작은 counts/delta/상태뿐이며 UUID/질문/storage/CSRF/nonce를 출력하지 않는다. raw script/URL 입력이나 fake Session/verified 주입은 없다.

## 직접 집중 검증

기존 clean env·절대 Node·OPENSSL_CONF=/dev/null·OS preflight·source/dependency provenance·동일 guard의 보호 입구를 공식 require_escalated 심사로 사용했다.

| 선택 | 최종 결과 | checkpoint 로그 |
|---|---|---|
| `core-unit` | 121통과 = core53 + BFF14 + config6 + tooling48, fail/skip/cancel0, exit0 | `unit-4.log` |
| `core-type` | 오류0, exit0 | `type-4.log` |
| `core-lint` | 대상 오류0, exit0 | `lint-4.log` |

unit은 실제 production의 latch/세대 함수와 parent callback을 IO/ref 주입으로 실행해 explicit gating·중복 lock·stale owner/URL/visibility/unmount·timeout·route remount marker/고정 storage 보존을 검사한다. 실제 fixture의 cap/scenario/snapshot/one-shot 함수도 고정 AST 추출로 실행했고 bundle 구문과 wiring을 검사했다. 이 증거는 React mount/effect/클릭이 아니며 fake hooks로 lifecycle 통과를 만들지 않았다.

첫 unit114/type는 통과했지만 lint가 초기 effect의 동기 state 변경 규칙1건으로 child1/entry78에 실패했다. 접근/OS 거절이 아니며 임시 root 정리를 확인했다. 초기 검증을 commit 이후 microtask에서 해당 세대가 여전히 유효할 때만 시작하도록 수정했다. 다음 unit115/type/lint가 통과했다. 마지막으로 명시 재인증의 GET-only 의도를 child 최초 검증까지 연결하고 bundle 구문 회귀를 추가해 116/type/lint로 영향 재검증했다. 이후 독립 검토에서 마지막 owner provenance 소실과 클릭 없는 실패 표시 누락을 확인해 위 두 경계를 보완했다. 실제 parent callback·지속 fingerprint·failure 채널/상태 callback 회귀5개를 더해 최종121/type/lint가 통과했다. 과거 실행 수를 합산하지 않는다.

최종 unit4 worker/type1/lint1의 journal에서 예상 밖 violation·diagnosticFailure·original raw dispatch0을 확인한다. tooling의16 denial은 기존 expected negatives다. native 전체 관측/모든 원본 읽기 부재 증명이 아니다. 모든 검사 child가 settlement되고 자기 root가 제거됐으며 실행 중 검사/fixture 서버는 없다.

`safe-checks-guard.cjs` SHA256 `3a9cb45bc865d560612ccd5876f060c69aa0abe5ff635576888781d9efe7d3ee`는 base와 byte-identical이다. runner/helper/package/lock·React5개·Backend/AI/DB·CI는 변경하지 않는다. 전체 build/Backend/PG·기존 의미 suite는 재실행하지 않았다.

## 조율 측 실제 mounted 재개 절차와 예상 delta

아래는 **준비된 제어/예상값**이며 개발 측 실행 결과가 아니다. 조율 측이 source 검토 후 기존 보호 core-browser·확인된 전용 프로필/소유 탭 identity와 그 실행의 emitted origin만 사용한다. 서버를 개발 측에서 시작하지 않았다.

각 좁은 시나리오는 `시나리오 arm · <name>` → 필요한 실제 행동 → `30초 내 관측 수집` 순서다. collect는 acceptance pass가 아니라 서버가 관측한 delta 수집이다.30초 전에 수집하고 다음 시나리오를 arm한다. 실패/상한 초과 시 더 클릭하지 않으며 failed/취소 영수증과 parent postcheck·정리를 먼저 확인한다. 기존 fixture 완료/취소 버튼과 수명주기 증거는 UI 통과와 구분한다.

| scenario | 제어/관측 | 예상 앱 요청 delta |
|---|---|---|
| `rerender` | ready 계획/동의 또는 stored에서 합성 카운터 버튼 반복 | session/core0; 원문·계획·결과·동의 유지 |
| `reauth` | 합성 pending 준비 뒤 core HTTP401, session HTTP200. 제어만으로는 앱 요청0. `질문 확인`으로 보존 preparation GET을 명시 실행 | 첫 실패는 session1 + core GET1; POST0. 이어 idle/rerender/pageshow/visibility/URL-back 각2초는 추가 자동0 |
| `recovery` | latch UI의 로그인 재확인 중복 클릭. core401 유지 | 한 작업: session3 + preparation GET1, POST0; 다시 latch·추가 자동0 |
| `recovery` | 같은 pending ID에서 core200으로 바꾼 뒤 명시 재확인 | 한 작업: session4 + preparation GET1, POST0; 같은 키/본문, 자동 polling0 |
| `recovery` | known supervisor ID 명시 복구 | session4 + outcome GET1, POST0. consumed preparation에서 binding까지 읽는 경우는 별도 두 GET 경로로 구분 |
| `stale-session` | 검증 A에서 hide/retire → B로 변경 → show 또는 route remount | 자동 session1 뒤 latch·core0/grant0. 이미 latch 중이면 자동0. 빈 research에서 명시 B 확인 성공은 session2/core0이며 A 고정 입력은 보존 |
| `stale-session` | session hold_next → 명시 검증 → held 표시 → 계정/상태 변경·hide/unmount → release | 과거 snapshot 응답이 현재 화면을 복원하지 않음. latch 중 자동 요청0; 이후 명시 B 검증은 B 자료만 |
| `new-request` | 실제 terminal 결과 뒤 명시 새 요청, 빈 research | 자동 POST0, ended 안내0. 정상 새 질문 편집·명시 준비 가능 |

클릭 없는 failure 전달은 `scenario arm` 후 추가 앱 행동 없이30초를 넘겨 확인한다. 고정 실패 표시·disabled controls·Session 해제가 자동으로 나타나야 하며, server failed terminal과 소유 정리도 별도 확인한다. 이는 의도된 실패/정리 회귀이고 UI 수용 성공이 아니다. 모든 정상 scenario는30초 전에 collect하며 cap 재현은 별도 source 검토/조율 없이 무작정 반복하지 않는다.

blank latch 명시 확인은 parent/child session2회·core0이다. 위 session 수는 기존 helper의 전후 인증을 포함한다. 작은 네트워크 차단/실패가 중간에서 발생하면 더 적을 수 있으나 숨은 반복이나 추가 POST를 허용하지 않는다. fixed ACKunknown/result_ready storage 비교와 실제 URL/back/reload·늦은 timer·1440/390·Tab/focus는 해당 source에서 실제 관측한 결과를 별도 기록해야 한다. 본문/ID/storage 원문을 공개 증거에 덤프하지 않는다.

## 남은 범위와 인계

현재 최종 source의 mounted React/interaction/storage/navigation·1440/390·focus는 미실행이다. 준비 fixture/함수/구문 검사와 이전 부분 수용을 현재 실제 통과로 바꾸지 않는다. 실제 Backend/auth/PG/Google/provider/모델 품질·운영 인수도 미실행이며 실제 키/.env·CF026 live 경계와 별개다.

정확5파일 manifest·NUL 목록·명령/로그 SHA·변경 diff·미실행과 실패 이력은 비공개 checkpoint에 남긴다. 개발 측 git add/commit/push/PR/merge는0이며 새 권한을 가정하지 않는다. 독립 source 검토와 실제 mounted 재개/게시 조율은 부모 담당이다. 현재 denied/uncertain 실행은 없고 실제 mounted 수용은 pending이다. 취소 후 local 편집 draft 의미는 별도 UX 후보로 보존했다.


## 종료 전 조율 측 실제 관측과 Draft 보존 상태

조율 측이 전용 미로그인 Chrome의 production Session/ChatView 합성 화면에서 정상 회귀를 실행했다. ready/stored 부모 rerender의 앱 요청 delta0, pending core401/session200의 session1+coreGET1, 명시 실패 복구3+1·성공 복구4+1과 POST0, 늦은 A session 응답/계정 B 전환의 latch 유지, terminal 뒤 새 요청 session2/core0·ended 안내0, latch 뒤 reload delta0, known ID 수동 복구 session4+outcomeGET1/POST0을 관측했다. 정상 회차는 completed receipt·parent exit0·provider/model0·소유 root 정리가 확인됐다는 전달 근거다. 개발 측 직접 실행으로 집계하지 않는다.

별도 이전 SCENARIO_DEADLINE 회차는 서버의 실패 종료/정리는 됐지만 브라우저가 armed/활성 제어/Session mounted 상태를 유지해 실패 전달 수용에 실패했다. 이를 보완하여 client30초 deadline·bounded watch 등록/수신·header flush·strict ready/React commit ACK·단계별 증거를 기존 fixture/control 안에 추가했다. 최종 수정 전 보호 unit126개(58+14+6+48)·lint는 통과했다.

마지막 실제 Chrome에서는 arm 뒤30초가 지나 추가 클릭 없이 고정 실패 안내·모든 제어 disabled·Session 해제·failure watch commit-acknowledged가 관측됐다. **실행 도중 fixture source가 바뀌어 보호 parent command/package postcheck가78로 종료됐다.** 소유 root 정리와 guard violation0은 확인됐지만 이 회차는 최종 exact-source 통과가 아니다.1440/390은 관측했으나 emulation의 native AX/screenshot 갱신 시점 불일치로 최종 시각 수용을 보류한다.

최종 fixture SHA256은 `f55fcb5345340d9f3a74f32df0c0bf1dea4ec32d0e9388eadbbc6265dc1ac355`다. 마지막으로 client commit ACK missing/timeout을 정제된 commit_unconfirmed로 남기되 failed terminal receipt 저장/정리를 계속하도록 최소 보완했다. **이 마지막 보완 뒤 실행 검사는 하지 않았다.** production Session/guard는 그대로이며, source drift 회차와 최종 source 증거를 합치지 않는다.

현재 종료 전 인계는 Draft PR 보존 수준이다. 최종 exact-source 보호 검증/브라우저 수용·최신 head CI/검토·병합 완료를 주장하지 않는다. 개발 측은 이후 새 검사·코드/테스트 수정·Git 게시·CF026/provider 작업을 하지 않는다. 실제 브라우저 결과와 최종 게시 기록은 조율 측이 관리한다.

## 2026-11-10 최종 게시 시점 추가 관측

이 절이 위의 개발 측 미실행 기록 뒤에 확인한 최신 상태다. production Session은 재인증 회귀 통과 시점과 동일하다.

- 전용 미로그인 Chrome의 실제 mounted 검증에서 rerender 추가 요청 0, pending 401 뒤 자동 반복 중단, 실패/성공 수동 GET 복구의 추가 POST 0, 계정 A→B 및 늦은 A 응답 차단, 새 요청의 종료 안내 없음, reload 재인증 latch 유지, known ID GET-only 복구를 확인했다. 정상 회차는 완료 receipt·부모 exit 0과 소유 자원 정리를 확인했다. 1440/390 화면은 관측했으나 시각 갱신 제약 때문에 최종 시각 수용은 보류한다.
- 이후 fixture 전달 경계를 보완했다. headers flush와 bounded ready ACK 뒤에만 arm하고, 독립 client 30초 deadline을 유지하며 React 실패 commit ACK와 서버 write 완료를 구분한다. ACK 미확인은 `commit_unconfirmed`로 기록하고 failed receipt 저장·정리를 계속한다.
- 이 보완의 마지막 작은 ACK 예외 수정 직전 보호 unit 126개(core 58 + BFF 14 + config 6 + tooling 48)와 lint 오류 0을 확인했다. production Session이 바뀌기 전의 type 검사도 통과했다. 마지막 ACK 예외 수정 후 실행 검증은 미실행이다.
- 마지막 실제 deadline 사례에서 추가 클릭 없이 고정 실패 안내, 모든 제어 disabled, Session 해제, `commit-acknowledged`를 관측했다. 그러나 실행 중 마지막 source 보완과 겹쳐 부모의 command/package postcheck는 exit 78로 실패했다. guard violation 0과 소유 임시 root 정리는 확인했다. 이 관측을 최종 exact-source 검증 통과로 간주하지 않는다.
- 최종 fixture SHA256: `f55fcb5345340d9f3a74f32df0c0bf1dea4ec32d0e9388eadbbc6265dc1ac355`. production Session과 guard는 이번 마지막 fixture 보완에서 불변이다.
- 최종 동일 소스의 deadline/ACK 미수신 회귀와 전체 시각·focus 검증은 남아 있다. Draft PR로 게시하고 CI/merge를 기다리거나 실행하지 않는다. 실제 Backend/auth/PG/provider/모델 검증은 이번 게시 범위에 없으며 모델·provider 호출과 비용은 0이다. CF026/OpenAI 후속 작업은 중단했다.

## 2026-11-10 재개: 최종 동일 소스 집중 검증

이 절은 위 종료 전 미검증 상태 이후의 직접 실행 결과다. 재개 HEAD는 `bb9682b1879e0941b9ce9ae3161f1aabf4e9c08b`, 같은 `feat/supervisor-reauth-lifecycle`의 clean 상태에서 시작했다. PR30 Draft 및 해당 head의 원격 CI 성공은 조율 측 전달 근거이며 이번 개발 측 원격 조회/게시 결과가 아니다.

마지막 ACK 예외 보완의 실제 fixture terminal callbacks·`bounded`·`receiptFile`과 기존 `createFixtureTerminal`을 실행하는 회귀4개를 추가했다. missing commit과 commit timeout은 `commit_unconfirmed`를 남기고 failed 영수증을 mode0600으로 저장한 뒤 close/settled로 이어진다. 정상 ACK는 unconfirmed를 기록하지 않는다. handler settlement 실패는 성공 영수증으로 바꾸지 않고 실패를 전파하며 close한다. 영수증 임시파일과 검사 소유 디렉터리 제거도 확인했다. 서버/타이머 IO 일부는 주입한 단위 검사이며 실제 listener/React/브라우저 실행이 아니다.

첫 보호 unit130(62+14+6+48)·type·lint는 통과했다. 이후 독립 검토에서 collect가 서버30초 전에 성공해 timer를 취소했지만 응답 전 client deadline이 만료되는 race를 확인했다. 유효한 failure commit을 받아도 서버가 기록/응답만 하고590초까지 남을 수 있었다. 기존 strict ACK control 안에서 열린 terminal만 failed 종료를 요청하도록 수정했다. ACK handler는 terminal 종료 완료를 await하지 않으며 자신의 응답/settlement 뒤 drain이 진행된다. 이미 닫히는 terminal은 다시 시작하지 않는다. 서버 collect→client deadline→commit ACK→handler settlement→failed receipt/close 순서의 실제 함수 회귀1개를 추가했다. 새 endpoint/helper/runner나 권한 확대는 없다.

수정 뒤 같은 최종 제품/검사 소스로 다음 한 회차를 실행했다. 모든 실행은 clean env(`LANG=en_US.UTF-8`, `TZ=UTC`, `OPENSSL_CONF=/dev/null`)·고정 Node22.7.0·기존 보호 `frontend/scripts/check-local-ports.mjs` 입구와 정식 `require_escalated` 심사를 사용했다.

| 선택 | 최종 결과 | 비공개 checkpoint 로그 |
|---|---|---|
| `core-unit` | 131통과 = core63 + BFF14 + config6 + tooling48; fail/skip/cancel0, parent exit0 | `core-unit-2.log` |
| `core-type` | 오류0, parent exit0 | `core-type-2.log` |
| `core-lint` | 대상 오류0, parent exit0 | `core-lint-2.log` |

최종 실행 시각은09:41:35–09:42:13 UTC다. unit worker4/exitRecords4, type·lint 각1/1이며 예상 밖 violation·diagnosticFailure·original raw dispatch0이다. tooling의16 denial은 기존 expected negatives다. 각 parent는 자기 temporary root 제거를 확인했다. JS journal 범위의 계측이며 native 전체 관측/모든 원본 읽기 부재 증명으로 확대하지 않는다. 현재 source·명령·Node/의존성·로그 SHA와 전후 불변 대조는 비공개 checkpoint의 `final-source.json`, `validation-evidence.json`, `handoff.md`에 보존한다.

production Session SHA `b5ef8618f552e8e77399b478f5327c2e2137bf857f823893fc8394f9770c9b44`와 guard SHA `3a9cb45bc865d560612ccd5876f060c69aa0abe5ff635576888781d9efe7d3ee`는 재개 HEAD와 동일하다. runner/helper/package/lock·설치 의존성·Backend/AI/DB/CI도 변경하지 않았다. 최종 검증 뒤에는 이 결과 문서만 갱신했다.

이번 재개에서 브라우저 서버/프로필/탭·Backend/DB/provider/Google·키/.env·CF026/OpenAI·Git 쓰기는 실행하지 않았다. denied/uncertain 작업은 없다. 수정 후 최종 source의 실제 mounted deadline·1440/390·focus는 조율 측 검증 pending이다. 의도된 failed 시나리오의 child1/parent78은 UI acceptance pass가 아니다. 현 runner는 child 실패 시 일반 terminal summary 전에 빠지므로 실제 실패 회차의 디스크 receipt 회수는 지원된 소유 증거 경로가 확보됐을 때만 보고하고, 로그/화면 관측만으로 receipt 읽기 완료를 주장하지 않는다. 보호 runner를 바꾸거나 다른 경로로 우회하지 않는다.


## 2026-11-10 재개 후 동일 소스 브라우저 관측과 게시 범위

아래는 조율 측이 새 미로그인 전용 테스트 프로필에서 최종 fixture SHA256 `76c094ac4832beef556c77c08b61485fdbf9ed9c41f47dd8b7dc3748ca6dabf0`와 unit SHA256 `871ec8a7291be1626504619b73d9f717ec85cb8cd445317f704fd94499fbe773`를 고정한 뒤 수행해 전달한 세 회차다. 위의 source drift 실패와 미실행 기록을 대체해 삭제하지 않으며, 이전 lifecycle 관측을 이번 세 회차에서 전부 재실행한 것으로 합산하지 않는다. 이번 게시 담당은 manifest·불변 입력과 전달된 결과를 대조했고 브라우저를 직접 재실행하지 않았다.

1. **mounted deadline:** 시나리오를 arm한 뒤 추가 행동 없이 고정 실패 안내, 모든 fixture 제어 disabled, Session/질문 제거와 `commit-acknowledged`를 AX와 화면에서 관측했다. 서버 단계는 body written → commit received → response written이었다. attempts2/session2/core0/POST0, 의도된 child1/parent78이며 source 불변·guard violation0·소유 root/listener 부재를 확인했다. 이는 실패 전달·정리 회귀 관측이며 정상 UI 전체 수용이나 parent exit0이 아니다.
2. **정상 화면·focus:** fixture UI complete로 종료해 parent0, completed receipt 검증, 소유 root/listener 부재·violation0을 확인했다. sessionGET9/preparePOST2, 다른 core counter와 provider/model은0이었다. 1440에서 빈 질문의 focus ring, Tab으로 활성 `질문 확인` 이동, Return으로 plan/동의 표시를 관측했다. 명시적인 계정 B 재확인으로 A plan이 제거됐고 B 질문으로 새 plan을 만들었다. 390 화면에서 인증 카드·질문·plan·동의·action과 하단 버튼이 production 카드 안에 적절히 쌓여 표시됐다. fixture의 raw 진단 JSON만 가로 page overflow를 만들었다. 비에뮬레이션 native keyboard에서 동의 후 Tab으로 활성 Flow action에 focus가 이동했으며 Flow 실행은 하지 않았다. 에뮬레이션 AX pointer로 pending을 누르려던 시도는 계정 B에 닿았으므로 pending 성공 사례로 세지 않는다. 이후 native keyboard/비에뮬레이션 조작으로 전환했다.
3. **ACK 미수신:** watch 등록 → arm → 같은 소유 탭의 about:blank 이동 후 `closed_before_body`, active0, commitAcks0, `SCENARIO_DEADLINE`, `commit_unconfirmed`를 기록했다. attempts2/session2/core0/POST0, 의도된 child1/parent78이며 소유 root/listener 부재·violation0을 확인했다. 실제 실패 회차의 디스크 receipt는 독립 회수하지 못했다. 변경하지 않은 parent가 정상 summary 전에 예외로 끝난 뒤 root를 정리하므로 로그만으로 failed receipt 검증 성공을 주장하지 않는다. 앞 절의 실제 함수 추출·주입 timer/server·실제 파일 IO 회귀와 실제 HTTP-process 영수증 증거는 구분한다.

OS process 조회는 차단돼 재시도하지 않았다. 정리는 소유 runner settlement 기록 및 root/listener 확인에 근거하며 native-wide process 부재 증명은 아니다. 화면은 native 브라우저 작업자의 inline 관측 증거이며 저장된 screenshot 파일을 제공한 것은 아니다. 모든 runner는 종료됐고 테스트 프로필은 about:blank·emulation off로 남았다. 실제 Backend/auth/DB/provider/model·credential 접근은 없었다.

독립 read-only 검토에서 collect 응답/client deadline race를 찾아 보완했고 위 정확 fixture/unit hash의 재검토에는 추가 조치가 필요한 잔여 지적이 없었다는 전달 결과다. 최종 보호 unit131·type·lint 통과 이후 제품/검사 입력은 불변이며 이번 게시 보완은 이 기록과 디자인의 검증 상태뿐이다.

정확390 keyboard traversal, 긴 오류 layout, 일시적인 재확인 disabled 상태는 여전히 미검증이다. fixture 진단 JSON overflow와 실패 회차 receipt 회수 한계도 남긴다. 실제 인증·Backend/DB·provider/모델 및 전체 브라우저 수용을 완료로 선언하지 않는다. 기존 [Draft PR #30](https://github.com/bellra-jin/verith/pull/30)의 같은 branch에 게시하며 Ready·merge·auto-merge·배포는 하지 않는다. 새 head의 원격 CI는 PR에서 별도로 확인하며 이전 head의 성공을 새 head 결과로 사용하지 않는다.
