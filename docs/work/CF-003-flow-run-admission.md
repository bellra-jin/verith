# CF-003 · Flow 접수·멱등·본인 실행 상태 재조회 기반

## 현재 상태

구현·검증 진행 중이다. 기본 gate false, receipt_only 접수이며 worker/AI 실행은 없다.
**Flow 접수·멱등·본인 실행 상태 재조회 기반 완료.** 구현·직접 검증 및 최종 독립 source-only 수용을 마쳤고, 최종 정본 CF-003 v1.2 전체·diff·SHA 대조를 완료했다. 최종 보호 self 15/15·unit 469/469 및 두 번째 실제 격리 PG/ASGI 검증 8묶음·물리 제약 거부26건은 통과했다. 첫 PG exit2/cleanup_failed 이력과 별도 복구 정리를 보존한다. 두 실행의 정확 CID 부재를 확인했으며 첫 실패 원인은 미확정이다. 기본 gate는 false이며 worker/AI 실행은 없다.

- 최초 정본 v1.0 SHA `862de41c42684c41d6ccc73e97089595c1e8919c424e0bacb0106462f29ee595`을 전체 읽고 독립 준비를 시작했다.
- v1.1 SHA `8622afbf22745a58dc44ac83ffbb1805bd8eee3b54a3f7d6587650ef9f5ed263` 수신 후 전체를 읽고 23번째 허용 경로인 snapshot 테스트를 보완했다. 기존 3개 digest는 보존한다.
- 최종 v1.2 SHA `7c12088599d789a9080326c8636a5c3b5c1ec8789d8fbe251f44f408ac2373a8`을 수신해 전체·v1.1 대비 diff를 읽었다. v1.1 보존본 SHA도 위 값과 일치했다. 23경로 유지·기존 진단/두 실행 증거 구분만의 문서 보완이며 helper 확대·새 코드·검사 재실행은 없다. 아래 v1.0/v1.1 실행 이력은 당시 기준으로 보존한다.
- 운영 v1.1/v1.2/v1.2 hash 재대조, root/Backend/AI 안내·문서 권위와 현재 canonical 코드를 읽었다. 관련 .agents/skills 경로는 없었다.
- 기준/현재 HEAD `d67f731b1c2f452179d66abaa2b3381cccb8a15d`, branch `feat/flow-run-admission`.
  clean develop/worktree 1·정확한 fetch/push 전체 URL·동명 branch 부재를 확인했다.
  develop 전환→fetch→ff-only 최신화→새 branch 순서로 준비했다. 기본 실행의 GitHub DNS 실패(exit128)와 후속 fetch/ls-remote 성공을 구분한다. reset/clean/stash/rebase는 없다.
- 공개 변경 전 사본/해시는 `/tmp/cf003-baseline-4c_x0nod/baseline.json`에 보존했다. private 환경·기존 자료는 복사하지 않았다.

## 이번 변경과 수용 경계

[Backend 계약](../../backend/docs/flow_run_admission.md)의 정확한 POST/GET, 실제 세션·CSRF/owner,
영속 UNIQUE·commit 후 202·replay/GET·안전 오류를 구현한다. 테이블/registry/새 migration만 추가하고
기존 보고/CF 파생본·manifest·migration history·결과 payload는 보존한다.
Next/BFF/UI·공개 save·다른 관점·실제/가짜 AI·worker·게시/삭제·예산/실행권은 이번 범위 밖이다.

## 직접 보호 검사 이력

공개 시작은 repo root에서 clean env와 기존 절대 Backend Python의 `-I -S`,
`backend/scripts/check_safe.py self-test` 또는 `unit`이다. 직접 pytest로 보호를 우회하지 않는다.

