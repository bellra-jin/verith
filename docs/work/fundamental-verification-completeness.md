# Fundamental verification metadata completeness

## Scope and contract
AI-only correction; no new wire columns, public DTO enum or Backend/frontend edits. Normal verify_node emits all four check booleans plus outcome. Missing/partial external or legacy metadata was previously promoted by two consumers.

- HTML badge now requires existing outcome `passed` AND all four fields exactly True. Missing keys, null, integer 1 and truthy strings are not observations.
- ERD projection now writes its three existing check booleans with exact-True semantics (missing/malformed becomes False). It does not add guard_passed to the DB-shaped object.
- Missing/blank/non-string outcome becomes the existing `guarded` value. An explicitly passed outcome with any missing/non-boolean check is also guarded. Existing complete typed metadata is preserved, including a False check with an independently assigned stability outcome; the HTML badge still requires all True. This change does not redefine every historical outcome as a conjunction of checks.
- False means no demonstrated pass, not proof a check ran and failed. Existing insufficient_data outcome is preserved. Source metadata is not mutated or rewritten; nested original meta remains original observation, while the ERD projection is conservative.

## Consumer inspection
`api/payload.py` produces existing Boolean columns and String outcome. Backend `fundamental/application/report_service.py` projects those values without a passed default; DB `fundamental/report_verification.py` uses Boolean/String, not an enum. Frontend `fundamental-report-view.tsx` does not use these fields for a passed badge, and retains verdict/data_status-based insufficient display. No claim all external clients have been executed.

## Validation
Two test-first cases failed before implementation. Guarded calculator suite 115/115 and insufficient route suite 14/14 passed using the approved temporary lock-pinned venv. Coverage includes every missing check, malformed truthy values, missing/invalid outcome, full normal metadata, guarded/insufficient preservation, exact existing ERD field set and rendered badge behavior. No live DB/provider/app startup/writer; saved historical JSON/HTML not rewritten. Full Backend storage/UI roundtrip remains unverified.

Commands:
`& "$env:TEMP\verith-sdk-boundary-20261115\Scripts\python.exe" -I ai/tests/fundamental/test_calculators_isolated.py`
`& "$env:TEMP\verith-sdk-boundary-20261115\Scripts\python.exe" -I ai/tests/fundamental/test_accounting_basis_isolated.py`
