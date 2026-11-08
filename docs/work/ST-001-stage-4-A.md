# ST-001 4-A · Flow 구현의 첫 실제 이동

확인 시각: 2026-11-08 03:49 KST (+09:00). 실제 이동과 보호 회귀를 수행했다. 최초 기록 당시 대기였던 독립 최종 검토는 이후 source-only로 완료됐으며, 이번 4-A 이동을 막는 결함은 발견되지 않았다. **전체 Backend·AI·Frontend 폴더 재구성 완료가 아니다.** 이번 첫 단위는 Backend 4개와 AI 2개의 구현 이동이다. 나머지 전체 기능의 인벤토리·후속 매핑을 이어 적용한다.

## 기준과 보존

- 외부 정본 ST-001 v1.8, SHA-256 `3113a2aa6b941131d99dda425fd4a02955a70fd476d209519b6943943eee5677`의 0절을 적용했다. 개인 정본 경로·대화·비밀값은 복사하지 않는다.
- branch `chore/safe-backend-frontend-checks`, HEAD/base `7df12403848e480f223767232540d4c2c055ba5e`. 새 branch/fetch/checkout·git add/commit/push/PR/merge를 실행하지 않았다.
- 첫 수정 전 기존 미커밋 공개 작업 23개와 원본 6개를 자기 임시 보존본으로 확보했다. 기존 23개 중 20개는 SHA-256과 bytes가 그대로다. 나머지 안전 입구 3개는 아래 relocation 부분만 변경했다. 기존 manifest/3-B 기록·Frontend guard/HMAC·HTTP 기대값은 그대로다.
- 총 작업 트리 변경은 기존 23개와 이번 허용 20개가 3개 겹친 **40개 경로**다. 이를 새 변경 40개 또는 정리할 잡파일로 해석하지 않는다. staged 0이며 변경을 보존한다.

## 실제 before/after

| 기존 경로: 호환 import만 유지 | 실제 정의의 새 위치 |
|---|---|
| `backend/src/api/schemas/flow_payload.py` | `backend/src/modules/flow/domain/payload.py` |
| `backend/src/api/schemas/flow_execution.py` | `backend/src/modules/flow/domain/execution.py` |
| `backend/src/api/schemas/flow_report.py` | `backend/src/modules/flow/api/schemas.py` |
| `backend/src/api/routes/flow_reports.py` | `backend/src/modules/flow/api/router.py` |
| `ai/src/agents/flow/schemas.py` | `ai/src/agents/flow/domain/models.py` |
| `ai/src/agents/flow/export/to_json.py` | `ai/src/agents/flow/api/payload.py` |

구 경로에는 함수·클래스 구현이 없고 명시적 재노출만 있다. Backend `src/modules/flow/domain`은 payload/실행 계약, `api`는 DTO/router다. AI는 기존 agent 기능 루트를 유지하며 `domain/models.py`와 `api/payload.py`로 나눴다. 불필요한 initializer·빈 계층은 만들지 않았다.

Backend main/service/common reports의 계약·router import만 새 위치로 연결했다. `src.api.main:app`·AI `src.main:app` 및 기존 HTTP·owner/CSRF·DB/설정·자산 경계는 유지했다. service/repository 구현은 이번에 이동하지 않았다. 첫 6개에는 resource 경로 계산/파일 읽기 코드가 없다.

## 보호 입구의 국소 변경

- [controller](../../backend/scripts/check_safe.py): 새 Backend 4개·AI 2개를 정확한 신규 사본 경로에 추가했다. AI 원본 shim 2개와 새 구현 2개의 hash를 구분하고, index에 없는 신규 입력은 exact NEW 집합으로만 받는다.
- [bootstrap](../../backend/scripts/safe_checks_bootstrap.py): AI namespace 5개와 shim/구현 module 4개의 정확한 자기 사본 origin을 확인한다. 다른 위치나 동명 source를 허용하지 않는다.
- [합성 안전 회귀](../../backend/tests/safe_checks/test_entry.py): 정확한 신규 입력·필수 입력 누락·인접 AI 경로 거부·새 origin 오염을 추가 검증한다.
- sandbox profile·파일/네트워크 권한·native 예외·HMAC·resolver/cache·startup 환경은 확대하지 않았다. OS 적용·native 양성/음성 canary와 기존 guard가 먼저 설치된 자기 임시 사본에서만 Python 검사를 실행했다.

## 직접 실행 결과

공통 cwd는 저장소 root다. 아래 workload 각각에 공식 `require_escalated`를 요청하고 승인된 실행을 사용했다. 기존 .env/credentials/ignored Compose·DB·Google·외부 AI·모델·앱 서버·새 설치는 사용하지 않았다.

