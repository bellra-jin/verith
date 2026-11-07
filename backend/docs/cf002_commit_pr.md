# CF-002 사용자 직접 commit/push·Draft PR 안내

2026-11-07 최종 작업 상태 기준. 아래 명령은 **준비만 했고 실행하지 않았다**. zsh/macOS에서 블록별로 실행한다. 자동으로 브랜치를 전환하거나 stash/reset/force-push하지 않는다.

- 작업 branch `feat/flow-auth-ownership`, 기준/현재 HEAD `d8d800b104822dfc72e1a7b0daecfa1ac45b9e43`, origin `https://github.com/bellra-jin/verith.git`, PR base `develop`.
- 준비 시 staged 변경0건. 기준 작업 트리는 깨끗했고 이번 목록은 CF-002 작업/승인된 포트 변경 경로와 대조했다. 이후 사용자 편집이 같은 파일에 섞였으면 staged diff를 검토하고 그 파일의 stage를 보류한다. 지금 원격을 fetch하지 않았으므로 로컬 origin/develop을 원격 최신이라고 단정하지 않는다.
- 아래 exact 파일만 stage한다. `.env`·credentials·임시 자원·ignored Docker-compose.yml은 포함하지 않는다. **ignored compose ports-only 수정은 로컬에만 남고 PR에 전달되지 않는다.** `git add -A`, `git add .`, `git add -f`를 사용하지 않는다.
- 기존 staged 변경, branch/HEAD/origin 불일치면 중단한다. 임의 unstage/reset으로 정리하지 않는다. push가 거부되면 force 대신 원격 차이를 확인한다. 실패한 검사를 숨기지 않으며 Draft 유지가 맞다.

## 1. 지정 파일만 stage한 뒤 확인

아래 블록을 실행하면 stage만 한다. 출력된 목록/통계를 확인하고 이어서 `git diff --cached`로 내용을 검토한다. 코드 블록은 private 값 출력 명령을 포함하지 않지만, 사용자가 이후 새 비밀을 코드에 직접 넣었다면 그 파일은 stage/출력을 보류한다.

