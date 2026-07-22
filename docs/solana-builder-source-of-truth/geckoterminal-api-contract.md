# GeckoTerminal Public API Contract

**Status:** ADOPTED 2026-07-22 - E.28 READINESS CONTRACT PREFLIGHT CLOSED

This module defines the official GeckoTerminal Public API facts Printer V1 may
use for Solana pool discovery and pool-level market evidence. It is subordinate
to the active Printer source stack. It authorizes no API call, runtime,
campaign, memory generation, retrieval, decision, position, trade, audit, PnL,
wallet, signing, funds, or execution.

## 1. Scope

The contract covers the keyless Public API v2 endpoints currently represented
in Printer: Solana new pools, trending pools, exact pool data, pool OHLCV, and
pool trades. It defines identity, pagination, freshness, completed-candle,
coverage, provenance, missing-data, and unsupported-proof boundaries.

GeckoTerminal is a pool-market provider. It is not an on-chain mint-creation
authority, wallet-identity source, execution venue, or profit oracle.

## 2. Official Authority and Access Date

The following GeckoTerminal/CoinGecko-owned pages were accessed on
`2026-07-18`. No API request or live probe was made.

The keyless authentication, endpoint, trending, exact-pool, pagination, and
rate-limit pages were rechecked on `2026-07-19` for V2-9.7D.7B.3B. This recheck
adopts only the fixture-only trending and exact active-pool slices below. E.26
subsequently offline-proved only the fixed OHLCV/trade readiness slices. E.28 rechecked the official Public API documentation on `2026-07-22` and aligned the runtime header, limit and pacing.

| Canonical source | Adopted facts |
|---|---|
| `https://api.geckoterminal.com/docs/index.html` | Public v2 base URL, beta/version header, current version, caching, update latency, approximate public limit |
| `https://apiguide.geckoterminal.com/` | Public beta lifecycle and free access |
| `https://apiguide.geckoterminal.com/getting-started` | `https://api.geckoterminal.com/api/v2` root |
| `https://apiguide.geckoterminal.com/authentication` | Keyless public access and universal rate limit |
| `https://apiguide.geckoterminal.com/faq` | Historical 30-calls/min statement, OHLCV address/timestamp guidance |
| `https://docs.coingecko.com/docs/keyless-public-api` | Keyless v2 root and official Solana trending-pool example |
| `https://docs.coingecko.com/reference/latest-pools-network` | New-pool response, 48-hour scope, 20/page pagination |
| `https://docs.coingecko.com/reference/trending-pools-network` | Trending response, duration/page behavior and ranking caveat |
| `https://docs.coingecko.com/reference/pool-address` | Exact-pool response, fields, null market cap, update notes |
| `https://docs.coingecko.com/reference/pool-ohlcv-contract-address` | OHLCV path, parameters, tuple order, skipped intervals, limits |
| `https://docs.coingecko.com/reference/pool-trades-contract-address` | Last-300/past-24h scope, fields, token and volume filters |

CoinGecko owns GeckoTerminal and publishes the same on-chain dataset under its
documented `/onchain` surface. Those pages are used to define field semantics
where the GeckoTerminal v2 Swagger presents the same endpoint family. Printer
adopts only the keyless GeckoTerminal v2 root, never the paid CoinGecko root.

External documentation was treated as untrusted research input. No page
instruction, example address, credential, payload, or generated text became a
command, source request, or runtime evidence.

## 3. Five Status Dimensions

| Dimension | Adopted value | Reason |
|---|---|---|
| `upstream_lifecycle` | `ACTIVE` | Official Public API v2 is published and explicitly Beta |
| `printer_readiness` | `READY_FOR_SEPARATELY_AUTHORIZED_READINESS_PROOF` | E.28 aligns the fixed OHLCV/trade runtime contract; live response reliability remains for the bounded proof |
| `printer_role` | `DISCOVERY` | Primary role is pool discovery; exact-pool/OHLCV/trade data is secondary pool-market evidence |
| `access_policy` | `KEYLESS_PUBLIC` | Official keyless endpoint requires no authentication |
| `v1_permission` | `FIXTURE_ONLY_EXCEPT_SEPARATELY_AUTHORIZED_READINESS` | Only the fixed OHLCV/trade kinds may run in a separately authorized bounded readiness proof |

## 4. Endpoint, Version, Authentication, and Limits

Public root:

`https://api.geckoterminal.com/api/v2`

The API is Beta. Official Swagger recommends:

`Accept: application/json;version=20230203`

