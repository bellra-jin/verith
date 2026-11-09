# CF-018 Flow 사용 한도·보수적 비용 예약

- 사용 정본: CF-018 v1.0, SHA-256 `12a6ecd24935a34b92797c126442df4e96e73e075a98c2e63374200acb441ad8`.
- 최신 UX/후속 순서 기준: 전체 작업 운영 v1.2 §4.1, SHA-256 `42c4601a23635eb3aea36605234025b75b31994e35cde72a6c1ab54981a2fa2f`. 여기서 재정의하지 않는다.
- base develop `d6efac632ca87b194e4025892c3741815039d2b5`, branch `feat/flow-usage-limits`, 정본36경로 범위. 사용자 Git 게시 전 미커밋 구현이다.

## 구현과 범위

서버 인증 사용자/편입 Flow 실행의 KST 일일 횟수·서비스 금액을 원자 예약하고, 수신 dict의 독립 검증 가능한 호출 usage를 결과 게시/재인증보다 앞서 원 기간에 정산한다. 새 run↔예약 및 user/service 기간 관계는 DB deferred commit-time 검증, 식별/가격/기간 한도는 불변이다. 기존 key·GET·legacy/snapshot 게시 복구는 새 정책 파싱/차감보다 앞서 처리한다. 설정은 raw/기본 닫힘이며 실제 운영 값을 활성화하지 않았다.

SDK constructor 뒤 invoke 직전과 KIS 실제 post/get 진입을 관측한다. 응답 usage는 content cap/deadline보다 먼저 읽는다. 실제 작업 종료 때만 미호출을 확정하며 cached 누락/usage 오류·HTTP/JSON/body 유실·timeout은0이 아닌 unknown hold다. 모델/관측 상한 이상은 사용량 정산 가능성과 독립적으로 blocked를 보존한다. attempted True는 False/NULL로 되돌릴 수 없다.

보고서 계산·v1 payload·prompt/config·다른 고정 profile·기존 원장/복구/fence는 보존한다. 새로운 worker/재전송/관리 API나 화면을 만들지 않았다. Frontend는 안전한429 code와 고정 안내만 추가한다. 다른 관점/앱 밖 비용과 KIS 요금은 통제/산정하지 않는다. 예약 $0.9135는 실제 비용·청구서·지출 승인이 아니다.

## 검증 상태

- Backend 보호 self **2/2**, 신규 단일 집중 unit 최종 **57/57**, guard 위반 **0**, 자기 임시 root 정리, exit 0.
- Frontend 기존 analysis 입구: unit **25/25 (13+9+3)**, 대상 type/lint exit 0, 관측된 guard 위반 0, 자기 root 정리. helper/VM 및 source assertion이며 실제 React/브라우저 실행은 아니다.
- 새 owned PG 최종 **9그룹**, public 합성 dispatch **19건 각각 1회**, HTTP 거절 **16건**, DB 제약 거절 **20건**, private/env/외부 HTTP·network 접근 **0**, 전체 exit 0. 실제 session/CSRF/owner와 검증된 제한-role 연결·동일 연결 migration을 사용했다. 생성한 자기 자원만 exact CID 부재까지 확인해 정리했고 공개 source-copy도 제거했다.
- PG는 DDL 실패 rollback·legacy bytes/구 snapshot 복구·빈 downgrade/reupgrade, 같은 key의 결정적 winner/loser202→최종 GET 수렴·예약/카운터1, 사용자/서비스·금액 경합, grant/정산/snapshot/게시 ACK 불명, 확정 rollback/취소, 결과 오류·세션 폐기·늦은 응답의 독립 정산, attempted 단조성·최초 확정/동일 재수신, 삭제 후 회계 보존, 모델/상한 이상 blocked, deferred 관계/식별/불변 조건 및 nonempty downgrade 거부를 확인했다. 원 기간 이후 수신한 receipt는 원 user/service 두 bucket만 정산하고 현재 기간 두 bucket의 저장값은 불변임을 직접 비교했다.

