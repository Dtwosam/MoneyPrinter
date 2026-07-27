# Printer V1 V2-9.8B.10 — Post-Selection Lifecycle Integrity Closeout

## Verdict

```text
V2_9_8B_10_POST_SELECTION_LIFECYCLE_REPAIR_PASS
```

Audit, design, implementation, and focused proof are closed. This does **not**
mark V2-9.8B complete and does **not** authorize another production run, tag, or
push.

## Exact root cause

Execution `20260727T001520Z-d513e21260b5` selected two market-eligible tokens and
completed tracking handoff, then failed at lifecycle entry:

| Field | Value |
|---|---|
| First cause | `OPERATIONAL_CAMPAIGN_FAILED:IntegrityError` |
| Statement | `INSERT INTO printer_memory_factory_runs (... db_mode ...)` |
| Owner | `run_one_command_15m_factory` |
| Value | `db_mode='OPERATIONAL_PERSISTENT'` |
| Constraint | migration 028 `CHECK (db_mode = 'PROOF_ONLY')` |
| SQLite message | `CHECK constraint failed: db_mode = 'PROOF_ONLY'` |

Deterministic for every operational-persistent lifecycle entry. Both selected
tokens being `LATEST_GRADUATED` was incidental. Zero `WINDOW_15M` rows because
the factory-run INSERT never committed.

Secondary defects:

1. Factory connection for that INSERT lived outside the lifecycle `try/finally`,
   so a failed insert leaked a write handle and contributed to
   `database is locked` during automatic terminalization.
2. Public exception surface hard-coded `source_calls: 0`, hiding durable ledger
   total `18`.

## Repair

| ID | Change |
|---|---|
| R1 | Migration `044_memory_factory_run_operational_db_mode.sql` widens factory-run `db_mode` to `PROOF_ONLY \| OPERATIONAL_PERSISTENT` |
| R2 | Factory closes SQLite connection on pre-lifecycle insert failure |
| R3 | `_terminalize_initialized_failure` retries cleanup/reconcile/report under SQLite busy/locked |
| R4 | Heartbeat `stop()` joins longer so renewals finish before cleanup |
| R5 | Public failure surface emits durable `campaign_source_calls` from holder ledger when available |
| R6 | Runtime schema readiness accepts the widened `db_mode` CHECK |
| R7 | `EXPECTED_MIGRATION_COUNT = 44` |

No second lifecycle owner, Scheduler, source counter, terminal owner, retry
framework, restart, or successor path was added.

## Focused proof

```text
.venv/bin/python -m pytest \
  tests/test_v2_9_8b_10_post_selection_lifecycle_integrity.py \
  tests/test_v2_9_8b_5_7_discovery_productivity.py \
  tests/test_v2_9_8b_2_holder_budget_supervision_repair.py \
  tests/test_v2_9_8b_4_blocked_supply_source_reporting.py \
  tests/test_v2_9_7e_43_graduated_liquidity_front_door.py \
  tests/test_v2_9_7e_42_direct_migration_discovery.py \
  tests/test_v2_9_1_proof_db_schema_readiness.py \
  -q
```

Result: **99 passed**.

Proof coverage includes:

1. Operational factory-run INSERT no longer IntegrityErrors  
2. Duplicate factory `run_id` fails closed  
3. Two-token readiness bundle distinct + conflict-safe  
4. Post-selection IntegrityError terminalizes campaign/run/cycle and releases lease  
5. First terminal cause immutable on idempotent cleanup  
6. Busy-retry survives transient `database is locked`  
7. Durable campaign source total (18) readable for public failure surface  
8. Discovery / floor-cooldown / holder-budget / reporting / schema regressions green  

## Heartbeat / terminalization result

* Heartbeat still never terminalizes.
* Cleanup coordinator retries locked SQLite operations.
* Factory no longer leaves an open write connection after insert failure.
* Disposable proof: cleanup_completed + lease_released after simulated IntegrityError.

## Source-total reporting result

Public blocked surface now includes:

```text
campaign_source_calls: <ledger governed_requests or null>
source_calls: <same when available, else 0>
```

Status and report-only modes remain action-local zero-source when they perform
no work.

## Files changed

| File | Role |
|---|---|
| `docs/printer-v1-v2-9-8b-post-selection-lifecycle-integrity-audit.md` | 10A audit |
| `docs/printer-v1-v2-9-8b-post-selection-lifecycle-integrity-design.md` | 10B design |
| `docs/printer-v1-v2-9-8b-post-selection-lifecycle-integrity-closeout.md` | This closeout |
| `migrations/044_memory_factory_run_operational_db_mode.sql` | Schema repair |
| `src/printer_v1/operator_cli/one_command_15m_factory.py` | Close conn on insert fault |
| `src/printer_v1/operator_cli/operational_memory_factory_command.py` | Migration count, busy retry, source total, heartbeat join |
| `src/printer_v1/operator_cli/proof_db_schema_readiness.py` | Accept widened db_mode CHECK |
| `tests/test_v2_9_8b_10_post_selection_lifecycle_integrity.py` | Focused proofs |
| `tests/test_v2_9_8b_5_7_discovery_productivity.py` | Expect migration count 44 |

## Money-usefulness contribution

Unblocks the only remaining gate between successful two-token graduated
selection and lawful `WINDOW_15M` collection. Discovery productivity repairs
from V2-9.8B.5–7 can now feed the existing memory lifecycle without inventing a
second path or lowering capital-protection floors.

## What remains locked

* Automatic production retry authorization  
* V2-9.8B complete claim  
* Retrieval, paper decisions, BUY/SELL/HOLD  
* Positions, trades, audits, PnL  
* Live wallets / private keys / signing / real funds  
* Paid APIs  
* Scoring / ranking / confidence / weighted logic  
* Embeddings / vectors  
* Raising ceiling 45 or lowering `$3,000` / two-token rules  
* 1h / 4h / 12h / 24h production windows  

## Functionality Risks / Setbacks / Efficiency Blockers

| Item | Status |
|---|---|
| Lifecycle runtime beyond insert still un-proven in production | Residual — requires later readiness + one authorized attempt |
| Historical failed execution left SELECTED slots / no windows | Preserved intentionally; not rewritten |
| Public source total best-effort joins latest supervision ledger | Residual — correct when ledger exists; null/0 before ledger |
| Factory still refuses operational mode on non-authoritative paths | Correct lock preserved |

## Conditions for a later readiness review

Before any operator-authorized production attempt:

1. Clean tracked tree on the post-repair closeout HEAD.  
2. Migration count **44**, latest `044_memory_factory_run_operational_db_mode.sql`.  
3. `preflight-only` READY; integrity ok; FK violations 0; zero active work.  
4. Explicit single-run authorization (not this closeout).  
5. Expect multi-round discovery kwargs + operational factory-run insert to succeed
   when two eligible tokens are selected.  

## Stop conditions honored

* No production `-Mode run`  
* No live source calls  
* No rewrite of execution `20260727T001520Z-d513e21260b5`  
* No tag or push  
* No V2-9.8B complete claim  
* No financial unlock  
