# Printer V1 V2-2K Discovery/Selection Practical Coverage Diagnostic Audit

Status: `PRACTICAL DIAGNOSTIC AUDIT`

Final verdict:

`V2-2K Discovery/Selection Practical Coverage Diagnostic Audit: AUDIT_COMPLETE_WITH_BLOCKERS`

V2-2J and V2-3 remain paused. This audit measures current discovery and selection
coverage. It does not implement repairs, generate memory, activate retrieval,
create paper decisions, or unlock any financial capability.

## 1. Authority and Audit Boundary

The audit used the active source stack together:

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
- `docs/printer-v1-v2-2i-discovery-selection-capacity-repair-bounded-proof.md`

Only free/public, operator-approved, bounded READY paths were called. Every live
request used the existing Source Governor path. PumpPortal and PumpSwap were not
forced. No scheduler job was executed. The persistent DB was not mutated.

## 2. Source Capability Matrix

The registry contains 11 source definitions. Four sources are accepted by the
controlled discovery CLI. Of those four, two providers and three channels have a
READY live HTTP path today.

| Source/channel | Registered | Command path | Live status | Free/public | V2-2I | V2-2K | Expected output |
|---|---|---|---|---|---|---|---|
| GeckoTerminal new pools | YES | YES | READY | YES | YES | YES | Launch/new-pool discovery |
| GeckoTerminal trending pools | YES | YES | READY | YES | YES | YES | Trending/reference pools |
| DexScreener token search | YES | YES | READY | YES | NO | YES | Search results |
| PumpPortal launch stream | YES | Contract/fixture path | NOT_READY | YES | NO | NO | Pump.fun launches |
| PumpPortal migration stream | YES | Contract/fixture path | NOT_READY | YES | NO | NO | Migration events |
| PumpSwap pool confirmation | YES | Contract/fixture path | NOT_READY | YES | NO | NO | Read-only confirmation |
| PumpSwap migration reference | YES | Contract/fixture path | NOT_READY | YES | NO | NO | Migration/reference |
| Solana RPC references | YES | Evidence/reference commands, not discovery CLI | NOT A DISCOVERY PATH | Public or operator-supplied free | NO | NO | Mint/holder/pool references |
| Helius free tier references | YES | No active discovery command/adapter found | NOT_READY/OPTIONAL | Free tier optional | NO | NO | On-chain reference |
| Jupiter quote | YES | Paper-evidence path only | PAPER-REALISM ONLY | YES | NO | NO | Quote-only, never discovery |

### Capability contribution

| Source/channel | Token age | Native 15m fields | Dead tokens | WATCH_ONLY | Revival/migration |
|---|---|---|---|---|---|
| GeckoTerminal new pools | No token age; pair age yes | No | Possible but none observed as D1 | Yes, observed | No explicit revival/migration |
| GeckoTerminal trending | No token age; pair age yes | No | Possible but none observed as D1 | Possible | No explicit revival/migration |
| DexScreener search | No token age; pair age mostly available | No | Yes, raw D1 observed | Yes, observed | Not explicit in current search |
| PumpPortal launch | Event timing may support future age design | No | Not its primary purpose | Classification may yield WATCH_ONLY | Launch only |
| PumpPortal migration | Event timing may support future age design | No | Not primary | Possible | Yes, intended migration feed |
| PumpSwap confirmation/migration | Pair reference only | No | Potential confirmation evidence | Possible | Yes, intended migration confirmation |
| Solana RPC / Helius | Current paths do not derive token creation age | No | Protection/reference only | No discovery output | Historical work would be new scope |
| Jupiter quote | No | No | No | No | No; paper realism only |

Static conclusions:

- READY discovery providers: 2 of 4 CLI-supported providers.
- READY discovery channels: 3.
- NOT_READY discovery channels in the plan catalog: 4
  (two PumpPortal and two PumpSwap).
- Solana RPC, Helius, and Jupiter are not candidate-discovery feeds.
- No current single-response discovery source provides native 15m change/volume.

## 3. Bounded Audit Setup

