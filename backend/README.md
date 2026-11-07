# veriθ Backend

## 공용 환경 참고 · ST-001 3-A

[개발 환경 안내](../docs/development.md)·[Backend 변수 예제](../docs/examples/backend.env.example)·
[별도 명시 Compose 참고](../docs/examples/compose.local.example.yaml)를 추가했다. 실제 자격/설정이나
기동 검증을 제공하지 않는다. DATABASE_URL의 필수 검증과 AI_SERVICE_URL 검증 부재, graph 조건을
구분한다. 아래 Docker/migration/seed/restore/sync는 기본 테스트 준비가 아니며 3-B 안전 entry도 미구현이다.
기존 .env/ignored Compose/DB·자료는 조회·복사·변경하지 않는다.

## 문서 탐색과 현재 범위

[문서 목록/권위](../docs/documentation.md), [Backend 작성 가이드](docs/backend_coding_guidelines.md),
[현재 책임/DB 경계](../docs/architecture/current-boundaries.md)를 먼저 읽는다.
현재 공개 사용은 검증된 본인 Flow 조회·개별 삭제이며, 아래 과거 분석/관리 예시는 현재 허용 API가 아니다.
[CF-001](../docs/contracts/CF-001-v1.1.shared-v1.md)의 저장 계약에
[CF-002](../docs/contracts/CF-002-v0.6.shared-v1.md)의 인증/owner·차단 경계를 함께 적용한다.
Fundamental의 마스터 SELECT 호환과 실제 role의 최소 권한 미확인은 책임 지도에서 구분한다.
실제 .env·ignored Compose는 clone의 공용 환경 예제가 아니다. 아래 Docker/migration/seed/restore/sync
명령은 별도 대상·권한·데이터 영향을 확인하는 관리 작업이며 기본 테스트 준비로 실행하지 않는다.
이번 문서 단계에서는 기능/DB/Google/AI 검사를 재실행하지 않는다.


FastAPI 백엔드 — 요청을 받아 AI 에이전트를 호출하고, 결과 JSON을 검증·저장하고, 프론트에 제공한다.

- DB 구조·관계·제약 정본: [`docs/schema.md`](docs/schema.md)
- Alembic 변경·검증 절차: [`docs/migrations.md`](docs/migrations.md)
- Stock Resolver 응답 의미·경계: [`docs/stock_resolver.md`](docs/stock_resolver.md)
- 전체 종목 마스터 동기화(KIS): [`docs/stock_master_sync.md`](docs/stock_master_sync.md)
- DART 법인코드 동기화(corp_code): [`docs/dart_corp_code_sync.md`](docs/dart_corp_code_sync.md)
- **DB 역할 경계(canonical/dev/test)**: [`docs/db_boundaries.md`](docs/db_boundaries.md)
- **Technical Report Frontend API 계약(정본, 프론트 구현 기준)**: [`docs/technical_frontend_api_contract.md`](docs/technical_frontend_api_contract.md)
- Technical Report backend handoff(구현 노트): [`docs/technical_backend_handoff.md`](docs/technical_backend_handoff.md)
- Technical Follow-up answer 생성 경계(caller-provided 정책·미래 AI 경로): [`docs/technical_followup_answer_boundary.md`](docs/technical_followup_answer_boundary.md)
- 리포트 보관함 공통 목록 API(agent_type 필터 카드 리스트): [`docs/report_archive_api_contract.md`](docs/report_archive_api_contract.md)

## CF-002 로컬 포트 전환

