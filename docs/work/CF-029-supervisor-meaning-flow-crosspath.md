# CF-029 · 합성 의미 준비와 Flow 저장의 교차 회귀

## 기준과 현재 판정

- 지시서 v1.0 SHA-256 `8166e01a10d22d492998fed4e87af5890c8ec6b5cc4e02281684cc5259b16e68`을 사용했다.
- 원격 `origin/develop` read-only 확인 결과와 작업 base는 모두 `6e9e625ed18a9a6b48cd06012e662d703aaf1de7`이다. 새 worktree는 `verith-supervisor-flow-crosspath`, branch는 `test/supervisor-meaning-flow-crosspath`다.
- **최종 구현의 보호 self3/unit87 및 owned synthetic PG 교차 회차 5그룹이 통과했다.** 최초에는 지원 source-copy 형식 확인을 보류했으나, 조율자가 기존 공개 helper로 구성한 private launcher를 검토하고 고정 controller의 preopen 보완 뒤 공식 실행을 승인했다. PG1의 검사 설정 오류를 수정하고 PG2로 필요한 실패 영향 재검증을 마쳤다. 원격 CI/PR/최종 독립 검토는 별도다.
- main Technical WIP, CF021/CF028 worktree, CF026 실행 자료·원 승인/예산·hold/release flag는 변경하거나 입력으로 사용하지 않았다. Git add/commit/push/PR/merge는 실행하지 않았다.

## 구현 범위

정확히 지시된 네 경로만 변경한다. checker에는 proof 한 개만 받는 strict synthetic entry를 추가했다. 기존 checker의 함수/클래스 20개는 AST 대조에서 그대로다. `verify_meaning_assembly`, `_run_meaning_assembly`, `verify_live`의 mode·반환·No Flow 계약은 보존했다.

새 checker는 새 owned DB를 요구하고 기존 실제 `PreparationService`와 provider형 `MockTransport` 조립을 재사용한다. 한 epoch의 정상 준비 A를 본인 ASGI GET으로 읽은 뒤 다른 owner B의 마지막 unknown을 만든다. 이후 assembly helper를 다시 호출하지 않는다. owner+prepare-key digest로 찾은 실제 준비 A와 draft/spec/plan hash를 대조하며, 본인 세션·CSRF·Origin을 실제 ASGI confirmation에 전달한다.

동의 누락/false·잘못된 plan hash·다른 owner·세션 없음/무효·CSRF/Origin 실패는 서로 다른 confirmation key로 검사한다. CSRF와 Origin의 기존 계약은 401 `AUTH_REQUIRED`다. 유효 동의는 합성 USD0.01 budget으로 429를 확인한 뒤, usage period/run/reservation/call/report가 모두 0인지 확인한다. binding/준비 소비 commit은 보존하며, USD2의 합성 설정에서 같은 key/body로 기존 coordinator에 재진입한다. 저장 한 번, replay/GET 추가 실행 0, 본인/타인 report 경계와 consumed root의 민감 본문 정리를 검사한다.

의미 epoch의 accounting snapshot/hash와 Mock count/generation/supplier를 구분한다. 준비 소비로 달라지는 전체 preparation row는 불변 snapshot 대상으로 삼지 않는다. Flow의 913,500,000 nanoUSD 예약 및 9개의 `not_called` slot은 합성 데이터이며 외부 공급자 호출로 집계하지 않는다. 이 경로는 아래 PG2에서 실제 발급 세션·CSRF/owner·SQL·저장/조회로 통과했다. 최초 준비는 HTTP preparation POST 전체가 아닌 private `PreparationService` 경로이며, 이후 GET/confirmation/report는 실제 Backend ASGI다.

`--verify-supervisor-meaning-flow-db`는 기존 mutually-exclusive parser·DB-only HOME·nonce 제거·같은 connection migration·120초 checker·실패 진단·receipt 기반 cleanup 분기에만 연결했다. Google/Frontend 준비나 서버 기동으로 fall-through하지 않는다. 기존 assembly flag의 독립 dispatch는 유지했다.

## 직접 실행한 보호 검사

