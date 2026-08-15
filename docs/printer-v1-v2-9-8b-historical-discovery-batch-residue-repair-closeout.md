# Printer V1 V2-9.8B — Historical Discovery-Batch Residue Repair Closeout

## Verdict

`V2_9_8B_HISTORICAL_DISCOVERY_BATCH_RESIDUE_REPAIR_CLOSEOUT_PASS_READY_FOR_EXACT_DISPOSABLE_COPY_REPROOF`

## Lane identity

- Prior historical reconciliation implementation closeout: `89bbf9db68f3b5cc062514b23638a0763d7b323b`
- Discovery-batch repair design: `8a2463a962843a4110a2f08d9464af0b64347681`
- Verified repair implementation: `c5998516ff1782a2d65bebdac908543de3eafee6`
- Branch: `agent/v2-9-8b-historical-discovery-batch-residue-repair`
- Historical execution: `20260814T172224Z-490856f405bf`
- Historical factory run: `ed0fa279-38e6-401b-8b34-0a9531a9c720`
- Expected authoritative DB SHA256 before reconciliation: `5e830af41d58325d3f9e521f1b95f697b8151113cb783cf05a2a776e204639bc`

The authoritative Mac database and original historical artifacts were not mutated by this lane.

## Blocker repaired

The first real disposable-copy proof correctly blocked because the authoritative historical execution contains one live `printer_discovery_batches` row in `DISCOVERING`, while the prior recovery contract permitted only nine database row identities and required zero nonterminal discovery batches.

The read-only residue audit proved this is a historical contract-design gap, not a new runtime owner requirement:

- exactly one discovery batch belongs to the historical campaign/run;
- it is the only nonterminal discovery batch in the database;
- exactly eight linked discovery-work rows exist and all are `SUCCEEDED`;
- their Scheduler jobs are exactly 2011–2018 and already terminal/unlocked;
- zero linked/global active discovery work exists;
- `cleanup_campaign_supervision()` is the canonical owner already responsible for terminalizing this batch;
- projected canonical cleanup is exactly one discovery-batch row and zero discovery-work rows.

Classification remains `DESIGN_GAP` with secondary `CONTRACT_DRIFT`.

## Exact historical discovery-batch binding

The repair pins the exact batch identity supplied by the read-only Mac evidence:

- discovery batch id: `discovery-batch:20260814T172224Z-490856f405bf-campaign:20260814T172224Z-490856f405bf-campaign-run:20260814T172224Z-490856f405bf-cycle`
- canonical hash: `4071014af1e602c399482f07b1da357dad9ec48474edc67a6a787945838f0443`
- cycle seed hash: `092dcebfe80c993630c94d6e5b6e29fefc84194acf64e50e6b69121ec98c7288`
- campaign selection seed identity: `b4c15ed2f729d353afa0d3e6cc1ae600b9fbfc37cbd9c35733be5a30fdffb4c7`
- policy version: `V2-9.8B-FOUR-TOKEN-BOUNDED-CAPACITY-PROOF-V1`
- provider contracts: `{"direct":"V2-9.7E.11","geckoterminal":"V2-9.7D.7B.4B"}`
- git provenance identity: `live-operational:V2-9.7E.11`
- pump cursor slot/signature: null/null
- pump continuity state: `UNKNOWN`
- pre-state: `DISCOVERING`, null first cause, null terminal time.

It also pins the exact eight discovery work identities/types and Scheduler ids 2011–2018 as terminal `SUCCEEDED`.

## Implementation

`HistoricalFourTokenRecoveryContract` now binds the exact historical discovery-batch evidence rather than allowing a generic nonterminal batch.

The recovery preflight now requires:

1. exactly one batch for the historical campaign/run;
2. exact batch id and campaign/configuration/run/cycle ownership;
3. exact stable hash/policy/provider/git/cursor facts;
4. exact `DISCOVERING` pre-state with null prior cause/time;
5. exactly the eight expected linked `SUCCEEDED` discovery-work rows;
6. exactly one nonterminal discovery batch globally for this pinned historical DB identity;
7. zero active discovery/Scheduler/proof work under the existing guards.

Any missing, additional or drifted shape fails closed before reconciliation writes.

`printer_discovery_batches` is now included in `_historical_identity_maps()` keyed by `discovery_batch_id`. The post-reconciliation changed-row allowlist therefore expands from nine to exactly ten identities, with only the pinned historical discovery batch permitted as the tenth.

The canonical owner sequence remains unchanged:

1. `reconcile_four_token_cycle_terminal(...)`;
2. `cleanup_campaign_supervision(...)`;
3. `reconcile_campaign_terminal(...)`.

No new discovery terminalization owner was introduced.

The recovery requires the canonical supervision cleanup report to prove:

- `terminalized_discovery_batches == 1`;
- `cancelled_discovery_work == 0`.

The batch post-state must be exactly:

- `TERMINAL_FAILED`;
- first terminal cause `FourTokenFactoryAdapterError: cycle terminal reconciliation requires a fresh transaction`;
- non-null terminal timestamp;
- every other persisted batch column unchanged.

Migration-056 historical provenance remains forbidden.

## Replay repair

`_historical_already_reconciled()` now requires the exact pinned discovery batch to be terminal-correct before returning `V2_9_8B_HISTORICAL_FOUR_TOKEN_ALREADY_RECONCILED`.

