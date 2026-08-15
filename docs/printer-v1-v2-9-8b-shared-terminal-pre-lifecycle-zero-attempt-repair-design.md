# Printer V1 V2-9.8B — Shared-Terminal Pre-Lifecycle Zero-Attempt Repair Design

## Lane identity

- Starting commit: `8fbfb088b70d8849d558f1c8b05f3bb6694958de`
- Required parent anchor: `c7279622247a7e18ff2b29c6ebc63597d4774b92`
- Branch: `agent/v2-9-8b-shared-terminal-pre-lifecycle-repair`
- Prior slot-order/rollback repair is closed and is not reopened.
- Historical execution `20260814T172224Z-490856f405bf` remains preserved; this repair does not mutate or reconcile it.

## Design verdict

`V2_9_8B_SHARED_TERMINAL_PRE_LIFECYCLE_ZERO_ATTEMPT_SHAPE_DESIGN_PASS_READY_FOR_FOCUSED_TDD_REPAIR`

The audit finding is confirmed by focused RED. Current Phase B rejects the legitimate one-Cycle-1 / zero-Cycle-2-attempt shape.

### Safety amendment after RED

Empty tables alone are not strong enough to prove lifecycle phase. The implementation therefore must not infer `CAMPAIGN_PRE_LIFECYCLE` merely from `zero windows + zero Cycle-2 attempts`.

The canonical factory already owns the exact control-flow boundary. It must keep one in-memory witness for Cycle 1:

- initially `opening_completed = False`;
- set `True` immediately after the Cycle-1 `_plan_opening_jobs()` call returns successfully;
- in the terminal `finally:` path, pass `terminal_phase='CAMPAIGN_PRE_LIFECYCLE'` to Phase A only when Cycle 1 is being terminalized while that witness is still false;
- all other Phase-A calls pass no pre-lifecycle phase.

This witness is not itself durable. Phase A converts it into durable provenance only after independently rechecking the exact persisted shape. The combination of positive control-flow witness + structural DB guards is the fail-closed contract.

## Accepted terminal shapes

### `TWO_CYCLE_COMPLETION`

Unchanged: exact cycle ordinals `[1,2]`, both terminal, and all existing zero-active-work/shared-cleanup guards pass.

### `ONE_CYCLE_HONEST_NO_ADMISSION`

Unchanged: exact cycle `[1]` plus exactly one terminal proposed-Cycle-2 pre-admission attempt (`NO_PAIR`/`BLOCKED`/`FAILED`/`CANCELLED`), non-empty immutable cause, and `consumed_cycle_id IS NULL`.

### `ONE_CYCLE_PRE_LIFECYCLE_ZERO_ATTEMPT`

Required Phase-B evidence:

1. exact admitted cycle ordinal list `[1]`;
2. Cycle 1 is terminal;
3. proposed Cycle-2 attempt count exactly zero;
4. no Cycle-2 row;
5. zero Cycle-1 campaign lifecycle windows;
6. exactly one immutable provenance row bound to campaign/run/factory/Cycle 1/proposed Cycle 2;
7. provenance phase exactly `CAMPAIGN_PRE_LIFECYCLE`;
8. provenance cause non-empty and exactly equal to Cycle 1 immutable first terminal cause;
9. all existing active-work, Scheduler-job, factory-step and campaign-active-work guards pass.

Anything missing, duplicated, contradictory or malformed rejects.

## Durable provenance

Add forward-only migration `056_four_token_pre_lifecycle_terminal_provenance.sql` and table:

`printer_four_token_pre_lifecycle_terminal_provenance`

Minimum fields:

- `campaign_id`
- `campaign_run_id`
- `authoritative_factory_run_id`
- `cycle_id`
- `cycle_ordinal` constrained to 1
- `proposed_cycle_ordinal` constrained to 2
- `terminal_phase` constrained to `CAMPAIGN_PRE_LIFECYCLE`
- `first_terminal_cause` non-empty
- `recorded_at` non-empty

Use canonical ownership foreign keys, one composite identity per campaign/run/factory/proposed Cycle 2, exact-shape insert guards, and immutable update/delete triggers.

Migration 056 also adds delete protection to `printer_pre_admission_discovery_attempts`; migration 055 protects identity/cause updates but must not allow an attempt to disappear and later make a zero-attempt shape look legitimate.

## Canonical owners and recording point

Two existing owners cooperate without creating a parallel lifecycle engine:

