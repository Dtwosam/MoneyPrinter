# Printer V1 V2-9.8B WINDOW_15M One-Shot Wrapper Git-Provenance Compatibility Design

Date: 2026-08-01

Lane:
`V2-9.8B WINDOW_15M One-Shot Wrapper Git-Provenance Compatibility Design`

Lane type: design/specification only.

## 1. Design verdict

`V2_9_8B_WINDOW_15M_ONE_SHOT_WRAPPER_GIT_PROVENANCE_COMPATIBILITY_DESIGN_PASS`

A narrow, fail-closed compatibility design is approved.

The production Git-provenance helper remains strict and unchanged in meaning.
The repair adds a separately validated, authorization-bound exact-file manifest.
Only after every listed path and hash is independently proven may those exact
repository-relative file paths be passed to the existing
`capture_git_provenance()` allowlist parameter.

This design does not implement the repair, authorize another campaign, contact
providers, mutate the authoritative database, generate memory, or unlock any
retrieval or financial capability.

## 2. Controlling baseline

| Item | Value |
| --- | --- |
| Audit closeout commit | `32c9dc4e087efd922417ead74537d98f9de8585c` |
| Design branch | `agent/v2-9-8b-window-15m-provenance-compatibility-design` |
| Consumed authorization | `V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z` |
| Final-authorization commit | `ffb7e4581833ee4ee77763a2bfcff0c98f8087a1` |
| Accepted post-050 DB SHA-256 | `56ca1218442db1a571ba715794ba91b70c3bfeba242f21855275c026d4c8eed5` |
| Migration ledger | `50 / 050_campaign_scheduler_ownership_scope.sql` |
| Provenance-block audit verdict | `V2_9_8B_WINDOW_15M_PRE_LIFECYCLE_GIT_PROVENANCE_BLOCK_AUDIT_PASS` |
| Root cause | `DETERMINISTIC_WRAPPER_PROVENANCE_SELF_BLOCK` |

The classifier proved:

- 13 untracked files existed before the consumed command started;
- all 13 belonged to approved immutable evidence packages;
- zero unrelated pre-command files existed;
- zero known hashes mismatched;
- the production helper reported untracked state with no allowlist;
- the same helper passed with the exact file allowlist;
- the authoritative DB remained byte-identical;
- zero provider, source, Scheduler, campaign, memory, retrieval, or financial
  work occurred.

## 3. Current code boundary

The production command currently imports and uses:

- `capture_git_provenance()`;
- `GitProvenanceError`.

`_capture_operational_git_provenance()` supplies only the three authoritative
SQLite runtime sidecar paths:

- `data/printer_v1.sqlite3-journal`;
- `data/printer_v1.sqlite3-wal`;
- `data/printer_v1.sqlite3-shm`.

Any other repository-visible untracked file causes
`git_untracked_present=true`, after which the operational command raises:

`launch Git tree contains an arbitrary untracked file`

The helper already supports an exact repository-relative file allowlist and
already rejects malformed allowlist entries, including:

- absolute paths;
- traversal;
- trailing-directory paths;
- glob characters.

The defect is not inside the helper. The defect is that the one-shot wrapper's
required immutable evidence files were never converted into a validated exact
allowlist before the production preflight ran.

## 4. Design goals

The repair must:

1. preserve the strict tracked-tree and untracked-file safety boundary;
2. permit only exact immutable evidence files required by one authorization;
3. bind the file set to the exact authorization, Git HEAD, branch, and command;
4. verify every file exists and matches its expected SHA-256 before launch;
5. prove that no additional untracked path exists;
6. keep the canonical six-field production Git-provenance payload unchanged;
7. avoid ignore-rule changes, directory exemptions, globs, or broad roots;
8. avoid moving or deleting accepted migration evidence;
9. keep the public PowerShell command shape unchanged;
10. preserve one-attempt/no-retry behavior.

## 5. Rejected alternatives

### 5.1 Ignore `operator-runs/`

Rejected.

Adding `operator-runs/` to `.gitignore`, `.git/info/exclude`, or a global Git
exclude file would hide unrelated future files and weaken launch provenance.