Backend 실행 명령은 `uv run uvicorn src.api.main:app --reload --port 8200`이다.
브라우저/CORS 기본은 `http://localhost:3200`, Backend→AI 안내값은
`AI_SERVICE_URL=http://localhost:9200`이다. 실제 AI는 이번 작업에서 기동/호출하지 않는다.
Backend `DATABASE_URL`은 `postgresql+asyncpg://<user>:<password>@localhost:15432/<database>`이다.
`NEO4J_URI`는 `bolt://localhost:17687`을 host 안내로 사용한다. Compose 내부 포트는 유지한다.
Google local callback/origin은 3200이며 AUTH 설정은 명시해야 한다.
[비밀 없는 전체 안내](../docs/local_ports.md), [CF-002 검증 보고](docs/flow_auth_ownership.md).
기존 private override는 미확인이다. 아래 기존 관리 명령은 대상/영향을 확인한 별도 작업이며
포트 변경을 이유로 컨테이너 재시작·migration·seed·restore를 자동 실행하지 않는다.

## 개발 환경

```bash
# 저장소 루트에서 PostgreSQL(+pgvector) 기동 (host 포트 15432)
docker compose up -d postgres

cd backend
uv sync
# DATABASE_URL은 환경변수 또는 backend/.env로 주입
# 호스트에서 compose DB에 연결할 때: postgresql+asyncpg://...@localhost:15432/...
uv run alembic upgrade head     # 스키마 적용
```

`DATABASE_URL`은 필수이며 환경변수가 `backend/.env`보다 우선한다. 드라이버는 `asyncpg`이므로
DSN 스킴은 `postgresql+asyncpg://`를 사용한다. 컨테이너 내부에서 연결할 때는 서비스명과 컨테이너
포트 5432를 사용하고, 호스트에서 연결할 때는 compose host 포트 15432을 사용한다.

## Seed stocks

`stocks` 에 **개발 bootstrap 종목(10종 + market)** 을 seed 한다.

> ⚠️ **이 10종은 개발 bootstrap 데이터이지 전체 종목 정본이 아니다.** Stock Resolver 는 종목 수와
> 무관한 공통 구조지만, 현재 실제 식별 가능한 범위는 seed 된 10종뿐이다. 전체 KRX 종목 지원은 후속
> 마스터 동기화 작업(별도 브랜치)이 완료돼야 한다 — [`docs/stock_resolver.md`](docs/stock_resolver.md) §5.
> `stocks`(공통 마스터)와 Technical 10종 지원 정책(`BATTERY_TICKERS`)은 **별개**다.

```bash
cd backend
# 순서 중요: 종목 마스터 먼저, 그다음 Stock Resolver 별칭.
uv run python -m scripts.seed_stocks
uv run python -m scripts.seed_stock_aliases
```

주의:
- PostgreSQL 이 실행 중이어야 하고, `DATABASE_URL`(포트 15432) 이 설정돼 있어야 한다.
- 두 스크립트 모두 **idempotent** (`ON CONFLICT ... DO NOTHING`) — 여러 번 실행해도 기존 row 를 덮지 않는다.
- `seed_stock_aliases` 는 참조 종목이 `stocks` 에 없으면 **부분 seed 없이 fail-fast** 하므로 반드시 `seed_stocks` 를 먼저 실행한다.
- 별칭 정본은 `src/api/constants/stock_aliases.py`(변형만 — 공식 이름은 `stocks.stock_name`).

**전체 종목 마스터 동기화(bootstrap 과 별개, 수동·네트워크):** 개발 10종 seed 는 bootstrap 이고, 전체
국내 종목은 KIS 마스터를 `sync_stocks` 로 동기화한다. 기본 dry-run(DB 미변경), `--apply` 에서만 반영.
```bash
uv run python -m scripts.sync_stocks            # dry-run
uv run python -m scripts.sync_stocks --inspect   # 앵커 검산(DB 미변경)
uv run python -m scripts.sync_stocks --apply      # 실제 반영(commit)
```
자세한 출처·파싱·포함/제외·정책은 [`docs/stock_master_sync.md`](docs/stock_master_sync.md).

