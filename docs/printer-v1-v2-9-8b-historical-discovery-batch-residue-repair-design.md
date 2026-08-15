# Printer V1 V2-9.8B — Historical Discovery-Batch Residue Repair Design

## Verdict

`V2_9_8B_HISTORICAL_DISCOVERY_BATCH_RESIDUE_REPAIR_DESIGN_PASS_PENDING_EXACT_BATCH_IDENTITY_BINDING`

## Baseline

- Remote implementation closeout: `89bbf9db68f3b5cc062514b23638a0763d7b323b`
- Historical execution: `20260814T172224Z-490856f405bf`
- Historical factory run: `ed0fa279-38e6-401b-8b34-0a9531a9c720`
- Expected pre-reconciliation DB SHA256: `5e830af41d58325d3f9e521f1b95f697b8151113cb783cf05a2a776e204639bc`
- Controlling cause: `FourTokenFactoryAdapterError: cycle terminal reconciliation requires a fresh transaction`
- Audit classification: `DESIGN_GAP` with secondary `CONTRACT_DRIFT`.

The audit commit `dee59cf9a5bc107c4d3c1d56e510eb062adfce7e` is local-only and was supplied as read-only evidence. The authoritative DB remains untouched.

## Design decision

The historical reconciliation contract expands from exactly nine approved DB row identities to exactly ten. The tenth identity is the one historical `printer_discovery_batches` row already owned by `cleanup_campaign_supervision()`.

No new terminalization owner is introduced. The existing canonical supervision cleanup remains responsible for changing the batch from `DISCOVERING` to `TERMINAL_FAILED`.

The repair must not weaken the guard to "allow any nonterminal batch".

## Contract changes

`HistoricalFourTokenRecoveryContract` gains exact immutable expectations for the historical discovery batch:

- exact `discovery_batch_id`;
- exact campaign/configuration/run/cycle ownership;
- expected pre-state `DISCOVERING`;
- expected null `first_terminal_cause`;
- expected null `terminal_at`;
- exact `canonical_hash`;
- exact `cycle_seed_hash`;
- exact `campaign_selection_seed_identity`;
- exact `policy_version`;
- exact canonical `provider_contract_versions_json` value;
- exact `git_provenance_identity`;
- exact null pump cursor slot/signature.

The full values for the six stable identity/hash facts must be copied exactly from the read-only audit evidence before implementation. Truncated values are not acceptable.

## Preflight

Replace the current zero-nonterminal-batch guard with an exact-batch guard.

Before any backup, lease release, or DB write, preflight must prove:

1. exactly one discovery batch exists for the historical campaign/run;
2. its id is the contract-pinned historical batch id;
3. its campaign/configuration/run/cycle ownership matches the contract exactly;
4. `batch_state == 'DISCOVERING'`;
5. `first_terminal_cause IS NULL` and `terminal_at IS NULL`;
6. every pinned stable identity/hash field matches exactly;
7. pump cursor slot/signature are both null;
8. exactly eight linked discovery-work rows exist and all are terminal `SUCCEEDED`;
9. linked Scheduler ids are exactly `2011..2018` and already terminal/unlocked;
10. zero linked or global active discovery work exists;
11. there is no second nonterminal discovery batch.

Any missing, additional, contradictory, or drifted shape fails closed before mutation.

## Canonical mutation composition

Keep the existing order:

1. `reconcile_four_token_cycle_terminal(...)`
2. `cleanup_campaign_supervision(...)`
3. `reconcile_campaign_terminal(...)`

For the pinned historical state, step 2 must be required to report:

- `discovery_batch_rowcount == 1`
- `discovery_work_rowcount == 0`

Scheduler work/jobs must remain unchanged.

## Exact approved mutation set

Exactly ten DB row identities across eight tables may change:

1. campaign;
2. campaign run;
3. Cycle 1;
4. slot 1;
5. slot 2;
6. supervision;
7. tracking queue 58;
8. tracking queue 59;
9. factory run;
10. the one pinned historical discovery batch.

