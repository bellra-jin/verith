# CF-006 · Flow 합성 입력 snapshot 준비 결과

CF-006 v1.2의 내부 합성 입력 봉인·실제 principal/owner 재조회 범위를 구현했다. 최종 보호 self **18/18**, unit **16파일 851/851**, unexpected skip/guard 0·exit 0 및 자기 임시 root 제거를 확인했다. 실제 owned PostgreSQL은 세 번째 실행에서 CF-006 **9묶음·내부/SQL 거부 55건**, CF-003 **8묶음·제약 거부 26건**, 별도 fresh PG의 downgrade 선행 검사까지 exit 0으로 통과했다. 독립 검토는 source-only 수용이며 runtime 재실행이 아니다.

공개 API·ErrorCode/schema/payload digest·receipt_only/pending/not_stored·기존 계산/Gate는 불변이다. snapshot은 실행권/예산 예약/결과가 아니다. 이번 범위에서 사용자 자격과 실제 외부 AI/KIS/Google 호출을 사용하지 않았다. 실제 Google·브라우저/BFF·AI·worker/claim/attempt 실행·결과 snapshot/리포트 저장/게시·운영 DB·장기 purge는 미검증/미구현 후속이다.

## 기준·변경 범위

- 정본: CF-006 v1.2, SHA-256 `2e77ab3e8ec98950c8842508a4ca50689c2df973e755ae82734f3aacd4c0a786`. 읽기 준비 v1.1 SHA `8fcd03b83814ed5c40a6d0b08b277703887b72c4d91273ba5fbf240b1c1fb864`와 보존본/diff를 대조한 뒤 착수했다. 외부 정본/이력은 수정하지 않았다.
- base/HEAD: `5c980528c01991cd3e71fb8d4eab448c56c90f0c`, branch `feat/flow-input-snapshot`, PR #9 merged. merge parents `a6f27aa53c376bbfc5c3e8679aa50c9c02869518` / `4b91629616edf23b09ff59cdacbc7c04e5a2c30f`.
- 착수 시 clean develop/worktree1·origin 전체 fetch/push `https://github.com/bellra-jin/verith.git` 확인 → fetch → ff-only Already up to date → 동명 branch 없음 확인 후 전용 branch 생성. 강제 정리·기존 변경 덮어쓰기·publishing 없음.
- 허용 19개 중 실제 변경 19개: code/test/entry 13 + 안내/결과 6. 정확한 집합은 아래 manifest/pathspec과 대조한다.

## 구현과 보존

새 domain은 고정 fixture 두 종류와 strict canonical UTF-8 TEXT/hash·독립 v1 reader·고정 내부 오류를 제공한다. 초기 generator 공유 검증 문제를 고쳐 catalog/SPEC/_data 변경 후에도 기존 bytes/read/get가 유효하다. 숫자/false/null/누락·중복 키·비유한 값·문자열/128KiB 경계를 검사한다. 실제 asyncpg UUID subtype은 UUID로 수용하고 임의 문자열 인자는 거부한다.

service는 DB principal 재검증/세션 SHARE → owner run FOR UPDATE → exact run UNIQUE INSERT/별도 winner SELECT → 봉인/receipt 관계 대조 → commit 확인 후 반환 순서다. 동일 내용은 최초 ID/시각/bytes를 재사용하고 다른 내용·source drift는 덮어쓰지 않는다. commit 전/확정 rollback은 잔여0, DB commit 후 ACK/응답 유실은 최초 봉인본 조회/replay로 확인한다. 반환 body 변조는 다음 조회에 영향을 주지 않는다.

새 c6001 migration은 parent UNIQUE/composite owner FK·RESTRICT·필수 열/CHECK·UPDATE/DELETE 거부 trigger를 추가한다. 기존 pgcrypto를 사용하며 기존 receipt/auth/report/index/stock 값을 rewrite하지 않는다. parent→snapshot ACCESS EXCLUSIVE 순서와 nonempty downgrade 거부를 유지한다. 관리자 ALTER/DROP/TRUNCATE나 일반 purge를 막는 권한 격리가 아니다.

