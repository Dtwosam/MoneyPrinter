# Printer V1 V2-9.8B — Shared-Terminal Pre-Lifecycle Zero-Attempt Repair Design

## Lane identity

- Starting commit: `8fbfb088b70d8849d558f1c8b05f3bb6694958de`
- Required parent anchor: `c7279622247a7e18ff2b29c6ebc63597d4774b92`
- Branch: `agent/v2-9-8b-shared-terminal-pre-lifecycle-repair`
- Scope: repair design only at this commit.
- Prior slot-order/rollback repair is closed and is not reopened.
- Historical execution `20260814T172224Z-490856f405bf` remains preserved; this design does not mutate or reconcile it.

## Design verdict

`V2_9_8B_SHARED_TERMINAL_PRE_LIFECYCLE_ZERO_ATTEMPT_SHAPE_DESIGN_PASS_READY_FOR_FOCUSED_TDD_REPAIR`

The post-repair audit finding is confirmed in committed code. `finalize_four_token_shared_terminal()` accepts a one-cycle terminal only when exactly one terminal Cycle-2 pre-admission attempt row exists. A legitimate Cycle-1 pre-lifecycle terminal can have one admitted Cycle-1 row, no Cycle-2 row, no Cycle-2 attempt row, and no lifecycle windows. That exact shape currently fails Phase B.

## Existing accepted shapes

### 1. `TWO_CYCLE_COMPLETION`

Keep unchanged:

- exact admitted cycle ordinals `[1, 2]`;
- both cycles terminal before shared cleanup;
- zero active campaign work/jobs;
- zero running factory steps;
- clean campaign-active-work report.

### 2. `ONE_CYCLE_HONEST_NO_ADMISSION`

Keep unchanged:

- exact admitted cycle ordinal `[1]`;
- exactly one proposed-Cycle-2 pre-admission attempt;
- attempt state is one of `NO_PAIR`, `BLOCKED`, `FAILED`, `CANCELLED`;
- immutable terminal cause exists;
- `consumed_cycle_id IS NULL`;
- Cycle 1 is terminal;
- all existing zero-active-work and shared-cleanup guards pass.

## New accepted shape

### 3. `ONE_CYCLE_PRE_LIFECYCLE_ZERO_ATTEMPT`

This shape must be narrower than `one cycle + zero attempts`.

Required evidence at Phase B:

1. exact admitted cycle ordinal list is `[1]`;
2. Cycle 1 is terminal;
3. proposed Cycle-2 attempt count is exactly zero;
4. Cycle-2 cycle count is exactly zero;
5. Cycle-1 lifecycle-window count is exactly zero;
6. exactly one immutable provenance row exists for the same campaign, campaign run, authoritative factory run, Cycle 1 and proposed Cycle 2;
7. provenance phase is exactly `CAMPAIGN_PRE_LIFECYCLE`;
8. provenance terminal cause is non-empty and exactly equals Cycle 1's immutable first terminal cause;
9. all existing active-work, Scheduler-job, factory-step and shared-cleanup guards pass.

If any condition is absent, duplicated, contradictory or malformed, Phase B must reject.

## Durable provenance owner

Existing tables do not safely own this fact:

- supervision owns process/campaign supervision, not admission-phase provenance;
- heartbeat evidence owns liveness failure evidence;
- factory `stop_reason` and cycle `first_terminal_cause` own cause, not lifecycle phase;
- the pre-admission attempt ledger owns a real Scheduler-governed Cycle-2 discovery/selection opportunity and must not receive a fabricated synthetic attempt.

Add forward-only migration `056_four_token_pre_lifecycle_terminal_provenance.sql` with one dedicated immutable table:

`printer_four_token_pre_lifecycle_terminal_provenance`

Minimum identity/evidence fields:

- `campaign_id`
- `campaign_run_id`
- `authoritative_factory_run_id`
- `cycle_id`
- `cycle_ordinal` constrained to `1`
- `proposed_cycle_ordinal` constrained to `2`
- `terminal_phase` constrained to `CAMPAIGN_PRE_LIFECYCLE`
- `first_terminal_cause` non-empty
- `recorded_at` non-empty

Use one composite primary/unique identity per campaign/run/factory/proposed Cycle 2, canonical ownership foreign keys, an insert guard proving the exact one-cycle/zero-attempt/zero-window shape, and immutable update/delete triggers.

Migration 056 must also add a delete-protection trigger to `printer_pre_admission_discovery_attempts`. Migration 055 already makes attempt identity and first terminal cause immutable but does not forbid deletion of the attempt row itself. Future zero-attempt classification must not become valid merely because an earlier attempt row disappeared.

## Provenance recording point

The smallest canonical production owner is Phase A in `four_token_factory_adapter.py`, not the discovery callback and not the outer launcher.

