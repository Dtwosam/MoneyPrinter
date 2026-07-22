# Source Governor Evidence Rules

**Status:** ACTIVE — verified 2026-07-12

Defines what evidence each governed source may contribute to a candidate,
what evidence it may NOT contribute, and what the Source Governor must
enforce at the request boundary.

## Governing Principles

1. Every source request must pass Source Governor approval before execution.
2. No source may bypass the Central Scheduler or Source Governor.
3. Evidence claims must match the source that produced them.
4. Provenance must be preserved from transport through normalization to snapshot.
5. A source may not contribute a tier it cannot produce.

## PumpPortal

### Approved request kinds

| Request kind | Allowed | Evidence tier contributed |
|---|---|---|
| `pumpfun_launch_stream` | YES | `OBSERVED_LIVE_LAUNCH` (current); T2 (future, pending schema change) |
| `pumpfun_migration_stream` | YES | None (migration events never contribute token_created_at) |
| Any other kind | NO | Rejected at Governor boundary |

### Evidence contribution rules

| Evidence field | May PumpPortal contribute? | Condition |
|---|---|---|
| `token_created_at` | YES (T2) | Only if `tokenCreatedAt` is present in the raw event AND valid |
| `token_created_at` | NO | From migration events (`pumpfun_migration_stream`) |
| `token_age_seconds` | YES | Only derived from `token_created_at` when T2 conditions are met |
| `live_observed_launch` | YES | When no timestamp field exists in a `pumpfun_launch_stream` event |
| `pair_created_at` | NO | PumpPortal stream does not supply pair creation time |
| `price_usd` | NO | Not in stream schema |
| `liquidity_usd` | APPROXIMATE | Derived from `vSolInBondingCurve * approx_sol_rate` only |
| `volume_*` / `txns_*` | NO | Not in stream schema |
| `price_change_*` | NO | Not in stream schema |

### What PumpPortal may NOT do

- Stamp T2 without explicit `tokenCreatedAt` in the raw event
- Stamp T2 from migration events
- Contribute token_created_at from pair metadata
- Claim evidenced liquidity without the SOL-to-USD approximation caveat
- Bypass the `_PUMPPORTAL_DURATION_SECONDS_CEILING` or `_PUMPPORTAL_MAX_EVENTS_CEILING`
- Open a persistent reconnect loop
- Spawn a background thread or scheduler job

## GeckoTerminal

The adopted provider contract is `geckoterminal-api-contract.md`. The keyless
Public API v2 is active Beta. The 7B.3B trending and exact active-pool contracts
are repaired for fixture-only use. E.26 additionally offline-proves only the
fixed OHLCV/trade kinds for a separately authorized bounded readiness proof.
E.28 aligns their official version header, 10/minute ceiling, six-second pacing
and zero-retry configuration; normal production network use remains blocked.

### Approved request kinds

| Request kind | Current permission | Evidence tier contributed |
|---|---|---|
| `geckoterminal_new_pool_discovery` | `ALLOWED_FIXTURE_ONLY` | Bounded pool/pair discovery page |
| `geckoterminal_trending_pool_reference` | `ALLOWED_FIXTURE_ONLY` | Page-1, 1h provider-ranked Solana pool reference only |
| `geckoterminal_active_pool_reference` | `ALLOWED_FIXTURE_ONLY` | One exact pool with non-zero provider `transactions.m5` |
| `pair_market_snapshot` | `ALLOWED_FIXTURE_ONLY` | Exact-pool market snapshot fallback |
| `geckoterminal_readiness_base_snapshot` | `ALLOWED_SEPARATELY_AUTHORIZED_READINESS_PROOF` | One exact Solana pool/base-mint metadata call for positive `reserve_in_usd`, price, m5 and h1 evidence; one attempt, no retry/rotation; must pass before OHLCV/trades |
| `geckoterminal_ohlcv_15m` | `ALLOWED_SEPARATELY_AUTHORIZED_READINESS_PROOF` | `price_change_15m`, `volume_15m` from one fresh, completed, exact 900-second candle; no retry/rotation |
| `geckoterminal_pool_trades_15m` | `ALLOWED_SEPARATELY_AUTHORIZED_READINESS_PROOF` | `txns_15m` from one unfiltered, well-formed, complete returned set aligned to the same candle; no retry/rotation |
| `geckoterminal_pool_snapshot` | `NOT_IMPLEMENTED` | Proposed exact-pool request name |
| `geckoterminal_pool_ohlcv` | `NOT_IMPLEMENTED` | Proposed parameterized exact-pool OHLCV |
| `geckoterminal_pool_trades` | `NOT_IMPLEMENTED` | Proposed parameterized exact-pool trades |

