# Printer V1 — Lane X13: WINDOW_1H Operator Proof Readiness / Runbook

**Type:** Documentation and runbook only. No code changes. No tests. No runtime.
No source fetching. No DB writes. No real WINDOW_1H collection. No CLI execution.
Do not run `printer-run-lane-x12-fast-1h-cycle` or `printer-run-lane-x12-normal-1h-cycle`
in this lane. Do not run X10.10C. Do not start real WINDOW_1H collection.

**Date:** 2026-07-08

**Prerequisite anchor commits:**
- `4ae4313` — X11: 1h Activation Readiness Review
  Tag: `printer-v1-lane-x11-1h-activation-readiness`
- `bfc6e2d` — X12: WINDOW_1H Structural Implementation
  Tag: `printer-v1-lane-x12-1h-structural-implementation`

---

## Todo / Checklist

- [x] Read AGENTS.md
- [x] Read docs/printer-v1-clean-master-spec.md
- [x] Read docs/printer-v1-post-rc-build-order.md
- [x] Read docs/printer-v1-memory-factory-guide.md
- [x] Read docs/printer-v1-lane-x11-1h-activation-readiness.md
- [x] Read src/printer_v1/operator_cli/lane_x12_1h_runner.py
- [x] Read src/printer_v1/operator_cli/lane_e2o_1h_window_close.py
- [x] Read src/printer_v1/operator_cli/lane_e2h_fast_1h_handler.py
- [x] Read src/printer_v1/operator_cli/lane_e2h_normal_1h_handler.py
- [x] Read src/printer_v1/snapshots/cadence_policy.py
- [x] Read src/printer_v1/scheduler/contracts.py
- [x] Write docs/printer-v1-lane-x13-1h-operator-proof-readiness.md

---

## 1. Purpose

Lane X13 is the operator proof readiness runbook for the first real WINDOW_1H collection run.

X12 built all required structural components for WINDOW_1H: scheduler job kinds, the 1h window
close boundary, TRACK_FAST and TRACK_NORMAL handlers, the Lane Q coverage policy, the bounded
runner, CLI commands, and a 99-test suite. X12 did NOT run a live proof. No real WINDOW_1H
records exist in the DB. The structural code is tested and committed, but the live proof has
not been executed.

X13 designs the first real proof so the operator can run it with full knowledge of what will
happen, what is acceptable, and what is not acceptable. X13 is NOT an authorization to start
collection. It is the pre-flight specification that a future Lane X14 will execute.

Lane X13 does NOT:
- Run the X12 CLI against any DB.
- Authorize real WINDOW_1H collection in this session.
- Change any source code.
- Write any DB rows.
- Fetch any source data.
- Unlock retrieval, paper decisions, BUY, SELL, HOLD, positions, PnL, or live trading.
- Supersede any rule in the source-of-truth stack.

Lane X13 DOES:
- Confirm which proof shape (TRACK_FAST or TRACK_NORMAL) is safer for a first run and why.
- Specify the exact CLI command template an operator would run in X14.
- Define required DB backup steps before any proof run.
- Define the required token-list shape and size for a first proof.
- Define all required operator approval flags.
- Define expected output fields and what constitutes success vs. dirty vs. stopped.
- Define all stop conditions that the runner enforces automatically.
- Define the lock verification checklist an operator must confirm before and after.
- Define dirty-memory expectations and pair drift handling.
- Define which post-run reports to collect.
- Define the commit policy after a successful proof.
- Define what X14 should and must not do.

---

## 2. Source-of-Truth Constraints

All rules below are inherited from the source-of-truth stack and apply without exception to
Lane X13, the future Lane X14 proof run, and all subsequent 1h lanes.

### From AGENTS.md (V1 Locked Rules)

- Solana-only. Solana memecoin-only. Paper-trading only.
- No live wallet. No private keys. No real funds. No live execution.
- No paid API dependency.
- No scoring system. No ranking system. No confidence percentage system.
- No weighted decision logic.
- No engine bypassing Source Governor. No engine bypassing Central Scheduler.
- No paper decision without clean memory comparison.
- No paper position without valid clean-memory-backed paper decision.
- No dirty memory training decisions.
- No vectors/embeddings unless explicitly approved later.
- WINDOW_5M_MICRO_EVENT is support-only. It must never become a main outcome window.
- Do not run X10.10C as part of this lane.

### From docs/printer-v1-clean-master-spec.md

- WINDOW_1H role: "Short-term continuation/failure memory."
- 1h must start after 15m factory behavior is stable.
- 4h must wait until 1h memory is clean and scheduler/source capacity is stable.
- All snapshot evidence must have `source_status = COMPLETE` and
  `data_quality_label = CLEAN_DATA` to be eligible for clean memory promotion.
- Dirty, stale, incomplete, delayed, or broken data must not become clean memory.

### From docs/printer-v1-post-rc-build-order.md

- Post-RC Lane 6 exit gate: longer windows are structurally supported; real operation remains
  15m-only until approved.
- WINDOW_1H collection is approved after X11 design and X12 structural implementation are
  committed and the operator explicitly authorizes the first proof.

### From docs/printer-v1-memory-factory-guide.md

- Memory Factory activation order: (1) 15m main + 5m support, (2) 1h continuation/failure,
  (3) 4h medium-term, (4) 12h/24h.
- `open 1h only if token remains useful/eligible after 15m`
- `TRACK_FAST: continue to 1h if token survives and data remains useful`
- `TRACK_NORMAL: open 1h only if token remains useful/eligible after 15m`

### From docs/printer-v1-lane-x11-1h-activation-readiness.md (Section 20, Step 9)

> Using an isolated proof DB (copy of current `data/printer_v1.sqlite3` to a backup path):
> - Run X12 TRACK_FAST 1h runner with 1-3 known tokens.
> - Duration: single 1h proof (bounded).
> - Expected result: 1-3 WINDOW_1H records created; covered windows promoted; locks all zero delta.
> - Operator reviews before any live DB merge.

Lane X13 refines this guidance into an exact specification.

---

## 3. Current State After X12

### 3.1 What X12 Built (All Confirmed Committed)

