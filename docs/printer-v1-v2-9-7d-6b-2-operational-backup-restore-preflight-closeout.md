# V2-9.7D.6B.2 Operational Backup/Restore Preflight Closeout

## Result

V2-9.7D.6B.2 adds a fail-closed, file-oriented operational backup and
disposable restore-rehearsal API. Verification used disposable fixture
databases only. `data/printer_v1.sqlite3` was not opened, copied, migrated, or
modified.

## Money-Usefulness Contribution

Later operational memory growth is useful only if its existing corpus can be
recovered without silent truncation, cross-target mistakes, or destructive
migration. This preflight records the exact source identity and data shape,
proves a byte-identical backup, rehearses migration through 032 away from the
source, and prevents an unverified or partial artifact from becoming the
recovery basis. It creates no memory and authorizes no financial action.

## What 6B.2 Improves

- Requires the resolved persistent-target path and exact `sha256:` content
  identity supplied by the caller.
- Rejects active SQLite writers and visible WAL, shared-memory, or rollback-
  journal sidecars before copying.
- Records source size, SHA-256, ordered migration ledger, operational critical
  row counts, integrity results, and foreign-key results.
- Holds SQLite's immediate writer reservation while copying and validating the
  source snapshot.
- Creates the temporary backup in the final backup directory, verifies its
  bytes and metadata, and publishes with same-volume `os.link` no-overwrite
  semantics.
- Restores only to a fresh direct child of an explicit disposable root, proves
  byte identity before migration, applies canonical migrations through 032,
  and validates the restored runtime schema, ledger, counts, integrity, and
  foreign keys.
- Never replaces or deletes a published backup. An interrupted or failed later
  attempt removes only its unpublished temporary file and disposable restore.
- Returns explicit zero-source, zero-scheduler-runtime, and zero-source-write
  evidence.

## What Remains Locked

Persistent-target migration, operational command exposure, backup scheduling,
retention policy, B.1/B.2 adapters, lifecycle rotation, operational lease and
runtime, source calls, memory generation, final reporting, replay, retrieval,
decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, wallets, signing, and
live execution remain locked. 6B.3 was not started.

## Proof Completed

- exact source path and SHA-256 identity mismatch block before artifacts;
- source metadata includes size, hash, ledger, critical counts, integrity, and
  foreign-key results;
- an active writer and visible WAL state block without publication;
- the verified backup size, hash, and bytes match the source;
- interrupted copy and hash mismatch publish no backup;
- existing backup and restore targets are never overwritten;
- a disposable restore reaches migration 032 with valid schema, ledger,
  critical counts, integrity, and foreign keys;
- source bytes, hash, size, metadata, and seeded rows remain unchanged;
- a prior verified backup survives a failed later attempt;
- separate repeated runs produce identical evidence for identical source
  inputs, while artifact reuse fails closed; and
- no source, scheduler runtime, retrieval, or financial behavior runs.

## Functionality Risks / Setbacks / Efficiency Blockers

- The preflight conservatively blocks whenever `-wal`, `-shm`, or `-journal`
  exists. An operator must establish a closed, checkpointed SQLite state before
  this API can pass; this lane intentionally does not checkpoint or delete
  source sidecars.
- SQLite's immediate reservation proves writer exclusion during the snapshot,
  but it is not the future campaign-scoped B.4 operational lease. Runtime
  ownership remains a later lane.
- Atomic publication uses a same-volume hard link. A filesystem that does not
  support hard links fails closed rather than falling back to an overwrite-
  capable rename or a visible partial copy.
- The preflight returns evidence to its caller but does not persist a campaign
  prerequisite record. Final immutable prerequisite/report wiring remains a
  later Slice 6 responsibility.
- Source-failure request linkage remains limited by the existing authoritative
  schema noted in 6B.1; this preflight records row counts, not inferred
  relationships.

## Scope Confirmation

No persistent target, existing backup, source adapter, scheduler job, lifecycle
record, memory row, campaign runtime, command surface, replay, retrieval row, or
financial-capability row was created or modified. Only disposable database
fixtures were used.
