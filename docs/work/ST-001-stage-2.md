# ST-001 v1.1 · 2단계 작업 안내 구현/검증 기록

> 현재 상태 주석 — 2026-11-07T23:51:05+09:00 확인: 사용자 PR #4는 23:28:57 KST
> (`2026-11-07T14:28:57Z`) 병합 완료로 전달됐다. head `9bf536e53ca7dab75d35b43200198c298a54ec0e`,
> merge/develop `6308d8c9517d8d8d4f1c7b69e845fb5fe33836ef`이며 fetch 후 로컬 develop과 일치함을 확인했다.
> 아래 commit/push/PR/병합 대기와 미커밋·고정 HEAD 명령은 당시 이력이다. 현재 재실행 명령이 아니며,
> 기존 검사·실패/미검증·PR 본문·명령은 그대로 보존한다. 새 작업은 [3-A 기록](ST-001-stage-3-A.md)이다.

- 작성: 2026-11-07T22:59:33+09:00 (Asia/Seoul, +09:00).
- 상태: P2 해소·독립 재검토 통과·사용자 직접 commit/push/Draft PR/병합 대기.
- 지시 원본: ST-001_문서_정본과_안전한_개발_기반_정리.md **v1.1 / 2단계**.
  source SHA-256 `9a7d519f8636e6ba127bb66e74c74ff70d84f50b8705814b91916599c2ef97be`를 수신값과 대조했다.
- 운영 문서는 전체 작업 v1.1/지시서 작성 v1.2/코드 개발 v1.2를 다시 읽고 기존 source hash와 일치함을 확인했다.
  기존 frontend AGENTS/CLAUDE와 관련 로컬 지침을 읽었으며 .agents/skills는 없었다.
- 시작 상태: develop/HEAD `083dea8436b699aa3a52ddbf36848e8fe3535720`, staged/unstaged 0, worktree 1, 동명 branch 없음.
  실제 fetch 성공 → develop ff-only 확인(이미 최신) → `docs/repository-work-guide` 생성 순서로 착수했다.
  develop/origin develop/작업 HEAD는 같은 기준 SHA다. 이후 commit/PR merge는 수행하지 않았다.
- 선행 사용자 commit `7aab357ae9e358dc7ab34320e4e5eecc1ae56288`/PR #3이 기준 merge에 포함됨을
  Git 그래프로 확인했고 head→merge 파일 차이 0을 직접 확인했다. mergedAt 22:42:40 KST
  (`2026-11-07T13:42:40Z`)와 closed/merged 상태는 전달된 원격 확인 기록이며 새 API 조회로 바꾸지 않는다.

## 변경 범위

[상위 AGENTS](../../AGENTS.md)에서 [Backend](../../backend/AGENTS.md)·[AI](../../ai/AGENTS.md)·
[Frontend](../../frontend/AGENTS.md)로 연결했다. 실제 entry/config·service/repository·auth/owner·
문서 권위·검사 경로와 위험을 안내한다. 문서용 source 읽기만 했고 config/app을 import하지 않았다.
기존 Next BEGIN/END 블록과 1단계 본문·포트폴리오를 보존한다.

manifest는 기존 work_item 객체를 work_item_history에 원형 보존하고 현재 ST v1.1/2단계/hash/
기준 SHA와 checked_at만 갱신한다. 이미 출판한 CF snapshot bytes/source/publication/hash/
reviewed SHA와 reference_documents는 바꾸지 않는다. 1단계 보고에는 PR #3 병합 주석만 추가했다.

허용/변경 파일은 다음 9개뿐이며 사용자용 명령도 이 기록 안에 둔다.

- [AGENTS.md](../../AGENTS.md)
- [backend/AGENTS.md](../../backend/AGENTS.md)
- [ai/AGENTS.md](../../ai/AGENTS.md)
- [frontend/AGENTS.md](../../frontend/AGENTS.md)
- [README.md](../../README.md)
- [docs/documentation.md](../../docs/documentation.md)
- [docs/contracts/manifest.json](../../docs/contracts/manifest.json)
- [docs/work/ST-001-stage-1.md](../../docs/work/ST-001-stage-1.md)
- [docs/work/ST-001-stage-2.md](../../docs/work/ST-001-stage-2.md)

