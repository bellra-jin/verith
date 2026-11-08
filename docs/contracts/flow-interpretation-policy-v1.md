# Flow 신규 해석 정책 v1

정책은 `flow.fact-selection.v1`, prompt는 `flow.explain.fact-selection.v1`이다.
LLM은 검증된 fact ID만 선택하고 문장은 코드가 구성한다. 자유 서술의 폭을 줄여
주체·기간·단위·확정일과 수치를 바꾸는 경로를 제한한다. 모델의 선택 유용성은
실제 공급자 품질 평가와 구분한다.

각 fact는 원자료 관측창·날짜·주체·지표·단위·원값 부호·표시 정밀도와 고정 문장에
결합한다. bank는 최대 24개, 선택은 1~8개의 서로 다른 ID다. 응답은 정확히
`{"schema_version":1,"fact_ids":["목록에 있는 ID"]}`이며 버전은 정수 1이다.
4096 UTF-8 bytes 초과, duplicate key, extra, 미등록/중복 ID, Markdown·자유 문장,
수치/기간 override는 거부한다. 거부된 raw 응답은 로그·payload·HTML에 남기지 않는다.

확정일은 수집 자료의 마지막 날짜다. 요청 후보일로 대신하지 않는다. 연속 순매수는
원자료를 최신부터 독립 순회해 양수가 이어지는 길이와 threshold 신호를 대조한다.
전행 양수여도 제공 관측 이전의 연속을 뜻하지 않는다. 날짜 중복·역순·비유한 수치·
bool·음수/소수 claimed days는 통과하지 않는다. 기존 계산과 v1 숫자는 변경하지 않는다.

강도는 **최근 실제 관측 N행 순매수합 ÷ 같은 창의 종목 일평균 거래대금**이다.
N은 실제 제공 행수와 RECENT_DAYS(5) 중 작은 값이다. 전체 거래대금 비중이나 보유율이
아니며 100% 초과도 가능하다. 분모 0/미확인의 기존 ratio=0 후퇴는 측정된 0%가 아니다.
관측이 부족/불명하면 기존 observation_window 안내를 그대로 사용하고 지속성 비교
fact를 발급하지 않는다. 자료 행수 충족도 시장 거래일 완비를 보증하지 않는다.

| 지표 | 원자료 단위 → 문장 단위 | 표시 정밀도·창 |
|---|---|---|
| 순매수합·지속성 합 | 백만원 → 억원(÷100) | 소수 1자리, 실제 단기/장기 창 |
| 강도 | ratio → %(×100) | 소수 1자리, 실제 최근 N행 |
| 한도소진율·변화 | % / %p | 소수 2자리, producer와 같은 최근 최대 5행 |
| 종가·전일비 | 원 | 원 단위, 확정일 |
| 등락률 | % | 소수 2자리, 확정일 |
| 연속 순매수 | 제공 관측 행 | 정수, 전체 원자료 내 최신 연속 |

단일 formatter를 사용한다. 허용오차와 별도로 0/양/음 부호가 일치해야 하며,
표시 반올림으로 0이 되는 비영값은 “양수/음수·표시 정밀도 미만”으로 구분한다.
선택 순서와 무관하게 기본 방향·외국인/기관 구도·확정일·관측 안내를 보존하고
고정 순서의 3문단을 만든다. Gate3는 bank·선택·meta·결정적 문장의 정확한 일치를
요구한다. 빈/잘린 응답도 시도로 세어 최대 3회 후 기존 fact_only로 후퇴한다.
regen_count 0/1/2, interpretation null 및 provider/model null 의미는 유지한다.
공급자 timeout/취소는 선택 파싱 오류로 재시도하지 않는다.

신규 SPEC만 policy source/prompt SHA를 pin하며 live engine 전 fingerprint를 확인한다.
원 config·모델·payload/input version·deadline/retry/token cap은 유지한다. 구 저장 자료는
해당 row의 원 SPEC·input/result JSON·hash·UUID로 기존 adapter에서 복구한다.
새 Gate3나 현재 SPEC로 구 해석을 재생성/수정하지 않는다.
