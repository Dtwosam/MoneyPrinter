# Printer V1 V2-9.8B Post-DTW100 WINDOW_1H Checkpoint 1 — Clean 15m → 1h Handoff Closeout

## Verdict

`V2_9_8B_POST_DTW100_1H_CHECKPOINT_1_CLEAN_15M_TO_1H_HANDOFF_PASS`

Checkpoint 1 is complete. Starting from two canonical clean-promoted `WINDOW_15M` predecessors, the current standard-first-hour path now creates the complete two-slot continuation decision set, exact `WINDOW_1H` successor ownership rows, and token-slot advancement to `WINDOW_1H_CONTINUING` as one fail-closed first-evaluation ownership transaction.

The repair reuses the existing campaign-ownership architecture. It creates no parallel 1h persistence system, scheduler, source path, memory engine, schema, or migration.

## Baseline and commits

- Checkpoint baseline: `6a031b75f3dfefda6c0f4b95fd3f1d5d8f528cdc`
- Audit commit: `fcf0f35c8a46ac4e56c08578945a7625c995c504`
- Repair design commit: `6eb63c1ab485a1410b1d67dad785a64063c0f8b6`
- Valid RED fixture/test head: `36acb61b6f0e3c396fb9be09ccdf9519c48da92e`
- Initial atomic implementation: `60176e640edbeda732a52147ce8ecb5f47079065`
- Proven implementation head before closeout: `970960b02c743dbc594524701aa16bc8fc144c45`
- Branch: `agent/v2-9-8b-post-dtw100-1h-checkpoint1-clean-15m-handoff`

## Starting boundary preserved

This checkpoint intentionally begins after successful 15m memory completion. It does not re-audit discovery, selection, initial 15m collection, or 15m clean promotion.

A valid handoff predecessor remains required to have exact campaign/run/cycle/token-slot/token/mint/pair/lifecycle identity, a closed `WINDOW_15M`, `CLEAN_DATA`, canonical clean episode plus fingerprint, B.1 clean-promotion authority, acceptable B.2 safety, and continuous governed evidence.

## Blocker found

Before the repair, the operational owner could persist immutable continuation objects and `WINDOW_1H` successor ownership before attempting token-slot state advancement. The state transitions caught and ignored `CampaignOwnershipError`, so a successor could exist while its slot did not truthfully reach `WINDOW_1H_CONTINUING`.

That allowed an impossible partial handoff state and was not covered by the restored historical first-hour tests.

## Repair implemented

### Canonical atomic owner

`src/printer_v1/operator_cli/campaign_ownership.py` now owns `persist_standard_first_hour_handoff_set(...)`.

For a first authoritative evaluation it atomically:

1. requires exactly two handoff candidates and exactly the campaign's two token slots;
2. validates campaign/run/cycle/slot/token/pair/mint/pair-identity/lifecycle identity;
3. accepts only legitimate pre-handoff token-slot states (`SELECTED`, `WINDOW_15M_ACTIVE`, `WINDOW_15M_CLOSED`);
4. validates the exact owned 15m predecessor, root lifecycle, and memory-window binding;
5. requires `CLEAN_PROMOTED` predecessor ownership for a token that will continue;
6. persists the complete immutable `CONTINUATION_4A` decision set;
7. creates each required exact `WINDOW_1H` successor with the same root 15m lifecycle and exact predecessor id;
8. advances each continuing slot through the remaining valid prefix states to `WINDOW_1H_CONTINUING`;
9. reads back and verifies the complete persisted state before commit;
10. rolls the transaction back on any ownership/integrity conflict.

### Operational caller

`src/printer_v1/operator_cli/operational_selective_1h.py` no longer performs separately committed successor persistence followed by swallowed state transitions. First-evaluation persistence routes through the canonical atomic ownership helper.

Replay/idempotency remains a separate read/verify path. The strict state validation is intentionally inside the first-evaluation atomic writer, not globally before replay. Therefore an already-successful handoff at `WINDOW_1H_CONTINUING` can be evaluated idempotently and conflicting recomputation still fails against the immutable object hash/payload.

## TDD evidence

### Valid RED

- Exact head: `36acb61b6f0e3c396fb9be09ccdf9519c48da92e`
- Workflow run: `31344130452`
- Job: `93322772727`
- Compilation: PASS
- Result: 38 tests run; 37 PASS; exactly 1 intended failure.
- Intended failure: `test_conflicting_slot_state_fails_before_any_handoff_side_effect` because the old code did not raise on an impossible pre-first-evaluation `WINDOW_1H_CONTINUING` state.

