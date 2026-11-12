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

## CF039 · 기본 비활성 동기 runner 연결

`make_engine_bridge`는 기본 비활성이며 서버가 명시한 sync_runner·LLM client·OHLCV fetcher와 cache/trace_sink를 받는다.
cache/trace의 None은 미사용이며 다른 의존성·설정·환경·graph/provider를 자동으로 만들지 않는다. coroutine 함수와
비동기 callable 의존성은 거절한다. 주입 객체가 있다는 사실만으로 그 구현의 network-free 성질을 보증하지 않는다.
실제 app/router/Backend/Supervisor에는 등록하지 않는다.

활성화된 한 작업의 입력은 caller mutation과 분리된 snapshot으로 실제 별도 thread에 전달한다. 원질문·종목·as_of와
request/trace ID는 바꾸거나 생성하지 않는다. 기존 순수 Deadline으로 시작+WAIT_SECONDS와 명시된 더 이른 만료의
교집합을 사용하며 snapshot/dispatch/worker/result 경계에서 확인한다. 기존 HTTP3초와 route/auth/body는 그대로다.
cooperative deadline은 동기 함수를 강제로 멈추지 못한다.

HTTP waiter의 timeout/취소는 기존 Runtime이 즉시 처리한다. bridge engine task가 취소돼도 실제 worker 종료를 기다리고,
반복 취소를 성공으로 바꾸거나 uncancel하지 않는다. is_alive false와 join을 확인한 뒤 취소를 재전파하므로 기존 단일
Runtime 슬롯은 물리 worker가 끝나기 전에 풀리지 않는다. 무응답 worker는 BUSY를 유지하며 강제 thread kill/재시도는 없다.
늦은 결과는 종료된 HTTP 기다림으로 되돌려 주지 않는다. 운영 종료·부하/무응답 worker 회수까지 검증했다는 뜻은 아니다.

typed model은 Python 값으로 dump한 뒤 datetime/date의 표준 ISO 표현과 enum 값을 JSON으로 직렬화한다. raw JSON 숫자·
문자열은 바꾸지 않고, 필드를 채우거나 요청에 맞춰 시간 표현/ID를 고치지 않는다. 기존 complete/validate_result/validate_response가
최종 판단하며, 동등한 시각이라도 raw 표현이 다른 binding은 계속 거절될 수 있다. 합성 execution_mode·cutoff 미검증과
생성/발행 시각 미보고를 그대로 보존한다.

현재 보호 환경에는 실제 graph runtime/dependency가 준비되지 않았으며 collector의 graph/config/provider import 금지를
유지한다. 이번 증거는 실제 thread와 주입한 fake runner의 연결이며 실제 LangGraph 계산·KIS/OpenAI·캐시/trace 서비스·
owner 저장/usage·Supervisor 실행 수용이 아니다. [직접 검사와 미실행 경계](../work/CF-039-technical-engine-bridge.md)를 따른다.

## CF040 · import 안전성과 명시 초기화

Technical config는 import 때 환경/파일을 탐색하거나 dotenv/getenv·client/cache/trace 생성을 하지 않는다.
기존 정적 기본값을 두고 명시 initialize_runtime이 intraday/trace-enabled/trace-path의 불변 snapshot을 한 번 확정한다.
기존 bool 파싱·기본값·환경 우선/override=False·명시 KIS/OpenAI loader와 파일 위치는 유지한다.
동시 factory는 같은 완성 snapshot을 받고 실패는 부분 상태/client 없이 고정 오류로 닫힌다.

기존 get_llm_client/get_fetcher/get_cache/get_trace_sink의 명시 호출/override 경계는 보존하며 Technical import는
setup 뒤로 미룬다. trace는 snapshot을 소비하고 LLM 타입 alias는 런타임 client import 없는 forward reference를 사용한다.
미초기화 상태의 pipeline/graph가 먼저 로드됐으면 늦은 setup을 거절한다. reload·module 삭제·다른 module flag patch는 없다.
기본 main/route와 다른 legacy Supervisor chain은 재활성화하지 않는다.

검사는 실제 config 및 선택한 factory 함수 body와 자기 환경 mapping/import spy를 사용한다. 전체 dependencies module이나
실제 graph/service를 import한 수용이 아니다. CF021의 config/graph 금지·AST-only 검사와 기존 worker/guard는 유지한다.
실제 compiled graph의 wheel/platform/site provenance·정확 collection과 수집 전 tracing/provider 차단은 설계 선행이며,
이 import 안전화가 설치·실제 graph/KIS/OpenAI 실행을 허가하지 않는다. [검증 기록](../work/CF-040-technical-runtime-setup.md)을 따른다.

## 실제 compiled graph의 한정 합성 연결

