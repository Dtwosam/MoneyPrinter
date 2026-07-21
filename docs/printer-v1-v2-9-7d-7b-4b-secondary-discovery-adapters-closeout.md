# V2-9.7D.7B.4B Secondary Discovery Adapters Closeout

**Status:** PASS
**Lane:** V2-9.7D.7B.4B
**Boundary:** fixture-backed adapter implementation and synthetic proof only
**Date:** 2026-07-21

PASS means the adopted GeckoTerminal trending/active-pool and Solana Tracker
free REST trending/top contracts now have pure fixture-fed adapters with
Source Governor and Central Scheduler ownership. It does not mean that
network transport, API-key materialization, persistence, combined campaign
execution, tracking handoff, live-source proof, or any financial capability
exists.

## Todo / Checklist

- [x] Verify exact starting commit `f8939344b76a1fe4090ec89b6489485712b8e66a`.
- [x] Read AGENTS.md and the active Printer V1 / memory-growth source stack.
- [x] Read 7B.2 design, 7B.3B closeout, adopted contracts, and existing adapters.
- [x] Implement fixture-backed GeckoTerminal trending and active-pool adapters.
- [x] Implement fixture-backed Solana Tracker trending and top adapters.
- [x] Admit adopted request kinds in Source Governor registry.
- [x] Prove identity, stripping, failures, ceilings, isolation, replay, bypass.
- [x] Write this closeout and commit only on PASS.

## Exact Files Changed

- `src/printer_v1/sources/secondary_discovery.py` (new)
- `src/printer_v1/sources/registry.py`
- `tests/fixtures/secondary_discovery_adapters.json` (new)
- `tests/test_v2_9_7d_7b_4b_secondary_discovery_adapters.py` (new)
- `tests/test_phase2_source_registry_governor.py`
- `docs/printer-v1-v2-9-7d-7b-4b-secondary-discovery-adapters-closeout.md` (new)

## Implemented Provider Behavior

### GeckoTerminal

Fixture-only support for:

- `geckoterminal_trending_pool_reference` against
  `/networks/solana/trending_pools` with exact
  `include=base_token,quote_token,dex`, `page=1`, `duration=1h`;
- `geckoterminal_active_pool_reference` against one exact pool with
  `include=base_token,quote_token,dex`;
- exact network, pool, base mint, quote mint, and venue/DEX identity;
- page ceiling of 20 pools and one trending plus one active request per lane;
- receipt-time freshness against the adopted 180-second policy;
- non-zero finite non-negative `transactions.m5.buys + sells` as the only
  active condition;
- malformed, missing, stale, ambiguous, zero-activity, and rate-limited
  responses as explicit failures with no empty-success rewrite.

### Solana Tracker

Fixture-only support for:

- `solana_tracker_pumpfun_trending` against `/tokens/trending/1h`;
- `solana_tracker_pumpfun_top` against `/top-performers/1h`;
- exact mint and available market identity through `token.mint`, `poolId`,
  matching `tokenAddress`, `quoteToken`, and case-sensitive
  `market == "pumpfun"`;
- authentication and free-plan quota validation via secret reference only
  (`api_key_secret_ref`, monthly remaining capacity, 3 rps / 10_000 month);
- body ceiling of 100 rows, one trending plus one top request per lane;
- provider `lastUpdated` plus receipt freshness against 180 seconds;
- malformed, missing, ambiguous, stale/future, rate-limited, auth-blocked,
  and quota-blocked responses as explicit failures.

## Normalization and Authority Boundaries

Normalized observations retain only exact identity and provenance fields:

- provider, channel, network, mint, pool, quote mint, venue, observed_at;
- `pumpfun_origin_status = PROVIDER_LABEL_UNVERIFIED`;
- optional active `activity_interval=m5` and categorical activity count;
- immutable raw payload hash and non-multiplying provenance count.

Neither provider can establish:

