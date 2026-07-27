# Printer V1 V2-9.8B.19 — Full Production Readiness Consolidation Audit

## 1. Verdict

```text
V2_9_8B_19_CONSOLIDATION_AUDIT_PASS_BLOCKERS_PROVEN
```

This audit documents every discoverable blocker on the public operational
command surface that prevented a real bounded two-token `WINDOW_15M` campaign
from completing, and defines the consolidation repairs required before
requalification.

This document does not authorize production. It does not unlock retrieval,
paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, longer windows,
or live execution.

## 2. Baseline

| Gate | Evidence | Result |
|---|---|---|
| Exact HEAD | `54d5bbf29ade32349b574ea4af6db5288a2e0d94` (`Close V2-9.8B heartbeat terminalization repair`) | PASS |
| Tracked worktree | clean before edits | PASS |
| Printer process | none | PASS |
| Active lease / campaign / factory | all terminal; supervision `TERMINAL` | PASS |
| Scheduler active/locked | 0 | PASS |
| SQLite sidecars | none | PASS |
| Integrity | `ok` | PASS |
| Foreign keys | 0 violations | PASS |
| Applied migrations | 45; latest `045_heartbeat_failure_evidence.sql` | PASS |

Authoritative database:

```text
/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3
```

## 3. Public path audited

```text
PowerShell wrapper
→ preflight
→ backup/restore
→ campaign supervision
→ discovery and selection
→ tracking handoff
→ factory creation
→ heartbeat and cancellation
→ WINDOW_15M collection and closeout
→ terminal reconciliation
→ status
→ report-only replay
→ recovery
```

Primary entry points:

- `scripts/Start-PrinterV1-MemoryFactory.ps1`
- `printer_v1.operator_cli.operational_memory_factory_command`
- shared owners: Source Governor, Central Scheduler, campaign supervision,
  discovery persistence, unified terminal closure, backup/restore preflight,
  recovery

## 4. Proven blockers

### B1 — Stale hard-coded migration count (immediate production blocker)

| Field | Value |
|---|---|
| Location | `operational_memory_factory_command.EXPECTED_MIGRATION_COUNT = 44` |
| Canonical truth | 45 ordered files under `migrations/`; latest `045_...` |
| Symptom | `build_activation_preflight()` raises `canonical migration ledger mismatch` |
| Classification | `COMMITTED_CODE_DEFECT` |
| Why not “change 44→45” | A second hard-coded integer will drift again on migration 046. Count and names must derive from one ordered source. |

Reproduced on baseline:

```text
EXPECTED_MIGRATION_COUNT 44
canonical 45
preflight_error OperationalMemoryFactoryError canonical migration ledger mismatch
```

### B2 — Blocked-command counters were not action-local

| Field | Value |
|---|---|
| Location | `main()` exception path called `_latest_campaign_source_total()` unconditionally |
| Symptom | Failed `preflight-only` reported `source_calls: 22` from the previous campaign holder ledger |
| Classification | `COMMITTED_CODE_DEFECT` |
| Risk | Operators misread blocked preflight/status as having made source calls; readiness gates become dishonest |

Reproduced:

```text
{"campaign_source_calls": 22, "source_calls": 22,
 "status": "OPERATIONAL_COMMAND_BLOCKED", ...}
```

while the blocked action was `preflight-only` and performed zero source work.

### B3 — Opaque preflight failure surface

| Field | Value |
|---|---|
| Location | `build_activation_preflight` |
| Symptom | One generic string for migration, integrity, active-state, and other gates |
| Classification | `COMMITTED_CODE_DEFECT` / efficiency blocker |
| Repair | Exact `gate=<name>: <detail>` messages for every fail-closed check |

### B4 — Stale operational preflight fixture (FK orphans)

| Field | Value |
|---|---|
| Location | `tests/test_v2_9_8a_public_operational_command.py` |
| Symptom | Disposable copy deleted campaign ownership tables and left 34 FK orphans in discovery/report/slot/holder rows |
| Classification | `TEST_FIXTURE_DEFECT` |
| Prior note | Documented as residual efficiency blocker in V2-9.8B.16 closeout |
| Repair | Relationally valid quiescent corpus copy; never delete ownership parents that remaining rows still reference |

