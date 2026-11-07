<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

## Verith Frontend 작업 범위

[상위 공통 안내](../AGENTS.md)와 [문서 권위](../docs/documentation.md),
[Frontend 작성 가이드](docs/frontend_coding_guidelines.md)를 읽는다. 위 Next 규칙은 그대로 적용한다.
관련 현 버전 번들 가이드를 코드 작업 전에 읽고, 예전 Pages Router 지식으로 파일을 재배치하지 않는다.

- 실제 entry는 [src/app](src/app), Next 설정은 [next.config.ts](next.config.ts),
  BFF/SSR 경계는 [session-proxy](src/lib/session-proxy.ts)·[session-backend](src/lib/session-backend.ts)다.
  설정을 확인하려고 앱을 기동하거나 private env를 읽지 않는다.
- Next는 같은 origin 진입/세션 쿠키 전달·화면을 맡고 최종 principal/owner는 Backend가 검증한다.
  원문 중복 Cookie·개인 no-store·검증된 pagination·CSRF/Origin·미설정 BACKEND_URL fail-closed를 유지한다.
  공개 owner/payload 저장·전체 삭제·Supervisor 직접 AI proxy를 다시 열거나 브라우저에서 DB/AI에 직접 붙지 않는다.
- Flow/인증과 Technical JSON·enum/화면 계약은 [문서 목록](../docs/documentation.md)에서 범위를 나눠 읽는다.
  공유 파생본은 원본/외부 자격 사용 허가가 아니다. [포트 계약](../docs/local_ports.md)의 localhost
  callback/Host/Origin을 IP alias나 다른 port로 완화하지 않는다.

## 현재 검사 도우미와 제한

기존 의존성은 [package.json](package.json)·[package-lock.json](package-lock.json),
검사는 [tests](tests)·[scripts/check-local-ports.mjs](scripts/check-local-ports.mjs)에 있다.
Frontend 작업 디렉터리에서 `node scripts/check-local-ports.mjs`를 사용하는 기존 경로가 있지만,
기존 Node/설치 의존성·사본 대상에 private 자료가 없는지 확인한 별도 검사 작업에서만 실행한다.
새 임시 사본/loopback HTTP 대역·build/type/대상 lint를 만들고 자기 사본을 정리하는 부작용이 있다.
현재 도우미의 지정 디렉터리 재귀 복사는 .env 제외만으로 다른 key/dump/log·symlink 자료의 안전한
제외까지 보장하지 않는다. 복사 범위/자원 경계를 먼저 검토하며 불확실하면 실행하지 말고 보고한다.

3-A [환경 안내](../docs/development.md)·[Frontend 예제](../docs/examples/frontend.env.example)는 비밀 없는 참고이며
실제 설정/실행 승인이 아니다. 3-B의 수집 전 공통 안전 entry는 **미구현 후속**이다. 이 단계에서는 위 명령이나
unit/build/lint·실제 Backend/Google/AI·DB/Docker를 실행하지 않는다. 전체 ESLint의 기존 실패와
실제 인증 미검증은 [검증 상태](../docs/documentation.md#검증-상태와-이력)에 보존한다.
