# Printer V1 Lane E2H -- TRACK_FAST_FIRST_15M Runtime Handler Boundary

## 1. Purpose

Lane E2H builds the missing TRACK_FAST_FIRST_15M runtime handler boundary
discovered by E2G.

After E2H:
- TRACK_FAST_FIRST_15M is registered in PHASE35_SAFE_JOB_KINDS.
- The handler boundary enforces all pre-execution gates.
- Real source transport is still fixture-only (Phase 23 boundary). The handler
  fails closed when real source transport is unavailable.
- E2G no longer blocks on "handler not implemented". E2G now blocks on "real
  source transport is fixture-only". That is acceptable until a real source
  adapter replaces FixtureSourceAdapter.

Claude did not run the real cycle. The operator must run the real command
manually after the real source adapter is implemented and E2G confirms
OPERATOR_RUN_READY.

---

## 2. Anchor

- Lane E2G commit: `8ee5b6e`
- Lane E2G tag: `printer-v1-post-lane10-lane-e2g-first-bounded-15m-cycle-operator-run`
- E2G is closed. E2G returned BLOCKED ("handler not implemented").
- E2H is anchored to the E2G tag above.

---

## 3. Discovery Finding (E2G, confirmed E2H)

E2G found the real bounded 15m cycle runtime path does NOT exist:

- `PHASE35_SAFE_JOB_KINDS = {"BACKUP_SOURCE_CHECK"}` -- TRACK_FAST_FIRST_15M missing
- `_execute_phase35_scheduler_job` raised UNSUPPORTED_JOB_KIND_PHASE35
- `governed_execution.py` is fixture-only (FixtureSourceAdapter, no real network)

**E2H resolution:**

- `PHASE35_SAFE_JOB_KINDS` now includes `"TRACK_FAST_FIRST_15M"`.
- `_execute_phase35_scheduler_job` dispatches TRACK_FAST_FIRST_15M jobs to the E2H handler.
- The E2H handler fails closed on real source transport unavailability.
- `_check_15m_cycle_runtime_available()` in E2G now imports E2H to check both
  handler registration AND transport availability.

**Remaining blocker:**

Real source transport is still fixture-only. `check_real_source_transport_available()`
returns `(False, reason)`. E2G blocks on "real source transport unavailable" instead
of "handler not implemented". This is acceptable.

---

## 4. E2H Package

Lane E2H delivers:

- `src/printer_v1/operator_cli/e2h_runtime_handler.py`
- Updated `PHASE35_SAFE_JOB_KINDS` in `src/printer_v1/operator_cli/commands.py`
- Updated `_check_15m_cycle_runtime_available()` in `src/printer_v1/operator_cli/e2g_operator_run.py`
- Tests in `tests/test_post_rc_lane_e2h_track_fast_first_15m_runtime_handler.py`
- This handler boundary document

---

## 5. Handler Design

### 5.1 Registration

```python
# commands.py
PHASE35_SAFE_JOB_KINDS = {"BACKUP_SOURCE_CHECK", "TRACK_FAST_FIRST_15M"}
```

When `_execute_phase35_scheduler_job` receives a TRACK_FAST_FIRST_15M job,
it dispatches to `execute_track_fast_first_15m_job` in `e2h_runtime_handler.py`.

### 5.2 Handler constants

| Constant | Value |
|----------|-------|
| `HANDLER_JOB_KIND` | `"TRACK_FAST_FIRST_15M"` |
| `HANDLER_LIFECYCLE_LANE` | `"TRACK_FAST"` |
| `HANDLER_TARGET_WINDOW` | `"WINDOW_15M"` |
| `HANDLER_MAX_TOKENS_FIRST_RUN` | `1` |
| `HANDLER_SOURCE_NAME` | `"dexscreener"` |
| `HANDLER_REQUEST_KIND` | `"pair_market_snapshot"` |

### 5.3 Handler gate order

All of the following must pass for executed=True:

1. Real source transport available (`check_real_source_transport_available()`)
   -- currently FAILS (fixture-only)
