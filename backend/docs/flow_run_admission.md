# Flow 접수·멱등·본인 실행 상태 재조회

CF-003의 개발용 접수 기반이다. `receipt_only` 행을 보존하며 분석·가짜 AI·worker를 실행하지 않는다.
기존 Flow 결과의 저장/조회/삭제 계약과 분리한다. 구현·검증 상태는
[작업 기록](../../docs/work/CF-003-flow-run-admission.md)을 따른다.

## API와 기본 비활성 경계

`FLOW_RUN_ADMISSION_ENABLED` 기본값은 false다. 비활성 상태는 dependency/DB 호출 전
403 `FEATURE_UNAVAILABLE`이다. 실제 private 설정을 바꾸거나 자동 활성화하지 않는다.

| method / path | 의미 |
|---|---|
| POST `/api/flow/runs` | 새 접수/동일 요청 재사용 모두 commit 후 202. 상대 Location은 `/api/flow/runs/{run_id}` |
| GET `/api/flow/runs/{run_id}` | 본인 상태 200. 타인과 없는 ID는 같은 404 |

목록·DELETE·execute·retry·trailing slash·중첩 경로·`/v1/runs` alias는 열지 않는다.
Next/BFF/UI와 기존 공개 save/전체 삭제 차단은 변경하지 않는다.

입력은 ticker(기존 strict ASCII 6자리), question(strict 비공백·최대 2,000문자),
timezone-aware ISO as_of, body idempotency_key(strict 비공백·UTF-8 1~256bytes) 네 필드뿐이다.
NUL/lone surrogate·epoch·naive 시각·owner/상태/ID/payload 추가 필드를 거부한다.
유효한 질문/키의 앞뒤 공백·대소문자·Unicode는 보존하고 as_of만 UTC로 정규화한다.

기존 앱 세션 쿠키로 principal을 검증한다. POST는 정확한 Host/Origin/CSRF와 세션 SHARE 잠금을
사용하며 service에서도 세션을 재검증한다. body/header의 임의 owner는 인증이 아니다.

## 응답과 멱등

새 경로만 `CommonResponse[FlowRunState]`의 request_id/data/error를 사용한다.
외부 request_id는 HTTP 요청마다 Backend가 새로 발급한다. data.request_id는 최초 접수 추적 ID이고
run_id/예약 attempt_id와 함께 replay/GET에서 불변이다. 상태는 pending/not_stored,
report_id/error는 null이다. 예약 attempt UUID는 시도 행이나 실행권을 뜻하지 않는다.

모든 정상/오류/gate 거부는 `Cache-Control: private, no-store`, `Vary: Cookie, Origin`이다.
401 AUTH_REQUIRED, local Host 403 AUTH_REQUEST_INVALID, 404 RESOURCE_NOT_FOUND,
409 IDEMPOTENCY_CONFLICT, 입력/JSON/UUID 오류 422 INPUT_INVALID,
DB 획득·인증·commit·teardown 실패 503 SERVICE_UNAVAILABLE을 고정 메시지로 반환한다.
거부된 질문·키·cookie·CSRF·DSN·raw exception을 오류/로그에 넣지 않는다.

원문 키는 저장하지 않고 UTF-8 SHA-256 32bytes를 owner+operation 범위의 UNIQUE로 사용한다.
기존 fingerprint 규칙과 동일한 key 제외 UTC 정규화 입력을 함께 비교한다.
대상 유일 제약만 INSERT ON CONFLICT DO NOTHING RETURNING으로 처리하고, 미삽입이면 별도
READ COMMITTED SELECT로 확정 winner를 읽는다. 같은 입력은 원래 행을 수정하지 않고 재사용하며
다른 입력은 rollback/409다. 다른 owner의 같은 키는 별도 run이다.

## 영속 경계와 migration

새 `flow_runs` 하나만 추가한다. FK owner RESTRICT, operation flow, 계약 version 1,
키 digest 길이 32, 소문자 hex fingerprint 64, object JSONB request_input,
attempt_id UNIQUE, receipt_only/pending/not_stored와 finite created_at CHECK를 둔다.
stocks/report/root/자식/공통 index는 접수로 쓰지 않는다.

revision `c3001a7e0001`은 `c2001a7e0001` 뒤에 추가한다. 기존 revision/data backfill은 없다.
downgrade는 같은 transaction의 ACCESS EXCLUSIVE 잠금 후 nonempty이면 어떤 DROP 전에도 거부한다.
비어 있는 새 테이블의 downgrade/reupgrade만 격리 검사한다. 운영 데이터 삭제 절차가 아니다.

접수 SHARE가 먼저면 logout의 exclusive 잠금이 접수 commit까지 대기하며, revoke가 먼저 commit하면
이전 cookie의 POST/GET은 401이다. 실제 PostgreSQL 경합·rollback·migration/ASGI 검사와
mock-only unit을 구분한다. 실제 Google/브라우저/TCP/BFF/SSR/AI 연결은 이번 수용 범위가 아니다.
