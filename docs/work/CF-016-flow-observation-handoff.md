# CF-016 · Flow 관측 복구·인수 안내

Base `f88d593fda03e0cf1f6709fb8960662e76821cb7`, branch `fix/flow-observation-recovery`. 정본 v1.0 SHA-256 `61502437f66a1eca37c337030c197786ae0bab6520eafbf217465c6213a21009`; 정확 Frontend/문서11경로다. 최초 인계 SHA 대조 중 정본의 최종 SHA 갱신을 수신해 전체 본문을 다시 읽고 이 값으로 고정했다. 그 시점 제품 변경은 없었으며 브랜치를 다시 만들지 않았다.

## 구현과 독립 검토

- 실제 사용하는 `AnalysisObservation`은 첫 server deadline과 관측 시작부터 단조120초를 연장하지 않는다. 순차 예약과 마지막 GET 최대1회, 각 조회15초 abort를 유지한다. terminal/result_ready는 예약을 멈추고 클라이언트 대기로 서버 상태를 재작성하지 않는다.
- `observeAnalysis`는 세션/계정/URL/generation을 재검증하고 같은 분석 GET 한 번만 수행한다. 수동 복구는 자동 관측·POST·새 키를 만들지 않는다. explicit URL을 다른 pending ID로 대체하지 않으며 저장소 실패 시 알려진 URL GET은 허용하되 POST는 차단한다. 초기 세션 실패도 같은 화면에서 재확인한다.
- 독립 source 검토에서 terminal/수동 관측 종료 후 hidden→shown의 session-only/no-view가 POST를 열 수 있음을 확인해 stopped 결과의 verified=false를 유지했다. 알려진 ID에 원래 동일 pending 키가 없으면 publication POST도 닫는다. 이전 abort/catch/finally·늦은 응답은 generation/intent가 다른 상태를 지우지 못한다.
- 재무 root.as_of 원본은 보존하고 엔진 기록 시각/자료 기준일 미확인으로 안내한다. 실제 기간/공시 필드와 구분하며 raw JSON·0/null/날짜를 바꾸지 않는다. 과거 합성 예제, 이미 연결된 production writer와 남은 준영 도메인/운영 인수를 분리했다. [Flow 실제 연동 확인 항목](../flow-live-readiness.md)은 실제 환경 수용이 아니다.

## 직접 실행한 변경 관련 검사

공통 시작은 기존 검증된 절대 Node와 `env -i LANG=en_US.UTF-8 TZ=UTC OPENSSL_CONF=/dev/null`, 기존 `frontend/scripts/check-local-ports.mjs`다. 입구/guard/workflow는 수정하지 않았다.

| 기존 고정 모드 | 최종 결과 |
|---|---|
| analysis-unit | 3파일, 12+9+3=24/24, exit0 |
| analysis-type / analysis-lint | 양쪽 exit0, 오류0/경고0 |
| fundamental-unit | 3파일, 7+9+3=19/19, exit0 |
| fundamental-type / fundamental-lint | 양쪽 exit0, 오류0/경고0 |

모든 최종 회차는 기존 OS/FS/network 보호 및 source 검증 아래 관측 위반0·자기 root 제거를 확인했다. JS filesystem journal과 native 전체 관측은 구분하며 native 전체 접근0을 주장하지 않는다. 두 unit 모드의 BFF/config 중복은 기존 고정 선택이다.

최초 Flow unit은 11/12에서 실패했다. 합성503 fixture가 기존 공통 JSON envelope를 누락해 기존 wire가502로 분류했기 때문이다. 제품 wire/기대값은 보존하고 fixture를 계약에 맞췄다. 해당 unit/lint만 영향 재검증했으며, 마지막 same-ID pending POST 경계와 deadline 방어 보완 후 analysis unit/type/lint를 최종 확인했다. 통과한 무관 검사와 재무 검사는 반복하지 않았다.

실제 helper/VM 회귀는 주입시간으로15초 이후 저장 성공, 고정120초/짧은·잘못된·과거·먼 미래 deadline, 마지막 조회1회와 terminal stop, session/GET503→회복, 저장소 실패/ID 없음/URL 우선, 401·계정 변경·중복 intent·이전 abort·늦은 응답, stopped session-only 복귀·원래 키 보존과 GET-only를 실행했다. JSX 생명주기·성공 오류 해제·버튼/abort/finally 연결 및 재무 label/raw값 보존은 source assertion과 순수 formatter 실행이며 실제 React/DOM/browser 클릭 성공이 아니다. 실제120초 sleep은 하지 않았다.

## 유지한 한계와 CI

로컬 Backend/PG·전체 build/HTTP·서비스·Google/KIS/OpenAI·사용자 키/.env/cache/기존DB·설치를 실행하지 않았다. Backend/AI/DB/runner/workflow/guard와 기존 API/schema/payload 계약 hash·원본 금융자료는 변경하지 않았다. 문서의 이름/필드는 source만 대조했으며 실제 설정·계정·주소·자료시점·품질·호출/비용은 미확인이다.

기존 PR safe checks / flow-quality의 최신 HEAD 및 Ready CI 성공을 병합 조건으로 확인한다. 이 원격 CI는 Backend 고정 검사이며 로컬 Frontend unit/type/lint나 브라우저 성공을 대신하지 않는다. 실제 CI URL/head/checkout merge와 병합 결과는 PR 및 최종 인계에 별도 기록한다.

<!-- CF016_PR_BODY_START -->
Flow status observation now uses its first server deadline and a fixed monotonic120s budget, with at most one final bounded GET. In-page manual recovery revalidates the session and observes the same analysis without POST, new key or AI execution; storage failure does not block a known URL GET and cannot enable POST. Stopped/no-view and missing same-ID pending-key paths remain closed for publication.

Fundamental root.as_of is labeled as an engine timestamp with source date unconfirmed, preserving the original JSON/value. Updated handoff separates the historical example, already-connected production writer and remaining domain/operational work; live-readiness documents source-backed settings/fields without reading actual values.

Validation: local protected analysis-unit24 (12+9+3) and fundamental-unit19 (7+9+3), both fixed type/lint exit0, observed guard violations0, all owned roots removed. Helper/VM tests inject clocks and responses; lifecycle wiring is source coverage, not actual React/browser clicks. Initial Flow unit11/12 failed because the synthetic503 omitted the existing common JSON envelope; only the fixture was corrected. Independent review findings and related revalidation are recorded.

Exact11 Frontend/document paths. Backend/AI/DB/workflow/runner/guards/API/schema/payload and original financial data are unchanged. No local Backend/PG/build/HTTP/service/provider/credential/cache work. Existing PR/Ready CI is Backend-only and is checked separately; it does not replace local Frontend validation.
<!-- CF016_PR_BODY_END -->
