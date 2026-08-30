# Printer V1 V2-9.8B Token-Local Source-Failure Terminalization Repair

## Audit / readiness

Baseline: `ba75c76b16cf1b5a2b44ec27822733e161b10abc` on `governance/v2-9-8b-post-reconciliation-readiness-closeout`.
Repair branch: `repair/v2-9-8b-token-local-terminalization`.

Aug-30 retained evidence establishes one legitimate token-local source failure in Cycle 1 / slot 1 at `t1_snapshot_10`: DexScreener transport timeout followed by the single governed GeckoTerminal fallback transport timeout. The step/job failed and the affected token's remaining work was cancelled. Cycle 2 nevertheless completed all lifecycle Scheduler work and both of its WINDOW_15M windows were CLEAN_PROMOTED. Shared finalization later raised `FourTokenFactoryAdapterError: incomplete cycle cannot consume a completion stop cause` after the factory run persisted `COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED`.

Current production inspection establishes the missing state transition: the generic token-local failure path in `one_command_15m_factory.py` terminalizes owned WINDOW_1H and WINDOW_4H lifecycles, but an owned WINDOW_15M SNAPSHOT failure only fails the step/job and cancels that token's pending jobs. Its campaign WINDOW_15M / token-slot state can therefore remain active when the queue drains.

Current Lane-4 bounded proof is authoritative for the required semantics: a token with `TOKEN_LOCAL_FAILURE` does not fail its peer token or unrelated cycle; the affected cycle may still derive `TERMINAL_SUCCESS`, and the two-cycle aggregate remains `TERMINAL_SUCCESS` when all other owned terminal evidence is lawful.

Classification: `COMMITTED_CODE_DEFECT`.

## Root defect

The production first-15m token-local failure path does not reconcile the exact owned campaign WINDOW_15M and token slot to a terminal token-local failure disposition. Queue exhaustion can therefore occur with canonical cycle accounting still `ACTIVE_INCOMPLETE`. Because the factory control loop uses `COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED` as its neutral/no-shared-stop sentinel, shared finalization then encounters an incomplete cycle plus a completion stop cause and correctly fails closed.

The adapter guard is not defective and must remain unchanged.

## Design

Add one narrow first-15m terminalization operation at the existing token-local failure boundary.

For a failed owned WINDOW_15M lifecycle step:

1. Resolve the exact campaign scheduler-work ownership for that scheduler job.
2. Resolve its exact campaign WINDOW_15M and token slot.
3. Transition only that owned WINDOW_15M to the existing approved blocked terminal state and only that token slot to the existing approved token-local failed state, preserving the exact failure cause.
4. Do not modify the peer token, peer cycle, Source Governor, Central Scheduler, retry policy, or provider order.
5. Preserve idempotent/fail-closed compare-and-update behavior and reject identity/state ambiguity.
6. Continue the factory loop so unrelated token/cycle work drains normally.
7. Allow canonical cycle accounting to derive terminal truth. Do not manufacture cycle/campaign success in the failure handler.
8. Only canonical terminal accounting may convert the neutral completion sentinel into durable shared completion truth.

Existing WINDOW_1H/WINDOW_4H terminalizers remain unchanged. `four_token_factory_adapter.py` remains unchanged.

## Required RED proof

A disposable two-cycle production-seam test must model:

- Cycle 1 slot 1 owned WINDOW_15M SNAPSHOT fails token-locally.
- The failed step/job is terminal and its remaining token jobs are cancelled.
- Cycle 1 slot 2 reaches its lawful terminal state.
- Cycle 2 reaches two lawful terminal WINDOW_15M states.
- No campaign-global fault exists.

Baseline must reproduce the defect: Cycle 1 remains incomplete and reconciliation encounters the completion-stop guard.

## Required GREEN proof

After the minimal patch:

- failed token outcome is `TOKEN_LOCAL_FAILURE`;
- peer token is not failed;
- Cycle 1 derives `TERMINAL_SUCCESS` under the current Lane-4 contract;
- Cycle 2 remains `TERMINAL_SUCCESS`;
- aggregate derives `TERMINAL_SUCCESS`;
- no `incomplete cycle cannot consume a completion stop cause` exception;
- exact source-failure cause remains attributable to the failed token;
- all-success control remains unchanged;
- existing genuine campaign-global failure control remains unchanged;
- zero provider calls, zero authoritative-DB writes, zero retry/rerun/resume/restart/successor.

## Locks

No DexScreener retry. No GeckoTerminal retry. No third provider. `automatic_retries=0`. No Source Governor bypass/change. No Central Scheduler bypass/change. No migration/schema change. No authoritative DB repair. No live campaign or authorization. No retrieval/financial/12h/24h activation.

## Design verdict

`PASS_FOR_TDD_IMPLEMENTATION` — implement only after a focused RED reproduction on disposable state.