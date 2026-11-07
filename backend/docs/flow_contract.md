# CF-001 최소 공통·Flow 계약

기준: develop `7f376ce11c7bd12254e1e6fe1cebc3bf13f64e66`, 작업 브랜치
`feat/flow-contract`. 상세설계 v1.0은 목표 안전 원칙, MVP v0.1은 단계 제안이다.
이번 구현은 스키마·순수 검증·기존 save-only 경계만 다룬다.
사용 지시서는 `지시서/CF-001_최소_공통_Flow_계약.md`다. v1.0으로 시작했으며
한시 보존 조건을 반영한 정본 **v1.1을 다시 읽고 현재 기준으로 적용**했다.
`지시서/코드_개발_운영.md`와 `지시서/지시서_작성_운영.md` v1.0을 실제로 읽고
적용했다. 설계 결정에 종속된 변경만 보류하고, 승인된 독립 검증은 계속한다.
이후 도비가 전달한 작성 채팅 검토 결과에 따라 기존 checks JSONB의 한시 보존을
적용했다. 전달 조건은 형식 구분, root·자식·목록 정합성, 신규 손상의 legacy 우회
금지, legacy 한계 명시, 실제 격리 DB 조회·삭제·rollback 검사다. 해당 조건은 현재
정본 v1.1의 6-1절에 반영돼 있다. 독립 검토에서 전달된 P2 두 건도 수정·재검증했다.

## 공개·내부 경계

- `FlowRunRequest`: ticker(ASCII 6자리), question(공백만 불가), timezone 포함
  as_of, idempotency_key(공백만 불가). owner, payload, 검증 상태, 실행 ID는 금지.
- `ExecutionContext`: 검증된 Backend principal에서 생성할 owner_user_id와
  Backend 발급 request_id/run_id/attempt_id(UUID). 타입 검증은 인증이 아니다.
  client_session_id, 임의 헤더, UUID 인지는 인증 근거가 아니다.
- `FlowResultReference`: 위 문맥과 원본 AI report_id(UUID)를 연결한다.
  bind_flow_result가 검증한 원본 JSON의 SHA-256도 연결하여 같은 ID의 본문 변경을
  구분한다. 해시는 인증·수치 정답의 증거가 아니다.
  같은 attempt의 최종 결과 변경은 충돌이다. 연결·충돌·삭제 검증은 순수 계약
  검사이며 실제 DB 경쟁 제어, 인증, tombstone 서비스는 후속이다.
- 실행 pending/running/succeeded/failed/unknown과 저장 not_stored/stored/unknown을
  분리한다. unknown은 자동 재호출 근거가 아니다. 성공해도 미저장일 수 있다.
- 공통 응답은 request_id/data/error. data와 error 중 하나만 존재한다.
  안전한 code/message는 고정 매핑: AUTH_REQUIRED 401, RESOURCE_NOT_FOUND 404,
  IDEMPOTENCY_CONFLICT·RESULT_CONFLICT 409, INPUT_INVALID·UNSUPPORTED_VERSION 422,
  RESULT_CONTRACT_INVALID 502, DATA_INSUFFICIENT 422. 내부 오류 원문은 노출하지 않는다.

이 스키마는 신규 endpoint에 아직 연결하지 않는다. 기존 `/api/flow/reports/save`는
호환을 위해 payload/question/client_session_id를 받는 **legacy save-only 경계**다.
추가 owner·실행·검증 필드는 거부하지만 인증·owner 필터는 아직 없다. 기존 CRUD와
전체 삭제도 실제 Flow 공개 전 내부화/차단하고 검증된 인증 경로로 교체해야 한다.
이번 변경을 로그인·인가 완료로 해석하면 안 된다. 기존 응답 wrapper도 유지한다.

## version 1 입력과 보존