### 5.2 Allowlist an entire directory

Rejected.

The production helper intentionally accepts exact file paths only. Directory or
glob exemptions would turn a bounded evidence exception into an open-ended
repository bypass.

### 5.3 Delete or relocate accepted evidence packages

Rejected.

The migration-050 and consumed-authorization packages are part of the accepted
evidence chain. Moving or deleting them would damage audit continuity and would
not solve future one-shot marker creation safely.

### 5.4 Add free-form CLI `--allow-untracked` values

Rejected.

A generic user-provided path list would make the operational command responsible
for trusting arbitrary operator input. The allowlist must come from an immutable,
hash-bound authorization manifest, not free-form command arguments.

### 5.5 Bypass `capture_git_provenance()`

Rejected.

The existing helper remains the canonical Git status owner. The repair validates
an exact manifest first, then invokes the same helper with the resulting exact
paths.

## 6. Approved architecture

### 6.1 External immutable manifest

The one-shot wrapper creates one canonical JSON manifest outside the Git
repository before it creates the one-attempt marker.

Recommended location:

`~/.config/printer-v1/authorizations/<authorization_id>/git-provenance-manifest.json`

The manifest must not live under the repository because it would otherwise need
to allowlist and hash itself, creating a circular trust problem.

The wrapper also exports two environment variables for the single child process:

- `PRINTER_V1_GIT_PROVENANCE_MANIFEST_PATH`;
- `PRINTER_V1_GIT_PROVENANCE_MANIFEST_SHA256`.

The PowerShell launcher needs no new public parameter. It already inherits the
wrapper's child-process environment and continues to invoke only:

`python -m printer_v1.operator_cli.operational_memory_factory_command run --operator-approved`

### 6.2 Manifest schema

Exact top-level schema:

```json
{
  "schema_version": "PRINTER_V1_GIT_PROVENANCE_MANIFEST_V1",
  "authorization_id": "...",
  "authorization_file": {
    "path": "operator-runs/.../final_authorization.json",
    "sha256": "..."
  },
  "repository": {
    "branch": "...",
    "head": "..."
  },
  "authorized_command": {
    "mode": "run",
    "operator_approved": true
  },
  "migration_execution_id": "...",
  "created_at": "timezone-aware ISO-8601",
  "files": [
    {
      "path": "repository-relative exact file path",
      "sha256": "64 lowercase hexadecimal characters",
      "size": 0,
      "package_kind": "MIGRATION_050_EVIDENCE or WINDOW_15M_AUTHORIZATION_EVIDENCE"
    }
  ]
}
```

No additional top-level or file-entry keys are accepted.

### 6.3 Exact path roots

Every manifest file must fall under exactly one of these two bounded forms:

1. Migration package:

`operator-runs/v2-9-8b-authoritative-mig050/<migration_execution_id>/<exact-file>`

2. Current authorization package:

`operator-runs/v2-9-8b-window-15m-final-authorization/<authorization_id>/<exact-file>`

Rules:

- file paths are repository-relative POSIX paths;
- no absolute paths;
- no `..` traversal;
- no empty segments;
- no trailing slash;
- no `*`, `?`, or `[` glob characters;
- no duplicate normalized path;
- no symlink file or symlink parent component;
- no path outside the two exact package identities;
- no runtime artifact directory under `~/PrinterOperations` is included because
  it is outside the repository;
- SQLite sidecars remain separately owned by the existing fixed sidecar tuple.

### 6.4 Authorization validation

Before accepting the manifest, the production validator reads the referenced
`final_authorization.json` and requires:

- SHA-256 equals `authorization_file.sha256`;
- `authorization_id` equals the manifest authorization ID;
- final-authorization verdict is PASS;
- authorized Git branch equals the current branch;
- authorized Git HEAD equals the current HEAD;
- exact authorized mode is `run`;
- operator approval is required;
- allowed invocation count is one;
- automatic retry, manual rerun, resume, restart, and successor are false;
- ordinary `WINDOW_15M` policy remains exact;
- selective-1h continuation is false.

