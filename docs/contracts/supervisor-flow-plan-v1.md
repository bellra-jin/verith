# Supervisor Flow plan v1

The current product goal and sequence are defined once in the external overall operating document §4.1. CF-020 connects only natural-language preparation to existing Flow execution. Technical/combined perspectives, Fundamental/Macro/Industry, multi-turn and News execution are not implemented here. Dedicated prior screens are not the final UX.

## Boundaries

Authenticated `POST /api/flow/plans` through same-origin `POST /api/private/flow/plans` accepts exact `query`, optional paired `selected_ticker`/`candidate_ref`. Original UTF-8 query (1–300 characters, nonblank, no NUL) is preserved; identity/views/model/URL/as_of/execution keys cannot be supplied. Request limit is4096 bytes, public result16384 bytes. Unsupported methods/subpaths/query strings stay closed. No run, attempt, reservation, secret or durable plan is created.

AI `POST /internal/supervisor/plan` uses `supervisor.flow-plan.v1` and policy `supervisor.flow-only.1`. Backend generates request/trace UUIDs and the query SHA. Start returns one typed resolve_stock request or unsupported/needs_clarification only. Backend invokes the existing canonical StockResolverService once with the original query, then at most one continuation; it does not duplicate AI intent classification. Continuation independently rechecks intent/views and canonical fields. Backend verifies the exact query hash, IDs, policy, views, canonical code/name/market and selected result. Recursive tools or start-ready without canonical resolution are invalid.

No automatic retry, LLM/rewrite/fallback/agent imports or executions occur in preparation. Body/auth/initial rollback/resolve/HTTP/final auth share the10-second Backend deadline; individual AI/resolve budgets are3 seconds and BFF is12 seconds. Initial auth transaction is rolled back before waiting for AI. Final publication uses a new transaction and real SQL session/user revalidation.

AI service auth is the existing matching single X-Flow-Service-Token, printable ASCII minimum32 bytes, constant-time checked after default-off gate and before body/planning dependencies. Only configured server origin and fixed path are used. Redirects and environment proxies are disabled. Internal request/result limit32768 bytes is enforced during decoded streaming; identity encoding is requested and other encodings are rejected. Local invalid input422, config/service/auth-upstream503, deadline504 and explicit invalid result502 remain distinct. Query, token, upstream body and raw errors are never exposed.

## Canonical and selection

Canonical resolved stock has exact ASCII6-digit stock_code, nonblank/control-free1–256-character stock_name and nullable KOSPI/KOSDAQ/KONEX market. Ambiguous has no stock and zero to ten distinct candidate codes with canonical fields and match_type; zero or one candidate is not automatic resolution. not_found is distinct from errors/ambiguous unknown_identifier. Numeric matching uses ASCII digits with numeric boundaries; name/alias matching otherwise remains the existing resolver algorithm.

candidate_ref is lowercase SHA-256 of canonical JSON `{version,policy_version,query,resolution}` with candidate codes sorted. It includes returned status/reason/code/name/market/match_type, not reflected raw matched_text. It is not a secret, signature, TTL ticket or execution permission. Selection re-runs start/fresh resolver. Malformed ref or out-of-current-set selection is422. A valid-format ref mismatch for a valid member always returns selection_stale; forged versus stale cannot be distinguished. Only the returned maximum ten candidates are covered.

Public statuses: ready_for_confirmation, needs_stock_selection, selection_stale, not_found, needs_clarification, unsupported. Data contains version/policy/query hash/views/status/reason/resolution/ref within the existing request_id/data/error envelope. No analysis completion state appears in a plan.

## Execution and UI

Active /research AnalysisRequest uses the new preparation component only for a fresh request. Owner/session is checked before each plan/selection and again before adoption. Question/selection/owner/URL/generation/visibility/cancel/unmount invalidates plan/consent and aborts late responses. A synchronous lock rejects double clicks. Only ready + exactly Flow can supply canonical ticker/original query to the existing freshPending after explicit analysis consent.

Existing pending/known IDs bypass planner/resolver and preserve their original ticker/question/as_of/key and fingerprint. GET-only recovery never posts, plans, resolves or publishes. Explicit same-key result_ready POST can publish only the durable snapshot. Existing usage coordinator, claim ACK, owner/fence/tombstone, storage schema and analysis helper are unchanged. Plan-time name is only guidance; new admission rechecks the current master and fixes its own snapshot, while existing keys retain their original snapshot.

## Verification levels

See [CF-020 work record](../work/CF-020-supervisor-flow-orchestration.md). Fixed pure/ASGI tests, owned-PG integration, real production React with synthetic HTTP, Next SSR/BFF and real providers are separate evidence. CI adds only planning self/unit to the existing ten protected Backend steps. Latest PR head and a new Ready CI success plus independent review are required before a normal merge. No operating usage activation or real provider/Google credentials are included.
