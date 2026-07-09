# Printer V1 V2-2Z Staged / Native 15m Evidence Readiness Review

**Lane:** V2-2Z — Staged / Native 15m Evidence Readiness Review
**Type:** Audit/readiness only
**Executor:** Claude Sonnet 4.6 (standard mode)
**Verdict:** `READINESS_COMPLETE_WITH_BLOCKERS`
**Date:** 2026-07-09

---

V2-3, V2-4, PumpPortal live transport, PumpSwap readiness, source expansion,
runtime/scheduler, memory generation, retrieval, paper decisions, BUY/SELL/HOLD,
positions, trades, audits, and PnL remain paused.

This lane is audit/readiness only. No code was changed. No tests were changed.
No DB was migrated or mutated. No live sources were called. No paper decisions
were created.

---

## 1. Source Stack Read

The following source-of-truth documents were read for this lane:

| Document | Role |
|---|---|
| `AGENTS.md` | Highest authority |
| `docs/printer-v1-clean-master-spec.md` | Master specification |
| `docs/printer-v1-post-rc-build-order.md` | Post-RC lane order |
| `docs/printer-v1-memory-factory-guide.md` | Memory factory rules |
| `docs/printer-v1-current-state-memory-growth-audit.md` | Baseline state |
| `docs/printer-v1-memory-growth-build-order-v2.md` | V2 roadmap |

Recent lane docs read:

| Document | Verdict |
|---|---|
| `docs/printer-v1-v2-2j-discovery-selection-foundation-closeout.md` | CLOSEOUT_COMPLETE_WITH_BLOCKERS |
| `docs/printer-v1-v2-2k-discovery-selection-practical-coverage-diagnostic-audit.md` | AUDIT_COMPLETE_WITH_BLOCKERS |
| `docs/printer-v1-v2-2i-discovery-selection-capacity-repair-bounded-proof.md` | PROOF_PASS_WITH_BLOCKERS |
| `docs/printer-v1-v2-2x-2-t2-token-age-evidence-implementation-fixture-proof.md` | IMPLEMENTATION_PROOF_PASS_WITH_BLOCKERS |
| `docs/printer-v1-v2-2x-3-t2-token-age-evidence-verification.md` | VERIFICATION_PASS_WITH_BLOCKERS |
| `docs/printer-v1-v2-2y-bounded-live-t2-token-age-proof.md` | PROOF_NOT_READY_WITH_BLOCKER |
| `docs/printer-v1-v2-2p-3-pair-market-age-metadata-verification.md` | VERIFICATION_PASS |

---

## 2. Files Inspected

| File | Purpose |
|---|---|
| `src/printer_v1/discovery/parser.py` | NORMALIZED_FIELDS, normalization paths, tier logic |
| `src/printer_v1/discovery/selection_batch.py` | _METADATA_FIELDS, _CRITICAL_FAST_EVENT_FIELDS, A3 gate |
| `src/printer_v1/sources/geckoterminal.py` | GeckoTerminal normalization; which fields extracted |
| `src/printer_v1/sources/dexscreener.py` | DexScreener normalization; which fields extracted |
| `src/printer_v1/sources/pumpportal.py` | PumpPortal adapter; field coverage |
| `src/printer_v1/sources/pumpswap.py` | PumpSwap adapter; field coverage |
| `src/printer_v1/sources/registry.py` | Source registry; allowed request kinds |
| `src/printer_v1/sources/recording.py` | SQLite recording helpers |
| `src/printer_v1/snapshots/recorder.py` | SNAPSHOT_INSERT_FIELDS; 15m column usage |
| `src/printer_v1/snapshots/contracts.py` | Snapshot quality/coverage labels |
| `src/printer_v1/db/migrate.py` | Migration runner |
| `migrations/001_database_foundation.sql` | printer_token_snapshots schema; 15m columns |
| `migrations/006_token_level_snapshot_system.sql` | Snapshot gap and window coverage tables |
| `migrations/021_repeatable_evidence_windows.sql` | Memory window identity fields |
| `tests/test_v2_2h3_field_normalization_fast_events.py` | 15m field test assertions |

---

## 3. Anchors