| Component | File | Status |
|-----------|------|--------|
| Scheduler job kinds | `scheduler/contracts.py` | `TRACK_FAST_1H` and `TRACK_NORMAL_1H` in `JobKind` and `JOB_PRIORITY_ORDER` |
| WINDOW_1H close boundary | `lane_e2o_1h_window_close.py` | Created. Idempotency on `snapshot_start_id`. Pair drift detection. |
| TRACK_FAST_1H handler | `lane_e2h_fast_1h_handler.py` | Created. 6-gate architecture. Hard freshness gate. |
| TRACK_NORMAL_1H handler | `lane_e2h_normal_1h_handler.py` | Created. 6-gate architecture. Advisory freshness only. |
| Cadence policy WINDOW_1H | `snapshots/cadence_policy.py` | TF: min=8/gap=600s/interval=240s. TN: min=3/gap=1800s/interval=720s. Both `enabled_for_real_collection=True`. |
| Bounded 1h runner | `lane_x12_1h_runner.py` | Created. FAST mode (1-5 tokens). NORMAL mode (1-7 tokens). `_adapter_map` test bypass. `_cycle_budget` gate. |
| CLI — TRACK_FAST | `commands.py` + `pyproject.toml` | `printer-run-lane-x12-fast-1h-cycle` registered. |
| CLI — TRACK_NORMAL | `commands.py` + `pyproject.toml` | `printer-run-lane-x12-normal-1h-cycle` registered. |
| Test suite | `tests/test_post_lane10_lane_x12_1h_runner.py` | 99 tests. All pass. |

### 3.2 Regression Test State After X12

| Test suite | Test count | Result |
|------------|-----------|--------|
| X12 new suite | 99 | PASS |
| X10.10B TRACK_NORMAL 15m runner | 72 | PASS |
| X5 five-token runner | 174 | PASS |
| X10.9 freshness gate | 38 | PASS |
| X10.6 discovery/selection traceability | 105 | PASS |
| X6 discovery/selection repair | 150 | PASS |
| **Total** | **638** | **ALL PASS** |

### 3.3 What X12 Did NOT Do

- Did not run any real WINDOW_1H collection.
- Did not write any WINDOW_1H rows to `data/printer_v1.sqlite3`.
- Did not create any paper decisions, positions, trade events, PnL, or retrieval records.
- Did not run the X12 CLI against the live DB.
- Did not activate retrieval, BUY, SELL, HOLD, or any financial capability.
- Did not enable 4h, 12h, or 24h windows.

### 3.4 Current DB State (Post-X12, Pre-X13 Proof)

| Window Kind | Records | Status |
|-------------|---------|--------|
| WINDOW_15M | Multiple (includes 18+ clean episodes) | Active, growing |
| WINDOW_1H | **0** | **Never collected** |
| WINDOW_5M_MICRO_EVENT | Present as support rows | Support-only |
| WINDOW_4H / 12H / 24H | 0 | Disabled |

---

## 4. Why X13 Is Documentation-Only

X12 built the structure. X13 designs the proof. The actual proof execution belongs to X14.

The separation of documentation (X13) from execution (X14) is intentional:

1. **Operator review before execution.** A real proof run against the live DB (or a copy of it)
   is an irreversible operation in the sense that it creates real DB rows, accumulates source
   request budget, and may produce DIRTY_MEMORY records that need to be audited. The operator
   must understand exactly what will happen before the first run.

2. **Token selection is not yet decided.** The first proof requires specific tokens with known
   recent source evidence and confirmed pair addresses. Token selection is an operator task that
   happens in X14 preparation, not a code task that can be done in X13.

3. **Proof DB isolation must be set up before execution.** The first real WINDOW_1H proof must
   run against a copy of the live DB, not the live DB itself. Setting up that isolation is an
   operator action, not a code change.

4. **Precedent from X10.7/X10.8.** The first WINDOW_15M live proof used the same approach: X10.9
   (freshness gate review) → X10.10A (audit) → X10.7 (first proof run). X13 follows this pattern.

5. **Post-RC Lane 6 exit gate requires explicit operator approval per run.** The Post-RC build
   order requires operator approval before each real collection run. X13 is the approval design
   for that gate. X14 is the actual approval and execution.

---

## 5. First Proof Recommendation: TRACK_FAST or TRACK_NORMAL?

**Recommendation: TRACK_FAST with 1 token.**

### Reasoning

#### Safety argument for TRACK_FAST

TRACK_FAST has a hard freshness gate (X10.9 pattern). Before the runner starts, it checks whether
the token's last source evidence is within 300 seconds. If the token is stale, the run is blocked
before a single source call is made. This means:

- A stale or dead token cannot accidentally run for 45 minutes at 240s cadence accumulating
  failed snapshots and DIRTY_MEMORY records.
- The operator is forced to confirm the token is fresh before the proof starts.
- If the token dies during the 45-minute window, the source budget failure counter stops the run.

TRACK_NORMAL's advisory-only freshness means a stale token can proceed. For a first proof,
the hard gate is safer — it enforces a pre-run sanity check automatically.

#### Evidence density argument for TRACK_FAST

TRACK_FAST targets ~11 snapshots in the 45-minute continuation window. The minimum for clean
promotion is 8 (72% coverage). This gives enough margin to validate the Lane Q coverage audit
at the end of the window without requiring perfect cadence.

TRACK_NORMAL targets only ~4 snapshots with a minimum of 3 (75% coverage). While this sounds
like a lower bar, any single source failure in a TRACK_NORMAL proof leaves the coverage audit
at exactly the minimum. TRACK_FAST's higher density provides more evidence that the full pipeline
(snapshot → E2O → Lane Q → Lane K / E2Z) functions correctly end-to-end.

#### Operational predictability argument

TRACK_FAST memecoins are selected during fast-event windows (high volume, price action, activity).
For a bounded 45-minute proof, the token's fast-event status is the best available guarantee
that source calls during the window will return CLEAN_DATA rather than STALE_DATA or empty
responses. TRACK_NORMAL tokens are slower-moving; a first proof with a slow-moving token
that produces mostly PARTIAL_MEMORY would not prove the 1h pipeline end-to-end as definitively.

#### Why NOT TRACK_NORMAL first

- Advisory freshness does not automatically block a stale token — operator must verify manually.
- Lower snapshot count (~4) means a single failure produces minimum-coverage output.
- Slower cadence (720s = 12 min) means the first snapshot after start takes 12 minutes.
  If the first source call fails, it takes 24 minutes before the second attempt. A failed
  first proof takes much longer to diagnose.
- TRACK_NORMAL 1h is best proven after TRACK_FAST 1h is confirmed working.

#### Why NOT a mixed first proof

A mixed first proof (TRACK_FAST + TRACK_NORMAL tokens in one run) is not supported by the
`lane_x12_1h_runner.py` architecture: the two CLI commands are separate by design. The first
proof should use one mode only. Mixing would:
- Require running two CLI commands simultaneously (two separate DB connections).
- Complicate the audit: was the issue TRACK_FAST or TRACK_NORMAL?
- Use more source budget than necessary for a single proof.

Mixed 1h proofs belong to a later lane after both single-mode proofs are individually confirmed.

