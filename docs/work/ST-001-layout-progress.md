# ST-001 · 전체 폴더 재배치 진행 기록

## 현재 기준과 상태

- **후속 정본 수신 v1.17:** SHA-256 `101fd8fa6b883333b0162f4d7e05827188f2c8908ffd1b7e2717037b139a2f71`, inventory SHA-256 `0ff8ea26908b89c68359f1139e3de331993990994807751e1fa5b403c497a5df`. 아래 v1.15는 구조 적용 기준이며 후속 type/lint와 build 차단의 현재 정책은 v1.17 0.12절을 따른다.

- **현재 최종 적용:** ST-001 v1.15 SHA-256 `dbcfc1880d872d005958d0b4ff80dcc9ed23455b40046651cb41442acd7b71cb`, inventory SHA-256 `b965e9566eb501c4856513a6650b51786d93c87df652152a971c6d72929307dc`. Flow 최종3의 명시 설정과 마지막 정리가 승인·적용됐다. **536개 이동 행 처리 = target525개 존재 + 이동 후 marker 제거 disposition11개**, retain marker 제거9개 별도. 공개 파일838개가 정확한 최종 예상 집합과 일치한다.

- **후속 현재 상태:** 아래 Technical 최종 보완 절에서 self 22/unit 37·standalone type·대상 lint가 새로 통과했다. Mac 3-B build/HTTP는 입력 경계 차단을 유지하며, 별도 승인된 clean Docker에서는 정식 build(생성 타입 포함)와 실제 Next+fake Backend HTTP 3개가 통과했다(아래 담당자 실행 증거). 별도 네이티브 담당자의 실제 격리 PG 합성 검사 2개는 통과했으며 나머지 DB suite와 실제 Google은 미검증이다. 실제 AI는 별도 승인한 요청 1회가 인증 단계 HTTP 401로 종료되어 생성물 미검증이다(아래 후속 증거). 구조 완료 시점의 type 거절·lint 오류는 당시 이력이다.

- **구조 정리 완료 시점의 직접 검사:** Backend self13/13·선택unit402/402, Frontend self21/21·unit36/36, exit0·예상 밖 guard/skip0·각 자기 임시 root 제거. 기존 최종 type 도구 거절·lint 기존any2·build/HTTP/AI 전체 런타임 미검증은 그대로다. 아래533/Flow3/외부placeholder 보류 문장은 그 시점 이력이며 최신 승인으로 해소됐다. 구조 적용 완료와 전체 기능/실환경 수용을 구분한다.

> **v1.14 당시 외부 미확인 변경 이력:** 앞선858개 exact 집합 검사 이후 retain 대상 `frontend/src/app/reports/flow/[reportId]/.gitkeep`가 없어져 현재 공개 집합은857개다. Git은0-byte tracked 파일 삭제로 표시한다. 같은 디렉터리의 tracked page.tsx가 실제 존재하므로 폴더 추적/기능에 필요하지 않다. 삭제 주체는 미확인이고 개발 작업에 귀속하거나 임의 복원/추가 삭제하지 않는다. 이 파일은 나머지 검증/결과나 사용자 결정의 선행조건이 아니며 완료된533 이동·원래23 보존과 분리한다. 앞선858 검사는 그 시점 이력이고 다른 예상 밖 추가/누락은0이다.

- 당시 정본 **v1.14** SHA-256 `52629edae90d2c524a303a9b0a7110868faa15da0154829aa6e16bc367845ad0`, inventory SHA-256 `8b6d64a6467cf7b92fc42a5ea276f9f1cd6043a943a83e7d8953af3ab8974078`. 기존 v1.12 shim/DB3·v1.13 bat4 계약은 유지하며 ignore5/PS1 참조1만 보완했다.

- 당시 확인 **2026-11-08 05:39 KST**. 정본 v1.13 SHA-256 `21866b5a970ba00d606e2d767694d2ff119d5a9d4a55d909f0a662e3cf29bb58`, inventory SHA-256 `4c4b6a5121e9172f6223ca58bd7b5bdb9569188fb3664548cfe994737ba70418`. v1.12 shim 제거 계약은 유지하고 Windows script 정확한 참조 4개만 보완했다.

- 최종 shim 제거 우선 정본 **v1.12** SHA-256 `88e4758f68e1f1e5a1daebc0f5dfa51bcba97276e5c7c1d52656b20643337560`, 인벤토리 SHA-256 `e3d3ffd227c97873b001fba022908036c2bf7f4882ca6342fc1237a52ae43d06`. v1.11 helper 안은 미적용 취소다. 이전 v1.10 매핑/실행 이력과 manifest/CF는 보존한다.

- 설계/이동 당시 지시서 v1.10 SHA-256 `ff6d0e5a5bcbbf444ffe7ed0bf9ede10de0380cd8743ec15dc41c34cd1ace1e6`. B02 착수 당시 v1.9/hash `1877bb48b0b703969330e1c94affcf68d1b48dc00ef1ac00483915c1e5776b28`는 이력이다.
- 현재 부속 전체 파일표 v1.10 SHA-256 `36458c0b5c2bcc044c0dd459bab7559790e7bcaae8baa505320689df92802d2a`. v1.9/hash `fd05c212e85fec9bd39fe54bdb818710b7f3122d17b4c1d8349438be7288907c`는 원형 보존됐다. 변경은 Fundamental/data Python source 6개의 참조 수정 가능 표시와 문구/진척 정정뿐이며 자원/권한 확대가 아니다.
- 같은 branch `chore/safe-backend-frontend-checks`, HEAD/base `7df12403848e480f223767232540d4c2c055ba5e`. staged 0. 새 branch/fetch/reset/stash/git/gh 변경 액션 없음.
- 현재 실제 이동은 **533/536개**다: Backend 59개, AI 428개, Frontend 46개. AI Flow dotenv 실제 구현 3개만 미이동이며 나머지 실제 이동·현재 참조 정리를 검증 중이다. Backend 59개는 독립 source-only 수용을 마쳤고 AI Flow 후속 25개와 Technical 111개 및 Frontend 46개는 독립 source-only 수용됐다. 실제 AI runtime 및 최종 Frontend type/build/HTTP 수용은 별개다.
- 총 857개 분류: 이동 계획 536개, 설계상 유지 321개. 첫 4-A 6개는 실제 이동·보호 실행·독립 source-only 수용 완료다. B02 2개도 실제 이동·보호 실행·독립 source-only 수용을 마쳤다. FE-01 9개는 실제 이동과 아래 직접 검증을 마쳤으며 최종 독립 정적 재검토도 완료됐다. B03 16개는 실제 이동·보호 회귀·독립 정적 수용을 마쳤다. B04 5개는 실제 이동·보호 회귀·독립 정적 수용을 마쳤다. B05 5개는 실제 이동·보호 회귀·독립 정적 수용을 마쳤다. B06 4개는 실제 이동·보호 회귀·독립 정적 수용을 마쳤다. **전체 재구성 완료가 아니다.**
- 기존 [4-A 기록](ST-001-stage-4-A.md)과 [3-B 기록](ST-001-stage-3-B.md)은 당시 source/hash/실행 사실로 보존한다. 후속 이동으로 기존 해시가 달라지면 그 과거 기록을 새 결과로 덮어쓰지 않는다.
- 기존 private 환경·데이터·DB/volume·runtime history/cache/traces/output을 읽거나 이동하지 않는다. 설치·외부 HTTP/Google/AI·DB·배포·원본 앱 서버는 실행하지 않는다.

## B02 · Flow application / infrastructure

| 기존 호환 경로 | 실제 구현 |
|---|---|
| `backend/src/api/services/flow_report_service.py` | `backend/src/modules/flow/application/report_service.py` |
| `backend/src/api/repositories/flow_report_repository.py` | `backend/src/modules/flow/infrastructure/report_repository.py` |

batch 전에 최신 원본과 정확한 영향 consumer의 bytes/hash를 자기 임시 보존본으로 확보했다. 새 위치에는 실제 구현을, 구 경로에는 명시적 export만 두었다. 전체 module alias/wildcard/sys.path 변경은 없다. import 제외 실행 본문 AST가 같아 SQL/owner/인증/transaction 계산 로직이 바뀌지 않았다.

known test/mock은 canonical `report_service`/`report_repository` 모듈을 patch한다. 구 shim의 전역 재할당이 canonical 구현에 자동 전달된다고 가정하지 않는다. runtime route/common reports·관리 script·단위/통합 테스트의 정확한 import 소비자를 갱신했으며 관리 script나 통합 DB 검사는 실행하지 않았다. 기존 안전 입구에는 새 구현 2개의 exact NEW 사본 입력만 추가했다. OS/FS/network/HMAC/profile/audit 예외 확대는 없다.

공식 `require_escalated`의 별도 workload 승인으로 기존 env-free `-I -S` Backend 입구를 실행했다.

```sh
/usr/bin/env -i LANG=en_US.UTF-8 TZ=UTC /Users/parkjinhee/AI/verith_refactor/verith/backend/.venv/bin/python -I -S backend/scripts/check_safe.py self-test
/usr/bin/env -i LANG=en_US.UTF-8 TZ=UTC /Users/parkjinhee/AI/verith_refactor/verith/backend/.venv/bin/python -I -S backend/scripts/check_safe.py unit
```

- self-test: 10개 실행/통과, exit 0, 자기 임시 root 제거.
- unit: 고정 6개 파일 collected 252/passed 252, guard 위반 0, skip/누락 0, exit 0, 자기 임시 root 제거. 기존 244개 + 4-A 7개 + B02 canonical module-global patch 1개다.
- 새 회귀는 구/신 class·함수 동일성과 canonical origin, 실제 class method의 globals 및 repository 모듈 patch 연결을 확인한다. 기존 OpenAPI·공개 Flow JSON schema·고정 payload의 이동 전 해시 비교도 계속 통과한다.
- 직접 정적 검증: 2개 구현의 import 제외 AST 동일. 실제 DB SQL 실행/경합이나 실제 인증/AI 검증으로 확대하지 않는다.
- 독립 source-only 검토: 수용. 작성/조율자는 새 구현과 구 shim·known 소비자 canonical import·SQL/auth/transaction AST 및 전역 patch 회귀/NEW2만의 변경을 확인했고 차단 결함은 없었다. 별도 테스트 재실행은 하지 않았으며 위 10/252는 개발자의 직접 실행이다.

## FE-01 · 공통 UI/계약/helper 실제 이동

9개 파일은 현재 최신 bytes 그대로 이동했고 exports/directives/JSX/type·공개 URL·client/server 경계는 바꾸지 않았다. source consumer 30개와 ports 단위의 VM load 경로를 정확히 갱신했다. 로컬 source import 136개가 실제 새 경로로 해석된다. UI 전체 렌더 또는 Frontend 전체 수용을 의미하지 않는다.

| source | 실제 target |
|---|---|
| `frontend/src/api/backend.ts` | `frontend/src/shared/api/backend.ts` |
| `frontend/src/components/common/.gitkeep` | `frontend/src/shared/ui/.gitkeep` |
| `frontend/src/components/ui/app-shell.tsx` | `frontend/src/shared/ui/app-shell.tsx` |
| `frontend/src/components/ui/section-card.tsx` | `frontend/src/shared/ui/section-card.tsx` |
| `frontend/src/components/ui/status-badge.tsx` | `frontend/src/shared/ui/status-badge.tsx` |
| `frontend/src/lib/bold-text.tsx` | `frontend/src/shared/ui/bold-text.tsx` |
| `frontend/src/lib/format.ts` | `frontend/src/shared/lib/format.ts` |
| `frontend/src/types/archive.ts` | `frontend/src/shared/contracts/report.ts` |
| `frontend/src/utils/.gitkeep` | `frontend/src/shared/lib/.gitkeep` |

검사 사본은 index metadata와 정확한 9개 relocation 표의 교집합을 사용한다. 누락된 파일을 일반적으로 건너뛰거나 임의 untracked tree를 추가하지 않는다. type 모드는 자기 사본에 설치 Next의 writeAppTypeDeclarations.js와 같은 `next`/`next/image-types/global` 표준 참조 2줄만 준비했다. 이는 실제 Next 기본 core/image typings을 사용하는 **standalone tsc** 검사다. 설치 Next의 전체 생성 파일에는 `.next/types/routes.d.ts` import가 있고 strictRouteTypes 설정에 따라 validator/cache-life/link도 추가되므로, generated route/typegen 전체 동등 검증이나 full Next build 통과가 아니다. 가짜 routes/any stub·typegen/build 실행은 추가하지 않았다. 원본 ignored next-env 파일을 읽지 않았으며 제품 config/의존성 version/lock 변경은 없다. 대상 lint에는 이 batch의 새 TS/TSX 7개를 명시 포함했다.

공통 public 시작은 `env -i LANG=en_US.UTF-8 TZ=UTC OPENSSL_CONF=/dev/null`과 검증된 절대 Node, `frontend/scripts/check-local-ports.mjs`다. 각 self-test/unit/type/lint workload를 별도 공식 require_escalated로 실행했다. 모든 검사에는 OS native 양성/음성 사전검사·CJS guard·자기 임시 사본/자원 정리가 적용됐다.

| 실행 시점/대상 | 실제 결과 |
|---|---|
| 이동 직후 self-test | 21/21, exit 0, 자기 root 제거 |
| 이동 직후 unit | 4개 파일 모두 exit 0, worker 4/exit record 4/partial 0, 자기 root 제거 |
| 독립 type | tsc --noEmit --incremental false, exit 0, guard 위반 0, 자기 root 제거. 최종 TS/TSX bytes와 같으며 아래 lint-only guard 변수명 수정 전 실행이다. |
| 최초 대상 lint | 기존 CJS guard HTTP loop 지역명 module의 Next no-assign-module-variable 오류 1개와 controller unused os 경고 1개. child 1/controller 78, guard 위반 0, 자기 root 제거. 실제 lint 실패로 보존한다. |
| 최소 수정 | HTTP loop 로컬 module→transportModule alpha-rename만 수행했다. 역치환하면 loop 원본 bytes가 같다. 미사용 os import 1개를 제거했다. 규칙/파일 제외·정책/FS/OS/network/HMAC/endpoint/TLS 의미 변경은 없다. |
| 최종 self-test | tests 21/pass 21/fail 0/cancelled 0/skipped 0/todo 0, exit 0, 자기 root 제거 |
| 최종 unit | disabled-routes 10/10 + session-proxy 2/2 + ports 3/3 + safety 21/21 = **36/36**, 4개 파일, fail/cancelled/skipped/todo 모두 0. exit 0, worker 4/exit record 4/partial 0, unexpected guard 위반 0, 자기 root 제거 |
| 최종 대상 lint | exit 0, error/warning 0, guard 위반 0, 자기 root 제거. 전체 repository lint가 아니라 명시 대상 검사다. |

관측 ledger의 JS rawOriginalDispatches 0은 계측한 JS fs 소비에 한정한다. self/unit의 14개 expected negative와 허용되지 않은 실제 소비 실패를 구분한다. native 전체 관측 성공으로 확대하지 않는다. 기존 build 차단은 변경하지 않았고 build/HTTP를 재시도하지 않았다.

독립 정적 검토는 9개 target bytes·30개 source import-only·136개 참조·public/client/server 경계 보존에서 차단 결함이 없다고 전달받았다. 조율자의 마지막 lint-only delta source 재검토도 완료됐다. HTTP loop의 명칭 역치환 bytes 동일·endpoint/기본 port/거부 의미 불변·미사용 os import만의 제거를 확인했고 차단 결함은 없었다. 작성측의 최종 보고 bytes/hash 대조까지 완료돼 FE-01 독립 정적 수용을 받았다. runtime을 독립 재실행했다고 쓰지 않는다.

### FE-01 실행 source와 보존 checkpoint

최종 self/unit/lint는 아래 같은 controller/guard/safety source에서 실행했다. type은 TS source가 같고 lint-only binding 수정 전 guard/controller에서 수행한 결과다. checkpoint는 공개 코드/검사 source만 담은 자기 임시 보존본이며 실제 credential·원본 private 자료·runtime key는 없다.

| 파일 | 정확한 보존 checkpoint | 사전 SHA-256 | 최종 SHA-256 |
|---|---|---|---|
| `frontend/scripts/check-local-ports.mjs` | `/tmp/verith-restructure-baseline-r38ooouu/FE-01/frontend/scripts/check-local-ports.mjs` | `bc19f2b5363f75ed080b759b4be56f1f111ab93eb6cf5f6c88d45ee91e0ea060` | `a05f550bc8986067bcf2da346340ececc658a8a40bf47b10b65e74659cb23e09` |
| `frontend/scripts/safe-checks-guard.cjs` | `/tmp/verith-restructure-baseline-r38ooouu/FE-01/frontend/scripts/safe-checks-guard.cjs` | `b1912f4a3645c85786b4ff35f6d6b2f96ea7945b8b4e13102bfa1e9bdcab5f2c` | `6b82a520aee8a3866878aa4a7425f16110fd62eb59dd58b4d87e7d273b228575` |
| `frontend/tests/safe-checks.test.mjs` | `/tmp/verith-restructure-baseline-r38ooouu/post-B02/frontend/tests/safe-checks.test.mjs` | `042965137d36ed330ad4b9bf83651bae92e4c70c44f4ef5e3ed18090d22db8c0` | `d8cf49faff37dc55584fee1a2bb108b0a1aa200168cafb765f40849b9c8ff972` |

## B03 · Stocks 16개 실제 이동

client/repository 4개 → infrastructure, parser/정규화/상수 7개 → domain, service 3개 → application, DTO/router 2개 → api로 이동했다. 실제 전체 경로는 아래 전수 표에서 B03으로 추적한다. 옛 경로는 명시 bridge만 남겼고 known consumer는 canonical import를 사용한다. 16개 구현 모두 import를 제외한 실행 AST가 batch 전 최신 bytes와 같다. __file__ 기반 resource 계산은 이 16개에 없다.

검사 후보 중 stock_resolver_semantics/boundary는 실제 DB fixture/seed/transaction 의존이 있어 **선택하지 않았다**. 실행한 뒤 skip한 것이 아니다. source 전체와 import closure를 읽은 순수 3개(test_text_normalize, test_stock_master_parser, test_dart_corp_code_parser) 및 합성 fixture 2개만 exact 사본 입력에 추가했다. 기존 고정 6파일은 그대로 모두 실행한다. 기존 confcutdir=tests/unit를 유지하고 자동 conftest plugin이 tests/unit/conftest.py 밖에 등록되면 수집을 실패시키는 확인을 추가했다. root conftest의 합성 수동 import 회귀는 계속 실행한다. 새로운 원본/FS/OS/network/HMAC 권한은 없다.

- 이동 전 baseline: self 10/10, 선택 9파일 282/282(기존 252 + 순수 parser 30), guard 위반 0, exit 0, 자기 root 제거.
- 이동 후: self 10/10, 선택 9파일 298/298(기존 282 + 객체/origin 16), skip/누락/guard 위반 0, exit 0, 자기 root 제거.
- 실행 명령은 위 B02의 동일 env-free Python -I -S check_safe.py self-test/unit이며 각 workload는 별도 공식 require_escalated 승인을 받았다.
- source AST·canonical 실제 origin/old-new 객체·기존 공개 OpenAPI/JSON schema/payload hash 회귀를 확인했다. 실제 KIS/DART·DB·SQL/권한 통합 성공으로 확대하지 않는다.
- 독립 source-only 검토: 수용. 조율자는 16개 target(9개 bytes 동일/7개 import-only)·전체 AST·영향 stock test/fixture 13개의 기대값 보존과 canonical consumer를 확인했다. runtime/DB/테스트를 독립 재실행하지 않았다. 검토에서 지적한 현재 안내 4파일의 canonical 참조를 갱신하고 local link/diff check를 확인했다. 과거 handoff 이력은 보존한다. 후속 B04를 계속한다.

| B03 최종 검사 source | SHA-256 |
|---|---|
| `backend/scripts/check_safe.py` | `3c26343f1cb2472271dbb5188bda130c1de1923571581ffbaa6fedddafcf135e` |
| `backend/scripts/safe_checks_bootstrap.py` | `c3e547c8adbaa91e352b7c7d1886ea414d36e4779216c7ba0617e43f4f94126e` |
| `backend/tests/safe_checks/test_entry.py` | `55df0abcf9baffe32289573c1819ac7f66e8f6587e50b884486bd7fba2249dc9` |
| `backend/tests/unit/test_flow_contract.py` | `9735b540578b03bc59f648e4cb80fd932fbe080753cd76f27b5630d5d21c6a93` |

## B04 · Technical 5개 실제 이동

AI output 계약 → domain, HTTP DTO/router → api, service → application, repository → infrastructure로 실제 이동했다. 5개 원본은 명시 bridge만 유지하며 known consumer는 canonical import로 바꿨다. 5개 모두 import 제외 AST가 같고 __file__ 계산이 없다. DB model/schema·AI 호출/SQL·HTTP/권한 동작은 변경하지 않았다.

기존 test_technical_read_model.py 전체 593줄과 import/call closure를 감사했다. 동기 순수 테스트 40개는 합성 payload와 미저장 ORM 객체로 projection만 호출하며 session/DB/네트워크 호출이나 root fixture 인자가 없다. 해당 exact 파일 하나를 보호 선택에 추가했다. 기존 고정6 + pure stocks3 + technical1 = 10파일이고 confcutdir/등록 plugin 확인을 유지한다. 실제 test_technical_reports.py DB 검사는 실행하지 않았다.

- 이동 전: 선택 10파일 338/338(기존298 + 순수 projection40), guard0/exit0/자기 root 제거.
- 이동 후: self10/10, 선택 10파일 343/343(기존338 + canonical 객체/origin5), skip/누락/guard0/exit0/자기 root 제거.
- 각 workload는 기존 env-free Python -I -S check_safe.py 입구와 별도 공식 require_escalated를 사용했다. profile/FS/OS/network/HMAC/설치·환경 권한을 확대하지 않았다.
- 기존 전체 Backend OpenAPI·Flow JSON schema·고정 payload hash 비교도 그대로 통과했다. 실제 Technical AI·DB·브라우저 통합 성공으로 확대하지 않는다.
- 독립 source-only 검토: 수용. 조율자는 5개 구현의 AST·명시 bridge·main/deps/known 소비자 및 read-model/archive 테스트 기대값 보존·resource anchor 없음에 차단 결함이 없음을 확인했다. 테스트를 독립 재실행하지 않았다. 검토 지적에 따라 현재 technical_frontend_api_contract의 route/schema/service 참조만 canonical로 바꾸고 과거 handoff는 보존했다. 다음 B05를 계속한다.

| B04 최종 검사 source | SHA-256 |
|---|---|
| `backend/scripts/check_safe.py` | `dc226ba3be2339897824959e1fc983774925e9896e32b08cbfe69d5b3de3fa96` |
| `backend/scripts/safe_checks_bootstrap.py` | `c3e547c8adbaa91e352b7c7d1886ea414d36e4779216c7ba0617e43f4f94126e` |
| `backend/tests/safe_checks/test_entry.py` | `55df0abcf9baffe32289573c1819ac7f66e8f6587e50b884486bd7fba2249dc9` |
| `backend/tests/unit/test_flow_contract.py` | `bbe68c87a2ec0228ded78b88f7ff91da0bd69a8fd13728a61f430f9886fda484` |

## B05 · Fundamental 5개 실제 이동

AI mirror → domain, route/DTO → api, service → application, repository → infrastructure로 실제 이동했다. 원래 5개 경로는 명시 bridge만 남겼다. 최신 원본 대비 import 제외 실행/SQL/상수 AST가 같고 __file__ 기반 자산 계산은 없다. known consumer의 import만 canonical로 연결했다.

기존 test_ai_client.py 전체 60줄/8개는 httpx.MockTransport만 사용함을 감사해 exact 선택에 추가했다. 기존 fixed6·순수 stocks3/technical1과 함께 총 11파일이다. Fundamental DB integration은 실행하지 않았다. 추가 회귀는 canonical 객체/origin 5개와 실제 메모리 transport로 Fundamental POST 경로·payload·200/422/504/503 매핑을 확인하는 4개다. 외부 서버 호출은 없다.

- 이동 전 baseline: 11파일 351/351(기존343 + MockTransport8), guard0/exit0/자기 root 제거.
- 이동 후: self10/10, 11파일 360/360(기존351 + 객체/origin5 + Fundamental transport4), skip/누락/guard0/exit0/자기 root 제거.
- 기존 전체 Backend OpenAPI·Flow 모델 JSON schema·payload baseline 해시 비교도 통과했다. SQL/auth/transaction 의미는 수정하지 않았으며 실제 DB/AI 저장 통합을 검증한 것이 아니다.
- 실행은 기존 env-free Python -I -S check_safe.py self-test/unit의 별도 공식 require_escalated 승인 경로다. FS/OS/network/HMAC 예외·설치·원본 앱 실행은 추가하지 않았다.
- 독립 source-only 검토: 수용. 조율자는 5개 구현 AST·명시 bridge·SQL/transaction/HTTP/error 의미·canonical router 1회와 known consumer 및 memory transport 회귀를 확인했고 차단 결함은 없었다. runtime/DB/AI를 독립 재실행하지 않았다. B06을 이어 수행했다.

| B05 최종 검사 source | SHA-256 |
|---|---|
| `backend/scripts/check_safe.py` | `503f7c2805ff5bfd3572b920ae506416624465c03b00f0735fbfae36914b124d` |
| `backend/scripts/safe_checks_bootstrap.py` | `c3e547c8adbaa91e352b7c7d1886ea414d36e4779216c7ba0617e43f4f94126e` |
| `backend/tests/safe_checks/test_entry.py` | `55df0abcf9baffe32289573c1819ac7f66e8f6587e50b884486bd7fba2249dc9` |
| `backend/tests/unit/test_flow_contract.py` | `d8506f94c65da000a57adcb447bc089356295a41d745e5ff8f235b392d9664e9` |

## B06 · Industry 4개 실제 이동

Industry DTO/router → api, service → application, repository → infrastructure로 실제 4개를 이동했다. 구 경로는 명시 bridge만 있고 known consumer는 canonical import로 갱신했다. 4개 구현의 import 제외 AST·SQL/transaction/HTTP/오류 본문은 동일하고 __file__ 기반 자산 계산이 없다.

직전 B05의 360개 통과 source가 B06 이동 전 기준이다(동일 baseline 재사용이며 새로 실행했다고 표시하지 않는다). 추가 검증은 canonical 객체/origin 4개와 memory MockTransport를 사용한 analyze/render 각각 200/422/504/503의 8개다. HTML은 합성 Response text이며 실제 렌더 서버·DB·외부 AI/HTTP 호출을 하지 않았다. 기존 test_industry_reports.py의 실제 DB integration은 선택하지 않았다.

- 이동 후 self10/10, 선택 11파일 372/372(기존360+객체/origin4+memory transport8), skip/누락/guard0/exit0, 자기 root 제거.
- 기존 전체 OpenAPI·Flow JSON schema·고정 payload hash도 통과했다. 기존 env-free Python -I -S 입구 self-test/unit을 workload별 공식 require_escalated로 실행했고 FS/OS/network/HMAC 정책을 확대하지 않았다.
- 독립 source-only 검토: 수용. 작성측/조율자는 4개 AST·명시 bridge·router 1회·known consumer 및 memory transport 계약에 차단 결함이 없음을 확인했다. 당시 source4SHA도 실제 bytes와 일치했고 runtime/DB/AI/HTML을 독립 재실행하지 않았다. 360 baseline 재사용 표시는 그대로 보존한다.

| B06 최종 검사 source | SHA-256 |
|---|---|
| `backend/scripts/check_safe.py` | `c65cc61c86891e2505a8d6cde8e66465a3dbbd0efc2b3587e593b687275d5182` |
| `backend/scripts/safe_checks_bootstrap.py` | `c3e547c8adbaa91e352b7c7d1886ea414d36e4779216c7ba0617e43f4f94126e` |
| `backend/tests/safe_checks/test_entry.py` | `55df0abcf9baffe32289573c1819ac7f66e8f6587e50b884486bd7fba2249dc9` |
| `backend/tests/unit/test_flow_contract.py` | `fdc813c9e17a321e6a2e8126eced1522c400e70576b2a2fb77e518e07f44e1bf` |

## B07 · News 13개 실제 이동

News의 규칙/importance → domain, DTO/router → api, service → application, PostgreSQL/graph repository → infrastructure로 실제 13개를 이동했다. old13은 명시 bridge이며 known consumer는 canonical import다. 13개 전체의 import 제외 AST·SQL/Cypher/transaction·상수·HTTP/오류 본문이 같고 __file__ 기반 자산 계산이 없다.

기존 test_importance.py 전체 58줄/5개와 import closure는 math/표준 dataclass·순수 계산/상수만 사용하므로 exact 보호 선택에 추가했다. News PG/Neo4j 저장/조회/cleanup integration은 선택하지 않았다. 기존 고정6·순수 stocks/technical·MockTransport를 포함해 총 12파일이다.