| Lane | Commit |
|---|---|
| V2-2J closeout | `c6f002a` |
| V2-2X.2 fixture T2 implementation | `7eae329` |
| V2-2X.3 verification | `6af1012` |
| V2-2Y bounded live T2 proof (blocker) | `e6f5723` |

---

## 4. Current 15m Parser-Field State

### 4.1 NORMALIZED_FIELDS

All three 15m evidence fields exist in `NORMALIZED_FIELDS` in `parser.py`:

| Field | Normalization paths |
|---|---|
| `price_change_15m` | `("priceChange", "m15")`, `("price_change", "m15")`, `("price_change_15m",)` |
| `volume_15m` | `("volume", "m15")`, `("volume_15m",)` |
| `txns_15m` | `("txns", "m15")`, `("txns_15m",)` |

### 4.2 Downstream plumbing

| Layer | Status |
|---|---|
| `SNAPSHOT_INSERT_FIELDS` in `snapshots/recorder.py` | All three present: `volume_15m`, `txns_15m`, `price_change_15m` |
| `_METADATA_FIELDS` in `selection_batch.py` | `volume_15m`, `price_change_15m` present; metadata survives to batch item |
| `_CRITICAL_FAST_EVENT_FIELDS` in `selection_batch.py` | `price_change_15m`, `volume_15m` present; counted in field-completeness report |
| `printer_token_snapshots` DB table (migration 001) | `volume_15m REAL`, `txns_15m INTEGER`, `price_change_15m REAL` — native columns |

### 4.3 Current fill rate

V2-2K live audit (70 normalized candidates, GeckoTerminal + DexScreener):

| Field | Missing count | Missing % |
|---|---:|---:|
| `price_change_15m` | 70 | 100.0% |
| `volume_15m` | 70 | 100.0% |
| `txns_15m` | 70 (inferred) | 100.0% |

GeckoTerminal (40 candidates): 15m price change/volume — 40, 100%.
DexScreener (30 candidates): 15m price change/volume — 30, 100%.

Test `test_v2_2h3_field_normalization_fast_events.py` asserts this explicitly:

```python
def test_volume_15m_remains_none_from_standard_source(self):
    # Neither DexScreener nor GeckoTerminal expose 15m volume; must remain None
    result = normalize_candidate("dexscreener", pair, now=_FIXED_NOW)
    self.assertIsNone(result["volume_15m"])
```

### 4.4 Staged observation and derived-window fields

No staged observation timestamp fields exist specifically for 15m derivation.
No `snapshot_open_price`, `snapshot_close_price`, or `observation_interval_seconds`
fields exist in the current schema. No derived-window metadata table exists.
`printer_token_snapshots` records `price_usd` and `captured_at` for each snapshot,
which are the minimum ingredients for staged derivation, but no derivation module
reads two rows and computes a delta.

---

## 5. Source Capability Matrix

### 5.1 GeckoTerminal (new pools / trending pools)

| Aspect | Result |
|---|---|
| Request kinds | `geckoterminal_new_pool_discovery`, `geckoterminal_trending_pool_reference` |
| Live status | READY |
| Native 15m fields in API response | NO |
| Fields extracted by adapter | `volume_5m`, `volume_1h`, `volume_24h`; `txns_5m`, `txns_1h`, `txns_24h`; `price_change_5m`, `price_change_1h`, `price_change_24h`; `pair_created_at` |
| 15m fields extracted | NONE |
| GeckoTerminal OHLCV endpoint (`/ohlcv/minute?aggregate=15`) | EXISTS in GeckoTerminal API but NOT wired in current adapter |
| OHLCV endpoint status | NOT registered; no adapter transport; no request kind; no governance path |

The GeckoTerminal pool-list endpoints (`/new_pools`, `/trending_pools`) return rolling-window
data for 5m, 1h, and 24h only. The API does not include `volume_usd.m15`,
`transactions.m15`, or `price_change_percentage.m15` in pool-list responses.

A separate GeckoTerminal OHLCV endpoint exists (`/api/v2/networks/{network}/pools/{pool_address}/ohlcv/minute?aggregate=15&limit=1`) that could return a single 15m candle for a specific pair. However this endpoint is pair-level (not batch discovery), is not registered in the source registry, has no adapter transport, and would require a separate design and implementation lane.

### 5.2 DexScreener (token search)