### Evidence contribution rules

| Evidence field | Condition |
|---|---|
| pool discovery | Preserve page, duration, receipt, exact pool/base/quote identity, and partial coverage |
| trending reference | Provider ranking only; never Printer score, rank, confidence, weight, or signal |
| `price_change_15m` | Exact-pool, exact-token-side completed 15m candle arithmetic; stale/ambiguous candles rejected |
| `volume_15m` | Same exact completed candle, currency and gap policy retained |
| `txns_15m` | Only after unfiltered, well-formed, non-truncated window coverage is proven |
| `pool_created_at` / pair age | T4 pair/pool age only; never token creation time |
| T2/T3 token age | NOT available from GeckoTerminal |

HTTP 200 alone is not completeness. Missing/malformed fields, wrong
network/pool/mint/token side, stale receipt, partial pages, rate limits,
timeouts, provider errors, skipped/ambiguous OHLCV intervals, capped or
filtered trade history, malformed trade records, and incomplete provenance
fail closed. Receipt time is not provider observation time.

GeckoTerminal cannot prove mint creation, wallet authenticity, beneficial
ownership, participant coordination, manipulation intent, token safety,
executable tradeability, fills, exits, or profit. It cannot unlock memory,
retrieval, decisions, positions, trades, audits, or PnL.

## Solana Tracker Free REST

The adopted provider contract is
`solana-tracker-secondary-discovery-contract.md`. Only the free Data API REST
plan and two fixture-only request kinds are permitted. Datastream, RPC, swap,
wallet, PnL, trading, paid, and metered surfaces are outside this contract.

### Approved request kinds

| Request kind | Current permission | Evidence tier contributed |
|---|---|---|
| `solana_tracker_pumpfun_trending` | `ALLOWED_FIXTURE_ONLY` | Membership in `/tokens/trending/1h` after exact provider `pumpfun` pool filtering |
| `solana_tracker_pumpfun_top` | `ALLOWED_FIXTURE_ONLY` | Membership in `/top-performers/1h` after exact provider `pumpfun` pool filtering |

The required `x-api-key` is a secret reference only. It may not be logged,
stored in fixtures, committed, or treated as wallet authority. Free-plan
capacity is 10,000 requests/month and 3 requests/second as rechecked on
2026-07-19. The 7B.2 local ceiling is stricter: one trending request plus one
top request per cycle, 10 seconds each, zero retries.

Only exact token mint and exact pool identity fields survive normalization.
At least one pool must have `market == "pumpfun"` and
`pool.tokenAddress == token.mint`. This is provider classification evidence,
not canonical Pump.fun origin; direct finalized on-chain origin verification
remains mandatory.

Provider list position, response order, score, risk, popularity, performance,
price change, promoted/verified status, holder/wallet analytics, and all
similar fields are discarded before eligibility and selection. Missing,
stale, malformed, ambiguous, unauthenticated, forbidden, rate-limited,
quota-exhausted, non-2xx, or provider-error responses fail closed and cannot
become empty success.

## DexScreener

### Approved request kinds

| Request kind | Allowed | Evidence tier contributed |
|---|---|---|
| `dexscreener_discovery` | YES | Pool/pair discovery; price; liquidity; volume; txns |
| `pair_market_snapshot` | `ALLOWED_SEPARATELY_AUTHORIZED_READINESS_PROOF` | Historical E.26 DexScreener base permission; superseded by the E.30 GeckoTerminal exact-pool base in the current readiness composition |

### Evidence contribution rules

