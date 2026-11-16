# Industry 알려진 기업의 검색 범위·근거 귀속 보호

## MD 근거와 실제 재현
MD §18/26/27·SDD05는 기업별 근거 scope와 두 기업 혼입 방지를 요구한다.
기존 _mentioned_company는 가장 긴 한 표면형만 골라 'LG화학과 삼성SDI 사업구조 비교'도 한 기업 자료로 vector 검색했다. 실제 함수를 fake vector로 연결하여 양쪽 기업 근거가 남지 않는 실패를 먼저 재현했다.

## 보수적 지원 범위
알려진 registry의 canonical/사람이 지정한 alias/6자리 코드만 사용한다. 생성 alias 파일을 새로운 식별 근거로 믿지 않는다.
단순 단일기업, 기업을 특정하지 않은 기존 global, 명시적 known2기업 비교만 지원한다. 겹친 에코프로/에코프로비엠은 longest nonoverlapping 표면을 고르고 같은 회사의 반복 alias는 중복 요구로 만들지 않는다. 동일 표면이 여러 회사로 충돌하면 임의 우선순위로 귀속하지 않는다.
제외·복잡한 범위·명시 시점/연도 조건·3기업 이상·불명확 비교는 scope미확인으로 보류한다. 이는 완전한 자연어 의도 parser가 아니며 정해진 보수 profile 밖의 유효 질문도 보류할 수 있다. unknown 회사 이름을 포괄적으로 검출/지원한다는 뜻이 아니다.
명시 비교/미확인 scope는 모델이 global/다른 label을 내도 deterministic vector scope 경계로 보낸다. 단일/global의 기존 정상 route는 유지한다.

## 1회 검색과 귀속 확인
기존 k5 검색을 유지한다. 단일기업은 company canonical 필터1회, known2 비교는 기존 global 검색1회만 한다. 복잡 조건/식별 충돌은 추가 추정이나 검색 없이 보류한다.
global top5에 두 회사 모두 나오지 않을 수 있다. 더 조회해 메우지 않으며 '이번 검색 범위에서 모두 확보 못함'으로 보류한다. 실제 corpus에 자료가 없다고 단정하지 않는다. 호출수1은 DB/임베딩/비용 상한이나 동일 원가의 보증이 아니다.
각 chunk의 이름과 코드가 registry의 같은 회사로 매핑돼야 한다. 제공된 값이 불일치·미등록 alias·코드 형식 오류이거나 이름/코드가 모두 없으면 특정 회사에 붙이지 않는다. 한 필드만 있으면 그 명시 식별자가 유일하게 매핑돼야 하며 누락 값을 요청 회사명으로 채우지 않는다.
소스 값은 독립 copy로 보존하고 이름/코드/본문을 임의 교정하지 않는다. 맞는 근거와 부족한 회사를 구분한 내부 frozen CompanyScope만 전달한다. 관측은 metadata consistency이지 원문 진실·발행사 인증·release/기간 pin 증명이 아니다.

## 답변과 공용 계약
비대칭/불명확/실패 scope는 QA·verifier를 호출하지 않고 제한된 보류문만 반환한다. 기존 classifier는 그 전에 실행될 수 있으므로 전체 실행 LLM0이나 무료 실행이라고 주장하지 않는다.
두 기업의 근거가 확보된 경우만 기존 QA/검증 흐름으로 가며, 기존 answer 본문에 상위 검색 결과 범위·전체 자료/동일 시점 미입증을 명시한다.
기존 typed verification record는 보류에 not_run, 기존 wire에는 unchecked/미실행을 사용한다. CompanyScope·내부 state는 public JSON에 포함하지 않는다.
AI request question-only 및 research-report.v1 필드·reportId·원본 question·기존 enum은 유지한다. local renderer validator 및 실제 기존 export 경로를 검사했다.
읽기 전용 대조한 Backend _validate_payload는 기존 version/reportId/question.text/answer.body를 요구하며 원문 payload를 저장한다. 그러나 IndustryReportService는 status/data_status=completed를 고정한다. 본문 보류/unchecked가 정식 machine-readable limited·공개 eligible 정책으로 통합된다는 뜻이 아니다. 그 품질·저장 매핑은 진희 담당 blocker이며 변경하지 않았다.

## 합성 검증
source의 실제 company retrieval/normalizer·route 함수를 AST로 읽고 fake vector만 주입했다.
known2/Korean vs/English 비교, 1회 검색, 비대칭/중복A source, alias/code 충돌·누락·비정형, registry 충돌, 중첩 이름, numeric substring, 단일/global 호환·copy 독립, stale/forged scope·모델 label 우회를 회귀했다.
actual QA→검증→binding→export에서 missing/ambiguous/stale/불일치는 QA0·unchecked, 정상 known2는 QA1/verifier1·제한문 보존·기존wire25/25 통과를 확인했다.
실제 graph/DB/embedding/model/provider·기존 CSV/원천·배포는 실행하거나 변경하지 않는다. 수집 전 네트워크/DNS/subprocess·쓰기·설정/데이터 읽기 차단.
source pin·실제 corpus coverage·현재성·DB 읽기권한·공통 quality/보관함/게시 통합·full LangGraph/HTTP/UI 수용은 여전히 별도 미완료다.

재현: C:/Verith/.venv/Scripts/python.exe -I -S ai/tests/industry/test_company_scope_isolated.py
