# Printer V1 V2-6.2 — Continuous First-Hour Lifecycle Repair Closeout

## Status

Verdict: `V2_6_2_CONTINUOUS_LIFECYCLE_PASS`

One continuous lifecycle — `5m support -> 15m main window -> 1h continuation`
for the same run / token / pair / lane — is now enforced by a single
authoritative contract, wired into the 1h close path, and proven with fixtures
and temporary DBs. No live sources were run; V2-7 was not begun; no tag.

## Gate 1 — Audit

The continuity pieces existed but were not connected:

1. `cadence_policy.evaluate_transition_gap` (the 15m->1h transition classifier)
   was **orphaned** — defined but called by nothing.
2. `lane_e2o_1h_window_close` created each 1h window standalone, keyed by
   `(pair, WINDOW_1H, snapshot_start_id)`, deriving `window_end_at` from the
   closing snapshot's `captured_at`. There was **no** link to the preceding 15m
   window, **no** `15m close + 2700s` deadline anchoring, and **no** transition /
   reuse / restart check.
3. 5m->15m linkage existed only as a **read-only report** (`e2w_5m_linkage_report`,
   via `parent_window_id`); nothing enforced that the 5m support window uses the
   *first snapshots of the same 15m run*, the same run/token/pair/lane, or
   no-restart.
4. `lane_x12_1h_runner` hardcoded the 1h-phase snapshot interval at 240s (FAST) /
   720s (NORMAL) — **target drift** from the V2-6.1a contract (120s / 240s).
5. No single resolver tied run/token/pair/lane across the three stages.

## Gate 2 — Implement

### New authoritative contract — `src/printer_v1/snapshots/lifecycle_continuity.py`

Pure, fixture-testable evaluators plus a DB resolver. No DB mutation; no memory /
episode / retrieval / paper / position / PnL row is written or unlocked here.

- `compute_1h_continuation_deadline(fifteen_m_close_at)` — `close + 2700s`,
  anchored to the **15m close**, never to the first 1h snapshot.
- `build_1h_continuation_plan(fifteen_m)` — enqueues **immediately at the 15m
  close** with `deadline_at = 15m close + 2700s`.
- `evaluate_5m_to_15m_continuity(...)` — enforces same run/token/pair/lane; the
  5m window uses the *first snapshots of the same 15m run* (identical opening
  snapshot = no restart; 5m range is a prefix of the 15m range); the 15m close
  stays anchored to opening + 900s; the first post-5m gap is judged on the 15m
  cadence thresholds (CLEAN / DIRTY / BLOCKED).
- `evaluate_15m_to_1h_continuity(...)` — enforces same run/token/pair/lane; the
  1h continuation links the **exact fresh 15m window and its closing snapshot**;
  rejects historical / already-consumed window reuse; rejects deadline **target
  drift** (a deadline anchored to delayed-first-snapshot + 2700s); rejects an
  **interpolated** first snapshot; and classifies the transition gap with the
  approved FAST/NORMAL thresholds — a **negative gap (delayed restart disguised
  as continuation) is BLOCKED**. This wires in the previously-orphaned
  `evaluate_transition_gap`.
- `resolve_lifecycle_continuity(conn, run_id, token_id, pair_id, tracking_lane)`
  — read-only DB resolver that reads the 5m / 15m / 1h windows for the run and
  runs both evaluators, returning an overall verdict plus the consumable
  `do_not_train` / `can_be_quality_memory` flags.

Outcome discipline (consumed by E2Q / Lane Q / Lane K): CONTINUOUS may become
quality memory; **DIRTY forces `do_not_train`**; **BLOCKED cannot become quality
memory** at all.

### Wired into the 1h close — `lane_e2o_1h_window_close`

`close_1h_memory_window_from_snapshot` gained an additive, backward-compatible
`continuation_of_15m=` (and `consumed_15m_window_ids=`) parameter. When a
continuation is supplied it now:
- validates continuity via the new contract;
- **anchors `window_start_at = 15m close` and `window_end_at = 15m close + 2700s`**
  (not first-snapshot-derived);
