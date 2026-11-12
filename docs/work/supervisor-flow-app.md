# Supervisor·Flow 전용 AI 앱

기준 develop `58e50f21653d8b73feb4261b00c6cb7668a8551a`, 전용
`feat/supervisor-flow-app` 작업이다. 프론트는 다른 담당 범위이며 이 작업에서 수정하지 않는다.

## 제품 연결

표준 `src.main`은 Fundamental·Industry·Technical도 import한다. 기존 Flow와 Supervisor의
정상 router factory를 필요한 환경에서 사용할 수 있도록
`src.supervisor.api.flow_app:create_app`을 추가했다. uvicorn의 `--factory` 시작점이며 별도
엔진·Gateway·회계·실행 프레임워크를 만들지 않는다. 기존 main은 변경하지 않았다.

factory는 실제 두 router를 인자 없이 조립하고 독립적인 앱을 반환한다. Flow의 실제 engine
선택과 단일 worker 슬롯·deadline·usage 수집은 기존 runtime에 남는다. 앱 생성 시 설정이나
환경 파일·키를 읽지 않는다. 기존 feature gate와 service-token 인증은 각 요청에서 그대로
동작한다. 명시적인 `FLOW_ANALYSIS_ENABLED`와 Flow engine gate가 필요하며 기본 비활성이다.

이 전용 앱은 meaning runtime을 설치하지 않는다. process의 meaning 설정만으로 모델을
활성화하지 않으며, 부족한 의미는 기존 unavailable/명확화로 남긴다. 표준 main의 명시 runtime
설치 경로나 의미 비용 callback의 HTTPS 계약을 변경하지 않는다.

## 모델 없는 명확화와 Flow 회계

원질문 `현대건설 외국인 말고 3주 수급`에 종목 답변 `현대건설`을 명시하면 policy2의
결정적 start/continue로 종목을 해소할 수 있다. 정확한 두 조건은 unsupported와 waiver로
보존하고 scope_confirmation/partial 장벽을 유지한다. 실제 실행에는 새로 반환된 계획의
조건 ID에 대한 부분 범위 동의가 필요하며, 과거 정리된 DB 계획/ID를 재사용하지 않는다.

Backend의 기존 Supervisor confirm→Flow AnalysisService/FlowUsageControl→AIClient→Flow
route/engine 경로는 그대로다. Flow는 service token으로 인증한 요청에 usage를 응답하고,
Backend가 별도로 관측·정산한다. AI에서 Backend로 Flow 비용 callback을 보내는 구조가
아니므로 localhost HTTP를 사용할 수 있다. 이는 의미 모델 callback의 TLS를 해제하는 것이
아니다. 미설정 한도·인증 실패·불확실한 예약 ACK에서 전송하지 않는 기존 경계는 유지한다.

## 검사와 한계

기존 보호 meaning-unit에서 실제 factory와 HTTP ASGI를 검사했다. 앱 생성/복수 생성 시
설정 읽기0, 실제 Flow runtime의 engine=None, 관련 없는 agent import0, default-off,
토큰 없음/오류/중복의 body 전 거절, 모델 없는 명확화/두 waiver, process meaning 설정으로
모델 활성화0, Flow engine gate가 닫힌 상태의 graph import0을 확인한다.

검사 loader는 기존 순수 Flow/Deadline 입력을 실제 namespace와 정확 origin으로 순서대로
로드한다. 새 앱 source pin 하나만 기존 입력 집합에 추가하며 CF023의32개·worker/guard·
기존 수집 전 금지 경계는 유지한다. 실제 공급자를 합성 engine으로 대체해 성공했다고
표현하지 않는다. 테스트 요청은 합성 ASGI이며 실제 uvicorn/외부 provider·owned PG
전체 실행은 별도의 승인된 환경 검증과 구분한다.

이 변경의 검증 중 설치·환경/키 읽기·KIS/OpenAI 호출·DB·새 비용 예약은0이다. 기존 실제
의미 해석 성공과500m 보수 예약/소비 기록은 불변이다. 이후 승인된 격리 설치·Flow 실제
한 건은 이 제품 코드 검사 결과와 별도 기록으로 남긴다.

최종 보호 meaning-self 7개·meaning-unit 367개 통과, guard 위반0과 자기 임시 root 제거를
확인했다. 독립 최종 검토에서 차단 결함은 없었다. 초기 합성 loader의 Deadline 순서와
FastAPI lazy router 검사 방식만 보완했으며 제품·guard를 완화하지 않았다. Ready PR/CI
결과와 이후 실제 실행은 별도 인계로 기록한다.
