# Printer V1 Handoff

## Current verified implementation

Branch: `assistant/v2-9-8b-later-cycle-mint-market-replay-repair`.

The 2026-09-11 four-token Standard-4H operational attempt used authorization
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260911T082442Z_98f7588c` on HEAD
`599e13f76af3ac2222649a66fca7cd37a5adab10`. It is terminal, cleanup completed,
the lease was released, and Scheduler locked/pending/running work is zero. The
authorization is consumed and permanently non-reusable.

## Current capability

Printer V1 remains Solana-only, memecoin-only, paper-only. Source Governor is
the sole governed source-request owner and Central Scheduler the sole scheduler
owner. `WINDOW_5M_MICRO_EVENT` remains support-only; `WINDOW_12H` and
`WINDOW_24H` remain locked. Retrieval, decision, position, PnL, wallet, signing
and live trading capabilities remain locked.

## Latest meaningful result

The failed 2026-09-11 attempt proved two coordination defects and both are now
repaired at code/test level.

1. Terminal precedence: Cycle 1 could have canonical successful 15m accounting
   while the shared factory had already persisted a campaign-wide non-completion
   stop such as `LATER_CYCLE_ADMISSION_DEADLINE_EXHAUSTED`. Reconciliation now
   honors that persisted campaign stop before strict four-token 4h completion
   validation. Genuine completion still requires strict through-4h proof.
2. Scheduler re-entry starvation: a RUNNING Cycle-2 attempt could cooperatively
   re-enter even when its boundary explicitly returned `LIFECYCLE_WORK`, causing
   due Cycle-1 Scheduler work to be skipped repeatedly until the Cycle-2 deadline.
   `LIFECYCLE_WORK` now preempts Cycle-2 cooperative re-entry so the due lifecycle
   job executes; Cycle 2 may re-enter afterward.

Operational evidence for the starvation defect was explicit: Cycle 2 completed
four successful acquisition quanta with 25/30 discovery operations still unused
and no refresh wait, while a Cycle-1 snapshot due at 08:54:37 UTC did not start
until 09:03:26 UTC. The repaired control-flow regression prevents that loop.

Focused verification on the repaired checkout:

- `py_compile` passed for both production files and both changed regression files;
- `git diff --check` passed;
- 26 passed across terminal/wake/callback/checkpoint/full Standard-4H coverage;
- 56 passed across the broader affected Cycle-2/disjointness/materialization/
  acquisition/terminal/wake/checkpoint/full Standard-4H surface.

The previous Cycle-2 deadline-anchor repair remains intact: the 600-second
later-cycle deadline is anchored to the later of atomic Cycle-1 slot creation and
authoritative factory-run `started_at`. The 300-second minimum admission spacing,
evidence, health, capacity, disjointness, tracking and Standard-4H requirements
are unchanged.

## Proven blocker

The 2026-09-11 operational blocker was not candidate scarcity: Cycle-2 discovery
had substantial unused governed budget when scheduler re-entry starvation began.
The starvation and terminal-mask defects are repaired at code/test level. Literal
provider-driven four-token 4/2/2 completion remains unproven until a fresh,
separately authorized operational attempt on the repaired exact HEAD.

## Exact next permitted action

Push the repaired branch and verify CI on the exact pushed HEAD. Any later
operational attempt requires a fresh one-shot authorization bound to that exact
HEAD and the then-current authoritative DB after migration/integrity/FK/
zero-active-work/non-reuse gates. Never reuse a consumed authorization.
