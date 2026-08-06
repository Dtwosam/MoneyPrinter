# Printer V1 V2-9.8B WINDOW_15M Historical Authorization Evidence Contract Design

| Field | Value |
| --- | --- |
| Status | Approved design revision (`DESIGN_PASS`) |
| Revision | R2 — Historical Authorization Trust Root |
| Lane type | design/specification only |
| Baseline design commit | `045d88f154caa9d7f6243aa8e3e694078e9dd4b3` |
| Original implementation baseline | `ef19f25489a01d86387bc55cb98a128601cdb036` |
| Design branch | `agent/v2-9-8b-window-15m-historical-authorization-trust-root-design-revision` |
| Date | 2026-08-06 |

## 1. Verdict

`V2_9_8B_WINDOW_15M_HISTORICAL_AUTHORIZATION_TRUST_ROOT_DESIGN_REVISION_COMPLETE`

R2 preserves the four-class historical-evidence design from R1 but corrects one unsafe trust assumption.

R1 allowed the historical-evidence owner to scan every non-current authorization directory and automatically emit every untracked regular file into `H`. That would have converted filesystem placement into authorization. A random safe-looking directory under the authorization package root could therefore have been hashed and accepted as historical evidence.

R2 supersedes that behavior.

Historical authorization trust must come from an exact approved-ID set declared by the **current final authorization document**. Filesystem discovery may verify and inventory those IDs, but it may never create or broaden the approved set.

This is still a design-only lane. It does not modify production code, tests, authorization packages, evidence, the authoritative database, providers, discovery, the Central Scheduler, Source Governor, campaigns, memory, retrieval, or paper-trading capabilities.

## 2. Controlling source stack

Use this design inside the active Printer V1 source stack:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`

Also governing this lane:

- `docs/printer-v1-python-builder-guide.md`
- `docs/printer-v1-v2-9-8b-window-15m-source-specific-admission-retained-evidence-repair-closeout.md`
- `docs/printer-v1-v2-9-8b-window-15m-exact-market-member-binding-repair-closeout.md`
- `docs/printer-v1-v2-9-8b-window-15m-dexscreener-orientation-binding-repair-closeout.md`
- `docs/printer-v1-v2-9-8b-window-15m-fresh-authorization-after-orientation-repair-closeout.md`
- the current Git-provenance manifest, one-shot wrapper, preparation and provenance owners

Required progression remains:

`audit/readiness -> design/specification -> implementation -> bounded proof/test -> closeout`

## 3. Incident and current dispositions

Two manual invocations of:

`V2_9_8B_WINDOW_15M_AUTH_20260806T005252Z`

blocked before marker creation with:

```text
GitProvenanceAuthorizationError:
unexpected untracked repository file not covered by manifest:
operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260805T224959Z/final_authorization.json
```

No child command, provider, discovery, Scheduler, campaign, or memory path started.

Dispositions remain:

```text
V2_9_8B_WINDOW_15M_AUTH_20260806T005252Z
= BLOCKED_UNCONSUMED_SUPERSEDED

V2_9_8B_WINDOW_15M_AUTH_20260805T224959Z
= PERMANENTLY_CONSUMED_PRESERVED
```

Neither package may be edited, deleted, moved, or reused.

## 4. Confirmed root cause

Classification:

`COMMITTED_CODE_DEFECT`

Current production uses:

```text
F == T ∪ M
```

where:

- `F` = every regular file under `operator-runs/`
- `T` = tracked historical paths at exact HEAD
- `M` = current manifest paths

`build_manifest_bytes` currently binds only:

1. the current Migration-050 package;
2. the current authorization package.

Preserved prior authorization packages are untracked, are not in `T`, and are not part of current `M`, so the pre-marker validator rejects them.

R1 correctly introduced a historical set `H`, but its first enumeration rule was too broad: it trusted every discovered non-current authorization directory. Path placement plus path/size/SHA-256 proves integrity after enumeration; it does not prove that the package was lawfully authorized.

## 5. R2 trust-root decision

### 5.1 Canonical trust source

The exact approved historical authorization ID set comes from the current final authorization document field:

`prior_authorizations_non_reusable`

For future authorization packages after this repair, that field becomes a required, validated trust declaration.

It is both:

- an explicit deny-reuse list; and
- the maximum historical authorization ID set that may contribute untracked files to `H`.

It is **not** populated by scanning the filesystem.

The authorization-preparation lane must supply it explicitly from known authorization history and must echo the exact list in its tracked closeout. Unknown directories discovered on disk must never be added automatically.

### 5.2 Required validation

The current authorization resolver must validate `prior_authorizations_non_reusable` before manifest construction:

- value is an array;
- every item is a non-empty string matching the existing safe-ID law;
- IDs are unique;
- IDs are sorted lexicographically for deterministic package bytes;
- the current authorization ID is absent;
- no wildcard, path, prefix, glob, or directory entry is accepted;
- an empty array is lawful when no prior IDs are approved.

Malformed or duplicate IDs block before staging and before marker creation.

### 5.3 Trust is declaration, not discovery

The historical owner receives the approved set as an argument. It may not derive or enlarge the set from package directories.

Required public contract:

```python
def enumerate_historical_authorization_evidence(
    *,
    repository_root: str | Path,
    current_authorization_id: str,
    approved_historical_authorization_ids: Collection[str],
    tracked_operator_runs_paths: set[str] | None = None,
    git_executable: str = "git",
    timeout_seconds: float = GIT_COMMAND_TIMEOUT_SECONDS,
    runner: Callable[..., Any] = subprocess.run,
) -> tuple[dict[str, Any], ...]:
    """Return exact approved historical authorization file records."""