The consumed authorization remains invalid for reuse. A future implementation
proof uses a disposable authorization fixture. Any real campaign requires a new
post-repair authorization ID.

### 6.5 File validation

For every manifest file, the production validator must require:

- file exists and is a regular file;
- path resolves inside the repository root and inside its declared package root;
- no symlink or hard-link ambiguity accepted by the implementation contract;
- exact byte size matches;
- exact SHA-256 matches;
- path is unique;
- package kind matches path root;
- authorization package identity matches authorization ID;
- migration package identity matches migration execution ID.

The validator then obtains the complete observed untracked path set using the
same Git semantics as `capture_git_provenance()`.

It requires:

`observed_untracked_paths == manifest_file_paths`

except for the existing fixed authoritative SQLite sidecar allowlist, which
remains separately managed by the operational command.

This equality is mandatory. A manifest may not list a missing file, and an
observed untracked file may not be absent from the manifest.

### 6.6 Manifest integrity

The production validator requires:

- manifest path is absolute;
- manifest is outside the repository;
- manifest is a regular non-symlink file;
- manifest SHA-256 environment value is lowercase 64-character hexadecimal;
- actual manifest SHA-256 equals the environment value;
- canonical JSON parses without duplicate keys;
- schema and all types are exact;
- `created_at` is timezone-aware;
- branch and HEAD match live Git state;
- no path or hash normalization ambiguity exists.

The production command records only:

- manifest schema version;
- manifest SHA-256;
- authorization ID;
- exact allowed-file count;
- canonical exact-file-set digest;
- canonical six-field Git-provenance payload.

It must not copy secret values or full evidence file contents into campaign
configuration.

## 7. Canonical file-set digest

After validation, sort file records by path and encode canonical JSON using:

- `sort_keys=True`;
- separators `(',', ':')`;
- ASCII-safe encoding;
- no NaN values.

Hash the canonical byte representation with SHA-256.

This produces:

`git_provenance_allowed_file_set_sha256`

The digest is recorded in:

- pre-run evidence;
- one-attempt marker;
- operational preflight result;
- campaign configuration/launch provenance;
- terminal evidence.

The existing six-field `git_provenance` object remains unchanged and remains the
canonical tracked/untracked status object.

## 8. Production integration boundary

### 8.1 New focused module

Preferred new module:

`src/printer_v1/operator_cli/git_provenance_authorization_manifest.py`

Responsibilities:

- load manifest path/hash from explicit function arguments;
- parse canonical schema;
- validate authorization JSON;
- validate exact path roots;
- validate every file hash and size;
- validate exact observed-untracked set equality;
- return an immutable result containing:
  - exact tuple of allowed repository-relative paths;
  - manifest SHA-256;
  - file-set SHA-256;
  - authorization ID;
  - file count.

It must make no network request and no database write.

### 8.2 Existing helper

`src/printer_v1/operator_cli/git_provenance.py` remains semantically unchanged.

No directory or glob support is added. Existing malformed-path checks stay in
place.

### 8.3 Operational command

`operational_memory_factory_command.py` changes only at the preflight ownership
boundary:

1. read manifest path/hash from the child environment;
2. require both variables together or neither;
3. for ordinary `run`, require a valid manifest when repository untracked files
   exceed fixed SQLite sidecars;
4. call the new manifest validator;
5. combine its exact path tuple with the fixed SQLite sidecar tuple;
6. call existing `capture_git_provenance()`;
7. reject if `git_untracked_present` remains true;
8. include the bounded manifest summary in preflight evidence.

No source, Scheduler, campaign, memory, retrieval, or financial ownership moves.

### 8.4 Mode restrictions

The manifest integration is approved only for:

- `preflight-only`, for zero-source disposable validation;
- ordinary `run`, for a future separately authorized campaign.

It is not accepted for:

- `selective-1h-preflight`;
- `selective-1h-proof`;
- `discovery-only`;
- `status`;
- `cooperative-stop`;
- `recover-orphan`;
- `report-only`.

Those modes either continue with current provenance behavior or fail closed if
the manifest environment variables are supplied.

## 9. One-shot wrapper contract

