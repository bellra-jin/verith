# Received vector chunk locator in internal evidence context

## Requirement and existing identifiers
MD sections13/18 require source/locator/version trace and pinned evidence. Current `infrastructure/graph/vectorize.py::_chunk_id` already constructs stock-index-eight-hex identifiers using a truncated SHA1 of stock/index/body. `vector_retrieve.py::_RETURN_PROPS` already returns id and stock_code. These are received chunk locators, not immutable release IDs, authentic source attestations or guaranteed collision-free identities.

`application/evidence_context.py::_format_chunk_context` previously omitted the received identifier when preparing the QA evidence prompt, leaving only local V1/V2 references. It now preserves a syntactically valid existing identifier with a matching explicit stock_code. Missing/non-string/malformed/newline-injected IDs and mismatched stock codes become an empty internal locator, never a generated replacement. Context explicitly states immutable release/version unconfirmed. Invalid locator does not remove or alter the source text or other existing metadata.

## Compatibility-first limit
Public citation text and graph/vector evidence JSON are unchanged. parse_answer extracts citationText, but build_report_payload does not export it; consequently adding a locator suffix there would NOT create durable saved-report provenance. That initial surface idea was removed before completion. No public source fields, section labels, evidence IDs, frontend code, Backend schema or dataset files were changed. Existing helper facade APIs remain unchanged; new helper is private to evidence_context.

This is only internal prompt trace preservation, NOT completion of MD persisted-source/version requirements. Existing final_state chunks already retain the original id; the change stops losing it in the compact QA context. It does not recompute/verify the old ID against source text, certify a company alias, pin a dataset or prove filing/date/source freshness. Same ID may be reused or forged. Snapshot/durable report locator and release pin require a separately agreed integration contract; these remain blockers.

## Tests and limits
Test-first missing-context-locator assertion failed. Guarded company evidence10/10, export29/29 and evidence-context6/6 pass. Checks cover expected locator, absent/type-invalid/malformed/injected/mismatched stock, original chunk nonmutation, original citation prefix/link formatting, public evidence IDs/schema, existing citation parser and actual static HTML JSON render. The new helper and consuming files remain below400 lines.

No actual corpus/config/DB/provider/writer/browser was invoked; tests use synthetic sources. Full model compliance, UI runtime and real saved report lookup are not verified. Existing stored outputs are untouched.

Commands:
`.venv/Scripts/python.exe -I -S ai/tests/industry/test_company_evidence_isolated.py`
`.venv/Scripts/python.exe -I -S ai/tests/industry/test_export_isolated.py`
`.venv/Scripts/python.exe -I -S ai/tests/industry/test_evidence_context_isolated.py`
