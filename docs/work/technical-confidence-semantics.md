# Technical confidence의 규칙 기반 근거 점수 의미

기준 develop `9a4d86adcf429894879bdc0aa7a10b31bd56f8a7`에서
`verith-technical-quality-integration` / `fix/technical-regime-confidence`로 warmup과 함께
15파일로 통합했다. 원래 `verith-technical-confidence-semantics`의 9파일과 manifest/로그는 보존했다.

## 제품 변경과 보존

confidence_basis는 기존 전체·긍정·중립·부정 개수와 높음/보통/낮음 라벨을 유지하며
‘현재 지표의 규칙 기반 근거 점수이며 상승 확률·예측 정확도가 아님’을 설명한다. 지표 개수 자체의
충분함을 보장하지 않는다는 제한도 명시한다. 결정론 한 줄 요약은 ‘근거 점수 높음’ 등으로 간결하게
유지하고 전체 정의는 신호 설명/본문과 confidence_basis에 남긴다.

생성·재생성 prompt는 같은 의미와 근거 개수 보존을 지시한다. 약세를 전제한 고정 구조를
‘개별 부정 기여/개별 긍정 기여’로 바꾸고 중립을 긍정으로 바꾸거나 전체 추세를 단정하지 않는다.
optional detail 세 필드가 ‘검증 대상이 아니다’라는 단정도 제거하고 확정 라벨·금지/충돌 표현
준수를 요구한다. 이미 머지된 CF055의 부가 필드 검사·국면별 fallback도 함께 보존한다.

계산식·가중치·0.7/0.4 구간·수치·enum·schema·재생성 상한은 변경하지 않는다. 새로운 지표 수 기반
감점이나 확률 보정식을 만들지 않는다. 지표가 적어도 HIGH가 가능한 현재 계산을 숨기지 않는다.

## 실제 통합 검증과 한계

- 기존 보호 graph unit **99 passed, guard 0**, graph self **7 passed**. warmup과
  PR74/CF055/CF056 회귀를 이 통합 source에서 실제 함께 실행했다.
- 한 방향 지표1개·거래량 확인1·횡보는 기존 agreement=1/volume_confirm=1/trend_clarity=0/
  conflict_absence=1, **0.8/HIGH** 그대로다. 긍정·부정 단일 지표 및 혼합/빈 지표 개수도 보존한다.
- 실제 fallback·두 prompt 렌더·compiled graph/thread bridge/strict completion에서 확정
  confidence/level·score/consensus·지표 signal/value/metrics/weight·국면 및 호출 상한을 확인했다.
  정상 한 줄 요약은 간결하고 본문/근거에는 전체 정의가 남는다.
- self는 기존 계산 함수 AST 보존 및 실제 텍스트 함수의 닫힌 AST/최소 builtins 실행을 확인한다.
  원격 기존 graph-self와 로컬 실제 graph99 증거를 구분한다. 가짜 LLM/OHLCV/HTTP이며 실제 모델은 아니다.
- source provenance·기존 64패키지 7,421파일의 전후 snapshot
  `6abde22e2d8f13cd378761ae43c5a5b84a764631eeadd5fd7dcc9e2a6b15d0a4` 일치와
  자기 임시 root 제거·기존 Backend .venv 원복을 확인했다. guard/worker/선택 범위는 변경하지 않았다.

정의는 LLM에 대한 prompt 지시이며 자유 문장 전체의 확률 오해·숫자 grounding을 검증 완료한 것이
아니다. 실제 모델 준수는 이번에 실행하지 않았다. 숫자 근거 분리는 후속 CF059의 별도 단위다.

사용자 명시 범위에 따라 Ready PR·정확 head CI 후 정상 머지하며 타인 PR·PR61 HOLD는 건드리지
않는다. 실제 OpenAI/KIS·키/env·DB·설치·운영 활성화·추가 예약 없이 원래 실행 자료와 **$0.70 hold**를
보존한다. 로컬 검증 이후 원격 PR/CI/merge 결과는 별도 기록한다.
