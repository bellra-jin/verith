# CF047 · 새 인증 세션의 Flow 저장본 복구

기준 develop: `a48c68c79882eb5218fdbe605dbbbe0f42dba6d7`. 기존 main Technical WIP, 이전 실제 실행과 예약 기록, 머지 보류 PR61은 변경하지 않는다.

현재 owner 저장·조회 SQL에서 확정 제품 결함은 발견하지 않았다. 기존 CF029의 한 합성 coordinator 저장본으로 새 SQL 발급 A2의 전체 보고서·목록과 동일 confirmation replay를 확인한다. 기대 payload는 committed run의 원 result JSON과 SHA에서 얻고 기존 JSON 타입 보존 비교로 검증한다. 새 모델/Flow dispatch·예약/정산 변화는 계수뿐 아니라 원 run과 회계 행 전체로 대조한다.

고정 `--verify-flow-owned-report-read-db`는 기존 owned parent와 Backend exec bootstrap만 재사용한다. Frontend 복사·기동은 없고, 두 자식은 다른 PID/nonce로 같은 제한 DB를 읽는다. Backend 기본 분석 gate는 켜지 않는다. Supervisor binding replay/GET는 parent ASGI, 자식 관측은 Flow 보고서 GET이다. A2 철회와 index만 제거한 fixture 음성 뒤 본문 미노출을 확인한다. 시작 probe의 합성 쓰기는 outer rollback이며 committed rows 불변을 별도로 검사한다.

원 epoch UUID와 DB driver의 UUID 하위 타입 사이에 있던 합성 조립 호환 누락은 신뢰된 SQL 반환 경계에서 stdlib UUID로 정규화했다. 문자열·숫자·bytes·UUID 유사 일반 객체는 거절하며 제품 strict 타입 검사는 유지한다. 실제 실행의 동결된 소스/기록을 수정하지 않는다.

`google_login_bootstrap.py`와 `google_login_inputs.py` 원본은 수정하지 않았다. 내용 독립 검토 뒤 정확한 readonly source pin 두 개만 추가했다. 가짜 Google 설정·owned HOME·dotenv-disabled 사본·제한 DB DTO/anonymous pipe·연결 attestation·PID/PGID/start-time·포트/nonce readiness·정리를 유지한다. 기대 payload와 private anchor는 부모 메모리에만 유지한다. cookie는 인증된 localhost GET 헤더로만 전달하며 bootstrap DTO·로그·환경·argv·파일에는 넣지 않는다. 전체 고정 300초 중 작업은 최초 270초 안에 끝내며 정리에도 원 300초 절대기한과 Docker 잔여 timeout을 적용한다. 만료/미정리는 실패로 남긴다.

## 검증 상태

- 보호 `meaning-assembly-self`: 4개 통과.
- 보호 단일 `meaning-assembly-unit`: 146개 통과, guard 위반 0. 실제 nested 응답 판정·asyncpg UUID 타입·Backend-only source/HOME·nonce/PID/port/readiness·취소/실패/정리·원본 변조·private anchor·기한 회귀다.
- 첫 owned PG 회차는 기존 조립의 epoch 주입에서 중단됐고 DB/source copy 정리는 확인했다. UUID 경계 수선 뒤 최종 CF047 모드는 exit 0·10그룹을 통과했다. 두 Backend exec는 서로 다른 실제 PID였고, 각 새 engine/연결이 동일 owned DB identity를 재검증했다.
- A2 전체 payload·목록·동일 binding, B404/목록 미포함, A2 철회401/A1 유지, index만 제거한 root의404/목록 제외가 통과했다. 합성 Flow dispatch는 총1이고 재조회로 추가된 dispatch·의미 모의 호출·예약·정산은0이다. 원 unknown hold 해시와 run/회계 행도 그대로였다. provider call 행9개는 모두 `not_called`인 합성 슬롯이며 외부 호출 증거가 아니다.
- 두 자식의 exit/reap·listener 부재, 자기 DB와 Backend workspace/source copy 제거 및 source299·dependency/origin 사후 대조가 통과했다. 이후 별도 읽기로 두 PID·8200 listener·정확 owned CID의 부재와 원 source299 불변도 확인했다. source copy 부재는 기존 owner postcheck 기록으로 구분한다.
- 독립 읽기 검토에서 발견한 자식 Supervisor gate와 cleanup 상대기한 문제를 수정했고 재검토에서 차단 결함은 없었다. 최종 exact-head 원격 CI/Ready PR/merge 결과는 별도 확인 후 인계한다. 로컬 실제 PG 수용을 원격 CI가 실행했다고 쓰지 않는다.

합성 SQL 세션은 Google 로그인 증거가 아니며, 일회용 DB에서 commit된 저장본 복구는 영구 사용자 보관함/운영 배포 수용이 아니다. 실제 provider·환경파일/키·추가 패키지·기존 DB 접근은 없다. 이전 Supervisor 보수 예약 $0.50은 불변이다.
