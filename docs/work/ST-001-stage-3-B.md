# ST-001 v1.7 · 3-B 안전 검사 입구 구현/차단 기록

- 상태: **v1.7 진단 한정 self-test 20개·unit 35개 통과. 진단 build는 거부 22회/대상 ID 10개로 exit 78·정리 완료. 추가 정책/HTTP/type/lint/최종 독립 수용 미완료**. 과거 결과·실패는 이력으로 보존.
- 최초 수신 정본 v1.4 / source SHA-256 `e07ce413fb6f763c70a3433898465411f475aed30856be28f04a0295e2d6fe39`를 직접 읽고 수신값과 대조했다.
  운영 정본 전체 작업 v1.1/작성 v1.2/개발 v1.2와 root·Backend·Frontend AGENTS를 다시 읽었다.
  관련 .agents/skills는 repo/상위에 없었다. Next 16.2.10 번들 CLI/env 가이드를 읽고 webpack build와 production start 계약을 확인했다.
- 시작: develop, HEAD/로컬 develop/origin develop `7df12403848e480f223767232540d4c2c055ba5e`, clean/staged 0, worktree 1개.
  전체 fetch/push origin은 각각 단일 `https://github.com/bellra-jin/verith.git`, 동명 local/remote branch 없음.
  기본 fetch는 DNS 오류로 실패했고 같은 승인 fetch를 네트워크 허용 경로에서 성공했다. ff-only는 Already up to date.
  그 develop에서 **chore/safe-backend-frontend-checks**를 생성했으며 강제 정리/stash/이전 작업 branch 분기는 하지 않았다.
- PR #5 head `5eecd0b8c62ad56041e0b2a1bf888b9b053fd430`, mergedAt 2026-11-08 00:19:42 KST
  (`2026-11-07T15:19:42Z`), merge `7df1240`은 전달받은 병합 확인이다. 이번 fetch 뒤 기준 일치를 확인했고,
  head→merge 차이와 선행 포함은 Git으로 대조한다. 새 GitHub 상태 조회를 실행한 것으로 표현하지 않는다.

## 정확한 차단과 현재 완료 범위

최신 상태는 말미의 v1.7 진단 한정/20·35 통과/22회·10개 ID 식별 절이다. 아래 v1.4의 실패·대기 표현은 당시 이력이며 현재 결과와 구분한다.

아래는 초기 실행 이력이다. root literal 보완 뒤 standalone 최소 probe 통과와 현재 본 검사 조건 대기는 말미의 최신 절에 구분한다.

2026-11-08 00:30~00:54 KST 실행에서 `/usr/bin/sandbox-exec`를 최소 임시 profile과 자기 합성 canary로
시작했으나 **exit 71 / `sandbox-exec: sandbox_apply: Operation not permitted`**로 적용 단계에서 실패했다.
이는 OS 실행 권한 실패이며 자동 승인 검토가 거부한 메시지는 아니다. 정책 적용 뒤 실제 runtime/pytest/Next가
실행됐거나 OS 격리가 통과했다고 주장하지 않는다. 원본 private 파일/실서버를 probe하지 않았고 자기 합성 폴더는 제거됐다.

정본은 native/자손 통제를 입증하지 못하면 해당 명령을 실행하지 않도록 한다. 따라서 보호를 무음 해제하거나
다른 경로로 같은 거부를 우회/반복하지 않았다. Backend/Frontend guarded self-test·선택 unit·build/HTTP/type/lint는
**미실행/미검증**이다. 새 코드의 OS profile/native/자손·copy/통신/수명 회귀가 아직 입증되지 않았으며,
이 상태를 안전 입구 수용/실제 로그인·인가·DB 성공으로 표현하지 않는다.

다음 재개 조건은 OS sandbox가 허용되는 정확한 실행 대상/권한의 확인과 같은 최소 profile의 자기 합성 검증이다.
그 뒤 self-test → Backend 고정 6개 → Frontend unit/build/HTTP 3개/type/변경분 포함 대상 lint 순서로 실행·수정·재검증한다.
새 설치·OS 보호 해제·home/repo 전체 허용·기존 앱/DB 접근은 대안이 아니다. 범위/설계 변경은 정본 갱신 전 구현하지 않는다.
당시 차단 해소를 위한 설계 변경은 하지 않았으며 OS 환경에 종속되지 않는 코드·구문/입력·보존 검사를 진행했다.

## 초기 구현 파일과 당시 미검증 경계 · v1.4 이력

| 파일/책임 | 구현 내용 / 검증 제한 |
|---|---|
| [Backend controller](../../backend/scripts/check_safe.py) | stdlib/help/list/고정 argv·기존 interpreter/site metadata, Git index/명시 source copy·identity, nonce/root 소유 정리·fresh OS worker/timeout. OS gate 이후 경로는 미검증 |
| [Backend bootstrap](../../backend/scripts/safe_checks_bootstrap.py) | -I -S에서 pytest import 전 env/path·파일/audit·dotenv·DNS/TCP/UDP/process 보호, 부모/수명 watchdog. plugin 자동 로드 차단·pytest_asyncio 명시·고정 선택/0건·skip/xfail/위반 실패 집계. 실제 수집·native/IPC 호환은 미검증 |
| [Backend 합성 회귀](../../backend/tests/safe_checks/test_entry.py) | 수집 시점 private/DNS/TCP/UDP/process probe·빈 자격·dotenv·symlink/hardlink/FIFO/탈출 회귀 코드. OS gate 때문에 실행하지 않음 |
| [Frontend controller](../../frontend/scripts/check-local-ports.mjs) | 명시 Git/source copy·정규/비hardlink·race 검사, clean child env, 검증 dependency 읽기 전용 링크, OS gate·worker 추적/수명/정리. 원본 Turbopack root/dev server 사용 제거. 실제 gate 이후 미검증 |
| [Frontend preload](../../frontend/scripts/safe-checks-guard.cjs) | fs/네트워크/DNS/UDP/process/worker 경로 제한과 허용 자기 port, 자손 preload/watchdog. JS 통제는 OS 격리 아님. native/프로세스/파일 API 전체 우회 차단을 통과로 보고하지 않음 |
| [HTTP helper](../../frontend/tests/helpers/safe-http.mjs) | 첫 취득부터 자기 listener/child 정리, production build만 start·자기 PID/listener/cwd/nonce 준비, bounded timeout/TERM·KILL 뒤 종료 확인. 실제 bind/readiness/정리 경합은 미검증 |
| [Frontend 합성 회귀](../../frontend/tests/safe-checks.test.mjs) | copy/사전 guard/합성 자격 회귀 코드, 미실행 |
| [HTTP disabled](../../frontend/tests/disabled-http.test.mjs), [session](../../frontend/tests/session-http.test.mjs), [ports](../../frontend/tests/ports-http.test.mjs) | 본문 assertion 6/21/13줄 보존. 준비/취득/종료만 helper로 교체, 개별 timeout 120초 이내. production 전환의 실제 결과는 아직 미검증 |
| [Frontend package](../../frontend/package.json) | 기존 scripts/의존성 유지, check:safe alias 한 개 추가. npm 자체 clean launch까지 자동 보장하지 않음 |

그 외 허용 문서 12경로는 root/서비스 README·AGENTS, [개발 안내](../development.md),
[문서 목록](../documentation.md), [manifest](../contracts/manifest.json),
[3-A 병합 주석](ST-001-stage-3-A.md)과 이 보고서다. 정확한 전체 허용 집합은 아래 최종 검사에서 대조한다.
3-A 본문/명령·공용 예제·Next 규칙·포트폴리오·CF bytes/hash/metadata/reference·기존 unit/conftest/lock/
제품 API/DB schema/auth/owner/port는 변경하지 않는다. v1.3 work_item만 기존 이력과 함께 원형 보존하고 현재 v1.4로 갱신했다.

## 고정 선택·제외와 초기 실행표 · v1.4 이력

Backend는 다음 **6개 전체**를 고정 선택한다. 실제 collected/executed는 현재 0이며 수집 전 차단된 것이다.

- tests/unit/test_flow_contract.py
- tests/unit/test_cf002_boundary.py
- tests/unit/test_cf002_google.py
- tests/unit/test_cf002_local_ports.py
- tests/unit/test_cf002_review_regressions.py
- tests/unit/test_cf002_session_failures.py

상위 DB conftest는 자동 수집 대상에서 제외하지만 두 conftest의 합성 수동 import 회귀와 seed import 회귀는
기존 테스트 그대로 유지했다. 이 회귀가 통과한 것은 아직 아니다. 나머지 unit 파일
`test_interactive_runner_security.py`, `test_runner_owned_database.py`, `test_google_login_workspace.py`,
`test_google_login_inputs.py`, `test_google_login_controller.py`는 이번 최소 선택에서 제외한다.
interactive/owned-DB/credential helper 범위이기 때문이며 삭제/skip하지 않았다. root/실DB suite·3-C AI는 이번 선택이 아니다.

Frontend는 기존 disabled-routes/session-proxy/ports unit과 새 안전성 회귀, 사본 webpack build→production HTTP 3개→type→
기존 9개+변경 mjs/cjs/helper 전부 대상 lint를 선택하도록 구현했다. 실제 수집/실행 수는 0이다.
원본 package build는 바꾸지 않고 검사만 --webpack을 사용한다. 기존 전체 ESLint explicit-any 오류 2건/unused 경고 3건은
과거 보고의 실패이며 이번에 재실행하거나 해결한 것이 아니다. 대상 lint의 실제 파일 포함/ignore 여부도 미검증이다.

현재 사용할 수 있는 확인 모드는 --help/list와 거부되는 잘못된 인자다. 저장소 루트에서 실제 확인한 시작은 다음 형태다.
`$(pwd -P)`는 검증한 현재 저장소 절대 경로를 shell에서 채우며 임의 interpreter 입력을 받는 옵션이 아니다.
Backend는 기존 backend/.venv/bin/python(Python 3.12, -I -S), Node는 아래 canonical 절대 경로다.

```sh
/usr/bin/env -i LANG=en_US.UTF-8 TZ=UTC "$(pwd -P)/backend/.venv/bin/python" -I -S backend/scripts/check_safe.py --help
/usr/bin/env -i LANG=en_US.UTF-8 TZ=UTC OPENSSL_CONF=/dev/null /opt/homebrew/Cellar/node/22.7.0/bin/node frontend/scripts/check-local-ports.mjs --help
```

OS 재개 조건 충족 전 self-test/unit/build/local-http/type/lint는 실행하지 않는다. 전체 env 상속·새 dependency 설치를 하지 않으며,
기존 .env/credentials/ignored Compose/Docker Env·실DB/Google/AI/모델·Docker/migration/seed·원본 앱은 열람/실행하지 않는다.

## 직접 실행한 결과와 구현 오류 처리

- 정본 해시/branch/HEAD/전체 원격/worktree/clean·fetch/ff-only/전용 branch 준비를 직접 확인했다.
- 합성 OS canary: sandbox_apply에서 exit 71, 자기 temp 폴더 제거. 정책 검증 **실패**, child app/pytest/Next **미실행**.
- Backend self-test 첫 호출은 macOS가 clean launch에도 자동 추가하는 `__CF_USER_TEXT_ENCODING` 이름 때문에
  env allowlist에서 exit 78로 먼저 거부됐다. 값을 읽거나 출력하지 않고 자동 추가되는 이름임을 별도 clean subprocess로 확인했다.
  공개 시작의 비민감 이름만 허용하고 worker env에는 전달하지 않도록 수정했다. 이 수정이 OS 적용 권한을 바꾸는 것은 아니므로
  OS preflight/보호 self-test를 재시도해 통과로 만들지 않았다. 수정 후 self-test 본문은 여전히 미검증이다.
