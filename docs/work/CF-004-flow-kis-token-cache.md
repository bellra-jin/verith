# CF-004 · Flow KIS 캐시 격리·strict 검증·안전 저장

## 현재 상태

**무키 캐시 보완 완료.** CF-004 v1.0 전체와 source SHA-256
`5b6b2524e1f3d264faa3fd6d6796a5068a769c71a766e82b422d7c8d118dfda4`를 대조했다.
최종 보호 self16/16·고정14파일 unit568/568이 exit0·guard0으로 통과했고 각 자기 root 제거를 확인했다.
최종 독립 source-only 검토에서 필수 수정 없음으로 수용됐다는 전달을 받았다. 독립 runtime 재실행은 아니다.
실제 외부 KIS/AI 호출·사용자 자격·기존 캐시 사용은 수행하지 않았다.

## 기준·변경 보존

- 기준/현재 HEAD `38c0b34a5741198484278767a7ada1c925f71301`, branch `fix/flow-kis-token-cache`, base develop.
- PR #7 병합 및 현재 원격 develop을 확인했다. clean develop/staged0/worktree1·단일 origin의 전체 fetch/push URL `https://github.com/bellra-jin/verith.git`·동명 local/remote branch 부재를 대조했다.
- fetch→ff-only 최신 확인→위 새 branch 순서로 준비했다. reset/clean/stash/rebase·Git 게시 작업은 없다.
- 공개 시작 bytes/hash 사본은 `/tmp/cf004-baseline-q52jews7/baseline.json`에 보존했다. 실제 private 설정·캐시는 복사하지 않았다.
- 운영 v1.1/v1.2/v1.2, root/AI/Backend 안내와 문서 권위를 읽었다. 관련 .agents/skills는 없었다. 공유 snapshot/manifest·CF-003 API/DB/검사·기존 migration·payload v1·Frontend는 변경하지 않았다.

## 구현과 영향

[캐시 계약](../../ai/docs/contracts/flow/kis-token-cache.md)의 stdlib 제품 모듈로 캐시 책임만 분리했다.
서버의 trailing slash만 제거하고 정확한 app key/secret을 버전 표식과 경계 있는 JSON으로 SHA-256 결합한다.
같은 문맥만 재사용하고 key/secret/server 변경은 별도 파일이다. 원문 자격을 파일명/record/오류에 넣지 않으며 암호화라고 주장하지 않는다.

schema_version은 JSON 정수2만, token은 공백·제어문자 없는 ASCII만 허용한다. cache record는 정확4필드·문맥 일치·유한 expires_at을 요구한다.
중복 key·잘못된 JSON/UTF-8·추가/누락 필드·bool/문자열/NaN/Infinity/overflow 시간·64KiB 초과는 유효 캐시로 사용하지 않는다.
now도 유한 숫자만 받고 `now < expires_at - 60`일 때 hit이다. raw 발급 JSON의 token과 존재하는 숫자 TTL>60을 검증하며 임의86400 보충을 제거했다.
hit issuer0/miss 최대1이며 실패 뒤 반복 발급하지 않는다.

caller 경로의 component를 metadata로 확인하고 symlink를 거부한 뒤 명시 부모만 no-follow directory FD로 연다.
새 부모0700·기존 부모 소유/비쓰기 경계, 파일 regular/uid/single-link/0600을 검사한다. FIFO는 열기 전에 거부하고 파일 open도 no-follow/nonblocking이다.
배타 생성 temp의 mode0600 확인·fchmod를 첫 token byte 전에 수행한다. write/flush/fsync·부모/entry/temp identity 재대조 뒤 같은 dirfd의 replace로 교체한다.
교체 전 실패는 원본 bytes/inode를 보존하고 자기 temp만 제거한다. 교체 후 실패는 committed=True 고정 오류로 구분한다. unsupported 보호 조건을 우회하지 않는다.

KIS 연결부는 pure validator와 cache-first 흐름에 위임하며 두 소비자가 이미 읽은 같은 base_url을 명시 전달한다.
`_load_credentials`의 AI root .env/override=False·process env 우선·호출 시점은 유지했다. 캐시 외 함수의 AST는 기존과 같고 두 소비자의 base_url 인자만 추가됐다.
실제 KIS 모듈은 import하지 않았으며 이 연결은 source wiring 검토다. GET 유량 제어·수치/정렬·20행/20일·signals/config·render·payload는 바꾸지 않았다.

기존 무결합 `kis_token.json`은 읽기/채택/이전/삭제하지 않는다. **추후 실제 실행의 첫 요청은 새 문맥 cache가 없어 새 토큰 발급이 필요할 수 있다.** 이번에는 실제 발급하지 않았다.
실제 KIS 응답이 strict TTL 계약에 맞는지, 기존 실캐시 전환 및 토큰 실사용은 미검증이다.