```sh
/usr/bin/env -i LANG=en_US.UTF-8 TZ=UTC /Users/parkjinhee/AI/verith_refactor/verith/backend/.venv/bin/python -I -S backend/scripts/check_safe.py self-test
/usr/bin/env -i LANG=en_US.UTF-8 TZ=UTC /Users/parkjinhee/AI/verith_refactor/verith/backend/.venv/bin/python -I -S backend/scripts/check_safe.py unit
```

| 시점/검사 | 실제 결과 |
|---|---|
| 이동 전 기존 self-test | 9개 실행/9개 통과, exit 0, 자기 root 제거 |
| 이동 전 기존 고정 6개 unit | collected 244/passed 244, guard 위반 0, exit 0, 자기 root 제거 |
| 이동 전 공개 계약 baseline 추가 | 기존 244 + baseline 1 = 245개 통과, guard 위반 0, exit 0 |
| 이동 후 self-test | 10개 실행/10개 통과, exit 0, 자기 root 제거 |
| 이동 후 첫 unit | collected 251, passed 250/failed 1, guard 위반 0, worker 1/controller 78, 자기 root 제거 |
| 실패 원인과 수정 | 새 route 검사에서 app.routes의 leaf APIRoute를 가정했다. 설치 FastAPI는 `_IncludedRouter(original_router=...)` lazy wrapper를 사용한다. 설치 source 확인 후 실제 등록 router 동일 객체 1회와 공개 path/method를 검사하도록 새 회귀만 수정했다. 제품 route/기존 기대값은 수정하지 않았다. |
| 수정 후 unit | collected 251/passed 251, guard 위반 0, exit 0, 자기 root 제거 |
| 정확한 canonical origin assertion 보강 후 최종 unit | collected 251/passed 251, guard 위반 0, exit 0, 자기 root 제거 |

251개는 기존 고정 6파일의 **244개 전부 + 이동 회귀 7개**다. 새 회귀는 old/new 공개 객체 동일성·canonical module/origin 6사례와 이동 전후 전체 Backend OpenAPI/공개 모델 JSON schema/실제 순수 producer의 고정 합성 payload 비교 1사례다. 단순 alias 비교만으로 회귀를 대체하지 않았다. 기존 Flow 테스트 함수/데코레이터/기대값 AST도 변경하지 않았다.

이동 전 보호 worker가 기록한 비교 기준:

| 자료 | SHA-256 (정렬된 JSON, ensure_ascii=False) |
|---|---|
| 전체 Backend OpenAPI | `dbec0f00b8c57c5a906639c7763e83e38f7c847e1ee5a4116342450a2195bc24` |
| 공개 Flow 모델 JSON schema 묶음 | `91065e01c38b32b5a39a8746b8dc8ca216f471580eb2c59f0d5262065e20772b` |
| 고정 합성 payload | `a60b8618350693c42cebdf75b72d22163b2145f77857b7285dc614262d72af5a` |

payload 비교는 기존 실제 순수 exporter/fixture를 호출하고 UUID만 합성 고정했다. 기존 graph·데이터 수집·LLM·DB는 실행하지 않았다. 이동 후 세 해시가 같으며 JSON 의미나 schema 정규화 변경은 없었다.

## 정적 검증과 변경 파일

이번 허용 20개는 위 before/after 12개, main/service/common reports 3개, unit test 1개, 안전 입구 3개, 이 보고서 1개다. 전체 40개 집합 중 기존 20개 보호 파일은 bytes 동일이며 이번 허용 범위 밖 새 차이는 없다. Python AST 구문·import 제외 실행 본문/validator/decorator/상수 보존·AI 구현 2개 bytes·main/service/common reports import-only·기존 테스트 본문 보존·로컬 링크 4개·이동 경로 쌍 6개 및 `git diff --check`를 직접 확인했다. 허용 코드 19개 Python 구문·총 변경 40개/이번 허용 20개/기존 20개 bytes 보존·staged 0/예상 밖 새 변경 0·정본 hash가 모두 통과했다. 보호 controller의 수정 함수는 selected_sources뿐, bootstrap은 valid_flow_origins뿐이며 나머지 profile/audit/보호 함수 AST는 보존본과 같다.

