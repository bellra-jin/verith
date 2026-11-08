# CF-012 Flow 인증 분석·본인 저장

기준 develop `04d2ff8fd550608dfaf61ac53cdf780eabf7c5d9`, branch `feat/flow-analysis-report`. 최초 v1.0 SHA `9d20884df50be06726460435c44f46e5dbdf3a5a03fedbb44a8c271815c7d1d6`의 43경로로 착수했다. 현재 v1.1 SHA `f8296314cce46bccbd705295ba89192fe362707e693ef3ea969eeabfae05ff90`은 소유 helper와 기존 회귀 2경로만 추가한 정확 45경로다.

## 현재 수용 대기 상태

제품 연결과 변경 집중 검사는 통과했으며 최종 source 검토·Git 인계 대기다. Backend 새 입력 self 3/3, 집중 unit 267/267, owner helper 87/87, Frontend unit 16/16·변경 root type·대상 lint가 exit 0이다. 성공 PG는 실제 세션/owner·Flow-only ASGI deterministic engine의 6그룹/거절24건/분석ID11개 각각 dispatch1을 확인했고 exit 0·정확 CID 부재를 확인했다. 실제 공급자/사용자 자격/Google/기존 DB·브라우저/React E2E는 미검증이다. 아래 실패·복구는 당시 이력이며 현재 미완료로 읽지 않는다.

현재 구현: `/research` 요청/상태 UI → BFF → 실제 세션·owner Backend → Flow 전용 HTTP → 원본 v1 snapshot 선보존 → 본인 report 원자 게시/조회. receipt/synthetic/fake 및 공개 raw-payload save 차단은 유지한다. 실제 provider는 default-off이며 이번 작업에서 실제 자격 사용·외부 공급자 호출은 수행하지 않는다.

변경 관련 집중 검사를 완료했다. 최초 검증 계획과 실제 실행 범위는 아래에 구분한다. AI router/runtime의 정확 4개 source copy와 deterministic engine만 실행한다. 실제 workflow/KIS/LLM wiring은 source 검토이며 실제 graph·pandas·provider·브라우저/React 클릭 성공으로 확대하지 않는다. 원장 commit ACK 유실·게시 rollback/replay·소유권·세션 폐기·삭제 fence는 새 자기 PG+ASGI checker 대상이다. 기존 통과 전체 suite/Next Docker/browser는 반복하지 않는다.

## 집중 검사 현재 결과

- Backend 고정 새 입력 self 3/3 exit 0. 집중 unit 2파일 267/267 exit 0, guard 위반 0, 자기 임시 root 제거. 첫 fixture flush/새 schema 투영/테스트 principal 누락과 이어진 origin collection 연결 실패는 수정 이력으로 구분한다. 기존 payload/OpenAPI/schema digest는 그대로 유지한다.
- Frontend helper/BFF/config 3파일 16/16 exit 0. 변경 TS root 7개와 import closure의 standalone type exit 0. 대상 lint도 exit 0·오류/경고 0, 두 검사 guard 0·owned root 제거. 전체 generated-route/build/React/브라우저 검사가 아니다. source assertion 변수명 오류와 render ref 읽기 lint 오류는 수정 이력이다.
- owned PG 첫 회차는 생성 뒤 소유 metadata 검사와 cleanup에서 기존 helper가 거부해 exit 2. migration/앱/AI 검사는 미실행이다. 정확 CID `77e3b015a4c17da8ed59eb2fab6c010c6b92c0a379769421d34506b7bb3fd24d`, resource `CF-002-login-49d7e23e7df3`. 이후 읽기 전용 확인은 running/read-only/tmpfs/mount0/loopback binding을 확인했으나 최초 거부 원인을 확정하지 않았다. 기존 helper/시간/소유 조건은 변경하지 않았다. 이후 별도 cleanup-only 복구에서 생성 CID와 현재 metadata를 재대조한 뒤 stop exit 0 → 정지 확인 → rm exit 0 → 정확 CID absent=true를 확인했다. 원래 receipt 재구성/재채택은 없었으며 이 정리는 full guard 재통과나 기능 검사 성공이 아니다. 새 PG 검사는 미실행이다.

검사 증거는 `/private/tmp/cf012-baseline-6g_a2qzp`에 보존했다. PG 완료/정리 전 전체 수용·게시 가능으로 표시하지 않는다.

## v1.1 소유 helper 집중 보완·두 번째 PG

원본 receipt/verify_metadata/시간 window/기존 소유 조건은 유지했다. post-start readonly inspect 최대 3회·5초, 각 call 잔여 timeout·sleep 뒤 deadline 검사를 추가했다. 고정 identity/config 불일치는 즉시 거부한다. 실패 원 receipt는 별도 private 0700/0600 파일에만 보존하며 password/DSN/Env는 포함하지 않는다. cleanup 결과는 exclusive side record의 유효 JSON과 complete 표식으로 구분한다. 파일 fsync는 적용했지만 시스템/파일시스템 crash durability는 주장하지 않는다.