- clean public launch 8건: 양쪽 --help/list는 각 0, external/추가인자는 각 2. caller에 합성 DSN/Google key·
  PYTHONPATH/PYTEST_PLUGINS/NODE_OPTIONS canary를 주고 env -i를 통해 시작했으며 startup marker 생성 0, worker 시작 0.
  native loader 주입/OS 격리 성공까지 입증한 검사는 아니다. 자기 합성 canary 폴더는 context 종료로 제거됐다.
- Python source 3개의 AST와 Node source 7개의 --check 구문이 통과했다. 앱·테스트 module 실행이나 선택 검사 통과가 아니다.
- 기존 HTTP 본문 assertion 40줄은 원문과 대조해 보존했다. 일반 ready 200 검사 대신 helper의 nonce/소유 검증으로 바꾼 부분은
  실제 runtime에서 아직 검증하지 않았으며 기대값을 낮춰 통과한 결과가 아니다.

최종 정적 집합/링크/hash/markers·간단 명령 사전조건 결과는 아래 마지막 절에 기록한다.
이 최초 기록 시점에는 독립 검토 전이었다. 이후 조기 독립 정적 검토의 수정/추가 회귀를 반영했으며 최종 독립 재검토는 대기 중이다. 코드 존재·문법 통과와 실제 안전 경계·필수 검사 통과를 분리한다.

## 사용자 직접 보존 commit과 Draft PR 초안

**현재 3-B 수용 미완료**다. 다음은 검토/보존을 위한 초안이며 Ready/merge 권장이 아니다.
OS 차단 해소·실제 선택 검사·독립 검토 후 결과/PR 본문을 최종화해야 한다. 실제 git/gh 변경 명령은 실행하지 않았다.

권장 commit: `test: add guarded backend and frontend check entrypoints`

Draft PR 제목: **ST-001 3-B: 안전 검사 입구와 비노출 진단 — 추가 정책 대기**

<!-- ST001_3B_PR_BODY_BEGIN -->
ST-001 v1.7 3-B 안전 검사 입구와 추가 거부의 비노출 진단을 구현합니다. 선택 unit은 통과했지만 build 실패·추가 정책·후속 검사·독립 수용이 남아 있는 검토용 Draft입니다. 3-B 전체 완료/Ready/merge를 의미하지 않습니다.

## 변경

- Backend fresh -I -S bootstrap·고정 6파일·수집 전 보호와 v1.5의 정확한 Flow 입력 2개/origin 검증을 구현합니다. 기존 fixture/conftest/기대값·Backend 최종 통과 코드는 유지합니다.
- Frontend tracked/명시 사본·guard·단일 immutable package metadata snapshot·production HTTP helper를 구현하고 기존 HTTP assertion 40줄을 보존합니다.
- v1.7은 읽기 전 deny 값에만 fixed 공개 label·role/private flag·per-run HMAC-SHA-256 ID·copy membership을 부여합니다. 난수 key는 자기 0700 root의 0600 capability에만 두고 출력/인자/env/journal/보고서에 남기지 않습니다.
- bounded journal/aggregate·실제 fs consumer 계측·controller 변조/정리·budget/partial/error 회귀를 보강합니다. label/caller/ID를 허용 판단에 쓰거나 새 IO를 추가하지 않습니다.
- 현재 안내·v1.7 diagnostic-only metadata만 갱신하고 v1.6 객체 전체를 이력에 보존합니다. CF/Next/3-A 예제·과거 결과·포트폴리오와 제품 API/auth/owner/port/DB/lock·실환경은 유지합니다.

## 직접 검증

- Backend v1.5 self-test 9개·unit 244개 최종 통과 코드는 그대로이며 새 실행으로 재표기하지 않습니다. v1.6 Frontend 17/32·모든 실패/거절/partial 기록도 이력으로 유지합니다.
- 최신 self-test 20개·unit 4파일 35개(10+2+3+20) 모두 통과, fail/skip/cancel/todo 0·exit 0·자기 root 제거입니다.
- 진단 build는 한 번 실행했고 컴파일·내장 TypeScript·정적 생성/trace 단계 뒤 거부 22회로 worker 1/controller 78입니다. 요청 대상은 정규화 ID 10개(cgroup 1개/4회, unknown hash 9개/각 2회)이며 22파일로 해석하지 않습니다.
- hash 대상은 original-project 1개·original-repo 1개·outside 7개, 모두 known-copy=false/공개 label 없음입니다. outside ID 1개만 private-name flag이며 실재/credential 내용은 확인하지 않았습니다. HMAC으로 가린 경로를 역탐색하지 않았습니다.
- worker journal 16개 중 exit 1/partial 15를 그대로 보존합니다. 단일 원본 package literal의 instrumented JS raw dispatch 0·diagnostic failure 0·callback snapshot hit 2는 해당 관측 범위이며 native 전체 0이 아닙니다. 부모 공개 source 검증 4회와 OS 합성 canary는 별도입니다.
- 자기 child/group·root·임시 key/capability·원시 journal 제거를 확인했습니다. 원시 임시 자료는 stage하지 않고 비민감 집계만 보고서에 남깁니다.

## 남은 차단

cgroup 감지 동작과 unknown hash 입력의 정확한 경로/필수성·접근/대체 정책은 미결정입니다. 이번에는 추가 읽기·OS 권한·snapshot 확대·CI/telemetry·cache/resolver 변경·fake ENOENT/거부 무시를 하지 않았고 build 반복도 보류합니다. HTTP/별도 type/대상 lint는 미실행이며 전체 lint 기존 실패를 유지합니다.

허용 23경로/staged 0/범위 밖·제품 runtime 0·링크/해시/본문 보존은 별도 정적 검사로 확인합니다. 실제 DB/Google/외부 AI/모델/Docker/설치/원본 앱/private 내용 사용은 없습니다. 추가 정책 판단과 후속 검증/최종 독립 검토가 필요하며 3-C·구조 분리는 후속입니다. 실제 add/commit/push/Draft PR/Ready/merge는 사용자가 직접 합니다.
<!-- ST001_3B_PR_BODY_END -->

### 간단 명령의 사전조건과 PR 본문 추출

저장소 cwd에서 최종 status/check-ignore의 허용 23경로와 staged 0/다른 변경 0·전체 fetch/push 단일 승인 URL을
다시 확인하고 `git diff`를 직접 검토한다. 같은 파일 안의 새 사용자 편집도 별도로 검토해야 한다.
전제가 달라지면 `git add .`를 보류하며 reset/stash/force-add로 정리하지 않는다. commit 후에는 staged/HEAD/commit 경로를
확인하고 정확한 branch를 push한다. 명령 사이에 새 변경이 생기면 다시 검토한다. 현재 Ready/merge는 보류다.

아래 stdlib 추출은 marker 각 1개·순서·빈 본문을 확인하고 자기 /tmp 신규 파일에만 쓴다. raw marker 문자열을
아래 코드에서 이어 붙여 작성하므로 실제 marker는 본문의 두 경계에만 존재한다. 변수를 설정할 Terminal에서 실행한다.

```sh
st001_3b_body_file=$(python3 - <<'ST001_3B_BODY'
from pathlib import Path
import os, tempfile
text=Path('docs/work/ST-001-stage-3-B.md').read_text()
prefix='<!-- '+'ST001_3B_PR_BODY_'
begin=prefix+'BEGIN -->'; end=prefix+'END -->'
if text.count(begin)!=1 or text.count(end)!=1 or text.index(begin)>=text.index(end):
    raise SystemExit('STOP: invalid PR body boundaries')
body=text.split(begin,1)[1].split(end,1)[0].strip()
if not body:
    raise SystemExit('STOP: empty PR body')
fd,name=tempfile.mkstemp(prefix='st001-3b-pr-',suffix='.md',dir='/tmp')
try:
    with os.fdopen(fd,'w') as out:
        out.write(body+'\n')
except BaseException:
    os.unlink(name)
    raise
print(name)
ST001_3B_BODY
) || { unset st001_3b_body_file; printf '%s\n' 'STOP: PR body extraction failed'; false; }
```

추출 실패는 nonzero이며 변수를 지운다. 실패하면 아래 PR 명령으로 진행하지 않는다. 별도 명령 실행 전에 본문 파일이 정상 생성됐는지 확인한다.

### 사용자 명령 · 각 한 줄

```sh
git add .
git commit -m 'test: add guarded backend and frontend check entrypoints'
git push --set-upstream origin chore/safe-backend-frontend-checks
gh pr create --repo bellra-jin/verith --draft --base develop --head chore/safe-backend-frontend-checks --title 'ST-001 3-B: 안전 검사 입구와 비노출 진단 — 추가 정책 대기' --body-file "$st001_3b_body_file"
```

PR 생성 후에는 이번 추출에서 만든 자기 파일만 `rm -f -- "$st001_3b_body_file"`로 제거한다.
실제 추출 파일 생성/cleanup과 git/gh 액션은 개발 검증에서 실행하지 않으며 추출 본문은 메모리에서 대조한다.

## 초기 정적 검사·당시 남은 검증 · v1.4 이력

2026-11-08T01:15:53+09:00 기준. 다음 임시 stdlib 도구를 최종 bytes에서 실행하며 결과는 직접 검사와 독립 보고를 구분한다.

```text
/usr/bin/env -i LANG=en_US.UTF-8 TZ=UTC <검증한 repo 절대 경로>/backend/.venv/bin/python -I -S /tmp/st001_3b_check.py
git diff --check
```

- 실제 변경 23경로=허용 23경로, staged 0, 범위 밖/제품 runtime/API/DB/auth/owner/port/기존 unit/conftest/lock 변경 0.
- status --porcelain=v1 -z --untracked-files=all과 check-ignore --no-index --stdin을 대조했다. 23개 모두 비무시(exit 1/출력 없음), 다른 변경 0이다. 현재 이 조건에서만 위 git add .가 검토한 경로를 포함한다. 실제 stage는 하지 않았다.
- Python AST 3개·Node --check 7개 통과. public clean-launch 12건(help/list·external·추가 인자·help+extra·unit+--)의 예상 exit와 합성 startup marker 미생성을 확인했다. OS gate/실제 suite 실행을 재시도한 검사가 아니다.
- 현재 문서 path/anchor 218개 통과. 보존한 3-A 본문/옛 명령·README 포트폴리오·Next 326 bytes·CF 2개 bytes/hash/metadata/reference·3-A 예제/이력 불변, v1.3 work_item 1회 원형 보존을 확인했다.
- HTTP 본문 assertion 6+21+13=40줄 보존. PR marker 각 1개/순서/비어 있지 않은 본문·메모리 추출, 내장 Python 및 shell 구문·정확한 repo/base/head/--draft를 확인했다. 실제 PR 임시 파일 생성/정리·git/gh 액션은 미실행이다.
- clean env 안의 Git은 DARWIN_USER_TEMP_DIR confstr 경고 후 /tmp를 사용했지만 관련 읽기 명령은 정상 완료했다. parent 환경/private 파일을 가져와 경고를 숨기지 않았다.

위 숫자는 최종 수정 뒤 같은 임시 검사기를 다시 실행해 확인한다. 실제 보호 self-test·선택 6개·Frontend unit/build/HTTP/type/lint와 최종 독립 수용은 미완료다.

## 조기 독립 정적 검토 반영 · 실행 검증은 별도

아래는 개발 중 source-only 검토에서 전달된 지적이다. 검토자가 OS gate/앱/테스트를 대신 실행한 결과가 아니다.
마지막 수정 코드의 정적 재대조·구문 확인과 합성 회귀 **구현**을 남기며, 실행 회귀 통과/최종 독립 수용으로 표현하지 않는다.

