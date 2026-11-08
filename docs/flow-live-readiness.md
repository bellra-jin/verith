# Flow 실제 연동 전 확인 항목

코드 연결과 합성 검증 이후의 운영 준비 항목이다. 실제 설정 값·키·계정·캐시·DB·공급자·서비스·배포는 확인하거나 활성화하지 않았다. 실행 명령이나 자격 값은 이 문서에 넣지 않는다.

| 항목 | 코드상 전제와 미확인 사항 |
|---|---|
| 서비스 주소 | canonical Frontend3200 → Backend8200 → AI9200. Frontend `BACKEND_URL`, Backend `AI_SERVICE_URL`·`DATABASE_URL`은 각각 다른 연결이다. container의 localhost는 host와 다르며 서비스 내부 주소/포트를 일괄 치환하지 않는다. 실제 주소·접속·자격은 미확인이다. |
| gate·인증 | Frontend/Backend/AI `FLOW_ANALYSIS_ENABLED`, AI `FLOW_ENGINE_EXECUTION_ENABLED`는 기본 닫힘이다. Backend/AI `FLOW_SERVICE_TOKEN`이 일치해야 한다. 운영 HTTP header용으로 printable ASCII32바이트 이상을 준비하는 기준이며 기존 제품 검증을 바꾸지 않는다. 이번에 값을 읽거나 gate를 켜지 않았다. |
| 시작 환경·동시성 | AI gate/token은 dotenv 이전 `os.getenv`로 검사하므로 startup process environment에 필요하다. 표준 `ai/src/main.py`는 다른 agent router도 eager import하며 Flow-only 기동을 보장하지 않는다. 1-slot은 프로세스별이므로 초기 운영 worker1개가 전제다. |
| 공급자·시장자료 | 실제 이름은 `KIS_API_KEY`, `KIS_API_SECRET`, `KIS_BASE_URL`, `OPENAI_API_KEY`다. 현재 모델 상수 `gpt-5.4-mini`의 계정 사용 가능 여부는 미검증이다. KIS 시장자료·안전한 캐시 경로와 계정/시장 접근·호출/비용 경계가 필요하며 실제 키·캐시·시장 상태는 확인하지 않았다. |
| 로그인·입력 | Google Web callback `http://localhost:3200/api/auth/callback`; `AUTH_ORIGINS`·`CORS_ORIGINS`는 canonical `http://localhost:3200`, 명시 로컬 HTTP 설정은 `AUTH_ALLOW_LOCAL_HTTP`다. 엄격 Host·Origin·CSRF를 유지하며8200 callback/IP alias로 완화하지 않는다. 등록된 ASCII6자리 ticker와 새 현재 시각 요청을 사용한다. 요청 context·종목명·후보 날짜·확정 거래일의 기존 binding을 재구현하지 않는다. 요청 시각은 실제 확정 거래일과 다르다. |
| 기한·복구 | Flow120초 / Backend HTTP125초 / BFF130초 / Frontend POST135초. 자동 관측은 최초 deadline과 관측 시작부터 단조120초, 기한 마지막 GET은 최대1회·15초 abort다. 이후 수동 GET은 세션 재검증 뒤 같은 분석을 조회하며 자동 POST·새키·AI호출0이다. result_ready는 동의한 명시 same-key POST로 snapshot 게시만 복구한다. GET은 dispatch/publication이 없지만 만료 bookkeeping을 commit할 수 있다. |
| 실제 수용 증거 | stored만으로 KIS/OpenAI 성공을 주장하지 않는다. captured snapshot의 `observed_calls.openai`와 저장 payload의 `verification.outcome`, `interpretation_meta.source/provider/model`, 해석 유무·gate 결과·확정일을 함께 확인해야 한다. 계수는 시도 관측이며 공급자 성공·실제 청구의 증거가 아니다. fact_only/fallback과 explained/llm을 구분한다. `interpretation_status` 필드는 가정하지 않는다. |

대기 timeout 뒤에도 실제 하위 실행이 끝날 때까지 slot이 유지될 수 있다. 엔진1회는 외부 호출1회나 취소·과금 중단을 뜻하지 않는다. 실제 Google/KIS/OpenAI·원천 수치/해석 품질·자료시점·약관/비용·운영 DB·startup/배포 수용은 별도 미확인이다.

근거: [포트/인증 경계](local_ports.md), [Flow HTTP gate](../ai/src/agents/flow/api/http.py), [실행/호출 관측](../ai/src/agents/flow/application/execution_runtime.py), [KIS 입력](../ai/src/agents/flow/infrastructure/kis_client.py), [모델 상수](../ai/src/agents/flow/config.py), [v1 exporter](../ai/src/agents/flow/api/payload.py), [재무 인수 안내](examples/fundamental-owned-analysis.md).
