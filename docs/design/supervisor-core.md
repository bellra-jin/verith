# Supervisor 단일 채팅 디자인

[공통 계약](../contracts/supervisor-core-v1.md)을 표현하는 `/research`의 활성 SupervisorChat → production SupervisorSession/ChatView다. Next navigation과 기존 Flow 복구 seam만 얇은 wrapper에 남긴다. 기존 AppShell과 보관함을 교체하지 않는다. Technical 실행이나 이전 ResearchView를 되살리지 않는다.

## 화면과 상태

한 자연어 composer에서 원문 bubble→typed 명확화→canonical 후보→계획/범위 동의→실제 Flow 상태/저장 링크로 이어진다. 원문과 답변 출처, 조건 ID·focus/제외·unsupported와 명시 waiver를 함께 표시한다. 요청/연결/선택 관점은 별도 배지이며 미지원 분석의 가짜 진행률을 만들지 않는다.

| 상태 | 표시·행동 |
|---|---|
| 초기·준비 | 자연어 입력, 현재 Flow만 연결됨, 동기 중복 잠금 |
| 명확화·후보 | typed 답변, 검증된 canonical 이름/코드/시장, stale 재확인 |
| 범위 확인 | 원조건과 유효 범위, 부분 실행·조건별 동의·최종 실행을 구분 |
| 실행·관측 | 실제 state/deadline, 자동 관측 종료 뒤 GET-only 재확인 |
| result_ready | 저장 미완료 안내, matching fixed pending이 있을 때만 same-key 게시 복구 |
| unknown·실패 | 고정 오류, unknown을 취소로 단정하지 않음, 새 key 자동 실행 없음 |
| partial·stored | Flow 저장 결과와 미지원 not_executed를 구분, 검증된 본인 상세 링크 |
| 인증 만료·삭제 | 비공개 질문/계획/결과 숨김, fresh session 재확인 또는 deleted |

draft 편집은 계획/동의를 무효화한다. binding pending 뒤는 read-only다. ACKunknown·running·unknown·result_ready에서는 같은 키/본문의 복구 근거를 버리는 새 대화 reset을 막고, terminal stored/failed/deleted에서 명시적으로 시작한다. 기존 Flow pending은 우선 복구하고 새 Sup key로 변환하지 않는다. matching pending 없는 Sup 직접 링크는 관측만 가능하다.

## 표현과 접근성

scoped `chat.css`는 기존 인디고/슬레이트·흰 카드·라운드·폭/타이포를 사용한다. desktop1440/mobile390은 한 열 전환·가로 넘침 없음·레이블·키보드 focus·aria-live·색 외 상태 텍스트를 수용 기준으로 삼는다. React text만 사용하고 외부 font/asset·raw HTML·iframe을 추가하지 않는다.

## 증거 구분

보호 unit은 production helper 행동과 source assertion을 구분한다. 준비된 fixture는 실제 SupervisorSession+ChatView+CSS와 production React CJS5를 합성 HTTP로 제공한다. 별도 성공용 상태기나 validator stub을 두지 않고 실제 session/core 요청 helper를 사용하지만 Next SSR/BFF·실제 DB/모델 검증이 아니다. 격리 browser capability가 확인되지 않으면 실제 desktop/mobile 시각·클릭 수용은 미실행이다. 현재 실제 결과/차단은 [CF-023 작업 기록](../work/CF-023-supervisor-meaning.md)을 따른다.


## CF-023 고정 준비 수용

첫 준비 전 owner별 prepare_key/Draft/parent/digest를 저장하며 ID 수신 뒤 body와 ID의 binding digest도 대조한다. 준비 접수503/ACKunknown은 동일 키·동일 본문으로만 회수하고 known ID는 GET 관측한다. 소비된 preparation의 owner-bound binding 참조는 GET-only로 복구하며 confirm 입력을 재구성하지 않는다. 기존 확정 binding/pending과 legacy Flow pending이 새 준비보다 우선이다.

