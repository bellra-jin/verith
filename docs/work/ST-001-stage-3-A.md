# ST-001 v1.3 · 3-A 공용 환경 참고 구현/검증 기록

> 현재 병합 주석 — 2026-11-08T00:53:41+09:00 확인: PR #5는 사용자 병합 완료로 전달됐고,
> mergedAt은 00:19:42 KST (`2026-11-07T15:19:42Z`)다. head `5eecd0b8c62ad56041e0b2a1bf888b9b053fd430`,
> merge/develop `7df12403848e480f223767232540d4c2c055ba5e`이며 fetch 후 로컬 develop과 일치했다.
> 아래 미커밋·commit/push/PR/병합 대기와 명령은 당시 이력이며 현재 재실행하지 않는다.
> 과거 본문·검사/미검증·PR/명령을 보존하고 현재 작업은 [3-B 기록](ST-001-stage-3-B.md)에 구분한다.

- 상태: 구현·자체 정적 검증·독립 검토 수용 완료. 사용자 직접 commit/push/Draft PR/병합 대기.
- 정본: ST-001_문서_정본과_안전한_개발_기반_정리.md v1.3 / 3-A.
  source SHA-256 `73f4c0b6d98fa3e33fc6d1d8f9fc0892f94608175eff3024d47a85300fbf1099`를 직접 읽어 수신값과 대조했다.
  v1.2는 중간 보존 이력이며 구현 기준으로 사용하지 않았다.
- 전체 작업 v1.1 / 지시서 작성 v1.2 / 코드 개발 v1.2와 root·서비스 AGENTS를 다시 읽고 운영 정본 hash가 기존값과 같음을 확인했다.
  Frontend CLAUDE의 AGENTS 참조를 확인했고 root/상위 .agents/skills는 없었다. 관련 Next 코드를 수정하지 않는다.
- 시작: develop, HEAD/로컬 develop/origin develop `6308d8c9517d8d8d4f1c7b69e845fb5fe33836ef`, staged/unstaged 0, worktree 1개, 동명 local/remote branch 없음.
  전체 fetch/push origin은 각각 단일 `https://github.com/bellra-jin/verith.git`이었다.
- 기본 sandbox의 fetch는 DNS 오류로 실패했다. 승인된 같은 fetch를 네트워크 허용 경로로 실행해 성공했고,
  develop ff-only 확인은 Already up to date였다. 그 develop에서 `chore/public-environment-examples`를 생성했다.
  원격이 전달 기준보다 앞선 변경은 없었다. 강제 정리·stash·다른 branch에서 분기하지 않았다.
- 선행 PR #4의 head `9bf536e53ca7dab75d35b43200198c298a54ec0e`, merge `6308d8c`,
  mergedAt 2026-11-07 23:28:57 KST (`2026-11-07T14:28:57Z`)는 전달된 병합 확인이다.
  이번에는 fetch 후 develop 일치와 Git 그래프/파일 차이를 직접 대조하며 새 GitHub API 검증으로 표현하지 않는다.

## 구현과 source 대조

[개발 안내](../development.md)에 서비스별 변수 표와 source 링크, 필수/선택·미설정/빈 값·fallback·
비밀 여부·driver·host/container 주소를 기록했다. 예제는 즉시 실행 가능한 설정이나 안전 bootstrap이 아니다.

| 직접 읽은 source | 반영한 경계 |
|---|---|
| Frontend src/api/backend.ts, src/lib/session-backend.ts·session-proxy.ts, package/lock | 공개 NEXT_PUBLIC_API_URL의 nullish fallback/빈 값과 서버 BACKEND_URL의 명시 요구를 구분. 3200/8200·Host/Origin·no-store/owner 경계 유지 |
| Backend src/api/config.py, auth/google.py, routes/auth.py, pyproject/lock | DATABASE_URL 공백 거부·asyncpg와 AI_SERVICE_URL의 검증 부재를 구분. graph true일 때만 Neo4j 필수, 기본 false. Google 빈 키/명시 local HTTP 선택·TTL·관리 DART 경계 |
| AI Supervisor/News config | BACKEND_BASE_URL 공백 fallback. QWEN_API_KEY는 endpoint, News 빈 값은 기존 추론 주소 fallback. 빈 token은 인증 완성이 아님 |
| Fundamental core/config.py, data/corp_code.py, interpret/llm_client.py | psycopg DSN·앱 자격 alias 위험·별도 최소 권한 미확인. URL 공백 lookup 거부와 static_fallback/source/risk flag를 구분. Qwen first alias·모델/LLM 기본과 OpenAI fallback 조건 |
| Industry config, Flow config/core/kis_client.py/nodes/explain.py, Technical config/services/cache_service.py | NEO4J_USERNAME 차이, LLM/embedding의 미설정/빈 값·모델 로딩, KIS·고정 Flow 모델·Technical OpenAI 모델 필수, 선택 cache 생략 |
| docs/local_ports.md·서비스 package/pyproject/lock | host 3200/8200/9200 및 15432/16379/17474/17687, 내부 5432/6379/7474/7687. 추론 주소·실제 private override를 예제로 복사하지 않음 |

