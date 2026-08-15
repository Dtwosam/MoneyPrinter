# Printer V1 V2-9.8B — Historical Disposable Lease Alias Repair Closeout

## Verdict

`V2_9_8B_HISTORICAL_DISPOSABLE_LEASE_ALIAS_REPAIR_CLOSEOUT_PASS_READY_FOR_REAL_DISPOSABLE_COPY_REPROOF`

## Lane identity

- Prior discovery-batch repair closeout: `01245f9d699ce01b534135287feaf1790c4a4a6b`
- Audit/design: `c59d0c64d411e4367a19425e69c17f2126824c57`
- Refined design: `85c9f7b8278455140f6fca8e38c104db44f743cd`
- Verified implementation: `4f70e1b20ed5fe699da22ec1bfbec9d0b4f04848`
- Branch: `agent/v2-9-8b-historical-lease-alias-repair`
- Historical execution: `20260814T172224Z-490856f405bf`
- Expected authoritative DB SHA256 before reconciliation: `5e830af41d58325d3f9e521f1b95f697b8151113cb783cf05a2a776e204639bc`

The authoritative Mac DB, original historical artifacts, and recorded historical lease were not mutated by this lane.

## Blocker repaired

The first real disposable-copy reproof exposed a latent path-coupling defect: the byte-identical disposable DB preserves the original absolute `lease_lock_path`, while `_historical_preflight()` previously required that recorded path to equal the copied `artifact_root / campaign.lease.lock`.

Using the original artifact root would have allowed canonical cleanup to unlink the original historical lease. Rewriting `lease_lock_path` in the copied DB would have broken the exact pinned DB identity and widened the proof mutation set.

The defect was therefore classified as `DESIGN_GAP` with secondary `PROOF_HARNESS_PATH_COUPLING`.

## Design resolution

The DB row remains unchanged. The exact DB SHA already binds the persisted recorded lease path, so no user-specific absolute path was added to `HistoricalFourTokenRecoveryContract`.

`reconcile_exact_historical_four_token_execution()` now accepts one optional proof-only keyword:

`disposable_lease_alias: str | Path | None = None`

Default `None` preserves the authoritative path behavior.

Alias mode requires before historical reconciliation writes:

- alias resolves exactly to `artifact_root / campaign.lease.lock`;
- alias differs from the recorded SQLite lease path;
- recorded lease exists;
- alias exists;
- alias and recorded lease bytes are identical;
- both lease payloads match the exact supervision ownership identity and expiry;
- all existing exact DB SHA, migration, graph, Scheduler, discovery, artifact and no-active-work guards still pass.

No SQLite lease-path rewrite is performed.

## Canonical cleanup preservation

The existing campaign-supervision cleanup body remains single-sourced in `_cleanup_campaign_supervision_impl()`.

The public `cleanup_campaign_supervision()` keeps its previous signature and always calls the internal implementation without a release override. Its normal behavior therefore still releases the SQLite-recorded lease.

Only the exact historical reconciliation path can call the internal implementation with the already validated disposable alias.

In alias mode the cleanup:

1. validates recorded and alias leases before transactional DB mutation;
2. executes the same canonical terminal DB cleanup;
3. releases only the copied alias with the existing `_release_lock()` ownership guard;
4. revalidates that the recorded original lease is still byte-identical;
5. persists `lease_released_at` only in the disposable DB;
6. reports `lease_release_mode = DISPOSABLE_ALIAS` and `recorded_lease_preserved = true`.

Default mode reports `lease_release_mode = RECORDED`.

## Replay repair

`_historical_already_reconciled()` now understands the explicit proof mode without weakening default semantics.

Default mode still requires the SQLite-recorded lease to be absent.

Disposable alias mode requires:

- exact terminal DB state;
- durable cleanup and lease-release timestamps;
- alias absent;
- recorded lease still present;
- recorded lease still satisfies the exact historical ownership/expiry contract;
- all existing batch, queue, factory and provenance checks pass.

Thus a second disposable invocation can truthfully return `V2_9_8B_HISTORICAL_FOUR_TOKEN_ALREADY_RECONCILED` while the authoritative original lease remains preserved.

## Mutation contract

The approved DB mutation set remains exactly ten historical row identities. No lease-path column change was added.

In disposable alias mode the only additional filesystem mutation is deletion of the copied alias. The recorded original historical lease is preservation evidence, not a mutation target.

## TDD evidence

### RED

Run `31876787276`, job `94993607808`:

- 3 expected failures;
- 1 fail-closed control passed;
- alias-mode tests failed because `disposable_lease_alias` did not yet exist;
- relocated artifact root without alias remained rejected.

### GREEN harness corrections

Two intermediate GREEN attempts stopped inside temporary patch tooling before production tests:

- run `31876884543`, job `94993840122`: ambiguous campaign-supervision text anchor;
- run `31876921719`, job `94993933625`: ambiguous initial-replay text anchor.

Both failures occurred before production test execution. No implementation was committed from either run. The temporary patch harness was narrowed only to resolve its own anchors; production design was not widened.

### Verified GREEN

Run `31876987710`, job `94994091116`:

- `16 passed, 7 subtests passed in 26.72s`;
- both changed modules passed `py_compile`;
- `git diff --check` passed;
- cached diff check passed before commit;
- temporary RED/GREEN workflows and both patch scripts were removed before the verified implementation commit;
- verified implementation commit: `4f70e1b20ed5fe699da22ec1bfbec9d0b4f04848`.

The focused affected suite covered:

- exact disposable alias reconciliation;
- alias deletion with recorded lease byte preservation;
- no SQLite lease-path rebinding;
- exact ten-row historical mutation count;
- disposable idempotent replay with zero second-write count;
- corrupted/non-identical alias rejection before DB mutation;
- same-path alias rejection before DB mutation;
- no-alias relocated-root rejection;
- prior historical four-token reconciliation behavior;
- prior historical discovery-batch contract behavior;
- nearest operational lease/safe-stop behavior, including 7 subtests.

No broad suite was run; this narrow proof-path repair used the minimum sufficient affected suite.

## Final net diff

Compared with refined design commit `85c9f7b8278455140f6fca8e38c104db44f743cd`, the final implementation tree changes only:

- `src/printer_v1/operator_cli/campaign_supervision.py`;
- `src/printer_v1/operator_cli/operational_campaign_recovery.py`;
- `tests/test_v2_9_8b_historical_lease_alias_repair.py`.

All temporary workflow and patch files are absent from the final implementation tree.

## Money-usefulness contribution

This repair makes the exact historical cleanup safely provable without risking the authoritative evidence set. Clearing abandoned durable ownership is necessary before trustworthy bounded memory-growth operations can resume, but this lane creates no retrieval or trading capability.

## What this improves

- safe byte-identical disposable proof isolation;
- preservation of the original historical lease;
- reuse of the canonical cleanup owner rather than duplicate terminalization logic;
- proof-mode replay truthfulness;
- continued exact ten-row DB mutation accounting;
- fail-closed alias ownership and byte-identity checks.

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

## Proof required next

Repeat the real Mac-local historical reconciliation proof on a byte-identical disposable DB and copied historical artifact root using unmodified `HistoricalFourTokenRecoveryContract()` plus only:

`disposable_lease_alias=<DISPOSABLE_ARTIFACT_ROOT>/campaign.lease.lock`

The proof must independently establish:

1. authoritative source revalidation still matches DB SHA `5e830af41d58325d3f9e521f1b95f697b8151113cb783cf05a2a776e204639bc` and original evidence is quiescent;
2. disposable DB begins byte-identical to the authoritative DB;
3. first invocation returns `V2_9_8B_HISTORICAL_FOUR_TOKEN_RECONCILED`;
4. exactly ten DB row identities change;
5. cleanup reports `lease_release_mode = DISPOSABLE_ALIAS` and `recorded_lease_preserved = true`;
6. copied alias is deleted while the recorded original lease remains byte-identical;
7. persisted `lease_lock_path` remains the original recorded path;
8. historical discovery batch reaches exact terminal state and all other batch fields remain unchanged;
9. Scheduler work/jobs and eight terminal discovery-work rows remain unchanged;
10. every non-approved table hash and locked retrieval/financial hash remains unchanged;
11. windows, factory steps and Cycle-2 attempts remain zero;
12. migration ledger remains 55/head 055 with zero migration-056 provenance;
13. integrity/FK checks remain clean;
14. second invocation with the now-absent alias returns `V2_9_8B_HISTORICAL_FOUR_TOKEN_ALREADY_RECONCILED`, `database_writes = 0`, and leaves the post-first-run disposable DB SHA unchanged;
15. authoritative DB, original artifacts and recorded original lease remain unchanged after the proof.

Only after that real disposable-copy reproof closes PASS may authoritative historical reconciliation readiness/authorization be considered.

## Functionality Risks / Setbacks / Efficiency Blockers

- The internal release-path override must remain private to exact historical recovery; exposing it as generic runtime cleanup would weaken lease safety.
- Alias mode intentionally preserves a filesystem lease while marking only the disposable DB supervision lease released. It is valid only because the copied DB is non-authoritative proof state.
- Replay correctness depends on explicit alias mode plus exact terminal DB state; default mode must continue requiring the recorded lease to be absent.
- The real Mac-local proof remains mandatory because synthetic tests cannot prove the actual absolute-path/evidence interaction.
