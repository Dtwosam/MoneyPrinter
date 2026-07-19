# V2-9.7D.6B.5 Operational Lease and Safe-Stop Closeout

## Result

V2-9.7D.6B.5 adds a campaign-scoped operational supervision owner, migration
033, and one transactional safe-stop path. It is separate from migration 030
and `proof_supervision.py`; no proof-only row, scope, launcher type, or run
identity is repurposed.

## Money-Usefulness Contribution

Long evidence campaigns are useful only when their writer ownership and stop
boundary are unambiguous. Exact leases prevent two owners from spending source
and scheduler capacity on the same run. Fail-closed renewal and transactional
child cleanup prevent uncertain work from contaminating later campaign memory,
while immutable first-cause evidence makes interrupted collection diagnosable.

## What 6B.5 Improves

- Migration 033 exact-links one lifetime operational supervision identity to
  campaign, immutable configuration, run, owner, and same-directory lock path.
- A campaign run can have only one supervision row. A terminal row cannot be
  resumed, replaced, or used to create a successor owner.
- Acquisition requires exact graph ownership and both campaign and run in
  `RUNNING` state.
- Heartbeat and expiry must advance monotonically. Atomic lock replacement
  retries only Windows errors 5, 32, and 33, for at most three attempts.
- An unconfirmed exact-owner renewal invokes the same safe-stop path, blocks
  new child work, terminalizes active campaign work, clears linked scheduler
  locks, commits terminal state, and only then releases the lease.
- Cooperative cancellation persists `STOPPING` supervision plus
  `STOP_REQUESTED` campaign/run state before cleanup.
- Natural completion, failure, cancellation, and renewal uncertainty use one
  cleanup function.
- Cleanup exact-links every affected row, rejects scheduler jobs shared with a
  foreign campaign/run, and is idempotent after terminalization.
- The first terminal cause stored in supervision, campaign, run, cycles,
  windows, and active campaign work is retained when later failures arrive.
- B.3 ownership is preserved: token-slot lifecycle disposition and tracking
  queue rotation are not changed by supervision cleanup.

## What Remains Locked

This lane does not provide a runtime loop, launcher, command surface, source
call, memory generation, lifecycle rotation execution, persistent-target
migration, final report, replay, retrieval, decision, BUY/SELL/HOLD, position,
trade, audit, PnL, wallet, signing, or live execution. It does not create a
resume, restart, or successor campaign. 6B.6 was not started.

## Proof Completed

- clean disposable migration through 033 and a distinct operational ledger;
- exact owner acquisition, monotonic renewal, terminal cleanup, and release;
- active and post-terminal competing owners fail closed;
- campaign/configuration/run/owner mismatches fail closed;
- exhausted bounded Windows replacement retry produces no confirmed renewal;
- missing, malformed, or foreign lock state after exact ledger ownership also
  enters safe-stop and cannot leave child work active;
- renewal uncertainty terminalizes child work and releases its lock;
- cooperative cancellation prevents new work and uses the common cleanup path;
- natural, cancelled, and failed terminalization preserve exact states;
- later worker or logger faults cannot replace the first terminal cause;
- active scheduler work, windows, cycles, jobs, and locks are terminal before
  lease release;
- repeated cleanup is idempotent;
- no proof supervision row, successor, restart, or resume is created; and
- locked retrieval and financial tables remain empty.

## Functionality Risks / Setbacks / Efficiency Blockers

- The operational lock is local same-directory filesystem coordination. This
  lane does not claim distributed lease semantics.
- A renewal is confirmed only after both atomic lock replacement and the
  compare-and-update ledger write. Failure of either ends the run instead of
  attempting an automatic recovery.
- The retry set is intentionally limited to confirmed transient Windows
  replacement errors. Unknown filesystem errors fail immediately.
- Cleanup cancels campaign-owned scheduler work and active window/cycle state,
  but deliberately leaves B.3 token disposition and queue rotation untouched.
- A scheduler job linked to more than one campaign/run makes cleanup ambiguous
  and blocks transactionally.
- Lease release follows the committed cleanup transaction. If filesystem
  release itself fails, the terminal ledger remains unreleased and a repeated
  exact-owner cleanup may retry release without changing the first cause.

## Scope Confirmation

All verification uses disposable databases and temporary lock files. The
persistent target was not opened or migrated. No source, runtime, scheduler
execution, lifecycle rotation, report, replay, retrieval, or financial
capability was activated. Unrelated artifacts were untouched.