## 직접 검증과 기존 보고의 구분

이번에는 9개 문서의 현재 링크/anchor·entry/config/검사 경로, Next 블록 bytes, manifest 작업 이력/
source hash와 CF 불변, 허용 범위·runtime diff·개인/비밀 제외·diff check를 임시 표준 라이브러리
도구로 검사한다. 최종 수치/결과는 마지막 자체 검사 절에 기록한다. 영구 검사 script는 추가하지 않는다.

1단계의 path/anchor 210개 독립 검토는 과거 보고 확인이다. 작성 채팅의 현재 tree local path 190개
검사는 anchor/전체 재검사를 제외한 전달 결과다. 두 수치를 이번 2단계 직접 검사로 재사용하지 않는다.
문서 전용이므로 기능/unit/build/type/lint·DB/Google/AI/Docker는 **미실행**이며, 앱 import·서비스
실행·모델 다운로드·migration/seed·기존 데이터 변경·비밀 파일 읽기도 하지 않는다.

현재 Backend autouse fixture가 test module 수집 전에 항상 차단하는 것은 아니고, Frontend 도우미의
지정 디렉터리 재귀 복사가 .env 외 모든 private 자료의 제외를 보장하는 것도 아니다. AI config import/
전체 pytest 역시 dotenv·HTTP/DB/모델 부작용을 일으킬 수 있다. 이 한계와 기존 전체 lint 실패,
실제 인증 미검증·Fundamental SELECT 권한 미확인을 AGENTS/문서 목록에 유지한다.

## 독립 검토와 후속 조건

현재 결과는 독립 검토의 P2 1건을 해소하고 자체 재검증과 독립 재검토를 통과했다. 수용 범위는
2단계 작업 안내·문서·사용자 실행 준비다. 기능/인증/공개 검증이나 ST-001 전체 완료를 선언하지 않는다.
3-A 공용 환경 예제 → 3-B Backend/Frontend 공통 안전 entry → 3-C AI 안전 entry는 미구현이다.
이 단계 사용자 병합 후 최신 develop의 별도 branch에서 시작하며 지금 branch에 누적하지 않는다.
큰 파일/코드 디렉터리 재배치는 비교 판단 전 보류다. 기존 .env·credentials·ignored Compose·
실제 포트·기존 서비스/DB/volume는 보존하며 과거 credential 사용 승인을 승계하지 않는다.

## 사용자 직접 실행 준비

권장 commit: `docs: add repository and service work guides`

Draft PR 제목: **ST-001 2단계: 저장소·서비스 작업 안내와 검사 경계 정리**

다음 PR 본문은 아래 경계 표식 사이의 완성된 텍스트다. PR 생성 시 이 내용만 자기 임시 파일에
추출해 --body-file로 전달하고 정리한다. 이 준비는 실제 git add/commit/push/PR 실행이 아니다.

<!-- ST001_STAGE2_PR_BEGIN -->
처음 작업하는 사람이 실제 entry/config와 문서 정본, 현재 검사 위험을 root와 서비스별 AGENTS에서 찾도록 정리합니다. 앱/DB/권한/환경 동작을 바꾸지 않는 ST-001 v1.1 2단계 문서 변경입니다.

## 변경

- root·Backend·AI AGENTS를 추가하고 Frontend 기존 Next 규칙 블록은 bytes 그대로 유지하며 필요한 App Router/BFF/SSR·사본 검사 안내만 보강합니다.
- 실제 source 경로·auth/owner/root-index·legacy NULL·no-store·공개 save/전체 삭제/직접 AI proxy 차단과 Fundamental 공유 master SELECT 호환/최소 권한 미확인을 명시합니다.
- README/문서 목록에 현재 2단계·AGENTS·미구현 3-A/B/C를 구분합니다. 1단계 보고에는 사용자 PR #3 병합 주석만 붙이고 본문을 보존합니다.
- manifest의 옛 work_item을 work_item_history에 원형 보존합니다. 현재 작업 메타데이터만 v1.1/2단계로 갱신하며 CF snapshot bytes/출처/버전/hash/reviewed SHA·reference_documents는 유지합니다.