- 이동 전 baseline 12파일 377/377(기존372 + pure importance5), guard0/exit0/자기 root 제거.
- 이동 후 self10/10, 12파일 390/390(기존377 + canonical 객체/origin13), skip/누락/guard0/exit0/자기 root 제거.
- 기존 전체 Backend OpenAPI·Flow JSON schema·고정 payload hash 비교도 통과했다. 실행은 기존 env-free Python -I -S self-test/unit 입구의 workload별 공식 require_escalated다.
- 새 FS/OS/network/HMAC·DB/Neo4j·AI/HTTP·설치 권한은 없고 source 움직임을 실제 News 통합 검증으로 확대하지 않는다.
- 독립 source-only 검토: 수용. 작성측/조율자는 13개 전체 AST·명시 bridge·canonical consumer/graph mock·router 1회·기존 테스트 기대값과 exact 선택/정책 보존을 확인했다. 당시 source4SHA가 실제 bytes와 같았고 테스트를 독립 재실행하지 않았다. 다음 B08을 이어간다.

| B07 최종 검사 source | SHA-256 |
|---|---|
| `backend/scripts/check_safe.py` | `f441b508c3cd64e14ed5032caef140447c50f0365ad12b7ae1420c539e4f484e` |
| `backend/scripts/safe_checks_bootstrap.py` | `c3e547c8adbaa91e352b7c7d1886ea414d36e4779216c7ba0617e43f4f94126e` |
| `backend/tests/safe_checks/test_entry.py` | `55df0abcf9baffe32289573c1819ac7f66e8f6587e50b884486bd7fba2249dc9` |
| `backend/tests/unit/test_flow_contract.py` | `c7c46b019c5783a4a03a66211dde3a090e17efb16e6b9f0cfab43dad1275d25c` |

## B08 · 공통 reports 4개 실제 이동

공통 report/card DTO 2개와 archive/router, 공통 repository 총 4개를 modules/reports의 api/infrastructure로 실제 이동했다. original4는 명시 bridge이며 Flow/다른 기능/known test의 agent_repo와 DTO import를 canonical로 갱신했다. 전체 import 제외 AST·SQL/owner/transaction·응답 본문은 같고 resource 계산이 없다.

직전 B07의 390개 통과 source를 이동 전 기준으로 재사용했다(별도 baseline 재실행으로 표시하지 않는다). 기존 Flow memory archive/owner/손상 검증을 그대로 실행하고, canonical 객체/origin 4개를 추가했다. 실제 PG test_report_archive.py는 실행하지 않았다.

- 이동 후 self10/10, 선택 12파일 394/394(기존390+객체/origin4), skip/누락/guard0/exit0, 자기 root 제거.
- 기존 전체 OpenAPI/Flow 모델 JSON schema·고정 payload hash 비교도 통과했다. 기존 env-free Python -I -S self-test/unit을 workload별 공식 require_escalated로 실행했다.
- FS/OS/network/HMAC/profile 예외·원본 데이터/DB/서비스·설치는 추가하지 않았다. 실제 PG/인가 integration 검증으로 확대하지 않는다.
- 독립 source-only 검토: 수용. 조율자는 3개 bytes 동일/route import-only·SQL/DTO/owner/auth/error 보존·canonical router 1회/같은 Flow provider·consumer 9개 AST와 exact NEW4/identity4를 확인했다. bootstrap/self-test 불변이며 테스트는 독립 재실행하지 않았다. 검토 때 실행 기록이 아직 조회되지 않았다는 시점 차이는 위 실제 실행 결과와 구분한다. B09를 이어간다.

| B08 최종 검사 source | SHA-256 |
|---|---|
| `backend/scripts/check_safe.py` | `23d80e974e3cf777eb9ac23bb19e3a319543a4fb935a8d1890aee2ac50765f5e` |
| `backend/scripts/safe_checks_bootstrap.py` | `c3e547c8adbaa91e352b7c7d1886ea414d36e4779216c7ba0617e43f4f94126e` |
| `backend/tests/safe_checks/test_entry.py` | `55df0abcf9baffe32289573c1819ac7f66e8f6587e50b884486bd7fba2249dc9` |
| `backend/tests/unit/test_flow_contract.py` | `0a8550a588f2a7e20de797b2e207da90fc06a2c30f362674b030cb15c7a92a3b` |

## B09 · Auth 3개 실제 이동

Google OIDC adapter → modules/auth/infrastructure/google_oidc.py, 앱 session service → application/session_service.py, auth router → api/router.py로 실제 3개를 이동했다. old3은 명시 bridge이며 known runtime/test/mock의 module-global patch·reload 소비자는 canonical import/module 문자열로 갱신했다. nonce/PKCE/서명/세션 digest·잠금·Origin/CSRF·cookie·오류 본문/SQL은 import 제외 AST와 같고 resource 계산이 없다.

직전 B08 보호 394개 source가 이동 전 기준이다(재사용이며 baseline을 새로 실행했다고 표시하지 않는다). 기존 서명된 mock OIDC·session failure·boundary/local-port 회귀를 유지하고 canonical 객체/origin3개를 추가했다.

- 이동 후 self10/10, 선택12파일397/397(기존394+객체/origin3), skip/누락/guard0/exit0, 자기 root 제거.
- 전체 OpenAPI·Flow 모델 JSON schema·고정 payload baseline 해시도 그대로 통과했다. 기존 env-free Python -I -S self-test/unit을 workload별 공식 require_escalated로 실행했다.
- 실제 Google 로그인/credentials·DB session·A/B 인가/경합을 재검증하지 않았다. mock/AST 결과를 실제 인증/DB 통합 수용으로 확대하지 않는다. 새로운 FS/OS/network/HMAC/설치/실행 권한도 없다.
- 독립 source-only 검토: 수용. 작성측/조율자는 3개 AST·명시 bridge·canonical router 1회·CSRF/Origin/cookie/session/오류 및 known 소비자 보존과 당시 source4SHA를 확인했다. 테스트를 독립 재실행하지 않았다. 현재 AGENTS/development/책임 지도 인증 참조를 canonical로 바꾸고 링크 검사에서 발견한 이전 FE-01 경로도 함께 정정했다. 역사 문서는 보존했다. 최초 인계 때 임시 기록 생성기가 retain auth/__init__ 행도 move로 처리해 기록 저장이 중단됐고, action=move 필터로 좁게 고친 뒤 실제 B09 절/해시 저장을 재확인했다. 이는 제품/검사 실패가 아니며 runtime 재실행 사유가 아니다. B10을 이어간다.

| B09 최종 검사 source | SHA-256 |
|---|---|
| `backend/scripts/check_safe.py` | `e33d7e59cb9245949fd0977207fd579a86104c9c2764734f0ac70b3338e278e4` |
| `backend/scripts/safe_checks_bootstrap.py` | `c3e547c8adbaa91e352b7c7d1886ea414d36e4779216c7ba0617e43f4f94126e` |
| `backend/tests/safe_checks/test_entry.py` | `55df0abcf9baffe32289573c1819ac7f66e8f6587e50b884486bd7fba2249dc9` |
| `backend/tests/unit/test_flow_contract.py` | `ccfed19f436393b4bcf9c68eebe0207bd25b977a4de4ba342ab879a1e96c61e7` |

## B10 · Shared 3개 실제 이동·Backend 구현 59개 적용

AccessBoundary → shared/http, AI client → shared/infrastructure/clients, config → shared/config로 실제 3개를 이동했다. old3은 명시 bridge, main/deps 및 known runtime/mock/reload 소비자는 canonical import다. 최신 source의 import 제외 실행/상수/오류·HTTP 본문은 같으며 main entry는 src.api.main:app이다. 이로써 Backend 계획의 구현 59개가 모두 새 소유 위치에 있다(전체 AI/Frontend 재배치 완료가 아니다).

config의 old src/api와 new src/shared는 같은 깊이라 parents[2]가 가리키는 Backend root와 .env 경로가 그대로다. 원본 .env는 열지 않았다. google_login_workspace.py의 required source/실제 dotenv 비활성화 대상과 local-port source-inspection·fakeworkspace fixture의 literal src/api/config.py만 src/shared/config.py로 바꿨다. 이 3개 source는 해당 literal 역치환 시 checkpoint와 정확히 같았다.

DB/session·graph driver·Alembic/migration의 mutable_references=false anchor는 HEAD bytes 그대로 보존했다. 이들이 유지한 old src.api.config import는 명시 bridge를 통해 같은 canonical settings를 받으므로 필요한 호환 예외다. ORM/model/migration/데이터를 바꾸지 않았다. 실제 .env/credentials·DB에 접근해 root/singleton을 확인하지 않았다.

- 직전 B09의 397개 보호 통과 source를 이동 전 기준으로 재사용했다(별도 재실행이 아니다).
- 이동 후 self10/10, 선택12파일401/401(기존397+shared 객체/origin3+config root/singleton/dependency1), skip/누락/guard0/exit0, 자기 root 제거.
- 새 singleton 회귀는 보호된 cold-import에서 legacy/canonical Settings/settings·main/auth/db.session settings의 같은 객체와 auth get_session의 동일 함수 및 owned Backend .env 경로 값만 확인한다. config를 hot-reload한 후 모든 이전 from-import binding을 자동 갱신한다는 새 계약이 아니다.
- 기존 전체 OpenAPI/Flow 모델 JSON schema/고정 payload baseline 해시도 통과했다. 기존 env-free Python -I -S self-test/unit을 workload별 공식 require_escalated로 실행했고 FS/OS/network/HMAC 예외·의존성·설치는 늘리지 않았다.
- fakeworkspace 테스트는 source에서 실제 fake .env 파일을 쓰는 fixture가 있어 엄격한 기존 private-path audit와 충돌한다. 이 테스트 자체는 선택/실행하지 않았고 예외를 추가하지 않았다. 실제 거부 결과를 얻은 것으로 표시하지 않는다. 해당 consumer는 exact literal 변경의 정적 비교만 했다. 실제 interactive workspace/Google/DB/migration 검증은 미실행이다.

독립 source-only 검토는 source 59개 전체에 대해 29개 bytes 동일/30개 import-only와 API/SQL·singleton/root/DB anchor 보존을 확인했고 구현 차단 결함이 없다고 전달했다. 실행 self10/unit401은 개발 직접 실행이며 독립 재실행은 아니다. 지적된 현재 6개 안내 문서의 canonical 링크와 modules/shared/compatibility 책임 설명만 갱신하고 local link/diff check를 확인했다. 예시 tree는 예시로, migrations의 유지 import·DART 과거 followup·역사 보고는 그대로다.

다음 AI의 429개 잔여와 Frontend 37개 잔여 실제 이동을 이어간다. AI 런타임 실행은 이미 보호된 Flow model/export 4개 closure와 기존 producer/schema 회귀에 한정한다. pandas/graph/config/LLM/DB/model 초기화를 위한 새 입력·guard/general runner·설치는 추가하지 않는다. 나머지는 실제 이동·AST/import/entry/resource 보존과 런타임 미검증을 분리한다.

| B10 최종 검사 source | SHA-256 |
|---|---|
| `backend/scripts/check_safe.py` | `8ed25190e209530c73cc0fb3b039d5b2752bbb1d6ca10f4bf343c998a4b1657a` |
| `backend/scripts/safe_checks_bootstrap.py` | `c3e547c8adbaa91e352b7c7d1886ea414d36e4779216c7ba0617e43f4f94126e` |
| `backend/tests/safe_checks/test_entry.py` | `55df0abcf9baffe32289573c1819ac7f66e8f6587e50b884486bd7fba2249dc9` |
| `backend/tests/unit/test_flow_contract.py` | `7458c5366b0a70581acb332945aa0cca683d4b5b8fa8711e24eb17284b534e3a` |

## 다음 단위와 검증 제한

B02의 독립 정적 검토를 마치고 FE-01 공통 UI/계약/helper 9개를 실제 이동했다. 다음 Backend·AI·Frontend batch를 이어간다. 이전 Frontend build exit 78·HTTP/type/lint 미실행은 3-B 당시 결과로 보존하며 Python 이동의 선행조건이 아니다. 현재 type/대상 lint는 아래 FE-01에서 직접 실행해 통과했고 build/HTTP는 여전히 미실행/차단 이력이다. 새 Frontend type/lint는 exact relocation 입력과 실제 설치 declaration/guard를 확인한 자기 사본에서만 실행한다. 새 읽기/OS/network 권한이나 build 차단 우회는 하지 않는다.

전체 완료는 아래 모든 move row의 실제 구현/consumer/reference 처리를 끝내고 필요한 최종 검증을 통과한 때다. JSON은 계획이며 표의 계획상 유지도 실제 권한·실서비스 검증 완료가 아니다. 실제 이동·정적 통과·선택 unit·build/HTTP 미검증을 각각 기록한다. 사용자 직접 commit/push/Draft PR 원칙을 유지하며 현재 `git add .` 또는 과거 고정 명령을 사용하지 않는다.

## 전수 경로 진행표

유지 이유·evidence·권한/자원 anchor의 정본은 위 hash의 부속 파일표다. 이 표는 실제 이동 상태를 별도로 추적한다.


## AI Flow 후속 1 · 실제 25개 이동 (2026-11-08 05:15 KST)

application 3개(agent/workflow/validation), domain 3개(signals/verification 2), infrastructure 2개(stock master/render builder), template 1개, tests 15개(테스트 14+fixture 1), 명세 1개를 실제 이동했다. 정확한 source/target은 전수 표에 기록한다. 기존 4-A의 AI 모델/exporter 두 구현과 old shim 두 개는 재이동하거나 덮어쓰지 않았다.

- 이동 전 최신 bytes/hash 보존본: `/tmp/verith-restructure-baseline-r38ooouu/AI-FLOW-1/changes.json`과 그 아래 exact source 사본. 내부 작성 helper의 초기 행 수 assertion(26→정확한 25)과 system Python 3.9의 기존 신문법 AST 파싱 오류는 파일 이동 전 중단이었다. 기존 Backend Python의 비실행 AST 파서로 바꿔 이동했으며 제품 코드/기대값 오류와 구분한다.
- 변경 Python 28개는 import와 테스트 `_SRC` 14개의 동일 ai/src anchor, Supervisor 합성 injected-module 문자열 1개를 제외한 AST가 같다. 테스트 함수·decorator·assertion은 보존됐다. 상대 import 31개는 실제 canonical module/namespace로 해석된다. render builder의 sibling template 관계·template bytes, storage 명세 bytes는 그대로다.
- Supervisor lazy adapter와 주입 mock의 module 경로를 함께 canonical로 바꿨다. 테스트 수집은 전환 중 두 트리 `tests`/`src`를 명시하여 아직 미이동인 다른 feature 테스트를 누락하지 않는다. AI 전체 pytest는 실행하지 않았다. 현재 storage-spec 링크 세 곳만 새 경로로 정정했다.
- 보호 입구의 의도된 old/new origin 문자열 2파일은 일반 import 치환 대상이 아님을 발견해 이번 batch 전 정확한 bytes로 보존했다. 추가 source/FS/OS/network/HMAC 허용은 없다.
- **정확한 보류 3개:** core/kis_client.py, nodes/explain.py, devtools/streamlit_flow_lab.py. 물리 위치와 `load_dotenv(find_dotenv(usecwd=False))`/caller 기반 탐색·prompt/sys.path anchor는 유지한다. 이동한 domain/application 소비 import만 갱신했다. 무인자 loader helper나 탐색 정책 변경은 구현하지 않았다. 작성 측의 source-only 판단을 기다리며 다른 feature 이동은 계속한다.
- 별도 공식 require_escalated의 기존 env-free Backend self-test **10/10**, unit **12파일 collected/passed 401/401**, skip/guard 0, exit 0. 각 자기 임시 root 제거를 실제 확인했다. 명령은 B02에 기록한 self-test/unit과 같다. 이 실행은 기존 pure AI closure 4개의 producer/schema/payload 회귀이며 AI graph/config/수집/LLM·실DB 통과가 아니다.
- 독립 source-only 검토에서 수용됐다. Python 본문/기존 assert 221개·old/canonical pure closure·자원 관계 보존을 확인했으며 독립 런타임 재실행은 아니다. 실제 KIS/HTTP/LLM/모델·AI14개 테스트·전체 build/HTTP는 미실행이며, 새 설치/검사 runner/guard 예외 없이 다음 AI feature 정리를 이어간다.

| 이번 검증 source | SHA-256 |
|---|---|
| `backend/scripts/check_safe.py` | `8ed25190e209530c73cc0fb3b039d5b2752bbb1d6ca10f4bf343c998a4b1657a` |
| `backend/scripts/safe_checks_bootstrap.py` | `c3e547c8adbaa91e352b7c7d1886ea414d36e4779216c7ba0617e43f4f94126e` |
| `backend/tests/safe_checks/test_entry.py` | `55df0abcf9baffe32289573c1819ac7f66e8f6587e50b884486bd7fba2249dc9` |
| `backend/tests/unit/test_flow_contract.py` | `7458c5366b0a70581acb332945aa0cca683d4b5b8fa8711e24eb17284b534e3a` |


## AI Technical · 실제 111개 이동 (2026-11-08 05:22 KST)

기능 root는 유지하고 domain 모델/지표/규칙/해석, application node/orchestration/agent, infrastructure KIS/cache/LLM/trace, API chart/router를 실제 분리했다. 공유 Deadline은 exact 목적지 shared/runtime로 이동했고 전체 알려진 AI 소비자를 함께 갱신했다. 테스트·문서/계약·도해·devtools/scripts도 파일표의 정확한 목적지로 옮겼다. 새 old shim은 만들지 않았고 Technical config와 runtime traces/output/data는 그대로 유지했다.

- 이동 전 checkpoint: `/tmp/verith-restructure-baseline-r38ooouu/AI-TECHNICAL/changes.json`과 exact 원본 사본. move 111개 모두 실제 target에 있고 old source에는 없다. 수정 Python source/consumer 82개의 구문 및 import/module-name 참조·정확한 resource assignment 외 AST가 같다. 기존 함수/검증/assertion/SQL/HTTP/timeout 의미는 바꾸지 않았다. 상대 import 172개가 실제 module/namespace로 해석된다.
- 자기 합성 PurePosixPath 계산 17개를 직접 대조했다. prompt는 원래 feature/prompts로, standalone script/devtool의 import/.env 기준은 원래 ai root로, smoke 출력·KIS TOKEN_CACHE의 SCRIPT_DIR은 원래 ai/src/agents/technical/scripts로 유지한다. 원래 `_find_ai_dir` 구현과 탐색 순서는 그대로이며 실제 `.env`/output/token을 열거나 옮기지 않았다. 테스트의 chart/indicator/regime/synthesis source 검사 디렉터리와 diagnostics script 경로만 새 canonical 위치로 맞췄다.
- main의 공개 Technical router 등록은 한 번이며 경로/method/schema 본문은 보존했다. dependency factory/늦은 Supervisor adapter·injected mock·monkeypatch/logger 문자열도 새 canonical module로 연결했다. config의 import-time dotenv root/trace path는 이동하지 않았다.
- non-Python 문서/도해 bytes는 이동 시 동일했고 이후 현재 Markdown 링크의 exact 경로 소비자만 갱신했다. 문서 전체를 새 실행 결과로 재작성하지 않았다.
- 검증은 source-only AST/구문/import/resource/bytes 대조 및 diff check다. **Technical pytest/graph/config/모델/KIS/Redis/LLM/실DB/HTTP는 미실행**이다. 기존 보호된 Backend pure AI closure4를 Technical 전체로 확장하지 않았다. 직전 Flow 후속 self10/unit401 결과와 이번 정적 검사를 구분한다. 실제 API/전체 AI 수용이나 full build/HTTP 통과가 아니다.
- 독립 source-only 검토 수용: target111·import binding1248·본문과 기존 테스트 기대값 보존을 확인했다. 최초 P2로 fresh clone에서 옛 TOKEN_CACHE 부모가 없을 수 있음을 확인했고 `TOKEN_CACHE.write_text` 직전에 **`TOKEN_CACHE.parent.mkdir(parents=True, exist_ok=True)` 한 줄**로 기존 소스 디렉터리가 보장하던 존재 조건만 복원했다. 경로/자격/HTTP/캐시 정책은 그대로다. 이 한 줄을 제외한 get_access_token 및 _find_ai_dir/load_credentials/main/save_csv AST는 checkpoint와 같다. 수정 후 독립 source 재검토도 수용됐으며 실제 mkdir/캐시 쓰기/스크립트 실행은 하지 않았다. script/lab CLI 예시와 현재 문서 계약 링크만 새 경로로 정정하고 output 경로는 보존했다. Flow dotenv3의 물리 이동은 별도 보류다.


## FE-02/03·FE-04 · 잔여 37개 실제 이동 (2026-11-08 05:34 KST)

기능 API/type/lib와 placeholder 26개, server-only session/BFF helper 3개, 테스트 7개/가이드 1개를 실제 이동해 **Frontend 전체 move 46개**가 target에 있고 old source는 없다. checkpoint는 `/tmp/verith-restructure-baseline-r38ooouu/FE-02-03/changes.json` 및 `FE-04/changes.json`이다. 원본 최신 bytes를 보존했고 known source·VM loader·현재 문서 소비자만 canonical로 바꿨다.

독립 source-only 검토에서 TS/TSX 80개의 import/re-export 외 본문·export/type-only/directive/server-only/SSR/BFF/Cookie/HTTP 의미, src TS/TSX 80개의 독립 local import 137개(@/ alias 128 + relative 9; external 78은 별도), exact mapping46·fixed/fresh/self/lint·canonical ports 예약 분기와 기존 테스트 기대값 보존을 수용했다. test project root는 새 위치에서 ../../.., integration helper는 ../../helpers, tooling helper는 ../helpers/scripts는 ../../scripts로 조정했다. package/lock/config·Next 규칙 block·CJS guard/OS/network/HMAC 정책은 변경하지 않았다. 독립 재실행이 아니다.

| 실제 실행 단계 | 결과 |
|---|---|
| FE02/03 이동 후 self/unit | self21/21, unit10+2+3+21=36/36, exit0, 각 자기 root 제거 |
| FE04 최종 self 최초 요청 | 자동 검토가 같은 Frontend self-test 미해결 중복 세션을 이유로 **CreateProcess 전 거절**. 명령은 기존 env-free Node check-local-ports.mjs self-test다. 실행0이며 테스트/OS 실패가 아니다. |
| 상태 확인과 self 1회 재요청 | 기본권한 ps/pgrep 조회는 불가했다. 공식 읽기전용 ps PID/PPID/comm만 조회했고 검증 Node/sandbox-exec 실행파일명 필터 결과0을 확인했다. 인자/env/비밀 조회·프로세스 종료는 없다. 이 새 근거에 따른 공식 1회 재요청 승인 뒤 **self21/21**, fail/skip0, exit0, 자기 root 제거 |
| FE04 최종 unit | 4파일 tests/pass 10+2+3+21=**36/36**, fail/cancelled/skipped/todo0, exit0, worker4/exit4/partial0, 예상 밖 guard0·자기 root 제거. 세션13056 종료를 실제 확인 |
| FE04 최종 type | 최초 unit 종료 미확인 이유로 CreateProcess 전 거절. unit exit0/root 제거를 확인한 뒤 공식 1회 재요청도 `requested type check is already running in unresolved session 472` 이유로 거절됐다. 472는 이 요청을 담은 functions 승인대기 cell이며 실제 exec 세션은 생성되지 않았다. **최종 type 실행0/도구 차단**, 추가 재요청 중단. FE01 tsc 통과를 이번 최종 결과로 재사용하지 않는다. |
| FE04 최종 대상 lint | child1/controller78. 기존 Technical type의 any2곳(새 model/types.ts:191,207) no-explicit-any **오류2/경고0**, guard0·worker1/exit1/partial0·자기 root 제거. HEAD의 old types/technical.ts에 있던 두 any 그대로이며 새 타입/규칙 약화나 파일 제외를 하지 않았다. |
| build/HTTP/typegen | 기존 별도 차단을 유지하며 재실행하지 않음. standalone core/image tsc와 full generated-route/typegen도 구분 |

모든 실제 검사 시작은 env -i LANG=en_US.UTF-8 TZ=UTC OPENSSL_CONF=/dev/null과 검증 Node 절대경로 및 check-local-ports.mjs의 workload별 공식 require_escalated 요청이었다. 관측 JS fs 범위와 native 전체 미관측, 예상된 음성 canary와 실제 guard 오류를 구분한다. `.env`·credentials·설치·원본 app/server·실DB·Google·외부AI는 실행/읽지 않았다. 전체 Frontend 구조 적용과 최종 기능/build/HTTP 수용은 같은 뜻이 아니다.

| FE04 최종 검사 source | SHA-256 |
|---|---|
| `frontend/scripts/check-local-ports.mjs` | `ef78b1ed1595376cc9c8fb42292d8f826a9b31ec7e9be2068de1f20522f9c06f` |
| `frontend/scripts/safe-checks-guard.cjs` | `6b82a520aee8a3866878aa4a7425f16110fd62eb59dd58b4d87e7d273b228575` |
| `frontend/tests/tooling/safe-checks.test.mjs` | `6972f351b2ba4a92ca19b0c92273f75851c2c1ba248c420a0999ba5c8e5940be` |

Technical P2 수정 source SHA-256: `9e7653f0087520e8fd32bd861803b381ef3cac04430d26fe4382b8ed69828f18`.


## v1.12 · 옛 compatibility shim 61개 제거

삭제 직전 export-only AST·canonical target·최신 bytes를 확인해 checkpoint `/tmp/verith-restructure-baseline-r38ooouu/SHIM-REMOVAL/changes.json`과 exact 원본 사본으로 보존했다. Backend 59개와 AI Flow 모델/export old 2개만 unlink했고 실제 업무 구현/데이터/미이동 Flow dotenv3은 삭제하지 않았다. 신규 shim은 없다.

- 소비자·producer fixture·AI payload import를 canonical로 갱신했다. DB/session·graph driver·Alembic env **정확한 3개**는 config import만 변경됐고 다른 실행 AST가 같다. 나머지 DB/migration Python 37개·revision/history·schema/data는 변경하지 않았다. 실제 DB/migration은 실행하지 않았다.
- REMOVED_SOURCES exact61만 수집 입력에서 제외했다. FLOW_INPUTS는 canonical models/payload 2개와 현재 bytes hash로 축소하고 namespace/origin 검사도 같은 closure로 정리했다. 일반 missing-file catch·새 FS/OS/network/plugin/HMAC/runner 예외는 없다.
- relocation 전용 9개 test 함수의 old/new 동일성 주장은 canonical module origin·원래 export 존재/소유·old source 부재로 대체했다. 원래 API/path/status/schema/payload/owner·CSRF·오류/SQL/global patch 기대는 보존했다. 기존 singleton/root/get_session와 실제 service globals patch 검사는 유지했다. 변경 node 이름 대응은 checkpoint `renamed_node_ids`에 있다. 삭제를 성공으로 숨기는 skip/xfail은 없다.
- 삭제 직후 self10/10·unit401/401 통과. 이후 relocation node 이름 정정 및 current copied Python의 stale-import 검사1개 추가 후 **최종 unit 12파일 402/402**, skip/guard0, exit0, 자기 root 제거를 직접 확인했다. 원래 244개 및 공개 OpenAPI/JSON schema/payload hash 비교는 유지한다. B10의 이전401을 제거 후 결과로 재사용하지 않았다. 명령은 기존 env-free -I -S check_safe.py self-test/unit이며 workload별 공식 require_escalated 경로였다.
- 독립 source-only 수용: old61 모두 export-only·정확 삭제, canonical 구현31 import-only/30 bytes 동일, Python532개의 stale old import0·DB3 import-only·동결37·export map 및 기존 행동 AST/guard 경계 보존을 확인했다. runtime을 독립 재실행한 것은 아니다. 최신 추가 stale-import 회귀도 source 검토와 위402 실행으로 구분한다. 현재 Backend 설명/DSN 링크 세 곳은 shim 제거 후 상태로 정정했다.

| 제거 후 최종 검증 source | SHA-256 |
|---|---|
| `backend/scripts/check_safe.py` | `75503088a172610524ba292422ca250cd2f0ccc5b69b5fb5af43f14480ccfb72` |
| `backend/scripts/safe_checks_bootstrap.py` | `89966fd3a5ad39068315894aee2be9afda7303517a99fc9ef1293848f38fe223` |
| `backend/tests/safe_checks/test_entry.py` | `700d8c6373988eb647eff0438ecb4b19c3502d78e9d710997ff53b5ed02b6a09` |
| `backend/tests/unit/test_flow_contract.py` | `458d76b5240a50b4bd66092af71943fbe89279bfafe4d52b4f6262c9b6b18792` |

## AI Fundamental · 실제 108개 이동

application node/해석/계획·domain 계약/비율·infrastructure data/retrieval/LLM/history·API 직렬화/렌더, scripts/examples/tests/docs를 exact 매핑대로 옮겼다. checkpoint는 `/tmp/verith-restructure-baseline-r38ooouu/AI-FUNDAMENTAL/changes.json`과 `current-target-hashes.json`이다. source/consumer Python94개의 구문·import/module 참조·9개 resource assignment 외 AST/기존 기대값을 대조했고 relative import103개가 연결된다. 합성 경로 **12개**는 기존 cache/history/api_test/out root와 이동한 samples/fixtures에 정확히 대응한다. config는 원위치·dotenv/DB alias 의미 그대로다.

