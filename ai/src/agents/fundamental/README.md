# Fundamental Agent

`ai/src/agents/fundamental`은 veriθ 멀티에이전트 중 재무·펀더멘털 워커입니다. DART 공시를 수집하고, 결정론 코드로 재무 지표·점수·라벨을 산출한 뒤, LLM은 그 결과를 해석 문장으로만 정리합니다. 최종 산출의 주 계약은 `FundamentalResponse` JSON이며, `report_html`은 로컬 검수와 디버그를 위한 부가 산출물입니다. 데이터가 부족하면 추정하지 않고 `insufficient_data` 응답으로 닫습니다.

## 문서 맵

| 문서 | 내용 |
| --- | --- |
| [01_OVERVIEW.md](../../../docs/agents/fundamental/01_OVERVIEW.md) | 폴더의 의미, 책임 범위, 결정론/LLM 경계 |
| [02_ARCHITECTURE_NODES.md](../../../docs/agents/fundamental/02_ARCHITECTURE_NODES.md) | LangGraph 워크플로와 노드별 역할 |
| [03_DATA_CONTRACT.md](../../../docs/agents/fundamental/03_DATA_CONTRACT.md) | `FundamentalResponse`, `erd_payload`, 프론트 JSON 계약 |
| [04_VERIFICATION_POLICY.md](../../../docs/agents/fundamental/04_VERIFICATION_POLICY.md) | 검증 게이트, verdict guard, risk flags |
| [05_MERGE_GUIDE.md](../../../docs/agents/fundamental/05_MERGE_GUIDE.md) | develop 머지 전 확인 사항과 커밋 포함 대상 |
| [06_DEV_GUIDE.md](../../../docs/agents/fundamental/06_DEV_GUIDE.md) | 로컬 실행, 테스트, HTML preview 생성법 |
| [07_SUPERVISOR_CONTRACT.md](../../../docs/agents/fundamental/07_SUPERVISOR_CONTRACT.md) | 공개 입력 계약, Supervisor 연결, insufficient_data 정책, ERD 크로스체크, corp_code 후속 debt |

## 빠른 시작

```bat
cd /d C:\verith\ai
C:\verith\.venv\Scripts\python.exe -m pytest tests\fundamental -q
C:\verith\.venv\Scripts\python.exe -m scripts.fundamental.batch_demo
```

실행 옵션과 preview 생성법은 위 문서 맵의 `06_DEV_GUIDE.md`를 참고하세요.


## CF-002 v0.5 로컬 연결 안내

AI FastAPI 실행 주소는 `http://localhost:9200` (`uv run uvicorn src.main:app --reload --port 9200`, ai 루트),
Backend resolver/HTTP 경계는 `BACKEND_BASE_URL=http://localhost:8200`이다.
Backend의 `AI_SERVICE_URL` 안내도 9200이다. News는 계속 Backend HTTP로만 DB에 접근한다.
Fundamental의 `VERITH_DB_URL`/`DATABASE_URL`은 기존 소비자 드라이버 규약을 유지하며
host 포트15432만 사용한다. 예: `postgresql://<user>:<password>@localhost:15432/<database>`.
Industry의 host `NEO4J_URI=bolt://localhost:17687` (HTTP UI 17474), Technical의 선택적
host cache는 `REDIS_URL=redis://localhost:16379/0`이다. REDIS_URL 미설정은 계속 cache 비활성이다.
Compose 내부는 postgres:5432·redis:6379·neo4j:7687을 유지한다. 추론용 8001/v1이나 외부
모델 서버 주소는 AI FastAPI 서비스 포트가 아니므로 바꾸지 않는다.
기존 private 환경값은 미확인이다. 이 안내는 실제 AI/DB/Redis/Neo4j 기동·호출·계정 설정을
실행했다는 뜻이 아니며, CF-002 사용자 경로의 새 분석/저장 차단은 그대로다.
