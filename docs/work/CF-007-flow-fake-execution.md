# CF-007 · Flow fake 일회 실행과 결과 저장

봉인된 합성 입력에 strict opt-in한 실제 owner의 **일회 fake 실행→내부 결과 원자 저장→본인 재조회**를 구현했다. 보호 self **19/19**, 선택 unit **17파일 893/893** 통과·skip/guard0·exit0·각 owned root 제거를 확인했다. 실제 새 owned PG 재검증은 **9묶음·거부64·exit0**, 엔진 호출12/서로 다른 execution ID12/ID당 최대1, 정확 CID 부재/label0까지 확인했다. 최초 PG 실패는 별도 이력이며 원인은 미확정이다. 독립 최종 검토는 source-only 수용으로 runtime 재실행이 아니다.

이번 범위에서 사용자 키·실제 외부 KIS/AI/Google 호출을 사용하지 않았다. 공개 HTTP/BFF/UI·기존 보관함 게시/삭제·실제 Google/브라우저·운영 DB·일반 worker/실비 budget·실제 시장 데이터는 범위 밖이다. 기존 receipt는 계속 receipt_only/pending/not_stored, preparation executable=false다.

## 기준과 변경

- 정본 CF-007 v1.0 SHA-256 `08b15c5dfdc627bc01556183e3546b1643003ddaf4bc52385cf47dc172e439db` 전체를 읽고 대조했다. 외부 정본·공유 계약·과거 기록은 수정하지 않았다.
- base/착수 HEAD `70d49b3eacccabd1db7bf2ea53cf678102f81bc7`(CF-006 PR #10). branch `feat/flow-fake-execution`. 직전 병합 준비의 fetch/ff-only를 재사용하고 착수 시 clean develop/origin 일치·worktree1·전체 origin fetch/push 단일 `https://github.com/bellra-jin/verith.git`·동명 branch 없음만 확인한 뒤 branch를 만들었다. 새 작업의 검사를 과거 통과 결과로 대체하지 않았다.
- 실제 변경 exact17파일(code/test/entry11 + 안내/결과6). 기존 변경 덮어쓰기/reset/clean/stash·실제 stage/commit/push/PR/merge 없음.

새 `flow_fake_executions` 한 테이블에 별도 일회권과 내부 artifact를 둔다. run/owner는 execution→snapshot→run JOIN, 실제 principal/session 재검증으로 결정한다. bool True만 받으며 최초 grant commit을 확인한 승자만 메모리 claim token으로 고정 coroutine을 호출한다. DB에는 digest만, 반환 view에는 token/digest가 없다. 재요청·loser·다른 본인 세션·실패/timeout 이후 모두 엔진 재호출0이다. crash나 grant ACK 유실 때 호출0일 수 있어 exactly-once 완료를 약속하지 않는다.

claim/terminal/get은 세션 SHARE→owner run FOR UPDATE→입력 검증→execution FOR UPDATE 순서다. fake 동안 DB 잠금/transaction은 없다. DB clock 한 샘플의10초 deadline과 coroutine1초 한도, 기한 전 후보 CAS/기한 뒤 결과없는 timed_out CAS를 나눈다. 결과/상태/hash/종료시각은 한 commit이다. strict canonical/입력ID/hash/reference/ticker/as_of/단위·행수 검증과 독립 반환 사본을 사용한다. 현재 engine binding을 조회에서 다시 호출하지 않는다.

고정 full20/short4는 봉인 달력 행의 수량·거래대금 합계와 synthetic 안내만 만든다. 실제20거래일·시장 수급·Gate/투자 판단·Flow payload v1/report ID로 바꾸지 않는다. 기존 prepare/report service의 자체 commit을 새 transaction 안에서 중첩 호출하지 않는다.

c7001(parent c6001)은 새 테이블·제약·전용 trigger만 추가한다. INSERT running만, identity 불변, running→terminal1회, terminal no-op/DELETE 거부, DB 현재 deadline 검증을 둔다. downgrade는 run→input→execution ACCESS EXCLUSIVE 후 모든 상태 행이 하나라도 있으면 거부한다. 관리자 DDL/TRUNCATE·장기 purge 정책은 별도다. 기존 CF003/006 mode는 caller에서 c6001을 선택하고 checker 본문·revision 허용을 변경하지 않았다.

## 필요한 최종 회차와 실패 후 한정 재검증

실행일 2026-11-08 KST. self/unit 정확 시작·끝 시각은 별도 capture하지 않았다. 공식 `require_escalated`로 다음을 각1회 실행했다.

```sh
/usr/bin/env -i LANG=en_US.UTF-8 TZ=UTC /Users/parkjinhee/AI/verith_refactor/verith/backend/.venv/bin/python -I -S backend/scripts/check_safe.py self-test
/usr/bin/env -i LANG=en_US.UTF-8 TZ=UTC /Users/parkjinhee/AI/verith_refactor/verith/backend/.venv/bin/python -I -S backend/scripts/check_safe.py unit
```

- self19/19, unit893/893(기존851+신규42, 선택17파일), collection error/skip/unexpected guard0·exit0·각 owned root 제거.
- full20/short4 pure engine·strict opt-in/JSON·mock service의 commit/호출 제어·SQL/source 회귀는 unit 증거다. 실제 PG/세션/lock/ACK 결과와 구분한다.
- 수집 전 보호·고정 기존 선택/원공개 digest·plugin/환경·FS/OS/network·기존 hash/origin·bootstrap은 유지했다. raw pytest/새 일반 runner·Frontend/AI 전체 검사는 사용하지 않았다.

### 첫 실제 PG 회차 — 실패 보존

`pg-round-1.log`: 시작 `2026-11-08T08:55:39.800194+00:00`(17:55:39 KST), exit1. 새 resource `CF-002-login-7c0dbb6d3e38`, CID `c2bc1b3edceab5b61b1f315ad4b4258a37417bd2d540b19f4a8c417227261159`, 생성 `2026-11-08T08:55:42.104269458Z`.

소유 생성·readonly preflight·동일 연결 head migration은 통과했고 migration_preservation 시작 뒤 고정 진단 other로 중단됐다. 세부 predicate/예외는 미확정이다. fake 결과 성공으로 쓰지 않는다. runner 제거 보고 후 exact CID absence=true·해당 label 잔여0을 별도 읽기 확인했다. 생성시각은 명령 시작/끝 시각이 아니다.

원문·locals·DSN·token·nonce 출력이나 조건 완화 없이 **새 checker의 고정 phase9줄만** 추가해 해당 구간을 구분했다. 그9줄을 역제거하면 최초 checker SHA가 정확히 복원되며 다른 capture source는 모두 동일했다(`fixed-phase-delta.json`). 제품/기한/제약/선택 의미는 바꾸지 않았다. 통과한 self/unit은 반복하지 않고 실패한 PG에 한정해 재검증했다.

### 한정 진단/재검증 — 실제 수직 경로 통과

`pg-diagnostic.log`: 시작 `2026-11-08T08:59:30.368337+00:00`(17:59:30 KST), exit0. resource `CF-002-login-925eace6ea48`, CID `656b724fc4412d41764b2c223113d76f5593755b7ff8088bfb024fc220e7836b`, 생성 `2026-11-08T08:59:30.604422842Z`. 정확 명령 종료 wall-clock은 별도 미수집이다.

| 실제 PG 묶음 | 확인 |
|---|---|
| migration/보존 | fresh c7, c6 실제 receipt·봉인 input·auth·owner/NULL legacy report/index/stock을 둔 upgrade, empty grant 왕복, 새 CREATE 직후 전용 DDL 실패 rollback |
| 일회권/만료 | running 및 timed_out nonempty downgrade 거부, late candidate 폐기, crash grant takeover0 |
| 수직 경로 | 실제 합성 session cookie/CSRF/Origin ASGI POST→내부 prepare→full20/short4 fake→원자 저장→별도 attested owner get, 수치·단위/ID/hash/사본 보존, 공개 receipt pending 그대로 |
| 권한/전제 | 실제 A/B·만료/폐기/위조 principal·없는/미준비/손상 입력·strict opt-in, 호출/쓰기0 |
| 경쟁 | 두 별도 attested 연결을 run lock/barrier로 경쟁, 한 grant/ID·최대1회 엔진·다른 본인 session replay0 |
| 실패/ACK | grant/terminal의 확정 rollback vs 실제 commit 뒤 ACK 유실, 엔진 예외/잘못된 결과/1초 timeout, 결과/상태 대조와 재호출0 |
| 세션 순서 | grant 및 terminal/revoke 양순서의 실제 SHARE/UPDATE lock wait·폐기 후 저장/조회 거부 |
| 물리 제약 | wrong fence·identity/DELETE/terminal no-op, FK/NOT NULL/CHECK·정상 body/hash를 사용하는 상태 조합14case, DB deadline 뒤 성공 거부·owner 만료 확정 |
| 범위 보존 | 기존 input bytes/hash·receipt 상태·report/index/stock 불변, engine 계측 max1, scoped 관측 거부0 |

합계 **9묶음·거부64**, engine 호출12/서로 다른 execution ID12/ID당 최대1이다. 12는 서로 다른 시험용 run의 합계이며 같은 실행을12회 재시도한 것이 아니다. 실제 provider 호출0이다. Python file/socket/httpx/dotenv wrapper 관측0은 native 전체 I/O tracing이 아니다. 기존 CF003/006 전체 PG checker를 중첩하지 않았다.

Python3.12.13 isolated1/no_site1/no_bytecode=true·exact기존 site-packages를 사용했다. 기존 local Docker의 `--pull=never`·소유증명·readonly preflight·제한 role·동일 연결 attestation/migration·자기 HOME·finally cleanup을 유지했다. 새 설치/기존 DB·volume 채택 없음. runner 제거 후 exact 성공 CID absence=true·label0을 별도 확인했다. Docker 자체/기존 image는 보존했고 전역 다른 자원 부재를 주장하지 않는다. 이 성공은 첫 other의 원인 해결 증거가 아니다.

실제 성공 launcher(repo cwd):

```sh
set -o pipefail
/usr/bin/env -i PATH=/usr/local/bin:/usr/bin:/bin LANG=en_US.UTF-8 TZ=UTC PYTHONDONTWRITEBYTECODE=1 /Users/parkjinhee/AI/verith_refactor/verith/backend/.venv/bin/python -I -S -B -c 'import sys,runpy,json; from pathlib import Path; from datetime import datetime,UTC; root=Path.cwd(); site=root/"backend/.venv/lib/python3.12/site-packages"; assert site.is_dir(); sys.path[:0]=[str(root/"backend"),str(site)]; sys.argv=[str(root/"backend/scripts/cf002_interactive_login.py"),"--verify-flow-fake-execution-db"]; print("CF007_RUNTIME "+json.dumps({"started_at":datetime.now(UTC).isoformat(),"python":sys.version.split()[0],"isolated":sys.flags.isolated,"no_site":sys.flags.no_site,"no_bytecode":sys.dont_write_bytecode}),flush=True); runpy.run_path(sys.argv[0],run_name="__main__")' | /usr/bin/sed -l -E 's/"nonce": "[^"]+"/"nonce": "[redacted]"/g' | /usr/bin/tee /var/folders/d7/v1s6ddq12y9fftsqrvrgcz140000gn/T/cf007-baseline-v8lhvsa7/pg-diagnostic.log
```

위 명령은 실행 이력이며 재실행 지시가 아니다. 이번 기록에는 개인 대화·자격 관련 과거 이력을 복사하지 않는다.


로그 SHA-256: `pg-round-1.log` = `722a5add852388d8a9b43e76df1aa4a40a1ec9f98ceb336f91ec79cceb3d3b87`, `pg-diagnostic.log` = `82073cd0acb5a4077c7e18d1bf1108e3cd12942a5070fbd4138b723d7944e30e`. 로그의 counts/removal 보고와 tool 완료 exit·별도 exact CID 부재 확인은 각기 다른 증거다.

## 독립 검토와 최종 source

독립 source-only 검토에서 제품 필수 결함은 발견되지 않았다. checker의 상태별 SQL 시험 가림을 제거하고 terminal revoke-first를 실제 lock wait로 보완했으며, nonempty downgrade는 정확한 자체 거부만 인정한다. 진단 phase-only delta·기존 CF003/006 checker/helper/run/input·공개 계약/bootstrap 보존과 로그 범위를 최종 재검토했다. 검토자는 파일 수정·앱/테스트/DB/Docker를 실행하지 않았다. log에서 읽은 counts와 root의 tool exit/CID 부재 증거는 분리한다.

| 경로 | SHA-256 |
|---|---|
| `backend/src/modules/flow/domain/fake_execution.py` | `38b87f65ccfbd9d545050f739090d4dedb59c6ccbd41e833961fe37437a5972d` |
| `backend/src/modules/flow/application/fake_execution_service.py` | `9e2f41b6384324a2809fdc2f45a93ad84e484000387c097d9b4ca377def50df0` |
| `backend/src/modules/flow/infrastructure/fake_execution_repository.py` | `a8bbc825b9d3171063ac5f9c98251f87bcf788ac4580781093d13608b1347f27` |
| `backend/db/models/flow/fake_execution.py` | `bf9196ba36f5fa43b332a267ca0c507b6afb8a96438b74f2db8bed2380f72ed5` |
| `backend/db/models/registry.py` | `5b9798b56c61becc6523b92c8221bb065e6f6e801c5e281137b85242a8dba6c5` |
| `backend/db/migrations/versions/20261108_c7001a7e0001_flow_fake_execution.py` | `f05c07c2a497d4faddbf71c4981e6ba3c37ef757d634ff386d0f20d2e708d448` |
| `backend/tests/unit/test_cf007_flow_fake_execution.py` | `f6d41d1f41968c53da5ca6c9c4ff811ed008c8ba4dbc969984256c3011c42c5d` |
| `backend/scripts/check_safe.py` | `c86663b06402c7240fd406e4cdeac93a116aa3d083663c42ca111e0f7604b5df` |
| `backend/tests/safe_checks/test_entry.py` | `e8ce6055ca6e59aa3b04e9c25b126cd02f97203ef230fcb3ffbab3355bd95828` |
| `backend/scripts/cf007_fake_execution_check.py` | `55c7ee603e846c720bd0b0818d454c240ba6c0418452148d67df3736353e3494` |
| `backend/scripts/cf002_interactive_login.py` | `77bd7d59b316379d8a994aecb3a3d55ee7852ccbdc616df4aff5c357e2076ad8` |

self/unit source와 최종 차이는 고정 checker phase뿐이며 그 delta는 source-only 및 실제 재검증으로 확인했다. 성공 PG 이후 code/test/entry 변경은 없다. 기존 owned helper SHA `6ad32139269c0526b6737a4501c9f7e9b807a68a928f9c1f1e1df6559ec626d8`는 불변이다. 추가 통과 회차를 반복하지 않았다.

## exact Git 인계

checkpoint `/var/folders/d7/v1s6ddq12y9fftsqrvrgcz140000gn/T/cf007-baseline-v8lhvsa7`:

- `scope.json`/`baseline.json`: exact17과 시작 보존본.
- `round-1-source.json`/`pg-diagnostic-source.json`/`fixed-phase-delta.json`: 실제 검증 source와 phase-only 차이.
- `final-source.json`/`stage-pathspec.nul`: 최종17 bytes/크기·기준 metadata와 NUL literal pathspec. manifest 자체 hash는 자기 참조하지 않는다.
- `reviewguard.py`: 현재 branch/HEAD/origin/worktree·staged·전체 변경 집합/ignore·regular single-link/no-symlink·hash 및 PR body를 읽기 전용 확인. `--staged`는 index bytes까지 확인한다.
- `review-pr-body.md`: 아래 marker의 실제 본문. 각 marker는 문서에1회만 존재한다.

- `backend/src/modules/flow/domain/fake_execution.py`
- `backend/src/modules/flow/application/fake_execution_service.py`
- `backend/src/modules/flow/infrastructure/fake_execution_repository.py`
- `backend/db/models/flow/fake_execution.py`
- `backend/db/models/registry.py`
- `backend/db/migrations/versions/20261108_c7001a7e0001_flow_fake_execution.py`
- `backend/tests/unit/test_cf007_flow_fake_execution.py`
- `backend/scripts/check_safe.py`
- `backend/tests/safe_checks/test_entry.py`
- `backend/scripts/cf007_fake_execution_check.py`
- `backend/scripts/cf002_interactive_login.py`
- `backend/docs/flow_fake_execution.md`
- `backend/docs/schema.md`
- `backend/docs/migrations.md`
- `docs/development.md`
- `docs/documentation.md`
- `docs/work/CF-007-flow-fake-execution.md`

아래는 사용자 실행용이다. 변경이나 상태가 달라지면 다시 검토한다. 우선 전체 경로/기밀·무관 변경과 신규 파일까지 검토하고 exact bytes만 stage한다. 실제 Git publishing은 수행하지 않았다.

```sh
cd /Users/parkjinhee/AI/verith_refactor/verith
/usr/bin/python3 -I -S -B /var/folders/d7/v1s6ddq12y9fftsqrvrgcz140000gn/T/cf007-baseline-v8lhvsa7/reviewguard.py
git diff --check
git diff --stat
# final-source.json의 신규 파일을 포함한17경로 내용을 검토한다.
git add --pathspec-from-file=/var/folders/d7/v1s6ddq12y9fftsqrvrgcz140000gn/T/cf007-baseline-v8lhvsa7/stage-pathspec.nul --pathspec-file-nul
/usr/bin/python3 -I -S -B /var/folders/d7/v1s6ddq12y9fftsqrvrgcz140000gn/T/cf007-baseline-v8lhvsa7/reviewguard.py --staged
git diff --cached --check
git diff --cached --stat
git commit -m "feat(flow): execute one-shot fake flow and store owner-scoped artifacts"
git push -u origin feat/flow-fake-execution
gh pr create --repo bellra-jin/verith --base develop --head feat/flow-fake-execution --draft --title "feat(flow): execute and store a one-shot synthetic artifact" --body-file /var/folders/d7/v1s6ddq12y9fftsqrvrgcz140000gn/T/cf007-baseline-v8lhvsa7/review-pr-body.md
```

PR 본문 재추출(임시 body만 갱신, Git 변경 없음):

```sh
/usr/bin/python3 -I -S -B - <<'BODY'
from pathlib import Path
source=Path('docs/work/CF-007-flow-fake-execution.md').read_text()
start,end='<!-- CF007_'+'PR_BODY_START -->','<!-- CF007_'+'PR_BODY_END -->'
assert source.count(start)==source.count(end)==1
body=source.split(start,1)[1].split(end,1)[0].strip()+'\n'
Path('/var/folders/d7/v1s6ddq12y9fftsqrvrgcz140000gn/T/cf007-baseline-v8lhvsa7/review-pr-body.md').write_text(body)
BODY
```

<!-- CF007_PR_BODY_START -->
Flow의 봉인 합성 입력을 실제 실행/저장으로 연결하기 위해, 명시 opt-in한 owner의 fake 일회 실행과 별도 내부 artifact 저장·재조회를 추가합니다. 기존 receipt 상태와 공개 API/보관함은 유지합니다.

- 입력당 단일 grant·메모리 claim token/DB digest, DB deadline·단일 terminal 전이·owner JOIN과 strict 결과 연결 검증을 적용했습니다. ACK 유실/실패/timeout 이후 엔진을 다시 호출하지 않습니다.
- 보호 self19/unit893 통과·skip/guard0·임시 root 제거. 실제 owned PG 재검증9묶음/거부64·exit0, 12개 execution ID에 각각1회 호출, exact CID 제거/부재를 확인했습니다.
- 첫 PG의 원인 미확정 실패와 고정 phase-only 진단 재검증을 작업 기록에 분리했습니다. 독립 검토는 source-only이며 기존 CF003/006 PG 전체를 반복하지 않았습니다.
- 실제 AI/KIS/Google·브라우저/BFF·기존 리포트 게시/삭제·일반 worker/운영 DB는 범위 밖입니다. 내부 artifact이며 exactly-once 완료·takeover/저장 retry·관리자 DDL 격리를 제공하지 않습니다.

Base develop / head feat/flow-fake-execution, 구현 기준 `70d49b3eacccabd1db7bf2ea53cf678102f81bc7`. 상세: `docs/work/CF-007-flow-fake-execution.md`.
<!-- CF007_PR_BODY_END -->
