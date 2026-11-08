# Flow 내부 fake 일회 실행과 결과 저장

CF-007은 기존 receipt와 봉인 입력에 명시적으로 opt-in한 사용자를 위해 합성 결과를 한 번 실행·저장·재조회하는 내부 경로다. `FakeExecutionService.execute_once(run_id, *, allow_fake)`는 실제 bool True만 받는다. `get(run_id)`은 엔진을 실행하지 않는다. 공개 endpoint/BFF/UI·기존 리포트/보관함 게시·실제 KIS/AI 호출은 없다.

## 단일 실행권과 결과

새 `flow_fake_executions`는 input당 한 행이다. execution→input snapshot→run owner JOIN과 실제 principal/session 재검증을 사용한다. 기존 receipt의 `receipt_only/pending/not_stored`, 예약 attempt UUID와 preparation의 executable=false는 변경하지 않는다. 새 행은 고정 `flow.fake.summary.v1`에만 쓰는 별도 일회권이며 token 원문은 호출자 메모리, DB에는 SHA-256만 둔다. 조회/보고에 token/digest를 노출하지 않는다.

claim은 session SHARE→owner run FOR UPDATE→저장 input 검증→execution 조회/정확 input UNIQUE INSERT→commit이다. 최초 INSERT 승자가 commit 성공을 확인한 때만 DB 잠금 밖에서 순수 coroutine을 호출한다. grant 이후 crash/ACK 유실이면 호출0일 수 있다. 최대1을 보장하며 exactly-once 완료·takeover·실행권 갱신은 제공하지 않는다. 기존 행의 replay는 상태/결과만 반환한다.

엔진은 최대20개 봉인된 합성 달력 행의 개인/외국인/기관 주수·거래대금 합계, 행수·날짜·단위와 합성 안내를 만든다. 4행은 짧은 합성 표본이며 20일 지속성 결론을 만들지 않는다. 결과는 input ID/hash·최초 reference·ticker/as_of·execution ID와 결합한 내부 canonical UTF-8 TEXT(최대128KiB)/SHA다. Flow payload v1/report ID나 실제 관측 시각·Gate 판정을 생성하지 않는다. reader는 저장본과 고정 v1 관계를 검증하며 현재 engine binding을 호출해 대체하지 않는다. body는 매번 독립 파싱한다.

## 기한·terminal·복구 한계

INSERT의 DB clock_timestamp 한 샘플부터 deadline은10초, 순수 coroutine의 wait_for는1초다. CPU 강제 중단이나 모든 DB 연결의10초 이내 종료를 약속하지 않는다. 상태는 running/succeeded/failed/timed_out이다. succeeded만 검증된 결과를 가지며 실패는 고정 오류와 결과NULL이다.

terminal도 session SHARE→run→input 검증→execution FOR UPDATE 순서다. id/input/claim digest와 running을 확인하고, DB 기한 전 후보만 결과/상태/hash/종료시각을 한 commit에 확정한다. 기한 후는 후보를 버리고 deadline_expired timed_out만 확정한다. 내부 owner get은 같은 잠금과 DB deadline으로 만료만 확정할 수 있다. 세션이 폐기됐으면 terminal·반환을 거부하며 다른 유효 본인 세션은 조회/만료 처리만 할 수 있다.

commit 성공 확인 전에는 성공을 반환하지 않는다. grant ACK 유실은 엔진 호출0, terminal ACK 유실은 owner 조회로 저장 결과를 확인한다. 확정 rollback·DB 결과 불명확을 구분한다. terminal rollback으로 candidate를 잃어도 엔진을 다시 호출하거나 다른 요청이 재생성하지 않는다. 자동 저장 retry/프로세스 재시작 복구는 후속이다.

## 물리 제약·migration

`c7001a7e0001`(parent c6001)은 새 테이블만 추가한다. input FK/RESTRICT·UNIQUE, 고정 version/engine·claim32bytes·finite시각/10초간격·상태별NULL조합·결과 object/UTF-8크기/hash/ID 연결 CHECK를 둔다. 전용 trigger는 INSERT running만, identity 불변, running→terminal 한 번만, DELETE 전부 거부하며 성공 제출의 실제 DB 현재시각도 확인한다. terminal no-op UPDATE도 거부한다. 관리자 DDL/TRUNCATE까지 막는 권한 격리는 아니다.

downgrade는 flow_runs→flow_input_snapshots→flow_fake_executions ACCESS EXCLUSIVE 후 실행행이 한 개라도 있으면 거부한다. 실행행이 없으면 기존 봉인 입력이 있어도 c7→c6가 가능하다. 기존 mode의 caller migration은 정확한 c6001, 새 mode는 head/c7001을 사용한다. CF003/006 checker 본문/허용 revision은 그대로다.

## 검증 경계

고정 mode는 `backend/scripts/cf002_interactive_login.py --verify-flow-fake-execution-db`다. 기존 clean-env Python -I -S -B, exact dependency, 소유증명·readonly preflight·동일 연결 attestation/migration·자기 HOME/환경 차단·finally cleanup을 전제로 한다. 기존 PG 전체 checker를 중첩하지 않는다. 일반 app DB·pytest·dotenv로 우회하지 않는다.

실제 결과와 source/동시성/실패·정리 근거는 [작업 기록](../../docs/work/CF-007-flow-fake-execution.md)에 구분한다. 합성 신원으로 실제 세션/ASGI/PG를 확인하는 것이며 실제 Google·브라우저·외부 AI·운영 DB·기존 보관함 게시의 완료는 아니다. wrapper 관측은 native 전체 tracing이 아니다.