| Aspect | Result |
|---|---|
| Request kinds | `token_discovery` |
| Live status | READY |
| Native 15m fields in API response | NO |
| Fields extracted by adapter | `volume_5m`, `volume_1h`, `volume_24h`; `txns_5m`, `txns_1h`, `txns_24h`; `price_change_5m`, `price_change_1h`, `price_change_24h`; `pair_created_at` |
| 15m fields extracted | NONE |
| DexScreener API 15m support | NOT available. DexScreener's `/latest/dex/search` and `/latest/dex/pairs/` responses use `volume.m5`, `volume.h1`, `volume.h6`, `volume.h24` — no `m15` window exists in the API |

DexScreener's public API does not provide 15m rolling windows. No adapter extension
can add 15m fields from DexScreener responses because the upstream API does not emit them.

### 5.3 PumpPortal (launch/migration stream)

| Aspect | Result |
|---|---|
| Request kinds | `pumpfun_launch_stream`, `pumpfun_migration_stream` |
| Live status | NOT_READY (fixture-only, `fixture_transport_only=True`) |
| Native 15m fields | NO — event-based stream; provides token identity, liquidity, curve metadata; not price/volume candles |
| 15m contribution | None possible from this source |

### 5.4 PumpSwap (pool confirmation)

| Aspect | Result |
|---|---|
| Request kinds | `pumpswap_pool_confirmation`, `pumpswap_migration_pool_reference` |
| Live status | NOT_READY (fixture-only) |
| Native 15m fields | NO — read-only pool confirmation; no time-series price/volume data |
| 15m contribution | None possible from this source |

### 5.5 Solana RPC / Helius

| Aspect | Result |
|---|---|
| Status | On-chain account data; not a price/volume source |
| Native 15m fields | NO |
| 15m contribution | None possible from these sources |

### 5.6 Summary

| Source | Native 15m | Staged basis (price snapshots) | Notes |
|---|---|---|---|
| GeckoTerminal new/trending pools | NO | YES (price_usd at captured_at exists) | Rolling-window 5m/1h/24h only |
| GeckoTerminal OHLCV endpoint | POSSIBLE (not wired) | N/A | New request kind + transport required |
| DexScreener search | NO | YES (price_usd at captured_at exists) | API has no m15 field; no workaround |
| PumpPortal | NO | NO | Event source, no candle data |
| PumpSwap | NO | NO | Confirmation source, no candle data |
| Solana RPC / Helius | NO | NO | On-chain; no price history |
| Jupiter | NO | NO | Paper quote realism only |

**Conclusion: No current READY source provides native 15m fields.**

---

## 6. Staged Observation Capability

### 6.1 Tables that exist

| Table | Relevant to 15m derivation | Key columns |
|---|---|---|
| `printer_token_snapshots` | YES — primary | `token_id`, `pair_id`, `captured_at`, `price_usd`, `volume_15m`, `txns_15m`, `price_change_15m`, `source_status`, `data_quality_label`, `snapshot_quality_label` |
| `printer_source_responses` | YES — governance trace | `source_name`, `received_at`, `data_quality_label`, `normalized_payload_json` |
| `printer_discovery_candidates` | YES — candidate record | `source_name`, `token_id`, `pair_id`, `normalized_candidate_payload_json` |
| `printer_snapshot_window_coverage` | YES — coverage context | `token_id`, `pair_id`, `opened_at`, `closed_at`, `coverage_label` |
| `printer_memory_windows` | DOWNSTREAM | `snapshot_start_id`, `snapshot_end_id`, `window_kind` |
| `printer_tokens` | YES — identity | `token_mint`, `chain` |
| `printer_pairs` | YES — identity | `pair_address`, `token_id` |

The `printer_token_snapshots` table has `price_usd` and `captured_at` which
are the minimum columns needed for staged `price_change_15m` derivation from two
observations.

### 6.2 What exists for staged derivation

- Timestamped price observations (`price_usd`, `captured_at`) in `printer_token_snapshots`
- Token and pair identity through FK constraints
- Data quality labels (`CLEAN_DATA`, `STALE_DATA`, etc.) per snapshot
- Source status per snapshot
- Gap and coverage labels (via migration 006)

### 6.3 What is missing for staged derivation

