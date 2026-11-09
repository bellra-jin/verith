# CF-023 Supervisor 의미 보완·고정 준비

기준 develop `f9faecec3b5a05999616d86a6355e99d726efe64`, branch `feat/supervisor-meaning`. 정본 v1.1 SHA-256 `899636d12d603350e00e784f17e05db90d5d73402e1f2bf5beee4aa52749bd18`, 허용52파일/AI 입력32개다. 선행 CF022 결과를 이번 검사로 집계하지 않으며, 중지된 다른 작업의 source는 입력으로 사용하지 않았다.

## 구현

- policy2의 후보는 원문·typed 답변의 정확 span만 제안한다. 서버의 닫힌 대응표가 view/domain/주체/기간·원단위/부정 scope를 검증하고 MeaningFrame을 정본화한다. 모델0 충분성은 의미 있는 잔여까지 검사한다. 다중 종목·시장 범위·명시 부정·상충 조건을 모델이 삭제해 실행 준비로 만들지 못한다. 종목 포함/제외의 canonical alias 충돌도 Backend resolver에서 거절한다.
- 준비 POST는 owner/key 유일 claim의 commit ACK 뒤에만 추출하며, 같은 키 replay·경합 loser·unknown ACK는 재생성하지 않는다. 원문/frame/초기 plan은 root에만 둔다. child는 참조·고정 선택·continuation/hash만 보존한다. root→leaf 잠금과 deferred owner/consumption 제약으로 sibling 및 parent/child가 한 binding만 채택한다.
- resolver 뒤 DB시각을 재확인하고 소비 UPDATE의 DB guard도 만료를 검사한다. 만료 소비는 같은 transaction의 새 binding까지 rollback한다. 기존 binding replay는 준비 TTL보다 먼저 처리한다. optional preparation_id=None은 legacy digest에서 제외한다.
- 채택·명시 취소·만료 access·기존 Flow 보고서 삭제가 원문을 redact한다. 늦은 결과는 삭제/만료한 준비를 부활시키지 않는다. TTL10분은 첫 채택 유효기간이며 자동 물리 purge나 비용 환불이 아니다. 접근하지 않은 만료행의 물리 잔류는 후속 운영 보존 정책의 한계로 남긴다.
- 의미 budget은 고정 개발 단위 epoch에 최대2시도·count2/generation2·총USD0.10 보수 예약을 영속 제한한다. count/generation은 같은 attempt 예약을 공유한다. unknown/anomalous 또는 ACK불명은 hold/block이며 재시작·새 키·TTL·삭제로 초기화하지 않는다. production gateway는 기본 unavailable이다.
- 상태/hooks를 production `SupervisorSession`으로 이동했다. `SupervisorChat`은 Next navigation·legacy Flow seam만 연결한다. 준비 키/본문을 송신 전에 저장하고 known ID는 GET으로 관측한다. GET plan도 고정 draft/선택과 대조하며, consumed binding은 GET-only로 복구한다. ACKunknown/running/unknown/result_ready의 확정 키는 새 대화 동작으로 버리지 않는다. terminal 상태만 명시 reset한다.
- 명확화 답변 버튼·IME 보호·사람용 관점/상태/준비 남은시간·44px checkbox label을 보완했다. 합성 fixture도 실제 Session/ChatView/CSS와 native HTTP helper를 사용하며 별도 성공용 상태기를 두지 않는다.

기존 Flow 실행 원장·usage·claim·fingerprint·payload/계산·snapshot·owner/auth/삭제 의미는 보존한다. News 신규 분석·수집/실행, Technical/재무 연결, 운영 한도 활성화는 이번 범위 밖이다.

## 직접 검증

| 선택 | 최종 결과 | 로그 이름 |
|---|---|---|
| 보호 `meaning-self` | 3통과, exit0 | `backend-self-2.log` |
| 보호 `meaning-unit` 단일 신규 파일 | 44통과, guard 위반0, exit0 | `backend-unit-4.log` |
| Frontend 보호 `core-unit` | 93통과(37+14+6+36), exit0 | `frontend-unit-3.log` |
| Frontend 보호 `core-type` | 오류0, exit0. 이후 TS 제품 변경0 | `frontend-type-2.log` |
| Frontend 보호 `core-lint` | 오류0, exit0 | `frontend-lint-3.log` |
| 새 소유 PG 집중 검사 | 10그룹, 금지접근0, exit0 | `pg-2.log` |
| 검토 후 별도 소유 PG 영향 검사 | TTL/소비 rollback/unknown hold 3그룹, 금지접근0, exit0. 앞10그룹 반복0 | `pg-impact-1.log` |