A state where campaign/run/cycle/slots/queues/supervision/factory are terminal but the batch remains `DISCOVERING` can no longer be reported as reconciled.

## TDD evidence

### Focused RED

Run `31875840220`, job `94991325921`:

- 2 expected failures, 1 safety test passed;
- exact ten-row historical shape failed at the prior `historical nonterminal discovery batch exists` guard;
- replay-negative test proved the prior implementation could report success without considering the live batch;
- identity-drift fail-closed coverage already passed.

An earlier RED fixture attempt touched an immutable batch identity after insert; that test-only setup was corrected to create the wrong identity at insertion time. It was not used as defect evidence.

### First GREEN attempt

Run `31875957631`, job `94991606372`:

- 10 passed, 4 failed;
- production reached canonical cleanup, but the new assertion used stale report key names;
- two old historical success tests still built the obsolete no-batch fixture;
- the replay-negative fixture also depended on that obsolete success path.

Static inspection confirmed the canonical cleanup report fields are `terminalized_discovery_batches` and `cancelled_discovery_work`. Only those assertions and stale test fixtures were corrected; production authority was not widened.

### Corrected GREEN

Run `31876119958`, job `94991987380`:

- `14 passed in 17.45s`;
- `python -m py_compile src/printer_v1/operator_cli/operational_campaign_recovery.py` passed;
- `git diff --check` passed;
- cached diff check passed before commit;
- temporary RED/GREEN workflows and patch scripts were deleted before the verified implementation commit.

The focused suite covered:

- exact ten-identity reconciliation;
- exact batch terminalization with all nonterminal identity fields preserved;
- canonical cleanup rowcount proof;
- discovery-batch identity drift rejection before recovery mutation;
- replay rejection over live batch residue;
- historical reconciliation success and idempotence with the corrected ten-row fixture;
- prior nonterminal-batch safety behavior;
- shared-terminal zero-attempt regressions;
- four-token terminal integration regressions.

No broad suite was run; this narrow repair used the minimum sufficient affected suite under Printer V1 risk-based verification rules.

## Final net diff

Compared with design commit `8a2463a...`, the final implementation changes only:

- `src/printer_v1/operator_cli/operational_campaign_recovery.py`;
- `tests/test_v2_9_8b_historical_discovery_batch_residue_repair.py`;
- `tests/test_v2_9_8b_historical_four_token_reconciliation.py`.

All temporary verifier files are absent from the final net tree.

## Money-usefulness contribution

This repair makes historical durable cleanup truthful and executable for the exact consumed failure state. Removing abandoned ownership is necessary before trustworthy bounded memory-growth operation can resume, but this lane creates no trading or retrieval capability.

## What this improves

- complete accounting of the hidden historical discovery-batch residue;
- exact ten-row identity-scoped reconciliation contract;
- reuse of the existing canonical cleanup owner;
- fail-closed stable batch identity binding;
- truthful idempotent replay;
- explicit proof that linked discovery work and Scheduler ownership remain terminal and unchanged.

## What remains locked

This closeout does not authorize:

- authoritative Mac DB reconciliation;
- fresh proof authorization;
- another four-token operational proof;
- six-token widening;
- longer-window activation;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- paper positions;
- trade events/audits;
- PnL.

All Solana-only, memecoin-only, paper-only, Source Governor, Central Scheduler and clean-memory restrictions remain unchanged.

## Proof required before authoritative mutation

The next gate is a second **real historical disposable-copy proof** using:

- a byte-identical copy of the still-authoritative DB at SHA `5e830af41d58325d3f9e521f1b95f697b8151113cb783cf05a2a776e204639bc`;
- disposable copies of the exact historical artifacts, pre-campaign backup and lease;
- production code from `c5998516ff1782a2d65bebdac908543de3eafee6` or this closeout descendant;
- unmodified `HistoricalFourTokenRecoveryContract()`.

The proof must establish:

1. first invocation returns `V2_9_8B_HISTORICAL_FOUR_TOKEN_RECONCILED`;
2. exactly ten DB row identities change and the pinned discovery batch is the tenth;
3. cleanup reports one terminalized discovery batch and zero cancelled discovery work;
4. batch reaches exact `TERMINAL_FAILED` state with preserved cause and all other fields unchanged;
5. every non-approved table hash is unchanged;
6. Scheduler work/jobs and locked retrieval/financial hashes are unchanged;
7. windows/steps/Cycle-2 attempts remain zero;
8. migration ledger remains 55/head 055 and migration-056 provenance remains zero;
9. integrity/FK checks remain clean;
10. second invocation returns `V2_9_8B_HISTORICAL_FOUR_TOKEN_ALREADY_RECONCILED` with zero writes and unchanged disposable DB SHA;
11. authoritative DB/artifacts/lease remain byte-identical and untouched.

Only after that proof passes and is closed out may authoritative historical reconciliation be considered.

## Functionality Risks / Setbacks / Efficiency Blockers

- The authoritative reconciliation remains a Mac-local mutation and must not occur before the real disposable-copy reproof passes.
- The exact recovery intentionally remains tied to the historical migration-055 DB identity; it is not a generic recovery API.
- A mismatch in any pinned batch fact must block rather than be auto-corrected.
- No fresh authorization may reuse the consumed pre-cleanup DB identity; authoritative cleanup, if later approved, will produce a new DB SHA that must be rebound through the normal readiness/authorization path.
