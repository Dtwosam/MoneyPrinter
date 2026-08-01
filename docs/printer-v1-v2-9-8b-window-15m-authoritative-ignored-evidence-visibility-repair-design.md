# Printer V1 V2-9.8B WINDOW_15M Authoritative Ignored-Evidence Visibility Repair Design

Date: 2026-08-01

Lane:
`V2-9.8B WINDOW_15M Authoritative Ignored-Evidence Visibility Repair Design`

Lane type: design/specification only.

## 1. Verdict

`V2_9_8B_WINDOW_15M_AUTHORITATIVE_IGNORED_EVIDENCE_VISIBILITY_REPAIR_DESIGN_PASS`

A narrow fail-closed design is approved for reconciling complete repository-local evidence with Git-visible and Git-ignored untracked files.

The design preserves the existing all-file manifest and external marker contract. It does not change `.gitignore`, `.git/info/exclude`, global Git configuration, the canonical six-field Git-provenance payload, the public PowerShell command, Source Governor ownership, Central Scheduler ownership, campaign policy, memory policy, retrieval locks, or paper-trading locks.

No code was implemented, no proof ran, no wrapper was created, no authorization was issued, no provider was contacted, no Scheduler or campaign ran, and the authoritative database was not opened or mutated.

## 2. Controlling baseline

