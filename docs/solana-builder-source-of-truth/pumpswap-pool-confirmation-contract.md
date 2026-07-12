# PumpSwap Pool Confirmation Contract

**Status:** VERIFIED 2026-07-12 (governed on-chain confirmation proven live)
**Authority:** A1 on-chain (Solana RPC `getAccountInfo`) for the program ID and
pool ownership; A6 (Printer implementation `src/printer_v1/sources/pumpswap.py`);
A7 corroboration from the pump-fun pump-swap SDK and Bitquery PumpSwap docs.

PumpSwap is the post-migration AMM for graduated Pump.fun tokens. In Printer V1
the PumpSwap adapter is **read-only confirmation and provenance metadata only**.
It confirms that an observed token/pool exists on the graduation venue; it never
executes, signs, builds instructions, routes, or moves funds.

## PumpSwap AMM Program ID (verified on-chain 2026-07-12)

`pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA`

- On-chain `getAccountInfo(program)` returns `executable=true`, owner
  `BPFLoaderUpgradeab1e11111111111111111111111` — a deployed Solana program.
- Corroborated by the official `@pump-fun/pump-swap-sdk` and Bitquery's PumpSwap
  API docs (A7, corroboration only).

## Role and Permission

| Dimension | Value |
|---|---|
| `printer_role` | `DISCOVERY` (governed on-chain venue confirmation for graduated tokens) |
| `printer_readiness` | `ACTIVE_READY` (governed on-chain confirmation via Solana RPC) |
| `access_policy` | `KEYLESS_PUBLIC` (public Solana RPC `getAccountInfo` / `getTransaction`) |
| `v1_permission` | `ALLOWED_GOVERNED` |
| Execution | PROHIBITED — no swap, route, instruction, or signing |

## Allowed Request Kinds

| Request kind | Meaning |
|---|---|
| `pumpswap_pool_confirmation` | Confirm a graduated token's PumpSwap pool exists (fixture) |
| `pumpswap_migration_pool_reference` | Reference the migration/graduation pool (fixture) |
| `pumpswap_liquidity_reference` | Read-only liquidity reference (fixture) |
| `pumpswap_onchain_pool_confirmation` | **Governed on-chain confirmation via Solana RPC** |

## On-Chain Confirmation Contract (`pumpswap_onchain_pool_confirmation`)

Locator evidence: a real PumpPortal migration event supplies `mint`, migration
`signature`, and venue `pool: "pump-amm"` (a venue label, not a pool address).
The pool address is resolved separately (e.g. DexScreener `dexId == pumpswap`).

Confirmation (all categorical hard equalities — no scores/ranks/weights):

1. `getAccountInfo(pool, base64)` — the pool account must exist.
2. `owner == pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA` — correct program identity.
3. `base_mint` at pool-account byte offset **43** (`[43,75)`) must equal the
   expected mint (exact mint↔pool binding). Layout:
   8 (anchor discriminator) + 1 (pool_bump) + 2 (index) + 32 (creator) = 43;
   verified live against two distinct real pools.

Fails closed with an explicit reason on: account not found, owner not PumpSwap,
undecodable/short data, base_mint mismatch, or expected-mint undecodable.

### Migration transaction block time

When a migration `signature` is supplied, `getTransaction(signature)` block time
may be stored as `pumpswap_migration_block_time` (with `pumpswap_migration_slot`)
— **migration evidence only**. It must NEVER stamp `token_created_at` or any
token-age tier. The confirmation token entry carries no `token_created_at`.

### Live proof (2026-07-12, isolated DB)

Locator (real PumpPortal migration event): mint
`GwZvGvVzjWTL1mvpw55KQWztTQvWo3B6ew16N2aspump`, signature `ijqgk3Ht…`,
venue `pump-amm`. Pool resolved `6TJuebvz9hqJaybCWpKm7ygmFqcxHxJ3Azi5BJhmHak`.
Result: `COMPLETE / CLEAN_DATA`, `pool_owner == program_id == pAMMBay…`,
`migration_block_time = 1783886668`, `token_created_at` absent; 1 governed
request / 1 response / 0 failures.

Any other request kind is rejected at the Source Governor boundary
(`pumpswap_request_kind_not_allowed`).