- returns `E2O_1H_CONTINUITY_BLOCKED` (no window created) on a BLOCKED transition;
- writes `do_not_train = 1` + `DIRTY_DATA` on a DIRTY transition;
- embeds the continuity verdict in `supporting_context_json`.

With no continuation argument the behaviour is unchanged (the 19-test 1h audit
gate suite still passes).

### Target-drift fix — `lane_x12_1h_runner`

The 1h-phase default snapshot interval now **derives from the authoritative
policy** (`get_policy("WINDOW_1H", lane)` → FAST 120s, NORMAL 240s) instead of the
stale hardcoded 240s / 720s, so the runner can never drift from the contract.

## Gate 3 — Verify

`tests/test_v2_6_2_continuous_lifecycle.py` — **32 passed**. Fixtures and
temporary DBs only. Proves:

| Requirement | Test evidence |
|---|---|
| 1h deadline = 15m close + 2700s | `compute_1h_continuation_deadline`, plan `deadline_at` |
| continuation enqueues at 15m close | `build_1h_continuation_plan` `enqueue_at` |
| continuous 5m->15m linkage | `Test5mTo15mContinuity.test_clean` + DB resolver |
| 5m uses first snapshots / no restart | `test_restart_different_opening_snapshot_blocked`, `test_5m_range_not_prefix_blocked` |
| 15m close anchored to open + 900s | `test_15m_close_not_anchored_to_900s_blocked` |
| first post-5m gap on 15m thresholds | `test_first_post_5m_gap_dirty` / `_blocked` |
| continuous 15m->1h linkage | `Test15mTo1hContinuity.test_clean` + DB resolver |
| exact fresh window + closing snapshot | `test_wrong_linked_window_blocked`, `test_wrong_closing_snapshot_blocked` |
| clean / dirty / blocked transition thresholds | `test_clean`, `test_dirty_transition_gap`, `test_blocked_transition_gap`, `test_normal_lane_clean` |
| delayed restart rejected | `test_negative_gap_delayed_restart_blocked` |
| reused historical windows rejected | `test_reused_historical_window_blocked`, E2O `test_reused_window_blocked` |
| interpolation rejected | `test_interpolated_first_snapshot_blocked` |
| deadline target drift rejected | `test_deadline_target_drift_blocked` |
| clocks not reset | opening-snapshot identity checks; E2O anchors to 15m close |
| same run/token/pair/lane throughout | identity checks + `TestDbResolver` |
| E2O consumes continuity | `TestE2OContinuationWiring` (created/dirty/blocked, anchored end, do_not_train) |
| E2Q / Lane Q / Lane K consume result | `do_not_train` + `DIRTY_DATA` written to the row; BLOCKED never creates a window |
| downstream locks unchanged | `TestDownstreamLocks` (paper/position/trade tables zero-delta) |

Regression (no behaviour change elsewhere): 1h audit gate **19 passed**; Lane X12
1h runner **99 passed** (with the drift fix); V2-6.1 cadence continuity green.

### Pass rationale

Both linkages enforced for the same run/token/pair/lane; clean/dirty/blocked
transition thresholds correct; delayed restart and historical-window reuse and
interpolation and target drift all rejected; clocks are anchored (opening
snapshot preserved, 1h deadline = 15m close + 2700s); the continuity verdict is
consumed by the 1h close and flows to E2Q / Lane Q / Lane K via
`do_not_train` / `can_be_quality_memory`; all downstream financial / retrieval
locks stay zero-delta. → `V2_6_2_CONTINUOUS_LIFECYCLE_PASS`.

## Follow-up (out of scope)

The continuity contract is authoritative and consumed at the 1h close; wiring it
into the live `lane_x12_1h_runner` continuation-planning path (enqueue timing +
deadline) and into the one-command factory is a separate integration lane and was
not exercised here (no live run in this lane).
