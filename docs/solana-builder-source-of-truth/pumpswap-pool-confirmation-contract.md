# PumpSwap Pool Confirmation Contract

**Status:** AUTHORED 2026-07-12
**Authority:** A6 (Printer implementation `src/printer_v1/sources/pumpswap.py`);
A1/A3 upstream PumpSwap program semantics marked `UNKNOWN_REQUIRES_RESEARCH`
where no pinned official source is cited.

PumpSwap is the post-migration AMM for graduated Pump.fun tokens. In Printer V1
the PumpSwap adapter is **read-only confirmation and provenance metadata only**.
It confirms that an observed token/pool exists on the graduation venue; it never
executes, signs, builds instructions, routes, or moves funds.

## Role and Permission

| Dimension | Value |
|---|---|
| `printer_role` | `DISCOVERY` (venue confirmation for graduated tokens) |
| `printer_readiness` | `ALLOWED_FIXTURE_ONLY` (no keyless live PumpSwap endpoint wired) |
| `access_policy` | `UNKNOWN_REQUIRES_RESEARCH` (no confirmed free keyless pool endpoint) |
| `v1_permission` | `ALLOWED_FIXTURE_ONLY` |
| Execution | PROHIBITED — no swap, route, instruction, or signing |

## Allowed Request Kinds

| Request kind | Meaning |
|---|---|
| `pumpswap_pool_confirmation` | Confirm a graduated token's PumpSwap pool exists |
| `pumpswap_migration_pool_reference` | Reference the migration/graduation pool |
| `pumpswap_liquidity_reference` | Read-only liquidity reference |

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

- A transaction block time may be stored as governed evidence only.
- It must **not** stamp T2 or `token_created_at`.
- Live signature confirmation via RPC is **not implemented in this sprint** and
  is marked `UNKNOWN_REQUIRES_RESEARCH` for a later governed lane.

## V1 Compliance

| Requirement | Status |
|---|---|
| Read-only (no execution/signing/routing) | PASS |
| No wallet / private keys | PASS |
| No paid dependency | PASS (fixture-only; no keyless live endpoint wired) |
| Solana-only | PASS |
| No scoring / ranking | PASS |

## UNKNOWN_REQUIRES_RESEARCH

| Item | Status |
|---|---|
| Official PumpSwap AMM program ID / IDL and pinned authority | UNKNOWN_REQUIRES_RESEARCH |
| Whether a free keyless PumpSwap pool-state endpoint exists for live confirmation | UNKNOWN_REQUIRES_RESEARCH |
| Exact on-chain pool account layout for direct RPC confirmation | UNKNOWN_REQUIRES_RESEARCH |

## Change History

| Date | Change | Author |
|---|---|---|
| 2026-07-12 | Authored from A6 implementation; confirmation, timestamp, dedup, and governed-signature rules documented; live endpoint gaps marked UNKNOWN_REQUIRES_RESEARCH | Claude Opus 4.8 / PumpPortal-PumpSwap readiness |
