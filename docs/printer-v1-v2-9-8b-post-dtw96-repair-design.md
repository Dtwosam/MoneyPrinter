# Printer V1 — V2-9.8B Post-DTW96 Permanent Supply Truth Repair Design

## Verdict

`V2_9_8B_POST_DTW96_PERMANENT_SUPPLY_TRUTH_REPAIR_DESIGN_COMPLETE`

## Baseline

Audit closeout: `73abee044d7e43553d265f6f3f88f75b8f7fba3c`

This design is specification-only. It does not authorize implementation, source execution, Scheduler runtime, memory generation, WINDOW_15M, or a fresh one-use authorization.

## Problem statement

DTW96 proved four connected defects while all safety gates still failed closed:

1. GeckoTerminal reconciliation fallback I/O can occur before the shared reconciliation-stage budget is checked/charged.
2. Permanent outer candidate-supply readiness can become true while the canonical persistent supply owner is not ready at the required four-deep reserve.
3. `LAWFUL_WORK_REMAINING_WITH_CAPACITY` can be masked by candidate-local tracking exclusions in shortage classification.
4. A persisted exhaustion certificate is omitted from the later permanent pre-lifecycle terminal-report projection.

The repair must preserve the existing 30-operation permanent discovery ceiling and stage reservations `3/2/6/7/8/4`, `MINIMUM_FREEZE_DEPTH=4`, active two-slot selection, tracking exclusions, Source Governor, Central Scheduler, and all financial/retrieval locks.

## Design 1 — enforce reconciliation capacity before fallback I/O

### Owner

`src/printer_v1/discovery/permanent_discovery_availability.py`

### API change

Extend `run_dexscreener_batch_market_resolution(...)` with one explicit optional integer input representing the maximum GeckoTerminal reconciliation fallbacks permitted for this invocation, for example:

`max_geckoterminal_fallbacks: int | None = None`

Semantics:

- `None` preserves existing non-permanent/test callers that do not supply an external stage-budget cap.
- an integer must be non-negative;
- effective fallback limit is `min(6, unresolved_count, max_geckoterminal_fallbacks)` when supplied;
- `0` means zero GeckoTerminal fallback source requests;
- the cap is checked before entering the fallback loop and therefore before Source Governor execution / provider I/O;
- suppressed excess unresolved mints remain unresolved and are reported; no retry, borrowing, provider substitution, or fabricated evidence occurs.

The report continues to expose actual `calls_by_stage["reconciliation"]` based only on requests that actually occurred.

### Caller

`src/printer_v1/discovery/eligible_token_supply.py`

Immediately before each permanent market-owner call:

- capture `reconciliation_offer = stage_budget.available("reconciliation")`;
- pass that value as the fallback cap;
- after return, read the actual reconciliation-call count;
- fail closed if actual calls exceed the offered cap;
- charge exactly the actual count to `stage_budget.consume("reconciliation", actual)`;
- never issue fallback I/O and only then discover capacity is unavailable.

Apply the same rule to any protocol-resume market call that enables reconciliation; if that call deliberately disables GeckoTerminal fallback today, retain zero fallback behavior.

Do not alter stage reservations or transfer capacity backward.

## Design 2 — permanent readiness must respect persistent owner truth

### Owner

`src/printer_v1/operator_cli/graduated_supply_front_door.py`

For `permanent_availability=True`, outer `GraduatedSupply.ready` must require both:

- `persistent.ready is True`; and
- the existing two-candidate selection/supply conditions.

The ordinary two-candidate selector remains the neutral chooser of the two active slots; it must not be allowed to promote an incomplete 3/4 permanent reserve to READY.

For non-permanent callers, preserve existing readiness behavior.

When persistent readiness is false, preserve the persistent shortage/certificate diagnostics even when two candidates happen to be selectable.

## Design 3 — campaign-level lawful-work truth outranks tracking shortage masking

### Owner

`src/printer_v1/discovery/eligible_token_supply.py`

Shortage precedence must preserve campaign-level continuation truth:

- source availability/evidence failures retain their existing precedence;
- true flat/stage budget exhaustion and duration exhaustion retain their existing truthful classifications;
- when `last_stop_reason == "LAWFUL_WORK_REMAINING_WITH_CAPACITY"`, classification must remain `DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE` and must not be overwritten merely because one or more candidate tracking dispositions are ineligible;
- `TRACKING_STATE_CAPACITY_BLOCKED` remains valid only when tracking-state exclusions are the actual reason capacity cannot be reached after no stronger campaign-level continuation defect applies.

