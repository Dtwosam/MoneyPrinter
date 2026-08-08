# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — Post-DTW53 Controlling Proof Closeout

Date: 2026-08-08

Linear: `DTW-54`

Approved immutable proof HEAD:
`ee32b325f96c672e21247ac43395290931781da5`

Proof ID:
`C8_REPROOF_AFTER_DTW53_20260808`

Actions run: `31231155572`

Job: `93035124603`

Artifact: `checkpoint8-post-dtw53-reproof-ee32b325`

Artifact ID: `9014056017`

Artifact ZIP SHA-256:
`0022488af2c99d3ba36c205af3b19fae689af762ddc2a7610a7b5cdf1a237bd3`

Frozen evidence SHA-256:
`a016b9fe7d7a71f050b56e7f5473d6b1190444053df3305cd7027edc7f09c8a5`

## Verdict

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_POST_DTW53_CONTROLLING_CAMPAIGN_PASS_INDEPENDENT_INSPECTION_BLOCKED`

The authorized one-shot controlling campaign itself reached `CAMPAIGN_PASS` and froze valid evidence. Checkpoint 8 as a whole is not closed PASS because the mandatory independent inspection then failed with:

`CURRENT_RUN_GRAPH_MISSING`

The authorization is consumed. No retry, rerun, resume, restart, successor, or second proof identity is authorized.

## One-shot consumption

The proof used exactly one controlling harness invocation.

The atomic sentinel records:

- `attempt_ordinal = 1`
- `git_head = ee32b325f96c672e21247ac43395290931781da5`
- `proof_id = C8_REPROOF_AFTER_DTW53_20260808`
- schema `CHECKPOINT8_CONTROLLING_ATTEMPT_V1`

The harness exited `0` and froze the proof summary exactly once.

The temporary GitHub Actions runner was deleted after the consumed run and PR #46 was closed unmerged.

## Controlling campaign evidence

Frozen identities:

- campaign: `20260808T005025Z-21b2b5c7cf1b-campaign`
- campaign run: `20260808T005025Z-21b2b5c7cf1b-campaign-run`
- factory run: `5ad2b0e6-7d45-4ce1-9017-09f44c744695`
- cycle: `20260808T005025Z-21b2b5c7cf1b-cycle`

Controlling campaign result:

- `campaign_acceptance_verdict = CAMPAIGN_PASS`
- `campaign_pass = true`
- `operational_lifecycle_pass = true`
- `clean_memory_outcome_pass = true`
- runtime status `COMPLETED`
- first terminal cause `COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED`
- exactly 2 selected targets
- exactly 2 terminal `WINDOW_15M` lifecycles
- 2 episode rows
- 2 fingerprint rows
- cadence coverage complete for both token lifecycles
- both slots terminalized to `COOLDOWN`

The full-run campaign acceptance object has no failing checks and no compensation blockers. In particular:

- `owner_action_local_equal_non_vacuous = true`
- `reservation_attempt_outcomes_complete = true`
- `all_mandatory_stages_sealed = true`
- `scheduler_ownership_correspondence_exact = true`
- `scheduler_transition_coverage_complete = true`
- `exactly_one_matching_factory_binding = true`
- `runtime_terminal_completed = true`
- `zero_active_owned_work_after_cleanup = true`
- `zero_forbidden_deltas = true`

DTW-53's two repaired accounting defects therefore held under the fresh complete composition.

Six-unit totals:

- `SOURCE_TRANSPORT_OPERATION = 46`
- `SOURCE_RESPONSE_BYTES = 9211`
- `NORMALIZED_SOURCE_ROWS = 128`
- `SCHEDULER_WORK_ITEM = 28`
- `LIFECYCLE_RESERVED_TRANSPORT_OPERATION = 28`
- `LOCAL_VALIDATION_STEP = 93`

Lifecycle reservation outcomes:

- reserved: 28
- attempted: 26
- succeeded: 26
- failed: 0
- malformed linkage: 0
- duplicate reservation linkage: 0
- unexpected outcomes: 0
- complete: true

## Safety and lock preservation

- fixture transport operation count: 57
- network attempt count: 0
- report-only replay zero-work: true
- DB integrity: `ok`
- foreign-key violations: 0
- protected capability deltas: 0
- `WINDOW_1H = 0`
- `WINDOW_4H = 0`
- `WINDOW_12H = 0`
- `WINDOW_24H = 0`
- active Scheduler jobs after cleanup: 0
- locked Scheduler jobs after cleanup: 0
- automatic retries: 0
- restart: 0
- resume: 0
- successor: 0
- lease released: true
- lease lock absent: true

No provider/network fallback, authoritative DB mutation, retrieval, paper decision, BUY/SELL/HOLD, position, trade, audit, or PnL path was activated.

## Independent inspection blocker

The required independent inspector exited `1` before it could produce a passing independent-inspection artifact.

Exact first error:

`Checkpoint8IndependentInspectionError: CURRENT_RUN_GRAPH_MISSING`

Read-only inspection of the frozen proof DB establishes:

1. `printer_memory_factory_campaign_runs` contains exactly one campaign-run row:
   - campaign run `20260808T005025Z-21b2b5c7cf1b-campaign-run`
   - authoritative factory run `5ad2b0e6-7d45-4ce1-9017-09f44c744695`
2. `printer_memory_factory_runs` contains exactly that factory run and it is `COMPLETED`.
3. `printer_memory_factory_run_steps` contains 18 rows, all correctly keyed by the factory-run UUID `5ad2b0e6-7d45-4ce1-9017-09f44c744695`.
4. The independent inspector takes the frozen summary's campaign `run_id`, then calls `_rows_for_identity()` directly on `printer_memory_factory_run_steps` using that campaign-run identity.
5. `printer_memory_factory_run_steps` has only a `run_id` column and that column is factory-run identity, not campaign-run identity.
6. Therefore the inspector finds zero rows and raises `CURRENT_RUN_GRAPH_MISSING` even though the exact durable campaign→factory binding and run graph are present.

This is evidence of an independent-inspection identity-projection gap, not evidence that the controlling campaign lacked a run graph.

No repair is authorized in this proof lane.

## Money-usefulness contribution

The fresh one-shot proof demonstrates that the repaired final campaign acceptance layer can now truthfully accept the complete two-token 15m composition without weakening owner/action-local equality, reservation accounting, cadence, Scheduler ownership, cleanup, or downstream locks.

The remaining blocker is in independent verification of that already-durable graph. Fixing it later, if approved, would improve confidence that a campaign PASS can be independently reconstructed rather than trusted only from its frozen campaign report.

## What this proof improves / proves

- DTW-53's two exact accounting repairs survive a full fresh bounded composition.
- campaign acceptance reaches `CAMPAIGN_PASS` with zero failing checks.
- two terminal 15m lifecycles are durably present.
- final safety/cleanup and report-only replay remain bounded and zero-work where required.
- downstream financial/retrieval capabilities remain untouched.

## What this proof does not unlock

This closeout does not unlock:

- another C8 proof;
- operational `WINDOW_15M` activation outside a later approved boundary;
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
- scoring, ranking, confidence, weighted logic, embeddings, or vectors.

## Functionality Risks / Setbacks / Efficiency Blockers

- Checkpoint 8 cannot close PASS until the independent inspector can resolve the authoritative campaign-run→factory-run binding and reconstruct the current run graph without guessing.
- The inspector must not solve this by treating campaign-run ID as factory-run ID, by broad unscoped row search, or by weakening current-run identity checks.
- The existing exact one-to-one durable binding should be the starting audit target; any ambiguity or multiple binding must remain fail-closed.
- The consumed proof must remain historical evidence and must not be rerun or rewritten.

## Next permitted step

Static/read-only audit of the independent-inspection campaign-run→factory-run graph projection.

That audit may inspect the frozen artifact, inspector code, schema, existing tests, and exact binding rows. It may not modify production/inspection code, run another C8 proof, contact providers, mutate the authoritative DB, activate runtime, or unlock downstream capabilities.
