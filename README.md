# veriθ — 멀티 에이전트 주식 분석 서비스

## Top Supervisor · 가격/기술적 분석 에이전트

> 사용자의 자연어 질문을 5개 전문 에이전트에 분배하고, 실제 시세를 바탕으로 기술적 국면·신호·신뢰도·리스크를 설명하는 서비스입니다.
>
> 이 문서는 팀 프로젝트 전체가 아니라 제가 담당한 **Top Supervisor, 가격/기술적 분석 에이전트, technical 리포트 연동**을 중심으로 작성했습니다.

---

## 1. 프로젝트 개요

| 항목 | 내용 |
|---|---|
| 프로젝트명 | veriθ — 멀티 에이전트 주식 분석 서비스 |
| 진행 기간 | 2026.07.02 ~ 2026.07.10 |
| 인원 | 5인 팀 프로젝트 |
| 담당 역할 | Top Supervisor, 가격/기술적 분석 에이전트, 리포트 백엔드·프론트엔드 연동 |
| 핵심 구현 | LangGraph 10노드 파이프라인, 결정론 기반 신호·검증, KIS 장애 대응, 리포트 저장·시각화 |
| 검증 규모 | 담당 AI 범위 테스트 함수 831개 — technical 711개, supervisor 120개 |

veriθ는 하나의 질문을 기술적 분석, 재무, 뉴스·감성, 수급, 산업·섹터의 5개 관점으로 나누어 분석합니다. 저는 **질문의 실행 경로를 결정하는 Top Supervisor**와 **가격 데이터를 분석하는 technical agent**를 구현했습니다.

### 핵심 성과

- 질문을 해석하고 5개 에이전트의 실행 여부를 결정하는 Top Supervisor 설계
- 기술적 분석을 10개 노드로 분리한 LangGraph 파이프라인 구현
- 국면·점수·신뢰도·리스크는 코드가 확정하고 LLM은 설명만 담당하도록 책임 분리
- LLM 라벨 왜곡을 탐지하는 결정론 검증과 재생성·템플릿 폴백 구현
- KIS 재시도, 타임프레임별 stale cache, 데이터 부족 상태를 포함한 장애 대응
- technical 리포트의 DB 스키마, API 계약, Next.js 화면까지 end-to-end 연결

---

## 2. 시연 영상

