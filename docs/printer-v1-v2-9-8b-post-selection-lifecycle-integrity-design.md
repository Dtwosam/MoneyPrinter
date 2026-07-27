# Printer V1 V2-9.8B.10B — Post-Selection Lifecycle Integrity Design

## Verdict

```text
V2_9_8B_10B_POST_SELECTION_INTEGRITY_DESIGN_PASS
```

Authority: `docs/printer-v1-v2-9-8b-post-selection-lifecycle-integrity-audit.md`
(`V2_9_8B_10A_POST_SELECTION_INTEGRITY_AUDIT_PASS`).

This design authorizes the **minimum** repair. It does not create a second
lifecycle owner, Scheduler, source counter, terminal owner, retry framework, or
recovery product. It does not authorize production.

## Goal

Allow a valid two-token `PILOT_INPUT_READY` handoff to enter the **existing**
`WINDOW_15M` factory lifecycle exactly once under operational persistence, then
fail-closed and terminalize cleanly if a later fault occurs.

## Repair set (smallest)

### R1 — Schema: factory-run `db_mode` allows operational persistence

Migration `044_memory_factory_run_operational_db_mode.sql`:

* Rebuild `printer_memory_factory_runs` so:

```text
db_mode TEXT NOT NULL CHECK (db_mode IN ('PROOF_ONLY', 'OPERATIONAL_PERSISTENT'))
```

* Preserve all existing columns and indexes.
* Copy all existing rows unchanged (historically only `PROOF_ONLY` when present).
* Do not alter campaign-table modes, selection rules, or source ceilings.

### R2 — Factory connection always closes on insert failure

In `run_one_command_15m_factory`:

* Keep the existing INSERT semantics.
* On any exception before the main lifecycle `try/finally`, close the SQLite
  connection so a failed operational insert cannot hold a write lock against
  terminal cleanup.

### R3 — Terminal cleanup retries transient SQLite locks

In operational command `_terminalize_initialized_failure` (and only there as the
automatic post-fault coordinator):

* Retry `cleanup_campaign_supervision` (and report write if needed) a small
  bounded number of times when the error is SQLite busy/locked.
* Preserve first terminal cause immutability (existing cleanup rules).
* No new terminal owner.

### R4 — Heartbeat stop before cleanup remains mandatory

Keep “heartbeat never terminalizes” rule. Ensure exception path:

1. signals stop on the heartbeat thread,
2. joins with a bounded wait,
3. then runs cleanup retries.

No second lease owner.

### R5 — Public failure surface reports durable campaign source total

When `main` catches a post-run exception:

* Best-effort read of the latest holder ledger `governed_requests` for the latest
  campaign supervision run (read-only).
* Emit:

```text
campaign_source_calls: <int or null>
source_calls: <same durable total when available, else 0 for pre-ledger faults>
```

Do not invent a second source-accounting owner. Prefer the existing
`printer_holder_campaign_operation_ledgers` total.

## Non-goals

* No production run
* No rewrite of execution `20260727T001520Z-d513e21260b5`
* No second lifecycle/Scheduler/source-counter/terminal owner
* No automatic retry of production campaigns
* No restart/successor
* No retrieval / decisions / positions / trades / audits / PnL
* No scoring/ranking/confidence/weights
* No raising ceiling 45 or lowering $3k / two-token rules
* No long-window enablement

## Identity and once-only rules preserved

* One campaign / one run / one cycle graph per operational execution
* Exactly two token slots (ordinals 1 and 2)
* Factory run created only after readiness handoff enters lifecycle
* Duplicate lifecycle entry: existing unique keys / factory run uniqueness fail closed
* Invalid predecessor/state transitions: existing ownership transition rules

## Proof plan (focused disposable only)

1. Operational-persistent factory INSERT succeeds after migration  
2. Two selected tokens can enter lifecycle once without IntegrityError  
3. One factory-run row; no duplicate lifecycle graph  
4. Two distinct handoffs remain valid  
5. First WINDOW_15M work only after readiness  
6. Duplicate lifecycle entry fails safely  
7. Invalid transition fails closed  
8. Post-selection exception terminalizes campaign/run/cycle and releases lease  
9. Heartbeat + open connection cannot permanently block cleanup  
10. First terminal cause immutable  
11. Public failure output includes durable campaign source total when ledger exists  
12. Status/report-only stay zero-source in their modes  
13. Discovery / floor-cooldown / holder-budget / reporting regressions still pass  

## Acceptance

`V2_9_8B_10_POST_SELECTION_LIFECYCLE_REPAIR_PASS` only after focused proofs pass
and closeout is committed. Still no production authorization and no V2-9.8B
complete claim.
