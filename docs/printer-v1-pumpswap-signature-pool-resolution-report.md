# Printer V1 — PumpSwap Pool Resolution from Migration Signature

**Date:** 2026-07-12
**Verdict: `PUMPSWAP_SIGNATURE_POOL_RESOLUTION_PASS`**
**Scope:** One lane. Read-only. No DexScreener dependency for pool resolution.
No scoring/ranking/confidence/weighting, paid API, wallet, keys, execution,
memory, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits,
PnL, A3, or V2-3. Persistent DB (`data/printer_v1.sqlite3`) hash unchanged:
`97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB`.

## Audit findings

A real PumpPortal migration event supplies only `mint`, migration `signature`,
`txType: "migrate"`, and venue `pool: "pump-amm"` (a label, not a pool address).
So the pool must be resolved from the transaction.

Audit of a real migration transaction (`getTransaction`,
`maxSupportedTransactionVersion=0`): **27 account keys** — 16 static
(`message.accountKeys`), 1 ALT-loaded writable, 10 ALT-loaded readonly
(`meta.loadedAddresses`). Of these, **exactly 2 are owned by the PumpSwap AMM
program** `pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA`:

- `6TJuebvz9hqJaybCWpKm7ygmFqcxHxJ3Azi5BJhmHak` — 301 bytes, `base_mint@43 ==
  expected mint` → **the pool**.
- `ADyA8hdefvWN2dbGGWFotbzWxrAvLW83WG6QCVXvJKqw` — 907 bytes, no mint at offset 43
  → a different PumpSwap account type (config), correctly excluded.

Therefore `owner == program AND base_mint@43 == mint` yields a **unique** pool.

## Parsing contract (implemented)

`migration signature → getTransaction → account keys (static + ALT-loaded,
deduped) → getMultipleAccounts (batched ≤100) → filter owner==program AND
base_mint@43==mint → exactly one pool`.

- `collect_transaction_account_keys(tx)` — static + `loadedAddresses.{writable,
  readonly}`, order-preserving dedup; accepts jsonParsed or string keys.
- `resolve_pumpswap_pool_from_transaction(tx, account_infos, expected_mint)` —
  pure; fails closed with explicit reasons: `transaction_not_found`,
  `no_confirmed_pumpswap_pool_in_transaction` (zero),
  `ambiguous_multiple_pumpswap_pools` (>1). Records `account_keys_total`,
  `program_owned_count`, `mint_matched_count`, migration block time + slot.
- `build_pumpswap_signature_pool_resolver_transport(...)` — governed transport
  doing the RPC sequence; resolved pool re-confirmed via
  `confirm_pumpswap_pool_from_account`. New request kind
  `pumpswap_signature_pool_resolution` (registry + adapter routing).
- **Migration block time is migration evidence only** (`pumpswap_migration_block_time`)
  and never becomes `token_created_at` or a token-age tier.
- No DexScreener import or call in `pumpswap.py` (asserted by test).

## Tests

`test_pumpswap_signature_pool_resolution.py` (12): account-key collection
(static + ALT + dedup); unique resolution; zero/ambiguous/missing fail-closed;
config account excluded; transport end-to-end (mocked RPC); tx-not-found and
ambiguous fail-closed through the normalizer; resolution provenance with no
`token_created_at`; registry/routing wiring; no score/rank fields and no
DexScreener dependency. Existing pumpswap/registry suites remain green.

## Live proof (isolated DB)

Locator: a real captured PumpPortal migration signature (mint
`GwZvGvVzjWTL1mvpw55KQWztTQvWo3B6ew16N2aspump`, sig `ijqgk3Ht…`). The bounded
capture window observed no new graduation, so the proof used this real
previously-captured migration signature. Governed run:

- `COMPLETE / CLEAN_DATA`; **pool resolved from the signature alone**:
  `6TJuebvz9hqJaybCWpKm7ygmFqcxHxJ3Azi5BJhmHak`.
- `account_keys_total = 27`, `program_owned_count = 2`, `mint_matched_count = 1`.
- `pool_owner == program_id`, `pumpswap_pool_resolved_from_signature = True`,
  `migration_block_time = 1783886668`, `token_created_at` absent.
- 1 governed request / 1 response / 0 failures. No DexScreener call.

Chain proven end-to-end:
`migration signature → transaction parsing → pool discovery → PumpSwap
ownership → exact mint binding`.

## Source-stack updates

`pumpswap-pool-confirmation-contract.md` — signature pool resolution contract
added; "resolve pool without DexScreener" resolved; "migration events carry pool
address?" answered (no — resolved from the transaction). PDA seed derivation
remains `UNKNOWN_REQUIRES_RESEARCH` but is no longer required.

## Commit

`Resolve PumpSwap pool from migration signature`

## Remaining blocker

- Live capture of a *fresh* migration signature is timing-dependent; a bounded
  window may see no graduation (the proof then uses a real captured signature).
- PumpSwap Pool full account layout (quote_mint@75 inferred) and PDA seed
  derivation remain `UNKNOWN_REQUIRES_RESEARCH` — not required for resolution.

A3 not started.
