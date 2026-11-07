# Verith 저장소 작업 안내

이 파일은 저장소 전체의 공통 작업 안내다. 먼저 [문서 권위 목록](docs/documentation.md)을 읽고,
수정 범위의 [Frontend](frontend/AGENTS.md)·[Backend](backend/AGENTS.md)·[AI](ai/AGENTS.md) 안내를
함께 적용한다. 하위 안내는 해당 범위의 구체 규칙을 보완하며 사용자 지시나 작업 범위를 확대하지 않는다.
관련 하위 AGENTS/기존 로컬 지침과 충돌하면 출처·영향을 확인하고 해당 부분만 보고한다.

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
| FastAPI Backend | [main](backend/src/api/main.py), [config](backend/src/api/config.py) | principal/세션·owner·저장/조회/삭제·오류 경계 |
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
- 현재 Backend unit fixture/DB guard와 Frontend 사본 도우미는 존재하지만 **수집 전 공통 안전 entry가
  완성된 것은 아니다**. 서비스 안내의 사전 조건/제한을 읽고 실행한다. AI 전체 pytest를 기본 검사로 돌리지 않는다.
- 단위/합성 HTTP·실제 PG·실제 Google/사용자 UI·실제 AI를 나눠 보고한다. 과거 결과 확인을 이번
  직접 실행으로 바꾸지 않는다. 전체 lint의 기존 실패와 실제 인증 미검증은 [검증 상태](docs/documentation.md#검증-상태와-이력)에 남아 있다.
- 로컬 host port와 엄격한 callback/Origin/CSRF 규칙은 [포트 안내](docs/local_ports.md)를 따른다.
  container 내부 port·모델 inference 주소를 일괄 치환하거나 private override가 맞는다고 가정하지 않는다.

## 이번 단계와 후속

ST-001 v1.1 2단계의 기준은 `083dea8436b699aa3a52ddbf36848e8fe3535720`이며
현재 결과는 [2단계 기록](docs/work/ST-001-stage-2.md)에 남긴다. 1단계 PR #3 병합과
이 단계 문서 검토는 실제 기능/인증/공개 검증 완료가 아니다.
3-A 공용 환경 예제 → 3-B Backend/Frontend 공통 안전 entry → 3-C AI 안전 entry는 **미구현 후속**이다.
이 단계 검토/사용자 병합 후 최신 develop·별도 branch에서 진행하고 현재 branch에 누적하지 않는다.
큰 파일/코드 디렉터리 재배치 구조는 비교 판단 전 보류한다. 현재 지도는 파일 이동 지시가 아니다.