The repaired wrapper performs this order:

1. fresh branch, HEAD, tracked-tree, DB, schema, residue, source-contract, and
   capability-lock gates;
2. enumerate all current untracked evidence files;
3. prove every existing file belongs to an approved immutable package and hash it;
4. write future authorization-specific `pre_run_evidence.json`;
5. create the new immutable `application_started.json` marker exactly once;
6. hash both new files;
7. build the exact manifest including all pre-existing evidence plus the two new
   files;
8. write the manifest outside the repository;
9. hash the manifest;
10. re-read and re-hash every manifest-listed file;
11. require the observed untracked set equals the manifest set;
12. launch the exact ordinary PowerShell command once with the two manifest
    environment variables;
13. capture terminal evidence;
14. never retry.

The wrapper must not run the production command until step 11 passes.

## 10. Failure law

Before the one-attempt marker exists:

- any validation failure blocks without consuming authorization.

After the one-attempt marker exists:

- any validation or launch failure consumes authorization;
- no retry, rerun, resume, restart, or successor is allowed;
- no automatic manifest repair is allowed;
- no file deletion, ignore-rule mutation, or package relocation is allowed;
- terminal evidence must record the first failure exactly.

A future authorization should require the wrapper to generate the manifest and
revalidate it before the marker whenever technically possible. The marker must
remain the final irreversible pre-launch boundary.

## 11. Implementation scope

Allowed implementation files:

- `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py`;
- `src/printer_v1/operator_cli/operational_memory_factory_command.py`;
- focused tests for the new manifest module and operational preflight boundary;
- the authorization-specific external wrapper artifact produced after code
  closeout.

Possible test-only fixture files are allowed under the focused test directory.

Not approved without a new design decision:

- `.gitignore`;
- `.git/info/exclude`;
- global Git config;
- migration files;
- database schema;
- Source Governor;
- Central Scheduler;
- discovery, holder, snapshot, memory, retrieval, or paper-trading code;
- PowerShell public command parameters;
- broad launcher or campaign architecture changes.

## 12. Minimum sufficient proof

### 12.1 Unit and focused integration tests

1. valid external manifest with exact approved files passes;
2. no manifest reproduces `git_untracked_present=true` when evidence exists;
3. one unrelated untracked file blocks;
4. one missing manifest file blocks;
5. one hash-mismatched file blocks;
6. one size mismatch blocks;
7. duplicate normalized path blocks;
8. wrong package kind blocks;
9. wrong authorization ID blocks;
10. wrong branch or HEAD blocks;
11. non-PASS authorization blocks;
12. wrong command or selective-1h authorization blocks;
13. directory, glob, absolute, traversal, symlink, or out-of-root path blocks;
14. manifest inside repository blocks;
15. manifest hash mismatch blocks;
16. malformed/extra schema keys block;
17. staged changes block;
18. unstaged changes block;
19. an extra observed file absent from manifest blocks;
20. a manifest-listed file absent from the observed set blocks;
21. fixed SQLite sidecars remain separately allowed only by exact names;
22. all unsupported public modes reject the manifest environment.

### 12.2 Disposable proof

Run one bounded disposable proof with:

- a temporary Git repository;
- copied evidence-package fixtures;
- a disposable DB or no DB where the tested function permits;
- no provider keys required;
- no network access;
- no authoritative DB mutation;
- no Source Governor or Scheduler runtime;
- no campaign creation;
- no memory, retrieval, decision, position, trade, audit, or PnL work.

Required observations:

- no-allowlist path reports untracked;
- exact valid manifest reports no unexpected untracked file;
- unrelated file negative case blocks;
- hash mismatch negative case blocks;
- tracked staged/unstaged negative cases block;
- manifest and file-set digests are deterministic across repeated read-only
  evaluations.

### 12.3 Risk-based test boundary

Run focused tests for:

- new manifest parser/validator;
- existing Git-provenance helper interaction;
- ordinary activation preflight boundary;
- mode rejection.

Do not run a broad regression suite during implementation unless the change
expands beyond this approved boundary or focused results reveal cross-cutting
risk. Reserve the broader relevant suite for repair closeout and the later
pre-authorization checkpoint.

