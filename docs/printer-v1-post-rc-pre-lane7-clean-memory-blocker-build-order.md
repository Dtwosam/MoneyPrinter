# Pre-Lane-7 Clean Memory Blocker Build Order

This is a consolidated pre-Lane-7 Post-RC planning task.

It is not Lane 7. It is not source adapter implementation. It is not live data collection. It is not a migration task. It is not a paper decision task.

Printer V1 remains Solana-only, Solana memecoin-only, paper-trading only, no live wallet, no private keys, no real funds, no live execution, no paid API dependency, no scoring, no ranking, no confidence percentages, no weighted decision logic, no engine bypassing Source Governor, no engine bypassing Central Scheduler, no dirty-memory retrieval, no BUY unlock, no paper positions, no paper trade events, and no PnL.

## Current Status Summary

Latest anchor:

- `9a2d117` / `printer-v1-post-rc-paper-quote-evidence-storage-schema-design`

Current validated state:

- Lane 6 is complete.
- Fresh context validation is complete.
- Missing source candidates have been evaluated.
- Jupiter paper quote readiness is documented.
- Paper quote fixture readiness is documented and tested.
- Paper quote storage schema design is documented and tested.
- Fresh 15m memory evidence has already reached complete snapshot coverage.
- Fresh context rows have been created for the latest validated snapshot/window.
- Historical source failures remain visible.

Current blocking state:

- `clean_memory_count` is still `0`.
- Clean eligible memory is still `0`.
- Retrieval remains blocked.
- Paper decisions remain blocked.
- Paper positions remain `0`.
- Paper trade events remain `0`.
- Lane 7 remains blocked.

Current remaining blockers:

- `chain_heat_label: SOLANA_UNKNOWN`
- `market_regime_label: UNKNOWN`
- `safety_status_label: SAFETY_UNKNOWN`
- `entry_realism_label: ENTRY_UNKNOWN`
- `exit_realism_label: EXIT_UNKNOWN`
- `flow_direction_label: FLOW_UNKNOWN`
- `flow_pressure_label: FLOW_UNKNOWN`

The current bottleneck is not retrieval expansion. It is missing or unknown context evidence needed before the first clean eligible memory can exist.

## Blocker Table

| Blocker | Why it blocks clean memory | Current stored data may help | Current derived logic may help | Fixture/schema design needed | Future source adapter needed | Migration may be needed later | Allowed before Lane 7 | Can unlock clean memory alone | Recommended task type |
|---|---|---|---|---|---|---|---|---|---|
| `safety_status_label: SAFETY_UNKNOWN` | Safety is a hard protection gate; unknown authority/distribution/rug evidence cannot train clean decisions. | Existing liquidity fields help liquidity safety only, not authority/distribution. | Current logic can derive some liquidity safety but leaves authority/distribution unknown. | Yes, for Solana RPC/GoPlus-style safety fixtures and evidence contract. | Likely yes, via Source Governor only. | Possibly, if safety evidence cannot fit existing `printer_safety_rug_snapshots` fields. | Yes, as fixture/schema/migration-review/source-governed tasks only. | No. Safety known still needs market, chain, flow, and realism. | First concrete task: fixture-only Solana safety evidence contract and gate tests. |
| `entry_realism_label: ENTRY_UNKNOWN` | Paper entry realism is required before claiming a realistic outcome or paper-profit possibility. | `price_usd` and `liquidity_usd` frame entry, but do not prove route/slippage/price impact. | Current liquidity logic can label caution from liquidity, but route remains unknown without quote evidence. | Already started; storage schema is designed but not migrated. | Later, likely Jupiter quote through Source Governor. | Yes, if `printer_paper_quote_evidence` is approved. | Yes, but only fixture/schema/migration review before source integration. | No. Quote evidence only helps entry/exit realism. | Migration proposal review after safety fixture path is defined. |
| `exit_realism_label: EXIT_UNKNOWN` | Exit realism is required before any paper-profit or capital-protection claim can be clean. | Snapshot sequence can show liquidity decay and price path, but not actual route/slippage/price impact. | Current logic can identify liquidity caution/blocking, but route remains unknown. | Already started; storage schema is designed but not migrated. | Later, likely Jupiter quote through Source Governor. | Yes, if quote evidence gets a dedicated table. | Yes, but only fixture/schema/migration review before source integration. | No. Exit realism cannot solve safety/market/chain/flow. | Same quote evidence migration proposal review as entry realism. |
| `flow_direction_label: FLOW_UNKNOWN` | Memory fingerprints include flow direction; unknown flow weakens setup comparison and can block clean context. | Existing DexScreener snapshots store total volume/txns. Raw payload may contain buy/sell split, but normalized snapshots may not preserve it yet. | Current logic derives volume/tx activity, not full direction without side split. | Yes, fixture-only test for stored/raw buy-sell split preservation and derived flow labels. | Maybe. Existing DexScreener raw data may be enough; GeckoTerminal/other source only if existing data cannot solve it. | Possibly, if normalized snapshots need buy/sell side fields. | Yes, as fixture/test or migration proposal; no live fetch. | No. Flow known still needs safety/realism/market/chain. | Fixture-only DexScreener raw-flow preservation review. |
| `flow_pressure_label: FLOW_UNKNOWN` | Flow pressure is part of trading-flow context and helps distinguish accumulation/outflow/wash-like behavior. | Existing total volume/txns help activity but not pressure. | Derived logic cannot safely infer pressure from totals alone. | Yes, alongside flow direction fixtures. | Maybe later if buy/sell split is unavailable from existing governed data. | Possibly, if side-aware fields must be added. | Yes, as fixture/test or migration proposal; no live fetch. | No. | Same fixture-only raw-flow preservation review. |
| `market_regime_label: UNKNOWN` | Broad market context is required by the memory spec, but must remain context only. | Current token snapshots do not carry BTC/SOL/Fear & Greed broad market data. | Current logic cannot derive market regime from token-local fields without fabricating context. | Maybe, but source contract is more important than schema because table already exists. | Yes, likely CoinGecko/free broad market and/or Alternative.me, governed only. | Unlikely if `printer_market_regime_snapshots` is sufficient. | Yes, as source-governed implementation later, below token-level priorities. | No. Broad context cannot be a trade signal. | Later governed broad-market context task after token-level blockers. |
| `chain_heat_label: SOLANA_UNKNOWN` | Solana memecoin environment context is required, but broad heat must not drive decisions alone. | Token snapshots show one tracked token/pair only; they cannot prove broad Solana heat. | Current logic cannot safely derive broad chain heat from one token. | Maybe, but table already exists. | Yes, likely DefiLlama/CoinGecko/Solana Status/official data, governed only. | Unlikely if `printer_solana_chain_heat_snapshots` is sufficient. | Yes, as source-governed implementation later, below token-level priorities. | No. Chain heat is context only. | Later governed chain/broad context task after token-level blockers. |

