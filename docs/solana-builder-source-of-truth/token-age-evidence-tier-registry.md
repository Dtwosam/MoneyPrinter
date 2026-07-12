# Token Age Evidence Tier Registry

**Status:** ACTIVE — verified 2026-07-12

This registry defines all valid `token_age_evidence_tier` values used by
Printer V1, their sources, and their data constraints. No tier may be stamped
without meeting all listed requirements.

## Tier Definitions

### T1 — Authoritative Creation Timestamp (Reserved)

| Property | Value |
|---|---|
| Stamp condition | Authoritative on-chain creation confirmation with sub-second precision |
| Required field | `token_created_at` set from authoritative source |
| Sources | Not yet implemented in V1 |
| Status | RESERVED — no V1 source currently qualifies |
| Notes | Defined for future use; must not be assigned today |

### T2 — Provider-Supplied Creation Timestamp

| Property | Value |
|---|---|
| Stamp condition | `source_name == "pumpportal"` AND `request_kind == "pumpfun_launch_stream"` AND `token_created_at` is not None AND `token_age_seconds` is derivable |
| Required field | `token_created_at` from explicit provider field (`tokenCreatedAt`, `createdTimestamp`, or `timestamp`) |
| Staleness gate | Rejected if older than 3600 seconds at observation time |
| Future gate | Rejected if timestamp is in the future relative to observation |
| Sources | PumpPortal `subscribeNewToken` **when `tokenCreatedAt` is present** |
| Current PumpPortal status | **BLOCKED** — `tokenCreatedAt` is absent from all observed events (verified 2026-07-12) |
| Notes | T2 is architecturally defined and implemented; the blocker is the data source, not the code |

### T3 — Governed RPC Mint-Creation Evidence

| Property | Value |
|---|---|
| Stamp condition | `source_name == "solana_rpc"` AND `request_kind == "mint_creation_time_reference"` AND `token_created_at` is not None AND `token_age_seconds` is derivable |
| Required field | `token_created_at` from on-chain mint account block time |
| Sources | Solana public RPC `getAccountInfo` on mint address → block time lookup |
| Status | IMPLEMENTED — see V2-2AK |
| Notes | Governed request per token; adds latency but provides verified on-chain time |

### T4_PAIR_ONLY — Pool/Pair Age Only

| Property | Value |
|---|---|
| Stamp condition | `pair_created_at` is known but `token_created_at` is not |
| Required field | `pair_created_at` or `pair_age_seconds` |
| Sources | DexScreener, GeckoTerminal pool metadata |
| Status | IMPLEMENTED |
| Notes | Pair age is NOT token age. T4 must never be promoted to T1/T2/T3 by inference |

### T5_UNKNOWN — No Age Evidence

| Property | Value |
|---|---|
| Stamp condition | Default when no other tier applies |
| Required field | None |
| Sources | All sources |
| Status | IMPLEMENTED (default) |
| Notes | token_age_seconds is None; token_created_at is None |

### OBSERVED_LIVE_LAUNCH — Mint-Bearing Launch Event Without Timestamp

| Property | Value |
|---|---|
| Stamp condition | `source_name == "pumpportal"` AND `request_kind == "pumpfun_launch_stream"` AND no timestamp field present in event (`tokenCreatedAt`, `createdTimestamp`, `timestamp` all absent) AND `live_observed_launch == True` |
| Required field | `live_observed_launch = True` in normalized event |
| Sources | PumpPortal `subscribeNewToken` (current production behavior as of 2026-07-12) |
| Status | ACTIVE — this is what real PumpPortal events produce |
| Notes | Token is known to be launching NOW. No historical creation time available. token_created_at and token_age_seconds are None. |

## Field Contract

For any candidate that enters `normalize_candidate("pumpportal", ...)`:

| Output field | T2 | OBSERVED_LIVE_LAUNCH | T3 | T4_PAIR_ONLY | T5_UNKNOWN |
|---|---|---|---|---|---|
| `token_age_evidence_tier` | `"T2"` | `"OBSERVED_LIVE_LAUNCH"` | `"T3"` | `None` | `None` |
| `token_created_at` | non-None | `None` | non-None | `None` | `None` |
| `token_age_seconds` | non-None | `None` | non-None | `None` | `None` |
| `live_observed_launch` | `False` | `True` | `False` | `False` | `False` |
| `pair_age_context_label` | set normally | set normally | set normally | set normally | `UNKNOWN_TOKEN_AGE` |

## Stamping Rules

1. A tier must never be stamped without the evidence that defines it.
2. T2 requires explicit provider-supplied `tokenCreatedAt` (or fallback) in the raw event. Absence means no T2.
3. `pair_created_at` / `pair_age_seconds` must never promote to token_age_seconds or to T2/T3.
4. T3 requires a separate governed Solana RPC call; it cannot be inferred from discovery events.
5. `live_observed_launch` and T2 are mutually exclusive for the same event.
6. Future timestamps (event time > observation time) are rejected for all tiers.
7. Stale timestamps (age > 3600s at observation) are rejected for T2.

## Current PumpPortal Stream Evidence Tier

As of 2026-07-12, real `subscribeNewToken` events produce:

```
token_age_evidence_tier = OBSERVED_LIVE_LAUNCH
token_created_at = None
token_age_seconds = None
live_observed_launch = True
```

T2 from PumpPortal requires either:
- PumpPortal to add `tokenCreatedAt` to their event schema, or
- A cross-referenced on-chain lookup (which would yield T3, not T2)