새 Compose는 required image/credential 입력 문자열과 tmpfs를 쓴 별도 선택 참고다.
현재 project/labels/port의 비점유를 보장하지 않는다. 실제 실행 전 자원 사전확인·선택 image/권한/volume 검토가 필요하다.
Redis는 기본 제외 unfinished profile과 exit 78 placeholder이며 인증된 Redis 구성이 아니다.
앱/AI build·자동 migration/seed·기존 volume/host bind/secret mount를 포함하지 않는다.

## 변경 파일과 보존

허용/계획은 아래 16경로다. 이 기록 안에 PR 초안·사용자 명령도 넣으며 별도 script/명령 파일을 추가하지 않는다.

- [docs/development.md](../development.md)
- [docs/examples/frontend.env.example](../examples/frontend.env.example)
- [docs/examples/backend.env.example](../examples/backend.env.example)
- [docs/examples/ai.env.example](../examples/ai.env.example)
- [docs/examples/compose.local.example.yaml](../examples/compose.local.example.yaml)
- [README.md](../../README.md)
- [frontend/README.md](../../frontend/README.md)
- [backend/README.md](../../backend/README.md)
- [AGENTS.md](../../AGENTS.md)
- [frontend/AGENTS.md](../../frontend/AGENTS.md)
- [backend/AGENTS.md](../../backend/AGENTS.md)
- [ai/AGENTS.md](../../ai/AGENTS.md)
- [docs/documentation.md](../documentation.md)
- [docs/contracts/manifest.json](../contracts/manifest.json)
- [docs/work/ST-001-stage-2.md](ST-001-stage-2.md)
- [docs/work/ST-001-stage-3-A.md](ST-001-stage-3-A.md)

manifest는 기존 v1.0 이력을 유지하고 직전 v1.1 work_item을 원형으로 한 번만 추가했다.
현재 work_item만 v1.3/source hash/3-A/6308d8c로 갱신했다. CF snapshot bytes/source/publication/hash/
reviewed metadata와 reference_documents는 불변이다. 2단계 보고에는 상단 병합 주석만 추가했으며
역사 본문/명령·실패/미검증과 README 포트폴리오·Next 규칙 블록은 보존한다.

## 검증·제외·후속

