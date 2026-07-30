# Printer V1 V2-9.8B Post-Handoff Terminal Compensation Readiness

Date: 2026-07-30

Lane: `V2-9.8B Post-Handoff Terminal Compensation Repair`

Status: `READINESS_CONFIRMED`

## Baseline

- Branch: `master`
- Committed HEAD: `e864463472ad8c1db6f171847caac885940445fd`
- Campaign-accounting and terminal-enforcement changes remain uncommitted and
  lane-owned (not reset, discarded, stashed, or overwritten).
- Authoritative DB SHA-256 (never opened for write):
  `e748ba505cb8c7d67b8feb3a09b97719a0f3560e41dfb9242570cff3157962e6`
- Migration head: `049`

## Readiness audit source

The completed independent blocker review
(`docs/printer-v1-v2-9-8b-campaign-accounting-terminal-enforcement-audit.md`,
`AUDIT_COMPLETE`) and the prior closeout
(`...-terminal-enforcement-closeout.md`,
`V2_9_8B_CAMPAIGN_ACCOUNTING_TERMINAL_ENFORCEMENT_BLOCKED`) are used verbatim as
this lane's readiness audit. That audit closed repairs 1–10 and 13 and left
exactly one class open: **repairs 11–12** (`POST_HANDOFF_PROOF_GAP`), reported as
two discrepancies:

- **D-1 (primary):** literal "zero slots / jobs / links" is unreachable after a
  committed atomic two-slot handoff, because
  `printer_discovery_selected_item_links` is append-only immutable (migration
  034 `BEFORE UPDATE/DELETE` → `RAISE(ABORT)`) and FK-pins the token slots and
  the first-15m Scheduler job (`NO ACTION`). The prior compensation therefore
  *deleted* deletable lifecycle residue but left the pinned slots, tracking, and
  first-15m jobs **active** and merely *reported* them as surviving.
- **D-2 (secondary):** object-materialization / post-activation injections are
  driver-level representative simulations, not faults inside the real runner.

## What this lane changes vs. the prior BLOCKED verdict

The prior lane sought literal row-zero and was correctly blocked by the schema.
This lane adopts the **accepted invariant** that resolves D-1 without touching
the protected handoff:

```text
after a post-handoff failure:
  zero active, runnable, leased, reusable, or orphan work;
  immutable terminal handoff audit evidence may remain
```

The repair is therefore a **terminalization**, not a deletion, of the pinned
handoff rows: the surviving slots and first-15m jobs move to a lawful
non-runnable terminal state and their tracking is closed, while the immutable
selected-item links and their FK-pinned rows are preserved unchanged as terminal
audit evidence. D-2 remains explicitly out of scope and is re-reported as a
blocker (see the design's scope exclusions).

## Confirmed reusable authorities (no second cleanup owner introduced)

| Concern | Existing authority reused |
|---|---|
| Slot / tracking / cycle / run / campaign terminalization + campaign-scoped Scheduler job cancellation + active-work proof | `operator_cli/unified_terminal_closure.reconcile_campaign_terminal` (idempotent; already the canonical terminal owner, used by the coordinator, recovery, and heartbeat paths) |
| Per-record compare-and-update terminal transition (first-cause-immutable, idempotent) | `operator_cli/campaign_ownership.transition_state` (`token_slot` → `MANUAL_REVIEW`; migration-032 lawful terminal state) |
| Scheduler job cancellation through the committed owner | `scheduler.scheduler.cancel_job` (+ `ACTIVE_STATUS_VALUES`) |
| Exact zero-active-work accounting | `operator_cli/campaign_active_work.campaign_active_work_report` |

## Confirmed schema facts underpinning the design

- Token-slot lawful non-runnable terminal states (migration 032):
  `COOLDOWN`, `ARCHIVED`, `MANUAL_REVIEW`, `FAILED`, each requiring a non-empty
  `first_terminal_cause` and `terminal_at`. `token_state`,
  `first_terminal_cause`, `terminal_at`, `updated_at` are **not** in the
  slot-identity immutability trigger, so terminalizing a `SELECTED` slot is
  lawful; the slot row is never deleted, so the FK pin and the two-slot cycle
  trigger stay satisfied.
- The executor's first-15m Scheduler jobs (`window15m:<mint>:<pool>`,
  `TRACK_NORMAL_FIRST_15M`) are **not** reachable through the campaign-scoped job
  scan (they carry no `printer_discovery_work` /
  `printer_memory_factory_campaign_scheduler_work` link). They are cycle-scoped
  instead through the immutable link column
  `printer_discovery_selected_item_links.first_window_15m_scheduler_job_id`,
  which is exactly how the compensation reaches them — including re-cancelling
  jobs whose in-handoff cancellation was rolled back with the failed transaction.
- Freshly claimed tracking rows are `QUEUED`; `reconcile_campaign_terminal`
  drives the slot-linked `QUEUED` row to `SKIPPED` (`MANUAL_REVIEW` action).
- N2/N7 `printer_candidate_acquisition_leases` are not campaign-scoped and are
  out of scope; the compensation only guarantees zero `ACTIVE`/`STOPPING` leases
  as a safety net (release/terminalize, never delete audit rows).

## Readiness conclusion

All required authorities exist, are idempotent, and are lawful to compose. No
schema change, no new cleanup authority, and no touch of the immutable links are
required. Proceed to final compensation design → implementation → frozen
disposable-DB proof → closeout.
