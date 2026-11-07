# ST-001 v1.0 · 1단계 구현/검증 기록

> **현재 병합 상태 주석 · 2026-11-07T22:57:03+09:00**
> ST-001 1단계는 사용자 commit `7aab357ae9e358dc7ab34320e4e5eecc1ae56288`의
> [PR #3](https://github.com/bellra-jin/verith/pull/3)으로 develop에 병합됐다. merge/head 검토 기준은
> `083dea8436b699aa3a52ddbf36848e8fe3535720`다. 전달된 원격 mergedAt은 22:42:40 KST
> (`2026-11-07T13:42:40Z`)이며 이번 fetch/로컬 Git 그래프로 포함과 파일 차이 0을 직접 확인했다.
> 아래 본문의 미커밋/병합 대기·당시 검사/실패/미검증·명령은 **1단계 작성 당시 이력**으로 보존한다.
> 현재 별도 미커밋 작업은 `docs/repository-work-guide`의 ST-001 v1.1 2단계다.
> 이전 210개 독립 검토를 이번 추가 문서의 검사로 재사용하지 않는다.
> [현재 문서 목록](../documentation.md)·[2단계 기록](ST-001-stage-2.md)을 따른다.

- 기록 시각: 2026-11-07T18:57:00+09:00 (Asia/Seoul, +09:00).
- 상태: P2 1건 수정·자체 재검증 및 수정 후 독립 재검토 통과. 사용자 commit/push/Draft PR/병합 대기. 2단계 이후는 이 단계의 사용자 병합 후 진행.
- 지시 원본: ST-001_문서_정본과_안전한_개발_기반_정리.md v1.0,
  SHA-256 `1b7975913e92ff08065b2094879075fbe796e6e57d6227890b8bc92a772c5010`.
- 읽은 운영: 전체 작업 v1.1/지시서 작성 v1.2/코드 개발 v1.2. 각 source hash를 수신값과 대조했다.
- 시작 branch feat/flow-auth-ownership/HEAD 7a5853d, staged/unstaged 0·worktree 1·동명 branch 없음.
  develop 전환→실제 origin fetch 성공→ff-only 최신화→`docs/document-authority` 생성 순서를 지켰다.
- 기준 develop/origin develop/작업 HEAD: `a5b60f2fd0b00efedae2c98a2004ede62470b094`. 원격이 전달된 merge보다 앞서지 않았다.
  선행 7a5853d→a5b60f2의 파일 차이 0, parent 포함/merge commit 제목을 직접 확인했다.
  PR #2 merged 시각 18:22:15 KST (`2026-11-07T09:22:15Z`)는 전달된 원격 조회 기록이며,
  이번 직접 Git commit metadata의 committer 시각 18:22:14 KST와 출처를 구분한다.
- 현재 문서 수정은 미커밋/미스테이징. 과거 CF-002 구현은 이미 commit/병합된 상태다.

## 구현 범위

[문서 목록](../documentation.md)·[현재 책임/DB 지도](../architecture/current-boundaries.md),
[공유 CF-001](../contracts/CF-001-v1.1.shared-v1.md)/[공유 CF-002](../contracts/CF-002-v0.6.shared-v1.md)와
[manifest](../contracts/manifest.json)를 추가했다. README/서비스 README·두 가이드의 실제 경로를
맞추고, Technical 범위와 현재 Flow 인증/owner 경계를 분리했다. 기존 포트폴리오·실행 당시 본문은
보존하고 현재 commit/PR 상태 주석을 추가했다. 과거 고정 HEAD stage 명령은 현재 실행 안내가 아니다.
Flow handoff의 상대 링크 4개 정정 외에 과거 본문을 새 사실로 덮어쓰지 않았다.
Fundamental은 SELECT 호환 사실/실제 role 미확인/후속 API 계약을 나눴으며 동작을 바꾸지 않았다.

## 직접 검사와 제외 범위

임시 `/tmp/st001_doc_check.py`(이번 검토 환경의 일회용 stdlib 도구, 저장소에 추가하지 않음)로
현재 탐색 대상과 새 문서의 Markdown local path/anchor를 검사하고, 과거 보고서는 새 상태 prefix와
기존 본문 보존을 구분했다. README·두 가이드·새 문서는 전체 로컬 링크를 검사한다.
외부 HTTP 링크·전체 저장소 역사 문서·코드 블록의 비실행 예시는 검증 범위가 아니다.

최종 링크/구문/범위 검사 수치는 아래 최종 결과 절에 기록한다. permanent 검사 entry는 후속 3단계다.
기능/unit/type/build/lint·DB/Google/AI·Docker 검사는 **미실행**이다. 문서 전용 범위라 필요 없고
과거 실행 승인도 승계하지 않는다. 과거 CF 보고의 343/15+3 등은 보고서 확인이며 이번 직접 통과가 아니다.
전체 Frontend lint 기존 explicit-any 오류 2건/unused 경고 3건 및 자연 시간 만료·옛 cookie·A→B 교차 UI·
개별 실제 HTTP/BFF 직접 관측·B 상세 본문 명시 확인의 미검증은 보존했다.

## 출처와 파생 hash

원본 bytes/source hash와 shared-v1 파생 bytes/hash는 별개이며 source version은 payload version이 아니다.

- CF-001 v1.1: source `ff92ece459e42f707cc723e9dda7b2e353b423c8c2c1bfa60db37e7262d83c08`, snapshot `bf8e8bb84c8ba80a8fa7f074b12b0b92a53b732389928f2684158236394fe8d7`.

- CF-002 v0.6: source `00fb44149066602152002910b446004289de8b3eed1410b8f554dd873b5d32eb`, snapshot `97fb8d2480f5129d690370e71ef8a3db6e39d9372f6d84cf47c24a6c23477ff3`.

외부 원본·개인 운영 문서를 복사/수정하지 않았다. 새 공유 문서에서 개인 이름/계정/프로젝트·Mac
경로/대화·원시 PID/CID/nonce·일회성 credential 승인을 제외하고 변수가 필요하면 공개 이름만 썼다.
원본이 clone에 없다는 한계를 명시하되 공유 계약은 원본 없이 읽을 수 있게 작성했다.

## 변경 파일

- [PR_DESCRIPTION.md](../../PR_DESCRIPTION.md)
- [README.md](../../README.md)
- [backend/README.md](../../backend/README.md)
- [backend/docs/backend_coding_guidelines.md](../../backend/docs/backend_coding_guidelines.md)
- [backend/docs/cf002_commit_pr.md](../../backend/docs/cf002_commit_pr.md)
- [backend/docs/cf002_pr_body.md](../../backend/docs/cf002_pr_body.md)
- [backend/docs/db_boundaries.md](../../backend/docs/db_boundaries.md)
- [backend/docs/flow_auth_ownership.md](../../backend/docs/flow_auth_ownership.md)
- [backend/docs/flow_backend_handoff.md](../../backend/docs/flow_backend_handoff.md)
- [backend/docs/flow_contract.md](../../backend/docs/flow_contract.md)
- [backend/docs/google_login_check.md](../../backend/docs/google_login_check.md)
- [backend/docs/report_archive_api_contract.md](../../backend/docs/report_archive_api_contract.md)
- [backend/docs/technical_frontend_api_contract.md](../../backend/docs/technical_frontend_api_contract.md)
- [docs/architecture/current-boundaries.md](../../docs/architecture/current-boundaries.md)
- [docs/contracts/CF-001-v1.1.shared-v1.md](../../docs/contracts/CF-001-v1.1.shared-v1.md)
- [docs/contracts/CF-002-v0.6.shared-v1.md](../../docs/contracts/CF-002-v0.6.shared-v1.md)
- [docs/contracts/manifest.json](../../docs/contracts/manifest.json)
- [docs/documentation.md](../../docs/documentation.md)
- [docs/work/ST-001-stage-1-commands.md](../../docs/work/ST-001-stage-1-commands.md)
- [docs/work/ST-001-stage-1-pr.md](../../docs/work/ST-001-stage-1-pr.md)
- [docs/work/ST-001-stage-1.md](../../docs/work/ST-001-stage-1.md)
- [frontend/README.md](../../frontend/README.md)
- [frontend/docs/frontend_coding_guidelines.md](../../frontend/docs/frontend_coding_guidelines.md)

## 남은 일과 사용자 실행

독립 검토→P2 수정/재검증→독립 재검토 수용을 마쳤다. 이제 사용자 commit/push/Draft PR/병합을 기다린다. 그 전 root AGENTS나
다음 브랜치를 만들지 않는다. 큰 파일/폴더 구조는 비교 판단 전 미확정이다. 현재 권한/DB/포트/서비스
실환경을 새로 확인하지 않았고 ignored compose/private env는 보존했다.

권장 commit: `docs: establish document authority and shared Flow contracts`

Draft PR 제목: **ST-001 1단계: 문서 정본과 공유 계약·현재 상태 정리**

[완성 PR 본문](ST-001-stage-1-pr.md), [사용자 직접 실행 명령](ST-001-stage-1-commands.md).
실제 add/commit/push/PR/Ready/merge는 수행하지 않는다.

## 최종 자체 검사 결과

2026-11-07T18:58:20+09:00 기준 최종 문서 23개(Markdown 22/manifest JSON 1개).

| 직접 검사 | 결과 / 범위 |
|---|---|
| 지정 현재 탐색 local path/anchor | **206개 통과·실패 0**. README/두 가이드/새 문서 전체, 과거 보고의 새 주석 범위. 외부 HTTP 링크 10개는 요청하지 않았으며 전체 저장소 역사 문서 검사 아님 |
| 역사 기록/포트폴리오 | 기존 본문 보존. Flow handoff 링크 4개만 절대→상대 target으로 정정. 선택된 역사 링크 중 미해결 0 |
| manifest | CF source 2개·파생 bytes hash 2개·source/publication 버전·reviewed SHA·절 대응/생략 확인. ST 원본과 설계/MVP source hash도 실제 bytes 대조 |
| 공유 제외 | 새 공유 계약/manifest/목록/책임 지도의 개인 경로/계정·대화·프로젝트 정보·원시 영수증·자격 승인 제외를 정적 패턴+내용 검토. 원본을 통째로 복사하지 않음 |
| 실행 영향 | 변경은 23개 문서 경로뿐, runtime/source/DB/schema/권한/환경 diff 0. .env/credentials/ignored Compose 조회·서비스/DB/Google/AI 실행 0 |
| 사용자 명령 | zsh 블록 4개 syntax-only 통과. stage/commit 허용 경로 23개와 현재 변경 경로 23개가 일치하며 staged 0. explicit repo/base/head+--draft와 branch/HEAD/origin/기존 staged guard 확인 |
| whitespace | git diff --check 통과 |

실행 명령은 임시 stdlib 링크/manifest 검사기와 별도 zsh -n·범위 대조, git diff --check다.
스냅샷 source bytes·내용을 읽었지만 private 환경 파일/자료를 읽지 않았다. 신뢰할 수 있는 전체
비밀 탐지 보장을 주장하지 않으며 계약 파생본의 실제 diff 검토가 필요하다.
필요한 함수/DB 테스트를 빠뜨린 것이 아니라 문서 전용 계약에 맞춰 기능 검사를 실행하지 않았다.
develop ff-only 동기화는 위와 같이 직접 수행했고 새 merge commit/PR merge는 만들지 않았다.
위 초기 자체 검사는 독립 검토 전의 기록이다. 아래 수정 후 자체 재검증과 독립 재검토 상태를 구분한다.

## 독립 검토 P2 수정과 재검증

수정 기록: 2026-11-07T19:05:53+09:00.

독립 검토에서 사용자 명령의 원격 URL guard 불일치 **1건(P2)**을 확인했다. 4개 zsh 블록의
origin/push-origin 기대값 8개에는 .git suffix가 없었으나, 읽기 전용으로 관측한 실제 fetch/push URL은
모두 `https://github.com/bellra-jin/verith.git`이었다. 그대로 실행하면 stage 전 origin mismatch로
중단되므로 **실제 원격 설정은 보존하고 8개 기대값만 관측 URL과 일치시켰다**.
`gh pr create --repo https://github.com/bellra-jin/verith`는 저장소 지정값이며 별도로 유지한다.

이번에 추가한 안내·주석·보고·PR 초안·공유 파생본의 일반 문장을 띄어쓰기 중심으로 다듬었다.
코드 블록·URL·정확한 식별자/경로/해시는 보호하고 과거 본문은 바꾸지 않았다.
최초 게시 전 shared-v1의 계약/범위는 유지했으며 두 파생 bytes hash를 새로 계산해 manifest와
위 보고 참조를 함께 갱신했다. 원본 source hash·source version은 그대로다.

검사 수의 차이도 구분한다. 초기 개발 자체 **206개**는 현재 탐색/새 문서/추가 주석 범위였고,
독립 검토 **210개**는 Flow handoff에서 정정한 상대 링크 4개를 더 포함했다. 둘은 서로 다른
범위의 결과다. 수정 후 직접 검사는 이 4개를 포함한 총 210개로 범위를 맞춰 다시 검사한다.
외부 HTTP나 전체 저장소 역사 문서가 검증됐다고 확장하지 않는다.

최종 직접 재검증은 링크/anchor·두 원본/두 파생 hash·공유 제외·역사 본문/포트폴리오 보존,
관측 origin/push URL 8개 대조·zsh 구문 4블록·stage/commit 허용 경로 23개·staged 0·runtime diff 0·
diff check를 대상으로 한다. git/gh 작업 블록은 실행하지 않고 읽기/구문 검사만 수행한다.
기능/서비스/DB/Google/AI·외부 HTTP는 계속 미실행이다. 기존 lint 실패·실제 인증 미검증과 구조
재배치 보류를 유지한다. **이 수정 기록 당시에는 독립 재검토 대기 중**이었다. 최종 통과 결과는 아래 마감 절에 구분한다.

### 수정 후 직접 재검증 결과

2026-11-07T19:07:00+09:00 기준:

- 실제 origin/push-origin을 읽기 전용으로 확인하고 **8개 guard 기대값 전부 일치**를 확인했다.
  두 관측값 모두 `https://github.com/bellra-jin/verith.git`이며 원격 설정은 바꾸지 않았다.
- 현재 탐색 206개 + 정정한 Flow handoff 링크 4개 = **총 210개 경로/anchor 통과**, 오류 0.
  초기 자체 206개와 독립 210개의 범위 차이를 위에 명시했다. 외부 HTTP는 검사하지 않았다.
- 두 원본/두 파생 hash·버전/절 대응, 파생 hash의 manifest/보고 참조가 일치했다.
  CF-001 파생 `bf8e8bb84c8ba80a8fa7f074b12b0b92a53b732389928f2684158236394fe8d7`,
  CF-002 파생 `97fb8d2480f5129d690370e71ef8a3db6e39d9372f6d84cf47c24a6c23477ff3`이다.
  원본 해시는 변경하지 않았다.
- zsh 블록 4개 syntax-only 통과, literal add/commit expected/실제 변경 집합 모두 23개로 일치.
  개인/비밀 제외·과거 보고 본문/루트 포트폴리오 보존·runtime diff 0·staged 0·diff check 통과.
- git/gh action 블록은 실행하지 않았다. 문서 전용 정정이며 계약/단계 범위 변경은 없다.
  **당시에는 독립 재검토 대기** 상태로 반환했다. 실제 검사/서비스/DB/Google/AI는 실행하지 않았다.

## 독립 재검토 통과 · 1단계 마감

결과 수신·기록: 2026-11-07T19:09:59+09:00.
아래는 독립 검토자가 직접 재실행한 결과의 전달 기록이다. 이번 마감 편집에서 동일 검사를
새로 실행한 것으로 표시하지 않는다.

- actual origin/push URL과 8개 guard의 `.git` 포함 값 일치.
- 로컬 경로/anchor 210개 오류 0. 초기 자체 206개와 추가 handoff 링크 4개의 범위 차이 유지.
- CF 원본 2개/파생 2개/ST 원본 hash, manifest와 보고 참조 일치.
- zsh 블록 4개 syntax-only 통과. literal add/commit expected/실제 변경 집합 23개 일치.
- staged 0, runtime/문서 외 변경 0, diff check 통과.
- 과거 CF 본문/포트폴리오 보존, 계약·실패/미검증·직접 DB 권한 미확인·구조 재배치 보류 유지.
- **P2 원격 guard 결함 해소, 잔여 차단 결함 없음. 수정 후 독립 재검토 통과.**

수용 범위는 **ST-001 v1.0 1단계 문서 정리와 사용자 직접 실행 준비**다. 전체 ST-001·기능·
실제 인증/서비스 공개 검증 완료는 아니다. 사용자의 commit/push/Draft PR/병합을 기다리며,
후속 단계는 이 단계 병합 후 최신 develop에서 별도 브랜치로 시작한다. 현재 브랜치·미커밋
변경을 보존한다. 이번 마감은 보고서/PR 초안 문구만 변경했으며 계약·스냅샷·manifest·명령,
실제 git/gh 액션·서비스/DB/Google/AI·비밀 파일은 변경하거나 실행/조회하지 않았다.
