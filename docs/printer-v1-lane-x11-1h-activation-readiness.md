# Printer V1 — Lane X11: 1h Activation Readiness Review

**Type:** Documentation and design review only. No code changes. No runtime.
No source fetching. No DB writes. No real WINDOW_1H collection.
No fake 1h assembled from 15m data. No mixed-lane runtime proof.

**Date:** 2026-07-07

**Prerequisite anchor commits:**
- `d0d337e` — X10.10A: Mixed-Lane 15m Memory Growth Audit
  Tag: `printer-v1-lane-x10-10a-mixed-lane-memory-growth-audit`
- `0627d61` — X10.10B: TRACK_NORMAL 15m Runner
  Tag: `printer-v1-lane-x10-10b-track-normal-15m-runner`

---

## Todo / Checklist

- [x] Read AGENTS.md
- [x] Read docs/printer-v1-clean-master-spec.md
- [x] Read docs/printer-v1-post-rc-build-order.md
- [x] Read docs/printer-v1-memory-factory-guide.md
- [x] Read docs/printer-v1-proposed-memory-growth-build-order.md
- [x] Read docs/printer-v1-lane-x10-memory-growth-yield-report.md
- [x] Read docs/printer-v1-lane-x10-6-discovery-selection-traceability-repair.md
- [x] Read docs/printer-v1-lane-x10-7-manual-discovery-15m-proof-report.md
- [x] Read docs/printer-v1-lane-x10-8-manual-discovery-15m-proof-report.md
- [x] Read docs/printer-v1-lane-x10-9a-pre-snapshot-freshness-audit.md
- [x] Read docs/printer-v1-lane-x10-10a-mixed-lane-15m-memory-growth-audit.md
- [x] Inspect `src/printer_v1/snapshots/frequency.py` — cadences beyond first 15m
- [x] Inspect `src/printer_v1/scheduler/contracts.py` — job kinds inventory
- [x] Inspect `src/printer_v1/operator_cli/e2o_memory_window_close.py` — E2O_WINDOW_KIND constant
- [x] Write docs/printer-v1-lane-x11-1h-activation-readiness.md

---

## 1. Purpose

Lane X11 is a documentation-only readiness review for WINDOW_1H memory collection.

Its purpose is to define what WINDOW_1H should look like, what must be built before any real 1h
collection run is allowed, and what conditions must hold before a Lane X12 proof can proceed.

Lane X11 does NOT:

- authorize any real WINDOW_1H collection
- authorize any code change in this session
- authorize source fetching for 1h evidence
- authorize fake 1h data assembled from 15m snapshots
- unlock retrieval, paper decisions, BUY, SELL, HOLD, positions, PnL, or live trading
- supersede any authority in the source-of-truth stack

Lane X11 DOES:

- document the current state of all infrastructure relevant to WINDOW_1H
- document what 15m has proven and what it has not proven
- design the proposed WINDOW_1H evidence identity
- design the proposed snapshot cadences and coverage thresholds for 1h
- define stop conditions, dirty-memory gates, and replay/idempotency rules for a future X12 proof
- identify all gaps between current infrastructure and a real 1h runner
- preserve all V1 financial and retrieval locks

The authority for this document's design decisions remains the source-of-truth stack:

1. `AGENTS.md`
2. `docs/printer-v1-clean-master-spec.md`
3. `docs/printer-v1-post-rc-build-order.md`
4. `docs/printer-v1-memory-factory-guide.md`

---

## 2. Source-of-Truth Constraints

All of the following rules apply without exception in Lane X11 and all future X12+ lanes:

### From AGENTS.md (V1 Locked Rules)

- Solana-only. Solana memecoin-only. Paper-trading only.
- No live wallet. No private keys. No real funds. No live execution.
- No paid API dependency.
- No scoring system. No ranking system. No confidence percentage system. No weighted decision
  logic.
- No engine bypassing Source Governor. No engine bypassing Central Scheduler.
- No paper decision without clean memory comparison.
- No paper position without valid clean-memory-backed paper decision.
- No dirty memory training decisions.
- No broad context engine acting as a direct trade signal.
- No vectors/embeddings unless explicitly approved later.

### From `docs/printer-v1-clean-master-spec.md` (System Charter)

- WINDOW_5M_MICRO_EVENT is support-only. It must not become a main outcome window.
- All data quality labels: CLEAN_DATA, ACCEPTABLE_PARTIAL_DATA, DIRTY_DATA, STALE_DATA,
  MISSING_CRITICAL_DATA, CONFLICTING_DATA, DO_NOT_TRAIN.
- Only CLEAN_DATA and acceptable partial data can become clean memory.
- Any critical gap blocks training use.
- Memory windows must be tied to a specific evidence identity (snapshot_start_id, snapshot_end_id,
  window_start_at, window_end_at).
- WINDOW_1H role: "Short-term continuation/failure memory."
- 1h should start after 15m factory behavior is stable.
- 4h should start after 1h memory is clean and scheduler/source capacity is stable.

### From `docs/printer-v1-post-rc-build-order.md` (Post-RC Lane 6)

- Post-RC Lane 6 (Longer Window Activation Readiness) allows: fixture tests, schema readiness,
  generic window_kind code paths.
- Post-RC Lane 6 does NOT allow: real 1h/4h/12h/24h collection, fake long-window data from 15m
  snapshots, runtime expansion.
- Exit gate: longer windows are structurally supported; real operation remains 15m-only until
  approved.

### From `docs/printer-v1-memory-factory-guide.md` (Window Policy)

- Memory Factory should activate windows in this order: (1) 15m main + 5m support, (2) 1h
  continuation/failure, (3) 4h medium-term, (4) 12h/24h.
- `open 1h only if token remains useful/eligible after 15m`
- `TRACK_FAST: continue to 1h if token survives and data remains useful`
- `TRACK_NORMAL: open 1h only if token remains useful/eligible after 15m`

### From `docs/printer-v1-lane-x10-memory-growth-yield-report.md` (R5: 1h Constraint)

> Only WINDOW_15M is active for real collection. Longer windows are disabled per roadmap.
> Lane X11 (1h Activation Readiness) must be a documentation/design-only lane before any real
> 1h collection runs.

---

## 3. Current State After X10 / X10.10B

### 3.1 X10.10B Pre-X11 Correction (Completed)

Lane X10.10A identified that TRACK_NORMAL tokens received zero 15m memory windows under the
TRACK_FAST-only X5 runner. This was a winner-bias gap: all 15m memory came from fast-event tokens;
slow fades, failed tokens, liquidity decay, and boring baselines produced no memory.

Lane X10.10B was built and committed to close that gap:

| Component | Status |
|-----------|--------|
| `lane_e2h_normal_first_15m_handler.py` | CREATED — TRACK_NORMAL handler, parallel to E2H |
| `lane_x10_10_normal_15m_runner.py` | CREATED — 1-7 token bounded TRACK_NORMAL runner |
| CLI `printer-run-lane-x10-10-normal-15m-cycle` | REGISTERED in commands.py + pyproject.toml |
| `tests/test_post_lane10_lane_x10_10_normal_15m_runner.py` | CREATED — 72 tests, all passing |
| X5 regression (174 tests) | PASS — X5 TRACK_FAST validation untouched |
| X10.9 regression (38 tests) | PASS |
| X10.6 regression (105 tests) | PASS |
| X6 regression (150 tests) | PASS |

