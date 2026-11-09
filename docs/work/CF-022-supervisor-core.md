# CF-022 Supervisor core 작업 기록

기준 develop `bba0305f09cecd8b52ffe79474ebc0e84e77e7e8`, branch `feat/supervisor-core`. 확정 지시 v1.1 SHA-256 `3f506b4209061578b9af2d70da3a69a350acbad30d96d50e6fd9ab064fc5f630`, 허용50파일/AI입력28개다. 중지된 CF-021의 다른 worktree/WIP는 보존했고 source 입력으로 쓰지 않았다.

## 구현과 검토 보완

[공통 계약](../contracts/supervisor-core-v1.md)·[단일 채팅 디자인](../design/supervisor-core.md)에 따라 원질문→MeaningFrame/typed Plan·Outcome→immutable owner/key binding→기존 owned Flow/usage→단일 채팅/BFF를 연결했다. 실제 의미 모델 gateway는 unavailable이며 Technical·재무·거시·News 실행을 열지 않는다.

과거/상대 시점·기간 단서, 주체 focus/제외와 답변의 부정을 보존한다. 모델이 명시 종목/조건·명확화/지시 무시 장벽을 지우면 채택하지 않는다. multi_stock/시장 범위의 개별 종목 답변은 실제 stock typed answer로 이어진다. 확정 후 원조건과 effective_scope/waiver 근거를 함께 표시한다.

기존 Flow pending 우선 복구, 고정 pending 없는 직접 링크의 GET-only 관측, 손상/읽기 불가 storage와 알려진 ID의 관측 분리, 세션401 숨김, canonical UUID URL 대조와 오래된 poll 무효화를 반영했다. actual helper의 지연 세션/취소·계정 변경, 실제503 고정 pending 보존·typed 답변·timer 동작을 검사했으며 React 상태/이벤트 전체 검증과 구분한다.

GET의 live binding 관측 뒤 삭제가 첫 Flow run 조회 전/Flow GET 전 완료되는 두 경로와 확정 POST 최종 관측 전 삭제는 fresh owned binding을 다시 읽는다. 삭제 transaction의 binding redaction/rollback, 원 회계 유지와 기존 잠금 순서를 보존했다. 핵심 신규 Python은 명시 import·줄바꿈으로 정리했다.

## 최종 직접 검증

2026-11-09 UTC 실행이며 상세 시각·정확 argv·source/log SHA는 비공개 checkpoint에 보존한다.

| 보호 검사 | 최종 결과 | 증거 파일명 |
|---|---|---|
| Backend core-self | 3/3, exit0, owned root 정리 | backend-self-4.log |
| Backend core-unit | 단일 파일49/49, guard0, exit0, owned root 정리 | backend-unit-5.log |
| Frontend core-unit | 82/82 (29+13+5+35), exit0, 위반0·기대한 부정검사/diagnostics 구분, owned root 정리 | frontend-unit-4.log |
| Frontend core-type | 변경 대상만 검사, exit0 | frontend-type-3.log |
| Frontend core-lint | 대상 오류0, exit0 | frontend-lint-3.log |
| 소유 PG 최신 회차 | 13그룹, binding7/Flow analysis5·dispatch5·engine5, 금지 접근0, exit0 | pg-3.log |

PG는 full ownership/원 receipt·제한 role/preflight·동일 연결 migration을 거쳤다. 신규 revision 적용/빈 downgrade/기존 표 보존, 실제 API auth/CSRF·prepare mutation0, planning 중 세션 폐기와 fresh auth, owner/key 경쟁 winner·기존 usage/예약1, row 확인 replay의 planner/resolver/dispatch0, 다른 입력409/타인404, binding ACK 불명 최초Flow0/primary 행 확인 복구, admission 전 중단, result_ready GET 게시0/same-key snapshot 게시, 실제 user quota 소진429·정책차단provider0, handoff 만료 새 run 차단/기존 run 복구를 검사했다. 삭제 rollback·GET/confirm 및 첫 run 읽기 전 삭제 barrier는 결정적으로 제어했다. 최신과 앞선 성공 회차 모두 실제 receipt의 정확 CID를 검증·제거하고 부재를 확인했다. 시간 경과에 따른 session expiry 자체는 별도 미검증이다.

