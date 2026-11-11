# CF034 · Supervisor 준비 POST의 Frontend 기한 정합성

기준은 PR37 병합 develop `0b993fdaa64873dca038c7e7da1f38c46b7c1d08`,
branch는 `fix/supervisor-preparation-deadline`이다. 정본 v1.0 SHA-256
`069d09a4fbcedd096acdc16e881baae4c7b0c7d665cf1b3e715807b8827705ae`의
정확 9파일 범위를 따른다. 기존 worktree/WIP·CF029 변경과 거절 행동은 보존했다.

## 문제와 수정

Backend preparation은 75초인데 BFF와 Conversation action은 준비를 16초에
취소했다. 단순 상수 치환은 body·인증·GET 복구까지 늘리므로 실제 POST만
별도로 제한한다. 제품 변경은 다음 3파일이다.

- `session-proxy.ts`: 정확 preparations POST는 진입부터 95초 전체와 16초 body
  신호를 분리한다. body 만료는 upstream 0·504이고 응답 stream도 전체 기한으로 닫는다.
- `supervisor-session.tsx`: 고정 body/ID·새 child 조건으로 실제 method를 먼저
  선택한다. POST 130초·ID GET 16초·confirm 145초를 유지하며 method drift는
  송신 전에 거절한다. abort를 결과 채택 검사에 포함하고 timeout 안내와 자기
  pending만 정리한다. 이전 finally는 새 ticket의 잠금을 해제하지 못한다.
- `supervisor-request.ts`: POST 전후 session fetch/JSON 각각 15초와 outer
  취소를 결합한다. 늦은 인증/owner 변경과 hash 중 취소 결과를 거절한다.
  action의 storage hash 뒤 현재 context를 확인해 stale 저장을 차단한다.

기존 GET/DELETE·legacy prepare·재인증·같은 key 복구·동의·owner/URL/generation/
visibility·focus 경계는 유지한다. shared Flow fetchSession과 Backend/AI는 변경하지 않는다.
새 caller sibling은 `verith-supervisor-preparation-deadline/frontend` 한 곳만
추가했다. 기존 모든 sibling·유일 dependency root·package/lock pin·trusted
identity·source-copy·pre/post provenance·worker/guard는 그대로다.

## 직접 검증

clean env와 검증한 절대 Node에서 기존 보호 `core-unit`, `core-type`,
`core-lint`만 실행했다. 명령 형식은 다음과 같고 실제 경로/명령·로그 hash는
저장소 밖 이번 전용 인계서에 남겼다. raw node-test나 보호 해제는 하지 않았다.

```sh
env -i LANG=en_US.UTF-8 TZ=UTC OPENSSL_CONF=/dev/null \
  <verified absolute Node> scripts/check-local-ports.mjs core-unit
```

| 검사 | 직접 결과 |
|---|---|
| core-unit | 고정 4파일 204개 통과: core 119 / BFF 18 / config 6 / tooling 61 |
| core-type | 같은 제품 소스 hash에서 exit 0 |
| core-lint | 최종 테스트 보강 뒤 exit 0, 오류/경고 없음 |
| source/의존성 후검사 | 통과, 자기 임시 root 제거 |
| guard/worker | 불변, unexpected violations 0·diagnostic failures 0 |

tooling의 의도된 부정 검사는 expected negatives로 구분하며 금지 접근 성공으로
해석하지 않는다. 첫 unit 로그에는 100통과/12실패 합계와 마지막 tail만 남았다.
소스 대조에서 추출 action의 VM에 HTMLElement가 빠져 있음을 확인했고, 제품
코드를 바꾸지 않고 그 합성 class 한 항목만 추가했다. 그 뒤 197개가 통과했다.
개별 실패 exception은 로그에 보존되지 않아 12건 각각을 재구성할 수는 없다.
최종 method/인증/복구 회귀를 추가해 204개가 통과했다. 실패 로그는 보존하며
통과 수에 합산하지 않는다. type 결과 뒤 제품 소스는 변경하지 않았다.

실제 BFF 함수/route loader로 16초 초과 정상 응답, body 16초 upstream0·504,
전체95초 upstream/decoded stream 종료와 CSRF/byte/header 보호를 확인했다.
실제 action 추출로 새 POST/child POST/ID GET 선택, timer 비갱신, 130초 abort,
같은 key/body의 명시 retry·자동 POST0, hash/storage 중 취소 및 늦은 응답의
채택0·이전 finally의 새 잠금 해제0을 확인했다. 실제 preparationRequest의
전후 인증15초·decode 지연·이미 취소/중간 취소·늦은200·owner 변경과 timer/
listener 정리를 검증했다. 이는 production 함수+주입 IO·가짜 시계 회귀다.

제품 3파일과 최종 회귀·caller의 독립 읽기 검토에서 구체적 blocker가 없음을
전달받았다. 최종 문서·manifest 인계는 실제 원격 CI/PR 수용을 대신하지 않는다.

## 한계와 남은 범위

React mount·실제 브라우저·Next 서버·로그인·Backend/PG·OpenAI/KIS·운영 수용은
이번에 실행하지 않았다. 브라우저 abort가 Backend/model 송신 취소나 비용0을
보장하지 않는다. API/count/key/.env/DB·flag 활성화·예약/발급은 0이며 기존
250m 보수 예약과 실제 generation/청구 미확정 상태를 변경하지 않았다.

정확 9파일을 별도 PR 범위로 인계하며 commit/push/PR·원격 CI는 아직 하지 않았다.
실제 merge는 사용자 담당이다. CF029 파일을 옮기거나 거절된 fetch/stage/publish를
이 작업으로 재시도하지 않았다.
