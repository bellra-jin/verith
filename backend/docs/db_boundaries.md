# CF-002 현재 DB 경계와 포트

> **현재 적용 범위 (a5b60f2 / 2026-11-07 KST):** 아래 같은 서버의 역할별 DB와 경고-only fixture 설명은 과거 운영 이력이다. 현재 별도 일회용 자원 fail-closed 조건과 Fundamental 직접 SELECT의 최소 권한 미확인을 구분한다.
> [문서 권위](../../docs/documentation.md)와 [현재 책임/DB 경계](../../docs/architecture/current-boundaries.md)를 함께 읽는다. 이번 문서 단계는 기능/DB 검사를 재실행하지 않았다.

로컬 앱 PostgreSQL host mapping은 **15432:5432**이다. host DSN 안내는
`postgresql+asyncpg://<user>:<password>@localhost:15432/<database>`이고 컨테이너 내부
`postgres:5432`는 유지한다. 실제 private URL/자격·기존 컨테이너 전환은 미확인·미실행이다.

pytest는 앱 fallback 없이 승인된 **별도 일회용 자원·주소·제한 역할**만 사용한다.
TEST_DATABASE_URL/TEST_DATABASE_APPROVAL 누락·앱과 같은 서버/별칭·읽기 전용 확인 실패는
DDL/DML 전에 즉시 오류로 중단한다. 같은 인스턴스에 다른 DB명만 만든 것은 현재 격리 조건을
충족하지 않는다. migration도 재확인한 동일 연결을 사용한다.
[현재 검증 절차/증거](flow_auth_ownership.md), [포트 안내](../../docs/local_ports.md).
포트 변경을 이유로 아래 과거의 DB 생성·관리·canonical 승격을 다시 실행하지 않는다.

---

## 과거 운영 기록 — 현재 테스트 준비 절차 아님

# DB 역할 경계 (canonical / dev·smoke / test)

`docs/db_boundaries.md`

**핵심: "어느 DB가 canonical truth인지"를 역할별로 분리한다.** 하나의 공유 DB(dev=test=smoke)를 계속
끌고 가면 운영 `--apply`/seed 커밋이 테스트 전제를 오염시키는 문제가 반복된다. 같은 PostgreSQL
인스턴스(`verith-postgres`, host `:5433`, user `verith`)에 **역할별 DB**를 둔다.

## 역할 표
| DB | 역할 | 내용 | 접속 경계 |
|---|---|---|---|
| **`verith`** | **공용 canonical runtime DB (ACTIVE)** | KIS master sync 전체 주권 **2,607**(KOSPI 893 + KOSDAQ 1,714) + alias 32 + corp_codes **3,976** | `DATABASE_URL` — app·scripts·alembic·`sync_stocks --apply` |
| `verith_canonical` | **검증/이행용(더 이상 runtime truth 아님)** | 승격 검증에 쓴 사본. 백업/참고용(삭제 가능) | (runtime 참조 안 함) |
| **`verith_test`** | **pytest 전용(clean)** | 스키마만(migrate). 테스트가 in-tx seed·rollback 격리 | `TEST_DATABASE_URL` — pytest |

> **공용 DB 승격 완료(2026-07):** **`verith.stocks` 를 13(bootstrap) → 2,607(KIS master 전체 주권)** 로
> `sync_stocks --apply` 반영했다. **DB 이름을 바꾼 게 아니라 공용 `verith` 내용 자체가 canonical** 이다.
> `DATABASE_URL` 은 계속 `verith` 를 가리킨다(팀 운영 방향). `verith_canonical` 은 이행 검증용이었고 이제
> runtime truth 가 아니다. `TEST_DATABASE_URL=verith_test` 불변 — 테스트/runtime DB 혼용 금지.

## URL 경계
- **`DATABASE_URL`** = **`verith`**(ACTIVE canonical): app runtime(FastAPI) · `scripts/*`(seed/sync) · `alembic`.
- **`TEST_DATABASE_URL`** = **`verith_test`**: pytest 만(`tests/conftest.py`). 미설정/앱 DB와 동일하면
  conftest 가 **경고**(오염 위험 노출).
- **canonical stock sync**(`sync_stocks --apply`)는 이제 공용 `verith`(=`DATABASE_URL`)에 적용된다.

## 원칙
- **canonical source = 공용 `verith.stocks`**(KIS master sync 반영, 2,607 주권). `seed_stocks`(battery 10)·
  `seed_representative_stocks`(대표 3)는 **bootstrap/보조**(canonical 에 흡수됨 — 제거 아님, fresh/오프라인
  dev 편의).
