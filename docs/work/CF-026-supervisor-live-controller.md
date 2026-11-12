# CF-026 Supervisor one-shot live controller

현재 정본 v1.6 SHA256 `48aec6c42fda7fa81d0c288a73d3e2d763aa1c889b19c9d0f6e2f28aecf2ed8e`.
아래 v1.2/v1.3과 실제 중단 기록은 각 실행 시점의 이력이다.
기준/HEAD `ad7ced12df1b227f07106b82598cd67d6e687768`, 별도
`feat/supervisor-live-controller`에서 정확6경로를 작업한다. CF027 source와
CF021 WIP는 접근/복사/수정하지 않는다. Git 게시·브라우저·Frontend는 범위 밖이다.

## 구현과 정적 확인

- 일회 외부 승인과 private grant/state/lock을 분리했다. owner/mode/regular/
  nlink/symlink·전후 identity, atomic replace·파일/디렉터리 fsync와 영속 claim
  ACK를 검사한다. grant는 저장소 디렉터리/lock identity도 고정하여 동일 grant의
  복제로 새 예산을 만들 수 없다. issued 생성은 명시 synthetic fixture뿐이다.
- 원 proof/receipt로만 신규 owned bootstrap과 명시 epoch INSERT/commit/fresh
  SELECT를 조율한다. 기존 CF023 단위·예약/한도·SELECT-only verifier를 보존한다.
- 정확한 두 request/draft/projection/spec·source capability·공식 evidence·expiry를
  phase별로 확인하며 실제 supplier는 count ACK 이후 최대1회다. key 원본0644와
  private state0600을 구별하고 chmod/복사/환경 fallback을 만들지 않았다.
- 첫 observed 정산의 request/projection과 정상 원장 전이를 확인한 후 같은
  proof/epoch의 다음 snapshot만 승인 journal에 ACK한다. unknown은 다음 실행을
  열지 않는다. 취소/예외에도 cleanup 전에 fresh ledger를 bounded 조회한다.
  읽기 불가면 횟수/실사용액은 unknown이며 전체 승인 한도를 보수 hold로 영속
  기록한다. 기록 ACK도 불명이면 자원을 disposal하지 않고 원 cleanup proof를
  보존하며 claimed를 유지한다. 취소는 성공으로 삼키지 않고 전달한다.
- 고정 self/unit 선택과 단일 수집 파일을 추가했다. AI32 pin·checker·gateway·
  worker/bootstrap·OS/FS/network/env guard·CI·migration/package는 변경하지 않는다.

현재 controller·단위·입구·self source의 AST 정적 구문은 통과했다. 승인 점유,
파일/출처, phase scope, ACK 손실, 첫 unknown, 실패 회계 보존, 취소/정리 및
두 고정 합성 후보의 실제 meaning policy/gateway/fixed-frame 회귀를 작성했다.
아직 실행하지 않은 회귀의 존재를 통과로 집계하지 않는다.

## 실행 차단: 자동 승인 심사

2026-11-10 재개 중 clean env/전용 Python `-I -S -B`의 기존 보호 입구로
`live-controller-self`를 `require_escalated` 심사에 요청했다. 도구가 실행 전
거절했다. 사유는 이전 CF026/OpenAI 중단 범위가 유효하며 ‘계속 진행’은 CF027에
한정된다는 승인 범위 판단이었다. 코드/OS/검사의 실행 실패가 아니다. 프로세스와
owned root/PG는 생성되지 않았고 해당 실행 로그도 생성되지 않았다.

최신 CF026 무키 구현·검증 인계와 이 심사 해석의 차이를 조율 측에 보고했다.
조율 측도 거절을 확인했으며 새로운 관련 사용자 근거 전 실행 중지를 지시했다.
현재 심사 진행 중이 아니다. 새로운 관련 근거 없이 같은 요청을 반복하거나 raw
pytest·다른 인터프리터/DB/도구·guard 완화로 우회하지 않는다.

| 검사 | 현재 상태 |
|---|---|
| `live-controller-self` | denied before execution, 통과 수 없음 |
| `live-controller-unit` | 미실행/중지, 새 관련 근거 전 요청하지 않음 |
| 두 의미 후보 무키 preflight | 회귀 작성, 실행 미검증 |
| 신규 owned synthetic PG bootstrap/회계/cleanup | 미실행/중지, 생성0·정리 대상0 |
| 실제 key/count/generation/provider | 미실행0, live grant 미발급 |
| 브라우저·운영 DB/한도·Git 게시 | 미실행 |

controller 구현의 실행 수용과 live 실행 준비는 완료가 아니다. 별도 외부 승인
capability와 고정 두 drafts/expiry·fresh source metadata·공식 문서/가격/count
매핑 evidence의 실제 hash가 필요하다. 비용·기존 key 사용 승인이 없다고 되묻는
상태가 아니라, 이 단계의 보호 실행 심사와 미고정 runtime 입력이 남은 상태다.
정확 source/명령/차단 원문·checkpoint hash는 비공개 인계에 남긴다.

## 독립 정적 검토 finding 보완 (실행 수용 전)

첫 초안은 verify 반환 경로에서만 snapshot을 보존했다. 취소/timeout/예외 뒤
cleanup 전에 확인 가능한 회계가 사라질 수 있다는 지적을 반영했다. 이제
`finally`에서 별도5초 bound로 fresh owned ledger 조회를 먼저 시도한다.
성공하면 원장과 hash를 영속 기록하고, 조회 불가면 count/generation/실사용액을
null unknown으로 남기며 승인 전체100,000,000nanoUSD를 보수 hold로 기록한다.
이 기록 ACK가 불명이면 자원을 disposal하지 않고 cleanup-only 원 proof를
보존하며 claimed를 유지한다. cancellation은 기록/정리 후 다시 전달한다.
정상·취소·snapshot 불가·회계 기록 실패의 주입식 회귀를 추가했지만 미실행이다.

두 번째 지적은 preclaim의 missing field·Pydantic validation·파일 오류·외부
callback 예외가 raw로 나갈 수 있다는 점이다. `run_controller` 전체를 고정
`ControllerError` 경계로 감쌌고 알 수 없는 stage도 고정 코드로 닫는다.
`CancelledError`는 그대로 전달한다. 해당5가지 preclaim 회귀도 작성/미실행이다.

최종 draft의 정적 AST 구문·정확6경로와 기존 AI32/checker/worker/bootstrap/
runner-owned/lock 불변은 source hash로 대조한다. 이는 code execution이나
후보 preflight·DB·회계 수용 통과가 아니다. 재개 시에는 최신 source를 다시
고정하고 허용된 동일 보호 self/unit, 두 고정 후보의 실제 무키 policy 경로,
자기 소유 synthetic PG 한 회차와 정확 부재/정리를 순서대로 검증해야 한다.
독립 source 검토의 추가 finding 해결과 새로운 관련 실행 승인 근거가 선행한다.

## 새 승인 근거 이후 직접 실행 결과

조율 측이 준비 코드 검사·격리 DB 검증과 통과 뒤 총USD0.10 실제 모델 검증의
명시적 재개 승인을 전달했다. 이전 거절이 실행 전이었음을 확인한 뒤 동일
보호 self를 한 번 재심사 요청했고 허용됐다. 앞 절의 denied/중지는 그 이전
이력이며 우회나 반복 generic 승인 제출로 해소한 것이 아니다.

최초 self3·unit54가 통과했다. 두 고정 합성 draft는 실제 `understand_v2`와
검토된 fake gateway의 strict proposal, policy2 및 fixed-frame validator를
통과했다. 첫 후보의3주 조건·외국인 제외, 둘째 후보의 원문 기간/부정·기관
focus와 typed views 답변의 ID/revision을 보존했고 조건을 honored로 바꾸지
않았다. 실제 모델이 이 후보를 생성한 결과는 아니다.

그 뒤 source-copy launcher에서 `__file__` 기준 key 경로 검사가 승인된 원본
경로와 달라질 수 있는 문제를 보완했다. 명시 `ReviewedCodeRoot` capability에
검토 원 worktree의 경로/디렉터리 identity/controller hash를 고정하고,
원본/사본 bytes를 대조한 후 그 원 worktree의 승인된 sibling key 경로만
허용한다. 임의 env/CLI root나 fallback은 없고 key 원본은 읽지 않았다.
합성 metadata 주입 회귀로 임시 import 위치와 무관한 정확 경로, 잘못된
worktree/부재 capability·controller drift 거절을 검사했다.

| 최종 선택 | 직접 결과 | 비공개 checkpoint 로그 |
|---|---|---|
| 보호 `live-controller-self` | 3통과, exit0 | `self-3.log` |
| 보호 `live-controller-unit` | 단일 파일55통과, guard violations0, exit0 | `unit-2.log` |
| source-copy 신규 owned synthetic PG | 5묶음, exit0 | `pg-2.log` |

PG 첫 준비는 `LocalDocker()` 초기화에서 중단됐다. clean PATH에 설치된 Docker
위치가 없었고, 설치 파일 metadata는 고정된 기존 경로에 있음을 확인했다.
초기 로그는 실제 exception 종류/stderr를 남기지 않아 정확 원문 오류는 복원할
수 없다. source frame과 `resource_requested` 부재로 owner/생성 명령 이전임을
대조했으며, 테스트 grant는 재사용하지 않았다. launcher의 고정 PATH/실행파일
metadata만 맞춘 다음 회차에서 실제 owned DB는 한 개 생성됐다. 다른 endpoint,
새 image pull/설치·권한 변경이나 기존 자원 채택은 하지 않았다.

실제 PG 회차는 controller의 영속 claim ACK 뒤 기존 LocalDocker/OwnedPostgres,
동일 소유 proof/제한 역할·migration과 실제 Principal을 사용했다. 명시 최초
epoch INSERT/commit/fresh SELECT, 첫 success observed 정산, 동일 proof/epoch의
다음 immutable binding snapshot 및 외부 journal ACK, 마지막 missing-usage
unknown hold를 확인했다. 같은 epoch의 count2/generation2·예약2/100,000,000nanoUSD,
관측 상태 observed+unknown, blocked/active hold와 claimed→closed 및 replay/restart
거절을 직접 대조했다. 기존 synthetic transport만 사용했고 실제 source key 읽기와
provider 요청은0이다. 첫 합성 usage100/10의 표준 추정120,000nanoUSD는 모의 값이며
실제 사용량·청구액이 아니다.

owned cleanup은 원 receipt의 정확 자원 identity/부재 검사를 거쳐 `_removed`를
확인했다. source-copy root도 제거됐다. 승인/정산/unknown journal은 source-copy와
PG 밖 private state에 보존했다. 최종 소스와 PG 사본 입력 hash를 전후 대조했으며
이후 바뀐 것은 결과 문서뿐이다. 자기 단위/self root도 각 parent가 제거했다.
금지 private/network/HTTP/dotenv 접근 관측0이고 AI32 pin/checker/gateway/worker/
bootstrap/runner-owned/CI/package/lock은 불변이다. mock fault/회계 기록 ACK 손실
등의 단위 시뮬레이션을 별도 실제 PG 회차로 합산하지 않는다.

