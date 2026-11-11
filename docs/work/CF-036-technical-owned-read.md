# CF-036 Technical 본인 목록과 차트 조회

기준 develop `4ca1dfe5b5ed41042c951f5353fe0037d4fe8d47`의 보존된 `feat/technical-owned-read`에서
정확 27경로를 작업한다. CF035의 내부 저장/본인 복구와 CF031 decoder/차트 wrapper를 재사용해 조회 전용 링크,
본인 목록, 기존 상세 URL을 연결한다. 새 engine·실행 schema·stage API·usage·Supervisor launch는 없다.

재개 전 staged 0과 tracked 8/untracked 6 WIP의 원문 hash를 대조했다. 13개는 보존 원형과 일치했고,
owned-report-view의 reportId keyed session wrapper는 재개 조율에서 추가한 첫 render 보호다. 기존 branch에서
WIP를 유지한 정상 ff-only 최신화 뒤 구현을 이어갔다. 원본 WIP/다른 worktree와 실제 모델 실행 자료는 변경하지 않는다.

Backend는 정확한 인증 GET 두 개만 연다. 기존 CF035 owner/snapshot/전체 index 정확 한 개 조건을 공유 SQL로
유지하고 선택 행의 canonical snapshot·projection을 다시 검증한다. 목록은 limit+1 고정 정렬, 상세는 별도 B 입력과
result의 원 TEXT/SHA를 전달한다. 캐시 금지·고정 오류·전체 15초와 목록 64 KiB/상세 4,259,840 bytes 한도를 적용한다.
조회는 commit/stage/AI를 호출하지 않는다. legacy read/save/analyze/trace/follow-up은 계속 닫혀 있다.

Frontend의 same-origin BFF는 exact GET/query와 기존 Cookie/Origin/Host 보호를 유지한다. client는 원 TEXT bytes의
SHA와 independent expected를 확인해 기존 decoder/TechnicalBoundaryPreview에 전달한다. 전후 session 확인과
전체 55초, report 선택·401·hide/unmount·취소·늦은 응답의 채택 차단을 검사한다. 화면은 합성·cutoff 미검증·시각
미보고·빈/미제공을 표시하며 조회와 실행을 구분한다.

## 직접 검증

2026-11-11의 보호 Backend self 3개와 단일 unit 40개가 통과했다. 기존 clean env의 절대 Python `-I -S -B`와
`technical-owned-read-self/unit` 고정 입구를 사용했으며 guard 위반 0, parent exit 0, 각 소유 임시 root 제거를
확인했다. 첫 unit의 JSONResponse 테스트 접근 오류 1건은 body JSON 읽기로 수정했고 영향 검사만 재실행했다.
테스트 대상은 실제 새 router/service/SQL/DTO이며 session I/O는 합성이다. 실제 timeout 회귀는 테스트에서만 기존
asyncio timeout을 짧게 주입해 await 취소와 function dependency rollback을 확인한다. 제품의 15초 설정값은 유지하며
실제 15초 경과를 기다린 성능/DB 취소 검사는 아니다. 기존 worker/OS/FS/network guard는 변경하지 않았다.

별도 새 source-copy launcher로 기존 `--verify-technical-owned-read-db` 고정 분기를 실행했다. 선택 source 250개와
기존 순수 AI 호환 6개를 고정했으며, 기존 proof/CreationReceipt·readonly preflight·동일 검증 연결 migration·제한 role·
소유 socket과 isolated_application 보호를 재사용했다. 과거 CF035 launcher·grant/resource는 수정하거나 재사용하지 않았다.
새 Verith 전용 PG에서 합성 결과를 한 번 stage한 뒤 실제 Principal/session과 AccessBoundary/router의 GET 45회를 확인했다.

PG/ASGI의 다섯 묶음이 통과했다: A 목록/상세와 새 로그인 원 TEXT/SHA·B 격리, 무세션/만료/철회/위조/중복 Cookie와
local Host, exact GET/query/UUID/method 및 legacy 차단, root/snapshot/전체 index eligibility 탈락의 404와 목록 제외,
선택 projection 변조 502 및 같은 소유 transaction에서 snapshot 테이블을 임시 rename한 schema 미준비 503이다.
각 변조 transaction은 rollback했다. read stage/commit/engine/provider는 0이고 private/env/network/HTTP 관측 거절도 0이다.
정확 receipt의 DB 제거/부재, source copy 제거, source/dependency/origin 후검사와 parent exit 0을 확인했다.
이 실제 PG/ASGI는 실제 Google 로그인이나 BFF 서버·브라우저를 한 체인으로 실행한 E2E와 구분한다.

