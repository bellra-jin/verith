# 기존 일반 unit 계약 회귀 수선 · 2026-11-13

기준 develop/HEAD `c33ec8ec5d5ade308ce75568cdbf0883acc1e042` (PR72 병합),
branch `fix/legacy-unit-contracts`, 별도 worktree `verith-unit-contract-repair`.
이번 범위는 기존 162개 실패의 로컬 수정·검증이다. stage/commit/push/PR/merge는 하지 않았다.
제품·migration·검사 실행기/guard/source pin·공유 fixture·CI 변경은 없다.

## 원인과 변경

CF054 보존 로그는 변경본 823 pass/162 fail, 기준본 815 pass/162 fail이었다.
출력 tail만 보존되어 전체 162개 traceback이 남아 있는 것은 아니다. 보존된 실패 이름,
현 소스/파라미터, 이번 보호 재실행의 잔여 실패를 함께 대조했다.

| 기존 실패 | 수 | 현재 계약으로 고친 검사 |
|---|---:|---|
| CF005 facts | 64 | CF014의 raw evidence 기반 FactBank를 요구한다. 표시 signals만으로 메뉴를 발급하지 않고, 검증된 1/4/5/19/20행의 실제 fact ID·날짜·notice·지속성 보류를 검사한다. |
| CF005 daily/persistence | 64 | CF019 `_display_number`의 닫힌 의존성을 함께 추출한다. 원값/부호·0·미세 비영값·자료 없음·입력 불변을 검사한다. |
| CF005 비정상 숫자 표시 | 21 | 동일한 실제 formatter 의존성을 사용하고 NaN/무한대/bool/문자열/null/overflow 정수의 보류를 유지한다. |
| CF005 옛 prompt/전체 AST hash | 3 | ID 선택 prompt·Gate2 실제 지속성 대조 slice·render context 보존으로 검증한다. 그대로인 HTML escape 함수의 기존 pin은 유지한다. |
| CF007 migration gate | 1 | CF015가 이미 추가한 정확한 고정 `c15001a7e0001` 대상과 선행 proof preflight를 검사한다. c60001 회귀·내부 전용 경계는 유지한다. |
| 재무 client 인증 누락 | 4 | 가짜 필수 서비스 토큰을 명시하고 실제 MockTransport 수신 header/path/body를 검사한다. |
| 옛 Technical 무인증 client 기대 | 4 | 기존 상태/timeout/connect 검사를 인증된 typed boundary로 옮긴다. legacy 호출의 HTTP 0회와 잘못된 토큰의 HTTP 0회도 추가한다. |
| Supervisor 기본 resolver 주소 | 1 | 현재 import-safe 설정의 빈 주소·rewrite off·import/call 부재를 확인한다. 타 AI 기본값 검사는 보존한다. |
| 합계 | **162** | skip/xfail/검사 삭제로 통과시키지 않았다. |

보호 self-test에는 별도의 낡은 기대값도 있었다. CF014가 이미 허용/pin한 Flow 상수 파일을
여전히 금지 대상으로 기대했다. 기존 exact pin을 대조하고 인접 소스·private 거절은 유지하도록
검사를 수정했다. 허용 목록 자체는 바꾸지 않았다.

독립 읽기 검토 지적에 따라 CF005 rule slice는 닫힌 AST 호출/속성과 최소 builtins로 실행한다.
CF007은 gate 전체 AST를 고정하고 `ValueError`만 제공한다. 추가 call/else/comparator 변조를
실행 전에 거절하는 6개 음성 회귀를 추가했다. 원본/사본 경계와 OS 보호는 그대로다.

## 직접 실행 결과

모두 clean env의 기존 `backend/scripts/check_safe.py` 고정 mode를 사용했다.

| mode | 결과 |
|---|---:|
| `unit` | **1,008/1,008**, 고정 19파일, guard 위반 0 |
| `self-test` | **20/20** |
| `quality-unit` | **77/77**, guard 위반 0 |
| `display-unit` | **54/54**, guard 위반 0 |

각 실행은 자기 임시 root 제거를 확인했다. 기존 985개에서 23개 회귀를 더해 1,008개다.
실제 pandas/Gate2 전체·Jinja 렌더·graph/provider·PG·Google/UI/배포 수용은 이번 결과가 아니다.
DB·키/환경파일·OpenAI/KIS·설치·운영 활성화·새 비용 예약은 모두 0이다.
중간 수정 중 unit 80 fail→9 fail→전체 통과였으며 최종 AST 보완 뒤 다시 전체 통과했다.
AIClient 파일 전체 교체 제안은 자동 심사에서 회귀 축소 위험으로 거절되어 미실행이었다.
기존 검사 함수를 유지하는 작은 patch로 대체했으며 이후 검증이 통과했다.

## 정확한 로컬 변경 범위

- `backend/tests/unit/test_cf005_flow_observation.py`
- `backend/tests/unit/test_cf007_flow_fake_execution.py`
- `backend/tests/safe_checks/test_entry.py`
- `backend/tests/test_ai_client.py`
- `backend/tests/unit/test_cf002_local_ports.py`
- `backend/tests/unit/test_flow_contract.py`
- 이 작업 기록

권장 commit 제목: `test: align legacy unit checks with current execution contracts`.
게시/머지는 이번 위임 범위 밖이며 명령을 실행하지 않았다. 최종 읽기 원격 조회에서도 develop은
기준 SHA, 열린 PR은 HOLD #61뿐이었다. 준영 PR 선행 의존은 그 조회 시점에 없었다.
개인 검사 로그·최종 manifest는 전용 `.unit-contract-repair-20261113`에 두며 게시하지 않는다.
CF054 및 과거 실제 실행 자료, main WIP, 다른 worktree는 보존했다.

## 후속 실제 Technical 검증의 남은 실행 조건

승인된 범위는 현대건설 1건, count/gen 각각 최대 4, 자동/SDK retry 0,
KIS 인증 최대 3·시장 GET 최대 30·계좌/주문 0이다. 신규 보수 예약 최대 $0.20과
기존 Supervisor $0.50 hold를 분리해 총 $0.70 이내로 관리한다. 아직 이번 예약/실제 호출은 없다.

실제 실행 전에는 전용 소유 프로세스/Verith DB에서 명시적인
`TECHNICAL_EXECUTION_ENABLED`, `TECHNICAL_EXECUTION_CONFIG`, 서로 다른 AI/authority 토큰과
정확한 HTTPS origin·기한·정책/가격/계수 근거를 결합해야 한다. AI는 `ExecutionOptions`의
credential supplier/fetcher/cache/trace를 명시 설치해야 하며 현재 main의 초기 runtime은 None이다.
환경파일이나 운영 서비스의 장기 설정/재시작은 이번에 수행하지 않았다.

또한 현재 Technical `load_kis_settings()`는 부모 `.env` 탐색을 수행한다. 승인된 원래 AI
자격 소스만 쓰는 격리 경계에 맞추려면 이 부분의 명시적 settings 주입 경계를 먼저 확정해야 한다.
키를 복사하거나 탐색을 우회하지 않는다. cache/trace 없음, intraday off, 전용 자원 정리,
실패/ACK 불명에서 hold·한 번 소비 기록 보존 및 무재실행을 유지해야 한다.
이 조건을 확인하는 작업과 실제 제공자 검증은 이번 단위 검사 성공과 구분한다.