현재 실행 차단 denied/uncertain은 없다. 다만 live key/count/generation은 아직
실행0이며, 조율 측의 실제 grant·두 drafts/순서/expiry·source fresh metadata와
capability·공식 count/매핑/가격 evidence의 고정 hash 및 최종 독립 검토가 남는다.
완료된 synthetic 검증을 live authority/provider·실제 모델 품질·브라우저·운영
인수로 확대하지 않는다. Git 게시도 이번 개발 측은 실행하지 않았다.

## 실제 일회 검증 중단 결과 (조율 측 실행·증거 확인 전달)

이 절은 위 무키 검증/실행0 기록 이후의 실제 일회 시도다. 사용자가 두 합성
질의와 처리용 고정 지시·응답 형식의 API 전송까지 명시 승인한 뒤, 조율 측이
기존 일회 intent와 독립 검토된 launcher로 한 번 실행했다. 개발 측이 이번
문서 갱신에서 재실행하거나 키·provider·DB에 접근한 결과가 아니다.

실행은 `FIRST_SETTLEMENT_UNCONFIRMED` gate에서 중단됐고 둘째 후보는 실행하지
않았다. 원장의 count-stage reservation은1, generation reservation은0이다.
이 카운터는 supplier/HTTP보다 앞서 기록되므로 실제 count HTTP 전송·완료와
key-read 횟수는 보존 증거만으로 확정할 수 없다. 이 값을 실제 API 호출 수로
표현하거나 위 무키 단계의 provider0을 실제 시도 전체에 적용하지 않는다.

`estimated_nano`는 null이며 실사용액을 확인하지 못했다. 보수 unknown hold는
50,000,000nanoUSD(USD0.05)다. 이는 청구액이 아니라 총USD0.10 승인 범위 안에
남긴 보수 예약이다. 모델 출력·토큰 수·semantic 결과도 확인하지 못했다.
관측된 중단 gate만으로 API 오류나 키 문제를 단정하지 않으며 원인 진단은
정적 검토 중이다. 실제 OpenAI 연결·품질 검증은 여전히 미완료다.

최종 fresh-ledger accounting의 영속 기록, approval closed와 cleanup_confirmed,
원 owned PostgreSQL 및 source-copy 제거는 조율 측이 확인했다. 실행 직후
264 source manifest·기존6파일 범위·AI32/불변 파일·bound artifact hash도 모두
일치했다는 전달 근거다. 개발 측은 이번 문서 갱신에서4개 Python source가
기존 frozen hash와 동일함을 별도로 읽기 대조했다.

이번 변경은 이 결과 문서 한 파일뿐이다. 실행 시점 frozen manifest와 일회
승인/grant/state는 덮어쓰거나 재사용하지 않았다. 코드·검사·Git stage/commit/
push, DB/provider·키 읽기는 추가 실행하지 않았다. 이전 무키 통과와 이번
실제 중단/불명 사용량을 합쳐 전체 검증 통과로 표시하지 않는다.

## CF026 v1.3 한정 진단 보완·무키 검증

정본 v1.3 SHA256 `0ab6b5726cc0a291ee8bccfc895d9e1fb63a92b777623f977f6d7eac3b36bbf3`를
적용했다. 같은 branch/HEAD의 기존 정확6파일 WIP를 보존하고 controller·단일
unit·계약·이 작업 기록만 보완했다. 보호 입구와 self 선택은 기존 그대로다.
새 private checkpoint를 사용했으며 이전 실제 승인·grant/state·USD0.05 unknown
hold와 실행 시점 artifact/manifest를 읽거나 수정·재사용하지 않았다.

시도별 관측은 최대2개다. verifier 반환 직후 고정 stage(max16)/기존 meaning
enum/settlement만 검증·투영하여 실패 gate와 원장 snapshot보다 먼저 고정한다.
반환이 없으면 false와 nullable 필드, 잘못된 반환은 고정 DIAGNOSTIC_INVALID로
남긴다. 전체 결과/plan·자유 body/문자열과 그 hash를 복사하지 않으며 private
controller 결과 요약도 이 투영된 필드만 사용한다.

실제 controller supplier closure에 비민감 진입/승인검사/source API 진입·반환/
실패·취소·timeout label을 추가했다. recorder는 key 값을 받지 않는다. source
진입은 파일 내용 읽기 완료가 아니며 반환도 HTTP 전송 영수증이 아니다. 고정
ControllerError code만 보존하고 다른 오류와 malformed 진단은 닫힌 code로
정규화했다. supplier 이전/내부 실패/공급 후 HTTP unknown/유효 generation
authority 관문/예약 ACK를 사용한 분류와 근거 label을 함께 기록한다. HTTP
송신은 추가 관측하지 않았으므로 count/generation HTTP는 모두 unknown으로
둔다. 원장 예약 수를 실제 호출 수로 표현하지 않는다.

새 이벤트를 만들지 않고 기존 settlement/final accounting ACK에 진단을 합쳤다.
journal24개 상한은 그대로이며 nonterminal21개에서 멈춰 final accounting/
closing/cleanup3자리를 예약한다. 진단 또는 필수 회계/closing ACK 실패는
두 번째 작업을 막고 claimed·hold·cleanup proof를 보존한다. 기존 bounded
fresh-ledger/unknown 회계가 먼저 진행되고 cancellation은 정리/보존 후 전파한다.

| 이번 직접 실행 | 결과 | 새 checkpoint 로그 |
|---|---|---|
| 보호 `live-controller-self` | 3통과, parent exit0 | `self-1.log` |
| 보호 단일 `live-controller-unit` | 최종77통과, guard violations0, parent exit0 | `unit-2.log` |

두 실행은 기존 clean env·검증 Python `-I -S -B`·동일 OS/worker 보호 입구에서
정식 `require_escalated` 심사를 거쳤다. 실패·거절 없이 통과했고 각 parent가
자기 temporary root를 제거했다. 단위/fixture는 자기 합성 파일·mock만 사용하며
실제 key/provider/DB·닫힌 live 승인 접근은0이다. 임의 raw 검사나 guard 완화는
없었다. 코드/테스트는 이 최종 검사 bytes로 동결하고 이후 결과 문서만 갱신했다.

새22사례는 실제 `OwnedHooks.verify`의 supplier closure를 실행하고 authority와
source IO/verifier만 주입했다. 반환 전 예외·승인 실패·read 진입 후 실패·취소·
timeout·정상 반환 뒤 count-unknown·유효 generation authority 뒤 실패·generation
예약 label을 구분했다. verifier의 고정값이 FIRST_SETTLEMENT_UNCONFIRMED 뒤에도
final accounting에 남는지, malformed/null/미반환, 최대2시도, 진단/회계 ACK
실패의 proof/hold·재호출 차단과 cancellation 전파를 검사했다. 서로 다른
key/error/body/stage/enum sentinel과 그 SHA256가 durable JSON·반환 요약·로그/
오류에 남지 않는지도 검사했다. 실제 PrivateStore의 atomic 파일 기록과24개
상한/종료 자리 예약을 사용했으나 이는 실제 PG/HTTP 검사 증거가 아니다.

첫 무키 unit76 뒤 독립 검토가 ACK-loss 회귀의 첫 결과도 hold라서 ACK 실패
자체의 차단 효과를 분리하지 못한다고 지적했다. 제품 코드 변경 없이 첫
결과를 observed/supplemented와 정상 원장 전이로 둔 뒤 첫 진단 ACK만 잃는
회귀를 추가했다. ACK 실패만으로 둘째 supplier/검증 callback 진입0, reserved
50,000,000 보존·cleanup 보류/proof 보존·claimed 유지가 확인됐다. 영향 unit만
77개로 재검증했다. self3의 제품/입구/고정 선택은 그 뒤 불변이라 반복하지
않았다. 테스트 작성 중 주석 줄바꿈의 정적 구문 오류는 보호 검사 전에
바로잡았으며 보호 실행의 실패·거절은 없었다.

추가 PG는 실행하지 않았다. 이번 변경은 controller의 bounded projection과
PG 밖 private journal의 기존 atomic ACK 결합이며 SQL/schema·원장 조회/정산·
gateway/verifier·DB 정리 API는 불변이다. 실제 임시 파일과 주입 ledger/proof로
해당 결합·기록 실패를 검사했으므로 기존 bootstrap 전체나 PG5를 반복할 새
DB 검증 필요성이 없다고 판단했다. 앞 절의 PG5와 실제 live 중단은 과거 source
기준 이력이며 이번 직접 검증으로 합산하지 않는다.

최종 정확6경로 manifest·검사 명령/시각/로그 hash·AI32와 checker/gateway/worker/
bootstrap/runner/CI/package/lock 불변 및 원본 WIP 보존 대조는 새 비공개
checkpoint에 남겼다. Git stage/commit/push/merge와 추가 실제 OpenAI 검증은
실행하지 않았다. 이번 통과는 관측 개선의 무키 수용이며 이전 실패 원인을
소급 확정하거나 실제 OpenAI 연결·품질 성공을 뜻하지 않는다. 이전 key-read/
count HTTP unknown과 닫힌 승인·USD0.05 hold는 그대로다.

v1.3 독립 최종 검토는 완료됐으며 미해결 finding은 없다. 검토된 controller
SHA256 `a429d3a1eef74f12e9932daa986b0a8d422784577531be7c9d2a1722dafefb91`과
unit SHA256 `cead407093afcb06a90c1aa5c18c71f58035aaf1f51e0b5996b83474552d06cb`는
동결 소스와 일치한다. 정상 observed/supplemented 첫 결과의 진단 ACK 손실만으로
둘째 callback/supplier 차단·one read·claimed/proof 보존·cleanup 미실행과
observed accounting 유지가 확인됐다는 독립 source 검토 결과를 전달받았다.
조율 측은 self3/unit77 로그·guard0·검사 root 정리도 읽기 대조했다. 이번에는
검토 상태 문서만 갱신했으며 코드/테스트 재실행이나 실제 연결 수용의 추가
통과로 집계하지 않는다.


## CF026 v1.4 단일 잔여분 continuation·무키 수용

정본 v1.4의 같은 승인 잔여분만 구현했다. 기존 closed 직접 경로와 원 예산을
다시 열지 않는다. 현재 개발 단계는 실제 원 승인 파일·키·grant/state·이전
실행 checkpoint를 열거나 바꾸지 않았고, 자기 합성 ancestry만 사용했다.

- 원 canonical namespace/안정 lock 아래 고정 단일 slot을 두고, slot 밖 발급
  tombstone을 먼저 파일·디렉터리 fsync한다. issued 영수증/상태의 ACK 뒤 외부
  capability만 runtime에 넘긴다. partial 발급, slot 삭제, witness 누락/변조,
  복제·alias·동시 발급/claim·restart는 재발급 또는 실행을 열지 않는다.
- 원 grant/state/closure 증거의 raw bytes hash와 canonical digest를 구별한다.
  원 expiry는 역사이고 현재 권한·evidence·source·runtime·expiry는 별개다.
  첫 동일 request 한 건만 허용하며 둘째 질문과 새 prepare key는 거절한다.
  원50,000,000+child50,000,000nanoUSD의 보수 hold와 원1+child1 시도를 강제한다.
  원 사용량이 불명이므로 전체 실사용액은 null이며 청구액이라고 표현하지 않는다.
- 새 child PG/epoch는 기존 원장의 복원이나 새 예산이 아니다. 실제 Principal·
  pending preparation/attempt/spec/request를 fresh 확인한 뒤 root count/generation
  권한을 각각 단1회 영속 ACK한다. 기존 PhaseBudget의 local 예약 ACK가 그 뒤에
  오고, local count ACK를 다시 확인한 후에만 지연 supplier를 호출한다.
