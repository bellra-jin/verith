# CF043 · Supervisor AI 요청 전 준비와 세션 재검증

기준 develop `c23e925a4f2441bf419eddafe594d752a00f8252`에서 별도 branch로 분리했다.
정확5파일로 [공통 계약](../contracts/supervisor-core-v1.md)의 전송 직전 검사만 실제 제품에 연결했다.

## 제품 변경

기존 post는 admission commit ACK 뒤 start로, resolver commit 뒤 continue로 바로 전송했다. 첫 await 전 strict
canonical request/draft/spec와 실제 immutable Principal을 복사하고, 서버 id/attempt/owner/optional epoch·TTL·
root/parent/depth 및 ancestor primitive tuple을 commit 전에 고정한다. mutable ORM/새 AI 응답을 기대값으로 쓰지 않는다.
body/중첩 답변과 wire payload도 분리해 외부 참조 mutation이 다음 phase를 바꾸지 않게 한다. frozen context는 요청
메모리에만 있고 repr/log/새 저장으로 원문·Principal/token을 노출하지 않는다.

실제 post→build→exchange의 각 start/continue에 fresh Principal SQL(lock=True), owner lineage/closure/clock과
pending identity·현재 spec/draft/epoch·고정 ancestor 계획 검사를 연결했다. child는 NULL 원문을 보존하고 새 pending
leaf를 assembled하지 않는다. 검사 commit ACK 뒤 DB lock 없이 HTTP로 넘어간다. clock 직전 monotonic+DB 최소 TTL의
보수적 절대 기한은 guard ACK 뒤와 payload 재검증 뒤 마지막 send 직전에 다시 검사한다. CF042 절대 기한을 늘리지 않는다.

폐기/만료 closure는 내부 control flow로 build를 중단해 같은 외곽 기한 안에서 기존 get/view/redaction으로 돌아간다.
start 중 삭제가 완료되면 continue0·200/deleted/plan=None이며, 이미 보낸 start를0으로 바꾸지 않는다.
기존 key replay/GET/adopt/confirm·TTL/selection 규칙·winner ACK·취소/rollback·None75는 그대로다.

## 직접 보호 검사

기존 clean env·검증 Backend Python의 -I -S -B 및 고정 meaning-self/meaning-unit/meaning-assembly-unit만 사용했다.
최종 self4·meaning unit189·직접 영향 assembly unit103개가 통과했고 guard0·parent exit0·각 소유 root 제거를 확인했다.
AI32/origin·caller/worker/guard·패키지·CI는 변경하지 않았다. PG/Frontend나 완료된 무관 전체 suite는 로컬에서 반복하지 않았다.

실제 post/build/exchange/guard·Principal SQL 생성과 명시 fake session/row·resolver·기존 AI ASGI transport를 조합했다.
정상 root의 claim ACK→guard ACK→start, resolver ACK→guard ACK→continue 순서와 HTTP의 transaction 종료를 확인했다.
실제 repo.lineage SQL의 owner/populate_existing/for_update 조건은 명시 row return으로 검사했고 실제 PG 잠금 증거는 아니다.

claim/guard ACK 불명과 admission ACK 뒤/resolve ACK 뒤 revoke·owner/attempt/key/request/draft/spec/epoch/root/depth
drift는 다음 phase0이다. 같은 key replay/GET은 응답을 보존하고 AI/epoch/예약 추가0이다. nested body mutation,
정상 candidate child·NULL 원문·임의 선택/ancestor 변조와 기존 ancestor의 다른 spec/epoch 거절도 확인했다.

clock/commit/payload 처리 중 TTL 만료·더 짧은 절대 기한과 공개 ASGI guard 중 CancelledError·rollback/session finally를
관측했다. 실제 AccessBoundary/CoreRoute/dependency/PreparationService를 통과하는 late_delete는200/deleted/plan=None·
start1/continue0이다. CF024 real-post fixture는 nullable identity 필드와 Principal SQL 반환만 보완해 새 guard를 실제 통과시켰고,
guard 자체를 mock하지 않았다. 이전 CF042 build mock 회귀는 이 새 guard 증거와 분리한다.

초기182개 통과 뒤 공개 ASGI fixture 확장에서186개 통과/1개 실패가 있었다. 실제 R.service가 기본 StockResolverService를
구성해 synthetic resolver가 전달되지 않은503이었다. 실제 route/dependency/guard와 실제 SupervisorService는 유지하고
resolver IO만 명시 DI로 보완한 뒤187개가 통과했다. ancestor의 현재 spec/epoch 독립 대조2개를 더한 최종189개도 통과했다.
초기/실패/최종 로그를 별도 보존했으며 기대값·제품 guard·보호를 완화하거나 skip하지 않았다.

## 한계와 인계

실제 PG locking/concurrency·Google/모델/provider·키/env/DB·다운로드/설치·flag·새 예약은 없다. 기본 gateway=None/
epoch_id=None, CF023 test 예산 미활성, 기존350m과 실제 소비/False 기록은 불변이다. 운영 epoch/정책 공급자와
인증된 reserve/settlement를 AI로 잇는 phase 서비스는 여전히 없고 이번 guard는 비용/실행권을 발급하지 않는다.

검사 commit 다음 순간의 철회/삭제까지 원자적으로 막거나 실제 provider 중단/비용0을 보장하지 않는다.
이번 완료는 현재 preparation의 실제 전송 직전 관측이며 production gateway 조립/실모델·Flow 전체 인수는 아니다.
독립 최종 검토·Ready PR·exact-head CI와 정상 merge 결과는 해당 단계의 증거로 별도 기록한다.