Frontend 보호 `technical-owned-read-unit`은 신규 실제 함수/상태·composition 35개, BFF 24개, tooling 65개의
총 124개를 통과했다. 집중 type/lint는 각각 exit 0이며, 실제 pinned React/Recharts/Lucide/react-is registry를
준비하는 기존 `technical-chart-unit`도 65개가 통과했다. 중복되는 tooling 수를 별도 고유 테스트로 합산하지 않는다.
최종 source의 예상 외 guard 위반은 0이고 자기 임시 root가 모두 제거됐다. 개발 중 가짜 시계 테스트의 동기화와
기존 terminal receipt가 엄격한 8카운터를 받는 점을 보완한 과정은 원문 로그에 보존했다. 새 owned GET 카운터는
기존 receipt를 바꾸지 않고 별도의 같은 nonce/PID/cwd/port에 결합된 artifact로 검증한다. 기존 worker/guard·
원래 terminal helper·CF031 decoder/preview/chart panel·package/lock은 변경하지 않았다.

## Mounted 화면 관측과 정리

기존 허용된 미로그인 Supervisor test Chrome 창을 이전 emitted origin과 native AX로 식별한 뒤 새 탭에서
이번 고정 `technical-chart-browser`의 emitted origin만 사용했다. 새 profile·다른 Desktop·임의 브라우저는 만들지 않았다.
한 번의 590초 회차 안에서 실제 production owned read component/lib와 React/Recharts가 합성 session/GET을 소비했다.
Next/AppShell/BFF 서버·실제 인증·PG를 이 브라우저 체인에 올린 E2E가 아니다.

직접 확인한 동작은 목록 두 카드의 native 상세 이동, 재조회/reload, 5년·RSI 전환, 다른 report 선택 후
3개월/RSI 초기화, 빈 목록, 401/404/긴 오류의 고정 안내와 차트 숨김, 전후 owner 변경의 채택 차단이다.
1200ms 합성 지연 조회 뒤 새 탭으로 숨기고 복귀했을 때 idle/차트 0을 관측했으며 자동 재조회 없이 명시 GET으로
새 session 확인 뒤 차트를 복구했다. upstream 작업/비용 중단이나 정확한 중복 GET 횟수를 이 화면 관측으로 보장하지 않는다.
동기 중복 잠금·timeout·hash-await 뒤 취소와 옛 finally 격리는 보호 unit 근거다.

fixture 진단의 innerWidth/innerHeight로 CSS viewport 390×719와 1440×1438을 각각 확인했고 둘 다 overflow=false였다.
390에서는 DevTools device toolbar의 표시 배율 100%, 1440에서는 같은 toolbar의 표시 배율 50%였다.
이는 browser page zoom이나 물리 화면 크기 검증이 아니다. 390에서 안내문/실제 차트가 폭 안에 있고 버튼이 줄바꿈되는
screenshot을 관측했고 native Tab으로 5년 버튼에 도달해 Return으로 전환한 뒤 RSI에 Tab·Space를 적용했다.
표준 1440×844나 물리적 휴대폰/Safari 수용으로 확대하지 않는다. 처음 DevTools AX 값 설정이 원하는 크기에 적용되지 않은
상태는 관측 성공에 포함하지 않았고, focused native keyboard 입력 후 실제 진단 수치를 대조했다.

fixture의 인위적 ‘다른 report 선택’은 key 초기화를 위해 pushState와 render를 직접 조합한다. 그 history 항목에서
native Back한 경우 fixture는 Next router처럼 prop을 갱신하지 않아 URL/prop 불일치로 내용을 숨기고 retry도 닫혔다.
이 제한은 production route 전환의 실패로 단정하거나 정상 Back 복구 통과로 표현하지 않는다. 실제 native href와 page
composition/type, BFF 함수, PG/ASGI 근거를 각각 구분한다.

on-page 완료를 누른 뒤 CUA에서 `lifecycle completed`와 root unmount(차트·링크 0)를 확인했다. 보호 parent exit 0,
completed terminal receipt, 원래 sessionGET 28 및 실행 관련 POST/model/provider 0, 별도 listGET 5/detailGET 10/
modePOST 9를 확인했다. generic receipt의 `ack=not_observed`, `browser:* not_executed`, `ui_acceptance=not_executed`는
원형대로 보존했으며 이 ACK를 DB commit ACK나 자동 UI 수용으로 바꾸지 않는다. 위 화면/키보드 관측은 별도 operator의
CUA 근거다. 등록 child/readiness/listener 종료, package/registry/provenance 후검사와 소유 root 제거는 보호 parent 근거로 통과했다.
추가 수동 `/bin/ps`의 정확 소유 PID 조회는 로컬 sandbox EPERM으로 차단돼 그 방식의 PID 부재는 미확인이다.
다른 도구/경로 재시도나 신호 전송은 하지 않았다. 이 추가 감사 한계를 기존 보호 parent의 정상 cleanup과 구분한다.

실제 engine/KIS/provider,
운영 DB·migration·사용자 합성 seed, 실제 Google 로그인, 전체 Next build와 Technical 실행은 수행하지 않는다.
원격 exact-head CI·독립 리뷰·Ready/PR/merge는 조율 결과를 별도로 기록하며 검증되지 않은 경계를 통과로 표시하지 않는다.
