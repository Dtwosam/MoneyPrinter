Codex Build Version - single-system rewrite of the MoneyPrinter whitepaper

Purpose: make Printer one aligned Solana memecoin memory and paper-trading machine. Every part must help Printer protect capital, learn from clean historical episodes, and move toward becoming a realistic money-making machine.

*This rewrite removes repeated rules, aligns all engines into one lifecycle, and keeps V1 strictly paper-only. It is designed to be broken into Codex implementation prompts later.*

# 0. System Charter

## 0.1 Printer Identity

Printer V1 is a Solana-only memecoin memory and paper-trading machine. It tracks Solana memecoins, records their full market conditions, rejects dirty or unrealistic data, stores clean historical episodes, compares new setups against prior memories, and outputs paper-only decisions.

Printer V1 is not a live trading bot. It does not touch real funds, sign transactions, connect to a trading wallet, or depend on paid APIs. Its job is to prove that memory-backed paper decisions can survive real Solana memecoin conditions before any future live system is discussed.

## 0.2 Single Goal

Printer has one final goal: become a money-making machine. V1 does not try to do this by trading live. V1 does it by learning which actions protected capital or made money in realistic paper conditions.

Printer must learn from action and inaction: buying, selling, holding, waiting, avoiding, missing entries, entering late, selling early, round-tripping, and doing nothing when data was weak.

## 0.3 Scope

| **Scope Item** | **V1 Rule**                                                                       |
|----------------|-----------------------------------------------------------------------------------|
| Chain          | Solana only. No Base, Ethereum, BNB Chain, or multi-chain logic in V1.            |
| Asset class    | Solana memecoins and Pump.fun / Solana DEX meme behavior.                         |
| Mode           | Paper trading only. No real wallet. No private keys. No live execution.           |
| Data           | Free/public data only. Paid APIs and paid social/smart-wallet tools are excluded. |
| Decision style | Memory comparison only. No scoring system.                                        |
| Output actions | BUY, SELL, HOLD, WAIT, AVOID, NO_ACTION. All are paper-only.                      |

## 0.4 Allowed Free-First Data Sources

- DexScreener - main free source for Solana pair discovery, liquidity, volume, FDV, price changes, boosted tokens, and token profiles.

- GeckoTerminal - backup pool/OHLC/liquidity/volume confirmation, used carefully because public limits are limited.

- PumpPortal free streams - subscribeNewToken and subscribeMigration only. Metered trade/account streams are not required in V1.

- Alternative.me Fear & Greed - broad crypto sentiment backdrop.

- CoinGecko free/public/demo data - BTC, ETH, SOL market context and broad market movement.

- DefiLlama - Solana TVL, DEX volume, stablecoin, fees/revenue, and liquidity context where useful.

- GoPlus or similar free safety data where available.

- Solana public RPC / Helius free tier - limited raw confirmation, mint/account/pool checks, and safety verification.

- Jupiter quote API - paper simulation only for quote/slippage/price-impact checks.

## 0.5 Excluded V1 Dependencies

- Paid Birdeye, paid LunarCrush, paid X API, paid smart-wallet tools, paid sentiment tools, paid execution infrastructure, and any feature that cannot work without paid data.

- Live wallet connection, private keys, real buying, real selling, signing transactions, or real fund movement.

- Any scoring system: buy score, sell score, confidence score as trigger, safety score, liquidity score, chart score, flow score, market score, combined score, or any point-based decision.

## 0.6 Decision Outputs

| **Action** | **Meaning in Printer V1**                                                                                                      |
|------------|--------------------------------------------------------------------------------------------------------------------------------|
| BUY        | Printer would enter a paper position because similar clean memories support the setup and entry is realistic.                  |
| SELL       | Printer would exit a paper position because memory, exit realism, or invalidation conditions support selling.                  |
| HOLD       | Printer would keep a paper position open because similar memories support continuation and risk has not invalidated the trade. |
| WAIT       | Printer sees something forming, but memory or data does not support action yet.                                                |
| AVOID      | Printer sees enough danger or historically bad setup behavior to stay away. Avoid is a real decision.                          |
| NO_ACTION  | Printer does not have enough clean data or memory to make a useful decision.                                                   |

## 0.7 Core Rules That Apply Everywhere

1.  Memory-backed only: every decision must be supported by clean historical memory or choose WAIT, AVOID, or NO_ACTION.

2.  No scoring: engines describe conditions and compare memories; they never convert conditions into points.

3.  Profit reality: paper profit only counts if entry and exit were realistic under liquidity, slippage, price impact, and timing.

4.  Manipulation-aware: price and volume alone are never trusted. Printer watches fake volume, wash-like behavior, thin liquidity pumps, insider-style selling, sudden liquidity removal, and fast pump-dumps.

5.  Clean memory only: incomplete, stale, broken, delayed, or missing critical data becomes DIRTY_MEMORY and DO_NOT_TRAIN.

6.  Source failure honesty: missing data is marked missing. Failed sources are recorded. Printer never invents market, price, liquidity, safety, or flow data.

7.  Avoid is useful: correct avoids and wrong avoids are both stored and audited because avoiding bad setups is part of making money.

8.  Token-level reality beats broad context: market regime and Solana heat are context, not trade signals.

9.  Paper first: V1 must prove the system before live trading is discussed.

## 0.8 Required Decision Explanation Template

- Decision

- Current setup

- Market condition

- Solana condition

- Safety condition

- Liquidity / exit condition

- Trading flow condition

- Chart / volatility condition

- Similar clean memories found

- What happened in those memories

- Best historical action

- Worst historical action

- Current action

- Reason

- Invalidation condition

- Paper trade status

## 0.9 Printer Lifecycle

10. Collect broad market context.

11. Collect Solana memecoin environment context.

12. Discover candidate Solana memecoins worth tracking.

13. Run safety/rug checks.

14. Check liquidity and exit realism.

15. Record trading flow.

16. Record chart and volatility behavior.

17. Schedule token snapshots at the right frequency.

18. Close clean memory windows only when complete.

19. Build episodes and memory fingerprints.

20. Compare current setups to similar clean memories.

21. Make paper decisions only from memory.

22. Audit every paper decision and paper P/L.

23. Improve memory quality and decision rules without breaking V1 restrictions.

# 1. Shared Data Quality, Labels, and System Contracts

## 1.1 Source Status

| **Status**  | **Meaning**                                           | **Can Support Clean Memory?**             |
|-------------|-------------------------------------------------------|-------------------------------------------|
| COMPLETE    | All required fields were captured from valid sources. | Yes                                       |
| PARTIAL     | Required fields captured, optional fields missing.    | Yes, if required fields are strong enough |
| FAILED      | One or more required fields are missing.              | No                                        |
| STALE       | Data is too old to trust.                             | No                                        |
| CONFLICTING | Sources disagree in a way that matters.               | Only WATCH_ONLY unless resolved           |

## 1.2 Data Quality Labels

- CLEAN_DATA

- ACCEPTABLE_PARTIAL_DATA

- DIRTY_DATA

- STALE_DATA

- MISSING_CRITICAL_DATA

- CONFLICTING_DATA

- DO_NOT_TRAIN

Only CLEAN_DATA and acceptable partial data can become clean memory. Any critical gap blocks training use.

## 1.3 Memory Windows