CF003 `_verify`·migration·owned HOME·isolated_application 및 기존 formatter/owned_session 본문은 보존했다. CF003의 c3001/run0/user0 검사를 CF006 자체 사용자/snapshot 전에 그대로 실행하고 c6001로 복귀한다. 보호 입구는 exact 신규 source7개·고정 unit1개·선택 경계 회귀만 추가했다. 기존 hash pin/수집 전 보호/plugin/FS/OS/network/bootstrap·helper는 확대하지 않았다. `runner_owned_database.py` SHA는 `6ad32139269c0526b6737a4501c9f7e9b807a68a928f9c1f1e1df6559ec626d8`로 불변이다.

새 실패 출력은 실제 실패 자원의 resource_id/container_id/created_at만 허용한다. 원문/locals/SQL/DSN/nonce를 넣지 않는다. 기존 성공 영수증과 formatter는 유지한다. 둘째 자원 cleanup 실패는 outer finally까지 전파해 exit2이며 양 owner의 cleanup을 시도한다.

## 직접 보호 검사와 수정 이력

아래 공식 workload는 repo cwd에서 각각 `require_escalated`로 실행했다. 기존 보호를 해제하거나 raw pytest로 대체하지 않았다. 실행일은 2026-11-08이며 각 self/unit 시작·끝의 정확한 wall-clock은 별도 capture하지 않았다.

```sh
/usr/bin/env -i LANG=en_US.UTF-8 TZ=UTC /Users/parkjinhee/AI/verith_refactor/verith/backend/.venv/bin/python -I -S backend/scripts/check_safe.py self-test
/usr/bin/env -i LANG=en_US.UTF-8 TZ=UTC /Users/parkjinhee/AI/verith_refactor/verith/backend/.venv/bin/python -I -S backend/scripts/check_safe.py unit
```

| 시점 | 실제 결과 | 후속 |
|---|---|---|
| 최초 self | 18/18·exit0·root 제거 | 기존 선택/보호와 새 exact 입력 확인 |
| 최초 unit | 846 수집/845 pass/1 fail·guard0·controller78·root 제거 | CF003 HOME 분기를 OR로 합쳐 기존 AST 순서 회귀 실패. 기존 테스트를 고치지 않고 old 분기를 보존하고 CF006 분기를 별도 추가 |
| 보완 unit | 846/846·guard0·exit0·root 제거 | 최초 service/domain 회귀 통과 |
| cleanup 회귀 추가 | 848 수집/846 pass/2 fail·guard0·controller78·root 제거 | 선택 수집은 완료됐으나 두 시험 실행 중 사본 밖 workspace helper import 실패. copy 허용을 넓히지 않고 고정 main AST만 합성 추출 |
| 보완 unit | 848/848·guard0·exit0·root 제거 | Docker/PG를 시작하지 않는 cleanup 제어 회귀 |
| UUID 보완 unit | 849/849·guard0·exit0·root 제거 | 실제 asyncpg UUID subtype 합성 검사 |
| 최종 self / unit | 18/18 / 851/851(16파일)·skip0·guard0·exit0·각 root 제거 | 실패 check×cleanup 4조합·정확 둘째 CID·allowlist/비노출·exit1/2 포함 |

최종 unit에는 원래 전체 선택 795개와 새 56개가 포함된다. domain/helper 동작·mock service·실제 main 함수의 제한된 AST 합성 실행은 unit 증거다. wiring/SQL/잠금 순서의 source assertion과 실제 PG에서의 실행은 구분한다. 기존 공개 snapshot digest 검사는 그대로 통과했다.

## 실제 owned PostgreSQL 실행·실패·정리

