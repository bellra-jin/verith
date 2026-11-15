# CF060 Fundamental execution admission limits

Base: develop `e2ecca4956bd4e11698309506d3ae40a0710d944` (PR85).
Worktree: `verith-fundamental-admission-limits`; branch: `feat/fundamental-admission-limits`.

The native Fundamental service now always supplies count-only admission control to the existing coordinator. Two raw explicit positive limits are required for new owner/key admission. The winning INSERT, actual connection READ COMMITTED check, fixed global transaction try-lock and subsequent all-state KST COUNT share the admission transaction. Self-included counts may equal a limit; excess or busy rolls the INSERT back. Only the acknowledged original winner dispatches. Existing replay, result_ready publication, owner reads and tombstones retain their contracts.

No new schema/table/migration/flag, generic executor or financial ledger. Common coordinator/profile/adapter/writer/read, AI and Frontend are unchanged. Control observe is a no-op, not usage or financial settlement. New missing-stock eligibility is explicitly FEATURE_UNAVAILABLE. Worker settings equality is an operational prerequisite rather than a durable DB guarantee; changing policy never clears old run counts. Global try-lock contention may reject below-cap admissions without automatic retry.

## Verification

Unit77 and self3 passed with guard0. The existing owned-PG mode passed 15 groups (10 existing + 5 new CF060 groups), with 26 Fundamental and 3 Flow fake dispatches. It observed 34 distinct actual SQL admission connections, confirmed separate lock/COUNT order, cap1 races for users and service, busy/repeatable-read/cancellation rollback, ACK-loss count preservation, absent-policy result_ready recovery, owner/other-user boundaries and unchanged Flow accounting. Native inspection confirmed the exact owned DB container was absent after cleanup. Remote exact-head CI remains pending publication. Initial unit failure was a synthetic principal fixture omission; initial self failure was a list/set comparison in the newly added test. Both were corrected without changing existing product protection. No tests were skipped or removed.

The old CF015 owned checker had a c150-only head assertion, while current develop is c610. The verifier now tests the actual current head; the original frozen c150 populated-downgrade guard is still executed on an attested owned connection in its rollback-only context, and whole-head populated downgrade refusal is separately retained. No revision stamp/reset or old migration change is used. The old two-engine publication race admits serially before racing results, preserving that test while acknowledging the new fail-fast admission-lock contract.

The old policy-table/flag draft was not connected or executed and was removed before verification. The final contract uses existing run counts only. Verification uses only the existing protected fundamental modes and the existing Verith owned-PG proof/receipt/cleanup path, real SQL A/B sessions and ASGI fake engines. It is not actual Google, financial calculation/provider acceptance, or production activation.

Original WIP/other workspaces, consumed actual runs and the $1.30 conservative hold remain untouched. PR61 remains HOLD. New OpenAI/KIS/DART requests, key/environment reads and package installation: 0. Before publication/merge, compare latest develop, Junyoung's open PRs/dependencies, final manifest and exact-head CI. No GPT/coauthor signature.
