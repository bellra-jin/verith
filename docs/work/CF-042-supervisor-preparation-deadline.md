# CF042 · Supervisor 준비 POST의 Backend 기한 정합성

기준 develop `5795a1a395213fc31153e3e33c82186b3953d880`에서 별도 branch로 분리했다.
정확8파일로 [공통 계약](../contracts/supervisor-core-v1.md)의 준비 POST 기한만 수정했다.

## 원인과 제품 변경

기존 AccessBoundary는 preparations POST에 시작+15초의 core_deadline을 기록하고 CoreRoute가 그대로 사용했다.
따라서 내부 PreparationService75초·AIClient70초보다 공개 Backend가 먼저 취소됐다. 기존 private 직접 service
ASGI 검증은 이 public middleware/route 경로의 증거가 아니었다.

exact preparations POST만 최초 middleware 시각 t0에서 전체75초와 body/초기 인증15초를 나눈다. CoreRoute·
초기 Principal dependency는 같은 절대시각을 사용하고, endpoint가 기존 preparations(value) factory를 유지한 채
내부 keyword로 전체 기한을 실제 PreparationService.post에 전달한다. 해당 service는 caller와 진입+75초 중
이른 기한만 사용한다. 진입 시 만료/비유한·잘못된 타입은 admission/AI 전에 닫는다.

middleware 없는 direct route는 기존15초 이하의 fallback을 같은 내부 keyword로 전달한다. private/direct service에서
keyword를 생략하면 기존 asyncio.timeout(75)를 그대로 쓴다. 다른 route의15/140초·input cap·gate와 AI/Frontend
기한·schema·semantic/hash/key·TTL/admit/commitACK·owner/unknown·취소/rollback/session cleanup은 보존했다.

변경된 AccessBoundary의 CF036 readonly pin 한 값만 실제 bytes로 맞췄고 관련 고정 source/pin self 회귀 하나를 더했다.
AI32·pure Flow origin·기존 source 선택/worker·OS/FS/network/env guard와 package/lock·CI는 그대로다.

## 직접 보호 검사

기존 clean env·검증 Backend Python의 -I -S -B와 고정 meaning-self/meaning-unit을 사용했다. self4·단일 unit147개가
통과했고 예상 밖 guard 위반0·parent exit0·각 소유 임시 root 제거를 확인했다. 첫 집중 unit133개도 통과했으며,
이후 계약의 직접 호출 상한/외부 취소/타경로 보존을 더한 최종147개를 별도로 보존했다. 실패를 숨기거나
검사를 skip한 변경은 없다. 관련 없는 완료 suite·PG/Frontend·live-controller 검사는 로컬에서 반복하지 않았다.

실제 AccessBoundary→CoreRoute→초기 service dependency→PreparationService.post를 합성 ASGI로 통과했다.
auth/session·persistence·AI만 명시 fake이며, 테스트 clock을100배로 축소해 실제 timeout/cancel을 관측했다.
운영75/15 고정값과 같은 절대 기한 전달을 대조했고 old15 뒤/total75 전 성공, slow body/누적 body+초기auth15
중단·admission/AI0, total75의504/AI취소·rollback·세션 finally·늦은 ready 미채택을 확인했다.

같은 prepare key replay와 GET은 응답이 같고 추가 admission/AI0이며 다른 owner GET은404다. 이는 명시 fake
인증/DB의 관측이며 실제 SQL owner 수용은 아니다. 과거/비유한/잘못된 기한과 비정상 direct scope의 선거절,
직접 service의 상대75·명시 absolute 최대75, 더 짧은 상위 기한과 외부 CancelledError 전파/cleanup도 확인했다.

GET/DELETE/legacy/confirm과 잘못된 method/path/query·본문16KiB는 실제 경로 회귀로 확인했다.
Flow/Fundamental 등 다른 AccessBoundary branch의 AST 불변은 별도 source 증거이며 해당 제품 전체 수용은 아니다.

## 한계와 인계

실제 DB·Google·provider·키/env 읽기·설치·새 epoch/예약·flag 활성화는 없다. 기존350m과 소비/False 기록은 불변이다.
운영 epoch/정책의 SELECT-only 공급자와 fresh Principal/draft/spec·reserve/settlement ACK를 AI gateway까지 연결하는
실제 서버 서비스는 아직 없다. 이번 수정은 공개 Backend 조기 timeout의 제품 수정이며 production gateway 조립 완료가 아니다.

독립 최종 검토·Ready PR·exact-head CI/정상 merge 결과는 해당 단계의 증거로 별도 기록한다.

이번 absolute deadline은 Backend route→PreparationService.post의 내부 전달이다. exchange/build의 기존 AI wire에는
이 monotonic 값이 포함되지 않고 production phase provider도 없다. Backend의 바깥 취소가 실제 외부 provider
작업 중단이나 과금0을 보장하지 않으며, 그 연결은 production 조립의 미완료 선행조건으로 남는다.
