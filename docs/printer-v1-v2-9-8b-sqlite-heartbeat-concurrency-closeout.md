# Printer V1 V2-9.8B.20 — SQLite Heartbeat Concurrency Consolidation Closeout

## Final verdict

```text
V2_9_8B_20_SQLITE_HEARTBEAT_CONCURRENCY_CONSOLIDATION_PASS
READY_FOR_OPERATOR_REVIEW_BEFORE_ONE_SEPARATE_PRODUCTION_ATTEMPT
```

This closeout completes audit, design, implementation, disposable concurrency
proof, operational regressions, residue review, and documentation.

It does **not** run production. It does **not** authorize automatic retry. It
does **not** unlock retrieval, paper decisions, BUY/SELL/HOLD, positions,
trades, audits, PnL, longer windows, wallets, or live execution.

## Baseline and implementation identity

| Item | Value |
|---|---|
| Starting clean HEAD | `cfd4beb7d3b097d31f25cf6ce81e6736cf9a4860` |
| Starting subject | `Close V2-9.8B production readiness consolidation` |
| Implementation commit | `c942194` — `Stabilize V2-9.8B SQLite heartbeat concurrency` |
| Closeout subject | `Close V2-9.8B SQLite concurrency consolidation` |
| Failed executions | `20260727T202052Z-d42812d31bd8`, `20260727T203044Z-7f8e098bf267` |
| Authoritative DB | `data/printer_v1.sqlite3` |
| Integrity / FKs after work | `ok` / 0 |

## Exact shared root cause

Both campaigns failed at the first 30s heartbeat with durable
`LEASE_RENEWAL_SQLITE_LOCKED` because the main discovery writer held a deferred
SQLite write transaction open across live PumpPortal migration-stream I/O
(~84s and ~121s). Heartbeat `BEGIN IMMEDIATE` busy budget (~10.2s) could not
obtain the write lock.

Full evidence: `docs/printer-v1-v2-9-8b-sqlite-heartbeat-concurrency-audit.md`.

## Architectural repair

### Central contract

New module `src/printer_v1/db/sqlite_write_contracts.py`:

* `release_write_transaction` — commit any open shared-connection write
* `connect_operational` / `configure_operational_connection` — foreign_keys + busy_timeout
* `short_write_transaction` — explicit `BEGIN IMMEDIATE` / commit / rollback

Exported from `printer_v1.db`.

### Governed source execution boundary

`execute_source_request_with_governor` now:

1. records the request
2. **releases the write lock**
3. runs `adapter.execute` (source I/O with no open write transaction)
4. records response/failure and releases again

This is the production root-cause fix for every owner that passes a shared
connection through governed source execution (migration discovery, front door,
locator, holder, safety context, lifecycle context).

### Operational owners

| Owner | Repair |
|---|---|
| `direct_migration_discovery` | operational connect; release before settle/reverify sleeps |
| `graduated_liquidity_front_door` | operational connect |
| `graduated_supply_front_door` locator | operational connect |
| `combined_executor` | operational connect |
| `one_command_15m_factory._collect_preclose_context` | release before pacer sleeps |
| `authoritative_live_operational_campaign` | operational connect; release before holder funnel / collection |

### Explicitly not used as primary fix

* lease duration increase
* heartbeat interval slowdown
* busy-timeout increase alone
* automatic renewal retries that hide contention
* suppressing or reclassifying `LEASE_RENEWAL_SQLITE_LOCKED`
* continuing without confirmed renewal

No migration or journal-mode rewrite was required.

## Files changed

### Implementation

* `src/printer_v1/db/sqlite_write_contracts.py` (new)
* `src/printer_v1/db/__init__.py`
* `src/printer_v1/sources/governed_execution.py`
* `src/printer_v1/discovery/direct_migration_discovery.py`
* `src/printer_v1/discovery/graduated_liquidity_front_door.py`
* `src/printer_v1/discovery/combined_executor.py`
* `src/printer_v1/operator_cli/graduated_supply_front_door.py`
* `src/printer_v1/operator_cli/one_command_15m_factory.py`
* `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`

### Proof / docs

* `tests/test_v2_9_8b_20_sqlite_heartbeat_concurrency.py` (new)
* `docs/printer-v1-v2-9-8b-sqlite-heartbeat-concurrency-audit.md`
* `docs/printer-v1-v2-9-8b-sqlite-heartbeat-concurrency-closeout.md`

## Disposable concurrency proof

Command:

```text
.venv/bin/pytest -q tests/test_v2_9_8b_20_sqlite_heartbeat_concurrency.py
```

Result: **9 passed in ~37s**.