## Priority Order

Safest blocker build order:

1. Safety/rug evidence.
   Safety is the first practical blocker because it is a hard protection gate. A token with unknown authority/distribution/rug evidence should not become clean training memory. Current stored liquidity helps only part of safety, so the next task should be fixture-only safety evidence contract and gate tests using Solana RPC/GoPlus-style candidate shapes without live calls.

2. Entry/exit realism evidence storage migration review.
   Quote evidence has already been planned enough. The next useful quote task is not more readiness planning; it is a concrete migration proposal review for `printer_paper_quote_evidence`, still without applying a migration or calling Jupiter.

3. Flow direction/pressure from existing governed data.
   This should check whether existing DexScreener raw responses already contain enough buy/sell split evidence to derive flow direction/pressure. If yes, prefer using existing stored governed payloads and fixture tests. If not, write a migration/source-governed task later.

4. Market regime broad context.
   Market regime is required context, but it is broad context and not a direct trade signal. It should come after token-level safety/realism/flow blockers because token-level evidence beats broad context.

5. Solana chain heat broad context.
   Chain heat is also required context, but it should not become a direct trade signal and should not compete with token snapshots. It can be developed alongside or after market regime once the token-level blockers have concrete paths.

This priority order intentionally avoids Lane 7 work. Retrieval expansion is useless until at least one clean eligible memory exists.

## Stop-Doing List

Stop doing:

- No more separate source-readiness docs unless this build order explicitly creates that task.
- No Lane 7 prompts until clean eligible memory exists.
- No more quote planning unless it moves into concrete fixture, schema, migration-review, or later source-governed implementation work.
- No live source integrations before a governed source task exists.
- No source-specific planning loop for every candidate source.
- No broad context work that turns market regime or chain heat into a trade signal.
- No paper decision or BUY unlock planning before clean memory exists.

## Next 5 Concrete Tasks

### 1. Solana Safety Evidence Fixture Contract

- Task type: fixture-only.
- Blocker addressed: `safety_status_label: SAFETY_UNKNOWN`.
- Allowed work: add fixture-only tests and documentation for authority, freeze authority, holder concentration, liquidity-lock status, source status, data quality, and target linkage.
- Not allowed work: no RPC calls, no GoPlus calls, no adapter, no DB mutation, no migration application, no clean-memory unlock.
- Expected exit gate: safety fixture states can map to `SAFETY_CLEAN`, `SAFETY_CAUTION`, `SAFETY_SUSPICIOUS`, `SAFETY_UNSAFE`, or `SAFETY_UNKNOWN` without fabricating evidence; unknown/failed/stale safety remains blocking.

### 2. Paper Quote Evidence Migration Proposal Review

- Task type: migration review.
- Blocker addressed: `entry_realism_label: ENTRY_UNKNOWN`, `exit_realism_label: EXIT_UNKNOWN`.
- Allowed work: propose exact migration SQL for `printer_paper_quote_evidence`, constraints, indexes, and audit labels; do not apply it.
- Not allowed work: no migration application, no Jupiter adapter, no live quote calls, no source rows, no paper decisions.
- Expected exit gate: operator can approve, reject, or revise a precise quote-evidence migration proposal.

