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
