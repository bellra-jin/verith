# Industry 명시적 검증 거부 관계의 신규 candidate 제외

이 문서는 초기 explicit-False 패치 기록이다. unknown 관계 유지 정책은 [후속 supported-only/quarantine](industry-unknown-candidate-quarantine.md)에서 변경되었다.

## 근거와 적용범위
고도화 MD §18은 거부 근거를 인용뿐 아니라 해당 근거에 의존한 관계 주장에서도 제외하도록 요구한다.
기존 raw_to_triples는 verify_evidence=False에서도 인용만 비우고 Triple을 생성했다. merge와 이후 graph ingestion에는 그 관계/출처가 남을 수 있었다.
수정은 앞으로 만드는 LLM candidate의 정규화 경로만 대상으로 한다. 기존 Neo4j·CSV·graph_documents·원문·raw cache를 읽거나 삭제/재작성/재적재하지 않았다. 실제 수집·LLM·main·writer·ingest는 실행하지 않았다.

## 명확한 결과 구분
- supported: 원천이 있고 verifier가 정확한 bool True를 반환. 인용을 보존한다. 이는 기존 quote/source 매칭 통과이지 관계 의미나 기업 사실 전체의 진실 보증이 아니다.
- rejected: 원천이 있고 verifier가 정확한 bool False를 반환. 이 신규 관계 candidate만 반환 목록에서 제외하고 기존 형태의 reject 관측을 남긴다.
- not_run: 인용 없음 또는 원천 없음. 관계는 기존 호환대로 남지만 검증된 인용은 없으며 supported로 기록하지 않는다.
- indeterminate: 원천 loader/검증기 예외 또는 비정형 반환(None/숫자/비bool 등). 관계는 기존 호환대로 남고 인용은 비운다. 명시적 거부로 잘못 분류하지 않는다.

optional caller-owned verification_observations에서 신규 candidate별 status/reason을 받으며 wrapper는 상태별 개수를 출력한다. 공용 schema나 저장 Triple 필드를 추가하지 않는다. 미확인 상태의 durable 저장·게시 정책은 아직 이 경로에서 보장하지 않으며, 이번 변경이 unknown 관계를 운영에 적재/공개해도 된다는 뜻이 아니다.

## 구조와 호환성
pure domain/candidates.py가 신규 정규화를 처리한다. 기존 Triple/merge는 domain/triples.py, 기존 원천 quote 검사 함수는 infrastructure/extraction/evidence_verification.py로 책임 분리했다.
extract.py 기존 callable 이름은 import facade로 보존했고 530→398줄로 줄였다. 모든 관련 코드 파일은400줄 이하다.
이동한6개 정의(Triple/merge/원천검사4개)는 HEAD 원문과 AST 동일하다. 구조화 지분 자료 처리·output writer·reject writer·main의 AST도 그대로다. 실제 writer는 테스트에서 fake로 대체한다.

## TDD와 검증
명시적 reject 관계가 남는 기존 오류를 먼저 실패 재현했다. 최종 stdlib 격리 검사에서6개 시나리오 그룹 통과:
거부 관계 제거, 정상 인용 보존, no-quote/원천없음/loader·verifier오류/None·숫자·list verdict 구분, 정상+거부 중복의 origins 오염 차단, 구조화 OWNS_STAKE의0 보존, 파일400줄 상한.
input dictionary 불변과 rejected CSV 관측의 origin/evidence 보존도 확인했다.
소스 수집 전 네트워크/DNS/subprocess·쓰기·설정/데이터 읽기를 차단하고 실제 raw_to_triples wrapper와 순수 정규화·merge를 실행했다. 원천 loader/verifier/normalizer·reject writer는 synthetic callback이며 실제 RapidFuzz·회사 별칭 품질·원천 파일·DB·provider 수용은 아니다.

재현: C:/Verith/.venv/Scripts/python.exe -I -S ai/tests/industry/test_rejected_candidates_isolated.py
