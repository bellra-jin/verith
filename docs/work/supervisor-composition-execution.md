# Flow 접수/실행 분리와 내부 조합 runtime

기준 develop `98bd96010da26923c163d804cdc6cefd644c5c0a`. 기존 WIP/실제 실행 자료를 보존하고
별도 작업공간에서 구현했다. 공개 복수 선택 planner/API는 이 단위에 포함하지 않는다.

## 제품 변경

- 공통 coordinator의 기존 POST를 admission commit ACK와 dispatch helper로 나눴다. 공개 POST는
  즉시 연결하고 기존 result_ready 게시/replay를 보존한다. Fundamental은 기존 profile 위임을 유지한다.
- Flow 내부 접수는 fresh ACK에만 같은 invocation의 일회 continuation을 보관한다. replay/ACK 유실/
  취소/폐기/다른 객체는 재발급하지 않는다. 원 owner/session·입력·grant·client snapshot을 실행 전에 검증한다.
- 기존 독립 원장과 reserve/observe/receive/writer를 재사용한다. 각 자식 INSERT에 원 접수 cutoff를
  적용하고 Root 140초/자식의 더 이른 monotonic 기한은 접수 시점에 고정한다. 기한 후 정상 body의
  유효 usage는 관측하고 결과 수신/게시만 차단한다. 미확정 body/commit은 unknown hold로 남는다.
- 내부 runtime은 기본 off이며 Technical 접수 ACK/분석시점 → Flow 접수를 원 15초 안에 끝낸 뒤
  두 기존 runtime을 직렬 호출한다. 자식 실패가 다른 저장본을 지우거나 전체 성공으로 바꾸지 않는다.
  외곽 취소에 새 재실행/SQL 정리를 붙이지 않으며 native의 기존 rollback과 caller 소유 session 종료를 유지한다.
- v2의 명시 child_inputs는 부모 원질문/확정 범위와 구분한다. Flow는 원질문을 유지하고 Technical은
  같은 canonical code의 고정 차트 profile로 투영한다. v1을 자동 변환하지 않으며 옛 native intent와 조회를 보존한다.
  c610은 기존 guard만 확장하고 새 표/원장을 만들지 않는다. 공유 c600 migration 원형은 불변이다.

## 실패 원인과 검증의 구분

이전 추가 Technical fixture와 첫 조립 PG에서는 혼합 원질문 `000720 수급과 차트`가 그대로 전달됐다.
기존 Technical 단일-view build_plan은 이를 엔진 진입 전에 거절한다. 첫 조립 회차에서 Flow stored /
Technical unknown·HTTP503, 엔진/가짜 SDK 증가 0을 안전한 메타데이터로 확인했다. 유실됐던 원 예외를
복원한 것은 아니며, 동일 입력과 기존 boundary의 결정적 거절을 보호 회귀로 재현했다.
validator를 완화하거나 수신 fixture로 대체하지 않고 명시 projection 뒤 실제 두 AI route/runtime에서
주입한 가짜 엔진과 count/generation HTTP를 실행해 두 stored 결과를 확인했다.

invalid Technical 출력은 기존 AI 계약에서 Backend receive 전 거절돼 unknown/full hold가 된다.
초기 새 테스트의 failed 기대를 이 기존 의미에 맞췄으며 제품의 unknown 보호는 변경하지 않았다.
첫 재무 검사는 공통 coordinator의 직접 Flow import를 지적해 기존 profile 위임으로 고쳤고,
새 Flow unit fixture의 operation 누락도 수정했다. 기존 assertion/guard를 삭제하거나 skip하지 않았다.

## 확인 범위와 한계

- 보호 Flow analysis 291 / core 137 / Technical boundary 245 / Technical admission 283 / Fundamental 35.
  core/analysis/admission self 3+3+5=11도 통과했다. guard와 기존 mode/설치는 유지한다. 원격 CI는 정확 head로 별도 확인한다.
- PG-2 및 마지막 monotonic cap 고정 뒤 최종 PG-3 모두 기존 46 + 새 조립 8 = 54그룹 통과 및 자기 DB 정리. 실제 SQL 인증 세션 A1/A2/타인,
  두 실제 AI ASGI route·주입 엔진·가짜 SDK, 정상 저장/부분 실패, 실제 commit 뒤 ACK 유실 wrapper,
  두 SQL 세션 경합, 취소/재요청 추가 실행 0, 늦은 접수 예약 0, v1 읽기/v2 projection SQL 거절을 확인했다.
- PG 최상위의 synthetic_provider_execution_runs=3/mockHTTP6와 fixture 문구는 기존 CF053 그룹 범위다.
  새 조립 진단은 누적 Technical 가짜 엔진 7/SDK HTTP14이며 정상 조합 한 건 자체는 두 엔진 각 1회와
  count/gen 한 쌍이다. 실제 provider 0·compiled graph 0이다. 전체 graph 품질 검증으로 확대하지 않는다.
- 마지막 기한 검토에서 접수 때 자식 monotonic cap을 추가 고정했다. 이 변경 후 최종 PG 소스 해시와
  검사 결과를 함께 보존했다. 최종 PG-3의 실행 코드 16파일은 현재 바이트와 일치하며, 이후 문구 정리만 한 문서 2개와 구분한다.
- 공개 복수 선택/동의 API·실제 공급자·Google·배포는 미검증/미연결이다. 실제 OpenAI/KIS·키/env·
  설치·타 DB/프로젝트·프론트·준영 AI·News·운영 설정 변경은 없고 기존 $1.30 보수 hold는 유지한다.
