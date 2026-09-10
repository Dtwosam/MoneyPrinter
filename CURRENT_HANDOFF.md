# Printer V1 Handoff

## Current verified implementation

Branch: `assistant/v2-9-8b-later-cycle-mint-market-replay-repair`.

The fourth four-token Standard-4H operational attempt ran on HEAD
`0328296a66e6ace9f6b7552c79ef3e46ba5e3016`. It durably admitted both Cycle-1
slots and started lifecycle work, but Cycle 2 was terminalized `BLOCKED` with
`LATER_CYCLE_ADMISSION_DEADLINE_EXHAUSTED`. Cleanup completed, the lease was
released, and authoritative active campaign/factory/Scheduler work is zero.
Its one-shot authorization is consumed and must never be reused.

## Current capability

Printer V1 remains Solana-only, memecoin-only, paper-only. Source Governor is
the sole governed source-request owner and Central Scheduler the sole scheduler
owner. `WINDOW_5M_MICRO_EVENT` remains support-only; `WINDOW_12H` and
`WINDOW_24H` remain locked. Retrieval, decision, position, PnL, wallet, signing
and live trading capabilities remain locked.

## Latest meaningful result

The Cycle-2 deadline defect is repaired on current code: the 600-second later-
cycle admission deadline is anchored to the later of atomic Cycle-1 slot creation
and the authoritative factory-run `started_at`, so Cycle-1 pre-lifecycle discovery
cannot consume the entire Cycle-2 window. The 300-second minimum admission
spacing and all health/evidence/capacity gates are unchanged.

Focused verification on the integrated branch includes:

- 19 passed across deadline/wake-order/admission-checkpoint/Standard-4H tests;
- 38 passed across broader Cycle-2 admission/integration coverage;
- 25 passed across shared-scheduler/overlap/capacity accounting audit;
- 16 passed after integration on the authoritative branch across wake ordering,
  callback consume/materialize, terminal integration, and full Standard-4H audit;
- `git diff --check` passed.

The full disposable two-cycle overlap path proves two disjoint Cycle-1 targets and
two disjoint Cycle-2 targets can share the scheduler through 15m -> 1h -> 4h,
with lifecycle work taking due-time priority, Cycle-2 acquisition cooperatively
yielding/re-entering, exact cycle-scoped Scheduler ownership, and terminal zero
active work.

## Proven blocker

`LATER_CYCLE_ADMISSION_DEADLINE_EXHAUSTED` caused by pre-lifecycle timestamp
anchoring is repaired at code/test level. No remaining shared-scheduler starvation
or known Cycle-2 admission blocker was found in the audited seam. Literal
provider-driven two-cycle 4/2/2 completion remains unproven until a fresh
separately authorized operational attempt on the repaired exact HEAD.

## Exact next permitted action

Push the repaired authoritative branch. Any new operational attempt requires a
fresh one-shot authorization bound to the repaired exact HEAD and current
authoritative DB after migration/integrity/FK/zero-active-work/non-reuse gates.
Do not reuse any consumed authorization.
