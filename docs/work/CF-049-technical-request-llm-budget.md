# CF049 · Technical 요청별 LLM 제한과 사용량 증거

CF049 v1.1의 정확6파일이다. CF048 CI 대기 중 부모가 순차 조건을 좁게 조정해 동결 head `908a49b`의 별도 worktree에서 착수했고, PR66 정상 merge `13b081e26ef35983b0f78559ad7da923fad171f3` 확인 뒤 tree 차이0의 ff-only 통합을 완료했다. CF048 branch/source와 다른 WIP는 변경하지 않았다.

## 제품 결과와 경계

기존 OpenAiLlmClient에 명시 opt-in strict 정책/요청 budget을 추가했다. 원 full policy bytes와 독립 hash·typed projection 및 run/attempt/예약/원 기한을 고정한다. 계수 DI는 기본 unavailable이다. 명시 trusted DI가 exact projection·identity에 발급한 opaque receipt를 스스로 검증해야 하며 형식/marker만으로 실제 계수를 주장하지 않는다. 실제 계수 구현이나 count API·설치는 추가하지 않았다.

한 budget을 모든 adapter가 공유하고 최대4 ordinal/보수 hold를 SDK 전에 소비한다. 같은 lock의 별도 entered 선형화, 대기 후 actual SDK/responses/create identity·retry0·고정 generation 인자 재검사, UTC/monotonic·더 짧은 adapter 기한, 전 호출 usage/unknown·sticky closed를 구현했다. legacy 호출/factory/last_usage와 기존 graph/prompt/계산은 유지한다. 무설정 fallback·원장·route·실행기·새 mode·운영 활성화는 없다.

독립 검토에서 늦은 응답 채택, 캡처 SDK와 count 뒤 검사 SDK의 불일치, 자유 문자열 내부 예외, snapshot UUID 참조 공유를 발견해 각각 수용 직전 기한/정책 검사, 실제 dispatch identity 재검사, 고정 reason allowlist, UUID 깊은 사본으로 보완했다. 관측 usage와 이미 소비한 ordinal/hold는 어느 경우에도 환급/초기화하지 않는다.

## 직접 검증

기존 `technical-runtime-self/unit`에서 실제 helper/class/complete/factory의 고정 이름 AST만 compile/exec한다. actual openai/config factory/graph 모듈·환경·provider를 import/호출하지 않으며, 기존5 AI exact pin/6 pure Flow origins·worker/guard·source/dependency 사후 대조와 자기 root 정리를 유지한다.

최종 보호 unit 149개 통과, guard0. legacy 호환, 명시 strict 누락/정책·계수·retry·model/cap/prompt 거절, N+1/동시 cap·여러 adapter 공유·다른 요청 격리, 소비 후 만료·후속 SDK0, usage 누락/불일치·status/빈 text/refusal/metadata 거절, 역순 응답의 ordinal 귀속, deadline/timeout-only 축소와 의미 변조 거절, unsafe snapshot 변조, 고정 비밀 sentinel 비노출을 확인했다. self 결과와 원격 exact-head CI는 최종 게시 시 별도 대조한다.

두 실제 thread barrier 회귀는 A 소비/미진입 뒤 B unknown 폐쇄이면 A SDK0·환급0, A entered 선형화 뒤 B 폐쇄이면 A의 관측/결과와 아직 미진입 call을 구분함을 확인한다. SDK 대기 중 다른 call이 진행하므로 I/O 동안 budget lock을 잡지 않는다. 실제 HTTP 경합이나 강제 thread 취소 증거는 아니다.

중간 unit 1건은 검증된 0-token을 잘못 음성으로 둔 fixture 때문에 실패했다. 제품의 exact nonnegative 계수 계약을 유지하고 음성을 -1/과대값으로 수정한 뒤 전체 집중 unit을 확인했다. 이전 실패 로그는 보존한다.

PR 게시 후 기한 변환을 추가 대조해, local UTC가 원 시작시각보다 이르면 CLOCK_INVALID로 닫고 UTC 관측 전 monotonic 기준점에서 원 duration 이하만 변환하도록 보완했다. UTC 관측 지연과 이후 wall-clock 역행에도 원 기한이 늘지 않는 집중 회귀 두 개를 추가했다.

## 미완료

계수/SDK retry0 검사는 자기 합성 issuer·SDK의 실제 제품 함수 실행이다. 실제 tokenizer/count transport의 정확성·SDK wire·운영 가격/한도·프로세스 간 단일성·CF048 claim 조립·provider별 durable 승인/정산·실제 엔진→저장·Supervisor dispatch는 미완료다. 설치·키/env·DB·실제 OpenAI/KIS·추가 예약은0, 기존 Supervisor $0.50 및 실제 소비 기록·PR61 HOLD는 불변이다. 승인 기한은 2026-11-12 21:00 UTC다.
