# Flow KIS 실전 origin 사전 검증

기준 develop `d0aee90754c0de96df27bffdcd236de8718ed0f3`, 전용 `fix/flow-kis-origin`이다.
실제 Flow 실행 준비와 자격/설정은 수정하지 않고 실제 API·DB·예약을 새로 만들지 않는다.

기존 KIS 자격 로더는 값 존재만 확인하여 모의 또는 비정상 주소에서도 token 요청까지
진행할 수 있었다. 실전 전용 조회에 맞는 origin을 로더 반환 전에 검증하고, 비밀 없는
고정 `KisConfigurationError/KIS_CONFIGURATION_INVALID`로 닫는다. 이 타입은 기존
`KisError`의 하위 타입이며 공개 HTTP DTO와 회계/보수 hold를 변경하지 않는다.

키/환경 파일을 읽지 않는 고정 가짜 설정으로 실제 자격 로더와 두 fetch 함수 body를
기존 보호 AST 입구에서 검사한다. 모의/HTTP/포트/위장 host/userinfo/path/query/fragment/
공백/control/Unicode·비문자열은 거절하고 HTTP client 생성·token/cache·외부 요청0을
단언한다. 정상 실전 주소와 trailing slash/대문자 주소는 기존 반환 계약을 유지한다.

기존 token cache·가격/한도·수치 계산·다른 agent·Frontend·lock·실제 .env는 그대로다.
같은 KIS source를 공유하는 여섯 exact pin만 새 bytes로 갱신하며 허용 입력 집합·worker/
guard를 늘리거나 약화하지 않는다. 원 실제 실행의 입력/기록·보수 예약은 repin하지 않는다.

이번 합성 검사는 실제 KIS 인증·자료·계정 종류 또는 정상 서버의 실동작 증거가 아니다.
현재 실제 실행의 설정 불일치는 별도로 남으며 이 변경이 실전 설정을 자동 생성/변경하지 않는다.

검사 결과: 기존 보호 flow-errors-self 2개·단일 flow-errors-unit 125개 통과, guard 위반0,
자기 임시 root 제거 확인. 별도 독립 source 검토에서 차단 결함은 없었다. 실제 환경값·키·
공급자·DB·새 예약은 사용하지 않았다. Ready PR/정확 head CI·병합 결과는 별도 인계에 남긴다.
