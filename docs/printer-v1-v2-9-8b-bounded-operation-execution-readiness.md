# Printer V1 V2-9.8B Bounded Operation Execution Readiness

Date: 2026-08-15

## Verdict

`V2_9_8B_BOUNDED_OPERATION_EXECUTION_READINESS_BLOCKED:migration_056_current_evidence_is_git_tracked_but_the_current_package_contract_requires_untracked_evidence`

**Classification: `CONTRACT_DRIFT_BLOCKER`.** Not patched in this lane.

## Boundary

Readiness / discriminating proof only. The authorization was not consumed,
`apply_authorization_once()` was not called, no application marker was created,
no Printer/Scheduler/campaign/discovery/source/memory runtime ran, the
authoritative database was not mutated, and no code was repaired.

## Authorization preconditions — all hold

| check | value |
| --- | --- |
| authorization | `V2_9_8B_FOUR_TOKEN_PROOF_AUTH_20260815T174451Z_1c9bc205` |
| SHA-256 | `b997fda2bc500f2239ccf28c454e1f1fac81ef70219ff3520a87783493e91ba8` (exact) |
| unconsumed | yes — no application directory, no marker |
| temporally valid | yes — expires `2026-08-16T05:44:51Z`, **11 h 34 m** remaining at test time |
| authoritative DB | `555f9558a4f83ac4639ed5d909768a0c9d4b23871f65c31b251a702efb13273e` |
| zero state | clean, all eleven domains `0` |

The authorization itself is sound. The blocker is in the repository evidence
topology it must be consumed against.

## 1. Tracked/untracked classification of migration-056 evidence

At bound HEAD `36c9e2ccfa35186133fce9e600a54c6e8cc46e68`:

| evidence root | tracked files at bound HEAD |
| --- | --- |
| `operator-runs/v2-9-8b-migration-056-application` (**current migration**) | **4 — TRACKED** |
| `operator-runs/v2-9-8b-four-token-final-authorization` (**current authorization**) | 0 — untracked |
| `operator-runs/v2-9-8b-migration-055-application` | 0 — untracked |
| `operator-runs/v2-9-8b-authoritative-mig050` | 0 — untracked |

The four tracked files are `pre_application_snapshot.json`,
`post_application_snapshot.json`, `migration_056_application_result.json`, and
`disposable_rehearsal.json`.

Migration-056 is the **only** current-package evidence that is Git-tracked. Every
comparable predecessor package is untracked.

## 2. Production contract

`git_provenance_authorization_manifest._reconcile_evidence_sets()` enforces two
independent rules that both bear on this:

```python
tracked_allowlist_overlap = t_paths & allowlist_u
if tracked_allowlist_overlap:
    raise GitProvenanceAuthorizationError(
        "untracked allowlist path is tracked instead of untracked: " + ...)
```

where `allowlist_u = M ∪ Ha ∪ Hm` — current manifest paths plus approved
historical authorization and migration evidence. And immediately after:

```python
tracked_current = {
    path for path in t_paths
    if any(_is_beneath_root(path, root) for root in current_package_roots)
}
if tracked_current:
    raise GitProvenanceAuthorizationError(
        "tracked file exists inside a current evidence package: " + ...)
```

with `current_package_roots = (migration_package_root, authorization_package_root)`.

**Answer to the question posed: yes.** The contract rejects tracked files beneath
the current migration/authorization package roots, on two separate checks. Current
evidence packages are required to be untracked operator evidence, bound by path,
size, and SHA-256 rather than by Git tracking.

## 3. Exact pre-marker result — the decisive test

Reproduced in a disposable local clone outside the user's working repository:

- clone at `…/scratchpad/premarker-clone-181247Z`
- local branch exactly `agent/v2-9-8b-fresh-authorization-creation`
- HEAD exactly `36c9e2ccfa35186133fce9e600a54c6e8cc46e68`
- **`git remote remove origin`** — 0 remotes, so no remote ref could be mutated
- exact current and approved historical operator evidence copied from the source
  checkout; authorization file verified at SHA `b997fda2…` inside the clone
- manifest built with `build_manifest_bytes()` (5 files) and written to a
  temporary path **outside the clone**
- **no application marker was built or written; the child was not invoked**

`validate_git_provenance_manifest_pre_marker(..., profile=FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE)`:

```
PRE-MARKER RESULT: FAIL
  untracked allowlist path is tracked instead of untracked:
    operator-runs/v2-9-8b-migration-056-application/MIGRATION_056_20260815T164802Z/disposable_rehearsal.json,
    operator-runs/v2-9-8b-migration-056-application/MIGRATION_056_20260815T164802Z/migration_056_application_result.json,
    operator-runs/v2-9-8b-migration-056-application/MIGRATION_056_20260815T164802Z/post_application_snapshot.json,
    operator-runs/v2-9-8b-migration-056-application/MIGRATION_056_20260815T164802Z/pre_application_snapshot.json
```

