# Printer V1 — V2-2D Same-Token/New-Pair Classification Preflight

**Status:** PREFLIGHT ONLY

**Date:** 2026-07-08

**Lane:** V2-2D preflight — same-token/new-pair classification required before bounded proof

**Prerequisite satisfied:** V2-2C committed at `b0ca1b5 Implement V2-2C discovery selection repairs`

---

## 1. Boundary Confirmation

This document is read-only and design-only.

**Allowed in this preflight:**

- Read-only DB inspection (`mode=ro`, `PRAGMA query_only = ON`, `SELECT` only)
- Existing document and artifact review
- Static inspection of code and migration files
- Classification reasoning and documentation

**Not allowed in this preflight:**

- DB mutation
- Migrations
- Source fetching
- Discovery runs
- Scheduler or runtime execution
- Memory generation
- Retrieval activation
- Paper decisions
- BUY/SELL/HOLD
- Positions, trades, paper trade audits, PnL
- Scoring/ranking/confidence/weighted logic
- Embeddings/vectors
- Live wallet/private keys/real funds/live execution

No data was written or mutated during this preflight.

---

## 2. Files and Artifacts Inspected

**Design documents:**

- `docs/printer-v1-v2-2a-discovery-selection-pipeline-audit.md`
- `docs/printer-v1-v2-2b-memory-diet-buckets-quotas-reasons-design.md`

**DB inspected (read-only):**

- `data/printer_v1.sqlite3`
- Access: `sqlite3.connect('file:data/printer_v1.sqlite3?mode=ro', uri=True)`
- Safety: `PRAGMA query_only = ON` applied before any query
- All queries: `SELECT` only

**Operator-run artifacts reviewed:**

- `operator-runs/manual-x10-9-fresh/x6-selection.20260707-215733.json`
- `operator-runs/manual-x10-9-fresh/x10-6-selection-batch.20260707-215733.json`

---

## 3. DB Tables Inspected

| Table | Reason |
|-------|--------|
| `printer_tokens` | Token mint and symbol for IDs 7, 12, 13 |
| `printer_pairs` | All pair addresses, timestamps, `base_token_mint`, `pool_source` |
| `printer_discovery_candidates` | Whether each pair went through the discovery pipeline |
| `printer_tracking_queue` | Whether each pair entered the tracking queue |
| `printer_token_lifecycle_events` | Lifecycle transitions for each pair |
| `printer_memory_windows` | How many windows exist per pair, memory_status, data_quality_label |
| `printer_source_responses` | Source response records for discovery candidates 6 and 11 |

---

## 4. Evidence Summary Per Token

### 4.1 token_id 7 — BONK (`DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263`)

**Token record:**

- symbol: `Bonk`, name: `Bonk`
- created_at: `2026-06-24`
- 3 pairs in DB: pair_id 7, 16, 17

**Pair detail:**

| pair_id | pair_address (truncated) | first_seen_at | last_seen_at | base_token_mint |
|---------|--------------------------|---------------|--------------|-----------------|
| 7 | `6oFWm7KP...cnsp` | 2026-06-24T16:01 | 2026-07-07T09:02 | `None` |
| 16 | `2hXcTGNf...yas` | 2026-07-06T21:56 | 2026-07-06T22:18 | `2hXcTGNf...yas` (= pair_address — DATA BUG) |
| 17 | `BrMYU1XW...Mj` | 2026-07-06T22:20 | 2026-07-06T22:42 | `BrMYU1XW...Mj` (= pair_address — DATA BUG) |

**Discovery pipeline state:**

| pair_id | Discovery candidate | Tracking queue | Lifecycle event | Source response |
|---------|---------------------|----------------|-----------------|-----------------|
| 7 | Yes (id=6, TRACK_FAST, dexscreener, sr_id=78) | Yes (id=6, QUEUED) | Yes (id=6, PROMOTE_TO_TRACK_FAST) | Yes (id=78, CLEAN_DATA) |
| 16 | **No** | **No** | **No** | Unknown |
| 17 | **No** | **No** | **No** | Unknown |

**Memory windows:**

| pair_id | Count | memory_status distribution |
|---------|-------|----------------------------|
| 7 | 26 | CLEAN_MEMORY×1, DIRTY_MEMORY×19, PARTIAL_MEMORY×5, AUDIT_ONLY×3 |
| 16 | 1 | PARTIAL_MEMORY×1 |
| 17 | 1 | DIRTY_MEMORY×1 |