| Evidence field | Condition |
|---|---|
| `pair_created_at` | YES — from DexScreener `pairCreatedAt` field |
| `token_age_seconds` | T4_PAIR_ONLY only (pair age, not token age) |
| `token_created_at` | NO — DexScreener does not provide mint creation time |
| T2/T3 token age | NOT available from DexScreener |

## GoPlus Solana Token Security

The adopted provider contract is
`goplus-solana-token-security-api-contract.md`. The provider is active Beta;
Printer remains partial for broad safety claims. E.28 permits only one
fail-closed exact-mint attempt per candidate inside a separately authorized
bounded readiness proof; broader network reliance remains blocked.

### Approved and proposed request kinds

| Request kind | Current permission | Evidence contribution |
|---|---|---|
| `safety_reference` | `ALLOWED_SEPARATELY_AUTHORIZED_READINESS_PROOF` | One exact-mint defensive response; one attempt, no retry; unknown remains ineligible |
| `solana_token_security_reference` | `NOT_IMPLEMENTED` | Proposed clearer future exact-mint request name |
| Transaction simulation, wallet, approval, signing, or execution | NO | None |

### Evidence contribution rules

| Evidence | Condition |
|---|---|
| authority/token-function danger | Explicit valid provider field for exact mint; missing is unknown |
| holder concentration | Valid top-ten fields with strict units/ranges; account rows do not prove independent wallets |
| DEX/LP context | Exact selected pool ID only; known-locker evidence is not universal lock proof |
| provider malicious-address context | Preserve raw field/provenance; do not convert to identity or intent proof |
| safety result | One composite input only; cannot independently prove a safe token or clean memory |

Unknown/malformed envelopes, code 2 partial data, unsupported codes, missing
mandatory fields, stale receipt, mint mismatch, pool mismatch, and incomplete
provenance fail closed. Provider silence is never safety. GoPlus cannot prove
wallet authenticity, common control, coordination, manipulation intent,
executable tradeability, or profit. It cannot unlock memory, retrieval,
decisions, positions, trades, audits, or PnL.

## Solana RPC

### Approved request kinds

| Request kind | Allowed | Evidence tier contributed |
|---|---|---|
| `mint_creation_time_reference` | YES | `token_created_at` from on-chain block time (T3) |
| `holder_concentration_reference` | `ALLOWED_SEPARATELY_AUTHORIZED_READINESS_PROOF` | Two finalized read-only methods for one exact mint; one attempt, no retry |

### Evidence contribution rules

| Evidence field | Condition |
|---|---|
| `token_created_at` | YES - only from a finalized successful `initializeMint`/`initializeMint2` transaction attributed to the exact requested mint; `getAccountInfo` validates mint state but supplies no age |
| `token_age_seconds` | YES — derived from T3 token_created_at |
| `token_age_evidence_tier` | `"T3"` |

For A3 enrichment, the market-source request/response and the Solana RPC T3
request/response remain separate governed traces. Printer may overlay them only
on an exact mint match. A failed, missing, non-finalized, or mismatched T3 trace
must leave token age unknown and cannot produce A3.


## Helius Free RPC

Helius Free is a fixed authenticated backup for holder concentration only. The
adopted endpoint is `https://mainnet.helius-rpc.com/?api-key=...`; the key is an
operator runtime secret and never evidence. The Free RPC limit is 10 requests
per second and standard RPC methods cost one credit each. Printer is stricter at
30 operations/minute with two-second pacing.

| Request kind | Current permission | Evidence contribution |
|---|---|---|
| `holder_concentration_reference` | `ALLOWED_SEPARATELY_AUTHORIZED_READINESS_PROOF` | Exact-mint `getTokenLargestAccounts` plus `getTokenSupply`, both finalized |

One governed Helius holder request charges two underlying transport operations.
It runs only after an eligible transient public-RPC failure, exactly once, on
the fixed mainnet host. Missing auth, 4xx, malformed/RPC errors, target mismatch,
stale/conflicting evidence, quota/rate failure or missing fields fail closed.
There is no retry, endpoint rotation, second backup or paid fallback.

## Jupiter Route and Quote