기존 Python 3.12.13 `isolated=1/no_site=1/no_bytecode=true`, clean env, exact `backend/.venv/lib/python3.12/site-packages`와 기존 DB-only mode를 사용했다. 기존 local Docker/허용 image·receipt·readonly preflight·동일 연결 attestation/migration·자기 HOME·외부/dotenv 차단과 finally cleanup을 유지했다. 다운로드/설치·기존 DB/volume 채택 없음. Python wrapper의 observed denial0은 native 전체 I/O tracing이 아니다.

- **PG1, exit1:** `owned_creation`의 start 후 기존 verify_metadata에서 실패했다. migration/새 검사는 미실행. 세부 predicate는 미확정이며 해결됐다고 주장하지 않는다. resource `CF-002-login-942ca8ae2c66` 제거 보고 후 exact label 잔여0을 별도 확인했다. create 반환 전 실패로 최초 CID는 capture되지 않았다.
- **PG2, exit1:** CID `eacf43b28c6953f59905d55c7d0741309cb60576796e249764559ba1f49a96ec`, resource `CF-002-login-6666e9312a23`, 생성 `2026-11-08T07:53:10.447008378Z`. 생성·동일 연결 migration·CF003 회귀·CF006 DDL/왕복은 통과했으나 첫 봉인 barrier에서 TimeoutError. 당시 내부 task 원인은 capture되지 않았다. asyncpg UUID subtype 및 task 실패를 timeout으로 덮는 문제를 source/회귀로 보완했고 이후 PG3가 통과했다. 이 성공을 첫 metadata 실패의 원인 증명으로 쓰지 않는다. exact CID 부재/label0 별도 확인.
- **PG3, exit0:** 시작 runtime capture `2026-11-08T07:56:09.369416+00:00`(16:56:09 KST), 종료 정확 시각 미수집. 아래 두 자원은 생성시각이며 명령 시작/끝 시각과 다르다.

| 목적 | CID | resource | 생성시각 UTC |
|---|---|---|---|
| CF003 회귀+CF006 봉인/제약/경합 | `494ea79dd08e01143c82fd1dd57c1f2c8742b5da6e1c9224935a88b8b6f51da7` | `CF-002-login-da164b327913` | `2026-11-08T07:56:09.608568419Z` |
| 별도 downgrade-lock-first | `5bf56725c5a124347872e063c4f3fe240ba4b20f6884cd398bfeba3b4df94882` | `CF-002-login-124add3617fb` | `2026-11-08T07:56:34.691582833Z` |

PG3는 CF006 9묶음·내부/SQL 거부55, CF003 8묶음·제약26, 별도 lock-first 1묶음을 통과했다. 실제 별도 attested 연결과 DB lock wait/barrier로 같은/다른 준비 경쟁, 세션 revoke 양순서, 첫 snapshot0→1 후 downgrade 거부, downgrade 선행 시 늦은 prepare 고정 실패/테이블 재생성0을 확인했다. CREATE 후 전용 hook 예외·기존 receipt 포함 rollback/upgrade/빈 왕복, composite FK/UNIQUE/NOT NULL/CHECK/immutable trigger, ACK 유실 원본 replay와 source drift fail-closed를 실행했다. 양 자원 제거 보고와 exact 두 CID absence=true/각 label0을 별도 읽기 확인했다.

대기 요청의 일시적인 `aborted before dispatch`를 명령 미실행으로 해석한 중간 보고는 정정한다. 기존 cell/session 완료 결과와 로그를 재조회해 실제 PG3 **completed/exit0**을 확인했다. 재확인 전 새 실행은 요청하지 않았다. **PG4 실행은 없다.** 준비해 둔 source metadata는 `post-review-source.json`으로 구분했다.

성공 PG3 source와 최종 source 차이는 entry의 실패 출력과 새 unit 두 파일뿐이다. 제품/domain/service/repo/ORM/migration/checker는 동일하다. 마지막 delta는 self18/unit851 및 독립 source-only 재검토로 확인했고, 영향 없는 PG를 반복하지 않았다. 최종 source를 통째로 PG3 당시 bytes였다고 재기록하지 않는다.