owner-focused 기존 unit 1파일 58/58 exit 0·guard 0·owned root 제거. 최초 사본 연결 누락으로 collection 0에서 중단된 이력을 보존하고, 정확 기존 helper/stdlib 의존 사본만 연결해 통과했다. 기존 267/16/type/lint는 반복하지 않았다.

두 번째 PG는 `CF-002-login-62e91d69618f`, CID `cf093c57537a2af5718aef81fb58e0a22140222a3b6bd5b5a704c3f6894b2c57`의 생성/metadata·cleanup 실패 exit 2로 중단했다. migration·기능은 미실행이다. 이후 실제 보존된 원본 receipt를 비공개로 대조해 nonce/원 시간 window/고정 Created/binding을 포함한 현재 full metadata guard 통과를 확인했다. 원 receipt 수정·자원 채택·DB 접속 없이 해당 CID의 stop exit 0 → 정지 상태와 full guard 재대조 → rm exit 0 → 정확 CID absent=true를 확인했다. 첫 자원의 별도 cleanup-only 복구와 이번 원본 receipt 기반 guard 재통과를 구분한다.

최초 실패 당시 inspect/attempt 판정은 미수집이므로 정확한 일시 항목을 소급 확정하지 않는다. 현재 guard 통과는 시간에 따른 status/port projection 변화 후보와 부합하지만 기능 검증 성공을 뜻하지 않는다. 새 PG 재실행과 게시/머지는 보류다.

## 고정 predicate 진단 회귀·세 번째 PG

원본 verify_metadata 본문/acceptance를 유지하고, 검토된 함수 source hash와 일치할 때만 원본 예외 traceback의 함수·상대 위치를 고정 enum으로 매핑한다. 미등록·내부 source 변경은 UNKNOWN이다. 예외 문자열/locals/nonce/원 시각/Env/전체 inspect는 출력하지 않는다. 새 helper frame whitelist와 phase/attempt/재조회 가능 boolean을 추가했다. owner-focused 84/84 exit 0·guard 0·owned root 제거를 확인했고 기존 기능 suite는 반복하지 않았다.

세 번째 PG는 resource `CF-002-login-489b4a1222f7`, CID `2e22329578c722b5f511ca050c7dbdc3d48d6f8a0177c5973e2d871c8ea0e6df`의 post-start poll 1/2/3에서 모두 LIVE_PORT_CARDINALITY / ValueError / transient_eligible=true로 실패했다(exit 2). 이 분기 조합은 live port 목록이 빈 배열인 경우를 특정한다. 당시 migration/앱/기능 검사는 미실행이다. 최초/두 번째 회차의 세부 원인을 이 결과로 소급 확정하지 않는다.

이후 보존 원본 receipt로 현재 full metadata guard가 통과하고 live binding count 1임을 확인했다. 동일 원본으로 stop exit 0 → 정지 상태 guard 재대조 → rm exit 0 → 정확 CID absent=true를 확인했다. receipt 수정·자원 채택·DB 접속·guard 완화는 없었다. 근본 Docker projection 지연 시간은 미측정이며, 현재 50ms 간격 3회가 실제 5초 재조회 예산을 사용하지 못한다는 source 차이를 다음 최소 수정 후보로 남긴다. 새 PG/추가 검사/게시는 중단했다.

## 0·2·4초 분산 조회와 네 번째 PG

동일 최대 3회/5초 안에서 post-start 조회를 절대 0·2·4초 목표로 분산했다. 각 read는 잔여 timeout만 쓰고, sleep overshoot/고정 identity 불일치/빈 binding은 계속 거부한다. owner-focused 87/87 exit 0·guard 0·owned root 제거를 확인했다. 기존 기능/Frontend suite는 반복하지 않았다.

네 번째 PG resource `CF-002-login-43b5c4cb57c2`, CID `c9508a35c0e9a8ae991a9cfc410ac18927284c7db6c5bbcecd01e2ddd33e744b`는 원본 full guard와 readonly preflight·동일 연결 migration을 통과했다. 새 revision DDL rollback/기존 receipt·snapshot·fake·legacy 보존과 strict body/session/owner 그룹을 통과했다. 첫 저장·동일 요청 그룹에서 stored 상태 assertion이 실패해 exit 1로 중단했다. runner 정리 후 exact CID absent=true를 독립 읽기 확인했다.

실패 source 대조: isolated_application의 고정 환경은 AI_SERVICE_URL을 설정하지 않고 제품 Settings 기본값은 빈 문자열이다. checker는 gate/token/ASGITransport를 주입하지만 AI_SERVICE_URL은 고정하지 않았다. 이 경로는 AIClient의 fail-closed 설정 검증에서 AIValidationError→failed 상태가 된다. 실패 로그에는 안전 error code/engine 계수 자체가 캡처되지 않았으므로 이를 과거 runtime 출력으로 만들지 않는다. 최소 보완 후보는 checker 안에서만 고정 가상 AI origin을 명시하는 것이며, 실제 transport는 계속 Flow-only ASGI로 한정한다. 아직 이 보완/추가 PG는 실행하지 않았고 게시/머지는 보류다.

## 최종 PG 성공과 검증 범위

