# Governed PumpSwap Account-Batch Confirmation Plan

> Inline execution this session.

**Goal:** Wire `process_protocol_confirmation_queue` to Source-Governed Solana `getMultipleAccounts` so supported fresh Pump-family mint+pool rows get exact PumpSwap owner + base_mint@43 confirmation.

**Architecture:** Reuse `confirm_pumpswap_pool_from_account` and registered `solana_rpc` / `pumpswap_pool_account_batch`. Add normalize + fixture/live transport + queue composition that batches up to 100 pools, maps per-member outcomes into exact-market states, and returns confirmed identities to market validation.

**Tech Stack:** Python 3.12, pytest, existing Source Governor / PumpSwap helpers.

## Owner classification

| Owner | Class |
|---|---|
| `process_protocol_confirmation_queue` | REPAIR (offline stub → real batch) |
| Source Governor + `pumpswap_pool_account_batch` kind | REUSE |
| Solana JSON-RPC `_rpc_post` / measured transport | REUSE |
| `confirm_pumpswap_pool_from_account` | REUSE |
| exact-market transitions | REUSE |
| protocol StageBudget | REUSE (1 op per batch) |
| market re-entry after confirm | MISSING → add |

## Tasks

1. Add `normalize` + transport builder + adapter for `pumpswap_pool_account_batch`
2. Rewrite queue to batch, confirm, transition, return confirmed set
3. eligible_token_supply: pass transport; re-run market for confirmed if capacity
4. Focused tests + closeout + commit