| **Window**                | **Role**                                                                                                                                                  |
|---------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------|
| 5 minutes                 | Support micro-event window. Used to study fast pump-dumps, wick pumps, micro-trades, late-buy traps, and first-burst behavior. Not a main outcome window. |
| 15 minutes                | First clean outcome window. A 15m memory must complete the full 15m span without critical gaps.                                                           |
| 1 hour                    | Short-term continuation/failure memory.                                                                                                                   |
| 4 hours                   | Medium-term behavior memory.                                                                                                                              |
| 12 hours                  | Survival, delayed dump, revival, and longer consolidation memory.                                                                                         |
| 24 hours                  | Full-day outcome memory.                                                                                                                                  |
| 30 hours retained context | Used to keep surrounding context after 24h so late effects, delayed rugs, revivals, and audit checks can be attached.                                     |

## 1.4 Clean Window Rule

A memory window is clean only if the full window completes with enough required snapshots and critical fields. If tracking is incomplete, broken, delayed, stale, or missing critical fields, the resulting episode must be marked DIRTY_MEMORY and DO_NOT_TRAIN. Partial windows may be stored for audit, but cannot drive decisions as clean memory.

## 1.5 Unified Engine Rule

Each engine has one job. Context engines do not trade. Discovery does not trade. Safety does not buy. Liquidity does not buy. Flow does not buy. Chart does not buy. The Memory Engine compares completed episodes. The Paper Trading Engine uses that memory comparison to make paper-only decisions.

# 2. Market Regime Engine

## 2.1 Purpose

The Market Regime Engine records the wider crypto market condition around every Solana memecoin setup. It gives Printer context so future memories are compared inside the right market environment.

A Solana memecoin setup can behave differently when BTC is pumping, BTC is dumping, SOL is strong, SOL is weak, the market is fearful, the market is greedy, traders are chasing risk, or traders are protecting capital.

## 2.2 Core Question

What kind of wider crypto market was this Solana memecoin trading inside when the setup appeared?

## 2.3 Labels

- EXTREME_FEAR

- FEAR

- NEUTRAL

- GREED

- EXTREME_GREED

- RISK_ON

- RISK_OFF

- CHOPPY

- VOLATILE

- UNKNOWN

## 2.4 Transition Labels

- FEAR_TO_NEUTRAL

- NEUTRAL_TO_GREED

- GREED_TO_EXTREME_GREED

- EXTREME_GREED_TO_GREED

- GREED_TO_NEUTRAL

- NEUTRAL_TO_FEAR

- FEAR_TO_EXTREME_FEAR

- RISK_OFF_TO_RISK_ON

- RISK_ON_TO_RISK_OFF

- CHOPPY_TO_TRENDING

- TRENDING_TO_CHOPPY

- UNKNOWN_TRANSITION

## 2.5 Data Captured

| **Required**                | **Optional**                                     |
|-----------------------------|--------------------------------------------------|
| captured_at                 | ETH trend                                        |
| BTC price or BTC 24h change | Solana TVL                                       |
| SOL price or SOL 24h change | Solana DEX volume context                        |
| Fear & Greed label or value | stablecoin context                               |
| market_regime_label         | tracked Solana meme volume                       |
| source_status               | tracked Solana hot pair count and meme liquidity |

## 2.6 Storage Table

Suggested table: printer_market_regime_snapshots

- id

- captured_at

- btc_price_usd

- btc_change_1h

- btc_change_24h

- btc_change_7d

- eth_price_usd

- eth_change_24h

- eth_change_7d

- sol_price_usd

- sol_change_1h

- sol_change_24h

- sol_change_7d

- sol_volume_24h

- fear_greed_value

- fear_greed_label

- fear_greed_previous_value

- fear_greed_previous_label

- solana_tvl_usd

- solana_dex_volume_context

- stablecoin_context

- tracked_solana_meme_volume

- tracked_solana_meme_liquidity

- tracked_solana_hot_pair_count

- tracked_solana_new_pair_count

- market_regime_label

- market_transition_label

- data_quality_label

- source_status

- created_at

## 2.7 Snapshot Frequency

- Every 15 minutes for active market context.

- Every 1 hour for stable storage.

- Immediate refresh if SOL or BTC moves sharply.

- Immediate refresh if Fear & Greed source updates.

## 2.8 Output

- current_market_regime

- current_market_transition

- market_data_quality

- market_snapshot_id

## 2.9 Locked Rule

Market regime is not a trade signal. It is a memory condition. Printer must never buy or sell because of market regime alone.

# 3. Solana Chain Heat Engine

## 3.1 Purpose

The Solana Chain Heat Engine records the local Solana memecoin environment around every token episode. Since Printer is Solana-only, it must understand whether Solana meme activity is healthy, rotating, manipulated, cooling, or dead.

## 3.2 Core Question

What kind of Solana memecoin environment was this token trading inside?

## 3.3 Main Principle

Solana heat must be proven by tradable behavior, not vibes. SOL price being up, one token pumping, many launches, or many boosted tokens does not automatically mean healthy heat. Healthy heat requires broad activity, liquidity support, token survival, and enough exit liquidity for realistic paper trades.

## 3.4 Labels

| **Label**               | **Meaning**                                                                                                            |
|-------------------------|------------------------------------------------------------------------------------------------------------------------|
| SOLANA_MEME_HOT         | Broad activity, rising volume/liquidity, migrations active, multiple tokens surviving beyond first windows.            |
| SOLANA_MEME_ACTIVE      | Healthy but not overheated activity; steady liquidity and usable movement.                                             |
| SOLANA_MEME_ROTATING    | Liquidity and attention moving quickly from older tokens to newer tokens. Holding too long may be punished.            |
| SOLANA_MEME_CHOPPY      | Unstable activity, failed breakouts, short-lived pumps, weak commitment.                                               |
| SOLANA_MEME_COOLING     | Activity, liquidity, migrations, and survival are weakening.                                                           |
| SOLANA_MEME_DEAD        | Very weak activity; most new setups die quickly.                                                                       |
| SOLANA_MEME_MANIPULATED | Activity looks high but unhealthy: thin liquidity, boosted visibility, suspicious vertical moves, weak follow-through. |
| SOLANA_MEME_UNKNOWN     | Missing, stale, conflicting, or unclear data.                                                                          |

## 3.5 Transition Labels

- DEAD_TO_ACTIVE

- ACTIVE_TO_HOT

- HOT_TO_ROTATING

- HOT_TO_COOLING

- ACTIVE_TO_CHOPPY

- CHOPPY_TO_ACTIVE

- COOLING_TO_DEAD

- DEAD_TO_MANIPULATED

- MANIPULATED_TO_ACTIVE

- UNKNOWN_TRANSITION

## 3.6 Data Captured

| **Required**                                        | **Optional**                                            |
|-----------------------------------------------------|---------------------------------------------------------|
| captured_at                                         | Solana TVL, DEX volume, stablecoin context, fee context |
| SOL price or SOL 24h change                         | Pump.fun new token count and migration count            |
| new_solana_pairs_count or active_solana_pairs_count | boosted token count and hot pair count                  |
| tracked_solana_meme_volume                          | median pair liquidity and low-liquidity pair count      |
| tracked_solana_meme_liquidity                       | migrated token survival/failure counts                  |
| chain_heat_label                                    | liquidity inflow/outflow context                        |
| source_status                                       | tracked meme FDV total where useful                     |

## 3.7 Storage Table

Suggested table: printer_solana_chain_heat_snapshots

- id

- captured_at

- sol_price_usd

- sol_change_1h

- sol_change_24h

- sol_change_7d

- sol_volume_24h

- solana_tvl_usd

- solana_dex_volume_context

- solana_stablecoin_context

- solana_fee_context

- new_pumpfun_tokens_count

- pumpfun_migrations_count

- new_solana_pairs_count

- active_solana_pairs_count

- hot_solana_pairs_count

- boosted_solana_tokens_count

- tracked_solana_meme_volume