2026-11-10 UTC, 새 worktree의 다음 고정 입구를 공식 `require_escalated` 심사로 실행했다. 아래는 명령 형식이며 정확한 경로는 private handoff에 보존했다. `MODE`는 각각 `meaning-assembly-self`, `meaning-assembly-unit`이다.

```sh
env -i LANG=en_US.UTF-8 TZ=UTC \
  <verified absolute Python> \
  -I -S -B \
  <worktree>/backend/scripts/check_safe.py MODE
```

| 검사 | 최종 직접 결과 | 증거 |
|---|---|---|
| `meaning-assembly-self` | 3 통과, exit 0 | `backend-self-early-scope-fix.log` |
| `meaning-assembly-unit` | 단일 기존 수집 파일 87 통과, guard 위반 0, exit 0 | `backend-unit-early-scope-fix.log` |
| diff whitespace | 통과 | `git diff --check` |
| 기존 checker 정의 보존 | 기존 함수/클래스 20개 AST 동일 | base/current source 대조 |
| guard/bootstrap/selection/owned runner | base와 bytes 동일 | 아래 고정 hash |
| 신규 owned PG CLI | PG2 최종 5그룹 통과, exit 0 | `pg-2.log` |
| 독립 source 검토 | 조율자의 report decoder 지적 수정·재검증 및 private launcher 검토 완료; 최종 전체 검토 진행 | PG2 직접 실행과 구분 |
| 원격 CI·PR | 미실행/조율 대기 | 게시하지 않음 |

최초 self3/unit82 통과 후, 첫 본인 ASGI GET을 unknown 전에도 확인하고 unknown의 실제 B attempt identity를 고정하는 검사 순서를 보완했다. 그 보완 뒤 self3/unit82가 통과했다. 이후 독립 검토에서 Supervisor `{data,error}` decoder를 legacy report GET에도 적용했던 checker 오류를 발견했다. report 전용 decoder로 실제 `FlowReportEnvelope` 성공과 `detail` 오류, 저장 report ID를 검사하도록 고쳤다. 잘못된 wrapper·타인 404·미인증 401·다른 report ID·status/private header 회귀 3건을 추가했다. 이 수정 뒤 self3/unit85가 통과했다. PG1에서는 첫 owner GET이 늦은 합성 settings scope보다 먼저 실행돼 기존 feature gate가 닫혀 있었다. 초기 GET에도 합성 feature/token/env를 scope 안에서 적용하고 정상/취소 복원 회귀 2건을 추가했다. 위 최종 로그는 이 수정 뒤 self3/unit87을 재실행한 결과다. 제품 route나 gate는 변경하지 않았다. unit의 wrapper 취소/정리·observation 변조·실제 parser/main AST DI routing 검사는 callback/AST 합성이며 실제 PG·발급 세션 성공으로 집계하지 않는다.

로그와 정확한 실행 경로·명령·자원 식별자는 저장소 밖의 새 private checkpoint에 보존했다. 기존 private checkpoint는 읽지 않았다. 각 보호 입구는 자기 임시 root 제거를 출력했다. PG1/PG2 모두 기존 owned runner가 자기 receipt의 정확 CID를 제거하고 부재를 확인했다. 각 private launcher는 source/dependency/origin 후검사와 source-copy root 부재도 확인했다. receipt nonce·cookie·raw exception은 로그로 내보내지 않았다.

