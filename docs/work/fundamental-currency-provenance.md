# 원문 통화 누락과 KRW fallback의 내부 provenance 분리

2026-11-15. MD §17/SDD04·05의 통화·근거·미확인 보존과 검증 승격 방지에 따른 AI 내부 보완이다. 기존 currency 기본값만으로 원문에 KRW가 있었다고 볼 수 없었다.

## 형상/호환 경계

MetricValue에 새 필드를 넣는 안은 적용하지 않았다. 기존 dataclass7필드·asdict 키·일반dict 반환 형상을 유지하고, standardize_year_rows의 선택적 caller-owned currency_provenance 출력맵에 선택된 원문 행의 통화존재 여부를 보존한다. collect의 내부 metric_currency_provenance(year→metric→bool)를 calc/trend에 선택인자로 전달한다. same-filing first-wins와 최신선택의 값/통화/존재증거가 함께 움직이며, 유효원천으로만 파생한 부채는 그 provenance도 보존한다.

- 실제 새정규화 경로의 키없음/null/빈문자열/공백/비문자열은 False, 비어있지 않은 원문통화 문자열은 True다. 이는 필드존재 관측이지 ISO 통화code 진위/공급자 인증 증거는 아니다.
- sidecar가 제공되면 실제metric에 명시True가 있어야 한다. 부분map·없음·정수1같은 비boolean은 원문통화 미입증이다.
- sidecar 자체가 없는 구형 직접호출은 기존 수치호환을 유지하되 CURRENCY_UNPROVEN_LEGACY로 표시한다. 구형입력의 호환값을 통화검증 성공으로 승격하지 않는다. 이미 저장된 immutable 과거결과를 수정하거나 소급인증하지 않는다.

원문금액과 기존 KRW fallback 자체는 보존하되 새 실제원문미입증의 비율·성장률·EPS/BPS·금액trend 및 해당ROE 지점은 기존 unavailable/null로 보류한다. CURRENCY_UNPROVEN/TREND_CURRENCY_UNPROVEN 사유로 명시적다른통화·비KRW지원불가·원천계정누락과 구별한다. 매출통화가 미입증이면 그것으로 저기저 금액임계값을 적용하지 않는다.

## 검증 표시와 기존 소비자

기존 consistency_passed는 Backend 미러의 dict형태, DB nullableBoolean, writer의 그대로 전달값이며 AI payload도 기존bool 필드를 사용한다. 현재 재무 프론트 파일들에서는 이필드를 직접읽는 검증표시를 찾지 못했고, AIHTML은 기존 summary의 양수검증 조건으로 검증됨 배지를 만든다. 통화 미입증/불일치/단위한계는 기존 consistency_passed=False와 정보부족 reason으로 내려 검증됨으로 보이지 않게 한다. verdict 안정성을 뜻하는 기존 outcome과 다른검증 boolean은 임의성공/실패로 바꾸지 않는다.

대차균형도 미입증·다른통화 계정을 더하지 않고 비교보류 사유를 남긴다. 실제같은통화의 불일치는 기존VERIFY_BALANCE_IDENTITY_FAILED를 유지한다. 기존 숫자/점수표/임계값/호출·원가측정값을 새로 만들거나 환산하지 않는다. 지표보류는 기존점수산식에서 해당지표가 제외되는 영향이 있고, 추가한계flag는 기존confidence정책을 그대로 따른다.

## 직접 검사와 실제 반환 경로

```powershell
# Python3.12, lock Pydantic2.13.4 및 전이의존성이 있는 별도환경
python -I ai/tests/fundamental/test_calculators_isolated.py
python -I ai/tests/fundamental/test_accounting_basis_isolated.py
```

최종 계산/정규화/표시/스키마/HTML회귀80/80, collect/혼합/metadata전달7/7, 기존usage7/7 통과했다. 초기6개는 신규선택인자 미지원으로 테스트실행불가(70/76), 이후 부분sidecar/legacy/검증배지/균형검증 추가4개 실패(76/80)를 보완한 이력을 구분한다.

실제collect·calc·verify·report source의 함수body와 기존route를 안전하게 조립했다. 특히 실제report_node→실제FundamentalResponse.model_dump(mode='json')→엄격JSON/reportUUID→현재실제Backend미러Pydantic의 읽기전용 검증까지 통과했다. 전체wire/erd의 모든dict키에서 metric_currency_provenance/currency_provenance/yearly_metrics 유출이 없고, MetricValue/asdict 키7개도 그대로다. 저장payload consistency_passed=False 및 실제AIHTML에서 검증됨 없음도 확인했다. 공개DTO/Backend 파일·프론트 수정은 없다.

외부connect/DNS/subprocess·파일쓰기·설정/.env·임의프로젝트자료 접근은 수집전 차단한다. 실제app/LangGraph/HTTP/DB·저장왕복·공급자·브라우저나 전체AI pytest는 실행하지 않았다. 실제자료 통화/기간/단위의 진위·구형결과 이력증명 및 통화코드의 외부유효성 검증은 여전히 별도다. 이bool은 Backend usage_trusted/inventory_closed나 권한·정산증거가 아니다. 유료호출·운영·배포·Git게시 변경은 없다.

최종 source는 standardize95/calculators379/trend65/consistency76/state78/collect207/calc51/verify171줄, 신규test_currency_provenance205줄이다. HTML builder는 기존1025→1047줄의 기존초과파일로 사유표시구문만작게추가했고 무의미한분할은하지않았다.
