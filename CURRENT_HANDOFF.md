# CURRENT HANDOFF

Date: 2026-08-18

## Current lane

`V2-9.8B Four-Token 4/2/2 Freeze-Input Versus Two-Slot Truncation Repair Design`

Status: `CLOSED_PASS`

Verdict:

`V2_9_8B_FOUR_TOKEN_4_2_2_FREEZE_INPUT_VERSUS_TWO_SLOT_TRUNCATION_REPAIR_DESIGN_PASS`

Implementation disposition: `IMPLEMENTATION_REQUIRED`

## Current baseline

Consumed-attempt launch baseline:

`2c8caf0b72136cc6eefbb114d4804175abc2097b`

Design branch:

`agent/v2-9-8b-four-token-4-2-2-freeze-input-versus-two-slot-truncation-repair-design`

Design document commit:

`0bb8234f3ff396e72e7de3f6baf098538cb8717c`

Master remains untouched.

## Consumed incident

Authorization:

`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260818T205144Z`

The authorization was consumed exactly once. The campaign ended pre-lifecycle with:

`PRE_LIFECYCLE_DISCOVERY_SELECTION_COVERAGE_INSUFFICIENT`

`lifecycle_started = false`.

The consumed authorization and failed-attempt DB/source/reserve/holder evidence are immutable history and are not reusable or deleted.

## Proven forensic cause

Classification: `PROVEN_IMPLEMENTATION_DEFECT`.

Printer produced eight lawful `MARKET_READY` / `MEMORY_OBSERVATION_ELIGIBLE` exact PumpSwap candidates at or above the $3,000 liquidity floor. The permanent front door retained that full reserve in `GraduatedSupply.holder_reserve_supply`, but also selected the two immediate slot candidates into `GraduatedSupply.graduated_supply`.

`authoritative_live_operational_campaign.py` incorrectly fed the two-slot `graduated_supply` into permanent `_graduated_admission()`. The post-filter freeze therefore saw only two candidates even though its correct minimum depth is four and eight lawful candidates existed.

This was not market scarcity, source scarcity, holder failure, tracking shortage, protocol shortage, Source Governor failure, Scheduler failure, or a freeze-depth defect.

## Approved repair design

For permanent memory-observation mode only:

```text
holder_reserve_supply (full bounded lawful reserve)
-> permanent graduated admission
-> full valid MEMORY_OBSERVATION_ELIGIBLE rows
-> freeze_eligible_reserve
-> exactly 2 selected + 2 alternates
-> exactly the selected 2 enter Cycle 1 slots
```

The existing `graduated_supply` remains the two-slot front-door handoff carrier; it is no longer used as the full pre-freeze observation universe.

Primary future product file:

- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`

No product change is designed in `graduated_supply_front_door.py`; it already exposes both semantic carriers correctly.

## Invariants

- `MINIMUM_FREEZE_DEPTH` remains 4.
- Freeze remains exactly 2 selected + 2 alternates on success.
- Holder work remains bounded to the existing selected-slot subset and is not a memory-observation gate.
- $3,000 liquidity floor, exact mint/pair law, protocol confirmation and tracking exclusions remain unchanged.
- Cycle 2 still requires fresh governed disjoint supply; Cycle-1 alternates are not automatically Cycle-2 supply.
- `standard-four-hour-run` remains two-token operational.
- `four-token-bounded-capacity-proof-run` remains proof-only.
- `four-token-standard-four-hour-run` remains exact operational 4/2/2.
- Source Governor and Central Scheduler remain sole owners.
- Zero retries, no endpoint rotation, 300s minimum cycle spacing unchanged.
- 5m support-only; 12h/24h locked.
- Migration head remains 058; no 059.
- Retrieval and all financial capabilities remain locked.

## Verification required by implementation

TDD red before product code, then minimum green scope.

Positive proof must reproduce >=8 lawful reserve candidates while the immediate front-door pair is 2, prove freeze receives the full post-filter reserve and returns 2 selected + 2 alternates, and prove only selected 2 activate Cycle 1.

Negative proof with only 3 lawful candidates must still coverage-block.

Use frozen/no-network fixtures and a disposable DB only. No live providers, authoritative DB mutation, authorization, application marker, or Printer launch.

The observed six-unit reporting mismatch and missing pre-lifecycle provenance row are `NON_CAUSAL_REPORTING_EVIDENCE_GAPS` and remain outside this repair.

## Exact next permitted action

`V2-9.8B Four-Token 4/2/2 Freeze-Input Versus Two-Slot Truncation Repair Implementation`

Implementation only, followed by bounded proof/test and closeout. Do not create another authorization and do not run Printer.

The active authority stack wins any conflict with this handoff.