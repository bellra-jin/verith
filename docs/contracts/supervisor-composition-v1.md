# Supervisor Flow/Technical 조합 요청 — v1 보존과 v2 명시 입력

이 단위는 내부 영속 기반이다. 이 문서나 접수 기록만으로 공급자 실행·정산·운영 활성화 권한을 만들지 않는다.
기존 `supervisor.core.v1`과 `supervisor.technical.v1`, 각 실행/보고서/비용 계약은 유지한다.

## 식별과 동의

조합 요청은 소유자·원 확인 세션·원 client key digest·원 질문과 의미 frame·canonical 종목·선택 관점·
조건/동의·두 자식의 정책 snapshot을 한 번 고정한다. 선택은 flow/technical 중 하나 또는 둘이다.
다른 관점·복수 종목·미해결 근거를 임의로 제거해 부분 실행하지 않는다. unsupported 조건은 정확한
waiver와 부분 동의가 없으면 실행하지 않는다. 원래 질문/조건은 부모에 남고 자식 실행 입력의
projection과 구분한다. 고정 자식 key는 부모 ID·관점·서버만 보유하는 고정 identity seed에서 파생하며 재생성/회전하지 않는다.
공개 부모 ID만으로 자식 key를 추측해 다른 세션이 선점하지 못하게 한다. seed/claim digest/자식 key는
사용자 응답이나 로그로 내보내지 않는다.

각 자식 정책과 최대 예약을 별도로 고정한다. 부모는 이 참조와 합계를 표시할 뿐 새 공통 비용 원장을
만들거나 Flow/Technical 예약을 섞지 않는다. 정책이 없으면 새 접수는 닫힌다. 성공·실패·unknown만으로
어느 자식의 hold도 해제하지 않는다. 기존 실제 검증 비용 hold는 제품의 향후 예산이 아니다.

## 한 번의 시작과 시점

새 부모 접수와 시작권의 SQL commit ACK를 이번 invocation에서 직접 확인한 원 확인 세션만
직렬 실행을 시작할 수 있다. ACK 유실·프로세스 재시작·다른 로그인 세션은 토큰이나 실행권을 복구하지
않는다. 같은 POST와 GET은 현재 부모/자식을 관찰하며 재접수·재claim·새 공급자 호출을 하지 않는다.

최초 요청의 140초 총 deadline과 15초 admission/planning deadline을 공유한다. 자식마다
새로 시작하지 않는다. 하나의 AsyncSession에서 병렬 gather하지 않으며, 다음 자식 전 남은 시간이
없으면 미시작 상태를 보존한다. 기존 Flow POST는 접수/게시 복구를 할 수 있어 replay에서 호출하지
않는다. Technical의 기존 binding POST가 관찰 전용이라는 차이도 그대로 유지한다.

Technical이 선택되면 기존 provider admission에서 고정한 `as_of`를 부모의 분석 시점으로 연결한다.
`started_at == as_of` 보호는 바꾸지 않는다. 이 연결을 확인하기 전에는 Flow를 시작하지 않는다.
Flow 단독은 부모 접수 시점을 사용한다. 자식의 deadline과 회계 기간은 해당 정책을 그대로 따른다.
공통 분석 시점은 공급자 공개/마감 시각 검증이나 실제 동시 수집을 의미하지 않는다.

Technical 접수 ACK와 분석시점 확정을 선행하고 선택된 자식 접수·인계는 최초 15초 안에 완료한다.
제공자 실행 순서는 후속 조립에서 확정하며 이 단위는 dispatch를 구현하지 않는다. Flow POST가
접수와 실행을 결합하는 문제는 다음 연결에서 해결하며 deadline 확대나 갱신으로 해결하지 않는다.
Flow 결과의 참조 연결은 그 인계로 시작한 원 실행의 전체 140초 안에서 가능하지만 새로운
접수·실행권을 만들지 않는다. ACK 불명 상태의 Flow POST를 다시 호출하지 않는다.

## 관찰과 부분 결과

부모는 자식의 실제 상태·참조·정책/예약을 유지한다. stored만 저장 성공이다. result_ready는 stored가
아니며 unknown은 실패·미호출·취소·환불이 아니다. 한 자식의 실패나 unknown으로 다른 stored 결과를
삭제하거나 전체 fulfilled로 표시하지 않는다. 전체 fulfillment와 각 관점 상태를 별도로 반환한다.

원 확인 세션이 철회되면 새 실행을 중단한다. 같은 소유자의 유효한 다른 세션은 관찰할 수 있지만
미소비 실행권을 가져가지 않는다. 타인의 부모/자식은 404로 닫는다. 조회에서 재실행·예약·게시 복구를
자동 수행하지 않는다. 삭제/정리와 늦은 자식 결과의 상태는 각 기존 owner 계약을 따른다.

