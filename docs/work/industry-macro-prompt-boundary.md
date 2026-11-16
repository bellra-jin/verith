# Industry 거시 답변 시점·근거 경계

## 범위
- 2026-11-15, C:\Verith의 기존 Industry 답변 경로를 보완했다.
- 근거: SDD 05의 금리·환율·물가·경기 현황/기업 연결 설명, 기준일·출처 보존 및 이익 크기·주가 방향 단정 금지.
- 독립 거시 agent, 지표 데이터셋/수집기, 외부 공급자, 공개 API나 저장 계약은 신설하지 않았다.

## 변경
- 기존 `ANSWER_TEMPLATE`을 `ai/src/agents/industry/domain/answer_policy.py`로 책임 단위 추출하고 거시 규칙 4개를 추가했다. retrieval.py는 이 단일 정책을 import한다. 모델/조회 실행 로직과 답변 정책의 분리이며 새 계층·래퍼를 만들지 않았다.
- 지표 수치·단위·관측 기간·자료 기준일·출처가 없는 부분은 미확인, 생성 시각으로 자료 기준일 대체 금지.
- 과거 공시를 최신 지표로 제시하지 않고 사실/해석/인과를 구분하며 이익 크기·주가 방향 예측을 금지.
- 청크/조회 결과의 지시문이 답변 규칙을 바꾸지 못하도록 명시.
- question/context/chunks 입력과 출력 payload, 인용 부착 및 실행 흐름은 유지했다.

## 직접 검증
- Python 3.10의 `-I -S`로 `ai/tests/industry/test_macro_prompt_isolated.py` 직접 실행: 6/6 통과.
- 테스트는 stdlib AST로 소스 상수 문자열만 읽는다. 제품 module/config/graph/LLM을 import하거나 실행하지 않는다.
- 기존 입력 placeholder, 빈 근거 안내/인용 규칙, 시점/출처, 인과·예측 금지 및 원문 지시문 경계 및 기존 경로의 단일 정책 import를 검사했다.
- 대상 `git diff --check` 통과.
- 코드 파일 줄수: retrieval.py 513줄(이 작업 전 533줄, 다른 동시 작업 전 측정), 정책 모듈 30줄, 격리 테스트 74줄. 기존 400줄 초과 retrieval.py를 증가시키지 않고 독립 검토 가능한 답변 정책만 분리했다. 나머지 기존 초과는 미해결이며 전면 재배치를 하지 않았다.

## 남은 경계
- 프롬프트 명시와 정적 회귀는 실제 모델 준수·최신 지표 정확성·거시 기능 완성 증거가 아니다.
- 별도 거시 모듈이나 금리/환율/물가/경기 시계열 원천은 현재 agents 트리에서 확인되지 않았다. Industry의 공시/그래프/청크 경로를 사용한다.
- 실제 공급자/모델·DB·브라우저·전체 pytest·배포는 실행하지 않았다.
- 지표 범위/원천/시점/갱신·비교 정책과 backend 반영 계약은 별도 합의·검증이 필요하다. 자료 부족을 최신 현황이나 0으로 채우지 않는다.

## 후속 근거 책임 분리
- 기존 retrieval.py의 근거 문맥·출처 deeplink·인용 표시 helper 17개를 application/evidence_context.py로 옮겼다. 조회/모델 실행 함수는 옮기거나 바꾸지 않았다.
- 이동 시 helper17개와 generate_answer/generate_cypher/answer_question/main 4개의 AST 동등성을 직접 확인했다. 동시 작업의 typed 검증 전달을 보존했다.
- 기존 retrieval helper import를 재노출해 report_export의 lazy import 호환을 유지한다. 함수 객체는 동일하며 _FILING_META/_SOURCE_NORM 캐시는 새 모듈 한 곳에서만 소유한다. RAW_DIR config import 위험은 기존과 같으며 안전 import라고 주장하지 않는다.
- 직접 재검증: 메모리 원천만 사용하는 근거 격리6/6, 거시 정책6/6, 기존 typed 검증·export 격리17/17 통과. 실제 config/graph/모델·원천 파일은 검사 입력으로 쓰지 않았다.
- 대상 diff-check 통과. 최종 분리 시점 retrieval.py 270줄, evidence_context.py 284줄로 두 파일 모두400줄 이하. 앞선513줄은 후속 이전의 이력이다.
- 독립 읽기 전용 리뷰에서 확정 회귀 결함 없음: HEAD 대비 이동17함수 AST 동일, cache 단일 소유와 lazy helper import 호환을 재확인했다. 실제 모듈/config import·공급자·DB·브라우저·전체 pytest는 여전히 미실행이다.
