# Printer V1 — V2-2E Discovery/Selection Foundation Closeout Report

**Status:** COMPLETE_WITH_BLOCKERS

**Date:** 2026-07-08

**Lane:** V2-2E — Discovery/selection foundation closeout

**Verdict:** V2-2 Discovery/Selection Foundation is closed. V2-3 may proceed as
design/specification only.

---

## 1. Lane Boundary

This document is a closeout and documentation lane only.

**Allowed in V2-2E:**

- Closeout documentation
- Existing artifact review
- Static checks
- Risk and blocker summary
- Next-lane readiness decision

**Not allowed in V2-2E:**

- Implementation
- Migrations
- DB mutation
- Discovery runs
- Source fetching
- Scheduler or runtime execution
- Memory generation
- Retrieval activation
- Paper decisions
- BUY/SELL/HOLD
- Positions, trade events, paper trade audits, PnL
- Scoring/ranking/confidence/weighted logic
- Embeddings/vectors

---

## 2. V2-2 Lane Summary

### 2.1 V2-2A — Audit result

**Commit:** `6d493a5 Add V2-2A discovery selection pipeline audit`

**Result:** AUDIT COMPLETE

Key findings from the audit:

- The base discovery pipeline is governed: `printer-discover-candidates-once` requires
  `--operator-approved`, enforces Solana chain, caps max candidates, uses Source
  Governor calls, and records source request/response/failure rows.
- All 15 discovery candidates in the live DB have a `source_response_id` linkage —
  no ungoverned candidates exist.
- The tracking queue handoff is structurally present: discovery actions
  (`TRACK_FAST`, `TRACK_NORMAL`, `WATCH_ONLY`) map to tracking lanes, lifecycle events
  are recorded, and scheduler job kinds exist for each lane.
- Dedup safeguards are active: `printer_tokens.token_mint` and
  `printer_pairs.pair_address` are unique-constrained. X6 has explicit mint/pair dedup.
- Same-token/new-pair cases existed in the DB (tokens 7, 12, 13 each had multiple
  pairs) but were not formally classified.
- Selection reasons existed in X6/X10.6 artifacts but were not persisted to a durable
  selection-batch table.
- No memory-diet bucket taxonomy, quota policy, or STNP classification contract
  existed at audit time.
- Locked tables all at zero or historical only: retrieval matches 0, paper positions 0,
  trade events 0, paper trade audits 0.

**Gaps identified and handed to V2-2B:**

- No durable selection-batch table.
- No V2 memory-diet quota policy.
- STNP behavior detected but unclassified.
- X6/X10.6 selection artifacts not integrated with a DB-backed selection contract.

### 2.2 V2-2B — Design result

**Commits:**

- `f9bc787 Add V2-2B memory diet selection design`
- `86b95d7 Fix V2-2B: token classification gate is V2-2D, not V2-2C`

**Result:** DESIGN COMPLETE

Key outputs:

- 20-bucket memory-diet taxonomy designed: Groups A (fast-event), B (normal-activity),
  C (liquidity), D (lifecycle), E (exit-evidence), F (counterfactual/deferred).
- Quota rules designed: A1 cap ≤ 2; Group A requires trap bucket (A2/A3/A4); 6+ item
  batch requires D1 + WATCH_ONLY + Group B or D; Group F gated on ≥10 corpus episodes;
  no duplicate mints/pairs.
- Selection and rejection reason taxonomy designed (22+ reason labels).
- STNP classifications designed: MIGRATION, REVIVAL, PAIR_DRIFT, DUPLICATE_RECYCLE,
  DISTINCT_EVIDENCE, UNRESOLVED. UNRESOLVED blocks batch entry.
- Cooldown/archive/reopen gate semantics designed.
- WATCH_ONLY promotion gate semantics designed (silent promotion blocked).
- V2-2B fix: moved STNP token-classification gate from V2-2C to V2-2D (correct
  sequencing — implementation should not classify STNP; that is a preflight task).

### 2.3 V2-2C — Implementation result

**Commit:** `b0ca1b5 Implement V2-2C discovery selection repairs`