Before Cycle 1 is transitioned terminal, `reconcile_four_token_cycle_terminal()` may record the provenance row only when all of the following are true in the same transaction:

- current cycle ordinal is exactly 1;
- run status being reconciled is not `COMPLETED`;
- the campaign/run owns exactly one cycle and it is Cycle 1;
- there is no Cycle-2 pre-admission attempt;
- there is no Cycle-2 cycle;
- there are zero campaign lifecycle windows for Cycle 1;
- terminal cause is non-empty;
- migration 056 table exists.

The provenance insert and Cycle-1 terminal transition must commit atomically. If the evidence is not exact, no provenance row is written and existing Phase B fail-closed behavior remains.

This avoids changing the main factory orchestration merely to carry a shadow phase flag and keeps classification evidence next to the Phase A/B owner that consumes it.

## Rejected shapes

Always reject:

- one cycle + zero attempts without provenance;
- one cycle + zero attempts with any lifecycle window;
- one cycle + zero attempts with a Cycle-2 cycle;
- one cycle + zero attempts with duplicate/mismatched provenance;
- provenance whose cause differs from Cycle 1 terminal cause;
- provenance plus any Cycle-2 attempt row;
- generic `RUNNER_EXCEPTION` without the exact structural provenance contract;
- malformed cycle ordinals;
- non-terminal admitted cycles;
- active campaign work, active Scheduler jobs or running factory steps;
- unknown terminal shapes.

## Focused TDD repair

### RED tests

Minimum new failures before production implementation:

1. exact one-cycle, zero-attempt, zero-window pre-lifecycle provenance shape should terminalize as `ONE_CYCLE_PRE_LIFECYCLE_ZERO_ATTEMPT` — must fail on the current implementation;
2. one-cycle + zero attempts + no provenance remains rejected;
3. provenance plus an attempt row is rejected;
4. provenance plus a lifecycle window is rejected;
5. provenance/cycle terminal-cause mismatch is rejected;
6. migration valid insert succeeds only for the exact shape;
7. invalid provenance inserts fail;
8. provenance update/delete fail;
9. pre-admission attempt deletion fails after migration 056.

### GREEN regressions

Run only the nearest existing coverage needed to protect the change:

- two-cycle shared terminal path;
- one-cycle honest no-admission path;
- Phase-A-before-Phase-B sequencing;
- pre-admission callback zero-row failure contract;
- migration ordering/integrity around 055/056.

Do not broaden to unrelated suites unless a focused failure proves the dependency surface is wider.

## Bounded proof after implementation

After focused GREEN, use only an offline/disposable SQLite database. Prove:

- migration 056 applies forward-only;
- Phase A atomically creates provenance only for the exact pre-lifecycle shape;
- Phase B accepts that exact new shape;
- missing/contradictory evidence still fails closed;
- existing two-cycle and honest-no-admission shapes remain accepted;
- no source fetch, discovery run, memory generation, operational scheduler execution or authoritative DB mutation occurs.

## Historical reconciliation sequencing

The implementation must not rewrite the consumed historical execution.

After repair closeout, a separate reconciliation lane may assess `20260814T172224Z-490856f405bf` against its preserved audit evidence. Because that execution predates migration 056, no new provenance may be silently inferred during this repair. Any historical provenance/backfill required for reconciliation must be explicit, narrowly justified by the completed audit, and proved on a disposable copy before authoritative mutation.

Fresh authorization can only follow successful historical cleanup/reconciliation and a new authoritative DB identity.

## Money-usefulness contribution

This repair prevents legitimate bounded four-token campaigns that fail before lifecycle start from leaving abandoned active ownership. Reliable terminal cleanup reduces operator recovery work and makes later memory-growth proofs more trustworthy; it does not itself create trading capability or financial decisions.

## What this improves

- exact shared-terminal classification;
- durable distinction between legitimate pre-lifecycle zero-attempt termination and ambiguous missing attempt history;
- terminal cleanup reliability;
- future recoverability of bounded four-token operations.

## What remains locked

No new authorization, operational proof run, six-token widening, 12h/24h activation, retrieval, paper decision, BUY/SELL/HOLD, paper position, trade event, trade audit or PnL is unlocked by this repair.

## Functionality Risks / Setbacks / Efficiency Blockers

- The historical residue predates migration 056 and therefore still needs a separate reconciliation design/proof after this repair closes.
- Any broad fallback such as `one cycle + zero attempts = valid` would weaken fail-closed ownership and is forbidden.
- A schema addition increases migration surface slightly; keeping it additive, single-purpose and immutable is the smallest safe durable solution.
- Current connected environment does not imply authorization to mutate the authoritative SQLite database; all implementation proof remains offline/disposable.

## Next lane

Focused TDD repair only: RED -> minimal migration/adapter implementation -> focused GREEN -> disposable proof -> repair closeout. Stop before historical reconciliation or fresh operational authorization.