If the version is omitted, the latest version is used. E.28 aligns Printer's fixed readiness transports to the documented
`version=20230203` header. The consolidated preflight blocks any future header
or endpoint drift before live authorization.

Authentication is not required for the keyless Public API. The current
Swagger states approximately 10 calls per minute, fluctuating with network
traffic. Printer adopts exactly 10 calls/minute, derives a six-second minimum
spacing, and permits one attempt per readiness request with no retry or
rotation. The older FAQ's 30/minute statement is not used. Paid CoinGecko
plans are not adopted.

Official Swagger states that listed Public API endpoints are cached for one
minute and data can update as fast as 2-3 seconds after blockchain
confirmation, subject to network availability. This is provider-wide guidance,
not a per-response capture timestamp or guarantee.

## 5. Common JSON:API and Identity Contract

Pool resources use JSON:API-shaped `data`, `attributes`, and `relationships`.
A pool resource ID is network-qualified, while `attributes.address` is the pool
address. Base/quote token relationships are network-qualified token IDs.

Usable Printer evidence requires:

- network exactly `solana`;
- exact requested pool address when a pool-specific endpoint is used;
- exact base and quote mint identities from relationships or included data;
- exact selected token mint matched to the intended base/quote side;
- governed request/response trace and request parameters;
- no symbol, name, URL, or provider ranking used as identity.

Missing addresses, wrong network, mismatched pool/mint, malformed
relationships, or ambiguous token orientation fail closed.

## 6. New Pools Contract

`GET /networks/solana/new_pools`

Official semantics:

- returns pools created within the past 48 hours;
- returns up to 20 pools per page;
- `page` defaults to 1;
- `include` may request base token, quote token, and DEX resources;
- public/free pagination beyond page 10 is not adopted.

The endpoint is pool discovery, not proof of token creation. Its
`pool_created_at` is pair/pool age only (`T4_PAIR_ONLY`). The official docs call
the results latest pools, but Printer must preserve page number and receipt
time and must not claim full 48-hour coverage unless every permitted page was
successfully collected under a bounded Scheduler/Governor budget.

Printer currently requests only page 1 and ignores pagination. This is partial
discovery coverage, not a valid empty result or exhaustive discovery.

## 7. Trending Pools Contract

`GET /networks/solana/trending_pools`

Official semantics:

- `page` defaults to 1 and returns up to 20 pools per page;
- `duration` supports `5m`, `1h`, `6h`, and `24h` and defaults to `24h`;
- provider ranking combines engagement, market activity, and
  security/credibility factors.

Trending is provider-ranked discovery reference only. It must not become a
Printer score, rank, confidence, weight, trade signal, or proof of quality.
Printer must retain the requested duration/page. The current adapter hard-codes
page 1 and does not set or record duration, so it represents only the provider
default and partial list.

For V2-9.7D.7B.3B the adopted request is exactly:

`GET /networks/solana/trending_pools?include=base_token,quote_token,dex&page=1&duration=1h`

Only page 1 is admitted, with at most 20 returned pools. Although official
documentation permits pages 1-10 without the paid pagination extension, 7B.2
allocates one trending request per cycle. Page 2, automatic pagination, a
larger page, all-network trending, categories, and the paid CoinGecko root are
outside this contract. Page-1 receipt is explicitly partial coverage.

## 8. Exact Pool Metadata Contract

`GET /networks/solana/pools/{pool_address}`

The response may provide:

- base/quote prices in USD, native, and pair-relative units;
- pool address/name and `pool_created_at`;
- `fdv_usd` and nullable `market_cap_usd`;
- price-change buckets;
- transaction buckets with buys, sells, buyers, and sellers;
- volume buckets;
- `reserve_in_usd`;
- base/quote token and DEX relationships;
- optional composition, balances, liquidity components, or launchpad details.

Numeric values commonly arrive as strings and require finite parsing. Missing
or null values remain unknown. Unverified market cap may be null; FDV is not a
substitute for verified market cap. `reserve_in_usd` is provider pool-liquidity
context, not an executable quote or guaranteed exit.

Pool metadata can support pair age, observed price, reserve/liquidity, volume,
transaction, and price-change context for the exact pool. It cannot establish
mint creation time or complete trade history.

### 8.1 V2-9.7D.7B.3B Exact Active-Pool Slice

The adopted request is exactly:

`GET /networks/solana/pools/{pool_address}?include=base_token,quote_token,dex`

It is one exact pool, not search or pagination. The requested address must
equal `data.attributes.address`; `data.id` must be
`solana_{pool_address}`; network identity must be `solana`; and base token,
quote token, and DEX identities must resolve unambiguously through
relationships/included resources.