[![veriθ 기술적 분석 리포트 시연](https://img.youtube.com/vi/rqtL-DXbrH4/maxresdefault.jpg)](https://www.youtube.com/watch?v=rqtL-DXbrH4)

> 질문 입력부터 Supervisor 분배, 기술적 분석, 차트·리스크·검증 결과 렌더링까지 확인할 수 있습니다.

---

## 3. 문제 정의

### 3.1 LLM이 금융 판단까지 맡아도 되는가

LLM에 분석을 전부 맡기면 입력에 없는 수치를 만들거나 코드가 계산한 국면과 반대되는 설명을 생성할 수 있습니다. 예를 들어 결과가 `sideways`인데도 “상승 전환”이라고 표현하면 사용자는 잘못된 신호를 받게 됩니다.

프롬프트로만 통제하기보다, **LLM이 결정할 수 있는 범위 자체를 제한하고 결과를 코드로 검증하는 구조**가 필요했습니다.

### 3.2 데이터가 불완전할 때 어떻게 동작해야 하는가

외부 시세 API는 지연되거나 일부 타임프레임만 실패할 수 있고, 신규·미상장 종목은 분석에 필요한 봉이 부족할 수 있습니다. 값을 추정해 채우거나 전체 요청을 실패시키는 대신 현재 확보한 데이터 상태를 명확히 드러내야 했습니다.

### 3.3 설계 원칙

- **결정은 코드, 설명은 LLM** — 국면·점수·신뢰도·리스크를 코드로 확정합니다.
- **투자 지시보다 관찰 결과** — “매수/매도” 대신 “관찰된다/보인다”는 표현을 사용합니다.
- **모르면 모른다고 응답** — 데이터가 부족하면 `regime_unavailable`로 종료합니다.
- **장애와 데이터 부족을 구분** — 인프라 장애, 종목 미식별, 부분 데이터 부족을 다른 상태로 표현합니다.
- **실증 범위만 문서화** — 확인하지 않은 종목과 기능을 완료로 표현하지 않습니다.

---

## 4. 담당 범위와 전체 흐름

```text
ai/src/supervisor/                # 질문 해석·종목 식별·에이전트 분배
ai/src/agents/technical/          # 가격/기술적 분석 — LangGraph 10노드
ai/src/api/                       # supervisor·technical 내부 API
backend/src/api/**/technical_*    # 리포트 저장·조회
backend/db/models/technical/      # 리포트 스키마·마이그레이션
frontend/src/features/technical/  # technical 리포트 화면
```

```text
사용자 질문
    ↓
Top Supervisor
├─ 질문 유형 판별: company / industry / market / general
├─ 필요할 때만 종목 resolver 호출
├─ 에이전트별 실행 가능 여부 결정
└─ 5개 전문 에이전트에 맞는 지시 생성
    ↓
technical agent
시세 수집 → 지표 계산 → 국면 분류 → 신호·신뢰도·리스크 산출
         → 차트 생성 → LLM 해석 → 결과 검증
    ↓
Backend 저장 → Frontend 리포트
```

상위 **Top Supervisor**는 어떤 에이전트를 실행할지 결정합니다. technical agent 내부의 **Technical Supervisor**는 10개 노드의 순서를 조율합니다. 이름은 같지만 책임이 다른 두 계층입니다.

---

## 5. Top Supervisor

### 5.1 조건부 종목 식별

모든 질문에 종목 조회를 수행하지 않습니다. 질문 유형을 먼저 판별하고 특정 기업을 대상으로 할 때만 backend resolver를 호출합니다.

```python
QuestionKind = Literal["company", "industry", "market", "general"]

# "삼성전자 차트 어때?"      → company  → resolve 수행
# "2차전지 산업 전망은?"     → industry → resolve 생략
# "오늘 코스피 흐름 알려줘"  → market   → resolve 생략
```

| resolve 상태 | 의미 | 종목 의존 에이전트에 내려가는 사유 코드 |
|---|---|---|
| `resolved` | 종목 식별 성공 | `stock_resolved` — 실행 |
| `not_found` | 미상장·오타·미식별 | `stock_not_found` — 장애가 아닌 정상 상태 |
| `ambiguous` | 후보가 여러 개 | `stock_ambiguous` — 단일 확정 필요 |
| `not_attempted` | 비종목 질문이라 호출하지 않음 | `stock_not_resolved` |
| `error` | timeout·연결·5xx | `resolver_unavailable` — 일시적 도구 장애 |

상태(`ResolutionStatus`)와 사유 코드(`ReasonCode`)를 분리해, 프론트가 "종목이 없습니다"와 "잠시 후 다시 시도하세요"를 다르게 안내할 수 있게 했습니다.

### 5.2 실행 정책과 실패 격리

```text
Planning:  interpret → resolve → policy → rewrite → TaskEnvelope[5]
Execution: TaskEnvelope[5] → adapter 호출 → AgentResult[5]
```

- 실행 불가 작업은 `skipped`로 남기고 호출하지 않습니다.
- 한 에이전트의 예외는 `failed`로 격리해 나머지 분석을 계속합니다.
- LLM은 자연어 지시만 만들고 종목 코드는 resolver 결과에서만 주입합니다.
- LLM 호출·파싱 실패 시 에이전트별 결정론 템플릿으로 폴백합니다.

### 5.3 종목 정본 데이터 보호

정본 resolver가 찾지 못한 공시명·영문명·과거 사명은 요청 범위에서만 보조 조회합니다.

```text
ephemeral result → candidate 수집 → review → approve → canonical 반영
```

fallback 결과를 실시간으로 정본 DB에 쓰지 않아 잘못된 alias가 섞이는 것을 막았습니다.

---

## 6. 가격/기술적 분석 에이전트

### 6.1 LangGraph 10노드

| # | 노드 | 주체 | 역할 |
|---:|---|---|---|
| 1 | `normalize_question` | LLM | 질문을 안전한 분석 요청으로 정규화 |
| 2 | `focus_analysis` | LLM | 분석 초점과 의도 정리 |
| 3 | `data_collect` | 코드 | KIS 일·주·월봉 조회와 캐시 처리 |
| 4 | `indicator_calculate` | 코드 | MA·RSI·거래량·지지저항·패턴 계산 |
| 5 | `regime_classify` | 코드 | 일봉 국면과 상위 타임프레임 보정 |
| 6 | `signal_aggregate` | 코드 | 지표별 신호 가중 합산 |
| 7 | `confidence_calculate` | 코드 | 지표 일치도·거래량 확인 기반 신뢰도 산출 |
| 8 | `risk_detect` | 코드 | 과열·저항 근접·신호 충돌 등 리스크 탐지 |
| 9 | `chart_generate` | 코드 | 캔들·오버레이·annotation 생성 |
| 10 | `interpret_report` | LLM + 검증 | 확정값 설명 후 라벨 일치 검사 |

LLM은 1·2·10번 노드에서만 사용합니다. 나머지 7개 노드는 동일 입력에 동일 결과를 내는 결정론 코드입니다.

번호는 설계 문서상의 노드 번호이고, 실제 그래프에서는 **`regime_classify`가 gate로 먼저 실행**됩니다. 국면을 판정하지 못하면 지표 계산·신호 종합·신뢰도·리스크를 모두 건너뛰고 안전하게 종료하기 위해서입니다.

```text
data_collect → regime_classify → indicator_calculate → signal_aggregate
             → confidence_calculate → risk_detect → chart_generate → interpret_report
```

```text
technical_supervisor → technical_graph → pipeline_steps
```

흐름 제어와 계산을 단방향으로 분리해 순환 import를 제거하고, 계산 함수를 그래프와 독립적으로 테스트할 수 있게 했습니다.

### 6.2 멀티 타임프레임 국면 판정

| 타임프레임 | 역할 | 반영 범위 |
|---|---|---|
| 일봉 | 현재 신호와 1차 국면 | 5개 지표, `signal_score` |
| 주봉 | 중기 추세 맥락 | 추세 방향, 주요 지지·저항 |
| 월봉 | 장기 방향성 | 대세 추세 |

KIS에서 일·주·월봉을 각각 조회하고 일봉 국면을 상위 타임프레임 규칙으로 보정합니다. 최종 결과에는 `final_regime`과 타임프레임 정합성을 나타내는 `alignment_flag`를 함께 제공합니다.

```python
class Regime(str, Enum):
    UPTREND_INTACT         = "uptrend_intact"            # 상승 추세 유지
    OVERHEATED             = "overheated"                # 과열
    BULLISH_REVERSAL_WATCH = "bullish_reversal_watch"    # 상승 전환 관찰
    OVERSOLD_REBOUND_WATCH = "oversold_rebound_watch"    # 과매도 반등 관찰
    DOWNTREND              = "downtrend"                 # 하락 추세
    SIDEWAYS               = "sideways"                  # 횡보
    UNAVAILABLE            = "unavailable"               # 판단 불가
```

### 6.3 신호와 신뢰도 분리

`signal_score`는 방향과 세기, `confidence`는 결과의 신뢰도를 뜻합니다. 약하지만 일관된 신호와 강하지만 충돌이 큰 신호를 구분하기 위해 두 축을 나눴습니다.

```python
INDICATOR_WEIGHTS = {
    "moving_average": 0.30, "rsi": 0.20, "volume": 0.20,
    "support_resistance": 0.20, "pattern": 0.10,
}
CONFIDENCE_WEIGHTS = {
    "agreement": 0.40,        # 지표 간 일치도
    "volume_confirm": 0.20,   # 거래량 확인
    "trend_clarity": 0.20,    # 추세 명확성
    "conflict_absence": 0.20, # 충돌 신호 부재
}
```

일부 지표를 계산할 수 없으면 가능한 지표만 사용하고 가중치를 재정규화합니다. 누락 값을 임의로 채우지 않습니다.

### 6.4 차트 annotation

지지·저항, 박스권, 돌파 후보, 패턴 후보, 거래량 급증 구간을 코드로 탐지해 좌표와 함께 전달합니다. 컵앤핸들은 완성된 패턴으로 단정하지 않고 **후보 구간과 원본 앵커만 표시**합니다.

---

## 7. 신뢰성·복원력 설계

### 7.1 3단계 검증

```text
① 지표 계산값 검증
    ↓
② 계산값 → 국면 규칙 검증
    ↓
③ 코드가 확정한 국면 ↔ LLM 설명의 라벨 일치 검증
```

3차 검증은 LLM-as-judge가 아닌 키워드·라벨 사전으로 판정합니다. 대표 표현, 충돌 표현, 금지 문구, 출력 스키마, 확정값 재생성 여부를 모두 확인합니다.

```text
LLM 설명
├─ 검증 통과 → 사용
└─ 실패 → 확정 라벨을 주입해 1회 재생성
              ├─ 통과 → 사용
              └─ 실패 → 템플릿 문장 폴백
```

재생성은 1회로 제한하고 `verification` 필드로 검증·폴백 결과를 노출합니다.

### 7.2 KIS 장애와 데이터 부족

```text
KIS 조회 → 최대 3회 재시도(1/2/4초 백오프)
         → 실패한 타임프레임만 stale cache 조회
         → 캐시도 없으면 data_status로 부족 상태 명시
```

KIS의 호출당 100건 제한은 기간 청크 분할과 경계 중복·누락 검사로 처리했습니다. 일·주·월봉 실패를 독립적으로 흡수하므로 주봉이 실패해도 일봉이 있다면 제한된 분석을 계속합니다.

| 상황 | 응답 |
|---|---|
| 정상 | `data_status=normal` |
| 일부 데이터 부족 | `data_status=data_limited` |
| 분석 가능한 봉 부족 | `data_status=regime_unavailable` |
| stale cache 사용 | `data_status=stale_cache`, `source="KIS (stale)"` |
| 모든 시세 조회 실패 | 단독 API 502 / Supervisor 결과 `failed` |

### 7.3 관측과 민감정보 보호

- 노드별 실행 시간과 상태를 secret-safe JSONL trace로 기록
- API 키·토큰을 기록 시점에 redaction
- 예외 메시지는 개행 제거 후 300자로 제한하고 traceback·원문은 외부 응답에서 제외
- `request_id`, `report_id`, `trace_id`의 생성·저장 책임을 계층별로 분리

---

## 8. Backend · Frontend 연동

### Backend

- `technical_reports`와 signal·chart·interpretation·risk·verification·followup 자식 테이블 설계
- AI 응답 전용 Pydantic 계약으로 저장 전 스키마 검증
- `stocks`, `stock_aliases`, `stock_corp_codes` 종목 정본 관리
- KIS master와 DART corp code 동기화 경로 구현

종목명 정본은 backend가 소유하며 AI는 전달받은 `stock_name`을 소비만 합니다.

### Frontend

| 컴포넌트 | 역할 |
|---|---|
| `technical-hero` | 종목·국면·한 줄 요약 |
| `technical-trust-cards` | 데이터 상태·검증 결과·출처 |
| `indicator-card` | 지표별 신호·수치·해석 |
| `technical-chart-panel` | 캔들·오버레이·annotation |
| `technical-signal-risk-grid` | 종합 신호·신뢰도·리스크 |
| `technical-summary-sections` | 추세·신호·리스크·관찰점 |
| `technical-trace-drawer` | 실행 trace 확인 |

분석 결과뿐 아니라 데이터 상태와 검증 결과를 함께 배치해 리포트의 신뢰 근거를 확인할 수 있게 했습니다.

---

## 9. 기술 스택

| 분류 | 기술 |
|---|---|
| AI | Python 3.12, FastAPI, LangGraph, LangChain, OpenAI Responses API |
| 데이터 | 한국투자증권 KIS OpenAPI, DART, Pandas, NumPy |
| 저장 | PostgreSQL 16, SQLAlchemy, Alembic, Redis 7 |
| 계약·검증 | Pydantic v2, pytest |
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS v4, Recharts |
| 개발 환경 | uv, Docker Compose, Git, GitHub |

---

## 10. 프로젝트 구조

```text
ai/src/
├── supervisor/
│   ├── planning/              # 질문 해석·resolve·정책·지시 생성
│   ├── execution/             # agent 실행·adapter
│   ├── schemas.py             # 공통 typed 계약
│   └── runtime.py             # planning·execution 조립
├── agents/technical/
│   ├── supervisor/            # LangGraph·pipeline 조율
│   ├── nodes/                 # 10개 노드 adapter
│   ├── indicators/            # MA·RSI·거래량·지지저항·패턴
│   ├── regime/                # 국면·멀티 타임프레임 규칙
│   ├── synthesis/             # 점수·신뢰도·리스크
│   ├── charts/                # 차트·annotation
│   ├── services/              # KIS·Redis·OpenAI client
│   ├── observability/         # trace·라벨 검증
│   └── schemas/               # 입출력 계약·enum
└── api/                       # supervisor·technical endpoint

backend/                       # technical 리포트 저장·조회
frontend/src/features/technical/ # technical 리포트 UI
```

---

## 11. 실행 방법

> Git, Docker, uv, Node.js가 필요합니다. 환경 변수 파일과 `docker-compose.yml`은 저장소에 포함되어 있지 않습니다.

```bash
# 1. PostgreSQL · Redis
docker compose up -d

# 2. AI 서버 (:9000)
cd ai && uv sync
uv run uvicorn main:app --reload --port 9000

# 3. Backend (:8000)
cd backend && uv sync
uv run alembic upgrade head
uv run uvicorn src.api.main:app --reload --port 8000

# 4. Frontend (:3000)
cd frontend && npm install
npm run dev
```

### 담당 범위 테스트

```bash
cd ai
uv run pytest src/agents/technical/tests -q
uv run pytest src/supervisor/tests -q
```

fake resolver·adapter·LLM과 FastAPI dependency override를 사용합니다. 외부 API 상태 때문에 CI가 흔들리지 않도록 실 KIS·OpenAI 호출은 수동 smoke test로 분리했습니다.

---

## 12. 트러블슈팅

### 12.1 LLM이 확정 국면과 반대되는 문장을 생성

**문제**  
코드 결과가 `sideways`인데 LLM이 “상승 전환”이라고 설명하는 사례가 있었습니다. 프롬프트 지시만으로는 일관되게 막을 수 없었습니다.

**해결**  
라벨별 대표·충돌·금지 표현 사전을 만들고 문장을 결정론으로 검사했습니다. 실패하면 라벨을 주입해 한 번만 재생성하고 다시 실패하면 템플릿으로 대체했습니다.

**결과**  
“LLM에게 결정권을 주지 않는다”는 원칙을 테스트 가능한 코드로 보장했습니다.

### 12.2 KIS 100건 제한과 부분 장애

**문제**  
5년치 일봉 조회에는 페이징이 필요했고 청크 경계에서 중복·누락이 생길 수 있었습니다. 일부 타임프레임 실패가 전체 분석 실패로 이어지기도 했습니다.

**해결**  
기간을 최대 10개 청크로 나누고 경계 완전성을 검사했습니다. 재시도 후에도 실패하면 해당 타임프레임의 stale cache만 사용하도록 폴백을 분리했습니다.

**결과**  
일부 데이터가 없어도 가능한 범위에서 분석하며 stale 사용 여부와 데이터 제한을 명시합니다.

### 12.3 resolver와 technical 지원 범위 불일치

**문제**  
초기 technical agent는 2차전지 10종만 허용했지만 상위 resolver는 더 넓은 종목을 식별했습니다.

**해결**  
고정 membership gate를 제거하고 6자리 종목 코드를 입력 계약으로 삼았습니다. 종목명은 backend에서 주입하고 데이터 확보 여부는 `data_status`로 표현했습니다.

**결과**  
계획 단계와 technical 지원 범위를 분리했습니다. 기존 대표 종목의 real smoke는 완료했으며 전체 종목 검증은 stock seed 확장 이후 과제로 남겼습니다.

### 12.4 그래프와 계산 로직의 결합

**문제**  
Supervisor에 흐름 제어와 계산이 섞여 LangGraph 도입 시 순환 import와 중복 테스트가 발생했습니다.

**해결**  
`technical_supervisor → technical_graph → pipeline_steps` 단방향 의존으로 재구성하고 각 노드를 계산 helper를 호출하는 얇은 adapter로 만들었습니다.

**결과**  
계산·판정·출력 계약을 유지한 채 실행 흐름만 교체하고 계산 로직을 독립적으로 검증할 수 있게 됐습니다.

---

## 13. 회고

이 프로젝트에서 중요하게 본 것은 **LLM을 얼마나 많이 쓰는가가 아니라 어디까지 맡길 것인가**였습니다. 금융 데이터의 수치와 판단은 코드가 확정하고 LLM은 사용자가 이해할 수 있는 언어로 변환하도록 역할을 제한했습니다. 여기에 출력 검증과 유한한 폴백을 더해 신뢰성 원칙을 실제 코드로 만들었습니다.

또한 데이터가 없을 때 억지로 답을 만들지 않고 stale cache와 분석 불가 상태를 그대로 노출했습니다. 분석 서비스에서는 화려한 문장보다 **모르는 것을 모른다고 표현하는 능력**이 더 중요하다는 점을 배웠습니다.

마지막으로 Supervisor, adapter, AI, backend 정본 데이터의 소유권을 분리하며 계층 경계의 중요성을 체감했습니다. 명시적인 계약과 단방향 의존은 기능 구현만큼 중요한 결과물이었습니다.

---

## 14. 고도화 방향

1. **에이전트 실행 병렬화** — 순차 fan-out을 병렬화하고 전체 deadline과 호출별 timeout을 함께 관리합니다.
2. **검증 사전 반자동 확장** — 재생성·폴백 사례에서 누락 표현 후보를 모아 검토·승인 후 반영합니다.
3. **전체 종목 real smoke 확대** — 업종별 대표 종목을 검증하고 데이터 상태 분포를 측정합니다.
4. **장중 데이터 정식 지원** — feature flag로 격리한 분봉 분석과 별도의 단기 국면 모델을 검토합니다.
