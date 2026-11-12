# Supervisor 종목 mention과 수급 조건 안내

기준 develop `27789fce42d41a80f14c3821541d62aa5ae3fa18`의 별도
`fix/supervisor-stock-mention-guidance` 작업이다. 폐쇄 복구 실행 코드·private 자료·소비 기록을
이 브랜치에 편입하지 않는다. 이 제품 변경은 모델 안내와 기존 엄격한 검증의 정합성에 한정한다.

## 관측 결과와 한계

승인된 실제 질문 회차는 count/generation 각1회와 응답·사용량·정산 ACK 후 의미 rejected로
종료됐다. 보존된 항목은 `mentions` index1의 `외국인`, 원문 span5:8이며 텍스트 일치가
확인됐다. `MENTION_NAME_SHAPE_REJECTED`는 add_mention의 종목명 shape 검사가 수급 주체를
정상적으로 거절한 결과다. 전체 후보가 보존된 것은 아니므로 다른 부정 조건/기간의 누락이나
나머지 모델 분류를 추정하지 않는다. 이 결과를 이전 미보존 실패의 유일한 원인으로도 쓰지 않는다.

관측 사용량은 input900/output477/total1377/cached0, 고정 단가의 관측 추정은
$0.0028215이며 청구서 확정액이 아니다. 원 총400m 보수 예약과 모든 실제 자료는 보존하고
새 예약·재호출은 하지 않았다. 독립 postflight에서 PID 종료·lock 해제·claim 보존·False 원복,
정확 소유 컨테이너/소스 사본 부재와 closed·정산/cleanup ACK를 확인했다.

## 최소 제품 변경

기존 prompt는 view 정의를 설명했지만 mentions가 종목/회사 이름 전용이라는 필드 구분을
명시하지 않았다. 기존 stock_name_shape는 외국인/기관/개인을 거절하며 parsed_condition은
flow focus/exclude로 처리하므로 그 엄격한 경계는 바꾸지 않는다. prompt에 필드 분류,
제외 주체의 별도 인접 부정 span, 원 기간/단위 및 서버의 지원 여부 판단을 명시했다.

변경은 prompt, Backend semantic mirror/파생 SHA, 정확 source pin/self, 기존 meaning unit,
기존 core 계약과 이 기록의 7파일이다. schema/DTO·grounding·deterministic·fixed frame/plan·
gateway·가격·한도·권한·owner·동의 검사는 그대로다. 의미 계약은 prompt SHA 하나만 변한다.
기존 소비 spec/입력이나 운영 정책을 새 spec으로 repin하거나 자동 갱신하지 않는다.

## 검증

기존 보호 meaning-self 7개·meaning-unit 312개 통과, guard0·자기 임시 root 제거 확인.
직접 변경한 prompt pin 단언의 기존 live-controller-self 4개도 통과했다.
실제 assess/understand_v2에서 관측 오분류와 기관/개인 및 명시 부정의 변형을 계속 거절했다.
올바른 합성 후보의 회사/flow/주체 제외/인접 부정/3주 분리를 확인하고, 미지원 기간·partial
확인/waiver 장벽과 잘못된 답변 출처·누락/차용 부정 거절을 유지했다. 원 후보 불변 및 과거
semantic spec 복원 hash로 prompt 이외 변경0을 대조했다.

새 실제 provider·key/env·DB·예약·서비스 활성화는0이다. 이 합성 검사는 모델이 새 안내를
따른다는 실제 품질 검증이 아니다. 독립 검토·Ready PR/정확 head CI와 정상 merge 결과는
로컬 검사 및 실제 의미 실패와 구분해 인계한다.