## 검증과 제한

- 선행 PR #3 병합 develop 083dea8에서 fetch/ff-only 확인 후 docs/repository-work-guide를 생성했습니다. 허용 9경로만 수정합니다.
- 자체 정적 검사에서 현재 링크/anchor 148개, Next 원문 326 bytes 보존, manifest 이력/source hash와 CF bytes/메타데이터 불변, 허용/실제 변경 9경로·staged 0·범위 밖/runtime diff 0·whitespace가 통과했습니다. 원격 guard 8개·zsh 블록 4개 구문과 PR 본문 추출도 별도로 확인하며 독립 검토와 구분합니다.
- 1단계 210개 독립 검사와 작성 채팅의 path 190개 확인은 과거/전달 근거이며 이번 실행 결과와 구분합니다.
- 문서 전용이라 기능/unit/build/lint·실DB/Google/AI/Docker·앱 import는 하지 않습니다. 기존 lint 실패·실제 인증 미검증·수집 전 보호의 한계는 보존합니다.
- 3-A 환경 예제·3-B/3-C 안전 entry는 미구현 후속입니다. 이 단계 검토/사용자 병합 전 다음 구현을 누적하지 않으며 구조 재배치/큰 파일 분리도 보류합니다. 기존 .env·ignored Compose·자격·서비스/자료를 읽거나 변경하지 않았습니다.

독립 검토에서 다중 원격 URL을 놓치는 P2 1건을 수정하여 모든 fetch/push guard가 --all 전체 목록을 승인된 단일 주소와 비교하도록 했습니다. 자체 재검증과 수정 후 독립 재검토에서 현재 단일 URL은 guard 8개 모두 통과하고, 프로세스 한정으로 추가 URL을 넣으면 8개 모두 거부했습니다. 실제 원격 설정은 전후 동일합니다. 독립 재검토는 통과했으며 잔여 결함은 없습니다. 사용자 직접 commit/push/Draft PR/병합을 기다립니다. 독립 재검토의 PR 본문 추출은 메모리에서 확인했고 실제 임시 파일 정리는 실행하지 않고 코드만 검토했습니다.

수용은 2단계 문서/작업 안내와 사용자 직접 실행 준비에 한정합니다. 전체 기능/인증/공개 완료가 아닙니다. 실제 commit/push/PR/Ready/merge는 사용자가 직접 합니다.
<!-- ST001_STAGE2_PR_END -->

## 사용자 명령 1 · 지정 파일 stage 후 검토

독립 검토/수용 후 저장소의 Terminal(zsh/macOS)에서 블록별로 실행한다. branch/HEAD/실제 fetch·
push URL·기존 staged가 다르면 중단한다. 같은 파일에 새 사용자 편집이 섞였으면 diff를 검토하고
해당 stage를 보류한다. reset/stash/강제 add로 정리하지 않는다. 아래 명령은 실행하지 않았다.

```zsh
(
  set -eu
  cd "$(git rev-parse --show-toplevel)"
  [ "$(git branch --show-current)" = 'docs/repository-work-guide' ] || { printf '%s\n' 'STOP: branch mismatch'; exit 1; }
  [ "$(git remote get-url --all origin)" = 'https://github.com/bellra-jin/verith.git' ] || { printf '%s\n' 'STOP: origin mismatch'; exit 1; }
  [ "$(git remote get-url --push --all origin)" = 'https://github.com/bellra-jin/verith.git' ] || { printf '%s\n' 'STOP: push origin mismatch'; exit 1; }
  [ "$(git rev-parse HEAD)" = '083dea8436b699aa3a52ddbf36848e8fe3535720' ] || { printf '%s\n' 'STOP: base HEAD changed'; exit 1; }
  git diff --cached --quiet -- || { printf '%s\n' 'STOP: existing staged changes'; exit 1; }
  git add -- \
    'AGENTS.md' \
    'backend/AGENTS.md' \
    'ai/AGENTS.md' \
    'frontend/AGENTS.md' \
    'README.md' \
    'docs/documentation.md' \
    'docs/contracts/manifest.json' \
    'docs/work/ST-001-stage-1.md' \
    'docs/work/ST-001-stage-2.md'
  git diff --cached --check
  git diff --cached --stat
)
```

