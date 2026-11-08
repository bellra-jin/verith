<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

> **최종 구조 우선 계약:** ST-001 v1.15(명시 Flow 설정·최종 marker 정리)에 따라 불필요한 old shim을 제거하며 canonical 구현 하나로 정리한다. Flow 마지막3도 AI 루트 .env 명시 정책으로 이동했다. 실제 설정 값/AI 실행은 미검증이다. [진행 기록](../docs/work/ST-001-layout-progress.md)을 따른다.


> **현재 우선 기준:** ST-001 v1.10 실제 이동은 [전체 진행 기록](../docs/work/ST-001-layout-progress.md)을 따릅니다. 아래 v1.7/3-B의 20/35·type/lint 미실행은 당시 이력입니다. FE-01은 self 21/unit 36·standalone core/image tsc·대상 lint가 통과했으며 full generated-route/typegen·build/HTTP 수용은 여전히 미완료입니다.


## Verith Frontend 작업 범위

[상위 공통 안내](../AGENTS.md)와 [문서 권위](../docs/documentation.md),
[Frontend 작성 가이드](docs/coding-guidelines.md)를 읽는다. 위 Next 규칙은 그대로 적용한다.
관련 현 버전 번들 가이드를 코드 작업 전에 읽고, 예전 Pages Router 지식으로 파일을 재배치하지 않는다.

- 실제 entry는 [src/app](src/app), Next 설정은 [next.config.ts](next.config.ts),
  BFF/SSR 경계는 [session-proxy](src/shared/server/session-proxy.ts)·[session-backend](src/shared/server/session-backend.ts)다.
  설정을 확인하려고 앱을 기동하거나 private env를 읽지 않는다.
- Next는 같은 origin 진입/세션 쿠키 전달·화면을 맡고 최종 principal/owner는 Backend가 검증한다.
  원문 중복 Cookie·개인 no-store·검증된 pagination·CSRF/Origin·미설정 BACKEND_URL fail-closed를 유지한다.
  공개 owner/payload 저장·전체 삭제·Supervisor 직접 AI proxy를 다시 열거나 브라우저에서 DB/AI에 직접 붙지 않는다.
- Flow/인증과 Technical JSON·enum/화면 계약은 [문서 목록](../docs/documentation.md)에서 범위를 나눠 읽는다.
  공유 파생본은 원본/외부 자격 사용 허가가 아니다. [포트 계약](../docs/local_ports.md)의 localhost
  callback/Host/Origin을 IP alias나 다른 port로 완화하지 않는다.

## 3-B 당시 검사 도우미와 제한 (이력)

기존 의존성은 [package.json](package.json)·[package-lock.json](package-lock.json),
검사는 [tests](tests)·[scripts/check-local-ports.mjs](scripts/check-local-ports.mjs)에 있다.
3-B는 Git metadata와 명시 source 교집합·고정 신규 파일만 복사하도록 이 경로를 보완한다.
clean env의 검증된 절대 Node로 시작하며 [개발 실행표](../docs/development.md#3-b-검사-입구와-현재-차단)를 따른다.
자기 사본의 webpack build/production start·loopback 대역·nonce/child 소유와 수명을 확인해야 한다.
OPENSSL_CONF=/dev/null을 공개 시작/자손에 고정한 최신 self-test 20개·unit 4파일 35개가 통과했다. build는 단일 package snapshot을 사용하지만 추가 파일 요청이 거부되어 실패했다. HTTP/type/대상 lint는 미실행이며 파일 권한/OS profile/resolver 동작은 넓히지 않았다.
JS preload는 OS 격리가 아니며 [기록](../docs/work/ST-001-stage-3-B.md)의 차단을 보호 해제로 우회하지 않는다.

3-A [환경 안내](../docs/development.md)·[Frontend 예제](../docs/examples/frontend.env.example)는 비밀 없는 참고이며
실제 설정/실행 승인이 아니다. 3-B 구현은 **수용 미완료**이며 실제 Backend/Google/AI·DB/Docker는 검사하지 않는다.
검증된 OS 보호 아래 자기 사본 검사만 대상이다. 전체 ESLint의 기존 실패와
실제 인증 미검증은 [검증 상태](../docs/documentation.md#검증-상태와-이력)에 보존한다.

v1.6의 오류 정규화·실제 fs 소비 계측·controller 변조/정리 회귀가 최종 self-test 17개와 unit 32개에서 통과했다. build 3회는 모두 exit 78·자기 root 정리였다. 마지막 worker journal의 16개 중 15개는 부분 기록이며 native 전체 관측은 아니다. 이전 거절·실패는 이력으로 보존한다.

v1.7 진단 한정 실행은 self-test 20개·unit 35개 통과, build는 거부 22회/정규화 target ID 10개로 exit 78이다. 이 중 cgroup 1개·4회, unknown hash 9개·18회이며 hash 대상의 known-copy membership은 모두 false다. HMAC 식별을 읽기 허용에 쓰지 않으며 추가 build/HTTP/type/lint는 새 정책 판단 전 진행하지 않는다. 앞선 v1.6 수치·실패는 당시 이력이다.
