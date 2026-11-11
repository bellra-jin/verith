# CF-041 채팅에서 기존 재무 화면 열기

기준 develop `3fede01294d1461ad0a8043ee3002635c271f842`와 별도 `feat/supervisor-fundamental-navigation`에서
정확 6경로만 변경했다. CF040 A의 완료 변경과 다른 WIP를 보존한다. 이 작업은 기존 재무 화면의 탐색 연결이며
Supervisor typed 재무 계획·dispatch·단일 채팅 실행 통합이 아니다.

채팅의 기존 Technical 조회 안내 문단에 literal native `<a href="/fundamental">`와
‘재무 분석·본인 결과 열기’, ‘별도 재무 화면에서 실행 여부를 확인합니다’ 안내를 추가했다.
Technical 링크와 기존 CSS/token을 유지하고 재무 badge는 ‘채팅 실행 미연결’로 표현한다.
링크에는 query/hash·원질문·종목·owner·analysis ID·동의·key/body를 전달하지 않는다.
클릭 handler·새 상태·자동 prefetch·POST·새 탭·강제 focus 또는 미전송 draft 저장은 추가하지 않았다.

기존 `/fundamental` page/lib/component/BFF는 읽기로만 대조했다. query 없는 기존 page는 analysisId=null로
AnalysisEntry를 조합하며 기존 기능 gate가 false이면 사용 불가 안내를 낸다. 실제 gate 값은 읽지 않았다.
기존 component는 verified·체크박스 동의·명시 실행 버튼 뒤에만 postAnalysis를 호출한다.
기존 단위 source의 GET never POST 및 명시 replay key/body 보존 회귀도 원형과 같음을 확인했다.
재무 전체 suite·DB·engine을 다시 실행한 증거가 아니며 기존 인증/owner·별도 동의를 대체하지 않는다.

## Fixture와 보호 범위

기존 core-browser fixture의 host/origin·terminal-open 검사를 통과한 raw exact GET `/fundamental`만
비개인 navigation marker와 native `/research` return으로 응답한다. query·추가 path·잘못된 method는 거절한다.
기존 research/API/assets validator·counter/receipt schema·request 상한·590초 fixture/600초 parent 기한은 바꾸지 않는다.
marker에는 실제 재무 component·인증·자료 조회를 마운트하지 않으며 실제 재무 화면 렌더 성공으로 표현하지 않는다.

caller는 `verith-supervisor-fundamental-navigation/frontend` exact sibling 한 곳만 추가했다.
기존 dependency alias와 metadataRoot·package/lock·React 5파일·realpath/owner/mode/identity 및
source/dependency 전후 검사, worker 원본 접근 차단과 OS/FS/network/env guard를 유지한다.
새 harness/mode/package/CI·Backend/AI·예약/원장 변경은 없다.

## 직접 보호 검사

기존 설치 Node를 사용하는 clean env의 절대 `check-local-ports.mjs core-unit/type/lint`와 `fixture-lint`를 실행했다.
최종 core-unit은 실제 core 함수/JSX 126개, BFF 24개, port 6개, tooling 67개의 총 223개가 통과했다.
core-type/core-lint/fixture-lint는 각각 exit 0이며 최종 lint findings는 빈 배열이다.
예상 밖 guard 위반 0, source/dependency/provenance 후검사와 각 소유 임시 root 제거를 확인했다.
기존 tooling의 의도된 negative guard probe 16개와 예상 밖 위반을 구분한다.

첫 unit은 기존 provenance 단언의 sibling 목록 한 곳이 새 exact sibling을 포함하지 않아 실패했다.
그 목록에 승인된 이름 하나만 추가했고 영향 검사에서 통과했다. 첫 lint의 불필요한 새 directive 경고는
기존 같은 탐색 문단과 기존 native-link directive를 재사용해 없앴다. 처음 실행한 로그도 보존했다.
허용 범위나 worker/guard를 완화해 우회하지 않았다.

추가 JSX 단위는 실제 ChatView를 transpile하고 no-op hooks/JSX 및 callback/fetch/storage spy를 주입한다.
pending/잠금/미인증/삭제/미지원 등 상태에서 정확 href/label과 handler·query 부재, Technical 링크 유지,
일반 rerender의 callback/fetch/pending storage 변경 0을 확인한다. hooks/effects와 React를 실제 mount한 검사는 아니다.
fixture 검사는 실제 선택한 handler/helper body와 합성 request/response로 exact GET, raw target 거절,
고정 marker/native return과 API 카운터 불변을 확인한다. 실제 브라우저 탐색은 별도 근거다.

