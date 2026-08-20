# CURRENT HANDOFF

Date: 2026-08-20

## Current lane

`V2-9.8B Factory-Run Terminal Cleanup Product Repair`

Status: `CLOSED_PASS`

Verdict:

`V2_9_8B_FACTORY_RUN_TERMINAL_CLEANUP_PRODUCT_REPAIR_PASS`

Boundary evidence:

- authoritative DB mutation: **NO**
- historical orphan reconciled: **NO**
- provider/runtime calls: **NO**
- orphan `ad5a83e6-9830-4c6b-8150-66445f54c8cc` remains `RUNNING`
- authoritative DB SHA unchanged:
  `f167858a7a47c2837bced97223501f8d1c004d1c8c7a8177ed080c4e8d27f341`

## Exact branch / HEAD

Branch:

`agent/v2-9-8b-factory-run-terminal-cleanup-product-repair`

Final repaired product HEAD / candidate launch identity:

`6c44d5140bb79d032ad6a78e81eb8c77540371c8`

Product repair commit:

`d42a5aa5b5b27e79bb843babee4cbd91d9280af2`

Baseline:

`28e9d44c14c7eefcc6b2210922e6456e0f39ff3c`

Historical pre-repair executable provenance (do **not** use for next authorization):

`9cfa8a152c3a02c0c5ef599cf0cffe6e269ab885`

## Defects repaired

1. `campaign_active_work_report(...).clean_terminal` is false while the exact
   linked factory run is `PENDING`/`RUNNING` (`active_factory_runs` counted).
2. `finalize_four_token_shared_terminal` no longer early-returns from an
   already-terminal campaign/run while its linked factory remains active; it
   routes cleanup through the existing canonical terminal owner.
3. `_finalize_returned_pre_lifecycle_result` resolves and passes the exact linked
   `factory_run_id` when an authoritative factory exists; `None` remains lawful
   only when no factory was ever linked.

Preserved:

- `_active_counts()` factory-run visibility repair
- `reconcile_campaign_terminal` as the sole factory terminal owner
- failed-campaign factory transition `RUNNING -> SAFE_STOPPED`
- first terminal cause / existing stop_reason preservation
- Scheduler/pre-admission cleanup ownership

## Proof summary

Focused disposable suite:

`tests/test_v2_9_8b_factory_run_terminal_cleanup_product_repair.py`

Adjacent regressions (factory/shared terminal, pre-admission cleanup, unified
terminal, active-count visibility): **68 passed + 30 subtests**.

## Authorization posture

Do **not** create a fresh 4/2/2 authorization yet.

The next authorization must bind:

- launch Git HEAD = this repaired product HEAD (not `9cfa8a…`)
- DB SHA = the post-orphan-reconciliation SHA (not yet changed)

The existing fresh 4/2/2 authorization design needs only a narrow identity
refresh/rebind after orphan reconciliation.

## Exact next permitted action

`V2-9.8B One-Time Historical Orphan Factory-Run Reconciliation`

Reconcile exactly:

`printer_memory_factory_runs.run_id = ad5a83e6-9830-4c6b-8150-66445f54c8cc`

through the existing canonical terminal owner
(`RUNNING -> SAFE_STOPPED`), with backup/restore proof, then remeasure the
authoritative DB SHA for the later authorization identity refresh.

## Locks

Solana-only; Solana memecoin-only; paper-only. No live wallet/private keys/signing/real funds/live execution. No paid API dependency. No scoring/ranking/confidence/weighted logic. No embeddings/vectors. No Source Governor or Central Scheduler bypass. No dirty-memory retrieval/decision use. Retrieval, BUY/SELL/HOLD, positions, trade events, paper audits and PnL remain locked. `WINDOW_5M_MICRO_EVENT` remains support-only. 12h/24h remain locked. No Migration 059.

The active authority stack wins any conflict with this handoff.