출력과 git diff --cached를 검토한 다음에만 commit한다. 광범위 add -A/force-add는 쓰지 않는다.

## 사용자 명령 2 · 검토한 변경 commit

```zsh
(
  set -eu
  cd "$(git rev-parse --show-toplevel)"
  [ "$(git branch --show-current)" = 'docs/repository-work-guide' ] || { printf '%s\n' 'STOP: branch mismatch'; exit 1; }
  [ "$(git remote get-url --all origin)" = 'https://github.com/bellra-jin/verith.git' ] || { printf '%s\n' 'STOP: origin mismatch'; exit 1; }
  [ "$(git remote get-url --push --all origin)" = 'https://github.com/bellra-jin/verith.git' ] || { printf '%s\n' 'STOP: push origin mismatch'; exit 1; }
  [ "$(git rev-parse HEAD)" = '083dea8436b699aa3a52ddbf36848e8fe3535720' ] || { printf '%s\n' 'STOP: base HEAD changed'; exit 1; }
  python3 - <<'ST001_STAGE2_PATHS'
import subprocess
expected={'docs/work/ST-001-stage-1.md', 'AGENTS.md', 'README.md', 'frontend/AGENTS.md', 'backend/AGENTS.md', 'ai/AGENTS.md', 'docs/documentation.md', 'docs/work/ST-001-stage-2.md', 'docs/contracts/manifest.json'}
actual=set(filter(None,subprocess.check_output(['git','diff','--cached','--name-only','-z']).decode().split('\0')))
if actual!=expected:raise SystemExit('STOP: staged paths differ from ST-001 stage two scope')
ST001_STAGE2_PATHS
  git diff --cached --check
  git commit -m 'docs: add repository and service work guides'
)
```

## 사용자 명령 3 · commit 확인 후 push

git log -1 --stat로 이번 commit인지 확인한다. 준비 이후 원격은 달라질 수 있으며 일반 push 거부 시
차이를 확인한다. force-push/rebase/merge를 임의로 실행하지 않는다.

```zsh
(
  set -eu
  cd "$(git rev-parse --show-toplevel)"
  [ "$(git branch --show-current)" = 'docs/repository-work-guide' ] || { printf '%s\n' 'STOP: branch mismatch'; exit 1; }
  [ "$(git remote get-url --all origin)" = 'https://github.com/bellra-jin/verith.git' ] || { printf '%s\n' 'STOP: origin mismatch'; exit 1; }
  [ "$(git remote get-url --push --all origin)" = 'https://github.com/bellra-jin/verith.git' ] || { printf '%s\n' 'STOP: push origin mismatch'; exit 1; }
  [ "$(git rev-list --count 083dea8436b699aa3a52ddbf36848e8fe3535720..HEAD)" = '1' ] || { printf '%s\n' 'STOP: unexpected commit history'; exit 1; }
  git diff --quiet -- || { printf '%s\n' 'STOP: tracked changes remain'; exit 1; }
  git diff --cached --quiet -- || { printf '%s\n' 'STOP: staged changes remain'; exit 1; }
  git push --set-upstream origin docs/repository-work-guide
)
```

## 사용자 명령 4 · 정확한 저장소의 Draft PR

이 블록은 PR 본문만 신규 임시 파일에 추출하고 종료 때 그 파일을 제거한다. 영구/비밀 설정 파일을
만들지 않는다. gh 인증/동명 PR 문제가 있으면 먼저 확인하며 자격 생성·Ready/merge를 대신하지 않는다.