```zsh
(
  set -eu
  cd /Users/parkjinhee/AI/verith_refactor/verith
  [ "$(git branch --show-current)" = 'feat/flow-auth-ownership' ] || { printf '%s\n' 'STOP: branch mismatch'; exit 1; }
  [ "$(git remote get-url origin)" = 'https://github.com/bellra-jin/verith.git' ] || { printf '%s\n' 'STOP: origin mismatch'; exit 1; }
  [ "$(git remote get-url --push origin)" = 'https://github.com/bellra-jin/verith.git' ] || { printf '%s\n' 'STOP: push origin mismatch'; exit 1; }
  [ "$(git rev-parse HEAD)" = 'd8d800b104822dfc72e1a7b0daecfa1ac45b9e43' ] || { printf '%s\n' 'STOP: HEAD changed'; exit 1; }
  git diff --cached --quiet -- || { printf '%s\n' 'STOP: pre-existing staged changes'; exit 1; }
git add -- \
  'README.md' \
  'ai/src/agents/fundamental/README.md' \
  'ai/src/agents/fundamental/README/06_DEV_GUIDE.md' \
  'ai/src/agents/industry/config.py' \
  'ai/src/agents/news/CLAUDE.md' \
  'ai/src/agents/news/README.md' \
  'ai/src/agents/news/config.py' \
  'ai/src/agents/news/demo_pipeline_app.py' \
  'ai/src/agents/news/services/backend/__init__.py' \
  'ai/src/agents/news/services/backend/client.py' \
  'ai/src/agents/technical/README.md' \
  'ai/src/agents/technical/docs/config.md' \
  'ai/src/supervisor/README.md' \
  'ai/src/supervisor/config.py' \
  'ai/src/supervisor/devtools/streamlit_supervisor_news_lab.py' \
  'ai/src/supervisor/scripts/smoke_supervisor.py' \
  'backend/README.md' \
  'backend/db/graph/driver.py' \
  'backend/db/migrations/env.py' \
  'backend/db/migrations/versions/20261107_c2001a7e0001_auth_and_flow_owner.py' \
  'backend/db/models/auth/__init__.py' \
  'backend/db/models/auth/models.py' \
  'backend/db/models/common/agent_report.py' \
  'backend/db/models/flow/flow_report.py' \
  'backend/db/models/registry.py' \
  'backend/db/session.py' \
  'backend/docs/cf002_commit_pr.md' \
  'backend/docs/cf002_pr_body.md' \
  'backend/docs/db_boundaries.md' \
  'backend/docs/flow_auth_ownership.md' \
  'backend/docs/google_login_check.md' \
  'backend/docs/migrations.md' \
  'backend/docs/schema.md' \
  'backend/pyproject.toml' \
  'backend/scripts/cf002_concurrency_check.py' \
  'backend/scripts/cf002_controller_check.py' \
  'backend/scripts/cf002_interactive_login.py' \
  'backend/scripts/cf002_migration_check.py' \
  'backend/scripts/check_cf002_database.py' \
  'backend/scripts/export_industry_graph.py' \
  'backend/scripts/export_news_graph.py' \
  'backend/scripts/google_login_bootstrap.py' \
  'backend/scripts/google_login_controller.py' \
  'backend/scripts/google_login_inputs.py' \
  'backend/scripts/google_login_workspace.py' \
  'backend/scripts/runner_owned_database.py' \
  'backend/scripts/seed_representative_stocks.py' \
  'backend/scripts/seed_stock_aliases.py' \
  'backend/scripts/seed_stocks.py' \
  'backend/src/api/access_boundary.py' \
  'backend/src/api/auth/__init__.py' \
  'backend/src/api/auth/google.py' \
  'backend/src/api/config.py' \
  'backend/src/api/main.py' \
  'backend/src/api/repositories/flow_report_repository.py' \
  'backend/src/api/routes/auth.py' \
  'backend/src/api/routes/flow_reports.py' \
  'backend/src/api/routes/reports.py' \
  'backend/src/api/services/auth_service.py' \
  'backend/src/api/services/flow_report_service.py' \
  'backend/src/api/services/technical_report_service.py' \
  'backend/tests/conftest.py' \
  'backend/tests/db_safety.py' \
  'backend/tests/flow_integration/conftest.py' \
  'backend/tests/flow_integration/test_cf002_auth_ownership.py' \
  'backend/tests/flow_integration/test_cf002_preflight.py' \
  'backend/tests/flow_integration/test_flow_persistence.py' \
  'backend/tests/unit/conftest.py' \
  'backend/tests/unit/test_cf002_boundary.py' \
  'backend/tests/unit/test_cf002_google.py' \
  'backend/tests/unit/test_cf002_local_ports.py' \
  'backend/tests/unit/test_cf002_review_regressions.py' \
  'backend/tests/unit/test_cf002_session_failures.py' \
  'backend/tests/unit/test_flow_contract.py' \
  'backend/tests/unit/test_google_login_controller.py' \
  'backend/tests/unit/test_google_login_inputs.py' \
  'backend/tests/unit/test_google_login_workspace.py' \
  'backend/tests/unit/test_interactive_runner_security.py' \
  'backend/tests/unit/test_runner_owned_database.py' \
  'backend/uv.lock' \
  'docs/local_ports.md' \
  'frontend/README.md' \
  'frontend/docs/frontend_coding_guidelines.md' \
  'frontend/next.config.ts' \
  'frontend/package.json' \
  'frontend/scripts/check-local-ports.mjs' \
  'frontend/src/api/backend.ts' \
  'frontend/src/api/flow.ts' \
  'frontend/src/api/supervisor.ts' \
  'frontend/src/app/api/auth/[action]/route.ts' \
  'frontend/src/app/api/flow/reports/route.ts' \
  'frontend/src/app/api/fundamental/reports/[reportId]/html/route.ts' \
  'frontend/src/app/api/fundamental/reports/route.ts' \
  'frontend/src/app/api/industry/reports/[reportId]/html/route.ts' \
  'frontend/src/app/api/industry/reports/route.ts' \
  'frontend/src/app/api/news/reports/route.ts' \
  'frontend/src/app/api/private/[...path]/route.ts' \
  'frontend/src/app/api/supervisor/analyze/route.ts' \
  'frontend/src/app/api/technical/reports/route.ts' \
  'frontend/src/app/page.tsx' \
  'frontend/src/app/reports/flow/[reportId]/page.tsx' \
  'frontend/src/app/research/page.tsx' \
  'frontend/src/app/unavailable/page.tsx' \
  'frontend/src/features/flow/components/session-controls.tsx' \
  'frontend/src/lib/archive-pagination.ts' \
  'frontend/src/lib/disabled-feature.ts' \
  'frontend/src/lib/session-backend.ts' \
  'frontend/src/lib/session-proxy.ts' \
  'frontend/src/proxy.ts' \
  'frontend/tests/disabled-http.test.mjs' \
  'frontend/tests/disabled-routes.test.mjs' \
  'frontend/tests/ports-http.test.mjs' \
  'frontend/tests/ports.test.mjs' \
  'frontend/tests/session-http.test.mjs' \
  'frontend/tests/session-proxy.test.mjs'
  git diff --cached --check
  git diff --cached --stat
)
```

