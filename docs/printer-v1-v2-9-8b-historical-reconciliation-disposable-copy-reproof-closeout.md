# Printer V1 V2-9.8B — Historical Reconciliation Disposable-Copy Reproof Closeout

## Verdict

`V2_9_8B_HISTORICAL_RECONCILIATION_DISPOSABLE_COPY_REPROOF_CLOSEOUT_PASS_READY_FOR_AUTHORITATIVE_RECONCILIATION_READINESS_REVIEW`

## Lane identity

- Repair closeout used by the proof: `7c56588c494298e0051e34b524cb4860d7da8531`
- Verified implementation ancestor: `14525da518f7340768f939314cb15f90fb3dae96`
- Historical execution: `20260814T172224Z-490856f405bf`
- Authoritative DB SHA before and after proof: `5e830af41d58325d3f9e521f1b95f697b8151113cb783cf05a2a776e204639bc`

The proof ran only against disposable copies. The authoritative Mac DB, original historical artifacts, original historical lease, current local branch/HEAD, and existing untracked evidence directories remained unchanged.

## Proof result

The second repaired disposable-copy reproof passed.

Source revalidation confirmed:

- authoritative DB SHA matched exactly and had no SQLite sidecars;
- historical PID `59354` was dead and no Printer operational process was present;
- the original lease existed, was unheld, and retained SHA `71389ed8...`;
- all seven historical artifact SHAs matched;
- the pinned discovery batch remained `DISCOVERING` with null terminal cause/time;
- exactly eight linked discovery-work rows remained `SUCCEEDED` on Scheduler jobs `2011`–`2018`;
- exactly one nonterminal discovery batch existed globally.

The disposable DB was byte-identical to the authoritative DB at proof start. Its persisted `lease_lock_path` was deliberately left unchanged. The repaired `lease_lock_path_override` was proven to select only `<DISPOSABLE_ARTIFACT_ROOT>/campaign.lease.lock`, so the original lease could not be targeted by the disposable proof.

## First invocation

The exact historical reconciliation returned:

`V2_9_8B_HISTORICAL_FOUR_TOKEN_RECONCILED`

Independent before/after snapshots produced 45/45 passing checks.

Exactly ten DB row identities changed and no others:

1. historical campaign;
2. historical campaign run;
3. Cycle 1;
4. slot 1;
5. slot 2;
6. supervision;
7. tracking queue 58;
8. tracking queue 59;
9. historical factory run;
10. the exact pinned historical discovery batch.

Required final states were proven:

- campaign / run / Cycle 1: `TERMINAL_FAILED`;
- both slots: `MANUAL_REVIEW`;
- queues 58 / 59: `SKIPPED` with action `MANUAL_REVIEW`;
- supervision: `TERMINAL / FAILED` with cleanup and lease-release timestamps;
- historical factory run: `SAFE_STOPPED`;
- pinned discovery batch: `TERMINAL_FAILED`;
- disposable lease: absent;
- original lease: still present with unchanged SHA.

The exact original first terminal cause remained preserved on all six relevant carriers:

`FourTokenFactoryAdapterError: cycle terminal reconciliation requires a fresh transaction`

For the discovery batch, the cause was preserved, `terminal_at` became non-null, and all fourteen other persisted columns remained byte-identical.

Additional independent checks proved:

- all eight discovery-work rows remained unchanged and `SUCCEEDED`;
- Scheduler jobs `2011`–`2020` remained unchanged;
- campaign Scheduler-work rows remained unchanged;
- no non-approved table hash changed;
- all eight approved tables changed as expected;
- locked retrieval and financial table hashes remained unchanged;
- campaign windows remained zero;
- factory steps remained zero;
- Cycle-2 attempts remained zero;
- disposable DB migration ledger remained 55 / head 055;
- migration-056 provenance remained absent from the disposable DB;
- integrity check remained `ok`;
- foreign-key violations remained zero;
- no nonterminal discovery batch remained after reconciliation.

The restore-rehearsal copy under the recovery-run artifact applied migration 056 only inside that throwaway rehearsal copy. The reconciled disposable DB itself remained at migration 55 / head 055 with no migration-056 table.

## Idempotent replay

The second invocation returned:

`V2_9_8B_HISTORICAL_FOUR_TOKEN_ALREADY_RECONCILED`

The disposable DB SHA was unchanged before and after invocation two (`83b81e7e...`), and no second recovery directory was created because replay returned before backup/mutation.

This proves the strengthened terminal discovery-batch predicate and the disposable physical lease boundary are both compatible with exact idempotent replay.

## Authoritative evidence after proof

After disposable proof completion:

- authoritative DB SHA remained exactly `5e830af41d58325d3f9e521f1b95f697b8151113cb783cf05a2a776e204639bc`;
- no SQLite sidecars existed;
- original lease remained present with unchanged SHA `71389ed8...`;
- all seven historical artifact SHAs remained unchanged;
- original artifact-root listing remained unchanged;
- authoritative pinned batch remained `DISCOVERING` with null terminal cause/time;
- authoritative campaign remained `RUNNING`.

No authoritative reconciliation occurred.

## Money-usefulness contribution

This proof removes the final known disposable-verification blocker around bounded cleanup of abandoned historical ownership. It increases confidence that persistent memory-growth operations can be recovered without corrupting Scheduler, discovery, retrieval, or financial state. It does not create or unlock any trading capability.

## What this improves

- proves the exact ten-row reconciliation contract against a byte-identical copy of the real authoritative DB;
- proves the discovery batch is the only additional mutable residue;
- proves disposable lease handling cannot target the original lease;
- proves unrelated Scheduler/discovery work and locked domains remain unchanged;
- proves exact idempotent replay after reconciliation;
- provides sufficient bounded evidence to proceed to an authoritative-reconciliation readiness review.

## What remains locked

This closeout does not authorize:

- authoritative DB mutation yet;
- source fetching or discovery runs;
- Scheduler/runtime execution;
- memory generation;
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

All Solana-only, memecoin-only, paper-only, Source Governor, Central Scheduler, clean-memory, no-scoring, no-paid-dependency, and lane-boundary restrictions remain unchanged.

## Next lane

The next allowed lane is an **authoritative historical reconciliation readiness review**, not authoritative mutation itself.

That readiness review must be read-only and must freshly revalidate the authoritative DB/artifact/lease state, confirm no Printer process or lease holder exists, define a new immediate pre-mutation backup and rollback boundary, re-confirm the exact ten-row mutation contract and disposable-proof evidence, and specify a stop-on-any-drift gate.

Only a separate PASS closeout from that readiness review may authorize the bounded authoritative reconciliation operation.

## Functionality Risks / Setbacks / Efficiency Blockers

- The authoritative DB still intentionally contains the stranded historical residue until an explicit later mutation lane passes readiness.
- Any drift in DB SHA, lease bytes/path/ownership, historical artifacts, discovery batch/work, Scheduler rows, or process state invalidates the current mutation assumptions and must block authoritative reconciliation.
- The disposable proof validates the exact current historical state only; it is not a generic recovery authorization for other executions.
- The unrelated pre-existing insufficient-pool scheduler-cancellation test drift remains outside this lane and must not be used to expand scope.