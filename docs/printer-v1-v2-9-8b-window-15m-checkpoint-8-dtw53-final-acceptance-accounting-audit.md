# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — DTW-53 Final Acceptance Accounting Audit

Date: 2026-08-08

Linear: `DTW-53`

Frozen audit baseline: `fe35f1bf7bb24118797f273b753c05a7dc165bec`

Consumed controlling proof: `C8_REPROOF_AFTER_DTW52_20260807`

## Verdict

`DTW53_FINAL_ACCEPTANCE_ACCOUNTING_AUDIT_COMPLETE_TWO_NEIGHBORING_DEFECTS`

The consumed C8 proof reached a completed two-token `WINDOW_15M` lifecycle with `clean_memory_outcome_pass=true`, but final campaign acceptance correctly remained `BLOCKED_UNSAFE` because two distinct accounting/projection defects remain.

No new C8 proof, source/provider/network work, runtime, authoritative DB mutation, memory generation, retrieval, decision, position, trade, audit, PnL, or `WINDOW_1H+` work was performed in this audit.

## A. LOCAL_VALIDATION_STEP identity-set mismatch

Frozen reconciliation:

- `SOURCE_TRANSPORT_OPERATION`: action-local 46 / owner 46 / exact set equality true
- `SCHEDULER_WORK_ITEM`: 28 / 28 / true
- `LIFECYCLE_RESERVED_TRANSPORT_OPERATION`: 28 / 28 / true
- `LOCAL_VALIDATION_STEP`: action-local 89 / owner 93 / false

The exact four owner-only identities are all real `DIRECT_MIGRATION` validations:

1. `yLbgqeghdHBurT2M9eLJi39RMwwRvqg9fLQJCxfusoP` — `PUMPSWAP_GRADUATION_VERIFIED` — ordinal 1
2. `5dqWELD3TqMDw8BHmi7wcKXrEhuvwNqeCDLCYQGijHut` — `PUMPSWAP_GRADUATION_VERIFIED` — ordinal 2
3. `Hx7d5gD9Lt23A7BQkBxiE6rnfFuw9ARsHSLGN6Acvcbb` — `PUMPSWAP_GRADUATION_VERIFIED` — ordinal 3
4. `5aNJBy3n3AjsGZ2qvQFKfV6BhKSTQU6MXxN2sjGu8nei` — `PUMPSWAP_GRADUATION_VERIFIED` — ordinal 4

### Proven producer/projection gap

`src/printer_v1/discovery/direct_migration_discovery.py` creates one `LocalValidationIdentity` for each PumpSwap graduation verification and seals those identities into the `DIRECT_MIGRATION` stage for campaign-owner ingestion.

The same path accepts `transport_identity_observer` and fires it at measured-transport time, which is why the action-local ledger contains the direct-migration transport identities and campaign transport equality is 46/46.

It does not expose or invoke an equivalent verification-only local-validation observer. Therefore the four genuine direct-migration validations reach the campaign owner but never reach the independent action-local validation ledger.

This is a projection defect. The owner identities are truthful and must not be deleted, discounted, or excluded merely to make equality pass.

## B. reservation_attempt_outcomes_complete scope mismatch

Frozen `source_operation_outcomes`:

- `reserved = 28`
- `attempted = 46`
- `succeeded = 26`
- `failed = 0`

The acceptance law currently derives `attempted` from all campaign-owner transport records, while `reserved` is specifically `LIFECYCLE_RESERVED_TRANSPORT_OPERATION`.

That mixes different scopes.

The 46 campaign-wide transports include 20 pre-lifecycle/discovery transports with no lifecycle reservation linkage:

- locator: 1
- direct migration: 13
- fresh-pool nomination: 1
- mint-market batch: 1
- holder safety: 4

The remaining 26 transports are the actual `WINDOW_15M` lifecycle transport attempts. They use the lifecycle outcome vocabulary and all 26 are `SUCCEEDED`; none failed. The 28 lifecycle reservations are a capacity/reservation ceiling: 16 snapshot reservations plus 12 window-close reservations. Two reserved close-operation slots were not consumed, which is lawful under the existing `reserved >= attempted` acceptance rule.

