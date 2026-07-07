# Printer V1 — Lane X10.10A Mixed-Lane 15m Memory Growth Audit

**Verdict:** `MIXED_LANE_MEMORY_GROWTH_NEEDED`
**Implementation status:** `IMPLEMENTATION_NOT_YET_DONE`
**Recommended next lane:** `LANE_X10_10B` (bounded TRACK_NORMAL 15m runner — new module)
**Locks preserved:** `LOCKS_PRESERVED`

**Audit type:** Read-only. No code changes. No runtime. No source calls. No DB writes.
**Date:** 2026-07-07

---

## 1. Purpose

This audit determines whether the Printer V1 memory pipeline needs a bounded 15m runner for
TRACK_NORMAL tokens, and if so, how to implement it safely without breaking any V1 lock.

The specific question: Lane X5 is TRACK_FAST-only. TRACK_NORMAL tokens currently receive **no
bounded 15m memory windows**. Is this a gap that causes winner bias, and how should it be closed?

No code was modified. No runtime was invoked. No DB was written. No source calls were made.

---

## 2. Code Paths and Documents Inspected

### 2.1 Documents Read

| Document | Key Finding |
|---|---|
| `AGENTS.md` | Resource priority order; all V1 locks; anti-bias rules |
| `docs/printer-v1-clean-master-spec.md` | TRACK_NORMAL cadence: 5-10 min first 15m; max_track_normal=7 |
| `docs/printer-v1-post-rc-build-order.md` | Post-RC Lane 4 explicitly mentions mixed TRACK_FAST/TRACK_NORMAL |
| `docs/printer-v1-memory-factory-guide.md` | Conservative config: max_track_fast=3, max_track_normal=7; anti-bias |
| `docs/printer-v1-lane-x10-9a-pre-snapshot-freshness-audit.md` | Freshness policy per lane; TRACK_NORMAL advisory-only (no hard block) |
| `docs/printer-v1-lane-x10-8-manual-discovery-15m-proof-report.md` | X10.8 run was TRACK_FAST-only; pipeline proved correct for 5 TRACK_FAST tokens |
| `docs/printer-v1-lane-x10-6-discovery-selection-traceability-repair.md` | X10.6 event-kind system; TRACK_NORMAL candidates eligible for selection |

### 2.2 Source Files Inspected

| File | Lines / Purpose | Key Finding |
|---|---|---|
| `lane_x5_five_token_runner.py` | Lines 1-343 | Validator hard-requires `tracking_lane == "TRACK_FAST"` (line 292); TRACK_NORMAL rejected |
| `lane_x10_9_freshness_gate.py` | Full file | No TRACK_NORMAL path; all logic is TRACK_FAST; advisory threshold defined in X10.9a doc only |
| `lane_x6_discovery_selection_repair.py` | Full file | Selects from all discovery candidates; `freshness_warning=True` only for TRACK_FAST >120s |
| `lane_x10_6_selection_traceability.py` | Full file | Event kinds and context tags apply to all lanes; `no_discovery_origin` etc. are lane-agnostic |
| `scheduler/contracts.py` | Lines 9-27 | `TRACK_NORMAL_FIRST_15M` job kind **is defined** (`JobKind.TRACK_NORMAL_FIRST_15M`) |
| `scheduler/resource_governor.py` | Lines 89-129 | `next_check_interval_seconds[TRACK_NORMAL_FIRST_15M] = 300`; retry interval = 300s |
| `snapshots/frequency.py` | Lines 46-52 | TRACK_NORMAL first 15m base interval = **420 seconds (~7 min)** |
| `e2h_runtime_handler.py` | Lines 1-120 | Handler is TRACK_FAST_FIRST_15M only; no TRACK_NORMAL handler exists |
| `e2c_readiness.py` | Lines 278-283 | Plans `TRACK_NORMAL_FIRST_15M` jobs for TRACK_NORMAL tokens (infrastructure exists) |
| `e2c_fixture_rehearsal.py` | Lines 115-118 | Selects `TRACK_NORMAL_FIRST_15M` vs `TRACK_FAST_FIRST_15M` by lifecycle_lane |
| `e2o_memory_window_close.py` | Line 51 | `E2O_ALLOWED_LANES = frozenset({"TRACK_FAST", "TRACK_NORMAL"})` — window close already works |
| `snapshots/cadence_policy.py` | Lines 111-115 | `SnapshotCadencePolicy` for `TRACK_NORMAL + WINDOW_15M` **is defined** |
| `lifecycle/tracking_queue.py` | Lines 33-35 | `TRACK_NORMAL → TRACK_NORMAL_FIRST_15M` mapping is live |
| `snapshots/recorder.py` | Lines 25-26 | `TRACK_NORMAL → TRACK_NORMAL_FIRST_15M` mapping is live |

