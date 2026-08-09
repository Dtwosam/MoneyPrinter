# Printer V1 — V2-9.8B Post-DTW96 Permanent Supply Readiness Audit Closeout

## Verdict

`V2_9_8B_POST_DTW96_PERMANENT_SUPPLY_READINESS_AUDIT_PASS_REPAIR_REQUIRED`

## Scope

Audit/readiness only. No source execution, Scheduler runtime, memory generation, authorization creation, lifecycle start, retrieval, paper decision, position, trade event, audit, or PnL work was performed.

## Controlling evidence

DTW96 authorization `V2_9_8B_WINDOW_15M_AUTH_20260809T095642Z` is permanently consumed.

DTW96 stopped pre-lifecycle with `PRE_LIFECYCLE_DISCOVERY_SELECTION_COVERAGE_INSUFFICIENT` and `lifecycle_started=false`.

Read-only authoritative evidence proves:

- 48 confirmed inventory pools existed.
- 10 identities were evaluated in one persistent-discovery round.
- 3 candidates were `ELIGIBLE_FRESH` / memory-observation eligible.
- permanent availability required reserve depth 4.
- 7 identities were lawfully excluded by tracking state: 2 `DUPLICATE_ACTIVE_TRACKING`, 5 `TERMINAL_TRACKING_STATE`.
- the durable exhaustion certificate exists with `eligible_reserve_count=3`, `required_eligible_capacity=4`, `provider_failures=0`, `channels_unavailable=[]`, `source_operations_remaining=19`, and `last_reason_discovery_could_not_continue=LAWFUL_WORK_REMAINING_WITH_CAPACITY`.
- the immutable terminal report drops that certificate and projects `exhaustion_certificate=null`.

## Exact defects

### 1. Pre-I/O reconciliation stage-budget enforcement defect

The permanent stage reservations remain:

- intake: 3
- market_batching: 2
- reconciliation: 6
- protocol_confirmation: 7
- holder_safety: 8
- final_refresh_handoff: 4

DTW96 request order proves all six reconciliation units were first consumed by the bounded unknown-liquidity backup (`liq-backup-*`, requests 2079–2084). The later canonical DexScreener mint batch (`mint-batch-r1`, request 2086) then emitted six GeckoTerminal reconciliation fallback requests (2087–2092).

The current control flow allows those fallback source requests to execute before the caller attempts to charge their reconciliation-stage capacity. The post-call charge therefore discovers no remaining reconciliation capacity and stops the persistent loop. This is a pre-I/O enforcement defect: stage capacity must be checked/capped before governed fallback source requests can be issued.

The repair must not raise the 30-operation ceiling or any stage reservation.

### 2. Permanent supply readiness projection defect

`run_persistent_eligible_token_supply()` raises permanent required reserve capacity to at least 4 and correctly returns not-ready below that depth. `build_graduated_supply()` subsequently recomputes readiness from the ordinary two-candidate selector and can project READY when two candidates can be selected from a 3/4 reserve.

Permanent outer readiness must not become true when `persistent.ready` is false.

### 3. Shortage precedence defect

The persistent owner records `LAWFUL_WORK_REMAINING_WITH_CAPACITY`, but later shortage precedence can overwrite the associated architecture-false condition with `TRACKING_STATE_CAPACITY_BLOCKED` merely because some tracking dispositions are ineligible.

Tracking-state exclusions remain valid candidate-local facts, but they must not mask the stronger campaign-level fact that lawful discovery work remained.

### 4. Exhaustion-certificate/report projection defect

The authoritative DB contains the DTW96 exhaustion certificate, while terminal-summary and immutable terminal campaign report project it as null.

Blocked-supply reporting must preserve the authoritative certificate identity/payload without changing its ownership or persistence semantics.

## Non-defects / rules preserved

- `MINIMUM_FREEZE_DEPTH=4` is intentional and remains unchanged.
- active token capacity remains exactly 2.
- tracking exclusions are not relaxed.
- no migration-registry confirmation is reintroduced for market-present candidates.
- PumpSwap protocol/account validation remains required.
- no Source Governor or Central Scheduler bypass is permitted.
- no new source, provider, ranking, score, confidence, weighting, embedding, or paid API is permitted.

## Money-usefulness contribution

The repair prevents bounded discovery capacity from being wasted after only one market round, allowing Printer to search the already-governed inventory for enough clean observation candidates while preserving strict evidence and stage budgets. Accurate readiness and exhaustion reporting also prevents operators from mistaking an architectural stop for true token scarcity.

## What this audit improves

It identifies the exact DTW96 failure mechanism and separates candidate-local tracking exclusions from campaign-level discovery continuation truth.

## What this audit does not unlock

No runtime, fresh authorization, WINDOW_15M rerun, WINDOW_1H+, retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events, audits, or PnL.

## Proof required after implementation

Minimum sufficient offline proof must establish:

1. reconciliation fallback source calls are capped before I/O by the remaining reconciliation-stage capacity;
2. zero remaining reconciliation capacity produces zero new fallback source calls;
3. the second protected market batch remains available when the first market round leaves reserve depth below 4 and lawful inventory remains;
4. permanent outer readiness cannot become true while `persistent.ready` is false;
5. `LAWFUL_WORK_REMAINING_WITH_CAPACITY` is not masked by tracking-state shortage classification;
6. the persisted exhaustion certificate is propagated to blocked/terminal reporting;
7. existing four-deep freeze, two-slot activation, Source Governor, Scheduler, accounting, and financial locks remain unchanged.

## Functionality Risks / Setbacks / Efficiency Blockers

- Moving budget enforcement after I/O again would preserve the defect.
- Giving reconciliation more capacity would hide rather than repair the defect.
- Lowering reserve depth 4 to 2 would weaken the approved observation-surplus safety contract.
- Treating all tracking exclusions as the root cause would continue to mask lawful unexplored discovery work.
- Broad regression work is unnecessary before implementation; focused TDD is sufficient, with broader checks reserved for closeout/rereadiness.

## Next permitted step

Design/specification of the narrow DTW96 repair. No new authorization or live proof is permitted before design, implementation, bounded offline proof, closeout, and rereadiness pass.
