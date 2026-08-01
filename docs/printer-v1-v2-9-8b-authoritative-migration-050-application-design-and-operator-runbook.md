# Printer V1 V2-9.8B Authoritative Migration 050 Application Design and Operator Runbook

Date: 2026-08-01

Lane:
`V2-9.8B Authoritative Migration 050 Application Design and Operator Runbook`

Type: design/specification only.

Starting HEAD:
`f7ec83aea898cdcb398ef0a2f1b2c757dacb5351`

Starting readiness verdict:
`V2_9_8B_POST_ACCOUNTING_REPAIR_AUTHORITATIVE_WINDOW_15M_CAMPAIGN_READINESS_AUDIT_BLOCKED`

Block class being addressed:
`BLOCKED_AUTHORITATIVE_MIGRATION_050_NOT_APPLIED`

## 1. Verdict

`V2_9_8B_AUTHORITATIVE_MIGRATION_050_APPLICATION_DESIGN_PASS`

This design defines the only permitted authoritative application procedure for
`050_campaign_scheduler_ownership_scope.sql`.

It does not apply migration 050, open the authoritative database for mutation,
run a campaign, contact a provider, generate memory, or unlock any retrieval or
financial capability.

A PASS authorizes only the next independent read-only and documentation-only
final-authorization review.

## 2. Active-source-stack reconciliation

Use this runbook only with:

- `AGENTS.md`;
- `docs/printer-v1-clean-master-spec.md`;
- `docs/printer-v1-post-rc-build-order.md`;
- `docs/printer-v1-memory-factory-guide.md`;
- `docs/printer-v1-current-state-memory-growth-audit.md`;
- `docs/printer-v1-memory-growth-build-order-v2.md`;
- the completed migration design, implementation, bounded proof, and closeout;
- the blocked authoritative readiness audit at the starting HEAD.

The older assistant anchor still records the pre-readiness prohibition on an
authoritative migration. The later blocked readiness audit is the current lane
evidence: it proved that the repaired code cannot safely run against the
pre-050 authoritative schema and named this design as the exact next task.

This design does not alter the permanent V1 roadmap or unlock a campaign. It
adds the missing audit -> design -> final authorization -> bounded application
-> proof -> closeout sequence required by the active build-order pattern.

## 3. Accepted migration evidence

The authoritative application must reuse, not redesign, the accepted migration
chain:

- schema amendment:
  `V2_9_8B_CAMPAIGN_SCHEDULER_OWNERSHIP_SCHEMA_DESIGN_AMENDMENT_PASS`;
- implementation:
  `V2_9_8B_CAMPAIGN_SCHEDULER_OWNERSHIP_SCHEMA_MIGRATION_IMPLEMENTATION_PASS`;
- migration file:
  `migrations/050_campaign_scheduler_ownership_scope.sql`;
- migration Git blob SHA:
  `3a5bf6de05deb202316b6689a2d7f4206359e6e9`;
- controlling disposable proof:
  `V2_9_8B_CAMPAIGN_SCHEDULER_OWNERSHIP_SCHEMA_MIGRATION_BOUNDED_PROOF_PASS`;
- controlling proof execution:
  `V2_9_8B_MIG050_BOUNDED_PROOF_20260801T144740Z_5df7a275`;
- migration closeout:
  `V2_9_8B_CAMPAIGN_SCHEDULER_OWNERSHIP_SCHEMA_MIGRATION_CLOSEOUT_PASS`;
- closeout commit:
  `d0e7298315239cc85ff47155a2922339a9e7a52e`.

The controlling disposable proof established:

- byte-identical source copy before migration;
- ledger transition from 49/049 to 50/050 only;
- integrity `ok` and zero foreign-key violations;
- exact historical-row preservation;
- all four V2 Scheduler ownership scopes;
- rollback on injected migration failures;
- no authoritative DB mutation.

No new migration, schema owner, migration runner, or proof package is permitted
in the authoritative application lane.

## 4. Exact authoritative target and audit snapshot

Authoritative target:

`/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3`

