# Printer V1 V2-9.7D.7B.3B Secondary Discovery Contract Adoption Closeout

## Verdict

`V2_9_7D_7B_3B_SECONDARY_DISCOVERY_CONTRACT_ADOPTION_PASS`

PASS means the minimum GeckoTerminal and Solana Tracker secondary discovery
contracts are bounded, fail-closed, and synthetic-fixture proven, while current
PumpPortal access is explicitly blocked. It does not activate an adapter,
secret, provider call, schema, database, campaign, runtime, retrieval, or
financial capability.

## Todo / Checklist

- [x] Verify exact starting commit and tracked baseline.
- [x] Reconcile 7B.1, 7B.2, existing provider contracts, and governance rules.
- [x] Recheck current official provider authentication, quota, and schemas.
- [x] Repair/adopt minimum GeckoTerminal trending and active-pool slices.
- [x] Adopt minimum Solana Tracker free REST trending/top slices.
- [x] Recheck and keep PumpPortal blocked under current access requirements.
- [x] Prove identity extraction, failure handling, and field/order stripping.
- [x] Run bypass and diff checks and preserve downstream locks.

## Scope and Baseline

- Starting HEAD: `051cbe13584173842f96bb6c2236db2e503fe550`
- Starting tracked tree: clean
- Existing unrelated untracked artifacts: observed and untouched
- External work: official-documentation/current-public-contract research only
- Provider calls, account/key creation, WebSocket/RPC activity, source fetching,
  database commands, schemas, migrations, and runtime: none
- Lane changes: provider/governance documentation, one synthetic fixture, one
  fixture-only test, and this closeout

## Provider Disposition

| Provider | 7B.3B result | Exact role | Runtime state |
|---|---|---|---|
| GeckoTerminal keyless v2 | ADOPTED for fixture-only trending and active-pool contracts | Page-1 1h trending pool membership; one exact pool's non-zero `transactions.m5` | No adapter/network activation |
| Solana Tracker free Data API REST | ADOPTED for fixture-only trending/top contracts | Locally filtered provider `pumpfun` pool membership in `/tokens/trending/1h` and `/top-performers/1h` | No key creation, adapter, or network activation |
| PumpPortal | BLOCKED | None | Current access requires API key, linked wallet, and at least 0.02 SOL funding |
| DexScreener | UNCHANGED | Existing fresh-profile/active-market authority only | Not expanded |
| PumpSwap | UNCHANGED | Exact migration/pool confirmation only | Never candidate origin |

Pumpdev remains excluded from automatic planning.

## Adopted Authority and Contracts

### GeckoTerminal

Official GeckoTerminal/CoinGecko-owned pages rechecked 2026-07-19 establish:

- keyless root `https://api.geckoterminal.com/api/v2`;
- no authentication header for the public root;
- dynamic keyless fair-use throttling, with the existing stricter Printer
  ceiling of approximately 10 calls/minute retained;
- trending endpoint pages of at most 20, provider durations `5m`, `1h`, `6h`,
  and `24h`, and paid access beyond page 10;
- JSON:API pool/base/quote/DEX identity relationships;
- exact-pool transaction buckets including `m5`; and
- public caching/latency guidance that is not a response timestamp or SLA.

Adopted 7B requests:

- `geckoterminal_trending_pool_reference`:
  `/networks/solana/trending_pools`, exact `page=1`, `duration=1h`, and
  `include=base_token,quote_token,dex`; at most one call and 20 pools.
- `geckoterminal_active_pool_reference`:
  `/networks/solana/pools/{pool_address}`, exact pool identity and includes;
  at most one call and active only when finite non-negative
  `transactions.m5.buys + sells > 0`.

Printer receipt time is observation time; no provider observation timestamp is
invented. The existing 180-second receipt-age policy is retained. Missing,
stale, wrong-network, wrong-pool, ambiguous base/quote/DEX, malformed activity,
zero activity, rate limit, timeout, non-2xx, and provider errors contribute
nothing and never become zero-activity success.

### Solana Tracker

Official Solana Tracker pages accessed 2026-07-19 establish:

- root `https://data.solanatracker.io`;
- required `x-api-key` from a free account dashboard;
- free Data API plan: EUR 0, 10,000 requests/month, 3 requests/second, REST only;
- HTTP 429 after rate/capacity exhaustion;
- `/tokens/trending/{timeframe}` returns up to 100 tokens trending by
  transaction volume for the timeframe;
