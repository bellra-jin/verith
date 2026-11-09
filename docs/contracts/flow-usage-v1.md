# Flow 사용 한도·관측 비용 v1

현재 편입 operation은 `flow.analysis.v1` 하나다. 한도는 화면이 아닌 인증 사용자→operation→analysis/attempt→공급자 call에 귀속한다. 최종 UX와 후속 순서는 전체 작업 운영 v1.2 §4.1을 참조하며 여기에서 재정의하지 않는다. 현재 전용 화면·종목코드 입력은 그대로다. Fundamental·Technical·Industry·거시·Supervisor·CLI와 앱 밖 API 비용은 이 원장에 편입되지 않았다.

## 새 접수의 닫힌 기본값

`FLOW_USAGE_LIMITS_ENABLED`, `FLOW_SUPPORTED_TICKERS`, `FLOW_USER_DAILY_REQUEST_LIMIT`, `FLOW_SERVICE_DAILY_REQUEST_LIMIT`, `FLOW_SERVICE_DAILY_BUDGET_USD`는 원래 문자열/미설정 값을 유지한다. strict 파싱은 기존 key 조회 뒤 새 admission에서만 한다. 기본 false/빈 목록/0, 잘못된 설정과 지원 범위는 새 접수를403 `FEATURE_UNAVAILABLE`로 닫는다. 유효한 기간 한도 소진/blocked는429 `USAGE_LIMIT_EXCEEDED`다. 기존 key 조회·snapshot 게시 복구·GET·legacy 복구는 새 정책 오류에 막히지 않는다. 운영 값은 이번 변경에서 활성화하지 않았다.

서버의 검증된 DB admission 시각으로 KST [00:00, 다음 날00:00)의 UTC 경계를 저장한다. 사용자 as_of/브라우저 시계는 기간 키가 아니다. 최초 service 기간의 서비스 횟수·금액·사용자 횟수 정책을 고정하고, 새 user 기간도 그 snapshot을 사용한다. 설정 변경으로 같은 기간의 bucket을 새로 만들지 않는다. 긴급 비활성 flag는 새 실행에 즉시 적용한다. 등록된 Stock과 중복 없는 ASCII6자리 지원 목록이 모두 필요하다.

## 예약과 보장 범위

돈은 정수 nanoUSD다. 고정 가격 ID는 `openai.gpt-5.4-mini.standard.2026-11-09.v1`이며 입력750·cached75·출력4500 nanoUSD/token이다. 요청 모델은 gpt-5.4-mini, 허용 응답 모델은 정확히 gpt-5.4-mini와 gpt-5.4-mini-2026-03-17이다.

새 실행은 OpenAI3회 각각 input400000/output1000의 보수 상한, 합계 **913500000 nanoUSD = $0.9135**를 먼저 예약한다. 실제 사용액이나 지출 승인이 아니다. 전송 prompt는 UTF-8 32768 bytes, 응답 content는16384 bytes를 제한한다. byte를 정확한 provider token 수라고 부르지 않는다. SDK retry0·n1·default tier와 기존 timeout/재생성2회를 유지한다.

보장 범위는 편입 Flow의 원자 admission/예약 제한과 수신 usage의 표준단가 환산이다. 실제 청구서·세금/환율·다른 tier/모델·KIS 요금·미편입/앱 밖 호출은 보장하지 않는다. KIS 요금은 미산정 NULL이며 무료로 기록하지 않는다.

## 영속 경계

`analysis_usage_periods`, `analysis_usage_reservations`, `analysis_provider_calls`를 사용한다. 새 run ID와 reservation ID는 같으며 owner/operation/attempt/grant와 원 user/service 기간을 연결한다. bidirectional composite FK와 deferred commit-time 검증으로 고아·다른 owner/기간/scope 연결을 거부한다. legacy NULL은 backfill하지 않는다. 원 보고서·질문·prompt·credential은 비용 원장에 저장하지 않는다.

잠금 순서는 기존 session→run 다음 service period→user period→reservation→call이다. admit 승자만 같은 transaction에서 두 기간의 횟수와 최대 비용을 예약하고 claim commit ACK 뒤1회 dispatch한다. 중복 loser/거절/확정 rollback은 새 차감0이다. ACK 불명은 재실행·해제 근거가 아니다. 고유 실행 횟수는 실패·unknown·삭제로 되돌리지 않는다.

`input_snapshot.provider_usage`는 원 v1 payload와 별도인 versioned metadata다. OpenAI3+KIS token2+공급2+시세2의9개 고정 슬롯을 둔다. KIS cache hit는 token 시도0이고 retry는 data4회 안에 포함된다. timeout 계산·sleep·SDK constructor만으로 실제 호출을 세지 않는다.

Backend가 받은 dict의 독립 검증 가능한 receipt만 현재 결과 채택·세션 재인증보다 먼저 원 예약에 정산한다. 실제 작업 종료가 확인된 미호출과 유효 관측 부분만 해제한다. unknown/미수신/취소·timeout/HTTP 유실은 최대 잔여 예약을 유지한다. 잘못된 결과 payload·늦은 결과·세션 폐기는 유효 usage를 버릴 이유가 아니며, 공개 결과의 auth/deadline/fence는 그대로다. 502/JSON/크기 오류 등으로 body가 없으면 내부 관측을 확정 수신으로 바꾸지 않는다. callback/재전송 worker/수동 정산 API는 없다.

같은 최종 증거는 no-op, 다른 최종 증거는 거부한다. unknown은 첫 유효 확정 증거로 전환할 수 있지만 `attempted=True`는 False/NULL로 되돌릴 수 없다. cached 미보고는 실제0이 아닌 할인 없는 보수 추정이다. usage 누락/오류는0이 아니다. 모델 불일치·관측 가능한 상한 초과는 정산 가능성과 독립적으로 정제된 증거를 보존하고 blocked를 commit한다. 알 수 없는 비용을 임의 청구하거나 실제 추정을 cap에 맞춰 자르지 않는다.

정산·held 감소·추정 spend 증가는 한 transaction이다. 정산 ACK 불명은 동일 receipt 재처리로 확인하며 원래 기간에 귀속한다. 보고서 삭제/시간 경과는 unknown 환불이나 비용 원장 삭제 사유가 아니다. 본문 삭제 tombstone과 최소 회계 기록의 보존은 구분한다.

구현/직접 검사·미검증·실패 이력은 [작업 기록](../work/CF-018-flow-usage-limits.md)에 남긴다.
