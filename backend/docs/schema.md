# veriθ Backend — 통합 PostgreSQL 스키마 (팀 공유 문서)

## CF-022 추가: Supervisor 확정 계획 binding

`c22001a7e0001`(parent `c18001a7e0001`)의 `supervisor_request_bindings`는 실행 원장이 아닌 계획→고정 Flow 입력 연결 한 표다. [공통 계약](../../docs/contracts/supervisor-core-v1.md)을 따른다. UUID PK/owner FK RESTRICT, owner+client_key_digest32 UNIQUE, 확정 digest와 plan/Flow JSON/hash, 유일 Flow key digest, finite DB confirmed_at/handoff_before(+120초)/redacted_at을 둔다. JSON object/크기/hash·identity·불변 trigger를 적용하며 populated downgrade는 거절한다.

binding ACK 확인 뒤 바깥 transaction을 끝내고 기존 AnalysisService/FlowUsageControl을 호출한다. 실행/claim/usage/result는 기존 Flow 원장만이 권위다. 삭제는 기존 session→analysis→root 잠금 순서 뒤 같은 transaction에서 연결 plan/Flow JSON을 null로 redact하며 hash/owner/key/usage를 보존한다. 표 누락 fallback은 없고 운영 적용은 migration 선행조건이다. 소유 PG 검사와 실제 운영 DB 적용 여부는 [작업 기록](../../docs/work/CF-022-supervisor-core.md)에서 구분한다.

## CF-003 추가: receipt-only Flow 접수

`flow_runs`는 `c3001a7e0001`에서 추가하는 접수 전용 테이블이다. 기존 결과 테이블을 재사용하거나
pending 결과/index를 만들지 않는다. [API/물리 계약](flow_run_admission.md)과
[이번 검증 기록](../../docs/work/CF-003-flow-run-admission.md)을 따른다.
owner FK RESTRICT, owner/operation/key-digest UNIQUE, 예약 attempt UNIQUE,
flow/version1/digest32/hex64/JSONB object/receipt_only/pending/not_stored/finite 시각 CHECK를 둔다.
키 원문은 저장하지 않으며 정규화 입력·fingerprint와 최초 추적/run/attempt ID를 보존한다.
실행권·예산·worker·snapshot·report 연결을 구현한 테이블이 아니다.

`docs/schema.md`

이 문서는 veriθ 백엔드의 **통합 ERD 기준 PostgreSQL 물리 스키마 정본**이다. 테이블·관계·타입·
제약·인덱스와 PostgreSQL/Neo4j 경계만 다룬다. 로컬 실행과 테스트는 [`../README.md`](../README.md),
스키마 변경 절차와 검증은 [`migrations.md`](migrations.md)를 따른다.

- 스키마 정의(정본): SQLAlchemy 모델 `backend/db/models/**` + Alembic 마이그레이션
- 최초 마이그레이션: `backend/db/migrations/versions/20260707_705a5833d4a3_add_integrated_postgresql_schema.py` (revision `705a5833d4a3`)
- DB 컬럼·테이블 변경은 이 문서를 먼저 갱신한다(코딩 가이드 §1.1).

---

## 1. PostgreSQL 확장 (extension)

