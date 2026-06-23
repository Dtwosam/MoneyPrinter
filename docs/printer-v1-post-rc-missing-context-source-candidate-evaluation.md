# Missing Context Source Candidate Evaluation Plan

This is a planning-only Post-RC task. It is not Lane 7, not source adapter implementation, and not live data collection.

Printer V1 remains Solana-only, memecoin-only, paper-trading only, free/public-source only, no live wallet, no private keys, no real funds, no paid API dependency, no scoring, no ranking, no confidence percentages, no weighted decision logic, no dirty-memory retrieval, no BUY unlock, no paper positions, no paper trade events, and no PnL.

## Current Blocker Summary

Fresh 15m evidence has already proven the window mechanics:

- Fresh 15m memory window was created from snapshots `32, 33, 34, 35, 36`.
- Snapshot coverage was complete.
- Context collection for snapshot `36` created seven fresh context rows.
- Source quality was acceptable for the evidence window.
- Historical source failures remained visible.
- Clean memory remains blocked.
- Retrieval remains blocked.
- Paper decisions remain blocked.
- Paper positions remain `0`.
- Paper trade events remain `0`.

Remaining blockers:

- `chain_heat_label: SOLANA_UNKNOWN`
- `market_regime_label: UNKNOWN`
- `safety_status_label: SAFETY_UNKNOWN`
- `entry_realism_label: ENTRY_UNKNOWN`
- `exit_realism_label: EXIT_UNKNOWN`
- `flow_direction_label: FLOW_UNKNOWN`
- `flow_pressure_label: FLOW_UNKNOWN`

The recent clean-context blocker review established that some context labels can be derived from stored snapshot fields, but these remaining blockers need evidence that is not safely present in the current stored snapshot rows.

## Candidate Source Comparison Table

| Candidate source | Helps blockers | Cannot solve | Free/public status | API key | Paid-dependency risk | Source Governor requirement | Scheduler requirement | Snapshot competition risk | Evidence type | V1 verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| Official Solana data / `solana.com/data` | Solana chain heat, broad network activity, fees, slots, fee payers, DeFi/stablecoin context | Token safety, entry/exit route realism, token flow pressure, pair-specific buy/sell direction | Public dashboard; Solana page describes twice-daily network/stablecoin/DeFi metrics | Unknown for dashboard; linked products may vary | Medium: linked institutional/API products may be commercial | Must be wrapped as broad context request, never called by engines directly | Low priority broad context job, below token snapshots | Low if cached; unsuitable for high-frequency token windows | Broad context only | Candidate to investigate, not approved yet |
| Solana Status / network health | Chain health, outages, degraded RPC/cluster state | Market regime, token safety, entry/exit, flow pressure | Public status page | No for page/feed | Low | Status fetch must be governed and recorded as source evidence | Low-priority network-health check | Low | Broad infrastructure context only | Useful audit context; not enough for clean chain heat alone |
| Solana public RPC | Token mint/freeze authority, largest accounts, account state, possible holder concentration, raw chain checks | Broad market regime, DEX quote realism, off-chain pair liquidity, social/sentiment | Public endpoints exist but are rate-limited and not production-grade | No for public endpoints | Medium reliability risk; private RPC would be paid and out of scope unless optional | Must go through Source Governor with strict rate limits and method allowlist | Safety/liquidity refresh priority only when token is tracked | Medium: RPC calls can crowd snapshots if not capped | Token-level safety evidence | Good candidate for safety/rug evidence if rate-limited and optional |
| Helius free tier | Token metadata, DAS, enhanced transactions, RPC reliability, wallet/transfer history if free tier allows | Broad market regime; can drift into paid infrastructure/trading tools | Provider advertises free-to-enter plans and paid/enterprise scaling | Yes | High: must remain optional/free and avoid Sender/trading infrastructure | Must be optional provider behind Source Governor; no hard dependency | Safety/audit jobs only; no streaming runtime in V1 | Medium/high if used heavily | Token-level safety/transaction evidence | Investigate only as optional fallback; not required dependency |
| DefiLlama | Solana TVL, DEX volume, stablecoins, fees/revenue, broad DeFi liquidity | Token-level rug checks, entry/exit quotes, pair-specific flow direction | Public data/docs; tracks TVL, fees/revenue, DEX volume, stablecoins | Generally no for public endpoints, but verify per endpoint | Low/medium: API availability and endpoint limits need verification | Governed broad-context source request | Low-priority market/chain context schedule | Low | Broad context only | Strong candidate for market/chain backdrop, audit-only until validated |
| CoinGecko free/public/demo | BTC/SOL price/change, broad crypto market regime, maybe listed token context | New memecoin safety, unlisted pair flow, entry/exit quote realism | Keyless IP-limited and Demo plan documented | Demo key for stable quota; keyless possible with limits | Medium: Pro endpoints and reliable quota can become paid pressure | Governed market-context source request; must record keyless/demo status | Market regime job below token snapshots | Low | Broad market context | Candidate for market regime; not token-level proof |
| GeckoTerminal | Pool price/liquidity/OHLCV, pool historical chart, token pools, token market data | Safety authority, quote route realism, broad market regime | Public API currently free, beta, with change risk | Docs indicate public API; verify endpoint-level auth | Medium: CoinGecko paid on-chain endpoints offer higher limits | Governed backup token/pool market source | Backup confirmation, not duplicate fast loop | Medium if used at high cadence | Token-level market/chart/flow context | Good backup/confirmation candidate, not a replacement for snapshots |
| GoPlus or similar free safety data | Token security/rug flags where Solana support exists, honeypot/authority/risk metadata if available | Market regime, chain heat, entry/exit quotes, flow pressure | Public docs exist; chain support and Solana coverage must be proven | Likely key or access rules vary; verify | Medium: free limits/chain support may be unstable | Governed safety source request only | Safety refresh priority; no direct trade signal | Low/medium | Token-level safety evidence | Candidate only if Solana support and free terms are verified |
| Jupiter quote API | Entry realism, exit realism, route availability, price impact, slippage, quote freshness for paper simulation | Market regime, safety authority, chain heat, raw flow pressure | Public developer docs show quote endpoint, but current docs require `x-api-key` | Yes in current docs | Medium/high: developer platform/pricing migration risk | Governed paper-quote source request; never transaction build/execute | Entry/exit realism check only near memory/decision audit; no runtime loop | Medium: quote calls must not starve token snapshots | Token-level paper-simulation evidence | Best candidate for entry/exit realism if free API key remains acceptable |
| Existing DexScreener stored fields | Price, liquidity, volume, txns totals, FDV/market cap, price changes; partial chart/volume/tx activity | Market/chain broad context, safety authority/distribution, quote route/slippage/impact, full flow pressure if buy/sell split is not persisted | Existing approved free source path | No current key | Low, already integrated | Already governed; future changes must preserve request/response/failure records | Already scheduled through token snapshot path | Existing token snapshot priority | Token-level market evidence | Keep using; investigate preserving buy/sell split from raw response without broad adapter work |

