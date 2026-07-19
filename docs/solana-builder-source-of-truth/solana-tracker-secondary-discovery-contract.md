# Solana Tracker Secondary Discovery Contract

**Status:** ADOPTED 2026-07-19 FOR V2-9.7D.7B.3B FIXTURES ONLY

This contract adopts the minimum free Solana Tracker Data API REST surface for
secondary Pump.fun trending and top discovery. It authorizes no adapter,
request, secret creation, source fetch, database write, campaign, runtime,
memory, retrieval, decision, trade, or financial capability.

## Todo / Checklist

- [x] Pin REST endpoints, authentication, free quota, and finite local limits.
- [x] Pin token, mint, pool, quote, market, and freshness fields.
- [x] Bound the exact provider-side Pump.fun filtering claim.
- [x] Exclude rank, score, risk, popularity, promotion, and response order.
- [x] Define malformed, stale, quota, auth, ambiguity, and unknown handling.

## Official Authority and Access

Official Solana Tracker documentation accessed 2026-07-19:

- `https://docs.solanatracker.io/quickstart`
- `https://docs.solanatracker.io/pricing`
- `https://docs.solanatracker.io/data-api/tokens/get-trending-tokens-by-timeframe`
- `https://docs.solanatracker.io/data-api/tokens/get-top-performing-tokens`
- the linked Data API OpenAPI 3.1 schemas, version `1.0.0`

Production root: `https://data.solanatracker.io`.

Every request requires an `x-api-key` header. The official quickstart requires
a free Solana Tracker account and says the Data API key is retrieved from its
dashboard. No wallet, private key, funded account, SOL deposit, signing, or
real-fund prerequisite is documented for the Data API free plan.

The current free Data API plan is `EUR 0`, 10,000 requests/month, 3
requests/second, REST only, with no Datastream access. Exceeding plan rate or
request capacity returns HTTP 429. Paid plans, Datastream, Solana Tracker RPC,
Raptor, swap, wallet, PnL, trading, gRPC, and dedicated nodes are not adopted.

The key is a secret reference supplied by a later approved runtime. It must
never appear in URL query strings, fixtures, payload hashes, logs, reports,
databases, errors, or commits. Missing key is `BLOCKED_AUTH`, not permission to
use another product or provider.

## Adopted Endpoints

### Trending

`GET https://data.solanatracker.io/tokens/trending/1h`

- Source Governor kind: `solana_tracker_pumpfun_trending`
- Official meaning: up to 100 tokens trending by transaction volume in the
  specified one-hour timeframe.
- Pagination: none documented or adopted.
- Maximum requests per campaign cycle: 1.

### Top

`GET https://data.solanatracker.io/top-performers/1h`

- Source Governor kind: `solana_tracker_pumpfun_top`
- Official meaning: top-performing tokens launched today in the specified
  one-hour timeframe.
- Pagination: none documented or adopted.
- Maximum requests per campaign cycle: 1.

`top` means membership in this exact provider list. It does not mean largest
market cap, safest, most popular, best, profitable, or Printer-preferred.

Both requests have a 10-second local timeout and zero retries under 7B.2.
Together they reserve at most two free-plan requests per cycle. Campaign
preflight must reserve `cycle_count * 2` requests inside known remaining
monthly capacity and the 3-request/second upstream rate. Missing or unverifiable
quota blocks the provider lane. Unused capacity does not permit retries,
pagination, more timeframes, or another Solana Tracker endpoint.

## Response Schema and Identity

Both endpoints return a top-level JSON array of `TokenInfo` objects. The
adopted identity subset is:

- `token.mint`: canonical candidate mint string;
- `pools[]`: one or more provider pool observations;
- `pools[].poolId`: exact pool address;
- `pools[].tokenAddress`: must exactly equal `token.mint`;
- `pools[].quoteToken`: exact quote mint;
- `pools[].market`: provider market/launchpad label;
- `pools[].lastUpdated`: provider pool update time in Unix milliseconds;
- local governed request receipt time: Printer observation time.

Names, symbols, URIs, images, socials, decimals, creator, creation transaction,
creation time, deployer, and descriptive metadata are not identity. A response
does not contain a separate network field; the provider root is Solana-specific
but Printer must retain `network=solana` as contract provenance, not infer
another chain from names or addresses.

For every admitted observation:

1. `token.mint` must be one non-empty unambiguous mint;
2. exactly one admitted pool identity is emitted per `(channel, mint, poolId)`;
3. `poolId`, `tokenAddress`, `quoteToken`, `market`, and `lastUpdated` are
   mandatory;
4. `pool.tokenAddress == token.mint`;
5. `pool.market == "pumpfun"` using exact case-sensitive vocabulary;
6. update, receipt, and evaluation times must be finite and not future-dated;
7. pool update and response receipt must each be no more than 180 seconds old;
8. exact duplicate rows collapse; conflicting duplicates are rejected.

Multiple exact `pumpfun` pools for one mint remain separate market
observations. They do not multiply the mint's eligibility or selection
probability. A deterministic canonical sort by `(mint, poolId)` occurs only
after non-authoritative provider order is removed.

## Pump.fun Claim Boundary

The endpoints are not dedicated Pump.fun-only endpoints. Printer locally
retains only rows whose exact provider pool field says `market == "pumpfun"`.
This supports only these statements:

- provider-observed Pump.fun-market token appeared in the 1h trending list; or
- provider-observed Pump.fun-market token appeared in the 1h top-performers list.

It does not prove Pump Program creation, canonical Pump.fun origin, creation
time, bonding curve, migration, or venue authenticity. `createdOn`, mint
suffixes, URLs, names, creator fields, response membership, and category text
cannot substitute for exact pool filtering. Every candidate still requires
the separate successful finalized direct Pump-origin contract before
eligibility.

