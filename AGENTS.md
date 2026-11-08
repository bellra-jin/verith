# Verith 저장소 작업 안내

> **최종 구조 우선 계약:** ST-001 v1.15(명시 Flow 설정·최종 marker 정리)에 따라 불필요한 old shim을 제거하며 canonical 구현 하나로 정리한다. Flow 마지막3도 AI 루트 .env 명시 정책으로 이동했다. 실제 설정 값/AI 실행은 미검증이다. [진행 기록](docs/work/ST-001-layout-progress.md)을 따른다.

> **검증 시점 구분:** 아래 3-B의 9/244·20/35 및 type/lint 미실행 문장은 당시 이력입니다. 현재 Backend self 13/unit 402, Frontend self 21/unit 36·최종 type 도구 차단·대상 lint 기존 오류 2건과 구분합니다. FE-01 standalone core/image tsc 통과는 그 실행 시점 이력입니다. build/HTTP 전체 수용과 AI 잔여 실행은 미완료이며 [진행 기록](docs/work/ST-001-layout-progress.md)을 확인합니다.

이 파일은 저장소 전체의 공통 작업 안내다. 먼저 [문서 권위 목록](docs/documentation.md)을 읽고,
수정 범위의 [Frontend](frontend/AGENTS.md)·[Backend](backend/AGENTS.md)·[AI](ai/AGENTS.md) 안내를
함께 적용한다. 하위 안내는 해당 범위의 구체 규칙을 보완하며 사용자 지시나 작업 범위를 확대하지 않는다.
관련 하위 AGENTS/기존 로컬 지침과 충돌하면 출처·영향을 확인하고 해당 부분만 보고한다.

현재 ST-001 v1.15의 실제 폴더 재배치는 [전체 진행 기록](docs/work/ST-001-layout-progress.md)을 따른다.
Backend·AI·Frontend의 전수 이동 536행 처리를 마쳤고 최종 target525개와 승인된 marker 제거11개로 구분한다.
선택 보호 회귀는 통과했으며 전체 AI/DB/type/build/HTTP 수용과는 구분한다.
아래 3-B의 구조 비교 보류 문장은 당시 이력이며 최신 승인된 이동의 선행조건이 아니다.

## 시작과 변경 보존

- 최신 작업 지시의 버전·허용 파일·완료 기준부터 확인한다. 외부 개인 지시 원본/운영 대화나 과거
  credential 승인은 clone의 실행 권한이 아니다. 공유 파생본의 출처는 [manifest](docs/contracts/manifest.json)에 있다.
- 새 작업은 branch/HEAD·staged/unstaged·worktree·원격/동명 branch 확인 → develop 전환 →
  fetch → ff-only 가능할 때만 최신화 → 전용 branch 순서다. 동일 작업 재개는 새 작업과 구분한다.
- 기존 변경·다른 worktree·분기/충돌이 있으면 보존한다. 강제 checkout/reset/clean·임의 stash/rebase/
  merge로 우회하거나 이전 기능 브랜치에서 다음 작업을 조용히 분기하지 않는다.
- commit/push·실제 PR 생성·Ready·merge는 사용자가 직접 한다. 개발 결과에는 권장 commit 메시지와
  정확한 repo/base/head 및 `--draft`를 포함한 PR 초안·안전한 명령을 준비한다. 명시적 실행 요청 없이
  git add도 하지 않는다. 이미 승인된 범위의 구현/명확한 오류 수정은 같은 허락을 반복 요청하지 않는다.

## 현재 책임과 계약

| 영역 | 실제 시작 경로 | 책임 |
|---|---|---|
| Next | [frontend/src/app](frontend/src/app), [next.config.ts](frontend/next.config.ts) | 동일 origin BFF/SSR·세션 전달·화면. 최종 owner를 결정하지 않음 |
| FastAPI Backend | [main](backend/src/api/main.py), [config](backend/src/shared/config.py) | principal/세션·owner·저장/조회/삭제·오류 경계 |
| AI FastAPI | [main](ai/src/main.py), [routers](ai/src/api) | 분석/계산·결과 export. DB/사용자 owner 책임과 구분 |

