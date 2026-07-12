# Printer V1 — Fresh Discovery & PumpSwap Confirmation Report

**Date:** 2026-07-12
**Scope:** Two gated lanes. Paper-only. No scoring/ranking/confidence/weighting,
paid API, wallet, keys, execution, memory, retrieval, paper decisions,
BUY/SELL/HOLD, positions, trades, audits, PnL, A3, or V2-3. Persistent DB
(`data/printer_v1.sqlite3`) hash unchanged:
`97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB`.
Live proofs used fresh isolated DBs under `data/` (gitignored).

---

## Stage 1 — DexScreener fresh discovery vector

**Verdict: `DEXSCREENER_FRESH_VECTOR_PASS`**

### Audit (official keyless endpoints)

Verified against `docs.dexscreener.com/api/reference` (all keyless, no API key):

- `/token-profiles/latest/v1` — recently profiled tokens (`chainId`,
  `tokenAddress`, `updatedAt`); documented 60 req/min; recency-ordered.
- `/tokens/v1/{chainId}/{addresses}` — batch pair data for up to 30 comma-joined
  mints (same pair shape as search).
- `/token-boosts/latest/v1` / `/top/v1` — boosted tokens. **Not used**: boosts
  are promotions, not quality, and would be a score. Deliberately avoided.
- `/latest/dex/search` — the existing text-match vector (popular-token repeats).

Live probe findings: `/token-profiles/latest/v1` returned 13 Solana tokens of 30
(rest `robinhood`), all freshly listed pump.fun tokens (e.g. CASHPIGGY
`6wtZ…pump`). `/tokens/v1/solana/{10 addrs}` returned 10 distinct fresh pairs —
zero popular-token repeats — with full identity + market fields and
`pairCreatedAt`. Recency semantics confirmed; Solana filter by `chainId`;
identity via `baseToken.address` + `pairAddress`; duplication handled by existing
within-response dedup.

### Design & implementation (smallest governed categorical plan)

`build_dexscreener_fresh_profiles_transport`: one governed request performing two
keyless GETs — latest profiles → distinct Solana mints (deduped, capped 30) →
batch `/tokens/v1/solana/{addrs}` → `{"pairs": [...]}`. Reuses
`normalize_dexscreener_fixture_result` so **Solana-only and infrastructure-mint
exclusions, dedup, cooldown, rotation, source status/quality, and Governor /
scheduler limits are all preserved**. New request kind `dexscreener_fresh_profiles`
(registry + catalog READY), new channel `DEXSCREENER_LATEST_PROFILES`. No boost
amount, ordering position, or numeric is used as a score.

### Proof

- Fixtures: `test_dexscreener_fresh_profiles.py` (10) — profiles→tokens payload,
  non-Solana filtered, no-Solana fails closed, 429 rate-limit, malformed fails
  closed, dedup, cap ≤30, end-to-end exclusion, no score field.
- Live (isolated DB): `COMPLETE`, `DEXSCREENER_LATEST_PROFILES`, 1 req/1 resp/0
  fail. **14 fresh candidates found; 5 distinct fresh memecoins accepted +
  persisted** (TRACK_FAST/TRACK_NORMAL mix), 9 rejected (8 watch-only, 1
  max-candidates). No infrastructure mint accepted; all persisted with the fresh
  channel — vs the search vector's single popular-token accept.

---

## Stage 2 — PumpSwap live confirmation

**Verdict: `PUMPSWAP_LIVE_CONFIRMATION_PASS`**

### Audit & design

- **Program ID verified on-chain:** `pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA`
  — `getAccountInfo` returns `executable=true`, owner BPF Upgradeable Loader
  (A1 on-chain); corroborated by the pump-fun pump-swap SDK and Bitquery (A7).
- **Locator vs proof separation** (real PumpPortal migration event):
  - *Locator*: `mint`, migration `signature`, venue `pool: "pump-amm"` (label).
  - *On-chain pool confirmation*: `getAccountInfo(pool)` → `owner == program` and
    `base_mint@offset 43 == expected_mint` (both verified live on two pools).
  - *Migration tx time*: `getTransaction(signature).blockTime` — migration
    evidence only.
  - *Token creation time*: never derived; not stamped.
- **Migration or pool time never becomes `token_created_at`.** Enforced: the
  confirmation token entry carries no `token_created_at`; block time is stored as
  `pumpswap_migration_block_time`.

### Implementation (minimal read-only)

`pumpswap.py`: `PUMPSWAP_AMM_PROGRAM_ID`, base58 decode helper,
`confirm_pumpswap_pool_from_account` (pure: owner == program AND base_mint@43 ==
mint; fails closed on not-found / wrong-owner / short / undecodable / mismatch),
`build_pumpswap_confirmation_transport` (one `getAccountInfo` + optional one
`getTransaction`), `normalize_pumpswap_confirmation_payload` (fails closed unless
confirmed). New request kind `pumpswap_onchain_pool_confirmation` (registry +
adapter routing). Read-only; no swap/route/instruction/signing.

### Proof

- Fixtures: `test_pumpswap_onchain_confirmation.py` (13) — valid confirm; wrong
  owner / mint mismatch / missing account / short data all fail closed; normalize
  confirmed→COMPLETE with no `token_created_at`; unconfirmed→FAILED; request-kind
  routing; migration block-time is evidence-only; transport end-to-end (mocked
  RPC) incl. mismatch fail-closed; program ID + registry wiring; no score fields.
- Live (isolated DB) — real migration-event locator mint
  `GwZvGvVzjWTL1mvpw55KQWztTQvWo3B6ew16N2aspump`, sig `ijqgk3Ht…`, pool resolved
  `6TJuebvz9hqJaybCWpKm7ygmFqcxHxJ3Azi5BJhmHak`: `COMPLETE / CLEAN_DATA`,
  `pool_owner == program_id == pAMMBay…`, `migration_block_time = 1783886668`,
  slot `432499503`, `token_created_at` absent; 1 governed request / 1 response /
  0 failures.

---

## Source-stack changes

- `dexscreener-api-contract.md` — fresh-profiles vector documented; recency
  endpoint UNKNOWN resolved.
- `pumpswap-pool-confirmation-contract.md` — verified program ID, on-chain
  confirmation contract, base_mint@43 layout, migration-block-time-as-evidence;
  program-ID UNKNOWN resolved (full IDL/PDA/quote_mint remain open).

## Global verification

- Persistent DB hash unchanged (above).
- No memory, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades,
  audits, PnL. No paid API / wallet / keys. All new logic categorical — no
  scoring/ranking/confidence/weighting.

## Remaining blockers / next lane (from evidence — not started)

- PumpSwap pool full account layout (quote_mint@75 inferred, not confirmed),
  PDA seed derivation, and whether migration events ever carry the pool address
  remain `UNKNOWN_REQUIRES_RESEARCH`.
- Highest-value next lane: **resolve the PumpSwap pool address on-chain from the
  migration signature alone** (parse the migrate transaction to extract the
  created pool account owned by the PumpSwap program), removing the DexScreener
  pool-resolution dependency. A3 not started.