An earlier RED attempt used an invalid `FAILED` fixture without required terminal metadata and was rejected as TDD evidence rather than being counted.

### First GREEN attempt and correction

The initial atomic implementation correctly passed the new strict handoff tests but an early global slot-state preflight prevented legitimate replay/idempotency and changed the expected conflicting-recomputation failure path. That attempt was not accepted as closeout proof.

The correction removed only that premature nine-line global guard. Strict first-evaluation validation remains inside the atomic owner.

### Final GREEN

- Exact implementation head: `970960b02c743dbc594524701aa16bc8fc144c45`
- Workflow run: `31345095990`
- Job: `93325438527`
- Compilation: PASS
- Focused result: `Ran 38 tests ... OK`
- Total: 38/38 PASS, 0 failures, 0 errors.

The proof includes:

- two checkpoint-specific strict handoff tests;
- four standard-first-hour clean-object/reporting alignment tests;
- all 32 current operational first-hour tests.

It proves:

- canonical `CONSOLIDATION` and `NO_PUMP` predecessors continue;
- exact successor token/pair/root-lifecycle/predecessor identity;
- both successful slots reach `WINDOW_1H_CONTINUING`;
- impossible first-evaluation slot state fails before continuation-object or successor-window side effects;
- episode-only predecessor remains fail-closed;
- B.2 identity/freshness/provenance safety gates remain intact;
- duplicate continuation is idempotent;
- conflicting recomputation fails closed;
- repeated campaign barrier creates no duplicate Scheduler work;
- genuine 1h clean-object promotion remains covered by the existing alignment suite;
- 5m remains unable to satisfy 1h/E2Z authority.

The independent first-hour lifecycle focused workflow also passed on the same exact implementation head.

## Scope verification

From checkpoint baseline `6a031b75...` through proven implementation `970960b...`, the durable branch changes only:

- Checkpoint-1 audit document;
- Checkpoint-1 repair design document;
- `src/printer_v1/operator_cli/campaign_ownership.py`;
- `src/printer_v1/operator_cli/operational_selective_1h.py`;
- `tests/test_v2_9_8b_post_dtw100_checkpoint1_15m_1h_handoff.py`.

Disposable workflows and trigger files are not part of the proven durable implementation history after cleanup.

## Money-usefulness contribution

A later 1h memory can now be attributed to the exact same governed token lifecycle that produced its clean 15m predecessor. Printer cannot silently claim first-hour continuation while its ownership state remains at an earlier lifecycle stage. This protects trajectory truth, corpus identity, and future clean-memory comparison quality.

## What this checkpoint improves

- fail-closed 15m→1h ownership transition;
- atomic first-evaluation persistence;
- exact successor/predecessor/root-lifecycle identity;
- truthful `WINDOW_1H_CONTINUING` token state;
- preserved replay/idempotency;
- reuse of canonical campaign ownership instead of duplicating 15m machinery.

## What this checkpoint still does not unlock

- no real first-hour runtime;
- no one-use first-hour authorization or wrapper;
- no provider/RPC/source fetching;
- no authoritative DB mutation outside offline disposable tests;
- no proof yet that continuation initialization and the remaining 45-minute schedule are correct as one current composition — Checkpoint 2 owns that;
- no 1h runtime close proof — later checkpoints own it;
- no 4h activation;
- no retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL;
- no wallet, key, signing, real funds, live execution, paid APIs, scoring/ranking/confidence/weighting, embeddings, or vectors.

## Functionality Risks / Setbacks / Efficiency Blockers

- The atomic helper is intentionally narrow and should not be generalized into unrelated campaign state changes without a new design.
- Successful ownership handoff does not prove the Scheduler plan starts at the correct 15m close anchor; Checkpoint 2 must audit that separately.
- The current module/function names retain historical `selective_1h` wording even though 15m→1h is now standard. Renaming is unnecessary scope and was not performed.
- Source/Scheduler runtime remains locked, so this is an offline composition proof rather than a live first-hour proof.

## Next checkpoint

`Checkpoint 2 — WINDOW_1H continuation initialization`

Audit the current path from the successful Checkpoint-1 handoff into the remaining 45-minute continuation plan. Reuse existing lifecycle-continuity, cadence-policy, Source Governor, and Central Scheduler owners. Verify exact close anchor, exact 2700-second successor duration, first-continuation-snapshot timing, same token/pair/lifecycle identity, two-token scheduling/fairness, and no fresh one-hour clock. If a blocker is found, stop at Checkpoint 2 and complete audit → repair design → implementation → focused proof → closeout before advancing.
