# SQLite attribution contract (V2)

This is observational sidecar evidence, not a lock detector or operational
permission. The schema is `PRINTER_V1_SQLITE_WRITER_ATTRIBUTION_V2`. No SQLite
writes, source requests, retries, timeouts, or transaction ownership are added
by attribution. An active timeline is required; otherwise connectors retain
native SQLite behavior.

## Transaction state and events

- `TRANSACTION_BEGIN_REQUESTED` captures a UUID, connection UUID/role and a deep
  snapshot of owner, operation and context before SQLite attempts BEGIN (also
  implicit BEGIN and outer SAVEPOINT). A request is not an acquired transaction.
- `TRANSACTION_BEGIN_ACQUIRED` requires SQLite `in_transaction=True`. Deferred
  BEGIN/SAVEPOINT initially has kind `UNKNOWN`; it does not prove a read lock.
- Successful BEGIN IMMEDIATE/EXCLUSIVE or write SQL establishes `WRITE`.
  Successful SELECT establishes `READ` if no write has been established.
  A write kind stays WRITE through savepoint rollback: the outer transaction
  has not relinquished its write ownership. Unsupported SQL or failed writes
  keep a previously non-WRITE transaction UNKNOWN, including after later SELECTs.
- Commit and rollback have separate `REQUESTED`, `SUCCEEDED`, and `FAILED`
  events. Failure while SQLite remains in a transaction retains the same UUID.
  Success requires a successful call/statement and ended SQLite transaction.
- SAVEPOINT, RELEASE, and ROLLBACK TO have separate activity events. Nested
  release/rollback-to retain the outer transaction. Outermost successful release
  records `TRANSACTION_RELEASE_SUCCEEDED` and removes it only when SQLite ends it.
- Successful close with an active transaction records
  `TRANSACTION_CLOSE_ROLLBACK_SUCCEEDED`, followed by connection closure.
  Unexpected SQLite transaction termination is `TRANSACTION_SQLITE_ENDED`.
- Script errors can follow an already-executed terminal statement but occur
  before another statement is traced. If SQLite ended the transaction and the
  exact terminal outcome cannot be inferred, record `*_OUTCOME_UNKNOWN`, never
  fabricated commit success/failure. Repeated trigger traces do not prove
  completion of the outer statement.

Native connection/default cursor `execute`, `executemany`, and `executescript`,
SQL terminals, and connection context managers are covered. SQL is not rewritten;
SQLite's legacy implicit BEGIN and executescript pre-commit remain intact.
Comments and quoted tokens are recognized; top-level WITH DML is classified by
its effective operation. SQL text and parameter values are not persisted.

`STATEMENT_EXECUTION_*` reports execution observations outside an explicit
transaction, not an inferred commit. Open result cursors are separately tracked
until exhaustion, close, replacement or garbage collection. An open result
cursor may have already released its SQLite lock before Python observes
exhaustion: `lock_held_proven=False` explicitly preserves that uncertainty.
Custom cursor factories, direct sqlite3 base-method calls, native extensions,
reentrant SQL callbacks, and nonlegacy Python autocommit modes are outside this
API coverage; none are used by these converted production paths.

## Contention and context

`SQLITE_CONTENTION_OBSERVED` captures candidates at the SQLite BUSY/LOCKED
exception, before retry, rollback or close. Heartbeat failure evidence retains
phase, time and snapshots across outer attempts. Known transactions acquired
during an attempt are included if still active. Requests alone are excluded.
Single/multiple writers, single/multiple readers, mixed activity and UNKNOWN
transactions have distinct dispositions. The legacy empty-set disposition is
`NO_KNOWN_APPLICATION_OWNED_WRITER`; its empty candidates mean no known blocker.
Every disposition retains `causal_blocker_proven=False` and
`external_or_uninstrumented_blocker_possible=True`. Proven overlap never proves
that this candidate caused contention. Cursor details remain evidence of an
open result, not proof of an operating-system/SQLite lock.

Changing connection context never relabels an existing transaction. The real
`persist_snapshot_from_source_response` boundary explicitly installs SNAPSHOT
context, so its next transaction cannot inherit SOURCE_RESPONSE_RECORD.

## Operational coverage and remaining paths

Converted connection factories: Source Governor recording, Scheduler persistence,
campaign persistence, snapshot recording, lifecycle tracking queue, unified
terminal reconciliation/report readers, and supervision read-only connections.
Existing attributed factory-main and heartbeat connections use the same improved
instrumentation. Existing timeout, FK, query-only and commit ownership remain.

Remaining raw paths include source budget readers; durable external operation
logging; proof supervision; factory report-only loading; campaign lifecycle
rotation/readiness adapters; lifecycle continuity/coverage; pre-lifecycle refresh
and graduated-supply connections; authoritative campaign readiness/marker/recovery
connections; and separate recovery/backup/report utilities. Borrowed raw handles
remain raw. This lane does not claim whole-repository coverage or retrofit
connections opened before timeline activation.

The historical heartbeat blocker remains unproven. This contract grants no
cleanup, authorization, Scheduler run, source call, or Standard-4H launch.
