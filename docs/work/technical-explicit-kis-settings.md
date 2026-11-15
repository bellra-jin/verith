# Technical 명시 설정·검증 TLS·단일 실제 실행

기준 develop `c33ec8ec5d5ade308ce75568cdbf0883acc1e042`,
branch `fix/technical-explicit-kis-settings`, 별도 worktree `verith-technical-explicit-kis-settings`.
검사 수선 7파일과 분리했다. stage/commit/push/PR/merge는 하지 않았다.

## 후속 무키 수선 · 실제 실행 기록과 분리

새 `fix/technical-invocation-diagnostics` / `verith-technical-invocation-diagnostics`는 최신 develop
`c33ec8ec5d5ade308ce75568cdbf0883acc1e042`에서 분리했다. 앞선 검토된 로컬 12파일을 정확한 해시로
이어받고, 실제 실행에 사용한 worktree·source/once/result/hold는 수정하지 않았다. 게시·머지는 하지 않는다.

실제 요청의 normalize prompt와 model/input projection을 소스에서 재구성해 저장된 두 SHA256과
일치시켰다. 설치된 OpenAI SDK 2.44.0, async factory→sync 작업 스레드, 가짜 자격과 Mock HTTP에서
원래 요청 자체는 통과했다. 합성 count 응답에 Set-Cookie를 넣으면 HTTPX가 Cookie를 저장하고 다음
생성에 붙여, 소유 transport의 헤더 허용 목록이 HTTP_INVALID로 거절한다. SDK의 APIConnectionError
래핑 때문에 기존 record는 SDK_UNKNOWN/entered=false로 남는 것을 무네트워크로 재현했다.
이는 실제 응답의 Set-Cookie를 관측한 증거가 아니므로 실제 원인을 확정하지 않는다.

새 strict 소유 client는 stdlib CookieJar의 비수용 정책으로 응답 쿠키를 저장하지 않으며,
쿠키가 주입돼도 송신 전에 닫힌다. 기존 Cookie 헤더 거절은 유지한다. 소유 phase에서 발생한
기존 allowlist 고정 오류만 SDK 래핑 뒤에도 보존하며 원문 예외/헤더/응답을 공개하지 않는다.
새 SQL 필드·오류 enum·회계/환급·재시도 권한을 추가하지 않는다. legacy adapter도 유지한다.
실제 SDK+가짜 count Set-Cookie에서 수정 후 count/generation이 쿠키 없이 통과하며,
별도 금지 헤더 주입은 생성 inner HTTP 0과 HTTP_INVALID/hold 보존을 확인했다.

