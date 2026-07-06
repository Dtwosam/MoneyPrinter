# Printer V1 Lane X10.5 Discovery / Selection Explainability Audit

## 1. Purpose

This report audits how the five repaired Lane X5 proof tokens entered Printer's memory-growth flow before any Lane X11 work.

The audited proof tokens are:

- BONK
- WIF
- EAGLE250
- WEN
- ANSEM

This audit is documentation plus read-only DB inspection only. It does not run discovery, fetch sources, mutate the DB, create memory, activate retrieval, create paper decisions, unlock BUY/SELL/HOLD, open positions, create trade events, create audits, or create PnL.

The central question is whether the proof tokens were discovered by Printer, manually supplied, selected from existing DB state, or mixed across those paths.

## 2. Source-of-Truth Constraints

Source-of-truth documents checked:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-growth-build-order.md`
- `docs/printer-v1-memory-growth-automation-audit.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-lane-x10-memory-growth-yield-report.md`
- `docs/printer-v1-lane-x7-bounded-discovery-to-tracking-review.md`

Constraints preserved by this audit:

- Solana-only
- Solana memecoin-only
- paper-trading only
- no live wallet, private keys, real funds, or live execution
- no paid API dependency
- no scoring, ranking, confidence, or weighted decision logic
- no Source Governor bypass
- no Central Scheduler bypass
- no retrieval activation
- no paper decision creation
- no BUY/SELL/HOLD unlock
- no paper positions
- no trade events, paper trade audits, or PnL
- no dirty-memory decision use

Discovery remains intake only. Selection for memory growth must be memory-value based, not BUY-probability based.

## 3. Current Discovery / Source Inventory

Read-only DB inspection found these relevant tables:

| Table | Present | Row count | Audit note |
|---|---:|---:|---|
| `printer_discovery_candidates` | yes | 11 | Main discovery candidate table currently present. |
| `printer_token_discoveries` | no | n/a | Not present in current schema. |
| `printer_discovery_events` | no | n/a | Not present in current schema. |
| `printer_tracking_queue` | yes | 11 | Stores tracking lane/action/status after discovery routing. |
| `printer_tokens` | yes | 13 | Stores registered token records. |
| `printer_pairs` | yes | 14 | Stores registered pair records. |
| `printer_source_requests` | yes | 873 | Source-governed request trace table. |
| `printer_source_responses` | yes | 828 | Source-governed response trace table. |
| `printer_source_failures` | yes | 45 | Source-governed failure trace table. |
| `printer_token_lifecycle_events` | yes | 11 | Lifecycle event trace for discovery routing. |

Discovery sources actually represented in `printer_discovery_candidates`:

| Source | Discovery candidate rows | Actions represented |
|---|---:|---|
| `dexscreener` | 8 | TRACK_FAST, TRACK_NORMAL, WATCH_ONLY |
| `geckoterminal` | 3 | TRACK_FAST |

Other source names represented in source request/response/failure tables, but not as discovery candidates in this DB:

- `alternative_me`
- `coingecko`
- `defillama`
- `goplus`
- `jupiter_quote`
- `solana_rpc`

No `pumpportal` or `pumpswap` discovery rows were present in the persistent DB at audit time, even though source-channel/test code documents those paths.

## 4. The Five X5 Proof Tokens: Origin and Selection Path

### Summary Table

| Proof token | token_id | mint | symbol/name | pair_id(s) | pair address used in repaired X5 token list | DB token_status | Discovery origin | Operator-approved for X5 | Pair drift |
|---|---:|---|---|---|---|---|---|---|---|
| BONK | 7 | `DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263` | Bonk / Bonk | 7 | `6oFWm7KPLfxnwMb3z5xwBoXNSPP3JJyirAPqPSiVcnsp` | TRACK_FAST | DexScreener discovery candidate id 6 | yes | no |
| WIF | 8 | `CW8LSonJxHu7k3JnQnp5eTsrtRVgbpg38RwdizWWPyoi` | WIF / dogwifhat | 8 | `EzDd9yzVh2js6hVcaW4wXcaKc81kmEUMVUu4xa5n3gMX` | WATCH_ONLY | DexScreener discovery candidate id 7 | yes | no |
| EAGLE250 | 10 | `AXLmMWkRmSPdPxkuMqAD4nzYBK7QRssNkYZ6RXzLpump` | EAGLE250 / SOL | 10 | `3Qhv2Z6n5aknNzx56A2n4qvqUZ4CvbCkUh24KcK9T9qY` | TRACK_FAST | GeckoTerminal discovery candidate id 9 | yes | no |
| WEN | 11 | `66pQgfLHEfbHSBgYSZSrKEdJHHaGiYbgCtNbz48Apump` | WEN / SOL | 11 | `HZyqZRuAUCLdJaHqBfnoFHVBwXmuH3Sm1LyXnWu8Ee15` | TRACK_FAST | GeckoTerminal discovery candidate id 10 | yes | no |
| ANSEM | 13 | `9cRCn9rGT8V2imeM2BaKs13yhMEais3ruM3rPvTGpump` | ANSEM / The Black Bull | 13, 14 | `FnzKY6x7entQ1eR3D225dQyT7ybfka4PskBMQhb8L3CC` | TRACKING | No discovery candidate row found | yes | yes |

### Per-Token Details

#### BONK

- `token_id`: 7
- `pair_id`: 7
- `source_name`: `dexscreener`
- `source_response_id`: 78
- `source_request_id`: 84
- `request_kind`: `token_discovery`
- `request_key`: `post-rc-discovery-bonk`
- `discovery_action`: `TRACK_FAST`
- `tracking_lane`: `TRACK_FAST`
- `priority_reason`: `TRACK_FAST:fresh_solana_candidate_with_liquidity_and_activity:dexscreener`
- `tracking_action`: `NEW_DISCOVERY`
- `lifecycle_event`: `PROMOTE_TO_TRACK_FAST`
- origin finding: Printer-discovered through a governed DexScreener discovery path, then manually included in the X5 operator token list.

#### WIF

- `token_id`: 8
- `pair_id`: 8
- `source_name`: `dexscreener`
- `source_response_id`: 94
- `source_request_id`: 100
- `request_kind`: `token_discovery`
- `request_key`: `post-rc-discovery-wif`
- `discovery_action`: `WATCH_ONLY`
- `tracking_lane`: `WATCH_ONLY`
- `priority_reason`: `WATCH_ONLY:partial_market_fields_or_low_activity:dexscreener`
- `tracking_action`: `NEW_DISCOVERY`
- `lifecycle_event`: `WATCH_ONLY_REFRESH`
- origin finding: Printer-discovered through governed DexScreener, but classified as WATCH_ONLY in DB. It was manually elevated into the X5 proof token list as `TRACK_FAST` by operator approval.

This is the clearest selection explainability gap in the repaired X5 proof set: the proof-run token-list lane differs from the DB discovery lane.

#### EAGLE250

- `token_id`: 10
- `pair_id`: 10
- `source_name`: `geckoterminal`
- `source_response_id`: 114
- `source_request_id`: 120
- `request_kind`: `geckoterminal_trending_pool_reference`
- `request_key`: `manual-memory3-geckoterminal-trending-20260625-133555`
- `source_channel`: `GECKOTERMINAL_TRENDING_POOL`
- `source_channel_reason`: `geckoterminal_trending_pool_reference`
- `discovery_action`: `TRACK_FAST`
- `tracking_lane`: `TRACK_FAST`
- `priority_reason`: `TRACK_FAST:fresh_solana_candidate_with_liquidity_and_activity:geckoterminal`
- `tracking_action`: `NEW_DISCOVERY`
- `lifecycle_event`: `PROMOTE_TO_TRACK_FAST`
- origin finding: Printer-discovered through a governed GeckoTerminal trending-pool source response, then manually included in the X5 operator token list.

#### WEN

- `token_id`: 11
- `pair_id`: 11
- `source_name`: `geckoterminal`
- `source_response_id`: 114
- `source_request_id`: 120
- `request_kind`: `geckoterminal_trending_pool_reference`
- `request_key`: `manual-memory3-geckoterminal-trending-20260625-133555`
- `source_channel`: `GECKOTERMINAL_TRENDING_POOL`
- `source_channel_reason`: `geckoterminal_trending_pool_reference`
- `discovery_action`: `TRACK_FAST`
- `tracking_lane`: `TRACK_FAST`
- `priority_reason`: `TRACK_FAST:fresh_solana_candidate_with_liquidity_and_activity:geckoterminal`
- `tracking_action`: `NEW_DISCOVERY`
- `lifecycle_event`: `PROMOTE_TO_TRACK_FAST`
- origin finding: Printer-discovered through the same governed GeckoTerminal trending-pool source response as EAGLE250, then manually included in the X5 operator token list.

#### ANSEM

- `token_id`: 13
- `pair_id`: 13 and 14
- `token_status`: `TRACKING`
- initial `first_seen_at`: `2026-06-28T19:59:32.965114+00:00`
- `pair_id=13`: `FnzKY6x7entQ1eR3D225dQyT7ybfka4PskBMQhb8L3CC`
- `pair_id=14`: `6e7V9eegCHw997T72MxgwwJipZ6GJyZF8NvjkzT1rvpN`
- discovery candidate row: none found
- tracking queue row: none found
- lifecycle event row: none found
- first token snapshots exist with `tracking_lane=TRACK_FAST`, `snapshot_mode=FIRST_15M_CYCLE`, `source_status=COMPLETE`, and `data_quality_label=CLEAN_DATA`
- origin finding: ANSEM appears to have been supplied by the operator token list and materialized through the X5 runner/snapshot path rather than originating in the discovery candidate table.

ANSEM is the only audited proof token with pair drift. The operator token list used pair `FnzKY6...`, while DB state later contains a second pair `6e7V9e...` for the same token.

## 5. Manual vs Automatic Selection Finding

The five-token repaired X5 proof was not fully automated discovery-to-tracking selection.

The actual path was mixed:

- BONK: discovered by Printer, then manually approved for X5.
- WIF: discovered by Printer as WATCH_ONLY, then manually approved as TRACK_FAST for X5.
- EAGLE250: discovered by Printer, then manually approved for X5.
- WEN: discovered by Printer, then manually approved for X5.
- ANSEM: no discovery candidate row found; selected through manual operator token-list input and runner-created tracking/snapshot state.

Both inspected X5 token-list files contained all five entries with:

- `operator_approved: true`
- `tracking_lane: TRACK_FAST`
- `chain: solana`

Therefore, selection into the repaired proof run was operator-approved manual selection, not a fully auditable automatic candidate-selection path.

## 6. Source Coverage and Source Gaps

### Coverage Found

Discovery candidates in this DB are represented by:

- DexScreener search/discovery rows
- GeckoTerminal trending-pool rows

The source trace tables also contain evidence rows for:

- CoinGecko broad market context
- DefiLlama chain liquidity context
- Alternative.me fear/greed context
- GoPlus safety reference
- Jupiter paper quote realism
- Solana RPC safety/holder references

Those extra sources are context/evidence sources, not current discovery candidate origins in `printer_discovery_candidates`.

### Gaps

- No PumpPortal discovery rows were present in this persistent DB.
- No PumpSwap discovery rows were present in this persistent DB.
- No ANSEM discovery candidate row was present.
- No DB-native bridge row ties X6 selected candidates to the exact X5 token-list file used by the operator.
- No table field directly records "operator manually overrode WATCH_ONLY to TRACK_FAST for this proof run."

## 7. Fairness / Chance Analysis

### Are all eligible tokens given equal chance?

No, not in the current repaired proof path.

The current path is not random or equal-chance selection. It is a manual, operator-approved bridge from discovery/DB state into an X5 token list. X6 provides dedup, cooldown awareness, and memory-diet labeling, but the final inclusion step is the operator-authored JSON token list.

### Should all eligible tokens be given equal chance?

Not exactly.

Printer should not use buy-probability, scores, rankings, confidence percentages, or weighted logic. But "equal chance" is also not the right target if it means randomly selecting every eligible token without regard to memory value.

The safe target is memory-value fairness:

- Apply the same eligibility gates to every candidate.
- Do not prefer tokens because they look likely to produce a BUY.
- Prefer a balanced evidence diet for learning: pumps, dumps, fake pumps, wick-only moves, late-buy traps, liquidity decay, dead tokens, revivals, and ambiguous cases.
- Make every inclusion and exclusion reason auditable.
- Keep operator approval for bounded memory runs.

Fair selection should mean transparent, bounded, source-governed, memory-diet-aware selection without numeric scoring or trade prediction.

## 8. Dedup and Pair Drift Analysis

Read-only DB checks found:

- Duplicate token mints in `printer_tokens`: 0.
- Duplicate pair addresses in `printer_pairs`: 0.
- Tokens with multiple pairs: 1.
- The multi-pair token is ANSEM (`token_id=13`), with pair ids 13 and 14.

ANSEM same-token/new-pair handling is visible as pair drift but not fully resolved:

- The X5 token-list JSON used pair id 13's address: `FnzKY6x7entQ1eR3D225dQyT7ybfka4PskBMQhb8L3CC`.
- Later DB state includes pair id 14: `6e7V9eegCHw997T72MxgwwJipZ6GJyZF8NvjkzT1rvpN`.
- Lane X10 already reports ANSEM pair drift as non-blocking.

Before automated selection, pair drift needs a clearer operator-facing trace:

- which pair was selected,
- which pair was observed later,
- whether the new pair supersedes the old one,
- whether the old pair should be archived,
- whether the same-token/new-pair case should count as revival, pair migration, or ambiguous memory-diet coverage.

## 9. Memory-Diet Coverage Analysis

Lane X6 code and tests define memory-diet labels:

- `PUMP`
- `DUMP`
- `FAKE_PUMP`
- `WICK_ONLY`
- `LATE_BUY_TRAP`
- `LIQUIDITY_DECAY`
- `DEAD_TOKEN`
- `REVIVAL`
- `AMBIGUOUS`

This is the right direction for memory-value selection because it broadens learning beyond winners.

Current persistent DB/proof-run gaps:

- The repaired X5 proof token list itself does not store its X6 `memory_diet_label` per selected token.
- WIF was WATCH_ONLY in DB but TRACK_FAST in the proof token list, so its selection reason is manual rather than a clean X6 memory-diet trace.
- ANSEM has no discovery candidate row, so its memory-diet origin is not auditable from discovery.
- No proof was found that the five-token set was selected to cover all memory-diet categories.

The current system can represent memory-diet reasoning in X6 outputs, but the persistent bridge from X6 output to X5 token-list execution is not strong enough for automated bounded selection.

## 10. Risks

| Risk | Severity | Finding |
|---|---|---|
| Manual X6-to-X5 bridge | High | The operator token list is the final selection artifact; DB does not prove every token came from X6. |
| WATCH_ONLY override | High | WIF was WATCH_ONLY in discovery/tracking DB but TRACK_FAST in the proof token list. |
| ANSEM origin gap | High | ANSEM has no discovery candidate, tracking queue, or lifecycle event row. |
| Pair drift | Medium | ANSEM has two pairs; drift is reported but not resolved before future automation. |
| Incomplete discovery source diversity | Medium | Persistent discovery candidates only show DexScreener and GeckoTerminal. |
| PumpPortal/PumpSwap not represented in DB | Medium | Source paths exist in code/tests, but no persistent discovery evidence was found for them. |
| Selection may bias toward active pumps | Medium | X6 supports diet labels, but proof-run inclusion was manual and not proven balanced. |
| Stale/recycled token control | Medium | X3/X6 cooldown controls exist, but no cooldown/archive rows currently block repeated use. |
| Operator audit burden | Medium | The operator must reconcile discovery rows, token list JSON, pair drift, and proof-run output manually. |

## 11. Required Fixes Before Discovery Automation

Before discovery automation or automated bounded selection, Printer needs a traceability repair lane.

Required fixes:

1. Persist a selection batch record that links:
   - discovery candidate ids,
   - selected token ids,
   - selected pair ids,
   - memory-diet labels,
   - selection reasons,
   - dedup decisions,
   - cooldown/archive decisions,
   - same-token/new-pair findings,
   - operator approval,
   - and the exact X5 token-list/proof run.

2. Reject or explicitly record manual overrides, especially:
   - WATCH_ONLY promoted into TRACK_FAST,
   - tokens with no discovery candidate row,
   - tokens with pair drift,
   - tokens whose source trace is missing or stale.

3. Preserve memory-value selection:
   - no buy-probability labels,
   - no scores,
   - no ranks,
   - no confidence percentages,
   - no weighted selection.

4. Make source coverage explicit:
   - DexScreener discovery,
   - GeckoTerminal discovery,
   - PumpPortal discovery if used,
   - PumpSwap discovery if used,
   - and any manual baseline source.

5. Require a proof report before automation:
   - selected candidates,
   - rejected candidates,
   - manual overrides,
   - memory-diet balance,
   - source budget,
   - pair drift,
   - stale/recycled token check,
   - no downstream unlocks.

## 12. Verdict

Verdict: `PARTIAL_READY_WITH_GAPS`

Discovery explainability is partially ready because:

- discovery candidates are stored with source names, source response ids, source status, data quality, action/lane, priority reason, and source channel fields;
- tracking queue rows preserve lane/action/priority for discovered candidates;
- source request/response rows link several discovery candidates back to governed source traces;
- X6 code provides dedup, cooldown awareness, same-token/new-pair detection, memory-diet labels, and selection reasons.

Discovery explainability is not ready for automated bounded selection because:

- the repaired proof set was ultimately selected by manual operator token-list JSON;
- WIF was WATCH_ONLY in DB but TRACK_FAST in the proof run;
- ANSEM lacks a discovery candidate origin row;
- ANSEM has pair drift;
- the DB does not persist a selection batch linking X6 output to the X5 run;
- memory-diet coverage is available in code/tests but not persisted as the proof-run selection rationale.

`DISCOVERY_EXPLAINABILITY_READY`: no.

`PARTIAL_READY_WITH_GAPS`: yes.

`NOT_READY_FOR_AUTOMATED_SELECTION`: yes, for automation.

## 13. Next Recommended Action

Recommended next action:

`Lane X10.6 - Discovery Selection Traceability Repair`

Lane X10.6 should be a future implementation/reporting lane that repairs the selection traceability gap without enabling automation by default.

Minimum scope for Lane X10.6:

- persist a bounded selection batch artifact or report;
- tie selected tokens to discovery candidate ids where present;
- require explicit operator override reasons where discovery rows are absent or lanes differ;
- carry X6 memory-diet labels into the X5 proof-token selection artifact;
- flag WATCH_ONLY-to-TRACK_FAST manual overrides;
- flag same-token/new-pair and pair-drift cases;
- keep discovery as intake, not alpha;
- keep operator approval required;
- preserve all retrieval, paper-decision, BUY/SELL/HOLD, position, trade, audit, and PnL locks.

Lane X11 should wait unless the operator explicitly accepts this audit and chooses to defer discovery repair. The safer path is to repair discovery/selection traceability first.

