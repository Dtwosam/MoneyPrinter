# Printer V1 Handoff

## Current capability

Active branch: `assistant/v2-9-8b-later-cycle-mint-market-replay-repair`. Printer remains
Solana-only, memecoin-only, and paper-only. Source Governor remains the sole
source-request owner and Central Scheduler the sole scheduler owner; all
evidence, provenance, freshness, clean-memory, and capability gates fail
closed.

The authoritative DB at `data/printer_v1.sqlite3` is at migration `64 /
064_four_token_started_lifecycle_zero_attempt_provenance.sql`; failed-run
SHA-256 is `98232a9cb09072c854a679c1cfba8ea5461a0ada6cb2bea3c41a34d9e999b0d0`.
Dedicated migration-only exact-one-migration authorization infrastructure remains
separate from runtime authority.

## Latest meaningful result

Migration authorization `V2_9_8B_MIGRATION_064_AUTH_20260914T115201Z_1506c3c7`
remains consumed exactly once and migration `64/064` remains healthy.

Standard-4H authorization
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260914T123005Z_565f8c31` remains permanently
consumed exactly once. Durable lifecycle truth proves Cycle-1 lifecycle started;
the earlier pre-lifecycle failure classification was stale. Terminalization
encountered `planned-lifecycle zero-attempt provenance requires a fresh transaction`.

The full read-only SQLite audit found the DB healthy. The highest-priority P1
factory connection-lifetime defect is repaired: one outer ownership boundary
rolls back incomplete writes and closes the connection across initialization,
workload, and finalizer failures. `KeyboardInterrupt`, like `_ExternalStop`,
rolls back an inherited transaction before terminalization. Disposable
regressions prove release, exactly-once close, and preserved exception/report truth.

SQLite attribution V2 now distinguishes requested/acquired transactions,
successful/failed commit and rollback, READ/WRITE/UNKNOWN activity, savepoints,
and active-transaction close rollback. Connection/default-cursor execute,
executemany, executescript, SQL terminals and connection context managers have
disposable regressions. Heartbeat evidence snapshots the actual SQLite failure
before rollback/retry; held-reader COMMIT and held-writer BEGIN contention are
reproduced truthfully. Open result cursors remain explicitly uncertain lock
evidence. Snapshot persistence installs fresh context without relabeling an
existing transaction. See `docs/sqlite-attribution-contract.md` for semantics.

Converted raw factories cover source recording, Scheduler, campaign persistence,
snapshot/tracking queue, unified terminal reconciliation/readers, and supervision
readers, preserving PRAGMAs/timeouts/ownership. Remaining raw operational paths
include durable operation logging, source budget readers, proof supervision,
factory report loading, lifecycle rotation/continuity/coverage, pre-lifecycle
refresh/graduated supply, authoritative readiness/marker/recovery, and separate
backup/recovery/report utilities. Borrowed raw handles remain uninstrumented.

Later-cycle evidence INSERT failures now enter the existing typed persistence
handler and retain `LATER_CYCLE_ATTEMPT_PERSISTENCE_FAILED` through attempt,
Scheduler diagnostic, factory and shared terminalization. The already-committed
attempt/claim and observed callback execution remain truthful; failed evidence,
selection and Cycle 2 are not invented. Actual supply failures and successful
pair persistence retain existing behavior. SQLite attribution and factory
connection-lifetime regressions remain passing.

Unchanged baseline failures remain in migration-discovery's missing helper,
exact-recovery active-work preflight, the older migration-catalogue fixture,
and four cadence-isolation expectations (quantum bound, two incomplete DB
fixtures, and PAIR_READY terminality), reproduced on the starting HEAD.

Authoritative failed-run cleanup/lease/Scheduler residue remains untouched.
No new Standard-4H authorization is permitted while that residue remains.

## Proven blocker

The historical heartbeat blocker remains unproven. The latest heartbeat
acquired `BEGIN IMMEDIATE`; reader-held commit contention reproduced its symptom
on disposable state. Later cleanup BEGIN failures are a separate event sequence.
The attribution repair establishes forward observation semantics; it does not
establish the historical blocker. The authoritative DB hash and physical file
identity remain unchanged, preserving the audited healthy state.

## Exact next permitted action

The next recommended development lane is to reconcile the four pre-existing
cadence-isolation regressions against current acquisition-bound and PAIR_READY
contracts using disposable tests; do not change operational policy merely to
satisfy stale expectations. Any cleanup of failed execution
`20260914T123749Z-f4617e1d5431` still requires a separate exact-identity preflight
and explicit operator approval. Do not reuse consumed authority or prepare a
Standard-4H rerun while authoritative residue remains.
