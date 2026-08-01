# Printer V1 V2-9.8B WINDOW_15M Current-vs-Historical operator-runs Trust Boundary Repair Design

Date: 2026-08-01

Lane:
`V2-9.8B WINDOW_15M Current-vs-Historical operator-runs Trust Boundary Repair Design`

Lane type: design/specification only.

## 1. Verdict

`V2_9_8B_WINDOW_15M_CURRENT_VS_HISTORICAL_OPERATOR_RUNS_TRUST_BOUNDARY_REPAIR_DESIGN_PASS`

A final narrow trust-boundary correction is approved for distinguishing committed historical `operator-runs/` artifacts from current manifest-bound untracked evidence.

The approved model preserves the complete `operator-runs/` filesystem inventory, but replaces the incorrect invariant that every file beneath `operator-runs/` must belong to the current authorization manifest.

The correct model is:

- committed historical files are bound by the exact authorized Git HEAD;
- current visible or ignored untracked evidence is bound by the external manifest;
- every regular file beneath `operator-runs/` must belong to exactly one of those two sets;
- every current manifest file must remain untracked and must live beneath one of the two exact current package identities;
- every unexplained visible, ignored, tracked-in-current-package, symlink, or non-regular entry blocks.

No code was implemented, no test or proof ran, no file was deleted or moved, no ignore rule changed, no wrapper or marker was built, no authorization was issued, no provider or source was contacted, no Source Governor or Central Scheduler runtime ran, no campaign executed, and the authoritative database was not opened or mutated.

## 2. Controlling source stack