- `/top-performers/{timeframe}` returns top-performing tokens launched today;
- OpenAPI 3.1 version `1.0.0` `TokenInfo`, `Token`, `Pool`, `Events`, and `Risk`
  schemas; and
- no pagination contract for these two fixed lists.

Adopted 7B requests are exactly:

- `solana_tracker_pumpfun_trending` -> `GET /tokens/trending/1h`;
- `solana_tracker_pumpfun_top` -> `GET /top-performers/1h`.

Each has one request/cycle, 10-second timeout, zero retries. Exact identity is
`token.mint`, `poolId`, matching `pool.tokenAddress`, `quoteToken`, exact
case-sensitive `market == "pumpfun"`, and `lastUpdated`, plus governed receipt
time. Provider update and receipt must each be at most 180 seconds old.

These endpoints are not Pump.fun-only. The valid claim is only that a provider
`pumpfun` pool row appeared in the provider list. Direct successful finalized
on-chain origin verification remains mandatory. The API key is a secret
reference only and may never enter URLs, fixtures, logs, hashes, reports,
databases, errors, or commits.

### PumpPortal

Current official PumpPortal documentation rechecked 2026-07-19 uses
`wss://pumpportal.fun/api/data?api-key=...` and says token/account subscriptions
require an API key with a linked wallet funded with at least `0.02 SOL`.
Token/migration event categories are described as free, but trade streams are
metered.

The key/wallet/funding prerequisite conflicts with Printer locks. The prior
anonymous endpoint proof is retained as historical evidence only. No workaround,
wallet, deposit, signing, key, real funds, paid/metered path, or request kind is
adopted. PumpPortal remains `SKIPPED_BLOCKED_CONTRACT`.

## Exact Authority Boundaries

GeckoTerminal can establish provider-observed pool identity, page-1 trending
membership, and exact-pool `m5` transaction activity. Solana Tracker can
establish exact provider token/pool/quote/market identity and membership in its
1h trending or top-performers list. Neither can establish canonical Pump.fun
origin, mint creation, safety, authenticity, common control, insider status,
coordination, manipulation, executable liquidity, route, fill, exit, profit,
clean-memory fitness, retrieval relevance, or a decision.

DexScreener authority was not expanded. PumpSwap remains confirmation-only.
No provider may override direct finalized on-chain origin evidence or another
equal/higher-authority exact identity.

## Discarded Non-Authoritative Fields

Synthetic normalization proves exclusion of:

- response position/order and rank;
- provider scores, GT scores, risk scores, rugged/risk lists;
- popularity, trending/performance rank, boost, promotion, sponsorship, and
  verified/Jupiter-verified flags;
- snipers, bundlers, insiders, holders, developer, top-holder, wallet, and fee
  analytics;
- price change, price performance, market cap, FDV, liquidity, volume, buy/sell
  totals, and activity values as selection priority;
- names, symbols, images, socials, descriptions, URIs, and marketing labels.

Gecko `transactions.m5` is used only as the fixed categorical active condition,
not as a score or ordering value. Changing discarded fields or response order
does not change the canonical normalized identity set.

## Authentication and Quota Findings

- GeckoTerminal: keyless public v2, dynamic IP throttling; Printer retains the
  conservative 10/minute provider ceiling and the stricter two-call cycle slice.
- Solana Tracker: account plus secret `x-api-key`; free EUR 0 plan, 10,000
  requests/month, 3 requests/second; two calls/cycle maximum and quota
  reservation required before later use.
- PumpPortal: API key plus linked/funded wallet; incompatible and blocked.
- No paid CoinGecko, Solana Tracker, PumpPortal, or other provider path adopted.

## Remaining Implementation Order

1. V2-9.7D.7B.4A direct adapter/continuity implementation, when requested.
2. V2-9.7D.7B.4B secondary adapters using only these adopted contracts and
   unchanged DexScreener/PumpSwap authority.
3. V2-9.7D.7B.4C persistence reconciliation only after adapter proof.
4. V2-9.7D.7B.4D combined execution owner only after dependencies pass.
5. Disposable combined proof, then separately approved live-provider slices.

This lane starts none of those steps.

## Money-Usefulness

Secondary lists can diversify the future candidate corpus, while exact
pool/mint filtering, strict freshness, direct-origin dependency, and aggressive
rank/score/order stripping prevent provider marketing and performance lists
from becoming fake quality or selection priority. PumpPortal is sacrificed
rather than weakening wallet/funds locks. The result improves factual intake
breadth without predicting or unlocking profit.