Document unrelated pre-existing failures without expanding scope.

## 13. Implementation verdicts

The implementation lane must end with one of:

- `V2_9_8B_WINDOW_15M_GIT_PROVENANCE_COMPATIBILITY_IMPLEMENTATION_PASS`;
- `V2_9_8B_WINDOW_15M_GIT_PROVENANCE_COMPATIBILITY_IMPLEMENTATION_BLOCKED`.

PASS requires code, focused tests, and static verification only. It still does
not authorize a campaign or fresh authorization.

## 14. Repair proof and closeout sequence

The mandatory sequence remains:

1. this design;
2. implementation;
3. bounded disposable proof;
4. independent repair closeout;
5. repeated authoritative readiness audit;
6. new final authorization;
7. one future campaign attempt.

No step may be skipped.

## 15. Money-usefulness contribution

This design prevents another one-shot authorization from being consumed before
useful collection begins while preserving the stronger Git launch boundary.

It improves the chance that a future authorized paper-only campaign reaches its
real bounded source and memory path without hiding unrelated repository state.

It creates no market signal, memory, decision, position, trade, or profit claim.

## 16. What this lane improves

- defines the exact trust boundary between wrapper evidence and production Git
  provenance;
- keeps the existing strict helper as canonical owner;
- prevents broad ignore or directory bypasses;
- binds every exception to authorization identity, branch, HEAD, path, size, and
  SHA-256;
- provides deterministic positive and negative proof requirements;
- preserves accepted migration and authorization evidence packages;
- preserves the public ordinary command shape;
- separates repair design from implementation and campaign authorization.

## 17. What this lane still does not unlock

This design does not unlock:

- implementation by itself;
- a fresh authorization;
- another wrapper or campaign invocation;
- providers, RPC, WebSockets, source fetching, discovery, or Scheduler runtime;
- memory generation or promotion;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, or `WINDOW_24H`;
- retrieval or dirty-memory use;
- paper decisions or BUY/SELL/HOLD;
- positions, trade events, audits, or PnL;
- wallets, private keys, signing, real funds, or live execution;
- paid APIs;
- scoring, ranking, confidence, weighting, embeddings, or vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only.

## 18. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Design disposition | Required control |
| --- | --- | --- |
| Manifest could become a generic bypass | Rejected | Exact schema, authorization binding, exact roots and hashes |
| Manifest inside repo creates circular trust | Rejected | Store manifest outside repository |
| Operator changes manifest and env together | Fail closed through authorization, branch, HEAD, file-set and command validation | Future authorization binds implementation and wrapper hashes |
| Missing manifest-listed file could otherwise pass helper | Explicitly handled | Require observed set equals manifest set |
| Extra unrelated untracked file | Must block | Exact observed-set equality plus existing helper |
| Symlink or path normalization ambiguity | Must block | Resolve and reject symlink/traversal/duplicates |
| Broad `operator-runs/` exemption | Rejected | Exact files only |
| Migration evidence package is large | Accepted | Stream SHA-256; no file-content copying |
| Rehashing large backup adds launch cost | Accepted bounded cost | Hash once during wrapper manifest build and once in production validation |
| Wrapper may create marker before final validation | Design ordering corrected | Manifest and observed-set validation before irreversible marker where possible |
| Existing helper payload omits filenames | Preserved | Separate manifest summary and file-set digest |
| Selective-1h or discovery could inherit exception | Rejected | Ordinary preflight/run only |
| Fresh authorization could be issued too early | Blocked | Implementation, proof, closeout and readiness must complete first |

## 19. Exact next permitted lane

`V2-9.8B WINDOW_15M One-Shot Wrapper Git-Provenance Compatibility Implementation`

Type: narrowly scoped implementation and focused static/unit verification.

It may implement only this approved manifest integration and focused tests. It
may not run providers, source fetching, discovery, Scheduler runtime, a campaign,
memory generation, retrieval, paper decisions, positions, trades, audits, or
PnL. It may not issue a fresh campaign authorization.