독립 검토 P2는 fresh clone에서 옛 source 디렉터리의 존재가 사라져 보존한 cache/out 부모가 없을 수 있다는 정확한 5곳이다. infrastructure/data/cache.py와 scripts/fundamental/{batch_demo,bps_probe,dart_surface_probe,export_graph}.py의 기존 mkdir(exist_ok=True)에 **parents=True만** 추가했다. checkpoint `FUNDAMENTAL-P2`와 AST 대조에서 그 5개 keyword 외 차이0을 확인했다. 실제 mkdir/cache/output/API/스크립트 실행은0이며 수정 후 독립 source 재검토도 수용됐다. Technical의 동일 원인 한 줄 수정과 구분한다.

v1.13에서 run_checks.bat 한 파일의 frozen 표시 오류가 해소됐다. pytest 대상1+module3의 exact 참조4개만 바꿨고 역치환하면 이전 bytes/줄바꿈 그대로다. C:\verith cwd/인터프리터·codepage·실행순서/errorlevel/exit·setlocal/endlocal·옛 api_test/out/summary 출력 안내는 보존했다. Windows/bat·sample 생성·DART/DB/Qwen/LLM/AI 전체 pytest는 미실행이다. 현재 CLI/doc 링크만 새 canonical로 맞췄다.

## AI Industry · 실제 24개 이동

application·domain·infrastructure collection/extraction/graph·API report/router와 tests/docs/example을 옮겼다. checkpoint는 `/tmp/verith-restructure-baseline-r38ooouu/AI-INDUSTRY/changes.json`이다. Python22개의 import/module 참조 및 test AI_ROOT/EXAMPLE_PAYLOAD exact2개 외 AST/기대값이 같다. template HTML/support.js의 sibling 관계와 bytes를 유지하고 example은 examples/industry/report로 연결했다. CLI/inline subprocess import의 exact module 참조도 canonical로 정정했다. main/API body·JSON/검증 의미를 변경하지 않았다. 실제 Neo4j/DART/LLM/HTML 렌더/AI pytest/API는 미실행이며 독립 source-only 검토에서 수용됐다.

## AI News · 실제 120개 이동

application ingest/query/report/scheduler·domain models/rules·infrastructure Backend/RSS/LLM adapters, tests/conftest·docs/evals/examples·devtool을 실제 이동했다. checkpoint는 `/tmp/verith-restructure-baseline-r38ooouu/AI-NEWS/changes.json`이다. Python96개의 import/module 참조와 demo의 동일 ai root 보정1개 외 AST/기존 기대값이 같다. 비 Python bytes는 이동 시 그대로이며 source 참조/현재 문서 링크만 정정한다. config와 실제 data/cache/history/권한은 그대로다. 실제 RSS/Backend/Neo4j/LLM/eval/모델/AI pytest는 실행하지 않았으며 독립 source-only 검토에서 수용됐다.

## AI Supervisor/shared · 실제 38개 이동

Supervisor application planning/execution/runtime, domain contracts/policies/rewrite, infrastructure Backend/DART/observer와 API, tests/devtool/scripts/docs를 옮겼다. 공통 오류는 shared/api/errors.py로 이동했고 main의 동일 handler/router 등록과 dependency factory도 canonical로 연결했다. checkpoint는 `/tmp/verith-restructure-baseline-r38ooouu/AI-SUPERVISOR/changes.json`이다. Python42개의 import/module 참조와 exact resource3개 외 본문/기대값이 같다. devtool ai root는 그대로고 DART snapshot은 원래 supervisor/planning/data 파일을 계속 가리킨다. **실제 snapshot을 열거나 이동하지 않았다.** 입력 argv/output은 그대로다. graph·계획·AI adapter/외부 Backend·DART·모델·AI pytest/HTTP는 미실행이며 독립 source-only 검토에서 수용됐다.

## 전수 적용 후 현재 검증·잔여

- inventory move target **533/536** 존재, old source 제거/실제 구현 소유를 대조했다. retain321은 원위치 anchor·source/resource 예외이며 이동 수에 포함하지 않는다. 남은 Flow dotenv3은 기존 실제 구현/탐색 caller·인자를 유지한 보류다. credential 탐색 정책을 임의 바꾸거나 옛 helper/shim을 만들지 않는다.
- 현재 AI public Python의 local import statement **1,061개**를 비실행 AST로 해석해 unresolved0·삭제 source import0을 확인했다. 첫 자체 checker는 __init__ package 계산 오류로2건을 잘못 표시했으나 checker만 정정해0임을 확인했으며 제품 변경/실행 실패가 아니다. 이 수치는 독립 binding count나 런타임 import 성공과 다르다.
- 모든 AI 테스트가 tests/로 이동해 pyproject testpaths를 최종 ["tests"]로 맞췄다. 중간 ["tests","src"]는 단계적 이동 때의 수집 누락 방지 이력이다. dependency/package/lock version은 바꾸지 않았다. 전체 AI pytest는 실행하지 않는다.
- 새 source CLI/doc 경로, 실행 entry/import/__file__/상대 자원 의미를 정적으로 대조 중이다. protected Backend402·Frontend36과 실제 AI runtime·최종 type/build/HTTP 미완료를 나눠 기록한다. 기존 private·data/volume·실행 자원·Git stage/commit/push/PR는 변경하지 않았다.


## 마지막 참조·추적 보완과 최종 정적 점검

- Technical test_agent_entrypoint의 static boundary whitelist/required-import 기대가 옛 bare module명이라 이동 후 실패할 수 있음을 독립 정적으로 발견했다. domain.models.contracts·infrastructure.observability.trace_logger·infrastructure.cache_service·shared.runtime.deadline·orchestration[.technical_supervisor]의 **module identity만** 정정했다. import 수집 방식·허용 항목 수·required-delegation·나머지 assertions는 그대로다. checkpoint `TECHNICAL-BOUNDARY-REFERENCES`를 보존했다. 앱 import 없이 AST의 같은 node.module 집계/부분집합/필수 조건을 직접 대조했으며 AI pytest 통과로 주장하지 않는다. 최종 source-only 재검토에서 import/whitelist 8개 일치·필수 계약/위임 관계 보존과 정확한 identity 치환 외 helper/test AST 불변을 확인해 수용됐다. 독립 런타임 재실행은 아니다.
- v1.14의 ai/.gitignore에 tracked goldset의 새 target5 negation만 추가했다. root .gitignore·traces/·일반 *.jsonl은 그대로다. 정확5는 check-ignore --no-index에서 제외 해제, 가상의 다른 runtime JSONL/trace3은 계속 제외됨을 읽기전용 규칙으로 검증했다. 자료 생성/내용변경/stage/force-add는0이다.
- start_news_scheduler.ps1의 -m module1개만 canonical scheduling package로 바꿨고 역치환 bytes/줄바꿈 동일을 확인했다. PowerShell/Windows/scheduler는 실행하지 않았다. checkpoint `V1-14-REFERENCES`다.
- Fundamental guide2/README의 현재 pytest/module CLI, Supervisor의 실제 layer/router/smoke·devtool launch와 문서 위치, News CLAUDE의 같은 책임 규칙/현재 경로를 정정했다. 실제 유지하는 output/cache/snapshot root와 역사 결과는 바꾸지 않았다.
- 정확한 old source 부모 중 **빈 디렉터리73개만 atomic rmdir**로 정리했다. 재귀삭제/데이터 열람은 없고 nonempty·retained·ignored 파일이 있는 폴더는 그대로 둔다. 보호된 original dirty23개 중 원래 manifest/3-A/3-B history·Frontend package·safe-http5개는 이전 bytes와 같고, 나머지18개는 승인된 경로/현재 안내/입구 수정이다. 원본 checkpoint23개 SHA가 모두 보존됐다는 독립 확인과 각 delta의 행동 보존 검토를 구분한다.
- 선언상 immutable retained public 파일83개를 직접 대조했다. 원래 dirty였던 manifest/history는 HEAD로 덮어쓰지 않고 시작 snapshot SHA로 비교했고 나머지는 HEAD bytes로 비교했다. 최초 자체 checker가 manifest를 HEAD로 비교해 중단한 것은 기준 선택 오류였으며 올바른 원래 dirty baseline으로 재확인했다.
- 현재/신규 Markdown 로컬 링크301개 후보 중 실제 파일 경로300개가 존재한다. 나머지1개는 tasks/03_extract.md 코드 예시의 `list[EventCandidate](title+confidence)`를 링크 regex가 잘못 잡은 것이며 파일 링크가 아니다. 기존 명세 코드는 변경하지 않는다. anchor·전수 source 최종 점검은 계속하며 과거 immutable 보고의 옛 path literal은 현재 consumer로 집계하지 않는다.
- 최종 직접 점검에서 public 현재 파일 **858개**가 exact 예상 집합과 일치하고, retain321·이동533·원위치 보류3 존재 및 예상 밖 파일0·이동 target ignore0·staged0을 확인했다. Python532 구문 검사가 통과했다. fenced/inline code를 제외한 현재/신규 Markdown64파일의 실제 local path300·anchor13 오류0이다.
- 현재 소유한 retained feature guide와 Backend 현재 문서를 추가한 최종 확장 링크 검사 **Markdown77개/local path359/anchor13 오류0**도 통과했다. 앞의64/300은 그때의 좁은 검사 범위다. 마지막 News 지침은 통상 feature-only 범위를 삭제하지 않고 이번 ST 전체 이전의 명시 예외와 현재 docs/services 경로만 구분했다.
- 533개 실제 target의 최종 hashes는 각 checkpoint의 current-target-hashes.json으로 보관한다. 이는 비민감 공개 source 검사 증거이며 실제 인증/AI/DB 영수증이 아니다. Git/gh 변경·외부 호출·설치·실서비스/데이터 조작은0이다.

## v1.14 당시 재개 조건과 사용자 검토 초안 (이력)

현재 소유 범위에서 독립 가능한 이동/정적 검사·최소 수정·재검토는 마쳤다. 전체 완료나 commit 준비 완료가 아니다. 실제 후속 정책 결정은 아래 Flow 3개의 credential caller 탐색뿐이다. 외부 미확인 placeholder 삭제는 비차단 참고로 분리한다.

