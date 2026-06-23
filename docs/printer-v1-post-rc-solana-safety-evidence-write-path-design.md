# Solana Safety Evidence Write-Path Design

This is a pre-Lane-7 Post-RC design document.

It is not Lane 7. It is not live safety evidence collection. It is not source adapter implementation. It is not Solana RPC implementation. It is not GoPlus or RugCheck implementation. It is not a paper decision task. It is not a DB mutation task.

## Current State Summary

Current state:

- `printer_solana_safety_evidence` schema table now exists through `migrations/022_solana_safety_evidence.sql`.
- No write path exists for `printer_solana_safety_evidence`.
- No live source adapter exists for Solana safety evidence.
- No Solana RPC, GoPlus, RugCheck, Helius, Jupiter, or other live safety source is wired in.
- Clean memory count remains `0`.
- Clean eligible memory count remains `0`.
- Lane 7 remains blocked.
- Retrieval remains blocked.
- Paper decisions remain blocked.
- BUY remains locked.
- Paper positions remain `0`.
- Paper trade events remain `0`.
- PnL remains unavailable.
- `SAFETY_UNKNOWN` remains a hard clean-memory blocker.

This task is design-only. It does not write to the persistent database, does not insert rows into `printer_solana_safety_evidence`, and does not create source request, response, or failure rows.

## Future Allowed Write Path

The only acceptable future write path is:

1. Source Governor request.
2. Source response or source failure recorded through existing governed source trace tables.
3. Bounded scheduler/operator-approved collection job.
4. Target validation against token, optional pair, snapshot, memory window, or evidence window.
5. Freshness validation against the intended evidence window.
6. Categorical normalization into the safety evidence fixture shape.
7. Guarded insert into `printer_solana_safety_evidence`.
8. Memory audit may read the row only in a future approved audit-integration task.
9. Retrieval and paper decisions remain blocked unless a future clean-memory audit explicitly makes memory clean under all gates.

Future source-specific collection must never write directly from a source adapter into clean memory, retrieval, paper decisions, paper positions, trade events, or PnL.

## Required Write Guards

Before any future insert into `printer_solana_safety_evidence`, all of these guards must pass:

- `token_id` is present.
- `snapshot_id` is present.
- `paper_only_context` is true.
- `source_request_id` is present.
- Either `source_response_id` or `source_failure_id` is present.
- A successful source result must use `source_response_id`.
- A failed source result must use `source_failure_id`.
- Target validation proves the evidence belongs to the intended token, pair if used, snapshot, and window if used.
- `target_status` is `TARGET_MATCH` before evidence can ever support clean eligibility.
- `freshness_label` is fresh or acceptable before evidence can ever support clean eligibility.
- `source_status` is complete or acceptable partial before evidence can ever support clean eligibility.
- `data_quality_label` is clean or acceptable partial before evidence can ever support clean eligibility.
- Failed, stale, conflicting, missing, target-mismatched, or non-paper-context rows remain audit-only.
- Memory engine direct writes are forbidden.
- Paper decision engine direct writes are forbidden.
- Retrieval engine direct writes are forbidden.
- Paper monitor direct writes are forbidden.
- Any future write must occur behind Source Governor and Central Scheduler/operator boundary.

The write helper, when implemented later, should fail closed: if any guard is unclear, it should refuse clean eligibility and preserve the evidence as audit-only or decline the insert with an audit-visible reason.

## Normalization Rules

Normalization must be categorical only.

Use existing-compatible safety labels where possible:

- `SAFETY_CLEAN`
- `SAFETY_CAUTION`
- `SAFETY_SUSPICIOUS`
- `SAFETY_UNSAFE`
- `SAFETY_UNKNOWN`
- `SAFETY_DO_NOT_USE_FOR_MEMORY`

For future write-path review summaries, the following coarse categories may be used as non-storage shorthand:

- `SAFETY_CLEAR`
- `SAFETY_CAUTION`
- `SAFETY_BLOCKED`
- `SAFETY_UNKNOWN`

Those shorthand categories must map back to existing-compatible labels before storage or audit use.

Normalization must not add:

- scores
- rankings
- confidence percentages
- weighted risk values
- numeric decision values
- BUY signals
- live-trade flags
- wallet fields
- private-key fields
- signing fields
- transaction fields

## Failed, Missing, And Stale Behavior

Future write-path behavior must preserve bad or incomplete evidence honestly:

- A failed source creates or keeps source failure trace. It does not create clean evidence.
- Missing evidence remains `SAFETY_UNKNOWN`.
- Stale evidence remains audit-only.
- Mismatched evidence remains audit-only.
- Failed source evidence remains audit-only.
- Blocked or high-risk evidence cannot be clean.
- Caution evidence remains visible but cannot unlock clean memory alone.
- Missing Source Governor trace blocks clean eligibility.
- Non-paper-only evidence is invalid for V1 memory.
- Source failures must stay visible and must not be overwritten by optimistic fallback values.

## Source Governor Boundary