## Freshness and Observation Time

`pools[].lastUpdated` is provider pool-update evidence, not request time,
transaction time, token creation time, or proof that every field was updated
then. Printer's governed receipt time is the only response observation time.
Both timestamps and evaluation time must be retained.

The 180-second maximum is Printer policy, not a Solana Tracker SLA. No endpoint
cache/update guarantee was found in the adopted pages. Missing, seconds/millis
confusion, non-finite, stale, or materially future timestamps yield no
contribution. HTTP 200 does not prove fresh or complete coverage.

## Discarded Non-Authoritative Fields

Before eligibility, seed derivation, canonical ordering, or selection, discard:

- original array position and response order;
- `risk`, `risk.score`, risks, rugged, snipers, bundlers, insiders, top10,
  developer, fees, holder, and wallet fields;
- any `score`, rank, trending rank, performance rank, popularity, boost,
  promoted, sponsored, verified, `jupiterVerified`, or recommendation field;
- price/price-change performance, market cap, FDV, liquidity, volume, buys,
  sells, transaction totals, and holder totals as selection priority;
- names, symbols, images, socials, descriptions, URIs, and labels other than
  the exact `market == "pumpfun"` filter.

Separately adopted market fields may later remain factual provider
observations, but this discovery contract does not authorize them as
eligibility or selection inputs. Changing any discarded value or response
order must not change the normalized candidate identity set.

## Failure and Unknown Handling

| Condition | Required result |
|---|---|
| missing/invalid API key, HTTP 401/403 | `BLOCKED_AUTH`; no contribution |
| HTTP 429 or known exhausted monthly capacity | `BLOCKED_QUOTA`; no retry |
| timeout, transport, TLS, DNS, non-2xx, provider error | `FAILED_PROVIDER`; no empty success |
| non-array, malformed JSON/object, missing identity | `MALFORMED_RESPONSE`; reject response/row |
| missing/wrong `market`, mint/pool mismatch | `NOT_PUMPFUN_PROVIDER_OBSERVATION`; reject row |
| missing/stale/future `lastUpdated` or receipt | `STALE_OR_UNKNOWN`; reject row |
| conflicting duplicate or ambiguous identity | `AMBIGUOUS_IDENTITY`; reject conflict |
| empty well-formed array | factual empty provider list only; never market absence |
| over 100 rows | `SCHEMA_OR_LIMIT_DRIFT`; reject response |
| undocumented pagination/cursor/next link | do not follow; record drift |

All failures retain provider, secret-free endpoint, request kind, timeframe,
request/response/failure identity, receipt/evaluation times, HTTP status where
available, quota counters where available, and exact reason. Provider failure
is isolated and cannot authorize fallback, retry, endpoint rotation, another
timeframe, or another product.

## Scheduler and Governor Ownership

Both request kinds belong to source `solana_tracker` and one cycle-rooted
Central Scheduler work item:

`job_kind=DISCOVERY_REFRESH`,
`work_type=DISCOVERY_SOLANA_TRACKER_TRENDING_TOP`.

Source Governor admits each request. Central Scheduler owns creation, lease,
deadline, cancellation, terminal state, and later-cycle eligibility. A future
adapter may normalize only returned bytes; it may not schedule, retry, paginate,
rotate keys/endpoints, query quota, or call another surface independently.

The two calls remain inside the combined 45-call, 360-second, 8-MiB, and
failure ceilings frozen by 7B.2. Raw response remains capped at 1 MiB.
Disabled/unconfigured/auth-blocked provider work is
`SKIPPED_BLOCKED_CONTRACT` or its exact later terminal equivalent, never
silently absent.

## Authority Boundaries and Unknowns

Solana Tracker may contribute provider list membership and exact provider
token/pool/quote/market identities. It cannot prove complete population,
canonical Pump.fun creation/migration, token legitimacy, safety, wallet
identity, coordination, manipulation, executable liquidity, route, fill, exit,
profit, clean-memory fitness, retrieval relevance, or a decision/action.

Exact cache interval, tie-breaking, ranking formula, stable response order,
historical coverage, and a provider guarantee that `market="pumpfun"` always
maps to the official Pump Program are `UNKNOWN_REQUIRES_RESEARCH`. They are not
needed for the narrow fail-closed membership contract.

## Money-Usefulness

The two lists can broaden the factual candidate set while exact mint/pool
filtering and aggressive field stripping prevent provider promotion, risk
scores, performance ranks, and response order from steering later sampling.
Direct finalized origin remains mandatory, so provider marketing cannot become
fake provenance. This improves corpus diversity only; it predicts and unlocks
nothing.

## Remaining Locks

API-key creation/configuration, production registry, adapter, normalizer,
network requests, live proof, schema/database changes, combined execution,
campaign, runtime, pilot, memory generation, retrieval, decisions,
BUY/SELL/HOLD, positions, trades, audits, PnL, wallets, keys, signing, funds,
paid plans, scoring, ranking, confidence, weighting, embeddings, vectors, and
live execution remain locked.

## Functionality Risks / Setbacks / Efficiency Blockers

- Free quota/rate terms can change and require activation-time recheck.
- An API key/account is required even though the plan is free.
- Lists are curated/ranked subsets and are not Pump.fun-only upstream.
- Exact `pumpfun` spelling is provider vocabulary, not on-chain authority.
- No cache/update guarantee makes the 180-second rule conservative.
- Strict filtering reduces yield; top-performers is launched-today performance,
  not a general top-token fact.
- Score/risk/activity fields are tempting shortcuts but remain excluded.

## Stop Boundary

This document ends at fixture-only contract adoption. Do not create/configure
a key, implement an adapter, make a provider request, repair persistence,
execute combined discovery, run live proof, close V2-9.7D, or start a pilot.