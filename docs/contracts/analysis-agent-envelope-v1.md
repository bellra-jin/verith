# Analysis agent envelope v1

CF021의 비영속 내부 Technical boundary에서 사용하는 공통 wire 계약이다. 다른 agent의 기존 payload·fingerprint·auth/owner·저장 원형을 일괄 전환하지 않는다. [Technical 상세 계약](technical-boundary-v1.md)과 [직접 검증/한계](../work/CF-021-technical-boundary.md)를 함께 따른다.

## Header와 권위

Top-level은 `schema_version=analysis.agent.v1`, `request_id`, `trace_id`, `data`, `error`로 닫는다. 성공은 data만, 실패는 고정 error만 갖는다. 알려지지 않은 필드·중복 JSON key·비유한 숫자·숫자/boolean coercion과 유효하지 않은 UTF-8을 거절한다. 원문 query/token/예외 body를 오류로 돌려주지 않는다.

| 값 | 의미/권위 |
|---|---|
| request_id / trace_id | 호출자가 고정한 transport 요청/추적 ID |
| data.context.analysis_id | 기존 AnalysisContext의 분석 identity |
| admission_request_id / attempt_id | 접수/시도 identity, transport ID와 별개 |
| report_id | Backend immutable holder에 별도로 고정한 미게시 결과 ID |
| original_query / stock | 원 UTF-8 질문과 Backend가 공급한 canonical code/name/nullable market |
| requested_views / conditions | 요청 관점과 domain별 typed 조건. 알 수 없는 domain 조건은 버리지 않고 거절 |
| requested_as_of | 요청 cutoff. 실제 source coverage/생성시각과 구분 |

이번 요청의 ID는 모두 정확 UUID이고 서로 alias가 아니다. AI가 owner·provider URL·credential/model을 선택하지 않는다. 사용자 owner는 Backend AnalysisContext에만 있으며 AI wire에는 넣지 않는다. typed ID 자체가 인증/저장 완료 증거도 아니다.

## 현재 operation

`data.operation=technical.boundary.v1`, `requested_views=[technical]`, `conditions={profile:technical.multiframe.v1,periods:[3m,1y,5y]}`만 사용한다. wire의 context/stock/conditions는 닫힌 구조이며 임의 domain dict를 받지 않는다. 명시한 profile 기본값 외에 누락을 추정하거나 조건을 삭제하지 않는다. fingerprint는 operation/원질문/stock/requested_as_of/typed conditions의 canonical JSON SHA256이며 기존 Flow/Fundamental fingerprint에는 소급 적용하지 않는다.

성공 data는 `request_snapshot`, `request_sha256`, typed `result`, `coverage`, `execution_mode=synthetic`, `boundary_observed_at`이다. snapshot은 원 data를 lossless 보존하고 SHA는 원 요청 전체의 canonical JSON이다. validator가 만든 기본값/수치 변환을 원 JSON으로 재직렬화하지 않는다. Backend는 schema 외에도 요청 snapshot·ID·stock·조건·cutoff·hash와 엔진 ticker/request/as_of/trace를 값으로 대조한다. canonical 이름은 엔진의 resolved name으로 덮지 않는다.

error code는 FEATURE_UNAVAILABLE/AUTH_REQUIRED/INPUT_INVALID/SERVICE_UNAVAILABLE/DEADLINE_EXCEEDED/RESULT_CONTRACT_INVALID/BUSY이며 message는 `Technical boundary unavailable`로 고정한다. data/error의 상호 배타와 요청/응답 ID binding을 검증한다.

## 확장과 미완 경계

Backend/AI에 각각 순수 타입을 두고 공유 JSON fixture와 실제 합성 HTTP로 정합을 검증한다. Backend가 AI app/config를 production import하는 공유 모듈을 만들지 않는다. legacy TaskEnvelope rewrite/executor를 되살리지 않는다. 기존 public Supervisor는 Flow-only이고 이 내부 plan을 공개 ready/capability로 내보내지 않는다.

후속 재무에는 원질문과 별도/OFS·연결/CFS, 분기/latest·연수/years 등 typed 상세 조건을 보존해야 한다. 이번에 재무 interpreter/계산이나 다른 domain 실행 profile을 구현한 것은 아니다. 복합 관점·종합·멀티턴은 후속이다. News 신규 실행/수집은 제외한다. 실제 모델·공급자/운영 DB·브라우저·공개 Technical 실행은 이 계약의 합성 수용에 포함되지 않는다.
