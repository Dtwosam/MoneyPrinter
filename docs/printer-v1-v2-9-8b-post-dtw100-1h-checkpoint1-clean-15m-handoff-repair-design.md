# Printer V1 V2-9.8B Post-DTW100 WINDOW_1H Checkpoint 1 — Strict Atomic Handoff Repair Design

## Design verdict

`V2_9_8B_POST_DTW100_1H_CHECKPOINT_1_STRICT_ATOMIC_HANDOFF_REPAIR_DESIGN_PASS`

This design repairs only the ownership inconsistency proven by the Checkpoint-1 audit. It does not redesign first-hour collection, cadence, memory closeout, Source Governor, Central Scheduler, or clean-memory quality rules.

## Canonical owner

The atomic persistence boundary belongs in:

`src/printer_v1/operator_cli/campaign_ownership.py`

The orchestration caller remains:

`src/printer_v1/operator_cli/operational_selective_1h.py`

No new runner, scheduler, source adapter, memory engine, table, migration, or parallel ownership map is permitted.

## Required behavior

### 1. Read-only preflight before handoff evaluation side effects

Immediately after loading the two campaign token slots, the operational owner must require each slot to be in one legitimate pre-handoff prefix state:

- `SELECTED`
- `WINDOW_15M_ACTIVE`
- `WINDOW_15M_CLOSED`

Any `WINDOW_1H_CONTINUING`, `WINDOW_1H_CLOSED`, 4h state, terminal/disposition state, or unknown value is an ownership conflict and must raise before continuation objects or successor windows are created.

This compatibility set exists because current campaign bookkeeping may still reach the handoff with the slot at any already-established 15m prefix state; the repair advances the state honestly rather than pretending it was already advanced.

### 2. One atomic first-evaluation persistence transaction

Add one narrow composite function to `campaign_ownership.py` for the first authoritative standard-first-hour evaluation.

The function receives the complete two-token candidate set produced by the existing pure continuation evaluator. In one SQLite transaction it must:

1. verify exactly two candidates and exactly the expected two token slots;
2. revalidate campaign/run/cycle/token/pair/lifecycle identity;
3. revalidate each slot's allowed pre-handoff state;
4. verify each candidate's exact predecessor `WINDOW_15M` campaign-window ownership row and root lifecycle;
5. persist both immutable `CONTINUATION_4A` objects using the existing canonical JSON/hash contract;
6. for each `CONTINUE_TO_WINDOW_1H` candidate only:
   - require a deterministic successor id;
   - require that no successor already exists on a first evaluation;
   - insert the exact `WINDOW_1H` campaign-window ownership row with the same root 15m lifecycle and exact predecessor id;
   - advance the token slot, inside the same transaction, through any remaining valid prefix states until `WINDOW_1H_CONTINUING`;
7. for a hard-block candidate, create no `WINDOW_1H` successor and do not advance it into 1h;
8. read back the complete two-object set and every expected successor/final token state;
9. rollback the entire first-evaluation persistence transaction on any conflict.

The composite lives inside the existing campaign-ownership module so it is reuse of the canonical owner, not copy/paste duplication.

### 3. No swallowed ownership errors

Remove the current post-persistence `try/except CampaignOwnershipError: pass/continue` state advancement path from `operational_selective_1h.py`.

An ownership conflict must be visible and fail closed.

### 4. Replay remains unchanged

When the immutable two-object evaluation already exists and hashes/payloads match, the current replay/idempotent path remains read/verify-only. It must not call the first-evaluation atomic writer or create another successor.

### 5. No policy change

This repair must not change:

- standard `WINDOW_15M -> WINDOW_1H` continuation for otherwise-valid tokens;
- B.1 canonical clean-object authority;
- B.2 safety rules;
- exact continuity requirements;
- 1h cadence or 2700-second continuation duration;
- Source Governor or Central Scheduler ownership;
- `WINDOW_1H -> WINDOW_4H` selectivity;
- 5m support-only status;
- any retrieval/paper/financial lock.

## TDD proof contract

### RED

Before implementation, extend the current operational first-hour harness to require:

1. successful quiet-token handoff leaves both token slots at `WINDOW_1H_CONTINUING`;
2. each successor row preserves exact token/pair/root-lifecycle/predecessor identity;
3. forcing one token slot into a conflicting state before first evaluation raises and leaves:
   - zero `CONTINUATION_4A` objects;
   - zero `WINDOW_1H` campaign windows;
   - the other token unadvanced.

The current implementation is expected to fail at least the conflicting-state/no-side-effect proof because it swallows transition errors after persisting objects/windows.

### GREEN

Run the minimum sufficient offline proof:

- the changed operational first-hour test module;
- the existing standard-first-hour alignment module;
- compilation of `campaign_ownership.py` and `operational_selective_1h.py`;
- diff/scope review.

Broad repository regression is not required for this narrow repair unless the focused evidence exposes a directly related failure.

## Money-usefulness contribution

This repair makes the handoff trustworthy enough that a later 1h memory can be attributed to the exact same token lifecycle that produced the clean 15m predecessor. It prevents silent lifecycle divergence from contaminating trajectory learning.

## What this repair improves

- exact successor ownership;
- token-state truthfulness;
- atomic two-token first-evaluation persistence;
- fail-closed behavior on campaign-state conflicts;
- reuse of the proven campaign-ownership architecture.

## What remains locked

Everything beyond Checkpoint 1 remains locked, including real first-hour execution, one-use authorization, remaining-45m readiness, 1h closeout readiness, 4h activation, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, and PnL.

## Functionality Risks / Setbacks / Efficiency Blockers

- The atomic writer must not alter generic campaign-ownership behavior used by the proven 15m path.
- The repair must not convert token-local hard blocking into a campaign-wide policy decision; only ownership-integrity faults raise.
- First-evaluation atomicity must cover both continuation objects and any successor windows/states; otherwise a new partial-state class would remain.
- Existing replay semantics must stay idempotent.

## Stop condition

After implementation and focused proof, close Checkpoint 1. Do not begin Checkpoint 2 unless the exact implementation head proves the complete handoff contract above.
