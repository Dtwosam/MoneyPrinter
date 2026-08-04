# V2-9.8B Governed PumpSwap Account-Batch Confirmation Closeout

Date: 2026-08-04

Lane: `V2-9.8B — Governed PumpSwap Account-Batch Confirmation`

Baseline: `3cb19eac2e0d1bc9a531b060a836ff7816aaf36b`  
(`Repair permanent discovery conversion flow`)

Plan: `docs/superpowers/plans/2026-08-04-governed-pumpswap-account-batch-confirmation.md`

## Verdict

`V2_9_8B_GOVERNED_PUMPSWAP_ACCOUNT_BATCH_CONFIRMATION_PASS`

The production `PROTOCOL_CONFIRMATION_DUE` queue now executes a real Source-Governed
Solana `getMultipleAccounts` batch for supported Pump-family mint+pool identities,
applies the existing PumpSwap owner + `base_mint@43` law per member, transitions
exact-market state, and returns confirmed identities for current-market validation.
No live providers, authorization, or `WINDOW_15M` attempt ran in this lane.

## Owner classification (as implemented)

| Owner | Class | Notes |
|---|---|---|
| `process_protocol_confirmation_queue` | REPAIR | Offline stub replaced with governed batch composition |
| Source Governor + `pumpswap_pool_account_batch` | REUSE | Already registered on `solana_rpc` |
| Solana JSON-RPC transport | REUSE | One-attempt `getMultipleAccounts` via shared RPC helpers |
| `confirm_pumpswap_pool_from_account` | REUSE | Unchanged validation law |
| exact-market transitions | REUSE | Outcome → state/reason mapping |
| protocol StageBudget | REUSE | 1 op per batch (not per candidate) |
| market re-entry | ADDED | Confirmed set resumes mint-market batch when capacity remains |

## Behavior-to-proof matrix

| Required behavior | Production owner | Exact implementation | Proof | Verdict | Remaining limitation |
|---|---|---|---|---|---|
| Production queue calls governed transport | `process_protocol_confirmation_queue` | Builds governed request `solana_rpc`/`pumpswap_pool_account_batch` via `execute_source_request_with_governor` | `test_production_queue_calls_governed_transport` | PASS | Live endpoint only when no fixture transport is injected |
| One request confirms multiple candidates | `normalize_pumpswap_pool_account_batch_payload` + queue | Single batch addresses → N members | `test_one_batch_confirms_multiple_candidates` | PASS | Cap 100 unique pools/batch |
| Batch cap 100 | `build_ordered_unique_addresses` | `MAX_BATCH_ADDRESSES = GET_MULTIPLE_ACCOUNTS_BATCH_SIZE` | `test_batch_cap_100_enforced` | PASS | Remainder deferred to later batches under stage capacity |
| Duplicate address mapping | `build_ordered_unique_addresses` | Unique pool list; multi-mint share index | `test_duplicate_address_mapping` | PASS | — |
| Exact index mapping | normalize | `zip(addresses, values)` with length equality | `test_mixed_batch_preserves_valid_siblings` | PASS | Count mismatch → shared failure |
| Valid owner+mint pass | `confirm_pumpswap_pool_from_account` | Existing helper | `test_valid_owner_and_mint_pass` | PASS | — |
| Null account local | helper reason `pool_account_not_found` → `ACCOUNT_NOT_FOUND` | map to `EXACT_POOL_NO_MATCH` | `test_null_account_candidate_local` | PASS | — |
| Wrong owner local | `POOL_OWNER_MISMATCH` → `CONTRACT_BLOCKED` | | `test_wrong_owner_candidate_local` | PASS | — |
| Short/invalid data local | `POOL_DATA_UNDECODABLE` | | `test_short_data_candidate_local` | PASS | — |
| Wrong base mint identity | `BASE_MINT_MISMATCH` → `IDENTITY_CONFLICT` | | `test_wrong_base_mint_identity_mismatch` | PASS | — |
| Mixed batch siblings | normalize continues per member | | `test_mixed_batch_preserves_valid_siblings` | PASS | — |
| RPC/envelope/count shared failure | normalize `_failure` + queue marks all members `SOURCE_UNAVAILABLE` | | `test_count_mismatch_*`, `test_rpc_error_*`, `test_shared_failure_marks_all_members_*` | PASS | — |
| Unsupported venues zero transport | queue filters before batch | | `test_unsupported_venues_zero_transport` | PASS | Meteora never activated |
| Confirmed resume market | `eligible_token_supply` post-protocol market batch | | composition + unit wiring | PASS | Requires market capacity + batch factory |
| No forbidden evidence | member payload forces null reserves/age/holder/eligibility | | `test_valid_owner_and_mint_pass` asserts nulls | PASS | Full layout/quote offsets remain unresolved |
| Protocol + six-unit accounting | 1 request/batch, 1 transport, N local validations | | production queue tests | PASS | — |
| No retry / protected capability | one-attempt transport; no holder/lifecycle activation | | static + tests | PASS | — |

