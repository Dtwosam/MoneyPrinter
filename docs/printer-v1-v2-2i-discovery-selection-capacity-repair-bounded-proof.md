# Printer V1 V2-2I Discovery/Selection Capacity Repair Bounded Proof

Status: `BOUNDED PROOF`

Final verdict:

`V2-2I Discovery/Selection Capacity Repair Bounded Proof: PROOF_PASS_WITH_BLOCKERS`

V2-3 remains paused. This proof measures V2-2H on an isolated database copy. It
does not generate memory, activate retrieval, create paper decisions, unlock
BUY/SELL/HOLD, create positions, trades, paper trade audits, or PnL.

## 1. Authority and Lane Boundary

This proof used the required source stack together:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-assistant-active-build-order-anchor.md`
- `docs/printer-v1-v2-2-live-discovery-selection-capacity-audit.md`
- `docs/printer-v1-v2-2g-discovery-selection-capacity-repair-design.md`
- `docs/printer-v1-v2-2h-discovery-selection-repair-implementation-closeout.md`

The proof used only READY GeckoTerminal channels. PumpPortal and PumpSwap remained
NOT_READY and were not called. No direct API call bypassed Source Governor. The
persistent DB was not mutated.

## 2. Run Setup

| Item | Result |
|---|---|
| Discovery command | `printer-discover-candidates-once` through `main_discover_candidates_once()` |
| Selection path | V2-2C `selection_batch.py` functions on newly persisted proof rows |
| DB mode | Isolated proof DB copied from the current persistent DB |
| Persistent DB | `data/printer_v1.sqlite3`, read/hash verification only |
| Proof DB | `data/printer_v1_v2_2i_proof.sqlite3` |
| Migrations | Existing migrations applied through `printer_v1.db.apply_migrations()` to proof DB only |
| Source | `geckoterminal` |
| Planned channels | New-pool discovery and trending-pool reference |
| Maximum candidates | 20 |
| Maximum source requests | 2 |
| Per-request timeout | 5 seconds |
| Operator approved | Yes |
| Chain | Solana only |
| Started at | `2026-07-09T06:37:27.653781+00:00` |
| Ended at | `2026-07-09T06:37:31.516852+00:00` |
| Measured governed request span | 3.863071 seconds |
| Source Governor | Confirmed: both READY plan items used `execute_source_request_with_governor()` |
| Central Scheduler | Existing discovery handoff created bounded follow-up rows; no job was executed |

Proof command arguments:

```text
--db-path data/printer_v1_v2_2i_proof.sqlite3
--operator-approved
--chain solana
--source-name geckoterminal
--request-kind geckoterminal_new_pool_discovery
--max-candidates 20
--max-source-requests 2
--timeout-seconds 5
--request-key v2-2i-bounded-proof-20260709
--format json
```

The copied DB was one migration behind. Migration 025 was applied to the proof
copy through the normal migration runner, creating empty selection-batch tables
before the proof. No persistent schema changed.

## 3. Source-Budget Metrics

The command's `source_budget_report` returned:

| Metric | Result |
|---|---:|
| `max_source_requests` | 2 |
| `source_requests_planned` | 2 |
| `source_requests_attempted` | 2 |
| `source_responses_received` | 2 |
| `source_failures` | 0 |
| `source_failure_rate` | 0.0 |

Channel results:

| Metric | Result |
|---|---|
| `source_channels_planned` | `geckoterminal_new_pool_discovery`, `geckoterminal_trending_pool_reference` |
| `source_channels_sampled` | `geckoterminal_new_pool_discovery`, `geckoterminal_trending_pool_reference` |
| `source_channels_not_ready` | None in this two-channel plan |
| `source_channels_failed` | None |
| Candidates seen by source | `geckoterminal`: 40 |
| Candidates seen by new-pool channel | 20 |
| Candidates seen by trending channel | 20 |
| Candidates persisted by source | `geckoterminal`: 20 |
| Candidates persisted by new-pool channel | 12 |
| Candidates persisted by trending channel | 8 |

PumpPortal and PumpSwap remain globally NOT_READY for live execution, but they were
not part of this GeckoTerminal-only two-request plan. DexScreener was not needed to
prove multi-channel plumbing because both READY GeckoTerminal channels completed.

## 4. Candidate-Stage Metrics

The command's `candidate_stage_report` returned:

| Metric | Result |
|---|---:|
| `candidates_seen_total` | 40 |
| `candidates_normalized_total` | 40 |
| `candidates_persisted_total` | 20 |
| `candidates_rejected_pre_persistence` | 20 |
| `candidates_considered_for_selection` | `NOT_MEASURED` by discovery command |
| `candidates_selected` | `NOT_MEASURED` by discovery command |
| `candidates_rejected_by_selection` | `NOT_MEASURED` by discovery command |

The separate V2-2C proof supplied the selection-stage values:

- Candidates considered: 20
- Candidates selected into the assembled proof batch: 10
- Candidates rejected by selection: 10

The 20 pre-persistence rejections consist of:

- 6 WATCH_ONLY candidates rejected by the 15m proof-cycle intake gate.
- 1 existing token/pair duplicate.
- 10 candidates rejected after the 20-candidate persistence cap was reached.
- 3 unresolved within/cross-response STNP candidates rejected before persistence.

The wider cap worked: the command persisted 20 candidates instead of the old cap
of 3.

## 5. Age and Activity Metrics

The command's `age_activity_report` covered all 40 normalized candidates:

### Age buckets

| Age bucket | Count |
|---|---:|
| `AGE_UNKNOWN` | 40 |
| All known age buckets combined | 0 |

### Activity buckets

| Activity bucket | Count |
|---|---:|
| `ACTIVITY_HIGH` | 20 |
| `ACTIVITY_MEDIUM` | 11 |
| `ACTIVITY_LOW` | 9 |
| `ACTIVITY_DEAD` | 0 |
| `ACTIVITY_REVIVING` | 0 |
| `ACTIVITY_UNKNOWN` | 0 |

### Priority and requested summary counts

| Metric | Result |
|---|---:|
| `UNKNOWN_TIER_5` | 40 |
| Recent-active candidates | 0 |
| Old-active candidates | 0 |
| Low-volume/activity candidates | 9 |
| Candidates under $200 24h volume | 6 |
| Dead/low-activity candidates | 0 dead; 9 low |
| Revival candidates | 0 |
| Unknown age count | 40 |
| Unknown activity count | 0 |

Activity classification is now useful, but recent/old prioritization cannot work
on this source sample because `token_age_seconds` remains unknown for every row.
Pair age is known, but the current age bucket intentionally uses token age.

## 6. Field-Completeness Metrics

Denominator: 40 normalized candidates.

| Field | Missing | Missing % | Old audit | Change |
|---|---:|---:|---:|---|
| `token_created_at` | 40 | 100.0% | 100.0% | No improvement |
| `pair_created_at` | 0 | 0.0% | 100.0% | Improved |
| `token_age_seconds` | 40 | 100.0% | 100.0% | No improvement |
| `pair_age_seconds` | 0 | 0.0% | 100.0% | Improved |
| `price_change_5m` | 0 | 0.0% | 100.0% | Improved |
| `price_change_15m` | 40 | 100.0% | 100.0% | No improvement |
| `price_change_1h` | 0 | 0.0% | 100.0% | Improved |
| `price_change_24h` | 0 | 0.0% | 100.0% | Improved |
| `volume_15m` | 40 | 100.0% | 100.0% | No improvement |

V2-2H repaired pair creation/age and 5m/1h/24h price-change normalization for
real GeckoTerminal payloads. Token creation/age and native 15m fields remain absent.

## 7. Within-Response Integrity Metrics

The aggregated `within_response_integrity_report` returned:

| Metric | Result |
|---|---:|
| Duplicate pair count | 0 |
| Duplicate mint count | 3 |
| STNP event count | 3 |
| Duplicate rejections | 0 |
| STNP rejections | 3 |

All three STNP events were labeled
`STNP_WITHIN_RESPONSE_UNRESOLVED` and rejected before persistence. A read-only
post-check found zero duplicate token mints among the 20 newly persisted rows.
No unresolved STNP candidate reached persistence.

This is a direct improvement over the old audit, which observed same-mint/new-pair
risk without a proven within-response gate.

## 8. Source/Channel Attribution Proof

Stored discovery rows matched `source_budget_report` exactly:

| Stored source channel | Source response ID | Persisted rows |
|---|---:|---:|
| `GECKOTERMINAL_NEW_POOL` | 1072 | 12 |
| `GECKOTERMINAL_TRENDING_POOL` | 1073 | 8 |

Verification:

- Each persisted candidate retained its actual source channel.
- Each persisted candidate retained the matching source response ID.
- No trending candidate collapsed into the primary new-pool channel.
- Stored counts of 12 and 8 exactly match the source-budget persisted counts.
- Total stored rows, 20, exactly match `candidates_persisted_total`.

V2-2H.6 attribution repair passed on real governed responses.

## 9. V2-2C Selection Proof

The proof loaded only the 20 newly persisted discovery candidates. It used V2-2C
bucket assignment, lifecycle gate, WATCH_ONLY promotion gate, quota validation,
batch-item construction, universe summary, and selection-batch persistence.

### Selection totals

| Metric | Result |
|---|---:|
| Candidates considered | 20 |
| Candidates selected into assembled batch | 10 |
| Candidates rejected | 10 |
| Selection rate | 50.0% |
| Rejection rate | 50.0% |

### Selected by bucket

| Bucket | Count |
|---|---:|
| B1 | 4 |
| B3 | 1 |
| B5 | 1 |
| C1 | 3 |
| C2 | 1 |

### Selected by asset class

| Asset class | Count |
|---|---:|
| `VOLUME_RISING` | 4 |
| `HOT_TRENDING_PAIR` | 1 |
| `CONSOLIDATION` | 1 |
| `LIQUIDITY_RISING` | 3 |
| `LIQUIDITY_FALLING` | 1 |

### Selected by age, activity, source, and channel

| Dimension | Counts |
|---|---|
| Age bucket | `AGE_UNKNOWN`: 10 |
| Activity bucket | `ACTIVITY_MEDIUM`: 8; `ACTIVITY_LOW`: 2 |
| Source | `geckoterminal`: 10 |
| New-pool channel / response 1072 | 8 |
| Trending channel / response 1073 | 2 |
| Recent-active selected | 0 |
| Old-active selected | 0 |
| Low-activity selected | 0 by priority-tier logic; 2 carry `ACTIVITY_LOW` |

### Rejections and quota

| Metric | Result |
|---|---|
| Rejected by reason | `BATCH_QUOTA_EXCEEDED`: 10 |
| Reason detail | A1 candidates had no A2/A3/A4 counterpart |
| Final quota result | FAIL |
| Quota violation 1 | `MISSING_D1_DEAD_TOKEN_REQUIRED_FOR_6PLUS_BATCH` |
| Quota violation 2 | `MISSING_WATCH_ONLY_REQUIRED_FOR_6PLUS_BATCH` |

The selected set is materially more diverse than the old `{B5, B5}` baseline:
it spans five buckets and five asset classes across two channels. It is not a
quota-valid final batch because:

- no D1 dead-token candidate existed in the live sample; and
- discovery persistence excludes WATCH_ONLY candidates from this 15m proof-cycle
  intake, leaving no WATCH_ONLY row available to satisfy the six-plus quota.

The proof did not force diversity or weaken quota rules. The assembled batch is
audit evidence, not an approved memory-growth batch.

Old/legacy/low-volume tokens did not dominate by measured age because age was
unknown. Two selected candidates had low activity. No D1 or revival sample was
available.

## 10. Fast-Event Proof

Across all 40 normalized candidates:

| Bucket | Count |
|---|---:|
| A1 | 20 |
| A2 | 0 |
| A3 | 0 |
| A4 | 0 |

Across the 20 persisted candidates, 10 were A1 and were rejected from the
assembled selection because no A2/A3/A4 counterpart existed.

Findings:

- A2 is now technically possible because real normalized rows include
  `price_change_5m`; no candidate in this sample met the full A2 conditions.
- A3 remains unavailable from this real sample because
  `token_age_seconds` is missing for all candidates, even though
  `price_change_1h` is now present.
- A4 remains helper-only and is not wired into the main single-candidate
  selection path because prior candidate context is required.
- Missing `price_change_5m` improved from 100% to 0%.
- Missing `token_age_seconds` remained at 100%.
- Real fast-event output remains A1-only for this proof.

## 11. Row-Delta Lock Proof

### Expected proof-DB deltas

| Table | Before | After | Delta |
|---|---:|---:|---:|
| `printer_source_requests` | 1118 | 1120 | +2 |
| `printer_source_responses` | 1071 | 1073 | +2 |
| `printer_source_failures` | 47 | 47 | 0 |
| `printer_discovery_candidates` | 15 | 35 | +20 |
| `printer_tracking_queue` | 15 | 35 | +20 |
| `printer_selection_batches` | 0 | 1 | +1 |
| `printer_selection_batch_items` | 0 | 20 | +20 |
| `printer_scheduler_jobs` | 989 | 1009 | +20 |

The 20 scheduler rows are the existing discovery-to-tracking follow-up handoff.
No scheduler job was executed.

### Required zero downstream deltas

| Table | Before | After | Delta |
|---|---:|---:|---:|
| `printer_memory_windows` | 156 | 156 | 0 |
| `printer_memory_retrieval_queries` | 10 | 10 | 0 |
| `printer_memory_retrieval_matches` | 0 | 0 | 0 |
| `printer_paper_decisions` | 2 | 2 | 0 |
| `printer_paper_positions` | 0 | 0 | 0 |
| `printer_paper_trade_events` | 0 | 0 | 0 |
| `printer_paper_trade_audits` | 0 | 0 | 0 |
| `printer_paper_pl_calculations` | Table absent | Table absent | 0 / not applicable |

The persistent DB SHA-256 was identical before and after:

`97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB`

The persistent DB was not mutated.

## 12. Comparative Benchmark

| Measure | Old V2-2 live audit | V2-2I proof | Result |
|---|---:|---:|---|
| Source requests | 1 | 2 | Improved and bounded |
| Channels sampled | 1 | 2 | Improved |
| Candidates seen | 20 | 40 | Doubled |
| Candidates persisted | 3 | 20 | Increased by 17 |
| Candidate cap | 3 | 20 used; 50 supported | Repaired |
| Selection candidates considered | 3 | 20 | Increased |
| Selection result | 2 B5 rows | 10 rows across B1/B3/B5/C1/C2 | More diverse, quota still fails |
| Missing pair creation/age | 100% | 0% | Repaired |
| Missing 5m/1h/24h price changes | 100% | 0% | Repaired |
| Missing token creation/age | 100% | 100% | Still blocked |
| Missing 15m price/volume | 100% | 100% | Still blocked |
| Per-channel attribution | Primary-channel collapse risk | 12 new-pool + 8 trending stored correctly | Repaired |
| Within-response STNP | Risk observed | 3 events, all 3 blocked; zero persisted duplicate mints | Repaired conservatively |
| Source failures | 0 | 0 | Stable |
| Downstream lock deltas | 0 | 0 | Preserved |

V2-2H produced measurable improvements in capacity, channel coverage,
normalization, attribution, and STNP safety. It did not complete age-based priority,
15m-field completeness, A3/A4 differentiation, or quota-valid diet assembly.

## 13. Build-Readiness Audit Scores

These are build-readiness audit scores only. They are not token scores, trading
scores, confidence percentages, BUY probabilities, rankings, or weighted decision
logic.

| Area | Score | Reason |
|---|---:|---|
| Discovery capacity | 8 / 10 | 40 seen and 20 persisted in one bounded run; cap now configurable |
| Source/channel coverage | 7 / 10 | Two READY channels proved; still one provider and no PumpPortal/PumpSwap |
| Field completeness | 6 / 10 | Pair age and price-change repair passed; token age and 15m fields absent |
| Selection correctness | 7 / 10 | Gates and reasons worked; assembled batch correctly exposes quota failure |
| Memory-diet balance | 7 / 10 | Five buckets/classes, but no D1, WATCH_ONLY, trap/failure, or revival |
| Fast-event differentiation | 4 / 10 | A2 input repaired, but sample remains A1-only; A3/A4 blocked |
| Source/channel attribution | 10 / 10 | Stored 12/8 channel split exactly matches source-budget report |
| Safety/lock preservation | 10 / 10 | Isolated DB only; every downstream delta zero |
| Overall V2-2 discovery/selection readiness | 7 / 10 | Strong repair proof with explicit data/diet blockers |

## 14. Blockers

1. `token_created_at` and `token_age_seconds` remain missing for 100% of this
   real sample.
2. `price_change_15m` and `volume_15m` remain missing for 100%.
3. Age buckets and recent-active tiers remain unknown despite useful activity
   buckets.
4. A2 had no qualifying sample; A3 cannot classify without token age.
5. A4 remains helper-only because prior-candidate context is not wired.
6. The selected 10-item set fails the D1 and WATCH_ONLY six-plus quota gates.
7. Discovery persistence's 15m proof-cycle gate excludes WATCH_ONLY rows, which
   conflicts with selection quota requirements for batches of six or more.
8. No dead-token or revival sample appeared in the two live channels.
9. Only GeckoTerminal was exercised; DexScreener and sustained cross-provider
   budgeting were not measured in this proof.
10. REVIVAL and DISTINCT_EVIDENCE STNP still require external DB context.
11. PumpPortal and PumpSwap remain NOT_READY for live source plumbing.
12. The persistent DB remains behind migration 025; the proof copy required the
    normal migration path before selection persistence.

## 15. Handoff Decision

### Is V2-2 close enough to move to V2-2J?

Yes. V2-2I proved the implemented repairs with real governed data and preserved
all locks. The result is `PROOF_PASS_WITH_BLOCKERS`, so V2-2J may document the
measured pass and carry the blockers forward.

### Is V2-3 still paused?

Yes. V2-3 remains paused until V2-2J closeout is completed and accepted by the
operator.

### What V2-2J must document

- The two-request/two-channel capacity proof.
- The increase from 3 to 20 persisted candidates.
- Exact 12/8 channel attribution.
- Field improvements and remaining 100%-missing fields.
- Three STNP events blocked with zero persisted duplicate mints.
- The five-bucket selection improvement.
- The D1/WATCH_ONLY quota failure.
- A2/A3/A4 limitations.
- Persistent migration-025 readiness.
- Zero downstream deltas and unchanged persistent DB hash.

### What must remain blocked before V2-3/V2-4

- No memory generation or window creation.
- No retrieval activation.
- No paper decisions.
- No BUY/SELL/HOLD.
- No positions, trades, paper trade audits, or PnL.
- No claim of quota-valid automatic memory-diet assembly.
- No claim that age prioritization or A2/A3/A4 differentiation is complete.
- No live PumpPortal/PumpSwap claim.
- No unbounded or paid source expansion.

V2-3 design may be reconsidered only after V2-2J operator acceptance. V2-4
implementation must explicitly account for the unresolved fields, quota conflict,
prior-context A4/STNP requirements, schema readiness, and bounded source budget.

### Before discovery/selection can be called near-perfect

Printer still needs:

- real token creation/age evidence;
- real 15m price-change and volume evidence;
- a proof containing genuine A2/A3 and prior-context A4 examples;
- a quota-valid selected batch containing D1 and WATCH_ONLY representation;
- revival and distinct-evidence STNP classification using safe DB context;
- a bounded cross-provider proof, including DexScreener if approved;
- explicit resolution of WATCH_ONLY persistence versus six-plus quota needs;
- persistent migration readiness;
- repeated bounded runs proving stable source-budget and attribution behavior.

## 16. Test and Check Results

Targeted suites:

- `tests/test_v2_2h6_source_channel_attribution.py`: 21 passed.
- `tests/test_v2_2h5_multi_request_source_budget.py`: 73 passed.
- `tests/test_v2_2h4_within_response_stnp.py`: 46 passed, 121 subtests passed.
- `tests/test_v2_2h3_field_normalization_fast_events.py`: 67 passed, 44 subtests passed.
- `tests/test_v2_2h2_age_activity_recent_priority.py`: 66 passed, 27 subtests passed.
- `tests/test_v2_2h1_discovery_selection_capacity_repair.py`: 25 passed, 11 subtests passed.
- `tests/test_v2_2c_selection_batch.py`: 112 passed.
- `tests/test_post_rc_controlled_discovery_cycle.py`: 8 passed.

Total: 418 tests passed, plus 203 separately reported subtests. No test failed.

Each pytest run emitted a cache-write warning for `.pytest_cache`; this did not
affect test results, source calls, the proof DB, or the persistent DB.

## 17. Final Conclusion

`V2-2I Discovery/Selection Capacity Repair Bounded Proof: PROOF_PASS_WITH_BLOCKERS`

The V2-2H repairs work in a real bounded governed run. Capacity increased,
multi-channel collection executed within budget, per-channel attribution remained
correct, several critical fields were repaired, and unresolved STNP candidates
were blocked. The selection pool is significantly more diverse than the old
two-B5 result.

The system is not yet near-perfect. Token age and 15m fields remain absent, the
real sample remains A1-only in fast-event terms, A4 remains helper-only, and the
assembled selection fails D1 and WATCH_ONLY quota requirements.

V2-2J closeout is allowed. V2-3 remains paused until that closeout is accepted.
All memory, retrieval, paper, financial, live-execution, paid-source, scoring,
ranking, confidence, weighted-logic, embedding, and vector capabilities remain
locked.