- live는 기존 `verify_live`를 그대로 호출한다. 그 live factory의 synthetic
  authority/mapping/transport 거절과 shared-driver wrapper를 복제하지 않는다.
  synthetic만 실제 continuation authority→기존 PhaseBudget/gateway/ASGI/
  PreparationService를 주입 조립한다. 합성 transport를 live로 넘기지 않는다.
- 실패·취소·회계 ACK 손실은 이후 송신을 열지 않는다. bounded fresh child 회계와
  원 hold를 합친 증거를 정리 전에 기록하고, ACK 불명이면 claimed/proof/hold를
  보존한다. journal24 및 terminal3 공간은 유지하고 cancellation을 재전파한다.
- controller source는89,326bytes다. source-copy provenance 읽기에만128KiB를
  명시했고 key/grant/state의 기존64KiB 한도는 유지했다. 양 경계 회귀를 실행했다.

### 이번 직접 실행

모든 명령은 전용 worktree에서 기존 clean env/검증된 절대 Python `-I -S -B`로
실행했고 공식 `require_escalated` 심사를 통과했다. 현재 회차의 denied/pending/
uncertain 실행은 없다. 이전 거절과 실제 일회 중단 기록은 위 이력대로 보존한다.

| 선택 | UTC 시작–종료 | 결과 | private 로그 basename |
|---|---|---|---|
| 보호 `live-controller-self` | 13:00:34–13:00:35 | 3통과, exit0, 자기 root 제거 | `self-1.log` |
| 보호 단일 `live-controller-unit` | 13:00:52–13:00:57 | 124통과, guard0, exit0, 자기 root 제거 | `unit-1.log` |
| source-copy owned synthetic continuation PG | 13:04:37–13:04:42 | 5묶음, exit0, 자기 DB/source-copy 제거 | `pg-1.log` |

실행일은2026-11-10 UTC다. self/unit은 기존77회귀에 v1.4의47사례를 추가한
단일 파일124사례다. ancestry/발급 fsync·부분 발급·동시성·expiry·권한/phase·
ACK 손실·취소·timeout·회계/proof·재시작·source bound 검사는 주입/파일 합성이다.
이들을 실제 PG나 실제 provider 호출로 합산하지 않는다.

새 실제 PG는 한 회차/한 자원이다. 원 부모는 합성으로 만든 closed 역사이며
그 bytes가 끝까지 불변임을 직접 대조했다. 기존 소유 runner·동일 제한 역할/
migration/실제 Principal과 fresh child epoch를 사용했다. root 권한 count1/
generation1, child 원장 count1/generation1·reserved50,000,000, 기존 MockTransport의
observed 정산/supplemented·저장/owner GET, 최종11개 journal과 다음 순서를 검사했다.
`root_count_authority_ACK` → `local_count_ACK_before_supplier` →
`root_generation_authority_ACK` → `final_accounting` → `cleanup_confirmed`.
최초 local0/0/0과 generation 직전1/0/50,000,000도 직접 확인했다. 새 cap의
replay/restart2회는 DB/송신 전에 거절됐다. 기존 소유 receipt에 한정한 제거/부재
검사를 거친 owner의 `_removed`와 source-copy 부재를 확인했다. 관측된 금지 접근은
private/network/HTTP/dotenv 모두0이며 실제 provider 요청도0이다.

로그 SHA256:
- self: `0a7c149185061e61d00e40ce3c4dee4e2b3e49b26325bb47f88f267be863ed1a`
- unit: `aacaaa0110776f216ca01edf32274ad03ccb60eff62886a0460f03d40b40c679`
- PG: `2aa4cb83380004992ac18321a2e244db2b0052185cf4de0f932312c85d248383`

PG의264 source는 복사 전/후와 정리 전 원본/사본 hash를 대조했다. 최종 변경은
결과 문서뿐이며 제품 source와 검사는 실행 bytes로 동결한다. AI32, 기존 verifier/
gateway/runner/bootstrap/CI/package/lock은 시작 hash와 일치한다. 정확6경로·실행
명령·source/log manifest·cleanup 근거·NUL 목록은 새 private 인계에 보존한다.
이전 v1.3 동결/실제 실행 artifacts는 덮어쓰지 않았다. 최종 독립 검토는 대기다.

### 남은 실제 실행 전제

실제 continuation receipt/slot은 발행하지 않았다. 조율 측의 원 실제 ancestry/
closure 증거·원 lock·불변 bytes 대조, 현재 외부 권한과 실제 source/runtime 및
공식 evidence hash·짧은 expiry 고정, 검토된 live launcher/source-copy provenance가
필요하다. live `verify_live` 연결은 무키 dispatch 회귀이며 실제 supplier/공식
HTTP·실제 모델 품질은 미검증이다. 원 실제 key/count HTTP·실사용액 unknown을
이번 합성으로 소급 확정하지 않는다. 실제 브라우저·운영 DB/한도·Frontend·
Technical·Git 게시도 실행하지 않았다. 이번 결과는 무키 continuation 경계 수용이다.


## v1.4 독립 검토 후 발급 authority 경계 보완

앞 절의 로컬 tombstone만으로는 slot과 witness를 둘 다 삭제한 뒤 새 permission
객체로 발급하는 경로를 닫지 못했다. 객체별 `issuance_attempted`와 원 directory
identity는 삭제 이력을 증명하지 않는다. 이 finding을 확인했으며, 앞 절의 무키
결과를 실제 live 발급 수용 완료로 해석하지 않는다. 이전 동결 manifest/로그는
보존하고 새 영향 checkpoint에서 보완했다.

기존6파일 안에서 `OneShotIssuanceAuthority`를 필수 입력으로 추가했다. 원 anchor
단위 namespace가 독립 authority에 명시 available로 사전 등록돼 있어야 한다.
발급은 동일 원 lock 아래 외부 observe → available-to-consumed 원자 CAS/영속 ACK
→ fresh consumed 재조회 확인 → 로컬 tombstone/slot 순서다. 외부 state는 원 anchor에
묶이며 fresh permission·다른 receipt ID로 reset하지 않는다. 정확한 authority
identity를 receipt의 새 필수 `issuance_authority_sha256`에 결합한다. 기존 receipt를
다른 authority로 보내도 거절한다. 소비 ACK 불명·readback 실패·취소이면 로컬
파일/DB/송신을 열지 않으며 이후 소비 기회를 다시 만들지 않는다.

claim과 각 phase에서도 같은 소비 기록을 재조회한다. authority 부재/손실/불명은
available이 아니고 자동 생성·초기화하지 않는다. 두 로컬 artifact를 모두 지우고
새 permission과 재연결한 합성 issuer를 제공해도 consumed 상태로 재발급을 거절하는
회귀를 추가했다. 외부 ACK 손실·malformed ACK·readback 실패·취소·authority 교체와
새 receipt로 namespace reset 시도, runtime bootstrap 전 외부 상태 손실도 검사했다.
원 grant/state는 그대로이며 추가 예산이나 실제 발급을 만들지 않았다.

### 실제 외부 authority는 아직 제공되지 않음

모듈에는 live authority 저장소/서비스 구현이나 기본 provider가 없다. 기존 verify
callback의 Boolean 승인만으로 발급할 수 없으며 필수 one-shot observe/CAS 입력이
없으면 차단한다. 실제 조율에서는 독립적으로 영속하는 동일 namespace와 고정
identity, 사전 등록·원자 CAS·ACK·fresh readback·손실 시 거절을 입증하는 provider가
필요하다. 실제로 그런 provider를 제공/검토하기 전 **live 발급은 blocked/pending**다.
권한 거절을 우회하는 작업이 아니며 이 설계 결정을 합성 성공으로 해소하지 않는다.

이번 파일 기반 authority는 자기 fixture에서 외부 provider 계약을 흉내 낸
synthetic-only callback simulation이다. live mode에 사용할 수 없다. 해당 파일
저장이 실제 독립 저장소의 내구성·rollback 방지·재해 복구를 입증하지 않는다.
독립 authority 자체를 reset하거나 거짓 available을 반환해도 안전하다고 주장하지
않는다. 현재 실제 authority 연결·소비·receipt 발급·키/provider 호출은 모두0이다.

### 영향 검증 이력과 최종 결과

첫 unit은135통과/1실패/guard0이었다. 이전 tombstone fsync 주입이 새 외부 소비
ACK의 fsync에 먼저 걸려 tombstone 존재 assertion이 실패했다. 주입을 기존 로컬
tombstone 경계에 정확히 한정했고 제품 로직은 이 실패 때문에 바꾸지 않았다.
unit 재검증136통과 뒤 authority identity의 receipt 결합을 추가하여 교체 거절을
보완했다. 그 최종 source로 self/unit 및 필요한 synthetic PG를 확인했다.

| 최종 선택 | UTC 시작–종료 (2026-11-10) | 결과 | private 로그 basename |
|---|---|---|---|
| 보호 `live-controller-self` | 13:18:19–13:18:19 | 3통과, exit0, 자기 root 제거 | `self-2.log` |
| 보호 단일 `live-controller-unit` | 13:18:24–13:18:30 | 137통과, guard0, exit0, 자기 root 제거 | `unit-3.log` |
| owned synthetic PG 영향 회차 | 13:19:18–13:19:22 | 5묶음, exit0, 자기 DB/source-copy 제거 | `pg-2.log` |

발급 ACK가 bootstrap 앞에 추가되어 실제 결합 영향 확인이 필요했다. 최초 영향
PG는5묶음 통과/정리됐고, 이후 receipt schema에 authority identity를 결합한 최종
bytes로 한 번 더 확인했다. 두 회차를 한 회차로 숨기거나 단순 callback을 실제
외부 authority로 집계하지 않는다. 기존 PG를 폐기하거나 과거 전체 suite/FE를
반복하지 않았다. 최종 PG는 합성 외부 consumed 기록, 실제 새 child Principal/
epoch/PhaseBudget·ASGI·준비 저장과 count1/generation1·누적 보수 hold100,000,000,
원 합성 parent 불변·replay/restart 거절·owner `_removed`와 source-copy 부재를
검사했다. 실제 provider0과 관측된 금지 접근0을 유지했다.

최종 로그 SHA256:
- self: `d25efea054821d1d5032def5d5831ae7e637b0bfa2abdb1926472e377a47b9b3`
- unit: `0cf04910768db38c1f46852f905717fa4b8a2ef95ecb90ae8a762172946741bb`
- PG: `d3a471fd88b09faad13c36ee883011d1da210601c9a0b5f8c81eeee742bbf274`

모든 실행은 기존 보호 입구와 공식 require_escalated 심사를 유지했다. 현재 도구
권한 denied나 불명 자원은 없다. 최초 unit 실패는 해결된 회귀 실패이며 승인
거절과 다르다. 현재 source/interface의 독립 최종 검토는 완료됐으며 미해결 구체 finding은
없다. 조율 측과 독립 검토자가 exact6 manifest 및 self3/unit137 guard0·synthetic
PG5/정리 로그의 해시 일치를 대조했다. 실제 외부 authority 설계 결정은 여전히
pending이며 live 발급 blocked를 유지한다. 최종 실행264 source와 현재 bytes를 대조한 뒤 결과 문서만 갱신했다.
AI32/verifier/gateway/guard/runner/CI/package/lock은 앞 동결값 그대로다. 기존 실제
live 증거/closed grant/state/unknown hold는 읽거나 수정하지 않았고 Git도 미실행이다.

