# CURRENT HANDOFF

Date: 2026-08-20

## Current lane

`V2-9.8B Orphan Factory-Run Residual Reconciliation`

Status: `BLOCKED_PRODUCT_DEFECT_BEFORE_DB_MUTATION`

Verdict:

`PRODUCT_TERMINAL_CLEANUP_DEFECT_REQUIRES_REPAIR`

Separate findings:

- historical DB residue repaired: **NO** (authoritative mutation withheld)
- production terminal-cleanup defect found: **YES**
- zero-state / readiness visibility defect found: **YES** (narrow readiness helper repaired)
- active factory runs after: **1** (unchanged)
- authoritative DB SHA unchanged:
  `f167858a7a47c2837bced97223501f8d1c004d1c8c7a8177ed080c4e8d27f341`

No authorization was created or consumed. Printer was not run.

## Exact branch / HEAD

Branch:

`agent/v2-9-8b-orphan-factory-run-residual-reconciliation`

Authorized product baseline HEAD (unchanged launch identity):

`9cfa8a152c3a02c0c5ef599cf0cffe6e269ab885`

## Classification of orphan

Exact orphan:

- `printer_memory_factory_runs.run_id = ad5a83e6-9830-4c6b-8150-66445f54c8cc`
- `run_status = RUNNING`
- only active factory-run row
- linked campaign / campaign-run already `TERMINAL_FAILED`
- terminal cause:
  `OPERATIONAL_CAMPAIGN_FAILED:FourTokenFactoryAdapterError`
- factory steps: 18 `SUCCEEDED`, zero active
- Scheduler / pre-admission / discovery / supervision / lease residue: already zero

`reconcile_campaign_terminal(..., factory_run_id=..., run_status="FAILED")`
already maps this row lawfully to `SAFE_STOPPED` while preserving the campaign
terminal cause when invoked with the factory id.

## Why prior re-readiness reported zero factory residue

`operational_memory_factory_command._active_counts()` counted:

- `factory_run_steps` PENDING/RUNNING

but did **not** count:

- `printer_memory_factory_runs.run_status IN ('PENDING','RUNNING')`

So an orphan RUNNING factory with only SUCCEEDED steps looked quiescent to
readiness, while the strict four-token zero-state gate correctly reported
`active_factory_runs: 1`.

## Visibility repair landed in this lane

`_active_counts()` now includes `factory_runs` with the same PENDING/RUNNING
contract as the strict zero-state gate.

Focused proof:

`tests/test_v2_9_8b_active_counts_factory_run_visibility.py`

Authoritative DB was not mutated.

## Production terminal-cleanup defect (DB mutation blocked)

Do **not** one-row-clean the authoritative orphan yet. Current production can
still recreate or preserve the same condition:

1. `four_token_factory_adapter` returns early when the campaign run is already
   `TERMINAL_*` and does not require the linked factory run to be non-RUNNING.
2. `campaign_active_work_report(...).clean_terminal` does not treat a RUNNING
   factory run as unclean when steps are terminal.
3. At least one operational reconcile caller still passes
   `factory_run_id=None` on a failure path
   (`operational_memory_factory_command` pre-lifecycle reconciliation).

Hiding those with a historical row update would leave the defect live.

## Authorization posture

Do **not** create a fresh 4/2/2 authorization while:

- `active_factory_runs != 0`, or
- the production terminal-cleanup defect above remains unrepaired.

## Exact next permitted action

`V2-9.8B Factory-Run Terminal Cleanup Product Repair`

Repair the production paths so a campaign terminal cannot leave
`printer_memory_factory_runs.run_status='RUNNING'`, and so
`campaign_active_work_report` / shared-terminal already-terminal handling cannot
treat that orphan as clean.

Only after that product repair + focused proofs may the operator authorize the
exact one-time authoritative reconciliation of
`ad5a83e6-9830-4c6b-8150-66445f54c8cc`, then retry:

`V2-9.8B Fresh 4/2/2 Authorization Creation`

against launch HEAD `9cfa8a…` and the then-current DB SHA.

## Locks

Solana-only; Solana memecoin-only; paper-only. No live wallet/private keys/signing/real funds/live execution. No paid API dependency. No scoring/ranking/confidence/weighted logic. No embeddings/vectors. No Source Governor or Central Scheduler bypass. No dirty-memory retrieval/decision use. Retrieval, BUY/SELL/HOLD, positions, trade events, paper audits and PnL remain locked. `WINDOW_5M_MICRO_EVENT` remains support-only. 12h/24h remain locked. No Migration 059.

The active authority stack wins any conflict with this handoff.
