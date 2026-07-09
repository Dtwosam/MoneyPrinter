# Printer V1 V2-2S.2 Selection Cooldown Wiring Repair

## 1. Repair Verdict

`REPAIR_COMPLETE_WITH_BLOCKERS`

Both V2-2S.1 blockers are resolved:

1. Token cooldown now selects the latest batch seq across all pair rows for a mint.
2. A bounded selection-path wiring helper (`apply_selection_cooldown_gates()`) is implemented and tested.

V2-2T, V2-2J, V2-3, and discovery persistence gate reform remain paused.

## 2. Executor

Claude Sonnet 4.6 — paper-trading-only, Solana-only system.

## 3. Source Anchors

- V2-2R design: `a1257a0`
- V2-2S implementation: `22d0e51`
- V2-2S.1 verification verdict: `VERIFICATION_PARTIAL_WITH_BLOCKER`

## 4. Files Changed

| File | Change |
|---|---|
| `src/printer_v1/discovery/selection_batch.py` | Fix `check_token_selection_cooldown()` query; add `apply_selection_cooldown_gates()` |
| `tests/test_v2_2s_selection_cooldown.py` | Add `apply_selection_cooldown_gates` import; add `TestMultiPairTokenCooldownLatestRow` and `TestApplySelectionCooldownGates` test classes (19 new tests) |
| `docs/printer-v1-v2-2s-2-selection-cooldown-wiring-repair.md` | This document |

No migration, memory, retrieval, paper-decision, position, trade, audit, or
PnL file changed.

## 5. Exact Blocker Fixes

### Fix 1 — Token cooldown latest-row safety

**Before (V2-2S):**

```python
row = conn.execute(
    "SELECT last_selected_batch_seq FROM printer_selection_rotation_state WHERE token_mint = ?",
    (token_mint,),
).fetchone()
```

**After (V2-2S.2):**

```python
row = conn.execute(
    "SELECT MAX(last_selected_batch_seq) FROM printer_selection_rotation_state WHERE token_mint = ?",
    (token_mint,),
).fetchone()
```

`MAX()` returns the single largest `last_selected_batch_seq` across every pair
row for the mint, even when the mint appears in multiple rotation-state rows
with different `pair_address` values. Without `MAX()`, SQLite can return any
row (not necessarily the latest), allowing a multi-pair mint to bypass token
cooldown by evaluating against an older pair's sequence number.

`MAX()` on an empty result set returns a single row with `NULL`, so the
existing `row is None or row[0] is None` guard remains correct.

The pair helper (`check_pair_selection_cooldown()`) already uses
`ORDER BY last_selected_batch_seq DESC LIMIT 1` and is not changed.

### Fix 2 — Selection assembly wiring

**New function: `apply_selection_cooldown_gates(db_or_connection, candidates, current_batch_seq, *, cooldown_window=3) -> tuple[list, list]`**

Wires token and pair cooldown checks into the bounded selection assembly path
after existing STNP, lifecycle cooldown/archive, and WATCH_ONLY promotion gates
and before quota validation (V2-2R Section 9.1 ordering).

Behavior:

- Iterates over each candidate.
- Calls `check_token_selection_cooldown()` first per candidate.
- If token is blocked → appends to rejected list with `item_status=REJECTED` and `rejection_reason=TOKEN_SELECTION_COOLDOWN`; skips pair check.
- If token is not blocked → calls `check_pair_selection_cooldown()`.
- If pair is blocked → appends to rejected list with `rejection_reason=PAIR_SELECTION_COOLDOWN`.
- If both pass → appends to eligible list unmodified.
- Returns `(eligible_candidates, cooldown_rejected_candidates)`.

Does not call source fetching, memory generation, retrieval, paper decisions,
BUY/SELL/HOLD, positions, trades, audits, PnL, or any financial path.
Uses `_connect()` pattern with own-connection tracking.

## 6. Tests Run

### V2-2S focused suite (including V2-2S.2 additions)

```
tests/test_v2_2s_selection_cooldown.py — 80 passed
```

New test classes added:

**`TestMultiPairTokenCooldownLatestRow`** (5 tests):

| Test | What it proves |
|---|---|
| `test_latest_pair_row_controls_token_cooldown` | Mint on PAIR_A at seq 1, PAIR_B at seq 5: blocked at seq 6 using seq 5, not seq 1 |
| `test_old_pair_row_does_not_allow_too_early` | Seq-1 row cannot be used to allow when newer seq-4 row exists |
| `test_allowed_only_when_latest_seq_clears_window` | Allowed at seq 8 with latest at seq 5 (batches_since=3, window=3) |
| `test_single_pair_row_still_works` | Single-pair path still blocked correctly |
| `test_pair_cooldown_still_pair_specific_with_multi_rows` | Pair cooldown is pair-specific even with multi-pair mint |