### 2.3 Searches Performed

| Search | Result |
|---|---|
| `TRACK_NORMAL_FIRST_15M` in `operator_cli/` | Found in `e2c_readiness.py` and `e2c_fixture_rehearsal.py` only; no handler, no runner |
| Any `lane_x*normal*` or `bounded.*track_normal` file | No file found |
| `lane_x10_10*` | No file found |

---

## 3. Current Behavior: What Happens to TRACK_NORMAL Tokens Today

**Answer: TRACK_NORMAL tokens receive zero 15m memory windows under any bounded run.**

The full evidence chain:

1. Discovery (`printer-discover-candidates-once`) creates candidates with `tracking_lane` field.
   TRACK_NORMAL candidates are written alongside TRACK_FAST candidates — no issue here.

2. X6 selection (`printer-run-lane-x6-discovery-selection-repair`) reads both lanes.
   `freshness_warning=False` for TRACK_NORMAL even if stale — appropriate (advisory only, no block).

3. X10.6 batch (`build_selection_batch`) accepts TRACK_NORMAL candidates.
   Event kinds, context tags, source traces work for all lanes. No TRACK_NORMAL-specific gap here.

4. **Lane X5** (`printer-run-lane-x5-five-token-cycle`) rejects any non-TRACK_FAST token:
   ```
   lane_x5_five_token_runner.py:292
       if lane != _REQUIRED_TRACKING_LANE:   # "TRACK_FAST"
           errors.append(...)
   ```
   A token list with `tracking_lane=TRACK_NORMAL` fails validation and X5 returns `LANE_X5_BLOCKED`.

5. No other bounded runner exists for TRACK_NORMAL. Searching the entire codebase finds:
   - `TRACK_NORMAL_FIRST_15M` job kind defined in contracts, planned in e2c_readiness, mapped in
     lifecycle queue and recorder — but **no handler and no runner** have been implemented.
   - `e2h_runtime_handler.py` is TRACK_FAST_FIRST_15M only.

**Result:** A TRACK_NORMAL token goes through discovery, X6, X10.6 — and then stops.
It is never snapshotted. It never gets a WINDOW_15M. It produces zero memory.

---

## 4. Answers to the 12 Audit Questions

### Q1: Does TRACK_NORMAL need its own bounded 15m runner, or can X5 be extended?

**Verdict: TRACK_NORMAL needs its own dedicated runner. X5 must NOT be extended.**

Reasons X5 extension is wrong:
- X5 is hard-proven with exactly 5 TRACK_FAST tokens through X10.7 and X10.8. Opening it to
  TRACK_NORMAL would invalidate the proof (the proven invariant is "exactly 5 TRACK_FAST").
- TRACK_NORMAL has a fundamentally different snapshot cadence (420s vs 120s), job kind
  (TRACK_NORMAL_FIRST_15M vs TRACK_FAST_FIRST_15M), and freshness policy (advisory vs hard block).
- X5 uses `_REQUIRED_TRACKING_LANE = "TRACK_FAST"` as a hard constant. Relaxing it would mean
  all 38 X10.9 freshness gate tests would need re-verification, and the TRACK_FAST-only invariant
  stated in the Lane X5 doc would no longer hold.
- Mixing lanes in one runner creates shared-state risk: a stalled TRACK_NORMAL token could affect
  TRACK_FAST cadence continuity and vice versa.

Correct approach: A new parallel runner (`lane_x10_10_normal_15m_runner.py`, as X10.10B) that
mirrors X5's structure but with TRACK_NORMAL-specific constants and up to 7 tokens.

---

### Q2: What is the spec-defined snapshot cadence for TRACK_NORMAL in the first 15m?

