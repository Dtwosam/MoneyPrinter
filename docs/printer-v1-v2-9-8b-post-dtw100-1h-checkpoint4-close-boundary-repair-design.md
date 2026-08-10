# Printer V1 V2-9.8B Post-DTW100 1h Checkpoint 4 Close-Boundary Truth Repair Design

## Design verdict

`V2_9_8B_POST_DTW100_1H_CHECKPOINT_4_CLOSE_BOUNDARY_TRUTH_REPAIR_DESIGN_PASS`

Implement one narrow repair across the existing first-hour factory/close/cadence owners. Reuse all current collection, Scheduler, Source Governor, continuity, memory-window, and campaign-ownership primitives. Do not create a parallel 1h close path.

## Baseline

Design baseline: `495b14221c1e2a68d04425c1056db37e91c03ee7`.

Audit verdict:

`V2_9_8B_POST_DTW100_1H_CHECKPOINT_4_CLOSE_BOUNDARY_AUDIT_BLOCKED_CLOSE_TRUTH_REPAIR_REQUIRED`

## Canonical owners

- `src/printer_v1/operator_cli/one_command_15m_factory.py`
  - runtime claim/dispatch/finalization;
  - exact V2 campaign Scheduler/window ownership helpers.
- `src/printer_v1/operator_cli/lane_e2o_1h_window_close.py`
  - canonical `WINDOW_1H` evidence-window writer.
- `src/printer_v1/snapshots/cadence_policy.py`
  - one cadence/closing-freshness policy owner.
- `src/printer_v1/operator_cli/campaign_ownership.py`
  - reused unchanged for state transitions and one-shot memory-row binding.

No new module, schema, migration, source adapter, Scheduler, or collector.

## Repair 1 — real-time CLOSE_PENDING

Add a private factory helper for an owned `CONTINUATION_CLOSE` Scheduler job.

Contract:

- resolve the exact V2 `WINDOW_LIFECYCLE` ownership row;
- require exact `stage_id == WINDOW_1H`, exact campaign/run/cycle/token-slot/window identity, and one exact campaign window;
- if the window is `COLLECTING`, use `campaign_ownership.transition_state()` to advance to `CLOSE_PENDING`;
- `CLOSE_PENDING` is idempotent;
- any other nonterminal/terminal state fails closed;
- historical/non-campaign callers with no V2 ownership row remain compatible/no-op.

Call it immediately after the close Scheduler job is claimed and its run-step enters `RUNNING`, before any close-time source work.

## Repair 2 — exact memory-row binding at successful close

Add a private factory helper that runs only for a successful `CONTINUATION_CLOSE` result with a non-null `memory_window_id`.

Contract:

- resolve the exact owned `WINDOW_1H` from the Scheduler job;
- require the campaign window is `CLOSE_PENDING`;
- call existing `campaign_ownership.bind_window_memory_row_id()`;
- require exact token, pair, and `WINDOW_1H` identity through the canonical binder;
- exact repeat with the same row is idempotent;
- conflicting row binding fails closed;
- perform the bind before `complete_job()` so the Scheduler cannot report successful close while the campaign graph is unbound.

This does not terminalize or promote the campaign window. Checkpoint 5/6 retain audit/promotion/terminal responsibilities.

## Repair 3 — close failure is token-local and terminal

For any token-local `CONTINUATION_CLOSE` failure after claim:

- Scheduler job follows existing fail path;
- campaign Scheduler projection follows Scheduler truth;
- pending work for only that token is cancelled as today;
- exact owned first-hour campaign window becomes `BLOCKED` with the first close failure cause;
- peer token/window/work remains untouched.

Existing run-wide safe-stop cleanup remains unchanged.

## Repair 4 — actual closing snapshot must reach the fixed deadline

In `close_1h_memory_window_from_snapshot()` when `continuation_of_15m` is supplied:

1. compute the authoritative fixed deadline using existing `compute_1h_continuation_deadline()`;
2. parse the actual closing snapshot `captured_at`;
3. if either timestamp is unparseable, fail closed;
4. compute `closing_snapshot_lateness_seconds = closing_snapshot_at - deadline`;
5. if lateness is negative beyond tiny floating/timestamp tolerance, return `E2O_1H_WINDOW_BLOCKED` and write no 1h row;
6. retain the fixed `window_start_at = 15m close` and `window_end_at = deadline` rather than drifting the target to the observed close;
7. persist/report the observed close timestamp and lateness in supporting context/result.

This preserves the correct fixed first-hour target while proving the evidence actually reached it.

## Repair 5 — reuse the shared forced-closing freshness policy

For both `WINDOW_1H` FAST and NORMAL cadence policies set:

- `require_full_anchored_duration=True`
- `require_forced_closing_snapshot=True`

Do not change:

- 2700-second duration;
- FAST 120/180/240 gap thresholds;
- NORMAL 240/360/480 gap thresholds;
- FAST expected 24 snapshots;
- NORMAL expected 13 snapshots;
- source or Scheduler ceilings;
- `closing_clean_late_seconds=60` default.

The existing evaluator then provides the desired semantics:

- closing snapshot before deadline: BLOCKED;
- at deadline / <=60s late: closing freshness CLEAN, subject to ordinary count/gap gates;
- >60s late but below nominal interval: DIRTY;
- lateness >= nominal interval: BLOCKED.

The policy tightens evidence truth only; it adds no requests or Scheduler work.

## TDD / focused proof

Create one checkpoint-specific offline test module. RED must be produced before production changes and must fail for the missing/incorrect close-boundary behavior, not fixture construction.

Minimum proof scenarios:

1. campaign window starts `COLLECTING`; claiming `CONTINUATION_CLOSE` and applying the close-boundary owner moves only that exact window to `CLOSE_PENDING`;
2. early closing snapshot (< fixed deadline) creates zero `WINDOW_1H` rows;
3. exact-deadline closing snapshot creates/returns the genuine 1h row and reports zero lateness;
4. successful result binds that row to the exact campaign window while leaving state `CLOSE_PENDING`;
5. conflicting memory-row bind fails closed;
6. 1h cadence evaluator proves at-deadline/near-deadline clean-closing freshness, >60s dirty freshness, and >= nominal-late blocked freshness;
7. `CONTINUATION_CLOSE` failure blocks only the affected token's exact campaign window; peer remains active;
8. directly affected Checkpoints 1-3, operational first-hour, cadence, and campaign Scheduler-ownership tests stay green.

Risk-based verification only; no broad repository regression suite is required for this narrow checkpoint.

## Money-usefulness contribution

The repair ensures a future clean first-hour memory corresponds to evidence that actually reached the first-hour boundary, not merely metadata containing a 2700-second target. It also makes the campaign graph and close row agree at the moment the close exists.

## What remains locked

No live first-hour run, authorization/wrapper, 4h activation, 12h/24h, retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events, paper audits, PnL, wallet/private keys/real funds/live execution, paid APIs, scoring/ranking/confidence/weighted logic, embeddings, or vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only.

## Functionality Risks / Setbacks / Efficiency Blockers

- Existing old 1h fixtures may create synthetic closes before the deadline; any failures must be classified as stale fixtures unless they demonstrate a production contract problem.
- The forced-close policy can reveal real lateness that previous clamping hid. This is intentional; do not widen thresholds merely to preserve old green tests.
- The current close function immediately invokes downstream audit/promotion after writing the row. This design does not refactor that sequencing; Checkpoint 5 audits it separately.
- Memory-row binding must happen before Scheduler success but after successful row creation; reversing that order can leave either a phantom bind or an unowned success.

## Stop condition

After implementation, focused proof, and exact-closeout-HEAD verification pass, close Checkpoint 4. Only then begin Checkpoint 5 — genuine first-hour memory construction.
