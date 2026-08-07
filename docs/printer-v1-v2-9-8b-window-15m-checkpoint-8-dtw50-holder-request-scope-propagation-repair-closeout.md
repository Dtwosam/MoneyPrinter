# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — DTW-50 Holder Request Scope Propagation Repair Closeout

Date: 2026-08-07

Linear: `DTW-50`

Design HEAD: `1feff619726b496867306d3be52a46c8962d9e68`

Implementation commit: `6015e2c3084cf6b4ebbdf4097a71a369813f2087`

Verdict:

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_DTW50_HOLDER_REQUEST_SCOPE_PROPAGATION_REPAIR_OFFLINE_PASS`

## Proven defect

The consumed post-DTW49 proof froze `HONEST_BLOCKED` before lifecycle because holder request IDs 13–16 were stage-reported and transport-complete but persisted outside the canonical campaign request-key root. Strict reconciliation correctly classified them as `CURRENT_STAGE_REQUEST_OUTSIDE_CAMPAIGN_SCOPE` and `MANIFEST_REQUEST_NOT_DURABLE`.

## Deterministic RED

At the approved design baseline, the focused regression reproduced the holder request under the legacy `run_id:holder_eligibility_N:context:*` namespace and failed the exact campaign-root / strict-reconciliation expectation.

Classification: `DTW50_HOLDER_REQUEST_OUTSIDE_CAMPAIGN_SCOPE_RED_CONFIRMED`.

## Repair

The existing validated campaign request-key root is propagated from permanent supply diagnostics into the authoritative holder funnel.

Each permanent holder candidate receives `<campaign-root>-holder-<ordinal>-context`.

`_collect_preclose_context()` accepts that explicit prefix only when supplied; default callers retain their legacy run/step prefix unchanged.

The one permitted holder backup receives the same explicit holder prefix. Backup eligibility, endpoint, retry law, budgets and evidence rules are unchanged.

## Offline GREEN

- changed-file `py_compile`: PASS
- dedicated DTW-50 regression: `3 passed`
- existing C8 real-consumer compatibility: `9 passed`
- complete focused C8 suite: `105 passed`
- exact four-file implementation manifest: PASS
- `git diff --check`: PASS
- provider/network execution: NONE
- controlling C8 proof: NONE

## Money-usefulness contribution

Holder evidence now remains inside the same exact durable campaign provenance boundary as discovery and market evidence, removing an accounting-only barrier to trustworthy 15-minute memory without relaxing source or evidence law.

## What remains locked

Checkpoint 8 remains open pending independent DTW-50 review/readiness and a separately authorized future one-shot proof. Operational `WINDOW_15M` memory activation, `WINDOW_1H+`, retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits and PnL remain locked.

## Functionality Risks / Setbacks / Efficiency Blockers

1. A future C8 attempt can expose another downstream blocker; do not rerun automatically.
2. The repair relies on the already-validated root and intentionally refuses to reconstruct a second scope.
3. Reconciliation remains strict and unchanged.
4. Another controlling proof requires a new explicit authorization after independent readiness review.
