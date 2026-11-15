# Technical 선택적 사용량 증거의 strict 보존

기준 develop `83d38c0af1ec5f49ae4b14e4071d0f4e1c107467`에서 기존 Technical OpenAI 어댑터의 작은 정확성 오류를 수정했다. 이 변경은 Technical 실행/운영 비용 연결을 활성화하지 않는다.

`_extract_usage`는 누락된 필드를 0으로 채우고 `int(...)`로 문자열·bool·소수 값을 변환했으며 input+output과 total의 일치도 검사하지 않았다. 따라서 없는 사용량이 0이 되거나 잘못된 관측이 유효한 정수처럼 보일 수 있었다. 기존 함수 문서의 “없거나 불안정하면 None”에 맞춰 세 필드가 모두 명시적인 비음수 정수(exact int)이고 input+output==total일 때만 새 dict로 보존한다. 누락/None/bool/문자열/소수/음수/합계 불일치는 None이며 명시된 유효 0/0/0과 기존 11/22/33은 그대로다. 분석 텍스트를 거절하거나 다시 호출하지 않는다.

기존 CF040 보호 collection에서 해당 어댑터 source 하나의 exact readonly pin만 추가했다. 실제 `_extract_usage`/`_extract_text` 함수와 `OpenAiLlmClient` class의 AST body를 실행하고 자기 합성 SDK 객체를 주입한다. 전체 SDK/config loader/client factory/graph/provider를 import하지 않는다. 기존 CF021 import 금지·worker·OS/파일/네트워크/프로세스 guard와 모드/CI/패키지는 변경하지 않는다.

보호 self 3개·unit 52개가 통과했고 guard 위반 0·자기 임시 root 제거를 확인했다. 기존 정상 동작에 더해 누락·잘못된 타입·합계·명시적 0·유효 정수·연속 성공 후 잘못된 사용량에서 carryover 없음과 분석 텍스트 보존을 확인했다. 실제 source body 검사이며 원본 SDK 전체 모듈 import/외부 호출 검증과 구분한다.

`last_usage`는 여전히 마지막 성공 호출의 선택적 관측이다. 여러 호출의 총계, 가격/모델 일치, 예약/정산 ACK, 실제 청구 확정이나 실행권이 아니다. None은 미사용/무료 증거가 아니다. Technical 전용 admission/profile·멱등 실행·사용량 정책·lazy 운영 조립은 별도 미완료다. Flow 회계/기존 실제 소비·예약/once·키/.env·DB·Frontend·준영 AI를 변경하거나 호출하지 않았다.
