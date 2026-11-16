# Industry 인용만으로 verified 승격 차단

## 근거
고도화 상세설계 v1.0 §18·26·27은 미실행 검증의 verified 승격 금지와 동일 final_state 결과 보존을 요구한다.
현 faithfulness.check_faithfulness는 checked=False(근거 없음·거절·검증기 장애/파싱 실패), checked=True(실제 판정)로 구분한다.
하지만 retrieval.generate_answer는 text만 반환하고 agent._generate_answer도 answer만 state에 전달한다.
report_export.parse_answer는 인용 문자열이 있다는 이유만으로 verified/근거 검증 완료를 만들었다. 인용 존재는 실행 성공 증거가 아니다.

## 최소 수정
warning은 기존 unsupportedClaims를 유지하고, 그 외는 기존 unchecked/근거 검증 정보 없음을 사용한다.
새 enum/필드·공용 schema·Backend/Frontend는 변경하지 않는다. final_state의 임의 checked/verified 힌트도 신뢰하지 않는다.
이 경로는 실제 clean 검증도 문자열만으로 입증할 수 없으므로 unchecked로 보수 처리한다. verified 복구에는 같은 실행·답변·근거에 결합한 typed 결과 전달과 소비계약 검토가 필요하다.
not_run/indeterminate 세분화도 현재 export가 구분근거를 잃으므로 이 수정이 완료했다고 주장하지 않는다.

## 검증
새 2회귀 실패(6/8)를 먼저 확인하고 최소 수정 후 통과. 최종 11/11.
기존 export5회귀, 인용/no-citation, 임의 신뢰힌트 무시, 실제 faithfulness 함수의 no-evidence/예외/깨진응답/clean fake판정, warning 보존, 실제 validator→기존 HTML renderer의 JSON 상태 보존을 검사했다.
stdlib 격리 러너는 source 수집 전에 네트워크/DNS/subprocess·쓰기·설정/데이터 읽기를 차단한다. report_export는 순수 함수/상수/stdlib import만 AST 로딩하고 실제 graph/provider/config 초기화는 하지 않는다. edge provenance 메타데이터 조회는 fake로 격리했다.
HTML/support 두 기존 정적 asset만 명시적으로 허용하고 생성 HTML/JS는 실행하지 않았다. 브라우저/실제 API/Neo4j/LLM 수용 아님.

재현: C:/Verith/.venv/Scripts/python.exe -I -S ai/tests/industry/test_export_isolated.py

## 다음 과제·한계
현재 execution.pipeline의 faithfulness 단계는 정적으로 done/Implemented이며 실제 검증 상태와 결합되지 않는다. 이번 최소 패치에서 새 pipeline enum을 임의 도입하지 않았으며 후속 typed 결과 전달과 함께 검토해야 한다.
기업별 근거/거부근거 관계 제거, 검색 상한·read-only 실제 권한, dataset pin/coverage, 실제 동일실행 통합은 별도 미완료다.
report_export.py는 기존 600줄대 초과 파일이다. 이번 변경은 상태 추론 한 줄·설명만으로 제한했고 무의미한 구조분할은 하지 않았다.
유료 호출·배포·Backend/Supervisor/Flow/Technical 및 Git 게시 변경은 없다.

후속: [결합된 내부 검증 관측 전달](industry-bound-verification.md)에서 typed 기록과 같은 입력/출력 일치 시에만 기존 positive 상태를 복원하고 pipeline 정적 완료 표시를 제거했다. 초기 최소 패치의 한계와 구분한다.