From `snapshots/frequency.py` lines 46-52:
```python
if lane == TokenLifecycleState.TRACK_NORMAL:
    age = token_age_seconds if token_age_seconds is not None else 0
    if age <= 15 * 60:
        return 420   # 7 minutes during first 15m
    if age <= 60 * 60:
        return 720   # 12 minutes until 1h
    return 1200      # 20 minutes after 1h
```

**First 15m cadence: one snapshot every 420 seconds (~7 minutes).**
This is 2 snapshots per 15m window (at ~7 min and ~14 min — approximately 2 per window, not 10
like TRACK_FAST). TRACK_NORMAL 15m windows will have fewer data points than TRACK_FAST — this is
by design; TRACK_NORMAL is for tokens where high-resolution is not justified.

From the clean-master-spec: "TRACK_NORMAL: every 5-10 min first 15m" — the 420s (~7 min)
implementation is within spec.

---

### Q3: What job kind does TRACK_NORMAL use for first 15m?

**`TRACK_NORMAL_FIRST_15M`** — defined at `scheduler/contracts.py:11`:
```python
class JobKind(str, Enum):
    TRACK_NORMAL_FIRST_15M = "TRACK_NORMAL_FIRST_15M"
```

It is in `PHASE35_SAFE_JOB_KINDS` (line 25 of contracts.py) and has its own resource governor
intervals (300s next_check, 300s retry). The scheduler fully supports this job kind — it just has
no handler or runner to create/execute jobs of this type.

---

### Q4: Does any existing runner currently execute TRACK_NORMAL_FIRST_15M jobs?

**No.** Exhaustive search result:

| Layer | Status |
|---|---|
| Job kind defined | YES (`contracts.py:11`) |
| Resource governor intervals | YES (300s, 300s) |
| Cadence policy defined | YES (cadence_policy.py, TRACK_NORMAL + WINDOW_15M) |
| Lifecycle queue mapping | YES (tracking_queue.py:35) |
| Snapshot recorder mapping | YES (recorder.py:26) |
| E2C readiness planner | YES (e2c_readiness.py:280) |
| E2C fixture rehearsal | YES (e2c_fixture_rehearsal.py:117) |
| **E2H-style handler** | **NO — does not exist** |
| **Bounded runner** | **NO — does not exist** |

The infrastructure is ready but the execution layer (handler + runner) is missing.

---

### Q5: Should TRACK_NORMAL share source budget with TRACK_FAST, or have its own allocation?

**Share the Source Governor, do not bypass it. No separate budget required.**

Budget pressure comparison (steady-state):
- TRACK_FAST (max 3 tokens): one call per 120s per token = 1 call every 40s combined
- TRACK_NORMAL (max 7 tokens): one call per 420s per token = 1 call every 60s combined
- Combined load: ~1 call per 24s in the busiest possible scenario (3 TRACK_FAST + 7 TRACK_NORMAL)

This is within the Source Governor's managed capacity. The governor already implements
`TRACK_FAST > TRACK_NORMAL` in priority order, so TRACK_FAST calls are never crowded out.

Key requirement: the TRACK_NORMAL runner must call `can_request_source()` from the Source Governor
before any source call, exactly as the E2H handler does. No bypass. No separate governor instance.

If both runners are active simultaneously, the scheduler's `no OTHER RUNNING jobs` gate (Gate 2 in
E2H) means they cannot execute source calls at the exact same moment — they are naturally
interleaved by the job-claim mechanism.

---

### Q6: Does TRACK_NORMAL need the X10.9 freshness gate (hard block), or just advisory?

**TRACK_NORMAL needs advisory only — no hard block. X10.9's hard gate must not apply to
TRACK_NORMAL tokens.**

Justification:
- TRACK_NORMAL tokens are by definition slower-moving. A 10-minute-old TRACK_NORMAL candidate is
  not stale in the same sense as a 3-minute-old TRACK_FAST candidate.
- The spec defines TRACK_NORMAL as "every 5-10 min snapshots" — a 600s staleness threshold is
  meaningful, not 180s.
- Hard blocking on TRACK_NORMAL before a 15m window would require re-discovery for slow-moving
  tokens that are legitimately still worth tracking.
- Anti-bias rules: blocking stale TRACK_NORMAL tokens would exclude exactly the slow-fade and
  boring-but-useful tokens that prevent winner bias.