**Result:** IMPLEMENTED AND TESTED

Key outputs:

- `migrations/025_selection_batch.sql`: Two new tables.
  - `printer_selection_batches`: batch header with status, window kind, counts,
    pool summary JSON, diversity/quality notes, operator approval.
  - `printer_selection_batch_items`: per-candidate row with primary bucket, bucket
    name, asset class, behavior context labels, selection/rejection reasons, tracking
    lane, lane rationale, source trace IDs, STNP fields, cooldown fields, metadata
    JSON.
- `src/printer_v1/discovery/selection_batch.py`: Full V2-2C module.
  - `assign_bucket()`: categorical bucket assignment, no scores.
  - `derive_asset_class()`: categorical asset-class tag.
  - `classify_same_token_new_pair()`: STNP gate.
  - `check_cooldown_archive_gate()`: lifecycle state gate.
  - `check_watch_only_promotion_gate()`: silent promotion guard.
  - `validate_batch_quota()`: quota rule enforcement.
  - `build_candidate_universe_summary()`: pool-level summary with diversity/quality notes.
  - `extract_candidate_metadata()`: market-structure metadata extraction.
  - `build_batch_item()`: item dict builder from candidate + gate results.
  - `persist_selection_batch()`: DB persistence to `printer_selection_batches` and
    `printer_selection_batch_items`.
- `tests/test_v2_2c_selection_batch.py`: 112 unit tests across 15 test classes.
  Covers all bucket assignments, asset class derivation, behavior context labels,
  STNP gate, cooldown/archive gate, WATCH_ONLY promotion gate, quota validation,
  reason persistence, candidate metadata extraction, candidate universe summary,
  batch persistence, no-score/no-rank checks, no-financial-side-effects checks,
  no-memory-window checks, and migration 025.

### 2.4 V2-2D STNP preflight — Result

**Commit:** `9f557e1 Add V2-2D same-token new-pair preflight`

**Result:** PREFLIGHT COMPLETE — read-only classification

Key findings:

- token_id 7 (BONK), pair_ids 16 and 17: UNRESOLVED. Both extra pairs have
  `base_token_mint = pair_address` (data ingestion bug). No discovery candidates.
  Original pair 7 is clean and approved for inclusion.
- token_id 12 (FARM), pair_id 18: UNRESOLVED. Same data ingestion bug. No discovery
  candidate. Original pair 12 is clean and approved for inclusion.
- token_id 13 (ANSEM), pair_ids 13 and 14: UNRESOLVED. Both pairs have the
  `base_token_mint = pair_address` bug. Neither pair has a discovery candidate. 29
  memory windows exist across both pairs but all are DIRTY or PARTIAL with most
  flagged `MISSING_CRITICAL_DATA` and `do_not_train = 1`. ANSEM must be excluded
  entirely from V2-2D-style batches.
- Root cause: pairs 13, 14, 16, 17, and 18 were created outside the governed
  discovery pipeline. The parser that writes `base_token_mint` was not applied.

### 2.5 V2-2D bounded proof — Result

**Commit:** `58c2049 Add V2-2D bounded discovery selection proof`

**Result:** PROOF COMPLETE — QUOTA PASS — DATA GAP FOUND

Key outputs:

- `scripts/v2_2d_selection_batch_proof.py`: Isolated proof script.
- `data/printer_v1_v2_2d_proof.sqlite3`: Isolated proof DB (not committed).
- Proof DB is a byte-for-byte copy of the live DB at proof time, with migration 025
  applied. Live DB was opened read-only only.

Proof results:

- Candidate universe: 15 discovery candidates loaded from live DB (read-only).
- STNP exclusions effect: zero. No excluded token/pair had a discovery candidate.
- All 15 candidates passed individual gates: STNP gate, cooldown/archive gate, WATCH_ONLY promotion gate.
- Bucket assignment: 6 A1, 4 D1, 3 B5, 1 B4, 1 B3. Zero A2/A3/A4.
- Quota screening: 6 A1 candidates rejected with `BATCH_QUOTA_EXCEEDED` because no
  A2/A3/A4 counterpart existed in the pool.