This design follows the active Printer V1 source stack:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`

The active memory-growth build order remains part of the source stack and is not the sole source of truth.

The required V2 progression remains:

`audit/readiness -> design/specification -> implementation -> bounded proof/test -> closeout report`

## 3. Exact starting baseline

| Item | Value |
| --- | --- |
| Design branch | `agent/v2-9-8b-window-15m-current-vs-historical-operator-runs-trust-boundary-design` |
| Starting HEAD | `ecc957c7908c476a3242847b2bbaf1ba9c0890ad` |
| Blocking audit verdict | `V2_9_8B_WINDOW_15M_REPEATED_POST_REPAIR_AUTHORITATIVE_READINESS_AUDIT_BLOCKED` |
| Blocking audit commit | `ecc957c7908c476a3242847b2bbaf1ba9c0890ad` |
| Repair implementation commit | `32ec6467d08165637015d5775d5ba6e2180a74af` |
| Repair bounded-proof commit | `21ea24d5e2ae53b7d689c2acd97a94688f58d9c0` |
| Repair independent-closeout commit | `83b8333cbd49994a3cc9dcbb3755a229825d60d5` |

Authoritative repository shape at the blocking audit:

- current manifest-shaped evidence: 19 files;
- current visible untracked evidence: 17 files;
- current ignored untracked evidence: 2 files;
- committed historical `operator-runs/` files: 11 files;
- complete `operator-runs/` filesystem inventory: 30 files;
- intended 19 files: unchanged by path, size, SHA-256, and `mtime_ns`;
- authoritative database: unchanged and unopened through SQLite.

## 4. Root cause

The current repaired validator derives:

- `M`: current manifest file paths;
- `V`: Git-visible untracked paths;
- `I`: Git-ignored untracked paths beneath `operator-runs/`;
- `F`: every regular filesystem file beneath `operator-runs/`.

It currently requires:

`F == M`

That rule correctly detects extra current evidence in a disposable repository containing only the manifest package. It is incorrect in the authoritative repository because `operator-runs/` also stores committed historical proof artifacts.

The 11 additional files are not unexplained current residue. They are committed repository content already bound to the exact Git HEAD. Requiring them in the current external manifest would inflate the new authorization scope and misclassify history as current evidence.

The current validator therefore conflates two independent trust mechanisms:

1. Git-tracked repository history, bound by branch, exact HEAD, and clean tracked-tree checks;
2. current untracked authorization evidence, bound by exact manifest path, package identity, size, and SHA-256.

The repair must separate those mechanisms and reconcile them without weakening either.

## 5. Approved trust model

The authoritative repository may contain two legitimate file classes beneath `operator-runs/`.

### 5.1 Historical tracked class

Historical tracked files are repository artifacts already present in the Git index at the exact authorized HEAD.

They are not current authorization evidence and must not be inserted into the current manifest.

Their trust binding is:

- exact repository branch;
- exact repository HEAD;
- clean staged state;
- clean unstaged state;
- exact Git tracked-path classification.

A historical tracked file is allowed only when Git proves it is tracked at the authorized HEAD and it is outside the two exact current package roots.

### 5.2 Current manifest-bound class

Current evidence files are untracked files listed in the external manifest.

Their trust binding remains:

- exact current package identity;
- normalized repository-relative POSIX path;
- exact size;
- exact SHA-256;
- regular file;
- no symlink file or parent component;
- exact visible-untracked or ignored-untracked classification;
- exact external manifest and marker bindings.

A current manifest file must never be accepted merely because it is tracked.

### 5.3 Unexpected class

Any `operator-runs/` file that is neither:

- tracked at the exact authorized HEAD; nor
- listed in the current manifest and proven current-untracked

is unexpected and blocks.

No directory, glob, naming convention, age, or lane prefix may substitute for exact classification.

## 6. Five-set reconciliation model

The implementation must independently derive five exact sets.

### 6.1 Current manifest set

`M = all normalized current manifest file paths`

Every member of `M` must pass the existing direct validation and must live under exactly one of the two current package roots derived from the manifest identities.

### 6.2 Git-visible untracked set

`V = git ls-files --others --exclude-standard -z`

After subtracting only the existing fixed authoritative SQLite runtime sidecars:

`V_effective = V - fixed_sidecars`

This remains a whole-repository query so visible untracked drift outside `operator-runs/` still blocks.

### 6.3 Scoped Git-ignored untracked set

`I = git ls-files --others --ignored --exclude-standard -z -- operator-runs/`

This remains scoped to `operator-runs/` so unrelated ignored development content elsewhere does not enter the authorization boundary.

### 6.4 Scoped Git-tracked historical set

`T = git ls-files --cached -z -- operator-runs/`

`T` is the exact tracked `operator-runs/` baseline at the authorized HEAD.

The query must:

- be scoped only to `operator-runs/`;
- use NUL-delimited output;
- reject malformed, duplicate, absolute, traversal, backslash, or outside-scope paths;
- fail closed on Git error or timeout.

`T` is not copied into the external manifest and is not returned as an untracked allowlist.

### 6.5 Complete filesystem inventory

`F = every regular filesystem file beneath operator-runs/`

The existing no-follow recursive inventory remains required.

It must continue to:

- reject a symlinked `operator-runs/` root;
- reject symlink files and directories anywhere beneath it;
- reject sockets, devices, FIFOs, or other non-regular entries;
- normalize every repository-relative path;
- include tracked, visible-untracked, and ignored-untracked files;
- avoid hashing unrelated content outside `operator-runs/`.

## 7. Exact current package roots

The validator must derive two exact current package roots from the already validated manifest identities:

1. `operator-runs/v2-9-8b-authoritative-mig050/<migration_execution_id>/`
2. `operator-runs/v2-9-8b-window-15m-final-authorization/<authorization_id>/`

Define:

`C = every filesystem file in F beneath either exact current package root`

The current package invariant is:

`C == M`

Consequences:

- a tracked historical file inside a current package root blocks;
- an extra visible file inside a current package root blocks;
- an extra ignored file inside a current package root blocks;
- a manifest omission inside a current package root blocks;
- an empty or neighboring execution directory does not become authorized;
- historical files outside the exact current package roots remain separately classified by `T`.

## 8. Required invariants

The repaired validator must require all of the following.

### 8.1 Current manifest remains exactly untracked

Every path in `M` must be classified as exactly one of:

- visible untracked in `V_effective`; or
- ignored untracked in `I`.

Require:

- `M subset_of (V_effective union I)`;
- `M intersect T == empty`;
- `V_effective intersect I == empty`;
- `T intersect V_effective == empty`;
- `T intersect I == empty`.

Any manifest path classified as tracked, both visible and ignored, or neither visible nor ignored blocks.

### 8.2 No unmanifested visible untracked file

`V_effective - M == empty`

This preserves current whole-repository protection against visible untracked drift.

### 8.3 No unmanifested ignored operator-runs file

`I - M == empty`

An ignored untracked file anywhere beneath `operator-runs/` must belong to the current manifest or block.

This prevents historical-looking ignored residue from hiding outside the current roots.

### 8.4 Current roots equal current manifest

`C == M`

The two exact current package identities contain only the current manifest files and no tracked, visible-extra, ignored-extra, symlink, or non-regular entry.

### 8.5 Complete namespace classification

`F == T union M`

Because `T` and `M` must be disjoint, every regular file beneath `operator-runs/` is exactly one of:

- tracked historical baseline; or
- current manifest-bound untracked evidence.

Any unexplained filesystem file blocks.

### 8.6 Tracked historical files stay outside current roots

`T intersect C == empty`

Equivalent exact-root checks are acceptable, but a tracked path beneath either current package root must block.

### 8.7 Tracked baseline completeness

Every path in `T` must exist as a regular, non-symlink member of `F`.

A missing, replaced, symlinked, or non-regular tracked historical path blocks through tracked-tree checks and filesystem reconciliation.

### 8.8 Existing direct validation remains mandatory

Set reconciliation does not replace current file validation.

Every member of `M` must still pass:

- exact approved package kind;
- exact authorization or migration identity;
- normalized repository-relative POSIX path;
- no absolute path, traversal, empty segment, trailing slash, glob, or backslash;
- no symlink file or parent component;
- regular file;
- exact size;
- exact SHA-256;
- unique path.

## 9. Why tracked history does not need the current manifest

The manifest exists to bind files that Git does not bind as tracked repository content.

Historical tracked files are already committed into the repository tree. The exact HEAD cryptographically binds their paths and blob identities. The validator already requires that:

- the live HEAD equals the manifest HEAD;
- the final authorization HEAD equals the live HEAD;
- the marker HEAD equals the live HEAD;
- there are no staged changes;
- there are no unstaged changes.

Therefore `T` is not an exemption based on filenames or directories. It is an exact Git-index classification bound to the authorized commit.

A new or modified historical file cannot silently enter `T` without a new commit and a new authorized HEAD.

## 10. Production validation sequence

The implementation must preserve the current ordering and extend it as follows:

1. validate external manifest path and SHA-256;
2. parse the exact manifest schema with duplicate-key rejection;
3. read live branch, HEAD, staged state, and unstaged state;
4. validate the referenced final authorization against live branch and HEAD;
5. derive the two exact current package roots;
6. directly validate every manifest file by path, package identity, size, and SHA-256;
7. enumerate `V` using the existing whole-repository visible-untracked query;
8. enumerate `I` using the existing ignored-untracked query scoped to `operator-runs/`;
9. enumerate `T` using the new tracked query scoped to `operator-runs/`;
10. inventory `F` beneath `operator-runs/` without following symlinks;
11. derive `C` from `F` using only the two exact current package roots;
12. prove every invariant in Section 8;
13. compute the unchanged allowed-file-set digest over `M` only;
14. validate the external marker and all existing bindings;
15. return the unchanged immutable current untracked allowlist and bounded summary.

No marker may be created until the complete pre-marker validation passes.

## 11. Compatibility requirements

The repair must not change:

- `PRINTER_V1_GIT_PROVENANCE_MANIFEST_V1`;
- `PRINTER_V1_APPLICATION_MARKER_V1`;
- the allowed-file-set digest algorithm;
- the immutable `ValidatedGitProvenanceAuthorization` public fields;
- the canonical six-field Git-provenance payload;
- `capture_git_provenance()` semantics;
- public PowerShell parameters or command shape;
- the ordinary `WINDOW_15M` command mode;
- the one-attempt/no-retry law;
- Source Governor ownership;
- Central Scheduler ownership;
- campaign ceilings, duration, recovery, or terminal law;
- database schema or migrations;
- memory, retrieval, decision, position, trade, audit, or PnL locks.

The returned allowlist must continue to contain only `M`, never `T`.

The bounded summary must remain filename-free.

## 12. Failure law

Before marker creation, any of the following blocks:

- Git tracked query error, timeout, malformed output, duplicate path, or outside-scope path;
- a manifest path that is tracked;
- a tracked path inside either exact current package root;
- an untracked visible file outside `M`, except existing fixed sidecars;
- an ignored untracked `operator-runs/` file outside `M`;
- a filesystem path beneath `operator-runs/` that belongs to neither `T` nor `M`;
- a path classified into more than one of `T`, `V_effective`, or `I`;
- a current package inventory mismatch;
- a tracked historical path missing from the filesystem inventory;
- a symlink or non-regular entry anywhere beneath `operator-runs/`;
- any existing schema, branch, HEAD, authorization, marker, path, size, SHA-256, staged, unstaged, or timeout failure.

After marker creation, the existing one-attempt terminal law remains unchanged. No retry, rerun, resume, restart, successor, automatic repair, evidence deletion, relocation, or ignore mutation is allowed.

## 13. Rejected alternatives

The implementation must not:

- delete or relocate the 11 historical files;
- delete or relocate the 19 current files;
- insert tracked historical files into the current manifest;
- hardcode the current count of 11 historical files as an allowlist;
- trust lane names or directory prefixes instead of Git classification;
- broadly exempt all files outside the two current package roots;
- inventory only current roots and ignore the rest of `operator-runs/`;
- change `.gitignore`, `.git/info/exclude`, or global Git configuration;
- disable standard excludes repository-wide;
- accept directories or globs;
- return tracked historical files to `capture_git_provenance()` as allowed untracked paths;
- bypass the production validator;
- issue a fresh authorization before the complete repair sequence passes.

## 14. Approved implementation scope

The next implementation lane may change only:

1. `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py`;
2. focused trust-boundary tests, preferably by extending:
   `tests/test_v2_9_8b_window_15m_ignored_evidence_visibility.py`;
3. one implementation closeout document.

Small private helpers may be added for:

- scoped tracked-path enumeration;
- exact current-root membership;
- five-set reconciliation;
- deterministic bounded blocker messages.

`git_provenance.py`, `operational_memory_factory_command.py`, public command surfaces, schemas, wrappers, authorizations, ignore rules, database code, Scheduler, source adapters, memory, retrieval, and paper-trading code are out of scope unless a direct focused test proves an unavoidable integration defect. Any such defect must stop the lane for a separate design review rather than silently expanding scope.

## 15. Minimum sufficient implementation tests

The focused suite must include at least:

1. positive authoritative-shaped repository with 11 tracked historical files, 17 visible current files, 2 ignored current SQLite files, and a complete 19-file manifest passes;
2. complete namespace inventory has 30 files and reconciles as `11 tracked + 19 manifest`;
3. historical tracked files are not returned in the current allowed-untracked paths;
4. current manifest digest remains deterministic and excludes historical tracked files;
5. a tracked historical file outside current roots is accepted only when tracked at the exact HEAD;
6. a visible untracked historical-looking file outside current roots blocks;
7. an ignored untracked historical-looking file outside current roots blocks;
8. a tracked file inside a current package root blocks;
9. a current manifest path changed from untracked to tracked blocks;
10. an extra visible file inside a current root blocks;
11. an extra ignored file inside a current root blocks;
12. a manifest file missing from a current root blocks;
13. a tracked historical file deleted or modified blocks through clean-tree or reconciliation checks;
14. a symlink file or symlink directory anywhere beneath `operator-runs/` blocks;
15. a non-regular entry anywhere beneath `operator-runs/` blocks where portable support exists;
16. malformed, duplicate, or outside-scope tracked Git output blocks;
17. overlap among tracked, visible, and ignored classifications blocks;
18. a visible extra file elsewhere in the repository blocks;
19. unrelated ignored content outside `operator-runs/` remains outside the trust boundary and is not authorized;
20. existing authorization, marker, branch, HEAD, schema, path, hash, size, mode, and six-field provenance tests remain green;
21. no network, authoritative database, provider, Source Governor, Scheduler, campaign, memory, retrieval, decision, position, trade, audit, or PnL call occurs.

Use disposable repositories and temporary fixtures only.

## 16. Bounded proof required after implementation

The later bounded proof must use the exact authoritative shape, not a simplified 19-file-only repository.

It must prove:

- 30 total regular files beneath `operator-runs/`;
- 11 exact Git-tracked historical files outside current roots;
- 17 visible current untracked files;
- 2 ignored current untracked SQLite files;
- 19 current manifest files;
- `F == T union M`;
- `C == M`;
- no overlap among tracked, visible, and ignored classifications;
- current allowed-untracked result contains exactly 19 files and no historical tracked path;
- negative cases for extra visible, extra ignored, tracked-in-current-root, and tracked-tree mutation;
- zero network, authoritative SQLite, provider, Source Governor, Scheduler, campaign, memory, retrieval, decision, position, trade, audit, and PnL activity;
- all authoritative evidence and database state unchanged.

After proof PASS, the roadmap still requires:

1. independent repair closeout;
2. one repeated authoritative readiness audit against the real 30-file repository;
3. only after readiness PASS, a separate fresh final authorization lane.

No campaign may run before those steps pass.

## 17. Money-usefulness contribution

This design removes the remaining deterministic pre-marker blocker without deleting history or widening the current manifest.

It preserves both:

- historical audit evidence already committed at the authorized HEAD;
- current exact evidence needed for the next bounded paper-only `WINDOW_15M` operation.

That reduces the risk of wasting another one-shot authorization on repository bookkeeping while preserving strict evidence integrity. It creates no market signal, memory, retrieval result, decision, position, trade, or profit claim.

## 18. What this design improves

- models the real repository shape instead of a simplified disposable shape;
- separates committed historical evidence from current untracked evidence;
- keeps the complete `operator-runs/` inventory under fail-closed reconciliation;
- preserves detection of every unexplained visible or ignored untracked file;
- blocks tracked files from entering current package roots;
- keeps the current manifest limited to the exact 19 current files;
- uses the authorized Git HEAD as the historical baseline rather than a hardcoded file list;
- preserves schemas, command surfaces, Source Governor, Central Scheduler, and all V1 locks;
- defines one complete implementation/proof acceptance shape to prevent further one-condition-at-a-time repairs.

## 19. What remains locked

This design does not unlock:

- implementation before the next approved lane;
- wrapper construction;
- application marker creation;
- fresh final authorization;
- providers, RPC, WebSockets, or source fetching;
- Source Governor or Central Scheduler runtime;
- a `WINDOW_15M` campaign;
- memory generation or promotion;
- retrieval;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, or `WINDOW_24H`;
- paper decisions, BUY/SELL/HOLD, positions, trade events, audits, or PnL;
- wallets, private keys, signing, real funds, live execution, or paid APIs;
- scoring, ranking, confidence, weighting, embeddings, or vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only. Printer V1 remains Solana-only, Solana memecoin-only, and paper-only.

## 20. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Design control |
| --- | --- |
| Tracked history becomes a broad exemption | Only exact Git-tracked paths at the authorized HEAD enter `T` |
| New tracked artifact silently expands history | Requires a new commit and therefore a new exact authorized HEAD |
| Historical path becomes current evidence | `M intersect T == empty`; current files must be visible or ignored untracked |
| Tracked file appears inside current package | `C == M` and tracked/current-root disjointness block it |
| Extra visible evidence anywhere | Whole-repository `V_effective - M == empty` |
| Extra ignored evidence under `operator-runs/` | `I - M == empty` |
| Unexplained filesystem file | `F == T union M` |
| Simplified proof misses real repository history | Mandatory 30-file, 11-tracked plus 19-current proof shape |
| Hardcoded 11-file list becomes stale | Prohibited; `T` is derived from the exact Git index at HEAD |
| Symlink or special-file escape | Complete no-follow inventory still rejects all such entries |
| Historical deletion or mutation | Clean tracked-tree checks plus `T`/`F` reconciliation |
| Schema or command drift | Explicitly unchanged and covered by existing focused tests |
| Another narrow follow-on blocker | Full five-set actual-shape proof required before closeout |
| Scope drifts into authorization or campaign | Explicitly prohibited until readiness PASS |

## 21. Exact next lane

`V2-9.8B WINDOW_15M Current-vs-Historical operator-runs Trust Boundary Repair Implementation`

Type: narrow implementation and focused disposable verification only.

Expected PASS verdict:

`V2_9_8B_WINDOW_15M_CURRENT_VS_HISTORICAL_OPERATOR_RUNS_TRUST_BOUNDARY_REPAIR_IMPLEMENTATION_PASS`

The next lane may implement only the approved five-set reconciliation and focused tests. It may not delete or move evidence, modify ignore rules, build the wrapper, create a marker, issue authorization, contact providers, run Source Governor or Central Scheduler, execute a campaign, mutate the authoritative database, generate memory, activate retrieval, or unlock paper trading.
