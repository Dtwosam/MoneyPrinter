# Printer V1 Handoff

## Current verified implementation

Branch: `assistant/v2-9-8b-paper-position-audit-lockout-audit`.

Latest fully verified code/test HEAD before this handoff-only update:
`d6a8839d5b18d15b586e9b9dc108d9a06e8e9e92`.

GitHub Actions run `34401666253`, job `102634783052`, is green on that HEAD:

- focused post-holder/reconciliation boundary: **29 passed**;
- clean-memory consumer lockout boundary: **27 passed**;
- paper position/monitor/audit/PnL lockout boundary: **46 passed**;
- shared discovery/admission/two-cycle Standard-4H boundary:
  **399 passed, 2 deselected, 32 subtests passed**;
- affected-module compile: passed;
- diff whitespace check: passed.

## Current capability

Printer V1 remains Solana-only, memecoin-only, paper-only. Source Governor is
the sole governed source-request owner and Central Scheduler is the sole
Scheduler owner. `WINDOW_5M_MICRO_EVENT` is support-only; `WINDOW_12H` and
`WINDOW_24H` remain locked.

The earlier discovery/admission/lifecycle work remains green: exact-two Cycle-1
admission, generic non-Pump present-pool verification and protocol->market
resume, atomic and campaign-disjoint Cycle-2 admission, and exact four-target
two-cycle progression through 15m -> 1h -> 4h with clean-memory promotion
quality-gated to exact physical window identity.

Current downstream capability sequencing is now code-enforced, not merely
unreached by the memory factory:

- `RETRIEVAL_ACTIVATION_ENABLED = False`;
- `PAPER_DECISIONS_ENABLED = False`;
- `PAPER_POSITIONS_ENABLED = False`;
- `PAPER_AUDITS_ENABLED = False`;
- `PAPER_PNL_ENABLED = False`.

The verified locks cover:

- clean memory may be inspected read-only, but cannot persist retrieval queries
  or matches while retrieval activation is locked;
- paper-decision recorders and direct action/status helpers cannot emit or
  persist BUY/SELL/HOLD/WAIT/AVOID/NO_ACTION decision authority while locked;
- paper position entry, sizing, monitoring, exit decisions, trade-event output,
  position mutation, and monitor Scheduler enqueue are locked;
- realized/unrealized PnL calculations, PnL-state output, and PnL reporting are
  locked;
- paper audit classification/report output, persistence, trade-audit writes,
  and audit Scheduler enqueue are locked;
- Central Scheduler rejects locked downstream target tables and rejects
  `OPEN_PAPER_TRADE_MONITOR` activation outside the separately locked audit
  target;
- `PAPER_MONITORING` cannot be claimed or updated into the tracking queue,
  durably recorded as a new lifecycle state, scheduled from a historical queue
  row, or used to write/schedule paper-monitoring snapshots while positions/PnL
  remain locked;
- a historical `PAPER_MONITORING` queue row cannot be reactivated to
  QUEUED/ACTIVE/PAUSED while locked, but can still be archived or otherwise
  retired safely;
- synthetic hardening shortcuts cannot bypass the retrieval, decision,
  position/monitor, audit, or PnL locks;
- read-only retrieval/history, stored position/audit inspection, and
  paper-only/no-live-execution validators remain available.

Historical Phase 4/15/16/17/18/20 tests explicitly enable their future
subsystems only inside disposable test setup and restore the default locks
afterward. This preserves testability of implemented future engines without
granting current runtime authority.

## Latest meaningful result

The downstream paper engines were implemented and directly callable even though
current V2-9.8B authority keeps them locked. The repair moved capability
sequencing to the consumer boundaries themselves and to Central Scheduler, then
closed two lifecycle bypasses that table-only locking would miss:

1. `PAPER_MONITORING` work could be selected by job kind against an unrelated
   Scheduler target; Scheduler enqueue is now job-kind-aware.
2. A historical `PAPER_MONITORING` tracking row could be reactivated by
   changing only its queue status; live ownership reactivation is now rejected
   while archival/cleanup remains possible.

The focused regression proves those paths fail before mutation while ordinary
TRACK_FAST tracking and ordinary memory-window Scheduler work remain unchanged.

## Proven blocker

None remains in the scoped clean-memory -> retrieval/decision -> paper
position/monitor/audit/PnL lockout engineering lane.

This is **not** operational authorization and does not establish authoritative
database or live-run readiness. No operational Printer run, live provider/RPC
or WebSocket execution, Scheduler operation, wallet/signing action, or
authoritative database mutation was performed.

Default branch `master` remains historically divergent from this active
development lineage and is not a safe blind merge/rebase target.

## Exact next permitted action

Begin a narrow read/test-only audit of downstream reporting/operator-review
surfaces that consume historical memory/paper tables. Prove those surfaces
remain read-only and cannot synthesize or activate retrieval, paper decisions,
positions, monitoring, audits, or PnL while the current capability locks are
false. Repair only a concrete reachable unlock if found.

Do not activate any locked capability, run Printer operationally, use live
providers, operate Scheduler jobs, or mutate the authoritative database without
a new explicit authorization boundary.
