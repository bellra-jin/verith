# Supervisor Flow preparation

Current entry is authenticated `POST /internal/supervisor/plan`. It is a bounded, free, deterministic plan protocol: start returns an unsupported/clarification result or one `resolve_stock` tool request; Backend supplies a fresh canonical union to one continuation. Existing planner/interpret/policy/models/runtime are the active planning implementation.

Planning imports no agent, Technical dependency factory, Redis, trace sink, fallback, rewrite or LLM/model runtime. The router checks the existing Flow gate and exactly one matching printable service token before planning imports/body processing. Standard AI main still has unrelated agent imports; this router does not make the entire AI app import-safe.

`/internal/supervisor/analyze` and legacy `run_analysis` are closed. FlowAdapter rejects before any engine import. News is absent from the execution model/order/default adapters and its workflow import/call is removed. This does not delete News domain/data/archive or stop existing services. Remaining legacy adapter classes are not a supported planning-to-execution route.

Only explicit individual-stock supply/participant-flow intent can request canonical resolution. Other perspectives/mixed requests, generic buy/sell advice, bare stocks and market-wide flow are unsupported or require clarification; they are never silently executed as Flow. Rules are intentionally bounded and are not general natural-language understanding or multi-turn support.

Backend owns session/CSRF/Origin, canonical resolution, usage, admission/idempotency and atomic owner-aware storage. A plan/ref is not a ticket or execution grant. Confirmed Flow uses the existing authenticated analyses coordinator and usage control, never a direct adapter.

See [the plan contract](../../../docs/contracts/supervisor-flow-plan-v1.md) and [verification record](../../../docs/work/CF-020-supervisor-flow-orchestration.md). No real keys/providers, migration or service activation is performed by this implementation work.