| 파일 | SHA-256 |
|---|---|
| `backend-self-early-scope-fix.log` | `1737571f38bb1abb94a8968127de945d649e9e18724ff18f23d614e3df9f5f21` |
| `backend-unit-early-scope-fix.log` | `b3adc30d957b832a52c43d52224119b23ded99ff2faf8b3f5a3a88ab7dda2679` |
| `pg-1.log` (실패 이력) | `71134ef62aa63c2e47a78ffe4339bc5c24ae6a440303fb1085ca4c0732bc8880` |
| `pg-2.log` (최종 통과) | `edf6d779dfa70f3cd74ffbd8e9ff0877a2c719478d54ef596b91aa68edfa9bc4` |
| `backend/scripts/cf002_interactive_login.py` | `15fa128e549efacb90282e029e36833912c5476d65d6710b00214625a781f1f9` |
| `backend/scripts/cf023_supervisor_meaning_check.py` | `72a6c480c8bf3fb133533213fcfd01b818ecb426fb379a12611c2b5bd010423a` |
| `backend/tests/unit/test_cf024_supervisor_live_verifier.py` | `cbb4bfa5ca7ac54e0dad721b1dd8a73a4b4d046f734ae9ea2cfeb88dfc9214a0` |
| `backend/scripts/check_safe.py` (불변) | `59f0b8a6983947f94005d3080043194df376761341b3e332155e25be39e6f34e` |
| `backend/scripts/safe_checks_bootstrap.py` (불변) | `2b4f706192b9ca20770b3005843d934bcdd44dace385168f84920904b9ca68a6` |
| `backend/tests/safe_checks/test_entry.py` (불변) | `265856384cebcd7756c85cc7b33c2a53221e3a47b902ae25f6befb46a1e3dd61` |
| `backend/scripts/runner_owned_database.py` (불변) | `8295670c5caadb7177c545683511bd16b80ee1fd02e9ff19341e9812b3c83b98` |

## 의존성과 남은 수용 조건

새 worktree의 누락된 `.venv` alias만 기존 검증된 Backend `.venv` 설치로 연결했다. 정확한 설치 경로는 private handoff에 보존했다. `uv.lock` SHA `7beffafebfee13a5d5d09738813225464f35687347929a6d7819a58b4058b78e`, `pyproject.toml` SHA `91b2b71e68e5c02046cce1e7ad9d6a4ec7c44d8fccca998da544b316bb35e318`은 설치 원본과 동일했다. CPython 3.12.13 runtime SHA `36984af9f922aec72ba5b03e811ee92512268785007192e20f826cbd07cf8d04`를 대조했고 system site는 꺼져 있다. 기존 bootstrap이 runtime/site의 owner/mode, 원본과 사본의 source/hash/origin·AI32 pin, OS/FS/network 보호를 적용했다. 설치·image pull·의존성 복사는 하지 않았다.

다음 단계는 최종 diff/PG 근거의 독립 검토와 최신 exact-head CI다. 아래 PG entry는 기존 unit OS sandbox와 적용 경계가 다르다. unit의 OS/FS/network/bootstrap 보호는 그대로이며, PG는 기존 `LocalDocker` 소유 receipt·제한 role·readonly/socket preflight·같은 연결 migration과 `isolated_application(proof)`의 dotenv/import/외부 HTTP 차단을 사용한다. 새 OS allowlist/profile이나 앱/실DB fallback은 만들지 않았다.

## 실제 owned PG 실행과 정리

두 회차는 아래 형식의 동일한 clean-env 절대 interpreter entry를 공식 `require_escalated` 심사로 실행했다. private launcher는 저장소 밖에 있어 공개 변경 파일 수에 포함되지 않는다. 기존 공개 `check_safe.selected_sources(repo, assembly_only=True)`·`regular_bytes`·`validate_dependency`·`OwnedRoot`로 264개 source를 복사하고 AI32 pin과 source/dependency의 전후 hash·copied module origin을 확인한다. 원본 controller는 private non-`scripts` module로만 로드한다. 고정 copied CLI의 `--verify-supervisor-meaning-flow-db` dispatch·120초 checker·finally cleanup은 그대로다. Docker binary는 `/usr/local/bin/docker`가 가리키는 공식 Docker.app 실행 파일 SHA `85dd50c82c33a1dcd7ff4fbd09b17a37fd0d4152f6817a8efb2e2a54b4d8d038`으로 고정했다. 원래 context의 local Unix socket만 확인하며 기존 image의 `--pull=never`를 유지한다.

```sh
/usr/bin/env -i LANG=en_US.UTF-8 TZ=UTC \
  <verified absolute Python> \
  -I -S -B \
  <private reviewed launcher>
```

PG1은 `pg-1.log`, PG2는 `pg-2.log`로 stdout/stderr를 보존했다. PG1 launcher·manifest/identity와 각 unit/self 로그도 덮어쓰지 않고 남겼다. 새 실행 거절이나 공급자 우회는 없었다.