CF039/CF040 위의 후속 고정 검사는 검토된 별도 64-wheel site와 정확한 소스 사본에서 실제 `run_technical_agent`의 compiled LangGraph를 thread bridge와 Runtime의 strict completion에 연결한다. 기존 CF021의 graph/config import 금지는 해당 collection에 그대로 적용하며 새 `technical-graph-unit`과 혼합하지 않는다.

기존 ScriptedLlm·합성 OHLCV로 normal/data_limited/regime_unavailable 세 경우의 원문/ID/as_of·결과·coverage·worker/slot 정리를 확인한다. 수집 전 파일/네트워크/프로세스 보호, 명시 config 초기화·intraday/trace 비활성, 원본 source 차단과 source/site 전후 provenance가 필수다. urllib3의 import-only IPv6 탐색은 검사 중 IPv4-only 플랫폼 가정으로 예방하며 실제 IPv6 검증으로 해석하지 않는다. CI self는 입구 보호만 검사하고 실제 그래프 unit은 별도 설치 site의 로컬 증거로 구분한다.

이 결과는 KIS/OpenAI·캐시/trace 서비스·운영 활성화·public Technical 실행/저장/usage·전체 main 시작 성공이 아니다. [직접 결과와 한계](../work/technical-compiled-bridge.md)를 따른다. 앞 CF039/CF040의 graph 미실행 문장은 당시 이력이며, 그 보호 collection 자체를 완화하지 않는다.

## Technical 선택적 provider 사용량

기존 `OpenAiLlmClient.last_usage`는 명시된 input/output/total 세 값이 모두 비음수 exact integer이며 input+output==total일 때만 보존한다. 누락·None·bool·문자열·소수·음수·합계 불일치는 None이며 0으로 채우거나 정수로 강제 변환하지 않는다. 분석 텍스트는 유지하고 추가 호출하지 않는다.

이는 마지막 호출의 선택적 증거이며 누적 사용량·가격 검증·비용 승인·예약/정산·청구 확정을 대신하지 않는다. None을 미사용/무료로 간주하지 않는다. [수정과 보호 회귀](../work/technical-usage-evidence.md)는 실제 어댑터의 선택 AST body와 fake SDK 객체를 사용하는 무키 검사이며 운영 SDK/실제 provider 검증은 아니다.

## 이미 저장된 Technical 결과의 정확한 stage 재요청

내부 `TechnicalOwnedReportService.stage`는 fresh Principal 검증과 root 잠금 뒤 이미 존재하는 ID를 검사한다. 동일 owner의 root·snapshot·정확 한 index·저장 당시 session 및 모든 child projection을 기존 read로 다시 검증하고, 저장된 FrozenAnalysisResult 전체가 caller의 검증 결과와 정확히 같을 때만 기존 StagedReportReference를 반환한다. 원 TEXT/세션/행을 변경하거나 flush·commit·AI 호출을 하지 않는다. 다른 유효 입력/결과, 타인·legacy·손상·누락·중복 index는 충돌로 닫는다.

이는 이미 저장된 결과의 재요청만 지원한다. 아직 없는 동일 ID의 동시 최초 저장은 기존 PK 충돌이 가능하며, caller commit 책임과 ACK 불명 뒤 GET-only 복구는 그대로다. 새 실행 identity/admission·멱등 실행·Technical 사용량 정책·운영 활성화 또는 commit 성공 보증이 아니다. [제품 변경과 검증](../work/technical-owned-stage-replay.md)을 따른다.

## CF048 Technical 전용 접수와 로컬 claim

`TechnicalAdmissionService`는 아직 router/coordinator에 등록되지 않은 내부 SQL 컴포넌트다. 기존 Principal·등록 Stock 검증 뒤 Technical 단일 관점과 고정 3m/1y/5y intent를 깊게 고정한다. 새 접수에는 operation/ticker·사용자/서비스 일일 횟수·예산/예약·기한·model/tier·가격 근거·token/byte/call cap이 모두 명시된 정책이 필요하다. 정책 부재/오류/당일 drift는 새 접수와 새 claim만 닫는다. 합성 가격/hash를 운영 근거로 승격하지 않는다.

인증→원 period→run 순서의 잠금 아래 owner/key의 같은 입력은 원 identity를 복구하고 다른 입력은 conflict다. 새 run·횟수·예약은 한 commit이며 ACK 뒤에만 최초 private claim token을 반환한다. 다른 정상 owner 세션 A2의 GET/replay는 원 admission session을 바꾸지 않고 새 token을 발급하지 않는다. `dispatch_claim`은 원 세션/token·고정 context/input/spec/policy·Stock·DB 기한을 다시 대조하고 최초 commit ACK 뒤에만 `newly_claimed=True`를 준다. 지연된 ACK는 원 기한을 늘리지 않는다.

