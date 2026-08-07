# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — DTW-46 Repair Readiness Decision

Date: 2026-08-07

Design HEAD: `e1c29324c923e4c5d2391a8e39b5ce51c4022886`

Repair commit: `275a9731556b889237895d4a2a808a057a144a1e`

Repair closeout commit: `3f34c3090598a3d070d15285b248b102b44d760f`

## Independent review verdict

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_DTW_46_REPAIR_CLOSEOUT_INDEPENDENT_REVIEW_PASS`

## Independent review findings

GitHub verification confirms:

- repair commit `275a973...` is exactly one commit ahead of design HEAD `e1c293...`;
- the repair commit changes exactly two files:
  1. `scripts/v2_9_8b_checkpoint8_controlling_public_composition_proof.py`
  2. `tests/test_v2_9_8b_window_15m_checkpoint8_real_consumer_compatibility.py`;
- no `src/printer_v1/` production code changed;
- the proof-only helper serializes one measured transport identity with existing measured-transport primitives;
- all four approved permanent-market fixture seams use route-correct stage/source/request semantics;
- the focused regression exercises those four seams through the canonical DexScreener/GeckoTerminal adapters and requires exactly one surviving identity plus zero process-local network attempts.

The local isolated proof evidence supplied for the repair records:

- deterministic RED: `TRANSPORT_IDENTITIES_MISSING` with `transport_operations_used=1` and an empty identity tuple;
- changed-file `py_compile`: PASS;
- focused compatibility: `6 passed`;
- full focused Checkpoint 8 suite: `97 passed`;
- network tripwire: zero;
- `git diff --check`: PASS;
- exact two-file manifest: PASS;
- no controlling proof run.

The closeout commit `3f34c309...` is exactly one documentation-only commit after the repair and adds only the DTW-46 repair closeout document. Its claims match the design, repair diff, and supplied local proof evidence.

## Readiness decision

DTW-46 is ready to close.

The independent-review prerequisite for considering a later Checkpoint 8 re-proof authorization is satisfied.

**No Checkpoint 8 controlling proof is authorized by this decision.** Any later proof still requires a separate explicit operator authorization and must start from the then-current verified repository state.

Checkpoint 8 itself remains open.

## Money-usefulness contribution

This removes the known proof-fixture identity blocker without weakening production accounting, allowing a future separately authorized Checkpoint 8 campaign to test useful permanent-market evidence under the canonical measured transport contract.

## What remains locked

No `WINDOW_1H+`, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL are unlocked.

## Functionality Risks / Setbacks / Efficiency Blockers

- The next authorized campaign may reveal a different downstream blocker; treat any such blocker as a new audit subject rather than extending DTW-46 scope.
- This review verifies the repository diff and consistency of the supplied local proof evidence; it does not substitute for a future controlling campaign.
- Checkpoint 8 remains incomplete until its separately authorized controlling campaign and required independent inspection/closeout pass.