독립 조기 source 검토의 모델/상한 이상 독립 판정·attempted=True 역행 금지, 정확 parent revision 허용·결정적 same-key 경합·날짜 경계 정산 보완을 제품/unit/PG에 반영했다. 최종 독립 source 수용은 별도 검토 결과와 구분한다. 정책·한도·종목·실제 지출을 활성화한 검사는 아니다.

### 실패와 필요한 영향 재검증

최초 unit 54/56의 두 실패는 cached 가격 기대값 산술 오류와 합성 row의 claim digest 누락이었다. fixture 수정 후56/56, 아래 DDL 회귀 추가 후 최종57/57이다. 제품 가격 계산을 기대값에 맞춰 바꾸지 않았다.

PG 준비/실행 이력은 보존했다. 1회차는 local_context exit1·자원 생성 전 중단이며 launcher PATH에 기존 Docker CLI가 없음을 확인했다. 원 예외 종류는 미수집이므로 그 이상의 원인을 확정하지 않는다. 2회차는 parent migration 뒤 legacy fixture raw INSERT에서 중단했고 원 SQLSTATE는 미수집이다. typed Core INSERT/명시 deadline으로 수정한 뒤 해당 단계가 통과했다. 3회차는 새 migration에서 SQLSTATE22P02: SQLAlchemy가 CHECK의 압축 JSON `:숫자`를 bind로 해석해 NULL을 넣는 현상을 공개 DDL 컴파일로 확인했다. JSON 의미가 같은 literal 표현으로 수정하고 ORM/migration 컴파일 회귀를 추가했다. 4회차는 잘못된 CSRF를403으로 기대한 checker 오류를 기존401 AUTH_REQUIRED 계약으로 맞췄다. 5회차는 checker 시간 이동이 admission 이후 expire에도 적용되는 것을 source로 확인해 admission 시각 한 번에만 적용하도록 수정했다. 기존 guard/제품 인증·deadline을 완화하지 않았다. 2~5회차의 자기 PG도 각각 exact CID 제거·부재를 확인했고 source-copy를 정리했다. 필요한 실패 영향 PG 재검증만 이어 최종6회차에서9그룹을 통과했다. 통과한 무관한 suite/Frontend/기존 PG는 반복하지 않았다.

## 인계와 미검증

실제 key/.env·원래 cache/home·기존 DB/volume/서비스를 사용하지 않는다. 신규 설치나 실제 공급자 호출은 하지 않는다. 원격 최신 head/Ready CI는 사용자 Git 게시 이후 별도 확인해야 한다. 사용자 직접 add/commit/push/Draft PR/Ready/merge이며 개발 측은 명령/본문·exact manifest/NUL pathspec만 준비한다.

<!-- CF018_PR_BODY_START -->
## 변경

Flow 새 실행에 인증 사용자·서비스 일일 횟수/보수적 비용 예약과 독립 usage 정산을 연결합니다. 같은 key 조회·게시 복구와 legacy는 추가 차감하지 않고, unknown은 잔여 예약을 유지합니다. DB commit-time 참조/기간/identity 검증과 최소429 고정 안내를 추가합니다.

## 검증

- Backend 보호 self2/unit57·guard0, 새 owned PG9그룹/합성 dispatch19건 각1/HTTP 거절16·DB 거절20/금지 접근0 및 자기 자원 정리, Frontend unit25·대상 type/lint exit0.
- 실패 fixture·DDL literal 수정과 영향 재검증 이력은 작업 기록에 보존했습니다. React/브라우저·실제 공급자·원격 CI 실행과 구분합니다.
- 실제 provider/Google/browser·운영 설정/기존 DB·다른 관점 비용은 검증/통제 범위가 아닙니다.
- $0.9135는 실제 청구액이 아닌 실행 예약액입니다. 원격 최신 head와 Ready CI 확인이 남아 있습니다.

상세 기록: `docs/work/CF-018-flow-usage-limits.md`.
<!-- CF018_PR_BODY_END -->