- **공용 `verith` 가 canonical truth 다.** `verith_canonical` 은 이행 검증용(백업/참고).
- **sync 는 별도 관리 명령**(`--inspect`/dry-run/`--apply`). **질문 처리 경로(resolver/supervisor/agents)는
  read-only** — 질문 처리 중 stocks 를 자동 insert/update 하지 않는다.
- **alias 는 수동/운영 큐레이션**. sync 는 `stocks` 만 갱신하고 `stock_aliases` 는 손대지 않는다.
- 팀원이 같은 공용 DB 상태를 pull 후 재현해야 할 때는 **live sync 대신 repo SQL dump**
  (`backend/dumps/shared_verith_snapshot.sql`)을 사용한다. 즉 git 이 나르는 것은 Postgres 볼륨이 아니라
  **재현 가능한 canonical data artifact** 다.

## 테스트 오염 해소(검증)
- 전용 `verith_test`(clean)로 pytest → `corp_code_sync` 4건(공유 `verith` 의 3,976 corp_codes commit 전제
  충돌)이 **해소**됨. `test_fundamental_reports` 1건은 DB 오염이 아니라 **코드 이슈**(develop 머지)로 잔존 —
  별도 조사.
- boundary/semantics/resolver 테스트는 실존 종목 가정을 **synthetic 코드**로 분리해 universe 확장에도
  의미 유지(`test_stock_resolver.py`).

## 설정 방법
```bash
# 같은 인스턴스에 역할별 DB 생성(최초 1회) — verith user 는 superuser.
docker exec verith-postgres psql -U verith -d postgres -c "CREATE DATABASE verith_canonical;"
docker exec verith-postgres psql -U verith -d postgres -c "CREATE DATABASE verith_test;"
# 각 DB 스키마
DATABASE_URL=postgresql+asyncpg://verith:verith1234@localhost:5433/verith_canonical uv run alembic upgrade head
DATABASE_URL=postgresql+asyncpg://verith:verith1234@localhost:5433/verith_test        uv run alembic upgrade head
# canonical 에 전체 주권 반영
DATABASE_URL=…/verith_canonical uv run python -m scripts.sync_stocks --apply
```
`backend/.env` 에 `TEST_DATABASE_URL=…/verith_test` 를 두면 pytest 가 전용 test DB 를 쓴다.
> **collation 주의:** 볼륨이 다른 libc 로 생성된 경우 `CREATE DATABASE` 가 template1 collation mismatch 로
> 실패할 수 있다 → `ALTER DATABASE template1 REFRESH COLLATION VERSION;`(postgres·verith 동일) 후 재시도.

## 공용 `verith` canonical 승격 완료 (ACTIVE)
공용 `verith.stocks` 를 **13 → 2,607** 로 `sync_stocks --apply` 반영하고 `verith` 기준 smoke 검증했다.

| 항목 | 상태 | 근거(verith runtime) |
|---|---|---|
| stocks | ✅ | **13 → 2,607**(inserted 2,594 / unchanged 13 / missing 0) |
| representative 13종 흡수 | ✅ | battery+representative 13종 모두 unchanged(충돌 0) |
| stock_aliases / corp_codes | ✅ | 32 alias / 3,976 corp_codes(불변) |
| resolver(broader) | ✅ | 삼성전자·NAVER·SK하이닉스·셀트리온 exact / 삼전·Kakao alias / LG ambiguous / synthetic not_found |
| app runtime | ✅ | `DATABASE_URL=verith`, `src.api.main` import OK |
| read-only 원칙 | ✅ | resolve smoke 후 `verith.stocks` 수 불변(2,607) — 질문 경로 자동 write 없음 |
| pytest 격리 | ✅ | `TEST_DATABASE_URL=verith_test` — verith apply 무관, 156 passed. verith(2,607) 기준 resolver 테스트도 30 passed(synthetic 하드닝이 broader universe 이미 커버 → ripple 0) |

**broader universe 는 의도된 변화(release note 급):** 승격으로 예전 `not_found` 였던 종목(NAVER·SK하이닉스·
셀트리온 등)이 이제 `resolved` 되고, "LG" 는 (주)LG(003550) 포함으로 더 정확히 `ambiguous` 된다. **버그가
아니라 canonical 승격의 결과.**

## 후속(이번 브랜치 밖)
- **fundamental contract-violation 테스트 fixture 수정**(`meta.erd_payload.fundamental_report` 부재 —
  DB/runtime blocker 아님, `verith_test` 기준 pytest 유일 실패). 승격과 무관해 분리한다.
- 실행 중인 backend(:8000)는 승격 전 상태로 떠 있으면 **재기동**해야 2,607 반영(같은 `verith` DB 라 재기동만).
- `verith_canonical`(이행 사본) 정리/삭제, delete/deactivate·상장폐지 lifecycle, sync 이력, min_count 상향.
