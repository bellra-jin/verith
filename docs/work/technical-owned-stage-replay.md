# 이미 저장된 Technical 결과의 정확한 stage 재요청

기준 develop `68f3333f39f773dbae32049c04bb7eb9abe846f1`에서 기존 internal stage의 저장 ID 충돌 경로만 보완했다. 기존에는 동일 결과도 ID가 존재하면 항상 충돌했다. 지금은 Principal 재인증→root FOR UPDATE 뒤 기존 read의 SQL owner·정확 한 index·snapshot/hash/context·모든 자식 projection 검증과 FrozenAnalysisResult 전체 비교를 재사용한다. 동일한 저장본에만 기존 참조를 반환하며 새로운 행·flush·commit·원래 저장 session 변경은 없다. 새로운 로그인 session에서도 현재 인증과 저장 당시 session을 구분한다.

다른 입력/결과, 다른 owner·legacy, 잘못된 snapshot/index/children은 계속 충돌한다. source TEXT·정수/소수 표현·binding을 정규화해 맞추거나 덮어쓰지 않는다. 공유 read 입구의 해당 Backend 서비스 exact pin 한 개만 갱신하며 허용 집합·guard·패키지·AI/Frontend·기존 실행/소비 자료는 불변이다.

보호 unit 72개 통과, guard 0·자기 root 제거 확인. 신규 회귀는 정확한 재요청/새 로그인/원래 session 유지·쓰기 0과 서로 다른 유효 결과·입력·owner·손상/중복 index 거절을 확인한다. 기존 고정 owned PG 입구로 실제 SQL의 SELECT-only 재요청, 관련 없는 dirty ORM 변경의 미flush·caller rollback, 다른 입력/owner 충돌과 기존 저장본 불변을 검증한다. 보호 self 3개와 실제 PG 7그룹이 통과했다. 신규 SELECT-only/dirty caller session 및 충돌 회귀, 기존 동시 최초 저장 PK 경쟁·ACK 불명 GET-only·손상 거절·downgrade 보호를 확인했다. source/dependency/origin 전후 검사와 정확한 소유 DB·source copy 제거도 통과했다. 최초 두 PG 회차는 오래된 c350 revision 고정 단언 때문에 실패했으며 기록을 보존했다. checker는 단일 copied source head와 CF035 계보를 확인하고 실제 DB 및 실패 downgrade 후 revision을 같은 head와 대조하도록 두 단언만 호환 수정했다.

이번 변경은 이미 존재하는 저장본에 한정한다. 없는 ID의 동시 최초 저장은 기존 PK 경쟁/충돌을 유지하며 이를 원자적 replay winner로 바꾸지 않았다. commit ACK 불명은 여전히 GET-only이고 이 stage 재요청을 새 실행 근거로 쓰지 않는다. 새 Technical admission/run profile·사용량 정책·Supervisor 확정 dispatch·운영 engine 조립은 미완료다. 실제 KIS/OpenAI·키/.env·새 설치·기존 DB·사용자 프론트를 실행/변경하지 않는다.
