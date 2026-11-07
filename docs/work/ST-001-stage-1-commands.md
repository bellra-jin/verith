# ST-001 1단계 · 사용자 직접 commit/push/Draft PR 명령

독립 검토/수용 후 사용자가 저장소 루트 Terminal(zsh/macOS)에서 블록별로 실행한다.
**이 명령은 준비만 했고 실행하지 않았다.** 실제 변경은 문서 23개(JSON manifest 1개 포함)이며
같은 파일에 다른 사용자 편집이 섞였으면 staged diff를 검토하고 해당 부분은 보류한다.
다른 staged 변경이 있으면 중단하고 임의 unstage/reset/stash로 정리하지 않는다.
.env·credentials·ignored Compose·임시 자료는 포함하지 않는다. 과거 CF-002 stage 명령을 재사용하지 않는다.

## 1. 지정 파일만 stage하고 검토

```zsh
(
  set -eu
  cd "$(git rev-parse --show-toplevel)"
  [ "$(git branch --show-current)" = 'docs/document-authority' ] || { printf '%s\n' 'STOP: branch mismatch'; exit 1; }
  [ "$(git remote get-url origin)" = 'https://github.com/bellra-jin/verith.git' ] || { printf '%s\n' 'STOP: origin mismatch'; exit 1; }
  [ "$(git remote get-url --push origin)" = 'https://github.com/bellra-jin/verith.git' ] || { printf '%s\n' 'STOP: push origin mismatch'; exit 1; }
  [ "$(git rev-parse HEAD)" = 'a5b60f2fd0b00efedae2c98a2004ede62470b094' ] || { printf '%s\n' 'STOP: base HEAD changed'; exit 1; }
  git diff --cached --quiet -- || { printf '%s\n' 'STOP: existing staged changes'; exit 1; }
  git add -- \
    'PR_DESCRIPTION.md' \
    'README.md' \
    'backend/README.md' \
    'backend/docs/backend_coding_guidelines.md' \
    'backend/docs/cf002_commit_pr.md' \
    'backend/docs/cf002_pr_body.md' \
    'backend/docs/db_boundaries.md' \
    'backend/docs/flow_auth_ownership.md' \
    'backend/docs/flow_backend_handoff.md' \
    'backend/docs/flow_contract.md' \
    'backend/docs/google_login_check.md' \
    'backend/docs/report_archive_api_contract.md' \
    'backend/docs/technical_frontend_api_contract.md' \
    'docs/architecture/current-boundaries.md' \
    'docs/contracts/CF-001-v1.1.shared-v1.md' \
    'docs/contracts/CF-002-v0.6.shared-v1.md' \
    'docs/contracts/manifest.json' \
    'docs/documentation.md' \
    'docs/work/ST-001-stage-1-commands.md' \
    'docs/work/ST-001-stage-1-pr.md' \
    'docs/work/ST-001-stage-1.md' \
    'frontend/README.md' \
    'frontend/docs/frontend_coding_guidelines.md'
  git diff --cached --check
  git diff --cached --stat
)
```

출력된 파일과 `git diff --cached`를 직접 검토한 뒤 다음 블록으로 진행한다. add -A/강제 add는 쓰지 않는다.

## 2. 검토 후 commit