ACK 불명 복구는 caller가 아는 key의 readonly/no-autoflush 조회이며 새 claim 권위가 없다. 취소/timeout/만료/원문 삭제/불확실 송신은 unknown 및 원 예약/횟수를 보존한다. get/claim/close_unknown에서 만료를 처리할 때 intent를 실제 NULL로 만들며 자동 sweeper/정산/환급은 없다. owner/run/period 삭제나 새 날짜로 원 key·hold를 초기화하지 않는다.

E는 admission intent hash, B는 기존 strict boundary wire/fingerprint, S는 기존 owned-stage wrapper/hash다. 이를 같은 hash로 취급하지 않는다. 후속 공통 coordinator가 admission/claim SQL과 commit/ACK의 유일한 소유자가 되어 한 번만 수행해야 한다. 이 서비스를 먼저 호출한 뒤 coordinator.post로 다시 접수·예약하는 방식은 금지다. 이번에는 adapter/hook·엔진/owned writer·Supervisor 확정 dispatch·실제 provider 송신/요금 정산·운영 정책을 연결하지 않는다. [검증과 미완료](../work/CF-048-technical-admission.md)를 따른다.

## CF049 명시 opt-in 요청별 LLM 소비와 전 호출 증거

기존 legacy `complete(prompt)`와 `last_usage` 계약은 유지한다. 명시 `strict=True`는 `TechnicalRequestLlmBudget`을 필수로 받고, 누락/실패에서 legacy로 fallback하지 않는다. 한 실행의 모든 adapter가 budget 하나를 공유해야 한다. 원 CF048 policy canonical bytes/독립 expected hash·typed projection, run/attempt·예약·UTC 시작/기한을 깊게 고정하며 재호출/관측 usage로 소비를 초기화하거나 환급하지 않는다. CF048을 import하거나 Flow/시험 예산을 가져오지 않는다.

strict는 최종 model/input projection과 원 prompt·request identity에 결합된 계수 영수증을 명시 trusted DI로 받고 그 의존성의 `verify`와 고정 mapping/version/provenance 결합을 요구한다. 단순 token 정수/hash/boolean은 계수 근거가 아니다. 실제 Technical 계수 구현/provenance는 아직 없으며 기본 DI=None은 SDK0으로 닫힌다. 합성 issuer/verify는 실제 정확 계수 증명이 아니고, 임의 주입 구현의 진위를 문자열/hash 형식 검사만으로 보증하지 않는다. 향후 실사용 DI의 구현·provenance 검토가 필수다. count transport/API를 자동 생성하지 않는다.

최대1..4 call cap과 보수 hold를 lock 아래 SDK 전에 소비하고, 같은 lock에서 미폐쇄·원 ordinal·미진입·기한을 다시 확인해 entered 권위를 한 번 선형화한다. 계수/SDK I/O 동안 lock을 유지하지 않는다. unknown이 먼저 닫았으면 이미 소비한 미진입 call은 SDK0·hold 유지이며, 이미 entered인 call은 응답을 원 ordinal에 끝까지 보존한다. 계수 전 캡처 SDK/responses/create identity와 retry0·model/tier/output cap/store=False를 대기 후 재검사한다. 원 시작보다 이른 local UTC는 닫고, 관측 전 기준점에서 원 duration 이하로 한 번 결합한 monotonic·원 UTC·더 짧은 기존 Deadline 및 per-call timeout을 계속 좁히며, 늦게 반환한 응답도 usage 먼저 보존한 뒤 텍스트 채택을 거절한다.

최대4개의 불변 snapshot은 원 identity/hash·fixed model/tier/caps·보수 hold·entered/response_received·각 usage/추정액 또는 unknown·텍스트 수용/고정 이유/경과를 구분한다. missing/invalid usage는 0으로 채우지 않고 completed 아닌 status/refusal/빈 text·cap/count 불일치/예외/취소는 sticky closed다. 원문 prompt/응답·provider 자유 metadata·키/자유 exception은 저장하지 않는다. output byte cap은 추출 텍스트 수용 한도이며 SDK 전체 decoded body의 메모리/transport read cap은 아니다.

entered는 로컬 진입 권위이며 wire/처리/청구 관측이 아니다. SDK 객체의 retry 설정 검사와 adapter dispatch 횟수는 임의 callable의 내부 HTTP/재시도를 입증하지 않는다. 프로세스 재시작/동일 run의 새 budget 차단은 CF048 claim과 후속 단일 coordinator 조립의 책임이다. 실제 SDK/endpoint/proxy/계수 provenance·Backend→엔진→저장·durable 승인/정산·Supervisor dispatch·운영 활성화는 미완료다. [직접 검사와 한계](../work/CF-049-technical-request-llm-budget.md)를 따른다.
