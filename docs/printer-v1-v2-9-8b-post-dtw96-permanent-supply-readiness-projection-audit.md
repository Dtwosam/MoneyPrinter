# Printer V1 V2-9.8B post-DTW96 permanent supply readiness projection audit

## Verdict

`V2_9_8B_POST_DTW96_PERMANENT_SUPPLY_READINESS_PROJECTION_AUDIT_PASS_COMMITTED_CONTRACT_DRIFT_CONFIRMED`

Audit only. No source fetching, runtime, authoritative DB mutation, memory generation, authorization, retrieval, paper decision, position, trade, audit, or PnL work was performed by this lane.

## Baseline

- Consumed-attempt closeout: `4f0f0a28cef2fbaebcd9e7da57b5fcedeaf81843`
- Runtime code identity audited: `00679edb624665d8dc1952ea7d6906324cc1d956`
- Consumed authorization: `V2_9_8B_WINDOW_15M_AUTH_20260809T095642Z`

## Source-stack alignment

This audit preserves the active Printer V1 source stack and the active V2 memory-growth build order. It does not lower safety gates to force a campaign through. The four-deep permanent observation reserve remains a safety/continuity contract; active token capacity remains exactly two.

## Runtime evidence

The consumed DTW96 terminal evidence reported:

- terminal: `PRE_LIFECYCLE_DISCOVERY_SELECTION_COVERAGE_INSUFFICIENT`
- shortage: `TRACKING_STATE_CAPACITY_BLOCKED`
- 10 candidates observed and validated
- 3 `ELIGIBLE_FRESH` market-eligible candidates
- 2 `DUPLICATE_ACTIVE_TRACKING` exclusions
- 5 `TERMINAL_TRACKING_STATE` exclusions
- active token capacity: 2
- lifecycle started: false
- accounting complete and clean terminal cleanup

## Committed permanent supply contract

`src/printer_v1/discovery/eligible_token_supply.py` owns the persistent multi-round supply loop.

For `permanent_availability=True`, it explicitly raises `required_token_capacity` to at least 4. The comment defines the intent as two selected candidates plus one fully eligible alternate per slot. This is reserve capacity only and does not authorize four active tokens.

The same owner continues bounded evaluation while `len(campaign_eligible) < required_token_capacity`. If it ends below the required capacity, `ready` is false and the under-capacity branch creates and persists an `ExhaustionCertificate`. Tracking-state exclusions are a defined shortage classification after source, budget, and duration failures are ruled out.

Therefore the permanent supply owner is internally consistent with the four-deep freeze contract.

## Confirmed projection defect

`src/printer_v1/operator_cli/graduated_supply_front_door.py::build_graduated_supply()` passes its caller-facing `required_token_capacity` into the persistent supply owner. The ordinary operational caller leaves that value at 2; the persistent owner upgrades it internally to 4 for permanent availability.

After the persistent owner returns, `build_graduated_supply()` does not gate its own readiness on `persistent.ready`.

Instead it:

1. takes the returned eligible reserve;
2. runs the canonical neutral two-candidate selector;
3. builds `supply` from the two selected identities; and
4. sets outer readiness from `authority.ready` and `len(supply) == required_token_capacity` using the outer value 2.

This permits the following contradictory state:

- persistent permanent supply: 3/4, `ready=False`, shortage/exhaustion truth present;
- outer two-candidate projection: two candidates selectable, therefore `ready=True`;
- downstream permanent memory freeze: 3/4, `coverage_blocker=True`, therefore handoff blocked.

DTW96 matches this shape exactly.

### Root cause

Permanent reserve readiness and active two-slot selection readiness are different contracts, but the outer composition currently collapses them into one boolean and lets two-slot readiness override persistent reserve failure.

The downstream freeze-depth guard correctly failed closed and prevented lifecycle start. The defect is therefore an upstream readiness-projection contradiction, not a reason to weaken the downstream guard.

## Exhaustion-certificate reporting finding

The persistent under-capacity path is designed to create and persist an `ExhaustionCertificate`, and `build_graduated_supply()` copies that certificate into `diagnostics["exhaustion_certificate"]` when present.

The retained terminal extraction for DTW96 showed `blocked_supply.exhaustion_certificate: null` / no certificate in the surfaced blocked-supply projection. Static code therefore establishes a reporting question but not yet whether persistence itself failed.

Minimum sufficient next audit evidence: read-only query of `printer_discovery_exhaustion_certificates` for the exact DTW96 campaign/execution plus inspection of the terminal-report projection path. No runtime is needed.

## Safest repair direction, not yet authorized

If the durable exhaustion evidence confirms the expected persistent shortage, the narrow design should preserve both contracts separately:

- permanent supply readiness must remain false unless `persistent.ready` is true;
- two-slot selector readiness may describe which two identities would be selected only after the permanent reserve contract is satisfied;
- outer `GraduatedSupply.ready` must never upgrade a persistent permanent-supply failure;
- exhaustion-certificate/shortage truth must remain visible in the final blocked terminal report;
- four-deep reserve, two active slots, tracking exclusions, Source Governor, Central Scheduler, and all financial/retrieval locks remain unchanged.

Do not lower `MINIMUM_FREEZE_DEPTH` from 4 to 2 and do not reopen terminal tracking rows merely to force capacity.

## Money-usefulness contribution

Correct readiness truth prevents Printer from spending one-use campaign authorizations and source budget on a lifecycle that cannot lawfully pass its reserve-depth handoff. It preserves alternate capacity and diversity before committing the two active 15m slots, improving the chance that bounded collection produces usable memory rather than another pre-lifecycle terminal.

## What this lane improves

- Identifies the exact permanent-supply versus two-slot readiness semantic drift.
- Protects the valid four-deep reserve safety rule from being incorrectly treated as the problem.
- Narrows the next proof to one read-only certificate check and one report-projection inspection before any design or implementation.

## What this lane still does not unlock

No fresh authorization, discovery/source run, Scheduler/runtime execution, memory generation, `WINDOW_15M`, `WINDOW_1H+`, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, paper audits, PnL, wallet, signing, private keys, real funds, or live execution.

## Proof/test needed before completion of a later repair

1. Read-only DTW96 exhaustion-certificate persistence check.
2. Design-only exact readiness/report projection contract.
3. Focused TDD proving a 3/4 permanent reserve cannot be upgraded to ready by the two-slot selector.
4. Focused TDD proving 4/4 still selects exactly two without scoring/ranking/weighting.
5. Focused proof that the persistent shortage/certificate reaches terminal reporting.
6. Post-repair read-only rereadiness before any new authorization.

## Functionality Risks / Setbacks / Efficiency Blockers

- Lowering reserve depth would remove the alternate-per-slot protection and weaken the adopted permanent-discovery contract.
- Treating terminal tracking state as fresh would bypass lifecycle ownership and create duplicate/reopened tracking without the required owner.
- Gating only on two selected candidates repeats DTW96-style wasted authorizations.
- Broad regression or live rerun is unnecessary before the narrow durable-certificate audit and design are complete.