- tracked_solana_meme_liquidity

- tracked_solana_meme_fdv_total

- average_tracked_pair_liquidity

- median_tracked_pair_liquidity

- low_liquidity_pair_count

- dead_new_pair_count

- migrated_token_survival_count

- migrated_token_failure_count

- liquidity_inflow_context

- liquidity_outflow_context

- chain_heat_label

- chain_heat_transition_label

- data_quality_label

- source_status

- created_at

## 3.8 Snapshot Frequency

| **Condition**                        | **Frequency**                                                               |
|--------------------------------------|-----------------------------------------------------------------------------|
| Normal                               | Every 20 minutes                                                            |
| Active or hot                        | Every 15 minutes                                                            |
| Extreme launch or migration activity | Every 10 minutes for discovery-related counters if free-source limits allow |
| GeckoTerminal backup                 | Every 20-30 minutes when needed                                             |
| DefiLlama context                    | Every 30-60 minutes                                                         |
| CoinGecko SOL context                | Every 15-20 minutes                                                         |

## 3.9 Priority Rule

Token-level tracking always beats broad chain heat. If free API limits or system resources are tight, Printer prioritizes tracked token snapshots, hot token flow/chart snapshots, safety/rug checks, discovery updates, then chain heat and backups.

## 3.10 Output

- current_solana_chain_heat

- current_chain_heat_transition

- chain_heat_data_quality

- chain_heat_snapshot_id

## 3.11 Locked Rule

Solana chain heat is not a buy or sell signal. It is a memory condition used to compare token setups against past completed episodes from similar Solana environments.

# 4. Discovery Engine

## 4.1 Purpose

The Discovery Engine finds Solana memecoins worth tracking. It is the front door of Printer. It does not buy, sell, or create scores. It only decides whether a token should enter tracking and how urgently.

## 4.2 Core Question

Should Printer track this Solana memecoin, and how urgently?

## 4.3 Tracking Actions

| **Action**     | **Meaning**                                                                                                           |
|----------------|-----------------------------------------------------------------------------------------------------------------------|
| TRACK_FAST     | Token is moving, changing, risky, or important enough to capture high-detail memory quickly. Not a buy signal.        |
| TRACK_NORMAL   | Token has enough data and activity for regular tracking.                                                              |
| WATCH_ONLY     | Token may become useful later, but does not yet deserve full tracking resources.                                      |
| IGNORE         | Token is not worth regular attention unless a strong revival or valid new source appears.                             |
| INSTANT_REJECT | Token is too dangerous, broken, untradeable, or useless for active tracking. It may still be stored as reject memory. |

## 4.4 Discovery Channels

| **Channel**                | **Default Handling**                                                                    |
|----------------------------|-----------------------------------------------------------------------------------------|
| New Pump.fun launch        | Usually WATCH_ONLY or IGNORE unless valid pair/liquidity/activity appears quickly.      |
| Pump.fun migration         | Usually TRACK_NORMAL or TRACK_FAST depending on liquidity, activity, and data quality.  |
| New Solana DEX pair        | Action depends on liquidity, volume, pair age, txns, and source quality.                |
| Boosted token              | WATCH_ONLY or TRACK_NORMAL. Boost is attention, not quality.                            |
| Sudden volume              | TRACK_NORMAL until liquidity, safety, and flow are checked.                             |
| Sudden liquidity           | TRACK_NORMAL or TRACK_FAST if volume, txns, and price behavior support deeper tracking. |
| Fast 5m micro-pump         | TRACK_FAST if usable liquidity and pair data exist.                                     |
| Liquidity reduction        | TRACK_NORMAL if active/known, because liquidity decay is important memory.              |
| Volume reduction           | TRACK_NORMAL or WATCH_ONLY depending on prior state.                                    |
| Stable/consolidating token | WATCH_ONLY or TRACK_NORMAL if active and useful for memory.                             |
| Revived token              | WATCH_ONLY or TRACK_NORMAL; may become TRACK_FAST if sharp revival occurs.              |
| Hot pair token             | TRACK_NORMAL unless token-level conditions justify TRACK_FAST.                          |

## 4.5 Core Learning Rule

Discovery must feed full market-behavior memory, not only bullish memory. Printer learns from pumps, dumps, consolidation, stable ranges, dead movement, revival, fake pumps, micro-pumps, liquidity increase/decrease, volume increase/decrease, transaction changes, holder changes where available, and failed breakouts.

## 4.6 Micro-Pump Rule

Printer must not automatically label every fake-looking pump as useless. Some fake pumps are untradable traps. Some are tradable micro-pumps if entered early and exited fast. Discovery must preserve this difference for later memory.

- TRADABLE_MICRO_PUMP

- UNTRADABLE_MICRO_PUMP

- FAKE_PUMP_WITH_EXIT

- FAKE_PUMP_NO_EXIT

- FAST_PUMP_DUMP

- WICK_PUMP

- LATE_BUY_TRAP

- MICRO_PUMP_TO_SUSTAINED_PUMP

- MICRO_PUMP_TO_CONSOLIDATION

- MICRO_PUMP_TO_DEAD_TOKEN

## 4.7 Required Discovery Fields

- discovered_at

- discovery_source

- discovery_channel

- token_mint

- chain

- token_name where available

- token_symbol where available

- initial_tracking_action

- discovery_reason

- source_status

- discovery_data_quality

## 4.8 Required Fields for TRACK_NORMAL or TRACK_FAST

- valid token_mint

- pair_address or pool_address

- dex_id where available

- pair_created_at or pair_age_seconds estimate

- token_age_seconds where available

- liquidity_usd

- liquidity_state

- price_usd or price_native

- volume and transaction activity where available

- price_change windows where available or internally calculated

- FDV and market_cap where available

- fdv_liquidity_ratio where available

- volume_liquidity_ratio where available

- boost_status where available

- migration_status where available

- token_activity_state

- micro_event_state

- source_status not FAILED or STALE

## 4.9 Discovery Reasons

- NEW_PUMPFUN_LAUNCH

- PUMPFUN_MIGRATION

- NEW_SOLANA_PAIR

- DEXSCREENER_PROFILE

- DEXSCREENER_BOOST

- DEXSCREENER_ACTIVE_BOOST

- DEXSCREENER_AD

- SUDDEN_VOLUME

- VOLUME_DECAY

- STABLE_VOLUME

- SUDDEN_LIQUIDITY

- LIQUIDITY_DECAY

- STABLE_LIQUIDITY

- TXN_SPIKE

- TXN_DECAY

- STABLE_TXNS

- HOT_PAIR

- FAST_MICRO_PUMP

- FAST_PUMP_DUMP

- WICK_PUMP

- CONSOLIDATION_ACTIVITY

- DUMP_ACTIVITY

- REVIVED_ACTIVITY

- DEAD_ACTIVITY

- MANUAL_REVIEW

- BACKUP_SOURCE_CONFIRMATION

## 4.10 State Labels

| **State Type** | **Labels**                                                                                                                      |
|----------------|---------------------------------------------------------------------------------------------------------------------------------|
| Liquidity      | LIQUIDITY_RISING, LIQUIDITY_FALLING, LIQUIDITY_STABLE, LIQUIDITY_MISSING, LIQUIDITY_REMOVED, LIQUIDITY_THIN, LIQUIDITY_ABNORMAL |
| Volume         | VOLUME_RISING, VOLUME_FALLING, VOLUME_STABLE, VOLUME_MISSING, VOLUME_SPIKE, VOLUME_DECAY, VOLUME_ABNORMAL                       |
| Transactions   | TXNS_RISING, TXNS_FALLING, TXNS_STABLE, TXNS_MISSING, TXNS_SPIKE, TXNS_DECAY, TXNS_ABNORMAL                                     |
| Price          | PRICE_RISING, PRICE_FALLING, PRICE_STABLE, PRICE_SPIKING, PRICE_DUMPING, PRICE_RANGING, PRICE_REVIVING, PRICE_DEAD              |
| Token activity | NEW, ACTIVE, HOT, COOLING, CHOPPY, CONSOLIDATING, DUMPING, DEAD, REVIVING, UNKNOWN                                              |

