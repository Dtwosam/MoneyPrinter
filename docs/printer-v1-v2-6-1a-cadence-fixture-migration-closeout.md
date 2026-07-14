# Printer V1 V2-6.1a — Cadence Contract Adoption & Fixture Migration Closeout

## Status

Verdict: `V2_6_1A_CADENCE_MIGRATION_PASS`

The approved shared cadence contract from V2-6.1 (which stopped at design because
migrating the fixture corpus was out of that lane's scope) is now fully adopted in
runtime code and the clean-15m-window fixture corpus is migrated to the new 16/9
cadence. All affected suites are green except a set of **pre-existing** failures
that fail identically at the V2-6.1 baseline (`d215f83`) and are unrelated to
cadence (documented below). Implement-and-verify only: no live sources, no 15m
proof, no V2-7, no tag.

## Contract adopted (single source of truth)

`src/printer_v1/snapshots/cadence_policy.py` is authoritative. Three-tier
count+gap classification (STRICT):

| Window          | Lane   | Nominal | Dirty above | Block above | Expected snaps |
|-----------------|--------|--------:|------------:|------------:|---------------:|
| 5m support      | FAST   |     30s |         45s |         60s |             11 |
| 5m support      | NORMAL |     60s |         90s |        120s |              6 |
| 15m             | FAST   |     60s |         90s |        120s |         **16** |
| 15m             | NORMAL |    120s |        180s |        240s |          **9** |
| 1h continuation | FAST   |    120s |        180s |        240s |             24 |
| 1h continuation | NORMAL |    240s |        360s |        480s |             13 |

`expected_snapshot_count = ceil(window_seconds / nominal_gap) + 1`. 5m is
support-only + disabled as a main window; 15m and genuine 1h continuation are
enabled; 4h/12h/24h disabled. CLEAN = count ≥ expected AND every gap ≤ dirty-above;
DIRTY = a gap in (dirty, block] OR count < expected with gaps ≤ block; BLOCKED =
gap > block, < 2 snaps, disabled/support-only, or unparseable boundaries.

## Runtime changes

- **`cadence_policy.py`** — the authoritative three-tier policy table + evaluator
  (`evaluate_cadence_policy`, `evaluate_transition_gap`, `expected_snapshot_count`),
  with `CADENCE_POLICY_DIRTY` and the 15m→1h transition constants.
- **`lane_q_15m_window_integrity_guard.py`** — DIRTY now also blocks clean
  promotion (`status in (BLOCKED, DIRTY)`), so a real-but-below-clean window can
  never be promoted clean.
- **`lane_u2_coverage_audit_persistence.py`** — DIRTY maps to
  `COVERAGE_STATE_BLOCKED`.
- **`one_command_15m_factory.py`** — runner schedules and budgets now derive from
  the shared policy: 15m FAST/NORMAL = 16/9 snapshots; ceilings 21 per token,
  65 run-wide, 51 scheduler rows (recompute automatically from the policy).

### Root-cause fix during migration (`get_policy` lane fallback)

An earlier V2-6.1a iteration added a last-resort `get_policy` fallback that
returned the first lane policy for **any** unmapped lane string. That force-fit the
generic lifecycle value `"TRACKING"` (used by Lane S / Lane Q's
`_get_token_tracking_lane`, and split-pair fixtures) onto the FAST policy, causing
synthetic 2-snapshot proof windows to be coverage-BLOCKED and regressing Lane S /
E2X / E2Y / Lane K. The fallback is now restricted to `tracking_lane is None`
only. This restores the behavior already documented in
`lane_u2_coverage_audit_persistence._derive_tracking_lane`
("`get_policy('WINDOW_15M', 'TRACKING')` returns None"). Mapped lanes
(`TRACK_FAST`/`TRACK_NORMAL`) and the 5m lane-less lookup are unaffected.

## Fixture migration

Every fixture representing a clean 15m window updated to 16/9 (no expected counts
weakened, no clean fixture turned dirty to pass):

- **Cadence policy** (`test_v2_6_1_snapshot_cadence_continuity.py`,
  `test_post_lane10_lane_u_cadence_policy.py`) — contract table, 3-tier
  classification, transition, 1h-enabled.
- **Lane U2** (`test_post_lane10_lane_u2_coverage_persistence.py`) — TrackFast
  actual/expected count 10→16 and gap audits 9→15; TrackNormal 5→9 / 4→8;
  Idempotency and TrackingLaneDerivation stale end-IDs fixed to span all 16 snaps
  (gap audits 9→15, expected 10→16); SplitPair4+2 gap audits 54→90.
- **1h runner** (`test_post_lane10_lane_x12_1h_runner.py`) — the stale WINDOW_1H
  policy assertions (min 8→24, gap 600→240, interval 240→120 FAST; min 3→13,
  gap 1800→480, interval 720→240 NORMAL). WINDOW_1H is enabled as a continuation
  window (still forbidden as a *main* collection window — the runner
  `disabled_collection_window_kinds` assertions correctly still hold).
- **V2-4 / V2-5 factory** (`test_v2_4_one_command_15m_factory.py`,
  `test_v2_5_multi_token_15m_conservative.py`) — 16/9 schedules, budgets ≤ 21/65/51.

Lane S 2-snapshot proof windows are intentionally coverage-exempt (token_status
`"TRACKING"` → policy None → UNKNOWN); they require no snapshot addition and remain
valid through Lane Q after the `get_policy` fix.

## Verification (focused → affected regression)

Run with the fix + migration in place:

| Suite | Result |
|-------|--------|
| cadence continuity + Lane U cadence policy + x12 1h + V2-4 + V2-5 | 255 passed |
| E2X + E2Y + Lane K/E2Z + E2J | 320 passed |
| X2 + X4 + X5 runners | 369 passed |
| Lane Q guard + Lane R/E2O + x12 1h + Lane U memory-factory | 332 passed |
| Lane U2 coverage persistence | 138 passed, 9 pre-existing failures |
| Lane S real-spaced 15m proof | 59 passed, 9 pre-existing failures |

Proven: clean fixtures meet the new count/gap rules; missed-count fixtures are
DIRTY; excessive-gap fixtures are BLOCKED; Lane Q and Lane U2 never promote DIRTY
coverage; runner budgets match the derived 16/9 · 21/65/51 values; retrieval /
financial hard-locks remain zero (asserted within the green suites).

## Pre-existing failures (NOT introduced by this lane)

18 tests fail identically at baseline `d215f83` (verified by stashing this lane's
changes and re-running). All share one root cause unrelated to cadence: they
assert that the E2Y **set gate** / group selection gates episode creation, but the
current Lane K pipeline (`lane_k_e2z_pipeline_wiring`, Step 4/5) treats the set
gate as **informational** and promotes each individually-eligible window via the
per-window E2Z gate. These are out of scope for a cadence-fixture migration and are
left unchanged:

- Lane U2 (9): `LaneKSplitPairTests` zero_e2z/clean/episodes;
  `LaneU2SplitPair4Plus2TrackFastTests` 4_2_zero_clean/episodes_via_lane_k;
  `LaneKCandidateCoverageFilterTests` 4_pass_2_blocked_zero_episodes/clean;
  `LaneKGroupSelectionPairTests` 6_1_episodes_created/in_db_is_6.
- Lane S (9): `LaneSLaneKFullFlowTests` (5), `LaneSLaneKIdempotencyTests` (3),
  `LaneSLaneKBlockedWindowsTests` e2y_gate_passed_with_five_candidates (1).

## Scope honored

Implement + verify only. No live sources, no bounded 15m regression proof, no V2-7,
no tag. Historical proof documents and observed historical budgets are unchanged.
One logical commit contains the four runtime files, the migrated fixtures, and this
closeout.