명시 KIS 멀티프레임 함수는 한 invocation의 함수 지역 토큰을 D/W/M 전체에 재사용한다.
서로 다른 invocation은 공유하지 않으며 전역/디스크 캐시·자동 재인증은 추가하지 않는다.
공식 샘플도 유효 토큰을 먼저 재사용한다.
[한국투자 공식 auth 샘플](https://github.com/koreainvestment/open-trading-api/blob/main/examples_user/kis_auth.py).
이 사실만으로 실제 두 번째 인증 403이 중복 발급 제한이었다고 확정하지 않는다.
명시 분기의 auth/market HTTP·API·network·잘못된 응답은 제한된 비밀 없는 오류로 처리한다.
기본 환경/cache 경로와 기존 market retry 상한은 유지한다.

기존 실제 KIS 감사는 헤더 단계에서 500을 기록했다. 소스와 순차 감사상 500 뒤 조회 지속은
rate-limit marker(EGW00201) 분기 또는 헤더 이후 본문 수신 RequestError의 재시도 경로와 일치한다.
비재시도성 500 즉시 실패 경로는 아니지만, 실제 marker/msg_cd/body는 보존되지 않아 양자를 구분할 수 없다.

최종 보호 runtime unit **273**, self **5**, graph 보호 mode **25** 통과(기존 compiled graph/합성 23 + 실제 SDK wire 2),
guard 위반 **0**·자기 임시 root 정리. 기존 설치 dependency 7,421개 snapshot 전후 동일,
검사 후 Backend venv symlink 복원을 확인했다. 가짜 응답의 정상/음성·비밀 sentinel·쿠키 저장 거절,
KIS D/W/M token1·market10 및 최대재시도 market30, 별도 invocation 분리와 추가 인증0을 확인했다.
실제 SDK 진단도 네트워크·credential 파일 read·child 시작을 차단한 별도 무키 프로세스다.
실제 SDK의 Set-Cookie 성공과 금지 Cookie 헤더 실패는 기존 `test_technical_compiled_bridge.py`의
정식 두 회귀로도 포함했다. pinned 2.44.0과 실제 SDK request serialization·cookie 처리를 사용하고
소유 inner I/O만 MockTransport로 바꾼다. 고정 테스트의 해당 thread 안에서만 정확 SDK package
origin을 확인해 import하고 종료 시 SDK module을 해제한다. 다른 금지 import와 OS guard는 유지한다.
처음 실행은 25개 assertion 통과에도 SDK 플랫폼 탐색의 쓰기 시도 2건이 보호에 걸려 전체 실패였다.
SDK 모듈 안의 platform 헤더 메타데이터만 고정 합성 값으로 제공해 native 탐색을 방지한 뒤,
25개·guard0와 원본/사본·7421 dependency 전후 동일성 및 자기 정리를 확인했다.
표준 platform·OS 보호·인증·실제 request/response 검증을 완화하지 않았다. native 플랫폼 탐색 수용의
증거는 아니며 새 테스트 mode/프레임워크/설치·운영 SDK 활성화를 만들지 않았다.

새 실제 OpenAI/KIS 호출·키 접근·DB·예약·설치·운영 설정·게시·머지는 **0**이다.
이전 실제 run은 unknown, Technical $0.20와 Supervisor $0.50 보수 hold 합계 $0.70을 유지한다.
수정 후 실제 공급자 성공·보고서 저장은 미검증이며 실제 once를 재사용하지 않는다.

## 현재 결과 · 2026-11-13

이 변경은 로컬만 보존하며 commit/push/PR/merge하지 않았다. 검사 수선 PR #73과 분리한다.
기존 PR #61의 KIS host 제한은 여전히 보류다.

명시 RuntimeSettings를 받은 초기화는 dotenv 탐색을 생략하고, 기본 호출·초기화 latch·late-import 차단은
유지한다. 같은 invocation의 KIS stopped Event를 실제 runtime 취소의 첫 관측에서 닫는다.
Backend AIClient와 AI authority client는 Technical 전용 opt-in으로 검증하는 TLS context를 복사·고정하고,
Supervisor 실제 dependency도 server-only app state의 context를 전달한다. 기본 TLS/Flow/Fundamental과
인증·동의·SQL·소유권 경계는 그대로다. OS 신뢰 저장소 변경, verify=False, 임의 transport 확대는 없다.

최종 필요한 무키 검사는 runtime unit 261, admission unit 283, compiled graph unit 23,
runtime self 5가 통과했다. guard 위반 0과 자기 임시 root 정리를 확인했다.
실제 graph 검사는 합성 SDK/OHLCV이며 실제 공급자 검증과 구분한다. 취소 검사는 이미 송신된 네 합성 HTTP를
기준으로 취소 후 증가 0을 확인한다.

실제 한 건은 별도 Backend/AI 환경과 소유 임시 CA의 양방향 검증 HTTPS를 사용했다. 실제 SQL 인증 세션,
CSRF/Origin, CF054 prepare/confirm → 단일 durable start → 실제 graph 경로를 사용했다.
Google 로그인·운영 배포·사용자 영구 보관함의 검증은 아니다.

첫 사전검증은 종목 자동 승격을 가정한 caller 준비 assertion에서 종료했다. prepare HTTP 200 이후
응답 전체를 보존하지 않아 실패 필드의 실제 값은 남아 있지 않다. confirm/once/키/API/SQL 예약은 모두 0이며
원 기록을 보존했다. 기존 CF054 계약은 현대건설 이름만 자동 확정하지 않는다. 승인된 현대건설 종목명을
명시 stock 답변으로 전달한 정상 경로에서 ready·000720·Technical·3m/1y/5y 고정 범위를 확인했다.

이후 confirm은 정확 한 번이며 실제 실행은 **완료되지 않았다**.

- OpenAI 공식 count 1회 응답·검증, input count 876. 생성 record는 entered=false,
  response_received=false, usage=null, reason=SDK_UNKNOWN이다.
- 소유 transport는 검증과 generation 소비 표시 후에만 inner HTTP를 호출하며, 해당 표시를 되돌리지 않는다.
  따라서 이 기록에서는 생성 요청이 소유 inner 전송 경계를 통과하지 않았다. 원본 SDK 예외/traceback은
  저장하지 않아 정확 발생 지점은 미확인이다. 설치 SDK 2.44.0과 가짜 inner HTTP의 무키 진단은
  count/generation 둘 다 수용돼 같은 실패를 재현하지 못했다.
- KIS token 2회(200, 403), market GET 8회(200 다섯·500 세 번), 계좌·주문 0.
  세부 provider 오류 body/code는 보존하지 않아 403/500의 구체 사유는 단정하지 않는다.
- SQL run은 unknown, 보고서/snapshot 0. 본인 Supervisor GET 200은 unknown 상태 조회의 성공이다.
  prepare 재요청은 신규 admission을 닫은 뒤 403이며 추가 실행하지 않았다.
- worker 종료 뒤 같은 async 소유 문맥에서 최종 회계를 다시 확인해 usage evidence를 보존했다.
  Technical $0.20 전액 hold와 기존 Supervisor $0.50을 별도로 유지한다. 합계 $0.70이며
  count 876은 생성 usage/확정 청구액이 아니다. KIS 이용료도 미확인이다.
- source 508개 불변, exact Backend/AI PID 부재·소유 컨테이너 부재·임시 HOME/CA/key 정리와
  canonical lock 해제를 독립 확인했다. 실제 once/회계/실패 기록은 보존했고 자동 재실행·예약 해제는 없다.

실제 실행 파일과 raw 읽기 결과·once·회계는 비공개 전용 checkpoint에 보존하며 게시 대상에 넣지 않는다.
로그 stage 이름에 storage_confirmed가 포함돼도 success=false/report0인 실제 결과가 권위다.
실제 Technical 저장/전체 통합은 미완료이므로 재무 통합 완료나 성공으로 확대하지 않는다.

## 아래는 실제 실행 전 준비 시점의 이력

## 구현·검증 완료

`kis_client.py`의 기존 D/W/M 조회에 명시 `KISSettings` 인자를 전달한다.
이 분기는 dotenv 탐색·전역 token cache 읽기/쓰기를 하지 않는다. 한 timeframe의 모든 청크는
그 호출이 발급한 token 하나를 사용한다. 기본 호출의 환경 설정·캐시는 유지한다.
잘못된 타입/빈 자격/제어문자·HTTP/userinfo/path/query/fragment/port0는 고정 오류로 닫는다.
주입 client가 없으면 이 명시 분기의 자체 client는 trust_env=False·follow_redirects=False다.
별도 `kis_request_gate`가 caller의 정확한 origin·종목·token/market 경로와 호출 상한을 송신 직전 검사한다.
취소 Event·원 절대기한·네 timeout 최소값을 적용하고 한 번 소비한 전송을 환급하지 않는다.
클라이언트 자체의 TLS 검증·proxy/redirect/transport retry 차단은 caller 책임이다. #61은 보류 그대로다.

기존 `technical-runtime-unit`에 닫힌 AST·최소 builtins·MockTransport 회귀를 추가했다.
KIS 모듈을 import하지 않고 정확 source copy/pin 한 개만 추가했다. 실제 pure OHLCV 모델을 사용한다.
기존 stdlib datetime이 요구하는 `_strptime`/`time` 조회만 고정 lookup으로 제공한다.

- runtime unit **254/254**, guard 위반 0, 자기 임시 root 제거.
- runtime self **5/5**, exact pin·사본/선택/인접 소스 거절 확인, 자기 임시 root 제거.
- 합성 정상 D/W/M: token 3·market GET 5+4+1=10.
- 각 청크 429 두 번 후 성공: token 3·market GET 15+12+3=30.
- 환경 loader 0, 기존 token cache 불변, 잘못된 설정의 HTTP 0.
- hook의 타 origin/port·계좌/주문·타종목·초과 호출 거절, 만료/취소/NaN 뒤 추가 전송0.
- request 생성 뒤 남은 시간이 1.25초로 줄면 connect/read/pool≤1.25, 기존 write0.5 유지.
  이는 실제 TLS/네트워크 수용이 아닌 MockTransport 검증이다.
- 실제 자격/env·OpenAI/KIS·DB·설치·운영 활성화·신규 예약 모두 0.

변경은 KIS client, check_safe의 정확 readonly pin 추가, 기존 runtime unit/self 검사와 이 기록이다.
기존 실행기/OS guard·graph/SQL·한도 숫자는 변경하지 않았다.

## 실제 한 건의 비용 근거와 남은 진입 조건

고정 모델 `gpt-5.4-mini-2026-03-17`, service_tier=`default`가 전제다.
현재 공식 모델 문서는 입력 $0.75/M·출력 $4.50/M이며 default는 표준 가격/성능이다.
[모델](https://developers.openai.com/api/docs/models/gpt-5.4-mini),
[service tier](https://developers.openai.com/api/reference/resources/responses/methods/create).

입력32768/출력4096·최대4회면 생성 상한은 $0.172032,
지역처리10% 여유를 포함하면 $0.1892352다.
[지역처리 가격](https://developers.openai.com/api/docs/pricing).
공식 입력 계수 API는 무료이며 생성 요청은 별도 과금한다.
[무료 계수 근거](https://help.openai.com/en/articles/4936856-understanding-and-counting-tokens).
이는 해당 모델/정책/caps를 실제 Configuration에 일치 설치했을 때의 계산이며 청구 확정액이 아니다.
신규 보수 예약 최대 $0.20·기존 Supervisor $0.50 별도 보존·합계 $0.70이다. KIS 요금은 미확인이다.

실제 실행 준비 완료로 표시하지 않는다. 다음이 실제 송신 전에 필요하다.

1. 승인된 정확 KIS origin과 일회 소유 client의 TLS/proxy/redirect/transport retry0 고정.
2. 새 hook에 실제 invocation의 deadline/Event를 연결하고 소유 client의 TLS/proxy/redirect/retry0를 고정.
   hook만 구현했다는 사실은 실제 runtime 취소와 연결됐다는 증거가 아니다.
3. 원래 AI 자격 소스에서 필요한 네 필드만 인증 목적으로 공급하는 명시 supplier와
   실제 Backend/AI origin·서로 다른 service/authority token·동일 policy/counter/caps 결합.
4. Verith 소유 DB·한 프로세스·한 key, 신규 admission 한 건 후 닫기, 불명 hold/usage 보존과
   자기 자원 정리. 기존 CF054 prepare/confirm→CF053→CF050 경로를 유지한다.

현재 runtime 설치/실행·장기 배포·운영 설정 변경은 하지 않았다. 새 일반 실행기/원장이나
protected synthetic 입구의 live 전환으로 이 조건을 우회하지 않는다.

## 분리 runtime의 구체적인 미완료 경계

기존 Backend site에는 SQLAlchemy/asyncpg/Alembic/Authlib가 있고 승인64 site에는 graph/OpenAI가 있다.
서로 필요한 상대 의존성이 없으며 임의 결합/추가 설치는 하지 않았다. 단일 AI worker와 Backend를
별도 환경으로 유지해야 한다. 또한 `initialize_runtime()`는 flags를 줘도 `_load_env_file()`을 호출하므로
명시 flags snapshot을 환경 탐색 없이 주입하는 정상 경계가 아직 없다. 전역 patch로 이를 열지 않는다.

`ExecutionAuthorityClient`는 주입 transport를 정확 ASGITransport만 허용하고 production은
transport=None의 기본 인증 TLS다. 로컬의 별도 AI worker에 소유 임시 CA를 신뢰시키는 정상 주입은
현재 지원되지 않는다. ASGI/IPC proxy로 실제 TLS 연결을 한 것처럼 처리하거나 공개 인증 검증을
완화하지 않았다. 이 초기화/전용 TLS 신뢰 경계의 최소 제품 변경과 검토 또는 실제 제공된 승인 대상이
확정되기 전에는 자격 읽기·once/예약·DB/child·provider 실행을 시작하지 않는다.
