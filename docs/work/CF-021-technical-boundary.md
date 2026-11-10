# CF-021 · Technical typed boundary 완성

상태: 기존 WIP 이식·구현과 focused 보호 검사 완료 정리 중. 독립 최종 검토·원격 게시/CI는 pending. 실제 DB/engine/provider/공개 Technical/차트 화면은 미실행이다.

## 기준·원본 보존

정본v1.0 SHA256 `264b9fbb9d4e1d101267cf462b50013e4a32e100eb502006d7b9e7ae4a865f8a`의 정확27경로를 따른다. 사용자 최신 지시에 따라 과거 중단된 Technical WIP를 완성한다. 새 전용 worktree branch는 `feat/technical-boundary-completion`, 검증된 remote develop/base는 `6e9e625ed18a9a6b48cd06012e662d703aaf1de7`다.

원본 feat/technical-typed-boundary at bba0305의 tracked4개·신규11개 모두 허용 범위 안임을 확인하고 파일별 원 base/WIP/새 base/이식 hash와 tracked patch를 private checkpoint에 기록했다. 신규11개는 정확 파일만 복사했고 tracked4개는 diff를 apply-check한 뒤 이식했다. 최신 base에서 달라진 AIClient는 전체 덮어쓰기 없이 기존 Technical diff만 적용해 후속 Supervisor 메서드를 보존했다. 원래 branch/index/WIP와 CF026/CF028 작업공간·private 자료는 변경하지 않았다. reset/stash/clean·stage/commit/push는 실행하지 않았다.

## 구현

- 순수 공통 envelope와 AI/Backend typed Technical 상세, immutable AnalysisContext/report binding, 실제 Backend→ASGI MockTransport→주입 fake engine→strict freeze→chart props 왕복.
- disabled/lazy router와 legacy 실행 폐쇄, 고정 token/경로·body/response/3초 한도·취소 뒤 소유 async task slot 유지. 남은 budget0/만료는 task 생성 전 거절.
- intraday 검증 상수0.05/3만 순수 모듈로 이동. config re-export와 나머지 설정/계산 보존.
- 공유 fixture와 순수 boundary-preview·기존 date/price/RSI/level helper 회귀. 공개 UI/BFF/실제 rendering 추가 없음.
- 고정 AI28 source pin과 단일 Backend 수집 파일·정확 Frontend technical-boundary-unit/type/lint 모드. 기존 bootstrap/guard/OS/FS/network·package/lock 보존. 기존 원격18 보호단계 유지 후 boundary self/unit2개만 추가한다. 옛 정본의12단계 표기는 당시 base 이력이며 최신18개를 삭제하지 않는다.

## 실행 준비와 보호

Backend lock/pyproject와 기존 설치 runtime/owner·mode를 검증한 뒤 새 worktree의 없는 backend/.venv만 정확 기존 설치로 alias했다. Frontend도 고정 package707bytes/SHA와 lock·설치 version/소유를 확인한 뒤 없는 node_modules만 alias했다. 설치/사본/기존 dependency 변경은 없다.

Frontend caller #21–22 안에서 기존 core와 새 Technical sibling만 정확 일치로 허용하고 유일한 기존 dependency/metadata root를 유지했다. 유사 이름·다른 workspace/dependency·target/realpath 변조·untrusted uid/mode를 거절하며 pre/post source/package/lock/owned manifest 검사는 그대로다. CF028이 먼저 병합되면 그 verification sibling 허용을 삭제하지 않도록 최신 caller diff와 tooling 회귀를 재조정·영향 재검증해야 한다. 다른 WIP source나 임의 prefix/env/CLI root를 입력으로 쓰지 않는다.

## 검증 상태와 한계

집중 보호 self/unit·FEunit/type/lint의 최종 명령·수/로그hash/정리 binding은 최종 checkpoint에 확정한다. Backend/AI source-only 보존은 이전 public Supervisor/Flow/Fundamental·News registry·wire/fingerprint/snapshot의 byte/AST/pin 대조이며 실제 전체 behavior suite로 집계하지 않는다.