## 4.11 Polling and Enrichment Frequencies

| **Item**                                   | **Frequency / Rule**                                                                  |
|--------------------------------------------|---------------------------------------------------------------------------------------|
| PumpPortal new token and migration streams | One stable websocket connection. Event-based. No metered trade/account streams in V1. |
| DexScreener latest token profiles          | Every 10-15 minutes.                                                                  |
| DexScreener latest boosted tokens          | Every 10-15 minutes.                                                                  |
| DexScreener top boosted tokens             | Every 15-20 minutes.                                                                  |
| DexScreener new pair / token pair checks   | Every 5-10 minutes.                                                                   |
| WATCH_ONLY refresh                         | Every 20-30 minutes unless activity appears.                                          |
| IGNORE / INSTANT_REJECT                    | No regular refresh unless strong revival or valid new source appears.                 |
| GeckoTerminal backup                       | Every 20-30 minutes only when needed.                                                 |
| RPC / Helius confirmation                  | Only after initial discovery filters or for suspicious/high-priority tokens.          |

## 4.12 Promotion and Demotion

| **Change**                         | **Triggers**                                                                                                                                                         |
|------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| WATCH_ONLY to TRACK_NORMAL         | Liquidity appears, valid pair appears, volume/txns start, migration happens, token survives early window, activity revives, or consolidation becomes useful.         |
| WATCH_ONLY to TRACK_FAST           | Migration plus strong activity, fast 5m micro-pump with usable liquidity, multiple discovery channels, sudden liquidity and volume together, sharp revival.          |
| TRACK_NORMAL to TRACK_FAST         | Volume/liquidity/txns expand or collapse sharply, hot-pair activity, migration keeps activity, important dump/consolidation/revival, micro-pump state.               |
| TRACK_FAST to TRACK_NORMAL         | Micro-event ends, volume fades, liquidity stabilizes, price inactive, token leaves hot activity, slower consolidation.                                               |
| TRACK_NORMAL to WATCH_ONLY         | Activity fades, volume dies, liquidity too thin, pair weakens, token stale, useful windows close.                                                                    |
| Any active state to INSTANT_REJECT | Liquidity removed, severe safety/rug result, pair data breaks, token untradeable, known bad pattern, micro-pump proven untradable with no remaining useful activity. |

## 4.13 Storage Tables

- printer_token_discoveries

- printer_discovery_events

- printer_tracking_queue

- printer_micro_events

## 4.14 Output

- token_mint

- pair_address

- discovery_reason

- current_tracking_action

- tracking_priority

- discovery_data_quality

- micro_event_state where applicable

- discovery_record_id

## 4.15 Locked Rule

Discovery is intake, not alpha. It decides what Printer should watch so future memory can teach profit or loss. No token moves from discovery directly into paper BUY.

# 5. Safety / Rug Filter Engine

## 5.1 Purpose

The Safety / Rug Filter Engine identifies danger before Printer wastes resources or opens a paper trade. It protects Printer from obvious traps, severe risk patterns, untradeable tokens, and memory pollution.

## 5.2 Core Question

Is this token safe enough to track, simulate, or include in clean memory, and what risks must future memory remember?

## 5.3 Main Principle

Safety does not buy. Safety can block or downgrade tracking, force AVOID, prevent paper BUY, or mark an episode as unsafe/dirty. A token can pump and still be unsafe. Printer must record that difference.

## 5.4 Checks

| **Check Area**           | **What Printer Looks For**                                                                                            |
|--------------------------|-----------------------------------------------------------------------------------------------------------------------|
| Authority checks         | Mint authority, freeze authority, upgrade/mint risks where detectable, and whether token control creates severe risk. |
| Liquidity safety         | Liquidity removed, liquidity too thin, abnormal liquidity changes, LP concentration, sudden pool weakness.            |
| Holder concentration     | Top-holder risk, abnormal distribution, wallet clusters where free data allows, suspicious concentration.             |
| Dev/creator/pool wallets | Creator-style selling, pool wallet behavior, repeated dangerous launch patterns where detectable.                     |
| Metadata/name/symbol     | Impersonation, copycat names, suspicious metadata changes, missing/abnormal links where useful.                       |
| Tradeability             | Broken pair data, failed quote, impossible exit, severe slippage/price impact.                                        |
| Micro-pump safety        | Wick-only moves, thin-liquidity vertical pumps, pump with no exit, sudden liquidity removal after attention.          |

## 5.5 Safety Labels

- SAFETY_CLEAR

- SAFETY_CAUTION

- SAFETY_ELEVATED_RISK

- SAFETY_HIGH_RISK

- SAFETY_SEVERE_RISK

- UNTRADEABLE

- UNKNOWN_SAFETY

## 5.6 Safety Actions

- ALLOW_TRACKING

- DOWNGRADE_TO_WATCH_ONLY

- BLOCK_TRACK_FAST

- BLOCK_PAPER_BUY

- FORCE_AVOID

- MARK_DIRTY_MEMORY

- ARCHIVE_REJECT_MEMORY

- RECHECK_REQUIRED

## 5.7 Required Fields

- checked_at

- token_mint

- pair_address or pool_address where relevant

- safety_label

- safety_action

- source_status

- data_quality_label

- critical_flags

- reason

## 5.8 Storage Table

Suggested table: printer_token_safety_checks

- id

- token_mint

- pair_address

- checked_at

- mint_authority_status

- freeze_authority_status

- liquidity_safety_state

- holder_concentration_state

- dev_wallet_state

- metadata_state

- tradeability_state

- critical_flags

- safety_label

- safety_action

- source_status

- data_quality_label

- created_at

## 5.9 Check Frequency

| **Token State**          | **Safety Frequency**                                                                      |
|--------------------------|-------------------------------------------------------------------------------------------|
| TRACK_FAST / micro-event | At discovery/promotion, before paper BUY, and on sharp liquidity/price/flow changes.      |
| TRACK_NORMAL             | At discovery/promotion, before paper BUY, and around memory-window close.                 |
| WATCH_ONLY               | Light safety check only when token is promoted or suspicious signals appear.              |
| Open paper position      | Recheck when exit danger appears, liquidity drops, price dumps, or invalidation triggers. |

## 5.10 Locked Rule

Safety cannot create a BUY. It can only protect Printer, shape memory, block bad actions, or support AVOID/WAIT/NO_ACTION. Severe safety risk must override any bullish-looking setup in V1.

# 6. Liquidity + Exit Engine

## 6.1 Purpose

The Liquidity + Exit Engine decides whether a paper trade could realistically enter and exit. It protects Printer from fake chart profit. A token going up is not a clean profit if Printer could not enter before extension or exit before liquidity disappeared.

## 6.2 Core Question

Could Printer realistically enter and exit this setup with acceptable liquidity, slippage, price impact, and timing?

## 6.3 Main Principle

Liquidity is not only a filter. It is memory. Printer must remember whether liquidity rose, fell, stayed stable, disappeared, became abnormal, supported exits, or trapped late buyers.

## 6.4 State Labels

