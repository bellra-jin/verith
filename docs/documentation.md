# 문서 목록과 권위

## CF-023 근거 있는 의미 보완과 고정 준비

[정책/준비 계약](contracts/supervisor-core-v1.md)·[production 채팅 디자인](design/supervisor-core.md)·[직접 검사와 한계](work/CF-023-supervisor-meaning.md)를 따른다. 새 policy2는 원문/답변 span의 닫힌 의미 대응·잔여를 검증하고, 한 번 준비한 계획을 저장해 기존 owned Flow binding에 단일 소비한다. policy1 hash/replay와 기존 Flow 회계는 유지한다. 실제 OpenAI key 전송 및 계수 요금 상한 증거는 pending이며 production gateway는 닫혀 있다. 합성 보호 검사/소유 PG와 실제 모델 품질·1440/390 브라우저 수용·원격 CI를 구분한다.

## CF-022 Supervisor core와 단일 채팅

[core 계약](contracts/supervisor-core-v1.md)·[단일 채팅 디자인](design/supervisor-core.md)·[직접 검사/차단 기록](work/CF-022-supervisor-core.md)을 따른다. 원질문/조건·명확화·부분 범위 동의와 기존 owned Flow를 연결한다. production 의미 모델은 unavailable이다. Frontend caller의 metadata/source provenance 분리와 기존 strict worker 수용, self3/unit49·Frontend82/type/lint·소유 PG13그룹은 직접 통과했으며 실제 브라우저·모델 미검증과 원격 CI 대기는 구분한다. 후속 Technical·재무·멀티턴/운영 활성화를 이번 범위로 섞지 않는다.

## CF-020 Supervisor 자연어 준비와 Flow 연결

[계획 계약](contracts/supervisor-flow-plan-v1.md)과 [source/검증/차단 기록](work/CF-020-supervisor-flow-orchestration.md)을 따른다. AI가 무비용 의도/계획을 소유하고 Backend가 canonical resolver·인증·owner·기존 usage/coordinator를 소유한다. 준비는 실행권이 아니며 News·미지원 관점을 Flow로 대신 실행하지 않는다. pending/known ID 복구와 admission snapshot은 보존한다. 이전 사용자 직접 Git 안내보다 이번 작업의 명시 위임이 우선하며 실제 최신 head/Ready CI·독립 검토·검증 범위를 구분한다.

## CF-019 Flow 표시·삭제 UX

[표시/삭제 계약](contracts/flow-display-quality-v1.md)·[활성화 없는 한도 안내](flow-usage-configuration.md)·[이번 실행/미검증](work/CF-019-flow-quality-delete-ux.md)을 따른다. 기존 숫자/해석·Backend/DB/회계는 보존하며 실제 React 합성 클릭과 helper/source assertion을 구분한다.

## CF-018 Flow 사용 한도·보수 예약

[사용 한도 v1](contracts/flow-usage-v1.md)·[구현/검증 상태](work/CF-018-flow-usage-limits.md)를 따른다. 인증 사용자·Flow 실행·실제 호출 단위의 제한이며 미설정은 새 admission만 닫는다. $0.9135 예약·usage 추정·unknown hold는 실제 청구와 구분하고 미편입 관점을 통제한다고 주장하지 않는다. 최종 UX/승인 순서는 전체 작업 운영 v1.2 §4.1을 유일한 현재 기준으로 참조하며 이 문서에서 새 로드맵을 만들지 않는다.

## CF-017 Flow 오류 분류

