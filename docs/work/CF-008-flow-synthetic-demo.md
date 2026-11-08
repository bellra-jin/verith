# CF-008 · Flow 합성 데모 웹 요청과 조회

기본 비활성 `/flow/demo`의 **명시 요청→합성 입력 봉인→일회 fake 실행→데모 전용 저장→실제 owner 재조회**를 Backend/BFF/UI에 연결했다. 기존 receipt·입력·일회권 구현/DB 계약·실제 보관함은 변경하지 않았다. Backend 보호 self20/20·unit18파일938/938, Frontend self24/24·unit6파일132/132·standalone type·대상 lint가 통과했다. 예상 밖 guard0·자기 임시 root 제거를 확인했다. lint에는 기존 `flow-report-view.tsx`의 미사용 `cls` 경고1건이 남는다.

새 실제 owned PG/ASGI는 최종 회차 **6묶음·거부34·engine9/서로 다른 execution9/ID당 최대1·exit0**으로 통과했고 exact CID 부재/해당 label0을 확인했다. 첫 metadata/cleanup 실패와 별도 복구, checker 기대값 실패/진단은 아래에 보존한다. **현재 source의 Next build/HTTP·실제 React/브라우저는 미실행·미검증**이다. 공개 웹 전체 통합 성공이나 실제 Google/KIS/AI 성공을 뜻하지 않는다. 실제 설정·사용자 키/캐시·외부 provider·기존 DB/volume 사용은 없다.

## 기준·범위·구현

- 정본 전체를 읽고 대조한 CF-008 v1.0 SHA `374f186422a8034ae23c4e682c84982b72f41671c1eff5bbff38ed9d4c7baa92`로 시작했다. 같은 작업의 v1.1 SHA `dc2248f20fbfd398ee8eaf2254390069353a562e86756ebbd81e5c86b63abdec` 전체를 수신·대조했다. v1.1은 ports VM loader 정확1파일 추가와 HTTP flag 전달 한계 정정이다. 외부 정본/보존본·공유 계약/manifest는 수정하지 않았다.
- base/HEAD `d5c0a1dea251728598fb45556303d77b0ab2c014`, branch `feat/flow-synthetic-demo-web`, origin fetch/push 단일 `https://github.com/bellra-jin/verith.git`, worktree1. 직전 CF-007 PR #11 병합·fetch/ff-only 확인을 재사용하고 착수 시 clean 상태·동명 branch 없음만 대조해 새 branch를 만들었다. reset/clean/stash·사용자 변경 덮어쓰기 없음.
- 최종 exact33파일(code/test/entry29 + 안내/결과4). 기존 CF003/006/007 제품·DB 모델/registry/migration·auth/OIDC·계산/Gate/payload·Frontend guard/package/lock/Next AGENTS 블록은 불변이다. Next16.2.10 번들 page/route/cookies 가이드를 읽고 Promise searchParams를 await했다.

Backend는 정확 POST `/api/flow/synthetic-demo/runs`, GET 같은 경로의 UUID 상세만 연다. gate false·인증 미설정은 body/dependency/engine 전에 닫는다. 실제4096byte 제한·strict UTF-8·중복 JSON key·비유한 수/extra/type·strict bool True를 검사한다. 세 필드 key/as_of/allow_fake만 받아 ticker005930·고정 question·full20/v1을 서버에서 정한다. actual principal/CSRF/owner를 유지하고 새 오류는 고정 CommonResponse/request_id·private/no-store·Vary Cookie/Origin으로 닫는다.

admit→prepare→execute는 기존 자체 commit을 순차 호출하며 전체 원자 transaction으로 가장하지 않는다. 부분 확정·claim/terminal ACK·HTTP 응답 유실 뒤 같은 key/as_of replay는 동일 ID를 회수한다. GET은 owner/fixed marker/full20/v1 봉인만 허용하며 short4·일반 receipt·타인/없는 ID는404다. 하위 not_found만 admitted/prepared로 표시하고 corrupt/auth/unavailable을 감추지 않는다. 새 실행을 만들지 않지만 기존 owner 한정 running→timed_out 만료 확정은 수행할 수 있다.

BFF는 정확 demo POST에만 bounded 원문 bytes와 안전한 Content-Type을 전달한다. 기존 logout의 body 없음·Cookie 원문/Origin/CSRF 전달·임의 owner/service 헤더 배제·canonical3200→8200 Host/Origin은 유지한다. 새 서버 flag는 정확 문자열 true만 켜며 malformed BACKEND_URL/transport 오류는 안전 envelope로 닫는다.