**Original pair (pair_id 7):**
Normalized payload from source response 78 (dexscreener): liquidity_usd $291,186, volume_24h $588,217, volume_5m $9,778, txns_5m 67, txns_1h 487. High-activity large-cap token. Clean data. FDV ~$369M. Properly discovered through the full pipeline.

**Extra pairs (pair_id 16, 17):**
Both appeared during a single active session on 2026-07-06 (~22 minutes each, back-to-back). Both have `base_token_mint` set to their own pair_address, not the BONK mint (`DezXAZ8z...`). This is a data ingestion bug — the parser wrote the pair address into the `base_token_mint` column rather than the actual token mint. Neither pair has a discovery candidate, tracking queue entry, or lifecycle event.

---

### 4.2 token_id 12 — FARM (`yMJPZbnhoHib3ib8n8PfiVcp9yauk1vnaGKLx7epump`)

**Token record:**

- symbol: `None`, name: `FARM / SOL`
- created_at: `2026-06-25`
- Token mint suffix: `pump` (PumpFun-launched token)
- 2 pairs in DB: pair_id 12, 18

**Pair detail:**

| pair_id | pair_address (truncated) | first_seen_at | last_seen_at | base_token_mint | pool_source |
|---------|--------------------------|---------------|--------------|-----------------|-------------|
| 12 | `7G7hXmRv...zCBf` | 2026-06-17T14:25 (source capture) | 2026-06-17T14:25 | `yMJPZbn...pump` (CORRECT — actual token mint) | `geckoterminal` |
| 18 | `frxrS52r...4Dd` | 2026-07-07T08:25 | 2026-07-07T09:02 | `frxrS52r...4Dd` (= pair_address — DATA BUG) | `None` |

**Discovery pipeline state:**

| pair_id | Discovery candidate | Tracking queue | Lifecycle event | Source response |
|---------|---------------------|----------------|-----------------|-----------------|
| 12 | Yes (id=11, TRACK_FAST, geckoterminal TRENDING_POOL, sr_id=114) | Yes (id=11, QUEUED) | Yes (id=11, PROMOTE_TO_TRACK_FAST) | Yes (id=114, CLEAN_DATA) |
| 18 | **No** | **No** | **No** | Unknown |

**Memory windows:**

| pair_id | Count | memory_status distribution |
|---------|-------|----------------------------|
| 12 | 0 | (none — original pair was never cycled through memory factory) |
| 18 | 2 | PARTIAL_MEMORY×1, DIRTY_MEMORY×1 |

**Original pair (pair_id 12):**
Normalized payload from source response 114 (geckoterminal, TRENDING_POOL): liquidity_usd $95,417, volume_24h $548,857, volume_5m $4,628, txns_5m 46, txns_1h 203. Active high-liquidity pool. Source captured 2026-06-17; discovered locally 2026-06-25. `base_token_mint` correctly set to FARM's actual token mint. Clean discovery trail.

**Extra pair (pair_id 18):**
Appeared on 2026-07-07 (~37 minutes). `base_token_mint` = pair_address (same data ingestion bug as BONK extra pairs). No discovery candidate. Memory windows on pair 18 are PARTIAL and DIRTY — not CLEAN.

---

### 4.3 token_id 13 — ANSEM (`9cRCn9rGT8V2imeM2BaKs13yhMEais3ruM3rPvTGpump`)

**Token record:**

- symbol: `ANSEM`, name: `The Black Bull`
- created_at: `2026-06-28`
- Token mint suffix: `pump` (PumpFun-launched token)
- 2 pairs in DB: pair_id 13, 14

**Pair detail:**

| pair_id | pair_address (truncated) | first_seen_at | last_seen_at | base_token_mint |
|---------|--------------------------|---------------|--------------|-----------------|
| 13 | `FnzKY6x7...3CC` | 2026-06-28T19:59 | 2026-06-29T10:38 | `FnzKY6x7...3CC` (= pair_address — DATA BUG) |
| 14 | `6e7V9eeg...pvN` | 2026-07-04T22:12 | 2026-07-06T22:40 | `6e7V9eeg...pvN` (= pair_address — DATA BUG) |