Readiness-audit snapshot:

| Field | Audited value |
| --- | --- |
| SHA-256 | `e13c40892f0c14d4c07960e00218569a536c50c0fc27815049284c3dd2aff5c2` |
| Size | `65,654,784` bytes |
| mtime_ns | `1785510479935495533` |
| Applied migration count | `49` |
| Applied migration tip | `049_candidate_acquisition_integration.sql` |
| Canonical migration count | `50` |
| Canonical migration tip | `050_campaign_scheduler_ownership_scope.sql` |
| Scheduler ownership rows | `0` |
| Duplicate non-null Scheduler-job ownership | `0` |
| Integrity | `ok` |
| Foreign-key violations | `0` |
| SQLite sidecars | absent |

These values are an audit anchor, not permission to assume the database is
unchanged later. Final authorization must freshly re-read filesystem identity,
ledger, schema, row counts, integrity, foreign keys, residue, and sidecars.

Any change from the audit snapshot is a hard stop unless an independent
read-only reconciliation proves the drift is expected and a new design or
authorization explicitly accepts it. Do not silently update the expected hash.

## 5. Application unit and ownership

The application unit is exactly one call to the existing canonical migration
runner at the exact accepted repository commit:

```python
from printer_v1.db import apply_migrations
apply_migrations("data/printer_v1.sqlite3")
```

The repository must contain exactly 50 canonical migration files and the
canonical ledger must end at migration 050 before authorization.

The authoritative pre-application ledger must be the exact canonical prefix of
length 49. Therefore the runner can apply only migration 050.

Do not:

- execute migration SQL manually through the SQLite CLI;
- copy schema from a disposable proof database;
- edit `printer_schema_migrations` directly;
- run a second migration mechanism;
- combine migration application with preflight, campaign runtime, discovery,
  source fetching, report-only replay, memory generation, or cleanup;
- retry automatically after any failure.

One human-approved invocation is one application attempt. Any abnormal exit or
post-check failure ends the attempt and enters the rollback decision path.

## 6. Immutable execution package

The final authorization must reserve one unique execution ID:

```text
V2_9_8B_AUTHORITATIVE_MIG050_<UTC_TIMESTAMP>_<8_HEX>
```

All evidence belongs under one execution-specific directory:

```text
operator-runs/v2-9-8b-authoritative-mig050/<EXECUTION_ID>/
```

Required files:

```text
preflight.json
backup_restore_preflight.json
final_authorization.json
application_stdout.txt
application_stderr.txt
post_migration_proof.json
rollback.json                 # only if rollback is entered
closeout_inputs.json
```

Rules:

- the execution directory must not already exist;
- no generic mutable `proof_summary.json` is controlling;
- no file may be overwritten;
- every JSON artifact must carry the execution ID, exact Git HEAD, DB path,
  source pre-hash, and creation timestamp;
- final closeout may create a pointer only after accepting the exact package;
- failed or superseded attempts remain named and are never deleted or relabelled
  as PASS.

## 7. Final-authorization preconditions

The independent final-authorization review must prove all of the following from
fresh evidence before permitting mutation.

### 7.1 Git and migration identity

- exact repository HEAD pinned by the authorization;
- exact migration blob SHA
  `3a5bf6de05deb202316b6689a2d7f4206359e6e9`;
- tracked worktree and index clean;
- no untracked file under `migrations/`, `src/`, `tests/`, or the execution
  package path;
- canonical migrations exactly 50, ending at 050;
- no later migration file present.

### 7.2 Quiescence and residue

- no Printer operational command or worker running;
- no active campaign, campaign run, supervision, discovery work, factory step,
  proof supervision, Scheduler job, or campaign Scheduler ownership row;
- no locked Scheduler jobs;
- all terminal supervision leases released;
- no campaign lease-lock file;
- no `-wal`, `-shm`, or `-journal` sidecar;
- an exclusive SQLite writer reservation can be acquired with timeout zero.

### 7.3 Database readiness

