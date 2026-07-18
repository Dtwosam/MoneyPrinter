# Printer V1 V2-9.7D.1C GeckoTerminal Contract Audit and Adoption Closeout

## Verdict

`V2_9_7D_1C_GECKOTERMINAL_CONTRACT_AUDIT_ADOPTION_PASS`

PASS means the current official GeckoTerminal contract was audited and adopted
with supported evidence, unknowns, and implementation blockers explicit. It
does not mean provider implementation, network reliance, runtime, or any later
V2-9.7D capability is ready.

## Preflight and Scope

- Starting HEAD: `db50bb6c586d7932c5b1bfda02890c5ffee00032`
- Starting tracked tree: clean
- Existing unrelated untracked artifacts: observed and untouched
- Work performed: documentation, static repository inspection, and official
  documentation research only
- API calls, live probes, source fetching, tests, DB commands, runtime: none
- Code, tests, migrations, schemas, databases, and roadmaps: unchanged

## Executive Finding

The official contract is sufficiently documented for conservative adoption.
GeckoTerminal publishes an active Beta, keyless Public API v2 with explicit
Solana support, pool-list and exact-pool endpoints, OHLCV tuple semantics, and
a last-300/past-24h pool-trades boundary.

Printer already has governed, fixture-first discovery, exact-pool, OHLCV, and
trade paths with useful identity/provenance checks. Network reliance is not
ready. The implementation hard-codes page 1, uses a version header different
from current Swagger, retains a 30/min registry budget while current Swagger
says approximately 10/min, assumes OHLCV/trade ordering, and can call filtered
or malformed trade history complete.

Those are bounded later implementation blockers. The adopted permission is
`ALLOWED_FIXTURE_ONLY`, so no source or downstream capability was activated.

## Adoption Gate

| Requirement | Result |
|---|---|
| Official root/version/auth and Solana support identified | PASS |
| Current free limit handled conservatively | PASS - adopt 10/min; older 30/min statement retained as conflict |
| New/trending/exact-pool/OHLCV/trade contracts recorded | PASS |
| Pagination, freshness, candle, and coverage semantics bounded | PASS |
| Supported and unsupported evidence separated | PASS |
| Current code, storage, discovery, and focused tests reconciled | PASS |
| Unknown facts remain `UNKNOWN_REQUIRES_RESEARCH` | PASS |
| Governor/Scheduler and downstream locks preserved | PASS |
| No live use or implementation activation | PASS |

## Official Sources

Accessed `2026-07-18`:

- `https://api.geckoterminal.com/docs/index.html`
- `https://apiguide.geckoterminal.com/`
- `https://apiguide.geckoterminal.com/getting-started`
- `https://apiguide.geckoterminal.com/authentication`
- `https://apiguide.geckoterminal.com/faq`
- `https://docs.coingecko.com/docs/keyless-public-api`
- `https://docs.coingecko.com/reference/latest-pools-network`
- `https://docs.coingecko.com/reference/trending-pools-network`
- `https://docs.coingecko.com/reference/pool-address`
- `https://docs.coingecko.com/reference/pool-ohlcv-contract-address`
- `https://docs.coingecko.com/reference/pool-trades-contract-address`

The official GeckoTerminal Swagger and API guide are primary. Official
CoinGecko on-chain pages define the same GeckoTerminal dataset's detailed field
and parameter semantics. Only the keyless GeckoTerminal v2 root is adopted.
No page instruction, example address, credential, or payload was executed.

## Findings

- Public v2 root is `https://api.geckoterminal.com/api/v2`; it is keyless,
  free, and Beta.
- Current Swagger documents `version=20230203`, one-minute caching, and an
  approximate 10-calls/minute public limit.
- The older official FAQ says 30 calls/minute. The stricter current value is
  adopted and the discrepancy must be rechecked before implementation.
- New pools are pools created within 48 hours, up to 20/page. Page 1 alone is
  partial discovery coverage.
- Trending is provider-ranked reference involving engagement, activity, and
  credibility factors. It cannot become Printer scoring/ranking or a signal.
- `pool_created_at` is pool/pair age only, never token creation time.
- Pool attributes can support exact-linked price, reserve/liquidity, volume,
  transaction, and price-change observations; nullable market cap and FDV must
  remain distinct.
- OHLCV rows are `[start, open, high, low, close, volume]`; empty intervals are
  skipped by default, and no explicit completed-candle flag is documented.
- Pool trades expose at most the last 300 trades in 24 hours. A volume filter
  changes the population and cannot support an unqualified total count.

## Current Implementation Gaps

