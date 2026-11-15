# Fundamental AI per-attempt usage 관측

기준: `bellra-jin/verith` develop `d5597225f98b7d5803d48d4b808fd86d2ad31896` (Backend PR #88 병합). 작업 branch: `feat/fundamental-attempt-usage`. AI Fundamental 내부만 변경하며 Backend/Frontend, 기존 `cost_summary` 계산과 외부 응답의 기존 필드는 유지한다.

## 구현

- `infrastructure/llm/usage.py`는 실제 HTTP 전송 직전 고유 nonzero canonical UUID를 생성하고 재시도 부모 call ID를 보존한다. 최초 전송·structured-output 재생성·공급자 fallback·SDK 하위 재전송을 별도 관측한다. 전송 결과가 불확실하면 `outcome=unknown` 및 모르는 토큰 null을 유지한다.
- provider, 요청 model, 응답 model, 요청 tier와 확인된 응답 service tier, canonical JSON 요청 SHA-256, 현재 timeout/max_tokens/SDK-default 정책 설명의 SHA-256를 남긴다. 응답 tier 누락은 null이며 요청에 tier를 명시하지 않았으면 requested_service_tier도 null이며 default로 채우지 않는다. 비밀값·URL·프롬프트·응답 전문·오류 원문은 이 증거에 넣지 않는다.
- input/cached/output/total 토큰은 독립적으로 보존한다. 누락을 0으로, cached/total을 계산값으로 대체하지 않는다. 잘못된 타입도 정상 토큰으로 강제 변환하지 않는다.
- SDK의 기본 재시도 횟수/상태/지연은 변경하지 않는다. OpenAI `DefaultAsyncHttpxClient`의 HTTP request/response hooks로 내부 재전송을 별도 기록하고 응답을 읽어 usage를 보존한다. structured-output 1회 retry, 기존 Qwen circuit 및 OpenAI fallback 동작도 유지한다. 생성한 async client는 종료한다.
- planner/interpret/critic/critic revision/verify retry의 결과와 실패 fallback에서 `llm_call_usage_records`를 전달한다. 최종 report `meta.call_usage`의 `schema_version=fundamental.call-attempts.v1`과 `calls`에 담긴다. 기존 stage 집계·`llm_call_count`·`cost_summary`는 호환용 부분합일 수 있으며 실제 전송 수/총 정산값으로 바꾸지 않았다.

## Backend PR #88과의 경계

이 필드는 AI producer 관측안이다. Backend `fundamental.usage-evidence.v1` 문서와 동일한 wire 계약이 아니며 직접 classifier 입력으로 전달하지 않는다. Backend-owned run/admission/attempt/owner/input/time·정책 digest·authoritative closed inventory·caps·expectation fingerprint와 독립적인 provenance collector는 아직 없다. AI의 새 call ID나 정책 digest를 Backend의 사전 기대값으로 복사해 신뢰를 만들면 안 된다.

`inventory_closed`, `usage_trusted`, `complete`, 금액·예약·환급·정산 ACK를 생성하지 않는다. null service tier/토큰·실패/불확실 호출은 미확인으로 남는다. Backend의 count-only observe/no-op, 모든 assessment의 keep_reservation=true, Supervisor 실행 차단은 그대로다. 원문 저장·DB schema·정산 runtime·운영 flag를 바꾸지 않는다.

실행별 `capture_usage` ContextVar scope는 stage wrapper의 정상 반환 전에 모든 전송 row를 별도 실행 collector에도 등록한다. SDK retry의 후속 row와 응답 갱신도 같은 collector에서 보인다. `analyze_fundamental`/`analyze_fundamental_public`는 선택적 caller-owned `call_usage_records`를 받고, 취소/일반 예외에는 현재 snapshot을 `fundamental_call_usage_records` 속성으로 붙여 재전파한다. scope는 finally 복원되어 다음/동시 실행과 혼합되지 않는다. 정상 노드 state의 호환 집계와 실행 collector를 분리하여 중복 등록을 피한다.

이것은 실행 프로세스 안의 메모리 회수 경계다. 프로세스 종료/장애 시 영속 보존을 제공하지 않는다. 기존 HTTP runtime은 오류를 닫힌 오류로 감싸며 HTTP 응답에 이 증거를 공개하지 않는다. 따라서 Backend로 취소 증거를 durable 전달하거나 정산하는 통합은 미구현이다. 별도의 trusted durable collector와 Backend 계약 합의 전 실제 비용통제/정산/공개 수용을 주장할 수 없다.

## 검증

Windows Python 3.12에서 다음 고정 stdlib 격리 테스트를 실행했다. 설정/graph/DB 및 실제 pydantic/OpenAI는 로드하지 않고, source 수집 전에 파일 쓰기·설정 읽기·외부 connect/DNS/subprocess를 차단했다. fake async는 이벤트 루프/소켓 없이 즉시 완료되는 coroutine으로 실행한다.

```powershell
& C:\Verith\.venv\Scripts\python.exe -I -S ai/tests/fundamental/test_call_usage_isolated.py
```

최종 4/4 통과:
1. 모든 토큰이 명시적 0인 성공, 요청 digest/UUID/tier/비밀 비포함.
2. 전체 usage 또는 일부 토큰·tier 누락, 각 null과 독립적 0 보존.
3. schema retry 및 두 공급자 모두 실패, 최초 증거·부모 ID·변경된 요청 digest 보존.
4. SDK timeout/HTTP 재시도·불확실 전송·공급자 fallback·취소, interpret/critic 실패/verify 노드 전달 및 기존 cost_summary 0/null 보존. 실제 agent 경계 함수와 fake workflow에서 로컬 wrapper collector 반환 전 취소되어도 caller collector/예외 snapshot에 2개 전송이 남고 scope가 복원됨을 확인했다. 중첩/교차 실행 ContextVar 분리도 검증했다.

첫 시도는 Windows asyncio 자체 socketpair를 connect guard가 차단해 제품 assertion 전 0/4였다. guard를 해제하지 않고 테스트 fake coroutine의 실행만 무소켓으로 바꾼 뒤 최종 4/4 통과했다.

독립 Sol 읽기 검토에서 미전송 요청 tier의 default 생성과 테스트 pydantic stub 복원 누락을 지적받아 각각 null 보존/patch.dict 복원으로 수정하고 4개 회귀를 다시 통과했다. 이후 취소 시 wrapper의 증거 유실을 실행별 공유 collector와 예외 snapshot으로 보완하고 추가 assertion까지 4개 회귀를 다시 통과했다. 프로세스 장애 내구성/Backend 전달은 위 미완료 경계로 남긴다.

로컬 venv에는 SDK/pydantic/pytest가 설치되지 않았다. 실제 SDK+HTTPX 통합, 실제 pydantic validation, 전체 pytest/type/lint, graph/DB/실제 provider/브라우저는 미실행이다. 의존성 설치·키/.env 읽기·유료 호출·운영 활성화·git add/commit/push/PR 생성은 하지 않았다. lockfile의 OpenAI 2.44.0 공식 소스와 HTTPX event hooks 문서에서 지원 API만 대조했다.

참고: [Backend 정본](../contracts/fundamental-analysis-v1.md#fundamental-usage-completeness-classification), [OpenAI 2.44.0 공개 export](https://github.com/openai/openai-python/blob/v2.44.0/src/openai/__init__.py), [HTTPX event hooks](https://www.python-httpx.org/advanced/event-hooks/).

## 사용자 직접 게시용 초안

권장 commit: `feat(fundamental): retain per-attempt AI usage observations`

- repo: `bellra-jin/verith`
- base: `develop`
- head: `feat/fundamental-attempt-usage`
- PR 제목: `feat(fundamental): retain per-attempt AI usage observations`
- PR 본문: 위 구현/검증/Backend 경계와 미검증 조건을 포함한다. draft로만 준비한다.

사용자가 이 worktree의 diff를 검토한 뒤 원하는 정확한 파일만 직접 stage/commit/push하고 실행할 PR 명령:

```powershell
gh pr create --repo bellra-jin/verith --base develop --head feat/fundamental-attempt-usage --draft --title 'feat(fundamental): retain per-attempt AI usage observations' --body-file docs/work/fundamental-ai-call-usage.md
```

이 명령은 실행하지 않았다. 다른 worktree의 기존 WIP는 그대로 보존한다.

최종 재검토: 독립 Sol 읽기 검토에서 기존 지적 3건 수정 확인, 새 차단 결함 미발견. 독립 fake 4/4 재실행 및 diff whitespace 검사 통과. AST 21개 parse 통과. 변경 코드 13파일은 모두 400줄 미만(최대 테스트348줄, 제품 report_node286줄)이며 파일별 줄수 기준을 충족한다. 현재 열린 Fundamental PR 검색 결과는 0건이었다. 원래 C:\Verith의 branch/HEAD와 기존 frontend/지침/SDD/원본 WIP가 유지됨을 최종 확인했다.

## 재전달·충돌 테스트 보완과 정정

앞서의 “4개 가짜응답”은 호출 경로 중심의 4개였으며, 사용자가 지정한 동일 ID 동일 재전달 및 동일 ID 다른 수치 충돌은 그 실행에 포함되지 않았다. 이 누락을 정정하고 별도 `ai/tests/fundamental/test_call_usage_receipt_contract_isolated.py`를 추가했다. Backend 제품 코드는 변경하지 않고 PR88의 실제 순수 `AnalysisContext`/`UsageExpectation`/`classify_usage`를 설정·DB 없이 로드한다. fake SDK가 생산한 행을 정확한 Backend wire 필드로 명시 투영하며, 별도의 synthetic expectation/신뢰 인자는 테스트 fixture에만 사용한다. 실제 trusted collector나 Backend 연동이 생긴 것으로 간주하지 않는다.

추가 실제 실행 **2/2 통과**:
- 동일 call ID/동일 내용: 한 번, 동일 문서 두 번, 문서 안 같은 call 두 번 모두 assessment가 동일하다. 보존 call 1개, 토큰 합계 `(10,2,5,15)`로 중복 합산이 없고 keep_reservation=true다. 같은 bytes라도 기본 untrusted에서는 unknown/PROVENANCE_UNPROVEN 및 합계 없음도 확인했다.
- 동일 call ID/다른 수치: `(input,total)=(10,15)`와 `(11,16)`을 정방향/역방향/원본 재전달로 넣어도 rejected/CALL_CONFLICT가 동일하다. 두 수치 증거를 모두 보존하고 총합은 모두 null, 원본 producer 행은 10으로 유지하며 keep_reservation=true다.

```powershell
& C:\Verith\.venv\Scripts\python.exe -I -S ai/tests/fundamental/test_call_usage_receipt_contract_isolated.py
```

최종 실행 결과는 기존 호출 경로 4/4 + 추가 재전달/충돌 계약 2/2, 합계 6/6이다. producer runtime의 영속 dedup/정산을 구현하거나 검증했다는 뜻은 아니다. 실 SDK/LangGraph/DB/HTTP 전달의 미검증 경계는 그대로다.


## 2026-11-15 원시 사용량 보존 후속

기존 WIP를 유지한 채 SDK typed response가 HTTP hook의 원시 usage를 다시 덮어쓰는 경계를 수정했다. 예를 들어 원시 `prompt_tokens="7"`, `completion_tokens=false`가 SDK에서 정수 7/0으로 해석되어도 호출별 증거에는 원시 타입이 남는다. 기존 호환 summary는 SDK 파싱값을 유지한다. 유효성/신뢰/완결 판정을 AI에서 새로 수행하지 않는다.

추가 격리 회귀는 수정 전 1건 실패로 재현했고, 수정 후 기존 호출 회귀 4건과 추가 1건 및 재전달/충돌 계약 2건, 총 7/7 통과했다. 실제 SDK/pydantic 파싱을 실행한 검증은 아니며 fake SDK에서 raw/typed 차이를 의도적으로 주입했다. 실제 SDK·HTTPX·LangGraph·DB·공급자·HTTP durable 수집 연결은 여전히 미검증이다. 운영 활성화, 유료 호출, 의존성 설치, stage/commit/push/PR 변경은 수행하지 않았다.


## 2026-11-15 실제 SDK 무키 HTTP 경계와 추가 순수 회귀

기존 환경/lock을 건드리지 않고 별도 임시 venv에 lock 버전 OpenAI 2.44.0, HTTPX 0.28.1, Pydantic 2.13.4, pytest 9.1.1, pytest-asyncio 1.4.0 및 lock 고정 전이 의존성을 설치했다. 첫 설치의 보조 index DNS 재시도 때문에 중단 후 격리 옵션과 retries=0으로 재시도해 성공했다. 공급자 분석 호출은 없다.

`ai/tests/fundamental/test_call_usage_sdk_isolated.py`는 직접 실행용 검사다. pytest 수집만으로 실행하거나 audit hook을 설치하지 않는다. 실제 SDK·HTTPX MockTransport와 실제 Pydantic을 사용하고, 합성 키/설정으로 실제 app/config/graph/DB import를 피한다. Windows 이벤트 루프 내부 socketpair만 사전 생성하고 source 수집 전에 외부 connect/DNS/subprocess/파일쓰기를 차단한다. 프로젝트 .env/비Python 자료 읽기도 차단하며 HTTP client는 trust_env=False다.

직접 실행한 7경계 모두 통과:
- 실제 SDK 성공, 토큰0, 전송 HTTP body digest 일치
- usage 누락 null 보존
- 잘못된 원시 문자열/불리언 토큰 타입 보존
- SDK 기본 자동 HTTP429/timeout 재시도 3회별 ID·부모·outcome 보존
- 실제 Pydantic 실패 후 schema retry
- SDK 재시도 고갈 후 OpenAI fallback
- 취소 전파

```powershell
& "$env:TEMP\verith-sdk-boundary-20261115\Scripts\python.exe" -I ai/tests/fundamental/test_call_usage_sdk_isolated.py
```

기존 격리 회귀 7/7도 유지된다. 추가로 binding/evidence_graph/formatting/period/stability/verdict_guard/schema_builder의 순수 pytest 25/25를 별도 빈 설정, 플러그인 자동탐색·캐시·캡처·logging 비활성, 외부 IO·파일쓰기·설정/인프라 source import 차단 아래 통과했다. 초기 pytest 두 시도는 pyproject 읽기 및 logging devnull 쓰기 guard가 차단했으며 제품 assertion까지 도달하지 않았다. 차단을 완화하지 않고 별도 설정/해당 플러그인 비활성으로 해결했다.

전체 AI pytest는 config dotenv·DB·graph·모델 초기화를 포함하므로 실행하지 않았다. 실제 공급자·DB·HTTP runtime 및 durable receipt collector 연결/전체 type/lint/원격 CI는 미검증이다. Backend #88의 authoritative inventory, owner/run/attempt/time/policy/expectation binding과 provenance는 Backend 소유이므로 AI producer가 inventory_closed/usage_trusted를 생성하거나 신뢰 승격하는 adapter는 추가하지 않았다. 비용 예약·정산 및 Supervisor 변경, 운영 활성화, git 게시도 없다.
