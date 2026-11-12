# 실제 Technical compiled graph와 thread bridge의 합성 연결

기준 develop `d0aee90754c0de96df27bffdcd236de8718ed0f3`에서 기존 계산/engine 코드를 변경하지 않고 실제 `run_technical_agent → LangGraph → TechnicalEngineBridge → BoundaryRuntime → complete/validate_response`를 연결했다. 이는 공급자·운영 활성화 검증이 아니다.

## 고정 입력과 보호

기존 AI `test_technical_supervisor.py`의 ScriptedLlm·D/W/M OHLCV와 `test_technical_langgraph.py`의 정상 scripted 응답을 그대로 import한다. 두 기존 fixture 파일도 정확한 origin/hash의 읽기 입력이며 전체 AI suite를 수집하지 않는다. 정상, 빈 일봉(data_limited), 짧은 일봉(regime_unavailable)의 세 사례만 단일 Backend 파일에서 수집한다. 결과를 사전 생성하거나 보정하지 않는다.

기존 check_safe의 별도 고정 `technical-graph-self/unit` 선택에 소스 64개(Technical closure·prompt·기존 pure Flow 6파일·기존 fixture 2개·AI lock)와 Backend 검사 입력 5개를 닫힌 목록으로 지정한다. 기존 CF021 collector의 FORBIDDEN/AST-only 규칙과 worker bytes·OS/파일/네트워크/프로세스 guard는 변경하지 않는다. 원본 저장소는 worker 읽기 capability에 없다.

unit은 별도로 승인·설치된 CPython 3.12 arm64의 잠긴 64개 package site를 사용한다. 버전 집합·각 component owner/mode·symlink 거절과 모든 파일(기존 pyc 포함)의 read 전후 identity/nlink/O_NOFOLLOW, 전체 site hash의 전후 일치를 확인한다. 설치 때 확인한 공식 wheel SHA/metadata/native ABI receipt와 이번 site 전후 검사는 다른 증거다. 새 다운로드·설치·원래 Backend site 변경은 없다.

수집 전에 합성 intraday=false·Technical trace=false·LangSmith tracing=false를 설정하고 실제 config의 명시 initialize_runtime을 호출한다. 실제 pipeline/graph를 그 뒤 import하며 reload나 다른 module flag patch를 하지 않는다. LLM/fetcher는 필수 fake DI, cache/trace_sink는 명시 None이다. SDK/Redis/다른 agent/DB import sentinel도 수집 전에 설치한다.

첫 회차는 urllib3 import의 `_has_ipv6`가 `::1:0` bind를 시도하여 guard가 차단했다. 세 계산 결과 자체는 통과했지만 그 회차는 전체 실패로 보존했다. 최종 검사는 의존성 import 동안만 `socket.has_ipv6=False`인 가짜 플랫폼을 명시해 해당 탐색을 예방한다. 네트워크 허용·guard 예외는 추가하지 않았다. 따라서 실제 IPv6 환경 동작은 검증하지 않았다.

## 직접 결과

- 보호 self 2개 통과: exact source/mode와 CF021 경계 보존, metadata symlink의 read 전 거절, pyc 변경 탐지.
- 실제 compiled graph 통합 unit 3개 통과, guard 위반 0. 각 원문·stock name·request/trace ID·UTC as_of와 입력 불변, 상태·차트·coverage를 strict response로 검증했다. 별도 thread dispatch 1회, 명시 fake fetch 1회, 실제 scripted LLM 사용 및 worker 종료·runtime 슬롯 해제를 확인했다.
- source/dependency 전후 provenance와 자기 임시 root 제거를 확인했다. 최초 실패/진단 로그는 최종 성공으로 덮지 않았다.
- 독립 읽기 검토에서 metadata/pyc finding 2건을 보완했고 추가 blocker는 없었다.

실행 입구는 기존과 같은 clean env·절대 `backend/.venv/bin/python -I -S -B backend/scripts/check_safe.py technical-graph-self` 또는 `technical-graph-unit`이다. unit의 `.venv`는 검토된 별도 64-wheel 환경으로 준비된 작업공간에서만 사용한다. self는 graph import/AI 설치 없이 기존 Backend site에서도 실행할 수 있다. CI는 self 한 단계만 추가하며, 실제 compiled graph 3사례의 증거는 별도 설치 환경의 로컬 보호 실행이다.

실제 KIS/OpenAI·환경파일·trace 네트워크·Redis·DB·Google·Frontend, public route와 Backend 저장/usage/Supervisor 새 Technical 실행, 전체 AI main 시작은 검증하지 않았다. 합성 execution_mode와 cutoff 미검증·생성/발행 시각 미보고를 유지한다. 기존 실제 Supervisor의 예약/once/원장과 실제 Flow 보류 상태에는 영향이 없다.