- Final selected batch: 9 items — D1×4, B5×3, B4×1, B3×1. `validate_batch_quota()`
  returned PASS with zero violations.
- All locked table deltas: zero (memory windows, paper decisions, paper positions,
  paper trade audits).
- Source Governor: not invoked. All data from existing DB rows.
- Central Scheduler: not invoked.

---

## 3. What Is Now Proven

| Capability | Proof status | Notes |
|-----------|-------------|-------|
| Candidate-universe visibility | PROVEN | 15 candidates read from DB; summary by source, channel, bucket, lane, asset class |
| Asset-class metadata | PROVEN | `derive_asset_class()` assigns categorical tags for all 20 buckets |
| Selection-batch persistence | PROVEN | V2-2D wrote 1 batch row + 15 item rows to isolated proof DB |
| Bucket assignment | PROVEN | 112 unit tests + proof run; all 5 bucket groups exercised |
| Quota validation | PROVEN | V2-2D batch passed `validate_batch_quota()` with zero violations |
| Duplicate mint/pair rejection | PROVEN | Quota validator blocks duplicate mints and pair addresses; tested |
| Unresolved STNP rejection | PROVEN | `classify_same_token_new_pair()` blocks UNRESOLVED; tested; STNP preflight applied |
| WATCH_ONLY promotion gate | PROVEN | `check_watch_only_promotion_gate()` blocks silent promotion; tested; WIF passed correctly |
| Cooldown/archive/reopen gates | PROVEN | `check_cooldown_archive_gate()` tested; no cooldown/archived candidates in proof run |
| Isolated proof DB path | PROVEN | Proof DB copied from live, live DB never written |
| Locked table deltas stayed zero | PROVEN | memory_windows, paper_decisions, paper_positions, paper_trade_audits all delta=0 |
| No memory unlock | PROVEN | No memory windows created |
| No retrieval unlock | PROVEN | Retrieval table absent; zero retrieval matches |
| No paper/financial unlock | PROVEN | Paper decisions, positions, trade events, audits all delta=0 |
| Selection reasons persist | PROVEN | `selection_reason` and `rejection_reason` populated for all 15 items |
| Rejection reasons persist | PROVEN | All 6 rejected A1 items have `BATCH_QUOTA_EXCEEDED` + `lane_rationale` |

---

## 4. What Is Only Partially Proven

**V2-2D used an isolated proof DB, not a live governed run.**

- V2-2D proved selection assembly from existing DB rows under V2-2C module logic.
- V2-2D did **not** invoke the Source Governor. No source requests were made. All data
  came from rows already in `printer_discovery_candidates` with their original
  normalized payloads.
- V2-2D did **not** invoke the Central Scheduler. No scheduler jobs were created or
  queried during the proof.
- V2-2D did **not** create memory windows. Selection proves intake only, not memory
  production.
- V2-2D did **not** prove one-command Memory Factory automation. The proof script is a
  standalone Python file, not an operator command.
- V2-2D did **not** prove live governed discovery feeding into a selection batch in a
  single end-to-end flow. The pipeline from Source Governor → discovery candidates →
  selection batch → tracking queue remains a manual assembly in proof form.

These are the open items handed to V2-3 and V2-4.

---

## 5. Key Blocker — Missing Discovery Fields

The V2-2D proof found that `price_change_5m` and `token_age_seconds` are absent from
most normalized payloads in `printer_discovery_candidates`.

**Effect:**

- `assign_bucket()` relies on `price_change_5m` to fire A2 (WICK_ONLY_PUMP):
  `price_change_5m <= -20.0 AND volume_5m >= 1000`.
- `assign_bucket()` relies on `token_age_seconds` to fire A3 (LATE_BUY_TRAP):
  `token_age_seconds >= 3600 AND price_change_1h < 0`.
- With both fields absent (defaulting to 0.0), every fast-tier candidate falls into A1
  (FAST_PUMP_FOLLOW).
