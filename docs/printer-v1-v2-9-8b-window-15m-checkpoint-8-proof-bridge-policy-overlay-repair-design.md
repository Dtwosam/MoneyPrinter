# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — Proof-Bridge Policy Overlay Repair Design

Date: 2026-08-07

Audit commit: `16ffc7100199efd2881ca9e1e434e847dac814f6`

## Design verdict

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_PROOF_BRIDGE_POLICY_OVERLAY_REPAIR_APPROVED_FOR_OFFLINE_IMPLEMENTATION_ONLY`

## Exact change

In the disposable-owner branch of `operational_memory_factory_command._run_operational_campaign`, build graduated-supply kwargs as:

1. the canonical `OPERATIONAL_GRADUATED_SUPPLY_KWARGS` mapping;
2. overlaid by the disposable owner bridge's fixture dependency kwargs.

Conceptually:

```python
bridge_graduated_supply_kwargs = {
    **OPERATIONAL_GRADUATED_SUPPLY_KWARGS,
    **dict(owner_bridge.graduated_supply_kwargs),
}
```

The fixture overlay wins only for keys it explicitly owns. The proof harness must not copy or redefine canonical operational policy values.

## Why this is the correct owner boundary

`OPERATIONAL_GRADUATED_SUPPLY_KWARGS` already owns ordinary `WINDOW_15M` graduated-supply policy. The C8 bridge owns deterministic dependency injection, not a replacement operational policy.

This keeps the proof on the same permanent operational supply path as normal Printer execution while substituting only approved zero-provider fixture dependencies.

## Regression contract

Add focused coverage that proves:

- normal operational policy keys remain present under a disposable bridge;
- `permanent_availability` remains `True`;
- fixture-owned transport keys are overlaid from the bridge;
- no production discovery module is modified;
- no provider/network execution is required by the test.

Prefer a narrow unit-level boundary test over another campaign execution.

## Money-usefulness contribution

The resulting Checkpoint 8 proof will test the actual permanent candidate-supply architecture intended to feed clean memories, making any eventual proof pass economically meaningful rather than an artifact of a proof-only route.

## What this lane improves

- exact policy parity between ordinary operational supply and disposable C8 composition;
- deterministic fixture dependency injection without policy replacement;
- avoidance of accidental live-provider fallback inside a zero-network proof.

## What this lane still does not unlock

It does not complete Checkpoint 8 and does not authorize a new controlling proof. `WINDOW_1H+`, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, and PnL remain locked.

## Minimum sufficient verification

- targeted new bridge-policy regression;
- relevant existing C8 disposable/public-command tests;
- full focused `tests/test_v2_9_8b_window_15m_checkpoint8_*.py` suite;
- `py_compile` for the changed production command/test modules as applicable;
- `git diff --check`;
- static diff proof that no discovery module changed.

No broad repository regression suite is required.

## Functionality Risks / Setbacks / Efficiency Blockers

- An incorrect merge order could let canonical defaults overwrite deterministic fixture dependencies; fixture overrides must be applied last.
- Duplicating the policy mapping in C8 would create drift; this design forbids duplication.
- Passing offline verification only proves the repaired composition boundary; a later explicit one-shot authorization is still required for runtime proof.