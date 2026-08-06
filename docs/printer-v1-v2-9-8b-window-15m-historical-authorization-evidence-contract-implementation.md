# Printer V1 V2-9.8B WINDOW_15M Historical Authorization Evidence Contract Implementation

| Field | Value |
| --- | --- |
| Document title | Historical Authorization Evidence Contract Implementation |
| Date | 2026-08-06 |
| Lane type | implementation + focused disposable proof |
| Baseline branch | `agent/v2-9-8b-window-15m-historical-authorization-trust-root-design-revision` |
| Baseline full HEAD | `a80673db2187bc394872acd1941385307fe7e155` |
| Implementation branch | `agent/v2-9-8b-window-15m-historical-authorization-evidence-contract-implementation` |
| Final full HEAD | `b8f08d59e28e3a40a4d65474a418f0e5c7180979` |
| Controlling design | `docs/printer-v1-v2-9-8b-window-15m-historical-authorization-evidence-contract-design.md` (R2) |

## 1. Root cause

`COMMITTED_CODE_DEFECT` in the Git-provenance authorization manifest boundary and one-shot wrapper builder.

Production required:

```text
F == T ∪ M
```

`build_manifest_bytes` bound only current Migration-050 and current authorization packages into `M`. Preserved untracked prior authorization packages remained outside `T` and `M`, so pre-marker validation failed with:

```text
GitProvenanceAuthorizationError:
unexpected untracked repository file not covered by manifest:
operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260805T224959Z/final_authorization.json
```

## 2. Production changes

| Path | Role |
| --- | --- |
| `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py` | Manifest V2, trust-root validation, historical owner, split reconciliation, union allowlist |
| `src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py` | Manifest V2 builder, pre-marker staging cleanup, marker consumption wording |
| `src/printer_v1/operator_cli/window_15m_authorization_preparation.py` | Non-consuming preparation parity owner (new) |
| Focused tests | Manifest, wrapper, ignored/trust-boundary, new historical contract |
| This document + closeout | Implementation record |

## 3. Trust-root implementation

Canonical source:

`prior_authorizations_non_reusable` on the **current** final authorization document.

Validation (`validate_prior_authorizations_non_reusable` / `extract_approved_historical_authorization_ids`):

- value is an array;
- each item is a non-empty safe authorization ID (`^[A-Za-z0-9_.-]+$`);
- unique, lexicographically sorted;
- current authorization ID absent;
- no path, wildcard, glob, prefix, or directory entry;
- empty array is lawful.

Directory discovery never creates or broadens the approved set.

## 4. Manifest V2 schema

```text
PRINTER_V1_GIT_PROVENANCE_MANIFEST_V2
```

Exact top-level keys:

```text
schema_version
authorization_id
authorization_file
repository
authorized_command
migration_execution_id
created_at
files
historical_authorization_evidence
```

Marker schema unchanged:

```text
PRINTER_V1_APPLICATION_MARKER_V1
```

`files[]` remains current-only (`MIGRATION_050_EVIDENCE`, `WINDOW_15M_AUTHORIZATION_EVIDENCE`).

`historical_authorization_evidence[]` is required and may be empty.

Manifest V1 is rejected after the atomic builder+validator change. No intermediate HEAD was published with split schema ownership.

## 5. Historical owner contract

Canonical owner:

`enumerate_historical_authorization_evidence` in `git_provenance_authorization_manifest.py`

Behavior:

1. Validates `operator-runs/` and the authorization package root as real non-symlink directories.
2. Scans only immediate package directories under `operator-runs/v2-9-8b-window-15m-final-authorization/`.
3. Validates each directory name with the safe-ID law.
4. Rejects current ID in the approved set.
5. For each approved historical ID: inventories regular files, excludes tracked HEAD paths from `H`, emits exact untracked records.
6. Rejects unapproved non-current packages that contain untracked regular files.
7. Permits approved IDs that are absent or empty without inventing evidence.
8. Sorts by path; rejects duplicates; never follows symlinks; never permits directory-only or wildcard rules.

Each historical record:

```text
path, sha256, size, evidence_class, authorization_id, terminal_disposition
```

`evidence_class = HISTORICAL_WINDOW_15M_AUTHORIZATION_EVIDENCE`

`terminal_disposition` is diagnostic only (default `DISPOSITION_NOT_AVAILABLE`; named policy labels for the two controlling package IDs).

## 6. Set reconciliation

```text
T  tracked historical operator-runs at exact HEAD
M  current manifest files[] only
H  approved historical authorization evidence
U  = M ∪ H
F  complete regular-file inventory under operator-runs/
C  inventory under the two current package roots
A  validated prior_authorizations_non_reusable
```

Laws:

```text
F = T ∪ M ∪ H
C = M
authorization_ids(H) ⊆ A
T ∩ M = ∅
T ∩ H = ∅
M ∩ H = ∅
H ∩ C = ∅
```

`_reconcile_evidence_sets` receives separate `current_manifest_paths` and `historical_paths`. Historical paths never satisfy current-package identity.

Allowlist / digest:

```text
allowed_untracked_paths = sorted(paths(M) ∪ paths(H))
file_count = |M ∪ H|
allowed_file_set_sha256 binds path/size/sha256/package_kind over M∪H
```

## 7. Preparation parity

Module:

`src/printer_v1/operator_cli/window_15m_authorization_preparation.py`

Function:

`prepare_git_provenance_authorization_parity`

Uses exact production:

```text
build_manifest_bytes
+
validate_git_provenance_manifest_pre_marker
```

Writes a temporary manifest outside the repository and application root; removes it in `finally`; creates no marker, no canonical application directory, no child, no provider contact, no DB mutation, no Git mutation.

Honest status:

```text
inventory_pre_marker_parity_PASS
does not by itself equal full_apply_readiness_PASS
```

## 8. Marker consumption law

Consumption occurs only after successful create-once write of:

```text
APPLICATION_ROOT/<authorization_id>/application-marker.json
```

Pre-marker failure:

```text
UNCONSUMED_PRE_MARKER_BLOCKED
```

Post-marker terminals remain `CONSUMED_*`. Historical packages were not edited to retrofit older wording.

## 9. Staging cleanup

`_cleanup_pre_marker_staging` in the wrapper:

- operates only on the exact invocation staging path;
- rejects symlink staging paths;
- lists without following symlinks;
- deletes only known invocation-owned regular files (`git-provenance-manifest.json`);
- never uses `shutil.rmtree`;
- never touches sibling staging or canonical application evidence;
- preserves the original exception as controlling;
- reports cleanup failure as secondary information;
- never implies consumption.

Best-effort empty `rmdir` after successful manifest promotion is retained.

## 10. Restrictions honored

This lane did **not**:

- run `Start-PrinterV1-Window15M-OneShot.ps1`;
- call `apply_authorization_once` against the real repository;
- create or consume a real authorization / application marker;
- modify either historical authorization package;
- clean real external staging residue;
- edit `.gitignore`;
- contact providers;
- run discovery, Scheduler, campaign, memory, or DB mutations;
- unlock retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.

## 11. Money-usefulness contribution

Removes the deterministic provenance inventory blocker that wasted one-use `WINDOW_15M` authorizations while preserving exact historical audit evidence. Enables a later readiness lane and one fresh authorization on the repaired HEAD without laundering unknown directories into historical trust.
