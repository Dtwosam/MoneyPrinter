# Authorization Report — V2_9_8B_WINDOW_15M_AUTH_20260805T101248Z

## Verdict

`V2_9_8B_POST_DRIFT_GUARD_WINDOW_15M_AUTHORIZATION_PASS`

This package authorizes exactly one manual authoritative `WINDOW_15M` campaign
attempt through the canonical one-shot wrapper on branch
`agent/v2-9-8b-pre-authorization-migration-ledger-drift-guard` at exact HEAD `7a4152bb90b14317513bb10879ee3861410270c7`
(`Enforce package database binding before consumption`).

Authoritative database `/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3` is pinned at
SHA-256 `5cf5326c4a820538a2f648a274bf14797c23a988bfae0f25aa49f01205cfafdc` (size `68009984`, inode `1230526`, mtime_ns `1785921369859239685`,
migration head `052_memory_observation_eligibility_layers.sql`, 52 migrations,
integrity `ok`, foreign-key violations 0, no sidecars).

One-use law: consumed when wrapper execution begins, regardless of result.
Reuse, retry, rerun, resume, restart, automatic successor, concurrent or second
execution, discovery-only substitutes and direct child invocation are forbidden.

Created `2026-08-05T10:12:48.555929Z`; expires `2026-08-06T10:12:48.555929Z`.
Expiry is operator-enforced: the production wrapper does not read `expires_at`.

Prior authorization `V2_9_8B_WINDOW_15M_AUTH_20260804T214901Z` remains permanently
consumed and must not be reused. Migration-ledger drift-guard prepare/review PASS
is required before application.
