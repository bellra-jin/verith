# CF-002: Google OIDC 세션과 Flow 소유권 경계 구현

기존 무인증 리포트 API와 Backend를 거치지 않는 AI 프록시를 닫고, Google code+PKCE 로그인과 PostgreSQL 폐기 가능한 앱 세션으로 본인 Flow 결과의 목록/count·상세·개별 삭제를 보호합니다. 선행 CF-001 PR #1 병합 기준 develop `d8d800b104822dfc72e1a7b0daecfa1ac45b9e43`에서 시작했으며 CF-002 정본 v0.2→v0.6을 적용했습니다.

## 변경

- auth user/identity/session 모델과 확장 migration. raw bearer 대신 SHA-256 digest, 유한 만료·폐기·사용자 비활성 상태를 매 요청 검증합니다.
- Google 고정 discovery/endpoint·openid·PKCE S256·일회 state/nonce/browser 결합과 RS256/claims 검증. 실제 계정 선택·로그인/MFA는 사용자만 수행했습니다.
- Flow root owner와 정확히 한 공통 index/동일 owner를 SQL로 확인합니다. legacy owner NULL·원본 payload·외부 UUID를 자동 재귀속하지 않습니다. 공개 임의 저장·일괄 삭제·Supervisor 직접 AI/기존 프록시 우회를 차단합니다.
- Next same-origin BFF/SSR·no-store·원문 중복 쿠키 거부·검증된 pagination과 개별 삭제 복귀. Frontend3200/Backend8200/AI9200 및 로컬 데이터 host port 문서를 정리했습니다.
- 앱 DB fallback 없는 테스트 guard와 직접 생성 영수증 기반 일회용 PG, 제한 역할·이중 readonly·동일 연결 migration, env-free exec 앱·유한 수명·자기 자원 정리를 구현했습니다. Backend만 승인된 Google 두 키를 선택 처리합니다.

## 검증

- 최종 Backend unit **343 passed**; 준비 도우미/테스트 12파일 Ruff·format, 변경 Python62파일 AST, diff check 통과.
- 비밀 env 없는 새 사본에서 Frontend **18 passed**(handler/BFF15 + 실제 로컬 Next HTTP3), TypeScript·CF-002 변경 TS/TSX24파일 ESLint·production build 통과. HTTP 검사는 합성 Backend이며 실제 Google 검증과 구분합니다.
- 전체 Frontend ESLint는 **실패**: 기준 HEAD와 동일한 `frontend/src/types/technical.ts:191,207`의 기존 explicit-any2건, 기존 unused 경고3건입니다. 범위 밖 Technical 타입을 임의 수정하지 않았습니다.
- v0.4 당시 별도 실제 PG integration54 + seed3, 신원 경쟁·동시 logout HTTP·migration/rollback 회귀 통과. 이번 회차에 그 전체54개를 재실행한 것은 아닙니다.
- v0.6 새 소유 DB의 제한 역할/migration·내부 쓰기/rollback·normal/부분 startup/SIGTERM 정리, 별도 합성 controller A/B·owner-NULL legacy 비노출/보존을 실제 PG에서 확인했습니다.
- 실제 Google 두 계정의 사용자 로그인 보고와 canonical identity/활성 session/다른 user 기반 bind-A/B를 확인했습니다. 실제 DB/service의 본인 목록/count/페이지/상세·타인 조회/삭제 거부가 통과했습니다.
- 사용자 브라우저 확인: A 본인2건/상세, B seed 전0건·seed 후2건, B→A1 상세404, B2 본인 UI 삭제 후 B1만1건, A2건 보존·삭제B2 재접속404. 서버 aggregate Flow4→3과 대조했습니다. 개별 owner별 DB 잔여 조회나 네트워크 status 직접 캡처로 표현하지 않습니다.
- 첫 실제 환경의 사용자 로그아웃 후 DB revoked1/active0 확인. 두 번째 환경은 최종 active2/Flow3 기록 뒤 finish/exit0·기록 PID/정확한 CID/임시 사본 제거와 부재를 확인했습니다. 기존 컨테이너·volume·앱 DB는 변경하지 않았습니다.

## 남은 제한 / Draft 유지 이유

- 실제 시간 만료, 옛 cookie 재전송, A→B 반대 방향 교차 UI, 각 실제 HTTP/BFF 응답의 직접 관측은 미검증입니다. B 상세 본문 명시 사용자 확인도 별도로 받지 않았습니다. 이번 세션TTL3600은 runtime 수명보다 늦게 만료되므로 자연 만료를 통과했다고 주장하지 않습니다.
- 실제 로그아웃/세션 폐기와 단순 임시 DB 제거를 구분합니다. 추가 검사는 짧은 TTL의 검토된 별도 환경 등으로 진행해야 하며 원시 cookie/token/sub를 추출하지 않습니다.
- 단일 프로세스의 한시 OIDC state 한계, 미설정 fail-closed를 유지합니다. 새 분석·실제 AI·worker·게시 복구·운영 배포는 범위 밖입니다. CF-002 전체 완료나 공개 준비 완료로 선언하지 않습니다.
- **ignored `Docker-compose.yml`은 이 커밋에 포함하지 않습니다.** 로컬 host mapping15432:5432/16379:6379/17474:7474/17687:7687만 수정했고 기존 환경/volume/내부 port는 보존했습니다. 사전 구조 지문을 별도 보관하지 않은 한계도 문서에 있습니다. clone에는 추적된 실행 코드·README·`docs/local_ports.md` 안내가 전달되며 ignored compose 변경은 전달되지 않습니다.
- 실행 중 생성한 원본 영수증 JSON/임시 사본은 stage하지 않으며, 비민감 종료 영수증 요약은 검증 문서에 포함합니다. `.env`·credentials·실행 DB·Google 두 키는 포함하지 않습니다. 사용자 직접 저장한 private `.env`는 읽거나 stage하지 않습니다. Console/새 자격증명/기존 서비스 실행 전환도 하지 않았습니다.

상세: `backend/docs/flow_auth_ownership.md`, `backend/docs/google_login_check.md`. commit/push/PR 생성·Ready·merge·deploy는 실행하지 않았습니다.