Source facts checked during planning:

- `solana.com/data` presents network, stablecoin, and DeFi metrics refreshed twice daily and notes the data lags by one day for refresh schedules.
- Solana public RPC endpoints are public and rate-limited; official docs also warn public services are not intended for production applications and may block high-traffic use.
- Solana Status exposes operational health for Mainnet Beta, RPC nodes, regional RPC nodes, explorer, and `solana.com`.
- CoinGecko documents Demo rate limits and keyless IP-based rate limiting.
- DefiLlama documents TVL, fees/revenue, DEX volume, stablecoins, and other broad DeFi metrics.
- GeckoTerminal describes a free public API for prices, OHLC, trading volumes, liquidity, tokens, and pools, but marks it beta and subject to change.
- Jupiter quote docs currently show a GET quote endpoint with route, slippage, and price impact fields, and require an `x-api-key`.

## `solana.com/data` / Official Solana Data Candidate Review

`solana.com/data` is worth investigating for Solana chain heat, but it should not be treated as approved or sufficient yet.

What it can help with:

- Broad Solana network activity.
- Fee and block production context.
- Transaction and non-vote transaction count context.
- Stablecoin and DeFi backdrop if the underlying data is accessible in a governed, repeatable way.
- A slow-moving chain heat backdrop, especially for `SOLANA_UNKNOWN` reduction in audit reports.

What it cannot help with:

- It cannot provide token-level rug/safety authority evidence.
- It cannot provide token holder distribution by itself.
- It cannot provide entry or exit quote realism.
- It cannot provide Jupiter route/slippage/price-impact evidence.
- It cannot provide pair-specific flow direction or flow pressure.
- It is refreshed twice daily and lags by one day, so it is not fresh enough by itself for a 15m memory window that requires near-window context.
- It must not become a direct trade signal.

Planning verdict:

