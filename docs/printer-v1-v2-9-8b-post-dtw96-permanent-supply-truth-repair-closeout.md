# Printer V1 — V2-9.8B Post-DTW96 Permanent Supply Truth Repair Closeout

## Verdict

`V2_9_8B_POST_DTW96_PERMANENT_SUPPLY_TRUTH_REPAIR_CLOSEOUT_PASS`

## Baseline and implementation

- Audit closeout: `73abee044d7e43553d265f6f3f88f75b8f7fba3c`
- Design: `a29c0198ac61e99e21074bd6cd1a6791f6271a77`
- Complete RED baseline: `95f9ffbd875352eb9df13422fb062427968354a9`
- Implementation: `1535bddd05e9d1a5e59c8c1c6fc34be235b991dd`
- Implementation branch: `agent/v2-9-8b-post-dtw96-permanent-supply-truth-repair-implementation`

The implementation branch was independently verified on GitHub to be exactly the implementation commit above and exactly one commit above the complete RED baseline.

## Implemented repair

The implementation changes only these four approved production owners:

- `src/printer_v1/discovery/eligible_token_supply.py`
- `src/printer_v1/discovery/permanent_discovery_availability.py`
- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
- `src/printer_v1/operator_cli/graduated_supply_front_door.py`

The repair:

1. captures remaining reconciliation-stage capacity before the canonical market owner can issue GeckoTerminal fallback I/O;
2. caps fallback requests before Source Governor/provider execution;
3. validates that actual reconciliation calls cannot exceed the offered capacity, then charges exactly the actual call count;
4. requires permanent outer readiness to respect `persistent.ready` in addition to the existing two-candidate selector conditions;
5. preserves `LAWFUL_WORK_REMAINING_WITH_CAPACITY` as `DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE` ahead of candidate-local tracking masking while retaining stronger source/budget/duration failures;
6. propagates the existing exhaustion certificate into the permanent pre-lifecycle reporting projections without reconstructing or mutating it.

## Focused proof evidence

Operator-local disposable/offline proof returned:

- focused DTW96 tests: `8 passed in 0.77s`
- existing GeckoTerminal fallback compatibility: `1 passed in 0.39s`
- `py_compile`: PASS
- `git diff --check`: PASS
- authoritative database accessed: false
- Printer source calls: 0
- Scheduler runtime calls: 0
- authorization created: false
- WINDOW_15M started: false

RED was separately demonstrated before implementation:

- first contract RED: 5 failed, 1 passed;
- complete behavioral RED: 7 failed, 1 passed, including zero-capacity and partial-capacity pre-I/O fallback behavior.

Independent GitHub verification confirms the implementation commit contains only the four approved production files and the implementation branch remains frozen at `1535bddd05e9d1a5e59c8c1c6fc34be235b991dd`.

## Locked invariants preserved

- active selection capacity: `2`
- `MINIMUM_FREEZE_DEPTH`: `4`
- stage reservations: `3/2/6/7/8/4`
- no operation-ceiling increase
- no liquidity-floor change
- no tracking-policy relaxation
- no migration-registry confirmation reintroduction
- no PumpSwap protocol/account validation removal
- no Source Governor bypass
- no Central Scheduler bypass
- no retrieval, paper decision, BUY/SELL/HOLD, position, trade-event, paper-trade-audit, or PnL unlock
- no WINDOW_1H+ unlock

## Money-usefulness contribution

The repair prevents already-unaffordable reconciliation work from consuming source calls, preserves the intended bounded discovery budget, and makes readiness/blocked evidence reflect the canonical permanent-supply owner. This improves the reliability of memory-growth evidence without weakening admission or source-quality rules.

## What this lane improves

- pre-I/O reconciliation budget enforcement;
- truthful permanent supply readiness;
- truthful lawful-work-versus-tracking shortage precedence;
- durable exhaustion-certificate reporting;
- consistency between the persistent supply owner and downstream pre-lifecycle gates.

## What this lane still does not unlock

This closeout does not authorize another live WINDOW_15M run by itself. It does not unlock WINDOW_1H+, retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events, audits, or PnL.

The next roadmap-compliant step is a fresh **read-only post-DTW96 rereadiness audit** against the authoritative database and exact implementation HEAD. Only after rereadiness passes may a new one-use WINDOW_15M authorization preparation/review lane begin.

## Proof/test required before next real runtime

The rereadiness lane must, at minimum, verify read-only immutable database health/identity, migration ledger state, zero active/locked residue, source/composition/dependency/holder-budget readiness, historical paper-audit preservation, and exact Git binding to the repaired HEAD. It must perform zero source calls, zero Scheduler runtime, zero database writes, create no authorization, and start no WINDOW_15M runtime.

## Functionality Risks / Setbacks / Efficiency Blockers

- This focused proof does not itself prove a real campaign will achieve four-deep reserve; it proves the identified control/truth defects are repaired under disposable tests.
- A future bounded real attempt may still honestly block for genuine market/source/tracking conditions.
- The existing stage ceilings intentionally remain restrictive; do not raise them merely to force a pass.
- The four-deep reserve remains mandatory and must not be reduced to two.
- Any new unrelated blocker found during rereadiness or a later authorized run requires its own bounded audit/design sequence.

## Stop condition

Stop here for implementation/proof. Do not create a fresh authorization or invoke Printer until the post-DTW96 read-only rereadiness audit and its closeout pass.