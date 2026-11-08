# 현재 책임과 데이터 접근 경계

기준 `a5b60f2fd0b00efedae2c98a2004ede62470b094` / 2026-11-07, Asia/Seoul (+09:00).
정적 코드 대조이며 앱·DB·외부 인증·AI·권한을 이번에 실행/검증하지 않았다.
[문서 권위/검증 상태](../documentation.md), [공유 인증 계약](../contracts/CF-002-v0.6.shared-v1.md)을 따른다.
이 설명은 현재 책임 지도이며 코드 이동 지시가 아니다. 경로는 ST-001 v1.10의 적용된 이동까지 반영했고, 책임/권한 기준이나 과거 실제 검증을 새로 통과한 것으로 갱신하지 않았다.

## 현재 공개 경로와 데이터 책임

| 영역 | 현재 entry / 책임 | 허용 경계·제외 |
|---|---|---|
| Next App Router | [src/app](../../frontend/src/app), [session BFF](../../frontend/src/shared/server/session-proxy.ts), [SSR 전달](../../frontend/src/shared/server/session-backend.ts) | 동일 origin 세션 전달·화면·no-store. raw 중복 Cookie를 임의 축약하지 않음. owner/검증 결과를 공개 입력으로 받지 않음 |
| FastAPI Backend | [src/api/main.py](../../backend/src/api/main.py), [access_boundary](../../backend/src/shared/http/access_boundary.py), [auth](../../backend/src/modules/auth/api/router.py) | health·종목 resolver·auth 진입을 허용하고 본인 Flow GET/개별 DELETE·공통 목록을 최종 인증/owner 검사. 공개 save·전체 삭제·다른 관점/News 관리·직접 AI proxy는 차단 |
| Flow 저장/조회 | [service](../../backend/src/modules/flow/application/report_service.py), [repository](../../backend/src/modules/flow/infrastructure/report_repository.py) | 원본 AI ID/v1 JSON 유지, 검증된 내부 principal 저장, root owner+정확히 1 index owner를 SQL로 검사. legacy owner NULL 자동 배정 없음 |
| DB 모델/migration | [models](../../backend/db/models), [migrations](../../backend/db/migrations), [schema](../../backend/docs/schema.md) | Backend 소유. auth/root-owner 확장·common 외부 UUID 보존. 기존 데이터 자동 보정/동기화·권한 부여 없음 |
| AI FastAPI | [src/main.py](../../ai/src/main.py), [src/api](../../ai/src/api) | 분석·순수 계산/export 책임. 코드/라우터 존재가 현재 공개 분석 실행 허용이나 운영 서비스 인증 완료를 뜻하지 않음 |
| 종목 관리 | [resolver](../../backend/src/modules/stocks/api/router.py), [master sync](../../backend/docs/stock_master_sync.md), [corp-code sync](../../backend/docs/dart_corp_code_sync.md) | resolver는 식별 응답. KIS/DART 관리 sync는 별도 수동/네트워크·DB 변경 작업이며 기본 사용자 요청 흐름과 다름 |

현재 Frontend 3200/Backend 8200/AI 9200과 데이터 host port는 [포트 문서](../local_ports.md)에 있다.
기존 container 내부 포트·서비스명과 host 주소를 혼동하지 않는다. AI를 직접 공개해도 안전하다는
증거는 없고, Backend→AI 서비스 인증/가짜 AI 공통 접수·worker·예산·복구는 후속이다.
개별 삭제 검증은 늦은 worker 재게시 방지 서비스 완료가 아니다.

## Fundamental 직접 DB 호환 경로

현재 [corp_code.py의 _backend_lookup](../../ai/src/agents/fundamental/infrastructure/data/corp_code.py)는 psycopg로
stock_corp_codes의 **stock_code/corp_code/corp_name_from_dart**를 stock_code parameter로
SELECT와 LIMIT 1을 사용한다. [config](../../ai/src/agents/fundamental/core/config.py)는 VERITH_DB_URL을
우선하고 DATABASE_URL alias를 수용하며 import 시 AI dotenv source를 읽는다.
asyncpg scheme을 psycopg용으로 정규화하는 기존 호환 동작도 있다.

기존 timeout/retry·프로세스 cache와 static fallback/source·CORP_CODE_FALLBACK_STATIC 표시는
그대로 둔다. lookup 실패 뒤 static fallback이 있다는 사실을 최신 정본 DB 조회 성공으로
표현하지 않는다. [기존 Supervisor 계약](../../ai/docs/agents/fundamental/07_SUPERVISOR_CONTRACT.md)의
기술 부채와 함께 읽는다.

**SELECT만 쓰는 코드와 실제 자격이 SELECT-only라는 보장은 다르다.** 연결 role의 최소 권한·
실제 DB/자격/네트워크는 미확인이다. private env나 기존 DB에 접속해 확인하지 않았다.
이 문서는 공유 종목 마스터 lookup의 현재 호환 경로를 설명할 뿐, 앱 credential 복사나 실제
직접 연결을 새로 허가하지 않는다. 사용자 report·auth/session/owner 조회·write/DDL·master sync·
AI에서 owner 결정으로 확대하지 않는다.

실제 Fundamental 연결 전 전용 최소 read-only role·허용 table/필드·timeout·오류/fallback 출처와
자격 분리를 별도 검증해야 한다. 새 테스트 준비는 fake connection/합성 설정으로 한정한다.
현재 [stock resolver 응답](../../backend/src/modules/stocks/api/schemas.py)에는 corp_code가 없으므로
`POST /api/stocks/resolve`로 기계 교체하지 않는다. Backend 서비스 인증을 갖춘 corp-code 소비
API의 path/schema·not-found/unavailable·fallback/cache는 별도 확정 계약 후 구현한다.

## DB 검사와 실행 안전

[DB guard](../../backend/tests/db_safety.py)는 앱 fallback 없이 승인된 별도 일회용 자원·주소·
제한 역할을 확인하고 readonly preflight 뒤 동일 검증 연결로 migration해야 한다.
[runner 소유 증명](../../backend/scripts/runner_owned_database.py)은 현재 직접 생성한 local 자원의
엄격한 영수증 경로이며 기존 container 채택·일반 guard skip이 아니다.
[DB 경계 문서](../../backend/docs/db_boundaries.md)의 같은 서버에 여러 DB를 만들던 표는 과거
운영 기록이다. 지금 테스트 격리를 충족하는 준비 명령으로 재사용하지 않는다.

단위/합성 HTTP·실제 PG·실제 Google/사용자 UI·실제 AI의 증거를 나눠 보고한다.
과거 실행 승인·로그인 자격을 이번 문서 작업이나 clone의 새 실행 허가로 승계하지 않는다.
.env·credentials·ignored Docker-compose.yml·기존 컨테이너/volume는 읽거나 변경하지 않는다.

## 구조 개선 후보와 후속 단계

Technical 차트·Flow 표시·Technical projection 등 큰 파일은 책임 분리 후보일 뿐이다.
폴더 이동/목표 계층은 비교 판단과 새 확정 지시 전 보류한다. 파일 행수만으로 이동하지 않는다.
후속 추출은 기존 export/route·payload/API·transaction/SQL·인증 책임을 보존하는 작은 단위와
선행 회귀가 필요하다. 다음 AGENTS/환경 예제/안전 검사 진입점 단계도 선행 검토·사용자 병합 후
별도 브랜치로 진행하며 이 1단계에 구현하지 않는다.
