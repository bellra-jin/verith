# Industry 동일 결과에 결합된 검증 관측 전달

## MD 근거와 공용 계약
§18/26/27의 같은 final_state 구조화·미검증 승격 금지·검증기 장애 구분을 따른다.
기존 generate_answer 문자열 반환은 그대로 유지하고 optional caller-owned verification_records에 내부 frozen AnswerVerification을 한 번 전달한다. AgentState 내부 sidecar만 추가하고 공용 JSON 필드는 추가하지 않는다.
기록의 SHA256은 question·최종 answer(인용/경고 포함)·rows·chunks의 strict JSON에 결합된다. 비유한 값/직렬화 불가 원천은 binding을 만들지 못한다.
export는 정확한 내부 기록 타입과 현재 데이터의 binding 일치를 확인한다. 임의 checked/verified boolean·dict 기록은 신뢰하지 않는다. 답변·질문·행·chunk가 바뀐 stale 기록은 unchecked다.
이 digest는 인증·권한·공급자 서명·DB trust·dataset release pin·사실 진실의 보증이 아니다. 동일 내용의 기록만으로 별도 run의 실행 신원을 증명하는 계약도 아니다.

## 실제 결과와 표시
faithfulness 결과의 내부 outcome을 not_run(verify=False/근거·검사문장 없음), indeterminate(초기화/호출/파싱 장애), checked(실제 문장 판정)로 보존한다.
공용 research-report.v1은 기존 status 값 유지: 완료된 clean 검사만 verified(문장 근거 검사 통과), 실제 unsupported는 warning, 미실행·장애·미일치/관측없음은 unchecked다. 기존 문자열 warning을 clean 상태로 덮지 않는다.
pipeline도 기존 done/skipped 값만 사용한다. done은 실제 문장검사 완료이며 unsupported의 정당성이나 모든 사실의 진실을 뜻하지 않는다. skipped는 완료 검사 미확보를 뜻하며 statusText에서 미실행/판정 불가/실행 미확인을 구분한다. 확인되지 않은 단계를 정적 Implemented로 표시하지 않는다.
검증기 초기화 장애도 기존 fail-open 원칙에 맞게 판정 불가로 남기고 답변 원문을 유지한다.

## 회귀 및 실행 한계
기록 부재 pipeline 회귀가 수정 전 실패(11/12), 최종 17/17.
실제 generate_answer 함수와 actual agent node·faithfulness 함수를 AST로 로드하고 fake QA/verifier로 검증한다. 프롬프트당 QA1+검증1, verify=False/근거없음에는 검증0을 확인한다.
skip·검증예외·초기화실패·깨진응답·clean·unsupported, answer/question/rows/chunks 변경과 dict변조, NaN binding 거부, frozen 객체, 외부 schema key 보존·sidecar 비유출·실제validator/HTML JSON보존을 검사한다.
네트워크/DNS/subprocess/파일쓰기/설정·데이터 읽기를 수집 전 차단한다. 원천 citation formatting/evidence 메타데이터 조회는 synthetic helper로 격리했다. 실제 LangGraph 엔진/HTTP/Neo4j·checkpointer·외부모델·브라우저 E2E는 실행하지 않았다.
검증기 자연어 판정 품질·source authenticity·공시시점·기업별 근거scope·거부근거 연결 제거·dataset pin/coverage·읽기 실제 권한은 이 변경으로 수용되지 않는다.
거시 담당의 ANSWER_TEMPLATE 추출·정책과 구간분리하여 동시 변경을 보존했다. Backend/Supervisor/Flow/Technical·예약/정산·유료호출·배포·Git 게시는 변경하지 않았다.

기존 초과 파일의 악화를 피하려고 pipeline 표시를 순수 api/report/pipeline.py 책임으로 추출했다. report_export는 645→592줄, retrieval은 거시 템플릿 추출을 보존한 521줄(기존533줄)로 기존 초과를 줄였다. agent351/faithfulness160/내부record34줄이다.

400줄 상한 후속: graph/evidence projection 16개 함수와 관련 상수를 api/report/graph_payload.py(368줄)로 분리했다. report_export는 현재246줄이다. 16개 함수는 HEAD 원문과 AST 동일(새 위치에 맞춘 lazy relative import만 조정)함을 직접 확인했다. 기존 build_graph_and_evidence import 경로는 facade로 보존했다. 신규 크기 회귀 포함 최종18/18이며 거시 정책6/6 재실행. 위645→592는 초기 추정 기록이고 분리 직전 실제 파일은603줄이었다. 최종 직접 측정246/368을 따른다.
