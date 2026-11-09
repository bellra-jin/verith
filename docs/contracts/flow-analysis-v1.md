# Flow 인증 분석 v1

실제 분석은 receipt-only 접수·합성 데모와 별개다. `/research` → 동일 origin BFF → Backend POST `/api/flow/analyses`와 GET `/{analysis_id}`로 연결하며 기본 비활성이다. POST는 ticker/question/UTC as_of/idempotency_key/strict allow_analysis:true만 받는다. 사용자 세션·CSRF·Origin·owner 검사는 Backend 책임이며 private/no-store를 유지한다.

Backend는 종목 이름·후보 기준일·실행 사양과 120초 claim을 고정한다. 확인된 claim commit 승자만 Flow 전용 내부 HTTP를 한 번 호출한다. commit 결과 불명이나 running/unknown 재조회는 재호출하지 않는다. 125초 HTTP 총 대기와 협조적 provider 제한은 이미 전송된 동기 작업의 강제 종료를 뜻하지 않는다. 단일 AI 프로세스 slot은 실제 작업이 끝날 때 반환된다.

원본 v1 payload와 별도 수집 입력 snapshot을 상관 ID·종목·날짜·단위·finite 값·SHA와 대조하여 result_ready로 먼저 보존한다. 게시 재개는 이 snapshot만 사용한다. 기존 v1 root/자식/본인 index와 stored 전이는 같은 transaction이다. 확정 report ID 충돌은 terminal 실패이며 원본 삭제 후에도 같은 UUID로 게시하지 않는다. GET은 게시나 AI를 시작하지 않는다.

삭제는 session → analysis → root 순서로 잠그고 저장 연결과 root version을 재확인한다. root/index 삭제와 deleted tombstone을 같은 transaction으로 처리하며 요청·입력·결과 본문을 제거한다. ID·fingerprint·hash만 남아 재노출을 막는다. 기존 stock과 관계없는 legacy/다른 owner 자료는 보존한다.

양쪽 FLOW_ANALYSIS_ENABLED와 AI FLOW_ENGINE_EXECUTION_ENABLED는 기본 false다. FLOW_SERVICE_TOKEN은 서버 전용 최소 32 UTF-8 bytes다. 실제 활성화에는 전용 자격·허용 자료·공급자 조건·호출/비용 한도·배포 동시성 확인이 필요하다. 초기 CF-012 검증은 deterministic engine/transport와 자기 격리 PG였다. 이후 CF-017 별도 실제 실행은 Google 로그인→삼성전자005930 KIS/OpenAI 분석→저장→같은 결과 재조회→UI 삭제·404와 임시 자료/자원 정리를 확인했다. 이는 단일 종목·격리 환경의 증거이며 운영 전반·모든 종목·실제 청구서 검증을 뜻하지 않는다. 원분석 요청의 deleted enum은 UI에서 직접 확인하지 못했다.

## Flow 내부 오류 분류 (CF-017)

AI 내부 HTTP는 JSON/UTF-8/크기/DTO 입력 오류만 `422 INPUT_INVALID`로 처리한다. 유효 요청 뒤 일반 engine/provider 오류와 `ValueError`는 `503 SERVICE_UNAVAILABLE`, deadline·KIS/SDK timeout은 `504 DEADLINE_EXCEEDED`, 결과 추출·snapshot binding·canonical/크기 계약 위반은 `502 RESULT_CONTRACT_INVALID`다. gate/auth·no-store와 실제 sync 작업 종료까지 slot을 보유하는 조건은 유지한다.

Backend의 Flow client는 서비스 주소/포트/token 설정 오류와 내부401/403·일반5xx를 unavailable로 구분한다. 명시적 bounded JSON의502 `error.code=RESULT_CONTRACT_INVALID`와 잘못된200 결과만 contract 오류다. 기존400/409/422 입력 거부는 validation 오류다. coordinator는 validation→`failed/DATA_INSUFFICIENT`, contract→`failed/RESULT_CONTRACT_INVALID`, unavailable/timeout→`unknown/SERVICE_UNAVAILABLE`를 기록한다. 이는 AI 내부 상태와 Backend 분석 POST/GET의 기존200/202 응답을 구분하는 설명이며 자동 재실행을 추가하지 않는다. [합성·실제 실행 결과와 남은 한계](../work/CF-017-flow-error-classification.md)를 따른다.