| 변경 시점 | 실제 결과 |
|---|---|
| 초기 exact 입력/선택 보완 | self 14/14, exit0, 자기 root 제거 |
| 최초 unit | 13파일 452개 중 451 pass/1 fail, worker1/controller78, guard0, 자기 root 제거. 새 component 비교의 FastAPI 출력 schema 차이 |
| snapshot helper 보완 후 | 13파일 452/452, exit0/guard0, 자기 root 제거. 옛 digest 변경 없음 |
| 새 raw DB/teardown 회귀 추가 | 459개 중457 pass/2 fail, worker1/controller78, guard0, 자기 root 제거. 합성 token이 짧아 DB 오류 이전에 인증 거부된 테스트 입력 문제 |
| token 형태 수정 후 | 13파일 459/459, exit0/guard0, 자기 root 제거. 실제 인증 함수의 DB 오류 경로 확인, mock 성공 인증으로 대체하지 않음 |

| 정상 handler teardown·snapshot 음성·UTC 경계 추가 후 | self 15/15 통과. unit 467 중465 pass/2 fail: 정상 503은 맞았으나 바깥 CORS의 중복 Origin 때문에 문자열 Vary 비교가 실패. guard0·자기 root 제거 |
| Vary field-name 집합 비교로 보완 후 | unit 13파일 467/467, exit0/guard0·자기 root 제거 |
| 제약 SQLSTATE 보완 후, 진단 추가 전 재실행 | self 15/15, exit0. unit 13파일 수집467/pass467/fail0/skip0, exit0/guard0. 각각 자기 root 제거. self chunk c469d9, unit session41461/chunk5fdf8b |

최종 공개 명령은 각각 실행도구의 `sandbox_permissions=require_escalated`로 실행했다. 앱·실제 DB·외부 API를 호출하지 않는 보호 사본 검사다.

```sh
/usr/bin/env -i LANG=en_US.UTF-8 TZ=UTC /Users/parkjinhee/AI/verith_refactor/verith/backend/.venv/bin/python -I -S backend/scripts/check_safe.py self-test
/usr/bin/env -i LANG=en_US.UTF-8 TZ=UTC /Users/parkjinhee/AI/verith_refactor/verith/backend/.venv/bin/python -I -S backend/scripts/check_safe.py unit
```

## 독립 source 검토 지적과 수정

- nonempty downgrade 확인과 DROP 사이 INSERT 경합: ACCESS EXCLUSIVE 먼저→EXISTS→빈 경우 DROP으로 수정. 실제 두 순서의 경합 회귀를 checker에 구현했다. 현재 PG 실패로 그 회귀는 아직 실행하지 못했다.
- malformed UTF-8 JSON의 Starlette 400: 해당 body parsing 오류만 INPUT_INVALID/422로 변환하고 기존 401/local Host403을 유지했다.
- DB 획득·인증·cleanup의 raw OSError/TimeoutError: 신규 경로 안에서 SERVICE_UNAVAILABLE/503.
  function-scoped 세션 종료가 성공 전송 전에 wrapper 안에서 끝나도록 설치 FastAPI stack 동작을 대조했다.
- 위 세 수정은 독립 source-only 검토에서 수용됐다는 전달을 받았다. 이는 실제 PG나 최종 전체 검사 수용이 아니다.

## 첫 실제 PG 실행 실패와 자기 자원 복구

공식 metadata 확인에서 daemon27.4.0 및 기존 pgvector/pgvector:pg16 image
`sha256:fa3d9bb7ee77f5c1f0bfb009a9df30243c040896825f3033b09a77101bb2ca95` linux/arm64를 확인했다.
이미지 pull/설치는 없었다. 현재 Docker context 확인 뒤 자기 Docker CLI 임시 0700 디렉터리를 HOME으로 사용하고, 기존 TLS 설정을 바꾸지 않은 채 create/preflight/migration/cleanup 동안 유지·복원하도록 보완했다. 개인 인증서/환경 파일은 조회하지 않았다. 이 구조는 독립 source-only 검토 수용 전달을 받았으며 실제 PG 성공 증거와 구분한다.