- The quota rule requires a trap/failure bucket (A2/A3/A4) whenever Group A is present.
- With no A2/A3/A4 in the pool, all A1 candidates are rejected.

**Candidates blocked by this gap in V2-2D:**

- token_id 2 (pair 2, PUMP/dexscreener) — A1 rejected
- token_id 7, pair 7 (BONK/dexscreener, $291k liquidity) — A1 rejected
- token_id 10, pair 10 (geckoterminal, $18k liquidity) — A1 rejected
- token_id 11, pair 11 (geckoterminal, $87k liquidity) — A1 rejected
- token_id 12, pair 12 (FARM/geckoterminal, $95k liquidity) — A1 rejected
- token_id 14, pair 15 (PUMP/dexscreener, $34k liquidity) — A1 rejected

BONK (pair 7) and FARM (pair 12) both have clean STNP status and clean discovery
trails. They cannot enter a balanced fast batch until either:

1. The discovery source parser is extended to capture `price_change_5m` and
   `token_age_seconds` from source responses and store them in the normalized payload.
2. Or a manual operator-approved A2/A3/A4 override is used for known wick/trap/failed
   candidates.

This is a **data collection gap**, not a V2-2C implementation bug. The selection logic
is correct. The pipeline upstream of selection must grow.

**Repair path:** Extend the discovery source parser (`parser.py`) to capture
`price_change_5m` and `token_age_seconds` from source API responses and include them in
`normalized_candidate_payload_json`. This is out of scope for V2-2 and should be
tracked in V2-3 or V2-4.

---

## 6. STNP Closeout

| token_id | Token | Pair | V2-2 decision | Condition |
|----------|-------|------|---------------|-----------|
| 7 | BONK | pair_id 7 | MAY INCLUDE in future batches | Clean discovery, no STNP classification needed |
| 7 | BONK | pair_ids 16, 17 | EXCLUDED | UNRESOLVED — base_token_mint = pair_address bug |
| 12 | FARM | pair_id 12 | MAY INCLUDE in future batches | Clean discovery, no STNP classification needed |
| 12 | FARM | pair_id 18 | EXCLUDED | UNRESOLVED — base_token_mint = pair_address bug |
| 13 | ANSEM | pair_ids 13, 14 | MUST EXCLUDE ENTIRELY | UNRESOLVED on both pairs; no discovery candidates; 29 memory windows all DIRTY/PARTIAL |

**Corrupted pairs that must not enter selection batches:**

pair_ids 13, 14, 16, 17, and 18 all share the `base_token_mint = pair_address`
data ingestion bug. These pairs must not enter any selection batch under the current
data state. Any future re-entry requires:

1. A corrected re-discovery that produces a clean `printer_discovery_candidates` row
   with valid `base_token_mint`.
2. An explicit STNP classification performed under a V2-2D-style preflight.
3. Operator approval.

**Root ingestion bug status:** The `base_token_mint = pair_address` bug is documented
in the V2-2D STNP preflight and this closeout. It has not been diagnosed or repaired in
V2-2. Repair is out of scope for V2-2 and must be tracked as a future lane task.

**ANSEM long-term status:** ANSEM (token_id 13) may eventually be re-discovered through
the governed pipeline with clean pair data. Until then, the 29 existing ANSEM memory
windows must not be used for retrieval or training, as the majority have
`do_not_train = 1` and no clean source trace.

---

## 7. Money-Usefulness Contribution

V2-2 advances Printer's money-usefulness goal in these ways:

**Reduces winner-only bias.** The V2-2B quota rules and V2-2D proof show that Printer
will reject a batch of pure TRACK_FAST winners if no trap/failure counterpart is
present. This is not a failure — it is the quota system working as designed to prevent
a corpus dominated by pump successes.

**Protects against corrupted pair drift.** The STNP preflight and classification gate
prevent corrupted extra pairs from BONK, FARM, and ANSEM from entering any selection
batch. Without V2-2's gates, these pairs could have produced dirty memory.