1. Flow **core/kis_client.py → infrastructure/kis_client.py**, **nodes/explain.py → infrastructure/llm/explain.py**, **devtools/streamlit_flow_lab.py → ai/devtools/flow/streamlit_flow_lab.py**. 현 find_dotenv(usecwd=False)는 caller 파일 위치에서 위로 탐색하므로 이동만으로는 같은 우선순위를 보장하지 못한다. 권고 후보는 명시적 AI 서비스 root `.env` 하나와 process env 우선·override=False를 유지하고 중간/부모/cwd 자동 탐색은 중단하는 좁은 계약이다. 이는 기존 탐색 동작 변경이므로 **아직 미승인·미구현**이다. 실제 `.env` 조회/이동·old helper/새 loader·일반 runner는 하지 않는다. 작성/조율자가 사용자 판단을 연결한다.
2. retain으로 명시된 `frontend/src/app/reports/flow/[reportId]/.gitkeep`의 예상 밖 삭제. HEAD 원본은 0-byte/SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`다. 개발/작성/독립 검토 측은 해당 삭제를 수행하거나 승인하지 않았으며 사용자/다른 작업 의도는 미확인이다. 같은 디렉터리에 tracked page.tsx가 있어 이 placeholder는 폴더 추적/기능에 필요하지 않다. 외부 미확인 변경으로 그대로 보존하고 임의 복원하거나 자기 작업으로 귀속하지 않는다. 별도 사용자 판단을 요구하거나 나머지 검증/결과를 멈출 기능상 필요는 없다. 기능 소스 손실로 확대하지 않고 완료된533 이동 수치는 유지한다.

권장 commit 메시지의 임시 초안은 `refactor: organize backend, AI, and frontend by feature`다. PR 제목 초안은 `refactor: 기능별 폴더 정리와 canonical import 통합`이다. 최종 PR 본문은 실제 533개 이동/61개 shim 제거, Backend10/402·Frontend21/36, Python532 구문·AI local1061·문서77/359/13, final type 도구 차단·lint 기존any2·build/HTTP/AI runtime 미검증 및 위 보류를 그대로 드러내야 한다. 사용자 실행용 stage/commit/push/Draft PR 명령은 Flow 최종 정책이 정리된 뒤 정확한 파일 집합/HEAD/전체 remote URL guard를 갖춰 작성한다. 외부 미확인 placeholder 삭제는 본 작업과 분리해 명령의 자동 포함 대상으로 삼지 않는다. 현재 `git add .` 또는 실제 git/gh 액션을 권하지도 실행하지도 않았다.


## v1.15 · Flow 최종3 실제 이동·명시 dotenv 합성 검증

사용자가 AI 서비스 루트 `.env` 통일·process env 우선 정책을 승인한 뒤 마지막3을 실제 이동했다. checkpoint는 `/tmp/verith-restructure-baseline-r38ooouu/FLOW-FINAL-PREPARE`(이동 전 source/검사7개)와 `AI-FLOW-FINAL/changes.json`(원본/consumer5개)이다. 새 old helper/shim/일반 loader는 없다.

| before | 실제 canonical | 명시 AI root/보존 call owner |
|---|---|---|
| ai/src/agents/flow/core/kis_client.py | ai/src/agents/flow/infrastructure/kis_client.py | parents4 / _load_credentials |
| ai/src/agents/flow/nodes/explain.py | ai/src/agents/flow/infrastructure/llm/explain.py | parents5 / explain의 기존 gate 이후 |
| ai/src/agents/flow/devtools/streamlit_flow_lab.py | ai/devtools/flow/streamlit_flow_lab.py | parents2 / 기존 top-level 시점 |

각 source의 `_ENV_FILE = _AI_ROOT / ".env"`와 단일 `load_dotenv(dotenv_path=_ENV_FILE, override=False)`를 확인했다. prompt는 새 parents2/prompts/explain.txt, lab의 _SRC는 AIroot/src이며 workflow/token mock consumer도 canonical로 바꿨다. 독립 source-only 검토는 업무 본문·자격 키·HTTP/token/cache·UI 순서/호출 시점 및 config/prompt bytes 보존을 수용했다. 독립 실행은 아니다.

기존 runtime Flow 모델/export2개 hash/origin은 그대로다. exact FLOW_POLICY_SOURCES3은 source-copy/AST 전용으로만 추가했고 graph/KIS/LLM/Streamlit을 import하지 않았다. 기존 self10에 helper1/test3을 추가했다. compile 전 root/ENV/labSRC/prompt RHS·필수집합·중복/재바인딩·단일 call/원 owner를 검증해 허용된 선언/call만 합성 __file__/cwd로 실행한다. 받은 path/override를 먼저 검사한 dispatcher는 path를 실제 loader에 넘기지 않고 real dotenv.main.load_dotenv(stream=StringIO(...),override=False)만 호출한다.

- 공식 require_escalated Backend self-test: **13 tests/13 pass**, exit0, 자기 root 제거. 실제 source-derived root/Path/call 검증과3source×3cwd×process 값2개(process/빈문자열)=18 subcase, 중간/부모/cwd fixture 키 미적용·루트없는 empty stream의 process-only·환경/cwd 복원 및 package-root load/find 차단 alias identity 보존을 확인했다. 물리 `.env` 파일을 만들거나 조회/open하지 않았다.
- 별도 공식 Backend unit: **12파일 collected/passed402/402**, skip/guard0, exit0, 자기 root 제거. 원래402 행동·공개 API/schema/payload hash 회귀를 그대로 유지했다. 이전 결과를 최종 source 결과로 재사용하지 않았다.
- 명령은 기존 env-free Python -I -S check_safe.py self-test/unit과 같고 각 workload를 별도 요청했다. fresh env/실.env open/private/OS/FS/network/plugin 보호와 bootstrap bytes는 바꾸지 않았다.
- **사용자 영향:** 중간/부모/cwd `.env`에만 의존했던 다른 실행/배포/debugger 환경은 앞으로 사용자가 AIroot `.env` 또는 process env로 설정해야 한다. 기존 process 값은 빈 문자열도 우선한다. 실제 값/키 유무·서비스 성공은 확인하지 않았다. 조율자의 승인된 읽기전용 lstat 확인에서는 이 checkout의 ai/.env가 regular이고 repo·src·agents·Flow 및 옛 core/nodes/devtools의 후보는 absent여서 보통 file-caller 탐색도 ai/.env에 도달할 것으로 관측했다. 이 메타데이터 확인은 개발자가 추가 실행한 검사가 아니며 저장소 밖 부모/cwd/debugger/다른 배포나 실제 내용에 대한 보장이 아니다. 기존 설정파일 이전/복사/덮어쓰기는0이다.

| Flow 최종 검증 source | SHA-256 |
|---|---|
| `backend/scripts/check_safe.py` | `5987f2c6c80e0f7ba8f4ee78683b1a456c1a8810bf65fc452ec540fd1cf5ef3c` |
| `backend/scripts/safe_checks_bootstrap.py` | `89966fd3a5ad39068315894aee2be9afda7303517a99fc9ef1293848f38fe223` |
| `backend/tests/safe_checks/test_entry.py` | `9833d22bc0a165d5e5c6e23202b11c205a43aabeb27f560ae2906d8863d41ea1` |
| `backend/tests/unit/test_flow_contract.py` | `458d76b5240a50b4bd66092af71943fbe89279bfafe4d52b4f6262c9b6b18792` |

## v1.15 · 마지막 marker/빈 폴더 정리와 최종 Frontend 회귀

모든 source 이동 및 위 합성 검증이 통과한 다음에만 최종 정리를 실행했다. `FINAL-MARKERS/before-identities.json`·`result.json`은 비민감 자기 임시 checkpoint에만 두며 raw inode/영수증을 repo에 복사하지 않는다. 삭제 직전 no-symlink parent descriptor·regular/0-byte/single-link/identity를 확인한 exact19개만 unlink했다. 이미 없는 Flow app marker1개는 승인된 최종 disposition이며 복원하거나 삭제 주체를 추정하지 않았다. 운영 eval anchor3개는 건드리지 않았다.

- 실제 marker unlink19 / 이미 없음1 / 운영 anchor 보존3. 아래 전수표의 exact20개는 승인 제거로, move목적지 marker11개는 이동 누락과 구분해 표시했다.
- directory_candidates exact10개 모두 fresh 비symlink/identity 대조 후 하위부터 atomic rmdir로 제거됐다. 7개 scaffold leaf/parent와 Flow old core/nodes/devtools3개뿐이다. nonempty 거부0/추가삭제0이며 디렉터리 내용 열거/hidden·ignored 비우기/재귀 workspace 삭제는 없다. runtime/data/cache/history/traces/다른 앱 자원은 보존했다.
- Frontend controller의 retired marker9개 mapping만 제외해46→37로 줄였고 safety의 개수 기대1개만37로 맞췄다. exact JSON mapping 제거·숫자 치환을 되돌리면 checkpoint bytes와 같다. package/lock·guard·OS/private/network/HMAC/기존 행동 assertions는 불변이다.
- 별도 공식 require_escalated 최종 Frontend self-test **21/21**, unit **disabled10+session2+ports3+safety21=36/36**, fail/cancelled/skipped/todo0, exit0·worker4/exit4/partial0·예상 밖 guard0·각 자기 root 제거. env -i와 OPENSSL_CONF=/dev/null·검증 Node·기존 check-local-ports.mjs self-test/unit을 사용했다. 이전 type 거절/기존lint2/빌드·HTTP 미검증은 지우거나 재시도하지 않았다.

| 최종 Frontend 검증 source | SHA-256 |
|---|---|
| `frontend/scripts/check-local-ports.mjs` | `36b085e67def26624f64c45ba2c83bf5aae9daef23c96e24b4a21b244a13b687` |
| `frontend/scripts/safe-checks-guard.cjs` | `6b82a520aee8a3866878aa4a7425f16110fd62eb59dd58b4d87e7d273b228575` |
| `frontend/tests/tooling/safe-checks.test.mjs` | `9eb8724551782aa6585d265e7f4aa2637e84d740991d9c6f8e13fee51486f130` |

### 정확한 최종 집합과 수용 한계

move536행 처리=실제 target525+승인 marker disposition11, retain321행=실제312+승인 marker disposition9다. 공개 최종838파일이 exact 예상 집합과 일치하며 예상 밖 추가/누락0·staged0을 직접 확인했다. 전체 Python532개 비실행 구문 검사도 통과했다. 원래23 보존본·CF/manifest/과거 source/거절/실패·공유 migration history는 보존한다.

최종 source/정리 결과는 독립 source-only 재검토에서 수용됐다. 검토자가 runtime을 독립 재실행한 것은 아니다. 구조 적용과 실제 기능/실환경의 전체 수용을 구분한다. 실제 .env I/O/자격·DB/Google/KIS/LLM/Streamlit/AI 전체 및 최종 type/build/HTTP는 미검증이며, 대상lint 기존any2 오류도 유지한다. Git add/commit/push/PR/merge·배포·설치는 실행하지 않았다.

<!-- ST001_LAYOUT_ROWS_BEGIN -->
| 원래 source | 목표 target | batch | 실제 상태 |
|---|---|---|---|
| `.github/PULL_REQUEST_TEMPLATE.md` | `.github/PULL_REQUEST_TEMPLATE.md` | ROOT-ANCHOR | 계획상 유지 / 설계 예외 |
| `.gitignore` | `.gitignore` | ROOT-ANCHOR | 계획상 유지 / 설계 예외 |
| `.python-version` | `.python-version` | ROOT-ANCHOR | 계획상 유지 / 설계 예외 |
| `AGENTS.md` | `AGENTS.md` | ROOT-ANCHOR | 계획상 유지 / 설계 예외 |
| `PR_DESCRIPTION.md` | `PR_DESCRIPTION.md` | ROOT-ANCHOR | 계획상 유지 / 설계 예외 |
| `README.md` | `README.md` | ROOT-ANCHOR | 계획상 유지 / 설계 예외 |
| `ai/.gitignore` | `ai/.gitignore` | AI-ANCHOR | 계획상 유지 / 설계 예외 |
| `ai/AGENTS.md` | `ai/AGENTS.md` | AI-ANCHOR | 계획상 유지 / 설계 예외 |
| `ai/docs/supervisor_agent_followups.md` | `ai/docs/supervisor_agent_followups.md` | AI-ANCHOR | 계획상 유지 / 설계 예외 |
| `ai/pyproject.toml` | `ai/pyproject.toml` | AI-ANCHOR | 계획상 유지 / 설계 예외 |
| `ai/src/agents/flow/.gitkeep` | `ai/src/agents/flow/.gitkeep` | AI-FLOW-ENTRY | 최종 승인 불필요 marker 제거 / retain disposition |
| `ai/src/agents/flow/agent.py` | `ai/src/agents/flow/application/agent.py` | AI-FLOW-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/flow/config.py` | `ai/src/agents/flow/config.py` | AI-FLOW-CONFIG-ANCHOR | 계획상 유지 / 설계 예외 |
| `ai/src/agents/flow/core/kis_client.py` | `ai/src/agents/flow/infrastructure/kis_client.py` | AI-FLOW-SOURCE | 실제 이동·명시 dotenv 정책·합성 검증 / 독립 정적 수용 |
| `ai/src/agents/flow/core/signals.py` | `ai/src/agents/flow/domain/signals.py` | AI-FLOW-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/flow/core/stock_master.py` | `ai/src/agents/flow/infrastructure/stock_master.py` | AI-FLOW-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/flow/core/verify_input.py` | `ai/src/agents/flow/application/validation.py` | AI-FLOW-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/flow/core/verify_interpretation.py` | `ai/src/agents/flow/domain/verification/interpretation.py` | AI-FLOW-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/flow/core/verify_rules.py` | `ai/src/agents/flow/domain/verification/signals.py` | AI-FLOW-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/flow/devtools/streamlit_flow_lab.py` | `ai/devtools/flow/streamlit_flow_lab.py` | AI-FLOW-DEVTOOLS | 실제 이동·명시 dotenv 정책·합성 검증 / 독립 정적 수용 |
| `ai/src/agents/flow/docs/storage-spec.md` | `ai/docs/contracts/flow/storage-spec.md` | AI-FLOW-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/flow/export/to_json.py` | `ai/src/agents/flow/api/payload.py` | 4-A | 이동·보호 회귀·독립 정적 검토 완료 (4-A) |
| `ai/src/agents/flow/graph.py` | `ai/src/agents/flow/application/workflow.py` | AI-FLOW-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/flow/nodes/explain.py` | `ai/src/agents/flow/infrastructure/llm/explain.py` | AI-FLOW-SOURCE | 실제 이동·명시 dotenv 정책·합성 검증 / 독립 정적 수용 |
| `ai/src/agents/flow/prompts/explain.txt` | `ai/src/agents/flow/prompts/explain.txt` | AI-FLOW-PROMPT-ANCHOR | 계획상 유지 / 설계 예외 |
| `ai/src/agents/flow/render/builder.py` | `ai/src/agents/flow/infrastructure/render/builder.py` | AI-FLOW-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/flow/render/templates/supply_demand.html` | `ai/src/agents/flow/infrastructure/render/templates/supply_demand.html` | AI-FLOW-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/flow/schemas.py` | `ai/src/agents/flow/domain/models.py` | 4-A | 이동·보호 회귀·독립 정적 검토 완료 (4-A) |
| `ai/src/agents/flow/tests/fixtures.py` | `ai/tests/flow/fixtures.py` | AI-FLOW-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/flow/tests/test_daily.py` | `ai/tests/flow/test_daily.py` | AI-FLOW-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/flow/tests/test_export.py` | `ai/tests/flow/test_export.py` | AI-FLOW-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/flow/tests/test_gate1.py` | `ai/tests/flow/test_gate1.py` | AI-FLOW-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/flow/tests/test_generalization.py` | `ai/tests/flow/test_generalization.py` | AI-FLOW-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/flow/tests/test_graph_smoke.py` | `ai/tests/flow/test_graph_smoke.py` | AI-FLOW-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/flow/tests/test_inst_detail.py` | `ai/tests/flow/test_inst_detail.py` | AI-FLOW-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/flow/tests/test_kis_token_cache.py` | `ai/tests/flow/test_kis_token_cache.py` | AI-FLOW-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/flow/tests/test_ownership.py` | `ai/tests/flow/test_ownership.py` | AI-FLOW-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/flow/tests/test_persistence.py` | `ai/tests/flow/test_persistence.py` | AI-FLOW-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/flow/tests/test_price_daily.py` | `ai/tests/flow/test_price_daily.py` | AI-FLOW-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/flow/tests/test_signals.py` | `ai/tests/flow/test_signals.py` | AI-FLOW-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/flow/tests/test_ticker_resolve.py` | `ai/tests/flow/test_ticker_resolve.py` | AI-FLOW-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/flow/tests/test_verify.py` | `ai/tests/flow/test_verify.py` | AI-FLOW-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/flow/tests/test_verify_interpretation.py` | `ai/tests/flow/test_verify_interpretation.py` | AI-FLOW-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/FRONTEND_INTEGRATION.md` | `ai/docs/agents/fundamental/FRONTEND_INTEGRATION.md` | AI-FUNDAMENTAL-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/MERGE_HANDOFF.md` | `ai/docs/agents/fundamental/MERGE_HANDOFF.md` | AI-FUNDAMENTAL-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/README.md` | `ai/src/agents/fundamental/README.md` | AI-FUNDAMENTAL-ENTRY | 계획상 유지 / 설계 예외 |
| `ai/src/agents/fundamental/README/01_OVERVIEW.md` | `ai/docs/agents/fundamental/01_OVERVIEW.md` | AI-FUNDAMENTAL-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/README/02_ARCHITECTURE_NODES.md` | `ai/docs/agents/fundamental/02_ARCHITECTURE_NODES.md` | AI-FUNDAMENTAL-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/README/03_DATA_CONTRACT.md` | `ai/docs/agents/fundamental/03_DATA_CONTRACT.md` | AI-FUNDAMENTAL-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/README/04_VERIFICATION_POLICY.md` | `ai/docs/agents/fundamental/04_VERIFICATION_POLICY.md` | AI-FUNDAMENTAL-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/README/05_MERGE_GUIDE.md` | `ai/docs/agents/fundamental/05_MERGE_GUIDE.md` | AI-FUNDAMENTAL-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/README/06_DEV_GUIDE.md` | `ai/docs/agents/fundamental/06_DEV_GUIDE.md` | AI-FUNDAMENTAL-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/README/07_SUPERVISOR_CONTRACT.md` | `ai/docs/agents/fundamental/07_SUPERVISOR_CONTRACT.md` | AI-FUNDAMENTAL-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/__init__.py` | `ai/src/agents/fundamental/__init__.py` | AI-FUNDAMENTAL-ENTRY | 계획상 유지 / 설계 예외 |
| `ai/src/agents/fundamental/api_test/__init__.py` | `ai/scripts/fundamental/__init__.py` | AI-FUNDAMENTAL-SCRIPTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/api_test/ask_agent.py` | `ai/scripts/fundamental/ask_agent.py` | AI-FUNDAMENTAL-SCRIPTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/api_test/batch_demo.py` | `ai/scripts/fundamental/batch_demo.py` | AI-FUNDAMENTAL-SCRIPTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/api_test/bps_probe.py` | `ai/scripts/fundamental/bps_probe.py` | AI-FUNDAMENTAL-SCRIPTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/api_test/check_qwen.py` | `ai/scripts/fundamental/check_qwen.py` | AI-FUNDAMENTAL-SCRIPTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/api_test/dart_surface_probe.py` | `ai/scripts/fundamental/dart_surface_probe.py` | AI-FUNDAMENTAL-SCRIPTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/api_test/demo_dart_fetch.py` | `ai/scripts/fundamental/demo_dart_fetch.py` | AI-FUNDAMENTAL-SCRIPTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/api_test/export_graph.py` | `ai/scripts/fundamental/export_graph.py` | AI-FUNDAMENTAL-SCRIPTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/api_test/make_qwen_markdown.py` | `ai/scripts/fundamental/make_qwen_markdown.py` | AI-FUNDAMENTAL-SCRIPTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/api_test/make_sample_payload.py` | `ai/scripts/fundamental/make_sample_payload.py` | AI-FUNDAMENTAL-SCRIPTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/api_test/run_checks.bat` | `ai/scripts/fundamental/run_checks.bat` | AI-FUNDAMENTAL-SCRIPTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/api_test/samples/fundamental_report_sample.html` | `ai/examples/fundamental/fundamental_report_sample.html` | AI-FUNDAMENTAL-EXAMPLES | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/api_test/samples/fundamental_response_sample.json` | `ai/examples/fundamental/fundamental_response_sample.json` | AI-FUNDAMENTAL-EXAMPLES | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/api_test/samples/qwen_output_sample.md` | `ai/examples/fundamental/qwen_output_sample.md` | AI-FUNDAMENTAL-EXAMPLES | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/core/__init__.py` | `ai/src/agents/fundamental/core/__init__.py` | AI-FUNDAMENTAL-ENTRY | 계획상 유지 / 설계 예외 |
| `ai/src/agents/fundamental/core/config.py` | `ai/src/agents/fundamental/core/config.py` | AI-FUNDAMENTAL-CONFIG-ANCHOR | 계획상 유지 / 설계 예외 |
| `ai/src/agents/fundamental/core/contract.py` | `ai/src/agents/fundamental/domain/contracts.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/core/decisions.py` | `ai/src/agents/fundamental/application/decisions.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/core/failures.py` | `ai/src/agents/fundamental/application/failures.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/core/observability.py` | `ai/src/agents/fundamental/application/observability.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/core/query_interpreter.py` | `ai/src/agents/fundamental/application/query_interpreter.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/core/resilience.py` | `ai/src/agents/fundamental/application/resilience.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/core/run_history.py` | `ai/src/agents/fundamental/infrastructure/run_history.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/core/state.py` | `ai/src/agents/fundamental/application/state.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/data/__init__.py` | `ai/src/agents/fundamental/infrastructure/data/__init__.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/data/cache.py` | `ai/src/agents/fundamental/infrastructure/data/cache.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/data/corp_code.py` | `ai/src/agents/fundamental/infrastructure/data/corp_code.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/data/dart_client.py` | `ai/src/agents/fundamental/infrastructure/data/dart_client.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/data/latest_report.py` | `ai/src/agents/fundamental/application/report_selection.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/data/regular_disclosure.py` | `ai/src/agents/fundamental/infrastructure/data/regular_disclosure.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/docs/api_spec.md` | `ai/docs/contracts/fundamental/api_spec.md` | AI-FUNDAMENTAL-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/emit/html_builder.py` | `ai/src/agents/fundamental/api/rendering/html_builder.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/evidence/__init__.py` | `ai/src/agents/fundamental/domain/evidence/__init__.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/evidence/graph_builder.py` | `ai/src/agents/fundamental/domain/evidence/graph_builder.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/evidence/path_selector.py` | `ai/src/agents/fundamental/domain/evidence/path_selector.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/graph.py` | `ai/src/agents/fundamental/application/agent.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/interpret/__init__.py` | `ai/src/agents/fundamental/application/interpretation/__init__.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/interpret/critic.py` | `ai/src/agents/fundamental/application/interpretation/critic.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/interpret/fallback_template.py` | `ai/src/agents/fundamental/domain/interpretation/fallback_template.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/interpret/llm_client.py` | `ai/src/agents/fundamental/infrastructure/llm/client.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/interpret/llm_interpreter.py` | `ai/src/agents/fundamental/application/interpretation/llm_interpreter.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/interpret/planner.py` | `ai/src/agents/fundamental/application/interpretation/planner.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/interpret/prompts.py` | `ai/src/agents/fundamental/application/interpretation/prompts.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/nodes/README.md` | `ai/docs/agents/fundamental/nodes/README.md` | AI-FUNDAMENTAL-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/nodes/__init__.py` | `ai/src/agents/fundamental/application/nodes/__init__.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/nodes/calc_node.py` | `ai/src/agents/fundamental/application/nodes/calc_node.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/nodes/collect_node.py` | `ai/src/agents/fundamental/application/nodes/collect_node.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/nodes/critic_node.py` | `ai/src/agents/fundamental/application/nodes/critic_node.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/nodes/evidence_node.py` | `ai/src/agents/fundamental/application/nodes/evidence_node.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/nodes/interpret_node.py` | `ai/src/agents/fundamental/application/nodes/interpret_node.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/nodes/normalize_node.py` | `ai/src/agents/fundamental/application/nodes/normalize_node.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/nodes/plan_node.py` | `ai/src/agents/fundamental/application/nodes/plan_node.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/nodes/report_node.py` | `ai/src/agents/fundamental/application/nodes/report_node.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/nodes/verify_node.py` | `ai/src/agents/fundamental/application/nodes/verify_node.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/nodes/workflow.py` | `ai/src/agents/fundamental/application/nodes/workflow.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/normalize/__init__.py` | `ai/src/agents/fundamental/domain/normalization/__init__.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/normalize/account_mapper.py` | `ai/src/agents/fundamental/domain/normalization/account_mapper.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/normalize/amendment_resolver.py` | `ai/src/agents/fundamental/domain/normalization/amendment_resolver.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/normalize/standardize.py` | `ai/src/agents/fundamental/domain/normalization/standardize.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/normalize/unit_normalizer.py` | `ai/src/agents/fundamental/domain/normalization/unit_normalizer.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/ratios/__init__.py` | `ai/src/agents/fundamental/domain/ratios/__init__.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/ratios/calculators.py` | `ai/src/agents/fundamental/domain/ratios/calculators.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/ratios/scorer.py` | `ai/src/agents/fundamental/domain/ratios/scorer.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/ratios/trend.py` | `ai/src/agents/fundamental/domain/ratios/trend.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/report/__init__.py` | `ai/src/agents/fundamental/api/reporting/__init__.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/report/formatting.py` | `ai/src/agents/fundamental/api/reporting/formatting.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/report/period.py` | `ai/src/agents/fundamental/domain/reporting/period.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/report/schema_builder.py` | `ai/src/agents/fundamental/api/payload.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/retrieval/__init__.py` | `ai/src/agents/fundamental/infrastructure/dart/__init__.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/retrieval/source_policy.py` | `ai/src/agents/fundamental/infrastructure/dart/source_policy.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/tests/fixtures/lgchem_2025_cfs_rows.json` | `ai/tests/fundamental/fixtures/lgchem_2025_cfs_rows.json` | AI-FUNDAMENTAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/tests/fixtures/synthetic_derived_liabilities_rows.json` | `ai/tests/fundamental/fixtures/synthetic_derived_liabilities_rows.json` | AI-FUNDAMENTAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/tests/test_agent_finalization.py` | `ai/tests/fundamental/test_agent_finalization.py` | AI-FUNDAMENTAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/tests/test_ask_agent.py` | `ai/tests/fundamental/test_ask_agent.py` | AI-FUNDAMENTAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/tests/test_binding.py` | `ai/tests/fundamental/test_binding.py` | AI-FUNDAMENTAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/tests/test_calculators.py` | `ai/tests/fundamental/test_calculators.py` | AI-FUNDAMENTAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/tests/test_config.py` | `ai/tests/fundamental/test_config.py` | AI-FUNDAMENTAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/tests/test_consistency.py` | `ai/tests/fundamental/test_consistency.py` | AI-FUNDAMENTAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/tests/test_corp_code_resolution.py` | `ai/tests/fundamental/test_corp_code_resolution.py` | AI-FUNDAMENTAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/tests/test_evidence_graph.py` | `ai/tests/fundamental/test_evidence_graph.py` | AI-FUNDAMENTAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/tests/test_failure_contract.py` | `ai/tests/fundamental/test_failure_contract.py` | AI-FUNDAMENTAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/tests/test_formatting.py` | `ai/tests/fundamental/test_formatting.py` | AI-FUNDAMENTAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/tests/test_fundamental_api.py` | `ai/tests/fundamental/test_fundamental_api.py` | AI-FUNDAMENTAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/tests/test_golden_derived_liabilities.py` | `ai/tests/fundamental/test_golden_derived_liabilities.py` | AI-FUNDAMENTAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/tests/test_golden_lgchem.py` | `ai/tests/fundamental/test_golden_lgchem.py` | AI-FUNDAMENTAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/tests/test_html_builder.py` | `ai/tests/fundamental/test_html_builder.py` | AI-FUNDAMENTAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/tests/test_llm_interpreter.py` | `ai/tests/fundamental/test_llm_interpreter.py` | AI-FUNDAMENTAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/tests/test_observability.py` | `ai/tests/fundamental/test_observability.py` | AI-FUNDAMENTAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/tests/test_period.py` | `ai/tests/fundamental/test_period.py` | AI-FUNDAMENTAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/tests/test_public_contract.py` | `ai/tests/fundamental/test_public_contract.py` | AI-FUNDAMENTAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/tests/test_regular_disclosure.py` | `ai/tests/fundamental/test_regular_disclosure.py` | AI-FUNDAMENTAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/tests/test_retrieval_source_policy.py` | `ai/tests/fundamental/test_retrieval_source_policy.py` | AI-FUNDAMENTAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/tests/test_schema_builder.py` | `ai/tests/fundamental/test_schema_builder.py` | AI-FUNDAMENTAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/tests/test_stability.py` | `ai/tests/fundamental/test_stability.py` | AI-FUNDAMENTAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/tests/test_verdict_guard.py` | `ai/tests/fundamental/test_verdict_guard.py` | AI-FUNDAMENTAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/verify/__init__.py` | `ai/src/agents/fundamental/domain/verification/__init__.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/verify/binding.py` | `ai/src/agents/fundamental/domain/verification/binding.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/verify/consistency.py` | `ai/src/agents/fundamental/domain/verification/consistency.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/verify/stability.py` | `ai/src/agents/fundamental/domain/verification/stability.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/fundamental/verify/verdict_guard.py` | `ai/src/agents/fundamental/domain/verification/verdict_guard.py` | AI-FUNDAMENTAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/industry/.gitkeep` | `ai/src/agents/industry/.gitkeep` | AI-INDUSTRY-ENTRY | 최종 승인 불필요 marker 제거 / retain disposition |
| `ai/src/agents/industry/__init__.py` | `ai/src/agents/industry/__init__.py` | AI-INDUSTRY-ENTRY | 계획상 유지 / 설계 예외 |
| `ai/src/agents/industry/agent.py` | `ai/src/agents/industry/application/agent.py` | AI-INDUSTRY-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/industry/companies.py` | `ai/src/agents/industry/domain/companies.py` | AI-INDUSTRY-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/industry/config.py` | `ai/src/agents/industry/config.py` | AI-INDUSTRY-CONFIG-ANCHOR | 계획상 유지 / 설계 예외 |
| `ai/src/agents/industry/dart_collect.py` | `ai/src/agents/industry/infrastructure/collection/dart_collect.py` | AI-INDUSTRY-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/industry/data/extracted/evidence_rejected.csv` | `ai/src/agents/industry/data/extracted/evidence_rejected.csv` | AI-INDUSTRY-DATA-ANCHOR | 계획상 유지 / 설계 예외 |
| `ai/src/agents/industry/data/extracted/graph_documents.json` | `ai/src/agents/industry/data/extracted/graph_documents.json` | AI-INDUSTRY-DATA-ANCHOR | 계획상 유지 / 설계 예외 |
| `ai/src/agents/industry/data/extracted/llm_aliases.json` | `ai/src/agents/industry/data/extracted/llm_aliases.json` | AI-INDUSTRY-DATA-ANCHOR | 계획상 유지 / 설계 예외 |
| `ai/src/agents/industry/data/extracted/nodes.csv` | `ai/src/agents/industry/data/extracted/nodes.csv` | AI-INDUSTRY-DATA-ANCHOR | 계획상 유지 / 설계 예외 |
| `ai/src/agents/industry/data/extracted/raw_llm.json` | `ai/src/agents/industry/data/extracted/raw_llm.json` | AI-INDUSTRY-DATA-ANCHOR | 계획상 유지 / 설계 예외 |
| `ai/src/agents/industry/data/extracted/triples.csv` | `ai/src/agents/industry/data/extracted/triples.csv` | AI-INDUSTRY-DATA-ANCHOR | 계획상 유지 / 설계 예외 |
| `ai/src/agents/industry/data/raw/003670/business_content.txt` | `ai/src/agents/industry/data/raw/003670/business_content.txt` | AI-INDUSTRY-DATA-ANCHOR | 계획상 유지 / 설계 예외 |
| `ai/src/agents/industry/data/raw/003670/meta.json` | `ai/src/agents/industry/data/raw/003670/meta.json` | AI-INDUSTRY-DATA-ANCHOR | 계획상 유지 / 설계 예외 |
| `ai/src/agents/industry/data/raw/006400/business_content.txt` | `ai/src/agents/industry/data/raw/006400/business_content.txt` | AI-INDUSTRY-DATA-ANCHOR | 계획상 유지 / 설계 예외 |
| `ai/src/agents/industry/data/raw/006400/meta.json` | `ai/src/agents/industry/data/raw/006400/meta.json` | AI-INDUSTRY-DATA-ANCHOR | 계획상 유지 / 설계 예외 |
| `ai/src/agents/industry/data/raw/051910/business_content.txt` | `ai/src/agents/industry/data/raw/051910/business_content.txt` | AI-INDUSTRY-DATA-ANCHOR | 계획상 유지 / 설계 예외 |
| `ai/src/agents/industry/data/raw/051910/meta.json` | `ai/src/agents/industry/data/raw/051910/meta.json` | AI-INDUSTRY-DATA-ANCHOR | 계획상 유지 / 설계 예외 |
| `ai/src/agents/industry/data/raw/066970/business_content.txt` | `ai/src/agents/industry/data/raw/066970/business_content.txt` | AI-INDUSTRY-DATA-ANCHOR | 계획상 유지 / 설계 예외 |
| `ai/src/agents/industry/data/raw/066970/meta.json` | `ai/src/agents/industry/data/raw/066970/meta.json` | AI-INDUSTRY-DATA-ANCHOR | 계획상 유지 / 설계 예외 |
| `ai/src/agents/industry/data/raw/086520/business_content.txt` | `ai/src/agents/industry/data/raw/086520/business_content.txt` | AI-INDUSTRY-DATA-ANCHOR | 계획상 유지 / 설계 예외 |
| `ai/src/agents/industry/data/raw/086520/meta.json` | `ai/src/agents/industry/data/raw/086520/meta.json` | AI-INDUSTRY-DATA-ANCHOR | 계획상 유지 / 설계 예외 |
| `ai/src/agents/industry/data/raw/096770/business_content.txt` | `ai/src/agents/industry/data/raw/096770/business_content.txt` | AI-INDUSTRY-DATA-ANCHOR | 계획상 유지 / 설계 예외 |
| `ai/src/agents/industry/data/raw/096770/meta.json` | `ai/src/agents/industry/data/raw/096770/meta.json` | AI-INDUSTRY-DATA-ANCHOR | 계획상 유지 / 설계 예외 |
| `ai/src/agents/industry/data/raw/247540/business_content.txt` | `ai/src/agents/industry/data/raw/247540/business_content.txt` | AI-INDUSTRY-DATA-ANCHOR | 계획상 유지 / 설계 예외 |
| `ai/src/agents/industry/data/raw/247540/meta.json` | `ai/src/agents/industry/data/raw/247540/meta.json` | AI-INDUSTRY-DATA-ANCHOR | 계획상 유지 / 설계 예외 |
| `ai/src/agents/industry/data/raw/348370/business_content.txt` | `ai/src/agents/industry/data/raw/348370/business_content.txt` | AI-INDUSTRY-DATA-ANCHOR | 계획상 유지 / 설계 예외 |
| `ai/src/agents/industry/data/raw/348370/meta.json` | `ai/src/agents/industry/data/raw/348370/meta.json` | AI-INDUSTRY-DATA-ANCHOR | 계획상 유지 / 설계 예외 |
| `ai/src/agents/industry/data/raw/361610/business_content.txt` | `ai/src/agents/industry/data/raw/361610/business_content.txt` | AI-INDUSTRY-DATA-ANCHOR | 계획상 유지 / 설계 예외 |
| `ai/src/agents/industry/data/raw/361610/meta.json` | `ai/src/agents/industry/data/raw/361610/meta.json` | AI-INDUSTRY-DATA-ANCHOR | 계획상 유지 / 설계 예외 |
| `ai/src/agents/industry/data/raw/373220/business_content.txt` | `ai/src/agents/industry/data/raw/373220/business_content.txt` | AI-INDUSTRY-DATA-ANCHOR | 계획상 유지 / 설계 예외 |
| `ai/src/agents/industry/data/raw/373220/meta.json` | `ai/src/agents/industry/data/raw/373220/meta.json` | AI-INDUSTRY-DATA-ANCHOR | 계획상 유지 / 설계 예외 |
| `ai/src/agents/industry/data/structured/holdings.csv` | `ai/src/agents/industry/data/structured/holdings.csv` | AI-INDUSTRY-DATA-ANCHOR | 계획상 유지 / 설계 예외 |
| `ai/src/agents/industry/data/structured/major_shareholders.csv` | `ai/src/agents/industry/data/structured/major_shareholders.csv` | AI-INDUSTRY-DATA-ANCHOR | 계획상 유지 / 설계 예외 |
| `ai/src/agents/industry/extract.py` | `ai/src/agents/industry/infrastructure/extraction/extract.py` | AI-INDUSTRY-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/industry/faithfulness.py` | `ai/src/agents/industry/application/faithfulness.py` | AI-INDUSTRY-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/industry/ingest.py` | `ai/src/agents/industry/infrastructure/graph/ingest.py` | AI-INDUSTRY-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/industry/llm_check.py` | `ai/scripts/industry/llm_check.py` | AI-INDUSTRY-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/industry/make_report/DATA_SCHEMA.md` | `ai/docs/contracts/industry/report_data_schema.md` | AI-INDUSTRY-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/industry/make_report/__init__.py` | `ai/src/agents/industry/api/report/__init__.py` | AI-INDUSTRY-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/industry/make_report/__main__.py` | `ai/src/agents/industry/api/report/__main__.py` | AI-INDUSTRY-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/industry/make_report/example_payload.json` | `ai/examples/industry/report/example_payload.json` | AI-INDUSTRY-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/industry/make_report/render.py` | `ai/src/agents/industry/api/report/render.py` | AI-INDUSTRY-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/industry/make_report/report_template.html` | `ai/src/agents/industry/api/report/report_template.html` | AI-INDUSTRY-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/industry/make_report/support.js` | `ai/src/agents/industry/api/report/support.js` | AI-INDUSTRY-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/industry/normalize.py` | `ai/src/agents/industry/infrastructure/entity_normalization.py` | AI-INDUSTRY-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/industry/report_export.py` | `ai/src/agents/industry/application/report_export.py` | AI-INDUSTRY-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/industry/resolve.py` | `ai/src/agents/industry/infrastructure/extraction/resolve.py` | AI-INDUSTRY-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/industry/retrieve.py` | `ai/src/agents/industry/application/retrieval.py` | AI-INDUSTRY-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/industry/schema.py` | `ai/src/agents/industry/domain/schema.py` | AI-INDUSTRY-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/industry/tests/test_make_report.py` | `ai/tests/industry/test_make_report.py` | AI-INDUSTRY-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/industry/tests/test_report_export.py` | `ai/tests/industry/test_report_export.py` | AI-INDUSTRY-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/industry/vector_retrieve.py` | `ai/src/agents/industry/infrastructure/graph/vector_retrieve.py` | AI-INDUSTRY-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/industry/vectorize.py` | `ai/src/agents/industry/infrastructure/graph/vectorize.py` | AI-INDUSTRY-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/CLAUDE.md` | `ai/src/agents/news/CLAUDE.md` | AI-NEWS-ENTRY | 계획상 유지 / 설계 예외 |
| `ai/src/agents/news/README.md` | `ai/src/agents/news/README.md` | AI-NEWS-ENTRY | 계획상 유지 / 설계 예외 |
| `ai/src/agents/news/__init__.py` | `ai/src/agents/news/__init__.py` | AI-NEWS-ENTRY | 계획상 유지 / 설계 예외 |
| `ai/src/agents/news/config.py` | `ai/src/agents/news/config.py` | AI-NEWS-CONFIG-ANCHOR | 계획상 유지 / 설계 예외 |
| `ai/src/agents/news/conftest.py` | `ai/tests/news/conftest.py` | AI-NEWS-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/demo_pipeline_app.py` | `ai/devtools/news/demo_pipeline_app.py` | AI-NEWS-DEVTOOLS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/docs/erd.dbml` | `ai/docs/contracts/news/erd.dbml` | AI-NEWS-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/docs/event_merge.md` | `ai/docs/agents/news/event_merge.md` | AI-NEWS-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/docs/model_choice.md` | `ai/docs/agents/news/model_choice.md` | AI-NEWS-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/docs/pipeline_spec.md` | `ai/docs/agents/news/pipeline_spec.md` | AI-NEWS-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/docs/query_spec.md` | `ai/docs/agents/news/query_spec.md` | AI-NEWS-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/docs/sequence.md` | `ai/docs/agents/news/sequence.md` | AI-NEWS-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/evals/README.md` | `ai/evals/news/README.md` | AI-NEWS-EVALS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/evals/axes/__init__.py` | `ai/evals/news/axes/__init__.py` | AI-NEWS-EVALS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/evals/axes/answer.py` | `ai/evals/news/axes/answer.py` | AI-NEWS-EVALS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/evals/axes/event.py` | `ai/evals/news/axes/event.py` | AI-NEWS-EVALS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/evals/axes/kg.py` | `ai/evals/news/axes/kg.py` | AI-NEWS-EVALS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/evals/axes/retriever.py` | `ai/evals/news/axes/retriever.py` | AI-NEWS-EVALS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/evals/axes/sentiment.py` | `ai/evals/news/axes/sentiment.py` | AI-NEWS-EVALS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/evals/config.py` | `ai/evals/news/config.py` | AI-NEWS-EVALS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/evals/datasets/event_goldset.jsonl` | `ai/evals/news/datasets/event_goldset.jsonl` | AI-NEWS-EVALS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/evals/datasets/generated/.gitkeep` | `ai/src/agents/news/evals/datasets/generated/.gitkeep` | AI-NEWS-EVAL-OUTPUT-ANCHOR | 계획상 유지 / 설계 예외 |
| `ai/src/agents/news/evals/datasets/kg_goldset.jsonl` | `ai/evals/news/datasets/kg_goldset.jsonl` | AI-NEWS-EVALS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/evals/datasets/qa_goldset.jsonl` | `ai/evals/news/datasets/qa_goldset.jsonl` | AI-NEWS-EVALS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/evals/datasets/retriever_goldset.jsonl` | `ai/evals/news/datasets/retriever_goldset.jsonl` | AI-NEWS-EVALS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/evals/datasets/sentiment_goldset.jsonl` | `ai/evals/news/datasets/sentiment_goldset.jsonl` | AI-NEWS-EVALS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/evals/generators/__init__.py` | `ai/evals/news/generators/__init__.py` | AI-NEWS-EVALS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/evals/generators/kg_testset.py` | `ai/evals/news/generators/kg_testset.py` | AI-NEWS-EVALS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/evals/metrics/__init__.py` | `ai/evals/news/metrics/__init__.py` | AI-NEWS-EVALS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/evals/metrics/deterministic/__init__.py` | `ai/evals/news/metrics/deterministic/__init__.py` | AI-NEWS-EVALS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/evals/metrics/deterministic/kg.py` | `ai/evals/news/metrics/deterministic/kg.py` | AI-NEWS-EVALS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/evals/metrics/deterministic/ontology.py` | `ai/evals/news/metrics/deterministic/ontology.py` | AI-NEWS-EVALS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/evals/metrics/deterministic/retrieval.py` | `ai/evals/news/metrics/deterministic/retrieval.py` | AI-NEWS-EVALS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/evals/metrics/deterministic/traceability.py` | `ai/evals/news/metrics/deterministic/traceability.py` | AI-NEWS-EVALS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/evals/metrics/judge/__init__.py` | `ai/evals/news/metrics/judge/__init__.py` | AI-NEWS-EVALS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/evals/metrics/judge/fallback_judge.py` | `ai/evals/news/metrics/judge/fallback_judge.py` | AI-NEWS-EVALS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/evals/metrics/judge/ragas_adapter.py` | `ai/evals/news/metrics/judge/ragas_adapter.py` | AI-NEWS-EVALS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/evals/results/ci/.gitkeep` | `ai/src/agents/news/evals/results/ci/.gitkeep` | AI-NEWS-EVAL-OUTPUT-ANCHOR | 계획상 유지 / 설계 예외 |
| `ai/src/agents/news/evals/results/release/.gitkeep` | `ai/src/agents/news/evals/results/release/.gitkeep` | AI-NEWS-EVAL-OUTPUT-ANCHOR | 계획상 유지 / 설계 예외 |
| `ai/src/agents/news/evals/run_eval.py` | `ai/evals/news/run_eval.py` | AI-NEWS-EVALS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/graph.py` | `ai/src/agents/news/application/workflow.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/nodes/__init__.py` | `ai/src/agents/news/application/nodes/__init__.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/nodes/crawl.py` | `ai/src/agents/news/application/nodes/crawl.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/nodes/embedding.py` | `ai/src/agents/news/application/nodes/embedding.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/nodes/extract.py` | `ai/src/agents/news/application/nodes/extract.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/nodes/graph_builder.py` | `ai/src/agents/news/application/nodes/graph_builder.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/nodes/importance.py` | `ai/src/agents/news/application/nodes/importance.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/nodes/merge_event.py` | `ai/src/agents/news/application/nodes/merge_event.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/nodes/query.py` | `ai/src/agents/news/application/nodes/query.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/nodes/report.py` | `ai/src/agents/news/application/nodes/report.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/nodes/save.py` | `ai/src/agents/news/application/nodes/save.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/nodes/sentiment.py` | `ai/src/agents/news/application/nodes/sentiment.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/scheduler/__init__.py` | `ai/src/agents/news/application/scheduling/__init__.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/scheduler/__main__.py` | `ai/src/agents/news/application/scheduling/__main__.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/scheduler/cleanup_scheduler.py` | `ai/src/agents/news/application/scheduling/cleanup_scheduler.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/scheduler/rss_scheduler.py` | `ai/src/agents/news/application/scheduling/rss_scheduler.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/scheduler/runner.py` | `ai/src/agents/news/application/scheduling/runner.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/schemas/__init__.py` | `ai/src/agents/news/domain/models/__init__.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/schemas/article.py` | `ai/src/agents/news/domain/models/article.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/schemas/event.py` | `ai/src/agents/news/domain/models/event.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/schemas/graph.py` | `ai/src/agents/news/domain/models/graph.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/schemas/query.py` | `ai/src/agents/news/domain/models/query.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/schemas/report.py` | `ai/src/agents/news/domain/models/report.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/schemas/response.py` | `ai/src/agents/news/domain/models/response.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/services/__init__.py` | `ai/src/agents/news/application/services/__init__.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/services/answer_generator.py` | `ai/src/agents/news/application/services/answer_generator.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/services/backend/__init__.py` | `ai/src/agents/news/infrastructure/backend/__init__.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/services/backend/client.py` | `ai/src/agents/news/infrastructure/backend/client.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/services/backend/dedup_client.py` | `ai/src/agents/news/infrastructure/backend/dedup_client.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/services/backend/providers.py` | `ai/src/agents/news/infrastructure/backend/providers.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/services/backend/query_client.py` | `ai/src/agents/news/infrastructure/backend/query_client.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/services/backend/save_client.py` | `ai/src/agents/news/infrastructure/backend/save_client.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/services/crawler.py` | `ai/src/agents/news/infrastructure/http/crawler.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/services/embedder.py` | `ai/src/agents/news/infrastructure/models/embedder.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/services/event_merge.py` | `ai/src/agents/news/domain/services/event_merge.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/services/finbert.py` | `ai/src/agents/news/infrastructure/models/finbert.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/services/graph_builder.py` | `ai/src/agents/news/domain/services/graph_builder.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/services/graph_query.py` | `ai/src/agents/news/application/services/graph_query.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/services/importance.py` | `ai/src/agents/news/domain/services/importance.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/services/knowledge_graph.py` | `ai/src/agents/news/domain/services/knowledge_graph.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/services/llm.py` | `ai/src/agents/news/infrastructure/models/llm.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/services/query_understanding.py` | `ai/src/agents/news/application/services/query_understanding.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/services/report_renderer.py` | `ai/src/agents/news/api/payload.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/services/rss.py` | `ai/src/agents/news/infrastructure/http/rss.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/state.py` | `ai/src/agents/news/application/state.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/tasks/01_schemas.md` | `ai/docs/agents/news/tasks/01_schemas.md` | AI-NEWS-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/tasks/02_rss_crawler.md` | `ai/docs/agents/news/tasks/02_rss_crawler.md` | AI-NEWS-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/tasks/03_extract.md` | `ai/docs/agents/news/tasks/03_extract.md` | AI-NEWS-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/tasks/04_sentiment.md` | `ai/docs/agents/news/tasks/04_sentiment.md` | AI-NEWS-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/tasks/05_embedding_merge.md` | `ai/docs/agents/news/tasks/05_embedding_merge.md` | AI-NEWS-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/tasks/06_importance.md` | `ai/docs/agents/news/tasks/06_importance.md` | AI-NEWS-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/tasks/07_graph_builder.md` | `ai/docs/agents/news/tasks/07_graph_builder.md` | AI-NEWS-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/tasks/08_backend_client.md` | `ai/docs/agents/news/tasks/08_backend_client.md` | AI-NEWS-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/tasks/09_report.md` | `ai/docs/agents/news/tasks/09_report.md` | AI-NEWS-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/tasks/10_scheduler.md` | `ai/docs/agents/news/tasks/10_scheduler.md` | AI-NEWS-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/tasks/11_graph_state.md` | `ai/docs/agents/news/tasks/11_graph_state.md` | AI-NEWS-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/templates/css/.gitkeep` | `ai/examples/news/report/css/.gitkeep` | AI-NEWS-EXAMPLES | 최종 승인 marker 제거 / 이동 누락 아님 |
| `ai/src/agents/news/templates/js/.gitkeep` | `ai/examples/news/report/js/.gitkeep` | AI-NEWS-EXAMPLES | 최종 승인 marker 제거 / 이동 누락 아님 |
| `ai/src/agents/news/templates/report.html` | `ai/examples/news/report/report.html` | AI-NEWS-EXAMPLES | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/tests/__init__.py` | `ai/tests/news/__init__.py` | AI-NEWS-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/tests/test_answer_generator.py` | `ai/tests/news/test_answer_generator.py` | AI-NEWS-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/tests/test_backend_client.py` | `ai/tests/news/test_backend_client.py` | AI-NEWS-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/tests/test_cleanup_scheduler.py` | `ai/tests/news/test_cleanup_scheduler.py` | AI-NEWS-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/tests/test_crawler.py` | `ai/tests/news/test_crawler.py` | AI-NEWS-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/tests/test_embedding.py` | `ai/tests/news/test_embedding.py` | AI-NEWS-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/tests/test_event_merge.py` | `ai/tests/news/test_event_merge.py` | AI-NEWS-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/tests/test_extract_node.py` | `ai/tests/news/test_extract_node.py` | AI-NEWS-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/tests/test_graph.py` | `ai/tests/news/test_graph.py` | AI-NEWS-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/tests/test_graph_builder.py` | `ai/tests/news/test_graph_builder.py` | AI-NEWS-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/tests/test_graph_query.py` | `ai/tests/news/test_graph_query.py` | AI-NEWS-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/tests/test_html_parser.py` | `ai/tests/news/test_html_parser.py` | AI-NEWS-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/tests/test_importance.py` | `ai/tests/news/test_importance.py` | AI-NEWS-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/tests/test_llm.py` | `ai/tests/news/test_llm.py` | AI-NEWS-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/tests/test_query_report_nodes.py` | `ai/tests/news/test_query_report_nodes.py` | AI-NEWS-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/tests/test_query_understanding.py` | `ai/tests/news/test_query_understanding.py` | AI-NEWS-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/tests/test_report.py` | `ai/tests/news/test_report.py` | AI-NEWS-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/tests/test_report_renderer.py` | `ai/tests/news/test_report_renderer.py` | AI-NEWS-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/tests/test_rss.py` | `ai/tests/news/test_rss.py` | AI-NEWS-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/tests/test_rss_scheduler.py` | `ai/tests/news/test_rss_scheduler.py` | AI-NEWS-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/tests/test_sentiment.py` | `ai/tests/news/test_sentiment.py` | AI-NEWS-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/tests/test_state.py` | `ai/tests/news/test_state.py` | AI-NEWS-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/utils/__init__.py` | `ai/src/agents/news/domain/utils/__init__.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/utils/entity.py` | `ai/src/agents/news/domain/utils/entity.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/utils/html_parser.py` | `ai/src/agents/news/infrastructure/parsers/html_parser.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/utils/rss_parser.py` | `ai/src/agents/news/infrastructure/parsers/rss_parser.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/utils/similarity.py` | `ai/src/agents/news/domain/utils/similarity.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/news/utils/time_utils.py` | `ai/src/agents/news/domain/utils/time_utils.py` | AI-NEWS-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/README.md` | `ai/src/agents/technical/README.md` | AI-TECHNICAL-ENTRY | 계획상 유지 / 설계 예외 |
| `ai/src/agents/technical/agent.py` | `ai/src/agents/technical/application/agent.py` | AI-TECHNICAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/charts/chart_builder.py` | `ai/src/agents/technical/api/charts/chart_builder.py` | AI-TECHNICAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/charts/intraday_chart_builder.py` | `ai/src/agents/technical/api/charts/intraday_chart_builder.py` | AI-TECHNICAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/charts/intraday_context_builder.py` | `ai/src/agents/technical/api/charts/intraday_context_builder.py` | AI-TECHNICAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/config.py` | `ai/src/agents/technical/config.py` | AI-TECHNICAL-CONFIG-ANCHOR | 계획상 유지 / 설계 예외 |
| `ai/src/agents/technical/devtools/streamlit_technical_lab.py` | `ai/devtools/technical/streamlit_technical_lab.py` | AI-TECHNICAL-DEVTOOLS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/docs/api_spec.md` | `ai/docs/contracts/technical/api_spec.md` | AI-TECHNICAL-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/docs/architecture.md` | `ai/docs/agents/technical/architecture.md` | AI-TECHNICAL-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/docs/assets/node4_5_multiframe.png` | `ai/docs/agents/technical/assets/node4_5_multiframe.png` | AI-TECHNICAL-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/docs/assets/node4_5_multiframe.svg` | `ai/docs/agents/technical/assets/node4_5_multiframe.svg` | AI-TECHNICAL-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/docs/assets/pipeline_ae_layers.png` | `ai/docs/agents/technical/assets/pipeline_ae_layers.png` | AI-TECHNICAL-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/docs/assets/pipeline_ae_layers.svg` | `ai/docs/agents/technical/assets/pipeline_ae_layers.svg` | AI-TECHNICAL-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/docs/assets/pipeline_branches.png` | `ai/docs/agents/technical/assets/pipeline_branches.png` | AI-TECHNICAL-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/docs/assets/pipeline_branches.svg` | `ai/docs/agents/technical/assets/pipeline_branches.svg` | AI-TECHNICAL-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/docs/assets/pipeline_de_failure.png` | `ai/docs/agents/technical/assets/pipeline_de_failure.png` | AI-TECHNICAL-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/docs/assets/pipeline_de_failure.svg` | `ai/docs/agents/technical/assets/pipeline_de_failure.svg` | AI-TECHNICAL-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/docs/assets/pipeline_success.png` | `ai/docs/agents/technical/assets/pipeline_success.png` | AI-TECHNICAL-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/docs/assets/pipeline_success.svg` | `ai/docs/agents/technical/assets/pipeline_success.svg` | AI-TECHNICAL-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/docs/assets/sequence_failure.png` | `ai/docs/agents/technical/assets/sequence_failure.png` | AI-TECHNICAL-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/docs/assets/sequence_failure.svg` | `ai/docs/agents/technical/assets/sequence_failure.svg` | AI-TECHNICAL-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/docs/assets/sequence_normal.png` | `ai/docs/agents/technical/assets/sequence_normal.png` | AI-TECHNICAL-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/docs/assets/sequence_normal.svg` | `ai/docs/agents/technical/assets/sequence_normal.svg` | AI-TECHNICAL-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/docs/chart_annotation_spec.md` | `ai/docs/contracts/technical/chart_annotation_spec.md` | AI-TECHNICAL-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/docs/config.md` | `ai/docs/agents/technical/config.md` | AI-TECHNICAL-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/docs/contracts.md` | `ai/docs/contracts/technical/contracts.md` | AI-TECHNICAL-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/docs/enums.md` | `ai/docs/contracts/technical/enums.md` | AI-TECHNICAL-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/docs/frontend_mapping.md` | `ai/docs/agents/technical/frontend_mapping.md` | AI-TECHNICAL-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/docs/glossary.md` | `ai/docs/agents/technical/glossary.md` | AI-TECHNICAL-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/docs/implementation_plan.md` | `ai/docs/agents/technical/implementation_plan.md` | AI-TECHNICAL-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/docs/integration_smoke.md` | `ai/docs/agents/technical/integration_smoke.md` | AI-TECHNICAL-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/docs/kis_mapping.md` | `ai/docs/agents/technical/kis_mapping.md` | AI-TECHNICAL-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/docs/pipeline.md` | `ai/docs/agents/technical/pipeline.md` | AI-TECHNICAL-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/docs/prompts.md` | `ai/docs/agents/technical/prompts.md` | AI-TECHNICAL-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/docs/regime_rules.md` | `ai/docs/agents/technical/regime_rules.md` | AI-TECHNICAL-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/docs/schema.md` | `ai/docs/contracts/technical/schema.md` | AI-TECHNICAL-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/docs/sequence.md` | `ai/docs/agents/technical/sequence.md` | AI-TECHNICAL-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/docs/technical_coding_guidelines.md` | `ai/docs/agents/technical/technical_coding_guidelines.md` | AI-TECHNICAL-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/docs/test_plan.md` | `ai/docs/agents/technical/test_plan.md` | AI-TECHNICAL-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/docs/trace_schema.md` | `ai/docs/contracts/technical/trace_schema.md` | AI-TECHNICAL-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/docs/usecase.md` | `ai/docs/agents/technical/usecase.md` | AI-TECHNICAL-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/indicators/moving_average.py` | `ai/src/agents/technical/domain/indicators/moving_average.py` | AI-TECHNICAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/indicators/pattern.py` | `ai/src/agents/technical/domain/indicators/pattern.py` | AI-TECHNICAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/indicators/rsi.py` | `ai/src/agents/technical/domain/indicators/rsi.py` | AI-TECHNICAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/indicators/support_resistance.py` | `ai/src/agents/technical/domain/indicators/support_resistance.py` | AI-TECHNICAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/indicators/volume.py` | `ai/src/agents/technical/domain/indicators/volume.py` | AI-TECHNICAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/nodes/_llm_utils.py` | `ai/src/agents/technical/infrastructure/llm/utils.py` | AI-TECHNICAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/nodes/chart_generate.py` | `ai/src/agents/technical/application/nodes/chart_generate.py` | AI-TECHNICAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/nodes/confidence_calculate.py` | `ai/src/agents/technical/application/nodes/confidence_calculate.py` | AI-TECHNICAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/nodes/data_collect.py` | `ai/src/agents/technical/application/nodes/data_collect.py` | AI-TECHNICAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/nodes/focus_analysis.py` | `ai/src/agents/technical/application/nodes/focus_analysis.py` | AI-TECHNICAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/nodes/indicator_calculate.py` | `ai/src/agents/technical/application/nodes/indicator_calculate.py` | AI-TECHNICAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/nodes/interpret_report.py` | `ai/src/agents/technical/application/nodes/interpret_report.py` | AI-TECHNICAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/nodes/normalize_question.py` | `ai/src/agents/technical/application/nodes/normalize_question.py` | AI-TECHNICAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/nodes/regime_classify.py` | `ai/src/agents/technical/application/nodes/regime_classify.py` | AI-TECHNICAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/nodes/risk_detect.py` | `ai/src/agents/technical/application/nodes/risk_detect.py` | AI-TECHNICAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/nodes/signal_aggregate.py` | `ai/src/agents/technical/application/nodes/signal_aggregate.py` | AI-TECHNICAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/observability/keyword_rules.py` | `ai/src/agents/technical/domain/interpretation/keyword_rules.py` | AI-TECHNICAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/observability/trace_logger.py` | `ai/src/agents/technical/infrastructure/observability/trace_logger.py` | AI-TECHNICAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/observability/trajectory_eval.py` | `ai/src/agents/technical/domain/interpretation/trajectory_eval.py` | AI-TECHNICAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/prompts/focus_analysis.md` | `ai/src/agents/technical/prompts/focus_analysis.md` | AI-TECHNICAL-PROMPT-ANCHOR | 계획상 유지 / 설계 예외 |
| `ai/src/agents/technical/prompts/interpret_report.md` | `ai/src/agents/technical/prompts/interpret_report.md` | AI-TECHNICAL-PROMPT-ANCHOR | 계획상 유지 / 설계 예외 |
| `ai/src/agents/technical/prompts/normalize_question.md` | `ai/src/agents/technical/prompts/normalize_question.md` | AI-TECHNICAL-PROMPT-ANCHOR | 계획상 유지 / 설계 예외 |
| `ai/src/agents/technical/prompts/regenerate_report.md` | `ai/src/agents/technical/prompts/regenerate_report.md` | AI-TECHNICAL-PROMPT-ANCHOR | 계획상 유지 / 설계 예외 |
| `ai/src/agents/technical/regime/multiframe.py` | `ai/src/agents/technical/domain/regime/multiframe.py` | AI-TECHNICAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/regime/rules.py` | `ai/src/agents/technical/domain/regime/rules.py` | AI-TECHNICAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/runtime/deadline.py` | `ai/src/shared/runtime/deadline.py` | AI-TECHNICAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/schemas/chart.py` | `ai/src/agents/technical/domain/models/chart.py` | AI-TECHNICAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/schemas/contracts.py` | `ai/src/agents/technical/domain/models/contracts.py` | AI-TECHNICAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/schemas/enums.py` | `ai/src/agents/technical/domain/models/enums.py` | AI-TECHNICAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/schemas/intraday.py` | `ai/src/agents/technical/domain/models/intraday.py` | AI-TECHNICAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/schemas/ohlcv.py` | `ai/src/agents/technical/domain/models/ohlcv.py` | AI-TECHNICAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/scripts/diagnose_chart_annotations.py` | `ai/scripts/technical/diagnose_chart_annotations.py` | AI-TECHNICAL-SCRIPTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/scripts/smoke_intraday_minute.py` | `ai/scripts/technical/smoke_intraday_minute.py` | AI-TECHNICAL-SCRIPTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/scripts/smoke_openai_llm.py` | `ai/scripts/technical/smoke_openai_llm.py` | AI-TECHNICAL-SCRIPTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/scripts/smoke_technical_agent.py` | `ai/scripts/technical/smoke_technical_agent.py` | AI-TECHNICAL-SCRIPTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/scripts/smoke_technical_integration.py` | `ai/scripts/technical/smoke_technical_integration.py` | AI-TECHNICAL-SCRIPTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/scripts/test_kis_ohlcv.py` | `ai/scripts/technical/test_kis_ohlcv.py` | AI-TECHNICAL-SCRIPTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/services/cache_service.py` | `ai/src/agents/technical/infrastructure/cache_service.py` | AI-TECHNICAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/services/kis_client.py` | `ai/src/agents/technical/infrastructure/kis_client.py` | AI-TECHNICAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/services/openai_llm_client.py` | `ai/src/agents/technical/infrastructure/openai_llm_client.py` | AI-TECHNICAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/supervisor/langgraph_state.py` | `ai/src/agents/technical/application/orchestration/langgraph_state.py` | AI-TECHNICAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/supervisor/pipeline_steps.py` | `ai/src/agents/technical/application/orchestration/pipeline_steps.py` | AI-TECHNICAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/supervisor/technical_graph.py` | `ai/src/agents/technical/application/orchestration/technical_graph.py` | AI-TECHNICAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/supervisor/technical_supervisor.py` | `ai/src/agents/technical/application/orchestration/technical_supervisor.py` | AI-TECHNICAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/synthesis/confidence.py` | `ai/src/agents/technical/domain/synthesis/confidence.py` | AI-TECHNICAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/synthesis/intraday_adjustment.py` | `ai/src/agents/technical/domain/synthesis/intraday_adjustment.py` | AI-TECHNICAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/synthesis/intraday_alignment.py` | `ai/src/agents/technical/domain/synthesis/intraday_alignment.py` | AI-TECHNICAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/synthesis/risk.py` | `ai/src/agents/technical/domain/synthesis/risk.py` | AI-TECHNICAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/synthesis/signal_score.py` | `ai/src/agents/technical/domain/synthesis/signal_score.py` | AI-TECHNICAL-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/tests/test_agent_entrypoint.py` | `ai/tests/technical/test_agent_entrypoint.py` | AI-TECHNICAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/tests/test_ai_endpoint.py` | `ai/tests/technical/test_ai_endpoint.py` | AI-TECHNICAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/tests/test_cache_service.py` | `ai/tests/technical/test_cache_service.py` | AI-TECHNICAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/tests/test_chart_annotation_diagnostics.py` | `ai/tests/technical/test_chart_annotation_diagnostics.py` | AI-TECHNICAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/tests/test_chart_builder.py` | `ai/tests/technical/test_chart_builder.py` | AI-TECHNICAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/tests/test_contracts.py` | `ai/tests/technical/test_contracts.py` | AI-TECHNICAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/tests/test_indicators.py` | `ai/tests/technical/test_indicators.py` | AI-TECHNICAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/tests/test_interpret_report.py` | `ai/tests/technical/test_interpret_report.py` | AI-TECHNICAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/tests/test_intraday_adjustment.py` | `ai/tests/technical/test_intraday_adjustment.py` | AI-TECHNICAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/tests/test_intraday_alignment.py` | `ai/tests/technical/test_intraday_alignment.py` | AI-TECHNICAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/tests/test_intraday_chart_builder.py` | `ai/tests/technical/test_intraday_chart_builder.py` | AI-TECHNICAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/tests/test_intraday_context.py` | `ai/tests/technical/test_intraday_context.py` | AI-TECHNICAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/tests/test_intraday_context_builder.py` | `ai/tests/technical/test_intraday_context_builder.py` | AI-TECHNICAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/tests/test_intraday_flag.py` | `ai/tests/technical/test_intraday_flag.py` | AI-TECHNICAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/tests/test_kis_client_mapping.py` | `ai/tests/technical/test_kis_client_mapping.py` | AI-TECHNICAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/tests/test_kis_intraday_client.py` | `ai/tests/technical/test_kis_intraday_client.py` | AI-TECHNICAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/tests/test_multiframe.py` | `ai/tests/technical/test_multiframe.py` | AI-TECHNICAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/tests/test_node_adapters.py` | `ai/tests/technical/test_node_adapters.py` | AI-TECHNICAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/tests/test_openai_llm_client.py` | `ai/tests/technical/test_openai_llm_client.py` | AI-TECHNICAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/tests/test_preprocess_nodes.py` | `ai/tests/technical/test_preprocess_nodes.py` | AI-TECHNICAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/tests/test_regime_rules.py` | `ai/tests/technical/test_regime_rules.py` | AI-TECHNICAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/tests/test_synthesis.py` | `ai/tests/technical/test_synthesis.py` | AI-TECHNICAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/tests/test_technical_langgraph.py` | `ai/tests/technical/test_technical_langgraph.py` | AI-TECHNICAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/tests/test_technical_supervisor.py` | `ai/tests/technical/test_technical_supervisor.py` | AI-TECHNICAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/tests/test_trace_logger.py` | `ai/tests/technical/test_trace_logger.py` | AI-TECHNICAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/agents/technical/tests/test_trajectory_eval.py` | `ai/tests/technical/test_trajectory_eval.py` | AI-TECHNICAL-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/api/dependencies.py` | `ai/src/api/dependencies.py` | AI-DI-STAGED | 계획상 유지 / 설계 예외 |
| `ai/src/api/errors.py` | `ai/src/shared/api/errors.py` | AI-SHARED | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/api/fundamental.py` | `ai/src/agents/fundamental/api/routes.py` | AI-FUNDAMENTAL-API | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/api/industry.py` | `ai/src/agents/industry/api/routes.py` | AI-INDUSTRY-API | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/api/supervisor.py` | `ai/src/supervisor/api/routes.py` | AI-SUPERVISOR-API | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/api/technical.py` | `ai/src/agents/technical/api/routes.py` | AI-TECHNICAL-API | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/main.py` | `ai/src/main.py` | AI-COMPOSITION | 계획상 유지 / 설계 예외 |
| `ai/src/supervisor/README.md` | `ai/src/supervisor/README.md` | AI-SUPERVISOR-ENTRY | 계획상 유지 / 설계 예외 |
| `ai/src/supervisor/config.py` | `ai/src/supervisor/config.py` | AI-SUPERVISOR-CONFIG-ANCHOR | 계획상 유지 / 설계 예외 |
| `ai/src/supervisor/devtools/streamlit_supervisor_news_lab.py` | `ai/devtools/supervisor/streamlit_supervisor_news_lab.py` | AI-SUPERVISOR-DEVTOOLS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/supervisor/docs/fallback_promotion.md` | `ai/docs/agents/supervisor/fallback_promotion.md` | AI-SUPERVISOR-DOCS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/supervisor/execution/adapters.py` | `ai/src/supervisor/application/execution/adapters.py` | AI-SUPERVISOR-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/supervisor/execution/executor.py` | `ai/src/supervisor/application/execution/executor.py` | AI-SUPERVISOR-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/supervisor/execution/schemas.py` | `ai/src/supervisor/domain/execution.py` | AI-SUPERVISOR-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/supervisor/planning/data/dart_corp_snapshot.json` | `ai/src/supervisor/planning/data/dart_corp_snapshot.json` | AI-SUPERVISOR-DATA-ANCHOR | 계획상 유지 / 설계 예외 |
| `ai/src/supervisor/planning/fallback_lookup.py` | `ai/src/supervisor/domain/planning/fallback_lookup.py` | AI-SUPERVISOR-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/supervisor/planning/fallback_observer.py` | `ai/src/supervisor/infrastructure/observability/fallback_observer.py` | AI-SUPERVISOR-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/supervisor/planning/fallback_promotion.py` | `ai/src/supervisor/domain/planning/fallback_promotion.py` | AI-SUPERVISOR-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/supervisor/planning/fallback_source.py` | `ai/src/supervisor/application/planning/fallback_source.py` | AI-SUPERVISOR-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/supervisor/planning/fallback_source_dart.py` | `ai/src/supervisor/infrastructure/dart/fallback_source.py` | AI-SUPERVISOR-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/supervisor/planning/interpret.py` | `ai/src/supervisor/domain/planning/interpret.py` | AI-SUPERVISOR-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/supervisor/planning/planner.py` | `ai/src/supervisor/application/planning/planner.py` | AI-SUPERVISOR-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/supervisor/planning/policy.py` | `ai/src/supervisor/domain/planning/policy.py` | AI-SUPERVISOR-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/supervisor/planning/resolve_client.py` | `ai/src/supervisor/infrastructure/backend/resolve_client.py` | AI-SUPERVISOR-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/supervisor/planning/rewrite.py` | `ai/src/supervisor/domain/planning/rewrite.py` | AI-SUPERVISOR-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/supervisor/planning/rewrite_llm.py` | `ai/src/supervisor/application/planning/rewrite_llm.py` | AI-SUPERVISOR-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/supervisor/runtime.py` | `ai/src/supervisor/application/runtime.py` | AI-SUPERVISOR-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/supervisor/schemas.py` | `ai/src/supervisor/domain/models.py` | AI-SUPERVISOR-SOURCE | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/supervisor/scripts/collect_fallback_candidates.py` | `ai/scripts/supervisor/collect_fallback_candidates.py` | AI-SUPERVISOR-SCRIPTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/supervisor/scripts/smoke_supervisor.py` | `ai/scripts/supervisor/smoke_supervisor.py` | AI-SUPERVISOR-SCRIPTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/supervisor/tests/_fakes.py` | `ai/tests/supervisor/_fakes.py` | AI-SUPERVISOR-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/supervisor/tests/test_agent_adapters.py` | `ai/tests/supervisor/test_agent_adapters.py` | AI-SUPERVISOR-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/supervisor/tests/test_executor.py` | `ai/tests/supervisor/test_executor.py` | AI-SUPERVISOR-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/supervisor/tests/test_fallback_lookup.py` | `ai/tests/supervisor/test_fallback_lookup.py` | AI-SUPERVISOR-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/supervisor/tests/test_fallback_observability.py` | `ai/tests/supervisor/test_fallback_observability.py` | AI-SUPERVISOR-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/supervisor/tests/test_fallback_promotion.py` | `ai/tests/supervisor/test_fallback_promotion.py` | AI-SUPERVISOR-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/supervisor/tests/test_fallback_source.py` | `ai/tests/supervisor/test_fallback_source.py` | AI-SUPERVISOR-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/supervisor/tests/test_fallback_source_dart.py` | `ai/tests/supervisor/test_fallback_source_dart.py` | AI-SUPERVISOR-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/supervisor/tests/test_interpret.py` | `ai/tests/supervisor/test_interpret.py` | AI-SUPERVISOR-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/supervisor/tests/test_policy.py` | `ai/tests/supervisor/test_policy.py` | AI-SUPERVISOR-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/supervisor/tests/test_resolve_client.py` | `ai/tests/supervisor/test_resolve_client.py` | AI-SUPERVISOR-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/supervisor/tests/test_rewrite.py` | `ai/tests/supervisor/test_rewrite.py` | AI-SUPERVISOR-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/supervisor/tests/test_rewrite_llm.py` | `ai/tests/supervisor/test_rewrite_llm.py` | AI-SUPERVISOR-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/supervisor/tests/test_supervisor.py` | `ai/tests/supervisor/test_supervisor.py` | AI-SUPERVISOR-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/supervisor/tests/test_supervisor_endpoint.py` | `ai/tests/supervisor/test_supervisor_endpoint.py` | AI-SUPERVISOR-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/src/supervisor/tests/test_supervisor_runtime.py` | `ai/tests/supervisor/test_supervisor_runtime.py` | AI-SUPERVISOR-TESTS | 실제 이동·독립 정적 수용 / AI 실행 미검증 |
| `ai/uv.lock` | `ai/uv.lock` | AI-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/AGENTS.md` | `backend/AGENTS.md` | DOC-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/README.md` | `backend/README.md` | DOC-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/alembic.ini` | `backend/alembic.ini` | PERSISTENCE-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/db/DATA_MODEL.md` | `backend/db/DATA_MODEL.md` | PERSISTENCE-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/db/base.py` | `backend/db/base.py` | PERSISTENCE-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/db/graph/__init__.py` | `backend/db/graph/__init__.py` | PERSISTENCE-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/db/graph/bootstrap.py` | `backend/db/graph/bootstrap.py` | PERSISTENCE-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/db/graph/driver.py` | `backend/db/graph/driver.py` | PERSISTENCE-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/db/migrations/env.py` | `backend/db/migrations/env.py` | PERSISTENCE-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/db/migrations/script.py.mako` | `backend/db/migrations/script.py.mako` | PERSISTENCE-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/db/migrations/versions/20260707_4a21292e89fc_add_stock_aliases.py` | `backend/db/migrations/versions/20260707_4a21292e89fc_add_stock_aliases.py` | PERSISTENCE-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/db/migrations/versions/20260707_705a5833d4a3_add_integrated_postgresql_schema.py` | `backend/db/migrations/versions/20260707_705a5833d4a3_add_integrated_postgresql_schema.py` | PERSISTENCE-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/db/migrations/versions/20260707_c7dbcc78614f_extend_industry_reports_schema.py` | `backend/db/migrations/versions/20260707_c7dbcc78614f_extend_industry_reports_schema.py` | PERSISTENCE-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/db/migrations/versions/20260708_6ca978063906_add_stock_corp_codes.py` | `backend/db/migrations/versions/20260708_6ca978063906_add_stock_corp_codes.py` | PERSISTENCE-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/db/migrations/versions/20260709_b1e9d4a7c2f1_connect_technical_and_flow_reports_to_stocks.py` | `backend/db/migrations/versions/20260709_b1e9d4a7c2f1_connect_technical_and_flow_reports_to_stocks.py` | PERSISTENCE-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/db/migrations/versions/20261107_c2001a7e0001_auth_and_flow_owner.py` | `backend/db/migrations/versions/20261107_c2001a7e0001_auth_and_flow_owner.py` | PERSISTENCE-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/db/models/_shared.py` | `backend/db/models/_shared.py` | PERSISTENCE-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/db/models/auth/__init__.py` | `backend/db/models/auth/__init__.py` | PERSISTENCE-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/db/models/auth/models.py` | `backend/db/models/auth/models.py` | PERSISTENCE-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/db/models/common/agent_report.py` | `backend/db/models/common/agent_report.py` | PERSISTENCE-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/db/models/common/stock.py` | `backend/db/models/common/stock.py` | PERSISTENCE-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/db/models/common/stock_alias.py` | `backend/db/models/common/stock_alias.py` | PERSISTENCE-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/db/models/common/stock_corp_code.py` | `backend/db/models/common/stock_corp_code.py` | PERSISTENCE-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/db/models/flow/flow_report.py` | `backend/db/models/flow/flow_report.py` | PERSISTENCE-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/db/models/flow/report_interpretation.py` | `backend/db/models/flow/report_interpretation.py` | PERSISTENCE-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/db/models/flow/report_verification.py` | `backend/db/models/flow/report_verification.py` | PERSISTENCE-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/db/models/fundamental/fundamental_report.py` | `backend/db/models/fundamental/fundamental_report.py` | PERSISTENCE-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/db/models/fundamental/report_evidence.py` | `backend/db/models/fundamental/report_evidence.py` | PERSISTENCE-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/db/models/fundamental/report_filing_snippet.py` | `backend/db/models/fundamental/report_filing_snippet.py` | PERSISTENCE-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/db/models/fundamental/report_insight.py` | `backend/db/models/fundamental/report_insight.py` | PERSISTENCE-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/db/models/fundamental/report_interpretation.py` | `backend/db/models/fundamental/report_interpretation.py` | PERSISTENCE-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/db/models/fundamental/report_ratio.py` | `backend/db/models/fundamental/report_ratio.py` | PERSISTENCE-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/db/models/fundamental/report_verification.py` | `backend/db/models/fundamental/report_verification.py` | PERSISTENCE-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/db/models/industry/industry_report.py` | `backend/db/models/industry/industry_report.py` | PERSISTENCE-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/db/models/news/SCHEMA_SPEC.md` | `backend/db/models/news/SCHEMA_SPEC.md` | PERSISTENCE-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/db/models/news/news.py` | `backend/db/models/news/news.py` | PERSISTENCE-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/db/models/news/news_report.py` | `backend/db/models/news/news_report.py` | PERSISTENCE-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/db/models/registry.py` | `backend/db/models/registry.py` | PERSISTENCE-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/db/models/technical/report_chart.py` | `backend/db/models/technical/report_chart.py` | PERSISTENCE-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/db/models/technical/report_followup.py` | `backend/db/models/technical/report_followup.py` | PERSISTENCE-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/db/models/technical/report_interpretation.py` | `backend/db/models/technical/report_interpretation.py` | PERSISTENCE-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/db/models/technical/report_risk_note.py` | `backend/db/models/technical/report_risk_note.py` | PERSISTENCE-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/db/models/technical/report_signal.py` | `backend/db/models/technical/report_signal.py` | PERSISTENCE-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/db/models/technical/report_verification.py` | `backend/db/models/technical/report_verification.py` | PERSISTENCE-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/db/models/technical/technical_report.py` | `backend/db/models/technical/technical_report.py` | PERSISTENCE-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/db/session.py` | `backend/db/session.py` | PERSISTENCE-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/docs/backend_coding_guidelines.md` | `backend/docs/backend_coding_guidelines.md` | DOC-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/docs/cf002_commit_pr.md` | `backend/docs/cf002_commit_pr.md` | DOC-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/docs/cf002_pr_body.md` | `backend/docs/cf002_pr_body.md` | DOC-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/docs/dart_corp_code_sync.md` | `backend/docs/dart_corp_code_sync.md` | DOC-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/docs/db_boundaries.md` | `backend/docs/db_boundaries.md` | DOC-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/docs/flow_auth_ownership.md` | `backend/docs/flow_auth_ownership.md` | DOC-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/docs/flow_backend_handoff.md` | `backend/docs/flow_backend_handoff.md` | DOC-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/docs/flow_contract.md` | `backend/docs/flow_contract.md` | DOC-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/docs/fundamental_corp_code_handoff.md` | `backend/docs/fundamental_corp_code_handoff.md` | DOC-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/docs/google_login_check.md` | `backend/docs/google_login_check.md` | DOC-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/docs/industry_backend_handoff.md` | `backend/docs/industry_backend_handoff.md` | DOC-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/docs/industry_report_html_frontend_handoff.md` | `backend/docs/industry_report_html_frontend_handoff.md` | DOC-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/docs/migrations.md` | `backend/docs/migrations.md` | DOC-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/docs/news_backend_handoff.md` | `backend/docs/news_backend_handoff.md` | DOC-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/docs/report_archive_api_contract.md` | `backend/docs/report_archive_api_contract.md` | DOC-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/docs/schema.md` | `backend/docs/schema.md` | DOC-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/docs/stock_master_sync.md` | `backend/docs/stock_master_sync.md` | DOC-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/docs/stock_resolver.md` | `backend/docs/stock_resolver.md` | DOC-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/docs/supervisor_backend_integration.md` | `backend/docs/supervisor_backend_integration.md` | DOC-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/docs/technical_backend_handoff.md` | `backend/docs/technical_backend_handoff.md` | DOC-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/docs/technical_followup_answer_boundary.md` | `backend/docs/technical_followup_answer_boundary.md` | DOC-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/docs/technical_frontend_api_contract.md` | `backend/docs/technical_frontend_api_contract.md` | DOC-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/dumps/README.md` | `backend/dumps/README.md` | DOC-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/dumps/shared_industry_neo4j.cypher` | `backend/dumps/shared_industry_neo4j.cypher` | PROTECTED-DATA | 계획상 유지 / 설계 예외 |
| `backend/dumps/shared_industry_pg.sql` | `backend/dumps/shared_industry_pg.sql` | PROTECTED-DATA | 계획상 유지 / 설계 예외 |
| `backend/dumps/shared_news_neo4j.cypher` | `backend/dumps/shared_news_neo4j.cypher` | PROTECTED-DATA | 계획상 유지 / 설계 예외 |
| `backend/dumps/shared_news_pg.sql` | `backend/dumps/shared_news_pg.sql` | PROTECTED-DATA | 계획상 유지 / 설계 예외 |
| `backend/dumps/shared_verith_snapshot.sql` | `backend/dumps/shared_verith_snapshot.sql` | PROTECTED-DATA | 계획상 유지 / 설계 예외 |
| `backend/pyproject.toml` | `backend/pyproject.toml` | TOOLCHAIN-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/scripts/cf002_concurrency_check.py` | `backend/scripts/cf002_concurrency_check.py` | CLI-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/scripts/cf002_controller_check.py` | `backend/scripts/cf002_controller_check.py` | CLI-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/scripts/cf002_interactive_login.py` | `backend/scripts/cf002_interactive_login.py` | CLI-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/scripts/cf002_migration_check.py` | `backend/scripts/cf002_migration_check.py` | CLI-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/scripts/check_cf002_database.py` | `backend/scripts/check_cf002_database.py` | CLI-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/scripts/check_safe.py` | `backend/scripts/check_safe.py` | TOOLING-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/scripts/export_industry_graph.py` | `backend/scripts/export_industry_graph.py` | CLI-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/scripts/export_industry_pg.py` | `backend/scripts/export_industry_pg.py` | CLI-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/scripts/export_news_graph.py` | `backend/scripts/export_news_graph.py` | CLI-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/scripts/export_news_pg.py` | `backend/scripts/export_news_pg.py` | CLI-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/scripts/google_login_bootstrap.py` | `backend/scripts/google_login_bootstrap.py` | CLI-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/scripts/google_login_controller.py` | `backend/scripts/google_login_controller.py` | CLI-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/scripts/google_login_inputs.py` | `backend/scripts/google_login_inputs.py` | CLI-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/scripts/google_login_workspace.py` | `backend/scripts/google_login_workspace.py` | CLI-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/scripts/runner_owned_database.py` | `backend/scripts/runner_owned_database.py` | CLI-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/scripts/safe_checks_bootstrap.py` | `backend/scripts/safe_checks_bootstrap.py` | TOOLING-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/scripts/seed_representative_stocks.py` | `backend/scripts/seed_representative_stocks.py` | CLI-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/scripts/seed_stock_aliases.py` | `backend/scripts/seed_stock_aliases.py` | CLI-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/scripts/seed_stocks.py` | `backend/scripts/seed_stocks.py` | CLI-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/scripts/sync_corp_codes.py` | `backend/scripts/sync_corp_codes.py` | CLI-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/scripts/sync_stocks.py` | `backend/scripts/sync_stocks.py` | CLI-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/src/api/access_boundary.py` | `backend/src/shared/http/access_boundary.py` | B10-shared-composition | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/auth/__init__.py` | `backend/src/api/auth/__init__.py` | B09-auth | 계획상 유지 / 설계 예외 |
| `backend/src/api/auth/google.py` | `backend/src/modules/auth/infrastructure/google_oidc.py` | B09-auth | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/clients/ai_client.py` | `backend/src/shared/infrastructure/clients/ai_client.py` | B10-shared-composition | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/clients/dart_corp_code_client.py` | `backend/src/modules/stocks/infrastructure/dart_corp_code_client.py` | B03-stocks | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/clients/kis_master_client.py` | `backend/src/modules/stocks/infrastructure/kis_master_client.py` | B03-stocks | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/config.py` | `backend/src/shared/config.py` | B10-shared-composition | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/constants/importance.py` | `backend/src/modules/news/domain/importance_rules.py` | B07-news | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/constants/kis_master.py` | `backend/src/modules/stocks/domain/constants/kis_master.py` | B03-stocks | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/constants/stock_aliases.py` | `backend/src/modules/stocks/domain/constants/stock_aliases.py` | B03-stocks | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/constants/stock_match.py` | `backend/src/modules/stocks/domain/constants/stock_match.py` | B03-stocks | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/constants/stocks.py` | `backend/src/modules/stocks/domain/constants/stocks.py` | B03-stocks | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/deps.py` | `backend/src/api/deps.py` | B10-shared-composition | 계획상 유지 / 설계 예외 |
| `backend/src/api/main.py` | `backend/src/api/main.py` | B10-shared-composition | 계획상 유지 / 설계 예외 |
| `backend/src/api/repositories/agent_report_repository.py` | `backend/src/modules/reports/infrastructure/agent_report_repository.py` | B08-reports | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/repositories/corp_code_repository.py` | `backend/src/modules/stocks/infrastructure/corp_code_repository.py` | B03-stocks | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/repositories/flow_report_repository.py` | `backend/src/modules/flow/infrastructure/report_repository.py` | B02-flow-application-repository | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/repositories/fundamental_report_repository.py` | `backend/src/modules/fundamental/infrastructure/report_repository.py` | B05-fundamental | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/repositories/industry_report_repository.py` | `backend/src/modules/industry/infrastructure/report_repository.py` | B06-industry | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/repositories/news_graph_repository.py` | `backend/src/modules/news/infrastructure/news_graph_repository.py` | B07-news | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/repositories/news_report_repository.py` | `backend/src/modules/news/infrastructure/report_repository.py` | B07-news | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/repositories/news_repository.py` | `backend/src/modules/news/infrastructure/news_repository.py` | B07-news | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/repositories/stock_repository.py` | `backend/src/modules/stocks/infrastructure/stock_repository.py` | B03-stocks | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/repositories/technical_report_repository.py` | `backend/src/modules/technical/infrastructure/report_repository.py` | B04-technical | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/routes/auth.py` | `backend/src/modules/auth/api/router.py` | B09-auth | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/routes/flow_reports.py` | `backend/src/modules/flow/api/router.py` | 4-A | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/routes/fundamental_reports.py` | `backend/src/modules/fundamental/api/router.py` | B05-fundamental | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/routes/industry_reports.py` | `backend/src/modules/industry/api/router.py` | B06-industry | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/routes/news.py` | `backend/src/modules/news/api/router.py` | B07-news | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/routes/reports.py` | `backend/src/modules/reports/api/router.py` | B08-reports | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/routes/stocks.py` | `backend/src/modules/stocks/api/router.py` | B03-stocks | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/routes/technical_reports.py` | `backend/src/modules/technical/api/router.py` | B04-technical | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/schemas/agent_report.py` | `backend/src/modules/reports/api/report_schemas.py` | B08-reports | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/schemas/ai_fundamental_output.py` | `backend/src/modules/fundamental/domain/ai_output.py` | B05-fundamental | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/schemas/ai_technical_output.py` | `backend/src/modules/technical/domain/ai_output.py` | B04-technical | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/schemas/flow_execution.py` | `backend/src/modules/flow/domain/execution.py` | 4-A | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/schemas/flow_payload.py` | `backend/src/modules/flow/domain/payload.py` | 4-A | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/schemas/flow_report.py` | `backend/src/modules/flow/api/schemas.py` | 4-A | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/schemas/fundamental_report.py` | `backend/src/modules/fundamental/api/schemas.py` | B05-fundamental | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/schemas/industry_report.py` | `backend/src/modules/industry/api/schemas.py` | B06-industry | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/schemas/news.py` | `backend/src/modules/news/api/schemas.py` | B07-news | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/schemas/news_report.py` | `backend/src/modules/news/api/report_schemas.py` | B07-news | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/schemas/report_archive.py` | `backend/src/modules/reports/api/archive_schemas.py` | B08-reports | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/schemas/stock_resolve.py` | `backend/src/modules/stocks/api/schemas.py` | B03-stocks | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/schemas/technical_report.py` | `backend/src/modules/technical/api/schemas.py` | B04-technical | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/services/auth_service.py` | `backend/src/modules/auth/application/session_service.py` | B09-auth | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/services/corp_code_sync_service.py` | `backend/src/modules/stocks/application/corp_code_sync_service.py` | B03-stocks | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/services/dart_corp_code_parser.py` | `backend/src/modules/stocks/domain/dart_corp_code_parser.py` | B03-stocks | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/services/flow_report_service.py` | `backend/src/modules/flow/application/report_service.py` | B02-flow-application-repository | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/services/fundamental_report_service.py` | `backend/src/modules/fundamental/application/report_service.py` | B05-fundamental | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/services/importance.py` | `backend/src/modules/news/domain/importance.py` | B07-news | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/services/industry_report_service.py` | `backend/src/modules/industry/application/report_service.py` | B06-industry | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/services/news_cleanup_service.py` | `backend/src/modules/news/application/cleanup_service.py` | B07-news | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/services/news_graph_query_service.py` | `backend/src/modules/news/application/graph_query_service.py` | B07-news | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/services/news_query_service.py` | `backend/src/modules/news/application/query_service.py` | B07-news | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/services/news_report_service.py` | `backend/src/modules/news/application/report_service.py` | B07-news | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/services/news_service.py` | `backend/src/modules/news/application/ingest_service.py` | B07-news | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/services/stock_master_parser.py` | `backend/src/modules/stocks/domain/stock_master_parser.py` | B03-stocks | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/services/stock_resolver_service.py` | `backend/src/modules/stocks/application/resolver_service.py` | B03-stocks | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/services/stock_sync_service.py` | `backend/src/modules/stocks/application/stock_sync_service.py` | B03-stocks | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/services/technical_report_service.py` | `backend/src/modules/technical/application/report_service.py` | B04-technical | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/src/api/text_normalize.py` | `backend/src/modules/stocks/domain/text_normalize.py` | B03-stocks | 실제 구현 이동·old shim 제거·독립 정적 수용 / 보호 회귀 통과 |
| `backend/tests/conftest.py` | `backend/tests/conftest.py` | TEST-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/tests/db_safety.py` | `backend/tests/db_safety.py` | TEST-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/tests/fixtures/ai_output.py` | `backend/tests/fixtures/ai_output.py` | TEST-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/tests/fixtures/dart_corp_code.py` | `backend/tests/fixtures/dart_corp_code.py` | TEST-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/tests/fixtures/flow_payload.py` | `backend/tests/fixtures/flow_payload.py` | TEST-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/tests/fixtures/kis_master.py` | `backend/tests/fixtures/kis_master.py` | TEST-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/tests/flow_integration/conftest.py` | `backend/tests/flow_integration/conftest.py` | TEST-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/tests/flow_integration/test_cf002_auth_ownership.py` | `backend/tests/flow_integration/test_cf002_auth_ownership.py` | TEST-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/tests/flow_integration/test_cf002_preflight.py` | `backend/tests/flow_integration/test_cf002_preflight.py` | TEST-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/tests/flow_integration/test_flow_persistence.py` | `backend/tests/flow_integration/test_flow_persistence.py` | TEST-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/tests/safe_checks/test_entry.py` | `backend/tests/safe_checks/test_entry.py` | TOOLING-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/tests/test_ai_client.py` | `backend/tests/test_ai_client.py` | TEST-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/tests/test_corp_code_sync_service.py` | `backend/tests/test_corp_code_sync_service.py` | TEST-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/tests/test_dart_corp_code_client.py` | `backend/tests/test_dart_corp_code_client.py` | TEST-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/tests/test_dart_corp_code_parser.py` | `backend/tests/test_dart_corp_code_parser.py` | TEST-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/tests/test_fundamental_reports.py` | `backend/tests/test_fundamental_reports.py` | TEST-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/tests/test_importance.py` | `backend/tests/test_importance.py` | TEST-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/tests/test_industry_reports.py` | `backend/tests/test_industry_reports.py` | TEST-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/tests/test_kis_master_client.py` | `backend/tests/test_kis_master_client.py` | TEST-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/tests/test_news_cleanup.py` | `backend/tests/test_news_cleanup.py` | TEST-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/tests/test_news_query.py` | `backend/tests/test_news_query.py` | TEST-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/tests/test_news_recent.py` | `backend/tests/test_news_recent.py` | TEST-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/tests/test_news_reports.py` | `backend/tests/test_news_reports.py` | TEST-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/tests/test_news_save.py` | `backend/tests/test_news_save.py` | TEST-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/tests/test_news_subject_query.py` | `backend/tests/test_news_subject_query.py` | TEST-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/tests/test_report_archive.py` | `backend/tests/test_report_archive.py` | TEST-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/tests/test_seed_representative_stocks.py` | `backend/tests/test_seed_representative_stocks.py` | TEST-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/tests/test_seed_stocks.py` | `backend/tests/test_seed_stocks.py` | TEST-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/tests/test_stock_aliases_db.py` | `backend/tests/test_stock_aliases_db.py` | TEST-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/tests/test_stock_master_parser.py` | `backend/tests/test_stock_master_parser.py` | TEST-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/tests/test_stock_resolve_api.py` | `backend/tests/test_stock_resolve_api.py` | TEST-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/tests/test_stock_resolver.py` | `backend/tests/test_stock_resolver.py` | TEST-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/tests/test_stock_resolver_boundary.py` | `backend/tests/test_stock_resolver_boundary.py` | TEST-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/tests/test_stock_resolver_semantics.py` | `backend/tests/test_stock_resolver_semantics.py` | TEST-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/tests/test_stock_sync_service.py` | `backend/tests/test_stock_sync_service.py` | TEST-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/tests/test_technical_read_model.py` | `backend/tests/test_technical_read_model.py` | TEST-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/tests/test_technical_reports.py` | `backend/tests/test_technical_reports.py` | TEST-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/tests/test_text_normalize.py` | `backend/tests/test_text_normalize.py` | TEST-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/tests/unit/conftest.py` | `backend/tests/unit/conftest.py` | TEST-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/tests/unit/test_cf002_boundary.py` | `backend/tests/unit/test_cf002_boundary.py` | TEST-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/tests/unit/test_cf002_google.py` | `backend/tests/unit/test_cf002_google.py` | TEST-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/tests/unit/test_cf002_local_ports.py` | `backend/tests/unit/test_cf002_local_ports.py` | TEST-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/tests/unit/test_cf002_review_regressions.py` | `backend/tests/unit/test_cf002_review_regressions.py` | TEST-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/tests/unit/test_cf002_session_failures.py` | `backend/tests/unit/test_cf002_session_failures.py` | TEST-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/tests/unit/test_flow_contract.py` | `backend/tests/unit/test_flow_contract.py` | TEST-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/tests/unit/test_google_login_controller.py` | `backend/tests/unit/test_google_login_controller.py` | TEST-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/tests/unit/test_google_login_inputs.py` | `backend/tests/unit/test_google_login_inputs.py` | TEST-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/tests/unit/test_google_login_workspace.py` | `backend/tests/unit/test_google_login_workspace.py` | TEST-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/tests/unit/test_interactive_runner_security.py` | `backend/tests/unit/test_interactive_runner_security.py` | TEST-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/tests/unit/test_runner_owned_database.py` | `backend/tests/unit/test_runner_owned_database.py` | TEST-ANCHOR | 계획상 유지 / 설계 예외 |
| `backend/uv.lock` | `backend/uv.lock` | TOOLCHAIN-ANCHOR | 계획상 유지 / 설계 예외 |
| `docs/.gitkeep` | `docs/.gitkeep` | ROOT-ANCHOR | 최종 승인 불필요 marker 제거 / retain disposition |
| `docs/architecture/current-boundaries.md` | `docs/architecture/current-boundaries.md` | ROOT-ANCHOR | 계획상 유지 / 설계 예외 |
| `docs/contracts/CF-001-v1.1.shared-v1.md` | `docs/contracts/CF-001-v1.1.shared-v1.md` | ROOT-ANCHOR | 계획상 유지 / 설계 예외 |
| `docs/contracts/CF-002-v0.6.shared-v1.md` | `docs/contracts/CF-002-v0.6.shared-v1.md` | ROOT-ANCHOR | 계획상 유지 / 설계 예외 |
| `docs/contracts/manifest.json` | `docs/contracts/manifest.json` | ROOT-ANCHOR | 계획상 유지 / 설계 예외 |
| `docs/development.md` | `docs/development.md` | ROOT-ANCHOR | 계획상 유지 / 설계 예외 |
| `docs/documentation.md` | `docs/documentation.md` | ROOT-ANCHOR | 계획상 유지 / 설계 예외 |
| `docs/examples/ai.env.example` | `docs/examples/ai.env.example` | ROOT-ANCHOR | 계획상 유지 / 설계 예외 |
| `docs/examples/backend.env.example` | `docs/examples/backend.env.example` | ROOT-ANCHOR | 계획상 유지 / 설계 예외 |
| `docs/examples/compose.local.example.yaml` | `docs/examples/compose.local.example.yaml` | ROOT-ANCHOR | 계획상 유지 / 설계 예외 |
| `docs/examples/frontend.env.example` | `docs/examples/frontend.env.example` | ROOT-ANCHOR | 계획상 유지 / 설계 예외 |
| `docs/local_ports.md` | `docs/local_ports.md` | ROOT-ANCHOR | 계획상 유지 / 설계 예외 |
| `docs/work/ST-001-stage-1-commands.md` | `docs/work/ST-001-stage-1-commands.md` | ROOT-ANCHOR | 계획상 유지 / 설계 예외 |
| `docs/work/ST-001-stage-1-pr.md` | `docs/work/ST-001-stage-1-pr.md` | ROOT-ANCHOR | 계획상 유지 / 설계 예외 |
| `docs/work/ST-001-stage-1.md` | `docs/work/ST-001-stage-1.md` | ROOT-ANCHOR | 계획상 유지 / 설계 예외 |
| `docs/work/ST-001-stage-2.md` | `docs/work/ST-001-stage-2.md` | ROOT-ANCHOR | 계획상 유지 / 설계 예외 |
| `docs/work/ST-001-stage-3-A.md` | `docs/work/ST-001-stage-3-A.md` | ROOT-ANCHOR | 계획상 유지 / 설계 예외 |
| `docs/work/ST-001-stage-3-B.md` | `docs/work/ST-001-stage-3-B.md` | TOOLING-ANCHOR | 계획상 유지 / 설계 예외 |
| `docs/work/ST-001-stage-4-A.md` | `docs/work/ST-001-stage-4-A.md` | TOOLING-ANCHOR | 계획상 유지 / 설계 예외 |
| `frontend/.gitignore` | `frontend/.gitignore` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/AGENTS.md` | `frontend/AGENTS.md` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/CLAUDE.md` | `frontend/CLAUDE.md` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/README.md` | `frontend/README.md` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/docs/frontend_coding_guidelines.md` | `frontend/docs/coding-guidelines.md` | FE-04 | 실제 이동·독립 정적 수용 / self·unit 통과·type 차단·lint 기존 2건 |
| `frontend/eslint.config.mjs` | `frontend/eslint.config.mjs` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/next.config.ts` | `frontend/next.config.ts` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/package-lock.json` | `frontend/package-lock.json` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/package.json` | `frontend/package.json` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/postcss.config.mjs` | `frontend/postcss.config.mjs` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/public/file.svg` | `frontend/public/file.svg` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/public/globe.svg` | `frontend/public/globe.svg` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/public/next.svg` | `frontend/public/next.svg` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/public/vercel.svg` | `frontend/public/vercel.svg` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/public/window.svg` | `frontend/public/window.svg` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/scripts/check-local-ports.mjs` | `frontend/scripts/check-local-ports.mjs` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/scripts/safe-checks-guard.cjs` | `frontend/scripts/safe-checks-guard.cjs` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/api/archive.ts` | `frontend/src/features/archive/api/reports.ts` | FE-02 | 실제 이동·독립 정적 수용 / self·unit 통과·type 차단·lint 기존 2건 |
| `frontend/src/api/backend.ts` | `frontend/src/shared/api/backend.ts` | FE-01 | 실제 이동·unit/type/대상 lint 통과 / 독립 정적 수용 완료 |
| `frontend/src/api/flow-create.ts` | `frontend/src/features/flow/api/create-report.ts` | FE-02 | 실제 이동·독립 정적 수용 / self·unit 통과·type 차단·lint 기존 2건 |
| `frontend/src/api/flow.ts` | `frontend/src/features/flow/api/reports.ts` | FE-02 | 실제 이동·독립 정적 수용 / self·unit 통과·type 차단·lint 기존 2건 |
| `frontend/src/api/fundamental-create.ts` | `frontend/src/features/fundamental/api/create-report.ts` | FE-02 | 실제 이동·독립 정적 수용 / self·unit 통과·type 차단·lint 기존 2건 |
| `frontend/src/api/fundamental.ts` | `frontend/src/features/fundamental/api/reports.ts` | FE-02 | 실제 이동·독립 정적 수용 / self·unit 통과·type 차단·lint 기존 2건 |
| `frontend/src/api/industry-create.ts` | `frontend/src/features/industry/api/create-report.ts` | FE-02 | 실제 이동·독립 정적 수용 / self·unit 통과·type 차단·lint 기존 2건 |
| `frontend/src/api/industry.ts` | `frontend/src/features/industry/api/reports.ts` | FE-02 | 실제 이동·독립 정적 수용 / self·unit 통과·type 차단·lint 기존 2건 |
| `frontend/src/api/news-create.ts` | `frontend/src/features/news/api/create-report.ts` | FE-02 | 실제 이동·독립 정적 수용 / self·unit 통과·type 차단·lint 기존 2건 |
| `frontend/src/api/news.ts` | `frontend/src/features/news/api/reports.ts` | FE-02 | 실제 이동·독립 정적 수용 / self·unit 통과·type 차단·lint 기존 2건 |
| `frontend/src/api/supervisor.ts` | `frontend/src/features/supervisor/api/analyze.ts` | FE-02 | 실제 이동·독립 정적 수용 / self·unit 통과·type 차단·lint 기존 2건 |
| `frontend/src/api/technical-create.ts` | `frontend/src/features/technical/api/create-report.ts` | FE-02 | 실제 이동·독립 정적 수용 / self·unit 통과·type 차단·lint 기존 2건 |
| `frontend/src/api/technical.ts` | `frontend/src/features/technical/api/reports.ts` | FE-02 | 실제 이동·독립 정적 수용 / self·unit 통과·type 차단·lint 기존 2건 |
| `frontend/src/app/api/auth/[action]/route.ts` | `frontend/src/app/api/auth/[action]/route.ts` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/app/api/flow/reports/route.ts` | `frontend/src/app/api/flow/reports/route.ts` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/app/api/fundamental/reports/[reportId]/html/route.ts` | `frontend/src/app/api/fundamental/reports/[reportId]/html/route.ts` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/app/api/fundamental/reports/route.ts` | `frontend/src/app/api/fundamental/reports/route.ts` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/app/api/industry/reports/[reportId]/html/route.ts` | `frontend/src/app/api/industry/reports/[reportId]/html/route.ts` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/app/api/industry/reports/route.ts` | `frontend/src/app/api/industry/reports/route.ts` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/app/api/news/reports/route.ts` | `frontend/src/app/api/news/reports/route.ts` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/app/api/private/[...path]/route.ts` | `frontend/src/app/api/private/[...path]/route.ts` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/app/api/supervisor/analyze/route.ts` | `frontend/src/app/api/supervisor/analyze/route.ts` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/app/api/technical/reports/route.ts` | `frontend/src/app/api/technical/reports/route.ts` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/app/favicon.ico` | `frontend/src/app/favicon.ico` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/app/globals.css` | `frontend/src/app/globals.css` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/app/layout.tsx` | `frontend/src/app/layout.tsx` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/app/observability/[traceId]/.gitkeep` | `frontend/src/app/observability/[traceId]/.gitkeep` | fixed-boundary | 최종 승인 불필요 marker 제거 / retain disposition |
| `frontend/src/app/onboarding/.gitkeep` | `frontend/src/app/onboarding/.gitkeep` | fixed-boundary | 최종 승인 불필요 marker 제거 / retain disposition |
| `frontend/src/app/page.tsx` | `frontend/src/app/page.tsx` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/app/reports/flow/[reportId]/.gitkeep` | `frontend/src/app/reports/flow/[reportId]/.gitkeep` | fixed-boundary | 최종 승인 불필요 marker 제거 / retain disposition |
| `frontend/src/app/reports/flow/[reportId]/page.tsx` | `frontend/src/app/reports/flow/[reportId]/page.tsx` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/app/reports/fundamental/[reportId]/.gitkeep` | `frontend/src/app/reports/fundamental/[reportId]/.gitkeep` | fixed-boundary | 최종 승인 불필요 marker 제거 / retain disposition |
| `frontend/src/app/reports/fundamental/[reportId]/page.tsx` | `frontend/src/app/reports/fundamental/[reportId]/page.tsx` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/app/reports/industry/[reportId]/.gitkeep` | `frontend/src/app/reports/industry/[reportId]/.gitkeep` | fixed-boundary | 최종 승인 불필요 marker 제거 / retain disposition |
| `frontend/src/app/reports/industry/[reportId]/page.tsx` | `frontend/src/app/reports/industry/[reportId]/page.tsx` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/app/reports/news/[reportId]/.gitkeep` | `frontend/src/app/reports/news/[reportId]/.gitkeep` | fixed-boundary | 최종 승인 불필요 marker 제거 / retain disposition |
| `frontend/src/app/reports/news/[reportId]/page.tsx` | `frontend/src/app/reports/news/[reportId]/page.tsx` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/app/reports/technical/[reportId]/page.tsx` | `frontend/src/app/reports/technical/[reportId]/page.tsx` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/app/reports/technical/demo/page.tsx` | `frontend/src/app/reports/technical/demo/page.tsx` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/app/research/page.tsx` | `frontend/src/app/research/page.tsx` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/app/unavailable/page.tsx` | `frontend/src/app/unavailable/page.tsx` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/components/common/.gitkeep` | `frontend/src/shared/ui/.gitkeep` | FE-01 | 최종 승인 marker 제거 / 이동 누락 아님 |
| `frontend/src/components/flow/.gitkeep` | `frontend/src/features/flow/components/.gitkeep` | FE-02 | 최종 승인 marker 제거 / 이동 누락 아님 |
| `frontend/src/components/fundamental/.gitkeep` | `frontend/src/features/fundamental/components/.gitkeep` | FE-02 | 최종 승인 marker 제거 / 이동 누락 아님 |
| `frontend/src/components/industry/.gitkeep` | `frontend/src/features/industry/components/.gitkeep` | FE-02 | 최종 승인 marker 제거 / 이동 누락 아님 |
| `frontend/src/components/news/.gitkeep` | `frontend/src/features/news/components/.gitkeep` | FE-02 | 최종 승인 marker 제거 / 이동 누락 아님 |
| `frontend/src/components/observability/.gitkeep` | `frontend/src/features/observability/components/.gitkeep` | FE-02 | 최종 승인 marker 제거 / 이동 누락 아님 |
| `frontend/src/components/reports/.gitkeep` | `frontend/src/features/archive/components/.gitkeep` | FE-02 | 최종 승인 marker 제거 / 이동 누락 아님 |
| `frontend/src/components/technical/.gitkeep` | `frontend/src/features/technical/components/.gitkeep` | FE-02 | 최종 승인 marker 제거 / 이동 누락 아님 |
| `frontend/src/components/ui/app-shell.tsx` | `frontend/src/shared/ui/app-shell.tsx` | FE-01 | 실제 이동·unit/type/대상 lint 통과 / 독립 정적 수용 완료 |
| `frontend/src/components/ui/section-card.tsx` | `frontend/src/shared/ui/section-card.tsx` | FE-01 | 실제 이동·unit/type/대상 lint 통과 / 독립 정적 수용 완료 |
| `frontend/src/components/ui/status-badge.tsx` | `frontend/src/shared/ui/status-badge.tsx` | FE-01 | 실제 이동·unit/type/대상 lint 통과 / 독립 정적 수용 완료 |
| `frontend/src/features/archive/components/archive-card.tsx` | `frontend/src/features/archive/components/archive-card.tsx` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/features/archive/components/archive-tabs.tsx` | `frontend/src/features/archive/components/archive-tabs.tsx` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/features/archive/components/delete-all-reports-button.tsx` | `frontend/src/features/archive/components/delete-all-reports-button.tsx` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/features/archive/components/delete-report-button.tsx` | `frontend/src/features/archive/components/delete-report-button.tsx` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/features/flow/components/flow-actions.tsx` | `frontend/src/features/flow/components/flow-actions.tsx` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/features/flow/components/flow-report-view.tsx` | `frontend/src/features/flow/components/flow-report-view.tsx` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/features/flow/components/session-controls.tsx` | `frontend/src/features/flow/components/session-controls.tsx` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/features/fundamental/components/fundamental-actions.tsx` | `frontend/src/features/fundamental/components/fundamental-actions.tsx` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/features/industry/components/industry-actions.tsx` | `frontend/src/features/industry/components/industry-actions.tsx` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/features/industry/components/industry-report-view.tsx` | `frontend/src/features/industry/components/industry-report-view.tsx` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/features/news/components/answer-text.tsx` | `frontend/src/features/news/components/answer-text.tsx` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/features/news/components/news-actions.tsx` | `frontend/src/features/news/components/news-actions.tsx` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/features/news/components/news-report-view.tsx` | `frontend/src/features/news/components/news-report-view.tsx` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/features/news/components/news-sentiment-bar.tsx` | `frontend/src/features/news/components/news-sentiment-bar.tsx` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/features/supervisor/components/composer.tsx` | `frontend/src/features/supervisor/components/composer.tsx` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/features/supervisor/components/pipeline-box.tsx` | `frontend/src/features/supervisor/components/pipeline-box.tsx` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/features/supervisor/components/research-view.tsx` | `frontend/src/features/supervisor/components/research-view.tsx` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/features/supervisor/components/result-message.tsx` | `frontend/src/features/supervisor/components/result-message.tsx` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/features/supervisor/lib/agents.ts` | `frontend/src/features/supervisor/lib/agents.ts` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/features/supervisor/mock-data/demo-analyze.ts` | `frontend/src/features/supervisor/mock-data/demo-analyze.ts` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/features/technical/components/indicator-card.tsx` | `frontend/src/features/technical/components/indicator-card.tsx` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/features/technical/components/technical-chart-panel.tsx` | `frontend/src/features/technical/components/technical-chart-panel.tsx` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/features/technical/components/technical-followups.tsx` | `frontend/src/features/technical/components/technical-followups.tsx` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/features/technical/components/technical-hero.tsx` | `frontend/src/features/technical/components/technical-hero.tsx` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/features/technical/components/technical-signal-risk-grid.tsx` | `frontend/src/features/technical/components/technical-signal-risk-grid.tsx` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/features/technical/components/technical-summary-sections.tsx` | `frontend/src/features/technical/components/technical-summary-sections.tsx` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/features/technical/components/technical-trace-drawer.tsx` | `frontend/src/features/technical/components/technical-trace-drawer.tsx` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/features/technical/components/technical-trust-cards.tsx` | `frontend/src/features/technical/components/technical-trust-cards.tsx` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/features/technical/mock-data/demo-overrides.ts` | `frontend/src/features/technical/mock-data/demo-overrides.ts` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/features/technical/mock-data/demo-report.ts` | `frontend/src/features/technical/mock-data/demo-report.ts` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/lib/archive-pagination.ts` | `frontend/src/features/archive/lib/pagination.ts` | FE-02 | 실제 이동·독립 정적 수용 / self·unit 통과·type 차단·lint 기존 2건 |
| `frontend/src/lib/bold-text.tsx` | `frontend/src/shared/ui/bold-text.tsx` | FE-01 | 실제 이동·unit/type/대상 lint 통과 / 독립 정적 수용 완료 |
| `frontend/src/lib/disabled-feature.ts` | `frontend/src/shared/server/disabled-feature.ts` | FE-03 | 실제 이동·독립 정적 수용 / self·unit 통과·type 차단·lint 기존 2건 |
| `frontend/src/lib/format.ts` | `frontend/src/shared/lib/format.ts` | FE-01 | 실제 이동·unit/type/대상 lint 통과 / 독립 정적 수용 완료 |
| `frontend/src/lib/report-links.ts` | `frontend/src/features/archive/lib/report-links.ts` | FE-02 | 실제 이동·독립 정적 수용 / self·unit 통과·type 차단·lint 기존 2건 |
| `frontend/src/lib/session-backend.ts` | `frontend/src/shared/server/session-backend.ts` | FE-03 | 실제 이동·독립 정적 수용 / self·unit 통과·type 차단·lint 기존 2건 |
| `frontend/src/lib/session-proxy.ts` | `frontend/src/shared/server/session-proxy.ts` | FE-03 | 실제 이동·독립 정적 수용 / self·unit 통과·type 차단·lint 기존 2건 |
| `frontend/src/lib/technical-chart.ts` | `frontend/src/features/technical/lib/chart.ts` | FE-02 | 실제 이동·독립 정적 수용 / self·unit 통과·type 차단·lint 기존 2건 |
| `frontend/src/lib/technical-labels.ts` | `frontend/src/features/technical/lib/labels.ts` | FE-02 | 실제 이동·독립 정적 수용 / self·unit 통과·type 차단·lint 기존 2건 |
| `frontend/src/proxy.ts` | `frontend/src/proxy.ts` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/src/types/archive.ts` | `frontend/src/shared/contracts/report.ts` | FE-01 | 실제 이동·unit/type/대상 lint 통과 / 독립 정적 수용 완료 |
| `frontend/src/types/news.ts` | `frontend/src/features/news/model/types.ts` | FE-02 | 실제 이동·독립 정적 수용 / self·unit 통과·type 차단·lint 기존 2건 |
| `frontend/src/types/supervisor.ts` | `frontend/src/features/supervisor/model/types.ts` | FE-02 | 실제 이동·독립 정적 수용 / self·unit 통과·type 차단·lint 기존 2건 |
| `frontend/src/types/technical.ts` | `frontend/src/features/technical/model/types.ts` | FE-02 | 실제 이동·독립 정적 수용 / self·unit 통과·type 차단·lint 기존 2건 |
| `frontend/src/utils/.gitkeep` | `frontend/src/shared/lib/.gitkeep` | FE-01 | 최종 승인 marker 제거 / 이동 누락 아님 |
| `frontend/tests/disabled-http.test.mjs` | `frontend/tests/integration/bff/disabled-http.test.mjs` | FE-04 | 실제 이동·독립 정적 수용 / self·unit 통과·type 차단·lint 기존 2건 |
| `frontend/tests/disabled-routes.test.mjs` | `frontend/tests/unit/bff/disabled-routes.test.mjs` | FE-04 | 실제 이동·독립 정적 수용 / self·unit 통과·type 차단·lint 기존 2건 |
| `frontend/tests/helpers/safe-http.mjs` | `frontend/tests/helpers/safe-http.mjs` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `frontend/tests/ports-http.test.mjs` | `frontend/tests/integration/bff/ports-http.test.mjs` | FE-04 | 실제 이동·독립 정적 수용 / self·unit 통과·type 차단·lint 기존 2건 |
| `frontend/tests/ports.test.mjs` | `frontend/tests/unit/config/ports.test.mjs` | FE-04 | 실제 이동·독립 정적 수용 / self·unit 통과·type 차단·lint 기존 2건 |
| `frontend/tests/safe-checks.test.mjs` | `frontend/tests/tooling/safe-checks.test.mjs` | FE-04 | 실제 이동·독립 정적 수용 / self·unit 통과·type 차단·lint 기존 2건 |
| `frontend/tests/session-http.test.mjs` | `frontend/tests/integration/bff/session-http.test.mjs` | FE-04 | 실제 이동·독립 정적 수용 / self·unit 통과·type 차단·lint 기존 2건 |
| `frontend/tests/session-proxy.test.mjs` | `frontend/tests/unit/bff/session-proxy.test.mjs` | FE-04 | 실제 이동·독립 정적 수용 / self·unit 통과·type 차단·lint 기존 2건 |
| `frontend/tsconfig.json` | `frontend/tsconfig.json` | fixed-boundary | 계획상 유지 / 설계 예외 |
| `restore_industry.ps1` | `restore_industry.ps1` | ROOT-ANCHOR | 계획상 유지 / 설계 예외 |
| `restore_industry.sh` | `restore_industry.sh` | ROOT-ANCHOR | 계획상 유지 / 설계 예외 |
| `restore_news.ps1` | `restore_news.ps1` | ROOT-ANCHOR | 계획상 유지 / 설계 예외 |
| `restore_news.sh` | `restore_news.sh` | ROOT-ANCHOR | 계획상 유지 / 설계 예외 |
| `snapshot_industry.ps1` | `snapshot_industry.ps1` | ROOT-ANCHOR | 계획상 유지 / 설계 예외 |
| `snapshot_industry.sh` | `snapshot_industry.sh` | ROOT-ANCHOR | 계획상 유지 / 설계 예외 |
| `snapshot_news.ps1` | `snapshot_news.ps1` | ROOT-ANCHOR | 계획상 유지 / 설계 예외 |
| `start_news_scheduler.ps1` | `start_news_scheduler.ps1` | ROOT-ANCHOR | 계획상 유지 / 설계 예외 |
<!-- ST001_LAYOUT_ROWS_END -->