## 보호 입력과 source-only 검토

새 source import closure는 hashlib/json/math/os/pathlib/secrets/stat/contextlib의 stdlib뿐이다. env/home/HTTPX/pandas/graph/config import나 import 시 제품 I/O·시각 호출은 없다.
기존 FLOW_INPUTS의 models/payload2 hash는 보존하고 CF004_INPUTS의 token_cache1 hash를 별도로 pin했다. 원본 source identity/hash와 사본 copy 경계를 유지한다.
고정 unit1만 추가해14파일이며 namespace 기존4+infrastructure1, origin 기존2+token_cache1만 확인한다. 수집·종료 검사와 OS/FS/network/private/timeout/정리는 유지했다.
모듈 전체 sys.modules가 깨끗하다는 주장 대신 해당 source의 AST와 실제 exact origin을 검사했다.

기존 AI 캐시 pytest의 다섯 의도(roundtrip/만료·margin/손상·누락/hit issuer0/miss 발급·갱신)를 pure API·합성 fixture로 옮겼다.
**AI pytest는 실행하지 않았다.** 새 Backend unit은 실제 제품 모듈을 실행하며 KIS adapter는 AST로만 검사한다.

## 직접 실행과 정리

2026-11-08 KST, repo root에서 다음 명령을 각각 실행도구 `sandbox_permissions=require_escalated`로 직렬 실행했다.
기존 Python3.12.13의 절대 경로와 env-i/-I/-S를 사용했다. 명령별 정확 시작/종료 시각은 별도 수집하지 않았다.

```sh
/usr/bin/env -i LANG=en_US.UTF-8 TZ=UTC /Users/parkjinhee/AI/verith_refactor/verith/backend/.venv/bin/python -I -S backend/scripts/check_safe.py self-test
/usr/bin/env -i LANG=en_US.UTF-8 TZ=UTC /Users/parkjinhee/AI/verith_refactor/verith/backend/.venv/bin/python -I -S backend/scripts/check_safe.py unit
```

| source 시점 | 실제 결과·증거 |
|---|---|
| 최초 구현·비노출 검사 | self16/16 exit0(chunk837674). unit14파일 수집568/pass568/fail0/skip0·guard0·exit0(session96916/chunk1daa46). 각각 owned root 제거 |
| 비노출 assertion 보완 후 최종 | self16/16 exit0(chunkaa038e). unit14파일 수집568/pass568/fail0/skip0·guard0·exit0(session89762/chunk220256). 각각 owned root 제거 |

두 회차 사이 제품 소스/보호 pin은 같고 unit의 비노출 검사를 보완했다. 직접 생성된 안전 예외에 suppress_context를 무조건 요구하는 대신 context가 있을 때만 확인하고, 원문 cause 없음과 실제 연결 traceback의 합성 sentinel 비노출을 검사한다. 기존 assertion 때문에 실패한 실행은 없었다.
최초 source 해시는 validation-1.json, 최종 실행 source는 validation-2.json에 당시 bytes로 보존했다. 최종 code7개는 실행 후 hash 변화0이다.

검증568개는 기존469개와 새 캐시99개다. 새 회귀는 문맥별 분리/legacy 불변·정확60초·invalid now·strict JSON/원형TTL·bounded read/write·unsafe file/부모/합성 다른 uid·생성0600/부모0700·write/flush/fsync/replace/fchmod 실패·old/new 완전 record·parent 교체·교체 후 committed 실패·source closure/실제 origin/KIS wiring을 포함한다.
다른 owner는 metadata만 합성하고 chown/권한 상승은 하지 않았다. synthetic sibling bytes/inode 보존을 확인했다. 합성 issuer는 네트워크 client가 아니다.

초기 정적 구문 검사에서 시스템 Python3.9가 기존 bootstrap의 Python3.12 f-string 문법을 해석하지 못했다. 이는 제품/보호 검사 실패가 아니며 기존 Python3.12로7개 source AST를 다시 확인해 통과했다.
실제 보호 검사 두 회차는 모두 성공했고 보호 실패·도구 거절·환경 차단은 없다. 검사 임시 root는 기존 controller가 각 회차 끝에 제거했다. 공개 review checkpoint만 남는다.

## 독립 검토 수용과 미검증

최종 독립 source-only 검토에서 제품 hash `3e090e2992aa9a0c7f78f644132765e616c002b35b5994ebc71a3f2fd26bad7f`와 pin 일치,
제품/실제 모듈 회귀/보호 입구에 필수 수정 없음, 비노출 보완 및 기존 hash2/선택·origin·OS/FS 경계 보존을 확인했다는 전달을 받았다.
직접 self16/unit568 결과는 개발 채팅의 실행이며 독립 검토자가 이를 재실행했다고 쓰지 않는다.

