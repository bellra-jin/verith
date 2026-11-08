# Flow 합성 데모 웹 계약

로그인 사용자의 별도 `/flow/demo?run_id=<UUID>`에서 합성 요청·저장 결과 조회만 연결한다. 실제 시세/수급/투자 분석이 아니며 기존 보관함에 게시하지 않는다. 기존 receipt의 pending/not_stored와 화면의 demo stage를 구분한다.

## 기본 닫힘과 정확한 경로

Backend `FLOW_SYNTHETIC_DEMO_ENABLED=False`, Frontend 서버 전용 동명 flag는 정확한 `true`만 활성화한다. 실제 설정 파일은 변경하지 않는다. 기존 `FLOW_RUN_ADMISSION_ENABLED`와 독립이며 demo가 켜져도 receipt의 공개 POST를 열지 않는다. off/인증 미설정은 body·DB dependency·engine 전에 닫는다.

- Backend POST `/api/flow/synthetic-demo/runs`, GET `/api/flow/synthetic-demo/runs/{run_id}`.
- 동일 origin BFF는 `/api/private/flow/synthetic-demo/runs`와 같은 UUID 상세 경로만 전달한다. 추가 path/method/query/임의 target은 전달하지 않는다.
- POST는 idempotency_key/as_of/strict allow_fake=true 세 필드만 받는다. ticker005930·question `Flow 합성 데모 v1`·fixture full20/v1은 서버 고정이다. 005930은 합성 표시 예시이며 실제 자료 조회의 증거가 아니다.
- 실제 4096-byte UTF-8 raw JSON 한도·중복 key·비유한 JSON·extra/타입·media/encoding을 dependency 전에 검사한다. Content-Length를 신뢰해 제한을 생략하지 않는다. BFF는 검사한 원문 bytes를 exact POST에만 전달한다.
- Cookie 원문(중복 이름 포함)·Origin·CSRF·안전한 Content-Type만 전달하고 Authorization/임의 owner/service/target 헤더는 배제한다. 기존 canonical localhost 3200→8200 규칙은 유지한다.

모든 새 성공/오류는 새 request_id와 CommonResponse, private/no-store·Vary Cookie/Origin을 사용한다. 실제 principal/owner/CSRF는 Backend가 검증하며 UI user_id·UUID·멱등 key는 인증이 아니다. 고정 오류 변환만 사용하고 새 ErrorCode는 없다. malformed BACKEND_URL·전송 실패도 새 데모 경로에서는 안전 envelope로 닫는다.

## 조율·조회·복구

POST는 admit commit→prepare commit→fake의 claim/terminal commit을 순서대로 호출한다. 전체 transaction을 가장하지 않는다. 부분 완료나 ACK/응답 유실은 같은 key/as_of의 명시적 POST로 이어지며, 기존 claim/terminal은 새 엔진 호출 없이 회수한다. terminal은200, 진행은202다. 알려진 run에만 Location을 담고 UI는 검증한 UUID로 자기 URL을 만든다.

GET은 owner receipt의 고정 marker와 full20/v1 봉인을 확인한다. 일반 receipt·같은 marker의 short4 prepared/result·타인/없는 자원은404다. 하위 not_found만 admitted/prepared로 표시하며 corrupt/auth/unavailable을 준비 중으로 숨기지 않는다. 새 run/seal/claim/engine을 만들지 않지만 CF007의 owner 한정 running→timed_out 만료 확정은 수행할 수 있다. DB 무쓰기 GET으로 보고하지 않는다.

view는 최초 run/request/예약 attempt, nullable input/execution ID, admitted/prepared/running/succeeded/failed/timed_out·기한/종료·저장 여부·성공 내부 결과/hash 또는 고정 failure를 명시한다. 성공은 데모 전용 저장이며 실제 리포트 게시가 아니다. token/digest/cookie/CSRF 원문은 결과에 넣지 않는다.

## UI identity와 수명

정확한 계정 namespace `verith.flow.synthetic-demo.v1:<user_id>`의 sessionStorage만 사용한다. 첫 명시 클릭에서 생성한 key/as_of는 POST 전에 저장한다. run/user UUID는 lowercase로 비교하되 멱등 key 원문을 replay에서 바꾸지 않는다. 손상/저장 실패에서 조용히 새 key로 POST하지 않는다. result·질문·token·CSRF는 저장하지 않는다.

busy ref와 intent generation은 double click·계정 변경·이전 응답을 차단한다. 새 데모는 timer 취소·abort·generation 무효화를 먼저 하고 자기 요청 화면으로 이동한다. GET 또는 POST의 running은 동일한1초/최대15회 GET loop로 연결하며, mount/refresh/back은 POST를 만들지 않는다. pagehide/가시성/세션 재검증 전에 결과를 숨기고,401/계정 변경/이탈에서 자기 요청과 표시를 정리한다. 실제 React 클릭/navigation 동작 검증과 helper/source assertion은 별도다.

## 검증과 현재 runtime 제약

기존 보호 Backend/FE entry·고정 새 unit·새 owned-PG `--verify-flow-synthetic-demo-db`를 사용한다. 실제 session/CSRF/owner/ASGI/PG와 Next+가짜 HTTP Backend·브라우저 결과는 구분한다. 정확한 실행·실패·정리는 [작업 기록](../../docs/work/CF-008-flow-synthetic-demo.md)에 남긴다.

새 Next HTTP test source는 있으나 현재 실행 준비 완료가 아니다. 기존 Mac build는 unknown 파일 접근 guard 차단이 미해소이며, 기존 preload/fork 환경 whitelist가 demo flag를 제거하므로 현재 ownedHTTP helper의 gate-on 검증도 불가능하다. guard/OS policy는 수정하지 않는다. 승인·준비된 독립 runtime 증거가 없으면 이 source의 Next HTTP/브라우저는 미검증으로 남긴다. 새 설치·범용 runner·원본 앱/사용자 profile을 대안으로 사용하지 않는다.
