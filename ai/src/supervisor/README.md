# Supervisor core와 Flow 준비

현재 단일 채팅의 내부 entry는 `POST /internal/supervisor/core/plan`이다. MeaningFrame/typed 조건→필요한 canonical resolve→bounded continuation→명시 범위 동의를 [core 계약](../../../docs/contracts/supervisor-core-v1.md)으로 표현한다. production meaning gateway는 unavailable이며 실제 SDK/키/env를 읽지 않는다. 이전 `/internal/supervisor/plan`의 CF020 제한 계약은 호환 경로로 보존한다.

새 core도 gate/token 선행·lazy import 경계이며 전체 AI main의 무부작용을 주장하지 않는다. 원문/부정·기간/주체 조건과 requested/capability/selected를 분리하고, 미지원 조건은 명시 동의 없이 Flow로 대체하지 않는다. 실행·usage·owner·저장/삭제는 Backend의 기존 owned Flow가 맡는다. Technical/재무/거시/News 실행이나 실제 모델 품질·전체 멀티턴은 이번 범위가 아니다.

Planning imports no agent, Technical dependency factory, Redis, trace sink, fallback, rewrite or LLM/model runtime. The router checks the existing Flow gate and exactly one matching printable service token before planning imports/body processing. Standard AI main still has unrelated agent imports; this router does not make the entire AI app import-safe.

`/internal/supervisor/analyze` and legacy `run_analysis` are closed. FlowAdapter rejects before any engine import. News is absent from the execution model/order/default adapters and its workflow import/call is removed. This does not delete News domain/data/archive or stop existing services. Remaining legacy adapter classes are not a supported planning-to-execution route.

Only explicit individual-stock supply/participant-flow intent can request canonical resolution. Other perspectives/mixed requests, generic buy/sell advice, bare stocks and market-wide flow are unsupported or require clarification; they are never silently executed as Flow. Rules are intentionally bounded and are not general natural-language understanding or multi-turn support.

Backend owns session/CSRF/Origin, canonical resolution, usage, admission/idempotency and atomic owner-aware storage. A plan/ref is not a ticket or execution grant. Confirmed Flow uses the existing authenticated analyses coordinator and usage control, never a direct adapter.

See [the plan contract](../../../docs/contracts/supervisor-flow-plan-v1.md) and [verification record](../../../docs/work/CF-020-supervisor-flow-orchestration.md). No real keys/providers, migration or service activation is performed by this implementation work.
