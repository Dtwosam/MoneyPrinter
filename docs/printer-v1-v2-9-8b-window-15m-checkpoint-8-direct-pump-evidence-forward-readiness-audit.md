# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — Post-Failure Forward Readiness Audit

Date: 2026-08-07

Status: `V2_9_8B_WINDOW_15M_CHECKPOINT_8_POST_FAILURE_FORWARD_READINESS_CONFIRMED_THREE_REPAIR_REQUIREMENTS`

Baseline audit commit: `416fae51a948f5edc4a2a9c9fb6ed4f7f8d73deb`
Linear: `DTW-47`

## Purpose

After confirming the consumed proof's `DIRECT_PUMP_EVIDENCE_MISSING` root cause, inspect the immediately reachable deterministic success path so another one-shot proof is not spent discovering static follow-on defects.

## Requirement 1 — carry current direct Pump evidence

Confirmed in the baseline audit: current direct migration produces complete `direct_pump_evidence`, but the permanent eligible-supply join copies only `retained_evidence` plus direct-admission labels. The admission owner correctly fails closed.

Repair only the exact-mint bridge in `eligible_token_supply`; do not reconstruct evidence and do not weaken admission.

## Requirement 2 — C8 fixture supply must satisfy the production four-reserve law

`run_persistent_eligible_token_supply()` intentionally raises permanent availability capacity to at least four: two selected candidates plus one fully eligible alternate per slot. This is reserve capacity, not four active tracking slots.

The C8 deterministic fixture currently creates only `alpha` and `bravo`, and its success-semantics/pre-run execution gates hardcode fixture candidate count `2`.

Therefore, after the evidence bridge is repaired, the current two-candidate fixture cannot prove the permanent eligible-reserve contract. C8 must model four lawful eligible supply candidates while still allowing the canonical neutral selection owner to select exactly two for tracking/lifecycle.

Required proof-only changes:

- deterministic candidates: four distinct Pump/PumpSwap candidates;
- success semantics: four fixture supply candidates, all non-infrastructure;
- execution preflight: require the four-candidate fixture supply contract;
- direct-migration compatibility: expect all four to survive the real consumer path;
- final tracking/lifecycle expectation remains exactly two selected candidates, not four active tokens.

Do not reduce or bypass the production four-reserve rule for C8.

## Requirement 3 — lifecycle market fixtures must be selected-target aware

The C8 `lifecycle.snapshot_adapter_factory` and fallback currently build their pair payload from `candidates[0]` regardless of the requested `token_mint` / `pool_address` factory arguments.

Once the four-candidate reserve feeds neutral two-candidate selection, either selected mint may be any lawful candidate. A first-candidate-only lifecycle fixture can therefore create an exact-target mismatch even though the selected candidate is valid.

Repair the proof fixture factory only so the requested exact mint/pool resolves to the matching deterministic candidate. Unknown or conflicting target identity must fail closed. General market context fixtures remain unchanged.

## Scope classification

The combined repair remains narrow:

1. one real production bridge field-continuity defect;
2. one C8 fixture reserve-capacity mismatch with production policy;
3. one C8 exact-target fixture-selection defect exposed by the larger lawful reserve.

No Source Governor, Scheduler, selection, memory-quality, cleanup, replay, financial, or longer-window owner changes are justified.

## Minimum offline proof before closeout

- deterministic RED reproducing missing direct evidence on permanent supply;
- four-candidate deterministic fixture semantics and real-consumer compatibility;
- exact-target lifecycle fixture tests for at least two distinct candidates and rejection of mismatched target;
- permanent `build_graduated_supply()` reaches READY with four reserve candidates and exactly two selected candidates under the C8 fixture, zero network attempts;
- focused affected tests and full C8 wildcard GREEN;
- `py_compile` for changed Python files;
- `git diff --check` and exact changed-file manifest;
- no provider/network/runtime/authoritative DB/controlling proof.

## Money-usefulness contribution

The repair proves the real intake can preserve exact source authority, maintain operational reserve resilience, and feed exactly two truthful selected tokens into 15m learning without fabricated lineage or hidden target substitution.

## What remains locked

No new controlling proof is authorized. Operational memory growth, provider access, authoritative DB use, WINDOW_1H+, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, and PnL remain locked.

## Functionality Risks / Setbacks / Efficiency Blockers

- Four fixture candidates must not become four active tracking tokens; selection remains exactly two.
- Evidence must be carried from the exact direct owner, never reconstructed from registry or market data.
- Lifecycle fixtures must fail closed on unknown/mismatched target rather than silently use candidate zero.
- Broad production refactors would exceed the proven defect; keep production change to evidence continuity only.
