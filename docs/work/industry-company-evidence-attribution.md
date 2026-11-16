# Industry 기업별 인용 출처 오귀속 차단

## MD 근거와 실제 재현
MD §18·SDD05는 기업별 근거 scope를 보존하도록 요구한다.
현 graph의 origins/evidences는 독립 union이라 첫 origin과 첫 quote가 다른 회사일 수 있다.
기존 _pick_origin은 인용이 어느 원천에도 없거나 너무 짧아도 첫 origin으로 fallback했다. ellipsis 인용은 첫 조각만 검사하여 서로 다른 회사의 조각이 섞여도 첫 회사로 링크할 수 있었다.
report graph metadata는 URL/reportName을 선택된 origin에서 가져오면서 stockCode는 origins[0]으로 만들어 같은 근거의 기업 표시가 어긋났다.
위 세 사례를 합성 입력으로 먼저 실패 재현(0/3)했다.

## 제한된 수정
quote가 있으면 한 원천 안에 모든 인용 조각이 순서대로 존재하는 경우만 origin을 선택한다. 기존8자 기준을 충족하지 않는 짧은 인용·미일치·읽기불가는 출처 미확인(None)이며 임의 첫 회사로 연결하지 않는다.
quote 없는 구조화 provenance는 기존 첫 origin 동작을 보존한다. no-quote 경로 자체가 원문 인용 검증을 입증하는 것은 아니다.
graph metadata의 reportName/URL/stockCode는 동일한 선택 origin에서 생성한다. 미확인 quote는 링크·공시명·종목코드를 빈 값으로 남기며 원래 quote/관계문장 자체를 임의로 변경하거나 삭제하지 않는다.
기존 private _edge_display_source_url 2-value view와 공용 research-report.v1 필드 구조는 유지한다. verified/품질 상태·Backend·DB·CSV·모델·실행/게시 계약은 변경하지 않는다.

## 검증
새3회귀의 수정 전 실패 후 최종9/9 통과.
unmatched quote, 회사 간 분리된 ellipsis, selected company의 code/report/URL 일치, 짧은 quote, 동일회사 ordered/reversed fragments, source OSError, no-quote 구조화호환, 실제 citation formatter·graph JSON의 미확인 표시와 기존2-value helper를 검사한다.
실제 evidence_context 함수들을 AST로 로드하고 synthetic source text/filing meta만 주입한다. graph projection은 실제 모듈을 사용한다. 수집 전 네트워크/DNS/subprocess·쓰기·설정/데이터 읽기를 차단하므로 실제 공시·원천·DB·provider 접근은 없다.
두 수정 코드 파일은400줄 이하다. source metadata는 테스트에서 합성 origin A/B일 뿐 실제 기업 자료를 읽지 않았다.

## 미완료와 blocker
이 검사는 인용 출처를 잘못 붙이는 국소 오류를 차단하며 관계 의미·원문 진실·기업별 모든 주장 품질을 보증하지 않는다.
현재 origins는 stock code만 담고 원문/공시의 immutable version·evidence별 filing-id·기간을 보존하지 않으므로, 과거 공시와 현재 회사 파일 사이의 완전한 시점 연결을 이 스키마만으로 입증할 수 없다. dataset release pin과 historical snapshot 인수가 별도 필요하다.
과거 graph의 미검증 관계를 읽기 시 제거하거나 DB를 정리하지 않는다. 실제 공개·source dataset 갱신·버전/저장 계약 변경은 이번 범위가 아니다.
미일치 인용의 quote/주장 자체는 기존 결과에 남을 수 있으며 이 수정이 이를 supported로 승격하는 것은 아니다.

재현: C:/Verith/.venv/Scripts/python.exe -I -S ai/tests/industry/test_company_evidence_isolated.py
