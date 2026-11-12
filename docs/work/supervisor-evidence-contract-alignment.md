# Supervisor 추출 계약과 복합 근거 정합성

기준 develop `abc4daaa3429a006a05062e8d9e58ba459350005`, 전용
`fix/supervisor-view-evidence-period` 작업이다. 실제 ordinal5 source/input/기록과450m은
동결 보존하고 새 모델·count·키/env·DB·예약·활성화는 실행하지 않았다.

## 확인한 문제와 변경

실제 회차에서 모델은 Flow 근거로 원문과 정확히 일치한 `3주 수급`을 제안했고, add_view의
정확한 관점 어휘 검사에서 VIEW_EVIDENCE_MISMATCH로 거절됐다. 전체 후보는 보존되지
않았으므로 다른 필드가 모두 올바르다거나 회사 해석까지 성공했다고 추정하지 않는다.
정산 ACK와 저장된 명확화/unsupported 조건·waiver 및 정리는 관측됐지만 의미 수용은 실패다.

단편 금지 문구 대신 prompt의 역할·출처·완성 입출력 예시와 schema의 세 배열 설명을
함께 정리했다. JSON 필드·타입·required·범위는 description 세 개를 제거한 hash로 이전과
동일함을 검증한다. Backend mirror/파생 semantic SHA와 AI 세 exact pin을 일치시킨다.
과거 semantic은 역사 hash로 복원해 보존하며 과거 소비 spec을 repin하지 않는다.

model-only align에서 정확한 전체 근거 검증 후 양의 PERIOD+공백/탭+유일 Flow 어휘만
같은 source의 최소 관점 span으로 정렬한다. 같은 source 기간1개·어휘1개·경계·기존 기간
parser·인접 부정 부재를 모두 요구한다. 그 외 근거는 원래대로 남겨 기존 validator가 거절한다.
Grounding 전체 class·stock_name_shape·validate_fixed_frame·assess AST는 기존과 동일하다.
전체 scan이 다른 조건·부정·관점·잔여를 계속 보존하며 모델 후보/원 Draft는 mutate하지 않는다.

## 별도 H01–H14 평가

이 질문은 새 few-shot 초안을 보지 않은 별도 검토자가 제공했다. prompt 예시에 복사하지
않았으며 질문 목록이 예시 입력과 겹치지 않는 단언도 둔다. 결과는 수작업 typed 후보와 실제
parser/plan 경계의 회귀이며 모델 생성 정확도나 시장 종목 조회 성공률이 아니다.

| 사례 | 검증한 경계/결과 |
|---|---|
| H01 | raw 한미약품·flow·기관 exclude/빼고·4주 unsupported 보존 |
| H02 | LG전자·자금 흐름·외국인 focus·최근5거래일 보존, 일로 환산/honored 없음 |
| H03 | technical 부정과 flow 요청 분리 |
| H04 | technical/fundamental/flow 모두 유지, partial 장벽과 새 실행 없음 |
| H05 | 기아/flow만, overview·주체·기간 기본값 없음 |
| H06 | 035720 raw 코드 유지, 회사 이름 생성0·개인 제외/9일 보존 |
| H07 | 두 raw 회사와 multi_stock 명확화, 첫 회사 선택0 |
| H08 | 부정 한국전력/활성 대우건설 분리 |
| H09 | 반복 기관 근거를 offset으로 고르지 않고 거절, scope 충돌 유지 |
| H10 | 반복 flow 근거/부정을 임의 발생 선택으로 해소하지 않고 거절 |
| H11 | holding 복합 근거 거절·잔여 보유 문맥 유지·실제 start가 clarify/needs_clarification, ready0 |
| H12 | 어제 부정·오늘·기관 focus·순매도 보존, 절대 날짜 생성0 |
| H13 | stock/주체 답변의 정확 answer_id와 질문의2개월/관점 분리 |
| H14 | 다른 답변의 부정 차용 거절, 올바른 source pair만 보존·동의 생성0 |

H11에서 기존 PERIOD는100주를 unsupported 기간으로 라벨할 수 있다. 이는 해결한 의미
분류가 아니라 기존 parser 한계다. 보유 중 잔여로 meaning 장벽이 남아 실행 가능한 plan이
되지 않음을 확인하며, 보유 수량을 정확히 이해했다거나100주 기간이 확정됐다고 채점하지 않는다.

추가 회귀는 관측 복합 근거의 최소 span/조건 ID/waiver 보존, 다른 기간·Flow 어휘,
혼합 주체/관점·반복/여러 기간·부정·범위 밖 값·다른 답변 출처·canonical 중복 거절과
fixed frame/replay·deterministic 경계 불변을 확인한다. 실제 저장 plan의 기간/제외 조건은
기존 scope_confirmation/waiver 장벽에 남기며 이 작업에서 실제 분석을 실행하지 않는다.

최종 보호 meaning-self 7개·meaning-unit 355개·live-controller-self 5개가 통과했다.
unit guard 위반은0이며 각 보호 회차의 자기 임시 root 제거를 확인했다. 독립 source/규칙
검토에서 구체 차단 결함은 없었다. Ready PR/정확 head CI 결과는 로컬 인계에 별도 기록한다.
실제 LLM이 새 예시·규칙을 따르는지는 새 구체 호출 승인 뒤의 별도 검증이며 이번에 호출하지 않았다.
