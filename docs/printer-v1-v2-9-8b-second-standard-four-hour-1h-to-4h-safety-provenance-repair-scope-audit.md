# Printer V1 V2-9.8B — Second Standard Four-Hour 1h→4h Safety/Provenance Repair-Scope Audit

## Verdict

`V2_9_8B_SECOND_STANDARD_FOUR_HOUR_1H_TO_4H_SAFETY_PROVENANCE_REPAIR_SCOPE_AUDIT_PASS`

Audit-only scope is complete. No source/provider calls, Scheduler runtime, authoritative DB mutation, memory generation, new authorization, rerun, resume, restart, successor, or 4h attempt was performed.

## Baseline

- audit baseline / parent HEAD: `04abb0f77156fc23a895c3b540e06b997217e70a`
- frozen consumed-launch branch remains `agent/v2-9-8b-post-standard-4h-fresh-authorization-preparation`
- frozen consumed-launch HEAD remains `fdf5ea4c31afc9e62f1b9bc7263a44e32bfb33b7`
- second consumed authorization remains permanently non-reusable

The audit used the active Printer V1 source stack and the committed second-attempt runtime-classification closeout. `docs/printer-v1-memory-growth-build-order-v2.md` remains the active memory-growth build order inside that stack, not the sole source of truth.

## Root-cause confirmation

The second standard-four-hour attempt produced two valid clean `WINDOW_1H` predecessors, but the standard 4h barrier found no exact safety authority on either first-hour memory. Both tokens therefore failed closed with:

- `predecessor_evidence_stale`
- `governed_provenance_untraceable`
- `mandatory_safety_context_missing`

Those three reasons remain one systemic integration failure, not three independent market failures.

### Consumer contract is correct

`campaign_authority_adapters.load_authoritative_window_safety()` requires the exact predecessor memory to retain:

`supporting_context_json.memory_build_evidence_overlays.safety_composite_id`

It then loads that exact composite and validates exact token/pair identity, cutoff/freshness, source traces, provenance, and safety result. It deliberately does not substitute an arbitrary latest safety record.

The standard 4h consumer correctly maps absent or unacceptable safety authority to failed freshness, untraceable governed provenance, and missing mandatory safety context. These hard gates must not be weakened.

### Producer contract is incomplete

`one_command_15m_factory._execute_continuation_close()` currently:

1. performs the final governed exact-pair snapshot;
2. resolves the exact current-run 15m predecessor;
3. closes `WINDOW_1H`;
4. derives the first-hour outcome;
5. runs audit/E2Z.

It performs no fresh close-time safety collection, no safety-composite persistence for the 1h closing snapshot, and no safety-composite binding into the produced 1h memory.

`lane_e2o_1h_window_close.py` correctly remains a source-free close module and is not the canonical owner for provider calls.

## Why copying the old 15m safety ID is rejected

The existing safety composite contract uses `MAX_AGE_SECONDS = 1800` (30 minutes). The first-hour close occurs about 45 minutes after the 15m checkpoint. Therefore the prior 15m safety composite cannot lawfully satisfy the 1h→4h freshness gate merely by copying its ID into the 1h row.

That shortcut would either remain stale or require weakening the approved freshness rule. Both are rejected.

The repair must produce fresh safety evidence at the first-hour close boundary.

## Canonical ownership

### Source collection owner

Keep source collection in `one_command_15m_factory` orchestration, using the existing `_collect_preclose_context(... include={"safety"})` path.

That path already:

- uses Source Governor;
- uses the governed GoPlus safety request;
- uses Solana RPC holder concentration only when GoPlus holder concentration is unknown;
- permits exactly one governed backup holder RPC after an eligible transient primary failure;
- persists source request/response/failure provenance.

No private source loop is required or allowed.

### Safety persistence owner

Reuse `_persist_preclose_context()` against the exact first-hour closing snapshot. It already persists structured GoPlus safety evidence and the composed safety record with exact token/pair/snapshot identity.

### First-hour memory binding owner

The orchestration that has both the fresh persisted composite and the newly closed `WINDOW_1H` row must bind only the exact fresh `safety_composite_id` into the first-hour memory's `memory_build_evidence_overlays`.

The binding must fail closed on missing composite ID, missing memory row, wrong window kind, token/pair mismatch, or closing-snapshot mismatch.

### Consumer owner

Keep `campaign_authority_adapters.load_authoritative_window_safety()` unchanged in semantics. It remains the exact B.2 authority adapter.

### 4h policy owner

Keep the standard 4h hard-gate semantics unchanged. No outcome, trajectory, learning-need, ranking, confidence, score, or 5m support signal may substitute for safety/freshness/provenance.

## Resource-accounting defect coupled to the producer defect