| Item | Result |
|---|---|
| Persistent DB | `data/printer_v1.sqlite3`, hash verification only |
| Proof DB | `data/printer_v1_v2_2k_practical_coverage_audit.sqlite3` |
| DB mode | Isolated copy |
| Migration handling | Existing migrations applied to proof DB only through `apply_migrations()` |
| Operator approval | Explicit |
| Chain | Solana only |
| Memory/retrieval/paper paths | Not run |

### Run A: GeckoTerminal

```text
source_name=geckoterminal
request_kind=geckoterminal_new_pool_discovery
max_candidates=20
max_source_requests=2
timeout_seconds=5
```

- Channels: new-pool discovery and trending-pool reference.
- Started: `2026-07-09T07:06:49.069210+00:00`.
- Ended: `2026-07-09T07:06:54.220542+00:00`.
- Governed request span: 5.151332 seconds.

### Run B: DexScreener

```text
source_name=dexscreener
query=pump
max_candidates=20
max_source_requests=1
timeout_seconds=5
```

- Channel: `DEXSCREENER_SEARCH`.
- Started: `2026-07-09T07:07:10.851270+00:00`.
- Ended: `2026-07-09T07:07:13.818620+00:00`.
- Governed request span: 2.967350 seconds.

Combined first-request-to-last-response span, including the operator-controlled
gap between commands: 24.749410 seconds.

## 4. Source-Budget Metrics

### Run A

| Metric | Result |
|---|---:|
| Requests planned / attempted | 2 / 2 |
| Responses | 2 |
| Failures | 0 |
| Failure rate | 0.0% |
| Candidates seen | 40 |
| Candidates persisted | 20 |
| New-pool seen / persisted | 20 / 12 |
| Trending seen / persisted | 20 / 8 |

### Run B

| Metric | Result |
|---|---:|
| Requests planned / attempted | 1 / 1 |
| Responses | 1 |
| Failures | 0 |
| Failure rate | 0.0% |
| Candidates seen | 30 |
| Candidates persisted | 0 |
| DexScreener search seen / persisted | 30 / 0 |

### Combined

| Metric | Result |
|---|---:|
| Requests planned / attempted | 3 / 3 |
| Responses | 3 |
| Failures | 0 |
| Failure rate | 0.0% |
| Providers sampled | 2 |
| Channels sampled | 3 |
| Candidates seen | 70 |
| Candidates persisted | 20 |

DexScreener was operationally READY and source-governed, but its generic `pump`
query was not practically productive:

- 13 of 30 raw candidates were non-Solana.
- 20 duplicate-mint/STNP events were rejected.
- Remaining clean candidates were duplicate-existing, WATCH_ONLY, or non-Solana.
- Zero DexScreener candidates persisted.

This is measured cross-provider coverage, not successful cross-provider selection.

## 5. Candidate-Stage Metrics

| Stage | Run A | Run B | Combined |
|---|---:|---:|---:|
| Seen | 40 | 30 | 70 |
| Normalized | 40 | 30 | 70 |
| Persisted | 20 | 0 | 20 |
| Rejected before persistence | 20 | 30 | 50 |
| Considered by separate V2-2C selection | N/A | N/A | 20 |
| Selected into assembled proof batch | N/A | N/A | 13 |
| Rejected by selection | N/A | N/A | 7 |

Candidate-stage visibility works. Practical persistence remains entirely dependent
on GeckoTerminal in this audit.

## 6. Token-Kind and Asset-Class Audit

Denominator: 70 normalized candidates.

### Asset classes

| Asset class | Count |
|---|---:|
| `FAST_PUMP` | 22 |
| `VOLUME_DECAYING` | 15 |
| `CONSOLIDATION` | 10 |
| `VOLUME_RISING` | 7 |
| `LIQUIDITY_RISING` | 7 |
| `LIQUIDITY_FALLING` | 4 |
| `DEAD_TOKEN` | 3 |
| `LIQUIDITY_REMOVED` | 2 |

### Primary buckets

| Bucket | Count |
|---|---:|
| A1 | 22 |
| B1 | 7 |
| B2 | 4 |
| B4 | 11 |
| B5 | 10 |
| C1 | 7 |
| C2 | 4 |
| C3 | 2 |
| D1 | 3 |
| A2 / A3 / A4 | 0 / 0 / 0 |