2. No OTHER RUNNING scheduler jobs (excluding current job)
3. No OTHER active locks (locked_at or lock_owner, excluding current job)
4. Source Governor budget allows the request (`can_request_source`)
5. No forbidden table mutations detected
6. (Execute source call if adapter provided -- only reached in tests or
   when real transport exists)

If any gate fails, the handler returns blocked with reason. The scheduler
marks the job FAILED via `_fail_scheduler_job_for_tick`.

### 5.4 Key functions

```python
is_handler_registered() -> bool
    # Always True after E2H.

check_real_source_transport_available() -> tuple[bool, str]
    # (False, reason) until real adapter replaces FixtureSourceAdapter.
    # Patchable in tests.

validate_token_entry(entry: dict) -> tuple[bool, str]
    # Validates single token: valid mint, lifecycle_lane == TRACK_FAST,
    # approved_by_operator == True.

validate_token_list(tokens: list[dict]) -> tuple[bool, str]
    # Validates token list: exactly 1 TRACK_FAST approved token.

check_source_governor(connection, source_name, request_kind) -> tuple[bool, str]
    # Checks Source Governor budget via count_recent_source_requests + can_request_source.

execute_track_fast_first_15m_job(connection, job, *, adapter=None) -> dict
    # Full handler. Fail closed on all gates above.
    # adapter: FixtureSourceAdapter for testing. None in production.
```

### 5.5 E2G integration update

`_check_15m_cycle_runtime_available()` in `e2g_operator_run.py` now:

1. Imports `is_handler_registered` and `check_real_source_transport_available` from E2H.
2. Returns `(False, "...handler registered but real source transport unavailable: ...")`
   when transport is fixture-only.
3. Returns `(True, "...")` only when handler registered AND transport real.

E2G blocker reason transitions:
- Before E2H: "TRACK_FAST_FIRST_15M runtime job handler not implemented"
- After E2H: "TRACK_FAST_FIRST_15M handler registered (Lane E2H) but real source
  transport unavailable: real source transport is fixture-only (Phase 23 boundary)..."

---

## 6. Allowed Cycle Effects (After Real Transport Is Implemented and Operator Runs)

When the operator runs the bounded execution command with a real source adapter:

| Table | Condition |
|-------|-----------|
| `printer_source_requests` | Each governed source request via Source Governor |
| `printer_source_responses` | Each governed source response |
| `printer_source_failures` | If a governed source call fails |
| `printer_scheduler_jobs` | Job rows updated by Central Scheduler |
| `printer_token_snapshots` | Only if source evidence is clean |
| `printer_context_snapshots` | Only if table exists and governed context path runs |
| `printer_contexts` | Only if table exists and evidence passes gates |
| `printer_memory_windows` | Only if 15m window closes with sufficient evidence |
| `printer_memories` | Only if all clean-memory quality gates pass |

Zero clean memories remains a valid first-run outcome.

---

## 7. Forbidden Table Changes

The following tables must NOT receive new rows during any TRACK_FAST_FIRST_15M cycle:

- `printer_paper_decisions` -- paper decisions remain locked
- `printer_paper_positions` -- paper positions remain locked
- `printer_paper_trade_events` -- trade events remain locked
- `printer_paper_trade_audits` -- paper trade audits remain locked
- Any BUY/SELL/HOLD decision rows -- remain locked

---

## 8. What E2H Does NOT Authorize

Lane E2H does NOT authorize:

- Claude running the real cycle
- Automatic execution of the bounded command
- BUY, SELL, or HOLD decisions
- Paper positions, trade events, or PnL
- Wallet logic, private keys, signing, live trading, or real funds
- Paid APIs
- Scoring, ranking, confidence percentages, or weighted logic
- Embeddings or vectors
- Dirty-memory retrieval for decisions
- Source fetching outside Source Governor boundaries
- Job creation outside Central Scheduler boundaries
- Real source calls (transport is still fixture-only after E2H)

