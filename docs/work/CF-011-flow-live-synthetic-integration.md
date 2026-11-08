# CF-011 · Flow 실제 HTTP와 격리 PG 최소 통합

**실제 Next `/flow/demo` → BFF → FastAPI HTTP listener → 새 자기 PostgreSQL 통합 한 회를 전체 exit0으로 완료했다.** 저장·동일 URL 재조회·동일 POST 재사용, 원 fake engine 총1회, 권한 거절6건을 확인했다. 제품 기능·기존 guard는 변경하지 않았다.

## 최종 source·범위

- CF-011 v1.0으로 읽기 준비 후 최종 v1.1 SHA `5f8085caa776b888a551fd2e62182f4090952964e47ef8a1ea152108ca220b9b`를 적용했다. clean develop·단일 origin/worktree 확인→fetch/ff-only 최신화→전용 branch 순서다. base `a0e220f7e207b56f79ece93e2b9f9473199dae6b`(PR #15), branch `test/flow-live-synthetic-integration`, origin `https://github.com/bellra-jin/verith.git`.
- 정확2개 신규 파일: `backend/scripts/cf011_next_backend_pg_check.py`, 이 기록. 실행 runner SHA `0e4ce8f344bbd537dcc92929c7dedfb1cc7083526a6bed40f0ae8922944cd169`는 이후 변경하지 않았다.
- 독립 검토본79feed…와 실행본의 정확한 차이는 Env 없는 선택 inspect, dependency archive의 O_EXCL/O_NOFOLLOW 생성, image Linux/arm64·Volumes 확인 **3곳**이다. 역치환 SHA가 `79feedc9799e8276f75bce2924c7b31b325439363253eac5470550eafeceea04`로 일치했다. Node lock 전후·고정 오류코드·독립 cleanup budget·PID/nonce/cwd/socket·15초 terminal deadline·container source 전후 검사는 이미 그 검토본에 포함됐다. 최종 source·로그/hash의 독립 읽기 수용과 아래 직접 실행을 구분한다.

## 실제 한 회와 정리 — 2026-11-08 KST

snapshot/checkpoint `/private/tmp/cf011-prepared-scjatlxs`, 실행 manifest SHA `265d0ff7e6eea6b1e964856cdbadbaf9388ee49432340c7fea2893b607326dac`. manifest에 공개 Frontend98·Backend127(검사기 포함), helper/source·lock·image·생성물 전체 SHA가 있다. 공식 Python은 `docker.io/library/python@sha256:df540bfd30bd380e89a349611ce42aa67bcb542d58c047706616eb6ba2f86a1b`(Linux arm64, OCI 표기3.12.16-slim-bookworm), 기존 pinned Node/PG를 사용했다. Node setup은 실제 v24.22.2를 확인했다. 별도 Python/npm version 명령은 반복하지 않았다.

설치용2개와 runtime3개를 분리했다. Node는 Verith lock407개·ignore-scripts·빈 npmrc/새 cache, Python은 backend uv.lock runtime36개·공식 PyPI·exact wheel hash/--no-deps/--only-binary로 설치했으며 source build/추가 도구는 없다. runtime Node owner는 network:none, Python/PG는 그 정확 CID의 namespace만 공유했다. 비root·read-only root·cap-drop/no-new-privileges·자기 tmpfs, host port/mount/socket/internal bridge0과 외부 route0을 유지했다. 실제 주소/MAC·Docker Env·자격은 출력하지 않았다.

새 PG의 직접 생성 CID/name/owner/resource/nonce·시각·고정 image·namespace를 검증하고 새 제한 role의 기존 readonly preflight, 실제 SQLAlchemy 연결 재대조 후 같은 연결 migration을 수행했다. pool 연결도 재대조했다. 기존 issue_session으로 A/B 세션을 commit한 뒤 production authenticate/CSRF/owner를 실제 HTTP로 확인했다. 인증 override·가짜 principal·새 로그인/제품 overlay는 없다. 원 fake engine은 결과/정책을 바꾸지 않는 호출 계수만 관찰했다.

| 단계 | 실제 결과 |
|---|---|
| 설치·build | Node407/Python36 설치 exit0. production build22:25:42.384581→57.108030 exit0, compile/generated types/static11/11/traces 통과 |
| 실제 통합 | 22:25:58.404978→22:26:01.351219 exit0. 성공 artifact의 ID·owner·input/result hash와 실제 PG 행 결합 일치 |
| replay/조회 | 동일 URL SSR·BFF GET·동일 key/body POST가 최초 결과 재사용, 새 envelope ID, 원 engine 총1회·run/input/execution1/1/1·실리포트/보관함0 |
| 거절6 | B 조회404, 무세션 GET/POST401, 누락/불일치 CSRF401, 외부 Origin403. private/no-store·필수 Vary 포함·data 유출/추가 실행/새 행0 |
| 사후·정리 | container source98/127·namespace·host source/artifact hash 통과. installer2개와 peer PG/Python→owner Node 순서로 정확 CID5개 제거·명시적 부재,22:26:02.301176 owner label 잔여0 |

**프로세스 session45475·최종 tool chunk224df2·exit0.** 정확 명령은 clean env(PATH=/usr/bin:/bin, LANG=en_US.UTF-8, TZ=UTC, TMPDIR=/tmp, PYTHONDONTWRITEBYTECODE=1)의 `backend/.venv/bin/python -I -S -B backend/scripts/cf011_next_backend_pg_check.py run --prepared /private/tmp/cf011-prepared-scjatlxs`였다. 이 기록은 재실행 안내가 아니다. runtime 실패/재시도·기존 suite 반복은 없었다.

각 CID·phase 시각·receipt/로그는 checkpoint에 보존했다. events SHA `e2d180c67b180a1298a29d41debcfc6c24016501fad7fe040457d1a2cea65ce6`, live log SHA `5ab6286f0b22073e12484108fe61c9cede35f201884e7da5be3f17585eeba0b2`. 생성 dependency archive2개도 hash/regular/single-link/identity 대조 후 exact unlink했고 disposition을 남겼다. 공개 snapshot·로그/ownership 증거, 공식 image cache와 Docker 앱은 유지했다. 전역 자원0을 주장하지 않으며 다른 프로젝트·기존 DB/volume·사용자 env/cache/profile은 사용/변경하지 않았다.

**실제 Google/provider·운영 DB·React/브라우저 클릭/hydration·Mac harness 자체 수용은 미검증이다.**

## 사용자 직접 Git 인계

현재 exact2의 final-source.json·literal NUL pathspec·PR body를 checkpoint에 준비했다. 상태/bytes가 바뀌면 먼저 재검토한다. 아래 Git publishing은 실행하지 않았다.

```sh
cd /Users/parkjinhee/AI/verith_refactor/verith
cf011_checkpoint=/private/tmp/cf011-prepared-scjatlxs
python3 "$cf011_checkpoint/reviewguard.py"
git diff --no-index /dev/null backend/scripts/cf011_next_backend_pg_check.py
git diff --no-index /dev/null docs/work/CF-011-flow-live-synthetic-integration.md
# 위 신규 파일 diff의 exit1은 차이가 있다는 정상 의미다.
git add --pathspec-from-file="$cf011_checkpoint/stage-pathspec.nul" --pathspec-file-nul
python3 "$cf011_checkpoint/reviewguard.py" --staged
git diff --cached --check
git diff --cached
git commit -m "test(flow): verify live Next Backend and isolated PG integration"
git push -u origin test/flow-live-synthetic-integration
gh pr create --repo bellra-jin/verith --base develop --head test/flow-live-synthetic-integration --draft --title "test(flow): verify live Next Backend and isolated PG integration" --body-file "$cf011_checkpoint/review-pr-body.md"
```

<!-- CF011_PR_BODY_START -->
현재 Flow 합성 데모의 실제 Next SSR/BFF→FastAPI HTTP→새 자기 PG 통합을 고정 검사기/기록2파일로 확인한다. 제품 코드·schema·인증/CSRF/owner·기존 guard는 변경하지 않는다.

전체 프로세스 exit0. 분리된 locked 설치 뒤 network:none 공동 namespace에서 build·성공 저장·동일 URL/POST replay, 원 engine 총1회·행1/1/1·권한 거절6건이 통과했다. 사후 container source/hash·network·host source 확인과 정확 CID5개 제거/부재·label0을 완료했다. 생성 dependency archive2개는 hash 증거를 남기고 제거했으며 공식 image cache는 유지했다.

실제 Google/provider·운영 DB·React/브라우저·Mac harness 수용은 포함하지 않는다. 기존 suite는 반복하지 않았다. 명령/source/로그·정리·한계는 docs/work/CF-011-flow-live-synthetic-integration.md에 기록했다.
<!-- CF011_PR_BODY_END -->
