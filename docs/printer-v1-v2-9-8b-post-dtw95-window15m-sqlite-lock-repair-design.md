# Printer V1 V2-9.8B post-DTW95 cancellation-probe SQLite repair design

Verdict: `V2_9_8B_POST_DTW95_SQLITE_LOCK_REPAIR_DESIGN_READY`

## Problem

The operational `WINDOW_15M` factory sleeps between due lifecycle steps and checks a cooperative cancellation probe once per second. The probe reads campaign supervision through `_read_only()`, whose SQLite connection uses `timeout=0.0`.

A healthy heartbeat is a legitimate concurrent SQLite writer. DTW95 proved that a short heartbeat write can coincide with the zero-timeout cancellation read and immediately raise `OperationalError: database is locked`, aborting the whole lifecycle before the next step is due.

## Canonical repair

Introduce one dedicated helper in `operational_memory_factory_command.py` for reading the campaign supervision cancellation state.

The helper must:

1. open the exact authoritative/validated DB read-only;
2. use a bounded SQLite busy timeout of **2 seconds**, aligned with `printer_v1.db.sqlite_write_contracts.DEFAULT_OPERATIONAL_BUSY_TIMEOUT_MS` / campaign supervision's operational contention budget;
3. perform only the existing supervision-state SELECT;
4. return the existing semantic results for missing, `STOPPING`, `TERMINAL`, and healthy `ACTIVE` supervision;
5. if SQLite remains `busy`/`locked` after the bounded wait, return the explicit terminal cause `CANCELLATION_PROBE_SQLITE_LOCKED`;
6. re-raise unrelated SQLite/database errors rather than disguising them;
7. never write the DB and never retry any source, Scheduler job, lifecycle step, authorization, or heartbeat operation.

Keep `_read_only()`'s default `timeout=0.0` for all unrelated callers. Add an optional timeout argument only so this one operational cancellation read can opt into the bounded contention contract.

The nested `cancellation_probe()` in `_run_operational_campaign()` delegates its supervision read to the new helper after checking heartbeat failure. Heartbeat failure remains first-priority and unchanged.

## Why this boundary

The observed collision happens during the factory's idle wait, not during close claim or close execution. The cancellation probe is invoked every second and is therefore the only zero-timeout DB operation on the proven path that aligns with the successful heartbeat timestamp.

Waiting up to the existing 2-second operational busy budget is safe because it does not authorize work; it merely allows a read to observe the authoritative supervision row after a legitimate short writer commits.

If the DB cannot be read inside that bound, failing closed with `CANCELLATION_PROBE_SQLITE_LOCKED` is safer and more truthful than continuing or reporting `SAFE_STOP_PREFLIGHT_FAILED`.

## Tests / bounded proof

Use disposable SQLite fixtures only.

### RED

A focused test must reproduce the old behavior: hold a short `BEGIN EXCLUSIVE` writer lock while invoking the supervision cancellation read with zero timeout; the old read raises `sqlite3.OperationalError: database is locked`.

### GREEN

With the repaired operational timeout:

- a short lock released within the bound resolves and an `ACTIVE` row returns `None`;
- `STOPPING` returns its stored cancellation reason;
- `TERMINAL` returns `CAMPAIGN_SUPERVISION_TERMINAL`;
- missing supervision returns `CAMPAIGN_SUPERVISION_MISSING`;
- a lock deliberately held beyond a short injected test timeout returns `CANCELLATION_PROBE_SQLITE_LOCKED`;
- unrelated SQLite errors are not converted to lock contention.

Compile the changed module and run only the focused regression plus the nearest existing operational-command/campaign-supervision tests if available. No broad suite is required for implementation proof.

## Safety invariants preserved

- lease remains 90 seconds;
- heartbeat cadence remains 30 seconds;
- heartbeat failure handling remains fail-closed;
- no source retry/rotation/reconnect;
- no Scheduler retry or bypass;
- no authorization reuse/resume/restart/successor;
- Source Governor and Central Scheduler ownership unchanged;
- `WINDOW_15M` only;
- retrieval, decisions, BUY/SELL/HOLD, paper positions, trades, audits, PnL remain locked;
- `WINDOW_1H+` remains locked.

## Money-usefulness contribution

This repair prevents a harmless, millisecond-scale SQLite writer collision from discarding a nearly complete live observation stream. It improves memory-factory completion reliability without changing what tokens qualify, what evidence counts, or any simulated trading rule.

## What remains locked

A passing offline proof does not authorize another live run. After implementation/proof closeout, Printer still requires read-only authoritative-DB rereadiness, a fresh one-use authorization package, independent authorization closeout, and one separately authorized `WINDOW_15M` attempt.

## Functionality Risks / Setbacks / Efficiency Blockers

- A globally widened read timeout would broaden preflight behavior; the design explicitly avoids it.
- An unbounded wait could hide genuine DB wedging; the wait is capped.
- Catching every `OperationalError` would hide corruption/schema faults; only busy/locked is normalized.
- Another independent writer could still exist; the post-repair live proof remains necessary after bounded offline verification.
