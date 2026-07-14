# Printer V1 V2-6.3 — Continuous Lifecycle Runtime Integration Closeout

## Status

Verdict: `V2_6_3_CONTINUOUS_RUNTIME_INTEGRATION_PASS`

The V2-6.2 continuity contract is now wired into the live runtime paths — the
Lane X12 1h runner, the one-command memory factory, and continuation
scheduling/reporting — so the `5m -> 15m -> 1h` lifecycle is enforced at runtime,
not just available as a contract. Implement + verify only; no live sources were
run; V2-7 was not begun; no tag.

## Integration

### Lane X12 1h runner (`lane_x12_1h_runner`)

- **Planning seam** — new `plan_1h_continuation(token_entry)` delegates to the
  contract's `build_1h_continuation_plan`, so the continuation is enqueued at the
  **exact 15m close** and the deadline is fixed at **`15m close + 2700s`**. The
  deadline derives solely from the 15m close, so a delayed first snapshot (or
  delayed planning) can never extend it.
- **Token linkage** — token-list entries may carry an optional
  `continuation_of_15m` (the preceding closed 15m window: id, snapshot_end_id,
  closed_at, token/pair, lane, run). It is parsed into per-token state and a plan
  is computed at run start.
- **Close consumes the verdict** — `_run_x12_token_step` threads
  `continuation_of_15m` into `close_1h_memory_window_from_snapshot`, so the E2O
  close classifies the 15m->1h transition and:
  - **CLEAN** — creates the 1h window, `do_not_train = 0`, `window_start` anchored
    to the 15m close and `window_end` to `15m close + 2700s`;
  - **DIRTY** — creates the window with `do_not_train = 1` (`DIRTY_DATA`);
  - **BLOCKED** (delayed restart / reused historical window / target drift) —
    returns `E2O_1H_CONTINUITY_BLOCKED`; the runner **fails the job and creates no
    1h window**, recording the reason on the scheduler job.

### One-command factory (`one_command_15m_factory`)

Each per-token outcome for a closed 15m window now carries a **`continuation_plan`**
(from `build_1h_continuation_plan`): `enqueue_at` = the 15m close, `deadline_at` =
`15m close + 2700s`. This is the factory's continuation scheduling/reporting seam.

### Cadence (carried from V2-6.2)

The runner's 1h-phase default interval already derives from the authoritative
policy (FAST 120s / NORMAL 240s), so the collection cadence cannot drift.

## Verify

`tests/test_v2_6_3_continuous_runtime_integration.py` — **8 passed**. Fixtures and
temporary DBs only.

| Requirement | Test |
|---|---|
| live planning path calls `build_1h_continuation_plan` | `TestPlanningPath.test_planning_calls_build_plan_and_anchors_deadline` |
| enqueue at exact 15m close; deadline = close + 2700s | same + `TestFactoryContinuationReport` |
| delayed scheduling cannot extend the deadline | `test_delayed_scheduling_cannot_extend_deadline` |
| factory reports the continuation plan | `TestFactoryContinuationReport.test_per_token_outcome_includes_continuation_plan` |
| first continuation snapshot obeys transition thresholds | `test_clean_continuation_creates_anchored_1h_window` (gap 60s → CLEAN, window anchored to close+2700s) |
| DIRTY forces `do_not_train` | `test_dirty_continuation_forces_do_not_train` (gap 210s → DIRTY, do_not_train=1) |
| BLOCKED prevents 1h window creation | `test_blocked_continuation_prevents_1h_window` (negative gap → 0 windows, job `CONTINUITY_BLOCKED`) |
| downstream locks unchanged | `test_downstream_locks_unchanged` (paper/position/trade/retrieval zero) |

Regression (all green): Lane X12 1h runner **99**; one-command V2-4 **15** / V2-5
**14**; E2O/E2Q 1h audit gate **19**; Lane Q **+** cadence continuity **+** V2-6.2
continuity **+** V2-6.3 integration bundle **169**; Lane K/E2Z pipeline **127**.

### Pass rationale

The live planning path calls the contract's `build_1h_continuation_plan`; the 1h
deadline is fixed at `15m close + 2700s` and cannot be extended by delayed
scheduling; the runner consumes the transition verdict before any quality
promotion (CLEAN creates an anchored window, DIRTY forces `do_not_train`, BLOCKED
creates no window); the factory reports the continuation plan; and all downstream
financial / retrieval locks stay zero. → `V2_6_3_CONTINUOUS_RUNTIME_INTEGRATION_PASS`.

## Follow-up (out of scope)

A persistently-BLOCKED continuation in the live runner re-attempts each cycle and
relies on the existing source-budget safe-stop to halt (bounded, but it does not
stop the token's tracking on the first block). A dedicated per-token "stop on
continuity block" is a runtime-hardening refinement for a later lane. Resolving
the actual preceding 15m window from the DB at runtime (rather than via the token
list `continuation_of_15m` linkage) is likewise a later integration step; the
contract and its consumption are proven here.