- canonical Pump.fun origin, mint creation, bonding curve, or migration;
- safety, authenticity, insider/common-control, or manipulation claims;
- executable liquidity, route, fill, exit, profit, clean-memory fitness,
  retrieval relevance, or any decision/action.

DexScreener and PumpSwap were not expanded, replaced, or refactored. PumpPortal
remains blocked. Pumpdev remains excluded.

## Stripped Non-Authoritative Fields

Before any eligibility or selection use, the adapters discard:

- response position/order and rank;
- provider scores, GT scores, risk scores, rugged/risk lists;
- popularity, trending/performance rank, boost, promotion, sponsorship, and
  verified/Jupiter-verified flags;
- holders, snipers, bundlers, insiders, developer, wallet, and fee analytics;
- price, price-change, market cap, FDV, liquidity, volume, buy/sell totals as
  selection priority;
- names, symbols, images, socials, descriptions, URIs, and marketing labels.

Gecko `transactions.m5` is used only as the fixed active condition, never as a
score or ordering value. Changing discarded fields or response order does not
change the canonical normalized identity set. Exact duplicate
`(provider, channel, mint, pool)` rows remain factual provenance
(`provenance_count`) and never multiply candidate authority keys.

## Failure Isolation

- Provider lanes are independently terminalized as `SUCCEEDED`,
  `SUCCEEDED_EMPTY`, `PARTIAL`, or `FAILED`.
- A GeckoTerminal failure does not erase Solana Tracker observations, and the
  reverse is also true.
- Rate limit / quota, auth, malformed, stale, ambiguous, not-active, and
  transport failures retain request kind, optional status code, and exact code.
- Ordinary retries are zero. Endpoint rotation is absent. Unplanned leftover
  fixture operations fail closed.

## Source Governor and Scheduler Ownership

Every fixture operation must carry:

- adopted `source_name` and request kind admitted by Source Governor;
- `scheduler_job_kind=DISCOVERY_REFRESH`;
- `work_type=DISCOVERY_GECKOTERMINAL_TRENDING_ACTIVE` for Gecko;
- `work_type=DISCOVERY_SOLANA_TRACKER_TRENDING_TOP` for Solana Tracker.

Incorrect source/request kind is `SOURCE_GOVERNOR_BYPASS`. Incorrect Scheduler
identity is `CENTRAL_SCHEDULER_BYPASS`. Validation occurs before transport
consumption. The production registry now admits:

- `geckoterminal_active_pool_reference` on `geckoterminal`;
- source `solana_tracker` with
  `solana_tracker_pumpfun_trending` and `solana_tracker_pumpfun_top`.

There is no network library, socket, HTTP client, WebSocket, database access,
persistence function, command, or runtime entry point in the new adapter
module.

## Enforced Ceilings

| Lane | Governed requests | Response ceiling | Freshness | Retries |
|---|---:|---:|---|---:|
| GeckoTerminal trending | 1 | 20 pools | 180s receipt age | 0 |
| GeckoTerminal active | 1 | 1 exact pool | 180s receipt age | 0 |
| Solana Tracker trending | 1 | 100 tokens | 180s update + receipt | 0 |
| Solana Tracker top | 1 | 100 tokens | 180s update + receipt | 0 |

Per-request governed ceilings are independent. Unused headroom is not converted
into retries, pagination, extra timeframes, or other endpoints.

## Money-Usefulness Contribution

Secondary lists can diversify the future candidate corpus while exact
pool/mint filtering, strict freshness, unverified provider Pump.fun labels,
direct-origin dependency, and aggressive rank/score/order stripping prevent
provider marketing and performance lists from becoming fake quality or
selection priority. The result improves factual intake breadth only. It does
not predict or unlock profit.

## What the Lane Still Does Not Unlock

