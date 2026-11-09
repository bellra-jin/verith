# CF-017 Flow 공급자 오류 분류

- 정본: `지시서/CF-017_Flow_공급자_오류_분류와_실연동_승인_경계.md`, v1.0, SHA-256 `58bb9d3d99202e3e3a2de5cc37c80ddeb6a02e2cbe9a59857229e9d903e2378a`.
- 기준 develop: `20f36233ab92ace6df23e78b39fe146a179c69f2`; 작업 branch: `fix/flow-provider-errors`. 미커밋 구현이며 사용자 Git 인계 대상이다.
- 변경은 정본13경로다. 공동 coordinator·DB·Frontend·token cache·shared deadline·schema/spec/prompt·계산·worker/bootstrap과 기존 OS/FS/network 보호는 변경하지 않았다.

## 구현

Flow HTTP의 body 검증과 실행 예외 경계를 분리했다. 일반 provider/engine `ValueError`는 입력422가 아닌503이다. 실행 후 결과 추출·형태·request binding·canonical/크기 위반만 고정 `ResultContractError`로502 처리한다. sync worker의 실제 종료 전 slot 반환 금지와 기존 기한은 유지한다.

KIS 발급/조회 timeout은 고정 deadline 오류로 변환한다. issuer의 timeout 여부만 호출별 boolean으로 보존해 순수 token cache가 예외를 감싼 뒤에도 `_get_token`에서 분류를 복원한다. 파일/cache 오류는 timeout으로 바꾸지 않는다. HTTP200 업무 실패·빈 결과·기준일 이전 결과 없음과 설정 누락을 포함한 모든 명시적 KisError11곳은 고정 문구다. rt_cd/msg_cd/msg1·ticker/date를 오류에 넣지 않는다. 원문 provider 오류를 공개하지 않고 기존 EGW00201 0.6초/1회 재시도만 유지한다. explain은 SDK `APITimeoutError`만 deadline으로 구분하며 모델·prompt·재생성/출력 상한은 보존한다.

Backend는 `analyze_flow`만 수정했다. 잘못된 URL parser/port·HTTPX 자체 URL 구문·token 및 내부401/403은 unavailable, bounded strict JSON502의 정확한 contract code만 contract 오류로 분류한다. 200 오류/2MiB 상한·125초 전체 대기·no proxy/redirect/retry는 유지한다. 다른 agent 메서드는 불변이다.

## 검증 상태

2026-11-09 보호 self **2/2**, 최종 unit **77/77**, 두 명령 **exit0**이다. unit은 **Selected files=1 / collected=77 / guard_violations=0**이며 각 소유 임시 root 제거를 확인했다. 최초 self2/2·unit70/70 이후 독립 검토의 두 보완과 KIS pin 변경에 영향받은 self/unit만 다시 실행했다. 고정12 AI 입력과 단일 unit 파일을 사용하는 기존 보호 입구의 `flow-errors-self`/`flow-errors-unit`만 실행했다. 기존 source map은 변경한 같은 경로 pin만 갱신하며 파일 집합과 guard는 보존했다. workflow는 기존 runtime/단계를 유지하고 새 두 고정 단계만 추가했다.

첫 unit은47/70 통과·23실패·exit78·guard0이었다. 합성 fixture가 UTC 시각을 `Z`로 fingerprint에 넣어 DTO의 `+00:00` 정규화와 달랐으며 engine 이전422였다. fixture만 수정한 영향 unit 회차가70/70으로 통과했다. 최초 로그는 보존했으며 이 fixture 수정에는 unit만 재검증했다. 기존 suite는 반복하지 않았다.

독립 검토의 KIS 업무 실패 비노출·HTTPX InvalidURL 경계를 보완했다. 새 unit 첫 시도는 추가 사례의 `kind` 매개변수 누락으로 수집0·exit78·guard0이었다. 테스트 signature만 정정한 다음 unit이77/77·exit0으로 통과했다. 이 실패와 소유 임시 root 정리 로그도 보존했다. HTTP200 업무 실패/빈 결과에 secret sentinel을 넣고 추출한 실제 fetch 함수→HTTP 응답/예외/log 비노출, 명시 KisError11개의 고정 literal을 검사한다. DataFrame 변환은 실행하지 않았다. 잘못된 IPv4와 민감 문자열 URL은 전송0회·고정 unavailable 예외를 확인했다.

