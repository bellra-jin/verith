# 결정적 fallback의 알려진 방향과 자료부족 점수 표현

2026-11-15. MD §17/SDD04·05가 요구한 0·음수·결측·흑적자전환·계산/표시한계 구분에 따른 AI 서술만의 보완이다.

기존 fallback은 value=None이면 모두 산출불가라 써서 이미 확인된 흑자전환/적자전환/저기저 회복 분류까지 누락했다. 이제 두성장지표의 status=not_meaningful이고display_value가있는 경우 그방향은 보존하며 퍼센트성장률은 표시하지않는다고 설명한다. unavailable의남은display값은 정상방향으로 승격하지 않는다. 기존0/음수/정상수치포맷은 유지한다.

insufficient_data의 표시점수0점을 정상재무평가 기준처럼 문장화하지 않고, 자료부족으로판정하지않으며 해당표시점수는정상재무평가점수가아님을 명시한다. score/label/점수산식·임계값·공용필드·호출·원가측정값은 바꾸지 않았다. 정상moderate등의 기존점수문장은 유지한다.

새4회귀중3개는수정전실패(81/84), 수정후전체84/84통과했다. known방향3종·허위%없음·진짜unavailable의staledisplay무시·known0·부족점수/정상점수 문맥을 검사하며, 실제 guard_llm_output과assess_verdict_stability에서도통과한다.

```powershell
# 기존보호runner,Python3.12/lock Pydantic2.13.4 의존성의별도환경
python -I ai/tests/fundamental/test_calculators_isolated.py
```

외부IO·파일쓰기·설정/비밀읽기 차단은 유지한다. 실제LLM응답·DART·LangGraph·HTTP·DB·저장/재조회·브라우저 수용을 검증한 것은 아니다. Backend/Frontend·PR61·유료호출·운영·Git게시 변경은 없다. 원문기업별검증자료·기간/회계단위·실측품질은 계속 별도수용이 필요하다.
