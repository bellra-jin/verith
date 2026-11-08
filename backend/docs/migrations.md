# veriθ Backend — PostgreSQL 마이그레이션 가이드

## CF-003 추가 revision과 비파괴 경계

새 revision `c3001a7e0001` (`20261108_c3001a7e0001_flow_run_admission.py`)은 `c2001a7e0001` 뒤에
flow_runs 하나만 추가한다. 기존 revision/자료 backfill은 없다. downgrade는 같은 transaction에서
ACCESS EXCLUSIVE를 먼저 획득한 뒤 nonempty이면 DROP 전에 거부한다.
운영 DB 삭제/초기화 안내가 아니며, 빈 새 테이블의 downgrade/reupgrade·동시 insert 순서는
승인된 새 소유 DB와 동일 attested 연결의 verified_test_mode에서만 검사한다.
[이번 계약](flow_run_admission.md)·[실행 상태](../../docs/work/CF-003-flow-run-admission.md)를 확인한다.

`docs/migrations.md`

이 문서는 PostgreSQL 스키마를 변경하고 Alembic 마이그레이션을 검증하는 절차를 다룬다.
테이블·관계·제약의 정본은 [`schema.md`](schema.md), 로컬 실행은 [`../README.md`](../README.md)를
따른다.

## 1. 기본 규약

- `backend/alembic.ini`와 `backend/db/migrations/env.py`를 사용한다.
- Alembic 환경은 `asyncpg` 기반이며 `create_async_engine`과 `connection.run_sync`로 실행한다.
- DSN은 `src.shared.config.settings.DATABASE_URL`에서 읽는다.
- 모델을 추가하면 `backend/db/models/registry.py`의 import와 `__all__`에 반드시 등록한다.
- DB 컬럼·테이블을 바꾸기 전에 `docs/schema.md`를 먼저 갱신한다.

## 2. 스키마 변경 절차

### 2.1 모델 작성

- `backend/db/models/<domain>/<file>.py`에 모델을 둔다.
- `db.models._shared.uuid_pk`와 `created_at`을 재사용한다.
- UUID PK, 문자열 종목코드, `timestamptz`, `jsonb`, `Decimal` 등은 `schema.md`의 타입 규칙을 따른다.
- report 종속 자식 FK에는 `ondelete="CASCADE"`를 사용한다.
- `stocks` 같은 마스터 참조에는 CASCADE를 사용하지 않는다.
- Neo4j 객체(Event/Company/…)를 PostgreSQL 테이블로 만들지 않는다.

### 2.2 registry 등록

새 모델 클래스를 `backend/db/models/registry.py`에 import하고 `__all__`에 추가한다. 등록하지 않으면
Alembic autogenerate가 모델을 인식하지 못한다.

### 2.3 revision 생성

```bash
cd backend
uv run alembic revision --autogenerate -m "<메시지>"
```

### 2.4 생성 파일 수동 점검

- 새 extension은 autogenerate되지 않으므로 필요한 경우 명시적으로 생성한다.
- `pgcrypto`와 `vector`는 initial migration에서만 생성·삭제하며 후속 migration에서 drop하지 않는다.
- pgvector 타입을 추가했다면 migration의 `pgvector.sqlalchemy.vector` import를 확인한다.
- DESC/표현식 인덱스가 `sa.text("... DESC")`로 렌더됐는지 확인한다.
- 자식 FK의 `ondelete="CASCADE"`, UNIQUE, NOT NULL이 모델 정책과 일치하는지 확인한다.

### 2.5 적용과 정합성 검증

```bash
uv run alembic upgrade head
uv run alembic check
uv run ruff check db src
```

아직 공유되지 않은 초기 migration을 검증할 때만 필요에 따라 왕복 테스트를 수행한다.

```bash
uv run alembic downgrade base
uv run alembic upgrade head
```

`downgrade base`는 모든 애플리케이션 테이블과 initial extension을 제거하므로 공유 개발 DB나 운영 DB에서
실행하지 않는다.

## 3. 공유된 migration 정책

- 브랜치 내부에서 아직 아무도 적용하지 않은 migration은 수정·재생성할 수 있다.
- 이미 공유·머지되어 팀원 DB에 적용된 migration은 수정하지 않는다.
- 공유 후 변경이 필요하면 새 revision에서 ALTER로 보강한다.
- 삭제된 revision을 팀원 DB의 `alembic_version`이 가리키는 상태를 만들지 않는다.

## 4. 검증 SQL

```bash
docker exec verith-postgres psql -U verith -d verith -c "
  SELECT extname FROM pg_extension WHERE extname IN ('pgcrypto','vector');
  SELECT count(*) FROM information_schema.tables
    WHERE table_schema='public' AND table_name<>'alembic_version';
  SELECT format_type(atttypid,atttypmod) FROM pg_attribute
    WHERE attrelid='news'::regclass AND attname='embedding';
"
```