UI는 opt-in·동기 busy·계정/tab 전용 pending key/as_of 보존·명시 replay와 고정 자기 URL만 사용한다. run/user UUID는 lowercase, 멱등 key bytes는 보존한다. refresh/back은 자동 POST0, GET/POST running은 공통1초/최대15회 poll loop를 쓴다. startNew/이탈은 timer/abort/generation을 먼저 무효화하고 오래된 응답/타이머를 거부한다. 실제 결과/CSRF를 storage에 저장하지 않는다. 성공은 데모 전용 저장이며 실제 시세/투자 분석·보관함 게시가 아니다. 자세한 [웹 계약](../../backend/docs/flow_synthetic_demo.md)을 따른다.

## 필요한 검사와 실제 결과

실행일 2026-11-08 KST. 정확한 self/unit/type/lint 시작·끝 wall-clock은 별도 capture하지 않았다. 기존 보호 입구를 각각 공식 실행했으며 raw pytest·원본 dev server·보호 해제는 없다.

```sh
/usr/bin/env -i LANG=en_US.UTF-8 TZ=UTC /Users/parkjinhee/AI/verith_refactor/verith/backend/.venv/bin/python -I -S backend/scripts/check_safe.py self-test
/usr/bin/env -i LANG=en_US.UTF-8 TZ=UTC /Users/parkjinhee/AI/verith_refactor/verith/backend/.venv/bin/python -I -S backend/scripts/check_safe.py unit
/usr/bin/env -i LANG=en_US.UTF-8 TZ=UTC OPENSSL_CONF=/dev/null /opt/homebrew/Cellar/node/22.7.0/bin/node frontend/scripts/check-local-ports.mjs self-test
/usr/bin/env -i LANG=en_US.UTF-8 TZ=UTC OPENSSL_CONF=/dev/null /opt/homebrew/Cellar/node/22.7.0/bin/node frontend/scripts/check-local-ports.mjs unit
/usr/bin/env -i LANG=en_US.UTF-8 TZ=UTC OPENSSL_CONF=/dev/null /opt/homebrew/Cellar/node/22.7.0/bin/node frontend/scripts/check-local-ports.mjs type
/usr/bin/env -i LANG=en_US.UTF-8 TZ=UTC OPENSSL_CONF=/dev/null /opt/homebrew/Cellar/node/22.7.0/bin/node frontend/scripts/check-local-ports.mjs lint
```

| 회차 | 실제 결과·구분 |
|---|---|
| Backend 최초 self/unit | 20/20·18파일937/937·exit0·skip/guard0·각 root 제거 |
| Backend 진단 영향 unit | 고정 source/function/정수 line만 출력하는 helper와 합성 비노출 회귀1개 추가 후938/938·exit0·skip/guard0·root 제거 |
| Frontend self | 24/24·exit0·root 제거. unit에서도 동일 tooling24가 통과했다 |
| Frontend 최초 unit | disabled10/proxy6 통과 뒤 기존 ports의 VM loader가 새 import를 몰라1pass/2fail·controller78. guard0·root 제거. 무관한 source 통과를 최종 전체 통과로 쓰지 않는다 |
| Frontend v1.1 영향 unit | 실제 flag source+동일 합성 env·필요 randomUUID만 loader에 연결, unknown import는 계속 거부. 6파일10+6+3+24+84+5=132/132·exit0·skip0·예상 밖 guard0·root 제거 |
| 최초 type/lint | standalone type exit0. lint는 SSR try/catch 내 JSX와 새 test의 module 변수명에6오류·기존 경고1, controller78·guard0·root 제거 |
| 수정 후 type/lint | JSX는 데이터 준비 뒤 try 밖에서 반환, test 변수는 bundle로 rename. 최종 type exit0·lint0오류/기존 경고1·guard0·각 root 제거. v1.1 ports loader까지 포함한 최종 lint도 같은 결과 |

Backend unit은 실제 full app의 제한 dependency/mock과 순수 DTO/조율 검사를 포함한다. 유효 세 필드 JSON+공백4096 허용/4097 거부, 누락/작은 Content-Length·여러 chunk 경계, 유효 JSON 문자열 내부 invalid UTF-8로 각각 원인을 분리했다. 옛 OpenAPI/schema/payload digest는 정확한 두 path·세 component/새 model-schema 추가분만 독립 검증·투영한 뒤 그대로 비교하며 negative projection도 유지한다.