정본: `ai/src/agents/flow/docs/storage-spec.md`, `export/to_json.build_payload`,
`core/signals.py`, frontend `src/api/flow.ts`. 지원 version은 정수 1만이다.
version/report_id/meta/signals/verification/interpretation은 필수다.
meta.ticker는 저장 FK 때문에 필수이며 base_date는 실제 ISO 일자 또는 명시적 null이다.
잘못된 날짜는 null로 바꾸지 않는다. stock_name/market은 문자열 또는 null이다.
trace_id는 과거 호출자가 임의 추적 문자열도 전달하므로 문자열/null로 보존한다.
report_id와 실행 ID는 UUID로 검증한다.

signals의 기존 블록은 생략 가능하다(가산적 v1 호환). 블록이 있으면 내부 필수
숫자·boolean·날짜를 검증한다. signals 전체 null은 기존 reader 호환으로 허용하되
자료 부족으로만 취급한다. inst_detail/ownership/price_daily 및 시세 순매매량의
null은 미수집/해당 자료 없음이며 0은 실제 수치다. NaN/무한대, bool을 숫자로,
숫자 문자열을 숫자로 바꾸는 처리는 허용하지 않는다. 명세의 가산적 확장을 위해
알 수 없는 payload 키는 JSON 값으로 보존한다. 공개 요청은 알 수 없는 키를 거부한다.
모든 중첩 키·문자열 값에 대해 PostgreSQL에 표현할 수 없는 NUL과 UTF-8로 인코딩할
수 없는 surrogate 코드 단위를 쓰기 전에 거부한다. question/client_session_id에도
같은 저장 문자열 검증을 적용한다. 삭제·치환·Unicode 정규화로 값을 고치지 않는다.
정상 한글·이모지·결합문자와 문자 그대로의 `\u0000`, `\ud800` 표기는 보존한다.

v1 단위·기간은 wire 필드가 아니라 생산자 의미에 묶인다: daily/inst_detail/
persistence 순매수는 백만원, strength.ratio는 비율, consecutive.days는 일수,
ownership.ratio는 %, price_daily close/change는 원, change_rate는 %, volume/
frgn_qty/inst_qty는 주. persistence는 최근 5/20 거래일, daily는 최대 최근 20,
ownership은 최대 5, price_daily는 최대 10 거래일이다. 실제 행 날짜를 보존하며
달력일 기간이나 원천 기준시각을 새로 추정하지 않는다. 생산자 상수/계산은 변경하지 않는다.
signals.py의 파일 상단 입력 예시에는 오래된 `원` 주석이 있지만 현재 KIS 매핑·
`_to_signals_frame` 및 frontend 표시는 `백만원`이다. 이 실행 경로를 기준으로
문서화하며 금액을 변환하지 않는다. `calc_strength`가 분모 0/NaN을 0으로 후퇴하는
기존 계산은 별도 품질 검토 대상이다. 이미 만들어진 0의 원래 결측 여부는 이번
저장 경계가 복원할 수 없다.

data_status/outcome/regen_count/interpretation_meta는 v1 추가 이전 자료에서 생략 또는
null 가능하다. 제공되면 구조·상호 정합을 검증한다. data_status는 ok/data_limited이며
price_daily 부재는 data_limited다. interpretation은 gate3 통과분만 가능하고 null은
통과 해석 없음을 뜻한다. outcome/source/provider/model은 이 의미와 일치해야 한다.
gate3 통과 자체는 해석 문자열 존재를 보장하지 않는다(build_payload 기존 동작).

legacy HTTP wrapper는 유지하되 잘못된 입력은 422와
`detail: {code, message}`로 응답한다. version 오류는 UNSUPPORTED_VERSION,
그 외 입력 오류는 INPUT_INVALID다. 원래 입력/검증 예외 전문을 응답하지 않는다.
저장된 결과가 계약을 위반하면 RESULT_CONTRACT_INVALID 502로 응답한다.
이는 신규 공통 envelope endpoint를 구현했다는 뜻이 아니다.