#### Why NOT 2-5 tokens for the first proof

More tokens means:
- More source calls per cadence cycle.
- More potential pair drift events to audit.
- More DIRTY_MEMORY records to explain if any token underperforms.
- More complex post-run analysis.

1 token is the minimum viable proof. It proves: the runner starts, creates TRACK_FAST_1H
scheduler jobs, collects snapshots, closes a WINDOW_1H record, runs Lane Q, runs Lane K/E2Z,
produces a clean episode (or explains why it is dirty), and terminates cleanly. All of this
can be confirmed from 1 token without any ambiguity about which token caused which outcome.

---

## 6. Recommended Token Count for First Proof

**1 token. TRACK_FAST only.**

Do not use 2-5 tokens for the first proof. Use 1 token that meets all of the following:

| Requirement | Reason |
|-------------|--------|
| `tracking_lane = "TRACK_FAST"` | Matches the recommended mode |
| `operator_approved = true` | Gate 0 pre-flight requires this |
| `chain = "solana"` | Solana-only constraint |
| Source evidence age ≤ 300s at run start | TRACK_FAST freshness gate hard-blocks otherwise |
| Confirmed pair address (not pair-drifted) | Pair drift at window open = immediate DIRTY_MEMORY |
| Token not in ARCHIVED, COOLDOWN, or INSTANT_REJECT state | Token lifecycle gate |
| Token has existing WINDOW_15M records (preferred) | Proves the token went through 15m first |
| ANSEM (token id=13) — excluded until pair drift resolved | X11 R8: unresolved pair ambiguity |

After the first proof succeeds with 1 TRACK_FAST token, the operator may escalate to:
- 2-3 TRACK_FAST tokens in a second proof.
- 1 TRACK_NORMAL token in a separate TRACK_NORMAL proof.
- Mixed-mode proofs only after both single-mode proofs are independently confirmed.

---

## 7. Required DB Backup Plan

**The first real WINDOW_1H proof must NOT run against the live `data/printer_v1.sqlite3` directly.**

### Step-by-step backup plan before executing X14

1. **Stop all running Printer V1 processes** (any X5, X10.10B, or other bounded runners).
   Confirm zero active scheduler locks: run `printer-report-e2u-15m-cycle-closeout` and
   verify `active_locks = 0`.

2. **Create a timestamped full backup of the live DB:**
   ```
   cp data/printer_v1.sqlite3 data/backups/printer_v1_pre_x14_proof_<YYYYMMDD_HHMMSS>.sqlite3
   ```
   Confirm the backup file exists and is non-zero in size.

3. **Create a proof copy of the live DB to run against:**
   ```
   cp data/printer_v1.sqlite3 data/proof_runs/printer_v1_x14_proof_<YYYYMMDD_HHMMSS>.sqlite3
   ```
   The proof run will write WINDOW_1H rows, scheduler jobs, and source records into this copy.
   The live DB is not touched during the proof run.

4. **Pass the proof copy as `--db-path` and the backup as `--backup-proof-path`:**
   ```
   --db-path data/proof_runs/printer_v1_x14_proof_<YYYYMMDD_HHMMSS>.sqlite3
   --backup-proof-path data/backups/printer_v1_pre_x14_proof_<YYYYMMDD_HHMMSS>.sqlite3
   ```

5. **After reviewing the proof run output**, decide whether to:
   - Merge the proof copy rows into the live DB (manual SQLite operation, separate operator task).
   - Discard the proof copy and repeat with a different token.
   - Archive the proof copy for audit records.

The backup file passed as `--backup-proof-path` must already exist on disk before the runner
starts. The runner checks `Path(backup_proof_path).is_file()` and blocks if the file is missing.
This enforces that a human confirmed the backup exists before any proof run begins.

### Backup integrity note

The runner does NOT write to the backup file. It is proof-of-existence only. The operator is
responsible for keeping the backup intact and confirming it is a complete copy of the DB
state at the moment the proof began.

---

## 8. Required Token-List Shape

The token list is a JSON file passed as `--token-list-path`. For the first proof:

```json
{
  "tokens": [
    {
      "token_mint": "<SOLANA_MINT_ADDRESS>",
      "pair_address": "<CONFIRMED_PAIR_ADDRESS>",
      "chain": "solana",
      "tracking_lane": "TRACK_FAST",
      "operator_approved": true
    }
  ]
}
```

### Field requirements

| Field | Type | Required | Rule |
|-------|------|----------|------|
| `token_mint` | string | Yes | 44-char base58 Solana mint address. No PLACEHOLDER values. |
| `pair_address` | string | Yes | Confirmed pair address for this token at proof time. No PLACEHOLDER values. |
| `chain` | string | Yes | Must be exactly `"solana"`. |
| `tracking_lane` | string | Yes | Must be exactly `"TRACK_FAST"` for the first proof. |
| `operator_approved` | boolean | Yes | Must be exactly `true` (not `"true"` as string, not `1`). |

### What to verify before saving the token list

- The token_mint corresponds to a token already in the proof DB's `printer_tokens` table.
- The pair_address corresponds to an active pair in `printer_pairs` for this token.
- The pair address was not involved in a drift event in recent X5 or X10.10B runs.
- The token has not been ARCHIVED or placed in COOLDOWN.
- A recent source response (within 300 seconds of proof run start time) exists or will be
  created by the runner's first snapshot cycle.

### Validator behavior

The runner's `_load_and_validate_token_list` function checks all the above constraints before
the proof run begins. If any check fails, the runner returns `LANE_X12_STATUS_BLOCKED` with
`blocked_reasons` listing exactly what failed. No source calls are made on a BLOCKED result.

---

## 9. Required Operator Approval Flags

Every CLI run of the X12 proof runner requires these two flags explicitly:

```
--operator-approved      (boolean flag — must be present on the command line)
--db-path                (must point to the proof copy, not the live DB)
```

Without `--operator-approved`, the runner immediately returns:

```json
{
  "lane_x12_status": "LANE_X12_BLOCKED",
  "blocked_reasons": ["operator_approved must be True to run the Lane X12 1h cycle"]
}
```

No source calls, no scheduler jobs, no DB writes are made before this gate passes.

Additional flags that must be set for a real proof (not left at 0):

| Flag | Required value for real proof | Reason |
|------|-------------------------------|--------|
| `--snapshot-interval-seconds` | `240.0` | TRACK_FAST 1h cadence (4 min). Set to 0 only in tests. |
| `--window-close-interval-seconds` | `2700.0` | 45-minute continuation window. Set to 0 only in tests. |
| `--throttle-backoff-seconds` | `2.0` (recommended) | Back off 2s after each source failure. Prevents rapid retry hammering. |
| `--source-budget-max-consecutive-failures` | `5` (default) | Safe stop after 5 consecutive failures. |

