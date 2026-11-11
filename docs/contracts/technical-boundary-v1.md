# Technical boundary v1

[공통 envelope](analysis-agent-envelope-v1.md)의 CF021 비영속 적용을 기록한다. 아래 CF035는 별도 내부 저장을, CF036은 인증된 본인 저장 결과의 GET/BFF/화면 조회를 추가한다. Technical 실행·공개 save·Supervisor launch·사용 한도는 여전히 연결하지 않는다.

## Typed 입력과 단일 adapter

순수 내부 builder는 canonical stock과 명확한 단일 Technical 요청만 선택한다. resolver/LLM을 호출하거나 canonical 종목을 만들지 않고, Flow+Technical/종합/News/비개별종목·불명확한 질문은 실행 준비로 승격하지 않는다. 기존 공개 Supervisor 의미/계획과 별개다.

TechnicalBoundaryBinding은 기존 AnalysisContext와 별도의 report_id/request_id/trace_id·원 입력 canonical JSON을 frozen holder로 결합한다. AnalysisContext identity/필드는 확장하지 않는다. adapter build_request → 고정 AIClient → strict validate_and_freeze → chart_preview가 연결되며 freeze에는 context와 report_id를 각각 넘긴다. stage는 명시 비영속 오류이며 DB call은 없다. registry/coordinator profile로 등록하지 않는다.

profile은 `technical.multiframe.v1`, periods는 고정 순서3m/1y/5y다.3m·1y는D,5y는W다. 기존1d→1min 타입은 남지만 이번 profile의 요청은 지원하지 않는다. 원질문은 엔진 TechnicalAgentInput.query, stock은 ticker/name, transport request/as_of와 별도 trace_id를 명시 매핑한다. 실제 agent.run/graph/SDK를 import·실행하지 않는 injected async engine까지만 지원한다.

## Import/HTTP/동시 실행 경계

기본 router는 enabled=false/engine=None으로 닫고 health는 외부 자원 없는 liveness다. 무인증 legacy analyze는 전송/실행 전에 고정 unavailable로 거절한다. isolated `/internal/technical/boundary`는 injected engine+명시 enabled+합성 service token에서만 gate→constant-time 단일 token→bounded body/schema→engine 순서로 실행한다. 운영 credential/env/config를 탐색해 기본 engine을 만들지 않는다.

Backend client는 server-owned 고정 경로·retry0·redirect0·trust_env=false·Accept-Encoding identity를 유지한다. 요청16,384bytes, decoded 응답2,097,152bytes, fake boundary 대기 최대3초다. malformed/중복 header·oversize·불명 encoding/JSON은 고정 오류로 닫는다. 사용자 body에서 URL/token을 받지 않는다.

프로세스 전체 in-flight1이며 remaining budget을 task 생성/slot 점유 전에 검사하고 validation/projection 뒤에도 재확인한다. 만료 요청은 engine0/slot0으로 거절한다. 요청 waiter timeout/cancellation 후 shield된 소유 async task가 실제 종료될 때까지 busy slot을 유지하고 늦은 결과를 freeze하지 않는다. 이는 sync/thread/실제 SDK 작업·과금 중단 보장이 아니다. 실제 engine의85/90초 계약은 검증하지 않았다.

## 결과·시간·원값

AI 기존 TechnicalAgentOutput와 ChartPayload/ohlcv/intraday/enums를 재사용하고 Backend는 typed mirror로 검사한다. config의0.05/3 검증 literal만 순수 intraday_limits로 옮기고 config가 같은 이름으로 re-export한다. 나머지 config AST/계산·schema 제한은 유지하며 config/dotenv는 순수 검사에서 import하지 않는다.

coverage는 requested periods와 실제 chart의 available periods, 각 period/candle unit/start/end/count/status를 구분한다. 빈 chart의 count0/start/end=null, 미제공과 빈 제공도 구분한다. cutoff_validation=unverified, engine_generated_at/source_published_at=null와 engine_does_not_report 사유를 둔다. boundary_observed_at은 경계 관측시각이며 요청 cutoff나 source 생성시각이 아니다. fixture의 KIS 문자열은 typed 예시로 실자료 조회 증거가 아니다.

Backend가 검증한 preview는 기존 TechnicalChartsReadModel props로 lossless 투영한다. Frontend 순수 helper는 period/unit/coverage와 유한 JSON을 확인하고 별도 사본을 반환한다. 전체 envelope/auth 검증을 이 helper로 대체하지 않는다. report ID·stock·OHLCV/MA/RSI/annotation·null/0을 보존하며 새 신호/가격을 계산하지 않는다. 공유 fixture를 실제 기존 날짜/가격/RSI/level helper로 검사하며 Recharts/React mount·실제 chart 렌더는 미실행이다.