## 구조 정리 이후 Technical type·lint 중간 수정본 (2026-11-07 21:36 UTC 당시)

구조 정리의 독립 source-only 수용 이후, 사용자가 후속 검증 순서를 승인한 별도 실행이다. 과거 type 도구 거절·lint 오류와 해당 실행 source/hash는 당시 기록으로 보존한다. 이번 변경은 `AnnotationBrief.meta`의 `unknown` 전환, Backend `_ma_series`가 생성하는 date/ma5/ma20/ma60 및 결측 null의 명시 타입, indicator-card의 pair/RSI 두 곳의 string/number 좁히기다. 숫자 0과 빈 문자열은 그대로 표시하며 기존 fallback 세 문구를 유지한다. MA 표의 기존 truthy 조건은 바꾸지 않았다. UI 렌더 회귀를 새로 실행한 결과로 확대하지 않는다.

- 변경 전 공개 checkpoint: `/tmp/verith-restructure-baseline-r38ooouu/TECHNICAL-TYPE-LINT/before-hashes.json` 및 같은 디렉터리의 공개 사본 4개.
- controller는 변경한 indicator-card의 정확한 lint 대상 1줄만 추가했다. 그 줄을 제거하면 checkpoint controller bytes와 같다. guard·copy/OS/FS/network·수명·기존 assertions는 변경하지 않았다.
- Frontend AGENTS의 프로젝트 주석을 BEGIN/END 밖으로 옮겨 원래 Next 규칙 블록 326 bytes를 HEAD와 동일하게 복원했다.