**Forces candidate-universe visibility.** V2-2C's `build_candidate_universe_summary()`
produces a per-source, per-channel, per-bucket, per-lane breakdown that the operator
can inspect. Selection is no longer a black box.

**Improves asset-class understanding.** Every selected and rejected candidate carries
an explicit `primary_bucket`, `bucket_name`, and `asset_class` label. The operator
can see why each candidate was categorized and why it was selected or rejected.

**Makes rejected candidates visible.** Every rejected candidate carries a specific
`rejection_reason`. The 6 A1 rejections in the V2-2D proof all carry
`BATCH_QUOTA_EXCEEDED` with a `lane_rationale` explaining the specific missing
counterpart. Rejected candidates are not silently discarded.

**Prevents fast tokens from entering without trap/failure evidence.** This is the most
important capital-protection contribution: Printer cannot select a batch of winners
without also selecting something that teaches traps or failures. This directly
improves future paper-decision quality by preventing the corpus from overfitting to
pump success.

**Improves the future memory diet before memory automation.** The V2-2D proof selected
a batch with 4 dead tokens (capital protection avoids), 3 consolidation patterns, 1
volume decay, and 1 transaction spike — a diverse starting diet even without fast-tier
tokens.

---

## 8. What V2-2 Does Not Unlock

V2-2 does not unlock:

- Discovery automation
- Source fetching or Source Governor calls for new data
- Memory generation or memory window creation
- Retrieval activation
- Paper decisions
- BUY/SELL/HOLD
- Paper positions
- Trade events
- Paper trade audits
- PnL
- Live trading
- Wallet/private keys
- Real funds
- Paid APIs
- Scoring/ranking/confidence/weighted logic
- Embeddings/vectors
- End-to-end one-command Memory Factory automation (that is V2-3/V2-4)
- Automatic discovery-to-memory pipeline (no live governed proof was run)

---

## 9. Functionality Risks / Setbacks / Efficiency Blockers

| Problem | Why it matters | Failure mode | Required mitigation | Status |
|---------|----------------|--------------|---------------------|--------|
| Missing `price_change_5m` in normalized payloads | Prevents A2 (WICK_ONLY_PUMP) bucket assignment | All fast-tier tokens fall into A1; A1 cannot be selected alone | Extend parser to capture `price_change_5m` from source responses | Open — tracked, not repaired in V2-2 |
| Missing `token_age_seconds` in normalized payloads | Prevents A3 (LATE_BUY_TRAP) bucket assignment | Same A1 over-classification problem | Extend parser to capture `token_age_seconds` | Open — tracked, not repaired in V2-2 |
| A1 over-classification | 6 of 6 fast-tier candidates fell into A1 in V2-2D proof | Cannot select BONK/FARM/other fast tokens until trap counterpart appears | Fix upstream data capture | Open |
| Cannot select fast-tier tokens without trap/failure counterpart | Quota rule designed to prevent winner-only bias | Selection batches will exclude all A1 until A2/A3/A4 enter pool | Either repair data capture or accept capital-protection-heavy batches initially | Known design tradeoff |
| Source Governor not invoked in V2-2D | V2-2D proof used existing DB rows only | Live governed discovery feeding selection is not yet proven end-to-end | V2-3/V2-4 must prove Source Governor path | Open — scoped to V2-3/V2-4 |
| Central Scheduler not invoked in V2-2D | V2-2D proof did not exercise scheduler | Scheduler-to-selection handoff not end-to-end proven | V2-3/V2-4 must prove Scheduler path | Open — scoped to V2-3/V2-4 |
| Corrupted extra pairs from old ingestion path | Pairs 13/14/16/17/18 have `base_token_mint = pair_address` | If re-discovered without fix, same bug repeats | Diagnose and repair ingestion path before re-discovering | Open — not repaired in V2-2 |
| ANSEM anomaly: 29 memory windows, zero discovery candidates | All ANSEM windows are DIRTY/PARTIAL with MISSING_CRITICAL_DATA | Existing windows may be confused with valid training data | Confirm `do_not_train = 1` on all ANSEM windows; do not use for retrieval or training | Documented; open repair |
| Candidate universe still small (15 candidates) | Small pool limits batch diversity | Future batches may be narrow by source/channel | Grow pool through governed discovery over time | Known; long-term open |
| Selected V2-2D batch is WATCH_ONLY/dead-token heavy | Protective but incomplete for fast-move learning | Corpus may over-represent capital protection, under-represent fast-event lessons | Fix parser fields to unlock A2/A3/A4; grow pool | Downstream of parser fix |