## Contract pins adopted

| Pin | Value |
|---|---|
| Solana `getMultipleAccounts` max addresses | **100** (`GET_MULTIPLE_ACCOUNTS_BATCH_SIZE`) |
| Result alignment | `len(result.value) == len(requested_addresses)` or shared failure |
| Encoding / commitment | `base64` / `finalized` |
| PumpSwap owner | `pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA` |
| base_mint law | bytes `[43,75)` via existing `confirm_pumpswap_pool_from_account` |
| Contract version string | `SOLANA_GET_MULTIPLE_ACCOUNTS_PUMPSWAP_BASE_MINT_2026_08_04` |

**Not adopted:** quote-mint offset as eligibility proof, reserve/`virtual_quote_reserves` decoding, full IDL expansion, per-candidate `getAccountInfo` loops.

## Files

| Path | Role |
|---|---|
| `src/printer_v1/sources/pumpswap_pool_account_batch.py` | Adapter, normalize, transport, address mapping |
| `src/printer_v1/discovery/permanent_discovery_availability.py` | Production queue composition |
| `src/printer_v1/discovery/eligible_token_supply.py` | Transport injection + market resume |
| `tests/test_v2_9_8b_governed_pumpswap_account_batch_confirmation.py` | Focused proofs |
| `tests/test_v2_9_8b_permanent_discovery_conversion_repair.py` | Updated protocol queue expectation |

## Verification

```text
.venv/bin/pytest \
  tests/test_v2_9_8b_governed_pumpswap_account_batch_confirmation.py \
  tests/test_v2_9_8b_permanent_discovery_conversion_repair.py \
  tests/test_v2_9_8b_permanent_discovery_availability.py \
  tests/test_v2_9_8b_21_eligible_token_supply_architecture.py \
  tests/test_v2_9_7e_42_direct_migration_discovery.py \
  tests/test_pumpswap_onchain_confirmation.py \
  tests/test_pumpswap_signature_pool_resolution.py \
  tests/test_v2_9_7e_45_holder_reserve_funnel.py \
  -q
→ 143 passed

compileall changed modules → OK
git diff --check → OK
```

No schema migration; no disposable DB integrity change required.

## Hard locks preserved

- Pump exactly-one migration rule unchanged
- Ceiling 30 / reservations 3/2/6/7/8/4 unchanged
- $3,000 floor unchanged
- No Meteora activation, no retries, no ranking/scores
- No Source Governor/Scheduler bypass
- No live providers / authorization / WINDOW_15M
- No retrieval/decisions/BUY/SELL/HOLD/positions/trades/audits/PnL

## Remaining blockers

1. Live re-proof still needs a **new** operator authorization and one-shot attempt.
2. Fresh protocol-confirmed pools still need separate market liquidity evidence (resume path runs Dex batch when capacity/factory available; it does not invent `$3K` proof).
3. Quote-mint / reserve layout decoding remains unresolved by design.
4. Untracked Migration-050 package and `/private/tmp/mp-preclaim` remain preserved.

## Final classification

`V2_9_8B_GOVERNED_PUMPSWAP_ACCOUNT_BATCH_CONFIRMATION_PASS`
