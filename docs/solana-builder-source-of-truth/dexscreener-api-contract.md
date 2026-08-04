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

| Request kind | Endpoint(s) | Printer builder |
|---|---|---|
| `token_discovery` | `GET /latest/dex/search?q={query}` | `build_dexscreener_smoke_transport` |
| `dexscreener_fresh_profiles` | `GET /token-profiles/latest/v1` then `GET /tokens/v1/solana/{addrs}` | `build_dexscreener_fresh_profiles_transport` |
| pair snapshot | `GET /latest/dex/pairs/solana/{pairAddress}` | `build_dexscreener_pair_snapshot_transport` |
| token lookup | `GET /latest/dex/tokens/{tokenMint}` | `build_dexscreener_token_transport` |

`token_discovery` and `dexscreener_fresh_profiles` are both READY in the
discovery request-plan catalog. The pair/token endpoints are used for governed
one-shot smoke checks and targeted snapshots.

## Fresh-listing discovery vector (`dexscreener_fresh_profiles`)

The keyless text-match search endpoint is a weak fresh-memecoin vector (returns
the popular PumpFun protocol token and major tokens; see findings below). The
fresh-profiles vector fixes this with two keyless GETs inside one governed
request:

1. `GET /token-profiles/latest/v1` — recently profiled tokens (`chainId`,
   `tokenAddress`, `updatedAt`); documented 60 req/min; recency-ordered.
   Filter to `chainId == "solana"`, de-duplicate, cap at 30 mints.
2. `GET /tokens/v1/solana/{comma-joined-mints}` — batch pair data (same pair
   shape as search: `baseToken.address`, `pairAddress`, `liquidity`, `volume`,
   `txns`, `priceChange`, `pairCreatedAt`, `dexId`).

Return shape: `{"pairs": [...]}`, consumed by
`normalize_dexscreener_fixture_result` (Solana-only + infrastructure-mint
exclusions still apply). Recency-of-listing is a categorical intake fact, not a
score; no `token-boosts` amount, ordering position, or any numeric is used as a
ranking. **Live proof (2026-07-12, isolated DB):** `COMPLETE`,
`DEXSCREENER_LATEST_PROFILES` channel, 14 fresh Solana candidates found, 5
distinct fresh memecoins accepted + persisted (TRACK_FAST/TRACK_NORMAL mix),
1 request / 1 response / 0 failures — vs the search vector's single
popular-token accept.

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

If the source returns a valid empty `pairs: []` list, Printer records a
`PARTIAL / ACCEPTABLE_PARTIAL_DATA` no-match result with no source failure.
Only a missing or non-list `pairs` field is malformed and fails as
`dexscreener_malformed_fixture`. If pairs are present but none survive the
categorical filters, the existing missing-critical-data outcome remains
applicable.

## Evidence Contribution

| Field | May DexScreener contribute? |
|---|---|
| Discovery pair/mint identity, price, liquidity, volume, txns, priceChange | YES |
| `pair_created_at` | YES (from `pairCreatedAt`) |
| `token_age_seconds` | T4_PAIR_ONLY only (pair age, never token age) |
| `price_change_1h` | Market-side A3 context when present; never supplies token age |

DexScreener market evidence may be joined to separately governed T1/T2/T3
token-age evidence only by exact Solana mint. The join must retain both source
response IDs and must not reinterpret pair, pool, discovery, or receipt time as
token creation time.
| `token_created_at` | NO — DexScreener does not provide mint creation time |
| T2 / T3 token age | NO |

See `token-age-evidence-tier-registry.md` and `source-governor-evidence-rules.md`.

## E.26 readiness-snapshot role

For a separately authorized bounded readiness proof, one governed exact-pair
DexScreener request is the primary/base snapshot operation for each selected
mint/pair. It may contribute current price, positive USD liquidity, 5m
price-change/volume/transactions, and wider-window activity only when each
value is present, well formed, fresh, and exact-linked to the requested Solana
mint and pair.

DexScreener does not expose an exact 15m bucket in the adopted pair schema.
Its `m5`, `h1`, and `h24` buckets must not be relabeled or arithmetically
interpolated as 15m evidence. Nullable or absent `liquidity.usd` remains
missing evidence and fails readiness closed; a supplemental source may not
fill or replace that base-liquidity requirement. Missing values may become
zero only through the pre-existing E.19 verified-inactivity contract, never
from source absence or pair youth.

The E.26 path performs no retry, endpoint rotation, reconnect, or fallback for
this primary request. One attempted transport is one charged operation.

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
| Whether a keyless recency/newness Solana discovery endpoint exists | RESOLVED — `/token-profiles/latest/v1` (recency-ordered, keyless) enriched via `/tokens/v1/solana/{addrs}`; implemented as `dexscreener_fresh_profiles` and proven live |
| DexScreener documented rate limits for `/latest/dex/search` (docs cite ~300 req/min for some endpoints; not re-verified here) | UNKNOWN_REQUIRES_RESEARCH |
| Whether `search` ordering (by liquidity) is a documented guarantee vs observed behavior | UNKNOWN_REQUIRES_RESEARCH |

## Change History

| Date | Change | Author |
|---|---|---|
| 2026-07-12 | Authored from A4 docs + A6 implementation and governed live probe; Stage 2 categorical exclusion filters documented | Claude Opus 4.8 / DexScreener productivity repair |

## E.30 readiness supersession

E.29 queried two exact, identity-matched Solana pairs approximately 183 and
171 seconds after their provider `pairCreatedAt` values. Both responses were
`COMPLETE` / `CLEAN_DATA`, carried positive price and m5/h1/h24 activity, and
returned nullable `liquidity.usd` as missing. Exact identity, malformed
transport and normalizer field loss are therefore rejected as causes. Because
raw provider bodies were not retained and the official contract makes the
liquidity object nullable, the evidence cannot distinguish provider omission
from provider-emitted null or prove a deterministic indexing-maturity cause.
Pair youth is a supported inference, not an admission threshold.

The current E.30 readiness composition no longer assigns base ownership to
DexScreener. It uses GeckoTerminal exact-pool metadata as the single base
operation so the fixed two-candidate snapshot reservation remains six rather
than growing to eight. DexScreener remains available for its other governed
roles and its historical E.26 permission remains auditable; it is not combined
with, used to overwrite, or used as an automatic fallback for the E.30 base.

## 2026-08-04 permanent discovery availability pin

The official DexScreener API reference was refreshed on 2026-08-04 for the
permanent mint-first discovery lane. The adopted current-market endpoint is:

`GET https://api.dexscreener.com/tokens/v1/solana/{comma-separated-mints}`

The official maximum remains **30 token addresses per request**. Printer pins
this boundary as `DEXSCREENER_TOKENS_V1_2026_08_04`. The active Eligible Token
Supply owner may issue one Source-Governed `candidate_market_batch` request for
1-30 distinct due mints before any targeted exact-pair request. Input identities
are deterministically deduplicated and sorted only to construct a stable request;
provider order, pair order and every market magnitude are forbidden as pool or
selection authority.

A successful HTTP 200 batch containing no pairs is categorical market absence,
not source unavailability. Every returned exact pool identity is preserved.
Different pools remain pending exact reconciliation and are never selected by
first row, liquidity, activity, provider popularity or provider order. There is
one transport attempt and no adapter retry.