- **No derivation logic** — no module computes `price_change_15m` from two snapshots
- **No design contract** — no formal specification for which snapshot pairs are eligible
- **No interval tolerance contract** — no rule for accepting a 13-17 minute delta as "15m"
- **No quality contract for derived evidence** — no distinction between native source
  15m value and derived-from-two-snapshots 15m value
- **No test suite for derivation** — no fixture tests proving the derivation rules

### 6.4 Feasibility assessment by field

| Field | Staged derivation feasible? | Constraint |
|---|---|---|
| `price_change_15m` | YES — conditional | Requires two CLEAN_DATA price snapshots for same pair/source, ~15 minutes apart. Computation: `(price_T+15m - price_T) / price_T * 100`. Safe if price_usd is non-zero in both snapshots. |
| `volume_15m` | NO from rolling-window sources | Current sources provide `volume_5m` = "rolling last 5 minutes." Summing 3 consecutive `volume_5m` readings is invalid: rolling windows overlap and do not represent sequential non-overlapping intervals. A cumulative-volume source or a native 15m candle would be needed. |
| `txns_15m` | NO from rolling-window sources | Same constraint as `volume_15m`. `txns_5m` is a rolling count and cannot be safely summed across three overlapping 5-minute windows. |

---

## 7. Core Question Answers

### Q1: 15m parser fields

`price_change_15m`, `volume_15m`, and `txns_15m` all exist in:
- `NORMALIZED_FIELDS` (parser.py)
- `SNAPSHOT_INSERT_FIELDS` (snapshots/recorder.py)
- `printer_token_snapshots` DB table (migration 001)
- `_METADATA_FIELDS` (selection_batch.py)
- `_CRITICAL_FAST_EVENT_FIELDS` (selection_batch.py field-completeness report)

All are currently 100% None in live pipeline output. No staged observation timestamps,
no snapshot open/close price fields, no derived-window metadata exist specifically
for 15m computation.

### Q2: Source adapter native 15m capability

No current source adapter provides native 15m fields. GeckoTerminal batch endpoints
and DexScreener are READY but neither returns 15m windows. PumpPortal, PumpSwap,
Solana RPC, Helius, and Jupiter are not price/volume candle sources. A GeckoTerminal
OHLCV pair-level endpoint could provide 15m candles but is not wired.

### Q3: Staged derivation from existing source responses

Staged `price_change_15m` is feasible from two clean governed snapshots for the
same pair/source taken ~15 minutes apart. `volume_15m` and `txns_15m` are not
safely derivable from existing rolling-window source data without fabrication.

Existing source rows are safe for staged price derivation only if:
- Both rows have `CLEAN_DATA` quality
- Neither row is stale or failed
- Both rows have non-None, non-zero `price_usd`
- Both rows are from the same source, token_id, and pair_id
- The `captured_at` delta is within a defined tolerance band (e.g. 12–18 minutes)

No module currently implements this.

### Q4: DB tables for staged observations

`printer_token_snapshots` is the primary staged-observation store and already has
columns for all three 15m fields. The pair/token identity, governance trace, and
quality label infrastructure exist. The missing piece is a derivation contract and
derivation module.

### Q5: 15m derivation without forbidden shortcuts

`price_change_15m`: Derivable without forbidden shortcuts if both snapshots are clean,
from the same governed source, and the time delta is genuinely ~15 minutes.

`volume_15m`: Cannot be derived without forbidden shortcuts from rolling-window sources.
Would require subtracting cumulative-volume observations or using a native 15m candle.

`txns_15m`: Same constraint as `volume_15m`. Not safely derivable from rolling counts.

No 15m value should be fabricated from 5m, 1h, or 24h values. The snapshot table
columns are designed to receive real 15m values; they must not receive placeholder
values copied from adjacent windows.

### Q6: Smallest safe next design lane

**Recommended: V2-2Z.1 — Staged Price-Change 15m Derivation Design**

Scope: design-only lane that produces a formal specification for:

1. Eligible snapshot-pair criteria (same `token_id`, `pair_id`, `source_name`;
   both `CLEAN_DATA`; both non-None `price_usd`; `captured_at` delta in tolerance band)
