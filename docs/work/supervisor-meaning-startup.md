# Supervisor meaning runtime startup 연결

기준 develop `feab0a9a6fcc5dba9d0776d74fd3aad988d87955`에서 별도
`fix/supervisor-meaning-startup` 작업으로 분리했다. 기존 main은 runtime을 None으로 두고
명시 설치 함수를 실제 startup에서 호출하지 않았다. lifespan에서 기존 옵션/설치/Gateway를
재사용하도록 연결했으며 새 회계·예산·서비스·검사 모드는 만들지 않았다.

변경은 AI main/factory, 기존 meaning unit/self, 해당 두 source pin, 기존 core 계약과 이 기록의
7파일이다. 기본 비활성이며 명시 enable/origin/별도 service token/counter snapshot이 모두
유효해야 한다. startup에서 key를 읽지 않고 기존 count ACK 이후 supplier만 process key
한 값을 읽는다. env 파일·서비스 설정·설치·운영 계정/한도/가격/계수 근거 발급은 수행하지 않았다.

검증은 기존 보호 meaning-self/unit 입구만 사용한다. 실제 factory를 수집 전 보호 안에서
다시 로드해 env/file 조회 부재를 확인하고, 실제 main의 선택된 lifespan/설치/라우터 조립 함수를
격리 FastAPI에 실행한다. 실제 core route/Gateway/budget client와 합성 ASGI phase 서버 및
provider MockTransport로 count ACK→key→count→generation→settle 순서를 확인한다.
이는 전체 main import나 실제 uvicorn/Backend/DB/provider 실행 증거가 아니다.

초기 self 실행은 새 worktree가 아닌 다른 경로의 interpreter를 지정해 실행 전
`unexpected Python interpreter`로 닫혔다. 기존 dependency site를 가리키는 새 worktree의
`.venv` symlink를 사용한 정확 입구로 바로잡았으며 보호/허용 범위를 바꾸지 않았다.

기존 B6R 소비 기록과 보수 예약400m·False 및 모든 다른 WIP는 불변이다. 이번 수정으로
새 발급/실제 count·generation 또는 재시도 권한을 만들지 않는다. 전체 main startup은 다른
서비스 의존성/import 때문에 이번 제한된 보호 collection에서 실행하지 않았고, 실제 배포
환경 설정·키 공급·운영 계정/정책·Supervisor→Flow 전체 인수는 미완료다.

최종 보호 meaning-self 7개와 meaning-unit 299개가 통과했고 guard 위반0·자기 사본 제거를
확인했다. 최초 unit의 실패3건은 include_router 이후 FastAPI의 lifespan wrapper와 원 함수를
동일 객체로 잘못 가정한 검사 보조 코드였다. 두 번째 unit의 실패1건은 정상 승인 거절의
기존 counter_unavailable을 unavailable로 기대한 단언이었다. 실제 context의 runtime 설치/해제,
정상 receipt+승인 False의 key0, malformed 설정과 count ACK 이후 실제 합성 순서는 유지했다.
독립 읽기 검토에서 발견한 잘못된 port 구성도 엄격히 거절하도록 보완했다.

독립 최종 코드 검토에 남은 blocker는 없다. 원격 exact-head CI/Ready PR·정상 merge 및 실제
배포/품질 결과는 이 로컬 합성 검사와 별도이며, 게시 결과는 PR과 비공개 인계에 기록한다.