### Discovery action and reasons

| Discovery action | Count |
|---|---:|
| `TRACK_FAST` | 22 |
| `TRACK_NORMAL` | 22 |
| `WATCH_ONLY` | 13 |
| `INSTANT_REJECT_MEMORY_ONLY` | 13 |

| Discovery reason | Count |
|---|---:|
| `clean_solana_candidate_with_basic_market_fields` | 22 |
| `fresh_solana_candidate_with_liquidity_and_activity` | 22 |
| `unsupported_chain_or_unusable_pair` | 13 |
| `no_recent_activity_pulse_for_memory_growth` | 6 |
| `partial_market_fields_or_low_activity` | 6 |
| `insufficient_activity_for_memory_growth` | 1 |

### Source, channel, lane, status, quality

- Raw by source: GeckoTerminal 40; DexScreener 30.
- Raw by channel: new pools 20; trending 20; DexScreener search 30.
- Raw Solana candidates: 57.
- Raw non-Solana candidates: 13.
- Persisted source: GeckoTerminal 20; DexScreener 0.
- Persisted channel: new pools 12; trending 8.
- Persisted lanes: `TRACK_NORMAL` 13; `TRACK_FAST` 7.
- Persisted status: `COMPLETE` 20.
- Persisted quality: `CLEAN_DATA` 20.

### Practical token-kind presence

| Kind | Presence |
|---|---|
| Fresh/new-pool | PRESENT: 20 raw, 12 persisted |
| Trending | PRESENT: 20 raw, 8 persisted |
| High activity | PRESENT: 22 raw |
| Medium activity | PRESENT: 26 raw |
| Low activity | PRESENT: 14 raw |
| Dead/near-dead | PRESENT: 3 raw D1, only 1 Solana; 0 persisted |
| Revival | ABSENT |
| Migration | ABSENT; NOT_READY channels not run |
| Legacy/reference | Trending provides older pair references, but token age remains unknown |
| WATCH_ONLY | PRESENT: 13 raw; 0 persisted |
| A1 | PRESENT: 22 |
| A2/A3/A4 | ABSENT |
| B buckets | PRESENT |
| C buckets | PRESENT |
| D bucket | D1 present raw only |
| E buckets | ABSENT |
| Under $200 24h volume | PRESENT: 20 |

The raw universe is meaningfully broader than the persisted/selected universe.
Important protective lessons are removed before selection.

## 7. Activity Audit

### Activity buckets

| Activity bucket | Raw count |
|---|---:|
| `ACTIVITY_HIGH` | 22 |
| `ACTIVITY_MEDIUM` | 26 |
| `ACTIVITY_LOW` | 14 |
| `ACTIVITY_DEAD` | 3 |
| `ACTIVITY_REVIVING` | 0 |
| `ACTIVITY_UNKNOWN` | 5 |

Selected activity:

- `ACTIVITY_MEDIUM`: 12
- `ACTIVITY_LOW`: 1
- High, dead, reviving, unknown: 0

Rejected-by-selection activity:

- `ACTIVITY_HIGH`: 7

Other activity measurements:

- Under $200 24h volume: 20.
- Low-activity candidates: 14.
- Dead candidates: 3.
- Revival candidates: 0.

### Volume distributions

| 5m volume bucket | Count |
|---|---:|
| Under $1 | 28 |
| $1-$100 | 7 |
| $100-$1,000 | 19 |
| $1,000-$10,000 | 13 |
| $10,000+ | 3 |

| 1h volume bucket | Count |
|---|---:|
| Under $1 | 22 |
| $1-$200 | 8 |
| $200-$1,000 | 11 |
| $1,000-$10,000 | 9 |
| $10,000-$100,000 | 16 |
| $100,000+ | 4 |

| 24h volume bucket | Count |
|---|---:|
| Under $1 | 7 |
| $1-$200 | 13 |
| $200-$1,000 | 10 |
| $1,000-$10,000 | 8 |
| $10,000-$100,000 | 4 |
| $100,000+ | 28 |

### Transaction distributions

| 5m transactions | Count |
|---|---:|
| 0 | 22 |
| 1-9 | 22 |
| 10-99 | 23 |
| 100+ | 3 |