### 3. DexScreener Raw Flow Preservation Fixture Review

- Task type: fixture-only / schema proposal if needed.
- Blocker addressed: `flow_direction_label: FLOW_UNKNOWN`, `flow_pressure_label: FLOW_UNKNOWN`.
- Allowed work: inspect stored normalized payload shape and write fixture tests proving whether buy/sell split can be preserved and mapped categorically.
- Not allowed work: no live DexScreener call, no source adapter change, no scoring, no flow-as-trade-signal behavior.
- Expected exit gate: either existing stored raw payload can support side-aware flow fixtures, or a small future schema proposal is justified.

### 4. Safety Evidence Storage Migration Review

- Task type: migration review.
- Blocker addressed: `safety_status_label: SAFETY_UNKNOWN`.
- Allowed work: only if Task 1 proves existing `printer_safety_rug_snapshots` cannot represent required authority/distribution evidence cleanly; otherwise skip.
- Not allowed work: no migration application, no RPC/source adapter, no DB mutation.
- Expected exit gate: clear decision whether existing safety table is enough or whether a minimal future migration is needed.

### 5. Governed Broad Context Implementation Readiness

- Task type: source-governed implementation later.
- Blockers addressed: `market_regime_label: UNKNOWN`, `chain_heat_label: SOLANA_UNKNOWN`.
- Allowed work: after token-level blockers have concrete paths, define one bounded governed broad-context implementation task using existing market/chain tables.
- Not allowed work: no direct API calls, no broad context as trade signal, no token snapshot starvation, no Lane 7.
- Expected exit gate: market/chain context can be refreshed through Source Governor and Central Scheduler without loosening clean-memory gates.

## Clean-Memory Minimum Path

Minimum path before the first clean eligible memory can exist:

1. A complete 15m evidence window exists.
2. Snapshot coverage remains complete and correctly scoped to the memory window.
3. Source quality for linked snapshots remains clean or acceptable partial.
4. Fresh targeted context exists for the evidence window.
5. Safety context is known and acceptable.
6. Entry realism is known or conservatively acceptable for the outcome being claimed.
7. Exit realism is known or conservatively acceptable for the outcome being claimed.
8. Flow direction and pressure are known enough for the current memory rules, or explicitly handled by an approved conservative rule.
9. Market regime context is known or explicitly handled by an approved conservative rule.
10. Solana chain heat context is known or explicitly handled by an approved conservative rule.
11. Memory audit passes without stale, failed, missing, mismatched, unknown, or conflicting critical context.
12. Retrieval remains clean-only and excludes dirty/audit-only memory.

No single blocker fix can create clean memory alone. Clean memory requires the full evidence bundle.

## Lane 7 Gate

Lane 7 is allowed only after enough clean eligible memories exist.

Until then:

- Retrieval stays blocked.
- Dirty memory stays audit-only.
- Audit-only memory stays non-retrievable.
- Paper decisions stay blocked.
- BUY stays locked.
- Paper positions stay impossible.
- Paper trade events stay impossible.
- PnL stays unavailable.

Lane 7 should not be used to make dirty memory useful. Lane 7 is retrieval reporting expansion only after clean memory exists.

## Source / Governor / Scheduler Rules

Rules for all future blocker work:

- No engine direct API calls.
- No source loops.
- No source spam.
- No direct external calls from memory, retrieval, paper decision, or monitor code.
- All future external evidence must go through Source Governor.
- All future source work must record request, response, and failure evidence honestly.
- All future collection must go through Central Scheduler.
- Token-level snapshots remain priority over broad context engines.
- Open paper-trade monitoring remains top priority when paper positions exist in a later approved lane.
- Broad market/chain context remains context only.
- No source evidence can become a score, ranking, confidence percentage, or weighted decision input.

## Non-Goals

This task does not:

- Add an adapter.
- Fetch live data.
- Call an API.
- Add RPC calls.
- Mutate the database.
- Apply a migration.
- Create source request, response, or failure rows.
- Create token snapshots.
- Create context rows.
- Build memory windows.
- Rebuild memory.
- Run retrieval.
- Create paper decisions.
- Create BUY.
- Create positions.
- Create trade events.
- Create PnL.
- Activate Lane 7.

## Recommendation

Build immediately next:

- `Solana Safety Evidence Fixture Contract`

Why this is the shortest safe path:

- Safety is a hard memory blocker.
- Existing stored liquidity data can only partially reduce safety uncertainty.
- Authority, freeze authority, distribution, and lock/rug evidence need a clear fixture contract before any source work.
- It keeps work concrete without calling RPC, adding adapters, mutating the DB, or starting Lane 7.

Remain blocked:

- Lane 7.
- Retrieval.
- Paper decisions.
- BUY.
- Paper positions.
- Paper trade events.
- PnL.
- Live trading.