첫 DB-only 실행은 실행도구의 `sandbox_permissions=require_escalated`로 실제 시작됐다. clean env·기존 절대 Python `-I -S -B` launcher로 `backend/scripts/cf002_interactive_login.py --verify-flow-admission-db`를 호출했다. 실행 출력 Python3.12.13/isolated1/no_site1/no_bytecode=true를 확인했다. site-packages는 정확한 backend/.venv/lib/python3.12/site-packages 한 곳만 sys.path에 추가했다. 이 실행의 source는 `/tmp/cf003-baseline-4c_x0nod/db-attempt-1-source.json`에 보존했다.

- session85997: `failed/stopped_without_fallback`, 이어 `cleanup_failed`, 최종 exit2. `owned_resource_created` 반환 전 실패했으며 migration·고정 checker에 도달하지 않았다. 실제 PG/ASGI·경합·물리 제약 통과 수는 0이다. 도구 정책 거절이 아니라 허용된 실행 안의 실패다.
- 직접 생성된 정확 CID `db984f3b322c1190115900f6b4942da7b69dd90cccca34fe05eb21328b95335d`, resource ID `CF-002-login-1c2cbfd518e5`. Docker Created `2026-11-08T05:25:39.685269875Z`는 컨테이너 생성시각이며 명령 시작/끝 시각이 아니다. 최초 실패의 원래 메모리 receipt를 사후 재구성하지 않았다.
- read-only 재확인에서 위 CID만 running, read-only root, mount0, loopback ephemeral5432→50002였다. 종료 로그의 CID/resource ID와 같은 CID의 create 이벤트를 대조했다. Env·로그·DB 내용·다른 자원은 읽지 않았다.
- 기존 finally 정리 실패와 별개로 정확한 자기 자원의 복구 정리를 수행했다. 정확 CID/Created/name/resource label·nonce와 고정 postgres 명령의 내부 일치·image·mount0/tmpfs/namespace/loopback port를 다시 대조한 뒤 그 자기 자원만 stop→rm했다. chunk2befb5 exit0, 정확 CID inspect의 명시적 No such object/container를 확인했다. 기존 helper cleanup 성공으로 소급 기록하지 않으며, DB 검증용 기존 컨테이너 채택·가짜 receipt 발급·자격 조회는 없었다. nonce/Env/DB 내용을 보고하지 않는다.

첫 실행의 실패 원인은 미확정이다. 기존 `runner_owned_database.py`의 `verify_metadata`는 여러 거부를 같은 고정 예외로 축약하고 호출자도 원문을 출력하지 않아 어느 검증/명령이 실패했는지 첫 실행의 기록만으로 확정할 수 없다. Docker 시작 직후 projection 지연 등은 가설일 뿐 확인된 원인으로 쓰지 않는다. 해당 helper는 CF-003 v1.1의 허용23경로 밖이므로 수정하지 않았다. 실패 자원 부재 확인 후, 아래의 허용 경로 안 고정 위치 진단을 적용한 별도 두 번째 실행만 진행했다.

첫 실패 뒤 공통 helper의 진단 변경도 검토했으나 구현하지 않았다. 최종 구현은 기존 호출자의 비민감 위치 진단에 한정하며 공통 helper의 bytes·소유 검증·정리 조건은 유지한다. 새 일반 runner/guard·검증 완화는 없다.

checker에는 Vary 토큰 집합이 정확히 Cookie+Origin인지(대소문자·공백 정규화/중복만 허용), private/no-store, attempt/PK/owner-key UNIQUE 및 모든 NOT NULL·finite created_at CHECK의 실제 SQLSTATE 거부, 두 downgrade 경합 순서가 구현됐다. 독립 source-only 검토에서 해당 보완을 확인했다는 전달을 받았다. 이 문단은 첫 실행 실패 직후 구현 상태의 기록이며, 이후 실제 결과는 아래 두 번째 실행 절을 따른다.

