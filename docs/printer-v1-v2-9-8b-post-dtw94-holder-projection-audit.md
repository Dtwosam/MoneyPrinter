# Printer V1 V2-9.8B — Post-DTW94 Holder Projection Audit

Date: 2026-08-09

## Verdict

`V2_9_8B_POST_DTW94_HOLDER_PROJECTION_AUDIT_PASS_COMMITTED_CODE_DEFECT_CONFIRMED`

Audit-only finding: committed code conflates holder-evidence usability with favorable holder-condition pass when projecting memory-observation activation state.

## Evidence

1. `_holder_execution_fact()` returns `eligible=True` for any clean exact-target holder result whose concentration label is known, including concentrated/extreme. This boolean is consumed by `resolve_holder_concentration_facts()` as an evidence-usability filter.
2. `_holder_observation_context()` currently assigns `fully_eligible = bool(holder_fact['eligible'])`.
3. The memory-observation path explicitly says holder concentration/unavailable evidence remain context and are not memory-admission inputs.
4. `pilot_input_readiness.evaluate_readiness_gates(... MEMORY_OBSERVATION)` does not require holder eligibility.
5. `memory_observation_activation` correctly asserts that `fully_eligible=True` is inconsistent unless holder condition is `HOLDER_CONCENTRATION_PASS` or `HOLDER_CONCENTRATION_HEALTHY`.
6. DTW94 terminated on exactly that invariant: `FULLY_ELIGIBLE_WITHOUT_HOLDER_PASS`.

## Root cause

`holder_fact['eligible']` is overloaded. At the source-resolution layer it means usable/known holder evidence. At the memory-activation projection layer it was incorrectly interpreted as favorable holder-condition pass.

This is a `COMMITTED_CODE_DEFECT` in projection semantics, not a source outage, not a holder threshold issue, and not an activation-contract defect.

## Correct semantic separation

For memory observation:

- holder evidence usability/completeness: preserve independently;
- holder condition: preserve exact categorical label, including concentrated/extreme/unknown;
- future-action holder pass: true only for `HOLDER_CONCENTRATION_PASS` or `HOLDER_CONCENTRATION_HEALTHY` with usable exact-target evidence;
- `fully_eligible`: project the future-action holder pass, never generic evidence usability;
- `MEMORY_OBSERVATION`: remains independent of holder pass.

The shared holder resolver must keep its existing evidence-usability behavior. Do not globally flip `_holder_execution_fact().eligible`, because `resolve_holder_concentration_facts()` uses it to identify usable exact evidence.

## Minimum repair target

Narrowly repair the projection in `authoritative_live_operational_campaign.py`:

- introduce one pure helper that derives favorable holder-condition pass from a holder fact;
- make `_holder_observation_context()` use that helper for `fully_eligible` while still marking usable known holder evidence as complete;
- make the memory-observation readiness-candidate `holder_eligible` projection use the same favorable-condition helper;
- keep holder label/context unchanged;
- keep `future_action_eligibility` fail-closed;
- keep the `FULLY_ELIGIBLE_WITHOUT_HOLDER_PASS` activation invariant unchanged.

Do not change holder providers, source order, thresholds, retries, budgets, discovery, selection, tracking eligibility, Source Governor, Central Scheduler, memory cleanliness law, or financial locks.

## Bounded proof required

Minimum sufficient offline proof:

- healthy/pass known evidence -> complete context + future holder pass true;
- concentrated known evidence -> complete context + future holder pass false;
- extreme known evidence -> complete context + future holder pass false;
- unknown/unavailable -> future holder pass false and truthful incomplete/unavailable context;
- memory-observation activation accepts concentrated/extreme when all independent memory evidence is valid and `fully_eligible=False`;
- existing invariant still rejects an explicitly contradictory `fully_eligible=True` + adverse holder condition;
- no source calls, Scheduler runtime, authoritative DB mutation, authorization, lifecycle or financial capability.

## Money-usefulness contribution

This permits Printer to retain risky/manipulated holder conditions as learnable memory context instead of blocking the episode or falsely calling the token holder-safe. That improves the diversity and honesty of future clean memories without making a buyability claim.

## What remains locked

No runtime or capability unlock follows from this audit. Another real `WINDOW_15M` requires design, implementation, focused proof, closeout, rereadiness, and a fresh one-use authorization.

## Functionality Risks / Setbacks / Efficiency Blockers

- The legacy name `eligible` remains semantically overloaded at the holder source-resolution layer; broad renaming is intentionally out of scope.
- Repairing too broadly could change holder transport budgeting or legacy future-action behavior.
- Weakening the activation invariant would conceal contradictory state and is prohibited.
- DTW94 authorization is permanently consumed.