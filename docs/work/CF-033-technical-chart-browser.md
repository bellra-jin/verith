# CF033 — 실제 Technical 차트 마운트

기준은 develop `41e4a183cad5f0a6b8f3634c116a53c256a8cb85`다. CF032의
`TechnicalBoundaryPreview`와 기존 `TechnicalChartPanel`을 수정 없이 실제 React DOM,
Recharts 및 Lucide와 조립하는 합성 브라우저 fixture를 추가했다. 공개 route나 제품
실행 경로를 열지 않으며 변경은 fixture, 보호 caller, tooling 회귀, 이 기록의 네 파일이다.

## 고정 조립과 보호

React 19.2.4의 기존 production 다섯 파일과 Recharts 3.9.1 UMD,
Lucide React 1.23.0 CJS, Next 16.2.10에 포함된 React-Is
19.3.0-canary-3f0b9e61-20260317 세 파일만 닫힌 registry에 넣는다.
최상위 React-Is 16.13.1은 사용하지 않는다. 실제 React19 element/fragment 인식과
차트·아이콘 exports를 보호 worker 안에서 실행한다. 이는 production dependency 변경이 아니다.

부모는 공개 package 네 개와 코드 파일의 고정 hash/version, trusted ownership/mode,
identity와 source/lock provenance를 전후 대조하며 실패한 child도 후검사한다.
기존 다섯 sibling을 보존하고 chart-browser sibling 한 곳만 추가했다. 임의 require,
동적 코드 생성, fallback, 새 설치, package/lock/guard/worker 변경은 없다.

GET은 `/technical-preview`, `/bundle.js`, `/fixture.css`만 제공한다. readiness는
기존 소유 파일이다. `/fixture-finish` POST는 정확 Host/Origin/nonce/content type,
1KiB body와 절대 5초 수신 제한을 유지한다. 기존 terminal helper로
receipt → ACK → 소유 listener close → settled 순서를 사용한다.
590초 fixture와 600초 parent 제한, 소유 PID/cwd/port 검증을 유지한다.

## 직접 검사

검증된 절대 Node 22.7.0, clean `env -i LANG=en_US.UTF-8 TZ=UTC
OPENSSL_CONF=/dev/null`에서 기존 `frontend/scripts/check-local-ports.mjs`를 실행했다.
정확 모드는 `technical-chart-unit`, `technical-chart-lint`, `technical-chart-browser`다.

- 최종 `technical-chart-unit`: 61개 통과. 실제 registry 사전검사, 정확 dependency/root
  선택과 drift 거절, import-safe helper·경로·body 제한 및 기존 terminal 회귀를 포함한다.
- 최종 `technical-chart-lint`: 변경 JavaScript 세 파일 통과.
- 최종 browser 회차: completed receipt, child/parent exit 0, listener/readiness/등록 child
  정리와 소유 root 제거. dependency/source 후검사 성공, 관측 guard 위반·진단 실패 0.
- guard SHA256:
  `3a9cb45bc865d560612ccd5876f060c69aa0abe5ff635576888781d9efe7d3ee` 불변.
  package/lock 및 실제 제품 readonly graph도 기준 bytes를 보존했다.

단위 숫자는 전체 서비스 수용이 아니다. guard 계측은 instrumented JS 파일 소비 범위이며
native 전체 읽기 부재 증명이 아니다. receipt의 browser 필드는 기존 schema대로
`not_executed`이고, ACK는 부모에서 `not_observed`다. 아래 직접 UI 관측을 receipt가
자동 증명한 것으로 표현하지 않는다.

## 실제 Chrome 관측

미로그인 전용 Supervisor test 프로필에서 emitted loopback origin만 사용했다.
실제 production component와 고정 합성 JSON을 사용했으며 component handler 직접 호출,
임의 DOM 평가, 외부 자료나 provider 호출은 없다.

최종 같은 소스 회차에서 다음을 확인했다.

- 390×844와 1440×844에서 실제 캔들, 가격축, brush, RSI 및 거래량 SVG와 아이콘을
  화면 캡처로 관찰했다. SVG의 실제 폭은 각각 350px와 1080px이고 높이는 288/92/80px다.
  화면 캡처는 도구 결과로 관찰했으며 별도 이미지 파일을 저장한 것은 아니다.
- native Tab → Return으로 3개월에서 5년으로 전환하고 Tab → Space로 RSI를 껐다.
  같은 binding 재렌더는 5년·RSI 꺼짐을 유지하고 새 binding B는 3개월·기본 지표로 초기화했다.
- 전부 빈 자료, 전부 미제공, typed 오류, 잘못된 packet은 모두 차트 없이 안전 문구를 표시했다.
- 정상 완료 버튼을 native 키보드로 실행한 뒤 UI unmount와 모든 제어 disabled를 확인했다.
  같은 회차의 소유 정리와 부모 후검사가 통과했다.

두 행의 작은 합성 자료이므로 실제 시장 차트의 수치·시각 품질을 검증한 결과가 아니다.
brush는 표시와 AX slider 존재만 확인했고 drag/키보드 범위 조작은 미실행이다.
물리적 폰, Safari, screen reader, 전체 Tailwind/Next build·운영 디자인,
실제 owner 저장/인증/Backend/PG/엔진/provider/모델 품질은 이번에 검증하지 않았다.

## 실패 이력과 최소 수정

초기 lint의 브라우저 전용 registry require 표기 오류를 한 줄의 목적 한정 lint 주석으로
정리했다. 불필요한 HTTP readiness 경로는 독립 검토 후 제거했다.

첫 browser는 AX emulation 클릭 위치 불일치로 의도보다 먼저 완료됐다.
receipt와 정리는 완료됐지만 부모가 강화된 React record를 기존 축약 record와 비교해
exit 78이었다. chart 모드의 후검사를 동일한 강화 record와 비교하도록 고쳤으며
전체 chart/metadata/React 전후 검사는 유지했다. 이 회차를 통과로 세지 않는다.

다음 회차는 정상 부모 종료와 DOM 마운트/상태 조작을 확인했지만 화면의 SVG가 흰색이었다.
별도 진단 회차에서 SVG 폭 0, 높이 정상, visible/opacity 1을 확인했다.
fixture의 `max-width:100%`가 Recharts의 의도된 0폭·overflow-visible 측정 래퍼와
충돌했다. fixture의 두 max-width 규칙만 제거한 최종 회차에서 실제 그리기를 확인했다.
제품 chart 계산/JSX/CSS, CSP, dependency 및 보호 조건은 수정하지 않았다.

## 검토와 게시

독립 읽기 검토는 registry/provenance/소유 수명주기 및 좁은 수정 delta에서 미해결
finding이 없음을 확인했다. 최종 문서와 네 파일의 공개 범위 대조 후 일반 게시 절차를 진행한다.
원격 CI와 merge 결과는 최종 인계에 별도로 기록하며, 이 문서만으로 미래 CI 성공을 주장하지 않는다.