현재 설치 Next 16.2.10의 번들 Link/page 가이드에서 Link의 prefetch/client navigation과 page/searchParams
계약을 확인한 뒤 작업했으며, 정본이 요구한 native anchor를 유지했다.

## 브라우저·게시 인계 시점의 기록

다음 세 문단은 구현 담당이 동결 source를 넘긴 당시의 범위이며, 실제 조율 결과는 아래에 별도로 기록한다.

구현 작업자는 브라우저 서버를 시작하지 않았다. 조율 측이 동결 source에서 기존 core-browser 입구를 한 번 실행하고
기존 미로그인 Supervisor test Chrome/Desktop 1·exact emitted origin에서 native 클릭 및 Tab/Return의 목적지·복귀,
안정 카운터·POST 0·390/1440 배치와 정상 terminal/cleanup을 별도로 확인한다.
marker에 이동한 채 끝내지 않고 `/research`로 돌아와 기존 fixture 완료/취소 제어로 닫는다.
실제 수행한 화면/키보드 범위, generic receipt의 UI 미실행 필드와 ACK 상태, 정상 parent/정리 결과는 이후 조율 기록으로 구분한다.

구현 시점에 Git stage/commit/push/PR·실제 모델/자료 API·환경/flag·DB/설치·350m/소비 원장 변경은 없다.
이는 구현 담당과 조율 측의 역할 구분이며 사용자의 한시적 정상 게시/merge 위임을 영구 금지로 바꾸지 않는다.
독립 리뷰·Ready PR·최신 exact-head 필수 CI/정상 merge 결과는 조율 측이 별도로 기록한다.
실제 Google/DART/OpenAI·운영 활성화·production 통합 E2E와 단일 채팅 재무 dispatch는 미검증/미구현 범위로 남는다.


## 실제 native QA 결과

동결한 동일 소스로 기존 보호 core-browser를 실행했다. 첫 회차에서 native 클릭과 textarea의 Shift+Tab→재무 링크
포커스→Return이 query/hash 없는 exact `/fundamental` marker로 이동했고 native return으로 `/research`에 돌아왔다.
첫 복귀의 session GET은 2→4이며 준비/확정 POST·DELETE·model/provider는 모두0이었다. Chrome responsive1440×844와
device toolbar 표시50%에서 링크·안내·입력/버튼의 겹침 없는 배치를 관측했다. 이는 DOM overflow 수치 측정이나
physical desktop/phone 수용이 아니다.

첫 회차는 CUA runtime 재초기화와 PTY 세션 소실 후 채널 오류로 끝났다. 정상 terminal receipt·parent exit0·자동 후검사를
확보하지 못했으므로 완료 회차로 세지 않는다. PID/listener 부재와 정확 소유 root의 uid/mode/nonce/readiness를 확인하고
그 root만 정리했다. source·고정 파일·React5 identity/hash의 별도 수동 재대조는 일치했다. 모바일 전환 중
noWindowsAvailable 오류도 보존했으며, 사용자 승인 거절이나 제품 오류로 단정하지 않았다.

브라우저 창을 다시 읽어 정상 제어를 확인한 뒤 남은 QA만 새 bounded 회차로 분리했다. responsive390×844·toolbar50%에서
기존 CSS의 두 링크·줄바꿈 안내·textarea·버튼이 화면 안에 겹침 없이 표시됐다. 실제 textarea 초점에서 Shift+Tab은
재무 anchor를 가리켰고 Return은 exact 목적지로 이동했다. native return 뒤 session GET4, 나머지 준비/확정/outcome·
POST/DELETE·model/provider0을 확인했다. 기존 fixture 완료 제어로 completed receipt·parent exit0·소스/의존성 후검사·
예상 밖 guard0과 자기 root/listener/PID 부재를 확인했다. 첫 회차의 실패 기록을 이 결과로 덮어쓰지 않았다.

generic receipt는 ACK not_observed와 UI not_executed 필드를 원형대로 유지한다. 위 화면·키보드는 별도의 CUA operator
관측이며 receipt가 UI 수용을 자동 증명했다고 표현하지 않는다. 실제 재무 page/로그인/자료·DART/모델은 실행하지 않았다.
빈 대화에서 이동했으므로 고정 pending key/body 보존은 기존 source/단위 근거이며 이번 mounted 관측으로 확대하지 않는다.
실제 폰·Safari·screenreader와 단일 채팅 재무 실행도 미검증이다. 실제 환경/키·DB·설치·추가 예약은 없으며350m은 불변이다.
