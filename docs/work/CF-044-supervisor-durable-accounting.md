# CF044 · Supervisor 독립 예약과 정산 저장

기준 develop `d01341b0b01bdc07269339a0ab3073498d5d59e9`에서 분리했다.
이 변경은 실제 SQL의 내부 회계 구성요소이며 운영 Gateway 연결이나 실행권 발급이 아니다.

## 구현

- 독립 account/reservation 모델과 additive `c44001a7e0001` migration을 추가했다.
  기존 preparation·test epoch·Flow 회계 표는 변경하지 않는다.
- operation/owner/canonical scope는 UNIQUE다. canonical JSONB scope의 별도 UNIQUE
  인덱스로 공백 표현만 바꾼 중복도 차단한다. 기간·정책·한도가 다른 같은 scope는 conflict다.
- 계정 생성은 명시 입력만 받는다. 누락 계정 자동 생성·만료/blocked 초기화는 없다.
  신규 생성/예약은 현재 semantic/model/tier/price/caps와 정확히 대조하고,
  이전 예약 정산은 저장된 불변 snapshot의 내부 정합성을 검증해 계산한다.
- Principal/session과 owner-bound preparation/attempt/request/draft/spec/projection을
  SQL로 대조하고 account→reservation 순서로 잠근다. 예약 INSERT와 누적액·횟수 증가는
  같은 transaction이며 commit ACK 뒤에만 receipt를 돌려준다.
- receipt는 회계 결과다. 송신 권위나 fresh 실행 인증을 대신하지 않는다.
- 정산은 strict 정수 usage와 고정 binding을 검증해 nanoUSD 추정액을 계산한다.
  observed 뒤에도 예약액 자동 환급은 없다. unknown/anomalous는 hold와 account block을 유지한다.
  동일 terminal receipt만 replay하며 다른 late evidence는 conflict다.
- 검증된 observed의 제한된 usage/enum/hash만 저장한다. 비허용·잘못된 관측은
  고정 이유와 digest만 남기며 자유 문자열·provider body를 저장하지 않는다.
- ACK 불명은 caller가 이미 알고 있는 account/preparation/attempt/Binding으로
  no-autoflush SELECT reconcile만 한다. 새 예약이나 송신권을 만들지 않는다.
  취소는 rollback 실패가 있어도 전파하고, rollback 중 새로 온 취소도 삼키지 않는다.
- migration은 새 두 표를 ACCESS EXCLUSIVE로 잠근 뒤 비어 있을 때만 downgrade한다.
  필수 JSON binding CHECK는 NULL도 거절하도록 `IS TRUE`로 닫는다.

## 실행한 검증

- 기존 보호 `meaning-self`: **5 passed**.
- 기존 보호 단일 `meaning-unit`: **212 passed**, guard violations **0**.
  정수·정책 일관성·이전 snapshot 정산·commit/rollback 양방향 취소·읽기 복구와
  source/고정 PG flag의 보호 회귀를 포함한다. 부모 exit0·자기 임시 root 제거를 확인했다.
- 새 고정 `--verify-supervisor-accounting-db`에서 기존 소유 자원 절차를 재사용했다.
  검증된 source-copy·AI32 고정 origin·제한 role·proof/receipt·동일 연결 migration과
  사전/사후 source·dependency 확인을 유지했다. 패키지나 guard를 변경하지 않았다.
- 최종 소유 PG 회차 **6그룹 passed / parent exit0**:
  1. 단일 migration head, 기존 행 보존, 빈 새 표 downgrade/reupgrade.
  2. 두 실제 SQL session의 동일 예약 승자1/동일 결과, scope 복제와 identity drift 거절.
     실제 composite FK SQLSTATE23503과 missing/null binding CHECK23514도 확인했다.
     실제 만료·삭제된 준비는 예약0이다.
  3. 정수 추정액·terminal replay/conflict·정산 후 hold, commit 뒤 ACK 손실의 읽기 복구.
     dirty session의 pending INSERT는 reconcile에서 flush되지 않았다.
     실제 세션 만료 뒤에도 고정 held 예약 정산을 기록했다.
  4. commit 전 실패에서 account/reservation 원자 rollback, 정확 한도·횟수 경계와 추가 예약0.
  5. bool/음수/float/overflow·잘못된 model/extra key의 anomalous·hold·block 및 비노출 receipt.
  6. populated downgrade 거절과 기존 회계 행 보존.
- ACK 손실은 **실제 commit 후의 wrapper simulation**이다.
  취소와 rollback 중 취소는 **mock 단위 회귀**로 검사했다. 실제 commit 후 취소나
  네트워크 ACK 소실·운영 장애 복구를 재현했다는 뜻은 아니다.
- 최종 소유 CID 제거·receipt 일치·sourcecopy 부재와 source/dependency 사후 검사가 통과했다.
  실제 provider/count/generation·키/.env 접근·운영 설정 활성화는 **0**이다.

## 중간 기록과 한계

초기 201/209/210 unit은 당시 source의 통과 기록이다. 최종 212와 합산하지 않는다.
초기 PG1–3은 각각 당시 구현/검사 범위의 통과다. 이후 인수 범위를 보완했다.
PG4/5는 저장된 preparation.expires_at을 변경하려던 fixture가 기존 immutable trigger에
거절돼 실패했다. 이를 제품 오류나 최종 통과로 바꾸지 않고 실패 자료와 cleanup을 보존했다.
만료 fixture를 처음 INSERT부터 유효한 과거 created/expires 쌍으로 만들어 PG6에서 통과했다.

운영 정책 발급·epoch 선택·Backend↔AI phase 승인/정산 transport·요청별 Gateway·실제 모델/Flow
전체 인수는 미완료다. 이번 예약 receipt는 그 권위를 만들지 않는다.
기존 실제 consumed 보수 예약 $0.35와 실행 기록은 그대로이며 청구확정액으로 표현하지 않는다.
운영 DB migration은 실행하지 않았다. 실제 Google/UI/provider 검증도 수행하지 않았다.

독립 최종 검토와 정확 head 원격 CI 뒤 사용자 승인 기한 안에서만 정상 Ready PR/merge를 진행한다.
게시·CI·merge의 정확 SHA와 실행 결과는 별도 완료 인계에 기록한다.