확인 가능한 범위의 명확화에는 눈에 보이는 **답변 확인** 버튼이 있고 IME 조합 Enter는 제출하지 않는다. 의미 정책이 해소할 수 없는 meaning 장벽은 질문 편집으로 안내한다. 내부 관점 코드를 입력하라고 요구하지 않는다. 원조건·조건별 조정 동의, 준비 meaning_status와 첫 채택 남은 시간을 사람용 문구로 표시한다. 체크박스 label과 주요 행동 영역은44px 이상이며 색 외 상태 텍스트를 유지한다.

첫 prepared confirm만 유효기간을 검사한다. 기존 binding replay는 TTL 때문에 잠그지 않는다. 서버가 first adoption을 명시적으로 거절한 경우만 해당 confirm pending을 해제하고 명시 재준비를 허용한다. 불명 응답은 terminal rejection으로 취급하지 않는다. 취소는 미채택 준비 원문 redaction이며 기존 Flow 취소가 아니다.

실제 1440/390 레이아웃·포커스·React 클릭은 지원되는 격리 browser capability가 없어 미실행이다. fixture 제어와 helper/unit/source assertion은 이 수용을 대체하지 않는다.

## CF-025 fixture 복구와 종료

fixture는 부모의 `CF025_FIXTURE_URL`에 출력된 `http://127.0.0.1:<검증 port>/research`만 사용한다. `/research?supervisor_id=<UUID>` 복구는 동일 validator로 서버·초기 ID·navigate·popstate를 연결하고 내부 ID를 정규화한다. 빈/중복/미지 query·analysis_id·경로 encoding 우회는 거절하며 `/` 별도 alias는 없다. 생산 Session의 URL/owner/generation 무효화는 그대로다.

대화형 fixture의 **fixture 완료 / fixture 취소** 버튼은 exact Host·Origin·현재 nonce를 요구하는 고정 terminal endpoint로 자기 수명주기만 끝낸다. complete는 UI 수용 완료가 아니고 cancel은 Flow 실행 취소가 아니다. 부모는 같은 자식의 immutable 영수증·정상 settlement·package/source/dependency postcheck·readiness/listener 제거를 함께 대조한다. ACK가 없으면 재전송하지 않고 영수증을 회수하되 ACK 불명을 보존한다. 받은 오류 ACK는 성공/불명으로 바꾸지 않는다. 590초 fixture·600초 worker 상한은 유지한다.

보호 `core-browser-check`는 부모가 등록한 fixture와 HTTP probe sibling을 사용한다. complete와 cancel을 별도 root의 순차 인스턴스로 검사하며 probe는 요청당 절대5초/전체60초로 제한한다. HTML/bundle·합성 준비/확정·복구 URL·명시 outcome GET과 종료/정리 증거일 뿐, 실제 React mount/interaction/storage_navigation/visual_1440/visual_390/focus는 모두 `not_executed`다. 자동 probe가 브라우저 JS를 실행하거나 페이지 요청이 자동 GET을 수행했다고 주장하지 않는다.

향후 수동 UI 검증은 사용자 확인을 받은 새 미로그인 전용 profile의 쿠키/storage 격리 또는 문서화된 격리 capability가 입증된 뒤 별도로 한다. 부모가 그 실행에서 출력한 주소만 사용하고, 임의 localhost/3200·새 tab을 격리로 간주하지 않는다. 명확화/후보·동의/취소·pending/401·늦은 응답·새 대화/뒤로가기·storage 복구·1440/390·키보드/focus를 실제 관측한 항목만 기록한다. 이번에는 browser/tab/profile·실제 Backend/모델을 실행하지 않았다. [직접 HTTP 결과와 한계](../work/CF-025-supervisor-browser-readiness.md)를 따른다.

## CF-027 재인증과 화면 수명주기

401/계정 변경은 Conversation 위 Session의 tab-local 재인증 latch를 닫는다. 원문/계획/결과·동의는 숨기고 요청/timer를 중단하지만 owner별 fixed pending/key/body/digest는 삭제하지 않는다. latch에는 민감 정보가 없는 정적 marker만 저장하며, 저장소 접근이 불명하면 자동 복구하지 않는다. 같은 탭의 route remount·부모 rerender·URL/back·pageshow/visibility 복귀도 이 marker를 해제하지 않는다. 마지막 검증 owner는 별도의 tab-local SHA256 fingerprint로 보존하고 요청 callback의 활성 owner/epoch와 분리한다. 자동 조회에서 이전 A와 다른 B가 관측되면 grant 전에 latch로 닫으며, 최초 로그인 또는 명시 재확인 뒤 실제 검증이 성공한 B만 새 provenance로 기록한다. fingerprint metadata 불명/불일치도 자동 채택하지 않으며 실제 session/owner 검증은 계속 수행한다.

