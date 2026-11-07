# ST-001 1단계: 문서 정본과 공유 계약·현재 상태 정리

처음 clone한 사용자가 없는 범용 문서를 따라가거나, 과거 미커밋/미인증 설명을 현재 상태로 읽는 문제를 정리합니다. 실행 코드·DB·권한·환경 동작을 바꾸지 않는 문서 전용 변경입니다.

## 변경

- README에 현재 보호된 Flow 경로·차단된 분석/저장·검증 제한과 문서 진입점을 추가하고 기존 포트폴리오/시연 본문을 이력으로 보존합니다.
- docs/documentation.md에서 도메인별 계약·목표 설계·외부 지시 원본·공유 파생본·실행 이력의 권위와 실제 경로를 구분합니다. 두 coding guide의 존재하지 않는 범용 참조를 실제 Technical/Flow/DB 문서로 고칩니다.
- 외부 CF-001 v1.1/CF-002 v0.6의 기술 계약을 shared-v1 파생본으로 정리하고 source/snapshot SHA-256·절 대응·생략 범위 manifest를 추가합니다. 개인 경로·계정·대화·일회성 자격 사용 승인·원시 실행 영수증은 복사하지 않습니다.
- 과거 CF 보고/PR 초안 상단에 commit 7a5853d/PR #2/merge a5b60f2와 작성 당시 이력의 해석을 명시합니다. News 초안은 CF-002 PR 본문과 구분하며 그 과거 News PR 상태는 미확인으로 남깁니다.
- 현재 책임/DB 지도를 추가합니다. Fundamental이 stock_corp_codes에서 필드 3개를 SELECT하는 호환 경로와 실제 최소 권한 미확인·후속 서비스 인증/API 계약을 구분합니다. 기존 driver/alias/cache/retry/schema/권한은 변경하지 않습니다.

## 기준·검증

- ST-001 v1.0 1단계. source SHA-256 `1b7975913e92ff08065b2094879075fbe796e6e57d6227890b8bc92a772c5010`.
- 선행 CF-002 PR #2 병합 후 develop 전환→fetch→ff-only a5b60f2→docs/document-authority 생성. CF-002 commit 7a5853d가 포함됨과 merge tree 파일 차이 0을 직접 확인했습니다.
- 지정 현재 탐색 링크/anchor·원본과 파생 hash/버전/절 대응·개인/비밀 제외·역사 본문 보존·문서 외/runtime diff 0을 임시 표준 라이브러리 검사기로 확인합니다. 최종 수치/실행 시각은 ST-001-stage-1.md에 기록합니다.
- Flow handoff의 기존 개인 절대 링크 4개는 상대 링크로 정정했습니다. 전체 저장소의 모든 역사 문서나 외부 HTTP 링크를 검사했다고 주장하지 않습니다.
- 문서만 바꾸므로 기능/unit/type/build/DB/Google/AI 검사를 재실행하지 않았습니다. 과거 보고 확인과 이번 직접 검사를 구분합니다. 전체 Frontend lint의 기존 오류 2건·경고 3건과 실제 인증의 남은 미검증을 보존합니다.

## 독립 검토 수정

원격 URL guard의 관측값 불일치 P2 1건을 수정했습니다. 8개 guard 기대값을 실제 fetch/push
URL인 `.git` 포함 주소와 대조하며, 원격 설정이나 실제 stage/commit/push/PR는 변경하지 않습니다.
새 일반 문장만 띄어쓰기를 정리하고 최초 게시 전 파생 hash를 갱신했습니다. 기존 source hash와
계약 내용은 유지합니다. **수정 후 독립 재검토가 통과했고 P2 결함 해소 및 잔여 차단 결함 없음을
확인받았습니다.** 독립 직접 검사는 실제 원격 값과 guard 8개 일치, 링크/anchor 210개 오류 0,
원본/파생/ST hash와 보고 참조 일치, zsh 블록 4개 구문, 허용/실제 변경 경로 23개 일치,
staged 0·runtime/문서 외 변경 0·diff check와 과거 본문 보존을 포함합니다.
초기 자체 검사 206개와 독립 검사 210개는 handoff 링크 4개의 포함 범위 차이입니다.

수용은 ST-001 v1.0 **1단계 문서 정리·사용자 직접 실행 준비**에 한정합니다. 전체 ST-001·기능·
실제 인증/공개 검증 완료를 뜻하지 않습니다. 사용자 commit/push/Draft PR/병합은 아직 실행하지
않았고 후속 단계는 이 단계의 사용자 병합을 기다립니다.

## 범위 밖·후속

root/backend/ai AGENTS·공용 환경 예제·수집 전 안전 검사 입구는 이후 별도 단계입니다. 큰 파일/폴더 재배치 구조는 비교 검토 전 보류합니다. 다음 개발 브랜치는 이 단계의 검토/사용자 병합 뒤 최신 develop에서 만듭니다.

기존 .env/ignored Docker-compose.yml/credentials·포트·서비스·DB/volume는 읽거나 변경하지 않았습니다. 과거 로컬 compose ports-only 변경은 이 PR로 공유되지 않습니다. 실제 인증/AI/전체 서비스 공개 완료를 뜻하지 않습니다. 작성 중 add/commit/push/PR/Ready/merge는 실행하지 않았습니다.
