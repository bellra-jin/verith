# CF053 · Technical 단일 start와 요청별 graph/usage

착수 정본 v1.0 SHA256 `2379cf3c4af67c8e2374dd0630415c024aba5d54daf456d1a5300219d8820c29`.
최종 정본 v1.1 SHA256 `74d5255e9ad4641f2ff46bcfcecd1fe2d0bcebfbfb237c2edec015e16de88477`에서
기존 CF035 회귀1파일을 추가 허용했다(허용 최대37경로).
기준 develop `4b2436cc1934d2b045e1f9f5f67e91a6dde20ff6`, 별도
`feat/technical-provider-execution` / `verith-technical-provider-execution`에서 구현했다.
게시/정상 merge 승인 마감은 2026-11-13 01:00 UTC다. PR61은 HOLD이며 준영 PR은 대리 변경/merge하지 않는다.

## 제품 결과

새 provider-spec 접수의 readiness→같은 claim/grant→인증된 SQL 단일 start의 fresh winner ACK→
요청별 CF051 budget/bundle을 공유하는 실제 graph/Bridge→독립 usage 관측과 CF050/CF035 저장을 연결했다.
기본 off, 정책 숫자/가격 기본값 없음, 옛 spec/동일 key 승격 없음, 원 기한/hold/IDs 유지다.
per-pair SQL RPC·재시작/다른 worker 승계·새 원장·정산/환급·public launch는 추가하지 않았다.
controlled 내부 복원과 공개 synthetic 조회를 분리하며 새 공개 detail은404다.

필수 원본만 변경했다. 조건부 추가 허용은 `backend/tests/unit/test_cf035_technical_owned_storage.py`
1개다. c350 migration CHECK와 현재 확장 model을 동일 비교하던 회귀를, 옛 bytes/hash/기존 synthetic
CHECK와 새 c530의 정확 model CHECK를 각각 검증하도록 변경했다. 과거 migration은 그대로다.
Frontend·News·준영 AI·guard/worker·CI/lock/package는 변경하지 않았다.

## 검증 범위와 현재 기록

- 보호 admission/runtime unit과 직접 영향 CF035/CF036, graph self/unit을 사용한다. raw pytest나 보호 해제는 없다.
- 실제 compiled graph + 가짜 SDK/HTTP/OHLCV는 별도 승인64-wheel site에서 검증한다. 실제 CF051 정의를
  기존 AST collector로 실행하고 openai/SQL/다른 AI import 차단을 유지한다. graph와 PG site를 합치지 않는다.
- 기존 `--verify-technical-completion-db`는 owned proof/제한 role/같은 연결 migration/정확 source copy·
  전후 provenance/자가 cleanup을 유지한다. 실제 SQL와 production client/AI route/callback/runtime,
  명시 synthetic runner를 사용한 ASGI 검증이며, 이 PG 회차 자체가 actual compiled graph 증거는 아니다.
- 최종 PG12는 28그룹 통과. old baseline16 + CF05312로, 새 revision DDL rollback·normal stored/A2/public 제외,
  잘못된 결과와 독립 usage·실제 두 SQL start 승자1·first fresh start/claim/observe commit ACK 손실,
  원 기한 뒤/철회 후 record-only 관측·SQL 타입/metadata/once/삭제·populated downgrade를 확인했다.
  ACK 손실은 실제 PG commit 뒤 wrapper simulation이며 실제 네트워크 단절이라고 표현하지 않는다.
- 최종 보호 검사: admission self5/unit279, runtime self5/unit236, boundary self3/unit208,
  owned storage unit72·owned read unit47, graph self2/unit22 통과·guard 위반0.
  graph22건은 실제 compiled graph와 가짜 SDK/OHLCV의 로컬 결과이며 원격 CI의 graph self와 구분한다.
  64개 설치 버전/의존성 snapshot 전후 불변은 매 회 wheel 원본의 암호학적 재검증이라는 뜻이 아니다.
  최종 PG12의 정확 소유 DB/source copy 제거와 source/dependency/origin postcheck를 확인했다.
- 최종 검증/게시 SHA 및 exact-head CI 결과는 완료 시 아래에 추가한다. 원 실행 로그·각 실패 회차와
  manifest는 private checkpoint에 별도 보존하며 공개하지 않는다.

## 실패 이력과 정리 구분

PG1은 asyncpg의 다중 CREATE FUNCTION 한 명령 문제, PG2–3은 새 SQL 변수/alias 충돌,
PG5–6은 JSON literal의 `:true/:false`가 SQLAlchemy text bind로 해석되는 새 spec CHECK 문제였다.
정확 canonical bytes의 hex decode와 compiler/SQL 회귀로 보완했다. PG7–8은 영문 chart 합성 질의와
기존 엄격한 planner의 불일치였다. planner를 완화하지 않고 지원 질의 및 start/credential 이전 검증으로
맞췄다. PG9의 관측 실패는 SQL object key 순서의 locale 의존성을 C collation으로 고정해 해결했다.
이 회차는 실제 공급자/키0이며 성공한 것처럼 바꾸지 않는다.

PG4는 환경 연결 전환으로 terminal/parent postcheck 없이 중단됐다. PID 부재, 원 creation receipt의
정확 CID/생성시각/resource label/mount0와 동결 source manifest를 독립 대조한 뒤 자기 컨테이너와
source copy만 제거·부재 확인했다. 정상 완료로 집계하지 않고 interruption/cleanup 기록을 분리 보존했다.
나머지 실패 및 통과 회차도 owned DB/source copy 정리와 provenance 결과를 각각 남긴다.

## 한계

실제 OpenAI/KIS 호출·key/.env 파일 읽기·새 설치·운영 활성화/DB 변경은0이다. 실제 SDK HTTP/TLS,
키 유효성·시장자료/횟수·청구 확정·settlement/hold 반환·전체 AI main/uvicorn startup·Supervisor 확정
Technical dispatch·운영 배포와 사용자 화면은 미검증/미완료다. 비밀 아닌 자동 trace flag 확인과
가짜 unit worker 설정은 실제 서비스 환경파일 읽기/변경과 구분한다. 기존 Supervisor $0.50 hold와
모든 실제 소비/동결 기록, 메인/다른 worktree의 WIP를 보존한다.