```

The wrapper builder and non-consuming preparation parity owner must pass the same validated approved-ID set from the current authorization document.

No parallel caller-owned scan is allowed.

## 6. Evidence classes and set law

Define:

- `T` = tracked historical `operator-runs/` files at exact HEAD
- `M_mig` = current Migration-050 manifest files
- `M_auth` = current authorization manifest files
- `M = M_mig ∪ M_auth`
- `H` = exact untracked files belonging to explicitly approved historical authorization IDs
- `U = M ∪ H` = exact untracked allowlist
- `F` = complete regular-file inventory under `operator-runs/`
- `C` = filesystem inventory under the two current package roots
- `A` = validated `prior_authorizations_non_reusable` ID set

Required equality:

```text
F = T ∪ M ∪ H
```

Required disjointness:

```text
T ∩ M = ∅
T ∩ H = ∅
M ∩ H = ∅
C = M
H ∩ C = ∅
```

Required trust relation:

```text
authorization_ids(H) ⊆ A
```

Required completeness rule:

```text
every untracked non-current authorization package containing regular files
must have its authorization ID in A and every one of its untracked files in H
```

No other file is accepted.

## 7. Historical enumeration algorithm

Canonical owner:

`enumerate_historical_authorization_evidence`

Canonical module:

`src/printer_v1/operator_cli/git_provenance_authorization_manifest.py`

Algorithm:

1. Validate the repository root, `operator-runs/`, and authorization package root as real non-symlink directories.
2. Validate `current_authorization_id` and the exact approved set `A`.
3. Read tracked `operator-runs/` paths at exact HEAD into `T`.
4. Scan immediate package directories beneath:

   `operator-runs/v2-9-8b-window-15m-final-authorization/`

5. Any symlinked package directory, malformed non-empty package directory, non-regular entry, or symlinked entry blocks.
6. For the current authorization ID:
   - do not emit historical rows;
   - current files remain owned only by `M_auth`.
7. For a non-current package ID in `A`:
   - recursively inventory every regular file;
   - tracked files remain in `T` and are not emitted into `H`;
   - every untracked regular file emits one exact `H` record.
8. For a non-current package ID not in `A`:
   - if the package contains any untracked regular file, block;
   - a package represented entirely by tracked files remains trusted through `T` only;
   - an empty valid-ID directory contributes no files and does not create trust.
9. Sort historical rows by path.
10. Reject duplicate paths.
11. Reconcile the full inventory independently so an owner bug cannot omit an untracked file silently.

A directory’s existence never creates trust.

## 8. Historical record contract

Each `H` row has exact keys:

```json
{
  "path": "operator-runs/v2-9-8b-window-15m-final-authorization/<AUTH_ID>/<FILE>",
  "sha256": "<64 lowercase hex>",
  "size": 123,
  "evidence_class": "HISTORICAL_WINDOW_15M_AUTHORIZATION_EVIDENCE",
  "authorization_id": "<AUTH_ID>",
  "terminal_disposition": "DISPOSITION_NOT_AVAILABLE"
}
```

Rules:

- path is normalized repository-relative POSIX;
- path is beneath the matching approved authorization ID directory;
- path is not beneath the current authorization directory;
- size and SHA-256 match the current regular file;
- no symlink component is accepted;
- `authorization_id` equals the package directory segment;
- `authorization_id` belongs to `A`;
- disposition is diagnostic only and never creates trust or reuse authority.

Allowed diagnostic dispositions:

```text
CONSUMED_CHILD_EXITED_ZERO
CONSUMED_CHILD_EXITED_NONZERO
CONSUMED_CHILD_START_FAILED
CONSUMED_CHILD_NOT_STARTED
BLOCKED_UNCONSUMED_SUPERSEDED
PERMANENTLY_CONSUMED_PRESERVED
DISPOSITION_NOT_AVAILABLE
```

Named policy labels for `…005252Z` and `…224959Z` remain explicit closeout/design decisions. Runtime residue alone must not invent those policy labels.

## 9. Manifest V2 contract

Schema:

`PRINTER_V1_GIT_PROVENANCE_MANIFEST_V2`

Marker schema remains:

`PRINTER_V1_APPLICATION_MARKER_V1`

Required top-level keys:

```text
schema_version
authorization_id
authorization_file
repository
authorized_command
migration_execution_id
created_at
files
historical_authorization_trust
historical_authorization_evidence
```

### 9.1 Historical trust section

```json
{
  "source_field": "prior_authorizations_non_reusable",
  "approved_authorization_ids": ["<ID1>", "<ID2>"],
  "approved_authorization_ids_sha256": "<digest>"
}
```

The ID digest is computed over canonical JSON for the sorted ID array.

The validator must prove exact equality between:

- the approved IDs in the current final authorization document; and
- the IDs copied into `historical_authorization_trust`.

Mismatch blocks.

### 9.2 Current and historical sections

`files[]` remains current-only and retains the existing entry shape and package kinds:

- `MIGRATION_050_EVIDENCE`
- `WINDOW_15M_AUTHORIZATION_EVIDENCE`

`historical_authorization_evidence[]` contains only `H` rows.

It is required and may be empty.

Do not place historical rows into current `files[]`.

### 9.3 Digest and allowlist

`allowed_untracked_paths` becomes:

```text
sorted(paths(M) ∪ paths(H))
```

`file_count` / `allowed_file_count` becomes:

```text
|M ∪ H|
```

The allowed-file-set digest uses path, size, SHA-256 and evidence/package class for both sets, sorted by path.

The full manifest SHA-256 additionally binds:

- approved historical IDs;
- their ID-set digest;
- diagnostic authorization IDs and dispositions.

## 10. Split reconciliation

Required signature:

```python
def _reconcile_evidence_sets(
    *,
    current_manifest_paths: set[str],
    historical_paths: set[str],
    visible_paths: set[str],
    ignored_paths: set[str],
    tracked_paths: set[str],
    inventory_paths: set[str],
    current_package_roots: tuple[str, str],
    sidecar_untracked_paths: Iterable[str],
) -> None:
    ...