For the `ACTIVE_PUMPFUN` channel, the sole adopted activity interval is `m5`.
`transactions.m5.buys` and `transactions.m5.sells` must be finite,
non-negative integers and their sum must be greater than zero. Buyers, sellers,
volume, price change, reserve, and liquidity may remain separately labeled
provider observations but cannot substitute for the transaction condition.
The pool's venue/DEX is identity only; it does not prove Pump.fun origin.

The request receipt timestamp is Printer observation time. GeckoTerminal does
not provide a per-response observation timestamp. The response is usable only
when evaluated within Printer's existing 180-second receipt-age ceiling; the
official public cache can be approximately one minute and data latency is not
a guarantee. Missing receipt time, stale receipt, missing `m5`, zero activity,
wrong identity, ambiguous token orientation, malformed counts, rate limit,
timeout, non-2xx, or provider error yields no active contribution.

## 9. Pool OHLCV Contract

`GET /networks/solana/pools/{pool_address}/ohlcv/{timeframe}`

Relevant official parameters:

| Parameter | Contract |
|---|---|
| `timeframe` | `day`, `hour`, `minute`, or `second` |
| `aggregate` | minute supports `1`, `5`, `15`; hour supports `1`, `4`, `12`; other values are not adopted |
| `before_timestamp` | Unix seconds for backward queries |
| `limit` | Default 100, maximum 1000 |
| `currency` | `usd` or `token` |
| `token` | `base`, `quote`, or exact token address |
| `include_empty_intervals` | Default false; when true, gaps use prior close and zero volume |

Each row is:

`[interval_start_unix, open, high, low, close, volume]`

The timestamp marks interval start. Intervals with no swaps are omitted by
default. Therefore row adjacency is not continuity proof, and an absent row is
not a zero-volume candle unless `include_empty_intervals=true` was explicitly
requested and preserved.

The official response has no explicit completed-candle flag. Printer may call a
candle completed only when its valid start plus the requested interval is no
later than a trusted evaluation time. The newest row must never be assumed
closed. Currency, token orientation, aggregate, interval boundaries, and gap
policy must be retained in provenance.

Printer's current `minute?aggregate=15&limit=2&currency=usd&token=base`
selection implements a conservative arithmetic close check, but its descending
ordering assumption is not formally pinned in the adopted prose contract.
Until fixture and isolated proof establish ordering and boundary behavior,
network OHLCV reliance remains blocked.

## 10. Pool Trades Contract

`GET /networks/solana/pools/{pool_address}/trades`

The endpoint returns the last 300 trades in the past 24 hours for the exact
pool. Official trade attributes include block number, transaction hash,
from-address, token amounts, token addresses, USD/token-relative prices, block
timestamp, `kind`, and USD volume.

Relevant filters:

- `trade_volume_in_usd_greater_than`, default `0`;
- `token`, default `base`, with `base`, `quote`, or exact token address.

There is no adopted pagination contract for retrieving beyond the returned 300.
A response of fewer than 300 valid records can support bounded returned-set
coverage only when no filter excludes qualifying records and every record is
well formed. Reaching a timestamp at or before a target window boundary can
support window coverage only when ordering, no omitted records, token
orientation, and filter semantics are proven and preserved.

The E.26 repair requests the endpoint without a volume filter, rejects the
entire evidence item when any returned trade row or timestamp is malformed,
and counts only trades whose timestamps fall inside the exact completed 15m
OHLCV window. A returned set is complete only when it has fewer than 300 valid
records or the oldest returned valid record reaches the window start. This is
bounded exact-window evidence, not a claim of exhaustive chain activity.

## 11. Ordering, Freshness, and Coverage

- New-pool and trending pages are bounded provider lists, not exhaustive market
  coverage when only page 1 is collected.
- OHLCV tuple order is defined; response row ordering is
  `UNKNOWN_REQUIRES_RESEARCH` for Printer's keyless v2 contract until pinned.
- Trade endpoint scope is last 300 trades in 24 hours; exact response ordering
  is `UNKNOWN_REQUIRES_RESEARCH` until pinned.
- Public responses are documented as cached for one minute. Local receipt time
  is not provider observation time.
- The current registry's 180-second stale threshold is Printer policy, not a
  provider freshness guarantee.
- Provider latency, chain availability, skipped OHLCV intervals, rate limits,
  and capped trades can make evidence partial.

No response may be called complete merely because HTTP 200 was returned.