Filesystem mutation remains limited to release/removal of the exact expired historical campaign lease.

`_historical_identity_maps()` must include `printer_discovery_batches` keyed by `discovery_batch_id` so the changed-row allowlist is identity-scoped rather than table-wide.

`printer_discovery_batches` may be added to `allowed_tables` only because the changed-identity check independently requires exactly the pinned batch id and no other row.

## Required discovery-batch post-state

The pinned batch must become:

- `batch_state = 'TERMINAL_FAILED'`;
- `first_terminal_cause` exactly equal to the preserved historical cause;
- `terminal_at` non-null.

Every other batch column must remain byte-for-byte/logically identical to its pre-state value.

No migration-056 provenance row may be created or backfilled.

## Replay contract

`_historical_already_reconciled()` must not return true unless the pinned historical discovery batch is also terminalized exactly:

- exact batch id and ownership;
- `TERMINAL_FAILED`;
- exact preserved cause;
- non-null `terminal_at`;
- all pinned stable identity/hash facts unchanged.

This closes the current replay hole where the seven existing row groups could appear reconciled while the discovery batch remained live residue.

## Focused TDD

Minimum RED/GREEN coverage:

1. exact historical fixture with the pinned `DISCOVERING` batch currently blocks under the nine-row contract;
2. repaired contract reconciles exactly ten identities and the batch becomes `TERMINAL_FAILED`;
3. cleanup reports exactly one batch row and zero discovery-work rows changed;
4. any changed stable batch identity/hash fact rejects before mutation;
5. a second nonterminal batch rejects before mutation;
6. any active linked discovery work rejects before mutation;
7. replay returns `ALREADY_RECONCILED` only when the pinned batch is terminal-correct;
8. replay rejects/does not claim success if the batch is still `DISCOVERING`;
9. existing shared-terminal and historical nine-row safety regressions remain green where still applicable.

Use only the focused affected suite, `py_compile`, and `git diff --check`.

## Disposable proof requirement

After implementation closeout, rerun the real historical disposable-copy proof from a byte-identical authoritative DB copy and copied artifact/lease root.

Required proof:

- first invocation returns `V2_9_8B_HISTORICAL_FOUR_TOKEN_RECONCILED`;
- exactly ten row identities changed;
- exact discovery batch is the tenth identity;
- all other table hashes unchanged;
- locked retrieval/financial hashes unchanged;
- Scheduler work/jobs unchanged;
- migration ledger remains 55/head 055;
- migration-056 provenance remains zero;
- integrity/FK clean;
- second invocation returns `V2_9_8B_HISTORICAL_FOUR_TOKEN_ALREADY_RECONCILED` with zero writes and unchanged DB SHA;
- authoritative source DB/artifacts/lease remain untouched.

Only after that proof and its closeout may an authoritative reconciliation be considered.

## Money-usefulness contribution

This repair removes an unsatisfied historical cleanup contract that currently prevents trustworthy return to bounded memory-growth readiness. It improves durable state truthfulness; it creates no trading capability.

## What this improves

- exact accounting of the hidden historical discovery-batch residue;
- canonical cleanup-owner reuse;
- ten-row identity-scoped mutation proof;
- fail-closed batch pre-state binding;
- truthful idempotent replay.

## What remains locked

No authoritative DB reconciliation, fresh authorization, four-token proof, six-token widening, longer-window activation, retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events/audits, or PnL is unlocked by this design.

## Functionality Risks / Setbacks / Efficiency Blockers

- Full stable batch identity values are not present in the pasted audit summary; implementation must not guess them.
- Removing the current preflight guard without adding exact identity checks would weaken safety.
- Adding `printer_discovery_batches` to the table allowlist without identity-scoped changed-row verification would be too broad.
- Replay must be repaired in the same implementation or stale batch residue could be reported as successfully reconciled.

## Next gate

Bind the exact full historical batch identity values from read-only local evidence, then proceed directly to focused RED TDD. No authoritative mutation is permitted.