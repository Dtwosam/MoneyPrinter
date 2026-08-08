# Printer V1 V2-9.8B Post-C8 Local Operational Lineage and One-Shot Staging Reconciliation — Design

Date: 2026-08-08

Linear: `DTW-71`

## Design verdict

`V2_9_8B_POST_C8_LOCAL_OPERATIONAL_LINEAGE_STAGING_RECONCILIATION_DESIGN_PASS`

The DTW-70 blocker is an environment/evidence alignment problem, not a newly proven code defect. The repair must preserve the authoritative DB byte-for-byte and must not delete or rewrite historical one-shot evidence.

## Starting facts

- local Mac branch: `agent/v2-9-8b-window-15m-fresh-authorization-after-source-request-scope-enforcement`;
- local Mac HEAD: `7defc2945c42053d9c770ebc66248d27c63ff4a3`;
- approved remote target branch: `agent/v2-9-8b-post-c8-operational-window15m-rereadiness-audit`;
- approved remote target HEAD for this design: `cd0a422d84a0076dd03ba34f1a764fc8795f6aaf`;
- ancestry: local HEAD is an ancestor of the post-C8 lineage; target is 215 commits ahead after the DTW-70 closeout;
- authoritative DB fresh SHA-256: `7380f9b4c172c218e6c9ab1fed996a06fcdeb90ff67f2b414d805f280403d54e`;
- DB migration/integrity/FK checks PASS;
- tracked/index local tree is clean; operator evidence is untracked;
- seven external `.staging` entries exist and must be classified, not deleted.

## Phase 1 — read-only/fetch audit

Before any worktree switch:

1. fetch only the approved remote target branch;
2. verify fetched target HEAD equals the approved target SHA;
3. verify current local HEAD is an ancestor of target;
4. compute the exact intersection between current untracked files and paths tracked by target;
5. if any collision exists, STOP without checkout;
6. classify every `.staging` entry by file inventory, hashes, marker/terminal presence and related authorization ID;
7. inspect exact factory-run status column/state so the generic DTW-70 capture gap is closed;
8. re-hash authoritative DB before any alignment.

No files are moved, deleted, staged, committed, reset, cleaned or rewritten in Phase 1.

## Phase 2 — local alignment, only after Phase 1 PASS

If and only if untracked collision count is zero and staging evidence is fully classified:

- switch to a new local branch named exactly `agent/v2-9-8b-post-c8-operational-window15m-rereadiness-audit` tracking the fetched remote branch;
- do not move the old local branch pointer;
- do not use `git reset --hard`, `git clean`, stash, force checkout, or deletion;
- leave `operator-runs/`, authoritative DB, and `~/PrinterOperations` evidence intact.

If a local branch with that name already exists but does not equal the approved remote SHA, STOP rather than force-update it.

## Phase 3 — bounded read-only proof

After switch:

- exact branch name and HEAD equal approved target;
- tracked/index clean;
- untracked evidence preserved;
- authoritative DB SHA remains exactly `7380f9b4c172c218e6c9ab1fed996a06fcdeb90ff67f2b414d805f280403d54e`;
- no SQLite sidecars;
- migration ledger still matches 52/52 and integrity/FK remain clean;
- factory-run states and all other operational surfaces show no active work;
- staging classification remains evidence-only and no current authorization authority exists;
- zero-I/O concrete composition preflight may be run only after the exact post-C8 branch is active.

## Staging classification law

Each staging directory must be assigned one of:

- `HISTORICAL_CONSUMED_STAGING_RESIDUE` when the related authorization has a canonical create-once application marker;
- `HISTORICAL_UNCONSUMED_PREMARKER_RESIDUE` when no marker exists and the related authorization is expired/superseded/historical;
- `TEST_OR_SIMULATION_PREMARKER_RESIDUE` only for clearly test/simulation-owned directories with no production authority;
- `BLOCKED_AMBIGUOUS_STAGING` for anything not provably covered above.

Classification does not authorize deletion. Cleanup, if ever desired, requires a separate evidence-retention decision after readiness is restored.

## Money-usefulness contribution

This alignment puts the real Mac operator checkout onto the exact code that passed the completed Checkpoint hardening sequence while preserving the existing clean authoritative corpus and historical evidence. It reduces the risk that a future one-use authorization burns against obsolete code.

## What remains locked

No authorization, wrapper application, provider/source fetching, Printer/Scheduler runtime, authoritative DB mutation, memory generation, WINDOW_1H+, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits or PnL.

## Functionality Risks / Setbacks / Efficiency Blockers

- untracked evidence may collide with target tracked paths; collision must stop alignment;
- stale staging residue may be harmless historical evidence but cannot be assumed harmless without classification;
- the authoritative DB must remain byte-identical across Git alignment;
- forcing checkout/reset/clean would destroy the evidentiary value of the audit and is prohibited;
- no broad test suite is needed for this environment-only repair.

## Stop condition

Design PASS permits Phase 1 audit only. Do not switch the worktree until Phase 1 returns zero untracked-path collisions and no ambiguous staging classification.