## CF026 v1.6 새 승인 aggregate 구현·현재 검증

정본 v1.6 SHA256 `48aec6c42fda7fa81d0c288a73d3e2d763aa1c889b19c9d0f6e2f28aecf2ed8e`를
읽고 같은 branch/HEAD의 기존6파일을 새 private checkpoint에 먼저 보존했다.
실제 새 승인 사건·장부·원 grant/state/hold·키는 열거나 발급/변경하지 않았다.
실제 승인 식별자·대화·원 private 경로를 이 문서나 공개 코드에 복사하지 않는다.
v1.4의 실제 외부 one-shot authority 미제공 차단도 별개로 유지한다.

새 경로는 `AggregatePermission`·조율 `CoordinationHistory`·명시 bootstrap과
open-only `AggregateSession`으로 분리했다. 조율 이력의 최초 시도 ACK 뒤에만
root/header/lock/state를 만들며, 실패/부분/불명 후 새 permission으로 초기화하지
않는다. Root/lock/header identity와 최신 sequence/hash/교체 inode를 고정한다.
각 전이는 조율 pending intent ACK→로컬 atomic replace/fsync/fresh read→확정
조율 head ACK로 진행하고, 불명 target을 마지막 확정 head로 채택하지 않는다.
재시작은 독립 보존한 동일 binding/head와 별도 explicit restart attestation이
없으면 차단한다. 로컬 장부와 조율 기준을 함께 잃으면 자동 복구할 수 없다.

예약 ACK→발행권 소비 ACK→child 결합 ACK→시작권 소비 ACK→기존 runner를
구현했다. exact intent의 현재 조율 승인을 매 단계 대조하며 원 carry50,000,000과
child100,000,000의 총150,000,000/잔여850,000,000을 보존한다. 어떤 결과에도
예약·권리를 환불하지 않는다. Current Flow913,500,000은 잔여 초과, Technical은
미편입으로 거절한다. 새 allocation은 잔액만으로 자동 생성되지 않는다.

Child validator·첫 observed gate·legacy usage/claim·verify_live는 유지했다.
Child final accounting에 aggregate ACK를 결합하는 한정 callback을 추가하여,
부모 회계 ACK 불명 시 기존 proof 보존 경로로 정리를 건너뛴다. Child terminal
결과에는 관측 횟수/nullable 추정액·HTTP unknown과 회계/정리 digest를 남긴다.
취소/종료 뒤 새 작업은 닫고 bounded 회계/cleanup만 허용한다. Aggregate state
64KiB·최대9 allocation, child journal24, key/grant/state64KiB를 유지했다.
Controller source130,830bytes로 코드 provenance128KiB 상한 안에 있다.

### 직접 실행과 실패 구분

기존 clean env/검증된 Python `-I -S -B` 보호 입구의 formal require_escalated 심사로
self3과 unit179가 먼저 통과했다. 이어 commit 경계의 예약/권리 역행 거절과
정리 전 aggregate 회계 ACK/proof 보존을 추가하고 필요한 self3·단일 unit187을
재검증했다. 최종 unit은187통과/guard0/exit0이며 각 자기 검사 root를 제거했다.
초기 기록용 shell 경로 오타는 검사 실행 전 실패였고 수정했다. 검사 거절이나
보호 해제·raw 우회는 없었다. 기존 의미/FE/PG 전체 suite는 반복하지 않았다.

신규 owned synthetic PG 한 회차는 실제 생성/migration/Principal/child epoch를
거쳐 기존 checker의 synthetic factory에서 거절됐다. 그 factory는 정확히
`현대건설 수급`·답변 없음만 허용하지만, aggregate는 정본의 두 고정 후보/답변을
보존하므로 조건이 다르다. 실패는 CONTROLLER_FAILED로 정규화됐으며 실제
count/generation/예약은0/0/0이다. 의미 모델·provider 오류라고 단정하지 않는다.
실제 OpenAI/key/provider 호출은0이다.

이 실패 뒤 부모 예약150,000,000과 발행/시작권은 유지·frozen됐다. Fresh child
회계가 부모에 ACK됐고 child closed/cleanup_confirmed 및 source-copy 부재를
확인했다. 기존 `OwnedHooks.cleanup`이 원 receipt의 제거/부재와 `_removed`를
검사한 뒤에만 cleanup_confirmed를 기록하는 경로다. 단순 owned_db_removed
문구만으로 정리됐다고 추정한 것이 아니다. 자원 불명이나 현재 권한 denial은 없다.

### 최초 PG 차단과 조율 사항 (후속 해소 전 이력)

최초 PG 결합 수용은 **실패/미완료**였다. Checker의 고정 synthetic 문법이나 정본의
승인된 두 질문을 바꿔 통과시키지 않는다. 현재 허용된 기존 synthetic factory로는
두 exact 후보를 검증할 수 없다는 계약 차이다. 최소 대안은 기존6파일 안의
aggregate-only synthetic DI 조립이 기존 PhaseBudget/gateway/ASGI/PreparationService와
검토된 MockTransport를 사용하게 명시하는 것이다. 이는 실제 live factory나
synthetic 입력 guard 변경과 구분해 검토해야 한다. 당시 해당 허용 범위 조율 전 PG 재실행을
보류했다. 이후 조율 측이 같은6파일의 synthetic DI 조합을 명시 요청했고 아래
최종 결과로 이 검증 차이를 해소했다. 기존 raw pytest/guard 완화·다른 자원 fallback은 없다.

실제 최초 bootstrap에는 동일 새 승인 사건의 canonical root·불변 carry 증거,
초기화 시도/성공/불명과 최신 head를 재개 가능하게 보존하는 조율 이력, exact
scope/source/runtime/가격 근거/expiry와 최초 allocation의 현재 권한 고정이 필요하다.
그 실제 이력이 준비됐다고 합성 callback 성공으로 주장하지 않는다. 실제 사용자
장부·child grant/allocation 발급과 provider, 원 private 실행 증거, Git 작업은 미실행이다.

### v1.6 DI·취소 보완 검증 (최종 기한 재검사 전)

조율 측이 exact 후보를 유지하는 올바른 synthetic DI 조합을 명시 요청했다.
기존 continuation의 합성 조립을 공유하는 `synthetic_preparation_assembly`와
`AggregateSyntheticHooks`를 기존6파일 안에 두었다. 기존 checker·live factory의
허용 조건은 바꾸지 않았다. Shared helper는 synthetic binding만 받으며 실제
PhaseBudget/Principal/기존 epoch SELECT, gateway와 검토된 MockTransport·ASGI·
PreparationService 저장/owner GET을 사용한다. Aggregate의 현재 승인 callback도
매 phase 재검사한다. Live는 이 조립을 거치지 않고 기존 verify_live를 사용한다.
승인된 두 질문/답변을 바꾸거나 임의 성공 후보를 직접 반환하지 않는다.

독립 검토의 늦은 취소 finding도 수정했다. 선행 FIRST_SETTLEMENT 오류가 있더라도
aggregate accounting ACK 또는 terminal 기록 중 뒤에 온 CancelledError가 최종
오류보다 우선하여 재전파된다. Bounded 회계와 기존 proof 보존/정리는 유지한다.
두 late-cancel 행동 회귀와 exact 두 draft의 DI 전달·live 거절 회귀를 추가했다.
공유 synthetic request/grant builder와 중복 설명/import 정리로 최종 controller는
130,075bytes다. 코드 provenance128KiB를 늘리지 않았으며 실제 source-copy의
aggregate_header 읽기와 기존 ReviewedCodeRoot 단위 경계를 통과했다.

| 최종 선택 | UTC 시작–종료 (2026-11-10) | 결과 | private 로그 basename |
|---|---|---|---|
| 보호 `live-controller-self` | 14:24:15–14:24:15 | 3통과, exit0, 자기 root 제거 | `self-3.log` |
| 보호 단일 `live-controller-unit` | 14:24:20–14:24:27 | 190통과, guard0, exit0, 자기 root 제거 | `unit-3.log` |
| 수정 후 owned synthetic aggregate PG | 14:25:18–14:25:23 | 4묶음, exit0, 자기 DB/source-copy 제거 | `pg-2.log` |

최종 PG는 새 자기 합성 aggregate와 새로운 child 한 건만 사용했다. 실제 parent
파일 reserve→issue→bind→start→accounting→terminal 조율 ACK, 새 owned DB/실제
migration·Principal·최초 child epoch와 기존 PhaseBudget, exact 두 준비 입력의
MockTransport success→missing usage를 확인했다. Child count2/generation2·예약
100,000,000·blocked/active unknown hold가 남고, aggregate carry50,000,000+
allocation100,000,000=150,000,000·잔여850,000,000·전체 actual estimate=null을
검사했다. Current Flow913,500,000 초과 거절과 같은 child 재시작 거절, 원 receipt
소유 자원의 `_removed`·source-copy 부재, 금지 접근 관측0·실제 provider0도 확인했다.

해당 시점까지 owned PG는 최초 실패1회와 수정 후 성공1회, 총2회였다. 각각 별도 자기
fixture/DB이며 실패의 예약/권리는 보존했다. 실제 사용자 사건을 새로 초기화해
예산을 회복한 것이 아니다. 실제 coordinator durable-history 구현의 증거로
합성 file/CAS를 확대하지 않는다. ACK loss·concurrency·head rollback/유실·expiry/
cancel·단조 상태 및 proof 조합은 별도 파일/callback unit이며 실제 PG4묶음과
합산하지 않는다. 기존 PG전체/FE/브라우저/실제 모델은 재실행하지 않았다.

최종 로그 SHA256:
- self: `9baa02210dd81fbece0f087f7a853adb9bbca91f78171f40a0a52a212a9bf086`
- unit: `0bc8c3b6c1e42b8d59a2ecbfadb5556a569280709bba53d10c96c8bcf90cb252`
- PG: `3a4270d521045662f045900436e8ebead9de9b2393974c15fcf78c22c220b2b2`

최종 실행264 source와 현재 제품/검사 bytes를 대조한 뒤 결과 문서만 갱신한다.
원6파일 시작 snapshot·최초 실패와 blocked manifest·이전 모든 실제 승인/hold
기록은 보존한다. AI32/checker/gateway/guard/runner/CI/package/lock은 불변이다.
최종 독립 검토는 대기이며 현재 실행 권한 denial·불명 자원은 없다. 남은 실제
최초 issuer/조율 history·canonical identity/기대 head·source/공식 evidence/expiry
고정은 별도 조율 단계다. v1.4 live authority 차단은 별개로 유지한다. 이번 무키
수용이 실제 OpenAI 품질·Flow/Technical·운영·브라우저 완료는 아니다.

### v1.6 최종 동결: ACK 대기 뒤 만료 재검사