Frontend actual flag의 exact true/미설정/잘못된 값은 제한 합성 env에서 실제 함수로 검사했다. transport catch는 유효 고정 base+rejecting fetch로 직접 확인했다. 나머지 helper/VM/source assertion은 실제 React 클릭·timer/navigation 시험이 아니다. UI generation/polling 회귀는 순수 helper 실행과 wiring/source assertion이며 브라우저 동작 완료로 확대하지 않는다. type은 자기 사본의 표준 Next core/image references를 쓰는 **standalone tsc**이며 generated-route/typegen/full build 검증이 아니다.

각 FE guard 관측에서 예상된 음성시험14회는 위반0과 구분한다. native I/O는 관측하지 않았고 parent의 승인된 공개 package 사전/사후 읽기도 worker 관측과 별도다. 수집 전 보호·기존 fixed 선택/원공개 digest/hash/origin·plugin/환경/FS/OS/network 경계를 유지했다.

## 실제 owned PG/ASGI — 실패·진단·성공

기존 Python3.12.13 `isolated=1/no_site=1/no_bytecode=true`, clean env와 exact 기존 site-packages를 사용했다. 새 DB-only mode `--verify-flow-synthetic-demo-db`는 기존 local Docker/캐시 image·pull=never·소유증명·readonly preflight·같은 연결 migration·제한 role·자기 HOME·dotenv/외부 차단과 finally cleanup을 유지한다. 새 설치·기존 DB/volume 채택·앱 listener/Google/provider 호출은 없다. 기존 CF003/006/007 전체 PG suite를 중첩하지 않았다.

| 회차·명령 시작 UTC | 자원/CID·Docker 생성시각 UTC | 결과 |
|---|---|---|
| PG1 10:16:32.710724 | CF-002-login-3e5de71d87e9 / d7095daf0616467b98647d1ed657b51b9fa946919007ba96eb434f597d15290a / 10:16:34.411853208Z | owned_creation metadata 실패·cleanup_failed·exit2. 앱/migration/checker 미실행 |
| PG2 10:18:36.603050 | CF-002-login-3e69f5df2e90 / 259b7444b574975fcf7cf366f8e3f5aadf88139016d275e8b3f323a7879be579 / 10:18:36.814759918Z | 소유/migration/default-off 통과 후 strict_body_and_auth 고정 VerificationFailure·exit1·runner 제거 |
| PG3 진단 10:21:38.856990 | CF-002-login-8cc414fdb277 / cdc42f2b6ee40c2b8b4e1cf9ece41a487814b465ceea2479f603f485d5eb5879 / 10:21:39.076726127Z | 같은 실패. 새 고정 alias/함수/line만으로 checker의 CSRF/Origin 기대값 위치를 확인·exit1·runner 제거 |
| PG4 수정 10:22:45.339736 | CF-002-login-c95fc9bb335c / 5725a33c5f26fe1d9cd05bfa83c6f61a602e98ccdb9ba62eab258d14bbf2c784 / 10:22:45.48731413Z | 아래6묶음34거부·exit0·runner 제거 |

생성시각은 명령 시작/끝과 다르며 명령 종료 정확 wall-clock은 미수집이다. PG1의 최초 metadata 거부 predicate는 미확정이다. 같은 CID가 running인 read-only metadata와 직접 생성 로그의 CID/resource를 확인한 뒤, exact CID/Created/name/resource·내부 nonce/고정 command 일치·read-only/mount0/tmpfs/namespace/loopback port를 대조해 그 자기 자원만 stop→rm한 별도 복구다. 최초 메모리 receipt를 재구성하거나 helper accept/reject·시간/소유 조건을 바꾸지 않았다. helper cleanup 성공으로 소급 기록하지 않는다. 복구 후 exact CID 부재/해당 label0을 확인했다.

PG2/3의 실제 원인은 새 checker의 잘못된 **403 기대값**이었다. 기존 request_principal/verify_csrf는 CSRF/Origin을401 AUTH_REQUIRED로 거부하므로 checker만401로 수정했다. 별도 local Host 거부403은 유지했다. 제품/auth/하위 service/guard는 변경하지 않았다. 진단은 고정 source 별칭/허용 함수/정수 행번호 최대8개만 출력하고 원문/locals/자격/nonce/경로는 출력하지 않는다. 합성 비노출 unit을 통과했다. 이 기대값 수정과 PG4 성공은 PG1의 최초 실패 원인 규명 증거가 아니다.

