# CF-013 공통 분석 adapter·재무 연결 예제

정본 v1.0 SHA `1d2fe5a669a449e7dfaed035a7a2da1725be0c11af6470850cd76a617f512512`. clean 최신 develop `215c8ab1a39c5eb9f15d1501f8e6af3e1a03efde`(PR17 병합)에서 `refactor/analysis-adapter-contract`로 착수했다. 허용16경로이며 CF-012 정본/기록·API/DB migration/AI·Frontend 제품·실재무 service는 변경하지 않는다.

불변 context/frozen JSON/hash와 작은 Protocol을 Flow 제품의 build/validate/stage에 연결했다. claim·owner·상태·트랜잭션·충돌/삭제는 기존 service에 남겼다. 재무는 미등록 합성 예제·기존 mirror 검증·원 JSON 보존과 명시 writer stage만 구현했다. 제품 source의 독립 정적 검토와 실제 검사는 구분한다.

검사는 신규 unit 단일 파일의 명시 wrapper3으로 기존 baseline1·충돌2를 호출하고, 새 공통/adapter 회귀만 수집한다. 실제 PG는 기존 도구로 새 자기 자원을 생성해 Flow adapter 저장/본인 조회·replay·stage flush 실패 rollback/복구·타인 거부·삭제만 확인한다. 기존 CF-012 전체 suite/Frontend/build/browser는 반복하지 않는다. 재무 unit은 실제 DB·금융 게시 검증이 아니다. 실제 키/.env/캐시·기존 DB·외부 공급자는 사용하지 않는다.

최종 실행·정리·독립 검토 결과와 source/Git 인계는 아래에 기록한다.

## 최종 직접 검증·한계

- 새 `adapter-self`: 2/2 exit 0. exact source/단일 파일 선택·중립 stdlib import만 확인했다.
- 새 `adapter-unit`: **수집1파일·25/25 exit 0·guard0**. 신규 공통/Flow/재무 conformance와 명시 wrapper3(기존 public baseline1·publication 충돌2)만 실행했다. 기존 267개 전체는 반복하지 않았다. 원 schema/hash 및 충돌 terminal/rollback assertion은 유지했다.
- 새 `--verify-analysis-adapter-db`: **exit 0**, 실제 자기 PG readonly preflight·동일 연결 migration 후 3그룹을 통과했다. 정상 원자 게시/본인 조회/replay의 원 ID/hash 유지, stage flush 직후 실패의 root/자식/index rollback·result_ready 보존과 AI 재호출 없는 복구, 타인 거부·삭제 tombstone/replay 비노출이다. 분석 ID2개 / deterministic dispatch2회(각1), scoped private/network/HTTP/dotenv denial은 모두0이다.
- CID `8054b7a68894a5ef24bfc587571886108512b7531ce02b772bcf91c18df008cb`, resource `CF-002-login-606338fa8df9`. 원래 full guard 기반 runner 정리 뒤 정확 CID absent=true를 별도 읽기 확인했다. 다른 자원/기존 DB·volume은 조회/변경하지 않았다. 보호 self/unit의 자기 root도 제거됐다.
- 순수 재무 예제의 auth는 unit에서 mock되고 writer는 메모리다. 실제 재무 사용자 인증·owner-aware DB 게시·rollback/조회/삭제를 통과한 것이 아니다. 기존 owner=None/자체 commit 재무 service는 미통합이다. 실제 공급자·키/.env·사용자 cache·기존 DB·Google·브라우저/React는 미실행이며 새 설치는 없다.

제품 source 독립 정적 검토와 exact 선택/기존 guard 불변 검토를 수용했다. 위 실행은 개발 측 직접 결과이며 독립 runtime 재실행이 아니다. Backend worker/OS·FS·network/ASGI·소유 guard는 바꾸지 않았다. 새 API/DB migration·AI/Frontend 제품 변화도 없다.

증거 checkpoint: `/private/tmp/cf013-baseline-cisxt4dt`. `self-1.log`, `unit-1.log`, `pg-1.log`, `pg-absence.json`, `pg-source.json`을 보존했다. 성공 source와 최종 bytes를 대조한 뒤 결과 기록만 마감했다. 실제 Git 시점의 base/head/origin·외부변경·staged·ignore·파일 identity를 확인한다.

## 인계

정확16경로의 `final-source.json`과 NUL pathspec, 아래 marker 사이와 byte가 같은 PR body를 checkpoint에 보존한다. 후속 재무 구현은 [필드맵·stage 인수 조건](../examples/fundamental-analysis-adapter.md)을 적용하고 owner-aware writer/실제 PG·인가·서비스 인증·자료/시점·비용 경계를 별도 확인해야 한다. 공통 계약 존재는 실제 게시/외부 연동 완료나 승인이 아니다.

권장 commit: `refactor(analysis): extract Flow adapter and synthetic financial example`

<!-- CF013_PR_BODY_START -->
Flow 제품의 요청 생성·결과 검증/고정·동일 transaction stage를 실제 사용하는 공통 Protocol로 추출합니다. 원장 claim·owner·상태·ACK 복구·commit/rollback·충돌/삭제 fence는 기존 service에 유지하고 API/DB/AI/Frontend 제품 계약은 바꾸지 않습니다.

- 불변 context와 canonical 원 JSON/hash/원 report UUID 결합을 검사합니다. 재무는 미등록 합성 응답·기존 mirror·명시 writer 예제로 제공하며 기본 writer 없음은 fail-closed입니다.
- 새 self2·단일 unit파일25(wrapper 기존 baseline1/충돌2 포함) 통과. 실제 자기 PG 3그룹에서 원자 저장·동일 ID/hash replay·flush 실패 rollback/snapshot-only 복구·타인 거부·삭제를 확인했습니다. 분석2/dispatch2·guard0·자기 CID 정리/부재를 확인했습니다.
- 실제 재무 인증/owner-aware DB 게시·실 공급자·Google·브라우저 E2E는 미검증입니다. 기존 재무 owner=None/자체 commit service는 연결하지 않았으며 후속 writer/인가·자료/시점·호출/비용 검증이 필요합니다.
<!-- CF013_PR_BODY_END -->
