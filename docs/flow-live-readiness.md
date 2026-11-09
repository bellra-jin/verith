# Flow 실제 연동 전 확인 항목

코드상 운영 전제와 CF-017 단일 종목 실제 검증 범위를 구분한다. 별도 실행 담당이 Google 로그인·실제 KIS/OpenAI 분석·저장/재조회·UI 삭제/404·임시 자료와 자원 정리를 완료했고 독립 artifact 대조 결과를 전달받았다. 개발 측 실제 환경 재실행이나 운영 배포 전체 수용은 아니다. 실행 자격 값·개인 계정·원시 증거·운영 식별자는 이 문서에 넣지 않는다.

| 항목 | 코드상 전제·확인 범위·남은 조건 |
|---|---|
| 서비스 주소 | canonical Frontend3200 → Backend8200 → AI9200. Frontend `BACKEND_URL`, Backend `AI_SERVICE_URL`·`DATABASE_URL`은 각각 다른 연결이다. container의 localhost는 host와 다르며 서비스 내부 주소/포트를 일괄 치환하지 않는다. 별도 격리 검증은 이 canonical 경로를 사용했으며 최종 세 포트 listener0을 확인했다. 운영 환경 연결/자격은 별도다. |
| gate·인증 | Frontend/Backend/AI `FLOW_ANALYSIS_ENABLED`, AI `FLOW_ENGINE_EXECUTION_ENABLED`는 기본 닫힘이다. Backend/AI `FLOW_SERVICE_TOKEN`이 일치해야 한다. 운영 HTTP header용으로 printable ASCII32바이트 이상을 준비하는 기준이며 기존 제품 검증을 바꾸지 않는다. 개발 측 합성 검사와 별도 실제 실행을 구분하며 실제 설정 값은 공유하지 않는다. |
| 시작 환경·동시성 | AI gate/token은 dotenv 이전 `os.getenv`로 검사하므로 startup process environment에 필요하다. 표준 `ai/src/main.py`는 다른 agent router도 eager import하며 Flow-only 기동을 보장하지 않는다. 1-slot은 프로세스별이므로 초기 운영 worker1개가 전제다. |
| 공급자·시장자료 | 실제 이름은 `KIS_API_KEY`, `KIS_API_SECRET`, `KIS_BASE_URL`, `OPENAI_API_KEY`다. 모델 `gpt-5.4-mini`는 별도 단일 종목 실제 호출에서 응답과 표시를 확인했다. 스모크와 브라우저 회차는 각각 KIS token1/data2·OpenAI1회였으며 기존 사용자 캐시는 재사용하지 않았다. 운영 계정/시장 범위·새 실행의 호출/비용 조건은 별도다. |
| 로그인·입력 | Google Web callback `http://localhost:3200/api/auth/callback`; `AUTH_ORIGINS`·`CORS_ORIGINS`는 canonical `http://localhost:3200`, 명시 로컬 HTTP 설정은 `AUTH_ALLOW_LOCAL_HTTP`다. 엄격 Host·Origin·CSRF를 유지하며8200 callback/IP alias로 완화하지 않는다. 등록된 ASCII6자리 ticker와 새 현재 시각 요청을 사용한다. 요청 context·종목명·후보 날짜·확정 거래일의 기존 binding을 재구현하지 않는다. 요청 시각은 실제 확정 거래일과 다르다. |
| 기한·복구 | Flow120초 / Backend HTTP125초 / BFF130초 / Frontend POST135초. 자동 관측은 최초 deadline과 관측 시작부터 단조120초, 기한 마지막 GET은 최대1회·15초 abort다. 이후 수동 GET은 세션 재검증 뒤 같은 분석을 조회하며 자동 POST·새키·AI호출0이다. result_ready는 동의한 명시 same-key POST로 snapshot 게시만 복구한다. GET은 dispatch/publication이 없지만 만료 bookkeeping을 commit할 수 있다. |
| 실제 수용 증거 | stored만으로 KIS/OpenAI 성공을 주장하지 않는다. captured snapshot의 `observed_calls.openai`와 저장 payload의 `verification.outcome`, `interpretation_meta.source/provider/model`, 해석 유무·gate 결과·확정일을 함께 확인해야 한다. 계수는 시도 관측이며 공급자 성공·실제 청구의 증거가 아니다. fact_only/fallback과 explained/llm을 구분한다. `interpretation_status` 필드는 가정하지 않는다. |

대기 timeout 뒤에도 실제 하위 실행이 끝날 때까지 slot이 유지될 수 있다. 엔진1회는 외부 호출1회나 취소·과금 중단을 뜻하지 않는다. Google/KIS/OpenAI의 단일 실제 연결은 아래 범위로 확인했다. 원천 수치/해석 품질 전반·모든 자료시점·약관/실제 청구·운영 DB·startup/배포 전체 수용은 별도다.

