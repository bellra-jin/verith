# CF-014 Flow 근거 검증과 선택형 해석

기준 develop `546413090dbb7059d677d545489a43e55eca1446`, branch
`fix/flow-grounded-interpretation`. CF-014 v1.1 정본 SHA-256은
`3d61b387bf675b004f4ad13e39f38741708c241895cb84873b8629aba62dd4c6`이다.
기능/문서 18경로와 원격 CI workflow 1경로의 총 19경로다.

연속일수 원자료 독립 검증과 [신규 해석 정책](../contracts/flow-interpretation-policy-v1.md)을
구현한다. LLM의 ID 선택과 코드의 문장 구성을 분리하고 최대 3회 후 fact_only로
후퇴한다. 수급 계산·v1 payload·관측창·저장/조회/구 snapshot 복구는 유지한다.
소진율은 원자료 전체로부터 producer와 같은 최근 5행을 비교한다.

## 검증 상태

최종 source에서 기존 보호 입구 `quality-self` **2/2**, `quality-unit` 단일
`test_cf014_flow_quality.py` **77/77**이 각각 exit0으로 통과했다.
unit의 `guard_violations=0`, 양쪽 자기 임시 root 제거를 확인했다.
초기 self2 통과 후 독립 source 검토의 raw19/daily20 불일치 보완으로 source/pin이
변경되어 self2만 영향 재검증했다. unit은 보완된 source에서 한 번 실행했다.
기존 전체 suite·PG·Frontend type/lint/build·앱·브라우저는 반복하지 않았다.
AI 제품/prompt 14개와 기존 worker origin 호환용 pinned token_cache 1개만 복사한다.
호환 모듈은 import만 하며 캐시 연산을 수행하지 않는다. 보호 worker·OS/FS/network
guard는 변경하지 않는다. pure 함수 및 고정 AST 함수 실행은 전체 pandas/graph,
LangChain/공급자 실행과 구분한다. 실제 KIS/OpenAI·키/개인 설정·DB·브라우저 검사는 없다.

## 원격 CI

`PR safe checks / flow-quality`는 develop 대상 PR의 draft 단계부터 실행한다.
공개 표준 macos-15, Python 3.12.10 arm64, uv 0.13.7을 고정하고 기존 Verith Backend
lock의 wheel만 설치한다. 원격 캐시·프로젝트 설치·sdist build·Python 자동 다운로드는
사용하지 않는다. 이후 기존 보호 입구의 focused self/unit만 clean env로 실행한다.
원격 최신 head의 실제 job/guard 결과 확인 전에는 병합하지 않는다.

