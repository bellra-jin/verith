# Flow 인증 분석 v1

실제 분석은 receipt-only 접수·합성 데모와 별개다. `/research` → 동일 origin BFF → Backend POST `/api/flow/analyses`와 GET `/{analysis_id}`로 연결하며 기본 비활성이다. POST는 ticker/question/UTC as_of/idempotency_key/strict allow_analysis:true만 받는다. 사용자 세션·CSRF·Origin·owner 검사는 Backend 책임이며 private/no-store를 유지한다.

Backend는 종목 이름·후보 기준일·실행 사양과 120초 claim을 고정한다. 확인된 claim commit 승자만 Flow 전용 내부 HTTP를 한 번 호출한다. commit 결과 불명이나 running/unknown 재조회는 재호출하지 않는다. 125초 HTTP 총 대기와 협조적 provider 제한은 이미 전송된 동기 작업의 강제 종료를 뜻하지 않는다. 단일 AI 프로세스 slot은 실제 작업이 끝날 때 반환된다.

원본 v1 payload와 별도 수집 입력 snapshot을 상관 ID·종목·날짜·단위·finite 값·SHA와 대조하여 result_ready로 먼저 보존한다. 게시 재개는 이 snapshot만 사용한다. 기존 v1 root/자식/본인 index와 stored 전이는 같은 transaction이다. 확정 report ID 충돌은 terminal 실패이며 원본 삭제 후에도 같은 UUID로 게시하지 않는다. GET은 게시나 AI를 시작하지 않는다.

삭제는 session → analysis → root 순서로 잠그고 저장 연결과 root version을 재확인한다. root/index 삭제와 deleted tombstone을 같은 transaction으로 처리하며 요청·입력·결과 본문을 제거한다. ID·fingerprint·hash만 남아 재노출을 막는다. 기존 stock과 관계없는 legacy/다른 owner 자료는 보존한다.

양쪽 FLOW_ANALYSIS_ENABLED와 AI FLOW_ENGINE_EXECUTION_ENABLED는 기본 false다. FLOW_SERVICE_TOKEN은 서버 전용 최소 32 UTF-8 bytes다. 실제 활성화에는 전용 자격·허용 자료·공급자 조건·호출/비용 한도·배포 동시성 확인이 필요하다. 이번 검증은 deterministic engine/transport와 자기 격리 PG이며 실제 KIS/OpenAI/Google·브라우저 E2E나 품질/비용 검증이 아니다.
