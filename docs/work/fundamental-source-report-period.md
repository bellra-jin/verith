# Explicit source report-period mismatch

## Evidence and scope
MD17 requires comparable periods and source lineage. Existing `domain/reporting/period.py::REPORT_SHORT_LABELS` maps 11011/FY,11013/1Q,11012/1H,11014/3Q. `infrastructure/data/dart_client.py` requests fnlttSinglAcntAll with bsns_year/reprt_code and returns list rows unchanged; source_policy preserves these rows/cache observations. Standardization reads ONLY thstrm_amount, not frmtrm_amount/bfefrmtrm_amount.

Previously a row explicitly labeled another known report code could override a correct source by newer receipt number and be displayed under the selected report's period. collect now passes the selected report code to an optional internal standardize argument. Recognized explicit source-code mismatches are excluded before latest selection, currency provenance or derived liabilities. Current source values/MetricValue fields/public DTO are unchanged. No amount conversion, alternate-period fallback, raw-file edits or Backend changes.

## Information shortage and compatibility
- Every rejected row => existing empty_data collect/report route, no shares/insights calls, empty ratios, existing insufficient_data outcome and unexecuted checksFalse. Actual observed source counts retained.
- A rejected necessary component => existing unavailable/MISSING ratio reason and no evidence for that ratio, not a mixed-period percentage.
- Matching current rows keep thstrm_amount even when prior comparison columns exist. Legitimate previous-year rows are independently collected with that previous bsns_year and the same selected report code. Prior columns are not reinterpreted or removed from source inputs.
- Missing/blank/nonstandard/non-string row report codes retain legacy compatibility. A caller omitting expected reprt_code also retains legacy behavior. This does NOT establish that legacy periods are verified.

Known-code agreement is NOT proof of equivalent duration, cumulative-vs-quarter treatment, account meaning, units, corrected-filing lineage or actual DART data accuracy. No per-observation period field is added. Actual source metadata missing cases remain limitations, not silently solved.

## Synthetic validation
Test-first new period regressions failed before implementation. Guarded calculator120/120, normalization16/16 and collect/report15/15 pass. Coverage includes all twelve pairwise known-code mismatches, newer wrong-period override, currency provenance preservation, same-filing derived liability prevention, matching zero/negative values, missing/malformed legacy codes, prior comparison columns and independent previous-year rows, partial unavailable and full empty_data. Original synthetic rows unchanged. Independent review requested.

Commands:
`& "$env:TEMP\verith-sdk-boundary-20261115\Scripts\python.exe" -I ai/tests/fundamental/test_calculators_isolated.py`
`.venv/Scripts/python.exe -I -S ai/tests/fundamental/test_standardize_isolated.py`
`& "$env:TEMP\verith-sdk-boundary-20261115\Scripts\python.exe" -I ai/tests/fundamental/test_accounting_basis_isolated.py`

Guards apply before source collection. No network/provider/DB/config/data/writer/app-startup/full-LangGraph execution; existing team changes preserved, no stage/commit/push.