검사는 real copied Flow router + ASGITransport, Backend MockTransport, AST로 추출한 실제 KIS/explain 함수 + 합성 client/context/SDK binding, 순수 cache + 소유 tmp_path, 가짜 시간과 실제 sync slot 수명을 대상으로 한다. synthetic profile/session의 coordinator 상태 매핑은 실제 인증/owner/DB 검증이 아니다. AST explain 검사는 실제 SDK propagation·prompt 파일·dotenv 실행 증거가 아니다.

위 검사는 개발 측이 직접 실행한 합성 집중 검사다. 이후 실제 연동의 별도 실행·증거 검토 측이 전달한 결과는 아래에 구분한다. 개발 측은 실제 공급자·Google·DB·브라우저 실행이나 기존 전체 Backend/Frontend/PG suite를 다시 수행하지 않았다. 원격 CI는 사용자 PR 게시 이후 최신 head 및 Ready 이벤트 결과를 별도 확인해야 하며 현재 미실행이다.

## 별도 실제 실행 결과

다음은 실행 담당의 관측과 독립 artifact 대조 결과를 전달받아 반영한 것이며, 개발 측의 실제 환경 독립 재실행은 아니다. 고정된 제품 source로 삼성전자005930 단일 시나리오를 수행했다.

| 회차 | 실제 호출·사용량 | 결과 |
|---|---|---|
| 독립 공급자 스모크 | KIS token1/data2, OpenAI1회, input1914/output320, 추정 $0.0028755 | Gate3개 모두 통과 |
| 브라우저 연결 | KIS token1/data2, OpenAI1회, input1914/output256, 추정 $0.0025875 | 실제 로그인·요청·저장·같은 결과 재조회·UI 삭제·404 확인 |

누적 OpenAI2회, 사용량 기준 추정 **$0.005463**으로 검증 한도3회/$0.10 이내다. 실제 청구서를 확인한 금액이 아니며 제품 전체의 총비용 hard cap을 입증하지 않는다.

실제 Google 로그인은 시크릿 창의 코드 교환·OIDC 검증과 격리 DB의 계정/identity/session 저장, 로그인된 보관함 UI로 확인했다. 첫 브라우저 분석은 임시 harness가 bytes 형태 localhost를 처리하지 못해 AI 연결 전에 중단됐다. graph 미진입·KIS/OpenAI 추가 호출0·추가 비용0을 확인했고 해당 테스트 자료와 자원을 정리했다. 제품 변경 없이 harness의 좁은 ASCII 정규화만 보완했다. 새 환경에서는 자격 사용 전에 실제 HTTPX localhost9200 health200을 확인했다.

브라우저 분석은 ‘수급·자금흐름 리포트 / 삼성전자005930’, 확정일2026-11-06, 입력·데이터·해석 검증 통과와 gpt-5.4-mini 표시를 확인했다. UI stored와 동일 보고서 GET·재조회 내용 일치, 격리 DB report1/run1을 확인했다. 이후 실제 UI 삭제로 목록0·DB report0, 삭제된 정확 보고서 URL의404와 본문 미노출을 확인했다.

테스트 계정/identity/session·분석 요청 기록을 테스트 PG tmpfs와 함께 정리했다. AI·Backend·PG·namespace owner의 정확 자원 제거/부재와 localhost3200/8200/9200 listener0을 확인한 후속 영수증이 앞선 cleanup pending을 해소했다. 저장·삭제·usage·정리 증거 해시는 독립 artifact 대조와 일치했다. 원본 DB·기존 리포트·일반 브라우저 프로필·다른 프로젝트는 보존했다. 비밀값·개인 계정값·운영 식별자·원시 증거는 공유 문서에 포함하지 않는다.

남은 한계는 다음과 같다.

- 원분석 요청의 `deleted` enum을 UI에서 직접 확인하지 못했다. 실제 보고서 삭제·빈 목록·404 확인과 구분한다.
- 현재 SessionControls의 ‘이 결과 삭제’는 별도 확인창 없이 즉시 DELETE한다. 확인한 계약에서 확인창 필수 조항은 찾지 못했으므로 검증 실패로 단정하지 않고 UX 개선 후보로 남긴다. 이번에 UI를 수정하지 않았다.
- 단일 종목·격리 환경의 성공이며 모든 종목, 원천 수치/해석 품질 전반, 장애의 실제 SDK 전파, 운영 배포 전체를 검증한 것은 아니다. 원격 PR/최신 head·Ready CI/병합도 아직 남아 있다.

