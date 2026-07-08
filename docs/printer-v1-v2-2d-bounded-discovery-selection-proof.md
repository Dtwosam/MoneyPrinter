# Printer V1 — V2-2D Bounded Discovery/Selection Proof

**Status:** PROOF COMPLETE

**Date:** 2026-07-08

**Lane:** V2-2D — Bounded discovery/selection proof

**Prerequisites satisfied:**

- V2-2C committed at `b0ca1b5 Implement V2-2C discovery selection repairs`
- V2-2D STNP preflight committed at `9f557e1 Add V2-2D same-token new-pair preflight`

---

## 1. Boundary Confirmation

This proof is bounded to existing DB rows only. No live sources were fetched.

**Allowed in this proof:**

- Read-only inspection of live DB
- Isolated proof DB mutation (`data/printer_v1_v2_2d_proof.sqlite3` only)
- Running V2-2C `selection_batch` module on existing discovery candidates
- Writing selection batch rows to proof DB

**Not allowed (confirmed not used):**

- Source fetching or Source Governor calls for new data
- Central Scheduler invocation
- Memory window creation
- Retrieval activation
- Paper decisions
- BUY/SELL/HOLD
- Positions, trade events, paper trade audits, PnL
- Scoring/ranking/confidence/weighted logic
- Embeddings/vectors
- Live wallet/private keys/real funds/live execution
- Live DB mutation

---

## 2. Proof Isolation

| Item | Value |
|------|-------|
| Live DB (read-only) | `data/printer_v1.sqlite3` |
| Proof DB (write target) | `data/printer_v1_v2_2d_proof.sqlite3` |
| Proof DB backup | `data/printer_v1_v2_2d_proof.sqlite3.bak` |
| Live DB size | 13,017,088 bytes |
| Proof DB size after copy | 13,017,088 bytes (byte-for-byte match) |
| Migration 025 applied to proof DB | Yes (before proof run) |
| Live DB written | **No** |

Live DB access: `sqlite3.connect('file:data/printer_v1.sqlite3?mode=ro', uri=True)` +
`PRAGMA query_only = ON`.

---

## 3. Proof Script

Script: `scripts/v2_2d_selection_batch_proof.py`

The script:

1. Opens live DB in read-only mode
2. Opens proof DB in read-write mode
3. Records locked table row counts (before)
4. Reads all 15 discovery candidates from live DB
5. Applies individual gates per V2-2C: STNP exclusion, cooldown/archive gate, WATCH_ONLY promotion gate
6. Assigns bucket, asset class, and selection/rejection reasons
7. Runs A1 quota screening (quota rule: Group A present requires trap/failure counterpart)
8. Builds selected and rejected item lists
9. Validates final quota with `validate_batch_quota()`
10. Persists batch and items to proof DB with `persist_selection_batch()`
11. Records locked table row counts (after) and verifies zero deltas

---

## 4. STNP Preflight Exclusions Applied

Per the V2-2D STNP preflight (`docs/printer-v1-v2-2d-stnp-classification-preflight.md`):

| token_id | Token | Pairs | V2-2D action |
|----------|-------|-------|--------------|
| 7 | BONK | pair 7 | MAY INCLUDE (pair_id 7 only) |
| 7 | BONK | pairs 16, 17 | EXCLUDED (UNRESOLVED — data bug) |
| 12 | FARM | pair 12 | MAY INCLUDE (pair_id 12 only) |
| 12 | FARM | pair 18 | EXCLUDED (UNRESOLVED — data bug) |
| 13 | ANSEM | pairs 13, 14 | MUST EXCLUDE entirely |

**Effect on candidate pool:** Zero. None of the excluded tokens or pairs (token_id 13,
pair_ids 16/17/18) have any discovery candidates in `printer_discovery_candidates`.
The corrupted pairs entered the system outside the discovery pipeline and therefore
never produced candidates. The STNP exclusion logic in the proof script confirmed
the absence — the `EXCLUDED_TOKEN_IDS` and `EXCLUDED_PAIR_IDS` checks fired for zero
candidates.

This is consistent with V2-2D's input requirement: only governed discovery candidates
are eligible for selection.

---

## 5. Individual Gate Results

All 15 discovery candidates were loaded. Each passed through three individual gates
in order:

### 5.1 STNP exclusion gate

No candidates were flagged. All 15 candidates have `token_id not in {13}` and
`pair_id not in {16, 17, 18}`.

### 5.2 Cooldown/archive gate