| 1h transactions | Count |
|---|---:|
| 0 | 17 |
| 1-9 | 15 |
| 10-99 | 18 |
| 100-999 | 16 |
| 1,000+ | 4 |

### Liquidity distribution

| Liquidity bucket | Count |
|---|---:|
| Unknown | 5 |
| Under $500 | 3 |
| $500-$1,000 | 1 |
| $1,000-$5,000 | 17 |
| $5,000-$25,000 | 5 |
| $25,000-$100,000 | 13 |
| $100,000+ | 26 |

Activity breadth exists in raw data. Selection does not yet preserve dead or high
activity lessons in a quota-valid way.

## 8. Token-Age Audit

| Age bucket | Raw | Selected | Rejected by selection |
|---|---:|---:|---:|
| `AGE_0_24H` | 0 | 0 | 0 |
| `AGE_1_7D` | 0 | 0 | 0 |
| `AGE_7_14D` | 0 | 0 | 0 |
| `AGE_14_28D` | 0 | 0 | 0 |
| `AGE_28D_PLUS` | 0 | 0 | 0 |
| `AGE_UNKNOWN` | 70 | 13 | 7 |

- Recent-active candidates: 0.
- Old-active candidates: 0.
- All 70 candidates are `UNKNOWN_TIER_5`.
- Current age buckets derive from `token_age_seconds`, not pair age.
- Pair age is available for 69 of 70 candidates.

Pair age must not silently replace token age under the current design. A pair may
be new while its token is old, especially for same-token/new-pair cases. Pair age
could become a separate categorical context or a conservative fallback only after
an explicit design defines the distinction and STNP safety. Token age remains
blocked by source data.

## 9. Field-Completeness Audit

### Combined, denominator 70

| Field | Missing | Missing % |
|---|---:|---:|
| `token_created_at` | 70 | 100.0% |
| `pair_created_at` | 1 | 1.4% |
| `token_age_seconds` | 70 | 100.0% |
| `pair_age_seconds` | 1 | 1.4% |
| `price_change_5m` | 21 | 30.0% |
| `price_change_15m` | 70 | 100.0% |
| `price_change_1h` | 17 | 24.3% |
| `price_change_24h` | 5 | 7.1% |
| `volume_5m` | 0 | 0.0% |
| `volume_15m` | 70 | 100.0% |
| `volume_1h` | 0 | 0.0% |
| `volume_24h` | 0 | 0.0% |
| `txns_5m` | 0 | 0.0% |
| `txns_1h` | 0 | 0.0% |
| `fdv` | 3 | 4.3% |
| `market_cap` | 34 | 48.6% |
| `liquidity_usd` | 5 | 7.1% |

### GeckoTerminal, denominator 40

- Token creation/age missing: 40, 100%.
- Pair creation/age missing: 0, 0%.
- 5m/1h/24h price change missing: 0, 0%.
- 15m price change/volume missing: 40, 100%.
- 5m/1h/24h volume and transaction fields missing: 0.
- FDV missing: 0.
- Market cap missing: 31, 77.5%.
- Liquidity missing: 0.

### DexScreener, denominator 30

- Token creation/age missing: 30, 100%.
- Pair creation/age missing: 1, 3.3%.
- 5m price change missing: 21, 70.0%.
- 1h price change missing: 17, 56.7%.
- 24h price change missing: 5, 16.7%.
- 15m price change/volume missing: 30, 100%.
- 5m/1h/24h volume and transaction fields missing: 0.
- FDV and market cap missing: 3 each, 10.0%.
- Liquidity missing: 5, 16.7%.

DexScreener improves market-cap availability but is worse than GeckoTerminal for
short-window price-change completeness in this query. It does not improve token
age or 15m fields.

Native 15m fields are unavailable from both single-response shapes. A real 15m
change/volume value requires staged governed observations or a specifically
approved source field. It must not be fabricated by copying 5m or 1h values.

## 10. Fast-Event Audit

| Fast bucket | Raw count |
|---|---:|
| A1 | 22 |
| A2 | 0 |
| A3 | 0 |
| A4 | 0 |

