# 분석 adapter 계약 v1

Flow 제품 경로에서 사용하는 작은 Protocol이다. 요청 생성, 도메인 응답 검증/고정, 동일 transaction의 report stage만 adapter 책임이다. principal·claim·멱등·기한·상태·commit/rollback·삭제는 caller service 책임이며 범용 실행 원장이나 plugin registry가 아니다.

| 타입/동작 | 계약 |
|---|---|
| AnalysisContext | 불변 analysis/admission/attempt/owner UUID, operation, 요청 fingerprint, UTC as_of/deadline. 매 HTTP envelope request_id와 최초 admission ID를 구분한다. owner는 검증된 Backend principal에서 온다. |
| FrozenAnalysisResult | 원 report UUID, context, input/result schema ID, finite canonical JSON 문자열·각 SHA, 식별/hash 결합 SHA. dict를 원본으로 보관하지 않는다. 중복 key·NaN/Infinity·비canonical/hash/결합 변조는 거부한다. SHA는 무결성 대조이며 인증/서명이 아니다. |
| build_request | 고정 입력에서 내부 DTO를 새로 만든다. 사용자 URL/provider/owner 선택을 추가하지 않는다. |
| validate_and_freeze | 공통 JSON/hash 검사 위에 각 도메인의 request/trace/ticker/날짜/원 report ID 검증을 적용한다. 정상 0/null/가산 필드와 원본 수치를 보존한다. |
| stage | caller session/principal/frozen을 받아 검증·write·flush까지만 수행하고 StagedReportReference를 반환한다. flush는 commit 성공이 아니다. commit/rollback·새 session·AI 호출·owner 결정·상태 전이는 금지다. |

[Flow 구현](../../backend/src/modules/flow/application/analysis_adapter.py)은 기존 Flow request/result 검증을 재사용한다. 기존 v1 payload/입력 snapshot과 hash를 그대로 보존하고 기존 stage_report가 실제 principal/세션을 검증한다. Flow service의 claim ACK 불명 dispatch0, result_ready 선보존, snapshot-only 게시 재개, 원자 stored·충돌 terminal·삭제 tombstone은 변경하지 않는다. GET은 실행/게시를 시작하지 않는다.

running은 실행권 고정, result_ready는 snapshot 확보, stored는 root/자식/index와 완료가 원자 commit된 상태다. failed는 확정 실패, unknown은 외부 실행/결과 불명, deleted는 비공개 tombstone이다. 같은 owner/operation/key·입력은 같은 실행, 다른 입력은409이며 unknown을 자동 재실행하지 않는다. 기존 HTTP 401/404/409/422 및 안전 envelope는 caller가 유지한다. 공통 모듈은 Flow ErrorCode를 역으로 import하지 않는다.

[미등록 재무 예제](../examples/fundamental-analysis-adapter.md)는 합성 요청 fixture와 메모리 writer만 사용한다. 실제 재무 service의 owner=None/자체 commit 경로는 연결하지 않는다. 실제 금융 원천자료 snapshot·사용자 소유 게시·실제 공급자 사용을 보장하는 공통 계층이 아니다.