---

## 10. Readiness Verdict

**V2-2 Discovery/Selection Foundation: `COMPLETE_WITH_BLOCKERS`**

V2-2 is complete because:

- V2-2A audit is committed and closed.
- V2-2B design is committed and closed.
- V2-2C implementation is committed with 112 tests passing.
- V2-2D STNP preflight is committed and closed.
- V2-2D bounded proof is committed, quota passes, all locked-table deltas are zero.

V2-2 has blockers that must be addressed before V2-4/V2-5 can produce diverse fast-tier
candidate batches:

1. `price_change_5m` and `token_age_seconds` must be captured in normalized payloads
   before A2/A3/A4 bucket differentiation works at discovery time.
2. The `base_token_mint = pair_address` data ingestion bug must be diagnosed and
   repaired before corrupted pairs can be re-used.
3. ANSEM (token_id 13) must be re-discovered through the governed pipeline before it
   can enter any batch.

**V2-3 may proceed as design/specification only.** V2-3 is architecture design for the
One-Command Memory Factory — no runtime, no DB mutation, no source fetching.

**V2-4/V2-5 implementation and proof must account for the missing `price_change_5m`
and `token_age_seconds` issue** before expecting fast-tier diversity in selection
batches.

**Any future live governed discovery proof must use Source Governor and Central
Scheduler boundaries.** The V2-2D proof established the selection logic. V2-4/V2-5
must prove the full pipeline from source call through candidate ingestion through
selection batch through tracking queue, using the governed paths.

---

## 11. Acceptance Checklist

| Gate | Status |
|------|--------|
| V2-2A audit committed | PASS — `6d493a5` |
| V2-2B design committed | PASS — `f9bc787`, `86b95d7` |
| V2-2C implementation committed | PASS — `b0ca1b5` |
| V2-2C tests pass (112 tests) | PASS |
| V2-2D STNP preflight committed | PASS — `9f557e1` |
| V2-2D proof committed | PASS — `58c2049` |
| V2-2D quota validation passes | PASS |
| V2-2D locked-table deltas zero | PASS |
| Selection reasons persist to DB | PASS |
| Rejection reasons persist to DB | PASS |
| No memory/retrieval/paper/financial unlock | PASS |
| Source Governor not bypassed | PASS |
| Central Scheduler not bypassed | PASS |
| STNP exclusions documented and applied | PASS |
| Missing field blockers documented | PASS |
| Corrupted pair ingestion bug documented | PASS |
| ANSEM anomaly documented | PASS |

---

## 12. Next Recommended Lane

**Next recommended lane: `V2-3 — One-Command Memory Factory Automation Design`**

V2-3 is **design-only**. It must not implement runtime, run discovery, fetch sources,
mutate the DB, or produce memory. V2-3 defines the architecture for the operator
command path:

```
operator starts one command
-> discovery/selection
-> tracking queue
-> scheduler jobs
-> Source Governor calls
-> snapshots
-> WINDOW_15M memory windows
-> clean/dirty audit
-> report
-> safe stop
```

V2-3 sub-lanes are all design and documentation:

- V2-3A: Audit fragmented current commands (static review only)
- V2-3B: Design orchestration (design doc only)
- V2-3C: Define DB safety rules (design doc only)
- V2-3D: Define stops/budgets/report contract (design doc only)
- V2-3E: Closeout design report (docs only)

V2-3 must not touch runtime. Implementation comes in V2-4.

---

## 13. Locks Preserved

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
- Source Governor was not bypassed in any V2-2 sub-lane.
- Central Scheduler was not bypassed in any V2-2 sub-lane.