PG3 실제 launcher(repo cwd, nonce redaction 및 pipefail 포함):

```sh
set -o pipefail
/usr/bin/env -i PATH=/usr/local/bin:/usr/bin:/bin LANG=en_US.UTF-8 TZ=UTC PYTHONDONTWRITEBYTECODE=1 /Users/parkjinhee/AI/verith_refactor/verith/backend/.venv/bin/python -I -S -B -c 'import sys,runpy,json; from pathlib import Path; from datetime import datetime,UTC; root=Path.cwd(); site=root/"backend/.venv/lib/python3.12/site-packages"; assert site.is_dir(); sys.path[:0]=[str(root/"backend"),str(site)]; sys.argv=[str(root/"backend/scripts/cf002_interactive_login.py"),"--verify-flow-input-snapshot-db"]; print("CF006_RUNTIME "+json.dumps({"started_at":datetime.now(UTC).isoformat(),"python":sys.version.split()[0],"isolated":sys.flags.isolated,"no_site":sys.flags.no_site,"no_bytecode":sys.dont_write_bytecode}),flush=True); runpy.run_path(sys.argv[0],run_name="__main__")' | /usr/bin/sed -l -E 's/"nonce": "[^"]+"/"nonce": "[redacted]"/g' | /usr/bin/tee /var/folders/d7/v1s6ddq12y9fftsqrvrgcz140000gn/T/cf006-baseline-4ou60jz6/pg-attempt-3.log
```

재실행 지시가 아닌 실행 이력이다. 이 로그만으로 source 불변이나 exit를 추정하지 않았다. tool 완료 exit0과 별도 source 비교·CID 부재 대조를 사용했다.

## 독립 검토와 잔여 한계

독립 source-only 검토에서 generator 독립성, 유효 JSON 크기 CHECK 입력, 기존 receipt 보존 증거, 전용 DDL hook, 첫 봉인 경합, secondary cleanup exit2, UUID subtype, task 실패 전파, 실패 출력 allowlist/실제 owner 선택을 검토·수정·재검토했다. 최종 추가 필수 결함 없음으로 수용했다. 검토자는 파일 수정·앱/테스트/DB/Docker를 실행하지 않았다. 실행 결과 확인과 source 검토를 독립 runtime 재실행으로 확대하지 않는다.

snapshot SHA는 내용 식별/손상 검출용이며 진실성/인증/실행권 증명이 아니다. 긴급 purge·실사용자 삭제/보존 정책은 후속이며 관리자를 막는 보안 격리는 아니다. 다음 fake-only 실행은 별도의 명시 전환·기한/제한·attempt/claim/fence를 계약해야 한다. 이번에는 결과 생성·저장·게시·삭제를 추가하지 않았다.

## 최종 코드 SHA-256

