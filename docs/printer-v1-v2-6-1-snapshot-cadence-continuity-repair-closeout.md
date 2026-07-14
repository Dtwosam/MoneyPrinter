# Printer V1 V2-6.1 Snapshot Cadence & 15m→1h Continuity Repair Closeout

## Status

Verdict: `V2_6_1_SNAPSHOT_CADENCE_REPAIR_PASS`

This closeout supersedes the interim `..._BLOCKED` status recorded when this lane
first stopped at Gate 2 (fixture migration was out of scope for the design lane).
The work then completed across three commits:

- **V2-6.1 (design, `d215f83`)** — Gate 1 audit and the authoritative contract
  (preserved in full below).
- **V2-6.1a (adoption + migration, `80f9ba2`)** — the contract is adopted in
  runtime code (`cadence_policy`, Lane Q, Lane U2, `one_command_15m_factory`), the
  clean-15m-window fixture corpus is migrated to 16/9, and the stale WINDOW_1H
  assertions are corrected. See
  `printer-v1-v2-6-1a-cadence-fixture-migration-closeout.md`.
- **V2-6.1b (this closeout)** — Gate-1 readiness re-confirmed, one bounded live
  `WINDOW_15M` proof run and inspected read-only, and V2-6.1 closed.

The persistent DB is byte-identical before and after the proof
(`97db9a15cc464d86137cbbb0dd0a4ef1880e9f4e231fb41e8b22ca09fb177fbb`, 13,017,088
bytes; 17 tokens / 1,012 snapshots / 156 windows / 53 episodes / 2 paper
decisions). The proof ran on an isolated PROOF_ONLY DB; no `WINDOW_1H` run was
started and V2-7 was not begun.

## Gate 2b — Bounded 15m cadence regression proof (V2-6.1b)

### Readiness (Gate 1 re-confirm)

156 focused cadence / V2-4 / V2-5 tests pass at `80f9ba2`. Confirmed from runtime:
FAST/NORMAL expected snapshots = 16 / 9; budgets derive as 21 per token, 65
run-wide, 51 scheduler rows; classification is honest (even-16 → PASS, a single
100s gap → DIRTY, 2 snaps @ 900s → BLOCKED); Lane Q and Lane U2 both block DIRTY
from clean promotion; the persistent-path guard rejects `data/printer_v1.sqlite3`
and the financial / paper / retrieval / window-15m-only locks stay engaged. The
18 baseline E2Y/Lane-K "set-gate gates episodes" failures are out of scope and are
not cadence regressions.

### The one bounded proof

`printer-run-one-command-15m-memory-factory --proof-mode --window-kind WINDOW_15M
--max-selected-tokens 2 --total-duration-seconds 1200` on an isolated PROOF_ONLY
DB. Run id `4859e93c-1bba-40ea-9180-6d8a96a0e738`; `run_status=COMPLETED`,
`stop_reason=COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED`. Discovery: geckoterminal,
eligible pool 31, selection seed `9654728248c84253f9aa1350d7549d2a`. Zero retries,
zero endpoint rotation, no code/threshold/token/budget change after start, exactly
one proof.

Both autonomously-selected tokens resolved to **TRACK_NORMAL** (expected 9), so
the live run exercised the NORMAL 9-cadence; the FAST 16-cadence is proven by the
Gate-1 tests and budget derivation (identical policy-derived mechanism) but was
not itself selected in this single autonomous run — disclosed as a scope limit,
not a defect.

| Token | Lane | Mint | Pair | Exp/Act snaps | Gaps (s) | Max gap | Missed | Cadence verdict | Evidence span | E2Q / outcome |
|-------|------|------|------|--------------:|----------|--------:|-------:|-----------------|--------------:|---------------|
| t2 | NORMAL | `25wNVfgrZSSSUATkAo7f3ABC428Rqj4EhmqtAgzFpump` | `6VQkgikXVdAMMm9PidwNHAKaMwo8Y1vAz2r1WdmftYzo` | 9 / 9 | 113.2, 113.1, 112.0, 112.4, 112.4, 112.5, 112.5, 116.3 | 116.3 | 0 | `CADENCE_POLICY_PASS` | 904.6s | audited → `DIRTY_MEMORY` (`MISSING_CRITICAL_DATA`) |
| t1 | NORMAL | `BZAmvoGH8P23mBtNpAx1sn8rxpvDyhxt6GWosLLLpump` | `4GrxC7S8PXSxfXunJgLTZNecjJfp7k1zKjz3hBGpFhJf` | 9 / 9 | 113.3, 113.4, 111.8, 112.4, 112.4, 112.5, 112.6, 118.9 | 118.9 | 0 | `CADENCE_POLICY_PASS` | 907.3s | audited → `DIRTY_MEMORY` (`MISSING_CRITICAL_DATA`) |

