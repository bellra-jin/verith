# Industry 신규 미검증 candidate의 supported-only 출력

## 근거와 승인 범위
MD §08은 근거부족에서 검증 가능한 사실만 limited로 구성하고 검증기 장애는 기본 보류하도록 한다. §18/SDD05는 근거 scope와 검증후 release를 요구한다.
앞선 explicit False 제외 패치는 unknown 관계가 Triple로 남는 호환성을 보존했다. 하지만 현 graph_documents/ingest는 그 unknown status를 보존하지 않아 이후 사실처럼 쓰일 수 있다. 이번 후속은 새 LLM candidate 출력에 한정한 보수적 선택이다.
기존 DB·CSV·graph_documents·raw cache·원문은 변경하거나 실행 입력으로 읽지 않았다. 수집·writer·ingest·전체graph 갱신·Backend/공개 API/schema는 변경/실행하지 않는다.

## 동작
- supported만 Triple 반환 목록에 포함한다.
- explicit bool False는 rejected 관측과 기존 rejects 목록으로 분리한다.
- not_run/indeterminate는 Triple 반환에서 제외하고 내부 quarantine에 원본 candidate deep-copy와 normalized observation(status/reason/source/relation/target/origin)을 보존한다.
- 원본 raw 입력을 수정하지 않고 unknown을 rejected로 속이지 않는다. 기본 호출자가 quarantine sink를 생략해도 unknown은 downstream 반환에 섞이지 않는다.
- raw_to_triples의 기존 list 반환은 유지한다. optional quarantined_candidates·verification_observations는 caller-owned 내부 메모리 sink다. 새 외부 저장/공개 필드를 만들지 않는다.
- 구조화 OWNS_STAKE는 별도 기존 경로이며 quote verifier를 통과시키거나 제거하지 않는다. 기존 지분0과 정상관계/출처가 유지된다.

## 비파괴 의미와 제한
quarantine snapshot은 원본 dictionary와 nested metadata를 독립 복사하여 상호 변경이 전파되지 않는다. 기존 raw cache는 그대로여서 자료 검토/후속 재정규화 원본을 삭제하지 않는다.
이것은 durable quarantine 저장소나 프로세스 장애 복구가 아니다. caller가 sink를 보존하지 않으면 메모리 관측은 실행 이후 남지 않는다. 새 영속 quarantine·운영 release/coverage 정책이 필요하면 팀 계약 검토가 별도 필요하다.
이미 적재된 기존 unknown/거부 관계를 제거하거나 과거 결과를 소급 재작성하지 않는다. 기존 graph 전체가 검증되었다는 뜻이 아니다. 실제 적재/활성화는 여전히 별도 승인이 필요하다.
supported는 기존 quote/source 매칭을 뜻할 뿐 관계 의미·기업 혼입·시점·사실 진실 전체의 보증이 아니다.

## TDD·회귀
수정 전 no-quote unknown이 반환되는 supported-only 회귀를 먼저 실패 재현했다.
수정 후7개 합성 시나리오 그룹(기존6+quarantine1) 통과. no_quote/source_unavailable/verifier/loader error/비정형 결과를 구분하고, rejected+supported+unknown 혼합에서 정상 출처만 merge로 넘어감을 확인했다.
quarantine 원본/status/reason 보존, nested deep-copy 양방향 독립, sink 미제공 기본경로 안전, 구조화 지분0·파일400줄 상한을 확인했다.
Industry export18/18·거시정책6/6·evidence context6/6와 diffcheck 통과. 실제 모델·DB·RapidFuzz·원천파일·브라우저·운영 적재는 실행하지 않았다.
수집 전 파일쓰기·설정/데이터읽기·네트워크/DNS/subprocess 차단. loader/verifier/normalizer/reject writer는 synthetic callback으로 격리했다.

재현: C:/Verith/.venv/Scripts/python.exe -I -S ai/tests/industry/test_rejected_candidates_isolated.py

문구 보정: raw_to_triples 자체는 기존 evidence_rejected.csv writer를 호출하며 그 writer는 w 모드로 거절 로그를 갱신한다. 기존 graph/최종 triple CSV를 직접 변경하지 않는다는 의미와 구분한다. 이번 검증에서는 해당 writer를 fake로 대체하여 거절 로그를 포함한 실제 데이터 파일을 전혀 쓰지 않았다.

후속: [main 메모리 검토정보 연결](industry-cli-candidate-review.md)로 CLI 내부 sink를 실제 전달하고 원문 없는 집계만 보고한다. None 반환 유지·새 영속 저장 없음·프로세스 이후 보존 불가 한계는 그대로다.