| **Type**           | **Labels**                                                                                                                      |
|--------------------|---------------------------------------------------------------------------------------------------------------------------------|
| Liquidity state    | LIQUIDITY_RISING, LIQUIDITY_FALLING, LIQUIDITY_STABLE, LIQUIDITY_THIN, LIQUIDITY_REMOVED, LIQUIDITY_ABNORMAL, LIQUIDITY_UNKNOWN |
| Exit state         | EXIT_REALISTIC, EXIT_DIFFICULT, EXIT_FRAGILE, EXIT_UNREALISTIC, EXIT_UNKNOWN                                                    |
| Entry state        | ENTRY_REALISTIC, ENTRY_LATE, ENTRY_TOO_EXTENDED, ENTRY_UNREALISTIC, ENTRY_UNKNOWN                                               |
| Slippage state     | SLIPPAGE_ACCEPTABLE, SLIPPAGE_HIGH, SLIPPAGE_SEVERE, SLIPPAGE_UNKNOWN                                                           |
| Price impact state | PRICE_IMPACT_ACCEPTABLE, PRICE_IMPACT_HIGH, PRICE_IMPACT_SEVERE, PRICE_IMPACT_UNKNOWN                                           |

## 6.5 Paper Size Buckets

Paper simulation should test realistic position-size buckets instead of assuming perfect fills. Suggested buckets: micro, small, medium, and larger test sizes, defined in configuration as dollar amounts. Each paper trade must store the bucket used.

## 6.6 What Printer Must Learn

- Whether rising liquidity supported continuation.

- Whether falling liquidity preceded dumps or rugs.

- Whether high FDV with thin liquidity created fake upside.

- Whether volume rose without liquidity support.

- Whether liquidity stayed long enough for exit.

- Whether micro-pumps were only tradable at small size.

- Whether consolidation with stable liquidity led to breakout, breakdown, or no action.

- Whether dumps with liquidity decay required earlier selling.

## 6.7 Required Fields

- checked_at

- token_mint

- pair_address

- liquidity_usd

- liquidity_state

- entry_realism_state

- exit_realism_state

- slippage_state

- price_impact_state

- paper_size_bucket

- quote_source where used

- source_status

- data_quality_label

## 6.8 Storage Table

Suggested table: printer_liquidity_exit_checks

- id

- token_mint

- pair_address

- checked_at

- liquidity_usd

- liquidity_change_5m

- liquidity_change_15m

- liquidity_change_1h

- liquidity_change_4h

- liquidity_change_12h

- liquidity_change_24h

- fdv

- fdv_liquidity_ratio

- volume_liquidity_ratio

- paper_size_bucket

- entry_realism_state

- exit_realism_state

- estimated_slippage

- slippage_state

- estimated_price_impact

- price_impact_state

- quote_source

- source_status

- data_quality_label

- created_at

## 6.9 Check Frequency

- Before any paper BUY or SELL decision.

- During active paper positions at the snapshot frequency required by Part 9.

- Faster during micro-events, dumps, liquidity decay, or exit danger.

- At memory-window close to verify whether paper P/L was realistic.

## 6.10 Locked Rule

A chart pump is not enough. Printer only treats paper profit as useful if the Liquidity + Exit Engine confirms realistic entry and exit conditions.

# 7. Trading Flow Engine

## 7.1 Purpose

The Trading Flow Engine records whether token activity looks like real demand, fake demand, seller pressure, buyer exhaustion, rotation, or manipulation. It studies the behavior behind price movement.

## 7.2 Core Question

What kind of buy/sell flow, transaction activity, and pressure pattern was happening while this token moved?

## 7.3 Main Principle

Flow is not a buy signal. It is memory context. Printer must learn which flow patterns led to continuation, reversal, failed pumps, late-buy traps, dumps, consolidation, or revivals.

## 7.4 Data Captured

- buy/sell transaction counts where available

- buy/sell volume where available

- transaction spikes/decay

- volume spikes/decay

- buyer growth or stall where available

- seller pressure

- exit flow

- flow imbalance

- flow quality

- flow changes across 5m, 15m, 1h, 4h, 12h, and 24h windows

## 7.5 Labels

| **Type**     | **Labels**                                                                                           |
|--------------|------------------------------------------------------------------------------------------------------|
| Trading flow | FLOW_EXPANDING, FLOW_FADING, FLOW_STABLE, FLOW_SPIKING, FLOW_COLLAPSING, FLOW_ABNORMAL, FLOW_UNKNOWN |
| Buyer state  | BUYERS_INCREASING, BUYERS_FADING, BUYERS_STABLE, BUYERS_EXHAUSTED, BUYERS_UNKNOWN                    |
| Seller state | SELLERS_INCREASING, SELLERS_FADING, SELLERS_STABLE, SELLERS_DOMINANT, SELLERS_UNKNOWN                |
| Pressure     | BUY_PRESSURE, SELL_PRESSURE, BALANCED_PRESSURE, PRESSURE_FLIPPING, PRESSURE_UNKNOWN                  |
| Exit flow    | EXIT_FLOW_HEALTHY, EXIT_FLOW_FRAGILE, EXIT_FLOW_DANGEROUS, EXIT_FLOW_UNKNOWN                         |
| Flow quality | REALISTIC_FLOW, THIN_FLOW, WASH_LIKE_FLOW, MANIPULATED_FLOW, CONFLICTING_FLOW, UNKNOWN_FLOW          |

## 7.6 Micro-Pump Flow Handling

During a 5m micro-event, Printer must record whether flow was early enough, broad enough, and liquid enough to support a realistic paper trade. A fast move with fake or thin flow may become FAKE_PUMP_NO_EXIT or LATE_BUY_TRAP memory instead of profit memory.

## 7.7 Required Fields

- checked_at

- token_mint

- pair_address

- volume_state

- transaction_state

- pressure_state

- flow_quality_label

- source_status

- data_quality_label

## 7.8 Storage Table

Suggested table: printer_trading_flow_snapshots

- id

- token_mint

- pair_address

- captured_at

- buy_txns_5m

- sell_txns_5m

- buy_volume_5m

- sell_volume_5m

- txns_15m

- txns_1h

- volume_15m

- volume_1h

- volume_4h

- volume_12h

- volume_24h

- buyer_state

- seller_state

- pressure_state

- transaction_state

- volume_state

- exit_flow_label

- flow_quality_label

- source_status

- data_quality_label

- created_at

## 7.9 Locked Rule

Trading flow cannot override safety, liquidity, or clean memory. It only helps Printer understand whether past and current movement had real demand, fake demand, seller pressure, or exit danger.

# 8. Chart / Volatility Engine

## 8.1 Purpose

The Chart / Volatility Engine records how price actually behaved: pump, dump, wick, range, breakout, breakdown, consolidation, exhaustion, revival, volatility compression, or volatility expansion.

## 8.2 Core Question

What did the chart structure and volatility do during this setup, and what happened after similar structures in clean memory?

## 8.3 Main Principle

The chart is evidence, not proof. Printer must not buy because price is green. It must record chart behavior together with liquidity, flow, safety, market regime, Solana heat, and memory outcome.

## 8.4 Labels

