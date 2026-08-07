# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — DTW-49 Holder Coverage Transport-Identity Projection Repair Closeout

Date: 2026-08-07

Linear: `DTW-49`

Design V2 HEAD: `80e924c464e5c7304ee6124a097e166d4502edfd`

Implementation tip before closeout: `aed188ce14ca0584b3d09d315e1ee067475c5225`

Verdict:

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_DTW49_HOLDER_COVERAGE_TRANSPORT_IDENTITY_PROJECTION_REPAIR_OFFLINE_PASS`

## Proven defect

The consumed post-DTW48 C8 attempt stopped before lifecycle at `CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH`.

DTW-49 proved that holder persistence declared truthful per-request transport counts but dropped exact `transport_identity_keys` before campaign reconciliation. This is not a governed-request-versus-transport-count defect and does not justify changing PumpSwap multi-transport accounting, budgets, ceilings, Source Governor, Central Scheduler, six-unit validation, or campaign acceptance.

## Deterministic RED

At design HEAD `80e924c464e5c7304ee6124a097e166d4502edfd`, the dedicated regression was materialized without changing production code and failed on the missing holder coverage transport-identity-key contract.

Classification:

`DTW49_HOLDER_COVERAGE_TRANSPORT_IDENTITY_KEYS_DROPPED_RED_CONFIRMED`

No provider/network access, Printer runtime, authoritative DB, or controlling proof was used.

## Repair

The implementation carries canonical per-request keys only from the real normalized holder execution payload.

It also makes lawful zero-transport coverage explicit with `transport_identity_keys=[]` and clears count/keys together on exact-identity accounting failure.

Exact implementation files:

1. `src/printer_v1/operator_cli/holder_reliability_budget_control.py`
2. `tests/test_v2_9_8b_window_15m_checkpoint8_holder_coverage_transport_identity.py`

No request count, transport count, budget, stage ceiling, provider transport, Scheduler, Source Governor, six-unit, memory, retrieval, decision, position, trade, audit, or PnL policy was weakened.

## Offline GREEN

- changed-file `py_compile`: PASS
- dedicated DTW-49 regression: `2 passed`
- existing C8 real-consumer compatibility: `9 passed`
- complete focused C8 suite: `102 passed`
- exact two-file implementation manifest: PASS
- `git diff --check`: PASS
- provider/network execution: NONE
- controlling C8 proof: NONE

## Money-usefulness contribution

The repair preserves holder provenance from governed execution through campaign reconciliation, so truthful holder evidence can reach the 15-minute lifecycle gate without losing the exact transport ownership needed for trustworthy memory.

## What this improves

- exact per-request holder transport ownership
- truthful request/transport reconciliation
- holder-stage evidence continuity into lifecycle readiness
- focused regression coverage for both nonzero and lawful zero transport

## What remains locked

This closeout does not authorize another Checkpoint 8 proof, operational `WINDOW_15M` memory growth, provider/network access, authoritative DB use, `WINDOW_1H+`, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.

Checkpoint 8 remains open pending independent DTW-49 review/readiness and any later separately authorized one-shot controlling proof.

## Functionality Risks / Setbacks / Efficiency Blockers

1. A later C8 attempt may expose a new downstream blocker; preserve it and open a new narrow lane rather than rerun.
2. Partial holder persistence remains fail-closed; no unproven identity keys were fabricated.
3. Request count and transport-operation count remain intentionally independent.
4. Full end-to-end C8 acceptance is still unproven by this offline repair.