| 최종 실제 PG 묶음 | 확인 |
|---|---|
| 기본 닫힘/독립 gate | off·인증 미설정 때 body/dependency/engine/쓰기0, 기존 receipt gate 독립 닫힘 |
| body/실제 인증 | 실제 합성 server session·CSRF/Origin/Host·중복 Cookie·만료/폐기, 유효4096/4097·chunk/Content-Length·strict UTF-8/JSON/type |
| 저장/owner/replay | fixed full20 봉인·fake 원자 artifact 저장·별도 attested owner GET·다른 본인 세션 replay, 고정 수치/단위/ID/hash, 타인/없는404·입력변경409 |
| 부분/불명확 결과 | admit/prepare 중단 후 명시 replay, claim/terminal 실제 commit 뒤 ACK 유실·완료 HTTP 응답 유실, 엔진 오류/timeout terminal·재호출0 |
| 경합 | 두 attested 요청 연결의 실제 run lock wait/barrier로 동일 POST 경쟁, run/seal/execution 같은 ID·engine 최대1 |
| 조회/범위 | non-demo/short4 prepared·terminal404, corrupt502/unavailable503 구분, owner GET expiry만 확정·새 행/engine0, 기존 receipt/input/result bytes·report/index/stock 불변 |

최종 engine 호출9는 서로 다른 시험 execution9개의 합이며 실제 외부 AI 호출은0이다. scoped private_file/external_network/external_http/dotenv_discovery denial0은 Python wrapper 범위이며 native 전체 tracing이 아니다. PG2/3/4는 runner 제거 뒤 정확 CID 부재/각 resource label0을 별도 읽기 확인했다. Docker 앱/기존 image와 다른 자원은 보존했다. 전역 컨테이너0을 주장하지 않는다.

실제 launcher는 repo cwd에서 `set -o pipefail`, `env -i PATH=/usr/local/bin:/usr/bin:/bin LANG=en_US.UTF-8 TZ=UTC PYTHONDONTWRITEBYTECODE=1`, `backend/.venv/bin/python -I -S -B -c`로 exact `backend/.venv/lib/python3.12/site-packages`와 backend를 sys.path에 넣고 `runpy.run_path(.../scripts/cf002_interactive_login.py, run_name='__main__')`를 호출했다. sys.argv의 mode는 위 단일 mode다. runtime 시작 metadata 출력과 stderr→stdout·nonce redaction sed·해당 checkpoint log tee를 사용했다. 기존 self/unit/type/lint의 성공과 PG 실패/성공은 별개다.

## 미검증과 독립 검토

- 새 HTTP test source는 gate-on 실행 준비 완료가 아니다. 기존 Mac build의 unknown 파일 접근 guard 차단과 별개로 preload env whitelist/forkPlan이 `FLOW_SYNTHETIC_DEMO_ENABLED`를 제거한다. safe-http의 env 조립은 실제 Next worker 전달 증거가 아니다. 이번 guard/OS policy는 불변이고 build/HTTP를 재요청하거나 새 플랫폼/설치로 우회하지 않았다.
- 현재 NextHTTP는 소스만 작성했으며 목표도 실제 Next+fake HTTP Backend 계약 시험이다. 완전한 실제 session/owner/PG/UI 시나리오를 검증한 것이 아니다. 실제 브라우저의 클릭/double click/back/refresh/계정 전환·Next→진짜 Backend→PG는 미검증이다.
- 실제 Google 로그인·KIS/OpenAI·실자료 분석·운영 DB·보관함 게시/삭제·일반 worker·full generated-route/typegen/build는 이번 결과에 포함하지 않는다. 과거 Docker build 성공을 새 source의 성공으로 재사용하지 않았다.
- coordinator의 독립 source 검토에서 full20 GET 분류, startNew generation/timer·sameURL running polling, UUID canonical화, 실제 flag/transport와 byte/UTF8 회귀를 보완했다. 검토자는 runtime을 재실행한 것이 아니다. 최종 Backend/FE 독립 source·로그 검토도 추가 필수 결함 없음으로 수용됐다. 이는 독립 runtime 재실행이 아니다.

## source·Git 인계

자기 checkpoint: `/var/folders/d7/v1s6ddq12y9fftsqrvrgcz140000gn/T/cf008-baseline-aup2dp21`.