최초 마이그레이션 `upgrade()` 가 테이블 생성 **전에** 아래를 만든다.

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- uuid PK 기본값 gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS vector;     -- news.embedding 의 vector 타입
```

> **확장 관리 규칙:** `pgcrypto`/`vector` 는 **이 initial 마이그레이션에서만** 생성/삭제한다.
> **후속 마이그레이션에서는 extension 을 drop 하지 않는다** (공유 자원).

---

## 2. 타입 규칙

| 종류 | 규칙 |
|---|---|
| UUID PK | postgres `uuid`, 기본값 `gen_random_uuid()` |
| 종목코드/ticker/corp_code | **varchar (문자열)**. 숫자 타입 금지(앞자리 0 보존) |
| created_at / as_of | `timestamptz` (created_at 은 서버 기본값 `now()`) |
| base_date | `date` |
| JSON | `jsonb` |
| news.embedding | `vector` (pgvector, **차원 미지정** — §5 참고) |

---

## 3. 테이블 카탈로그 (23개, 도메인별)

### Common
| 테이블 | 요약 | PK |
|---|---|---|
| `stocks` | **공통 종목 마스터**(코드·이름·시장). `stock_name` 이 공식 이름 정본 | `stock_code` (varchar) |
| `stock_aliases` | 종목 별칭(변형/영문/약칭/구명/모호그룹). `stock_code` FK→stocks **ON DELETE CASCADE** | `id` (uuid) |
| `stock_corp_codes` | **DART 법인식별 정본**(`stock_code`→`corp_code`, 상장사만). `corp_code` UNIQUE, **stocks FK 없음(no-FK)** | `stock_code` (varchar) |
| `agent_reports` | 전 에이전트 리포트 통합 인덱스 | `id` (uuid) |

> **stocks 소유권/범위:** `stocks` 는 Backend 소유 공통 마스터로, 장기적으로 전체 국내 상장 종목을
> 담는다. **현재 seed 된 10종은 개발 bootstrap** 이며 전체 정본이 아니다. 전체 KIS 종목 마스터 동기화는
> [`stock_master_sync.md`](stock_master_sync.md) 참고(수동·네트워크, insert/update만·삭제 없음).
> Technical 10종 지원 정책(`BATTERY_TICKERS`)과는 **별개**다.
> `stock_aliases` 제약: `UNIQUE(normalized_alias, stock_code)` · `CHECK(normalized_alias<>'')` ·
> `index(stock_code)`. 공식 이름은 여기 중복 저장하지 않는다(정본=`stocks.stock_name`).
> Resolver 응답 의미·경계는 [`stock_resolver.md`](stock_resolver.md) 참고(여기 중복 안 함).
>
> **stock_corp_codes 소유권/경계:** DART OpenAPI `corpCode.xml` 기준 **법인식별 정본**(상장사 `stock_code`
> → 8자리 `corp_code`). `stocks`(KIS/KRX 마스터)와 **책임이 다른 별도 계층**이라 `stock_code → stocks`
> **물리 FK 를 걸지 않는다**(no-FK 논리 링크) — DART 상장 전체를 stocks 적재 상태와 무관하게 선반영하기
> 위함. `corp_name_from_dart` 는 DART 공시명 원문이며 **`stocks.stock_name` 정본을 대체하지 않는다**.
> 제약: `PK(stock_code)` · `UNIQUE(corp_code)`. 동기화는 [`dart_corp_code_sync.md`](dart_corp_code_sync.md)
> 참고(수동·네트워크, insert/update만·삭제 없음). 조회 endpoint/AI wiring 은 후속 브랜치.

### Fundamental (재무)
| 테이블 | 요약 |
|---|---|
| `fundamental_reports` | 재무 분석 리포트 root |
| `report_ratios` | 재무 비율(roe·부채비율 등) |
| `report_evidence` | 비율/주장의 DART 원천 근거 |
| `fundamental_report_interpretations` | LLM/규칙 해석 (1:1) |
| `fundamental_report_verifications` | 검증 결과 (1:1) |
| `report_insights` | 배당/주주/감사 등 맥락 인사이트 |
| `report_filing_snippets` | 공시 원문 스니펫 |

### Technical (기술적)
| 테이블 | 요약 |
|---|---|
| `technical_reports` | 기술적 분석 리포트 root. 목록 `GET /api/technical/reports` / 상세 `GET .../{id}`(read model + trust_summary) / 차트 `GET .../{id}/charts`(full payload) / trace `GET .../{id}/trace`(단계 재구성, duration null) — 계약 [`technical_frontend_api_contract.md`](technical_frontend_api_contract.md) |
| `technical_report_signals` | 지표 신호 |
| `technical_report_charts` | 차트 페이로드 |
| `technical_report_risk_notes` | 리스크 노트 |
| `technical_report_interpretations` | 해석 (1:1) |
| `technical_report_verifications` | 검증 (1:1) |
| `technical_report_followups` | 후속 질의. write: `POST .../{id}/followups`(answer=caller 제공, parent snapshot 저장) / read: `GET .../{id}/followups` |

> **Technical read model(조회 계약 ≠ 저장 형식).** `technical_reports.output_payload` 에 AI output 원본(raw)을
> 계속 보존하되, **API 응답(`POST`·`GET /api/technical/reports/{id}`)은 프론트 친화 read model**로 정리해
> 반환한다(`stock`(canonical)·`meta`·`summary`·`interpretation`·`drivers`·`signals`·`risks`·`charts`·
> `verification` 블록). `stock` 은 **canonical `stocks` 우선**. AI 구조화 해석(one_line_summary·directional_bias·
> timeframe_alignment·key_drivers 등)은 `technical_report_interpretations.sections`(JSONB)에 저장되며, read model
> 은 projection 이라 구버전 payload(섹션 없음)에서도 shape 가 안정적이다. backend 는 값을 재해석하지 않는다.
> 응답에는 **`trace_summary`**(생성 경로·데이터 품질·검증 요약·flag) 블록도 포함된다 — "어떻게 생성/검증됐는지"의
> 제품용 요약(raw trace 미노출). 저장값 projection 이라 신규 저장 없음. 계약 정본: [`technical_backend_handoff.md`](technical_backend_handoff.md).

### News (뉴스, PostgreSQL 부분만)
| 테이블 | 요약 |
|---|---|
| `news` | 기사 원본. `embedding vector`, `event_id`(Neo4j 논리 링크) |
| `news_reports` | 뉴스 질의 결과 리포트 (`report_id` PK) |

### Flow (수급)
| 테이블 | 요약 |
|---|---|
| `flow_reports` | 수급/자금흐름 리포트 root |
| `flow_report_interpretations` | 해석 (1:1) |
| `flow_report_verifications` | 검증 (1:1) |

CF-001은 물리 스키마를 변경하지 않는다. **이번 한시 호환 저장 방식**은 기존 `checks` JSONB의
`gate1/2/3`를 유지하면서 예약 키 `_flow_payload_snapshot`에 검증된 v1 원본을
보존한다. version·추가 필드·null·생략 보존과 구 자료 reader 규칙은
[flow_contract.md](flow_contract.md)를 따른다. 전용 snapshot 저장소는 후속이다.
신규 형식 표식은 checks와 agent_reports.summary의 `_flow_storage_format`에 함께
보존한다. 이는 물리 컬럼이나 payload version 추가가 아니다.

### Industry (산업/섹터)
| 테이블 | 요약 |
|---|---|
| `industry_reports` | 산업 에이전트 PostgreSQL 리포트 저장 테이블. `payload`=research-report.v1 전체 JSON 정본 |

> **명칭 확정:** 5번째 에이전트는 **industry(산업/섹터)**. 과거 `macro` 명칭은 폐기, 테이블은 `industry_reports`.
>
> **industry_reports 규약:**
> - `payload`(jsonb)는 산업 에이전트 **research-report.v1 전체 JSON 정본**이다.
> - `report_id`(text, UNIQUE)는 `payload.reportId` 와 매핑되는 **외부 노출 ID**. 내부 PK 는 `id`(uuid)다.
> - `status`(pending/processing/completed/failed)가 리포트 lifecycle 정본. `data_status`·`input_payload`·`output_payload` 는 통합 호환용(reserved).
> - `agent_reports.agent_report_id` 는 `industry_reports.id`(report_id 아님)를 가리키는 **app-level reference**(FK 없음).
> - **Neo4j 의 Company/Industry/Product/Policy/Person/Chunk 는 PostgreSQL 테이블로 만들지 않는다**(그래프는 app 레벨 별도 처리).
> - 인덱스: `report_id` UNIQUE, `created_at DESC`, `question_type`, `payload` **GIN**, `request_id`, `trace_id`.

---

## 4. 관계와 무결성 (PostgreSQL 한정)

Neo4j 그래프(EVENT/COMPANY/SECTOR/…)는 **PostgreSQL 테이블이 아니다**(§6). 아래는 PG FK만.

```mermaid
erDiagram
    STOCKS ||--o{ AGENT_REPORTS : indexed_by
    STOCKS ||--o{ FUNDAMENTAL_REPORTS : analyzed_in

    FUNDAMENTAL_REPORTS ||--o{ REPORT_RATIOS : contains
    FUNDAMENTAL_REPORTS ||--o{ REPORT_EVIDENCE : has
    REPORT_RATIOS ||--o{ REPORT_EVIDENCE : proven_by
    FUNDAMENTAL_REPORTS ||--|| FUNDAMENTAL_REPORT_INTERPRETATIONS : explained_by
    FUNDAMENTAL_REPORTS ||--|| FUNDAMENTAL_REPORT_VERIFICATIONS : verified_by
    FUNDAMENTAL_REPORTS ||--o{ REPORT_INSIGHTS : contextualized_by
    FUNDAMENTAL_REPORTS ||--o{ REPORT_FILING_SNIPPETS : cites

    TECHNICAL_REPORTS ||--o{ TECHNICAL_REPORT_SIGNALS : contains
    TECHNICAL_REPORTS ||--o{ TECHNICAL_REPORT_CHARTS : has
    TECHNICAL_REPORTS ||--o{ TECHNICAL_REPORT_RISK_NOTES : observes
    TECHNICAL_REPORTS ||--|| TECHNICAL_REPORT_INTERPRETATIONS : explained_by
    TECHNICAL_REPORTS ||--|| TECHNICAL_REPORT_VERIFICATIONS : verified_by
    TECHNICAL_REPORTS ||--o{ TECHNICAL_REPORT_FOLLOWUPS : continues

    FLOW_REPORTS ||--|| FLOW_REPORT_INTERPRETATIONS : explained_by
    FLOW_REPORTS ||--|| FLOW_REPORT_VERIFICATIONS : verified_by
```

FK 전체 목록 (19개):

```
agent_reports.stock_code                        -> stocks.stock_code
fundamental_reports.stock_code                  -> stocks.stock_code
technical_reports.stock_code                    -> stocks.stock_code
flow_reports.stock_code                         -> stocks.stock_code
report_ratios.report_id                         -> fundamental_reports.id
report_evidence.report_id                       -> fundamental_reports.id
report_evidence.ratio_id (nullable)             -> report_ratios.id
report_insights.report_id                       -> fundamental_reports.id
report_filing_snippets.report_id                -> fundamental_reports.id
fundamental_report_interpretations.report_id(UQ)-> fundamental_reports.id
fundamental_report_verifications.report_id(UQ)  -> fundamental_reports.id
technical_report_signals.report_id              -> technical_reports.id
technical_report_charts.report_id               -> technical_reports.id
technical_report_risk_notes.report_id           -> technical_reports.id
technical_report_followups.report_id            -> technical_reports.id
technical_report_interpretations.report_id(UQ)  -> technical_reports.id
technical_report_verifications.report_id(UQ)    -> technical_reports.id
flow_report_interpretations.report_id(UQ)       -> flow_reports.id
flow_report_verifications.report_id(UQ)         -> flow_reports.id
```

**ON DELETE CASCADE** (자식 15개 FK): fundamental 7 + technical 6 + flow 2. report 삭제 시 자식이 함께 삭제된다. **`stocks` 참조 4개(agent_reports·fundamental_reports·technical_reports·flow_reports)는 마스터라 CASCADE 아님(NO ACTION).**

**FK 를 걸지 않는 것** (앱 레벨 논리 링크):
`agent_reports.agent_report_id`, `news.event_id`(Neo4j Event.canonical_id),
`news_reports.evidence`, 모든 `owner_user_id` / `owner_session_id`,
**`stock_corp_codes.stock_code`→stocks**(DART 계층 분리·상장 전체 선반영 목적, 의도적 no-FK).

UNIQUE (10): `technical_reports.request_id`, `news.url`, **`technical_report_signals(report_id, indicator)`**, **`stock_corp_codes.corp_code`**, 그리고 1:1 report_id 6개(fundamental·technical·flow interpretations/verifications).

**NOT NULL 정책(핵심):** 항상 존재하는 실행 메타데이터와 degraded에도 sentinel로 채워지는 컬럼만 NOT NULL. 예) `technical_reports`: `request_id`·`ticker`·`data_status`·`source`·`trace_id`·`as_of`·`input_payload`·`output_payload`·`final_regime`·`daily_regime`·`alignment_flag` = NOT NULL / `consensus`·`signal_score`·`confidence`·`weekly_trend`·`monthly_trend` = nullable. `news`: `title`·`url` NOT NULL. 통합 ERD 신규 컬럼(`timeframe`, `chart_*`)은 저장 정책 확정 전까지 nullable.

명시 인덱스 (`ix_` 18개 + signals UNIQUE 제약 1, DESC 는 표현식 인덱스):
```
agent_reports        (agent_type, created_at DESC) / (client_session_id, created_at DESC)
                     / (stock_code, created_at DESC) / (trace_id)
fundamental_reports  (request_id) / (stock_code, as_of DESC) / (trace_id)
technical_reports    (client_session_id, created_at DESC) / (stock_code, as_of DESC) / (ticker, as_of DESC) / (trace_id)
technical_report_charts     (report_id, period)
technical_report_signals    UNIQUE(report_id, indicator)
technical_report_risk_notes (report_id, severity)
technical_report_followups  (report_id, created_at)
news                 (event_id) / (published_at)
news_reports         (created_at DESC)
flow_reports         (stock_code, base_date DESC) / (ticker, base_date DESC) / (trace_id)
```

---

## 5. news.embedding 차원(dimension) 미정

- 임베딩 모델은 `arctic-embed-l-v2.0-ko`(news `SCHEMA_SPEC.md`)지만 **차원 숫자가 코드/문서에
  확정돼 있지 않아**, 컬럼은 **차원 없는 `vector`** 로 생성했다.
- 유사도 검색용 **ANN 인덱스(ivfflat/hnsw)** 는 차원 확정 후 **별도 마이그레이션**에서 추가한다.
  (dimensionless vector 에는 ANN 인덱스를 만들 수 없다.)

---

## 6. Neo4j 경계 — PostgreSQL 에 만들지 않는 것

아래는 뉴스 에이전트의 **Neo4j logical graph** 이며 **PostgreSQL 테이블로 만들지 않는다.**

```
EVENT, COMPANY, SECTOR, NEWSREF, KEYWORD, PERSON, COUNTRY
```

PostgreSQL 에는 `news.event_id`(nullable uuid)만 둬서 Neo4j `Event.canonical_id` 를 **논리적으로**
가리킨다. DB FK 는 없다. Event↔News 연결은 backend app 레벨에서 처리한다.

---

## 7. 마이그레이션 불변 규칙

- 모델 추가 시 `backend/db/models/registry.py`에 등록한다.
- 테이블·컬럼·제약 변경은 Alembic revision으로 반영한다.
- `pgcrypto`와 `vector`는 initial migration에서만 생성·삭제하고 후속 migration에서 drop하지 않는다.
- 이미 공유·적용된 migration은 수정하지 않고 새 revision에서 보강한다.
- 상세 생성·검증·트러블슈팅 절차는 [`migrations.md`](migrations.md)를 따른다.

---

## 8. 저장 계층 주의사항

- **`agent_reports.stock_code` / `fundamental_reports.stock_code` / `technical_reports.stock_code` / `flow_reports.stock_code`
  → `stocks.stock_code` FK**:
  리포트를 저장하기 전에 해당 종목이 `stocks` 에 있어야 한다.
  기본 지원 종목은 [`../README.md`](../README.md)의 seed 절차로 구성한다. 런타임 저장에서도
  결측에 대비해 `stocks`를 먼저 확보한 뒤 리포트/index를 저장한다.
- `stock_code` 는 **nullable** 이다(뉴스/산업/거시성 질의는 종목이 없을 수 있음).


## CF-002 v0.3 — 서버 인증과 Flow 소유권 확장

`auth_users`: 서버 발급 UUID PK, created_at timestamptz, nullable disabled_at.
`auth_identities`: UUID PK, user_id RESTRICT FK, 대소문자를 보존하는 nonempty issuer TEXT와
subject VARCHAR(255), created_at. UNIQUE(issuer, subject), user_id index. 최초 연결은 사용자와
신원을 같은 savepoint에서 생성하고 UNIQUE 경쟁 실패 시 둘 다 rollback 후 기존 신원을 읽는다.
`auth_sessions`: UUID PK, user_id RESTRICT FK, 유일한 SHA-256 token_digest BYTEA(32),
created_at/expires_at/revoked_at timestamptz. expires_at은 유한하며 created_at보다 미래,
revoked_at은 NULL 또는 created_at 이후. user_id/expires_at 및 expires_at index.
원문 난수 bearer는 DB에 저장하지 않는다. TTL 기본 3600초, 매 요청 DB 유효성 확인.

flow_reports.owner_user_id는 nullable RESTRICT FK이며 기존 행은 NULL 그대로 보존한다.
owner/created_at DESC/id DESC index를 추가한다. common agent_reports의 기존 owner/session
UUID는 논리 링크로 보존하고 global FK/UNIQUE/NOT NULL을 추가하지 않는다.
agent_type/owner/created_at DESC/id DESC 비유일 index를 추가한다.
Flow root owner가 정본이며 정확히 한 Flow index의 owner가 같아야 reader에 노출한다.
모든 목록/count/pagination/batch/detail/delete에서 SQL로 owner와 적격 projection을 검증한다.
삭제 잠금 순서는 유효 세션 공유 잠금 → 소유 root FOR UPDATE → index 정합성 → 삭제이다.
공개 저장·전체 삭제·다른 관점·Supervisor 직접 AI 경로는 닫는다.

b1e9d4a7c2f1 다음 확장 revision만 추가한다. auth 데이터 또는 nonNULL root owner가 있으면
파괴적 downgrade를 거부한다. 테스트 migration은 승인된 일회용 PostgreSQL의 구성·readonly
preflight 및 실제 SQLAlchemy 연결 재확인 후 동일 연결을 Alembic에 전달한다.
실제 외부 OIDC 검증은 내부 합성 세션/owner PostgreSQL 검증과 구별한다.


## CF-006 합성 입력 snapshot

`c6001a7e0001`은 기존 `flow_runs`에 `UNIQUE(id, owner_user_id)`만 더하고 `flow_input_snapshots`를 추가한다. 기존 receipt 값·상태·요청 키를 수정하지 않는다.

새 열은 id UUID PK, run_id/owner_user_id UUID, contract_version integer, mode TEXT, input_json TEXT, input_sha256 VARCHAR(64), sealed_at TIMESTAMPTZ이며 전부 NOT NULL이다. UNIQUE(run_id), (run_id,owner_user_id) composite FK/ON DELETE RESTRICT, version1/synthetic_only/finite 시각/UTF-8 128KiB/body version·mode/실제 SHA CHECK가 적용된다. no-op UPDATE·DELETE도 전용 trigger로 거부한다. domain의 canonical/schema/source 검증은 별도로 필요하다. 기존 receipt 자체의 DB 불변성이나 관리자 ALTER/DROP/TRUNCATE 차단을 추가한 것은 아니다. [내부 계약](flow_input_snapshot.md)을 따른다.


## CF-007 내부 fake 실행/결과

`flow_fake_executions`(c7001)은 input_snapshot_id UNIQUE FK/RESTRICT로 봉인 입력당 단일 실행권/결과를 저장한다. owner/run은 기존 input/run JOIN으로 판단하고 parent 열/제약을 추가하지 않는다. id/input/version/engine/claim/start/deadline은 불변, 상태는 running→succeeded/failed/timed_out 단1회이며 DELETE는 모든 상태에서 거부한다.

DB clock 기준10초 deadline·finite시각·상태별 결과/hash/error/finished NULL조합과 canonical 결과 object/UTF-8크기/hash/ID 관계를 검사한다. succeeded만 결과가 있다. token 원문은 저장하지 않고 digest32bytes만 보존한다. 기존 receipt/payload/report/index/stock은 바꾸지 않으며 관리자 DDL/장기 purge 정책은 별도다. [내부 계약](flow_fake_execution.md)을 따른다.

## CF-012 Flow 분석 원장

`flow_analysis_runs`는 receipt/synthetic/fake와 별도인 인증 분석 원장이다. owner/operation/key digest, attempt 및 채택 report ID가 유일하며 claim·시간·상태별 snapshot/null 관계를 DB 제약으로 검사한다. running→result_ready→stored→deleted와 failed/unknown terminal을 구분한다. result_ready의 canonical input/result 및 SHA를 먼저 commit하고 root/자식/index 게시와 stored 전이는 원자 처리한다. deleted는 요청·이름·입력·결과 본문을 비우고 최소 식별/hash만 보존한다. [공유 계약](../../docs/contracts/flow-analysis-v1.md).

## CF-015 · owned Fundamental analysis

`fundamental_analysis_runs` stores one immutable grant/request-context/result snapshot per owner/key. Unique attempt/report references and fenced state transitions prevent reuse after deletion. `fundamental_reports.owner_user_id` is nullable for legacy only. Owned readers require root + exactly one same-owner index + stored ledger; NULL legacy stays private.

## CF-018 편입 Flow 비용 원장

revision `c18001a7e0001`은 `analysis_usage_periods`(KST 기간·최초 한도 snapshot·횟수·held/추정 spend·blocked), `analysis_usage_reservations`(run/owner/attempt/grant·원 기간·고정 가격/상한·잔여 예약), `analysis_provider_calls`(유일한 provider/action/ordinal·UUID·attempted·nullable usage·정제 evidence hash)를 추가한다. 금액은 BIGINT 정수 nanoUSD이며 KIS 비용은 NULL이다. 원문·credential은 없다.

`flow_analysis_runs.budget_reservation_id`는 legacy에 NULL을 유지한다. 새 INSERT는 run ID와 같은 nonnull 참조가 필요하고, 양방향 composite FK 및 deferred constraint trigger가 commit 때 run↔reservation·기간 scope/owner/통화/날짜 관계를 확인한다. 식별·기간 한도·가격 snapshot은 불변이다. attempted True 역행과 확정 증거 교체, 회계 이력 삭제를 거부한다. 기존 report/receipt/synthetic schema·행은 변경하지 않는다. [사용 한도 계약](../../docs/contracts/flow-usage-v1.md)을 따른다. 실제 적용 여부는 [작업 기록](../../docs/work/CF-018-flow-usage-limits.md)과 구분한다.