실제 자격/.env·기존 token cache/home·KIS 발급/수집·AI/DB·AI 전체 pytest·Flow 그래프/계산·Frontend는 미검증/범위 밖이다.
동일 uid의 악의적 프로세스·모든 조상 경로 공격·전원 장애 directory 영속성·다중 프로세스 발급 single-flight/정확히 한 번 발급을 보장하지 않는다.
다른 프로세스가 새 KIS 토큰을 발급해 기존 토큰이 무효화되는 제공자 한계도 남는다. 후속20행/20일 의미 작업은 이 branch에 섞지 않는다.

## 최종 파일·source SHA

허용11경로(기존7/신규4), 범위 밖0·staged0·비무시를 확인한다. 아래 실행 code7 hash와 문서3 hash를 보존하며 보고서 자체 최신 hash는 외부 final-source.json에 기록한다.
공개 checkpoint `/tmp/cf004-baseline-q52jews7/`에 final-source.json과 review-pathspec.nul(exact11), review-pr-body.md를 저장한다.

| 경로 | SHA-256 |
|---|---|
| `ai/src/agents/flow/infrastructure/token_cache.py` | `3e090e2992aa9a0c7f78f644132765e616c002b35b5994ebc71a3f2fd26bad7f` |
| `ai/src/agents/flow/infrastructure/kis_client.py` | `96a0b8783b0a46725e6092c8f2698caa4d6cde5e54083e3bdca1b12c222a8933` |
| `ai/tests/flow/test_kis_token_cache.py` | `116c3e449c147cf7d10b7a802758d7e694af314b5c3a99cf3a8ddf6ead6f2369` |
| `backend/tests/unit/test_cf004_kis_token_cache.py` | `edf4e69e104cab1750b0fb9315f56bf1da2310dc43625cebee6df50a3c284f0a` |
| `backend/scripts/check_safe.py` | `d0a244cd851063e94a930df124e40e9328108acad8b0dd68127fa2e1e4cb3fa4` |
| `backend/scripts/safe_checks_bootstrap.py` | `b1489de831263ddd97551f3dd2d67c6cc0f668744dafc0c9597d305cc3a38829` |
| `backend/tests/safe_checks/test_entry.py` | `2b8b0f7912e82b9f2bd6abbe677bf294f524e5e1a2de3761008cc837545014fa` |
| `ai/docs/contracts/flow/kis-token-cache.md` | `bef5cb07a86e69611f2a15135efaf7423f8dfa4af479d4e2ab9c68c43273c8ff` |
| `docs/development.md` | `1a5c4fcb03b0279d0dea7134b7bca0d90153b873a821e6382b44f0e822347ea2` |
| `docs/documentation.md` | `8985d46d0900f7c1467113d52df4dba2063930278516af9927b914747f873680` |

## 사용자 review·commit·Draft PR 초안

구현·선택 검증·독립 source-only 수용을 마쳤다. 아래 명령은 사용자 review 후 직접 실행할 초안이며 개발 채팅은 add/commit/push/PR/Ready/merge를 실행하지 않았다.
repo `bellra-jin/verith`, base `develop`, head `fix/flow-kis-token-cache`, 검토 HEAD `38c0b34a5741198484278767a7ada1c925f71301`이다.
전체 fetch/push URL은 `https://github.com/bellra-jin/verith.git` 하나이며 다른 변경·원격·branch·HEAD가 생기면 다시 대조한다. 임시 checkpoint가 없으면 검토된11집합을 다시 준비한다. 무조건 git add .를 쓰지 않는다.

읽기 전용 guard는 현재 HEAD/branch/staged0·전체 URL·exact dirty11·hash/regular single-link/no-symlink·비무시·pathspec을 확인한다.