| 회차 | 직접 결과 | 자기 CID / 정리 |
|---|---|---|
| PG1, 자원 생성 16:51:08 UTC | same-connection migration·첫 실제 supplemented 준비 뒤 초기 ASGI GET feature 설정 누락으로 exit 1 | 원 receipt의 정확 CID 제거·부재 확인, sourcecopy 제거·postcheck 통과 |
| PG2, 자원 생성 16:53:43 UTC, 16:54:18 UTC 이전 완료 | 최종 source의 5그룹, exit 0 | 원 receipt의 정확 CID 제거·부재 확인, sourcecopy 제거·postcheck 통과 |

PG2 private launcher SHA는 `d58c2d4e9701543046e402795aea519ac3d9dff89d32124691f49aa8d9e14958`, source-selection manifest SHA는 `f3035c416b7172fc2615fcf6a3275b02fc529aa60b6274d6a9b49afd5b4766f4`, launcher identity SHA는 `055e9fd9af62adb4b0dd6ea7b7f98757a02f9b7930c5c2bf2ce4c7a2dc704777`이다. 초기 fixed controller는 lstat/O_NOFOLLOW/nonblock/fstat/afteridentity·bounded read와 hash 검증 후에만 compile/execute한다.

PG2의 실제 SQL·transport 대조 결과:

| 계수 | 최초 | budget 429 직후 | 저장·replay/GET 뒤 |
|---|---:|---:|---:|
| Flow run | 0 | 0 | 1 |
| Flow reservation | 0 | 0 | 1 |
| Flow report | 0 | 0 | 1 |
| Provider slot 행 | 0 | 0 | 9 (`not_called`) |
| Usage period | 0 | 0 | 2 |
| fake Flow dispatch | 0 | 0 | 1 |

의미 Mock count/generation/supplier는 각각 2회였다. 첫 성공의 observed 추정은 120,000 nanoUSD, 마지막 unknown의 `estimated_nano`는 null이다. 의미 reserved 100,000,000 nanoUSD·count2/generation2·attempt2·blocked·원 B active attempt를 보존했다. unknown 직후와 최종 epoch SHA는 모두 `67c43a3618777d086c105c4ddc32a93dfdef4de599af7daadc1a91dc77b9f16f`다. 8개 동의/plan/owner/session/CSRF/Origin 실패는 Flow/binding 추가 0, budget429는 binding commit을 보존하면서 Flow admission/period 전체 rollback을 확인했다. 같은 key/body retry만 저장 1회를 만들었고 이후 replay/request GET/report GET은 추가 dispatch·예약·의미 호출 0이었다. 준비 A의 consumed binding 참조와 민감 본문 NULL, B owner/무세션의 request/report 거절을 확인했다. 금지 접근 관측값은 private file/network/HTTP/dotenv 모두 0이었다.

현재 실제 OpenAI/KIS/Google·credential source 읽기·실제 비용·브라우저/Next·운영 DB 접근은 모두 0이다. 기존 실제 예산/승인 원장과 CF026 unknown hold는 이 합성 회귀의 입력이나 비용 항목이 아니다.

검토용 commit 제안: `test: add supervisor meaning to Flow crosspath regression`. repo는 `bellra-jin/verith`, base는 `develop`, head는 `test/supervisor-meaning-flow-crosspath`다. 최종 독립 검토/CI 전 Ready·merge하지 않으며 Git 실행은 조율자의 별도 범위다.

## CF-037 최신 develop 통합과 재검증 — 2026-11-11 UTC

위 결과는 최초 base와 PG1/PG2의 보존 이력이다. 이번에는 최신 develop
`f2c3ba4dc9c73508e8e0c89d1bbf5c8df61f40ab`에 같은 branch/worktree의 정확4파일 추가분만 통합했다.
원4파일·원형 hash·복구 patch와 과거 검사 로그는 별도 보존했다. 선행 commit이나 stash/reset/clean 없이,
보존한 tracked patch만 잠시 역적용해 같은 branch를 ff-only한 뒤 검토한 CF029 추가분을 재적용했다.
연결 장애로 한 역적용 요청의 결과가 처음 불명확했으나, 복구 뒤 원4파일 hash·HEAD·빈 index가 그대로인 것을
확인해 미실행을 대조한 뒤 진행했다. 정책 거절을 다른 경로로 우회하지 않았다.

