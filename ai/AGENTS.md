# AI 서비스 작업 안내

[상위 공통 안내](../AGENTS.md)·[문서 권위](../docs/documentation.md)와 해당 agent의 기존 로컬
지침을 읽는다. 예를 들어 News 범위에는 [기존 CLAUDE](src/agents/news/CLAUDE.md)가 있다.
이 안내는 현재 구조/예외를 설명하며 코드 이동·외부 모델 실행·새 DB 권한 부여 지시가 아니다.

## 실제 entry와 config

FastAPI app은 [src/main.py](src/main.py)이며 [src/api](src/api)의 Technical/Supervisor/
Fundamental/Industry router를 등록한다. 등록된 route가 현재 사용자에게 공개된 기능이라는 뜻은 아니다.
설정은 소스를 읽어 확인하며 다음 module을 import해 private 값을 검사하지 않는다.

| 영역 | 실제 config |
|---|---|
| Supervisor | [src/supervisor/config.py](src/supervisor/config.py) |
| Technical | [src/agents/technical/config.py](src/agents/technical/config.py) |
| Flow | [src/agents/flow/config.py](src/agents/flow/config.py) |
| Fundamental | [src/agents/fundamental/core/config.py](src/agents/fundamental/core/config.py) |
| Industry | [src/agents/industry/config.py](src/agents/industry/config.py) |
| News | [src/agents/news/config.py](src/agents/news/config.py) |

AI는 분석/계산·자료 의미/검증·결과 export를 맡는다. 사용자 principal/owner·앱 세션·DB
저장/조회/삭제의 최종 책임은 Backend다. 분석 결과 ID·숫자·기간·단위·null/0을 바꾸거나
저장을 위해 분석을 재호출하지 않는다. Flow는 [CF-001](../docs/contracts/CF-001-v1.1.shared-v1.md),
인증/공개 차단은 [CF-002](../docs/contracts/CF-002-v0.6.shared-v1.md),
도메인 계약/현재 책임은 [목록](../docs/documentation.md)·[지도](../docs/architecture/current-boundaries.md)를 따른다.
현재 공개 save·전체 삭제·직접 AI proxy 차단과 Backend root/index owner 검증을 우회하지 않는다.
AI가 사용자 owner를 정하거나 외부 token을 앱 세션으로 대신 쓰지 않는다.

## Fundamental 직접 DB의 한정된 호환 사실

[corp_code.py](src/agents/fundamental/data/corp_code.py)는 stock_corp_codes의 stock_code/
corp_code/corp_name_from_dart를 parameterized SELECT로 조회한다. config는 VERITH_DB_URL 우선과
DATABASE_URL alias를 수용한다. 이 구현을 보존하되 앱 credential을 AI로 복사하라는 안내를 만들지 않는다.
코드가 SELECT라는 사실과 실제 role의 SELECT-only 권한은 다르며 **실제 최소 권한은 미확인**이다.
현재 timeout/retry/cache·static fallback/source·risk flag도 변경하지 않는다.
사용자 report/auth/session/owner 접근·write/DDL·master sync로 확대하지 않는다.
실제 연결 전 전용 최소 권한·자격 분리와 서비스 인증을 갖춘 API 소비 계약이 별도로 필요하다.
현재 종목 resolver 응답에는 corp_code가 없으므로 기계 교체하지 않는다.

## 검사/실행 위험과 후속

- 의존성 선언은 [pyproject.toml](pyproject.toml)·[uv.lock](uv.lock)이다. 현재 설치 상태를 임의로
  바꾸거나 전역 업그레이드하지 않는다. module import나 CLI help도 안전하다고 가정하지 않는다.
- Fundamental config는 import 시 AI dotenv source를 읽고 다른 module은 HTTP/DB·LLM/
  모델 로딩/다운로드를 시작할 수 있다. parent env만 지워 전체 AI pytest를 실행해도 안전한 것이 아니다.
- `.env`·credentials·실제 DB/graph/cache·Google/AI endpoint·모델을 검사 입력으로 사용하지 않는다.
  승인된 별도 검사에서는 선택한 순수/합성 대상의 **수집 전** 파일/네트워크/DB/모델 부작용 차단을
  먼저 입증해야 한다. fake corp-code connection/설정·fallback/cache 검사와 실제 DART/DB 검증을 구분한다.
- 3-C AI 안전 entry와 3-A 공용 환경 예제는 **미구현 후속**이다. 아직 없는 script/명령을 안내하거나
  전체 pytest/실제 수집·smoke를 기본 시작 절차로 실행하지 않는다. 3-B도 별도 선행 단계다.
- 현재 문서 단계는 기능·unit/build/lint·AI/DB/Google/Docker 검사를 실행하지 않는다.
  과거 검사 보고와 이번 직접 검사를 구분하고 실제 인증 미검증/기존 lint 실패를 숨기지 않는다.
큰 파일·agent 폴더 구조 분리는 비교 판단 전 보류하며 현재 branch에서 후속 구현을 누적하지 않는다.