- Treat as `BROAD_CONTEXT_CANDIDATE`.
- Use only if a governed, free/public, stable source interface can be identified.
- Store cadence and lag explicitly.
- Mark as audit-only until tests prove it can support clean context freshness rules.
- Do not use it to unlock Lane 7 by itself.

## Blocker-by-Blocker Mapping

### Solana Chain Heat

Required evidence:

- SOL price/change.
- Network activity, successful/failed transaction context, fee/compute pressure, slots/block production.
- Solana DeFi/DEX volume, TVL, stablecoin context.
- Optional memecoin-specific breadth: active Solana pairs, new pairs, hot pairs, median liquidity, survival/failure counts.

Current stored fields that may help:

- Existing token snapshots can show local tracked-pair liquidity/volume/txns, but not broad Solana chain heat.
- Existing DexScreener fields are token/pair local, not broad chain context.

Candidate sources:

- `solana.com/data`: broad official network and DeFi metrics, slow cadence.
- Solana Status: network/RPC operational health.
- Solana public RPC: real-time cluster checks, block/slot/rpc health if used carefully.
- DefiLlama: Solana TVL, DEX volume, stablecoins, fees/revenue.
- CoinGecko: SOL price/change.
- GeckoTerminal/DexScreener: aggregate tracked Solana memecoin pool evidence only if derived from governed tracked data, not broad external scanning.

Clean memory support:

- Can support clean memory later only when freshness, cadence, source_status, and data_quality are explicit.
- `solana.com/data` alone likely remains audit-only for 15m clean memory because of delayed cadence.

### Market Regime

Required evidence:

- BTC price/change.
- SOL price/change.
- Fear/greed or equivalent broad crypto sentiment.
- Optional ETH, total crypto, stablecoin/DeFi liquidity context.

Current stored fields that may help:

- Token snapshot fields do not contain broad BTC/SOL/Fear & Greed context.

Candidate sources:

- CoinGecko free/public/demo: BTC/SOL price and changes.
- Alternative.me Fear & Greed remains aligned with the master spec, although not in this candidate list.
- DefiLlama: broad DeFi/stablecoin/TVL context.
- `solana.com/data`: Solana-specific broad backdrop, not full crypto market regime.

Clean memory support:

- CoinGecko/DefiLlama can support market context if governed, fresh enough, and source quality is recorded.
- Broad market regime must remain context only.

### Token Safety / Rug Evidence

Required evidence:

- Mint authority, freeze authority, update authority where relevant.
- Holder concentration/top holder/top 10 distribution.
- Liquidity lock or pool safety where available.
- Suspicious restrictions, transfer fee, blacklist/honeypot-like behavior where applicable.
- Source status and data quality per token/pair.

Current stored fields that may help:

- `liquidity_usd` already supports liquidity safety.
- Current stored DexScreener fields do not prove authority, distribution, or lock status.

Candidate sources:

- Solana public RPC: mint/freeze authority, token accounts, largest accounts, basic on-chain state.
- Helius free tier: optional richer DAS/enhanced transaction evidence if free and not required.
- GoPlus or similar: possible token security flags if Solana coverage/free access is verified.
- Existing DexScreener: liquidity and pair existence only.

Clean memory support:

- RPC-derived authority/distribution can support clean memory if the method set is allowlisted, rate-limited, and recorded.
- GoPlus-like safety data must remain audit-only until Solana support and free limits are proven.

### Entry Realism

Required evidence:

- Route available.
- Quote available and fresh.
- Estimated entry slippage.
- Estimated entry price impact.
- Paper size bucket assumptions.
- Entry liquidity/source freshness.

Current stored fields that may help:

- `price_usd` and `liquidity_usd` help frame entry conditions.
- Existing DexScreener fields do not prove route, quote freshness, slippage, or price impact.

Candidate sources:

- Jupiter quote API for paper simulation only.
- GeckoTerminal/DexScreener for pool price/liquidity confirmation, not quote realism.
- Solana public RPC may confirm account state but not practical route quote quality.

Clean memory support:

- Jupiter is the most directly relevant candidate, but only if API-key usage remains free/optional and governed.
- Entry realism must remain unknown if route/quote/slippage/impact are missing.

### Exit Realism

Required evidence:

- Exit route available.
- Quote available and fresh.
- Estimated exit slippage.
- Estimated exit price impact.
- Liquidity drain/decay evidence across the window.
- Exit source status near window close.

Current stored fields that may help:

- Snapshot sequence can show liquidity decay and price path.
- Existing fields still do not prove route/quote/slippage/price impact.

Candidate sources:

- Jupiter quote API for paper simulation only.
- Existing DexScreener/GeckoTerminal for liquidity trend confirmation.
- Solana public RPC for pool/account state confirmation, not quote realism.

Clean memory support:

- Exit realism can support clean memory only when quote route, slippage, price impact, and timing are recorded honestly.
- No route/quote means exit remains unknown or audit-only.

### Flow Direction

Required evidence:

- Buy/sell transaction counts.
- Buy/sell volume, if available.
- Wallet participation or repeated wallet concentration, if available.
- Time-bounded 5m/15m flow attached to the evidence window.

Current stored fields that may help:

- Current stored totals include volume and total txns.
- Existing DexScreener raw response may include buy/sell counts, but normalized snapshot columns currently collapse txns into totals.
- Stored totals can support volume activity and tx activity, but not full direction.

Candidate sources:

- Existing DexScreener fields if buy/sell split is preserved in normalized snapshots later.
- GeckoTerminal if endpoint returns buy/sell or OHLCV/transactions sufficient for direction.
- Helius/RPC enhanced transaction evidence only if free and carefully capped.

Clean memory support:

- Direction can support clean memory later if buy/sell split is captured as evidence, not inferred from total txns.
- Without buy/sell or pressure evidence, `FLOW_UNKNOWN` remains correct.

### Flow Pressure

Required evidence:

- Buy/sell volume ratio or buy/sell count ratio.
- Strong inflow/outflow detection tied to the window.
- Optional wallet participation / wash-like flags.

Current stored fields that may help:

- Total txns and volume help activity labels.
- They do not prove pressure without side split or wallet evidence.

Candidate sources:

- Existing DexScreener raw fields if side split is retained.
- GeckoTerminal if side split is exposed.
- Helius/enhanced transactions if free, optional, and capped.
- Public RPC can derive this only with non-trivial indexing; likely too expensive for V1 unless bounded to tiny tracked windows.

Clean memory support:

- Flow pressure must remain audit-only or unknown until side-aware flow is proven.
- Do not infer pressure from price movement alone.

## Which Sources Can Help Which Blockers

| Blocker | Best candidates | Secondary candidates | Audit-only until proven |
|---|---|---|---|
| Solana chain heat | `solana.com/data`, DefiLlama, CoinGecko SOL, Solana Status | Solana public RPC | `solana.com/data` because cadence/lag may not fit 15m freshness |
| Market regime | CoinGecko, DefiLlama, Alternative.me if later included | `solana.com/data` for Solana-specific backdrop | Any broad source until freshness and labels are tested |
| Safety/rug | Solana public RPC, GoPlus-like safety source | Helius free optional | GoPlus/Helius until free terms and Solana support are proven |
| Entry realism | Jupiter quote API | DexScreener/GeckoTerminal liquidity confirmation | Jupiter until API key/pricing risk is resolved |
| Exit realism | Jupiter quote API, snapshot liquidity decay | GeckoTerminal/DexScreener confirmation | Jupiter until governed quote limits are proven |
| Flow direction | Existing DexScreener raw split if persisted, GeckoTerminal if exposed | Helius/RPC enhanced tx evidence | Helius/RPC if indexing cost is high |
| Flow pressure | Existing DexScreener raw split if persisted, GeckoTerminal if exposed | Helius enhanced tx evidence | Any pressure source until side-aware evidence exists |

## Which Sources Cannot Solve Which Blockers

- `solana.com/data` cannot solve token-level safety, entry/exit quote realism, or pair-specific flow direction.
- Solana Status cannot solve market regime, token safety, entry/exit, or flow.
- Solana public RPC cannot solve broad market regime or practical Jupiter-style quote realism.
- DefiLlama cannot solve token authority/distribution, route quotes, or pair-specific buy/sell pressure.
- CoinGecko cannot solve unlisted memecoin safety, quote realism, or pair flow.
- GeckoTerminal cannot solve authority/freeze/holder safety by itself.
- GoPlus-like safety data cannot solve market/chain/entry/exit/flow.
- Jupiter cannot solve market regime, chain heat, safety authority, or flow pressure.
- Existing DexScreener totals cannot solve market regime, chain heat, authority safety, or quote realism.

## Source Governor Requirements

Any future source must:

- Be registered in the source registry before use.
- Execute only through Source Governor.
- Record request, response, and failure rows.
- Emit `source_status` and `data_quality_label`.
- Preserve historical source failures.
- Support request-key idempotency.
- Refuse paid-only endpoints.
- Expose whether an API key is required.
- Expose rate-limit and retry-after behavior.
- Keep broad context separate from token-level evidence.
- Never call external sources from memory, retrieval, decision, or paper-monitor code directly.

Recommended future request kinds:

- `solana_official_network_context`
- `solana_status_health_context`
- `solana_public_rpc_safety_check`
- `defillama_solana_context`
- `coingecko_market_context`
- `geckoterminal_pool_context`
- `goplus_token_safety_context`
- `jupiter_paper_quote_context`

These are planning names only, not implementation instructions.

## Central Scheduler Requirements

Any future source work must:

- Be scheduled through Central Scheduler.
- Respect the existing priority order: token snapshots and paper monitoring beat broad context.
- Be bounded and operator-approved during post-RC work.
- Avoid unbounded source loops.
- Use low frequency for broad context.
- Cache slow-moving broad data.
- Stop if rate limits or source failures appear.
- Never starve memory-window close snapshots.

Suggested relative priority:

1. Existing token snapshots and memory-window close snapshots.
2. Safety/liquidity refresh for tracked tokens.
3. Jupiter paper quote realism only when an operator-approved paper-simulation/memory-audit path needs it.
4. Market regime context.
5. Solana chain heat context.
6. Backup status checks.

## Free/Public Dependency Risk

Low risk:

- Solana Status page/feed if used only for health labels.
- Existing DexScreener path already approved.

Medium risk:

- `solana.com/data`, because dashboard data may not expose a stable API and may link to commercial products.
- Solana public RPC, because public endpoints are rate-limited and not intended for production-grade high traffic.
- DefiLlama, because endpoint stability and limits need adapter-level confirmation.
- CoinGecko, because reliable quota may require demo key or paid plan pressure.
- GeckoTerminal, because the public API is beta and paid CoinGecko on-chain endpoints offer higher limits.
- GoPlus-like safety, because Solana support and free terms must be confirmed.
- Jupiter quote, because current docs show API-key authorization and platform/pricing migration risk.

High risk if misused:

- Helius, because useful features can drift into paid infrastructure, streaming, or trading-specific services.
- Any source path that requires private/dedicated infrastructure for reliable operation.

## Rate-Limit / Reliability Risk

- Broad context sources should be cached and refreshed slowly.
- Token-level snapshots remain the top evidence priority.
- Public RPC should use a strict method allowlist and tiny per-window call budget.
- Jupiter quotes should be near-memory/decision audit checks only, never a loop.
- GeckoTerminal and CoinGecko must be treated as limited unless endpoint-level quotas are explicitly documented in future adapter planning.
- Helius must be optional and free-tier only; no paid plan may be required for V1.
- Source failures must remain visible and should block only the evidence window they affect.

## V1 Compliance Verdict

Compliant planning candidates:

- `solana.com/data` as broad audit context candidate only.
- Solana Status as broad infrastructure context.
- Solana public RPC as bounded token safety evidence.
- DefiLlama as broad market/chain context.
- CoinGecko free/public/demo as broad market context.
- GeckoTerminal as backup token/pool market context.
- GoPlus-like safety source only if Solana support/free access is proven.
- Jupiter quote API only for paper-simulation entry/exit realism, never transaction building/execution.
- Existing DexScreener fields remain the first token snapshot evidence path.

Not compliant:

- Any paid-only endpoint.
- Any source that requires live wallet, transaction building, signing, or execution.
- Any source called directly by engines outside Source Governor.
- Any source loop outside Central Scheduler.
- Any source used as a score, ranking, confidence, or direct BUY signal.

## Recommended Next Safe Task

Do not start Lane 7 yet.

Recommended next safe task:

Create a documentation-only or test-only adapter-readiness matrix that defines exact endpoint candidates, required fields, source_status/data_quality mappings, rate limits, and proof fixtures for one blocker group at a time, starting with either:

1. `Jupiter paper quote realism readiness` for `ENTRY_UNKNOWN` / `EXIT_UNKNOWN`, or
2. `Solana public RPC safety readiness` for `SAFETY_UNKNOWN`.

No adapter should be implemented until the operator approves a specific candidate, endpoint, free/public access model, Source Governor contract, Scheduler priority, and fixture-only tests.

Lane 7 remains blocked unless a future approved evidence path produces clean eligible memory safely.