X10.10B was committed at `0627d61` (tag: `printer-v1-lane-x10-10b-track-normal-15m-runner`).

X10.10B is NOT an active runtime lane as of X11. It corrects the anti-bias gap in the 15m memory
pipeline. It has not yet run against the live DB. It is ready for its first operator-approved run
when the operator chooses to execute it. This readiness review does not mandate or trigger that run.

### 3.2 Memory Window State (DB — as of Lane X10 yield report)

| Window Kind | Memory Status | Count |
|-------------|---------------|-------|
| WINDOW_15M | CLEAN_MEMORY (promoted to episodes) | 18 clean episodes |
| WINDOW_15M | PARTIAL_MEMORY | 19 |
| WINDOW_15M | DIRTY_MEMORY | 97 |
| WINDOW_15M | AUDIT_ONLY | 14 |
| WINDOW_5M_MICRO_EVENT | AUDIT_ONLY | 2 |
| **WINDOW_1H** | **Any** | **0** |
| **WINDOW_4H, 12H, 24H** | **Any** | **0** |

Zero WINDOW_1H records exist. This is expected and correct.

### 3.3 Locked-State Snapshot (as of X10.10B)

| Lock | Status |
|------|--------|
| retrieval_activated | OFF |
| paper_decisions | 2 rows (pre-existing Phase 32 work; delta=0 in all X10 runs) |
| paper_positions | 0 (all time) |
| trade_events | 0 (all time) |
| pnl_created | 0 (all time) |
| BUY enabled | No |
| SELL / HOLD enabled | No |
| live_trading | No |
| wallet / private_key | No |
| paid_api_dependency | No |
| scoring / ranking / confidence | No |
| embeddings / vectors | No |
| 1h collection (real) | Disabled |
| 4h / 12h / 24h collection | Disabled |
| WINDOW_5M_MICRO_EVENT as main | No |

---

## 4. Why Lane X11 Is Documentation-Only

Real WINDOW_1H collection cannot proceed until all of the following are satisfied, and none are
satisfied today:

### 4.1 Missing Scheduler Job Kinds (BLOCKER)

Current `scheduler/contracts.py` defines these job kinds relevant to memory:

```
TRACK_FAST_FIRST_15M       — exists, proven, active
TRACK_NORMAL_FIRST_15M     — exists, implemented in X10.10B, ready for first run
MEMORY_WINDOW_CLOSE        — exists (generic)
```

Missing for any real 1h collection:

```
TRACK_FAST_1H              — does not exist
TRACK_NORMAL_1H            — does not exist
```

No scheduler job kind exists to represent "collect a 1h-phase snapshot for a TRACK_FAST or
TRACK_NORMAL token." Adding these job kinds requires a code change (contracts.py) and must be
done in a future approved implementation lane (X12 or its sub-lanes), not here.

### 4.2 Missing E2O Support for WINDOW_1H (BLOCKER)

`e2o_memory_window_close.py` contains the hardcoded constant:

```python
E2O_WINDOW_KIND: str = "WINDOW_15M"   # line 48
```

The module docstring states: "WINDOW_15M only. 5m is not a valid main window."

E2O as currently implemented cannot close a WINDOW_1H memory window. A new variant
(e.g., `lane_e2h_1h_window_close.py` or a parameterized E2O) must be built in X12.
This is a required code change — cannot be done in X11.

### 4.3 Missing 1h Handler and Runner (BLOCKER)

| Required component | Status |
|-------------------|--------|
| 1h job handler (equivalent of E2H for 1h job kind) | Does not exist |
| 1h bounded runner (equivalent of X5/X10.10B for 1h collection) | Does not exist |
| CLI command for 1h runner | Does not exist |

These are new modules, not extensions of existing ones. Building them in X12 means:
- A new `lane_e2h_fast_1h_handler.py` and `lane_e2h_normal_1h_handler.py`
- A new `lane_x12_1h_runner.py` (or separate TRACK_FAST and TRACK_NORMAL runners)
- CLI registration in commands.py and pyproject.toml

### 4.4 Missing Lane Q Coverage Policy for WINDOW_1H (BLOCKER)

`snapshots/cadence_policy.py` defines `SnapshotCadencePolicy` for `TRACK_NORMAL + WINDOW_15M` and
`TRACK_FAST + WINDOW_15M`. No policy exists for any lane + WINDOW_1H combination.

Without a defined coverage policy, the Lane Q integrity guard cannot assess whether a 1h window's
snapshot count is sufficient, and the E2Z promotion pipeline cannot make a clean/dirty decision.

### 4.5 E2Z Promotion Path Not Tested for WINDOW_1H

Lane K / E2Z was tested and proven for WINDOW_15M only. The 18 CLEAN_MEMORY episodes are all
WINDOW_15M_CLEAN_MEMORY. E2Z has not been tested with WINDOW_1H windows and may require
extension to handle the `window_kind` field correctly.

### 4.6 No Proof That 15m → 1h Transition Works End-to-End

The complete token lifecycle transition — from `TRACK_FAST_FIRST_15M` job closure to a new
`TRACK_FAST_1H` job creation at token_age > 15m — has never been exercised. The same applies
for TRACK_NORMAL. No data in the live DB confirms this transition works correctly.

### 4.7 TRACK_NORMAL 15m Run Not Yet Executed Against Live DB

X10.10B (TRACK_NORMAL 15m runner) has been built and test-verified, but has not yet run against
the live `data/printer_v1.sqlite3`. Its first real run is a prerequisite milestone before
expanding to 1h. The system should prove TRACK_NORMAL 15m before moving to TRACK_NORMAL 1h.

**Summary verdict: Real WINDOW_1H collection requires at minimum 7 new/modified components.
None of the required code changes are authorized in Lane X11. They are authorized only in a
future explicitly approved Lane X12.**

---

## 5. What 15m Stability Has Already Proven

The following has been proven through X5 (X10.7 / X10.8) and is confirmed stable:

| Proven capability | Evidence |
|-------------------|----------|
| Bounded TRACK_FAST 15m runner | X5 five-token runner, 174 tests |
| Bounded TRACK_NORMAL 15m runner (built, not yet live) | X10.10B, 72 tests |
| WINDOW_15M open and close (E2O) for TRACK_FAST | X10.7 / X10.8 live DB runs |
| WINDOW_15M open and close (E2O) for TRACK_NORMAL | X10.10B integration tests |
| Lane Q coverage/gap audit for WINDOW_15M | Confirmed for both lanes |
| Cadence policy enforcement (CADENCE_POLICY_PASS / BLOCKED) | 18 clean, 33 blocked |
| Lane K / E2Z clean memory promotion for WINDOW_15M | 18 CLEAN_MEMORY episodes |
| E2Z idempotency (same window not promoted twice) | Confirmed in Lane U2 tests |
| Source Governor enforcement (no bypass) | Confirmed across all X5/X10.10B tests |
| Central Scheduler job-claim pattern | Confirmed for TRACK_FAST and TRACK_NORMAL |
| Source budget: consecutive failure safe stop | Confirmed in X5 and X10.10B tests |
| Pair drift detection and reporting | Confirmed in X5 (ANSEM pair drift) |
| Stale scheduler lock recovery | Confirmed in X10.8 (job 888 maintenance) |
| Discovery → X6 → X10.6 → X5 end-to-end | Proved in X10.7 / X10.8 |
| WINDOW_5M_MICRO_EVENT support-only isolation | No promotions, no BUY unlock |
| All financial and retrieval locks at zero delta | Every run confirmed |

