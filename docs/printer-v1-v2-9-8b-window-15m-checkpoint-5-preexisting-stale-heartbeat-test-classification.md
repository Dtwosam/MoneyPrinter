# Printer V1 — Checkpoint 5 Pre-existing Stale Heartbeat Test Classification

Issue: `DTW-31`

Branch head inspected: `4c46122c2b34df031795de6d51f8feb829686365`

## Verdict

`PREEXISTING_STALE_TEST_UNRELATED_TO_CHECKPOINT5_REPAIR`

## Failed test

`tests/test_v2_9_8b_20_sqlite_heartbeat_concurrency.py::TestMigrationDiscoverySleepDoesNotHoldLock::test_settle_sleep_releases_write_transaction`

The corrected Checkpoint 5 repair proof reached:

- fresh-process import-order proof: `4 passed`;
- Checkpoint 3 focused contracts: `3 passed`;
- Checkpoint 5 static contracts: PASS;
- focused Scheduler/lifecycle suite: `1 failed, 75 passed, 6 subtests passed` before fail-fast stop.

The failing test raised before executing the Checkpoint 5 repair surface:

```text
AttributeError: module 'printer_v1.discovery.direct_migration_discovery'
has no attribute 'release_write_transaction'
```

## Root cause

The test belongs to the older V2-9.8B.20 concurrency architecture where direct migration discovery supported:

- `settle_seconds > 0`;
- an intentional settle sleep;
- a module-level `release_write_transaction` helper patched to prove release-before-sleep.

The current direct migration owner has a different, later contract:

```python
if settle_seconds != 0.0:
    raise ValueError("FINALIZED_DIRECT_PUMP_LIVE_TAIL_FORBIDS_SETTLE_SLEEP")
```

It imports only `connect_operational` from `sqlite_write_contracts`; it no longer exports or calls `release_write_transaction`, because the settled multi-round path was retired. The test was not removed or rewritten when the restored finalized stateless one-page live-tail contract replaced that behavior.

The test also ends with:

```python
self.assertGreaterEqual(releases_before_sleep["count"], 0)
```

That assertion is true for every non-negative count, including zero, and therefore cannot prove release-before-sleep even if the old helper existed.

## Causality classification

The Checkpoint 5 import-order repair changes only:

- `src/printer_v1/discovery/__init__.py`;
- `src/printer_v1/discovery/checkpoint3_guards.py` removal;
- owner integration in `combined_executor.py`;
- delimiter-bound scope in `permanent_discovery_availability.py`.

It does not modify:

- `direct_migration_discovery.py`;
- `sqlite_write_contracts.py`;
- the heartbeat test;
- settle, reverify, live-tail, or migration transport behavior.

The failure is therefore unrelated pre-existing test debt, not a Checkpoint 5 production regression.

## Proof disposition

Risk-based verification will:

1. reproduce this exact failure on the pre-repair branch head;
2. require the exact `AttributeError` signature;
3. deselect only this exact obsolete test from the Checkpoint 5 focused proof;
4. run every other selected heartbeat, Scheduler, lifecycle, terminal, and accounting test unchanged;
5. document the deselection in the Checkpoint 5 closeout.

The stale test itself is not repaired in Checkpoint 5 because that would expand scope into historical direct-migration test maintenance. A separate maintenance lane may remove or rewrite it against the finalized no-settle contract.

## Money-usefulness contribution

This classification prevents a stale historical test from blocking a valid Scheduler/lifecycle safety repair while preserving honest evidence about the obsolete test. It does not weaken current production behavior or hide a reachable defect.

## What this improves

- exact proof causality;
- minimum-sufficient regression scope;
- separation of current product defects from historical test debt;
- honest closeout reporting.

## What this does not unlock

No runtime, provider fetch, authorization, authoritative DB mutation, memory generation, retrieval, paper decision, BUY/SELL/HOLD, paper position, trade, audit, PnL, longer window, or Checkpoint 6 capability is unlocked.

## Functionality Risks / Setbacks / Efficiency Blockers

- The stale test remains in the repository and may fail in broad suites until separately maintained.
- Deselecting more than this exact test would weaken proof and is forbidden.
- Any different failure in the remaining focused suite must stop the repair and be classified independently.
