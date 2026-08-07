# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — Four-Reserve Protocol Budget Audit

Date: 2026-08-07

Status: `V2_9_8B_WINDOW_15M_CHECKPOINT_8_FOUR_RESERVE_PROTOCOL_BUDGET_AUDIT_BLOCKED_PENDING_DETERMINISTIC_RED`

Baseline/design HEAD: `760031aea4c3edbb963e421b8bd05b60e2f37bda`
Linear: `DTW-47`

## Trigger

The DTW-47 deterministic offline RED reproduced the consumed defect exactly:

- `DIRECT_PUMP_EVIDENCE_MISSING:5aNJBy3n3AjsGZ2qvQFKfV6BhKSTQU6MXxN2sjGu8nei`
- zero network attempts
- no controlling proof

While preparing the approved four-file repair, forward static inspection found a second blocker in the same permanent eligible-supply path that would be reached only after expanding the C8 deterministic supply from two to four direct candidates.

## Static contract evidence

Permanent availability raises the eligible reserve requirement to at least four: two selected tokens plus one fully eligible alternate per slot.

The active operational supply policy permits up to five direct migration candidates per cycle.

The direct migration owner uses one governed finalized signature-page request, then for each direct candidate one transaction request and one governed PumpSwap verification request.

Therefore four direct candidates produce:

- 1 signature-page request;
- 4 transaction requests;
- 4 PumpSwap verification requests;
- 9 direct-discovery governed requests total.

In the permanent eligible-supply loop, `protocol_calls` is currently derived as:

```python
max(0, source_operation_ledger.source_requests - 1)
```

For four direct candidates this yields `8`.

`StageBudget.permanent_discovery_default()` reserves only `7` operations for `protocol_confirmation`. Earlier stages are not guaranteed to provide borrowable residual at that point. A direct four-candidate C8 fixture therefore appears capable of stopping at `DISCOVERY_OPERATION_BUDGET_EXHAUSTED` before the intended market/admission path.

## Classification

This is not evidence that the reserve law should be weakened.

It is also not yet approval to alter stage reservations or accounting attribution.

The static mismatch must first be reproduced deterministically offline because changing operation attribution or stage-budget ownership is a production accounting change and exceeds the current DTW-47 four-file design surface.

## Required next step

Run one deterministic, zero-network, no-sentinel offline RED that reuses the prepared C8 disposable composition but temporarily supplies four deterministic candidates in-process only. It must not edit repository files.

The RED must establish whether the real permanent supply path reaches the predicted budget terminal before source-specific admission.

If reproduced, return to design before implementation and define the smallest accounting-correct repair. Do not raise ceilings or weaken the four-reserve requirement merely to make C8 pass.

## Locks

No controlling proof, provider/network access, authoritative DB, GitHub Actions, operational memory growth, `WINDOW_1H+`, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL is authorized.

## Money-usefulness contribution

Avoids repairing only the first exception while leaving a deterministic permanent-supply accounting blocker that would prevent a resilient four-member reserve from reaching the two-token 15m learning path.

## What this improves

- forward-readiness accuracy;
- source-operation budget correctness review;
- protection against repeated one-shot proof consumption on sequential deterministic blockers.

## What this still does not unlock

Nothing operational. DTW-47 remains audit/design blocked pending deterministic RED.

## Functionality Risks / Setbacks / Efficiency Blockers

1. Four-reserve fixture expansion can increase direct protocol request count above the current stage reservation.
2. Raising the reservation without proving attribution would weaken budget ownership discipline.
3. Keeping only two direct fixture candidates would fail to exercise the active four-reserve production contract.
4. A new controlling proof before resolving this mismatch would risk consuming another attempt on a deterministic offline-reproducible blocker.