마지막 대조에서 bootstrap 시도·pending write·발행권·시작권 ACK 대기 동안
유효기한이 지나는 경우를 보강했다. 대기 뒤, root 생성/상태 write/child 생성/
runner 직전에 현재 승인·기한을 다시 검사한다. 늦은 ACK는 이미 소비된 기회나
예약을 돌리지 않으며 다음 부작용만 닫는다. Bootstrap/예약pending/발행/시작
늦은 ACK4사례에서 create/runner0 및 마지막 확정 head와 pending 보존을 검사했다.
Code provenance는 그대로128KiB이며 최종 source130,260bytes다. Key/grant/state는
여전히64KiB다. 새 의존성·새 endpoint·기존 guard 변경은 없다.

| 최종 선택 | UTC 시작–종료 (2026-11-10) | 결과 | private 로그 basename |
|---|---|---|---|
| 보호 self | 14:30:58–14:30:58 | 3통과, exit0, root 제거 | `self-4.log` |
| 보호 단일 unit | 14:31:03–14:31:10 | 194통과, guard0, exit0, root 제거 | `unit-4.log` |
| 최종 bytes owned aggregate PG | 14:31:36–14:31:40 | 4묶음, exit0, DB/source-copy 제거 | `pg-3.log` |

최종 PG는 위 ACK 재검사에 따른 승인 callback/조립 영향과 same-source binding을
확인한 회차다. 이 작업의 실제 owned PG 총3회(최초 factory 거절1, DI 수정 성공1,
최종 기한 재검사 성공1)를 구분해 보존한다. 각각 자기 합성 parent/자원이었고
모두 child cleanup_confirmed와 source-copy 부재를 확인했다. 실제 승인 사건을
재bootstrap하거나 이전 예약을 환불한 것이 아니다. 이전 PG4 결과를 최종 source로
거짓 재표기하지 않았고 각각의264 source manifest를 별도로 남겼다.

최종 self/unit/PG source와 현재 bytes는 일치하며 결과 docs만 이후 갱신했다.
최종 로그 SHA256:
- self: `aa5d94c0230f158406425c98c733d9ce859c6847f0434396cf0dc760fca9776f`
- unit: `245f6f9eee96473a7ce1abadddd50bcd5759c6f1430a43406152c0e9f8a3266a`
- PG: `3a4270d521045662f045900436e8ebead9de9b2393974c15fcf78c22c220b2b2`

실제 장부·allocation/grant 발급·key/provider/Git은 미실행이다. 현재 권한 denial·
불명 자원은 없다. 남은 것은 최종 독립 검토와 조율 측의 실제 단일 bootstrap/
이력·기대 head·정확 intent/source/공식 evidence/expiry 고정이다. 원 unknown
carry/closed 기록과 v1.4 authority 차단은 불변이며 별도 승인 경로와 혼동하지 않는다.


### 독립 최종 검토 후 마지막 history await의 expiry gap 보완

독립 검토가 `_check`의 초기 시간 검사 뒤 마지막 `aggregate_history_read`를
await하면 반환 전에 만료될 수 있음을 확인했다. cleanup=False일 때 그 마지막
await 뒤에 await 없는 현재시각/expiry 검사를 추가했다. 다른 controller 로직은
수정하지 않았다. 보완 전 동결 source와 비교해 guard147bytes 한 줄만 추가됐음을
대조했다. 최종 controller130,407bytes로128KiB 이내다.

실제 `_check`·issue·start 경로를 실행하는 지연 history.read 회귀3건을 추가했다.
Read가 initial 시간 검사 뒤 만료 시각으로 넘어가면 직접 check는 거절하고,
issue는 child root를 만들지 않으며 start는 legacy runner 진입0이다. 이미 소비된
예약/발행/시작권은 보존하고, 직접 check 경로의 identity-valid cleanup=True는
만료 뒤에도 가능함을 확인했다. 기존 source assertion이나 fake 성공만으로
검사한 것이 아니라 production state helper를 실행한 무키 회귀다.

2026-11-10 UTC14:39:06 보호 self3, 14:39:11–14:39:19 단일 unit197이 통과했다.
각 exit0·guard0·owned test root 제거를 확인했다. Self5/unit5는 최신 source다.
- `self-5.log` SHA256 `aa5d94c0230f158406425c98c733d9ce859c6847f0434396cf0dc760fca9776f`
- `unit-5.log` SHA256 `c38ef2aafe59933915c1846a4c266ef089d5f82f6acf30bfdf19d6e06b98205c`

이 한정 시간 가드 변경에는 PG를 반복하지 않았다. 위 PG3의4묶음은 보완 직전
source의 직접 실행 증거로 보존하며, 이를 최신 source로 재실행했다고 표시하지
않는다. Actual SQL/PhaseBudget/gateway/child 회계·정리 구현은 불변이고 새
시간 가드는 위 집중 회귀로 검증했다. 최종 manifest에는 PG 실행264 hash와 현재
self/unit264 hash를 별도로 두고 차이는 controller/test2개임을 대조한다.
새 실제 장부·grant·키/provider·DB·Git 작업은 없었다. 현재 도구 denial·불명 자원은
없으며 최종 독립 재검토와 실제 issuer binding 고정은 pending이다.

### 종료일 이후 synthetic 재현성과 live 만료의 분리

추가 독립 검토가 synthetic fixture까지 실제 승인 종료일로 clamp하여 이후 CI나
합성 PG가 만료되는 재현성 문제를 확인했다. `aggregate_deadline`은 live mode에서만
고정 종료일과 header expiry의 최소값을 사용한다. Live header의2026-11-10 21:00 UTC
초과 expiry 거절은 그대로다. 명시 synthetic mode는 자기 fixture 생성시각+6분
lease만 사용하며, synthetic history/source/child scope 및 고정 synthetic DI가
필요하다. 실제 승인 시간/권한을 연장하는 기능은 추가하지 않았다.

기간 만료 회귀는 fixture 자신의 expiry를 기준으로 바꿔 날짜와 무관하게 검사한다.
추가2회귀는 종료일+366일의 synthetic full controller 왕복과 live 고정 종료 거절,
synthetic→live mode 변경 거절이다. 실제 live source 검증을 성공으로 모사하거나
새 실제 장부를 발급한 결과가 아니다. 마지막 history-read expiry3회귀도 유지했다.

| 최종 선택 | UTC 시작–종료 (2026-11-10) | 결과 | private 로그 basename |
|---|---|---|---|
| 보호 self | 14:45:42–14:45:42 | 3통과, exit0, root 제거 | `self-6.log` |
| 보호 단일 unit | 14:45:47–14:45:55 | 199통과, guard0, exit0, root 제거 | `unit-6.log` |
| 미래 시계 owned synthetic PG | 14:50:03–14:50:08 | 4묶음, exit0, DB/source-copy 제거 | `pg-5.log` |

미래 PG는 controller의 synthetic 실행에만 종료일+366일 시계를 주입했다. OS 시계,
checker/gateway/DB 시계나 live 경계는 변경하지 않았다. 첫 미래 시도는 시계
하네스의 fromisoformat이 datetime 서브클래스를 반환하여 기존 PhaseBudget의
정확한 datetime 타입 검사에서 예약 전에 거절됐다. Count/gen0·부모 예약 유지·
child closed/cleanup_confirmed와 source-copy 부재를 확인했다. 제품이나 checker의
타입 검사를 바꾸지 않고 하네스 파싱만 표준 datetime 반환으로 맞춰 재검증했다.

최종 PG는 exact 후보의 count2/generation2·unknown hold·aggregate150,000,000/
잔여850,000,000·Flow 초과 거절·원 receipt 자원 제거를 확인했다. `real_provider_requests=0`,
`synthetic_clock_after_live_deadline=true`, `clock_parse_exact_datetime=true`,
`OS_clock_modified=false`가 기록됐다. 마지막 source의 실제 PG 조립 증거다.
실제2027년 환경 전체를 검증한 것이 아니라, 현재 환경에서 합성 controller의
종료일 이후 경계를 재현했다. 실제 운영 시간·권한은 연장하지 않았다.

이 작업의 owned PG는 총5회(최초 factory 거절, DI 성공, 기한 guard 성공,
미래 시계 하네스 타입 거절, 수정 하네스 성공)이며 모든 자기 자원/source-copy
정리를 확인했다. 실패와 수정·각 실행 source를 숨기거나 합산하지 않는다.
정리 전에 부모 회계 ACK를 지켰으며 실제 사용자 사건을 재초기화하지 않았다.

최종 로그 SHA256:
- self: `9baa02210dd81fbece0f087f7a853adb9bbca91f78171f40a0a52a212a9bf086`
- unit: `d58f4b9621739be7e7e40929c9bb03e2f5b4bfcf9dee78f108434665f08209fa`
- PG: `a5af20a0f257d886919b8fb5a0595691402f003b34b4e751d04b932827bdefa4`

최종 controller130,484bytes/코드128KiB 이내이며 credential/grant/state64KiB는
불변이다. PG5의264 source와 최신 self/unit/제품 bytes는 일치한다. 결과 docs만
그 뒤 갱신했다. 원 실제 승인·grant/state/unknown hold·실제 key/provider·Git은
추가 접근/변경/실행하지 않았다. 현재 tool denial·불명 자원은 없고 최종 독립
재검토 및 실제 조율 binding만 pending이다. v1.4 authority 차단도 유지한다.

## 게시 전 독립 검토 완료와 최신 base 대조

구현/interface 및 공개 범위의 독립 최종 검토를 완료했으며 미해결 구체 finding은
없다. 검토된 controller/unit과 self3/unit199/guard0·동일-source 미래 시계 owned
synthetic PG4묶음·정리 증거를 해시로 대조했다. 위 pending 문장은 각 과거 시점의
이력이다. 실제 모델 검증·실제 issuer 검증의 미완료 상태는 바뀌지 않았다.

게시 기준 develop은 CF027 병합 `1736ddc4f245ca668aae719bc8989bc83fbf2601`이다.
전용 branch를 fast-forward했고 upstream의 Frontend/문서5파일과 CF0266경로는
겹치지 않는다. 이후 CF026 제품/검사 bytes 및 검증 입력264개/AI32가 기존 동결값과
동일함을 읽기 대조했다. 이번 결과 addendum만 변경했으므로 기능 검사를 반복하지
않았다. 다른 worktree의 기존 WIP는 보존했다.

별도 실제 실행기의 활성화는 아직 승인 심사에서 진행되지 않았고, 새 aggregate의
실제 journal/장부·키/API는 이 게시 작업에서 만들거나 사용하지 않았다. 현재 결과는
실행기 구현·합성 검증 완료이며 실제 모델·Flow/Technical/provider·브라우저/운영
인수 완료가 아니다. 이전 실제 시도의 송신/사용량 unknown과 보수 carry는 보존한다.
원격 exact-head CI·Ready 이후 CI와 정상 병합 결과는 별도로 확인해야 한다.
## Fixed-window renewal preparation

The resumed controller keeps the historical shutdown constant and adds one closed
current window. Live headers require the reviewed start lower bound and expiry
upper bound; the authority is checked again after awaiting its acknowledgement.
No header fields, endpoints, retry policy, token caps, budget amounts, original
hold or issuance identities were changed. The controller remains below its
131,072-byte provenance cap. The private adapter, ceremony, descriptor builder
and frozen verifier use the same window; entry/runtime/coordinator remain unchanged.

Focused protected self3/unit207 passed with guard violations0 and owned-root
cleanup. The first self invocation stopped before worker execution because it
used the resolved interpreter instead of the documented absolute virtualenv entry.
Correcting that caller path preserved the interpreter guard. Separate private
helper tests55 passed using synthetic paths, with actual key/resource access,
network and subprocess operations blocked by the test audit.

