# Printer V1 — Four-Concurrent Overlapped Two-Cycle Capacity + Cycle-2 Fast Admission Design

Status: **APPROVED FOR IMPLEMENTATION**

Design verdict:

`V2_9_8B_FOUR_CONCURRENT_OVERLAPPED_TWO_CYCLE_CAPACITY_FAST_ADMISSION_DESIGN_PASS`

This design incorporates the independent review corrections. It does not
authorize a live campaign, drain the surviving `WAITING` row, raise budgets,
change refresh timing, or map the Cycle-2 2400s clock onto factory
`PROOF_DEADLINE`.

Governing prior audit:

`docs/printer-v1-v2-9-8b-four-concurrent-overlapped-two-cycle-feasibility-audit.md`

## 1. Capability envelope (source-stack adoption)

Adopt exactly this concurrent meaning and no more:

- one campaign / one campaign-run / one authoritative factory run;
- two cycles;
- exactly two slots per cycle, ordinals `(1, 2)`;
- maximum **four concurrent through-4h lifecycle tokens**;
- Cycle 2 may overlap Cycle 1 through `WINDOW_15M → WINDOW_1H → WINDOW_4H`;
- no third cycle;
- no fifth token;
- compiled 6-token / 3-cycle maximum remains unused;
- cycle-spacing floor remains 300 seconds;
- freeze-ready depth remains `>= 4`;
- exactly 2 selected + 2 report-only alternates;
- Cycle-2 campaign-history disjointness remains required;
- same Source Governor and Central Scheduler;
- retries `0`; endpoint rotation `false`;
- `WINDOW_5M_MICRO_EVENT` support-only;
- `WINDOW_12H` / `WINDOW_24H`, retrieval, and all financial capability remain locked.

Operational constants already bind `configured_through_4h_tokens = 4`. This
adoption aligns source-stack wording with that contract.

## 2. Architecture

Keep the existing one-campaign / 4/2/2 machine. Same factory, Scheduler,
Source Governor, and `15m → 1h → 4h` runner.

Do not introduce a second factory, Scheduler, Source Governor, thread,
Scheduler consumer for refresh, or new refresh stage machine.

## 3. Cycle-1 protection (unchanged layers)

1. Already-due lifecycle work wins (`DUE_LIFECYCLE_WORK`).
2. Due token snapshots/closes outrank `DISCOVERY_REFRESH`.
3. Future-deadline fit remains: skip Cycle-2 source work when
   `now + next_unit >= next_due_lifecycle`.

Cycle-2 runs only in lawful gaps.

## 4. Cycle-2 liveness

Reuse `cooperative_yield`, `StageBudget`,
`next_governed_request_worst_case_seconds`, `request_temporal_refresh`,
existing request identity / `request_key_root` /
`campaign_source_request_scope`.

The factory gate must use the **next existing cooperative governed-request
bound**, not `acquisition_quantum_bound(PERSISTED_REFRESH) ≈ 115s`.

When later-cycle progress is `waiting_for_refresh` and no next-request bound
is declared, use the existing
`acquisition_governed_request_bound(PERSISTED_REFRESH,
DIRECT_PUMP_SIGNATURE_PAGE, checkpoint_reserve=5.0)` primitive. Do not guess
zero or an invented timeout.

If Cycle-1 work is already due: service Cycle 1.

If Cycle-2's next cooperative request fits strictly before the next Cycle-1
evidence deadline: re-enter the Cycle-2 owner, perform at most that unit,
yield.

Otherwise: protect Cycle 1 and wake at the next relevant boundary.

### WAITING and not due

Remain waiting. Wake at
`min(refresh_due_at, next_lifecycle_deadline, acquisition_deadline_at)`.

### WAITING and already due

Do **not** return `WAITING` merely because `_waiter is None`. Claim the
persisted wait, run the existing cooperative request unit, persist progress,
yield. Same owner, same request identity, no duplicate request.

### CLAIMED

A cooperative refresh may yield while the wait remains `CLAIMED`. Treat
`CLAIMED` as active and immediately re-enterable. Do not fail-close
`_active_later_cycle_refresh_wake_at` on a single legitimate `CLAIMED` wait.
Ambiguous multi-wait ownership still fails closed.

## 5. Cycle-2 2400s deadline

Absolute clock: `acquisition_started_at + 2400s` on the wait/owner.

**Do not map this to factory `PROOF_DEADLINE`.** That stop reason has campaign
`STOP_DURATION` semantics and would halt healthy Cycle-1 1H/4H work.

When the acquisition deadline is due:

- skip the 115s-style source-work conflict (abandon is local);
- re-enter the existing Cycle-2 pre-lifecycle owner;
- that owner `_abandon`s the wait and terminalizes the attempt;
- mark Cycle-2 admission attempt finished;
- leave healthy Cycle-1 lifecycle running.

```text
Cycle-2 acquisition deadline exhausted
!=
campaign STOP_DURATION / PROOF_DEADLINE
```

## 6. Refresh timing

Unchanged in this implementation:

```text
initial intake T+0
refresh 1 T+600
refresh 2 T+1200
refresh 3 T+1800
deadline T+2400
```

No +300s. No global `DISCOVERY_REFRESH` change. No non-uniform schedule.

## 7. Wait cleanup

Canonical path:

```text
PreLifecycleTemporalRefreshOwner
  -> abandon_scoped_refresh_waits / _abandon / cancel_pending_wait
  -> cancel still-active matching Scheduler job
  -> terminalize_refresh_wait
  -> terminalize RUNNING refresh work if present
```

Call this from parent-interrupt reconcile and campaign terminal reconcile.
A cancelled Scheduler job with a leftover `WAITING`/`CLAIMED` wait is not
terminal cleanup.

Do not drain the surviving Sep-2 wait row.

## 8. Official zero-state

Count

```sql
printer_pre_lifecycle_discovery_refresh_waits
WHERE wait_state IN ('WAITING', 'CLAIMED')
```

Keep existing `RUNNING` refresh-work checks. Terminal wait history must not
block. Align with `campaign_active_work`.

## 9. Budgets

Do not change 476 / 118 / 444, retries 0, rotation false, or provider limits.

## 10. Schema

No migration.

## 11. Proof

Frozen/fake transport only. Focused tests for: Cycle-1 non-regression;
already-due Cycle-1 wins; sub-115s gap service; past-due WAITING claim;
CLAIMED re-entry; no duplicate request/transport; 2400s re-entry without
`PROOF_DEADLINE`; max four / no fifth / no third cycle; wait cleanup;
zero-state WAITING/CLAIMED; ceilings unchanged.