현재 initial schema 기준 기대값은 extension 2개(`pgcrypto`, `vector`), 애플리케이션 테이블 22개,
`news.embedding=vector`다.

## 5. 트러블슈팅

| 증상 | 원인 / 해결 |
|---|---|
| `Connect call failed ('127.0.0.1', 5432)` | 호스트 실행 시 `DATABASE_URL`을 compose host 포트 15432으로 맞춘다. |
| `CREATE EXTENSION vector` 실패 | PostgreSQL 이미지가 `pgvector/pgvector:pg16`인지 확인한다. |
| `ValueError: the greenlet library is required` | `uv sync`로 `sqlalchemy[asyncio]` 의존성을 설치한다. |
| `NameError: pgvector` | migration 상단의 `import pgvector.sqlalchemy.vector`를 확인한다. |
| `agent_reports ... stocks` FK 위반 | `stocks`를 먼저 확보한 뒤 report/index를 저장한다. |
| collation version mismatch 경고 | 개발 볼륨/OS locale 차이로 발생할 수 있다. 필요 시 DB collation version을 갱신한다. |


## CF-002 현재 경계

Host DSN 안내: `postgresql+asyncpg://<user>:<password>@localhost:15432/<database>`.
Compose 내부는 `postgres:5432` 그대로다. 포트 패치는 실제 migration/재시작 승인이 아니다.
검증은 앱 DB가 아닌 승인된 별도 일회용 PostgreSQL에서 readonly preflight·실제 SQLAlchemy
연결 재확인 후 동일 연결을 Alembic attributes/run_sync에 전달한다. verified test mode에
연결이 없으면 앱 URL 로딩 전에 실패한다. auth 행/소유권이 있으면 CF-002 downgrade는 거부된다.
기존 앱/운영 DB에서 위 왕복·extension drop 검사를 실행하지 않는다.
[CF-002 실행 증거](flow_auth_ownership.md), [포트 안내](../../docs/local_ports.md).


## CF-006 입력 준비 revision

`c6001a7e0001`의 parent는 `c3001a7e0001`이다. 신규 snapshot/제약/trigger를 한 transaction에서 만들고 기존 receipt/auth/report/index/stock을 backfill하지 않는다. 기존 pgcrypto만 사용한다.

downgrade는 flow_runs ACCESS EXCLUSIVE → flow_input_snapshots ACCESS EXCLUSIVE 순서로 잠근 뒤 nonempty면 거부한다. 빈 경우에만 이번 테이블·함수·parent UNIQUE를 제거한다. 직접 DELETE/TRUNCATE나 trigger 해제로 시험을 정리하지 않는다. 실제 owned PG에서 기존 receipt upgrade 보존·빈 왕복·신규 CREATE 직후 rollback·첫 봉인/downgrade 양방향을 확인했으며 [실행 이력](../../docs/work/CF-006-flow-input-snapshot.md)에 실패와 최종 source 차이를 분리했다. 운영 DB 실행 안내나 장기 purge 정책이 아니다.


## CF-007 revision

새 `c7001a7e0001`의 parent는 `c6001a7e0001`이다. 새 실행/결과 테이블과 전용 trigger/function만 생성하며 기존 행/backfill·공유 extension 변경은 없다. downgrade 잠금은 flow_runs→flow_input_snapshots→flow_fake_executions 순서다. running/failed/timed_out도 포함한 실행행이 존재하면 고정 거부하고 내용/revision을 보존한다. 실행행이 없으면 기존 입력 snapshot이 있어도 새 객체만 제거한다.

고정 runner의 기존 CF003/006 mode는 caller가 c6001을 선택하고 새 fake mode는 head에서 정확 c7001을 확인한다. CLI 임의 revision은 받지 않는다. 새 DDL 주입은 새 checker의 FLOW_FAKE_EXECUTIONS CREATE 직후 전용 예외이며 기존 checker 훅을 확장하지 않는다. [결과](../../docs/work/CF-007-flow-fake-execution.md)와 [내부 계약](flow_fake_execution.md)을 확인한다.

## CF-012 `c12001a7e0001`

`c7001a7e0001` 다음 revision은 `flow_analysis_runs` 하나와 전이 검증 trigger를 추가한다. 기존 receipt/input/fake/report 자료는 수정하지 않는다. downgrade는 ACCESS EXCLUSIVE 잠금 뒤 빈 테이블만 제거하며 행이 있으면 거부한다. 기존 DB에 적용하거나 자료를 비워 downgrade하지 않는다. 승인된 자기 PG에서 새 DDL 직후 실패 rollback과 이전 자료 보존을 검사한다.

## CF-015 · c15001a7e0001

Parent `c12001a7e0001`. Adds nullable Fundamental root owner, ownerful partial index uniqueness, and a separate guarded analysis ledger. No legacy backfill. Duplicate ownerful indexes abort upgrade. Downgrade locks and refuses any nonempty ledger/owned root/index. Only disposable attested PG is tested by the focused checker.