At this preparation checkpoint the three release flags remain False. No live
grant, aggregate, database or provider request has been created. Final source,
runtime and descriptor binding, independent review and the actual one-shot run
remain pending. These tests are not evidence of actual model interpretation.

## 갱신된 시간창의 실제 일회 실행 결과

현재 창의 source264, runtime, descriptor와 실행 명령의 독립 검토를 완료했다.
기존 일회 entry를 정식 도구 심사로 요청했고 허용되어 프로세스가 시작됐다.
`preflight-reviewed`는 성공했지만 `execute-reviewed-once`는 안전 중단 상태로
exit1을 반환했다. 같은 동작을 재시도하거나 다른 provider 경로로 전환하지 않았다.

최종 진단은 첫 후보의 `supplier_failure` / `KEY_SOURCE_INVALID`다. 승인 확인 뒤
`source_read_entered`를 기록했지만 `source_read_returned`에는 도달하지 않았다.
이 고정 코드는 로컬 `single_key`의 입력 형식 검증에서 발생한다. 값이나 형식의
세부 원인은 출력하거나 추가로 읽지 않았고, OpenAI 인증 오류로 단정하지 않는다.
첫 `FIRST_SETTLEMENT_UNCONFIRMED` gate에서 중단되어 둘째 후보는 실행하지 않았다.
모델 출력·종목/의도 해석 품질은 검증하지 못했다.

fresh ledger의 count-stage 예약1 / generation 예약0, estimated_nano=null,
blocked/unknown hold를 cleanup 전에 영속 기록했다. 예약 횟수는 실제 HTTP 호출
횟수가 아니다. count/generation HTTP 필드는 unknown을 유지한다. 이 실행의
phase 보수 hold는50,000,000nanoUSD이며, 외부 aggregate의 전체 예약은 과거
50,000,000 carry와 이번 allocation100,000,000을 합한150,000,000nanoUSD다.
이는 실제 청구액이나 관측된 사용액이 아니며, allocation은 환불하지 않는다.
aggregate는 frozen이고 child는 closed여서 새 실행을 자동으로 열지 않는다.

소유 receipt에 한정한 PG cleanup_confirmed와 entry의 source-copy close 반환을
확인했다. 원 실제 carry 파일 해시와 실행 source264는 전후 동일했다. 임시
세 RELEASED는 새 검토된 False bytes/hash로 전부 복원됐다. 원 key/environment
파일을 수정하거나 비밀·비밀 해시·raw provider 응답을 결과에 넣지 않았다.
실행 시점 frozen manifest는 보존하고 문서 갱신 hash를 별도 기록한다.
이번 결과는 실행 심사 통과 및 실제 안전 중단/회계/정리 관측이며, OpenAI 연결·
실제 모델 해석·Flow 저장·Technical·브라우저 수용 통과가 아니다.

## 키 출처 서비스 경로 정정 · 무키 검증

사용자의 서비스 위치 정정에 따라 검증기의 고정 source를 main worktree의
`verith/ai/.env`로 맞춘다. 이전 Backend source 지정은 잘못됐다. 조율 측의
비노출 검사에서 Backend의 대상 선언이0개였고 다른 형식 오류는 없었다는
보고를 받았다. 사용자 키 값이 잘못됐다고 판단할 근거는 없다.

Controller의 정확한 source 경로만 변경하고 Backend/Frontend/검증용 worktree/
다른 workspace/다른 파일명 거절 회귀를 추가한다. 기존 owner·regular/nlink1·
no-symlink·mode0644·identity drift 보호는 변경하지 않는다. 실제 `.env` 내용은
읽지 않고 합성 metadata와 기존 무키 보호 검사만 사용한다.
원 실행의 grant/state/aggregate/journal/descriptor/runtime/manifest와 예약은
불변으로 보존하며 새 source로 재결합하거나 재실행하지 않는다. 기존 private
runtime도 실행 당시 증거로 유지하고, 향후 수정안만 별도 checkpoint에 저장한다.
기존 외부 정본의 Backend 경로와 충돌하는 부분은 사용자의 후속 서비스 위치
정정에 따라 이 범위에서만 변경했다. 이 수정은 실행 기간이나 권한의 연장이 아니다.


이번 정정 후 기존 보호 `live-controller-self`3개와 단일
`live-controller-unit`212개가 통과했다. guard violations0이며 두 검사 모두
자기 임시 root를 제거했다. 정확 AI 경로 수용은 합성 metadata로, 기존 provenance
controller drift와 source identity/mode drift는 기존 회귀로 검사한다. 다른 서비스
경로5개는 credential metadata/content 접근 전에 거절함을 별도 회귀로 확인했다.
이 결과는 실제 AI source 파일의 키 존재·값·API 인증 수용을 증명하지 않는다.
기존 private runtime의 검토용 수정안은 정확 KEY 경로 한 줄만 변경됐고 구문을
정적으로 검사했다. 기존 실행 파일·고정 산출물은 교체하지 않았다. 실제 PG·모델·
provider·키 읽기·CF029 재시도·Git 게시·새 실행권 발행은 이번 정정에서0이다.


## frozen 사건을 보존한 후속 검사 준비

새 사용자 지시는 실제 호출이 아닌 후속 방법 준비·무키 회귀 범위다. 실제 창은
만료됐으며 기존 frozen 사건·소비된 실행권·150,000,000nanoUSD 예약은 유지한다.
기존 aggregate의 frozen 거절과 현재 source/hold에 맞지 않는 continuation을
변경하지 않는다. Controller는 130,675bytes로 기존 상한 안에 그대로 보존한다.

준비 전용 prototype과 합성 회귀를 기존 고정 단일 unit 파일에 추가했다. 실행
코드가 아니라 순수 계약 계산이며, 실제 파일/원장의 진위 확인이나 발급권은 없다.
독립 expected 9종 증거 hash, closed/frozen/소비/cleanup 상태, count 1/gen0,
HTTP unknown·usage null 및 현재 carry 150m을 대조한다. 첫 동일 질문의 요청/
projection만 고르고, 기존 모델·공식 목적지·default tier·토큰 상한·retry 0을
유지한 count 1/generation 1/HTTP 2·신규 50m의 계획만 계산한다. 계획 누적 200m/
잔여 800m은 실제 예약이나 비용이 아니다. 중간의 두 질문 100m 제안은 이후
독립 검토의 횟수 정정에 따라 채택하지 않았다.

반환값은 항상 execution_authorized=false이며 이전 실패의 재시도를 허용하지
않는다. 최초 요청을 1회 재검증하는 명시 결정과 새 시간창, 같은 선행 사건의
단일 소비 witness, 새 AI source capability·단일 실행 조립이 남아 있다.
현재 구현으로는 frozen aggregate를 재사용하거나 기존 runner를 호출할 수 없다.
private checkpoint에는 합성 계획/수용 기준만 기록하고 실제 grant/allocation/
장부·flags·키·provider·DB·CF029 거절 동작·Git은 건드리지 않는다.


기존 보호 `live-controller-unit`의 단일 파일 254개가 통과했다. 기존 212개와
신규 순수 계약 회귀 42개이며 guard violations 0, exit0, 자기 임시 root 제거를
확인했다. 보호 self/entry/controller/guard는 앞선 검사 이후 변경하지 않아
이번에는 반복하지 않았다. 예약과 사용액을 구분하고 입력 불변·다른 서비스 source
거절·실행 권한 없는 결과를 실제 live grant로 수용하지 않는 회귀를 포함한다.
합성 projection 검증을 실제 증거 진위·외부 단일 소비 authority 검증으로
표현하지 않는다. 기존 실제 실행 증거 11파일은 해시가 그대로다.


### 최종 한 질문 prototype · 새 진행 의사와 실행 미구현의 구분

이 절 앞부분의 ‘실제 호출이 아닌 준비 범위’는 최초 준비 지시 시점의 이력이다.
이후 사용자는 첫 동일 질문 하나/count 1회/generation 1회/추가 보수 예약
50,000,000nanoUSD·누적200,000,000 제안으로 진행하는 데 동의했다. 개발 측도
원문과 확인 가능한 수신 시각을 직접 대조했다. 같은 범위를 다시 승인받아야
한다는 상태가 아니며, 그 진행 의사를 검토된 실제 실행 scope·단일 소비·짧은
once-only lease에 결합하는 구현이 남은 상태다. 과거 만료창이나 소비된 실행권을
되살리지 않고 사용자 지정 기간을 임의로 만들지 않는다.

254개는 첫 질문/추가50m의 이전 prototype 검사 결과이며, 깊은 불변 반환과
history/attempt/spec/price 검사를 보완하기 전 이력이다. 보완 후 같은 보호 단일
파일에서 최종269개가 통과했다(exit0, guard violations0, 자기 임시 root 제거).
MappingProxyType 안의 primitive/tuple만 반환하며 top-level/nested 변경 거절,
입력 불변·결정론, 원 carry와 이번 batch 소속·attempt 누적2·독립 expected
namespace/proof·spec/price·두 질문/둘째 질문 대체 거절을 확인했다.

이 prototype의 독립 source 검토는 무키 범위에서 구체 차단 finding 없이 끝났다.
제공된 해시끼리의 일치가 실제 출처 진위를 증명하지 않는다는 한계를 유지한다.
실제 선행 증거·독립 witness 검증, 원자적 단일 소비, 정확 AI source의 fresh
capability와 검토된 단일 요청 실행기 결합은 미구현이다. Controller는 그대로이며
기존 grant/원장/hold·private runtime·flags와 실제 실행 증거는 변경하지 않았다.
이번 준비의 실제 key/.env 읽기·provider·DB·발급·Git·CF029 재시도는 모두0이다.

## 단일 요청 successor helper 구현 · 무키 조립

별도 단일 요청 조립 정본 v1.0 SHA256
`af1d792007538b7b41a5bce0df333e8300097ddad752acc37b8eb7f565fe3d83`의
정확6경로로 새 `backend/scripts/cf026_successor.py`와 기존 보호 선택/회귀·계약/
작업 기록을 보완했다. 기존 controller는130,675bytes와 검토된 hash 그대로다.
worker/guard·AI32·verifier/gateway/PhaseBudget·DB schema·package/lock·private
loader/entry와 실제 기록은 변경하지 않았다.

실제 frozen schema의10 JSON과 canonical 경로·pin을 검증하고, parent accounting과
child journal·coordination head/lock·runtime/source를 연결한다. 원 namespace/
bootstrap의 단일 successor identity, 독립 consume+readback, local journal의
scope/identity/fsync, 두 clock의600초/30초 제한, start fsync 이후 자원/SQL/epoch
쓰기 전 검사를 구현했다. 소유 engine에만 SQL/commit hook을 붙이고 복구한다.
기존 local epoch100m/2는 유지하며 외부50m/count1/generation1 권한을 좁게 쓴다.

초기 self3/unit283이 통과한 뒤 집중 회귀를 추가했다. 다음 회차는307통과/1실패였다.
실패는 성공용 mock ledger에 normal transition이 요구한 active=null이 빠진 fixture
오류였으며 이를 보완했다. 실제 DB나 공급자 오류로 해석하지 않는다. 이후317개가
통과했고 읽기 쉬운 줄바꿈 정리는 AST 동일성을 대조했다. 이력 로그는 보존하며
최종 소스 검사 결과와 합산하지 않는다.

