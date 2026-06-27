# Printer V1 Lane E2G -- First Bounded 15m Cycle Operator Run Boundary

## 1. Purpose

E2G defines the operator run boundary for the first bounded source-governed
15m Memory Factory cycle.

Lane E2G is a pre-run planning and gate-check package. Claude did not run the
real cycle. The operator must run the real command manually after committing
and tagging Lane E2G.

Lane E2G does NOT authorize real execution by itself. Before any real cycle:
1. Commit and tag Lane E2G.
2. Build the real TRACK_FAST_FIRST_15M runtime job handler (next lane).
3. Rerun the E2G boundary check to confirm OPERATOR_RUN_READY.
4. Run the exact_operator_run_command manually against the real DB.

---

## 2. Discovery Finding

**The real bounded 15m Memory Factory cycle runtime path does NOT exist
in the current build.**

Evidence:
- `PHASE35_SAFE_JOB_KINDS = {"BACKUP_SOURCE_CHECK"}` in `commands.py`
- `_execute_phase35_scheduler_job` raises `UNSUPPORTED_JOB_KIND_PHASE35`
  for any job kind not in `PHASE35_SAFE_JOB_KINDS`
- The existing `printer-run-bounded` (Phase 36) only handles `BACKUP_SOURCE_CHECK`
- No `TRACK_FAST_FIRST_15M` or `TRACK_NORMAL_FIRST_15M` job handler exists
- `governed_execution.py` is fixture-only -- no real source adapter network calls

Therefore E2G outputs `BLOCKED` until a real TRACK_FAST_FIRST_15M handler
is implemented. The real cycle remains manual after E2G commit/tag.

---

## 3. Anchor

- Lane E2F commit: `c5e54ba`
- Lane E2F tag: `printer-v1-post-lane10-lane-e2f-first-bounded-15m-cycle-execution-boundary`
- E2F is closed. E2F returned CYCLE_READY_TO_RUN.
- Backup proof: `data/backups/printer_v1_before_first_bounded_15m_cycle_20260627_200707.sqlite3`

Lane E2G is anchored to the E2F tag above.

---

## 4. E2G Operator Run Package

Lane E2G delivers:

- `src/printer_v1/operator_cli/e2g_operator_run.py`
- CLI command `printer-run-e2g-first-bounded-15m-operator-run`
- Tests in `tests/test_post_rc_lane_e2g_first_bounded_15m_cycle_operator_run.py`
- This operator run document

E2G outputs `OPERATOR_RUN_READY` or `BLOCKED`.

`OPERATOR_RUN_READY` means all automated boundary gates passed AND a real
TRACK_FAST_FIRST_15M runtime handler is confirmed to exist. It does NOT mean
the cycle was run. The operator must run the command manually.

Currently outputs `BLOCKED` because the runtime handler does not exist.

### 4.1 E2G boundary gates

All of the following must pass for `OPERATOR_RUN_READY`:

1. E2F `cycle_status` is `CYCLE_READY_TO_RUN`
2. Backup proof file physically exists at `--backup-proof-path`
3. `TRACK_FAST_FIRST_15M` runtime job handler is implemented
4. Token count is exactly 1 (E2G first-run constraint)
5. `--approval-confirmed` flag is set
6. `--backup-confirmed` flag is set
7. Zero RUNNING scheduler jobs
8. Zero active locks (locked_at or lock_owner)
9. Source Governor budget allows requests
10. Token list valid (no placeholders, approved_by_operator true)
11. All 11 hard-lock flags are False
12. No persistent DB mutation detected

If any gate fails, the output is `BLOCKED` with all reasons listed.

### 4.2 CLI

```
printer-run-e2g-first-bounded-15m-operator-run \
  --token-list-path <PATH_TO_TOKEN_LIST_JSON> \
  --approval-confirmed \
  --backup-confirmed \
  --backup-proof-path <PATH_TO_BACKUP_FILE> \
  --db-path <PATH_TO_DB> \
  --format json
```

### 4.3 Payload structure

