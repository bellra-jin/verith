# Industry main의 메모리 검토정보 및 안전한 집계 보고

## 기존 계약 확인
extract.main은 None 반환이며 __main__에서 main()을 호출한다. 저장소 Python/pyproject 검색에서 반환값을 exit code/public API로 소비하는 호출자는 찾지 못했다.
None 반환과 기존 CLI flags/defaults를 유지한다. optional keyword-only review_records는 내부 caller-owned sink이며 CLI 기본 호출은 그대로다.
argument parser만 pure cli_args.py로 책임 분리하여 extract.py399줄·관련 모듈 모두400줄 이하를 유지했다.

## 실제 연결
main이 raw_to_triples에 quarantine/verification_observations sink를 실제 전달한다.
build_candidate_review는 내부 caller용 원문 snapshot과 별도의 log-safe summary를 만든다. main은 summary만 출력하고, 요청된 review_records에는 내부 메모리 snapshot을 전달한다.
summary는 상태별 개수·미확인 사유 범주·quarantined_count와 retention=process_memory_only뿐이다. 기업명/출처/원문/개인 context/임의 예외메시지·동적 예외타입을 추가 로그에 노출하지 않는다.
지원되지 않는 원문은 rejected로 바꾸지 않으며 supported-only 출력 정책은 유지된다. 구조화 OWNS_STAKE는 별도 기존 경로다.
CLI 종료 후 quarantine을 저장/복구할 수 있다는 주장은 하지 않는다. sink 없는 CLI에서도 집계는 보고하지만 로컬 메모리는 프로세스 종료와 함께 사라진다. 새 DB/CSV/public schema/파일 저장 계약은 만들지 않는다.
writer 장애는 그대로 전파하며 summary는 저장 성공 ACK가 아니다. 호출자가 sink를 요청했다면 장애가 나도 실행 중 모은 검토정보는 메모리에서 확인할 수 있다.

## 정확한 쓰기 경계
raw_to_triples의 기존 evidence_rejected.csv writer는 w 모드로 거절 로그를 갱신한다. 함수 자체가 모든 CSV를 변경하지 않는다고 표현하면 틀리므로 docstring을 기존 graph/최종 triple CSV 미변경과 거절로그 writer 유지로 한정했다.
이번 작업은 source만 수정하고 실제 reject/output writer, raw cache, CSV, graph, 원문을 실행하거나 읽고 쓰지 않았다. main 테스트의 모든 수집/원천/정규화외 IO/writer는 fake다.
main의 기존 collection·output 동작은 실행 승인이 아니며 실제 실행에는 기존 권한·대상·비용 승인이 별도로 필요하다.

## TDD·검증
main 검토 sink 회귀의 수정 전 TypeError 실패를 먼저 확인했다.
수정 후 실제 main AST 함수 + 실제 순수 candidate/merge/review helper를 fake source/writer로 연결했다.
기존7개 candidate 시나리오에 main sink·no-sink/structured-only·writer 오류전파·CLI flags/summary비노출을 추가하여11개 시나리오 그룹 통과.
None 반환, 검토정보의 실행 간 독립, unknown원본 비변이, source/private context/인용·임의예외정보 비노출, 구조화 지분0, 상태/사유 분리와400줄 상한을 확인했다.
Industry export18/18 및 diffcheck 통과. 감사 guard는 수집 전 쓰기·설정/데이터 읽기·네트워크/DNS/subprocess를 차단한다. 실제 모델/DB/원천/CSV/브라우저 수용이 아니다.

재현: C:/Verith/.venv/Scripts/python.exe -I -S ai/tests/industry/test_rejected_candidates_isolated.py