1. `one_command_15m_factory.py` owns the positive control-flow witness because it owns Cycle-1 opening planning and the terminal `finally:` call to Phase A.
2. `four_token_factory_adapter.py::reconcile_four_token_cycle_terminal()` owns durable provenance because it owns Phase A and immediately precedes the Cycle-1 terminal transition.

Phase A may insert provenance only when:

- caller explicitly supplies `terminal_phase='CAMPAIGN_PRE_LIFECYCLE'`;
- current cycle ordinal is exactly 1;
- run status is not `COMPLETED`;
- campaign/run owns exactly one cycle and it is the supplied Cycle 1;
- Cycle 1 has exactly two slots;
- no Cycle-2 attempt exists;
- no Cycle-2 cycle exists;
- no Cycle-1 campaign window exists;
- cause is non-empty;
- migration 056 exists.

The provenance insert occurs immediately before the canonical Cycle-1 `transition_state()` so the transition owner's transaction commits both together. If any evidence is not exact, no provenance is written and Phase B remains fail closed.

## Always rejected

- one cycle + zero attempts without the explicit factory phase witness having produced durable provenance;
- generic `RUNNER_EXCEPTION` by itself;
- one cycle + zero attempts with any lifecycle window;
- one cycle + zero attempts with Cycle 2 present;
- provenance plus a Cycle-2 attempt row;
- missing/duplicate/mismatched provenance;
- provenance/cycle terminal-cause mismatch;
- malformed cycle ordinals;
- non-terminal admitted cycles;
- active campaign/Scheduler/factory work;
- unknown terminal shapes.

## Focused TDD

RED already proved two intended failures on commit `ae2a90425165e33ecc164b8b7c764748b096ed70` / workflow run `31853811127`:

- current Phase B raises `one-cycle shared terminal requires exact terminal no-admission evidence` for the new shape;
- migration 056 does not exist.

Implementation/GREEN must cover only the minimum risk surface:

- explicit pre-lifecycle factory witness -> Phase-A durable provenance -> Phase-B new shape acceptance;
- zero attempt without provenance still rejects;
- an explicit phase passed after opening completion is impossible from the canonical caller and malformed direct evidence rejects structurally;
- provenance + attempt rejects;
- provenance + window rejects;
- cause mismatch rejects;
- migration valid insert and immutability/delete guards;
- existing two-cycle shared terminal path;
- existing one-cycle honest-no-admission path;
- existing pre-admission callback zero-row failure contract.

No broad suite unless focused evidence proves a wider dependency surface.

## Bounded proof after implementation

Use disposable SQLite only. Prove migration 056 applies, the exact control-flow/Phase-A/Phase-B chain works, contradictory states still reject, and the two existing shapes remain unchanged. No source fetch, discovery run, memory generation, operational scheduler execution, authoritative DB mutation, or fresh authorization.

## Historical reconciliation sequencing

The consumed historical execution predates this provenance owner. Do not silently backfill it during this repair. After repair closeout, a separate reconciliation lane may use the preserved audit/artifact evidence to design and prove an execution-scoped historical reconciliation on a disposable copy before any authoritative mutation.

Fresh authorization may only follow successful cleanup/reconciliation and a new authoritative DB identity.

## Money-usefulness contribution

Prevents a legitimate early-failing bounded four-token proof from stranding durable active ownership and consuming scarce one-shot authority without a clean terminal path. It improves operational recoverability and trust in later memory-growth proofs; it unlocks no trading capability.

## What improves

- truthful pre-lifecycle provenance;
- exact shared-terminal classification;
- recurrence protection for early Cycle-1 failures;
- fail-closed distinction between legitimate zero-attempt termination and corrupt missing history.

## What remains locked

No fresh authorization, operational proof run, six-token widening, 12h/24h activation, retrieval, paper decision, BUY/SELL/HOLD, paper position, trade event, paper audit or PnL is unlocked.

## Functionality Risks / Setbacks / Efficiency Blockers

- Historical residue predates migration 056 and remains a separate reconciliation problem.
- A broad `one cycle + zero attempts = valid` fallback remains forbidden.
- Migration 056 adds a small schema surface, kept single-purpose and immutable.
- The explicit runtime witness must remain owned by the canonical factory; duplicating it elsewhere would create phase drift.
- All repair proof remains offline/disposable; connected GitHub access is not authority to mutate the operational database.

## Next lane

Focused TDD repair -> focused GREEN -> disposable proof -> repair closeout. Stop before historical reconciliation or fresh operational authorization.
