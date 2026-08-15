# Printer V1 V2-9.8B — Historical Execution Reconciliation Implementation Closeout

## Verdict

`V2_9_8B_HISTORICAL_EXECUTION_RECONCILIATION_IMPLEMENTATION_CLOSEOUT_PASS_READY_FOR_EXACT_DISPOSABLE_COPY_PROOF`

## Lane identity

- Repair closeout parent: `1b5a8cdf0dad74b8fa4730d090abfc8d6cd184a1`
- Audit/design commit: `cd2cbc061fcd1feee31452a182705b2b8fa76261`
- Local-evidence/queue-amended design: `7a78084a6fe683c2f0282d7e1b4df3f8920cadf8`
- Historical execution: `20260814T172224Z-490856f405bf`
- Historical factory run: `ed0fa279-38e6-401b-8b34-0a9531a9c720`
- Main verified implementation commit: `72d4f3d05b76ac773226e83b035f00870a73ab22`
- Final fail-closed safety commit: `bb680064dbb27a6d9bcd3cd39f475b312efa00dd`
- Branch: `agent/v2-9-8b-historical-execution-reconciliation`

The authoritative Mac database and historical artifact root were not mutated by this implementation lane.

## Local evidence binding

The read-only Mac-local evidence pass returned:

`LOCAL_HISTORICAL_RECONCILIATION_EVIDENCE_PASS`

It re-established the exact pre-reconciliation DB identity, 55-migration schema head, clean integrity/FK state, dead process/expired lease state, exact campaign/run/cycle/supervision/factory identities, exact slot order, queue ids 58/59, zero windows/steps/Cycle-2 attempts, terminal Scheduler ownership, immutable artifact SHA bindings and the controlling historical cause:

`FourTokenFactoryAdapterError: cycle terminal reconciliation requires a fresh transaction`

Migration-056 provenance is absent and remains forbidden for this historical execution.

## What was implemented

`operational_campaign_recovery.py` now contains a deliberately non-generic `HistoricalFourTokenRecoveryContract` and `reconcile_exact_historical_four_token_execution()`.

The contract pins:

- exact execution id;
- exact factory-run id;
- exact pre-reconciliation DB SHA;
- exact pre-campaign backup SHA;
- exact two mints in slot order;
- exact queue ids 58/59;
- exact Scheduler job ids 2011–2020;
- exact historical artifact SHA256 values;
- exact preserved first terminal cause.

The preflight fails closed on any mismatch in DB identity, migration head, integrity/FK state, artifacts, ownership states, factory config binding, slot order, queue linkage/state, windows/steps/attempts, Scheduler ownership/locks, proof/discovery activity, lease ownership/expiry or live Printer process.

The final safety amendment also proves there is **no nonterminal discovery batch for this exact campaign/run before any write begins**. This prevents a reused cleanup owner from mutating an unexpected discovery-batch row and only discovering that fact after the mutation.

## Canonical mutation composition

The implementation composes existing canonical owners in the approved order:

1. `reconcile_four_token_cycle_terminal(..., terminal_phase=None, run_status='FAILED')`
   - terminalizes Cycle 1;
   - moves the two slots to `MANUAL_REVIEW`;
   - never fabricates migration-056 provenance.

2. `cleanup_campaign_supervision(..., terminal_status='FAILED')`
   - terminalizes campaign/run supervision ownership;
   - records cleanup/release timestamps;
   - releases the exact expired lease.

3. `reconcile_campaign_terminal(..., lifecycle_started=False, factory_run_id=<exact historical run>)`
   - idempotently observes already-terminal campaign/run/cycle ownership;
   - moves tracking queue ids 58/59 from `QUEUED` to `SKIPPED` with `MANUAL_REVIEW` action and historical terminal reason;
   - closes the exact factory run to `SAFE_STOPPED`.

No shared Phase-B historical fabrication, migration, report insertion, source work, discovery run, memory generation, Scheduler runtime work, authorization or financial/retrieval capability is created.

## Exact approved mutation set

The disposable/authoritative execution is permitted to change exactly nine database row identities across seven tables:

1. historical campaign;
2. historical campaign run;
3. historical Cycle 1;
4. historical slot 1;
5. historical slot 2;
6. historical supervision;
7. tracking queue id 58;
8. tracking queue id 59;
9. historical factory run.

Filesystem mutation is limited to release/removal of the exact historical campaign lease lock.

The implementation captures per-table identity maps before mutation and rejects any post-state whose changed identities differ from that set. It also hashes every other database table and requires all non-approved tables to remain unchanged, while separately proving locked retrieval/financial table counts and row hashes are identical.

## RED evidence

### Primary historical reconciliation RED

Focused RED run `31873632401`, job `94985906021`:

- fixture successfully constructed the exact migration-055 historical shape;
- all three tests failed because `HistoricalFourTokenRecoveryContract` did not yet exist;
- no unrelated setup/import error was used as RED evidence.

### Independent preflight-safety RED

Run `31874102158`, job `94987099814` injected one exact-campaign `printer_discovery_batches` row in `PLANNED` state while rebinding the test contract to the changed disposable SHA.

