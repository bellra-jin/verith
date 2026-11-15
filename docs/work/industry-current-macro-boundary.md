# Current macro indicator boundary

## Requirement and source investigation
SDD05's 2026-11-12 scope requires corporate-relevant rates/FX/prices/cycle with source and reference date, not predicted profit magnitude or stock direction. Existing `domain/answer_policy.py` only prompted this rule.

Read-only source and public documentation inspection found Industry's corporate filing/graph/chunk retrieval and no authoritative current rate/FX time-series collector, source registry or typed freshness connection. Industry config source declares corporate data paths and model settings; secret configuration values and actual data files were not opened. Searches for ECOS/FRED/BOK/한국은행/금리/환율 did not establish a connected authoritative macro source. This is not evidence that a different team/service has no such data.

## Smallest safe improvement
`domain/macro_scope.py` recognizes a narrow explicit current-indicator value request. `application/retrieval.py::generate_answer` holds those requests before QA factory/invoke and verifier, returning a deterministic existing string and bound not_run record. It does not trust arbitrary rows/chunks claiming official source names or dates. The existing public export becomes unchecked, never verified. There are no new public fields, datasets, endpoints or contracts.

Current indicator modifier must directly qualify a named indicator, with an immediate value/status request, or the supported reverse word order. Narrow English current/latest rate phrases are supported only as a complete short direct query (optionally what-is/tell-me/show-me/give-me/how-much-is). English explanatory clauses and historical quotations are not held just because they mention a current-indicator phrase. Different-subject current modifiers, historical comparison, dated-as-of phrases and generic corporate transmission explanations remain on the existing path. A recognized current-value clause within a mixed question holds the whole answer, avoiding selective unsupported completion. No conversion or synthetic current number is introduced.

## Tests and honest limits
Test-first export regression failed before implementation. Guarded actual generate_answer/agent-answer-node/export fake tests now 28/28, macro prompt6/6 pass. Fixtures include fake official-looking dates/source names, old chunks, no evidence, verify=False, current vs past comparisons and unrelated current subjects. No source/DB/provider/writer/app initialization was executed.

This is a narrow request boundary, NOT general temporal NLP, numeric truth checking or a complete macro agent. Implicit-current '금리 알려줘', complex word order, synonyms, quotations and negation are not exhaustively parsed. Such unmatched wording remains governed by the existing prompt/verification limitations, not proved safe. Dated historical bypass does not authenticate a dated observation. Upstream classification/retrieval may already have executed, so this is zero QA/verifier calls on held answers, not zero run cost/network. Retained graph evidence may still appear in payload; body explicitly says current status is unconfirmed. Backend completed/quality status is unchanged and not certified. Historical saved outputs are not rewritten.

The actual current indicator/source/date/unit/freshness connection and live accuracy remain blocked on an approved authoritative source and integration scope. Do not claim current rates/FX support complete.

Commands:
`.venv/Scripts/python.exe -I -S ai/tests/industry/test_export_isolated.py`
`.venv/Scripts/python.exe -I -S ai/tests/industry/test_macro_prompt_isolated.py`

Independent review follow-up: English explanatory/historical mentions initially overmatched; new regressions reproduced the issue, then whole-short-query matching removed that overreach. Normal English current-value requests remain held. Complex compound English requests are deliberately outside the narrow detector, not certified safe.
