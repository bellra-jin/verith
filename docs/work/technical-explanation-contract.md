# Technical 설명 입력·재생성 계약 정합화

기준 develop: `fe10da4989b900f0969e54561a55514257f939a2` (PR80).

실제 한 건은 저장·본인 조회/타인 차단과 주봉 복구까지 성공했지만 종합 해석과 일부 지표 설명이
결정형 문구로 대체됐다. 제한된 진단에 numeric_claim_unsupported, label_conflict, forbidden_term이
남았다. 실패 후보 원문은 없어 특정 문장이 실제 위반이었는지 오탐이었는지는 확정할 수 없다.
numeric_claim_unsupported는 정성 설명 계약 밖의 숫자이며 실제 허위 숫자라는 뜻은 아니다.

재현 가능한 입력 계약의 모순을 고친다.

- 전체 must_avoid의 적용 범위를 interpretation_text로 명시하고 카드별 signal의 충돌 표현을 별도로 전달한다.
  반대 단어가 포함된 고정 본문 항목명을 강제하지 않는다.
- 고정 숫자 reference는 허용 필드 전체로 사용한다. 선택 필드에 무조건 긴 설명을 요구하지 않는다.
- 최초와 재생성에 동일한 전체 출력 형식·수치/금지/라벨 규칙을 제공한다. 제한된 실패 코드에
  해당 signal·생략 가능 여부·코드 소유 필드 예시를 결합한 수정 지침을 전달한다. 실패 후보는 되돌리지 않는다.
- 완성 예시는 기존 parser와 validator로 검사한 경우에만 입력에 제공한다. 지표 예시는 계산 규칙의
  정성 의미를 설명하며 원시 측정값을 복사하지 않는다.
- pattern 카드의 현재 캔들 신호와 차트 annotation의 장기 패턴 후보를 구분한다.

validator·금지어/수치/반대 라벨 보호·계산식/가중치·확정값·공개 schema·재생성 1회/최대 4호출은
유지한다. 선택 필드는 기존 생략/null/빈 문자열 백필 계약을 따른다. 문장이 짧아지거나 코드 문구가
표시될 수 있지만 정상적인 정성 설명을 일괄 제거하지 않는다. 예시 통과는 실제 모델 준수의 증거가 아니다.

기존 보호 graph 검사에서 실제 compiled graph와 가짜 SDK/OHLCV를 사용한다. 실제 API·키/env 읽기·
설치·DB·운영 활성화는 수행하지 않는다. 실제 실행 원본과 소비된 once 및 총 $1.10 보류는 불변이다.
검사 결과와 PR/CI 상태는 완료 후 아래에 기록한다.

이번 직접 검증 결과:

- 보호된 로컬 graph: **259 passed / guard 0**. 기존 compiled graph, 가짜 SDK/OHLCV,
  parser/validator, 부분 fallback, nullable, 사용량 증거와 송신 상한의 기존 회귀를 포함한다.
- 기존 self: **9 passed**. check_safe의 guard AST는 같으며 기존 소스/프롬프트 pin 4개만 갱신했다.
- 첫 검사 2실패는 테스트 기대값 오류였다. 프롬프트 본문 설명과 실제 payload key를 혼동한 확인,
  성공 trace status를 passed로 기대한 확인을 실제 payload와 success 상태 검사로 수정했다.
- 자기 임시 검사 자원은 정리됐다. 실제 제공자·새 DB/예약은 사용하지 않았고 실모델 품질은 미재검증이다.
