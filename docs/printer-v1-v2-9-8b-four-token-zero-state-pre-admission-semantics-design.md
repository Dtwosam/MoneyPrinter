# Printer V1 V2-9.8B Four-Token Pre-Admission Zero-State Semantics Repair Design

Date: 2026-08-14

## Verdict

`V2_9_8B_FOUR_TOKEN_ZERO_STATE_PRE_ADMISSION_SEMANTICS_DESIGN_PASS_READY_FOR_IMPLEMENTATION`

This design repairs only the canonical four-token pre-consumption zero-state projection for migration-055 pre-admission ownership.

## Baseline

- Repair branch: `agent/v2-9-8b-four-token-pre-admission-zero-state-repair`
- Audit commit: `0212f9c2913e159559aa96a3f002c96144b3d7da`
- Defect classification: `COMMITTED_CODE_DEFECT`

## Design decision

Keep `src/printer_v1/operator_cli/four_token_proof_zero_state_gate.py` as the sole canonical owner of the pre-consumption zero-state projection.

Replace the raw table count with a fail-closed retained-history predicate:

```sql
SELECT COUNT(*)
FROM printer_pre_admission_discovery_attempts
WHERE attempt_state NOT IN (
    'NO_PAIR', 'BLOCKED', 'FAILED', 'CANCELLED', 'CONSUMED'
)
```

This deliberately expresses the states proven safe to retain rather than positively naming only known blockers. Under migration 055 it produces:

- `PLANNED` -> blocking
- `RUNNING` -> blocking
- `PAIR_READY` -> blocking
- `NO_PAIR` -> non-blocking retained history
- `BLOCKED` -> non-blocking retained history
- `FAILED` -> non-blocking retained history
- `CANCELLED` -> non-blocking retained history
- `CONSUMED` -> non-blocking retained history

If an unexpected non-null state becomes possible because future schema semantics change, it is not on the historical allowlist and therefore blocks. Migration identity remains separately pinned to migration 055 by the existing gate.

## Why `PAIR_READY` remains blocking

Migration 055 terminalizes `PAIR_READY` but grants it the only post-terminal transition: `PAIR_READY -> CONSUMED`. The state carries a produced exact pair that has not yet been consumed into cycle ownership. A new bounded proof must not begin while that authority remains unconsumed.

No new cross-table or Scheduler inference is required for this repair; the migration-defined durable attempt state is the canonical state-machine authority, while existing Scheduler zero-state checks remain an independent defence.

## Files

Production modification:

- `src/printer_v1/operator_cli/four_token_proof_zero_state_gate.py`

Focused regression modification:

- `tests/test_v2_9_8b_four_token_proof_zero_state_gate.py`

No migration, wrapper, Scheduler, discovery, Source Governor, factory, campaign, or runtime file is changed by design.

## TDD contract

Before production code changes, add focused disposable-database regressions proving:

1. retained terminal pre-admission states `NO_PAIR`, `BLOCKED`, `FAILED`, `CANCELLED`, and `CONSUMED` project zero blocking pre-admission ownership and remain physically retained;
2. `PLANNED`, `RUNNING`, and `PAIR_READY` project blocking ownership;
3. the existing gate remains read-only;
4. existing zero-state behavior for all other domains remains unchanged.

The RED proof must fail against the raw-count implementation specifically because a retained terminal row projects as blocking.

Then make the one-query production change and rerun the same focused tests GREEN.

## Verification scope

Minimum sufficient verification only:

- focused `tests/test_v2_9_8b_four_token_proof_zero_state_gate.py`;
- nearest four-token one-shot wrapper/pre-consumption test surface if available and runnable without live/source activity;
- Python compilation for the changed production/test modules;
- diff/static inspection confirming only intended files changed during implementation.

No source calls, Printer runtime, proof execution, authoritative DB mutation, authorization creation/consumption, or broad unrelated suite is required for implementation verification.

A broader relevant regression surface may be reserved for repair closeout/pre-live rereadiness if the repository's existing verification path makes it available without widening into runtime.

## Money-usefulness contribution

This repair prevents legitimate historical ownership records from wasting or blocking future one-use proof opportunities, allowing the eventual four-token proof to measure real capacity while preserving forensic history.

## What this design improves

- aligns pre-admission zero-state semantics with migration 055;
- preserves immutable terminal evidence;
- keeps unconsumed `PAIR_READY` authority fail closed;
- avoids changing unrelated ownership layers.

## What this design does not unlock

Implementation PASS will not directly authorize a new four-token proof. Repair closeout must pass, followed by a fresh independent/read-only rereadiness review. Six-token work and all later memory/retrieval/paper-trading capabilities remain locked.

## Functionality Risks / Setbacks / Efficiency Blockers

- Treating `PAIR_READY` as non-blocking would weaken ownership safety; this design explicitly forbids that.
- Using `IN ('PLANNED','RUNNING','PAIR_READY')` alone would be less fail closed against future unexpected states; the retained-history allowlist avoids that weakness.
- Adding Scheduler-dependent joins would duplicate an existing independent defence and increase coupling without solving additional proven behavior.
- A migration change is unnecessary and would expand the risk surface.

## Implementation stop condition

Stop implementation if focused RED does not demonstrate the raw-count defect, if migration-055 fixture semantics cannot represent the designed state classifications, or if fixing the test requires widening production ownership beyond the canonical zero-state query.