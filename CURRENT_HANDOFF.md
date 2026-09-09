# Printer V1 Handoff

## Current verified implementation

Branch: `assistant/v2-9-8b-later-cycle-mint-market-replay-repair`.

Latest fully verified code/test HEAD before this handoff-only update:
`93e8cbd6e5fb8e167bcfb33563bec03e9b084527`.

GitHub Actions run `34382217081` is green on that HEAD:

- focused post-holder/reconciliation boundary: **29 passed**;
- shared discovery/admission/lifecycle/memory boundary:
  **375 passed, 2 deselected, 32 subtests passed**;
- affected-module compile: passed;
- diff whitespace check: passed.

## Current capability

Printer V1 remains Solana-only, memecoin-only, paper-only. Source Governor is
the sole governed source-request owner and Central Scheduler is the sole
Scheduler owner. Retrieval, decision, position, PnL, signing, wallet and live
trading capabilities remain locked. `WINDOW_5M_MICRO_EVENT` is support-only;
`WINDOW_12H` and `WINDOW_24H` remain locked.

The verified path now includes:

- exact-two freeze-ready supply for each two-slot cycle;
- legitimate generic non-Pump present-pool protocol confirmation and exact
  protocol -> market resume without Pump/PumpSwap identity invention;
- exact governed <=30-mint resume accounting with durable overflow;
- MOE recreation after successful generic market revalidation;
- no generic writes into Pump-registry-bound market-floor or legacy
  eligible-reserve compatibility tables;
- no insufficient-pool terminal while actionable acquisition work still has
  exact stage capacity, flat source budget and acquisition time;
- Cycle-2 history disjointness before selection and again at transactional
  admission;
- exact-two `PAIR_READY` persistence and atomic
  `PAIR_READY -> Cycle-2 slots + tracking -> CONSUMED`;
- consumed Cycle-2 admission immediately re-enters the same owned
  `WINDOW_15M -> WINDOW_1H -> WINDOW_4H` lifecycle path as Cycle 1;
- Cycle-1 and Cycle-2 Scheduler/lifecycle identities stay disjoint and
  12h/24h work is not created;
- a clean-cadence WINDOW_4H begins as `PARTIAL_MEMORY`, never directly as
  `CLEAN_MEMORY`;
- 4h promotion requires U2 coverage, genuine E2Q window identity, Lane-Q cadence
  integrity, explicit clean shared 4h context and a non-unknown full-path
  outcome before E2Z can create a clean episode;
- missing/dirty/late/mismatched 4h context is marked dirty/do-not-train before
  promotion;
- clean-object promotion is transactional and preserves exact
  window/token/pair/window-kind/outcome identity in both episode and canonical
  fingerprint;
- integrated four-token proof now regression-locks one clean object per source
  window, dynamic `<WINDOW_KIND>_CLEAN_MEMORY` episode identity, one canonical
  fingerprint per clean episode, exact 4h fingerprint-to-window identity, and
  zero retrieval/decision/position/trade/audit rows created by the run.

## Latest meaningful result

No runtime defect was found in the downstream lifecycle -> clean-memory
promotion chain. The existing production owners were already fail-closed.

The new proof closes a coverage gap in the integrated two-cycle Standard-4H
audit: any clean episode/fingerprint created by the four-token run must remain
exactly bound to its physical source window and cannot activate retrieval or
decision/trading surfaces.

The proof change is test-only:
`tests/test_v2_9_8b_full_four_token_standard4h_audit.py`.

## Proven blocker

None remains in the scoped discovery/admission, Cycle-2 atomic lifecycle, or
lifecycle -> clean-memory identity lanes.

This is **not** operational authorization and does not establish authoritative
database or live-run readiness. No operational Printer run, provider execution,
Scheduler operation or authoritative database mutation was performed.

Default branch `master` is not a safe blind integration target for this branch:
the last comparison showed substantial historical divergence. Do not rebase,
merge, or open a massive integration diff without first resolving the intended
active development lineage.

## Exact next permitted action

Begin a narrow read/test-only review at the clean-memory -> downstream-consumer
boundary: prove that clean episodes/fingerprints cannot be consumed by retrieval
or paper-decision paths while those capabilities remain locked, and repair only
a concrete reachable unlock if one is found.

Do not run Printer operationally or mutate the authoritative database without a
new explicit authorization boundary.