## 허용된 고정 위치 진단과 두 번째 실제 PG 통과

허용 경로 `cf002_interactive_login.py`의 신규 DB-only 모드에만 고정 단계·allowlist 예외 유형·정확한 공개 소스 함수/행 번호 진단을 추가했다. raw exception/locals/Env/실제 경로는 출력하지 않는다. `runner_owned_database.py`의 bytes·시간 bounds·accept/reject·소유/cleanup 조건은 그대로다. 기존 unit 안에 실제 helper AST를 추출해 합성 예외 원문/locals/unknown 유형·단계/경로 비노출 회귀 2건을 추가했다. 진단은 검증의 성공/실패 판단을 바꾸지 않는다.

- 보완 뒤 self15/15 exit0(chunk63e7e6), unit13파일 수집469/pass469/fail0/skip0·guard0·exit0(session67649/chunk7820df). 각각 자기 임시 root 제거. 원래467개 통과를 포함하며 두 진단 회귀가 추가됐다.
- 두 번째 PG 실행의 사전 source23 해시: `/tmp/cf003-baseline-4c_x0nod/db-attempt-2-source.json`. 실행도구의 `sandbox_permissions=require_escalated` 실행은 session57922/chunk73998c에서 exit0. 아래 실제 launcher를 사용했으며 shell pipefail로 원래 exit를 유지하고 출력의 nonce만 가렸다.

```sh
set -o pipefail
/usr/bin/env -i PATH=/usr/local/bin:/usr/bin:/bin LANG=en_US.UTF-8 TZ=UTC PYTHONDONTWRITEBYTECODE=1 /Users/parkjinhee/AI/verith_refactor/verith/backend/.venv/bin/python -I -S -B -c 'import sys,runpy,json; from pathlib import Path; root=Path.cwd(); site=root/"backend/.venv/lib"/("python"+str(sys.version_info.major)+"."+str(sys.version_info.minor))/"site-packages"; assert site.is_dir(); sys.path[:0]=[str(root/"backend"),str(site)]; sys.argv=[str(root/"backend/scripts/cf002_interactive_login.py"),"--verify-flow-admission-db"]; print("CF003_RUNTIME "+json.dumps({"python":sys.version.split()[0],"isolated":sys.flags.isolated,"no_site":sys.flags.no_site,"no_bytecode":sys.dont_write_bytecode}),flush=True); runpy.run_path(sys.argv[0],run_name="__main__")' | /usr/bin/sed -E 's/"nonce": "[^"]+"/"nonce": "[redacted]"/g'
```

| 실제 PG 검증 묶음 | 결과 |
|---|---|
| fresh upgrade·기존 합성 자료 보존·DDL 실패 rollback | 통과 |
| 실제 ASGI+PG commit/replay·owner·불변 run/attempt/최초 ID | 통과 |
| 입력·실제 앱 세션 인증·CSRF·owner 거부 | 통과 |
| gate off/인증 미설정 dependency0·안전 오류·성공 handler 뒤 teardown503 | 통과 |
| 같은/다른 입력의 별도 연결 commit·실제 lock 경합 | 통과 |
| INSERT rollback/재접수·commit 뒤 응답 유실/replay | 통과 |
| admission SHARE 선점 후 revoke 대기·폐기 cookie 거부 | 통과 |
| SQLSTATE 제약26건·nonempty downgrade 거부·insert/downgrade 양순서·빈 downgrade/reupgrade | 통과 |

이는 8개의 고정 검증 묶음이며 pytest 8개라는 뜻이 아니다. 실제 CHECK/FK/UNIQUE/NOT NULL 거부26건을 확인했다. 종료 시 flow_runs=0, 기존 합성 report/index/stock/NULL owner 자료의 전후 동일성을 검사했다. 실제 provider 연결 대신 합성 provider identity로 발급한 **진짜 앱 세션 구현**을 사용하며 Google 로그인이나 mock principal 통과로 주장하지 않는다.