No candidates were in COOLDOWN or ARCHIVED lifecycle state. All 15 have
`lifecycle_state` equal to their respective tracking action (TRACK_FAST,
TRACK_NORMAL, or WATCH_ONLY).

### 5.3 WATCH_ONLY promotion gate

Token_id 8 (WIF) has `discovery_action = WATCH_ONLY` and `tracking_lane = WATCH_ONLY`.
The promotion gate checks whether `tracking_lane in {TRACK_FAST, TRACK_NORMAL}` while
`discovery_action is WATCH_ONLY`. Since WIF's tracking lane is itself WATCH_ONLY, no
silent promotion is occurring. Gate passes.

No other candidates triggered the WATCH_ONLY promotion gate.

**Result: all 15 candidates passed all individual gates.**

---

## 6. Bucket Assignment Results

Bucket assignments use V2-2C `assign_bucket()`. All categorical — no scores or ranks.

| dc_id | token_id | pair_id | symbol | bucket | bucket_name | asset_class | tracking_lane |
|-------|----------|---------|--------|--------|-------------|-------------|---------------|
| 1 | 2 | 2 | PUMP | A1 | FAST_PUMP_FOLLOW | FAST_PUMP | TRACK_FAST |
| 2 | 3 | 3 | PUMP | D1 | DEAD_TOKEN | DEAD_TOKEN | TRACK_NORMAL |
| 3 | 4 | 4 | PUMP | D1 | DEAD_TOKEN | DEAD_TOKEN | TRACK_NORMAL |
| 4 | 5 | 5 | PUMP | D1 | DEAD_TOKEN | DEAD_TOKEN | TRACK_NORMAL |
| 5 | 6 | 6 | PUMP | D1 | DEAD_TOKEN | DEAD_TOKEN | TRACK_NORMAL |
| 6 | 7 | 7 | Bonk | A1 | FAST_PUMP_FOLLOW | FAST_PUMP | TRACK_FAST |
| 7 | 8 | 8 | WIF | B5 | CONSOLIDATION | CONSOLIDATION | WATCH_ONLY |
| 8 | 9 | 9 | memecoins | B4 | TRANSACTION_DECAY | VOLUME_DECAYING | TRACK_NORMAL |
| 9 | 10 | 10 | — | A1 | FAST_PUMP_FOLLOW | FAST_PUMP | TRACK_FAST |
| 10 | 11 | 11 | — | A1 | FAST_PUMP_FOLLOW | FAST_PUMP | TRACK_FAST |
| 11 | 12 | 12 | FARM | A1 | FAST_PUMP_FOLLOW | FAST_PUMP | TRACK_FAST |
| 12 | 14 | 15 | PUMP | A1 | FAST_PUMP_FOLLOW | FAST_PUMP | TRACK_FAST |
| 13 | 15 | 19 | — | B5 | CONSOLIDATION | CONSOLIDATION | TRACK_NORMAL |
| 14 | 16 | 20 | — | B5 | CONSOLIDATION | CONSOLIDATION | TRACK_NORMAL |
| 15 | 17 | 21 | — | B3 | TRANSACTION_SPIKE | HOT_TRENDING_PAIR | TRACK_NORMAL |

**Bucket distribution:**

| Bucket | Count | Bucket name |
|--------|-------|-------------|
| A1 | 6 | FAST_PUMP_FOLLOW |
| B3 | 1 | TRANSACTION_SPIKE |
| B4 | 1 | TRANSACTION_DECAY |
| B5 | 3 | CONSOLIDATION |
| D1 | 4 | DEAD_TOKEN |

**Why 6 A1 and no A2/A3/A4:**

A2 requires `price_change_5m <= -20.0` with high liquidity. A3 requires
`token_age_seconds >= 3600` with a negative 1h price change. The normalized payloads
for most candidates do not include `price_change_5m` or `token_age_seconds` fields
(these were not captured at discovery time for dexscreener candidates, and geckoterminal
candidates also did not include them). With both fields defaulting to 0.0, no candidate
qualifies for A2 or A3. A4 (FAILED_PUMP) is not assigned by `assign_bucket()` directly
— it requires operator override. Therefore all 6 fast-tier candidates fell uniformly
into A1.

This is a data quality finding: the current discovery pipeline does not capture
`price_change_5m` or `token_age_seconds` in normalized payloads, preventing A2/A3
bucket assignment. This must be addressed before A1/A2/A3 differentiation can work
at discovery time.

---

## 7. Quota Screening and Batch Assembly

### 7.1 A1 quota screening

The V2-2B quota rule states: if Group A buckets are present in the batch, at least one
trap/failure bucket (A2/A3/A4) must also be present.

