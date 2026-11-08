# Fundamental adapter handoff

`FundamentalAnalysisAdapter` implements the same `AnalysisAdapter` protocol as Flow and is composed by a fixed profile; no dynamic plugin registry. Context and frozen raw JSON bind owner, analysis/admission/attempt, fingerprint, spec, deadline and original report UUID. Existing unregistered CF-013 example remains separate.

Production writer `FundamentalReportService.stage_report` requires real principal and caller session, original report_id, question and admission-frozen stock_name. It validates bindings/ERD, locks existing root, rejects any existing root/index, maps existing projection fields and flushes only. Coordinator alone commits/rolls back/state-transitions. Do not call legacy create/save/_persist or owner=None writers.

Engine input map: ticker -> ticker; question -> query; admission UUID -> req-hex; attempt UUID -> trace-hex. No historical as_of enters the engine. Server requested_at belongs to the request-context snapshot. Raw output extra fields, zero/null and UUID spelling are preserved; all child.report_id and evidence.ratio_id bindings must match.

Before real use, the domain maintainer must confirm financial calculations/prompts/data selection, source snapshots and observed periods, financial verification and data quality, cancellation/retry/billing behavior, service/provider credentials and deployment. This change validates injected synthetic boundaries; it does not certify financial output or historical reproducibility.