- Seven persisted A1 candidates were rejected by selection because no A2/A3/A4
  counterpart existed.
- A2 can occur in code when `price_change_5m`, volume, and liquidity meet the
  categorical rule. No real candidate in this audit met it.
- A3 remains blocked because all 70 candidates lack `token_age_seconds`.
- A4 remains helper-only because prior-candidate context is not wired into the
  main selection path.

Exact blocked evidence:

- A2: qualifying negative 5m reversal plus fast-tier volume/liquidity was absent.
- A3: token age is missing; price-change evidence alone is insufficient.
- A4: prior and current candidate evidence must be compared at a context-aware
  call site.

Fast-event differentiation remains A1-only in practical live proof.

## 11. WATCH_ONLY, D1, and Quota Audit

| Metric | Result |
|---|---:|
| WATCH_ONLY seen raw | 13 |
| WATCH_ONLY rejected before persistence | At least 9 directly visible across command gate output; all 13 absent from persistence |
| WATCH_ONLY persisted | 0 |
| WATCH_ONLY considered by selection | 0 |
| D1 seen raw | 3 |
| Solana D1 seen raw | 1 |
| D1 persisted | 0 |
| D1 considered by selection | 0 |
| Final quota | FAIL |
| Quota violation | `MISSING_D1_DEAD_TOKEN_REQUIRED_FOR_6PLUS_BATCH` |
| Quota violation | `MISSING_WATCH_ONLY_REQUIRED_FOR_6PLUS_BATCH` |

The contradiction is confirmed:

1. `_select_discovery_candidates()` rejects WATCH_ONLY before persistence.
2. V2-2C requires at least one WATCH_ONLY item in a selected batch of six or more.
3. A normal discovery-to-persistence-to-selection path therefore cannot satisfy
   that quota without a separate audit-only candidate-pool handoff.

D1 absence is both source- and gate-related:

- GeckoTerminal produced no D1 in this sample.
- DexScreener raw data produced three D1 rows, including one Solana D1.
- DexScreener persisted zero rows because its candidate pool was dominated by
  duplicate-mint/STNP, non-Solana, duplicate-existing, and WATCH_ONLY outcomes.

Recommended direction, not implemented: design a non-tracking, audit-visible
candidate-pool handoff that allows WATCH_ONLY and valid Solana D1 lessons to be
considered by V2-2C without promoting them to active tracking or bypassing
discovery reasons. Alternatively, revise the quota semantics explicitly. The
current contradiction must not be solved by silently loosening either gate.

## 12. STNP and Duplication Audit

| Metric | Result |
|---|---:|
| Within-response duplicate pair events | 0 |
| Within-response duplicate mint events | 22 |
| Run A STNP events/rejections | 2 / 2 |
| Run B STNP events/rejections | 20 / 20 |
| Cross-response duplicate mints | 0 measured across response sets |
| Duplicate-pair rejections | 0 |
| Unresolved STNP persisted | NO |
| Duplicate mint persisted | NO |
| Migration cases | ABSENT / NOT SAMPLED |
| Revival cases | ABSENT |
| Distinct-evidence STNP cases | NOT MEASURED |

The conservative gate worked. The DexScreener result also reveals a practical
query-quality issue: many pairs for a small number of repeated mints make generic
search inefficient even when the safety gate correctly blocks them.

## 13. Selection Audit

The V2-2C audit used only the 20 newly persisted candidates.

| Metric | Result |
|---|---:|
| Considered | 20 |
| Selected into assembled proof batch | 13 |
| Rejected | 7 |
| Selection rate | 65.0% |
| Rejection rate | 35.0% |
| Quota result | FAIL |
| Quota-valid batch | NO |

Selected buckets:

- B1: 2
- B2: 1
- B5: 2
- C1: 5
- C2: 3

Selected asset classes:

- `VOLUME_RISING`: 2
- `VOLUME_DECAYING`: 1
- `CONSOLIDATION`: 2
- `LIQUIDITY_RISING`: 5
- `LIQUIDITY_FALLING`: 3

Selected dimensions:

- Age: `AGE_UNKNOWN` 13.
- Activity: `ACTIVITY_MEDIUM` 12; `ACTIVITY_LOW` 1.
- Tracking lane: `TRACK_NORMAL` 13.
- New-pool channel: 12.
- Trending channel: 1.
- DexScreener: 0.

