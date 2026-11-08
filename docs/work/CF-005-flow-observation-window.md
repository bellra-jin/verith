# CF-005 · Flow 관측기간 표시와 지속성 안내

## 현재 상태

**계산·저장 불변인 제공 관측기간 표시/LLM facts 보완 완료.** 최종 Backend self17/17·unit795/795,
Frontend self23/23·unit122/122·standalone type·대상 lint 모두 exit0이다. 예상 밖 guard 위반0·각 자기 root 정리를 확인했다.
대상 lint는 오류0/기존 source의 미사용 cls 경고1이다. 최종 독립 source-only 검토에서 추가 차단 결함 없음으로 수용됐다는 전달을 받았다.
독립 runtime 재실행·실제 원천 계산창/시장 coverage·앱 실행 성공을 뜻하지 않는다.

- 정본 CF-005 v1.1 전체 및 SHA `11b4cfa429311456a4b15ed9be5dfb74c371f71336def965c2bd2707dbaf99a4` 대조.
- v1.0 보존본 SHA `71a779c88f90174b05f118deb49b96ae8ec453ba067642a592ef352aeadd6796` 대조. v1.0은 읽기 준비만 했고 구현 기준은 v1.1이다.
- 기준/현재 HEAD `a6f27aa53c376bbfc5c3e8679aa50c9c02869518`, base develop, branch `fix/flow-observation-window`.
- PR #8 병합·clean develop·worktree1·전체 origin fetch/push URL `https://github.com/bellra-jin/verith.git`·동명 local/remote branch 부재 확인 후 fetch/ff-only→새 branch 순서로 준비했다.
- 공개 시작 bytes/hash는 `/tmp/cf005-baseline-xfis2tdi/baseline.json`에 보존했다. private 설정·캐시·사용자 자료는 복사하지 않았다.
- 운영 v1.1/v1.2/v1.2와 root/AI/Backend/Frontend AGENTS·문서 권위를 읽고 대조했다. 설치 Next16.2.10의 use-client·Server/Client Components·TypeScript 번들 가이드와 기존 Frontend 지침을 읽었다. Server Component/route/BFF 경계와 Next 규칙 블록은 유지한다.

## 실제 변경과 정책

[관측 안내 계약](../../ai/docs/contracts/flow/observation-window.md)을 따른다. stdlib Python helper와 순수 TS helper는
기존 daily/persistence를 읽어 unknown/insufficient/sufficient_rows라는 **view 상태만** 만든다. 새 payload 필드·저장 metadata가 아니다.

1~20행·canonical ISO date/고유/엄격 오름차순·3주체 유한 JSON 숫자·3주체 전체 저장 합과 실제 bool 판정이 필요하다.
저장/유도 합을 rel_tol1e-9/abs_tol1e-6 및 별도 음/0/양 부호로 대조하고 consistent도 양쪽 합에서 확인한다. 0/-0은 같은0으로 판정하되 원값은 보존한다.
부족/불명은 지속성 일관/상이 결론과 배지를 보류한다. 20행은 제공 자료 행수·내부 정합 근거일 뿐 거래일 완비·수집 누락 없음·원천 계산창 보증이 아니다.

safe daily와 유한 persistence 셀을 실제 순회·산술·날짜 포맷 앞에서 사용한다. 비배열/null/비객체 row·잘못된 날짜/숫자를0으로 바꾸거나 제거·정렬해20행으로 수선하지 않는다.
안전한 daily를 만들 수 없으면 placeholder이고 없는 persistence 셀은 자료 없음이다. 정상0·정상 숫자·막대 계산을 보존하며 malformed daily 때문에 다른 정상 저장 합/ratio를 덮어쓰지 않는다.
고정5/20거래일 캡션은 제공 관측/미확인 기준으로 바꾸고, 충분한 행수에서만 같은 비영 부호/반대 부호/합0을 구분한다.

