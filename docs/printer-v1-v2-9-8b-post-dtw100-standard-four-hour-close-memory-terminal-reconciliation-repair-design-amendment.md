# Printer V1 V2-9.8B Post-DTW100 Standard Four-Hour Close / Memory / Terminal-Reconciliation Repair Design Amendment

## Verdict

`V2_9_8B_POST_DTW100_STANDARD_FOUR_HOUR_CLOSE_MEMORY_TERMINAL_RECONCILIATION_REPAIR_DESIGN_AMENDMENT_PASS`

The original repair design remains valid for campaign binding/reconciliation and standard two-window terminal validation, with one mandatory prerequisite inserted before the quality/promotion boundary: derive and persist the exact full-path `WINDOW_4H` outcome before E2Q/Lane Q/E2Z.

This amendment does not authorize source fetching, runtime, real 4h collection, activation, 12h/24h, retrieval, decisions, positions or financial capability.

## Controlling sources

Original repair design:

`docs/printer-v1-v2-9-8b-post-dtw100-standard-four-hour-close-memory-terminal-reconciliation-repair-design.md`

Supplemental audit:

`docs/printer-v1-v2-9-8b-post-dtw100-standard-four-hour-outcome-promotion-supplemental-audit.md`

The amendment changes only the ordering and scope needed to make the original clean-promotion/replay requirements reachable on the canonical physical 4h path.

## Amendment 1 — add exact full-path 4h outcome owner

Add a private canonical factory helper conceptually:

`_derive_and_persist_four_hour_outcome(connection, run_id, token_id, pair_id, window_id, current_close_snapshot_id)`

It mirrors the proven first-hour outcome contract but is 4h-specific.

### Physical target

Require exactly:

- target `printer_memory_windows` row exists;
- exact token id;
- exact pair id;
- `window_kind='WINDOW_4H'`.

Wrong/missing physical identity fails closed before any update.

### Exact current-run snapshot path

Build the full main-lifecycle path for this exact run/token/pair from run-step ledger rows with successful snapshots from:

- `SNAPSHOT`;
- `WINDOW_CLOSE`;
- `CONTINUATION_SNAPSHOT`;
- `CONTINUATION_CLOSE`;
- `LONG_CONTINUATION_SNAPSHOT`.

Add the current `LONG_CONTINUATION_CLOSE` snapshot explicitly if it is not already represented by a successful ledger row.

Rules:

- de-duplicate exact snapshot IDs;
- load only those IDs from `printer_token_snapshots`;
- sort by `captured_at,id`;
- require every loaded snapshot to match exact token/pair;
- require the current long-close snapshot to be present;
- require at least two snapshots;
- missing/foreign snapshot identity fails closed.

Do not query all token snapshots by a broad timestamp range. The current-run step ledger is the inclusion authority.

### Classification

Call the existing categorical owner:

`classify_episode_outcome('WINDOW_4H', ordered_snapshots)`

Do not create a new 4h-specific outcome vocabulary or threshold set in this lane.

Persist the returned label exactly, including `OUTCOME_UNKNOWN` when that is the truthful classifier result.

### Provenance

Merge into the physical 4h supporting context:

- `full_four_hour_outcome_snapshot_ids`;
- `full_four_hour_outcome_snapshot_count`;
- `full_four_hour_outcome_path_start_at`;
- `full_four_hour_outcome_path_end_at`;
- `full_four_hour_outcome_source='EXACT_CURRENT_RUN_MAIN_LIFECYCLE'`.

Persist outcome + provenance with exact token/pair/`WINDOW_4H` compare-and-update semantics.

## Amendment 2 — execution ordering

In `_execute_long_4h_step`, after:

1. physical `close_current_run_4h` succeeds;
2. shared 4h context is constructed/persisted and any dirty context status is applied;

but **before** `run_4h_quality_gates`:

3. derive and persist the full-path 4h outcome under Amendment 1;
4. commit the physical/context/outcome facts required by the separate-path E2Q/Lane-Q/E2Z owners;
5. run the existing 4h quality gates unchanged.