2. Derivation formula and rounding
3. Derived evidence quality classification (must distinguish derived from native)
4. How derived value is stored (in `price_change_15m` with annotation? or new column?)
5. What test plan is required before accepting derived values
6. Governance rules: when derivation is allowed, when it is rejected, when it is deferred
7. Upper-bound and anti-abuse rules (e.g. max acceptable drift from 15 minutes)

A second optional parallel lane: **V2-2Z.2 — GeckoTerminal OHLCV 15m Source Design**

Scope: design-only lane that specifies:
1. New request kind: `geckoterminal_pool_ohlcv_15m`
2. New adapter transport to the OHLCV endpoint
3. Registry extension
4. Normalization of all three 15m fields from OHLCV candle
5. Governance path through Source Governor
6. How this integrates with batch discovery vs. pair-specific enrichment

These are design lanes. Neither implements code.

---

## 8. Native vs. Staged Recommendation

### Recommendation: Staged price-change first; native OHLCV as a future lane

**Staged `price_change_15m` derivation** is the lower-effort path:
- Uses existing `printer_token_snapshots` infrastructure
- Does not require a new source adapter or request kind
- Does not require new registry entries or governance wiring
- Can be proved with fixture tests against existing snapshot rows
- Leaves `volume_15m` and `txns_15m` as None (explicitly documented)
- Risk: timing imprecision; mitigated by tolerance band and quality labeling

**Native GeckoTerminal OHLCV** provides all three 15m fields but:
- Requires a pair-specific API call (cannot be batch)
- Requires new request kind and adapter transport
- Requires governance design for pair-level enrichment requests
- Would be a larger separate lane after the staged path is proven

**Fabricating 15m values from 5m/1h windows is not allowed** under any design.
Rolling-window `volume_5m × 3 = volume_15m` is arithmetically wrong (overlapping windows).
Copying `volume_1h / 4 = volume_15m` is also wrong (no intra-hour distribution guarantee).

---

## 9. Whether Implementation Can Proceed

**Implementation cannot proceed yet.** A design contract is required first because:

1. No formal spec for eligible snapshot pairs exists
2. No quality contract distinguishes derived from native 15m values
3. No tolerance band for interval precision has been agreed
4. No test plan has been defined
5. No governance rule for when derivation is allowed vs. deferred exists

The first safe step is a design-only lane (V2-2Z.1) that produces the contract.
After the operator accepts the design, implementation can proceed as V2-2Z.1.impl
or similar.

---

## 10. Proof/Test Plan Required Before Accepting 15m Evidence

Before any derived or native 15m evidence is accepted in the pipeline:

1. **Fixture tests for derivation function**: prove correct computation from two
   known price values; prove rejection of stale/failed/None-price pairs; prove
   interval tolerance bounds; prove no fallback to adjacent windows.

2. **Pipeline integration test**: prove derived `price_change_15m` appears in
   `extract_candidate_metadata()` output; prove it does not affect `derive_age_bucket()`,
   A3, or `derive_recent_active_tier()`.

3. **Source-trace test**: prove that a derived 15m value retains a source identity
   link to both snapshot IDs and is not promoted to clean native evidence without
   that link.

4. **Safety isolation tests**: prove that non-None `price_change_15m` alone does not
   create memory, activate retrieval, create a paper decision, or unlock BUY/SELL/HOLD.

5. **Anti-fabrication tests**: prove that `volume_15m` and `txns_15m` remain None
   when only price-change derivation is active.

6. **Staleness rejection tests**: prove that stale source rows (STALE_DATA quality)
   cannot produce derived 15m evidence.

If GeckoTerminal OHLCV native is implemented:
7. **Native candle normalization tests**: prove all three fields parse correctly;
   prove pair identity and timestamp match; prove OHLCV staleness threshold.

---

## 11. Safety Confirmations