- target path is exact;
- source SHA/size/mtime freshly recorded;
- source SHA equals the blocked-audit snapshot unless a separately accepted
  reconciliation exists;
- integrity is exactly `ok`;
- foreign-key violations are zero;
- applied ledger is exact canonical prefix 1-49;
- migration 050 is absent;
- duplicate non-null `scheduler_job_id` ownership count is zero;
- pre-050 table has no replacement-table residue;
- critical table row counts and the full preserved-field snapshot of
  `printer_memory_factory_campaign_scheduler_work` are captured.

### 7.4 Capability locks

Fresh baselines must be captured for:

- memory windows and episodes;
- retrieval queries and matches;
- paper decisions and decision audits;
- paper positions;
- trade events and trade audits;
- PnL-related rows;
- provider/source-request counts;
- Scheduler job counts.

The application must have zero deltas in every runtime, memory, retrieval, and
financial table. Only the schema, migration ledger, and SQLite physical layout
may change.

Any failed precondition returns:

`V2_9_8B_AUTHORITATIVE_MIGRATION_050_FINAL_AUTHORIZATION_BLOCKED`

No backup publication or migration application follows a blocked authorization.

## 8. Required backup and restore rehearsal

Use the existing single backup owner:

`operational_backup_restore_preflight()`

Required inputs are the exact authoritative path, its freshly captured
`sha256:<64 hex>` identity, a new same-volume backup path, and a new disposable
restore path.

The existing owner must prove:

- source path and content identity exact;
- no WAL/journal sidecar;
- exclusive writer reservation;
- source integrity and foreign keys healthy;
- byte-identical temporary and published backup;
- no overwrite of an existing backup;
- disposable restore initially byte-identical;
- disposable restore advances through all canonical migrations, including 050;
- restore integrity and foreign keys healthy;
- critical data-row counts unchanged;
- authoritative source SHA, size, and metadata unchanged during preflight.

The published backup path and hash are immutable final-authorization inputs.
The migration must not begin if the verified backup is missing, moved, changed,
or older than the final-authorization evidence.

### 8.1 Rollback rehearsal

Before final authorization, rehearse rollback on a disposable file only:

1. start from the migrated disposable restore produced by the backup preflight;
2. copy the verified pre-050 backup to a new adjacent temporary restore file;
3. verify its SHA and size equal the authoritative pre-hash and size;
4. atomically replace the disposable migrated file with that temporary file;
5. reopen the restored disposable file read-only;
6. prove ledger 49/049, integrity `ok`, zero FK violations, exact critical row
   counts, and exact preserved-field snapshot;
7. prove no temp file or sidecar remains.

Rollback rehearsal must never replace the authoritative database.

## 9. Final authorization record

The final-authorization document and `final_authorization.json` must pin:

- exact authorized Git HEAD and branch;
- migration file and blob SHA;
- execution ID and evidence directory;
- authoritative path, pre-hash, size, mtime, ledger, and schema identity;
- verified backup path, hash, size, and creation time;
- disposable restore path and post-050 proof result;
- rollback-rehearsal result;
- zero active/locked residue result;
- exact application command;
- one-attempt/no-retry rule;
- post-check and rollback stop conditions;
- all capability locks.

Allowed PASS label:

`V2_9_8B_AUTHORITATIVE_MIGRATION_050_FINAL_AUTHORIZATION_PASS`

A PASS authorizes exactly one migration-maintenance invocation. It does not
authorize a campaign or any other application command.

## 10. Bounded application procedure

After final authorization and only on its exact HEAD:

1. verify the final-authorization file and JSON are present and immutable;
2. recalculate the authoritative pre-hash and require exact equality with the
   authorized hash;
3. require the verified backup hash and size still match authorization;
4. repeat sidecar, exclusive-writer, active-work, locked-work, integrity, FK,
   duplicate-job, ledger-prefix, and canonical-count checks;
5. write `application_started_at` to a new evidence file;
6. execute the canonical migration runner once;
7. capture exit code, stdout, and stderr without redacting factual errors;
8. close the migration connection before post-checks;
9. prohibit any second invocation, even if the first appears incomplete;
10. immediately enter post-migration proof.

