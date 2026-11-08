# Fundamental owned analysis v1

POST `/api/fundamental/analyses`: exact `ticker`, `question`, `idempotency_key`, `allow_analysis:true`; strict finite JSON <=4096 bytes. GET `/{analysis_id}` is read-only. Server fixes request timestamp once; no public as_of or owner. Registered stock required. Default off.

The fixed Flow/Fundamental profiles use one coordinator. It commits claim before HTTP, validates/freezes original canonical JSON before publication, then stages root/children/index + stored in one transaction. Unknown commit never redispatches. Same key/input reuses identity; changed input conflicts. Only exact report uniqueness is a conclusive collision. Deleted ledger retains IDs/hashes and clears request/input/result text.

AI HTTP is `/internal/fundamental/analyze`, fixed service header `X-Fundamental-Service-Token`, token >=32 UTF-8 bytes, gated before engine import. Nested original engine request has exactly request_id/trace_id/ticker/query. Request context schema `fundamental.request-context.v1` is not financial source data. Deadline 60s, Backend HTTP total65s, BFF total70s; no retry. One worker slot remains held until actual worker/default-executor completion after timeout/cancellation. This is per process and does not prove provider cancellation or billing stops.

Owned list/count/detail/delete require matching root owner, exactly one total Fundamental index with same owner, and stored ledger association in SQL before pagination. Reads compare snapshot against all projections; no legacy fallback. Stage has no transaction control. Delete locks session -> run -> original root, then tombstones/scrubs/deletes atomically; shared stock stays.

UI uses separate account/tab pending identity, explicit POST and GET-only refresh/recovery, private BFF, structured text, and http/https source links only. No public raw save, bulk deletion, iframe/HTML/PDF rendering. Missing periods stay unknown; current request time never substitutes for source financial dates. Real provider/calculation/source coverage remains unverified.