The failure fires at `tracked_allowlist_overlap`, which precedes `tracked_current`;
both would reject the same four paths. The real pre-marker boundary therefore
fails closed **before** any marker could be created, exactly as designed.

## Root cause — an error introduced by an earlier lane in this programme

The bounded authoritative migration-056 lane committed the four evidence JSONs to
the migration branch. That was wrong: the current-package contract requires
current evidence to be untracked, which is why migration-055, migration-050, and
the four-token authorization root all carry zero tracked files.

The fresh-bounded-operation authorization readiness review then compounded it by
reporting the package as "BINDABLE" on the basis of
`_current_package_inventory(...)` resolving four paths. That helper computes
inventory membership only; it does **not** apply the tracked-rejection rules. The
"bindable" conclusion was measured with the wrong function and was wrong about the
actual gate. This lane's discriminating test is what surfaced it — which is
precisely why a pre-marker proof exists before consumption.

No prior verdict is retracted beyond that point: the authorization document
itself, its DB binding, policy, one-shot semantics, and non-reuse chain were all
independently verified and remain correct.

## Authorization remains unconsumed

Verified after the test:

- package still contains exactly one file, `final_authorization.json`, SHA
  `b997fda2…` unchanged
- no application directory for the ID; zero paths anywhere under the application
  root matching `1c9bc205`
- no `git-provenance-manifest.json` written inside the source repository
- authoritative DB SHA unchanged at `555f9558…`

The manifest produced for the test lives only in a temporary directory outside
both the clone and the source repository.

## Money-usefulness contribution

The pre-marker proof cost nothing and saved the authorization. Consumption writes
the application marker **before** the child runs, so had this been attempted as a
real execution, the authorization would have been irreversibly consumed and the
run would still have failed at the same boundary — burning scarce one-use
authority on a repository-topology error. The authorization remains intact with
11 h 34 m of validity, and the defect is now precisely located.

## What remains locked

One-shot execution, consumption of this authorization, campaign start, six-token
proof and capacity widening, 12h/24h activation, 1h rerun, source fetching and
discovery, memory generation, Scheduler work creation, retrieval, paper
decisions, BUY/SELL/HOLD, positions, trade events, paper audits, PnL, wallets,
private keys, signing, live execution, real funds, paid APIs,
scoring/ranking/confidence/weighted logic, embeddings, and vectors.

Solana memecoin-only and paper-only remain in force.

## Functionality Risks / Setbacks / Efficiency Blockers

- **The clock is now the binding risk.** The authorization expires
  `2026-08-16T05:44:51Z`. Any repair lane plus a re-run of execution readiness
  plus the proof's own 5 h 15 m wall envelope must all fit inside the remaining
  window, or this authorization dies unused like two of its three predecessors.
- The repair is not merely "untrack the four files." Removing them from Git
  changes the bound HEAD, which invalidates the authorization's repository
  binding — so the fix and a fresh authorization are coupled. Sequencing must be
  decided deliberately rather than improvised under time pressure.
- Two viable directions exist and this lane does not choose between them:
  untrack the migration-056 evidence so it matches the 050/055 pattern, or amend
  the current-package contract to admit tracked current evidence. The first
  preserves the existing contract; the second changes a security-relevant rule
  and would need its own design and proof.
- `_current_package_inventory` remains a trap for future lanes: it reports
  membership without applying tracked-rejection, and reading it as a bindability
  check produces a false green. Any future readiness lane should call the real
  pre-marker validator instead.
- The migration-056 database schema itself is unaffected and correct. Only the
  Git tracking status of its evidence package is wrong.
- No code was repaired and no broad suite was run, per this lane's boundary.

## Exact next lane

`V2-9.8B Migration-056 Evidence Tracking Contract Drift Repair Design` — a
design-only lane that:

1. chooses between untracking the migration-056 evidence package and amending the
   current-package reconciliation contract, with reasons;
2. specifies the coupling between that change and authorization re-creation,
   since any commit alters the bound HEAD;
3. defines the bounded proof required, which must include a real
   `validate_git_provenance_manifest_pre_marker` PASS rather than an
   `_current_package_inventory` check;
4. states explicitly whether the current authorization
   `V2_9_8B_FOUR_TOKEN_PROOF_AUTH_20260815T174451Z_1c9bc205` can survive the
   repair or must be discarded and re-created.

Do not consume the current authorization and do not start the campaign until that
design and its implementation close PASS.
