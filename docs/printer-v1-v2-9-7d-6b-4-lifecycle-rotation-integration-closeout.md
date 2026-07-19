# V2-9.7D.6B.4 Lifecycle/Rotation Integration Closeout

## Result

V2-9.7D.6B.4 adds a narrow campaign adapter to the existing B.3 lifecycle
reconciliation authority and a separate read-only replacement eligibility
gate. Verification used disposable databases only. No schema or persistent
target was changed.

## Money-Usefulness Contribution

Campaign slots must stop consuming collection capacity after a terminal token,
without immediately recycling stale pairs or disturbing a healthy peer token.
This adapter makes the B.3 cleanup and cooldown/archive result exact and
auditable before a slot can be considered vacant. It improves candidate
rotation hygiene and resource use without generating memory or enabling any
financial action.

## What 6B.4 Improves

- Exact-links campaign, run, authoritative B.3 run, cycle, token slot, integer
  token/pair rows, token/mint/pair strings, lifecycle identity, and tracking
  queue.
- Maps fixed campaign terminal outcomes to B.3 facts: natural to `CLEAN`, dirty
  to `DIRTY`, blocked to `TOKEN_LOCAL_FAILED`, and cancelled to `CANCELLED`.
- Calls the committed B.3 reconciliation function as the sole writer of queue
  disposition, lifecycle event, scheduler cleanup, and support-step cleanup.
- Requires one exact reconciliation event, one disposition, matching queue
  state, and zero active queue jobs, campaign work, and support steps before
  reporting a vacant slot.
- Preserves B.3 idempotency through its run/token/pair reconciliation key.
- Defaults to pair-specific cooldown; archive requires the existing explicit
  archive policy and is reported as requiring the existing reopen policy, not
  permanent rejection.
- Keeps replacement evaluation read-only. It requires prior successful
  reconciliation, zero active work, an exact candidate token/mint/pair mapping,
  a pair not already assigned in the cycle, and no persisted cooldown/archive
  or active queue state.
- Blocks same-pair recycling and graph/candidate identity mismatches.
- Reconciles one failed token independently, leaving the other campaign slot
  and its scheduler work untouched.
- Treats 5m support steps as cleanup/audit evidence only; their payload cannot
  select lifecycle disposition.

## What Remains Locked

The adapter does not create a replacement slot, select a candidate, reopen an
archived pair, run rotation, schedule work, orchestrate runtime, handle a lease,
assemble reports, replay, fetch sources, generate memory, retrieve, decide,
BUY/SELL/HOLD, create positions/trades/audits/PnL, use wallets, sign, or execute
live activity. 6B.5 was not started.

## Proof Completed

- natural completion produces one cooldown disposition/event and zero active
  associated work;
- dirty completion can use the explicit archive policy while archive remains
  non-permanent;
- blocked and cancelled outcomes produce independent manual-review/`SKIPPED`
  dispositions;
- repeated reconciliation reuses the same event and is idempotent;
- queue scheduler jobs and active 5m support jobs/steps are cancelled by B.3;
- replacement is blocked before reconciliation and allowed for an exact fresh
  candidate only afterward;
- persisted pair cooldown blocks immediate candidate selection;
- same-pair recycling and token/mint/pair/lifecycle mismatches fail closed;
- token-local failure does not mutate the other slot's queue or job;
- a 5m payload claiming archive cannot override the natural cooldown outcome;
  and
- locked-capability tables remain at zero rows.

## Functionality Risks / Setbacks / Efficiency Blockers

- B.3 still uses migration 028's proof-only run identity. The adapter requires
  migration 032's explicit `authoritative_run_id`; it does not redefine run
  ownership.
- Existing B.3 represents blocked/cancelled terminal handling as queue
  `SKIPPED` plus a `MANUAL_REVIEW` lifecycle event. The adapter preserves both
  facts rather than creating a parallel disposition vocabulary.
- A campaign scheduler-work row left active after B.3 cleanup blocks and rolls
  back reconciliation. This is intentionally fail-closed because B.3 does not
  own campaign-work state transitions.
- Pair cooldown is represented by the latest persisted exact-pair queue state;
  this lane does not invent a duration or silently reopen cooldown/archive.
- Replacement eligibility is advisory representation only. Actual candidate
  selection and slot creation remain later integration responsibilities.

## Scope Confirmation

No migration, persistent-target write, source call, runtime operation, lease,
report, replay, retrieval row, decision, position, trade, audit, or PnL was
created. Unrelated artifacts were untouched.