다음 각 명령은 저장소 root에서 별도 `require_escalated` 정식 요청으로 승인되어 직렬 실행했다. 공개 시작은 다음과 같다.

```zsh
/usr/bin/env -i LANG=en_US.UTF-8 TZ=UTC OPENSSL_CONF=/dev/null /opt/homebrew/Cellar/node/22.7.0/bin/node frontend/scripts/check-local-ports.mjs self-test
/usr/bin/env -i LANG=en_US.UTF-8 TZ=UTC OPENSSL_CONF=/dev/null /opt/homebrew/Cellar/node/22.7.0/bin/node frontend/scripts/check-local-ports.mjs unit
/usr/bin/env -i LANG=en_US.UTF-8 TZ=UTC OPENSSL_CONF=/dev/null /opt/homebrew/Cellar/node/22.7.0/bin/node frontend/scripts/check-local-ports.mjs type
/usr/bin/env -i LANG=en_US.UTF-8 TZ=UTC OPENSSL_CONF=/dev/null /opt/homebrew/Cellar/node/22.7.0/bin/node frontend/scripts/check-local-ports.mjs lint
```

| 이번 실제 실행 | 수집/결과 | exit·소유 자원 |
|---|---|---|
| self-test | 21/21, fail/cancelled/skipped/todo 0 | exit 0, worker 1/exit record 1/partial 0, 자기 root 제거 |
| unit | disabled 10 + session 2 + ports 3 + safety 21 = 36/36, fail/cancelled/skipped/todo 0 | exec session 32118 종료 확인, exit 0, worker 4/exit record 4/partial 0, 자기 root 제거 |
| type | standalone tsc `--noEmit --incremental false`, compiler 오류 0 | 요청 1회 승인, exec session 51598 종료 확인, exit 0, 자기 root 제거 |
| 대상 lint | 기존 대상과 변경 indicator-card 포함, 오류 0/경고 0 | exec session 28201 종료 확인, exit 0, 자기 root 제거 |