**Cadence is clean and honest.** Every gap (~112–119s) sits at the NORMAL nominal
112.5s spacing (900/8) with real-world jitter, all well below the 180s dirty
threshold; count is exactly 9/9 with 0 missed. Running the authoritative
`evaluate_cadence_policy` on the collected snapshots returns
`CADENCE_POLICY_PASS` for both windows. The **DIRTY** outcome is a separate,
honest data-completeness classification — E2Q flags `MISSING_CRITICAL_DATA`
(window-level `liquidity_usd`/`token_age_seconds` are `None` for these fresh
tokens even though each snapshot row is `CLEAN_DATA`/`COMPLETE`), so both windows
are `do_not_train=1` and withheld. A pass does not require clean memory.

### Context, safety, and pipeline stages

All 7 context roles captured and fresh (`chain_heat`, `chart_volatility`,
`liquidity_exit`, `market`, `micro_event`, `safety`, `trading_flow`;
`all_context_fresh_enough=true`, no blockers). Run steps: 16 SNAPSHOT + 2
WINDOW_CLOSE, all SUCCEEDED; E2Q audited both windows. The full safety /
entry-quote clean-promotion gate is an E2Z step that DIRTY windows never reach, so
no clean memory, episode, or Lane-K promotion occurred.

### Budgets, cleanup, replay, deltas

- **Governed budgets within ceilings:** per-token 14 (9 snapshot + 5 context) ≤ 21;
  run-wide 28 ≤ 65; scheduler rows 20 ≤ 51; discovery 2 ≤ 2; holder RPC fallbacks
  2 ≤ 2; automatic retries 0.
- **Terminal cleanup:** 0 pending/running run steps, 0 running jobs after stop,
  2 discovery handoffs cancelled.
- **Report-only replay** (`--report-only-run-id 4859e93c…`) reproduced
  `COMPLETED` with locks preserved and produced no writes.
- **Retrieval / financial deltas all zero:** retrieval queries 0, retrieval
  matches 0, paper decisions 0, paper positions 0, paper trade events 0, paper
  trade audits 0, paper audit reports 0. `locks_preserved` =
  {financial, paper_decisions_off, retrieval, window_15m_only} all true.
- **Yield:** clean 0 / dirty 2 / blocked 0 (`zero_clean_is_valid`).
- **Proof DB final:** sha256 `d458a97a41f57a639e2eff840262a64d0cd844346d509181ccf077c73a1dfda0`,
  18 snapshots / 2 windows / 0 episodes.

### Pass rationale

Correct 16/9 runtime cadence (NORMAL 9/9 live; FAST 16 unit-proven) ✓; honest
coverage classification (cadence PASS; DIRTY from a real data-completeness gate) ✓;
bounded execution (all budgets within ceilings, 0 retries/rotation, exactly one
proof) ✓; replay safety ✓; unchanged persistent DB (identical hash) ✓; zero
downstream activation (all forbidden deltas 0, locks preserved, 0 episodes) ✓.
Clean memory is explicitly not required. → `V2_6_1_SNAPSHOT_CADENCE_REPAIR_PASS`.

---

## Gate 1 — Audit and Design (V2-6.1, preserved)

### Conflicting cadence definitions found

1. `src/printer_v1/snapshots/cadence_policy.py` — the shared policy consumed by
   Lane Q, Lane U, Lane U2. 15m FAST nominal 90s / block 120s / min 10; NORMAL
   180s / 300s / 5. Two-tier only (pass/blocked); no middle "dirty" tier.
2. `one_command_15m_factory._schedule_offsets` — hardcoded 10 (FAST) / 6 (NORMAL)
   snapshots (~100s/150s spacing); the V2-4/V2-5 runner cadence.