Pool scan: 6 A1 candidates, 0 A2/A3/A4 candidates. No trap counterpart exists anywhere
in the candidate pool.

**Ruling:** All 6 A1 candidates were rejected with `BATCH_QUOTA_EXCEEDED` and
`lane_rationale = "A1_NO_TRAP_COUNTERPART: pool has no A2/A3/A4 to satisfy
GROUP_A_PRESENT_BUT_NO_TRAP_FAILURE_BUCKET quota rule"`.

This is not an A1 cap violation (cap = 2). This is a quota-balance violation: including
any A1 without a trap counterpart would produce a winner-only bias in the batch.

### 7.2 Selected batch (9 items)

| token_id | pair_id | bucket | asset_class | lane | selection_reason |
|----------|---------|--------|-------------|------|-----------------|
| 3 | 3 | D1 | DEAD_TOKEN | TRACK_NORMAL | DEAD_TOKEN_PROTECTION_SAMPLE |
| 4 | 4 | D1 | DEAD_TOKEN | TRACK_NORMAL | DEAD_TOKEN_PROTECTION_SAMPLE |
| 5 | 5 | D1 | DEAD_TOKEN | TRACK_NORMAL | DEAD_TOKEN_PROTECTION_SAMPLE |
| 6 | 6 | D1 | DEAD_TOKEN | TRACK_NORMAL | DEAD_TOKEN_PROTECTION_SAMPLE |
| 8 | 8 | B5 | CONSOLIDATION | WATCH_ONLY | CONSOLIDATION_PATTERN |
| 9 | 9 | B4 | VOLUME_DECAYING | TRACK_NORMAL | VOLUME_DECAY_PATTERN |
| 15 | 19 | B5 | CONSOLIDATION | TRACK_NORMAL | CONSOLIDATION_PATTERN |
| 16 | 20 | B5 | CONSOLIDATION | TRACK_NORMAL | CONSOLIDATION_PATTERN |
| 17 | 21 | B3 | HOT_TRENDING_PAIR | TRACK_NORMAL | TRANSACTION_SPIKE_DETECTED |

### 7.3 Rejected batch (6 items)

| token_id | pair_id | bucket | lane | rejection_reason |
|----------|---------|--------|------|-----------------|
| 2 | 2 | A1 | TRACK_FAST | BATCH_QUOTA_EXCEEDED |
| 7 | 7 | A1 | TRACK_FAST | BATCH_QUOTA_EXCEEDED |
| 10 | 10 | A1 | TRACK_FAST | BATCH_QUOTA_EXCEEDED |
| 11 | 11 | A1 | TRACK_FAST | BATCH_QUOTA_EXCEEDED |
| 12 | 12 | A1 | TRACK_FAST | BATCH_QUOTA_EXCEEDED |
| 14 | 15 | A1 | TRACK_FAST | BATCH_QUOTA_EXCEEDED |

Note: token_id 7 (BONK, pair 7) and token_id 12 (FARM, pair 12) are among the
rejected items. Their exclusion is due to quota (A1 without trap counterpart), not due
to STNP. Both pairs have clean discovery trails and can be included once the pipeline
captures `price_change_5m`/`token_age_seconds` to enable A2/A3 differentiation.

---

## 8. Final Quota Validation

Called: `validate_batch_quota(selected_items, min_corpus_episodes=30)`

| Rule | Check | Result |
|------|-------|--------|
| No duplicate mints | 9 unique mints | PASS |
| No duplicate pairs | 9 unique pair addresses | PASS |
| A1 cap (≤2 if present) | 0 A1 in selected batch | PASS |
| Group A present → trap required | No Group A in batch | PASS (rule N/A) |
| n≥6: D1 required | D1 count = 4 | PASS |
| n≥6: WATCH_ONLY required | token_id 8 (WIF) is WATCH_ONLY | PASS |
| n≥6: Group B or D required | D1×4, B3×1, B4×1, B5×3 | PASS |
| Group F: corpus ≥10 episodes | No Group F in batch | PASS (rule N/A) |

**`validate_batch_quota()` result: PASS — zero violations.**

---

## 9. Batch Persistence

| Field | Value |
|-------|-------|
| batch_id | `v2_2d_proof_491c9f78d864` |
| batch_status | `ASSEMBLED` |
| window_kind | `WINDOW_15M` |
| candidate_pool_total | 15 |
| selected_count | 9 |
| rejected_count | 6 |
| unavailable_or_unclassified_count | 0 |
| operator_approved | 0 (proof only) |
| created_at | 2026-07-08 20:12:09 |

