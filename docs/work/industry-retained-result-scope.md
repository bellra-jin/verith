# Industry AI 보관·사용 조회행 범위 일치

## MD 근거와 실제 재현
MD §18/26/27의 동일 final_state export·검색 상한·근거 범위 표시를 따른다.
기존 MAX_CONTEXT_ROWS=50은 QA prompt의 rows[:50]에만 적용됐고 state/evidence/citations/export에는 그 뒤의 행도 남을 수 있었다. actual execute node의 fake51행이50행으로 제한되지 않는 실패를 먼저 재현했다.

## 제한된 변경
기존50행 정책을 pure domain/result_scope.py 한 곳에 두고 retrieval의 기존 MAX_CONTEXT_ROWS import 이름을 유지한다.
agent execute, 직접 answer_question/CLI, generate_answer가 같은 retained-row helper를 사용한다. 최대51행만 관측하여50행을 독립 deep-copy하고 추가행 관측을 boolean으로 남긴다.
state에서 prompt·근거·인용·binding·export로 전달되는 실제 사용 행이 일치한다. 원본 반환 list/dictionary는 수정하지 않는다.
초과가 관측되면 기존 answer 본문에 deterministic 범위 제한문을 넣어 저장/HTML에도 남긴다. 기존 research-report.v1 필드 구조를 유지하고 내부 query_rows_truncated 필드는 wire에 내보내지 않는다.
비정형 결과는 사용 가능한 일부 자료처럼 꾸미지 않고 고정 오류로 닫는다. 오류/차단 상태는 clipped flag를 초기화한다. 모델 초기화 전에 row shape를 확인한다.
기존 정상50행 이내 경로에 새 제한문을 붙이지 않는다. 이는 원천 전체가50행 이하이거나 coverage완료임을 의미하지 않는다.

## 과장하지 않는 상한
이것은 AI state에 보관·사용하는 top-level50행 제한이다. DB driver가 이미 전체 결과를 materialize했을 수 있다.
DB의 실행시간·원천 결과 수·query plan/cardinality·임베딩/모델 토큰·비용·전체메모리 peak의 상한을 만들지 않는다. 한 행의 큰 nested payload/문자열 크기도 이 patch로 제한되지 않는다.
추가1행을 관측했다고 정확한 전체행수나 dataset completeness를 추정하지 않는다. helper의 iterator 소비 한도도 실제 DB 실행 취소·row fetch 제한의 보증은 아니다.
source pin·immutable release·원천 시점·실제 DB 최소권한·서버 timeout/result bound는 여전히 별도 blocker다. 기존 graph/CSV/DB/권한·Backend·운영 배포는 변경/실행하지 않는다.

## TDD·회귀
수정 전 actual execute node의51행 실패 확인 후 수정.
fake-only 격리 검사에서0/1/49/50/51/100행 경계, lazy iterator51개 관측, nested 원본↔보관본 양방향독립, 비정형/조회오류와 flag reset을 검사했다.
실제 answer node/generate_answer/export 함수를 source AST로 연결해 QA prompt·evidence·citations가0~49행만 사용하고50번째 이후는 제외됨을 확인했다. 전체 answer의 bound verification 일치와 실제 existing validator를 통과한 payload의 metrics.rows50·본문제한·내부필드 비유출을 검사했다.
직접 answer_question·CLI도 같은 제한문/범위를 쓰고 owned fake graph close·None 반환을 유지한다. 비정형 입력의 모델 초기화/invoke0을 확인했다.
수집 전 쓰기·설정/데이터 읽기·네트워크/DNS/subprocess 차단. 원천/모델/graph/formatting/verifier는 fake이며 실제 LangGraph engine·DB materialization·provider·서비스/브라우저·공개수용이 아니다.
기존 Cypher boundary 및 Industry export19/19와 함께 회귀했다. source 파일은 모두400줄 이하다.

재현: C:/Verith/.venv/Scripts/python.exe -I -S ai/tests/industry/test_result_scope_isolated.py