The adopted provider contract is `jupiter-route-quote-api-contract.md`. Metis
V1 is `SUPERSEDED`, and Printer's network adapter is
`PARTIAL_WITH_BLOCKER`. Until a later repair and proof passes, the existing
request kind is fixture-only.

### Approved request kinds

| Request kind | Current permission | Evidence contribution |
|---|---|---|
| `paper_quote_realism` | `ALLOWED_FIXTURE_ONLY` | Paper entry/exit route and quote context only |
| Transaction, swap, execute, wallet, or signing request | NO | None |

### Evidence contribution rules

| Evidence field | Condition |
|---|---|
| route available | Structurally valid route for exact mint pair, direction, amount, mode, and response |
| route unavailable | Explicit parsed provider no-route result; never generic HTTP 400 |
| amount, threshold, impact, route, fees | Later repair/proof; exact reconciliation and finite parsing required |
| quote freshness | Later conservative rule; receipt or registry duration alone is insufficient |
| entry/exit realism | Context only; not a fill, transaction, landed execution, or realized profit |

Missing auth, rate limiting, unknown HTTP errors, malformed JSON, schema or
identity mismatch, and missing quantitative fields fail closed. Missing or
malformed price impact must never become zero. Jupiter cannot contribute token
safety, wallet-level flow authenticity, clean eligibility by itself, retrieval,
decisions, positions, trades, audits, or PnL.

## Cross-Cycle A4 Evidence

`A4 / FAILED_PUMP` is derived only from two distinct governed discovery
responses for the exact same non-null Solana mint and pair. Both the prior and
current response must be `COMPLETE / CLEAN_DATA`, retain request and response
IDs, and have valid observation times proving that the current evidence is
newer. The prior persisted discovery row must classify as A1, A2, or A3. The
current row must satisfy the existing categorical failed-pump collapse rule.

Missing, stale, dirty, failed, same-response, identity-mismatched, or malformed
evidence fails closed. Source payloads cannot self-assert internal `a4_*`
evidence fields. A4 remains discovery/selection metadata only and cannot create
memory, retrieval, paper decisions, positions, trades, audits, or PnL.

## Classifier-Derived Category Coverage Diagnostics

Group A quota membership is derived by Printer's categorical classifier after
governed evidence enrichment. A source payload or caller-supplied bucket marker
cannot assert A2, A3, or A4. A3 requires accepted token-age provenance and the
existing market conditions. A4 requires the exact prior/current governed
evidence contract above.

The historical Group A cap/share, mandatory A2/A3/A4, Group B, decay, D1, and
WATCH_ONLY quota measurements are retained as categorical diagnostics. They no
longer block active handoff. Active selection uniformly samples a bounded,
seeded pool only after source quality, exact identity, activity, liquidity,
deduplication, STNP, cooldown, and rotation gates pass. WATCH_ONLY, D1, and
inactive evidence remains audit-only and must not enter active tracking or
create scheduler work. Classifications remain provenance-backed observations;
they are never source-asserted selection preferences.

## Governor Enforcement Responsibilities

The Source Governor must:

1. Reject any request kind not in the source's `allowed_request_kinds` set.
2. Record every approved request as a `printer_source_requests` row before transport.
3. Record every successful response as a `printer_source_responses` row.
4. Record every transport failure as a `printer_source_failures` row.
5. Not approve the same source + request_kind combination more times than the
   operator budget allows in the current run.

The Source Governor must NOT:

- Grant approval to circumvent the evidence contribution rules above.
- Allow a source to claim evidence it cannot produce.
- Allow evidence from one source to overwrite governed evidence from another
  source with equal or higher provenance confidence.

## Staged Derivation Guard

`PROVIDER_CANDLE_DERIVED` evidence (`price_change_15m_source_kind`) may not
be overwritten by subsequent requests. The `_protected_source_kinds` frozenset
in `staged_derivation.py` enforces this. Any change to this guard requires an
explicit operator-approved design lane.

## Evidence Isolation Rule

Evidence stamped by one source must never be attributed to another. The
`source_name` field on a candidate identifies the discovery source. Evidence
fields with `_source_kind` or `_provenance` suffixes identify their specific
contributing source. These must survive normalization, selection, and snapshot
persistence unchanged.
