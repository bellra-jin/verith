# Supervisor core v1

`supervisor.core.v1` / policy `supervisor.flow-core.1`의 공통 계약 정본이다. 기존 [Flow 분석](flow-analysis-v1.md)과 [usage](flow-usage-v1.md), Fundamental wire·fingerprint·저장 snapshot은 바꾸지 않는다.

## 의미와 계획

`MeaningFrame`은 불변 원질문/hash, active·negated 종목 mention과 정확한 evidence span, requested·negated views, typed 조건, unresolved slots, 최대4 revision/8 typed clarification answers와 해석 출처를 보존한다. 답변 evidence는 원문이 아닌 해당 answer ID/텍스트의 offset이다. 모델 제안은 검증 대상이며 canonical 종목·권한·capability의 근거가 아니다. 명시 종목·부정·기간 조건을 설명 없이 제거한 제안은 채택하지 않는다.

결정론 경로는 제한된 명시 표현만 처리한다. production meaning gateway는 unavailable이며 typed fake로만 검증한다. 실제 모델 품질·일반 NLU·완료된 대화 기억을 보장하지 않는다. 정보 부족은 명확화하고 다중 종목·시장 전체는 단일 Flow로 임의 축소하지 않는다.

`Plan`은 요청 관점, 연결 capability, 선택 관점을 구분한다. 현재 실행은 Flow 하나다. Technical·재무·거시·News의 실행을 열지 않는다. 고정 관측창·모든 주체를 유지하는 Flow가 이행하지 못하는 주체 focus/제외·과거 cutoff·기간 조건은 원조건으로 남긴다. `required_waivers`의 조건 ID와 부분 범위에 별도 명시 동의해야 한다. 확정 snapshot 및 Outcome의 `effective_scope`는 실제 동의한 고정 관측창/주체 유지/waiver를 원조건과 함께 추적한다.

semantic plan hash는 정렬된 finite JSON의 SHA-256이다. 원문/답변/revision·canonical resolution/ref·조건·policy·capability·선택을 포함하고 transport ID·준비 시각·미배정 Flow as_of는 포함하지 않는다. stock master 변경으로 첫 확정 계획이 달라지면 stale 재확인하며, 기존 binding replay는 최초 admission snapshot을 유지한다.

## HTTP 경계

| 경로 | 동작 |
|---|---|
| POST `/api/supervisor/core/prepare` | 비영속 의미 확인→필요할 때 canonical resolver1회→continuation |
| POST `/api/supervisor/core/requests` | 명시 동의·고정 owner/key binding 확정→기존 owned Flow 호출 또는 같은 입력 복구 |
| GET `/api/supervisor/core/requests/{supervisor_id}` | owner binding과 Flow 상태 관측. model/resolver/provider·snapshot 게시0 |

Next는 동일 origin `/api/private/supervisor/core/...` 세 경로만 전달한다. transport는 `schema_version/request_id/trace_id/data/error`이며 data/error는 상호 배타다. 요청 body16384/decoded 응답65536 bytes, 준비 전체15초, confirmed POST140초/BFF145초다. identity encoding·no redirect·trust_env=False와 기존 service token 경계를 유지한다. 세션/Origin/CSRF·private no-store·고정 오류가 적용된다. 오류 원본문·query·token을 출력하지 않는다.

AI 내부 `/internal/supervisor/core/plan`은 start→검증된 mention의 도구 요청→Backend canonical resolution→continuation이다. Backend에 자연어 classifier를 복제하지 않는다. 의미 모델5/resolve3/continuation3초는 전체15초 안에 속하며 retry0이다. 응답 전 fresh DB transaction에서 실제 세션을 재검증한다. legacy analyze/executor·rewrite·직접 FlowAdapter 실행은 닫힌다.

## Immutable binding과 기존 실행

`supervisor_request_bindings` 한 표는 owner/client key digest에 유일한 확정 계획/Flow body/hash만 연결한다. 실행 상태·예약·attempt·결과를 복제하지 않는다. Flow body는 원질문·확정 canonical ticker·DB 시각 as_of·binding UUID의 고정 key·명시 opt-in이며 원래 AnalysisService/FlowUsageControl을 사용한다.

owner/key의 기존 행부터 확인한다. 동일 입력은 고정 snapshot을 사용하며 모델/resolver0, 다른 질문/답변/선택/동의는409다. 최초 부재가 확인된 경합에서는 의미 검증이 두 번 일어날 수 있으나 UNIQUE 승자 binding만 사용한다. binding commit ACK가 불명이면 최초 Flow0이다. 후속 primary 조회로 행이 확인된 replay만 복구하며 부재/조회불명을 구분한다.

`handoff_before=confirmed_at+120초`는 Flow run이 없을 때 **Flow 호출 직전 DB 시각 검사**다. 기존 Flow 내부 lock 대기/admission의 원자 시각 상한은 아니다. binding lock/바깥 transaction을 유지한 채 Flow를 호출하지 않는다. 기존 실행 원장·claim/fence·deadline·usage·멱등·snapshot만이 실행 권위다.

## Outcome과 삭제

관점별 상태와 전체 coverage는 별개다. 미연결 관점은 not_executed, stored Flow만 있는 혼합 질문은 partial이다. running은 pending, result_ready는 저장 성공이 아니며 explicit same-key POST만 snapshot 게시를 복구한다. unknown은 failed/cancelled/환불이 아니다.

Flow 보고서 삭제의 기존 transaction/잠금 순서(session→analysis→root) 뒤 binding 민감 JSON도 redact한다. 실패하면 보고서·binding 모두 rollback한다. hashes/owner/key/usage는 보존한다. 관측 뒤 binding redaction을 다시 읽어 삭제와 경합한 이전 질문/계획/본문을 반환하지 않는다. deleted는 plan/effective scope/Flow 참조를 숨긴다. migration 선행조건을 표 부재 무시로 대체하지 않는다.

## UI와 검증의 한계

기본 `/research`는 단일 SupervisorChat이다. 기존 `analysis_id` 및 owner별 Flow pending은 원래 AnalysisEntry로 복구하고, Sup pending은 별도 schema/owner 저장소를 쓴다. direct supervisor URL에 고정 pending이 없으면 GET-only다. session401/계정·URL·visibility/generation 변경은 비공개 표시/동의를 무효화한다. 원입력과 key는 보존한다.

[디자인/상태 기준](../design/supervisor-core.md)과 [실행 기록](../work/CF-022-supervisor-core.md)은 실제 증거 수준을 구분한다. Backend 합성 HTTP/소유 PG는 실제 모델·브라우저·운영 배포의 검증이 아니다.
