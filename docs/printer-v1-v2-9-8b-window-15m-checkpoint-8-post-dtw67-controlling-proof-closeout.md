# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — Post-DTW67 Controlling Proof Closeout

Date: 2026-08-08

Linear: `DTW-68`

Approved immutable proof HEAD:

`7584b846fbe0fa79e8c9ce6fe35dfacbf7e07575`

Proof ID:

`C8_REPROOF_AFTER_DTW67_20260808`

Actions run:

`31239317931`

Job:

`93057459320`

Artifact:

`checkpoint8-post-dtw67-reproof-7584b846`

Artifact ID:

`9016671724`

Artifact ZIP SHA-256:

`d16c5da1e082b6d4fd08e3577966a7f8b684365e9c5e3a0d078939f72eb8cda4`

Frozen evidence SHA-256:

`cd5dbeff0d8e1bf94bbe9bb856757b87de0f5fe57eb732d1c75427b2a4cec469`

Disposable proof DB SHA-256:

`517bf536d212edb0381a8aacd598de53e52dcbf4f6fcbedb79faffaf01800926`

## Verdict

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_POST_DTW67_CONTROLLING_PROOF_PASS`

Checkpoint 8 closes PASS.

The single explicitly authorized controlling campaign reached `CAMPAIGN_PASS`, froze complete evidence, and the repaired mandatory independent inspector independently reconstructed that same frozen proof and returned `CHECKPOINT8_INDEPENDENT_INSPECTION_PASS`.

No second proof, retry, rerun, resume, restart, successor, or replacement proof identity was created.

## One-shot authorization consumption

The operator authorized exactly one fresh bounded Checkpoint 8 controlling proof.

That authorization was consumed when the controlling harness entered execution in Actions run `31239317931` / job `93057459320`.

The frozen sentinel records:

- `attempt_ordinal = 1`;
- `git_head = 7584b846fbe0fa79e8c9ce6fe35dfacbf7e07575`;
- `proof_id = C8_REPROOF_AFTER_DTW67_20260808`;
- `sentinel_schema = CHECKPOINT8_CONTROLLING_ATTEMPT_V1`.

The harness exit code was `0`. The independent inspector exit code was `0`.

The temporary proof PR was closed unmerged and the temporary proof workflow was deleted after the consumed run.

## Frozen identities

- execution: `20260808T042326Z-54ca64838a43`;
- campaign: `20260808T042326Z-54ca64838a43-campaign`;
- campaign run: `20260808T042326Z-54ca64838a43-campaign-run`;
- configuration: `20260808T042326Z-54ca64838a43-configuration`;
- cycle: `20260808T042326Z-54ca64838a43-cycle`;
- authoritative factory run: `9dd67856-54e4-44b3-9c81-d89ac1da32f3`;
- supervision: `20260808T042326Z-54ca64838a43-supervision`.

The campaign-run -> factory-run binding was independently reconstructed from the canonical durable bridge rather than inferred from string identity.

## Controlling campaign PASS

The controlling campaign froze:

- `campaign_pass = true`;
- `campaign_acceptance_verdict = CAMPAIGN_PASS`;
- `operational_lifecycle_pass = true`;
- `clean_memory_outcome_pass = true`;
- runtime terminal status `COMPLETED`;
- first terminal cause `COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED`;
- exactly two distinct selected targets;
- exactly two terminal ordinary `WINDOW_15M` lifecycles;
- complete cadence and closeout for both token lifecycles;
- both persisted slot dispositions terminalized to `COOLDOWN`.

Selected targets:

1. mint `5aNJBy3n3AjsGZ2qvQFKfV6BhKSTQU6MXxN2sjGu8nei`
   - pair `8Dekc3AoJchx4ZxENPP1M6HmgAi83FmZNQnv3enwKurq`
   - memory-window row `1`;
2. mint `Hx7d5gD9Lt23A7BQkBxiE6rnfFuw9ARsHSLGN6Acvcbb`
   - pair `7CQEubcAzwy3Nhh1v9QXYyD4vXp6JgwdRZYkybbfdRFs`
   - memory-window row `2`.

Each lifecycle completed eight scheduled snapshot steps plus one successful close, with nine observations at the memory-window layer and zero missing snapshots.

## Memory-layer truth

The two campaign-owned windows are:

- `WINDOW_15M`;
- `support_only = 0`;
- `window_state = CLEAN_PROMOTED`;
- terminal.

The referenced `printer_memory_windows` rows truthfully remain:

- `window_status = WINDOW_CLOSED`;
- `memory_status = PARTIAL_MEMORY`;
- `memory_quality_label = PARTIAL_MEMORY`;
- `data_quality_label = CLEAN_DATA`;
- `do_not_train = 0`;
- expected observations `9`;
- actual observations `9`;
- missing observations `0`;
- `coverage_state = COVERAGE_PASS`.

This is not a contradiction and was not relabeled by the proof.

Clean promotion is independently proven by the next durable layer:

- exactly two canonical `WINDOW_15M_CLEAN_MEMORY` episodes;
- both `COMPLETE`;
- both `memory_status = CLEAN_MEMORY`;
- both `memory_quality_label = CLEAN_MEMORY`;
- both `data_quality_label = CLEAN_DATA`;
- both `do_not_train = 0`;
- exactly two linked `STATIC_CONDITION_SUMMARY` fingerprint rows with exact payload identity.

## Durable graph and Scheduler proof

Read-only inspection found the exact current graph:

- 1 campaign-run row;
- 1 authoritative factory run;
- 18 factory-run steps;
- 28 campaign Scheduler-work rows;
- 28 Scheduler jobs;
- 8 discovery-work rows;
- 2 campaign windows;
- 2 memory windows;
- 2 clean episodes;
- 2 fingerprints.

Scheduler terminal composition:

- 26 `SUCCEEDED` jobs;
- 2 `CANCELLED` jobs;
- 8 `DISCOVERY_SELECTION` work rows succeeded;
- 2 `FIRST_15M_HANDOFF` rows cancelled as part of the accepted bounded ownership lifecycle;
- 18 `WINDOW_LIFECYCLE` rows succeeded;
- zero active Scheduler jobs after cleanup;
- zero locked Scheduler jobs after cleanup.

The terminal supervision row is `TERMINAL / COMPLETED` with completed cleanup and released lease.

## Source Governor and six-unit accounting

Independent source-accounting reconstruction passed without owner-name heuristics.

Six-unit totals:

- `SOURCE_TRANSPORT_OPERATION = 46`;
- `SOURCE_RESPONSE_BYTES = 9211`;
- `NORMALIZED_SOURCE_ROWS = 128`;
- `LOCAL_VALIDATION_STEP = 93`;
- `SCHEDULER_WORK_ITEM = 28`;
- `LIFECYCLE_RESERVED_TRANSPORT_OPERATION = 28`.

Lifecycle reservation outcomes:

- reserved: `28`;
- attempted: `26`;
- succeeded: `26`;
- failed: `0`;
- malformed linkage: `0`;
- duplicate reservation linkage: `0`;
- unexpected outcome: `0`;
- complete: `true`.

Owner/action-local identity sets are exact and non-vacuous for source transports, local validation, Scheduler work, and lifecycle reservations.

## REPORT_ONLY replay

The canonical replay result is:

- `status = REPLAYED`;
- `mode = REPORT_ONLY`;
- `source_calls = 0`;
- `scheduler_runtime_calls = 0`;
- `database_writes = 0`;
- `replay_new_source_calls = 0`;
- `replay_new_scheduler_calls = 0`;
- canonical `requested_identity` exactly matches campaign/run;
- nested full-run campaign/configuration/cycle/factory/execution/supervision identity exactly matches the independently reconstructed graph;
- nested proof expectation exactly matches proof ID and fixture manifest;
- no automatic retry, manual rerun, provider execution, restart, resume, or successor permission.

## Independent inspection PASS

The repaired independent inspector returned:

`CHECKPOINT8_INDEPENDENT_INSPECTION_PASS`

with `pass = true`.

Independent findings include:

- canonical migration count `52` and exact migration head `052_memory_observation_eligibility_layers.sql`;
- SQLite integrity `ok`;
- foreign-key violations `0`;
- database opened read-only and byte-stable;
- exact two terminal `WINDOW_15M` mints;
- both clean-memory episode chains present;
- both fingerprints present and identity-linked;
- Source Governor accounting exact;
- Central Scheduler correspondence exact;
- zero active/locked/orphan current work;
- lease released;
- no retry/rerun/resume/restart/successor;
- campaign/run/fixture identity exact.

## Safety and preserved locks

The fresh proof also froze:

- fixture transport operations: `57`;
- external network attempts: `0`;
- DB integrity: `ok`;
- FK violations: `0`;
- protected capability deltas: all `0`;
- `WINDOW_1H = 0`;
- `WINDOW_4H = 0`;
- `WINDOW_12H = 0`;
- `WINDOW_24H = 0`;
- automatic retry: `0`;
- restart: `0`;
- resume: `0`;
- successor: `0`;
- lease released: true;
- lease lock absent: true.

No authoritative persistent DB mutation, provider/network fallback, retrieval, paper decision, BUY/SELL/HOLD, position, trade event, paper trade audit, PnL, wallet/private-key/signing/live execution, paid API, scoring/ranking/confidence/weighted logic, embedding, or vector path was activated.

## Money-usefulness contribution

Checkpoint 8 now demonstrates that Printer can complete the bounded ordinary `WINDOW_15M` public-composition path, produce clean promoted memory evidence for two distinct tokens, preserve truthful lower-layer PARTIAL_MEMORY semantics, reconcile Source Governor and Central Scheduler ownership, close with zero residue, replay without work, and have all of those facts independently reconstructed from durable evidence.

That materially improves trust in the memory corpus that later paper-only comparison lanes may eventually consume, while preserving the rule that no retrieval or financial action is allowed merely because memory was generated successfully.

## What this proof improves / proves

- The rolling `WINDOW_15M` readiness-hardening sequence has reached its intended final complete-composition proof.
- The final campaign acceptance layer and independent inspector agree on the same campaign/run/factory/memory/source/Scheduler identities.
- The previously repaired accounting, packaging, disposable-DB, fixture, policy, Scheduler, source-link, clean-promotion, and identity-presence boundaries all hold together in one fresh controlling proof.
- Checkpoint 8 can therefore close PASS rather than campaign-only PASS or honest-blocked.

## What this proof still does not unlock

This PASS does not by itself unlock:

- another Checkpoint 8 proof;
- automatic production Memory Factory runtime;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, or `WINDOW_24H`;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- paper positions;
- trade events;
- paper trade audits;
- PnL;
- wallets, private keys, signing, live execution, or real funds;
- paid APIs;
- scoring, ranking, confidence percentages, weighted decision logic, embeddings, or vectors.

## Functionality Risks / Setbacks / Efficiency Blockers

- A proof PASS must not be treated as production activation permission.
- The clean-memory episode layer must not be collapsed into or used to rewrite the truthful PARTIAL_MEMORY state of the underlying memory-window rows.
- The one-shot proof authorization is consumed and must not be reused for another run.
- The active V2 build-order document still contains older V2-9.8B candidate-acquisition sequencing text that predates the completed rolling Checkpoint hardening work. Starting that older sub-lane automatically from this closeout would risk roadmap drift.
- `WINDOW_1H` remains separately blocked from automatic progression by the explicit later E2Q/audit-repair rule; this PASS does not change that.

## Next permitted step

Close the Checkpoint 8 / rolling `WINDOW_15M` readiness-hardening tracker and perform a read-only active-roadmap/current-state reconciliation before selecting any new runtime or capability lane.

That reconciliation must compare the current completed Checkpoint state against the active Printer V1 source stack and identify the true next V2-9.8B sub-lane without reviving superseded historical work or prematurely activating longer windows, retrieval, decisions, or trading.

No new operational campaign or capability is authorized by this closeout.

## Stop condition

Checkpoint 8 closes PASS and the one-shot proof lane stops here.