| Gap | Effect | Later minimum repair |
|---|---|---|
| Header uses `version=20230302` | Contract/version drift is hidden | Pin current official version and fixtures |
| Registry permits 30/min | Can exceed current approximate public limit | Adopt <=10/min and tighter Scheduler budget |
| New/trending URLs hard-code page 1 | Discovery coverage is underreported | Bounded page plan and partial-coverage reporting |
| Trending duration not explicit | Provider default is implicit | Preserve explicit duration/page provenance |
| Exact-pool normalizer accepts multiple fixture aliases | Official schema drift can be obscured | Strict official JSON:API mapping |
| Local receipt/captured time used for freshness | Does not prove provider observation time | Preserve one-minute cache uncertainty and local age |
| OHLCV list assumed descending | Wrong row could be selected | Fixture-pin order and interval boundaries |
| Only two OHLCV rows requested | Gaps can leave no closed row | Bounded gap-aware request/selection contract |
| Trade URL filters `volume_in_usd > 0` | Some trades can be excluded | Remove filter for totals or label as filtered |
| Malformed trade records are skipped | `<300` can be falsely called complete | Any malformed record blocks complete coverage |
| `<300` implies complete | Assumes response/order/index completeness | Prove returned-set and window coverage |
| Trade records counted without stronger semantic pin | Record count may not equal intended transaction metric | Define trade-record vs unique-transaction label |

## Proposed Governed Requests

Existing kinds remain compatibility names and fixture-only:

- `geckoterminal_new_pool_discovery`
- `geckoterminal_trending_pool_reference`
- `pair_market_snapshot`
- `geckoterminal_ohlcv_15m`
- `geckoterminal_pool_trades_15m`

Proposed, not implemented:

- `geckoterminal_pool_snapshot`
- `geckoterminal_pool_ohlcv`
- `geckoterminal_pool_trades`

No request kind was added to code or activated. Future requests must be
Source-Governed, Central-Scheduler-led, bounded, exact-linked, and free-only.

## Unsupported Proof Boundaries

GeckoTerminal cannot prove token creation time, mint initialization, authority
safety, holder authenticity, beneficial ownership, independent participants,
coordination, wash activity, manipulation intent, executable routes, slippage,
latency, fills, exits, or profit.

Provider names, symbols, trending order, sentiment, community reports, FDV,
market data, reserve/liquidity, transaction addresses, buyer/seller counts,
OHLCV, and trades must not be stretched beyond their exact descriptive or
pool-observation meanings.

## Unresolved Dependencies

- The public rate-limit conflict needs re-verification immediately before
  implementation; the current conservative ceiling remains 10/min.
- Exact keyless v2 OHLCV and trade response ordering is
  `UNKNOWN_REQUIRES_RESEARCH`.
- Exact parity of every CoinGecko on-chain field/nullability on keyless v2 must
  be fixture-pinned.
- Provider observation time and endpoint-specific cache age are not present in
  each response.
- Complete provider indexing and chain-latency guarantees are unknown.
- Wallet-level flow authenticity remains partial.

These do not block audit/adoption because every affected path remains
fixture-only and fail-closed. They do block implementation and network
activation readiness.

## Money-Usefulness Contribution

This lane reduces fake paper-profit risk by distinguishing exact pool-market
observations from mint age, participant authenticity, execution, and profit.
It preserves useful new/trending discovery, pair age, price, liquidity, volume,
transaction, and completed-candle evidence for later governed use while
preventing partial pages, filtered trades, in-progress candles, or provider
rankings from becoming false clean-memory or money claims.

## What This Lane Improves

- Establishes a dated official GeckoTerminal Public API v2 contract.
- Corrects the free-limit authority boundary conservatively.
- Defines exact pair/mint, page, timeframe, token-side, and coverage provenance.
- Separates completed-candle logic from undocumented provider assumptions.
- Exposes trade-count undercount and false-completeness risks before activation.
- Records proposed governed request names without implementation.

## What Remains Locked

- GeckoTerminal network requests and provider activation
- public-RPC consolidation, provider implementation, and later V2-9.7D work
- runtime, campaigns, memory generation, and operational commands
- clean-memory policy changes and operational memory growth
- retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits, and PnL
- wallets, keys, signing, funds, paid dependencies, and live execution
- scoring, ranking, confidence, weighting, embeddings, and vectors
- Source Governor or Central Scheduler bypass

## Functionality Risks / Setbacks / Efficiency Blockers

- Public API v2 is Beta and can change.
- Official rate-limit pages disagree; the stricter current Swagger value is
  necessary but reduces request capacity.
- One-minute caching and absent per-response observation time limit freshness.
- Page limits make exhaustive discovery expensive under a small free budget.
- Skipped OHLCV intervals complicate sparse-pool continuity.
- Last-300 trade caps can truncate active 15m windows.
- The current positive-volume filter and malformed-row skip can undercount.
- Pool transaction addresses do not solve wallet-level authenticity.

## Verification

| Check | Result |
|---|---|
| Exact starting HEAD and clean tracked tree | PASS |
| Static adapter, normalization, discovery, OHLCV/trade, storage, and focused-test inspection | PASS |
| Official-source reconciliation and access-date recording | PASS |
| Supported/unsupported evidence boundary scan | PASS |
| Capability-unlock and unsafe-proof wording scan | PASS |
| Approved documentation-only scope | PASS |
| `git diff --check` | PASS |

No tests, API calls, network probes, source requests, runtime, or database
commands were run; none belong to this lane.

## Final Lane Result

`V2_9_7D_1C_GECKOTERMINAL_CONTRACT_AUDIT_ADOPTION_PASS`

Stop after the lane-specific documentation commit. Do not begin public-RPC
consolidation, provider implementation, or later V2-9.7D work.