self/unit에서 예상된 synthetic deny 14건은 기존 negative 회귀이며 예상 밖 guard 위반은 0이다. type/lint는 deny 0·예상 밖 guard 0·worker/exit 각 1·partial 0이다. JS 계측 관측 범위를 native 전체 관측으로 확대하지 않는다. type 요청 직전 정식 읽기 전용 ps(PID/PPID/comm만)의 검증 Node/sandbox-exec 일치 결과가 비었고, 이전 unit은 이미 exit 0/root 제거였다. 과거 functions cell 472를 현재 실행 세션으로 취급하지 않았으며 이번 type은 승인·실행·종료가 실제 확인된 단일 요청이다. 이전 거절을 지우거나 대체 실행으로 우회하지 않았다.

standalone tsc는 기존 실제 Next core/image 선언을 사용하는 사본 검사다. generated route/typegen/full Next build 검증은 아니다. Backend source는 이번에 바꾸지 않았고 기존 self 13/unit 402를 이번 실행으로 재사용하지 않았다. UI 실제 표시·서비스/DB/AI 통합도 별도다.

### 이번 실행 source SHA-256

- `frontend/src/features/technical/model/types.ts`: `34bf5da903e156366c42be6c92f5f0b0bb3e345c8d8aa3b56bdcdc2c555eaaf6`
- `frontend/src/features/technical/components/indicator-card.tsx`: `5a0f41bbcc7ffd858c0c3380ad4fec39a777de157dd9b61809abaf136bb6a0e7`
- `frontend/scripts/check-local-ports.mjs`: `9145a1e507b7b8af9bb1041946d66f3675ff2aebc3936ff6ff20e979df75a6fc`
- `frontend/scripts/safe-checks-guard.cjs`: `6b82a520aee8a3866878aa4a7425f16110fd62eb59dd58b4d87e7d273b228575`
- `frontend/tests/tooling/safe-checks.test.mjs`: `9eb8724551782aa6585d265e7f4aa2637e84d740991d9c6f8e13fee51486f130`
- `frontend/AGENTS.md`: `0f746541c6a52ee6f9e70f4f792f9abfbede799204645dd4e8c3658e08400f31`

### build·HTTP의 현재 정확한 차단과 다음 경계

공개 설치 webpack의 FileSystemInfo `_readFileHash`가 요청받은 경로의 bytes를 읽어 snapshot hash를 계산하고, 공개 is-docker가 `/proc/self/cgroup`를 읽는 기전은 source-only로 확인했다. 과거 결과는 거부 22회/ID 10개(cgroup 4회, hash 18회/unknown ID 9개)이며 22개 파일이 아니다. AsyncQueue 경계와 기존 익명 식별 기록만으로 unknown 9개가 어떤 정확한 공개 입력이며 왜 필요한지 확정할 수 없다. knownCopy=false/HMAC 역할을 근거로 public manifest라고 허용하지 않는다. 이번 build 재실행·unknown 원본 조회·새 입력/guard/OS 예외는 0이다. CI/telemetry/cache/resolver 변경·가짜 ENOENT·dependency patch·설치로 우회하지 않는다. 정확한 producer→입력 관계와 최소 정책 판단이 확정되기 전 build는 차단이며, 안전한 build 성공 전 local-http도 미실행이다.

실제 DB·AI는 대상/격리/제한 역할/자격 사용/외부 전송/요청 수·비용 한도를 먼저 확정하는 별도 단계다. 실제 .env/credential·DB·Google/KIS/LLM/Streamlit/모델 다운로드·새 설치는 이번에 조회하거나 실행하지 않았다. 사용자 직접 Git publishing 원칙을 유지한다. 향후 PR에는 최초 미커밋 23개 중 부분 3-B 안전 도구 보완과 이번 구조 이동이 혼재하므로 순수 파일 이동만이라고 설명하지 않는다. 실제 stage/commit/push/PR/merge는 실행하지 않았다. 이번 최소 수정의 독립 source-only 재검토는 아직 요청 결과를 받기 전이며 사전 수용으로 쓰지 않는다.

### 공개 파일 manifest 시점 정리

기존 `final-public-file-manifest.json`의 857개는 v1.14 마지막 cleanup 전 사본이었다. 기존 bytes는 `/tmp/verith-restructure-baseline-r38ooouu/public-file-manifest-v1.14-before-final-cleanup.json`에 보존한다. 현재 `/tmp/verith-restructure-baseline-r38ooouu/final-public-file-manifest.json`은 이 보고와 후속 type/lint 최소 수정까지 반영한 공개 838개 집합/bytes이며, 메타데이터 sidecar에 시점과 이전 snapshot SHA를 구분한다. 누적 역사 실행 hash를 현재 bytes로 덮어쓰지 않는다.

## Technical 최종 보완·실행 결과 (2026-11-07 21:43 UTC)

중간 source의 self 21/unit 36/type/lint 통과 뒤 독립 source 검토에서 의미 경계 2건을 지적했다. 선언 타입이 저장값 보장보다 강했던 MA 타입과 잘못된 meta를 기본 숫자로 바꾸던 동작을 보완했다. 위 중간본 수치·source hash는 당시 이력이며 이 최종본으로 재사용하지 않았다.

1. recent_ma의 date는 producer의 str을 유지하고 ma5/ma20/ma60은 unknown으로 둔다. `_ma_series`는 저장된 value를 numeric 검증 없이 전달하므로 AI 원본 모델의 유효성만으로 저장 입력 전체를 보장하지 않는다. 표시 직전 typeof number를 확인하고, 기존 formatNumber 및 숫자 0/null의 빈 칸 동작을 유지한다. 비숫자를 강제로 변환하지 않고 Backend/DB/계약도 변경하지 않았다.
2. 작은 annotationText helper는 null/undefined일 때만 원래 기본값을 쓰며 string/number는 0·빈 문자열을 포함해 그대로 반환한다. boolean은 기존 React 빈 표시를 유지하고 배열/객체/그 외 잘못된 타입도 null로 안전하게 비운다. 잘못된 값으로 교차쌍/RSI 기본 숫자를 사실처럼 표시하지 않는다. 새 type assertion/문자열 강제 변환/ESLint 해제·대상 제외는 없다.

기존 `tests/tooling/safe-checks.test.mjs`에 순수 helper 회귀 1개를 추가했다. 실제 component source에서 이름이 정확한 helper 1개만 선택하고 call/new/property/element access가 없는지 확인한 뒤, 기존 TypeScript와 VM으로 그 함수만 실행한다. React/JSX/앱 import는 실행하지 않는다. fallback 3개 × 누락 2/정상값 7/잘못된 값 7 = 48개 합성 subcase를 확인한다. MA 표시 조건 3개는 source assertion이며 실제 DOM/전체 UI 렌더 회귀라고 주장하지 않는다. 새 파일·copy 예외·일반 runner·guard/FS/OS/network 권한은 추가하지 않았다. 기존 safety 21개 assertions는 보존됐다.

공개 실행 명령은 바로 위 4개와 같고 각 workload를 다시 별도 정식 `require_escalated`로 승인받아 순서대로 실행했다. 이미 승인·성공한 중간본 이후 새 source를 검증한 것이며 거절된 명령의 재시도/우회가 아니다. 새 요청 거절이나 불확정 결과는 없었다.

| 최종 source의 실제 실행 | 결과 | 종료·정리 |
|---|---|---|
| self-test | 22/22, failure/skip/cancelled/todo 0 | exit 0, 자기 root 제거 |
| unit | 10+2+3+22=37/37, failure/skip/cancelled/todo 0 | session 98296 최종 exit 0, worker 4/exit record 4/partial 0, 자기 root 제거 |
| standalone type | tsc 오류 0 | session 65015 최종 exit 0, worker/exit 1, partial 0, 자기 root 제거 |
| 대상 lint | 오류 0/경고 0 | session 93916 최종 exit 0, worker/exit 1, partial 0, 자기 root 제거 |

각 결과의 예상 밖 guard 위반은 0이다. self/unit의 예상 synthetic deny 14건과 원본 raw 접근 차단 4건은 기존 negative 검사이며 실제 비밀 조회가 아니다. type/lint는 deny 0이다. unit 종료 뒤 정식 ps에서 검증 Node/sandbox-exec 일치 0을 확인한 다음 type을 요청했고, type 종료/정리 뒤 lint를 요청했다. JS 계측과 OS canary의 관측 범위, standalone core/image tsc와 full generated-route/typegen의 차이는 유지한다. 실제 UI/실서비스 통합 검증은 아니다.

### 최종 실행 source SHA-256

- `frontend/src/features/technical/model/types.ts`: `8d7cd828b1423731d30408611ae184bc174db202859e8fba203ef8bef7678459`
- `frontend/src/features/technical/components/indicator-card.tsx`: `5daf640fbdd6c171b02c532937b681cfe12fefe0e07442d86c3e6347740dafd7`
- `frontend/scripts/check-local-ports.mjs`: `9145a1e507b7b8af9bb1041946d66f3675ff2aebc3936ff6ff20e979df75a6fc`
- `frontend/scripts/safe-checks-guard.cjs`: `6b82a520aee8a3866878aa4a7425f16110fd62eb59dd58b4d87e7d273b228575`
- `frontend/tests/tooling/safe-checks.test.mjs`: `765f74f0c9f407f50612ddfa4bc5cf824e7fcffb612c965691cc516295585a18`
- `frontend/AGENTS.md`: `0f746541c6a52ee6f9e70f4f792f9abfbede799204645dd4e8c3658e08400f31`

### build 후속의 최소 정책 제안 — 아직 미구현·미실행

cgroup probe와 unknown hash 요청은 별도 문제다. cgroup는 disabled flag만으로 constructor 호출이 없어지지 않고, catch하더라도 기존 guard 실패 기록은 보존된다. 이 한정 probe를 숨기거나 자동 성공 처리하지 않는다. unknown 9개 ID는 AsyncQueue 이전의 producer 출처가 기존 deny stack에 남지 않아 현재 자료의 추가 집계만으로 module/resolve/build snapshot을 확정할 수 없다. 기존 label/role/HMAC/knownCopy=false에서 공개성이나 읽기 허용을 추론하지 않는다.

가장 작은 다음 판단은 공개 producer의 비동기 경계 이전에 상수 분류(module-snapshot/resolve-snapshot/build-snapshot/unknown)만 전달할 정확한 API 지점이 있는지 source-only로 확인하는 것이다. 그런 지점이 입증된다면 별도 계약으로 기존 deny event에 bounded 분류 필드만 추가하는 진단 1회를 검토할 수 있다. 추가 파일 I/O·unknown 경로 조회·raw 경로/basename/Error 출력·HMAC key 출력·읽기/OS 허용·cache/resolver 변경·dependency patch는 0이어야 하고, 기존 실패 exit 및 자기 자원 정리를 유지해야 한다. 정확한 지점이나 전달 보존을 입증하지 못하면 추가 build는 요청하지 않는다. 새 정보가 없으면 반복하지 않으며 HTTP로 확대하지 않는다. 이 제안의 추가 계측·진단 실행은 아직 승인/구현/요청하지 않았다.

최종 보완본은 독립 source-only 재검토에서 수용됐다(guard 불변·controller lint 1줄·Next 블록 복원·기존 safety 21개 보존·의도된 비정상 값 빈 표시 포함). 검토자가 unit/type/lint를 독립 재실행한 것은 아니며 위 22/37/type/lint는 개발의 최종 실제 실행이다. build·HTTP와 실제 DB/AI/Google/모델 실행은 여전히 미실행이다. Git publishing·설치·배포도 실행하지 않았으며 기존 23개/데이터/CF/migration history는 보존한다.

최종 문서 정적 확인: 현재 Markdown 77개에서 경로 362개·anchor 13개 오류 0, `git diff --check` 통과. Next 규칙 326 bytes/기존 safety 21개 bytes 보존, 현재 공개 manifest 838개와 이전 857개 역사 사본 hash 일치, staged 0을 직접 확인했다. 이 정적 확인은 실제 서비스 검증이 아니다.

## v1.17 수신·최종 source 대조 (2026-11-08 KST)

정본과 부속 인벤토리의 SHA-256을 수신값과 직접 대조하고 최신 0.12절을 읽었다. v1.15와 source/target/action/batch 857행의 이동 매핑은 동일하다. 위 최종 types/card/controller/guard/safety/AGENTS 6개 SHA가 이미 정식 실행한 최종 source와 지금도 모두 같음을 직접 확인했다. v1.17 수신은 실행 후 기록이며, 실행 당시 승인된 인계와 현재 확정 계약이 일치한다는 대조다. 버전 수신만을 이유로 self/unit/type/lint를 반복하지 않았고 최종 실제 결과 22/37·type/lint exit0·guard0·각 root 제거는 그대로다.

