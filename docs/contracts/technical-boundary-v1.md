# Technical boundary v1

[공통 envelope](analysis-agent-envelope-v1.md)의 단일 비영속 적용이다. 공개 Technical route/BFF/UI·DB writer·owner lifecycle·사용 한도는 열지 않는다.

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
