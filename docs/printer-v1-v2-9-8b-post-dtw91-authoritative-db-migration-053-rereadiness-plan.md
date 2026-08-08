# Printer V1 V2-9.8B — Post-DTW91 Authoritative DB Migration 053 Rereadiness Plan

## Status

`DTW92_AUTHORIZED_REREADINESS_PLAN_READY`

## Baseline

- DTW-91 closeout: `b7896671c202f6b5af460134f7e817f2767da4fe`
- DTW-91 verdict: `V2_9_8B_POST_DTW90_READINESS_ROUTE_MIGRATION_053_BOUNDED_PROOF_PASS`
- Rereadiness branch: `agent/v2-9-8b-post-dtw91-authoritative-db-migration-053-rereadiness`
- Canonical migration: `migrations/053_pilot_input_readiness_route_domain.sql`
- Migration Git blob SHA: `571fde8ff9b69065d609cecb99bb65afeae67732`
- Canonical code migration head before authoritative application: 053
- Last observed authoritative Mac DB migration head: 052

## Operator authorization

The operator explicitly approved proceeding with the authoritative DB / operational rereadiness lane after DTW-91 PASS.

This approval permits one guarded authoritative schema migration from canonical 052 to canonical 053 only after all preconditions and a verified repository-owned backup/disposable-restore rehearsal pass.

It does not authorize Printer runtime, source work, discovery, memory generation, WINDOW_15M execution or any downstream capability.

## Expected pre-migration authoritative DB identity

Last authoritative identity recorded after the consumed DTW-83 attempt and DTW-84 read-only audit:

- path: `/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3`
- SHA-256: `3614c99cf4b2d501b6a46ed92ebc784e297261fcf443e316c181f5941d95c603`
- size: `70045696`
- inode: `1230526`
- mtime_ns: `1786209702000684860`
- migration count: `52`
- migration head: `052_memory_observation_eligibility_layers.sql`

The local migration procedure must fail closed before backup or mutation if this identity no longer matches. No attempt should normalize or silently accept drift.

## Required sequence

1. Align local Git to this exact tracked plan commit after it is created.
2. Require clean tracked/index state and no SQLite sidecars.
3. Verify authoritative DB exact pre-migration identity, integrity/FK and migration 52 ledger.
4. Verify all operational state is terminal and no active/locked Scheduler/campaign work exists.
5. Use repository-owned `operational_backup_restore_preflight` to create the backup and disposable restore.
6. Require source unchanged, backup/restore READY, and disposable restore successfully reaches canonical migration 053 with integrity/FK and exact migration ledger PASS.
7. Preserve the verified pre-053 backup as the rollback anchor.
8. Apply canonical migration 053 exactly once to the authoritative DB through repository `apply_migrations()`.
9. Verify post-migration ledger count/head 53/`053_pilot_input_readiness_route_domain.sql`, integrity/FK, table/index/trigger contract and historical readiness row/value/hash preservation.
10. Verify all operational state remains terminal, configured source is still approved, and the zero-I/O concrete WINDOW_15M composition preflight passes.
11. Write an explicit local application receipt/evidence artifact and stop before any new authorization.

## Failure posture

Any mismatch before application blocks the lane without modifying the authoritative database.

If migration application or a mandatory post-check fails, do not rerun migration and do not manually edit schema objects or `printer_schema_migrations`. Preserve the first failure and verified rollback anchor and follow the repository backup/restore reconciliation posture.

## Permanent locks

Still prohibited:

- source fetching;
- discovery runs;
- Printer operational campaign/runtime;
- Scheduler runtime;
- authorization creation/consumption;
- real `WINDOW_15M`;
- `WINDOW_1H`/4h/12h/24h;
- memory generation;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- paper positions;
- trade events/audits;
- PnL;
- live wallet/private keys/real funds/live execution.

## Money-usefulness contribution

This safely upgrades the authoritative corpus so valid market-present Solana memecoin candidates can retain truthful memory-observation route identity at the durable readiness boundary instead of being lost at SQLite persistence.

## Functionality Risks / Setbacks / Efficiency Blockers

- authoritative DB mutation is irreversible without a verified rollback restore, so the backup/restore rehearsal is mandatory;
- any current DB identity drift invalidates the known pre-migration anchor and blocks application;
- migration 053 changes the canonical ledger identity and therefore requires exact post-migration readiness proof;
- no live proof or authorization is permitted in this lane even if migration succeeds.