위 21:43 UTC 절의 producer-family 진단 후보는 당시 제안 이력으로만 보존한다. **현재 v1.17에서는 그 진단을 기본 다음 단계로 권하지 않으며 추가 계측/요청/실행하지 않는다.** family만으로 exact 입력의 공개성·필수성을 정할 수 없고, 공유 AsyncQueue의 안정적 public hook도 확인되지 않았다. callback/내부 wrapping이 조사 dependency 집합을 바꿀 수 있어 이를 새 HMAC·verbose·dependency patch·CI/cache/resolver 변경으로 해결하지 않는다.

현재 가장 작은 후속 정책 선택은 공개 source와 locked dependency를 모두 별도의 소유 검증 공간 안에 두는 환경을 허용할지다. dependency copy/locked install·격리 자원·입출력·정리 경계는 조율자의 별도 범위 확정 전에는 실행하지 않는다. 원본 dependency symlink를 그대로 두는 source 사본만으로 해결된다고 주장하지 않는다. build/local-http·실제 DB/AI/Google·설치·Git publishing은 이번 수신 후에도 실행 0이다.

## 별도 네이티브 담당자의 실제 일회용 PostgreSQL 검증 (인계 기록일 2026-11-08 KST)

조율자가 전달한 **네이티브 단일 실행 담당자의 실제 결과**를 기록한다. 이 개발 채팅은 DB/Frontend 명령·Docker 시작·환경 조회를 중복 실행하지 않았다. 기존 source와 clean env, 경로·symlink/디렉터리 존재를 확인한 기존 Python `-I -S -B` 및 exact dependency 경로로 DB-only CLI를 실행했다는 보고다. interpreter/dependency/source의 SHA 검증 또는 capture를 뜻하지 않으며 전체 shell argv/환경을 추정해 재구성하지 않는다. 위 이전 절의 실제 DB 미실행은 당시 이력이다. 최초 인계에 실행 시각·전체 명령 문자열·실행 source SHA는 미제공이었고, 후속 capture 구성은 아래에 구분한다. 명령 시작/끝 시각과 interpreter/dependency/source SHA는 여전히 미수집이다. 아래 CLI 표기는 분기를 식별한 것이며 전체 실제 실행 명령을 재구성한 것이 아니다.

사용자의 명시 승인 후 공식 Docker 앱을 정식 경로로 시작했고 daemon 27.4.0과 기존 `pgvector/pgvector:pg16` arm64/linux image를 사용했다. 시작 직후 실행 container 목록은 비어 있었고 image 다운로드/새 설치는 0이었다. 기존 앱 DB·role·volume·env/credential/Google/AI/외부 API·repo 코드/Git 변경은 없었다.

| 실제 실행 분기 | 담당자 실행 결과 | 이번 자원 |
|---|---|---|
| 기존 `scripts/cf002_interactive_login.py --verify-owned-db` | exit 0. readonly preflight·동일 연결 migration·합성 session/Flow 저장·목록·상세·삭제 통과. 검증 후 users/identities/sessions/reports 집계 각각 0 | CID `ec7210fa3383e7f294e1223e0bc6d16dcb824a64a77f16a1a889b3d3466b4c2f` |
| 기존 `scripts/cf002_interactive_login.py --verify-controller` | 별개 새 PG에서 exit 0. 합성 A/B owner 격리, 동일계정/모호 binding 거부, 만료·폐기 session 거부, 반복 삭제·stock 보존·NULL owner 비노출 통과 | CID `d712b6d5bbad4f52b9b2a3df8f180beb6ad3ffd3797e047ddd73134a52f5d1ad` |

각 runner의 자기 자원 삭제 확인 이후 정확한 두 CID의 `No such object`와 해당 resource label 잔여 0을 네이티브 담당자가 별도로 확인했다. 임시 role은 자기 container와 함께 제거됐으며 Docker Desktop 자체만 켜져 있다. 원래 container/volume·운영 DB·지속 계정 접근을 변경했다는 의미가 아니다.

추가 capture의 DB image ID는 `sha256:fa3d9bb7ee77f5c1f0bfb009a9df30243c040896825f3033b09a77101bb2ca95`, RepoDigest는 `pgvector/pgvector@sha256:00ba258a66dac104fd5171074a0084462a64a1369d8513f3d0a634e2f24d15bc`다. 위 owned-db CID의 Docker 생성시각은 **2026-11-08 06:57:42.858590259 KST**, controller CID는 **06:58:05.34673788 KST**다(원 DockerCreated UTC를 +09:00 변환). 이는 명령 시작/끝 시각이 아니다.

공개 launcher capture 구성은 backend cwd, `env -i PATH=/usr/local/bin:/usr/bin:/bin LANG=en_US.UTF-8 TZ=UTC PYTHONDONTWRITEBYTECODE=1`, repo의 `backend/.venv/bin/python -I -S -B`와 exact `backend/.venv/lib/python3.12/site-packages`의 sys.path 추가, 기존 `scripts/cf002_interactive_login.py`를 각 모드로 호출하는 runpy.run_path였다. `set -o pipefail`·nonce redaction을 사용했고 새 repo runner/모듈은 추가하지 않았다. 제공된 구성을 전체 shell argv로 합성하거나 재실행하지 않는다.

이번 수용은 **실제 PostgreSQL 위 합성 service/controller 통합 검사**다. 전체 DB pytest·rollback suite·실제 Google 사용자 인증/BFF/SSR·실제 AI 통과로 확대하지 않는다. 원시 receipt JSON·cookie/token/sub/credential 값은 이 기록에 포함하지 않는다.

### 별도 Frontend 검증의 환경 차단과 실행 분리

Cloud 담당자가 비밀 없는 source snapshot 108개/hash, Node 24.22.1/npm 11.9.0 및 공식 npm registry 응답 200을 확인했으나 최소 bwrap OS 격리 probe가 `NETLINK_ROUTE socket Operation not permitted`로 실패했다. 정식 경로에서도 같은 capability 오류로 종료했으며 **npm ci/build/HTTP 실행 0**이다. 보호를 해제하거나 다른 네트워크로 우회하지 않았고 제품 코드 실패로 분류하지 않는다.

당시 별도 Node container의 source-only 대안은 네이티브 담당자가 준비 중이었으며 공식 image 존재 확인과 신규 다운로드 필요 여부를 조율했다. 아래 후속 절에서 별도 Docker 검증이 완료됐다. 이 개발 채팅은 해당 runtime의 단일 담당자가 아니므로 중복 실행·설치·앱 시작을 하지 않는다. Mac webpack 계측·추가 진단은 계속 중단 상태다. 향후 별도 환경의 성공도 기존 3-B harness 전체 수용과 분리한다. Git publishing·배포는 실행하지 않았다.

## 별도 clean Docker Frontend build·HTTP 성공 (인계 기록일 2026-11-08 KST)

조율자가 전달한 **네이티브 단일 실행 담당자의 실제 결과**를 기록한다. 조율자 및 독립 검토자가 HTTP 로그에서 TAP 집계를 읽어 확인했다고 전달했다. 프로세스 exit와 source 불변은 그 로그 단독 증거가 아니라 실행 담당자의 capture/보고다. 이 개발 채팅은 source/runtime·설치·webpack 계측·Git 작업을 다시 실행하지 않았다. 앞선 cloud bwrap capability 차단·npm ci/build/HTTP 0과 아래 Docker 실행은 서로 다른 환경/시점이다. 이전 실패는 이력으로 보존한다.

| 환경·실행 | 담당자 확인 결과 |
|---|---|
| 입력 | 비밀 없는 현재 source snapshot 108개. container 안/source 및 원 repo/source 108개 SHA 모두 실행 전후 불변 |
| 공식 image | `node@sha256:01d566e8d94d8c619591d78652babfccd3c6992a3dffa9ed5ab39e11cf6c70e9`, Linux arm64, Node 24.22.2/npm 11.19.1 |
| 의존성 설치 | `npm ci --ignore-scripts` 407개, lifecycle script 실행 0. 원 repo의 dependency 설치/수정과 구분 |
| 정식 build | `npm run build -- --webpack`, Next 16.2.10 compile·generated types 포함 TypeScript·static 11/11·build traces 완료, exit 0 |
| 합성 HTTP | 기존 session-http/ports-http/disabled-http test body 3개 bytes 보존. 임시 Docker lifecycle helper만 사용해 실제 Next+fake Backend를 직렬 검증. tests 3/pass 3/fail 0/cancelled 0/skipped 0/todo 0/exit 0 |
| 정리 | outer finally에서 자기 test container rm exit 0 및 absence 확인. 원 repo 제품 source/Git 수정 0. 공식 Node image cache와 Docker Desktop 자체는 남아 있음 |

개인 home/.env/.git/DB/socket/원 repo mount는 없고 호스트 공개 port는 0이었다. 담당자는 build/HTTP 동안 network connection 0을 확인했다고 전달했다. npm 설치 단계와 container 내부 실제 loopback HTTP 검사를 이 격리 경계와 구분한다. read-only root·비root·cap-drop/no-new-privileges 등 보호를 유지했다.

최초 자기 `/work` tmpfs가 noexec여서 compile 전에 exit 126이었다. 사용자 승인된 실행 공간의 **자기 /work만 exec로 명시한 새 container**에서 정식 build/HTTP가 성공했고 첫 container도 제거됐다. 제품 코드 실패·Mac 보안 설정 변경으로 기록하지 않는다. 최초 인계에는 전체 실행 시각·CID·HTTP shell 명령·각 108개 source SHA 목록이 미제공이었으며, 후속에 제공된 capture만 아래에 추가한다. 명령 시작/끝 시각과 108개 SHA 전체 목록은 이번 인계에 미제공이다(108개는 snapshot-manifest에 기록됐다고 전달됨). 임시 adapter 자체 SHA는 미수집이며 이를 추정하지 않는다.

HTTP 3개가 검사한 범위는 legacy proxy·SSR upstream 0, canonical 3200→8200 callback/Host/Origin 거절, duplicate cookies·archive pagination·delete return이다. 보고된 로그 위치는 `/var/folders/d7/v1s6ddq12y9fftsqrvrgcz140000gn/T/verith-docker-fe-kstr7400/docker-http-test.log`이며 이 개발 채팅은 그 파일을 새로 읽지 않았다. 맨끝 Docker config `/dev/null` warning은 테스트 성공/실패 결과와 별도이며 비밀 내용을 읽은 로그라는 뜻이 아니다.

이번 결과는 **별도 clean Docker build 및 실제 Next+fake Backend HTTP 성공**이다. Mac 3-B harness의 자체 보호정책·unknown hash 허용·전체 수용을 뜻하지 않는다. Mac 계측·추가 build 요청은 중단 상태다. 실제 Google 로그인·외부 AI·전체 DB pytest/rollback suite·실제 Backend DB와 Frontend의 통합은 이 수용 범위 밖이다. 앞선 실제 PG 검사 2개 또한 별도 네이티브 담당자의 합성 service/controller 실행이며 이 개발 채팅의 재실행이 아니다. 운영 DB/기존 자료·자격/실외부 API·Git publishing·배포를 이번 기록 작업에서 접근/변경하지 않았다.

### Docker Frontend 후속 capture와 증거 출처

- 성공 CID `3589bc7413ef5bc2a8f550dcc98ec6555b00d6bed608c0cb07190b923397a2e1`, owner label `verith.check.owner=kstr7400-exec`. Docker 생성은 **2026-11-08 07:06:27.057912626 KST**(원 DockerCreated UTC 변환)이며 명령 시작시각이 아니다. 실행 직전 capture의 `22:10:24Z`(07:10:24 KST)는 running=true/networks={}/binds=null/ports={}를 보여 준다. `network connection 0`은 설치 시 네트워크까지 0이라는 뜻이 아니라 build/HTTP 시점의 Docker network 연결 상태다.
- 정리는 rm exit 0 및 정확한 성공 CID의 ps-a empty/absence True다. 첫 noexec CID `802d01a462f1630e569943313f53cd3bc1b1a0ba65c48c2b91ebf05d35315bd5`도 제거 확인됐다. 다른 작업을 포함한 전역 임시 container 0으로 확대하지 않는다.
- snapshot ZIP SHA-256 `fe3c26d11aa0882ff0c6eed6ff27a3f0b04d603ef41a738d6067ea6a63764931`, 내부 snapshot-manifest.json 108개. 임시 adapter SHA는 capture하지 않았다.

다음은 container 내부의 **당시 capture 명령**이며 재실행 지시나 전체 호스트 launcher가 아니다.

```text
timeout 360 npm ci --ignore-scripts --no-audit --no-fund --registry=https://registry.npmjs.org
timeout 420 npm run build -- --webpack
timeout 450 node --test --test-concurrency=1 docker-tests/integration/bff/disabled-http.test.mjs docker-tests/integration/bff/ports-http.test.mjs docker-tests/integration/bff/session-http.test.mjs
```

env-i 기반 HOME=/tmp/home·TMPDIR=/tmp·OPENSSL_CONF=/dev/null·NEXT_TELEMETRY_DISABLED=1, 빈 npmrc와 임시 cache를 사용했다. HTTP outer timeout은 480초이며 finally cleanup을 적용했다. build 별도 log 파일은 없고 실행 tool chunk `6854d1`/`baebf5`에 시작/완료 exit 0이 있다는 담당자 capture다.

원 HTTP test body와 동일하다고 전달된 SHA-256은 session `5efa2d3b2ff9c6b8e5ee27b866695156af3967c57da107ebb173fa56589343f0`, ports `703741869f2082d4040be6ec4e6eaf04a2ba6a8d90f2f782db02614dbf6b3047`, disabled `68ca3b45b1c65c4d70fc8c8c77cb2fecfd9ba3df416251e16c2cd23e5f56e9d0`이다. 이 개발 채팅이 해당 테스트를 재실행하거나 SHA를 새로 capture했다는 뜻이 아니다.

독립 검토자는 위 exact HTTP log만 추가로 읽어 SHA-256 `e63db60462ad1bb4496476c82dbfcc885d44953f9a1d88e09b3762cc4104a81e` 및 TAP tests 3/pass 3/fail 0/cancelled 0/skipped 0/todo 0을 확인했다. 세 이름은 legacy proxy·SSR upstream 방지 / 3200 auth BFF fixed 8200·callback·alias/Host/Origin 거부 / duplicate cookies·archive pages·deletion return 유지다. **로그 파일 자체에 프로세스 exit 0은 명시되지 않고 source 무변경도 이 로그만으로 증명되지 않는다.** exit 0·source 108개 불변·container 정리는 네이티브 실행 담당자의 별도 capture/보고로 출처를 분리한다. 이 개발 채팅은 로그·container·실환경을 추가 조회하거나 검사를 재현하지 않았다.

## 사용자 review·직접 stage/commit/push/Draft PR 초안

현재 read-only 확인: branch `chore/safe-backend-frontend-checks`, HEAD `7df12403848e480f223767232540d4c2c055ba5e`, fetch/push **전체 URL 각각 단일** `https://github.com/bellra-jin/verith.git`, staged 0. 변경 1,200경로는 v1.17 인벤토리 source/target+이 진행 기록 안이며 범위 밖 0이다. 원래 23개 중 5개는 baseline bytes와 같고 18개는 구조·문서·검사 보완이 겹친다. 부분 3-B 도구까지 포함한 혼합 변경을 사용자 review 후 하나의 Draft PR로 제안하며 rename-only라고 설명하지 않는다. local develop/origin/develop은 캐시 ref이며 원격 최신성을 새로 조회한 것은 아니다.

정확한 공개 stage 목록은 `/tmp/verith-restructure-baseline-r38ooouu/review-paths.txt`(1,200행), literal NUL pathspec은 같은 디렉터리 `review-pathspecs.nul`이다. pathspec SHA-256은 `884cb5a6ffa678d773076d0007d50c48affa024efa2388a701df7bab3e033d0a`, 경로 집합은 UTF-8 정렬+각 NUL 종단 기준 SHA-256 `e8e78b424a63d1793e3a68343a97f9d7ef5e04989fb384639d9b51d084344b32`다. 존재하는 변경 파일 중 ignored는 0이다. no-index ignore 검사에 걸린 5개는 이미 tracked였던 옛 News goldset의 승인된 삭제 경로이며 현재 파일이 없고, 새 target 5개는 exact negation으로 추적 가능하다. force-add하지 않는다.

아래는 **사용자가 직접 실행할 초안**이며 개발/검토 채팅이 실행하지 않았다. 먼저 전체 경로 목록과 diff(신규 파일 포함)를 읽어 기밀·무관 변경이 섞이지 않았는지 확인한다. 경로 일치는 내용의 기밀 부재를 자동 보증하지 않는다. stage 뒤에도 `git diff --cached`로 신규 source까지 검토하고, 승인하지 않은 변경이 있으면 다음 블록으로 가지 않는다. 실행 전 상태가 달라지거나 임시 파일이 없으면 중단하고 현재 목록/bytes를 다시 검토한다. 기존 과거 단계의 stage 명령이나 `git add .`/`add -A`를 재사용하지 않는다.

### 1. 사전 상태·snapshot 확인 후 exact stage

```zsh
(
set -e
cd /Users/parkjinhee/AI/verith_refactor/verith
git status --short --untracked-files=all
git --no-pager diff --no-ext-diff --stat
/usr/bin/env -i LANG=en_US.UTF-8 /usr/bin/python3 -I -S - <<'PY_STAGE'
from pathlib import Path
import subprocess, hashlib, json
run = lambda *args: subprocess.check_output(['git', *args])
assert run('branch','--show-current').decode().strip() == 'chore/safe-backend-frontend-checks'
assert run('rev-parse','HEAD').decode().strip() == '7df12403848e480f223767232540d4c2c055ba5e'
for args in [('remote','get-url','--all','origin'), ('remote','get-url','--push','--all','origin')]:
    assert run(*args).decode().strip() == 'https://github.com/bellra-jin/verith.git'
assert not run('diff','--cached','--name-only')
records = [x for x in run('status','--porcelain=v1','-z','--untracked-files=all','--no-renames').split(b'\0') if x]
paths = sorted({x[3:].decode() for x in records})
assert len(paths) == len(records) == 1200
assert hashlib.sha256(b'\0'.join(p.encode() for p in paths)+b'\0').hexdigest() == 'e8e78b424a63d1793e3a68343a97f9d7ef5e04989fb384639d9b51d084344b32'
root = Path('/tmp/verith-restructure-baseline-r38ooouu')
spec = (root/'review-pathspecs.nul').read_bytes()
assert hashlib.sha256(spec).hexdigest() == '884cb5a6ffa678d773076d0007d50c48affa024efa2388a701df7bab3e033d0a'
assert spec == b'\0'.join((':(top,literal)'+p).encode() for p in paths)+b'\0'
manifest = json.loads((root/'final-public-file-manifest.json').read_text())
assert len(manifest) == 838
assert all(not Path(p).is_symlink() and hashlib.sha256(Path(p).read_bytes()).hexdigest() == h for p,h in manifest.items())
print('Exact 1200 paths / current 838 public files match; review before committing.')
PY_STAGE
git add --pathspec-from-file=/tmp/verith-restructure-baseline-r38ooouu/review-pathspecs.nul --pathspec-file-nul
git --no-pager diff --cached --stat
git diff --cached --check
)
```

### 2. staged diff 확인 후 commit

```zsh
(
set -e
cd /Users/parkjinhee/AI/verith_refactor/verith
[[ "$(git branch --show-current)" == chore/safe-backend-frontend-checks ]]
[[ "$(git rev-parse HEAD)" == 7df12403848e480f223767232540d4c2c055ba5e ]]
git diff --quiet
[[ -z "$(git ls-files --others --exclude-standard)" ]]
/usr/bin/env -i LANG=en_US.UTF-8 /usr/bin/python3 -I -S - <<'PY_COMMIT'
import subprocess, hashlib
paths = sorted(set(subprocess.check_output(['git','diff','--cached','--name-only','--no-renames','-z']).split(b'\0'))-{b''})
assert len(paths) == 1200
assert hashlib.sha256(b'\0'.join(paths)+b'\0').hexdigest() == 'e8e78b424a63d1793e3a68343a97f9d7ef5e04989fb384639d9b51d084344b32'
PY_COMMIT
git diff --cached --check
git commit -m "refactor: organize features and strengthen safe validation"
)
```

### 3. 새 commit review 후 push

```zsh
(
set -e
cd /Users/parkjinhee/AI/verith_refactor/verith
[[ "$(git branch --show-current)" == chore/safe-backend-frontend-checks ]]
[[ "$(git rev-parse HEAD^)" == 7df12403848e480f223767232540d4c2c055ba5e ]]
[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]]
[[ "$(git remote get-url --all origin)" == https://github.com/bellra-jin/verith.git ]]
[[ "$(git remote get-url --push --all origin)" == https://github.com/bellra-jin/verith.git ]]
git --no-pager show --stat --oneline HEAD
git push origin HEAD:refs/heads/chore/safe-backend-frontend-checks
)
```

### 4. 아래 본문 review 후 Draft PR

동일 head의 open PR이 이미 있으면 중복 생성하지 않는다. base는 GitHub의 develop이며 이 문서가 원격 develop의 최신 SHA/충돌 없음을 보증하지 않는다. Ready/merge는 사용자가 별도로 판단한다.

```zsh
(
set -e
cd /Users/parkjinhee/AI/verith_refactor/verith
[[ "$(git branch --show-current)" == chore/safe-backend-frontend-checks ]]
[[ "$(git rev-parse HEAD^)" == 7df12403848e480f223767232540d4c2c055ba5e ]]
[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]]
[[ "$(git remote get-url --all origin)" == https://github.com/bellra-jin/verith.git ]]
[[ "$(git remote get-url --push --all origin)" == https://github.com/bellra-jin/verith.git ]]
[[ "$(/usr/bin/shasum -a 256 /tmp/verith-restructure-baseline-r38ooouu/review-pr-body.md | /usr/bin/awk '{print $1}')" == b42ea344ef3676746f665cfa6d80a74c7907ca51b30addb6ce38727bcddadb74 ]]
gh pr create --repo https://github.com/bellra-jin/verith --base develop --head chore/safe-backend-frontend-checks --draft --title "refactor: 기능별 구조 정리와 안전 검사 보완" --body-file /tmp/verith-restructure-baseline-r38ooouu/review-pr-body.md
)
```

### Draft PR 본문

<!-- ST001_LAYOUT_PR_BODY_BEGIN -->
기능별 구현과 내부 책임을 모으도록 Backend·AI·Frontend를 재배치하고 canonical import로 통합했습니다. 기존 미커밋 23개에 있던 부분 3-B 안전 검사 입구와 문서 보완, 후속 Technical 타입·표시 경계 수정도 함께 포함합니다. rename-only 변경이 아닙니다.

- 이동 계획 536행 처리: 현재 target 525개 + 승인된 marker 제거 11개. 별도 retain marker 9개 제거, 운영 marker 3개 보존, 불필요한 빈 폴더 10개 정리. old export shim 61개 제거 후 canonical 소비자·mock·CLI·자원 참조를 갱신했습니다.
- Flow 3개는 AI 루트 .env를 명시하고 process env(빈 문자열 포함) 우선·override=False를 유지합니다. 실제 자격 값이나 기존 설정 파일은 옮기지 않았습니다. Technical은 저장 MA 값을 unknown으로 다루고 잘못된 meta를 숫자 사실처럼 표시하지 않도록 보완했습니다.

검증: 개발의 보호 Backend self 13/unit 402, Frontend 최종 self 22/unit 37·standalone core/image tsc·대상 lint 통과. 별도 네이티브 담당자는 실제 일회용 PG 합성 service/controller 검사 2개 및 clean Docker의 정식 Next build(생성 타입·static 11/11·traces)와 실제 Next+fake Backend HTTP 3개를 통과했습니다. 실행 주체·source/hash·이전 실패·자기 container 정리 근거는 docs/work/ST-001-layout-progress.md에 구분했습니다.

한계: Mac 3-B harness 자체의 build/HTTP 보호정책 수용은 미완료입니다. 별도 Docker 성공을 그 수용으로 확대하지 않습니다. 전체 DB pytest/rollback suite·실제 Google/외부 AI·전체 앱 통합은 미검증입니다. 기존 데이터·migration history·CF 계약은 보존했으며 임시 test container는 제거됐습니다. Docker Desktop과 공식 image cache는 남아 있습니다.
<!-- ST001_LAYOUT_PR_BODY_END -->

## 별도 담당자의 실제 OpenAI 1회 요청 — 인증 거부 (인계 기록일 2026-11-08 KST)

사용자가 합성 수급 데이터와 삼성전자/005930만 공식 OpenAI에 보내는 gpt-5.4-mini 단 1회·US$0.01 이하·retry 0·기존 OpenAI 키 사용·KIS/DB/cache 0 조건을 명시 승인했고, **별도 검증자가 실행한 결과를 조율자가 전달했다.** 이 개발 채팅은 요청·키 조회·설치·검사를 재실행하지 않고 기록만 반영한다.

실제 `https://api.openai.com/v1/chat/completions` 요청 1회는 **HTTP 401 인증 거부**로 종료됐으며 재시도는 0이다. 인증 실패의 세부 원인은 미확정이다. 키/오류 본문 출력은 0이다. ai/.env를 전체 dotenv 설정으로 로드하지는 않았지만 줄순회 과정에서 다른 줄도 메모리를 통과했다. 오직 지정 OPENAI_API_KEY 필드만 parse/사용하고 기타값 출력은 0이었다고 전달받았다. 다른 secret bytes를 전혀 읽지 않았다는 뜻으로 확대하지 않는다. 지정 필드는 단순 literal·정확히 1개·비어 있지 않음을 사전 확인했고 값/prefix/길이를 기록하지 않았다. 첫 사전검사의 key 부재는 당시 프로세스 env에 관한 결과이지 해당 파일의 key 부재를 뜻하지 않는다. 이 기록을 위해 파일·프로세스 환경·키·오류 본문을 추가 조회하지 않았다.

| 사전 한도·요청 설정 | 전달된 실행 조건/결과 |
|---|---|
| 입력·출력 한도 | 입력 525 UTF-8 bytes를 기준으로 framing 여유 3,000을 둔 보수 입력 상한 3,525 tokens, max_completion_tokens 1,000, n=1 |
| 공개 요청 옵션 | reasoning_effort=none, service_tier=default, store=false, timeout 30초, 도구 0 |
| 사전 최대 계산 | 검증자가 확인한 당시 공식 표준 단가 input US$0.75/output US$4.50 per million 기준 `(3525×0.75 + 1000×4.50)/1000000 = US$0.00714375`(세금·환전 제외). 승인된 US$0.01 이하 한도 계산 |
| 응답·실제 비용 | HTTP 401. usage/finish/실제 생성 token·실제 청구액은 미제공이며 **과금 0으로 확정하지 않는다** |

실행 구성은 `backend/.venv/bin/python -I -S -B -c`였으며 이번 실제 resolved 경로·Python 버전은 별도 capture하지 않았다. 검증자 보고상 stdlib urllib.request와 `ProxyHandler({})`로 환경 proxy를 사용하지 않고, `ssl.create_default_context(cafile='/etc/ssl/cert.pem')`의 host/certificate 검증을 유지하며 redirect를 거부했다. `opener.open(req,timeout=30)` 단일 호출 지점·loop 0·retry 0이었고 HTTP 401 뒤에는 위 선택 source hash 검사만 했다. 패킷 추적은 없으므로 이 구성 보고를 별도의 packet 관측으로 확대하지 않는다. 이 개발 채팅이 코드·CA·프로세스·네트워크를 추가 조회했다는 의미도 아니다.

합성 수치의 외국인 5일 합 200,000·기관 합 50,000·외국인 강도 0.20은 별도 검증자의 stdlib 검산을 통과했다. 기존 Backend Python에 pandas/jinja2가 없어 원래 Flow compute/gate/render는 실행하지 않았다. 따라서 실제 AI 생성 성공·Flow 부분 통합 성공·실제 외부 데이터 수집 성공으로 쓰지 않는다.

검증자는 선택 source `ai/tests/flow/fixtures.py`, `ai/src/agents/flow/config.py`, `ai/src/agents/flow/infrastructure/llm/explain.py`의 전후 SHA를 실행 메모리에서 비교해 selected_source_hashes_unchanged:true, 생성 파일 0, KIS/DB/기존 cache 접근 0을 보고했다. 개별 hash 문자열은 출력/수집하지 않았으므로 이 기록에도 적거나 현재 파일에서 소급 수집하지 않는다. 생성물은 미검증이며 현재 실제 AI 검증의 차단 지점은 위 1회 인증 거부다. **이번 1회 승인은 소진됐고 인증 문제 해결 및 새로운 승인 전에는 재호출하지 않는다.** 별도 Docker build/fake HTTP·실제 PG 합성 검사 성공과 이 실패를 구분한다. 기존 PR 본문의 실제 AI 미검증 한계는 여전히 유효하여 본문 파일은 변경하지 않았다. 원 repo source·설치·실환경·Git publishing 변경은 이 기록 작업에서 실행하지 않았다.
