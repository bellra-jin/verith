# Flow · 제공 관측기간과 단기·장기 안내

CF-005 v1.1의 표시/입력 정책이다. [Python helper](../../../src/agents/flow/domain/observation_window.py)와
[TS helper](../../../../frontend/src/features/flow/lib/observation-window.ts)는 기존 v1 daily/persistence를
읽어 view 상태만 만든다. 새 payload 필드·저장 metadata·계산 정본이 아니며 원본 숫자를 대체하지 않는다.

## 근거와 상태

현재 caller의 단기5/장기20 기준을 사용한다. daily1~20행은 canonical ISO date·고유·엄격 오름차순이며
개인/외국인/기관 값이 bool 제외 유한 숫자여야 한다. 세 주체 persistence의 sum_5/sum_20·실제 bool인
consistent가 모두 있어야 한다. 제공된 최근 최대5/20행의 합과 저장 합은 rel_tol1e-9/abs_tol1e-6으로
가깝고, **각 저장/유도 합의 음·0·양 부호도 별도로 같아야 한다**. consistent는 두 합이 같은 비영 부호인지
유도·저장 양쪽에서 대조한다. 0/-0은 같은0이며 원값은 보존한다.

표시 근거의 합산은 Python/JS 모두0.0부터 순차 binary64 덧셈을 사용한다. Python3.12 sum의 보상 합산을
사용하지 않는다. 상쇄·overflow 등으로 저장 합과 이 근거가 맞지 않으면 unknown이며 생산 계산/Gate2를
바꾸거나 저장 합을 재계산해 대체하지 않는다. helper 통과도 제공 자료의 내부 정합 근거일 뿐이다.

| 상태 | 안내 |
|---|---|
| insufficient: 제공1~19행, 내부 정합 | 실제 제공 수를 표시하고 지속성 결론·일관 배지를 보류 |
| sufficient_rows: 제공20행, 내부 정합 | 제공 자료 기준 단기5/장기20 관측 비교. 양·음 동일부호/반대부호/합0 포함을 각각 구분 |
| unknown: 누락/손상·타입·날짜·정합 불명 | 계산창 관측기간 미확인·비교 보류. 유효한 저장 숫자는 보존 |

20행도 시장 거래일 완비·원천 계산창·수집 누락 없음·거래정지/휴장 coverage를 보증하지 않는다.
강도 재검산에 필요한 거래대금도 daily에 없으므로 이를 검증했다고 하지 않는다. 기존 data_status는
price_daily 의미를 유지하며 상태나 Gate 결과를 이 view로 덮어쓰지 않는다.

## 표시와 해석

배열/row/date/유한수 방어를 순회·산술·포맷 **전에** 사용한다. 잘못된 셀/행을0으로 채우거나 제거·정렬해
정상20행으로 만들지 않는다. 안전하게 표시할 수 없는 daily는 placeholder, 없는 persistence 셀은
자료 없음이다. 정상0·기존 숫자의 포맷/막대는 유지한다. 정상 persistence/ratio를 malformed daily 때문에
0으로 덮어쓰지 않는다. 이 방어는 일별·기간 표시 경로이며 모든 report JSON의 렌더 안전성 보장은 아니다.

강도·구도·기관 세부는 제공 관측/미확인 기준으로 설명하고 고정5/20거래일 확보를 단정하지 않는다.
Gate2 규칙5의 **성공 설명 문구만** 실제 대조 행수와 기간 검사 아님을 알린다. 기존 산술/허용오차·passed/
failures와 저장된 과거 checks는 유지한다.

LLM facts는 같은 상태를 사용한다. 부족/미확인이면 persistence 합/consistent 비교를 공급하지 않고
결정론적 비교 보류 안내를 제공한다. 충분한 행수에서도 제공 자료 기준이며 합0을 방향 상이로 바꾸지 않는다.
이는 입력·지시문 개선이지 실제 모델의 기간 주장 전체 준수나 새로운 Gate3 의미 검증이 아니다.

기존 interpretation 원문은 수정·재생성·숨김·삭제하지 않는다. 본문 가까이에 저장 당시 해석임과 관측
부족/미확인 경고를 표시한다. interpretation이 없어도 검증 배지 옆에 저장 당시 대조 결과·기간 비보증
안내가 남는다. 원문에 있는 과거 기간 주장을 제거한 것이 아니라 한계를 고지하는 정책이다.

## 검증 경계

[공통 합성 fixture](../../../../frontend/tests/fixtures/cf005-observation-cases.json)는 양쪽 helper의 상태·수·부호
경계를 고정한다. 기존 보호 entry에서 실제 helper와 정확히 추출한 `_facts_to_text`/`_daily_view`/
`_persistence_view`만 실행한다. 단일 HTML은 source-only exact copy이며 Jinja를 실행하지 않는다.
TSX 경고·방어 사용은 source/AST 배선 검사다. React DOM·브라우저·pandas/Gate2 런타임·AI 전체 pytest/
graph·실제 LLM은 미검증이다. standalone tsc도 full Next generated-route/typegen/build 성공이 아니다.

실제 .env/키·실캐시/home·KIS/AI·DB·앱·외부 socket·설치 없이 합성 입력만 사용한다.
실제 source SHA·검사 결과·한계는 [CF-005 작업 기록](../../../../docs/work/CF-005-flow-observation-window.md)에 남긴다.