성공 resource ID `CF-002-login-bd4d5cd8c627`, CID `e0f6a531bff179905b0b021bad9860a139538f180d71bae19add9a667a60734a`, Created `2026-11-08T05:39:21.948760631Z`, loopback127.0.0.1:50125, persistent mounts0. Created는 명령 시작/끝 시각이 아니다. 생성 receipt·readonly preflight·동일 연결 migration을 모두 기존 helper로 통과했다. runner finally가 owned_db_removed를 출력했고, 별도 공식 read-only 확인(chunkfc2379)에서 정확 CID No such object 및 해당 resource label ps-a 결과 empty를 확인했다. 첫 실패 CID도 같은 확인에서 No such object였다. 이 inspect의 부재 exit1은 DB workload exit0과 구분한다. 다른 작업을 포함한 전역 컨테이너0이라고 주장하지 않는다.

실행 전후 source23의 SHA 변화0을 확인했다(chunke9dd36). Python 래퍼에서 관측한 private-file/external-socket/external-httpx/dotenv-discovery 거부 카운터는 모두0이며, 관측 범위는 scoped Python 래퍼로 한정한다. native 패킷 추적이나 모든 I/O 관측으로 확대하지 않는다. 실제 .env/credential·기존 DB/volume·Google/AI/KIS·설치/이미지 pull은 사용하지 않았다. 원래 보호와 gate false를 유지했으며 제품 환경 설정은 바꾸지 않았다.

첫 실패는 고정 위치 진단 도입 전이라 상세 지점이 미확정이고, 두 번째 성공을 이유로 첫 실패나 복구 절차를 삭제하지 않는다. 최종 구현은 공통 helper를 변경하지 않으며 추가 PG 재실행도 진행하지 않는다. 현재 실제 PG 직접 검증은 완료했다. 아래 최종 독립 source-only 수용은 해당 실행을 독립 재현한 결과가 아니다.

## 최종 독립 source-only 리뷰 수용

최종 독립 source-only 검토에서 핵심 API/DB/멱등/owner/SHARE·downgrade 잠금·기존 snapshot 유지 및 허용23경로에 새 구체적 결함이 없음을 확인했다. 신규 DB-only 진단은 고정 stage/type/source 별칭/함수/정수 line·최대8frames, unknown의 other 처리와 비노출 unit2건이 수용됐으며 helper 조건 완화는 없다.

전달된 reviewer hash와 현재 파일을 읽기 전용으로 직접 대조해 모두 일치했다: runner `a3ae1d3de63937d2f43adf342f090ed8016a19f71f5972d1de22553d19f25c0b`, unit `2a532ddefe76ad3c0bd63a579c66766d3373e99b7100ef75d576b75b52e63321`, unchanged helper `6ad32139269c0526b6737a4501c9f7e9b807a68a928f9c1f1e1df6559ec626d8`.

self15/unit469 및 실제 PG8묶음·제약 거부26건·두 CID 정리는 개발 채팅의 직접 실행 원문 증거다. 독립 검토자는 이를 별도 실행한 것이 아니라 source-only 리뷰와 전달된 실행 증거를 확인한 것으로 기록한다. 실제 Google·AI·사용자 UI·운영 DB 및 전체 DB pytest는 이번 완료 수용에 포함하지 않는다. 첫 실패 미확정·복구와 두 번째 성공을 계속 분리한다. 최종 정본 v1.2 hash를 수신·대조했으며 문서 기준과 현재 구현/검증의 일치를 확인했다. 이 수용 때문에 코드·PG·검사를 다시 실행하지 않았다. 이후 작업은 이 미커밋 변경을 보존하고 현재 branch에 섞지 않는다.

## 최종 source·범위 점검