Before the safety repair, reconciliation mutated that batch and only then raised:

`historical reconciliation changed unexpected tables: ['printer_discovery_batches']`

That proved the need for a pre-mutation guard rather than relying on post-hoc table diff detection.

## GREEN and bounded disposable fixture proof

### Main implementation GREEN

Run `31874003286`, job `94986856429`:

- `10 passed in 13.13s`;
- `py_compile` passed for the modified recovery owner and the shared-terminal adapter;
- `git diff --check` passed;
- temporary implementation workflows/scripts were removed before the verified commit was pushed.

The affected suite covered:

- exact historical reconciliation success;
- queue-state/live-process drift rejection;
- idempotent already-reconciled behavior;
- shared-terminal zero-attempt contract regressions;
- four-token terminal integration regressions.

### Preflight safety GREEN

Run `31874160941`, job `94987245890`:

- `11 passed in 14.51s`;
- compilation and `git diff --check` passed;
- the nonterminal discovery-batch fixture is now rejected before mutation;
- temporary safety verifier files were removed before the final commit.

## Pre-existing unrelated test drift

An earlier verification attempt also included `tests/test_v2_9_8b_1_first_operation_blocker_repair.py`. Seven tests there fail before reaching this historical recovery implementation because the old fixtures no longer satisfy evolved command API requirements (`operator_approved` and current authorization requirements). The historical reconciliation tests themselves passed in that run.

Per Printer V1 risk-based verification rules, those unrelated pre-existing fixture failures were documented and not pulled into this narrow recovery lane.

## Independent final inspection

Compared amended design `7a78084...` through final safety implementation `bb680064...`.

Final net implementation changes are limited to:

- `src/printer_v1/operator_cli/operational_campaign_recovery.py`;
- `tests/test_v2_9_8b_historical_four_token_reconciliation.py`;
- `tests/test_v2_9_8b_historical_reconciliation_preflight_safety.py`.

All temporary verifier workflows/scripts are absent from the final net tree.

The final implementation explicitly guards the nonterminal discovery-batch side-effect surface before mutation. Existing active discovery/Scheduler/proof guards already keep the other reused cleanup-owner mutation surfaces inert.

## Money-usefulness contribution

This implementation provides a bounded, evidence-pinned way to remove abandoned durable ownership from a consumed failed proof without erasing the historical failure or widening runtime authority. Clearing that residue is necessary for trustworthy future bounded memory-growth readiness, but it creates no trading capability itself.

## What this improves

- exact recovery for the one consumed historical execution;
- preservation of true slot order and first cause;
- explicit disposition of previously hidden queue residue;
- exact nine-row mutation allowlist;
- full-table unexpected-mutation detection;
- locked retrieval/financial table invariance;
- pre-mutation rejection of discovery-batch side effects;
- idempotent safe replay after successful reconciliation;
- no fabricated migration-056 runtime history.

## What remains locked

This closeout does **not** authorize:

- authoritative Mac DB reconciliation yet;
- a fresh four-token proof;
- a new proof authorization;
- six-token widening;
- 12h/24h activation;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions;
- trade events/audits;
- PnL.

All Source Governor, Central Scheduler, clean-memory and paper-only restrictions remain unchanged.

## Proof required before authoritative mutation

The next gate is an **exact disposable-copy proof using the real historical Mac database and artifact evidence**, not a synthetic fixture.

It must:

1. re-confirm the authoritative DB still has SHA `5e830af41d58325d3f9e521f1b95f697b8151113cb783cf05a2a776e204639bc` and no live owner/sidecars;
2. create a byte-identical disposable DB copy and disposable copy of the exact historical artifact/lease root;
3. run `reconcile_exact_historical_four_token_execution()` against only those disposable copies using the production contract;
4. prove the exact nine database identities changed and nothing else;
5. prove queues 58/59, campaign/run/cycle/slots/supervision/factory states are exact;
6. prove Scheduler/discovery/window/step/attempt state remains inert;
7. prove retrieval/financial hashes unchanged;
8. prove integrity/FK clean and migration-056 provenance absent;
9. prove only the disposable lease file is removed;
10. prove the authoritative DB/artifacts are byte-unchanged after the proof.

Only after that exact proof passes may authoritative reconciliation be considered.

## Functionality Risks / Setbacks / Efficiency Blockers

1. The implementation is intentionally pinned to one historical execution and cannot be reused as a generic recovery endpoint.
2. The authoritative DB is still on migration 055; migration 056 must not be applied merely to perform this cleanup.
3. The next proof depends on Mac-local byte copies and process/filesystem verification unavailable through GitHub alone.
4. The two tracking-queue rows demonstrate that the existing four-token zero-state projection does not enumerate every durable operational residue domain; that broader observability question belongs to a later audit/design lane, not this cleanup.
5. The existing old first-operation repair test file has unrelated fixture drift and remains outside this lane.

## Safest next lane

`V2-9.8B — Exact Historical Reconciliation Disposable-Copy Proof`

STOP before authoritative mutation until that proof returns PASS.
