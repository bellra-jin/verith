# CF-010 · Docker Flow 합성 HTTP 검증

**현재 CF-010 v1.2 회차에서 production build와 실제 Next 합성 HTTP 두 시험은 exit0으로 통과했다. 전체 runner는 출력 형식 불일치로 exit1이며 완료 수용은 보류한다.** Node 기본 요약의 tests2/pass2/fail0을 기존 TAP 전용 parser가 거부했다. network-off와 source 전달 전 hash는 통과했고 자기 CID는 제거·부재/owner label0을 확인했다. HTTP 뒤 container source/hash·network 최종 검사는 이 parser 실패로 미실행이다. 자동 재실행·추가 설치 없이 아래 실제 결과를 보존한다. 이전 namespace 실패는 당시 이력이다.

## 기준·정확한 범위

- 정본 CF-010 v1.0 전체와 SHA `e227d85c5e571e1a2707add20a7783a8a2fd0d210764e8122ff8d2ead091f1ad`를 대조했다. 운영 v1.1/v1.2/v1.2·AGENTS를 적용했다. Next16.2.10 번들 project-structure의 private-folder 규칙을 읽고 파생 readiness 경로를 underscore 없이 고정했다.
- base/HEAD `8d4b2f8f9ce916eeca77de55adbfb68d3006afce`(CF009 PR #13), branch `test/flow-docker-synthetic-http`. clean 상태·전체 origin fetch/push 단일 `https://github.com/bellra-jin/verith.git`·worktree1·동명 branch 없음 확인→fetch→ff-only Already up to date→전용 branch 순서다. reset/clean/stash·publishing 없음.
- 정확6파일: `frontend/scripts/check-docker-synthetic-demo.py`, `frontend/tests/helpers/docker-synthetic-demo-http.mjs`, `frontend/tests/integration/bff/synthetic-demo-http.test.mjs`, `frontend/scripts/cf010-public-source-manifest.json`, `docs/documentation.md`, 이 worklog.
- 원 제품 src/package/lock/Next 설정·Mac controller/guard/safe-http·canonical ports test·Backend/DB·이전 기록은 불변이다. 실제 설정/자격·다른 프로젝트 npmrc/node_modules·사용자 cache/profile·운영 DB·provider는 사용하지 않는다. 공개 문서에 개인 대화나 자격 관련 과거 이력은 옮기지 않는다.

## 고정 입력과 최종 준비 artifact

실행 image ID `sha256:50e2bfc1d63c54b4925099d98a484ac1bcaa54a93e8efce53706f8a92fecf615`, 필수 RepoDigest `node@sha256:01d566e8d94d8c619591d78652babfccd3c6992a3dffa9ed5ab39e11cf6c70e9`, Linux/arm64다. 실행 mode에서 제한 metadata로 ID/digest/platform/Volumes를 다시 확인하며 자동 pull/다른 image는 없다. 과거 Node/npm 버전을 현재 capture로 쓰지 않는다.

- Verith package SHA `5dcc4949fad70a41d4c4fe5639f63931fcaf99accd3019a53052c00a4e697ef5`
- Verith lock SHA `bb3a6a2b6c2e6374a4fa43ab8d3022ea678b0e60a003ff2b2aafb5610a7c7fed`
- 현재 source101: configuration6·product87·asset5·HTTP test2·adapter1. 현재 tracked regular100644/stage0과 exact allowlist의 교집합이며 새 adapter만 명시 예외다.
- derived2: 사본의 `src/app/cf010-ready/route.ts`(URL `/cf010-ready`)와 `.cf010-owner.json`. 원 repo에는 readiness route를 만들지 않았다. 실행 사본의 manifest 자체도 별도 전송하며 자기 hash를 manifest body에 넣지 않는다.

최초 실행의 동결 prepared는 `/private/tmp/cf010-prepared-tkophnj9`였으며 아래 표는 그 당시 source/plan이다. 첫 실패·복구를 보존하는 역사 증거이며 다시 전체 run에 사용하지 않는다. 수정 후 새 대기 snapshot은 아래 재준비 절에 구분한다.

| 준비 source/artifact | SHA-256 |
|---|---|
| host runner | `10a00aeff17279b8504a7220ff30163da78d660ec46d5fb9bea881d48e990ed6` |
| Docker adapter | `ad75b9c6fa3c1521588adb1fc2d663a6ca0b87d6437a4ae4129919fe855360c7` |
| current synthetic HTTP test | `cde9a45de44a04c8a95663f6997e975f245d6826143e698ec2cc3b82728602e6` |
| canonical HTTP test(불변) | `703741869f2082d4040be6ec4e6eaf04a2ba6a8d90f2f782db02614dbf6b3047` |
| repo manifest / prepared manifest.json | `4c29083ca31cf2a67fcb6c98739e44e926dffe91f47c8667f40e7828549604d9` |
| prepared execution-plan.json | `ac5a04f6cf74ea8d7d4d5be8b46dc35140455e04465e3fb0769679d56cfb2908` |

prepared.json에 자기 디렉터리 identity와 정확4 artifact(install-input.tar·source-input.tar·manifest.json·execution-plan.json)의 크기/SHA를 기록했다. prepare는 그 record·현재 runner/입력·manifest·archive의 모든 member·현재 생성한 execution_plan bytes를 다시 대조하고 exit0으로 종료했다. host source는 부모 dirfd와 final FD 모두 no-follow로 열고 regular/single-link·inode/길이/mtime/ctime을 전후 대조한다. 외부 source collector를 import하지 않았다.

## 고정 실행 설계 — 준비 당시 계약

plan은 고정 Docker prefix·create argv·exec prefix·npm/build/HTTP argv와 inline setup/source/network proof를 담는다. 실제 create도 같은 create_args를 사용한다. CLI는 local Unix endpoint와 자기 빈 config/HOME·clean env를 명시하며 사용자 Docker auth/config나 Docker Env를 출력하지 않는다.

1. 자기 container 한 개: pull=never, uid/gid1000, read-only root, cap-drop ALL, no-new-privileges, restart=no, CPU2/memory4GiB/PID256. host mount/socket/공개 port/기존 volume 없음. /work3GiB rw,exec,nosuid,nodev와 /tmp256MiB rw,noexec,nosuid,nodev만 사용하며 두 tmpfs 모두 uid/gid1000·mode0700이다. container 자체1500초 수명, host1500초 deadline 안에서 cleanup 시간을 예약한다.
2. 처음에는 package/lock만 전달한다. 자기 빈 npmrc/home·새 cache와 clean env로 npm ci --ignore-scripts --no-audit --no-fund --registry=https://registry.npmjs.org를360초 한도로 실행한다. package/lock/URL/SRI를 설치 전후 대조한다. dev/platform optional deps를 생략하거나 다른 설치로 대체하지 않는다.
3. 설치 성공 뒤 자기 CID의 bridge를 disconnect한다. Docker network 연결0·host port/mount0과 namespace의 lo만 존재·외부 route 없음 proof를 남긴다. 설치 network가 registry-only firewall이라는 주장은 하지 않는다. build/HTTP 전후 확인하며 재연결 코드가 없다.
4. network-off 뒤 나머지 공개 source·원문 test 두 개·adapter overlay·derived proof를 검증된 relative regular archive/stdin으로 uid1000의 /work에 전달한다. 원 Mac helper는 수정하지 않는다. 사본 manifest SHA를 고정 인자로 확인하고 각 원/파생 입력 hash를 검증한다.
5. fresh .next 없음 확인 뒤 build420초 한 번, 그 build에서 canonical ports와 synthetic-demo 두 test만 serial450초 한 번이다. 마지막 source/manifest와 network-off를 재검증한다. 원 repo/private 환경·추가 suite·브라우저/DB는 실행하지 않는다.
6. adapter는 strict canonical/demo boolean·고정 flag/env, /work/owner/BUILD_ID·실제 child PID/socket inode·nonce/PID/cwd readiness를 확인한다. control probe는 application upstream count와 구분한다. bind/spawn부터 독립 cleanup·case120초·ready60초·TERM3초/KILL2초를 둔다. off를 닫은 뒤 on을 시작한다.
7. host finally는 정확 생성 CID/name/owner/resource/image/Created를 다시 확인한 자기 container만 rm force하고, 명시적 absence와 해당 label0을 별도로 기록한다. 생성 timeout/CID 불명확은 resource_uncertain·exit2로 남기며 label만으로 자원을 채택/정리하거나 자동 재시도하지 않는다. 기타 실패는 고정 phase/CheckFailure 사유만 출력한다. 원문 exception/locals/자격은 출력하지 않는다.

실행 mode에서 단계별 시작/끝·exit·경과/로그 hash·Node/npm·image/network/ownership·TAP·정리 증거를 생성한다. 첫 회차의 image/create·실패/복구 증거만 아래에 기록했다. 설치/build/HTTP 단계는 미실행이므로 결과를 추정하지 않는다.

## source 검토 보완과 현재 증거 수준

- 직접 BFF GET 전후 application 기록이 정확1개 추가되고 method/path/cookie가 맞는지 보완했다. 앞선 SSR 기록이나 fake handler의 동일 view 반환이 잘못된 직접 GET을 가리지 않게 했다.
- artifacts4·plan bytes 고정 비교·동일 create_args·고정 실패 사유/불명확 생성 판정을 반영했다. Python raw string의 namespace proof는 JS newline/공백 escape를 한 겹으로 수정했고 lo 자체도 반드시 하나 존재하도록 했다. 실제 namespace에서 실행한 증거는 아직 아니다.
- off SSR/POST/GET의403·private/no-store/Vary·application upstream0, on 직접 GET·admitted POST202·원문 bytes·중복 Cookie/CSRF/Origin 보존과 위조 헤더 배제·query/path 차단을 test에 넣었다. fake upstream이 malformed bytes를 받은 결과는 BFF 전달 증거이며 실제 Backend가 수용했다는 뜻이 아니다.
- adapter/test와 runner에 대한 중간 독립 source 검토를 받아 위 보완을 반영했다. 최초 frozen source/plan/manifest는 실행 전 독립 대조를 받아 한 회차를 실행했다. 아래 파서 보완도 독립 source 수용을 받았고, 새 prepare의 동결 대조와 실행 인계를 기다린다. 추가 사용자 승인을 요청하는 단계가 아니다.
- Python AST·whitespace와 prepare 자체 검증만 수행했다. 첫 두 준비 시 clean env의 Apple Python temp-directory 경고가 있었고 명시 TMPDIR=/tmp를 둔 최종 prepare는 경고 없이 exit0이었다. 이것은 Docker나 제품 실행 실패가 아니다. 이전 prepared 후보는 사용하지 않는다.

## 두 번째 회차의 실제 사용 명령 — 재실행 지시 아님

repo cwd에서 실행한다. runner는 prepare/run 외 임의 image·command·source root·registry passthrough를 받지 않는다. 아래 명령은 새 동결 대조·인계 후 두 번째 회차에 한 번 실행했다. 같은 snapshot을 자동 재실행하지 않는다.

```sh
/usr/bin/env -i PATH=/usr/bin:/bin LANG=en_US.UTF-8 TZ=UTC TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -I -S -B frontend/scripts/check-docker-synthetic-demo.py run --prepared /private/tmp/cf010-prepared-50pdkpol
```

container 안의 고정 주 workload는 다음과 같다. 실제 exec에는 plan의 clean env와 owner가 앞에 붙는다.

```text
/usr/bin/timeout --signal=TERM --kill-after=5 360 npm ci --ignore-scripts --no-audit --no-fund --registry=https://registry.npmjs.org
/usr/bin/timeout --signal=TERM --kill-after=5 420 npm run build -- --webpack
/usr/bin/timeout --signal=TERM --kill-after=5 450 node --test --test-concurrency=1 docker-tests/integration/bff/ports-http.test.mjs docker-tests/integration/bff/synthetic-demo-http.test.mjs
```

실행 완료/중단 후 이 절 뒤에 실제 결과·한계·source hash·exact6 manifest/NUL pathspec/사용자 commit·Draft PR 초안을 남긴다. 실제 add/commit/push/PR/Ready/merge는 사용자가 직접 한다. 현재 구현·source 준비를 HTTP/웹 통합 완료로 보고하지 않는다.


## 첫 실행·실패 원인·정확 자원 복구 (2026-11-08 KST)

첫 실제 명령은 위 고정 clean launcher와 최초 `--prepared /private/tmp/cf010-prepared-tkophnj9`였다. tool session19507의 최종 chunk f004ff는 **exit2**다. 20:48:35.013990에 image 확인을 시작했고 20:48:35.091853에 create를 요청했다. 정확 CID `0d2f927ca2a02ef2d3ce693960cdfce65b77cfc2dd66ed2171417b3f259d94ec`, owner `cf010-c3680d76818a449d4e6c8b7a`, resource는 최초 manifest SHA `4c29083ca31cf2a67fcb6c98739e44e926dffe91f47c8667f40e7828549604d9`다. Docker Created 원문 `2026-11-08T11:48:36.875074833Z`는 20:48:36.875074833 KST이며 명령 시작/끝과 다르다.

20:48:36.960925의 failed와20:48:36.985567의 cleanup_failed가 남았다. Apple Python3.9.6이 identity의 datetime.fromisoformat에서9자리 fractional초를 파싱하지 못해 ValueError를 발생시켰다. 고정 비민감 진단은 other였으며, 원문 exception/Env를 출력하지 않고 exact CID metadata와 같은 동결 identity 함수에 대한 읽기 전용 대조로 위치를 확인했다. container는 created/running=false, uid1000, read-only root, mounts0·host ports0였다. start·exec·npm·build·HTTP는 미실행이며 TAP/설치 개수/Node/npm capture는 없다.

runner의 최소 보완은 엄격한 Docker UTC timestamp 파서와 UTC datetime→정수 ns 변환 helper 두 개, 기존 생성창 비교 두 줄뿐이다. 두 helper/비교 변경을 역제거하면 최초 runner `10a00ae...` bytes가 정확히 복원된다. ±2초 창은 그대로이고1ns 단위로 비교하며 원문 Created 문자열·CID/name/owner/resource/image 일치는 보존한다. 합성 순수 회귀에서 유효7/잘못된값16, 생성창 양끝2·창 밖1ns2거부, 같은시각의 raw Created 표기 변경 거부, 소유조건 변형5거부를 확인했다. 이 회귀는 Docker 호출0이며 설치/웹 시험이 아니다. 수정 runner SHA는 `1e0863004f4e44457e3d21d4598088c5d5ae288e5f25703bcca91d25ef89be2d`로 독립 source 수용됐다.

기존 creation.json의 CID/owner/resource/requested/returned와 원문 Created를 복원하고, 수정된 동일 identity·cleanup만 호출하는 별도 exact 복구를 수행했다. 새 create/start/install/build는 없다. cleanup session63805 최종 chunk4223ec **exit0**, 20:55:21.869994 시작→20:55:23.368942 rm_exit0·명시적 absence=true·owner label_remaining0을 확인했다. 최초 runner finally의 cleanup 성공으로 소급 기록하지 않는다. 다른 자원/volume/image/prune·Docker 종료는 없었다.

최초 prepared에 `first-execution-events.json`(SHA `7b705728fcd4235330d1ff9c6757e357f32b7b0d13db18984e24ce0cead2f93b`), failure-readonly.json, creation.json, timestamp-parser-source-check.json, timestamp-exact-delta.json, cleanup-first-created-resource.py와 exact-recovery-cleanup.log를 보존한다. 복구 log SHA는 `b77159d9a2ea5d29c65f6f66ffe511039c8606a8174e060ac98fe7d2ae5a55b9`이며 recovery-summary.json에 별도 결과를 담았다. events의 최초 실패 prefix가 그대로임을 대조했다. 전역 container0이라고 확대하지 않는다.

## 복구 후 새 prepare — 전체 재실행 인계 대기

기존 CID 부재 확인 후에만 prepare를 수행했다. 새 `/private/tmp/cf010-prepared-50pdkpol`은 source101/derived2/artifacts4의 자체 source/archive/plan 검증을 exit0으로 완료했다. **새 Docker create·설치·build·HTTP는 아직 실행하지 않았다.** source 변경/추가 prepare 없이 이 bytes를 대조한다.

| 고정 대상 | SHA-256 |
|---|---|
| 수정 runner | `1e0863004f4e44457e3d21d4598088c5d5ae288e5f25703bcca91d25ef89be2d` |
| 새 repo/prepared manifest | `ba45e153b8b092475788603ebb3e86cd967ac6c5a63d028a31ab125b5044af42` |
| 새 execution-plan.json | `fc47d3ab1293168291afd20bcb8c8d88d5e5ec4410deca56acdc6a5aa3ebbf98` |

adapter/두 HTTP source·package/lock/제품 source와 나머지 보호는 최초 실행 전과 같다. 새 manifest는 수정 runner hash와 새 자기 ownership marker/plan을 반영한 별도 준비 증거이며 첫 실패 증거를 대체하지 않는다. source·plan의 읽기 대조 후 별도 실행 인계를 받아야 한다. 실제 Backend/DB·Google/provider·React/browser는 계속 범위 밖이다. 최종 Git/PR 인계는 실제 후속 결과와 한계를 기록한 뒤 준비하며 publishing은 사용자만 한다.


## 두 번째 실제 회차 — lock 설치 통과·namespace gate 실패

같은 고정 clean launcher와 `--prepared /private/tmp/cf010-prepared-50pdkpol`을 사용했다. session21427 최종 chunk d8c88e **exit1**이다. source/code/manifest/plan은 읽기 수용값 그대로다. 아래 시각은2026-11-08 KST이며 source의 UTC event를+09:00 변환했다.

| phase | 시각·실제 결과 |
|---|---|
| image/create | 20:59:06.022066 시작, 검토 image/digest/platform·Volumes없음 일치. CID `40591ea666be741595c61ff706a00eade7710a892020d8a56bef16099309dacb`, owner `cf010-acdf0db2d618f9889dcefb43`, Docker Created 원문 `2026-11-08T11:59:06.124935423Z` |
| identity | 20:59:06.542601 exit0. Node v24.22.2, uid/gid1000·cwd/work, 두 tmpfs 소유/권한 확인. read-only/mount0/host port0·limits 검증 |
| package/lock | install-input 전송과 설치 전 검증 exit0. package/lock SHA·공식 registry/SRI484 일치. source 나머지는 전송하지 않음 |
| npm/version·install | npm11.19.1. 20:59:06.811131→20:59:13.951059,7.139초·exit0·407packages. 고정 ignore-scripts/no-audit/no-fund 사용, npm update 안내는 출력뿐이며 업데이트 실행 없음 |
| 설치 후 lock | 20:59:14.031521 exit0. package/lock과 빈 user/global npmrc 불변 |
| Docker network-off | 20:59:14.127473 exact CID의 connected networks=[],ports={},mount0·소유/보호 확인. 이는 namespace interface/route 조건 통과 증거와 별도 |
| namespace proof | 20:59:14.128115→20:59:14.205410, exit1·CF010 external interface. devices.length===1 및 devices[0]==='lo' 조건에서 실패. route 읽기/판정까지 도달하지 않음 |
| finally cleanup | 20:59:14.206124→20:59:14.370578, rm_exit0·명시적 absence=true·owner label_remaining0. 최초 실패 CID와 다른 자기 자원이며 전역 자원0을 뜻하지 않음 |

설치 전후 package/lock SHA가 같고 실행 후 host public source101·prepared artifacts4·runner/manifest/plan 모두 불변임을 읽기 대조했다. 전체 source는 network gate 뒤 전송하도록 설계했으므로 이번 container에는 package/lock만 전달됐으며 **container source101 전후 검증·build·HTTP·TAP는 미실행**이다. 설치 script는 고정 ignore-scripts로 금지했고 이번 검사가 native 전체 syscall/lifecycle tracing이라는 뜻은 아니다. 사용자 설정/기존 dependency/cache·DB/provider는 사용하지 않았고 container와 자기 tmpfs/cache는 함께 제거됐다. Docker 앱과 기존 image는 남겼다.

새 prepared의 events.json SHA `f67b60210b004dd809c506b8d95b79745812cf7b9d20b2bda85ac6de097ef190`, install.log `d14788d087be38b942ef1d8118c4b5bb58db7588fd79387c5a775f4e9265d689`, network_off.log `6d65a8b9ce98e828379fbe1c61ce72b2947815087ab6aa949446db475ce9bc76`다. post-failure-summary.json에 code/plan/argv·source 불변과 실제 종료/정리 범위를 보존했다.

### 원인 구분과 최소 다음 판단

실제 실행 argv·동결 plan·현재 NETWORK_PROOF는 bytes 동일(SHA `ff6674b1e83efc1b5d6bacf3be7325e7fb1134d3d0015937cb02b6089b4db672`)이며 newline/공백 escape는 한 겹이다. 이전의 이중 escape는 재발하지 않았고 Node도 syntax 오류가 아닌 첫 interface 조건에서 중단했다. 그러나 실패 전에 실제 interface명/개수·route값을 출력하지 않아 disconnect 반영 지연·다른 interface·가상 파일의 예상 밖 형식 중 무엇인지는 증명할 수 없다. Docker Networks={}를 namespace egress 부재로 대체하거나 추정하여 조건을 완화하지 않는다.

source 변경 없이 가장 작은 검토 제안만 남긴다. 기존 namespace proof에서 이름/IP/MAC/gateway/raw proc 내용을 출력하지 않고 interface/route 개수·non-loopback 개수·loopback 판정·parse_ok만 고정 필드로 먼저 기록하는 방안이다. bounded read-only settle을 허용한다면 같은 이미 생성된 CID에서 짧은 유한 deadline/간격으로 동일 세 proc 파일만 다시 읽고, 기존 lo-only·external-interface/route0·source전송 전 gate를 그대로 만족해야 한다. timeout/parse 실패는 즉시 고정 실패이며 재연결/route·interface 조작·새 허용 목록/보안 완화는 없다. **이 제안은 아직 구현하거나 실행하지 않았다.**

기존 자원은 이미 제거돼 추가 namespace 관측은 불가능하다. 현재 고정 pipeline으로 새 관측을 실행하려면 새 자기 container와 동일 lock 설치도 다시 필요하므로 자동 반복하지 않는다. 조율된 최소 source/검증 범위와 새 동결 대조·인계를 받기 전에는 새 prepare/run·설치·추가 suite 없이 중단한다. 현재 CF010 build/HTTP 완료 기준은 미충족이며 최종 Git/PR 인계를 완료 성공처럼 표시하지 않는다.


## 필요한 관측 보완 동결 — 실행 전 이력

NETWORK_PROOF 블록만 변경했다. 이미 읽는 dev 결과를 한 번 담아 line/dataRow/colonMissingRow/interface 개수와 제한된 이름을 throw 전에 출력하고, 기존 route 읽기 결과의 IPv4/6 행수·파싱된 interface 집합도 출력한다. 이름은 최대16개·ASCII 허용 패턴1~32자 또는 고정 invalid이며 주소/카운터/원문은 출력하지 않는다. exact lo-only·외부 route 금지·source 전송 전 gate와 cleanup은 그대로다. 앞서 제안했던 settle/sleep/retry는 추가하지 않았다. 블록만 역치환하면 직전 runner1e086300… bytes가 정확히 복원된다.

새 준비는 `/private/tmp/cf010-prepared-2cdr3z8p`, source101/derived2/artifacts4 자체 검증 exit0이다. runner `688dcd1ab16dea83f5c85a8c236e7b0ff191111c8fd2f4b383db9232234ea603`, manifest `bf4fe0e2e740f8add6b4d08708ad0b282329579a1f06004f57f5373235fec389`, plan `fe5e813808c24322274dd494ef3241c180169584d6135a57d186e4839462bdf8`를 고정했다. 아래 명령은 당시 읽기 검토·실행 인계 전의 준비 기록이며, 이후 아래 마지막 관측 회차에 한 번 사용했다. 재실행 지시가 아니다.

```sh
/usr/bin/env -i PATH=/usr/bin:/bin LANG=en_US.UTF-8 TZ=UTC TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -I -S -B frontend/scripts/check-docker-synthetic-demo.py run --prepared /private/tmp/cf010-prepared-2cdr3z8p
```


## 마지막 한정 관측·중단 (2026-11-08 KST)

`cf010-prepared-2cdr3z8p`를 검토된 명령으로 한 번 실행했다. session53473 최종 chunk79c858은 exit1이다. image/소유/보호·Node24.22.2/npm11.19.1 확인, lock407개 설치7.253초·exit0·설치 전후 hash 일치까지 통과했다. Docker connected networks=[],host port0/mount0 확인 뒤21:09:01.212384~21:09:01.286676에 namespace proof가 exit1로 중단됐다.

고정 관측: lineCount12/dataRowCount10/colonMissing0/interfaceCount10, 이름은 `lo,tunl0,gre0,gretap0,erspan0,ip_vti0,ip6_vti0,sit0,ip6tnl0,ip6gre0`이다. IPv4 route0, IPv6 route3개/파싱된 interface집합 lo만 확인됐다. 즉 파싱/escape 오류가 아니라 관측된 비lo9개로 exact lo-only 조건이 실패했다. interface의 실제 up/down·주소 유무·연결 가능성은 관측하지 않아 외부 연결이 있었다거나 template들이 안전하다고 단정하지 않는다.

정확 CID `44ecebfcbfd83e09e87025c2e5858d7c3f5303cd90696ce08ef56ed72f3b6aaa`, Docker Created `2026-11-08T12:08:53.094118208Z`, owner `cf010-bcbf7011836c0f8612f8f60f`. finally21:09:01.427398에 rm_exit0·명시적 absence=true·owner label_remaining0을 확인했다. source 전달/build/HTTP/TAP는 전혀 시작하지 않았다. 실패/정리는 마지막 prepared의 events.json·network_off.log에 있고 첫 두 회차 기록도 보존한다.

추가 runtime·재설치·검사는 중지했다. network-none 실행공간을 별도로 만들더라도 같은 커널 template interface가 있을 수 있어 해결을 보장하지 않는다. 최소 정책 후보는 Docker network0·외부 route0과 비lo down/unconfigured를 조합한 연결성 판정이지만, 마지막 조건은 미관측이고 현 정본의 exact lo-only와 다르다. 상위 판단 전에는 이를 적용/재실행하지 않는다. 현재 결과를 build/HTTP 완료나 전체 웹 통합 성공으로 인계하지 않는다.


## 후속 읽기 전용 연결성 기준 준비 — 수정 정본·실행 인계 대기

namespace proof만 보완했다. Docker connected networks0과 기존 외부route 금지는 유지한다. 이름 검증·고정9종 집합 확인 뒤 자기 namespace의 sysfs flags와 node:os.networkInterfaces 결과만 읽어, lo의 UP/loopback flag·loopback주소와 비lo의 DOWN/주소 개수0을 동시에 요구한다. unknown/UP/주소/읽기불가/모순은 실패한다. 실제 주소/MAC/flags 원문은 출력하지 않고 이름·개수·boolean만 기록한다. 설정 변경·interface 조작·재연결·sleep/retry·추가 package는 없다. 이전 실패/정리·당시 exact lo-only 판정은 그대로 보존한다.

준비는 한 번 생성했다. `/private/tmp/cf010-prepared-nuse5p2e`의 source101/derived2/artifacts4 검증 exit0, runner `5f5d57845b1bf46524d2624af787df31ef62163eb806bf14fecd42bd1a9b86ff`, manifest `ada7b68ff41960987c02b4b58b57e2de86ad0dd9ce6c9f4673ef28d8a7aef729`, plan `4cd18bbf648d8f0f5e77e7dd3fdbd9e56f754c4cde1a11141fc8e591da8c39ba`다. namespace block만 역제거하면 직전688dcd… runner가 정확히 복원된다. 실제 이 준비본 run은 아직 실행하지 않았으며 수정 정본 확인·읽기 대조/실행 인계를 기다린다.


## v1.1 실행 전 정합성 보완 동결

NETWORK_PROOF만 변경해 실제 network 증거의 동적 이름/상태 배열 출력을 없애고 boolean/count 집계만 기록한다. IPv4는 정확11열·고정 header/hex/decimal 형식, IPv6는 정확10열·고정 hex/prefix/interface 형식을 확인한 뒤 기존 외부 route 거부를 적용한다. malformed는 고정 실패다. flags의 DOWN·lo UP/loopback·보고 주소 조건과 source 전송 전 gate는 유지했다.

node:os.networkInterfaces는 비활성 interface를 생략할 수 있다. 따라서 직접 증거는 **API가 보고한 사용 가능한 비lo 주소0 + flags DOWN + Docker network0 + 외부 route0**이며, 설정된 주소가 절대 없다는 보장은 아니다. 기존 비root/cap-drop/no-new-privileges로 interface 활성화 권한을 주지 않는 경계는 그대로다.

한 번의 새 prepare `/private/tmp/cf010-prepared-n_192hli`를 exit0으로 완료했다. runner `4f3a421ccfe54a4120902df2f02fdfa57bd8af5e1f81bd9407b446a31e7c8db2`, manifest `eadf7f8d40166572c4afb4dc7c8716f08795f61e3574812d66c9bdee0d48a0a8`, plan `a3a01b61fef4ab376a29685bf413835132d7ac1b29533f27151a39328d1379f3`로 동결한다. 실제 이 준비본 run은 아직0이며 수정 정본과 최종 읽기 대조·실행 인계 전이다. 새 도구/설치/긴 진단·추가 suite는 없다.


## v1.2 실제 회차 — build·HTTP 통과, 출력 형식 검사 실패

정본 v1.2 SHA `99a6d7caa009b92bdad29cb4aa5139e7455c10a3bad9f3dacadc7c681e7a22c1`과 독립 읽기 대조를 완료한 `/private/tmp/cf010-prepared-n_192hli`를 한 번 실행했다. runner `4f3a421ccfe54a4120902df2f02fdfa57bd8af5e1f81bd9407b446a31e7c8db2`, manifest `eadf7f8d40166572c4afb4dc7c8716f08795f61e3574812d66c9bdee0d48a0a8`, plan `a3a01b61fef4ab376a29685bf413835132d7ac1b29533f27151a39328d1379f3`는 실행 중 변경하지 않았다. 실제 launcher는 다음과 같으며 재실행 지시가 아니다.

```sh
/usr/bin/env -i PATH=/usr/bin:/bin LANG=en_US.UTF-8 TZ=UTC TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -I -S -B frontend/scripts/check-docker-synthetic-demo.py run --prepared /private/tmp/cf010-prepared-n_192hli
```

session26746 최종 chunk f6d8e8 **전체 exit1**. 아래 시각은 2026-11-08 KST다.

| 단계 | 실제 결과 |
|---|---|
| 생성·소유 | 21:23:56.451165 생성 시작. CID `bfe6f7e952db15d863d6d153237f5266ba1daf56f58dd1d82ccca821827d1ca3`, owner `cf010-7763cbb3561b0f4d141bb70a`, 원문 Created `2026-11-08T12:23:58.066455Z`. 고정 image/digest·uid/gid1000·read-only·cap/limits·host mount/port0 확인 |
| 설치 | Node24.22.2/npm11.19.1. 21:23:58.797256→21:24:06.012588, 7.214초·exit0·407packages. Verith package/lock만 먼저 전송, ignore-scripts 유지·설치 전후 hash 일치. npm update 안내는 실행하지 않음 |
| network-off | Docker 연결0 확인 후 21:24:06.256483 namespace proof exit0. interface10/허용 template9·unknown0, lo UP/loopback-only·API IPv4/IPv6 각각1, template UP0/API가 보고한 사용 가능한 IPv4/IPv6 주소0, 외부 IPv4/IPv6 route0. HTTP 전 같은 proof도 exit0. 실제 주소/MAC 출력 없음 |
| source 전달 | network-off 뒤 source101+derived2 전달, 21:24:06.376622 container source hash 전부 일치. fresh .next 부재 확인 |
| build | 21:24:06.437337→21:24:21.492929, 15.055초·exit0. Next16.2.10 compile·generated types 포함 TypeScript·static11/11·build traces 통과 |
| HTTP | 21:24:21.586563→21:24:22.873369, 1.286초·exit0. canonical3200→8200 callback/Host/Origin 및 demo off/on SSR/BFF raw bytes·no-store·URL 두 시험 통과. 기본 Node 요약은 tests2/pass2/fail0/cancelled0/skipped0/todo0 |
| runner 실패 | 21:24:22.874824 `HTTP exact test count`. 고정 HTTP argv에 `--test-reporter=tap`이 없고 실제 출력은 `ℹ tests 2` 등 기본 요약인데 parser는 `# tests 2` 형식만 요구한다. 제품/시험 실패와 구분한다. 실제 TAP 산출로 기록하지 않음 |
| finally | 21:24:22.875834→21:24:23.077302. 정확 자기 CID rm_exit0·명시적 absence=true·owner label_remaining0. 다른 자원/volume/image/Docker 앱은 변경하지 않음 |

전체 성공으로 소급하지 않는다. parser 직후의 container source-after와 network-after 검사는 미실행이며 이미 제거된 자원에서 추가 관측할 수 없다. 종료 후 읽기 전용 대조에서 host 공개 source101·runner·prepared artifacts4가 동결 hash와 일치했다. API가 DOWN interface를 생략할 수 있으므로 주소 증거는 보고된 사용 가능한 주소0으로 한정한다. 설치 network와 이후 network-off를 구분하며 외부 연결 probe/재연결은 없었다.

보존 증거는 같은 prepared의 events.json·build.log·http.log·network_off.log·source_before.log·post-run-summary.json이다. build log SHA `941845811d1bb3e26045cedc75fc2c738cfd98672c72bcd2b5a6562590e921bf`, HTTP log SHA `2b3a6a798a512cc3e4ae68cde8960c66b5db8083405033b6a2a85a9428eeb499`, namespace log SHA `79bcbae6ec3c7bbf6569e1c33f8088640a4e0cd0f91b7710dfca2b912ca6f387`다.

이 회차 이후 재prepare·재설치·runtime 재실행은 하지 않았다. 후속 최소 수정으로 다음 실행용 HTTP 고정 argv에 `--test-reporter=tap` 한 항목만 추가했다. 기존 엄격한 TAP 개수/실패/skip 검사는 그대로이며, 이 수정의 실제 실행은 미검증이다. 후속 여부는 이 실제 결과를 기준으로 결정한다. 이번 결과는 실제 Backend/session/owner/DB·Google/KIS/OpenAI·React 클릭/hydration/브라우저·Mac harness 수용이 아니다. 사용자 Git publishing은 실행하지 않았다.


## 최종 인계 — 출력 형식 최소 수정과 실행 증거 분리

최종 runner SHA `fd52002f2777fe05f3096a56b76e777527b826a54891924aa76290ef0e10fade`는 실제 실행한 `4f3a421c…`에서 HTTP argv의 `--test-reporter=tap` 추가 하나뿐이다. 역치환 bytes 일치와 Python AST 문법만 대조했고 설치/build/HTTP를 다시 실행하지 않았다. 실행 source 원형은 마지막 prepared의 executed-runner.py로 보존했다. 기존 http.log SHA `2b3a6a798a512cc3e4ae68cde8960c66b5db8083405033b6a2a85a9428eeb499`와 events.json SHA `96282296f861e1fc127259208d948d4c7ee04ac9001a38395b7b97a8e17f15af`의 실제 성공/전체 실패/정리 이력은 변경하지 않았다.

repo의 public-source-manifest와 마지막 prepared의 manifest/plan은 **실제 실행 snapshot 증거**로 보존한다. 이 manifest의 runner hash는 실행본4f3a…이며 최종 다음 실행용 runner fd520…와 의도적으로 다르다. 이를 최종 runner까지 실행한 증거로 사용하지 않는다. 향후 실행하려면 새 prepare·해당 source/plan 검토가 필요하지만 이번 인계에서 수행하지 않았다. host 공개 source101은 기존 동결 hash와 일치하며 최종 runner는 위 단일 flag delta로 별도 추적한다.

현재 handoff checkpoint는 `/var/folders/d7/v1s6ddq12y9fftsqrvrgcz140000gn/T/cf010-baseline-vp4fawzo`다. final-source.json은 정확6파일의 **현재** bytes와 실행 snapshot/최종 runner 구분을 기록하고, stage-pathspec.nul은 literal NUL pathspec, review-pr-body.md는 아래 단일 marker 사이 본문이다. 기존 CF009의 read-only reviewguard를 이 exact6/base/branch에 한정해 재사용했다. 추가 Docker/시험 기능은 없다. 상태/bytes가 달라지면 그대로 stage하지 말고 변경을 검토한다.

아래는 사용자 직접 실행용이며 개발 담당은 실행하지 않았다. 검토 후 stage diff에 기밀·무관 변경이 없는지 확인하며, stage 이후 reviewguard가 실패하면 commit/push하지 않는다.

```sh
cd /Users/parkjinhee/AI/verith_refactor/verith
python3 /var/folders/d7/v1s6ddq12y9fftsqrvrgcz140000gn/T/cf010-baseline-vp4fawzo/reviewguard.py
git diff --stat
git diff -- frontend/tests/integration/bff/synthetic-demo-http.test.mjs docs/documentation.md
# 신규 파일은 final-source.json의 정확6개 목록과 함께 직접 검토한다.
git add --pathspec-from-file=/var/folders/d7/v1s6ddq12y9fftsqrvrgcz140000gn/T/cf010-baseline-vp4fawzo/stage-pathspec.nul --pathspec-file-nul
python3 /var/folders/d7/v1s6ddq12y9fftsqrvrgcz140000gn/T/cf010-baseline-vp4fawzo/reviewguard.py --staged
git diff --cached --stat
git diff --cached --check
git diff --cached
git commit -m "test(flow): verify synthetic demo HTTP in isolated Docker"
git push -u origin test/flow-docker-synthetic-http
gh pr create --repo bellra-jin/verith --base develop --head test/flow-docker-synthetic-http --draft --title "test(flow): verify synthetic demo HTTP in isolated Docker" --body-file /var/folders/d7/v1s6ddq12y9fftsqrvrgcz140000gn/T/cf010-baseline-vp4fawzo/review-pr-body.md
```

<!-- CF010_PR_BODY_START -->
현재 Flow 합성 데모의 실제 Next SSR/BFF 요청·조회와 canonical callback 경계를 비밀 없는 Docker 사본에서 검증한다. 고정 공식 Node 이미지와 Verith lock만 사용하며 ignore-scripts 설치 뒤 외부 network-off를 확인한다. 원 제품 source·package/lock·Mac guard·Backend/DB는 변경하지 않는다.

- 실제 실행: Node24.22.2/npm11.19.1, 고정 lock407개 설치 exit0. network-off 후 Next16.2.10 production build(compile/generated types/static11/11/traces) exit0, 실제 Next+fake HTTP 두 시험 tests2/pass2/나머지0·subprocess exit0.
- 전체 runner는 Node 기본 요약과 TAP parser 형식 불일치로 exit1. HTTP 뒤 container source-after/network-after는 미실행이다. 정확 CID 제거·부재/owner label0과 host source101 불변은 확인했다. 앞선 timestamp/namespace 실패·별도 복구 이력도 보존한다.
- 후속 source 수정은 고정 HTTP argv에 --test-reporter=tap 추가 하나이며 실제 재실행하지 않았다. 실행 snapshot과 최종 다음 실행용 runner를 구분한다. 전체 완료 수용으로 소급하지 않는다.
- 실제 Backend/session/owner/DB·Google/KIS/OpenAI·React 이벤트/hydration/브라우저와 Mac harness 자체 수용은 범위 밖이다. 다른 프로젝트 npm·개인 설정·기존 DB는 사용하지 않았다.

정확6파일·source/hash·명령·각 phase/cleanup 및 미검증 범위는 docs/work/CF-010-docker-synthetic-demo.md에 기록했다.
<!-- CF010_PR_BODY_END -->
