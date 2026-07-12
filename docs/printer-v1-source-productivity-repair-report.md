# Printer V1 — Source Productivity & Readiness Repair Report

**Date:** 2026-07-12
**Scope:** Gated source-productivity mini-sprint (3 stages). Paper-only. No
execution, wallet, paid API, scoring/ranking, memory, retrieval, paper
decisions, positions, trades, audits, or PnL. Persistent DB
(`data/printer_v1.sqlite3`) hash unchanged throughout:
`97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB`.

All live proofs used fresh isolated DBs under `data/` (gitignored). One governed
connection each, hard-bounded, zero reconnect.

---

## Stage 1 — PumpPortal transport closeout

**Verdict: `MINIMAL_PUMPPORTAL_TRANSPORT_PASS_T2_LIVE_EVENT_BLOCKED`**
**Commit:** `3f7b5a9` "Fix PumpPortal launch acknowledgment handling"

- **Fix:** the bounded collection loop no longer counts the subscription
  acknowledgment (`{"message": "..."}`) as an event; only mint-bearing events
  are collected. Previously, with `max_events=1`, the acknowledgment ended
  collection before any real launch arrived.
- **Live proof:** one governed `subscribeNewToken` connection captured one real
  launch event — `anecdotalcoin` (`EoPaskBwbGK3GV7oxyNA5uPkQRnogTDZQBCxRUTDpump`).
  `source_status COMPLETE`, 1 request / 1 response / 0 failures.
- **T2 blocked (correctly):** the event carried no provider creation timestamp,
  so it became `live_observed_launch=true`, `token_created_at=NULL`,
  `token_age_seconds=NULL`, tier `OBSERVED_LIVE_LAUNCH`. **No T2 stamped.**
- Governed request/response provenance preserved.
- Tests: 35 in `test_v2_2y_pumpportal_t2_launch_proof.py` (added TR-24/25/26 for
  acknowledgment-drop and OBSERVED_LIVE_LAUNCH); 43 in
  `test_v2_2ab_pumpportal_live_transport.py` (bound-hardening test now asserts
  against the 120s ceiling).

---

## Stage 2 — DexScreener productivity repair

**Verdict: PARTIAL PASS** — the confirmed categorical safety/productivity gap is
repaired and proven; the deeper discovery-vector limitation is confirmed and
documented but intentionally not force-fixed (fixing it safely needs a larger
endpoint-strategy lane; gates were not weakened to inflate yield).

### Audit (requests -> responses -> parsed -> accepted -> persisted -> selected)

The DexScreener discovery path issues one governed HTTP GET to
`/latest/dex/search?q={query}` (default `pump`), normalizes pairs, dedups within
response, classifies (rule-only), and hands accepted candidates to selection.

Confirmed blockers (empirical live probe + code audit):

1. **No infrastructure-token / non-Solana exclusion at the source boundary.**
   GeckoTerminal already excludes WSOL/USDC/USDT base mints
   (`_SOLANA_NATIVE_QUOTE_MINTS`); DexScreener did not. Cross-chain rows and
   infrastructure quote-mints could enter the candidate stream and (for infra
   mints) be accepted as memecoins — a memecoin-only gap and wasted candidate
   consideration.
2. **The keyless `search` endpoint is a weak fresh-memecoin vector.** `q=pump`
   returns the PumpFun protocol token across many pools; `q=SOL` returns
   billion-USD major tokens. It is a text-match query with no recency ordering,
   and popular tokens dominate via per-mint pool duplication. This is the
   dominant reason DexScreener contributes few *fresh* assets.

### Design (smallest categorical, auditable repair — no scores/ranks/weights)

Add a categorical exclusion at `normalize_dexscreener_fixture_result`, mirroring
GeckoTerminal: drop non-Solana pairs, pairs missing pair/mint identity, and
infrastructure quote-mints (WSOL/USDC/USDT). Every excluded pair is recorded in
`normalized_payload["excluded_pairs"]` with an explicit reason — never silent.
Fails closed if no Solana memecoin pair survives.

### Implementation

`src/printer_v1/sources/dexscreener.py`: `_SOLANA_INFRASTRUCTURE_MINTS`
frozenset + categorical filter loop. Preserved: Solana-only, memecoin-only,
Source Governor, scheduler boundaries, mint/pair identity, source status /
data quality, existing dedup and rotation/cooldown rules.

### Proof

- **Fixtures:** `test_dexscreener_productivity_exclusion.py` (13 tests):
  non-Solana, infra-mint (WSOL/USDC/USDT), and missing-identity pairs excluded
  with reasons; real memecoin retained; all-junk response fails closed; infra
  mint never reaches selection; no score/rank/confidence field added.
- **Bounded live proof** (isolated DB `dexscreener_stage2_live_proof.sqlite3`,
  `q=pump`, max 5): `source_status COMPLETE`, 1 request / 1 response / 0
  failures. **17 Solana candidates seen; 13 non-Solana pairs excluded** at the
  boundary (bsc/pulsechain/tron "PUMP" clones, reason `non_solana_pair`),
  recorded in `excluded_pairs`. 1 accepted + persisted
  (`pumpCmXq...Dfn` → TRACK_FAST); 6 rejected with categorical reasons
  (5 `insufficient_activity_for_memory_growth`, 1 watch-only). No infrastructure
  mint accepted. Evidence (T4 pair-age context, market fields) reaches selection
  metadata.

