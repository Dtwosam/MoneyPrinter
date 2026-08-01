# Printer V1 V2-9.8B WINDOW_15M One-Shot Wrapper Git-Provenance Compatibility Design

Date: 2026-08-01

Lane:
`V2-9.8B WINDOW_15M One-Shot Wrapper Git-Provenance Compatibility Design`

Lane type: design/specification only.

## 1. Design verdict

`V2_9_8B_WINDOW_15M_ONE_SHOT_WRAPPER_GIT_PROVENANCE_COMPATIBILITY_DESIGN_PASS`

A narrow, fail-closed compatibility design is approved.

The production Git-provenance helper remains strict and unchanged in meaning.
The repair introduces:

1. an authorization-bound exact-file manifest outside the repository; and
2. an irreversible one-attempt marker outside the repository, created only after
   the manifest and observed repository state have passed validation.

Only exact repository-relative evidence files whose paths, sizes, hashes,
authorization identity, branch, HEAD, and command have been proven may be passed
to the existing `capture_git_provenance()` allowlist.

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
already rejects malformed entries, including:

- absolute paths;
- traversal;
- trailing-directory paths;
- glob characters.

The defect is not inside the helper. The defect is that the wrapper-created and
accepted repository-local evidence files were never converted into a validated
exact allowlist before the production preflight ran.

## 4. Design goals

The repair must:

1. preserve strict tracked-tree and untracked-file safety;
2. permit only exact immutable evidence files required by one authorization;
3. bind the file set to exact authorization, branch, HEAD, and command;
4. verify every file exists and matches expected size and SHA-256;
5. prove no additional untracked path exists;
6. validate the complete manifest before consuming authorization;
7. create the irreversible marker only after that validation passes;
8. keep the canonical six-field production Git-provenance payload unchanged;
9. avoid ignore-rule changes, directory exemptions, globs, or broad roots;
10. avoid moving or deleting accepted migration evidence;
11. keep the public PowerShell command shape unchanged;
12. preserve one-attempt/no-retry behavior.

## 5. Rejected alternatives

### 5.1 Ignore `operator-runs/`

Rejected.

Adding `operator-runs/` to `.gitignore`, `.git/info/exclude`, or global Git
configuration would hide unrelated future files and weaken launch provenance.

### 5.2 Allowlist an entire directory

Rejected.

Directory or glob exemptions would turn a bounded evidence exception into an
open-ended repository bypass.

### 5.3 Delete or relocate accepted repository evidence

Rejected.

The migration-050 and consumed-authorization packages are part of the accepted
evidence chain. They remain intact.

### 5.4 Add free-form CLI `--allow-untracked` values

Rejected.

The allowlist must come from a validated authorization manifest, not arbitrary
operator arguments.

### 5.5 Bypass or weaken `capture_git_provenance()`

Rejected.

The existing helper remains the canonical Git status owner.

### 5.6 Keep the irreversible marker inside the repository

Rejected for future repaired wrappers.

Creating the marker inside the repository before constructing the manifest
creates a circular ordering problem and can consume authorization on a
manifest-construction defect. The future marker therefore lives outside the
repository and is separately hash-bound.

## 6. Approved architecture

### 6.1 External authorization control directory

The future wrapper uses:

`~/.config/printer-v1/authorizations/<authorization_id>/`

This directory is outside the Git repository and contains exactly:

- `git-provenance-manifest.json`;
- `application_started.json`.

The accepted repository-local evidence packages remain unchanged.

The wrapper passes four environment variables only to the single authorized
child process:

- `PRINTER_V1_GIT_PROVENANCE_MANIFEST_PATH`;
- `PRINTER_V1_GIT_PROVENANCE_MANIFEST_SHA256`;
- `PRINTER_V1_APPLICATION_MARKER_PATH`;
- `PRINTER_V1_APPLICATION_MARKER_SHA256`.

The public PowerShell launcher gains no new parameter and continues to invoke:

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

### 6.3 Application marker schema

The marker is created with exclusive file creation only after the manifest has
passed complete validation.

Exact schema:

```json
{
  "schema_version": "PRINTER_V1_APPLICATION_MARKER_V1",
  "authorization_id": "...",
  "authorization_consumed_at": "timezone-aware ISO-8601",
  "authorization_sha256": "...",
  "manifest_sha256": "...",
  "allowed_file_set_sha256": "...",
  "repository_branch": "...",
  "repository_head": "...",
  "command": {
    "mode": "run",
    "operator_approved": true
  },
  "allowed_invocation_count": 1,
  "automatic_retry_allowed": false,
  "manual_rerun_allowed": false,
  "resume_allowed": false,
  "restart_allowed": false,
  "successor_allowed": false
}
```