현재23경로(기존13/신규10), 범위 밖0·staged0·ignored0, Python AST 구문 및 diff --check 통과다. HEAD/branch와 전체 origin fetch/push URL은 최초 기준 그대로다. CF snapshot/manifest·ST 이력·기존 migration/helper는 변경하지 않았다. 아래는 최종 실행 source 해시이며 보고서 자체 해시는 외부 사본에 기록한다.

| 경로 | SHA-256 |
|---|---|
| `backend/src/modules/flow/domain/execution.py` | `e4fef5dc243002f7e2173d631e080dee0fd7e70041af61b3acd9bd78583b875d` |
| `backend/src/modules/flow/api/run_schemas.py` | `72cba0c26594c81acb3994462e9682e20b3bd8cbc2863f694d8f03e1233c6fd3` |
| `backend/src/modules/flow/api/run_router.py` | `2da4a159282d4cf8a80970732d31b81ae881877019db81cd3bec65d7876c63e8` |
| `backend/src/modules/flow/application/run_service.py` | `1620051bbd141f037c538d1b42f3f24ae19a11b8afb750d95a32bb5229cee81e` |
| `backend/src/modules/flow/infrastructure/run_repository.py` | `3ab3fd1d22ce71c321c4bc31ea36f19d85712b453c1f8a70972be98fa012df3d` |
| `backend/db/models/flow/flow_run.py` | `8e490de138a9ef4d2b3ea951eec555b7d82f35f2ade0ca6ce2ecc914b3c723a7` |
| `backend/db/models/registry.py` | `fae7a492f92a319a95925e07d0e722bc5a3d37c48c90f736a472cbc21be714bf` |
| `backend/db/migrations/versions/20261108_c3001a7e0001_flow_run_admission.py` | `ad222818d85e7a5376fe91e2a39218c2bd7a818f895886a44ed37f5e00c6737b` |
| `backend/src/shared/config.py` | `271c70c144717a41996b7147dff6f729a8479b378c6785fa6e501937f28c9c46` |
| `backend/src/shared/http/access_boundary.py` | `2a7b4f061568db6fe9c0d63d0fe976846da4140abc093e561d00d1422f781ad6` |
| `backend/src/api/main.py` | `ea315a4f72ef9dd2002832b93051f739eb223c9c189fcaaf3a5af94a0cf81677` |
| `backend/tests/unit/test_cf003_flow_runs.py` | `2a532ddefe76ad3c0bd63a579c66766d3373e99b7100ef75d576b75b52e63321` |
| `backend/tests/unit/test_flow_contract.py` | `31121d125c95df87ffc68eb9b0edc33416d39b688247b7b7e72c1c299d6bf4c0` |
| `backend/scripts/check_safe.py` | `4e0e4d12d14062a475f0a9606eac0723b4a2a33b0c4ae5568090721466afe855` |
| `backend/tests/safe_checks/test_entry.py` | `fe469aa02526bb4fd24b40020dac03d165ac0321aebc2907bbdb01c02a764ece` |
| `backend/scripts/cf003_admission_check.py` | `d417f76b22d0851615e8c4a47abcd9fc2289011cc8bd0f47d4b1ef88eecd81fc` |
| `backend/scripts/cf002_interactive_login.py` | `a3ae1d3de63937d2f43adf342f090ed8016a19f71f5972d1de22553d19f25c0b` |
| `backend/docs/flow_run_admission.md` | `d8298e1caaf53768703b695b05a6cc4a9b6f98fb67a4f84932c335e8983767c8` |
| `backend/docs/schema.md` | `7ea52475d6adc3dd05aeb90e64c4e125e925eebd2e564257139dc410f2199e05` |
| `backend/docs/migrations.md` | `d28a083b776606b8ca54219b18b0d24aa20651e963bf56692b7213f5030ee9c9` |
| `docs/development.md` | `377d0c571d5cfb3758be90bd969c44049447b78fd5136f65cb18a01ab241ff01` |
| `docs/documentation.md` | `10233b7a503baac38421e72cf60ad5eb2e5d480c373009d5529134f8911d6664` |

