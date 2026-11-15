# Technical 장기 MA 기울기 이력과 횡보 구분

기준 develop은 `9a4d86adcf429894879bdc0aa7a10b31bd56f8a7`(PR73~76 실제 통합 후)이다.
`verith-technical-quality-integration` worktree의 `fix/technical-regime-confidence`에서 기존
warmup·confidence 두 단위를 공통 검사/pin 중복 없이 15파일로 통합했다. 원래
`verith-technical-regime-warmup`의 9파일·manifest·검증 기록은 변경하지 않았다.

## 제품 정책

이전 ‘장기 MA 기울기 없음 → 마지막 횡보’를 명시적으로 보완한다. 우선순위 1~5는 그대로 검사하고
마지막 SIDEWAYS 직전에만 slope60이 None이면 기존 UNAVAILABLE로 구분한다. MIN_DAILY_BARS=60은
유지하며 모든 입력에 65봉을 요구하지 않는다. 충분한 과열·과매도·하락 등 앞선 판정은 유효하다.
기울기 0은 계산된 값이며 다른 조건이 없으면 정상 횡보다.

multiframe은 UNAVAILABLE만 데이터/지표 이력 부족으로 설명하고 기존 neutral alignment를
유지한다. graph·출력 schema·상태·flag·confidence 계산은 수정하지 않았다. 기존 unavailable
분기가 signal/risk=null, technical_signals=[], charts 유지로 완료한다. test plan의 반대 정책
두 문장과 기존 missing-slope 단위 기대값도 같은 정책으로 맞췄다.

## 실제 통합 검증

- 기존 보호 graph unit **99 passed, guard 0**, graph self **7 passed**. 원래 두 단위와
  PR74/CF055/CF056의 회귀를 합산 추정하지 않고 이 통합 source에서 함께 실행했다.
- 실제 MA/RSI/밴드/캔들 계산으로 평탄한 60/64봉 unavailable, 65봉 기울기0·sideways와
  60/64봉의 충분한 과열·과매도·하락 보존을 확인했다.
- 실제 compiled graph/thread bridge/strict completion의 60/64봉 unavailable 및 65봉 normal,
  ID/as-of·차트·호출 상한·thread/slot 정리를 확인했다. 가짜 LLM/OHLCV이며 실제 공급자 검사가 아니다.
- 기존 self는 앞선 계산/우선순위 AST 보존과 닫힌 tail/context 실행을 확인한다. 원격 CI는 기존
  graph-self를 실행하며 실제 graph99는 로컬 증거다. AI test_regime_rules 파일 전체를 직접
  pytest로 실행하거나 새 source intake에 추가하지 않았다.
- source provenance와 기존 64패키지 7,421파일의 전후 snapshot
  `6abde22e2d8f13cd378761ae43c5a5b84a764631eeadd5fd7dcc9e2a6b15d0a4`가 일치했고
  자기 임시 root 제거·Backend .venv symlink 원복을 확인했다.

source pin은 기존 guard/selection AST를 유지하며 실제 변경 source의 정확 SHA만 결합했다.
공통 검사 충돌은 원본의 새 함수/메서드를 그대로 보존해 해결했다. confidence 의미 보완은
동반 기록을 따른다. 숫자 grounding·수식/가중치 재설계는 이 묶음에 없다.

사용자의 명시 범위에 따라 Ready PR·정확 head CI·정상 develop 머지를 진행하며 타인 PR은
대행하지 않는다. PR61 HOLD와 기존 실제 실행 자료·$0.70 hold는 불변이다. 실제 API·키/env·DB·
설치·운영 활성화·추가 예약은 없다. 이 기록은 로컬 검증 시점이며 원격 PR/CI/merge 결과는 별도다.