## Proof

| Check | Result |
|---|---|
| Exact starting commit and clean tracked baseline | PASS |
| Official endpoint/schema/auth/quota reconciliation | PASS |
| Gecko trending identity/page/duration contract | PASS |
| Gecko exact active-pool `m5` contract | PASS |
| Solana Tracker exact `pumpfun` mint/pool filter | PASS |
| PumpPortal incompatible-access blocking | PASS |
| Rank/score/risk/promotion/order mutation invariance | PASS |
| Malformed, stale, mismatch, zero-active, and over-limit failures | PASS |
| Source Governor/Central Scheduler bypass scan | PASS |
| `git diff --check` | PASS |
| `git diff --stat` and lane-scope review | PASS |

Focused fixture result: `4 passed`.

The pytest cache warning is environmental: pytest could not write its cache
path. It did not affect the test result or lane files.

## Files Changed

- `docs/solana-builder-source-of-truth/geckoterminal-api-contract.md`
- `docs/solana-builder-source-of-truth/solana-tracker-secondary-discovery-contract.md`
- `docs/solana-builder-source-of-truth/pumpportal-api-contract.md`
- `docs/solana-builder-source-of-truth/source-governor-evidence-rules.md`
- `tests/fixtures/secondary_discovery_contracts.json`
- `tests/test_secondary_discovery_contract_fixtures.py`
- `docs/printer-v1-v2-9-7d-7b-3b-secondary-discovery-contract-adoption-closeout.md`

## What Was Built

- Repaired GeckoTerminal trending and exact active-pool fixture contracts.
- Adopted Solana Tracker free REST trending/top fixture contract.
- Rechecked and blocked current PumpPortal access.
- Added Source Governor evidence-rule documentation for the adopted kinds.
- Added synthetic schema, identity, freshness, filtering, stripping, and
  fail-closed proof.

## What Was Not Touched

- Production adapters, registries, secrets, provider calls, schemas, migrations,
  databases, persistence, combined execution, campaign runtime, or pilot
- DexScreener or PumpSwap authority/implementation
- direct Pump decoder implementation or live proof
- memory generation, retrieval, decisions, positions, trades, audits, or PnL
- unrelated tracked/untracked files

## Tests / Checks Run

- `python -m pytest tests/test_secondary_discovery_contract_fixtures.py -q`
- static schema/auth/quota consistency checks in the focused fixture suite
- rank/score/risk/promotion/order stripping checks in the focused fixture suite
- focused Source Governor/Central Scheduler bypass scan
- `git diff --check`
- `git diff --stat`

No broad suite or real-provider test was run, matching the lane boundary and
risk-based minimum verification policy.

## What Remains Locked

Adapters, production registry/secret configuration, provider calls, source
fetching, live proof, schema/database mutation, persistence repair, combined
execution, campaign runtime, V2-9.7D closeout, pilot, memory generation,
retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL,
wallets, private keys, signing, real funds, paid APIs, scoring, ranking,
confidence, weighting, embeddings, vectors, and live execution remain locked.

## Functionality Risks / Setbacks / Efficiency Blockers

- Provider schemas, free quotas, rate limits, and access terms can drift.
- Solana Tracker requires an account/API key despite the free plan.
- Trending/top feeds are curated subsets and not upstream Pump.fun-only lists.
- Solana Tracker `pumpfun` is provider vocabulary pending direct verification.
- Top-performers is launched-today performance, not a general top-token claim.
- Gecko page 1 and one exact active enrichment are intentionally incomplete.
- Provider cache/update guarantees are insufficient for precise event time;
  conservative receipt/update freshness can reduce yield.
- Rank/score/risk fields remain available in raw responses and must be stripped
  before any future merge/gate/selection path.
- Blocking PumpPortal reduces low-latency redundancy but preserves core locks.

## Next Recommended Phase

`V2-9.7D.7B.4A - Direct adapter/continuity implementation`, only when
explicitly requested. Do not begin it from this lane.

## Final Lane Result

`V2_9_7D_7B_3B_SECONDARY_DISCOVERY_CONTRACT_ADOPTION_PASS`

Stop after the PASS-only lane commit. Do not tag and do not begin adapters,
persistence repair, combined execution, live-source proof, V2-9.7D closeout,
or the pilot.