```json
{
  "command": "printer-run-e2g-first-bounded-15m-operator-run",
  "dry_run": true,
  "planning_only": true,
  "claude_did_not_run_cycle": true,
  "e2f_execution_boundary": { "...full E2F payload..." },
  "first_run_status": "OPERATOR_RUN_READY | BLOCKED",
  "first_run_status_reasons": ["..."],
  "e2g_status": "E2G_OPERATOR_RUN_READY | E2G_OPERATOR_RUN_BLOCKED",
  "runtime_path_exists": false,
  "runtime_path_reason": "...",
  "backup_proof_confirmed": true | false,
  "backup_proof_reason": "...",
  "before_db_counts": { "printer_source_requests": N, ... },
  "exact_operator_run_command": "...inert text only...",
  "allowed_table_deltas": { "...tables allowed to change..." },
  "forbidden_table_deltas": ["...tables that must not change..."],
  "stop_conditions": ["..."],
  "rollback_checklist": ["[ ] ..."],
  "hard_locks": { "...all 11 flags, all false..." },
  "next_required_operator_action": "..."
}
```

### 4.4 exact_operator_run_command

The `exact_operator_run_command` field is inert text only. It does NOT execute.
Claude did not run this command. The operator must run it manually after
committing and tagging Lane E2G and after a real TRACK_FAST_FIRST_15M handler
is implemented.

### 4.5 before_db_counts

The `before_db_counts` field records row counts for audited tables at the time
this planning module runs. The operator should compare these counts against
post-run counts to verify only allowed tables changed.

### 4.6 Execution boundaries enforced

All source calls must go through Source Governor (`can_request_source`).

All job scheduling must go through Central Scheduler job tables
(`printer_scheduler_jobs`).

No direct source adapter calls are permitted from execution engines.

No BUY, SELL, or HOLD decisions during the cycle.

No paper positions, trade events, or PnL rows.

Maximum 1 approved token for the first run (E2G constraint).

Target window: WINDOW_15M (15m main window; 5m remains support-only).

---

## 5. Allowed Cycle Effects (After Real Handler Built and Operator Runs)

When the operator runs the bounded execution command against the real DB after
the TRACK_FAST_FIRST_15M handler is implemented:

| Table | Condition |
|-------|-----------|
| `printer_source_requests` | Each governed source request |
| `printer_source_responses` | Each governed source response |
| `printer_source_failures` | If a governed source call fails |
| `printer_scheduler_jobs` | Job rows managed by Central Scheduler |
| `printer_token_snapshots` | Only if source evidence is clean |
| `printer_context_snapshots` | Only if table exists and context path runs |
| `printer_contexts` | Only if table exists and evidence passes gates |
| `printer_memory_windows` | Only if 15m window closes with sufficient evidence |
| `printer_memories` | Only if all clean-memory quality gates pass |

Zero clean memories is a valid first-run outcome. No row is forced.

The following tables must NOT receive new rows:

- `printer_paper_decisions` -- remain locked
- `printer_paper_positions` -- remain locked
- `printer_paper_trade_events` -- remain locked
- `printer_paper_trade_audits` -- remain locked
- Any BUY/SELL/HOLD decision rows -- remain locked

---

## 6. What E2G Does NOT Authorize

`OPERATOR_RUN_READY` and the E2G boundary do NOT authorize:

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
- Any real execution before a TRACK_FAST_FIRST_15M handler is implemented

---

## 7. What Needs to Be Built (Next Lane)

Before the first real bounded 15m cycle can run:

1. A real `TRACK_FAST_FIRST_15M` job handler must be implemented.
2. The handler must be bounded by Source Governor and Central Scheduler.
3. The handler must only produce rows in allowed_table_deltas.
4. The handler must fail closed on any forbidden table mutation.
5. The handler must be tested and committed in a separately named lane.
6. After the handler is committed, rerun E2G to confirm `OPERATOR_RUN_READY`.

---

## 8. All V1 Restrictions Remain Active

After E2G, all Printer V1 restrictions from `AGENTS.md` and
`docs/printer-v1-clean-master-spec.md` remain fully active:

- Solana only. No multi-chain.
- Paper trading only. No real wallet. No private keys. No live execution.
- Free/public data only. No paid APIs.
- Memory comparison only. No scoring system.
- No BUY, SELL, or HOLD until separately unlocked under approved conditions.
- 5m remains support-only.
- 1h, 4h, 12h, 24h remain locked until separately approved.

---

## 9. Stop Conditions

Operator must stop immediately if any of the following occur:

- E2F `cycle_status` is not `CYCLE_READY_TO_RUN`.
- `TRACK_FAST_FIRST_15M` runtime handler is not implemented.
- Backup proof file does not exist at the provided path.
- `--approval-confirmed` was not explicitly set.
- `--backup-confirmed` was not explicitly set.
- DB backup does not exist or was not confirmed.
- DB file does not exist at the expected path.
- Token list validation reports `valid=false`.
- Token count is not exactly 1 for first run.
- `approved_by_operator` is `false` or missing.
- Placeholder mint remains in the token list.
- Any source reports `allowed=false` from Source Governor.
- Any `governor_decision` is `rate_limit_exceeded`.
- Any row with `status=RUNNING` in `printer_scheduler_jobs`.
- Any row with `locked_at IS NOT NULL` in `printer_scheduler_jobs`.
- Any row with `lock_owner` set in `printer_scheduler_jobs`.
- Any hard-lock flag is `true` when it should be `false`.
- Any direct source adapter call outside Source Governor boundaries.
- Any paper decision, position, trade event, or PnL row created.
- Any row created outside `allowed_table_deltas`.
- 5m targeted as main window (must remain support-only).

---

## 10. Rollback Checklist

If the real cycle mutates the DB unexpectedly:

```
[ ] Stop immediately if any unexpected row appears outside allowed_table_deltas.
[ ] Confirm backup file exists: Test-Path <backup_proof_path>
[ ] Rename current DB: Rename-Item data\printer_v1.sqlite3 data\printer_v1_unexpected_state_<ts>.sqlite3
[ ] Copy backup to DB path: Copy-Item -Path <backup_proof_path> -Destination data\printer_v1.sqlite3
[ ] Confirm restore: Test-Path data\printer_v1.sqlite3
[ ] Rerun E2C-C preflight to confirm DB state is clean after restore.
[ ] Review git status --short for unexpected changes.
[ ] Review git log --oneline -10 for unexpected commits.
[ ] Do not delete backup until lane is confirmed stable.
[ ] Report any unexpected source calls, row creation, or errors.
```

---

## 11. Next Lane Boundary

After E2G commit/tag:

1. Build the real `TRACK_FAST_FIRST_15M` runtime job handler (next lane).
2. Test the handler against a fixture DB; do not run against real DB until tested.
3. Commit and tag the handler lane.
4. Rerun E2G to confirm `OPERATOR_RUN_READY`.
5. Run the bounded cycle manually against the real DB.
6. Compare before/after row counts against `before_db_counts`.
7. Review results; the operator must explicitly name and approve the next lane.
8. BUY, SELL, HOLD, positions, and PnL remain locked until separately approved.

---

## 12. E2G Hard Lock Summary

All 11 hard-lock flags remain False in E2G planning output:

| Flag                          | E2G Value |
|-------------------------------|-----------|
| source_fetching_enabled       | false     |
| scheduler_execution_enabled   | false     |
| snapshot_creation_enabled     | false     |
| memory_creation_enabled       | false     |
| retrieval_activation_enabled  | false     |
| paper_decisions_enabled       | false     |
| buy_enabled                   | false     |
| sell_enabled                  | false     |
| hold_enabled                  | false     |
| positions_enabled             | false     |
| pnl_enabled                   | false     |

---

*Document status: E2G operator run boundary -- real runtime path does not yet exist;
Claude did not run the cycle.*
*Anchor: Lane E2G anchored to E2F tag
`printer-v1-post-lane10-lane-e2f-first-bounded-15m-cycle-execution-boundary`.*