### B5 — Drifting schema/version expectations in abstract command fixtures

| Field | Value |
|---|---|
| Location | abstract-command surface fixtures hard-coded `latest_migration` to historical heads (e.g. 035) |
| Symptom | After canonical-head validation, preflight fails with backup prerequisite mismatch |
| Classification | `TEST_FIXTURE_DEFECT` / drift |
| Repair | Fixture `latest_migration` derives from `canonical_migration_names()[-1]` |

### B6 — Safe ownership renewal message assertion drift

| Field | Value |
|---|---|
| Location | lease safe-stop tests expected raw `"ownership mismatch"` text in `renewal_error` |
| Symptom | Heartbeat sanitization correctly returns safe message; test failed |
| Classification | `TEST_ASSERTION_DRIFT` after safe-message hardening |
| Repair | Assert safe redacted message + `LEASE_RENEWAL_OWNERSHIP_MISMATCH` |

### B7 — `_read_only` default binding defeated AUTHORITATIVE_DB patches

| Field | Value |
|---|---|
| Location | `_read_only(path: Path = AUTHORITATIVE_DB)` default evaluated at import |
| Symptom | Disposable status/report tests patching `AUTHORITATIVE_DB` still targeted the real DB path |
| Classification | `COMMITTED_CODE_DEFECT` |
| Repair | Resolve against live module constant at call time |

## 5. Non-blockers confirmed healthy (prior lanes)

These were re-checked and remain intact; no policy change required:

- batch-scoped discovery recurrence (V2-9.8B.16)
- heartbeat failure evidence + zero-step terminalization (V2-9.8B.18)
- holder budget ceilings / admission 45
- six-candidate / $3,000 floor / two-token capacity
- Source Governor and Central Scheduler ownership
- `WINDOW_15M` only; support-only 5m
- retrieval and financial locks
- exact recovery idempotency owners
- no automatic retry / restart / successor

## 6. Required consolidation design

### 6.1 Single canonical migration source

Owner: `printer_v1.db.migrate`

```text
canonical_migration_names()
canonical_migration_count()
describe_migration_ledger_mismatch(applied)
validate_migration_ledger(applied)
apply_migrations()  # uses the same ordered names
```

Consumers must not hard-code a count:

- public operational preflight
- abstract campaign command ledger check
- proof DB schema readiness
- operator CLI migration status helpers
- tests

`EXPECTED_MIGRATION_COUNT` may remain as a derived export:

```text
EXPECTED_MIGRATION_COUNT = canonical_migration_count()
```

### 6.2 Exact preflight gates

Every fail-closed preflight path reports:

```text
operational preflight blocked: gate=<gate_name>: <exact detail>
```

Gates include at least:

- `database_target`
- `sqlite_sidecar_quiescence`
- `git_provenance`
- `source_contract`
- `runtime_dependency`
- `holder_budget`
- `migration_ledger` (missing / unexpected / duplicate / reordered / count)
- `database_integrity`
- `foreign_keys`
- `active_operational_state`
- `locked_capability_baseline`
- `historical_paper_audit`

### 6.3 Action-local blocked counters

| Mode | `source_calls` on block | Holder ledger lookup |
|---|---|---|
| `preflight-only` | 0 | never |
| `status` | 0 | never |
| `report-only` | 0 | never |
| `cooperative-stop` | 0 | never |
| `run` before campaign create | 0 | never |
| `run` after campaign create | ledger for **that run_id only** | `_latest_campaign_source_total(run_id=...)` |

Module context `_ACTION_RUN_CONTEXT["run_id"]` is reset at the start of every
public `main()` invocation and set when the campaign run graph is created.

### 6.4 Quiescent relational fixtures

Disposable preflight fixtures must:

1. copy authoritative corpus shape, or build a complete relational seed;
2. force only active surfaces terminal/unlocked;
3. preserve historical campaign/discovery/holder/report rows;
4. assert `PRAGMA integrity_check = ok` and zero FK violations before use.

