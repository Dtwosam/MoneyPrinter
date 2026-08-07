# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — Measured Market Fixture Repair Closeout

Date: 2026-08-07

DTW-46: `Checkpoint 8 measured market fixture identity failure audit and repair`

Design HEAD: `e1c29324c923e4c5d2391a8e39b5ce51c4022886`

Repair commit: `275a9731556b889237895d4a2a808a057a144a1e`

## Closeout verdict

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_MEASURED_MARKET_FIXTURE_REPAIR_OFFLINE_PASS`

## Scope completed

The approved proof-fixture-only repair was implemented at the four permanent market-source fixture seams:

- DexScreener fresh profiles: `DEXSCREENER_DISCOVERY` / `dexscreener_fresh_profiles`.
- DexScreener mint batch: `MINT_MARKET_BATCH` / `candidate_market_batch`.
- GeckoTerminal fresh nomination: `FRESH_POOL_NOMINATION` / `geckoterminal_new_pool_discovery`.
- GeckoTerminal reconciliation: `MINT_MARKET_BATCH` / `candidate_market_batch`.

Each repaired fixture payload now carries exactly one serialized measured transport identity while preserving the existing fixture response body and canonical adapter path.

## Deterministic RED

The isolated local worktree was pinned exactly to design HEAD `e1c29324...` and used the existing project Python environment.

Before implementation, the focused regression failed with:

`printer_v1.sources.measured_transport.MeasuredTransportError: TRANSPORT_IDENTITIES_MISSING`

The frozen payload showed `transport_operations_used=1` and `transport_operation_identities=()`.

This reproduced the exact DTW-46 defect before repair.

## GREEN proof

After the approved two-file repair:

- changed-file `py_compile`: PASS;
- focused real-consumer compatibility file: `6 passed`;
- full focused `tests/test_v2_9_8b_window_15m_checkpoint8_*.py`: `97 passed`;
- process-local `Checkpoint8NetworkTripwire`: zero attempts;
- `git diff --check`: PASS;
- exact changed-file manifest: PASS.

Exact changed files:

1. `scripts/v2_9_8b_checkpoint8_controlling_public_composition_proof.py`
2. `tests/test_v2_9_8b_window_15m_checkpoint8_real_consumer_compatibility.py`

No `src/printer_v1/` production code changed.

## Preserved boundaries

No Printer runtime, provider/network contact, authoritative DB access or mutation, authorization creation/consumption, GitHub Actions repair workflow, or Checkpoint 8 controlling proof was used for this repair.

No Source Governor, Central Scheduler, discovery owner, provider transport, production accounting owner, migration, or capability lock changed.

`WINDOW_1H+`, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, and PnL remain locked.

## Money-usefulness contribution

The repair lets permanent-market fixture evidence exercise the same measured transport identity contract required by six-unit accounting, so future authorized Checkpoint 8 evidence can reach meaningful two-token observation without being blocked by synthetic fixture metadata loss.

## What this lane improves

Checkpoint 8 proof-fixture fidelity and measured-source accounting compatibility for permanent DexScreener and GeckoTerminal market evidence.

## What this lane does not unlock

This closeout does not authorize another Checkpoint 8 controlling proof and does not complete Checkpoint 8.

A separate independent review of this closeout is required before any later operator authorization decision.

## Functionality Risks / Setbacks / Efficiency Blockers

- A later authorized proof may expose a different downstream seam; that does not pre-authorize unrelated repair.
- Measured identities must remain explicit fixture/transport evidence; no production fallback or inferred accounting identity was added.
- Checkpoint 8 remains open until a future separately authorized controlling campaign returns `CAMPAIGN_PASS` and its required inspection/closeout gates pass.
