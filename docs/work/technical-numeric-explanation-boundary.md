# CF059 · 정성 설명과 수치 근거 분리

기준 develop/HEAD는 `f8c2e0f51a560b9ab41b465ef5dc6dc7ebe39b0a`다. PR73~76 및 warmup/
confidence PR77의 실제 통합 뒤 `verith-technical-numeric-explanation`,
`fix/technical-numeric-explanation`에서 정본 CF059 v1.0의 정확 11파일로 구현했다.
원본 WIP·검증/실행 자료는 보존했다. 문서 정본 SHA는
`0a6ccbd8b73738872938ef3fc48bdd9c9c449cd1fe264eb6164231ec54e96c23`이다.

## 제품 경계와 tradeoff

LLM 문장은 정성 설명을 담당하고 실제 숫자는 기존 해당 지표 value/metrics에 남긴다. 맞게 복사한
측정값도 문장에서는 제한한다. 숫자 집합 whitelist나 metrics의 역산/반올림 재파싱을 사용하지 않는다.
순수 helper는 설정에서 만든 MA/RSI 식별자와 코드 고정 watchpoint를 지표·identifier/reference
역할·창/단위·필드에 결합한다. reference는 허용된 필드 전체의 코드 문구 일치이며 단순 RSI/선
키워드나 부분 문자열로 현재값 주장을 승인하지 않는다. MA watchpoint의 창 표기도 실제 설정에서
만들며 기본 문구는 그대로다.

실제 node.verify에서 기존 라벨·금지·구조·부가 필드 검사를 먼저 유지하고 고정 이유 코드의 실패를
결합한다. 네 detail 필드의 실패는 정확 indicator target/info로 기존 부분 fallback에 들어간다.
종합 본문·구조화 문자열/리스트는 기존 interpretation 블록으로 대체한다. 원문 숫자나 비밀을 새
오류 정보에 넣지 않는다. 선택 서술 필드의 missing/null/empty와 정상 다른 지표 설명은 유지한다.
계산·가중치·임계값·schema·재생성1회/전체최대4호출은 변경하지 않는다.

정확한 숫자 복사도 제한하므로 설명이 덜 구체적이고, 같은 지표 네 필드나 종합 블록 안의 정상
문장도 함께 대체될 수 있다. 코드 value/metrics와 fallback은 모델 응답으로 재검사하지 않는다.
숫자 없는 정상 정성 설명은 유지한다. 한글 수사·‘두 배/절반’·숫자 없는 관계 의미·모든 우회를
검증한 것이 아니며 완전 grounding이나 실제 모델 품질 완료로 보고하지 않는다.

## 검증

- 기존 graph99 회귀를 새 정성 fixture와 실제 verify 연결로 먼저 확인: **99 passed, guard0**.
  이전 mock은 코드 metrics를 LLM 문장에 복사했으므로 새 계약상 정성 응답으로 바꿨다.
  제품 validator를 patch하지 않았고 원래 숫자 복사 응답이 이제 거절되는 회귀도 포함했다.
- 최종 기존 보호 **technical-graph-unit 154 passed, guard0**, **technical-graph-self 9 passed**.
  지표/단위 차용·올바른 식별자·구두점·소수/콤마/부호/분수/과학표기/날짜/Unicode 숫자·reference의
  현재값 차용·4개 detail 필드·종합 문자열/리스트·None→0 금지를 검사한다.
- 실제 node의 기존 라벨 검사만 통과하는 숫자 주장에 새 실패가 결합됨을 확인했다. 실제 compiled
  graph/thread bridge/strict completion에서 해당 지표 네 필드만 대체·다른 지표 정성 설명 유지,
  종합 블록 대체, 재생성 정상 수용 및 원래 수치/개수/순서·confidence/score 보존을 확인했다.
- self는 실제 source pin guard를 닫힌 AST로 실행해 변조 거절을 확인하고 인접 입력은 허용하지
  않는다. 실제 순수 helper도 실행한다. 원격 기존 graph-self와 로컬 graph154 증거를 구분한다.
- source provenance 일치, 기존 64패키지 7,421파일 전후 snapshot
  `6abde22e2d8f13cd378761ae43c5a5b84a764631eeadd5fd7dcc9e2a6b15d0a4` 일치,
  자기 임시 root 제거·원 Backend .venv symlink 복구를 확인했다.

초기 독립 검토의 정상 구두점 과거절과 confidence 근거 개수 재서술 지시 모순은 수정했다.
수치·근거 개수는 코드 basis에 유지하며 LLM 문장에는 숫자로 반복하지 않는다. 최종 독립 검토와
정확 head 원격 CI/PR/merge는 로컬 검증 이후 결과로 별도 기록한다. 게시/머지 전 최신 develop·
준영 님 열린 PR·공통 계약/pin을 확인하고 그의 PR은 대신 머지하지 않는다. PR61 HOLD 유지.

외부 OpenAI/KIS·키/env 읽기·DB·설치·운영 활성화·추가 예약은0이다. 이전 실제 기록과 $0.70 hold는
보존한다. 이 개발 검증은 새 유료 호출이나 예약 해제를 승인하지 않는다.