## 2. 검토 후 commit

권장 메시지: `feat(auth): enforce Google sessions and Flow ownership boundaries`

```zsh
(
  set -eu
  cd /Users/parkjinhee/AI/verith_refactor/verith
  [ "$(git branch --show-current)" = 'feat/flow-auth-ownership' ] || { printf '%s\n' 'STOP: branch mismatch'; exit 1; }
  [ "$(git remote get-url origin)" = 'https://github.com/bellra-jin/verith.git' ] || { printf '%s\n' 'STOP: origin mismatch'; exit 1; }
  [ "$(git remote get-url --push origin)" = 'https://github.com/bellra-jin/verith.git' ] || { printf '%s\n' 'STOP: push origin mismatch'; exit 1; }
  [ "$(git rev-parse HEAD)" = 'd8d800b104822dfc72e1a7b0daecfa1ac45b9e43' ] || { printf '%s\n' 'STOP: HEAD changed'; exit 1; }
python3 - <<'CF002_STAGE_GUARD'
import re,subprocess
from pathlib import Path
expected=set(re.findall(r"^- `([^`]+)`$",Path("backend/docs/flow_auth_ownership.md").read_text(),re.M))
actual=set(filter(None,subprocess.check_output(["git","diff","--cached","--name-only","-z"]).decode().split("\0")))
if actual != expected:
    raise SystemExit("STOP: staged paths differ from the reviewed CF-002 manifest; do not commit")
CF002_STAGE_GUARD
  git diff --cached --check
  git commit -m 'feat(auth): enforce Google sessions and Flow ownership boundaries'
)
```

## 3. push

사용자가 만든 위 commit만인지 `git log -1 --stat`로 확인한 뒤 실행한다. 기존 ignored/private 로컬 파일은 전송되지 않는다. branch/origin 변경·추가 commit 또는 일반 push 거부 시 중단한다.

```zsh
(
  set -eu
  cd /Users/parkjinhee/AI/verith_refactor/verith
  [ "$(git branch --show-current)" = 'feat/flow-auth-ownership' ] || { printf '%s\n' 'STOP: branch mismatch'; exit 1; }
  [ "$(git remote get-url origin)" = 'https://github.com/bellra-jin/verith.git' ] || { printf '%s\n' 'STOP: origin mismatch'; exit 1; }
  [ "$(git remote get-url --push origin)" = 'https://github.com/bellra-jin/verith.git' ] || { printf '%s\n' 'STOP: push origin mismatch'; exit 1; }
  [ "$(git rev-list --count d8d800b104822dfc72e1a7b0daecfa1ac45b9e43..HEAD)" = '1' ] || { printf '%s\n' 'STOP: unexpected commit history'; exit 1; }
  git diff --quiet -- || { printf '%s\n' 'STOP: tracked changes remain'; exit 1; }
  git diff --cached --quiet -- || { printf '%s\n' 'STOP: staged changes remain'; exit 1; }
  git push --set-upstream origin feat/flow-auth-ownership
)
```

## 4. Draft PR

제목: **CF-002: Google OIDC 세션과 Flow 소유권 경계 구현**

본문은 같은 저장소의 `backend/docs/cf002_pr_body.md`에 완성된 텍스트로 준비했다. 실패한 전체 ESLint와 실제시간만료/옛cookie 등 미검증 항목도 포함한다. gh 인증이 없으면 사용자가 자기 환경에서 준비하며 assistant가 credential을 읽지 않는다. 기존 PR이 있으면 중복 생성 대신 확인한다. Ready/merge는 하지 않는다.

```zsh
(
  set -eu
  cd /Users/parkjinhee/AI/verith_refactor/verith
  [ "$(git branch --show-current)" = 'feat/flow-auth-ownership' ] || { printf '%s\n' 'STOP: branch mismatch'; exit 1; }
  [ "$(git remote get-url origin)" = 'https://github.com/bellra-jin/verith.git' ] || { printf '%s\n' 'STOP: origin mismatch'; exit 1; }
  [ "$(git remote get-url --push origin)" = 'https://github.com/bellra-jin/verith.git' ] || { printf '%s\n' 'STOP: push origin mismatch'; exit 1; }
  gh pr create --repo https://github.com/bellra-jin/verith --draft --base develop --head feat/flow-auth-ownership \
    --title 'CF-002: Google OIDC 세션과 Flow 소유권 경계 구현' \
    --body-file backend/docs/cf002_pr_body.md
)
```
