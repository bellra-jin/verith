# CF-031 Technical read boundary

Prepared on `feat/technical-read-boundary` from reviewed CF021 head
`b15a1f528f31c0f9ec2c966c0996b68f4d192316`. This is a pure, non-persistent
composition/restoration and chart projection change. The initial source consists
of exactly the eleven paths below. No execution profile is registered.

## Behavior and trust limits

`TechnicalReadBinding` retains only frozen contexts, a frozen CF021 binding and
canonical caller text. It compares the caller text's UTF-8 SHA (L) independently
from CF021's existing semantic request fingerprint (B). Equality is permitted;
neither digest proves ledger provenance or business semantics. Shared analysis,
admission, attempt, owner, as-of and deadline fields must agree. Owner UUID equality
does not establish authentication or SQL ownership.

Composition reuses `TechnicalBoundaryAdapter.validate_and_freeze`, or validates an
existing boundary frozen result with its `chart_preview`. It explicitly freezes
the same input/result JSON and schemas under the caller context. Restoration first
validates canonical text, strict JSON, text hashes and frozen binding hash, then
compares the independent expected caller context and exact boundary request/report.
It reconstructs the boundary-context frozen object and calls the existing
`chart_preview`, including existing response and schema checks. No second Backend
chart validator, generated IDs or generated timestamps are introduced. Returned
preview dictionaries are detached values.

`decodeTechnicalBoundary` accepts parsed unknown response data plus a separately
supplied expected request and request digest. It checks exact envelope/request
shapes and IDs, full question/stock/as-of/conditions snapshot, supplied digest
format/equality, coverage, and chart fields before calling `boundaryPreview`.
Non-chart result internals remain opaque JSON: this is not a complete
`TechnicalAgentOutput` validator. A valid safe error envelope returns a typed
`kind: error`; invalid packets throw a fixed safe error. Failures do not become
empty successful charts.

Frontend digest equality is consistency with independent expectations, not Python
canonical hashing or cryptographic verification. Parsed objects cannot reveal raw
duplicate keys or recover precision lost during JSON parsing. The decoder rejects
non-finite numbers, string/bool prices and unsafe integers. Within allowed JS
numbers it preserves zero, negative zero, null, annotation metadata and numeric
values without rounding or coercion. Structural equality uses `Object.is` before
the existing preview's JSON-based comparison. Backend retains its existing Python
numeric representation and strict raw-text checks, including larger integers;
the Frontend's narrower numeric limit is explicit.

`cutoff_validation: unverified` and unreported timestamps remain unchanged. Both
implementations require independently supplied expectations. Replacing all trusted
expectations is outside this consistency boundary.

## Exact source paths

1. `backend/src/modules/technical/application/boundary_restore.py`
2. `backend/tests/unit/test_cf031_technical_boundary_restore.py`
3. `backend/scripts/check_safe.py`
4. `backend/tests/safe_checks/test_entry.py`
5. `frontend/src/features/technical/lib/strict-boundary-read.ts`
6. `frontend/tests/unit/technical/boundary-read.test.mjs`
7. `frontend/tests/fixtures/cf031-technical-boundary-read.json`
8. `frontend/scripts/check-local-ports.mjs`
9. `frontend/tests/tooling/safe-checks.test.mjs`
10. `.github/workflows/pr-ci.yml`
11. `docs/work/CF-031-technical-read-boundary.md`

Existing AI28/fixed9 paths and hashes, CF021 helpers/models/tests/fixture, worker,
bootstrap, guards, package and lock files are unchanged. Backend adds its separate
single-file `CF031_TESTS` selection, exact helper/fixture pins and one fixture path
to the focused Frontend copy filter. Frontend adds exact read modes/inputs and the
single `verith-technical-read-boundary/frontend` sibling alias. Existing metadata,
dependency, realpath/uid/mode, package/lock, source hash and pre/post provenance
checks remain in force. CI retains the existing macos-15/runtime setup and adds
only the Backend protected self/unit steps.

