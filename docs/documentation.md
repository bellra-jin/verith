# 문서 목록과 권위

문서 목록 버전 1 / 확인일 2026-11-07, Asia/Seoul (+09:00).
검토 코드 `a5b60f2fd0b00efedae2c98a2004ede62470b094` (CF-002 PR #2 병합).
문서가 있다는 사실은 해당 기능의 공개 허용·검증 완료·실제 환경 설정을 뜻하지 않는다.

## 현재 개발 시작점

1. [루트 README](../README.md)의 현재 상태와 [현재 책임/DB 경계](architecture/current-boundaries.md)를 읽는다.
2. 아래 표에서 수정할 도메인의 계약과 코드 기준을 고른다. Technical 계약을 Flow나 전체 서비스 계약으로 확대하지 않는다.
3. [포트/설정 안내](local_ports.md)와 서비스별 [Frontend](../frontend/README.md)/[Backend](../backend/README.md)
   README를 확인한다. 서비스 실행·migration·seed·DB/Google/AI 검사는 문서 열람의 부수 작업이 아니다.
4. [검증 상태와 이력](#검증-상태와-이력)을 확인하고 필요한 승인/격리와 실행 범위가 없으면 실제 자원 검사를 시작하지 않는다.

## 권위와 충돌 처리

사용자의 최신 제한과 해당 작업의 확정 지시, 해당 도메인의 확정 공유 계약, 검토한 코드/실행 근거를
대조한다. 문서가 없거나 과거/다른 도메인이라면 코드가 틀렸다고 기계적으로 판단하지 않는다.
충돌의 출처·영향·권장안을 작성 담당에게 보고하고 확정 계약을 먼저 맞춘다. 구현 차이를 문서로
숨기거나 새 범용 contracts/api_spec 파일을 복제해 독립 정본을 만들지 않는다.

| 역할 | 파일 / 소유 범위 | 버전·기준 / 현재 상태 |
|---|---|---|
| 작업 지시 원본 | 외부 CF/ST 지시서 | 원본은 저장소 밖에서 보존. clone에 없는 경로로 탐색 링크를 만들지 않음. 개인 운영 문서·실행 승인은 공유하지 않음 |
| 공유 지시 파생본 | [CF-001](contracts/CF-001-v1.1.shared-v1.md), [CF-002](contracts/CF-002-v0.6.shared-v1.md) | 현재 사용 publication **shared-v1** 각각. 원본 아님. source/snapshot hash와 절 대응은 [manifest](contracts/manifest.json) |
| DB 물리 구조 | [schema](../backend/docs/schema.md), [모델](../backend/db/models), [revision](../backend/db/migrations/versions) | a5b60f2 tree, auth 확장 head c2001a7e0001. 문서·ORM·Alembic 대조; 실제 DB 적용 여부는 별도 |
| DB 변경 절차 | [migrations](../backend/docs/migrations.md), [DB 경계](../backend/docs/db_boundaries.md) | 현재 안전 경로와 과거 canonical 운영 기록을 구분 |
| Flow payload/검증 | [v1 storage-spec](../ai/src/agents/flow/docs/storage-spec.md), [exporter](../ai/src/agents/flow/export/to_json.py), [validator](../backend/src/api/schemas/flow_payload.py) | payload version 1, CF-001+후속 CF-002 적용. storage-spec의 초기 미구현 설명은 이력 |
| Flow 인증/owner | [CF-002 공유 계약](contracts/CF-002-v0.6.shared-v1.md), [현재 경계](architecture/current-boundaries.md#현재-공개-경로와-데이터-책임) | Backend가 최종 principal/root-index 검증. 공개 save 허용 아님 |
| Technical JSON/enum/화면 | [contracts](../ai/src/agents/technical/docs/contracts.md), [api_spec](../ai/src/agents/technical/docs/api_spec.md), [frontend_mapping](../ai/src/agents/technical/docs/frontend_mapping.md), [enums](../ai/src/agents/technical/docs/enums.md) | a5b60f2의 **Technical 도메인 문서**. 전체 서비스/Flow/auth 계약 아님. 현재 사용자 Technical 경로는 비활성 |
| Backend Technical API | [technical_frontend_api_contract](../backend/docs/technical_frontend_api_contract.md) | 저장/read model의 Technical 응답 계약. 현재 경로 공개/분석 실행 허가와 별개 |
| 공통 보관함 카드 | [report_archive_api_contract](../backend/docs/report_archive_api_contract.md) | 카드 shape/projection. CF-002의 현재 접근 허용은 본인 Flow만; 모든 agent 필터가 실행 가능하다는 뜻 아님 |
| 종목 식별/마스터 | [stock_resolver](../backend/docs/stock_resolver.md), [KIS master](../backend/docs/stock_master_sync.md), [DART corp code](../backend/docs/dart_corp_code_sync.md) | 종목 resolver·종목 마스터·법인 식별 레이어를 구분. 관리 sync는 수동 별도 작업 |
| Fundamental 직접 DB | [현재 관찰·호환·미확인 경계](architecture/current-boundaries.md#fundamental-직접-db-호환-경로) | SELECT로 필드 3개를 읽는 경로가 존재. 실제 최소 권한은 미확인. 새 API/자격/권한 변경 없음 |
| 개발 작성 가이드 | [Frontend](../frontend/docs/frontend_coding_guidelines.md), [Backend](../backend/docs/backend_coding_guidelines.md) | 현재 도메인 링크/실제 entry 참조. 예시 구조를 실제 재배치 지시로 쓰지 않음 |
| 구현/실행 이력 | [CF-001](../backend/docs/flow_contract.md), [CF-002](../backend/docs/flow_auth_ownership.md), [Google 검증 기록](../backend/docs/google_login_check.md) | 각 보고 시점·합성/실제·실패/미검증을 보존. 상단 현재 상태 주석과 본문 이력 분리 |
| 과거 PR 초안 | [CF-002 실행 명령](../backend/docs/cf002_commit_pr.md), [CF-002 PR 본문](../backend/docs/cf002_pr_body.md), [News 초안](../PR_DESCRIPTION.md) | **현재 실행 안내 아님**. 고정 HEAD stage/실제 자원 명령을 재사용하지 않음 |

## 외부 목표 설계와 출처

외부 **Verith_고도화_상세설계_v1.0.md**(v1.0)는 목표 아키텍처/안전 원칙,
**verith_고도화_mvp.md**(v0.1)는 단계 범위 제안이다. 원문은 이 clone에 포함하지 않는다.
논리 문서명·버전·source hash는 manifest의 reference_documents에 기록한다.
상세설계의 전체 실행/복구·다중 관점 목표를 현재 구현 완료로 읽지 않는다.

현재 문서 작업 지시는 **ST-001_문서_정본과_안전한_개발_기반_정리.md v1.0**,
source SHA-256 `1b7975913e92ff08065b2094879075fbe796e6e57d6227890b8bc92a772c5010`이다.
이번 구현 기준은 위 a5b60f2이며 1단계 문서만 미커밋이다. root/backend/ai AGENTS·공용 환경 예제·
수집 전 차단 검사 entry는 후속 분리 단계다. 다음 단계는 이 단계 검토와 사용자 병합 후 최신
develop에서 별도 브랜치로 시작한다. 큰 파일/폴더 재배치 구조는 비교 검토 전 **후보**이며 미확정이다.

## 검증 상태와 이력

ST-001 1단계는 문서 링크/anchor·출처/버전/hash·개인/비밀 제외·runtime diff 0을 직접 검사한다.
기능 테스트·서비스 실행·DB/Google/AI 검사를 재실행하지 않는다. 아래 기능 수치는 병합된
**과거 CF 보고서 확인**이며 이번 문서 단계의 실행 결과가 아니다.

- CF-001 보고: unit 148·실제 격리 PostgreSQL 29·카드 4 통과 기록.
- CF-002 보고: Backend unit 343, Frontend 단위/BFF 15+로컬 합성 Next HTTP 3,
  type/build/대상 lint 통과. PG integration 54+seed 3 등은 보고서에 적힌 이전 회차다.
- 전체 Frontend ESLint는 기존 Technical explicit-any 오류 2건·unused 경고 3건으로 **실패**했다.
  대상 lint 통과를 전체 통과로 바꾸지 않는다.
- 실제 Google A/B 사용자 확인·일부 UI/내부 DB owner·본인 삭제·자기 임시 자원 정리 기록이 있다.
  자연 시간 만료·옛 cookie 재전송·A→B 반대 방향 교차 UI·개별 실제 HTTP/BFF 응답 직접 관측·
  B 상세 본문 명시 확인은 **미검증**이다. PR 병합은 이 검증의 추가 통과가 아니다.
- 기존 [Backend unit 경계](../backend/tests/unit/conftest.py)와
  [Frontend 사본 검사 도우미](../frontend/scripts/check-local-ports.mjs)는 존재한다.
  모듈 수집 전 dotenv/외부 자원 차단까지 보장하는 새 공통 entry는 후속이며, AI 전체 pytest를
  parent env만 지워 실행해도 안전하다고 가정하지 않는다.
- ignored Compose는 공유되지 않았고 실제 private override/현재 DB 자격·포트 상태는 미확인이다.
  원본 비밀 파일을 읽거나 기존 컨테이너/자료를 재현 검사 대상으로 쓰지 않는다.

이번 문서 1단계의 직접 검사·변경 목록은 [ST-001 1단계 기록](work/ST-001-stage-1.md)에 있다.

## 공유본 갱신 절차

원본/확정 계약을 검토한 뒤 새 publication version 파일과 snapshot hash·manifest를 함께 갱신한다.
원본 source hash와 파생 bytes hash를 구분하며 manifest 자신의 hash를 내부에 넣지 않는다.
이전 snapshot을 보존하고 **현재 사용 버전은 이 목록에서만 지정**한다.
개인 이름/계정/프로젝트 정보·전체 로컬 경로·대화·원시 영수증·일회성 credential 승인은 공유하지 않는다.
오타/링크만 고쳐도 출판된 snapshot의 새 버전과 hash를 기록한다.