**Temporal gap between pairs:** ~5 days (pair 13 last seen June 29, pair 14 first seen July 4)

**Discovery pipeline state:**

| pair_id | Discovery candidate | Tracking queue | Lifecycle event | Source response |
|---------|---------------------|----------------|-----------------|-----------------|
| 13 | **No** | **No** | **No** | None |
| 14 | **No** | **No** | **No** | None |

**Memory windows:**

| pair_id | Count | memory_status distribution | do_not_train |
|---------|-------|----------------------------|--------------|
| 13 | 6 | PARTIAL_MEMORY×1 (CLEAN_DATA), DIRTY_MEMORY×5 (MISSING_CRITICAL_DATA) | 1 of 6 trainable |
| 14 | 23 | DIRTY_MEMORY×14 (MISSING_CRITICAL_DATA), PARTIAL_MEMORY×9 (CLEAN_DATA) | 9 of 23 trainable |

**Critical observation:** Neither pair for ANSEM ever went through the discovery pipeline. No discovery candidates, no tracking queue entries, no lifecycle events, no source responses. Both pairs have corrupted `base_token_mint` (= pair_address). Yet 29 memory windows exist — all generated outside the normal discovery-to-tracking pathway. V2-2B Section 16 already flagged ANSEM as the most critical STNP risk: "Any batch includes `token_id = 13` without resolved pair classification."

---

## 5. STNP Classification Table

| token_id | Token | Primary mint | Pair situation | Classification | Rationale |
|----------|-------|--------------|----------------|----------------|-----------|
| 7 | BONK | `DezXAZ8z...` | Pairs 16 and 17 vs original pair 7 | **UNRESOLVED** for pairs 16, 17 | No discovery candidates for extra pairs; `base_token_mint` = `pair_address` (data bug) on both; appeared and vanished within 22-min windows; cannot confirm as DISTINCT_EVIDENCE, MIGRATION, or DUPLICATE_RECYCLE without verified source data |
| 12 | FARM | `yMJPZbn...pump` | Pair 18 vs original pair 12 | **UNRESOLVED** for pair 18 | No discovery candidate for pair 18; `base_token_mint` = `pair_address` (data bug); appeared within 37-min window on 2026-07-07; original pair 12 has a clean discovery trail |
| 13 | ANSEM | `9cRCn9r...pump` | Pair 13 vs pair 14 | **UNRESOLVED** for both pairs | Neither pair has a discovery candidate; both have corrupted metadata; 5-day temporal gap between pairs is consistent with MIGRATION but no source evidence confirms it; V2-2B Section 7 and 16 already required explicit classification before batch entry |

### Supporting evidence per classification

**token_id 7, pairs 16 and 17 — why UNRESOLVED (not DISTINCT_EVIDENCE):**
- A DISTINCT_EVIDENCE classification requires "meaningfully different liquidity, volume, or price" between pools as separate markets. Pairs 16 and 17 have no discovery candidates to confirm their market data.
- The `base_token_mint` = `pair_address` on both extra pairs is a data ingestion anomaly that prevents confirming they represent real BONK pools rather than corrupt entries.
- The original pair 7 remains clean and is confirmed as a BONK pool on dexscreener ($291k liquidity, high volume). It is safe to use pair 7 without any STNP classification.

**token_id 12, pair 18 — why UNRESOLVED (not MIGRATION or DISTINCT_EVIDENCE):**
- FARM is a PumpFun-origin token (`pump` suffix) with $95k liquidity on its original GeckoTerminal pool; this suggests it may have already migrated to a Raydium-like DEX at time of first discovery.
- Pair 18 appears 12+ days after original discovery with no source trace. The `base_token_mint` bug prevents confirming it is a real FARM pool.
- Without a discovery candidate for pair 18, neither MIGRATION nor DISTINCT_EVIDENCE can be confirmed.
- Original pair 12 remains clean and can be used without STNP classification.

**token_id 13, pairs 13 and 14 — why UNRESOLVED (not MIGRATION):**
- The ~5-day gap between pair 13 (June 29) and pair 14 (July 4) is circumstantially consistent with a PumpFun-to-Raydium migration timeline for a memecoin.
- However: no discovery candidate exists for either pair. Neither went through the parser, classifier, or source response pathway. We cannot verify the migration event from DB evidence alone.
- All 29 memory windows across both pairs are DIRTY_MEMORY or PARTIAL_MEMORY. The majority have `data_quality_label = MISSING_CRITICAL_DATA` and `do_not_train = 1`.
- V2-2B Section 7 explicitly flagged ANSEM as the highest-risk STNP case (token_id = 13, mentioned by name in Section 16 risk table).