원본 report_id를 PK로 유지한다. **아래 저장 위치는 이번 CF-001의 한시 호환 방식**이며
최종 전용 snapshot 저장소가 아니다. 작성 채팅 검토 결과를 도비가 전달한 범위에서
적용하며 새 물리 컬럼·테이블·migration은 추가하지 않는다.
새 저장은 verification.checks JSONB의 예약 키
`_flow_payload_snapshot`에 검증된 원본 JSON을 함께 둔다. 기존 gate1/2/3 매핑과
승격 컬럼은 유지한다. 조회는 이 snapshot을 재검증하여 version·ID·수치·null·생략·
추가 필드를 그대로 반환한다. 저장 공간 중복은 migration 없는 호환을 위한 비용이다.
향후 전용 snapshot 테이블로 이전할 대상이다. 키가 없는 구 자료만 명시적 legacy-v1
adapter로 재구성한다. 기존 DB는 version을 저장하지 않았으므로 과거 미지원 version의
정체를 복원할 수 없다. 새 snapshot의 미지원 version은 오류이며 v1로 덮지 않는다.

기존 storage-spec은 checks를 검증 정보에 매핑한다. 전체
payload를 담는 예약 키는 물리 컬럼 변경이나 FE/AI 동시 변경은 필요 없지만,
검증 JSONB의 용도를 확장하고 수치/해석을 중복 저장하며 향후 reader에 영향을 준다.
대안은 (1) 현 JSONB 방식, (2) version과 생략/null/추가 필드 메타데이터만 보존하는
방식(중복은 줄지만 재구성 복잡도가 커짐), (3) 후속 전용 snapshot 컬럼/테이블이다.
(3)은 migration 범위이므로 이번에 구현하지 않는다. (1)을 이번 한시 방식으로
사용하며 장기 저장 구조·선보존 후 게시·복구 서비스를 확정하거나 구현한 것이 아니다.

`checks._flow_storage_format = "flow-payload-snapshot.v1"`과 같은 표식을
`agent_reports.summary._flow_storage_format`에도 보존한다. storage-format은
payload.version과 별개다. snapshot 또는 두 표식 중 하나라도 있으면 신규 reader만
사용하고, 표식 불일치·snapshot 누락/손상·미지원 payload version은 안전한 오류다.
신규 자식/인덱스 누락이나 중복, root·자식·gate·목록 summary와 snapshot의 불일치도
거부한다. 값은 읽을 때 조용히 수선하지 않는다. 형식 표식이 모두 없는 실제 구 자료만
legacy adapter 대상이다. 두 저장 영역의 표식과 snapshot이 **전부** 지워진 경우는
기존 물리 스키마만으로 구 자료와 구별할 수 없다는 한계가 있다. 이런 전체 메타데이터
파괴의 탐지·복구는 이번 보장의 범위가 아니다.

Flow 전용 목록과 공통 `/api/reports`, `/api/reports/archive` 모두 같은 정합성 검사를
거친다. 목록은 페이지의 Flow ID를 모아 root/해석/검증/인덱스를 4개 batch query로
읽어 대조한다. 기존 다른 관점의 계산·카드 표시를 변경하지 않는다. 손상된 Flow는
정상 상세·목록으로 게시하지 않고 RESULT_CONTRACT_INVALID 오류로 처리한다.
정합성 비교는 JSON 타입을 재귀적으로 대조한다. JSON number의 int/float는 같은
수치 범주로 비교하지만 boolean은 별도 범주다. Python의 `0 == False`, `1 == True`
때문에 숫자·boolean 손상이 통과하지 않는다. UUID/date 승격 값도 타입과 값을 대조한다.

## 자료·멱등·삭제의 후속 연결 계약

`DataObservation`은 source/as_of/period_start/period_end/unit/value/missing_reason을
검증한다. null 수치는 이유 필수, 0에는 결측 이유 금지, 기간 역전 금지다.
v1에 없는 실제 출처·기간·결측 사유를 만들어 넣지 않는다. 이 메타데이터를 실제 AI
입력/결과 snapshot에 실어 저장하려면 AI/Backend 계약과 보존 경로 연결이 필요하다.

