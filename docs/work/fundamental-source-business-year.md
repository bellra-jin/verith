# Fundamental 원본 사업연도 오귀속 차단

## 근거와 범위
고도화 상세설계 v1.0 §17 계산·근거 계약은 비교 전 기간 검사와 수치→계정·공시·출처 연결을 요구한다.
공식 [DART 전체 재무제표 가이드](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS003&apiId=2019020)의 응답 bsns_year는 사업연도이고 thstrm_amount는 당기금액이다. frmtrm_amount/bfefrmtrm_amount는 별도 전기/전전기 컬럼이다.
실제 dart_client.fetch_financials는 payload list 원문을 그대로 반환하고 source_policy도 연도 컬럼을 변환하지 않는다. standardize_year_rows는 thstrm_amount만 읽지만 원본 사업연도를 확인하지 않고 요청 fiscal_year를 부여했다.

## 수정
원본 bsns_year가 ASCII 네 자리로 명시되고 요청 사업연도와 다르면 정규화에서 제외한다. 전기값으로 재해석하거나 금액/요청연도를 임의 변경하지 않는다.
다른 연도의 최신 공시가 올바른 행을 덮어쓰거나 파생 부채에 섞이는 것도 차단한다.
누락/null/공백/비정형 원본 연도는 이번 명시적 불일치 검사 밖의 기존 호환 경로다. 기간이 입증됐다는 의미가 아니며 원천 기간 검증 전체 완료를 주장하지 않는다.
MetricValue/공용 응답 필드, Backend/Frontend, 비용 예약·정산, Supervisor는 변경하지 않는다.

## 검증
수정 전 두 새 회귀가 실패(111/113), 수정 후 계산·정규화·표시 합성 회귀 113/113.
실제 collect/report 함수의 격리 합성 검증에 다른 사업연도만 들어온 경우를 추가했다. 계산/추가 수집 없이 기존 insufficient_data 응답으로 닫히고 ratios/evidence/trend 수치가 비어 있다.
선택된 올바른 원본의 통화 sidecar, 같은 사업연도 0, legacy 음수/누락 연도 호환을 검사한다.
네트워크·환경/자격·DB·모델 접근과 쓰기를 수집 전 차단한 기존 검사만 사용한다. 실제 DART 호출·운영·유료 호출·전체 pytest/graph 수용은 실행하지 않았다.

## 남은 한계
report code/기간 길이/corp_code 및 원천 정정공시 대체 관계의 완전 검증은 별도다. 사업연도 일치만으로 이를 입증할 수 없다.
일반 empty_data 응답의 기존 cost_summary는 0 고정이며 retrieval_summary에는 관측 호출이 남는다. 이번 패치에서 비용 보고·정산 계약을 임의 변경하지 않았다.
독립 리뷰 후 최종 판정한다.

후속: 일반 부족 응답의 기존 0 고정 관측은 [별도 개선](fundamental-empty-data-observation.md)에서 실제 source 관측/null 구분으로 수정했다. 금액·정산 계약은 여전히 변경하지 않았다.
