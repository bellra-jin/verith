# CF038 · Supervisor 근거 원문과 위치 정합성

PR42 병합 develop `fbd08e92af3c25d1eee3bf2c14db209e97ee1bcf`에서 전용 branch로 분리했다. [제품 계약](../contracts/supervisor-evidence-alignment-v1.md)을 적용하며 이전 진단 PR·실제 실행 입력/원문/once·private 사본과 다른 WIP는 보존한다.

실제 직전 요청은 generation 응답·usage/정산 ACK가 관측됐지만 views[0]의 근거 text와 원문 span 불일치로 거절됐다. 이 변경은 모델 숫자 offset을 믿는 대신 지정 source의 유일한 exact text로 위치를 결정한다. 위치가 정합화돼도 당시 overview 후보는 기존 의미 검사에서 계속 거절된다. 이를 성공으로 바꾸거나 이전 미보존 응답의 원인으로 소급하지 않는다.

변경은 model-only 순수 전처리, 짧은 prompt 안내, Backend 의미 mirror, AI 두 파일 pin, 기존 self/단일 unit과 문서2개인 정확8경로다. source 선택/AI32 경로·guard/worker·gateway/verifier/meaning_service·schema·패키지·실행기·DB·Frontend는 변경하지 않았다. 입력/중첩 객체를 mutate하지 않고 변환 전후 strict 검증을 수행하며 기존 no_duplicate와 Grounding을 재사용한다.

새 prompt SHA는 `0456f2afc6939b45a61c6d59159bd42a8e807647c656b15fb7ed23a0bf7714c4`, 파생 의미 SHA는 `8a873009b7bf71f78b90efbf495ecd920ea12a8027f0ad629b5a530759f3c943`다. 모델·가격·caps·schema identity는 이전과 같다. 과거 prepared/consumed spec은 갱신하지 않는다.

## 직접 무키 검증

기존 clean env와 절대 Backend Python의 `-I -S -B`로 `check_safe.py meaning-self`와 `meaning-unit`만 실행했다. 보호 self3·단일 unit110개가 통과했고 guard 위반0·parent exit0·자기 임시 root 제거를 확인했다. 실제 provider·키/.env 내용·DB·새 예약·설정 활성화는 없다. 기존 누적350m 보수 예약과 소비된 실행 기록은 불변이다.

실제 함수로 한국어/공백/비BMP의 Python 좌표·입력 불변성, raw strict 타입/minimum, 없는/반복/겹치는 exact text, 잘못된 source pair/answer ID와 fallback 거절, 정합화 후 중복, answer-relative 좌표, 부정/기관·외국인/기간·단위/OFS·CFS, 잘못된 overview의 계속된 거절을 확인했다. 같은 `understand_v2`의 합성 gateway는 한 번만 호출되고, deterministic/policy1·저장 frame의 잘못된 span 거절과 기존 digest/replay 검사는 유지된다.

새 model-only 계약과 직접 충돌하는 기존 raw out-of-range 좌표 거절은 missing-text 거절로 바꾸고, 새 별도 회귀에서 잘못된 양수 offset의 정합화를 확인했다. 두 번 나타나는 ‘말고’를 지정한 기존 성공 fixture는 유일한 연속 ‘어제 말고’ 근거로 바꿔 기존 embedded negation 의미를 유지했다. 다른 의미/출처 거절 단언은 삭제하지 않았다.

첫 unit은108통과·2실패였다. 정합화 후 no_duplicate가 Pydantic ValidationError로 감싸지는 기대를 바로잡고, 잘못된 저장 frame fixture가 함수 전에 model validation으로 거절되던 구성을 실제 `validate_fixed_frame` 호출로 바꾼 뒤110개가 통과했다. 제품 수용 규칙은 이 실패 때문에 바꾸지 않았으며 원문 실패 로그도 비공개 검사 기록에 보존한다.

독립 소스 리뷰와 원격 exact-head CI/게시 결과는 해당 단계에서 별도로 기록한다. 현재 무키 통과를 실모델 품질·실제 인증/PG·production Supervisor→Flow 전체 수용으로 표현하지 않는다. 추가 실제 호출·ordinal4·새 발급/예약은 이번 범위 밖이다.

독립 최종 읽기 검토에서 추가 필수 결함은 없었다. 공개 원형6파일·제품 AST의 model-only 변경·기존 Grounding/fixed-frame 보존, AI32 집합/기존30개 pin·prompt/semantic mirror와110개 통과 로그를 대조했다. 리뷰 측은 검사를 재실행하지 않았으며 원격 CI 결과를 대신하지 않는다.