근거: [포트/인증 경계](local_ports.md), [Flow HTTP gate](../ai/src/agents/flow/api/http.py), [실행/호출 관측](../ai/src/agents/flow/application/execution_runtime.py), [KIS 입력](../ai/src/agents/flow/infrastructure/kis_client.py), [모델 상수](../ai/src/agents/flow/config.py), [v1 exporter](../ai/src/agents/flow/api/payload.py), [재무 인수 안내](examples/fundamental-owned-analysis.md).

## 공급자 실행 전 남은 경계 (CF-017)

오류 분류의 합성 집중 검사와 별도 실제 연동 결과를 구분한다. 실제 Google 코드 교환/OIDC 검증과 테스트 DB의 계정·identity·session 저장, 로그인 보관함 UI를 확인했다. 이후 삼성전자005930 분석은 UI stored, report1/run1, 같은 보고서 GET/재조회 내용 일치, 확정일2026-11-06·입력/데이터/해석 검증 통과를 확인했다. UI 삭제 후 목록0·DB report0·삭제 URL404/본문 미노출, 테스트 계정/세션/분석 기록과 자기 PG tmpfs·서비스 자원 정리를 확인했다. 일반 브라우저 프로필·기존 DB/리포트·다른 프로젝트는 보존했다. 이 결과는 실행·독립 증거 검토 측의 전달이며 개발 측 실제 환경 재실행은 아니다.

- 수신처는 KIS `https://openapi.koreainvestment.com:9443`와 OpenAI `https://api.openai.com`의 확인된 작업 path로 고정해야 한다. KIS token POST와 투자자 수급/일별 시세 GET만 대상으로 하며 주문·계좌 조회는 포함하지 않는다. base URL·SDK override·환경 proxy·redirect가 다른 수신처로 자격을 보내지 못하도록 실제 실행 경로에서 입증해야 한다. 현재 제품의 일반 환경 설정만으로 이 경계가 보장된다고 쓰지 않는다.
- 한 종목 분석도 정상 자료 GET2회, 유량 제어를 포함하면 최대4회이며 token 발급·캐시·재사용 범위는 별도다. 실행 전용 메모리/자기 임시 캐시만 사용하고 기존 사용자 캐시를 읽거나 갱신하지 않는다.
- OpenAI는 검증 fact 메뉴와 고정 prompt의 실제 입력량을 확인해야 한다. 모델의 입력 단가와 출력 cap만으로 전체 비용 상한이 보장되지는 않는다. 최대3회·각 출력1000·추가 SDK retry0을 유지하고, 매 요청 입력량과 전체 예산을 전송 전에 제한하는 별도 실행 준비가 필요하다. 현재 제품에 총비용 hard cap이 있다고 주장하지 않는다.
- Flow-only router 조립과 실제 graph의 잠금 의존성, 새 자기 PG·canonical3200→8200→9200·깨끗한 browser context의 소유/정리·인증을 확인해야 한다. 초기 Docker socket 접근 차단은 당시 이력이며 개발 측이 다른 socket/보호 완화로 우회하지 않았다. 별도 실행의 실제 브라우저/DB 증거와 합성 ASGI 검사는 구분한다. 향후 Google 코드/secret 교환과 실제 자격 전송은 매 실행의 별도 조건을 확인한다.


실제 사용량은 독립 스모크 input1914/output320·추정 $0.0028755, 브라우저 input1914/output256·추정 $0.0025875로 누적 OpenAI2회·추정 **$0.005463**이다. 검증 한도3회/$0.10 이내 관측이며 실제 청구서나 제품 총비용 hard cap의 증거가 아니다. 첫 브라우저 시도는 harness의 bytes localhost 처리에서 AI 연결 전 중단돼 graph·추가 공급자 호출/비용0을 확인했다. 좁은 ASCII 정규화 보완 뒤 새 환경에서는 자격 사용 전 HTTPX localhost9200 health200을 확인했다. 제품 source는 변경하지 않았다.

원요청 `deleted` enum의 UI 직접 확인은 못 했으며 실제 보고서 삭제/404와 구분한다. SessionControls 삭제 확인창은 필수 계약 위반으로 단정하지 않고 UX 개선 후보로 남긴다. 단일 종목·격리 시나리오를 모든 종목/운영 배포로 확대하지 않는다. 원격 최신 PR head 및 Ready 이벤트 CI, PR 게시/병합은 사용자 실행 후 별도 확인할 단계다.