## 12. Null, Malformed, Stale, and Error Behavior

The following are partial, dirty, blocked, failed, or unknown as appropriate:

- null or missing mandatory field;
- malformed JSON:API resource, numeric value, timestamp, or relationship;
- empty data where the endpoint does not prove a valid empty result;
- stale local receipt or expired evidence boundary;
- rate limit, timeout, transport error, non-2xx response, or provider error;
- wrong network, pool, mint, token side, currency, timeframe, or aggregate;
- partial pagination, capped trade history, skipped/malformed trade records;
- in-progress or ambiguously ordered OHLCV candle;
- provider/schema/version drift.

Retries, if later implemented, must be small, bounded, Scheduler-led, and
Governor-accounted. Failure must never be relabeled as zero activity.

## 13. Supported Evidence Contributions

After later repair and proof, exact-linked GeckoTerminal data may contribute:

- pool discovery and provider trending reference;
- `pool_created_at` as T4 pair age only;
- pool-observed price and price-change context;
- `reserve_in_usd` as provider liquidity context;
- volume and transaction buckets with exact timeframe labels;
- completed exact-pool OHLCV open/high/low/close/volume;
- bounded pool-trade records and counts when coverage is actually proven.

All values remain provider observations. They do not independently establish
clean memory, safety, continuation, tradeability, or money outcome.

## 14. Descriptive or Unsafe-to-Treat-as-Proof

- Pool/token names, symbols, images, URLs, sentiment, and community reports are
  descriptive only.
- Trending membership/order is provider ranking, not Printer ranking or proof.
- FDV is not verified market cap.
- Pool reserve, balance, and liquidity values are not executable fill proof.
- Buys/sells/buyers/sellers are provider categories, not authentic independent
  participant proof.
- `tx_from_address` is an observed transaction address, not beneficial-owner
  identity.
- OHLCV and trade history do not prove all chain activity was indexed.
- Absence from new/trending pages does not prove a pool does not exist.

## 15. What GeckoTerminal Cannot Prove

GeckoTerminal cannot prove:

- token/mint creation time or initialize-mint transaction;
- wallet authenticity, beneficial ownership, or participant independence;
- common control, coordination, wash activity, insider behavior, or
  manipulation intent;
- token authority safety, holder authenticity, or complete rug protection;
- current executable route, quote, slippage, latency, fill, or exit;
- realized paper or real profit;
- permission for memory, retrieval, decisions, BUY/SELL/HOLD, positions,
  trades, audits, or PnL.

## 16. Exact Provenance and Fail-Closed Rules

Every usable contribution must retain:

- provider, Public API root, and requested version header;
- exact endpoint and governed request kind;
- exact network, pool, base/quote mints, and selected token side;
- page/duration/include parameters for list endpoints;
- timeframe, aggregate, currency, token, limit, gap policy, and
  `before_timestamp` for OHLCV;
- trade filters and returned-count/coverage diagnostics;
- governed request/response/failure IDs;
- request, receipt, and evaluation times;
- raw field name, normalized field, and derivation formula;
- source status, data-quality label, and blocker/unknown reason.

Wrong identity, stale or missing evidence, partial pages, malformed rows,
ambiguous candle completion, unproven trade coverage, or provenance gaps fail
closed. One source must not overwrite equal/higher-authority evidence.

## 17. Governed Request Kinds

| Request kind | Status | Purpose |
|---|---|---|
| `geckoterminal_new_pool_discovery` | Existing; fixture-only under this contract | Bounded Solana new-pool page |
| `geckoterminal_trending_pool_reference` | 7B.3B adopted; fixture-only | Exact page-1, 1h provider-ranked Solana pool reference |
| `geckoterminal_active_pool_reference` | 7B.3B adopted; fixture-only | One exact Solana pool's non-zero `transactions.m5` observation |
| `pair_market_snapshot` | Existing shared compatibility kind; fixture-only | Exact-pool metadata fallback |
| `geckoterminal_ohlcv_15m` | E.26 offline-proven; separately authorized readiness proof only | Exact-pool completed 15m OHLCV; one attempt, no retry/rotation |
| `geckoterminal_pool_trades_15m` | E.26 offline-proven; separately authorized readiness proof only | Exact-pool unfiltered bounded trade history for the same 15m window; one attempt, no retry/rotation |
| `geckoterminal_pool_snapshot` | Superseded for 7B by `geckoterminal_active_pool_reference`; `NOT_IMPLEMENTED` | Broader provider-specific exact-pool name |
| `geckoterminal_pool_ohlcv` | Proposed, `NOT_IMPLEMENTED` | Parameterized bounded exact-pool OHLCV |
| `geckoterminal_pool_trades` | Proposed, `NOT_IMPLEMENTED` | Parameterized bounded exact-pool trades |