3. Comments referencing `snapshots/frequency.py` cadences.

These three disagree on both spacing and count.

### Authoritative contract (single source of truth to adopt)

| Window          | Lane   | Nominal | Dirty above | Block above | Expected snapshots |
|-----------------|--------|--------:|------------:|------------:|-------------------:|
| 5m support      | FAST   |     30s |         45s |         60s |                 11 |
| 5m support      | NORMAL |     60s |         90s |        120s |                  6 |
| 15m             | FAST   |     60s |         90s |        120s |                 16 |
| 15m             | NORMAL |    120s |        180s |        240s |                  9 |
| 1h continuation | FAST   |    120s |        180s |        240s |                 24 |
| 1h continuation | NORMAL |    240s |        360s |        480s |                 13 |

Expected minimum schedule = `ceil(window_seconds / nominal_gap) + 1`
(300/900/2700s windows). Coverage classification (count + gap, strict, as
selected by the operator):

- **CLEAN** — count ≥ expected AND every gap ≤ dirty-above.
- **DIRTY** — a gap in (dirty-above, block-above], OR count < expected (missed
  snapshots) with all gaps ≤ block-above. Never clean; `do_not_train`.
- **BLOCKED** — a gap > block-above, too few snapshots to evaluate,
  disabled/support-only window, or unparseable boundaries.

15m→1h transition rule (gap from the 15m closing snapshot to the first 1h
continuation snapshot): FAST expected ≤120s, dirty >180s, block >240s; NORMAL
expected ≤240s, dirty >360s, block >480s. Continuity requires the exact
preceding 15m window, same token/pair, a linked closing snapshot, no
interpolation, and rejects a negative gap (delayed restart disguised as
continuation).

5m stays support-only; 4h/12h/24h stay disabled.

### Source / scheduler budget audit (bounded — no Gate-1 stop)

The closer cadence stays bounded with the approved free sources:

- 15m FAST = 16 snapshots + 5 close-context = 21 governed/token. A two-token 15m
  proof = 2 discovery + 2×21 = 44 governed, 2×16 + 2 = 34 scheduler rows, within
  the 1,200s cap.
- Three-token 15m worst case (FAST) = 2 + 3×21 = 65 governed, 3×16 + 3 = 51
  scheduler rows — the recalculated V2-5 ceilings (per-token 21, run 65,
  scheduler 51).
- 1h continuation FAST = 24 snapshots over 2,700s — finite and bounded.

No unbounded-cadence stop condition was triggered.

### Pre-existing baseline finding

Three cadence tests already fail on the committed V2-6 baseline
(`test_window_1h_track_fast_disabled`, `..._normal_disabled`,
`test_disabled_window_blocked`): they assert `WINDOW_1H` is disabled, but the
policy already enables it (X12/V2-6). A follow-up lane must correct these to the
enabled-1h contract.

## Gate 2 — Implement and Verify (V2-6.1 interim; superseded by V2-6.1a)

> Historical record of the design lane's first implementation attempt. The
> blocker below was resolved by the V2-6.1a migration (`80f9ba2`); the
> "now reverted" note applied only to the design lane and no longer holds.

The implementation was built exactly to the authoritative contract and verified
against its directly owned suites before the blocker was found. Implemented (and
now reverted pending a dedicated migration lane):

- `cadence_policy.py` rewritten as the single authoritative contract: three-tier
  thresholds, expected-count helper, `CADENCE_POLICY_DIRTY`, per-gap reporting
  (nominal, every actual gap, largest gap, missed snapshots), and
  `evaluate_transition_gap` for the 15m→1h rule. A lane fallback keeps
  `get_policy(kind, None)` resolving for lane-specific-only windows.
- `one_command_15m_factory`: `_schedule_offsets` and all hard budgets derive
  from the policy (16/9 snapshots; per-token 21, run 65, scheduler 51).
- Lane Q and Lane U2: DIRTY coverage blocks clean promotion (never promoted).

Verified green: the cadence-policy suite (updated to the new contract, 105
tests), a new `test_v2_6_1_snapshot_cadence_continuity.py` (26 tests — table,
three-tier classification, jitter, no-interpolation, transition rule, shared
contract), the V2-4 factory suite (15), and the V2-5 multi-token suite (14).

