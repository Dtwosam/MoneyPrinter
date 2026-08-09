# Printer V1 V2-9.8B post-DTW95 SQLite contention audit

Verdict: `V2_9_8B_POST_DTW95_SQLITE_LOCK_AUDIT_PASS_ZERO_TIMEOUT_CANCELLATION_PROBE_COLLISION_CONFIRMED`

## Scope

Audit-only. No source fetching, Scheduler runtime, authoritative DB mutation, memory generation, authorization creation, or lifecycle execution.

## Runtime evidence

The consumed DTW95 factory run `5f16f9d4-b0bb-4929-affe-8979d38de962` entered the real two-token `WINDOW_15M` lifecycle and completed snapshot steps `00` through `07` for both tokens.

The last successful snapshot completed at `2026-08-09T09:17:00.112213+00:00`. The first close was not due until `2026-08-09T09:18:50.231583+00:00`.

At `2026-08-09T09:17:34.512219+00:00`, campaign supervision successfully advanced its heartbeat and lease. No heartbeat-failure row exists. About 19 ms later, terminal cleanup began and both not-yet-due close jobs were cancelled. The factory report preserved `OperationalError: database is locked` as `discovery_report.orchestration_error`.

Therefore the lock occurred during the idle wait before close, not during close execution or Scheduler claim of either close.

## Static mechanism

`one_command_15m_factory._sleep_with_cancellation()` checks the cooperative cancellation probe once per second during waits.

The ordinary operational command's cancellation probe calls `_read_only()` and reads the campaign supervision row.

`_read_only()` opens the authoritative SQLite database with `timeout=0.0` and `PRAGMA query_only=ON`.

Campaign heartbeat renewal is a separate legitimate writer. `campaign_supervision.renew_campaign_lease()` opens its own connection and uses bounded `BEGIN IMMEDIATE`/busy handling before committing the supervision heartbeat.

A zero-timeout read-only cancellation probe can therefore collide with the heartbeat's short SQLite commit/write window. Instead of waiting for the legitimate transient writer to release the database, the read fails immediately with `sqlite3.OperationalError: database is locked`.

That exception escapes the cancellation probe and the factory wait loop. The outer factory catch treats any uncaught orchestration exception as `SAFE_STOP_PREFLIGHT_FAILED`, causing a run-wide terminal stop even though the actual event is runtime SQLite contention.

## Root cause

The defect is not lease expiry and not failed heartbeat renewal. It is inconsistent operational SQLite contention policy:

- heartbeat writer: bounded busy wait/retry contract;
- long-lived lifecycle connection: configured busy timeout;
- read-only cancellation probe: `timeout=0.0`, immediate failure.

The probe is a high-frequency operational read that runs concurrently with the heartbeat writer and therefore must tolerate the same legitimate short contention window without weakening fail-closed cancellation semantics.

## Required design boundary

The repair must be limited to the cancellation-probe supervision read (or a narrowly parameterized `_read_only` path used by it).

Required behavior:

1. A transient SQLite busy/locked condition receives a bounded wait consistent with Printer's existing operational SQLite busy contract.
2. No source request, Scheduler operation, lifecycle step, authorization invocation, heartbeat interval, or lease duration is retried or widened.
3. Once the bounded wait is exhausted, the probe must fail closed with a specific SQLite-contention terminal cause rather than silently continue or surface `SAFE_STOP_PREFLIGHT_FAILED`.
4. Existing zero-timeout semantics for unrelated read-only preflights should remain unchanged unless separately justified.
5. Source Governor, Central Scheduler, one-use authorization, and all downstream capability locks remain unchanged.

## Money-usefulness contribution

The repair removes a purely infrastructural reason for discarding an otherwise healthy live 15-minute observation stream before memory close. It does not change token eligibility or trading outcomes; it improves the chance that already-collected governed evidence reaches the memory-quality decision boundary.

## What this does not unlock

No new runtime authorization, retrieval, decision, BUY/SELL/HOLD, paper position, trade, audit, PnL, `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, or `WINDOW_24H` capability is unlocked by this audit.

## Proof required before completion

Minimum sufficient proof:

- RED: under a disposable SQLite fixture with a legitimate short concurrent writer, the cancellation supervision read using zero-timeout behavior fails with `database is locked`.
- GREEN: the repaired probe survives a short contention interval and returns the correct supervision state without DB mutation.
- FAIL-CLOSED: contention held beyond the bounded wait yields the explicit SQLite-contention terminal classification.
- Adjacent regression: existing cancellation states (`STOPPING`, `TERMINAL`, missing supervision, normal `ACTIVE`) retain their behavior.
- No live sources, Scheduler runtime, authoritative DB mutation, or authorization creation.

## Functionality Risks / Setbacks / Efficiency Blockers

- Applying a busy timeout globally to all read-only helpers could mask unrelated preflight problems; avoid that broad change.
- Treating DB contention as a source retry would violate ownership boundaries; do not do it.
- Widening the 90-second lease or changing the 30-second heartbeat cadence is not supported by the evidence.
- If bounded contention still cannot clear, Printer must stop specifically and safely rather than spin indefinitely.
