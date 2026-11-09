# Flow 사용 한도 설정 안내

이 문서는 소스 기반 형태/전제 안내다. 실제 환경 값·운영 DB 적용은 확인하지 않았으며 종목·횟수·금액 선택이나 활성화·재기동·migration을 수행하지 않는다. 실행 가능한 임의 활성 예제도 제공하지 않는다.

## 다섯 raw 설정

| 이름 | 기본값 | 허용 형태 |
|---|---|---|
| FLOW_USAGE_LIMITS_ENABLED | 문자열 false | 정확한 문자열 true만 새 접수 활성 |
| FLOW_SUPPORTED_TICKERS | 빈 문자열 | 쉼표 구분·trim 후 중복 없는 ASCII6자리, 등록 Stock도 필요 |
| FLOW_USER_DAILY_REQUEST_LIMIT | 문자열0 | 양의10진 정수 문자열, signed64-bit 이내·선행0 금지 |
| FLOW_SERVICE_DAILY_REQUEST_LIMIT | 문자열0 | 양의10진 정수 문자열, signed64-bit 이내·선행0 금지 |
| FLOW_SERVICE_DAILY_BUDGET_USD | 문자열0 | 양의 고정소수 USD, 소수 최대9자리·길이 최대30·nanoUSD 환산 signed64-bit 이내 |

지수·달러기호·부호·NaN·실수/boolean 등 다른 타입은 허용하지 않는다. 비활성/잘못된 설정/지원되지 않는 종목은 새 접수403 FEATURE_UNAVAILABLE, 유효 기간 한도 소진/blocked는429 USAGE_LIMIT_EXCEEDED다. 새 설정 전에는 새 분석이 차단된다. GET·기존 동일키 조회/원 snapshot 게시 복구·legacy는 새 정책 파싱으로 막지 않는다.

## 주입·적용 시점과 전제

Backend [Settings](../backend/src/shared/config.py)는 고정 backend/.env 또는 process 환경변수를 읽고 process 값이 우선한다. 전역 Settings는 startup에 생성되므로 수정 후 모든 Backend worker의 재기동/배포 환경 반영이 필요하다. 파일 편집을 이미 실행 중인 프로세스가 자동 감지한다고 가정하지 않는다. 이 작업은 실제 파일 열람/변경이나 재기동을 하지 않는다.

로드된 enabled/지원 종목은 새 admission에 적용된다. 일일 기간은 검증된 DB admission 시각의 KST 자정~다음 자정이며 사용자 as_of/브라우저 시계가 아니다. 최초 service bucket의 서비스 횟수·예산·사용자 횟수 snapshot을 그날 새 사용자도 사용한다. 숫자 변경은 기존 bucket을 재설정하지 않고 다음 기간 최초 bucket에 적용한다. 한도 변경을 위해 기존 실행/예약·unknown을 초기화하지 않는다.

새 코드 사용에는 migration [c18001a7e0001](../backend/docs/migrations.md#cf-018-새-한도-원장-migration)이 전제다. 운영 DB 적용은 별도 승인·대상 검증이 필요하고 본 문서는 실행 허가가 아니다. 기존 Frontend/Backend/AI FLOW_ANALYSIS_ENABLED, AI FLOW_ENGINE_EXECUTION_ENABLED, service 인증·일치하는 token, 앱 session/CSRF/Origin 등 [실연동 전제](flow-live-readiness.md)도 별도로 필요하다. 이번 작업에서 어느 설정도 활성화하지 않았다.

## 예약·추정·청구의 구분

실행당 **$0.9135는 보수 예약**이며 실제 사용액·청구액·지출 승인이 아니다. Backend가 실제 수신한 독립 검증 가능한 usage만 고정 표준단가로 추정 정산한다. 누락/body 유실/timeout/unknown은 잔여 hold이며 날짜가 바뀌어도 원 기간에 귀속한다. 실패·보고서 삭제·시간 경과는 승인 횟수나 불명 예약의 자동 환불이 아니다. cached 미보고는 실측0이 아니라 할인 없는 보수 추정이다.

가격/모델/원자 예약·정산의 정본은 [기존 usage 계약](contracts/flow-usage-v1.md)이다. 이 단계는 편입 Flow만 다루며 다른 관점·앱 밖 API 비용·실제 청구서나 KIS 요금을 통제/검증했다고 주장하지 않는다.

근거: [raw parser](../backend/src/modules/analysis/domain/usage.py), [최초 bucket 정책/예약](../backend/src/modules/analysis/application/usage_service.py), [기간 SQL](../backend/src/modules/analysis/infrastructure/usage_repository.py), [이번 작업 기록](work/CF-019-flow-quality-delete-ux.md).