**DART 법인코드 동기화(별도 계층, 수동·네트워크):** 재무(Fundamental) 에이전트가 DART 조회 전에 쓰는
`stock_code → corp_code` 정본을 DART `corpCode.xml` 로 동기화한다(`stock_corp_codes`, stocks 와 no-FK 별도
계층). 기본 dry-run, `--apply` 에서만 반영. `DART_API_KEY`(sync 전용, startup 필수 아님)가 필요하다.
```bash
uv run python -m scripts.sync_corp_codes            # dry-run
uv run python -m scripts.sync_corp_codes --inspect   # 파싱 요약·샘플 검산(DB 미변경)
uv run python -m scripts.sync_corp_codes --apply      # 실제 반영(commit)
```
자세한 출처·파싱·이상치·정책은 [`docs/dart_corp_code_sync.md`](docs/dart_corp_code_sync.md).

확인:

```sql
SELECT stock_code, stock_name, market FROM stocks ORDER BY stock_code;
```

## Shared verith SQL dump

팀원이 **외부 KIS/DART sync 를 다시 돌리지 않고도** 공용 `verith` canonical 상태를 pull 후 재현할 수 있게,
repo 에 **SQL dump snapshot** 을 커밋해 둔다([`dumps/README.md`](dumps/README.md)).

권장 순서:

```bash
docker compose up -d postgres

cd backend
uv sync
uv run alembic upgrade head
docker exec -i verith-postgres psql -U verith -d verith < dumps/shared_verith_snapshot.sql
```

restore 후 확인:

```bash
docker exec verith-postgres psql -U verith -d verith -c "SELECT COUNT(*) FROM stocks;"
docker exec verith-postgres psql -U verith -d verith -c "SELECT COUNT(*) FROM stock_aliases;"
docker exec verith-postgres psql -U verith -d verith -c "SELECT COUNT(*) FROM stock_corp_codes;"
```

이 dump 는 다음 canonical 상태를 담는다.

- `stocks` — **2,607**
- `stock_aliases` — **32**
- `stock_corp_codes` — **3,976**

주의:

- 이 dump 는 **공용 `verith` 데이터를 snapshot 기준으로 다시 맞춘다**. 즉 `stocks` / `stock_aliases` /
  `stock_corp_codes` 는 snapshot 상태로 덮어쓴다고 생각하면 된다.
- 스키마는 dump 가 아니라 **Alembic** 이 관리하므로, 반드시 `uv run alembic upgrade head` 를 먼저 실행한다.
- backend 가 이미 떠 있으면 restore 후 **재기동**하는 편이 안전하다.

## CF-002 테스트 진입 기준

단위 검사는 `.venv/bin/python -m pytest --confcutdir=tests/unit tests/unit -q`로 실행한다.
실제 DB 검사는 명시적 TEST_DATABASE_URL과 승인된 별도 일회용 자원 manifest·제한 역할·
readonly preflight/실연결 재확인이 필수다. 앱 DB와 같은 서버의 다른 DB명은 허용하지 않는다.
[실제 검증 harness와 절차](docs/flow_auth_ownership.md)를 따른다. 기존 DB 생성·migration
예시는 현재 테스트 준비 명령으로 복사 실행하지 않는다.

## 관련 검사

```bash
cd backend
.venv/bin/python -m pytest --confcutdir=tests/unit tests/unit -q
```

DB 검사는 별도 일회용 PostgreSQL 승인·제한 역할·manifest가 확인된 뒤에만
[CF-002 검증 harness](docs/flow_auth_ownership.md)를 따른다. TEST_DATABASE_URL을 private .env에
추가하거나 같은 앱 서버에 verith_test라는 이름만 만드는 것으로는 실행되지 않는다.
미설정/같은 앱 대상은 경고가 아니라 setup error로 중단한다. 포트 패치 검증에서는
DB migration/seed/기존 컨테이너 실행 없이 단위·정적 검사를 수행한다.

마이그레이션 생성, downgrade 주의사항, 검증 SQL과 DB 트러블슈팅은
[`docs/migrations.md`](docs/migrations.md)에 정리돼 있다.
