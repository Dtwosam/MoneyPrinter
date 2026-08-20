# CURRENT HANDOFF

Date: 2026-08-20

## Current lane

`V2-9.8B One-Time Historical Orphan Factory-Run Reconciliation`

Status: `BLOCKED_PRODUCT_DEFECT_BEFORE_AUTHORITATIVE_MUTATION`

Verdict:

`PRODUCT_TERMINAL_CLEANUP_DEFECT_REQUIRES_REPAIR`

Boundary evidence:

- `ORPHAN_RECONCILED: NO`
- `ACTIVE_FACTORY_RUNS: 1`
- `AUTHORIZATION_CREATED: NO`
- `PRINTER_EXECUTED: NO`
- authoritative DB SHA unchanged:
  `f167858a7a47c2837bced97223501f8d1c004d1c8c7a8177ed080c4e8d27f341`
- orphan `ad5a83e6-9830-4c6b-8150-66445f54c8cc` remains `RUNNING`
- verified backup preserved (no authoritative write occurred):
  `operator-runs/v2-9-8b-historical-orphan-factory-run-reconciliation/RECONCILE_20260820T185845Z/verified-backup.sqlite3`

## Exact branch / HEAD

Branch:

`agent/v2-9-8b-historical-orphan-factory-run-reconciliation`

HEAD:

`cd6c2fed552ffb9753f61a7a33afd3118efff869`

Product repair ancestry present:

`d42a5aa5b5b27e79bb843babee4cbd91d9280af2`

## What was proved before mutation

All preflight gates passed:

- only active factory run = orphan id above
- linked campaign/run = `TERMINAL_FAILED`
- first terminal cause =
  `OPERATIONAL_CAMPAIGN_FAILED:FourTokenFactoryAdapterError`
- factory steps = 18 `SUCCEEDED`
- other active residue = 0
- integrity `ok`; FK 0; migrations 58 / `058_...`
- DB SHA exact match
- backup/restore preflight `OPERATIONAL_BACKUP_RESTORE_PREFLIGHT_READY`

## Why canonical reconcile cannot finish this orphan

`reconcile_campaign_terminal(..., factory_run_id=...)` updates the factory row to
`SAFE_STOPPED` in the open transaction, then calls `transition_state` for
cycle/run/campaign.

When those records are already terminal, `transition_state` raises immutable /
uses `with connection:` and **rolls back the same connection**, reverting the
factory UPDATE. The report still claims `factory_run=SAFE_STOPPED`, but the DB
row remains `RUNNING`.

Disposable reproduction against the verified backup confirmed:

- report `factory_run=SAFE_STOPPED`
- persisted status remains `RUNNING`
- `clean_terminal=false` / `active_factory_runs=1`

Therefore ad-hoc SQL was not used, and authoritative mutation was withheld.

## Exact next permitted action

`V2-9.8B Reconcile-Campaign-Terminal Already-Terminal Factory Persist Repair`

Minimum product repair:

1. Persist factory terminalization so a later already-terminal
   `transition_state` rollback cannot revert it (for example SAVEPOINT around
   ownership transitions, or commit/skip already-terminal transitions without
   rolling back prior factory work); and
2. Keep report honesty: do not claim `SAFE_STOPPED` unless the factory row is
   actually persisted that way.

Then retry this one-time orphan reconciliation against the same backup identity
/ refreshed preflight.

Do **not** create a 4/2/2 authorization until the orphan is truly
`SAFE_STOPPED` and re-readiness passes.

## Locks

Solana-only; Solana memecoin-only; paper-only. No live wallet/private keys/signing/real funds/live execution. No paid API dependency. No scoring/ranking/confidence/weighted logic. No embeddings/vectors. No Source Governor or Central Scheduler bypass. No dirty-memory retrieval/decision use. Retrieval, BUY/SELL/HOLD, positions, trade events, paper audits and PnL remain locked. `WINDOW_5M_MICRO_EVENT` remains support-only. 12h/24h remain locked. No Migration 059.

The active authority stack wins any conflict with this handoff.