The application command must run with providers, RPC, WebSockets, discovery,
Scheduler runtime, campaign runtime, and all automation disabled.

## 11. Post-migration proof

Post-proof is read-only and must establish:

### 11.1 Ledger and schema

- applied migration count exactly 50;
- tip exactly `050_campaign_scheduler_ownership_scope.sql`;
- ledger delta exactly `[050_campaign_scheduler_ownership_scope.sql]`;
- no duplicate, reordered, missing, or unexpected migration;
- the rebuilt Scheduler ownership table has the approved columns, CHECKs,
  foreign keys, indexes, and triggers;
- no `__v2_9_8b_050` replacement table or `_mig050_guard_*` residue;
- partial unique Scheduler-job index exists and is unique.

### 11.2 Historical and data preservation

- Scheduler ownership row count unchanged;
- every pre-existing preserved field matches the pre-snapshot in both directions;
- every historical row is `V1_WINDOW_BOUND` with new V2 fields NULL;
- all critical table row counts unchanged;
- memory and episode rows unchanged;
- no historical artifact, marker, report, or no-rerun record rewritten.

### 11.3 Health and safety

- integrity exactly `ok`;
- zero foreign-key violations;
- zero active and locked operational residue;
- all leases released;
- no SQLite sidecar after connection close;
- source/provider/Scheduler-runtime/application-command count zero outside the
  single migration invocation;
- zero memory, retrieval, decision, position, trade, audit, and PnL deltas;
- post-hash, size, and mtime recorded;
- verified backup remains byte-identical to the authorized pre-state.

Post-proof PASS label:

`V2_9_8B_AUTHORITATIVE_MIGRATION_050_APPLICATION_PROOF_PASS`

The proof is schema-maintenance evidence only. It does not prove campaign
readiness.

## 12. Failure and rollback law

Rollback is mandatory when any of these occurs:

- migration command exits nonzero or raises;
- ledger is not exactly 50/050;
- ledger delta is not exactly migration 050;
- integrity or FK check fails;
- schema, index, trigger, or historical preservation differs;
- any critical data, memory, artifact, marker, runtime, retrieval, or financial
  count changes unexpectedly;
- sidecar, temp-table, active-work, locked-work, or lease residue remains;
- evidence identity is incomplete or contradictory.

Do not rerun migration 050 to repair a failed attempt.

Authoritative rollback procedure:

1. stop all Printer processes and require no source or DB writer;
2. record the failed post-state hash and copy it to an immutable quarantine file;
3. verify the authorized backup hash and size again;
4. copy the backup to a new temporary file adjacent to the authoritative DB;
5. fsync and verify the temporary file;
6. atomically replace the authoritative DB with the temporary file;
7. fsync the containing directory;
8. reopen read-only and prove the exact authorized pre-hash, size, ledger 49/049,
   integrity `ok`, zero FK violations, critical row counts, and preserved-field
   snapshot;
9. prove no sidecar or temporary file remains;
10. write `rollback.json` and stop.

A successful rollback verdict is:

`V2_9_8B_AUTHORITATIVE_MIGRATION_050_APPLICATION_ROLLED_BACK_SAFE`

Rollback does not convert the failed application to PASS and does not authorize a
retry. A new attempt requires a new audit, design reconciliation, backup,
authorization, and execution ID.

If rollback cannot be proven exact, return:

`V2_9_8B_AUTHORITATIVE_MIGRATION_050_ROLLBACK_BLOCKED_OPERATOR_INTERVENTION_REQUIRED`

No campaign or other DB mutation is permitted.

## 13. Closeout and next lane

After a clean post-migration proof, perform an independent documentation-only
closeout. It must reconcile the exact application package, backup identity,
ledger/schema result, post-hash, data preservation, zero forbidden deltas, and
absence of rollback.

Allowed closeout PASS label:

`V2_9_8B_AUTHORITATIVE_MIGRATION_050_APPLICATION_CLOSEOUT_PASS`