실제 engine·provider/key/.env·DB/PG·Google·운영 startup·공개 Technical 실행·Recharts/React/브라우저·실자료 cutoff 품질은 미실행이다. fake async engine/ASGI와 차트 props 검증은 이 수용을 대신하지 않는다. stage는 명시 unavailable이며 DB0, 새 owner/usage/lifecycle 구현은 후속이다. 합성 비용/ID를 실제 승인·예산 기록으로 사용하지 않는다.


## 최종 직접 검사와 실패/수정 이력

Backend는 검증된 새 worktree alias의 Python3.12.13과 `env -i LANG=en_US.UTF-8 TZ=UTC <절대 backend/.venv/bin/python> -I -S -B <check_safe.py>`의 technical-boundary-self/unit으로 실행했다. self3/3, 단일수집 파일 unit175/175, guard 위반0·exit0, 각각 자기 임시 root 제거가 확인됐다. 최대3초 remaining 검사를 task/slot 이전과 input projection 이후에 적용하고0/음수/비유한/검증 중 만료에서 engine0/slot0을 직접 검사했다. 실제 Backend→인증된ASGI→주입 fake→strict freeze/preview 왕복, waiter timeout/cancel 뒤 busy 유지와 실제 child settlement도 포함한다. 실제 sync/provider 중단 검증은 아니다.

Backend 최종 실행의 도구 출력은 전체가 보존됐지만 처음부터 파일 redirect한 로그는 아니었다. self tool chunk e8a241/unit b75c67의 완전한 visible combined output·반환 객체·명령/provenance를 이후 추출해 private checkpoint에 보존했다. stdout/stderr 분리와 실제 실행 wall-clock은 도구가 제공하지 않아 주장하지 않는다. 추출본 hash는 self `60b98a71915ba4832bcef429826756a372818e8b58ec0aa918393d3dbc6ae84b`, unit `cadd34ff82768106aed5a332f1b1063e24a034c417ec5147f50fe7a2ca20bddd`다. 이 추출을 새 실행으로 세지 않는다.

Frontend는 검증된 절대 Node22.7.0과 `env -i OPENSSL_CONF=/dev/null <절대 Node> frontend/scripts/check-local-ports.mjs <mode>`를 새 전용 root에서 사용했다.

| mode | 실제 결과 | 로그 SHA256 |
|---|---|---|
| technical-boundary-unit | 65통과=preview15+tooling50, fail/skip/cancel0, parent0 | `ca1b98f8ecf24820ca466639a493ee6887ee0cfa291a817da9f0e34e22df376d` |
| technical-boundary-type | 오류0, parent0 | `6ea1c3dbc41af6a78585befab07ff86de4f7c87f2bc5b4450b2e4ea28a987028` |
| technical-boundary-lint | 오류/경고0, parent0 | `5a0b9ca5ab0dbe824b5f6f6ff97a3043c29d917d7c73838f2274d6a8e7d48e3b` |

FE type는16:30:07–16:30:08UTC, 최종unit은16:34:19–16:34:20UTC, lint는16:34:18–16:34:19UTC의 로그 생성/최종 기록 시각이다. 첫unit/type도 통과했으나 lint가 새 시험의 변수명 module을 Next 규칙으로 거절해 parent78이었다. 시험 변수만 m으로 바꾼 뒤 영향 unit/lint를 재검사했고 type 입력 bytes는 그대로다. 기존 guard 거부를 우회하거나 기대값을 느슨하게 바꾸지 않았다. FE 최종 unit workers/exitRecords2/2, type/lint1/1, partial/diagnosticFailure0·예상밖 violation0·각 소유root 제거다. tooling expected negatives는 일반 보호 회귀의 거절이며 native:not-observed를 전체 원본 읽기 부재 증거로 확대하지 않는다.