Advisory policy (from X10.9a doc, §5 Q7):
- Warn if TRACK_NORMAL candidate age > 300s at selection time
- Soft-flag if age > 600s
- Never hard-block TRACK_NORMAL in the runner pre-loop (only in X6 advisory)
- If no discovery candidate exists: `FRESHNESS_UNKNOWN` advisory, no block

Implementation note: The X10.9 freshness gate (`check_token_list_freshness`) is called from X5
with `FRESHNESS_UNKNOWN_BLOCKED` triggering a block. A TRACK_NORMAL runner must call a separate
advisory path — or call the same gate but treat `FRESHNESS_UNKNOWN` as advisory-only (warn in
output, do not block).

---

### Q7: What freshness policy should apply to TRACK_NORMAL in the first 15m?

| Age of best evidence | Policy | Action |
|---|---|---|
| <= 300 seconds | FRESH_WITHIN_PREFERRED | No warning |
| 301-600 seconds | FRESH_WITHIN_ADVISORY_LIMIT | Log warning; continue |
| > 600 seconds | STALE_ADVISORY | Log strong warning; continue (do not block) |
| No evidence | FRESHNESS_UNKNOWN | Log advisory; continue (do not block) |

These thresholds reflect TRACK_NORMAL's inherently slower pace. The 300s preferred threshold
aligns with the resource governor's 300s `next_check_interval_seconds` for TRACK_NORMAL_FIRST_15M.

Note: The runner output should always include `freshness_advisory_results` (list of per-token
freshness info) so the operator can see which tokens had stale designations. This is analogous to
X5's `freshness_gate_results` field — but it is informational, not a blocker.

---

### Q8: What is the winner-bias risk if only TRACK_FAST tokens receive 15m memory?

**HIGH — current state produces pure winner-selection bias. This is an explicit anti-bias
violation.**

From the Memory Factory Guide (anti-bias rules):
- "no winner-only dataset"
- "no survivorship bias — tokens that fail, die, or are boring are as important as successes"
- "include failed tokens, traps, liquidity decay, slow fades, revivals"

Current state analysis:
- X5 and X6 select TRACK_FAST tokens based on fast observable events (micro-cap pumps, migration
  events, new pairs). These are inherently the most active tokens at selection time.
- TRACK_NORMAL candidates in X6 include: LIQUIDITY_DECAY_EVENT, HIGH_ACTIVITY_NO_FOLLOW_THROUGH,
  SAFETY_RISK_MEMORY, AMBIGUOUS_MEMORY_CANDIDATE — the exact anti-bias categories.
- Without a TRACK_NORMAL runner, none of these categories accumulate memory.
- The Memory Factory's `max_track_normal=7` cap was set at 7 for a reason: TRACK_NORMAL tokens
  are expected to form the bulk of the diverse, unbiased memory set.

**Concrete bias introduced by current state:**
- All 15m memory windows come from tokens that were fast-moving at selection time
- Slow-moving tokens, failed tokens, and boring baseline tokens have zero representation
- Future retrieval (when activated) would only retrieve fast-event patterns
- Risk: the memory factory learns only "what a fast-moving token looks like" and cannot distinguish
  it from a slow-moving token because it has no slow-moving baseline

This is not a minor gap. The memory factory's anti-bias architecture requires TRACK_NORMAL memory.

---

### Q9: What is the minimum viable TRACK_NORMAL 15m runner?

**Minimum viable specification:**