| **Type**      | **Labels**                                                                                                                                           |
|---------------|------------------------------------------------------------------------------------------------------------------------------------------------------|
| Chart state   | CHART_PUMPING, CHART_DUMPING, CHART_RANGING, CHART_CONSOLIDATING, CHART_BREAKING_OUT, CHART_BREAKING_DOWN, CHART_REVIVING, CHART_DEAD, CHART_UNKNOWN |
| Volatility    | VOLATILITY_LOW, VOLATILITY_NORMAL, VOLATILITY_HIGH, VOLATILITY_EXTREME, VOLATILITY_COMPRESSING, VOLATILITY_EXPANDING, VOLATILITY_UNKNOWN             |
| Candle/wick   | GREEN_CANDLE, RED_CANDLE, WICK_UP, WICK_DOWN, WICK_ONLY_PUMP, REJECTION_CANDLE, UNKNOWN_CANDLE                                                       |
| Breakout      | CLEAN_BREAKOUT, FAILED_BREAKOUT, LATE_BREAKOUT, BREAKOUT_UNKNOWN                                                                                     |
| Breakdown     | CLEAN_BREAKDOWN, FAILED_BREAKDOWN, BREAKDOWN_UNKNOWN                                                                                                 |
| Dump          | FAST_DUMP, SLOW_BLEED, LIQUIDITY_DUMP, PANIC_DUMP, DUMP_UNKNOWN                                                                                      |
| Consolidation | HEALTHY_CONSOLIDATION, WEAK_CONSOLIDATION, DISTRIBUTION_RANGE, ACCUMULATION_RANGE, CONSOLIDATION_UNKNOWN                                             |
| Revival       | REAL_REVIVAL, FAKE_REVIVAL, REVIVAL_TO_SECOND_WAVE, REVIVAL_TO_DUMP, REVIVAL_UNKNOWN                                                                 |

## 8.5 What Printer Must Learn

- Whether breakouts held or failed.

- Whether wicks turned into traps.

- Whether extended moves punished late entries.

- Whether consolidation with stable liquidity preceded continuation.

- Whether volatility compression led to expansion.

- Whether revived charts produced second waves or exit liquidity.

- Whether holding after first pump caused round-tripping.

- Whether selling into chart exhaustion protected profit.

## 8.6 Required Fields

- captured_at

- token_mint

- pair_address

- price_usd or price_native

- price_change_5m where available

- price_change_15m

- price_change_1h

- chart_state

- volatility_state

- source_status

- data_quality_label

## 8.7 Storage Table

Suggested table: printer_chart_volatility_snapshots

- id

- token_mint

- pair_address

- captured_at

- price_usd

- price_native

- price_change_5m

- price_change_15m

- price_change_1h

- price_change_4h

- price_change_12h

- price_change_24h

- high_5m

- low_5m

- high_15m

- low_15m

- local_top_time

- local_bottom_time

- chart_state

- volatility_state

- wick_state

- breakout_state

- breakdown_state

- dump_state

- consolidation_state

- revival_state

- source_status

- data_quality_label

- created_at

## 8.8 Locked Rule

Chart behavior cannot trigger trades alone. It must be attached to clean memory and realism checks before any paper decision.

# 9. High-Frequency Token-Level Snapshot Scheduler

## 9.1 Purpose

The Snapshot Scheduler records tracked tokens often enough to create clean memory. It does not make trading decisions. It controls when and how rich token snapshots are captured.

## 9.2 Core Question

How often should Printer snapshot this token so the eventual memory window is clean, realistic, and useful?

## 9.3 Main Correction

Discovery polling is not token-level tracking. Discovery finds candidates. Token snapshots record what happens to a specific tracked token. Memory windows decide whether those snapshots become usable memory.

## 9.4 Token Tracking Lanes

| **Lane**                   | **Meaning**                                                                         |
|----------------------------|-------------------------------------------------------------------------------------|
| PAPER_MONITORING           | Open or recently active paper position. Highest priority.                           |
| TRACK_FAST                 | High-priority active token, micro-event, dump, strong change, or fast-moving setup. |
| TRACK_NORMAL               | Useful tracked token with normal activity.                                          |
| WATCH_ONLY                 | Light monitoring; not enough for full tracking.                                     |
| COOLDOWN                   | Token recently active but slowing down.                                             |
| ARCHIVED                   | Useful windows closed; no regular tracking.                                         |
| INSTANT_REJECT_MEMORY_ONLY | Rejected token stored for avoid/reject memory, not active tracking.                 |

## 9.5 Snapshot Modes

- NORMAL_MODE

- MICRO_EVENT_MODE

- DUMP_MODE

- CONSOLIDATION_MODE

- REVIVAL_MODE

- WINDOW_CLOSE_MODE

- PAPER_EXIT_PROTECTION_MODE

## 9.6 Recommended Token Snapshot Frequency

| **Lane / Mode**        | **Frequency**                                                                                |
|------------------------|----------------------------------------------------------------------------------------------|
| PAPER_MONITORING       | Fast enough to protect exits; speed up on dump, liquidity decay, flow flip, or invalidation. |
| TRACK_FAST first 15m   | Every 1-3 minutes if free-source limits allow.                                               |
| TRACK_FAST until 1h    | Every 3-5 minutes after first 15m if still active.                                           |
| TRACK_FAST until 4h    | Every 5-10 minutes if still relevant.                                                        |
| TRACK_NORMAL first 15m | Every 5-10 minutes.                                                                          |
| TRACK_NORMAL until 1h  | Every 10-15 minutes.                                                                         |
| TRACK_NORMAL until 4h  | Every 15-30 minutes if still relevant.                                                       |
| WATCH_ONLY             | Every 20-30 minutes, faster only if activity appears.                                        |
| Micro-event active     | Every 1-3 minutes during the event if limits allow.                                          |
| Window close           | Force final snapshot near each memory-window close.                                          |

## 9.7 Rich Snapshot Feature Set

- price

- liquidity

- volume

- transactions

- FDV/market cap

- price changes across windows

- liquidity changes

- volume changes

- txns changes

- safety state

- exit realism

- slippage/price impact where needed

- flow state

- chart state

- market_snapshot_id

- chain_heat_snapshot_id

- tracking_lane

- snapshot_mode

- source_status

- data_quality_label

## 9.8 Speed-Up Triggers

- open paper position

- fast 5m pump

- dump or fast selloff

- liquidity removal/decay

- volume spike or collapse

- transaction spike or collapse

- safety danger

- revival

- breakout/breakdown

- approaching memory-window close

- exit quote/slippage danger

## 9.9 Slow-Down / Stop Rules

- activity fades after useful window closes

- token becomes stale

- liquidity becomes unusable

- token moves to WATCH_ONLY or ARCHIVED

- safety rejects token

- free-source capacity is needed for higher-priority tokens

## 9.10 Snapshot Cleanliness

Every snapshot must record source status, data quality, captured_at, and critical fields. Dirty snapshots can be stored for audit but cannot support clean memory. A memory window fails cleanliness if coverage, timing, or critical fields are insufficient.

## 9.11 Storage Table

Suggested table: printer_token_snapshots

- id

- token_mint

- pair_address

- captured_at

- tracking_lane

- snapshot_mode

- price_usd

- price_native

- liquidity_usd

- volume_5m

- volume_15m

- volume_1h

- volume_4h

- volume_12h

- volume_24h

- txns_5m

- txns_15m

- txns_1h

- txns_4h

- txns_12h

- txns_24h

- fdv

- market_cap

- price_change_5m

- price_change_15m

- price_change_1h

- price_change_4h

- price_change_12h

- price_change_24h

- liquidity_state

- volume_state

- transaction_state

- price_state

- safety_label

- exit_realism_state

- flow_quality_label

- chart_state

- market_snapshot_id

- chain_heat_snapshot_id

- source_status

- data_quality_label

- created_at

## 9.12 Locked Rule

Part 9 records enough evidence for memory and paper audit. It must not make trade decisions, open paper trades, or weaken data rules to create more memories.

# 10. Episode / Memory Engine

## 10.1 Purpose

The Episode / Memory Engine turns completed token tracking windows into clean historical memory. It decides whether snapshots are good enough to train decisions and what action would have worked or failed.