멱등 비교는 같은 owner·key·정규화 입력이면 기존 run, 다른 입력이면 409라는
순수 검증만 제공한다. 접수·hash 저장·unique 제약·만료 정책은 구현하지 않는다.
삭제 표식이 있는 결과의 늦은 저장은 금지하는 순수 검증을 제공한다. 실제 owner
필터·tombstone·원자적 게시/삭제·동시 저장 충돌 제어는 후속 서비스 책임이다.

## 검증 범위와 미결정

단위 검사는 합성 fixture, fake session/repository, 독립 FastAPI 앱만 사용한다.
공용 tests/conftest.py는 앱 DB fallback을 허용하므로 `--confcutdir=tests/unit`로
차단한다. 실 DB·로그인·A/B 인가·멱등 경쟁·삭제 경합 통과를 의미하지 않는다.

오래된 flow_backend_handoff.md의 data_status 미정 설명보다 갱신된 AI 저장 명세와
export 코드의 ok/data_limited를 따른다. 지원 기업·정책 기간·예산·인증 방식·최종
ID 채택의 실행 연결은 미결정/후속이다. AI ID 보존은 기존 구현 유지이며 Backend가
해당 attempt에 연결하여 채택하는 방식은 제안 단계다.

`core/verify_interpretation.py`는 주체별 매수/매도 방향·수급 구도·개인 오귀속을
검사하며 애매한 방향은 보류(통과)한다. 해석의 숫자 인용 자체와 기간·단위·정확한
금액·출처 일치를 검사하는 구현은 확인되지 않았다. 이번에는 계산/게이트를 고치지
않는다. 후속 검사는 동일 숫자의
다른 주체 인용, 5/20일 혼동, 백만원/원·비율/% 혼동, 음수 부호 유실, 결측의 0 대체,
없는 수치 인용을 포함해야 한다. 실제 자료 확보와 격리 DB의 요청→실행→저장→조회→
삭제 검증을 거친 뒤 실제 Flow를 연결한다.

## 재현 명령과 완료 증거

backend 디렉터리에서 기존 uv.lock, Python 3.12, backend/.venv를 사용한다.

```sh
UV_CACHE_DIR=/tmp/verith-cf001-uv uv run --frozen --offline --python 3.12 pytest --confcutdir=tests/unit tests/unit/test_flow_contract.py -q
.venv/bin/ruff check src/api/schemas/flow_payload.py src/api/schemas/flow_execution.py src/api/schemas/flow_report.py src/api/services/flow_report_service.py src/api/routes/flow_reports.py tests/unit
```

2026-11-06: 기존 전역 uv cache는 쓰기 권한이 없고 네트워크 다운로드는 DNS 실패했다.
lock과 일치하는 캐시만 /tmp로 복사한 뒤 frozen/offline sync로 의존성을 준비했다.
lockfile은 변경하지 않았다. 공용 DB conftest를 제외하고 socket 연결도 테스트에서
차단한다. AI의 실제 build_payload와 GateResult만 import하여 합성 입력을 생성한다.
그래프·데이터 수집·LLM은 import/호출하지 않는다.

재검토에서 공개 as_of의 숫자 문자열이 Unix timestamp로 암묵 변환되는 결함을
재현했다(`"123"` → 1970년 시각). 명시적 ISO datetime 파싱으로 수정하고 회귀
검사를 추가했다. 목록 ticker도 ASCII 6자리로 통일했다. 테스트 환경변수는 fixture
종료 시 복원하고 route import를 fixture 내부로 옮겨 다른 테스트의 설정 오염을 막았다.

