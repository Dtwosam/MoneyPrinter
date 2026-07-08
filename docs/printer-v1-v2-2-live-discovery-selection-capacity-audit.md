# Printer V1 V2-2 Live Discovery/Selection Capacity Audit

Status: `CAPACITY / PERFORMANCE AUDIT`

Final verdict: `V2-2 Discovery/Selection Foundation: COMPLETE_WITH_BLOCKERS`

This report reopens V2-2 only to measure Printer's real bounded discovery path and
V2-2C selection logic. It does not start V2-3, generate memory, activate retrieval,
or unlock any paper-trading capability.

## 1. Source Stack and Boundary

The audit read and followed:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-assistant-active-build-order-anchor.md`
- `docs/printer-v1-v2-2a-discovery-selection-pipeline-audit.md`
- `docs/printer-v1-v2-2b-memory-diet-buckets-quotas-reasons-design.md`
- `docs/printer-v1-v2-2d-stnp-classification-preflight.md`
- `docs/printer-v1-v2-2d-bounded-discovery-selection-proof.md`
- `docs/printer-v1-v2-2e-discovery-selection-foundation-closeout.md`

The live call was operator-approved, Solana-only, free/public, one-shot, bounded by
one request and a five-second transport timeout, and routed through
`execute_source_request_with_governor()`. The command wrote only to an isolated copy
of the current database. The persistent database was not mutated.

## 2. Run Setup

| Item | Result |
|---|---|
| Command | `printer-discover-candidates-once` through `main_discover_candidates_once()` |
| Source | `geckoterminal` |
| Request kind | `geckoterminal_new_pool_discovery` |
| Source channel | `GECKOTERMINAL_NEW_POOL` |
| DB mode | Isolated proof DB copied from `data/printer_v1.sqlite3` |
| Proof DB | `data/printer_v1_v2_2_live_capacity_audit.sqlite3` |
| Operator approval | Explicit |
| Chain | Solana |
| Max candidates | 3, the command's current hard cap |
| Transport timeout | 5 seconds |
| Started | `2026-07-08T21:15:38.851633+00:00` |
| Ended | `2026-07-08T21:15:39.609849+00:00` |
| Measured request duration | 0.758216 seconds |
| Source status | `COMPLETE` |
| Data quality | `CLEAN_DATA` |
| Source request/response IDs | 1119 / 1072 in the proof DB |

The existing command does not support 50 persisted candidates or an explicit
`max_source_requests` option. Its validated range is one to three candidates and its
timeout range is greater than zero through ten seconds. This run used the largest
existing safe candidate cap and one source request.

The source call produced three scheduler follow-up rows in the proof DB as part of
the existing governed discovery handoff. No scheduler job was executed.

## 3. Discovery Capacity Metrics

| Metric | Result |
|---|---:|
| Source requests attempted | 1 |
| Source responses received | 1 |
| Source failures | 0 |
| Source failure rate | 0.0% |
| Normalized candidates discovered/inspected | 20 |
| Candidates persisted | 3 |
| Candidates rejected before persistence | 17 |
| Discovered candidates per second | 26.38 |
| Persisted candidates per second | 3.96 |
| Discovered candidates per source request | 20.0 |
| Persisted candidates per source request | 3.0 |

### Discovery distribution

| Dimension | Counts |
|---|---|
| Source | `geckoterminal`: 20 discovered, 3 persisted |
| Source channel | `GECKOTERMINAL_NEW_POOL`: 20 discovered, 3 persisted |
| Discovery action | `TRACK_FAST`: 3; `TRACK_NORMAL`: 9; `WATCH_ONLY`: 8 |
| Persisted tracking lane | `TRACK_FAST`: 1; `TRACK_NORMAL`: 2 |
| Persisted source status | `COMPLETE`: 3 |
| Persisted data quality | `CLEAN_DATA`: 3 |

Discovery reasons across the 20-candidate source universe:

- `clean_solana_candidate_with_basic_market_fields`: 9
- `fresh_solana_candidate_with_liquidity_and_activity`: 3
- `no_recent_activity_pulse_for_memory_growth`: 7
- `partial_market_fields_or_low_activity`: 1

Pre-persistence rejection reasons:

- `watch_only_not_eligible_for_15m_memory_proof_cycle`: 8
- `max_candidates_reached`: 9

The command inspected 20 candidates but persisted only 15%. Nine otherwise
trackable candidates were excluded solely because the three-candidate cap had been
reached. This is the primary measured discovery-capacity blocker.

## 4. Asset Universe and Coverage

All 20 normalized rows came from GeckoTerminal's Solana new-pool channel.

| Dimension | Counts |
|---|---|
| Asset class | `CONSOLIDATION`: 13; `HOT_TRENDING_PAIR`: 4; `FAST_PUMP`: 3 |
| Primary bucket | B5: 13; B3: 4; A1: 3 |
| Liquidity under $500 | 1 |
| Liquidity $500-$5,000 | 13 |
| Liquidity $5,000-$25,000 | 3 |
| Liquidity $25,000-$100,000 | 3 |
| Liquidity $100,000+ | 0 |
| 24h volume under $1,000 | 14 |
| 24h volume $1,000-$10,000 | 6 |
| 24h volume above $10,000 | 0 |
| Age bucket | `UNKNOWN`: 20 |
| New-pool channel rows | 20 |
| Migration rows | 0 |
| Boosted/hot/trending channel rows | `NOT_MEASURED` |
| Dead-token bucket rows | 0 |
| Low-liquidity rows under $500 | 1 |
| Unknown/unclassified bucket rows | 0 after categorical derivation |

No local artifact provides a defensible total Solana daily launch universe for this
run. Estimated daily universe and coverage percentage are therefore
`NOT_MEASURED`.

Source/channel blind spots:

- Only GeckoTerminal new pools were sampled.
- No governed DexScreener, PumpPortal, PumpSwap migration, trending, boosted,
  revival, or historical dead-token channel was sampled in this minimal run.
- One request cannot establish daily recall, channel overlap, or sustained rate-limit
  behavior.

## 5. Field Completeness

The denominator is the 20 normalized source candidates. Derived audit metadata
(`asset_class`, `primary_bucket`, source trace, and source channel) was attached
before completeness measurement.

| Field | Missing | Missing % |
|---|---:|---:|
| `token_created_at` | 20 | 100.0% |
| `pair_created_at` | 20 | 100.0% |
| `token_age_seconds` | 20 | 100.0% |
| `pair_age_seconds` | 20 | 100.0% |
| `price_usd` | 0 | 0.0% |
| `liquidity_usd` | 0 | 0.0% |
| `volume_5m` | 0 | 0.0% |
| `volume_15m` | 20 | 100.0% |
| `volume_1h` | 0 | 0.0% |
| `volume_24h` | 0 | 0.0% |
| `txns_5m` | 0 | 0.0% |
| `txns_1h` | 0 | 0.0% |
| `price_change_5m` | 20 | 100.0% |
| `price_change_15m` | 20 | 100.0% |
| `price_change_1h` | 20 | 100.0% |
| `price_change_24h` | 20 | 100.0% |
| `fdv` | 2 | 10.0% |
| `market_cap` | 20 | 100.0% |
| `source_response_id` | 0 | 0.0% |
| `source_channel` | 0 | 0.0% |
| `asset_class` | 0 | 0.0% |
| `primary_bucket` | 0 | 0.0% |

Price, liquidity, volume, transaction, and source-trace basics are strong for this
channel. Age and price-change fields needed for fast-event differentiation are
absent. A derived bucket being present does not repair missing source evidence.

## 6. V2-2C Selection Metrics

Migration 025 was absent from the copied current DB, so the existing
`migrations/025_selection_batch.sql` was applied to the proof DB only. No persistent
schema was changed.

The V2-2C batch considered only the three newly persisted candidates:

| Metric | Result |
|---|---:|
| Candidates considered | 3 |
| Candidates selected | 2 |
| Candidates rejected | 1 |
| Selection rate | 66.7% |
| Rejection rate | 33.3% |
| Selected buckets | B5: 2 |
| Selected asset classes | `CONSOLIDATION`: 2 |
| Selected tracking lanes | `TRACK_NORMAL`: 2 |
| Selected source/channel | `geckoterminal` / `GECKOTERMINAL_NEW_POOL`: 2 |
| Rejected reasons | `BATCH_QUOTA_EXCEEDED`: 1 |
| Final quota result | PASS |
| Final quota violations | 0 |
| Candidate-level quota failures | 1 |
| Duplicate mint rejections | 0 |
| Duplicate pair rejections | 0 |
| Unresolved STNP rejections | 0 |
| Corrupted metadata rejections | 0; corrupted rows never entered the batch |
| WATCH_ONLY gate rejections | 0; WATCH_ONLY rows were not persisted |
| Cooldown/archive gate rejections | 0 |
| Stale-source rejections | 0 |
| Missing-source-trace rejections | 0 |

The persisted A1 candidate was rejected because no A2, A3, or A4 counterpart existed.
After removing that candidate, the two-item B5 batch passed quota validation. This is
correct anti-winner-bias behavior, but the resulting memory diet is narrow.

## 7. Fast-Event Differentiation

| Metric | Result |
|---|---:|
| Fast-tier candidates in 20-row universe | 3 |
| A1 `FAST_PUMP_FOLLOW` | 3 |
| A2 `WICK_ONLY_PUMP` | 0 |
| A3 `LATE_BUY_TRAP` | 0 |
| A4 `FAILED_PUMP` | 0 |
| A2/A3/A4 blocked after classification | 0; none could be classified |
| Missing `price_change_5m` | 20 / 20, 100.0% |
| Missing `token_age_seconds` | 20 / 20, 100.0% |

Real normalized candidates cannot currently distinguish A2 or A3 on this channel
because their required fields are absent. Static inspection also found no A4 return
branch in `assign_bucket()`, so A4 is not presently derivable through that function.
The measured real-data outcome is therefore A1-only fast classification.

## 8. STNP and Corruption Safety

- Two of the 20 source candidates shared one mint across different pair addresses,
  creating same-token/new-pair review risk in the source universe.
- Only one of those two was eligible for persistence; the other remained
  `WATCH_ONLY`. No unresolved STNP candidate entered the V2-2C batch.
- Unresolved STNP rejections in the three-row selection batch: 0.
- ANSEM discovery candidates in the proof DB: 0.
- Corrupted pair IDs 13, 14, 16, 17, and 18 were present in the copied baseline with
  `base_token_mint = pair_address`.
- None of those corrupted pairs attempted to enter this selection batch.
- No excluded candidate entered selection.

Risk: the one-shot discovery persistence selector compares against the pre-run DB
sets, not a set updated after each accepted candidate. A same-mint/new-pair case
could therefore require explicit within-response dedup hardening if both rows are
otherwise eligible.

## 9. Row Deltas and Locks

| Table | Before | After | Delta |
|---|---:|---:|---:|
| `printer_discovery_candidates` | 15 | 18 | +3 |
| `printer_selection_batches` | table absent | 1 | proof schema + 1 |
| `printer_selection_batch_items` | table absent | 3 | proof schema + 3 |
| `printer_tracking_queue` | 15 | 18 | +3 |
| `printer_source_requests` | 1118 | 1119 | +1 |
| `printer_source_responses` | 1071 | 1072 | +1 |
| `printer_source_failures` | 47 | 47 | 0 |

Locked table verification:

| Table | Before | After | Delta |
|---|---:|---:|---:|
| `printer_memory_windows` | 156 | 156 | 0 |
| `printer_memory_retrieval_matches` | 0 | 0 | 0 |
| `printer_paper_decisions` | 2 | 2 | 0 |
| `printer_paper_positions` | 0 | 0 | 0 |
| `printer_paper_trade_events` | 0 | 0 | 0 |
| `printer_paper_trade_audits` | 0 | 0 | 0 |
| PnL table | absent | absent | 0 / not applicable |

No memory window was opened. No scheduler job was executed. No retrieval, decision,
position, trade, audit, or PnL path ran. The persistent DB stayed unchanged.

## 10. Build-Readiness Audit Scores

These are build-readiness audit scores only. They are not token scores, trading
scores, confidence percentages, BUY probabilities, rankings, or weighted decision
logic.

| Area | Score | Basis |
|---|---:|---|
| Discovery capacity | 4 / 10 | Fast one-request response, but persistence hard-capped at 3 of 20 |
| Source/channel coverage | 3 / 10 | One clean new-pool channel; broad universe coverage not measured |
| Field completeness | 4 / 10 | Strong basics; critical age and price-change fields absent |
| Selection correctness | 8 / 10 | Reasons, quota gate, trace, and lock behavior worked |
| Memory-diet balance | 4 / 10 | Final batch contained only two B5 consolidation candidates |
| Fast-event differentiation | 2 / 10 | A1 only; A2/A3 inputs absent and A4 path not proven |
| Safety/lock preservation | 10 / 10 | Proof DB only; all downstream deltas zero |
| Overall discovery/selection readiness | 5 / 10 | Foundation is safe and auditable, not yet complete or broad |

## 11. Blockers

1. The controlled discovery command persists at most three candidates per call.
2. It has no explicit `max_source_requests` option; one invocation currently means
   one request.
3. `price_change_5m`, `token_age_seconds`, creation timestamps, 15m fields, and
   price-change windows were missing from all 20 normalized rows.
4. A2 and A3 therefore cannot be distinguished from real normalized candidates in
   this channel.
5. No A4 assignment branch is proven in V2-2C `assign_bucket()`.
6. Only one source/channel was measured; daily Solana-universe coverage remains
   unknown.
7. The copied current DB did not contain migration 025 even though V2-2C selection
   code depends on its tables.
8. The selection batch was narrow: two B5 rows and no trap, dead, revival,
   migration, safety, liquidity-removal, or exit-realism sample.
9. Same-mint/new-pair rows can occur within one source response and need explicit
   within-response dedup/STNP review before both could be persisted.
10. Source budget, backoff, and sustained multi-request capacity remain unproven.

## 12. Handoff Decision

**Is V2-2 sorted enough to move to V2-3 design?** Yes, for design only. The bounded
live audit measured the current real path and preserved all locks. V2-2 remains
`COMPLETE_WITH_BLOCKERS`; it is not near-perfect.

V2-3 must carry forward:

- the three-candidate command cap;
- one-channel and daily-coverage uncertainty;
- missing age, creation, 15m, and price-change fields;
- absent real A2/A3 differentiation and unproven A4 classification;
- within-response duplicate-mint/STNP risk;
- migration 025 deployment/readiness;
- source-budget/backoff and sustained-capacity design;
- explicit separation between source-universe size, persisted candidates, and
  selection-batch size.

Before V2-4/V2-5 implementation/proof:

- define a bounded multi-channel request budget and hard stop contract;
- preserve Source Governor and Central Scheduler boundaries;
- add or prove normalized fields required for A2/A3/A4;
- define within-response mint/pair dedup and STNP handling;
- ensure selection schema readiness without ad hoc proof-only setup;
- prove tracking handoff without executing memory generation;
- retain a zero-downstream-delta assertion.

Before discovery/selection can be called near-perfect, Printer must prove bounded
repeatable multi-channel collection, measurable coverage, high critical-field
completeness, real A1/A2/A3/A4 differentiation, balanced bucket availability,
same-response dedup safety, source-rate-limit behavior, and deterministic selection
reasons across repeated proof runs.

## 13. Final Conclusion

`V2-2 Discovery/Selection Foundation: COMPLETE_WITH_BLOCKERS`

The real governed path is safe, fast for one request, source-traced, and capable of
feeding tracking and V2-2C selection on an isolated DB. It is not capacity-complete:
the command persists only three candidates, samples one channel at a time, and lacks
critical fields for fast-event differentiation. The final quota pass demonstrates
selection correctness, not broad memory-diet readiness.

V2-3 design may proceed while carrying every blocker above. V2-4/V2-5 implementation
or proof must not claim complete discovery capacity until those blockers are
resolved and re-measured. Memory generation, retrieval, paper decisions,
BUY/SELL/HOLD, positions, trades, audits, and PnL remain locked.