- scope.json exact33·baseline.json/기존 bytes, scope-v1.0.json은 당시32를 보존한다.
- round-1-source.json은 첫 회차, pg-diagnostic-source.json은 고정 진단 시점, validated-source.json은 최종 code29 SHA다. Backend 최종 unit 이후 checker의 CSRF/Origin 기대값만401로 맞췄고 그 checker는 최종 실제 PG에서 검증됐다. 통과한 무관한 self/unit을 반복하지 않았다.
- final-source.json은 최종33 path/size/SHA·base/branch/정본 metadata이며 자기 hash를 포함하지 않는다. stage-pathspec.nul은 각 exact 경로 앞 `:(literal)`을 붙인 NUL pathspec이다.
- reviewguard.py는 branch/base/HEAD/origin/worktree·전체 변경 집합·staged/ignore·regular single-link/no-symlink·source hash·PR marker/body를 읽기 전용으로 확인한다. --staged는 index bytes도 확인한다. 현재 상태가 달라지면 먼저 재검토한다.
- review-pr-body.md는 아래 marker 사이 실제 본문이다. marker는 각각1회만 둔다. log-hashes.json과 pg-round-*-absence/recovery.json에 원문 로그 hash와 정확 자원 부재를 보존했다. 외부 임시 증거는 clone의 영구 파일이 아니므로 필요하면 인계 전에 보존한다.

사용자 실행 전 diff·exact33·기밀/무관 변경을 검토한다. 다음은 **사용자용 초안이며 에이전트가 실행하지 않았다**. origin/base/head와 stage집합이 달라지면 중단한다.

```sh
cd /Users/parkjinhee/AI/verith_refactor/verith
python3 /var/folders/d7/v1s6ddq12y9fftsqrvrgcz140000gn/T/cf008-baseline-aup2dp21/reviewguard.py
git diff --stat
git diff --check
git diff -- backend frontend docs
git add --pathspec-from-file=/var/folders/d7/v1s6ddq12y9fftsqrvrgcz140000gn/T/cf008-baseline-aup2dp21/stage-pathspec.nul --pathspec-file-nul
python3 /var/folders/d7/v1s6ddq12y9fftsqrvrgcz140000gn/T/cf008-baseline-aup2dp21/reviewguard.py --staged
git diff --cached --stat
git diff --cached --check
git diff --cached
git commit -m "feat(flow): connect synthetic demo requests and owner reads"
git push -u origin feat/flow-synthetic-demo-web
gh pr create --repo bellra-jin/verith --base develop --head feat/flow-synthetic-demo-web --draft --title "feat(flow): connect synthetic demo requests and owner reads" --body-file /var/folders/d7/v1s6ddq12y9fftsqrvrgcz140000gn/T/cf008-baseline-aup2dp21/review-pr-body.md
```

`git diff`는 untracked 새 파일 본문을 보여주지 않으므로 exact manifest의 새 파일도 직접 검토한 뒤 stage한다. add/commit/push/실제 PR/Ready/merge는 사용자만 수행한다.

<!-- CF008_PR_BODY_START -->
## 변경

로그인 사용자 전용 `/flow/demo`에 명시 요청→고정 합성 입력→일회 fake 실행/데모 전용 저장→본인 재조회 흐름을 연결합니다. Backend와 서버 BFF는 기본 비활성이며 strict opt-in/raw4096-byte JSON·실제 session/CSRF/owner·private/no-store를 유지합니다. 부분 commit/응답 유실은 같은 요청 replay로 회수하며 기존 CF003/006/007 구현과 보관함/DB 계약은 바꾸지 않습니다.

UI는 계정/tab pending identity·double click 차단·generation/abort·제한 GET polling을 사용합니다. 실제 시세/투자 분석이나 보관함 게시가 아님을 표시합니다.

## 검증·한계

- Backend self20/20·unit938/938, Frontend self24/24·unit132/132·standalone type·대상 lint 통과. 예상 밖 guard0·임시 root 제거. 기존 lint 경고1건은 남습니다.
- 새 owned PG/ASGI6묶음·거부34·서로 다른 execution9/최대1회·exit0, 정확 CID 부재를 확인했습니다. 초기 metadata/cleanup 실패의 별도 복구와 checker 기대값 수정/재검증을 작업 기록에 보존했습니다.
- UI 회귀는 helper/VM/source 검증입니다. NextHTTP/실제 React·브라우저는 기존 build guard 및 demo flag 전달 제약으로 미실행이며 gate-on HTTP 준비 완료를 주장하지 않습니다. standalone type은 full typegen/build가 아닙니다.
- 실제 Google/KIS/AI·운영 DB·기존 보관함 게시는 포함하지 않습니다. 상세 source·실행/실패/정리 증거는 docs/work/CF-008-flow-synthetic-demo.md에 있습니다.
<!-- CF008_PR_BODY_END -->