전체23개 최종 해시와 exact staging pathspec은 자기 공개 checkpoint에 저장한다. 보고서 수정은 실행 제품 source를 변경하지 않으며 과거 실행 시점 해시는 해당 사본에 보존한다.

## 사용자 review·commit·Draft PR 초안

최종 독립 source-only 리뷰 수용 및 v1.2 정본 hash 대조를 마쳤다. 아래는 사용자 review 후 직접 실행할 명령 초안이며 개발 채팅은 실행하지 않는다. 개발 채팅은 git add/commit/push/실제 PR/Ready/merge를 실행하지 않았다. 이번 범위에서 실제 외부 AI 호출과 사용자 자격 사용은 수행하지 않았다.

review repo `bellra-jin/verith`, base `develop`, head `feat/flow-run-admission`, 기준 HEAD `d67f731b1c2f452179d66abaa2b3381cccb8a15d`다. commit 메시지: `feat: add owner-scoped receipt-only flow admission`.
`/tmp/cf003-baseline-4c_x0nod/final-source.json`은 현재 exact23 파일 SHA, `review-pathspec.nul`은 같은23 경로다. 임시 사본이 없거나 상태가 달라지면 아래 초안을 재확인한다. `git add .` 대신 이 공개 집합만 사용한다. stage 전 실제 diff를 검토해 비밀·무관 변경이 없음을 확인한다.

다음 사전 guard는 읽기 전용이다. HEAD·branch·staged0·전체 원격 URL/추가 원격·정확 dirty집합·파일 SHA·비무시·pathspec을 대조한다. guard 이후 새 변경이 있으면 다시 검사한다.

```sh
cd /Users/parkjinhee/AI/verith_refactor/verith
/usr/bin/env -i PATH=/usr/bin:/bin LANG=en_US.UTF-8 /usr/bin/python3 -I -S -B - <<'CHECK'
from pathlib import Path
import hashlib,json,subprocess
root=Path.cwd()
assert root==Path('/Users/parkjinhee/AI/verith_refactor/verith')
def git(*args):
    return subprocess.check_output(['/usr/bin/git',*args],cwd=root)
assert git('rev-parse','HEAD').decode().strip()=='d67f731b1c2f452179d66abaa2b3381cccb8a15d'
assert git('branch','--show-current').decode().strip()=='feat/flow-run-admission'
assert git('diff','--cached','--name-only')==b''
assert git('remote').decode().splitlines()==['origin']
for args in [('remote','get-url','--all','origin'),('remote','get-url','--push','--all','origin')]:
    assert git(*args).decode().splitlines()==['https://github.com/bellra-jin/verith.git']
folder=Path('/tmp/cf003-baseline-4c_x0nod')
manifest=json.loads((folder/'final-source.json').read_text())
assert len(manifest)==23 and set(manifest)==set(json.loads((folder/'baseline.json').read_text()))
changed=set(git('diff','--name-only','-z').decode().split('\0')[:-1])
changed.update(git('ls-files','--others','--exclude-standard','-z').decode().split('\0')[:-1])
assert changed==set(manifest)
for name,digest in manifest.items():
    path=root/name
    assert not path.is_symlink() and path.is_file() and path.stat().st_nlink==1
    assert hashlib.sha256(path.read_bytes()).hexdigest()==digest
pathspec=b'\0'.join(p.encode() for p in sorted(manifest))+b'\0'
assert (folder/'review-pathspec.nul').read_bytes()==pathspec
check=subprocess.run(['/usr/bin/git','check-ignore','--no-index','-z','--stdin'],input=pathspec,capture_output=True)
assert check.returncode==1 and check.stdout==b''
subprocess.run(['/usr/bin/git','diff','--check'],check=True)
print('review guard passed: exact23, source SHA matched, staged0')
CHECK
```

