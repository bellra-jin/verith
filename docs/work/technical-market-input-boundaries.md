# Technical 가격 범위와 지지·저항 동시 근접

기준 develop/HEAD는 `c33ec8ec5d5ade308ce75568cdbf0883acc1e042`이다. 전용 worktree
`verith-technical-market-input-boundaries`, branch `fix/technical-market-input-boundaries`에서
Technical 품질 개선의 두 번째 독립 단위를 구현했다. 설명 검증 변경(CF055), 실제 실행 소스,
PR73·74와 다른 작업 공간의 변경을 포함하지 않는다.

## 제품 변경

- 종가가 지지와 저항에 동시에 근접하면 기존 `neutral`을 반환한다. 종가 100, 지지 99,
  저항 101의 기존 지지 우선 `positive` 편향을 없앴다. 근접 임계값·경계 포함·단일 방향
  신호·양쪽 계산 불가 시 제외·0 분모 처리·가중치와 집계식은 유지한다.
- D/W/M `OHLCV`와 `IntradayCandle`은 `low <= open <= high`와
  `low <= close <= high`를 검사한다. 경계값·모든 가격 0·소수 가격을 수용하며 범위 밖 가격은
  보정하지 않고 거절한다. 기존 유한수·음수·high/low·날짜·추가 필드 검사도 유지한다.
- Backend `chart_contracts.py`의 두 모델에도 같은 검사를 적용한다. 이 파일은
  `execution_boundary.validate_result`의 실제 strict 수신/저장 계약이므로, AI만 수정하면
  외부 결과의 잘못된 가격을 Backend에서 수용할 수 있다. 이 동등한 경계 보완 외에는
  Backend 라우트·소유권·SQL·스키마를 변경하지 않았다.
- `check_safe.py`는 위 네 제품 파일의 검토된 source hash만 갱신한다. 선택 집합,
  guard·worker·권한·의존성·CI는 변경하지 않는다.

## 검증

- 기존 `technical-boundary-unit`: **244 passed, guard 0**. 양쪽 AI/Backend의 두 모델에서
  시가·종가 각각 상한/하한 위반을 거절하고 경계값·0·소수·분봉 거래대금 null은 보존한다.
  전체 결과 안의 범위 위반 candle도 AI/Backend 검증에서 거절한다.
- 기존 `technical-graph-unit`: **23 passed, guard 0**. 실제 compiled graph·thread bridge·strict
  completion을 가짜 LLM/OHLCV로 실행한다. 좁은 가격 범위에서 최종 지지/저항 신호는 중립이고
  실제 계산의 지지/저항 근거·값·가중치·집계 score/consensus를 보존한다. 실제 제공자 검사가 아니다.
- 기존 `technical-graph-self`: **3 passed**. 동시/단일 근접·기존 임계값·제외·0·임계값 경계를
  exact source의 닫힌 함수 AST로 검증한다. 최소 builtins와 호출/노드/속성 검사 뒤에만 실행한다.
  원격 CI의 기존 graph-self와 boundary-unit step이 각각 이 회귀를 실행하며 실제 graph는 로컬 검사다.
- graph source 전후 provenance 일치, 의존성 7,421파일 전후 snapshot
  `6abde22e2d8f13cd378761ae43c5a5b84a764631eeadd5fd7dcc9e2a6b15d0a4` 일치,
  자기 임시 root 제거와 Backend `.venv` symlink 원복을 확인했다. 설치하지 않았다.

## 통합과 남은 범위

원격 develop은 기준과 같고 준영 님 열린 PR은 없었다. PR73의 self 검사 수정과는 3-way
텍스트 통합이 가능하다. PR74와 source pin 사전은 텍스트 충돌하며 graph wrapper·self 검사는
텍스트 통합 가능하다. PR61도 source pin 사전이 겹치지만 계속 HOLD다. 다른 PR의 소스나
검사를 이 단위에 흡수하거나 대신 머지하지 않는다. 선행 PR이 머지되면 최신 develop을
통합하고 정확 pin·필요 검사·새 exact-head CI를 확인해야 한다.

이 문서 시점에는 stage/commit/push/PR/merge가 모두 미실행이다. 게시 승인과 독립 최종 검토는
별도로 확인하며 사용자가 직접 머지한다. 실제 OpenAI/KIS·키/env·DB·운영 활성화·새 예약은 없다.
기존 실제 실행 기록과 **$0.70 보류**를 보존했다. 숫자 grounding, warmup, confidence 가중치와
실제 공급자 품질은 이번 단위의 완료 범위가 아니다.

## 게시 후 CI의 기존 취소 회귀 수선

2026-11-13 사용자의 명시 게시 승인 후 정확 11파일로 Ready PR76을
게시했다. 같은 기준의 PR75 첫 CI에서는 기존 CF021 취소 검사의 마지막 정상 회복 요청이
시험용 10ms timeout을 재사용해 실패했다(207 passed/1 failed, guard 0). 이 파일은 PR75의
8파일에는 없으므로 PR75에 추가하지 않는다.

PR76의 허용된 기존 검사 파일 안에서 첫 강제 timeout과 worker 생존 중 busy 검사는
`remaining=.01`로 유지하고, 물리 worker 종료·취소 확인 뒤 정상 요청은 같은 runtime의
기존 3초 기본 예산으로 확인하도록 수선했다. 반복 취소·worker 생존·busy·호출 수·종료 검사는
삭제하지 않았고 제품 timeout/cancel/slot 코드나 보호 조건을 바꾸지 않았다. 최종 원격 CI는
이 수선이 포함된 새 정확 head를 기준으로 확인한다.
수선 후 기존 보호 boundary unit은 다시 **244 passed, guard 0**이었다. 제품·pin·graph 회귀는
변하지 않아 기존 graph23/self3 결과를 유지하며 불필요하게 반복하지 않았다.