| 경로 | SHA-256 |
|---|---|
| `backend/src/modules/flow/domain/input_snapshot.py` | `b296f8eec443abf1431aa76d1c173e35643f35021010042dda1f1479f3c28c7c` |
| `backend/src/modules/flow/application/input_preparation_service.py` | `187b12051fd60c903ee879d6744f1e06f29953f7a84f2d24466506c45f8853bd` |
| `backend/src/modules/flow/infrastructure/input_snapshot_repository.py` | `185c6cbba13d8843fa7b3ffb4c214f69652d0c3a05569bd0bb070ab7ebe334bc` |
| `backend/db/models/flow/input_snapshot.py` | `c607ced65a23d392b2a6521f0c629504872a4a63c52db3aab990673fbe04470f` |
| `backend/db/models/flow/flow_run.py` | `401ee7b331df1b3ccbf41538f31c3c6497f82bc7f1490fc69388d51362f49970` |
| `backend/db/models/registry.py` | `05b9b3410dfee2b5231c5a5d1f61967d683b00fca19645e7689be035a933f11e` |
| `backend/db/migrations/versions/20261108_c6001a7e0001_flow_input_snapshots.py` | `e3dcdd2e2243de72dad2c8850958fbc38817f8ad25d5b9f58ba6779e24f654e4` |
| `backend/tests/unit/test_cf006_flow_input_snapshot.py` | `f8a6fd083c465a21aa263bc0093477ed343646245190e980963b2610abe76a44` |
| `backend/scripts/check_safe.py` | `d13c56cf737f016e65a5e7abc5d6d5d2e9c7d7c683483766eea5883c5f6eb85a` |
| `backend/tests/safe_checks/test_entry.py` | `53d869f4d7e467474b118d2bc462c6eedc5c041258321440e72b96b4015b000f` |
| `backend/scripts/cf006_input_snapshot_check.py` | `c8d986ae7eaed8aae5a46deb510bce8187b3f88c9c63d1d29f7d72402cee3d91` |
| `backend/scripts/cf002_interactive_login.py` | `3d7b8b124afa9f108f7bfd7eec41f2866b3be75a8ec867dd4025721664d66d8d` |
| `backend/scripts/cf003_admission_check.py` | `d32363c5e0d216da4f9f16f0e87324d3d5e8a6c00a35c051910a0544923213e7` |

## 정확한 인계 자료와 사용자 Git 작업

checkpoint: `/var/folders/d7/v1s6ddq12y9fftsqrvrgcz140000gn/T/cf006-baseline-4ou60jz6`.

- `scope.json`/`baseline.json`: 정확19경로/시작 보존본.
- `pg-attempt-{1,2,3}-source.json`·동명 log: 각 실제 실행 시점 source와 redacted 출력. PG3 log SHA `6f6c0c4e5e1413fd3db0858578050f752bcee0db1c5c568dca3b601ad1888f47`.
- `final-source.json`: 최종19파일 SHA/크기·기준 branch/HEAD/정본 버전과 hash. 문서 자신을 포함하므로 manifest 자체 hash를 문서에 순환 포함하지 않는다.
- `stage-pathspec.nul`: 검토한19경로만 `:(literal)`·NUL로 나열.
- `review-pr-body.md`: 아래 단일 marker 본문과 동일.
- `reviewguard.py`: 이 branch/HEAD/origin/staged 상태·정확 pathset·regular single-link/no-symlink·무시 여부·현재 bytes를 읽기 전용으로 대조. `--staged`는 stage 후 index bytes도 확인한다. 상태/내용이 바뀌면 다시 검토해야 한다.

검토 19경로:

- `backend/src/modules/flow/domain/input_snapshot.py`
- `backend/src/modules/flow/application/input_preparation_service.py`
- `backend/src/modules/flow/infrastructure/input_snapshot_repository.py`
- `backend/db/models/flow/input_snapshot.py`
- `backend/db/models/flow/flow_run.py`
- `backend/db/models/registry.py`
- `backend/db/migrations/versions/20261108_c6001a7e0001_flow_input_snapshots.py`
- `backend/tests/unit/test_cf006_flow_input_snapshot.py`
- `backend/scripts/check_safe.py`
- `backend/tests/safe_checks/test_entry.py`
- `backend/scripts/cf006_input_snapshot_check.py`
- `backend/scripts/cf002_interactive_login.py`
- `backend/scripts/cf003_admission_check.py`
- `backend/docs/flow_input_snapshot.md`
- `backend/docs/schema.md`
- `backend/docs/migrations.md`
- `docs/development.md`
- `docs/documentation.md`
- `docs/work/CF-006-flow-input-snapshot.md`

아래 명령은 **사용자 실행용**이다. 실제 stage/commit/push/PR/Ready/merge는 수행하지 않았다. raw `git add .`를 권하지 않는다. 먼저 diff·전체 경로·기밀/무관 변경을 검토하고 reviewguard가 통과한 현재 bytes만 stage한다. 명령 사이 상태가 바뀌면 중단하고 다시 대조한다.

