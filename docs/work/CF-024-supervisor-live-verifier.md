# CF-024 Supervisor private 검증 조립

정본 v1.1 SHA256 `b7763ed7585f44751ccaeeb30b06c9833fb970f56a34a7776b923a7c877336ed`, 기준 develop `81a5382a1063112793a87cba8c1060cc0e71101d`, branch `feat/supervisor-live-verifier`, 정확10파일/기존 AI32 입력 범위다. 선행 CF023 의미72·Frontend93·PG10+3을 이번 직접 실행으로 집계하지 않는다.

## 구현과 책임

- private verifier는 실제 Principal·owner/준비/attempt/CF023 epoch를 PreparationService→AIClient→인증된 ASGI router→OpenAIMeaningGateway→기존 durable budget으로 연결한다. 별도 성공용 후보 반환 경로가 아니다. production router/default gateway·Backend 준비 서비스·budget SQL·DB schema·Frontend는 변경하지 않는다.
- synthetic mode는 내부 고정 MockTransport/합성 key만 사용하고 외부 supplier/authority/agreement/transport 주입은 거절한다. verifier_epoch의 INSERT는 새 일회용 합성 DB 초기화 한 곳에만 둔다. CF024라는 새 epoch를 만들거나 CF023 예산을 재설정하지 않는다.
- live mode는 외부에서 확인한 원본 owned proof/CreationReceipt object identity와 명시 epoch UUID/생성시각/상태 결합을 확인한다. 동일 proof의 ownership/preflight/attested connection과 SELECT로 기존 epoch만 검사하며 누락/교체/불명 시 fallback하지 않는다. live 초기 경로에는 INSERT/upsert/helper 초기화가 없다.
- live의 실제 실행 전제는 외부 조율이 감사한 action-time authority다. repo가 bool/hash/합성 fixture를 실제 승인으로 발급하지 않는다. authority scope에 고정 Principal/draft/spec/request/projection/agreement뿐 아니라 immutable DeferredKeySource와 정확 source capability identity를 포함한다. 키 값을 읽지 않고 supplier 교체를 거절한다. 실제 key loader나 환경 탐색은 추가하지 않았다.
- 각 count/generation 승인 직전 같은 proof의 fresh session에서 실제 Principal과 준비 owner/key/draft/spec/attempt/epoch·만료/redaction을 대조한 뒤 같은 session scope로 기존 DurableMeaningBudget을 호출한다. DB transaction/잠금과 commit ACK가 끝난 뒤 HTTP를 기다린다. DB 자격을 HTTP/AI 요청 body에 싣지 않는다.
- count 예약 commit ACK 뒤에만 지연 supplier를 attempt당 최대1회 호출하고 해당 count/generation에만 재사용한다. 종료 시 gateway instance의 key/supplier 참조를 제거하며 로그/결과/background task에 키를 남기지 않는다. 이는 참조 수명 제한이며 Python 문자열의 완전한 메모리 소거 보장이 아니다. 기존 eager api_key 합성 unit 경로는 호환한다.
- provider5초·verifier60초·승인 만료 중 가장 이른 절대 deadline을 공급·송신·정산·실패 정리에 유지한다. ACK 뒤 줄어든 deadline은 실제 송신 전에 즉시 다시 검사한다. 정산 뒤에도 기한을 확인하고 취소를 전파한다. 제한 시간 밖 정리나 detached task를 시작하지 않는다. block ACK 미확인은 unknown으로 남기며 성공으로 보고하지 않는다.
- 동일 owned Docker driver의 검증은 직렬화한다. 기존 driver의 per-call timeout만 남은 시간으로 줄였다가 finally 복원한다. 공유 driver의 여러 proof가 서로의 deadline wrapper를 덮어쓰지 않게 하며 기존 ownership/OS/FS/network/role 조건을 완화하지 않는다.

## 직접 검증

| 선택 | 결과 | 로그 이름 |
|---|---|---|
| 보호 `meaning-assembly-self` | 3통과, exit0 | `backend-self-3.log` |
| 보호 `meaning-assembly-unit` | 단일 신규 파일61통과, guard 위반0, exit0 | `backend-unit-3.log` |
| assembly 전용 새 소유 PG | 4그룹, 동일 epoch 최대2예약, 금지접근0, exit0 | `pg-2.log` |

Backend는 새 worktree의 검증된 절대 Python·clean env·`-I -S -B`와 기존 `scripts/check_safe.py`의 고정 선택을 사용했다. PG는 source-copy에서 기존 `cf002_interactive_login.py --verify-supervisor-meaning-assembly-db`의 동일 receipt/preflight/제한 role/attested connection·고정 로컬 image와 현재 migration을 사용했다. 기존16개 원격 보호 단계는 그대로 두고 assembly self/unit2단계를 추가했다. 실제 원격 새 head 실행은 게시 이후 확인한다.

