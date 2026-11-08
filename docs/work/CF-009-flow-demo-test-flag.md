# CF-009 · Flow 데모 flag 전달과 보호 회귀

보호 preload와 `forkPlan`의 **exact demo flag 값 검증·부모 값 보존**을 구현했다. 최종 변경 관련 보호 self-test **27/27·exit0·skip/fail/cancel/todo0**, 예상 음성시험14·예상 밖 guard0·진단 실패0·자기 임시 root 제거를 확인했다. 실제 Next worker/HTTP·React/브라우저 전달은 미검증이며 기존 build 입력 차단은 해결하지 않았다.

## 기준·변경·불변

- CF-009 v1.0 정본 전체와 SHA `6c3e7cb475fc4ee0b424eae17b26b87a6543c77a12ee5190be252cae2fdfe8ba`를 대조했다. 운영 v1.1/v1.2/v1.2와 root/Frontend AGENTS를 적용했다. 외부 지시서/과거 기록은 수정하지 않았다.
- base/HEAD `fb29bf322024f93507d45a8e57ee8605414e5b40`(CF-008 PR #12), branch `fix/flow-demo-test-flag`. clean develop·origin fetch/push 단일 `https://github.com/bellra-jin/verith.git`·worktree1·동명 branch 없음 확인→fetch→ff-only Already up to date→전용 branch 생성 순서다. 기존 변경 덮어쓰기/reset/clean/stash·publishing 없음.
- 정확4파일: `frontend/scripts/safe-checks-guard.cjs`, `frontend/tests/tooling/safe-checks.test.mjs`, `docs/documentation.md`, 이 worklog. controller/safe-http·CF008 제품·Backend/DB·package/lock/config·OS policy는 불변이다.

작은 순수 `validateDemoFlag`는 undefined/문자열 true/false만 받는다. 빈 값·공백·case 변형·숫자/boolean/object 등을 강제변환 없이 값 없는 고정 `SAFE_CHECK_DENIED: demo flag`로 거부한다. preload는 capability를 읽고 guard를 설치하기 전에 flag를 검증하고, 정확 키만 allowed set에 남긴다. 다른 secret/unknown/lookalike는 기존처럼 제거한다.

fork는 정제된 parent `cap.environment` 값을 검증한 뒤 그대로 복사한다. parent 미설정이면 출력 own-key도 없고, child options의 키 누락은 parent를 유지한다. child에 own-key가 있으면 유효하고 parent와 같아야 한다. parent 미설정/false→child true 주입, true→false 덮어쓰기와 malformed를 모두 거부한다. 다른 환경 상속·새 capability 필드·일반 CLI env 경로는 추가하지 않았다.

작은 helper/export·fork flag 처리·preload 검증/키 추가만 역제거하면 guard 원본 bytes가 정확히 복원된다. 새 시험3개를 제외하면 기존 시험24개를 포함한 원본 test bytes가 같다. FS/socket/DNS/UDP/TLS/HTTP/process·원본 raw-read/package snapshot/진단·필수 preload/OpenSSL/capability/fork target/argv/cwd/IPC/수명·정리 로직은 변경하지 않았다. `guard-delta.json`에 대조 결과를 보존했다.

## 실제 영향 검증과 독립 검토

2026-11-08 KST에 아래 기존 공식 보호 명령을 실행했다. 정확 시작/끝 wall-clock은 별도 capture하지 않았다. 첫 결과 기록 시각은 19:53 KST이며 명령 시작 시각이 아니다. 별도 raw Node/Next·새 child/IPC harness는 실행하지 않았다.

```sh
set -o pipefail
/usr/bin/env -i LANG=en_US.UTF-8 TZ=UTC OPENSSL_CONF=/dev/null /opt/homebrew/Cellar/node/22.7.0/bin/node frontend/scripts/check-local-ports.mjs self-test
```

실제 명령은 stderr를 합쳐 해당 checkpoint의 log로 tee했고 TAP 집계만 화면에 출력했다. clean env·고정 OpenSSL·OS preflight·자기 사본·기존 보호 preload·cleanup 경로를 유지했다.

| 회차 | 실제 결과 |
|---|---|
| 첫 구현 | 27/27·exit0·예상 음성시험14/예상 밖 위반0·root 제거. 독립 검토에서 fork baseline 동등성만으로 secret 키 부재를 직접 증명하지 못한 assertion 누락1건 발견 |
| assertion 영향 재검증 | 제품 guard는 불변. 반환 env의 GOOGLE_CLIENT_SECRET/UNREVIEWED_ENV/FLOW_SYNTHETIC_DEMO_ENABLED_LOOKALIKE own-key 부재를 직접 추가 후27/27·exit0·fail/skip/cancel/todo0·음성14/위반0·root 제거 |

최종 log `frontend-self-test-final.log` SHA `bce97a0dd509cf20ee49469afec463a48f5b56d71206f0b082a494ce8e240bb8`, 최초 log `frontend-self-test.log` SHA `87533f3a351d4ecf842e48a00b96bb6ded4a6a3bf44bae9fd6160c6311b4cf2b`다. 최종 tool chunk `41d5de`의 exit0·root 제거와 로그 TAP를 구분한다. 양 회차 worker1/exit record1/partial0·진단 실패0이며 native I/O는 미관측이다. parent의 승인된 공개 package 읽기4회는 worker와 별도다. 최초 결과를 최종 test source 결과로 재사용하지 않았다.

새 회귀3개는 실제 순수 validator, 실제 `forkPlan` 반환 env, AST로 정확한 실제 preload 블록 하나를 고른 제한 VM을 검사한다. VM의 process env/capability JSON/파일 읽기/install은 모두 합성이며 실제 guard 설치나 Next child를 실행하지 않는다. 값 비노출 canary, true/false/absent·malformed, parent 보존·child 주입/상충 거부, 다른 secret/unknown/lookalike own-key 제거와 기존 보호를 확인했다. 공식 self worker가 기존 보호 preload를 사용한 사실을 새 true/false의 실제 Next worker 전달 관측으로 확대하지 않는다.

독립 source 검토에서 guard 구현·보호 불변은 수용됐다. 누락된 직접 own-key assertion을 보완하고 위 한 회차만 영향 재검증했다. 최종 source/인계 대조는 대기 중이며 독립 runtime 재실행으로 기록하지 않는다.

## 미실행·남은 차단

- 이번에는 build/HTTP·React/브라우저·전체 FE unit/type/lint·Backend/PG를 실행하지 않았다. 실제 설정/키/사용자 cache/profile·운영 DB·외부 provider·설치 사용0이다. 과거 CF008 결과를 이번 결과로 복사하지 않았다.
- flag 전달 source 보완은 cgroup 탐색·verified copy 밖 unknown webpack hash9개 문제를 해결하지 않는다. 기존 blocked build/local-http는 재요청하지 않았고 새 원본 읽기·HMAC/verbose/역탐색·가짜 ENOENT·CI/cache/resolver/telemetry/dependency 변경은 없다.
- 별도 owned 검증 공간의 공개 source/locked dependency 배치나 실제 브라우저는 후속 범위다. 실제 앱 사본·Backend/owned PG·합성 server session·자기 browser context가 필요하며 shared 누락 copy helper를 여기서 고치거나 사용자 profile/기존 DB로 대체하지 않았다. 현재 보호 시험의 성공을 웹 전체 통합 완료로 선언하지 않는다.

## 최종 source와 사용자 Git 인계

| source | SHA-256 |
|---|---|
| guard | `3a9cb45bc865d560612ccd5876f060c69aa0abe5ff635576888781d9efe7d3ee` |
| 최종 tooling test | `224ac79d90f75b85217cd1b4e8d73de8d9f5ef520ffbefa4d1b7a3c3a94e0365` |

자기 checkpoint `/var/folders/d7/v1s6ddq12y9fftsqrvrgcz140000gn/T/cf009-baseline-3mv5ckqi`에 scope/baseline·기존 bytes·허용 delta 대조·첫/최종 log와 code SHA를 보존했다. `final-source.json`은 exact4 path/size/SHA·base/branch/정본 metadata, `stage-pathspec.nul`은 각 path의 `:(literal)` NUL 목록, `review-pr-body.md`는 아래 marker 사이의 실제 본문이다. `reviewguard.py`는 branch/base/HEAD/origin/worktree·변경/staged 집합/ignore·regular single-link/no-symlink·hash/PR body를 읽기 전용 대조하며 --staged는 index bytes도 확인한다. 상태가 바뀌거나 임시 증거가 없어지면 현재 bytes를 다시 검토한다.

다음은 사용자용 초안이며 에이전트는 실행하지 않았다. exact4 새 파일 본문·기밀/무관 변경까지 검토하고 stage 뒤에도 diff를 확인한다.

```sh
cd /Users/parkjinhee/AI/verith_refactor/verith
python3 /var/folders/d7/v1s6ddq12y9fftsqrvrgcz140000gn/T/cf009-baseline-3mv5ckqi/reviewguard.py
git diff -- frontend/scripts/safe-checks-guard.cjs frontend/tests/tooling/safe-checks.test.mjs docs/documentation.md
cat docs/work/CF-009-flow-demo-test-flag.md
git add --pathspec-from-file=/var/folders/d7/v1s6ddq12y9fftsqrvrgcz140000gn/T/cf009-baseline-3mv5ckqi/stage-pathspec.nul --pathspec-file-nul
python3 /var/folders/d7/v1s6ddq12y9fftsqrvrgcz140000gn/T/cf009-baseline-3mv5ckqi/reviewguard.py --staged
git diff --cached --check
git diff --cached
git commit -m "fix(checks): preserve validated Flow demo flag"
git push -u origin fix/flow-demo-test-flag
gh pr create --repo bellra-jin/verith --base develop --head fix/flow-demo-test-flag --draft --title "fix(checks): preserve validated Flow demo flag" --body-file /var/folders/d7/v1s6ddq12y9fftsqrvrgcz140000gn/T/cf009-baseline-3mv5ckqi/review-pr-body.md
```

실제 add/commit/push/PR/Ready/merge는 사용자가 직접 수행한다.

<!-- CF009_PR_BODY_START -->
## 변경

보호 preload에서 FLOW_SYNTHETIC_DEMO_ENABLED의 미설정/문자열 true·false만 검증·보존합니다. forkPlan은 정제된 부모 값을 유지하며 child options의 주입·상충·malformed를 고정 오류로 거부합니다. 다른 secret/unknown 환경 제거·필수 preload/IPC/OpenSSL·FS/OS/network/정리 보호는 유지합니다. CF008 제품/API/DB·controller/helper·의존성은 바꾸지 않습니다.

## 검증·한계

- 기존 보호 self-test 최종27/27·exit0, 예상 음성14·예상 밖 guard0·자기 root 제거. 직접 own-key assertion 보완 전 최초 결과와 영향 재검증을 기록했습니다.
- guard의 exact 허용 변경만 역제거하면 원본 bytes가 같고 기존24시험 bytes도 유지됩니다.
- 실제 validator/forkPlan·제한 VM 결과입니다. Next child/worker·HTTP·React/브라우저는 미검증이며 기존 build 입력 차단은 남습니다. 새 runtime/설치·키/외부 호출·DB는 사용하지 않았습니다.
- 상세 source·명령·정리·인계는 docs/work/CF-009-flow-demo-test-flag.md를 따릅니다.
<!-- CF009_PR_BODY_END -->
