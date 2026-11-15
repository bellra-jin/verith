# Industry 생성 Cypher의 보수적 지원 subset 차단

## MD 근거와 재현
MD §18/26/27·SDD05는 최소 읽기 쿼리·매개변수·시간/결과 상한·실제 DB 읽기 권한을 요구하며 자유 생성 Cypher는 후속으로 둔다.
현 generate_cypher는 LLM 문자열을 그대로 반환하고 agent._execute_cypher·retrieval.answer_question·CLI가 이를 graph.query에 전달했다.
fake graph에서 CREATE/DELETE/CALL apoc.cypher.run이 그대로 실행 경계에 도달하는 실패를 먼저 재현했다. 실제 DB나 공급자는 호출하지 않았다.

## 제한된 수정
pure domain/cypher_guard.py가 생성 결과와 실제 agent 실행 경계 양쪽에 적용된다. 쓰기/관리 절, CALL/LOAD CSV, 다중문장, 알려지지 않은 함수/확장·version prefix·interpolated string·모호한 escape/comment·불균형 구조를 보수적으로 거절한다.
일반 인용 문자열/escaped quotes·quoted property names·일반 주석·단일 trailing semicolon·기존5개 prompt read 예시는 유지한다.
입력 cap16384문자는 가드 자신의 작업량 상한이다. DB timeout·결과 수 상한·토큰/금액 budget으로 해석하지 않는다.
거절 오류 문구는 고정되어 query/개인 데이터/원천·예외 원문을 돌려주지 않는다. 실제 graph query 전에 거절하며 LangGraph generation node는 거절을 고정 error state로 바꾸고 기존 vector fallback으로 보낸다. 직접 answer_question/CLI 호출은 예외 전파로 닫힌다.
공용 응답/schema·DB 계정/권한·Backend·기존 데이터·고정 vector/overview 쿼리·모델 호출 정책은 변경하지 않는다.

## 공식 문서 확인
[Neo4j 문자열](https://neo4j.com/docs/cypher-manual/current/values-and-types/boolean-numeric-string/)의 backslash escape 및 Cypher25 interpolation을 참고했고 새 interpolation은 지원하지 않는다.
[주석](https://neo4j.com/docs/cypher-manual/current/syntax/comments/), [절 목록](https://neo4j.com/docs/cypher-manual/current/clauses/), [매개변수](https://neo4j.com/docs/cypher-manual/current/syntax/parameters/)의 공식 설명을 읽었다. 문서 조회는 공개 페이지뿐이며 서비스 API/계정에 접속하지 않았다.

## 테스트
기존 쓰기3개 도달 실패 후 정상read18개(기존prompt5개 포함), unsupported34개(쓰기/CALL/LOAD/다중문장/함수/주석·Unicode escape/interpolation/깨진구조), cap 경계 검증.
실제 _execute_cypher·generate_cypher·answer_question·CLI 함수의 source AST를 fake graph/model/factory로 연결했다. 모든 차단 입력에서 graph.query0, 정상read query1과 rows 보존, CLI owned fake graph close를 확인했다.
수집 전 쓰기·설정/데이터 읽기·네트워크/DNS/subprocess 차단. 실제 Neo4j/모델/config/계정·DB 권한/HTTP/브라우저·운영 수용은 실행하지 않았다.

## 반드시 남는 blocker
이 코드는 Cypher 언어 전체 parser나 보안/인가 경계가 아니다. 새 Neo4j 문법/사용자 함수/권한을 포괄적으로 입증하지 않으며 DB의 실제 least-privilege 읽기 계정과 고정 parameterized template를 대체하지 않는다.
보수적인 subset 밖의 정상 readonly 쿼리(일부 함수·read procedure·interpolation·version 지시문 등)도 거절할 수 있다. 이를 no_data나 원천 없음으로 꾸미지 않는다.
DB 실행시간·결과 수 제한, 실제 query plan/권한·template 고정·dataset release pin·trusted 서비스 수용은 아직 별도 미완료다. 현재guard통과만으로 production DB/외부 호출 실행을 허가하지 않는다.
기존 실제 graph/CSV·권한 설정을 건드리거나 안전 검사를 꺼서 live 검증하지 않는다.

재현: C:/Verith/.venv/Scripts/python.exe -I -S ai/tests/industry/test_cypher_boundary_isolated.py

## 독립 리뷰 후속: fallback·quoted invocation·range
첫 구현은 generate_cypher의 UnsupportedCypher가 LangGraph generation node를 중단하여 기존 vector fallback에 도달하지 못했다. 실제 generation node 회귀가 실패한 뒤 수정했다.
generation node는 차단 query 원문을 보관하지 않고 cypher 빈값·고정 error·내부 cypher_rejected=True·attempts1을 반환한다. execute node는 DB query0, route는 즉시 기존 vector fallback으로 간다. 반복 unsafe 생성을 추가 호출하지 않는다.
정상 생성은 rejection flag를 지우고 기존 DB read-error retry/max-attempt vector 경로를 유지한다. 일반 모델 RuntimeError를 query rejection이나 no_data로 바꾸지 않는다.
실제 node 함수들을 fake 모델/vector/graph/QA로 순서대로 연결하여 fallback vector1·QA1·graph.query0, 정상 회복과 retry, error의 고정성 및 공용 JSON 비유출을 확인했다. full LangGraph engine/서비스가 수용됐다는 뜻은 아니다.

quoted MATCH(1)처럼 escaped identifier를 function으로 호출할 때 group keyword 예외가 적용되던 subset 틈을 실패 재현 후 수정했다. quoted function은 명시 함수 allowlist만 허용하며 실제 DB에서 해당 함수가 존재하거나 쓰기가 실행됨을 입증한 것은 아니다.
기존5개 prompt read 예시에 range가 없고 현재 필요/안전한 bound가 입증되지 않아 range 함수는 큰/작은 인수 모두 fail-closed로 제외했다. 일반/quoted/qualified 형태도 같은 함수 allowlist로 차단한다.
이것으로 DB 리소스 budget이 해결되지는 않는다. 허용 read의 collect/aggregation·가변 길이 그래프 경로 등도 비용이 커질 수 있으며 실제 result/time/cardinality 상한과 DB 최소권한은 여전히 blocker다.

최종 query-boundary 회귀 통과(정상18/차단34/cap/실제 generation·CLI·node fallback·retry), Industry export19/19 및 diffcheck 통과.