현재 단위 결과: **148 passed**, 대상 파일 Ruff 검사 통과,
`git diff --check` 통과. 테스트에는 메모리 repository를 통한 HTTP 저장/조회 왕복,
쓰기 전 거부, null/0/생략/추가 필드 보존, 구 v1 reader, 저장된 미지원 version 차단,
공개 요청의 owner/payload 차단, 실행 참조·멱등·삭제 표식의 순수 검증이 포함된다.
기존 보관함 카드 projection 검사도 `--noconftest -k test_archive_card`로
**4 passed, 3 deselected**를 확인했다. 선택하지 않은 기존 endpoint 검사까지
통과했다고 주장하지 않는다.

## 실제 DB 검증 상태와 필수 후속 게이트

저장 JSONB 매핑이 바뀌므로 단위 테스트만으로 실제 저장 보존을 최종 승인하지 않는다.
db_boundaries.md와 .env에서 로컬 verith_test가 앱 verith와 다른 전용 테스트 DB로
설정된 것을 확인했다(자격증명은 출력하지 않음). 그러나 읽기 전용 연결 시도가
ConnectionRefusedError(errno 61)로 실패해 테이블·현재 격리 상태까지 확인하지 못했다.

`tests/flow_integration`에 기존 v1 테이블 왕복·새 snapshot 왕복·잘못된 입력 쓰기 0·
정합성 손상 차단·목록·삭제·실패 rollback 및 P2 회귀 검사 29개를 준비했다. 기존 DB conftest와 분리하며
앱 DB fallback·자동 migration·지속 seed는 금지한다. 명시적 opt-in, localhost의
verith_test 이름, 앱 DB와 분리 여부, 실제 연결 DB 이름, 테이블 준비를 확인한 뒤
외부 transaction + savepoint로 격리하며 종료 시 rollback과 결과 행 제거를 검사한다.

```sh
CF001_RUN_DB_TESTS=1 UV_CACHE_DIR=/tmp/verith-cf001-uv uv run --frozen --offline --python 3.12 pytest --confcutdir=tests/flow_integration tests/flow_integration -q --maxfail=1
```

첫 시도는 당시 검사 7개 중 첫 fixture의 DB 연결 단계에서 **1 setup error**로
중단됐다. 그때 DB assertion·쓰기는 없었고 나머지 6개도 미실행이었다.

이후 기존 사용자 DB·볼륨을 건드리지 않는 별도 테스트 DB 준비가 명시적으로 허용됐다.
기존 verith-postgres 컨테이너가 exited 상태임을 읽기로 확인하고, 이를 시작하지 않았다.
로컬 캐시의 pgvector/pgvector:pg16 이미지로 새 컨테이너
`verith-cf001-test-20261106-a4f6`를 만들었다. persistent volume/bind mount는 없고
data·socket·tmp 모두 tmpfs, 루트 파일시스템은 read-only이며 포트는
127.0.0.1:56180에만 노출했다. CF-001/disposable-test 라벨과 Mounts=[]를 확인했다.
기존 migration을 이 새 verith_test에만 적용했다. 새 migration은 작성하지 않았다.

저장 설계 결정과 독립적인 아래 검사만 선택했다.

```sh
CF001_RUN_DB_TESTS=1 TEST_DATABASE_URL=postgresql+asyncpg://cf001@127.0.0.1:56180/verith_test UV_CACHE_DIR=/tmp/verith-cf001-uv uv run --frozen --offline --python 3.12 pytest --confcutdir=tests/flow_integration tests/flow_integration/test_flow_persistence.py -q -k 'legacy_v1_roundtrip or invalid_input_has_no_stock_or_result_writes'
```

결과는 **4 passed, 4 deselected**다. 기존 분리 테이블에 합성 v1을 실제로 저장한
뒤 세션을 expire하여 DB에서 다시 조회했고 ID·수치·기간·검증 정보 일치를 확인했다.
기존 v1 reader 검사이며, 보류 중인 새 snapshot 저장안을 채택한 검사가 아니다.
중첩 타입·날짜·미지원 version 오류 3건은 실제 stocks/flow_reports/agent_reports
행수 변화 0을 확인했다. fixture의 외부 transaction/savepoint rollback도 통과했다.

