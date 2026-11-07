# Verith Frontend

## 공용 환경 참고 · ST-001 3-A

[개발 환경 안내](../docs/development.md)와 [Frontend 변수 예제](../docs/examples/frontend.env.example)는
비밀 없는 참고 형식이다. 실제 .env 자동 생성/복사·서비스 실행 절차가 아니며 현재 private override는
미확인이다. 서버 BACKEND_URL과 공개 NEXT_PUBLIC_API_URL의 미설정/빈 값 차이를 구분한다.
3-B 수집 전 안전 entry는 아직 미구현이며 아래 기존 명령을 이번 단계에서 실행하지 않는다.

## 문서 탐색과 현재 범위

[문서 권위/검증 상태](../docs/documentation.md), [Frontend 작성 가이드](docs/frontend_coding_guidelines.md),
[현재 책임 지도](../docs/architecture/current-boundaries.md)를 먼저 읽는다.
실제 route entry는 [src/app](src/app)이며 권장 구조 예시의 pages 폴더를 만들거나 파일을 옮기지 않는다.
현재 사용자 Flow 경로와 비활성 Technical/다른 관점을 구분한다. 아래 실행 명령은 필요한 자격/대상을
확인한 개발 안내이며 ST-001 문서 단계에서 서비스를 기동하지 않는다.
기존 검사 도우미가 존재해도 수집 전 차단을 갖춘 새 공통 안전 entry가 완료됐다는 뜻은 아니다.
전체 ESLint의 기존 실패·실제 로그인 미검증은 위 문서 목록에 보존한다.


Next 16.2.10의 로컬 브라우저 주소는 **http://localhost:3200**이다.

```sh
npm run dev       # next dev -p 3200
npm run build
npm start         # next start -p 3200
```

승인된 실제 실행 전 Next 서버에 `BACKEND_URL=http://localhost:8200`을 명시한다.
개인 API는 같은 origin `/api/auth/...`, `/api/private/...` BFF를 사용한다. 서버 URL이 없으면
503으로 닫고 공개 변수로 fallback하지 않는다. `NEXT_PUBLIC_API_URL`의 비개인 legacy helper
기본값은 `http://localhost:8200`이며 개인 API 우회용이 아니다.

Google의 등록·code 교환 redirect URI는 `http://localhost:3200/api/auth/callback`, 허용 앱
origin은 `http://localhost:3200`이다. 3000·127.0.0.1 alias를 혼용하지 않는다.
Google client secret은 Backend 전용이며 Next public 변수에 넣지 않는다.
프로젝트/client/secret·실제 로그인 등록/설정은 이 문서 작성으로 실행되지 않는다.

SSR은 원문 Cookie를 Backend에 전달하며 중복 판정·세션 폐기·최종 owner 검사는 Backend가
담당한다. 개인 목록/상세/삭제는 no-store이고 목록은 limit/offset 페이지를 제공한다.
새 분석·저장·전체 삭제와 구 직접 AI/HTML proxy는 차단 상태를 유지한다.

[전체 포트·변수 안내](../docs/local_ports.md), [CF-002 구현·검증](../backend/docs/flow_auth_ownership.md).
기존 private 환경 파일을 읽지 않는 검증은 `node scripts/check-local-ports.mjs`로 실행한다.
새 임시 프로젝트와 합성 HTTP 대역만 쓰며 만들었던 자원만 정리한다.
