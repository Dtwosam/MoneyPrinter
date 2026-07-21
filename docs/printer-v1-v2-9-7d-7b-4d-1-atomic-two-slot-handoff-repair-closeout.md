# V2-9.7D.7B.4D.1 Atomic Two-Slot Handoff Repair Closeout

**Status:** PASS
**Lane:** V2-9.7D.7B.4D.1
**Boundary:** initial activation handoff atomicity repair only
**Date:** 2026-07-21

PASS means initial two-slot discovery activation is transactionally two-or-none.
It does not unlock live providers, public commands, 7B.5, pilot, retrieval, or
financial capability.

## Todo / Checklist

- [x] Verify exact starting commit `65393d8484369ed61f4c3ad2d2c11c9d4444ebc9`.
- [x] Read 7B.2 design, 4D closeout, executor, and migration 034 owners.
- [x] Repair initial handoff into one SAVEPOINT-backed atomic boundary.
- [x] Preserve replacement as token-local and healthy-slot safe.
- [x] Add focused synthetic rollback proofs.
- [x] Rerun 4D, 4C, and 7A regressions.
- [x] Write this closeout and commit only on PASS.

## Root Cause

The 4D combined executor performed initial slot handoffs sequentially. The first
slot could mutate tracking queue, first `WINDOW_15M` job, and slot ownership
before the second handoff completed. Failure on the later handoff depended on
outer-transaction rollback discipline and left a documented risk that one slot
could remain filled, violating approved initial activation:

- select exactly two or none;
- no partial active campaign;
- no one-token initial activation.

## Exact Repair

In `src/printer_v1/discovery/combined_executor.py`:

1. **Preflight both vacancies** before any initial-activation mutation:
   exactly two selected candidates, vacancies `[1,2]`, confirmed origin,
   market identity, scheduler/handoff ceiling headroom, and no healthy
   conflicting slots.
2. **Create handoff work rows** for both slots first (first-fault visible).
3. **Open `SAVEPOINT initial_two_slot_handoff`**.
4. Inside the savepoint, insert selection batch/links and perform both slot
   assignments, tracking-queue handoffs, and first `WINDOW_15M` job links.
5. **Release** only when both handoffs succeed.
6. On any failure: **`ROLLBACK TO SAVEPOINT`**, restore handoff counters,
   terminalize both handoff work rows as `FAILED` with the exact first cause,
   mark the discovery batch `TERMINAL_FAILED`, and return a failed 7A result
   without leaving activation rows.
7. Replacement remains token-local: only the vacant ordinal is attempted; a
   healthy occupied slot is never selected as the target and is not mutated on
   vacancy failure.

No migration was required. Migration 034 already supports the needed links;
atomicity is an executor transaction boundary issue, not a schema gap.

## Transaction Boundary

| Region | Contents |
|---|---|
| Outside savepoint | Discovery intake, merge, gates, selection seed evaluation, handoff work-row creation |
| Inside savepoint | Selection batch, selected-item links, token/pair creation when needed, tracking queue rows, first WINDOW_15M jobs, campaign token slots for both ordinals |
| After failed savepoint | Batch `TERMINAL_FAILED`, handoff work `FAILED`, discovery observations retained |

Outer `execute()` still commits the final connection state. For initial handoff
faults the savepoint has already removed partial activation, so commit persists
failed discovery state without slots/queue/15m jobs.

## Rollback Behavior

Forced and natural initial-activation failures leave:

- zero campaign token slots for the cycle;
- zero tracking-queue rows from the handoff;
- zero `TRACK_NORMAL_FIRST_15M` jobs from the handoff;
- zero selected-item / selection-batch activation links;
- exact first failure cause on the discovery batch and handoff work rows;
- no automatic retry.

## Replacement-Flow Behavior

Replacement mode:

- targets only reconciled vacant ordinals;
- refuses healthy-slot mutation;
- fails the vacancy handoff without rewriting the healthy occupied slot;
- does not use the two-slot atomic savepoint (token-local failure domain).

## Tests

New focused module:

`tests/test_v2_9_7d_7b_4d_1_atomic_two_slot_handoff.py` — 8 passed

Proved:

1. successful initial activation commits both slots, queues, and 15m jobs;
2. failure before first handoff leaves both vacant;
3. failure during second rolls back the first completely;
4. second Scheduler-job failure rolls back both slots and queues;
5. duplicate active work causes full rollback;
6. conflicting slot state causes full rollback;
7. replacement failure leaves healthy occupied slot unchanged;
8. no 1h/4h/5m jobs; locked financial tables remain zero; Windows SQLite closes.

Regressions:

- `tests/test_v2_9_7d_7b_4d_combined_discovery_executor.py` — passed
- `tests/test_v2_9_7d_7b_4c_discovery_persistence.py` — passed
- `tests/test_v2_9_7d_7a_abstract_command_surface.py` — passed

Total focused run: **30 passed**.

`git diff --check` — PASS.

## Exact Files Changed

- `src/printer_v1/discovery/combined_executor.py`
- `tests/test_v2_9_7d_7b_4d_1_atomic_two_slot_handoff.py` (new)
- `docs/printer-v1-v2-9-7d-7b-4d-1-atomic-two-slot-handoff-repair-closeout.md` (new)

## Remaining Risks

- Discovery intake remains outside the handoff savepoint by design so failed
  activation can still audit observations. If a future requirement needs full
  cycle wipe on handoff failure, that would be a separate contract change.
- Replacement multi-vacancy cases still hand off vacancies sequentially; only
  initial two-slot activation is fully atomic. A future replacement multi-fill
  path would need its own token-local transaction policy.
- SAVEPOINT behavior depends on SQLite nested-transaction semantics already
  used by Printer on Windows; no migration was required.

## What Remains Locked

- 7B.5 isolated combined proof;
- live RPC/provider calls, secrets, public commands;
- operational campaign activation and pilot;
- retrieval, paper decisions, BUY/SELL/HOLD;
- positions, trades, audits, PnL;
- wallets, signing, live execution, paid APIs, scoring/ranking/embeddings;
- `WINDOW_5M_MICRO_EVENT` remains support-only;
- no 1h/4h continuation from discovery.

## Functionality Risks / Setbacks / Efficiency Blockers

- Handoff work rows and Scheduler discovery jobs for failed initial activation
  remain as failed audit rows; they intentionally do not activate tracking.
- Full multi-provider cycles still consume the 11-work intake ceiling; atomic
  repair did not expand capacity.
- Forced-fault injection hooks exist only for fixture proof and must not be
  used as runtime control surfaces.
- Idempotent re-execution of a completed cycle still fails closed on unique
  ownership constraints; this repair does not introduce silent overwrite.

## Stop Boundary

V2-9.7D.7B.4D.1 stops at atomic initial two-slot handoff repair, focused
proofs, and this closeout. `V2-9.7D.7B.5`, live-source proof, V2-9.7D closeout,
and the pilot have not begun.

## Final Lane Result

`V2_9_7D_7B_4D_1_ATOMIC_TWO_SLOT_HANDOFF_REPAIR_PASS`
