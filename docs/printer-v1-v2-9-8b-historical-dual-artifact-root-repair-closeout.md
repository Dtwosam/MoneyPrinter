# Printer V1 V2-9.8B — Historical Dual-Artifact-Root Repair Closeout

## Verdict

`V2_9_8B_HISTORICAL_DUAL_ARTIFACT_ROOT_REPAIR_CLOSEOUT_PASS_READY_FOR_TWO_ROOT_DISPOSABLE_COPY_REPROOF`

## Lane identity

- Design: `4c1706b057a1cff93f6fd8a7bc52de4c299d00e0`
- Application-root binding audit: `634bcf869d6ab74fd378bfae2b29d86f234905e0`
- Verified implementation: `c21bd26778b1632c4f65a4fac3c399ed6698eda6`
- Historical execution: `20260814T172224Z-490856f405bf`
- Expected authoritative DB SHA remains `5e830af41d58325d3f9e521f1b95f697b8151113cb783cf05a2a776e204639bc`.

No authoritative DB, historical lease, execution-root artifact, or consumed application-root artifact was mutated by this implementation lane.

## Repaired design gap

The historical recovery validator previously assumed all six pinned evidence files lived beneath the execution `artifact_root`. The real consumed execution has two immutable roots:

- execution root owns `terminal-summary.json` and the canonical campaign lease;
- consumed application root owns `application-marker.json`, `git-provenance-manifest.json`, `wrapper-terminal.json`, `child-terminal.json`, and `child-stderr.txt`.

The exact consumed application root was bound read-only as:

`/Users/Dtwo1/PrinterOperations/v2-9-8/four-token-proof-one-shot-applications/V2_9_8B_FOUR_TOKEN_PROOF_AUTH_20260814T171249Z_0022b4dc`

Exactly one scanned root matched all five existing pinned SHA-256 identities.

## Implementation

`reconcile_exact_historical_four_token_execution()` now requires explicit:

`application_artifact_root: str | Path`

The existing execution `artifact_root` remains the sole lease/execution-root owner.

Fixed ownership is enforced:

Application root only:

- `application-marker.json`
- `git-provenance-manifest.json`
- `wrapper-terminal.json`
- `child-terminal.json`
- `child-stderr.txt`

Execution root only:

- `terminal-summary.json`

The existing six SHA pins are unchanged. The validator additionally rejects any contract whose expected artifact-name set differs from the fixed ownership set.

There is no application-artifact fallback to the execution root, no generic filename/path map, no artifact copy/move/symlink/reconstruction, and no new filesystem mutation owner.

`application_artifact_root` is threaded only through exact historical artifact validation, preflight, post-state validation, and idempotent replay. It does not select or affect the DB, pre-campaign backup, lease path/release, recovery root, Scheduler, discovery, migrations, source/runtime behavior, or the exact ten-row mutation allowlist.

The authoritative lease continues to derive from `artifact_root/campaign.lease.lock`. The disposable-only `lease_lock_path_override` behavior is unchanged.

## TDD evidence

### RED

Expanded RED run `31884556933`, job `95011848309`:

- `5 failed in 5.31s`;
- every failure was the intended missing API:
  `TypeError: reconcile_exact_historical_four_token_execution() got an unexpected keyword argument 'application_artifact_root'`;
- no production code was applied in the RED.

RED coverage required:

1. exact two-root reconciliation and idempotent replay;
2. application root remains unchanged;
3. missing application artifact rejects before mutation;
4. application artifacts never fall back to execution root;
5. `terminal-summary.json` remains execution-root-owned;
6. wrong application artifact SHA rejects before mutation.

### GREEN

Run `31884606939`, job `95011966419`:

- `14 passed in 20.35s`;
- `python -m py_compile src/printer_v1/operator_cli/operational_campaign_recovery.py` passed;
- `git diff --check` passed;
- cached diff check passed before commit;
- temporary RED/GREEN workflows and patch script were removed before verified implementation commit `c21bd26778b1632c4f65a4fac3c399ed6698eda6`.

The focused suite included:

- dual-root topology and SHA guards;
- historical exact ten-row reconciliation;
- historical discovery-batch residue repair;
- historical reconciliation preflight safety;
- disposable lease-path repair.

No broad suite was run; minimum sufficient risk-based verification was used.

## Final net diff

Compared with design `4c1706b...`, the verified implementation tree changes only:

1. `docs/printer-v1-v2-9-8b-historical-application-root-binding-audit.md`;
2. `src/printer_v1/operator_cli/operational_campaign_recovery.py`;
3. `tests/test_v2_9_8b_historical_dual_artifact_root_repair.py`;
4. `tests/test_v2_9_8b_historical_dual_artifact_root_sha_guard.py`;
5. `tests/test_v2_9_8b_historical_four_token_reconciliation.py`.

All temporary verifier files are absent from the final net tree.

## Money-usefulness contribution

The repair keeps the consumed execution's evidence topology truthful while preserving the exact historical cleanup authority. This improves lifecycle/corpus trustworthiness before later bounded paper-only memory growth; it does not create or imply trading capability or profit.

## What this improves

- production validation now matches the real two-root consumed evidence topology;
- all six historical evidence identities remain hash pinned;
- original historical evidence does not need reconstruction or relocation;
- authoritative lease identity remains strict;
- disposable proof can copy both roots separately and exercise the real topology;
- idempotent replay remains part of the exact recovery contract.

## What remains locked

This closeout does not authorize:

- authoritative historical reconciliation;
- source fetching or discovery runs;
- Scheduler/runtime execution;
- memory generation;
- another four-token campaign or proof authorization;
- six-token widening;
- longer-window activation;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions, trade events/audits, or PnL;
- wallets, private keys, real funds, or live execution.

All Source Governor, Central Scheduler, clean-memory, no-scoring/ranking/confidence/weighted-logic, no-paid-dependency, and Solana-only/paper-only restrictions remain unchanged.

## Required next proof

The next allowed step is a fresh **two-root disposable-copy reproof**, not authoritative mutation.

It must:

1. revalidate the authoritative source read-only and stop on drift;
2. begin from a byte-identical copy of the authoritative DB;
3. preserve separate disposable execution and application roots matching the real topology;
4. validate all six existing pinned SHAs from their fixed owners;
5. use the disposable execution-root lease override only for proof isolation;
6. independently prove exactly ten DB identities change and no other DB/table/locked-domain content changes;
7. prove the disposable application root is byte-for-byte unchanged;
8. prove the disposable execution root changes only by canonical disposable lease deletion, excluding separately created recovery evidence outside that root;
9. preserve Scheduler/discovery-work rows, zero windows/steps/Cycle-2 attempts, migration 55/head055 and zero migration-056 provenance on the reconciled disposable DB;
10. prove exact zero-write idempotent replay;
11. prove the original authoritative DB, original lease, original execution root, and original application root are unchanged.

Only after that proof passes and is separately closed out may a fresh authoritative reconciliation readiness review be performed.

## Functionality Risks / Setbacks / Efficiency Blockers

- This remains an exact one-execution recovery surface, not a generic multi-root evidence resolver.
- Any application-root path or SHA drift must fail closed.
- The old synthetic one-root fixtures remain compatibility regressions only; readiness must be established with the real two-root topology.
- The authoritative historical residue intentionally remains until two-root proof and fresh readiness complete.
- Process-probe self-detection from heredoc/ancestor argv remains an operator invocation artifact; future proof scripts should avoid embedding the execution ID in ancestor command lines rather than weakening the guard.