LLM facts는 같은 view 판정을 사용한다. 부족/불명이면 persistence 합/판정은 제공하지 않고 결정론적 비교 보류만 제공한다.
충분한 경우도 제공 자료 기준이며 실제 LLM 실행·Gate3/retry는 바꾸지 않는다. 기존 interpretation은 그대로 전달하고 본문 바로 앞에 저장 당시 해석·기간 한계 안내를 둔다.
해석이 null이어도 검증 카드 cap에 저장 당시 대조 결과·기간 비보증·window.notice가 남는다. 과거 원문의 기간 주장을 삭제한 것이 아니라 한계를 고지한 것이다.

원 producer domain/signals.py·config/workflow·Gate1/3·payload/export·Backend schema/owner/auth·CF-004 캐시·Frontend BFF·의존성은 불변이다.
Gate2 규칙5는 **성공 설명 문자열 한 곳만** 실제 대조 행수/기간 충족 검사 아님으로 바꾸었다. 조건·허용오차·passed/failures와 저장된 과거 checks는 유지한다.

## 구현 중 source 검토와 수정

- Python3.12 built-in sum은 보상 합산이고 JS reduce는 순차 binary64 덧셈이므로 표시 근거가 달라질 수 있다는 source-only 지적을 받았다.
  표시 helper만 accumulator0.0부터 명시적인 순차 float 덧셈으로 맞췄다. producer/Gate2/저장 합은 바꾸지 않았다.
  앞17행0·마지막[1e16,1,-1e16]의 저장합1/consistentTrue→양쪽unknown, 저장합0/False→양쪽sufficient_rows/neutral을 공통fixture로 검증했다.
  수정 전 source를 실제 실행해 실패를 재현했다고 주장하지 않는다. 이 보완은 첫 보호 실행 전에 반영했다.
- 검증 카드 cap의 기간 안내 누락도 지적받았다. 해석 존재 여부와 무관한 cap에 저장 당시 결과/기간 비보증/window.notice를 두고 TSX source 회귀로 확인했다.
- 위 보완 뒤 독립 read-only 검토에서 핵심 구현·새 테스트에 추가 차단 결함 없음을 확인했다는 전달을 받았다.
  reviewer Python helper `acc50bc0aec7e0eee207f62a3b6bce00f2e37ce7d14e31de1acabc4c2d07ea27`,
  TS helper `5496c23157ca7618d3601392b90892666682198a9720da32b7d3b5bc475e116d`,
  fixture `9db1dabb4ad832d79f54089864f9200bdc08cc5db4c04f8bacf90f5c0c089634`는 현재 bytes와 직접 대조해 일치했다.

## 검증 방법·실제 결과

