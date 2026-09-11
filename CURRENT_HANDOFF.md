# Printer V1 Handoff

## Current verified implementation

Branch: `assistant/v2-9-8b-later-cycle-mint-market-replay-repair`.

The latest 2026-09-11 four-token Standard-4H operational attempt used authorization
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260911T114100Z_3fd609b4` on HEAD
`729d5d5ae3d4d568e33a1f405228239833c99eec`. It reached Cycle-1 lifecycle work,
then terminalized safely. Cleanup completed, the lease was released, active
Scheduler/factory/campaign work is zero, and the authorization is consumed and
permanently non-reusable.

## Current capability

Printer V1 remains Solana-only, memecoin-only, paper-only. Source Governor is
the sole governed source-request owner and Central Scheduler the sole scheduler
owner. `WINDOW_5M_MICRO_EVENT` remains support-only; `WINDOW_12H` and
`WINDOW_24H` remain locked. Retrieval, decision, position, PnL, wallet, signing
and live trading capabilities remain locked.

## Latest meaningful result

The latest failed attempt proved a second-refresh stage-identity collision in addition
to the previously repaired terminal-precedence and scheduler-reentry defects.

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

The latest operational evidence showed 27/27 provider requests completed with
`CLEAN_DATA`; the generic reconciliation mismatch was caused by duplicate six-unit
stage identity `PROTOCOL_CONFIRMATION|3`. Refresh #1 owned protocol stage 2, the
residual pass correctly advanced to stage 3, but non-cooperative refresh #2 used
`refresh_ordinal + 1` and reused stage 3. The refresh protocol path now asks the
authoritative stage-evidence owner for the next free `PROTOCOL_CONFIRMATION`
sequence, retaining `refresh_ordinal + 1` only as a fallback when no owner exists.
The duplicate-stage guard remains strict.

Focused verification for this repair: 22 passed across residual closeout, failed
refresh/stage identity, local-validation observation, initial refresh ownership,
persistent multisource refresh, and Standard-4H refresh-reentry seams; `py_compile`
and `git diff --check` passed. A detached untouched `ef515b94` worktree reproduced
the broader stale fixture/source-scope failures, proving they are baseline debt and
not regressions from this change.

The latest attempt also exposed a later-cycle cooperative-resume contract defect.
Cycle 2 lawfully persisted clean `solana_rpc/generic_present_pool_account_batch`
evidence at `...:c0002-protocol-q2-1`, but the resume validator only admitted
`pumpswap_pool_account_batch` for protocol-stage request keys. Re-entry therefore
misclassified its own clean Q2 row as `CAMPAIGN_SOURCE_REQUEST_SCOPE_ALREADY_EXISTS`.
The resume grammar now accepts both producer-owned protocol request kinds for the
existing protocol/residual/refresh key forms while retaining exact root, source,
stage grammar, registry, and single-terminal-artifact checks. The Cycle-1 token
that received `PARTIAL/ACCEPTABLE_PARTIAL_DATA` still fails closed; that clean-data
lock was intentionally not weakened.

The previous Cycle-2 deadline-anchor, terminal-precedence, and scheduler-reentry
repairs remain intact. The 600-second later-cycle deadline, 300-second minimum
admission spacing, evidence, health, capacity, disjointness, tracking and
Standard-4H requirements are unchanged.

## Proven blocker

The latest operational blocker is the repaired later-cycle cooperative-resume
protocol contract mismatch described above. Cycle 1 also observed one lawful
fail-closed partial snapshot, so literal provider-driven four-token 4/2/2 completion
remains unproven until a fresh, separately authorized attempt on the repaired exact
HEAD.

## Exact next permitted action

Commit/push the cooperative-resume protocol-contract repair and verify CI on the
exact pushed HEAD. Any later operational attempt requires a fresh one-shot
authorization bound to that exact HEAD and the then-current authoritative DB after
migration/integrity/FK/zero-active-work/non-reuse gates. Never reuse a consumed
authorization.
