# DexScreener API Contract

**Status:** VERIFIED 2026-07-12
**Authority:** A4 (DexScreener official API docs — `https://docs.dexscreener.com/api/reference`)
plus A6 (Printer implementation `src/printer_v1/sources/dexscreener.py` + governed live probe evidence)

This module documents the DexScreener endpoints Printer V1 uses for Solana
memecoin discovery, their response schema, and the categorical filters applied
before a pair becomes a discovery candidate. It is subordinate to the active
Printer stack (see `README.md`).

## Access

| Property | Value |
|---|---|
| Base URL | `https://api.dexscreener.com` |
| Authentication | None (keyless, no API key, no account) |
| Cost | Free |
| `access_policy` | `KEYLESS_PUBLIC` |
| `v1_permission` | `ALLOWED_GOVERNED` |
| Transport | HTTPS GET, JSON |
| Headers | `User-Agent`, `Accept: application/json` (see `DEXSCREENER_PUBLIC_API_HEADERS`) |

## Endpoints Used By Printer

| Request kind | Endpoint | Printer builder |
|---|---|---|
| `token_discovery` | `GET /latest/dex/search?q={query}` | `build_dexscreener_smoke_transport` |
| pair snapshot | `GET /latest/dex/pairs/solana/{pairAddress}` | `build_dexscreener_pair_snapshot_transport` |
| token lookup | `GET /latest/dex/tokens/{tokenMint}` | `build_dexscreener_token_transport` |

Only `token_discovery` is in the discovery request-plan catalog today
(`_SOURCE_REQUEST_PLAN_CATALOG["dexscreener"]`). The pair/token endpoints are
used for governed one-shot smoke checks and targeted snapshots.

## Response Schema — `/latest/dex/search`

Returns `{ "schemaVersion": ..., "pairs": [ ... ] }`. Each pair (fields Printer
normalizes in `normalize_dexscreener_fixture_result`):

| Field | Type | Notes |
|---|---|---|
| `chainId` | string | Printer keeps only `"solana"` |
| `pairAddress` | string | pair identity |
| `baseToken.address` | string | the discovery token mint (memecoin side) |
| `baseToken.symbol` / `.name` | string | display only |
| `priceUsd` | string | nullable |
| `liquidity.usd` | number | nullable |
| `volume.m5` / `.h1` / `.h24` | number | activity windows |
| `txns.m5` / `.h1` / `.h24` | `{buys, sells}` | Printer sums to a count and keeps buys/sells |
| `priceChange.m5` / `.h1` / `.h24` | number | percent |
| `fdv`, `marketCap` | number | nullable |
| `pairCreatedAt` | number (ms epoch) | **pair** creation, not token creation → T4_PAIR_ONLY only |

## Critical Findings (A6 live probe, 2026-07-12)

A governed live probe of `/latest/dex/search` was run to confirm productivity
behavior. Findings:

1. **The search endpoint is a text-match query, not a fresh-pair feed.**
   `q=SOL` returns billion-USD-liquidity major tokens whose name/symbol contains
   "SOL"; `q=pump` returns the PumpFun protocol token (`pumpCmXq...Dfn`) across
   many pools. Neither query is ordered by recency or surfaces newly-launched
   memecoins. This is the dominant reason DexScreener contributes few *fresh*
   assets. A recency/newness discovery vector is **not** available on the free
   keyless search endpoint — see UNKNOWN_REQUIRES_RESEARCH.

2. **Cross-chain results.** `search` returns pairs across all chains
   (probe: ~13 of 30 rows non-Solana). Printer excludes non-Solana pairs at the
   normalization boundary (Stage 2 repair) with reason `non_solana_pair`.

3. **Heavy per-mint pool duplication.** A popular token appears as many pool
   rows. Within-response dedup (`filter_within_response_duplicates`) keeps the
   first occurrence per mint/pair; DexScreener orders search results by
   liquidity, so the retained pool is the highest-liquidity pool.

4. **Infrastructure quote-mints can appear as `baseToken`.** For a WSOL/USDC
   pool the base side may be an infrastructure mint. Printer now excludes
   base mints in `{WSOL, USDC, USDT}` with reason `infrastructure_quote_mint`,
   mirroring `geckoterminal._SOLANA_NATIVE_QUOTE_MINTS`. Source of truth:
   `solana-mint-addresses.md`.

## Categorical Discovery Filters (Printer, Stage 2 repair)

Applied in `normalize_dexscreener_fixture_result` before any candidate is
emitted. All are categorical (set membership / string equality); no scores,
ranks, or weighted logic. Every excluded pair is recorded in
`normalized_payload["excluded_pairs"]` with an explicit reason — never silently
dropped.

| Exclusion reason | Rule |
|---|---|
| `non_solana_pair` | `chain != "solana"` |
| `missing_pair_or_mint_identity` | `pair_address` or `token_mint` absent |
| `infrastructure_quote_mint` | `token_mint in {WSOL, USDC, USDT}` |

If no pair survives, the result is `FAILED /
dexscreener_missing_critical_fixture_fields`.

## Evidence Contribution

| Field | May DexScreener contribute? |
|---|---|
| Discovery pair/mint identity, price, liquidity, volume, txns, priceChange | YES |
| `pair_created_at` | YES (from `pairCreatedAt`) |
| `token_age_seconds` | T4_PAIR_ONLY only (pair age, never token age) |
| `token_created_at` | NO — DexScreener does not provide mint creation time |
| T2 / T3 token age | NO |

See `token-age-evidence-tier-registry.md` and `source-governor-evidence-rules.md`.

## V1 Compliance

| Requirement | Status |
|---|---|
| No API key / account | PASS (keyless) |
| No paid dependency | PASS (free) |
| No wallet / private keys | PASS |
| Solana-only | PASS (non-Solana excluded at normalization) |
| Memecoin-only | PASS (infrastructure mints excluded) |
| No scoring / ranking | PASS (categorical filters only) |

## UNKNOWN_REQUIRES_RESEARCH

| Item | Status |
|---|---|
| Whether a keyless recency/newness Solana discovery endpoint exists (e.g. token-boosts / token-profiles as a fresh-memecoin vector) | UNKNOWN_REQUIRES_RESEARCH |
| DexScreener documented rate limits for `/latest/dex/search` (docs cite ~300 req/min for some endpoints; not re-verified here) | UNKNOWN_REQUIRES_RESEARCH |
| Whether `search` ordering (by liquidity) is a documented guarantee vs observed behavior | UNKNOWN_REQUIRES_RESEARCH |

## Change History

| Date | Change | Author |
|---|---|---|
| 2026-07-12 | Authored from A4 docs + A6 implementation and governed live probe; Stage 2 categorical exclusion filters documented | Claude Opus 4.8 / DexScreener productivity repair |
