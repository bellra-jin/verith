# Supervisor 모델 근거의 원문 위치 정합성 v1

기존 [Supervisor core](supervisor-core-v1.md)의 policy2 model proposal에만 적용한다. 모델의 후보는 의미나 실행 권한을 결정하지 않는다.

`assess`는 Draft와 후보를 기존 strict 형식으로 검증하고, 각 mention/view/condition의 evidence 및 제공된 negation을 지정 source pair에 대조한다. source는 `(original_query, None)` 또는 현재 답변의 정확한 `(clarification_answer, answer_id)`뿐이다. 다른 답변이나 원질문으로 fallback하지 않는다.

원문에서 evidence.text의 겹치는 발생까지 포함해 정확히 한 번 일치할 때만 Python Unicode 문자 기준 start/end-exclusive를 만든다. 없거나 두 번 이상이면 거절하며 모델 offset으로 중복 중 하나를 선택하지 않는다. 공백·대소문자·Unicode 정규화, trim, fuzzy match, 의역은 없다. raw offset의 strict 정수 타입과 minimum은 그대로 요구하지만 숫자 자체는 위치 권위가 아니다.

입력을 변경하지 않고 새 후보를 만든 뒤 MeaningProposal을 다시 검증한다. 정합화 뒤 같은 항목이 된 중복도 기존 no_duplicate가 거절한다. 그 다음 기존 Grounding의 source/span·종목명·view·domain/kind/value·부정·기간 검사와 조건/명확화·동의 규칙을 그대로 적용한다. 불리한 후보를 버리거나 overview를 flow로 바꾸지 않는다. 위치가 맞는 회사명도 overview의 의미 근거가 되지 않는다.

deterministic scan, policy1, `validate_fixed_frame`, 이미 저장된 canonical frame과 준비/binding replay에는 이 변환을 적용하지 않는다. 저장된 잘못된 span을 원문에서 다시 찾아 복구하지 않는다. service와 private 품질 관측은 기존의 같은 `assess`를 사용한다.

wire v1/policy2 구조와 schema·모델·토큰/가격·도구·retry 제한은 유지한다. prompt는 최소 연속 근거·정확한 source·명시적 관점의 뜻과 회사명에서 overview를 추론하지 않는 원칙을 안내한다. 새 prompt SHA와 파생 의미 identity는 Backend mirror 및 AI의 두 정확 source pin과 일치해야 한다. 과거 소비된 spec/입력/epoch를 새 identity로 repin하거나 자동 재추출하지 않는다.

무키 회귀는 실제 `assess`와 `understand_v2`의 순수/합성 gateway 경로를 확인한다. 추가 실제 모델 호출·DB·키 접근이나 운영 활성화를 허용하는 계약이 아니며, 실모델 의미 품질 개선은 별도 미검증이다. [직접 검증 기록](../work/CF-038-supervisor-evidence-alignment.md)을 구분해 읽는다.