## 보존한 실패와 해결

- Backend self 최초는2통과/1오류·exit78이었다. 새 테스트가 worker 안에서 git ls-files를 요청해 process guard가 차단했다. 합성 index 응답 주입으로 수정했으며 guard는 그대로다. 두 번째3개 통과와 최종 결과를 구분한다.
- Backend unit 최초36개는 통과했다. 이후 기본 도구 sandbox의 OS canary true가 exit71, worker0으로 중단됐다. 축약 로그에 stderr가 없어 세부 원인을 단정하지 않았다. 정식 require_escalated 심사 뒤 동일 canary/profile/entry/worker를 유지한 보호 명령으로 최신49개가 통과했다.
- Frontend 최초 unit/type/lint는 snapshot capability/fingerprint에서 worker0·exit78이었다. 새 codeRoot와 기존 dependency parent가 달라 worker 조건에 맞지 않았다. v1.1에 따라 고정 sibling의 공개 package metadata만 분리하고 양쪽707bytes/pin·새 lock·source manifest의 전후 provenance를 대조했다. 첫 provenance 시도는 기존 exact fresh 입력을 재대조 집합에서 빠뜨려 worker0·exit78이었다. 같은 승인 집합으로 맞췄고 정상 sibling preload/부정·drift 회귀가 통과했다. guard SHA `3a9cb45bc865d560612ccd5876f060c69aa0abe5ff635576888781d9efe7d3ee`는 불변이다.
- 대상 lint에서 내부 이동 링크와 렌더 중 ref 접근5건을 고쳤다. Next shim 없이 고정 이동 callback과 React replayable state를 사용했고 관련 unit/type/lint를 재검사했다.
- PG 최초 기본 sandbox는 create nonzero·receipt 할당 전 실패/exit1이었다. 당시 owned_db_removed 문구는 부재 증명이 아니었다. 정확 요청 이름 inspect도 permission denial로 불명이었으나, 정식 심사 후 같은 context의 ID-only inspect로 부재를 확인했다. 재생성/삭제 우회는 하지 않았다. 이번 허용 cf002 runner는 receipt 없는 실패를 cleanup_unverified로 표시하도록 수정했다. 다음 정식 소유 PG 회차는12그룹 통과했고, 마지막 early-delete 분기 보완 후 최종13그룹을 통과했다. 최초 실패 기록을 성공으로 바꾸지 않는다.

split metadata diagnostics의 copySources는 빈 배열이며 실제 새 source는 별도 caller provenance로 증명한다. rawOriginal0/native:not-observed는 기존 JS 계측 범위의 관측이지 모든 원본/native 읽기 부재 증명이 아니다. parent package read counter도 옛 metadata 미열람 증명이 아니다.

## 미실행과 게시 상태

문서화된 새 격리 browser context/loopback capability를 확인하지 못해 실제 ChatView desktop1440/mobile390 시각·클릭은 **미실행**이다. fixture 서버/탭/기존 개인 profile/cookie를 열지 않았다. 준비 fixture의 합성 API·ChatView는 SupervisorChat의 실제 세션/pending 경합, Next SSR/BFF·실 DB/모델 검증을 대신하지 않는다. helper 행동 회귀, 문자열 wiring assertion, 실제 API/PG를 구분한다.

실제 provider/Google/키·환경 파일·기존 DB·운영 migration·서비스/한도 활성화·새 설치는0이다. 기존 Flow 고정 창/계산·fingerprint·payload·회계는 유지한다. handoff120초는 Flow 호출 직전 DB 시각 검사이며 DB admission의 원자 상한이 아니다. 실제 모델 품질·일반 NLU·완료 대화 멀티턴은 미검증이다. Supervisor 이후 Flow 운영설정과 CF019 잔여 오류/지연 UI를 이번에 활성화하지 않았다.

개발 측은 Git stage/commit/push/PR/Ready/merge를 실행하지 않았다. 최종 원격 read-only 확인에서 develop은 위 base와 일치했고 feature ref는 없었다. exact source/log manifest·독립 검토 뒤 조율자가 게시한다. 최신 PR head/Ready CI는 아직 미실행이며 기존 Backend CI가 실제 브라우저/모델 수용을 대신하지 않는다.