### 6.5 Preserve policy

Do not change:

- six-candidate policy
- `$3,000` floor
- source ceiling 45
- two-token capacity
- cooldowns
- Source Governor / Central Scheduler ownership
- `WINDOW_15M` main window
- support-only 5m policy
- retrieval / financial locks

## 7. Full disposable qualification matrix (required proof)

| # | Proof | Owner |
|---:|---|---|
| 1 | Migration ledger pass; missing/reordered/duplicate/unexpected fail with exact reasons | migrate + preflight tests |
| 2 | `preflight-only` / `status` / `report-only` zero source, scheduler, writes | public command tests |
| 3 | Backup and restore verification | backup preflight tests |
| 4 | Two sequential campaigns may lawfully observe same candidates | batch-scoped persistence suite |
| 5 | Market-supply block closes safely | blocked-supply + lifecycle suites |
| 6 | Full two-token discovery→selection→tracking→factory→WINDOW_15M→report path | lifecycle + discovery + consolidation suites |
| 7 | Honest clean and dirty outcomes preserved | lifecycle/clean-memory suite |
| 8 | Persistence conflicts roll back without partial state | batch-scoped suite |
| 9 | Heartbeat success / SQLite-lock / expiry / ownership / unconfirmed paths retain safe evidence | heartbeat suites |
| 10 | Cancellation before/after factory leaves no active residue | heartbeat + first-operation suites |
| 11 | Status/report replay reflects factory identity and terminal state | consolidation + report suites |
| 12 | Recovery exact and idempotent | recovery suites |
| 13 | Source and Scheduler ceilings enforced | budget + pilot suites |
| 14 | SQLite integrity and FKs clean | all disposable paths |
| 15 | Retrieval and financial deltas zero | locked-table assertions |
| 16 | No retry / restart / successor | terminal reconciliation assertions |
| 17 | PowerShell wrapper runs public module on macOS | wrapper contract + live preflight after clean HEAD |

## 8. Authoritative post-repair gate (after clean commit)

Run only:

```text
preflight-only
status
report-only
```

Require:

- migration count 45
- latest migration 045
- readiness `V2_9_8_OPERATIONAL_PREFLIGHT_READY`
- action-local source calls 0
- Scheduler runtime calls 0
- database writes 0
- integrity `ok`
- zero FK violations
- zero active operational state
- clean Git provenance

Do not run production.

## 9. Functionality Risks / Setbacks / Efficiency Blockers

| Item | State | Control |
|---|---|---|
| Migration head drift | residual if any consumer hard-codes counts | single `migrate.py` source; derived exports only |
| Action-local counter edge cases | run failures before create correctly report 0 | `_ACTION_RUN_CONTEXT` reset + run_id filter |
| Fixture corpus size | copying authoritative DB is slower than empty schema | acceptable for readiness; keep proofs disposable |
| Full live 15m wall-clock | not run in this lane | disposable fixture path + operator production attempt later |
| Safe-message text churn | tests must assert categories/causes, not raw exception strings | prefer `terminal_cause` / category |
| Production market supply | not proven here | separate operator-approved production attempt |

## 10. Money-usefulness contribution

Removing preflight and accounting falsehoods is a capital-protection and learning-
efficiency repair: the machine can only grow clean memory if operators can trust
readiness gates, source totals, and terminal evidence. This is not a profit
claim and does not unlock trading.

## 11. What remains locked

- production campaign without separate operator approval
- automatic retry / restart / successor
- `WINDOW_1H` / `4H` / `12H` / `24H` production
- retrieval activation
- paper decisions, BUY/SELL/HOLD
- positions, trades, audits, PnL
- wallets, private keys, live execution
- paid APIs, scoring, ranking, confidence, weighted logic, embeddings/vectors

## 12. Next action

Implement the consolidation design above, run the full disposable matrix, commit
implementation/proof, run authoritative preflight/status/report-only on clean
HEAD, then close the lane.
