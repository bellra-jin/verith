# CF051 · 공식 입력 계수와 송신 전 pair 소비

정본 v1.1 SHA `18cc61ed3f4ea07318b49dc4b580cb03c1acf57d106a2137898c30d918458857`, 기준 develop `8b580613ce1990a437b586200dd775327cb0f42e`(CF050 PR68 병합)의 전용 `feat/technical-count-pairs`이며 정확6파일이다. CF050의 저장/coordinator·기존 WIP·실제 자료·$0.50 hold·PR61 HOLD·Frontend/News/준영 AI는 변경하지 않는다.

## 제품 결과

원 요청 budget에서 count 전 ordinal과 full worst-case hold를 소비한다. 같은 pair의 count/generation 진입을 각각 한 번 선형화하고 I/O 동안 lock을 풀며, 실패 count·unknown·취소·기한 만료에도 pair/hold를 보존하고 후속 송신을 닫는다. 영수증은 budget 자체 issuer와 ordinal·원 prompt/projection/request hash에 결합한다. snapshot은 count 진입/응답/검증/입력 토큰과 generation 진입/usage를 분리하며 원문은 영수증에 보관하지 않는다. CF049의 count 뒤 소비만 이 계약에 맞춰 교체했고 legacy/default counter unavailable은 유지했다.

명시 `official_count_openai_client`가 공식 SDK/HTTP client/transport를 직접 소유한다. 공식 streaming input_tokens.count의 bounded raw JSON을 직접 검사하고 같은 pair만 stream=False generation에 보낸다. 소유 transport가 실제 inner 요청 전에 공식 HTTPS/443/path·무 query/userinfo·header/JSON·SDK identity·retry0와 phase 권한을 확인한다. TLS verify/trust_env=False/proxy 없음·redirect 없음으로 구성하고 request/count/generation wire cap을 각각 필수로 받는다(2MiB 이하). non-200은 SDK의 error body read 전에 닫으며 200은 SDK 아래 stream의 encoding/누적 크기/length/기한을 검사한다. 네 종류 HTTP timeout은 실제 송신 직전 최신 잔여 이하로 줄인다.

명시 credential/base와 보조 SDK 인자로 fallback을 막고 OPENAI_CUSTOM_HEADERS presence·현재 effective DEBUG를 검사한다. 다른 SDK/Azure 전역이나 환경 key/model의 존재 자체는 거절 사유가 아니다. 실제 환경을 읽어 확인하지 않았으며 합성 mapping/constructor로 검증했다. count 응답만 닫고 bundle은 run 소유자가 close한다. close는 미진입 phase를 막고 실제 작업 중 자기 자원 정리를 미루며, 정리 예외가 원 오류/취소를 덮지 않는다. 다른 client/mount를 닫지 않는다.

## 검증과 독립 검토

기존 `technical-runtime-self/unit`과 동일 CF040 선택 AST·입력5개·순수 Flow origin6개를 사용한다. 실제 제품 factory/transport/stream/counter/budget/complete를 합성 SDK/HTTP constructors·context manager/bytes·통제 시간으로 실행한다. Request/Response/stream protocol은 Backend의 기존 HTTPX이며 실제 SDK import·socket/TLS·환경파일·DB·설치는0이다. 새 mode/runner/guard/CI 변경은 없다.

집중 회귀는 마지막 pair 경쟁/송신 상한, count 실패·취소/다른 ordinal 영수증 거절, 의미/SDK/HTTP identity 변조, 직접 SDK/counter와 중복 phase 차단, non-200 선행 close·분할/크기/length/encoding·strict raw count JSON, count 후 기한·송신 timeout 축소, usage 우선 보존, 부분 생성/종료·지연 정리/원 취소·자기 resource 정리 및 원문/비밀 비노출을 확인한다. 첫 unit의 SDK wrapper 교체 허용을 발견해 실제 adapter와 소유 SDK identity를 결합했고, 독립 리뷰의 close-before-entry와 cleanup masking을 보완했다. 기존 raw reason·strict/legacy 회귀와 이전 실패 로그는 보존한다.

최종 보호 self5/unit232 통과, guard0·자기 임시 root 제거를 확인했다. 최종 독립 읽기 리뷰에서 blocker0이며 제품 SHA/pin `d497c65d08cf270c95a640c7e7b323a03ee074a5a040c9774ebd2659e644e0dc`가 일치한다. 검토 후 제품은 동결했고 이 결과 문장만 추가했다. exact-source manifest와 원격 head CI/게시 결과는 실제 실행 증거에 따라 별도로 대조한다. 단위의 합성 SDK가 실제 SDK constructor/네트워크 수용을 입증하지 않으며 소유 SDK/HTTP bundle 생성은 이번 검사에서 가짜다.

## 남은 경계

공식 계수의 명시 opt-in 제품 경로와 로컬 pair gate가 완료 대상이다. free-count/모델·tier·공식 가격과 provenance의 운영 검토·유효 질문/최대액/승인·credential 공급·CF048 durable 송신 승인/정산·실제 engine/Backend/Supervisor 실행 조립은 미완료다. 최대4 pair(최대8 POST)는 새 실행권이 아니며 이번 실제 OpenAI/KIS·새 예약·운영 활성화는0이다. 입력 token receipt의 model은 요청 binding이고 실제 청구/독립 모델 보고가 아니다. HTTP timeout 축소는 동기 worker hard-kill/전체 wall-time 보장이 아니다. 승인된 게시/정상 병합 마감은 2026-11-12 21:00 UTC이며 게시·병합 직전 준영 PR/최신 develop/공통 계약 의존성을 확인한다.