## 10.2 Core Question

What happened in this completed episode, was the memory clean, and what did it teach Printer about buying, selling, holding, waiting, avoiding, or doing nothing?

## 10.3 Episode Definition

An episode is a completed token behavior window tied to a token, pair, market regime snapshot, Solana chain heat snapshot, safety state, liquidity/exit state, flow state, chart state, and outcome. Episodes may be 15m, 1h, 4h, 12h, or 24h. Micro-events are attached as support evidence.

## 10.4 Episode Types

- PUMP_EPISODE

- DUMP_EPISODE

- CONSOLIDATION_EPISODE

- RANGE_EPISODE

- REVIVAL_EPISODE

- DEAD_TOKEN_EPISODE

- MICRO_PUMP_EPISODE

- FAST_PUMP_DUMP_EPISODE

- WICK_PUMP_EPISODE

- LIQUIDITY_DECAY_EPISODE

- VOLUME_DECAY_EPISODE

- SAFETY_REJECT_EPISODE

- PAPER_POSITION_EPISODE

- AVOID_OUTCOME_EPISODE

- WAIT_OUTCOME_EPISODE

- NO_ACTION_EPISODE

## 10.5 Outcome Labels

| **Category**   | **Labels**                                                                                                                                                                                                                                                              |
|----------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Market outcome | SUSTAINED_PUMP, SHORT_TERM_PUMP, FAKE_PUMP, FAST_PUMP_DUMP, DUMP, SLOW_BLEED, CONSOLIDATION, RANGE, REVIVAL, DEAD, RUG_OR_LIQUIDITY_REMOVAL, UNKNOWN_OUTCOME                                                                                                            |
| Money outcome  | PAPER_PROFIT_REALISTIC, PAPER_PROFIT_FRAGILE, PAPER_PROFIT_UNREALISTIC, PAPER_LOSS, ROUND_TRIP, MISSED_ENTRY, LATE_ENTRY_TRAP, CORRECT_AVOID, WRONG_AVOID, CORRECT_WAIT, WRONG_WAIT, CORRECT_SELL, EARLY_SELL, BAD_HOLD, GOOD_HOLD, NO_ACTION_CORRECT, NO_ACTION_MISSED |
| Memory status  | CLEAN_MEMORY, PARTIAL_MEMORY, DIRTY_MEMORY, DO_NOT_TRAIN, AUDIT_ONLY                                                                                                                                                                                                    |

## 10.6 Required Episode Inputs

- token discovery record

- market regime snapshot

- Solana chain heat snapshot

- token snapshots with sufficient coverage

- safety checks

- liquidity/exit checks

- trading flow snapshots

- chart/volatility snapshots

- micro-event records where present

- paper-trade records where present

- source/data quality labels

## 10.7 Clean Memory Requirements

24. The window fully completed.

25. Snapshot coverage meets the required frequency quality for that window and lane.

26. Critical fields are present: price, liquidity, volume/txns, source status, data quality, market context, chain heat context, and safety/liquidity realism where needed.

27. No critical source is FAILED or STALE.

28. Entry and exit realism are known for any paper-profit claim.

29. The episode has a clear outcome label and memory quality label.

30. The memory can explain what action worked, what action failed, and why.

## 10.8 Dirty Memory Rules

If the window is incomplete, snapshots are too sparse, sources are stale, critical fields are missing, data conflicts are unresolved, or profit cannot be realistically verified, the episode must be marked DIRTY_MEMORY or AUDIT_ONLY and cannot train decisions.

## 10.9 Memory Comparison Rule

Printer decisions require retrieval of similar clean memories. Similarity should be based on condition fingerprints, not scores. A condition fingerprint should include market regime, chain heat, discovery channel/reason, safety state, liquidity/exit state, flow state, chart/volatility state, token age/pair age, micro-event state, and memory window.

## 10.10 Minimum Memory Requirement

If Printer does not have enough similar clean memories to support a strong comparison, it must not force BUY or HOLD. It should choose WAIT, AVOID, or NO_ACTION depending on risk and data quality.

## 10.11 Best Action / Worst Action Rule

Every useful memory should help answer: which action made money, protected capital, caused loss, caused missed upside, or round-tripped profit under similar conditions? Printer must preserve both best historical action and worst historical action.

## 10.12 Action-Specific Memory Rules

| **Action** | **What Memory Must Learn**                                                                                                   |
|------------|------------------------------------------------------------------------------------------------------------------------------|
| BUY        | When buying worked, when it failed, when it was too late, when it was unrealistic, and when it required fast exit.           |
| SELL       | When selling protected profit, when selling was early, when not selling caused round-trip, and when exit became unrealistic. |
| HOLD       | When holding allowed continuation and when holding caused drawdown or round-trip.                                            |
| WAIT       | When waiting saved money, when waiting missed money, and what confirmation would have mattered.                              |
| AVOID      | When avoiding was correct, when it missed a real pump, and what conditions caused the mistake.                               |
| NO_ACTION  | When no action was right due to weak data and when lack of memory missed an opportunity.                                     |

## 10.13 Episode Lifecycle

31. Open episode when a token enters active tracking or a relevant memory window begins.

32. Attach market regime and chain heat context.

33. Attach token snapshots, safety, liquidity, flow, and chart evidence.

34. Attach micro-event evidence when present.

35. Close the window only after full duration completes.

36. Calculate outcome and paper-realism labels.

37. Assign memory quality.

38. Store clean memory, partial audit memory, or dirty memory.

39. Make clean memories retrievable for future decisions.

40. Audit memory drift and improve data collection if quality is weak.

## 10.14 Storage Tables

- printer_episodes

- printer_episode_snapshots

- printer_episode_outcomes

- printer_memory_fingerprints

- printer_memory_retrieval_index

- printer_memory_audit_reports

## 10.15 Retrieval Output Format

- similar_memory_count

- matching_conditions

- dominant_outcomes

- best_historical_action

- worst_historical_action

- profit_realism_summary

- risk_summary

- memory_conflicts

- recommended_current_action_basis

## 10.16 Memory Conflict and Drift

If similar memories conflict, Printer must say the memory is mixed and avoid forcing a strong action. If newer clean memories begin contradicting older memories, Printer must flag drift and audit whether market behavior changed, data quality changed, or earlier memories were weak.

## 10.17 Locked Rule

Part 10 is the brain of memory, not the trade executor. It must only use completed, clean, realistic episodes for decision support. Dirty memory cannot support BUY, SELL, or HOLD decisions.

# 11. Paper Trading + Audit Engine

## 11.1 Purpose

The Paper Trading + Audit Engine tests Printer decisions under realistic conditions. It opens and closes paper trades, audits paper P/L, records whether decisions made or lost money, and feeds verified results back to memory.

## 11.2 Core Question

Based on current conditions and similar clean memories, what paper action is most likely to protect capital or make money, and did the result prove realistic after audit?

## 11.3 Relationship With Previous Parts

| **Previous Part**  | **What It Provides**                                   |
|--------------------|--------------------------------------------------------|
| Market Regime      | Wider crypto environment.                              |
| Solana Chain Heat  | Local Solana memecoin environment.                     |
| Discovery          | Why token was tracked and how urgent it is.            |
| Safety             | Risk, rug, and tradeability protection.                |
| Liquidity + Exit   | Entry/exit realism, slippage, price impact.            |
| Trading Flow       | Demand/sell pressure/flow quality context.             |
| Chart / Volatility | Price structure and volatility context.                |
| Snapshot Scheduler | Evidence frequency and coverage.                       |
| Episode / Memory   | Similar clean memories and historical action outcomes. |

