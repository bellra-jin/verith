# CF-025 Supervisor fixture 복구 URL과 정상 종료

정본 v1.0 SHA256 `1b0dfa185bcbaa251f99a5661daaf7a9f32076a0ec9329c24dba8941ab00a250`, 기준 `19530fc21615bee3351392bae37804ae5e61fc7b`, branch `feat/supervisor-browser-readiness`의 정확7파일 작업이다. PR28·원격18단계 성공은 선행 조율 측 보고이며 이번 직접 실행으로 집계하지 않는다. 실제 제품·의미 정책·Frontend production 컴포넌트·Backend/AI/DB·Flow fixture·CI/package는 변경하지 않았다.

## 구현

- fixture 전용 공통 validator가 origin-form raw target을 먼저 검증한다. `/research`와 단일 canonical UUID 복구 query만 HTML로 제공하며 initial ID·navigate·popstate에서 같은 함수를 사용한다. 강제 history 초기화를 제거하고 listener cleanup·잘못된 URL의 private view 숨김을 유지했다. exact asset/API method/path, Host와 Origin을 확인한다.
- strict terminal endpoint는 exact JSON action 하나, 1024 bytes, nonce/Host/Origin과 body5초를 요구한다. open→closing의 단일 승자 이후 지연 handler를 깨워 mutation/counter 증가를 fence한다. body 초과는 iterator의 socket 파괴에 기대지 않고 수신을 멈춘 뒤 고정 오류 응답/connection close로 끝낸다.
- cleanup은 남은 fixture deadline과 공통5초 중 이른 한계 안에서 처리한다. 자식은 frozen counter/terminal·browser not_executed를 새0600 regular/nlink1 영수증에 원자적으로 쓰고 ACK한 뒤 listener/readiness를 닫는다. 최종 phase를 설정한 뒤 stopped를 풀어 closing 상태의 조기 실패를 막는다. timed_out/failed/cancelled/completed를 구별한다.
- 부모는 기존 readiness nonce/PID/cwd/port·listener/등록 child identity 이후에만 probe를 시작한다. fixture/probe는 부모의 checkedCommand sibling이며 shared capability600초를 덮어줄이지 않고 probe command와 자체 deadline60초를 별도로 적용한다. 요청당 inactivity와 별도로 절대5초 타이머·응답 cap·literal loopback·redirect 미추적을 유지한다.
- 부모는 immutable receipt·두 child settlement·전후 package/provenance·production React5개 hash·listener/readiness 제거를 대조한다. 응답이 없는 전송 불확실만 ACKunknown으로 회수하며, 받은 오류 HTTP/JSON/state는 실패다. ACK 재전송은 하지 않는다. 대화형 core-browser의 명시 완료/취소에도 receipt 검증을 적용한다.

## 직접 실행 결과

2026-11-10 KST에 검증된 절대 Node·clean env·OPENSSL_CONF=/dev/null의 기존 보호 입구를 공식 require_escalated 심사 후 사용했다. 같은 보호를 유지한 필요한 영향 검사만 실행했다.

| 선택 | 최종 결과 | private checkpoint 로그 이름 |
|---|---|---|
| `self-test` | 48통과, fail/skip/cancel0, exit0 | `self-4.log` |
| `fixture-lint` | 변경 JS5개, 오류0, exit0 | `lint-5.log` |
| `core-browser-check` | 별도 root의 complete→cancel 두 순차 인스턴스 통과, exit0 | `http-4.log` |

self-test는 실제 URL/adapter helper와 fake history/event target, terminal/부모 callback·IO 및 고정 AST로 추출한 실제 body receiver/probe request 함수를 실행한다. 초기/reload ID·back/popstate cleanup·negative raw URL·중복terminal·counter fence·timeout/ACK 손실·조기 child/receipt/postcheck/cleanup 실패·oversize socket 보존·절대 request 타이머를 검사한다. fake 시간·callback 회귀를 실제590초 대기·브라우저 클릭으로 집계하지 않는다.

