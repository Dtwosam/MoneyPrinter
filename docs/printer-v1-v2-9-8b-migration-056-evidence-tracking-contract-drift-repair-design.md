# Printer V1 V2-9.8B Migration-056 Evidence Tracking Contract Drift Repair Design

Date: 2026-08-15

## Verdict

`V2_9_8B_MIGRATION_056_EVIDENCE_TRACKING_REPAIR_DESIGN_PASS_READY_FOR_IMPLEMENTATION`

## Classification

DESIGN ONLY for the confirmed `CONTRACT_DRIFT_BLOCKER` from bounded-operation execution readiness.

## Decision

Preserve the existing fail-closed provenance contract. Do **not** change `_reconcile_evidence_sets()` to admit tracked current evidence.

Repair the repository evidence topology instead:

- the four JSON files under `operator-runs/v2-9-8b-migration-056-application/MIGRATION_056_20260815T164802Z/` must stop being Git-tracked at the new implementation HEAD;
- their exact bytes remain preserved locally as current operator evidence;
- no `.gitignore` widening is required;
- no production code, migration SQL, database state, Source Governor, Scheduler, memory, retrieval, or paper-trading rule changes.

This matches the established migration-050 / migration-055 and authorization evidence model: current evidence is outside Git trust and is bound independently by exact path, size, and SHA-256.

## Why the alternative is rejected

Allowing tracked files inside current evidence packages would weaken two independent protections already enforced by `_reconcile_evidence_sets()`:

1. tracked files must not overlap the untracked current/historical allowlist;
2. tracked files must not exist beneath either current package root.

The defect is packaging drift introduced when Migration-056 evidence was committed, not a defect in those provenance rules. Changing the rules would broaden security authority unnecessarily.

## Current authorization disposition

`V2_9_8B_FOUR_TOKEN_PROOF_AUTH_20260815T174451Z_1c9bc205` cannot survive the repair.

Any commit that removes the four files from Git tracking changes repository HEAD, while the authorization is bound to `36c9e2ccfa35186133fce9e600a54c6e8cc46e68`. It must therefore remain preserved, unconsumed, and non-reusable/superseded. Do not rewrite, delete, or consume it.

Its current expiry is no longer the governing schedule for the repair. A fresh authorization must be issued only after the repaired HEAD is proven.

## Implementation contract

Implementation must start from this design commit and:

1. record the exact path, size, SHA-256, and bytes of the four Migration-056 JSON files before changing the index;
2. remove exactly those four files from Git tracking without deleting or modifying their working-tree bytes;
3. commit the tracking-state change only; do not rewrite migration history;
4. verify at the new HEAD that `git ls-files` reports zero tracked files beneath the current Migration-056 execution root;
5. verify all four local evidence files still exist byte-identically and are visible/ignored untracked evidence acceptable to the existing profile;
6. leave the authoritative DB untouched at SHA `555f9558a4f83ac4639ed5d909768a0c9d4b23871f65c31b251a702efb13273e`, migration 56/head056, with clean zero state.

No production-code change is approved by this design.

## Bounded proof required

Before any new real authorization is created, prove the repaired topology with the **real** pre-marker validator, not `_current_package_inventory()`.

Use a disposable clone/worktree at the repaired branch/HEAD and exact local operator evidence. Build a disposable, non-authoritative production-shaped authorization bound to that repaired Git/DB state, write the manifest outside the repository, then call:

`validate_git_provenance_manifest_pre_marker(..., profile=FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE)`

Required result: PASS with current Migration-056 evidence classified untracked and no tracked-current overlap.

Do not create an application marker and do not launch the child.

After that proof closes PASS, the sequence is:

1. repair closeout;
2. fresh authorization creation at the repaired HEAD;
3. independent authorization review;
4. final execution readiness using the real pre-marker validator;
5. only then one-shot bounded operation execution.

## Money-usefulness contribution

Restores the real consumption path without weakening provenance, so the next scarce one-use authorization can reach the bounded memory-growth operation instead of being burned on repository-evidence topology.

## What improves

- Migration-056 current evidence returns to the intended untracked operator-evidence model.
- The actual pre-marker validator becomes a mandatory readiness check.
- The false-green use of `_current_package_inventory()` as a bindability proxy is explicitly retired.

## What remains locked

Authorization consumption, campaign start, source fetching, discovery, Scheduler/runtime, memory generation, 1h rerun, 12h/24h activation, retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events, paper audits, PnL, wallets/private keys/live execution, scoring/ranking/confidence, embeddings/vectors.

## Functionality Risks / Setbacks / Efficiency Blockers

- Removing tracking changes HEAD, so every real authorization bound to the old HEAD is unusable and must not be salvaged.
- Losing the local four-file evidence after untracking would make current Migration-056 provenance unavailable; exact bytes must be preserved before the index change and verified afterward.
- A future fresh clone will not contain these operator files automatically; execution preparation must restore/copy the exact evidence into the bound launch checkout as already required for untracked authorization evidence.
- No contract relaxation is permitted merely to reduce Git-status friction.

## Next lane

`V2-9.8B Migration-056 Evidence Tracking Contract Drift Repair Implementation`

Implement only the tracking-state repair and its bounded pre-marker proof. No authorization creation and no runtime in that lane.