---

## 9. What Needs to Be Built (Next Lane)

Before the first real bounded 15m cycle can run:

1. A real source adapter must replace `FixtureSourceAdapter` in the governed
   execution path.
2. `check_real_source_transport_available()` must be updated to return `(True, "")`.
3. After the real adapter is committed, rerun E2G to confirm `OPERATOR_RUN_READY`.
4. Run the `exact_operator_run_command` manually against the real DB.

---

## 10. All V1 Restrictions Remain Active

After E2H, all Printer V1 restrictions from `AGENTS.md` and
`docs/printer-v1-clean-master-spec.md` remain fully active:

- Solana only. No multi-chain.
- Paper trading only. No real wallet. No private keys. No live execution.
- Free/public data only. No paid APIs.
- Memory comparison only. No scoring system.
- No BUY, SELL, or HOLD until separately unlocked under approved conditions.
- 5m remains support-only.
- 1h, 4h, 12h, 24h remain locked until separately approved.

---

## 11. Stop Conditions

Operator must stop immediately if any of the following occur:

- `check_real_source_transport_available()` returns True unexpectedly without
  a real adapter being implemented and committed.
- Any source adapter makes network calls outside Source Governor boundaries.
- Any BUY, SELL, or HOLD decision row is created.
- Any paper position, trade event, or PnL row is created.
- Any forbidden table receives new rows.
- Any hard-lock flag is True when it should be False.
- `TRACK_FAST_FIRST_15M` job processed with more than 1 approved token.
- `TRACK_FAST_FIRST_15M` job processed with a non-TRACK_FAST lifecycle lane.
- Any direct source adapter call outside Source Governor boundaries.
- 5m targeted as main window (must remain support-only).

---

## 12. Rollback Checklist

If the real cycle unexpectedly mutates the DB:

```
[ ] Stop immediately if any unexpected row appears outside allowed table changes.
[ ] Confirm backup file exists: Test-Path <backup_proof_path>
[ ] Rename current DB to preserve state: Rename-Item data\printer_v1.sqlite3 data\printer_v1_unexpected_state_<ts>.sqlite3
[ ] Copy backup to DB path: Copy-Item -Path <backup_proof_path> -Destination data\printer_v1.sqlite3
[ ] Confirm restore: Test-Path data\printer_v1.sqlite3
[ ] Rerun E2C-C preflight to confirm DB state is clean after restore.
[ ] Review git status --short for unexpected changes.
[ ] Review git log --oneline -10 for unexpected commits.
[ ] Do not delete backup until lane is confirmed stable.
[ ] Report any unexpected source calls, row creation, or errors.
```

---

## 13. Next Lane Boundary

After E2H commit/tag:

1. Implement a real source adapter to replace FixtureSourceAdapter.
2. Update `check_real_source_transport_available()` to return (True, "").
3. Commit and tag the real adapter lane.
4. Rerun E2G to confirm OPERATOR_RUN_READY.
5. Run the bounded cycle manually against the real DB.
6. Compare before/after row counts against before_db_counts.
7. Review results; operator must explicitly name and approve the next lane.
8. BUY, SELL, HOLD, positions, and PnL remain locked until separately approved.

---

## 14. E2H Hard Lock Summary

All 11 hard-lock flags remain False in E2H handler output:

| Flag | E2H Value |
|------|-----------|
| source_fetching_enabled | false |
| scheduler_execution_enabled | false |
| snapshot_creation_enabled | false |
| memory_creation_enabled | false |
| retrieval_activation_enabled | false |
| paper_decisions_enabled | false |
| buy_enabled | false |
| sell_enabled | false |
| hold_enabled | false |
| positions_enabled | false |
| pnl_enabled | false |

---

*Document status: E2H handler boundary built -- handler registered, real source
transport still fixture-only, real cycle remains manual.*
*Anchor: Lane E2H anchored to E2G tag
`printer-v1-post-lane10-lane-e2g-first-bounded-15m-cycle-operator-run`.*