| Safety rule | Status |
|---|---|
| Native 15m only from source that explicitly provides real 15m fields | CONFIRMED — no current source qualifies; will require explicit design and governance |
| Staged 15m only from same token/pair/source target observations | CONFIRMED — would require same `token_id`, `pair_id`, `source_name` constraint |
| No 15m value fabricated from 5m, 1h, or 24h fields | CONFIRMED — rolling windows cannot be used for volume/txn derivation |
| No 15m value inferred from pair age | CONFIRMED — no path exists for this |
| No dirty/stale/failed source rows produce clean 15m evidence | CONFIRMED — design must require `CLEAN_DATA` quality on both snapshots |
| 15m evidence alone does not create memory | CONFIRMED — memory creation requires memory window pipeline |
| 15m evidence alone does not activate retrieval | CONFIRMED — retrieval remains locked |
| 15m evidence alone does not create paper decisions | CONFIRMED — paper decisions remain locked |
| 15m evidence alone does not unlock BUY/SELL/HOLD | CONFIRMED — financial paths remain locked |
| 15m evidence remains upstream discovery/selection evidence only | CONFIRMED — no downstream financial wiring exists |

---

## 12. Money-Usefulness Contribution

**What 15m evidence would contribute:**

`price_change_15m` is currently 100% missing and is classified as a critical
fast-event field (`_CRITICAL_FAST_EVENT_FIELDS`). Its absence means:

- The A1 bucket (fast-pump) cannot be differentiated by 15m momentum
- A2/A3/A4 buckets require additional evidence; `price_change_15m` is one supporting
  input for A2 (reversal detection) and A3 (old token re-activity)
- The field-completeness report (`build_field_completeness_report`) currently shows
  100% missing for `price_change_15m` and `volume_15m` — this is the measured gap

**Impact on learning quality if filled:**

- Cleaner fast-event differentiation: A1 vs. wick-only vs. sustained
- Better timing context for 15m memory windows that the pipeline already targets
- More precise price-change evidence for memory fingerprints
- Does not unlock any financial gate by itself; improves learning-set quality

**Impact if not filled:**

The pipeline continues to operate with 5m and 1h windows. Memory windows labeled
`WINDOW_15M` already exist in the DB; their content snapshots carry 15m evidence
slots that remain None. This is a known gap, not a functional breakage. The system
continues to learn from price_usd, volume_5m, volume_1h, liquidity, and price
change over 5m/1h/24h windows.

---

## 13. What This Lane Improves

- Establishes the exact state of 15m evidence readiness in the repo
- Documents that the parser, recorder, and DB infrastructure are complete
- Confirms that no current READY source provides native 15m fields
- Confirms that staged price-change derivation is conceptually feasible
- Confirms that staged volume/txn derivation is not safe from rolling-window sources
- Identifies the smallest safe next design lane
- Documents the required proof/test plan before implementation
- Clears the readiness question so the next lane can be a focused design lane

---

## 14. What This Lane Still Does Not Unlock

- Implementation of staged 15m derivation (requires V2-2Z.1 design first)
- Native GeckoTerminal OHLCV transport (requires separate design and implementation lane)
- A2/A3/A4 fast-event buckets from 15m evidence (still require other evidence too)
- Memory generation (paused)
- Retrieval (locked)
- Paper decisions (locked)
- BUY/SELL/HOLD (locked)
- Positions, trades, audits, PnL (locked)
- PumpPortal live transport (blocked, V2-2Y)
- V2-3 / V2-4 (paused)

---

## 15. Functionality Risks / Setbacks / Efficiency Blockers

| Problem | Why it matters | How it could reduce quality or usefulness | Failure mode | Required mitigation |
|---|---|---|---|---|
| Fabricating 15m values from 5m or 1h windows | Produces numerically wrong evidence | Memory fingerprints built on fake values mislead future learning | False memory, biased decisions | Hard prohibition; test must assert volume_15m and txns_15m remain None when not natively sourced |
| Accepting rolling-window sum as staged volume_15m | Rolling 5m windows overlap; summing 3 is wrong | Overstated or understated volume evidence | Dirty memory, bad selection | Design contract must explicitly reject this approach |
| Interval drift in staged derivation | Snapshots taken 5 or 25 minutes apart are not "15m" | Mislabeled evidence produces incorrect price-change signal | Biased fast-event labels | Tolerance band in design contract; reject outside tolerance |
| Stale snapshot used in derivation | Stale prices are not real market prices | Derived 15m value reflects old state | False evidence quality | Both snapshots must be CLEAN_DATA; derivation rejects stale |
| Derived evidence treated as native | Parser cannot distinguish; DB column is the same | Derived values may receive higher trust than warranted | Incorrectly weighted in fingerprints | Separate quality tag or annotation distinguishing native vs. derived |
| GeckoTerminal OHLCV without governance | Pair-level HTTP call without Source Governor would bypass rate limits and trace | Ungoverned calls, untracked evidence | Rate limit breach; untraceable evidence | New transport must go through Source Governor; new request kind required |
| 15m evidence activating downstream financial paths prematurely | If wired incorrectly, could contribute to premature BUY logic | Paper decisions based on insufficient evidence | False signals | Verify no financial gate reads price_change_15m directly; add test |