Backend는 clean env의 새 worktree 절대 Python `-I -S -B`와 `scripts/check_safe.py`를 사용했다. Frontend는 검증된 절대 Node·clean env·`OPENSSL_CONF=/dev/null`과 기존 `scripts/check-local-ports.mjs`를 사용했다. PG는 검증 source-copy에서 기존 `cf002_interactive_login.py --verify-supervisor-meaning-db`와 동일 ownership receipt/preflight/제한 연결/로컬 image를 재사용했다. 영향3그룹은 같은 보호 입구에 고정 checker 함수를 주입해 앞10그룹을 반복하지 않았다.

대표 근거는 actor 제외와 Flow view 부정의 분리, stock polarity/alias 충돌, fixed-frame 조건 evidence 재검증, timeout/transport의 보수적 unavailable 및 취소 전달, policy별 candidate_ref, prior digest/OpenAPI baseline, provider streaming/response cap·usage unknown·예약 ACK send0, 준비 claim 경합/ACK 회수, child model0/root-only, sibling·parent-child 단일 승리, 삭제 중 늦은 결과 fence, 기존 Flow 저장/삭제, epoch 단회 정산/재시작 hold다. 추가 영향 PG는1.5초TTL 전에 진입한 resolver가1.8초 뒤 거절되는 사례와 직접 late SQL consume의 새 binding rollback, unknown+blocked=False의 DB/저장소 차단을 확인했다.

두 실제 소유 PG 실행 모두 full ownership 정리·정확 CID 부재 확인을 마쳤고 source-copy root도 제거했다. 소유 증거 없는 자원 정리·기존 DB/컨테이너 채택은 하지 않았다. Frontend guard hash `3a9cb45bc865d560612ccd5876f060c69aa0abe5ff635576888781d9efe7d3ee`는 불변이다. guard/capability/namespace/OS/FS/network 조건은 완화하지 않았다. FE 파일 관측은 instrumented JS journals 범위이며 native 전체 읽기 부재 증명으로 확대하지 않는다.

## 실패·수정 이력

- 최초 unit은33/40 통과였다. 잘못된 후보를 거절할 때 base frame의 provenance가 deterministic으로 남는7개 사례를 unavailable로 정리한 후 관련 검사와 추가 회귀가 통과했다.
- 최초 lint는 렌더 중 `Date.now()` 두 건으로 실패했다. effect/state 기반 남은시간 표시로 수정한 뒤 오류0이다.
- 첫 PG 준비는 `local_context`에서 DB 생성 전 중단됐다. clean PATH 누락과 Docker CLI 위치를 소스/비밀 없는 metadata로 대조했고, 고정 CLI PATH를 명시한 동일 runner로 통과했다. 최초 축약 진단에는 원 예외문구가 남지 않았으며 이 준비 실패를 권한 거절/DB 생성 성공으로 기록하지 않는다.
- 검토에서 발견된 모델 의미 손실, unknown hold 해제, resolver 뒤/소비 시점 TTL, 새 대화의 미확정 키 유실, GET draft 불일치 등은 허용 범위 안에서 보완했다. source 검토와 직접 실행 근거는 별도로 보존했다.

## 미실행·남은 경계

- **실제 모델:** OpenAI key 읽기·두 endpoint 전송 승인은 pending이다. 공식 snapshot/생성 단가·전체 입력 계수 필드 근거와 달리 count 요금 상한의 공식 증거가 없다. 예제가 계수 수수료를 생략했다는 사실을 무료 증거로 쓰지 않으며 CounterUnavailable/live gate closed를 유지한다. 생성2회의 계산상 상한USD0.043008은 전체 개발 단위 실제 청구나 계수 비용까지 보장하는 금액이 아니다. 실제 모델 품질·일반 NLU·서비스 전체 의미 비용 관리 완료가 아니다.
- **브라우저:** 문서화된 새 격리 context/profile API가 확인되지 않아 실제 React mount/controller click/storage/navigation·1440/390 레이아웃·focus 수용은 미실행이다. 이는 도구의 지원 capability 부족이며 접근 거절을 다른 경로로 우회하지 않았다. helper matrix/mock fetch/source assertion 및 fixture 구현은 mounted controller의 직접 검증을 대체하지 않는다. 새 서버/탭/개인 프로필을 사용하지 않았다.
- 실제 Next SSR/BFF 전체 흐름·Google/KIS/Flow 공급자·기존 DB/운영 migration·한도 활성화·전체 build/과거 suite는 실행하지 않았다. 합성 ASGI/자기 PG는 운영 전체 E2E 완료가 아니다.
- 원격 최신 exact-head CI/PR/병합은 조율 측 게시 이후 단계다. 로컬에서 stage/commit/push/PR를 실행하지 않았다. 최종 source/log SHA·NUL stage 목록과 공개 가능한 일반 PR 초안은 비공개 checkpoint로 인계한다.
