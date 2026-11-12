# CF048 · Technical 실행 접수와 비용 보류

기준 develop `36f49d97ad2bcbc9c59204146b4cc044aff3656f`, 전용 `feat/technical-execution-admission`. CF048 v1.2의 정확 15파일 범위다. 기존 사용자 WIP·Flow 원장·Supervisor 보수 예약 $0.50·실제 소비 기록과 PR61 HOLD를 보존한다.

## 제품 결과

Technical 전용 run/일일 period 두 SQL 표와 미등록 내부 서비스가 실제 Principal/Stock 확인, 같은 key 재요청, 원자 예약, 최초 ACK 뒤 private token, 원 admission 세션의 단일 로컬 claim, unknown/redaction·hold를 구현한다. SQL trigger/FK는 identity·period-policy·예약/기한 상한·단방향 전이·삭제 금지와 commit 최종 합계를 강제한다. 운영 수치 기본값은 없으며 명시 정책 없이는 신규 접수/claim이 닫힌다.

독립 검토에서 저장 policy보다 긴 run 기한을 직접 INSERT할 수 있는 누락을 발견해 DB guard와 저장 receipt 검사에 같은 상한을 추가했다. 해당 PG 음성은 fresh DB 시각으로 만들고 deferred 합계 검사 전에 flush 자체의 거절을 요구해 다른 제약으로 가려지지 않게 했다.

## 직접 검증

- 기존 보호 `technical-admission-self`: 3개 통과. `technical-admission-unit`: 최종 172개 통과, guard 0. 신규 CI 고정 두 step은 같은 clean env와 기존 worker/guard를 사용한다.
- 기존 소유 DB 부모의 `--verify-technical-admission-db`: 실제 일회용 Verith PG 11그룹 통과. migration 빈 downgrade/동일 연결 DDL rollback, 실제 두 SQL 세션의 접수·claim 승자1, A2 조회/타인·원 세션 차단, SQL identity/정책/deadline/카운터/삭제 거절, ACK 유실·취소, caller-known key의 dirty-session readonly 복구, DB clock 만료·실제 redaction/hold, 철회·원 session 정리 후 owner RESTRICT, 사용자/서비스·예산 경합, populated downgrade 보존을 확인했다.
- PG 합성 정책의 마지막 서비스 횟수와 최대 예약 금액 경계는 같은 시점에 도달한다. 이 실제 경합은 공통 잠금과 두 SQL 불변식을 증명하며, 각 서비스/금액 조건의 독립 분기는 단위검사로 구분한다.
- ACK 손실은 실제 PG commit 전후 wrapper simulation이다. 실제 provider/네트워크 ACK 유실 실험이 아니다. 만료 삭제는 get 호출 시 확인했고 운영 sweeper는 없다.
- PG 입력 소스 265개/AI 순수 호환 pin 6개를 전후 대조했고, 원본/사본·dependency·module origin postcheck와 소유 DB/소스 사본 cleanup이 통과했다. 공급자·실제 자격 읽기는 0이다.

초기 unit의 170개 assertion은 통과했지만 기존 worker의 Flow origin sentinel이 없어서 최종 수용이 실패했다. guard를 유지하고 기존 정확 6개 순수 파일 loader를 적용한 뒤 재검증했다. 이 실패를 통과 기록으로 바꾸지 않았다. PG는 첫 실제 회차에서 통과했다.

## 남은 경계

내부 SQL 예약과 로컬 claim은 provider 송신 권위·정산이 아니다. 실제 운영 가격/한도·request-local LLM call/token/금액 강제·공통 coordinator Technical profile·엔진/저장 연결·Supervisor 확정 dispatch·public 실행과 실제 공급자 인수는 미완료다. Flow 회계나 시험 epoch를 Technical 정책으로 복사하지 않았다. 원격 CI의 정확 head 결과와 PR/merge는 게시 시 별도 확인한다.
