# Printer V1 V2-9.8B Post-DTW96 Exhaustion Certificate Audit

## Scope

Audit-only follow-up to DTW96. No source fetching, runtime, Scheduler execution, memory generation, authorization, retrieval, paper decisions, positions, trades, audits, or PnL.

## Retained DTW96 evidence

Authorization `V2_9_8B_WINDOW_15M_AUTH_20260809T095642Z` is permanently consumed.

Authoritative read-only SQLite inspection found exactly one exhaustion certificate for campaign `20260809T095949Z-a3b8cedc5bd5-campaign`:

- certificate: `exh-20260809T095949Z-a3b8cedc5bd5`
- required eligible capacity: `4`
- eligible reserve count: `3`
- eligible count: `3`
- rejected count: `7`
- rejection reasons: `DUPLICATE_ACTIVE_TRACKING=2`, `TERMINAL_TRACKING_STATE=5`
- shortage classification: `TRACKING_STATE_CAPACITY_BLOCKED`
- discovery rounds: `1`
- source operations used: `11`
- source operations remaining: `19`
- pools confirmed / inventory known at start: `48`
- unique tokens observed: `10`
- provider failures: `0`
- channels unavailable: none
- stale evidence exclusions: `0`
- last reason discovery could not continue: `LAWFUL_WORK_REMAINING_WITH_CAPACITY`
- unexplored work prevented by hard ceiling: `false`

Certificate persistence therefore worked. The earlier terminal extraction omitted the certificate; that is a reporting/projection omission, not a certificate-persistence failure.

## Static contract findings

1. Permanent availability raises the persistent Eligible Token Supply target to at least four. The four-deep reserve is intentional: two selected identities plus one alternate per slot. It must not be reduced to two merely to force a proof pass.
2. The persistent loop is intended to continue while campaign eligible depth is below the required capacity, subject to governed stage/flat/duration limits.
3. The persistent owner correctly returned a below-capacity result and persisted an exhaustion certificate.
4. The outer `build_graduated_supply()` composition separately computes ordinary two-candidate selection readiness and can report supply readiness without requiring `persistent.ready`. This creates a truth mismatch when persistent depth is 2 or 3 but the permanent reserve requirement is 4. The downstream freeze-depth guard correctly prevented lifecycle entry in DTW96.
5. Shortage precedence can label the certificate `TRACKING_STATE_CAPACITY_BLOCKED` whenever any tracking disposition is ineligible, even when `last_stop_reason` has already been corrected to `LAWFUL_WORK_REMAINING_WITH_CAPACITY`. Therefore the shortage label alone is not sufficient to establish that tracking state was the actual reason no further lawful work could execute.
6. `source_operations_remaining=19` is not enough to prove another market batch was executable because the permanent path uses stage reservations. Market batching has a separate reservation and later-stage capacity cannot flow backward.

## Remaining audit question

Read the retained DTW96 `stage_capacity`, `stage_operations_used`, `sealed_stages`, `unsealed_stages`, `pending_work_by_queue`, `unexplored_unique_remaining`, `permanent_market_reports`, and direct protocol-confirmation accounting from the terminal artifact.

This will distinguish:

- legitimate exhaustion of the specific stage needed for the fourth observation-eligible candidate, with reporting/readiness projection defects only; from
- a premature stage-stop / accounting defect that left executable market work stranded while the persistent contract still required depth four.

No design or implementation is approved until this distinction is resolved.

## Money-usefulness contribution

Prevents Printer from confusing a real lack of usable observation reserve with an internal composition or stage-accounting defect. That preserves trustworthy memory-growth evidence rather than manufacturing a successful two-token handoff from an under-depth reserve.

## What this audit improves

- proves exhaustion-certificate persistence is healthy;
- separates flat campaign budget from stage-specific capacity;
- isolates readiness projection and shortage-classification truth risks;
- preserves the four-deep reserve safety contract.

## What this audit does not unlock

No new WINDOW_15M attempt, WINDOW_1H+, retrieval, paper decision, BUY/SELL/HOLD, paper position, trade event, trade audit, or PnL capability is unlocked.

## Proof required before completion

One bounded read-only extraction of the retained DTW96 stage-capacity/work-queue diagnostics. No source calls or DB mutation.

## Functionality Risks / Setbacks / Efficiency Blockers

- Lowering reserve depth from four to two would hide the defect and weaken resilience.
- Treating the 19 flat remaining operations as universally spendable would ignore stage reservation law.
- Treating every tracking exclusion as the terminal shortage cause can conceal unrelated architecture/stage exhaustion.
- Promoting outer two-candidate readiness when the permanent persistent owner is not ready can create contradictory state and force later guards to rescue the run.

## Audit state

`PARTIAL_AUDIT_COMPLETE_STAGE_CAPACITY_EVIDENCE_REQUIRED`
