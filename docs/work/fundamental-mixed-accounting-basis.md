# 혼합 회계기준의 안전한 자료부족 차단

2026-11-15. 고도화 상세설계 §17 및 SDD05의 기간별 CFS/OFS 보존·비교 가능성 확인 요구를 따른다.

## 문제와 계약 경계

기존 collect는 앞 연도CFS를 얻은 뒤 다음 연도CFS가 없으면 OFS로 fallback하고 이후 연도도 OFS로 조회했다. 같은 결과가 CFS/OFS 수치를 섞어 계산하면서 보고서에는 단일OFS로 표시될 수 있었다. 실제 소스 loop AST와 합성 fetch로 재현했다.

공용 FundamentalRequest/FundamentalResponse schema나 Backend/Frontend 계약을 추가하지 않고 AI 내부의 기존 empty_data→report→insufficient_data 경로를 재사용한다. 연도별 실제 결과가 비어 있지 않은 정규화값을 만들 때 회계기준을 내부 집합에 기록한다. CFS/OFS 혼합이면 MIXED_ACCOUNTING_BASIS와 명시 사유를 내고, 계산용 yearly_metrics는 비우고 단일 fs_div는 빈문자열(미확인)로 둔다. source_records·retrieval_summary·dart_calls는 보존한다. 주식수/추가 insight 조회와 계산·성장률·추세·LLM 경로는 실행하지 않는다.

혼합의 부족 응답은 미실행 검증을 True로 승격하지 않고 네 검증 boolean을 False로 둔다. 기존 outcome=insufficient_data, 빈 ratios/trend/evidence 및 기존 score0·confidence0.3 부족 표현은 유지한다. 동일 혼합 입력 자동 재시도를 유도하지 않도록 failure.retryable=False다. 실제 network source 수 및 latest_report_probe 표시가 있는 network probe 수를 기존 cost_summary 필드에 보존한다. 캐시 probe는 network로 세지 않으며, 입력에는 관측이 없으면 null을 유지한다. 원가/신뢰/정산을 판정하지 않는다.

## 직접 검사

```powershell
# Python3.12 및 lock Pydantic2.13.4 의존성이 있는 별도 환경
python -I ai/tests/fundamental/test_accounting_basis_isolated.py
```

실제 collect/report 함수 body와 기존 workflow의 route lambda, 실제 Pydantic schema를 사용하되 공급자·source summary·history sink는 합성 주입한다. 수집 전에 connect/DNS/subprocess/파일쓰기/.env/프로젝트 비Python자료 읽기를 차단한다. 실제 graph·app·config·DB·공급자를 import/호출하지 않는다. AST 함수 조립과 실제 LangGraph/HTTP 통합은 구분한다.

6/6 통과:
- CFS→OFS 혼합은 계산 입력이 없고 추가 shares/insights 조회0, source 증거 보존.
- 기존 스키마의 자료부족 응답, 검증승격 없음, 빈 결과/단일기준 미확인, LLM0.
- latest probe3중 network2/cache1과 financial network4를 구분하여 관측DART6/probe2 보존.
- 동질CFS 정상 경로 유지.
- 첫해부터 동질OFS fallback 및 명시OFS 정상 경로 유지.
- 진짜 empty_data의 기존 사유·분기 유지.

이 변경은 기간별 기준을 가진 완전한 결과 export나 CFS/OFS 비교 가능성 정책을 구현한 것이 아니다. 혼합자료는 안전하게 막는 임시 보수 경계다. 향후 유효한 연도별 결과를 함께 보여주려면 AI export·Backend/Frontend 소비 계약을 협의해야 한다. 실제 자료·저장/재조회·화면 수용 및 전체 AI suite는 미검증이다. Backend/Frontend·PR61·유료호출·운영·배포·Git게시 변경은 없다.