모든 테스트 종료 후 stocks·flow_reports·interpretations·verifications·agent_reports
행수를 별도 SQL로 확인했고 모두 0이었다. 기존 컨테이너는 계속 exited였다.
이번에 만든 임시 컨테이너만 라벨·Mounts=[]를 재확인한 뒤 stop/auto-remove했다.
위 포트는 이 실행의 기록이며 재사용할 실행 중 DB가 아니다. 기존 사용자 DB와 볼륨은
변경하지 않았다. 처음 실행에서는 새 snapshot 관련 4건을 설계 검토 결과까지 선택 제외했다.

검토 결과를 전달받아 조건을 반영한 뒤 별도의 새 컨테이너
`verith-cf001-test-20261106-b7e9`(같은 로컬 이미지·tmpfs·Mounts=[]·read-only root,
127.0.0.1:56253)에서 기존 migration을 적용하고 전체 검사를 실행했다.

```sh
CF001_RUN_DB_TESTS=1 TEST_DATABASE_URL=postgresql+asyncpg://cf001@127.0.0.1:56253/verith_test UV_CACHE_DIR=/tmp/verith-cf001-uv uv run --frozen --offline --python 3.12 pytest --confcutdir=tests/flow_integration tests/flow_integration -q --maxfail=1
```

한시 저장 검토 조건 반영 시 결과는 **19 passed**였다. 정상·자료 부족·가산적 v1의 새 snapshot 실제 왕복,
기존 v1 reader, 쓰기 전 거부, 저장된 미지원 version 차단, root·해석·검증·인덱스
불일치와 표식/snapshot/자식 누락 차단, 전용/공통 목록·보관함, 단일 결과 삭제의
자식 cascade·목록 제거, 중간 저장 실패의 호출자 rollback을 확인했다.
AI 결과만 합성 fixture로 만들고 실제 Repository·session·PostgreSQL을 사용했다.
이 결과는 실제 AI 호출이나 로그인·인가 검증의 증거가 아니다.

종료 후 5개 테이블의 행수를 별도 SQL로 확인해 모두 0임을 확인했고, 이 임시
컨테이너도 정리·제거했다. 기존 verith-postgres는 계속 exited다. 이 포트 역시
현재 실행 중인 DB가 아니라 검증 기록이다. 사용자 데이터·기존 볼륨·.env는 변경하지 않았다.

### v1.1 독립 검토 P2 수정·재검증

1. `validate_flow_payload`가 JSON 직렬화 가능 여부만 검사해 NUL/단독 surrogate를
   통과시켰다. `_check_json_types`에서 모든 키와 값의 저장 문자열을 재귀 검증한다.
   비호환 문자열은 안전한 INPUT_INVALID 422이며 저장 함수 재검증에서도 쓰기 전에
   거부한다. 원본을 변경하지 않는다.
2. `_check_snapshot_consistency`의 Python dict/값 동등성은 0/false를 구별하지 못했다.
   모든 projection·gate·summary 비교에 JSON 타입을 고려하는 재귀 비교를 적용했다.

추가 회귀 검사 수정 전 실행은 **13 failed, 2 passed**로 결함을 재현했다. 수정 후
전체 단위 검사는 **148 passed**다. 정상 Unicode와 literal escape의 원본 보존도 확인했다.

