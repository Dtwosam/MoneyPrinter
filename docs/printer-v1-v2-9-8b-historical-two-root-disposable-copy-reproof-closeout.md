# Printer V1 V2-9.8B — Historical Two-Root Disposable-Copy Reproof Closeout

## Verdict

`V2_9_8B_HISTORICAL_TWO_ROOT_DISPOSABLE_COPY_REPROOF_CLOSEOUT_PASS_READY_FOR_FRESH_AUTHORITATIVE_RECONCILIATION_READINESS_REVIEW`

## Lane identity

- Repair closeout baseline: `68e9b29664329cabce128f29d3ca89fc01c86110`
- Verified implementation ancestor: `c21bd26778b1632c4f65a4fac3c399ed6698eda6`
- Historical execution: `20260814T172224Z-490856f405bf`
- Authoritative DB expected SHA before authoritative reconciliation remains `5e830af41d58325d3f9e521f1b95f697b8151113cb783cf05a2a776e204639bc`.

No authoritative reconciliation occurred during this proof. The authoritative DB, original campaign lease, historical execution root, and consumed application root remained unchanged.

## Proof topology

The proof exercised the real immutable two-root evidence topology rather than a reconstructed one-root layout.

Execution root owner:

`/Users/Dtwo1/PrinterOperations/v2-9-8/20260814T172224Z-490856f405bf`

- owns `terminal-summary.json`;
- owns the campaign lease;
- owns the historical pre-campaign backup/rehearsal/report evidence.

Consumed application root owner:

`/Users/Dtwo1/PrinterOperations/v2-9-8/four-token-proof-one-shot-applications/V2_9_8B_FOUR_TOKEN_PROOF_AUTH_20260814T171249Z_0022b4dc`

- owns `application-marker.json`;
- `git-provenance-manifest.json`;
- `wrapper-terminal.json`;
- `child-terminal.json`;
- `child-stderr.txt`;
- incidental `child-stdout.txt` remained part of the root inventory.

Disposable copies preserved those roots separately. No application artifact was added to the execution root and `terminal-summary.json` was not moved to the application root.

## Source revalidation

Before disposable proof execution, all required authoritative facts passed read-only revalidation:

- authoritative DB SHA exact `5e830af41d58325d3f9e521f1b95f697b8151113cb783cf05a2a776e204639bc`;
- no SQLite sidecars;
- `PRAGMA integrity_check = ok`;
- foreign-key violations `0`;
- migration ledger count `55`, head `055_pre_admission_discovery_attempt_ownership.sql`;
- migration 056 absent from authoritative schema/ledger;
- historical PID `59354` dead;
- unchanged production process guard returned no owner;
- no DB/lease holder;
- original lease present and SHA `71389ed839964c1892751ff1ca323f24fa7c1523bd9b39dcbdee18d03370f8a4`;
- all six evidence SHA identities matched their fixed root owners;
- campaign/run remained `RUNNING`;
- Cycle 1 remained ordinal 1 `PLANNED`;
- supervision remained `ACTIVE`;
- factory run remained `RUNNING`;
- slots remained `SELECTED`;
- queues 58/59 remained `QUEUED` / `PROMOTE_TO_TRACK_NORMAL`;
- pinned discovery batch remained `DISCOVERING` with null terminal cause/time;
- exactly 8 linked discovery-work rows remained `SUCCEEDED` on jobs 2011–2018;
- jobs 2011–2020 remained 8 `SUCCEEDED` + 2 `CANCELLED`, inactive/unlocked;
- campaign Scheduler-work remained terminal;
- exactly one nonterminal discovery batch remained globally;
- campaign windows, factory steps, and Cycle-2 attempts remained zero.

The proof was invoked from a script file rather than a heredoc so ancestor argv did not contaminate the exact production live-process probe. The production guard itself was not weakened or replaced.

## Disposable material

A fresh disposable root under the operator scratchpad contained:

1. byte-identical DB copy with pre-proof SHA `5e830af4...`;
2. disposable execution root preserving the real execution-root topology;
3. separate disposable consumed application root preserving all six entries, including `child-stdout.txt`;
4. fresh recovery root outside both evidence roots.

Independent DB pre-state snapshots were captured before invocation.

## First invocation proof

The exact recovery entrypoint from the detached `68e9b296...` worktree was invoked only against disposable material with:

- separate `artifact_root` and `application_artifact_root`;
- disposable execution-root lease override for isolation only;
- unmodified `HistoricalFourTokenRecoveryContract()`;
- no source/runtime/Scheduler execution.

Result:

`V2_9_8B_HISTORICAL_FOUR_TOKEN_RECONCILED`

Observed self-report facts:

- changed database row identities: `10`;
- database writes: `10`;
- terminalized discovery batches: `1`;
- cancelled discovery work: `0`;
- source calls: `0`;
- Scheduler runtime calls: `0`;
- restart created: false;
- successor created: false;
- recovery backup SHA matched the original pinned DB SHA.

Independent before/after snapshots, not the production self-report, proved exactly these ten DB identities changed and no others:

1. historical campaign;
2. campaign run;
3. Cycle 1;
4. slot 1;
5. slot 2;
6. campaign supervision;
7. queue 58;
8. queue 59;
9. historical factory run;
10. pinned discovery batch.

Required terminal states were reached:

- campaign/run/Cycle1 -> `TERMINAL_FAILED`;
- both token slots -> `MANUAL_REVIEW`;
- queues 58/59 -> `SKIPPED` + `MANUAL_REVIEW`;
- supervision -> `TERMINAL` / `FAILED` with cleanup and lease-release timestamps;
- factory run -> `SAFE_STOPPED`;
- pinned discovery batch -> `TERMINAL_FAILED`.

Exact terminal cause remained:

`FourTokenFactoryAdapterError: cycle terminal reconciliation requires a fresh transaction`

For the pinned discovery batch, only `batch_state`, `first_terminal_cause`, and `terminal_at` changed; every other persisted field remained byte-identical.

All eight discovery-work rows, Scheduler jobs 2011–2020, and campaign Scheduler-work remained unchanged. No non-approved table hash changed. Locked retrieval/financial hashes remained unchanged. Windows, steps, and Cycle-2 attempts remained zero. Database integrity/FK checks passed and no SQLite sidecars existed.

## Filesystem proof

Disposable application root:

- 6 entries before -> 6 entries after;
- complete inventory and bytes unchanged;
- no create/delete/rename/content mutation.

Disposable execution root:

- 5 entries before -> 4 entries after;
- exactly `campaign.lease.lock` was removed;
- nothing else was added, deleted, renamed, or modified.

Recovery evidence existed only under the separate recovery root.

## Migration isolation

The reconciled disposable DB remained at migration ledger 55/head055 with migration056 absent.

The recovery restore-rehearsal copy legitimately advanced to migration056. That migration existed only in the throwaway rehearsal artifact, not in the reconciled disposable DB or authoritative DB.

## Idempotent replay

A second exact invocation with the same disposable evidence inputs and a second fresh recovery-root path returned:

`V2_9_8B_HISTORICAL_FOUR_TOKEN_ALREADY_RECONCILED`

- database writes: `0`;
- disposable DB SHA unchanged across invocation 2;
- second recovery root was never created;
- both disposable evidence roots remained unchanged from their post-invocation-1 state.

## Original source after proof

Post-proof read-only checks proved:

- authoritative DB SHA remained exact `5e830af41d58325d3f9e521f1b95f697b8151113cb783cf05a2a776e204639bc`;
- no authoritative sidecars;
- campaign remained `RUNNING`;
- pinned batch remained `DISCOVERING` with null cause/time;
- authoritative ledger remained 55/head055;
- original lease remained present with exact SHA;
- original execution-root inventory/hashes remained unchanged;
- original consumed application-root inventory/hashes remained unchanged;
- all five application artifact SHAs and execution-root terminal-summary SHA remained exact;
- no Printer/Scheduler/runtime was started.

Disposable/recovery proof evidence was preserved. Only the detached temporary worktree was removed. The user's local working branch/HEAD and untracked evidence directories were left untouched.

## Acceptance assessment

The proof closes the dual-artifact-root repair's bounded proof requirement. It establishes that the exact historical recovery contract can operate correctly with the real evidence topology while preserving the previously proven ten-row DB mutation boundary, locked domains, Scheduler/discovery work, migration isolation, and idempotent replay.

It does **not** itself authorize mutation of the authoritative DB because the recovery evidence interface changed after the previous authoritative readiness review. A fresh readiness review is required from this closeout state.

## Money-usefulness contribution

This removes a false historical-evidence-layout assumption while preserving exact cleanup authority. Clearing the abandoned historical ownership truthfully improves corpus/lifecycle trustworthiness required for later bounded paper-only memory growth; it creates no trading or profit capability.

## What this improves

- real two-root evidence topology is now proof-backed;
- exact six artifact SHA identities stay mandatory;
- no original artifact reconstruction is needed;
- authoritative lease ownership stays execution-root-only;
- exact ten-row cleanup authority remains proven;
- application evidence remains immutable during recovery;
- zero-write replay remains proven.

## What remains locked

This closeout does not authorize authoritative historical reconciliation until a fresh readiness review passes. It also does not authorize source fetching, discovery/runtime/Scheduler execution, memory generation, a fresh four-token campaign/proof authorization, six-token widening, longer-window activation, retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events/audits, PnL, wallets, private keys, real funds, live execution, paid APIs, scoring/ranking/confidence/weighted logic, embeddings/vectors, Source Governor bypass, or Central Scheduler bypass.

## Required next lane

Fresh **Authoritative Historical Reconciliation Readiness Review** only.

The review must revalidate the authoritative source and both immutable evidence roots, bind the exact authoritative call with the audited `application_artifact_root`, confirm authoritative omission of the disposable-only lease override, rebuild the fresh backup/rollback/stop-on-drift package, and confirm that the ten-row DB mutation boundary remains exact.

Only after that readiness review passes may a separately approved bounded authoritative reconciliation be attempted.

## Functionality Risks / Setbacks / Efficiency Blockers

- The authoritative residue remains intentionally stranded until fresh readiness passes.
- The recovery function is effectively one-shot against the pinned pre-reconciliation DB SHA; any failed attempt after mutation requires restoration before retry.
- The application root is evidence-only and must never become a generic filesystem resolution surface.
- Operator command-line self-detection remains possible if the execution ID is embedded in ancestor argv; use script-file invocation rather than weakening the live-process guard.
- The restore-rehearsal copy may contain migration056 and must not be mistaken for authoritative/disposable reconciled DB drift.