---

## 10. Required CLI Command Template

The first real WINDOW_1H proof uses the TRACK_FAST CLI. The exact command:

```bash
printer-run-lane-x12-fast-1h-cycle \
  --token-list-path /path/to/x14_proof_token_list.json \
  --db-path /path/to/data/proof_runs/printer_v1_x14_proof_<YYYYMMDD_HHMMSS>.sqlite3 \
  --backup-proof-path /path/to/data/backups/printer_v1_pre_x14_proof_<YYYYMMDD_HHMMSS>.sqlite3 \
  --operator-approved \
  --duration-profile 1h \
  --snapshot-interval-seconds 240.0 \
  --window-close-interval-seconds 2700.0 \
  --source-budget-max-consecutive-failures 5 \
  --throttle-backoff-seconds 2.0 \
  --format json
```

### Flag explanations

| Flag | Value | Effect |
|------|-------|--------|
| `--token-list-path` | path to JSON | Required. 1 TRACK_FAST token for the first proof. |
| `--db-path` | proof copy path | Required. Points to the proof copy, NOT the live DB. |
| `--backup-proof-path` | backup path | Required. Pre-existing backup file. Runner checks it exists. |
| `--operator-approved` | (flag, no value) | Required. Without this, immediate BLOCKED result. |
| `--duration-profile 1h` | `1h` = 3600s | Runner terminates after 3600s total runtime regardless of window state. |
| `--snapshot-interval-seconds 240.0` | 240s | Sleep 240s between cadence cycles (TRACK_FAST 1h cadence). |
| `--window-close-interval-seconds 2700.0` | 2700s | After 2700s of snapshots, trigger the WINDOW_1H close. |
| `--source-budget-max-consecutive-failures 5` | 5 | Stop after 5 consecutive failures (default; explicit for clarity). |
| `--throttle-backoff-seconds 2.0` | 2s | Sleep 2s after each failure before retrying. |
| `--format json` | json | Output the result as JSON for operator review and archival. |

### Expected wall-clock runtime

```
Startup + pre-flight:                  ~5-10 seconds
First snapshot (cycle 1):              ~2-5 seconds (source call + DB write)
Cadence sleep × 10 cycles:            10 × 240s = 2400 seconds (~40 minutes)
Final snapshot + window close:         ~5-15 seconds
Lane Q audit + Lane K/E2Z run:         ~2-5 seconds
Total:                                 ~2400-2500 seconds (~40-42 minutes)
```

The `--duration-profile 1h` limit (3600s) provides ~1 hour of headroom. The actual run
should complete in approximately 40-45 minutes.

### Do not use these flags for a real proof

```
_adapter_map       — test-only bypass; not accessible from CLI; skips freshness gate
_cycle_budget      — test-only; not accessible from CLI
--duration-profile 4h/12h/24h  — not for 1h proof
--allow-long-bounded-run       — only needed for 12h/24h profiles
--snapshot-interval-seconds 0  — test-only; would cause infinite rapid loops
--window-close-interval-seconds 0  — test-only; would close the window immediately after first snapshot
```

---

## 11. Runtime Duration and Cadence Settings

### Duration profile: `1h`

The `1h` duration profile sets the maximum total runtime to 3600 seconds. Within those 3600
seconds, the runner collects snapshots at 240s intervals and attempts to close the WINDOW_1H
after 2700 seconds of collection have elapsed from the first snapshot's timestamp.

Timeline for a 1-token TRACK_FAST proof:

```
t=0s:      Pre-flight gate passes. Job created and claimed.
t=0-5s:    First snapshot taken. Source call → DB write → snapshot_start_id recorded.
t=240s:    Second snapshot.
t=480s:    Third snapshot.
t=720s:    Fourth snapshot.
t=960s:    Fifth snapshot.
t=1200s:   Sixth snapshot.
t=1440s:   Seventh snapshot.
t=1680s:   Eighth snapshot.   ← Minimum for TRACK_FAST clean coverage (min=8)
t=1920s:   Ninth snapshot.
t=2160s:   Tenth snapshot.
t=2400s:   Eleventh snapshot.
t=2640s:   Twelfth snapshot.
t=2700s:   Window elapsed check: 2700s reached.
t=2700+:   Close snapshot taken → lane_e2o_1h_window_close called → Lane Q → Lane K/E2Z.
t=2700+:   Runner reports final status and exits.
```

The runner will not exceed 12-13 cadence cycles for a 1-token TRACK_FAST run with
`--window-close-interval-seconds 2700.0`.

### Cadence settings vs. test settings

| Setting | Real proof value | Test value | Why different |
|---------|-----------------|------------|---------------|
| `snapshot_interval_seconds` | 240.0 | 0.0 | Tests run in <1s; real runs wait 4 min between snapshots |
| `window_close_interval_seconds` | 2700.0 | 0.0 | Tests close immediately after first snapshot |
| `throttle_backoff_seconds` | 2.0 | 0.0 | Tests skip sleep; real runs back off on failure |

Using test settings in a real proof would immediately close the window after the first snapshot
(1 snapshot < 8 minimum → Lane Q blocks → DIRTY_MEMORY). This is the correct test behavior
but the wrong proof behavior. Always use real-proof cadence settings.

---

## 12. Expected Successful Output Fields

A successful first proof run should produce a JSON output with the following structure and values:

```json
{
  "command": "printer-run-lane-x12-fast-1h-cycle",
  "lane_x12_status": "LANE_X12_COMPLETED",
  "mode": "TRACK_FAST",
  "operator_approved": true,
  "window_kind": "WINDOW_1H",
  "selected_token_count": 1,
  "total_window_closes": 1,
  "total_1h_windows_created": 1,
  "clean_memory_rows_created": 0,
  "e2z_already_exists_count": 0,
  "dirty_or_blocked_memory_count": 0,
  "retrieval_rows_created": 0,
  "paper_decisions_created": 0,
  "positions_created": 0,
  "trade_events_created": 0,
  "paper_trade_audits_created": 0,
  "pnl_created": 0,
  "zero_clean_memories_is_valid": true,
  "buy_enabled": false,
  "sell_enabled": false,
  "hold_enabled": false,
  "pair_drift_detected": false,
  "total_pair_drift_events": 0,
  "total_source_failures": 0,
  "cadence_cycles_completed": 12,
  "actual_duration_seconds": [approximately 2700-3000],
  "token_reports": [
    {
      "slot": "A",
      "mint": "<MINT_ADDRESS>",
      "snapshots_created": 12,
      "memory_windows_created": 1,
      "window_closes": 1,
      "clean_memory_created": 0,
      "dirty_memory_count": 0,
      "pair_address_drift_count": 0,
      "source_failures_created": 0
    }
  ]
}
```