단일 verify_live spy는 실제 새 helper의 phase/deferred supplier/keyword 경로를
실행하지만 fresh Principal/준비 SQL·verifier 본체는 mock이다. epoch helper의
지연 clock 후 INSERT0와 소유 SQL/commit guard도 실제 새 함수를 mock DB에 실행한
회귀다. 실제 PG·migration·ASGI·OpenAI 통과로 보고하지 않는다. 실제 authority는
기본 unavailable이며 이번 synthetic witness는 독립 실제 서비스/원자 CAS 증거가 아니다.

회계 ACK 손실 전에 확인 가능한 ledger를 local journal에 남기고, ACK 뒤 cleanup을
확인한다. ACK 불명에는 proof/preserve와 보수 예약을 유지하고 취소를 재전파한다.
원 실제 기록·원150m 예약과 세 .env를 보존했다. 이번 actual 키/.env 읽기·DB·API·
발급·flags 활성화·Git·CF029 거절 재시도는0이다.

최종 동결 후보의 보호 self3·단일 unit322가 통과했다. 최종 로그는 self-4.log와
unit-6.log이며 guard violations0, exit0, 자기 임시 root 제거를 확인했다. 최종
직전 회차는320통과/2실패였다. 신규 테스트가 phase ACK 불명에서 proof를 보존한
올바른 동작을 cleanup으로 잘못 기대했기 때문이며 단언을 바로잡았다. 이력으로
보존하고 최종322와 합산하지 않는다. 검사 실행 권한 거절이나 실제 자원 실패는
아니었다.

최종 회귀에는 frozen 실제 schema/연결·canonical 경로와 root/coordination lock
identity·첫 요청 변조·old runtime/source·두 clock·lease 갱신 거절·start fsync
지연·소유 SQL/commit/epoch guard·동시/재시작/로컬 증거 손실·phase 직렬화·
ACK 불명·늦은 cancellation·회계 보존·고정 비밀 비노출이 포함된다. 실제 새 helper를
실행한 함수 테스트와 독립 authority/DB/verifier spy는 구분한다. source는 controller
모드에서만 신규1개를 더해265개이며 다른 기존 모드의 사본 범위는 늘리지 않았다.

실제 활성화에는 그대로인 private_runtime의 AI source/신규 module loader와265-source
검토 map, 단일 scope/lease descriptor, 명시 successor private entry, 실제 독립
authority adapter/retained witness가 남아 있다. old private entry는 여전히 과거
두 질문 ceremony를 가리키며 재사용하지 않는다. 이 단계는 repo helper와 무키
회귀 완료이지 실제 발급·원자 외부 권위·ASGI/PG/provider·모델 품질 완료가 아니다.
사용자의 단일 질문 진행 의사는 확인됐고 같은 범위의 시간 승인을 반복 요청할
상태가 아니다. 실제 동작 전 최종 scope/one-shot lease/출처 결합을 검토해야 한다.
# CF026 successor 명시 재시도 추가 검증

최초 successor의 별도 실제 시도는 server once 예약 50m이 소비된 뒤 readback이 시작 기한을 넘겨 입력을 보내지 않고 timeout으로 종료됐다. 부모가 관측한 해당 시도의 key/count/generation/DB는 0이며 entry는 False로 원복됐고 source copy는 제거됐다. 빈 local journal과 원 소비 기록은 보존한다. 기존 150m과 합친 200m은 실제 청구액이 아닌 보수 예약이며, 이번 코드 수정으로 해제하지 않는다.

후속 명시 재시도는 정확 첫 질문 한 개와 추가 50m·결합 250m, count 1/generation 1/HTTP 2/자동 provider retry 0으로 한정한다. base artifact 10과 frozen 부모 검증은 유지하고, 원 timeout/원복 evidence와 manifest pin, 실제 readback의 원문 UTF-8 본문·item/turn 및 새 동의를 추가 검증한다. body hash를 JSON 재직렬화로 대체하지 않으며, namespace/bootstrap의 고정 retry ordinal 1만 허용한다. 새 source/동의/nonce/디렉터리로 슬롯을 늘리지 않는다.

이번 직접 검증은 기존 보호 self 3개, 고정 단일 unit 358개 통과·guard 위반 0·parent exit 0·임시 root 제거다. 별도 private stdlib 합성 42개도 통과했고 audit의 key-content/network/unexpected-child는 각각 0이다. helper의 실제 함수와 local lock/fsync/PTY를 실행한 것이며, 외부 authority·runner·PG/provider는 합성/DI 경계다. 실제 모델 품질·정산 성공으로 표현하지 않는다.

초기 보호 명령은 private 준비용 PATH를 넣어 caller env gate에서 exit 78로 차단됐다. guard를 변경하지 않고 문서화된 PATH 없는 clean env와 정확한 worktree .venv Python 입구로 정정했다. 첫 unit의 테스트 assertion 배치와 validator 예외 기대 오류를 수정한 뒤, raw-body/manifest 및 늦은 ACK의 250m 보존 회귀를 포함한 최종 358개가 통과했다. 실패 로그는 private checkpoint에 별도 보존하며 성공으로 합산하지 않는다.

120초 시작 제한은 wall과 monotonic을 함께 강제하며 ready 입력도 120초다. 48.045초 전달, 120초 경계와 초과, 새 자원 전 늦은 ACK, 같은 retry의 중복/변조·이전 200m 보존을 검증했다. 전체 lease 600초·provider 60초·callback 5초·cleanup 30초·예약 전 preload 30초와 기존 controller/AI32/worker/guard/dependency는 유지했다. 새 실제 입력·임시 activation delta는 다음 독립 확인 대상이며, 이번 구현/무키 검사에서 실제 예약·키·DB·API·Git 실행은 0이다.

## 실제 retry1 결과와 별도 무키 deadline 보완

부모가 수행한 실제 retry1은 입력 전달 뒤 SUCCESSOR_CLOSED로 종료됐다. 보존된
정제 journal에는 count/generation 예약 ACK, supplier의 source_read_returned,
final accounting과 closed/cleanup_confirmed가 있다. meaning unavailable·정산
unconfirmed·usage unknown·estimated null이며, 250m은 청구액이 아닌 보수 예약이다.
기존 실행물·once·원장·입력·manifest와 이 예약을 그대로 보존했다.

generation 예약은 gateway가 count HTTP 200과 응답 검증을 통과한 뒤에만 발생한다는
코드 경로 근거가 있다. 생성 HTTP 송신/완료·모델 출력·실제 청구는 기존 증거로
확정할 수 없다. 당시 CONTROLLER_FAILED는 helper의
FIRST_SETTLEMENT_UNCONFIRMED를 일반화할 수 있는 오류 표시였으며 공급자 오류를
직접 증명하지 않는다. 실제 중단 원인의 시간·예외 단계는 소급 확정하지 않는다.

기존에는 provider와 meaning 전체가 각각 5초이고 내부 client 8초,
route/preparation 15초·verifier 60초였다. 중첩 timeout/cancellation이 정산을
끊을 수 있는 경로를 별도 무키 수정으로 보완했다. 새 spec은 provider 55초·
verifier 60초이며 양쪽 mirror SHA는
`c3cb325b4b4e92cf72b1ff62714dec6e12f8637220dcaa0b2d9443644b397251`이다.
policy2 외곽은 60/65/70/75초로 정렬하고 가장 이른 absolute deadline 안에서
송신과 최대 5초 정산 tail을 나눈다. policy1·body/auth·모델/가격/횟수는 보존한다.

정산은 await 전에 latch하여 성공·실패 경로 합계 최대 1회다. ACK 손실·빠른 DB
예외·정산 timeout에서 finish 1회와 HTTP 추가 요청 0을 확인했다. 외부 취소 시
SQL 재정산 없이 cancellation을 전파하고 hold/unknown을 보존한다. 안전 진단은
별도 private 필드의 고정 stage/elapsed와 정산 불명 flag만 사용한다. verifier가
반환하지 못하는 바깥 timeout/cancel에서는 이 진단도 없을 수 있다.

최종 직접 검사는 보호 meaning-assembly self 3개/unit 77개,
live-controller self 3개/unit 364개가 모두 통과했다. 두 unit은 각각 정확 단일
파일을 수집했고 guard violations 0·parent exit 0·자기 임시 root 제거를 확인했다.
새 private 사본의 합성 검사 44개도 통과했고 key-content/network/unexpected-child
audit는 각각 0, release flag는 False다. private 사본은 소비된 실행 파일을
덮어쓰지 않는다. 최종 코드의 독립 읽기 검토에서 구체적 blocker는 없었고 이후
테스트의 DB mock에 flush 하나를 보완했다.

PreparationService.post→실제 AIClient→인증 ASGI→meaning 경로에서 기존 15초에
해당하는 scaled 지연보다 긴 응답을 검증했다. DB/종목 resolver와 후보 gateway는
합성이며 실제 PG/provider 수용은 아니다. 실제 gateway/PhaseBudget/helper 함수
회귀, mock SQL·callback·scaled clock의 경계를 구분한다. 신규 회귀 첫 실행은
mock flush 누락으로 76통과/1실패였고 보완 후 77개가 통과했다. 이전 pin/기한
수정 중 실패 로그도 보존하며 최종 통과 수와 합산하지 않는다.

이번 수정·회귀에서 추가 actual key/.env 읽기·예약·발급·DB·API·flags 활성화·
Git 작업은 0이다. 새 semantic spec의 실제 승인/epoch/과거 lineage 호환·추가
실행·모델 품질은 미검증이며 이 작업은 ordinal 2나 기존 실행권 재사용을 열지 않는다.

## PR37 최신 develop 통합 pin 정합성

최초 원격 CI는 최신 develop과의 합성 merge에서 첫 보호 self의 source pin 검사로
중단됐다. 공통 AIClient에는 develop의 Technical legacy fail-closed/typed boundary와
이번 Supervisor policy2 timeout 변경이 함께 들어갔지만 CF021 고정 pin은 이전
Technical 전용 client hash였다. 보호를 완화하거나 새 hash로 일괄 치환하지 않고
양쪽 함수 diff를 검토한 뒤 최신 develop을 정상 merge하고 이 한 pin만 갱신했다.
다른 소스 허용 집합·고정 mode·worker/guard·dependency 검사는 그대로다.

통합 source의 직접 보호 검사는 quality self 2개, Technical boundary self 3개와
unit 175개, Technical read self 3개와 unit 47개, meaning unit 72개,
assembly self 3개와 unit 77개, controller self 3개와 unit 364개가 통과했다.
unit은 각 고정 단일 파일이고 guard violations 0·parent exit 0·자기 임시 root
제거를 확인했다. 공통 AIClient의 Supervisor 외 함수는 develop과 동일하며
Supervisor policy2 70초/policy1 8초 차이만 남는다. 통합 client와 한 pin 수정은
독립 읽기 검토에서도 확인됐다. 원격 최신 head CI 결과는 이 로컬 검사와 구분한다.

추가 실제 API/key/DB·flags 활성화·발급/예약은 없고 기존 250m 보수 예약 및
consumed 실행 증거는 불변이다. PR은 Draft로 유지하고 병합하지 않는다.

### CF037 고정 후속1회 준비

