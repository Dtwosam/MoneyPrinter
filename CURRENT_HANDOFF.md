# Printer V1 Handoff

## Current verified implementation

Branch: `assistant/v2-9-8b-cycle1-cycle2-four-hour-admission-proof`.

Latest fully verified production code/test HEAD before this handoff-only update:
`7b3f7ae2253ae20ee58c1193b2b5b60f57129cc2`.

GitHub Actions run `34471715199` is green on that HEAD:

- focused post-holder/reconciliation boundary: **29 passed**;
- exact two-cycle/four-token clean-4h-memory proof: **1 passed**;
- shared discovery/admission/two-cycle Standard-4H boundary: **399 passed, 2 deselected, 32 subtests passed**;
- affected-module compile: passed;
- diff whitespace check: passed.

## Current capability

Printer V1 remains Solana-only, memecoin-only, paper-only. Source Governor remains
the governed source-request owner and Central Scheduler remains the Scheduler
owner. Retrieval, decision, position, PnL, signing, wallet and live-trading
capabilities remain locked. `WINDOW_5M_MICRO_EVENT` is support-only;
`WINDOW_12H` and `WINDOW_24H` remain locked.

The disposable Standard-4H proof now verifies the requested full four-token,
two-cycle clean-memory success path: real Cycle-1 admission creates exactly two
owned slots, Cycle 2 admits a fresh/disjoint exact two-slot pair, both cycles
progress through their owned `WINDOW_15M -> WINDOW_1H -> WINDOW_4H` lifecycles,
and the four physical 4h windows each produce one exact clean episode and one
canonical fingerprint when the governed evidence is clean. Cycle/slot/token/pair/
physical-window identities and outcomes are required to match throughout.

Cadence, safety, source-quality, snapshot-coverage and clean-memory requirements
were not weakened. Dirty, stale, conflicting or incomplete evidence remains
blocked from clean promotion.

## Latest meaningful result

The strengthened four-clean-memory regression first proved a real production
sequencing defect. A clean physical `WINDOW_4H` reached U2 and E2Q successfully,
but Lane Q returned `CAMPAIGN_WINDOW_BINDING_MISSING`; E2Z therefore never ran
and the campaign window terminalized as `NO_PROMOTION`.

Root cause: Standard-4H quality gates ran before the owned campaign `WINDOW_4H`
was identity-bound to its newly closed physical memory row, while Lane Q's
historical cadence authority intentionally resolves through that exact campaign
window -> token slot -> tracking queue ownership graph.

Production repair `7b3f7ae2253ae20ee58c1193b2b5b60f57129cc2` fixes only that sequencing.
For `STANDARD_CAMPAIGN` closes, `close_current_run_4h` now requires the exact
V2 stage-scoped Scheduler/campaign owner, verifies token/pair/window/state
identity, binds the physical row through the existing
`campaign_ownership.bind_window_memory_row_id` owner, and read-back verifies that
the campaign window remains `CLOSE_PENDING`, the slot remains
`WINDOW_4H_CONTINUING`, and no terminal cause/time was introduced. The existing
terminal reconciler still exclusively owns clean/dirty/no-promotion terminal
classification after U2 -> E2Q -> Lane Q -> E2Z.

The exact regression is green after the repair and proves all four owned 4h
windows have distinct clean episodes and canonical fingerprints with exact
identity and matching non-unknown outcomes.

## Proven blocker

No code blocker remains proven in the audited disposable four-token/two-cycle
Standard-4H clean-memory path.

This does not guarantee that a live market run will always yield four clean
memories: real candidate scarcity or dirty/stale/conflicting/missing governed
evidence can lawfully prevent admission or clean promotion. The deterministic
proof also simulates elapsed time; it is not a four-wall-clock-hour host-uptime
proof.

No live provider/RPC execution, authoritative database mutation, wallet/signing,
or trading operation was authorized or performed in this lane.

Default branch `master` remains historically divergent from this active
development lineage and is not a safe blind merge/rebase target.

## Exact next permitted action

Treat `7b3f7ae2253ae20ee58c1193b2b5b60f57129cc2` as the verified production-code
anchor for this lane. If continuing toward operational use, open a new narrow
read/test-only readiness lane that explicitly checks real wall-clock supervision,
provider/RPC readiness and authorization against this anchor. Do not weaken any
admission, cadence, evidence or clean-memory gate, and do not execute Printer
operationally or mutate the authoritative database without a new explicit
authorization boundary.