Attach the outcome report to the close result as `full_four_hour_outcome`.

This preserves the current truthful transaction boundary: quality gates open separate connections and therefore require the prerequisite physical/context/outcome facts to be committed first.

## Amendment 3 — clean promotion/replay interpretation

The original design's 4h success classifier remains authoritative after this amendment.

A complete clean object may only exist when:

- physical 4h evidence passes current clean gates;
- shared 4h context is clean-ready;
- outcome is known and clean-promotion eligible;
- E2Z creates/verifies the exact episode/fingerprint pair.

If outcome is `OUTCOME_UNKNOWN`, E2Z remains blocked and the campaign success classifier must resolve the physical completion as `NO_PROMOTION`, not fabricate `CLEAN_PROMOTED`.

For exact known-outcome clean paths:

- first promotion event `E2Z_MEMORY_CREATED` -> campaign `CLEAN_PROMOTED`;
- exact pre-existing complete object + `E2Z_ALREADY_EXISTS` -> `ALREADY_EXISTS_IDEMPOTENT`.

## Amendment 4 — correct RED requirements

Before production implementation, fix the identity-mismatch test so binder existence is asserted outside `assertRaises`.

Add/retain a canonical physical-pipeline test that proves:

- 4h outcome is persisted before E2Z;
- known outcome allows first clean-object creation;
- second quality/promotion pass returns `E2Z_ALREADY_EXISTS`;
- no duplicate episode/fingerprint appears.

The previously historical one-token idempotency failure is now an intentional RED signal for this amended repair and must pass in GREEN.

## Production scope amendment

Expected production scope remains narrow:

- `src/printer_v1/operator_cli/one_command_15m_factory.py` — full-path 4h outcome owner, execution ordering, successful campaign binding, standard validator/routing;
- `src/printer_v1/operator_cli/one_token_4h_runtime.py` — successful 4h campaign terminal reconciler only.

Do not modify:

- `clean_object_promotion.py` outcome gate;
- `e2z_clean_memory_creation.py` eligibility gate;
- outcome classifier thresholds/vocabulary;
- physical 4h cadence/continuity policy;
- schema/migrations;
- sources or budgets.

A focused RED proving another canonical owner must change is required before widening production scope.

## Amended minimum GREEN proof

In addition to the original design proof list, require:

1. exact full current-run 4h snapshot path is used, including predecessor lifecycle and current long close;
2. foreign/historical snapshots are excluded;
3. known categorical 4h outcome is persisted before E2Z;
4. truthful `OUTCOME_UNKNOWN` remains non-promotable and terminalizes as `NO_PROMOTION`;
5. canonical one-token 4h first promotion succeeds and exact replay returns `E2Z_ALREADY_EXISTS`;
6. clean-object outcome gate remains unchanged;
7. first-hour outcome derivation tests remain green.

## Money-usefulness contribution

The amendment ensures that `CLEAN_MEMORY` means both clean evidence and a known observed result. It keeps a token's path outcome separate from whether that outcome was good or bad and prevents an unknown result from entering clean historical comparison later.

## What remains locked

Unchanged from the original design: real 4h collection, activation, 12h/24h, retrieval, paper decisions, BUY/SELL/HOLD, positions/trades/audits/PnL, wallets/signing/live execution/real funds, paid APIs, scoring/ranking/confidence/weighted logic, embeddings/vectors.

## Functionality Risks / Setbacks / Efficiency Blockers

- Full-path outcome derivation must use run-step identity, not broad timestamp inclusion.
- `OUTCOME_UNKNOWN` must remain honest even if it prevents a desired clean promotion.
- The quality pipeline must not be rewritten merely because its prerequisite outcome was missing.
- Campaign binding still occurs after the separately committed physical quality pipeline; later binding failure cannot erase physical evidence.
- The original standard two-window validator remains necessary; fixing outcome alone does not terminalize campaign ownership.

## Next task

Correct the RED tests and re-run focused RED under this amended design. Implement only after the corrected RED is clean and attributable to the amended missing behavior.