## Confirmation Contract

A pool entry is only accepted when ALL of the following hold
(`_normalize_pumpswap_pool`):

| Requirement | Rule |
|---|---|
| Token mint | `base_mint` / `baseMint` / `mint` / `token_mint` present |
| Pool address | `pool_address` / `poolAddress` / `pool_id` / `address` present |
| Chain | absent, `solana`, or `sol` — any other chain rejects the pool |
| Emitted `dex` | always `pumpswap` |
| Emitted `chain` | always `solana` |

Fails closed: a payload with no valid Solana pool entry returns
`FAILED / pumpswap_no_valid_solana_pools`. A malformed payload (no tokens/pools
list) returns `FAILED / pumpswap_missing_pool_list`. A `fixture_status:"failure"`
returns the declared failure type; `fixture_status:"stale"` returns
`STALE / pumpswap_stale_data`.

## Timestamp Semantics (critical)

- PumpSwap confirmation supplies **pool/venue** existence, not token creation.
- **Migration time and pair/pool creation time must NEVER become
  `token_created_at`.** The normalizer does not extract or emit any token
  creation timestamp; `token_age_seconds` and `token_created_at` remain unset.
- A graduated token's evidence tier for age is unchanged by PumpSwap
  confirmation (see `token-age-evidence-tier-registry.md`). PumpSwap may
  contribute the `PUMPSWAP_GRADUATED` / migration channel label only.

## Duplicate / Replay Handling

- Confirmation is idempotent read-only: re-confirming the same pool yields the
  same normalized entry. Downstream within-response dedup
  (`filter_within_response_duplicates`) collapses duplicate mint/pool rows.
- Exact token/pool matching is required: a confirmation whose mint or pool does
  not match the observed candidate must be treated as a mismatch and not used to
  confirm that candidate.

## Governed Signature / Transaction Confirmation

Where a graduation/migration is evidenced by a transaction signature, a governed
Solana RPC `getTransaction` block-time read MAY be stored as governed evidence
of the confirmation event. Per this sprint's lock:

- A transaction block time is stored as `pumpswap_migration_block_time` /
  `pumpswap_migration_slot` — governed evidence only.
- It must **not** stamp T2 or `token_created_at`. Proven: the confirmation token
  entry carries no `token_created_at`.
- Live confirmation via RPC is IMPLEMENTED and proven (see live proof above).

## V1 Compliance

| Requirement | Status |
|---|---|
| Read-only (no execution/signing/routing) | PASS |
| No wallet / private keys | PASS |
| No paid dependency | PASS (keyless public Solana RPC) |
| Solana-only | PASS |
| No scoring / ranking | PASS (categorical hard equalities only) |

## UNKNOWN_REQUIRES_RESEARCH

| Item | Status |
|---|---|
| Official PumpSwap AMM program ID / IDL and pinned authority | RESOLVED — program ID `pAMMBay…` verified on-chain (executable) + A7 SDK/Bitquery corroboration. Full IDL/account layout beyond base_mint@43 still UNKNOWN_REQUIRES_RESEARCH |
| PumpSwap Pool account full layout (quote_mint, lp_mint, reserves offsets) | UNKNOWN_REQUIRES_RESEARCH — only base_mint@43 verified live; quote_mint@75 inferred, not independently confirmed |
| PumpSwap pool PDA seed derivation (to resolve pool address without DexScreener) | UNKNOWN_REQUIRES_RESEARCH |
| Whether migration events ever carry the pool ADDRESS (not just `pool: "pump-amm"` venue label) | UNKNOWN_REQUIRES_RESEARCH |

## Change History

| Date | Change | Author |
|---|---|---|
| 2026-07-12 | Authored from A6 implementation; confirmation, timestamp, dedup, and governed-signature rules documented; live endpoint gaps marked UNKNOWN_REQUIRES_RESEARCH | Claude Opus 4.8 / PumpPortal-PumpSwap readiness |
| 2026-07-12 | Governed on-chain confirmation implemented and proven live: program ID verified on-chain, base_mint@43 layout verified, migration block-time as evidence-only. Program-ID UNKNOWN resolved; full IDL/PDA/quote_mint remain open | Claude Opus 4.8 / PumpSwap live confirmation |