---

## 6. V2-2D Batch Inclusion / Exclusion Decision

| token_id | Pair to use | V2-2D action | Condition |
|----------|-------------|--------------|-----------|
| 7 (BONK) | pair_id 7 only | **MAY INCLUDE** | No STNP classification needed for pair 7 (original pair with clean discovery). Pairs 16 and 17 must be **EXCLUDED** (UNRESOLVED). |
| 12 (FARM) | pair_id 12 only | **MAY INCLUDE** | No STNP classification needed for pair 12 (original pair with clean discovery). Pair 18 must be **EXCLUDED** (UNRESOLVED). |
| 13 (ANSEM) | Neither pair | **MUST EXCLUDE** | Neither pair 13 nor pair 14 has a discovery candidate. Classification is UNRESOLVED for both pairs. Token must not enter any bounded batch until at minimum one pair receives a proper discovery candidate and the STNP relationship between pairs 13 and 14 is explicitly resolved. |

---

## 7. Unresolved Blockers

| Blocker | Severity | Token affected |
|---------|----------|----------------|
| Pairs 16 and 17 for BONK have `base_token_mint = pair_address` (data ingestion bug) | MEDIUM — blocks those pairs only; pair 7 is clean | token_id 7 |
| Pair 18 for FARM has `base_token_mint = pair_address` (data ingestion bug) | MEDIUM — blocks pair 18 only; pair 12 is clean | token_id 12 |
| ANSEM has no discovery candidates for either pair | HIGH — blocks token entirely | token_id 13 |
| All ANSEM memory windows are DIRTY or PARTIAL, most with MISSING_CRITICAL_DATA | HIGH — existing windows are not usable for training | token_id 13 |
| ANSEM base_token_mint = pair_address on both pairs | HIGH — data quality prevents confirming pool identity | token_id 13 |

**Root cause hypothesis for `base_token_mint = pair_address` bug:**
Pairs 16, 17 (BONK) and pair 18 (FARM) and pairs 13, 14 (ANSEM) all share the same anomaly: `base_token_mint` is set to the pair address rather than the token mint. This is distinct from pair 12 (FARM original), which correctly shows `base_token_mint = yMJPZbn...pump`. The anomaly affects all pairs that were created outside the governed discovery pipeline or through a code path that did not apply the same normalization as the discovery parser. This is a data quality issue, not a STNP issue per se — but it compounds the STNP uncertainty.

---

## 8. Locks Preserved

- No DB rows were written or mutated.
- No migrations were run.
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

---

## 9. Next Recommended Lane

**Next recommended lane: `V2-2D — Bounded discovery/selection proof`**

Pre-conditions satisfied for V2-2D:
- [x] V2-2C implemented (`b0ca1b5`)
- [x] STNP classification preflight completed (this document)
- [x] token_id 7 pair-selection decision: pair 7 only
- [x] token_id 12 pair-selection decision: pair 12 only
- [x] token_id 13 ANSEM exclusion: excluded entirely

Pre-conditions NOT yet satisfied:
- [ ] token_id 13 (ANSEM) remains fully UNRESOLVED — must be excluded from all V2-2D batches
- [ ] Pairs 16, 17 (BONK) remain UNRESOLVED — must be excluded from V2-2D batches
- [ ] Pair 18 (FARM) remains UNRESOLVED — must be excluded from V2-2D batches
- [ ] The `base_token_mint = pair_address` data ingestion bug has not been diagnosed or repaired (out of scope for this preflight, but should be noted for future audit)

V2-2D may proceed using:
- token_id 7 (BONK), pair_id 7 — TRACK_FAST, clean discovery trail
- token_id 12 (FARM), pair_id 12 — TRACK_FAST, clean discovery trail
- Any other tokens from the tracking queue (token_ids 1–6, 8–11, 14–17) subject to V2-2B quota and gate rules
- token_id 13 (ANSEM) must be excluded from all V2-2D batches

V2-2D must not include any token with an UNRESOLVED same-token/new-pair classification per V2-2B Section 7.
