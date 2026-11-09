# Flow 표시·삭제 확인 계약 v1

CF-019의 표시 전용 계약이다. payload v1·원숫자·계산/신호·관측창·저장 해석·CF-014 fact/prompt 및 DB/owner/tombstone·CF-018 회계는 바꾸지 않는다. 최종 UX/후속 순서는 전체 작업 운영 v1.3 §4.1 한 곳을 참조한다.

- boolean을 제외한 유한수만 수치다. 누락/잘못된 수치는 자료 없음·판단 보류이며 0으로 채우지 않는다. 저장0/-0은 수치0을 표시하되 측정된 중립/유효 분모를 보증하지 않는다.
- 외국인과 기관 두 유한 ratio 및 유한 합이 있어야 기존 합의 부호 게이지를 표시한다. 한쪽 누락/합 overflow는 판단 보류다.
- 원값의 비영 여부·부호를 scale 전에 보존한다. 단위 변환 underflow나 표시 정밀도 미만은 양수/음수로 구분한다. 표시 자릿수는 유지하며 binary64 변환값의 정확한 half-even 반올림을 TS/Python wrapper에서 일치시킨다. CF-014 formatted 본체는 변경하지 않는다.
- 기관 세부는 표시할 수 있는 항목만 설명한다. 최대값0은 0 포함 순매수 없음, 표시값이 모두 음수일 때만 표시된 세부 모두 순매도다. 누락 항목까지 단정하지 않는다.
- 강도는 최근 실제 관측 N행 순매수합 ÷ 같은 창의 일평균 거래대금이다. 전체 기간 거래대금 비중/보유율이 아니며100%를 넘을 수 있다. 저장 ratio0만으로 분모가 유효하게 측정됐음을 알 수 없다.

현재 상세 route는 SessionControls가 보고서 본문을 감싼다. report 분기는 화면 내 삭제 확인/취소를 제공하고 확인 시작의 report/owner/URL/generation을 고정한다. session GET의 같은 user와 새 CSRF를 사용하며 session→DELETE 전체15초·동기 pending lock·자동 재시도0이다. UI user 비교는 인증이 아니고 기존 서버의 principal/Origin/CSRF/owner 검사는 그대로다.

숨김·window blur·페이지 이탈·대상/계정 props·URL 변경·unmount는 의도와 요청을 무효화한다. focus/visibility/pageshow 복귀는 session+report를 재확인한다. hashchange와 이벤트 없는 history 변경도 관측한다. 이벤트 없는 URL 변경의 감지는 최대 약200ms 간격이지만 확인 시작/실행/응답 반영 시에는 검증 당시 href와 현재 href를 즉시 대조한다. 서버 계정 변경을 아무 관측 이벤트 없이 즉시 아는 것은 아니며, 관측 이벤트와 삭제 직전 session의 같은 owner 확인이 보장 경계다. 늦은 성공/오류/후처리는 새 화면에 적용하지 않는다. 복귀/수동 복구는 같은 owner의 session 및 같은 report GET을 다시 확인한 뒤 본문을 공개하며 분석/POST를 시작하지 않는다.

명시 재조회와 복귀는 `document.hasFocus()`를 새로 읽어 cached false에 갇히지 않게 한다. 실제 focus가 없거나 hidden이면 GET/본문 공개를 하지 않으며 클릭만으로 focus를 강제하지 않는다. await 이후에도 실제 focus를 확인하고, 같은 identity/URL/generation인 요청만 pending을 정리한다. focus 상실로 닫힌 상태의 복구는 GET-only 재검증이다.

204만 삭제 완료다. 404는 이미 없거나 접근 불가로 안내하며 이번 삭제 성공을 주장하지 않는다. 인증/서버/네트워크 오류는 고정 문구로만 표시하고 새 확인을 요구한다. abort/timeout은 서버 rollback 보장이 아니다. returnTo는 로컬 보관함 정상 pagination만 허용한다. 로그아웃 분기는 기존 의미를 보존한다.

## 증거 구분

[작업 기록](../work/CF-019-flow-quality-delete-ux.md)의 실제 결과를 따른다. 순수 helper 실행·JSX/HTML source assertion·실제 React 합성 HTTP 클릭·Next SSR/BFF·Backend/PG 삭제는 서로 다른 수용 수준이다. fixture source나 서버 종료만으로 클릭 성공을 선언하지 않는다. 기존 CF018 삭제 후 회계 보존 PG는 과거 근거이며 이번 재실행이 아니다.