| 지적 | 수정·회귀 코드 | 현재 한계 |
|---|---|---|
| close의 조기 closed=true로 stop 실패 시 listener 정리 누락·timeout rejection 누락 | independentCleanup이 자원별 완료를 기록하고 실패 자원만 재시도·동시 호출을 공유. expiryCleanup은 timeout/정리 실패를 집계해 test close/exit로 전파. 합성 stop 실패·중복 정리·timeout 회귀 추가 | 실제 child/listener·timeout 회귀는 OS 차단으로 미실행 |
| Next fork 전부 거부로 webpack worker 불가 | 설치 Next ChildProcessWorker.initialize·next/lib/worker·formatNodeOptions·webpack-build source를 읽고 정확한 next/dist/compiled/jest-worker/processChild.js, 빈 argv, 고정 cwd/Node·pipe/IPC·한정 execArgv만 허용. env는 부모 spread 대신 새 allowlist/정확한 preload/한정 worker marker로 재구성. 임의 모듈/execArgv/IPC/env 변경 거부 회귀 추가 | 실제 webpack/native/IPC 호환 미검증. 지원하지 않는 옵션은 실패 유지 |
| 직계 child exit 후 별도 detached Next 그룹 잔존 가능 | helper Next는 test-worker와 같은 그룹을 유지. controller는 leader exit 뒤에도 그룹 생존을 재확인하고 root cwd 소유를 확인한 그룹만 TERM→KILL·소멸 확인. 실패 receipt/자기 root는 보존하고 다른 그룹도 독립 정리. 합성 leader 조기 exit·그룹 잔존/KILL·signal 정리 실패 회귀 추가 | 실제 PID/group/cwd·정리 경쟁과 신호 전달 미검증 |
| tracked secrets/keys/private/dumps/backups/logs 경로를 열 수 있음 | Backend/Frontend 모두 경로 component 단계에서 private 계열 이름/확장자를 제외·거부. source 선택에서도 배제. 합성 tracked 금지 경로/없는 root를 이용해 open 이전 거부 회귀 추가 | 실제 copy 회귀 실행 미검증 |
| 필수 회귀 코드 누락과 실행 차단 혼동 | 해당 스냅샷의 safety suite는 Backend 8개 test method / Frontend 13개 test 정의였으며, 최신 보완 후에는 9개/14개다. nonce/PID/cwd·가짜 200·조기 exit/ready timeout·bind/spawn 실패·일반 command nonzero/timeout·TERM→KILL·root 교체/형제 보존·0건/skip 실패·signal 정리 회귀 코드 추가 | 정의 수는 수집/실행/통과 수가 아님. OS 차단으로 실제 수집 0. native/자손 보호·전체 신호 시나리오는 여전히 입증되지 않음 |
| deny-default profile에서 helper의 signal 미허용 | 설치 macOS의 com.apple.securityd.sb·darwin-container-base.sb에서 target children 문법을 정적으로 확인하고 Frontend profile에 `(allow signal (target children))`만 추가. helper는 소유 직접 자식만, 외부 controller는 소유 그룹만 종료 | 전역 signal/target others 허용 없음. 실제 policy 적용 후 TERM/KILL 가능 여부는 미검증 |

## OS 실패의 정확한 실행 맥락과 재개 판단 근거

실패 probe는 `exec_command`의 **sandbox_permissions 생략(use_default)**으로 요청했다. 이 동작에 대해
require_escalated/새 승인 요청을 하지 않았다. 도구는 실행을 허용했고 바깥 Python은 결과를 출력한 뒤 exit 0이었다.
그 안에서 호출한 sandbox-exec가 exit 71과 sandbox_apply 오류를 반환했다. **tool 정책 거부가 아니라 허용된 실행
내부의 OS sandbox 적용 실패**다. Git fetch의 별도 네트워크 허용 요청/성공과 이 OS probe를 혼동하지 않는다.

정확한 argv 형태는 다음과 같다. CANARY_ROOT는 /tmp에 새로 만든 자기 임시 폴더이며 실제 난수 경로/원시 영수증은
공유 기록에 넣지 않는다. Python은 현재 repo의 기존 .venv 절대 경로로 시작했고 임의 interpreter를 사용하지 않았다.

```text
/usr/bin/env -i LANG=en_US.UTF-8 TZ=UTC <현재 repo 절대 경로>/backend/.venv/bin/python -I -S -
# 그 stdlib Python 안에서 shell 없이 subprocess.run(argv, env={LANG,TZ}, capture_output=True, timeout=10):
/usr/bin/sandbox-exec -f <CANARY_ROOT>/probe.sb /usr/bin/true
# 결과: 71; stderr: sandbox-exec: sandbox_apply: Operation not permitted
```

실제 최소 profile bytes는 다음 내용이었다. 자기 constant true/native read canary용이며 서비스 worker profile이 아니다.

```scheme
(version 1)
(deny default)
(allow process-exec)
(allow process-fork)
(allow file-read-metadata)
(allow file-read-data (subpath "/System") (subpath "/usr/lib") (literal "/bin/cat") (literal "/usr/bin/true") (literal "/dev/null"))
(allow sysctl-read)
(allow mach-lookup)
```

첫 명령이 exit 0일 때만 뒤의 `/bin/cat <자기 합성 private canary>` 부정을 실행하도록 작성했으므로 cat 단계는
실행하지 않았다. 오류를 OS 보호 성공이나 true 성공으로 표시하지 않는다. 자기 임시 폴더/합성 파일은
TemporaryDirectory context 종료로 제거됐다. native read/통신·자손 보호가 입증된 것은 아니다.

현재 세션이 workspace-write 관리 sandbox이고 probe가 use_default 안에서 실행됐다는 것은 주어진 실행 문맥으로
확인된다. **추가 sandbox 중첩 제한이 직접 원인인지, 다른 entitlement/OS 정책 때문인지는 이 오류만으로 확정할 수 없다.**
중첩 여부의 kernel/entitlement 진단이나 OS 설정 변경·다른 경로 재시도는 하지 않았다. 재개하려면 관리 실행 대상의
정확한 sandbox-exec 허용 조건/권한을 먼저 확인해야 하며, 이번 보고는 그 권한 변경/우회를 요청하거나 실행한 것이 아니다.


## 정식 승인 경로의 추가 최소 probe · 과거 실패와 구분

2026-11-08T01:15:53+09:00 확인. 기본 요청이 use_default였고 정식 실행 승인 요청이 아직 없었다는 새 근거와
최소 자기 합성 probe 한정 지시를 받아 **같은 최소 profile/true probe에만 require_escalated를 요청**했다.
새 OS 설정/지속 권한·앱/pytest/Next 실행 승인이 아니며 지시 증거를 도구 인자에 넣지 않았다.

공식 도구는 요청을 실행해 바깥 Python exit 0으로 결과를 반환했다. 내부 sandbox-exec returncode는 **-6(SIGABRT)**,
stderr는 빈 문자열이었다. 이것은 승인 거절 결과가 아니다. 정책 적용/true의 정상 완료가 확인되지 않았으므로
후속 native canary 읽기 단계는 조건문에 의해 미실행이었다. 자기 TemporaryDirectory가 실제 제거됐음(`exists=False`)을 확인했다.
이 결과만으로 profile 문제/권한·중첩 sandbox·OS syscall 중 어느 것이 원인인지 단정하지 않는다. 새 재시도/우회는 하지 않았다.

기존 use_default exit 71 기록은 지우지 않는다. require_escalated로 최소 probe가 정상화된 것이 아니므로 본 검사 실행으로
확대하지 않았으며, 이 시점에는 실제 self-test/선택 검사에 필요한 실행 조건/추가 승인 범위도 아직 확정할 수 없었다.
다음은 이 정확한 실패와 실행 문맥의 검토이며 앱·pytest·Next 실행 권한을 새로 요청하거나 자동 실행한 상태가 아니다.
필수 검사 수용 미완료·최종 독립 재검토 대기·사용자 commit/push/Draft PR/Ready/merge 경계는 유지한다.

## 최종 코드 식별값 · 내용 해시

자체 정적 검사 대상이며 이 해시 자체는 실행 안전성/통과 증거가 아니다. 보고서 자신의 순환 hash는 넣지 않는다.

| 경로 | SHA-256 |
|---|---|
| `backend/scripts/check_safe.py` | `aba16ebd5a851e1e9e2724a4d7507633b23c97ca86fd2e264ff406c95138b84a` |
| `backend/scripts/safe_checks_bootstrap.py` | `71dcabfe58c6c61c05acb7e8b7004517bf8619ba3e1e3d625330201628f29238` |
| `backend/tests/safe_checks/test_entry.py` | `b48e92512ade6a7342ad8bd88ccc34b4ea65702314935ac89e9cc2f46bcbbb27` |
| `frontend/scripts/check-local-ports.mjs` | `bc19f2b5363f75ed080b759b4be56f1f111ab93eb6cf5f6c88d45ee91e0ea060` |
| `frontend/scripts/safe-checks-guard.cjs` | `b1912f4a3645c85786b4ff35f6d6b2f96ea7945b8b4e13102bfa1e9bdcab5f2c` |
| `frontend/tests/helpers/safe-http.mjs` | `90e75becd5eb2f2482c1a6614a215082c1b9b4e846f2e3f867e72982b0fca8d7` |
| `frontend/tests/safe-checks.test.mjs` | `042965137d36ed330ad4b9bf83651bae92e4c70c44f4ef5e3ed18090d22db8c0` |
| `frontend/tests/disabled-http.test.mjs` | `9dfed19ded75dfdb06d6ec4bde2cc663256db784243d43ed18f87cdbe0b87e20` |
| `frontend/tests/session-http.test.mjs` | `8a77d355f49c3bec441984888920e66a4499134449be5da09106d85b00551888` |
| `frontend/tests/ports-http.test.mjs` | `1edb3887903cf1bc81c1ede4f9b2347df4b1c5798f691d4cc1cd72457ff62857` |
| `frontend/package.json` | `5dcc4949fad70a41d4c4fe5639f63931fcaf99accd3019a53052c00a4e697ef5` |

## 정확한 변경 경로 · 23개

최종 status/check-ignore와 대조한 집합이며 현재 staged는 0이다.

```text
backend/scripts/check_safe.py
backend/scripts/safe_checks_bootstrap.py
backend/tests/safe_checks/test_entry.py
frontend/scripts/check-local-ports.mjs
frontend/scripts/safe-checks-guard.cjs
frontend/tests/helpers/safe-http.mjs
frontend/tests/safe-checks.test.mjs
frontend/tests/disabled-http.test.mjs
frontend/tests/session-http.test.mjs
frontend/tests/ports-http.test.mjs
frontend/package.json
README.md
frontend/README.md
backend/README.md
AGENTS.md
frontend/AGENTS.md
backend/AGENTS.md
ai/AGENTS.md
docs/development.md
docs/documentation.md
docs/contracts/manifest.json
docs/work/ST-001-stage-3-A.md
docs/work/ST-001-stage-3-B.md
```


## dyld 근거 보완과 최소 양성/음성 probe 통과 · 최신 상태

설치 `/System/Library/Sandbox/Profiles/dyld-support.sb`는 libignition이 openat 기준 디렉터리로 /를
열기 위해 `(allow file-read* file-test-existence (literal "/"))`가 필요하다고 설명한다. 이 source를 직접 읽고
두 controller의 profile에 그 literal 한 줄을 추가했다. directory 자체의 예외이며 subpath /·home/repo
전체 read/write/network·system.sb 전체 import를 추가하지 않았다. 과거 SIGABRT의 단일 원인 확정은 아니다.