| 코드 경로 | 최종 SHA-256 |
|---|---|
| `backend/src/api/schemas/flow_payload.py` | `c430852c37c1b74cd3c7ab8c1098ebfabd05cc60cba52c80fd9a2c6b68129a13` |
| `backend/src/modules/flow/domain/payload.py` | `a302388e21a814ee30479ef2284d2f5a303ad5024d74132681a55f90948a8dd4` |
| `backend/src/api/schemas/flow_execution.py` | `9cc1850ca28ee8a1164dd94674c035a4166bfe1f7162ffa823e44f5c1e80bee6` |
| `backend/src/modules/flow/domain/execution.py` | `f72766c450dd41d69998018fdcbb82870daf62dee7930a675e5723806aff94ea` |
| `backend/src/api/schemas/flow_report.py` | `4152ef3914d3b55564108f9a4a3d56b4aa3737e15a5e182c483a3451a1597df3` |
| `backend/src/modules/flow/api/schemas.py` | `5756997023026769c9c679ef7a9bd3d8b1d04af9e21754781bd680aa6f5f16c6` |
| `backend/src/api/routes/flow_reports.py` | `a5ec97aecd5f17c01fd3bf4073bded865153f2b39bda7134bd1e28f78849e5ba` |
| `backend/src/modules/flow/api/router.py` | `3e7500cb9a661ae81a61536963e2dac8de35f97777ccc89eb3f42bd8447c68bc` |
| `ai/src/agents/flow/schemas.py` | `caf8b53152fdad2e9733282cc3c89c239db19993c35874d622d3e68bcb5bf332` |
| `ai/src/agents/flow/domain/models.py` | `5d3e2c5a243a0faed6f638f2af802a138d338e5bc324ebab3b2573810162fd12` |
| `ai/src/agents/flow/export/to_json.py` | `5c8dccaad89b76b06794a1783e59a55c8cceb41346cfceb5c3c05a453175c0e4` |
| `ai/src/agents/flow/api/payload.py` | `9523f4af93b14f77b41f440e83a1352932914d8d0e6f833c7ac174c9dab812a7` |
| `backend/src/api/main.py` | `cdd506c21df843e24f718c790a6f0f69ffd9bdc9de793ea701224c6235a08621` |
| `backend/src/api/services/flow_report_service.py` | `73de05a20a7a404a407deb9d702c35781eab6ea7be0c4468eb5531161f1bff09` |
| `backend/src/api/routes/reports.py` | `95b0ab452492431385619258eaa7326c9ec29d34f39fabd07ac2243069a85e44` |
| `backend/tests/unit/test_flow_contract.py` | `be2386226ebc6cb5157657dc93a479037e507b7b60f8d9dcfa44da82b9320579` |
| `backend/scripts/check_safe.py` | `e16637095b0856819003c55f90262174eb0d9ae4e0f5449d2dfcf3c7b56974ae` |
| `backend/scripts/safe_checks_bootstrap.py` | `6346c844a99762adaf599a472723e473a6ec6a0ec7700c1cdbeb98fb8ea6851a` |
| `backend/tests/safe_checks/test_entry.py` | `55df0abcf9baffe32289573c1819ac7f66e8f6587e50b884486bd7fba2249dc9` |

## 독립 검토와 남은 범위

조율자의 첫 source-only 독립 대조에서 6개 실행 본문 AST·AI bytes·main/service/common reports import-only·기존 dirty 20개 bytes 보존 및 diff check를 확인했다고 전달받았다. 이는 보고받은 정적 결과이며 위 직접 실행과 구분한다. 이후 조율자의 최종 source-only 독립 재검토가 완료됐다. 보고서의 최종 Python 19개 해시/구문·기존 Flow 테스트 AST 보존·보호 함수의 국소 변경·exact input/origin과 인접 경로 거부·FastAPI 단일 등록/OpenAPI parity를 확인했으며, 위 직접 실행의 251개 통과/guard 0 근거와 최종 코드가 대응한다고 전달받았다. 조율자는 테스트를 별도 재실행하지 않았으므로 독립 실행 통과로 기록하지 않는다. 이 검토에서 4-A 구조 이동을 막는 결함은 없으며 다음 확정 단위로 이어갈 수 있다.

기존 [3-B 기록](ST-001-stage-3-B.md)의 Frontend self-test 20/unit 35 및 build exit 78·HTTP/type/lint 미실행은 당시 결과로 보존한다. 이번 Python relocation이 그 build/전체 3-B를 통과시킨 것이 아니다. Frontend 파일은 이번 첫 단위에서 이동하지 않았고 전체 구조 재구성의 다음 매핑 대상이다.

실제 SQL·DB migration/저장·Google 로그인·외부 AI/모델·원본 앱 서버·Frontend build/HTTP/type/lint는 이번에 실행하지 않았다. 이 이동에서 runtime/API/DB/auth/port 의미를 변경하지 않아 해당 통합 재실행을 완료 근거로 주장하지 않는다. Backend application/infrastructure·auth/stocks/reports 및 다른 AI agent/Supervisor/shared·Frontend app/BFF/features/shared/tests/docs/assets는 후속 실제 이동으로 남는다. 전체 인벤토리에서 미이동을 완료로 세지 않는다.

전체 이동과 독립 검토가 끝나기 전 `git add .`나 과거 23개 고정 명령을 현재 변경 집합에 재사용하지 않는다. 사용자 직접 commit/push/Draft PR 원칙을 유지한다. 첫 단위 권장 메시지는 `refactor(flow): move contracts and API into feature modules`이며 전체 작업의 최종 PR 제목/본문·안전한 명령은 실제 전체 변경/검증 범위에 맞춰 다시 작성한다. 지금 실제 Git/gh 변경 액션은 없다.
