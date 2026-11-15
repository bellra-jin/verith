# Insufficient-input verification semantics

Scope: Fundamental AI only. No Backend/public DTO/frontend changes.

## Evidence and behavior
- `application/nodes/workflow.py`: unsupported_ticker/empty_data route collect directly to report, without verify.
- `application/nodes/report_node.py`: those responses now emit four existing check booleans False, meaning no check passed. Existing outcome=insufficient_data, original reasons, workflow=[collect,report], retryability, counts, score and verdict remain unchanged. This is not a claim that performed checks failed. Stale input verification cannot override this route.
- `api/rendering/html_builder.py::_verification_passed`: badge requires outcome=passed. Old insufficient_data records with True booleans must not earn a new rendered passed badge. Existing saved HTML is not rewritten.
- `domain/contracts.py`: meta remains dict; fields/types/enums unchanged.
- Backend read-only inspection: fundamental/domain/ai_output.py uses lenient metadata mirror, with no verification_summary bool/status declaration; application/report_service.py projects existing bool fields from ERD. Insufficient response already lacks erd_payload, so this change does not add Backend save support or certify an end-to-end stored report.
- Frontend read-only inspection: fundamental-report-view.tsx uses verdict_label/data_status for insufficient display, not these four metadata flags. No frontend files changed. Other external clients have not been executed; consumers must interpret the existing insufficient_data outcome instead of conflating False with a performed-check failure.

## Tests and limits
Test-first two regressions failed before change, then guarded accounting-basis runner 14/14 and calculator runner 113/113 passed. Actual Pydantic response JSON preserved existing types; route, stale state, generic empty, unsupported, wrong-year/mixed basis and badge outcomes covered. Source collection guard blocks network, subprocess, writes and project data/config access; history is fake.

Commands (approved temporary lock-pinned dependency environment):
`& "$env:TEMP\verith-sdk-boundary-20261115\Scripts\python.exe" -I ai/tests/fundamental/test_accounting_basis_isolated.py`
`& "$env:TEMP\verith-sdk-boundary-20261115\Scripts\python.exe" -I ai/tests/fundamental/test_calculators_isolated.py`

No real provider, DB, writer, app startup, browser or full LangGraph execution. No Backend settlement/reservation/Supervisor changes. This work does not establish source truth or public quality eligibility.
