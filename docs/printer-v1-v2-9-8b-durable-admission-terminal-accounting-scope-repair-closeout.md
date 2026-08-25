# Printer V1 / V2-9.8B — Durable-Admission Terminal-Accounting Scope Repair Closeout

Verdict:

`V2_9_8B_DURABLE_ADMISSION_TERMINAL_ACCOUNTING_SCOPE_REPAIR_CLOSEOUT_PASS_READY_FOR_POST_REPAIR_REREADINESS`

Implementation commit:

`58134d98a296543941377be471e3ee551db5d4d9`

Parent design commit:

`2b09b2630c82789b5de623c0be7b1933568be265`

Branch:

`agent/v2-9-8b-consumed-4-2-2-full-operational-run-forensic-audit`

## Closed repair

The implementation is accepted on the exact approved narrow surface:

- `CURRENT_HANDOFF.md`
- `src/printer_v1/operator_cli/operational_memory_factory_command.py`
- `tests/test_v2_9_8b_durable_admission_terminal_accounting_scope_repair.py`

Production behavior now scopes canonical terminal accounting from durable
admitted campaign cycles rather than accounting-registry cardinality.

For exact admitted ordinal `(1,)`, a provisional extra Cycle-2 accounting owner
may be excluded from canonical Lane-4 scope only when durable pre-admission
evidence proves that proposed Cycle 2 is terminal and unconsumed.

For exact admitted ordinals `(1,2)`, registered owner identity must still match
the two admitted cycle IDs exactly and the existing campaign projection / Lane-4
multi-cycle contract remains mandatory.

Terminal reconciliation sealing is limited to durable admitted cycles.
Single-cycle action-local reconciliation is sliced to the admitted cycle.
The post-initialization exception path uses the same durable-admission scope
resolver.

`TerminalClosureError` is imported from its canonical owner, so the intended
fail-closed terminal condition cannot fall through to the prior `NameError`.

## Upstream condition preserved

The consumed run's upstream diagnostic remains:

`HONEST_APPLICATION_VALIDATION_BLOCK:FROZEN_TRACKING_LANE_UNAVAILABLE`

This repair does not alter, bypass, retry, reinterpret, or weaken that block.

The consumed authorization remains historical and non-reusable:

`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260825T105852Z_07d92adf`

No successor is authorized by this closeout.

## Bounded proof

Repair-specific tests:

`7 passed in 0.21s`

The implementation applicator independently proved RED before the production
patch and GREEN after it.

The selected existing focused regression slice is already red on the exact
pre-repair baseline. Closeout re-observed the exact same five node IDs:

- `tests/test_v2_9_8b_four_token_factory_terminal_integration.py::test_real_factory_terminal_path_runs_cycle_phase_then_shared_owner_once[True]`
- `tests/test_v2_9_8b_four_token_standard_four_hour_operational_command.py::CapacityDerivationTests::test_derivation_is_live_not_a_literal`
- `tests/test_v2_9_8b_four_token_standard_four_hour_operational_command.py::CapacityDerivationTests::test_operational_capacity_is_the_derived_contract`
- `tests/test_v2_9_8b_multicycle_campaign_projection_finalization_repair.py::test_full_run_acceptance_does_not_attributeerror_on_readonly_projection`
- `tests/test_v2_9_8b_shared_terminal_pre_lifecycle_factory_integration.py::test_real_factory_opening_failure_records_pre_lifecycle_zero_attempt_shape`

These are documented as pre-existing baseline debt. Per `AGENTS.md`, unrelated
pre-existing failures are not expanded into the current repair lane when
baseline equivalence is proven. They are not represented as passing tests.

No new focused failure appeared and no existing failure disappeared as a side
effect of the repair.

Production source syntax compilation: PASS.

`git diff --check`: PASS.

## DB and immutable consumed-run evidence

Authoritative DB SHA remained:

`2d372c6658819bce6e8e69c83eab1d0baeb799a7b9acddf18cb04b0528e99e95`

No DB mutation, migration, sidecar, provider call, authorization creation,
application rewrite, retry, rerun, resume, restart, or successor occurred in
implementation proof or closeout.

The consumed application's marker/terminal evidence remained immutable.

## Production-path completeness

The repair maps to real production states:

- pre-admission accounting registration remains a real evidence producer;
- durable admitted cycles remain the admission authority;
- exact failed/unconsumed proposed Cycle-2 attempts prove which provisional
  owner may be excluded from canonical admitted-cycle accounting;
- genuine two-cycle admission remains exact `(1,2)`;
- inconsistent owner/admission shapes fail closed.

No test-only final classification was introduced as a production authority.

## Permanent locks

All Printer V1 permanent locks remain unchanged, including Solana-only,
Solana-memecoin-only, paper-only, no live wallet/signing/funds/execution,
no paid API dependency, no scoring/ranking/confidence weighting, no
embeddings/vectors, mandatory Source Governor and Central Scheduler, dirty
memory exclusion, 5m support-only, Cycle 3 locked, longer windows locked,
retrieval locked, and all financial/trading/PnL capabilities locked.

## Exact next permitted action

```text
READ-ONLY POST-DURABLE-ADMISSION TERMINAL-ACCOUNTING SCOPE REPAIR
EXACT-HEAD / WORKTREE / DB REREADINESS GATE
```

No fresh authorization preparation is permitted until that rereadiness gate
passes and creates the exact checkpoint HEAD a future authorization must bind.
