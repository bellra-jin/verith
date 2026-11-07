# Backend 작업 안내

[상위 공통 안내](../AGENTS.md)와 [문서 권위](../docs/documentation.md)를 먼저 읽는다.
이 파일은 backend 범위의 구체 책임/검사 위험을 설명하며 실제 DB·외부 인증 실행을 허가하지 않는다.

## 실제 entry와 책임

- FastAPI app: [src/api/main.py](src/api/main.py), 설정: [src/api/config.py](src/api/config.py).
  config는 기본적으로 backend dotenv source를 읽고 main은 route/config를 import한다.
  설정을 확인하려고 import/서버 시작을 하지 말고 소스만 읽는다.
- 요청/응답과 최종 status는 [routes](src/api/routes), 입력/출력 검증은 [schemas](src/api/schemas),
  유스케이스/transaction 조율은 [services](src/api/services), SQL/CRUD는 [repositories](src/api/repositories)가 맡는다.
- 모델은 [db/models](db/models), 스키마 정본은 [schema](docs/schema.md), migration은
  [db/migrations](db/migrations)와 [절차 문서](docs/migrations.md)다. 기존 공유 revision을 임의 수정하지 않는다.
- 분석 수치·국면/신호·LLM 해석을 Backend에서 새로 계산/보정하지 않는다.
  수동 KIS/DART master sync와 분석 요청 흐름은 [책임 지도](../docs/architecture/current-boundaries.md)에서 구분한다.

## 인증·owner·저장 경계

[Google/auth router](src/api/routes/auth.py)·[세션 service](src/api/services/auth_service.py)와
[Flow service](src/api/services/flow_report_service.py)·[repository](src/api/repositories/flow_report_repository.py)를 함께 본다.
principal은 검증된 앱 세션에서 얻으며 body owner/사용자 헤더/UUID는 인증이 아니다.
Flow root owner와 정확히 한 공통 index/동일 owner 조건을 목록/count·batch·상세·개별 삭제에
SQL로 적용한다. legacy NULL owner를 자동 연결하거나 노출하지 않는다.

공개 save·전체 삭제·구 직접 AI/다른 관점/관리 우회는 [AccessBoundary](src/api/access_boundary.py)와
동일 계약으로 닫는다. 개인 응답은 private/no-store, mutation은 CSRF/정확한 Origin을 검증한다.
세션/루트 잠금 순서·폐기 commit·원자 저장/삭제·shared stock 보존을 지킨다.
원본 Flow ID/v1 payload·한시 JSONB/legacy 보존은 [CF-001](../docs/contracts/CF-001-v1.1.shared-v1.md),
후속 인증/owner/migration은 [CF-002](../docs/contracts/CF-002-v0.6.shared-v1.md)를 따른다.
공통 실행·실제 AI·전용 snapshot/게시 복구·늦은 결과 경합을 구현한 것으로 확대하지 않는다.

## 현재 검사 경로와 사전 조건

기존 의존성은 [pyproject.toml](pyproject.toml)·[uv.lock](uv.lock)을 따른다. 검사 준비를 이유로
재설치/전역 업그레이드·실제 환경 복사를 하지 않는다. 다음은 **기존 명령의 위치 설명**이며
문서 단계에서 실행하는 기본 절차가 아니다.

- 단위 fixture: [tests/unit/conftest.py](tests/unit/conftest.py). backend 작업 디렉터리와 기존
  설치된 의존성에서 사용하는 현재 명령은 `.venv/bin/python -m pytest --confcutdir=tests/unit tests/unit -q`다.
  confcutdir는 상위 DB fixture 수집을 피한다. autouse fixture는 test module 수집/최상위 import보다
  늦을 수 있으므로 이 명령만으로 private 파일/네트워크의 **수집 전 차단**을 보장하지 않는다.
  별도 검사 작업에서 대상 import/환경/의존성과 격리를 먼저 확인하고, 불확실하면 실행하지 말고 보고한다.
- DB fixture: [tests/conftest.py](tests/conftest.py), [Flow fixture](tests/flow_integration/conftest.py),
  guard: [tests/db_safety.py](tests/db_safety.py). 이 경로는 단위 기본 명령으로 실행하지 않는다.
  기존 root fixture의 앱 대상 비교는 dotenv source를 읽을 수 있다. private 파일을 읽는 검사를
  문서/환경 확인 명목으로 호출하지 않는다.
- 실제 DB 검사는 승인된 **별도 일회용 자원·주소·제한 역할**을 확인하고 asyncpg readonly preflight →
  engine → 실제 연결 readonly 재대조 → 동일 검증 연결 migration 순서다. 미확인/앱과 같은 서버/
  별칭/자격·소유 불명은 DDL/DML 전에 중단하며 앱 DB fallback·skip·경고 후 실행은 금지한다.
  직접 생성 소유 증명 runner도 기존 container 채택/일반 guard 우회가 아니다. 실제 실행은 별도 대상/권한 조건을 따른다.

3-B의 수집 전 보호를 갖춘 Backend/Frontend 공통 안전 entry는 **미구현 후속**이다.
3-A [환경 안내](../docs/development.md)·[Backend 예제](../docs/examples/backend.env.example)는 비밀 없는 참고이며
실제 설정/실행 승인이 아니다. 문서·예제만 바꾸는 이 단계에는 unit/build/lint·앱/DB/Google/AI/Docker·migration/seed를 실행하지 않는다.
과거 통과/실패·실제 인증의 남은 검증은 [문서 목록](../docs/documentation.md#검증-상태와-이력)에 구분한다.