최신 develop의 timeout·정산·진단 변경을 재사용하며, 별도 작업공간에서 fixed ordinal2의 helper와 private 사본을 준비했다. 원150m+timeout50m+closed retry1 unknown50m=250m을 이월하고 추가50m·누적300m을 제안한다. 기존 실행물·원본 원장·승인·once와 실제 불확정 결과를 변경하지 않는다. 새 발급·예약·실제 키·DB·count/generation·설정 활성화는 아직 없다.

현재 무키 검증은 실제 helper/phase 함수·local file lock/fsync와 callback simulation이다. 최초 unit 회차의13개 실패는 spy를 함수로 대체한 뒤 call_count를 참조한 harness 오류와 missing-file의 OSError 기대 누락이었다. 두 harness를 보완한 동일 보호 unit은391개·guard0으로 통과했고 private44개도 통과했다. 이 결과를 실제 DB나 모델 수용으로 표현하지 않는다. 독립 검토에서 발견한 code-root0755/private-root0700 구분을 좁게 보완했으므로 해당 최종 변경의 검증 결과는 아래에 따로 기록한다.

최종 보호 self3/unit397·guard0, private 합성44개가 통과했다. 실제 기존10-artifact·closed retry1 journal/phases/result·정확 서버 원문 readback을 대조하고 최신 source281개 copy/import·live Scope.check까지 무키로 통과했다. source281은 controller 선택의 실제 집합이며 assembly280과 helper1을 구분한다. 새 실행용 private 사본은 비활성이며 실제 공급자 호출·새 예약은 아직 없다. 기존 gateway 반환 뒤의 grounded model-assisted assessment와 fresh ledger의 input/output/total/cached token 정수·고정 모델만 cleanup 전 accounting에 남기고 raw 응답·비밀은 보존하지 않는다. 누락 usage는0으로 만들지 않으며 이 준비 결과는 실제 모델 품질·청구 수용이 아니다. 독립 최종 delta 검토에 남은 blocker는 없고 guard/AI32/controller·과거 실행물은 불변이다.

### CF037 단일 실제 실행 결과와 오류 표시 보완

승인된 한 질문에서 무료 count 응답 검증과 generation 응답·usage·settlement ACK를 관찰했다. 고정 모델의 input804/output499/total1303/cached0, 원장 estimated_nano2,848,500(USD0.0028485)을 보존했다. 이는 토큰 단가 기반 추정이며 실제 청구서 확인이 아니다. 새50m이 소비돼 기존250m을 포함한 보수 예약300m을 유지한다. 정산은 observed·settlement_uncertain=false, 의미는 rejected·quality assessment=null이다. 따라서 이번 생성 결과/정산을 unknown으로 표현하지 않지만 의미 품질 수용은 미완료다.

기존 소스는 정산 미확정과 의미 미수용을 같은 FIRST_SETTLEMENT_UNCONFIRMED로 표시했다. 이를 정산이 observed인 rejected에는 MEANING_REJECTED, 다른 미보완 상태에는 MEANING_NOT_SUPPLEMENTED로 분리했다. 정산이 불명인 기존 실패 gate와 추가 송신 차단·회계/정리 순서는 그대로다. 신규 오류 라벨은 정확 helper 타입·고정 코드만 받으며 예외 문자열은 남기지 않는다. 보호 단일 unit401개·guard0으로 보완 회귀를 통과했다.

보존된 typed-return/grounded assessment 경로로 의미 validator 거절까지 확인할 수 있으나, 후보 원문과 세부 거절 조건은 남아 있지 않아 어느 span/부정/기간 검증이 실패했는지는 확정할 수 없다. 이를 추측하거나 성공으로 표시하지 않는다. 실제 journal closed·local accounting ACK·cleanup_confirmed와 임시 설정 False 원복을 확인했고, 실제 완료 후에는 새 키·DB·provider·예약 동작을 하지 않았다. 환경 전환으로 실제 발급 전 중단된 첫 준비 회차와, 새 동일 ordinal2의 실제 한 번을 구분해 비공개 증거로 보존했다. 반복 record·provider 재시도는 없으며 과거 입력·실행 manifest·once는 수정하지 않았다.

### CF037 B5 진단 보완과 ordinal3 준비

기존 실제 validator의 순수 판정 경로에서 실패한 고정 위치·필드/index·이유와 질문에 대조한 최소 근거를 보존하도록 보완했다. schema 거절과 분류 불가능한 grounding 실패를 구분하며, 승인된 질문에 없는 임의 값·원문 응답·예외/traceback·비밀은 투영하지 않는다. validator와 prompt/schema·gateway/verifier·AI32·controller·worker/guard는 변경하지 않았다.

고정 ordinal3은 원150m·timeout50m·unknown50m에 observed ordinal2의50m을 더한300m을 이월하고 새50m·누적350m을 제안한다. ordinal2의 실제 원문/readback·입력·journal/phases·usage/정산 ACK·meaning rejected·closed/cleanup/False와 실행 당시 source/runtime을 독립 pin으로 대조한다. 기존 retry2의250m 검증과 원본 소비 기록은 보존한다. 첫 질문 count1/generation1/HTTP2·자동 retry0과120초 시작/입력·600초 lease를 유지하고 실제 종료 상한은 오늘21:00 UTC다.

최종 보호 self3·단일 unit432개가 통과했고 guard 위반0·parent exit0·자기 임시 root 제거를 확인했다. private 합성45개는 키 내용 읽기/네트워크·DB 연결/예상 밖 subprocess0·비활성 설정·실제 예약0으로 통과했다. 실제 source281개 copy/import와 원본10-artifact 및 폐쇄된 ordinal2 증거 대조·Scope.check도 무키로 통과하고 자기 사본을 제거했다. 앞선 unit425/private44는 중간 source 결과이며 최종 수와 합산하지 않는다. 최초 입력 조립은 현재 helper와 과거 manifest를 비교해 실패했고, 현재 파일을 과거 실행물로 취급하지 않도록 보존된 실행 당시 helper를 대조한 뒤 통과했다. 실패 로그도 보존한다.

현재 ordinal3 private 사본은 False이며 신규 발급·예약·키 읽기·DB·count/generation·설정 활성화는 없다. 기존300m은 보수 예약이며 실제 청구액이 아니다. 입력·진단 검증을 실제 모델 품질 통과로 표현하지 않는다. 실제 한 번은 최종 입력 대조 후 같은 invocation의 단일 durable record·실제 readback·stdin 전달로 조율하며, 불명/거절 뒤 추가 송신하지 않는다.

### B5 실제 결과와 정리

앞 절의 미실행 상태는 준비 완료 시점의 이력이다. 최초 인계 명령은 clean env의 필수 PATH를 누락해 runtime 환경 검사에서 ready 전에 종료됐다. source copy·journal·발급·예약·키·DB·API는 없었다. 기존 허용 PATH를 명시한 무키 preflight 통과 후 코드·입력·private 해시를 바꾸지 않고 실제 최초 ordinal3 한 번을 수행했다. 두 번째 실행권이나 provider 자동 재시도는 없었다.

실제 count1·generation1의 응답과 usage input804/output285/total1089/cached0, estimated_nano1,885,500(USD0.0018855), settlement observed/ACK·settlement_uncertain=false를 관찰했다. 누적350m은 보수 예약이며 실제 청구서 금액이 아니다. 의미 결과는 MEANING_REJECTED로 종료돼 모델 의미 품질 수용은 실패했다.

거절은 views 항목0의 기존 validate 판정에서 EVIDENCE_SOURCE_SPAN_TEXT_MISMATCH로 확인됐다. 제안된 overview 근거는 원문 start0/end15를 가리켰지만 supplied_text는 ‘현대건설 외국인’이어서 실제 원문 구간 ‘현대건설 외국인 말고 3주 ’와 일치하지 않았다. 근거 불일치를 fail-closed로 거절한 결과이며 overview나 조건 해석을 성공으로 채택하지 않는다. 이 기록을 후보가 남지 않은 이전 ordinal2의 원인이라고 소급 단정하지 않는다.

최종 journal closed·6개 phase·delegated local accounting ACK·cleanup_confirmed, entry False/원래 hash·PID 부재·자기 source copy 부재를 확인했다. 실제 원문/readback·입력/source/실행 hash·usage/진단·정리 증거는 별도 비공개 결과로 보존하고 공개 Git에 넣지 않는다. 추가 외부 호출·발급·ordinal4는 하지 않았다. 이번 결과는 production Supervisor→Flow 전체 또는 Technical 엔진 인수가 아니다.

## CF037 B6 · CF038 이후의 한 질문 재검증 준비

기준 develop `527a73bfd3f3f886cd2b37021d510d1051177f05`의 별도 브랜치에서 준비한다.
기존 소비된 ordinal3은 응답·usage804/285/1089·관측 추정USD0.0018855·정산ACK 이후
의미 거절로 종료됐고, 새 검증의 성공 근거로 소급하지 않는다. 기존350m과 당시 source,
입력·원장·private False·cleanup 증거는 그대로다.

이번은 ordinal4 한 번만 허용하는 후속 분기다. 계획된 추가50m/누적400m은 기존 총한도 안의
보수 예약이며 아직 실제 배정 여부와 구분한다. 운영 정책 숫자나 새 budget root로 복사하지 않는다.
기존 helper/단일 unit/보호 entry와 새 private3 사본만 재사용한다. check_safe의 선택·AI32와
C controller/worker/guard/package/lock은 변경하지 않는다.

CF038 전후 semantic 차이는 정확 prompt SHA 하나다. 과거 prompt/spec/요청 hash를 당시
고정 source로 재구성해 검증하고, 현재 요청은 현재 rendered request와 전체 count projection에
대조한다. 과거 equality를 삭제하거나 새 prompt를 옛 실행에 repin하지 않는다.
현재 alignment의 실제 거절 위치를 유한 이유 코드로 추가했으며 미상은 그대로 미상이다.
validator/prompt/schema를 진단을 위해 다시 바꾸지 않는다.

집중 검증은 원본 history 불변, 400m·canonical once, 중복/ACK 손실·취소·source/spec drift,
현재 위치 정합화·overview 거절, 비밀 없는 투영과 private 비활성·정리를 검사한다.
기존 전체 의미/Frontend/CF044 PG 회귀는 이번 준비 때문에 반복하지 않는다.
실제 호출은 독립 소스/정확 입력 대조와 부모의 durable 일회 write/readback·같은 stdio 전달 뒤
한 번만 진행한다. 실제 결과·관측 usage/추정·정산·400m 또는 미발급·원복/cleanup을 분리한다.
의미 거절이면 새 ordinal5나 추가 송신을 하지 않으며 production/Flow 전체 인수로 확대하지 않는다.

B6 준비의 최종 보호 self4·단일 unit465·private 합성45가 통과했고 guard 위반0,
부모 exit0·자기 사본 제거 및 두 독립 검토를 확인했다. 실제292파일 copy/import·Scope.check도
무키로 통과했다. 현재 ordinal4는 발급·로컬 claim·예약·키 내용 읽기·DB/API·활성화0이다.
실제 한 번의 외부 실행은 별도의 구체 실행 승인 확인이 남아 보류하며, 준비 검사를
실모델 의미 수용으로 보고하지 않는다. 기존350m과 비공개 실제 기록/False는 그대로다.
