# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — Direct Pump Evidence Bridge Failure Audit

Date: 2026-08-07

Status: `V2_9_8B_WINDOW_15M_CHECKPOINT_8_DIRECT_PUMP_EVIDENCE_BRIDGE_AUDIT_CONFIRMED`

Consumed proof HEAD: `ecd399ef4f4aeee6cf541e4292bb6a5229c943b2`
Proof ID: `C8_REPROOF_AFTER_DTW46_20260807`
Linear: `DTW-47`

## Controlling failure

The single authorized local proof consumed its sentinel and exited 1 at the permanent graduated-supply admission boundary:

`DIRECT_PUMP_EVIDENCE_MISSING:5aNJBy3n3AjsGZ2qvQFKfV6BhKSTQU6MXxN2sjGu8nei`

No retry, rerun, resume, restart, or successor is permitted. The retained local proof root/worktree and frozen manifest remain historical evidence.

## Root cause

`direct_migration_discovery.run_direct_migration_discovery()` correctly constructs complete carried `direct_pump_evidence` for every confirmed Pump/PumpSwap candidate. The evidence contains exact mint, PumpSwap pool, migration signature, graduation slot/time, PumpSwap program id, and `confirmed=True`.

In permanent availability, `eligible_token_supply.run_persistent_eligible_token_supply()` converts market-resolved candidates and joins current direct discovery by mint. The join currently copies `retained_evidence` and sets:

- `admission_authority = DIRECT_PUMP_PUMPSWAP`
- `nomination_source = direct_pump_migration`
- `lineage_state = PUMP_GRADUATION_CONFIRMED`
- `exact_present_pool_confirmed = True`

but it does not carry `direct_pump_evidence` from the matched direct candidate.

`graduated_supply_front_door._source_specific_admission_for()` intentionally validates carried authority without consulting the migration registry. For `DIRECT_PUMP_PUMPSWAP`, missing `direct_pump_evidence` must fail closed. That gate behaved correctly and must not be weakened.

## Classification

This is an active permanent eligible-supply bridge contract defect, not a provider failure and not a C8 fixture-response defect. The deterministic C8 fixture exposed the same real bridge used by the permanent operational path.

The older/non-permanent supply tests do not prove this permanent join contract, which explains why the omission survived focused coverage.

## Narrow repair boundary

The smallest lawful repair is to preserve the already-proven `direct_pump_evidence` from the exact current-cycle `discovery.candidate_mix` row when that row is matched by mint into the permanent market-resolved candidate.

Do not:

- reconstruct or invent direct evidence from market data;
- query/recheck the graduated registry at admission time;
- weaken `_source_specific_admission_for()`;
- change Source Governor, Scheduler, selection, liquidity, holder, memory, or downstream capability law;
- change market-present-pool admission semantics.

A deterministic regression must reproduce the permanent-path missing-evidence RED, then prove the carried evidence reaches `_source_specific_admission_for()` unchanged enough to satisfy its exact identity contract.

## Money-usefulness contribution

Preserving exact Pump/PumpSwap authority through the real supply bridge lets truthful candidates reach 15m learning without replacing source evidence with inference or weakening admission safety.

## What this improves

- direct Pump/PumpSwap evidence continuity through permanent supply;
- end-to-end admission truth;
- permanent-path regression coverage.

## What remains locked

This audit and any repair do not authorize another C8 proof, operational memory growth, providers/network, authoritative DB use, WINDOW_1H+, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.

## Proof needed before closeout

Minimum sufficient offline proof:

1. deterministic RED on the exact permanent bridge;
2. minimal production bridge repair;
3. focused affected regression GREEN;
4. C8 real-consumer compatibility GREEN;
5. full focused C8 wildcard GREEN;
6. changed-file `py_compile` where applicable and `git diff --check`;
7. zero provider/network attempts;
8. exact narrow manifest and independent review.

No new controlling proof is part of this repair proof.

## Functionality Risks / Setbacks / Efficiency Blockers

- Copying evidence from the wrong mint would create false lineage; match by exact mint only.
- Reconstructing evidence downstream would create a second authority; carry the existing direct-owner evidence only.
- Weakening admission to make C8 pass would hide real evidence loss; preserve fail-closed admission unchanged.
- Expanding into market-present-pool policy would exceed the observed blocker; keep this lane direct-evidence-only.
