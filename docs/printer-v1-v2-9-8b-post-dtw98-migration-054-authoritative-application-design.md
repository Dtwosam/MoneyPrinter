# Printer V1 — V2-9.8B Post-DTW98 Migration 054 Authoritative Application Design

## Verdict

`V2_9_8B_POST_DTW98_MIGRATION_054_AUTHORITATIVE_APPLICATION_DESIGN_PASS`

This design authorizes only a future single bounded application of `054_pre_lifecycle_discovery_refresh_wait.sql` after an exact pre-application gate. It does not itself mutate the authoritative database and does not authorize WINDOW_15M runtime.

## Baseline

- migration-054 readiness closeout: `144d1831abd39302318023efb705288c5e2a8eb6`
- readiness verdict: `V2_9_8B_POST_DTW98_MIGRATION_054_AUTHORITATIVE_READINESS_CLOSEOUT_PASS`
- application-design branch: `agent/v2-9-8b-post-dtw98-migration-054-authoritative-application-design`

## Purpose

Apply exactly one already-proven forward migration to the authoritative Printer V1 SQLite database so the ratified temporal-persistence implementation has its required durable pending-refresh ownership table before any future authorization can be prepared.

## Frozen pre-application trust root

The application must refuse to start unless all of these still match:

- authoritative DB path: `/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3`
- SHA-256: `14b4e82b9f7118aa82e9b903e010195a16c10c77d014d7dc3571bb95cc83e5bc`
- size: `74715136`
- inode: `1230526`
- mtime_ns: `1786281184448521896`
- migration count: `53`
- migration head: `053_pilot_input_readiness_route_domain.sql`
- migration-ledger digest: `7431c09f51fd30fefaa6266bbbcd1049e1a8349f12bdb55c468e3b4088208bf1`
- integrity: `ok`
- FK violations: `0`
- no `-wal`, `-shm`, or `-journal` sidecars
- all active campaign/run/supervision/discovery/factory/Scheduler/proof counts zero
- no active Printer/WINDOW_15M process
- locked capability baseline PASS
- historical null-position paper-audit row count exactly `1`

Any drift requires `STOP_AND_REAUDIT`; do not repair in the application command.

## Exact Git/catalogue gate

Immediately before mutation:

- current Git branch/HEAD must equal the frozen application branch/head created from this design closeout;
- tracked tree must be clean;
- canonical migration catalogue must be valid;
- canonical count must be `54`;
- canonical head must be `054_pre_lifecycle_discovery_refresh_wait.sql`;
- authoritative applied ledger must be exactly canonical ordered prefix `001..053`;
- exactly one migration must be pending and it must be 054;
- migration file blob/content must match the committed design-reviewed migration;
- target table `printer_pre_lifecycle_discovery_refresh_waits` must not already exist.

Because `apply_migrations()` applies every pending canonical migration, any second pending migration or catalogue drift blocks the operation.

## Backup contract

Before mutation create one immutable pre-migration backup outside the repository under:

`$HOME/PrinterOperations/v2-9-8/migration-054-authoritative-application/<APPLICATION_ID>/`

Required files:

- `pre-migration-printer-v1.sqlite3`
- `application-evidence.json`

Backup requirements:

- source authoritative DB identity rechecked immediately before copy;
- normal byte copy only while no sidecars/runtime exist;
- backup SHA-256 and size must equal the authoritative pre-migration file exactly;
- backup is never opened read-write during application;
- application evidence records source path/identity, backup path/identity, Git identity, canonical migration facts, started/completed timestamps and terminal verdict.

No automatic restore is permitted. A failed post-apply proof stops for operator review; rollback must be a separately reviewed action because restoring a backup is itself an authoritative mutation.

## Canonical migration owner

Use only:

`printer_v1.db.migrate.apply_migrations(authoritative_db_path)`

Do not execute migration SQL ad hoc and do not insert the ledger row manually.

The call is permitted exactly once after all pre-application gates and backup checks pass.

## Expected mutation

Only the canonical migration-owned schema/ledger delta is permitted:

- add `printer_pre_lifecycle_discovery_refresh_waits`;
- add `idx_pre_lifecycle_refresh_wait_scope`;
- add `idx_pre_lifecycle_refresh_wait_job`;
- add `printer_pre_lifecycle_refresh_wait_identity_immutable`;
- add `printer_pre_lifecycle_refresh_wait_no_terminal_reopen`;
- append exactly one ledger row: `054_pre_lifecycle_discovery_refresh_wait.sql`.

The new table must contain zero rows immediately after migration.

No campaign, Scheduler, source, memory, retrieval, paper or financial row may be created by this application.

## Immediate post-application proof

Using a fresh read-only connection after `apply_migrations()` closes:

1. no SQLite sidecars remain;
2. `PRAGMA integrity_check` returns exactly `ok`;
3. `PRAGMA foreign_key_check` returns zero rows;
4. migration count is exactly `54`;
5. migration head is exactly 054;
6. applied ordered ledger exactly equals canonical ordered catalogue;
7. ledger digest equals canonical digest;
8. migration-054 table, two indexes and two triggers exist;
9. migration-054 table row count is `0`;
10. all active runtime/Scheduler counts remain zero;
11. locked capability baseline remains PASS;
12. historical null-position paper-audit row remains exactly `1`;
13. zero source calls, zero Scheduler runtime calls, zero authorization creation, zero Printer/WINDOW activity occurred.

Record the exact post-application DB SHA-256, size, inode, mtime_ns, count, head and ledger digest. This becomes the only valid DB identity for the later rereadiness lane.

## Failure semantics

### Before `apply_migrations()`

Any failed gate must leave the authoritative DB byte-identical and return a blocked verdict. No retry inside the command.

### During or after `apply_migrations()`

If the migration call raises or any post-apply proof fails:

- do not run `apply_migrations()` again automatically;
- do not create an authorization;
- do not start Printer runtime;
- preserve the pre-migration backup and application evidence;
- record observed post-failure DB identity and stop for a dedicated forensic/rollback review.

A process exit code alone never establishes success.

## Required application result

PASS requires a structured result containing at minimum:

- application ID;
- exact pre-DB identity;
- exact backup identity;
- exact post-DB identity;
- Git branch/HEAD;
- migration file/content identity;
- pre/post ledger facts;
- integrity/FK facts;
- schema object presence;
- active residue/capability facts;
- zero-I/O/runtime/auth facts;
- `migration_application_attempts: 1`;
- `automatic_retry_created: false`;
- `authorization_created: false`;
- `printer_runtime_started: false`;
- `window_15m_started: false`.

PASS verdict:

`V2_9_8B_POST_DTW98_MIGRATION_054_AUTHORITATIVE_APPLICATION_PASS`

## Money-usefulness contribution

Applying 054 makes the proven temporal-persistence behavior durably representable in the authoritative database. It enables a future campaign to wait safely for fresh eligible supply without sacrificing the four-token memory-quality gate or burning repeated one-use authorizations at an instantaneous 3/4 reserve.

## What this design improves

- gives the temporal refresh wait exact durable campaign/Scheduler ownership;
- preserves canonical migration and ledger discipline;
- creates a recoverable pre-migration trust point;
- separates schema mutation from runtime and authorization activity.

## What this design still does not unlock

Migration application alone does not authorize WINDOW_15M, source fetching, memory generation, WINDOW_1H+, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, wallets, keys, real funds, paid APIs, scoring/ranking/confidence/weighted systems, embeddings or vectors.

## Functionality Risks / Setbacks / Efficiency Blockers

- this is an authoritative DB mutation, so stale pre-identity or active runtime must fail closed;
- `apply_migrations()` applies all pending migrations, making the sole-pending-054 check mandatory;
- post-migration file SHA/size/mtime will legitimately change and must be re-anchored before later authorization work;
- automatic backup restore is intentionally forbidden because it could overwrite valid post-failure forensic state;
- test fixtures frozen at migration 052 remain a separate maintenance issue and must not weaken migration guards;
- successful schema application still requires application closeout and fresh post-migration rereadiness before any authorization.

## Next lane

`V2-9.8B Post-DTW98 Migration 054 Authoritative Application`

That lane may perform exactly one bounded authoritative migration application under this design. It may not run Printer or create a WINDOW_15M authorization.