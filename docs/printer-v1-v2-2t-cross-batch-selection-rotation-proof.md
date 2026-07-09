# Printer V1 V2-2T Cross-Batch Selection Rotation Proof

## 1. Status

Lane: `V2-2T - Cross-Batch Selection Rotation Proof`

Task type: bounded proof using isolated fixture DB

Verdict: `PROOF_PASS`

All 6 required proof scenarios pass (36/36 proof checks). No downstream
capability was unlocked. V2-2J, V2-3, and discovery persistence gate reform
remain paused.

## 2. Executor

Claude Sonnet 4.6 — paper-trading-only, Solana-only system.

## 3. Source Stack and Anchors

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-v2-2r-discovery-fair-chance-selection-rotation-design.md`
- `docs/printer-v1-v2-2s-cross-batch-selection-cooldown-implementation.md`
- `docs/printer-v1-v2-2s-2-selection-cooldown-wiring-repair.md`
- `docs/printer-v1-v2-2s-3-selection-cooldown-wiring-verification.md`

Anchors confirmed:

- V2-2R design: `a1257a0`
- V2-2S implementation: `22d0e51`
- V2-2S.2 repair: `8914697`
- V2-2S.3 verification: `0870307`

## 4. Proof DB

```
data/printer_v1_v2_2t_cross_batch_selection_rotation_proof.sqlite3
```

**Fixture / live distinction:**

- All proofs run against the isolated proof DB only.
- The proof DB is created fresh each run by deleting any existing file and
  re-applying all migrations.
- The persistent live DB (`data/printer_v1.sqlite3`) is never touched.
  Row-delta check at Proof 6 confirmed the live DB still exists.

**Migrations applied to proof DB:**

All 26 migration files applied via `apply_migrations()` from
`src/printer_v1/db/migrate.py` (sorted alphabetical glob `*.sql`).
This includes migration `026_selection_rotation_state.sql` which creates
`printer_selection_rotation_state`.

**No source calls made:**

No source-fetching path was invoked. `printer_source_requests`,
`printer_source_responses`, and `printer_source_failures` all have 0 rows.

## 5. Proof Results

### 5.1 Token Cooldown Proof

**Scenario:** MINT_X/PAIR_X selected in Batch 1 (seq=1). Check at batch seqs 2, 3, 4.

| Batch | seq | batches_since | Result | Check |
|---|---|---|---|---|
| 1 | 1 | — | SELECTED, rotation state created | `rotation_state_recorded=True` |
| 2 | 2 | 1 | BLOCKED: TOKEN_SELECTION_COOLDOWN | PASS |
| 3 | 3 | 2 | BLOCKED: TOKEN_SELECTION_COOLDOWN | PASS |
| 4 | 4 | 3 | ALLOWED (3 < 3 is False) | PASS |

Both `check_token_selection_cooldown()` and `apply_selection_cooldown_gates()`
verified at each batch.

**Token cooldown verdict: PASS** (7/7 checks).

### 5.2 Pair Cooldown Proof

**Scenario:** MINT_Y selected on PAIR_P (seq=2). Verify pair-specific behavior.

| Check | Result |
|---|---|
| PAIR_P blocked at seq 3 (batches_since=1) | PASS |
| PAIR_Q (new pair, no history) passes pair check at seq 3 | PASS |
| MINT_Y token cooldown still applies on PAIR_Q | PASS |
| `apply_selection_cooldown_gates()` blocks MINT_Y/PAIR_Q with TOKEN_SELECTION_COOLDOWN | PASS |
| PAIR_P allowed at seq 5 (batches_since=3, window=3, `3 < 3` is False) | PASS |

The strict less-than boundary (`batches_since < cooldown_window`) was confirmed:
at `batches_since == window`, the pair is allowed (not blocked).

**Pair cooldown verdict: PASS** (5/5 checks).

### 5.3 Multi-Pair Latest-Token-State Proof

**Scenario:** MINT_Z seeded on PAIR_A (seq=100) and PAIR_B (seq=105) via direct
rotation-state insertion.

| Check | Result |
|---|---|
| Two rotation rows exist (one per pair) | PASS |
| `MAX(last_selected_batch_seq)` = 105 (the latest) | PASS |
| Blocked at seq=106 (`batches_since = 1 < 3`, using MAX=105) | PASS |
| Without MAX, seq=100 row would give `batches_since = 6 >= 3` → incorrectly allowed | Confirmed |
| Allowed at seq=108 (`batches_since = 3`, `3 < 3` is False) | PASS |

**MAX() is necessary**: if the token cooldown query returned the PAIR_A row
(seq=100 instead of seq=105), `batches_since = 106 - 100 = 6 >= 3` would
incorrectly allow the token. `MAX()` returns 105 regardless of row order,
giving `batches_since = 1 < 3` → correctly blocked.

**Multi-pair latest-state verdict: PASS** (5/5 checks).

### 5.4 Rejected-Candidate Proof

**Scenario:** MINT_R selected in BATCH_R1 (seq=3). BATCH_R2 contains the
same candidate rejected by TOKEN_SELECTION_COOLDOWN.

| Check | Result |
|---|---|
| `apply_selection_cooldown_gates()` rejects at seq 4 with TOKEN_SELECTION_COOLDOWN | PASS |
| After BATCH_R2 persist: `last_selected_batch_seq` still = 3 (BATCH_R1) | PASS |
| `selection_count` not incremented (still 1) | PASS |
| `last_selected_batch_id` still = 'BATCH_R1' | PASS |
| BATCH_R2 contains 1 rejected item in `printer_selection_batch_items` | PASS |

Cooldown-rejected candidates are recorded in `printer_selection_batch_items`
with `item_status=REJECTED` but do NOT trigger a rotation-state upsert.
`record_selection_rotation_state()` filters to `ITEM_STATUS_SELECTED` items only.

**Rejected-candidate verdict: PASS** (5/5 checks).

### 5.5 Rotation-State Persistence Proof

**Scenario:** MINT_S/PAIR_S selected in BATCH_S1 (seq=5), then re-selected in
BATCH_S2 (seq=9) after 3 dummy batches advance the seq past the cooldown window.

| Check | Result |
|---|---|
| Rotation row created on first selection | PASS |
| `last_selected_batch_id` = 'BATCH_S1' | PASS |
| `last_selected_batch_seq` = 5 | PASS |
| `selection_count` = 1 | PASS |
| `last_evidence_fingerprint_json` persisted | PASS |
| Fingerprint is valid JSON with categorical fields only (no numeric scores) | PASS |
| `rotation_state_recorded=True` in batch persist result | PASS |
| Cooldown clear at seq=9 after 3 dummy batches (batches_since=4) | PASS |
| `selection_count` incremented to 2 after re-selection | PASS |
| `last_selected_batch_id` updated to 'BATCH_S2' | PASS |
| `last_selected_batch_seq` updated to 9 | PASS |
| `updated_at` advanced | PASS |

Fingerprint keys: `activity_bucket`, `pair_age_context_label`, `primary_bucket`,
`source_channel`. All values are string or None. No float, int, or weighted value.

**Rotation-state persistence verdict: PASS** (12/12 checks).

### 5.6 Row-Delta Lock Proof

**Forbidden tables — all must be 0 rows:**

| Table | Row count |
|---|---|
| `printer_memory_windows` | 0 |
| `printer_episodes` | 0 |
| `printer_episode_snapshots` | 0 |
| `printer_memory_fingerprints` | 0 |
| `printer_paper_decisions` | 0 |
| `printer_paper_positions` | 0 |
| `printer_paper_trade_events` | 0 |
| `printer_paper_trade_audits` | 0 |
| `printer_paper_decision_audits` | 0 |
| `printer_paper_audit_reports` | 0 |
| `printer_memory_retrieval_queries` | 0 |
| `printer_memory_retrieval_matches` | 0 |
| `printer_source_requests` | 0 |
| `printer_source_responses` | 0 |
| `printer_source_failures` | 0 |
| `printer_token_snapshots` | 0 |
| `printer_scheduler_jobs` | 0 |
| `printer_tokens` | 0 |
| `printer_pairs` | 0 |
| `printer_tracking_queue` | 0 |

**Allowed tables — proof writes here only:**

| Table | Row count |
|---|---|
| `printer_selection_batches` | 9 |
| `printer_selection_batch_items` | 9 |
| `printer_selection_rotation_state` | 6 |

Persistent DB (`data/printer_v1.sqlite3`): exists, unmodified.

No source call was made. No memory, retrieval, paper decision, position, trade,
audit, or PnL row was created.

**Row-delta lock verdict: PASS** (2/2 checks).

## 6. Proof DB Table Summary

| Table | Rows | Notes |
|---|---|---|
| `printer_selection_batches` | 9 | BATCH_X1, BATCH_Y_P, BATCH_R1, BATCH_R2, BATCH_S1, BATCH_DUMMY1/2/3, BATCH_S2 |
| `printer_selection_batch_items` | 9 | 1 item per batch |
| `printer_selection_rotation_state` | 6 | MINT_X/PAIR_X, MINT_Y/PAIR_P, MINT_Z/PAIR_A (seeded), MINT_Z/PAIR_B (seeded), MINT_R/PAIR_R, MINT_S/PAIR_S |

## 7. Tests and Checks

### Test suites

| Test suite | Result |
|---|---|
| `tests/test_v2_2s_selection_cooldown.py` | **80 passed** |
| `tests/test_v2_2c_selection_batch.py` | **120 passed** |
| `tests/test_v2_2p_pair_age_context.py` | **67 passed** |
| `tests/test_v2_2m_audit_only_handoff.py` | **95 passed** |
| `tests/test_post_rc_controlled_discovery_cycle.py` | **8 passed** |
| **Total** | **370 passed** |

### Git checks

- `git diff --check`: LF→CRLF line-ending warning only. No whitespace errors.
- `git status --short`: 1 new untracked file (`docs/` report only).
- `git diff --stat`: no modified tracked files.
- `git diff --name-only`: no modified tracked files.

## 8. Safety Confirmations

- No source-fetching path called.
- No discovery persistence reform added.
- No scheduler or runtime path changed.
- No memory or memory-window path changed.
- No retrieval path changed.
- No paper-decision path changed.
- No BUY/SELL/HOLD path changed.
- No position, trade, audit, or PnL path changed.
- No scoring, ranking, confidence, or weighted logic introduced.
- No embeddings or vectors introduced.
- `pair_age_seconds` not written to `token_age_seconds`.
- A3/age-gate/STNP/lifecycle/WATCH_ONLY functions unchanged (proof uses
  only `persist_selection_batch()`, `apply_selection_cooldown_gates()`,
  `check_token_selection_cooldown()`, `check_pair_selection_cooldown()`,
  `record_selection_rotation_state()`).
- `token_age_evidence_tier` remains `None` in all fixture candidates.
- Live DB untouched.
- Proof DB is in `data/` and not committed.

## 9. Remaining Blockers

1. `token_age_seconds` remains unavailable until a T1/T2/T3 source is separately
   approved and activated. A3 and recent-active tiers remain inaccessible.
2. `apply_selection_cooldown_gates()` is a callable helper. No live runtime or
   scheduler calls it (no live runtime exists in paper-trading-only scope).
3. Evidence-freshness meaningful-change waiver (V2-2R Rule 5) is implemented
   as helpers but not enforced as a selection-path policy.
4. Source/category exposure rotation (V2-2R Rules 3/4/6) is not implemented.
5. V2-2J, V2-3, V2-2Q remain paused.
6. Discovery persistence gate reform remains paused.

## 10. Proof Verdict

`PROOF_PASS`

All 6 proof scenarios passed (36/36 checks). All 370 regression tests pass.
No downstream capability was unlocked.

Cross-batch selection cooldown is proven to:

1. Block a token at batches 2 and 3 after selection; allow at batch 4.
2. Enforce pair-specific pair cooldown while correctly applying token cooldown
   even on new pairs for the same mint.
3. Use `MAX(last_selected_batch_seq)` to prevent multi-pair mints from being
   evaluated against stale older pair rows.
4. Prevent cooldown-rejected candidates from updating rotation state.
5. Persist and increment rotation state correctly on re-selection.
6. Create zero rows in memory, retrieval, paper, financial, or source tables.

## 11. Next Recommended Lane

The V2-2T proof closes the bounded cross-batch selection cooldown proof
requirement. The active V2 roadmap continues with:

- **V2-2E** — V2-2 Discovery/Selection Foundation closeout report (documents
  what V2-2A through V2-2T accomplished and what remains before V2-3).

V2-2J, V2-3, and discovery persistence gate reform remain paused and must
not be started without explicit operator instruction.
