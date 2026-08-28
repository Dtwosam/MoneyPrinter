# Printer V1 V2-9.8B Post-Consumption Interrupted Four-Token Lease-Failure Cleanup Production Implementation Closeout

Date: 2026-08-29

Implementation verdict:

```text
V2_9_8B_POST_CONSUMPTION_INTERRUPTED_FOUR_TOKEN_LEASE_FAILURE_CLEANUP_PRODUCTION_IMPLEMENTATION_PASS
```

This closeout covers **production component 1 only**. It does **not** implement
or apply the exact-execution `704f53472011` residue reconciliation owner.

Governing design:

`docs/printer-v1-v2-9-8b-post-consumption-interrupted-four-token-residual-reconciliation-lease-failure-cleanup-design.md`

Design verdict required and used:

`V2_9_8B_POST_CONSUMPTION_INTERRUPTED_FOUR_TOKEN_RESIDUAL_RECONCILIATION_LEASE_FAILURE_CLEANUP_DESIGN_AMENDMENT_PASS`

## 1. Baseline

| Item | Value |
|---|---|
| Design-baseline commit | `ba2a001acb8058b53c2df148f2454a930cc5d77b` |
| Pre-implementation HEAD parent | `1d75715ca38c14294f58303b3a5cdb785ed4ad4c` |
| Branch | `agent/v2-9-8b-aug25-a2z-repair-application` |
| Authoritative DB SHA (unchanged) | `c90376b9e26d0f2953a8d9b2fd5fee01d80ac4984510113e595fd1ccc3d9033d` |
| Migration tip | `62` / `062_pre_admission_attempt_evidence.sql` |
| Integrity / FK | `ok` / 0 |
| Live residue | attempt `RUNNING`, job `2808` `PENDING`, supervision `ACTIVE`, lease present |

## 2. What was implemented

### G1 — lease renewal (`campaign_supervision.py`)

- One monotonic hard deadline: `t0 + 15.0s`
- Every SQLite blocking wait/sleep clamped to remaining deadline
- 15s remaining-lease safety margin rechecked against planned block
- Outer maximum 3 attempts; existing inner busy ceilings retained but clamped
- No retry for non-lock / expired / ownership failures
- **DB supervision CAS COMMIT first**, lease-file mirror second
- `renewal_confirmed=True` only when DB and file agree
- DB-committed / file-unsynced → `LEASE_RENEWAL_UNCONFIRMED` with
  `db_ledger_advanced=true`, `lease_file_synced=false`
- Heartbeat thread still performs no terminal cleanup
- Lock-contention failure evidence prefers lease-file first so persistence
  cannot overrun the renewal deadline

`LEASE_RENEWAL_UNCONFIRMED` **already existed** in `_SAFE_FAILURES` /
`LEASE_RENEWAL_ERROR` vocabulary. No schema migration. No new cause constant
required beyond reusing that existing terminal cause.

### G2 — parent-interrupted Cycle-2 cleanup (`four_token_factory_adapter.py`)

- Owner: `reconcile_parent_interrupted_open_pre_admission_attempts(...)`
- **Sole** production call site: `finalize_four_token_shared_terminal` (before
  shape/active-work predicates)
- Cause: `PARENT_CAMPAIGN_INTERRUPTED:<C1_cause>`
- New admitted shape: `ONE_CYCLE_CAMPAIGN_INTERRUPTED_OPEN_ATTEMPT`
- `PARENT_CAMPAIGN_INTERRUPTED:*` excluded from
  `ONE_CYCLE_HONEST_NO_ADMISSION`
- State A atomic on one connection/transaction; replay B/C/D per design §5.5
- Never claims/executes Scheduler work; never fabricates `NO_PAIR`

### Scheduler cleanup ownership (`campaign_supervision.py`)

`cleanup_campaign_supervision` now cancels and counts active jobs linked through
`printer_pre_admission_discovery_attempts.scheduler_job_id` scoped by exact
campaign/run. No hard-coded job `2808`. No fake `campaign_scheduler_work` rows.

### Shared terminalizer order (`operational_memory_factory_command.py`)

`_four_token_shared_terminalizer` now runs:

`reconcile_campaign_terminal` → `cleanup_campaign_supervision`

Cleanup accepts same-cause already-terminal campaign/run while supervision is
still ACTIVE so the reorder cannot trip ownership inconsistency.

## 3. What was not done

- Exact-execution `704f53472011` recovery module
- Authoritative DB mutation / live job `2808` cancel / lease release
- Authorization create/apply/reuse
- Printer / providers / Scheduler runtime / remote-host work
- Capability unlocks (12h/24h, retrieval, financial, BUY/SELL/HOLD, PnL)

## 4. Tests

Commands:

```text
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_v2_9_8b_lease_renewal_sqlite_contention_bound.py \
  tests/test_v2_9_8b_interrupted_cycle2_parent_interrupt_cleanup.py
```

Result: **13 passed**

Also:

```text
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_v2_9_8b_20_sqlite_heartbeat_concurrency.py::TestProductionLockPatternAndRepair \
  tests/test_v2_9_8b_four_token_gate_g_two_phase_terminal.py \
  tests/test_v2_9_8b_shared_terminal_pre_lifecycle_zero_attempt.py \
  tests/test_v2_9_8b_pre_admission_terminal_cleanup_repair.py
```

Touched-owner regressions for lease expiry/ownership, prolonged lock past the
new 15s deadline, two-cycle gate G, pre-lifecycle zero-attempt, and
pre-admission terminal cleanup passed.

Three adjacent failures were reproduced on the pre-implementation baseline and
are **not** introduced by this lane:

- `test_settle_sleep_releases_write_transaction` (`release_write_transaction`
  attribute missing on discovery module)
- `test_exact_recovery_is_truthful_safe_and_idempotent` (historical recovery
  active-work fixture)
- `test_real_cycle2_pre_admission_persistence_failure_terminalizes_once`
  (expected cause string drift)

Deadline proof: prolonged-contention tests assert elapsed
`<= 15.0 + 0.250s`; insufficient-deadline paths fail without starting another
blocking wait.

Also: `py_compile` on changed modules and `git diff --check` passed.

## 5. No authoritative DB mutation proof

Post-implementation read-back:

- DB SHA still `c90376b9e26d0f2953a8d9b2fd5fee01d80ac4984510113e595fd1ccc3d9033d`
- Cycle-2 attempt still `RUNNING`
- Job `2808` still `PENDING`

## 6. Permanent-lock proof

No live trading, wallets/keys, paid APIs, scoring/ranking/confidence/weighted
logic, embeddings/vectors, Source Governor bypass, Central Scheduler bypass,
retrieval/financial capability, BUY/SELL/HOLD, positions/trades/PnL, 12h/24h,
or 5m-as-main-outcome changes landed.

## 7. Exact next permitted action

```text
INDEPENDENT PRODUCTION IMPLEMENTATION CLOSEOUT / REVIEW
```

Only after that passes may a **separately approved** exact-residue
reconciliation implementation lane be considered for consumed execution
`20260828T220832Z-704f53472011`.