### Interpreting `clean_memory_rows_created = 0`

After one 45-minute WINDOW_1H collection, `clean_memory_rows_created` may be 0. This is valid
and expected. The Lane K / E2Z pipeline promotes clean episodes; the first proof establishes
the WINDOW_1H evidence record in `printer_memory_windows` as `PARTIAL_MEMORY` with
`data_quality_label = CLEAN_DATA`. Episode creation (CLEAN_MEMORY) may require multiple
clean WINDOW_1H records or a batch-run in E2Y/E2Z. `zero_clean_memories_is_valid = true`
confirms this is acceptable. The proof succeeds if `total_window_closes = 1` and the window
record is written to `printer_memory_windows` with valid `window_start_at` / `window_end_at` /
`snapshot_start_id` / `snapshot_end_id` fields.

### Minimum success criteria

All of the following must be true for the first proof to be considered a pass:

1. `lane_x12_status == "LANE_X12_COMPLETED"` — runner exited cleanly, not BLOCKED or STOPPED.
2. `total_window_closes >= 1` — at least one WINDOW_1H close was attempted.
3. `total_1h_windows_created >= 1` — at least one WINDOW_1H row was written to `printer_memory_windows`.
4. `paper_decisions_created == 0` — no paper decisions created.
5. `positions_created == 0` — no positions created.
6. `pnl_created == 0` — no PnL created.
7. `retrieval_rows_created == 0` — no retrieval records created.
8. `pair_drift_detected == false` — no pair drift in this run (or documented if true, see Section 17).
9. The DB query below returns at least one row with `window_kind = "WINDOW_1H"`.

**Post-run DB verification query:**
```sql
SELECT id, token_id, pair_id, window_kind, window_status, memory_status,
       snapshot_start_id, snapshot_end_id, window_start_at, window_end_at,
       elapsed_seconds_implied, created_by_phase
FROM printer_memory_windows
WHERE window_kind = 'WINDOW_1H'
ORDER BY created_at DESC
LIMIT 5;
```

The result should show:
- `window_status = "WINDOW_CLOSED"`
- `memory_status = "PARTIAL_MEMORY"` (eligible for Lane Q review)
- `snapshot_start_id` is not NULL
- `snapshot_end_id` is not NULL
- `window_start_at` is not NULL
- `window_end_at` is not NULL
- `elapsed_seconds_implied` is approximately 2700 (may be slightly more or less depending on
  actual cadence timing; values between 2400 and 3000 are normal)

---

## 13. Acceptable Blocked Outcomes

The following BLOCKED outcomes are expected and acceptable during the first proof. They are not
failures of the X12 code — they are correct safety responses to real conditions.

| Blocked outcome | `blocked_reasons` entry | Operator action |
|-----------------|------------------------|-----------------|
| Freshness gate: stale token | `"X10.9 freshness gate: slot A mint <MINT> (STALE_TRACK_FAST): ..."` | Wait for a fresh source response or select a different token |
| Missing backup file | `"backup_proof_path not found: <PATH>"` | Create the backup file before re-running |
| DB not found | `"db_path not found: <PATH>"` | Create the proof copy before running |
| `operator_approved` missing | `"operator_approved must be True..."` | Add `--operator-approved` flag |
| Wrong mode: TRACK_NORMAL token in FAST runner | `"token list invalid: ... TRACK_FAST..."` | Use `printer-run-lane-x12-normal-1h-cycle` for NORMAL tokens |
| Token count exceeds 5 | `"Lane X12 TRACK_FAST mode accepts at most 5 tokens..."` | Reduce to 1 token for first proof |
| Lane K / E2Z import unavailable | `"Lane K / E2Z path unavailable: ..."` | Indicates a missing dependency; check installation |

If the runner returns `LANE_X12_STATUS_BLOCKED`, no WINDOW_1H rows are written and no
source calls were made. The operator can fix the `blocked_reasons`, update the token list or
backup path, and re-run without any DB cleanup needed.

---

## 14. Failure / Stop Conditions

These are conditions under which the runner returns `LANE_X12_STATUS_STOPPED` mid-run. Unlike
BLOCKED (pre-flight), STOPPED means the runner started and encountered a problem during execution.

| Stop condition | Trigger | DB state after stop |
|----------------|---------|---------------------|
| Source budget exceeded | `total_source_failures > source_budget_max_consecutive_failures` | Jobs marked FAILED; window may be incomplete; run E2U before retry |
| Duration limit | `elapsed_now >= max_duration_seconds` | Jobs completed or failed; any open window is NOT closed |
| Cycle budget (test-only) | `total_window_closes >= _cycle_budget` | Clean stop; used only in tests |

### After a STOPPED result

1. Run `printer-report-e2u-15m-cycle-closeout` to confirm `active_locks = 0`.
2. If `active_locks > 0`: check for stale RUNNING jobs; update them to FAILED status
   (same X10.8 maintenance pattern — set `status = 'FAILED'`, null `lock_owner` and `locked_at`
   WHERE `status = 'RUNNING'` and `job_kind = 'TRACK_FAST_1H'`).
3. Inspect `printer_memory_windows` for any partial WINDOW_1H records with
   `window_status != "WINDOW_CLOSED"` — these should not exist (the runner only closes windows
   after they have sufficient evidence) but must be audited if they do.
4. Decide whether to re-run on the same proof copy or start fresh from a new copy.

### Handler BLOCKED (mid-run)

If a single cadence step is blocked by Gate 2 (running jobs) or Gate 3 (active locks), the
handler returns `E2H_FAST_1H_STATUS_BLOCKED` and the step counts as a source failure. The
runner increments `total_source_failures` and continues to the next cadence cycle unless the
budget is exceeded. A single handler BLOCKED event does not stop the proof run.

---

## 15. Lock Verification Checklist

The operator must verify all locks before and after the proof run.

### Pre-run checklist

| Check | Command / Query | Expected value |
|-------|----------------|----------------|
| Active scheduler locks | `printer-report-e2u-15m-cycle-closeout` → `active_locks` | 0 |
| Paper decisions delta | SQL: `SELECT COUNT(*) FROM printer_paper_decisions` | Same as pre-proof baseline |
| Paper positions | SQL: `SELECT COUNT(*) FROM printer_paper_positions` | 0 |
| Trade events | SQL: `SELECT COUNT(*) FROM printer_paper_trade_events` | 0 |
| PnL records | SQL: `SELECT COUNT(*) FROM printer_pnl_records` (if table exists) | 0 |
| Retrieval candidates | SQL: `SELECT COUNT(*) FROM printer_retrieval_candidates` | 0 |
| Retrieval results | SQL: `SELECT COUNT(*) FROM printer_retrieval_results` | 0 |
| WINDOW_1H records | SQL: `SELECT COUNT(*) FROM printer_memory_windows WHERE window_kind = 'WINDOW_1H'` | 0 (on proof copy before run) |

