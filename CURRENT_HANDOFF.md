# CURRENT HANDOFF

Date: 2026-08-20

## Current lane

`V2-9.8B Pre-Admission Terminal Cleanup Repair + Exact Historical Reconciliation`

Status: `CLOSED_PASS`

Verdicts:

- Product repair: `V2_9_8B_PRE_ADMISSION_TERMINAL_CLEANUP_REPAIR_GREEN`
- Authoritative reconciliation: `PASS` for Scheduler job `2364` + linked pre-admission attempt
- Post-repair operational re-readiness:
  `V2_9_8B_POST_ALL_SIX_REPAIRS_OPERATIONAL_REREADINESS_PASS`

`READY_FOR_FRESH_4_2_2_AUTHORIZATION_DESIGN: YES`

This still does **not** authorize or run Printer.

## Exact branch / HEAD

Branch:

`agent/v2-9-8b-pre-admission-terminal-cleanup-repair`

Repair commit / HEAD:

`3836148924a4dfa021902f5844a7a3383bd52078`

Prior closed quality-repairs baseline:

`dc5b3e2f65677fd40f16a31ccdbccd63b7fc0833`

## What landed

### Product repair

`reconcile_campaign_terminal()` now terminalizes every still-active
(`PLANNED`/`RUNNING`) pre-admission discovery attempt attributable to the exact
campaign/run/factory/cycle scope:

- linked Scheduler jobs cancel only through Central Scheduler `cancel_job()`
- attempts terminalize only through `terminalize_pre_admission_attempt(... CANCELLED ...)`
- campaign terminal cause is carried into the attempt
- already-terminal / consumed attempts are preserved
- second reconciliation is idempotent
- `campaign_active_work_report(...).clean_terminal` can become true without
  weakening active-work law

### Authoritative DB reconciliation (operator-approved one-time)

Target: `data/printer_v1.sqlite3`

| Item | Value |
| --- | --- |
| SHA-256 before | `769befd90ab82e2ed7443b19ba8834dbf7807e0c0aaed20549e0e4ab6acc3847` |
| SHA-256 after | `f167858a7a47c2837bced97223501f8d1c004d1c8c7a8177ed080c4e8d27f341` |
| Backup/restore | `OPERATIONAL_BACKUP_RESTORE_PREFLIGHT_READY` |
| Backup evidence | `operator-runs/v2-9-8b-pre-admission-2364-reconciliation/RECONCILE_20260820T174324Z/` |
| Job 2364 | `PENDING` → `CANCELLED` (unlocked; `finished_at` set) |
| Linked attempt | `RUNNING` → `CANCELLED` |
| Attempt ID | `pre-admission:20260820T012435Z-09f5d090566f-campaign:20260820T012435Z-09f5d090566f-campaign-run:ad5a83e6-9830-4c6b-8150-66445f54c8cc:c0002` |
| Terminal cause | `OPERATIONAL_CAMPAIGN_FAILED:FourTokenFactoryAdapterError` |
| Integrity / FK | `ok` / 0 |

No unrelated Scheduler jobs or attempts were touched. Parent campaign/run
terminal truth was unchanged. Rows were not deleted.

## Proof summary

- Focused RED→GREEN tests: `tests/test_v2_9_8b_pre_admission_terminal_cleanup_repair.py` (7 passed)
- Affected regressions: unified terminal / pre-admission persistence / scheduler /
  shared terminal suites — 64 passed + 30 subtests
- Post-repair read-only re-readiness: zero active Scheduler / pre-admission /
  campaign / supervision / discovery / factory / lease residue; migrations 58 /
  head `058_direct_pump_migration_cursor.sql`; locked capability baseline intact;
  D4/D5 + Solana-native + Repairs 4–6 lineage remain closed

## Authorization posture

Do **not** create a new 4/2/2 authorization from this handoff alone as an
automatic next step unless the operator explicitly starts the authorization-
design lane.

Do **not** run Printer from this handoff.
Do **not** reuse any consumed authorization or historical application artifact.

## Exact next permitted action

`V2-9.8B Fresh 4/2/2 Authorization Design`

Design/specification only for a new execution identity bound to the repaired
HEAD and current authoritative DB SHA. It must not execute a campaign, contact
providers/RPC, or unlock retrieval/financial capabilities.

## Locks

Solana-only; Solana memecoin-only; paper-only. No live wallet/private keys/signing/real funds/live execution. No paid API dependency. No scoring/ranking/confidence/weighted logic. No embeddings/vectors. No Source Governor or Central Scheduler bypass. No dirty-memory retrieval/decision use. Retrieval, BUY/SELL/HOLD, positions, trade events, paper audits and PnL remain locked. `WINDOW_5M_MICRO_EVENT` remains support-only. 12h/24h remain locked. No Migration 059.

The 4/2/2 contract remains: 4 total tokens; 2 cycles; 2 tokens per cycle; Cycle 2 fresh/disjoint from Cycle 1; freeze minimum depth 4; exact-pool liquidity floor `$3,000`; minimum spacing `300s`; `WINDOW_15M` root; lawful token-local `15m -> 1h -> 4h`; retries `0`; endpoint rotation `false`; one-shot only; no rerun/resume/restart/successor.

The active authority stack wins any conflict with this handoff.
