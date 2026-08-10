# Printer V1 V2-9.8B Post-DTW100 Standard Four-Hour Outcome / Promotion Supplemental Audit

## Verdict

`V2_9_8B_POST_DTW100_STANDARD_FOUR_HOUR_OUTCOME_PROMOTION_SUPPLEMENTAL_AUDIT_BLOCKED_DESIGN_AMENDMENT_REQUIRED`

The first focused RED for standard 4h close/memory/terminal reconciliation exposed a prerequisite inside the same approved close/memory boundary: a clean physical `WINDOW_4H` currently reaches E2Z without a persisted outcome label, so clean-object promotion fails before campaign terminal reconciliation can truthfully classify `CLEAN_PROMOTED` or `ALREADY_EXISTS_IDEMPOTENT`.

This is now in-scope because the approved repair explicitly depends on authoritative 4h clean-object creation and replay. It was previously visible only as a historical one-token E2Z replay failure and was correctly deferred until this lane depended on it.

This supplemental audit authorizes no implementation, source call, runtime, real 4h collection, or activation.

## Baseline / RED evidence

Baseline design commit:

`f98991f8f86cdc1983db8751a257314af5a70067`

First RED test commit:

`f7757c7750ff0c23a827d9f92e6804147b9a254e`

RED workflow:

- run `31386738297`;
- job `93448728719`;
- exact-head compile PASS;
- 43 tests executed;
- seven new tests failed for the intentionally absent standard 4h successful binder/reconciler/validator;
- historical one-token `test_clean_close_runs_e2q_lane_q_lane_k_and_is_idempotent` also failed: expected `E2Z_ALREADY_EXISTS`, received `E2Z_BLOCKED`.

One new identity-mismatch test also had a fixture defect: its broad `assertRaises` could be satisfied by the intentionally missing binder itself. That test must be corrected before RED is accepted.

## Root cause

### Physical 4h close omits outcome

`one_token_4h_runtime.close_current_run_4h` creates the physical `WINDOW_4H` row with cadence/continuity identity, snapshots, memory/data quality and supporting context, but does not persist `outcome_label`.

The column has no schema default. A fresh physical 4h row therefore reaches the quality pipeline with `outcome_label = NULL` unless another owner fills it.

### Clean-object owner correctly rejects missing/unknown outcome

`clean_object_promotion.promote_clean_object` requires a non-empty, non-`OUTCOME_UNKNOWN` physical-window outcome before creating or accepting the clean episode/fingerprint pair. Missing outcome raises:

`WINDOW_OUTCOME_NOT_CLEAN_PROMOTION_ELIGIBLE`

That gate is correct money-memory law and must not be weakened.

### E2Z therefore cannot create the first 4h clean object

`run_4h_quality_gates` can reach its Lane-K invocation after E2Q and Lane Q pass, but E2Z remains blocked while the physical 4h outcome is absent. A subsequent replay is therefore also blocked because no complete clean object was ever created.

The remedy is not to weaken E2Z or fabricate an outcome.

## Proven first-hour precedent

The canonical first-hour close already has the correct ordering:

1. close the exact physical `WINDOW_1H`;
2. `_derive_and_persist_first_hour_outcome` builds the exact current-run lifecycle snapshot path;
3. it calls the existing categorical `classify_episode_outcome`;
4. it persists `outcome_label` plus path provenance on the physical window;
5. E2Q/Lane Q/E2Z run afterward.

The first-hour path deliberately includes predecessor/main lifecycle evidence rather than classifying only the continuation suffix.

## Existing outcome classifier is reusable

`printer_v1.memory.outcomes.classify_episode_outcome` is not hard-coded to 1h. It excludes only support-only 5m kinds and otherwise classifies a completed ordered snapshot path categorically. It uses no score, rank, confidence or weighted system.

The current outcome vocabulary includes categorical path outcomes such as `ROUND_TRIP`, `PUMP_AND_DUMP`, `REVIVAL`, `DEAD_TOKEN`, `CONSOLIDATION`, and `OUTCOME_UNKNOWN`.

No new 4h outcome vocabulary is needed in this repair.

## Required 4h outcome boundary

The stage-correct 4h owner must mirror the first-hour evidence law while covering the complete current-run main lifecycle through the 4h close, not only the long-continuation suffix.

For one exact token/pair/run it must use only current-run successful main-lifecycle snapshots from:

- `SNAPSHOT`;
- `WINDOW_CLOSE`;
- `CONTINUATION_SNAPSHOT`;
- `CONTINUATION_CLOSE`;
- `LONG_CONTINUATION_SNAPSHOT`;

plus the current `LONG_CONTINUATION_CLOSE` snapshot if not already in the successful ledger.

It must de-duplicate exact snapshot IDs, load them in chronological order, require exact token/pair identity, require the current 4h close snapshot, and call:

`classify_episode_outcome('WINDOW_4H', ordered_snapshots)`

The derived label and exact path provenance must be persisted on the exact physical `WINDOW_4H` before E2Q/Lane Q/E2Z.

If the classifier truthfully returns `OUTCOME_UNKNOWN`, the value remains unknown and clean promotion remains blocked/no-promotion. The repair must never coerce unknown into a promotable label merely to make E2Z pass.

## Why this remains the same major checkpoint

This finding does not add a new source, schema, scheduler, timeframe or financial capability. It is a missing composition step between the already-approved physical 4h close and the already-approved clean-object owner.

Without it, the previously designed campaign success reconciler cannot distinguish real clean promotion/replay because those states are unreachable on the canonical physical 4h path.

## Money-usefulness contribution

A clean memory without a truthful observed outcome is not useful money memory. Persisting the categorical full-path 4h outcome before promotion preserves what actually happened to the token while keeping evidence quality separate from outcome quality.

Bad outcomes may still be clean memories when evidence is complete; unknown outcomes remain non-promotable. This improves future historical comparison without creating any trading authority.

## What remains locked

- production repair until the design amendment passes;
- real 4h collection;
- operational authorization/activation;
- 12h/24h;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions, trades, audits, PnL;
- wallets, signing, live execution, real funds.

## Minimum additional proof

The amended repair must prove:

1. canonical physical 4h close persists a non-unknown categorical outcome from exact current-run main-lifecycle snapshots before E2Z when evidence produces a known outcome;
2. the exact path includes predecessor/main lifecycle plus long-continuation evidence and the current close snapshot;
3. foreign/historical snapshots are excluded;
4. exact token/pair/current-close identity mismatch fails closed;
5. truthful `OUTCOME_UNKNOWN` is preserved and cannot become clean memory;
6. first clean 4h promotion can return `E2Z_MEMORY_CREATED` and exact replay can return `E2Z_ALREADY_EXISTS`;
7. existing first-hour outcome behavior remains unchanged.

## Functionality Risks / Setbacks / Efficiency Blockers

- Classifying only the 3h long-continuation suffix would repeat the first-hour mistake already avoided by Checkpoint 5: final outcome must describe the complete main lifecycle to the checkpoint.
- Using all token snapshots by time range could admit historical or unrelated snapshots; the run-step ledger remains the identity authority.
- Weakening the clean-object outcome gate would create clean memories with unknown results and directly reduce money usefulness.
- Calling the old generic episode recorder would duplicate the active E2Z clean-object owner and is not justified.
- A new outcome vocabulary would expand product semantics unnecessarily; the existing categorical classifier is sufficient for this repair.

## Next permitted task

Amend the standard four-hour close/memory/terminal repair design to add this outcome-before-E2Z boundary, then correct/revalidate RED before any production implementation.