최종 직접 정적 검사 결과는 아래 마지막 검사 절에 기록한다. 이전 2단계 148개/1단계 210개 검사는
보고 확인이며 이번 diff의 새 검사로 재사용하지 않는다. 기존 전체 lint 실패·실제 인증의 자연 만료/옛 cookie
재전송 등 미검증·Fundamental 최소 DB 권한 미확인은 [검증 상태](../documentation.md#검증-상태와-이력)에 보존한다.

기능/unit/build/lint·새 설치·앱 config import·Docker 조회/up/build/pull/config·migration/seed·실DB/
Google/AI·모델 다운로드·실제 .env/credentials/ignored Compose/Docker Env 읽기는 미실행이다.
예제/빈 키/placeholder는 AI 전체 차단이나 안전한 오프라인 모드가 아니다. 실제 namespace/port/image/
자격/권한/private override와 기동·정리는 미검증이다. 이번 단계에는 생성한 서비스 자원이 없다.

독립 검토에서 수정이 필요한 사실상 결함은 발견되지 않아 3-A 문서/환경 참고와 사용자 실행 준비 범위로 수용됐다.
구현·자체 정적 검사·독립 수용과 실제 재현 검증을 구분하며 실제 앱/자원 검증 완료로 확대하지 않는다.
3-A 검토/수정·재검증과 사용자 병합 후 최신 develop에서 별도 3-B→3-C로 진행한다.
구조 재배치/큰 파일 분리는 비교 판단 전 보류이며 현재 branch에 후속 코드를 누적하지 않는다.

## 사용자 직접 실행 준비

권장 commit: `docs: add public environment reference examples`

Draft PR 제목: **ST-001 3-A: 비밀 없는 공용 환경 참고와 자원 경계 정리**

<!-- ST001_3A_PR_BEGIN -->
개인 환경 파일 없이 변수 소비자·미설정 동작과 실행 전 조건을 파악하도록 ST-001 v1.3 3-A 환경 참고를 추가합니다. 실제 앱/설정/DB/권한 동작은 변경하지 않습니다.

## 변경

- 서비스별 비밀 없는 env 참고와 개발 안내를 추가하고 필수/선택·빈 값·fallback·alias/driver·host/container 주소를 구분합니다.
- Backend AI URL 필수 검증 부재, 조건부 graph/Neo4j 변수명 차이, Fundamental 앱 DSN 상속 위험/static_fallback·권한 미확인, Qwen endpoint 의미와 AI 모델 로딩 위험을 명시합니다.
- 별도 선택 Compose는 required image/credential·loopback·tmpfs 참고이며 실제 기동 미검증입니다. Redis는 미완성 optional profile/실패 placeholder로 제한합니다. namespace만으로 격리를 보장하지 않습니다.
- 현재 안내와 manifest 작업 메타데이터만 갱신하고 v1.0/v1.1 이력·CF bytes/출처/metadata/reference·과거 2단계 본문/명령·Next 블록·포트폴리오를 보존합니다.

## 검증과 제한

- PR #4 병합 develop 6308d8c에서 fetch/ff-only 확인 후 chore/public-environment-examples를 생성했습니다. 허용 16경로만 수정합니다.
- source 텍스트/AST 대조와 비확장 파싱에서 env 변수 41개, YAML 서비스 3개/required 입력 7개를 확인했습니다. env 오류 8건·YAML 오류 4건을 거부했습니다. 링크/anchor 208개, Next 326 bytes·manifest/hash/본문 보존·허용 16경로·staged 0·runtime/범위 밖 diff 0·diff check가 통과했습니다. zsh 4블록·내장 Python 5개 구문과 URL guard 8개의 정상 통과/추가 URL 거부도 확인했습니다. 독립 검토도 3-A 문서/환경 참고와 사용자 실행 준비 범위로 수용됐으며 수정이 필요한 사실상 결함은 발견되지 않았습니다.
- 독립 검토자는 역사본문을 포함한 로컬 경로 252개와 anchor 9개를 확인했습니다. 자체 현재 안내 208개와 검사 범위가 다릅니다. 임시 checker 소스를 읽고 안전성을 확인했지만 전체 checker를 그대로 재실행한 결과는 아닙니다.
- 예제는 실제 환경·안전 bootstrap/오프라인 AI가 아닙니다. 기존 비밀/ignored Compose·Docker Env를 읽지 않으며 기능/unit/build/lint·설치·앱 import·Docker/실DB/Google/AI·migration/seed/모델 다운로드는 실행하지 않습니다.
- 기존 lint 실패·실제 인증 미검증·실제 DB 최소 권한/private override·namespace/image/port 미확인은 남습니다. 3-B/3-C는 미구현이고 구조 재배치도 보류합니다.

수용은 3-A 문서/예제와 사용자 실행 준비에 한정합니다. 실제 commit/push/Draft PR/Ready/merge는 사용자가 직접 하며 이 단계 병합 후 별도 3-B→3-C로 진행합니다.
<!-- ST001_3A_PR_END -->

## 사용자 명령 1 · 허용 파일만 stage 후 검토

독립 검토·수용 후 저장소 Terminal(zsh/macOS)에서 블록별로 실행한다. 기존 staged/HEAD/전체 원격 URL/
허용 파일이 다르면 중단한다. 새 사용자 편집이 같은 파일에 섞이면 diff를 검토하고 보류한다.
아래 git/gh action 블록은 실행하지 않았다. 예제/문서 외 실제 설정·비밀·ignored 자료를 추가하지 않는다.

```zsh
(
  set -eu
  cd "$(git rev-parse --show-toplevel)"
  [ "$(git branch --show-current)" = 'chore/public-environment-examples' ] || { printf '%s\n' 'STOP: branch mismatch'; exit 1; }
  [ "$(git remote get-url --all origin)" = 'https://github.com/bellra-jin/verith.git' ] || { printf '%s\n' 'STOP: origin mismatch'; exit 1; }
  [ "$(git remote get-url --push --all origin)" = 'https://github.com/bellra-jin/verith.git' ] || { printf '%s\n' 'STOP: push origin mismatch'; exit 1; }
  [ "$(git rev-parse HEAD)" = '6308d8c9517d8d8d4f1c7b69e845fb5fe33836ef' ] || { printf '%s\n' 'STOP: base HEAD changed'; exit 1; }
  git diff --cached --quiet -- || { printf '%s\n' 'STOP: existing staged changes'; exit 1; }
  python3 - <<'ST001_3A_PATHS'
from pathlib import Path
import subprocess
expected={'docs/examples/compose.local.example.yaml', 'backend/AGENTS.md', 'docs/contracts/manifest.json', 'docs/work/ST-001-stage-3-A.md', 'docs/work/ST-001-stage-2.md', 'docs/examples/ai.env.example', 'docs/development.md', 'ai/AGENTS.md', 'docs/examples/frontend.env.example', 'backend/README.md', 'docs/documentation.md', 'README.md', 'frontend/README.md', 'frontend/AGENTS.md', 'AGENTS.md', 'docs/examples/backend.env.example'}
def names(*args):
    return set(subprocess.check_output(['git',*args,'-z']).decode().rstrip('\0').split('\0'))-{''}
actual=names('diff','--name-only') | names('ls-files','--others','--exclude-standard')
if actual!=expected or any(not Path(p).is_file() or Path(p).is_symlink() for p in expected):
    raise SystemExit('STOP: unexpected files; preserve changes and review')
ST001_3A_PATHS
  git add -- \
    'docs/development.md' \
    'docs/examples/frontend.env.example' \
    'docs/examples/backend.env.example' \
    'docs/examples/ai.env.example' \
    'docs/examples/compose.local.example.yaml' \
    'README.md' \
    'frontend/README.md' \
    'backend/README.md' \
    'AGENTS.md' \
    'frontend/AGENTS.md' \
    'backend/AGENTS.md' \
    'ai/AGENTS.md' \
    'docs/documentation.md' \
    'docs/contracts/manifest.json' \
    'docs/work/ST-001-stage-2.md' \
    'docs/work/ST-001-stage-3-A.md'
  git diff --cached --check
  git diff --cached --stat
)
```

## 사용자 명령 2 · 검토한 변경 commit

지정 경로만으로도 같은 파일 안의 새 사용자 변경까지 구별할 수 없으므로 staged diff를 직접 검토한다.

```zsh
(
  set -eu
  cd "$(git rev-parse --show-toplevel)"
  [ "$(git branch --show-current)" = 'chore/public-environment-examples' ] || { printf '%s\n' 'STOP: branch mismatch'; exit 1; }
  [ "$(git remote get-url --all origin)" = 'https://github.com/bellra-jin/verith.git' ] || { printf '%s\n' 'STOP: origin mismatch'; exit 1; }
  [ "$(git remote get-url --push --all origin)" = 'https://github.com/bellra-jin/verith.git' ] || { printf '%s\n' 'STOP: push origin mismatch'; exit 1; }
  [ "$(git rev-parse HEAD)" = '6308d8c9517d8d8d4f1c7b69e845fb5fe33836ef' ] || { printf '%s\n' 'STOP: base HEAD changed'; exit 1; }
  python3 - <<'ST001_3A_CACHED'
import subprocess
expected={'docs/examples/compose.local.example.yaml', 'backend/AGENTS.md', 'docs/contracts/manifest.json', 'docs/work/ST-001-stage-3-A.md', 'docs/work/ST-001-stage-2.md', 'docs/examples/ai.env.example', 'docs/development.md', 'ai/AGENTS.md', 'docs/examples/frontend.env.example', 'backend/README.md', 'docs/documentation.md', 'README.md', 'frontend/README.md', 'frontend/AGENTS.md', 'AGENTS.md', 'docs/examples/backend.env.example'}
actual=set(subprocess.check_output(['git','diff','--cached','--name-only','-z']).decode().rstrip('\0').split('\0'))-{''}
if actual!=expected:
    raise SystemExit('STOP: staged paths mismatch')
ST001_3A_CACHED
  git diff --cached --check
  git commit -m 'docs: add public environment reference examples'
)
```

## 사용자 명령 3 · commit 확인 후 push

commit 내용을 확인한다. 원격 변경/보호 규칙으로 거부되면 차이를 검토하고 force-push/rebase/merge로 우회하지 않는다.

```zsh
(
  set -eu
  cd "$(git rev-parse --show-toplevel)"
  [ "$(git branch --show-current)" = 'chore/public-environment-examples' ] || { printf '%s\n' 'STOP: branch mismatch'; exit 1; }
  [ "$(git remote get-url --all origin)" = 'https://github.com/bellra-jin/verith.git' ] || { printf '%s\n' 'STOP: origin mismatch'; exit 1; }
  [ "$(git remote get-url --push --all origin)" = 'https://github.com/bellra-jin/verith.git' ] || { printf '%s\n' 'STOP: push origin mismatch'; exit 1; }
  git merge-base --is-ancestor 6308d8c9517d8d8d4f1c7b69e845fb5fe33836ef HEAD || { printf '%s\n' 'STOP: base ancestry changed'; exit 1; }
  [ "$(git rev-list --count 6308d8c9517d8d8d4f1c7b69e845fb5fe33836ef..HEAD)" = '1' ] || { printf '%s\n' 'STOP: unexpected commit history'; exit 1; }
  git diff --quiet -- || { printf '%s\n' 'STOP: tracked changes remain'; exit 1; }
  git diff --cached --quiet -- || { printf '%s\n' 'STOP: existing staged changes'; exit 1; }
  python3 - <<'ST001_3A_COMMITTED'
import subprocess
expected={'docs/examples/compose.local.example.yaml', 'backend/AGENTS.md', 'docs/contracts/manifest.json', 'docs/work/ST-001-stage-3-A.md', 'docs/work/ST-001-stage-2.md', 'docs/examples/ai.env.example', 'docs/development.md', 'ai/AGENTS.md', 'docs/examples/frontend.env.example', 'backend/README.md', 'docs/documentation.md', 'README.md', 'frontend/README.md', 'frontend/AGENTS.md', 'AGENTS.md', 'docs/examples/backend.env.example'}
actual=set(subprocess.check_output(['git','diff','--name-only','-z','6308d8c9517d8d8d4f1c7b69e845fb5fe33836ef','HEAD']).decode().rstrip('\0').split('\0'))-{''}
if actual!=expected:
    raise SystemExit('STOP: committed paths mismatch')
ST001_3A_COMMITTED
  git push --set-upstream origin chore/public-environment-examples
)
```

## 사용자 명령 4 · 정확한 저장소에 Draft PR

자기 신규 임시 파일에 이 문서의 PR 본문만 추출하고 종료 시 그 파일만 정리한다.
gh 자격/동명 PR 문제는 먼저 확인하며 Ready/merge·자격 생성은 대신하지 않는다.

```zsh
(
  set -eu
  cd "$(git rev-parse --show-toplevel)"
  [ "$(git branch --show-current)" = 'chore/public-environment-examples' ] || { printf '%s\n' 'STOP: branch mismatch'; exit 1; }
  [ "$(git remote get-url --all origin)" = 'https://github.com/bellra-jin/verith.git' ] || { printf '%s\n' 'STOP: origin mismatch'; exit 1; }
  [ "$(git remote get-url --push --all origin)" = 'https://github.com/bellra-jin/verith.git' ] || { printf '%s\n' 'STOP: push origin mismatch'; exit 1; }
  git merge-base --is-ancestor 6308d8c9517d8d8d4f1c7b69e845fb5fe33836ef HEAD || { printf '%s\n' 'STOP: base ancestry changed'; exit 1; }
  [ "$(git rev-list --count 6308d8c9517d8d8d4f1c7b69e845fb5fe33836ef..HEAD)" = '1' ] || { printf '%s\n' 'STOP: unexpected commit history'; exit 1; }
  git diff --quiet -- || { printf '%s\n' 'STOP: tracked changes remain'; exit 1; }
  git diff --cached --quiet -- || { printf '%s\n' 'STOP: existing staged changes'; exit 1; }
  python3 - <<'ST001_3A_COMMITTED'
import subprocess
expected={'docs/examples/compose.local.example.yaml', 'backend/AGENTS.md', 'docs/contracts/manifest.json', 'docs/work/ST-001-stage-3-A.md', 'docs/work/ST-001-stage-2.md', 'docs/examples/ai.env.example', 'docs/development.md', 'ai/AGENTS.md', 'docs/examples/frontend.env.example', 'backend/README.md', 'docs/documentation.md', 'README.md', 'frontend/README.md', 'frontend/AGENTS.md', 'AGENTS.md', 'docs/examples/backend.env.example'}
actual=set(subprocess.check_output(['git','diff','--name-only','-z','6308d8c9517d8d8d4f1c7b69e845fb5fe33836ef','HEAD']).decode().rstrip('\0').split('\0'))-{''}
if actual!=expected:
    raise SystemExit('STOP: committed paths mismatch')
ST001_3A_COMMITTED
  umask 077
  st001_3a_body_file=$(mktemp -t st001-3a-pr)
  trap 'rm -f -- "$st001_3a_body_file"' EXIT
  python3 - "$st001_3a_body_file" <<'ST001_3A_BODY'
from pathlib import Path
import sys
text=Path('docs/work/ST-001-stage-3-A.md').read_text()
begin='<!-- ST001_3A_PR_BEGIN -->'
end='<!-- ST001_3A_PR_END -->'
if text.count(begin)!=2 or text.count(end)!=2:
    raise SystemExit('STOP: PR body markers changed')
body=text.split(begin,1)[1].split(end,1)[0].strip()+'\n'
Path(sys.argv[1]).write_text(body)
ST001_3A_BODY
  gh pr create --repo https://github.com/bellra-jin/verith --draft \
    --base develop --head chore/public-environment-examples \
    --title 'ST-001 3-A: 비밀 없는 공용 환경 참고와 자원 경계 정리' \
    --body-file "$st001_3a_body_file"
)
```

## 최종 자체 정적 검사

2026-11-07T23:57:03+09:00 기준 자체 검사다. 아래 임시 도구를 기존 환경에서 실행했으며 새 의존성이나
영구 script/검사 entry는 추가하지 않았다. 보고서 마감 후 같은 검사기를 최종 diff에서 다시 실행한다.

```text
backend/.venv/bin/python -I /tmp/st001_3a_check.py
git diff --check
```

환경은 기존 Backend Python과 PyYAML 6.0.3이다. 추가 parser 설치/JSON 대안은 필요하지 않았다.
SafeLoader를 기반으로 중복 key·명시 tag/anchor/alias를 거부하고, 명시한 새 YAML bytes만 읽었다.
env는 새 예제 stream에 한정한 엄격한 한 줄 KEY=VALUE parser로 읽어 실행/보간/자동 탐색을 하지 않았다.
source는 텍스트/AST와 package JSON/pyproject·lock의 비실행 파싱으로 확인했다. 앱 module을 import하지 않았다.

| 검사 | 직접 결과와 범위 |
|---|---|
| source 대조 | Python source 14개 AST/텍스트, Frontend 3개 TS와 package/pyproject/lock·공개 포트 문서. guide의 필수/조건부/검증 부재·alias/driver·fallback 경계와 대조 |
| env | Frontend 2개·Backend 17개·AI 22개 = 변수 41개. 빈 비밀/명확한 placeholder·실제 소비자·AI 앱 DSN 미포함 확인. 중복/모호한 quote/다중행/잘못된 key·source/보간 구문 합성 오류 8건 거부 |
| YAML | 서비스 3개, required image/credential 입력 7개를 확장하지 않은 문자열로 확인. 정확한 loopback/tcp mapping·profile/실패 placeholder·tmpfs·금지 구조 부재 확인. 중복 key/unsafe tag/anchor·alias 합성 오류 4건 거부 |
| 현재 링크/anchor | 208개 통과, 오류 0. 새 안내·예제 참조·서비스 AGENTS·현재 문서 목록·보고서를 검사. README 역사와 2단계 기존 본문은 재발행하지 않고 새 부분만 검사. 외부 HTTP 조회 없음 |
| 보존/hash | Next 원문 326 bytes 동일. CF 2개 bytes·source/pub/hash/reviewed metadata·reference 불변. ST v1.3 source hash/기존 v1.0·v1.1 hash 및 work_item 원형 이력 확인. 2단계 본문/명령·README 역사/포트폴리오 보존 |
| 허용 범위 | 실제 16경로=허용 16경로, staged 0, 범위 밖/runtime/config/package/lock 변경 0. 기존 추적 파일의 허용 범위 밖 bytes도 시작 상태와 동일 |
| 사용자 명령 | zsh 4블록 syntax-only·내장 Python 5개 구문 통과. stage/commit/committed 경로 집합 16개 대조, HEAD/이력·staged·repo/base/head/--draft 확인. 실제 URL guard 8개 정상 통과, 프로세스 한정 추가 URL은 8개 모두 거부, 실제 원격 설정 전후 동일 |
| PR 본문/노출 | markers/메모리 추출 정상. 실제 임시 PR 파일 생성/cleanup은 실행하지 않고 trap 코드만 검토. 새 파일의 개인 경로/계정·개인 endpoint/사설 주소·비밀/원시 영수증 제외를 내용·정적 패턴으로 확인 |
| whitespace | git diff --check 통과 |

임시 검사기 초안은 required 변수명의 숫자 4를 허용하지 않아 NEO4J 입력을 잘못 거부했다.
검사기 정규식의 숫자 허용 누락만 수정하고 전체 관련 정적 검사를 재실행해 통과했다. 예제/계약/기대값을
완화한 수정은 없었다. 최초 sandbox fetch DNS 실패와 재시도 성공은 상단 착수 기록과 구분한다.

개인/비밀 검사는 명시된 새 내용의 패턴/검토 범위이며 모든 자료에 대한 비밀 탐지 보장은 아니다.
이미지 존재/실제 Compose 보간·인증/기동/volume 동작과 자동 정리, 실제 DB/Google/AI·모델·기능 검사는
미실행이다. 2단계 독립 148개와 이번 208개는 검사 대상이 다르며 이전 통과를 재사용하지 않았다.
위 최초 자체 검사 시점에는 독립 검토 대기였으며, 그 자체 통과를 당시 독립 수용/실제 재현 완료로 표현하지 않았다.

## 독립 수용과 최종 상태 마감

2026-11-08T00:03:48+09:00에 전달받은 독립 검토 결과를 반영했다. 수정이 필요한 사실상 결함은 없었으며
수용은 ST-001 v1.3 3-A 문서/환경 참고와 사용자 실행 준비에 한정한다.
독립 검토자는 정본 hash·branch/HEAD·허용 16경로/staged 0/범위 밖·runtime 0/diff check,
env 41개의 소비/required/blank/fallback/alias/driver, YAML SafeLoader 비보간 구조·서비스 3개·
required 입력 7개·loopback/tmpfs/optional profile/Redis exit 78, CF bytes/hash/metadata/reference·
manifest 이력·Next/역사본문 보존을 직접 확인했다. 독립 링크 검사는 역사본문을 포함한 로컬 경로 252개와
anchor 9개로, 자체 현재 안내 208개 검사와 범위가 다르다. 사용자 명령 zsh 4개/Python 5개 구문,
URL guard 정상 8개 통과/추가 8개 거부, stage/HEAD/branch·Draft PR repo/base/head/--draft·임시 정리 범위도 확인했다.
검토자가 임시 checker 소스를 읽고 안전성을 확인한 것과 전체 checker를 그대로 재실행한 것은 구분한다.

이번 마감은 이 기록의 상태/PR 본문/이력 문구만 갱신했으며 다른 15파일과 기존 명령 4블록은 보존했다.
마감 후 기존 `/tmp/st001_3a_check.py`를 최종 bytes에서 다시 실행했고 위 자체 정적 검사 항목이 모두 통과했다.
현재 안내 링크/anchor 208개, 허용 16경로·staged 0·범위 밖/runtime 0과 diff check도 재확인했다.
이는 개발 측 직접 재실행이며 독립 검토자의 실행으로 기록하지 않는다.
실제 Compose image/UID/volume/namespace/port·자격/권한·앱 동작은 미검증이다. 앱 import/Docker/
실DB/Google/AI·private 파일·설치와 실제 add/commit/push/PR/Ready/merge는 실행하지 않았다.
사용자 직접 실행·병합 대기이며 병합 후 별도 3-B→3-C, 구조 재배치 보류 조건을 유지한다.
