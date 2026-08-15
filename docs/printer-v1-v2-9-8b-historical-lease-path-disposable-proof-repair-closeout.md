# Printer V1 V2-9.8B — Historical Lease-Path Disposable-Proof Repair Closeout

## Verdict

`V2_9_8B_HISTORICAL_LEASE_PATH_DISPOSABLE_PROOF_REPAIR_CLOSEOUT_PASS_READY_FOR_EXACT_DISPOSABLE_COPY_REPROOF`

## Lane identity

- Prior discovery-batch repair closeout: `01245f9d699ce01b534135287feaf1790c4a4a6b`
- Verified implementation: `14525da`
- Branch: `agent/v2-9-8b-historical-lease-path-disposable-proof-repair`
- Historical execution: `20260814T172224Z-490856f405bf`
- Expected authoritative DB SHA before reconciliation: `5e830af41d58325d3f9e521f1b95f697b8151113cb783cf05a2a776e204639bc`

The authoritative Mac DB, original historical artifacts, and original lease were not mutated by this lane.

## Blocker repaired

The second real Mac disposable-copy reproof correctly blocked before writes because the byte-identical copied DB retained the authoritative absolute `lease_lock_path`, while the disposable artifact copy necessarily had a different filesystem path.

Static inspection proved a preflight-only fix would be unsafe: canonical `cleanup_campaign_supervision()` later released the DB-recorded path directly, and historical idempotent replay also tested the persisted path. A disposable proof could therefore not safely reach reconciliation without either rewriting the copied DB, weakening the pinned DB identity, or risking deletion of the authoritative lease.

## Design and implementation

The repair adds one optional physical lease-path injection boundary while keeping durable DB lease identity unchanged.

- `reconcile_exact_historical_four_token_execution(..., lease_lock_path_override=...)` accepts the override only when it resolves exactly to `<artifact_root>/campaign.lease.lock`; an arbitrary path fails closed before mutation.
- Without an override, historical reconciliation preserves the previous behavior and requires the persisted DB lease path to match the artifact-root lease.
- `_historical_preflight()` validates the selected physical lease payload/expiry while preserving the byte-identical DB row.
- `cleanup_campaign_supervision()` accepts an optional physical release path; absent that argument it still releases the persisted DB path exactly as before.
- `_historical_already_reconciled()` validates absence of the same selected physical lease, making disposable idempotent replay truthful without requiring the authoritative lease to disappear.
- No historical DB row is rewritten to make the proof work.
- The exact ten-row reconciliation mutation allowlist is unchanged.
- No new cleanup owner, source path, Scheduler path, migration, retry, runtime, memory, retrieval, or financial capability was introduced.

## TDD and verification evidence

### Focused RED

Run `31877513764`, job `94995315947`:

- 2 failures;
- both failures were the intended missing production API: `reconcile_exact_historical_four_token_execution()` did not accept `lease_lock_path_override`;
- no production mutation was used to manufacture the RED.

### First GREEN tooling attempt

Run `31877575494` failed before tests because the temporary patch script used a signature replacement pattern that matched two functions. This was verifier tooling only. The production target pattern was narrowed to the exact historical reconciliation function before rerun.

### Affected-suite classification

A later affected-suite run reached 23 passing tests plus one failure in:

`tests/test_v2_9_7e_1_insufficient_pool_terminal_cleanup.py::InsufficientPoolTerminalCleanupTests::test_insufficient_pool_cleanup_report_replay`

The assertion expected `cancelled_scheduler_jobs >= 1` but observed 0. Exact baseline run `31877671314`, job `94995686736`, checked out untouched pre-repair commit `01245f9d699ce01b534135287feaf1790c4a4a6b` and failed identically. The failure is therefore confirmed pre-existing drift unrelated to this lease-path repair and was not expanded into this lane.

### Final GREEN

Run `31877746768`, job `94995856601`:

- `22 passed, 7 subtests passed in 24.51s`;
- both changed Python modules compiled successfully;
- `git diff --check` passed;
- cached diff check passed before commit;
- temporary RED/GREEN/baseline workflows and patch script were removed before verified implementation commit `14525da`.

The final focused suite covers:

- exact disposable lease override reconciliation;
- deletion of only the disposable lease while original lease/DB remain unchanged in the fixture;
- exact ten-row historical reconciliation;
- arbitrary lease override fail-closed behavior;
- idempotent second invocation with zero writes;
- historical discovery-batch reconciliation and preflight safety;
- normal operational lease safe-stop behavior;
- shared-terminal zero-attempt regressions;
- four-token terminal integration regressions.

No broad suite was run; minimum sufficient risk-based verification was used.

## Final net diff

Compared with prior closeout `01245f9d...`, the verified implementation tree changes only:

- `docs/printer-v1-v2-9-8b-historical-lease-path-disposable-proof-repair-design.md`
- `src/printer_v1/operator_cli/campaign_supervision.py`
- `src/printer_v1/operator_cli/operational_campaign_recovery.py`
- `tests/test_v2_9_8b_historical_disposable_lease_path_repair.py`

All temporary verifier files are absent from the final net tree.

## Money-usefulness contribution

This removes a proof-environment coupling that prevented safe cleanup of abandoned durable ownership. It improves trust in persistent corpus operations and recovery evidence, but creates no trading or retrieval capability.

## What this improves

- byte-identical disposable DB proofs no longer require rewriting persisted lease identity;
- copied proof artifacts can own their own physical lease safely;
- canonical cleanup can release a deliberately injected physical lease without changing normal production semantics;
- original authoritative lease safety can be proven directly;
- idempotent replay can be validated against the same physical proof boundary.

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

All Solana-only, memecoin-only, paper-only, Source Governor, Central Scheduler, clean-memory, no-scoring, and no-paid-dependency restrictions remain unchanged.

## Proof required before authoritative mutation

Run the real Mac disposable-copy reproof again from this closeout descendant. The proof must preserve the original authoritative DB/artifacts/lease and invoke exact historical reconciliation against disposable copies with:

`lease_lock_path_override=<DISPOSABLE_ARTIFACT_ROOT>/campaign.lease.lock`

It must independently prove:

1. source DB SHA remains the pinned pre-reconciliation SHA before and after proof;
2. original lease SHA remains unchanged;
3. disposable DB begins byte-identical to source;
4. first invocation returns `V2_9_8B_HISTORICAL_FOUR_TOKEN_RECONCILED`;
5. exactly ten DB identities change;
6. only the disposable lease is released;
7. discovery batch is the tenth identity and reaches exact `TERMINAL_FAILED` state;
8. every non-approved table hash, Scheduler row, discovery-work row, and locked-domain hash remains unchanged;
9. windows/steps/Cycle-2 attempts remain zero; migration ledger remains 55/head055; migration-056 provenance remains zero; integrity/FK remain clean;
10. second invocation returns `V2_9_8B_HISTORICAL_FOUR_TOKEN_ALREADY_RECONCILED` with zero writes and unchanged post-first-run disposable DB SHA;
11. no source, Scheduler runtime, restart, successor, proof, authorization, retrieval, or financial action occurs.

Only after that reproof passes and is separately closed out may authoritative historical reconciliation be considered.