# Printer V1 V2-9.8B — Historical Lease-Path Disposable-Proof Repair Design

## Verdict

`V2_9_8B_HISTORICAL_LEASE_PATH_DISPOSABLE_PROOF_REPAIR_DESIGN_PASS_READY_FOR_FOCUSED_TDD`

## Proven blocker

The second real disposable-copy reproof reached `_historical_preflight()` and blocked before writes because the byte-identical copied DB still stores the original absolute `lease_lock_path`, while the copied artifact root contains its own `campaign.lease.lock`.

The existing recovery then has the same problem later: `cleanup_campaign_supervision()` releases the persisted DB path directly, and `_historical_already_reconciled()` requires that persisted path to be absent. Therefore changing only preflight would remain unsafe and could mutate the authoritative lease.

## Design

Add one optional physical lease-path override at the filesystem boundary.

Rules:

1. The historical DB row is never rewritten to make the proof work; its byte identity remains protected by the pinned DB SHA.
2. When no override is supplied, all existing authoritative/production behavior remains unchanged and the persisted `lease_lock_path` is used.
3. When an override is supplied to exact historical reconciliation, it must resolve exactly to `<artifact_root>/campaign.lease.lock`; arbitrary paths fail closed.
4. The preflight validates the persisted lease identity separately from the physical override and validates the lease payload/expiry from the selected physical lease.
5. `cleanup_campaign_supervision()` may receive the same explicit physical release path and release only that file; DB supervision state is still the canonical durable owner.
6. `_historical_already_reconciled()` must check absence of the same selected physical lease so idempotent replay is truthful on both authoritative and disposable runs.
7. No contract values, source/Scheduler/runtime behavior, row allowlist, historical cause, migration state, or financial/retrieval locks change.

This is dependency injection at the filesystem boundary, not a new recovery owner.

## Minimum sufficient TDD

RED must prove:

- byte-identical disposable DB + copied artifact root currently blocks because the persisted original lease path differs;
- no-override behavior remains pinned to the persisted lease;
- an arbitrary override outside the supplied artifact root is rejected before mutation.

GREEN must prove:

- exact disposable override allows the historical ten-row reconciliation while deleting only the disposable lease;
- original/persisted physical lease remains untouched in the test fixture;
- second invocation reports `ALREADY_RECONCILED` with zero writes;
- existing historical reconciliation, supervision cleanup, shared-terminal, and four-token terminal regressions remain green.

Verification: focused affected tests, `py_compile` for changed Python modules, `git diff --check`. No broad suite.

## Money-usefulness contribution

This removes a proof-environment coupling that currently prevents safe cleanup of abandoned historical ownership. It improves trustworthiness of persistent corpus operations but creates no market, memory, retrieval, decision, or trading capability.

## What remains locked

Authoritative reconciliation, fresh proof authorization, another operational four-token proof, six-token widening, longer windows, retrieval, decisions, BUY/SELL/HOLD, positions, trade events/audits, and PnL remain locked.

## Functionality Risks / Setbacks / Efficiency Blockers

- A free-form path override could redirect deletion to unrelated evidence. Control: exact `<artifact_root>/campaign.lease.lock` equality in historical recovery.
- Fixing preflight alone would still let canonical cleanup delete the original lease. Control: carry the same physical-path boundary through cleanup and replay validation.
- Changing the copied DB to rewrite the lease path would invalidate the proof premise. Control: DB remains byte-identical before invocation.