| # | Requirement | Result |
|---:|---|---|
| 1 | Exact production lock pattern reproduced before repair semantics | PASS — open write + hold blocks renewal with `LEASE_RENEWAL_SQLITE_LOCKED` |
| 2 | Repaired governed execute allows renewal under long adapter I/O | PASS |
| 3 | Many heartbeats under concurrent writers | PASS — ≥8 sequential renewals, 0 false failures |
| 4 | Three sequential disposable campaign lease cycles | PASS |
| 5 | Delayed source never leaves open write transaction | PASS |
| 6 | Genuine SQLite lock still fails closed with durable evidence | PASS |
| 7 | Lease expiry / ownership mismatch still fail closed | PASS |
| 8 | Integrity `ok` and FK clean after concurrency | PASS |
| 9 | Settle-path release helper available in migration discovery | PASS |

## Operational subsystem regressions

```text
.venv/bin/pytest -q -x --tb=line \
  tests/test_v2_9_8b_18_heartbeat_terminalization_repair.py \
  tests/test_v2_9_7b_4_heartbeat_lease_reliability.py \
  tests/test_v2_9_8b_16_batch_scoped_discovery_persistence.py \
  tests/test_v2_9_8b_19_production_readiness_consolidation.py
```

Result: **31 passed, 2 skipped, 5 subtests passed**.

```text
.venv/bin/pytest -q --tb=line \
  tests/test_v2_9_7e_42_direct_migration_discovery.py \
  tests/test_v2_9_7e_43_graduated_liquidity_front_door.py \
  tests/test_v2_9_7e_44_full_pilot_supply_integration.py \
  tests/test_v2_9_8b_5_7_discovery_productivity.py \
  tests/test_v2_9_8b_2_holder_budget_supervision_repair.py \
  tests/test_v2_9_8a_public_operational_command.py
```

Result: **89 passed**.

No unrelated product suites were run.

## PowerShell disposable qualification (macOS)

```text
pwsh -File scripts/Start-PrinterV1-MemoryFactory.ps1 -Mode preflight-only
pwsh -File scripts/Start-PrinterV1-MemoryFactory.ps1 -Mode status
pwsh -File scripts/Start-PrinterV1-MemoryFactory.ps1 -Mode report-only
```

| Mode | Source calls | Scheduler | Writes | Note |
|---|---:|---:|---:|---|
| preflight-only | 0 | 0 | 0 | blocked only by dirty worktree git provenance during this lane |
| status | 0 | 0 | 0 | reports latest terminal campaign read-only |
| report-only | 0 | 0 | 0 | zero-source replay of terminal report |

Wrapper itself is healthy. Dirty-tree preflight block is expected while uncommitted
lane files exist and is not a concurrency regression.

## Residue recovery

| Check | Result |
|---|---|
| Active supervision | 0 |
| RUNNING factories | 0 |
| Lease files for both executions | absent |
| Queues 20–23 | `SKIPPED` / `MANUAL_REVIEW` |
| Slots | `MANUAL_REVIEW` with stable cause |
| Factories | `SAFE_STOPPED` |
| Integrity / FKs | `ok` / 0 |

**No authoritative residue mutation was required.** Both failed executions were
already terminalized cleanly by V2-9.8B.18 zero-step / queue-slot disposition.
Heartbeat failure evidence rows remain immutable historical facts.

Recovery status:

```text
ALREADY_CLEAN_NO_AUTHORITATIVE_MUTATION
```

## Money-usefulness contribution

Printer cannot grow clean Solana memecoin memory if every production campaign
dies at the first heartbeat under legitimate discovery I/O. This repair restores
the condition required for bounded persistent 15m memory growth: the campaign
may collect governed evidence without false-failing the lease renewer, while
still fail-closing on genuine lock, expiry, ownership, and unconfirmed renewal.

## What remains locked

* retrieval / paper decisions / BUY / SELL / HOLD
* paper positions / trade events / paper audits / PnL
* live wallet / private keys / real funds / live execution
* paid APIs
* scoring / ranking / confidence / weighted logic
* embeddings / vectors
* `WINDOW_1H` / `4H` / `12H` / `24H` production work
* automatic production retry or successor campaigns
* source ceiling 45, two-token capacity, $3,000 floor, six-candidate policy

## Functionality Risks / Setbacks / Efficiency Blockers

| Item | Status |
|---|---|
| Request row may exist without response if process dies mid-I/O | accepted honesty improvement |
| Combined fixture executor still batches pure writes for cycle atomicity | residual; fixture-speed only |
| Very large pure-write batches without I/O could still pressure heartbeat | residual monitor item; not the production failure mode |
| Operator must still approve any future production attempt separately | hard gate |
| Preflight requires clean git tree for production launch | unchanged |

## Commits

1. `Stabilize V2-9.8B SQLite heartbeat concurrency` — implementation + audit + proof
2. `Close V2-9.8B SQLite concurrency consolidation` — closeout after residue review

## Final statement

```text
V2_9_8B_20_SQLITE_HEARTBEAT_CONCURRENCY_CONSOLIDATION_PASS
READY_FOR_OPERATOR_REVIEW_BEFORE_ONE_SEPARATE_PRODUCTION_ATTEMPT
```

Do not run production automatically. Do not tag or push from this lane.
