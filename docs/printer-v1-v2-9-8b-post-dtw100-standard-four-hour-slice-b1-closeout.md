# Printer V1 V2-9.8B Post-DTW100 Standard Four-Hour Slice B1 Closeout

## Verdict

`V2_9_8B_POST_DTW100_STANDARD_FOUR_HOUR_SLICE_B1_CAMPAIGN_HANDOFF_PASS`

Slice B1 is complete. It implements and proves the exact two-token campaign-ownership handoff from genuine clean `WINDOW_1H` predecessors into planned `WINDOW_4H` successors. It does not provide operational four-hour execution authority.

## Baseline and implementation

- RED baseline: `8b9b1226d641018857672b86dd08b154c0e4bde9` — `Add standard four-hour campaign handoff RED tests`
- Implementation: `ba58873d6b87d3be79294fef4037c70a77073f60` — `Implement standard four-hour campaign handoff`
- Production implementation changed only `src/printer_v1/operator_cli/campaign_ownership.py`.

## RED validation

Disposable PR #125 used runner-base `04a134482e967ee000a2b8d90ff99759c1d523e5`.

- workflow run: `31374351247`
- job: `93410117593`
- compile passed;
- existing Checkpoint 1/4/6 coverage remained healthy;
- exactly two new failures were caused by the intentionally missing `persist_standard_four_hour_handoff_set` owner;
- no fixture, import, SQL, runner, or infrastructure defect was accepted as RED.

PR #125 was closed unmerged.

## Implementation contract

`persist_standard_four_hour_handoff_set` now:

- requires the exact two campaign token slots;
- verifies exact campaign/run/cycle/slot/token/mint/pair/lifecycle identity;
- requires each exact campaign predecessor to be `WINDOW_1H` + `CLEAN_PROMOTED` and bound to its exact physical first-hour memory;
- requires the physical first-hour row and clean episode to be genuine, clean, eligible, and identity-matched;
- derives the successor deadline from the existing `WINDOW_4H` cadence policy;
- creates exactly two `WINDOW_4H` campaign rows in `PLANNED` with exact predecessor lineage and `memory_window_row_id=NULL`;
- advances both slots `WINDOW_1H_CLOSED -> WINDOW_4H_CONTINUING`;
- fails closed and rolls back the whole two-token handoff if either predecessor or identity is invalid;
- makes exact replay idempotent and rejects partial or conflicting replay;
- uses a SAVEPOINT so Slice B2 can compose this ownership primitive inside a later caller-owned transaction.

It creates no Scheduler work and performs no source work.

## GREEN verification

### Focused implementation proof

- workflow run: `31378303477`
- job: `93422486322`
- exact starting SHA: `8b9b1226d641018857672b86dd08b154c0e4bde9`
- compile: PASS
- focused suite: `59/59 PASS`
- `git diff --check`: PASS
- explicit `TRACK_FAST` and `TRACK_NORMAL` checks confirmed `WINDOW_4H.enabled_for_real_collection == False`.

The run committed only the production file and pushed implementation SHA `ba58873d6b87d3be79294fef4037c70a77073f60`.

### Independent exact-head proof

Disposable PR #130 tested the durable implementation head directly.

- exact head: `ba58873d6b87d3be79294fef4037c70a77073f60`
- workflow run: `31378637109`
- job: `93423533252`
- compile: PASS
- B1 + Checkpoint 6 + Checkpoint 1 suite: `21/21 PASS`

PR #130 was closed unmerged.

## Money-usefulness contribution

This slice gives both otherwise-valid selected tokens durable, exact campaign ownership into the standard four-hour observation path. That enables later campaign integration to preserve broader first-four-hour behavior such as continuation, collapse, revival, distribution, and manipulation context without using behavior labels as continuation qualifiers.

## What remains locked

B1 does not unlock source fetching, Scheduler/runtime execution, real four-hour collection, `WINDOW_12H`, `WINDOW_24H`, retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events, paper-trade audits, PnL, wallets, signing, or real funds.

`WINDOW_4H` real collection remains disabled.

## Functionality Risks / Setbacks / Efficiency Blockers

B1 is not the final operational 1h-to-4h atomic boundary. A campaign window and slot must never become operationally committed without the matching long-window run-step plan, Scheduler jobs, and stage-scoped campaign Scheduler-work ownership. Slice B2 must compose those objects with this B1 primitive inside one fail-closed caller-owned transaction and verify exact read-back counts. No nested early commit may split that boundary.

## Next permitted slice

`Slice B2 — two-token long-window planning + exact stage-scoped Scheduler ownership`.

B2 remains offline/TDD implementation work only. Real four-hour collection remains locked after B2 until the later approved proof, closeout, rereadiness, activation, and authorization sequence passes.