This design is governed by the active Printer V1 source stack:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`

Immediate lane evidence:

- post-repair readiness audit commit: `57a8ba600cfa008209fda1e9ec4efbef7dcfa005`
- audit verdict: `V2_9_8B_WINDOW_15M_POST_REPAIR_AUTHORITATIVE_READINESS_BLOCKED_IGNORED_EVIDENCE_VISIBILITY`
- implementation commit: `9a22d0de9e1a001b9c508a80c0b50d9ceda12b4c`
- disposable proof commit: `ada3376a09abcd6fe291d309889c1fb91d5d73ec`
- independent closeout commit: `eeb7345bb1f0ef0ac87d39ee4c5cbcfcc1307a13`
- accepted authoritative evidence files: 19
- Git-visible untracked evidence files: 17
- Git-ignored accepted evidence files: 2

The two ignored accepted files are:

1. `operator-runs/v2-9-8b-authoritative-mig050/<migration_execution_id>/disposable-restore/printer_v1-rehearsal.sqlite3`
2. `operator-runs/v2-9-8b-authoritative-mig050/<migration_execution_id>/verified-backup/printer_v1-pre050.sqlite3`

The repository ignore rules include `*.sqlite3`, so these files do not appear in `git ls-files --others --exclude-standard -z`.

## 3. Problem statement

The existing validator performs two independently useful checks:

1. it validates every manifest file directly by exact path, package identity, size, SHA-256, regular-file status, and symlink rejection;
2. it requires exact equality between the manifest file set and the Git-visible untracked set.

The second check is too narrow for the authoritative repository because standard Git excludes intentionally hide the two accepted `.sqlite3` backup files.

The repair must preserve complete evidence coverage without turning ignored files into a broad exemption.

The design must reject both unsafe alternatives:

- omitting ignored accepted files from the manifest;
- disabling standard excludes or broadly accepting ignored repository content.

## 4. Approved trust boundary

The approved evidence namespace is exactly:

`operator-runs/`

Within that namespace, the only accepted package identities for one authorization are:

1. `operator-runs/v2-9-8b-authoritative-mig050/<migration_execution_id>/`
2. `operator-runs/v2-9-8b-window-15m-final-authorization/<authorization_id>/`

The manifest continues to list every accepted evidence file under those exact identities.

Ignored files elsewhere in the repository, such as `.venv`, caches, local databases, or other intentionally excluded development artifacts, are not added to the evidence trust boundary and are not globally enumerated as evidence.

Visible untracked files anywhere outside the manifest and fixed SQLite runtime sidecars continue to block through the existing Git-provenance path.

Ignored files anywhere under `operator-runs/` are evidence-relevant and must be completely reconciled.

## 5. Three-set reconciliation model

The repaired validator must independently derive three exact sets.

### 5.1 Manifest set

`M = all normalized manifest file paths`

Every member of `M` must already pass the existing exact path, package identity, size, SHA-256, regular-file, non-symlink, and no-traversal validation.

### 5.2 Git-visible untracked set

`V = git ls-files --others --exclude-standard -z`

After subtracting only the existing fixed authoritative SQLite runtime sidecars:

`V_effective = V - fixed_sidecars`

This preserves current behavior for all non-ignored repository untracked files.

### 5.3 Complete operator-runs filesystem inventory

`F = every filesystem entry beneath operator-runs/ discovered by a bounded, no-follow recursive walk`

The walk must:

- start only at `<repository_root>/operator-runs`;
- never follow symlink directories;
- reject any symlink file or symlink directory encountered;
- reject sockets, devices, FIFOs, or other non-regular entries;
- record regular files only as repository-relative POSIX paths;
- reject path normalization ambiguity;
- include both Git-visible and Git-ignored files;
- include files under package identities other than the two authorized identities so they can block as unexpected evidence;
- perform no hashing outside `operator-runs/`.

Empty directories do not enter `F` and do not authorize any path.

## 6. Required invariants

The repaired validator must require all of the following.

### 6.1 Complete evidence equality

`F == M`

Consequences:

- a manifest-listed ignored file is accepted only when it physically exists in the complete inventory and already passed exact hash/size validation;
- an ignored file omitted from the manifest blocks;
- an extra ignored file inside an authorized package blocks;
- an extra ignored file under `operator-runs/` but outside the two authorized package identities blocks;
- a tracked file under `operator-runs/` blocks because it appears in `F` but cannot satisfy the untracked classification requirement below;
- no directory or glob exemption exists.

### 6.2 Visible-untracked containment

`V_effective - M == empty`

Any visible untracked file outside the manifest still blocks exactly as before.

### 6.3 Untracked classification of every manifest file

Every path in `M` must be proven to be exactly one of:

- Git-visible untracked; or
- Git-ignored untracked under `operator-runs/`.

Define a scoped Git-ignored set:

`I = git ls-files --others --ignored --exclude-standard -z -- operator-runs/`

Require:

- `V_effective` and `I` are disjoint;
- `M == (V_effective intersect M) union I`;
- `I` contains no path outside `M`;
- every path in `I` is also present in `F`;
- every path in `M` absent from `V_effective` must be present in `I`;
- no tracked manifest path is accepted.

Equivalent fail-closed checks may be used, but these set properties must remain true and directly tested.

### 6.4 Bounded ignored scope

The ignored query is scoped only to `operator-runs/`.

The repair must not run a whole-repository ignored-file inventory and must not attempt to manifest `.venv`, caches, local databases outside `operator-runs/`, or unrelated ignored development content.

### 6.5 Existing direct file validation remains mandatory

Set reconciliation does not replace direct file checks.

Every manifest file must still pass:

- exact repository-relative normalized POSIX path;
- exact approved package identity;
- no absolute path, traversal, empty segment, trailing slash, glob, or backslash;
- no symlink file or parent component;
- regular file;
- exact size;
- exact SHA-256;
- unique path;
- package kind and identity match.

## 7. Manifest and marker compatibility

No manifest schema change is required.

`PRINTER_V1_GIT_PROVENANCE_MANIFEST_V1` remains valid because it already binds every evidence file by path, package kind, size, and SHA-256.

No marker schema change is required.

`PRINTER_V1_APPLICATION_MARKER_V1` continues to bind:

- authorization SHA-256;
- manifest SHA-256;
- allowed-file-set SHA-256;
- branch and HEAD;
- command;
- one invocation;
- all retry/rerun/resume/restart/successor flags false.

The existing allowed-file-set digest remains over all manifest files, including ignored files.

The immutable validator result continues to return all manifest paths. Passing ignored paths to the existing capture helper is harmless because the helper sees only Git-visible untracked paths; all visible paths must still be contained in the exact allowlist.

## 8. Production validator sequence

The repaired validation order must be:

1. validate external manifest path and SHA-256;
2. parse exact manifest schema with duplicate-key rejection;
3. read live branch, HEAD, staged state, and unstaged state;
4. validate the referenced final authorization;
5. validate every manifest file directly by exact path, identity, size, and SHA-256;
6. enumerate `V` using the existing standard-exclude Git query;
7. enumerate `I` using the ignored Git query scoped to `operator-runs/`;
8. recursively inventory `F` beneath `operator-runs/` without following symlinks;
9. prove all set invariants in Section 6;
10. compute the unchanged allowed-file-set digest;
11. validate the external marker and all bindings;
12. return the immutable exact allowlist and bounded summary.

No marker may be created by the future wrapper until the complete pre-marker validation using the repaired production validator passes.

## 9. Failure law

Before marker creation, any of the following blocks without consuming authorization:

- missing or malformed `operator-runs/` namespace;
- manifest and filesystem inventory mismatch;
- manifest and visible/ignored Git classification mismatch;
- extra visible untracked file;
- extra ignored file anywhere under `operator-runs/`;
- ignored file under an unauthorized package identity;
- manifest file that is tracked rather than untracked;
- overlap between visible and ignored classifications;
- symlink or non-regular entry under `operator-runs/`;
- Git command error, malformed output, or timeout;
- any existing manifest, authorization, hash, size, branch, HEAD, or marker failure.

After marker creation, the existing one-attempt terminal law remains unchanged: no retry, rerun, resume, restart, successor, automatic repair, evidence deletion, ignore mutation, or package relocation.

## 10. Existing boundaries preserved

The repair must not modify:

- `.gitignore`;
- `.git/info/exclude`;
- global Git configuration;
- `src/printer_v1/operator_cli/git_provenance.py` semantics;
- the canonical six-field Git-provenance payload;
- fixed SQLite runtime-sidecar ownership;
- PowerShell parameters or public command shape;
- Source Governor or Central Scheduler ownership;
- campaign duration, request ceilings, scheduler ceilings, or retry law;
- memory generation, clean/dirty memory rules, retrieval, or financial capability locks.

The four manifest/marker environment variables remain all-or-none and accepted only for `preflight-only` and ordinary `run`.

## 11. Approved implementation scope

The next implementation lane may change only:

- `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py`;
- focused tests for ignored-evidence reconciliation;
- an implementation deliverable document.

`operational_memory_factory_command.py` should remain unchanged unless a focused implementation test proves a direct integration defect. Any such need must be documented before modification and remain limited to the existing preflight boundary.

The implementation may add small private helpers for:

- scoped ignored Git enumeration;
- bounded `operator-runs/` filesystem inventory;
- set reconciliation and deterministic blocker messages.

No wrapper, authorization, provider, Scheduler, campaign, memory, retrieval, decision, position, trade, audit, or PnL code is in scope.

## 12. Minimum sufficient implementation tests

The focused test suite must include at least:

1. positive repository with the real `*.sqlite3` ignore rule, 17 visible files, 2 ignored SQLite files, and a complete 19-file manifest passes;
2. complete manifest digest remains deterministic and includes ignored files;
3. extra ignored `.sqlite3` inside the authorized migration package blocks;
4. extra ignored file under `operator-runs/` outside both authorized package identities blocks;
5. ignored manifest file omitted from the filesystem blocks;
6. filesystem ignored file omitted from the manifest blocks;
7. tracked file under `operator-runs/` blocks;
8. visible extra untracked file outside `operator-runs/` blocks;
9. visible extra file inside `operator-runs/` blocks;
10. symlink file under `operator-runs/` blocks;
11. symlink directory under `operator-runs/` blocks without traversal;
12. non-regular filesystem entry blocks where portable test support exists;
13. manifest path classified by neither visible nor ignored Git sets blocks;
14. any overlap or duplicate classification blocks;
15. unrelated ignored content outside `operator-runs/` does not enter the evidence inventory and does not become authorized;
16. existing exact path, hash, size, schema, authorization, marker, mode, and six-field-payload tests remain green;
17. no network, database, provider, Scheduler, campaign, memory, retrieval, or financial call occurs.

Use temporary repositories and disposable fixtures only.

## 13. Proof required after implementation

A PASS implementation does not establish readiness by itself.

Required later sequence:

1. focused implementation verification;
2. bounded disposable proof reproducing the real `*.sqlite3` ignore semantics;
3. positive proof with all 19 authoritative-shaped evidence files;
4. negative proof for an extra ignored file inside an authorized package;
5. negative proof for an extra ignored file elsewhere under `operator-runs/`;
6. negative proof for a visible extra file outside `operator-runs/`;
7. proof that visible and ignored sets are disjoint and complete;
8. proof that unrelated ignored content outside `operator-runs/` is not authorized;
9. independent repair closeout;
10. repeated post-repair authoritative readiness audit;
11. only after readiness PASS, a separate fresh final authorization lane.

No campaign may run before all steps pass.

## 14. Money-usefulness contribution

This design removes a deterministic pre-lifecycle blocker that would otherwise consume another scarce one-shot authorization before useful `WINDOW_15M` collection begins.

It preserves both complete audit evidence and strict repository safety. That improves the reliability of future paper-only memory collection without creating market signal, memory, retrieval, decisions, positions, trades, or profit claims.

## 15. What this design improves

- preserves all 19 accepted evidence files in the manifest;
- makes ignored SQLite backups visible to the authorization trust boundary without changing ignore rules;
- detects extra ignored evidence inside or outside the two exact package identities under `operator-runs/`;
- retains current blocking behavior for visible untracked files anywhere in the repository;
- avoids whole-repository ignored-file enumeration;
- keeps existing manifest and marker schemas stable;
- keeps the six-field provenance payload unchanged;
- gives implementation and proof lanes exact positive and negative requirements.

## 16. What remains locked

- implementation until the next approved lane;
- external one-shot wrapper construction;
- fresh campaign authorization;
- providers, RPC, WebSockets, and source fetching;
- discovery and Scheduler runtime;
- campaign execution;
- memory generation or promotion;
- retrieval and dirty-memory use;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, and `WINDOW_24H`;
- paper decisions, BUY/SELL/HOLD, positions, trade events, audits, and PnL;
- wallets, private keys, signing, real funds, live execution, and paid APIs;
- scoring, ranking, confidence, weighting, embeddings, and vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only. Solana-only, memecoin-only, and paper-only V1 restrictions remain unchanged.

## 17. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Design control |
| --- | --- |
| Repair becomes a generic ignored-file bypass | Ignored inventory scoped only to `operator-runs/`; complete equality with manifest required |
| Extra ignored file inside authorized package | Complete filesystem inventory makes it an unexpected manifest mismatch |
| Extra ignored file outside authorized package | Entire `operator-runs/` namespace is inventoried, so it blocks |
| `.venv` and unrelated ignored content create noise | Whole-repository ignored scan is prohibited |
| Tracked evidence file is accidentally accepted | Every manifest file must be visible-untracked or ignored-untracked |
| Visible and ignored sets overlap | Disjointness is a required invariant and negative test |
| Symlink traversal escapes the namespace | No-follow walk plus symlink component rejection |
| Filesystem walk races with mutation | Future wrapper must revalidate immediately before marker creation; any mismatch blocks |
| Large backup files make hashing expensive | Existing streamed hashing remains; inventory itself records paths/types without duplicate content reads |
| Existing closeout appeared to PASS before readiness | Preserved as a valid code/proof closeout; authoritative readiness remains independently blocked until this repair sequence passes |
| Scope expands into wrapper or campaign work | Explicitly prohibited in design and implementation lanes |

## 18. Exact next lane

`V2-9.8B WINDOW_15M Authoritative Ignored-Evidence Visibility Repair Implementation`

Type: narrowly scoped implementation and focused static/unit verification.

PASS verdict for the next lane:

`V2_9_8B_WINDOW_15M_AUTHORITATIVE_IGNORED_EVIDENCE_VISIBILITY_REPAIR_IMPLEMENTATION_PASS`

The next lane may implement only the approved validator reconciliation and focused tests. It may not build the wrapper, issue authorization, contact providers, run Scheduler, execute a campaign, generate memory, activate retrieval, or unlock paper trading.
