# CF045 · 요청별 Supervisor 의미 보완과 비용 승인

명시된 기존 owner 계정과 검토된 정책·계수 근거가 있을 때, 실제 신규 준비에서 요청별 Gateway를
생성하고 인증된 Backend 예약·phase 승인·정산을 사용하는 제품 경로를 연결했다.
기본 설정은 비활성이며 운영 계정 발급·실제 key 공급·배포 활성화는 수행하지 않았다.

## 구현

- 준비별 고정 grant와 nonce digest, 원 Principal fingerprint, 별도의 준비/provider hash 공간을
  additive `c45001a7e0001`에 저장한다. 기존 migration/행과 public DTO는 바꾸지 않는다.
- 기존 CF044 SQL을 transaction stage로 재사용한다. count 예약·소비·grant 연결은 한 commit,
  generation은 최초 승자만 소비, 정산과 terminal receipt도 한 commit이다.
- session→준비 root/leaf→account→reservation→grant 순서로 fresh identity를 확인하고 lock을
  끝낸 뒤만 HTTP를 시작한다. 원 absolute deadline과 TTL은 늘리지 않는다.
- 실제 policy2 start에서 보완이 필요한 경우에만 새 Gateway/budget client를 만든다.
  deterministic·policy1·continue·동일 key replay/GET는 유료 권한을 새로 만들지 않는다.
  잘못된 paid enable 값도 startup을 깨지 않고 유료 경계에서만 비활성으로 판정한다.
- 두 내부 API는 별도 service token+grant로 body/SQL 전에 인증하고 닫힌 입력과 5초 callback을
  사용한다. 공개 OpenAPI에는 노출하지 않는다. provider request는 transient 검증 입력이다.
- ACK 불명 후 명시적인 handle-bound reconcile은 no_autoflush·SELECT-only이며 송신권 False다.
  자동 재시도/환급/rollover·late receipt 자동 복구는 없다. observed 추정액과 실제 청구액을 구분한다.

## 직접 검증

최종 source의 기존 보호 입구에서 다음을 직접 실행했다.

| 검사 | 결과 |
|---|---|
| meaning-self | 6 통과 |
| meaning-unit, 단일 기존 collection | 276 통과, guard 위반 0 |
| 직접 영향 meaning-assembly-unit | 103 통과, guard 위반 0 |
| 고정 `--verify-supervisor-meaning-runtime-db` | 소유 PG 12그룹 통과 |
| source/dependency/origin 사후 대조 | 통과 |
| 자기 PG·source 사본 cleanup | 정확 receipt/부재 확인, parent exit0 |

PG에서는 실제 Backend preparation HTTP→AI core ASGI→실제 요청별 Gateway→provider MockTransport→
Backend phase ASGI→실제 SQL을 연결했다. mock count1/generation1, synthetic supplier1이며 실제 provider는0이다.
두 SQL session의 count/generation 단일 승자, stage rollback, commit 후 ACK 손실 wrapper와 읽기 복구,
HTTP 중 다른 SQL transaction의 NOWAIT lock 성공, 원 요청 기한 소진, DELETE 뒤 generation0,
차단되지 않은 계정의 count→session revoke→generation0, 형식이 맞는 잘못된 nonce 거절을 확인했다.
정산 ACK 손실 뒤 reservation과 grant terminal의 원자 보존, 세션 철회 뒤 고정 비용 정산,
다른 terminal 증거 conflict, 빈 표 downgrade/reupgrade 및 populated downgrade 거절도 확인했다.
실제 SQL 관측과 ACK 손실 wrapper simulation은 구분한다.

초기 실패 이력은 보존했다. launcher의 허용 환경/PATH와 중첩 OS canary 실패는 worker 시작 전이었다.
초기 unit의 새 내부 경로 baseline projection·상태 enum·합성 count fee 기대를 정확히 수정했다.
PG에서 SQL UUID subtype을 strict Binding에 넘기는 실제 경계 오류는 명시 UUID 변환으로 수정했다.
이후 철회 fixture의 과거 timestamp와 기대 예외 타입 오류를 수정했으며 기존 DB 제약·auth는 유지했다.
최종 작은 raw enable 설정 보완 뒤 275/103/12를 다시 확인했다. 동일 과거 전체 suite를 돌리지는 않았다.
별도 읽기 전용 독립 리뷰에서 구체적 blocker가 없었고 guard/bootstrap/기존 Gateway·spec 보존을 확인했다.

## 남은 범위

운영 정책/계정 발급, 별도 service token과 key supplier 제공, 실제 AI 전체 startup·배포 활성화,
실제 provider 품질·청구서 확인 및 Supervisor→Flow 전체 인수는 미완료다.
실제 사용자 로그인/브라우저·실제 provider·외부 데이터 호출은 이번 검사에 포함하지 않았다.
기존 private 실제 검증의 소비·보수 예약은 이 SQL 계정으로 이전하거나 초기화하지 않았다.
Technical 설치·다른 WIP·다른 프로젝트 DB/컨테이너와 서비스별 환경 파일은 변경하지 않았다.

Ready PR의 정확 head CI와 develop 정상 병합 결과는 최종 게시 인계에서 구분한다.

## 게시 CI의 시간 정밀도 회귀

첫 PR CI에서 기존 CF042 단언의 `(258.325537915998 - 183.325537915998) == 75`가
부동소수점 상쇄로 실패했다(274 통과/1 실패, guard0). 제품 timeout은 바꾸지 않고
`deadline == started + 75`, `admission == started + 15`를 정확 비교하도록 수정했다.
실제 실패 기준값의 결정적 회귀와 더 짧은10초 기한의 미연장을 추가했으며,
보호 meaning-unit 276개 통과·guard0과 별도 읽기 리뷰를 확인했다. 제품 코드/PG 경로는
변경되지 않아 기존 self6/assembly103/소유PG12의 직접 증거를 보존했다.