### Post-run checklist

All of the following must show zero delta from the pre-run values:

| Lock field | Expected delta | If delta > 0 |
|------------|---------------|--------------|
| `paper_decisions_created` | 0 | CRITICAL: X12 violated financial lock |
| `positions_created` | 0 | CRITICAL: X12 violated financial lock |
| `trade_events_created` | 0 | CRITICAL: X12 violated financial lock |
| `pnl_created` | 0 | CRITICAL: X12 violated financial lock |
| `retrieval_rows_created` | 0 | CRITICAL: X12 violated retrieval lock |
| `paper_trade_audits_created` | 0 | CRITICAL: X12 violated audit lock |

These values are also reported in the runner's JSON output under the corresponding fields.
The runner's own `hard_locks` dict must contain all lock keys set to `true`. Confirm:

```json
"hard_locks": {
  "no_buy_sell_hold": true,
  "no_paper_decisions": true,
  "no_positions": true,
  "no_pnl": true,
  "no_retrieval_activation": true,
  "no_live_trading": true,
  "no_paid_api": true,
  "no_wallet_private_key": true,
  "no_scoring_ranking_confidence": true,
  "no_4h_12h_24h_collection": true,
  "no_window_15m_in_1h_runner": true,
  "no_5m_main_window": true,
  "no_fake_1h_from_15m": true,
  "no_lane_mixing_fast_normal": true,
  ...
}
```

If any lock shows `false` or is missing from the output, the run must be considered invalid
and the code must be audited before any further runs.

---

## 16. Dirty-Memory Expectations

The first proof will likely produce `PARTIAL_MEMORY` rather than `CLEAN_MEMORY` for the
WINDOW_1H record. This is correct and expected.

### Why PARTIAL_MEMORY is likely on the first proof

- The WINDOW_1H close module writes `memory_status = "PARTIAL_MEMORY"` at close time
  (`E2O_1H_MEMORY_STATUS = "PARTIAL_MEMORY"` in `lane_e2o_1h_window_close.py`).
- Promotion to `CLEAN_MEMORY` requires Lane Q to pass the coverage audit AND Lane K/E2Z
  to run the promotion pipeline. For a first proof with 1 token, E2Z may require more than
  one valid WINDOW_1H window before promoting a clean episode.
- A `PARTIAL_MEMORY` result with valid `window_start_at`, `window_end_at`, `snapshot_start_id`,
  and `snapshot_end_id` is the correct expected outcome of a first proof.

### Expected dirty rate

From X11 Section 22, R5:
> A significant fraction of memecoins die within 60 minutes. The DIRTY_MEMORY rate for
> WINDOW_1H is expected to be higher than for WINDOW_15M, especially for TRACK_FAST tokens.
> The operator should expect a clean yield rate below 50% for the first X12 proof run.

For a 1-token first proof, `dirty_memory_count = 1` (due to Lane Q blocking short coverage)
is acceptable — it proves the dirty path works. `dirty_memory_count = 0` with a valid
PARTIAL_MEMORY window is the ideal outcome.

### Lane Q blocking a first proof

If the token produces fewer than 8 TRACK_FAST snapshots in the 45-minute window (e.g., due to
source failures or the run being cut short), Lane Q will report `CADENCE_POLICY_BLOCKED` and the
window will be marked `DIRTY_MEMORY`. The correct response is to:

1. Review `total_source_failures` and `cadence_cycles_completed` in the output.
2. If `cadence_cycles_completed < 8`: the run was stopped early. Check the stop reason.
3. If `cadence_cycles_completed >= 8` but `window_closes = 0`: the window never elapsed —
   check `window_close_interval_seconds` was set to 2700.0 (not 0.0).

---

## 17. Pair Drift Handling

Pair drift means the token's pair address changed during the 45-minute window. This is more
likely over 1h than over 15m (X11 Section 17).

### How the X12 runner handles pair drift

The runner passes `expected_pair_id` to `close_1h_memory_window_from_snapshot`. If the closing
snapshot's `pair_id` does not match the expected pair_id, the close function returns
`pair_drift_detected = True` and status `E2O_1H_WINDOW_BLOCKED`. The runner then:
- Increments `dirty_or_blocked_memory_count`.
- Increments `tok["pair_address_drift_count"]`.
- Records the drift event in `tok["pair_drift_events"]`.
- Resets the token's window state (`window_start_snapshot_id = None`, `window_open_mono = None`).
- Does NOT write a WINDOW_1H row to `printer_memory_windows`.

### What the operator should do if pair drift is detected

1. Confirm the new pair address from the proof run output (`pair_drift_events` list).
2. Update the token list with the new pair address.
3. Decide whether to:
   a. Re-run the proof with the corrected pair address (recommended if drift was detected early).
   b. Exclude this token from future 1h proofs until pair stability is confirmed.
4. Do NOT attempt to close a WINDOW_1H that spans two pair addresses. The close is correctly
   blocked by the runner.

### Pair drift in the first proof

For the first proof, ANSEM (token id=13) must be excluded (X11 R8: unresolved pair ambiguity).
Select a token whose pair address has been stable in recent X5 or X10.10B runs. Tokens with a
single entry in `printer_pairs` and no PAIR_DRIFT_DETECTED events in `printer_memory_windows`
are preferred.

---

## 18. Source Governor and Central Scheduler Checks

### Source Governor

Every source call in a proof run must go through `can_request_source()`. The runner itself
does not call the Source Governor directly — this is delegated to the handler via Gate 4:

```
Gate 4: Source Governor budget allows the request
  → check_source_governor(connection, source_name, request_kind)
  → can_request_source("dexscreener", "pair_market_snapshot", recent_count)
  → If denied: blocked_gates += ["source_governor_denied: ..."]
```

If Gate 4 blocks, the handler returns `E2H_FAST_1H_STATUS_BLOCKED`. The runner counts this
as a source failure and continues to the next cycle. The Source Governor cannot be bypassed.

**Pre-run source governor check:** Before starting the proof, the operator should verify that
the DexScreener source budget allows at least 12-13 requests (1-token TRACK_FAST proof = ~12
source calls). Run `printer-report-e2u-15m-cycle-closeout` and check the `source_requests`
section for recent DexScreener request counts. If the budget is already near the hourly limit,
wait before starting the proof.