---

## 6. What 15m Has Not Proven Yet

The following capabilities are NOT proven and must be established before or during a future Lane X12:

| Unproven capability | Why it matters for 1h |
|---------------------|----------------------|
| WINDOW_1H open and close (E2O variant) | E2O is hardcoded WINDOW_15M; 1h needs new code |
| TRACK_FAST_1H job kind and handler | No such job kind exists in contracts.py |
| TRACK_NORMAL_1H job kind and handler | Same gap |
| 15m → 1h token lifecycle transition | No real DB evidence of token moving from first-15m phase to 1h continuation phase |
| Lane Q coverage policy for WINDOW_1H | No cadence policy for any lane + WINDOW_1H combination |
| E2Z promotion for WINDOW_1H | E2Z tested only with WINDOW_15M episodes |
| Long-window cadence enforcement | frequency.py defines cadences for age > 15m but they are unused by any runner |
| Pair drift implications over 60 minutes | Pair drift more likely over 1h; no 1h multi-window drift test data |
| Source budget over a 60-minute bounded run | X5 and X10.10B prove 15m and 1h-duration (with 15m windows); no 1h-window run |
| TRACK_NORMAL 15m memory in live DB | X10.10B built but not yet run against live data/printer_v1.sqlite3 |
| Multi-lane concurrent source budget math | No proof of TRACK_FAST + TRACK_NORMAL concurrent 1h runs |

---

## 7. Proposed WINDOW_1H Evidence Identity

A WINDOW_1H memory window must be uniquely identified by the following fields in
`printer_memory_windows`:

| Field | Value | Notes |
|-------|-------|-------|
| `token_id` | Integer | References `printer_tokens.id` |
| `pair_id` | Integer | References `printer_pairs.id` (same pair throughout the window) |
| `window_kind` | `"WINDOW_1H"` | Distinct from `"WINDOW_15M"` |
| `snapshot_start_id` | Integer | ID of the first snapshot taken after the 15m window closed (or the first snapshot of the 1h collection, if running 1h independently) |
| `snapshot_end_id` | Integer | ID of the last snapshot taken before or at the 1h mark |
| `window_start_at` | UTC timestamp | When the 1h collection phase began (nominally: when the 15m window closed) |
| `window_end_at` | UTC timestamp | When the 1h window was closed (~60 minutes after tracking start) |

**Evidence identity uniqueness rule:**
The combination of `(pair_id, window_kind, snapshot_start_id)` must be unique in
`printer_memory_windows`. Two WINDOW_1H records for the same token/pair in different time periods
are valid and expected — idempotency checks must use all three fields, not just
`(token_id, window_kind)`.

**No fake construction rule:**
A WINDOW_1H record must be built from real snapshots collected during the 1h window period.
It must NOT be assembled or inferred from WINDOW_15M data, from averaged 15m results, from
interpolated snapshots, or from any synthetic construction. Every snapshot referenced by
`snapshot_start_id` through `snapshot_end_id` must be a real DB row in `printer_token_snapshots`
with `source_status = COMPLETE` and `data_quality_label = CLEAN_DATA`.

**Sequential model (preferred):**
A token's 1h collection phase begins when its 15m window closes. The 15m close event triggers the
start of 1h evidence collection. This means:
- `snapshot_start_id` is the first new snapshot taken after the 15m window close
- `window_start_at` is the timestamp of the 15m window close
- `window_end_at` is approximately `window_start_at + 2700 seconds` (45 minutes later)
  yielding a total token age at 1h of ~60 minutes from initial tracking start

**Parallel model (not recommended for V1):**
A 1h window could be constructed from all snapshots from t=0 to t=60m, encompassing the 15m
window's evidence plus the continuation. This is architecturally more complex, requires the 1h
window to reference snapshots that are also referenced by the 15m window, and creates overlap
ambiguity in coverage audits. Do not use the parallel model in V1.

---

## 8. Proposed 1h Snapshot Cadence

From `src/printer_v1/snapshots/frequency.py` (`get_base_snapshot_interval_seconds`), the cadence
beyond the first 15 minutes is already defined:

```python
# TRACK_FAST
if age <= 15 * 60:   return 120   # 2 min — first 15m
if age <= 60 * 60:   return 240   # 4 min — 15m to 1h phase
return 480                          # 8 min — beyond 1h

# TRACK_NORMAL
if age <= 15 * 60:   return 420   # 7 min — first 15m
if age <= 60 * 60:   return 720   # 12 min — 15m to 1h phase
return 1200                         # 20 min — beyond 1h
```

These cadences are **defined but unused by any current runner**. A future 1h runner must activate
the `age <= 60 * 60` intervals for the continuation phase.

### Proposed snapshot count for WINDOW_1H (45-minute continuation)

The continuation phase spans from ~t=15m to ~t=60m (approximately 2700 seconds):

| Lane | Interval | Expected snapshots (2700s ÷ interval) |
|------|----------|--------------------------------------|
| TRACK_FAST (240s) | 240 seconds | ~11 snapshots |
| TRACK_NORMAL (720s) | 720 seconds | ~4 snapshots |

**Important:** These are snapshots in the continuation phase only (after the 15m window closes).
The 15m window's evidence is separate. For a full WINDOW_1H record that starts at t=15m, the
above numbers represent the expected evidence density.

### Proposed freshness policy for 1h-phase snapshots

Freshness requirements must be applied per snapshot during 1h collection, not only at the start
of the run:

| Evidence type | TRACK_FAST | TRACK_NORMAL |
|---------------|-----------|--------------|
| Snapshot age at next expected interval | Hard gate: must not exceed 2× the expected interval | Advisory: log warning if exceeding 2× interval |
| Single gap exceeding 3× expected interval | DIRTY_MEMORY (gap too large) | DIRTY_MEMORY (gap too large) |
| Source failure during 1h phase | Increment failure counter; stop at max consecutive failures | Same |

---

## 9. Proposed 1h Coverage / Gap Thresholds

These are proposed values for a future Lane Q coverage policy for WINDOW_1H. They must be encoded
in `snapshots/cadence_policy.py` during Lane X12 implementation.

### TRACK_FAST + WINDOW_1H

| Parameter | Proposed value | Rationale |
|-----------|---------------|-----------|
| Expected snapshot count (45-min phase) | 11 | 2700s ÷ 240s |
| Minimum snapshot count for CLEAN_DATA | 8 | ≥72% coverage |
| Maximum allowed gap between consecutive snapshots | 600 seconds | 2.5× the 240s interval |
| Gap flagging threshold | > 480 seconds | 2× the expected interval |