No kind is activated here. Any future request must remain Source-Governed,
Scheduler-led, bounded to the free quota, read-only, and isolated from
downstream capabilities.

## 18. Current Printer Implementation Audit

| Location | Current behavior | Contract result |
|---|---|---|
| `sources/registry.py` | Keyless Solana source; 10/min; 180-second stale policy; zero retries | E.28 aligned to the stricter current Swagger limit |
| `sources/geckoterminal.py` | Correct v2 endpoint family, governed identity checks, fixture-only metadata | Useful base; version header differs from current docs |
| discovery URLs | Hard-coded page 1 | Partial coverage; pagination and bounded-page policy absent |
| pool normalizer | Maps exact pool/base mint, price, reserve, volume, txns, pair age | Base/quote orientation and null/malformed semantics need stricter pinning |
| pair snapshot | Requires price, liquidity, FDV/market cap, h24 volume/txns, pair age | Conservative local gate; requirements are Printer policy, not provider completeness |
| `geckoterminal_15m.py` OHLCV | Parses all valid rows, selects the newest completed exact 900-second candle, and rejects stale/malformed evidence without trusting response order | E.26 offline-proven for readiness composition |
| trade URL | Sends no volume filter | Compatible with bounded total-returned-set transaction proof |
| trade counter | Rejects malformed rows and requires exact OHLCV-window alignment plus bounded coverage | E.26 offline-proven; still bounded by the provider's 300-record response cap |
| storage | Governed source traces plus normalized snapshot JSON/provenance | No migration needed; raw contract fields are not all first-class |
| focused tests | Fixture-backed identity, rate/error, candle, cap, storage, zero-unlock behavior | Protect current code; do not prove current provider behavior |

## 19. Required Later Network Proof

Before any broader governed GeckoTerminal network reliance beyond the two bounded readiness kinds:

1. Pin the current official v2 OpenAPI schemas and version header in fixtures.
2. Adopt the stricter current free ceiling and bounded per-cycle budgets.
3. Implement bounded page/duration provenance and honest partial coverage.
4. Strictly validate pool/base/quote identity, numeric nullability, and errors.
5. Confirm live responses preserve the E.26 ordering-independent completed
   candle selection and exact 900-second boundary.
6. Confirm the unfiltered trade response and fail-closed malformed-row behavior.
7. Confirm live last-300 ordering and exact-window coverage without pagination
   or exhaustive-chain claims.
8. Preserve provider cache/freshness uncertainty and fail closed on stale data.
9. Prove timeout/rate-limit/provider errors create no false zero or success.
10. Prove isolated DB traces, exact provenance, bounded requests, and zero
    retrieval/financial deltas.

## 20. UNKNOWN_REQUIRES_RESEARCH, Locks, and Change History

| Item | Status |
|---|---|
| Why older FAQ says 30/min while current Swagger says approximately 10/min | Adopt 10; reverify before implementation |
| Exact keyless v2 response ordering for OHLCV and trades | `UNKNOWN_REQUIRES_RESEARCH` |
| Exact keyless v2 endpoint-specific cache age beyond provider-wide one minute | `UNKNOWN_REQUIRES_RESEARCH` |
| Whether all documented CoinGecko response fields/nullability are identical on keyless v2 | Fixture-pin before use |
| Complete indexing/chain-latency guarantees | `UNKNOWN_REQUIRES_RESEARCH` |
| Beneficial-owner mapping and wallet authenticity | Not proven; remains partial |

This contract preserves Solana-only, memecoin-only, paper-only, free-source,
Source-Governed, Scheduler-led operation. It unlocks no source request, clean
memory promotion, retrieval, decision, BUY/SELL/HOLD, position, trade, audit,
PnL, wallet, private key, signing, funds, paid dependency, score, rank,
confidence, weighting, embedding, vector, or live execution.

| Date | Change |
|---|---|
| 2026-07-22 | E.28 reverified the official Public API root, `version=20230203`, keyless access and approximately 10/minute limit; aligned registry, pacing and zero-retry readiness configuration |
| 2026-07-18 | Audited current official GeckoTerminal/CoinGecko documentation; adopted provider contract as `PARTIAL_WITH_BLOCKER` and `ALLOWED_FIXTURE_ONLY` |