예전 canary가 cat의 임의 nonzero를 보호 성공으로 세던 결함도 수정했다. 두 controller는 stdout/stderr/exit/signal을
분리해 true 정상 0/빈 출력 → 허용 자기 cat 정상 0/정확한 내용 → 금지 자기 cat 정상 exit 1/빈 stdout/정확한
Permission denied 또는 Operation not permitted stderr 순서로 확인한다. 이전 단계 실패/timeout이면 다음 단계로
진행하지 않는다. signal·loader/init 실패·다른 exit·예상 밖 출력은 보호 성공이 아니다. 합성 결과/조기 중단 회귀를
추가했으며 safety 회귀는 현재 Backend 9개 method·Frontend 14개 test 정의다. 수집/통과 수가 아니다.

CJS preload의 no-require-imports 충돌은 설치 eslint-config-next/typescript recommended와 해당 rule의 allow schema를
직접 대조했다. 동기 preload에 필요한 이 파일의 정확한 node: builtin 목록만 inline allow regex로 국소 처리했다.
다른 require는 계속 error이며 파일을 lint 목록에서 빼거나 전역 eslint config를 바꾸지 않았다. 실제 ESLint는 미실행이다.

새 필수 root 규칙이라는 materially new evidence와 최소 probe 한정 지시에 따라 같은 공식 require_escalated 경로를
**이번 근거로 1회** 요청·실행했다. 아래 기존 최소 profile에 root literal과 자기 허용 canary literal만 추가했다.

```scheme
(allow file-read* file-test-existence (literal "/"))
(allow file-read-data (literal "<새 canonical 자기 temp>/allowed-canary"))
```

새 /tmp 폴더를 canonical path로 만들고 mode 0700, allowed/denied 합성 파일을 mode 0600으로 작성했다.
검증한 기존 .venv Python -I -S를 env -i로 시작했고, 각 단계는 shell 없는
`subprocess.run(['/usr/bin/sandbox-exec','-f',policy,*argv], cwd=owned_root, env={LANG,TZ}, capture_output=True, timeout=10)`이었다.

| 실제 단계 | 직접 결과 |
|---|---|
| /usr/bin/true | exit 0, signal 없음, stdout/stderr 0 bytes |
| /bin/cat 자기 allowed-canary | exit 0, signal 없음, 정확한 SYNTHETIC-ALLOWED + newline(18 bytes), stderr 0 |
| /bin/cat 자기 denied-canary | exit 1, signal 없음, stdout 0, 정확한 권한 거부 stderr(83 bytes) |
| 정리 | context 종료 뒤 자기 폴더 exists=False를 직접 확인 |

세 단계가 모두 통과했으며 승인 거절/불확실 결과·추가 재시도는 없었다. 과거 use_default exit 71과 정식 경로 -6
기록은 보존한다. 이번 결과는 **standalone 최소 native filesystem profile**이 적용되고 양성·음성 대조가 통과한 근거다.
수정한 controller의 전체 profile·Python/Node/dependency/native/자손·TCP/UDP/DNS/IPC·signal/cleanup·회귀 suite나
unit/build/HTTP/type/lint를 실행한 것은 아니다. 기존 원본 private·앱·실서버·DB/Google/AI·설치·OS 설정은 건드리지 않았다.

### 본 self-test와 선택 검사의 다음 실행 조건/권한

기존 3-B 개발·선택 검사 의도는 이미 승인돼 있지만 이번 공식 도구 승인은 최소 probe에 한정됐다.
이를 전체 workload의 require_escalated 실행 허가로 확대하지 않았다. 다음 두 정확한 단위의 source/profile과
자원·자손·signal/네트워크 거부 조건을 검토하고, 해당 공식 실행 권한 경계를 먼저 확인해야 한다.

- Backend: clean env·검증된 기존 절대 .venv Python -I -S의 `backend/scripts/check_safe.py self-test`.
  명시 source 사본·검증 dependency 읽기와 OS profile·Python bootstrap·합성 guard/copy/cleanup 회귀를 포함한다.
- Frontend: clean env·검증된 절대 Node의 `frontend/scripts/check-local-ports.mjs self-test`.
  명시 source 사본·dependency 링크·OS profile·CJS preload/자손·합성 회귀를 포함한다. build/HTTP/원본 dev server는 아직 실행하지 않는다.

위 단위는 true/cat만 실행한 최소 probe보다 범위가 크다. 이번 턴에서는 해당 승인을 새로 요청/실행하지 않았다.
self-test의 실제 결과/회귀 수정·독립 검토 뒤 Backend 고정 6개, Frontend unit/build/HTTP/type/대상 lint를 각각
한도/승인된 자기 자원 안에서 단계적으로 이어간다. 최소 probe 성공만으로 본 검사의 권한이 충분하다거나 안전 통과라고
확정하지 않는다. 3-B 수용·Ready/merge·3-C/구조 변경은 계속 대기다.


### 최신 자체 정적 재검증

2026-11-08T01:31:24+09:00. dyld/양성·음성/CJS 보완 뒤 같은 임시 검사기를 최종 bytes로 재실행했다.
허용/실제 23경로·staged 0·범위 밖/제품 runtime 0, check-ignore --no-index의 23개 비무시,
Python AST 3개/Node --check 7개·clean CLI 12건·현재 링크/anchor 218개·Next 326 bytes/CF/3-A 예제/
본문·이력 보존·PR marker 각 1개/본문 추출·diff check가 통과했다.
추가로 root literal의 존재/루트 subpath 광역 허용 부재, CJS inline allow 옵션과 실제 require의 정확한 builtin 목록,
lint 대상 포함, Backend 9개/Frontend 14개 회귀 **정의**를 정적으로 대조했다. 실제 ESLint·이 회귀 실행은 하지 않았다.
standalone 최소 native probe 3단계/정리 통과와 위 정적 검사, 아직 미실행인 본 self-test/unit/build/HTTP/type/lint를 구분한다.
최종 독립 재검토·본 실행 조건/권한 확인 대기이며 실제 git/gh/Ready/merge는 수행하지 않았다.


## 별도 공식 self-test 실행 결과 · v1.4 당시 이력

2026-11-08T01:42:06+09:00 확인. 독립 사전 정적 검토에서 최소 probe/CJS 보완과 self-test 전용 분기를 확인했다는
결과를 전달받은 뒤 source/profile·현재 hash를 직접 다시 읽고 Backend → Frontend 순서로 각 workload의
공식 require_escalated를 별도로 요청했다. tool 승인 거절은 없었으며 아래 실제 결과를 기록한다.
선택 unit/build/HTTP/type/lint로는 확대하지 않았다.

| 실제 실행 | 수집/실행/통과/실패·exit | 자원/의미 |
|---|---|---|
| Backend self-test | unittest 9개 발견·9개 실행·9개 통과·실패/error 0, controller exit 0 | 실제 OS/Python bootstrap 아래 합성 suite만 실행. 자기 root 제거 확인 |
| Frontend 최초 self-test | suite 수집/실행 0, 내부 Node exit 1·controller exit 78 | OS profile이 native OpenSSL 기본 config 접근을 거부. 자기 root 제거 확인 뒤 좁게 수정 |
| Frontend 호환 수정 후 self-test | Node TAP tests 14 / pass 14 / fail·skip·cancel·todo 0, controller exit 0 | 자기 root 제거 확인 |
| Frontend 자손 pin 거부 회귀 보완 후 최종 재실행 | 같은 14개 전부 통과·실패/skip/cancel/todo 0, controller exit 0 | 최종 코드 hash 기준. 자기 root 제거 확인 |

Backend의 실제 명령은 다음과 같았다. repo cwd의 기존 절대 .venv Python -I -S이며 임의 pytest/app을 실행하지 않았다.

```text
/usr/bin/env -i LANG=en_US.UTF-8 TZ=UTC <검증한 repo 절대 경로>/backend/.venv/bin/python -I -S backend/scripts/check_safe.py self-test
```

Frontend 최초 명령은 앞서 전달된 env -i/LANG/TZ/절대 Node의 self-test였다. controller는 시작됐지만 protected child가
Node native startup 중 `/opt/homebrew/etc/openssl@3/openssl.cnf`의 fopen에서 Operation not permitted를 받았다.
이는 도구 승인 거절이나 test assertion 실패가 아니라 **허용된 실행 내부의 native runtime 설정 접근 거부**였다.
해당 파일 내용/권한을 조사하거나 출력하지 않았고 그 디렉터리/파일을 profile read 예외에 추가하지 않았다.
최초 controller의 native 기본 설정 탐색 여부는 직접 추적하지 않았으므로 이전 실행 전체를 원본 config open 0으로
소급 주장하지 않는다. assistant가 원본 config/비밀값을 열람·출력한 근거는 없다.

좁은 수정은 **Node 시작 전** OPENSSL_CONF=/dev/null을 공개 clean launch에 넣는 것이다. 값은 사용자의
원본 설정에서 읽지 않고 생성하는 고정 runtime 입력이다. controller/자손/HTTP helper/fork/CJS env가 유지하고,
자손 spawn에서 누락/다른 경로를 거부한다. 기존 config/OS/전역 보안 설정이나 TLS 검증을 끄지 않는다.
이를 누락한 direct Node/npm 시작은 native startup을 소급 보호할 수 없다. Node CLI metadata를 이 고정값으로
확인하고 구문 검사를 거친 뒤, 수정된 정확한 self-test를 공식 require_escalated로 요청해 재검증했다.

```text
/usr/bin/env -i LANG=en_US.UTF-8 TZ=UTC OPENSSL_CONF=/dev/null /opt/homebrew/Cellar/node/22.7.0/bin/node frontend/scripts/check-local-ports.mjs self-test
```

현재 코드 식별값 표의 Backend/Frontend hash는 최종 통과 코드와 일치한다. Frontend의 마지막 변경은
spawn 자손의 OPENSSL_CONF 누락/다른 경로 거부를 추가한 것이며 같은 suite를 다시 실행해 14개 통과했다.
기존 Backend 코드에는 그 이후 변경이 없으므로 9개 통과 코드가 그대로다. 과거 실패/미검증은 당시 이력으로 남긴다.

### 실제로 입증한 범위와 아직 입증하지 않은 범위

- 실제 입증: 각 controller의 OS filesystem 양성/음성 canary, 검증 runtime/dependency로 시작한 guard worker,
  Python 수집 전 audit/dotenv·JS preload와 합성 copy/identity·결과/정리 로직, 정상 worker/group 종료 및 root 제거.
- self-test의 fork/IPC 옵션·TERM→KILL·signal/timeout·가짜 listener/nonce·root 교체 등은 합성/spy/mocked 로직
  회귀다. 실제 Next worker fork/IPC handshake·살아 있는 자손 강제 종료·실제 HTTP/bind 경합을 통과했다고 확대하지 않는다.
- Backend 고정 6개 pytest·Frontend 기존 unit 3개·webpack build/production HTTP 3개·type/대상 lint는 **미실행**이다.
  실제 DB/Google/AI/모델/Docker·원본 앱·설치·migration/seed는 실행하지 않았다. 전체 lint 기존 실패도 보존한다.

### 다음 workload 준비와 추가 공식 실행 경계

다음 첫 단위는 Backend `check_safe.py unit`과 Frontend의 OPENSSL_CONF=/dev/null clean launch `check-local-ports.mjs unit`이다.
두 명령은 별도 공식 실행 요청으로 범위를 명시해야 하며 이번 self-test 승인을 자동 재사용하지 않았다.
Backend는 guard 이후 고정 6개 전체 pytest·pytest_asyncio·메모리 ASGI/Mock DB·두 conftest 수동 import 회귀를
실제로 실행한다. Frontend unit은 원본 서버/build 없이 자기 사본에서 기존 unit 3개와 safety suite만 실행한다.
각각 실제 수집/실행·누락/0건/skip/오류·native 접근·정리를 확인하고 실패 시 좁게 수정·재검증해야 한다.