## Direct local verification, 2026-11-10 UTC

All executions used formal escalation approval and the existing protected public
entry points. No raw pytest/node-test, installation, full build, HTTP, provider,
SDK, DB or browser action was run.

| Protected mode | Result |
|---|---|
| Backend `technical-read-self` | 3 passed, exit 0 |
| Backend `technical-read-unit` | One selected file, collected/passed 47, guard violations 0, exit 0 |
| Frontend `technical-read-unit` | Decoder 46 + tooling 52 passed, no skips/failures, exit 0 |
| Frontend `technical-read-type` | exit 0 |
| Frontend `technical-read-lint` | exit 0, no lint findings |

Backend launch: `env -i LANG=en_US.UTF-8 TZ=UTC <worktree>/backend/.venv/bin/python
-I -S -B <worktree>/backend/scripts/check_safe.py <mode>`.
Frontend launch: `env -i LANG=en_US.UTF-8 TZ=UTC OPENSSL_CONF=/dev/null
/opt/homebrew/bin/node <worktree>/frontend/scripts/check-local-ports.mjs <mode>`.
Existing installed dependencies were reused via ignored dependency symlinks; no
package/lock/dependency contents were changed.

The first Frontend unit run exposed four test harness VM realm transfer failures;
the second exposed a missing -0 injection into the annotation RSI value consumed
by the existing chart helper. The initial lint run rejected a test variable named
`module`. These were test preparation/naming errors and were corrected without
weakening product validation or guards. Final unit was rerun after the lint fix.

Every invocation confirmed removal of its own temporary root. Final Frontend unit
reported two workers/two exit records, partial workers 0, unexpected violations 0,
diagnostic failures 0, and 16 expected negative guard probes. Type/lint reported
one worker/one exit record and no denials/violations. These observations cover
instrumented JS filesystem journals; native activity is not fully observed.
Parent public package reads were separately counted as approved source-copy and
pre/post validation. The final local unit log is a local handoff artifact, not
part of the published source.

## Handoff and remaining acceptance

No stage, commit, push or PR was performed during implementation. Independent
final source review and normal integration with the latest allowed develop after
CF021 are pending. The overlapping caller/tooling/CI paths must be reconciled by
normal merge; the latest existing exact sibling roots must be preserved alongside
the one new read-boundary sibling. Final exact-head/Ready CI must be checked by the
coordinator after integration. Local results above are for this b15a1f5-based
uncommitted implementation and do not certify the later integrated head.

SQL/model/migration/reservation, actual owner persistence/authentication, execution
profiles, HTTP/BFF/UI lifecycle, actual engines/providers, keys/flags/environment,
and rendered chart acceptance remain outside this work. Future execution still
requires its own deadline/auth/revocation and usage acceptance; this pure helper
does not resolve those concerns.

Suggested commit: `feat(technical): add pure caller restoration and strict read projection`.
Suggested PR title: `Add pure Technical caller restore and chart read boundary`.
Suggested PR body: "Bind validated CF021 frozen results to independent caller
contexts and restore them through the existing boundary validator. Decode unknown
Frontend envelopes with exact request/digest consistency and lossless chart
projection. Focused protected Backend self/unit and Frontend unit/type/lint pass;
actual authentication, persistence, engine execution and chart rendering are
outside scope."

## Independent frozen-source review

An independent read-only review of the eleven frozen files completed with no
unresolved actionable findings. It checked the helper/decoder trust boundaries,
reuse of the existing validators, shared adversarial cases, existing AI28/fixed9
pins and guard/package/lock preservation, the exact pure selections and existing
20 plus two new CI steps. It read the final Frontend 46+52 log; it did not rerun
tests. Backend self/unit and Frontend type/lint results are also retained as
explicit original-tool-output extraction artifacts, not separate original stdout
hashes or new executions. The implementation source remained frozen throughout
review. Latest-develop integration and its delta checks remain separate.