Rejected by selection:

- `BATCH_QUOTA_EXCEEDED`: 7 A1 candidates.
- Rejected activity: `ACTIVITY_HIGH` 7.
- Rejected age: `AGE_UNKNOWN` 7.

Quota violations:

- `MISSING_D1_DEAD_TOKEN_REQUIRED_FOR_6PLUS_BATCH`
- `MISSING_WATCH_ONLY_REQUIRED_FOR_6PLUS_BATCH`

Compared with V2-2I, this batch has the same number of represented selected
buckets and asset classes: five each. It selects 13 instead of 10, but is more
concentrated in new-pool rows (12 of 13) and entirely TRACK_NORMAL. It is not
meaningfully closer to quota validity.

The assembled batch is dominated by:

- one provider: GeckoTerminal, 100%;
- one channel: new pools, 92.3%;
- one activity type: medium, 92.3%;
- unknown token age: 100%.

## 14. Blocker Discovery

| Blocker | Status | Evidence | Likely repair direction | Near-perfect blocker |
|---|---|---|---|---|
| Token creation/age 100% missing | CONFIRMED | 70/70 missing | Governed token-age evidence design; keep pair age distinct | YES |
| 15m price/volume 100% missing | CONFIRMED | 70/70 missing | Derive only from staged governed snapshots, not one payload | YES |
| Recent-active priority blocked | CONFIRMED | All 70 `AGE_UNKNOWN` / `UNKNOWN_TIER_5` | Resolve token age or explicitly design safe pair-age context | YES |
| A3 blocked | CONFIRMED | Token age missing for all candidates | Token-age evidence first | YES |
| A4 helper-only | CONFIRMED | No main-path prior-context call site | Context-aware A4 integration design | YES |
| D1/WATCH_ONLY quota fails | CONFIRMED | Both six-plus violations returned | Repair candidate-pool handoff/quota semantics | YES |
| WATCH_ONLY excluded pre-selection | CONFIRMED | 13 raw, 0 persisted/considered | Audit-only WATCH_ONLY handoff or explicit quota redesign | YES |
| No D1/revival selected | CONFIRMED | 3 raw D1, 0 persisted; revival 0 | Preserve valid D1 lessons; sample READY migration later | YES |
| DexScreener proof missing | RESOLVED AS MEASUREMENT; NEW PRODUCTIVITY BLOCKER | 30 seen, 0 persisted, 13 non-Solana, 20 STNP events | Solana-focused query/intake and repeated-mint handling design | YES |
| PumpPortal/PumpSwap NOT_READY | CONFIRMED | Plan catalog remains NOT_READY | Separate bounded transport implementation/proof later | YES |

New blocker:

`DEXSCREENER_GENERIC_QUERY_LOW_PRODUCTIVITY`

The provider is READY and governed, but the default generic query is not
Solana-focused enough and returns repeated-pair clusters. The system rejects these
safely, yet gains no selectable cross-provider candidates.

## 15. Practical Readiness Scores

These are build-readiness audit scores only. They are not token scores, trading
scores, confidence percentages, BUY probabilities, rankings, or weighted logic.

| Area | Score | Reason |
|---|---:|---|
| Source readiness | 7 / 10 | Three READY channels work; four discovery channels remain NOT_READY |
| Source/channel coverage | 7 / 10 | Two providers and three channels measured; only GeckoTerminal persisted |
| Candidate universe breadth | 8 / 10 | 70 rows and eight asset classes, including raw dead/decay/liquidity cases |
| Token-kind diversity | 7 / 10 | Broad B/C/D raw classes; no revival, migration, E, A2/A3/A4 |
| Activity coverage | 8 / 10 | High/medium/low/dead present; no revival |
| Age coverage | 1 / 10 | Token age unknown for all 70 |
| Field completeness | 6 / 10 | Core market fields strong; token age and 15m fields absent |
| Fast-event differentiation | 4 / 10 | A1 only in real output |
| WATCH_ONLY/D1 quota readiness | 2 / 10 | Raw lessons exist but cannot reach selection; quota fails structurally |
| Selection balance | 5 / 10 | Five categories, but one provider/channel/activity and unknown age dominate |
| Safety/lock preservation | 10 / 10 | Isolated DB, governed calls, zero downstream deltas |
| Overall near-perfect readiness | 6 / 10 | Safe and broader, but structurally unable to produce a quota-valid balanced batch |