## 첫 직렬 단위의 입력 제한

첫 단위는 완전히 해소된 고정 범위만 접수한다. 조건이 있는 질문은 waiver 없이 잘라내지 않고
명확화/미지원으로 닫는다. 조건별 조합 waiver 정책은 후속 명시 계약에서 열어야 한다. 부분 결과
허용(`allow_partial_results`)은 미지원 조건을 없애는 동의와 별개이며 두 관점 선택 시 명시 true가
필요하다. 기존 단독 경로의 조건/waiver 계약은 변경하지 않는다.

## v1 기반 구현 범위

영속 접수·원 세션의 단일 시작·일회 인계·고정 자식 참조 연결·본인 상태 조회를 제공한다.
별도 DB 세션의 A2 조회는 실행권을 복원하지 않는다. 동일 key의 다른 snapshot은 거절하며
기한 이후 조회에서 부모를 영속 closed로 전이해 미시작 관점이 무기한 pending으로 남지 않게 한다.
close는 첫 await 전에 해당 부모의 미소비 인계권을 무효화한다. 이미 발급된 native 실행권의
취소나 공급자 중단을 의미하지는 않는다. 취소를 받은 task는 SQL 재정리 없이 전파하고, 호출자의
소유 AsyncSession 문맥이 rollback/종료하여 잠금을 해제해야 한다.

v1 기반만으로 공개 조합 API·Supervisor 복수 선택 planner·native 직렬 dispatch를 연결하지 않는다.
v2 내부 조립은 아래에서 별도로 구분한다.
격리 PG의 자식 fixture는 기존 native 접수/start/receive/writer를 검사에서 명시 호출한 것이며,
이 조합 서비스가 두 엔진을 실행했다는 증거가 아니다. 상태 GET은 native POST나 게시 복구를 호출하지 않는다.
새 프론트·다른 AI·실제 공급자·키/env·패키지 설치·운영 DB·기존 실제 기록 변경은 포함하지 않는다.


## v2 명시 자식 입력과 내부 실행 조립

`supervisor.composition.v2`는 기존 필드에 `child_inputs`를 추가한다. 부모의 원질문·전체 frame·
canonical Stock·선택 관점·조건/동의는 그대로 고정한다. 조건 없는 해소된 단일 종목만 허용한다.
Flow 입력은 동일 code와 원질문을 유지한다. Technical 입력은 동일 code의 `코드 차트`와 기존
`technical.multiframe.v1` / 3m·1y·5y로 명시한다. 이는 원질문의 자의적 부분 문자열 편집이 아니다.
지정한 두 고정 profile 외 범위를 승격하거나 조건을 버리는 projection은 거절한다.

기존 v1 snapshot/intent/자식 key namespace는 바꾸지 않는다. v1 상태 조회와 기존 원질문 기반
자식 fingerprint 검증을 보존하며, 새 runtime은 v1을 v2로 변환하거나 재실행하지 않는다.
v2의 파생 key도 기존 v1 UUID namespace를 유지하고 root scope hash는 새 명시 필드를 포함한다.
c610은 기존 guard를 확장할 뿐 표·비용 원장을 추가하지 않으며, 소비 이력이 있으면 downgrade를 거절한다.

내부 `CompositionRuntime`은 기본 비활성이다. 명시 활성화·원 확인 세션·이번 commit ACK 아래에서만
Technical 접수/시점을 연결한 뒤 Flow 접수를 끝내고 기존 두 runtime을 직렬 호출한다. 각 접수 INSERT는
원 15초 cutoff를 확인한다. 공개 Flow POST는 기존 즉시 실행과 result_ready 게시 복구를 유지하지만,
내부 접수 replay는 관찰만 하며 invocation-local continuation을 재발급하지 않는다.

Root 140초와 각 자식의 더 이른 monotonic 기한을 접수 때 고정하고 후속 조회/실행에서 늘리지 않는다.
DB wall clock 후퇴도 이 기한을 늘릴 수 없다. 받은 정상 body의 유효 usage는 기존 observe 경로로
보존하며 기한 후 결과 채택/게시를 막는다. body/회계 commit을 확인하지 못하면 기존 unknown hold를
보존한다. 외곽 취소에 새 SQL 재시도나 실행권 복원을 붙이지 않으며, native의 기존 rollback과 caller 소유 session 종료를 유지한다.
부모가 닫힌 뒤 미완료 native 상태는 보수적 unknown으로 투영하며 원 native 상태도 별도로 남긴다.

공개 복수 선택 planner/prepare/confirm API는 아직 미연결이다. 위 projection은 미래 공개 준비 응답에서
실행 범위와 함께 보여 주고 확인받아야 한다. 이 내부 조립 검증은 실제 공급자·전체 compiled graph·
운영 활성화·실제 Google 로그인 수용을 뜻하지 않는다.