Only that closeout may authorize a repeat:

`V2-9.8B Post-Migration Authoritative WINDOW_15M Campaign Readiness Audit`

That repeat audit remains read-only. It must not directly run a campaign.
Campaign design and final authorization remain separate later steps.

## 14. Money-usefulness contribution

This design protects future paper-only money usefulness by ensuring the
authoritative database can store exact stage-scoped Scheduler ownership before
new `WINDOW_15M` memory is created.

It prevents hidden work, double-counted Scheduler jobs, invented ownership, and
historical V1 evidence from being treated as repaired V2 proof. It makes no
profit claim and creates no trading capability.

## 15. What this design improves

- turns the readiness blocker into one bounded schema-maintenance procedure;
- reuses the proven migration and canonical migration runner;
- requires a fresh byte-identical backup and disposable restore rehearsal;
- separates authorization, application, proof, closeout, and campaign readiness;
- provides a deterministic rollback path with no automatic retry;
- preserves immutable execution-specific evidence;
- keeps all runtime and financial capabilities locked.

## 16. What remains locked

- migration application until final authorization PASS;
- any campaign, provider, RPC, WebSocket, source fetch, discovery, tracking,
  snapshot, close, or Scheduler runtime;
- memory generation, promotion, retrieval, or dirty-memory use;
- `WINDOW_1H`, 4h, 12h, and 24h;
- paper decisions;
- BUY, SELL, and HOLD;
- positions, trade events, paper trade audits, and PnL;
- wallets, private keys, signing, real funds, and live execution;
- paid APIs;
- scoring, ranking, confidence, weighting, embeddings, and vectors;
- V2-10.

## 17. Proof still required

Before this lane is complete operationally:

1. independent final-authorization review;
2. fresh backup/restore and rollback rehearsal;
3. exactly one bounded migration application;
4. read-only post-migration proof;
5. independent migration-application closeout;
6. repeat post-migration campaign readiness audit.

## 18. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Consequence | Required control |
| --- | --- | --- |
| DB drift after the readiness audit | Wrong database could be migrated | Fresh path/hash/size/mtime, ledger, schema, and residue evidence at authorization and immediately before application |
| Migration runner sees a later migration | More than 050 could apply | Exact pinned Git HEAD, exactly 50 canonical files, exact 49-prefix pre-ledger |
| Live writer or WAL sidecar | Byte copy or table rebuild may be inconsistent | Existing exclusive-writer and sidecar gates; no processes during application |
| Table rebuild damages history | Authoritative evidence loss | Byte-identical backup, preserved-field snapshot, row-count equality, integrity/FK checks, mandatory rollback |
| Migration succeeds but ledger insertion fails | Schema/ledger split state | Post-proof requires exact ledger/schema agreement; otherwise rollback, never rerun |
| Post-check failure encourages retry | Repeated mutation could compound damage | One-attempt/no-retry law and new-lane requirement |
| Backup is overwritten or stale | Rollback cannot restore exact pre-state | Immutable new backup path, hash/size recheck before application and rollback |
| Rollback overwrites failed evidence | Root cause becomes unverifiable | Quarantine exact failed post-state before atomic restore |
| Migration and campaign are combined | Failure source becomes ambiguous | Hard separation; campaign remains prohibited through closeout and repeat readiness |
| Generic evidence file is overwritten | Wrong execution may look controlling | Execution-specific immutable directory; no shared mutable summary |
| Existing stale migration-count tests | Broad suite may add unrelated scope | Run only final-authorization checks and migration-specific proof; document pre-existing failures |
| Large authoritative DB copy cost | Backup/rehearsal takes time and disk | One verified backup, one disposable restore, one rollback rehearsal; no broad repeated proof |

## 19. Exact next permitted lane

`V2-9.8B Authoritative Migration 050 Application Final Authorization Review`

Type: independent read-only inspection and documentation only.

It may inspect the exact target, create the authorized backup and disposable
restore rehearsal, and produce the final-authorization evidence package. It may
not apply migration 050 to the authoritative database or run any campaign.