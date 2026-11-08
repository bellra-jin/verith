# CF-015 · Fundamental owned execution

Base `07ddb9f78ccbaa1bb467c96de9e30ff18b9c8a28`, branch `feat/fundamental-owned-analysis`. Directive v1.1 SHA-256 `34c0e96d874251ce11ef256aafc387cf72cca91f25635427300a7e0d93e6f166`; exact 56 approved paths, 14 pinned AI source inputs. Source-only independent review is separate from the executions below.

The fixed Flow/Fundamental profiles share claim → confirmed commit → HTTP → fenced snapshot commit → stage/stored commit. Flow SQL/ledger and public behavior stay unchanged, including accept-UNIQUE503 vs publication-conflict409. Fundamental adds its own guarded ledger, nullable legacy owner without backfill, real principal-aware flush-only writer and snapshot-aware readers. Named report-UNIQUE alone establishes accept conflict; generic DB/ACK errors remain unresolved safely. Deleted tombstones retain IDs/hashes and remove request/input/result text.

`/fundamental` and private BFF provide strict opt-in, account/tab pending identity, GET-only refresh/recovery, own list/count/detail/delete and structured React text. Stock name is frozen at admission. Optional projection lists do not alter raw JSON. Raw UUID spelling, extra JSON, zero/null and large integers remain in the snapshot. No iframe/HTML/PDF or arbitrary source scheme runs. [Contract](../contracts/fundamental-analysis-v1.md) and [handoff](../examples/fundamental-owned-analysis.md).

## Executed validation

| Check | Final result |
|---|---|
| Existing protected Backend entry `fundamental-self` | 2/2, exit0, owned root removed |
| Same entry `fundamental-unit` | one collected file, 35/35, guard0, exit0, owned root removed |
| Existing Frontend entry `fundamental-unit` | 3 files, 6+9+3=18/18, exit0, instrumented violations0, owned root removed |
| `fundamental-type` / `fundamental-lint` | changed fixed targets, both exit0, errors0/warnings0 |
| DB-only `--verify-fundamental-analysis-db` | final exit0; actual isolated PG, real issued A/B sessions + ASGI HTTP client/AI router; no provider calls |

PG covered migration exact DDL injection rollback, legacy NULL preservation and empty downgrade/reupgrade; strict input/auth/CSRF; original JSON/owner list/count/detail; key races; claim/snapshot/publication ACK loss and post-flush rollback; engine error vs contract error; concurrent report-ID and deleted-ID refusal; actual root/partial-index publication conflicts; stored DELETE/replay lock crossing in both orders; session revocation; scrubbed tombstones; fixed Flow publication/replay/collision/deletion; new FK/NOT NULL/UNIQUE/CHECK and immutable-trigger refusals; exact nonempty downgrade refusal. Ten groups passed, Fundamental 21 grants/21 dispatches and Flow3/3 (each exactly1), HTTP refusals40; private-file/external-network/external-HTTP/dotenv denials0.

All three test CIDs were removed by their runner and independently confirmed absent with exact resource-label count0. No existing resource cleanup or helper/ownership-policy change. Official cached images remain. OS guard evidence and instrumented JS filesystem counters are distinct; native dispatch observation is not claimed.

## Failures and focused corrections

- First Backend unit31/33: OpenAPI projection exposed missing preserved legacy operation descriptions; unique test lacked an actual matching principal. Restored descriptions, corrected principal, and asserted injected accept/publish boundaries are reached. Unit32/33 then33/33; final34/34 and35/35 add closed-route/raw-limit regressions and fixed Flow-profile assertions. Old schema/payload digests remain unchanged; no blanket exclusions/hash replacement.
- First FE lint failed on new refs/effect initialization and test variable name; corrected without disabling lint. Final targeted lint/type and focused units passed.
- PG1: ownership/migration/rollback passed; closed HTML route was misclassified422 instead of closed403. Exact new route classification fixed and unit-tested. No analysis completion claim for this round.
- PG2: eight Fundamental groups passed; final Flow fixture reused a report UUID already claimed by the old ledger but expected publication409. Existing Flow accept error503 was preserved; a separate legacy-root fixture now checks publication409. No Flow guard/SQL change. Checker Events reset between scenarios.
- PG3: all ten groups passed; final code/runner/checker matches the successful execution. A later added raw4096/4097/chunk/UTF8/header unit changed only test bytes and passed. No unrelated suite repeated.

## Limits and CI

Actual providers/keys, real financial graph/calculations/data quality, historical analysis, Google login, production DB, TCP integration and browser/React clicks were not executed. UI lifecycle evidence is helper/VM/source assertions. Request context is not a source-financial snapshot; absent source periods stay unknown. Worker timeout/cancel tests demonstrate slot lifetime for controlled injected work, not provider cancellation or billing cessation.

Existing successful macos-15 runtime provisioning and all source/OS/FS/network/metadata protections are retained byte-for-byte; CI appends fixed `fundamental-self` and `fundamental-unit`. New head/Ready CI status is reported on the PR and in the final handoff; local success alone does not permit merge. No private credentials, receipts or conversation history enter this commit.

<!-- CF015_PR_BODY_START -->
Fundamental now connects authenticated requests to one fixed shared coordinator, service-authenticated AI HTTP, immutable result snapshots and atomic owner-aware publication. `/fundamental` exposes explicit requests, GET-only recovery and own list/detail/individual deletion; raw HTML and public save/bulk delete remain closed.

Flow keeps its existing ledger, claim/ACK/fence, snapshot and conflict/deletion semantics. Financial calculations/prompts/data selection remain unchanged. The new request-context snapshot does not certify financial source data or historical analysis.

Validation:
- Protected focused self 2/2, single-file unit 35/35, guard violations 0.
- Frontend focused unit 18/18; changed type and targeted lint exit 0; owned roots removed.
- Real owned PostgreSQL: 10 groups, Fundamental 21 grants/21 dispatches, Flow 3/3, 40 HTTP refusals plus SQL constraint/trigger checks; forbidden accesses 0. All three disposable CIDs independently confirmed absent, resource-label residue 0.
- First PG stopped on closed HTML route classification; second stopped on a Flow fixture confusing existing ledger UNIQUE with publication conflict. Both histories preserved; final focused PG exit 0. No ownership/guard relaxation.
- Existing macos-15 trusted runtime/lock setup is unchanged; two fixed coordinator/Fundamental checks were appended. Latest-head PR and Ready CI must succeed before merge.

Not exercised: real financial engine/graph, providers/keys, Google login, browser/React clicks, production DB or historical/source-financial correctness. UI lifecycle evidence is helper/VM/source coverage; Backend-to-AI uses real client + ASGITransport with deterministic injected engines.
<!-- CF015_PR_BODY_END -->