```

Use:

- `M` for current-package equality;
- `U = M ∪ H` for untracked/ignored allowlisting;
- `T ∪ M ∪ H` for complete inventory equality.

Required checks include:

```text
visible_effective − U = ∅
ignored − U = ∅
T ∩ U = ∅
M ⊆ F
H ⊆ F
M ⊆ C
C ⊆ M
C = M
H ∩ C = ∅
F = T ∪ M ∪ H
```

Forbidden implementation:

```text
manifest_paths = M ∪ H
missing_current = manifest_paths - C
```

That incorrectly treats historical files as current-package files.

## 11. Authorization preparation parity

A preparation PASS must be impossible when production wrapper pre-marker validation would reject the same repository state.

Canonical flow:

1. Resolve and hash-check the current final authorization using production rules.
2. Validate `prior_authorizations_non_reusable` into exact set `A`.
3. Build Manifest V2 using production `build_manifest_bytes`.
4. Use the canonical historical owner with `A`.
5. Write the manifest to a temporary directory outside the repository and outside the application root.
6. Call production `validate_git_provenance_manifest_pre_marker`.
7. Remove the temporary directory in `finally`.
8. Write no marker, canonical application directory, child output, provider request, or DB mutation.

Preparation and wrapper must use the same:

- authorization resolver;
- approved-ID validation;
- builder;
- historical owner;
- pre-marker validator;
- reconciliation law.

Operator-facing summaries must report separate counts:

```text
tracked_historical_count
current_manifest_count
historical_authorization_count
complete_inventory_count
allowed_untracked_count
approved_historical_authorization_id_count
```

Inventory parity PASS is not automatically full apply-readiness PASS. Temporal, ledger, source configuration, interpreter and composition gates remain separately reported.

## 12. Consumption law

Consumption occurs only when the create-once application marker is successfully written.

States:

```text
UNCONSUMED_PRE_MARKER_BLOCKED
CONSUMED_CHILD_NOT_STARTED
CONSUMED_CHILD_START_FAILED
CONSUMED_CHILD_EXITED_NONZERO
CONSUMED_CHILD_EXITED_ZERO
```

A pre-marker block leaves no marker and is technically unconsumed.

A superseded package remains non-reusable through exact HEAD/package policy even if technically unconsumed.

Future authorization packages must state:

```text
consumed_when = create_once_application_marker_successfully_written
pre_marker_block_consumes_authorization = false
wrapper_process_start_consumes_authorization = false
permanently_non_reusable_after_marker = true
```

All post-marker outcomes consume. No consumed authorization permits retry, rerun, resume, restart, successor, or concurrent second execution.

## 13. Staging cleanup

Pre-publication failures must clean only the exact invocation-specific staging directory.

Requirements:

- use `try/finally` around staging creation, manifest build/write and pre-marker validation;
- hold the exact staging path in a local variable;
- never use `shutil.rmtree`;
- never recurse into unknown entries;
- allow deletion only of known invocation-owned regular files, initially `git-provenance-manifest.json`;
- if an unexpected entry or symlink exists, preserve the directory and report a secondary cleanup blocker;
- never delete canonical application evidence or sibling staging directories;
- cleanup failure never replaces the original blocker;
- cleanup never creates or implies consumption.

Existing residue from the two blocked invocations must be inspected in a later bounded implementation/proof lane before any authorized cleanup. It is not part of this design revision.

## 14. Backward compatibility

- Manifest V1 is rejected after the atomic V2 builder/validator merge.
- Marker V1 remains unchanged.
- Current authorization-package schema remains V2, but future packages must contain a validated, deterministic `prior_authorizations_non_reusable` array.
- Existing blocked packages remain immutable and are not retrofitted.
- Tracked historical evidence remains trusted only through exact HEAD (`T`).
- Migration-050 evidence handling remains unchanged.
- The public PowerShell command remains unchanged.
- `capture_git_provenance` remains unchanged and receives `M ∪ H` as its exact allowlist.

## 15. Minimum implementation boundary

Production modules expected to change:

- `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py`
  - Manifest V2 schema;
  - approved-ID validation support;
  - historical owner;
  - historical section validation;
  - split reconciliation;
  - union allowlist digest.
- `src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py`
  - resolve/validate `prior_authorizations_non_reusable`;
  - Manifest V2 builder;
  - exact staging cleanup;
  - marker-based consumption wording/comments.
- `src/printer_v1/operator_cli/window_15m_authorization_preparation.py`
  - preferred non-consuming parity owner, or an equivalently named public function using production components.
- focused Git-provenance, wrapper, preparation and historical-evidence tests.
- implementation/proof/closeout documentation.

The Manifest V2 validator and builder must ship atomically. No intermediate HEAD may contain one without the other.

Out of scope:

- discovery and candidate admission;
- Source Governor or Central Scheduler runtime;
- memory generation;
- DB migrations or schema changes;
- provider calls;
- authorization creation;
- retrieval or paper-trading capabilities.

## 16. Minimum focused proof

Use disposable Git repositories, temporary external directories and disposable databases only.

Required tests:

1. One explicitly approved prior authorization with complete untracked files passes.
2. Multiple approved IDs and multi-file packages pass when complete.
3. A safe-looking but unlisted authorization directory containing an untracked file blocks.
4. Adding an unlisted directory before manifest construction blocks; the builder must not launder it into `H`.
5. An unknown non-authorization file under the authorization root blocks.
6. Current authorization ID in the approved set blocks.
7. Malformed, duplicate or unsorted approved IDs block.
8. Manifest trust IDs must equal current authorization-document IDs exactly.
9. Approved ID represented entirely in `T` passes without `H` rows.
10. Approved ID with mixed tracked and untracked files splits exactly between `T` and `H`.
11. Approved but locally absent or empty ID invents no files and does not pass unknown residue.
12. Altered historical file blocks.
13. Missing historical file blocks.
14. Additional file inside an approved package blocks unless exactly emitted and bound.
15. Duplicate current/historical path blocks.
16. Wildcards, directory-only entries and prefix allows are impossible.
17. Ignored and visible historical files reconcile exactly.
18. `allowed_untracked_paths == sorted(M ∪ H)`.
19. Complete inventory requires `F == T ∪ M ∪ H`.
20. Preparation and wrapper return the same pre-marker PASS/BLOCK for the same workspace.
21. Pre-marker failure creates no marker and starts no child.
22. Staging cleanup removes only the exact known staging directory.
23. Unexpected cleanup entry preserves the original blocker and leaves authorization unconsumed.
24. Marker write remains the consumption boundary.
25. Consumed authorization remains non-reusable.
26. `…005252Z` remains statically recorded as `BLOCKED_UNCONSUMED_SUPERSEDED`.
27. `…224959Z` remains permanently consumed and preserved.
28. `SELECTED_MINT_NOT_IN_REGISTRY` remains absent.
29. No provider, discovery, Scheduler, campaign, memory or authoritative DB write occurs.

Use minimum sufficient adjacent regressions only. Do not run a live wrapper or broad runtime suite.

## 17. Money-usefulness contribution

This repair removes a deterministic provenance blocker that prevents a lawful, repaired `WINDOW_15M` memory-growth attempt while preserving exact historical audit evidence.

The trust-root revision prevents the convenience repair from becoming a directory-wide evidence bypass. Only prior authorization IDs explicitly declared by the current authorization may contribute untracked historical files.

## 18. What this improves

- preserved prior authorization evidence can remain untracked without blocking every later authorization;
- unknown package directories cannot be self-authorized by location;
- every accepted historical file remains bound by exact path, size and SHA-256;
- preparation becomes an honest predictor of production pre-marker inventory validation;
- consumption wording matches marker creation;
- pre-marker staging residue is bounded and safely cleaned.

## 19. What this still does not unlock

- retrieval or dirty-memory use;
- paper decisions or BUY/SELL/HOLD;
- positions, trades, audits or PnL;
- wallets, keys, signing, real funds or live execution;
- paid APIs;
- scoring, ranking, confidence, weighting, embeddings or vectors;
- retry, rerun, resume, restart or successor;
- reuse of `…005252Z` or `…224959Z`;
- Source Governor or Central Scheduler bypass;
- `WINDOW_1H`, `4H`, `12H` or `24H` activation;
- a guarantee of provider success, eligible two-token supply or clean memory.

## 20. Functionality Risks / Setbacks / Efficiency Blockers

| Risk | Severity | Mitigation |
| --- | --- | --- |
| Authorization creator blindly copies all directory IDs into the trust list | High | explicit lane input and tracked closeout echo; package preparation must not derive the list from filesystem discovery |
| Growing historical ID/file counts | Medium | optional later rollover into tracked history; exact enumeration remains bounded to the authorization root |
| Builder/validator schema mismatch | High | atomic Manifest V2 merge |
| Incorrect `M ∪ H` use in current-package equality | High | split reconciliation and explicit forbidden pattern |
| Disposition metadata unavailable | Low | `DISPOSITION_NOT_AVAILABLE`; never used as trust or reuse authority |
| Staging cleanup deletes unrelated evidence | High | exact-path, non-recursive, known-entry-only cleanup |
| Operator mistakes unconsumed for reusable | High | explicit superseded disposition and exact HEAD enforcement |
| Preparation parity marketed as full readiness | Medium | separate parity and full-readiness results |

## 21. Key decisions

1. Four-class inventory remains `T + M_mig + M_auth + H`.
2. Manifest V2 keeps historical evidence separate from current `files[]`.
3. `prior_authorizations_non_reusable` in the current final authorization is the canonical approved-ID trust root for future packages.
4. The approved set is explicit lane input and is never generated by scanning package directories.
5. Manifest V2 copies and hashes the approved-ID set and validates exact equality with the current authorization document.
6. Unknown untracked package IDs block even when their directory names look valid.
7. Tracked historical files remain trusted through exact HEAD only.
8. Current-package equality remains `C == M`; untracked allowance is `U = M ∪ H`.
9. Preparation and wrapper share the same production owner and pre-marker validator.
10. Consumption occurs only at successful marker creation.
11. Pre-publication staging cleanup is exact-path and non-recursive.
12. Builder and validator ship atomically.
13. The implementation boundary remains manifest/wrapper/preparation/tests/docs only.

## 22. Exact next step

`V2-9.8B WINDOW_15M Historical Authorization Evidence Contract Implementation`

Implementation must begin from this R2 design commit and:

1. land Manifest V2, approved-ID validation, historical enumeration and split reconciliation;
2. update the wrapper builder and pre-marker staging cleanup in the same atomic unit;
3. add non-consuming preparation parity using the same production components;
4. run the focused disposable proofs above;
5. produce implementation and bounded-proof closeouts;
6. stop before creating a fresh authorization or running the wrapper.

After implementation, proof and operator inspection, a fresh one-use `WINDOW_15M` authorization may be prepared on the repaired HEAD. The superseded authorization `…005252Z` must never be reused.
