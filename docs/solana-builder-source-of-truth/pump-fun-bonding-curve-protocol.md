# Pump.fun Bonding-Curve Protocol

**Status:** REFRESHED 2026-07-30 — DIRECT ON-CHAIN MIGRATION CONTRACT ACTIVE
**Active authority:** A1 official `github.com/pump-fun/pump-public-docs` IDLs,
pinned and verified by `src/printer_v1/sources/pump_contracts.py`. Older
PumpPortal observations below are retained only as historical contract text and
have no ordinary-runtime authority.

## Restored Factory Contract Refresh (2026-07-30)

The ordinary restored factory no longer consumes PumpPortal migration frames.
The official Pump public repository and IDL are pinned by
`src/printer_v1/sources/pump_contracts.py`, including the mainnet Pump program
`6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P`, the exact `migrate`
discriminator, its ordered 25-account contract, and the Pump/PumpSwap PDA
relationships. `UNKNOWN_REQUIRES_RESEARCH` below is preserved as historical
lane text and does not override that later pinned active contract.

The live-tail locator accepts only a successful finalized transaction containing
exactly one supported top-level Pump `migrate` instruction. Program presence
without the exact discriminator and accounts is insufficient.

Pump.fun launches tokens on a bonding curve. When a token's curve completes it
**graduates/migrates** to a post-curve AMM (historically Raydium; PumpSwap for
newer graduations). This module documents the launch and migration event
semantics Printer V1 consumes via the free PumpPortal streams, and the
launch-vs-migration timestamp rules. It does not authorize any execution.

## Lifecycle Stages (as Printer observes them)

| Stage | Event source | Printer channel | Evidence tier |
|---|---|---|---|
| New launch on curve | PumpPortal `subscribeNewToken` | `PUMPFUN_NEW_TOKEN` | `OBSERVED_LIVE_LAUNCH` (no provider timestamp) |
| Graduation / migration | PumpPortal `subscribeMigration` | `PUMPFUN_MIGRATION` | none for token age (see below) |
| Post-migration pool | PumpSwap confirmation | `PUMPSWAP_GRADUATED` / migration ref | none for token age |

## Launch Event Semantics (`subscribeNewToken`)

Real launch events carry mint, pool, bonding-curve reserves, and creator, but
**no creation timestamp** (verified across live observations; see
`pumpportal-api-contract.md`). Bonding-curve fields Printer reads:

| Field | Use |
|---|---|
| `mint` | token mint identity |
| `bondingCurveKey` | pair/pool identity fallback |
| `vSolInBondingCurve` | approximate liquidity (SOL reserves → approx USD) |
| `vTokensInBondingCurve` | curve token reserves |
| `solAmount` / `initialBuy` / `marketCapSol` | activity context |

Because no provider timestamp exists, a real launch event is stamped
`live_observed_launch=True`, `token_created_at=NULL`, `token_age_seconds=NULL`,
tier `OBSERVED_LIVE_LAUNCH`. **T2 is not achievable from this stream.**

## Migration Event Semantics (`subscribeMigration`)

Migration events graduate a token off the bonding curve to a post-curve pool.
Printer reads:

| Field | Use |
|---|---|
| `mint` | token mint identity (must match the graduated token) |
| `newRaydiumPool` | post-migration pool address (pair identity) |

Normalization (`_normalize_pumpportal_event` with `pumpfun_migration_stream`):
emits `dex=raydium`, pair = `newRaydiumPool`, and **does not extract any
timestamp** — `token_created_at` and `live_observed_launch` remain unset.

## Timestamp Rule (critical, sprint lock)

- **Launch time, migration time, and pair/pool creation time must never become
  `token_created_at`.**
- The launch stream provides no creation timestamp; migration provides none
  either. Neither may be inferred into T2/T3 token-age evidence.
- A migration/graduation transaction block time may be stored as governed
  evidence of the *migration event* only; it must **not** stamp T2 or
  `token_created_at` in this sprint. See `source-governor-evidence-rules.md`.

## Source Provenance and Replay

- Every event carries `source_name=pumpportal` and its request_kind channel.
- Duplicate events (same mint/pair within a bounded response) are collapsed by
  within-response dedup; the first valid occurrence is retained.
- Locator-vs-proof: a PumpPortal-provided signature/pool is locator evidence
  only; it becomes proof only when an independent on-chain read confirms it
  (deferred; not performed in this sprint).

## V1 Compliance

| Requirement | Status |
|---|---|
| Free keyless streams only | PASS |
| No wallet / private keys / paid tier | PASS |
| No execution / instruction building / signing | PASS |
| No metered trade/account streams | PASS (not addressable) |
| No autonomous reconnect loop | PASS (bounded, zero-reconnect transport) |

## UNKNOWN_REQUIRES_RESEARCH

| Item | Status |
|---|---|
| Official pump.fun program ID / IDL and pinned A1 commit | UNKNOWN_REQUIRES_RESEARCH |
| Exact bonding-curve completion threshold and on-chain graduation trigger | UNKNOWN_REQUIRES_RESEARCH |
| Whether newer graduations report a PumpSwap pool field distinct from `newRaydiumPool` | UNKNOWN_REQUIRES_RESEARCH |
| Whether migration events ever include a creation/graduation timestamp | UNKNOWN_REQUIRES_RESEARCH |

## Change History

| Date | Change | Author |
|---|---|---|
| 2026-07-12 | Authored from A6 implementation and verified PumpPortal schema; launch/migration/timestamp semantics documented; on-chain program specifics marked UNKNOWN_REQUIRES_RESEARCH | Claude Opus 4.8 / PumpPortal-PumpSwap readiness |
