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

### Approved request kinds

| Request kind | Allowed | Evidence tier contributed |
|---|---|---|
| `geckoterminal_new_pool_discovery` | YES | Pool/pair discovery metadata |
| `geckoterminal_trending_pool_reference` | YES | Pool/pair discovery metadata |
| `geckoterminal_ohlcv_15m` | YES | `price_change_15m`, `volume_15m` (PROVIDER_CANDLE_DERIVED) |
| `geckoterminal_pool_trades_15m` | YES | `txns_15m` (PROVIDER_TRADES_WINDOW) |

### Evidence contribution rules

| Evidence field | Condition |
|---|---|
| `price_change_15m` | Only from completed 15m candle arithmetic; stale candles rejected |
| `volume_15m` | Only from same completed candle |
| `txns_15m` | Only when `oldest_reaches_window` proves complete coverage |
| `token_created_at` | CONDITIONAL — from pool metadata `pool_created_at` → T4 only |
| T2/T3 token age | NOT available from GeckoTerminal |

## DexScreener

### Approved request kinds

| Request kind | Allowed | Evidence tier contributed |
|---|---|---|
| `dexscreener_discovery` | YES | Pool/pair discovery; price; liquidity; volume; txns |

### Evidence contribution rules

| Evidence field | Condition |
|---|---|
| `pair_created_at` | YES — from DexScreener `pairCreatedAt` field |
| `token_age_seconds` | T4_PAIR_ONLY only (pair age, not token age) |
| `token_created_at` | NO — DexScreener does not provide mint creation time |
| T2/T3 token age | NOT available from DexScreener |

## Solana RPC

### Approved request kinds

| Request kind | Allowed | Evidence tier contributed |
|---|---|---|
| `mint_creation_time_reference` | YES | `token_created_at` from on-chain block time (T3) |

### Evidence contribution rules

| Evidence field | Condition |
|---|---|
| `token_created_at` | YES - only from a finalized successful `initializeMint`/`initializeMint2` transaction attributed to the exact requested mint; `getAccountInfo` validates mint state but supplies no age |
| `token_age_seconds` | YES — derived from T3 token_created_at |
| `token_age_evidence_tier` | `"T3"` |

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