그 뒤 unit 결과와 최종 source/profile을 검토한 후 build(webpack/worker fork/native/IPC), local-http(자기 동적 loopback와
canonical 3200/8200·소유 nonce), type/lint(변경 CJS/MJS 포함)의 정확한 한도/자원/권한을 각각 확인한다.
모든 workload를 한 번에 요청하거나 실제 DB/Google/AI/외부 network·기존 프로세스/자격을 허용하지 않는다.
현재에는 해당 후속 실행 승인을 요청/실행하지 않았다. 3-B 전체 수용/최종 독립 재검토·사용자 commit/push/Draft PR/Ready/merge는 대기다.


### self-test 후 최종 정적 확인

2026-11-08T01:46:33+09:00. OpenSSL pin을 포함한 최신 코드/안내에서 임시 checker를 재실행했다.
23개 허용/실제 경로·staged 0·범위 밖/제품 runtime 0·23개 비무시, Python AST 3개/Node 구문 7개·
clean CLI 12건(현재 Node 시작은 OPENSSL_CONF=/dev/null 포함)·현재 링크/anchor 218개·본문/CF/Next 보존·
PR marker/추출/구문과 diff check가 통과했다. 정적 checker가 별도 보호 suite를 실행한 것은 아니며,
위 별도 공식 self-test의 9개/14개 실제 통과와 구분한다. 선택 unit/build/HTTP/type/lint는 아직 실행하지 않았다.


## 선택 unit 공식 실행 결과 · v1.4 당시 체크포인트

두 workload를 각각 별도의 공식 require_escalated 요청으로 실행했다. 도구 승인 거절은 없었다.
Backend 실패와 Frontend 독립 재검증 결과를 전체 마감 전 commentary로 먼저 공유했다.
build/local-http/type/lint로는 확대하지 않았다. 아래 수치는 이전 self-test나 CF 과거 수치를 재사용하지 않는다.

| 실행 | 실제 수집/실행·결과 | exit/guard·정리 |
|---|---|---|
| Backend unit 최초 | pytest 설정 단계에서 collected 0/run 0 | worker 1/controller 78, guard 2. 자기 root 제거 |
| Backend 생성 log_file 수정 후 | 고정 6파일 선택. Flow 모듈 수집 오류 1, collected 96/run 0/pass 0. 실제 수집 경로 집합은 출력되지 않아 파일별 항목 분포는 미기록. skip 통과로 대체 안 함 | worker 1/controller 78, read outside capability 1. session 종료/자기 root 제거 확인 |
| Frontend unit 최초 | disabled-routes 10/10 후 session-proxy 2개 중 1 pass/1 fail. 총 run 12/pass 11/fail 1. 뒤 2파일 미실행 | controller 78, ENOENT 입력 누락. 자기 root 제거 |
| Frontend 정확한 BFF source 분류 수정 후 | 4파일/29개(10+2+3+14) 모두 실행·통과. fail/skip/cancel/todo 0 | 각 child 및 controller 0, 미처리 guard 실패 없음. 자기 root 제거 |

Backend의 첫 오류는 pytest logging plugin이 기본 `log_file=os.devnull`을 write로 여는 경로였다.
설치 `_pytest/logging.py`의 기본값을 정적으로 확인하고 생성 pytest config의 log_file을 자기 root/pytest.log로
지정했다. /dev/null/외부 write 허용이나 pytest logging 비활성화로 기대값을 약화하지 않았다. log는 root와 함께 제거됐다.
그 뒤 발생한 Flow import 오류와 남은 read guard 위반은 해결하지 않았으며 기록을 지우거나 ledger를 비워 통과시키지 않았다.
terminal dumb 설정 경고도 숨기려고 system/home 읽기를 넓히지 않았다.

Frontend 원인은 추적된 기존 BFF source가 API namespace 이름 `private` 때문에 일반 private-directory 필터에 잘못
분류된 것이었다. `git ls-files --stage`의 100644/stage 0과 실제 해당 source를 정적으로 확인했다.
승인된 tracked src 범위 안의 **src/app/api/private/[...path]/route.ts 단 한 파일**만 정확히 분류하고
이웃 private/keys/other 경로는 계속 차단했다. index·symlink·regular/nlink·race·범위 검사도 유지한다.
원본 API route/기존 unit/HTTP assertions는 바꾸지 않았다. 이 예외와 이웃 경로 차단 회귀를 safety suite에 보강한
최종 source로 공식 unit을 재실행해 29개 통과했다. private 폴더 재귀 복사나 일반 비밀 경로 허용이 아니다.

### Backend 입력 범위 차단 · 정본 답변이 필요한 정확한 두 파일

기존 `backend/tests/fixtures/flow_payload.py`는 _AI_SRC를 사본 ai/src에 잠시 추가하고
`agents.flow.export.to_json.build_payload`, `agents.flow.schemas.GateResult`를 import한다.
현 v1.4의 Backend 사본 허용에는 이 두 파일이 없고 AI config 3개를 data-only로 복사하는 경계만 있다.
따라서 추가 복사/import가 필요한 다음 입력은 정본 답변 전 **미적용/보류**다.

| 추가 입력 후보(원본은 수정하지 않음) | 정적 확인 / SHA-256 |
|---|---|
| ai/src/agents/flow/export/to_json.py | json/UUID·상대 schemas import의 순수 exporter. `9523f4af93b14f77b41f440e83a1352932914d8d0e6f833c7ac174c9dab812a7` |
| ai/src/agents/flow/schemas.py | datetime/typing/uuid·기존 Pydantic schema. `5d3e2c5a243a0faed6f638f2af802a138d338e5bc324ebab3b2573810162fd12` |

관련 __init__.py는 Git에 없고 namespace package 배치다. 위 source는 정적으로만 읽었으며 실제 AI 모듈을
원본에서 import하지 않았다. AI source를 수정하거나 source 사본에 추가하지도 않았다.
권장안은 이 두 **정확한 기존 tracked pure 파일**만 같은 상대 배치·동일 copy/OS/언어 guard 아래 Backend fixture
입력으로 명시하는 정본 답변이다. dotenv/config/그래프·자료 수집/LLM·AI 전체 root 허용으로 확대하지 않는다.
대안은 현 Backend 고정 6파일 검증을 보류하는 것이다. fixture를 가짜 payload로 바꾸기·test skip·원본 AI root
직접 import·AI 전체 복사는 사용하지 않는다. 답변이 input 계약을 갱신하면 새 버전/hash를 읽은 뒤 그 부분만 적용한다.
남은 read guard 위반 1건도 실제 원인을 좁게 확인·수정해야 하며 입력 누락만 고쳐 전체 통과라고 보고하지 않는다.

### 다음 단계의 준비·실행 경계

현재 Backend unit은 위 정본 답변 전 재실행하지 않는다. Frontend unit은 통과했지만 실제 webpack fork/IPC·
production HTTP/bind/nonce·live TERM/KILL·type/lint는 아직 미검증이다. 다음 build 요청은 최신 source/profile과
이번 exact BFF source 분류·OpenSSL pin·자원 한도를 확인한 뒤 별도 공식 실행으로 범위를 명시해야 한다.
이번 unit 승인을 모든 후속 workload/실제 서버 접근으로 자동 확대하지 않았다. 현재 build/HTTP/type/lint 요청/실행은 없다.

Backend self-test 9개는 이전 통과 코드의 결과다. 이후 bootstrap의 unit 전용 generated config/log 출력 부분이 바뀌었고
self-test 분기/guard 설치는 바꾸지 않았지만 이 변경 뒤 self-test를 다시 실행한 것은 아니다. Frontend unit의 마지막
14개 safety 실행은 정확한 source 분류 보완을 포함한 현재 source에서 통과한 결과다.
전체 unit/실DB/실제 로그인/인가/AI 완료나 3-B 수용·Ready/merge로 확대하지 않는다. 실제 git/gh 액션도 없다.


## v1.5 수신·현재 재검증 결과

- 수신 확인: 2026-11-08T02:14:33+09:00. 정본 v1.5/source SHA-256 `96eb6fc2521ca9e1f48439b146f351a3474d371ed7b4ab5e87fc67b01a081c51` 직접 일치.
- 같은 chore/safe-backend-frontend-checks / HEAD `7df12403848e480f223767232540d4c2c055ba5e`에서 재개했다. checkout/fetch/branch 변경·강제 정리 없음.
- 기존 v1.4 work_item 객체 전체를 v1.0/v1.1/v1.3 이력 뒤에 원형 보존하고 current만 v1.5/hash/같은 기준·3-B로 갱신했다. 이전 실행을 v1.5 결과로 일괄 치환하지 않았다.

### 정확한 입력과 origin 검증

정본 6/6-A 전체를 읽고 exact 입력 2개의 실제 bytes가 위 후보 표의 hash와 같음을 확인했다.
`FLOW_INPUTS`가 두 경로/hash만 고정하며 기존 Git/index·regular/identity·symlink·hardlink·race 검증을 적용한다.
원본 AI 파일은 수정하지 않았고 namespace __init__ 추가는 0개다. 인접 config/graph/다른 exporter와 __init__ 허용은 없다.
수집 완료/세션 완료 시 namespace 3개의 search location과 module 2개의 origin이 자기 checkout/ai/src의 정확한 경로인지 확인한다.
누락/동명 dependency package/다른 namespace location은 결과 실패다. 합성 origin/인접 경로 음성 회귀도 추가했다.

### Backend 공식 실행과 남은 read 위반 해소

각 아래 명령을 workload마다 공식 require_escalated로 별도 요청했다. 승인 거절/불확실 잔여 실행은 없었다.

```text
/usr/bin/env -i LANG=en_US.UTF-8 TZ=UTC /Users/parkjinhee/AI/verith_refactor/verith/backend/.venv/bin/python -I -S backend/scripts/check_safe.py self-test
/usr/bin/env -i LANG=en_US.UTF-8 TZ=UTC /Users/parkjinhee/AI/verith_refactor/verith/backend/.venv/bin/python -I -S backend/scripts/check_safe.py unit
```

| v1.5 순서 | 실제 결과 | 전체 exit / 정리 |
|---|---|---|
| 입력/origin/비민감 진단 보완 self-test | 9 run/9 pass | 0 / 자기 root 제거 |
| 입력 보완 뒤 고정 6파일 unit | 244 collected/244 pass, read guard 1건. pytest 통과만으로 전체 성공 처리하지 않음 | worker 1/controller 78 / 자기 root 제거 |
| 정확한 OS metadata literal 보완 self-test | 9 run/9 pass, 인접 경로 거부 회귀 포함 | 0 / 자기 root 제거 |
| 최종 고정 6파일 unit | 244 collected/244 pass. 누락/collection error/skip/xfail/guard 위반 0 | worker/controller 0 / 자기 group 부재 확인 후 root 제거 |

진단은 거부된 파일을 열거나 값을 출력하지 않고 event/capability 영역/검토된 호출 위치만 기록한다.
실제 stack은 Python `_osx_support.py:99→126→185→463`, `sysconfig.py:705→731→757`이었다.
설치 표준 라이브러리 source를 정적으로 읽어 대상이 `/System/Library/CoreServices/SystemVersion.plist`임을 확인했다.
원본 private가 아닌 macOS 버전 metadata이며 조사 도구는 그 plist 내용을 읽지 않았다.
OS profile은 이미 /System 읽기를 허용하고 있었으므로 변경하지 않았다. Python guard의 read에 그 literal 하나만
추가했다. 외부 write·인접 plist·원본 source/private·네트워크/process 허용을 넓히지 않았다.
pytest의 terminal dumb 경고는 남아 있으며 system/home 읽기를 추가해 숨기지 않았다.
고정 6파일 집합/Flow origin/결과 정책은 그대로 검사했고 기존 fixture/expectation/conftest를 변경하지 않았다.

### Frontend 공식 build 실패와 현재 보류