[CF-001 공유 계약](docs/contracts/CF-001-v1.1.shared-v1.md) 위에
[CF-002 인증/owner 계약](docs/contracts/CF-002-v0.6.shared-v1.md)을 적용한다.
Backend는 root owner와 정확히 한 index의 동일 owner를 SQL로 검사한다. legacy owner NULL을 자동
귀속/공개하지 않는다. 개인 응답 no-store와 공개 save/전체 삭제/직접 AI proxy 차단을 유지한다.
타입·UUID·임의 사용자 헤더·client_session_id는 인증이 아니다.
구체 예외와 Fundamental master SELECT 호환/권한 미확인은 [현재 책임 지도](docs/architecture/current-boundaries.md)를 따른다.

## 실행과 검증 경계

- config 경로는 소스를 읽어 파악한다. 실제 값을 확인하려고 config/app을 import하거나 `.env`·
  credentials·ignored Docker-compose.yml·Docker Env를 열거나 출력하지 않는다. 기존 DB/volume·
  컨테이너·다른 프로젝트 프로세스를 변경하지 않는다.
- entry·관리 명령·검사 경로가 문서에 있다는 사실은 서비스/DB/Google/AI·모델 다운로드·
  migration/seed·실제 비용 발생 허가가 아니다. 승인된 작업의 필요한 자원/대상/영향만 확인한다.
- 문서 전용 변경은 링크/anchor·JSON/hash·본문 보존·허용 diff·whitespace를 검사한다.
  기능/DB/외부 검사를 불필요하게 실행하지 않는다. 기능 작업의 검사는 해당 단계의 실제 검증 기준을 따른다.
- Backend/Frontend의 3-B 입구 구현은 [3-B 기록](docs/work/ST-001-stage-3-B.md)에 있다.
  Backend self-test 9개·선택 unit 244개는 통과했다. 최신 Frontend self-test 20개·unit 35개는 통과했지만 build가 추가 파일 요청의 guard 거부로 실패했고 HTTP/type/lint가 미실행이므로 **3-B 전체 수용은 미완료**다. 보호를 끄고 pytest/Next를 실행하지 않는다.
  서비스 안내의 사전 조건/한계를 읽으며 AI 전체 pytest를 기본 검사로 돌리지 않는다.
- 단위/합성 HTTP·실제 PG·실제 Google/사용자 UI·실제 AI를 나눠 보고한다. 과거 결과 확인을 이번
  직접 실행으로 바꾸지 않는다. 전체 lint의 기존 실패와 실제 인증 미검증은 [검증 상태](docs/documentation.md#검증-상태와-이력)에 남아 있다.
- 로컬 host port와 엄격한 callback/Origin/CSRF 규칙은 [포트 안내](docs/local_ports.md)를 따른다.
  container 내부 port·모델 inference 주소를 일괄 치환하거나 private override가 맞는다고 가정하지 않는다.

## 3-B 당시 기준과 후속 (이력)

ST-001 v1.7 3-B의 기준은 `7df12403848e480f223767232540d4c2c055ba5e`이며
현재 결과는 [3-B 기록](docs/work/ST-001-stage-3-B.md)에 남긴다. [3-A 기록](docs/work/ST-001-stage-3-A.md)은
PR #5 병합 이력이다. [공용 환경 안내·예제](docs/development.md)는 비밀 없는 참고이며 실제 환경/실행 승인이 아니다.
문서·예제 검토는 실제 기능/인증/공개 검증 완료가 아니다.
3-B 보호·선택 검사·독립 수용은 아직 완료되지 않았다. 3-C AI 안전 entry는 **미구현 후속**이다.
3-B 검토/사용자 병합 후 최신 develop·별도 branch에서 진행하고 현재 branch에 누적하지 않는다.
큰 파일/코드 디렉터리 재배치 구조는 비교 판단 전 보류한다. 현재 지도는 파일 이동 지시가 아니다.

현재 v1.7 진단은 self-test 20개·unit 35개 통과 뒤 build의 22회 거부를 정규화된 ID 10개로 식별했다. 9개 hash 대상은 기존 copy 입력이 아니며 정확한 경로/필요성은 미확인이다. 실행별 HMAC key는 임시 capability에만 두고 제거한다. 추가 읽기/CI/cache/resolver 허용은 없고 native 전체 관측으로 확대하지 않는다.