A TRACK_FAST 1h window with fewer than 8 snapshots in the continuation phase, or a single gap
exceeding 600 seconds, must be downgraded to `DIRTY_MEMORY` by the Lane Q coverage audit.
A window with 8-10 snapshots is `PARTIAL_MEMORY` and may be eligible for `CLEAN_MEMORY` promotion
after a coverage-weighted review (same rule as 15m PARTIAL_MEMORY).

### TRACK_NORMAL + WINDOW_1H

| Parameter | Proposed value | Rationale |
|-----------|---------------|-----------|
| Expected snapshot count (45-min phase) | 4 | 2700s ÷ 720s |
| Minimum snapshot count for CLEAN_DATA | 3 | ≥75% coverage |
| Maximum allowed gap between consecutive snapshots | 1800 seconds | 2.5× the 720s interval |
| Gap flagging threshold | > 1440 seconds | 2× the expected interval |

A TRACK_NORMAL 1h window with fewer than 3 snapshots in the continuation phase, or a single gap
exceeding 1800 seconds, must be downgraded to `DIRTY_MEMORY`.

### Note on "expected" vs "actual" counts

These thresholds are starting proposals for X12. The first X12 proof run results may require
adjustment. Thresholds must be set before implementation (not inferred post-hoc from a run).

---

## 10. Source Budget Expectations for 1h

### Source call rate during 1h (continuation phase only)

| Lane | Interval | Rate per token |
|------|----------|---------------|
| TRACK_FAST | 240s | 1 call per 4 min |
| TRACK_NORMAL | 720s | 1 call per 12 min |

### Combined worst-case rate (simultaneous 1h run: 5 TRACK_FAST + 7 TRACK_NORMAL)

| Lane | Tokens | Rate per token | Combined rate |
|------|--------|---------------|---------------|
| TRACK_FAST | 5 | 1/240s | 1 call per 48s |
| TRACK_NORMAL | 7 | 1/720s | 1 call per ~103s |
| Combined | 12 | — | ~1 call per 33s |

This is within the Source Governor's managed capacity. The governor's priority order
(`TRACK_FAST > TRACK_NORMAL`) means TRACK_FAST continuation calls are not starved.

### Comparison to 15m phase budget

During the first 15m phase:
- TRACK_FAST (5 tokens, 120s interval): 1 call per 24s combined
- TRACK_NORMAL (7 tokens, 420s interval): 1 call per 60s combined

The 1h continuation phase produces **fewer calls per unit time** than the first 15m phase for
TRACK_FAST (240s vs 120s). The total source budget pressure over a 1h window is the sum of:
- First 15m (high-frequency): ~7-8 calls per token for TRACK_FAST
- Continuation 15m-1h (lower-frequency): ~11 calls per token for TRACK_FAST

This is a total of ~18-19 source calls per TRACK_FAST token over 1h — well within the
Source Governor's rate limits for a bounded operator-controlled run.

### Source budget requirement for a 1h runner

The future 1h runner must:
1. Call `can_request_source()` before every source call (no bypass).
2. Count consecutive failures and stop if the threshold is exceeded.
3. Not share a single long-lived connection that accumulates scheduler lock conflicts with
   concurrent 15m runners.
4. Use the same `HANDLER_SOURCE_NAME = "dexscreener"` and `HANDLER_REQUEST_KIND = "pair_market_snapshot"` constants.

---

## 11. Stop Conditions for a Future 1h Proof

A future Lane X12 bounded 1h runner must stop safely under any of the following conditions:

| Condition | Stop behavior |
|-----------|---------------|
| Duration limit reached (e.g., `--duration 2h` for a 1h collection window + overhead) | Safe exit; mark all open jobs SUCCEEDED or FAILED as appropriate |
| Consecutive source failures exceed threshold (proposed default: 5) | LANE_X12_STOPPED; log `stopped_safely_reason`; mark all open windows DIRTY_MEMORY |
| Operator kill signal (external process kill) | Jobs are marked FAILED on next E2U preflight; stale locks must be cleared manually (X10.8 pattern) |
| Token pair drift detected mid-1h window | Mark the affected token's 1h window DIRTY_MEMORY; continue other tokens if multi-token runner |
| Source Governor denies request (budget exhausted) | Gate 4 blocks; increment failure counter; follow failure path |
| Scheduler lock conflict (another RUNNING job, Gate 2) | Handler blocks this step; retry on next cadence cycle; do not hard-stop unless consecutive failure threshold reached |
| Token becomes ARCHIVED or COOLDOWN during run | Do not close the open 1h window; mark DIRTY_MEMORY; skip that token for the remainder of the run |
| Cycle budget exhausted (test-only: `_cycle_budget`) | Stop cleanly; report `cycle_budget_exhausted` as stop reason |

### External kill recovery (X10.8 pattern)

If the 1h runner is killed externally mid-run:

1. Before the next run: run E2U preflight check (`printer-report-e2u-15m-cycle-closeout`).
2. If `active_locks > 0`: identify the stale job(s); confirm status is FAILED.
3. If status is FAILED but lock_owner or locked_at is still set: run targeted conditional UPDATE
   (null lock_owner and locked_at WHERE status=FAILED AND job_name and job_kind match exactly).
4. Re-confirm active_locks = 0 before retrying any runner.

This is identical to the X10.8 maintenance pattern and must be documented in the X12 runbook.

---

## 12. Dirty-Memory Gates for WINDOW_1H

All dirty-memory gates from WINDOW_15M carry over to WINDOW_1H with 1h-specific thresholds added:

| Gate | Effect | Threshold |
|------|--------|-----------|
| Source status not COMPLETE | DIRTY_MEMORY | Any snapshot with status ≠ COMPLETE |
| Data quality label not CLEAN_DATA | DIRTY_MEMORY | Any snapshot with label ≠ CLEAN_DATA |
| Snapshot count below minimum | CADENCE_POLICY_BLOCKED → DIRTY_MEMORY | TRACK_FAST <8; TRACK_NORMAL <3 (proposed) |
| Single gap exceeding 2.5× expected interval | DIRTY_MEMORY | TF: >600s; TN: >1800s (proposed) |
| Pair drift detected mid-window | DIRTY_MEMORY | Any pair_address mismatch within the same window |
| Missing critical context | DIRTY_MEMORY | Same rule as 15m; market/Solana context absent for critical snapshots |
| Source failure rate too high | PARTIAL_MEMORY at best | >20% of expected snapshots failed |
| Token in non-trackable state mid-window | DIRTY_MEMORY | ARCHIVED, COOLDOWN, or INSTANT_REJECT state during open window |

### DO_NOT_TRAIN rule

Any window marked DIRTY_MEMORY or DO_NOT_TRAIN must:
- Be preserved in `printer_memory_windows` for audit.
- Be excluded from Lane Q clean-promotion path.
- Not be used by E2Z for clean episode creation.
- Not be used by any future retrieval engine.
- Not block a new WINDOW_1H window for the same token/pair in a later time period.

---

## 13. Replay / Idempotency Rules for WINDOW_1H

These rules mirror the WINDOW_15M idempotency established in Lane U2:

### Primary idempotency key