### Remaining blocker (documented, not force-fixed)

The search endpoint's weak freshness vector is confirmed. A recency/newness
keyless Solana discovery endpoint is `UNKNOWN_REQUIRES_RESEARCH`
(`dexscreener-api-contract.md`). Resolving it belongs to a dedicated
endpoint-strategy lane; it must not be "fixed" by relaxing activity gates.

---

## Stage 3 — PumpPortal / PumpSwap readiness

**Verdict: PASS (with PumpSwap live confirmation deferred)** — launch stream
live-proven (Stage 1); migration transport wired and **a real live migration
event captured and correctly handled**; PumpSwap confirmation made usable for
discovery and fixture-proven (no keyless live endpoint exists, so live PumpSwap
confirmation is deferred to a later governed lane).

### Audit

- PumpPortal launch (`subscribeNewToken`): READY, live-proven (Stage 1).
- PumpPortal migration (`subscribeMigration`): previously NOT_READY (no live
  transport).
- PumpSwap confirmation: catalog entries were NOT_READY, so the discovery
  pipeline skipped them entirely — three CLI tests failed at HEAD because
  `source_channel` came back `None`.

### Design (contracts)

- **Launch events:** mint + curve reserves; no provider timestamp →
  `OBSERVED_LIVE_LAUNCH`, never T2.
- **Migration events:** mint + `newRaydiumPool`; `dex=raydium`; **no timestamp
  extracted** — migration/pair time never becomes `token_created_at`.
- **PumpSwap pool confirmation:** read-only; Solana-only; exact mint/pool
  identity required; fails closed on malformed/mismatched/non-Solana/missing
  identity/disallowed kind. A migration/confirmation transaction block time may
  be stored as governed evidence only — never stamping T2 or `token_created_at`
  in this sprint.
- Source provenance and duplicate/replay handling preserved (within-response
  dedup keeps first valid occurrence).

New source-stack docs: `pump-fun-bonding-curve-protocol.md`,
`pumpswap-pool-confirmation-contract.md`, `dexscreener-api-contract.md`
(uncertain items marked `UNKNOWN_REQUIRES_RESEARCH`).

### Implementation

- `pumpportal.py`: generalized `build_pumpportal_live_transport(request_kind=...)`
  with a subscription map (launch / migration only — metered trade/account
  streams intentionally not addressable); added
  `build_pumpportal_migration_transport` (same hard bounds, zero reconnect).
- `commands.py`: wired the migration live transport; flipped
  `pumpfun_migration_stream` and both PumpSwap confirmation kinds to READY.
  PumpSwap still REQUIRES an operator-provided confirmation transport (read-only;
  raises without one).

### Proof

- **Fixtures:** `test_pumpportal_pumpswap_readiness.py` (14 tests): migration
  transport subscribes `subscribeMigration`; launch unchanged; unaddressable
  request_kind rejected; migration event never sets `token_created_at` (even
  with a stray timestamp); PumpSwap valid confirmation COMPLETE; malformed /
  non-Solana / missing-identity / disallowed-kind all fail closed; migration
  catalog READY.
- **Live migration proof** (isolated DB): a 30s window observed no graduation
  (recorded honestly as `pumpportal_no_valid_solana_events` — graduations are
  far rarer than launches). A 120s window then **captured a real live migration
  event** — mint `EZFTe86hLyReT8AEfKPosP3YdZus8Z9u7yNhdHXTpump`,
  `source_status COMPLETE`, `PUMPFUN_MIGRATION` channel, 1 request / 1 response /
  0 failures. The event carried **`token_created_at=NULL`** and
  `live_observed_launch=false` (migration time is never token creation time,
  as required), `dex=raydium`. This particular event lacked a pool address, so
  it correctly **failed closed** at classification (INSTANT_REJECT) rather than
  being tracked on incomplete evidence.

### Remaining blockers (documented)

- Live migration event capture is timing-dependent; a bounded window may not
  contain a graduation.
- No keyless live PumpSwap pool-state endpoint is confirmed
  (`UNKNOWN_REQUIRES_RESEARCH`); live PumpSwap confirmation and governed
  signature/tx block-time confirmation are deferred to a later governed lane.

---

## Global verification

- Persistent DB hash unchanged (above).
- No memory generation, retrieval, paper decisions, BUY/SELL/HOLD, positions,
  trades, audits, or PnL.
- No paid API, wallet, or private keys. All streams free/keyless; PumpSwap
  fixture/operator-transport only.
- No scoring, ranking, confidence, or weighted logic — all filters categorical.

## Next lane (from the evidence — not started)

The highest-value remaining productivity lever is the **DexScreener fresh-token
discovery vector** (a recency/newness keyless endpoint strategy), followed by a
**governed live PumpSwap confirmation + migration signature block-time** lane.
A3 was not started.
