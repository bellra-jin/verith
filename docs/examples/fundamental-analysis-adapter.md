# CF-013 당시 재무 합성 adapter 예제와 인수 조건

[예제 코드](../../backend/examples/analysis/fundamental_adapter.py)와 [합성 응답](../../backend/examples/analysis/fundamental-response.v1.json)은 production registry/router에 등록되지 않는다. 실제 재무 agent·service·DB·공급자는 호출하지 않는다. 기존 mirror로 shape를 검증하지만 mirror의 extra-ignore/coercion 출력을 원본으로 저장하지 않고, 검증에 사용한 JSON 전체를 canonical 본문/hash로 고정한다.

| 공통/입력 | 기존 재무 요청/결과 |
|---|---|
| admission_request_id | `request_id = req-<UUID hex>` |
| attempt_id | `trace_id = trace-<UUID hex>` ↔ `meta.trace_id` |
| ticker | 요청·응답 ticker 정확 대조 |
| question | 요청 query |
| as_of / owner_user_id | context에만 보존. 기존 재무 API에 지원하지 않는 시점 고정·owner 보장을 새로 주장하지 않음 |
| 원 report UUID | `meta.erd_payload.fundamental_report.id`를 채택, 새 ID 생성/교체 없음 |
| input schema | `fundamental.synthetic-request.v1`: 합성 요청 fixture, 실제 재무 원천자료 snapshot 아님 |
| result schema | `fundamental.agent-output.v1`: 원 JSON 전체·추가 필드·0/null 보존 |

예제는 `FundamentalExampleAdapter(context, ticker, question, writer=...)`로 만든다. writer가 없으면 stage는 fail-closed다. 명시 writer가 있어도 기존 Principal·실제 세션 검증과 context owner 일치를 유지한다. writer는 `(동일 session, principal, frozen)`을 받고 동일 원 report/owner의 StagedReportReference를 반환하며 adapter는 flush한다. unit은 합성 Principal/메모리 session과 mock된 auth 검증을 쓰므로 실제 재무 로그인/게시 통과가 아니다.

아래 목록은 CF-013 당시 production writer 연결 전의 인수 조건이다. CF-015에서 생산용 엔진 HTTP 경계·owner-aware stage-only writer·원자 저장·본인 조회/삭제가 연결됐으며 합성 주입/자기 PG 검증을 마쳤다. 현재 연결 지도와 남은 도메인/운영 책임은 [production 인수 안내](fundamental-owned-analysis.md)를 따른다. 아래를 writer 신규 구현 요청이나 실제 공급자 품질 수용 완료로 읽지 않는다.

CF-013 당시 인수 조건:

- context owner를 root와 정확히 한 index에 동일하게 적용하고 legacy owner NULL을 채택하지 않는다.
- 동일 caller transaction에서 원 report/자식/index를 stage/flush만 한다. 기존 재무 service의 owner=None·자체 commit을 그대로 호출하지 않는다.
- 재무 payload의 실제 수치/근거·원천자료/시점·schema/관계 검증과 서비스 인증을 확정한다. 이번 mirror shape 검증이 이를 대체하지 않는다.
- 실제 격리 PG에서 원자 저장/rollback·본인 조회/타인 거부·멱등·삭제/복구를 확인한 뒤 별도 production 연결을 검토한다.
- 실제 공급자 자격·허용 자료/약관·외부 전송·호출/비용 한도는 별도 확인한다. 이 예제는 실행 승인이 아니다.

[공통 계약](../contracts/analysis-adapter-v1.md)과 [이번 직접 검증/한계](../work/CF-013-analysis-contracts.md)를 함께 따른다.