```zsh
(
  set -eu
  cd "$(git rev-parse --show-toplevel)"
  [ "$(git branch --show-current)" = 'docs/document-authority' ] || { printf '%s\n' 'STOP: branch mismatch'; exit 1; }
  [ "$(git remote get-url origin)" = 'https://github.com/bellra-jin/verith.git' ] || { printf '%s\n' 'STOP: origin mismatch'; exit 1; }
  [ "$(git remote get-url --push origin)" = 'https://github.com/bellra-jin/verith.git' ] || { printf '%s\n' 'STOP: push origin mismatch'; exit 1; }
  [ "$(git rev-parse HEAD)" = 'a5b60f2fd0b00efedae2c98a2004ede62470b094' ] || { printf '%s\n' 'STOP: base HEAD changed'; exit 1; }
  python3 - <<'ST001_STAGED_PATHS'
import subprocess
expected={'docs/architecture/current-boundaries.md', 'docs/contracts/CF-002-v0.6.shared-v1.md', 'docs/contracts/CF-001-v1.1.shared-v1.md', 'backend/README.md', 'backend/docs/db_boundaries.md', 'backend/docs/flow_auth_ownership.md', 'backend/docs/flow_backend_handoff.md', 'backend/docs/cf002_pr_body.md', 'docs/work/ST-001-stage-1-commands.md', 'PR_DESCRIPTION.md', 'docs/contracts/manifest.json', 'docs/work/ST-001-stage-1-pr.md', 'backend/docs/cf002_commit_pr.md', 'docs/documentation.md', 'docs/work/ST-001-stage-1.md', 'backend/docs/google_login_check.md', 'frontend/docs/frontend_coding_guidelines.md', 'backend/docs/backend_coding_guidelines.md', 'frontend/README.md', 'README.md', 'backend/docs/flow_contract.md', 'backend/docs/technical_frontend_api_contract.md', 'backend/docs/report_archive_api_contract.md'}
actual=set(filter(None,subprocess.check_output(['git','diff','--cached','--name-only','-z']).decode().split('\0')))
if actual!=expected:raise SystemExit('STOP: staged paths differ from reviewed ST-001 scope')
ST001_STAGED_PATHS
  git diff --cached --check
  git commit -m 'docs: establish document authority and shared Flow contracts'
)
```

## 3. commit 확인 후 push

한 개의 위 작업 commit인지 `git log -1 --stat`로 검토한다. origin/develop은 준비 시 a5b60f2였으며
실행 시 원격이 달라질 수 있다. 일반 push 거부 시 차이를 확인하고 force-push/rebase/merge를 임의로 하지 않는다.

```zsh
(
  set -eu
  cd "$(git rev-parse --show-toplevel)"
  [ "$(git branch --show-current)" = 'docs/document-authority' ] || { printf '%s\n' 'STOP: branch mismatch'; exit 1; }
  [ "$(git remote get-url origin)" = 'https://github.com/bellra-jin/verith.git' ] || { printf '%s\n' 'STOP: origin mismatch'; exit 1; }
  [ "$(git remote get-url --push origin)" = 'https://github.com/bellra-jin/verith.git' ] || { printf '%s\n' 'STOP: push origin mismatch'; exit 1; }
  [ "$(git rev-list --count a5b60f2fd0b00efedae2c98a2004ede62470b094..HEAD)" = '1' ] || { printf '%s\n' 'STOP: unexpected commit history'; exit 1; }
  git diff --quiet -- || { printf '%s\n' 'STOP: tracked changes remain'; exit 1; }
  git diff --cached --quiet -- || { printf '%s\n' 'STOP: staged changes remain'; exit 1; }
  git push --set-upstream origin docs/document-authority
)
```

## 4. 정확한 저장소의 Draft PR

제목/본문은 [PR 본문 파일](ST-001-stage-1-pr.md)에 준비했다. gh 인증이나 기존 PR 문제가 있으면
그 상태를 먼저 확인하고 임의 자격 생성/Ready/merge를 하지 않는다. PR 생성에는 정확한 repo/base/head를 명시한다.

```zsh
(
  set -eu
  cd "$(git rev-parse --show-toplevel)"
  [ "$(git branch --show-current)" = 'docs/document-authority' ] || { printf '%s\n' 'STOP: branch mismatch'; exit 1; }
  [ "$(git remote get-url origin)" = 'https://github.com/bellra-jin/verith.git' ] || { printf '%s\n' 'STOP: origin mismatch'; exit 1; }
  [ "$(git remote get-url --push origin)" = 'https://github.com/bellra-jin/verith.git' ] || { printf '%s\n' 'STOP: push origin mismatch'; exit 1; }
  gh pr create --repo https://github.com/bellra-jin/verith --draft \
    --base develop --head docs/document-authority \
    --title 'ST-001 1단계: 문서 정본과 공유 계약·현재 상태 정리' \
    --body-file docs/work/ST-001-stage-1-pr.md
)
```