사용자의 **로그인 상태 다시 확인**만 동기 ref-lock을 잡아 한 번의15초 bounded 복구를 시작한다. 이전 세대/owner/URL·숨김/unmount 뒤 늦은 session200과 callback은 현재 화면을 되살리지 못한다. 명시 복구는 같은 ID의 GET 검증까지만 하며 새 POST/key나 자동 polling을 시작하지 않는다. 다시401이면 latch로 돌아가고 다음 명시 행동까지 요청을 멈춘다. 실제 계정 검증과 private 조회가 성공한 뒤에만 latch를 해제한다.

안정 callback을 사용하므로 단순 부모 counter/stats rerender가 effect cleanup·비공개 내용/동의 초기화·추가 인증/조회 요청을 만들지 않는다. 실제 자동 관측을 시작한 뒤 중단/예산 종료된 경우에만 종료 안내를 표시한다. 새 대화/초기 인증·단순 명시 재인증은 그 안내를 켜지 않는다. 준비 취소 뒤 편집 draft를 보존하는 기존 의미는 이번에 변경하지 않는다.

합성 fixture는 인증 거절 전 session/core·method별 attempts를 성공 counter와 별도로 관측한다. 앱 요청128회/rolling2초24회 초과 또는 arm한 시나리오30초 초과는 실패/종료이며 UI 통과가 아니다. session hold_next/release는 이전 owner/status snapshot을 고정한다. 실패는 기존 소유 fixture-counts 경로의 nonce-bound 단일 유한 대기 응답으로 즉시 전달한다. 무한 polling/재연결 없이 실패 banner·동기 ref 잠금·Session 해제를 수행하고, 늦은 refresh/control 응답이 실패를 덮거나 잠금을 풀지 못한다. 서버는 알림 전송/연결 settlement와 기존 failed terminal 정리를 이어간다. 실제 React/브라우저 수용은 [CF-027 기록](../work/CF-027-supervisor-reauth-lifecycle.md)의 직접 실행/미실행 구분을 따른다.


CF027 종료 전 조율 측의 실제 Chrome에서는30초 뒤 클릭 없는 고정 실패 표시·제어 잠금·Session 해제·commit ACK를 관측했다. 그러나 실행 중 source drift로 parent postcheck78이 발생했으므로 최종 exact-source 수용 통과로 기록하지 않는다. 이후 동일 소스의 ACK 미수신 failed receipt·정리는 실제 callback/영수증 IO 회귀로 검사했다. collect가 서버에서 끝났어도 client deadline이 만료되면 유효한 failure commit은 열린 terminal을 failed로 닫는다. ACK handler는 종료 완료를 기다리지 않아 자기 drain과 교착하지 않는다. 이는 주입식 server/timer 검사이며 수정 후 mounted·1440/390·focus 수용은 별도로 남는다. 최신 검사와 제한은 CF-027 작업 기록의 재개 결과를 따른다.


이후 최종 동일 소스를 고정한 조율 측 브라우저 회차에서 클릭 없는 deadline 실패 화면·잠금·Session 해제·commit ACK와 ACK 미수신의 `commit_unconfirmed`·정리를 관측했다. 별도 정상 회차는 completed receipt/parent0, 1440 질문 focus·Tab/Return과390 production 카드 배치를 확인했다. 정확390 keyboard traversal·긴 오류·일시 재확인 disabled 상태는 미검증이며 fixture 진단 JSON overflow와 실제 실패 회차 receipt 미회수 한계가 남는다. 의도된 실패 회차의 child1/parent78을 정상 전체 수용으로 바꾸지 않는다. 상세 증거 경계는 [최신 CF-027 브라우저 기록](../work/CF-027-supervisor-reauth-lifecycle.md#2026-11-10-재개-후-동일-소스-브라우저-관측과-게시-범위)을 따른다.