---

## 16. Remaining Blockers

| Blocker | Status |
|---|---|
| No current source provides native 15m price/volume fields | HARD BLOCKER for native path |
| GeckoTerminal OHLCV adapter not wired | BLOCKED — requires design + implementation lane |
| No staged derivation design contract for price_change_15m | DESIGN REQUIRED before implementation |
| No staged derivation feasible for volume_15m or txns_15m from rolling-window sources | ARCHITECTURAL CONSTRAINT |
| No test suite for 15m derivation | REQUIRED before any implementation is accepted |
| PumpPortal live transport not implemented | HARD BLOCKER (from V2-2Y) |
| V2-3 remains paused | INTENTIONAL |
| Memory generation remains paused | INTENTIONAL |
| Retrieval remains locked | INTENTIONAL |
| Paper decisions remain locked | INTENTIONAL |
| BUY/SELL/HOLD remain locked | INTENTIONAL |
| Positions, trades, audits, PnL remain locked | INTENTIONAL |

---

## 17. Exact Next Recommended Lane

**V2-2Z.1 — Staged Price-Change 15m Derivation Design (design-only)**

Goal: produce a formal design contract for computing `price_change_15m` from two
consecutive clean governed price snapshots for the same pair, without implementing
code.

Allowed: documentation only — design contract, eligibility rules, quality
classification, test plan spec, anti-abuse rules.

Not allowed: code, migrations, tests, live source calls, DB mutation, or any
financial path.

Scope deliverable: one design document covering the six contract items listed in
Section 7 Q6.

After V2-2Z.1 design is accepted by the operator:

**V2-2Z.2 — Staged Price-Change 15m Derivation Implementation**

Goal: implement the approved design contract from V2-2Z.1.

Required: fixture test suite per the proof plan in Section 10.

**V2-2Z.3 (optional, parallel track) — GeckoTerminal OHLCV 15m Source Design**

Goal: design the native 15m candle path from GeckoTerminal OHLCV for all three
15m fields.

Not allowed: any code or live API call; design document only.

V2-3 and further memory-generation lanes remain paused until operator approval.

---

## 18. Git Checks

```text
git diff --check     → no whitespace errors (no tracked changes)
git status --short   → only untracked files: data/, operator output .txt files
git diff --stat      → (empty — no staged or unstaged changes to tracked files)
git diff --name-only → (empty)
```

No source code, test files, migrations, or memory files were changed in this lane.

---

## 19. Final Verdict

`READINESS_COMPLETE_WITH_BLOCKERS`

**Why COMPLETE**: The parser fields (`price_change_15m`, `volume_15m`, `txns_15m`)
exist in `NORMALIZED_FIELDS`, `SNAPSHOT_INSERT_FIELDS`, `_METADATA_FIELDS`,
`_CRITICAL_FAST_EVENT_FIELDS`, and the `printer_token_snapshots` DB table. The
infrastructure layer is structurally ready to receive 15m values.

**Why WITH_BLOCKERS**:

1. No current READY source provides native 15m fields. GeckoTerminal batch endpoints
   and DexScreener produce 100% missing 15m fields (confirmed in V2-2K live audit).

2. Staged `price_change_15m` derivation from two governed snapshots is conceptually
   feasible but has no design contract, no implementation, and no test suite.

3. Staged `volume_15m` and `txns_15m` derivation is not safely achievable from
   existing rolling-window sources without arithmetic fabrication.

4. A design lane (V2-2Z.1) must precede any implementation.

**V2-3 remains paused.** V2-2Z does not unlock memory generation, retrieval,
paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.

---

## 20. Git Anchor

V2-2Z commit: `e58db54` (amended; see `git log --oneline` for final hash)
