# Printer V1 V2-9.8B — Post-DTW94 Holder Projection Repair Design

Date: 2026-08-09

## Verdict

`V2_9_8B_POST_DTW94_HOLDER_PROJECTION_REPAIR_DESIGN_PASS`

## Design decision

Repair only the memory-observation projection of holder evidence in `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`.

### Add one pure helper

Add a helper equivalent to:

```python
def _holder_condition_passes(fact):
    if not fact or not bool(fact.get("eligible")):
        return False
    label = str(
        fact.get("holder_condition")
        or fact.get("holder_concentration_label")
        or "HOLDER_CONCENTRATION_UNKNOWN"
    )
    return label in {
        "HOLDER_CONCENTRATION_PASS",
        "HOLDER_CONCENTRATION_HEALTHY",
    }
```

The existing raw `fact['eligible']` remains the shared evidence-usability signal required by holder source reconciliation. Do not change it globally.

### Repair `_holder_observation_context`

Separate:

- `holder_evidence_usable = bool(holder_fact.get('eligible'))`
- `holder_pass = _holder_condition_passes(holder_fact)`

Project:

- known usable holder evidence -> `holder_evidence_status = COMPLETE` regardless of healthy/concentrated/extreme condition;
- unavailable/budget-bound evidence -> preserve current truthful status;
- `fully_eligible = holder_pass`;
- `future_action_eligibility` remains `BLOCKED_OR_UNKNOWN` in this memory-growth path;
- exact holder condition label remains unchanged.

### Repair memory-readiness candidate projection

Inside the permanent memory-observation readiness-candidate projection, replace the current generic evidence-usability boolean with `_holder_condition_passes(fact)` for the `holder_eligible` field.

This does not gate `MEMORY_OBSERVATION`; it makes the persisted field semantically truthful and consistent with `fully_eligible`.

### Preserve activation invariant

Do not change `memory_observation_activation` checks, including:

- `FULLY_ELIGIBLE_WITHOUT_HOLDER_PASS`
- `FUTURE_ACTION_ELIGIBILITY_OVERSTATED`

Those remain valuable fail-closed consistency guards.

## Explicit non-changes

No change to:

- holder providers or source order;
- Source Governor/Central Scheduler ownership;
- thresholds or concentration labels;
- retries, pacing, budgets or operation ceilings;
- discovery/selection/freeze order;
- tracking eligibility/requalification;
- liquidity floor;
- readiness purpose law;
- memory cleanliness rules;
- authorizations or runtime;
- `WINDOW_1H+` or any financial capability.

## Focused proof

Minimum sufficient tests:

1. usable `HOLDER_CONCENTRATION_HEALTHY` -> context COMPLETE, `fully_eligible=True`;
2. usable `HOLDER_CONCENTRATION_PASS` -> COMPLETE, `fully_eligible=True`;
3. usable `HOLDER_CONCENTRATION_CONCENTRATED` -> COMPLETE, `fully_eligible=False`;
4. usable `HOLDER_CONCENTRATION_EXTREME` -> COMPLETE, `fully_eligible=False`;
5. unknown/unavailable -> fail-closed future eligibility and truthful unavailable status;
6. activation validator accepts an otherwise valid concentrated/extreme memory-observation candidate when `fully_eligible=False`;
7. activation validator still rejects explicit `fully_eligible=True` with concentrated/extreme condition;
8. `MEMORY_OBSERVATION` readiness remains holder-pass-independent;
9. no source/Scheduler/runtime/authoritative-DB work.

Use focused tests only. Broader suites are unnecessary unless the narrow tests expose adjacent regression.

## Money-usefulness contribution

Risky holder concentration becomes usable historical context rather than an accidental memory admission blocker. Printer can learn from manipulated/concentrated conditions while keeping future action eligibility conservative and locked.

## What remains locked

A passing implementation/proof still does not authorize a new real campaign. Required next sequence remains implementation -> focused offline proof -> closeout -> authoritative rereadiness -> fresh one-use authorization.

## Functionality Risks / Setbacks / Efficiency Blockers

- The overloaded legacy `eligible` key remains technical debt but broad renaming would create unnecessary scope/risk.
- Tests must prove evidence completeness is not downgraded merely because holder condition is adverse.
- Any future code that again interprets raw holder `eligible` as favorable action eligibility could recreate this defect; the helper becomes the canonical local projection seam.