[내부 오류 계약](contracts/flow-analysis-v1.md#flow-내부-오류-분류-cf-017)과 [구현·집중 검사 기록](work/CF-017-flow-error-classification.md)을 따른다. 입력422·공급자/서비스503·deadline504·명시적 결과502를 분리하며 기존 coordinator/저장/API 계약은 유지한다. 별도 실제 실행은 Google 로그인→삼성전자005930 KIS/OpenAI 분석→저장·같은 결과 재조회→UI 삭제·404·임시 자료/자원 정리까지 확인했다. 개발 측 합성 검사와 전달받은 실제 실행/독립 artifact 검토를 구분하며, [범위와 남은 조건](flow-live-readiness.md#공급자-실행-전-남은-경계-cf-017)을 따른다. 단일 종목 검증이며 deleted enum UI·운영 전반·실제 청구서와 원격 CI/PR/병합의 당시 대기 문장은 이력이다. CF-017 PR #22는 develop `d6efac632ca87b194e4025892c3741815039d2b5`에 병합됐으며 head `e7db7aba1226bb91f93739c79bac70d5dafe74a9`의 Ready 이후 [CI42555725577](https://github.com/bellra-jin/verith/actions/runs/42555725577) 성공을 조율 측이 별도 확인했다.

## CF-010 Docker 합성 HTTP 검증 상태

CF-010 PR #14 병합 뒤 최신 develop `233f674c1fd42d2bb75c995df415c3629ef519cd`의 [후속 실제 회차](work/CF-010-docker-synthetic-demo.md)는 **전체 exit0**으로 완료했다. Verith lock 기반 ignore-scripts 설치와 network-off 후 production build·TAP 두 HTTP 시험·사후 container source/hash·사후 network-off·host source 확인·자기 CID 제거/부재/label0이 통과했다. runner의 BASE·BRANCH 고정값 두 개와 실행 manifest·문서2개만 갱신했다. 이전 PR의 exit1/미실행은 당시 이력으로 보존한다. 실제 Backend/DB·Google/provider·React/브라우저와 Mac harness 자체 수용은 별도다.

## CF-009 보호 시험 flag 전달

CF-008 PR #12 병합 `fb29bf322024f93507d45a8e57ee8605414e5b40` 위에서 보호 preload와 fork 환경의 exact demo flag 검증·부모 값 보존을 보완했다. [구현·self-test·미검증 경계](work/CF-009-flow-demo-test-flag.md)를 따른다. 순수 함수/제한 VM·forkPlan 반환값 검증이며 실제 Next worker·HTTP·React/브라우저 전달 성공을 뜻하지 않는다. 기존 build 입력 차단은 그대로이며 아래 CF-008의 flag 삭제 설명은 당시 이력이다.

## CF-008 현재 합성 웹 기준

CF-007 PR #11 병합 `d5c0a1dea251728598fb45556303d77b0ab2c014` 위에서 default-off 합성 데모의 Backend/BFF/UI를 연결한다. [웹 계약](../backend/docs/flow_synthetic_demo.md)·[source/검증/실행 한계](work/CF-008-flow-synthetic-demo.md)를 따른다. 실키/API/기존 보관함 게시는 포함하지 않으며 Next HTTP·실제 React/브라우저 증거와 helper/source 검사를 구분한다. 기존 build guard 및 demo flag 전달 제약은 미해소다.

## CF-007 현재 내부 실행 기준

CF-006 PR #10 병합 `70d49b3eacccabd1db7bf2ea53cf678102f81bc7` 위에서 합성 입력→명시 opt-in→fake 일회 실행→내부 결과 원자 저장→본인 재조회를 연결한다. [내부 계약](../backend/docs/flow_fake_execution.md)·[구현/검증](work/CF-007-flow-fake-execution.md)을 따른다. 공개 API/기존 보관함 게시·실제 KIS/AI는 포함하지 않으며 아래 이전 결과와 구분한다.

## CF-006 현재 입력 준비 기준

PR #9 병합 `5c980528c01991cd3e71fb8d4eab448c56c90f0c` 위에서 합성 입력 snapshot 봉인·실제 principal/owner 재조회만 추가한다. [내부 계약](../backend/docs/flow_input_snapshot.md)·[구현/검증/실패 이력](work/CF-006-flow-input-snapshot.md)을 따른다. 공개 API·receipt_only 상태·AI 실행·원 payload는 불변이며, 아래 이전 단계 수치는 각 당시 이력이다.

## CF-005 현재 표시·입력 기준

PR #8 병합 `a6f27aa53c376bbfc5c3e8679aa50c9c02869518` 위의 Flow 관측기간 안내 보완이다.
[관측 정책](../ai/docs/contracts/flow/observation-window.md)·[구현/검증 기록](work/CF-005-flow-observation-window.md)을 따른다.
기존 숫자·payload·Gate·해석 원문을 보존하며 제공 관측 부족/미확인·안전 표시·인접 경고만 정정한다.
실제 원천 계산창/시장 coverage나 AI 실행을 검증한 것이 아니다. 아래 이전 단계는 당시 이력이다.


## CF-004 현재 무키 작업

PR #7 병합 `38c0b34a5741198484278767a7ada1c925f71301` 위의 Flow KIS 캐시 보완이다.
[캐시 계약](../ai/docs/contracts/flow/kis-token-cache.md)·[직접 검증 기록](work/CF-004-flow-kis-token-cache.md)을 따른다.
stdlib 캐시 문맥/strict 검증/안전 저장과 한정 보호 회귀이며 실제 키·캐시·KIS/AI 실행은 포함하지 않는다.
아래 CF-003/ST-001 안내와 숫자는 각 단계 이력으로 보존한다.

## CF-003 현재 작업 기준

현재 새 기능 기준은 PR #6 병합 `d67f731b1c2f452179d66abaa2b3381cccb8a15d`다.
[Flow 접수·멱등·본인 조회 계약](../backend/docs/flow_run_admission.md)과
[CF-003 실제 작업/검증 기록](work/CF-003-flow-run-admission.md)을 따른다.
receipt_only·기본 비활성이며 AI/worker 실행은 포함하지 않는다. 아래 7df1240·이전 검사 수치는
그 시점 이력이다. CF 공유 publication/manifest·ST-001 완료 기록은 그대로 보존한다.

> **최종 구조 우선 계약:** ST-001 v1.15(명시 Flow 설정·최종 marker 정리)에 따라 불필요한 old shim을 제거하며 canonical 구현 하나로 정리한다. Flow 마지막3도 AI 루트 .env 명시 정책으로 이동했다. 실제 설정 값/AI 실행은 미검증이다. [진행 기록](work/ST-001-layout-progress.md)을 따른다.

> **실제 이동 결정 당시 — ST-001 v1.10:** 전체 기능의 실제 이동 승인이 적용되며 [전체 진행 기록](work/ST-001-layout-progress.md)을 현재 상태로 봅니다. 아래 v1.7 작업 지시·source SHA·비교 보류 문장은 3-B 당시 이력입니다. Backend 59개 이동/보호 회귀와 FE-01 선택 type/lint 결과를 이력과 구분하며, 전체 AI/Frontend 이동 및 build/HTTP 수용 완료는 아닙니다.

문서 목록 버전 4 / 확인일 2026-11-08, Asia/Seoul (+09:00).
현재 작업 기준 `7df12403848e480f223767232540d4c2c055ba5e` (ST-001 3-A PR #5 병합).
CF 공유 계약과 기존 도메인 표의 검토 기준은 a5b60f2이며 작업 기준 갱신을 이유로 바꾸지 않는다.
문서가 있다는 사실은 해당 기능의 공개 허용·검증 완료·실제 환경 설정을 뜻하지 않는다.

현재 실제 폴더 이동은 [ST-001 전체 재배치 진행 기록](work/ST-001-layout-progress.md)을 따른다.
이전 3-B 검사 이력과 이동 batch별 직접 검증·미검증을 구분한다.

## 현재 개발 시작점

1. [루트 README](../README.md)와 [root 작업 안내](../AGENTS.md), 해당 서비스의
   [Frontend](../frontend/AGENTS.md)·[Backend](../backend/AGENTS.md)·[AI](../ai/AGENTS.md) 안내를 읽고
   [현재 책임/DB 경계](architecture/current-boundaries.md)를 확인한다.
2. 아래 표에서 수정할 도메인의 계약과 코드 기준을 고른다. Technical 계약을 Flow나 전체 서비스 계약으로 확대하지 않는다.
3. [포트/설정 안내](local_ports.md)와 서비스별 [Frontend](../frontend/README.md)/[Backend](../backend/README.md)
   README, [공용 환경 참고](development.md)를 확인한다. 서비스 실행·migration·seed·DB/Google/AI 검사는 문서 열람의 부수 작업이 아니다.
4. [검증 상태와 이력](#검증-상태와-이력)을 확인하고 필요한 승인/격리와 실행 범위가 없으면 실제 자원 검사를 시작하지 않는다.

## 권위와 충돌 처리

사용자의 최신 제한과 해당 작업의 확정 지시, 해당 도메인의 확정 공유 계약, 검토한 코드/실행 근거를
대조한다. 문서가 없거나 과거/다른 도메인이라면 코드가 틀렸다고 기계적으로 판단하지 않는다.
충돌의 출처·영향·권장안을 작성 담당에게 보고하고 확정 계약을 먼저 맞춘다. 구현 차이를 문서로
숨기거나 새 범용 contracts/api_spec 파일을 복제해 독립 정본을 만들지 않는다.

| 역할 | 파일 / 소유 범위 | 버전·기준 / 현재 상태 |
|---|---|---|
| 작업 지시 원본 | 외부 CF/ST 지시서 | 원본은 저장소 밖에서 보존. clone에 없는 경로로 탐색 링크를 만들지 않음. 개인 운영 문서·실행 승인은 공유하지 않음 |
| 공유 지시 파생본 | [CF-001](contracts/CF-001-v1.1.shared-v1.md), [CF-002](contracts/CF-002-v0.6.shared-v1.md) | 현재 사용 publication **shared-v1** 각각. 원본 아님. source/snapshot hash와 절 대응은 [manifest](contracts/manifest.json) |
| DB 물리 구조 | [schema](../backend/docs/schema.md), [모델](../backend/db/models), [revision](../backend/db/migrations/versions) | a5b60f2 tree, auth 확장 head c2001a7e0001. 문서·ORM·Alembic 대조; 실제 DB 적용 여부는 별도 |
| DB 변경 절차 | [migrations](../backend/docs/migrations.md), [DB 경계](../backend/docs/db_boundaries.md) | 현재 안전 경로와 과거 canonical 운영 기록을 구분 |
| Flow payload/검증 | [v1 storage-spec](../ai/docs/contracts/flow/storage-spec.md), [exporter](../ai/src/agents/flow/api/payload.py), [validator](../backend/src/modules/flow/domain/payload.py) | payload version 1, CF-001+후속 CF-002 적용. storage-spec의 초기 미구현 설명은 이력 |
| Flow 인증/owner | [CF-002 공유 계약](contracts/CF-002-v0.6.shared-v1.md), [현재 경계](architecture/current-boundaries.md#현재-공개-경로와-데이터-책임) | Backend가 최종 principal/root-index 검증. 공개 save 허용 아님 |
| Technical JSON/enum/화면 | [contracts](../ai/docs/contracts/technical/contracts.md), [api_spec](../ai/docs/contracts/technical/api_spec.md), [frontend_mapping](../ai/docs/agents/technical/frontend_mapping.md), [enums](../ai/docs/contracts/technical/enums.md) | a5b60f2의 **Technical 도메인 문서**. 전체 서비스/Flow/auth 계약 아님. 현재 사용자 Technical 경로는 비활성 |
| Backend Technical API | [technical_frontend_api_contract](../backend/docs/technical_frontend_api_contract.md) | 저장/read model의 Technical 응답 계약. 현재 경로 공개/분석 실행 허가와 별개 |
| 공통 보관함 카드 | [report_archive_api_contract](../backend/docs/report_archive_api_contract.md) | 카드 shape/projection. CF-002의 현재 접근 허용은 본인 Flow만; 모든 agent 필터가 실행 가능하다는 뜻 아님 |
| 종목 식별/마스터 | [stock_resolver](../backend/docs/stock_resolver.md), [KIS master](../backend/docs/stock_master_sync.md), [DART corp code](../backend/docs/dart_corp_code_sync.md) | 종목 resolver·종목 마스터·법인 식별 레이어를 구분. 관리 sync는 수동 별도 작업 |
| Fundamental 직접 DB | [현재 관찰·호환·미확인 경계](architecture/current-boundaries.md#fundamental-직접-db-호환-경로) | SELECT로 필드 3개를 읽는 경로가 존재. 실제 최소 권한은 미확인. 새 API/자격/권한 변경 없음 |
| 개발 작성 가이드 | [Frontend](../frontend/docs/coding-guidelines.md), [Backend](../backend/docs/backend_coding_guidelines.md) | 현재 도메인 링크/실제 entry 참조. 예시 구조를 실제 재배치 지시로 쓰지 않음 |
| 공용 환경 참고 | [개발 안내](development.md), [Frontend](examples/frontend.env.example), [Backend](examples/backend.env.example), [AI](examples/ai.env.example), [명시 Compose](examples/compose.local.example.yaml) | ST-001 v1.3 / 3-A. 비밀 없는 참고, 실제 설정/기동 검증/안전 bootstrap 아님 |
| 구현/실행 이력 | [CF-001](../backend/docs/flow_contract.md), [CF-002](../backend/docs/flow_auth_ownership.md), [Google 검증 기록](../backend/docs/google_login_check.md) | 각 보고 시점·합성/실제·실패/미검증을 보존. 상단 현재 상태 주석과 본문 이력 분리 |
| 과거 PR 초안 | [CF-002 실행 명령](../backend/docs/cf002_commit_pr.md), [CF-002 PR 본문](../backend/docs/cf002_pr_body.md), [News 초안](../PR_DESCRIPTION.md) | **현재 실행 안내 아님**. 고정 HEAD stage/실제 자원 명령을 재사용하지 않음 |

## 외부 목표 설계와 출처

외부 **Verith_고도화_상세설계_v1.0.md**(v1.0)는 목표 아키텍처/안전 원칙,
**verith_고도화_mvp.md**(v0.1)는 단계 범위 제안이다. 원문은 이 clone에 포함하지 않는다.
논리 문서명·버전·source hash는 manifest의 reference_documents에 기록한다.
상세설계의 전체 실행/복구·다중 관점 목표를 현재 구현 완료로 읽지 않는다.

3-B 당시 작업 지시는 **ST-001_문서_정본과_안전한_개발_기반_정리.md v1.7 / 3-B**,
source SHA-256 `23e79f20066664ba8e32fb3c1a040e5bb33fdbfc08e44518c354ccee0e8b2601`다.
1단계 PR #3과 2단계 commit `9bf536e53ca7dab75d35b43200198c298a54ec0e`/PR #4가 병합됐고,
3-A commit `5eecd0b8c62ad56041e0b2a1bf888b9b053fd430`/PR #5도 병합됐다.
이번 작업 기준은 위 `7df1240`이며 새 미커밋은 3-B 검사 입구/보호/문서의 부분 구현이다.
manifest의 기존 v1.0·v1.1·v1.3 work_item은 work_item_history에 원형 보존하고 CF snapshot bytes/출처/버전/
hash/reviewed SHA와 reference_documents는 유지한다.

root·서비스 AGENTS는 2단계 병합 이력이며 Frontend 기존 Next 블록은 계속 보존한다. 3-A 공용 환경
예제는 병합됐으며 정적 검사·독립 수용·실제 기동 검증은 구분한다. **3-B는 Backend self-test 9개·unit 244개 통과, 최신 Frontend self-test 20개·unit 35개 통과, build 추가 소비 거부/최종 수용 대기**이며
3-C AI 안전 entry는 미구현 후속이다. [3-B 기록](work/ST-001-stage-3-B.md)과
[실행표](development.md#3-b-검사-입구와-현재-차단)를 따른다. 3-B 수용/사용자 병합 후 3-C로 진행한다.
큰 파일/폴더 재배치 구조는 비교 검토 전 **후보**이며 미확정이다.

## 검증 상태와 이력

ST-001 3-A의 16파일 정적 검사/독립 수용은 병합 이력이다. 현재 3-B의 23경로 구현에서는
수집 전 OS/언어 guard·자기 사본·선택 검사의 실제 검증이 필요하다. 현재 help/list/오류 인자·구문은 확인됐고,
이전 OS 실패·최소 probe와 별도 공식 실행한 Backend/Frontend self-test 9개/14개 통과를 구분한다. Frontend 기존 unit+safety 29개는 이전 source의 실제 통과다. 최신 v1.6 self-test 17개·unit 32개도 별도 공식 실행에서 통과했다. Backend는 v1.5의 정확한 입력 2개·origin 검증과 시스템 metadata literal 읽기 보완 뒤 고정 6파일 244개 통과·guard 0이다. Frontend build는 단일 package snapshot 응답 후 추가 파일 요청의 guard 거부로 실패했으며 HTTP/type/대상 lint는 미실행이다.
보호를 해제해 실행하지 않는다. 실DB/Google/AI 검사는 제외다. 아래 기능 수치는 병합된
**과거 CF 보고서 확인**이며 이번 문서 단계의 실행 결과가 아니다.

- CF-001 보고: unit 148·실제 격리 PostgreSQL 29·카드 4 통과 기록.
- CF-002 보고: Backend unit 343, Frontend 단위/BFF 15+로컬 합성 Next HTTP 3,
  type/build/대상 lint 통과. PG integration 54+seed 3 등은 보고서에 적힌 이전 회차다.
- 전체 Frontend ESLint는 기존 Technical explicit-any 오류 2건·unused 경고 3건으로 **실패**했다.
  대상 lint 통과를 전체 통과로 바꾸지 않는다.
- 실제 Google A/B 사용자 확인·일부 UI/내부 DB owner·본인 삭제·자기 임시 자원 정리 기록이 있다.
  자연 시간 만료·옛 cookie 재전송·A→B 반대 방향 교차 UI·개별 실제 HTTP/BFF 응답 직접 관측·
  B 상세 본문 명시 확인은 **미검증**이다. PR 병합은 이 검증의 추가 통과가 아니다.
- 기존 [Backend unit 경계](../backend/tests/unit/conftest.py)와
  [Frontend 사본 검사 도우미](../frontend/scripts/check-local-ports.mjs)는 존재한다.
  3-B 보강 입구는 OS/native/자손 보호와 선택 실행이 아직 검증되지 않았다. AI 전체 pytest를
  parent env만 지워 실행해도 안전하다고 가정하지 않는다.
- ignored Compose는 공유되지 않았고 실제 private override/현재 DB 자격·포트 상태는 미확인이다.
  원본 비밀 파일을 읽거나 기존 컨테이너/자료를 재현 검사 대상으로 쓰지 않는다.

1단계의 210개 독립 검토와 병합 전 작성/검사는 [1단계 기록](work/ST-001-stage-1.md)의 이력이다.
작성 채팅의 병합 tree 확인은 local path 190개 존재 검사이며 anchor/전체 재검사는 아니었다는
전달 기록과 구분한다. [2단계 기록](work/ST-001-stage-2.md)의 148개 검사/독립 재검토는 과거 이력이다.
3-A 예제의 직접 검사는 [3-A 기록](work/ST-001-stage-3-A.md)에 있다.
현재 직접 검사/미실행·차단은 [3-B 기록](work/ST-001-stage-3-B.md)에 구분한다.

## 공유본 갱신 절차

원본/확정 계약을 검토한 뒤 새 publication version 파일과 snapshot hash·manifest를 함께 갱신한다.
원본 source hash와 파생 bytes hash를 구분하며 manifest 자신의 hash를 내부에 넣지 않는다.
이전 snapshot을 보존하고 **현재 사용 버전은 이 목록에서만 지정**한다.
개인 이름/계정/프로젝트 정보·전체 로컬 경로·대화·원시 영수증·일회성 credential 승인은 공유하지 않는다.
오타/링크만 고쳐도 출판된 snapshot의 새 버전과 hash를 기록한다.

v1.6 당시 self-test 17개·unit 32개는 통과했다. build는 3회 모두 추가 파일 요청의 guard 거부로 exit 78·자기 root 정리였다. 최초 거절·실패·후속 거절과 승인된 재개를 이력으로 구분한다. worker fs 관측/부분 journal과 native 합성 canary·부모 공개 source 검증을 분리하며 native 전체 0을 주장하지 않는다.

v1.7 진단 한정 실행은 self-test 20개·unit 35개 통과, build는 거부 22회/정규화 target ID 10개로 exit 78이다. 이 중 cgroup 1개·4회, unknown hash 9개·18회이며 hash 대상의 known-copy membership은 모두 false다. HMAC 식별을 읽기 허용에 쓰지 않으며 추가 build/HTTP/type/lint는 새 정책 판단 전 진행하지 않는다. 앞선 v1.6 수치·실패는 당시 이력이다.

### CF-012 Flow 인증 분석

- [요청·실행·본인 저장 계약](contracts/flow-analysis-v1.md)
- [CF-012 구현·검증 기록](work/CF-012-flow-analysis.md)

### CF-013 실제사용 adapter와 재무 합성 예제

- [분석 adapter 공통 계약](contracts/analysis-adapter-v1.md)
- [재무 adapter 필드맵·stage 인수 조건](examples/fundamental-analysis-adapter.md)
- [CF-013 구현·집중 검증](work/CF-013-analysis-contracts.md)

- CF-014: [선택형 해석 정책](contracts/flow-interpretation-policy-v1.md) · [구현/검증 및 원격 CI](work/CF-014-flow-quality.md)

## CF-015 · Fundamental owned analyses

[Contract](contracts/fundamental-analysis-v1.md), [adapter handoff](examples/fundamental-owned-analysis.md), [execution record](work/CF-015-fundamental-owned-analysis.md). This adds current-time request context and owned storage, not verified financial source snapshots or historical analysis.

## CF-016 · Flow 상태 재조회와 인수 안내

[Flow 실제 연동 준비 항목](flow-live-readiness.md)·[현재 재무 production 인수 안내](examples/fundamental-owned-analysis.md)·[변경/검증 기록](work/CF-016-flow-observation-handoff.md). Flow는 최초 기한/단조 시간으로 bounded 자동 관측하고, 명시 GET-only 상태 복구와 same-key POST snapshot 게시 복구를 구분한다. 재무 as_of는 엔진 기록 시각이며 자료 기준일은 미확인이다. 실제 설정/키/서비스/공급자·브라우저 수용을 뜻하지 않는다.