기존 보호 entry의 source identity/hash·OS/FS/network/private·dependency·수집/종료 origin·timeout·정리는 유지했다.
Backend에 새 stdlib helper/hash1·고정 unit1·source-only verification/builder/prompt/**단일 HTML**4개와 공통 fixture만 exact 추가했다.
기존 models/payload2 hash·CF-004 cache pin·CF-003/004 검사와 namespace는 보존하고 기존 domain의 helper origin1만 더 확인했다.
Frontend는 새 helper/unit/fixture의 fixed/fresh·고정 unit·대상 lint만 추가했다. guard·mode·Host/TLS/포트·package/lock은 그대로다.

공통 fixture64개는 표준 JSON 합성 자료다. 1/4/5/19/20행·누락/타입/날짜/역순/중복·합/판정 불일치·합0/반대부호·모든 주체/각 창의 근접0 부호 충돌·음의0·상쇄·overflow를 포함한다.
NaN/Infinity는 양쪽 test 안에서 별도로 주입했다. 원 input/저장값 mutation0을 대조했다. 이 fixture는 실제 시장/계산 결과가 아니다.

Backend는 **실제 helper 모듈**을 import한다. `_facts_to_text`·`_daily_view`·`_persistence_view`는 정확한 함수 하나씩만 AST 선택하고
호출/attribute/default/금지 구문을 사전 검사한 뒤 실제 helper·고정 SUBJECTS·순수 config 값/제한 builtins를 주입해 실행한다.
LLM/builder 모듈 전체를 import하지 않는다. 단일 HTML은 텍스트 배선 검사만 하고 Jinja loader/render를 실행하지 않는다.
Frontend는 설치 TypeScript로 실제 순수 TS helper를 transpile/VM 실행한다. TSX의 safeDaily 선행·finite 셀·상태 조건·인접 경고는 source/AST 배선으로 확인하며 React DOM을 실행하지 않는다.

기존 Gate2 성공 문구만 copy AST에서 되돌리면 기준 verification 모듈 AST hash가 일치한다. 실제 explain 호출 함수·build_report의 기존 전달값·다른 renderer 함수 AST도 기준과 일치한다.
원 producer/config/workflow/cache·CF-003/004 및 기존 계약 unit·Frontend guard의 Git diff0도 확인했다. 기존 원문은 builder의 해석 formatter/전달 배선과 TSX의 동일 prop 사용으로 보존한다.

2026-11-08 KST에 repo root에서 아래 여섯 workload를 각각 실행도구 `sandbox_permissions=require_escalated`로 직렬 실행했다.
기존 절대 interpreter·clean env와 Node 시작 전 OPENSSL_CONF=/dev/null을 유지했다. 각 명령의 정확 시작/끝 시각은 별도 수집하지 않았다.

```sh
/usr/bin/env -i LANG=en_US.UTF-8 TZ=UTC /Users/parkjinhee/AI/verith_refactor/verith/backend/.venv/bin/python -I -S backend/scripts/check_safe.py self-test
/usr/bin/env -i LANG=en_US.UTF-8 TZ=UTC /Users/parkjinhee/AI/verith_refactor/verith/backend/.venv/bin/python -I -S backend/scripts/check_safe.py unit
/usr/bin/env -i LANG=en_US.UTF-8 TZ=UTC OPENSSL_CONF=/dev/null /opt/homebrew/Cellar/node/22.7.0/bin/node frontend/scripts/check-local-ports.mjs self-test
/usr/bin/env -i LANG=en_US.UTF-8 TZ=UTC OPENSSL_CONF=/dev/null /opt/homebrew/Cellar/node/22.7.0/bin/node frontend/scripts/check-local-ports.mjs unit
/usr/bin/env -i LANG=en_US.UTF-8 TZ=UTC OPENSSL_CONF=/dev/null /opt/homebrew/Cellar/node/22.7.0/bin/node frontend/scripts/check-local-ports.mjs type
/usr/bin/env -i LANG=en_US.UTF-8 TZ=UTC OPENSSL_CONF=/dev/null /opt/homebrew/Cellar/node/22.7.0/bin/node frontend/scripts/check-local-ports.mjs lint
```

unit/type/lint의 전체 Frontend 출력은 pipefail shell에서 자기 checkpoint의 frontend-{unit,type,lint}-1.log로 stdout/stderr를 보존했다. argv/workload·exit는 그대로다.

| 실제 실행 | 수집/통과·exit·증거 |
|---|---|
| Backend self | 17/17 exit0, chunk257cca, 자기 root 제거 |
| Backend unit | 고정15파일 수집795/pass795/fail0/skip0·guard0·exit0, session9171/chunkd6cc3e, 자기 root 제거 |
| Frontend self | 23/23·fail/skip/cancel/todo0·exit0, chunkcd5cd0, 자기 root 제거 |
| Frontend unit | 고정5파일의10/2/3/23/84개 합계122/122·fail/skip/cancel/todo0·exit0, session52952/chunk23a383, 자기 root 제거 |
| Frontend type | standalone core/image tsc exit0, session68076/chunk47b86b, 자기 root 제거 |
| Frontend 대상 lint | 오류0·경고1·exit0, session27472/chunk1377ed, 자기 root 제거 |

Backend 기존568개+새227개, Frontend 기존37개+copy 배선1개+새84개다. 실제 실행 실패·누락/skip·환경/도구 거절은 없었다.
lint의 cls 경고는 시작 source에서도 정의만 있고 callsite가 없으며 해당 함수 본문은 현재와 동일하다. 과거 source를 lint 재실행한 결과라고 쓰지 않는다.

Frontend self/unit의 합성 음성 거부14건은 expectedNegatives14와 같고 예상 밖 위반0이다. unit worker5/exit record5/partial0, type/lint 각 worker1/exit record1/partial0·거부0이다.
관측 범위는 instrumented JS fs journal이며 native 전체 관측이라고 주장하지 않는다. 자기 OS native canary와 scoped journal을 구분한다.
모든 workload가 자기 임시 root 제거를 출력했다. 기존 자원은 변경하지 않았고 공개 review checkpoint만 남는다.

## 한계·최종 범위

이번 수용은 **표시/입력 내부 정합·합성 helper/추출 함수·source 배선·standalone type/대상 lint**다.
pandas 실제 계산·Gate2 런타임·AI 전체 pytest/graph·Jinja HTML render·React DOM/브라우저·실제 LLM/앱은 미검증이다.
standalone tsc는 full generated-route/typegen/Next build 성공이 아니다. 실제 .env/키·실캐시/home·KIS/AI/DB·외부 API·설치는 사용하지 않았다.
원문 경고는 과거 해석의 기간 단정을 제거하거나 실제 모델 준수를 보증하지 않는다. 원천 coverage/metadata·20행 부족을 Gate 실패로 바꾸는 정책·기존 해석 숨김·worker/fake AI 실행은 후속이며 이 branch에 섞지 않는다.

최종20경로(기존13/신규7)·범위 밖0·staged0·비무시·diffcheck·새 문서 링크와 아래 읽기 전용 guard를 대조한다.
실행 후 code16개는 `/tmp/cf005-baseline-xfis2tdi/validated-code.json`에 보존했고 최종 문서 마감 중 변경하지 않았다.
아래19개 SHA와 보고서 자체 최신 SHA를 포함한 exact20 manifest는 같은 폴더의 final-source.json이다. review-pathspec.nul과 review-pr-body.md도 같은 checkpoint에 준비한다.

## 최종 source SHA

| 경로 | SHA-256 |
|---|---|
| `ai/src/agents/flow/domain/observation_window.py` | `acc50bc0aec7e0eee207f62a3b6bce00f2e37ce7d14e31de1acabc4c2d07ea27` |
| `ai/src/agents/flow/domain/verification/signals.py` | `dc208bdff7d422e605a0c72c4841874c6862f51a9179895df44013800d5d0d30` |
| `ai/src/agents/flow/infrastructure/llm/explain.py` | `dd0a82a8a6ef50fbc6bc2d82058fc3c7851cded0c29490b3ab7bd1aeb526796a` |
| `ai/src/agents/flow/prompts/explain.txt` | `f2990926e5b8c95ebbc423aa40529476c3fe53981a67d3abbeb5f6f0096294c5` |
| `ai/src/agents/flow/infrastructure/render/builder.py` | `7aef0f665f19767737eadec28b34b4e4b17d880d9766e5d1191dc898cdc38283` |
| `ai/src/agents/flow/infrastructure/render/templates/supply_demand.html` | `6df8e7067dfbacbced340317686d45a246990237627105ce714ced7fe7f796ee` |
| `frontend/src/features/flow/lib/observation-window.ts` | `5496c23157ca7618d3601392b90892666682198a9720da32b7d3b5bc475e116d` |
| `frontend/src/features/flow/components/flow-report-view.tsx` | `101671b4c795aab112bda6ae1e675420752f76305e6ae26cd70edd4b1731d4e0` |
| `backend/scripts/check_safe.py` | `867029c3365bebbfa1f6d3bd2b137447f458385b927df4168942f906e075d082` |
| `backend/scripts/safe_checks_bootstrap.py` | `2b4f706192b9ca20770b3005843d934bcdd44dace385168f84920904b9ca68a6` |
| `backend/tests/safe_checks/test_entry.py` | `28a3968344600dcaee06b0378c16bc3e4066e1ae341356028ec074e9e565038c` |
| `backend/tests/unit/test_cf005_flow_observation.py` | `a5ef2ac36b9289e90171e5f62d69bc72795040dc2abdb6ff3e8c43d6c0c899c6` |
| `frontend/scripts/check-local-ports.mjs` | `8404cfea193e82c84309a4fe4f14d84d8ae63c41541d4a0b4dc03daac22fe1e5` |
| `frontend/tests/tooling/safe-checks.test.mjs` | `057cd3313c41f0e8ad7f421b9c95949b5441bba0ff70ba3f1c7fa54d5fa3965e` |
| `frontend/tests/unit/flow/observation.test.mjs` | `3712fcca831cccd6f3dd08b6717576864b5677d40780360f9a8f8987b5866e90` |
| `frontend/tests/fixtures/cf005-observation-cases.json` | `9db1dabb4ad832d79f54089864f9200bdc08cc5db4c04f8bacf90f5c0c089634` |
| `ai/docs/contracts/flow/observation-window.md` | `3a730412427863368b97aae327994eeb670f642362bb6bafebc5353fd5bec96c` |
| `docs/development.md` | `3cbdf8c3b893f17666f207035db0e7fd6f0b279d6e2d42834f295e891206297a` |
| `docs/documentation.md` | `03770accb03330fcba6185fe982c63697145efae9d7555bed93a3f3f6cf3ce88` |

## 사용자 review·commit·Draft PR 초안

아래는 사용자 review 후 직접 실행할 초안이다. 개발 채팅은 git add/commit/push/실제 PR/Ready/merge를 실행하지 않았다.
repo `bellra-jin/verith`, base `develop`, head `fix/flow-observation-window`, 검토 HEAD `a6f27aa53c376bbfc5c3e8679aa50c9c02869518`이다.
정확한 전체 origin fetch/push URL은 `https://github.com/bellra-jin/verith.git` 하나다. 검토 뒤 변경·추가 원격·다른 HEAD/branch가 생기면 다시 확인한다.
checkpoint가 없으면 검토된20집합을 다시 준비하며 git add .를 무조건 실행하지 않는다.

아래 사전 guard는 **읽기 전용**으로 실행한다. 현재 HEAD/branch/staged0·전체 URL·exact dirty20·hash/regular single-link/no-symlink·비무시·pathspec을 대조한다.

```sh
cd /Users/parkjinhee/AI/verith_refactor/verith
/usr/bin/env -i PATH=/usr/bin:/bin LANG=en_US.UTF-8 /usr/bin/python3 -I -S -B - <<'CHECK'
from pathlib import Path
import hashlib,json,stat,subprocess
root=Path.cwd()
assert root==Path('/Users/parkjinhee/AI/verith_refactor/verith')
def git(*args): return subprocess.check_output(['/usr/bin/git',*args],cwd=root)
assert git('rev-parse','HEAD').decode().strip()=='a6f27aa53c376bbfc5c3e8679aa50c9c02869518'
assert git('branch','--show-current').decode().strip()=='fix/flow-observation-window'
assert git('diff','--cached','--name-only')==b''
assert git('remote').decode().splitlines()==['origin']
for args in [('remote','get-url','--all','origin'),('remote','get-url','--push','--all','origin')]:
    assert git(*args).decode().splitlines()==['https://github.com/bellra-jin/verith.git']
folder=Path('/tmp/cf005-baseline-xfis2tdi')
manifest=json.loads((folder/'final-source.json').read_text())
assert len(manifest)==20 and set(manifest)==set(json.loads((folder/'baseline.json').read_text()))
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
print('review guard passed: exact20, source SHA matched, staged0')
CHECK
```

guard 성공·diff 검토 뒤 사용자가 아래 각 명령을 직접 실행한다. add 후 staged diff가20경로/검토 bytes와 같고 HEAD가 위 값인지 확인한 뒤 commit한다.
commit 후 HEAD 변경은 예상된 것이며 위 pre-stage guard를 그 상태에 그대로 재사용하지 않는다. push/PR 전에도 현재 branch·전체 원격 주소를 확인한다.

```sh
git add --pathspec-from-file=/tmp/cf005-baseline-xfis2tdi/review-pathspec.nul --pathspec-file-nul
git diff --cached --check
git diff --cached --stat
git diff --cached
git commit -m "fix: clarify Flow observation windows without changing stored signals"
git push --set-upstream origin fix/flow-observation-window
```

<!-- CF005_PR_BODY_BEGIN -->
CF-005 v1.1(source SHA-256 11b4cfa429311456a4b15ed9be5dfb74c371f71336def965c2bd2707dbaf99a4)의 계산·저장 불변인 Flow 관측 안내 보완입니다. 기존 daily/저장 합·판정의 내부 정합을 Python/TS view helper로 확인하고 제공 관측 부족/미확인에서는 지속성 결론을 보류합니다. 20행도 거래일 완비나 원천 계산창 보증으로 표현하지 않습니다.

malformed daily/row/date·비유한 셀은 순회·산술·포맷 전에 안전하게 후퇴하고 누락을0으로 채우지 않습니다. 정상 저장 숫자·payload·data_status·Gate 판정은 유지합니다. 기존 해석 원문은 인접 경고로 보존하고, 해석이 없어도 검증 배지 옆에 저장 당시 대조/기간 비보증 안내를 둡니다. LLM facts는 부족/미확인 지속성 합·판정을 공급하지 않습니다.

최종 보호 Backend self17/17·고정15파일 unit795/795, Frontend self23/23·고정5파일 unit122/122·standalone type·대상 lint 모두 exit0입니다. 예상 밖 guard0·각 자기 root 제거, lint 오류0/기존 미사용 cls 경고1입니다. 공통64fixture의 부호/근접0/상쇄 및 실제 helper·정확 추출 함수 회귀를 확인했습니다. 최종 독립 source-only 검토에서 추가 차단 결함 없음으로 수용됐으며 독립 runtime 재실행은 아닙니다.

pandas/Gate2 런타임·AI 전체 pytest/graph·Jinja/React DOM/브라우저·실제 LLM/앱·KIS/DB는 미검증/범위 밖입니다. standalone type은 full Next generated-route/typegen/build가 아닙니다. source wiring 검증을 실제 render 성공으로 확대하지 않습니다. 실제 사용자 자격·키·기존 캐시는 사용하지 않았습니다. 실행/source hash·제한은 docs/work/CF-005-flow-observation-window.md에 기록했습니다.
<!-- CF005_PR_BODY_END -->

정확 marker 사이만 추출하고 shell 본문 치환으로 명령에 삽입하지 않는다.

```sh
/usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -S -B - <<'BODY'
from pathlib import Path
text=Path('docs/work/CF-005-flow-observation-window.md').read_text()
begin='<!-- CF005_'+'PR_BODY_BEGIN -->'
end='<!-- CF005_'+'PR_BODY_END -->'
assert text.count(begin)==text.count(end)==1
body=text.split(begin,1)[1].split(end,1)[0].strip()
assert body
Path('/tmp/cf005-baseline-xfis2tdi/review-pr-body.md').write_text(body+'\n')
BODY
gh pr create --repo bellra-jin/verith --base develop --head fix/flow-observation-window --draft --title "fix: Flow 관측기간 표시와 지속성 안내 정합성" --body-file /tmp/cf005-baseline-xfis2tdi/review-pr-body.md
```
