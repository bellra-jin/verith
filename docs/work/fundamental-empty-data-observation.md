# Fundamental 일반 부족 응답의 관측 보존

## 기존 계약 대조
고도화 MD §17의 근거 부족 표시와 호출별 사용량 작업의 unknown/0 구분을 따른다.
docs/contracts/fundamental-analysis-v1.md와 fundamental-ai-call-usage.md의 #88 연계 계약에서 cost_summary는 호환용 관측/부분합이다. authoritative inventory·독립 provenance·토큰 전체성·complete_usage·신뢰·금액·정산 ACK가 아니다.
정상 verify_node도 retrieval_summary의 financial_network_calls/probe_network_calls를 기존 cost_summary에 복사한다.

## 수정과 의미
일반 empty_data도 혼합 회계기준 부족 응답과 동일하게 수집 결과의 financial_network_calls를 보존한다. source == dart인 source record 수라는 기존 의미 그대로이며 HTTP retry/실패 전송 전체 개수나 비용을 추정하지 않는다.
latest probe는 source == dart와 latest_report_probe reason을 함께 충족한 record만 센다. 캐시 probe 제외. probe는 financial source 전체의 부분집합이므로 두 수를 합산하지 않는다.
관측 없는 부족 응답은 null, 관측된 cache-only는 0이다. 수집 전에 unsupported_ticker로 거절된 경로만 수집 없음이 확인되므로 기존 0을 유지한다.
LLM 미실행 0과 토큰 null, 응답 schema, 검증 summary/품질판정, count-only·keep_reservation·Backend·Supervisor·call_usage 계약은 변경하지 않는다.

## 합성 검증
추가 3회귀가 수정 전 실패(8/11). 수정 후 일반 empty network/cache, latest probe/cache, 미관측 null, unsupported 수집 전 0, 혼합 기준, 원본 사업연도 차단 및 기존 경로를 확인한다.
기존 격리 러너가 소스 수집 전 파일쓰기·비밀/설정읽기·외부 네트워크/DNS/subprocess를 차단한다. 실제 DART/LLM/DB/HTTP 서비스는 실행하지 않는다.
프로바이더별 실제 retry·오류/불확실 전송의 durable inventory와 #88 trusted 연결은 여전히 미구현/미수용이며 이 수정으로 해결되었다고 주장하지 않는다.

최종 직접 실행: collect/report 격리 12/12, 계산·정규화·표시 113/113 및 git diff --check 통과. 독립 리뷰 요청.
