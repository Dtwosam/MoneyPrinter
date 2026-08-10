# Printer V1 V2-9.8B Post-DTW100 Standard Four-Hour Slice B2 Closeout

## Verdict

`V2_9_8B_POST_DTW100_STANDARD_FOUR_HOUR_SLICE_B2_PLANNING_AND_SCHEDULER_OWNERSHIP_PASS`

Slice B2 is complete. The standard two-token 1h->4h campaign handoff can now atomically create exact long-window plans, Central Scheduler jobs, and stage-scoped campaign Scheduler-work ownership without enabling real four-hour collection.

## Baseline and implementation

- B1 closeout baseline: `ad9da64c3d2cbf646a5fdf0655c858e95b17f1fb`.
- B2 RED/test commit: `9bb5fd2ef16cfd549434e01d8ea2538aa2856968` — `Add standard four-hour campaign planning RED tests`.
- B2 production commit: `2492e480d7f207ce8c916c41cee047108bcc6e2f` — `Implement standard four-hour campaign planning`.
- Production implementation changed only:
  - `src/printer_v1/operator_cli/campaign_ownership.py`
  - `src/printer_v1/operator_cli/one_token_4h_runtime.py`

## RED and baseline reconciliation

Disposable B2 RED PR #131 used exact test head `9bb5fd2ef16cfd549434e01d8ea2538aa2856968`.

- workflow run: `31379418743`
- job: `93426001245`
- compile passed;
- B1 and Scheduler-ownership regressions remained healthy;
- the new B2 tests failed because the two-token campaign planning/Scheduler-ownership composer did not yet exist.

The bundle also surfaced one legacy one-token 4h close/E2Z assertion (`E2Z_BLOCKED` vs expected `E2Z_ALREADY_EXISTS`). Disposable baseline PR #132 reproduced the identical failure on exact pre-B2 parent `ad9da64c3d2cbf646a5fdf0655c858e95b17f1fb` in run `31380002602`, job `93427836559`. It is therefore documented as unrelated pre-existing behavior and was not used to expand or weaken B2.

Both disposable PRs were closed unmerged.

## Implementation contract

B2 reuses and narrowly refactors the existing 4h primitives rather than creating a second collector or Scheduler owner.

### Token-scoped planning

`one_token_4h_runtime.py` now exposes a reusable token-scoped 4h planning phase while preserving the historical one-token proof-mode contract.

For the standard two-token campaign path:

- the exact campaign run must match its authoritative factory run;
- exactly two candidates are required;
- plan counts come from the committed cadence policy;
- mixed `TRACK_FAST + TRACK_NORMAL` produces exactly `61 + 31 = 92` long-window jobs;
- each token has exactly one `LONG_CONTINUATION_CLOSE`;
- all Scheduler job identities are distinct;
- pre-existing partial or ambiguous long-window plans fail closed;
- exact full-plan replay is idempotent.

### Exact stage-scoped Scheduler ownership

Every long-window job is projected through the existing canonical campaign Scheduler-work owner with:

- exact campaign/run/cycle;
- exact token slot;
- exact campaign `WINDOW_4H`;
- exact factory run;
- exact Scheduler job id;
- `ownership_contract_version = V2_STAGE_SCOPED`;
- `work_scope = WINDOW_LIFECYCLE`;
- `stage_id = WINDOW_4H`;
- `target_category = CAMPAIGN_WINDOW`;
- exact window target identity;
- work intent matching the long-window run-step kind.

No second Scheduler-work table or ownership system was introduced.

### Final B1+B2 atomic transaction boundary

TDD exposed a real SQLite atomicity defect in the first GREEN attempt: B1's SAVEPOINT could become the outermost SQLite transaction and release/commit successor windows before a later Scheduler-work projection failed.

The final repair keeps the independently proven B1 SAVEPOINT but makes B2 explicitly own the outer transaction:

- B2 requires a clean transaction boundary;
- B2 issues `BEGIN` before invoking B1;
- B1 SAVEPOINT is therefore nested;
- the canonical Scheduler projection owner is transaction-aware and does not commit an already-active caller transaction;
- any planning, enqueue, projection, read-back, or identity failure rolls back campaign windows, slot transitions, long run steps, Scheduler jobs, and campaign Scheduler-work ownership together;
- success commits only after exact full-graph read-back.

No provider call, sleep, or operational source work occurs inside this offline transaction.

## Exact-head proof

Disposable PR #135 tested durable production SHA `2492e480d7f207ce8c916c41cee047108bcc6e2f` directly and was closed unmerged.

- workflow run: `31381322900`
- job: `93431910462`
- exact-head checkout: PASS
- compilation: PASS
- B2 + B1 + Scheduler-ownership focused suite: `52/52 PASS`
- targeted legacy one-token 4h planning contract: `4/4 PASS`
- injected campaign Scheduler-work projection failure fully rolls back all B1+B2 durable state: PASS
- mixed FAST/NORMAL exact `61 + 31 = 92` plan and ownership: PASS
- exact full-plan replay: PASS
- partial-plan fail-closed behavior: PASS
- `WINDOW_4H` real collection remains disabled for FAST and NORMAL: PASS
- `WINDOW_12H` and `WINDOW_24H` real collection remain disabled: PASS
- `git diff --check`: PASS

## Money-usefulness contribution

B2 turns two-token four-hour observation from a proof-shaped one-token plan into exact campaign-owned, Scheduler-owned long-window work. That improves future corpus usefulness for delayed pumps, collapse, revival, second expansion, round trips, distribution, survival, and liquidity deterioration while keeping both tokens attributable and bounded.

It does not establish profitability or authorize any paper action.

## What this slice improves

- supports both otherwise-valid tokens through policy-derived 4h planning;
- preserves exact campaign/Scheduler ownership for every planned long-window job;
- preserves the existing 4h cadence/planning primitives instead of duplicating them;
- closes the B1/B2 partial-commit hazard;
- provides exact replay and partial-plan fail-closed behavior;
- keeps the standard two-token resource shape auditable.

## What remains locked

This PASS does not unlock:

- 4h collection execution;
- source fetching;
- real `WINDOW_4H` collection activation;
- operational runtime or authorization;
- `WINDOW_12H` / `WINDOW_24H`;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions, trades, audits, or PnL;
- wallet, signing, real funds, or live execution.

## Functionality Risks / Setbacks / Efficiency Blockers

- B2 plans and owns long-window work but does not yet prove fair two-token service order during execution.
- Scheduler claim/execution, Source Governor reservation accounting, campaign active-state truth, Scheduler ownership-state synchronization, token-local failure isolation, and shared safe-stop behavior still require the next narrow checkpoint audit/implementation/proof sequence.
- Exact 4h close, E2Q/Lane Q/E2Z campaign composition, and 4h terminal reconciliation remain later checkpoints in the same implementation lane.
- The unrelated historical one-token E2Z replay assertion remains a documented pre-existing baseline failure; it is not a B2 blocker unless a later checkpoint audit proves that exact behavior affects its required path.
- No 12h successor may be created from a 4h close in this lane.

## Next permitted checkpoint

Do not invent a formal `Slice B3` label.

Per the durable handoff and adopted four-hour design, continue with a narrow **4h collection execution/state/accounting current-owner audit** before any further production change.

Audit/reuse at minimum:

- Central Scheduler claim and service-order behavior;
- snapshot execution through the existing collector;
- Source Governor ownership and lifecycle reservation accounting;
- Scheduler ownership-state synchronization;
- truthful campaign `WINDOW_4H` active-state transitions;
- categorical two-token fairness and close priority;
- token-local failure isolation;
- shared safe-stop cancellation/cleanup.

Use the first-hour Checkpoint-3 patterns only where technically applicable. The audit decides the exact blocker and next repair; no real source call, runtime, authorization, real 4h collection, 12h work, retrieval, decision, or financial capability is permitted by this closeout.