```text
/usr/bin/env -i LANG=en_US.UTF-8 TZ=UTC OPENSSL_CONF=/dev/null /opt/homebrew/Cellar/node/22.7.0/bin/node frontend/scripts/check-local-ports.mjs build
```

통과 unit source/profile·설치 Next worker/fork argv/IPC/env를 재검토한 뒤 이 build workload만 별도 공식 요청했다.
첫 실행은 webpack readFile→CacheBackend.provide에서 file outside capability였다.
파일 권한을 바꾸지 않고 임의 path/파일 내용 대신 안전한 scope/고정 공개 manifest 분류만 출력하도록 보강했다.
두 번째는 original-project 영역 package.json, 세 번째는 **정확한 original-project-root:package.json**으로 확인됐다.
세 실행 모두 Next 16.2.10 webpack 시작 뒤 worker 1/controller 78이며 각 자기 group/root 제거를 확인했다.
원본 `frontend/package.json` 요청은 JS guard에서 실제 read 전에 거부됐고 OS/JS 허용을 추가하지 않았다.
dependency canonical 경로에서 원본 공개 manifest로 이어지는 요청이라는 범위까지만 확인하며 webpack 전체 완료는 아니다.

작성 측이 검증/복사된 package snapshot으로 단일 metadata 요청을 해결할 수 있는지 source-only 검토 중이다.
정확한 새 정본/hash 전달 전 원본 manifest 읽기·metadata redirect·추가 build 반복은 적용/실행하지 않는다.
전체 home/repo/source 허용·dependency 재귀 copy/설치도 하지 않는다.

최신 진단 회귀를 포함한 Frontend self-test만 별도 공식 실행했다.

```text
/usr/bin/env -i LANG=en_US.UTF-8 TZ=UTC OPENSSL_CONF=/dev/null /opt/homebrew/Cellar/node/22.7.0/bin/node frontend/scripts/check-local-ports.mjs self-test
```

14 run/14 pass·fail/skip/cancel/todo 0·exit 0·자기 root 제거다. Frontend unit 29개는 진단 보완 전 당시 실제 결과다.
production HTTP·type·대상 lint는 요청/실행하지 않았고, 실제 Next fork/IPC 전체 build/HTTP·live signal 경쟁은 미검증이다.
3-B 전체 완료/독립 수용/Ready가 아니며 현재 실행·승인 대기인 child/검사 자원은 없다.


### v1.5 체크포인트 정적 마감

2026-11-08T02:15:23+09:00. 현재 bytes에서 임시 stdlib checker를 직접 실행해 다음을 확인했다.

- 변경/허용 23경로 일치, staged 0·범위 밖/제품 runtime 0, check-ignore --no-index 23개 모두 비무시(exit 1/출력 없음).
- source v1.5/hash·v1.4 work_item 원형 1회 추가·기존 이력/CF bytes/hash/metadata/reference·3-A 예제/역사본문·README portfolio·Next 326 bytes 보존.
- 코드 식별값 11개 현재 bytes 일치, Python AST 3개·Node 구문 7개·clean CLI 12건·현재 링크/anchor 218개·diff check 통과.
- HTTP 기존 assertion 40줄 보존, PR marker 각 1개·메모리 추출 3204 bytes·내장 Python/shell 구문·repo/base/head/--draft와 실제 전체 fetch/push 단일 URL 대조 통과.
- 정적 checker는 보호 suite/build를 실행하지 않았다. 위 공식 self-test/unit/build 결과와 별도다. PR 본문 파일 생성/cleanup·git/gh 변경 액션은 미실행이다.

현재 공식 실행 결과는 Backend self-test 9개·unit 244개 통과, Frontend 최신 self-test 14개 통과·당시 unit 29개 통과,
Frontend build 3회 차단·HTTP/type/lint 미실행이다. 실행 중 child/승인 대기 workload는 없다.
Frontend snapshot metadata 해법의 정본 결정/확정 hash 수신 전 추가 build와 원본 manifest 접근은 보류한다.
3-B 최종 독립 재검토/수용·사용자 commit/push/Draft PR/Ready/merge는 여전히 대기다.


## v1.6 단일 package snapshot 구현 · 최초 승인 거절 당시 기록

정본 전체와 6-B를 읽고 SHA-256 `3a2dd3d648fc04fc7aafd15fea09ce1a5e82955fcf262b4e8fbc69fc1466d4ce` 일치를 확인했다.
같은 branch/HEAD/23경로에서 재개했으며 v1.5 work_item 객체 전체를 이력 뒤에 1회 보존했다.
현재 source/hash만 v1.6으로 갱신했고 위 v1.4/v1.5 실행·실패·대기 이력은 그대로다.
설치 webpack bundle SHA `4293b6eb020382002a67bccdc2ccdaf6760fe041dd42de314e20fea7ca5a7ab7`,
공개 package SHA `5dcc4949fad70a41d4c4fe5639f63931fcaf99accd3019a53052c00a4e697ef5`도 직접 대조했다.

### 구현·보호 경계

- 기존 source copy에서 검증한 공개 package bytes/ancestor·file identity를 snapshot record에 결합한다. 최초 capture는 copy가 이미 읽은 Buffer를 그대로 사용한다.
- controller는 6-B.7의 기존 공개 source 절차로 command 전/후 source identity/hash와 사본을 재대조한다. 이 부모 단계의 source FD는 닫힌 뒤 child가 시작된다. worker에는 source raw-read를 주지 않는다.
- worker/fork마다 정확한 root/dependency/source 관계·literal 요청·owned snapshot identity/FD/707 bytes/hash를 검증하고 in-memory Buffer로 고정한다.
- callback/sync/Promise readFile 내용 응답만 지원한다. literal 이외 형태/인접·상위 path, stream/open/write/임의 FD를 이 mapping으로 지원하지 않는다. resolver context/config/alias/OS profile은 변경하지 않았다.
- 옵션은 Buffer/지원 encoding·read flag r·비동기 AbortSignal 범위만 처리한다. 반환 Buffer와 ledger는 복사하며 callback은 비동기로 호출한다. 허용 hit의 API별 횟수/fingerprint와 실패 ledger를 분리한다.
- 추가 합성 회귀 2개(전체 Frontend safety 16개)를 구현했다. 세 API/Buffer·encoding·abort·async timing·raw-open spy 0·부정 경로/옵션·snapshot 교체/손상/누락/capability·raw open/stream/write 거부를 다룬다. **아직 실행되지 않았다.**

### 공식 self-test 요청의 자동 승인 거절

```text
/usr/bin/env -i LANG=en_US.UTF-8 TZ=UTC OPENSSL_CONF=/dev/null /opt/homebrew/Cellar/node/22.7.0/bin/node frontend/scripts/check-local-ports.mjs self-test
```

exec_command의 sandbox_permissions=require_escalated로 위 workload를 요청했지만 자동 승인 검토가 CreateProcess 전에 거절했다.
사유는 당시 capturePackage가 controller에서도 원본 frontend/package.json을 읽는 것이 원본 raw-read 금지와 충돌한다는 판단이었다.
이는 test failure/OS syscall 실패가 아니라 **tool 승인 거절·실행되지 않음**이다. 테스트/worker/소유 root는 시작되지 않았다.
같은 명령의 우회 실행·반복 승인 요청·일반 환경에서 suite 실행은 하지 않았다.

정본 6-B.1/7은 부모의 승인된 source-copy 및 command 전후 source identity/hash 재검증을 허용하고,
6-B.4/6은 worker/native 원본 raw-read를 금지한다. 이 역할 구분을 승인 검토에 적용할 수 있는지 확인이 필요하다.
독립 보완으로 최초 snapshot capture의 추가 source read를 제거해 copy의 Buffer/identity 기록을 재사용하도록 바꿨다.
명령 전후 부모 재검증은 6-B.7 요구대로 남아 있다. 이를 제거하거나 원본 worker 읽기를 허용해 성공시키지 않는다.
이 보완 뒤 self-test는 아직 재요청/실행하지 않았으며 새 관련 근거 없이 거절된 workload를 반복하지 않는다.

Backend 통과 source 3개의 해시는 v1.5 최종 통과 뒤 동일하다. Backend self-test 9개·unit 244개 결과는 당시 실행 이력이며 v1.6에서 새로 실행했다고 하지 않는다.
Frontend self-test 16개/unit 31개는 구현상 선택 예정 수이고 실제 통과 수치가 아니다. build/후속 HTTP/type/lint도 새 실행은 없다.


### v1.6 최초 차단 중 직접 정적 확인 · 당시 이력

2026-11-08T02:31:57+09:00. 현재 bytes에서 임시 checker를 직접 재실행했다.
허용/실제 23경로·staged 0·범위 밖/제품 runtime 0·23개 비무시, Python AST 3개·Node 구문 7개,
clean CLI 12건·링크/anchor 218개·Next 326 bytes·CF/예제/본문 보존·v1.5 work_item 원형 추가와 v1.6 정본 hash가 통과했다.
코드 식별값 11개 현재 bytes·PR marker 각 1개/메모리 본문 3929 bytes·내장 Python/shell 구문·전체 URL/repo/base/head/--draft·diff check도 통과했다.
이 checker는 help/list/잘못된 인자만 호출하며 거절된 self-test나 suite/build/HTTP를 실행하지 않았다.
최종 실행 자원/승인 대기 child는 없고, 실제 git/gh 변경 액션도 없다. 신규 snapshot의 실행 검증과 3-B 수용은 여전히 미완료다.


## v1.6 초기 승인/실행 상태 · 당시 실행 보류 이력

시간순으로 서로 다른 세 공식 요청을 구분한다. 거절된 요청의 실행 결과가 불확실한 상태는 없다.

| 순서 | 공식 경로/실제 결과 | 실행·정리 |
|---|---|---|
| 최초 snapshot self-test | require_escalated / CreateProcess 거절 | 실행되지 않음, worker/root 생성 없음 |
| 최초 capture 재사용·옵션 capture 보완 후 self-test | 같은 공식 경로 승인. 16 run/15 pass/1 fail, skip/cancel/todo 0. worker 1/controller 78 | 자기 root 제거. 정확한 해당 root 부재도 읽기 전용 재확인 |
| capability 오류 정규화 후 재검증 요청 | 부모의 보류 메시지 수신 전에 제출했고 승인 판단 중 그 최신 지시가 적용되어 CreateProcess 거절 | 실행되지 않음. 이후 새 실행 요청/우회 0 |

최초 거절의 사유 원문:

> 실행 자체는 승인된 self-test이지만 현재 구현의 `capturePackage`가 self-test에서도 원본 `frontend/package.json`을 직접 읽으므로, 사용자가 명시한 원본 raw-read 금지와 충돌합니다.

후속 거절의 사유 원문:

> 최신 사용자 지시는 거절 사유가 직접 해결됐는지 확인되기 전 self-test 재요청·반복 실행을 보류하라고 명시했으므로, 이번 재실행은 현재 권한 범위를 벗어납니다.

두 건 모두 exec_command 도구가 `CreateProcess ... Rejected`를 반환했으며 syscall/test 실패가 아니다.
그 사이 승인 실행은 도구 완료 exit 78/TAP 16·15·1과 root 제거 출력을 실제 반환했다.
이는 해당 공식 요청만 승인됐다는 사실이며 이후 보류를 무시하거나 새 workload 권한으로 확대하지 않는다.

### 거절 이후 실제 코드 보완과 남은 source read