Tracking dispositions and counts remain fully reported as candidate-local diagnostics.

No tracking state becomes newly eligible under this repair.

## Design 4 — propagate the existing exhaustion certificate

### Owner

`src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`

The later permanent-memory pre-lifecycle terminal path must copy the already-owned:

`supply_diagnostics["exhaustion_certificate"]`

into `terminal_reporting["exhaustion_certificate"]` and any directly corresponding blocked-supply projection consumed by the command/report assembler.

Rules:

- never reconstruct a new certificate;
- never mutate the persisted certificate;
- preserve certificate identity and payload exactly as supplied by `GraduatedSupply.diagnostics`;
- no certificate is required on a ready path;
- `None` remains truthful when the persistent owner produced none.

## Minimum sufficient TDD proof

RED must be demonstrated before production modification.

Focused tests must prove:

1. **zero reconciliation capacity**
   - canonical DexScreener market request may run when otherwise due;
   - zero GeckoTerminal reconciliation fallback requests occur;
   - actual reconciliation charge is zero.

2. **partial reconciliation capacity**
   - with two units available and more than two unresolved mints, at most two fallback requests occur;
   - actual reported reconciliation calls equal the exact charge;
   - no third fallback transport occurs.

3. **caller invariant**
   - actual fallback calls greater than the offered reconciliation capacity fail closed rather than silently overrun accounting.

4. **persistent readiness truth**
   - persistent result not ready at 3/4 plus an ordinary selector capable of choosing two still yields outer permanent `ready=False`;
   - non-permanent two-candidate behavior remains unchanged.

5. **shortage precedence**
   - `LAWFUL_WORK_REMAINING_WITH_CAPACITY` plus tracking-ineligible candidates yields `DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE`;
   - a genuine tracking-only capacity blocker still yields `TRACKING_STATE_CAPACITY_BLOCKED`.

6. **certificate propagation**
   - the later permanent pre-lifecycle blocked path carries the exact supplied exhaustion certificate into terminal reporting;
   - no synthetic or altered certificate is produced.

7. **locked invariants**
   - `MINIMUM_FREEZE_DEPTH == 4`;
   - active selection capacity remains 2;
   - existing `STAGE_RESERVATIONS` remain exactly `3/2/6/7/8/4`;
   - no Source Governor/Scheduler bypass or financial/retrieval activation is introduced.

Use disposable/offline fixtures only. No authoritative database access and no source/network runtime are required for the focused proof.

## Implementation boundary

Expected production files are limited to:

- `src/printer_v1/discovery/permanent_discovery_availability.py`
- `src/printer_v1/discovery/eligible_token_supply.py`
- `src/printer_v1/operator_cli/graduated_supply_front_door.py`
- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`

Tests may add focused files under `tests/`.

Any need to change stage reservations, migrations/schema, tracking rules, liquidity floor, freeze depth, Source Governor, Central Scheduler, holder semantics, migration-registry policy, or financial/retrieval code is outside this design and must stop for a new audit/design decision.

## Money-usefulness contribution

This repair lets the bounded discovery budget be spent according to its existing stage contract instead of issuing reconciliation calls that are already unaffordable. It also makes readiness and terminal evidence accurately distinguish a true bounded shortage from an architectural continuation defect, improving the reliability of the memory-growth system without relaxing evidence quality.

## What this lane improves

- pre-I/O source-budget enforcement;
- persistent four-deep reserve truth;
- honest shortage classification;
- durable blocked-run evidence/reporting.

## What this lane still does not unlock

It does not unlock another live proof by itself, WINDOW_1H+, retrieval, paper decisions, BUY/SELL/HOLD, paper positions, trade events, paper trade audits, or PnL. A focused implementation proof, closeout, rereadiness, and fresh one-use authorization review must occur first.

## Functionality Risks / Setbacks / Efficiency Blockers

- Capping fallbacks after I/O would not repair the defect.
- Raising reconciliation or total operation ceilings would hide the defect and is forbidden.
- Lowering four-deep reserve safety would weaken the memory-observation contract and is forbidden.
- Making tracking exclusions globally weaker would create unrelated activation risk.
- Reconstructing certificates in reporting could create two authorities; only propagation is allowed.
- Broad regression suites are unnecessary for implementation proof; use focused tests plus compile/diff checks, reserving broader verification for closeout/rereadiness.

## Stop condition

After this design is frozen, proceed only to RED-focused TDD. Do not create a fresh authorization or run Printer until implementation, focused proof, closeout, and rereadiness all pass.