`(pair_id, window_kind = "WINDOW_1H", snapshot_start_id)` is the unique identifier for a
WINDOW_1H record. A promotion attempt with the same key must not create a duplicate row.

### E2Y group selection for WINDOW_1H

E2Y currently groups by `(pair_id, window_kind)` and selects the largest PARTIAL_MEMORY batch.
For WINDOW_1H, this grouping must be extended to also consider `snapshot_start_id` so that
multiple 1h windows for the same token/pair in different time periods are treated independently.

This is a code change for X12. It must not be done in X11.

### E2Z promotion idempotency for WINDOW_1H

E2Z checks for an existing episode with the same fingerprint before creating a new one. The
fingerprint for WINDOW_1H must include `window_start_at` (or `snapshot_start_id`) to distinguish
different 1h periods for the same token. If a clean WINDOW_1H episode already exists for a given
start timestamp and token/pair, re-running E2Z must be a no-op (same behavior as 15m).

### Dirty window preservation

An existing DIRTY_MEMORY or AUDIT_ONLY WINDOW_1H record must not block a future new clean
WINDOW_1H record for the same token/pair at a different time. Old dirty rows must stay visible
in `printer_memory_windows` (for audit) while new clean windows accumulate.

---

## 14. How WINDOW_15M and WINDOW_1H Interact

### Independence of evidence records

WINDOW_15M and WINDOW_1H are independent memory-window records in `printer_memory_windows`.
Each has its own `id`, `window_kind`, `snapshot_start_id`, `snapshot_end_id`, `window_start_at`,
`window_end_at`, `memory_status`, and `data_quality_label`.

A token may have:
- Multiple WINDOW_15M records over time (different time periods).
- Multiple WINDOW_1H records over time.
- A mix: some WINDOW_15M clean, some WINDOW_15M dirty; independently, some WINDOW_1H clean.
- A WINDOW_15M record with no corresponding WINDOW_1H (token died after 15m, never continued).
- A WINDOW_15M record that is DIRTY_MEMORY but a subsequent new WINDOW_1H that is CLEAN_MEMORY
  (unusual but possible if the token recovered and the 1h evidence was independently valid).

### Sequential timing model

Under the preferred sequential model:
1. Token begins tracking at t=0.
2. WINDOW_15M collects evidence from t=0 to t=15m.
3. At t=15m, E2O closes the WINDOW_15M record. Lane Q and Lane K run.
4. If the token is eligible for continuation (not ARCHIVED, not died, source alive), the 1h
   phase begins: new snapshots are collected from t=15m to t=60m.
5. At t=60m, a new E2O variant closes the WINDOW_1H record. A new Lane Q and Lane K run follows.

Steps 4-5 do not exist yet. They are the gap Lane X12 must close.

### WINDOW_15M remains primary

Even after WINDOW_1H is implemented, WINDOW_15M remains the primary active memory window.
Reasons:
- 15m has the highest information density per source call for fast-event tokens.
- A 1h window requires a token to remain trackable for 60 minutes — many memecoins die in
  the first 15 minutes.
- The retrieval engine (when activated) must query by `window_kind` and should always prefer
  15m evidence for fast decisions; 1h evidence is for continuation/survival queries.
- The memory-growth build order confirms: 15m must be stable before 1h activates.

### 1h does not replace 15m

Adding WINDOW_1H windows does not reduce the importance of WINDOW_15M. Both accumulate in
parallel. Each provides different information:
- WINDOW_15M: fast behavior, initial pump/dump/trap/die dynamics.
- WINDOW_1H: survival, continuation, consolidation, delayed dump, revival, hold viability.

Both must be clean and independently audited before either informs a paper decision.

---

## 15. How TRACK_FAST and TRACK_NORMAL Interact with Future 1h Windows

### Both lanes are eligible for WINDOW_1H

`frequency.py` defines cadences for `age > 15*60` for both TRACK_FAST and TRACK_NORMAL.
Both lanes are expected to continue into a 1h window if the token remains viable.

### Evidence density differs by lane

| Lane | First 15m snapshots | Continuation phase snapshots | Total per 1h |
|------|--------------------|-----------------------------|-------------|
| TRACK_FAST | ~7-8 (120s interval) | ~11 (240s interval, 45 min) | ~18-19 |
| TRACK_NORMAL | ~2 (420s interval) | ~4 (720s interval, 45 min) | ~6 |

TRACK_FAST tokens will have higher-resolution 1h memories. TRACK_NORMAL tokens will have
coarser evidence but will represent the slow-fade, boring-baseline cases that are essential
for anti-bias memory.

### Lane transition: first-15m → 1h phase

A token's scheduler job kind transitions at the 15m mark:

```
t < 15m:  TRACK_FAST_FIRST_15M  or  TRACK_NORMAL_FIRST_15M  (current job kinds — exist)
t >= 15m: TRACK_FAST_1H          or  TRACK_NORMAL_1H          (future job kinds — do not exist)
```

This transition requires new job kinds and new scheduler-compatible handlers. It is a Lane X12
implementation task.

### Priority order in resource contention

AGENTS.md resource priority order (relevant excerpt):
1. Open paper-trade monitoring
2. Exit-risk token snapshots
3. TRACK_FAST / micro-event token snapshots  ← TRACK_FAST_FIRST_15M / TRACK_FAST_1H
4. TRACK_NORMAL token snapshots              ← TRACK_NORMAL_FIRST_15M / TRACK_NORMAL_1H
5. Memory-window close snapshots
...

TRACK_FAST continuation snapshots have higher priority than TRACK_NORMAL continuation snapshots.
If a source budget conflict arises during a combined 1h run, TRACK_FAST tokens are served first.
This is already the policy — it does not change for 1h.

### No mixing of job kinds in a single runner step

A single runner step must not create a `TRACK_FAST_FIRST_15M` job for a token that is in the
1h phase. Similarly, it must not create a `TRACK_FAST_1H` job for a token that is still in the
first 15m phase. The runner must check `token_age_seconds` before each step and use the
appropriate job kind.

This age-aware dispatch logic does not exist in X5 or X10.10B and must be built in X12.

---

## 16. WINDOW_5M_MICRO_EVENT Support-Only Rule

`WINDOW_5M_MICRO_EVENT` remains support-only in all scenarios, including any future 1h context.

From `docs/printer-v1-post-rc-build-order.md`:
> `WINDOW_5M_MICRO_EVENT` is not a main outcome memory window. It must not satisfy the
> requirement for a completed 15m/1h/4h/12h/24h memory outcome window.

Specific prohibitions as they relate to 1h:

| Action | Status |
|--------|--------|
| 5m evidence satisfies WINDOW_1H evidence requirement | FORBIDDEN |
| 5m evidence counts toward WINDOW_1H snapshot count | FORBIDDEN |
| 5m window closes trigger a WINDOW_1H close | FORBIDDEN |
| 5m evidence unlocks retrieval for 1h queries | FORBIDDEN |
| 5m evidence informs a paper decision backed by 1h memory | FORBIDDEN |
| 5m evidence may provide micro-event context for a 1h memory (informational only) | ALLOWED (existing policy) |