### Central Scheduler

The runner creates one scheduler job per cadence cycle per token. For a 1-token TRACK_FAST
proof with 12 cadence cycles, approximately 12 `TRACK_FAST_1H` jobs will be created in
`printer_scheduler_jobs`. Each job is:
1. Created with status `PENDING`.
2. Claimed to status `RUNNING` (the runner owns the lock).
3. Completed (`SUCCEEDED`) or failed (`FAILED`) before the next cycle begins.

At no point during a healthy run should more than 1 RUNNING `TRACK_FAST_1H` job exist.

**Gate 2 (running jobs check) and Gate 3 (active locks check)** in the handler guard against
this. If another process has created a conflicting scheduler job, the handler blocks until clear.

For the first proof, confirm zero scheduler jobs with `status = 'RUNNING'` exist in the proof
copy DB before starting:

```sql
SELECT COUNT(*) FROM printer_scheduler_jobs WHERE status = 'RUNNING';
```
Expected: 0.

---

## 19. Post-Run Reports to Collect

After the proof run completes, collect and archive the following:

### Required reports

**1. Runner JSON output** (printed to stdout during run)
```
printer-run-lane-x12-fast-1h-cycle [all flags] --format json > x14_proof_run_output.json
```
Archive `x14_proof_run_output.json`. This is the primary proof artifact.

**2. E2U closeout report** (confirms locks and active state after run)
```
printer-report-e2u-15m-cycle-closeout
```
Verify: `active_locks = 0`, `paper_decisions_delta = 0`, `positions_delta = 0`.

**3. DB query: WINDOW_1H records created**
```sql
SELECT id, token_id, pair_id, window_kind, window_status, memory_status,
       snapshot_start_id, snapshot_end_id, window_start_at, window_end_at,
       created_by_phase, created_at
FROM printer_memory_windows
WHERE window_kind = 'WINDOW_1H'
ORDER BY created_at DESC;
```
Save output as `x14_proof_window_1h_records.txt`.

**4. DB query: TRACK_FAST_1H scheduler jobs**
```sql
SELECT id, job_name, job_kind, status, started_at, finished_at, last_error
FROM printer_scheduler_jobs
WHERE job_kind = 'TRACK_FAST_1H'
ORDER BY created_at DESC;
```
Save output as `x14_proof_scheduler_jobs.txt`.

**5. DB query: Source request counts**
```sql
SELECT source_name, COUNT(*) as request_count,
       MIN(requested_at) as first_request,
       MAX(requested_at) as last_request
FROM printer_source_requests
WHERE requested_at > [proof_run_start_time]
GROUP BY source_name;
```
Save output as `x14_proof_source_requests.txt`.

**6. Lock delta confirmation** (all should be zero)
```sql
SELECT
  (SELECT COUNT(*) FROM printer_paper_decisions)     AS paper_decisions,
  (SELECT COUNT(*) FROM printer_paper_positions)     AS paper_positions,
  (SELECT COUNT(*) FROM printer_paper_trade_events)  AS trade_events;
```

### Optional reports

- Lane Q audit details for the WINDOW_1H record:
  Query `printer_memory_window_audits` WHERE `window_id = [new_window_id]`.
- Lane K/E2Z result: Query `printer_episodes` for new rows created after proof start time.

---

## 20. Commit Policy After Proof

### If the proof PASSES (minimum success criteria from Section 12 met)

1. **Do not commit the proof DB copy.** Proof DB copies are operator artifacts, not repo
   artifacts. They live in `data/proof_runs/` and `data/backups/`, which are gitignored.

2. **Commit the X14 proof runbook** (the summary document produced by the operator after
   completing the X14 run — separate from this X13 design document).

3. **Do not merge the proof DB into the live DB** until the operator reviews:
   - All WINDOW_1H records for valid `window_start_at` / `window_end_at`.
   - All Lane Q audit results for the new windows.
   - Lock delta confirmation (all financial locks at zero delta).
   - At least one WINDOW_1H record with `memory_status = PARTIAL_MEMORY` and valid integrity fields.

4. **Tag after operator approval:**
   `printer-v1-lane-x14-1h-fast-proof-run` (or equivalent).

5. **Only after tagging:** merge proof DB rows into live DB or discard the proof copy and
   re-run the proof against the live DB with operator approval.

### If the proof returns LANE_X12_BLOCKED or LANE_X12_STOPPED

- No DB rows were created (BLOCKED) or the run ended early (STOPPED).
- No commit is needed.
- Fix the blocking condition, update the token list or backup paths, and re-run.
- Archive the failed run output for debugging records.

### If dirty-memory is produced but no clean window

- This is an acceptable first-proof outcome.
- Commit the X14 runbook documenting the dirty outcome.
- Investigate the Lane Q blocking reason (insufficient snapshots? too-wide gap? pair drift?).
- Decide whether to re-run with a different token or accept the dirty outcome as proof that
  the dirty path functions correctly.
- Do not retroactively change coverage thresholds to force a clean outcome on a dirty run.

---

## 21. What X14 Should Do

Lane X14 is the operator execution of the first real WINDOW_1H proof. It should:

1. **Read this X13 runbook** in full before executing any CLI command.
2. **Select 1 TRACK_FAST token** meeting all requirements from Section 6.
3. **Create the DB backup and proof copy** following Section 7.
4. **Write the token list** following Section 8.
5. **Run the exact CLI command** from Section 10 against the proof copy.
6. **Wait the full ~40-45 minutes** for the proof run to complete.
7. **Collect all post-run reports** from Section 19.
8. **Verify all lock fields** against the checklist in Section 15.
9. **Verify the WINDOW_1H DB record** using the query in Section 12.
10. **Document the result** as an X14 proof summary runbook entry.
11. **Decide whether to commit** following Section 20.
12. **Escalate to 2-3 token proof or TRACK_NORMAL proof** only after the 1-token proof is
    confirmed and reviewed — and only after operator explicitly approves the escalation.

---

## 22. What X14 Must Not Do

Lane X14 must NOT:

- Run the CLI against the **live** `data/printer_v1.sqlite3` directly. Use a proof copy.
- Run the X12 NORMAL CLI (`printer-run-lane-x12-normal-1h-cycle`) in the first proof.
  The first proof is TRACK_FAST only.
- Use `--snapshot-interval-seconds 0` or `--window-close-interval-seconds 0` for a real proof.
  Those are test-only settings.