AI28·고정cross-root9 입력은 현재 source/pin과 대조했다. 기존 Supervisor/Flow/Fundamental/agent/graph12파일 byte와 AIClient의 기존 메서드(의도적으로 닫은 analyze_technical 제외) AST·config의 두 상수 외 AST/값이 보존됐다. 이것은 source-only audit이며 기존 전체 runtime regression 수가 아니다. Frontend guard/Backend bootstrap·package/lock은 base와 byte 동일하다. 마지막 제품/시험 입력 변경 뒤 위 영향 검사가 이뤄졌고 이후에는 문서/인계 자료만 갱신했다.

이제 정확27파일 source와 검사/이식 증거를 동결한다. 독립 최종 검토와 CF028/CF029 정상 merge 순서·최신 base에서 caller/CI 영향 재검증은 조율 측이 맡는다. 아직 Git stage/commit/push/PR/CI/merge는 실행하지 않았다.


## 게시 전 독립 검토

조율 측의 최종 읽기 검토가 동결27파일·AI28/고정9 pin·원본WIP15·branch/HEAD/빈index·증거hash를 대조하고 미해결 finding 없이 통과했다. 이는 독립 재실행이 아니며 위 self/unit 수를 더하지 않는다. 제품/시험은 그대로 두고 이 완료 기록만 추가해 Draft PR을 준비한다. 이후 CF028/CF029 merge와 shared caller/tooling 정합화·영향 보호 검사·최신 exact-head/Ready CI 및 독립 delta 검토를 별도로 거친다. 현재 검토를 미래 integration 승인으로 확대하지 않는다.


## CF028 정상 병합 후 통합 검증

CF028 PR33의 merge `db2fc82df1f1c0177d543fb7f7be2c60a107df0d`를 정상 merge 방식으로 통합했다. caller와 tooling 두 충돌만 해결했으며, core·verification·Technical의 정확한 세 sibling 및 유일한 기존 dependency root를 보존한다. 두 작업의 회귀를 모두 유지하고 실제 보호 invocation의 유한 root assertion에도 Technical을 추가했다. 임의 prefix·환경/CLI 경로 입력과 fallback은 추가하지 않았다.

첫 unit 시도는 미해결 index stage 때문에 worker 0의 `unsupported index source`로 중단됐다. 임시 root 제거와 위반 0을 확인한 뒤 두 충돌 파일을 정상 stage 처리했다. 같은 보호 입구의 재검사에서는 unit 67개(preview 15 + tooling 52), type 오류 0, lint 오류·경고 0, 각각 parent exit 0과 소유 root 제거를 확인했다. 예상 보호 거절 16개와 예상 밖 위반 0, diagnostic failure 0을 구분한다. guard 및 package/lock은 불변이다.

Backend·AI·기존 AI28/고정9 입력과 CI는 기존 동결 bytes와 같으므로 Backend 검사를 반복하지 않았다. CF028의 나머지 제품·fixture·문서는 병합된 develop bytes를 그대로 사용했다. CF029 미게시 변경은 입력이나 게시 대상이 아니며 Technical의 선행 조건이 아니다. 이전 문단의 CF029 병합 대기는 당시 계획 이력이다. 이번 통합의 독립 delta 검토 및 새 exact-head/Ready CI는 별도로 확인한다. 실제 engine/provider·owner 저장·공개 Technical·차트 rendering 미검증은 그대로다.

독립 delta 읽기 검토는 미해결 finding 없이 완료됐다. 두 충돌 파일의 실제 hash와 staged bytes, 비충돌 CF028 6파일의 develop 일치, Backend/AI 17개 및 AI28·고정9 pin 불변과 unit67/type0/lint0·정리 로그를 대조했다. 독립 재실행 수로 집계하지 않는다. 새 commit의 원격 exact-head CI와 Ready CI는 게시 뒤 확인한다.