| Parameter | Value | Basis |
|---|---|---|
| Runner name | `lane_x10_10_normal_15m_runner.py` | Mirrors `lane_x5_five_token_runner.py` |
| CLI command | `printer-run-lane-x10-10-normal-15m-cycle` | Parallel to `printer-run-lane-x5-five-token-cycle` |
| Token count | 1 to 7 (operator-specified) | `max_track_normal=7` from Memory Factory Guide |
| Required tracking_lane | `TRACK_NORMAL` | Hard-validated (mirrors X5's TRACK_FAST check) |
| Job kind | `TRACK_NORMAL_FIRST_15M` | From `JobKind.TRACK_NORMAL_FIRST_15M` |
| Snapshot interval | ~420 seconds (7 min) | From `frequency.py` TRACK_NORMAL first-15m value |
| Window kind | `WINDOW_15M` | Same as X5; WINDOW_15M only |
| Freshness gate | Advisory only (see Q7) | No hard block for TRACK_NORMAL |
| Source Governor | Required — no bypass | Same as E2H/X5 |
| Central Scheduler | Required — job-claim pattern | Same as E2H/X5 |
| Window close | E2O (already allows TRACK_NORMAL) | `E2O_ALLOWED_LANES` includes TRACK_NORMAL |
| Financial locks | All V1 locks active | No BUY/SELL/HOLD, no paper decisions, no PnL |
| Duration flag | `--duration 1h` (default) | Same as X5 |
| Operator approval | Required per token | Same as X5 |

**Minimum token list format:**
```json
{
  "tokens": [
    {
      "token_mint": "<MINT_A>",
      "pair_address": "<PAIR_A>",
      "chain": "solana",
      "tracking_lane": "TRACK_NORMAL",
      "operator_approved": true
    }
  ]
}
```

This is a strict subset of the X6/X10.6 selection flow. The runner does NOT need to replicate X5's
5-token-exactly constraint — 1 to 7 tokens are valid.

---

### Q10: What lock set must the TRACK_NORMAL runner enforce?

Identical to Lane X5. All V1 locks carry over with no exceptions:

| Lock | Value | Notes |
|---|---|---|
| `no_buy_sell_hold` | True | No trading logic |
| `no_paper_decisions` | True | No `printer_paper_decisions` writes |
| `no_positions` | True | No `printer_paper_positions` writes |
| `no_pnl` | True | No PnL computation |
| `no_retrieval_activation` | True | No `printer_memory_retrieval_matches` writes |
| `no_live_trading` | True | No wallet, private keys, signing |
| `no_paid_api` | True | DexScreener free tier only |
| `no_source_governor_bypass` | True | Must call `can_request_source()` |
| `no_central_scheduler_bypass` | True | Must use job-claim pattern |
| `no_scoring_ranking_confidence` | True | No probability or scoring logic |
| `no_weighted_logic` | True | No weighted averages or optimization |
| `no_1h_4h_12h_24h_collection` | True | WINDOW_15M only |
| `no_5m_main_window` | True | WINDOW_5M_MICRO_EVENT is support-only |
| `no_daemon_mode` | True | Bounded operator run only |
| `no_unbounded_loop` | True | Must have duration limit |

Additional lock specific to X10.10B:
| `no_track_fast_in_normal_runner` | True | Runner validator must reject TRACK_FAST tokens |

This last lock prevents misuse: a TRACK_FAST token must NOT be run through the TRACK_NORMAL
runner (it would produce under-sampled windows relative to what TRACK_FAST events need).

---

### Q11: What test coverage is needed for a TRACK_NORMAL 15m runner?

Test file: `tests/test_post_lane10_lane_x10_10_normal_15m_runner.py`

**Validator tests (mirrors X5 test pattern):**
```
test_track_normal_token_list_validates_one_token
test_track_normal_token_list_validates_seven_tokens (max)
test_eight_tokens_rejected (max exceeded)
test_track_fast_token_rejected_by_track_normal_runner
test_watch_only_token_rejected
test_missing_pair_address_rejected
test_duplicate_mint_rejected
test_operator_approved_required
```

**Freshness advisory tests (no hard block):**
```
test_fresh_track_normal_within_300s_no_warning
test_stale_track_normal_300_600s_advisory_warning_logged
test_stale_track_normal_over_600s_strong_advisory_logged
test_no_discovery_candidate_freshness_unknown_advisory_not_blocked
test_stale_track_normal_does_not_block_run
```

**Window and job kind tests:**
```
test_creates_track_normal_first_15m_jobs
test_does_not_create_track_fast_first_15m_jobs
test_window_kind_is_window_15m_only
test_e2o_closes_window_for_track_normal
test_snapshot_interval_is_420_seconds_approx
```

**Lock tests (mirrors X5 pattern):**
```
test_no_paper_decisions_delta_in_output
test_no_positions_delta_in_output
test_no_retrieval_matches_delta_in_output
test_hard_locks_all_true_in_output
test_buy_sell_hold_all_false_in_output
```

**Budget and scheduler tests:**
```
test_source_governor_checked_before_each_source_call
test_running_jobs_gate_blocks_when_other_job_running
test_active_locks_gate_blocks_when_other_lock_exists
test_consecutive_failures_trigger_safe_stop
```

**No forbidden fields tests:**
```
test_output_has_no_buy_sell_hold_fields
test_output_has_no_score_rank_confidence_fields
test_output_has_no_position_pnl_fields
```

Estimated: 30-40 tests. All must use SQLite in-memory DB (apply_migrations pattern, same as X5).

---

### Q12: What risks and blockers exist for implementing TRACK_NORMAL 15m memory growth?

#### Risk 1: Source budget overlap when X5 and X10.10B run concurrently (MEDIUM)

If the operator runs X5 (3 TRACK_FAST, ~120s cadence) and X10.10B (7 TRACK_NORMAL, ~420s cadence)
simultaneously, the scheduler's `no OTHER RUNNING jobs` Gate 2 (in E2H) means they cannot
execute at the exact same instant. This produces de facto interleaving but may cause X5 cadence
slip (X5 might wait for X10.10B's job to complete before claiming its own job slot).

**Mitigation**: Document that X5 and X10.10B should not run in the same process simultaneously.
They can run sequentially (X5 first 15m, then X10.10B) or in separate operator-bounded cycles.
The source budget math shows they are compatible if interleaved (one 15m window each, not
overlapping) — just not as parallel processes sharing the same DB.

#### Risk 2: E2O window close works — but has it been tested for TRACK_NORMAL? (LOW)

`E2O_ALLOWED_LANES = frozenset({"TRACK_FAST", "TRACK_NORMAL"})` exists and is correct. However,
no X10.8-equivalent proof run has been done for TRACK_NORMAL tokens. The first X10.10B run will be
the first real-world validation of E2O with a TRACK_NORMAL token.

**Mitigation**: Include an E2O + TRACK_NORMAL integration test in the X10.10B test suite using an
in-memory DB before the first real run.

#### Risk 3: No E2H-equivalent TRACK_NORMAL handler exists (HIGH — BLOCKER for implementation)

The X5 cadence loop calls `execute_track_fast_first_15m_job()` (E2H). A TRACK_NORMAL runner
analogously needs `execute_track_normal_first_15m_job()` — an E2H-equivalent for TRACK_NORMAL.

This is the core missing piece. Options:
- **Option A**: Create a thin `lane_e2h_normal_handler.py` that mirrors E2H but uses
  `TRACK_NORMAL_FIRST_15M` job kind and TRACK_NORMAL validation rules.
- **Option B**: Extend E2H to be lane-parameterized (accepts job_kind as argument). Simpler but
  risks breaking the proven TRACK_FAST E2H path.

**Recommended**: Option A — separate handler file. Clean separation. E2H stays untouched.

#### Risk 4: TRACK_NORMAL freshness advisory not yet implemented (LOW — gaps exist)

X10.9 provides no TRACK_NORMAL advisory path. The `check_token_list_freshness` function returns
`FRESHNESS_UNKNOWN_BLOCKED` for unknown evidence — which is a BLOCK, not an advisory. The X10.10B
runner must either:
(a) not call `check_token_list_freshness` and implement its own advisory-only freshness check, or
(b) call `check_token_list_freshness` and treat UNKNOWN/STALE results as advisory-only (log but
    do not add to `blocked_reasons`).

Option (b) is simpler — reuse the gate but change the runner's response to the result.

#### Risk 5: Anti-bias requires diverse TRACK_NORMAL candidate pool (MEDIUM — operator discipline)

The runner itself does not enforce diversity. The operator must ensure the X6/X10.6 selection
process identifies genuinely diverse TRACK_NORMAL candidates (not just slower TRACK_FAST tokens).
If the operator puts 7 HOT_PAIR_REFERENCE tokens as TRACK_NORMAL, the bias is not resolved.

**Mitigation**: X10.6 batch balance assessment already warns when event-kind diversity is low.
Document that TRACK_NORMAL candidates should include LIQUIDITY_DECAY_EVENT, SAFETY_RISK_MEMORY,
HIGH_ACTIVITY_NO_FOLLOW_THROUGH, and AMBIGUOUS_MEMORY_CANDIDATE event kinds.

#### Risk 6: TRACK_NORMAL 15m windows produce fewer snapshots (LOW — expected)

With ~2 snapshots per 15m window (vs ~10 for TRACK_FAST), TRACK_NORMAL WINDOW_15M will often
produce PARTIAL_MEMORY (not CLEAN_MEMORY) on first run — same as X5/X10.8. This is not a bug;
CLEAN_MEMORY requires multi-window accumulation.

**Mitigation**: Document expected output. PARTIAL_MEMORY + CLEAN_DATA = pipeline success for
a first-run proof.

---

## 5. Gap Summary

| Gap | Severity | Status |
|---|---|---|
| No bounded TRACK_NORMAL 15m runner | CRITICAL | Unimplemented |
| No TRACK_NORMAL_FIRST_15M handler (E2H equivalent) | CRITICAL (blocker) | Unimplemented |
| TRACK_NORMAL freshness advisory path not in X10.9 | MEDIUM | Unimplemented |
| Zero TRACK_NORMAL 15m memory windows in any proof run | CRITICAL | Confirmed gap |
| E2O TRACK_NORMAL integration not tested (code exists) | LOW | Test gap |
| No operator doc for mixed-lane concurrent-run risk | LOW | Doc gap |

---

## 6. What Infrastructure Is Already Ready

Significant infrastructure exists and does NOT need to be built for X10.10B:

| Infrastructure | Location | Ready |
|---|---|---|
| `TRACK_NORMAL_FIRST_15M` job kind | `scheduler/contracts.py:11` | YES |
| Resource governor intervals | `resource_governor.py:95,121` | YES |
| Cadence policy TRACK_NORMAL + WINDOW_15M | `cadence_policy.py:111-115` | YES |
| E2O window close (TRACK_NORMAL allowed) | `e2o_memory_window_close.py:51` | YES |
| Lifecycle queue mapping | `lifecycle/tracking_queue.py:35` | YES |
| Snapshot recorder mapping | `snapshots/recorder.py:26` | YES |
| E2C readiness planner (plans TRACK_NORMAL jobs) | `e2c_readiness.py:278-283` | YES |
| E2C fixture rehearsal (TRACK_NORMAL path) | `e2c_fixture_rehearsal.py:117` | YES |
| `get_base_snapshot_interval_seconds` TRACK_NORMAL | `snapshots/frequency.py:46` | YES |
| DB schema (all required tables) | All migration files | YES |
| Source Governor (shared) | `sources/governor.py` | YES |
| Anti-bias token event kinds (X10.6) | `lane_x10_6_selection_traceability.py` | YES |

What is **missing** (must be built in X10.10B):
1. `lane_e2h_normal_first_15m_handler.py` — TRACK_NORMAL handler (parallel to E2H)
2. `lane_x10_10_normal_15m_runner.py` — bounded runner (parallel to X5)
3. CLI command registration in `commands.py` and `pyproject.toml`
4. Test suite `tests/test_post_lane10_lane_x10_10_normal_15m_runner.py`
5. TRACK_NORMAL freshness advisory (either extend X10.9 or implement inline in runner)

---

## 7. Safest Implementation Plan (X10.10B)

Build order within X10.10B (all in one lane, no splitting):

### Step 1: TRACK_NORMAL handler (`lane_e2h_normal_first_15m_handler.py`)

Mirrors E2H (`e2h_runtime_handler.py`) with:
- `HANDLER_JOB_KIND = "TRACK_NORMAL_FIRST_15M"`
- `HANDLER_LIFECYCLE_LANE = "TRACK_NORMAL"`
- `HANDLER_TARGET_WINDOW = "WINDOW_15M"`
- Same gate order (transport → no running jobs → no active locks → source governor → execute)
- No freshness hard block (advisory only, unlike E2H's position in the TRACK_FAST chain)
- All financial locks remain

Scope: new file only. E2H and X5 untouched.

### Step 2: Bounded runner (`lane_x10_10_normal_15m_runner.py`)

Mirrors `lane_x5_five_token_runner.py` with:
- Validator: `tracking_lane == "TRACK_NORMAL"` (hard check), 1-7 tokens
- Cadence: snapshot_interval_seconds default = 420
- Job creation calls: `TRACK_NORMAL_FIRST_15M` kind
- Freshness: call `check_token_list_freshness` but treat STALE/UNKNOWN as advisory (log in output,
  do not add to `blocked_reasons`)
- Output: includes `freshness_advisory_results` (not `freshness_gate_results`)
- All V1 lock fields identical to X5 output format

Scope: new file only. X5 untouched.

### Step 3: CLI registration

In `commands.py`: add `printer-run-lane-x10-10-normal-15m-cycle` command.
In `pyproject.toml`: add script entry.

Scope: `commands.py` (one function, one `add_parser` call) + `pyproject.toml` (one line).

### Step 4: Test suite

`tests/test_post_lane10_lane_x10_10_normal_15m_runner.py`
30-40 tests covering all cases from Q11. Uses in-memory SQLite + `apply_migrations`.

### Step 5: Regression check

After X10.10B tests pass:
- Re-run X5 tests (must still pass: 174 tests)
- Re-run X10.9 tests (must still pass: 38 tests)
- Re-run X10.6 tests (must still pass: 105 tests)
- Re-run X6 tests (must still pass: 150 tests)

---

## 8. Tests Needed (X10.10B)

Estimated test count: 35 tests across 8 classes. See Q11 for full list.

Test infrastructure required: same `_DbBase` pattern as `test_post_lane10_lane_x10_9_freshness_gate.py`. Use `apply_migrations`, `_insert_token`, `_insert_pair`, `_insert_source_request`, `_insert_source_response`, `_insert_discovery_candidate`.

No new test infrastructure needed — X10.10B tests are a smaller version of X5's test pattern with TRACK_NORMAL-specific constants.

---

## 9. Files Changed (Audit Only — Zero Changes)

| File | Status |
|---|---|
| `docs/printer-v1-lane-x10-10a-mixed-lane-15m-memory-growth-audit.md` | CREATED (this file) |

No code files were modified. No tests were run. No DB was written. No source calls were made.

---

## 10. Final Verdicts

```
MIXED_LANE_MEMORY_GROWTH_NEEDED:       YES
  Reason: TRACK_NORMAL tokens produce zero 15m memory windows under current
          infrastructure. Anti-bias rules require failed tokens, traps, slow
          fades, revivals, and boring baseline tokens — all TRACK_NORMAL
          categories. Without TRACK_NORMAL memory, the memory factory learns
          only from fast-event tokens, violating the anti-bias spec.

IMPLEMENTATION_NOT_YET_DONE:           YES
  Reason: No bounded TRACK_NORMAL runner exists. No TRACK_NORMAL handler
          (E2H equivalent) exists. TRACK_NORMAL_FIRST_15M job kind is defined
          in contracts and infrastructure but has no execution path.

RECOMMENDED_NEXT_LANE:                 LANE_X10_10B
  Scope: New module lane_e2h_normal_first_15m_handler.py +
         lane_x10_10_normal_15m_runner.py + CLI command + test suite.
         No changes to X5, E2H, X10.9, X10.6, or X6.
         No DB migrations required.
         Estimated: 4 new files, 1-2 modified (commands.py, pyproject.toml).

LOCKS_PRESERVED:                       YES
  All V1 locks carry over unchanged. TRACK_NORMAL runner uses same gate
  architecture as X5. No new capabilities unlocked. No financial locks
  relaxed. No retrieval activation. No scoring or ranking. No live trading.
  No paper decisions. WINDOW_15M only.

implementation_blocker:                TRACK_NORMAL_FIRST_15M_HANDLER_MISSING
  The E2H handler equivalent for TRACK_NORMAL does not exist. This is the
  critical missing piece. Must be built before the runner can function.

migration_required:                    NO
  All DB tables needed already exist. E2O already allows TRACK_NORMAL.
  Snapshot recorder and lifecycle queue already map TRACK_NORMAL correctly.

freshness_policy_for_track_normal:     ADVISORY_ONLY_NO_HARD_BLOCK
  Preferred threshold: 300s. Advisory threshold: 600s. FRESHNESS_UNKNOWN
  is advisory, not a blocker. TRACK_NORMAL staleness never blocks the run.

source_budget_sharing:                 SHARED_GOVERNOR_NO_BYPASS
  TRACK_FAST and TRACK_NORMAL share the Source Governor. TRACK_FAST has
  priority. Concurrent runs are not recommended (schedule sequentially).

winner_bias_severity:                  HIGH
  Current TRACK_FAST-only memory is pure selection bias. Unacceptable for
  a memory factory that must learn from all token outcomes, not just winners.

x10_10b_can_proceed:                   YES_READY_TO_IMPLEMENT
  All infrastructure is in place. Zero blockers once X10.10B implementation
  is authorized. Do not implement until operator authorizes X10.10B.
```