- Skip the pre-run lock verification checklist.
- Include ANSEM (token id=13) until pair drift is resolved.
- Include more than 1 token in the first proof.
- Run a 4h, 6h, or longer `--duration-profile` for the first proof.
- Use `--allow-long-bounded-run` in the first proof.
- Attempt to combine TRACK_FAST and TRACK_NORMAL tokens in a single CLI invocation. The
  `printer-run-lane-x12-fast-1h-cycle` CLI rejects TRACK_NORMAL tokens by design.
- Unlock retrieval, paper decisions, BUY, SELL, HOLD, positions, trade events, PnL, or any
  financial capability as a result of the proof.
- Run X10.10C (TRACK_NORMAL live 15m proof) as part of X14. X10.10C is a separate track.
- Enable 4h, 12h, or 24h windows. They remain disabled until 1h is proven.
- Merge proof DB rows into the live DB without operator review of all post-run reports.
- Commit code changes. X14 is an operator execution lane, not a code lane.
- Exceed the `source_budget_max_consecutive_failures` limit by disabling the budget guard.
- Fabricate or adjust WINDOW_1H timestamps to force a clean outcome from a dirty run.
- Run any BUY/SELL/HOLD logic. The runner enforces this; the operator must confirm after.
- Start a second proof run before reviewing the first proof's output completely.

---

## 23. Final Verdicts

```
X13_DOC_ONLY_COMPLETE:                                          YES
  Reason: All 23 sections completed. No code was modified in this session.
  No runtime was invoked. No source calls were made. No DB was written. No
  CLI commands were executed. All financial and retrieval locks remain
  unchanged. The operator proof runbook for the first real WINDOW_1H
  collection (to be executed in X14) is fully specified.

X14_TINY_1H_PROOF_DESIGN_READY:                                 YES
  Reason: The exact CLI command template, token-list shape, DB backup plan,
  runtime duration settings, cadence parameters, expected output fields,
  minimum success criteria, acceptable blocked outcomes, stop conditions,
  lock verification checklist, dirty-memory expectations, pair drift handling,
  Source Governor checks, post-run report list, commit policy, and X14 do /
  do-not lists are all specified in this document. X14 can proceed after
  operator review and approval of this X13 runbook.

  Recommended first proof shape:
    CLI:              printer-run-lane-x12-fast-1h-cycle
    Mode:             TRACK_FAST
    Token count:      1
    Duration:         --duration-profile 1h (3600s total)
    Snapshot cadence: --snapshot-interval-seconds 240.0 (4 min, TRACK_FAST 1h)
    Window close:     --window-close-interval-seconds 2700.0 (45-min window)
    Throttle:         --throttle-backoff-seconds 2.0
    Budget:           --source-budget-max-consecutive-failures 5
    DB:               Proof copy of data/printer_v1.sqlite3 (not live)
    Backup:           Pre-existing timestamped backup (must exist before run)

REAL_1H_RUNTIME_STILL_NOT_STARTED:                              CONFIRMED
  Reason: No CLI command was run in X13. No WINDOW_1H records exist in any
  DB as a result of X13. The first real WINDOW_1H collection has not started.
  It remains pending operator approval and execution in X14. This document
  cannot and does not start a live proof.

MIXED_1H_RUNTIME_NOT_APPROVED:                                  CONFIRMED
  Reason: A mixed TRACK_FAST + TRACK_NORMAL 1h proof in a single runner
  session is not supported by the lane_x12_1h_runner.py architecture and is
  not approved in X14. TRACK_FAST and TRACK_NORMAL use separate CLI commands
  by design. Mixed proofs belong to a later lane after both single-mode proofs
  are independently confirmed. X14 must use TRACK_FAST only (1 token) for the
  first proof.

WINDOW_15M_REMAINS_PRIMARY_ACTIVE_MEMORY:                       CONFIRMED
  Reason: WINDOW_15M is the only window kind with real collected records in
  the current DB (18+ clean episodes, growing). WINDOW_1H has zero records.
  After X14, WINDOW_1H will have 0-1 records. WINDOW_15M remains the primary
  active memory window through X14 and beyond. The 1h continuation window
  supplements 15m; it does not replace it. Memory retrieval, when activated,
  must query by window_kind and must not treat 1h windows as substitutes for
  15m windows for fast-decision use cases.

WINDOW_5M_REMAINS_SUPPORT_ONLY:                                 CONFIRMED
  Reason: WINDOW_5M_MICRO_EVENT cannot satisfy any WINDOW_1H evidence
  requirement, cannot count toward WINDOW_1H snapshot totals, cannot trigger
  a WINDOW_1H close, and cannot unlock retrieval, paper decisions, BUY,
  positions, or PnL. This rule is unchanged from all prior lanes and applies
  without exception to X14 and all future 1h lanes.

4H_12H_24H_REMAIN_DISABLED:                                     CONFIRMED
  Reason: 4h, 12h, and 24h collection remain disabled through X13, X14, and
  beyond. They may only be activated after WINDOW_1H memory is proven clean
  and stable over multiple proof runs, and only after an explicit
  operator-approved activation lane beyond X14. The cadence policy entries for
  4h/12h/24h have enabled_for_real_collection=False and must not be changed
  without a dedicated approval lane.

ALL_FINANCIAL_AND_RETRIEVAL_LOCKS_PRESERVED:                    CONFIRMED
  Reason: This document introduces no code changes. No financial lock is
  relaxed. No retrieval is activated. No BUY/SELL/HOLD capability is added.
  No paper decisions are unlocked. No paper positions, trade events, paper
  trade audits, or PnL are created. Live trading, wallet, private key, and
  paid API locks are all confirmed active. Scoring, ranking, confidence, and
  weighted logic remain locked. The lane_x12_1h_runner.py hard_locks dict
  confirms all locks at the runner level; the X12 handlers confirm them at
  the execution level; the E2O_1H window close confirms them at the
  window-write level.
```

---

## End-of-Lane Summary

**Files changed:** `docs/printer-v1-lane-x13-1h-operator-proof-readiness.md` (created).

**Code touched:** No. Zero source files modified.

**Runtime touched:** No. No CLI command executed. No proof run started.

**Source fetching touched:** No. No DexScreener or other source calls made.

**DB touched:** No. No DB reads or writes performed.

**Recommended X14 proof shape:**
TRACK_FAST, 1 token, `--duration-profile 1h`, `--snapshot-interval-seconds 240.0`,
`--window-close-interval-seconds 2700.0`. Against a proof copy of the live DB.
Backup required before running.

**Pass/fail:** PASS — all 23 sections complete, all 8 required final verdicts present.

**Can X14 proceed after operator approval:** YES. This runbook provides all information
needed to execute the first real WINDOW_1H proof. The operator must review Sections 6-10
for the exact proof shape, token selection criteria, and CLI command, then explicitly approve
and execute. No further design work is needed before X14.