HTTP complete 인스턴스는 production validator로 고정 draft/plan/hash/candidate/PreparationView/Outcome을 검증하며 합성 preparePOST1·confirmPOST1을 만들었다. 실제 반환 binding ID의 HTML reload200 뒤 **명시 outcome GET1**을 수행해 같은 plan을 확인했다. reload의 추가 prepare/confirm/model/provider는0이다. sessionGET1이며 외부 model/provider0이다. 정확 경로/asset·no-store/CSP·잘못된 query/method/Host/Origin/nonce/body도 확인했다. bundle은 제공됐으며 실행/mount된 것은 아니다.

다음 별도 인스턴스는 prepare/confirm/outcome0으로 실제 cancel 영수증과 정상 종료를 확인했다. 이는 cancelled 상태와 정리 검사의 통과이며 UI 수용 성공이 아니다. 두 terminal ACK는 received였고 각 인스턴스의 registered child0·readiness 제거·같은 PID/port listener 부재·root 제거를 확인했다. 앞 인스턴스의 settlement/postcheck/root 정리 뒤에만 다음을 시작했다. 현재 실행 중인 fixture/probe는 없다.

관측 journal은 HTTP 각 인스턴스2 worker/2 exitRecords·예상 밖 denial0·violation0·diagnosticFailure0·original raw dispatch0이다. self의16 denial은 기존 보호 부정 회귀의 expected negatives와 일치했다. 이는 instrumented JS FS/journal 범위이며 native 전체 읽기/외부 부작용의 전수 관측 증명이 아니다.

## 실패·수정 이력

- 첫 self43개는 통과했다. 독립 WIP 검토에서 종료 close가 stopped를 먼저 풀어 phase=closing을 관측할 수 있는 race를 발견해 phase 확정 뒤 신호로 수정하고 실제 helper 순서 회귀를 추가했다. 다음 self44개와 첫 HTTP complete/cancel은 통과했다.
- 첫 lint는 신규 probe의 지역 변수 `module`이 Next lint 규칙에 걸려 exit78/child1이었다. 접근/OS 거절이 아니며 이름만 수정했다. 자기 root 정리는 확인됐다. 다음 lint는 통과했다.
- 추가 독립 지적의 받은 오류 ACK와 unknown 구분, bounded body 수신, 절대 request deadline, 대화형 종료/부모 검증을 보완하고 해당 실제 helper/AST 회귀를 추가했다. 최종 self48/lint/HTTP 위 결과는 이 변경 뒤 실행했으며 이전 실행을 합산하지 않는다. 받은 응답 cap/HTTP parser protocol 위반도 명시 실패로 전달하는 마지막 회귀를 추가했다. terminal 부정 HTTP는 정확403/405/422를 대조한다. 이 보완으로 영향받은 선택만 재검증했으며 이전 실행을 합산하지 않는다.
- guard `safe-checks-guard.cjs` SHA256 `3a9cb45bc865d560612ccd5876f060c69aa0abe5ff635576888781d9efe7d3ee`는 기준과 byte-identical이다. OS/FS/network/dependency 권한·원본 provenance·React5개 검증을 낮추지 않았다.

## 미실행과 인계

`react_mount`, `interaction`, `storage_navigation`, `visual_1440`, `visual_390`, `focus`는 **항상 not_executed**로 기록했다. 실제 브라우저/tab/profile/DOM·Next SSR/BFF·Backend 인증/PG·provider/Google·실제 모델 품질/가격 증명·운영 인수는 이번 검사 범위가 아니다. 실제 key/.env/cache·기존 DB/volume·옛 WIP source·새 설치에 접근하지 않았고 운영 한도를 활성화하지 않았다. 실제 key 전송 action-time 승인과 공식 count 비용 근거는 별도 pending이다. Technical·재무·멀티턴·News 신규 실행도 포함하지 않는다.

현재 개발 측 stage/commit/push/PR/merge는0이며 일반 PR/exact-head 원격 CI·독립 최종 검토/병합은 조율 측이 담당한다. 기존 원격18단계는 Backend 검사이며 이번 HTTP 또는 브라우저 증거를 대신하지 않는다. 최종 exact7 manifest/NUL·명령·현재 Git 상태·로그 SHA·private ownership/정리 증거·공개 PR 초안은 checkpoint에 보존한다. 공개 문서/PR에는 nonce/PID/root/실행 ID·개인 경로·원시 증거를 포함하지 않는다.