위 guard 성공과 독립 검토 후 사용자가 순서대로 실행할 각 명령 초안이다. add 후 staged diff가 허용23경로/검토 bytes와 같고 HEAD가 여전히 위 값인지 다시 확인한 뒤 commit한다. push/PR 전에도 전체 원격 주소와 branch를 다시 확인한다. fetch/merge/rebase/force 옵션은 없다.

```sh
git add --pathspec-from-file=/tmp/cf003-baseline-4c_x0nod/review-pathspec.nul --pathspec-file-nul
git diff --cached --check
git diff --cached --stat
git diff --cached
git commit -m "feat: add owner-scoped receipt-only flow admission"
git push --set-upstream origin feat/flow-run-admission
```

PR 본문은 정확 marker 사이만 추출한다. 셸 치환으로 본문을 명령에 삽입하지 않는다.

<!-- CF003_PR_BODY_BEGIN -->
최종 기준은 CF-003 v1.2, source SHA-256 `7c12088599d789a9080326c8636a5c3b5c1ec8789d8fbe251f44f408ac2373a8`입니다. 구현·직접 검증·독립 source-only 수용과 정본 대조를 마쳤습니다.

기본 비활성 receipt_only Flow 접수 기반을 추가합니다. 실제 앱 세션·CSRF와 owner SQL로 POST /api/flow/runs 및 GET /api/flow/runs/{run_id}를 보호하고, 영속 멱등 UNIQUE·commit 후202·본인 상태 재조회를 제공합니다. worker·가짜/실제 AI·결과 저장/삭제·BFF/UI는 추가하지 않습니다.

새 flow_runs 테이블과 nonempty downgrade 보호를 추가했습니다. 기존 OpenAPI/schema/payload digest는 정확한 추가 계약 검증과 제한된 copy 투영으로 보존합니다. 신규 오류/DB teardown과 raw body 경계를 처리하며 기존 API 응답을 전역 변경하지 않습니다.

검증: 보호 self15/15, 고정13파일 unit469/469, guard0. 실제 자기 PostgreSQL에서 ASGI/owner/CSRF·멱등/폐기 경합·rollback/응답 유실·migration/downgrade 양순서 등8묶음 및 물리 제약 거부26건을 통과했습니다. 첫 PG 실행 exit2/cleanup_failed는 별도 복구 정리했고, 두 번째 exit0과 두 정확 CID 부재를 확인했습니다. 첫 실패 원인은 미확정입니다. 고정 위치 진단만 허용 호출자에 추가했으며 공통 소유 helper/보호 조건은 변경하지 않았습니다.

실제 Google/AI·사용자 BFF/UI·전체 DB pytest·worker는 미검증/범위 밖입니다. 검사 provider identity는 합성이고 실제 세션 구현과 새 소유 PG를 사용했습니다. 자세한 실행/실패/정리·source SHA는 docs/work/CF-003-flow-run-admission.md에 있습니다. 최종 독립 source-only 리뷰에서 새 구체적 결함 없음으로 수용됐습니다. 위 unit·PG 실행은 개발측 직접 실행이며 독립 재실행은 아닙니다.
<!-- CF003_PR_BODY_END -->

```sh
/usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -S -B - <<'BODY'
from pathlib import Path
text=Path('docs/work/CF-003-flow-run-admission.md').read_text()
begin='<!-- CF003_'+'PR_BODY_BEGIN -->'
end='<!-- CF003_'+'PR_BODY_END -->'
assert text.count(begin)==text.count(end)==1
body=text.split(begin,1)[1].split(end,1)[0].strip()
assert body
Path('/tmp/cf003-baseline-4c_x0nod/review-pr-body.md').write_text(body+'\n')
BODY
gh pr create --repo bellra-jin/verith --base develop --head feat/flow-run-admission --draft --title "feat: Flow 접수·멱등·본인 실행 상태 조회 기반" --body-file /tmp/cf003-baseline-4c_x0nod/review-pr-body.md
```
