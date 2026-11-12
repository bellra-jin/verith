# CF046 · Supervisor/Flow 오류와 대기 안내

준비·확정 응답 대기와 서버 실행 상태를 구분하고, 사용 한도·기능 이용 불가·응답 기한 초과를
검증된 코드/status 조합에서만 안전한 한국어로 표시한다. 기존 request 모듈의 유한 문구를
생산 Session/ChatView에서 사용한다. Backend/BFF/wire·저장·분석 실행 경로는 바꾸지 않았다.

## 변경과 보존

- core/preparation 요청의 세 오류 코드를 보존한다. envelope/코드/status가 모순되거나 미상인 경우
  기존 안전한 일반 오류로 닫고 서버 원문은 출력하지 않는다.
- 표시용 operation은 실제 준비 POST/GET·child POST·확정 POST·verification GET·준비 DELETE다.
  서버가 `flow.running`을 반환했을 때만 분석 실행 중을 표시한다. GET은 새 실행/게시가 아니다.
- 오류 안내는 보유한 서버 ID와 일치한다. ID 없는 POST에 GET 복구를 약속하지 않으며 fixed key/body를
  보존하는 기존 명시 확인 경로를 안내한다. timeout을 취소/비용0으로 표현하지 않는다.
- intent/generation·동의·재인증·owner/URL/visibility·focus·취소·409 미채택 정리와 모든 기존 시간 한도를
  보존했다. 새 timer·재시도·key·실행·분석값을 만들지 않는다.
- fixture는 `coreFailure: none|usage|feature|deadline|service`만 추가했다. auth403과 분리하고 기존
  raw attempt accounting 뒤·성공 handler count 앞에서 검증된 envelope를 반환한다.
- caller에는 정확한 새 Frontend sibling 한 곳만 추가했다. dependency/metadata root와 package/lock,
  원본 접근 차단·복사/사후 provenance·guard/worker는 보존했다.

## 직접 검사

기존 보호 입구의 clean env·고정 설치 Node로 실행했다. 설치·실제 환경 파일/키·외부 API/DB는 사용하지 않았다.

| 검사 | 실제 결과 |
|---|---|
| core-unit | core 157 + BFF 24 + ports 6 + tooling 68 = **255 통과** |
| core-type | exit0 |
| core-lint | exit0, lint findings 빈 배열 |
| fixture-lint | exit0 |
| 원본/사본·dependency 사후 검사/자기 root cleanup | 통과 |
| guard 부정 검사 | 기존 예상 음성 16건 유지, 뜻하지 않은 위반0 |
| 최신 develop 통합 | `d005746c6d468e62ae3cc8b0934131098481de8a` ff-only, FE WIP 8파일 hash 불변 |

생산 요청 함수에서 코드/status·raw message fallback·pending/key/body 불변·추가 POST0을 검사했다.
실제 Session action을 주입 IO로 실행해 새 준비/ID GET/child/confirm 표시와 timeout·기존 generation 정리를
확인했다. 실제 ChatView JSX의 operation/running/result_ready/unknown/GET 표시 및 rerender 요청/저장0도
확인했다. 이는 React mount lifecycle·실제 사용자 클릭의 증거가 아니다.

첫 unit 회차는 기존 JSX의 옛 GET 안내 문구 기대가 실패했다. 이어 tooling에서 승인한 새 sibling을 기존
정확 root/provenance 기대 목록 두 곳에도 반영해야 함을 확인했다. 해당 기대를 정확히 추가했고 임의
sibling·root·dependency·owner/mode drift 거절은 유지했다. 최초 로그는 controller tail 제한으로 실패
상세 일부가 없으며, 원문 기대와 최종 통과 결과 이상으로 이력을 확대하지 않는다. 실패 로그는 보존했다.

## 실제 브라우저 회차와 남은 검증

최초 CUA inventory는 개인 Chrome extension만 노출했다. 개인 창/프로필·설정 파일을 열거나 새
프로필을 만들지 않고 보류했다. 이후 조율 측이 기존 `Supervisor test` 창을 지원 UI에서 확인해
해당 창만 사용했다. 새 보호 core-browser의 emitted origin에서 생산 Session/ChatView가 mount된
AX와 합성 control·counter를 직접 읽었다. Responsive 설정 `1440×844`도 AX로 확인했다.

native 좌표/scroll/Raise 입력에서 `noWindowsAvailable`이 반복됐고 AX 입력의 일부 반영은 불안정했다.
DevTools 전환 뒤 기존 visibility/인증 경계가 private 화면을 숨겨 재확인 안내를 표시했다.
오류·지연·명시 복구·390 overflow·Tab/Return/Space·focus의 실제 수용은 **미완료**다.
1440 설정 확인을 레이아웃/키보드 통과로 확대하지 않는다. 새 회차를 반복하거나 guard를 우회하지 않았다.

동일 회차의 완료 버튼 요청 뒤 `completed` terminal receipt와 parent exit0·소유 root 제거 및
source/dependency 사후 검사를 확인했다. receipt ACK는 `not_observed`이므로 브라우저의 완료 ACK를
주장하지 않는다. counter는 session GET2, core/준비/확정/결과 요청0, model/provider0이다.
자동 receipt의 UI 필드는 모두 `not_executed`이며, 위 직접 관측과도 구분한다.

실제 provider/Google 로그인/Backend·BFF·Flow 회계/운영 한도 설정은 미실행/범위 밖이다.
CF037 실제 기록·보수 예약과 CF045 작업/다른 WIP·서비스별 환경 파일·다른 DB/Docker는 변경하지 않았다.
현재 commit/push/PR/merge는 미수행이며, 최종 독립 검토·화면 미완료 경계와 exact-head CI를 구분해
상위 조율에서 게시 여부를 정한다.
