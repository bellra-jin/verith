# Flow 합성 입력 snapshot 준비

CF-006은 인증된 사용자의 기존 receipt에 합성 입력을 한 번 봉인하고 본인에게 재조회하는 **내부 service**다. HTTP endpoint, 실행권, worker, AI 결과를 추가하지 않는다. 기존 접수 gate·응답과 `receipt_only / pending / not_stored` 상태는 그대로다.

## 계약과 저장본

`InputPreparationService.prepare(run_id, fixture_id, version=1)`과 `get(run_id)`는 전달받은 principal도 실제 DB 세션에서 재검증한다. 세션 SHARE → owner-scoped run FOR UPDATE 순서이며, 타인/없는 run·snapshot은 같은 내부 not-found로 닫는다. 공개 ErrorCode/schema는 변경하지 않는다.

서버 catalog는 `flow.synthetic.full20`/`flow.synthetic.short4` v1이다. 요청 UTC 날짜를 끝점으로 20/4개의 연속 달력 날짜에 개인 -50,000·외국인 40,000·기관 10,000주, 거래대금 1,000,000원을 둔다. 실제 거래일/원천 자료가 아니며 published/observed/retrieved 시각은 null과 synthetic 사유를 보존한다.

본문에는 최초 receipt reference·정규화 요청·기존 fingerprint, fixture 내용/버전/schema/hash 및 비실행 사양을 보존한다. 사양은 fixture provider, executable=false, 외부 호출/최대 비용 0, not_reserved다. 예약 attempt UUID나 snapshot 존재는 실행 권한이 아니다.

canonical UTF-8 JSON TEXT(키 정렬, 공백 없는 separators, ensure_ascii=False, allow_nan=False), 최대 128KiB와 별도 SHA-256을 저장한다. 중복 키·비문자열 키·비유한 값·NUL/surrogate·잘못된 구조/타입을 거부한다. snapshot ID/봉인시각은 내용 hash 밖이다. 읽기는 digest·canonical bytes·고정 v1 schema·열/receipt 관계를 검증하고 현재 fixture 생성기/catalog/spec로 저장본을 재생성하지 않는다. 반환 body는 매번 독립 파싱한 사본이다.

같은 준비는 최초 ID·sealed_at·bytes를 반환하고 다른 fixture/내용은 conflict다. source receipt drift는 fail-closed하며 자동 재봉인하지 않는다. commit 성공 확인 후에만 성공을 반환한다. commit 전 실패/확정 rollback과 DB commit 뒤 ACK/응답 유실은 다르다. 불명확 결과는 고정 실패 후 같은 owner/run 조회·동일 prepare replay로 최초 봉인본을 확인하며 rollback 시도만으로 잔여 0을 주장하지 않는다.

## DB와 migration

revision `c6001a7e0001`(parent `c3001a7e0001`)은 `flow_input_snapshots`와 `flow_runs UNIQUE(id, owner_user_id)`만 추가한다. snapshot은 run당 한 행, composite owner FK/RESTRICT, 필수 열/버전/mode/finite 시각/UTF-8 길이/body/hash CHECK를 갖는다. 기존 pgcrypto를 사용하며 extension을 새로 만들지 않는다. UPDATE와 DELETE는 no-op도 trigger로 거부한다.

downgrade는 parent flow_runs ACCESS EXCLUSIVE → snapshot ACCESS EXCLUSIVE → 존재 확인 순서다. nonempty면 거부하고 revision/내용을 보존한다. 비어 있을 때만 이번 객체를 제거한다. 기존 receipt와 snapshot의 불변성은 구분한다. 관리자 ALTER/DROP/TRUNCATE까지 막는 권한 격리가 아니며 실사용자 purge/장기 보존 정책도 후속이다.

## 검증 입구와 수용 범위

기존 보호 `backend/scripts/check_safe.py self-test`/`unit` 및 고정 DB-only `backend/scripts/cf002_interactive_login.py --verify-flow-input-snapshot-db`를 사용한다. DB-only mode는 기존 소유증명·readonly preflight·동일 연결 attestation/migration·자기 HOME·dotenv/외부 통제를 재사용하고 앱/listener/Google 분기 전에 반환한다. 새 설치·일반 pytest·앱 DB fallback을 사용하지 않는다.

새 PG checker는 CF-006 사용자/snapshot 생성 전에 기존 CF-003 검사를 c3001/run0/user0 기준으로 그대로 실행하고 c6001로 복귀한다. 새 DDL 실패 주입은 flow_input_snapshots 생성 직후 전용 예외로 확인한다. 기존 receipt를 둔 upgrade/왕복, 실제 세션/owner, 최초 봉인, SQL 거부, 경합, ACK 유실·rollback·source drift·downgrade 양방향을 검사한다. lock-first는 별도 새 소유 PG에서 테이블 부재를 유지한 채 끝내며 재생성으로 복구하지 않는다.

최종 보호 self 18/unit 851 통과 및 실제 PG 결과·실패 이력·정리는 [작업 기록](../../docs/work/CF-006-flow-input-snapshot.md)에 있다. 실제 세션은 DB에 만든 합성 신원을 사용했다. 실제 Google·AI·브라우저·worker·결과 저장/게시 성공을 뜻하지 않는다. Python wrapper 관측은 native 전체 I/O tracing이 아니다.
