# Printer V1 V2-9.1 Proof-DB Schema Readiness Repair Closeout

## Status

Lane: `V2-9.1 - Proof-DB Schema Readiness Repair`

Verdict: `V2_9_1_PROOF_DB_SCHEMA_READINESS_PASS`

V2-9.1 repaired and verified only the isolated proof-DB preparation boundary.
No source transport, scheduler runtime, V2-9 proof, 12h/24h work, retrieval,
paper decision, position, trade, audit, or PnL path ran.

## Audit Finding

The missing schema already had one canonical owner:

- `migrations/028_memory_factory_run_ledger.sql` creates
  `printer_memory_factory_runs` and `printer_memory_factory_run_steps`;
- the same migration owns their columns, `WINDOW_15M` and `PROOF_ONLY`
  checks, unique keys, foreign keys, and three named indexes; and
- migration 029 is the current latest canonical migration.

The canonical persistent DB at the V2-9 baseline recorded 24 applied migrations,
ending at `024_discovery_source_channel.sql`. It therefore did not contain
migrations 025 through 029, including migration 028.

The blocked V2-9 preparation copied the persistent DB directly to the proof and
backup paths but did not call the canonical migration runner on the proof copy.
That skipped the existing run-ledger migration. Temporary factory and V2-8.1
tests did not expose the gap because their setup calls `apply_migrations()`
before using the DB or creating its backup.

No duplicate migration or ad hoc production schema SQL was added.

## Repair

The new `printer-prepare-v2-9-proof-db` path:

1. requires explicit operator approval at the CLI boundary;
2. rejects the canonical persistent DB as a proof or backup target;
3. requires distinct, fresh persistent, proof, and backup paths;
4. copies the persistent DB to the isolated proof path;
5. applies every SQL file in the canonical migration directory to the proof only;
6. requires canonical migration 028 to exist;
7. validates migration state and rejects missing or unknown ledger entries;
8. validates SQLite integrity and foreign-key integrity;
9. validates both run-ledger tables, required columns, NOT NULL constraints,
   unique keys, named indexes, check constraints, and foreign keys;
10. compares all critical proof row counts with the persistent baseline;
11. verifies the persistent hash and critical counts did not change;
12. creates the backup only after proof migration and validation succeed;
13. validates the backup and requires it to be byte-identical to the proof; and
14. reports that neither sources nor scheduler runtime ran.

The one-command runtime schema gate now uses the same complete validator. A DB
with only the table names, incomplete migrations, missing indexes, ambiguous
migration entries, or broken constraints fails before discovery or runtime.

## Temporary-DB Proofs

Ten focused V2-9.1 tests proved:

- a canonical migration-024 DB copy becomes current and runtime-ready only in
  the isolated proof copy;
- both run-ledger tables are created through migration 028;
- migration 029 and the full current migration ledger are present;
- all V2-8.1 run-ledger columns, indexes, checks, unique keys, and foreign keys
  validate;
- canonical migration application is idempotent;
- the persistent fixture hash and critical counts remain unchanged;
- the validated backup is byte-identical to the proof;
- missing migration 028 blocks before the proof copy is created;
- a failed migration creates no backup;
- an incomplete migration blocks both backup creation and the runtime gate;
- a missing required runtime index blocks the runtime gate;
- non-fresh, overlapping, or canonical-persistent proof targets are rejected;
- operator approval is required before copying; and
- source, scheduler, memory, retrieval, and financial row counts remain zero.

## Regression Verification

Final passing checks:

- V2-9.1 schema readiness: `10 passed`;
- canonical database schema/migration idempotency: `9 passed`;
- persistent local DB bootstrap: `10 passed`;
- V2-8.1 one-token 4h runtime fixtures/replay: `6 passed, 2 subtests passed`;
- one-command factory replay and DB isolation: `16 passed`;
- continuous lifecycle runtime integration: `8 passed`;
- focused Lane K/E2Z hard-lock checks: `27 passed, 100 deselected`;
- Python compilation: passed; and
- `git diff --check`: passed.

Two historical migration tests were corrected to expect the already-existing
canonical 028 and 029 migrations rather than stale 024/027 endpoints. No test
was weakened.

## Persistent DB Verification

The real persistent DB was read only.

SHA-256 before and after this repair:

`97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB`

Critical counts remained unchanged:

- source requests / responses / failures: `1118 / 1071 / 47`;
- scheduler jobs: `989`;
- token snapshots: `1012`;
- memory windows / fingerprints: `156 / 23`;
- retrieval queries / matches: `10 / 0`;
- paper decisions: `2`;
- paper positions / trade events / trade audits: `0 / 0 / 0`;
- run-ledger runs / steps: `0 / 0`.

Existing historical rows are baseline state, not V2-9.1 output. Every persistent
delta is zero.

## Files Changed

- `src/printer_v1/operator_cli/proof_db_schema_readiness.py`
- `src/printer_v1/operator_cli/one_command_15m_factory.py`
- `pyproject.toml`
- `tests/test_v2_9_1_proof_db_schema_readiness.py`
- `tests/test_phase1_database_schema.py`
- `tests/test_phase18_6_persistent_local_db_bootstrap.py`
- this closeout

## What Was Built

- One reusable, operator-approved proof-DB preparation command.
- One shared full runtime-schema validator.
- Fail-closed migration, isolation, validation, backup, and persistent-preservation
  checks.
- Focused temporary-DB repair and regression coverage.

## What Was Not Touched

- The canonical persistent DB schema or contents.
- Canonical migration SQL.
- Source Governor, source adapters, endpoints, budgets, retries, or rotation.
- Central Scheduler runtime or scheduler policy.
- 4h cadence, continuity, quality, cleanup, or replay policy.
- V2-9 runtime proof execution.
- 12h/24h work.
- Retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.
- Wallet, private-key, signing, live-execution, paid-source, scoring, ranking,
  confidence, weighted, embedding, or vector logic.

## Functionality Risks / Setbacks / Efficiency Blockers

1. A failed canonical migration can leave a partial proof file. The repair
   deliberately withholds the backup and the fresh-path rule prevents that file
   from being reused silently; the operator must discard it before a later
   separately approved preparation.
2. The canonical persistent DB remains on migration 024 by design. Future proof
   preparation must use this repaired path; raw file copy remains insufficient.
3. This lane proves schema readiness only. It does not prove real 4h source
   latency, rate limits, cadence, context freshness, cleanup, replay, or quality.
4. The preparation CLI does not start the proof. A separate operator decision is
   still required.
5. The desktop `apply_patch` helper was unavailable during this lane, so exact
   scoped local-writer fallbacks were used and then verified by compilation,
   focused tests, and Git diff checks.

## Pass/Fail Status

`V2_9_1_PROOF_DB_SCHEMA_READINESS_PASS`

The existing canonical migrations are now applied and fully validated on the
isolated proof copy before backup creation or runtime eligibility. Failure paths
remain closed, the persistent DB remains unchanged, and all locks hold.

## Next Recommended Phase

Stop for operator review. A new, separately operator-approved V2-9 proof may be
considered after this PASS closeout. Do not rerun V2-9 automatically and do not
begin V2-10, 12h, or 24h work.