## 11.4 Paper Position Lifecycle

41. Decision request is created for a tracked token.

42. Current setup is assembled from all engines.

43. Similar clean memories are retrieved.

44. Safety and liquidity realism gates run.

45. Paper decision is produced.

46. If BUY, a paper position is opened only with required fields and size bucket.

47. While open, PAPER_MONITORING snapshots continue.

48. SELL, HOLD, WAIT, AVOID, or NO_ACTION updates are audited.

49. Position closes through sell condition, invalidation, window close, or exit rule.

50. Paper P/L is calculated with realistic entry/exit, slippage, and price impact.

51. Audit labels are assigned.

52. Clean audited result becomes memory only if realistic and complete.

## 11.5 Paper Entry Requirements

- enough similar clean memories supporting BUY

- safety not severe

- entry realism confirmed

- exit path realistic

- liquidity supports paper size bucket

- slippage and price impact acceptable

- snapshot frequency adequate

- current market/chain context recorded

- invalidation condition defined

- paper size bucket defined

- entry price rule applied

## 11.6 Paper Exit / SELL Requirements

- memory-backed sell condition

- invalidation condition hit

- liquidity/exit danger

- flow flip to seller pressure

- chart exhaustion or breakdown

- round-trip risk

- safety risk increases

- window close requires audit

- exit quote/slippage check confirms realistic exit

## 11.7 HOLD / WAIT / AVOID / NO_ACTION Requirements

| **Action** | **Requirements**                                                                                                 |
|------------|------------------------------------------------------------------------------------------------------------------|
| HOLD       | Open position, memory supports continuation, exit remains realistic, invalidation not hit, safety not worsening. |
| WAIT       | Setup forming but memory/data not strong enough; risk not severe enough for AVOID.                               |
| AVOID      | Danger or bad historical outcomes are strong enough to stay away; store and later audit avoid result.            |
| NO_ACTION  | Insufficient clean memory, poor data, missing critical inputs, or unknown context.                               |

## 11.8 Micro-Trade Rule

A micro-trade is valid only if Printer could detect the move early, enter before extension, exit before dump, and confirm acceptable liquidity, slippage, and price impact. A chart-only 5m gain is not clean profit unless the audit proves it was realistically tradable.

## 11.9 Late-Buy Trap and Round-Trip Rules

Printer must tag late entries that buy after the move is already extended and then fail. Printer must also tag round-trips where a paper position had profit but holding caused the gain to disappear. These are core money-machine lessons.

## 11.10 Paper P/L Calculation

- entry price must come from realistic captured price or quote near decision time

- exit price must come from realistic captured price or quote near exit time

- slippage must be applied where available

- price impact must be considered for the paper size bucket

- unrealistic exits do not count as clean profit

- perfect-top exits are not allowed unless snapshots and exit logic prove that exit was available

## 11.11 Audit Labels

| **Type**         | **Labels**                                                                                             |
|------------------|--------------------------------------------------------------------------------------------------------|
| Trade result     | PAPER_WIN_REALISTIC, PAPER_WIN_FRAGILE, PAPER_WIN_UNREALISTIC, PAPER_LOSS, PAPER_BREAKEVEN, ROUND_TRIP |
| Decision quality | GOOD_DECISION, BAD_DECISION, MIXED_DECISION, TOO_EARLY, TOO_LATE, TOO_WEAK_MEMORY, DIRTY_DATA_DECISION |
| Trade quality    | CLEAN_PAPER_TRADE, FRAGILE_PAPER_TRADE, UNREALISTIC_PAPER_TRADE, DO_NOT_TRAIN                          |

## 11.12 Storage Tables

- printer_paper_decisions

- printer_paper_positions

- printer_paper_trade_events

- printer_paper_trade_audits

- printer_paper_pl_calculations

- printer_paper_decision_memory_links

## 11.13 Paper Decision Explanation Format

- Decision

- Current setup

- Market condition

- Solana condition

- Safety condition

- Liquidity / exit condition

- Trading flow condition

- Chart / volatility condition

- Similar clean memories found

- What happened in those memories

- Best historical action

- Worst historical action

- Current action

- Reason

- Invalidation condition

- Paper trade status

- Audit plan

## 11.14 What This Engine Must Not Do

- execute live trades

- connect wallets

- sign transactions

- use real funds

- ignore safety

- ignore liquidity

- claim fake chart profit as real paper profit

- use dirty memory

- use scores

- open paper BUY with weak memory

- perfectly exit at tops without evidence

## 11.15 Locked Rule

Part 11 is paper trading only. Every paper decision must be audited. No paper trade becomes clean training memory unless it is realistic, fully audited, and supported by clean episode data.

# 12. Codex Build Order

## 12.1 Build Principle

Printer should be built as one machine, but Codex prompts should implement it in safe, testable lanes. Each lane must have a clear goal, exact files/tables/jobs affected, pass/fail checks, and strict V1 guardrails.

## 12.2 Suggested Implementation Order

53. Create system constants, labels, and shared data-quality contracts.

54. Create database schema/migrations for context snapshots, discoveries, token snapshots, safety, liquidity, flow, chart, episodes, memory, paper decisions, and audits.

55. Build source adapters with free-source limits and source_status handling.

56. Build Market Regime Engine.

57. Build Solana Chain Heat Engine.

58. Build Discovery Engine and tracking queue.

59. Build Safety / Rug Filter Engine.

60. Build Liquidity + Exit Engine and paper quote realism checks.

61. Build Trading Flow Engine.

62. Build Chart / Volatility Engine.

63. Build Snapshot Scheduler with lanes and modes.

64. Build Episode / Memory Engine with clean/dirty gates.

65. Build memory retrieval and condition fingerprint matching.

66. Build Paper Trading + Audit Engine.

67. Build reports for memory quality, paper P/L realism, decision outcomes, and drift.

68. Only after V1 proves realistic paper performance should any live-trading discussion happen.

## 12.3 Prompt Rules for Codex

69. Start each prompt with the goal in plain English.

70. State V1 restrictions: Solana only, paper only, no paid APIs, no wallet, no private keys, no live execution, no scoring.

71. Specify the exact part/engine being implemented.

72. Specify existing files/tables to inspect before writing code.

73. Define exact schema changes if needed.

74. Define source_status and data_quality behavior.

75. Define pass/fail verification commands or tests.

76. Do not let Codex jump into later engines before the current lane passes.

77. Do not accept vague output. Every lane closes with a measurable result.

78. No broad runtime, no live trading, no paper BUY unless the paper engine lane explicitly allows paper decisions and all gates are implemented.

## 12.4 Global Acceptance Gates

- Every stored record has source_status and data_quality_label where relevant.

- No engine uses scores.

- No engine buys/sells alone.

- Every memory links to market regime and chain heat context.

- Every paper trade links to similar clean memories.

- Every paper profit is audited for realistic entry and exit.

- Dirty memory is never used for decisions.

- Free-source failures are recorded, not guessed over.

- V1 remains paper-only.

# 13. Final Printer V1 Locked Rule

Printer V1 exists to build a realistic Solana memecoin money machine through memory, not hype. It must collect clean data, reject dirty data, understand context, track useful token behavior, verify liquidity and exits, compare current setups with past clean memories, make paper-only decisions, audit every result, and improve from what actually happened.

The machine should not chase every pump. It should learn which pumps were tradable, which were traps, which exits were realistic, which holds round-tripped, which waits saved money, and which avoids protected capital.

In V1, the path to making money is discipline: clean memory first, paper realism second, audited decisions third, live trading never in V1.

*Prepared as a cleaned Codex build spec from the uploaded MoneyPrinter WhitePaper document.*