기존 DB/볼륨과 분리된 새 tmpfs 컨테이너 `verith-cf001-test-20261106-c8f2`를 같은
로컬 이미지로 준비하고 Mounts=[]·read-only root·loopback(127.0.0.1:56433)을
확인한 뒤 기존 migration만 적용했다. 실제 DB 검사 전체 결과는 **29 passed**다.
NUL/상·하위 단독 surrogate를 중첩 키·값에 넣은 6건은 실제 테이블 쓰기 0을 확인했다.
숫자 0→boolean false, boolean false→숫자 0, gate 번호 1→boolean true의 3건은
명시적 SQL UPDATE로 손상시켰다(ORM dirty tracking도 Python equality로 변경을
생략할 수 있으므로 ORM 대입만 사용하지 않음). DB에서 실제 JSONB 타입을 다시
확인한 뒤 상세·목록이 모두 안전한 오류로 거부하는 것을 검증했다.
정상 Unicode/literal escape의 실제 DB 왕복도 통과했다.

```sh
CF001_RUN_DB_TESTS=1 TEST_DATABASE_URL=postgresql+asyncpg://cf001@127.0.0.1:56433/verith_test UV_CACHE_DIR=/tmp/verith-cf001-uv uv run --frozen --offline --python 3.12 pytest --confcutdir=tests/flow_integration tests/flow_integration -q --maxfail=1
```

마지막으로 5개 테이블의 행수 0을 별도 SQL로 확인하고 이 임시 컨테이너도 제거했다.
기존 verith-postgres는 계속 exited다. Ruff·대상 format·diff 검사와 기존 보관함 카드
검사 **4 passed, 3 deselected**도 재실행해 통과했다. 새 의존성·DB 필드·설계 확장은 없다.

| 단계 | 필수 실제 검증과 현재 상태 |
|---|---|
| 이번 저장 계약 | 새 격리 PostgreSQL에서 실제 왕복·목록·손상 차단·삭제·rollback·P2 회귀 검사 29건 통과 |
| 인증·owner 구현 | 실제 로그인 세션·인증 문맥과 사용자 A/B의 목록·상세·근거·삭제 경계. 아직 미구현·미검증 |
| 공통 실행 구현 | 실제 Backend+격리 DB+가짜 AI의 접수→실행→저장→조회→삭제, 멱등 경쟁·늦은 저장·삭제 경합. 아직 미구현·미검증 |
| 실제 AI 연결 | 서비스 인증·실자료·수치 인용·자료 부족·오류 전달과 같은 결과 보존을 실제 경로로 검사. 아직 미구현·미검증 |

가짜 AI/메모리 Repository로 실제 로그인·인가·DB 경쟁·실제 AI 통과를 대체하지 않는다.
외부 유료 호출이나 사용자 데이터 변경이 필요하면 비용·영향을 먼저 보고하고 승인
전에는 진행하지 않는다. 이번에 그러한 호출이나 데이터 변경을 하지 않았다.

backend_coding_guidelines.md가 참조하는 api_spec.md/contracts.md/enums.md는 현재
checkout에 없어 이번 한정 계약과 legacy 응답 변경은 이 문서에 명시한다.

## 변경 파일과 영향

- schemas/flow_payload.py, flow_execution.py, flow_report.py: v1 구조와 공개/내부
  계약, 안전한 오류, 원본을 변환하지 않는 저장 입력 검증.
- services/flow_report_service.py: 저장 직전 재검증, 한시 snapshot·형식 표식 저장,
  구/신규 reader 분기와 root·자식·목록 정합성 대조.
- repositories/flow_report_repository.py: 결과 인덱스 조회와 목록용 일괄 자료 조회.
- services/technical_report_service.py: 기존 공통 목록/보관함의 Flow 행에 같은 대조 적용.
- routes/flow_reports.py, reports.py: 입력/손상 결과의 안전한 오류 응답.
- docs/flow_contract.md, flow_backend_handoff.md, schema.md: 계약·한계·검토 출처·검증 기록.
- tests/fixtures/flow_payload.py, tests/unit/{conftest.py,test_flow_contract.py},
  tests/flow_integration/{conftest.py,test_flow_persistence.py}: 합성 fixture, 네트워크를
  차단한 단위 검사, 명시적으로 선택하는 실제 격리 DB 검사.

새 의존성·lockfile 변경·물리 스키마 변경·AI/Frontend 코드 변경은 없다.