WINDOW_5M_MICRO_EVENT evidence may be referenced as context in a WINDOW_1H supporting_context_json
blob, but it must be clearly labeled as micro-event support context — not as a main evidence
window and not as a substitute for any WINDOW_1H snapshot.

---

## 17. Pair Drift / Same-Token-New-Pair Handling

Pair drift is significantly more likely over a 1h window than over a 15m window. A Solana
memecoin may migrate from Pump.fun to Raydium (or to a new AMM pool) within 60 minutes of
initial tracking.

### Current pair drift state (from X10 yield report)

The live DB shows ANSEM (token id=13) has 14 pairs total for 13 tokens — one token has two
pair records, reflecting the pair drift observed during the X5 run. Pair drift is detected and
reported but does not currently trigger any automated response (no cooldown, no window block).

### Required pair drift policy for WINDOW_1H

| Event | Required action |
|-------|----------------|
| Pair address in source response differs from the pair_address the runner was given for this token at start | Record the drift event; mark the 1h window DIRTY_MEMORY; do not close a clean window |
| Pair migration detected at or before the 15m close | The 15m window may still be valid (same pair was used throughout 15m); do NOT start the 1h phase with the old pair |
| Pair migration detected during 1h continuation phase | Stop collecting for this token; mark any open 1h window DIRTY_MEMORY; do not promote |
| New pair confirmed for the same token | Requires a new tracking session starting from t=0 (new WINDOW_15M first); do not continue an existing 1h window |

### Pair-drift contamination rule

A WINDOW_1H record must reference exactly one `pair_id` in `printer_pairs`. If the pair_address
changes mid-window, the window's evidence is contaminated (it would compare two different pair's
behaviors in the same evidence record). Mixed-pair windows must be DIRTY_MEMORY.

### Operator action required

Before running any real 1h proof (X12), the operator must:
1. Confirm or update the ANSEM pair address in the token list (open item from X10 R1).
2. Decide the pair address to use for each token in the 1h run.
3. The 1h runner must record `pair_address_supplied` vs `pair_address_actual` for each window,
   exactly as X5 does today.

---

## 18. Discovery / Selection Traceability Requirements

All X10.6 traceability requirements apply to 1h token selection, with additional constraints:

### Required traceability fields for a 1h token list

A token list submitted to a future 1h runner must include (same fields as X5/X10.10B, plus):

| Field | Required | Notes |
|-------|----------|-------|
| `token_mint` | Yes | Solana mint address |
| `pair_address` | Yes | Single pair to track through the full 1h window |
| `chain` | Yes | Must be `"solana"` |
| `tracking_lane` | Yes | `"TRACK_FAST"` or `"TRACK_NORMAL"` |
| `operator_approved` | Yes | Must be `true` |
| `selected_at` | Recommended | ISO timestamp of when this token was selected for 1h tracking |
| `event_kind` | Recommended | From X10.6 event-kind constants |
| `source_trace` | Recommended | `source_request_id`, `source_response_id` from discovery |
| `manual_override_reason` | Required if lane overridden | Needed if WATCH_ONLY → TRACK_FAST override |

The `selected_at` field is especially important for 1h tracking: a token selected 2 hours ago
for a 1h window may already have evolved beyond the event that justified TRACK_FAST selection.
Freshness at 1h-selection time must be stricter than at 15m-selection time.

### Batch diversity requirement

The same X10.6 event-kind diversity principle applies to 1h selections:
- HOT_PAIR_REFERENCE tokens (BONK, WIF etc.) can be included for baseline memory but should not
  dominate the batch.
- LIQUIDITY_DECAY_EVENT, SAFETY_RISK_MEMORY, HIGH_ACTIVITY_NO_FOLLOW_THROUGH, and
  AMBIGUOUS_MEMORY_CANDIDATE tokens are especially valuable for 1h memory — they capture
  what happens to a token after the initial fast event fades.

---

## 19. Freshness Requirements Inherited from X10.9

Lane X10.9 established freshness requirements for TRACK_FAST tokens before their first snapshot.
These requirements carry forward to the 1h phase, with extended thresholds:

### TRACK_FAST freshness for 1h selection

| Evidence age at 1h selection time | Policy |
|-----------------------------------|----|
| ≤ 180 seconds | FRESH_WITHIN_PREFERRED_LIMIT — proceed normally |
| 181-300 seconds | FRESH_WITHIN_HARD_LIMIT — log warning; proceed |
| > 300 seconds | STALE_TRACK_FAST — hard block if source response evidence is stale; operator must refresh |

A TRACK_FAST token selected for 1h tracking must have been freshly confirmed as TRACK_FAST
category before the 1h run starts. The X10.9 freshness gate applies at the beginning of any
1h runner, exactly as it applies at the beginning of X5.

**Key difference from 15m:** If a TRACK_FAST token's last discovery evidence is >300 seconds old
at 1h-selection time, the event that justified TRACK_FAST selection may be over. Snapshotting
it for another hour at TRACK_FAST cadence would produce snapshots of a dead or slow token at the
wrong frequency — producing DIRTY_MEMORY rather than useful fast-event continuation data.

### TRACK_NORMAL freshness for 1h selection

Advisory-only. Same thresholds as X10.10B:
- ≤ 300s: fresh, no warning.
- 301-600s: advisory warning logged.
- > 600s: strong advisory logged; do not block (same as 15m policy).
- FRESHNESS_UNKNOWN: advisory; do not block.

### Post-15m freshness (continuous monitoring)

During the 1h continuation phase, freshness is defined differently from the pre-run gate:
- Each source call produces a new snapshot with `received_at = now`.
- The gap between consecutive snapshots must not exceed 2× the expected interval.
- Gaps exceeding this threshold are flagged as coverage gaps (Lane Q policy), not freshness blocks.
- There is no per-step freshness re-check after the first snapshot — cadence enforcement replaces it.

---

## 20. Required Future Lane X12 Proof Design

Lane X12 is the implementation and proof lane for real WINDOW_1H collection. Lane X11 approves
the X12 design outlined below. Lane X11 does NOT authorize any real 1h collection.

### X12 must build (in order):

**Step 1: Scheduler contracts extension (code change, approved for X12)**

In `scheduler/contracts.py`:
```python
TRACK_FAST_1H = "TRACK_FAST_1H"
TRACK_NORMAL_1H = "TRACK_NORMAL_1H"
```

Add both job kinds to `JOB_PRIORITY_ORDER` between `TRACK_NORMAL_FIRST_15M` and
`MEMORY_WINDOW_CLOSE`, preserving TRACK_FAST priority over TRACK_NORMAL.

**Step 2: E2O variant for WINDOW_1H (code change, approved for X12)**

New module `lane_e2o_1h_window_close.py` (or parameterize E2O to accept `window_kind`):
- `E2O_1H_WINDOW_KIND = "WINDOW_1H"`
- Same gate architecture as E2O for 15m (token_id, pair_id, snapshot_start_id checks)
- Must enforce `TRACK_FAST or TRACK_NORMAL` lane constraint (same `E2O_ALLOWED_LANES`)
- Must enforce `pair_id` consistency throughout the window
- Must refuse to close if pair drift was detected

**Step 3: 1h handlers (code change, approved for X12)**

