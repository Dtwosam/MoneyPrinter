# V2-9.7E.1 Insufficient-Pool Terminal Cleanup and Reporting Repair Closeout

**Status:** PASS  
**Lane:** V2-9.7E.1  
**Date:** 2026-07-21  
**Baseline HEAD:** `506cf76f59db8be5995db3f2a238eb212b185e22`

## Verdict

`V2_9_7E_1_INSUFFICIENT_POOL_TERMINAL_CLEANUP_REPAIR_PASS`

## Todo / Checklist

- [x] Verify HEAD `506cf76…` and preserve blocked-pilot artifacts untouched.
- [x] Diagnose `IntegrityError` root cause (cycle two-slot trigger).
- [x] Diagnose residual ACTIVE supervision and discovery Scheduler jobs.
- [x] Repair trigger via migration 035 for terminal zero-slot cycles.
- [x] Repair supervision cleanup for discovery_work/batch/jobs.
- [x] Repair discovery executor batch terminalization on insufficient pool.
- [x] Repair final report assembly/persistence for zero-slot insufficient pool.
- [x] Focused synthetic proof + affected regressions.
- [x] Closeout documentation; no V2-9.7E re-run.

## Root Cause

From the blocked V2-9.7E pilot:

1. **Primary IntegrityError**  
   Migration `032` trigger `printer_campaign_cycle_requires_two_slots` aborted
   **any** leave from `PLANNED` when `COUNT(token_slots) <> 2`, including
   transitions to `TERMINAL_*`. Insufficient-pool discovery correctly activates
   **zero** slots, so cleanup could not terminalize the cycle.

2. **Residual discovery Scheduler work**  
   Combined discovery creates jobs linked through `printer_discovery_work`
   (migration 034), not only `printer_memory_factory_campaign_scheduler_work`.
   Cleanup cancelled only the campaign-scheduler-work path, leaving
   `DISCOVERY_REFRESH` jobs and open discovery work.

3. **Discovery batch left non-terminal**  
   The insufficient-pool branch terminalized selection work but did not mark
   the discovery batch `TERMINAL_FAILED`.

4. **Final report blocked**  
   Report assembly required two slots per cycle, required 4A–5C objects, and
   required a non-null authoritative memory-factory run. None exist for a
   pure insufficient-pool discovery stop, so no report and no zero-source
   replay could run.

Eligibility, origin, freshness, cooldown, and two-or-none rules were **not**
the defect and were not changed.

## Exact Repair

### Migration `035_insufficient_pool_cycle_terminal_trigger.sql`

Recreate `printer_campaign_cycle_requires_two_slots` so the two-slot check
applies only when leaving `PLANNED` to a **non-terminal** state. Terminal
transitions (`TERMINAL_%`) may complete with zero slots.

### `campaign_supervision.cleanup_campaign_supervision`

- Terminalize open `printer_discovery_work` for the campaign/run.
- Terminalize non-terminal `printer_discovery_batches`.
- Cancel Scheduler jobs linked via **either** campaign scheduler work **or**
  discovery work.
- Include discovery work in active-child residual checks.
- Reject conflicting terminal cleanup (different status/cause) while allowing
  identical idempotent replay.
- Preserve first terminal cause.

### `combined_executor` insufficient-pool branch

- Fail remaining open discovery work rows for the batch.
- Mark discovery batch `TERMINAL_FAILED` with
  `INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL`.

### Final report + persistence

- Allow **zero** slots when cause is `INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL`
  (still require exactly two slots otherwise; forbid non-zero slots for that
  cause).
- Allow empty 4A–5C object sets for that cause only.
- Synthesize a zero-delta authoritative envelope from locked-capability table
  counts when no authoritative memory-factory run exists for that cause.
- Allow empty `object_ids` on terminal report persistence only for that cause.

## Terminal-State Flow (after repair)

```text
INITIAL discovery -> INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL
  -> zero slots / zero tracking / zero windows
  -> discovery work FAILED; batch TERMINAL_FAILED
  -> cleanup_campaign_supervision(FAILED, same cause)
       cancel discovery + campaign Scheduler jobs
       terminalize cycles (now allowed with 0 slots)
       terminalize campaign/run
       supervision TERMINAL; lease released
  -> persist_final_campaign_report (once; idempotent)
  -> replay_terminal_campaign_report (read-only, write-free)
```

## Proof

Focused suite: `tests/test_v2_9_7e_1_insufficient_pool_terminal_cleanup.py`

| Assertion | Result |
|---|---|
| Insufficient-pool cleanup without IntegrityError | PASS |
| First cause unchanged | PASS |
| Supervision TERMINAL; lease released | PASS |
| Discovery/Scheduler work terminal | PASS |
| Zero slots / tracking / windows | PASS |
| Final report once + idempotent | PASS |
| Conflicting cleanup fails closed | PASS |
| Zero-source replay write-free; hash/counts stable | PASS |
| Locked-capability zeros | PASS |
| Non-terminal PLANNED→DISCOVERING still requires two slots | PASS |

Focused + regressions (6B.5–6B.8, 7A, 7B.5, 4D, 4D.1, 4C):

**60 passed, 22 subtests passed.**

Original pilot DB/backups/blocked pilot closeout: **not modified**, **not committed**.

## Money-Usefulness Contribution

Fail-closed insufficient-pool stops can now leave a durable, replayable
terminal report without inventing tokens or weakening selection. Operators can
audit honest empty activations instead of residual ACTIVE leases and open jobs.

## Remaining Locks / Out of Scope

- No second live pilot / source calls in this lane  
- No V2-9.7F / V2-9.8  
- No retrieval, decisions, BUY/SELL/HOLD, positions, trades, PnL, wallets  
- No eligibility/origin/freshness weakening  
- Original blocked pilot residual state is historical evidence only  

## Functionality Risks / Setbacks / Efficiency Blockers

- Synthetic authoritative envelope for insufficient-pool reports is intentional
  zero-delta evidence, not a memory-factory yield claim.
- Empty object sets are allowed only for that exact terminal cause.
- Future INITIAL abstract-command preflight (two pre-existing slots) remains a
  separate composition concern, not fixed here.
- Multi-window live campaign executor after dual activation remains out of scope.

## Files Changed

- `migrations/035_insufficient_pool_cycle_terminal_trigger.sql`
- `src/printer_v1/operator_cli/campaign_supervision.py`
- `src/printer_v1/discovery/combined_executor.py`
- `src/printer_v1/operator_cli/final_campaign_report.py`
- `src/printer_v1/operator_cli/campaign_persistence.py`
- `tests/test_v2_9_7e_1_insufficient_pool_terminal_cleanup.py`
- `docs/printer-v1-v2-9-7e-1-insufficient-pool-terminal-cleanup-repair-closeout.md`

## Stop Boundary

V2-9.7E.1 stops at this repair PASS. Do **not** re-run V2-9.7E in this lane.
