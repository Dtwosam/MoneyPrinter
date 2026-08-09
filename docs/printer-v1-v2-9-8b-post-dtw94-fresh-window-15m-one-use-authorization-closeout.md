# Printer V1 — Post-DTW94 fresh WINDOW_15M one-use authorization closeout

## Verdict

`V2_9_8B_POST_DTW94_FRESH_WINDOW_15M_ONE_USE_AUTHORIZATION_REVIEW_PASS_RUNTIME_INVOCATION_ALLOWED`

The fresh post-DTW94 one-use `WINDOW_15M` authorization package passed independent review. This closeout allows exactly one later wrapper invocation under the approved host-awake safeguard. It does not itself invoke runtime.

## Frozen authorization binding

- preparation branch: `agent/v2-9-8b-post-dtw94-window15m-authorization-preparation`
- frozen HEAD: `b44e7156dfd1979582502190385a0f45f67c41e6`
- authorization id: `V2_9_8B_WINDOW_15M_AUTH_20260809T090158Z`
- authorization file: `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260809T090158Z/final_authorization.json`
- authorization SHA-256: `27f6ec95b7de6cdfeed92c12bcb6f8b095c3c1d7c870efba112ac85ae8ca6778`
- authorized at: `2026-08-09T09:01:58Z`
- expires at: `2026-08-10T09:01:58Z`
- temporal status: `TEMPORALLY_VALID`

## Authoritative database binding

- SHA-256: `d3c89f3e5f2397c2926fdaffd2588c0239c745b28e63709d565e8eef6c7c36c2`
- size: `71561216`
- inode: `1230526`
- mtime_ns: `1786238123838511351`
- migration count: `53`
- migration head: `053_pilot_input_readiness_route_domain.sql`

The database was unchanged during package preparation.

## Independent package-review evidence

- package verdict: `V2_9_8B_POST_DTW94_FRESH_WINDOW_15M_ONE_USE_AUTHORIZATION_PACKAGE_REVIEW_PASS`
- migration guard prepare: PASS
- migration guard review: PASS
- historical non-reusable authorization count: `23`
- Source Governor contract: `READY`, external requests `0`
- concrete `WINDOW_15M` composition: `READY`
- dependency preflight: `READY`
- holder budget: `READY`
- active campaigns/runs/supervision/discovery/factory/scheduler/proof work: all `0`
- locked Scheduler jobs: `0`
- historical null-position paper-audit baseline preserved: `1`
- pre-marker allowed-file count: `23`
- pre-marker allowed-file-set SHA-256: `6dc2b4a1f2907bc8b2f83bb398d8c1dcc7b1c2c7989d6005f6e22a48f40da7f3`
- pre-marker manifest SHA-256: `e01b65ae59d16a81b1940d15b93a0c192e7c836d351ac54c5246733d9814b582`
- application marker created: `false`
- wrapper invoked: `false`
- Printer runtime started: `false`
- Scheduler runtime started: `false`
- `WINDOW_15M` started: `false`

## Runtime law

Exactly one wrapper invocation is permitted while this authorization remains temporally valid. The authorization is permanently consumed once invocation begins regardless of outcome.

The Mac invocation must run under `caffeinate -dimsu` (or an explicitly approved repository-equivalent host-awake guard). No automatic retry, manual rerun, restart, resume, or successor is allowed.

The runtime must preserve the repaired holder semantics: usable adverse holder evidence remains memory-observation context and must not be projected as favorable future-action holder pass.

## Money-usefulness contribution

This authorization permits one bounded attempt to prove the corrected memory-observation path can reach and close a real `WINDOW_15M` lifecycle while preserving adverse holder information instead of rejecting it as a favorable-holder contradiction.

## What remains locked

This closeout unlocks only the single authorized `WINDOW_15M` attempt. It does not unlock `WINDOW_1H+`, retrieval, paper decisions, BUY/SELL/HOLD, paper positions, trade events, paper trade audits, or PnL.

## Proof required after invocation

The consumed attempt must be reconciled from child terminal truth, campaign report/accounting, cleanup/lease state, Scheduler/discovery parity, authoritative DB state, and any produced `WINDOW_15M`/memory evidence. Process exit code alone is never sufficient for campaign PASS.

## Functionality Risks / Setbacks / Efficiency Blockers

- Host suspension can recreate lease expiry if `caffeinate` is omitted.
- The authorization is one-use even if runtime blocks before lifecycle.
- Any post-preparation Git or authoritative-DB drift invalidates the binding.
- Holder evidence usability and favorable holder condition must remain separate.
