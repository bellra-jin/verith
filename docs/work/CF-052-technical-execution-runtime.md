# CF052 · 기수락 Technical run의 단일 실행 조립

정본 v1.0 SHA `fd36b9aa9ecb0dedbca20f52fb3193fff50856fdb5499020c3729c529420c617`, 기준 develop `9029c9ca57fd76865706079e4d23df6ec166aaf8`, 전용 `feat/technical-execution-runtime`의 정확8파일이다. CF051·다른 WIP·기존 실제 기록/$0.50 hold·PR61 HOLD·Frontend/News/준영 AI는 보존한다. 새 승인 마감은 2026-11-13 01:00 UTC이며 완료된 과거 기록은 바꾸지 않는다.

## 제품 변경

기본 비활성 runtime이 기존 admission expected/token·정책·Principal·실제 AIClient의 순수 구성과 method를 첫 await 전에 고정한다. 동기 invocation latch는 해제하지 않는다. 직접 호출한 dispatch_claim의 이번 ACK/newly_claimed=True만 진행하고, fresh SQL auth/period/run 잠금에서 claimed/unaccepted·원 identity/세션·정책/Stock/spec/기한을 확인해 고정 B/S를 만든다. 잠금 종료 ACK 뒤 캡처한 client/config/method를 다시 확인하고 기존3초 synthetic boundary를 한 번 호출한다. 이번 claim.run의 결과는 CF050 receive와 CF035 writer로 저장한다.

AIClient의 Technical URL/token/transport 검증을 비밀 repr 없는 private frozen helper로 분리하고 실제 request도 그 snapshot을 사용한다. 다른 서비스·기존 body/응답 한도/auth/trust_env/redirect/3초는 보존한다. 독립 읽기로 해당 bytes를 확인한 뒤 기존 exact pin만 갱신했다. 보호 검사 첫 회차의 pin 불일치 차단과 이후 검사 결과를 구분한다.

client 정상 실패만 동일 auth/period/run 잠금 안의 claimed/unaccepted fence에서 기존 close_unknown으로 닫는다. receive 이후 오류는 accepted snapshot/stored일 수 있어 이 경로를 사용하지 않는다. 외부 취소에 runner가 SQL 재정리나 detached task를 붙이지 않는다. 예상하지 못한 SQL/IO는 원문/parameters 없이 고정 unavailable로 바꾸며 알려진 domain/auth 오류와 원 취소는 보존한다. 재접수·post·claim 재발급·새 상태머신/표·route·엔진/provider/정산 권한은 없다.

## 검증 상태

기존 보호 admission self5/unit236 통과·guard0·자기 임시 root 제거를 확인했다. 실제 runtime/admission/coordinator/CF050/CF035와 실제 AIClient에 명시 auth/SQL I/O 합성 및 MockTransport를 사용했다. default-off·구성 오류 claim0, 이번 ACK 기반1회·재호출/다른 인스턴스 replay, config/method/기한 drift·fresh ready/unknown, claim/fresh ACK 불명, client timeout/취소와 receive 단계 실패·ready 보존·claimed fence·원문 비노출을 검사했다. 단위의 SQL I/O는 합성으로 실제 경합 증명이 아니다.

기존 completion PG 모드에는 admit-only에서 시작하는 정확3그룹을 추가했다. 실제 SQL claim 경합과 A2 복원, 실제 claim/receive/publish commit의 ACK wrapper, client 오류/취소·receive 취소·ready race 보존을 기존 fixed ASGI 합성 응답으로 연결한다. CF050 baseline13그룹 receiving-only와 새 synthetic_boundary_invocations를 분리한다. 원 source PG1과 짧은 waiter 보완 source PG2에서 각각 기존13+새3=16그룹이 통과했고, 각 회차 synthetic ASGI boundary_invocations=8·provider/engine0을 분리했다. 실제 SQL의 두 session claim 승자1·A2 lossless 복원과 real commit ACK wrapper 및 ready/hold 보존을 확인했다. 실제 네트워크 ACK 손실·AI router/graph 실행은 아니다. 소유 DB/소스 사본 제거와 exact CID 부재·소스270개/순수 Flow6/readonly fixture1·dependency/origin 전후 대조가 통과했다. 직접 영향 기존 boundary self3/unit208도 guard0으로 통과했다. 최종 독립 읽기 리뷰에서 추가 blocker0이며 검토한 runtime/client/checker bytes가 그대로임을 확인했다. 검토 뒤 이 결과 문장만 추가했다. exact-head CI/PR 결과는 최종 게시 때 별도로 대조한다. 새 runner/모드/CI/guard/AI 입력·설치 변경은 없다.

게시 뒤 통제 시계 회귀에서 원 run 기한만 남은 경우 3초 waiter를 넘긴 반환을 저장하는 경계를 재현했다(원 source235통과/음성1실패). 최초 waiter 시작+짧은 잔여를 별도 절대기한으로 고정하고 timeout context 종료 뒤 다시 확인해 기존 TIMEOUT/claimed fence로 처리하도록 보완했다. 수정 source self5/unit236·PG2의16그룹과 독립 delta 리뷰 blocker0을 확인했다. AIClient·기존 boundary 회귀 bytes는 그대로여서 해당 검사를 반복하지 않았다. 원 실패/PG1/게시 기록은 보존한다.

## 남은 경계

완료 대상은 기수락 run의 이번 claim ACK에 기반한 단일 synthetic boundary 호출과 기존 저장 연결이다. 실제 AI router·compiled graph·외부 HTTP/Google·운영 DB/배포·실제 OpenAI/KIS·사용량 정산·Supervisor dispatch는 미검증/미연결이다. 현재 wire는3초/synthetic이며 provider_authority=false·settlement=false, 전액 hold와 원 기한/ID를 유지한다. waiter timeout은 physical worker 종료나 실행·비용0의 증거가 아니다. 추가 실제 예약·키/env 접근·provider 호출·설치는0이다.
