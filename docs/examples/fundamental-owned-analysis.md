# Fundamental production 연결과 인수 안내

CF-015 이후 [생산용 adapter](../../backend/src/modules/fundamental/application/analysis_adapter.py), [고정 profile](../../backend/src/modules/fundamental/application/analysis_profile.py), [공통 coordinator](../../backend/src/modules/analysis/application/coordinator.py), [owner-aware writer](../../backend/src/modules/fundamental/application/report_service.py)는 이미 연결돼 있다. writer를 새로 구현할 단계가 아니다. CF-013의 [미등록 합성 예제](fundamental-analysis-adapter.md)는 당시 계약 설명이며 production 경로와 구분한다. 코드 연결 및 합성 주입·자기 PG 검증이 실제 공급자/재무 품질 수용을 뜻하지 않는다.

## 고정 HTTP 경계와 필드 지도

Backend의 `/api/fundamental/analyses`는 `ticker/question/idempotency_key/allow_analysis:true`만 받고 실제 principal을 사용한다. 서버 admission DB 시각을 한 번 고정하며 client as_of는 거절한다. AI `/internal/fundamental/analyze`의 전체 envelope는 다음 필드다.

`schema_version`, `analysis_id`, `admission_request_id`, `attempt_id`, `fingerprint`, `requested_at`, `deadline_at`, `spec`, `request`.

| 공통 요청 문맥 | nested engine 입력 |
|---|---|
| `admission_request_id` | `request_id = req-<UUID hex>` |
| `attempt_id` | `trace_id = trace-<UUID hex>` |
| `ticker` | `ticker` |
| `question` | `query` |

nested `request`는 정확히 `request_id/trace_id/ticker/query` 네 필드이고 기존 `analyze_fundamental_public`에 전달된다. `requested_at`/deadline은 요청 문맥이다. `fundamental.request-context.v1`은 원천 금융자료 snapshot이나 역사 시점 재현 보장이 아니다. 원 JSON/UUID/extra/0/null을 보존하고 child.report_id·ratio 외부참조를 검사한다.

## 이미 연결된 저장 경계

`FundamentalReportService.stage_report`는 실제 principal·동일 session과 원 report_id/question/admission-frozen stock_name을 받아 root·자식·정확히 한 owner index를 flush만 한다. claim/owner/state/충돌/삭제, commit/rollback은 coordinator/service 책임이다. root와 index owner 일치, legacy NULL 비귀속, 원 snapshot 선보존과 원자 publication·tombstone은 재구현 대상이 아니다. owner=None/자체 commit의 legacy create/save/_persist를 호출하지 않는다.

상태 GET은 dispatch/publication을 하지 않는다. 만료 bookkeeping은 commit될 수 있다. `result_ready`의 명시 same-key POST는 기존 snapshot 게시만 복구하고 AI를 재호출하지 않는다. 타인 결과·ownerless legacy·공개 save·전량 삭제·HTML/PDF는 닫힌다.

## 운영 전제와 도메인 인수

- Backend/AI의 `FUNDAMENTAL_SERVICE_TOKEN` 일치(최소32 UTF-8 bytes), Backend/AI/Frontend의 `FUNDAMENTAL_ANALYSIS_ENABLED`, AI의 `FUNDAMENTAL_ENGINE_EXECUTION_ENABLED`가 운영 전제다. 기본은 닫힘이며 여기서 값을 확인·설정하거나 켜지 않았다.
- migration `c15001a7e0001`, 등록 종목, 로그인 세션·CSRF·엄격 Origin/Host가 필요하다. 실제 운영 DB·Google 세션·배포 연결은 미확인이다.
- 준영 님 인수 책임은 실제 재무 계산·자료 선택·프롬프트, 원천 금융자료 snapshot/시점, 도메인 검증과 품질이다. 서비스/공급자 자격·호출/재시도·비용·배포 확인도 실제 연동 전에 남아 있다.
- 현재 payload 생성기는 root `as_of`와 `created_at`에 엔진 생성 시각을 기록한다. 이는 자료 기준일이 아니다. 실제 재무 기간·공시 시점과 구분하며 누락 시 unknown/null을 유지한다.
- HTTP 대기 종료는 실제 하위 실행·과금 중단을 보장하지 않는다. 1-slot은 실제 worker/default executor 완료까지 유지되는 프로세스별 제한이다.

[계약](../contracts/fundamental-analysis-v1.md)과 [CF-015 실행/미검증 기록](../work/CF-015-fundamental-owned-analysis.md)을 따른다. 실제 값·키·캐시·공급자·운영 DB는 이번 문서 점검에서 읽거나 사용하지 않았다.
