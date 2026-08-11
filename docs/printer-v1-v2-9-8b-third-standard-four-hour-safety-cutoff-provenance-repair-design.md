# Printer V1 V2-9.8B — Third Standard Four-Hour Safety Cutoff / Provenance Repair Design

## Verdict

`V2_9_8B_THIRD_STANDARD_FOUR_HOUR_SAFETY_CUTOFF_PROVENANCE_REPAIR_DESIGN_PASS`

## Baseline

Audit closeout: `d1f57145ca719223502d6521cb4881532530e1b8`.

Primary defect: `COMMITTED_CODE_DEFECT_AT_FIXED_FIRST_HOUR_CUTOFF_VS_OBSERVED_CLOSE_SAFETY_EVIDENCE_BOUNDARY`.

The third consumed attempt proved that a valid Scheduler-owned `CONTINUATION_CLOSE` can collect fresh safety and capture its final exact-pair snapshot a few seconds after the fixed 15m-close + 2700s lifecycle deadline. B.2 currently treats that earlier lifecycle deadline as the evidence cutoff and therefore rejects the exact fresh evidence it was designed to consume.

## Chosen design

Preserve two independent authoritative timestamps:

1. **Lifecycle deadline** — `printer_memory_windows.window_end_at`; remains the fixed 15m close + 2700s boundary and remains the value the standard-4h caller must supply as `memory_window_close_cutoff`.
2. **Observed close-evidence cutoff** — `printer_token_snapshots.captured_at` for the exact `printer_memory_windows.snapshot_end_id`.

For `load_authoritative_window_safety(..., memory_window_close_cutoff=...)`:

- continue requiring the supplied lifecycle cutoff to exactly equal authoritative `window_end_at`;
- load the exact closing snapshot identified by `snapshot_end_id`;
- require that snapshot to belong to the same token and pair as the memory window/campaign graph;
- require the closing snapshot timestamp to parse;
- require the observed close timestamp to be **at or after** the lifecycle deadline; otherwise fail closed because the close snapshot would precede the fixed lifecycle boundary;
- use the exact closing snapshot `captured_at` as the evidence/provenance cutoff for the bound safety composite and its source traces;
- keep `MAX_AGE_SECONDS == 1800`, source trace correspondence, target/pair/mint identity, exact composite ID, exact snapshot ID, freshness labels, source status, data quality, rejection reason, response-request identity, and failure-source identity unchanged;
- return both timestamps explicitly so audit output cannot confuse them.

Checkpoint-based B.2 behavior remains unchanged. Only the exact memory-window close path receives observed-close cutoff semantics.

## Why this design

This is narrower and safer than moving provider work earlier. It requires no new Scheduler job, no new provider call, no budget change, no cadence change, and no producer rewrite. The already-approved producer continues to collect fresh safety during the Scheduler-owned close and bind it to the exact closing snapshot.

The repair does not add a grace period. Evidence is valid only up to the timestamp of the exact closing snapshot already bound to the memory window. Evidence after that snapshot still fails closed.

## Production scope

Modify only:

- `src/printer_v1/operator_cli/campaign_authority_adapters.py`

Add focused proof:

- `tests/test_v2_9_8b_third_standard_four_hour_safety_cutoff_provenance_repair.py`

No migration, schema change, Source Governor change, Scheduler change, request-ceiling change, authorization change, or runtime change.

## Required focused proof

The test must prove:

1. lifecycle deadline `T`, closing snapshot `T+5s`, and fresh governed safety trace at/before `T+5s` can pass B.2;
2. caller still must supply exactly `window_end_at == T`;
3. evidence or trace after the exact closing snapshot fails closed;
4. evidence older than 1800 seconds fails closed;
5. wrong closing snapshot/token/pair identity fails closed;
6. wrong source trace/request-response identity still fails closed;
7. checkpoint B.2 semantics remain unchanged;
8. no request/Scheduler budget changes are introduced.

Use minimum sufficient risk-based verification. No live provider call, Scheduler runtime, DB mutation outside test fixtures, memory generation, authorization, or standard-four-hour attempt is part of this proof.

## Money-usefulness contribution

Removes a deterministic false block at the 1h→4h learning boundary without making genuinely stale, future, mismatched, or untraceable safety evidence easier to pass.

## What remains locked

No new standard-four-hour attempt, authorization, 12h/24h, retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events, paper-trade audits, PnL, wallet/private keys/signing/real funds/live execution, paid APIs, scoring/ranking/confidence/weighted logic, embeddings, or vectors.

## Functionality Risks / Setbacks / Efficiency Blockers

- **Future-data leakage:** prevented by binding the cutoff to the exact closing snapshot, never wall-clock grace.
- **Lifecycle-duration drift:** prevented by retaining `window_end_at` as the fixed deadline and continuing to validate the caller against it.
- **Identity drift:** prevented by exact closing-snapshot token/pair and composite snapshot checks.
- **Broad repair drift:** prevented by modifying only the B.2 memory-window adapter and focused tests.

## Next lane

If this design is accepted, the next lane is:

`THIRD_STANDARD_FOUR_HOUR_SAFETY_CUTOFF_PROVENANCE_REPAIR_IMPLEMENTATION`

Required sequence after implementation: focused bounded offline proof -> implementation closeout -> fresh operational rereadiness. No authorization or live attempt before rereadiness closes PASS.