Persisted to proof DB only. Live DB was not written.

---

## 10. Row-Delta Lock Checks

Locked tables compared between live DB and proof DB after proof run:

| Table | Live count | Proof count | Delta | Status |
|-------|-----------|-------------|-------|--------|
| `printer_memory_windows` | 156 | 156 | 0 | CLEAN |
| `printer_paper_decisions` | 2 | 2 | 0 | CLEAN |
| `printer_paper_positions` | 0 | 0 | 0 | CLEAN |
| `printer_paper_trade_audits` | 0 | 0 | 0 | CLEAN |

Tables not present in live DB (confirmed no rows created):
- `printer_retrieval_matches` — table does not exist (no retrieval system active)
- `printer_trade_events` — table does not exist

Selection batch tables (proof DB only):

| Table | Before | After | Delta |
|-------|--------|-------|-------|
| `printer_selection_batches` | 0 | 1 | +1 |
| `printer_selection_batch_items` | 0 | 15 | +15 |

**All locked table deltas are zero. No memory windows, paper decisions, paper
positions, paper trade audits, retrieval matches, or trade events were created.**

---

## 11. Source Governor and Central Scheduler Boundary

| Boundary | Status |
|----------|--------|
| Source Governor | Not bypassed. No source calls were made. All data from existing DB rows. |
| Central Scheduler | Not invoked. No scheduler jobs were created or queried. |
| Live source fetching | Not performed. |
| Proof script runtime | Self-contained Python script reading existing DB rows only. |

---

## 12. Learning-Usefulness Assessment

The 9-item selected batch covers the following learning categories from the V2-2B
required learning targets:

| Learning target | Covered by |
|----------------|-----------|
| Dead tokens | D1 ×4 (tokens 3, 4, 5, 6) |
| Capital protection avoids | D1 ×4 |
| Volume decay | B4 ×1 (token 9, memecoins) |
| Transaction spike | B3 ×1 (token 17) |
| Consolidation pattern | B5 ×3 (tokens 8, 15, 16) |
| WATCH_ONLY behavior | B5 ×1 (token 8, WIF) |

**Learning categories not covered (gap):**

- Winners (A1) — excluded due to missing trap counterpart
- Wick-only pumps (A2) — no A2 in pool (missing `price_change_5m`)
- Late-buy traps (A3) — no A3 in pool (missing `token_age_seconds`)
- Failed pumps (A4) — no A4 in pool (requires operator override)
- Liquidity rising (C1) — no C1 in pool
- Liquidity falling (C2) — no C2 in pool
- Liquidity removed (C3) — no C3 in pool
- Revival (D2) — no D2 in pool
- Migration event (D3) — no migration-channel candidates in pool
- Suspicious safety (D4) — no safety-flagged candidates in pool
- Realistic exit evidence (E1) — deferred
- Unrealistic exit evidence (E2) — deferred
- Counterfactual avoids/waits (F1-F4) — corpus too small (30 episodes < 10 minimum for F group; actually 30 > 10, but none present)

The batch is learning-useful for capital protection and decay/consolidation patterns.
It is not learning-useful for pump/trap/wick differentiation until the pipeline captures
`price_change_5m` and `token_age_seconds` at discovery time.

---

## 13. Key Findings

### Finding 1: Proof assembly SUCCEEDS

Printer can assemble a safe 9-item batch from existing discovery candidates using
V2-2C gates and quota validation without scores, ranks, BUY logic, paper decisions,
memory generation, or financial rows.

### Finding 2: A1 candidates excluded by quota — root cause: missing market fields

All 6 fast-tier (TRACK_FAST) candidates fell into A1 because `price_change_5m` and
`token_age_seconds` are absent from their normalized payloads. Without these fields,
`assign_bucket()` cannot differentiate A1 (clean pump) from A2 (wick-only) or
A3 (late-buy trap). The quota rule then prevents A1 inclusion without a trap
counterpart. This blocks BONK (pair 7) and FARM (pair 12) — both confirmed real,
high-liquidity tokens — from this batch.

**This is not a V2-2C implementation bug. This is a data collection gap** that should
be addressed in V2-2E or a future discovery-pipeline repair.

### Finding 3: STNP exclusions had zero effect on candidate pool

The corrupted extra pairs (16, 17, 18) and ANSEM (token_id 13) never entered the
`printer_discovery_candidates` table. The STNP exclusion logic fired for zero rows.
This confirms the boundary: only governed discovery candidates can enter the selection
pool. The data quality bug (`base_token_mint = pair_address`) on uncontrolled pairs
naturally prevented them from appearing in the candidate pool.