New module `lane_e2h_fast_1h_handler.py`:
- Job kind: `TRACK_FAST_1H`
- Same 6-gate architecture as E2H (`lane_e2h_runtime_handler.py`)
- All financial locks identical

New module `lane_e2h_normal_1h_handler.py`:
- Job kind: `TRACK_NORMAL_1H`
- Same 6-gate architecture as X10.10B handler
- Freshness: advisory only (same as TRACK_NORMAL)

**Step 4: Lane Q coverage policy for WINDOW_1H (code change, approved for X12)**

In `snapshots/cadence_policy.py`:
- Add `SnapshotCadencePolicy` for `TRACK_FAST + WINDOW_1H`: minimum 8 snapshots, max gap 600s
- Add `SnapshotCadencePolicy` for `TRACK_NORMAL + WINDOW_1H`: minimum 3 snapshots, max gap 1800s

**Step 5: 1h bounded runner (code change, approved for X12)**

New module `lane_x12_1h_runner.py`:
- Accepts 1-5 TRACK_FAST tokens OR 1-7 TRACK_NORMAL tokens (separate validation or separate
  runner for each lane — do not mix TRACK_FAST and TRACK_NORMAL in one 1h runner until proven)
- Age-aware job kind dispatch: first 15m → TRACK_FAST_FIRST_15M / TRACK_NORMAL_FIRST_15M;
  after 15m → TRACK_FAST_1H / TRACK_NORMAL_1H
- Freshness gate: TRACK_FAST hard block (X10.9); TRACK_NORMAL advisory only
- Window close via E2O 1h variant after 45 minutes of continuation evidence
- All V1 financial and retrieval locks preserved
- `_adapter_map` test bypass (same as X5/X10.10B)

**Step 6: CLI registration (code change, approved for X12)**

```
printer-run-lane-x12-fast-1h-cycle    (TRACK_FAST tokens)
printer-run-lane-x12-normal-1h-cycle  (TRACK_NORMAL tokens)
```

**Step 7: Test suite (approved for X12)**

`tests/test_post_lane10_lane_x12_1h_runner.py`:
- Same pattern as test_post_lane10_lane_x10_10_normal_15m_runner.py
- TRACK_FAST rejected by TRACK_NORMAL 1h runner (and vice versa)
- WINDOW_1H job kinds created; TRACK_FAST_FIRST_15M / TRACK_NORMAL_FIRST_15M NOT created by 1h runner
- Coverage thresholds enforced (separate tests for 8-snapshot / 3-snapshot minimum)
- Pair drift detection marks window DIRTY_MEMORY
- No paper decisions, positions, PnL, retrieval, BUY/SELL/HOLD in output
- Freshness gate (TRACK_FAST hard; TRACK_NORMAL advisory)

**Step 8: Regression test suite (X12 gate)**

After X12 tests pass, run all prior regression suites:
- X5 five-token runner (174 tests)
- X10.9 freshness gate (38 tests)
- X10.6 selection traceability (105 tests)
- X6 discovery repair (150 tests)
- X10.10B TRACK_NORMAL runner (72 tests)

All must still pass. X12 code changes must not break any prior lane.

**Step 9: First real X12 proof run**

Using an isolated proof DB (copy of current `data/printer_v1.sqlite3` to a backup path):
- Run X12 TRACK_FAST 1h runner with 1-3 known tokens.
- Duration: single 1h proof (bounded).
- Expected result: 1-3 WINDOW_1H records created; covered windows promoted; locks all zero delta.
- Operator reviews before any live DB merge.

X12 must NOT be started until X11 documentation is committed and the operator explicitly approves
X12 design and implementation.

---

## 21. Locked-State Checklist

| Lock | Current | After X12 (proposed) |
|------|---------|---------------------|
| retrieval_activated | OFF | OFF (retrieval activation is a later lane) |
| paper_decisions | 0 delta | 0 delta (BUY/SELL/HOLD remain locked) |
| paper_positions | 0 | 0 |
| trade_events | 0 | 0 |
| pnl_created | 0 | 0 |
| BUY enabled | No | No |
| SELL / HOLD enabled | No | No |
| live_trading | No | No |
| wallet / private_key | No | No |
| paid_api_dependency | No | No |
| scoring / ranking / confidence | No | No |
| embeddings / vectors | No | No |
| 4h / 12h / 24h collection | Disabled | Disabled (4h comes after 1h is proven) |
| WINDOW_5M_MICRO_EVENT as main | No | No |
| WINDOW_1H collection | Disabled (X11) | Only after X12 operator approval |
| X10.10C (TRACK_NORMAL live proof) | Not in scope for X11 | Not blocked; can proceed in parallel to X12 if operator chooses |

---

## 22. Risks and Blockers

### R1: WINDOW_1H requires 7 new or modified components (BLOCKER — all for X12)

Real 1h collection is blocked until all of the following are built in X12:

1. `TRACK_FAST_1H` and `TRACK_NORMAL_1H` job kinds in `scheduler/contracts.py`
2. E2O 1h variant (`E2O_WINDOW_KIND = "WINDOW_1H"`)
3. TRACK_FAST 1h handler (new file)
4. TRACK_NORMAL 1h handler (new file)
5. Lane Q coverage policy for WINDOW_1H (both lanes)
6. 1h bounded runner (new file)
7. CLI registration and test suite

None of these exist. None can be built in X11.

### R2: TRACK_NORMAL 15m not yet run against live DB (MEDIUM — pre-X12 prerequisite)

X10.10B built the TRACK_NORMAL 15m runner and passed 72 tests. However, it has not yet been
run against the live `data/printer_v1.sqlite3`. The first TRACK_NORMAL 15m live run should be
completed before the first TRACK_NORMAL 1h proof in X12. This produces baseline TRACK_NORMAL
15m memory against which the 1h continuation memory can be compared in future retrieval.

### R3: E2Y and E2Z may need extension for WINDOW_1H grouping (MEDIUM)

E2Y currently groups by `(pair_id, window_kind)`. For WINDOW_1H with multiple time periods,
this grouping may confuse different 1h windows for the same token. E2Z may similarly need
extension to handle `window_start_at` as part of the fingerprint. These are low-risk code
changes but must be designed carefully to avoid breaking existing WINDOW_15M promotion.

### R4: Pair drift over 1h is more likely than over 15m (MEDIUM — operational risk)

Memecoins can migrate pools within 60 minutes. The operator must review the pair address for
each token before a 1h run and confirm it is stable. Automated pair-drift handling (archiving
the old pair, resuming with the new pair) is not in scope for X12 and should remain a manual
decision gate.

### R5: Token survival rate over 1h is lower than over 15m (MEDIUM — expected dirty rate)

A significant fraction of memecoins die (liquidity < $1k, volume → 0, no new snapshots pass
quality check) within 60 minutes. The DIRTY_MEMORY rate for WINDOW_1H is expected to be
higher than for WINDOW_15M, especially for TRACK_FAST tokens (which are selected during
fast events that may end before 1h). This is not a bug — it is the correct behavior. The
operator should expect a clean yield rate below 50% for the first X12 proof run.

### R6: Age-aware job kind dispatch is not implemented (MEDIUM — blocker within X12)

