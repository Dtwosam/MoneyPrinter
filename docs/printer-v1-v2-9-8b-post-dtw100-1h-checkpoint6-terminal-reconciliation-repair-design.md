# Printer V1 V2-9.8B Post-DTW100 1h Checkpoint 6 Terminal-Reconciliation Repair Design

## Design verdict

`V2_9_8B_POST_DTW100_1H_CHECKPOINT_6_TERMINAL_RECONCILIATION_REPAIR_DESIGN_PASS`

Implement one bounded lifecycle-reconciliation repair using the existing campaign window/token-slot tables, state vocabulary, exact continuation Scheduler ownership, and first-terminal-cause law. Do not create a new lifecycle engine, schema, Scheduler path, 4h successor, or retry mechanism.

## Baseline

Design baseline: `2bd655c5e2ca2e920254c883d2a4f6d39a6d433c`.

Audit verdict:

`V2_9_8B_POST_DTW100_1H_CHECKPOINT_6_TERMINAL_RECONCILIATION_AUDIT_BLOCKED_WINDOW_AND_TOKEN_STATE_RECONCILIATION_REQUIRED`

## Canonical owners

- `src/printer_v1/operator_cli/campaign_ownership.py`
  - existing state vocabulary and compare-and-update law;
  - exact campaign window/token-slot ownership tables.
- `src/printer_v1/operator_cli/operational_selective_1h.py`
  - first-hour lifecycle boundary and existing `bind_1h_memory_window()` behavior.
- `src/printer_v1/operator_cli/one_command_15m_factory.py`
  - real continuation success/failure/run-wide cleanup wiring;
  - exact continuation Scheduler-job -> campaign-window resolver.

No schema, migration, source adapter, new Scheduler job kind, or 4h planner change.

## Repair 1 — classify a successful first-hour close from authoritative memory truth

After Checkpoint 5 succeeds, the exact physical `WINDOW_1H` row and its clean-object result are known.

Use the same conservative meaning already established for 15m campaign-window close classification:

- exact eligible `WINDOW_1H_CLEAN_MEMORY` episode exists for the physical row -> `CLEAN_PROMOTED`;
- physical row has `do_not_train != 0` or non-`CLEAN_DATA` quality -> `DIRTY`;
- otherwise the close is valid but no authoritative clean object exists -> `NO_PROMOTION`.

Do not derive campaign terminal state from a convenient E2Z string alone. Runtime/source/continuity failure is not a normal no-promotion result and remains `BLOCKED`.

## Repair 2 — reconcile successful window and token together

Add one narrow first-hour terminal-reconciliation helper under the existing first-hour/campaign ownership surface. It must operate on the exact campaign `WINDOW_1H` and its owning token slot in one transaction.

Success preconditions:

- exact campaign window exists and is `WINDOW_1H`;
- exact owning slot identity matches the window token/pair/campaign/run/cycle;
- window is at `CLOSE_PENDING` unless this is an exact idempotent replay;
- physical `memory_window_row_id` exists and exact token/pair/window-kind identity matches;
- slot is `WINDOW_1H_CONTINUING` unless already exactly reconciled.

Success mutation:

1. bind the exact physical memory row if not already bound;
2. `CLOSE_PENDING -> AUDITING`;
3. `AUDITING -> CLEAN_PROMOTED | DIRTY | NO_PROMOTION` with immutable first terminal cause;
4. `WINDOW_1H_CONTINUING -> WINDOW_1H_CLOSED`;
5. read back exact window/slot/memory identity before commit.

Repeated exact reconciliation returns idempotently without a duplicate terminal cause or state transition. A conflicting terminal state, memory row, slot identity, or first cause fails closed.

No success path may move the token to `WINDOW_4H_CONTINUING`.

## Repair 3 — token-local first-hour failure

When a real `CONTINUATION_SNAPSHOT` or `CONTINUATION_CLOSE` fails token-locally:

- retain existing Scheduler failure and pending-work cancellation;
- exact owned `WINDOW_1H` -> `BLOCKED` with the existing failure cause;
- exact owning token slot `WINDOW_1H_CONTINUING -> FAILED` with the same first cause;
- peer window/slot remain untouched.

The repair must be idempotent if cleanup revisits the same exact failed owner.

## Repair 4 — run-wide first-hour cancellation

