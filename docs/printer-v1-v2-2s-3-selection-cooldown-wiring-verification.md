# Printer V1 V2-2S.3 Cross-Batch Selection Cooldown Wiring Verification

## 1. Status

Lane: `V2-2S.3 - Cross-Batch Selection Cooldown Wiring Verification`

Task type: independent verification only

Verdict: `VERIFICATION_PASS`

V2-2T, V2-2J, V2-3, and discovery persistence gate reform remain paused.

V2-2S.2 resolved both V2-2S.1 blockers. Token cooldown is now latest-row-safe
across multi-pair mints. A bounded `apply_selection_cooldown_gates()` wiring
helper is implemented, correctly ordered, and covered by focused tests.
No downstream capability was unlocked.

## 2. Source Stack and Anchors

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-v2-2r-discovery-fair-chance-selection-rotation-design.md`
- `docs/printer-v1-v2-2s-cross-batch-selection-cooldown-implementation.md`
- `docs/printer-v1-v2-2s-2-selection-cooldown-wiring-repair.md`

Anchors confirmed:

- V2-2R design: `a1257a0`
- V2-2S implementation: `22d0e51`
- V2-2S.2 repair: `8914697`

## 3. Files Inspected

- `src/printer_v1/discovery/selection_batch.py` — V2-2S.2 diff and function bodies
- `tests/test_v2_2s_selection_cooldown.py` — complete test file including new classes
- `docs/printer-v1-v2-2s-2-selection-cooldown-wiring-repair.md`
- V2-2S.2 commit scope and diff (`git show 8914697`)

## 4. Latest-Token-State Verification

### 4.1 MAX() query confirmed present

`check_token_selection_cooldown()` at line 1588 (post-repair) executes:

```python
row = conn.execute(
    "SELECT MAX(last_selected_batch_seq) FROM printer_selection_rotation_state WHERE token_mint = ?",
    (token_mint,),
).fetchone()
```

`MAX()` returns the single largest `last_selected_batch_seq` across all
`(token_mint, pair_address)` rows for the mint. SQLite's `MAX()` on an empty
result set returns a single row with `NULL`; the existing `row[0] is None`
guard handles that case correctly.

### 4.2 Old unordered query removed

The pre-repair query `SELECT last_selected_batch_seq ... WHERE token_mint = ?`
without `ORDER BY` or `MAX` is no longer present. `git show 8914697` confirms
the only change to `check_token_selection_cooldown()` is the addition of the
`MAX()` aggregate and a three-line explanatory comment.

### 4.3 Pair cooldown remains pair-specific

`check_pair_selection_cooldown()` is unchanged from V2-2S. It queries:

```sql
SELECT last_selected_batch_seq
FROM printer_selection_rotation_state
WHERE pair_address = ?
ORDER BY last_selected_batch_seq DESC
LIMIT 1
```

This is keyed on `pair_address` only. A token on a new pair with no history
for that pair address passes the pair check regardless of what other pairs have
recorded. Token and pair cooldowns are independent as required.

### 4.4 Multi-pair scenario proof (static)

Given:
- MINT_A selected on PAIR_A at batch seq 1 → row: `(MINT_A, PAIR_A, seq=1)`
- MINT_A selected on PAIR_B at batch seq 5 → row: `(MINT_A, PAIR_B, seq=5)`

At current batch seq 6:

- Old query: could return either row; if it returned the PAIR_A row, `batches_since = 6-1 = 5`, `5 < 3` is False → incorrectly allowed.
- New query: `MAX(last_selected_batch_seq)` = 5 regardless of row order; `batches_since = 6-5 = 1`, `1 < 3` → correctly blocked.

`TestMultiPairTokenCooldownLatestRow` in the test suite exercises this exact scenario
and passes, confirming the static analysis.

Latest-token-state verdict: **PASS**.

## 5. Cooldown-Gate Helper Verification

### 5.1 `apply_selection_cooldown_gates()` structure

The function:

1. Opens or reuses a DB connection via `_connect()` with own-connection tracking.
2. Iterates once over the candidates list.
3. For each candidate:
   - Calls `check_token_selection_cooldown(conn, token_mint, current_batch_seq, cooldown_window=cooldown_window)`.
   - If `ok_token` is False: appends `{**candidate, "item_status": ITEM_STATUS_REJECTED, "rejection_reason": token_reason}` to rejected; `continue`.
   - Calls `check_pair_selection_cooldown(conn, pair_address, current_batch_seq, cooldown_window=cooldown_window)`.
   - If `ok_pair` is False: appends `{**candidate, "item_status": ITEM_STATUS_REJECTED, "rejection_reason": pair_reason}` to rejected; `continue`.
   - Otherwise: appends candidate (unmodified) to eligible.
4. Closes connection if own_connection.
5. Returns `(eligible, rejected)`.

### 5.2 Ordering confirmed

Token cooldown is called before pair cooldown per candidate. A token blocked at
the token level skips the pair check (`continue` after the token block). This
is the V2-2R Section 9.1 ordering.

### 5.3 Eligible candidates unmodified

Eligible candidates reach `eligible.append(candidate)` unmodified. No extra
keys are injected on the eligible path. `test_eligible_candidate_unmodified`
verifies this.

### 5.4 Rejected candidates have correct shape

Rejected candidates receive `item_status=ITEM_STATUS_REJECTED` and
`rejection_reason` set to either `REJECTION_TOKEN_SELECTION_COOLDOWN`
(`"TOKEN_SELECTION_COOLDOWN"`) or `REJECTION_PAIR_SELECTION_COOLDOWN`
(`"PAIR_SELECTION_COOLDOWN"`). Both are string constants. No numeric score,
rank, or float appears on any rejected candidate.

### 5.5 Cooldown-rejected candidates do not enter rotation state

`record_selection_rotation_state()` filters to `ITEM_STATUS_SELECTED` items
only. A candidate that is ITEM_STATUS_REJECTED with a cooldown reason is not
persisted as selected. `test_rejected_cooldown_candidate_does_not_enter_selected_items`
verifies: after gating and persisting, `selected_count=0` and the
`last_selected_batch_id` in the rotation-state row is still from the prior seed,
not the current batch.

Cooldown-gate helper verdict: **PASS**.

## 6. Commit Scope Verification

`git show 8914697` shows three changed files:

| File | Type | Assessment |
|---|---|---|
| `docs/printer-v1-v2-2s-2-selection-cooldown-wiring-repair.md` | Doc | Repair report only |
| `src/printer_v1/discovery/selection_batch.py` | Source | 1 query change + new function only |
| `tests/test_v2_2s_selection_cooldown.py` | Test | Import + 2 new test classes only |

The diff for `selection_batch.py` contains no removed lines except the old
`SELECT last_selected_batch_seq` query line. All other production code additions
are the `apply_selection_cooldown_gates()` function body.

No migration, memory-window, retrieval, paper-decision, position, trade, audit,
PnL, or scheduler file was touched.

Commit scope verdict: **PASS**.

## 7. Tests and Checks

### Executed

| Test suite | Result |
|---|---|
| `tests/test_v2_2s_selection_cooldown.py` | **80 passed** |
| `tests/test_v2_2c_selection_batch.py` | **120 passed** |
| `tests/test_v2_2p_pair_age_context.py` | **67 passed** |
| `tests/test_v2_2m_audit_only_handoff.py` | **95 passed** |
| `tests/test_post_rc_controlled_discovery_cycle.py` | **8 passed** |
| **Total** | **370 passed** |

### V2-2S.2 new test coverage summary

`TestMultiPairTokenCooldownLatestRow` (5 tests):

| Test | Proof |
|---|---|
| `test_latest_pair_row_controls_token_cooldown` | seq 6 blocked from seq 5, not seq 1 |
| `test_old_pair_row_does_not_allow_too_early` | newer row at seq 4 blocks at seq 6 |
| `test_allowed_only_when_latest_seq_clears_window` | allowed at seq 8 from seq 5 (window=3) |
| `test_single_pair_row_still_works` | single-pair path unchanged |
| `test_pair_cooldown_still_pair_specific_with_multi_rows` | PAIR_A cleared, PAIR_B blocked |

`TestApplySelectionCooldownGates` (14 tests):

| Test | Proof |
|---|---|
| `test_no_prior_state_all_eligible` | fresh candidates all pass |
| `test_token_cooldown_rejects_candidate` | token block → TOKEN_SELECTION_COOLDOWN |
| `test_pair_cooldown_rejects_candidate` | pair block → PAIR_SELECTION_COOLDOWN |
| `test_token_cooldown_checked_before_pair` | token fires first when both blocked |
| `test_candidate_passes_after_cooldown_window` | eligible after window expires |
| `test_rejected_candidate_has_correct_item_status` | item_status=REJECTED |
| `test_eligible_candidate_unmodified` | no extra keys injected |
| `test_mixed_batch_splits_correctly` | 1 blocked + 1 fresh → correct split |
| `test_empty_candidates_returns_empty_lists` | empty input → empty output |
| `test_rejected_cooldown_candidate_does_not_enter_selected_items` | selected_count=0 after persist |
| `test_no_paper_decisions_created` | no paper_decisions rows |
| `test_no_token_tracking_rows_created` | no printer_tokens rows |
| `test_returns_tuple_of_two_lists` | return type verified |
| `test_new_pair_for_same_mint_blocked_by_token_cooldown` | new pair does not bypass token cooldown |

### Git checks

- `git diff --check`: no output (no whitespace errors; LF→CRLF is a git config warning, not an error)
- `git status --short`: no modified tracked files in working tree
- `git diff --stat`: no output (clean working tree)
- `git diff --name-only`: no output (clean working tree)

## 8. Safety Confirmations

Static diff inspection of V2-2S.2 commit (`8914697`) confirms:

- No source-fetching path changed.
- No discovery persistence reform added.
- No scheduler or runtime path changed.
- No memory or memory-window path changed.
- No retrieval path changed.
- No paper-decision path changed.
- No BUY/SELL/HOLD path changed.
- No position, trade, audit, or PnL path changed.
- No scoring, ranking, confidence, or weighted logic introduced.
- No embeddings or vectors introduced.
- No assignment from `pair_age_seconds` to `token_age_seconds`.
- `derive_age_bucket()` function body is unchanged.
- `assign_bucket()` function body is unchanged; A3 gate (`_tok_age_known`) is untouched.
- `derive_recent_active_tier()` function body is unchanged.
- `classify_same_token_new_pair()` unchanged.
- `check_cooldown_archive_gate()` unchanged.
- `check_watch_only_promotion_gate()` unchanged.
- `filter_within_response_duplicates()` unchanged.
- `record_selection_rotation_state()` unchanged.
- `persist_selection_batch()` unchanged.
- `compute_evidence_identity_fingerprint()` unchanged.
- `fingerprint_change_is_meaningful()` unchanged.
- `token_age_evidence_tier` remains `None` — no T1/T2/T3 source activated.

All downstream V1 capabilities remain locked.

## 9. Remaining Blockers

1. `token_age_seconds` remains unavailable; no T1/T2/T3 source is approved or
   activated. A3 and recent-active tiers remain inaccessible.
2. `apply_selection_cooldown_gates()` is a callable helper. No live runtime or
   scheduler calls it (no live runtime exists in paper-trading-only scope).
3. Evidence-freshness meaningful-change waiver (V2-2R Rule 5) is implemented
   as helpers but not enforced as a selection-path policy.
4. Source/category exposure rotation (V2-2R Rules 3/4/6) is not implemented.
5. V2-2J, V2-3, V2-2Q remain paused.
6. Discovery persistence gate reform remains paused.

## 10. Verification Verdict

`VERIFICATION_PASS`

Both V2-2S.1 blockers verified resolved:

1. `check_token_selection_cooldown()` uses `MAX(last_selected_batch_seq)` and
   cannot read a stale older pair row for a multi-pair mint.
2. `apply_selection_cooldown_gates()` is implemented, wires token then pair
   cooldown in the correct V2-2R Section 9.1 order, returns eligible candidates
   unmodified and rejected candidates with categorical rejection reasons, and
   prevents cooldown-rejected candidates from entering selected items or updating
   rotation state.

All 370 tests pass. No downstream capability was unlocked.

## 11. Whether V2-2T Proof Is Allowed

**V2-2T is allowed.**

Prerequisites satisfied:

- V2-2S migration, persistence, fingerprint, and nominal cooldown behavior: verified (V2-2S.1)
- Token latest-row safety and bounded selection gate path: verified (this lane)
- All 370 tests passing
- No forbidden downstream capability activated

V2-2T should prove cross-batch enforcement using `apply_selection_cooldown_gates()`
against a fixture DB. V2-2J, V2-3, and discovery persistence gate reform remain
paused and must not be folded into V2-2T.