The current X5 and X10.10B runners create `TRACK_FAST_FIRST_15M` or `TRACK_NORMAL_FIRST_15M`
jobs regardless of the token's age. An age-aware dispatch (first 15m → FIRST_15M jobs; beyond
15m → 1H jobs) does not exist. This dispatch logic is a core new feature for X12.

### R7: 4h / 12h / 24h remain fully disabled (CONFIRMED — not a risk, a policy)

This review explicitly confirms: 4h, 12h, and 24h windows remain disabled after X11. They
remain disabled after X12. They may only be activated after 1h collection is proven clean and
stable over multiple proof runs, and only after an explicit operator-approved activation lane
beyond X12.

### R8: ANSEM pair drift unresolved (OPEN — operator action required before X12)

From X10 yield report R1: ANSEM (token id=13) has 14 pairs registered for 13 tokens. The
operator must resolve the ANSEM pair address before including ANSEM in any future bounded run
(15m or 1h). Leaving it unresolved risks producing DIRTY_MEMORY windows for ANSEM in both
WINDOW_15M and any future WINDOW_1H.

### R9: X10.10C (TRACK_NORMAL live DB proof) not scheduled (NON-BLOCKING — separate track)

X10.10C (the real-DB proof run of X10.10B against live data) is not in scope for X11 or X12.
It can proceed as an independent operator-approved action at any time. Its results would confirm
TRACK_NORMAL 15m memory grows correctly and provide the baseline TRACK_NORMAL data that will
eventually inform TRACK_NORMAL 1h continuation memory.

---

## 23. Final Verdicts

```
X11_DOC_ONLY_COMPLETE:                              YES
  Reason: All 23 sections completed. No code was modified. No runtime was
  invoked. No source calls were made. No DB was written. No migrations were
  run. All financial and retrieval locks remain at zero delta. The design for
  WINDOW_1H has been documented for a future Lane X12 implementation.

READY_FOR_X12_DESIGN:                               YES
  Reason: The proposed WINDOW_1H evidence identity, snapshot cadences,
  coverage thresholds, dirty-memory gates, replay/idempotency rules, stop
  conditions, and component inventory are fully specified in this document.
  X12 implementation may begin after operator approval of this X11 review.

NOT_READY_FOR_REAL_1H_RUNTIME:                      CONFIRMED
  Reason: Seven required components are missing (scheduler job kinds, E2O 1h
  variant, TRACK_FAST 1h handler, TRACK_NORMAL 1h handler, Lane Q 1h
  coverage policy, 1h bounded runner, CLI registration). None are built. None
  can be built in X11. Real WINDOW_1H collection must wait for X12.

WINDOW_15M_REMAINS_PRIMARY_ACTIVE_MEMORY:           CONFIRMED
  Reason: WINDOW_15M is the only active real-collection window. 18
  WINDOW_15M_CLEAN_MEMORY episodes exist. WINDOW_1H has zero records. 15m
  must remain the primary window during X12 implementation and through the
  first X12 proof run. 15m is not replaced by 1h.

WINDOW_5M_REMAINS_SUPPORT_ONLY:                     CONFIRMED
  Reason: WINDOW_5M_MICRO_EVENT cannot satisfy any WINDOW_1H evidence
  requirement. It cannot count toward WINDOW_1H snapshot totals. It cannot
  trigger a WINDOW_1H close. It cannot unlock retrieval, paper decisions,
  BUY, positions, or PnL by itself. This rule is unchanged from prior lanes
  and applies without exception to any future 1h collection.

ALL_FINANCIAL_AND_RETRIEVAL_LOCKS_PRESERVED:        CONFIRMED
  Reason: This document introduces no code changes. No financial lock is
  relaxed. No retrieval is activated. No BUY/SELL/HOLD capability is added.
  No paper decisions are unlocked. No paper positions, trade events, paper
  trade audits, or PnL are created. Live trading, wallet, private key, and
  paid API locks are all confirmed active. 4h/12h/24h collection remains
  disabled. Scoring, ranking, confidence, and weighted logic remain locked.

x12_design_approved_by_x11:                        YES
  The 9-step X12 build sequence (Section 20) is approved as the correct
  implementation plan. X12 must not start until this X11 document is
  committed and the operator explicitly approves X12 to proceed.

x10_10c_status:                                     NOT_IN_SCOPE_NOT_BLOCKED
  The TRACK_NORMAL 15m live-DB proof run (X10.10C) is not in scope for X11
  or X12. It is not blocked. It is a prerequisite milestone before the first
  TRACK_NORMAL 1h proof in X12, but it does not block the TRACK_FAST 1h
  proof.

4h_12h_24h_status:                                  DISABLED_UNTIL_1H_PROVEN
  4h, 12h, and 24h collection remain disabled and will remain disabled through
  X12. They may only be activated after 1h memory is proven clean and stable,
  and only after an explicit operator-approved activation lane beyond X12.
```

---

## Files Changed

| File | Status |
|------|--------|
| `docs/printer-v1-lane-x11-1h-activation-readiness.md` | CREATED (this file) |

## Code Touched

None. Zero code changes in this lane.

## Runtime Touched

None. No runtime was invoked. No bounded runner was started.

## Checks Run

| Check | Result |
|-------|--------|
| Source-of-truth docs read (AGENTS.md, master spec, post-RC build order, memory factory guide) | PASS |
| X10 / X10.10A / X10.10B / X10.6 / X10.7 / X10.8 / X10.9a docs read | PASS |
| `frequency.py` inspected (cadences beyond 15m) | PASS |
| `scheduler/contracts.py` inspected (job kinds) | PASS |
| `e2o_memory_window_close.py` inspected (E2O_WINDOW_KIND constant) | PASS |
| No code changes made | CONFIRMED |
| No source fetching | CONFIRMED |
| No DB writes | CONFIRMED |
| All V1 locks confirmed active | CONFIRMED |
| No 1h collection authorized | CONFIRMED |
| No fake 1h assembled from 15m data | CONFIRMED |

## Pass / Fail

**PASS.** Lane X11 is documentation-only and all required sections are complete.

## Risks

See Section 22. Summary of highest-priority risks:
- R1 (BLOCKER): Real 1h requires 7 new/modified components — none built yet.
- R2 (MEDIUM): TRACK_NORMAL 15m not yet run against live DB.
- R4 (MEDIUM): Pair drift more likely over 1h; ANSEM drift still unresolved (R8).
- R5 (EXPECTED): DIRTY_MEMORY rate for first 1h proof will be higher than 15m rate.

## Whether X12 Design Can Proceed

**YES.** X12 design and implementation can begin after operator approval of this X11 review.
The required component inventory (Section 4), evidence identity design (Section 7), cadence
proposals (Section 8-9), dirty-memory gates (Section 12), idempotency rules (Section 13), and
9-step build sequence (Section 20) are fully specified.

## Whether Real 1h Remains Blocked

**YES.** Real WINDOW_1H collection remains blocked until Lane X12 is implemented, tested, and
operator-approved. No real 1h collection can occur in Lane X11. No code change in this session
authorizes or enables real 1h collection. WINDOW_15M remains the only active real-collection
window.
