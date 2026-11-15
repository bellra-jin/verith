# Supervisor Flow/Technical 내부 조합 기반

기준 develop `3fc132ec42999e957c19385feccb42ec6ffa4ddb`에서 별도 작업공간으로 진행했다.
[계약](../contracts/supervisor-composition-v1.md)의 첫 내부 단위이며 완전한 복수 실행 완료가 아니다.

- 고정 owner/원 확인 세션/client key/scope/consent/독립 정책의 영속 접수와 replay 관찰을 구현했다.
- 실제 Stock resolver로 양의 언급과 부정 별칭을 재검증한다. 초기 범위는 완전히 해소된 조건 없는
  단일 종목이며, 조건·복수 종목·미해결 의미를 잘라내 실행하지 않는다.
- 서버의 private identity seed로 자식 key를 고정한다. 토큰/seed/key는 상태 응답에 내보내지 않는다.
- 이번 invocation의 commit ACK만 시작/인계권을 준다. ACK 불명·재시작·다른 세션은 권한을 복구하지 않는다.
  원 15초 접수/인계와 140초 총 기한은 갱신하지 않는다. close의 첫 await 전에 미소비 인계권을 닫는다.
- native 접수 ACK/결과의 고정 참조를 검증하고, Technical 접수의 as-of를 두 관점의 시점으로 연결한다.
  원 Flow/Technical 원장을 재사용하며 공통 비용 원장을 만들거나 hold를 해제하지 않는다.
- 새 owner 세션 조회에서도 stored/unknown/미시작을 각각 보존한다. 조회는 native POST·예약·게시를 하지 않는다.
  기한 후 조회는 부모를 영속 close한다. 취소는 즉시 전파하며 caller 소유 세션 문맥이 잠금을 정리한다.

## 직접 검증

- 기존 보호 core self 3 / unit 120, Technical admission unit 283 통과, guard 위반 0.
- 기존 Verith 소유 `--verify-technical-completion-db`: 기존 39 + 새 조합 7 = 46그룹 통과 및 자기 DB 제거.
  실제 SQL 세션/인증 A1·A2·타인, start/handoff 경합, 실제 commit 뒤 ACK 유실 wrapper,
  stored+unknown 부분 결과와 새 DB 세션 조회, 철회, 취소 후 auth/root 잠금 해제, 만료 close,
  타인 child 연결·redaction NULL→참조 추가·DELETE/TRUNCATE·populated downgrade 거절을 확인했다.
- 자식 fixture는 기존 native 접수/start/receive/writer와 명시 합성 실패를 검사에서 직접 호출한다.
  이 조합 서비스가 두 엔진/compiled graph를 실행했다는 증거가 아니다. 실제 공급자 호출 0.
- 첫 PG 회차는 asyncpg의 복수 함수 DDL 한 execute로 중단되어 함수별 DDL로 나눴다. 다음 회차는
  새 fixture의 원문 checksum을 canonical checksum으로 정정했다. 세 번째 회차의 추가 AI fixture
  결과는 stored가 아니어서 중단했으며, 새 범위의 필요한 저장 fixture를 기존 SQL 수신/저장으로
  직접 구성했다. 실패 로그와 매 회 소유 DB 정리 기록을 보존했다. 검사를 skip하거나 제품 보호를 낮추지 않았다.
- PG 종료 후 migration의 CHECKS/GUARD literal 표기만 정리했다. 검사 전 고정 SQL 파일과 현재
  SQL 문자열의 일치 및 이전 표기와의 정규화 AST 동일성을 대조했다. 과거 exact byte hash의 독립
  캡처와는 구분한다. 이후 추가한 늦은 Flow 결과 연결 1건까지 최종 core 120이 통과했다.
- 최종 13파일이며 제품/SQL·검사·문서만 포함한다. private 실행/인증/예약 자료는 게시하지 않는다.

## 후속

공개 복수 실행 planner/API 및 native 직렬 dispatch는 미연결이다. Technical 접수 ACK·분석시점 확정과
두 자식 접수·인계는 15초 안에 구분하여 조립해야 한다. Flow POST의 접수/실행 결합을 후속에서
해결하며 Technical 모델 실행 후 Flow 접수를 약속하거나 원 기한을 늘리지 않는다.
새 provider/키/env/설치/운영/다른 DB·프로젝트 작업은 없고, 기존 실제 자료와 $1.30 보수 hold는 불변이다.