공식 tag를 직접 조회해 checkout v6.0.2 `de0fac2e4500dabe0009e67214ff5f5447ce83dd`,
setup-python v6.0.0 `e797f83bcb11b83ae66e0230d6156d7c80228e7c`, setup-uv v10.3.2
`07a047e608db84b3d8c06cd9a7c7dcc9c355c18e`를 pin했다.
uv arm64 archive checksum은 [공식 0.13.7 release](https://github.com/astral-sh/uv/releases/tag/0.13.7)의
[checksum](https://releases.astral.sh/github/uv/releases/download/0.13.7/uv-aarch64-apple-darwin.tar.gz.sha256)을 사용한다.
로컬 통과와 원격 실행 성공은 별개다. 첫 원격 run은 아래 metadata 경계에서 중단했고, 공식 전용 runtime으로 후속 확인한다. native canary나 runtime/dependency metadata
보호 실패는 해당 원인으로 보고하며 조건 완화로 통과시키지 않는다.


## 첫 원격 CI와 전용 runtime 보완

[첫 CI](https://github.com/bellra-jin/verith/actions/runs/42503459227)는 PR head
`7be00f4b12bbb89d58dcb5fc78aa850e7357110b` / 실제 checkout merge
`cda7f15cdc3f31c4a766465be954ee59767fec4c`에서 설치까지 성공한 뒤 metadata guard
exit78로 중단했다. [진단 CI](https://github.com/bellra-jin/verith/actions/runs/42503736352)는
head `19d4f5f7488d5012c678118e67bbef7a6641177f` / checkout merge
`bb33b0c40589e1f965918cd09c02d4a0bd286d94`였다. runner uid501,
canonical `/Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12` 및 runtime
`/Library/Frameworks/Python.framework/Versions/3.12`가 uid0/mode0775여서 group-write 조건에
걸렸다. site-packages는 uid501/mode0755로 적합했다. 두 회차 원격 self/unit 실행은 0이다.
기존 toolcache chmod·복사·guard 예외 추가 없이 중단했다.

후속 workflow는 checksum pin된 uv0.13.7의 내장 Python metadata를 사용한다.
[정확 항목](https://raw.githubusercontent.com/astral-sh/uv/0.13.7/crates/uv-python-managed/download-metadata.json)의
`cpython-3.12.10-darwin-aarch64-none` URL은
`https://github.com/astral-sh/python-build-standalone/releases/download/20250529/cpython-3.12.10%2B20250529-aarch64-apple-darwin-install_only_stripped.tar.gz`,
SHA-256은 `2579c9ffcbb0a745f1de3d645612c7466269eb9a23316a54ece49d50c1c9122f`다.
[공식 다운로드 코드](https://raw.githubusercontent.com/astral-sh/uv/0.13.7/crates/uv-python-managed/src/downloads.rs)의
embedded catalog·HashReader·HashMismatch 경로를 읽었다. clean env에서 metadata override를
사용하지 않고 canonical 공식 release source로 제한한다. uv의 안전 추출 경로와 별도로
새0700 디렉터리의 전체 경로/링크 및 uid/mode를 읽기 검증한다. setup-python runtime은
이 filesystem metadata 검사만 수행하며, lock 설치와 보호 검사는 새 절대 Python만 쓴다.
venv canonical interpreter가 자기 디렉터리 밖이면 실패하고 toolcache로 후퇴하지 않는다.
표준 CI의 일회용 runner 공간에만 설치하며 원래 toolcache/OS 권한·guard는 불변이다.
[전용 Python 첫 회차](https://github.com/bellra-jin/verith/actions/runs/42504452140)는
head `dafb7849d373dca8bf2f212073f64b409d700873` / checkout merge
`52cada0c7485a2b9b59ae1cd28d984c9e2e2bd86`에서 공식 managed Python 설치 후,
추가한 모든 절대 symlink 거부 assertion에서 중단했다. 실패 링크 자체 경로는 미수집이므로
아래 알려진 링크와 같았다고 확정하지 않는다. 해당 회차 wheel/self/unit은 미실행이다.

[공식 uv managed source](https://raw.githubusercontent.com/astral-sh/uv/0.13.7/crates/uv-python-managed/src/managed.rs)의
minor-version link 생성 경로에 맞춰 자기 root의
`runtime/cpython-3.12-macos-aarch64-none` 한 개만 정확한 patch runtime
`runtime/cpython-3.12.10-macos-aarch64-none`으로의 raw 절대 대상 및 canonical 대상이
모두 일치할 때 지원한다. 그 외 절대 링크·모든 root 외부 escape는 계속 거부한다.
뜻밖의 거부는 자기 root 상대경로/고정 사유/대상 상대경로만 기록하고 외부 대상은
고정 redaction한다. 기존 metadata/OS/FS/network guard와 제품 source는 변경하지 않는다.
후속 실제 결과는 별도로 확인한다.

## 범위·호환·source 검토

기존 수급 계산·관측창·payload exporter·config source는 불변이다. AI/Backend DTO와
Backend domain은 SPEC 상수 외 AST가 기준과 같고, Gate2 규칙3 이후 bytes는 동일하다.
Gate2 규칙2만 strict 원자료/날짜/주체/threshold 대조로 연결한다. 신규 bank의 소진율
창을 실제 producer의 최근5행으로 맞추고, raw/daily 창 불일치는 bank 거부로 처리했다.
구 SPEC stored snapshot의 adapter freeze/from_stored에서 원 ID/JSON/hash를 유지했다.

실행 검사는 실제 pure helper·Gate3·payload/adapter와 고정 workflow/facts/rule2 AST
함수 실행이다. pandas 계산 전체·graph·LangChain·LLM/실제 KIS 품질을 실행한 결과로
확대하지 않는다. runtime fingerprint/caps 및 미실행 wiring은 source/AST 확인이다.
AI 기존 Gate3 테스트의 기대를 새 정책에 맞췄으나 raw AI pytest는 실행하지 않았다.
독립 source 검토와 개발측의 위 직접 실행을 구분한다.

정책 source SHA-256 `4cf9fa103736cc5c852eb96cbb1f42253ad875f89bccf3dcd47a43bb76f6fd22`,
prompt SHA-256 `9e8a04b6d7d0f534d54552e78ed489cb74f3cc7160fbd379b030758ae891406c`.
실행 로그·source 목록은 자기 checkpoint에 보존한다. 새 소스 변경이 없으면 통과한
로컬 검사를 반복하지 않는다.

## PR 본문

<!-- CF014_PR_BODY_START -->
신규 Flow 해석에서 LLM은 검증 fact ID만 선택하고 코드는 확정일·주체·원자료 관측창·단위를 결합한 3문단을 구성합니다. 원자료 연속 순매수 길이와 신호를 독립 검증하고, 빈/잘린 선택 응답도 최대3회 뒤 기존 fact_only로 후퇴합니다. 기존 계산/v1 payload·관측창·원 SPEC 저장본의 복구는 유지합니다.

검증: 보호 focused self 2/2, 단일 unit 77/77, guard0, 자기 임시 root 정리. pure 함수/고정 AST 및 합성 stored snapshot 확인이며 실제 KIS/OpenAI·pandas/graph·DB·브라우저 품질 검증은 아닙니다. 신규 PR CI는 macos-15에서 고정 공식 action·Python/uv와 Verith lock wheel 설치 후 같은 보호 focused self/unit을 실행합니다. 최신 PR head의 실제 원격 결과를 확인한 뒤 병합합니다.
<!-- CF014_PR_BODY_END -->