```zsh
(
  set -eu
  umask 077
  cd "$(git rev-parse --show-toplevel)"
  [ "$(git branch --show-current)" = 'docs/repository-work-guide' ] || { printf '%s\n' 'STOP: branch mismatch'; exit 1; }
  [ "$(git remote get-url --all origin)" = 'https://github.com/bellra-jin/verith.git' ] || { printf '%s\n' 'STOP: origin mismatch'; exit 1; }
  [ "$(git remote get-url --push --all origin)" = 'https://github.com/bellra-jin/verith.git' ] || { printf '%s\n' 'STOP: push origin mismatch'; exit 1; }
  st001_pr_body_file=$(mktemp -t st001-stage2-pr)
  trap 'rm -f -- "$st001_pr_body_file"' EXIT
  python3 - "$st001_pr_body_file" <<'ST001_STAGE2_BODY'
import sys
from pathlib import Path
text=Path('docs/work/ST-001-stage-2.md').read_text()
begin='<!-- ST001_STAGE2_PR_BEGIN -->'
end='<!-- ST001_STAGE2_PR_END -->'
if text.count(begin)!=2 or text.count(end)!=2:
    raise SystemExit('STOP: PR body markers changed')
# The first pair is the PR body; the second occurrence is this extractor's code.
body=text.split(begin,1)[1].split(end,1)[0].strip()+'\n'
Path(sys.argv[1]).write_text(body)
ST001_STAGE2_BODY
  gh pr create --repo https://github.com/bellra-jin/verith --draft \
    --base develop --head docs/repository-work-guide \
    --title 'ST-001 2단계: 저장소·서비스 작업 안내와 검사 경계 정리' \
    --body-file "$st001_pr_body_file"
)
```

## 최종 자체 정적 검사

2026-11-07T23:02:24+09:00 기준. 임시 stdlib 검사기
`/tmp/st001_stage2_check.py`와 zsh -n·git diff --check를 직접 실행했다. 영구 script/검사 entry는
추가하지 않았고, 실행 가능한 기능/서비스를 검사하지 않았다.

| 검사 | 직접 결과 / 범위 |
|---|---|
| 현재 local path/anchor | **148개 통과, 오류 0**. 변경된 Markdown과 1단계 보고의 새 병합 주석만 검사. 과거 1단계 본문과 외부 HTTP 링크 2개는 이번 재검사 범위 아님 |
| Next 원문 | 기존 BEGIN/END 규칙 블록 **326 bytes 동일** |
| manifest | 옛 work_item 원형을 이력에 정확히 1회 보존. 현재/이전 ST source hash 확인. 작업 메타데이터 외 기존 키/객체 불변 |
| CF 계약/reference | snapshot 2개 bytes와 source/pub/hash/reviewed SHA·reference_documents 불변. 과거 reviewed SHA를 현재 SHA로 바꾸지 않음 |
| 본문 보존 | 1단계 원래 본문 및 README 과거 포트폴리오 bytes 보존 |
| 범위/노출 | 허용 9경로=실제 변경 9경로, staged 0, 범위 밖/runtime diff 0. 새 작업 안내의 개인 경로/계정/대화/원시 영수증/승인 제외를 내용·정적 패턴으로 확인 |
| 사용자 명령 | 실제 .git 포함 origin/push 값과 guard 8개 일치. zsh 블록 4개 syntax-only 통과. literal add/commit expected 9경로 일치, 명시 repo/base/head/--draft 확인 |
| whitespace | git diff --check 통과 |

PR 본문 추출은 저장소의 이 문서만 읽고 새 자기 임시 파일에 쓴 결과를 대조한다. git/gh action
블록은 실행하지 않는다. 이는 private 입력/앱 import나 실제 PR 생성 검사가 아니다.
개인/비밀 검사는 명시 범위의 패턴/내용 검토이며 임의 자료 전체의 비밀 탐지 보장은 아니다.
기능/unit/type/build/lint·실제 DB/Google/AI/Docker 검사는 **미실행**으로 유지한다.
1단계의 210개와 작성 채팅의 path 190개는 각각 이전/전달 근거이며 위 148개와 범위가 다르다.
위는 최초 자체 검사 당시의 **독립 검토 대기** 기록이다. 후속 P2 수정/재검증은 아래에 구분한다. 사용자 commit/push/실제 PR/Ready/merge도 실행하지 않았다.

## 독립 검토 P2 수정과 자체 재검증

2026-11-07T23:11:37+09:00 기준. 독립 검토에서 push guard가 첫 URL만 읽어 추가 pushurl을
놓치는 P2 1건이 전달됐다. 현재 실제 origin의 fetch/push는 각각 승인된 단일 URL이며 설정 이상은
없었다. 이 문서의 현재 단계 명령/보고만 수정했다. push guard 4개는
`git remote get-url --push --all origin`, fetch guard 4개는 `git remote get-url --all origin`의
전체 출력을 `https://github.com/bellra-jin/verith.git` 한 줄과 정확히 비교한다.

