# Printer V1 Lane E2F -- First Bounded 15m Cycle Execution Boundary

## 1. Purpose

E2F defines the first execution boundary for the first bounded source-governed
15m Memory Factory cycle.

Lane E2F is an execution-boundary planning package. Claude did not run the real
cycle. The operator must run the real command manually after committing and tagging
Lane E2F.

Lane E2F does NOT authorize real execution by itself. The operator must:
1. Commit and tag Lane E2F.
2. Review the E2F payload and confirm `CYCLE_READY_TO_RUN`.
3. Run the `exact_operator_run_command` manually against the real DB.

The first cycle is bounded to 1-2 operator-approved tokens and the 15m target window.

5m remains support-only. BUY, SELL, HOLD, paper decisions, positions, and PnL
remain locked. All V1 restrictions remain active.

---

## 2. Anchor

- Lane E2E commit: `16f2979`
- Lane E2E tag: `printer-v1-post-lane10-lane-e2e-first-bounded-cycle-approval-packet`
- E2E is closed.

Lane E2F is anchored to the E2E tag above.

---

## 3. E2F Execution Boundary Package

Lane E2F delivers:

- `src/printer_v1/operator_cli/e2f_execution_boundary.py`
- CLI command `printer-run-first-bounded-15m-cycle`
- Tests in `tests/test_post_rc_lane_e2f_first_bounded_15m_cycle_execution_boundary.py`
- This execution boundary document

E2F outputs `CYCLE_READY_TO_RUN` or `BLOCKED`.

`CYCLE_READY_TO_RUN` means all automated boundary gates have passed. It does NOT
mean the cycle was run. The operator must run the command manually.

### 3.1 Execution boundary gates

All of the following must pass for `CYCLE_READY_TO_RUN`:

1. E2E `approval_packet_status` is `APPROVAL_PACKET_READY`
2. `--approval-confirmed` flag is explicitly set by operator
3. `--backup-confirmed` flag is explicitly set by operator
4. DB backup confirmed (propagated from E2E -> E2D -> E2C-F gates)
5. DB exists and is accessible
6. Zero RUNNING scheduler jobs
7. Zero active scheduler locks (locked_at or lock_owner)
8. Source Governor budget allows requests
9. Token list valid (1-2 tokens, no placeholders, all approved)
10. All 11 hard-lock flags are False
11. No persistent DB mutation detected

If any gate fails, the output is `BLOCKED` with reasons listed.

### 3.2 Payload structure

```json
{
  "command": "printer-run-first-bounded-15m-cycle",
  "dry_run": true,
  "planning_only": true,
  "claude_did_not_run_cycle": true,
  "e2e_approval_packet": { "...full E2E approval packet..." },
  "cycle_status": "CYCLE_READY_TO_RUN | BLOCKED",
  "cycle_status_reasons": ["..."],
  "e2f_status": "E2F_EXECUTION_BOUNDARY_READY | E2F_EXECUTION_BOUNDARY_BLOCKED",
  "exact_operator_run_command": "...inert text only...",
  "mutation_plan": { "...what would be written by the real cycle..." },
  "stop_conditions": ["..."],
  "rollback_checklist": ["[ ] ..."],
  "hard_locks": { "...all 11 flags, all false..." },
  "next_required_operator_action": "..."
}
```

### 3.3 exact_operator_run_command

The `exact_operator_run_command` field contains inert text only. It does NOT execute
any command. Claude did not run this command. The operator must run it manually against
the real DB after committing and tagging Lane E2F.

### 3.4 Execution boundaries enforced

All real source calls must go through the Source Governor (`can_request_source`).

All job scheduling must go through the Central Scheduler job tables
(`printer_scheduler_jobs`).

No direct source adapter calls are permitted from execution engines outside the
Source Governor boundary.

No BUY, SELL, or HOLD decisions may be created during the cycle.

No paper positions, trade events, or PnL rows may be created.

---

## 4. Allowed Cycle Effects (After Operator Runs Manually)

When the operator runs the bounded execution command manually against the real DB,
the following rows may be created:

| Table | Condition |
|-------|-----------|
| `printer_source_requests` | Each governed source request |
| `printer_source_responses` | Each governed source response |
| `printer_source_failures` | If a governed source call fails |
| `printer_scheduler_jobs` | Job rows managed by Central Scheduler |
| `printer_token_snapshots` | Only if source evidence is clean |
| `printer_context_snapshots` | Only if context collection runs and passes gates |
| `printer_contexts` | Only if context evidence passes existing gates |
| `printer_memory_windows` | Only if a 15m window closes with sufficient evidence |
| `printer_memories` | Only if all memory quality gates pass |

Zero clean memories is a valid outcome. No row is forced.

The following tables must NOT receive new rows:

- `printer_paper_decisions` -- paper decisions remain locked
- `printer_paper_positions` -- paper positions remain locked
- `printer_trade_events` -- trade events remain locked
- `printer_paper_trade_audits` -- paper trade audits remain locked

---

## 5. What E2F Does NOT Authorize

`CYCLE_READY_TO_RUN` and the E2F execution boundary do NOT authorize:

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

---

## 6. All V1 Restrictions Remain Active

After E2F, all Printer V1 restrictions from `AGENTS.md` and
`docs/printer-v1-clean-master-spec.md` remain fully active:

- Solana only. No multi-chain.
- Paper trading only. No real wallet. No private keys. No live execution.
- Free/public data only. No paid APIs.
- Memory comparison only. No scoring system.
- No BUY, SELL, or HOLD until separately unlocked under approved conditions.
- 5m remains support-only.
- 1h, 4h, 12h, 24h remain locked until separately approved.

---

## 7. Stop Conditions

Operator must stop immediately if any of the following occur:

- E2E `approval_packet_status` is not `APPROVAL_PACKET_READY`.
- `--approval-confirmed` flag was not explicitly set.
- DB backup does not exist or was not confirmed.
- DB file does not exist at the expected path.
- Token list validation reports `valid=false`.
- Any `token_mint` fails Solana base58 format check.
- `lifecycle_lane` is not `TRACK_FAST` or `TRACK_NORMAL`.
- Duplicate `token_mint` values in the list.
- Token count is 0 or greater than 2.
- `approved_by_operator` is `false` or missing for any token.
- Placeholder mints remain in the token list.
- Any source reports `allowed=false` from Source Governor.
- Any `governor_decision` is `rate_limit_exceeded`.
- Any row with `status=RUNNING` in `printer_scheduler_jobs`.
- Any row with `locked_at IS NOT NULL` in `printer_scheduler_jobs`.
- Any row with `lock_owner` set in `printer_scheduler_jobs`.
- Any hard-lock flag is `true` when it should be `false`.
- Any direct source adapter call outside Source Governor boundaries.
- Any paper decision, position, trade event, or PnL row created.

---

## 8. Rollback Checklist

If the real cycle mutates the DB unexpectedly:

```
[ ] Stop immediately if any unexpected row appears outside allowed_table_deltas.
[ ] Confirm backup file exists: Test-Path <backup_path>
[ ] Rename current DB: Rename-Item data\printer_v1.sqlite3 data\printer_v1_unexpected_state_<ts>.sqlite3
[ ] Copy backup to DB path: Copy-Item -Path <backup_path> -Destination data\printer_v1.sqlite3
[ ] Confirm restore: Test-Path data\printer_v1.sqlite3
[ ] Rerun E2C-C preflight to confirm DB state is clean after restore.
[ ] Review git status --short for unexpected changes.
[ ] Review git log --oneline -10 for unexpected commits.
[ ] Do not delete the backup file until the lane is confirmed stable.
[ ] Report any unexpected row creation, source calls, or errors.
```

---

## 9. Next Lane Boundary

After the first bounded cycle runs and completes:

- The cycle result (zero or more clean memories) must be reviewed.
- The operator must explicitly name and approve a next lane.
- BUY, SELL, HOLD, positions, and PnL remain locked until separately approved.
- 5m remains support-only.
- 1h, 4h, 12h, 24h remain locked until separately approved.

---

## 10. E2F Hard Lock Summary

All 11 hard-lock flags remain False in E2F planning output:

| Flag                          | E2F Value |
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

These flags govern the planning payload. The real cycle execution is not controlled
by these flags directly -- the real cycle is bounded by the Central Scheduler and
Source Governor boundaries.

---

*Document status: E2F execution-boundary planning -- defines boundary, Claude did not run cycle.*
*Anchor: Lane E2F anchored to E2E tag `printer-v1-post-lane10-lane-e2e-first-bounded-cycle-approval-packet`.*