**`TestApplySelectionCooldownGates`** (14 tests):

| Test | What it proves |
|---|---|
| `test_no_prior_state_all_eligible` | All candidates pass when no rotation state exists |
| `test_token_cooldown_rejects_candidate` | In-cooldown token is rejected with TOKEN_SELECTION_COOLDOWN |
| `test_pair_cooldown_rejects_candidate` | In-cooldown pair is rejected with PAIR_SELECTION_COOLDOWN |
| `test_token_cooldown_checked_before_pair` | Token check fires first when both are in cooldown |
| `test_candidate_passes_after_cooldown_window` | Eligible after window elapses |
| `test_rejected_candidate_has_correct_item_status` | Rejected dict has item_status=REJECTED |
| `test_eligible_candidate_unmodified` | No extra keys injected on eligible candidates |
| `test_mixed_batch_splits_correctly` | One blocked + one fresh → split correctly |
| `test_empty_candidates_returns_empty_lists` | Empty input returns empty lists |
| `test_rejected_cooldown_candidate_does_not_enter_selected_items` | Rejected cooldown candidate → selected_count=0 after persist; rotation state not updated |
| `test_no_paper_decisions_created` | No paper_decisions rows created |
| `test_no_token_tracking_rows_created` | No printer_tokens rows created |
| `test_returns_tuple_of_two_lists` | Return type is `tuple[list, list]` |
| `test_new_pair_for_same_mint_blocked_by_token_cooldown` | Mint on new pair is still blocked by token cooldown |

### Regression suites

| Test suite | Result |
|---|---|
| `tests/test_v2_2s_selection_cooldown.py` | **80 passed** |
| `tests/test_v2_2c_selection_batch.py` | **120 passed** |
| `tests/test_v2_2p_pair_age_context.py` | **67 passed** |
| `tests/test_v2_2m_audit_only_handoff.py` | **95 passed** |
| `tests/test_post_rc_controlled_discovery_cycle.py` | **8 passed** |
| **Total** | **370 passed** |

## 7. Git Checks

- `git diff --check`: LF→CRLF line-ending warning only. No whitespace errors.
- `git status --short`: 2 modified files (intended)
- `git diff --name-only`: `src/printer_v1/discovery/selection_batch.py`, `tests/test_v2_2s_selection_cooldown.py`
- No unintended staged changes.

## 8. Safety Confirmations

- No source-fetching path changed.
- No discovery persistence reform added.
- No scheduler/runtime path changed.
- No memory or memory-window path changed.
- No retrieval path changed.
- No paper decision path changed.
- No BUY/SELL/HOLD path changed.
- No position, trade, audit, or PnL path changed.
- No scoring, ranking, confidence, or weighted logic introduced.
- No embeddings or vectors introduced.
- `pair_age_seconds` not written to `token_age_seconds`.
- `derive_age_bucket()` still reads token age only.
- A3 gate (`_tok_age_known`) not touched.
- `token_age_evidence_tier` remains `None`.
- WATCH_ONLY promotion gate not touched.
- Existing STNP, lifecycle, and WATCH_ONLY gate functions not modified.
- Evidence fingerprint functions not modified.
- `record_selection_rotation_state()` not modified.
- `persist_selection_batch()` not modified.

## 9. Remaining Blockers

1. `token_age_seconds` unavailable until a T1/T2/T3 source is separately
   approved and activated. A3 and recent-active tiers remain inaccessible.
2. `apply_selection_cooldown_gates()` is a callable helper; it is not called
   by any live runtime or scheduler (no live runtime exists in
   paper-trading-only scope).
3. Evidence-freshness meaningful-change waiver behavior (V2-2R Rule 5) is
   implemented as helpers but not yet enforced as a selection-path policy.
4. Source/category exposure rotation (V2-2R Rules 3/4/6) is not implemented.
5. V2-2J, V2-3, V2-2Q, V2-2T remain paused.
6. Discovery persistence gate reform remains paused.

## 10. Whether V2-2S.3 Verification Is Allowed

**V2-2S.3 is allowed.**

Both V2-2S.1 blockers are resolved:

- Token cooldown now reads the latest state across all pair rows for a mint.
- A bounded `apply_selection_cooldown_gates()` path exists and is tested.

V2-2S.3 should verify:

- the MAX query fix;
- `apply_selection_cooldown_gates()` behavior;
- the 19 new focused tests;
- that no new downstream capability was unlocked.

V2-2T is not allowed until V2-2S.3 passes.