직접 재검증 결과는 다음과 같다.

- 문서에서 추출한 guard 8개는 현재 단일 URL에서 모두 통과했다. `git -c`로 프로세스에만 추가
  fetch/push URL을 주면 8개 모두 거부했다. 기존 첫 URL 조회가 추가 pushurl을 놓치는 현상도
  읽기 전용으로 재현했다. 실제 원격 설정의 검사 전후 값은 같고 네트워크/push는 실행하지 않았다.
- 임시 검사기 `/tmp/st001_stage2_check_p2.py`로 local path/anchor 148개, Next 블록 326 bytes,
  manifest 이력/source hash·CF snapshot bytes/메타데이터·reference_documents 불변,
  1단계 본문/포트폴리오 보존을 다시 확인했다. 허용/실제 9경로, staged 0, 범위 밖/runtime diff 0이다.
- zsh 4개 블록은 syntax-only, 내장 Python 2개는 구문 검사를 통과했다. 명시 repo/base/head/--draft,
  literal add/commit expected 9경로와 PR 본문 추출 구조도 다시 확인했다. git diff --check가 통과했다.
- 이번 수정 전후 나머지 8개 작업 파일과 과거 1단계 명령 파일의 해시가 같다. 원격 설정·계약·
  snapshot·manifest·과거 명령은 이번 결함 수정으로 바꾸지 않았다.

전달받은 최초 독립 검토에서도 링크 148개·보존/해시·9경로·runtime 0·명령 구문 등 나머지 검사는
통과했다. 그 결과와 위 직접 재검증을 구분한다. **이 자체 재검증 시점에는 수정 후 독립 재검토 대기**였으며,
이후 전달된 독립 재검토 통과 결과는 아래 마감 기록으로 구분한다.
독립 검토의 PR 본문 메모리 추출 2484 bytes는 수정 전 시점의 결과다. 당시 검토자는 실제 임시 파일
생성/정리를 실행하지 않고 trap을 문구로 검토했으며, 이를 이번 수정 후 실행 결과로 쓰지 않는다.
기능/서비스/DB/Google/AI/Docker·비밀 읽기와 실제 add/commit/push/PR/Ready/merge는 미실행이다.
수용 범위는 ST-001 v1.1 2단계 문서와 사용자 직접 실행 준비이며 전체 ST-001 완료가 아니다.

## 독립 재검토 통과와 마감

2026-11-07T23:14:13+09:00에 전달받은 독립 재검토 통과 결과를 반영했다. P2는 해소됐으며 잔여 결함은 없다.
독립 검토자는 URL guard 8개의 정상 단일 URL 통과·추가 URL 거부와 실제 원격 설정 전후 동일,
local path/anchor 148개, zsh 4블록·내장 Python 2개 구문, Next 326 bytes·README 역사·1단계 본문 보존,
manifest 이력/정본 hash·CF bytes/hash/metadata/reference 보존, 허용 9경로·staged 0·범위 밖/runtime 0·
diff check 통과를 직접 확인했다. PR 본문은 메모리 추출로 확인했으며 실제 임시 파일 정리는 실행하지 않고
코드만 검토했다. 이는 전달받은 독립 재검토 결과이며 이번 마감에서 전체 검사를 새로 실행한 기록이 아니다.

이번 마감의 직접 검증은 변경한 보고서의 링크·PR 본문 추출/markers·현재/이력 문구와 git diff --check다.
기존 명령 4블록과 다른 작업 파일은 보존했다. 사용자 직접 commit/push/Draft PR/병합 대기이며,
실제 add/commit/push/PR/Ready/merge는 실행하지 않았다. 수용은 2단계 문서/작업 안내/사용자 실행 준비에
한정하며 서비스/기능/실DB/Google/AI 검증이나 3단계 완료가 아니다. 사용자 병합 후 3-A→3-B→3-C,
구조 재배치 보류 조건은 유지한다.
