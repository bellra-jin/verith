# Supervisor 단일 채팅 디자인

[공통 계약](../contracts/supervisor-core-v1.md)을 표현하는 `/research`의 활성 SupervisorChat/ChatView다. 기존 AppShell과 보관함을 교체하지 않는다. Technical 실행이나 이전 ResearchView를 되살리지 않는다.

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

draft 편집은 계획/동의를 무효화한다. binding pending 뒤는 read-only이며 새 요청은 명시 동작이다. 기존 Flow pending은 우선 복구하고 새 Sup key로 변환하지 않는다. matching pending 없는 Sup 직접 링크는 관측만 가능하다.

## 표현과 접근성

scoped `chat.css`는 기존 인디고/슬레이트·흰 카드·라운드·폭/타이포를 사용한다. desktop1440/mobile390은 한 열 전환·가로 넘침 없음·레이블·키보드 focus·aria-live·색 외 상태 텍스트를 수용 기준으로 삼는다. React text만 사용하고 외부 font/asset·raw HTML·iframe을 추가하지 않는다.

## 증거 구분

보호 unit은 production helper 행동과 source assertion을 구분한다. 준비된 fixture는 실제 ChatView+CSS와 production React CJS5를 합성 HTTP로 제공할 뿐 Next SSR/BFF·실제 DB/모델 검증이 아니다. 격리 browser capability가 확인되지 않으면 실제 desktop/mobile 시각·클릭 수용은 미실행이다. 현재 실제 결과/차단은 [작업 기록](../work/CF-022-supervisor-core.md)을 따른다.
