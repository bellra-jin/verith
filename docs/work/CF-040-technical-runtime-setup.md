# CF040 A · Technical import 안전성과 명시 초기화

CF039 완료 develop `ca8028b11d28b12377927354ec827f0e2ea7ec17`에서 전용 branch로 분리했다.
정확9경로의 [계약 추록](../contracts/technical-boundary-v1.md)과 [설정 안내](../../ai/docs/agents/technical/config.md)를 적용했다.
B의 wheel/별도 dependency site·실제 graph 실행은 설계 선행이며 이 작업의 실행 범위가 아니다.

## 제품 변경

config import의 dotenv import/로드, ancestor `.env` 탐색과 getenv를 제거했다. import 상태의 기본값은 기존 intraday False,
trace True·같은 기본 trace 경로이며 client/cache/trace 파일을 만들지 않는다. 명시 initialize_runtime이 기존 bool 파싱과
파일 탐색·override=False/환경 우선으로 세 설정을 불변 snapshot 하나에 확정한다. RLock으로 동시 caller를 직렬화하고,
완성된 snapshot은 같은 객체로 재사용한다. 실패는 부분 snapshot/client 없이 고정 오류로 닫히고 다시 읽지 않는다.

명시 KIS/OpenAI loader는 호출할 때만 공통 lazy dotenv loader를 사용한다. 인증정보 값·모델·기본값·가격·timeout/retry·
지원 정책과 기존 파일 탐색을 바꾸지 않았다. invalid bool의 경고에서 raw 값만 제거했으며 파싱/False fallback은 그대로다.
snapshot의 trace 경로와 기존 key dataclass는 repr에 비밀값을 남기지 않는다.

pipeline_steps/technical_graph/supervisor/agent가 미초기화 상태로 먼저 로드됐으면 env load 전후 검사에서 거절한다.
reload·실제 module 삭제·다른 module flag patch로 복구하지 않는다. Technical factory는 setup 뒤에 필요한 dependency를
지연 import하고 trace는 snapshot의 bool/path를 사용한다. LlmClient 타입 alias는 실제 runtime class가 없는 상태에서도
평가 가능한 문자열 forward reference다. 기존 get_* 호출/override, default_openai_client의 명시 monkeypatch 지점과
다른 Supervisor/resolver/fallback/adapters 함수는 보존했다.

기본 main/route에 setup·engine을 연결하지 않았다. dependencies에는 다른 legacy chain이 남아 있으므로 전체 module
import 안전성이나 실제 Technical 서비스 연결 완료로 확대하지 않는다. CF039 bridge/Runtime/HTTP·계산·owner 저장/usage·
Frontend·schema·패키지·worker/OS/FS/network/env guard는 변경하지 않았다.

## 직접 무키 검사

기존 clean env의 절대 Backend Python과 `-I -S -B`, 고정 technical-runtime-self/unit을 각 한 번 실행했다.
self3·단일 unit39개가 통과했고 guard 위반0·parent exit0·각 소유 임시 root 제거를 확인했다.
직접 영향인 기존 technical-boundary-self3도 통과해 새 readonly config pin과 원래 config/graph 금지 loader를 확인했다.
이미 통과한 bridge208·meaning·PG/Frontend 전체 검사는 로컬에서 반복하지 않았다.

실제 config의 collection import probe에서 getenv·dotenv import/load·환경 파일 탐색/생성 시도0을 확인했다.
명시 호출은 자기 합성 환경 mapping·dotenv/import spy만 사용했다. unset/true/false/invalid 파싱·env 우선/override=False,
명시 loader·일회/frozen/동시 동일 snapshot·실패 원자성/latch·전후 late reader 거절·setup→import→factory 순서,
trace snapshot·LLM override/deadline 전달·비밀 sentinel 비노출을 실제 함수로 확인했다.

dependencies 검사는 선택한 실제 setup/factory AST body와 안전한 type alias/선언만 실행했다. 전체 legacy module·실제
graph/provider를 import한 증거가 아니다. late reader는 자기 합성 sys.modules sentinel이며 실제 pipeline을 삭제하거나
reload한 것이 아니다. dotenv/파일/키를 실제로 읽거나 cache/trace 서비스를 생성하지 않았다.

새 mode의 AI 읽기는 config/dependencies/intraday_limits/순수 Deadline의 정확4파일과 기존 Flow pure6 origin뿐이다.
AI32 집합·기존 CF021 collector/FORBIDDEN/AST-only graph 검사와 원본 접근 금지는 보존한다. 기존 CF021의 readonly config
pin만 새 bytes로 맞추고, 새 고정 self/단일 unit과 CI 두 step을 추가했다. 새 interpreter/site·패키지 설치 권한은 없다.

## 미실행과 다음 선행

실제 `.env`/키·KIS/OpenAI/count·DB·캐시/trace·새 발급/예약·설정 활성화는 없다. 기존350m 보수 예약과 모든 소비/실행 자료는 불변이다.
실제 compiled LangGraph 계산은 미실행이다. graph runtime의 공식 wheel/platform·자기 별도 site/provenance·정확 수집 전
import closure와 tracing/provider 차단이 먼저 필요하다. 현재 Backend site 고정 입구를 다른 interpreter/raw pytest/전체 설치로 우회하지 않았다.

B의 graph35+worker7 dependency 및 source49 후보는 아직 실행 manifest·허용 목록·설치 명령이 아니다.
pandas/numpy는 그 좁은 graph closure의 필수가 아니며, 다른 AI 기능의 요구를 부정하는 말도 아니다.
기존 ScriptedLlm/DWM·실제 compiled graph 테스트를 재구현하지 않았다. A의 통과를 실제 graph·엔진 품질·owner 실행 수용으로 표현하지 않는다.

독립 최종 검토와 원격 exact-head CI·Ready PR/정상 merge 결과는 각 단계의 증거로 별도 보고한다.

독립 최종 읽기 검토에서 정확9파일·제품2파일·고정 입력·단일 unit·기존 보호 보존과 로그 범위를 대조했고, 남은 구체적 blocker는 없었다.
검토자는 추가 실행이나 Git 변경을 하지 않았다. 원격 게시 전 develop이 기준 commit과 같고 동명 branch/PR이 없음을 확인했다.