## 공개 연결의 선행조건

실제 engine의 인증/lazy startup·sync/SDK budget, owner-aware root/index/stage-only writer, 전용 owned profile/lifecycle/멱등/snapshot/게시·삭제, Technical usage, 실제 소유 PG가 먼저 필요하다. legacy owner=NULL writer/save·Flow usage로 대신하지 않는다. 이후 public planning/capability/BFF/UI·실제 차트 수용을 연결한다. 현재 결과는 합성 내부 계약/adapter 수용이며 전체 Technical 제품 완료가 아니다.
# CF-035 내부 stage와 본인 복구

앞의 CF021 비영속 adapter와 CF031 순수 복원은 그대로다. 별도 `TechnicalOwnedReportService`만 검증된
Principal과 결과에서 재생성하지 않은 독립 `TechnicalReadBinding`, L-bound `FrozenAnalysisResult`를 받는다.
L.operation은 `technical.owned-stage.v1`, caller TEXT는 정확히
`{"operation":"technical.owned-stage.v1","boundary_request":<원 B request>}`의 Python canonical JSON이다.
L은 caller TEXT의 SHA, B는 기존 semantic fingerprint다. 두 fingerprint·context·원문·조건·report/request/trace
ID를 각각 검증하고 기존 CF031 restore/CF021 chart validator를 재사용한다.

stage는 fresh DB session 검증/잠금 → 기존 root 잠금 → ID/index 충돌·기존 canonical stock 조회 → 순수 projection
순서다. stock master를 보강하지 않는다. root/신호/차트/위험/해석/검증·immutable snapshot·owned index 하나를
동일 transaction에 flush만 한다. commit/rollback은 호출자 책임이며 stage 반환은 저장 확정이 아니다.
기존 report/request 충돌은 덮어쓰지 않고 DB IntegrityError는 호출자가 rollback한다. legacy 생성/AI 호출·공개 save와
연결하지 않으며 새 execution profile/usage/admission 원장도 없다.

read도 실제 Principal/session lock을 검사한다. SQL에서 root/snapshot owner 일치와 전체 Technical index 정확1개·
동일 owner를 만족해야 row를 반환한다. legacy NULL owner, missing snapshot/index, NULL/타인/중복 index는 미존재다.
선택된 snapshot의 canonical TEXT·SHA·binding·ID와 root/모든 자식/index projection을 재검사한다. 저장 당시 session은
snapshot anchor와 index를 비교하며 현재의 새 로그인 session과 같을 필요는 없다. 변조는 원문 없는 고정 오류다.
동일 ID read는 commit ACK 불명 뒤 관측 수단이며 자동 재stage·AI·새 ID 생성은 없다.

snapshot TEXT의 배열/숫자/원문은 유지한다. detached preview의 charts만 고정 display_order로 정렬한다. 빈 chart와
미제공 chart는 기존 coverage로 구분하고 JSONB projection을 정확 bytes의 대체물로 삼지 않는다.
저장 기대값은 내부 durable anchor이며 전체 DB 임의 변경 권한자에 대한 외부 암호 증명이나 실제 engine/시장자료·
실행/비용 영수증이 아니다. execution_mode synthetic/cutoff unverified 한계를 유지한다.

공개 Technical 실행·HTTP/BFF/UI·Supervisor launch·사용 한도·실제 모델·삭제/follow-up 연결은 이번 범위가 아니다.


## CF-036 본인 저장 목록과 차트 조회

채팅의 ‘저장된 차트 결과 보기 · 조회 전용’ native link는 `/reports/technical`로 연결한다. 목록의 상세 링크는
기존 `/reports/technical/{report_id}` URL을 사용한다. 두 page는 force-dynamic/revalidate 0이며 기존 AppShell과
owned read client를 조합한다. legacy GET/trace/follow-up과 모든 KIS 수치 검증 주장은 상세에서 제거한다.
실행되지 않은 Technical 분석을 Supervisor Outcome으로 표시하거나 합성 결과를 실제 자료로 표현하지 않는다.

Backend의 새 GET은 `/api/technical/owned-reports`와 정확 canonical UUID 상세 하나뿐이다. configured auth와
실제 `request_principal(mutation=False)` 및 CF035의 fresh Principal/session 검증을 사용한다. 목록 query는 선택적
ASCII 6자리 stock_code, limit 기본 10·범위 1..20, offset 기본 0·범위 0..10000으로 닫는다. 중복·알 수 없는 key와
상세 query·추가 segment·비허용 method는 거절한다. 전체 Backend read는 dependency 정리를 포함해 15초로 제한한다.
기존 `/api/technical/reports`·save/analyze·DELETE·trace/follow-up·직접 AI proxy는 계속 닫혀 있다.