checker에만 `http://synthetic.invalid`를 고정하여 빈 설정의 제품 fail-closed를 보존했다. 실제 transport는 Flow-only ASGI이며 DNS/TCP/외부 공급자를 호출하지 않는다. 다섯 번째 PG에서 첫 응답 status 200/state stored/error null/fake dispatch1을 관측했다. 앞선 checker 누락 원인은 source 대조와 이 보완 후 관측으로 구분한다.

- 실행 exit 0. readonly preflight·동일 연결 migration 후 새 revision DDL 실패 rollback·이전 receipt/snapshot/fake/legacy 보존, strict 입력/실제 세션·CSRF·Origin·owner, 원자 저장·동일 URL/동일 key replay·동시 key winner, claim/snapshot/게시 ACK·rollback 복구, 잘못된 결과·늦은 응답 fence·대기 중 세션 폐기, tombstone·legacy ID 충돌/삭제 순서를 통과했다.
- 6그룹, 거절24건, fake dispatch11 / analysis ID11, 각 ID 실행1. private file/외부 network/외부 HTTP/dotenv discovery의 scoped guard denial은 모두0이다. native 전수 추적이나 실제 AI 품질 검증을 뜻하지 않는다.
- CID `113028c223bd4a650c8250bec7cc9e4fe6ad78fe3bb845836dca96b53b1399f8`, resource `CF-002-login-1d59e507bd6a`. runner의 원래 full guard 기반 정리 후 정확 CID absent=true를 별도 읽기 확인했다. 앞선 네 자원도 각 정리/부재 증거를 보존했다. 기존 다른 자원은 조회/정리하지 않았다.
- Backend 집중 검사는 신규 분석 경계와 변경 기존 v1 계약 2파일 267개이며 전체 Backend suite가 아니다. owner helper 87개는 해당 기존 회귀 파일1개다. Frontend 16개는 helper/BFF/config VM 및 source assertion이며 React 클릭·navigation/timer runtime이 아니다. type은 변경 root7개와 import closure의 standalone core/image 범위이며 generated routes/typegen/build를 반복하지 않았다.
- AI 정확 source4를 보호 사본에서 주입 engine으로 실행했다. 실제 agent/workflow/KIS/LLM 연결은 source 검토이며 실 graph/pandas/provider/cache 실행은 없다. 실제 활성화에는 서버 URL/token·provider gate·허용 자료/약관·호출/비용/배포 동시성 확인이 필요하다.

증거: `/private/tmp/cf012-baseline-6g_a2qzp`의 `backend-self-1.log`, `backend-unit-3.log`, `owned-unit-schedule-1.log`, `frontend-unit-3.log`, `frontend-type-2.log`, `frontend-lint-2.log`, `pg-5.log`, `pg-5-absence.json`. `pg-5-source.json`은 성공 실행 직전 source를 고정한다. 이후 제품/검사 source 변경 없이 결과 문서와 최종 manifest를 정리했다.

## Git 검토 인계

정확45경로·단일 branch/base/origin·staged0·regular single-link/no-symlink·ignore 누락0·diffcheck를 최종 checkpoint에서 대조한다. checkpoint의 `final-source.json`, literal-path 명령용 `stage-paths.nul`, `review-pr-body.md`, read-only `reviewguard.py`를 함께 확인한다. 상태가 바뀌면 인계 검증도 다시 확인한다. 실제 게시 절차 전에 최종 source 검토를 완료한다.

권장 commit: `feat(flow): connect authenticated analysis to atomic owner reports`

PR 초안은 아래 marker 사이이며 checkpoint 본문과 byte 대조한다.

<!-- CF012_PR_BODY_START -->
인증된 `/research` 요청을 Flow 전용 내부 HTTP와 본인 v1 리포트 저장·조회에 연결합니다. claim을 commit한 승자만 한 번 dispatch하고, 검증된 입력/결과 snapshot을 먼저 보존해 저장 재개 시 AI를 다시 호출하지 않습니다. 삭제 tombstone·늦은 응답 fence·기존 report ID 충돌을 처리하며 receipt/synthetic/fake와 공개 raw-payload save 차단을 유지합니다.

- 실제 provider는 기본 비활성입니다. 기존 Flow 계산/해석 엔진 wiring을 재사용하되 이번에는 deterministic ASGI engine만 실행했습니다.
- Backend self3·집중 unit267·owner helper87, Frontend unit16·변경 type/lint 통과. 실제 자기 PG의 6그룹/거절24/11개 ID 각각 dispatch1·정리/부재 통과입니다.
- post-start 빈 live-port projection을 full guard 허용 없이 3회/5초 내 0·2·4초 재조회로 처리합니다. 최초 실패·cleanup 복구 및 checker 가상 URL 누락 이력은 작업 기록에 남겼습니다.
- 실제 KIS/OpenAI/Google·기존 DB·브라우저/React E2E·전체 suite/generated-route/build 검증은 포함하지 않습니다. 실제 활성화에는 서비스 자격·자료/약관·호출/비용·배포 동시성 확인이 필요합니다.
<!-- CF012_PR_BODY_END -->
