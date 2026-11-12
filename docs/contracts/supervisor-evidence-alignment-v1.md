# Supervisor 모델 근거의 원문 위치 정합성 v1.1

기존 [Supervisor core](supervisor-core-v1.md)의 policy2 model proposal에만 적용한다. 모델의 후보는 의미나 실행 권한을 결정하지 않는다.

`assess`는 Draft와 후보를 기존 strict 형식으로 검증하고, 각 mention/view/condition의 evidence 및 제공된 negation을 지정 source pair에 대조한다. source는 `(original_query, None)` 또는 현재 답변의 정확한 `(clarification_answer, answer_id)`뿐이다. 다른 답변이나 원질문으로 fallback하지 않는다.

원문에서 evidence.text의 겹치는 발생까지 포함해 정확히 한 번 일치할 때만 Python Unicode 문자 기준 start/end-exclusive를 만든다. 없거나 두 번 이상이면 거절하며 모델 offset으로 중복 중 하나를 선택하지 않는다. 아래의 닫힌 복합 근거 규칙 외에는 텍스트를 바꾸지 않는다. 공백·대소문자·Unicode 정규화, trim, fuzzy match, 의역은 없다. raw offset의 strict 정수 타입과 minimum은 그대로 요구하지만 숫자 자체는 위치 권위가 아니다.

입력을 변경하지 않고 새 후보를 만든 뒤 MeaningProposal을 다시 검증한다. 정합화 뒤 같은 항목이 된 중복도 기존 no_duplicate가 거절한다. 그 다음 기존 Grounding의 source/span·종목명·view·domain/kind/value·부정·기간 검사와 조건/명확화·동의 규칙을 그대로 적용한다. 불리한 후보를 버리거나 overview를 flow로 바꾸지 않는다. 위치가 맞는 회사명도 overview의 의미 근거가 되지 않는다.

deterministic scan, policy1, `validate_fixed_frame`, 이미 저장된 canonical frame과 준비/binding replay에는 이 변환을 적용하지 않는다. 저장된 잘못된 span을 원문에서 다시 찾아 복구하지 않는다. service와 private 품질 관측은 기존의 같은 `assess`를 사용한다.

wire v1/policy2 구조와 schema의 필드·타입·required·범위 및 모델·토큰/가격·도구·retry 제한은 유지한다. schema의 mentions/views/conditions 설명 metadata와 prompt를 함께 정의한다. 새 prompt/schema SHA와 파생 의미 identity는 Backend mirror 및 해당 AI 세 파일의 정확 source pin과 일치해야 한다. 과거 소비된 spec/입력/epoch를 새 identity로 repin하거나 자동 재추출하지 않는다.

## 역할과 완성 예시

mentions는 원문 회사/종목 이름 또는 입력된 6자리 코드만이다. views는 명시된 관점 어휘이며 회사명이나 수급 주체가 아니다. conditions는 주체 focus/exclude·원 기간/단위·cutoff와 부정을 보존한다. 각 부정은 같은 source의 인접 span이어야 하고 typed 답변은 실행 동의가 아니다. prompt의 완성 Draft/MeaningProposal 예시 8개는 단순 수급·차트·복수 관점·모호한 raw 이름·입력 코드·종목 미지정·제외/기간·지정 답변 출처를 구분한다. 예시 자체는 종목 정본화나 실행·지원 판정이 아니다.

## 양의 기간 + Flow 어휘의 닫힌 정렬

먼저 제공된 근거 전체를 정확 source pair의 유일한 원문 span에 대조한다. 그 후 model view=flow이고 supplied negation=None인 경우에만, 근거가 **기존 PERIOD 하나 + 공백/탭 + Flow 어휘 하나**로 완전히 분해될 수 있는지 검사한다. 같은 named source에 PERIOD가 하나뿐이고 추출할 Flow 어휘도 유일해야 하며, 근거 경계가 다른 이름/단어 내부를 자르지 않아야 한다. 기존 parsed_condition이 같은 기간을 flow/period로 검증하고, 좁힌 관점에 인접한 부정도 없어야 한다.

모든 조건을 만족하면 동일 source/answer_id·원문 내부의 정확 Flow 부분만 새 view evidence로 만든다. 예를 들어 `3주 수급`의 관점 근거는 `수급`이 된다. 기간을 새로 만들거나 지원된 것으로 바꾸지 않는다. 기존 전체 source scan이 `3주`를 unsupported 조건으로 보존하고 같은 condition ID/waiver·명확화/부분 동의 장벽을 유지한다. 다른 주체·부정·관점·잔여 문구도 삭제하지 않는다.

부정·수급 주체·다른 관점·둘 이상의 기간·반복/모호한 어휘·holding 문맥 등이 근거에 섞이거나 parser가 확인하지 못하면 정렬하지 않는다. 기존 add_view가 이를 거절하며 다른 후보를 버려 수용하지 않는다. 기간 뒤 관점 순서 외의 일반 복합 근거는 허용하지 않는다. 변환 후 canonical 중복도 계속 거절한다. deterministic scan·저장 frame·replay는 이 규칙을 사용하지 않는다.

## 독립 평가와 한계

prompt를 보지 않고 작성된 H01–H14는 few-shot 예시로 복사하지 않고 기존 단일 meaning unit의 별도 수작업 후보/parser 평가로 둔다. 의미 보존·exact 출처/부정·유일한 분리/모호성·waiver/실행 장벽을 확인하며 실제 LLM 정확도·시장 종목 조회·실제 실행 결과가 아니다. `100주 보유 중`은 새 정렬이 잔여 문구를 지워 수용하지 않지만, 기존 PERIOD가 `100주`를 unsupported 기간으로 라벨할 수 있는 한계가 남는다. 보유 문맥은 unrecognized/meaning으로 남아 ready가 되지 않으며 이를 보유 수량의 정확한 이해로 채점하지 않는다.

무키 회귀는 실제 `assess`와 `understand_v2`의 순수/합성 gateway 경로를 확인한다. 추가 실제 모델 호출·DB·키 접근이나 운영 활성화를 허용하는 계약이 아니며, 실모델 의미 품질 개선은 별도 미검증이다. [직접 검증 기록](../work/CF-038-supervisor-evidence-alignment.md)을 구분해 읽는다.

이번 bundle의 변경·평가 결과는 [추출 계약 정합성 기록](../work/supervisor-evidence-contract-alignment.md)에 분리한다.