목록 SQL은 CF035와 같은 root/snapshot owner 및 전체 Technical index 정확 한 개·같은 owner 조건을 적용한다.
created_at DESC/report_id DESC의 고정 순서로 limit+1을 선택하고 선택된 모든 행을 기존 read로 다시 검증한다.
검증 실패 행을 조용히 건너뛰지 않는다. 카드에는 report_id, stock, created_at, requested_as_of,
execution_mode=`synthetic`, cutoff_validation=`unverified`만 반환하며 원질문·owner/session·실행 ID를 담지 않는다.
목록이 비어 있는 상태와 schema가 준비되지 않은 오류를 구분한다.

wire는 `schema_version=technical.owned-read.v1`, transport request_id, 상호 배타적인 data/error를 사용한다.
목록 data는 items/limit/offset/has_more다. 상세 data는 report_id/created_at/request_json/request_sha256/
result_json/result_sha256이다. request TEXT와 SHA는 검증된 별도 B 입력에서, result TEXT와 SHA는 별도 저장 결과에서
전달한다. result.request_snapshot을 independent expected로 사용하지 않는다. URL·outer ID·B report ID를 각각 대조한다.
기존 canonical TEXT를 JSONB나 validator의 재직렬화로 대체하지 않는다.

모든 성공/실패에 private/no-store와 Vary Cookie, Origin을 적용한다. 오류는 원문 없는 고정 code/message이며
401 AUTH_REQUIRED, 403 AUTH_REQUEST_INVALID/FEATURE_UNAVAILABLE, 404 RESOURCE_NOT_FOUND, 422 INPUT_INVALID,
502 RESULT_CONTRACT_INVALID, 503 SERVICE_UNAVAILABLE, 504 DEADLINE_EXCEEDED로 구분한다. 타인·legacy NULL·부재와
SQL eligibility 탈락은 같은 404다. UTF-8 serializer를 유지하고 목록 decoded cap은 65,536 bytes,
상세는 4,259,840 bytes다. 이 상세 한도는 B 입력 16 KiB와 결과 2 MiB TEXT의 string escaping 여유를 포함하며
저장본을 잘라서 반환하지 않는다.

same-origin BFF는 `/api/private/technical/owned-reports`와 정확 상세 GET만 고정 Backend 경로로 전달한다.
Cookie/Origin·local Host·중복 Cookie·spoofed 인증 헤더 제거, identity/no redirect/no-store를 유지하고 새 GET의
fetch와 decoded streaming을 합쳐 진입부터 20초의 비갱신 기한과 동일 wire 한도를 적용한다. 다른 Flow·준비·확인·
인증 기한이나 응답 한도는 바꾸지 않는다.

Frontend는 원 request/result TEXT의 UTF-8 SHA를 그대로 검사한 뒤 JSON.parse와 기존 CF031 unknown decoder에
전달한다. Python canonical JSON을 JS JSON.stringify로 다시 만들어 hash하지 않는다. 기존 decoder가 표시할 수 없는
unsafe integer 등을 거절하면 고정 표시 오류로 닫으며 원 DB TEXT를 반올림하지 않는다. 검증된 preview는 기존
TechnicalBoundaryPreview에 전달하고 합성·cutoff 미검증·생성/발행 시각 미보고·빈/미제공 상태를 유지한다.

조회는 전 session 확인 15초, BFF 20초, 후 session 확인 15초와 검증 여유를 포함한 전체 55초의 비갱신 동작이다.
중복 클릭은 동기 잠금과 pending으로 막고 settlement 뒤 명시 GET 재시도만 제공한다. session/owner 변경·401·
선택/URL 변경·hide/pagehide/back·unmount에서는 내용을 숨기고 이전 세대 응답 및 hash await 후 채택을 막는다.
reportId로 구분한 읽기 session과 기존 chart binding key가 첫 render의 옛 차트 노출과 새 보고서의 기간/brush/toggle
잔류를 차단한다. 동일 binding의 단순 rerender는 chart를 다시 mount하지 않는다. owner·원문·결과를 storage에 복제하지 않는다.

[집중 검사와 실제 화면 기록](../work/CF-036-technical-owned-read.md)은 단위/BFF 함수, 실제 소유 PG와 인증 ASGI,
합성 HTTP의 mounted React/Recharts를 각각 구분한다. 이 연결은 실제 Google 로그인부터 PG/BFF/화면까지 이어진
전체 E2E 또는 실제 engine/KIS 품질 검증이 아니다. 후속 실행에는 authenticated/lazy engine, sync/SDK budget,
전용 owned execution profile·durable lifecycle/멱등·Technical usage 검증이 별도로 필요하다.