- 최초 `capturePackage`의 추가 source read를 제거했다. `copyProject`가 이미 읽어 검증한 package Buffer/identity를 `packageRecord`에 넘긴다.
- controller `copyProject`는 기존 허용 source들의 최초 copy와 copy 뒤 hash 재대조를 계속 수행한다. package도 그 정확한 집합 중 하나다.
- controller `recheckPackage`에는 명령 전/후 **record.sourceRoot/package.json 하나**를 `readSource`로 읽는 동작이 남는다. 이는 v1.6 6-B.7의 부모 검증을 구현한 것이며 공개 source index/regular/nlink/ancestor/FD/해시 검증·FD finally close를 사용한다.
- command의 try/finally가 전/후 검사와 source/snapshot 동일성을 묶는다. 원본 bytes를 worker/fork로 다시 읽게 하거나 source FD를 상속하지 않는다.
- worker `readPackageSnapshot`은 원본에 lstat/realpath metadata만 사용하고, open/read는 owned root/package.json 하나에만 수행한다. OS profile의 원본 manifest read-data 허용 추가는 0이다.
- API 옵션을 호출 시점에 capture해 반환 전 caller의 옵션 변경이 비동기 응답을 바꾸지 않게 보완했다. 세 read API와 immutability 등의 첫 신규 회귀는 실제 실행에서 통과했다.

이 중 부모의 공개 source 재검증과 worker/raw-read 금지의 구분을 독립 검토하고 새 실행 재개 지시 전에는 self-test/unit/build를 더 요청하지 않는다.
독립 검토가 아직 끝나지 않았으며 기술적 동등성/안전성 전체 수용으로 표현하지 않는다.

### 실제 실패와 이후 미검증 수정

16개 중 실패한 신규 회귀는 잘못된 sourceRoot capability가 realpath 단계에서 ENOENT를 반환한 사례였다.
데이터 접근 허용 실패가 아니라 안전한 거부 메시지 기대와 달리 내부 경로를 포함한 metadata 오류가 전파된 문제다.
`loadPackageSnapshot`에서 capability/metadata/identity/hash 오류를 값 없는 `SAFE_CHECK_DENIED: snapshot capability/fingerprint`로
정규화했다. 기대값을 약화하지 않았고 원본 read 허용을 추가하지 않았다. **이 최신 수정의 실행 재검증은 거절돼 미실행**이다.
실패 실행의 installed snapshot ledger는 readFile/readFileSync/promisesReadFile hit 각 0, rawOriginalReadCalls 0·미처리 guard deny 0이었다. 이 rawOriginalReadCalls 값은 당시 상수였으므로 실측 증거에서 제외하며 아래 P2 보완의 실제 consumer 계측과 구분한다.
첫 pure responder 회귀의 raw-open spy 0은 통과했지만 두 번째 회귀가 중간에 실패해 installed API 양성/음성 대조 전체가 끝난 것은 아니다.
따라서 모든 snapshot/negative/native/worker 회귀 통과로 확장하지 않는다. unit 31개는 예상 선택 수이며 실제 수집·통과 결과가 아니다.

Backend의 v1.5 최종 코드 해시는 그대로이며 self-test 9·unit 244 결과를 새 실행으로 바꾸지 않았다.
현재 실행 중 worker/임시 검사 root/불확실 요청은 없다. 신규 build/HTTP/type/lint·git/gh 변경 액션도 없다.


### 최신 보류 뒤 source-only 직접 검사

2026-11-08T02:35:07+09:00. `--source-only` 임시 checker로 현재 bytes의 Python AST 3개·Node 구문 7개,
허용 23경로/staged 0/범위 밖·제품 runtime 0/비무시 23개, source hash/manifest 이력/CF·3-A·역사본문·Next 326 bytes,
현재 링크/anchor 218개·코드 hash 11개·PR marker 각 1개/메모리 4211 bytes·내장 구문/원격/PR 대상·diff check를 확인했다.
이 실행에서는 CLI help/list/오류 인자도 재실행하지 않았고, suite/build/HTTP/앱 worker도 실행하지 않았다.
실제 git/gh 변경 액션 0이며 다음 실행은 독립 검토와 재개 지시를 기다린다.


## v1.6 독립 지적 보완 · 최신 17/32 통과와 추가 소비 차단

확인 기록 시각: 2026-11-08T02:54:30+09:00. 도구 응답에 개별 요청의 절대시각이 제공되지 않은 항목은 실행 순서만 기록하며 시각을 추정하지 않는다.
새 인계는 이전 보류가 도구 결과 반영 전에 전달됐음을 확인하고 실패 수정/좁은 공식 재검증을 허용했다.
이 사실을 이전 거절의 소급 승인으로 바꾸지 않고, 그 이후 요청을 각각 require_escalated로 실행했다. 새 거절/불확실 요청은 없다.

### 독립 P2 보완과 수용 근거

1. **상수 ledger 제거:** packageResponder.ledger의 rawOriginalReadCalls:0 필드를 제거했다. 과거 0값은 실측 근거가 아니다.
   실제 설치 fs wrapper가 raw consumer를 호출하는 지점에서 dispatch 총수/원본 대상 dispatch/거부 횟수와 API를 집계한다.
   installed callback/sync/Promise·ESM 응답을 raw-open spy 안에서 실행하고 raw dispatch 증가 0·hit 증가를 대조한다.
   자기 사본의 정상 raw read는 실제 카운터를 증가시키고, 원본 open/stream·alias 거부는 별도 counter에 남는다.
   observed 원본 dispatch가 발생하면 exit가 실패하며 native 전체는 not-observed로 표시한다.
2. **controller 실제 연결 회귀:** packageRecord/recheckPackage/checkedCommand를 합성 source와 snapshot으로 직접 연결했다.
   source/snapshot 사전·사후 변조, source ancestor/root 교체, command nonzero·postcheck 중복 실패, precheck 실패 시 미실행,
   실제 command 함수의 fake child receipt retire/집합 제거·소유 root 거부·합성 형제 보존을 확인했다.
   runtime source는 기존 project 상수이고 CLI/env의 임의 root 옵션을 추가하지 않았다. 테스트의 sourceRoot 인자는 owned 합성 fixture다.
   precheck는 기록 identity를 먼저 대조해 바뀐 source/snapshot을 reread 전에 거부한다. 부모 source FD는 사용 후 닫는다.

첫 보완 self-test는 17개 중 16개 통과·1개 실패였다. 신규 spy가 합성 변조 write open을 read로 세던 문제였고,
read-only flags만 집계하도록 고쳐 기대한 pre/post source read 수와 실제 cleanup을 검증했다. 기존 unit/HTTP 기대값은 바꾸지 않았다.
오류 정규화와 설치 mapping 회귀는 그 실행부터 통과했고 최종 17개에서도 통과했다.

### 관측 보존과 한계

guard는 owned root의 O_EXCL/O_NOFOLLOW 0600 journal에 validated bootstrap·metadata hit·deny·expected negative·exit를 기록한다.
2MB 상한이며 source bytes·임의 원본 path/자격을 출력하지 않는다. rawOriginalDispatches는 실제 raw 소비 지점의 동적 계측이다.
거부 이력 deniedTotal과 expectedNegatives는 각각 누적하고 원본 raw 거부 수를 지우지 않는다. 예기치 않은 거부/계측 불일치는 실패다.
controller는 자기 그룹 부재 뒤 bounded journal만 읽어 worker별 최종/부분 기록을 집계하고, 관측 검사 실패에도 자기 root 정리를 시도한다.
원시 journal은 자기 root와 함께 제거했고 비민감 집계만 보고한다. guard를 우회하는 native 전체 실행을 관측한 것은 아니다.

### 공식 명령과 직접 결과

공통 명령은 아래 clean launch의 마지막 mode를 self-test/unit/build로 지정한 정확한 형태다. 각각 별도 공식 요청이었다.

```text
/usr/bin/env -i LANG=en_US.UTF-8 TZ=UTC OPENSSL_CONF=/dev/null /opt/homebrew/Cellar/node/22.7.0/bin/node frontend/scripts/check-local-ports.mjs self-test
/usr/bin/env -i LANG=en_US.UTF-8 TZ=UTC OPENSSL_CONF=/dev/null /opt/homebrew/Cellar/node/22.7.0/bin/node frontend/scripts/check-local-ports.mjs unit
/usr/bin/env -i LANG=en_US.UTF-8 TZ=UTC OPENSSL_CONF=/dev/null /opt/homebrew/Cellar/node/22.7.0/bin/node frontend/scripts/check-local-ports.mjs build
```

| 실행 버전/단위 | 실제 결과 | 관측·정리 |
|---|---|---|
| P2 보강 최초 self-test | 17 run/16 pass/1 fail, controller 78 | spy의 write/read 분류 오류. 자기 root 제거 |
| spy 보완 self-test 및 unit | self-test 17/17, unit 4파일 32/32, fail/skip/cancel/todo 0·exit 0 | 자기 root 제거. 당시 instrumentation 포함 |
| v1.6 build 1 | Next compile/type/static 11개/trace 진행 뒤 guard 거부로 worker 1/controller 78 | parent process 거부 1건. 당시 전체 자손 관측 미보존. 자기 root 제거 |
| bounded journal 보강 self-test 및 unit | self-test 17/17, unit 32/32, exit 0 | journal/실패 전파/정리 포함. 자기 root 제거 |
| v1.6 build 2 | worker 1/controller 78. 단계 출력은 끝나도 전체 성공 아님 | 16 worker journal(exit 1/partial 15), 원본 raw dispatch 관측 0·추가 거부 22·snapshot callback hit 2, 자기 group/root 정리 |
| 안전한 caller 진단 보강 최종 self-test/unit | self-test 17/17, unit 10+2+3+17=32/32, fail/skip/cancel/todo 0·exit 0 | worker journal 4개 모두 exit 기록, 원본 raw dispatch 0·expected deny 13/13·snapshot hit 4. 자기 root 제거 |
| v1.6 build 3 | worker 1/controller 78, 컴파일·내장 type·static/trace 단계 진행 | 16 worker(exit 1/partial 15), 관측 원본 raw dispatch 0·추가 거부 22·callback hit 2, 자기 group/root 정리 |

최종 self-test는 worker 1개/exit 기록 1개/partial 0이며 observed raw original dispatch 0·raw original denied 4,
expected deny 13/13·snapshot API hit callback 1/sync 2/Promise 1이다. 부모 공개 source 검증 읽기는 4회다.
최종 unit은 worker 4개/exit 기록 4개/partial 0이며 같은 합성 negative 13/13·snapshot hit 4와 원본 raw dispatch 0을 확인했다.
부모 공개 source 검증은 10회다. 이 부모 읽기를 worker raw-read 0에 섞지 않는다. native OS canary true/허용/거부 대조도 각 entry에서 별도로 통과했다.

### 새 소비와 정확한 차단

v1.6 build 3의 누적 거부 22건은 다음 source 호출로 분리됐다. guard에서 데이터 read 전에 거부했고 파일 내용은 읽지 않았다.

- 4건: 설치 `next/dist/compiled/is-docker/index.js:1:191`의 hasDockerCGroup → `/proc/self/cgroup` readFileSync.
  `next/dist/telemetry/storage.js:82,252`가 NEXT_TELEMETRY_DISABLED 상태에서도 constructor에서 storage 위치를 계산한다.
  main build와 webpack worker 초기화가 각각 이 탐색을 시도했다. OS 환경을 Docker로 바꾸거나 fake 파일/응답을 주지 않았다.
- 18건: 설치 webpack bundle5.js:29:296487의 FileSystemInfo._readFileHash → CachedInputFileSystem/graceful-fs readFile,
  bundle5.js:29:1378173의 AsyncQueue 처리. 원본 프로젝트 분류 2·외부 분류 14·private 분류 2건이다.
  이 18건의 정확한 대상은 아직 redacted/미확인이다. private 분류만으로 실제 credential 파일이라고 단정하지 않으며 source 원본/부재/optional 동작도 확인 전 가정하지 않는다.