Every future write must be backed by governed source trace.

Required properties:

- A source request row exists before evidence is collected.
- A source response row exists for successful collection.
- A source failure row exists for failed collection when available.
- Source response and failure ids remain auditable from the evidence row.
- Safety evidence cannot be created directly by clean-memory logic.
- Safety evidence cannot be created directly by paper-decision logic.
- Safety evidence cannot be created directly by retrieval logic.
- Safety evidence cannot be created by an adapter bypassing Source Governor.
- Source failures must be preserved, not hidden.
- Any future source must remain free/public or optional-free under V1 rules.

## Central Scheduler Boundary

Future collection must be scheduler-controlled.

Required properties:

- Future collection is scheduled.
- Future collection is bounded.
- Manual proof collection requires explicit operator approval.
- Future scheduler job uses an approved safe job kind, likely `TRACKED_TOKEN_SAFETY_LIQUIDITY_REFRESH` or a later explicitly approved equivalent.
- No continuous loop.
- No source spam.
- No daemon.
- No cron.
- No Celery.
- No APScheduler.
- No runtime expansion without roadmap approval.
- No source collection competes with higher-priority token snapshots or paper monitoring in later lanes.

## Clean-Memory Gate Preservation

The write path alone cannot create clean memory.

Safety evidence alone cannot unlock clean memory. It can only help resolve the safety portion of a future clean-memory audit.

Other blockers still apply:

- market regime
- Solana chain heat
- flow direction
- flow pressure
- entry realism
- exit realism
- snapshot coverage
- source quality
- evidence-window targeting
- memory audit rules

Dirty, stale, failed, target-mismatched, and audit-only evidence cannot enter retrieval.

No paper decision, BUY, paper position, paper trade event, or PnL can be unlocked by safety evidence writes alone.

## Future Implementation Phases

Recommended future split:

1. Solana safety write-path fixture tests.
   - Fixture-only tests for source trace, scheduler boundary, target validation, freshness validation, failed/stale/missing handling, and forbidden-field guards.

2. Source-governed insert helper design.
   - Design a pure write helper contract without wiring runtime collection.

3. Isolated DB write tests.
   - Temp DB only. Insert fixture rows into `printer_solana_safety_evidence` and prove downstream tables remain unchanged.

4. Manual operator command design.
   - Define an operator-approved manual command shape without live collection.

5. Bounded scheduler integration design.
   - Define how an approved job would claim, normalize, insert, and stop.

6. Later source adapter review.
   - Only after fixture/write-helper paths are approved, review a governed free/public safety source. Do not make live source implementation the immediate next task.

7. Later memory audit integration review.
   - Only after evidence write path exists, review how memory audit may read safety rows while preserving all clean-memory gates.

## Fixture Test Status

Fixture-only write-path guard tests were added in:

`tests/test_post_rc_solana_safety_evidence_write_path_fixture_tests.py`

These tests prove:

- Design requires Source Governor trace.
- Design requires scheduler/operator boundary.
- Design forbids memory-engine direct writes.
- Design forbids paper-engine direct writes.
- Design forbids retrieval direct writes.
- Failed evidence remains audit-only.
- Stale evidence remains audit-only.
- Missing evidence remains `SAFETY_UNKNOWN`.
- Target mismatch remains audit-only.
- Caution evidence does not unlock clean memory alone.
- Blocked/high-risk evidence cannot be clean.
- Score, rank, confidence, and weighted fields are forbidden.
- Wallet, private-key, signature, signing, transaction, and live-execution fields are forbidden.
- Safety write path does not unlock clean memory.
- Safety write path does not unlock retrieval.
- Safety write path does not create paper decisions.
- Safety write path does not create positions.
- Safety write path does not create trade events.
- Safety write path does not create PnL.

The tests are in-memory only. They do not insert into `printer_solana_safety_evidence`, do not mutate the persistent DB, and do not implement a runtime write helper.

## Non-Goals

This task does not:

- Write to the persistent DB.
- Insert rows into `printer_solana_safety_evidence`.
- Create persistent evidence rows.
- Create source request rows.
- Create source response rows.
- Create source failure rows.
- Add a source adapter.
- Add a Solana RPC client.
- Add GoPlus or RugCheck integration.
- Call a live API.
- Call live RPC.
- Collect source data.
- Create token snapshots.
- Create context rows.
- Build or rebuild memory.
- Run retrieval.
- Create paper decisions.
- Unlock BUY.
- Create paper positions.
- Create paper trade events.
- Create PnL.
- Activate Lane 7.

## Recommended Next Safe Task

Recommended next safe task:

`Solana Safety Evidence Insert Helper Design`

Why:

- The schema exists.
- The write path is now defined.
- Fixture-only write-path guard tests now exist.
- The next narrow step is to design the future insert helper contract without live source collection, runtime wiring, paper decisions, BUY unlocks, or persistent DB mutation outside temp tests.

Lane 7 remains blocked until clean eligible memory exists.