When run-wide cleanup cancels an active owned `WINDOW_1H` because the campaign/run is safely stopping:

- active exact window -> `CANCELLED` with the run stop cause;
- exact owning token slot still in `WINDOW_1H_CONTINUING` -> `MANUAL_REVIEW` with the same cause;
- an already `WINDOW_1H_CLOSED`, `FAILED`, `MANUAL_REVIEW`, or otherwise terminal slot is not rewritten;
- an already terminal window keeps its first cause.

`MANUAL_REVIEW` is used for shared/run-wide interruption because the campaign design distinguishes token-local failure from shared failure and sends shared safe-stop conditions to operator review. Do not mislabel an externally interrupted/blocked shared run as a token-specific market/evidence failure.

## Repair 5 — keep Scheduler/work truth unchanged

Do not change:

- `complete_job()` / `fail_job()` / `cancel_job()` semantics;
- `_sync_owned_campaign_scheduler_job()`;
- Scheduler retry ceilings;
- continuation schedule/cadence;
- active-work accounting.

The terminal reconciliation must occur before the successful close job is committed terminal, so a reconciliation fault cannot leave Scheduler `SUCCEEDED` while campaign window/token truth is stale.

On failure cleanup, preserve the current order in which Scheduler failure and exact pending cancellation are recorded; lifecycle reconciliation must remain token-local and fail closed.

## TDD / focused proof

Create one Checkpoint-6 offline test module. Valid RED must prove state drift using current owners, not synthetic expectations disconnected from real campaign/Scheduler ownership.

Minimum proof:

1. successful current behavior binds the physical 1h row but leaves window `CLOSE_PENDING` and slot `WINDOW_1H_CONTINUING` before repair;
2. clean success -> exact window `CLEAN_PROMOTED`, exact slot `WINDOW_1H_CLOSED`;
3. dirty success -> exact window `DIRTY`, exact slot `WINDOW_1H_CLOSED`;
4. valid close without clean object -> exact window `NO_PROMOTION`, exact slot `WINDOW_1H_CLOSED`;
5. token-local continuation failure -> exact window `BLOCKED`, exact slot `FAILED`, peer unchanged;
6. run-wide cancellation -> active exact window `CANCELLED`, active exact slot `MANUAL_REVIEW`, already completed peer unchanged;
7. exact repeat is idempotent and preserves first terminal cause;
8. conflicting physical row/window/token identity fails without partial lifecycle drift;
9. exact continuation Scheduler job and campaign Scheduler-work row remain terminal after success/failure;
10. zero active first-hour Scheduler work remains;
11. zero `WINDOW_4H` campaign windows and zero long-continuation Scheduler work are created;
12. Checkpoints 1-5 plus directly affected campaign/Scheduler/state regressions remain green.

Use risk-based verification; no full repository suite is required.

## Money-usefulness contribution

The first-hour memory is only operationally useful if its evidence, campaign window, token slot, and Scheduler ownership all agree that the first hour is finished. This repair removes stale active lifecycle state and gives any later 4h policy a trustworthy, exact predecessor boundary.

## What remains locked

No live first-hour execution, fresh authorization/wrapper, standard 1h->4h continuation, 12h/24h, retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events, paper-trade audits, PnL, wallet/private keys/real funds/live execution, paid APIs, scoring/ranking/confidence/weighted logic, embeddings, or vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only.

## Functionality Risks / Setbacks / Efficiency Blockers

- Window and token reconciliation must be one exact ownership transaction; fixing one while leaving the other stale is not acceptable.
- Success classification must use authoritative clean-object/source-window quality, not pipeline convenience fields.
- Shared stop must not become token-specific `FAILED` without token-local failure evidence.
- `MANUAL_REVIEW` on shared stop must apply only to a still-active first-hour slot; completed/terminal peers are immutable.
- The repair must not turn `WINDOW_1H_CLOSED` into implicit 4h permission.
- Nested connection context managers can create unintended commit boundaries; the reconciliation helper must own its transaction explicitly and avoid partial commit between window and token updates.

## Stop condition

After focused RED, implementation, GREEN proof, durable closeout, and exact-closeout-HEAD verification pass, close Checkpoint 6. Only then reassess the roadmap for the standard 1h->4h lifecycle policy audit/design; do not create operational authorization automatically.