checker와 CF024 unit은 최신 정의 뒤의 append-only 추가이며, 기존 provider55/verifier60·정산1회·취소·
gateway diagnostic·No Flow/live 경계를 보존한다. runner에는 고정 새 flag만 추가하고 현재 Technical owned
분기·같은 연결 migration·DB-only·120초 dispatch·receipt 정리를 유지했다. check_safe/test_entry·AI32·
worker/guard·제품 코드·migration·Frontend·CI·package/lock은 이번 diff가 아니다.

이번 직접 보호 검사에서 `meaning-assembly-self` 3개, 단일 `meaning-assembly-unit` 103개가 통과했다.
guard 위반0·각 parent exit0·소유 임시 root 제거를 확인했다. 이전 unit87과 합산하지 않는다.
동일 최종 source280개·AI 고정32개를 기존 source-copy/clean-env 형식으로 고정해 새 Verith 전용 owned PG
한 회차를 실행했고 현재 migration head `c35001a7e0001` 위에서 5묶음·parent exit0으로 통과했다.
정확 CreationReceipt에 따른 자기 DB 제거/부재, sourcecopy 제거, source/dependency/origin 후검사도 통과했다.

동일 epoch의 ready A→unknown B에서 Mock count/generation/supplier는 각각2, unknown 보류는100,000,000
nanoUSD의 합성 장부로 유지됐다. 8개 동의/plan/owner/session/CSRF/Origin 거절은 Flow/binding 추가0이었다.
budget429 직후 fresh SQL의 Flow run/reservation/report/provider slot/period는 모두0이고 이미 commit된
Supervisor binding은 보존됐다. 같은 confirmation key/body의 재진입에서 fake Flow dispatch1·run1·reservation1·
report1·not_called provider slot9·period2를 확인했다. 이후 replay/GET은 의미 호출·예약·fake dispatch 추가0이며
unknown 직후와 최종 의미 epoch SHA가 일치했다. 예약 slot9를 외부9회 호출로 집계하지 않는다.

최초 준비는 private PreparationService 경로이고 이후 조회·동의·저장/보고서 조회는 실제 인증 Backend ASGI다.
실제 Next/BFF·브라우저·Google·KIS/OpenAI E2E는 아니다. 이번 합성 회차의 실제 credential/provider/Google 호출과
새 실제 비용 예약은0이다. 기존 실제 생성/청구의 미확정 상태와 보수 예약0.25는 별도 이력이며 변경하지 않았다.

기존 staging/fetch의 실행 전 거절 이력은 보존한다. 공유 origin/develop 객체가 최신이라 이번 fetch 재시도는
필요하지 않았다. 새 직접 요청 범위에서 필수 검증·독립 리뷰 뒤 정확4파일 stage/commit/push/Draft PR을
정식 심사하며, 이 기록 시점에는 게시 전이다. 새 거절은 해당 단계에서 중단하고 우회하지 않는다. Ready/merge는 하지 않는다.

최신 정확4파일·고정9파일·AI32·직접 로그3개의 최종 독립 읽기 대조를 완료했고 미해결 blocker는 없었다.
이는 source/로그 검토이며 독립 검사 재실행은 아니다. 게시 심사와 원격 exact-head CI는 이후 별도 단계다.

### CF037 PR CI 호환 보완

첫 PR CI는 meaning assembly를 포함한 앞선 보호 검사를 통과했으나 Technical owned self의 기존 조건 문자열 검사에서 실패했다. DB-only 조건에 추가한 flag가 기존 두 flag 사이에 놓여 생긴 소스 호환 문제였다. 여섯 조건의 동일한 OR 항을 순서만 조정해 기존 인접 표현과 모든 새 분기를 함께 보존했다. 보호 검사나 assertion은 변경하지 않았다. 보완 후 보호 Technical owned self 3개와 meaning assembly unit 103개가 통과했고 guard 위반은 0, 검사 소유 임시 root는 제거됐다. 최초 로컬 비상승 실행은 OS canary에서 exit 78로 중단되어 worker가 시작되지 않았으며, 기존 보호를 유지한 정식 실행에서 통과했다. 실제 PG 검증은 앞선 회차의 근거이며 이번 동치 순서 보완으로 새 DB를 생성하지 않았다.