단위 증거는 callback/session simulation과 직접 pure 경계 검사다. 누락/가짜/만료 approval·계수 근거, supplier 교체, live 기존 epoch SELECT 거절, 원본 proof/receipt 교체, 틀린 owner/attempt/epoch/draft/spec·삭제/만료, count 뒤 Principal/준비/승인 변경, count/generation 예약 전·후 ACK불명, generation ACK 뒤 만료 send0, supplier 실패/잘못된 값·취소, usage/model/크기/형식/timeout, 정산 ACK불명·지연/취소, driver 공유·취소 복원을 검사했다. in-memory callback 결과를 실제 PostgreSQL commit 증거로 확대하지 않는다.

### 동일 PG epoch의 실제 조립 순서

1. 실제 테스트 session Principal과 준비 claim ACK 확인 → count 예약 ACK → 합성 supplier1회 → 모의 count → generation 예약 ACK → 모의 generation → 실제 durable 정산 ACK → 고정 준비 저장/본인 재조회가 순서대로 통과했다. state ready, meaning supplemented였다.
2. 같은 prepare key replay는 기존 준비를 읽었고 supplier/모의 count/generation·새 예약0이었다.
3. 마지막 새 준비는 같은 epoch의 두 번째 예약만 사용했다. usage 누락 응답에서 unknown hold와 block ACK를 확인했다.
4. 그 뒤 기존 key replay를 통한 verifier 재진입과 새 key/restart 모두 추가 supplier/송신 전에 닫혔다. 동일 epoch의 count2/generation2·예약2·100,000,000 nanoUSD 보수 예약·observed1/unknown1을 그대로 확인했다. reset/새 epoch/대체 DB로 이어가지 않았다.

관측된 합성 usage100 input/10 output의 고정 단가 계산120,000 nanoUSD는 **합성 정산 검사값**이며 실제 사용액/승인 또는 청구서 금액이 아니다. 외부 provider 요청은0이며 모의 요청만 count2/generation2였다. 다른 ACK 손실·Principal/승인 만료·취소 조합은 위 단위 callback simulation으로 분리했다. 실제 DB epoch를 재생성해 모든 실패 조합을 한 예산의 DB 검증으로 집계하지 않았다.

PG의 full ownership 정리·정확 CID 부재와 source-copy root 제거를 확인했다. self/unit도 소유 임시 root를 제거했다. 기존 DB/volume/컨테이너·개인 profile·다른 프로젝트를 채택하거나 정리하지 않았다. 최종 gateway/checker 제품 bytes는 성공한 PG source-copy manifest와 일치하며 이후 추가 변경은 단위 회귀와 결과 문서뿐이다.

## 준비 이력·검토

- self/unit은49→53→61로 필요한 조립 실패 회귀를 보강하며 모두 통과했다. 최종 수는61이며 이전 실행을 합산하지 않는다.
- 독립 정적 검토의 generation ACK 뒤 deadline 재검사, supplier/source capability binding, 공유 driver 직렬화/복원 지적을 보완했다. source 검토와 실제 실행 결과를 구분한다.
- 첫 PG 준비는 private source-copy controller가 기존 pin 상수 `CF023_INPUTS`를 `CF024_INPUTS`로 잘못 참조해 DB 생성 전에 중단됐다. 임시 source root는 제거됐으며 DB/epoch 생성0이었다. 상수명만 바로잡은 동일 보호 경로의 다음 실행이 위4그룹을 통과했다. 이를 OS/접근 거절이나 불명 DB 생성으로 기록하지 않는다.

## 미실행과 한계

실제 OpenAI key 읽기/두 endpoint 전송 action-time 승인과 count 요금·전체 입력 계수의 감사 가능한 근거는 pending이다. 합성 agreement/hash·내부 authority는 실제 승인·공식 fee 증거로 승격하지 않는다. 다른 모델로 바꾸거나 count 비용0을 가정하지 않았다. 기본 verify_live는 미충족 입력에서 계속 닫히며, 신뢰된 private 호출이 전제를 공급할 때만 같은 조립으로 이어진다. 이번에는 live mode·provider·실제 모델 품질을 실행하지 않았다.

실제 브라우저 인수·운영 활성화·Google/KIS/Flow 실행·보고서 게시·Technical/재무·News 신규 실행/수집·Frontend/기존 의미/PG 전체 suite·새 설치는 하지 않았다. 구현 및 무키 합성 조립 통과는 실제 모델·전체 제품/운영 인수 완료와 다르다. 최신 head 원격 CI/일반 PR/병합은 조율 측이 담당하며 개발 측 Git 쓰기는0이다. 최종 source/log SHA·명령·NUL 목록·공개 PR 초안은 비공개 checkpoint에 보존한다.