### The blocker

Under the **strict count** requirement (clean requires count ≥ expected), every
committed test that builds a "clean" 15m window at the previous cadence
(typically 10 snapshots at 90s, or 5 at 180s) now classifies **DIRTY** (count <
16 / 9) and is correctly withheld from clean promotion. This is the correct
behavior of the selected rule, but it breaks the clean-window fixtures across a
large committed corpus:

- **Confirmed:** `test_post_lane10_lane_u2_coverage_persistence.py` — 41 failures
  (coverage-pass, candidate-set, group-selection, episodes-created fixtures).
- **Confirmed partial:** ~11 further failures across
  `test_post_rc_lane_e2x_15m_clean_memory_eligibility`,
  `test_post_rc_lane_e2y_15m_candidate_set_gate`,
  `test_post_lane10_lane_s_real_spaced_15m_window_proof`, and
  `test_post_lane10_lane_k_e2z_pipeline_wiring`.
- **Not yet measured but structurally identical:** the two/three/five-token
  runner suites (`lane_x2`, `lane_x4`, `lane_x5`) and `lane_e2j`, which all build
  clean 15m windows at the old cadence.

Total blast radius is corpus-wide (estimated 60–100+ tests across a dozen-plus
suites), each requiring its fixtures rebuilt to 16-snapshot / 60s clean windows
(and 9 / 120s for NORMAL). This is a bounded, mechanical migration, but it is far
larger than V2-6.1's other gates and carries real error risk if rushed, so the
lane stops here rather than commit a broken corpus or a partial migration.

## Gate 3 — One bounded 15m regression proof

Not run. Gate 2 did not pass, and the lane stops at the first failed gate.
No `WINDOW_1H` was run. The persistent DB was not touched.

## Money Usefulness

The authoritative contract is the right foundation: one shared cadence source,
a real "dirty" middle tier so partial coverage produces honest dirty memory
instead of silently-clean or hard-blocked windows, per-gap and missed-snapshot
reporting, and a genuine 15m→1h continuity rule that rejects relabelled or
delayed-restart continuations. Adopting it improves the credibility of every
future clean memory. The strict-count choice raises the clean bar (16 evenly
spaced FAST snapshots), which is more truthful but requires the existing fixture
corpus to be rebuilt to that bar first.

## Recalculated Budgets (for the migration lane)

Per-token governed 21 (16 snapshots + 5 context); run-wide 65 (2 discovery +
3×21); scheduler rows 51 (3×16 + 3 handoffs); 1 holder RPC fallback/token; zero
retries; 1,200s cap. All derive from the cadence policy so they recompute if the
contract changes.

## Remaining Risks / Blockers

- Corpus-wide clean-window fixture migration (the primary blocker above).
- Three pre-existing 1h-disabled cadence-test failures must be corrected to the
  enabled-1h contract as part of the migration.
- The strict-count rule means any real run whose live sampling misses snapshots
  yields dirty (not clean) memory — expected and honest, but it lowers clean
  yield versus the old lenient count.

## Preserved Locks

Solana-only, memecoin-only, paper-only, `WINDOW_15M` main / 5m support-only,
4h/12h/24h disabled. No retrieval, paper decisions, BUY/SELL/HOLD, positions,
trades, audits, PnL, wallets, keys, funds, paid APIs, scoring/embeddings, Source
Governor or Central Scheduler bypass, or persistent-DB mutation. Nothing was
committed to production code; committed HEAD remains the green V2-6 state.

## V2-7 Readiness

**Not ready.** V2-7 must not start until V2-6.1 is completed: adopt the
authoritative cadence contract and migrate the clean-window fixture corpus to the
16/9-snapshot cadence (a dedicated migration lane), then run the bounded 15m
regression proof. Only after that green baseline should a 1h proof (V2-7) be
considered.

## Recommended Next Lane

`V2-6.1a — Cadence contract adoption + clean-window fixture migration`: land the
authoritative `cadence_policy.py` and factory/Lane-Q/Lane-U2 consumption, then
migrate every clean-15m-window fixture (u2, e2x, e2y, s, k, x2, x4, x5, e2j,
cadence) to 16/9-snapshot cadence and fix the three stale 1h-disabled tests, in
one focused pass with the full suite green, before the bounded 15m proof.
