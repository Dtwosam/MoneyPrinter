# Printer V1 V2-9.8B Post-DTW100 1h Checkpoint 3 Remaining-45m Collection Implementation / Focused Proof Closeout

## Verdict

`V2_9_8B_POST_DTW100_1H_CHECKPOINT_3_REMAINING_45M_COLLECTION_IMPLEMENTATION_FOCUSED_PROOF_PASS`

Checkpoint 3 is complete for the offline current-state composition boundary. The existing governed continuation collector remains the canonical data path; the repair synchronizes campaign lifecycle truth and lifecycle-reservation accounting around that path without changing cadence, source execution, request ceilings, or memory semantics.

This PASS does not authorize a live first-hour run, source fetching, authoritative-DB operation, or any later capability.

## Baseline and lane boundary

- Checkpoint-2 closeout baseline: `7e489ad8665fce4c0fcfe04e98d5c2d215d6253e`.
- Checkpoint-3 branch: `agent/v2-9-8b-post-dtw100-1h-checkpoint3-remaining-45m-collection`.
- Starting boundary: an exact owned `WINDOW_1H` successor already exists and its 2700-second continuation Scheduler work is already planned and projected to that exact campaign window.
- Scope: execution-state truth and accounting during the remaining 45-minute collection only.

No discovery/selection re-audit, live source call, Scheduler runtime proof, authoritative DB mutation, authorization, wrapper execution, 4h activation, retrieval, decision, position, trade, audit, or PnL work occurred.

## Audit findings

The existing continuation collection machinery was reusable and did not require a second collector. `CONTINUATION_SNAPSHOT` already reuses the canonical snapshot execution and persistence path, exact token/pair identity, Source Governor execution, Central Scheduler jobs, and the established bounded first-hour cadence.

Three integration gaps were found around that working collector:

1. campaign Scheduler ownership rows could remain `PENDING` after their canonical Scheduler jobs advanced to `RUNNING` or a terminal state;
2. the exact owned `WINDOW_1H` campaign window could remain `PLANNED` while continuation evidence was already being collected;
3. continuation snapshot/close work did not pass through the existing lifecycle-reservation observation record path used by 15m lifecycle work.

These were classified as one bounded collection-state/accounting synchronization repair. No evidence or safety gate was weakened.

## Repair design and implementation

The repair stayed in the canonical factory owner, `src/printer_v1/operator_cli/one_command_15m_factory.py`, and reuses existing campaign/Scheduler ownership and state-transition authorities.

Implementation commit:

`5fbd88c0e9896779c38ab392830544198d862f30` — `Synchronize first-hour collection ownership state`

The implementation:

- synchronizes an existing V2 `WINDOW_LIFECYCLE` ownership projection from canonical Scheduler truth after claim, completion, failure, and cancellation;
- advances the exact owned `WINDOW_1H` from `PLANNED` to `COLLECTING` when its first `CONTINUATION_SNAPSHOT` is actually claimed;
- fails closed on ambiguous or conflicting campaign/Scheduler/window ownership;
- blocks only the affected token's exact first-hour window on token-local continuation collection failure while preserving the peer token;
- cancels remaining exact owned first-hour windows on a run-wide non-normal stop;
- factors the existing lifecycle-reservation record construction into one helper and applies the same accounting vocabulary to `CONTINUATION_SNAPSHOT` and `CONTINUATION_CLOSE`;
- preserves the established reservation shape, while adding categorical operation families `CONTINUATION_SNAPSHOT_OBSERVATION` and `CONTINUATION_CLOSE_OBSERVATION`.

No new source adapter, collector, Scheduler, retry loop, table, migration, score, rank, confidence, weighted logic, embedding, or vector system was created.

## Valid RED proof

Corrected RED head:

`e03d26058ed65dbb2496d6f49d9e449a1f09099d` — `Fix checkpoint 3 RED fixture API usage`

Disposable PR: #98, closed unmerged.

Focused RED workflow:

- run: `31347504985`
- job: `93332064633`
- compile: PASS
- tests: 79 total; 76 passed; exactly 3 Checkpoint-3 errors
- intended missing hooks: campaign Scheduler-state synchronization and continuation lifecycle-reservation construction

All Checkpoint-1, Checkpoint-2, standard-first-hour, operational-first-hour, and directly affected Scheduler-ownership tests remained green. The independent first-hour policy workflow on the same RED head also passed.

