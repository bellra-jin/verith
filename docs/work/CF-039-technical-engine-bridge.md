# CF039 · Technical 동기 엔진의 비동기 연결

CF036이 완료된 develop `d37b1e9cb7d0f47bc10671f0e9ec1f89d5b50dac`에서 별도 branch로 분리했다.
정확6경로에 기본 비활성 DI bridge, 기존 단일 CF021 unit/loader·bridge pin1개·관련 source 수량과
[계약 추록](../contracts/technical-boundary-v1.md#cf039--기본-비활성-동기-runner-연결)을 추가했다.
실제 기존 graph/agent·계산·config·route/Runtime/adapter·storage/coordinator/usage·Frontend·CI·guard·package/lock은 변경하지 않았다.

sync_runner, LLM client, fetcher는 필수이고 cache/trace_sink도 명시한다. None cache/trace는 미사용이다.
한 작업의 입력 snapshot과 같은 의존성·trace ID·축소한 cooperative Deadline을 실제 별도 thread에 전달한다.
worker 결과/예외를 관측한 뒤 물리 thread 종료와 join을 확인하고, 취소가 있으면 재전파한다.
별도 allocator/queue·일반 retry·강제 thread kill·uncancel·자동 client/환경 탐색은 없다.

기존 Runtime의 shield된 HTTP waiter와 실제 engine task 수명을 구분한다. timeout/즉시 waiter 취소·반복 inner task 취소 뒤에도
worker가 살아 있는 동안 두 번째 요청은 BUSY이고 dispatch는 추가되지 않는다. 종료 뒤 슬롯이 해제되고 다음 정상 호출이 가능하다.
늦은 성공/실패는 이미 종료된 HTTP 응답으로 채택하지 않는다. 무응답 sync 함수는 cooperative 기한만으로 종료시킬 수 없으므로
운영 프로세스 종료나 무응답 worker 강제 회수까지 해결했다고 표현하지 않는다.

## 직접 무키 검증

기존 clean env의 절대 Backend Python `-I -S -B`와 `technical-boundary-self/unit`만 사용했다.
최종 self3·단일 unit208개가 통과했고 guard 위반0·parent exit0·소유 임시 root 제거를 확인했다.
기존175개 회귀는 삭제하지 않았다. 실제 threading.Event로 runner를 hold/release하고 Thread identity·is_alive/join을 확인했다.
loop heartbeat, 입력 snapshot·동일 의존성/trace·기한, 기본 비활성/누락·비동기 callable/만료에서 worker0,
실제 ASGI의 strict 정상/오류와 typed enum/datetime 직렬화, HTTP timeout/BUSY/late 결과, waiter/inner 반복 취소·자기 worker/task 종료를 확인했다.
sleep만으로 thread 종료를 추정하지 않았다. 작은 합성 HTTP 제한은 기존3초를 바꾼 제품 설정이 아니라 검사 주입이다.

첫 unit은203통과·1실패였다. typed model의 JSON-mode가 UTC를 Z로 내보내 기존 fixture의 +00:00 raw binding과 달라진 실패였다.
model의 Python 값에서 표준 datetime.isoformat()/enum.value로 직렬화하도록 보완했고, 요청 표현을 읽어 출력을 덮어쓰지 않는다.
다른 시각 표현의 요청은 계속502가 되는 회귀를 추가한 뒤205개가 통과했다. 독립 검토에서 async complete callable 객체의
사전 거절 누락을 보완하고 runner/LLM/fetcher 객체 회귀를 더해 최종208개가 통과했다. 이전 실패 로그는 별도로 보존한다.

CF021의 기존 AI28개 pin은 그대로이며 bridge 정확1개만 추가해29개다. 기존 고정9개와 CF035 순수 Flow6 origin,
FORBIDDEN/ImportSentinel·AST-only graph 검사·worker/OS/FS/network/env 보호를 유지한다.
이미 pin된 순수 Deadline을 bridge보다 먼저 명시적으로 load하고 CF021/CF031 관련 수량 두 곳만 맞췄다.
실제 graph/config/provider를 새로 import할 권한·새 mode/패키지 설치를 추가하지 않았다.

## 실제 계산과 남은 조건

이번 runner는 고정 합성 출력을 반환하는 주입 함수다. fake OHLCV/LLM으로 실제 LangGraph를 계산한 결과가 아니다.
보호 Backend 환경에는 필요한 langgraph/langchain_core/langsmith/pandas/numpy가 준비되지 않았고 AI 전용 환경도 미준비다.
실제 config import의 dotenv 탐색과 graph의 조건부 intraday KIS fallback도 현재 금지 경계다.
다른 interpreter·raw pytest·새 설치·graph/config stub·guard 완화로 우회하지 않았다.

실제 그래프 검증에는 검증된 dependency provenance, 수집 전 보호를 유지하는 정확 graph import closure와
자동 dotenv/provider fallback을 피하는 명시 조립이 먼저 필요하다. 실제 엔진 품질·KIS/OpenAI·owner 저장/usage와
Supervisor dispatch는 별도 후속이다. service_token이라는 기존 변수명만으로 credential 혼용을 주장하지 않는다.
키/.env·실제 DB·모델/count·신규 발급/예약·설정 활성화는 없으며 기존350m 보수 예약과 소비된 실행 증거는 불변이다.

독립 최종 source 검토·원격 exact-head CI와 게시 결과는 각각 구분한다. 로컬 thread 회귀 통과를 실모델/실제 graph 수용으로 쓰지 않는다.

독립 최종 읽기 검토에서 추가 필수 수정은 없었다. 공개 원형과 기존 테스트/guard 보존, AI28 pin 유지와 bridge1개 추가,
취소/기한/slot·시간 표현의 엄격한 거절 및 self3/unit208 로그를 대조했다. 리뷰 측은 검사를 재실행하지 않았다.
