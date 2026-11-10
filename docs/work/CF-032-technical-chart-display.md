# CF-032 · Technical 검증 차트 표시 경계

CF032 v1.1의 정확 5파일을 develop
`ffbe39a62e6b12780ece3ad037d2d911ad8a9026` 기반의
`feat/technical-chart-display`에서 구현한다. 정본 SHA-256은
`63f6cdef171c59ccb8b8d6696336dbcc397d3fb5f04f4f180ad619a11c0d0cb2`다.
기존 작업공간과 거절된 CF029 게시, 실제 공급자 실행·예산·승인 자료는 변경하지 않는다.

## 표시 계약

새 `TechnicalBoundaryPreview`는 매 함수 호출마다 실제 CF031 decoder를 실행한다.
참조 identity만으로 검증 결과를 cache하지 않는다. 잘못된 입력과 검증된 typed error는
고정 안전 안내로 구분하며, chart 자료가 전부 비어 있거나 미제공이면 명시 빈 상태를
표시한다. 성공에서만 검증된 preview 전체를 기존 `TechnicalChartPanel` element의
charts prop으로 그대로 전달한다. 숫자·음의 0·null·annotation을 보정하지 않는다.

합성 미리보기, 요청 기준시점 적용 미검증, 엔진 생성 시각·원천 공개 시각 미보고와
기간별 제공·빈 자료·미제공을 인접 표시한다. 현재 시각이나 요청 시각을 자료 시각으로
대체하지 않는다. 원질문·owner·내부 ID/hash·raw 예외는 DOM용 텍스트/속성에 출력하지 않는다.

검증 후 report ID, supplied request digest와 request/context IDs·fingerprint의 고정
scalar tuple을 내부 React key로 쓴다. 같은 binding의 clone은 같은 key이고 다른
binding은 다른 key다. JSON tuple 인코딩은 canonical hash나 진위 증거가 아니다.
동일 binding은 같은 frozen 결과를 공급한다는 상위 계약을 전제로 하며, key만으로
동일 binding의 내용 변조를 탐지한다고 주장하지 않는다.

## 보호 검사 범위

caller에 정확 technical-display-unit/type/lint와 전용 sibling 한 곳만 추가한다.
기존 네 sibling·단일 dependency 관계·package/lock·trusted identity·source copy와
전후 provenance를 유지한다. 기존 공통 harness/tooling 사본 범위는 유지하며 신규
wrapper mode graph와 readonly 7개를 전체 사본 수로 표현하지 않는다.

unit은 새 단일 test와 기존 tooling만 실행한다. 실제 production React CJS 5개의
lock version·path·identity/hash를 기존 reactRecords로 전후 대조하고 unit capability에
전달한다. browser/core 권한과 port는 부여하지 않는다. 실패한 child 뒤에도 React
postcheck를 수행하며 child 실패와 drift를 함께 보존한다. guard/worker는 불변이다.

검사는 실제 production wrapper와 decoder/preview, 실제 React/JSX runtime을 닫힌
registry에서 실행한다. VM 사이에는 이미 검증된 preview의 realm 전달만 수행한다.
panel import만 호출하면 실패하는 명시적 sentinel type으로 대체해 element 생성과
props/key를 관측한다. 이는 실제 함수/React element composition이며 panel 실행,
Recharts mount, DOM/reconciliation/state reset, 브라우저·1440/390·focus 검증이 아니다.
타입검사는 실제 readonly panel과 전이 import를 포함하며 lint는 새 변경 대상만 검사한다.

## 현재 진행과 미검증

구현 뒤 필요한 보호 unit/type/lint를 실행했다. 아래 직접 결과와 이력을 source/log hash에 결합하고 독립 source 검토를 요청한다.

실제 engine/provider/key·DB/사용자별 저장/auth/usage·HTTP/BFF/public page·Supervisor
실행 연결·운영 활성화는 미실행이다. 기존 panel/계산/decoder/fixture·AI/Backend/CI와
package/lock은 변경하지 않는다. 이 작은 표시 경계는 Technical 전체 제품 인수가 아니다.


## 직접 검사와 실패 이력

검증된 절대 Node22.7.0으로 `env -i LANG=en_US.UTF-8 TZ=UTC
OPENSSL_CONF=/dev/null <Node> frontend/scripts/check-local-ports.mjs
technical-display-<unit|type|lint>`를 전용 worktree root에서 공식 승인 심사로 실행했다.
최종 unit은 wrapper 15 + tooling 58 = 73통과, fail/skip/cancel 0이다. type은 실제
readonly panel과 전이 import를 포함해 오류 0, lint는 새 component/test와
caller/tooling에서 오류·경고 0이다. 각 parent exit 0과 자기 임시 root 제거를 확인했다.
unit worker/exitRecords 2/2, type/lint 1/1이며 partial/diagnostic failure 0,
예상 밖 위반 0이다. 기존 tooling 음성 probe 16개와 native 전체 미관측을 구분한다.

첫 회차 unit73/type0도 통과했지만 lint는 try/catch 안의 JSX 구성 두 지점을
react-hooks/error-boundaries 규칙으로 거절해 parent78이었다. decoder/key의 순수
예외 처리를 helper로 분리하고 JSX를 밖에 둔 뒤 영향 unit/type/lint를 재검사했다.
검증·lint 규칙을 삭제하거나 완화하지 않았다. 최종 검사 전 React 기록에는 기존
5개 path/version/hash 검증을 재사용하면서 trusted file·inode/mtime 등 identity도
결합해 같은 내용으로 파일이 교체되는 drift를 실행 전후 거절하도록 보완했다.
실제 검사는 현재 production 파일을 읽고 비교하며, 손실/실패/drift 조합은 실제
parent helper의 bounded callback simulation이다. 설치된 dependency를 변조하지 않았다.

최종 source·readonly graph·dependency metadata와 6개 실행 로그의 hash를 별도
private manifest에 보존했다. source와 guard/package/lock·기존 CI는 불변 대조했다.
단위의 실제 production React element 생성과 panel sentinel 관측을 실제 Recharts
렌더·DOM reconciliation·state reset·브라우저나 실제 사용자 수용으로 세지 않는다.
정상 PR의 exact-head/Ready CI는 로컬 검사를 대신하지 않으며 게시 뒤 별도 확인한다.


## 게시 전 독립 검토

동결 exact5의 독립 읽기 검토가 미해결 finding 없이 완료됐다. 실제 decoder/React
element 실행, 안전·빈 상태와 key·props, caller의 exact sibling·React pre/post
identity 및 실패 경로, source5/readonly7/불변 입력·safe NUL 목록과 최종
73/type0/lint0·guard/정리 로그를 대조했다. 독립 재실행은 하지 않았으며 실제
mounted/state reset/Recharts/브라우저 수용으로 확대하지 않았다. 이후에는 이
완료 기록만 추가하고 제품/시험은 변경하지 않았다. 원격 exact-head/Ready CI와
정상 병합 결과는 별도 게시 인계 기록에 남긴다.