```sh
cd /Users/parkjinhee/AI/verith_refactor/verith
/usr/bin/env -i PATH=/usr/bin:/bin LANG=en_US.UTF-8 /usr/bin/python3 -I -S -B - <<'CHECK'
from pathlib import Path
import hashlib,json,stat,subprocess
root=Path.cwd()
assert root==Path('/Users/parkjinhee/AI/verith_refactor/verith')
def git(*args): return subprocess.check_output(['/usr/bin/git',*args],cwd=root)
assert git('rev-parse','HEAD').decode().strip()=='38c0b34a5741198484278767a7ada1c925f71301'
assert git('branch','--show-current').decode().strip()=='fix/flow-kis-token-cache'
assert git('diff','--cached','--name-only')==b''
assert git('remote').decode().splitlines()==['origin']
for args in [('remote','get-url','--all','origin'),('remote','get-url','--push','--all','origin')]:
    assert git(*args).decode().splitlines()==['https://github.com/bellra-jin/verith.git']
folder=Path('/tmp/cf004-baseline-q52jews7')
manifest=json.loads((folder/'final-source.json').read_text())
assert len(manifest)==11 and set(manifest)==set(json.loads((folder/'baseline.json').read_text()))
changed=set(git('diff','--name-only','-z').decode().split('\0')[:-1])
changed.update(git('ls-files','--others','--exclude-standard','-z').decode().split('\0')[:-1])
assert changed==set(manifest)
for name,digest in manifest.items():
    path=root/name
    assert not any(p.is_symlink() for p in [path,*path.parents])
    info=path.lstat()
    assert stat.S_ISREG(info.st_mode) and info.st_nlink==1
    assert hashlib.sha256(path.read_bytes()).hexdigest()==digest
pathspec=b'\0'.join(p.encode() for p in sorted(manifest))+b'\0'
assert (folder/'review-pathspec.nul').read_bytes()==pathspec
ignored=subprocess.run(['/usr/bin/git','check-ignore','--no-index','-z','--stdin'],input=pathspec,capture_output=True)
assert ignored.returncode==1 and ignored.stdout==b''
subprocess.run(['/usr/bin/git','diff','--check'],check=True)
print('review guard passed: exact11, source SHA matched, staged0')
CHECK
```

guard 성공과 diff 검토 후 사용자가 순서대로 실행할 초안이다. add 후 staged diff가 검토11경로·bytes와 같고 HEAD가 여전히 위 값인지 확인한 뒤 commit한다. push/PR 전에도 branch와 전체 원격 주소를 다시 확인한다.

```sh
git add --pathspec-from-file=/tmp/cf004-baseline-q52jews7/review-pathspec.nul --pathspec-file-nul
git diff --cached --check
git diff --cached --stat
git diff --cached
git commit -m "fix: isolate Flow KIS token cache and persist tokens atomically"
git push --set-upstream origin fix/flow-kis-token-cache
```

<!-- CF004_PR_BODY_BEGIN -->
CF-004 v1.0(source SHA-256 5b6b2524e1f3d264faa3fd6d6796a5068a769c71a766e82b422d7c8d118dfda4)의 무키 Flow KIS 캐시 보완입니다. 서버+app key+secret에 결합한 별도 캐시와 strict token/JSON/TTL 검증을 stdlib 모듈로 분리했습니다. 기존 무결합 캐시는 읽거나 변경하지 않아 이후 첫 실제 실행에서 새 발급이 필요할 수 있습니다. 이번에는 실제 외부 호출·사용자 자격·기존 캐시를 사용하지 않았습니다.

no-follow/uid/single-link/0600 검사와 생성 시점0600·동일 dirfd 원자 교체를 적용했습니다. 안전 경계 위반은 발급으로 우회하지 않으며 교체 전 실패의 기존 파일 보존과 교체 후 실패를 구분합니다. KIS 연결은 두 소비자의 명시 base_url과 raw 응답 validator에 한정했습니다.

최종 보호 self16/16·고정14파일 unit568/568, exit0/guard0·각 owned root 제거입니다. 기존469개를 보존하고 실제 제품 모듈의 합성 캐시 회귀99개를 추가했습니다. 최종 독립 source-only 리뷰는 필수 수정 없음으로 수용됐으며 독립 runtime 재실행은 아닙니다.

AI pytest·실제 KIS 발급/수집·실캐시 전환·Flow 계산/그래프·AI/DB는 미검증/범위 밖입니다. 다중 프로세스 발급 single-flight·동일 uid 공격·전원 장애 directory 영속성은 보장하지 않습니다. 20행/20일·payload v1·CF-003 API/DB·Frontend는 변경하지 않았습니다. 실행/source SHA·제한은 docs/work/CF-004-flow-kis-token-cache.md에 기록했습니다.
<!-- CF004_PR_BODY_END -->

PR 본문은 정확 marker 사이만 추출하고 shell 본문 치환을 사용하지 않는다.

```sh
/usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -S -B - <<'BODY'
from pathlib import Path
text=Path('docs/work/CF-004-flow-kis-token-cache.md').read_text()
begin='<!-- CF004_'+'PR_BODY_BEGIN -->'
end='<!-- CF004_'+'PR_BODY_END -->'
assert text.count(begin)==text.count(end)==1
body=text.split(begin,1)[1].split(end,1)[0].strip()
assert body
Path('/tmp/cf004-baseline-q52jews7/review-pr-body.md').write_text(body+'\n')
BODY
gh pr create --repo bellra-jin/verith --base develop --head fix/flow-kis-token-cache --draft --title "fix: Flow KIS 토큰 캐시 격리와 안전 저장" --body-file /tmp/cf004-baseline-q52jews7/review-pr-body.md
```