Therefore the truthful lifecycle comparison is:

- reserved 28
- attempted 26
- succeeded 26
- failed 0

The existing check is false because it compares lifecycle reservations against campaign-wide attempts, not because a real source attempt lacks a terminal outcome.

This is a separate neighboring scope defect from the four missing local-validation projections.

## Root-cause relationship

The two failures share the same final-acceptance surface but are not the same defect:

1. direct-migration local validation identities are not independently projected action-locally;
2. reservation-attempt outcome accounting uses the wrong transport scope.

They may remain in one DTW-53 repair lane, but each requires its own deterministic RED and focused GREEN.

## Minimum safe design direction

Design only after this audit commit:

1. Add a verification-only local-validation observation path for direct migration, propagated through the existing eligible-supply/public composition owner into `CampaignActionLocalLedger.observe_local_validation`. Observation must occur from the real validation producer before stage sealing; it must not be reconstructed from sealed owner evidence or counts.
2. Make `reservation_attempt_outcomes_complete` operate only on lifecycle/reservation-bound transport attempts. Preserve a fail-closed rule that a lifecycle transport cannot disappear merely because reservation linkage is malformed or missing.
3. Preserve exact owner/action-local identity-set equality, non-vacuous evidence, Source Governor, Central Scheduler, six-unit accounting, all request/transport counts, budgets, holder law, cleanup/replay law, and every downstream capability lock.

Explicitly prohibited repairs:

- deleting the four owner identities;
- reducing expected owner counts;
- excluding `DIRECT_MIGRATION` from equality solely to pass;
- synthesizing action-local identities from owner evidence or integer totals;
- redefining campaign-wide transport counts;
- treating pre-lifecycle `OK` / `COMPLETED` transports as lifecycle reservation outcomes;
- weakening `reserved >= attempted` or terminal-outcome completeness;
- rerunning C8 before design, implementation, focused proof, closeout, independent readiness review, and new operator authorization.

## Minimum proof required after implementation

Risk-based verification only:

- deterministic RED for the missing direct-migration action-local validation projection;
- deterministic RED for campaign-wide transports contaminating lifecycle reservation outcomes;
- focused GREEN proving exact owner/action-local validation identity-set equality;
- focused GREEN proving `reserved=28`, lifecycle `attempted=26`, `succeeded=26`, `failed=0`, and `reservation_attempt_outcomes_complete=true` for the frozen composition shape;
- negative coverage that malformed/missing lifecycle reservation linkage still fails closed;
- nearest affected Checkpoint 8 accounting/replay compatibility tests;
- compilation and diff checks.

No broad suite is required until DTW-53 major closeout / pre-C8-readiness unless the implementation becomes cross-cutting beyond this design.

## Money-usefulness contribution

This repair path makes Printer's final acceptance gate faithfully prove the real work performed by a clean two-token 15m campaign. It removes false accounting blockers without weakening the evidence needed to trust future memory growth.

## What this audit improves

- identifies the exact four mismatched validation identities;
- proves they are genuine direct-migration validations, not fabricated owner rows;
- proves the action-local projection surface is missing for that validation family;
- proves reservation completeness is blocked by scope mixing rather than an unfinished provider call;
- separates the two defects so implementation can stay narrow.

## What remains locked

Checkpoint 8 is still blocked. This audit does not authorize implementation by itself, a new C8 controlling proof, operational `WINDOW_15M` activation, `WINDOW_1H+`, retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events, paper trade audits, PnL, wallets, signing, live execution, real funds, paid APIs, scoring/ranking/confidence/weighted logic, embeddings, or vectors.

## Functionality Risks / Setbacks / Efficiency Blockers

- A repair that mirrors owner evidence into action-local after the fact would make equality circular and invalid.
- Filtering transports only by a permissive field without proving lifecycle ownership could hide an unreserved lifecycle request.
- Broadening this lane into source, Scheduler, holder, memory, or runtime changes would create unnecessary regression risk and credit use.
- Another controlling C8 proof before offline closeout would consume proof authority without first removing the known deterministic defects.

## Next permitted step

`DTW-53 design/specification` for the two narrow repairs above.

Stop before implementation until that design is committed and its deterministic RED targets are explicit.