공개 source 대조로 첫 4건의 target과 나머지 호출 지점까지 확인했지만 새로운 read 허용·임의 ENOENT·resolver/alias/symlink/캐시
동작 변경은 하지 않았다. v1.6은 package metadata literal 하나만 허용하므로 추가 소비의 정본 판단 전 build를 더 반복하지 않는다.
후속 production HTTP/type/대상 lint는 미실행이다. build 안의 TypeScript 완료를 별도 type mode 통과로 바꾸지 않는다.
실DB/Google/AI/모델/Docker/설치/원본 앱/기존 자료를 사용·변경하지 않았고 Backend 통과 3파일 해시는 동일하다.
최종 독립 검토가 정적 해소를 전달한 시점과 이번 실제 실행/현재 hash는 별개로 기록한다. 3-B 수용은 미완료다.


### 최종 직접 정적 확인과 재검토 식별값

2026-11-08T02:55:10+09:00. 현재 bytes에서 source-only 임시 checker를 직접 실행했다.
23개 허용/실제 집합·staged 0·범위 밖/제품 runtime 0·비무시 23개, AST 3개/Node 구문 7개,
현재 링크/anchor 218개·코드 hash 11개·manifest v1.6/source digest와 이전 work_item 원형·CF/3-A/역사본문·Next 326 bytes,
PR marker 각 1개/메모리 본문 3388 bytes·내장 Python/shell 구문·전체 fetch/push 단일 URL/repo/base/head/--draft·diff check가 통과했다.
이 정적 실행에서 CLI/suite/build를 다시 호출하지 않았으며 실제 보호 검사는 위 별도 공식 실행 결과다.

전달된 17:46:19 UTC 독립 정적 검토와 현재 식별값을 구분한다. controller `eb73239eb2d012485d63978538fab81b80cde19f6ff81869cd8d60da7626d1b4`와
safety `4bf1187aff2ba448e1e07d36f438adc9f5824d51c79056e02ff26032846ec669`는 전달된 prefix와 맞는다.
guard는 그 뒤 safeCallers와 표준 공개 metadata 분류 진단을 보강해 현재 `85067a84d367901fa67bf5acc2ce98ff4ae6b6082802cfe638d1e07175afb084`다.
이 후속 guard bytes로 self-test 17개·unit 32개가 통과했고 build 추가 소비를 확인했다. 후속 hash의 독립 수용을 미리 주장하지 않는다.
현재 branch/HEAD는 그대로이고 실행 중 자원/불확실 승인 요청은 없다. 실제 git/gh 변경 액션도 없다.
추가 소비 판단 전 build 재실행·HTTP/type/대상 lint를 보류하며 3-B 전체 완료가 아니다.


## v1.7 진단 한정 · 20/35 통과와 22회·10개 ID 식별

수신/확인 기록 시각: 2026-11-08T03:15:12+09:00. 정본 source SHA-256 `23e79f20066664ba8e32fb3c1a040e5bb33fdbfc08e44518c354ccee0e8b2601` 일치.
앞서 전체를 읽은 v1.6 보존본과 v1.7 전체 변경·6-C를 대조했다. 같은 branch/기준 HEAD/허용 23경로로 이어갔다.
기존 v1.6 current 객체 전체를 history에 1회 원형 보존하고 current만 v1.7/hash/diagnostic-only follow-up으로 갱신했다.
이전 9/244·17/32·모든 실패/거절/partial·원시 source 버전은 새 v1.7 결과로 바꾸지 않았다.

### 진단 계약 구현과 직접 회귀

- 기존 file guard가 이미 만든 lexical/canonical 후보만 입력으로 받는다. HMAC 분류 자체는 fs/network/unknown metadata API를 호출하지 않는다.
- 공개 allowset은 exact cgroup/검토 Frontend metadata/검증 copy source다. 비공개 이름을 가진 source는 label하지 않으며 공용 BFF `src/app/api/private/[...path]/route.ts`만 exact 공개 예외다. basename/확장자/prefix를 공개 허용 근거로 쓰지 않는다.
- 나머지는 fixed role/private-name flag·knownCopy·API/access/caller family·HMAC ID/count만 기록한다. raw target/별칭/basename/Error/키는 출력하지 않는다.
- 부모가 매 실행 새 crypto.randomBytes(32) key와 별도 run ID를 만들고 0600 capability에 전달한다. 같은 실행 worker는 동일 key를 쓰고 새 실행은 key가 달라진다. nonce/공개 run ID를 key로 재사용하지 않으며 argv/env/로그에는 넣지 않는다.
- 진단의 label/caller/ID는 policy와 분리돼 있다. normalized ID는 HMAC이며 plain SHA(path)가 아니다. key 유출/host 관리자에 대한 익명화 보장으로 표현하지 않는다.
- bounded event 수 256/worker·필드 길이·count와 journal 2MB/aggregate 512 제한을 추가하고, 진단 실패/예산/기존 deny는 실패로 유지한다. worker exit/partial은 추정 보정하지 않는다.

합성 회귀 3개를 추가해 safety 20개가 됐다. exact/인접·동명 label, BFF/private 구분, 같은 key의 worker ID 일치/새 key 분리,
raw private 문자열/키/Error 비노출, 진단 fs IO spy 0, installed deny/raw dispatch 불변, 0600 capability·journal 비노출,
budget/normalization 실패, aggregate count/distinct worker·partial 보존과 진단 오류 전파를 실제 확인했다.

### 공식 요청과 실제 결과

각 아래 workload를 별도 require_escalated로 요청·실행했다. 새 거절/불확실 실행은 없었다.

```text
/usr/bin/env -i LANG=en_US.UTF-8 TZ=UTC OPENSSL_CONF=/dev/null /opt/homebrew/Cellar/node/22.7.0/bin/node frontend/scripts/check-local-ports.mjs self-test
/usr/bin/env -i LANG=en_US.UTF-8 TZ=UTC OPENSSL_CONF=/dev/null /opt/homebrew/Cellar/node/22.7.0/bin/node frontend/scripts/check-local-ports.mjs unit
/usr/bin/env -i LANG=en_US.UTF-8 TZ=UTC OPENSSL_CONF=/dev/null /opt/homebrew/Cellar/node/22.7.0/bin/node frontend/scripts/check-local-ports.mjs build
```

| 단위 | 실제 수집/실행 | exit·정리 |
|---|---|---|
| v1.7 self-test | 20 run/20 pass, fail/skip/cancel/todo 0 | 0·자기 root 제거 |
| v1.7 unit | 4파일 10+2+3+20=35 run/35 pass, fail/skip/cancel/todo 0 | 0·자기 root 제거 |
| v1.7 진단 build 1회 | Next compile/내장 type/static/trace 진행. 거부 22회·expected negative 0·diagnostic failure 0 | worker 1/controller 78·자기 group/root/key 임시 자료 제거 |

새 build를 성공 처리하지 않았고 HTTP를 시작하지 않았다. parent 공개 source 검증은 self-test 4회/unit 10회/build 4회이며
worker의 단일 원본 package literal raw dispatch 계측과 별도다. 이 raw dispatch 필드는 그 literal/추적된 FD의 instrumented JS 소비 지점이며,
모든 원본 파일/native 전체를 관측한 값이 아니다. unknown 거부는 데이터 consumer 호출 전 유지됐다. OS 합성 native canary도 별도다.

### 새 식별 결과 · 실행 내 ID만 상관 가능

진단 build run ID는 `f1cbbb07bf8a8f54dedc2a98`다. 아래 ID는 읽기 편하게 앞 16자로 표시하며 이번 실행 내에서만 상관 식별한다.
key는 기록/출력하지 않았고 root와 함께 제거했다. 새 실행에서 같은 ID를 기대하거나 raw 경로를 역탐색하지 않는다.

| 대상 ID prefix | 고정 공개 label / 역할 | API·caller | 거부 횟수 / 관측 worker | knownCopy / private-name |
|---|---|---|---|---|
| 7a1bb73190d27ad3 | telemetry-container-probe:cgroup / outside | readFileSync / telemetry-container-detection | 4회 / 4개(entry 1+next 3) | false / false |
| e35958a6320ee543 | label 없음 / original-project | readFile / webpack-file-hash | 2회 / 2개 | false / false |
| a3989781e78f0387 | label 없음 / original-repo | readFile / webpack-file-hash | 2회 / 2개 | false / false |
| f8f796243e5f9065 | label 없음 / outside | readFile / webpack-file-hash | 2회 / 2개 | false / false |
| 112901f19f0884f1 | label 없음 / outside | readFile / webpack-file-hash | 2회 / 2개 | false / false |
| 595cda11f2659ccc | label 없음 / outside | readFile / webpack-file-hash | 2회 / 2개 | false / false |
| b50adabd984d5343 | label 없음 / outside | readFile / webpack-file-hash | 2회 / 2개 | false / false |
| d2b3878cad86095b | label 없음 / outside | readFile / webpack-file-hash | 2회 / 2개 | false / false |
| 0b0727fd88f8dae5 | label 없음 / outside | readFile / webpack-file-hash | 2회 / 2개 | false / false |
| d078aca67e8030cf | label 없음 / outside | readFile / webpack-file-hash | 2회 / 2개 | false / true |

이전 v1.6 scope/private 분류와 진단 규칙이 달라졌으므로 과거 총계를 재계산해 섞지 않는다.

22회 요청이 ID 10개로 묶인 것이며 22파일/10개 실재 파일이라는 뜻이 아니다. hash 18회는 ID 9개이고 모두 현재 검증 copy set 밖이다.
현재 허용 copy source로 확인된 입력이나 공개 BFF source는 이번 hash 거부에 없었다. 정확한 raw 경로·존재/부재·필수/optional 여부는 미확인이다.
private-name=true는 문자열 규칙이며 credential 존재/내용을 확인했다는 뜻이 아니다. unknown ID의 파일을 열거나 private 자료에서 역매핑하지 않았다.

16 worker journal 중 exit 기록 1/partial 15를 그대로 유지했다. JS journal 관측의 단일 package literal raw dispatch 0,
callback snapshot hit 2·diagnostic failure 0과 native 미관측·부모 공개 source 읽기를 분리한다. raw journal/키/임시 사본은 보관·stage하지 않았다.

### 남은 정책과 재개 조건

cgroup probe의 동작 수용/환경 분기와 unknown hash 입력의 정확한 producer/역할·필요성·접근/대체 정책은 미결정이다.
label/ID가 붙어도 read 허용이 생기지 않는다. 이번에는 새 파일/OS·snapshot 대상 확대·CI/telemetry 환경·cache/resolver 동작 변경,
fake ENOENT·거부 무시·dependency patch를 하지 않았다. 추가 정보 없이 build를 반복하지 않으며 식별 결과를 작성 측 판단으로 넘긴다.
HTTP/별도 type/대상 lint는 미실행, 전체 lint 기존 실패와 Backend v1.5 통과 hash는 보존한다. 3-B 전체 수용/독립 재검토도 아직 미완료다.


### v1.7 최종 정적 확인

2026-11-08T03:16:47+09:00. source-only 임시 checker를 현재 bytes에서 직접 실행했다.
허용/실제 23경로·staged 0·범위 밖/제품 runtime 0·비무시 23개, Python AST 3개·Node 구문 7개,
현재 링크/anchor 218개·v1.7 source hash/metadata·v1.6 객체 원형 이력·CF/3-A/과거 본문/Next 326 bytes 보존,
코드 hash 11개·PR marker 각 1개/메모리 본문 3667 bytes·내장 Python/shell 구문·원격/repo/base/head/--draft·diff check가 통과했다.
정적 checker는 CLI나 suite/build를 다시 호출하지 않았다. 공식 실행의 20/35/진단 build 78과 별개다.
현재 실행 중/승인 대기/불확실 자원은 없고 자기 자원/key 임시 파일은 제거됐다. git/gh 변경 액션 0이다.
진단 자체의 독립 재검토와 새 접근/동작 정책 판단은 대기이며 3-B 전체 완료가 아니다.
