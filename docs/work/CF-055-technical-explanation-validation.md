# CF055 · Technical 설명 검증 실패의 최종 반영

기준 develop `c33ec8ec5d5ade308ce75568cdbf0883acc1e042`, branch `fix/technical-explanation-quality`.
제품 3파일, source pin 1, 기존 검사 2, 문서 2의 총 8파일이다. CF055의 허용 10경로 중
AI test 2파일과 사본 선택은 형식적으로 추가하지 않고 기존 compiled graph/순수 self에서 실제 사례를 실행했다.
새 SDK/KIS/config/계산식·schema/enum·prompt·재생성 상한·worker/OS guard/패키지·CI 설치는 바꾸지 않았다.

## 바뀐 동작

- 모든 interpretation.* 섹션의 기존 실패를 interpretation 묶음 실패로 반영해, 재생성 소진 뒤
  나쁜 섹션이 다시 채택되지 않는다. 단일 source 계약에 맞춰 summary 묶음만 fallback하고 정상 detail은 보존한다.
- detail_reason/caution/watchpoint도 금지어와 해당 지표 signal의 충돌을 검사한다. 대표 표현은
  필수 detail에만 요구한다. 실패한 지표의 네 문장은 기존 결정형 fallback으로 대체하고 정상 지표는 유지한다.
- indicator/detail의 잘못된 타입, 선택 필드의 숫자/불린/객체/배열을 str로 바꾸지 않는다.
  선택 부가 필드 생략/null/빈 값은 기존 안전한 기본 문장 보충을 유지한다.
- 지표 또는 요약의 실패가 남으면 최종/trace label_matched=false와 template_fallback을 사용한다.
  재생성이 모두 통과하면 llm_regenerated·passed·regen_count=1로 표시한다.
- fallback은 확정 국면과 개별 긍정/부정 신호를 구분한다. 모든 국면에서 하락 압력 완화나 추세 복원을
  전제하는 문구를 제거하고 새 판정·예측을 하지 않는다.

## 직접 검증

수정된 fixture로 기준 제품 소스를 일시 사본 검증한 corrected-baseline은 **36 failed/22 passed**다.
초기 before-fix/after-fix-1에는 필수 sync_runner 누락과 잘못된 literal 기대값 같은 fixture 오류가 포함돼
제품 재현 실적으로 합산하지 않는다. 기준 검사 후 후보 소스는 finally 정확 복원했고 index/HEAD는 바꾸지 않았다.

최종 기존 보호 technical-graph-unit **68/68**, technical-graph-self **4/4**, guard 위반 0.
68건은 실제 compiled graph/bridge/Pydantic·가짜 LLM/OHLCV의 최종 serialization까지 확인한다.
9종 summary 필드, detail 부가 필드 금지/충돌, 문자열 타입, null/빈 값, 재생성 성공,
parse/호출 예외, summary+detail 동시 실패와 기존 unavailable 경로를 포함한다.
확정 indicator/signal/value/metrics/weight 보존, source·label_matched·regen_count·최대4회 호출,
물리 worker/slot 종료를 확인했다. dependency 7,421개 snapshot 전후 동일과 자기 root 제거,
Backend venv symlink 복원을 확인했다. 새 실제 provider/키/env/DB·설치·예약은 0이다.

기존 원격 CI graph step은 self다. 두 순수 self 회귀는 정확 hash의 실제 evaluator 모듈과 닫힌 AST의
실제 fallback 분기를 실행한다. 새 CI mode/설치 없이 기존 step에서 수집된다. 실제 graph68은 로컬
보호 결과이며 원격 실행 결과로 확대하지 않는다. 전체 일반 unit/전체 AI pytest는 실행하지 않았다.

## 협업·게시 상태

최종 확인에서 준영 님의 열린 PR은 없고 PR73/74는 미병합, PR61은 HOLD다.
PR73과 test_entry 공통 hunk의 3-way 모의 대조는 clean이다.
PR74와 제품 3파일은 겹치지 않지만 공통 check_safe pin의 한 줄과 graph test의 EOF 추가는 텍스트 충돌이 있다.
PR74가 먼저 병합되면 최신 develop에서 그 pin·실제 SDK 회귀를 보존해 정상 통합하고 필요한 영향검사를 해야 한다.
현재 PR74 변경을 복사/대리 merge하거나 원격 검사를 약화하지 않았다.

이 작업의 git add/commit/push/PR/merge·auto-merge는 미실행이다. 정확 8파일의 게시 범위를 준비하고
사용자 직접 실행 지시를 기다린다. 기존 실제 실행 source·once/회계/정리 기록과 총 $0.70 hold는 불변이다.

## 남은 경계

자유 문장 숫자의 지표/필드별 값·단위·기간 grounding과 구조화 요약의 모든 라벨 의미 대조는 아직 미완료다.
이번 타입/실패 집계를 숫자 검증 완료로 표현하지 않는다. 전역 숫자 목록·다른 지표의 같은 값·임의 반올림은 없다.
support/resistance 동시 근접·OHLC 범위·60/64/65봉 warmup과 confidence 정책은 별도 다음 단위다.
실제 LLM 해석 정확도·Technical 통합 저장 성공·재무 연결·프론트/운영 배포 완료를 뜻하지 않는다.