No additional keys are accepted.

The marker path must be outside the repository and inside the exact external
authorization control directory.

### 6.4 Exact repository path roots

Every manifest-listed repository file must fall under exactly one of:

1. Migration package:

`operator-runs/v2-9-8b-authoritative-mig050/<migration_execution_id>/<exact-file>`

2. Current authorization package:

`operator-runs/v2-9-8b-window-15m-final-authorization/<authorization_id>/<exact-file>`

Rules:

- repository-relative POSIX paths only;
- no absolute path;
- no `..` traversal;
- no empty segment;
- no trailing slash;
- no `*`, `?`, or `[` glob character;
- no duplicate normalized path;
- no symlink file or symlink parent component;
- no path outside the two exact package identities;
- no runtime artifact under `~/PrinterOperations` is included because it is
  outside the repository;
- SQLite sidecars remain separately owned by the existing fixed sidecar tuple.

### 6.5 Authorization validation

The production validator reads the referenced repository-local
`final_authorization.json` and requires:

- SHA-256 equals `authorization_file.sha256`;
- authorization ID equals the manifest authorization ID;
- final-authorization verdict is PASS;
- authorized branch and HEAD equal live Git state;
- exact authorized mode is `run`;
- operator approval is required;
- allowed invocation count is one;
- automatic retry, manual rerun, resume, restart, and successor are false;
- ordinary `WINDOW_15M` policy remains exact;
- selective-1h continuation is false.

The consumed authorization is never reusable. Disposable implementation proof
uses fixture authorization. Any future campaign requires a new post-repair
authorization ID.

### 6.6 Manifest file validation

For every manifest file, require:

- file exists and is a regular file;
- path resolves inside the repository and declared package root;
- no symlink or hard-link ambiguity accepted by the implementation contract;
- exact byte size matches;
- exact SHA-256 matches;
- path is unique;
- package kind matches path root;
- authorization package identity matches authorization ID;
- migration package identity matches migration execution ID.

The validator obtains the complete observed untracked set using the same Git
semantics as `capture_git_provenance()` and requires:

`observed_untracked_paths == manifest_file_paths`

The fixed authoritative SQLite runtime sidecars remain separately controlled by
the existing operational tuple.

A manifest-listed file missing from the observed set blocks. An observed file
missing from the manifest blocks.

### 6.7 Manifest integrity

Require:

- absolute manifest path;
- path outside the repository;
- exact external authorization control directory;
- regular non-symlink file;
- lowercase 64-character expected SHA-256;
- actual manifest SHA-256 equals expected value;
- canonical JSON without duplicate keys;
- exact schema and types;
- timezone-aware creation time;
- branch and HEAD match live Git state;
- no path or hash normalization ambiguity.

### 6.8 Marker integrity

After complete manifest validation, the wrapper creates the marker with exclusive
creation, hashes it, and launches the child.

The production validator requires:

- absolute marker path;
- marker outside the repository;
- exact external authorization control directory;
- regular non-symlink file;
- actual marker SHA-256 equals environment value;
- exact marker schema;
- authorization ID matches manifest and authorization file;
- marker manifest SHA-256 matches the validated manifest;
- marker file-set SHA-256 matches the validated file set;
- branch, HEAD, and command match;
- allowed invocation count is one;
- all retry/rerun/resume/restart/successor fields are false.

A missing or mismatched marker blocks before any campaign identity, provider,
source, Scheduler, or database work.

## 7. Canonical file-set digest

Sort manifest file records by path and encode canonical JSON using:

- `sort_keys=True`;
- separators `(',', ':')`;
- ASCII-safe encoding;
- no NaN values.

Hash the canonical bytes with SHA-256 to produce:

`git_provenance_allowed_file_set_sha256`

Record the digest in:

- the external marker;
- operational preflight result;
- campaign configuration/launch provenance;
- terminal evidence.

The existing six-field `git_provenance` object remains unchanged and canonical.

## 8. Production integration boundary

### 8.1 New focused module

Preferred new module:

`src/printer_v1/operator_cli/git_provenance_authorization_manifest.py`

Responsibilities:

- load explicit manifest and marker paths/hashes;
- parse both exact schemas;
- validate authorization JSON;
- validate exact repository path roots;
- validate every file hash and size;
- validate exact observed-untracked equality;
- validate marker-to-manifest binding;
- return an immutable result containing:
  - exact tuple of allowed repository-relative paths;
  - manifest SHA-256;
  - marker SHA-256;
  - file-set SHA-256;
  - authorization ID;
  - file count.

It makes no network request and no database write.

### 8.2 Existing helper

`src/printer_v1/operator_cli/git_provenance.py` remains semantically unchanged.

No directory or glob support is added. Existing malformed-path checks remain.

### 8.3 Operational command

`operational_memory_factory_command.py` changes only at the preflight boundary:

1. read the four environment values;
2. require all four together or none;
3. reject partial configuration;
4. for authorized ordinary `run`, validate manifest and marker;
5. combine the exact validated path tuple with fixed SQLite sidecar paths;
6. call existing `capture_git_provenance()`;
7. reject if `git_untracked_present` remains true;
8. include only bounded manifest/marker summaries in preflight evidence.

No source, Scheduler, campaign, memory, retrieval, or financial ownership moves.

### 8.4 Mode restrictions

The manifest integration is approved only for:

- `preflight-only`, using a disposable non-consumed marker fixture for zero-source
  validation; and
- ordinary `run`, using a real externally created consumed marker.

It is not accepted for:

- `selective-1h-preflight`;
- `selective-1h-proof`;
- `discovery-only`;
- `status`;
- `cooperative-stop`;
- `recover-orphan`;
- `report-only`.

Unsupported modes fail closed if any manifest or marker environment variable is
supplied.

## 9. Correct one-shot wrapper order

The repaired wrapper performs:

1. fresh branch, HEAD, tracked-tree, DB, schema, residue, source-contract, and
   capability-lock gates;
2. enumerate all current repository untracked evidence files;
3. prove each existing file belongs to an approved immutable package;
4. write future authorization-specific repository-local `pre_run_evidence.json`;
5. re-enumerate the complete repository untracked set;
6. hash every file and build the exact manifest;
7. write the manifest outside the repository;
8. hash and fully validate the manifest using the production validator in
   non-consuming validation mode;
9. recheck branch, HEAD, DB identity, file hashes, and exact observed set;
10. create external `application_started.json` exactly once;
11. hash the marker;
12. launch the exact ordinary PowerShell command once with all four environment
    values;
13. production preflight revalidates manifest and marker;
14. capture terminal evidence;
15. never retry.

The irreversible marker is the final pre-launch boundary. No manifest, file-set,
or repository validation remains pending when it is created.

## 10. Failure law

Before the external marker exists:

- any validation failure blocks without consuming authorization;
- wrapper may exit safely;
- no campaign command is launched.

After the marker exists:

- authorization is consumed;
- any marker validation or launch failure remains terminal;
- no retry, rerun, resume, restart, or successor is allowed;
- no automatic manifest repair is allowed;
- no evidence deletion, ignore mutation, or package relocation is allowed;
- terminal evidence records the first failure exactly.

## 11. Implementation scope

Allowed implementation files:

- `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py`;
- `src/printer_v1/operator_cli/operational_memory_factory_command.py`;
- focused tests for the new module and preflight boundary;
- a future authorization-specific external wrapper artifact after code closeout.

Possible test-only fixtures are allowed under focused test paths.

Not approved without a new design decision:

- `.gitignore`;
- `.git/info/exclude`;
- global Git config;
- migration files or database schema;
- Source Governor or Central Scheduler;
- discovery, holder, snapshot, memory, retrieval, or paper-trading code;
- PowerShell public parameters;
- broad launcher or campaign architecture changes.

## 12. Minimum sufficient proof

### 12.1 Unit and focused integration tests

1. valid external manifest and marker with exact approved files pass;
2. no allowlist reproduces untracked state when evidence exists;
3. one unrelated untracked file blocks;
4. one missing manifest file blocks;
5. one hash mismatch blocks;
6. one size mismatch blocks;
7. duplicate normalized path blocks;
8. wrong package kind blocks;
9. wrong authorization ID blocks;
10. wrong branch or HEAD blocks;
11. non-PASS authorization blocks;
12. wrong command or selective-1h authorization blocks;
13. directory, glob, absolute, traversal, symlink, or out-of-root path blocks;
14. manifest or marker inside repository blocks;
15. manifest hash mismatch blocks;
16. marker hash mismatch blocks;
17. marker-to-manifest digest mismatch blocks;
18. malformed or extra schema keys block;
19. staged changes block;
20. unstaged changes block;
21. extra observed file absent from manifest blocks;
22. manifest-listed file absent from observed set blocks;
23. partial environment configuration blocks;
24. fixed SQLite sidecars remain separately allowed only by exact names;
25. unsupported public modes reject manifest/marker environment;
26. no marker is created when pre-marker validation fails;
27. marker exclusive creation prevents a second invocation.