## 16. Row-Delta Lock Proof

### Allowed proof-DB deltas

| Table | Before | After | Delta |
|---|---:|---:|---:|
| `printer_source_requests` | 1118 | 1121 | +3 |
| `printer_source_responses` | 1071 | 1074 | +3 |
| `printer_source_failures` | 47 | 47 | 0 |
| `printer_discovery_candidates` | 15 | 35 | +20 |
| `printer_tracking_queue` | 15 | 35 | +20 |
| `printer_selection_batches` | 0 | 1 | +1 |
| `printer_selection_batch_items` | 0 | 20 | +20 |
| `printer_scheduler_jobs` | 989 | 1009 | +20 |

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

Persistent DB SHA-256 before and after:

`97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB`

The persistent DB was not mutated.

## 17. Functionality Risks / Setbacks / Efficiency Blockers

| Risk | Practical effect | Current protection | Remaining work |
|---|---|---|---|
| WATCH_ONLY quota contradiction | Six-plus batch cannot pass through normal persisted pool | Quota fails honestly | Design audit-only candidate handoff or revise semantics explicitly |
| D1 lost before selection | Capital-protection lessons absent from selected diet | Raw reports expose D1 | Preserve valid Solana D1 without activating tracking |
| Generic DexScreener query | Cross-chain noise and repeated mints waste request budget | Solana and STNP gates block unsafe rows | Solana-focused query/intake design |
| Unknown token age | No recent/old priority or A3 | Unknown remains visible | Governed token-age evidence |
| Missing 15m fields | Cannot classify true 15m behavior at discovery time | Missing remains visible | Staged snapshot derivation |
| A4 helper-only | Failed-pump lessons absent | No false A4 classification | Prior-context integration design |
| Source concentration | Selected batch remains GeckoTerminal/new-pool dominated | Attribution is accurate | Productive second-provider path |
| NOT_READY launch/migration feeds | No direct migration/revival lesson supply | Not executed | Separate future transport lane |

## 18. Final Verdict

`V2-2K Discovery/Selection Practical Coverage Diagnostic Audit: AUDIT_COMPLETE_WITH_BLOCKERS`

Printer can safely execute three READY discovery channels across two providers.
It can normalize a broad raw universe and correctly reject non-Solana, duplicate,
and unresolved STNP rows. It cannot yet turn that breadth into a quota-valid,
balanced selection batch.

The most immediate blocker is not raw source capacity. It is the structural
candidate-pool handoff:

- WATCH_ONLY is required by six-plus selection quota but rejected before
  persistence.
- Raw D1 lessons exist but do not reach selection.
- The resulting batch cannot pass quota even with broader source coverage.

Token age, native 15m evidence, A3/A4, migration/revival, and productive
DexScreener intake remain important secondary blockers.

## 19. Next Recommended V2-2 Repair Lane

**Next recommended lane: `V2-2L - WATCH_ONLY / D1 Quota Semantics and Candidate-Pool Handoff Repair Design`.**

This should be design-only first. It must define how WATCH_ONLY and valid Solana
D1 candidates can remain audit-visible and eligible for memory-diet quota
consideration without:

- silently promoting them to TRACK_NORMAL or TRACK_FAST;
- creating active tracking/scheduler work;
- weakening STNP, source-trace, quality, or lifecycle gates;
- generating memory;
- activating retrieval or paper decisions; or
- unlocking BUY/SELL/HOLD, positions, trades, audits, or PnL.

The design must decide whether quota operates on:

1. the broader governed candidate universe; or
2. only persisted tracking candidates with revised quota semantics.

It must not simply remove the WATCH_ONLY or D1 protections to make quota pass.

After that repair is designed and proved, a later V2-2 lane should address token
age/15m evidence and the DexScreener Solana-query productivity gap. V2-2J and
V2-3 remain paused.