## 실행 준비와 인계

실제 연동의 공식 수신처·입력/비용 제한·환경/인증/정리는 [실행 준비](../flow-live-readiness.md#공급자-실행-전-남은-경계-cf-017)에 구분했다. 초기 Docker socket metadata 조회의 OS 차단은 당시 이력으로 보존한다. 개발 측이 같은 동작을 재시도하거나 다른 socket·권한 확대를 하지 않았다는 사실과 이후 별도 실행 환경에서 완료된 실제 검증을 구분한다. 후속 운영 실행 조건과 제품의 비용 hard cap이 자동으로 충족된 것으로 확대하지 않는다.

사용자가 최종 manifest/NUL pathspec과 변경 내용을 확인한 뒤 stage/commit/push/Draft PR을 수행한다. 원격 CI의 기존 Backend quality/fundamental 검사와 신규 Flow 오류 집중 검사를 구분하고 최신 head/Ready CI 성공 전 병합하지 않는다. agent는 git add/commit/push/PR/Ready/merge를 수행하지 않았다. 마지막으로 수행한 fetch 시점의 HEAD/origin develop은 기준 커밋과 일치했고 worktree1·staged0·범위 밖 변경0이다. 독립 최종 source/로그 검토는 추가 blocking 결함 없이 수용됐다. source13개·로그6개 hash, self2/unit77·guard0·소유 root 정리, AI pin 집합4/14/14/12와 literal NUL pathspec·staged0·base/branch를 읽기 대조한 결과이며 독립 runtime 재실행은 아니다. 이후 별도 실제 검증과 정리 결과는 위 전달 증거로 보완됐다. 운영 전반과 실제 장애 SDK 전파는 별도이며 사용자 PR/최신 head·Ready CI 확인이 남아 있다.

검사 로그와 실제 실행 증거는 각 기존 비공개 checkpoint에 보존한다. final source manifest·literal NUL pathspec·PR 본문·사용자 명령은 별도 로컬 인계 산출물이며 공유 문서에 임시 경로를 넣지 않는다. source hash는 문서 바깥 manifest가 문서 자체까지 포함해 계산하므로 자기참조 hash를 기록하지 않는다.

<!-- CF017_PR_BODY_START -->
## 변경

Flow 내부 오류를 입력422·공급자/서비스503·deadline504·명시적 결과 계약502로 구분합니다. KIS token cache wrapper 경유 timeout과 SDK timeout을 보존하고 Backend의 잘못된 service 설정/401·403/정확한502 code 분류를 수정합니다. 기존 coordinator/저장·계산·API 계약과 보호는 유지합니다.

## 검증

- 기존 보호 입구: 신규 focused self2/2, 단일 unit77/77, guard0, exit0, 소유 임시 root 정리. 첫 unit fixture 실패와 수정 후 결과는 작업 기록에 구분했습니다.
- ASGI/MockTransport·AST 합성 binding과 실제 SDK/provider/graph 실행은 구분합니다.
- 별도 실행·증거 검토 결과: 실제 Google 로그인→삼성전자005930 KIS/OpenAI 분석→저장→같은 결과 재조회→UI 삭제→빈 목록/404→임시 자료·자원 정리를 확인했습니다. 개발 측의 독립 실제 환경 재실행과는 구분합니다.
- 스모크와 브라우저 합계 OpenAI2회, 사용량 기준 추정 $0.005463이며 실제 청구서 확인은 아닙니다. 첫 harness 차단은 graph/추가 공급자 호출0으로 종료했고 제품 변경 없이 해결했습니다.
- 원요청 deleted enum UI는 미확인이고 삭제 확인창은 UX 개선 후보입니다. 단일 종목 성공을 운영 환경 전체 검증으로 확대하지 않습니다. 원격 CI/PR/병합은 아직 실행하지 않았습니다.
- 독립 최종 source/로그 검토 수용: 추가 blocking 결함 없음. 독립 runtime 재실행과는 구분합니다.
- 기존 보호 workflow에 새 두 고정 단계만 추가했습니다. 최신 head와 Ready CI 성공 확인이 병합 조건입니다.

상세 기록: `docs/work/CF-017-flow-error-classification.md`.
<!-- CF017_PR_BODY_END -->
