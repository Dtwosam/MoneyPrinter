# Printer V1 V2-9.8B Later-Cycle Fresh Inventory / Refresh / Identity Design

Status: DESIGN_APPROVED_FOR_IMPLEMENTATION_BY_OPERATOR

Baseline: `cf329a03801ca8af7e9fb5dbe65455f96cb9a2c6`

## Scope

Repair only the three later-cycle defects proven by the completed 4/2/2 forensic closeout. Preserve the closed freeze-input repair, two active slots, freeze depth 4, Source Governor, Central Scheduler, zero automatic retries, and all V1 locks.

## A1 — fresh eligible inventory traversal

Problem: later-cycle permanent discovery persists fresh exact-market / reserve evidence, including protocol-confirmed `CURRENT_VISIBLE` + `MEMORY_OBSERVATION_ELIGIBLE` identities, but the eligible traversal reloads only `export_graduated_candidates()`, which is the historical `printer_pumpswap_graduated_candidate_registry`.

Design:
- Do not broaden the global meaning of `export_graduated_candidates()`.
- Add a later-cycle-specific inventory composer that reads both:
  1. historical graduated-registry inventory, and
  2. fresh exact-market/reserve identities that are already protocol-confirmed, `CURRENT_VISIBLE`, and `MEMORY_OBSERVATION_ELIGIBLE` for the exact campaign/acquisition scope.
- Union by exact mint + exact pair/pool identity; stronger current evidence wins only when identities agree.
- Preserve all existing categorical gates: Solana identity, PumpSwap protocol confirmation, liquidity floor, tracking-state eligibility, Cycle-1 disjointness, safety/evidence gates, and freeze depth 4.
- Fresh inventory becoming visible must not imply admission. Freeze remains the admission boundary.
- Exhaustion accounting must count the same lawful inventory store that later-cycle selection actually traverses.

## A2 — temporal refresh ownership

Problem: cooperative later-cycle work can terminalize with remaining acquisition time/source budget and no durable 600-second refresh opportunity.

Design:
- Keep one durable `PreLifecycleAcquisitionOwner` / ledger identity for the whole Cycle-2 attempt.
- Resume that owner across cooperative Scheduler quanta; never create a fresh ledger at the final claim merely to classify shortage.
- When no pair is available and the acquisition deadline plus source budget still permit another refresh interval, persist the wait/refresh work and yield.
- Emit terminal shortage only after the bounded owner reports no lawful refresh opportunity remains, or a harder categorical stop applies.
- Refresh work remains Central-Scheduler-owned and Source-Governed; this is not a retry and must not introduce endpoint rotation.

## A3 — resolved identity preservation

Problem: a weaker incoming Dex observation with `UNRESOLVED_TOKEN_PROGRAM` / `UNRESOLVED_POOL_PROGRAM` can demote an already exact PumpSwap identity to `IDENTITY_CONFLICT`.

Design:
- Treat incoming `UNRESOLVED_*` as weaker evidence.
- If the stored value is resolved and the new value is unresolved, retain the stored value and do not create an identity conflict.
- If both old and new are resolved and disagree, preserve the existing fail-closed conflict behavior.
- If old is unresolved and new is resolved, upgrade to the resolved value.
- Record provenance without allowing weaker evidence to erase stronger identity.

## Required proof

Test first, then implementation. Focused tests must prove:
1. fresh protocol-confirmed MOE appears in later-cycle eligible traversal while historical registry inventory still works;
2. fresh evidence does not bypass freeze depth or tracking/Cycle-1 disjointness;
3. a remaining 600-second opportunity is durably scheduled rather than terminalized;
4. no refresh is scheduled once the bounded horizon/source budget is exhausted;
5. incoming unresolved program ids preserve an existing resolved PumpSwap identity;
6. conflicting resolved ids still fail closed.

No live provider calls, no Printer run, no authorization, no migration.