Current lifecycle reservation accounting reserves only one request for `CONTINUATION_CLOSE`: its exact-pair closing snapshot.

Fresh first-hour safety requires a bounded safety bundle:

- GoPlus safety: 1 request;
- holder primary, when required: at most 1 request;
- one approved backup holder RPC after eligible transient primary failure: at most 1 request.

Therefore the safe hard reservation for `CONTINUATION_CLOSE` is:

- closing snapshot: 1;
- first-hour safety context: 3;
- total: 4 source transport operations.

No additional Scheduler work item is needed because these governed source operations execute inside the already Scheduler-owned first-hour close step.

The standard lifecycle request budgets currently omit this first-hour safety component. The repair must add `3` request operations per token that reaches a first-hour close. For the existing two-token standard campaign maximums this changes the request ceilings from:

- FAST + FAST: `230` → `236`
- FAST + NORMAL: `182` → `188`
- NORMAL + NORMAL: `134` → `140`

Scheduler ceilings remain unchanged at `210`, `162`, and `114` respectively.

These are hard ceilings/reservations, not expected usage targets. If GoPlus already supplies usable holder concentration, fewer actual source calls may occur.

## Exact repair scope

Approved next design may change only what is required to:

1. reserve first-hour close safety transport capacity;
2. collect fresh governed safety at `CONTINUATION_CLOSE`;
3. persist the fresh safety evidence/composite against the exact closing snapshot;
4. bind the exact fresh composite ID to the produced `WINDOW_1H` memory;
5. preserve exact-source provenance and freshness checks;
6. update standard cumulative request ceilings/accounting;
7. add focused offline tests proving the contract.

The repair must not:

- reuse stale 15m safety as fresh 1h authority;
- weaken the 30-minute freshness contract;
- make `lane_e2o_1h_window_close.py` perform provider calls;
- make B.2 search for an arbitrary latest composite;
- bypass Source Governor or Central Scheduler;
- add retries or endpoint rotation beyond the already approved single holder backup path;
- alter selection, outcome qualification, 5m support role, 12h/24h, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.

## Minimum sufficient offline proof required

Before repair closeout, focused offline proof must show at least:

1. `CONTINUATION_CLOSE` reserves `4` governed operations with one close-observation reservation and three first-hour-safety reservations;
2. standard lifecycle request ceilings include the new first-hour safety component while Scheduler ceilings remain unchanged;
3. a first-hour close fixture collects safety through the existing governed context path, not through the source-free close module;
4. the persisted composite is tied to the exact first-hour closing snapshot and exact token/pair;
5. the produced `WINDOW_1H` row contains the exact `memory_build_evidence_overlays.safety_composite_id`;
6. missing/mismatched composite identity fails closed;
7. B.2 can resolve the newly bound fresh first-hour safety authority and retains its existing freshness/provenance/safety checks;
8. no test unlocks or writes retrieval, paper decisions, positions, trades, audits, PnL, 12h, or 24h state.

No provider/live proof is part of this repair implementation lane.

## Money-usefulness contribution

This repair lets Printer preserve a trustworthy safety state at the first-hour decision boundary instead of discarding an otherwise clean lifecycle because the safety authority link is missing. That improves memory-growth usefulness without teaching Printer to ignore changing rug/holder risks between 15m and 1h.

## What this lane improves

- identifies the exact canonical producer defect;
- rejects unsafe stale-evidence reuse;
- identifies the missing transport reservation/accounting component;
- defines the narrow source-governed and Scheduler-owned repair boundary.

## What this lane still does not unlock

- no new standard 4h attempt;
- no fresh authorization;
- no runtime/source fetching;
- no 12h/24h;
- no retrieval;
- no paper decisions;
- no BUY/SELL/HOLD;
- no paper positions, trade events, paper-trade audits, or PnL.

## Functionality Risks / Setbacks / Efficiency Blockers

- **Safety freshness regression:** copying the old 15m composite would silently weaken the intended first-hour safety checkpoint; explicitly prohibited.
- **Budget under-reservation:** adding fresh safety without increasing `CONTINUATION_CLOSE` reservation can create a later hard-budget stop after work has already started.
- **Hidden source-loop drift:** provider calls added inside the source-free 1h close module would violate source ownership; explicitly prohibited.
- **Identity contamination:** attaching a composite without exact token/pair/snapshot checks could make a clean first-hour memory unsafe for later continuation.
- **Scope expansion:** this repair must not be used to revisit unrelated historical holder-budget or 15m accounting behavior unless a focused repair test proves a direct conflict.

## Next lane

`SECOND_STANDARD_FOUR_HOUR_1H_TO_4H_SAFETY_PROVENANCE_REPAIR_DESIGN`

Design is permitted only within the exact scope above. It does not authorize runtime or another 4h attempt.