Earlier fixture-construction failures were rejected and were not counted as RED evidence.

## Focused GREEN proof

Exact implementation head:

`5fbd88c0e9896779c38ab392830544198d862f30`

Disposable PR: #101, closed unmerged.

Focused GREEN workflow:

- run: `31347958318`
- job: `93333332362`
- compile: PASS
- tests: `79/79 PASS`

The proof includes:

- Checkpoint-3 collection-state/accounting tests;
- Checkpoint-2 continuation-initialization tests;
- Checkpoint-1 clean-15m-to-1h handoff tests;
- standard first-hour harness/reporting alignment;
- the operational first-hour harness;
- directly affected campaign Scheduler-ownership schema/contract tests.

The three Checkpoint-3 tests prove:

1. Scheduler claim/success keeps campaign ownership state truthful, the exact `WINDOW_1H` becomes `COLLECTING`, and the snapshot remains exact-token/exact-pair governed evidence;
2. token-local continuation failure/cancellation terminalizes only the affected token's owned work/window and leaves the peer continuation intact;
3. continuation snapshot and close steps reuse lifecycle-reservation accounting with distinct categorical operation families.

Independent first-hour policy workflow on the same implementation head also passed.

## Money-usefulness contribution

This repair makes the remaining 45-minute evidence path more trustworthy without replacing its already-proven data collector. Printer can now keep its campaign graph, Scheduler truth, and resource-accounting observations aligned while it accumulates the evidence needed for a genuine first-hour memory. That reduces the risk of learning from a lifecycle whose operational records falsely say work was merely planned or pending when it had actually executed.

It does not prove profitability or authorize any financial action.

## What this checkpoint improves

- Exact campaign Scheduler ownership now follows canonical Scheduler state during continuation execution.
- The first-hour campaign window truthfully enters `COLLECTING` when collection starts.
- Token-local collection failure remains token-local at the campaign window/work level.
- Continuation source work uses the same lifecycle-reservation observation contract as the 15m lifecycle instead of bypassing it.
- Existing exact-pair, Source Governor, Scheduler, persistence, and cadence owners are reused rather than duplicated.

## What this checkpoint still does not unlock

- no live first-hour execution;
- no first-hour one-shot authorization or wrapper;
- no provider/source fetching;
- no authoritative DB mutation or operational memory generation;
- no 4h activation;
- no 12h/24h work;
- no retrieval;
- no paper decisions;
- no BUY/SELL/HOLD;
- no paper positions, trade events, paper-trade audits, or PnL;
- no live wallet, private keys, real funds, signing, or execution;
- no paid APIs, scoring, ranking, confidence, weighted logic, embeddings, or vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only and has no independent continuation, memory, retrieval, decision, or financial authority.

## Proof still required before operational use

Checkpoint 3 must be followed by the remaining end-to-end first-hour checkpoints. In particular, Checkpoint 4 must audit the genuine 1h close boundary before the project can claim the full first-hour lifecycle is compositionally ready. A fresh full-chain rereadiness review is still required after all checkpoints pass and before any one-use authorization is prepared.

## Functionality Risks / Setbacks / Efficiency Blockers

- State synchronization is now explicit, but later close-boundary code must prove lawful `COLLECTING -> CLOSE_PENDING` behavior rather than relying on retrospective terminal reconciliation.
- The current focused proof is offline/deterministic; it does not prove wall-clock provider/runtime behavior.
- Continuation reservation records are verification/accounting observations; they do not themselves reserve or expand Source Governor budget.
- Any later Scheduler ownership drift must remain fail-closed; callers must not overwrite canonical Scheduler truth with narrative state.
- The canonical factory remains large; this checkpoint deliberately avoided a broad refactor because reuse and narrow repair are safer than introducing parallel orchestration.

## Next checkpoint

`V2-9.8B Post-DTW100 1h Checkpoint 4 — 1h Close Boundary`

Checkpoint 4 starts only after exact-closeout-HEAD verification of this checkpoint. It must audit the remaining-45m deadline/close transition, final continuation close evidence, exact `WINDOW_1H` close state, Scheduler close cleanup, cadence/coverage boundary, and genuine first-hour memory-window closure. It must reuse the proven 15m/shared close machinery where applicable and must not perform a live run or memory-promotion implementation belonging to later checkpoints.
