# Industry 검증 출력의 모호성·주장 누락 차단

## MD 근거와 실제 결함
MD §18·SDD05의 미검증 verified 승격 금지와 검증 범위 보존을 따른다.
기존 parser는 finditer/last-wins로 모순된 중복 UNSUPPORTED→SUPPORTED, SUPPORTED 접두사·설명 속 문구, 범위 밖 index를 clean 판정으로 수용할 수 있었다.
또 답변 어디에든 '정보가 없다' 같은 문자열이 있으면 전체 답변을 refusal로 생략했고, [G1] 뒤의 실제 주장도 citation-only로 제거했다.
합성8개 검사 중6개 실패를 먼저 재현했다.

## 최소 수정과 상태
검증 출력은 비어 있지 않은 각 줄 전체가 단일 판정 형식이어야 한다. 중복(동일/상충), 범위 밖 번호, 접두사·설명·unknown label 등은 parse실패→indeterminate로 남기며 clean/verified로 승격하지 않는다.
기존 콜론/점/닫는괄호 번호 표기와 대소문자 호환은 유지한다. 누락 sentence index를 False/미검증 경고로 두는 기존 보수적 동작도 유지한다.
검사 제외는 알려진 완전 거절문장3개와 내용 없는 [G1]/[V1] 표식뿐이다. 복합 답변에서는 그 거절문장만 제외하며 나머지 사실·부정·유사 거절 표현은 검증기에 전달한다. 제외한 거절문장 자체는 경고 답변에서도 유지한다.
원문 답변을 보존하는 기존 verifier fail-open 동작은 유지한다. 모호성은 검증 상태의 fail-closed(indeterminate→기존 unchecked/판정 불가)이며 원문 전체 삭제나 공개 보류를 구현한 것이 아니다.
공용 필드/상태 enum·Backend·게시 권한·저장·provider/DB/운영 정책은 변경하지 않는다.

## 회귀
초기8개6실패→수정 후13/13.
정상 support/unsupported, 부분 누락, 중복/접두/설명/번호오류·unknown·빈출력, 완전 거절/부분 거절, 거절 문장+사실 복합, 부정 표현, 소수점·목록, bare ref/실제 주장 뒤 ref를 검사한다.
추가 실제 QA→faithfulness→내부 binding→export 회귀에서 모호출력 unchecked/판정 불가, 복합 unsupported 경고1개·거절문장 보존, 전체거절 verifier0과 ref-prefixed claim verifier1을 확인했다. 기존 export22/22.
수집 전 쓰기·설정/데이터 읽기·네트워크/DNS/subprocess 차단. 실제 source함수와 fake 검증기만 사용하여 실제 모델/자료/DB/서비스를 호출하지 않는다.

## 한계
이는 자연어 전체 분절·negation 의미·재무/기업 사실 진실을 보증하는 NLP 모델이 아니다. 알려진 거절문장 밖의 표현은 무검증으로 자동 생략하지 않는 보수 정책이며 일부 추가 verifier 호출이 생길 수 있다.
엄격한 형식을 따르지 않는 모델 출력은 실제로 유용해도 indeterminate일 수 있다. 합성 통과는 실제 모델 precision/recall·언어 커버리지 개선 실측이 아니다.
indeterminate 본문의 공개 보류/종합 제외·품질 revision은 공통 Backend 계약의 별도 통합 범위다. 이 패치에서 활성화/우회하지 않았다.

재현: C:/Verith/.venv/Scripts/python.exe -I -S ai/tests/industry/test_faithfulness_isolated.py