### 12.2 Disposable proof

Run one bounded disposable proof with:

- temporary Git repository;
- copied evidence-package fixtures;
- disposable authorization and marker fixtures;
- disposable DB or no DB where function-level proof permits;
- no provider keys required;
- no network access;
- no authoritative DB mutation;
- no Source Governor or Scheduler runtime;
- no campaign creation;
- no memory, retrieval, decision, position, trade, audit, or PnL work.

Required observations:

- no-allowlist path reports untracked;
- exact manifest and marker report no unexpected untracked file;
- unrelated-file negative case blocks;
- file-hash negative case blocks;
- marker-hash negative case blocks;
- tracked staged/unstaged cases block;
- manifest and file-set digests are deterministic;
- failed pre-marker validation leaves no application marker.

### 12.3 Risk-based test boundary

Run focused tests for:

- manifest/marker parser and validator;
- existing Git-provenance helper interaction;
- ordinary activation preflight boundary;
- mode rejection;
- exclusive marker semantics.

Do not run a broad regression suite during implementation unless focused results
show cross-cutting risk or implementation exceeds this boundary. Reserve the
broader relevant suite for repair closeout and pre-authorization checkpoint.

Document unrelated pre-existing failures without expanding scope.

## 13. Implementation verdicts

The implementation lane must end with one of:

- `V2_9_8B_WINDOW_15M_GIT_PROVENANCE_COMPATIBILITY_IMPLEMENTATION_PASS`;
- `V2_9_8B_WINDOW_15M_GIT_PROVENANCE_COMPATIBILITY_IMPLEMENTATION_BLOCKED`.

PASS requires code, focused tests, and static verification only. It still does
not authorize a campaign or fresh authorization.

## 14. Mandatory sequence after this design

1. implementation;
2. bounded disposable proof;
3. independent repair closeout;
4. repeated authoritative readiness audit;
5. new final authorization;
6. one future campaign attempt.

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
- removes the marker/manifest ordering circularity;
- preserves the existing strict helper as canonical owner;
- prevents broad ignore and directory bypasses;
- binds every exception to authorization identity, branch, HEAD, path, size, and
  SHA-256;
- makes authorization consumption the final irreversible pre-launch action;
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
| Manifest becomes a generic bypass | Rejected | Exact schema, authorization binding, exact roots and hashes |
| Manifest or marker inside repo creates circular trust | Rejected | Both live in external authorization directory |
| Marker created before validation wastes authorization | Rejected | Complete validation before exclusive marker creation |
| Operator changes manifest and environment together | Fail closed through authorization, branch, HEAD, command, file-set and marker binding | Future authorization pins implementation and wrapper hashes |
| Missing manifest-listed file could otherwise pass helper | Explicitly handled | Exact observed-set equality |
| Extra unrelated untracked file | Must block | Equality plus existing helper |
| Symlink or path normalization ambiguity | Must block | Resolve and reject ambiguity |
| Broad `operator-runs/` exemption | Rejected | Exact files only |
| Migration package is large | Accepted bounded cost | Stream SHA-256; no content copying |
| Rehashing backup adds launch cost | Accepted | Hash during manifest build and production validation |
| Existing helper payload omits filenames | Preserved | Separate manifest summary and file-set digest |
| Selective-1h or discovery inherits exception | Rejected | Ordinary preflight/run only |
| Fresh authorization issued too early | Blocked | Implementation, proof, closeout, and readiness first |

## 19. Exact next permitted lane

`V2-9.8B WINDOW_15M One-Shot Wrapper Git-Provenance Compatibility Implementation`

Type: narrowly scoped implementation and focused static/unit verification.

It may implement only this approved manifest/marker integration and focused
tests. It may not run providers, source fetching, discovery, Scheduler runtime,
a campaign, memory generation, retrieval, paper decisions, positions, trades,
audits, or PnL. It may not issue a fresh campaign authorization.