```sh
cd /Users/parkjinhee/AI/verith_refactor/verith
/usr/bin/python3 -I -S -B /var/folders/d7/v1s6ddq12y9fftsqrvrgcz140000gn/T/cf006-baseline-4ou60jz6/reviewguard.py
git diff --check
git diff --stat
git diff -- backend/db/models/flow/flow_run.py backend/db/models/registry.py backend/scripts/cf002_interactive_login.py backend/scripts/cf003_admission_check.py backend/scripts/check_safe.py backend/tests/safe_checks/test_entry.py
# 신규 파일도 final-source.json의 정확 목록을 열어 검토한다.
git add --pathspec-from-file=/var/folders/d7/v1s6ddq12y9fftsqrvrgcz140000gn/T/cf006-baseline-4ou60jz6/stage-pathspec.nul --pathspec-file-nul
/usr/bin/python3 -I -S -B /var/folders/d7/v1s6ddq12y9fftsqrvrgcz140000gn/T/cf006-baseline-4ou60jz6/reviewguard.py --staged
git diff --cached --check
git diff --cached --stat
git commit -m "feat(flow): seal synthetic input snapshots with owner verification"
git push -u origin feat/flow-input-snapshot
gh pr create --repo bellra-jin/verith --base develop --head feat/flow-input-snapshot --draft --title "feat(flow): seal synthetic input snapshots" --body-file /var/folders/d7/v1s6ddq12y9fftsqrvrgcz140000gn/T/cf006-baseline-4ou60jz6/review-pr-body.md
```

PR 본문을 다시 추출할 경우(repo/Git 변경 없이 exact 임시 body만 갱신):

```sh
/usr/bin/python3 -I -S -B - <<'BODY'
from pathlib import Path
source = Path('docs/work/CF-006-flow-input-snapshot.md').read_text()
start, end = '<!-- CF006_' + 'PR_BODY_START -->', '<!-- CF006_' + 'PR_BODY_END -->'
assert source.count(start) == source.count(end) == 1
body = source.split(start, 1)[1].split(end, 1)[0].strip() + '\n'
Path('/var/folders/d7/v1s6ddq12y9fftsqrvrgcz140000gn/T/cf006-baseline-4ou60jz6/review-pr-body.md').write_text(body)
BODY
```

<!-- CF006_PR_BODY_START -->
Flow receipt에는 선택자만 있어 후속 실행이 입력 자료를 고정할 수 없었습니다. 내부 준비 service가 서버 합성 자료·비실행 사양을 한 번 봉인하고 실제 principal/owner로 재조회하도록 추가합니다. 공개 API와 receipt_only 상태는 유지합니다.

- canonical UTF-8 TEXT/hash, run당 한 봉인본, composite owner FK, immutable trigger, 원자 replay·source drift 거부를 추가했습니다. commit 불명확 시 최초 봉인본 조회/replay로 복구합니다.
- 보호 self18/unit851 통과·skip/guard0·root 정리. 실제 owned PG에서 CF006 9묶음/거부55·기존 CF003 8묶음/제약26·별도 downgrade 선행 검사가 exit0이며 정확한 자원 부재를 확인했습니다.
- 초기 metadata 실패·barrier timeout과 수정, 최종 실패 출력/unit delta의 영향 검증은 작업 기록에 분리했습니다. 독립 검토는 source-only입니다.
- 실제 AI/Google/브라우저·worker 실행·결과 저장/게시·운영 DB는 범위 밖입니다. snapshot은 실행권/예약이 아니며 관리자 DDL/장기 purge 정책을 제공하지 않습니다.

Base `develop` / head `feat/flow-input-snapshot`, 구현 기준 `5c980528c01991cd3e71fb8d4eab448c56c90f0c`입니다. 상세 근거: `docs/work/CF-006-flow-input-snapshot.md`.
<!-- CF006_PR_BODY_END -->
