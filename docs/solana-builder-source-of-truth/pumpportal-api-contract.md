# PumpPortal API Contract

**Status:** VERIFIED 2026-07-12  
**Verification method:** Live probe from operator machine (9 events observed)

## Access

| Property | Value |
|---|---|
| WebSocket URL | `wss://pumpportal.fun/api/data` |
| Authentication | None (keyless, no API key, no wallet, no registration) |
| Cost | Free |
| Protocol | WebSocket over TLS (wss://) |
| Certificate | Let's Encrypt, valid until 2026-09-05 |
| Resolved IP | 216.155.134.164 |

## Subscription Methods

### `subscribeNewToken` — launch stream

Sent immediately after connection:

```json
{"method": "subscribeNewToken"}
```

Server sends one acknowledgment before events begin:

```json
{"message": "Successfully subscribed to token creation events."}
```

This acknowledgment must **not** be counted as a token event. It contains no `mint` field.

### `subscribeMigration` — migration stream

```json
{"method": "subscribeMigration"}
```

## Real Event Schema — `subscribeNewToken`

Verified from 9 consecutive live observations on 2026-07-12:

| Field | Type | Always present | Notes |
|---|---|---|---|
| `mint` | string | YES | Token mint address |
| `signature` | string | YES | Transaction signature |
| `txType` | string | YES | e.g. `"create"` |
| `traderPublicKey` | string | YES | Creator wallet |
| `initialBuy` | number | YES | SOL amount of initial buy |
| `solAmount` | number | YES | SOL in transaction |
| `marketCapSol` | number | YES | Market cap in SOL |
| `vSolInBondingCurve` | number | CONDITIONAL | Bonding curve SOL reserves (most events) |
| `vTokensInBondingCurve` | number | CONDITIONAL | Bonding curve token reserves |
| `bondingCurveKey` | string | CONDITIONAL | Bonding curve address |
| `pool` | string | YES | Pool identifier |
| `name` | string | YES | Token name |
| `symbol` | string | YES | Token symbol |
| `uri` | string | YES | Metadata URI |
| `is_mayhem_mode` | boolean | CONDITIONAL | Present on most events |
| `newTokenBalance` | number | CONDITIONAL | Rare (non-bonding-curve events) |
| `solInPool` | number | CONDITIONAL | Rare (non-bonding-curve events) |
| `tokensInPool` | number | CONDITIONAL | Rare (non-bonding-curve events) |

## Critical Negative Findings

### No timestamp fields

**`tokenCreatedAt` is NOT present in real `subscribeNewToken` events.**

Zero timestamp fields were observed across 9 events. The following fields were absent in every observed event:

- `tokenCreatedAt`
- `createdTimestamp`
- `timestamp`
- `createdAt`
- `created_at`

**Implication:** T2 token-age evidence tier cannot be stamped from the
`subscribeNewToken` stream alone. Events from this stream receive
`live_observed_launch=True` and `token_age_evidence_tier=OBSERVED_LIVE_LAUNCH`.

See `token-age-evidence-tier-registry.md`.

### Pre-event acknowledgment message

The server sends `{"message": "..."}` before any token events. Transport
implementations must skip this message and must NOT count it toward the
event-collection limit (max_events). Counting the acknowledgment as a
collected event causes the collection loop to exit before any real events
arrive, which is the root cause of the original V2-2Y transport failure.

## Transport Behavior

| Layer | Status |
|---|---|
| DNS | PASS — resolves to 216.155.134.164 |
| TCP | PASS — connects in ~204ms |
| TLS | PASS — valid Let's Encrypt certificate |
| WebSocket handshake | PASS — upgrades in ~1226ms |
| Subscription send | PASS — accepted, confirmation received |
| Event delivery | PASS — events arrive continuously (9 in ~45s observed) |
| Token creation timestamp | FAIL — field absent from all events |

## V1 Compliance

| Requirement | Status |
|---|---|
| No API key | PASS — keyless |
| No wallet connection | PASS — no wallet |
| No private keys | PASS |
| No paid dependency | PASS — free stream |
| No authentication registration | PASS — anonymous |

## T2 Tier Status

**T2 is NOT achievable from `subscribeNewToken` alone.**

T2 requires an explicit provider-supplied `tokenCreatedAt` timestamp
(see `token-age-evidence-tier-registry.md`). PumpPortal does not include
this field.

Events from this stream receive: `token_age_evidence_tier = OBSERVED_LIVE_LAUNCH`

## Compliant Alternatives Requiring a Later Design Lane

The following alternatives could enable T2 or equivalent evidence. None may
be implemented without an explicit operator-approved design lane.

| Alternative | Evidence tier | Design lane required | V1 constraint risk |
|---|---|---|---|
| Solana RPC `getAccountInfo` on mint → block time | T3 | New governed RPC source lane | None (free, keyless) |
| Helius free-tier mint-creation webhook/API | T2 or T3 | New governed Helius source lane | None if free tier |
| PumpPortal future schema addition of `tokenCreatedAt` | T2 | Re-verify after PumpPortal update | None |
| DexScreener pool age for pair_created_at | T4_PAIR_ONLY | Already implemented | Not token-age evidence |

## UNKNOWN_REQUIRES_RESEARCH Items

| Item | Status |
|---|---|
| Whether PumpPortal will add `tokenCreatedAt` in future | UNKNOWN_REQUIRES_RESEARCH |
| Whether Helius free tier exposes token creation time | UNKNOWN_REQUIRES_RESEARCH |
| Whether `subscribeMigration` events include timestamp fields | UNKNOWN_REQUIRES_RESEARCH |
| Rate limits for `subscribeNewToken` stream | UNKNOWN_REQUIRES_RESEARCH — no documented limit observed |