- real provider or internet calls;
- credential/secret materialization or API-key creation;
- schema or migration changes;
- database mutation or persistence reconciliation;
- combined campaign execution or tracking handoff;
- runtime or command publication;
- live-source proof, V2-9.7D closeout, or pilot;
- retrieval, paper decisions, BUY/SELL/HOLD/WAIT/AVOID/NO_ACTION;
- positions, trade events, paper audits, or PnL;
- wallets, private keys, signing, real funds, live execution;
- paid APIs, scoring, ranking, confidence, weighting, embeddings, or vectors;
- expansion of DexScreener or PumpSwap authority;
- PumpPortal unblocking or Pumpdev inclusion;
- `WINDOW_5M_MICRO_EVENT` as anything other than support-only.

## Focused Proof Results

| Check | Result |
|---|---|
| Valid GeckoTerminal trending response | PASS |
| Valid GeckoTerminal active-pool response | PASS |
| Valid Solana Tracker trending response | PASS |
| Valid Solana Tracker top response | PASS |
| Exact identity normalization | PASS |
| Rank/score/risk/promoted/response-order stripping | PASS |
| Duplicate observations remain provenance only | PASS |
| Provider Pump.fun labels remain unverified | PASS |
| Malformed response handling | PASS |
| Stale response handling | PASS |
| Ambiguous identity handling | PASS |
| Rate-limit handling | PASS |
| Pagination and response ceilings | PASS |
| Independent provider failure isolation | PASS |
| Deterministic replay | PASS |
| Source Governor bypass prevention | PASS |
| Central Scheduler bypass prevention | PASS |
| Auth/quota configuration validation | PASS |
| No network/secret material in adapter surface | PASS |

Focused suite:

- `tests/test_v2_9_7d_7b_4b_secondary_discovery_adapters.py`
- `tests/test_secondary_discovery_contract_fixtures.py`
- `tests/test_phase2_source_registry_governor.py`
- `tests/test_post_rc_geckoterminal_discovery_adapter.py`
- `tests/test_post_rc_pumpswap_confirmation_adapter.py`
- `tests/test_dexscreener_fresh_profiles.py`
- `tests/test_phase3_scheduler_resource_governor.py`

All selected focused tests passed. AST parse of changed Python modules passed.
`git diff --check` passed.

## Remaining Blockers

No blocker remains for this synthetic implementation lane.

Real provider transport, secret provisioning, measured free-quota behavior,
persistent source/work linkage, combined execution ownership, and live-source
proof remain intentionally unproved and belong to later explicitly authorized
lanes (7B.4C+, live-proof, activation review).

## Functionality Risks / Setbacks / Efficiency Blockers

- Provider schemas, free quotas, rate limits, and access terms can drift after
  the 2026-07-19 adoption recheck.
- Solana Tracker still requires an account and secret `x-api-key` despite the
  free plan; missing or unverifiable quota blocks the lane.
- Trending/top feeds are curated subsets and are not upstream Pump.fun-only
  lists; strict `pumpfun` filtering reduces yield by design.
- Provider `pumpfun` / `pump-fun` venue labels remain unverified observations
  until direct finalized Pump origin evidence confirms the exact mint.
- Gecko page-1 and one exact active enrichment are intentionally incomplete
  coverage, not exhaustive market discovery.
- Conservative 180-second freshness can discard still-useful but slightly
  delayed provider rows.
- Zero ordinary retries preserve budgets and auditability but increase
  `FAILED` / `PARTIAL` cycles under transient provider faults.
- Rank/score/risk fields remain present in raw responses and must continue to
  be stripped before any future merge/gate/selection path.
- Fixture transport costs prove accounting logic, not measured provider or
  network costs.

## Stop Boundary

V2-9.7D.7B.4B stops at the pure fixture-backed secondary adapters, registry
admission of adopted request kinds, synthetic fixtures/tests, and this
closeout. Persistence reconciliation, combined execution, live-source proof,
V2-9.7D closeout, and the pilot have not begun.

## Final Lane Result

`V2_9_7D_7B_4B_SECONDARY_DISCOVERY_ADAPTERS_PASS`