### Finding 4: Locked table deltas are all zero

No memory windows, paper decisions, paper positions, paper trade audits, retrieval
matches, or trade events were created. The proof is fully isolated.

### Finding 5: WATCH_ONLY gate and quota requirement both satisfied

Token 8 (WIF) in WATCH_ONLY lane passed the WATCH_ONLY promotion gate (no silent
promotion) and satisfies the 6+ batch WATCH_ONLY requirement. This is the only
WATCH_ONLY token in the candidate pool.

---

## 14. Batch Diversity Notes

From `build_candidate_universe_summary()`:

```
pool_diversity_notes: []
```

The batch satisfies all diversity conditions checked by the summary builder:
- Not all selected items are A1 (no selected A1 at all)
- D1 count > 0 for 9-item batch ✓
- WATCH_ONLY count > 0 for 9-item batch ✓

---

## 15. Locks Preserved

- No DB rows were written to the live DB.
- No migrations were applied to the live DB.
- No discovery commands were executed.
- No source fetching was performed.
- No memory generation was triggered.
- No retrieval was activated.
- No paper decisions were created.
- No BUY/SELL/HOLD actions were taken.
- No paper positions, trade events, paper trade audits, or PnL were created.
- No scoring, ranking, confidence, or weighted logic was used.
- No embeddings or vectors were used.
- No live wallet, private keys, real funds, or live execution was used.
- Source Governor not bypassed.
- Central Scheduler not invoked.

---

## 16. Acceptance Gate

| Gate | Status | Notes |
|------|--------|-------|
| Proof uses isolated DB only | PASS | Proof DB is a copy; live DB read-only |
| No live DB mutation | PASS | All deltas zero |
| No memory windows created | PASS | Delta = 0 |
| No paper decisions created | PASS | Delta = 0 |
| No retrieval rows created | PASS | Table absent |
| No financial rows created | PASS | Positions, trade events, audits all zero |
| Selection batch persists reasons | PASS | `selection_reason` and `rejection_reason` populated for all 15 items |
| Quota validation passes | PASS | `validate_batch_quota()` returns (True, []) |
| No duplicate mints or pairs | PASS | All 9 mints and pairs are unique |
| WATCH_ONLY present (6+ batch) | PASS | Token 8 (WIF) is WATCH_ONLY |
| D1 present (6+ batch) | PASS | 4 D1 dead tokens included |
| Source Governor not bypassed | PASS | No source calls made |
| Central Scheduler not bypassed | PASS | No scheduler calls made |
| Useful tokens selected safely | PASS | Capital-protection and decay/consolidation coverage |

**V2-2D acceptance gate: PASS with noted gap (A1 exclusion due to missing discovery fields).**

---

## 17. Data Quality Gap for V2-2E

The proof revealed that `price_change_5m` and `token_age_seconds` are absent from
most normalized payloads in `printer_discovery_candidates`. This prevents:

- A2 (WICK_ONLY_PUMP) assignment at discovery time
- A3 (LATE_BUY_TRAP) assignment at discovery time
- Any batch that includes A1 fast-pump tokens (requires trap counterpart to satisfy quota)

Repair path: the discovery source parser should be extended to capture and store
`price_change_5m` and `token_age_seconds` in normalized payloads during source
response processing. This is a pipeline data-capture fix, not a selection logic fix.

This gap does not invalidate the V2-2D proof. The proof shows the selection system
works correctly given the available data. It shows where the pipeline must grow next.

---

## 18. Next Recommended Lane

**Next recommended lane: `V2-2E — Closeout report`**

V2-2D pre-conditions are fully satisfied:
- [x] V2-2C implemented and committed
- [x] STNP classification preflight completed and committed
- [x] Isolated proof DB assembled
- [x] V2-2C selection batch module exercised against real DB rows
- [x] Quota validation passed
- [x] Row-delta locks all zero
- [x] Proof report committed

Open items for V2-2E or future lanes:
- [ ] Discovery pipeline must capture `price_change_5m` and `token_age_seconds`
      to enable A2/A3 bucket differentiation
- [ ] `base_token_mint = pair_address` data ingestion bug must be diagnosed and
      repaired for pairs 16, 17, 18, 13, 14
- [ ] ANSEM (token_id 13) requires a clean re-discovery before any batch consideration
- [ ] Longer-term: selection batch should feed the tracking queue handoff automatically
      (V2-3/V2-4 work)
