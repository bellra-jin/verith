# Supervisor composition API

기준 develop: `c07b407fa536761a5bc6899b325cf374075f0af0` (PR #84).

프론트 변경 없이 condition/waiver 없는 확정 단일 종목의 Flow, Technical 또는 두 관점을 선택·동의·실행·조회하는 별도 API다. 기존 단독 DTO와 공개 경로는 유지한다. 새 SQL 표·원장·migration·범용 workflow는 추가하지 않는다.

- `POST /api/supervisor/core/composition/prepare`: 기존 strict Draft를 받는다. 인증 후 기존 결정형 의미 서비스와 canonical Stock resolver로 의미/부정 별칭을 검증한다. 미지원 조건, 모호한 종목/관점, 잔여 의미는 `needs_clarification`이며 실행 가능한 hash를 반환하지 않는다.
- `POST /api/supervisor/core/composition/requests`: client_key, Draft, expected_plan_hash, consent만 받는다. 서버가 frame/Stock/명시 child_inputs/서버 정책을 재계산하고 별도 composition hash를 대조한다. 계획은 자식별 예약 상한·합계와 정확한 구성 fingerprint도 표시하여 해시에 결합한다. 두 관점은 `allow_partial_results=true`가 필수다. 단독 Plan이나 클라이언트 frame/config/policy는 복합 동의가 아니다.
- `GET /api/supervisor/core/composition/requests/{id}`: 같은 owner의 새 세션에서도 관측과 기존 owned reader의 검증된 결과 복원을 제공한다. 재접수·재게시·추가 엔진 실행은 없다. 설정 off 또는 현재 구성 제거 뒤에도 저장 기록을 읽는다. 같은 key POST 재요청도 관측만 한다.

기본 `SUPERVISOR_COMPOSITION_ENABLED=false`다. 새 작업에만 명시 Flow 정책/Technical 설정과 각 서비스 gate가 필요하며 설정을 자동 생성하거나 운영 활성화하지 않는다. GET/replay는 현재 설정·AI client 생성을 요구하지 않는다. Technical-only 의미 계획도 기존 결정형 core 인증 구성을 사용한다.

원 수신 시점부터 15초 접수/계획과 140초 전체 기한을 유지한다. 기존 runtime의 fresh commit ACK, 원 확인 세션, 한 번만 소비하는 continuation, 개별 원장의 예약/unknown hold, 부분 성공 저장을 재사용한다. 새 공개 API도 callback·실행 권한이나 private child key를 반환하지 않는다.

요청은 정확 route/method·raw path·중복 header·query 금지, JSON 16KiB, 실제 인증/Origin/CSRF 경계를 통과한다. 응답은 private/no-store다. 차트 결과를 포함하는 composition 경로만 별도 route class의 2MiB 제한을 사용하며 기존 CoreRoute의 65,536-byte 제한은 불변이다. Technical 결과는 전체 owned snapshot 검증 후 ticker/as_of/data_status/regime/signal/technical_signals/risk/charts/interpretation/verification의 명시 DTO로 투영한다. 내부 입력·execution authority·usage·transport 메타데이터는 반환하지 않는다.

## 검증 기록

로컬 core 156·meaning 367·analysis 291·core self 3 통과, guard 위반 0. 기존 보호 owned-PG 모드에서 58개 그룹(기존 54 + 공개 API 4)이 통과했다. 실제 SQL로 발급한 A/A2/B 세션과 실제 Backend middleware/router/DI 및 두 AI ASGI route를 사용했다. Flow/Technical/두 관점의 native 가짜 엔진 저장, A2 전체 결과 복원, 현재 구성 off/제거 뒤 GET 및 같은 key 관측, 타인 404·철회 401, 부분 성공과 unknown hold를 확인했다. 240KB 응답 정상과 2MiB 초과 거절은 별도 ASGI 회귀다. 원격 CI는 게시 후 확인한다. 최초 core baseline 실패는 승인된 새 경로의 OpenAPI projection 누락이었으며 기존 공개 계약을 바꾸지 않고 정확 새 세 경로와 두 DTO만 분리했다. 최초 PG 시도는 새 공개 준비 응답에서 멈췄고 상세 원문 예외는 저장하지 않았다. 가짜 AI core의 token 환경을 명시한 뒤 재검증해 통과했으며 첫 두 시도 모두 자기 DB 제거를 확인했다. 최종 예약 표시/fingerprint 보완 뒤 현재 소스의 PG 58그룹도 다시 통과했고 소유 DB 제거를 확인했다. 실제 공급자/키/기존 DB는 사용하지 않았다.

합성 ASGI/가짜 엔진과 실제 발급 SQL 세션/Verith 소유 격리 PG는 실제 OpenAI/KIS, 실제 compiled graph, Google 로그인·브라우저·TLS/운영 배포 수용과 구분한다. 이전 실행/once/원본 자료와 $1.30 보수 hold는 변경하지 않는다.

기존 PG 요약의 synthetic_provider_execution_runs=3/mock_provider_HTTP_requests=6은 앞선 CF053 baseline 그룹의 수치이며 전체 조합/API 누적 호출 수가 아니다. 이번 네 공개 API 그룹은 선택 관점별 가짜 엔진 증분과 관측 요청의 증분 0을 별도로 assert한다. 실제 공급자 호출과 compiled graph dispatch는 0이다.

PG 최종 회차 뒤 새 endpoint의 16KiB 초과 청크를 버퍼에 합치기 전에 거절하도록 순서만 보완했고, core 156/guard0을 다시 확인했다. 정상 요청/SQL·실행·복원 계약은 그대로다. 이 최종 크기 검사 delta와 PG 실행 바이트는 구분한다.
